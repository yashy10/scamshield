"""The demo's "Scan now" button: run one scan for a user and keep the latest result in memory.

With SCAMSHIELD_AGENT_ARN set, it invokes the deployed agent runtime (Phase 3+). Otherwise it runs
the local agent (`agent/`), which needs the local MCP server running.

detached=True (on Vercel, where a function freezes once it responds): ask the deployed agent to start
a background scan and return straight away; the warnings arrive by email.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"
log = logging.getLogger("scamshield.web.scans")


@dataclass
class ScanState:
    status: str  # running | done | started | error
    summary: str = ""
    tool_calls: int = 0
    labeled: int = 0  # emails the agent recorded a verdict for
    error: str = ""
    at: float = field(default_factory=time.time)  # when this state began


class ScanRunner:
    def __init__(self, agent_arn: str | None = None, region: str = "us-east-1", agent_dir: Path = AGENT_DIR,
                 detached: bool = False) -> None:
        self.agent_arn = agent_arn
        self.region = region
        self.agent_dir = agent_dir
        self.detached = detached
        self.states: dict[str, ScanState] = {}
        self._lock = threading.Lock()

    def start(self, user_id: str) -> None:
        if self.detached:
            self._start_detached(user_id)
            return
        with self._lock:
            if self.states.get(user_id, ScanState("idle")).status == "running":
                return
            self.states[user_id] = ScanState("running")
        threading.Thread(target=self._run, args=(user_id,), daemon=True).start()

    def _run(self, user_id: str) -> None:
        try:
            result = self._invoke_deployed(user_id) if self.agent_arn else self._invoke_local(user_id)
            calls = result.get("tool_calls", [])
            labeled = sum(1 for c in calls if str(c.get("tool", "")).endswith("label_email") and c.get("status") == "success")
            state = ScanState("done", summary=result.get("summary", ""), tool_calls=len(calls), labeled=labeled)
        except Exception as exc:  # the page shows a plain message; the detail goes to the log
            log.warning("scan failed user=%s: %s", user_id, exc)
            state = ScanState("error", error=str(exc)[:400])
        with self._lock:
            self.states[user_id] = state

    def _start_detached(self, user_id: str) -> None:
        if not self.agent_arn:
            state = ScanState("error", error="Scan now on the hosted site needs the deployed agent: set SCAMSHIELD_AGENT_ARN.")
        else:
            try:
                self._invoke_deployed(user_id, wait=False)
                state = ScanState("started", summary="Scan started. Any warnings arrive by email within a few minutes.")
            except Exception as exc:
                state = ScanState("error", error=str(exc)[:400])
        with self._lock:
            self.states[user_id] = state

    def _invoke_local(self, user_id: str) -> dict:
        # The agent has its own project environment; don't hand it this site's virtualenv.
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME")}
        started = time.time()
        proc = subprocess.run(
            ["uv", "run", "--directory", str(self.agent_dir), "python", "-m", "scamshield_agent",
             "--user-id", user_id, "--json"],
            capture_output=True, text=True, timeout=600, env=env,
        )
        if proc.returncode != 0:
            tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
            log.warning("agent exited %s after %.0fs user=%s; stderr tail:\n%s",
                        proc.returncode, time.time() - started, user_id, tail)
            lines = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
            raise RuntimeError(lines[-1] if lines else "The scan failed.")
        log.info("agent finished in %.0fs user=%s", time.time() - started, user_id)
        return json.loads(proc.stdout)

    def _invoke_deployed(self, user_id: str, wait: bool = True) -> dict:
        import boto3

        resp = boto3.client("bedrock-agentcore", region_name=self.region).invoke_agent_runtime(
            agentRuntimeArn=self.agent_arn,
            qualifier="DEFAULT",
            runtimeSessionId=f"scan-now-{user_id}-{uuid.uuid4().hex}",
            contentType="application/json",
            payload=json.dumps({"user_id": user_id, "wait": wait}).encode(),
        )
        return json.loads(resp["response"].read())
