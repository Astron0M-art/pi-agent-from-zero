"""v0.2.0 冻结快照的零依赖测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent  # noqa: E402
from messages import AssistantMessage, ToolCall, ToolResultMessage, UserMessage  # noqa: E402
from providers import FakeModel  # noqa: E402


class AgentTests(unittest.TestCase):
    def test_provider_receives_typed_request(self) -> None:
        fake = FakeModel([AssistantMessage("完成")])

        answer = Agent(fake, lambda _command: True, model="lesson").run("你好")

        self.assertEqual(answer, "完成")
        self.assertEqual(fake.requests[0].messages, (UserMessage("你好"),))
        self.assertEqual(fake.requests[0].model, "lesson")

    def test_tool_result_keeps_call_id(self) -> None:
        call = ToolCall("call-7", "bash", {"command": "printf ok"})
        fake = FakeModel([AssistantMessage(tool_calls=(call,)), AssistantMessage("完成")])

        with tempfile.TemporaryDirectory() as directory:
            Agent(fake, lambda _command: True, cwd=Path(directory)).run("运行")

        self.assertEqual(fake.requests[1].messages[-1], ToolResultMessage("call-7", "bash", "ok"))

    def test_unknown_tool_is_a_model_visible_error(self) -> None:
        call = ToolCall("call-8", "read", {"path": "README.md"})
        fake = FakeModel([AssistantMessage(tool_calls=(call,)), AssistantMessage("不可用")])

        Agent(fake, lambda _command: self.fail("approval should not run")).run("读取")

        result = fake.requests[1].messages[-1]
        self.assertIsInstance(result, ToolResultMessage)
        assert isinstance(result, ToolResultMessage)
        self.assertTrue(result.is_error)
        self.assertEqual(result.tool_call_id, "call-8")


if __name__ == "__main__":
    unittest.main()
