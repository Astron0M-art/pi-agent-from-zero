import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent  # noqa: E402
from events import AgentCompleted, AgentFailed, CancellationToken, ProviderCompleted  # noqa: E402
from messages import AssistantMessage, ToolCall, ToolResultMessage  # noqa: E402
from providers import FakeModel, ModelRequest  # noqa: E402
from tools import (  # noqa: E402
    Tool,
    ToolDefinition,
    ToolOutcome,
    ToolRegistry,
    create_bash_tool,
)


def complete(message: AssistantMessage):
    return [ProviderCompleted(message)]


class ToolRuntimeTests(unittest.TestCase):
    def test_schema_is_sent_and_valid_call_is_correlated(self) -> None:
        definition = ToolDefinition(
            "echo",
            "Echo.",
            {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        )
        tool = Tool(
            definition,
            lambda args, _token: ToolOutcome(f"echo: {args['message']}"),
        )

        def finish(request: ModelRequest, _token: CancellationToken):
            result = request.messages[-1]
            self.assertEqual(result, ToolResultMessage("echo-1", "echo", "echo: hello"))
            return complete(AssistantMessage("完成"))

        fake = FakeModel(
            [
                complete(
                    AssistantMessage(tool_calls=(ToolCall("echo-1", "echo", {"message": "hello"}),))
                ),
                finish,
            ]
        )

        events = list(Agent(fake, ToolRegistry([tool])).stream("回声"))

        self.assertEqual(fake.requests[0].tools, (definition,))
        self.assertEqual(events[-1], AgentCompleted("完成"))

    def test_invalid_arguments_never_execute_tool(self) -> None:
        executed = False

        def execute(_args: Mapping[str, object], _token: CancellationToken) -> ToolOutcome:
            nonlocal executed
            executed = True
            return ToolOutcome("不应执行")

        definition = ToolDefinition(
            "echo",
            "Echo.",
            {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        )
        registry = ToolRegistry([Tool(definition, execute)])

        result = registry.execute(ToolCall("bad", "echo", {}), CancellationToken())

        self.assertFalse(executed)
        self.assertTrue(result.is_error)
        self.assertIn("is required", result.content)

    def test_approved_bash_creates_external_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ToolRegistry([create_bash_tool(lambda _command: True, root)])

            result = registry.execute(
                ToolCall("bash-1", "bash", {"command": "printf ok > result.txt"}),
                CancellationToken(),
            )

            self.assertFalse(result.is_error)
            self.assertEqual((root / "result.txt").read_text(), "ok")

    def test_tool_budget_blocks_second_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = (
                ToolCall("one", "bash", {"command": "touch first"}),
                ToolCall("two", "bash", {"command": "touch forbidden"}),
            )
            fake = FakeModel([complete(AssistantMessage(tool_calls=calls))])
            registry = ToolRegistry([create_bash_tool(lambda _command: True, root)])

            events = list(Agent(fake, registry, max_tool_calls=1).stream("执行"))

            self.assertTrue((root / "first").exists())
            self.assertFalse((root / "forbidden").exists())
            self.assertEqual(events[-1], AgentFailed("budget", "agent exceeded 1 tool calls"))


if __name__ == "__main__":
    unittest.main()
