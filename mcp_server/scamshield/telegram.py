"""Telegram alerts: a short "Scam blocked successfully" message to one Telegram chat each time
ScamShield flags an email as a scam, with a link to the ScamShield dashboard.

Best effort: a failed alert is logged and never fails the tool call. The email is already labeled,
and the warning emails are what the person relies on.

The bot token is part of every Bot API URL, so it must never reach a log line: errors here carry
our own message only (never the request URL), and httpx request logging stays off.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Callable
from typing import Protocol

import httpx2

from .credentials import CredentialError
from .notify import defang

log = logging.getLogger("scamshield.telegram")
# httpx logs every request URL at INFO, and a Bot API URL contains the bot token.
logging.getLogger("httpx2").setLevel(logging.WARNING)

API_URL = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_LINK = "https://scamshield-lac-two.vercel.app/"


class TelegramError(Exception):
    pass


class TelegramClient:
    """A minimal Telegram Bot API client (only what ScamShield uses)."""

    def __init__(self, token: str, http: httpx2.Client | None = None) -> None:
        self._token = token
        self._http = http or httpx2.Client(timeout=10)

    def call(self, method: str, payload: dict | None = None) -> dict | list:
        try:
            resp = self._http.post(API_URL.format(token=self._token, method=method), json=payload or {})
        except httpx2.HTTPError:
            # `from None`: the original exception can carry the URL, and with it the token.
            raise TelegramError(f"Could not reach Telegram ({method}).") from None
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code != 200 or not body.get("ok"):
            detail = str(body.get("description") or "no details")[:200]
            raise TelegramError(f"Telegram refused {method} (HTTP {resp.status_code}): {detail}")
        return body["result"]


def scam_blocked_message(*, protected_name: str | None, sender_domain: str | None, link: str) -> dict:
    """The sendMessage payload (minus chat_id). Never includes the email's subject or body."""
    e = html.escape
    who = f"sent to {e(protected_name)}" if protected_name else "in a protected inbox"
    lines = [
        "🛡️ <b>Scam blocked successfully</b>",
        "",
        f"ScamShield caught a scam email {who} and flagged it in Gmail.",
    ]
    if sender_domain:
        lines.append(f"From: {e(defang(sender_domain))}")
    lines += ["", f"Check it here: {e(link)}"]
    payload: dict = {
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    # Telegram rejects button URLs it can't open (e.g. http://localhost), which would fail the whole send.
    if link.startswith("https://"):
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "Open ScamShield", "url": link}]]}
    return payload


class ScamAlerts(Protocol):
    def scam_blocked(self, *, protected_name: str | None, sender_domain: str | None) -> bool: ...


class TelegramAlerts:
    """Sends the alert to one chat. `token` is called on each send, so a vault-held token can rotate."""

    def __init__(
        self,
        token: Callable[[], str],
        chat_id: str,
        link: str = DEFAULT_LINK,
        client_factory: Callable[[str, httpx2.Client], TelegramClient] = TelegramClient,
    ) -> None:
        self._token = token
        self.chat_id = chat_id
        self.link = link
        self._client_factory = client_factory
        self._http = httpx2.Client(timeout=5)

    def scam_blocked(self, *, protected_name: str | None, sender_domain: str | None) -> bool:
        payload = scam_blocked_message(protected_name=protected_name, sender_domain=sender_domain, link=self.link)
        try:
            self._client_factory(self._token(), self._http).call("sendMessage", {"chat_id": self.chat_id, **payload})
        except Exception as exc:  # best effort: never fail the tool over an alert
            known = isinstance(exc, (TelegramError, CredentialError))
            log.warning("Telegram alert not sent: %s", exc if known else type(exc).__name__)
            return False
        log.info("Telegram alert sent")
        return True
