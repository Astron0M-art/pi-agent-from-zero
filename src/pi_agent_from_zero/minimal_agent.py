"""v0.1.0: 一个刻意保持狭窄的最小 Agent 循环。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

HistoryEntry = dict[str, str]


@dataclass(frozen=True)
class ModelOutput:
    """单一模型本轮给出的文本，或一个 Bash 工具请求。"""

    text: str = ""
    bash_command: str | None = None


Model = Callable[[Sequence[HistoryEntry]], ModelOutput]
Approval = Callable[[str], bool]


class Agent:
    """在模型和一个需要审批的 Bash 工具之间循环。"""

    def __init__(
        self,
        model: Model,
        approve: Approval,
        *,
        cwd: Path | None = None,
        max_turns: int = 8,
        timeout_seconds: float = 10,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.model = model
        self.approve = approve
        self.cwd = (cwd or Path.cwd()).resolve()
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.history: list[HistoryEntry] = []

    def run(self, prompt: str) -> str:
        """运行到模型返回最终文本，或耗尽循环预算。"""

        self.history.append({"role": "user", "content": prompt})

        for _ in range(self.max_turns):
            output = self.model(tuple(dict(item) for item in self.history))
            assistant_entry = {"role": "assistant", "content": output.text}
            if output.bash_command is not None:
                assistant_entry["bash_command"] = output.bash_command
            self.history.append(assistant_entry)

            if output.bash_command is None:
                return output.text

            result = self._call_bash(output.bash_command)
            self.history.append({"role": "tool", "name": "bash", "content": result})

        raise RuntimeError(f"agent exceeded {self.max_turns} turns")

    def _call_bash(self, command: str) -> str:
        if not self.approve(command):
            return "DENIED: user rejected the bash command"

        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: command timed out after {self.timeout_seconds:g}s"

        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            output += f"\nERROR: command exited with {completed.returncode}"
        return output or "(no output)"


def _demo_model(history: Sequence[HistoryEntry]) -> ModelOutput:
    """无需 API Key 的确定性模型，用来观察循环而非模拟智能。"""

    tool_results = [item for item in history if item["role"] == "tool"]
    if not tool_results:
        return ModelOutput("我先确认当前工作目录。", "pwd")
    return ModelOutput(f"任务演示完成，bash 返回：\n{tool_results[-1]['content']}")


def _ask(command: str) -> bool:
    answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.1.0 最小 Agent 离线演示")
    parser.add_argument("prompt", nargs="?", default="告诉我当前目录")
    args = parser.parse_args()
    print(Agent(_demo_model, _ask).run(args.prompt))
