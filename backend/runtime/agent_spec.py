"""
AgentSpec: what the system needs to know about a specialist besides its prompt.

A specialist is a Markdown file in ``backend/agents/markdown/``.  The optional
front-matter at the top of the file tells the *rule-based* twin what to look
for, so a new agent works in rules mode without any Python::

    ---
    description: Cache health (Redis, Memcached)         # shown in the UI and to the router
    layer: dependency                                    # where it sits on the app map
    hypothesis: dependency_issue                         # what it concludes when it matches
    evidence_types: [log, error_rate, latency]           # evidence it reads
    keywords: [cache, redis, eviction]                   # words that make evidence relevant
    incident_keywords: []                                # only run when the incident mentions one
    ---

Without front-matter the agent still works in LLM mode; in rules mode it
reports "found nothing".
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

LAYERS = ("cicd", "config", "kubernetes", "service", "traffic", "dependency")


@dataclass
class AgentSpec:
    name: str
    description: str = ""
    layer: str = "service"
    hypothesis: str = "unknown"
    evidence_types: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    incident_keywords: List[str] = field(default_factory=list)
    max_confidence: float = 0.65    # keyword rules guess; a spawned agent (made for exactly this problem) may reach 0.8
    origin: str = "file"            # "file" (an .md in agents/markdown) or "spawned" (made during an investigation)
    reason: str = ""                # why it was spawned
    path: Optional[str] = None

    @property
    def has_rules(self) -> bool:
        return bool(self.keywords and self.evidence_types and self.hypothesis != "unknown")

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in (
            "name", "description", "layer", "hypothesis", "evidence_types",
            "keywords", "incident_keywords", "max_confidence", "origin", "reason")}


def split_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """('---\\nkey: v\\n---\\nbody') -> ({'key': 'v'}, 'body'); no front-matter -> ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), parts[2].lstrip("\n")


def spec_from_markdown(name: str, text: str, path: Optional[str] = None) -> Tuple[AgentSpec, str]:
    """Parse one agent file into (spec, prompt body without front-matter)."""
    meta, body = split_front_matter(text)
    as_list = lambda v: [str(x).lower() for x in v] if isinstance(v, list) else []   # noqa: E731
    spec = AgentSpec(
        name=name,
        description=str(meta.get("description") or _first_paragraph(body, "## Role")),
        layer=str(meta.get("layer", "service")),
        hypothesis=str(meta.get("hypothesis", "unknown")),
        evidence_types=as_list(meta.get("evidence_types")),
        keywords=as_list(meta.get("keywords")),
        incident_keywords=as_list(meta.get("incident_keywords")),
        path=path,
    )
    return spec, body


def _first_paragraph(body: str, heading: str) -> str:
    """The first line under `heading` in the Markdown body, or ''."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == heading:
            for follow in lines[i + 1:]:
                if follow.strip():
                    return follow.strip()
    return ""
