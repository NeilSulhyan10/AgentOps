"""Small helpers shared by the rule-based specialists (the Python twins of the .md agents)."""

import re
from typing import Any, Dict, Iterable, List, Optional

from backend.models import Evidence

_UNITS = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1024 * 1024}


def mem_mi(value: Any) -> Optional[float]:
    """'127Mi' -> 127.0, '1Gi' -> 1024.0, anything unparseable -> None."""
    match = re.fullmatch(r"\s*([\d.]+)\s*(Ki|Mi|Gi|Ti)?\s*", str(value))
    if not match:
        return None
    return float(match.group(1)) * _UNITS.get(match.group(2) or "Mi", 1)


def of_type(evidence: Iterable[Evidence], *types: str) -> List[Evidence]:
    """Evidence items whose type is one of `types` (enum or plain string)."""
    wanted = set(types)
    return [e for e in evidence if getattr(e.evidence_type, "value", e.evidence_type) in wanted]


def contains(text: Any, pattern: str) -> bool:
    """Case-insensitive regex search over text; `_` counts as a space ('db_down' matches 'db down')."""
    return re.search(pattern, str(text).lower().replace("_", " ")) is not None


def ids(items: Iterable[Evidence]) -> List[str]:
    return [e.evidence_id for e in items]


def result(hypothesis, finding: str, evidence: List[str], confidence: float, reasoning: str) -> Dict[str, Any]:
    """The dict every specialist's `_analyze_evidence` returns."""
    return {
        "hypothesis": hypothesis,
        "finding": finding,
        "evidence": evidence,
        "confidence": round(confidence, 2),
        "reasoning": reasoning,
    }
