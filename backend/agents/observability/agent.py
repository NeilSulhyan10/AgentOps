"""
Rule-based observability specialist.

Reads latency, error rate, logs and stack traces and decides which pattern
they show (first match wins):

    dependency down   error logs say unreachable / connection refused / upstream  -> dependency_issue
    missing config    error logs say env var not set / missing secret              -> configuration_error
    slow and failing  p99 above 2 s AND error rate above 10%                       -> traffic_incident
    memory kills      logs mention OOM kills                                       -> kubernetes_oom
    errors only       error rate above 10%, or stack traces                        -> application_error
    all quiet         metrics normal                                               -> unknown ("nothing wrong here")
"""

from typing import Any, Dict, List

from backend.agents.signals import contains, ids, of_type, result
from backend.models import AgentFinding, Evidence, HypothesisType, Incident

_DEPENDENCY_DOWN = r"unreachable|connection refused|cannot connect|could not connect|upstream (?:error|unavailable)"
_CONFIG_MISSING = r"env var|not set|missing (?:env|secret|config)|secret"
_OOM = r"\boom\b|oomkill|exit code 137"


class ObservabilityAgent:
    AGENT_NAME = "observability_analyzer"

    def __init__(self):
        self.agent_type = self.AGENT_NAME

    def investigate(self, incident: Incident, existing_evidence: List[Evidence]) -> AgentFinding:
        found = self._analyze_evidence(incident, existing_evidence)
        return AgentFinding(
            investigation_id="", agent_type=self.agent_type, iteration=0,
            hypothesis=found["hypothesis"], finding=found["finding"], evidence=found["evidence"],
            confidence=found["confidence"], reasoning=found["reasoning"],
        )

    def _analyze_evidence(self, incident: Incident, evidence: List[Evidence]) -> Dict[str, Any]:
        latency = of_type(evidence, "latency")
        errors = of_type(evidence, "error_rate")
        logs = of_type(evidence, "log")
        stacks = of_type(evidence, "stack_trace")
        traces = of_type(evidence, "trace")
        if not (latency or errors or logs or stacks or traces):
            return result(HypothesisType.UNKNOWN, "No observability evidence found for this incident", [], 0.1,
                          "No metrics, logs, or traces available")

        p99 = max((self._number(e.raw_data.get("p99")) for e in latency), default=0.0)
        rate = max((self._number(e.raw_data.get("rate")) for e in errors), default=0.0)
        slow, failing = p99 > 2000, rate > 10

        dependency = [e for e in logs + stacks if contains(e.description, _DEPENDENCY_DOWN)]
        if dependency:
            return result(
                HypothesisType.DEPENDENCY_ISSUE,
                f"The service cannot reach something it depends on ({dependency[0].description}); "
                f"error rate {rate:g}%, latency itself is {p99:g} ms so the app is not overloaded",
                ids(dependency + errors), 0.9, "; ".join(e.description for e in dependency[:3]),
            )

        missing = [e for e in logs + stacks if contains(e.description, _CONFIG_MISSING)]
        if missing:
            return result(
                HypothesisType.CONFIGURATION_ERROR,
                f"The application aborts because a setting is missing ({missing[0].description})",
                ids(missing), 0.85, "; ".join(e.description for e in missing[:3]),
            )

        if slow and failing:
            return result(
                HypothesisType.TRAFFIC_INCIDENT,
                f"Requests are slow (p99 {p99:g} ms) and {rate:g}% of them fail",
                ids(latency + errors + traces), 0.85, "; ".join(e.description for e in (latency + errors)[:3]),
            )

        oom = [e for e in logs if contains(e.description, _OOM)]
        if oom:
            return result(
                HypothesisType.KUBERNETES_OOM,
                f"Logs show the container being killed for memory: {oom[0].description}",
                ids(oom + errors), 0.8, "; ".join(e.description for e in oom[:3]),
            )

        if failing or stacks:
            proof = errors + stacks
            return result(
                HypothesisType.APPLICATION_ERROR,
                f"The application is erroring ({rate:g}% errors, {len(stacks)} stack traces)" if failing
                else f"Stack traces show application errors: {stacks[0].description}",
                ids(proof), 0.8, "; ".join(e.description for e in proof[:3]),
            )

        if slow:
            return result(HypothesisType.TRAFFIC_INCIDENT, f"Latency is high (p99 {p99:g} ms) without errors",
                          ids(latency), 0.75, "; ".join(e.description for e in latency[:2]))

        return result(
            HypothesisType.UNKNOWN,
            f"Metrics look normal: p99 {p99:g} ms, error rate {rate:g}%, no error logs",
            ids(latency + errors + logs), 0.3, "No anomaly in latency, error rate, logs or traces.",
        )

    @staticmethod
    def _number(value: Any) -> float:
        return float(value) if isinstance(value, (int, float)) else 0.0
