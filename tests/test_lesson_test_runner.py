from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_runner(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    runner = Path(__file__).parents[1] / "scripts" / "run_lesson_tests.py"
    return subprocess.run(
        [sys.executable, str(runner), "--lessons-dir", str(tmp_path / "lessons")],
        check=False,
        capture_output=True,
        text=True,
    )


def make_lesson(tmp_path: Path, test_source: str | None) -> Path:
    lesson_dir = tmp_path / "lessons" / "01-example"
    lesson_dir.mkdir(parents=True)
    if test_source is not None:
        tests_dir = lesson_dir / "tests"
        tests_dir.mkdir()
        if test_source:
            (tests_dir / "test_example.py").write_text(test_source, encoding="utf-8")
    return lesson_dir


def test_runner_executes_a_valid_lesson(tmp_path: Path) -> None:
    make_lesson(
        tmp_path,
        "import unittest\n\nclass ExampleTest(unittest.TestCase):\n"
        "    def test_ok(self):\n        self.assertTrue(True)\n",
    )

    completed = run_runner(tmp_path)

    assert completed.returncode == 0
    assert "Validated 1 frozen lesson suites." in completed.stdout


def test_runner_rejects_a_lesson_without_tests_directory(tmp_path: Path) -> None:
    make_lesson(tmp_path, None)

    completed = run_runner(tmp_path)

    assert completed.returncode != 0
    assert "missing tests directory" in completed.stderr


def test_runner_rejects_an_empty_test_suite(tmp_path: Path) -> None:
    make_lesson(tmp_path, "")

    completed = run_runner(tmp_path)

    assert completed.returncode != 0
    assert "no tests discovered" in completed.stderr


def test_runner_propagates_a_test_failure(tmp_path: Path) -> None:
    make_lesson(
        tmp_path,
        "import unittest\n\nclass ExampleTest(unittest.TestCase):\n"
        "    def test_failure(self):\n        self.fail('expected failure')\n",
    )

    completed = run_runner(tmp_path)

    assert completed.returncode != 0
    assert "FAILED" in completed.stderr
