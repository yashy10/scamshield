"""Entrypoint (AgentCore Runtime expects the MCP server at 0.0.0.0:8000/mcp; set SCAMSHIELD_HOST=0.0.0.0 there)."""

from scamshield.server import main

if __name__ == "__main__":
    main()
