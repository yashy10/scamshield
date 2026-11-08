"""Compose and send the plain-English warning email."""

from __future__ import annotations

import html
import logging
import re
import sys
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("scamshield.notify")

HEADLINES = {
    "scam": "This email is likely a scam. Don't click its links.",
    "suspicious": "This email looks suspicious. Don't click its links until you're sure it's real.",
}
WHAT_TO_DO = (
    "What to do: delete it, and contact the real company through a phone number or website "
    "you already trust. Don't reply to the email."
)

_URL = re.compile(r"\bhttps?://\S+", re.IGNORECASE)
_DOMAINISH = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def defang(text: str) -> str:
    """Make URLs and domains unclickable: https://evil.com -> hxxps://evil[.]com."""
    text = _URL.sub(lambda m: re.sub(r"^http", "hxxp", m.group(0), flags=re.IGNORECASE), text)
    return _DOMAINISH.sub(lambda m: m.group(0).replace(".", "[.]"), text)


def clean_reasons(reasons: list[str]) -> list[str]:
    cleaned = [re.sub(r"\s+", " ", r).strip()[:300] for r in reasons]
    return [defang(r) for r in cleaned if r]


@dataclass
class Message:
    to: str
    subject: str
    text: str
    html: str


def compose(
    *,
    to: str,
    verdict: str,
    reasons: list[str],
    for_guardian: bool,
    protected_label: str,
    sender_domain: str,
    original_subject: str | None,
) -> Message:
    """Build the warning. The guardian copy never includes the email's subject (verdicts only)."""
    headline = HEADLINES[verdict]
    sender = defang(sender_domain) if sender_domain else "an unknown sender"
    kind = "likely scam" if verdict == "scam" else "suspicious email"

    if for_guardian:
        subject = f"ScamShield: we warned {protected_label} about a {kind}"
        intro = f"ScamShield found a {kind} in {protected_label}'s inbox and sent them this warning."
        identify = f"It came from {sender}."
        footer = (
            "You're getting this because you're their ScamShield guardian. You see the verdict "
            "and reasons only, never the email itself. You may want to check in with them."
        )
    else:
        subject = "ScamShield: likely scam in your inbox" if verdict == "scam" else "ScamShield: please check this email"
        intro = headline
        if original_subject:
            title = defang(re.sub(r"\s+", " ", original_subject).strip()[:120])
            identify = f'The email titled "{title}", from {sender}.'
        else:
            identify = f"The email from {sender}."
        footer = (
            'ScamShield added a "ScamShield" label to this email in Gmail. '
            "It never deletes or moves your email."
        )

    lines = [intro, "", identify, "", "Why:"]
    lines += [f"  - {r}" for r in reasons]
    lines += ["", WHAT_TO_DO, "", footer]
    text = "\n".join(lines)

    e = html.escape
    items = "".join(f"<li style='margin-bottom:6px'>{e(r)}</li>" for r in reasons)
    body_html = (
        "<div style='font-family:Arial,Helvetica,sans-serif;font-size:18px;line-height:1.5;color:#1a1a1a;max-width:600px'>"
        f"<p style='font-size:22px;font-weight:bold;color:#b3261e;margin:0 0 16px'>{e(intro)}</p>"
        f"<p>{e(identify)}</p>"
        f"<p style='margin-bottom:4px'><strong>Why:</strong></p><ul style='margin-top:0'>{items}</ul>"
        f"<p><strong>{e(WHAT_TO_DO)}</strong></p>"
        f"<p style='font-size:14px;color:#555'>{e(footer)}</p>"
        "</div>"
    )
    return Message(to=to, subject=subject, text=text, html=body_html)


class EmailSender(Protocol):
    def send(self, message: Message) -> None: ...


class ConsoleSender:
    """Prints the warning instead of sending it. For local development."""

    def send(self, message: Message) -> None:
        print(f"\n--- [ScamShield console email] To: {message.to}\nSubject: {message.subject}\n\n{message.text}\n---", file=sys.stderr)


class SesSender:
    def __init__(self, from_address: str, region: str, client=None) -> None:
        import boto3

        self.from_address = from_address
        self._client = client or boto3.client("sesv2", region_name=region)

    def send(self, message: Message) -> None:
        self._client.send_email(
            FromEmailAddress=self.from_address,
            Destination={"ToAddresses": [message.to]},
            Content={
                "Simple": {
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": message.text, "Charset": "UTF-8"},
                        "Html": {"Data": message.html, "Charset": "UTF-8"},
                    },
                }
            },
        )
        log.info("SES warning sent")


def make_sender(backend: str, from_address: str | None, region: str) -> EmailSender:
    if backend == "console":
        return ConsoleSender()
    if backend == "ses":
        if not from_address:
            raise ValueError("SCAMSHIELD_SES_FROM must be set to a verified SES address.")
        return SesSender(from_address, region)
    raise ValueError(f"Unknown SCAMSHIELD_EMAIL_BACKEND: {backend!r}")
