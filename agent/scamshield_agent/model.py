"""Claude Opus 5.5 on Amazon Bedrock, as a Strands model.

Two ways to reach Claude on Bedrock, picked with SCAMSHIELD_MODEL_PROVIDER:

converse (default): the bedrock-runtime Converse API through Strands' native BedrockModel, with a
    cross-region inference profile such as "us.anthropic.claude-opus-5-5". This is the path the
    hackathon account allows (IAM: bedrock:InvokeModel / InvokeModelWithResponseStream).
mantle: Claude in Amazon Bedrock, the Messages API on the bedrock-mantle endpoint, through Strands'
    AnthropicModel with its client swapped for AsyncAnthropicBedrockMantle (model id
    "anthropic.claude-opus-5-5"). The hackathon organization's SCP denies bedrock-mantle:CreateInference.
"""

from __future__ import annotations

from strands.models import Model

from .config import AgentSettings


def build_model(cfg: AgentSettings) -> Model:
    # Opus 5.5 always thinks (adaptive) and defaults to medium effort; set it explicitly.
    # No temperature/top_p: current Claude models reject sampling parameters.
    effort = {"output_config": {"effort": cfg.effort}}

    if cfg.model_provider == "converse":
        from botocore.config import Config
        from strands.models.bedrock import BedrockModel

        return BedrockModel(
            model_id=cfg.model_id,
            region_name=cfg.region,
            max_tokens=cfg.max_tokens,
            additional_request_fields=effort,
            # One turn can think about ten emails before it streams anything, and Bedrock sometimes
            # throttles or drops a stream: wait longer and retry with backoff instead of failing the scan.
            boto_client_config=Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 6, "mode": "adaptive"}),
        )

    if cfg.model_provider == "mantle":
        from anthropic import AsyncAnthropicBedrockMantle
        from strands.models.anthropic import AnthropicModel

        model = AnthropicModel(model_id=cfg.model_id, max_tokens=cfg.max_tokens, params=effort)
        model.client = AsyncAnthropicBedrockMantle(aws_region=cfg.region)
        return model

    raise ValueError(f"Unknown SCAMSHIELD_MODEL_PROVIDER: {cfg.model_provider!r}")
