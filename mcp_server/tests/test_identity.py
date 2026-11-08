"""AgentCore Identity providers against a stubbed boto3 client (no AWS calls)."""

import boto3
import pytest
from botocore.stub import Stubber

from scamshield.credentials import (
    GMAIL_SCOPES,
    AgentCoreApiKeyProvider,
    AgentCoreGmailTokenProvider,
    CredentialError,
)


RETURN_URL = "https://scamshield.example/connect/callback"


@pytest.fixture
def client():
    c = boto3.client(
        "bedrock-agentcore", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y"
    )
    with Stubber(c) as stub:
        yield c, stub
        stub.assert_no_pending_responses()


def expect_workload_token(stub, user_id="grandma"):
    stub.add_response(
        "get_workload_access_token_for_user_id",
        {"workloadAccessToken": "wat-123"},
        {"workloadName": "mcp-runtime-id", "userId": user_id},
    )


def test_gmail_token_from_vault(client):
    c, stub = client
    expect_workload_token(stub)
    stub.add_response(
        "get_resource_oauth2_token",
        {"accessToken": "ya29.token"},
        {
            "workloadIdentityToken": "wat-123",
            "resourceCredentialProviderName": "scamshield-google",
            "scopes": GMAIL_SCOPES,
            "oauth2Flow": "USER_FEDERATION",
            # AgentCore requires a registered return URL on every fetch, and the consent's custom
            # parameters; without either it refuses or starts a new consent instead.
            "resourceOauth2ReturnUrl": RETURN_URL,
            "customParameters": {"access_type": "offline", "prompt": "consent"},
        },
    )
    provider = AgentCoreGmailTokenProvider("mcp-runtime-id", "scamshield-google", "us-east-1", RETURN_URL, client=c)
    assert provider.access_token("grandma") == "ya29.token"


def test_gmail_not_connected_hides_consent_url(client):
    c, stub = client
    expect_workload_token(stub)
    stub.add_response(
        "get_resource_oauth2_token",
        {"authorizationUrl": "https://accounts.google.com/o/oauth2/auth?x=1", "sessionUri": "urn:s"},
    )
    provider = AgentCoreGmailTokenProvider("mcp-runtime-id", "scamshield-google", "us-east-1", RETURN_URL, client=c)
    with pytest.raises(CredentialError) as err:
        provider.access_token("grandma")
    assert "not connected" in str(err.value)
    assert "accounts.google.com" not in str(err.value)  # never hand a consent link to the model


def test_gmail_identity_error_is_friendly(client):
    c, stub = client
    stub.add_client_error("get_workload_access_token_for_user_id", service_error_code="AccessDeniedException")
    provider = AgentCoreGmailTokenProvider("mcp-runtime-id", "scamshield-google", "us-east-1", RETURN_URL, client=c)
    with pytest.raises(CredentialError, match="AccessDeniedException"):
        provider.access_token("grandma")


def test_gmail_rejects_bad_user_id_before_calling_aws(client):
    c, _ = client
    provider = AgentCoreGmailTokenProvider("mcp-runtime-id", "scamshield-google", "us-east-1", RETURN_URL, client=c)
    with pytest.raises(CredentialError):
        provider.access_token("../../evil")


def test_api_key_is_cached(client):
    c, stub = client
    stub.add_response("get_workload_access_token", {"workloadAccessToken": "wat-9"}, {"workloadName": "mcp-runtime-id"})
    stub.add_response(
        "get_resource_api_key",
        {"apiKey": "AIza-key"},
        {"workloadIdentityToken": "wat-9", "resourceCredentialProviderName": "scamshield-safe-browsing"},
    )
    provider = AgentCoreApiKeyProvider("mcp-runtime-id", "scamshield-safe-browsing", "us-east-1", client=c)
    assert provider.safe_browsing_key() == "AIza-key"
    assert provider.safe_browsing_key() == "AIza-key"  # second call served from cache, no new stub needed


def test_make_credentials_requires_workload_name():
    import dataclasses

    from scamshield.config import get_settings
    from scamshield.server import make_credentials

    settings = dataclasses.replace(get_settings(), credentials_backend="agentcore", workload_name=None)
    with pytest.raises(ValueError, match="SCAMSHIELD_WORKLOAD_NAME"):
        make_credentials(settings)
