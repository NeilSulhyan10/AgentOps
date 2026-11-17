"""Measure how often AgentOps finds the right root cause, and whether its confidence means anything.

  python scripts/evaluate.py                    rules engine on the fixture scenarios
  python scripts/evaluate.py --live             ... plus a real ShopLite broken on purpose (see backend/live/shoplite.py)
  python scripts/evaluate.py --live --llm       ... and the same evidence again with the LLM from .env
  python scripts/evaluate.py --only live        only the live scenarios
  python scripts/evaluate.py --faults crash oom --live --only live

Every engine sees exactly the same evidence, so the comparison is fair.  Writes
docs/eval/latest.md and latest.json (use --out to change the folder).

Groups:
  shoplite-fixtures   the seven hand-written ShopLite scenarios (the rules were tuned on these)
  other-fixtures      the other hand-written incidents
  live                real ShopLite, evidence nobody wrote
  live-held-out       a live fault no fixture or rule was written for (crash)
"""

import argparse
import asyncio
import copy
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.flow import build_trace, read_events  # noqa: E402
from backend.live.shoplite import EXPECTED, HELD_OUT, LabResult, run_lab  # noqa: E402
from backend.llm import reset_llm_provider  # noqa: E402
from backend.orchestrator import create_initial_state, run_investigation  # noqa: E402
from backend.services.apps import expected_root_cause  # noqa: E402
from backend.services.scenarios import list_scenarios, load_scenario_incident  # noqa: E402

BUCKETS = [(0.0, 0.5), (0.5, 0.75), (0.75, 0.9), (0.9, 1.0001)]
CONFIGURED_PROVIDER = settings.llm_provider          # what .env asks for, before we force rules


def group_of(scenario_id: str, live: bool) -> str:
    if live:
        return "live-held-out" if scenario_id.split(":")[1] in HELD_OUT else "live"
    return "shoplite-fixtures" if scenario_id.startswith("shoplite-") else "other-fixtures"


async def run_one(engine: str, scenario_id: str, group: str, expected: str, state) -> Dict[str, Any]:
    settings.llm_provider = "rules" if engine == "rules" else CONFIGURED_PROVIDER
    settings.fault_injection = ""
    reset_llm_provider()
    started = time.perf_counter()
    final = await run_investigation(state)
    took = time.perf_counter() - started
    events = read_events(final.investigation_id)
    trace = build_trace(events)
    calls = [e for e in events if e["event"] == "llm_call"]
    got = trace.root_cause_type or "none (failed)"
    return {
        "engine": engine, "group": group, "scenario": scenario_id, "expected": expected, "got": got,
        "correct": got == expected, "confidence": round(trace.confidence, 2), "status": trace.final_status,
        "agents": [a for a in dict.fromkeys(final.agents_invoked)], "flagged_steps": len(trace.problems),
        "seconds": round(took, 1), "llm_calls": len(calls), "llm_tokens": sum(c.get("tokens") or 0 for c in calls),
        "llm_seconds": round(sum(c.get("duration_ms") or 0 for c in calls) / 1000, 1),
        "fallbacks": sum(1 for e in events if e["event"] == "llm_parse_fallback"),
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Accuracy, calibration and cost for one set of rows."""
    n = len(rows)
    right = [r for r in rows if r["correct"]]
    wrong = [r for r in rows if not r["correct"]]
    diagnosable = [r for r in rows if r["expected"] != "unknown"]
    healthy = [r for r in rows if r["expected"] == "unknown"]
    buckets = []
    for lo, hi in BUCKETS:
        inside = [r for r in diagnosable if lo <= r["confidence"] < hi]
        buckets.append({"range": f"{lo:.2f}-{min(hi, 1.0):.2f}", "n": len(inside),
                        "accuracy": round(sum(r["correct"] for r in inside) / len(inside), 2) if inside else None})
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None   # noqa: E731
    return {
        "n": n, "accuracy": round(len(right) / n, 2) if n else None,
        "mean_confidence_when_right": mean([r["confidence"] for r in right]),
        "mean_confidence_when_wrong": mean([r["confidence"] for r in wrong]),
        "brier": mean([(r["confidence"] - r["correct"]) ** 2 for r in diagnosable]),
        "false_alarms": f"{sum(not r['correct'] for r in healthy)}/{len(healthy)}" if healthy else "-",
        "calibration": buckets,
        "mean_seconds": mean([r["seconds"] for r in rows]), "llm_calls": sum(r["llm_calls"] for r in rows),
        "llm_tokens": sum(r["llm_tokens"] for r in rows), "fallbacks": sum(r["fallbacks"] for r in rows),
    }


def to_markdown(rows: List[Dict[str, Any]], engines: List[str], notes: List[str]) -> str:
    out = ["# Evaluation: does AgentOps find the right root cause?", "",
           f"Generated {datetime.now():%Y-%m-%d %H:%M} by `python scripts/evaluate.py`. " + " ".join(notes), ""]
    out += ["## Accuracy", "", "| Group | " + " | ".join(f"{e}" for e in engines) + " |", "|---|" + "---|" * len(engines)]
    groups = list(dict.fromkeys(r["group"] for r in rows)) + ["all"]
    for g in groups:
        cells = []
        for e in engines:
            sel = [r for r in rows if r["engine"] == e and (g == "all" or r["group"] == g)]
            s = summarize(sel)
            cells.append(f"{sum(r['correct'] for r in sel)}/{s['n']} ({s['accuracy']:.0%})" if s["n"] else "-")
        out.append(f"| {g} | " + " | ".join(cells) + " |")
    out += ["", "## Is the confidence meaningful?", "",
            "Brier score is the mean squared gap between confidence and being right (0 is perfect, 0.25 is a coin flip), over incidents that have a real cause. "
            "A useful confidence is high when right and low when wrong.", "",
            "| Engine | Mean conf. when right | Mean conf. when wrong | Brier | False alarms on healthy |", "|---|---|---|---|---|"]
    for e in engines:
        s = summarize([r for r in rows if r["engine"] == e])
        out.append(f"| {e} | {s['mean_confidence_when_right']} | {s['mean_confidence_when_wrong']} | {s['brier']} | {s['false_alarms']} |")
    out += ["", "Accuracy by confidence band (incidents with a real cause):", "", "| Engine | " + " | ".join(b['range'] for b in summarize(rows)['calibration']) + " |",
            "|---|" + "---|" * len(BUCKETS)]
    for e in engines:
        cal = summarize([r for r in rows if r["engine"] == e])["calibration"]
        out.append(f"| {e} | " + " | ".join(f"{b['accuracy']:.0%} (n={b['n']})" if b["n"] else "-" for b in cal) + " |")
    out += ["", "## Cost", "", "| Engine | Mean seconds per run | LLM calls | LLM tokens | Unusable LLM answers |", "|---|---|---|---|---|"]
    for e in engines:
        s = summarize([r for r in rows if r["engine"] == e])
        out.append(f"| {e} | {s['mean_seconds']} | {s['llm_calls']} | {s['llm_tokens']} | {s['fallbacks']} |")
    out += ["", "## Every run", "", "| Engine | Group | Scenario | Expected | Got | Conf. | Agents | Flagged | s |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["group"], r["scenario"], r["engine"])):
        out.append(f"| {r['engine']} | {r['group']} | `{r['scenario']}` | {r['expected']} | {'**' + r['got'] + '**' if not r['correct'] else r['got']}"
                   f" | {r['confidence']} | {', '.join(a.replace('_analyzer', '') for a in r['agents'])} | {r['flagged_steps']} | {r['seconds']} |")
    return "\n".join(out) + "\n"


async def main(args) -> int:
    logging.basicConfig(level=logging.ERROR)
    engines = ["rules"] + (["llm"] if args.llm else [])
    if args.llm and CONFIGURED_PROVIDER in ("rules", "mock", ""):
        sys.exit("--llm needs an LLM: set LLM_PROVIDER (and its API key) in .env")

    work: List[tuple] = []          # (scenario_id, group, expected, make_state)
    if args.only in ("all", "fixtures"):
        for s in list_scenarios():
            expected = expected_root_cause(s["scenario_id"])
            if expected and (not args.scenarios or s["scenario_id"] in args.scenarios):
                incident = load_scenario_incident(s["scenario_id"])
                work.append((s["scenario_id"], group_of(s["scenario_id"], False), expected,
                             lambda i=incident: create_initial_state(i, settings.max_iterations)))
    labs: Dict[str, LabResult] = {}
    if args.live or args.only == "live":
        for fault in args.faults or list(EXPECTED):
            print(f"live lab: breaking a real ShopLite with {fault} ...", flush=True)
            labs[fault] = await run_lab(fault)
            lab = labs[fault]
            sid = f"live:{fault}"

            def make(lab=lab):
                state = create_initial_state(copy.deepcopy(lab.incident), settings.max_iterations)
                state.evidence = copy.deepcopy(lab.evidence)
                return state
            if args.only != "fixtures":
                work.append((sid, group_of(sid, True), lab.expected_root_cause, make))
    if args.only == "live":
        work = [w for w in work if w[0].startswith("live:")]

    rows: List[Dict[str, Any]] = []
    for scenario_id, group, expected, make_state in work:
        for engine in engines:
            row = await run_one(engine, scenario_id, group, expected, make_state())
            rows.append(row)
            print(f"{engine:<5} {scenario_id:<26} {'OK ' if row['correct'] else 'BAD'} expected={expected:<26} got={row['got']:<26} conf={row['confidence']}", flush=True)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = [f"Engines: {', '.join(engines)}" + (f" (LLM: {CONFIGURED_PROVIDER})" if args.llm else "") + "."]
    (out_dir / "latest.md").write_text(to_markdown(rows, engines, notes), encoding="utf-8")
    (out_dir / "latest.json").write_text(json.dumps({"rows": rows, "summary": {e: summarize([r for r in rows if r["engine"] == e]) for e in engines}}, indent=2), encoding="utf-8")
    print(f"\nWrote {out_dir / 'latest.md'}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="also run the LLM configured in .env on the same evidence")
    parser.add_argument("--live", action="store_true", help="include a real, broken ShopLite")
    parser.add_argument("--only", choices=["all", "fixtures", "live"], default="all")
    parser.add_argument("--faults", nargs="*", choices=list(EXPECTED), help="live faults to run (default: all)")
    parser.add_argument("--scenarios", nargs="*", help="fixture scenario ids to run (default: all with ground truth)")
    parser.add_argument("--out", default="docs/eval")
    sys.exit(asyncio.run(main(parser.parse_args())))
