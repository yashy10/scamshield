"""Connecting a protected person's Gmail, shared by the sign-up web app and the CLI scripts.

Two consent flows, picked by SCAMSHIELD_CREDENTIALS (same switch as the MCP server):

local (Phase 1): Google's consent screen with our own OAuth client (.local/secrets/google_oauth_client.json);
    the token is saved to .local/secrets/gmail_token_<user_id>.json.
agentcore (Phase 3): AgentCore Identity runs the consent and keeps the token in its vault. Our side only
    hosts the session-binding callback and calls CompleteResourceTokenAuth.

Both are two steps: start() returns the URL to send the browser to plus a small `state` dict the caller
keeps in the user's own browser session; finish() checks that state against the callback and returns
an access token (used once, to read the account's address).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .credentials import (
    GMAIL_SCOPES,
    AgentCoreGmailTokenProvider,
    LocalGmailTokenProvider,
    validate_user_id,
    write_secret,
)
from .store import Invite, Store, UserProfile, now_iso

CONSENT_PARAMS = {"access_type": "offline", "prompt": "consent"}  # a refresh token on every (re)consent


class ConsentError(Exception):
    """The consent flow can't be completed (cancelled, expired, or not this browser's flow)."""


@dataclass
class ConsentStart:
    authorization_url: str | None  # None: already connected, call finish() straight away
    state: dict[str, Any] = field(default_factory=dict)


class LocalGoogleConsent:
    """Phase 1: our own Google OAuth client; the token lands in the local secrets folder."""

    def __init__(self, settings: Settings, redirect_uri: str, flow_factory=None) -> None:
        self.settings = settings
        self.redirect_uri = redirect_uri
        self.client_file = settings.secrets_dir / "google_oauth_client.json"
        self._flow_factory = flow_factory

    def _flow(self, state: str | None = None):
        if not self.client_file.exists():
            raise ConsentError(
                f"Google sign-in isn’t set up yet: save the OAuth client file to {self.client_file}."
            )
        if self._flow_factory:
            return self._flow_factory(state=state)
        from google_auth_oauthlib.flow import Flow

        return Flow.from_client_secrets_file(
            str(self.client_file), scopes=GMAIL_SCOPES, redirect_uri=self.redirect_uri, state=state
        )

    def start(self, user_id: str) -> ConsentStart:
        validate_user_id(user_id)
        flow = self._flow()
        url, state = flow.authorization_url(**CONSENT_PARAMS)
        return ConsentStart(url, {"state": state, "code_verifier": getattr(flow, "code_verifier", None)})

    def finish(self, user_id: str, saved: dict[str, Any], params: dict[str, str]) -> str:
        if params.get("error"):
            raise ConsentError("Google sign-in was cancelled, so Gmail wasn’t connected.")
        if not params.get("code") or params.get("state") != saved.get("state"):
            raise ConsentError("This sign-in doesn’t match the one started in this browser. Start again.")
        flow = self._flow(state=saved["state"])
        if saved.get("code_verifier"):
            flow.code_verifier = saved["code_verifier"]
        flow.fetch_token(code=params["code"])
        write_secret(LocalGmailTokenProvider(self.settings.secrets_dir).token_path(user_id), flow.credentials.to_json())
        return flow.credentials.token


class IdentityConsent:
    """Phase 3: AgentCore Identity runs Google's consent; the token stays in its vault."""

    def __init__(self, settings: Settings, return_url: str, client=None) -> None:
        if not settings.workload_name:
            raise ConsentError("SCAMSHIELD_WORKLOAD_NAME (the MCP runtime's workload identity) must be set.")
        import boto3

        self.settings = settings
        self.return_url = return_url
        self._client = client or boto3.client("bedrock-agentcore", region_name=settings.aws_region)

    def start(self, user_id: str, force: bool = False) -> ConsentStart:
        validate_user_id(user_id)
        workload_token = self._client.get_workload_access_token_for_user_id(
            workloadName=self.settings.workload_name, userId=user_id
        )["workloadAccessToken"]
        resp = self._client.get_resource_oauth2_token(
            workloadIdentityToken=workload_token,
            resourceCredentialProviderName=self.settings.google_provider_name,
            scopes=GMAIL_SCOPES,
            oauth2Flow="USER_FEDERATION",
            resourceOauth2ReturnUrl=self.return_url,
            forceAuthentication=force,
            customParameters=CONSENT_PARAMS,
        )
        if resp.get("accessToken"):
            return ConsentStart(None)
        return ConsentStart(resp["authorizationUrl"], {"session_uri": resp.get("sessionUri")})

    def finish(self, user_id: str, saved: dict[str, Any], params: dict[str, str]) -> str:
        session_id = params.get("session_id")
        if session_id:
            # Session binding: only complete the consent this browser started.
            if saved.get("session_uri") and session_id != saved["session_uri"]:
                raise ConsentError("This sign-in doesn’t match the one started in this browser. Start again.")
            self._client.complete_resource_token_auth(userIdentifier={"userId": user_id}, sessionUri=session_id)
        provider = AgentCoreGmailTokenProvider(
            self.settings.workload_name, self.settings.google_provider_name, self.settings.aws_region, client=self._client
        )
        return provider.access_token(user_id)


def make_consent(settings: Settings, base_url: str, **kwargs):
    """The consent flow for this deployment. Local mode returns to the site root, like Google's
    desktop-app loopback flow; Identity mode returns to /connect/callback (register that URL on the
    MCP runtime's workload identity)."""
    base = base_url.rstrip("/")
    if settings.credentials_backend == "agentcore":
        return IdentityConsent(settings, f"{base}/connect/callback", **kwargs)
    return LocalGoogleConsent(settings, f"{base}/", **kwargs)


def complete_signup(store: Store, invite: Invite, gmail_address: str) -> UserProfile:
    """Link the connected Gmail to the guardian, and mark the invite used."""
    profile = UserProfile(
        user_id=invite.user_id,
        email=gmail_address.strip().lower(),
        guardian_email=invite.guardian_email,
        display_name=invite.protected_name,
        guardian_name=invite.guardian_name,
    )
    store.put_user(profile)
    invite.connected_at, invite.connected_email = now_iso(), profile.email
    store.put_invite(invite)
    return profile
