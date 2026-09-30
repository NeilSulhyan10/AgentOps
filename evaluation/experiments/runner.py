"""
Experiment runner for evaluating adaptive vs fixed workflow investigations.
"""

import json
import asyncio
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from backend.models import Incident, InvestigationState
from backend.orchestrator.graph import build_investigation_graph, create_initial_state
from evaluation.baseline.fixed_workflow import FixedWorkflowInvestigator
from evaluation.metrics.evaluator import (
    EvaluationMetrics,
    ComparisonResult,
    evaluate_investigation,
    compare_workflows,
    compute_overall_score,
)
from backend.tools.data_access import DataLoader


class ExperimentRunner:
    """
    Runs evaluation experiments comparing adaptive vs fixed workflow.
    """
    
    def __init__(
        self,
        data_dir: str = "/home/neil/Documents/Project/agentops/data",
        ground_truth_dir: str = "/home/neil/Documents/Project/agentops/data/ground_truth",
        output_dir: str = "/home/neil/Documents/Project/agentops/evaluation/experiments"
    ):
        self.data_loader = DataLoader(data_dir)
        self.ground_truth_dir = Path(ground_truth_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.adaptive_graph = build_investigation_graph()
        self.fixed_investigator = FixedWorkflowInvestigator()
    
    def load_ground_truth(self, incident_id: str) -> Dict[str, Any]:
        """Load ground truth for an incident."""
        gt_file = self.ground_truth_dir / f"{incident_id}.json"
        if not gt_file.exists():
            raise ValueError(f"Ground truth not found for {incident_id}")
        with open(gt_file) as f:
            return json.load(f)
    
    def load_incident(self, incident_id: str) -> Incident:
        """Load incident data."""
        incident_data = self.data_loader.load_incident_data(incident_id)
        if not incident_data:
            raise ValueError(f"Incident data not found for {incident_id}")
        return Incident(**incident_data)
    
    async def run_adaptive_investigation(
        self, 
        incident: Incident,
        max_iterations: int = 5
    ) -> InvestigationState:
        """Run adaptive investigation."""
        initial_state = create_initial_state(incident, max_iterations=max_iterations)
        result = await self.adaptive_graph.ainvoke({
            "investigation": initial_state,
            "messages": [],
            "current_agent": None,
            "should_continue": True,
            "next_action": ""
        })
        return result["investigation"]
    
    def run_fixed_investigation(self, incident: Incident) -> InvestigationState:
        """Run fixed workflow investigation."""
        return self.fixed_investigator.investigate(incident)
    
    async def run_single_experiment(
        self,
        incident_id: str,
        max_iterations: int = 5
    ) -> ComparisonResult:
        """
        Run a single experiment comparing adaptive vs fixed for one incident.
        """
        # Load incident and ground truth
        incident = self.load_incident(incident_id)
        ground_truth = self.load_ground_truth(incident_id)
        
        # Run adaptive investigation
        print(f"Running adaptive investigation for {incident_id}...")
        start = time.time()
        adaptive_inv = await self.run_adaptive_investigation(incident, max_iterations)
        adaptive_time = time.time() - start
        print(f"  Adaptive completed in {adaptive_time:.2f}s, confidence: {adaptive_inv.overall_confidence:.2%}")
        
        # Run fixed investigation
        print(f"Running fixed workflow investigation for {incident_id}...")
        start = time.time()
        fixed_inv = self.run_fixed_investigation(incident)
        fixed_time = time.time() - start
        print(f"  Fixed completed in {fixed_time:.2f}s, confidence: {fixed_inv.overall_confidence:.2%}")
        
        # Compare
        comparison = compare_workflows(
            incident_id,
            adaptive_inv,
            fixed_inv,
            ground_truth,
            adaptive_time,
            fixed_time
        )
        
        print(f"  Winner: {comparison.winner} (diff: {comparison.score_difference:.3f})")
        
        return comparison
    
    async def run_experiment_suite(
        self,
        incident_ids: List[str],
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        Run experiments for multiple incidents and generate summary report.
        """
        results = []
        summary = {
            "experiment_id": f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "incidents": incident_ids,
            "max_iterations": max_iterations,
            "comparisons": [],
            "summary": {
                "total": 0,
                "adaptive_wins": 0,
                "fixed_wins": 0,
                "ties": 0,
                "avg_adaptive_score": 0.0,
                "avg_fixed_score": 0.0,
                "avg_score_difference": 0.0,
            }
        }
        
        adaptive_scores = []
        fixed_scores = []
        score_diffs = []
        
        for incident_id in incident_ids:
            try:
                comparison = await self.run_single_experiment(incident_id, max_iterations)
                results.append(comparison)
                
                summary["comparisons"].append(comparison.to_dict())
                adaptive_scores.append(comparison.adaptive_metrics.overall_score)
                fixed_scores.append(comparison.fixed_metrics.overall_score)
                score_diffs.append(comparison.score_difference)
                
                summary["summary"]["total"] += 1
                if comparison.winner == "adaptive":
                    summary["summary"]["adaptive_wins"] += 1
                elif comparison.winner == "fixed":
                    summary["summary"]["fixed_wins"] += 1
                else:
                    summary["summary"]["ties"] += 1
                    
            except Exception as e:
                print(f"Error running experiment for {incident_id}: {e}")
                summary["comparisons"].append({
                    "incident_id": incident_id,
                    "error": str(e)
                })
        
        # Compute summary statistics
        if adaptive_scores:
            summary["summary"]["avg_adaptive_score"] = statistics.mean(adaptive_scores)
        if fixed_scores:
            summary["summary"]["avg_fixed_score"] = statistics.mean(fixed_scores)
        if score_diffs:
            summary["summary"]["avg_score_difference"] = statistics.mean(score_diffs)
        
        # Save results
        self.save_results(summary)
        
        return summary
    
    def save_results(self, results: Dict[str, Any]) -> Path:
        """Save experiment results to JSON file."""
        filename = f"{results['experiment_id']}.json"
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {filepath}")
        return filepath
    
    def load_results(self, experiment_id: str) -> Dict[str, Any]:
        """Load experiment results from JSON file."""
        filepath = self.output_dir / f"{experiment_id}.json"
        with open(filepath) as f:
            return json.load(f)
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate human-readable report from results."""
        lines = [
            "=" * 60,
            "EVALUATION EXPERIMENT REPORT",
            "=" * 60,
            f"Experiment ID: {results['experiment_id']}",
            f"Timestamp: {results['timestamp']}",
            f"Incidents: {', '.join(results['incidents'])}",
            f"Max Iterations: {results['max_iterations']}",
            "",
            "SUMMARY",
            "-" * 60,
            f"Total Experiments: {results['summary']['total']}",
            f"Adaptive Wins: {results['summary']['adaptive_wins']}",
            f"Fixed Wins: {results['summary']['fixed_wins']}",
            f"Ties: {results['summary']['ties']}",
            f"Avg Adaptive Score: {results['summary']['avg_adaptive_score']:.3f}",
            f"Avg Fixed Score: {results['summary']['avg_fixed_score']:.3f}",
            f"Avg Score Difference: {results['summary']['avg_score_difference']:.3f}",
            "",
            "DETAILED RESULTS",
            "-" * 60,
        ]
        
        for comp in results["comparisons"]:
            if "error" in comp:
                lines.append(f"  {comp['incident_id']}: ERROR - {comp['error']}")
                continue
            
            adaptive = comp["adaptive_metrics"]
            fixed = comp["fixed_metrics"]
            lines.append(f"  {comp['incident_id']}:")
            lines.append(f"    Winner: {comp['winner']} (diff: {comp['score_difference']:.3f})")
            lines.append(f"    Adaptive: score={adaptive['overall_score']:.3f}, "
                        f"rca_type={adaptive['root_cause_type_correct']}, "
                        f"conf={adaptive['confidence_vs_accuracy']:.2f}, "
                        f"iter={adaptive['iterations']}, agents={adaptive['agents_invoked']}")
            lines.append(f"    Fixed:    score={fixed['overall_score']:.3f}, "
                        f"rca_type={fixed['root_cause_type_correct']}, "
                        f"conf={fixed['confidence_vs_accuracy']:.2f}, "
                        f"iter={fixed['iterations']}, agents={fixed['agents_invoked']}")
            lines.append("")
        
        return "\n".join(lines)


import statistics


async def run_evaluation(
    incident_ids: List[str] = None,
    data_dir: str = "/home/neil/Documents/Project/agentops/data",
    ground_truth_dir: str = "/home/neil/Documents/Project/agentops/data/ground_truth",
    output_dir: str = "/home/neil/Documents/Project/agentops/evaluation/experiments",
    max_iterations: int = 5
) -> Dict[str, Any]:
    """
    Main entry point for running evaluation experiments.
    """
    if incident_ids is None:
        # Auto-discover incidents from ground truth
        gt_path = Path(ground_truth_dir)
        incident_ids = [f.stem for f in gt_path.glob("*.json")]
    
    print(f"Running evaluation on incidents: {incident_ids}")
    
    runner = ExperimentRunner(data_dir, ground_truth_dir, output_dir)
    results = await runner.run_experiment_suite(incident_ids, max_iterations)
    
    # Print report
    report = runner.generate_report(results)
    print("\n" + report)
    
    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())