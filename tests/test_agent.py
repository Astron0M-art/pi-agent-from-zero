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
    ToolResultMessage,
    ToolStarted,
    UserMessage,
)


def bash_call(command: object, *, call_id: str = "call-1") -> ToolCall:
    return ToolCall(call_id, "bash", {"command": command})


def completed(message: AssistantMessage) -> list[ProviderCompleted]:
    return [ProviderCompleted(message)]


def test_direct_answer_streams_typed_events_and_request() -> None:
    message = AssistantMessage("直接回答")
    fake = FakeModel(
        [[ProviderTextDelta("直接"), ProviderTextDelta("回答"), ProviderCompleted(message)]]
    )

    events = list(
        Agent(fake, lambda _command: True, model="lesson-model", system_prompt="教学").stream(
            "你好"
        )
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
    assert request.available_tools == ("bash",)
    assert request.messages == (UserMessage("你好"),)


def test_approved_bash_emits_tool_events_and_keeps_identity(tmp_path: Path) -> None:
    call = bash_call("printf lesson > result.txt && cat result.txt")

    def finish(request: ModelRequest, _cancellation: CancellationToken) -> list[ProviderCompleted]:
        result = request.messages[-1]
        assert isinstance(result, ToolResultMessage)
        return completed(AssistantMessage(f"看到 {result.content}"))

    fake = FakeModel([completed(AssistantMessage(tool_calls=(call,))), finish])

    events = list(Agent(fake, lambda _command: True, cwd=tmp_path).stream("写入文件"))

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
    Agent(denied, lambda _command: False, cwd=tmp_path).run("写入")
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
    Agent(unknown, lambda _command: pytest.fail("approval must not run")).run("读取")
    assert unknown.requests[1].messages[-1] == ToolResultMessage(
        "call-read", "read", "unknown tool: read", is_error=True
    )


def test_external_cancellation_discards_partial_assistant_message() -> None:
    root = CancellationToken()

    def cancelling_stream(
        _request: ModelRequest, _token: CancellationToken
    ) -> Iterator[ProviderTextDelta | ProviderCompleted]:
        yield ProviderTextDelta("只完成一半")
        root.cancel("测试请求停止")
        yield ProviderCompleted(AssistantMessage("只完成一半"))

    agent = Agent(FakeModel([cancelling_stream]), lambda _command: True)

    events = list(agent.stream("开始", cancellation=root))

    assert events[-1] == AgentFailed("cancelled", "测试请求停止")
    assert TextDeltaEvent("只完成一半") in events
    assert agent.messages == [UserMessage("开始")]


def test_zero_timeout_stops_before_mutating_history_or_calling_provider() -> None:
    fake = FakeModel([completed(AssistantMessage("来不及"))])
    agent = Agent(fake, lambda _command: True)

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
    agent = Agent(FakeModel([stream]), lambda _command: True)

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

    answer = Agent(
        fake,
        lambda _command: True,
        cwd=tmp_path,
        command_timeout_seconds=0.01,
    ).run("运行")

    result = fake.requests[1].messages[-1]
    assert isinstance(result, ToolResultMessage)
    assert result.is_error is True
    assert "timed out" in result.content
    assert answer == "已处理超时"


def test_turn_budget_and_run_wrapper_expose_failure_kind(tmp_path: Path) -> None:
    fake = FakeModel(
        [
            completed(AssistantMessage(tool_calls=(bash_call("true", call_id="one"),))),
            completed(AssistantMessage(tool_calls=(bash_call("true", call_id="two"),))),
        ]
    )

    with pytest.raises(AgentRunError) as raised:
        Agent(fake, lambda _command: True, cwd=tmp_path, max_turns=2).run("不要停")

    assert raised.value.kind == "budget"
    assert "exceeded 2 turns" in str(raised.value)
