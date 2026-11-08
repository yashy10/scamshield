from __future__ import annotations

import dataclasses
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from scamshield import server
from scamshield.testing import make_fake_env
from scamshield_agent.config import get_settings


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mcp(tmp_path: Path):
    """The real ScamShield MCP server over streamable HTTP, backed by in-memory fakes."""
    fake = make_fake_env(tmp_path)
    server.set_services(fake.services)
    port = _free_port()
    uv = uvicorn.Server(
        uvicorn.Config(server.mcp.streamable_http_app(stateless_http=True), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not uv.started and time.time() < deadline:
        time.sleep(0.05)
    assert uv.started, "MCP server did not start"
    settings = dataclasses.replace(
        get_settings(),
        mcp_url=f"http://127.0.0.1:{port}/mcp",
        tool_prefix="",
        gateway_auth="none",
        store_backend="local",
        local_store_path=fake.services.settings.local_store_path,
    )
    yield fake, settings
    uv.should_exit = True
    thread.join(timeout=10)
    server.set_services(None)
