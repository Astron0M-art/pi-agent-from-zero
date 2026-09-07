from __future__ import annotations

import subprocess
import sys
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
