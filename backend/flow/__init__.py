"""
Flow inspection: record what an investigation did, then show where it went wrong.

    log.py      write / read the flow log (logs/flow.jsonl)
    trace.py    events of one investigation -> ordered steps tagged ok / warning / error
    layers.py   which layer of the investigated app holds the root cause
    diagram.py  Mermaid diagrams (app map + pipeline map)
    report.py   terminal, Markdown and HTML reports
"""

from backend.flow.log import log_flow, read_events
from backend.flow.trace import FlowTrace, Step, build_trace, group_by_investigation

__all__ = ["log_flow", "read_events", "FlowTrace", "Step", "build_trace", "group_by_investigation"]
