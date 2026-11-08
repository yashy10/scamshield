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


def test_list_emails_and_marked_safe(store):
    store.put_email(EmailRecord(user_id="grandma", email_id="m1", verdict="scam", subject="Locked", sender_domain="x.com"))
    store.put_email(EmailRecord(user_id="grandma", email_id="m2", verdict="fine"))
    store.put_email(EmailRecord(user_id="other", email_id="m3", verdict="fine"))
    assert sorted(r.email_id for r in store.list_emails("grandma")) == ["m1", "m2"]

    record = store.get_email("grandma", "m1")
    record.marked_safe_at, record.marked_safe_by = "2026-11-07T00:00:00+00:00", "g@example.com"
    store.put_email(record)
    again = store.get_email("grandma", "m1")
    assert (again.marked_safe_at, again.marked_safe_by, again.subject) == (
        "2026-11-07T00:00:00+00:00", "g@example.com", "Locked")

    # Undoing it really removes the mark (the whole item is replaced, and None values are dropped).
    again.marked_safe_at = again.marked_safe_by = None
    store.put_email(again)
    assert store.get_email("grandma", "m1").marked_safe_at is None


def test_update_email_keeps_other_writers_fields(store):
    # send_warning writes the reasons, then label_email writes its fields: neither may erase the other's.
    store.update_email("u1", "e1", {"verdict": "suspicious", "reasons": ["The website is 3 days old."],
                                    "warned_recipients": ["me@gmail.com"], "warned_at": "2026-11-08T05:00:00+00:00"})
    store.update_email("u1", "e1", {"verdict": "suspicious", "labeled": True, "checked_at": "2026-11-08T05:00:01+00:00",
                                    "sender_domain": "tiktokshop.com", "subject": "Your plan"})
    got = store.get_email("u1", "e1")
    assert got.reasons == ["The website is 3 days old."] and got.warned_recipients == ["me@gmail.com"]
    assert got.labeled and got.sender_domain == "tiktokshop.com" and got.subject == "Your plan"

    # A field set to None is removed (undoing "marked safe").
    store.update_email("u1", "e1", {"marked_safe_at": "2026-11-08T06:00:00+00:00", "marked_safe_by": "me@gmail.com"})
    store.update_email("u1", "e1", {"marked_safe_at": None, "marked_safe_by": None})
    got = store.get_email("u1", "e1")
    assert got.marked_safe_at is None and got.reasons == ["The website is 3 days old."]

    # Creating a record without a verdict defaults it to fine.
    store.update_email("u1", "e2", {"labeled": False})
    assert store.get_email("u1", "e2").verdict == "fine"


def test_update_email_rejects_unknown_fields(store):
    with pytest.raises(ValueError):
        store.update_email("u1", "e1", {"body": "never stored"})
    with pytest.raises(ValueError):
        store.update_email("u1", "e1", {"user_id": "someone-else"})
