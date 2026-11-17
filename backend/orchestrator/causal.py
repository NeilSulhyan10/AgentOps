"""
Deciding the root-cause TYPE from what the specialists found.

Both the critic and the rule-based RCA need the same answer to "what kind of
failure is this?", so the rule lives here once.

Each finding carries a hypothesis.  They are not equals:

* a **mechanism** is a way a system actually breaks: out of memory, bad
  configuration, a failing dependency, a traffic/latency problem;
* a **trigger** is the change that set a mechanism off: a bad deployment;
* a **symptom** is what the mechanism looks like from outside: application
  errors.  Symptoms never decide the type when a mechanism is known.

Rules, in order (only findings with confidence >= STRONG count):

1. Two or more *different* mechanisms plus a deployment trigger  ->
   ``multi_layer_failure`` (one change broke several layers at once).
2. Otherwise the most confident mechanism wins.
3. If no mechanism, the most confident trigger/symptom wins.
4. If every specialist reports "unknown", the answer is ``unknown``: the
   service looks healthy and we do not invent a cause.
"""

from typing import List, Tuple

from backend.models import AgentFinding, HypothesisType

STRONG = 0.7

TRIGGER = {HypothesisType.DEPLOYMENT_INDUCED_FAILURE}
SYMPTOM = {HypothesisType.APPLICATION_ERROR}
NOT_A_CAUSE = {HypothesisType.UNKNOWN, HypothesisType.MULTI_LAYER_FAILURE}


def _h(finding: AgentFinding) -> HypothesisType:
    value = finding.hypothesis
    return value if isinstance(value, HypothesisType) else HypothesisType(value)


def decide_root_cause(findings: List[AgentFinding]) -> Tuple[HypothesisType, str]:
    """Return (root cause type, one-line reason) for these (already grounded) findings."""
    if not findings:
        return HypothesisType.UNKNOWN, "no findings"

    strong = [f for f in findings if f.confidence >= STRONG and _h(f) != HypothesisType.UNKNOWN]
    if not strong:
        # Nothing confident.  A weak finding may still be the best lead; all-unknown means "nothing wrong".
        best = max(findings, key=lambda f: f.confidence)
        return _h(best), f"best available lead from {best.agent_type} (low confidence)"

    if any(_h(f) == HypothesisType.MULTI_LAYER_FAILURE for f in strong):
        return HypothesisType.MULTI_LAYER_FAILURE, "a specialist reported a multi-layer failure"

    mechanisms = {_h(f) for f in strong if _h(f) not in TRIGGER | SYMPTOM | NOT_A_CAUSE}
    has_trigger = any(_h(f) in TRIGGER for f in strong)
    if len(mechanisms) >= 2 and has_trigger:
        names = ", ".join(sorted(m.value for m in mechanisms))
        return HypothesisType.MULTI_LAYER_FAILURE, f"one change set off several separate failures ({names})"

    mechanism_findings = [f for f in strong if _h(f) in mechanisms]
    if mechanism_findings:
        lead = max(mechanism_findings, key=lambda f: f.confidence)
        return _h(lead), f"most confident mechanism ({lead.agent_type}, {lead.confidence:.2f})"

    lead = max(strong, key=lambda f: f.confidence)
    return _h(lead), f"most confident finding ({lead.agent_type}, {lead.confidence:.2f})"


def found_nothing(grounded: List[AgentFinding], min_layers: int = 2) -> bool:
    """True when at least `min_layers` specialists looked and every one found nothing wrong."""
    layers = {f.agent_type for f in grounded}
    return len(layers) >= min_layers and all(_h(f) == HypothesisType.UNKNOWN for f in grounded)
