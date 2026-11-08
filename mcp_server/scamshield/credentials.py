"""Where the tools get their secrets. SCAMSHIELD_CREDENTIALS picks the pair:

local (Phase 1): a Gmail OAuth token saved by scripts/connect_gmail.py, and the
    Safe Browsing key from an environment variable.
agentcore (Phase 3): both come from AgentCore Identity at call time. Nothing is stored
    by this code and nothing reaches the model.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx2

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
# Sent on the consent AND on every later token fetch: AgentCore Identity only returns the stored token
# when the custom parameters match the ones the consent used (otherwise it starts a new consent).
GMAIL_CONSENT_PARAMS = {"access_type": "offline", "prompt": "consent"}
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class CredentialError(Exception):
    """A credential is missing or could not be refreshed."""


def validate_user_id(user_id: str) -> str:
    if not _USER_ID_RE.fullmatch(user_id or ""):
        raise CredentialError("user_id must be 1-64 characters: letters, digits, '-' or '_'.")
    return user_id


class GmailTokenProvider(Protocol):
    def access_token(self, user_id: str) -> str: ...


class LocalGmailTokenProvider:
    """Reads <secrets_dir>/gmail_token_<user_id>.json (google-auth 'authorized user' format) and refreshes it."""

    def __init__(self, secrets_dir: Path, http: httpx2.Client | None = None) -> None:
        self.secrets_dir = secrets_dir
        self._http = http or httpx2.Client(timeout=15)
        self._lock = threading.Lock()

    def token_path(self, user_id: str) -> Path:
        return self.secrets_dir / f"gmail_token_{validate_user_id(user_id)}.json"

    def access_token(self, user_id: str) -> str:
        path = self.token_path(user_id)
        if not path.exists():
            raise CredentialError(
                f"Gmail is not connected for user '{user_id}'. "
                f"Run: uv run scripts/connect_gmail.py --user-id {user_id}"
            )
        with self._lock:
            data = json.loads(path.read_text())
            if self._still_valid(data):
                return data["token"]
            return self._refresh(path, data)

    @staticmethod
    def _still_valid(data: dict) -> bool:
        token, expiry = data.get("token"), data.get("expiry")
        if not token or not expiry:
            return False
        expires_at = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at - datetime.now(UTC) > timedelta(minutes=2)

    def _refresh(self, path: Path, data: dict) -> str:
        required = ("refresh_token", "client_id", "client_secret")
        if any(not data.get(k) for k in required):
            raise CredentialError(f"Saved Gmail token at {path.name} cannot be refreshed; reconnect Gmail.")
        resp = self._http.post(
            data.get("token_uri") or _GOOGLE_TOKEN_URI,
            data={
                "grant_type": "refresh_token",
                "refresh_token": data["refresh_token"],
                "client_id": data["client_id"],
                "client_secret": data["client_secret"],
            },
        )
        if resp.status_code != 200:
            # Testing-mode Google apps expire refresh tokens after 7 days.
            raise CredentialError(
                f"Google refused the Gmail token refresh (HTTP {resp.status_code}). Reconnect Gmail."
            )
        body = resp.json()
        data["token"] = body["access_token"]
        expires_at = datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 3600)))
        data["expiry"] = expires_at.isoformat().replace("+00:00", "Z")
        write_secret(path, json.dumps(data))
        return data["token"]


class ApiKeyProvider(Protocol):
    def safe_browsing_key(self) -> str: ...


class EnvApiKeyProvider:
    def __init__(self, key: str | None) -> None:
        self._key = key

    def safe_browsing_key(self) -> str:
        if not self._key:
            raise CredentialError("SAFE_BROWSING_API_KEY is not set.")
        return self._key


class AgentCoreGmailTokenProvider:
    """Phase 3: the user's Gmail token comes from the AgentCore Identity token vault.

    The vault is keyed by (workload identity, user id). The sign-up site (or
    `scripts/connect_gmail_identity.py`) puts the token there through Google's consent screen; Identity
    refreshes it with the stored refresh token. Policy at the Gateway pins `user_id` to the caller, so a
    tool can't ask for someone else's token.

    AgentCore requires a return URL registered on the workload identity on every USER_FEDERATION call,
    even when the token is already stored, and the same custom parameters as the consent.
    """

    def __init__(self, workload_name: str, provider_name: str, region: str, return_url: str, client=None) -> None:
        import boto3

        self.workload_name = workload_name
        self.provider_name = provider_name
        self.return_url = return_url
        self._client = client or boto3.client("bedrock-agentcore", region_name=region)

    def access_token(self, user_id: str) -> str:
        from botocore.exceptions import ClientError

        validate_user_id(user_id)
        try:
            workload_token = self._client.get_workload_access_token_for_user_id(
                workloadName=self.workload_name, userId=user_id
            )["workloadAccessToken"]
            resp = self._client.get_resource_oauth2_token(
                workloadIdentityToken=workload_token,
                resourceCredentialProviderName=self.provider_name,
                scopes=GMAIL_SCOPES,
                oauth2Flow="USER_FEDERATION",
                resourceOauth2ReturnUrl=self.return_url,
                customParameters=GMAIL_CONSENT_PARAMS,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Error")
            raise CredentialError(f"AgentCore Identity refused the Gmail token request ({code}).") from exc
        token = resp.get("accessToken")
        if not token:
            # Identity answered with a consent URL instead: the user hasn't connected Gmail yet.
            # The URL is deliberately not passed on; consent only happens through the connect script.
            raise CredentialError(
                f"Gmail is not connected for user '{user_id}'. "
                f"Run: uv run scripts/connect_gmail_identity.py --user-id {user_id}"
            )
        return token


class AgentCoreApiKeyProvider:
    """Phase 3: an API key from an AgentCore Identity API-key credential provider: the Safe Browsing key,
    or the Telegram bot token (`what` names it in errors)."""

    _TTL = timedelta(minutes=10)

    def __init__(
        self, workload_name: str, provider_name: str, region: str, client=None, what: str = "Safe Browsing key"
    ) -> None:
        import boto3

        self.workload_name = workload_name
        self.provider_name = provider_name
        self.what = what
        self._client = client or boto3.client("bedrock-agentcore", region_name=region)
        self._cached: tuple[str, datetime] | None = None
        self._lock = threading.Lock()

    def safe_browsing_key(self) -> str:
        return self.api_key()

    def api_key(self) -> str:
        from botocore.exceptions import ClientError

        with self._lock:
            if self._cached and datetime.now(UTC) - self._cached[1] < self._TTL:
                return self._cached[0]
            try:
                workload_token = self._client.get_workload_access_token(workloadName=self.workload_name)[
                    "workloadAccessToken"
                ]
                key = self._client.get_resource_api_key(
                    workloadIdentityToken=workload_token, resourceCredentialProviderName=self.provider_name
                )["apiKey"]
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "Error")
                raise CredentialError(f"AgentCore Identity refused the {self.what} request ({code}).") from exc
            self._cached = (key, datetime.now(UTC))
            return key


def write_secret(path: Path, content: str) -> None:
    """Write a file readable only by the current user."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    os.chmod(path, 0o600)
