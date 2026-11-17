"""
Fault injection: break AgentOps on purpose, to see how a failure shows up.

Set ``FAULT_INJECTION=<name>`` (or ``scripts/investigate.py run <scenario> --fault <name>``)
and the investigation runs with that one thing broken.  Everything else is decided
by the rule-based implementations, so a fault run needs no LLM key and no network,
and always produces the same flow report.

These faults are inside AgentOps itself.  Faults in the *investigated application*
(a bad deploy, an OOM-killed pod, ...) are the scenarios in ``data/incidents/``.
"""

import json
from typing import Dict

from backend.llm.base import LLMProvider, LLMRequest, LLMResponse

# name -> what breaks, and what you should see in the flow report
FAULTS: Dict[str, str] = {
    "llm_bad_json": "Every LLM answer is prose instead of JSON. Each LLM step falls back to rules (amber on every LLM step).",
    "router_unknown_agent": "The router LLM picks an agent that does not exist. The rule-based router chooses instead (amber at route).",
    "ungrounded_finding": "Specialists cite evidence ids that do not exist. Their findings are ignored, so confidence never rises (amber at invoke_agent).",
    "critic_always_challenges": "The critic rejects every conclusion. The investigation loops back until its rounds run out (amber at critique).",
    "agent_crash": "The specialist's LLM call raises an exception. The investigation fails (red at invoke_agent).",
    "missing_evidence": "No evidence can be loaded for the incident. Nothing can be grounded (amber at load_evidence).",
}


class FaultInjectingLLM(LLMProvider):
    """An LLM stand-in that misbehaves for one kind of call and stays silent for all others."""

    def __init__(self, fault: str):
        if fault not in FAULTS:
            raise ValueError(f"Unknown fault '{fault}'. Known faults: {', '.join(sorted(FAULTS))}")
        self.fault = fault

    @property
    def provider_name(self) -> str:
        return f"rules+fault:{self.fault}"

    @property
    def model_name(self) -> str:
        return "none"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        task = request.metadata.get("task")

        if self.fault == "llm_bad_json":
            return LLMResponse(content="Sure! Looking at the evidence, I think the pod is unhealthy.")

        if self.fault == "router_unknown_agent" and task == "routing":
            return _json(selected_agent="network_analyzer", reasoning="Looks like a network problem.", confidence=0.9)

        if self.fault == "ungrounded_finding" and task == "analysis":
            return _json(
                hypothesis="deployment_induced_failure",
                finding="A recent deployment broke the service.",
                evidence=["evidence-that-does-not-exist-1", "evidence-that-does-not-exist-2"],
                confidence=0.95,
                reasoning="Confident answer with invented evidence ids.",
            )

        if self.fault == "critic_always_challenges" and task == "critic":
            return _json(
                verdict="challenged", hypothesis="unknown", confidence=0.3,
                concerns=["The conclusion is not convincing (injected fault: the critic rejects everything)."],
                missing_checks=["Ask another specialist."], suggested_agent=None,
                reasoning="Injected fault.",
            )

        if self.fault == "agent_crash" and task == "analysis":
            raise RuntimeError("LLM provider timed out after 60s (injected fault: agent_crash)")

        # Not the call this fault targets: no LLM answer, let the rules decide.
        return LLMResponse(content="", skipped=True)


def _json(**payload) -> LLMResponse:
    return LLMResponse(content=json.dumps(payload))
