"""Run an investigation on this machine and see where things went wrong.

No server, no MongoDB, no API key: the graph runs in this process and, unless
you pass --llm, every decision is made by the rule-based implementations.

  python scripts/investigate.py list                       scenarios you can run
  python scripts/investigate.py faults                     faults you can inject into AgentOps
  python scripts/investigate.py run shoplite-S2            investigate one scenario
  python scripts/investigate.py run all                    investigate every scenario
  python scripts/investigate.py run shoplite-S2 --fault agent_crash
  python scripts/investigate.py run shoplite-S2 --llm      use the LLM configured in .env
  python scripts/investigate.py showcase                   rebuild docs/showcase (ready-made examples)
  python scripts/investigate.py report --last              report for the latest run in logs/flow.jsonl
  python scripts/investigate.py report <investigation_id>  (works for runs made by the server too)

Each run prints a step list and writes <out>/<name>.html and <out>/<name>.md
(default out: reports/).  Open the .html in a browser for the diagrams.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.faults import FAULTS  # noqa: E402
from backend.flow import FlowTrace, build_trace, group_by_investigation, read_events  # noqa: E402
from backend.flow.report import headline, to_html, to_markdown, to_text  # noqa: E402
from backend.llm import reset_llm_provider  # noqa: E402
from backend.orchestrator import create_initial_state, run_investigation  # noqa: E402
from backend.services.scenarios import list_scenarios, load_scenario_incident  # noqa: E402

# The scenario used to demonstrate faults inside AgentOps (a ShopLite pod being OOM-killed).
FAULT_DEMO_SCENARIO = "shoplite-S2"
# The scenario that needs a specialist nobody wrote: Redis cache eviction (see backend/runtime/spawner.py).
SPAWN_DEMO_SCENARIO = "incident-008"


def expected_root_cause(scenario_id: str) -> Optional[str]:
    """Ground truth is read here, by the developer tool only - never by the agents."""
    truth_file = Path(settings.data_dir) / "ground_truth" / f"{scenario_id}.json"
    if not truth_file.exists():
        return None
    return json.loads(truth_file.read_text(encoding="utf-8")).get("root_cause_type")


async def investigate(scenario_id: str, fault: str = "") -> FlowTrace:
    """Run one scenario through the graph and return its flow trace."""
    settings.fault_injection = fault
    reset_llm_provider()
    incident = load_scenario_incident(scenario_id)
    state = await run_investigation(create_initial_state(incident, settings.max_iterations))
    return build_trace(read_events(state.investigation_id))


def write_reports(trace: FlowTrace, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.md").write_text(to_markdown(trace), encoding="utf-8")
    html_path = out_dir / f"{name}.html"
    html_path.write_text(to_html(trace), encoding="utf-8")
    return html_path


def verdict(trace: FlowTrace, scenario_id: str) -> str:
    expected = expected_root_cause(scenario_id)
    if not expected or trace.final_status == "failed":
        return ""
    got = trace.root_cause_type or "unknown"
    return f"MATCH (expected {expected})" if got == expected else f"MISMATCH (expected {expected}, got {got})"


async def cmd_run(args) -> int:
    scenario_ids = [s["scenario_id"] for s in list_scenarios()] if args.scenario == "all" else [args.scenario]
    for scenario_id in scenario_ids:
        try:
            trace = await investigate(scenario_id, args.fault or "")
        except KeyError:
            sys.exit(f"Unknown scenario '{scenario_id}'. Try: python scripts/investigate.py list")
        name = f"{scenario_id}--{args.fault}" if args.fault else scenario_id
        html_path = write_reports(trace, Path(args.out), name)
        print(to_text(trace))
        if verdict(trace, scenario_id):
            print(f"  Ground truth: {verdict(trace, scenario_id)}")
        print(f"  Report: {html_path}\n")
    return 0


async def cmd_showcase(args) -> int:
    """Regenerate the ready-made examples: every ShopLite scenario, then every injected fault."""
    out_dir = Path(args.out)
    rows: List[str] = []

    rows += ["## Faults in the application (ShopLite)", "",
             "AgentOps works correctly here; the report shows which layer of ShopLite is broken.", "",
             "| Scenario | Incident | Result | Ground truth | Report |", "|---|---|---|---|---|"]
    for scenario in list_scenarios():
        scenario_id = scenario["scenario_id"]
        if not scenario_id.startswith("shoplite-"):
            continue
        trace = await investigate(scenario_id)
        write_reports(trace, out_dir, scenario_id)
        rows.append(f"| `{scenario_id}` | {scenario['title']} | {headline(trace)} | {verdict(trace, scenario_id)} "
                    f"| [{scenario_id}.md]({scenario_id}.md) |")
        print(f"{scenario_id:<28} {headline(trace)}")

    rows += ["", "## Dynamic agent spawning", "",
             "No standard specialist covers a Redis cache. The `spawn_agent` step creates `cache_analyzer` while the investigation runs.", "",
             "| Scenario | Incident | Result | Ground truth | Report |", "|---|---|---|---|---|"]
    trace = await investigate(SPAWN_DEMO_SCENARIO)
    write_reports(trace, out_dir, SPAWN_DEMO_SCENARIO)
    rows.append(f"| `{SPAWN_DEMO_SCENARIO}` | {trace.title} | {headline(trace)} | {verdict(trace, SPAWN_DEMO_SCENARIO)} "
                f"| [{SPAWN_DEMO_SCENARIO}.md]({SPAWN_DEMO_SCENARIO}.md) |")
    print(f"{SPAWN_DEMO_SCENARIO:<28} {headline(trace)}")

    rows += ["", "## Faults inside AgentOps (injected)", "",
             f"Same incident every time (`{FAULT_DEMO_SCENARIO}`), with one part of AgentOps broken on purpose. "
             "The report shows which node of the investigation misbehaved.", "",
             "| Fault | What is broken | Result | Steps flagged | Report |", "|---|---|---|---|---|"]
    for fault, description in FAULTS.items():
        trace = await investigate(FAULT_DEMO_SCENARIO, fault)
        name = f"{FAULT_DEMO_SCENARIO}--{fault}"
        write_reports(trace, out_dir, name)
        flagged = ", ".join(dict.fromkeys(s.node for s in trace.problems)) or "none"
        rows.append(f"| `{fault}` | {description} | {headline(trace)} | {flagged} | [{name}.md]({name}.md) |")
        print(f"{name:<28} {headline(trace)}")

    index = ["# Showcase: ready-made flow reports", "",
             "Generated by `python scripts/investigate.py showcase` (rule-based mode, no LLM, no network).",
             "Open a `.md` here on GitHub, or the matching `.html` in a browser.", ""] + rows
    (out_dir / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"\nIndex: {out_dir / 'README.md'}")
    return 0


def cmd_report(args) -> int:
    runs = group_by_investigation(read_events(path=args.log))
    if not runs:
        sys.exit(f"No flow events in {args.log or settings.flow_log_path}. Run an investigation first.")
    if args.last:
        investigation_id = max(runs, key=lambda run_id: runs[run_id][-1]["ts"])
    elif args.investigation_id in runs:
        investigation_id = args.investigation_id
    else:
        sys.exit(f"Investigation '{args.investigation_id}' is not in the flow log. Use --last for the latest run.")
    trace = build_trace(runs[investigation_id])
    html_path = write_reports(trace, Path(args.out), trace.incident_id or investigation_id)
    print(to_text(trace))
    print(f"  Report: {html_path}")
    return 0


def cmd_list(_args) -> int:
    for s in list_scenarios():
        expected = expected_root_cause(s["scenario_id"]) or "-"
        print(f"{s['scenario_id']:<14} {s['severity']:<9} {expected:<28} {s['title']}")
    return 0


def cmd_faults(_args) -> int:
    for name, description in FAULTS.items():
        print(f"{name:<26} {description}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="scenarios you can run")
    commands.add_parser("faults", help="faults you can inject")

    run = commands.add_parser("run", help="investigate a scenario")
    run.add_argument("scenario", help="scenario id, or 'all'")
    run.add_argument("--fault", choices=sorted(FAULTS), help="break one part of AgentOps on purpose")
    run.add_argument("--llm", action="store_true", help="use the LLM provider from .env instead of rules")
    run.add_argument("--out", default="reports", help="directory for the reports (default: reports)")

    showcase = commands.add_parser("showcase", help="rebuild the ready-made examples")
    showcase.add_argument("--out", default="docs/showcase")

    report = commands.add_parser("report", help="report for a run already in the flow log")
    report.add_argument("investigation_id", nargs="?")
    report.add_argument("--last", action="store_true", help="the most recent investigation")
    report.add_argument("--log", help="flow log to read (default: FLOW_LOG_PATH)")
    report.add_argument("--out", default="reports")

    args = parser.parse_args()
    logging.basicConfig(level=logging.ERROR)   # the flow report is the output; keep library logs quiet
    if args.command == "report" and not (args.last or args.investigation_id):
        parser.error("report needs an investigation id or --last")
    if getattr(args, "fault", None) and getattr(args, "llm", False):
        parser.error("--fault replaces the LLM, so it cannot be combined with --llm")

    # Local runs are rule-based unless the developer explicitly asks for the configured LLM.
    if not getattr(args, "llm", False):
        settings.llm_provider = "rules"

    if args.command == "run":
        return asyncio.run(cmd_run(args))
    if args.command == "showcase":
        return asyncio.run(cmd_showcase(args))
    handlers = {"list": cmd_list, "faults": cmd_faults, "report": cmd_report}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
