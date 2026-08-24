from pathlib import Path

import pytest

from pi_agent_from_zero import Agent, ModelOutput, __version__


class FakeModel:
    """按脚本返回结果，测试默认不连接真实模型。"""

    def __init__(self, *outputs: ModelOutput) -> None:
        self.outputs = list(outputs)
        self.histories: list[tuple[dict[str, str], ...]] = []

    def __call__(self, history: tuple[dict[str, str], ...]) -> ModelOutput:
        self.histories.append(history)
        return self.outputs.pop(0)


def test_bootstrap_version() -> None:
    assert __version__ == "0.1.0"


def test_returns_direct_answer_without_side_effect() -> None:
    model = FakeModel(ModelOutput("直接回答"))
    approved: list[str] = []

    answer = Agent(model, lambda command: approved.append(command) or True).run("你好")

    assert answer == "直接回答"
    assert approved == []


def test_executes_approved_bash_and_returns_result(tmp_path: Path) -> None:
    model = FakeModel(
        ModelOutput("读取文件", "printf lesson > result.txt && cat result.txt"),
        ModelOutput("已经写入 lesson"),
    )

    answer = Agent(model, lambda _command: True, cwd=tmp_path).run("写入文件")

    assert answer == "已经写入 lesson"
    assert (tmp_path / "result.txt").read_text() == "lesson"
    assert model.histories[1][-1] == {"role": "tool", "name": "bash", "content": "lesson"}


def test_denial_is_observable_and_command_is_not_executed(tmp_path: Path) -> None:
    model = FakeModel(
        ModelOutput("尝试写入", "touch forbidden.txt"),
        ModelOutput("用户拒绝后停止"),
    )

    answer = Agent(model, lambda _command: False, cwd=tmp_path).run("写入文件")

    assert answer == "用户拒绝后停止"
    assert not (tmp_path / "forbidden.txt").exists()
    assert model.histories[1][-1]["content"].startswith("DENIED:")


def test_nonzero_exit_is_returned_to_model(tmp_path: Path) -> None:
    model = FakeModel(ModelOutput("运行失败命令", "exit 7"), ModelOutput("看到退出码 7"))

    Agent(model, lambda _command: True, cwd=tmp_path).run("测试失败")

    assert "command exited with 7" in model.histories[1][-1]["content"]


def test_turn_budget_stops_infinite_tool_loop(tmp_path: Path) -> None:
    model = FakeModel(ModelOutput(bash_command="true"), ModelOutput(bash_command="true"))

    with pytest.raises(RuntimeError, match="exceeded 2 turns"):
        Agent(model, lambda _command: True, cwd=tmp_path, max_turns=2).run("不要停")
