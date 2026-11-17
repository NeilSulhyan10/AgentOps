"""
Rule-based CI/CD specialist.

Reads deployments, code/config/dependency changes and decides what kind of
change is the suspect (first match wins):

    config removed or breaking   value missing/removed, secret, probe, bad_config  -> configuration_error
    dependency touched           dependency bump, or a db/redis/upstream setting   -> dependency_issue
    broken release               failed deployment, or a resource-limit change     -> deployment_induced_failure
    some other change            code/config change that shipped                   -> deployment_induced_failure (weak)
    nothing changed              same image, no changes                            -> unknown ("nothing wrong here")
"""

from typing import Any, Dict, List

from backend.agents.signals import contains, ids, of_type, result
from backend.models import AgentFinding, Evidence, HypothesisType, Incident

_CONFIG_BREAKING = r"missing|removed|unset|\bempty\b|secret|probe|configmap|bad config"
_DEPENDENCY = r"\b(db|database|postgres|mysql|mongo|redis|upstream|dependency)\b"
_RESOURCE_LIMIT = r"memory|cpu|limit|replicas"
_DEPENDENCY_MANIFEST = r"requirements|package(-lock)?\.json|\.lock|go\.(mod|sum)|pom\.xml|gemfile|pyproject"


class CICDAgent:
    AGENT_NAME = "cicd_analyzer"

    def __init__(self):
        self.agent_type = self.AGENT_NAME

    def investigate(self, incident: Incident, existing_evidence: List[Evidence]) -> AgentFinding:
        found = self._analyze_evidence(incident, existing_evidence)
        return AgentFinding(
            investigation_id="", agent_type=self.agent_type, iteration=0,
            hypothesis=found["hypothesis"], finding=found["finding"], evidence=found["evidence"],
            confidence=found["confidence"], reasoning=found["reasoning"],
        )

    def _analyze_evidence(self, incident: Incident, evidence: List[Evidence]) -> Dict[str, Any]:
        deployments = of_type(evidence, "deployment")
        configs = of_type(evidence, "config_change")
        code = of_type(evidence, "code_change")
        dependencies = of_type(evidence, "dependency_change")
        failed_jobs = of_type(evidence, "job_failure")
        if not (deployments or configs or code or dependencies or failed_jobs):
            return result(HypothesisType.UNKNOWN, "No CI/CD evidence found for this incident", [], 0.1,
                          "No deployment or configuration data available")

        failed = [d for d in deployments if str(d.raw_data.get("status", "")).lower() in ("failed", "failure")] + failed_jobs
        new_image = [d for d in deployments if d.raw_data.get("image") != d.raw_data.get("previous_image")]
        all_changes = configs + code + dependencies

        breaking = [c for c in configs if contains(f"{c.raw_data.get('key')} {c.raw_data.get('new_value')}", _CONFIG_BREAKING)]
        if breaking:
            return result(
                HypothesisType.CONFIGURATION_ERROR,
                f"A required setting was removed or broken by the release: {breaking[0].description}",
                ids(breaking + failed), 0.9,
                "; ".join(c.description for c in breaking[:3]),
            )

        app_code = [c for c in code if not contains(c.raw_data.get("file"), _DEPENDENCY_MANIFEST)]
        depends = dependencies + [c for c in configs if contains(f"{c.raw_data.get('key')} {c.raw_data.get('new_value')}", _DEPENDENCY)]
        if depends and not app_code:   # a release that also changed application code is a bigger suspect
            return result(
                HypothesisType.DEPENDENCY_ISSUE,
                f"The release touched a dependency: {depends[0].description}",
                ids(depends), 0.75 if dependencies else 0.7,
                "; ".join(c.description for c in depends[:3]),
            )

        limits = [c for c in configs if contains(c.raw_data.get("key"), _RESOURCE_LIMIT)]
        if failed or limits or app_code:
            suspects = failed + limits + app_code
            why = ("The deployment failed" if failed else "A resource limit was changed in the release" if limits
                   else "The release changed application code")
            return result(
                HypothesisType.DEPLOYMENT_INDUCED_FAILURE,
                f"{why}; the incident starts right after it: {suspects[0].description}",
                ids(suspects + deployments), 0.9 if (failed and app_code) or limits else 0.85,
                "; ".join(s.description for s in suspects[:3]),
            )

        if all_changes or new_image:
            shown = all_changes + new_image
            return result(
                HypothesisType.DEPLOYMENT_INDUCED_FAILURE,
                f"A release with changes shipped just before the incident: {shown[0].description}",
                ids(shown + deployments), 0.6, "; ".join(s.description for s in shown[:3]),
            )

        return result(
            HypothesisType.UNKNOWN,
            "The deployment re-used the same image and changed nothing; CI/CD does not explain the incident",
            ids(deployments), 0.3, "No code, config or dependency change in the CI/CD evidence.",
        )
