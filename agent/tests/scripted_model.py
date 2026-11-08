"""A Strands model that replays scripted assistant turns, so the agent loop can be tested
end to end without Bedrock. Each turn is a list of ("tool", name, input) or ("text", str)."""

from __future__ import annotations

import copy
import json
from typing import Any

from strands.models import Model


class ScriptedModel(Model):
    def __init__(self, turns: list[list[tuple]]) -> None:
        self.turns = list(turns)
        self.requests: list[dict[str, Any]] = []
        self.config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("ScamShield never uses structured output")
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.requests.append(
            {"system": system_prompt, "tools": [t["name"] for t in tool_specs or []], "messages": copy.deepcopy(messages)}
        )
        turn = self.turns.pop(0)
        n = len(self.requests)
        yield {"messageStart": {"role": "assistant"}}
        used_tool = False
        for i, item in enumerate(turn):
            if item[0] == "text":
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": item[1]}}}
            else:
                used_tool = True
                _, name, args = item
                yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"call-{n}-{i}", "name": name}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use" if used_tool else "end_turn"}}


def tool_results(messages: list[dict]) -> dict[str, list[dict]]:
    """Map toolUseId -> the toolResult content blocks found in a conversation."""
    found: dict[str, list[dict]] = {}
    for message in messages:
        for block in message.get("content", []):
            if "toolResult" in block:
                found[block["toolResult"]["toolUseId"]] = block["toolResult"]["content"]
    return found
