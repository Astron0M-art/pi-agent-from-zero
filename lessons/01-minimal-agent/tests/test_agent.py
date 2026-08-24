"""冻结快照的零依赖回归测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent, ModelOutput  # noqa: E402


class FakeModel:
    def __init__(self, *outputs: ModelOutput) -> None:
        self.outputs = list(outputs)
        self.history: tuple[dict[str, str], ...] = ()

    def __call__(self, history: tuple[dict[str, str], ...]) -> ModelOutput:
        self.history = history
        return self.outputs.pop(0)


class AgentTests(unittest.TestCase):
    def test_approved_command_runs(self) -> None:
        model = FakeModel(ModelOutput(bash_command="printf ok"), ModelOutput("完成"))

        with tempfile.TemporaryDirectory() as directory:
            answer = Agent(model, lambda _command: True, cwd=Path(directory)).run("测试")

        self.assertEqual(answer, "完成")
        self.assertEqual(model.history[-1]["content"], "ok")

    def test_denied_command_does_not_run(self) -> None:
        model = FakeModel(ModelOutput(bash_command="touch denied"), ModelOutput("已停止"))

        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            Agent(model, lambda _command: False, cwd=cwd).run("测试")
            self.assertFalse((cwd / "denied").exists())

        self.assertIn("DENIED", model.history[-1]["content"])


if __name__ == "__main__":
    unittest.main()
