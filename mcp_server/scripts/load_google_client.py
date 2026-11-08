"""Load a Google "Web application" OAuth client into the AgentCore Identity credential provider.

Reads the client JSON downloaded from Google Cloud and updates the provider in place, so the client
secret goes from the file straight to AgentCore Identity (Secrets Manager) and is never printed.

    uv run scripts/load_google_client.py ../.local/secrets/google_web_client.json [--provider scamshield-google]

The Google client must list the provider's callback URL as an Authorized redirect URI; this script
prints that URL.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3

from scamshield.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("client_file", type=Path)
    parser.add_argument("--provider", default="scamshield-google")
    args = parser.parse_args()

    data = json.loads(args.client_file.read_text())
    client = data.get("web")
    if not client:
        print("That file isn't a Web application client (no 'web' section). Create one of type Web application.")
        return 1

    agentcore = boto3.client("bedrock-agentcore-control", region_name=get_settings().aws_region)
    resp = agentcore.update_oauth2_credential_provider(
        name=args.provider,
        credentialProviderVendor="GoogleOauth2",
        oauth2ProviderConfigInput={
            "googleOauth2ProviderConfig": {"clientId": client["client_id"], "clientSecret": client["client_secret"]}
        },
    )
    callback = resp.get("callbackUrl")
    redirects = client.get("redirect_uris", [])
    print(f"Loaded client {client['client_id'][:16]}… into provider '{args.provider}'.")
    print(f"Callback URL: {callback}")
    print("Redirect URI registered in Google:", "yes" if callback in redirects else "NO - add the callback URL above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
