"""Create or update a protected user's profile (their address and their guardian) without touching OAuth.

Used for the fixture-inbox demo and to change a guardian later. Re-run sync_policies.py afterwards
once Policy is deployed.

    uv run scripts/link_user.py --user-id grandma --email grandma@example.com --guardian-email alex@example.com \
        [--name Margaret] [--guardian-name Alex]
"""

from __future__ import annotations

import argparse
import sys

from scamshield.config import get_settings
from scamshield.credentials import validate_user_id
from scamshield.store import UserProfile, make_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--guardian-email", required=True)
    parser.add_argument("--name")
    parser.add_argument("--guardian-name")
    args = parser.parse_args()

    settings = get_settings()
    store = make_store(settings)
    profile = UserProfile(
        user_id=validate_user_id(args.user_id),
        email=args.email.strip().lower(),
        guardian_email=args.guardian_email.strip().lower(),
        display_name=args.name,
        guardian_name=args.guardian_name,
    )
    store.put_user(profile)
    print(f"Linked '{profile.user_id}' ({profile.email}) -> guardian {profile.guardian_email}. Store: {settings.store_backend}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
