"""Agent settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]  # .../agent


@dataclass(frozen=True)
class AgentSettings:
    # Where the tools are: the local MCP server (Phase 2) or the Gateway's MCP URL (Phase 3).
    mcp_url: str
    # Behind the Gateway, tool names carry the target prefix, e.g. "scamshield___".
    tool_prefix: str
    # "converse" (bedrock-runtime, default) or "mantle" (Claude in Amazon Bedrock); see model.py.
    model_provider: str
    model_id: str
    effort: str
    max_tokens: int
    region: str
    # Gateway auth: "none" locally, "agentcore-m2m" in the cloud (Cognito token via AgentCore Identity).
    gateway_auth: str
    gateway_provider: str
    gateway_scopes: tuple[str, ...]
    # Where the user -> guardian link lives (same store as the MCP server).
    store_backend: str
    local_store_path: Path
    dynamodb_table: str


# Injected into every runtime by the AgentCore CLI's CDK app for the gateway named ScamShieldGateway.
_CLI_GATEWAY_URL = "AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_URL"
_CLI_GATEWAY_CREDENTIAL = "AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_CREDENTIAL_PROVIDER"


def _provider_name(value: str) -> str:
    """The CLI may pass the credential provider's ARN; Identity APIs take its name."""
    return value.rsplit("/", 1)[-1] if value.startswith("arn:") else value


def get_settings() -> AgentSettings:
    env = os.environ.get
    gateway_url = env(_CLI_GATEWAY_URL)
    if gateway_url and not gateway_url.rstrip("/").endswith("/mcp"):
        gateway_url = gateway_url.rstrip("/") + "/mcp"
    on_gateway = bool(gateway_url) and not env("SCAMSHIELD_MCP_URL")
    return AgentSettings(
        mcp_url=env("SCAMSHIELD_MCP_URL") or gateway_url or "http://127.0.0.1:8000/mcp",
        tool_prefix=env("SCAMSHIELD_TOOL_PREFIX", "scamshield___" if on_gateway else ""),
        model_provider=(provider := env("SCAMSHIELD_MODEL_PROVIDER", "converse").lower()),
        model_id=env(
            "SCAMSHIELD_MODEL_ID",
            "anthropic.claude-opus-5-5" if provider == "mantle" else "us.anthropic.claude-opus-5-5",
        ),
        effort=env("SCAMSHIELD_EFFORT", "medium"),
        # Opus 5.5 can write up to 128K tokens; a turn that weighs ten emails and plans ~50 lookups needs room.
        max_tokens=int(env("SCAMSHIELD_MAX_TOKENS", "64000")),
        region=env("SCAMSHIELD_AWS_REGION") or env("AWS_REGION") or env("AWS_DEFAULT_REGION") or "us-east-1",
        gateway_auth=env("SCAMSHIELD_GATEWAY_AUTH", "agentcore-m2m" if on_gateway else "none").lower(),
        gateway_provider=_provider_name(
            env("SCAMSHIELD_GATEWAY_PROVIDER") or env(_CLI_GATEWAY_CREDENTIAL) or "ScamShield_default_ScamShieldGateway-oauth"
        ),
        gateway_scopes=tuple(
            s for s in env("SCAMSHIELD_GATEWAY_SCOPES", "scamshield-gateway/invoke" if on_gateway else "").split(",") if s
        ),
        store_backend=env("SCAMSHIELD_STORE", "local").lower(),
        local_store_path=Path(env("SCAMSHIELD_LOCAL_STORE_PATH", str(AGENT_ROOT.parent / ".local" / "store.json"))),
        dynamodb_table=env("SCAMSHIELD_DYNAMODB_TABLE", "ScamShield"),
    )
