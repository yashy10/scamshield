#!/usr/bin/env python3
import aws_cdk as cdk

from scamshield_infra.stack import ScamShieldInfraStack

app = cdk.App()
ScamShieldInfraStack(
    app,
    "ScamShieldInfra",
    # Region is pinned; the account comes from your credentials at deploy time.
    env=cdk.Environment(region="us-east-1"),
    description="ScamShield: verdict table, SES identities, MCP server policy, scan schedules.",
)
app.synth()
