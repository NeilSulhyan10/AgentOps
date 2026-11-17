"""
Dynamic agent spawner: create a specialist while an investigation is running.

Why: the specialists that ship as ``.md`` files cannot cover every incident.
When the incident (or the critic) points at something none of them owns - a
cache, a message queue, DNS, a full disk, an expired certificate, rate limiting -
the ``spawn_agent`` node asks this module for a new specialist.

How: ``FOCUS_CATALOG`` describes each kind of problem we know how to look for
(keywords, which evidence is relevant, what it concludes).  ``spawn`` turns a
matching focus into an ``AgentSpec`` + a prompt rendered from
``agents/markdown/_template.md`` and registers it for THIS investigation only.
From then on it is an ordinary specialist: the router can pick it, the runner
runs it (LLM with the rendered prompt, or its keyword rules), and the flow
report shows it as spawned.

To keep an agent you like, call ``save_agent`` (or POST /api/agents): it writes
a real ``.md`` file and the agent is available to every future investigation.

To teach the spawner a new kind of problem, add one entry to ``FOCUS_CATALOG``.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from backend.runtime.agent_spec import LAYERS, AgentSpec

TEMPLATE = Path(__file__).parent.parent / "agents" / "markdown" / "_template.md"
AGENTS_DIR = TEMPLATE.parent


@dataclass(frozen=True)
class Focus:
    key: str                 # becomes "<key>_analyzer"
    title: str
    layer: str               # one of agent_spec.LAYERS
    hypothesis: str          # what the agent concludes when its evidence matches
    keywords: tuple          # words that mark evidence and incident text as relevant
    evidence_types: tuple
    looks_for: str           # one sentence for the prompt and the UI


FOCUS_CATALOG: Dict[str, Focus] = {f.key: f for f in [
    Focus("cache", "Cache", "dependency", "dependency_issue",
          ("cache", "redis", "memcache", "eviction", "evicting", "maxmemory", "hit ratio"),
          ("log", "error_rate", "latency", "stack_trace"),
          "cache servers that are full, evicting keys, or no longer absorbing load"),
    Focus("queue", "Message queue", "dependency", "dependency_issue",
          ("queue", "kafka", "rabbit", "consumer lag", "backlog", "dead letter"),
          ("log", "error_rate", "latency", "trace"),
          "queues and brokers with growing backlogs or stuck consumers"),
    Focus("network", "Network and DNS", "dependency", "dependency_issue",
          ("dns", "name resolution", "connection reset", "no route", "packet loss", "tls handshake"),
          ("log", "trace", "stack_trace", "error_rate"),
          "name resolution, connection resets and other network-level failures"),
    Focus("storage", "Storage", "kubernetes", "application_error",
          ("disk", "no space left", "volume", "pvc", "inode", "ephemeral-storage", "evicted"),
          ("log", "pod_event", "resource_usage"),
          "full disks, exhausted volumes and ephemeral-storage evictions"),
    Focus("certificate", "Certificates", "config", "configuration_error",
          ("certificate", "x509", "expired", "ssl", "tls"),
          ("log", "stack_trace", "pod_event", "config_change"),
          "expired or untrusted certificates and TLS misconfiguration"),
    Focus("rate_limit", "Rate limiting", "traffic", "traffic_incident",
          ("429", "rate limit", "throttl", "quota", "too many requests"),
          ("log", "error_rate", "latency"),
          "requests being throttled by this service or by a provider it calls"),
]}

# investigation_id -> {agent name -> spec}.  In memory on purpose: spawned agents belong to one run.
_spawned: Dict[str, Dict[str, AgentSpec]] = {}


def agent_name(focus: Focus) -> str:
    return f"{focus.key}_analyzer"


def find_focuses(text: str) -> List[Focus]:
    """Focuses whose keywords appear in `text`, best match (most keywords) first."""
    text = " ".join(str(text).lower().replace("_", " ").split())
    scored = [(sum(1 for k in f.keywords if re.search(rf"(?<!\w){re.escape(k)}", text)), f) for f in FOCUS_CATALOG.values()]
    return [f for score, f in sorted(scored, key=lambda s: -s[0]) if score > 0]


def render_prompt(focus: Focus) -> str:
    return TEMPLATE.read_text(encoding="utf-8").format(
        name=agent_name(focus), title=focus.title, looks_for=focus.looks_for,
        hypothesis=focus.hypothesis, keywords=", ".join(focus.keywords), evidence_types=", ".join(focus.evidence_types),
    )


Request = Tuple[Focus, str]       # (what to look for, why we think so)


def requests_from_text(texts: List[str]) -> List[Request]:
    """One request per text, for the focus that matches it best (the text becomes the reason)."""
    return [(found[0], " ".join(str(t).split())[:200]) for t in texts if (found := find_focuses(t))]


def spawn(investigation_id: str, requests: List[Request], existing: List[str]) -> List[AgentSpec]:
    """
    Spawn a specialist for each request that no existing agent covers
    (`existing` = names already available).  Returns the new specs.
    """
    made: List[AgentSpec] = []
    for focus, reason in requests:
        name = agent_name(focus)
        if name in existing or name in _spawned.get(investigation_id, {}):
            continue
        spec = AgentSpec(
            name=name, description=f"{focus.title}: {focus.looks_for}", layer=focus.layer,
            hypothesis=focus.hypothesis, evidence_types=list(focus.evidence_types),
            keywords=list(focus.keywords), max_confidence=0.8, origin="spawned", reason=reason,
        )
        _spawned.setdefault(investigation_id, {})[name] = spec
        _prompts[(investigation_id, name)] = render_prompt(focus)
        made.append(spec)
    return made


_prompts: Dict[tuple, str] = {}


def spawned_for(investigation_id: str) -> Dict[str, AgentSpec]:
    return _spawned.get(investigation_id, {})


def spawned_prompt(investigation_id: str, name: str) -> Optional[str]:
    return _prompts.get((investigation_id, name))


def forget(investigation_id: str) -> None:
    """Drop a finished investigation's spawned agents (their record lives on in the flow log)."""
    _spawned.pop(investigation_id, None)
    for key in [k for k in _prompts if k[0] == investigation_id]:
        _prompts.pop(key, None)


def save_agent(spec: AgentSpec, prompt_body: Optional[str] = None) -> Path:
    """Write `spec` as a permanent specialist (.md with front-matter); the loader picks it up on reload."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", spec.name):
        raise ValueError("agent name must be lowercase letters, digits and underscores, e.g. 'cache_analyzer'")
    if spec.layer not in LAYERS:
        raise ValueError(f"layer must be one of {', '.join(LAYERS)}")
    path = AGENTS_DIR / f"{spec.name}.md"
    if path.exists():
        raise FileExistsError(f"{spec.name} already exists")
    meta = {"description": spec.description, "layer": spec.layer, "hypothesis": spec.hypothesis,
            "evidence_types": spec.evidence_types, "keywords": spec.keywords}
    if spec.incident_keywords:
        meta["incident_keywords"] = spec.incident_keywords
    body = prompt_body or TEMPLATE.read_text(encoding="utf-8").format(
        name=spec.name, title=spec.name.replace("_", " ").title(), looks_for=spec.description,
        hypothesis=spec.hypothesis, keywords=", ".join(spec.keywords), evidence_types=", ".join(spec.evidence_types))
    path.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    return path
