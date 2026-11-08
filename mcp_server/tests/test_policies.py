"""Evaluate the generated Cedar locally with cedarpy: the same allow/deny decisions the
Gateway's policy engine should make in ENFORCE mode."""

import cedarpy
import pytest

from scamshield.policies import inbox_tools_policy, send_warning_policy
from scamshield.store import UserProfile

GW = "arn:aws:bedrock-agentcore:us-east-1:111111111111:gateway/scamshield-gw"
GRANDMA = UserProfile(user_id="grandma", email="grandma@example.com", guardian_email="alex@example.com")
OTHER = UserProfile(user_id="bob", email="bob@example.com", guardian_email="carol@example.com")


def policy_set(client_id=None):
    return "\n".join(
        [
            inbox_tools_policy(GW, client_id=client_id),
            send_warning_policy(GW, GRANDMA, client_id=client_id),
            send_warning_policy(GW, OTHER, client_id=client_id),
        ]
    )


def decide(tool, args, policies=None, client_id="agent-client"):
    request = {
        "principal": 'AgentCore::OAuthUser::"agent-client"',
        "action": f'AgentCore::Action::"scamshield___{tool}"',
        "resource": f'AgentCore::Gateway::"{GW}"',
        "context": {"input": args},
    }
    entities = [
        {"uid": {"type": "AgentCore::OAuthUser", "id": "agent-client"}, "attrs": {}, "parents": [], "tags": {"client_id": client_id}}
    ]
    result = cedarpy.is_authorized(request, policies or policy_set(), entities)
    assert not result.diagnostics.errors, result.diagnostics.errors
    return result.decision


@pytest.mark.parametrize("tool", ["get_new_emails", "check_domain_age", "check_threat_list", "label_email"])
def test_rule1_inbox_tools_allowed(tool):
    assert decide(tool, {"user_id": "grandma"}) == cedarpy.Decision.Allow


@pytest.mark.parametrize("tool", ["delete_email", "forward_email", "send_email", "trash_email"])
def test_rule1_anything_else_denied(tool):
    assert decide(tool, {"user_id": "grandma"}) == cedarpy.Decision.Deny


def test_rule2_user_and_guardian_allowed():
    args = {"user_id": "grandma", "email_id": "m1", "verdict": "scam", "reasons": ["r"], "recipients": ["grandma@example.com", "alex@example.com"]}
    assert decide("send_warning", args) == cedarpy.Decision.Allow
    args["recipients"] = ["alex@example.com"]
    assert decide("send_warning", args) == cedarpy.Decision.Allow


def test_rule2_injected_recipient_denied():
    args = {"user_id": "grandma", "email_id": "m1", "verdict": "scam", "reasons": ["r"],
            "recipients": ["grandma@example.com", "alex@example.com", "helper@example.com"]}
    assert decide("send_warning", args) == cedarpy.Decision.Deny


def test_rule2_cannot_use_another_users_guardian():
    args = {"user_id": "grandma", "email_id": "m1", "verdict": "scam", "reasons": ["r"], "recipients": ["carol@example.com"]}
    assert decide("send_warning", args) == cedarpy.Decision.Deny


def test_rule2_is_case_sensitive_so_agent_must_send_lowercase():
    args = {"user_id": "grandma", "email_id": "m1", "verdict": "scam", "reasons": ["r"], "recipients": ["Grandma@Example.com"]}
    assert decide("send_warning", args) == cedarpy.Decision.Deny


def test_client_id_pin():
    pinned = policy_set(client_id="agent-client")
    assert decide("get_new_emails", {"user_id": "grandma"}, pinned) == cedarpy.Decision.Allow
    assert decide("get_new_emails", {"user_id": "grandma"}, pinned, client_id="someone-else") == cedarpy.Decision.Deny


def test_generator_rejects_unsafe_values():
    with pytest.raises(ValueError):
        send_warning_policy(GW, UserProfile(user_id="grandma", email='x"@evil.com', guardian_email="a@b.com"))
    with pytest.raises(ValueError):
        inbox_tools_policy("not-an-arn")
    with pytest.raises(ValueError):
        send_warning_policy(GW, UserProfile(user_id="grandma", email="g@example.com"))  # no guardian


def test_list_users(tmp_path):
    from scamshield.store import LocalStore

    store = LocalStore(tmp_path / "s.json")
    store.put_user(OTHER)
    store.put_user(GRANDMA)
    assert [u.user_id for u in store.list_users()] == ["bob", "grandma"]
