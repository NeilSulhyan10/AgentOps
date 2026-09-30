// AgentOps MongoDB Initialization
// Creates collections with indexes for the investigation platform

db = db.getSiblingDB('agentops');

// Incidents collection
db.createCollection('incidents');
db.incidents.createIndex({ "incident_id": 1 }, { unique: true });
db.incidents.createIndex({ "created_at": -1 });
db.incidents.createIndex({ "status": 1 });
db.incidents.createIndex({ "severity": 1 });

// Investigations collection
db.createCollection('investigations');
db.investigations.createIndex({ "investigation_id": 1 }, { unique: true });
db.investigations.createIndex({ "incident_id": 1 });
db.investigations.createIndex({ "status": 1 });
db.investigations.createIndex({ "created_at": -1 });

// Agent findings collection
db.createCollection('agent_findings');
db.agent_findings.createIndex({ "investigation_id": 1 });
db.agent_findings.createIndex({ "agent_type": 1 });
db.agent_findings.createIndex({ "created_at": -1 });

// Evidence collection
db.createCollection('evidence');
db.evidence.createIndex({ "investigation_id": 1 });
db.evidence.createIndex({ "agent_type": 1 });
db.evidence.createIndex({ "evidence_type": 1 });

// Routing decisions collection
db.createCollection('routing_decisions');
db.routing_decisions.createIndex({ "investigation_id": 1 });
db.routing_decisions.createIndex({ "iteration": 1 });
db.routing_decisions.createIndex({ "selected_agent": 1 });

// Confidence history collection
db.createCollection('confidence_history');
db.confidence_history.createIndex({ "investigation_id": 1 });
db.confidence_history.createIndex({ "iteration": 1 });

// Root cause analyses collection
db.createCollection('root_cause_analyses');
db.root_cause_analyses.createIndex({ "investigation_id": 1 }, { unique: true });
db.root_cause_analyses.createIndex({ "root_cause_type": 1 });
db.root_cause_analyses.createIndex({ "created_at": -1 });

// Remediation recommendations collection
db.createCollection('remediations');
db.remediations.createIndex({ "investigation_id": 1 }, { unique: true });
db.remediations.createIndex({ "status": 1 });

print('AgentOps database initialized with collections and indexes');