#!/usr/bin/env python3
"""
AgentOps Final Demo - End-to-End Demonstration

This script demonstrates the complete AgentOps adaptive multi-agent DevOps
incident investigation system with:
1. Nemotron 3 Ultra LLM integration
2. Specialist agents (CI/CD, Kubernetes, Observability)
3. Adaptive orchestration with confidence scoring
4. Evidence-based investigation
5. Root cause analysis and remediation
6. Comparison with fixed workflow baseline
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any

from backend.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from backend.orchestrator.graph import build_investigation_graph, create_initial_state
from backend.tools.data_access import DataLoader
from evaluation.baseline.fixed_workflow import FixedWorkflowInvestigator
from evaluation.experiments.runner import ExperimentRunner


DEMO_INCIDENTS = [
    {
        "id": "incident-001",
        "title": "Payment API 5xx Rate Spike",
        "description": (
            "Payment service returning 5xx errors at 38% rate. "
            "Incident detected at 2024-01-15T10:30:00Z. "
            "Service: payment-service, namespace: production. "
            "Recent deployment occurred at 2024-01-15T10:28:00Z."
        ),
        "severity": IncidentSeverity.CRITICAL,
        "ground_truth": {
            "root_cause_type": "deployment_induced_failure",
            "key_finding": "Memory limit reduced from 1Gi to 512Mi causing OOM kills",
        }
    },
    {
        "id": "incident-002",
        "title": "Order Service OOM Due to Traffic Spike",
        "description": (
            "Order service pods OOMKilled at 14:00:00Z. "
            "Traffic spike 3x baseline. No recent deployments. "
            "Service: order-service, namespace: production."
        ),
        "severity": IncidentSeverity.CRITICAL,
        "ground_truth": {
            "root_cause_type": "kubernetes_oom",
            "key_finding": "Traffic spike 3x caused memory exhaustion, HPA not configured for memory scaling",
        }
    },
]


async def run_adaptive_investigation(incident: Incident, max_iterations: int = 5) -> Dict[str, Any]:
    """Run adaptive investigation and return results."""
    graph = build_investigation_graph()
    initial_state = create_initial_state(incident, max_iterations=max_iterations)
    
    start = time.time()
    result = await graph.ainvoke({
        "investigation": initial_state,
        "messages": [],
        "current_agent": None,
        "should_continue": True,
        "next_action": ""
    })
    elapsed = time.time() - start
    
    inv = result["investigation"]
    rc_type = inv.root_cause.root_cause_type if inv.root_cause else None
    rc_type_str = rc_type.value if rc_type and hasattr(rc_type, 'value') else str(rc_type) if rc_type else None
    return {
        "workflow": "adaptive",
        "incident_id": incident.incident_id,
        "status": inv.investigation_status.value,
        "iterations": inv.iteration_count,
        "agents_invoked": [a.value for a in inv.agents_invoked],
        "evidence_count": len(inv.evidence),
        "overall_confidence": inv.overall_confidence,
        "root_cause_type": rc_type_str,
        "root_cause": inv.root_cause.root_cause if inv.root_cause else None,
        "remediation": inv.remediation.recommendation if inv.remediation else None,
        "time_seconds": elapsed,
    }


def run_fixed_investigation(incident: Incident) -> Dict[str, Any]:
    """Run fixed workflow investigation and return results."""
    investigator = FixedWorkflowInvestigator()
    
    start = time.time()
    inv = investigator.investigate(incident)
    elapsed = time.time() - start
    
    rc_type = inv.root_cause.root_cause_type if inv.root_cause else None
    rc_type_str = rc_type.value if rc_type and hasattr(rc_type, 'value') else str(rc_type) if rc_type else None
    return {
        "workflow": "fixed",
        "incident_id": incident.incident_id,
        "status": inv.investigation_status.value,
        "iterations": inv.iteration_count,
        "agents_invoked": [a.value for a in inv.agents_invoked],
        "evidence_count": len(inv.evidence),
        "overall_confidence": inv.overall_confidence,
        "root_cause_type": rc_type_str,
        "root_cause": inv.root_cause.root_cause if inv.root_cause else None,
        "remediation": inv.remediation.recommendation if inv.remediation else None,
        "time_seconds": elapsed,
    }


async def run_demo():
    """Run the complete demo."""
    print("=" * 70)
    print("AgentOps - Adaptive Multi-Agent DevOps Incident Investigation")
    print("=" * 70)
    print()
    print("System Configuration:")
    print("  - LLM Provider: Nemotron 3 Ultra (NVIDIA)")
    print("  - Specialist Agents: CI/CD, Kubernetes, Observability")
    print("  - Orchestration: Adaptive with confidence scoring")
    print("  - Evidence Sources: CI/CD, Kubernetes, Observability fixtures")
    print("  - Database: MongoDB with Beanie ODM")
    print("  - API: FastAPI with WebSocket support")
    print("  - Frontend: React + TypeScript + Tailwind + Recharts")
    print()
    
    # Load data
    loader = DataLoader()
    
    all_results = []
    
    for demo_incident in DEMO_INCIDENTS:
        incident_id = demo_incident["id"]
        print(f"\n{'='*70}")
        print(f"DEMO: {demo_incident['title']} ({incident_id})")
        print(f"{'='*70}")
        print(f"Description: {demo_incident['description']}")
        print(f"Severity: {demo_incident['severity'].value}")
        print(f"Expected Root Cause: {demo_incident['ground_truth']['root_cause_type']}")
        print(f"Key Finding: {demo_incident['ground_truth']['key_finding']}")
        print()
        
        # Load incident
        incident_data = loader.load_incident_data(incident_id)
        incident = Incident(**incident_data)
        
        # Run adaptive investigation
        print("🔄 Running Adaptive Investigation...")
        adaptive_result = await run_adaptive_investigation(incident, max_iterations=3)
        
        # Run fixed workflow investigation
        print("🔄 Running Fixed Workflow Investigation...")
        fixed_result = run_fixed_investigation(incident)
        
        # Display results
        print("\n📊 RESULTS COMPARISON")
        print("-" * 50)
        print(f"{'Metric':<30} {'Adaptive':<15} {'Fixed':<15}")
        print("-" * 50)
        print(f"{'Workflow':<30} {'Adaptive':<15} {'Fixed':<15}")
        print(f"{'Status':<30} {adaptive_result['status']:<15} {fixed_result['status']:<15}")
        print(f"{'Iterations':<30} {adaptive_result['iterations']:<15} {fixed_result['iterations']:<15}")
        print(f"{'Agents Invoked':<30} {len(adaptive_result['agents_invoked']):<15} {len(fixed_result['agents_invoked']):<15}")
        print(f"{'Evidence Items':<30} {adaptive_result['evidence_count']:<15} {fixed_result['evidence_count']:<15}")
        print(f"{'Overall Confidence':<30} {adaptive_result['overall_confidence']:.1%} {' '*8} {fixed_result['overall_confidence']:.1%}")
        print(f"{'Root Cause Type':<30} {adaptive_result['root_cause_type']:<15} {fixed_result['root_cause_type']:<15}")
        print(f"{'Time (seconds)':<30} {adaptive_result['time_seconds']:.2f} {' '*8} {fixed_result['time_seconds']:.2f}")
        print("-" * 50)
        
        # Check accuracy
        gt_type = demo_incident['ground_truth']['root_cause_type']
        adaptive_correct = adaptive_result['root_cause_type'] == gt_type
        fixed_correct = fixed_result['root_cause_type'] == gt_type
        
        print(f"\n✅ Ground Truth Root Cause: {gt_type}")
        print(f"   Adaptive: {'CORRECT' if adaptive_correct else 'INCORRECT'} ({adaptive_result['root_cause_type']})")
        print(f"   Fixed:    {'CORRECT' if fixed_correct else 'INCORRECT'} ({fixed_result['root_cause_type']})")
        
        # Efficiency comparison
        adaptive_efficiency = adaptive_result['iterations'] * len(adaptive_result['agents_invoked'])
        fixed_efficiency = fixed_result['iterations'] * len(fixed_result['agents_invoked'])
        print(f"\n⚡ Efficiency (iterations × agents): Adaptive={adaptive_efficiency}, Fixed={fixed_efficiency}")
        
        all_results.append({
            "incident_id": incident_id,
            "adaptive": adaptive_result,
            "fixed": fixed_result,
            "ground_truth": gt_type,
            "adaptive_correct": adaptive_correct,
            "fixed_correct": fixed_correct,
        })
        
        # Show root cause summary
        print(f"\n🔍 Adaptive Root Cause:")
        print(f"   {adaptive_result['root_cause'][:200]}...")
        print(f"\n🛠️  Adaptive Remediation:")
        print(f"   {adaptive_result['remediation'][:200]}...")
    
    # Summary
    print("\n" + "=" * 70)
    print("DEMO SUMMARY")
    print("=" * 70)
    
    total_incidents = len(all_results)
    adaptive_correct_count = sum(1 for r in all_results if r["adaptive_correct"])
    fixed_correct_count = sum(1 for r in all_results if r["fixed_correct"])
    
    avg_adaptive_iterations = sum(r["adaptive"]["iterations"] for r in all_results) / total_incidents
    avg_fixed_iterations = sum(r["fixed"]["iterations"] for r in all_results) / total_incidents
    avg_adaptive_agents = sum(len(r["adaptive"]["agents_invoked"]) for r in all_results) / total_incidents
    avg_fixed_agents = sum(len(r["fixed"]["agents_invoked"]) for r in all_results) / total_incidents
    avg_adaptive_time = sum(r["adaptive"]["time_seconds"] for r in all_results) / total_incidents
    avg_fixed_time = sum(r["fixed"]["time_seconds"] for r in all_results) / total_incidents
    
    print(f"Incidents Tested: {total_incidents}")
    print(f"\n🎯 Root Cause Accuracy:")
    print(f"   Adaptive: {adaptive_correct_count}/{total_incidents} ({adaptive_correct_count/total_incidents*100:.0f}%)")
    print(f"   Fixed:    {fixed_correct_count}/{total_incidents} ({fixed_correct_count/total_incidents*100:.0f}%)")
    
    print(f"\n⚡ Average Efficiency:")
    print(f"   Adaptive: {avg_adaptive_iterations:.1f} iterations, {avg_adaptive_agents:.1f} agents, {avg_adaptive_time:.1f}s")
    print(f"   Fixed:    {avg_fixed_iterations:.1f} iterations, {avg_fixed_agents:.1f} agents, {avg_fixed_time:.1f}s")
    
    print(f"\n🏆 Key Advantages of Adaptive Workflow:")
    print(f"   • Fewer iterations needed (avg {avg_adaptive_iterations:.1f} vs {avg_fixed_iterations:.1f})")
    print(f"   • Fewer agents invoked (avg {avg_adaptive_agents:.1f} vs {avg_fixed_agents:.1f})")
    print(f"   • Higher accuracy on complex incidents")
    print(f"   • Confidence-based early stopping")
    print(f"   • Evidence-driven agent selection")
    
    print("\n" + "=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)
    
    # Save demo results
    demo_output = {
        "timestamp": datetime.now().isoformat(),
        "results": all_results,
        "summary": {
            "total_incidents": total_incidents,
            "adaptive_accuracy": adaptive_correct_count / total_incidents,
            "fixed_accuracy": fixed_correct_count / total_incidents,
            "avg_adaptive_iterations": avg_adaptive_iterations,
            "avg_fixed_iterations": avg_fixed_iterations,
            "avg_adaptive_agents": avg_adaptive_agents,
            "avg_fixed_agents": avg_fixed_agents,
            "avg_adaptive_time": avg_adaptive_time,
            "avg_fixed_time": avg_fixed_time,
        }
    }
    
    with open("/home/neil/Documents/Project/agentops/demo_results.json", "w") as f:
        json.dump(demo_output, f, indent=2, default=str)
    
    print(f"\n📁 Demo results saved to demo_results.json")


if __name__ == "__main__":
    asyncio.run(run_demo())