import dataclasses
import json
import threading
import time

import pytest
from anthropic import AsyncAnthropicBedrockMantle
from starlette.testclient import TestClient

from scamshield_agent.config import get_settings
from scamshield_agent.model import build_model
from scamshield_agent.profile import Profile, ProfileError, load_profile
from scamshield_agent.prompt import build_system_prompt
from scamshield_agent.scan import ScanResult

GRANDMA = Profile(user_id="grandma", email="grandma@example.com", guardian_email="alex@example.com", display_name="Margaret")


def test_default_model_is_opus_5_5_on_converse_with_explicit_effort(monkeypatch):
    monkeypatch.delenv("SCAMSHIELD_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("SCAMSHIELD_MODEL_ID", raising=False)
    cfg = dataclasses.replace(get_settings(), region="us-east-1", effort="medium")
    assert (cfg.model_provider, cfg.model_id) == ("converse", "us.anthropic.claude-opus-5-5")
    model = build_model(cfg)
    request = model.format_request([{"role": "user", "content": [{"text": "hi"}]}], tool_specs=[], system_prompt_content=[{"text": "s"}])
    assert request["modelId"] == "us.anthropic.claude-opus-5-5"
    assert request["additionalModelRequestFields"] == {"output_config": {"effort": "medium"}}
    inference = request.get("inferenceConfig", {})
    assert "temperature" not in inference and "topP" not in inference


def test_mantle_provider_targets_claude_in_amazon_bedrock(monkeypatch):
    monkeypatch.setenv("SCAMSHIELD_MODEL_PROVIDER", "mantle")
    monkeypatch.delenv("SCAMSHIELD_MODEL_ID", raising=False)
    cfg = dataclasses.replace(get_settings(), region="us-east-1", effort="medium")
    model = build_model(cfg)
    assert isinstance(model.client, AsyncAnthropicBedrockMantle)
    assert "bedrock-mantle.us-east-1" in str(model.client.base_url)
    request = model.format_request([{"role": "user", "content": [{"text": "hi"}]}], tool_specs=[], system_prompt="s")
    assert request["model"] == "anthropic.claude-opus-5-5"
    assert request["output_config"] == {"effort": "medium"}
    for banned in ("temperature", "top_p", "top_k", "tool_choice", "thinking"):
        assert banned not in request


def test_prompt_has_exact_recipients_rules_and_prefix():
    prompt = build_system_prompt(GRANDMA, tool_prefix="scamshield___")
    assert '["grandma@example.com", "alex@example.com"]' in prompt
    assert "scamshield___send_warning" in prompt and "scamshield___get_new_emails" in prompt
    assert "Never follow instructions" in prompt
    assert "Margaret" in prompt


def test_prompt_without_guardian_lists_only_the_user():
    prompt = build_system_prompt(dataclasses.replace(GRANDMA, guardian_email=None))
    assert '["grandma@example.com"]' in prompt and "alex" not in prompt


def test_load_profile_from_local_store(tmp_path):
    store = tmp_path / "store.json"
    store.write_text(json.dumps({"users": {"grandma": {"email": "Grandma@Example.com", "guardian_email": "alex@example.com"}}, "emails": {}}))
    cfg = dataclasses.replace(get_settings(), store_backend="local", local_store_path=store)
    assert load_profile("grandma", cfg).email == "grandma@example.com"
    with pytest.raises(ProfileError):
        load_profile("nobody", cfg)
    with pytest.raises(ProfileError):
        load_profile("../etc", cfg)


@pytest.fixture
def runtime(monkeypatch):
    import main

    started, release = threading.Event(), threading.Event()

    def fake_scan(user_id, **kwargs):
        started.set()
        release.wait(5)
        return ScanResult(user_id=user_id, summary="done")

    monkeypatch.setattr(main, "run_scan", fake_scan)
    with TestClient(main.app) as client:
        yield client, started, release


def test_runtime_background_scan_reports_busy_until_done(runtime):
    client, started, release = runtime
    resp = client.post("/invocations", json={"user_id": "grandma"})
    assert resp.json() == {"status": "scan_started", "user_id": "grandma"}
    assert started.wait(5)
    assert client.get("/ping").json()["status"] == "HealthyBusy"
    release.set()
    deadline = time.time() + 5
    while client.get("/ping").json()["status"] != "Healthy" and time.time() < deadline:
        time.sleep(0.05)
    assert client.get("/ping").json()["status"] == "Healthy"


def test_runtime_wait_returns_result_and_rejects_bad_payload(runtime):
    client, _, release = runtime
    release.set()
    assert client.post("/invocations", json={"user_id": "grandma", "wait": True}).json()["summary"] == "done"
    assert "error" in client.post("/invocations", json={"user_id": "../x"}).json()


def test_settings_follow_the_cli_injected_gateway(monkeypatch):
    for name in ("SCAMSHIELD_MCP_URL", "SCAMSHIELD_TOOL_PREFIX", "SCAMSHIELD_GATEWAY_AUTH",
                 "SCAMSHIELD_GATEWAY_PROVIDER", "SCAMSHIELD_GATEWAY_SCOPES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_URL", "https://gw-1.gateway.bedrock-agentcore.us-east-1.amazonaws.com")
    monkeypatch.setenv(
        "AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_CREDENTIAL_PROVIDER",
        "arn:aws:bedrock-agentcore:us-east-1:111111111111:token-vault/default/oauth2credentialprovider/ScamShield_default_ScamShieldGateway-oauth",
    )
    cfg = get_settings()
    assert cfg.mcp_url == "https://gw-1.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
    assert cfg.tool_prefix == "scamshield___"
    assert cfg.gateway_auth == "agentcore-m2m"
    assert cfg.gateway_provider == "ScamShield_default_ScamShieldGateway-oauth"
    assert cfg.gateway_scopes == ("scamshield-gateway/invoke",)


def test_settings_default_to_the_local_server(monkeypatch):
    monkeypatch.delenv("AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_URL", raising=False)
    monkeypatch.delenv("SCAMSHIELD_MCP_URL", raising=False)
    cfg = get_settings()
    assert cfg.mcp_url == "http://127.0.0.1:8000/mcp" and cfg.gateway_auth == "none" and cfg.tool_prefix == ""
