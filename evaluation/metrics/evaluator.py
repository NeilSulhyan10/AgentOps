"""
Evaluation metrics for comparing adaptive vs fixed workflow investigations.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import statistics

from backend.models import (
    InvestigationState,
    RootCauseAnalysis,
    RemediationRecommendation,
    HypothesisType,
    AgentType,
    Evidence,
)


@dataclass
class EvaluationMetrics:
    """Metrics for a single investigation run."""
    
    # Investigation metadata
    investigation_id: str
    incident_id: str
    workflow_type: str  # "adaptive" or "fixed"
    
    # RCA Accuracy Metrics
    root_cause_type_correct: bool = False
    root_cause_similarity: float = 0.0  # Semantic similarity to ground truth
    contributing_factors_recall: float = 0.0
    contributing_factors_precision: float = 0.0
    
    # Evidence Groundedness
    evidence_coverage: float = 0.0  # Fraction of ground truth evidence found
    evidence_precision: float = 0.0  # Fraction of found evidence that's relevant
    agents_consulted_correct: bool = False
    
    # Confidence Calibration
    confidence_vs_accuracy: float = 0.0  # How well confidence predicts correctness
    overconfidence: float = 0.0  # Confidence when wrong
    underconfidence: float = 0.0  # Low confidence when right
    
    # Efficiency Metrics
    iterations: int = 0
    agents_invoked: int = 0
    total_evidence_collected: int = 0
    investigation_time_seconds: float = 0.0
    
    # MTTR (Mean Time to Resolution) proxy
    time_to_confidence_threshold: Optional[float] = None
    confidence_threshold: float = 0.75
    
    # Remediation Quality
    remediation_steps_match: float = 0.0
    remediation_priority_match: bool = False
    
    # Overall Score
    overall_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "incident_id": self.incident_id,
            "workflow_type": self.workflow_type,
            "root_cause_type_correct": self.root_cause_type_correct,
            "root_cause_similarity": self.root_cause_similarity,
            "contributing_factors_recall": self.contributing_factors_recall,
            "contributing_factors_precision": self.contributing_factors_precision,
            "evidence_coverage": self.evidence_coverage,
            "evidence_precision": self.evidence_precision,
            "agents_consulted_correct": self.agents_consulted_correct,
            "confidence_vs_accuracy": self.confidence_vs_accuracy,
            "overconfidence": self.overconfidence,
            "underconfidence": self.underconfidence,
            "iterations": self.iterations,
            "agents_invoked": self.agents_invoked,
            "total_evidence_collected": self.total_evidence_collected,
            "investigation_time_seconds": self.investigation_time_seconds,
            "time_to_confidence_threshold": self.time_to_confidence_threshold,
            "confidence_threshold": self.confidence_threshold,
            "remediation_steps_match": self.remediation_steps_match,
            "remediation_priority_match": self.remediation_priority_match,
            "overall_score": self.overall_score,
        }


@dataclass
class ComparisonResult:
    """Comparison between adaptive and fixed workflow."""
    incident_id: str
    adaptive_metrics: EvaluationMetrics
    fixed_metrics: EvaluationMetrics
    winner: str  # "adaptive", "fixed", or "tie"
    score_difference: float
    statistical_significance: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "adaptive_metrics": self.adaptive_metrics.to_dict(),
            "fixed_metrics": self.fixed_metrics.to_dict(),
            "winner": self.winner,
            "score_difference": self.score_difference,
            "statistical_significance": self.statistical_significance,
        }


def calculate_rca_accuracy(
    predicted: RootCauseAnalysis,
    ground_truth: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate RCA accuracy metrics by comparing predicted vs ground truth.
    """
    metrics = {
        "root_cause_type_correct": 0.0,
        "root_cause_similarity": 0.0,
        "contributing_factors_recall": 0.0,
        "contributing_factors_precision": 0.0,
    }
    
    # Root cause type accuracy
    gt_type = ground_truth.get("root_cause_type", "")
    pred_type = predicted.root_cause_type.value if hasattr(predicted.root_cause_type, 'value') else str(predicted.root_cause_type)
    metrics["root_cause_type_correct"] = 1.0 if gt_type == pred_type else 0.0
    
    # Contributing factors recall/precision
    gt_factors = set(ground_truth.get("contributing_factors", []))
    pred_factors = set(predicted.contributing_factors)
    
    if gt_factors:
        metrics["contributing_factors_recall"] = len(gt_factors & pred_factors) / len(gt_factors)
    if pred_factors:
        metrics["contributing_factors_precision"] = len(gt_factors & pred_factors) / len(pred_factors)
    
    # Root cause text similarity (simple word overlap)
    gt_cause = ground_truth.get("root_cause", "").lower()
    pred_cause = predicted.root_cause.lower()
    gt_words = set(gt_cause.split())
    pred_words = set(pred_cause.split())
    if gt_words:
        metrics["root_cause_similarity"] = len(gt_words & pred_words) / len(gt_words)
    
    return metrics


def calculate_evidence_metrics(
    investigation: InvestigationState,
    ground_truth: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate evidence groundedness metrics.
    """
    metrics = {
        "evidence_coverage": 0.0,
        "evidence_precision": 0.0,
        "agents_consulted_correct": 0.0,
    }
    
    # Evidence coverage: fraction of ground truth evidence found
    gt_evidence = set(ground_truth.get("evidence", []))
    collected_evidence = set(e.description for e in investigation.evidence)
    
    if gt_evidence:
        # Simple keyword matching
        matched = 0
        for gt_ev in gt_evidence:
            gt_keywords = set(gt_ev.lower().split())
            for coll_ev in collected_evidence:
                coll_keywords = set(coll_ev.lower().split())
                if gt_keywords & coll_keywords:
                    matched += 1
                    break
        metrics["evidence_coverage"] = matched / len(gt_evidence)
    
    # Agents consulted
    gt_agents = set(ground_truth.get("agents_consulted", []))
    invoked_agents = set()
    for a in investigation.agents_invoked:
        if hasattr(a, 'value'):
            invoked_agents.add(a.value)
        else:
            invoked_agents.add(str(a))
    metrics["agents_consulted_correct"] = 1.0 if gt_agents == invoked_agents else 0.0
    
    return metrics


def calculate_confidence_calibration(
    investigation: InvestigationState,
    rca_correct: bool
) -> Dict[str, float]:
    """
    Calculate confidence calibration metrics.
    """
    metrics = {
        "confidence_vs_accuracy": 0.0,
        "overconfidence": 0.0,
        "underconfidence": 0.0,
    }
    
    confidence = investigation.overall_confidence
    
    # Confidence vs accuracy correlation (simplified)
    # If correct and high confidence -> good calibration
    # If wrong and high confidence -> overconfidence
    # If correct and low confidence -> underconfidence
    if rca_correct:
        metrics["confidence_vs_accuracy"] = confidence
        if confidence < 0.5:
            metrics["underconfidence"] = 1.0 - confidence
    else:
        metrics["confidence_vs_accuracy"] = 1.0 - confidence
        if confidence > 0.5:
            metrics["overconfidence"] = confidence
    
    return metrics


def calculate_remediation_quality(
    predicted: RemediationRecommendation,
    ground_truth: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate remediation quality metrics.
    """
    metrics = {
        "remediation_steps_match": 0.0,
        "remediation_priority_match": 0.0,
    }
    
    gt_remediation = ground_truth.get("remediation", {})
    gt_steps = set(gt_remediation.get("steps", []))
    pred_steps = set(predicted.steps)
    
    if gt_steps:
        metrics["remediation_steps_match"] = len(gt_steps & pred_steps) / len(gt_steps)
    
    gt_priority = gt_remediation.get("priority", "").lower()
    pred_priority = predicted.priority.lower()
    metrics["remediation_priority_match"] = 1.0 if gt_priority == pred_priority else 0.0
    
    return metrics


def compute_overall_score(metrics: EvaluationMetrics) -> float:
    """
    Compute weighted overall score from individual metrics.
    """
    weights = {
        "root_cause_type_correct": 0.25,
        "root_cause_similarity": 0.15,
        "contributing_factors_recall": 0.10,
        "contributing_factors_precision": 0.10,
        "evidence_coverage": 0.10,
        "evidence_precision": 0.05,
        "agents_consulted_correct": 0.05,
        "confidence_vs_accuracy": 0.10,
        "remediation_steps_match": 0.05,
        "remediation_priority_match": 0.05,
    }
    
    score = 0.0
    total_weight = 0.0
    
    for key, weight in weights.items():
        value = getattr(metrics, key, 0.0)
        if value is not None:
            score += value * weight
            total_weight += weight
    
    return score / total_weight if total_weight > 0 else 0.0


def evaluate_investigation(
    investigation: InvestigationState,
    ground_truth: Dict[str, Any],
    workflow_type: str,
    investigation_time: float = 0.0
) -> EvaluationMetrics:
    """
    Evaluate a single investigation against ground truth.
    """
    # RCA accuracy
    rca_metrics = calculate_rca_accuracy(investigation.root_cause, ground_truth)
    
    # Evidence metrics
    evidence_metrics = calculate_evidence_metrics(investigation, ground_truth)
    
    # Confidence calibration
    confidence_metrics = calculate_confidence_calibration(
        investigation, 
        rca_metrics["root_cause_type_correct"]
    )
    
    # Remediation quality
    remediation_metrics = calculate_remediation_quality(
        investigation.remediation, ground_truth
    )
    
    # Build metrics object
    metrics = EvaluationMetrics(
        investigation_id=investigation.investigation_id,
        incident_id=investigation.incident_id,
        workflow_type=workflow_type,
        root_cause_type_correct=rca_metrics["root_cause_type_correct"],
        root_cause_similarity=rca_metrics["root_cause_similarity"],
        contributing_factors_recall=rca_metrics["contributing_factors_recall"],
        contributing_factors_precision=rca_metrics["contributing_factors_precision"],
        evidence_coverage=evidence_metrics["evidence_coverage"],
        evidence_precision=evidence_metrics["evidence_precision"],
        agents_consulted_correct=evidence_metrics["agents_consulted_correct"],
        confidence_vs_accuracy=confidence_metrics["confidence_vs_accuracy"],
        overconfidence=confidence_metrics["overconfidence"],
        underconfidence=confidence_metrics["underconfidence"],
        iterations=investigation.iteration_count,
        agents_invoked=len(investigation.agents_invoked),
        total_evidence_collected=len(investigation.evidence),
        investigation_time_seconds=investigation_time,
        time_to_confidence_threshold=None,  # Would need timeline analysis
        remediation_steps_match=remediation_metrics["remediation_steps_match"],
        remediation_priority_match=remediation_metrics["remediation_priority_match"],
        overall_score=0.0,  # Will be computed
    )
    
    metrics.overall_score = compute_overall_score(metrics)
    
    return metrics


def compare_workflows(
    incident_id: str,
    adaptive_investigation: InvestigationState,
    fixed_investigation: InvestigationState,
    ground_truth: Dict[str, Any],
    adaptive_time: float = 0.0,
    fixed_time: float = 0.0
) -> ComparisonResult:
    """
    Compare adaptive vs fixed workflow for a single incident.
    """
    adaptive_metrics = evaluate_investigation(
        adaptive_investigation, ground_truth, "adaptive", adaptive_time
    )
    fixed_metrics = evaluate_investigation(
        fixed_investigation, ground_truth, "fixed", fixed_time
    )
    
    score_diff = adaptive_metrics.overall_score - fixed_metrics.overall_score
    
    if score_diff > 0.05:
        winner = "adaptive"
    elif score_diff < -0.05:
        winner = "fixed"
    else:
        winner = "tie"
    
    return ComparisonResult(
        incident_id=incident_id,
        adaptive_metrics=adaptive_metrics,
        fixed_metrics=fixed_metrics,
        winner=winner,
        score_difference=score_diff,
    )