import json
import asyncio
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel

from .base import LLMProvider, LLMRequest, LLMResponse


class MockLLM(LLMProvider):
    def __init__(self, delay: float = 0.1):
        self._delay = delay
        self._call_count = 0
        self._responses: Dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-llm"

    def set_response(self, key: str, response: Any) -> None:
        self._responses[key] = response

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self._call_count += 1
        await asyncio.sleep(self._delay)

        key = self._extract_key(request.prompt)
        if key in self._responses:
            content = self._responses[key]
        else:
            content = self._default_response(request.prompt)

        return LLMResponse(
            content=content if isinstance(content, str) else json.dumps(content),
            tokens_used=len(content) if isinstance(content, str) else len(json.dumps(content)),
            model=self.model_name,
            metadata={"call_count": self._call_count, "key": key}
        )

    async def generate_structured(
        self,
        request: LLMRequest,
        response_model: Type[BaseModel]
    ) -> BaseModel:
        response = await self.generate(request)
        try:
            data = json.loads(response.content)
            return response_model(**data)
        except (json.JSONDecodeError, ValueError):
            return response_model()

    def _extract_key(self, prompt: str) -> str:
        lines = prompt.strip().split('\n')
        for line in lines:
            if line.startswith('TASK:') or line.startswith('ROUTE:') or line.startswith('ANALYZE:'):
                return line.split(':', 1)[1].strip()[:50]
        return "default"

    def _default_response(self, prompt: str) -> str:
        prompt_lower = prompt.lower()

        if "route" in prompt_lower or "router" in prompt_lower:
            return json.dumps({
                "selected_agent": "cicd",
                "reasoning": "Mock routing decision - prioritizing CI/CD agent",
                "confidence": 0.8
            })
        elif "analyze" in prompt_lower or "evidence" in prompt_lower:
            return json.dumps({
                "finding": "Mock analysis finding",
                "hypothesis": "deployment_induced_failure",
                "evidence": ["mock_evidence_1", "mock_evidence_2"],
                "confidence": 0.75,
                "reasoning": "Mock analysis reasoning"
            })
        elif "root cause" in prompt_lower or "rca" in prompt_lower:
            return json.dumps({
                "root_cause": "Mock root cause identified",
                "root_cause_type": "deployment_induced_failure",
                "contributing_factors": ["factor1", "factor2"],
                "confidence": 0.85
            })
        elif "remediation" in prompt_lower:
            return json.dumps({
                "recommendation": "Mock remediation recommendation",
                "steps": ["step1", "step2"],
                "priority": "high"
            })

        return "Mock LLM response"


class DeterministicMockLLM(MockLLM):
    def __init__(self):
        super().__init__(delay=0.0)
        self._routing_rules = {
            "deployment": "cicd",
            "oom": "kubernetes",
            "memory": "kubernetes",
            "exit_code_137": "kubernetes",
            "latency": "observability",
            "error_rate": "observability",
            "5xx": "observability",
            "p99": "observability"
        }

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self._call_count += 1

        if "ROUTE:" in request.prompt:
            return await self._deterministic_route(request.prompt)
        elif "ANALYZE:" in request.prompt:
            return await self._deterministic_analyze(request.prompt)
        elif "RCA:" in request.prompt:
            return await self._deterministic_rca(request.prompt)
        elif "REMEDIATION:" in request.prompt:
            return await self._deterministic_remediation(request.prompt)

        return LLMResponse(
            content="Deterministic mock response",
            tokens_used=10,
            model=self.model_name,
            metadata={"call_count": self._call_count}
        )

    async def _deterministic_route(self, prompt: str) -> LLMResponse:
        prompt_lower = prompt.lower()

        for keyword, agent in self._routing_rules.items():
            if keyword in prompt_lower:
                return LLMResponse(
                    content=json.dumps({
                        "selected_agent": agent,
                        "reasoning": f"Rule-based routing: detected '{keyword}' in evidence",
                        "confidence": 0.9
                    }),
                    tokens_used=50,
                    model=self.model_name,
                    metadata={"call_count": self._call_count, "routing_rule": keyword}
                )

        return LLMResponse(
            content=json.dumps({
                "selected_agent": "cicd",
                "reasoning": "Default to CI/CD agent",
                "confidence": 0.5
            }),
            tokens_used=50,
            model=self.model_name,
            metadata={"call_count": self._call_count}
        )

    async def _deterministic_analyze(self, prompt: str) -> LLMResponse:
        prompt_lower = prompt.lower()

        if "cicd" in prompt_lower or "deployment" in prompt_lower:
            return LLMResponse(
                content=json.dumps({
                    "finding": "Recent deployment detected with configuration change",
                    "hypothesis": "deployment_induced_failure",
                    "evidence": ["deployment_timestamp_match", "config_change_detected"],
                    "confidence": 0.85,
                    "reasoning": "Deployment occurred 2 minutes before incident onset"
                }),
                tokens_used=80,
                model=self.model_name,
                metadata={"call_count": self._call_count, "agent": "cicd"}
            )
        elif "kubernetes" in prompt_lower or "pod" in prompt_lower:
            return LLMResponse(
                content=json.dumps({
                    "finding": "Pod OOMKilled with exit code 137",
                    "hypothesis": "kubernetes_oom",
                    "evidence": ["exit_code_137", "memory_usage_980Mi", "memory_limit_1Gi"],
                    "confidence": 0.92,
                    "reasoning": "Memory usage exceeded limit causing OOM kill"
                }),
                tokens_used=80,
                model=self.model_name,
                metadata={"call_count": self._call_count, "agent": "kubernetes"}
            )
        elif "observability" in prompt_lower or "latency" in prompt_lower:
            return LLMResponse(
                content=json.dumps({
                    "finding": "P99 latency spike detected with error rate increase",
                    "hypothesis": "traffic_incident",
                    "evidence": ["p99_latency_5s", "error_rate_38%", "correlation_id_trace"],
                    "confidence": 0.78,
                    "reasoning": "Traffic spike correlates with latency degradation"
                }),
                tokens_used=80,
                model=self.model_name,
                metadata={"call_count": self._call_count, "agent": "observability"}
            )

        return LLMResponse(
            content=json.dumps({
                "finding": "No specific evidence found",
                "hypothesis": "unknown",
                "evidence": [],
                "confidence": 0.1,
                "reasoning": "Insufficient data for analysis"
            }),
            tokens_used=50,
            model=self.model_name,
            metadata={"call_count": self._call_count}
        )

    async def _deterministic_rca(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            content=json.dumps({
                "root_cause": "Recent deployment reduced memory limit from 1Gi to 512Mi, causing payment-service pods to exceed configured memory limit and terminate with exit code 137",
                "root_cause_type": "deployment_induced_failure",
                "contributing_factors": [
                    "Memory limit reduced in deployment",
                    "Application memory usage exceeded new limit",
                    "No canary deployment to catch issue"
                ],
                "confidence": 0.89
            }),
            tokens_used=100,
            model=self.model_name,
            metadata={"call_count": self._call_count}
        )

    async def _deterministic_remediation(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            content=json.dumps({
                "recommendation": "Restore previous memory limit (1Gi) and redeploy with canary rollout",
                "steps": [
                    "Revert memory limit change in deployment config",
                    "Deploy to canary (10% traffic)",
                    "Monitor memory usage and error rates",
                    "Gradually increase traffic to 100%"
                ],
                "priority": "high",
                "estimated_effort": "low",
                "risk_level": "low"
            }),
            tokens_used=80,
            model=self.model_name,
            metadata={"call_count": self._call_count}
        )