"""v0.2.0 冻结快照：保留多轮 REPL，再引入 Message 与 Provider。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from messages import AssistantMessage, Message, ToolCall, ToolResultMessage, UserMessage
from providers import ModelRequest, Provider

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


class ReplProvider:
    """根据当前用户轮次生成离线响应，同时记录请求供教学观察。"""

    provider_id = "repl-fake"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> AssistantMessage:
        self.requests.append(request)
        user_indexes = [
            index
            for index, message in enumerate(request.messages)
            if isinstance(message, UserMessage)
        ]
        latest_user_index = user_indexes[-1]
        prompt = request.messages[latest_user_index].content
        current_turn = request.messages[latest_user_index:]
        if isinstance(current_turn[-1], ToolResultMessage):
            result = current_turn[-1]
            return AssistantMessage(f"第 {len(user_indexes)} 轮完成，bash 返回：\n{result.content}")
        if prompt.startswith("/bash ") and prompt.removeprefix("/bash ").strip():
            command = prompt.removeprefix("/bash ").strip()
            return AssistantMessage(
                f"第 {len(user_indexes)} 轮请求 Bash。",
                (ToolCall(f"bash-{len(user_indexes)}", "bash", {"command": command}),),
            )
        if prompt.strip() == "/bash":
            return AssistantMessage("用法：/bash <command>")
        return AssistantMessage(f"离线模型收到第 {len(user_indexes)} 轮：{prompt}")


def ask(command: str) -> bool:
    try:
        answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


def repl(agent: Agent) -> None:
    print("Pi Agent from Zero v0.2 · Message + Provider")
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
        print(f"Assistant > {agent.run(prompt)}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.2.0 消息与 Provider Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    args = parser.parse_args()
    agent = Agent(ReplProvider(), ask, model="repl-fake")
    if args.prompt is not None:
        print(agent.run(args.prompt))
        return
    repl(agent)


if __name__ == "__main__":
    main()
