"""
Flow reports: one FlowTrace rendered for three audiences.

* ``to_text``     - terminal summary (what ``scripts/investigate.py`` prints)
* ``to_markdown`` - Markdown with Mermaid blocks (renders on GitHub / in VS Code)
* ``to_html``     - one self-contained HTML page (open it in any browser)

The HTML page loads Mermaid from a CDN to draw the diagrams.  Without internet
the diagrams show as Mermaid source text; the verdict and step table still work.
"""

from html import escape
from typing import List

from backend.flow.diagram import app_map, pipeline_map
from backend.flow.trace import ERROR, OK, WARNING, FlowTrace, Step

_ICON = {OK: "✔", WARNING: "⚠", ERROR: "✖"}
_LEGEND = "green = fine · amber = worth a look · red = the fault · grey dashed = not visited"


def headline(trace: FlowTrace) -> str:
    """One sentence saying how the investigation ended."""
    if trace.final_status == "failed":
        failed = next((s for s in trace.steps if s.status == ERROR), None)
        return f"Investigation FAILED at node '{failed.node}'." if failed else "Investigation FAILED."
    if not trace.root_cause_type:
        return f"Investigation is {trace.final_status}; no root cause written yet."
    return f"Root cause: {trace.root_cause_type} (confidence {trace.confidence:.2f}, status {trace.final_status})."


def to_text(trace: FlowTrace) -> str:
    lines = [f"{trace.incident_id or trace.investigation_id}: {trace.title}", f"  {headline(trace)}"]
    for number, step in enumerate(trace.steps, start=1):
        took = f"  [{step.duration_ms} ms]" if step.duration_ms is not None else ""
        lines.append(f"  {_ICON[step.status]} {number:>2}. {step.node:<13} {step.title}{took}")
        if step.status != OK:
            lines.extend(f"         {note}" for note in step.notes)
    count = len(trace.problems)
    lines.append(f"  {count} step(s) need attention." if count else "  No problems in the investigation flow.")
    return "\n".join(lines)


def to_markdown(trace: FlowTrace) -> str:
    out: List[str] = [
        f"# Flow report: {trace.incident_id or trace.investigation_id}",
        "",
        f"**{trace.title}**",
        "",
        f"- Result: {headline(trace)}",
        f"- Decisions made by: `{trace.engine or 'unknown'}`",
        f"- Investigation id: `{trace.investigation_id}`",
    ]
    if trace.fault:
        out.append(f"- Injected fault (demo): `{trace.fault}`")
    out += ["", "## Steps that need attention", ""]
    if trace.problems:
        for step in trace.problems:
            out.append(f"- {_ICON[step.status]} **{step.node}** - {step.title}")
            out.extend(f"  - {note}" for note in step.notes)
    else:
        out.append("None. Every step of the investigation ran cleanly.")
    out += [
        "", "## Where the fault is in the application", "", f"_{_LEGEND}_", "",
        "```mermaid", app_map(trace), "```",
        "", "## How the investigation ran", "",
        "_Thick arrows are the path that was taken._", "",
        "```mermaid", pipeline_map(trace), "```",
        "", "## Step by step", "",
        "| # | | Node | What happened | Details |",
        "|---|---|---|---|---|",
    ]
    for number, step in enumerate(trace.steps, start=1):
        notes = "<br>".join(_cell(note) for note in step.notes)
        out.append(f"| {number} | {_ICON[step.status]} | `{step.node}` | {_cell(step.title)} | {notes} |")
    return "\n".join(out) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_html(trace: FlowTrace) -> str:
    problems = "".join(_problem_html(step) for step in trace.problems) or (
        '<p class="ok-line">✔ Every step of the investigation ran cleanly.</p>'
    )
    rows = "".join(
        f'<tr class="{step.status}"><td>{number}</td><td>{_ICON[step.status]}</td>'
        f"<td><code>{escape(step.node)}</code></td><td>{escape(step.title)}</td>"
        f'<td>{"<br>".join(escape(n) for n in step.notes)}</td>'
        f'<td>{"" if step.duration_ms is None else step.duration_ms}</td></tr>'
        for number, step in enumerate(trace.steps, start=1)
    )
    fault = f"<span>injected fault: <b>{escape(trace.fault)}</b></span>" if trace.fault else ""
    return _PAGE.format(
        incident=escape(trace.incident_id or trace.investigation_id),
        title=escape(trace.title),
        status=trace.worst_status,
        headline=escape(headline(trace)),
        engine=escape(trace.engine or "unknown"),
        investigation_id=escape(trace.investigation_id),
        fault=fault,
        problems=problems,
        legend=_LEGEND,
        app_map=escape(app_map(trace)),
        pipeline_map=escape(pipeline_map(trace)),
        rows=rows,
    )


def _problem_html(step: Step) -> str:
    notes = "".join(f"<li>{escape(note)}</li>" for note in step.notes)
    return (
        f'<div class="problem {step.status}"><b>{_ICON[step.status]} {escape(step.node)}</b>'
        f" - {escape(step.title)}<ul>{notes}</ul></div>"
    )


# Doubled braces are literal braces: this string goes through str.format().
_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flow report: {incident}</title>
<style>
  :root {{ --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --card:#f6f8fa;
           --ok:#1a7f37; --warning:#9a6700; --error:#cf222e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --card:#151b23;
             --ok:#3fb950; --warning:#d29922; --error:#f85149; }}
  }}
  body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,sans-serif; margin:0; padding:24px 16px; }}
  main {{ max-width:1000px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  h2 {{ font-size:17px; margin:32px 0 8px; }}
  .muted, .meta {{ color:var(--muted); font-size:13px; }}
  .meta span {{ margin-right:16px; }}
  .verdict {{ border:1px solid var(--line); border-left:6px solid var(--ok); background:var(--card);
              padding:12px 16px; border-radius:6px; margin:16px 0; font-weight:600; }}
  .verdict.warning {{ border-left-color:var(--warning); }}
  .verdict.error {{ border-left-color:var(--error); }}
  .problem {{ border-left:4px solid var(--warning); background:var(--card); padding:8px 12px; margin:8px 0; border-radius:4px; }}
  .problem.error {{ border-left-color:var(--error); }}
  .problem ul {{ margin:4px 0 0; padding-left:20px; }}
  .ok-line {{ color:var(--ok); }}
  /* Diagrams keep a white card so their colours read the same in light and dark mode. */
  .diagram {{ background:#ffffff; border:1px solid var(--line); border-radius:6px; padding:12px; overflow-x:auto; }}
  .diagram pre {{ margin:0; color:#1f2328; font-size:12px; }}
  .table-wrap {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th, td {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }}
  tr.warning td:nth-child(2) {{ color:var(--warning); }}
  tr.error td:nth-child(2) {{ color:var(--error); }}
  tr.ok td:nth-child(2) {{ color:var(--ok); }}
  tr.error {{ background:color-mix(in srgb, var(--error) 12%, transparent); }}
</style>
</head>
<body>
<main>
  <h1>{incident}</h1>
  <div>{title}</div>
  <div class="verdict {status}">{headline}</div>
  <div class="meta"><span>decisions made by: <b>{engine}</b></span>{fault}<span>investigation {investigation_id}</span></div>

  <h2>Steps that need attention</h2>
  {problems}

  <h2>Where the fault is in the application</h2>
  <p class="muted">{legend}</p>
  <div class="diagram"><pre class="mermaid">{app_map}</pre></div>

  <h2>How the investigation ran</h2>
  <p class="muted">Thick arrows are the path that was taken. {legend}</p>
  <div class="diagram"><pre class="mermaid">{pipeline_map}</pre></div>

  <h2>Step by step</h2>
  <div class="table-wrap">
  <table>
    <thead><tr><th>#</th><th></th><th>Node</th><th>What happened</th><th>Details</th><th>ms</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</main>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "strict" }});
</script>
</body>
</html>
"""
