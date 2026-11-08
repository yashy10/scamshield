"""Runtime settings, read from environment variables (and the repo-root .env when present).

Local secrets and state default to <repo>/.local/, outside the mcp_server/ code folder, because
AgentCore CodeZip packaging uploads everything in the code folder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # .../mcp_server
REPO_ROOT = PACKAGE_ROOT.parent
LOCAL_DIR = REPO_ROOT / ".local"  # git-ignored; never inside a deployed code folder


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    # Storage: "local" (JSON file, for Phase 1) or "dynamodb".
    store_backend: str
    local_store_path: Path
    dynamodb_table: str
    aws_region: str

    # Outbound warnings: "console" (print only) or "ses".
    email_backend: str
    ses_from_address: str | None

    # "api" (real Gmail) or "fixture" (simulated inbox, RDAP and Safe Browsing from a JSON file,
    # for running the agent with only AWS credentials).
    gmail_backend: str
    fixture_inbox: Path
    # "local" (Phase 1: token file + env key) or "agentcore" (Phase 3: AgentCore Identity).
    credentials_backend: str
    secrets_dir: Path
    safe_browsing_api_key: str | None
    # AgentCore Identity (Phase 3). The workload name is the MCP server runtime's ID.
    workload_name: str | None
    google_provider_name: str
    safe_browsing_provider_name: str

    # Scan limits.
    gmail_lookback_days: int
    max_emails_per_scan: int
    max_links_per_email: int
    snippet_chars: int

    label_name: str
    # Defense in depth: the tool also refuses recipients that are not the user or
    # their guardian. AgentCore Policy enforces the same rule at the Gateway.
    tool_recipient_check: bool

    host: str
    port: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    return Settings(
        store_backend=os.environ.get("SCAMSHIELD_STORE", "local").lower(),
        local_store_path=_env_path("SCAMSHIELD_LOCAL_STORE_PATH", LOCAL_DIR / "store.json"),
        dynamodb_table=os.environ.get("SCAMSHIELD_DYNAMODB_TABLE", "ScamShield"),
        # SCAMSHIELD_AWS_REGION wins: hosts like Vercel set AWS_REGION to their own function region.
        aws_region=os.environ.get("SCAMSHIELD_AWS_REGION") or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1",
        email_backend=os.environ.get("SCAMSHIELD_EMAIL_BACKEND", "console").lower(),
        ses_from_address=os.environ.get("SCAMSHIELD_SES_FROM") or None,
        gmail_backend=os.environ.get("SCAMSHIELD_GMAIL", "api").lower(),
        fixture_inbox=_env_path("SCAMSHIELD_FIXTURE_INBOX", REPO_ROOT / "demo" / "inbox.json"),
        credentials_backend=os.environ.get("SCAMSHIELD_CREDENTIALS", "local").lower(),
        secrets_dir=_env_path("SCAMSHIELD_SECRETS_DIR", LOCAL_DIR / "secrets"),
        safe_browsing_api_key=os.environ.get("SAFE_BROWSING_API_KEY") or None,
        workload_name=os.environ.get("SCAMSHIELD_WORKLOAD_NAME") or None,
        google_provider_name=os.environ.get("SCAMSHIELD_GOOGLE_PROVIDER", "scamshield-google"),
        safe_browsing_provider_name=os.environ.get("SCAMSHIELD_SAFE_BROWSING_PROVIDER", "scamshield-safe-browsing"),
        gmail_lookback_days=_env_int("SCAMSHIELD_LOOKBACK_DAYS", 3),
        max_emails_per_scan=_env_int("SCAMSHIELD_MAX_EMAILS", 10),
        max_links_per_email=_env_int("SCAMSHIELD_MAX_LINKS", 10),
        snippet_chars=_env_int("SCAMSHIELD_SNIPPET_CHARS", 400),
        label_name=os.environ.get("SCAMSHIELD_LABEL", "ScamShield"),
        tool_recipient_check=_env_bool("SCAMSHIELD_TOOL_RECIPIENT_CHECK", True),
        # Bind to localhost by default; set SCAMSHIELD_HOST=0.0.0.0 inside AgentCore Runtime.
        host=os.environ.get("SCAMSHIELD_HOST", "127.0.0.1"),
        port=_env_int("SCAMSHIELD_PORT", 8000),
    )
