"""v0.2.0 冻结快照：统一 Message、Provider 接口和 FakeModel。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from messages import AssistantMessage, Message, ToolCall, ToolResultMessage, UserMessage
from providers import FakeModel, ModelRequest, Provider

Approval = Callable[[str], bool]


class Agent:
    def __init__(
        self,
        provider: Provider,
        approve: Approval,
        *,
        model: str = "default",
        system_prompt: str = "You are a local coding agent.",
        cwd: Path | None = None,
        max_turns: int = 8,
        timeout_seconds: float = 10,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.provider = provider
        self.approve = approve
        self.model = model
        self.system_prompt = system_prompt
        self.cwd = (cwd or Path.cwd()).resolve()
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.messages: list[Message] = []

    def run(self, prompt: str) -> str:
        self.messages.append(UserMessage(prompt))
        for _ in range(self.max_turns):
            reply = self.provider.complete(
                ModelRequest(
                    self.model,
                    self.system_prompt,
                    tuple(self.messages),
                    available_tools=("bash",),
                )
            )
            self.messages.append(reply)
            if not reply.tool_calls:
                return reply.content
            self.messages.extend(self._execute(call) for call in reply.tool_calls)
        raise RuntimeError(f"agent exceeded {self.max_turns} turns")

    def _execute(self, call: ToolCall) -> ToolResultMessage:
        if call.name != "bash":
            return self._error(call, f"unknown tool: {call.name}")
        command = call.arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return self._error(call, "bash.command must be a non-empty string")
        if not self.approve(command):
            return self._error(call, "user denied the bash command")

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
            return self._error(call, f"command timed out after {self.timeout_seconds:g}s")

        output = completed.stdout + completed.stderr
        is_error = completed.returncode != 0
        if is_error:
            output += f"\ncommand exited with {completed.returncode}"
        return ToolResultMessage(call.id, call.name, output or "(no output)", is_error)

    @staticmethod
    def _error(call: ToolCall, message: str) -> ToolResultMessage:
        return ToolResultMessage(call.id, call.name, message, is_error=True)


def final_reply(request: ModelRequest) -> AssistantMessage:
    result = request.messages[-1]
    assert isinstance(result, ToolResultMessage)
    return AssistantMessage(f"任务演示完成，bash 返回：\n{result.content}")


def ask(command: str) -> bool:
    return input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ").strip().lower() in {"y", "yes"}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.2.0 消息与 Provider 离线演示")
    parser.add_argument("prompt", nargs="?", default="告诉我当前目录")
    args = parser.parse_args()
    fake = FakeModel(
        [
            AssistantMessage(
                "我先确认当前工作目录。", (ToolCall("call-1", "bash", {"command": "pwd"}),)
            ),
            final_reply,
        ]
    )
    print(Agent(fake, ask, model="fake-scripted").run(args.prompt))
