"""The sign-up flow end to end: guardian signs up, invite, join page, Google consent, protected.
Google and AWS are faked: a stand-in OAuth flow (local mode) and a stubbed boto3 client (Identity mode)."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import boto3
import pytest
from botocore.stub import Stubber
from starlette.testclient import TestClient

from scamshield.config import get_settings
from scamshield.credentials import GMAIL_SCOPES
from scamshield.store import LocalStore
from scamshield_web.app import SiteConfig, create_app

GUARDIAN = {"guardian_name": "Alex", "guardian_email": "Alex@Example.com", "protected_name": "Margaret", "agreed": "yes"}


class FakeFlow:
    """Stands in for google_auth_oauthlib's Flow."""

    def __init__(self, state=None):
        self.state = state or "state-123"
        self.code_verifier = "verifier-xyz"
        self.fetched_with = None
        self.credentials = None

    def authorization_url(self, **params):
        assert params == {"access_type": "offline", "prompt": "consent"}
        return f"https://accounts.google.com/o/oauth2/auth?state={self.state}", self.state

    def fetch_token(self, code):
        self.fetched_with = (code, self.code_verifier)
        token = "ya29.local-token"
        self.credentials = type("Creds", (), {"token": token, "to_json": lambda _self: json.dumps({"token": token})})()


class FakeGmail:
    def __init__(self, token):
        self.token = token

    def profile_email(self):
        return "Margaret.Demo@gmail.com"


class FakeScans:
    def __init__(self):
        self.states, self.started = {}, []

    def start(self, user_id):
        self.started.append(user_id)


def make_client(tmp_path: Path, backend="local", consent_kwargs=None, **site_kwargs):
    settings = dataclasses.replace(
        get_settings(), credentials_backend=backend, secrets_dir=tmp_path / "secrets",
        workload_name="mcp-runtime-id", google_provider_name="ScamShield_default_GoogleGmail",
        local_store_path=tmp_path / "store.json", store_backend="local",
    )
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "google_oauth_client.json").write_text("{}")
    store, scans = LocalStore(settings.local_store_path), FakeScans()
    cfg = SiteConfig(settings=settings, store=store, base_url="http://localhost:8080",
                     consent_kwargs=consent_kwargs if consent_kwargs is not None else {"flow_factory": FakeFlow},
                     gmail_factory=FakeGmail, scans=scans, **{"on_vercel": False, **site_kwargs})
    return TestClient(create_app(cfg), follow_redirects=False), store, scans, settings


def sign_up(client) -> str:
    resp = client.post("/signup", data=GUARDIAN)
    assert resp.status_code == 303
    return resp.headers["location"].rsplit("/", 1)[1]


def test_home_and_signup_validation(tmp_path):
    client, *_ = make_client(tmp_path)
    assert "Protect someone" in client.get("/").text
    resp = client.post("/signup", data={"guardian_name": "", "guardian_email": "nope", "protected_name": ""})
    assert resp.status_code == 400
    for msg in ("Enter your name.", "Enter an email address", "Enter their first name.", "once they"):
        assert msg in resp.text


def test_full_signup_local_google(tmp_path):
    client, store, scans, settings = make_client(tmp_path)
    token = sign_up(client)

    invite_page = client.get(f"/invite/{token}").text
    assert f"http://localhost:8080/join/{token}" in invite_page

    join = client.get(f"/join/{token}").text
    assert "Hi Margaret" in join and "Alex sees warnings only" in join and "Connect my Gmail" in join

    start = client.post(f"/join/{token}/connect")
    assert start.status_code == 303 and start.headers["location"].startswith("https://accounts.google.com/")

    # Google sends the browser back to the site root (desktop-client loopback style).
    done = client.get("/", params={"code": "auth-code", "state": "state-123"})
    assert done.status_code == 303 and done.headers["location"] == f"/protected/{token}"

    invite = store.get_invite(token)
    profile = store.get_user(invite.user_id)
    assert (profile.email, profile.guardian_email, profile.display_name) == (
        "margaret.demo@gmail.com", "alex@example.com", "Margaret")
    assert re.fullmatch(r"margaret-[0-9a-f]{4}", invite.user_id)
    token_file = settings.secrets_dir / f"gmail_token_{invite.user_id}.json"
    assert json.loads(token_file.read_text())["token"] == "ya29.local-token"

    assert "You’re protected, Margaret" in client.get(f"/protected/{token}").text
    # The invite is used: opening it again goes straight to the protected page.
    assert client.get(f"/join/{token}").headers["location"] == f"/protected/{token}"

    people = client.get("/people").text
    assert "margaret.demo@gmail.com" in people and "Scan now" in people
    assert client.post(f"/people/{invite.user_id}/scan").status_code == 303
    assert scans.started == [invite.user_id]


def test_consent_callback_must_match_this_browser(tmp_path):
    client, store, *_ = make_client(tmp_path)
    token = sign_up(client)
    client.post(f"/join/{token}/connect")
    wrong = client.get("/", params={"code": "c", "state": "someone-elses-state"})
    assert wrong.status_code == 303
    assert wrong.headers["location"] == f"/connect/problem?error=not_connected&token={token}"
    assert store.get_invite(token).connected_at is None
    problem = client.get(wrong.headers["location"]).text
    assert "Gmail isn’t connected yet" in problem and f'href="/join/{token}"' in problem

    stranger = TestClient(client.app, follow_redirects=False)  # no session cookie at all
    restart = stranger.get("/", params={"code": "c", "state": "state-123"})
    assert restart.headers["location"] == "/connect/problem?error=restart"
    assert "Start again" in stranger.get(restart.headers["location"]).text


def test_cancelled_google_sign_in(tmp_path):
    client, store, *_ = make_client(tmp_path)
    token = sign_up(client)
    client.post(f"/join/{token}/connect")
    resp = client.get("/", params={"error": "access_denied", "state": "state-123"})
    assert resp.headers["location"] == f"/connect/problem?error=not_connected&token={token}"
    assert "cancelled" in client.get(resp.headers["location"]).text and store.get_invite(token).connected_at is None


def test_bad_invite_links(tmp_path):
    client, *_ = make_client(tmp_path)
    assert client.get("/join/not-a-real-token").status_code == 404
    assert client.get("/join/../../etc").status_code == 404
    assert client.post("/join/not-a-real-token/connect").headers["location"] == "/connect/problem?error=bad_invite"
    assert client.post("/people/nobody/scan").status_code == 303  # unknown users are ignored


def test_missing_google_client_file_is_explained(tmp_path):
    client, *_ , settings = make_client(tmp_path)
    (settings.secrets_dir / "google_oauth_client.json").unlink()
    token = sign_up(client)
    resp = client.post(f"/join/{token}/connect")
    assert resp.headers["location"] == f"/connect/problem?error=unavailable&token={token}"
    assert "can’t be connected right now" in client.get(resp.headers["location"]).text


def test_full_signup_agentcore_identity(tmp_path):
    agentcore = boto3.client("bedrock-agentcore", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    with Stubber(agentcore) as stub:
        client, store, *_ = make_client(tmp_path, backend="agentcore", consent_kwargs={"client": agentcore})
        token = sign_up(client)
        user_id = store.get_invite(token).user_id

        stub.add_response("get_workload_access_token_for_user_id", {"workloadAccessToken": "wat"},
                          {"workloadName": "mcp-runtime-id", "userId": user_id})
        stub.add_response(
            "get_resource_oauth2_token",
            {"authorizationUrl": "https://accounts.google.com/o/oauth2/auth?x=1", "sessionUri": "urn:session:1"},
            {"workloadIdentityToken": "wat", "resourceCredentialProviderName": "ScamShield_default_GoogleGmail",
             "scopes": GMAIL_SCOPES, "oauth2Flow": "USER_FEDERATION",
             "resourceOauth2ReturnUrl": "http://localhost:8080/connect/callback", "forceAuthentication": False,
             "customParameters": {"access_type": "offline", "prompt": "consent"}},
        )
        start = client.post(f"/join/{token}/connect")
        assert start.headers["location"] == "https://accounts.google.com/o/oauth2/auth?x=1"

        stub.add_response("complete_resource_token_auth", {},
                          {"userIdentifier": {"userId": user_id}, "sessionUri": "urn:session:1"})
        stub.add_response("get_workload_access_token_for_user_id", {"workloadAccessToken": "wat2"})
        stub.add_response(
            "get_resource_oauth2_token", {"accessToken": "ya29.from-vault"},
            # Fetching the stored token must repeat the return URL and the consent's custom parameters.
            {"workloadIdentityToken": "wat2", "resourceCredentialProviderName": "ScamShield_default_GoogleGmail",
             "scopes": GMAIL_SCOPES, "oauth2Flow": "USER_FEDERATION",
             "resourceOauth2ReturnUrl": "http://localhost:8080/connect/callback",
             "customParameters": {"access_type": "offline", "prompt": "consent"}},
        )
        done = client.get("/connect/callback", params={"session_id": "urn:session:1"})
        assert done.headers["location"] == f"/protected/{token}"
        assert store.get_user(user_id).email == "margaret.demo@gmail.com"
        # Identity mode never writes a token file.
        assert not list((tmp_path / "secrets").glob("gmail_token_*"))


def test_identity_callback_for_another_session_is_refused(tmp_path):
    agentcore = boto3.client("bedrock-agentcore", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    with Stubber(agentcore) as stub:
        client, store, *_ = make_client(tmp_path, backend="agentcore", consent_kwargs={"client": agentcore})
        token = sign_up(client)
        stub.add_response("get_workload_access_token_for_user_id", {"workloadAccessToken": "wat"})
        stub.add_response("get_resource_oauth2_token", {"authorizationUrl": "https://g/x", "sessionUri": "urn:session:mine"})
        client.post(f"/join/{token}/connect")
        resp = client.get("/connect/callback", params={"session_id": "urn:session:someone-else"})
        assert resp.headers["location"] == f"/connect/problem?error=not_connected&token={token}"
        assert store.get_invite(token).connected_at is None


def test_people_page_password(tmp_path, monkeypatch):
    import base64

    monkeypatch.setenv("SCAMSHIELD_WEB_SECRET", "test-secret")
    client, *_ = make_client(tmp_path, admin_password="s3cret", on_vercel=True)
    assert client.get("/people").status_code == 401
    assert client.post("/people/someone/scan").status_code == 401
    good = base64.b64encode(b"admin:s3cret").decode()
    bad = base64.b64encode(b"admin:nope").decode()
    assert client.get("/people", headers={"Authorization": f"Basic {bad}"}).status_code == 401
    assert client.get("/people", headers={"Authorization": f"Basic {good}"}).status_code == 200


def test_people_page_hidden_on_vercel_without_password(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMSHIELD_WEB_SECRET", "test-secret")
    client, *_ = make_client(tmp_path, admin_password="", on_vercel=True)
    assert client.get("/people").status_code == 404
    assert client.get("/").status_code == 200  # the public pages still work


def test_vercel_requires_a_shared_session_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("SCAMSHIELD_WEB_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SCAMSHIELD_WEB_SECRET"):
        make_client(tmp_path, on_vercel=True)


def test_detached_scan_starts_the_deployed_agent(monkeypatch):
    from scamshield_web.scans import ScanRunner

    calls = []
    runner = ScanRunner("arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/agent-x", detached=True)
    monkeypatch.setattr(runner, "_invoke_deployed", lambda user_id, wait=True: calls.append((user_id, wait)) or {})
    runner.start("walter-1")
    assert calls == [("walter-1", False)] and runner.states["walter-1"].status == "started"

    no_agent = ScanRunner(None, detached=True)
    no_agent.start("walter-1")
    assert no_agent.states["walter-1"].status == "error" and "SCAMSHIELD_AGENT_ARN" in no_agent.states["walter-1"].error


def test_aws_credential_modes(monkeypatch):
    import boto3

    from scamshield_web import aws

    for name in ("SCAMSHIELD_AWS_ROLE_ARN", "SCAMSHIELD_AWS_ACCESS_KEY_ID", "SCAMSHIELD_AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert aws.configure_aws("us-east-1") == "default"

    monkeypatch.setenv("SCAMSHIELD_AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("SCAMSHIELD_AWS_SECRET_ACCESS_KEY", "secret")
    assert aws.configure_aws("us-east-1") == "keys"
    assert boto3.DEFAULT_SESSION.get_credentials().access_key == "AKIDEXAMPLE"

    monkeypatch.setenv("SCAMSHIELD_AWS_ROLE_ARN", "arn:aws:iam::111111111111:role/scamshield-vercel")
    assert aws.configure_aws("us-east-1") == "oidc"
    creds = boto3.DEFAULT_SESSION.get_credentials()
    assert creds.method == "assume-role-with-web-identity"
    assert boto3.DEFAULT_SESSION.region_name == "us-east-1"

    aws.remember_oidc_token("header-token")
    assert aws._load_oidc_token() == "header-token"
    boto3.setup_default_session()  # leave a clean default session for other tests
