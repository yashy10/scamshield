"""AgentCore Runtime entrypoint for the investigator agent (Phases 3 and 5).

Payload: {"user_id": "grandma"} starts a scan in the background and returns at once, which is
what EventBridge Scheduler sends. {"user_id": "grandma", "wait": true} runs the scan and returns
its result (the demo's "Scan now").
"""

from __future__ import annotations

import contextvars
import logging
import threading

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from scamshield_agent.profile import USER_ID_RE
from scamshield_agent.scan import run_scan

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("scamshield.agent")

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    user_id = str((payload or {}).get("user_id", ""))
    if not USER_ID_RE.fullmatch(user_id):
        return {"error": "payload needs a valid user_id"}

    if payload.get("wait"):
        return run_scan(user_id).as_dict()

    # Background scan: the health check reports HealthyBusy until complete_async_task.
    task_id = app.add_async_task("scan", {"user_id": user_id})
    context = contextvars.copy_context()  # keeps the runtime's request context (workload token) for Identity calls

    def work() -> None:
        try:
            run_scan(user_id)
        except Exception:
            log.exception("scan failed user=%s", user_id)
        finally:
            app.complete_async_task(task_id)

    threading.Thread(target=context.run, args=(work,), daemon=True).start()
    return {"status": "scan_started", "user_id": user_id}


if __name__ == "__main__":
    app.run()
