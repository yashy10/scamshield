"""Landing page, Google sign-in and the dashboard. Google's token endpoint is faked."""

from __future__ import annotations

import base64
import json
import math
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from scamshield.store import EmailRecord, Invite, UserProfile
from scamshield_web.auth import SIGNIN_MESSAGES, GoogleSignIn
from scamshield_web.dashboard import RING_RADIUS, Person, inbox_view, ring, warned_to

from .test_web import make_client

CLIENT_ID = "test-client.apps.googleusercontent.com"
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def jwt(claims: dict) -> str:
    def enc(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.signature"


class FakeTokenEndpoint:
    """Stands in for https://oauth2.googleapis.com/token."""

    def __init__(self, **claims):
        self.claims = claims
        self.posted = None

    def post(self, url, data):
        self.posted = (url, data)
        claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "exp": time.time() + 300,
                  "email_verified": True, **self.claims}
        if claims.get("nonce") == "FROM_SESSION":
            claims["nonce"] = self.nonce
        body = {"id_token": jwt(claims), "access_token": "ya29.not-used"}
        return type("Resp", (), {"status_code": 200, "json": lambda _self: body})()


def seed(store):
    store.put_user(UserProfile(user_id="margaret-1a2b", email="margaret@gmail.com", guardian_email="alex@example.com",
                               display_name="Margaret", guardian_name="Alex"))
    store.put_user(UserProfile(user_id="someone-else", email="other@gmail.com", guardian_email="carol@example.com",
                               display_name="Pat", guardian_name="Carol"))
    recent = (datetime.now(UTC) - timedelta(days=2)).isoformat(timespec="seconds")
    store.put_email(EmailRecord(user_id="margaret-1a2b", email_id="m1", verdict="scam", labeled=True,
                                reasons=["The link goes to a website registered 3 days ago."], warned_at=recent,
                                warned_recipients=["margaret@gmail.com", "alex@example.com"],
                                sender_name="Chase Security", sender_domain="chase-secure-login.com",
                                subject="Your account is locked", received_at=recent, checked_at=recent))
    store.put_email(EmailRecord(user_id="margaret-1a2b", email_id="m2", verdict="fine", checked_at=recent))
    store.put_email(EmailRecord(user_id="someone-else", email_id="p1", verdict="scam", subject="Pat's private scam",
                                sender_domain="secret.example", checked_at=recent))


def sign_in_with_google(client, endpoint: FakeTokenEndpoint):
    start = client.post("/signin/google")
    assert start.status_code == 303
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["scope"] == ["openid email profile"] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://localhost:8080/signin/callback"]
    endpoint.nonce = query["nonce"][0]
    return client.get("/signin/callback", params={"state": query["state"][0], "code": "auth-code"})


def sub(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


def google(tmp_path, **claims):
    endpoint = FakeTokenEndpoint(nonce="FROM_SESSION", **claims)
    sign_in = GoogleSignIn(CLIENT_ID, "client-secret", "http://localhost:8080/signin/callback", http=endpoint)
    client, store, *_ = make_client(tmp_path, sign_in=sign_in, dev_sign_in=False)
    seed(store)
    return client, store, endpoint


def test_landing_page_has_sign_in_and_sources(tmp_path):
    client, *_ = make_client(tmp_path)
    page = client.get("/").text
    assert 'href="/signin"' in page and "Protect someone" in page
    assert "ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf" in page and "48,064" in page
    assert client.get("/dashboard").headers["location"] == "/signin"


def test_guardian_signs_in_with_google_and_sees_warnings_only(tmp_path):
    client, _, endpoint = google(tmp_path, email="Alex@Example.com", given_name="Alex")
    done = sign_in_with_google(client, endpoint)
    assert done.status_code == 303 and done.headers["location"] == "/dashboard"
    url, data = endpoint.posted
    assert url == "https://oauth2.googleapis.com/token" and data["code"] == "auth-code" and data["code_verifier"]

    page = client.get("/dashboard").text
    assert "Margaret’s inbox" in page and "We caught 1 scam email sent to Margaret" in page
    assert "chase-secure-login.com" in page and "Warning sent to Margaret and you" in page
    assert "Your account is locked" not in page  # guardians don't see subjects
    assert "Pat" not in page and "secret.example" not in page
    # Asking for someone else's inbox falls back to one this account may see.
    other = client.get("/dashboard", params={"person": "someone-else"}).text
    assert "secret.example" not in other and "Margaret’s inbox" in other

    assert client.post("/signout").status_code == 303
    assert client.get("/dashboard").headers["location"] == "/signin"


def test_protected_person_sees_subjects(tmp_path):
    client, _, endpoint = google(tmp_path, email="margaret@gmail.com", given_name="Margaret")
    sign_in_with_google(client, endpoint)
    page = client.get("/dashboard").text
    assert "Your inbox" in page and "Your account is locked" in page and "Warning sent to you and Alex" in page


def test_stranger_sees_the_empty_state(tmp_path):
    client, _, endpoint = google(tmp_path, email="nobody@gmail.com")
    sign_in_with_google(client, endpoint)
    page = client.get("/dashboard").text
    assert "No one is protected with this account yet" in page and "secret.example" not in page


def test_google_sign_in_is_checked(tmp_path):
    for n, (claims, code) in enumerate([({"email": "alex@example.com", "aud": "someone-elses-client"}, "wrong_client"),
                                        ({"email": "alex@example.com", "email_verified": False}, "unverified"),
                                        ({"email": "alex@example.com", "exp": time.time() - 10}, "expired")]):
        client, _, endpoint = google(sub(tmp_path, f"case{n}"), **claims)
        resp = sign_in_with_google(client, endpoint)
        assert resp.status_code == 303 and resp.headers["location"] == f"/signin?error={code}"
        assert client.get("/dashboard").headers["location"] == "/signin"
        assert SIGNIN_MESSAGES[code] in client.get(resp.headers["location"]).text

    client, _, endpoint = google(sub(tmp_path, "state"), email="alex@example.com")
    client.post("/signin/google")
    forged = client.get("/signin/callback", params={"state": "not-the-one-we-sent", "code": "x"})
    assert forged.headers["location"] == "/signin?error=restart" and endpoint.posted is None
    cancelled = client.get("/signin/callback", params={"error": "access_denied"})
    assert cancelled.headers["location"] == "/signin?error=cancelled"


def test_sign_in_not_configured(tmp_path):
    client, *_ = make_client(tmp_path)
    assert client.post("/signin/google").headers["location"] == "/signin?error=not_configured"
    assert client.get("/signin/callback").headers["location"] == "/signin?error=not_configured"


def test_dev_sign_in_only_on_localhost(tmp_path, monkeypatch):
    client, store, *_ = make_client(sub(tmp_path, "local"), dev_sign_in=True)
    seed(store)
    assert "Local preview" in client.get("/signin").text
    assert client.post("/signin/dev", data={"email": "alex@example.com"}).headers["location"] == "/dashboard"
    assert "Margaret’s inbox" in client.get("/dashboard").text
    assert client.post("/signin/dev", data={"email": "nope"}).headers["location"] == "/signin?error=bad_email"

    monkeypatch.setenv("SCAMSHIELD_WEB_SECRET", "x" * 32)
    hosted, *_ = make_client(sub(tmp_path, "vercel"), dev_sign_in=True, on_vercel=True)
    assert "Local preview" not in hosted.get("/signin").text
    assert hosted.post("/signin/dev", data={"email": "alex@example.com"}).status_code == 404


def test_connecting_gmail_signs_the_person_in(tmp_path):
    client, *_ = make_client(tmp_path)
    token = client.post("/signup", data={"guardian_name": "Alex", "guardian_email": "alex@example.com",
                                         "protected_name": "Margaret", "agreed": "yes"}).headers["location"].rsplit("/", 1)[1]
    client.post(f"/join/{token}/connect")
    client.get("/", params={"code": "auth-code", "state": "state-123"})
    page = client.get("/dashboard").text
    assert "Your inbox" in page and "Waiting for the first check" in page


def test_waiting_invites_show_for_the_guardian(tmp_path):
    client, store, *_ = make_client(tmp_path, dev_sign_in=True)
    store.put_invite(Invite(token="tok-12345678", user_id="june-1", protected_name="June",
                            guardian_name="Alex", guardian_email="alex@example.com"))
    client.post("/signin/dev", data={"email": "alex@example.com"})
    page = client.get("/dashboard").text
    assert "June hasn’t connected their Gmail yet" in page and "/join/tok-12345678" in page


def test_ring_and_status(tmp_path):
    circumference = 2 * math.pi * RING_RADIUS
    segments = ring([("scam", "Scams", 1), ("suspicious", "Careful", 0), ("safe", "Safe", 999)])
    assert [s.key for s in segments] == ["scam", "safe"]
    assert segments[0].dash > 0.02 * circumference  # one scam in a thousand is still visible
    assert abs(sum(s.dash for s in segments) + 2 * 3.0 - circumference) < 0.01
    assert ring([("safe", "Safe", 5)])[0].dash == circumference  # a lone segment is a full circle, no gap
    assert ring([("safe", "Safe", 0)])[0].key == "empty"

    _, store, *_ = make_client(tmp_path)
    profile = UserProfile(user_id="u1", email="me@gmail.com", guardian_email="kid@example.com", display_name="Me")
    store.put_user(profile)
    person = Person(profile, "self")
    assert inbox_view(store, person, now=NOW).status == "waiting"
    old = (NOW - timedelta(days=40)).isoformat()
    store.put_email(EmailRecord(user_id="u1", email_id="a", verdict="scam", checked_at=old, received_at=old))
    store.put_email(EmailRecord(user_id="u1", email_id="b", verdict="fine", checked_at=NOW.isoformat()))
    assert inbox_view(store, person, "30", now=NOW).status == "safe"  # the scam is older than 30 days
    view = inbox_view(store, person, "all", now=NOW)
    assert (view.status, view.checked, len(view.scams)) == ("scam", 2, 1)
    store.put_email(EmailRecord(user_id="u1", email_id="c", verdict="suspicious", checked_at=NOW.isoformat()))
    assert inbox_view(store, person, "7", now=NOW).status == "careful"

    record = EmailRecord(user_id="u1", email_id="a", verdict="scam", warned_recipients=["me@gmail.com", "kid@example.com"])
    assert warned_to(record, person) == "you and your family member"
    assert warned_to(record, Person(profile, "guardian")) == "Me and you"
