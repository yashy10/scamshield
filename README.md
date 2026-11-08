# ScamShield

An AI agent that watches a vulnerable person's Gmail, investigates risky emails with real evidence,
labels likely scams, and sends a plain-English warning to the user and a trusted guardian.
Built on Amazon Bedrock AgentCore (Runtime, Gateway, Identity, Policy). See `ScamShield PRD.pdf`;
the phased build plan lives in the "ScamShield Build Plan" Claude Doc.

> The AI does the thinking, but it never holds the keys or makes the rules.

## Status

Everything that can be built and tested without credentials is done. Each phase's "done when"
check still needs real accounts.

| Phase | Built | Verified so far | Blocked on |
|---|---|---|---|
| 1. Tools | MCP server, 5 tools; sign-up site (`web/`) | 50 tests; live RDAP; real HTTP server; sign-up flow tested in both modes | Google Cloud project, Safe Browsing key |
| 2. Agent | Strands agent, Opus 5.5 on Bedrock | 11 tests; **real Opus 5.5 scan of the simulated inbox: all 5 verdicts right** | Real Gmail inbox (Google setup) |
| 3. Deploy | Identity-backed credentials, consent script, runtime entrypoint, CDK stack, AgentCore CLI project + runbook (`deploy/`) | Stubbed Identity calls; `cdk synth`; 12 infra tests; AgentCore stack typechecks; runtime deps resolve for ARM64 | AWS credentials, Google "Web application" OAuth client |
| 4. Guardrails | Cedar policy generator | Policies evaluated locally with the Cedar engine | A deployed Gateway ARN |
| 5. Trigger | Scheduler in CDK, background entrypoint, Scan now | Entrypoint ping/busy behaviour tested | A deployed agent runtime |

## Layout

```
mcp_server/            the ScamShield MCP server (FastMCP, now `MCPServer` in MCP SDK v2)
  scamshield/server.py   the 5 tools
  scamshield/credentials.py   local (Phase 1) or AgentCore Identity (Phase 3) secrets
  scamshield/policies.py      Cedar generator for Policy (Phase 4)
  scamshield/testing.py       fakes + fixture-inbox demo mode
  scripts/               connect_gmail.py (local), connect_gmail_identity.py (Identity), link_user.py,
                         sync_policies.py, forget_emails.py, call_tool.py
agent/                 the investigator agent (Strands + Claude Opus 5.5 on Bedrock)
  scamshield_agent/      model, prompt, user_id-pinning hook, scan loop, CLI
  main.py                AgentCore Runtime entrypoint (background scan for the scheduler, wait=true for Scan now)
  scripts/scan_now.py    invoke the deployed agent
infra/                 CDK: DynamoDB table, SES identities, MCP-server IAM policy, EventBridge schedules
deploy/                AgentCore CLI project + Phase 3 runbook
demo/                  simulated inbox (inbox.json) and the real demo emails
web/                   sign-up site: guardian invites, "Connect my Gmail", people page with Scan now
```

## What you need to do (credentials)

1. **AWS:** done. Credentials work (IAM user `acmHacks`) and Claude Opus 5.5 answers through Bedrock's
   Converse API. The account's organization blocks the newer `bedrock-mantle` endpoint, so the agent uses Converse.
2. **Google Cloud:** project with Gmail API + Safe Browsing API; OAuth consent screen in Testing with
   the test inbox as a test user; a Desktop OAuth client JSON at `.local/secrets/google_oauth_client.json` (Phase 1) and later
   a Web application client for AgentCore Identity (Phase 3); a Safe Browsing API key in `.env` at the repo root.
   Local secrets and state live in the git-ignored `.local/`, outside the code folders AgentCore uploads.
3. **SES:** verify the sender and recipient addresses (the CDK stack can create the identities).

## Run it

```bash
# Tests (no credentials needed)
cd mcp_server && uv run pytest     # 50 tests
cd agent && uv run pytest          # 10 tests, full loop with a scripted model
cd infra && uv run pytest          # 12 tests
cd web && uv run pytest            # 8 tests, sign-up flow with Google/Identity faked

# Sign-up site: http://localhost:8080 (guardian signs up, sends the invite, they connect Gmail)
cd web && uv run python app.py

# Phase 1: tools against the real test inbox
cp .env.example .env && cd mcp_server   # add SAFE_BROWSING_API_KEY to .env
uv run scripts/connect_gmail.py --user-id grandma --guardian-email you@example.com --name Margaret   # or use the sign-up site
uv run python main.py                    # then MCP Inspector -> http://127.0.0.1:8000/mcp

# Phase 2: one real scan (AWS credentials). Use the simulated inbox first: see demo/README.md
cd agent && uv run python -m scamshield_agent --user-id grandma
```

Phases 3 to 5 deploy steps: `deploy/README.md` (AgentCore CLI) and `infra/README.md` (CDK).

**The sign-up site** uses the same switch as the MCP server. With `SCAMSHIELD_CREDENTIALS=local` (default) Google
returns to `http://localhost:8080/` and the token is saved in `.local/secrets/`. That works with the Desktop OAuth
client; if Google reports `redirect_uri_mismatch`, set `SCAMSHIELD_WEB_BASE_URL=http://127.0.0.1:8080`. With
`SCAMSHIELD_CREDENTIALS=agentcore` (Phase 3) AgentCore Identity runs the consent, keeps the token, and returns to
`http://localhost:8080/connect/callback`, which must be allowed on the MCP runtime's workload identity.
Scan now runs the local agent, or the deployed one when `SCAMSHIELD_AGENT_ARN` is set.

## Design decisions and deviations from the PRD

- **MCP SDK v2.** `FastMCP` was renamed `MCPServer` in `mcp` 2.x; AgentCore's current docs use v2.
- **Claude Opus 5.5 through Bedrock's Converse API** (`us.anthropic.claude-opus-5-5`, Strands' native
  `BedrockModel`), effort set explicitly to `medium`. The hackathon organization's SCP denies the newer
  Claude in Amazon Bedrock endpoint (`bedrock-mantle`); `SCAMSHIELD_MODEL_PROVIDER=mantle` switches to it
  for accounts that allow it. No refusal fallback: a refused turn ends that scan and the emails are
  retried on the next run.
- **`get_new_emails` returns the sender's display name** (`sender_name`, with family names redacted), so the
  model can spot a brand name sent from an unrelated domain, the PRD's "odd sender" signal.
- **`user_id` never comes from the model.** A Strands hook overwrites it on every tool call; Policy
  pins it again at the Gateway.
- **Gmail scope is `gmail.modify`**, the narrowest that can add labels; it technically also allows
  sending and trashing. No tool can do either, and Policy rule 1 denies anything else.
- **`label_email` records every verdict, including `fine`.** Emails without links are marked checked
  automatically.
- **The guardian's copy never includes the email's subject**, only verdict, reasons and sender domain.
- **Recipients are checked twice:** by Policy at the Gateway and by `send_warning` itself
  (`SCAMSHIELD_TOOL_RECIPIENT_CHECK=false` relies on Policy alone, e.g. for the with/without-Policy eval).
- **Cedar can't read DynamoDB**, so the recipient rule is generated per user (`sync_policies.py`) and
  re-run when a guardian changes. Cedar compares exact strings; the agent's prompt carries the
  addresses in lowercase.
- **Redaction affects the injection demo:** real email addresses are stripped before the model sees
  them, so the demo email spells the address out ("helper at example dot com").
- **"Our code never sees the token"** is not quite true: the MCP server holds the Gmail token in memory
  for each call. It is never stored by our code and never reaches the model.
- **Secrets stay out of logs:** the Safe Browsing key goes in a header, HTTP request logging is off,
  and a consent URL is never returned to the model.
- Safe Browsing is non-commercial only; a commercial launch would switch to Google Web Risk.
- Testing-mode Google apps expire refresh tokens after 7 days; reconnect the day before the demo.
