"""Sign in with Google (OpenID Connect, authorization code + PKCE) for the dashboard.

Everyone ScamShield protects has a Google account, and guardians usually do too, so the site keeps no
passwords. The sign-in asks only for the person's name and verified email address
(scopes: openid email profile). It is a different, smaller grant than the Gmail connection.

The ID token comes straight from Google's token endpoint over TLS, in exchange for our client secret, so
its signature doesn't need checking here (Google's OpenID Connect guide says the same). Its issuer,
audience, expiry and nonce are still checked.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx2

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
SCOPES = "openid email profile"
CALLBACK_PATH = "/signin/callback"


# What each sign-in problem means, in words a person can act on. The frontend shows these by code.
SIGNIN_MESSAGES = {
    "cancelled": "Sign-in was cancelled. You can try again.",
    "restart": "This sign-in didn’t start in this browser, or it expired. Try again.",
    "google": "Google didn’t confirm the sign-in. Try again in a minute.",
    "wrong_client": "That sign-in wasn’t meant for ScamShield.",
    "expired": "That sign-in expired. Try again.",
    "unverified": "Google hasn’t verified the email address on that account.",
    "not_configured": "Google sign-in isn’t set up on this site yet.",
    "bad_email": "Enter an email address like name@example.com.",
}


class SignInError(Exception):
    """Google didn't confirm who this is. `code` is one of SIGNIN_MESSAGES; the message is safe to show."""

    def __init__(self, code: str) -> None:
        super().__init__(SIGNIN_MESSAGES[code])
        self.code = code


@dataclass(frozen=True)
class Account:
    email: str
    name: str

    def to_session(self) -> dict:
        return {"email": self.email, "name": self.name}

    @classmethod
    def from_session(cls, raw) -> Account | None:
        if not isinstance(raw, dict) or not raw.get("email"):
            return None
        return cls(email=str(raw["email"]).lower(), name=str(raw.get("name") or ""))


@dataclass(frozen=True)
class SignInStart:
    url: str
    state: dict  # kept in the session until Google sends the browser back


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise SignInError("google") from exc


class GoogleSignIn:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, http: httpx2.Client | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._http = http or httpx2.Client(timeout=15)

    def start(self) -> SignInStart:
        state, nonce, verifier = (secrets.token_urlsafe(24) for _ in range(3))
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return SignInStart(f"{AUTH_URL}?{urlencode(params)}", {"state": state, "nonce": nonce, "verifier": verifier})

    def finish(self, saved: dict, params: dict) -> Account:
        if params.get("error"):
            raise SignInError("cancelled")
        if not saved or not params.get("state") or not secrets.compare_digest(saved["state"], params["state"]):
            raise SignInError("restart")
        try:
            resp = self._http.post(TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": params.get("code", ""),
                "code_verifier": saved["verifier"],
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            })
        except httpx2.HTTPError as exc:
            raise SignInError("google") from exc
        if resp.status_code != 200 or "id_token" not in resp.json():
            raise SignInError("google")

        claims = _claims(resp.json()["id_token"])
        if claims.get("iss") not in ISSUERS or claims.get("aud") != self.client_id:
            raise SignInError("wrong_client")
        if float(claims.get("exp", 0)) < time.time() or claims.get("nonce") != saved["nonce"]:
            raise SignInError("expired")
        if not claims.get("email") or claims.get("email_verified") is not True:
            raise SignInError("unverified")
        return Account(email=claims["email"].lower(), name=claims.get("given_name") or claims.get("name") or "")


def load_google_client(secrets_dir: Path) -> tuple[str, str] | None:
    """Client ID and secret of the Google "Web application" client: env on Vercel, the downloaded JSON locally."""
    client_id, client_secret = os.environ.get("SCAMSHIELD_GOOGLE_CLIENT_ID"), os.environ.get("SCAMSHIELD_GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret
    path = secrets_dir / "google_web_client.json"
    if path.exists():
        web = json.loads(path.read_text()).get("web") or {}
        if web.get("client_id") and web.get("client_secret"):
            return web["client_id"], web["client_secret"]
    return None
