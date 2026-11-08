import base64
import binascii
import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from scamshield_infra.stack import EXECUTION_ID, INVOKE_AGENT_RUNTIME_TARGET, ScamShieldInfraStack

RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/scamshield_agent-AbC123xyz"


def synth(**context) -> Template:
    app = cdk.App(context=context)
    stack = ScamShieldInfraStack(app, "ScamShieldInfra", env=cdk.Environment(region="us-east-1"))
    return Template.from_stack(stack)


def policy_statements(template: Template) -> list[dict]:
    policies = template.find_resources(
        "AWS::IAM::ManagedPolicy", {"Properties": {"ManagedPolicyName": "ScamShieldMcpServerAccess"}}
    )
    assert len(policies) == 1
    (policy,) = policies.values()
    return policy["Properties"]["PolicyDocument"]["Statement"]


def actions(statements: list[dict]) -> set[str]:
    found: set[str] = set()
    for s in statements:
        found |= {s["Action"]} if isinstance(s["Action"], str) else set(s["Action"])
    return found


def schedules(template: Template) -> list[dict]:
    return [r["Properties"] for r in template.find_resources("AWS::Scheduler::Schedule").values()]


# --- table


def test_table_key_schema_and_billing():
    t = synth()
    t.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "ScamShield",
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": Match.array_equals(
                [
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ]
            ),
            "BillingMode": "PAY_PER_REQUEST",
        },
    )
    t.has_resource("AWS::DynamoDB::Table", {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"})


# --- MCP server policy


def test_policy_actions_without_ses():
    t = synth()
    assert actions(policy_statements(t)) == {
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:BatchGetItem",
        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        "bedrock-agentcore:GetResourceOauth2Token",
        "bedrock-agentcore:GetResourceApiKey",
        "secretsmanager:GetSecretValue",
    }
    t.resource_count_is("AWS::SES::EmailIdentity", 0)


def test_policy_table_statement_scoped_to_table():
    t = synth()
    (table_id,) = t.find_resources("AWS::DynamoDB::Table")
    (stmt,) = [s for s in policy_statements(t) if s.get("Sid") == "VerdictTable"]
    assert stmt["Resource"] == {"Fn::GetAtt": [table_id, "Arn"]}


def test_policy_agentcore_resources_use_pseudo_parameters():
    (stmt,) = [s for s in policy_statements(synth()) if s.get("Sid") == "AgentCoreIdentityReads"]
    rendered = json.dumps(stmt["Resource"])
    assert "AWS::AccountId" in rendered and "AWS::Region" in rendered
    assert "workload-identity-directory/default*" in rendered
    assert "token-vault/*" in rendered
    assert "111111111111" not in rendered


def test_ses_identities_and_send_permission():
    t = synth(sesFrom="alerts@example.com", sesIdentities="grandma@example.com, guardian@example.com,Alerts@example.com")
    # sender + 2 recipients; the duplicate sender (different case) is dropped
    t.resource_count_is("AWS::SES::EmailIdentity", 3)
    t.has_resource_properties("AWS::SES::EmailIdentity", {"EmailIdentity": "alerts@example.com"})
    t.has_resource_properties("AWS::SES::EmailIdentity", {"EmailIdentity": "guardian@example.com"})

    (stmt,) = [s for s in policy_statements(t) if s.get("Sid") == "SendWarningEmail"]
    assert stmt["Action"] == "ses:SendEmail"
    assert stmt["Condition"] == {"StringEquals": {"ses:FromAddress": "alerts@example.com"}}
    rendered = json.dumps(stmt["Resource"])
    assert stmt["Resource"] != "*"
    for address in ("alerts@example.com", "grandma@example.com", "guardian@example.com"):
        assert f":identity/{address}" in rendered


def test_invalid_ses_address_rejected():
    with pytest.raises(ValueError, match="Not an email"):
        synth(sesFrom="not-an-address")


# --- schedules


def test_no_schedule_without_runtime_context():
    t = synth(scanUsers="grandma")
    t.resource_count_is("AWS::Scheduler::Schedule", 0)
    t.resource_count_is("AWS::IAM::Role", 0)
    assert "SchedulerRoleArn" not in t.find_outputs("*")


def test_schedule_targets_agent_runtime():
    t = synth(agentRuntimeArn=RUNTIME_ARN, scanUsers="grandma")
    (props,) = schedules(t)
    assert props["ScheduleExpression"] == "rate(5 minutes)"
    assert props["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert props["State"] == "DISABLED"
    target = props["Target"]
    assert target["Arn"] == INVOKE_AGENT_RUNTIME_TARGET == "arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime"
    assert target["RetryPolicy"] == {"MaximumRetryAttempts": 0}

    request = json.loads(target["Input"])
    assert request["AgentRuntimeArn"] == RUNTIME_ARN
    assert request["ContentType"] == "application/json"

    payload = request["Payload"]
    assert isinstance(payload, str)
    assert json.loads(payload) == {"user_id": "grandma"}  # raw JSON text...
    with pytest.raises((binascii.Error, ValueError)):  # ...not base64
        base64.b64decode(payload, validate=True)

    session_id = request["RuntimeSessionId"]
    assert session_id.endswith(EXECUTION_ID)
    assert len(session_id.removesuffix(EXECUTION_ID)) >= 33  # API minimum, before substitution
    assert len(session_id) <= 256

    t.has_output("SchedulerRoleArn", {})


def test_one_schedule_per_user_and_enabled_flag():
    t = synth(agentRuntimeArn=RUNTIME_ARN, scanUsers="grandma, grandpa", schedulesEnabled="true")
    found = {json.loads(json.loads(p["Target"]["Input"])["Payload"])["user_id"]: p for p in schedules(t)}
    assert set(found) == {"grandma", "grandpa"}
    assert all(p["State"] == "ENABLED" for p in found.values())
    assert found["grandpa"]["Name"] == "ScamShieldScan-grandpa"


def test_scheduler_role_trust_and_permission():
    t = synth(agentRuntimeArn=RUNTIME_ARN, scanUsers="grandma")
    t.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "scheduler.amazonaws.com"},
                        "Condition": {"StringEquals": {"aws:SourceAccount": {"Ref": "AWS::AccountId"}}},
                    }
                ]
            }
        },
    )
    t.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": [
                    {
                        "Action": "bedrock-agentcore:InvokeAgentRuntime",
                        "Effect": "Allow",
                        "Resource": [RUNTIME_ARN, f"{RUNTIME_ARN}/*"],
                    }
                ]
            }
        },
    )


@pytest.mark.parametrize(
    "context, message",
    [
        ({"agentRuntimeArn": "arn:aws:lambda:us-east-1:111111111111:function:x", "scanUsers": "grandma"}, "agentRuntimeArn"),
        ({"agentRuntimeArn": RUNTIME_ARN, "scanUsers": "grand ma"}, "scanUsers"),
    ],
)
def test_bad_schedule_context_rejected(context, message):
    with pytest.raises(ValueError, match=message):
        synth(**context)
