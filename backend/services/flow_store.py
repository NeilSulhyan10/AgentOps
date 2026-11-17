"""
Keep each investigation's flow events in MongoDB.

While a run is going, events are in the local flow log (logs/flow.jsonl), which is what
the Flow tab reads.  When it finishes they are copied to the database, so the Flow tab
also works for runs made by another process (the CLI, another container) and survives
the log file being lost.  ``load_flow_events`` tries the file first, then the database.
"""

import logging
from typing import Dict, List

from backend.flow.log import read_events
from backend.models.mongodb import FlowEventsDoc

logger = logging.getLogger(__name__)


async def save_flow(investigation_id: str) -> bool:
    """Copy one run's events from the flow log to the database. Never raises."""
    try:
        events = read_events(investigation_id)
        if not events:
            return False
        doc = await FlowEventsDoc.find_one({"investigation_id": investigation_id})
        if doc:
            doc.events = events
            await doc.save()
        else:
            await FlowEventsDoc(investigation_id=investigation_id, events=events).insert()
        return True
    except Exception as exc:
        logger.warning("Could not save flow events for %s: %s", investigation_id, exc)
        return False


async def load_flow_events(investigation_id: str) -> List[dict]:
    events = read_events(investigation_id)
    if events:
        return events
    try:
        doc = await FlowEventsDoc.find_one({"investigation_id": investigation_id})
    except Exception as exc:       # database unavailable: "no flow data" is better than a 500
        logger.warning("Could not read flow events for %s: %s", investigation_id, exc)
        return []
    return list(doc.events) if doc else []


async def backfill() -> Dict[str, int]:
    """Save events for every investigation in the database that the flow log knows and the database does not."""
    from backend.models.mongodb import InvestigationDoc

    have = {d.investigation_id for d in await FlowEventsDoc.find_all().to_list()}
    result = {"saved": 0, "no_events": 0}
    for inv in await InvestigationDoc.find_all().to_list():
        if inv.investigation_id in have:
            continue
        result["saved" if await save_flow(inv.investigation_id) else "no_events"] += 1
    return result
