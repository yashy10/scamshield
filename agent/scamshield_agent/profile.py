"""Read the protected user's profile (their address and their guardian's) from the shared store.

The agent puts these two addresses in its system prompt, so the warning recipients come from
code-written configuration, never from email content. Same storage layout as mcp_server/scamshield/store.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .config import AgentSettings

USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ProfileError(Exception):
    pass


@dataclass(frozen=True)
class Profile:
    user_id: str
    email: str
    guardian_email: str | None
    display_name: str | None = None


def load_profile(user_id: str, cfg: AgentSettings) -> Profile:
    if not USER_ID_RE.fullmatch(user_id or ""):
        raise ProfileError("Invalid user_id.")
    raw = _read(user_id, cfg)
    if not raw or not raw.get("email"):
        raise ProfileError(f"User '{user_id}' is not set up (connect Gmail first).")
    return Profile(
        user_id=user_id,
        email=raw["email"].lower(),
        guardian_email=(raw.get("guardian_email") or "").lower() or None,
        display_name=raw.get("display_name"),
    )


def _read(user_id: str, cfg: AgentSettings) -> dict | None:
    if cfg.store_backend == "local":
        if not cfg.local_store_path.exists():
            return None
        return json.loads(cfg.local_store_path.read_text())["users"].get(user_id)
    if cfg.store_backend == "dynamodb":
        import boto3

        table = boto3.resource("dynamodb", region_name=cfg.region).Table(cfg.dynamodb_table)
        return table.get_item(Key={"pk": f"USER#{user_id}", "sk": "PROFILE"}).get("Item")
    raise ProfileError(f"Unknown SCAMSHIELD_STORE: {cfg.store_backend!r}")
