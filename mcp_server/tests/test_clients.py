"""HTTP clients against mocked transports (no network)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from scamshield.credentials import CredentialError, LocalGmailTokenProvider
from scamshield.gmail import GmailClient, GmailError, parse_message
from scamshield.rdap import RdapClient
from scamshield.safebrowsing import SafeBrowsingClient

from scamshield.testing import gmail_message

BOOTSTRAP = {"services": [[["com", "net"], ["https://rdap.verisign.com/com/v1/"]]]}


def rdap_http(registered: str | None, status: int = 200) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == "data.iana.org":
            return httpx2.Response(200, json=BOOTSTRAP)
        assert request.url.path == "/com/v1/domain/chase-secure-login.com"
        if status != 200:
            return httpx2.Response(status)
        events = [{"eventAction": "registration", "eventDate": registered}] if registered else []
        return httpx2.Response(200, json={"events": events})

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_rdap_age():
    client = RdapClient(http=rdap_http("2026-11-04T10:00:00Z"))
    result = client.lookup("chase-secure-login.com", now=datetime(2026, 11, 7, 12, tzinfo=UTC))
    assert result.registered_date == "2026-11-04"
    assert result.age_days == 3
    assert result.lookup_status == "ok"


def test_rdap_not_found_and_unknown_tld():
    assert RdapClient(http=rdap_http(None, status=404)).lookup("chase-secure-login.com").lookup_status == "not_found"
    assert RdapClient(http=rdap_http(None)).lookup("example.zz").lookup_status == "no_rdap_server"


def test_safe_browsing_flagged_prefers_phishing():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["x-goog-api-key"] == "k"
        assert "key" not in request.url.params  # never in the URL (URLs get logged)
        body = json.loads(request.content)
        assert body["threatInfo"]["threatEntries"] == [{"url": "http://bad.example/"}]
        return httpx2.Response(200, json={"matches": [{"threatType": "MALWARE"}, {"threatType": "SOCIAL_ENGINEERING"}]})

    result = SafeBrowsingClient("k", http=httpx2.Client(transport=httpx2.MockTransport(handler))).check("http://bad.example/")
    assert result.flagged and result.threat_type == "SOCIAL_ENGINEERING"


def test_safe_browsing_clean():
    http = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json={})))
    result = SafeBrowsingClient("k", http=http).check("https://example.com/")
    assert result.flagged is False and result.threat_type is None


def test_parse_message_multipart():
    msg = gmail_message(
        "18c0ffee12345678",
        sender='"Chase Bank" <alerts@Chase-Secure-Login.com>',
        subject="Account locked",
        text="Click https://chase-secure-login.com/x",
        html="<a href='https://chase-secure-login.com/x'>here</a>",
    )
    parsed = parse_message(msg)
    assert parsed.sender_domain == "chase-secure-login.com"
    assert parsed.subject == "Account locked"
    assert "https://chase-secure-login.com/x" in parsed.text
    assert "href" in parsed.html


def test_gmail_client_never_removes_labels():
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.url.path.endswith("/labels") and request.method == "GET":
            return httpx2.Response(200, json={"labels": [{"id": "Label_9", "name": "ScamShield"}]})
        return httpx2.Response(200, json={})

    gmail = GmailClient("t", http=httpx2.Client(transport=httpx2.MockTransport(handler)))
    gmail.add_label("18c0ffee12345678", gmail.ensure_label("ScamShield"))
    method, path, content = calls[-1]
    assert (method, path) == ("POST", "/gmail/v1/users/me/messages/18c0ffee12345678/modify")
    assert json.loads(content) == {"addLabelIds": ["Label_9"]}


def test_gmail_rejects_bad_ids():
    gmail = GmailClient("t", http=httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200))))
    with pytest.raises(GmailError):
        gmail.add_label("../../etc", "Label_1")


def test_local_token_refresh(tmp_path: Path):
    path = tmp_path / "gmail_token_grandma.json"
    path.write_text(json.dumps({
        "token": "old", "expiry": "2020-01-01T00:00:00Z", "refresh_token": "r",
        "client_id": "c", "client_secret": "s", "token_uri": "https://oauth2.googleapis.com/token",
    }))

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert b"grant_type=refresh_token" in request.content
        return httpx2.Response(200, json={"access_token": "new", "expires_in": 3600})

    provider = LocalGmailTokenProvider(tmp_path, http=httpx2.Client(transport=httpx2.MockTransport(handler)))
    assert provider.access_token("grandma") == "new"
    assert json.loads(path.read_text())["token"] == "new"
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert provider.access_token("grandma") == "new"  # cached, no second refresh needed


def test_token_provider_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(CredentialError):
        LocalGmailTokenProvider(tmp_path).access_token("../secrets")
