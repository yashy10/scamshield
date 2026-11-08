"""AWS credentials for the sign-up site, set once as boto3's default session.

SCAMSHIELD_AWS_ROLE_ARN (on Vercel): assume that IAM role with Vercel's OIDC token, so no AWS keys
    are stored anywhere. The token arrives on each request in the x-vercel-oidc-token header
    (or VERCEL_OIDC_TOKEN in `vercel dev`); OidcTokenMiddleware keeps the latest one.
SCAMSHIELD_AWS_ACCESS_KEY_ID / SCAMSHIELD_AWS_SECRET_ACCESS_KEY: a dedicated IAM user's keys.
Neither: boto3's normal credential chain (local development).

Vercel reserves the AWS_* variable names (its functions run with their own AWS credentials),
hence the SCAMSHIELD_ prefix, and why explicit credentials replace the default chain.
"""

from __future__ import annotations

import os
import threading

import boto3
import botocore.session
from botocore.credentials import AssumeRoleWithWebIdentityCredentialFetcher, DeferredRefreshableCredentials

_token_lock = threading.Lock()
_latest_oidc_token: str | None = None


def remember_oidc_token(token: str | None) -> None:
    global _latest_oidc_token
    if token:
        with _token_lock:
            _latest_oidc_token = token


def _load_oidc_token() -> str:
    with _token_lock:
        token = _latest_oidc_token
    token = token or os.environ.get("VERCEL_OIDC_TOKEN")
    if not token:
        raise RuntimeError("No Vercel OIDC token yet; is OIDC federation enabled for this project?")
    return token


def configure_aws(region: str) -> str:
    """Set boto3's default session for this process. Returns the mode used."""
    role_arn = os.environ.get("SCAMSHIELD_AWS_ROLE_ARN")
    access_key = os.environ.get("SCAMSHIELD_AWS_ACCESS_KEY_ID")
    if role_arn:
        session = botocore.session.get_session()
        fetcher = AssumeRoleWithWebIdentityCredentialFetcher(
            client_creator=session.create_client,
            web_identity_token_loader=_load_oidc_token,
            role_arn=role_arn,
            extra_args={"RoleSessionName": "scamshield-web"},
        )
        session._credentials = DeferredRefreshableCredentials(  # botocore has no public setter for these
            method="assume-role-with-web-identity", refresh_using=fetcher.fetch_credentials
        )
        session.set_config_variable("region", region)
        boto3.setup_default_session(botocore_session=session)
        return "oidc"
    if access_key:
        boto3.setup_default_session(
            aws_access_key_id=access_key,
            aws_secret_access_key=os.environ["SCAMSHIELD_AWS_SECRET_ACCESS_KEY"],
            region_name=region,
        )
        return "keys"
    return "default"


class OidcTokenMiddleware:
    """Pure ASGI middleware: remember the Vercel OIDC token from each request."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name == b"x-vercel-oidc-token":
                    remember_oidc_token(value.decode("latin-1"))
                    break
        await self.app(scope, receive, send)
