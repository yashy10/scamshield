"""Tiny MCP client for the running server (an alternative to MCP Inspector).

Usage:
    uv run scripts/call_tool.py list
    uv run scripts/call_tool.py check_domain_age '{"domain": "example.com"}'
    uv run scripts/call_tool.py get_new_emails '{"user_id": "grandma"}'

Set SCAMSHIELD_MCP_URL to target another server (default http://127.0.0.1:8000/mcp).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client

URL = os.environ.get("SCAMSHIELD_MCP_URL", "http://127.0.0.1:8000/mcp")


async def run(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    async with Client(URL) as client:
        if argv[0] == "list":
            for tool in (await client.list_tools()).tools:
                print(f"- {tool.name}: {(tool.description or '').splitlines()[0]}")
            return 0
        args = json.loads(argv[1]) if len(argv) > 1 else {}
        result = await client.call_tool(argv[0], args)
        if result.structured_content is not None:
            print(json.dumps(result.structured_content, indent=2))
        else:
            for block in result.content:
                print(getattr(block, "text", block))
        return 1 if result.is_error else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run(sys.argv[1:])))
