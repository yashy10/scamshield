import { AgentCoreApplication, type AgentCoreApplicationProps } from '@aws/agentcore-cdk';
import { Stack, type StackProps } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface AgentCoreStackProps extends StackProps {
  /** Props for the AgentCore application, produced by transformAgentCoreJson from agentcore/agentcore.json. */
  application: AgentCoreApplicationProps;
}

/** Created by the infra/ CDK app (ScamShieldInfra): verdict table, SES send, Identity reads. */
const MCP_SERVER_ACCESS_POLICY = 'ScamShieldMcpServerAccess';
/** The DynamoDB table created by infra/ (user -> guardian links, verdicts). */
const VERDICT_TABLE = 'ScamShield';

/**
 * The stack the AgentCore CLI deploys. Everything declared in agentcore/agentcore.json is
 * created by the AgentCoreApplication construct. The two additions below are what
 * agentcore.json can't express (see deploy/README.md).
 */
export class AgentCoreStack extends Stack {
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);
    this.application = new AgentCoreApplication(this, 'Application', props.application);

    const mcpServer = this.application.runtime('ScamShieldMcp');
    const gateway = this.application.gateway('ScamShieldGateway');

    // 1. The gateway's `scamshield` target is an mcpServer target that signs with the gateway
    //    role (GATEWAY_IAM_ROLE, service bedrock-agentcore). The construct grants
    //    InvokeAgentRuntime only for httpRuntime targets, so grant it here. A separate Policy,
    //    not the role's DefaultPolicy: every runtime already depends on the gateway (it gets
    //    AGENTCORE_GATEWAY_* env vars), so a DefaultPolicy grant could form a dependency cycle.
    new iam.Policy(this, 'GatewayInvokesMcpServer', {
      roles: [gateway.role],
      statements: [
        new iam.PolicyStatement({
          actions: ['bedrock-agentcore:InvokeAgentRuntime'],
          resources: [mcpServer.runtimeArn, `${mcpServer.runtimeArn}/runtime-endpoint/*`],
        }),
      ],
    });

    // 2. The MCP server's DynamoDB / SES / Identity permissions live in infra/, which can't see
    //    this role. Attach that managed policy by name; deploy infra/ first.
    mcpServer.role.addManagedPolicy(
      iam.ManagedPolicy.fromManagedPolicyName(this, 'McpServerAccess', MCP_SERVER_ACCESS_POLICY),
    );

    // 3. The agent reads the protected user's profile (their address and their guardian's, which go
    //    into its system prompt) and calls Claude through bedrock-runtime (Converse/ConverseStream)
    //    with the US cross-region inference profile. The profile routes to several US regions, so the
    //    underlying foundation-model grant uses a region wildcard. (The hackathon organization's SCP
    //    denies the newer bedrock-mantle endpoint, so that path isn't granted.)
    const agent = this.application.runtime('ScamShieldAgent');
    new iam.Policy(this, 'AgentAccess', {
      roles: [agent.role],
      statements: [
        new iam.PolicyStatement({
          actions: ['dynamodb:GetItem'],
          resources: [`arn:${this.partition}:dynamodb:${this.region}:${this.account}:table/${VERDICT_TABLE}`],
        }),
        new iam.PolicyStatement({
          actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
          resources: [
            `arn:${this.partition}:bedrock:${this.region}:${this.account}:inference-profile/us.anthropic.claude-*`,
            `arn:${this.partition}:bedrock:*::foundation-model/anthropic.claude-*`,
          ],
        }),
      ],
    });
  }
}
