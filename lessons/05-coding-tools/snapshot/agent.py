"""v0.5.0：能在项目根目录内读、写、改、执行与搜索的 Agent。"""

from __future__ import annotations

import shlex
from collections.abc import Generator, Iterator
from pathlib import Path

from coding_tools import create_coding_tools
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
from tools import ToolRegistry


class Agent:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        *,
        max_turns: int = 8,
        max_tool_calls: int = 16,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls
        self.messages: list[Message] = []

    def stream(
        self, prompt: str, *, cancellation: CancellationToken | None = None
    ) -> Iterator[AgentEvent]:
        token = cancellation or CancellationToken()
        yield AgentStarted(prompt)
        try:
            token.checkpoint()
            self.messages.append(UserMessage(prompt))
            tool_calls_used = 0
            for _ in range(self.max_turns):
                reply = yield from self._reply(token)
                self.messages.append(reply)
                yield AssistantCompleted(reply)
                if not reply.tool_calls:
                    yield AgentCompleted(reply.content)
                    return
                for call in reply.tool_calls:
                    if tool_calls_used >= self.max_tool_calls:
                        yield AgentFailed(
                            "budget", f"agent exceeded {self.max_tool_calls} tool calls"
                        )
                        return
                    tool_calls_used += 1
                    yield ToolStarted(call)
                    result = self.tools.execute(call, token)
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
        request = ModelRequest(tuple(self.messages), self.tools.definitions)
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
            raise ProtocolError("provider stream ended without completed event")
        if deltas and "".join(deltas) != completed.content:
            raise ProtocolError("streamed text does not match completed message")
        return completed


class ProtocolError(RuntimeError):
    pass


def ask(operation: str) -> bool:
    try:
        answer = input(f"允许执行操作 `{operation}` 吗？[y/N] ")
    except EOFError:
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


class ReplProvider:
    """保留多轮 Bash，并让本版新增的五个工具共享同一 Registry。"""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def stream(self, request: ModelRequest, token: CancellationToken):
        self.requests.append(request)
        token.checkpoint()
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
            text = f"第 {len(user_indexes)} 轮完成，{result.tool_name} 返回：\n{result.content}"
            reply = AssistantMessage(text)
        elif prompt.startswith("/"):
            text, call = parse_tool_command(prompt, len(user_indexes))
            reply = AssistantMessage(text, (call,) if call else ())
        else:
            text = f"离线模型收到第 {len(user_indexes)} 轮：{prompt}"
            reply = AssistantMessage(text)
        yield ProviderTextDelta(text)
        yield ProviderCompleted(reply)


def parse_tool_command(prompt: str, turn: int) -> tuple[str, ToolCall | None]:
    """把教学用斜杠命令转换成 v0.5 的结构化 ToolCall。"""

    if prompt.startswith("/bash ") and prompt.removeprefix("/bash ").strip():
        command = prompt.removeprefix("/bash ").strip()
        return f"第 {turn} 轮请求 bash。", ToolCall(f"bash-{turn}", "bash", {"command": command})
    try:
        parts = shlex.split(prompt)
    except ValueError as error:
        return f"命令解析失败：{error}", None
    if len(parts) == 2 and parts[0] == "/read":
        return f"第 {turn} 轮请求 read。", ToolCall(f"read-{turn}", "read", {"path": parts[1]})
    if len(parts) in {2, 3} and parts[0] == "/grep":
        arguments = {"query": parts[1]}
        if len(parts) == 3:
            arguments["path"] = parts[2]
        return f"第 {turn} 轮请求 grep。", ToolCall(f"grep-{turn}", "grep", arguments)
    if len(parts) >= 3 and parts[0] == "/write":
        return f"第 {turn} 轮请求 write。", ToolCall(
            f"write-{turn}",
            "write",
            {"path": parts[1], "content": " ".join(parts[2:])},
        )
    if len(parts) == 4 and parts[0] == "/edit":
        return f"第 {turn} 轮请求 edit。", ToolCall(
            f"edit-{turn}",
            "edit",
            {"path": parts[1], "old_text": parts[2], "new_text": parts[3]},
        )
    return (
        "工具命令：/read <path>；/grep <query> [path]；"
        "/write <path> <content>；/edit <path> <old> <new>；/bash <command>",
        None,
    )


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
    print("Pi Agent from Zero v0.5 · Coding Tools")
    print("连续对话；/read、/grep、/write、/edit、/bash 调用工具；/exit 退出。")
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

    parser = argparse.ArgumentParser(description="运行 v0.5.0 Coding Tools Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    args = parser.parse_args()
    agent = Agent(ReplProvider(), ToolRegistry(create_coding_tools(Path.cwd(), ask)))
    if args.prompt is not None:
        print_turn(agent, args.prompt)
        return
    repl(agent)


if __name__ == "__main__":
    main()
