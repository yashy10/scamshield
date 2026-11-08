"""Telegram "Scam blocked successfully" alerts: when they fire, what they say, and that they never break a scan."""

import dataclasses
import json
import logging

import httpx2
import pytest

from scamshield.config import get_settings
from scamshield.server import make_alerts
from scamshield.telegram import TelegramAlerts, TelegramClient, scam_blocked_message

from .test_tools import PLAIN_ID, SCAM_ID, call, seed

LINK = "https://scamshield-lac-two.vercel.app/"
TOKEN = "123456789:AAH-secret-token-value-0123456789abc"


@pytest.mark.anyio
async def test_alert_once_per_blocked_scam(env):
    seed(env)
    await call("label_email", {"user_id": "grandma", "email_id": PLAIN_ID, "verdict": "fine"})
    assert env.alerts.sent == []

    await call("label_email", {"user_id": "grandma", "email_id": SCAM_ID, "verdict": "scam"})
    assert env.alerts.sent == [{"protected_name": "Margaret", "sender_domain": "chase-secure-login.com"}]

    # A retried label_email doesn't alert again.
    await call("label_email", {"user_id": "grandma", "email_id": SCAM_ID, "verdict": "scam"})
    assert len(env.alerts.sent) == 1


@pytest.mark.anyio
async def test_suspicious_emails_dont_alert(env):
    seed(env)
    result = await call("label_email", {"user_id": "grandma", "email_id": SCAM_ID, "verdict": "suspicious"})
    assert result.structured_content["labeled"] is True
    assert env.alerts.sent == []


@pytest.mark.anyio
async def test_alert_when_warning_was_sent_first(env):
    """Real scans often warn before labeling; send_warning already wrote verdict=scam then."""
    seed(env)
    await call("send_warning", {
        "user_id": "grandma", "email_id": SCAM_ID, "verdict": "scam",
        "reasons": ["The website was created 3 days ago."], "recipients": ["grandma@example.com"],
    })
    assert env.alerts.sent == []
    await call("label_email", {"user_id": "grandma", "email_id": SCAM_ID, "verdict": "scam"})
    assert len(env.alerts.sent) == 1


def test_message_text():
    payload = scam_blocked_message(protected_name="Margaret <b>", sender_domain="chase-secure-login.com", link=LINK)
    text = payload["text"]
    assert "Scam blocked successfully" in text
    assert LINK in text
    assert "chase-secure-login[.]com" in text  # defanged: not a tappable link
    assert "Margaret &lt;b&gt;" in text  # HTML-escaped
    assert payload["reply_markup"]["inline_keyboard"][0][0]["url"] == LINK

    # No name, no sender, and a link Telegram can't use as a button (it would reject the whole message).
    local = scam_blocked_message(protected_name=None, sender_domain=None, link="http://localhost:3000/")
    assert "protected inbox" in local["text"] and "From:" not in local["text"]
    assert "reply_markup" not in local


def _alerts(handler):
    def factory(token, _http):
        return TelegramClient(token, http=httpx2.Client(transport=httpx2.MockTransport(handler)))

    return TelegramAlerts(lambda: TOKEN, "-1001234", LINK, client_factory=factory)


def test_send_message_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx2.Response(200, json={"ok": True, "result": {"message_id": 1}})

    assert _alerts(handler).scam_blocked(protected_name="Margaret", sender_domain="evil.com") is True
    (request,) = seen
    assert request.url.path == f"/bot{TOKEN}/sendMessage"
    body = json.loads(request.content)
    assert body["chat_id"] == "-1001234" and body["parse_mode"] == "HTML"


def test_failed_alert_is_logged_without_the_token(caplog):
    def refuse(request):
        return httpx2.Response(403, json={"ok": False, "description": "Forbidden: bot was kicked from the group chat"})

    def unreachable(request):
        raise httpx2.ConnectError(f"cannot connect to {request.url}")

    with caplog.at_level(logging.DEBUG):
        assert _alerts(refuse).scam_blocked(protected_name="Margaret", sender_domain="evil.com") is False
        assert _alerts(unreachable).scam_blocked(protected_name="Margaret", sender_domain="evil.com") is False
    assert "bot was kicked" in caplog.text
    assert TOKEN not in caplog.text


def test_make_alerts_config():
    base = get_settings()
    off = dataclasses.replace(base, telegram_chat_id=None, telegram_bot_token=TOKEN)
    assert make_alerts(off) is None

    no_token = dataclasses.replace(base, telegram_chat_id="42", telegram_bot_token=None, telegram_provider_name=None)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        make_alerts(no_token)

    on = dataclasses.replace(base, telegram_chat_id="42", telegram_bot_token=TOKEN, telegram_provider_name=None)
    alerts = make_alerts(on)
    assert isinstance(alerts, TelegramAlerts) and alerts.chat_id == "42" and alerts.link == base.telegram_link

    identity = dataclasses.replace(base, telegram_chat_id="42", telegram_provider_name="scamshield-telegram", workload_name=None)
    with pytest.raises(ValueError, match="SCAMSHIELD_WORKLOAD_NAME"):
        make_alerts(identity)
