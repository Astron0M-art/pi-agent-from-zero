from collections.abc import Iterator
from pathlib import Path

import pytest

from pi_agent_from_zero import (
    Agent,
    AgentCompleted,
    AgentFailed,
    AgentRunError,
    AgentStarted,
    AssistantCompleted,
    AssistantMessage,
    CancellationToken,
    FakeModel,
    ModelRequest,
    ProviderCompleted,
    ProviderFailed,
    ProviderTextDelta,
    TextDeltaEvent,
    ToolCall,
    ToolCompleted,
    ToolRegistry,
    ToolResultMessage,
    ToolStarted,
    UserMessage,
    create_bash_tool,
)


def bash_call(command: object, *, call_id: str = "call-1") -> ToolCall:
    return ToolCall(call_id, "bash", {"command": command})


def completed(message: AssistantMessage) -> list[ProviderCompleted]:
    return [ProviderCompleted(message)]


def bash_registry(approve=lambda _command: True, *, cwd: Path | None = None) -> ToolRegistry:
    return ToolRegistry([create_bash_tool(approve, cwd=cwd)])


def test_direct_answer_streams_events_and_tool_definitions() -> None:
    message = AssistantMessage("直接回答")
    fake = FakeModel(
        [[ProviderTextDelta("直接"), ProviderTextDelta("回答"), ProviderCompleted(message)]]
    )

    events = list(
        Agent(
            fake,
            bash_registry(),
            model="lesson-model",
            system_prompt="教学",
        ).stream("你好")
    )

    assert events == [
        AgentStarted("你好"),
        TextDeltaEvent("直接"),
        TextDeltaEvent("回答"),
        AssistantCompleted(message),
        AgentCompleted("直接回答"),
    ]
    request = fake.requests[0]
    assert request.model == "lesson-model"
    assert request.system_prompt == "教学"
    assert request.messages == (UserMessage("你好"),)
    assert [tool.name for tool in request.tools] == ["bash"]
    assert request.tools[0].parameters["required"] == ("command",)


def test_approved_bash_emits_tool_events_and_keeps_identity(tmp_path: Path) -> None:
    call = bash_call("printf lesson > result.txt && cat result.txt")

    def finish(request: ModelRequest, _cancellation: CancellationToken) -> list[ProviderCompleted]:
        result = request.messages[-1]
        assert isinstance(result, ToolResultMessage)
        return completed(AssistantMessage(f"看到 {result.content}"))

    fake = FakeModel([completed(AssistantMessage(tool_calls=(call,))), finish])

    events = list(Agent(fake, bash_registry(cwd=tmp_path)).stream("写入文件"))

    assert (tmp_path / "result.txt").read_text() == "lesson"
    assert ToolStarted(call) in events
    assert ToolCompleted(ToolResultMessage("call-1", "bash", "lesson")) in events
    assert events[-1] == AgentCompleted("看到 lesson")
    assert fake.requests[1].messages[-1] == ToolResultMessage("call-1", "bash", "lesson")


def test_denied_and_unknown_tools_become_model_visible_errors(tmp_path: Path) -> None:
    denied = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(bash_call("touch forbidden"),))),
            completed(AssistantMessage("已停止")),
        ]
    )
    Agent(denied, bash_registry(lambda _command: False, cwd=tmp_path)).run("写入")
    denied_result = denied.requests[1].messages[-1]
    assert isinstance(denied_result, ToolResultMessage)
    assert denied_result.is_error is True
    assert denied_result.content == "user denied the bash command"
    assert not (tmp_path / "forbidden").exists()

    call = ToolCall("call-read", "read", {"path": "README.md"})
    unknown = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(call,))),
            completed(AssistantMessage("工具不可用")),
        ]
    )
    Agent(unknown, ToolRegistry([])).run("读取")
    assert unknown.requests[1].messages[-1] == ToolResultMessage(
        "call-read", "read", "tool not found: read", is_error=True
    )


def test_invalid_arguments_do_not_reach_approval_or_shell(tmp_path: Path) -> None:
    fake = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(bash_call(42),))),
            completed(AssistantMessage("参数错误")),
        ]
    )

    Agent(
        fake,
        bash_registry(lambda _command: pytest.fail("approval must not run"), cwd=tmp_path),
    ).run("执行")

    result = fake.requests[1].messages[-1]
    assert isinstance(result, ToolResultMessage)
    assert result.is_error is True
    assert result.content == "invalid arguments: arguments.command: expected string"


def test_external_cancellation_discards_partial_assistant_message() -> None:
    root = CancellationToken()

    def cancelling_stream(
        _request: ModelRequest, _token: CancellationToken
    ) -> Iterator[ProviderTextDelta | ProviderCompleted]:
        yield ProviderTextDelta("只完成一半")
        root.cancel("测试请求停止")
        yield ProviderCompleted(AssistantMessage("只完成一半"))

    agent = Agent(FakeModel([cancelling_stream]), ToolRegistry([]))

    events = list(agent.stream("开始", cancellation=root))

    assert events[-1] == AgentFailed("cancelled", "测试请求停止")
    assert TextDeltaEvent("只完成一半") in events
    assert agent.messages == [UserMessage("开始")]


def test_zero_timeout_stops_before_mutating_history_or_calling_provider() -> None:
    fake = FakeModel([completed(AssistantMessage("来不及"))])
    agent = Agent(fake, ToolRegistry([]))

    events = list(agent.stream("开始", timeout_seconds=0))

    assert events[0] == AgentStarted("开始")
    assert isinstance(events[-1], AgentFailed)
    assert events[-1].kind == "timeout"
    assert agent.messages == []
    assert fake.requests == []


@pytest.mark.parametrize(
    ("stream", "kind"),
    [
        ([ProviderFailed("上游坏了")], "provider"),
        ([ProviderTextDelta("甲"), ProviderCompleted(AssistantMessage("乙"))], "protocol"),
        ([ProviderTextDelta("没有终点")], "protocol"),
    ],
)
def test_provider_failures_have_explicit_terminal_event(stream: list, kind: str) -> None:
    agent = Agent(FakeModel([stream]), ToolRegistry([]))

    events = list(agent.stream("开始"))

    assert isinstance(events[-1], AgentFailed)
    assert events[-1].kind == kind
    assert agent.messages == [UserMessage("开始")]


def test_command_timeout_is_a_tool_result_and_agent_can_continue(tmp_path: Path) -> None:
    fake = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(bash_call("sleep 1"),))),
            completed(AssistantMessage("已处理超时")),
        ]
    )

    registry = ToolRegistry(
        [create_bash_tool(lambda _command: True, cwd=tmp_path, timeout_seconds=0.01)]
    )
    answer = Agent(fake, registry).run("运行")

    result = fake.requests[1].messages[-1]
    assert isinstance(result, ToolResultMessage)
    assert result.is_error is True
    assert "timed out" in result.content
    assert answer == "已处理超时"


def test_model_turn_budget_exposes_failure_kind(tmp_path: Path) -> None:
    fake = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(bash_call("true", call_id="one"),))),
            completed(AssistantMessage(tool_calls=(bash_call("true", call_id="two"),))),
        ]
    )

    with pytest.raises(AgentRunError) as raised:
        Agent(fake, bash_registry(cwd=tmp_path), max_turns=2).run("不要停")

    assert raised.value.kind == "budget"
    assert "exceeded 2 turns" in str(raised.value)


def test_tool_call_budget_stops_before_extra_side_effect(tmp_path: Path) -> None:
    calls = (
        bash_call("touch first", call_id="one"),
        bash_call("touch forbidden", call_id="two"),
    )
    fake = FakeModel([completed(AssistantMessage(tool_calls=calls))])
    agent = Agent(fake, bash_registry(cwd=tmp_path), max_tool_calls=1)

    events = list(agent.stream("只允许一次工具"))

    assert (tmp_path / "first").exists()
    assert not (tmp_path / "forbidden").exists()
    assert events[-1] == AgentFailed("budget", "agent exceeded 1 tool calls")
    assert ToolStarted(calls[1]) not in events
