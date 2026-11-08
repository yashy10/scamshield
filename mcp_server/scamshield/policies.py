"""Cedar policies for the AgentCore Policy engine on the Gateway (Phase 4).

Policy denies any tool call that no policy permits, so:
  Rule 1 (inbox actions are label-only) = permit exactly the four non-sending tools.
  Rule 2 (warnings only to the user and their guardian) = one send_warning permit per user,
  generated from the store, because Cedar can't read DynamoDB at decision time.

Gateway action names are "<target><separator><tool>". AWS docs show both "___" and "__";
read the real names from the deployed Gateway's tool list before generating.
"""

from __future__ import annotations

import re

from .credentials import validate_user_id
from .store import UserProfile

INBOX_TOOLS = ("get_new_emails", "check_domain_age", "check_threat_list", "label_email")
_GATEWAY_ARN = re.compile(r"^arn:aws[a-z-]*:bedrock-agentcore:[a-z0-9-]+:\d{12}:gateway/[A-Za-z0-9_-]+$")
_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")
_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _check(value: str, pattern: re.Pattern[str], what: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"Invalid {what}: {value!r}")
    return value


def _action(tool: str, target: str, sep: str) -> str:
    return f'AgentCore::Action::"{target}{sep}{tool}"'


def _caller_condition(client_id: str | None) -> str:
    if not client_id:
        return ""
    _check(client_id, _NAME, "client id")
    return f'principal.hasTag("client_id") && principal.getTag("client_id") == "{client_id}"'


def inbox_tools_policy(gateway_arn: str, *, target: str = "scamshield", sep: str = "___", client_id: str | None = None) -> str:
    _check(gateway_arn, _GATEWAY_ARN, "gateway ARN")
    _check(target, _NAME, "target name")
    actions = ",\n    ".join(_action(t, target, sep) for t in INBOX_TOOLS)
    caller = _caller_condition(client_id)
    when = f"\nwhen {{\n  {caller}\n}}" if caller else ""
    return (
        "// Rule 1: inbox actions are label-only. Only these four tools are permitted;\n"
        "// any other tool (send, forward, delete...) is denied by default.\n"
        "permit(\n"
        "  principal,\n"
        f"  action in [\n    {actions}\n  ],\n"
        f'  resource == AgentCore::Gateway::"{gateway_arn}"){when};\n'
    )


def send_warning_policy(
    gateway_arn: str,
    profile: UserProfile,
    *,
    target: str = "scamshield",
    sep: str = "___",
    client_id: str | None = None,
) -> str:
    _check(gateway_arn, _GATEWAY_ARN, "gateway ARN")
    _check(target, _NAME, "target name")
    user_id = validate_user_id(profile.user_id)
    recipients = sorted(_check(r, _EMAIL, "email address") for r in profile.allowed_recipients())
    if not profile.guardian_email:
        raise ValueError(f"User {user_id!r} has no guardian linked.")
    allowed = ", ".join(f'"{r}"' for r in recipients)
    conditions = [
        f'context.input.user_id == "{user_id}"',
        f"[{allowed}].containsAll(context.input.recipients)",
    ]
    if caller := _caller_condition(client_id):
        conditions.insert(0, caller)
    body = " &&\n  ".join(conditions)
    return (
        f"// Rule 2 for {user_id}: warnings go only to the user and their linked guardian.\n"
        "// Generated from the store by scripts/sync_policies.py; regenerate when the guardian changes.\n"
        "permit(\n"
        "  principal,\n"
        f"  action == {_action('send_warning', target, sep)},\n"
        f'  resource == AgentCore::Gateway::"{gateway_arn}")\n'
        f"when {{\n  {body}\n}};\n"
    )
