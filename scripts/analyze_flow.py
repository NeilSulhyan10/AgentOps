"""Summarise logs/flow.jsonl: per-investigation agent path and overall agent usage.

Usage: python scripts/analyze_flow.py [path] [--id INVESTIGATION_ID]
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="logs/flow.jsonl")
    ap.add_argument("--id", help="only show this investigation")
    args = ap.parse_args()

    runs = defaultdict(list)
    incident_to_inv = {}
    stray = []
    for rec in load(args.path):
        if rec["investigation_id"]:
            runs[rec["investigation_id"]].append(rec)
            if rec.get("incident_id"):
                incident_to_inv[rec["incident_id"]] = rec["investigation_id"]
        else:
            stray.append(rec)
    for rec in stray:  # parse-fallback events only know the incident id
        inv = incident_to_inv.get(rec.get("incident_id"))
        if inv:
            runs[inv].append(rec)

    usage, fallbacks = Counter(), Counter()
    for inv_id, events in runs.items():
        if args.id and inv_id != args.id:
            continue
        events.sort(key=lambda e: e["ts"])
        print(f"\n=== {inv_id} ===")
        for e in events:
            ev = e["event"]
            if ev == "route":
                tag = " [deterministic fallback]" if e["used_deterministic_fallback"] else ""
                print(f"  route #{e['iteration']}: {e['selected_agent']}{tag} ({e['duration_ms']}ms)")
                if e["used_deterministic_fallback"]:
                    fallbacks["router"] += 1
            elif ev == "agent_finding":
                usage[e["agent"]] += 1
                print(f"    {e['agent']}: {e['hypothesis']} conf={e['confidence']:.2f} "
                      f"grounded={e['grounded_evidence']}/{e['cited_evidence']} ({e['duration_ms']}ms)")
            elif ev == "evaluate":
                print(f"  evaluate: overall={e['overall_confidence']:.2f} "
                      f"threshold={e['threshold']} sufficient={e['is_sufficient']}")
            elif ev == "critic":
                usage["critic"] += 1
                nxt = f" -> {e['suggested_agent']}" if e.get("looping_back") else ""
                print(f"  critic #{e['round']}: {e['verdict']} conf={e['confidence']:.2f}{nxt}")
                for c in e.get("concerns", []):
                    print(f"      concern: {c}")
            elif ev == "llm_parse_fallback":
                fallbacks[e["task"]] += 1
                print(f"    ! LLM parse fallback ({e['task']}) {e.get('agent', '')}")
            elif ev in ("agent_failed", "route_stopped"):
                print(f"    ! {ev}: {e.get('error') or e.get('reason')}")
            elif ev == "rca":
                print(f"  rca: {e['root_cause_type']} status={e['status']} "
                      f"conf={e['overall_confidence']:.2f} iterations={e['iterations']}")

    print("\n--- Agent usage ---")
    for agent, n in usage.most_common():
        print(f"  {agent}: {n}")
    print("--- Fallbacks ---")
    for k, n in fallbacks.most_common() or [("none", 0)]:
        print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
