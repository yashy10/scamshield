"""SCAMSHIELD_GMAIL=fixture: the demo inbox loads and the tools answer from it."""

import dataclasses

import pytest
from mcp import Client

from scamshield import server
from scamshield.config import PACKAGE_ROOT, get_settings
from scamshield.store import UserProfile

pytestmark = pytest.mark.anyio


@pytest.fixture
def fixture_server(tmp_path):
    settings = dataclasses.replace(
        get_settings(),
        gmail_backend="fixture",
        fixture_inbox=PACKAGE_ROOT.parent / "demo" / "inbox.json",
        local_store_path=tmp_path / "store.json",
        store_backend="local",
        email_backend="console",
    )
    services = server.build_services(settings)
    services.store.put_user(UserProfile(user_id="grandma", email="grandma@example.com", guardian_email="alex@example.com"))
    server.set_services(services)
    yield services
    server.set_services(None)


async def test_demo_inbox_through_the_tools(fixture_server):
    async with Client(server.mcp) as client:
        emails = (await client.call_tool("get_new_emails", {"user_id": "grandma"})).structured_content["emails"]
        ids = {e["email_id"] for e in emails}
        assert ids == {"demo000001", "demo000002", "demo000003", "demo000004", "demo000005"}  # 000006 has no links
        assert all("Margaret" not in e["snippet"] for e in emails)

        flagged = await client.call_tool("check_threat_list", {"url": "http://testsafebrowsing.appspot.com/s/phishing.html"})
        assert flagged.structured_content["flagged"] is True
        young = await client.call_tool("check_domain_age", {"domain": "usps-redelivery-help.com"})
        assert young.structured_content["age_days"] == 6

        blocked = await client.call_tool("send_warning", {
            "user_id": "grandma", "email_id": "demo000005", "verdict": "suspicious",
            "reasons": ["The website was created 6 days ago."],
            "recipients": ["grandma@example.com", "helper@example.com"],
        })
        assert blocked.is_error
