import os
import time
from collections.abc import Mapping

import pytest

from pi_agent_from_zero import (
    CancellationRequested,
    CancellationToken,
    DeadlineExceeded,
    SchemaDefinitionError,
    SchemaValidationError,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolExecutionError,
    ToolOutcome,
    ToolRegistry,
    ToolResultMessage,
    create_bash_tool,
    validate_arguments,
)
from pi_agent_from_zero import tools as tools_module


def definition(name: str = "echo") -> ToolDefinition:
    return ToolDefinition(
        name,
        "Echo one message.",
        {
            "type": "object",
            "properties": {
                "message": {"type": "string", "minLength": 1},
                "count": {"type": "integer"},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    )


def test_definition_is_frozen_and_registry_rejects_duplicates() -> None:
    source: dict[str, object] = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
    }
    tool_definition = ToolDefinition("echo", "Echo.", source)
    source["type"] = "string"

    assert tool_definition.parameters["type"] == "object"
    with pytest.raises(TypeError):
        tool_definition.parameters["type"] = "string"

    tool = Tool(tool_definition, lambda _args, _token: ToolOutcome("ok"))
    with pytest.raises(ValueError, match="duplicate tool name"):
        ToolRegistry([tool, tool])


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string"},
        {"type": "object", "properties": {"x": {"type": "array"}}},
        {"type": "object", "properties": {}, "required": ["missing"]},
    ],
)
def test_malformed_or_unsupported_schema_fails_at_registration(
    schema: dict[str, object],
) -> None:
    with pytest.raises(SchemaDefinitionError):
        ToolDefinition("broken", "Broken.", schema)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "arguments.message: is required"),
        ({"message": ""}, "arguments.message: length must be at least 1"),
        ({"message": 7}, "arguments.message: expected string"),
        ({"message": "ok", "extra": True}, "arguments.extra: additional property"),
        ({"message": "ok", "count": True}, "arguments.count: expected integer"),
    ],
)
def test_schema_validation_reports_stable_paths(arguments: dict[str, object], message: str) -> None:
    with pytest.raises(SchemaValidationError, match=message):
        validate_arguments(definition().parameters, arguments)


def test_registry_executes_validated_arguments_and_correlates_result() -> None:
    observed: list[Mapping[str, object]] = []

    def execute(arguments: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
        observed.append(arguments)
        return ToolOutcome(f"echo: {arguments['message']}")

    registry = ToolRegistry([Tool(definition(), execute)])

    result = registry.execute(ToolCall("call-7", "echo", {"message": "hello"}), CancellationToken())

    assert result == ToolResultMessage("call-7", "echo", "echo: hello")
    assert observed == [{"message": "hello"}]


def test_invalid_arguments_never_execute_handler() -> None:
    executed = False

    def execute(_arguments: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
        nonlocal executed
        executed = True
        return ToolOutcome("must not happen")

    registry = ToolRegistry([Tool(definition(), execute)])

    result = registry.execute(ToolCall("bad", "echo", {}), CancellationToken())

    assert executed is False
    assert result.is_error is True
    assert result.content == "invalid arguments: arguments.message: is required"


def test_expected_and_unexpected_tool_failures_are_normalized() -> None:
    def expected(_arguments: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
        raise ToolExecutionError("domain failure")

    def unexpected(_arguments: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
        raise RuntimeError("implementation failure")

    valid_call = ToolCall("one", "expected", {"message": "x"})
    registry = ToolRegistry(
        [
            Tool(definition("expected"), expected),
            Tool(definition("unexpected"), unexpected),
        ]
    )

    assert registry.execute(valid_call, CancellationToken()) == ToolResultMessage(
        "one", "expected", "domain failure", is_error=True
    )
    assert registry.execute(
        ToolCall("two", "unexpected", {"message": "x"}), CancellationToken()
    ) == ToolResultMessage(
        "two",
        "unexpected",
        "tool execution failed: implementation failure",
        is_error=True,
    )


def test_unknown_tool_keeps_call_identity() -> None:
    result = ToolRegistry([]).execute(ToolCall("missing-1", "missing", {}), CancellationToken())

    assert result == ToolResultMessage(
        "missing-1", "missing", "tool not found: missing", is_error=True
    )


def test_cancellation_is_not_downgraded_to_tool_error() -> None:
    def cancel(_arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        token.cancel("stop the run")
        token.checkpoint()
        return ToolOutcome("unreachable")

    registry = ToolRegistry([Tool(definition(), cancel)])

    with pytest.raises(CancellationRequested, match="stop the run"):
        registry.execute(ToolCall("cancel-1", "echo", {"message": "x"}), CancellationToken())


def test_registry_checks_deadline_after_non_cooperative_handler() -> None:
    def finish_late(_arguments: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
        time.sleep(0.01)
        return ToolOutcome("late success")

    registry = ToolRegistry([Tool(definition(), finish_late)])

    with pytest.raises(DeadlineExceeded, match="exceeded its timeout"):
        registry.execute(
            ToolCall("late-1", "echo", {"message": "x"}),
            CancellationToken(0.001),
        )


def test_bash_interrupt_stops_child_before_propagating(monkeypatch, tmp_path) -> None:
    class InterruptedProcess:
        returncode = -15

        def __init__(self) -> None:
            self.terminated = False
            self.communicate_calls = 0

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise KeyboardInterrupt
            return "", ""

        def poll(self):
            return None if not self.terminated else self.returncode

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.terminated = True

    process = InterruptedProcess()
    monkeypatch.setattr(tools_module.subprocess, "Popen", lambda *_args, **_kwargs: process)
    bash = create_bash_tool(lambda _command: True, cwd=tmp_path)

    with pytest.raises(KeyboardInterrupt):
        bash.execute({"command": "sleep 5"}, CancellationToken())

    assert process.terminated is True
    assert process.communicate_calls == 2


@pytest.mark.skipif(os.name != "posix", reason="process-group semantics are POSIX-specific")
def test_bash_deadline_stops_background_child_without_waiting_for_it(tmp_path) -> None:
    child_pid_file = tmp_path / "child.pid"
    bash = create_bash_tool(lambda _command: True, cwd=tmp_path)
    started_at = time.monotonic()

    with pytest.raises(DeadlineExceeded, match="exceeded its timeout"):
        bash.execute(
            {"command": "sleep 10 & child=$!; echo $child > child.pid; wait"},
            CancellationToken(0.5),
        )

    elapsed = time.monotonic() - started_at
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    child_stopped = False
    for _ in range(20):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            child_stopped = True
            break
        time.sleep(0.01)

    assert elapsed < 1
    assert child_stopped is True
