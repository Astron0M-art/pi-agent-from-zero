import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent  # noqa: E402
from events import (  # noqa: E402
    AgentCompleted,
    AgentFailed,
    CancellationToken,
    ProviderCompleted,
    ProviderTextDelta,
    TextDelta,
)
from messages import AssistantMessage, ToolCall, UserMessage  # noqa: E402
from providers import FakeModel, ModelRequest  # noqa: E402


class StreamingAgentTests(unittest.TestCase):
    def test_streams_text_then_completes(self) -> None:
        fake = FakeModel(
            [
                [
                    ProviderTextDelta("你"),
                    ProviderTextDelta("好"),
                    ProviderCompleted(AssistantMessage("你好")),
                ]
            ]
        )

        events = list(Agent(fake, lambda _command: True).stream("开始"))

        self.assertIn(TextDelta("你"), events)
        self.assertEqual(events[-1], AgentCompleted("你好"))
        self.assertEqual(fake.requests[0].messages, (UserMessage("开始"),))

    def test_cancelled_partial_message_is_not_committed(self) -> None:
        token = CancellationToken()

        def cancel_mid_stream(_request: ModelRequest, _token: CancellationToken):
            yield ProviderTextDelta("半句")
            token.cancel("学生触发取消")
            yield ProviderCompleted(AssistantMessage("半句"))

        agent = Agent(FakeModel([cancel_mid_stream]), lambda _command: True)

        events = list(agent.stream("开始", cancellation=token))

        self.assertEqual(events[-1], AgentFailed("cancelled", "学生触发取消"))
        self.assertEqual(agent.messages, [UserMessage("开始")])

    def test_mismatched_final_message_fails(self) -> None:
        fake = FakeModel(
            [[ProviderTextDelta("流里的字"), ProviderCompleted(AssistantMessage("另一句话"))]]
        )
        agent = Agent(fake, lambda _command: True)

        events = list(agent.stream("开始"))

        self.assertEqual(events[-1].kind, "protocol")
        self.assertEqual(agent.messages, [UserMessage("开始")])

    def test_bash_timeout_is_a_tool_result_instead_of_a_traceback(self) -> None:
        agent = Agent(FakeModel([]), lambda _command: True)
        call = ToolCall("bash-1", "bash", {"command": "sleep 6"})

        with patch("agent.subprocess.run", side_effect=subprocess.TimeoutExpired("bash", 5)):
            result = agent._execute(call)

        self.assertTrue(result.is_error)
        self.assertEqual(result.content, "command timed out after 5s")


if __name__ == "__main__":
    unittest.main()
