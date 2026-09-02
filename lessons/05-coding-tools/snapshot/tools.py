"""最小 Tool Registry、统一输出截断和 Bash 工具。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from events import CancellationToken, Cancelled
from messages import ToolCall, ToolResultMessage

ToolHandler = Callable[[Mapping[str, object], CancellationToken], "ToolOutcome"]
Approval = Callable[[str], bool]


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Mapping[str, object]


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Tool:
    definition: ToolDefinition
    execute: ToolHandler


@dataclass(frozen=True)
class OutputLimits:
    max_chars: int = 4_000
    max_lines: int = 200

    def __post_init__(self) -> None:
        if self.max_chars < 1 or self.max_lines < 1:
            raise ValueError("output limits must be positive")


def truncate_output(content: str, limits: OutputLimits) -> str:
    lines = content.splitlines()
    if len(content) <= limits.max_chars and len(lines) <= limits.max_lines:
        return content
    marker = f"[truncated: {len(lines)} lines, {len(content)} chars total]"
    if limits.max_lines == 1:
        return marker[: limits.max_chars]
    available = limits.max_chars - len(marker) - 1
    if available <= 0:
        return marker[: limits.max_chars]
    prefix = "\n".join(lines[: limits.max_lines - 1])[:available].rstrip("\n")
    return f"{prefix}\n{marker}" if prefix else marker[: limits.max_chars]


def validate_arguments(
    schema: Mapping[str, object], arguments: Mapping[str, object]
) -> Mapping[str, object]:
    properties = cast(Mapping[str, Mapping[str, object]], schema["properties"])
    required = cast(list[str], schema.get("required", []))
    for name in required:
        if name not in arguments:
            raise ValueError(f"arguments.{name}: is required")
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise ValueError(f"arguments.{unknown[0]}: additional property is not allowed")
    for name, value in arguments.items():
        if name not in properties:
            continue
        expected = properties[name]["type"]
        valid = (expected == "string" and isinstance(value, str)) or (
            expected == "integer" and isinstance(value, int) and not isinstance(value, bool)
        )
        if not valid:
            raise ValueError(f"arguments.{name}: expected {expected}")
        minimum = properties[name].get("minLength")
        if isinstance(value, str) and isinstance(minimum, int) and len(value) < minimum:
            raise ValueError(f"arguments.{name}: length must be at least {minimum}")
    return MappingProxyType(dict(arguments))


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool], *, output_limits: OutputLimits | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.definition.name in self._tools:
                raise ValueError(f"duplicate tool name: {tool.definition.name}")
            self._tools[tool.definition.name] = tool
        self.output_limits = output_limits or OutputLimits()

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    def execute(self, call: ToolCall, token: CancellationToken) -> ToolResultMessage:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResultMessage(call.id, call.name, f"tool not found: {call.name}", True)
        try:
            arguments = validate_arguments(tool.definition.parameters, call.arguments)
        except ValueError as error:
            return ToolResultMessage(call.id, call.name, f"invalid arguments: {error}", True)
        try:
            token.checkpoint()
            outcome = tool.execute(arguments, token)
            return ToolResultMessage(
                call.id,
                call.name,
                truncate_output(outcome.content or "(no output)", self.output_limits),
                outcome.is_error,
            )
        except Cancelled:
            raise
        except ToolExecutionError as error:
            return ToolResultMessage(call.id, call.name, str(error), True)
        except Exception as error:
            return ToolResultMessage(call.id, call.name, f"tool execution failed: {error}", True)


def create_bash_tool(approve: Callable[[str], bool], cwd: Path) -> Tool:
    definition = ToolDefinition(
        "bash",
        "Run one approved Bash command.",
        {
            "type": "object",
            "properties": {"command": {"type": "string", "minLength": 1}},
            "required": ["command"],
            "additionalProperties": False,
        },
    )

    def execute(arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        command = cast(str, arguments["command"])
        token.checkpoint()
        if not approve(command):
            return ToolOutcome("user denied the bash command", True)
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        content = completed.stdout + completed.stderr
        if completed.returncode:
            content += f"\ncommand exited with {completed.returncode}"
        return ToolOutcome(content or "(no output)", completed.returncode != 0)

    return Tool(definition, execute)
