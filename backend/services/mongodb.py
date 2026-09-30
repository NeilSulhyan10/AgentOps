from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from backend.config import settings
from backend.models.mongodb import (
    IncidentDoc, InvestigationDoc, EvidenceDoc, AgentFindingDoc,
    RoutingDecisionDoc, ConfidenceEntryDoc, RootCauseAnalysisDoc, RemediationDoc
)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database = None

    async def connect(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.database = self.client[settings.mongodb_database]
        
        await init_beanie(
            database=self.database,
            document_models=[
                IncidentDoc,
                InvestigationDoc,
                EvidenceDoc,
                AgentFindingDoc,
                RoutingDecisionDoc,
                ConfidenceEntryDoc,
                RootCauseAnalysisDoc,
                RemediationDoc,
            ]
        )

    async def close(self):
        if self.client:
            self.client.close()


mongodb = MongoDB()