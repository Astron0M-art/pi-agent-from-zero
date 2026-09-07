"""v0.1.0 冻结快照：可连续对话的最小 Agent 与显式 Bash 审批。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

HistoryEntry = dict[str, str]


@dataclass(frozen=True)
class ModelOutput:
    text: str = ""
    bash_command: str | None = None


Model = Callable[[Sequence[HistoryEntry]], ModelOutput]
Approval = Callable[[str], bool]


class Agent:
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


def demo_model(history: Sequence[HistoryEntry]) -> ModelOutput:
    """确定性离线模型：普通文字回显，``/bash`` 触发工具调用。"""

    user_indexes = [index for index, item in enumerate(history) if item["role"] == "user"]
    latest_user_index = user_indexes[-1]
    current_turn = history[latest_user_index:]
    prompt = history[latest_user_index]["content"]

    if current_turn[-1]["role"] == "tool":
        result = current_turn[-1]["content"]
        return ModelOutput(f"第 {len(user_indexes)} 轮完成，bash 返回：\n{result}")
    if prompt.startswith("/bash ") and prompt.removeprefix("/bash ").strip():
        command = prompt.removeprefix("/bash ").strip()
        return ModelOutput(f"第 {len(user_indexes)} 轮请求 Bash。", command)
    if prompt.strip() == "/bash":
        return ModelOutput("用法：/bash <command>")
    return ModelOutput(f"离线模型收到第 {len(user_indexes)} 轮：{prompt}")


def ask(command: str) -> bool:
    try:
        answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    except EOFError:
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


def repl(agent: Agent) -> None:
    """复用同一个 Agent，让 history 跨用户轮次保留。"""

    print("Pi Agent from Zero v0.1 · 离线教学模式")
    print("普通文字可连续对话；/bash <command> 调用工具；/exit 退出。")
    while True:
        try:
            prompt = input("Pi Agent > ")
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return
        prompt = prompt.strip()
        if prompt in {"/exit", "/quit"}:
            print("再见。")
            return
        if not prompt:
            continue
        try:
            print(f"Assistant > {agent.run(prompt)}")
        except KeyboardInterrupt:
            print("\n再见。")
            return


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.1.0 最小 Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    args = parser.parse_args()
    agent = Agent(demo_model, ask)
    if args.prompt is not None:
        print(agent.run(args.prompt))
        return
    repl(agent)


if __name__ == "__main__":
    main()
