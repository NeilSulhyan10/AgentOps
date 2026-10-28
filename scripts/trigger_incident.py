"""Trigger replayable incident scenarios against a running AgentOps backend.

Usage:
  python scripts/trigger_incident.py list
  python scripts/trigger_incident.py run incident-003 [--wait]
  python scripts/trigger_incident.py run all --wait
Options: --base-url http://localhost:8000
With --wait the script polls until each investigation finishes and compares the
result with data/ground_truth/<scenario>.json (read locally, never by the backend).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GROUND_TRUTH = Path(__file__).resolve().parent.parent / "data" / "ground_truth"
DONE = {"completed", "failed", "max_iterations_reached", "insufficient_evidence"}


def call(base, method, path):
    req = urllib.request.Request(f"{base}/api{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.URLError as exc:
        sys.exit(f"Cannot reach {base}: {exc}")


def wait(base, inv_id, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        inv = call(base, "GET", f"/investigations/{inv_id}")
        if inv["investigation_status"] in DONE:
            return inv
        time.sleep(2)
    sys.exit(f"Timed out waiting for {inv_id}")


def report(scenario, inv):
    rca = inv.get("root_cause") or {}
    truth_file = GROUND_TRUTH / f"{scenario}.json"
    truth = json.loads(truth_file.read_text()) if truth_file.exists() else {}
    predicted, expected = rca.get("root_cause_type"), truth.get("root_cause_type")
    verdict = "n/a" if not expected else ("MATCH" if predicted == expected else "MISMATCH")
    print(f"\n{scenario}: {inv['investigation_status']}")
    print(f"  agents:     {' -> '.join(inv['agents_invoked'])}")
    print(f"  confidence: {inv['overall_confidence']:.2f}  iterations: {inv['iteration_count']}")
    for r in inv.get("critic_reviews", []):
        print(f"  critic #{r['round']}: {r['verdict']} ({r['confidence']:.2f})"
              + (f" -> {r['suggested_agent']}" if r.get("suggested_agent") else ""))
        for c in r["concerns"]:
            print(f"      concern: {c}")
    print(f"  root cause: {predicted}  (expected {expected}) {verdict}")
    print(f"  {(rca.get('root_cause') or '').splitlines()[0] if rca.get('root_cause') else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "run"])
    ap.add_argument("scenario", nargs="?", help="scenario id or 'all'")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--base-url", default="http://localhost:8000")
    args = ap.parse_args()

    scenarios = call(args.base_url, "GET", "/scenarios")["scenarios"]
    if args.action == "list":
        for s in scenarios:
            print(f"{s['scenario_id']:<14} {s['severity']:<9} {s['service_name']:<18} {s['title']}")
        return

    if not args.scenario:
        sys.exit("run needs a scenario id or 'all'")
    ids = [s["scenario_id"] for s in scenarios] if args.scenario == "all" else [args.scenario]
    started = {}
    for sid in ids:
        resp = call(args.base_url, "POST", f"/scenarios/{sid}/trigger")
        started[sid] = resp["investigation_id"]
        print(f"started {sid}: investigation {resp['investigation_id']}")
    if args.wait:
        for sid, inv_id in started.items():
            report(sid, wait(args.base_url, inv_id, args.timeout))


if __name__ == "__main__":
    main()
