"""v0.3.0 教学快照：流式事件、统一超时和取消。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Generator, Iterator
from pathlib import Path

from events import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    CancellationToken,
    Cancelled,
    DeadlineExceeded,
    ProviderCompleted,
    ProviderFailed,
    ProviderTextDelta,
    TextDelta,
    ToolCompleted,
    ToolStarted,
)
from messages import AssistantMessage, Message, ToolCall, ToolResultMessage, UserMessage
from providers import ModelRequest, Provider

Approval = Callable[[str], bool]


class ProtocolError(RuntimeError):
    pass


class Agent:
    def __init__(
        self,
        provider: Provider,
        approve: Approval,
        *,
        cwd: Path | None = None,
        max_turns: int = 8,
    ) -> None:
        self.provider = provider
        self.approve = approve
        self.cwd = (cwd or Path.cwd()).resolve()
        self.max_turns = max_turns
        self.messages: list[Message] = []

    def stream(
        self, prompt: str, *, cancellation: CancellationToken | None = None
    ) -> Iterator[AgentEvent]:
        token = cancellation or CancellationToken()
        yield AgentStarted(prompt)
        try:
            token.checkpoint()
            self.messages.append(UserMessage(prompt))
            for _ in range(self.max_turns):
                reply = yield from self._reply(token)
                self.messages.append(reply)
                yield AssistantCompleted(reply)
                if not reply.tool_calls:
                    yield AgentCompleted(reply.content)
                    return
                for call in reply.tool_calls:
                    token.checkpoint()
                    yield ToolStarted(call)
                    result = self._execute(call, token)
                    self.messages.append(result)
                    yield ToolCompleted(result)
            yield AgentFailed("budget", f"agent exceeded {self.max_turns} turns")
        except Cancelled as error:
            yield AgentFailed("cancelled", str(error))
        except DeadlineExceeded as error:
            yield AgentFailed("timeout", str(error))
        except ProtocolError as error:
            yield AgentFailed("protocol", str(error))
        except RuntimeError as error:
            yield AgentFailed("provider", str(error))

    def _reply(self, token: CancellationToken) -> Generator[AgentEvent, None, AssistantMessage]:
        request = ModelRequest(
            "fake", "You are a local coding agent.", tuple(self.messages), ("bash",)
        )
        deltas: list[str] = []
        completed: AssistantMessage | None = None
        provider_failure: ProviderFailed | None = None
        terminal_seen = False
        for event in self.provider.stream(request, token):
            token.checkpoint()
            if terminal_seen:
                raise ProtocolError("provider emitted an event after its terminal event")
            if isinstance(event, ProviderTextDelta):
                deltas.append(event.delta)
                yield TextDelta(event.delta)
            elif isinstance(event, ProviderCompleted):
                completed = event.message
                terminal_seen = True
            elif isinstance(event, ProviderFailed):
                provider_failure = event
                terminal_seen = True
            else:
                raise ProtocolError(f"unknown provider event: {type(event).__name__}")
        token.checkpoint()
        if provider_failure is not None:
            if provider_failure.kind == "cancelled":
                raise Cancelled(provider_failure.message)
            raise RuntimeError(provider_failure.message)
        if completed is None:
            raise ProtocolError("provider stream ended without a terminal event")
        if deltas and "".join(deltas) != completed.content:
            raise ProtocolError("streamed text does not match completed message")
        return completed

    def _execute(self, call: ToolCall, token: CancellationToken) -> ToolResultMessage:
        command = call.arguments.get("command")
        if call.name != "bash" or not isinstance(command, str):
            return ToolResultMessage(call.id, call.name, "invalid tool call", True)
        if not self.approve(command):
            return ToolResultMessage(call.id, call.name, "user denied command", True)
        token.checkpoint()
        try:
            completed = subprocess.run(
                ["bash", "-lc", command],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResultMessage(
                call.id,
                call.name,
                "command timed out after 5s",
                True,
            )
        token.checkpoint()
        output = completed.stdout + completed.stderr or "(no output)"
        return ToolResultMessage(call.id, call.name, output, completed.returncode != 0)


def ask(command: str) -> bool:
    try:
        answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    except EOFError:
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


class ReplProvider:
    """v0.2 Provider 边界的流式实现；每次请求都可由历史决定响应。"""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def stream(self, request: ModelRequest, cancellation: CancellationToken):
        self.requests.append(request)
        cancellation.checkpoint()
        user_indexes = [
            index
            for index, message in enumerate(request.messages)
            if isinstance(message, UserMessage)
        ]
        latest_user_index = user_indexes[-1]
        prompt = request.messages[latest_user_index].content
        current_turn = request.messages[latest_user_index:]
        if isinstance(current_turn[-1], ToolResultMessage):
            text = f"第 {len(user_indexes)} 轮完成，bash 返回：\n{current_turn[-1].content}"
            reply = AssistantMessage(text)
        elif prompt.startswith("/bash ") and prompt.removeprefix("/bash ").strip():
            command = prompt.removeprefix("/bash ").strip()
            text = f"第 {len(user_indexes)} 轮请求 Bash。"
            reply = AssistantMessage(
                text,
                (ToolCall(f"bash-{len(user_indexes)}", "bash", {"command": command}),),
            )
        elif prompt.strip() == "/bash":
            text = "用法：/bash <command>"
            reply = AssistantMessage(text)
        else:
            text = f"离线模型收到第 {len(user_indexes)} 轮：{prompt}"
            reply = AssistantMessage(text)
        yield ProviderTextDelta(text)
        yield ProviderCompleted(reply)


def print_turn(agent: Agent, prompt: str) -> None:
    for event in agent.stream(prompt):
        if isinstance(event, TextDelta):
            print(event.delta, end="", flush=True)
        elif isinstance(event, ToolStarted):
            print(f"\n[tool:start] {event.call.name}")
        elif isinstance(event, ToolCompleted):
            print(f"[tool:done] error={event.result.is_error}: {event.result.content}")
        elif isinstance(event, AgentFailed):
            print(f"\n[{event.kind}] {event.message}")
    print()


def repl(agent: Agent) -> None:
    print("Pi Agent from Zero v0.3 · Streaming + Cancellation")
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
            print_turn(agent, prompt)
        except KeyboardInterrupt:
            print("\n再见。")
            return


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.3.0 流式 Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    args = parser.parse_args()
    agent = Agent(ReplProvider(), ask)
    if args.prompt is not None:
        print_turn(agent, args.prompt)
        return
    repl(agent)


if __name__ == "__main__":
    main()
