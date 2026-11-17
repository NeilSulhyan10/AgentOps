"""
Live ShopLite lab: real evidence from a really running, really broken application.

The scenarios in ``data/`` are written by hand.  This lab produces evidence the way
production would, so the investigator is tested on data nobody wrote for it:

    supervisor   starts ShopLite as a real process and behaves like a kubelet:
                 restarts it when it exits (with a restart count), kills it when its
                 memory exceeds the limit (exit 137, "OOMKilled"), and probes /health
                 for readiness
    prober       sends real HTTP traffic and records status and latency of every request
    logs         ShopLite's own JSON log lines, read from the process output
    deploy diff  what changed compared with a healthy deployment (the FAULT variable,
                 the memory limit, the required secret): what a CI system would report

Nothing in the incident text or the evidence names the fault.  The investigator
has to work it out from symptoms.  Linux only (reads /proc for memory).

    ShopLite checkout:  SHOPLITE_DIR (default ../ShopLite)
"""

import asyncio
import json
import os
import re
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.config import REPO_ROOT
from backend.models import Evidence, Incident
from backend.tools.data_access import cicd_evidence_from_data, kubernetes_evidence_from_data, observability_evidence_from_data

SHOPLITE_DIR = Path(os.getenv("SHOPLITE_DIR", REPO_ROOT.parent / "ShopLite"))
SOURCE = "live_shoplite"

# What each fault should be diagnosed as (the lab knows because it injected it).
EXPECTED = {
    "none": "unknown",
    "oom": "kubernetes_oom",
    "latency": "traffic_incident",
    "db_down": "dependency_issue",
    "bad_config": "configuration_error",
    "crash": "application_error",       # held out: no fixture scenario uses this fault
}
HELD_OUT = {"crash"}

BASELINE = {"FAULT": "none", "resources.limits.memory": "256Mi", "REQUIRED_SECRET": "present"}
MAX_RESTARTS = 3
WINDOW_S = {"oom": 28, "latency": 22}       # others settle quickly
DEFAULT_WINDOW_S = 9


@dataclass
class LabResult:
    fault: str
    expected_root_cause: str
    incident: Incident
    evidence: List[Evidence]
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _Probe:
    route: str
    status: int           # 0 = no answer
    latency_ms: float
    at: float


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rss_mib(pid: int) -> Optional[float]:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Supervisor:
    """Runs ShopLite and behaves like a kubelet for one pod."""

    def __init__(self, fault: str, limit_mib: int, port: int):
        self.fault, self.limit_mib, self.port = fault, limit_mib, port
        self.logs: List[dict] = []
        self.raw: List[str] = []
        self.restarts = 0
        self.last_exit: Optional[int] = None
        self.last_reason: Optional[str] = None
        self.events: List[dict] = []
        self.peak_rss = 0.0
        self.started_at = time.time()
        self.ever_ready = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.Task] = None
        self._stop = False

    def _env(self) -> Dict[str, str]:
        env = {**os.environ, "FAULT": self.fault, "MEMORY_LIMIT_HINT": str(self.limit_mib),
               "GIT_SHA": "sha-live", "IMAGE_TAG": "live", "PYTHONPATH": str(SHOPLITE_DIR), "PYTHONUNBUFFERED": "1"}
        env.pop("REQUIRED_SECRET", None)           # bad_config means the secret was not deployed
        return env

    async def _spawn(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(self.port), "--log-level", "warning",
            cwd=str(SHOPLITE_DIR), env=self._env(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        self._reader = asyncio.create_task(self._read(self._proc))

    async def _read(self, proc) -> None:
        assert proc.stdout
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if not line:
                continue
            self.raw.append(line)
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    record.setdefault("ts", time.time())
                    self.logs.append(record)
            except json.JSONDecodeError:
                pass

    def _record_exit(self, code: int, oom: bool) -> None:
        code = 137 if oom else (128 + -code if code < 0 else code)
        self.last_exit, self.last_reason = code, "OOMKilled" if oom else "Error"
        now = _iso(time.time())
        if oom:
            self.events.append({"type": "Warning", "reason": "OOMKilling", "timestamp": now,
                                "message": f"Container shoplite exceeded memory limit of {self.limit_mib}Mi and was killed"})
        else:
            self.events.append({"type": "Warning", "reason": "Failed", "timestamp": now,
                                "message": f"Error: container shoplite exited with code {code}"})

    async def run(self, window_s: float, probe_loop) -> None:
        """Keep one ShopLite alive for `window_s` seconds, restarting it like a kubelet would."""
        deadline = time.time() + window_s
        backoff = 1.0
        while time.time() < deadline and not self._stop:
            await self._spawn()
            assert self._proc
            ready = await self._wait_listening(min(6.0, deadline - time.time()))
            if ready:
                self.ever_ready = True
                killed = await self._watch(deadline, probe_loop)
                if killed is None:
                    break                                   # window over, still running
                self._record_exit(killed[0], oom=killed[1])
            else:
                code = await self._wait_exit(3.0)
                self._record_exit(code if code is not None else 1, oom=False)
            if self.restarts >= MAX_RESTARTS:
                self.events.append({"type": "Warning", "reason": "BackOff", "timestamp": _iso(time.time()),
                                    "message": "Back-off restarting failed container shoplite"})
                break
            self.restarts += 1
            self.events.append({"type": "Warning", "reason": "BackOff", "timestamp": _iso(time.time()),
                                "message": "Back-off restarting failed container shoplite"})
            await asyncio.sleep(backoff)
            backoff *= 2
        await self.stop()

    async def _wait_listening(self, timeout: float) -> bool:
        end = time.time() + max(timeout, 0.5)
        while time.time() < end:
            if self._proc and self._proc.returncode is not None:
                return False
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", self.port), 0.5)
                writer.close()
                return True
            except (OSError, asyncio.TimeoutError):
                await asyncio.sleep(0.2)
        return False

    async def _wait_exit(self, timeout: float) -> Optional[int]:
        try:
            return await asyncio.wait_for(self._proc.wait(), timeout)       # type: ignore[union-attr]
        except asyncio.TimeoutError:
            return None

    async def _watch(self, deadline: float, probe_loop):
        """Probe and watch memory until the window ends (None) or the process dies ((exit code, was OOM))."""
        assert self._proc
        probing = asyncio.create_task(probe_loop(deadline))
        try:
            while time.time() < deadline:
                if self._proc.returncode is not None:
                    return self._proc.returncode, False
                rss = _rss_mib(self._proc.pid)
                if rss is not None:
                    self.peak_rss = max(self.peak_rss, rss)
                    if rss > self.limit_mib:
                        self._proc.kill()
                        await self._proc.wait()
                        return -9, True
                await asyncio.sleep(0.25)
            return None
        finally:
            probing.cancel()

    async def stop(self) -> None:
        self._stop = True
        if self._proc and self._proc.returncode is None:
            self._proc.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(self._proc.wait(), 3)
            except asyncio.TimeoutError:
                self._proc.kill()
        if self._reader:
            await asyncio.sleep(0.1)
            self._reader.cancel()


async def _probe_loop(port: int, probes: List[_Probe], deadline: float) -> None:
    """A blackbox prober: one real request at a time against the live service."""
    routes = [("GET", "/health", None), ("GET", "/products", None), ("POST", "/orders", {"product_id": 1, "quantity": 1})]
    i = 0
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=8.0) as client:
        while time.time() < deadline:
            method, route, body = routes[i % len(routes)]
            i += 1
            started = time.perf_counter()
            try:
                response = await client.request(method, route, json=body)
                status = response.status_code
            except httpx.HTTPError:
                status = 0
            probes.append(_Probe(route, status, (time.perf_counter() - started) * 1000, time.time()))
            await asyncio.sleep(0.15)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def _log_lines(sup: _Supervisor, limit: int = 12) -> List[dict]:
    """The log lines worth showing: every distinct warning/error message, then a few startup lines."""
    chosen, seen = [], set()
    for rec in sup.logs:
        message = str(rec.get("message", ""))
        key = re.sub(r"\d+", "#", message)
        if rec.get("level") in ("ERROR", "WARNING", "CRITICAL") and key not in seen:
            seen.add(key)
            chosen.append({**rec, "timestamp": _iso(rec["ts"]) if isinstance(rec.get("ts"), float) else rec.get("timestamp", "")})
    for rec in sup.logs:
        if len(chosen) >= limit:
            break
        key = re.sub(r"\d+", "#", str(rec.get("message", "")))
        if rec.get("level") == "INFO" and key not in seen:
            seen.add(key)
            chosen.append({**rec, "timestamp": _iso(rec["ts"]) if isinstance(rec.get("ts"), float) else ""})
    return [{k: v for k, v in rec.items() if k != "ts"} for rec in chosen[:limit]]


def _stack_traces(sup: _Supervisor) -> List[dict]:
    """Exceptions that reached the process output (uvicorn prints tracebacks as plain text)."""
    seen, traces = set(), []
    for line in sup.raw:
        match = re.match(r"^(\w+(?:Error|Exception)): (.+)$", line.strip())
        if match and match.group(0) not in seen:
            seen.add(match.group(0))
            traces.append({"timestamp": _iso(time.time()), "error": match.group(0), "service": "shoplite"})
    return traces


def build_observability(sup: _Supervisor, probes: List[_Probe]) -> Dict[str, Any]:
    answered = [p for p in probes if p.status]
    latencies = [p.latency_ms for p in answered]
    errors = [p for p in probes if p.status == 0 or p.status >= 400]
    codes: Dict[str, int] = {}
    for p in errors:
        codes[str(p.status or "no_response")] = codes.get(str(p.status or "no_response"), 0) + 1
    now = _iso(time.time())
    data: Dict[str, Any] = {
        "latency": {"p50": round(_percentile(latencies, 0.5)), "p95": round(_percentile(latencies, 0.95)),
                    "p99": round(_percentile(latencies, 0.99)), "unit": "ms", "timestamp": now, "service": "shoplite"} if latencies else None,
        "error_rate": {"rate": round(100 * len(errors) / len(probes), 1) if probes else 0.0, "count": len(errors),
                       "total_requests": len(probes), "timestamp": now, "service": "shoplite", "error_codes": codes} if probes else None,
        "logs": _log_lines(sup), "stack_traces": _stack_traces(sup),
    }
    return data


def build_kubernetes(sup: _Supervisor, probes: List[_Probe]) -> Dict[str, Any]:
    events = list(sup.events)
    health = [p for p in probes if p.route == "/health"]
    not_ready = [p for p in health if p.status != 200]
    if sup.last_reason == "OOMKilled":
        status = "OOMKilled"
    elif sup.last_exit not in (None, 0) and (sup.restarts > 0 or not sup.ever_ready):
        status = "CrashLoopBackOff"
    else:
        status = "Running"
    if not_ready and status == "Running":
        for p in not_ready[:2]:
            events.append({"type": "Warning", "reason": "Unhealthy", "timestamp": _iso(p.at),
                           "message": f"Readiness probe failed: HTTP probe failed with statuscode: {p.status}"})
    pod = {
        "name": "shoplite-7f9c6d8b5-live1", "namespace": "shoplite", "status": status,
        "ready": status == "Running" and not not_ready, "restart_count": sup.restarts,
        "exit_code": sup.last_exit if sup.last_exit is not None else 0,
        "memory_usage": f"{round(sup.peak_rss)}Mi" if sup.peak_rss else "10Mi", "memory_limit": f"{sup.limit_mib}Mi",
        "cpu_usage": "20m", "cpu_limit": "500m", "started_at": _iso(sup.started_at),
        "last_termination_reason": sup.last_reason, "last_termination_exit_code": sup.last_exit, "events": events,
    }
    return {"pods": [pod]}


def build_cicd(sup: _Supervisor, fault: str, limit_mib: int) -> Dict[str, Any]:
    """The deploy diff against a healthy baseline: what a CI system would report as changed."""
    now = _iso(sup.started_at)
    actual = {"FAULT": fault, "resources.limits.memory": f"{limit_mib}Mi",
              "REQUIRED_SECRET": "missing" if fault == "bad_config" else "present"}
    changes = [{"key": k, "old_value": BASELINE[k], "new_value": v, "timestamp": now, "changed_by": "lab-deploy"}
               for k, v in actual.items() if v != BASELINE[k]]
    return {
        "deployments": [{"deployment_id": "shoplite-deploy-live", "timestamp": now, "service": "shoplite", "namespace": "shoplite",
                         "image": "shoplite:sha-live", "previous_image": "shoplite:sha-abc1234", "strategy": "rolling",
                         "replicas": 1, "status": "success" if sup.ever_ready else "failed"}],
        "code_changes": [], "config_changes": changes, "dependency_changes": [],
    }


def describe(probes: List[_Probe], sup: _Supervisor, obs: Dict[str, Any]) -> tuple:
    """Incident title and description from the symptoms only (never the fault)."""
    rate = (obs.get("error_rate") or {}).get("rate", 0.0)
    p99 = (obs.get("latency") or {}).get("p99", 0)
    if rate == 0 and not sup.restarts and sup.ever_ready:
        return ("ShopLite routine health check", f"Routine check of shoplite: error rate 0%, p99 latency {p99} ms, no restarts. All probes passed.")
    bits = [f"error rate {rate}% over {len(probes)} probes"]
    if p99:
        bits.append(f"p99 latency {p99} ms")
    if sup.restarts:
        bits.append(f"{sup.restarts} container restarts")
    if not sup.ever_ready:
        bits.append("the container never became ready")
    title = "ShopLite unhealthy: " + ", ".join(bits[:2])
    return (title, "Alert on shoplite: " + "; ".join(bits) + ". Service: shoplite, namespace: shoplite.")


async def run_lab(fault: str, limit_mib: Optional[int] = None) -> LabResult:
    """Break a real ShopLite with `fault`, observe it, and return an incident plus the evidence."""
    if fault not in EXPECTED:
        raise ValueError(f"unknown fault '{fault}'. Choose from: {', '.join(EXPECTED)}")
    if not (SHOPLITE_DIR / "app" / "main.py").exists():
        raise FileNotFoundError(f"ShopLite not found at {SHOPLITE_DIR}. Set SHOPLITE_DIR.")
    limit = limit_mib or (128 if fault == "oom" else 256)
    port = _free_port()
    sup, probes = _Supervisor(fault, limit, port), []
    await sup.run(WINDOW_S.get(fault, DEFAULT_WINDOW_S), lambda deadline: _probe_loop(port, probes, deadline))

    obs, kube, cicd = build_observability(sup, probes), build_kubernetes(sup, probes), build_cicd(sup, fault, limit)
    evidence = (cicd_evidence_from_data(cicd) + kubernetes_evidence_from_data(kube) + observability_evidence_from_data(obs))
    for item in evidence:
        item.source = SOURCE
    title, description = describe(probes, sup, obs)
    now = datetime.now(timezone.utc)
    incident = Incident(
        incident_id=f"live-shoplite-{fault.replace('_', '-')}-{now.strftime('%H%M%S')}", title=title, description=description,
        severity="high", source="live-lab", service_name="shoplite", namespace="shoplite",
        started_at=now - timedelta(seconds=WINDOW_S.get(fault, DEFAULT_WINDOW_S)), detected_at=now,
        metadata={"lab": True}, tags=["live", "shoplite"],
    )
    return LabResult(fault, EXPECTED[fault], incident, evidence,
                     {"probes": len(probes), "restarts": sup.restarts, "last_exit": sup.last_exit, "peak_rss_mib": round(sup.peak_rss)})
