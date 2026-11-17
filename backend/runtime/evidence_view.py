"""
Choosing which evidence goes into an LLM prompt when there is more than fits.

The old rule, "the last N items", silently dropped whatever was loaded first (the
CI/CD evidence).  This keeps every *kind* of evidence represented:

1. the specialist's own layer gets up to 60% of the budget (a Kubernetes analyst
   sees mostly Kubernetes evidence), the rest goes to the other layers;
2. inside a budget, the strongest item of every evidence type is taken first,
   then the rest by confidence;
3. the prompt says what was left out ("12 more not shown: log 9, trace 3"), so the
   model knows its view is partial.

Output keeps the original order, so it still reads as a timeline.
"""

from collections import Counter
from typing import Callable, List, Optional

from backend.models import Evidence

OWN_LAYER_SHARE = 0.6


def _type(item: Evidence) -> str:
    return str(getattr(item.evidence_type, "value", item.evidence_type))


def _pick(items: List[Evidence], budget: int) -> List[Evidence]:
    """Strongest of every type first, then by confidence, up to `budget` items."""
    if budget <= 0:
        return []
    ranked = sorted(items, key=lambda e: -e.confidence)
    chosen, seen_types = [], set()
    for item in ranked:                       # pass 1: one per type
        if _type(item) not in seen_types and len(chosen) < budget:
            chosen.append(item)
            seen_types.add(_type(item))
    for item in ranked:                       # pass 2: fill the rest
        if len(chosen) >= budget:
            break
        if item not in chosen:
            chosen.append(item)
    return chosen


def select_evidence(evidence: List[Evidence], limit: int, focus_agent: Optional[str] = None) -> List[Evidence]:
    """Up to `limit` items, original order preserved, balanced as described in the module docstring."""
    if len(evidence) <= limit:
        return list(evidence)
    own = [e for e in evidence if focus_agent and e.agent_type == focus_agent]
    other = [e for e in evidence if e not in own]
    own_budget = min(len(own), round(limit * OWN_LAYER_SHARE)) if own else 0
    chosen = _pick(own, own_budget) + _pick(other, limit - own_budget)
    if len(chosen) < limit:                   # the other layers had less than their share
        chosen += _pick([e for e in own if e not in chosen], limit - len(chosen))
    keep = {id(e) for e in chosen}
    return [e for e in evidence if id(e) in keep]


def format_evidence(
    evidence: List[Evidence], limit: int = 40, focus_agent: Optional[str] = None, description_chars: int = 300,
) -> str:
    """Prompt text for the evidence list, with a note on what was left out."""
    if not evidence:
        return "No evidence collected yet."
    shown = select_evidence(evidence, limit, focus_agent)
    lines = [f"  - evidence_id={e.evidence_id} [{e.agent_type}] {_type(e)}: {e.description[:description_chars]}" for e in shown]
    hidden = Counter(_type(e) for e in evidence if e not in shown)
    if hidden:
        lines.append(f"  ({sum(hidden.values())} more items not shown: "
                     + ", ".join(f"{t} {n}" for t, n in hidden.most_common()) + ")")
    return "\n".join(lines)
