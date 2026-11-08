"""Phase 4: generate the Cedar policies for the Gateway's policy engine from the store.

Writes ../policies/generated/ (git-ignored: the files contain email addresses) and prints the
AgentCore CLI commands to load them. Re-run whenever a guardian is linked or changed.

Usage:
    uv run scripts/sync_policies.py --gateway-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/abc \
        [--target scamshield] [--separator ___] [--client-id <agent cognito client id>] [--engine ScamShieldPolicy]
"""

from __future__ import annotations

import argparse
import os
import sys

from scamshield.config import PACKAGE_ROOT, get_settings
from scamshield.policies import inbox_tools_policy, send_warning_policy
from scamshield.store import make_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway-arn", default=os.environ.get("SCAMSHIELD_GATEWAY_ARN"))
    parser.add_argument("--target", default="scamshield", help="Gateway target name")
    parser.add_argument("--separator", default="___", help="Between target and tool in action names")
    parser.add_argument("--client-id", help="Pin policies to the agent's Cognito client (principal tag client_id)")
    parser.add_argument("--engine", default="ScamShieldPolicy", help="Policy engine name in the AgentCore project")
    parser.add_argument("--out", default=str(PACKAGE_ROOT.parent / "policies" / "generated"))
    args = parser.parse_args()
    if not args.gateway_arn:
        print("Pass --gateway-arn (from `agentcore status --json`) or set SCAMSHIELD_GATEWAY_ARN.")
        return 1

    opts = dict(target=args.target, sep=args.separator, client_id=args.client_id)
    files = {"AllowInboxTools": inbox_tools_policy(args.gateway_arn, **opts)}
    skipped = []
    for profile in make_store(get_settings()).list_users():
        if not profile.guardian_email:
            skipped.append(profile.user_id)
            continue
        files[f"SendWarning_{profile.user_id}"] = send_warning_policy(args.gateway_arn, profile, **opts)

    os.makedirs(args.out, exist_ok=True)
    print(f"Wrote {len(files)} policies to {args.out}")
    for name, text in files.items():
        path = os.path.join(args.out, f"{name}.cedar")
        with open(path, "w") as fh:
            fh.write(text)
        print(f"  agentcore add policy --name {name} --engine {args.engine} --statement file://{path}")
    if skipped:
        print(f"Skipped users with no guardian: {', '.join(skipped)}")
    print("Then run: agentcore deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
