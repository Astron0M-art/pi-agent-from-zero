"""v0.4.0: 使用工具 Registry 和双重循环预算的本地 Agent。"""

from __future__ import annotations

from collections.abc import Generator, Iterator

from pi_agent_from_zero.events import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    CancellationRequested,
    CancellationToken,
    DeadlineExceeded,
    FailureKind,
    ProviderCompleted,
    ProviderFailed,
    ProviderTextDelta,
    TextDeltaEvent,
    ToolCompleted,
    ToolStarted,
)
from pi_agent_from_zero.messages import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_from_zero.providers import FakeModel, ModelRequest, Provider
from pi_agent_from_zero.tools import ToolRegistry, create_bash_tool


class AgentRunError(RuntimeError):
    """为仍想一次性调用 Agent 的代码保留的失败接口。"""

    def __init__(self, kind: FailureKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class _ProviderError(RuntimeError):
    pass


class _ProtocolError(RuntimeError):
    pass


class _BudgetError(RuntimeError):
    pass


class Agent:
    """在 Provider 流和 Registry 工具结果之间循环，并发出生命周期事件。"""

    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        *,
        model: str = "default",
        system_prompt: str = "You are a local coding agent.",
        max_turns: int = 8,
        max_tool_calls: int = 16,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")
        self.provider = provider
        self.tools = tools
        self.model = model
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls
        self.messages: list[Message] = []

    def stream(
        self,
        prompt: str,
        *,
        cancellation: CancellationToken | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[AgentEvent]:
        """运行 Agent，并保证最终只产生一个 completed 或 failed 事件。"""

        token = CancellationToken(timeout_seconds, parent=cancellation)
        yield AgentStarted(prompt)
        try:
            token.checkpoint()
            self.messages.append(UserMessage(prompt))
            tool_calls_used = 0
            for _ in range(self.max_turns):
                reply = yield from self._stream_reply(token)
                self.messages.append(reply)
                yield AssistantCompleted(reply)
                if not reply.tool_calls:
                    yield AgentCompleted(reply.content)
                    return

                for call in reply.tool_calls:
                    token.checkpoint()
                    if tool_calls_used >= self.max_tool_calls:
                        raise _BudgetError(f"agent exceeded {self.max_tool_calls} tool calls")
                    tool_calls_used += 1
                    yield ToolStarted(call)
                    result = self.tools.execute(call, token)
                    self.messages.append(result)
                    yield ToolCompleted(result)

            raise _BudgetError(f"agent exceeded {self.max_turns} turns")
        except CancellationRequested as error:
            yield AgentFailed("cancelled", str(error))
        except DeadlineExceeded as error:
            yield AgentFailed("timeout", str(error))
        except _ProviderError as error:
            yield AgentFailed("provider", str(error))
        except _ProtocolError as error:
            yield AgentFailed("protocol", str(error))
        except _BudgetError as error:
            yield AgentFailed("budget", str(error))
        except Exception as error:  # pragma: no cover - 最终安全网
            yield AgentFailed("runtime", str(error))

    def run(
        self,
        prompt: str,
        *,
        cancellation: CancellationToken | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """消费事件流；兼容只需要最终文本的调用方。"""

        for event in self.stream(
            prompt, cancellation=cancellation, timeout_seconds=timeout_seconds
        ):
            if isinstance(event, AgentCompleted):
                return event.answer
            if isinstance(event, AgentFailed):
                raise AgentRunError(event.kind, event.message)
        raise AgentRunError("runtime", "agent stream ended without a terminal event")

    def _stream_reply(
        self, cancellation: CancellationToken
    ) -> Generator[AgentEvent, None, AssistantMessage]:
        request = ModelRequest(
            model=self.model,
            system_prompt=self.system_prompt,
            messages=tuple(self.messages),
            tools=self.tools.definitions,
        )
        deltas: list[str] = []
        completed: AssistantMessage | None = None
        terminal_seen = False
        try:
            for event in self.provider.stream(request, cancellation):
                cancellation.checkpoint()
                if terminal_seen:
                    raise _ProtocolError("provider emitted an event after its terminal event")
                if isinstance(event, ProviderTextDelta):
                    deltas.append(event.delta)
                    yield TextDeltaEvent(event.delta)
                elif isinstance(event, ProviderCompleted):
                    completed = event.message
                    terminal_seen = True
                elif isinstance(event, ProviderFailed):
                    terminal_seen = True
                    if event.kind == "cancelled":
                        raise CancellationRequested(event.message)
                    raise _ProviderError(event.message)
                else:
                    raise _ProtocolError(f"unknown provider event: {type(event).__name__}")
        except (CancellationRequested, DeadlineExceeded, _ProviderError, _ProtocolError):
            raise
        except Exception as error:
            raise _ProviderError(str(error)) from error

        if completed is None:
            raise _ProtocolError("provider stream ended without a terminal event")
        streamed_text = "".join(deltas)
        if deltas and streamed_text != completed.content:
            raise _ProtocolError("streamed text does not match completed message content")
        return completed


def _final_stream(
    request: ModelRequest, cancellation: CancellationToken
) -> Iterator[ProviderTextDelta | ProviderCompleted]:
    del cancellation
    result = request.messages[-1]
    assert isinstance(result, ToolResultMessage)
    text = f"任务演示完成，bash 返回：\n{result.content}"
    yield ProviderTextDelta(text)
    yield ProviderCompleted(AssistantMessage(text))


def _ask(command: str) -> bool:
    answer = input(f"允许执行 bash 命令 `{command}` 吗？[y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 v0.4.0 工具 Registry 离线演示")
    parser.add_argument("prompt", nargs="?", default="告诉我当前目录")
    args = parser.parse_args()
    first_text = "我先确认当前工作目录。"
    fake = FakeModel(
        [
            [
                ProviderTextDelta(first_text),
                ProviderCompleted(
                    AssistantMessage(
                        first_text,
                        (ToolCall("call-1", "bash", {"command": "pwd"}),),
                    )
                ),
            ],
            _final_stream,
        ]
    )
    registry = ToolRegistry([create_bash_tool(_ask)])
    agent = Agent(fake, registry, model="fake-scripted")
    for event in agent.stream(args.prompt):
        if isinstance(event, TextDeltaEvent):
            print(event.delta, end="", flush=True)
        elif isinstance(event, ToolStarted):
            print(f"\n[tool:start] {event.call.name}")
        elif isinstance(event, ToolCompleted):
            print(f"[tool:done] error={event.result.is_error}")
        elif isinstance(event, AgentCompleted):
            print()
        elif isinstance(event, AgentFailed):
            raise SystemExit(f"[{event.kind}] {event.message}")
