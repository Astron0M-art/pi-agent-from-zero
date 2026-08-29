from collections.abc import Mapping

import pytest

from pi_agent_from_zero import (
    CancellationRequested,
    CancellationToken,
    SchemaDefinitionError,
    SchemaValidationError,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolExecutionError,
    ToolOutcome,
    ToolRegistry,
    ToolResultMessage,
    validate_arguments,
)


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
