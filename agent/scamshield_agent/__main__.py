"""Run one scan locally against the MCP server (Phase 2).

    uv run python -m scamshield_agent --user-id grandma

Needs AWS credentials with Bedrock access to Claude, and the MCP server running
(`cd ../mcp_server && uv run python main.py`).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import anthropic
import botocore.exceptions

from .config import get_settings
from .profile import ProfileError
from .scan import run_scan


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one ScamShield scan.")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "httpx2", "botocore", "strands.telemetry"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        result = run_scan(args.user_id)
    except anthropic.AuthenticationError as exc:
        print(f"Bedrock rejected the AWS credentials ({exc.status_code}). Check `aws sts get-caller-identity`.")
        return 2
    except anthropic.PermissionDeniedError as exc:
        print(f"No access to {get_settings().model_id} on Bedrock ({exc.status_code}). Request model access, "
              "or set SCAMSHIELD_MODEL_ID=us.anthropic.claude-opus-4-8.")
        return 2
    except ProfileError as exc:
        print(exc)
        return 2
    except botocore.exceptions.NoCredentialsError:
        print("No AWS credentials found. Run `aws configure` (region us-east-1).")
        return 2
    except botocore.exceptions.ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"Bedrock refused the call ({err.get('Code')}): {err.get('Message', '')[:200]}")
        return 2
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        for call in result.tool_calls:
            shown = {k: v for k, v in (call["input"] or {}).items() if k != "user_id"}
            print(f"  {call['status']:>7}  {call['tool']}  {json.dumps(shown)[:120]}")
        print(f"\n{result.summary}")
        if result.user_id_overrides:
            print(f"\nNote: the model tried a different user_id {result.user_id_overrides} time(s); it was pinned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
