"""Print a step list for every investigation in a flow log.

Usage: python scripts/analyze_flow.py [path-to-flow.jsonl] [--id INVESTIGATION_ID]

For diagrams and an HTML page use `python scripts/investigate.py report`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402
from backend.flow import build_trace, group_by_investigation, read_events  # noqa: E402
from backend.flow.report import to_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=settings.flow_log_path)
    parser.add_argument("--id", help="only show this investigation")
    args = parser.parse_args()

    runs = group_by_investigation(read_events(path=args.path))
    shown = [(run_id, events) for run_id, events in runs.items() if not args.id or run_id == args.id]
    if not shown:
        sys.exit(f"No matching investigations in {args.path}")
    flagged = 0
    for _, events in shown:
        trace = build_trace(events)
        flagged += bool(trace.problems)
        print(to_text(trace) + "\n")
    print(f"{len(shown)} investigation(s), {flagged} with steps that need attention.")


if __name__ == "__main__":
    main()
