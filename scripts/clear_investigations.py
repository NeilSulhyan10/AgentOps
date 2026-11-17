"""Delete every investigation (and its evidence, findings, RCA...) from the configured MongoDB.

  python scripts/clear_investigations.py          show what is there, delete nothing
  python scripts/clear_investigations.py --yes    delete it

Kept on purpose: ProcessedRunDoc (which GitHub runs the monitor already handled; deleting it would
make the monitor re-investigate old runs) and the local flow log in logs/flow.jsonl.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402
from backend.models.mongodb import (  # noqa: E402
    AgentFindingDoc, ConfidenceEntryDoc, EvidenceDoc, IncidentDoc, InvestigationDoc,
    RemediationDoc, RootCauseAnalysisDoc, RoutingDecisionDoc, FlowEventsDoc,
)
from backend.services.mongodb import mongodb  # noqa: E402

COLLECTIONS = [InvestigationDoc, IncidentDoc, EvidenceDoc, AgentFindingDoc, RoutingDecisionDoc,
               ConfidenceEntryDoc, RootCauseAnalysisDoc, RemediationDoc, FlowEventsDoc]


async def main(delete: bool) -> int:
    await mongodb.connect()
    print(f"Database: {settings.mongodb_database}  (host not shown)")
    for doc in COLLECTIONS:
        print(f"  {doc.__name__:<24} {await doc.find_all().count():>6}")
    if not delete:
        print("\nNothing deleted. Re-run with --yes to delete the rows above.")
        return 0
    for doc in COLLECTIONS:
        await doc.find_all().delete()
    print("\nDeleted. Remaining:", {doc.__name__: await doc.find_all().count() for doc in COLLECTIONS})
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="actually delete")
    sys.exit(asyncio.run(main(parser.parse_args().yes)))
