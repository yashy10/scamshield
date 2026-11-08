"""The guardian sign-up, shared by the HTML form and the JSON API so both apply the same rules."""

from __future__ import annotations

import re
import secrets

from scamshield.store import Invite, Store

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")

AGREE_MESSAGE = "Check this box once they’ve agreed. ScamShield only protects people who want it."


def validate_signup(guardian_name: str, guardian_email: str, protected_name: str, agreed: bool
                    ) -> tuple[dict[str, str], dict[str, str]]:
    """(cleaned data, errors keyed guardian_name / guardian_email / protected_name / agreed)."""
    data = {"guardian_name": guardian_name.strip(), "guardian_email": guardian_email.strip(),
            "protected_name": protected_name.strip()}
    errors = {}
    if not 1 <= len(data["guardian_name"]) <= 60:
        errors["guardian_name"] = "Enter your name."
    if not EMAIL_RE.fullmatch(data["guardian_email"]):
        errors["guardian_email"] = "Enter an email address like name@example.com."
    if not 1 <= len(data["protected_name"]) <= 40:
        errors["protected_name"] = "Enter their first name."
    if not agreed:
        errors["agreed"] = AGREE_MESSAGE
    return data, errors


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
    return f"{slug or 'user'}-{secrets.token_hex(2)}"


def create_invite(store: Store, data: dict[str, str]) -> Invite:
    invite = Invite(
        token=secrets.token_urlsafe(18),
        user_id=_slug(data["protected_name"]),
        protected_name=data["protected_name"],
        guardian_name=data["guardian_name"],
        guardian_email=data["guardian_email"].lower(),
    )
    store.put_invite(invite)
    return invite
