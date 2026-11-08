"""In-memory fakes for Gmail, RDAP, Safe Browsing and SES. Used by the tests, the agent's
end-to-end tests, and the fixture-inbox demo mode (SCAMSHIELD_GMAIL=fixture)."""

from __future__ import annotations

import base64
import dataclasses
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import get_settings
from .notify import Message
from .rdap import DomainAge
from .safebrowsing import ThreatResult
from .server import Services
from .store import LocalStore, UserProfile

PHISH_URL = "http://testsafebrowsing.appspot.com/s/phishing.html"


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def gmail_message(email_id: str, *, sender: str, subject: str, text: str = "", html: str = "") -> dict:
    """A message shaped like the Gmail API's format=full response."""
    parts = []
    if text:
        parts.append({"mimeType": "text/plain", "headers": [{"name": "Content-Type", "value": "text/plain; charset=UTF-8"}], "body": {"data": b64(text)}})
    if html:
        parts.append({"mimeType": "text/html", "headers": [{"name": "Content-Type", "value": "text/html; charset=UTF-8"}], "body": {"data": b64(html)}})
    return {
        "id": email_id,
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [{"name": "From", "value": sender}, {"name": "Subject", "value": subject}],
            "parts": parts,
        },
    }


class FakeGmail:
    def __init__(self, profile_email: str = "grandma@example.com") -> None:
        self.messages: dict[str, dict] = {}
        self.labels: dict[str, str] = {}
        self.applied: list[tuple[str, str]] = []
        self.last_query: str | None = None
        self._profile_email = profile_email

    def add(self, message: dict) -> None:
        self.messages[message["id"]] = message

    def profile_email(self) -> str:
        return self._profile_email

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        self.last_query = query
        return list(self.messages)[:max_results]

    def get_message(self, email_id: str) -> dict:
        return self.messages[email_id]

    def get_headers(self, email_id: str, names: list[str]) -> dict[str, str]:
        headers = self.messages[email_id]["payload"]["headers"]
        return {h["name"].lower(): h["value"] for h in headers}

    def ensure_label(self, name: str) -> str:
        return self.labels.setdefault(name, f"Label_{len(self.labels) + 1}")

    def add_label(self, email_id: str, label_id: str) -> None:
        self.applied.append((email_id, label_id))


class FakeTokens:
    def __init__(self) -> None:
        self.requested_for: list[str] = []

    def access_token(self, user_id: str) -> str:
        self.requested_for.append(user_id)
        return "fake-token"


class FakeKeys:
    def safe_browsing_key(self) -> str:
        return "fake-key"


class FakeRdap:
    def __init__(self, ages: dict[str, int]) -> None:
        self.ages = ages

    def lookup(self, domain: str) -> DomainAge:
        if domain not in self.ages:
            return DomainAge(domain=domain, lookup_status="not_found")
        age = self.ages[domain]
        registered = (datetime.now(UTC) - timedelta(days=age)).date().isoformat()
        return DomainAge(domain=domain, registered_date=registered, age_days=age)


class FakeSafeBrowsing:
    FLAGGED = {PHISH_URL}

    def __init__(self, key: str) -> None:
        pass

    def check(self, url: str) -> ThreatResult:
        if url in self.FLAGGED:
            return ThreatResult(url=url, flagged=True, threat_type="SOCIAL_ENGINEERING")
        return ThreatResult(url=url, flagged=False)


class AlertRecorder:
    """Records "Scam blocked" alerts instead of sending them to Telegram."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def scam_blocked(self, *, protected_name: str | None, sender_domain: str | None) -> bool:
        self.sent.append({"protected_name": protected_name, "sender_domain": sender_domain})
        return True


class OutboxSender:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        self.sent.append(message)


@dataclass
class FakeEnv:
    services: Services
    gmail: FakeGmail
    tokens: FakeTokens
    outbox: OutboxSender
    store: LocalStore
    alerts: AlertRecorder


def make_fake_env(tmp_path: Path) -> FakeEnv:
    """Services wired to fakes plus a real LocalStore in tmp_path, with user 'grandma' linked to guardian Alex."""
    settings = dataclasses.replace(get_settings(), local_store_path=tmp_path / "store.json", secrets_dir=tmp_path)
    store = LocalStore(settings.local_store_path)
    store.put_user(
        UserProfile(
            user_id="grandma",
            email="grandma@example.com",
            guardian_email="alex@example.com",
            display_name="Margaret",
            guardian_name="Alex",
        )
    )
    gmail, tokens, outbox, alerts = FakeGmail(), FakeTokens(), OutboxSender(), AlertRecorder()
    services = Services(
        settings=settings,
        store=store,
        gmail_tokens=tokens,
        api_keys=FakeKeys(),
        rdap=FakeRdap({"chase-secure-login.com": 3, "chase.com": 10_000, "example.com": 10_000}),
        sender=outbox,
        gmail_factory=lambda token: gmail,
        safebrowsing_factory=FakeSafeBrowsing,
        alerts=alerts,
    )
    return FakeEnv(services=services, gmail=gmail, tokens=tokens, outbox=outbox, store=store, alerts=alerts)


def fixture_services(settings, store, sender, alerts=None) -> Services:
    """Demo mode: a simulated inbox plus simulated RDAP and Safe Browsing, from a JSON file.

    The file holds {"profile_email", "domain_ages": {domain: days}, "flagged_urls": [...],
    "emails": [{"id", "from", "subject", "text"?, "html"?}]}. Only the model is real.
    """
    data = json.loads(Path(settings.fixture_inbox).read_text())
    gmail = FakeGmail(profile_email=data.get("profile_email", "grandma@example.com"))
    for email in data["emails"]:
        gmail.add(gmail_message(email["id"], sender=email["from"], subject=email["subject"],
                                text=email.get("text", ""), html=email.get("html", "")))
    flagged = frozenset(data.get("flagged_urls", []))

    class FixtureSafeBrowsing(FakeSafeBrowsing):
        FLAGGED = flagged

    logging.getLogger("scamshield").warning(
        "FIXTURE INBOX MODE: Gmail, RDAP and Safe Browsing are simulated from %s", settings.fixture_inbox
    )
    return Services(
        settings=settings,
        store=store,
        gmail_tokens=FakeTokens(),
        api_keys=FakeKeys(),
        rdap=FakeRdap(data.get("domain_ages", {})),
        sender=sender,
        gmail_factory=lambda token: gmail,
        safebrowsing_factory=FixtureSafeBrowsing,
        alerts=alerts,
    )
