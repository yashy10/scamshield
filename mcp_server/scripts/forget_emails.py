"""Forget which emails were checked for a user in the LOCAL store, so a demo can be re-run.
(It does not remove Gmail labels; remove those in Gmail if you want a clean inbox.)

    uv run scripts/forget_emails.py --user-id grandma
"""

from __future__ import annotations

import argparse
import json
import sys

from scamshield.config import get_settings
from scamshield.credentials import validate_user_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if settings.store_backend != "local":
        print("Only the local store is supported; delete EMAIL# items in DynamoDB by hand.")
        return 1
    path = settings.local_store_path
    if not path.exists():
        print("Nothing to forget.")
        return 0
    data = json.loads(path.read_text())
    removed = len(data["emails"].pop(validate_user_id(args.user_id), {}))
    path.write_text(json.dumps(data, indent=2))
    print(f"Forgot {removed} checked emails for '{args.user_id}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
