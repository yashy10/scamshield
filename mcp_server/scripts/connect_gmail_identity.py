"""Phase 3: connect a protected user's Gmail through AgentCore Identity (the "Connect Gmail" step).

Google's consent screen runs in the browser; AgentCore Identity stores the token in its vault under
(MCP server workload, user id). Our code never stores it. This script only hosts the local
session-binding callback and then records the user -> guardian link.

One-time setup (needs AWS credentials):
    aws bedrock-agentcore-control update-workload-identity --name "$SCAMSHIELD_WORKLOAD_NAME" \
        --allowed-resource-oauth2-return-urls http://localhost:8765/callback
If AgentCore rejects a plain-http localhost URL, expose the callback over HTTPS (e.g. a tunnel)
and pass that URL with --return-url.

Usage (env: SCAMSHIELD_WORKLOAD_NAME, AWS_REGION, SCAMSHIELD_STORE=dynamodb):
    uv run scripts/connect_gmail_identity.py --user-id grandma --guardian-email you@example.com [--name Margaret] [--reauth]
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from scamshield.config import get_settings
from scamshield.credentials import validate_user_id
from scamshield.gmail import GmailClient
from scamshield.onboarding import ConsentError, IdentityConsent
from scamshield.store import UserProfile, make_store


def wait_for_session_id(port: int, timeout_s: int = 600) -> str | None:
    """Serve one /callback request on 127.0.0.1 and return its session_id query parameter."""
    received: dict[str, str] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parts = urlsplit(self.path)
            session_id = parse_qs(parts.query).get("session_id", [None])[0]
            if parts.path != "/callback" or not session_id:
                self.send_response(404)
                self.end_headers()
                return
            received["session_id"] = session_id
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Gmail connected to ScamShield.</h1><p>You can close this tab.</p>")
            done.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        done.wait(timeout_s)
    finally:
        server.shutdown()
    return received.get("session_id")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--guardian-email", required=True)
    parser.add_argument("--name", help="Protected user's name (redacted from snippets)")
    parser.add_argument("--guardian-name", help="Guardian's name (redacted from snippets)")
    parser.add_argument("--reauth", action="store_true", help="Force a fresh Google consent")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--return-url", help="Override the session-binding callback URL")
    args = parser.parse_args()

    settings = get_settings()
    user_id = validate_user_id(args.user_id)
    if not settings.workload_name:
        print("Set SCAMSHIELD_WORKLOAD_NAME to the MCP server runtime's workload identity (its runtime ID).")
        return 1
    return_url = args.return_url or f"http://localhost:{args.port}/callback"
    consent = IdentityConsent(settings, return_url)  # same flow the sign-up site uses

    try:
        start = consent.start(user_id, force=args.reauth)
        params: dict[str, str] = {}
        if start.authorization_url:
            print(f"Opening Google's consent page (valid 10 minutes):\n{start.authorization_url}\n")
            webbrowser.open(start.authorization_url)
            session_id = wait_for_session_id(args.port) if not args.return_url else input("Paste session_id: ").strip()
            if not session_id:
                print("Timed out waiting for the consent callback.")
                return 1
            params = {"session_id": session_id}
        email = GmailClient(consent.finish(user_id, start.state, params)).profile_email()
    except ConsentError as exc:
        print(exc)
        return 1
    print("Consent recorded in AgentCore Identity.")

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
    print(f"Connected '{user_id}' ({email}); guardian: {args.guardian_email}. Store: {settings.store_backend}")
    print("Next: regenerate Cedar policies so the guardian is allowed (uv run scripts/sync_policies.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
