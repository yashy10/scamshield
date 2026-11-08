# ScamShield infra (CDK)

One stack, `ScamShieldInfra`, in us-east-1. AgentCore Runtime, Gateway, Identity and Policy come from
the AgentCore CLI; this stack holds what they use.

| Resource | Notes |
|---|---|
| DynamoDB table `ScamShield` | `pk`/`sk` strings, on-demand. Verdicts only, never email bodies. Deleted with the stack. |
| SES email identities | `sesFrom` plus every `sesIdentities` address. The SES sandbox only delivers to verified addresses. |
| Managed policy `ScamShieldMcpServerAccess` | For the MCP server runtime's execution role: table Get/Put/BatchGet, `ses:SendEmail` from `sesFrom` only, AgentCore Identity token and API key reads, `secretsmanager:GetSecretValue`. |
| Scheduler role + one schedule per `scanUsers` id | Only when `agentRuntimeArn` is set. Runs `rate(5 minutes)`, no retries, calls `InvokeAgentRuntime` with `{"user_id": "<id>"}` and a new session id per run. |

Outputs: `TableName`, `McpServerPolicyArn`, `SchedulerRoleArn` (only when the schedules exist).

## Deploy

You need AWS credentials for the target account, and a one-time bootstrap of the account and region:

```bash
cd infra
uv sync
npx -y aws-cdk@2.1146.1 bootstrap aws://<account-id>/us-east-1
npx -y aws-cdk@2.1146.1 deploy \
  -c sesFrom=scamshield.alerts@example.com \
  -c sesIdentities=grandma@example.com,guardian@example.com \
  -c agentRuntimeArn=arn:aws:bedrock-agentcore:us-east-1:<account-id>:runtime/<runtime-id> \
  -c scanUsers=grandma \
  -c schedulesEnabled=false
```

- **SES sends a verification email to every identity.** Each address must click its link before SES will
  send from or to it. If an address is already verified in SES (for example from Phase 1), delete it in the
  SES console first, or the deploy fails because the identity already exists.
- Use the same `sesFrom` value as `SCAMSHIELD_SES_FROM`; the policy only allows that From address.
- Every flag is optional, but pass the same set on every deploy: leaving one out removes what it created.
- Leave `agentRuntimeArn` out until the runtime exists. Schedules start `DISABLED`; redeploy with
  `-c schedulesEnabled=true` to start scanning.
- Then attach the policy to the MCP server runtime's execution role:
  `aws iam attach-role-policy --role-name <mcp-runtime-role> --policy-arn <McpServerPolicyArn>`.
- Scheduler has been observed to give up on a universal-target call after about 30 seconds and record it as
  failed even when the agent finishes. The agent entrypoint should return an acknowledgement quickly and
  keep scanning in the background.

## Check without deploying

```bash
uv run pytest
npx -y aws-cdk@2.1146.1 synth -c agentRuntimeArn=arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/x -c scanUsers=grandma
```

Synth needs no credentials. On Node 23, set `JSII_SILENCE_WARNING_END_OF_LIFE_NODE_VERSION=23` to hide jsii's warning.
