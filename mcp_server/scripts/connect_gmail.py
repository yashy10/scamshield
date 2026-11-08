"""Phase 1 only: connect a protected user's Gmail on this machine and link their guardian.

Runs Google's own consent screen in your browser, saves the token to
.local/secrets/gmail_token_<user_id>.json (mode 600, git-ignored), reads the account's address,
and stores the user -> guardian link. Phase 3 replaces this with AgentCore Identity.

Usage:
    uv run scripts/connect_gmail.py --user-id grandma --guardian-email you@example.com \
        [--name "Margaret"] [--guardian-name "Alex"] [--reauth]

Needs .local/secrets/google_oauth_client.json (repo root): a "Desktop app" OAuth client from Google Cloud Console.
"""

from __future__ import annotations

import argparse
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from scamshield.config import get_settings
from scamshield.credentials import GMAIL_SCOPES, LocalGmailTokenProvider, validate_user_id, write_secret
from scamshield.gmail import GmailClient
from scamshield.store import UserProfile, make_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True, help="Short id for the protected user, e.g. grandma")
    parser.add_argument("--guardian-email", required=True, help="Guardian's email address (copied on warnings)")
    parser.add_argument("--name", help="Protected user's name (redacted from snippets, used in guardian emails)")
    parser.add_argument("--guardian-name", help="Guardian's name (redacted from snippets)")
    parser.add_argument("--reauth", action="store_true", help="Run the Google consent flow even if a token exists")
    args = parser.parse_args()

    settings = get_settings()
    user_id = validate_user_id(args.user_id)
    tokens = LocalGmailTokenProvider(settings.secrets_dir)
    token_path = tokens.token_path(user_id)
    client_file = settings.secrets_dir / "google_oauth_client.json"

    if args.reauth or not token_path.exists():
        if not client_file.exists():
            print(f"Missing {client_file}. Create a Desktop OAuth client in Google Cloud Console and save its JSON there.")
            return 1
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
        write_secret(token_path, creds.to_json())
        print(f"Saved Gmail token to {token_path}")

    email = GmailClient(tokens.access_token(user_id)).profile_email()
    store = make_store(settings)
    existing = store.get_user(user_id)
    store.put_user(
        UserProfile(
            user_id=user_id,
            email=email.lower(),
            guardian_email=args.guardian_email.strip().lower(),
            display_name=args.name or (existing.display_name if existing else None),
            guardian_name=args.guardian_name or (existing.guardian_name if existing else None),
        )
    )
    print(f"Connected user '{user_id}' ({email}); guardian: {args.guardian_email}")
    print(f"Store: {settings.store_backend}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
