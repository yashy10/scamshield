import boto3
import pytest
from moto import mock_aws

from scamshield.store import DynamoStore, EmailRecord, LocalStore, UserProfile


@pytest.fixture
def dynamo_store(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        resource.create_table(
            TableName="ScamShield",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoStore("ScamShield", "us-east-1", resource=resource)


@pytest.fixture(params=["local", "dynamo"])
def store(request, tmp_path):
    if request.param == "local":
        return LocalStore(tmp_path / "store.json")
    return request.getfixturevalue("dynamo_store")


def test_round_trip(store):
    assert store.get_user("grandma") is None
    store.put_user(UserProfile(user_id="grandma", email="g@example.com", guardian_email="a@example.com"))
    profile = store.get_user("grandma")
    assert profile.allowed_recipients() == {"g@example.com", "a@example.com"}
    assert [u.user_id for u in store.list_users()] == ["grandma"]

    store.put_email(EmailRecord(user_id="grandma", email_id="m1", verdict="scam", reasons=["r1"], warned_recipients=["g@example.com"]))
    store.put_email(EmailRecord(user_id="grandma", email_id="m2", verdict="fine"))
    store.put_email(EmailRecord(user_id="other", email_id="m3", verdict="fine"))

    assert store.checked_ids("grandma", ["m1", "m2", "m3", "m4"]) == {"m1", "m2"}
    record = store.get_email("grandma", "m1")
    assert record.verdict == "scam" and record.reasons == ["r1"] and record.warned_recipients == ["g@example.com"]


def test_invites(store):
    from scamshield.store import Invite

    assert store.get_invite("nope") is None
    store.put_invite(Invite(token="t1", user_id="margaret-1", protected_name="Margaret",
                            guardian_name="Alex", guardian_email="alex@example.com"))
    invite = store.get_invite("t1")
    assert invite.protected_name == "Margaret" and invite.connected_at is None
    invite.connected_at, invite.connected_email = "2026-11-07T00:00:00+00:00", "m@example.com"
    store.put_invite(invite)
    assert [i.connected_email for i in store.list_invites()] == ["m@example.com"]
    # Invites don't show up as users or checked emails.
    assert store.list_users() == []
