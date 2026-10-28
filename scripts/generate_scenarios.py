"""Generate replayable incident scenarios (incident, cicd, kubernetes, observability, ground truth).

Usage: python scripts/generate_scenarios.py [--out data] [--only incident-003]

Each scenario writes matching evidence for every layer plus a ground-truth file that
only the evaluator reads.  Existing incident-001/002 are hand-written and left alone.
Output is deterministic, so regenerating produces identical files.
"""

import argparse
import json
from pathlib import Path


def event(reason, message, ts, kind="Warning"):
    return {"type": kind, "reason": reason, "message": message, "timestamp": ts}


def pod(name, ns, status, ready, restarts, exit_code, mem, mem_limit, cpu, started, events):
    return {
        "name": name, "namespace": ns, "status": status, "ready": ready,
        "restart_count": restarts, "exit_code": exit_code,
        "memory_usage": mem, "memory_limit": mem_limit,
        "cpu_usage": cpu, "cpu_limit": "1000m", "started_at": started, "events": events,
    }


def log(ts, level, message, **extra):
    return {"timestamp": ts, "level": level, "message": message, **extra}


def trace(trace_id, op, duration, status, error, ts, code, service):
    return {
        "trace_id": trace_id, "span_id": trace_id[::-1], "parent_span_id": None,
        "service": service, "operation": op, "duration": duration, "status": status,
        "error": error, "timestamp": ts,
        "tags": {"http.status_code": code, "http.method": "POST", "http.url": op.split(" ", 1)[-1]},
    }


def latency(p50, p95, p99, ts, svc):
    return {"p50": p50, "p95": p95, "p99": p99, "unit": "ms", "timestamp": ts, "service": svc}


def errors(rate, count, total, ts, svc, codes):
    return {"rate": rate, "count": count, "total_requests": total, "timestamp": ts, "service": svc, "error_codes": codes}


SCENARIOS = {}

# A: tests fail because of an incompatible dependency version ---------------------------
SCENARIOS["incident-003"] = {
    "incident": {
        "title": "Auth service release blocked: tests failing after dependency upgrade",
        "description": "auth-service deployment failed in CI at 2024-02-02T09:41:00Z. Integration tests error out on import after a library upgrade. Production is still running the previous release. Service: auth-service, namespace: production.",
        "severity": "medium", "source": "ci-pipeline", "service_name": "auth-service", "namespace": "production",
        "started_at": "2024-02-02T09:41:00Z", "detected_at": "2024-02-02T09:42:00Z",
        "metadata": {"pipeline": "build-and-test", "failed_job": "integration-tests"},
        "tags": ["auth", "ci", "tests", "dependency"],
    },
    "cicd": {
        "deployments": [{"deployment_id": "deploy-301", "timestamp": "2024-02-02T09:41:00Z", "service": "auth-service",
                         "namespace": "production", "image": "auth-service:v4.2.0", "previous_image": "auth-service:v4.1.3",
                         "strategy": "rolling", "replicas": 3, "status": "failed"}],
        "code_changes": [{"file": "requirements.txt", "description": "Bumped PyJWT to the 3.x line", "author": "dev-team",
                          "commit": "a1b2c3d", "timestamp": "2024-02-02T09:20:00Z"}],
        "config_changes": [],
        "dependency_changes": [{"name": "pyjwt", "old_version": "2.8.0", "new_version": "3.0.0", "timestamp": "2024-02-02T09:20:00Z"}],
    },
    "kubernetes": {"pods": [
        pod(f"auth-service-6c9d8f7b4-{s}", "production", "Running", True, 0, 0, "140Mi", "512Mi", "180m",
            "2024-02-01T16:00:00Z", [event("Started", "Started container auth-service", "2024-02-01T16:00:05Z", "Normal")])
        for s in ("a1x9k", "b2y8m", "c3z7n")]},
    "observability": {
        "latency": latency(30, 60, 95, "2024-02-02T09:42:00Z", "auth-service"),
        "error_rate": errors(0.1, 4, 4000, "2024-02-02T09:42:00Z", "auth-service", {"500": 4}),
        "logs": [
            log("2024-02-02T09:40:12Z", "ERROR", "ImportError: cannot import name 'PyJWT' from 'jwt' during integration-tests", service="auth-service"),
            log("2024-02-02T09:40:13Z", "ERROR", "Test session failed: 38 tests errored at collection (incompatible jwt library version)", service="auth-service"),
        ],
        "stack_traces": [{"timestamp": "2024-02-02T09:40:12Z", "error": "ImportError: cannot import name 'PyJWT' from 'jwt'",
                          "service": "auth-service", "trace": "ImportError: cannot import name 'PyJWT' from 'jwt'\n\tat tests/conftest.py:12\n\tat auth/tokens.py:4"}],
    },
    "truth": {
        "root_cause": "Upgrading pyjwt from 2.8.0 to 3.0.0 removed the PyJWT import used by auth/tokens.py, so the integration tests failed at import time and the release was blocked. Production is unaffected.",
        "root_cause_type": "dependency_issue",
        "contributing_factors": ["pyjwt major version bump 2.8.0 -> 3.0.0", "Code still imports the removed PyJWT name", "Dependency pinned by major version without compatibility check"],
        "evidence": ["Deployment status failed", "Dependency change pyjwt 2.8.0 -> 3.0.0", "ImportError: cannot import name PyJWT", "Production pods healthy"],
        "agents_consulted": ["cicd_analyzer", "dependency_analyzer"],
        "expected_confidence": 0.85,
        "remediation": {"recommendation": "Pin pyjwt below 3.0 or migrate auth/tokens.py to the 3.x API", "steps": ["Pin pyjwt<3 in requirements.txt", "Re-run the pipeline", "Plan the 3.x migration separately"], "priority": "medium", "estimated_effort": "low", "risk_level": "low"},
    },
}

# B: pipeline succeeds, new container image crashes on startup --------------------------
SCENARIOS["incident-004"] = {
    "incident": {
        "title": "Checkout service crash-looping after successful deployment",
        "description": "checkout-service pods in CrashLoopBackOff since the deployment at 2024-02-05T11:10:00Z. The pipeline reported success. Error rate is rising as old replicas are replaced. Service: checkout-service, namespace: production.",
        "severity": "critical", "source": "prometheus-alert", "service_name": "checkout-service", "namespace": "production",
        "started_at": "2024-02-05T11:12:00Z", "detected_at": "2024-02-05T11:13:00Z",
        "metadata": {"alert_name": "CheckoutCrashLoop", "restarts": 14},
        "tags": ["checkout", "crashloop", "deployment"],
    },
    "cicd": {
        "deployments": [{"deployment_id": "deploy-401", "timestamp": "2024-02-05T11:10:00Z", "service": "checkout-service",
                         "namespace": "production", "image": "checkout-service:v1.9.0", "previous_image": "checkout-service:v1.8.4",
                         "strategy": "rolling", "replicas": 3, "status": "success"}],
        "code_changes": [{"file": "src/checkout/settings.py", "description": "Require PAYMENT_GATEWAY_URL at startup", "author": "dev-team",
                          "commit": "b7c8d9e", "timestamp": "2024-02-05T10:30:00Z"}],
        "config_changes": [],
        "dependency_changes": [],
    },
    "kubernetes": {"pods": [
        pod("checkout-service-5f7c9d8b6-k4t2p", "production", "CrashLoopBackOff", False, 14, 1, "60Mi", "512Mi", "40m",
            "2024-02-05T11:10:30Z", [
                event("Pulled", "Successfully pulled image checkout-service:v1.9.0", "2024-02-05T11:10:25Z", "Normal"),
                event("Started", "Started container checkout-service", "2024-02-05T11:10:30Z", "Normal"),
                event("BackOff", "Back-off restarting failed container checkout-service", "2024-02-05T11:11:30Z"),
            ]),
        pod("checkout-service-5f7c9d8b6-m8q1w", "production", "CrashLoopBackOff", False, 13, 1, "58Mi", "512Mi", "35m",
            "2024-02-05T11:10:40Z", [event("BackOff", "Back-off restarting failed container checkout-service", "2024-02-05T11:11:40Z")]),
    ]},
    "observability": {
        "latency": latency(40, 120, 400, "2024-02-05T11:13:00Z", "checkout-service"),
        "error_rate": errors(61.0, 2440, 4000, "2024-02-05T11:13:00Z", "checkout-service", {"502": 1600, "503": 840}),
        "logs": [
            log("2024-02-05T11:10:31Z", "ERROR", "Startup failed: required environment variable PAYMENT_GATEWAY_URL is not set", service="checkout-service", pod="checkout-service-5f7c9d8b6-k4t2p"),
            log("2024-02-05T11:10:31Z", "ERROR", "Process exited with code 1 during initialisation", service="checkout-service"),
        ],
        "stack_traces": [{"timestamp": "2024-02-05T11:10:31Z", "error": "RuntimeError: PAYMENT_GATEWAY_URL is not set", "service": "checkout-service",
                          "pod": "checkout-service-5f7c9d8b6-k4t2p", "trace": "RuntimeError: PAYMENT_GATEWAY_URL is not set\n\tat src/checkout/settings.py:21\n\tat src/checkout/main.py:8"}],
    },
    "truth": {
        "root_cause": "The v1.9.0 image requires PAYMENT_GATEWAY_URL at startup (new code in settings.py) but the deployment never supplies it, so every new pod exits with code 1 and crash-loops. The pipeline passed because tests do not run the real startup path.",
        "root_cause_type": "deployment_induced_failure",
        "contributing_factors": ["New required environment variable introduced in code", "Deployment manifest not updated with the variable", "Pipeline has no startup smoke test"],
        "evidence": ["Deployment succeeded at 11:10", "Pod CrashLoopBackOff restarts 14 exit code 1", "PAYMENT_GATEWAY_URL is not set", "Code change in settings.py"],
        "agents_consulted": ["cicd_analyzer", "kubernetes_analyzer", "observability_analyzer"],
        "expected_confidence": 0.88,
        "remediation": {"recommendation": "Roll back to v1.8.4 or add PAYMENT_GATEWAY_URL to the deployment", "steps": ["kubectl rollout undo deployment/checkout-service", "Add PAYMENT_GATEWAY_URL to the manifest", "Add a startup smoke test to the pipeline"], "priority": "high", "estimated_effort": "low", "risk_level": "low"},
    },
}

# C: deployment succeeds, app cannot reach its database ------------------------------------
SCENARIOS["incident-005"] = {
    "incident": {
        "title": "Orders API failing: cannot connect to database",
        "description": "orders-api returns 500 on most requests since 2024-02-09T15:02:00Z. Application logs show connection refused to the database. A deployment completed two hours earlier without issues. Service: orders-api, namespace: production.",
        "severity": "critical", "source": "prometheus-alert", "service_name": "orders-api", "namespace": "production",
        "started_at": "2024-02-09T15:02:00Z", "detected_at": "2024-02-09T15:03:00Z",
        "metadata": {"alert_name": "OrdersApiHighErrorRate", "error_rate": 72},
        "tags": ["orders", "database", "5xx"],
    },
    "cicd": {
        "deployments": [{"deployment_id": "deploy-501", "timestamp": "2024-02-09T13:00:00Z", "service": "orders-api",
                         "namespace": "production", "image": "orders-api:v3.0.2", "previous_image": "orders-api:v3.0.1",
                         "strategy": "rolling", "replicas": 4, "status": "success"}],
        "code_changes": [{"file": "src/orders/pricing.py", "description": "Rounded totals to two decimals", "author": "dev-team",
                          "commit": "c4d5e6f", "timestamp": "2024-02-09T12:20:00Z"}],
        "config_changes": [],
        "dependency_changes": [],
    },
    "kubernetes": {"pods": [
        pod(f"orders-api-7b8c6d5f9-{s}", "production", "Running", True, 0, 0, "300Mi", "1Gi", "210m",
            "2024-02-09T13:00:40Z", [event("Started", "Started container orders-api", "2024-02-09T13:00:40Z", "Normal")])
        for s in ("d4e5f", "g6h7j", "k8l9m", "n1p2q")]},
    "observability": {
        "latency": latency(60, 5000, 30000, "2024-02-09T15:03:00Z", "orders-api"),
        "error_rate": errors(72.0, 2880, 4000, "2024-02-09T15:03:00Z", "orders-api", {"500": 2880}),
        "logs": [
            log("2024-02-09T15:02:03Z", "ERROR", "Could not connect to database host db-primary.internal:5432: connection refused", service="orders-api"),
            log("2024-02-09T15:02:09Z", "ERROR", "Database connection pool exhausted after repeated connection refused errors", service="orders-api"),
            log("2024-02-09T15:01:40Z", "WARN", "db-primary.internal failover started: primary became unreachable", service="db-proxy"),
        ],
        "stack_traces": [{"timestamp": "2024-02-09T15:02:03Z", "error": "psycopg2.OperationalError: connection refused", "service": "orders-api",
                          "trace": "psycopg2.OperationalError: could not connect to server: Connection refused\n\tat db/pool.py:55\n\tat orders/repository.py:31"}],
        "traces": [
            trace("c5d6e7f8a9b0", "POST /api/v1/orders", 30000, "error", "db_connection_refused", "2024-02-09T15:02:10Z", 500, "orders-api"),
            trace("d6e7f8a9b0c1", "POST /api/v1/orders", 29800, "error", "db_connection_refused", "2024-02-09T15:02:20Z", 500, "orders-api"),
        ],
    },
    "truth": {
        "root_cause": "The primary database became unreachable during a failover at 15:01, so orders-api could not open connections and exhausted its pool. The earlier deployment is unrelated and the pods themselves are healthy.",
        "root_cause_type": "dependency_issue",
        "contributing_factors": ["Database primary failover at 15:01", "Connection refused to db-primary.internal:5432", "Connection pool exhausted with no fast-fail", "Deployment two hours earlier is a red herring"],
        "evidence": ["Connection refused to database host", "Database failover started", "Pods running with zero restarts", "Deployment succeeded at 13:00"],
        "agents_consulted": ["observability_analyzer", "dependency_analyzer"],
        "expected_confidence": 0.87,
        "remediation": {"recommendation": "Restore database connectivity and make the application reconnect after failover", "steps": ["Confirm the new database primary is serving", "Point db-primary.internal at the new primary", "Restart or recycle connection pools", "Add retry with backoff and a circuit breaker"], "priority": "high", "estimated_effort": "medium", "risk_level": "low"},
    },
}

# D: application slow because the container is running out of memory -------------------
SCENARIOS["incident-006"] = {
    "incident": {
        "title": "Search service latency high: memory pressure",
        "description": "search-service p99 latency rose from 200ms to 4.5s since 2024-02-12T08:30:00Z. Pods are using almost all of their memory limit but have not been killed yet. No recent deployments. Service: search-service, namespace: production.",
        "severity": "high", "source": "prometheus-alert", "service_name": "search-service", "namespace": "production",
        "started_at": "2024-02-12T08:30:00Z", "detected_at": "2024-02-12T08:35:00Z",
        "metadata": {"alert_name": "SearchLatencyHigh", "p99_ms": 4500},
        "tags": ["search", "latency", "memory"],
    },
    "cicd": {"deployments": [], "code_changes": [], "config_changes": [], "dependency_changes": []},
    "kubernetes": {"pods": [
        pod("search-service-6d5f7c8b9-r1s2t", "production", "Running", True, 1, 0, "1002Mi", "1Gi", "980m",
            "2024-02-12T02:10:00Z", [event("Warning", "Container search-service memory usage at 98% of limit", "2024-02-12T08:28:00Z")]),
        pod("search-service-6d5f7c8b9-u3v4w", "production", "Running", True, 0, 0, "996Mi", "1Gi", "960m",
            "2024-02-12T02:10:05Z", [event("Warning", "Container search-service memory usage at 97% of limit", "2024-02-12T08:29:00Z")]),
    ]},
    "observability": {
        "latency": latency(380, 2800, 4500, "2024-02-12T08:35:00Z", "search-service"),
        "error_rate": errors(2.1, 84, 4000, "2024-02-12T08:35:00Z", "search-service", {"504": 84}),
        "logs": [
            log("2024-02-12T08:20:00Z", "WARN", "GC pause 1800ms: heap at 97% after full collection", service="search-service"),
            log("2024-02-12T08:31:00Z", "WARN", "Index cache growing without eviction: 910Mi resident", service="search-service"),
        ],
    },
    "truth": {
        "root_cause": "search-service's in-memory index cache grows without eviction until the container reaches about 98% of its 1Gi limit. Constant garbage collection then stalls requests, which shows up as high latency before any OOM kill.",
        "root_cause_type": "kubernetes_oom",
        "contributing_factors": ["Memory usage 1002Mi / 1Gi limit", "Cache without eviction", "Long GC pauses", "No recent deployment or traffic change"],
        "evidence": ["Memory usage 1002Mi / 1Gi", "GC pause 1800ms heap at 97%", "Index cache growing without eviction", "No deployments in window"],
        "agents_consulted": ["kubernetes_analyzer", "observability_analyzer"],
        "expected_confidence": 0.82,
        "remediation": {"recommendation": "Bound the index cache and raise the memory limit", "steps": ["Add eviction to the index cache", "Raise memory limit to 2Gi as a stop-gap", "Alert on memory above 85% of limit"], "priority": "high", "estimated_effort": "medium", "risk_level": "low"},
    },
}

# E: deployment introduces a config error that fails health checks ----------------------
SCENARIOS["incident-007"] = {
    "incident": {
        "title": "Inventory service pods not ready after deployment: probes failing",
        "description": "After the deployment at 2024-02-14T10:00:00Z, new inventory-service pods never become ready. The readiness probe fails with 404 and the rollout is stuck. Service: inventory-service, namespace: production.",
        "severity": "high", "source": "prometheus-alert", "service_name": "inventory-service", "namespace": "production",
        "started_at": "2024-02-14T10:02:00Z", "detected_at": "2024-02-14T10:04:00Z",
        "metadata": {"alert_name": "RolloutStuck", "unavailable_replicas": 3},
        "tags": ["inventory", "readiness", "deployment", "config"],
    },
    "cicd": {
        "deployments": [{"deployment_id": "deploy-701", "timestamp": "2024-02-14T10:00:00Z", "service": "inventory-service",
                         "namespace": "production", "image": "inventory-service:v2.1.0", "previous_image": "inventory-service:v2.0.9",
                         "strategy": "rolling", "replicas": 3, "status": "success"}],
        "code_changes": [],
        "config_changes": [{"key": "readinessProbe.httpGet.path", "old_value": "/healthz", "new_value": "/health/ready",
                            "timestamp": "2024-02-14T09:55:00Z", "changed_by": "devops-team"}],
        "dependency_changes": [],
    },
    "kubernetes": {"pods": [
        pod(f"inventory-service-8c7d6e5f4-{s}", "production", "Running", False, 0, 0, "210Mi", "512Mi", "120m",
            "2024-02-14T10:00:30Z", [
                event("Started", "Started container inventory-service", "2024-02-14T10:00:30Z", "Normal"),
                event("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 404", "2024-02-14T10:01:00Z"),
                event("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 404", "2024-02-14T10:01:10Z"),
            ])
        for s in ("p1a2b", "q3c4d", "r5e6f")]},
    "observability": {
        "latency": latency(25, 40, 60, "2024-02-14T10:04:00Z", "inventory-service"),
        "error_rate": errors(0.4, 16, 4000, "2024-02-14T10:04:00Z", "inventory-service", {"503": 16}),
        "logs": [
            log("2024-02-14T10:01:00Z", "WARN", "GET /health/ready 404 not found (route is /healthz)", service="inventory-service"),
            log("2024-02-14T10:01:05Z", "INFO", "Application started and serving requests on :8080", service="inventory-service"),
        ],
    },
    "truth": {
        "root_cause": "The deployment changed the readiness probe path from /healthz to /health/ready, but the application only serves /healthz. Kubernetes keeps marking the new pods unready, so the rollout never completes.",
        "root_cause_type": "configuration_error",
        "contributing_factors": ["Probe path changed to /health/ready", "Application serves /healthz only", "Probe returns 404", "Application itself starts normally"],
        "evidence": ["Config change readinessProbe path", "Readiness probe failed statuscode 404", "Application started and serving requests", "Pods running but not ready"],
        "agents_consulted": ["config_analyzer", "kubernetes_analyzer", "cicd_analyzer"],
        "expected_confidence": 0.9,
        "remediation": {"recommendation": "Revert the readiness probe path to /healthz", "steps": ["Revert readinessProbe.httpGet.path to /healthz", "Re-apply the deployment", "Add a manifest lint that checks probe paths exist"], "priority": "high", "estimated_effort": "low", "risk_level": "low"},
    },
}


def write(out: Path, folder: str, name: str, data: dict) -> None:
    path = out / folder / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--only", help="a single scenario id")
    args = ap.parse_args()
    out = Path(args.out)
    for sid, sc in SCENARIOS.items():
        if args.only and sid != args.only:
            continue
        write(out, "incidents", sid, {"incident_id": sid, "status": "open", **sc["incident"]})
        write(out, "cicd", sid, sc["cicd"])
        write(out, "kubernetes", sid, sc["kubernetes"])
        write(out, "observability", sid, sc["observability"])
        write(out, "ground_truth", sid, {"incident_id": sid, **sc["truth"]})
        print(f"wrote {sid}: {sc['incident']['title']}")


if __name__ == "__main__":
    main()
