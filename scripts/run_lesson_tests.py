"""Run every frozen lesson test suite in an isolated Python process."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unittest
from pathlib import Path

LESSON_NAME = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*$")


def _discover_lesson_dirs(lessons_dir: Path) -> list[Path]:
    if not lessons_dir.is_dir():
        raise ValueError(f"lessons directory does not exist: {lessons_dir}")
    lesson_dirs = sorted(
        path for path in lessons_dir.iterdir() if path.is_dir() and LESSON_NAME.fullmatch(path.name)
    )
    if not lesson_dirs:
        raise ValueError(f"no numbered lesson directories found in: {lessons_dir}")
    return lesson_dirs


def _run_single_suite(tests_dir: Path) -> int:
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern="test*.py")
    test_count = suite.countTestCases()
    if test_count == 0:
        print(f"ERROR: no tests discovered in {tests_dir}", file=sys.stderr)
        return 2
    print(f"Running {test_count} tests from {tests_dir}", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def run_all_lessons(lessons_dir: Path, timeout_seconds: float) -> int:
    try:
        lesson_dirs = _discover_lesson_dirs(lessons_dir)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    test_dirs: list[Path] = []
    for lesson_dir in lesson_dirs:
        tests_dir = lesson_dir / "tests"
        if not tests_dir.is_dir():
            print(f"ERROR: missing tests directory: {tests_dir}", file=sys.stderr)
            return 2
        test_dirs.append(tests_dir)

    runner = Path(__file__).resolve()
    for tests_dir in test_dirs:
        print(f"\n=== {tests_dir.parent.name} ===", flush=True)
        try:
            completed = subprocess.run(
                [sys.executable, str(runner), "--suite", str(tests_dir)],
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            print(
                f"ERROR: lesson test suite exceeded {timeout_seconds:g}s: {tests_dir}",
                file=sys.stderr,
            )
            return 124
        if completed.returncode != 0:
            return completed.returncode

    print(f"\nValidated {len(test_dirs)} frozen lesson suites.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lessons-dir", type=Path, default=Path("lessons"))
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--suite", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.suite is not None:
        return _run_single_suite(args.suite)
    if args.timeout_seconds <= 0:
        print("ERROR: --timeout-seconds must be greater than zero", file=sys.stderr)
        return 2
    return run_all_lessons(args.lessons_dir, args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
