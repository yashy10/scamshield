"""The demo's "Scan now": invoke the deployed agent runtime for one user.

    uv run scripts/scan_now.py --user-id grandma [--wait] [--arn arn:aws:bedrock-agentcore:...:runtime/...]

The runtime ARN comes from --arn or SCAMSHIELD_AGENT_ARN (`agentcore status --json`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import boto3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--wait", action="store_true", help="Wait for the scan and print its result")
    parser.add_argument("--arn", default=os.environ.get("SCAMSHIELD_AGENT_ARN"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()
    if not args.arn:
        print("Pass --arn or set SCAMSHIELD_AGENT_ARN.")
        return 1

    client = boto3.client("bedrock-agentcore", region_name=args.region)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=args.arn,
        qualifier="DEFAULT",
        runtimeSessionId=f"scan-now-{args.user_id}-{uuid.uuid4().hex}",  # API minimum is 33 characters
        contentType="application/json",
        payload=json.dumps({"user_id": args.user_id, "wait": args.wait}).encode(),
    )
    body = resp["response"].read().decode()
    try:
        print(json.dumps(json.loads(body), indent=2))
    except json.JSONDecodeError:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
