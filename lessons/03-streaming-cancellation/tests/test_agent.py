import sys
import unittest
from pathlib import Path

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
from messages import AssistantMessage, UserMessage  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
