# deploy/: ScamShield's AgentCore project

This directory is an AgentCore CLI project (`@aws/agentcore` 1.0.2), created offline with
`agentcore create --name ScamShield --template empty --skip-install --skip-git` plus the `add` commands
below. It holds no app code: both runtimes point at the repo's own `mcp_server/` and `agent/` directories.

```
deploy/
  agentcore/agentcore.json     the spec: runtimes, gateway, policy engine (edit with the CLI or jq)
  agentcore/aws-targets.json   deployment targets; empty until the first deploy adds "default"
  agentcore/.env.local         gitignored; the CLI keeps credential secrets here, encrypted
  agentcore/cdk/               the CDK app the CLI deploys (lib/cdk-stack.ts has three additions, below)
```

## What is declared

| Resource | Name | Config |
|---|---|---|
| Runtime | `ScamShieldMcp` | MCP protocol, CodeZip, Python 3.13, `codeLocation: ../mcp_server`, entrypoint `main.py`, inbound `AWS_IAM`, env vars below |
| Runtime | `ScamShieldAgent` | HTTP protocol, CodeZip, Python 3.13, `codeLocation: ../agent`, entrypoint `main.py`, inbound `AWS_IAM`, env vars below |
| Gateway | `ScamShieldGateway` | MCP, inbound `CUSTOM_JWT` (Cognito, **placeholders until step 3**), semantic search off, policy engine `ScamShieldPolicy` in `LOG_ONLY` |
| Policy engine | `ScamShieldPolicy` | no policies yet (they need the gateway ARN, step 11) |

Deployed names follow `<project>_<target>_<name>`: runtimes `ScamShield_default_ScamShieldMcp` and
`ScamShield_default_ScamShieldAgent` (plus a service suffix), gateway `ScamShield-default-ScamShieldGateway`,
CloudFormation stack `AgentCore-ScamShield-default`.

`ScamShieldMcp` env vars: `SCAMSHIELD_HOST=0.0.0.0`, `SCAMSHIELD_STORE=dynamodb`, `SCAMSHIELD_DYNAMODB_TABLE=ScamShield`,
`SCAMSHIELD_EMAIL_BACKEND=ses`, `SCAMSHIELD_SES_FROM` (**placeholder until step 3**), `SCAMSHIELD_CREDENTIALS=agentcore`,
`SCAMSHIELD_GOOGLE_PROVIDER=ScamShield_default_GoogleGmail`, `SCAMSHIELD_SAFE_BROWSING_PROVIDER=ScamShield_default_SafeBrowsing`.
`SCAMSHIELD_WORKLOAD_NAME` is added in step 8, because it is the runtime's own ID and only exists after the first deploy.
The CDK app also injects these into **every** runtime: `AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_URL` / `_ARN` / `_AUTH_TYPE`,
`AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_CREDENTIAL_PROVIDER` (once `ScamShieldGateway-oauth` exists, with IAM to fetch its token),
and `CREDENTIAL_<NAME>_NAME` for each credential (the deployed provider name, e.g. `CREDENTIAL_GOOGLEGMAIL_NAME`).

`agentcore/cdk/lib/cdk-stack.ts` adds what `agentcore.json` can't express:
1. `bedrock-agentcore:InvokeAgentRuntime` on `ScamShieldMcp` for the gateway role. The construct grants this only for
   `httpRuntime` targets, not for an `mcpServer` target that signs with the gateway role.
2. Attaches infra/'s managed policy `ScamShieldMcpServerAccess` (DynamoDB, SES, Identity reads) to the MCP runtime role.
   **infra/ must be deployed before this project.**

3. `ScamShieldAgent`'s role gets `dynamodb:GetItem` on the `ScamShield` table (it reads the user's and guardian's
   addresses for its prompt) and `bedrock:InvokeModel` / `InvokeModelWithResponseStream` on the US Claude inference
   profiles. The hackathon organization's SCP denies the newer `bedrock-mantle` endpoint, so the agent uses Converse.

`ScamShieldAgent` env vars: `SCAMSHIELD_STORE=dynamodb`, `SCAMSHIELD_DYNAMODB_TABLE=ScamShield`,
`SCAMSHIELD_MODEL_PROVIDER=converse`, `SCAMSHIELD_MODEL_ID=us.anthropic.claude-opus-5-5`, `SCAMSHIELD_EFFORT=medium`, `SCAMSHIELD_TOOL_PREFIX=scamshield___`,
`SCAMSHIELD_GATEWAY_AUTH=agentcore-m2m`, `SCAMSHIELD_GATEWAY_SCOPES=scamshield-gateway/invoke`. The Gateway URL and its
credential provider come from the CLI-injected `AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_*` vars. If step 9 shows the
Gateway's tool names use `__` rather than `___`, change `SCAMSHIELD_TOOL_PREFIX` (and `--separator` in step 11).
Opus 5.5 is already callable from this account (tested); `us.anthropic.claude-opus-4-8` is the fallback.

## Code prerequisites (done)

- Both `pyproject.toml` files depend on `aws-opentelemetry-distro~=0.21.0`: the deployed entrypoint is
  `opentelemetry-instrument main.py`. Both dependency sets resolve for aarch64 manylinux with binary wheels only.
- CodeZip uploads everything in `../mcp_server` and `../agent` except `.git`, `.venv`, `venv`, `__pycache__`,
  `.pytest_cache`, `.DS_Store`, `node_modules`. So local secrets and state (Gmail tokens, the OAuth client JSON, the
  local verdict store, `.env`) live in the repo root's git-ignored `.local/` and `.env`, never inside a code folder.
  Still check before each deploy: `ls -a ../mcp_server ../agent | grep -E '\.env|secrets|\.local|\.data'` prints nothing.
- Only `[project].dependencies` are installed (with `uv pip install --only-binary :all:` for aarch64 manylinux); `uv.lock`
  is ignored. Both runtimes are on Python 3.13 because both `requires-python` ranges stop below 3.14.
- `agentcore dev` will not run these runtimes: it requires code inside the project root
  (`runtime code directory must be within the project root`). Run them locally the way their own READMEs describe.

## Phase 3 runbook

Run everything from `deploy/` in one shell session; later steps use variables set by earlier ones.
Never put a secret on a command line or in a file. Read it with `read -rs` and pipe it in.

### 0. Session setup
```bash
cd deploy
export AWS_REGION=us-east-1
agentcore() { npx -y @aws/agentcore@1.0.2 "$@"; }   # pinned; avoids the Python starter toolkit's `agentcore`
edit_spec() { jq "$@" agentcore/agentcore.json > agentcore/agentcore.json.new && mv agentcore/agentcore.json.new agentcore/agentcore.json; }
aws sts get-caller-identity                            # must succeed
(cd agentcore/cdk && npm install)                      # `create` ran with --skip-install
ls -d ../mcp_server/.env ../mcp_server/secrets ../mcp_server/.data ../agent/.env 2>/dev/null && echo "STOP: these would be uploaded"
# Optional: deploy also turns on CloudWatch Transaction Search account-wide unless you opt out first:
#   agentcore config transactionSearch false
```

### 1. Google: a Web OAuth client
The Phase 1 client is a Desktop app, and Desktop clients can't register AgentCore's redirect URI. In Google Cloud
Console, go to APIs & Services, then Credentials, then Create OAuth client ID, and choose **Web application**.
Leave the redirect URIs empty for now; step 7 fills them in. Keep the consent screen in Testing with the test account added.
```bash
GOOGLE_CLIENT_ID=<web client id>.apps.googleusercontent.com
```

### 2. Cognito for the gateway's inbound JWT (AWS CLI)
The AgentCore CLI can't create an identity provider. 1.0.2 has no Cognito code, and the "gateway created with the AgentCore
CLI" doc says to set one up first. The agent gets tokens with the client-credentials grant.
```bash
POOL_ID=$(aws cognito-idp create-user-pool --pool-name ScamShieldGateway --query UserPool.Id --output text)
GW_DOMAIN="scamshield-gw-$(openssl rand -hex 4)"
aws cognito-idp create-user-pool-domain --user-pool-id "$POOL_ID" --domain "$GW_DOMAIN"
aws cognito-idp create-resource-server --user-pool-id "$POOL_ID" --identifier scamshield-gateway \
  --name "ScamShield Gateway" --scopes '[{"ScopeName":"invoke","ScopeDescription":"Call ScamShield tools"}]'
GW_CLIENT_ID=$(aws cognito-idp create-user-pool-client --user-pool-id "$POOL_ID" --client-name scamshield-agent \
  --generate-secret --allowed-o-auth-flows client_credentials --allowed-o-auth-flows-user-pool-client \
  --allowed-o-auth-scopes scamshield-gateway/invoke --query UserPoolClient.ClientId --output text)
DISCOVERY_URL="https://cognito-idp.$AWS_REGION.amazonaws.com/$POOL_ID/.well-known/openid-configuration"
```

### 3. Fill the placeholders
```bash
SES_FROM=<the SES-verified sender, same as infra's sesFrom>
edit_spec --arg url "$DISCOVERY_URL" --arg client "$GW_CLIENT_ID" --arg from "$SES_FROM" '
  (.agentCoreGateways[] | select(.name == "ScamShieldGateway") | .authorizerConfiguration.customJwtAuthorizer) |= (.discoveryUrl = $url | .allowedClients = [$client])
  | (.runtimes[] | select(.name == "ScamShieldMcp") | .envVars[] | select(.name == "SCAMSHIELD_SES_FROM") | .value) = $from'
grep -n CHANGE_ME agentcore/agentcore.json && echo "STOP: placeholders left"
```

### 4. Credential providers (secrets piped on stdin)
```bash
printf 'Google client secret: '; read -rs GOOGLE_CLIENT_SECRET; echo
printf '%s' "$GOOGLE_CLIENT_SECRET" | agentcore add credentials oauth --name GoogleGmail --vendor GoogleOauth2 \
  --provider-configuration "{\"googleOauth2ProviderConfig\":{\"clientId\":\"$GOOGLE_CLIENT_ID\"}}" --client-secret -

printf 'Safe Browsing API key: '; read -rs SAFE_BROWSING_API_KEY; echo
printf '%s' "$SAFE_BROWSING_API_KEY" | agentcore add credentials api-key --name SafeBrowsing --api-key -

# The agent's token for the gateway. The name must be exactly <gateway>-oauth: the CDK app then passes its
# provider to every runtime as AGENTCORE_GATEWAY_SCAMSHIELDGATEWAY_CREDENTIAL_PROVIDER and grants token access.
aws cognito-idp describe-user-pool-client --user-pool-id "$POOL_ID" --client-id "$GW_CLIENT_ID" \
  --query UserPoolClient.ClientSecret --output text \
| agentcore add credentials oauth --name ScamShieldGateway-oauth --discovery-url "$DISCOVERY_URL" \
  --client-id "$GW_CLIENT_ID" --scopes scamshield-gateway/invoke --client-secret -
unset GOOGLE_CLIENT_SECRET SAFE_BROWSING_API_KEY
```
- `--scopes` can't be combined with `--provider-configuration`. The Gmail scope (`gmail.modify`) is requested at token
  time by `mcp_server/scamshield/credentials.py`.
- Where the secrets go: the CLI stores them **encrypted** in `agentcore/.env.local` (gitignored, mode 600), using a key in
  the macOS keychain (`aws-agentcore`) or `~/.agentcore/secrets.key`. `agentcore deploy` sends them to AgentCore Identity,
  which keeps them in Secrets Manager. The local copy stays after deploy. To avoid disk entirely, omit `--client-secret`/`--api-key`
  and export `AGENTCORE_CREDENTIAL_GOOGLEGMAIL_CLIENT_SECRET`, `AGENTCORE_CREDENTIAL_SAFEBROWSING` and
  `AGENTCORE_CREDENTIAL_SCAMSHIELDGATEWAY_OAUTH_CLIENT_SECRET` for the `agentcore deploy` command instead.
- Provider names are `ScamShield_default_<credential name>`, matching the MCP env vars above.

### 5. Deploy infra/ first
`cdk-stack.ts` attaches `ScamShieldMcpServerAccess`, so that policy must already exist. Deploy `infra/` as its README says,
with `sesFrom` but without `agentRuntimeArn` for now.

### 6. First deploy
```bash
agentcore deploy --json
```
On a first run this writes the `default` target to `agentcore/aws-targets.json` (the account from STS, `us-east-1`), bootstraps CDK
if needed (`--skip-bootstrap` if someone else did), creates the three credential providers (outside CloudFormation), then
deploys the stack: both runtimes, the gateway with no targets, the policy engine, and the IAM additions.

### 7. Collect outputs; register Google's redirect URI
```bash
STATUS=$(agentcore status --json)
arn_of() { printf '%s' "$STATUS" | jq -r --arg t "$1" --arg n "$2" '.resources[] | select(.resourceType == $t and .name == $n) | .arn'; }
MCP_ARN=$(arn_of runtime ScamShieldMcp);       MCP_ID=${MCP_ARN##*/}
AGENT_ARN=$(arn_of runtime ScamShieldAgent)
GATEWAY_ARN=$(arn_of gateway ScamShieldGateway); GATEWAY_ID=${GATEWAY_ARN##*/}
POLICY_ENGINE_ARN=$(arn_of policy-engine ScamShieldPolicy)
WORKLOAD_ARN=$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$MCP_ID" \
  --query workloadIdentityDetails.workloadIdentityArn --output text); WORKLOAD_NAME=${WORKLOAD_ARN##*/}

# Each OAuth provider gets its own AgentCore callback URL. The CLI doesn't save it, so look it up:
agentcore identity oauth2-credential-provider get --name ScamShield_default_GoogleGmail --json | jq -r .callbackUrl
```
Add that URL under the Web client's **Authorized redirect URIs** in Google Cloud Console.

### 8. Second pass: workload name and the gateway target
```bash
edit_spec --arg wl "$WORKLOAD_NAME" '(.runtimes[] | select(.name == "ScamShieldMcp") | .envVars) |=
  (map(select(.name != "SCAMSHIELD_WORKLOAD_NAME")) + [{name: "SCAMSHIELD_WORKLOAD_NAME", value: $wl}])'

MCP_URL="https://bedrock-agentcore.$AWS_REGION.amazonaws.com/runtimes/$(printf '%s' "$MCP_ARN" | jq -sRr @uri)/invocations?qualifier=DEFAULT"
jq -n --arg url "$MCP_URL" '{name: "scamshield", targetType: "mcpServer", endpoint: $url,
    outboundAuth: {type: "GATEWAY_IAM_ROLE", service: "bedrock-agentcore"}}' \
| agentcore add gateway-target --gateway ScamShieldGateway --target-configuration -
agentcore deploy --json
```
`--runtime ScamShieldMcp` looks like the shortcut for this, but it builds an `httpRuntime` target, and that needs a gateway with
`protocolType: "None"`: `Target "scamshield" is httpRuntime but the Gateway does not have protocolType: "None"`.
An `mcpServer` target can only name a project runtime through its URL, which is why this step waits for the first deploy.
Creating the target syncs the tool list right away (tools/list, signed with the gateway role). If you change the tools later, resync with
`aws bedrock-agentcore-control synchronize-gateway-targets --gateway-identifier "$GATEWAY_ID" --target-id-list <target id from agentcore status>`.

### 9. Smoke test through the gateway
```bash
GW_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id "$POOL_ID" --client-id "$GW_CLIENT_ID" \
  --query UserPoolClient.ClientSecret --output text)
TOKEN=$(curl -s -K <(printf 'user = "%s:%s"\n' "$GW_CLIENT_ID" "$GW_SECRET") \
  -d 'grant_type=client_credentials&scope=scamshield-gateway/invoke' \
  "https://$GW_DOMAIN.auth.$AWS_REGION.amazoncognito.com/oauth2/token" | jq -r .access_token); unset GW_SECRET
printf '%s' "$TOKEN" | agentcore invoke --gateway ScamShieldGateway --path /mcp --method POST \
  --content-type application/json --bearer-token - \
  --payload '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
Expect the five tools, prefixed with the target name (`scamshield___get_new_emails`, ...).

### 10. Hand-offs
- `AGENT_ARN` goes to infra/ for the schedules: redeploy it with `-c agentRuntimeArn=$AGENT_ARN -c scanUsers=<ids>`.
- `GATEWAY_ARN` and `GW_CLIENT_ID` go to the policy generator (step 11).
- Connect Grandma's Gmail through AgentCore Identity. The session-binding return URL must be allowed on the MCP runtime's
  workload identity (AgentCore's session-binding docs require it). If AgentCore rejects a plain-http localhost URL, expose
  the callback over HTTPS (a tunnel) and pass that URL with `--return-url`.
  ```bash
  aws bedrock-agentcore-control update-workload-identity --name "$WORKLOAD_NAME" \
    --allowed-resource-oauth2-return-urls http://localhost:8080/connect/callback http://localhost:8765/callback

  # The demo way: the sign-up site (guardian signs up, then "Connect my Gmail" on the invite page)
  (cd ../web && SCAMSHIELD_CREDENTIALS=agentcore SCAMSHIELD_WORKLOAD_NAME="$WORKLOAD_NAME" \
     SCAMSHIELD_GOOGLE_PROVIDER=ScamShield_default_GoogleGmail SCAMSHIELD_STORE=dynamodb \
     SCAMSHIELD_AGENT_ARN="$AGENT_ARN" uv run python app.py)

  # Or from the command line
  (cd ../mcp_server && SCAMSHIELD_WORKLOAD_NAME="$WORKLOAD_NAME" SCAMSHIELD_GOOGLE_PROVIDER=ScamShield_default_GoogleGmail \
     SCAMSHIELD_STORE=dynamodb uv run scripts/connect_gmail_identity.py --user-id grandma \
     --guardian-email <guardian address> --name <grandma's first name>)
  ```
  After anyone connects, re-run step 11's `sync_policies.py` so Policy allows warnings to their guardian.

### 11. Policies, still in LOG_ONLY
`sync_policies.py` writes one rule-1 policy (the four inbox tools) and one rule-2 policy per user (send_warning only to
that user and their guardian, from DynamoDB) to the git-ignored `policies/generated/`, and prints the `add policy`
commands. Re-run it whenever a guardian changes.
```bash
(cd ../mcp_server && SCAMSHIELD_STORE=dynamodb uv run scripts/sync_policies.py \
   --gateway-arn "$GATEWAY_ARN" --client-id "$GW_CLIENT_ID" --separator ___ --engine ScamShieldPolicy)
# run each printed `agentcore add policy --name ... --engine ScamShieldPolicy --statement file://...` here, then:
agentcore deploy --json
```
Defaults: `--validation-mode fail-on-any-findings` and `--enforcement-mode active` (per policy). While the gateway is in
`LOG_ONLY`, decisions are only logged. `add policy` inlines the statement into `agentcore.json`; `sourceFile` is a note. After
editing a `.cedar` file, run `agentcore remove policy --engine ScamShieldPolicy --name <policy_name>`, then add it again.
To draft Cedar from English: `agentcore gateway policy generate --gateway-id "$GATEWAY_ID" --prompt '<rule in English>'`.

### 12. Switch to ENFORCE
The CLI has no command for this in 1.0.2. Re-running `add policy-engine` fails with
`a policy-engine with name 'ScamShieldPolicy' already exists`, and attaching a different engine replaces this one. Edit the spec instead:
```bash
edit_spec '(.agentCoreGateways[] | select(.name == "ScamShieldGateway") | .policyEngineConfiguration.mode) = "ENFORCE"'
agentcore deploy --json
```
To go back, set it to `"LOG_ONLY"` and deploy again. The CLI flags for this setting are `log-only` | `enforce`;
the JSON values are `LOG_ONLY` | `ENFORCE`.

### Teardown
`agentcore remove all --yes && agentcore deploy --yes` deletes the stack and the credential providers. Also delete the Cognito pool and the Google client.
