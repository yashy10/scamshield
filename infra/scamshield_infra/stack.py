"""ScamShieldInfra: the few AWS resources ScamShield needs outside AgentCore itself.

The AgentCore Runtime, Gateway, Identity and Policy resources are created by the AgentCore CLI.
This stack holds what they use: the verdict table, the SES identities, an IAM policy to attach
to the MCP server runtime's execution role, and the schedules that start a scan every 5 minutes.

Context (all optional; pass with `cdk deploy -c key=value`):
    sesFrom           verified sender address for warning emails
    sesIdentities     comma-separated recipient addresses (the SES sandbox needs each one verified)
    agentRuntimeArn   ARN of the agent runtime the schedules invoke
    scanUsers         comma-separated user ids to scan, e.g. "grandma"
    schedulesEnabled  "true" to create the schedules ENABLED (default: DISABLED)
"""

from __future__ import annotations

import json
import re

from aws_cdk import Annotations, Aws, CfnOutput, RemovalPolicy, Stack, Token
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_ses as ses
from constructs import Construct

TABLE_NAME = "ScamShield"
MCP_POLICY_NAME = "ScamShieldMcpServerAccess"

# EventBridge Scheduler universal target: Scheduler calls the AWS SDK API directly.
INVOKE_AGENT_RUNTIME_TARGET = "arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime"

# InvokeAgentRuntime requires runtimeSessionId to be 33-256 characters. Scheduler replaces
# <aws.scheduler.execution-id> with a unique id per invocation attempt (documented example:
# "d32c5kddcf5bb8c3"), so every scan gets a fresh session. The documented length of the id is
# only an example, so the fixed prefix alone is >= 33 characters and the minimum always holds.
SESSION_ID_PREFIX = "scamshield-scheduled-scan-session-"
EXECUTION_ID = "<aws.scheduler.execution-id>"

_EMAIL = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")
# User ids end up in schedule names ([0-9a-zA-Z-_.]+, max 64) and session ids.
_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_RUNTIME_ARN = re.compile(r"^arn:aws[a-z-]*:bedrock-agentcore:([a-z0-9-]+):(\d{12}):runtime/[A-Za-z0-9_-]+$")


def _csv(value: object) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    return [str(i).strip() for i in items if str(i).strip()]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "enabled", "on"}


def scan_input(agent_runtime_arn: str, user_id: str) -> str:
    """The schedule's Input: the InvokeAgentRuntime request, as JSON.

    Payload is the raw JSON string the agent's entrypoint receives, not base64. The API models
    it as a blob, but Scheduler passes the member through as written; base64 reached the handler
    as base64 text and broke it.
    """
    return json.dumps(
        {
            "AgentRuntimeArn": agent_runtime_arn,
            "RuntimeSessionId": f"{SESSION_ID_PREFIX}{user_id}-{EXECUTION_ID}",
            "Payload": json.dumps({"user_id": user_id}),
            "ContentType": "application/json",
        }
    )


class ScamShieldInfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- 1. Verdict table. Holds verdicts and user->guardian links, never email bodies.
        # Shape matches DynamoStore in mcp_server/scamshield/store.py:
        #   pk = "USER#<id>", sk = "PROFILE" | "EMAIL#<email id>"
        table = dynamodb.Table(
            self,
            "Table",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # hackathon; nothing in it is irreplaceable
        )

        # --- 2. SES email identities. Creating one makes SES email that address a verification link.
        ses_from = str(self.node.try_get_context("sesFrom") or "").strip() or None
        recipients = _csv(self.node.try_get_context("sesIdentities"))
        addresses: dict[str, str] = {}  # lowercased -> as given; dedupes sender/recipient overlap
        for address in ([ses_from] if ses_from else []) + recipients:
            if not _EMAIL.match(address):
                raise ValueError(f"Not an email address in sesFrom/sesIdentities: {address!r}")
            addresses.setdefault(address.lower(), address)
        for key, address in addresses.items():
            # Construct id from the address, so editing the list never replaces (and
            # re-verifies) an identity that stays in it.
            ses.EmailIdentity(self, f"EmailIdentity-{key}", identity=ses.Identity.email(address))
        if recipients and not ses_from:
            Annotations.of(self).add_warning_v2(
                "scamshield:sesFromMissing",
                "sesIdentities given without sesFrom: identities are created, but the MCP server "
                "policy grants no ses:SendEmail until sesFrom is set.",
            )

        # --- 3. Policy for the MCP server runtime's execution role (that role comes from the
        # AgentCore CLI; attach this policy to it after both exist).
        statements = [
            iam.PolicyStatement(
                sid="VerdictTable",
                actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:BatchGetItem"],
                resources=[table.table_arn],
            ),
        ]
        if ses_from:
            # Least privilege for SESv2 SendEmail (IAM action ses:SendEmail) is BOTH:
            #  - Resource = the identity ARNs in this stack, not "*". SES authorizes SendEmail
            #    against the identity resources the message uses; scoping to these ARNs means no
            #    other identity in the account can be used. Recipient identities are listed too:
            #    in the sandbox every recipient is a verified identity in this account, and SES
            #    has been reported to authorize against those as well. That adds nothing an
            #    attacker could use, because the From address is pinned below.
            #  - ses:FromAddress = sesFrom, so even with a recipient identity in Resource the From
            #    header can only ever be the ScamShield sender.
            # "*" plus the condition alone would leave every other identity in the account (and
            # any configuration set) usable as a resource, so the scoped form is strictly tighter.
            statements.append(
                iam.PolicyStatement(
                    sid="SendWarningEmail",
                    actions=["ses:SendEmail"],
                    resources=[
                        f"arn:{Aws.PARTITION}:ses:{Aws.REGION}:{Aws.ACCOUNT_ID}:identity/{address}"
                        for address in addresses.values()
                    ],
                    conditions={"StringEquals": {"ses:FromAddress": ses_from}},
                )
            )
        agentcore = f"arn:{Aws.PARTITION}:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}"
        statements += [
            # AgentCore Identity: the server fetches the user's Gmail OAuth token and the Safe
            # Browsing API key from the token vault on each call.
            iam.PolicyStatement(
                sid="AgentCoreIdentityReads",
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetResourceApiKey",
                ],
                resources=[
                    f"{agentcore}:workload-identity-directory/default*",
                    f"{agentcore}:token-vault/*",
                ],
            ),
            # The token vault keeps credential-provider secrets (OAuth client secret, API key) in
            # Secrets Manager. TODO: narrow to the credential providers' secret ARNs once they
            # exist (each provider reports its secret ARN), instead of every secret here.
            iam.PolicyStatement(
                sid="CredentialProviderSecrets",
                actions=["secretsmanager:GetSecretValue"],
                resources=[f"arn:{Aws.PARTITION}:secretsmanager:{Aws.REGION}:{Aws.ACCOUNT_ID}:secret:*"],
            ),
        ]
        mcp_policy = iam.ManagedPolicy(
            self,
            "McpServerAccess",
            managed_policy_name=MCP_POLICY_NAME,
            description="ScamShield MCP server runtime: verdict table, SES warnings, AgentCore Identity reads.",
            statements=statements,
        )

        # --- 4. Scan schedules: Scheduler invokes the agent runtime once per user every 5 minutes.
        runtime_arn = str(self.node.try_get_context("agentRuntimeArn") or "").strip() or None
        scan_users = _csv(self.node.try_get_context("scanUsers"))
        state = "ENABLED" if _truthy(self.node.try_get_context("schedulesEnabled")) else "DISABLED"
        for user_id in scan_users:
            if not _USER_ID.match(user_id):
                raise ValueError(f"scanUsers ids must match {_USER_ID.pattern}: {user_id!r}")
        if scan_users and not runtime_arn:
            Annotations.of(self).add_warning_v2(
                "scamshield:runtimeArnMissing", "scanUsers given without agentRuntimeArn: no schedules created."
            )

        if runtime_arn:
            match = _RUNTIME_ARN.match(runtime_arn)
            if not match:
                raise ValueError(
                    "agentRuntimeArn must look like "
                    f"arn:aws:bedrock-agentcore:<region>:<account>:runtime/<id>, got {runtime_arn!r}"
                )
            if not Token.is_unresolved(self.region) and match.group(1) != self.region:
                Annotations.of(self).add_warning_v2(
                    "scamshield:runtimeRegion",
                    f"agentRuntimeArn is in {match.group(1)} but this stack deploys to {self.region}.",
                )

            scheduler_role = iam.Role(
                self,
                "SchedulerRole",
                description="EventBridge Scheduler: invoke the ScamShield agent runtime.",
                assumed_by=iam.ServicePrincipal(
                    "scheduler.amazonaws.com",
                    conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}},
                ),
            )
            scheduler_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[runtime_arn, f"{runtime_arn}/*"],  # runtime and its endpoints
                )
            )
            if not scan_users:
                Annotations.of(self).add_warning_v2(
                    "scamshield:scanUsersMissing", "agentRuntimeArn given without scanUsers: no schedules created."
                )
            for user_id in scan_users:
                schedule = scheduler.CfnSchedule(
                    self,
                    f"Scan-{user_id}",
                    name=f"ScamShieldScan-{user_id}",
                    description=f"ScamShield: scan {user_id}'s inbox",
                    schedule_expression="rate(5 minutes)",
                    flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
                    state=state,
                    target=scheduler.CfnSchedule.TargetProperty(
                        arn=INVOKE_AGENT_RUNTIME_TARGET,
                        role_arn=scheduler_role.role_arn,
                        input=scan_input(runtime_arn, user_id),
                        # The next run is 5 minutes away; a retry would just overlap it.
                        retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(maximum_retry_attempts=0),
                    ),
                )
                # Create the role's policy before the schedule, so the first run is authorized.
                schedule.node.add_dependency(scheduler_role)

            CfnOutput(self, "SchedulerRoleArn", value=scheduler_role.role_arn)

        # --- 5. Outputs
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "McpServerPolicyArn", value=mcp_policy.managed_policy_arn)
