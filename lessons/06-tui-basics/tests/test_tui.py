import sys
import tempfile
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent  # noqa: E402
from coding_tools import create_coding_tools  # noqa: E402
from events import (  # noqa: E402
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    ProviderCompleted,
    ProviderTextDelta,
    TextDelta,
    ToolCompleted,
    ToolStarted,
)
from messages import AssistantMessage, ToolCall, ToolResultMessage  # noqa: E402
from providers import FakeModel  # noqa: E402
from tools import ToolRegistry  # noqa: E402
from tui import (  # noqa: E402
    InputBuffer,
    MessageView,
    ToolCard,
    TuiApp,
    TuiRenderer,
    TuiState,
    reduce_event,
)


class TuiBasicsTests(unittest.TestCase):
    def test_input_buffer_insert_backspace_and_submit(self) -> None:
        buffer = InputBuffer().insert("ac")
        buffer = InputBuffer(buffer.text, 1).insert("b")

        self.assertEqual(buffer, InputBuffer("abc", 2))
        self.assertEqual(buffer.backspace(), InputBuffer("ac", 1))
        self.assertEqual(buffer.submit(), ("abc", InputBuffer()))
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            InputBuffer(" ", 1).submit()
        with self.assertRaisesRegex(ValueError, "inside"):
            InputBuffer("x", 2)

    def test_stream_and_tool_events_become_one_message_and_card(self) -> None:
        state = reduce_event(TuiState(), AgentStarted("inspect"))
        state = reduce_event(state, TextDelta("hel"))
        state = reduce_event(state, TextDelta("lo"))
        state = reduce_event(state, AssistantCompleted(AssistantMessage("hello")))
        call = ToolCall("read-1", "read", {"path": "README.md"})
        state = reduce_event(state, ToolStarted(call))
        state = reduce_event(
            state,
            ToolCompleted(ToolResultMessage("read-1", "read", "content")),
        )
        state = reduce_event(state, AgentCompleted("done"))

        self.assertEqual(
            state.messages,
            (MessageView("user", "inspect"), MessageView("assistant", "hello")),
        )
        self.assertEqual(state.tool_cards[0].status, "succeeded")
        self.assertEqual(state.status, "completed")

    def test_failure_remains_visible(self) -> None:
        call = ToolCall("write-1", "write", {"path": "x", "content": "x"})
        state = reduce_event(TuiState(), ToolStarted(call))
        state = reduce_event(
            state,
            ToolCompleted(ToolResultMessage("write-1", "write", "denied", True)),
        )
        state = reduce_event(state, AgentFailed("provider", "offline"))

        self.assertEqual(state.tool_cards[0].status, "failed")
        self.assertEqual(state.status_detail, "provider: offline")

    def test_fixed_viewport_keeps_input_and_status(self) -> None:
        state = TuiState(
            input_buffer=InputBuffer("next", 4),
            timeline=tuple(MessageView("assistant", f"line {i}") for i in range(20)),
            status="running",
            status_detail="Agent is working",
        )
        frame = TuiRenderer(width=48, height=12).render(state)

        self.assertEqual(len(frame.splitlines()), 12)
        self.assertTrue(all(len(line) == 48 for line in frame.splitlines()))
        self.assertIn("earlier entries hidden", frame)
        self.assertIn("INPUT> next|", frame)
        self.assertIn("STATUS> running", frame)

    def test_fake_model_drives_complete_tui_without_paid_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("Pi Agent", encoding="utf-8")
            fake = FakeModel(
                [
                    [
                        ProviderTextDelta("searching"),
                        ProviderCompleted(
                            AssistantMessage(
                                "searching",
                                (
                                    ToolCall(
                                        "grep-1",
                                        "grep",
                                        {"query": "Pi", "path": "README.md"},
                                    ),
                                ),
                            )
                        ),
                    ],
                    [ProviderCompleted(AssistantMessage("found"))],
                ]
            )
            agent = Agent(
                fake,
                ToolRegistry(create_coding_tools(root, lambda _operation: False)),
            )
            app = TuiApp(agent, TuiRenderer(width=52, height=14))
            app.type_text("inspect")

            frames = list(app.frames())

            self.assertEqual(len(frames), 7)
            self.assertEqual(app.state.status, "completed")
            self.assertEqual(app.state.messages[-1], MessageView("assistant", "found"))
            self.assertEqual(app.state.tool_cards[0].status, "succeeded")
            self.assertIsInstance(app.state.timeline[2], ToolCard)
            self.assertEqual(app.state.timeline[3], MessageView("assistant", "found"))


if __name__ == "__main__":
    unittest.main()
