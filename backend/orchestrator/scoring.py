"""
The confidence formula.

Confidence is computed by AgentOps from the evidence, not just read from what
an agent claims.  Every number below is shown in the Flow tab and the reports.

1. Finding score, per specialist (0 to 1)

       finding = grounding x ( 0.50 x reported + 0.30 x strength + 0.20 x coverage )

   reported   the specialist's own confidence (rules or LLM)
   strength   average confidence of the real evidence items it cites
   coverage   min(1, real cited items / 3): how much independent evidence backs it
   grounding  real cited items / cited items.  A finding that cites evidence which
              does not exist scores 0 however sure it sounds.

2. Investigation confidence, for the root-cause type chosen by ``causal.py``

       overall = clamp( (base + corroboration - contradiction - open_gaps) x critic , 0, 0.99 )

   base           best finding score among the specialists that support the chosen type
   corroboration  +0.05 for each further layer that supports it (at most +0.10)
   contradiction  -0.15 for each strong (>= 0.70) finding that blames a different
                  mechanism (at most -0.30). Parts of a multi-layer failure do not count.
   open_gaps      -0.05 for each question the pre-filter raised that no finding has
                  answered yet (at most -0.15)
   critic         1.0 if the critic confirmed (or has not run), 0.8 if it challenged and
                  the doubt is still open

   Special case, root cause ``unknown`` (everyone found nothing wrong): ``base`` is just the
   highest *reported* value and there is no corroboration. A healthy service is not a
   confident diagnosis, so this stays low (0.3 for the rule-based specialists).

The run stops looking when ``overall`` reaches CONFIDENCE_THRESHOLD (0.75).
If every specialist looked and found nothing wrong, the run also stops, with a low score.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from backend.models import AgentFinding, CriticReview, Evidence, HypothesisType
from backend.orchestrator.causal import NOT_A_CAUSE, SYMPTOM, TRIGGER, STRONG, decide_root_cause

# --- the numbers (change them here; the README table is generated from the same names) ---
W_REPORTED, W_STRENGTH, W_COVERAGE = 0.50, 0.30, 0.20
COVERAGE_FULL_AT = 3            # real cited items that give full coverage
CORROBORATION_EACH, CORROBORATION_MAX = 0.05, 0.10
CONTRADICTION_EACH, CONTRADICTION_MAX = 0.15, 0.30
GAP_EACH, GAP_MAX = 0.05, 0.15
CRITIC_CHALLENGED_FACTOR = 0.8
MAX_CONFIDENCE = 0.99           # never certain

FORMULA = (
    "finding = grounding x (0.50 reported + 0.30 strength + 0.20 coverage);  "
    "overall = (base + corroboration - contradiction - open_gaps) x critic"
)


@dataclass
class FindingScore:
    agent: str
    hypothesis: str
    reported: float
    strength: float
    coverage: float
    grounding: float
    score: float


@dataclass
class ConfidenceBreakdown:
    hypothesis: str = "unknown"
    reason: str = ""
    base: float = 0.0
    corroboration: float = 0.0
    contradiction: float = 0.0
    open_gaps: float = 0.0
    critic: float = 1.0
    overall: float = 0.0
    findings: List[FindingScore] = field(default_factory=list)
    formula: str = FORMULA

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def agent_scores(self) -> Dict[str, float]:
        return {f.agent: f.score for f in self.findings}


def _h(value) -> HypothesisType:
    return value if isinstance(value, HypothesisType) else HypothesisType(value)


def score_finding(finding: AgentFinding, evidence: List[Evidence]) -> FindingScore:
    by_id = {e.evidence_id: e for e in evidence}
    cited = list(dict.fromkeys(finding.evidence))
    real = [by_id[i] for i in cited if i in by_id]
    grounding = len(real) / len(cited) if cited else 0.0
    strength = sum(e.confidence for e in real) / len(real) if real else 0.0
    coverage = min(1.0, len(real) / COVERAGE_FULL_AT)
    score = grounding * (W_REPORTED * finding.confidence + W_STRENGTH * strength + W_COVERAGE * coverage)
    return FindingScore(
        agent=finding.agent_type, hypothesis=_h(finding.hypothesis).value, reported=round(finding.confidence, 2),
        strength=round(strength, 2), coverage=round(coverage, 2), grounding=round(grounding, 2), score=round(score, 2),
    )


def score_investigation(
    findings: List[AgentFinding],
    evidence: List[Evidence],
    evidence_gaps: Optional[List[str]] = None,
    critic: Optional[CriticReview] = None,
) -> ConfidenceBreakdown:
    """Score the investigation so far; see the module docstring for the formula."""
    scored = {id(f): score_finding(f, evidence) for f in findings}
    grounded = [f for f in findings if scored[id(f)].grounding > 0]
    if not grounded:
        return ConfidenceBreakdown(reason="no finding cites real evidence", findings=list(scored.values()))

    root, reason = decide_root_cause(grounded)
    mechanisms = {_h(f.hypothesis) for f in grounded
                  if scored[id(f)].score >= STRONG and _h(f.hypothesis) not in TRIGGER | SYMPTOM | NOT_A_CAUSE}
    if root == HypothesisType.MULTI_LAYER_FAILURE:
        supporting_types = mechanisms | TRIGGER | {HypothesisType.MULTI_LAYER_FAILURE}
    else:
        supporting_types = {root}
    supporters = [f for f in grounded if _h(f.hypothesis) in supporting_types]

    if root == HypothesisType.UNKNOWN:
        # "Nothing found" is not a diagnosis: no credit for strength, coverage or agreement, only what was reported.
        base = max((scored[id(f)].reported * scored[id(f)].grounding for f in supporters), default=0.0)
        corroboration = 0.0
    else:
        base = max((scored[id(f)].score for f in supporters), default=0.0)
        layers = {f.agent_type for f in supporters}
        corroboration = min(CORROBORATION_MAX, CORROBORATION_EACH * max(0, len(layers) - 1))
    dissent = [f for f in grounded
               if scored[id(f)].score >= STRONG and _h(f.hypothesis) in mechanisms and _h(f.hypothesis) not in supporting_types]
    contradiction = min(CONTRADICTION_MAX, CONTRADICTION_EACH * len(dissent))
    open_gaps = min(GAP_MAX, GAP_EACH * len([g for g in (evidence_gaps or []) if not g.startswith("critic:")]))
    factor = CRITIC_CHALLENGED_FACTOR if critic is not None and critic.verdict == "challenged" else 1.0

    overall = max(0.0, min(MAX_CONFIDENCE, (base + corroboration - contradiction - open_gaps) * factor))
    return ConfidenceBreakdown(
        hypothesis=root.value, reason=reason, base=round(base, 2), corroboration=round(corroboration, 2),
        contradiction=round(contradiction, 2), open_gaps=round(open_gaps, 2), critic=factor,
        overall=round(overall, 2), findings=list(scored.values()),
    )
