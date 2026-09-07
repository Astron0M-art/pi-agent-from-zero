from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
LESSON_ENTRIES = (
    ("v0.1", PROJECT_ROOT / "lessons/01-minimal-agent/snapshot/agent.py"),
    ("v0.2", PROJECT_ROOT / "lessons/02-message-provider/snapshot/agent.py"),
    ("v0.3", PROJECT_ROOT / "lessons/03-streaming-cancellation/snapshot/agent.py"),
    ("v0.4", PROJECT_ROOT / "lessons/04-tool-runtime/snapshot/agent.py"),
    ("v0.5", PROJECT_ROOT / "lessons/05-coding-tools/snapshot/agent.py"),
    ("v0.6", PROJECT_ROOT / "lessons/06-tui-basics/snapshot/tui.py"),
)
CODING_TOOL_ENTRIES = LESSON_ENTRIES[-2:]
STREAMING_ENTRIES = LESSON_ENTRIES[2:]


def _run(entry: Path, transcript: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(entry)],
        cwd=cwd,
        input=transcript,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
def test_every_version_keeps_multi_turn_bash_and_yes(
    version: str, entry: Path, tmp_path: Path
) -> None:
    result = _run(
        entry,
        "你好\n/bash pwd\ny\n审批后继续聊\n/exit\n",
        tmp_path,
    )

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert "Pi Agent > " in result.stdout
    assert "第 1 轮" in result.stdout
    assert "第 3 轮" in result.stdout
    assert "允许执行" in result.stdout
    assert "`pwd`" in result.stdout
    assert str(tmp_path) in result.stdout
    assert "再见" in result.stdout


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
def test_every_version_denies_bash_without_ending_the_conversation(
    version: str, entry: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "must-not-exist.txt"
    result = _run(
        entry,
        f"/bash touch {marker.name}\nn\n拒绝以后还能继续\n/quit\n",
        tmp_path,
    )

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert not marker.exists()
    assert "denied" in result.stdout.lower() or "拒绝" in result.stdout
    assert "第 2 轮" in result.stdout
    assert "再见" in result.stdout


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
def test_every_version_exits_cleanly_on_eof(version: str, entry: Path, tmp_path: Path) -> None:
    result = _run(entry, "", tmp_path)

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert "Pi Agent > " in result.stdout
    assert "再见" in result.stdout


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
def test_every_version_accepts_full_yes(version: str, entry: Path, tmp_path: Path) -> None:
    result = _run(entry, "/bash printf yes-approved\nyes\n/exit\n", tmp_path)

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert "yes-approved" in result.stdout


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
def test_every_version_exits_cleanly_on_interrupt(
    version: str, entry: Path, tmp_path: Path
) -> None:
    process = subprocess.Popen(
        [sys.executable, str(entry)],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    output = ""
    deadline = time.monotonic() + 5
    while "Pi Agent > " not in output and time.monotonic() < deadline:
        character = process.stdout.read(1)
        if not character:
            break
        output += character
    assert "Pi Agent > " in output, f"{version}: prompt not displayed"

    process.send_signal(signal.SIGINT)
    remaining_output, stderr = process.communicate(timeout=5)
    output += remaining_output

    assert process.returncode == 0, f"{version}: {output}\n{stderr}"
    assert "再见" in output


@pytest.mark.parametrize(
    ("version", "entry", "uses_registry"),
    [(version, entry, index > 0) for index, (version, entry) in enumerate(STREAMING_ENTRIES)],
)
def test_v03_and_later_preserve_cancellation_and_deadline(
    version: str, entry: Path, uses_registry: bool
) -> None:
    constructor = (
        "Agent(FakeModel([]), ToolRegistry([]))"
        if uses_registry
        else "Agent(FakeModel([]), lambda _command: True)"
    )
    registry_import = "from tools import ToolRegistry\n" if uses_registry else ""
    program = (
        "from agent import Agent\n"
        "from events import CancellationToken\n"
        "from providers import FakeModel\n"
        f"{registry_import}"
        "cancelled = CancellationToken()\n"
        "cancelled.cancel('test stop')\n"
        f"first = {constructor}\n"
        "cancel_events = list(first.stream('cancel', cancellation=cancelled))\n"
        f"second = {constructor}\n"
        "timeout_events = list(second.stream('timeout', cancellation=CancellationToken(0)))\n"
        "print(cancel_events[-1].kind, len(first.messages))\n"
        "print(timeout_events[-1].kind, len(second.messages))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=entry.parent,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert result.stdout.splitlines() == ["cancelled 0", "timeout 0"]


@pytest.mark.parametrize(("version", "entry"), CODING_TOOL_ENTRIES)
def test_v05_and_later_combine_chat_with_project_tools(
    version: str, entry: Path, tmp_path: Path
) -> None:
    result = _run(
        entry,
        "/write note.txt alpha\ny\n/read note.txt\n"
        "/edit note.txt alpha beta\ny\n/grep beta note.txt\n/exit\n",
        tmp_path,
    )

    assert result.returncode == 0, f"{version}: {result.stdout}\n{result.stderr}"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "beta"
    assert "第 1 轮完成，write 返回" in result.stdout
    assert "第 2 轮完成，read 返回" in result.stdout
    assert "第 3 轮完成，edit 返回" in result.stdout
    assert "note.txt:1:beta" in result.stdout
