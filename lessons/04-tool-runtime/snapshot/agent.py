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
from providers import FakeModel, ModelRequest
from tools import ToolRegistry, create_bash_tool


class Agent:
    def __init__(
        self,
        provider: FakeModel,
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
    return input(f"允许执行 `{command}` 吗？[y/N] ").strip().lower() in {"y", "yes"}


def main() -> None:
    first = "我会通过 Registry 调用 bash。"

    def finish(request: ModelRequest, _token: CancellationToken):
        result = request.messages[-1]
        assert isinstance(result, ToolResultMessage)
        text = f"\n工具返回：{result.content}"
        return [ProviderTextDelta(text), ProviderCompleted(AssistantMessage(text))]

    fake = FakeModel(
        [
            [
                ProviderTextDelta(first),
                ProviderCompleted(
                    AssistantMessage(
                        first,
                        (ToolCall("call-1", "bash", {"command": "pwd"}),),
                    )
                ),
            ],
            finish,
        ]
    )
    registry = ToolRegistry([create_bash_tool(ask, Path.cwd())])
    for event in Agent(fake, registry).stream("告诉我当前目录"):
        if isinstance(event, TextDelta):
            print(event.delta, end="", flush=True)
        elif isinstance(event, ToolStarted):
            print(f"\n[tool:start] {event.call.name}")
        elif isinstance(event, ToolCompleted):
            print(f"[tool:done] error={event.result.is_error}")
        elif isinstance(event, AgentFailed):
            print(f"\n[{event.kind}] {event.message}")


if __name__ == "__main__":
    main()
