"""Strands hooks: pin user_id on every tool call, and keep a compact log of tool calls."""

from __future__ import annotations

import logging
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

log = logging.getLogger("scamshield.agent")


class PinUserId(HookProvider):
    """Overwrite `user_id` on every tool call with the user this scan runs for.

    The model never chooses whose inbox it touches. A different value from the model (for example
    one injected by an email) is replaced and counted. At the Gateway, Policy enforces the same thing.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.overrides = 0

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._pin)

    def _pin(self, event: BeforeToolCallEvent) -> None:
        tool_input = event.tool_use.get("input")
        if not isinstance(tool_input, dict) or not _takes_user_id(event, tool_input):
            return
        supplied = tool_input.get("user_id")
        if supplied != self.user_id:
            if supplied is not None:
                self.overrides += 1
                log.warning("Model supplied user_id %r for %s; pinned to %r", supplied, event.tool_use.get("name"), self.user_id)
            tool_input["user_id"] = self.user_id


def _takes_user_id(event: BeforeToolCallEvent, tool_input: dict) -> bool:
    tool = event.selected_tool
    if tool is None:
        return "user_id" in tool_input
    props = tool.tool_spec.get("inputSchema", {}).get("json", {}).get("properties", {})
    return "user_id" in props


class ToolLog(HookProvider):
    """Records each tool call's name, arguments and status (no tool results: they hold email text)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._record)

    def _record(self, event: AfterToolCallEvent) -> None:
        status = (event.result or {}).get("status", "error" if event.exception else "unknown")
        self.calls.append({"tool": event.tool_use.get("name"), "input": event.tool_use.get("input"), "status": status})
