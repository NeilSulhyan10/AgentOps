"""
Rule-based Kubernetes specialist.

Looks at pod exit codes, restarts, events and memory, and decides which of
these it is (first match wins):

    out of memory   exit 137 / OOMKilled / OOMKilling event      -> kubernetes_oom
    memory pressure usage >= 90% of the limit, nothing killed yet -> kubernetes_oom (weaker)
    startup crash   exits with a non-zero code that is not 137    -> application_error
    failing probes  pods run but readiness/liveness checks fail   -> application_error (weaker)
    healthy         exit 0, no restarts, memory comfortable       -> unknown ("nothing wrong here")

A pod that merely *started* is never evidence of a problem.
"""

from typing import Any, Dict, List

from backend.agents.signals import ids, mem_mi, of_type, result
from backend.models import AgentFinding, Evidence, HypothesisType, Incident

OOM_EVENTS = {"OOMKilling", "OutOfMemory"}
PROBE_EVENTS = {"Unhealthy"}


class KubernetesAgent:
    AGENT_NAME = "kubernetes_analyzer"

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
        pods = of_type(evidence, "pod_exit_code")          # each one carries the whole pod record
        restarts = of_type(evidence, "pod_restart_count")
        events = of_type(evidence, "pod_event")
        usage = of_type(evidence, "resource_usage")
        if not (pods or restarts or events or usage):
            return result(HypothesisType.UNKNOWN, "No Kubernetes evidence found for this incident", [], 0.1,
                          "No pod or resource data available")

        oom_pods = [e for e in pods if e.raw_data.get("exit_code") == 137
                    or e.raw_data.get("last_termination_reason") == "OOMKilled"
                    or e.raw_data.get("status") == "OOMKilled"]
        oom_events = [e for e in events if e.raw_data.get("reason") in OOM_EVENTS]
        if oom_pods or oom_events:
            proof = oom_pods + oom_events
            return result(
                HypothesisType.KUBERNETES_OOM,
                f"{len(oom_pods)} pod(s) were OOMKilled (exit code 137): they used more memory than their limit allows",
                ids(proof), 0.95 if oom_pods else 0.85,
                "; ".join(e.description for e in proof[:4]),
            )

        crashed = [e for e in pods if e.raw_data.get("exit_code") not in (0, None)
                   or e.raw_data.get("status") == "CrashLoopBackOff"]
        restarting = [e for e in restarts if e.raw_data.get("restart_count", 0) > 3]
        if restarting and not crashed:
            return result(
                HypothesisType.APPLICATION_ERROR,
                f"{len(restarting)} pod(s) keep restarting (up to {max(e.raw_data['restart_count'] for e in restarting)} times); "
                "the logs or the application evidence must say why",
                ids(restarting), 0.75, "; ".join(e.description for e in restarting[:3]),
            )
        if crashed:
            codes = sorted({e.raw_data.get("exit_code") for e in crashed})
            peak = max((self._memory_fraction(e) for e in usage), default=0.0)
            return result(
                HypothesisType.APPLICATION_ERROR,
                f"{len(crashed)} pod(s) crash on startup with exit code {', '.join(map(str, codes))}; "
                f"memory is only at {peak:.0%} of the limit, so this is not a resource problem",
                ids(crashed + [e for e in events if e.raw_data.get("reason") in ("BackOff", "Failed")]), 0.8,
                "; ".join(e.description for e in crashed[:3]),
            )

        pressured = [e for e in usage if self._memory_fraction(e) >= 0.9]
        if pressured:
            return result(
                HypothesisType.KUBERNETES_OOM,
                "Memory is at 90% or more of the limit; the pod is close to being OOMKilled",
                ids(pressured), 0.8, "; ".join(e.description for e in pressured[:3]),
            )

        failing_probes = [e for e in events if e.raw_data.get("reason") in PROBE_EVENTS]
        if failing_probes:
            return result(
                HypothesisType.APPLICATION_ERROR,
                f"Pods are running but fail their health checks ({len(failing_probes)} events); "
                "the fault is inside the application or something it depends on, not in Kubernetes",
                ids(failing_probes), 0.6, "; ".join(e.description for e in failing_probes[:3]),
            )

        peak = max((self._memory_fraction(e) for e in usage), default=0.0)
        return result(
            HypothesisType.UNKNOWN,
            f"Pods look healthy: exit code 0, {sum(e.raw_data.get('restart_count', 0) for e in restarts)} restarts, "
            f"memory at most {peak:.0%} of the limit",
            ids(pods + restarts + usage), 0.3, "No crash, OOM, restart or probe failure in the Kubernetes evidence.",
        )

    @staticmethod
    def _memory_fraction(item: Evidence) -> float:
        used, limit = mem_mi(item.raw_data.get("usage")), mem_mi(item.raw_data.get("limit"))
        return used / limit if used is not None and limit else 0.0
