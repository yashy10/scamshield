"""The demo's "Scan now" button: run one scan for a user and keep the latest result in memory.

With SCAMSHIELD_AGENT_ARN set, it invokes the deployed agent runtime (Phase 3+). Otherwise it runs
the local agent (`agent/`), which needs the local MCP server running.

detached=True (on Vercel, where a function freezes once it responds): ask the deployed agent to start
a background scan and return straight away; the warnings arrive by email.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"


@dataclass
class ScanState:
    status: str  # running | done | started | error
    summary: str = ""
    tool_calls: int = 0
    error: str = ""


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
            state = ScanState("done", summary=result.get("summary", ""), tool_calls=len(result.get("tool_calls", [])))
        except Exception as exc:  # shown on the page; the operator fixes and retries
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
        proc = subprocess.run(
            ["uv", "run", "--directory", str(self.agent_dir), "python", "-m", "scamshield_agent",
             "--user-id", user_id, "--json"],
            capture_output=True, text=True, timeout=600, env=os.environ.copy(),
        )
        if proc.returncode != 0:
            lines = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
            raise RuntimeError(lines[-1] if lines else "The scan failed.")
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
