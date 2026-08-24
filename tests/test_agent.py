from pathlib import Path

import pytest

from pi_agent_from_zero import (
    Agent,
    AssistantMessage,
    FakeModel,
    ModelRequest,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def bash_call(command: object, *, call_id: str = "call-1") -> ToolCall:
    return ToolCall(call_id, "bash", {"command": command})


def test_direct_answer_uses_structured_request() -> None:
    fake = FakeModel([AssistantMessage("直接回答")])

    answer = Agent(fake, lambda _command: True, model="lesson-model", system_prompt="教学").run(
        "你好"
    )

    assert answer == "直接回答"
    request = fake.requests[0]
    assert request.model == "lesson-model"
    assert request.system_prompt == "教学"
    assert request.available_tools == ("bash",)
    assert request.messages == (UserMessage("你好"),)


def test_approved_bash_result_keeps_call_identity(tmp_path: Path) -> None:
    def finish(request: ModelRequest) -> AssistantMessage:
        result = request.messages[-1]
        assert isinstance(result, ToolResultMessage)
        return AssistantMessage(f"看到 {result.content}")

    fake = FakeModel(
        [
            AssistantMessage(
                tool_calls=(bash_call("printf lesson > result.txt && cat result.txt"),)
            ),
            finish,
        ]
    )

    answer = Agent(fake, lambda _command: True, cwd=tmp_path).run("写入文件")

    assert answer == "看到 lesson"
    assert (tmp_path / "result.txt").read_text() == "lesson"
    result = fake.requests[1].messages[-1]
    assert result == ToolResultMessage("call-1", "bash", "lesson")


def test_denied_command_is_an_error_message_without_side_effect(tmp_path: Path) -> None:
    fake = FakeModel(
        [AssistantMessage(tool_calls=(bash_call("touch forbidden"),)), AssistantMessage("已停止")]
    )

    Agent(fake, lambda _command: False, cwd=tmp_path).run("写入")

    assert not (tmp_path / "forbidden").exists()
    result = fake.requests[1].messages[-1]
    assert isinstance(result, ToolResultMessage)
    assert result.is_error is True
    assert result.content == "user denied the bash command"


def test_unknown_tool_returns_correlated_error() -> None:
    call = ToolCall("call-read", "read", {"path": "README.md"})
    fake = FakeModel([AssistantMessage(tool_calls=(call,)), AssistantMessage("工具不可用")])

    Agent(fake, lambda _command: pytest.fail("approval must not run")).run("读取")

    result = fake.requests[1].messages[-1]
    assert result == ToolResultMessage("call-read", "read", "unknown tool: read", is_error=True)


def test_malformed_bash_arguments_are_visible_to_model() -> None:
    fake = FakeModel([AssistantMessage(tool_calls=(bash_call(42),)), AssistantMessage("参数错误")])

    Agent(fake, lambda _command: pytest.fail("approval must not run")).run("运行")

    result = fake.requests[1].messages[-1]
    assert isinstance(result, ToolResultMessage)
    assert result.is_error is True
    assert "non-empty string" in result.content


def test_turn_budget_stops_infinite_tool_loop(tmp_path: Path) -> None:
    fake = FakeModel(
        [
            AssistantMessage(tool_calls=(bash_call("true", call_id="one"),)),
            AssistantMessage(tool_calls=(bash_call("true", call_id="two"),)),
        ]
    )

    with pytest.raises(RuntimeError, match="exceeded 2 turns"):
        Agent(fake, lambda _command: True, cwd=tmp_path, max_turns=2).run("不要停")
