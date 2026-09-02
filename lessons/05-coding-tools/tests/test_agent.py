import sys
import tempfile
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).parents[1] / "snapshot"
sys.path.insert(0, str(SNAPSHOT))

from agent import Agent  # noqa: E402
from coding_tools import ProjectWorkspace, create_coding_tools  # noqa: E402
from events import CancellationToken, ProviderCompleted  # noqa: E402
from messages import AssistantMessage, ToolCall, ToolResultMessage  # noqa: E402
from providers import FakeModel, ModelRequest  # noqa: E402
from tools import OutputLimits, ToolRegistry  # noqa: E402


def complete(message: AssistantMessage):
    return [ProviderCompleted(message)]


class CodingToolsTests(unittest.TestCase):
    def test_agent_reads_then_finishes_with_correlated_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("课程", encoding="utf-8")
            registry = ToolRegistry(create_coding_tools(root, lambda _operation: True))

            def finish(request: ModelRequest, _token: CancellationToken):
                self.assertEqual(
                    request.messages[-1],
                    ToolResultMessage("read-1", "read", "课程"),
                )
                return complete(AssistantMessage("完成"))

            fake = FakeModel(
                [
                    complete(
                        AssistantMessage(
                            tool_calls=(ToolCall("read-1", "read", {"path": "README.md"}),)
                        )
                    ),
                    finish,
                ]
            )

            events = list(Agent(fake, registry).stream("读文件"))

            self.assertEqual(events[-1].answer, "完成")
            self.assertEqual(
                [definition.name for definition in fake.requests[0].tools],
                ["read", "write", "edit", "bash", "grep"],
            )

    def test_write_edit_grep_and_project_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ToolRegistry(create_coding_tools(root, lambda _operation: True))
            token = CancellationToken()

            written = registry.execute(
                ToolCall("write-1", "write", {"path": "app.py", "content": "old\n"}),
                token,
            )
            edited = registry.execute(
                ToolCall(
                    "edit-1",
                    "edit",
                    {"path": "app.py", "old_text": "old", "new_text": "new"},
                ),
                token,
            )
            found = registry.execute(ToolCall("grep-1", "grep", {"query": "new"}), token)
            escaped = registry.execute(ToolCall("read-2", "read", {"path": "../secret"}), token)

            self.assertFalse(written.is_error)
            self.assertFalse(edited.is_error)
            self.assertEqual(found.content, "app.py:1:new")
            self.assertTrue(escaped.is_error)
            self.assertEqual(escaped.content, "path escapes the project root")

    def test_denial_and_ambiguous_edit_leave_file_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "repeat.txt"
            target.write_text("x x", encoding="utf-8")
            registry = ToolRegistry(create_coding_tools(root, lambda _operation: False))

            denied = registry.execute(
                ToolCall("write-1", "write", {"path": "new.txt", "content": "no"}),
                CancellationToken(),
            )
            ambiguous = registry.execute(
                ToolCall(
                    "edit-1",
                    "edit",
                    {"path": "repeat.txt", "old_text": "x", "new_text": "y"},
                ),
                CancellationToken(),
            )

            self.assertTrue(denied.is_error)
            self.assertFalse((root / "new.txt").exists())
            self.assertTrue(ambiguous.is_error)
            self.assertEqual(target.read_text(encoding="utf-8"), "x x")

    def test_all_results_are_truncated_before_returning_to_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "long.txt").write_text("\n".join(["long line"] * 30))
            registry = ToolRegistry(
                create_coding_tools(root, lambda _operation: True),
                output_limits=OutputLimits(max_chars=90, max_lines=4),
            )

            result = registry.execute(
                ToolCall("read-1", "read", {"path": "long.txt"}),
                CancellationToken(),
            )

            self.assertLessEqual(len(result.content), 90)
            self.assertLessEqual(len(result.content.splitlines()), 4)
            self.assertIn("[truncated:", result.content)

    def test_workspace_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ProjectWorkspace(Path(directory))
            with self.assertRaisesRegex(RuntimeError, "relative"):
                workspace.resolve("/tmp/outside")


if __name__ == "__main__":
    unittest.main()
