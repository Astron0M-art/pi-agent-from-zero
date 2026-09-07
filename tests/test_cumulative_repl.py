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


def _start(entry: Path, cwd: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(entry)],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _read_until(process: subprocess.Popen[str], marker: str) -> str:
    assert process.stdout is not None
    output = ""
    deadline = time.monotonic() + 5
    while marker not in output and time.monotonic() < deadline:
        character = process.stdout.read(1)
        if not character:
            break
        output += character
    return output


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
    process = _start(entry, tmp_path)
    output = _read_until(process, "Pi Agent > ")
    assert "Pi Agent > " in output, f"{version}: prompt not displayed"

    process.send_signal(signal.SIGINT)
    remaining_output, stderr = process.communicate(timeout=5)
    output += remaining_output

    assert process.returncode == 0, f"{version}: {output}\n{stderr}"
    assert "再见" in output


@pytest.mark.parametrize(("version", "entry"), LESSON_ENTRIES)
@pytest.mark.parametrize("phase", ["approval", "running"])
def test_every_version_exits_cleanly_when_tool_is_interrupted(
    version: str, entry: Path, phase: str, tmp_path: Path
) -> None:
    process = _start(entry, tmp_path)
    output = _read_until(process, "Pi Agent > ")
    assert process.stdin is not None
    command = "pwd" if phase == "approval" else "sleep 5"
    process.stdin.write(f"/bash {command}\n")
    process.stdin.flush()
    output += _read_until(process, "[y/N] ")
    assert "[y/N] " in output, f"{version}: approval prompt not displayed"
    if phase == "running":
        process.stdin.write("y\n")
        process.stdin.flush()
        time.sleep(0.1)

    process.send_signal(signal.SIGINT)
    remaining_output, stderr = process.communicate(timeout=5)
    output += remaining_output

    assert process.returncode == 0, f"{version}: {output}\n{stderr}"
    assert "再见" in output
    assert "Traceback" not in stderr


@pytest.mark.parametrize(
    ("version", "entry", "uses_registry"),
    [(version, entry, index > 0) for index, (version, entry) in enumerate(STREAMING_ENTRIES)],
)
def test_v03_and_later_preserve_cancellation_and_deadline(
    version: str, entry: Path, uses_registry: bool
) -> None:
    constructor = (
        "Agent(provider, ToolRegistry([]))"
        if uses_registry
        else "Agent(provider, lambda _command: True)"
    )
    registry_import = (
        "from tools import Tool, ToolDefinition, ToolOutcome, ToolRegistry\n"
        if uses_registry
        else ""
    )
    tool_timeout_program = ""
    if uses_registry:
        tool_timeout_program = (
            "from messages import ToolCall\n"
            "def slow_tool(_arguments, token):\n"
            "    time.sleep(0.01)\n"
            "    token.checkpoint()\n"
            "    return ToolOutcome('late')\n"
            "definition = ToolDefinition('slow', 'slow', "
            "{'type': 'object', 'properties': {}, 'additionalProperties': False})\n"
            "tool_reply = AssistantMessage(tool_calls=(ToolCall('slow-1', 'slow', {}),))\n"
            "tool_agent = Agent(FakeModel([[ProviderCompleted(tool_reply)]]), "
            "ToolRegistry([Tool(definition, slow_tool)]))\n"
            "tool_events = list(tool_agent.stream('tool', "
            "cancellation=CancellationToken(0.001)))\n"
            "print(tool_events[-1].kind, len(tool_agent.messages))\n"
        )
    program = (
        "import time\n"
        "from agent import Agent\n"
        "from events import CancellationToken, ProviderCompleted, ProviderTextDelta\n"
        "from messages import AssistantMessage\n"
        "from providers import FakeModel\n"
        f"{registry_import}"
        f"def make(provider):\n    return {constructor}\n"
        "class DirectProvider:\n"
        "    def __init__(self, factory):\n"
        "        self.factory = factory\n"
        "    def stream(self, request, token):\n"
        "        yield from self.factory(request, token)\n"
        "cancelled = CancellationToken()\n"
        "cancelled.cancel('test stop')\n"
        "first = make(FakeModel([]))\n"
        "cancel_events = list(first.stream('cancel', cancellation=cancelled))\n"
        "second = make(FakeModel([]))\n"
        "timeout_events = list(second.stream('timeout', cancellation=CancellationToken(0)))\n"
        "print(cancel_events[-1].kind, len(first.messages))\n"
        "print(timeout_events[-1].kind, len(second.messages))\n"
        "def cancel_mid(_request, token):\n"
        "    yield ProviderTextDelta('half')\n"
        "    token.cancel('mid-stream stop')\n"
        "    yield ProviderCompleted(AssistantMessage('half'))\n"
        "mid = make(DirectProvider(cancel_mid))\n"
        "mid_events = list(mid.stream('mid', cancellation=CancellationToken()))\n"
        "print(mid_events[-1].kind, len(mid.messages))\n"
        "def expire_mid(_request, _token):\n"
        "    yield ProviderTextDelta('half')\n"
        "    time.sleep(0.01)\n"
        "    yield ProviderCompleted(AssistantMessage('half'))\n"
        "late = make(DirectProvider(expire_mid))\n"
        "late_events = list(late.stream('late', cancellation=CancellationToken(0.001)))\n"
        "print(late_events[-1].kind, len(late.messages))\n"
        "bad = make(FakeModel([[ProviderTextDelta('a'), "
        "ProviderCompleted(AssistantMessage('b'))]]))\n"
        "bad_events = list(bad.stream('bad'))\n"
        "print(bad_events[-1].kind, len(bad.messages))\n"
        f"{tool_timeout_program}"
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
    expected = [
        "cancelled 0",
        "timeout 0",
        "cancelled 1",
        "timeout 1",
        "protocol 1",
    ]
    if uses_registry:
        expected.append("timeout 2")
    assert result.stdout.splitlines() == expected


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
