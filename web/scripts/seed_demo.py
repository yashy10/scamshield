"""Fill a local JSON store with demo people and eight weeks of results, to preview the dashboard.

    uv run python scripts/seed_demo.py                      # writes ../.local/demo-store.json
    SCAMSHIELD_STORE=local SCAMSHIELD_LOCAL_STORE_PATH=../.local/demo-store.json SCAMSHIELD_DEV_SIGNIN=1 \
        uv run python app.py

Then sign in on http://localhost:8080/signin with the local preview box as alex@example.com (a guardian
of three people) or margaret.demo@gmail.com (sees her own inbox). Never point this at DynamoDB.
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scamshield.config import LOCAL_DIR
from scamshield.store import EmailRecord, Invite, LocalStore, UserProfile

GUARDIAN = ("Alex", "alex@example.com")

FLAGGED = {
    "margaret": [
        (1.6, "scam", "Chase Security Team", "chase-secure-login.com", "Your account has been locked",
         ["The link goes to chase-secure-login.com, a website registered 3 days ago.",
          "Google Safe Browsing lists the link as a phishing site.",
          "It says it is from Chase, but it was sent from an unrelated address."]),
        (4.2, "suspicious", "Billing Department", "invoice-paynow.com", "Invoice #4471 is overdue",
         ["The payment website was registered 2 months ago.",
          "It pushes you to pay quickly to avoid a late fee, for an invoice you may not recognise."]),
        (6.1, "scam", "USPS Delivery", "usps-redelivery-help.com", "Package on hold: action needed today",
         ["The link goes to a website registered 5 days ago, not usps.com.",
          "It asks for a small fee to redeliver a package. The Postal Service doesn’t do this by email."]),
        (19.4, "scam", "Netflix", "streamflix-accounts.net", "Please update your payment details",
         ["Google Safe Browsing lists the link as a phishing site.",
          "It says it is from Netflix, but it was sent from streamflix-accounts.net."]),
        (24.8, "suspicious", "Prize Center", "winners-notice.org", "You’ve been selected for a $500 gift card",
         ["The website was registered 6 weeks ago.", "It offers a prize you didn’t enter for."]),
        (37.0, "scam", "Microsoft Support", "ms-support-alerts.com", "Your computer has a virus. Call now",
         ["The link goes to a website registered 2 days ago.",
          "Microsoft doesn’t email you about viruses or ask you to call a number."]),
    ],
    "june": [
        (2.7, "suspicious", "Medicare Benefits", "medicare-benefit-update.com", "Your 2027 benefits card is ready",
         ["The website was registered 3 weeks ago, and it isn’t medicare.gov.",
          "It asks you to confirm your Medicare number."]),
    ],
    "robert": [],
}

PEOPLE = [("margaret", "Margaret", "margaret.demo@gmail.com", 7),
          ("robert", "Robert", "robert.demo@gmail.com", 4),
          ("june", "June", "june.demo@gmail.com", 5)]


def seed(path: Path, now: datetime) -> None:
    store = LocalStore(path)
    rng = random.Random(7)
    for key, name, email, per_day in PEOPLE:
        user_id = f"demo-{key}"
        store.put_user(UserProfile(user_id=user_id, email=email, guardian_email=GUARDIAN[1],
                                   display_name=name, guardian_name=GUARDIAN[0]))
        store.put_invite(Invite(token=f"demo-invite-{key}", user_id=user_id, protected_name=name,
                                guardian_name=GUARDIAN[0], guardian_email=GUARDIAN[1],
                                created_at=(now - timedelta(days=60)).isoformat(timespec="seconds"),
                                connected_at=(now - timedelta(days=59)).isoformat(timespec="seconds"),
                                connected_email=email))
        n = 0
        for day in range(56):
            for _ in range(max(0, round(rng.gauss(per_day, 2)))):
                n += 1
                moment = now - timedelta(days=day, hours=rng.uniform(0.2, 23))
                verdict = "no_links" if rng.random() < 0.45 else "fine"
                store.put_email(EmailRecord(user_id=user_id, email_id=f"{user_id}-{n:05d}", verdict=verdict,
                                            checked_at=(moment + timedelta(minutes=20)).isoformat(timespec="seconds"),
                                            received_at=moment.isoformat(timespec="seconds")))
        for i, (days_ago, verdict, sender, domain, subject, reasons) in enumerate(FLAGGED[key]):
            moment = now - timedelta(days=days_ago)
            store.put_email(EmailRecord(
                user_id=user_id, email_id=f"{user_id}-flagged-{i}", verdict=verdict, labeled=True,
                reasons=reasons, checked_at=(moment + timedelta(minutes=25)).isoformat(timespec="seconds"),
                warned_at=(moment + timedelta(minutes=26)).isoformat(timespec="seconds"),
                warned_recipients=[email, GUARDIAN[1]], sender_name=sender, sender_domain=domain,
                subject=subject, received_at=moment.isoformat(timespec="seconds"),
            ))
    print(f"Seeded {len(PEOPLE)} demo people into {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", type=Path, default=LOCAL_DIR / "demo-store.json")
    args = parser.parse_args()
    if args.store.exists():
        args.store.unlink()  # start clean so "now" lines up with the seeded dates
    seed(args.store, datetime.now(UTC))
