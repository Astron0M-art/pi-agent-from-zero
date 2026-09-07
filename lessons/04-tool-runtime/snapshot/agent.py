"""v0.4.0：由 Tool Registry 驱动、带双重预算的 Agent。"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from pathlib import Path

from events import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    CancellationToken,
    Cancelled,
    ProviderCompleted,
    ProviderTextDelta,
    TextDelta,
    ToolCompleted,
    ToolStarted,
)
from messages import AssistantMessage, Message, ToolCall, ToolResultMessage, UserMessage
from providers import ModelRequest, Provider
from tools import ToolRegistry, create_bash_tool


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

    def stream(self, prompt: str) -> Iterator[AgentEvent]:
        token = CancellationToken()
        yield AgentStarted(prompt)
        self.messages.append(UserMessage(prompt))
        tool_calls_used = 0
        try:
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
        except RuntimeError as error:
            yield AgentFailed("provider", str(error))

    def _reply(self, token: CancellationToken) -> Generator[AgentEvent, None, AssistantMessage]:
        request = ModelRequest(tuple(self.messages), self.tools.definitions)
        deltas: list[str] = []
        completed: AssistantMessage | None = None
        for event in self.provider.stream(request, token):
            if isinstance(event, ProviderTextDelta):
                deltas.append(event.delta)
                yield TextDelta(event.delta)
            elif isinstance(event, ProviderCompleted):
                completed = event.message
        if completed is None:
            raise RuntimeError("provider stream ended without completed event")
        if deltas and "".join(deltas) != completed.content:
            raise RuntimeError("streamed text does not match completed message")
        return completed


def ask(command: str) -> bool:
    try:
        answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


class ReplProvider:
    """在 Registry 版本中保留 v0.3 的多轮流式交互。"""

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
    print("Pi Agent from Zero v0.4 · Tool Registry + Budgets")
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
        print_turn(agent, prompt)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.4.0 Tool Registry Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    args = parser.parse_args()
    agent = Agent(ReplProvider(), ToolRegistry([create_bash_tool(ask, Path.cwd())]))
    if args.prompt is not None:
        print_turn(agent, args.prompt)
        return
    repl(agent)


if __name__ == "__main__":
    main()
