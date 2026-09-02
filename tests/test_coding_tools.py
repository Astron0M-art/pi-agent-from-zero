from pathlib import Path

import pytest

from pi_agent_from_zero import (
    CancellationToken,
    OutputLimits,
    ProjectWorkspace,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolOutcome,
    ToolRegistry,
    create_coding_tools,
    create_edit_tool,
    create_grep_tool,
    create_read_tool,
    create_write_tool,
    truncate_output,
)


def call(registry: ToolRegistry, name: str, arguments: dict[str, object]):
    return registry.execute(ToolCall("call-1", name, arguments), CancellationToken())


def test_coding_toolset_has_stable_model_visible_order(tmp_path: Path) -> None:
    registry = ToolRegistry(create_coding_tools(tmp_path, lambda _operation: True))

    assert [definition.name for definition in registry.definitions] == [
        "read",
        "write",
        "edit",
        "bash",
        "grep",
    ]


def test_read_returns_utf8_text_and_rejects_project_escape(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("你好，Agent", encoding="utf-8")
    registry = ToolRegistry([create_read_tool(ProjectWorkspace(tmp_path))])

    assert call(registry, "read", {"path": "hello.txt"}).content == "你好，Agent"
    escaped = call(registry, "read", {"path": "../outside.txt"})

    assert escaped.is_error is True
    assert escaped.content == "path escapes the project root"


def test_read_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-for-pi-agent-test.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "outside.txt"
    try:
        link.symlink_to(outside)
        registry = ToolRegistry([create_read_tool(ProjectWorkspace(tmp_path))])
        result = call(registry, "read", {"path": "outside.txt"})
        assert result.is_error is True
        assert result.content == "path escapes the project root"
    finally:
        outside.unlink(missing_ok=True)


def test_write_requires_approval_before_creating_file(tmp_path: Path) -> None:
    approvals: list[str] = []
    workspace = ProjectWorkspace(tmp_path)

    denied_registry = ToolRegistry(
        [create_write_tool(workspace, lambda operation: approvals.append(operation) or False)]
    )
    denied = call(
        denied_registry,
        "write",
        {"path": "notes/result.txt", "content": "first"},
    )
    assert denied.is_error is True
    assert not (tmp_path / "notes/result.txt").exists()
    assert approvals == ["write notes/result.txt"]

    allowed_registry = ToolRegistry([create_write_tool(workspace, lambda _operation: True)])
    allowed = call(
        allowed_registry,
        "write",
        {"path": "notes/result.txt", "content": "done"},
    )
    assert allowed.is_error is False
    assert (tmp_path / "notes/result.txt").read_text(encoding="utf-8") == "done"


def test_edit_requires_one_exact_match_and_never_mutates_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("old\nold\n", encoding="utf-8")
    registry = ToolRegistry([create_edit_tool(ProjectWorkspace(tmp_path), lambda _operation: True)])

    ambiguous = call(
        registry,
        "edit",
        {"path": "app.py", "old_text": "old", "new_text": "new"},
    )
    assert ambiguous.is_error is True
    assert "found 2 matches" in ambiguous.content
    assert target.read_text(encoding="utf-8") == "old\nold\n"

    changed = call(
        registry,
        "edit",
        {"path": "app.py", "old_text": "old\nold", "new_text": "new"},
    )
    assert changed.is_error is False
    assert target.read_text(encoding="utf-8") == "new\n"


def test_grep_returns_literal_path_line_matches_and_limit(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle one\nneedle two\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\xffneedle")
    registry = ToolRegistry([create_grep_tool(ProjectWorkspace(tmp_path), max_matches=1)])

    result = call(registry, "grep", {"query": "needle"})

    assert result.is_error is False
    assert result.content == "a.txt:1:needle one\n[match limit reached: 1]"


def test_grep_skips_file_symlinks_that_escape_project(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-grep-outside.txt"
    outside.write_text("private needle", encoding="utf-8")
    try:
        (tmp_path / "linked.txt").symlink_to(outside)
        registry = ToolRegistry([create_grep_tool(ProjectWorkspace(tmp_path))])

        result = call(registry, "grep", {"query": "needle"})

        assert result.content == "(no matches)"
    finally:
        outside.unlink(missing_ok=True)


def test_truncation_obeys_both_result_limits() -> None:
    content = "\n".join(f"line-{number}" for number in range(20))
    limits = OutputLimits(max_chars=80, max_lines=4)

    truncated = truncate_output(content, limits)

    assert len(truncated) <= 80
    assert len(truncated.splitlines()) <= 4
    assert "[truncated:" in truncated


def test_registry_bounds_every_successful_tool_result() -> None:
    definition = ToolDefinition(
        "large",
        "Return a large result.",
        {"type": "object", "properties": {}, "additionalProperties": False},
    )
    registry = ToolRegistry(
        [Tool(definition, lambda _arguments, _token: ToolOutcome("x" * 200))],
        output_limits=OutputLimits(max_chars=50, max_lines=2),
    )

    result = call(registry, "large", {})

    assert len(result.content) <= 50
    assert "[truncated:" in result.content


@pytest.mark.parametrize(("max_chars", "max_lines"), [(0, 1), (1, 0)])
def test_output_limits_must_be_positive(max_chars: int, max_lines: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        OutputLimits(max_chars=max_chars, max_lines=max_lines)
