"""v0.2.0: 使用统一消息和 Provider 边界的本地 Agent。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from pi_agent_from_zero.messages import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_from_zero.providers import FakeModel, ModelRequest, Provider

Approval = Callable[[str], bool]


class Agent:
    """让一个 Provider 在统一消息和审批后的 Bash 结果之间循环。"""

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
        """运行到 Provider 返回无工具调用的最终消息。"""

        self.messages.append(UserMessage(prompt))
        for _ in range(self.max_turns):
            reply = self.provider.complete(
                ModelRequest(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    messages=tuple(self.messages),
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
            return self._tool_error(call, f"unknown tool: {call.name}")

        command = call.arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return self._tool_error(call, "bash.command must be a non-empty string")
        if not self.approve(command):
            return self._tool_error(call, "user denied the bash command")

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
            return self._tool_error(call, f"command timed out after {self.timeout_seconds:g}s")

        output = completed.stdout + completed.stderr
        is_error = completed.returncode != 0
        if is_error:
            output += f"\ncommand exited with {completed.returncode}"
        return ToolResultMessage(
            tool_call_id=call.id,
            tool_name=call.name,
            content=output or "(no output)",
            is_error=is_error,
        )

    @staticmethod
    def _tool_error(call: ToolCall, message: str) -> ToolResultMessage:
        return ToolResultMessage(call.id, call.name, message, is_error=True)


def _final_reply(request: ModelRequest) -> AssistantMessage:
    result = request.messages[-1]
    assert isinstance(result, ToolResultMessage)
    return AssistantMessage(f"任务演示完成，bash 返回：\n{result.content}")


def _ask(command: str) -> bool:
    answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.2.0 消息与 Provider 离线演示")
    parser.add_argument("prompt", nargs="?", default="告诉我当前目录")
    args = parser.parse_args()
    fake = FakeModel(
        [
            AssistantMessage(
                "我先确认当前工作目录。", (ToolCall("call-1", "bash", {"command": "pwd"}),)
            ),
            _final_reply,
        ]
    )
    print(Agent(fake, _ask, model="fake-scripted").run(args.prompt))
