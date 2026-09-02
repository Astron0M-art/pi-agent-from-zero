"""工具定义、Schema 校验、Registry、输出截断与 Bash 工具。"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from pi_agent_from_zero.events import (
    CancellationRequested,
    CancellationToken,
    DeadlineExceeded,
)
from pi_agent_from_zero.messages import ToolCall, ToolResultMessage

Approval = Callable[[str], bool]
ToolHandler = Callable[[Mapping[str, object], CancellationToken], "ToolOutcome"]
_TOOL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SCALAR_TYPES = {"string", "integer", "number", "boolean"}


class SchemaDefinitionError(ValueError):
    """工具声明了教学运行时不支持或不合法的 Schema。"""


class SchemaValidationError(ValueError):
    """模型给出的工具参数不符合工具 Schema。"""


class ToolExecutionError(RuntimeError):
    """工具预期内失败，应该安全地回填给模型。"""


@dataclass(frozen=True, slots=True)
class OutputLimits:
    """模型可见工具结果的字符与行数上限。"""

    max_chars: int = 4_000
    max_lines: int = 200

    def __post_init__(self) -> None:
        if self.max_chars < 1 or self.max_lines < 1:
            raise ValueError("output limits must be positive")


def truncate_output(content: str, limits: OutputLimits) -> str:
    """保留结果头部并附截断标记；返回值本身也不超过上限。"""

    lines = content.splitlines()
    total_lines = len(lines)
    if len(content) <= limits.max_chars and total_lines <= limits.max_lines:
        return content

    marker = f"[truncated: {total_lines} lines, {len(content)} chars total]"
    if limits.max_lines == 1:
        return marker[: limits.max_chars]

    visible_lines = lines[: limits.max_lines - 1]
    prefix = "\n".join(visible_lines)
    available = limits.max_chars - len(marker) - 1
    if available <= 0:
        return marker[: limits.max_chars]
    prefix = prefix[:available].rstrip("\n")
    if not prefix:
        return marker[: limits.max_chars]
    return f"{prefix}\n{marker}"


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SchemaDefinitionError("schema keys must be strings")
            frozen[key] = _freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _check_schema(schema: Mapping[str, object]) -> None:
    if schema.get("type") != "object":
        raise SchemaDefinitionError("tool schema type must be object")
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise SchemaDefinitionError("schema.properties must be an object")
    for name, raw_property in properties.items():
        if not isinstance(name, str) or not isinstance(raw_property, Mapping):
            raise SchemaDefinitionError("each property must have a string name and schema")
        property_type = raw_property.get("type")
        if property_type not in _SCALAR_TYPES:
            raise SchemaDefinitionError(
                f"property {name!r} uses unsupported type {property_type!r}"
            )
        if "minLength" in raw_property:
            minimum = raw_property["minLength"]
            if (
                property_type != "string"
                or not isinstance(minimum, int)
                or isinstance(minimum, bool)
                or minimum < 0
            ):
                raise SchemaDefinitionError(f"property {name!r} has invalid minLength")
    required = schema.get("required", ())
    if not isinstance(required, (list, tuple)) or not all(
        isinstance(name, str) for name in required
    ):
        raise SchemaDefinitionError("schema.required must be a list of strings")
    unknown_required = set(required) - set(properties)
    if unknown_required:
        names = ", ".join(sorted(unknown_required))
        raise SchemaDefinitionError(f"required properties are not declared: {names}")
    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, bool):
        raise SchemaDefinitionError("schema.additionalProperties must be boolean")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """可发送给模型的工具名称、说明和 JSON Schema 子集。"""

    name: str
    description: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _TOOL_NAME.fullmatch(self.name):
            raise ValueError(f"invalid tool name: {self.name!r}")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("tool description must not be empty")
        if not isinstance(self.parameters, Mapping):
            raise SchemaDefinitionError("tool parameters must be an object schema")
        frozen = cast(Mapping[str, object], _freeze(self.parameters))
        _check_schema(frozen)
        object.__setattr__(self, "parameters", frozen)


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """工具处理器的结果；Registry 负责补上调用 ID 和工具名。"""

    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Tool:
    definition: ToolDefinition
    execute: ToolHandler


def _matches_type(value: object, expected: object) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def validate_arguments(
    schema: Mapping[str, object], arguments: Mapping[str, object]
) -> Mapping[str, object]:
    """验证顶层对象和标量属性，返回不可变参数副本。"""

    properties = cast(Mapping[str, object], schema.get("properties", {}))
    required = cast(tuple[str, ...], schema.get("required", ()))
    for name in required:
        if name not in arguments:
            raise SchemaValidationError(f"arguments.{name}: is required")

    if schema.get("additionalProperties", True) is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise SchemaValidationError(
                f"arguments.{unknown[0]}: additional property is not allowed"
            )

    for name, value in arguments.items():
        raw_property = properties.get(name)
        if raw_property is None:
            continue
        property_schema = cast(Mapping[str, object], raw_property)
        expected = property_schema["type"]
        if not _matches_type(value, expected):
            raise SchemaValidationError(f"arguments.{name}: expected {expected}")
        minimum = property_schema.get("minLength")
        if isinstance(minimum, int) and isinstance(value, str) and len(value) < minimum:
            raise SchemaValidationError(f"arguments.{name}: length must be at least {minimum}")

    return MappingProxyType(dict(arguments))


class ToolRegistry:
    """工具声明与执行的唯一入口。"""

    def __init__(self, tools: Iterable[Tool], *, output_limits: OutputLimits | None = None) -> None:
        by_name: dict[str, Tool] = {}
        for tool in tools:
            name = tool.definition.name
            if name in by_name:
                raise ValueError(f"duplicate tool name: {name}")
            by_name[name] = tool
        self._tools = MappingProxyType(by_name)
        self._definitions = tuple(tool.definition for tool in by_name.values())
        self._output_limits = output_limits or OutputLimits()

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return self._definitions

    def execute(self, call: ToolCall, cancellation: CancellationToken) -> ToolResultMessage:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._error(call, f"tool not found: {call.name}")
        try:
            arguments = validate_arguments(tool.definition.parameters, call.arguments)
            cancellation.checkpoint()
            outcome = tool.execute(arguments, cancellation)
            if not isinstance(outcome, ToolOutcome):
                raise TypeError("tool handler must return ToolOutcome")
            if not isinstance(outcome.content, str) or not isinstance(outcome.is_error, bool):
                raise TypeError("ToolOutcome must contain string content and bool is_error")
            return ToolResultMessage(
                call.id,
                call.name,
                truncate_output(outcome.content or "(no output)", self._output_limits),
                is_error=outcome.is_error,
            )
        except (CancellationRequested, DeadlineExceeded):
            raise
        except SchemaValidationError as error:
            return self._error(call, f"invalid arguments: {error}")
        except ToolExecutionError as error:
            return self._error(call, str(error))
        except Exception as error:
            return self._error(call, f"tool execution failed: {error}")

    @staticmethod
    def _error(call: ToolCall, message: str) -> ToolResultMessage:
        return ToolResultMessage(call.id, call.name, message, is_error=True)


def create_bash_tool(
    approve: Approval,
    *,
    cwd: Path | None = None,
    timeout_seconds: float = 10,
) -> Tool:
    """构造当前唯一带副作用的工具；审批仍由宿主提供。"""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    working_directory = (cwd or Path.cwd()).resolve()
    definition = ToolDefinition(
        name="bash",
        description="Run one Bash command in the current project after approval.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "minLength": 1},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    )

    def execute(arguments: Mapping[str, object], cancellation: CancellationToken) -> ToolOutcome:
        command = cast(str, arguments["command"])
        cancellation.checkpoint()
        if not approve(command):
            return ToolOutcome("user denied the bash command", is_error=True)
        cancellation.checkpoint()
        try:
            process = subprocess.Popen(
                ["bash", "-lc", command],
                cwd=working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            raise ToolExecutionError(f"could not start command: {error}") from error

        started_at = time.monotonic()
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                try:
                    cancellation.checkpoint()
                except (CancellationRequested, DeadlineExceeded):
                    _stop_process(process)
                    raise
                if time.monotonic() - started_at >= timeout_seconds:
                    _stop_process(process)
                    return ToolOutcome(
                        f"command timed out after {timeout_seconds:g}s", is_error=True
                    )

        output = stdout + stderr
        is_error = process.returncode != 0
        if is_error:
            output += f"\ncommand exited with {process.returncode}"
        return ToolOutcome(output or "(no output)", is_error=is_error)

    return Tool(definition, execute)


def _stop_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.communicate(timeout=0.2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
