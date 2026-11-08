"""The JSON API the Next.js frontend uses: session, dashboard, Scan now, Mark as safe, sign-up and invites."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from scamshield.store import EmailRecord, Invite, LocalStore, UserProfile
from scamshield_web.api import dashboard_json, zone
from scamshield_web.auth import Account
from scamshield_web.scans import ScanState

from .test_web import make_client

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
WEB = {"X-ScamShield-Client": "web"}
ALEX = Account("alex@example.com", "Alex")


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def seed(store, now=NOW):
    store.put_user(UserProfile(user_id="margaret-1", email="margaret@gmail.com", guardian_email="alex@example.com",
                               display_name="Margaret", guardian_name="Alex"))
    store.put_user(UserProfile(user_id="robert-1", email="robert@gmail.com", guardian_email="alex@example.com",
                               display_name="Robert", guardian_name="Alex"))
    store.put_user(UserProfile(user_id="pat-1", email="pat@gmail.com", guardian_email="carol@example.com",
                               display_name="Pat"))
    two_days = iso(now - timedelta(days=2))
    store.put_email(EmailRecord(user_id="margaret-1", email_id="scam1", verdict="scam", labeled=True,
                                reasons=["The website is 3 days old."], warned_at=two_days,
                                warned_recipients=["margaret@gmail.com", "alex@example.com"],
                                sender_name="Chase Security", sender_domain="chase-secure-login.com",
                                subject="Your account is locked", received_at=two_days, checked_at=two_days))
    store.put_email(EmailRecord(user_id="margaret-1", email_id="fine1", verdict="fine",
                                received_at=iso(now - timedelta(days=1)), checked_at=iso(now - timedelta(hours=3))))
    # Ten days ago: outside the last 7 days, inside the 7 before them.
    ten = iso(now - timedelta(days=10))
    store.put_email(EmailRecord(user_id="margaret-1", email_id="sus1", verdict="suspicious", received_at=ten,
                                checked_at=ten, sender_domain="invoice-paynow.com", subject="Invoice overdue"))
    store.put_email(EmailRecord(user_id="robert-1", email_id="r1", verdict="no_links",
                                received_at=iso(now - timedelta(days=3)), checked_at=iso(now - timedelta(days=3))))
    store.put_email(EmailRecord(user_id="pat-1", email_id="p1", verdict="scam", subject="Pat's private email",
                                checked_at=two_days))
    store.put_invite(Invite(token="waiting-token-1", user_id="june-1", protected_name="June", guardian_name="Alex",
                            guardian_email="alex@example.com"))


def site(tmp_path):
    store = LocalStore(tmp_path / "store.json")
    seed(store)
    scans = SimpleNamespace(states={})
    return SimpleNamespace(store=store, base_url="http://localhost:3000", scans=scans), store


def test_dashboard_for_a_guardian(tmp_path):
    cfg, _ = site(tmp_path)
    data = dashboard_json(cfg, ALEX, "margaret-1", "7", UTC, now=NOW)

    assert data["account"] == {"email": "alex@example.com", "name": "Alex"}
    assert [(p["id"], p["role"], p["status"], p["flagged30d"]) for p in data["people"]] == [
        ("margaret-1", "guardian", "scam", 2), ("robert-1", "guardian", "safe", 0)]
    assert data["waiting"] == [{"token": "waiting-token-1", "protectedName": "June",
                                "inviteUrl": "http://localhost:3000/join/waiting-token-1"}]

    view = data["view"]
    assert view["person"] == {"id": "margaret-1", "name": "Margaret", "email": "margaret@gmail.com",
                              "role": "guardian", "guardianName": "Alex", "guardianEmail": "alex@example.com"}
    assert (view["period"], view["periodLabel"], view["status"]) == ("7", "Last 7 days", "scam")
    assert view["counts"] == {"checked": 2, "scam": 1, "suspicious": 0, "safe": 1, "warningsSent": 1, "markedSafe": 0}
    assert view["previous"] == {"checked": 1, "scam": 0, "suspicious": 1, "safe": 0}
    assert view["lastCheckedAt"] == iso(NOW - timedelta(hours=3))
    assert view["scan"] == {"status": "idle", "message": None}

    [item] = view["flagged"]
    assert item["id"] == "scam1" and item["subject"] is None  # guardians see warnings, not emails
    assert item["senderDomain"] == "chase-secure-login.com" and item["warnedTo"] == "Margaret and you"
    assert item["markedSafe"] is None and item["labeled"] is True

    assert view["series"]["unit"] == "day"
    assert [p["start"] for p in view["series"]["points"]] == [f"2026-11-0{d}" for d in range(1, 8)]
    assert view["series"]["points"][4] == {"start": "2026-11-05", "safe": 0, "suspicious": 0, "scam": 1}

    # Nobody else's data leaks, and an inbox this account can't see falls back to its first person.
    assert "Pat" not in str(data) and "pat-1" not in str(data)
    assert dashboard_json(cfg, ALEX, "pat-1", "7", UTC, now=NOW)["view"]["person"]["id"] == "margaret-1"


def test_dashboard_for_the_person_and_strangers(tmp_path):
    cfg, _ = site(tmp_path)
    mine = dashboard_json(cfg, Account("margaret@gmail.com", "Margaret"), None, "30", UTC, now=NOW)
    assert [p["role"] for p in mine["people"]] == ["self"] and mine["waiting"] == []
    view = mine["view"]
    assert [f["subject"] for f in view["flagged"]] == ["Your account is locked", "Invoice overdue"]
    assert view["flagged"][0]["warnedTo"] == "you and Alex"
    assert len(view["series"]["points"]) == 30

    nobody = dashboard_json(cfg, Account("nobody@gmail.com", ""), None, "30", UTC, now=NOW)
    assert nobody["people"] == [] and nobody["view"] is None


def test_days_follow_the_viewers_time_zone(tmp_path):
    cfg, store = site(tmp_path)
    late = iso(datetime(2026, 11, 7, 3, 30, tzinfo=UTC))  # 7:30 pm on Nov 6 in Los Angeles
    store.put_email(EmailRecord(user_id="robert-1", email_id="r2", verdict="scam", received_at=late, checked_at=late))
    utc = dashboard_json(cfg, ALEX, "robert-1", "7", UTC, now=NOW)["view"]["series"]["points"]
    la = dashboard_json(cfg, ALEX, "robert-1", "7", ZoneInfo("America/Los_Angeles"), now=NOW)["view"]["series"]["points"]
    assert next(p for p in utc if p["start"] == "2026-11-07")["scam"] == 1
    assert next(p for p in la if p["start"] == "2026-11-06")["scam"] == 1
    assert zone("America/Los_Angeles") == ZoneInfo("America/Los_Angeles")
    assert zone("Not/AZone") is UTC and zone("../../etc/passwd") is UTC and zone(None) is UTC


def test_all_time_is_weekly(tmp_path):
    cfg, _ = site(tmp_path)
    view = dashboard_json(cfg, ALEX, "margaret-1", "all", UTC, now=NOW)["view"]
    assert view["series"]["unit"] == "week" and view["previous"] is None and view["periodLabel"] == "All time"
    starts = [p["start"] for p in view["series"]["points"]]
    assert starts == ["2026-10-26", "2026-11-02"]  # Mondays, from the first record's week to this week
    assert sum(p["scam"] + p["suspicious"] + p["safe"] for p in view["series"]["points"]) == view["counts"]["checked"] == 3


def test_marked_safe_counts_as_safe(tmp_path):
    cfg, store = site(tmp_path)
    record = store.get_email("margaret-1", "scam1")
    record.marked_safe_at, record.marked_safe_by = iso(NOW), "alex@example.com"
    store.put_email(record)
    data = dashboard_json(cfg, ALEX, "margaret-1", "7", UTC, now=NOW)
    view = data["view"]
    assert view["status"] == "safe" and data["people"][0]["status"] == "careful"  # the suspicious one is 10 days old
    assert view["counts"] == {"checked": 2, "scam": 0, "suspicious": 0, "safe": 2, "warningsSent": 1,
                                   "markedSafe": 1}
    assert view["flagged"][0]["markedSafe"] == {"at": iso(NOW), "by": "alex@example.com"}
    assert view["series"]["points"][4]["safe"] == 1 and view["series"]["points"][4]["scam"] == 0


def test_session_and_dashboard_over_http(tmp_path):
    client, store, *_ = make_client(tmp_path, dev_sign_in=True)
    seed(store, datetime.now(UTC))
    assert client.get("/api/session").json() == {"account": None, "googleSignIn": False, "devSignIn": True}
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401 and resp.json() == {"error": "signed_out"}

    client.post("/signin/dev", data={"email": "alex@example.com"})
    assert client.get("/api/session").json()["account"] == {"email": "alex@example.com", "name": ""}
    resp = client.get("/api/dashboard", params={"person": "margaret-1", "period": "bogus", "tz": "Europe/London"})
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    assert resp.json()["view"]["period"] == "30" and resp.json()["view"]["person"]["id"] == "margaret-1"

    assert client.get("/api/nope").json() == {"error": "not_found"}


def test_scan_now(tmp_path):
    client, store, scans, _ = make_client(tmp_path, dev_sign_in=True)
    seed(store)
    assert client.post("/api/people/margaret-1/scan", headers=WEB).status_code == 401
    client.post("/signin/dev", data={"email": "alex@example.com"})

    assert client.post("/api/people/margaret-1/scan").json() == {"error": "missing_client_header"}
    assert client.post("/api/people/pat-1/scan", headers=WEB).status_code == 404
    assert client.get("/api/people/margaret-1/scan").json() == {"status": "idle", "message": None}

    resp = client.post("/api/people/margaret-1/scan", headers=WEB)
    assert resp.status_code == 202 and resp.json() == {"status": "started"} and scans.started == ["margaret-1"]

    scans.states["margaret-1"] = ScanState("running")
    resp = client.post("/api/people/margaret-1/scan", headers=WEB)
    assert resp.status_code == 200 and resp.json() == {"status": "running"} and scans.started == ["margaret-1"]
    assert client.get("/api/people/margaret-1/scan").json() == {"status": "running",
                                                                "message": "Checking new emails now."}

    # A deployed scan that just started isn't started again for a minute.
    scans.states["margaret-1"] = ScanState("started", summary="Scan started.")
    assert client.post("/api/people/margaret-1/scan", headers=WEB).json() == {"status": "started"}
    assert scans.started == ["margaret-1"]
    scans.states["margaret-1"] = ScanState("started", at=time.time() - 120)
    assert client.post("/api/people/margaret-1/scan", headers=WEB).status_code == 202
    assert scans.started == ["margaret-1", "margaret-1"]

    def broken(user_id):
        scans.states[user_id] = ScanState("error", error="set SCAMSHIELD_AGENT_ARN")
    scans.start = broken
    resp = client.post("/api/people/robert-1/scan", headers=WEB)
    assert resp.status_code == 503 and "isn’t available" in resp.json()["error"]
    assert "ARN" not in resp.text  # operator details stay in the logs


def test_mark_as_safe_and_undo(tmp_path):
    client, store, *_ = make_client(tmp_path, dev_sign_in=True)
    seed(store)
    url = "/api/people/margaret-1/emails/scam1/safe"
    assert client.post(url, json={"safe": True}, headers=WEB).status_code == 401
    client.post("/signin/dev", data={"email": "alex@example.com"})

    assert client.post(url, json={"safe": True}).status_code == 403
    assert client.post(url, content="not json", headers={**WEB, "content-type": "application/json"}).status_code == 400
    assert client.post(url, json={"safe": "yes"}, headers=WEB).status_code == 400
    assert client.post("/api/people/pat-1/emails/p1/safe", json={"safe": True}, headers=WEB).status_code == 404
    assert client.post("/api/people/margaret-1/emails/missing/safe", json={"safe": True}, headers=WEB).status_code == 404

    marked = client.post(url, json={"safe": True}, headers=WEB).json()["markedSafe"]
    assert marked["by"] == "alex@example.com" and store.get_email("margaret-1", "scam1").marked_safe_at == marked["at"]
    assert client.post(url, json={"safe": False}, headers=WEB).json() == {"markedSafe": None}
    assert store.get_email("margaret-1", "scam1").marked_safe_by is None


def test_signup_and_invites(tmp_path):
    client, store, *_ = make_client(tmp_path)
    assert client.post("/api/signup", json={}).status_code == 403
    bad = client.post("/api/signup", json={"guardianName": "", "guardianEmail": "nope", "protectedName": 5,
                                           "agreed": "yes"}, headers=WEB)
    assert bad.status_code == 400
    assert set(bad.json()["errors"]) == {"guardianName", "guardianEmail", "protectedName", "agreed"}
    assert bad.json()["errors"]["guardianEmail"] == "Enter an email address like name@example.com."

    ok = client.post("/api/signup", json={"guardianName": " Alex ", "guardianEmail": "Alex@Example.com",
                                          "protectedName": "Margaret", "agreed": True}, headers=WEB)
    assert ok.status_code == 201
    token = ok.json()["token"]
    assert ok.json()["inviteUrl"] == f"http://localhost:8080/join/{token}"
    invite = store.get_invite(token)
    assert (invite.guardian_name, invite.guardian_email, invite.protected_name) == ("Alex", "alex@example.com", "Margaret")

    assert client.get(f"/api/invites/{token}").json() == {"protectedName": "Margaret", "guardianName": "Alex",
                                                          "connected": False,
                                                          "inviteUrl": f"http://localhost:8080/join/{token}"}
    assert client.get("/api/invites/short").status_code == 404
    assert client.get("/api/invites/no-such-invite-token").status_code == 404
