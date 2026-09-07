"""v0.5.0 项目根目录内的 read、write、edit、bash 与 grep 工具。"""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import cast

from events import CancellationToken
from tools import (
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

    def atomic_write(
        self,
        raw_path: str,
        content: str,
        *,
        expected_content: str | None = None,
    ) -> None:
        """Write through a stable directory descriptor and reject stale edits."""

        parts = self._safe_parts(raw_path)
        try:
            parent_fd = self._open_parent(parts[:-1], create=expected_content is None)
        except ToolExecutionError:
            raise
        except OSError as error:
            raise ToolExecutionError(f"could not write file: {error}") from error
        filename = parts[-1]
        temporary = f".pi-agent-{secrets.token_hex(8)}.tmp"
        try:
            target_mode = self._mode_at(parent_fd, filename)
            if expected_content is not None:
                current = self._read_at(parent_fd, filename)
                if current != expected_content:
                    raise ToolExecutionError("file changed while awaiting approval; edit aborted")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            temporary_fd = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
            try:
                if target_mode is not None:
                    os.fchmod(temporary_fd, target_mode)
                with os.fdopen(temporary_fd, "w", encoding="utf-8") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                with suppress(OSError):
                    os.unlink(temporary, dir_fd=parent_fd)
                raise
            os.replace(
                temporary,
                filename,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        except ToolExecutionError:
            raise
        except OSError as error:
            raise ToolExecutionError(f"could not write file: {error}") from error
        finally:
            with suppress(OSError):
                os.unlink(temporary, dir_fd=parent_fd)
            os.close(parent_fd)

    def _safe_parts(self, raw_path: str) -> tuple[str, ...]:
        requested = Path(raw_path)
        if requested.is_absolute():
            raise ToolExecutionError("path must be relative to the project root")
        parts = tuple(part for part in requested.parts if part not in {"", "."})
        if not parts or ".." in parts:
            raise ToolExecutionError("path escapes the project root")
        return parts

    def _open_parent(self, parts: tuple[str, ...], *, create: bool) -> int:
        if os.open not in os.supports_dir_fd or os.rename not in os.supports_dir_fd:
            raise ToolExecutionError("secure file writes require dir_fd support")
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        current_fd = os.open(self.root, flags)
        try:
            for part in parts:
                if create:
                    with suppress(FileExistsError):
                        os.mkdir(part, dir_fd=current_fd)
                next_fd = os.open(part, flags, dir_fd=current_fd)
                os.close(current_fd)
                current_fd = next_fd
            return current_fd
        except BaseException:
            os.close(current_fd)
            raise

    @staticmethod
    def _read_at(parent_fd: int, filename: str) -> str:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(filename, flags, dir_fd=parent_fd)
            with os.fdopen(descriptor, encoding="utf-8") as handle:
                return handle.read()
        except UnicodeDecodeError as error:
            raise ToolExecutionError("edit only supports UTF-8 text files") from error
        except OSError as error:
            raise ToolExecutionError(f"could not read file: {error}") from error

    @staticmethod
    def _mode_at(parent_fd: int, filename: str) -> int | None:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(filename, flags, dir_fd=parent_fd)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ToolExecutionError(f"could not inspect file: {error}") from error
        try:
            return stat.S_IMODE(os.fstat(descriptor).st_mode)
        finally:
            os.close(descriptor)


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
        raw_path = cast(str, arguments["path"])
        path = workspace.resolve(raw_path)
        relative = workspace.display(path)
        token.checkpoint()
        if not approve(f"write {relative}"):
            return ToolOutcome(f"user denied writing {relative}", is_error=True)
        token.checkpoint()
        content = cast(str, arguments["content"])
        workspace.atomic_write(raw_path, content)
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
        raw_path = cast(str, arguments["path"])
        path = workspace.resolve(raw_path)
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
        workspace.atomic_write(
            raw_path,
            content.replace(old_text, new_text, 1),
            expected_content=content,
        )
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
