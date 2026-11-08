"""One scan for one protected user: fetch new emails, investigate, label, warn."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from strands import Agent
from strands.models import Model
from strands.tools.mcp import MCPClient

from .config import AgentSettings, get_settings
from .hooks import PinUserId, ToolLog
from .model import build_model
from .profile import Profile, load_profile
from .prompt import build_system_prompt

log = logging.getLogger("scamshield.agent")

SCAN_PROMPT = "Run a scan of the inbox now."


@dataclass
class ScanResult:
    user_id: str
    summary: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    user_id_overrides: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def gateway_headers(cfg: AgentSettings) -> dict[str, str]:
    """Bearer token for the Gateway. In the cloud it is a Cognito machine token from AgentCore Identity."""
    if cfg.gateway_auth == "none":
        return {}
    if cfg.gateway_auth == "agentcore-m2m":
        from bedrock_agentcore.identity.auth import requires_access_token

        @requires_access_token(provider_name=cfg.gateway_provider, scopes=list(cfg.gateway_scopes), auth_flow="M2M")
        async def _token(*, access_token: str) -> str:
            return access_token

        return {"Authorization": f"Bearer {asyncio.run(_token())}"}
    raise ValueError(f"Unknown SCAMSHIELD_GATEWAY_AUTH: {cfg.gateway_auth!r}")


def run_scan(
    user_id: str,
    *,
    settings: AgentSettings | None = None,
    model: Model | None = None,
    profile: Profile | None = None,
) -> ScanResult:
    cfg = settings or get_settings()
    profile = profile or load_profile(user_id, cfg)
    pin, tool_log = PinUserId(profile.user_id), ToolLog()

    client = MCPClient(url=cfg.mcp_url, headers=gateway_headers(cfg) or None)
    with client:
        agent = Agent(
            model=model or build_model(cfg),
            tools=client.list_tools_sync(),
            system_prompt=build_system_prompt(profile, cfg.tool_prefix),
            hooks=[pin, tool_log],
            callback_handler=None,
        )
        result = agent(SCAN_PROMPT)

    log.info("scan user=%s tool_calls=%d user_id_overrides=%d", profile.user_id, len(tool_log.calls), pin.overrides)
    return ScanResult(
        user_id=profile.user_id,
        summary=str(result).strip(),
        tool_calls=tool_log.calls,
        user_id_overrides=pin.overrides,
    )
