"""Minimal Gmail REST client. It takes a bare access token so the same code works with a
locally refreshed token (Phase 1) and with a token from AgentCore Identity (Phase 3).

Deliberately missing: send, trash, delete, and removing labels.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from email.utils import parseaddr

import httpx2

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_EMAIL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_CHARSET_RE = re.compile(r"charset=\"?([\w.-]+)\"?", re.IGNORECASE)
# Red label so it stands out; both values are from Gmail's allowed label palette.
_LABEL_COLOR = {"backgroundColor": "#fb4c2f", "textColor": "#ffffff"}


class GmailError(Exception):
    pass


def validate_email_id(email_id: str) -> str:
    if not _EMAIL_ID_RE.fullmatch(email_id or ""):
        raise GmailError("email_id is not a valid Gmail message id.")
    return email_id


@dataclass
class ParsedEmail:
    email_id: str
    from_address: str
    sender_name: str
    sender_domain: str
    subject: str
    text: str
    html: str


class GmailClient:
    def __init__(self, access_token: str, http: httpx2.Client | None = None) -> None:
        self._http = http or httpx2.Client(timeout=20)
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._http.request(method, f"{GMAIL_API}{path}", headers=self._headers, **kwargs)
        if resp.status_code == 401:
            raise GmailError("Gmail rejected the access token; reconnect Gmail.")
        if resp.status_code == 404:
            raise GmailError("Gmail message or label not found.")
        if resp.status_code >= 400:
            raise GmailError(f"Gmail API error (HTTP {resp.status_code}).")
        return resp.json() if resp.content else {}

    def profile_email(self) -> str:
        return self._request("GET", "/profile")["emailAddress"]

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        data = self._request("GET", "/messages", params={"q": query, "maxResults": max_results})
        return [m["id"] for m in data.get("messages", [])]

    def get_message(self, email_id: str) -> dict:
        validate_email_id(email_id)
        return self._request("GET", f"/messages/{email_id}", params={"format": "full"})

    def get_headers(self, email_id: str, names: list[str]) -> dict[str, str]:
        validate_email_id(email_id)
        data = self._request(
            "GET",
            f"/messages/{email_id}",
            params=[("format", "metadata"), *[("metadataHeaders", n) for n in names]],
        )
        return _header_map(data.get("payload", {}))

    def ensure_label(self, name: str) -> str:
        for label in self._request("GET", "/labels").get("labels", []):
            if label.get("name") == name:
                return label["id"]
        body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        try:
            created = self._request("POST", "/labels", json={**body, "color": _LABEL_COLOR})
        except GmailError:  # Retry without color in case the palette is rejected.
            created = self._request("POST", "/labels", json=body)
        return created["id"]

    def add_label(self, email_id: str, label_id: str) -> None:
        validate_email_id(email_id)
        self._request("POST", f"/messages/{email_id}/modify", json={"addLabelIds": [label_id]})


def _header_map(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    content_type = _header_map(part).get("content-type", "")
    match = _CHARSET_RE.search(content_type)
    charset = match.group(1) if match else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _walk(part: dict, texts: list[str], htmls: list[str]) -> None:
    mime = part.get("mimeType", "")
    if part.get("filename"):  # attachment
        return
    if mime == "text/plain":
        texts.append(_decode_part(part))
    elif mime == "text/html":
        htmls.append(_decode_part(part))
    for child in part.get("parts", []) or []:
        _walk(child, texts, htmls)


def sender_domain_of(from_header: str) -> tuple[str, str]:
    address = parseaddr(from_header)[1].lower()
    domain = address.rsplit("@", 1)[1] if "@" in address else ""
    return address, domain


def parse_message(message: dict) -> ParsedEmail:
    payload = message.get("payload", {})
    headers = _header_map(payload)
    texts: list[str] = []
    htmls: list[str] = []
    _walk(payload, texts, htmls)
    address, domain = sender_domain_of(headers.get("from", ""))
    return ParsedEmail(
        email_id=message["id"],
        from_address=address,
        sender_name=parseaddr(headers.get("from", ""))[0].strip(),
        sender_domain=domain,
        subject=headers.get("subject", ""),
        text="\n".join(texts),
        html="\n".join(htmls),
    )
