"""v0.5.0 项目根目录内的 read、write、edit、bash 与 grep 工具。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from pi_agent_from_zero.events import CancellationToken
from pi_agent_from_zero.tools import (
    Approval,
    Tool,
    ToolDefinition,
    ToolExecutionError,
    ToolOutcome,
    create_bash_tool,
)


class ProjectWorkspace:
    """把所有文件工具限制在一个解析后的项目根目录内。"""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("project root must be a directory")

    def resolve(self, raw_path: str) -> Path:
        requested = Path(raw_path)
        if requested.is_absolute():
            raise ToolExecutionError("path must be relative to the project root")
        candidate = (self.root / requested).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise ToolExecutionError("path escapes the project root") from error
        return candidate

    def display(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() or "."


def _definition(
    name: str,
    description: str,
    properties: Mapping[str, object],
    required: list[str],
) -> ToolDefinition:
    return ToolDefinition(
        name,
        description,
        {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    )


def create_read_tool(workspace: ProjectWorkspace) -> Tool:
    definition = _definition(
        "read",
        "Read one UTF-8 text file inside the project root.",
        {"path": {"type": "string", "minLength": 1}},
        ["path"],
    )

    def execute(arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        token.checkpoint()
        path = workspace.resolve(cast(str, arguments["path"]))
        if not path.exists():
            raise ToolExecutionError(f"file not found: {workspace.display(path)}")
        if not path.is_file():
            raise ToolExecutionError(f"path is not a file: {workspace.display(path)}")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ToolExecutionError("read only supports UTF-8 text files") from error
        except OSError as error:
            raise ToolExecutionError(f"could not read file: {error}") from error
        token.checkpoint()
        return ToolOutcome(content)

    return Tool(definition, execute)


def create_write_tool(workspace: ProjectWorkspace, approve: Approval) -> Tool:
    definition = _definition(
        "write",
        "Write one UTF-8 file inside the project root after approval.",
        {
            "path": {"type": "string", "minLength": 1},
            "content": {"type": "string"},
        },
        ["path", "content"],
    )

    def execute(arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        path = workspace.resolve(cast(str, arguments["path"]))
        relative = workspace.display(path)
        token.checkpoint()
        if not approve(f"write {relative}"):
            return ToolOutcome(f"user denied writing {relative}", is_error=True)
        token.checkpoint()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            content = cast(str, arguments["content"])
            path.write_text(content, encoding="utf-8")
        except OSError as error:
            raise ToolExecutionError(f"could not write file: {error}") from error
        token.checkpoint()
        return ToolOutcome(f"wrote {len(content)} characters to {relative}")

    return Tool(definition, execute)


def create_edit_tool(workspace: ProjectWorkspace, approve: Approval) -> Tool:
    definition = _definition(
        "edit",
        "Replace one unique exact text block in a UTF-8 project file after approval.",
        {
            "path": {"type": "string", "minLength": 1},
            "old_text": {"type": "string", "minLength": 1},
            "new_text": {"type": "string"},
        },
        ["path", "old_text", "new_text"],
    )

    def execute(arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        path = workspace.resolve(cast(str, arguments["path"]))
        relative = workspace.display(path)
        if not path.is_file():
            raise ToolExecutionError(f"file not found: {relative}")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ToolExecutionError("edit only supports UTF-8 text files") from error
        except OSError as error:
            raise ToolExecutionError(f"could not read file: {error}") from error

        old_text = cast(str, arguments["old_text"])
        occurrences = content.count(old_text)
        if occurrences != 1:
            raise ToolExecutionError(
                f"old_text must match exactly once; found {occurrences} matches"
            )
        token.checkpoint()
        if not approve(f"edit {relative}"):
            return ToolOutcome(f"user denied editing {relative}", is_error=True)
        token.checkpoint()
        new_text = cast(str, arguments["new_text"])
        try:
            path.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        except OSError as error:
            raise ToolExecutionError(f"could not edit file: {error}") from error
        token.checkpoint()
        return ToolOutcome(f"replaced one block in {relative}")

    return Tool(definition, execute)


def create_grep_tool(workspace: ProjectWorkspace, *, max_matches: int = 100) -> Tool:
    if max_matches < 1:
        raise ValueError("max_matches must be positive")
    definition = _definition(
        "grep",
        "Find literal text in UTF-8 project files and return path:line matches.",
        {
            "query": {"type": "string", "minLength": 1},
            "path": {"type": "string", "minLength": 1},
        },
        ["query"],
    )

    def execute(arguments: Mapping[str, object], token: CancellationToken) -> ToolOutcome:
        query = cast(str, arguments["query"])
        start = workspace.resolve(cast(str, arguments.get("path", ".")))
        if not start.exists():
            raise ToolExecutionError(f"search path not found: {workspace.display(start)}")
        paths = [start] if start.is_file() else _walk_files(start)
        matches: list[str] = []
        reached_limit = False
        for raw_path in paths:
            token.checkpoint()
            try:
                path = workspace.resolve(workspace.display(raw_path))
            except ToolExecutionError:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(lines, start=1):
                if query not in line:
                    continue
                matches.append(f"{workspace.display(path)}:{line_number}:{line}")
                if len(matches) >= max_matches:
                    reached_limit = True
                    break
            if reached_limit:
                break
        if not matches:
            return ToolOutcome("(no matches)")
        if reached_limit:
            matches.append(f"[match limit reached: {max_matches}]")
        return ToolOutcome("\n".join(matches))

    return Tool(definition, execute)


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if not name.startswith("."))
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            files.append(Path(directory, filename))
    return files


def create_coding_tools(root: Path, approve: Approval) -> tuple[Tool, ...]:
    """按稳定顺序构造本版五个 Coding Tools。"""

    workspace = ProjectWorkspace(root)
    return (
        create_read_tool(workspace),
        create_write_tool(workspace, approve),
        create_edit_tool(workspace, approve),
        create_bash_tool(approve, cwd=workspace.root),
        create_grep_tool(workspace),
    )
