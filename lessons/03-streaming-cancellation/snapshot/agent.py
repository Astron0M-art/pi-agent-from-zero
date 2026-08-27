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
from providers import FakeModel, ModelRequest, Provider

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
                    result = self._execute(call)
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
        for event in self.provider.stream(request, token):
            token.checkpoint()
            if isinstance(event, ProviderTextDelta):
                deltas.append(event.delta)
                yield TextDelta(event.delta)
            elif isinstance(event, ProviderCompleted):
                completed = event.message
            elif isinstance(event, ProviderFailed):
                if event.kind == "cancelled":
                    raise Cancelled(event.message)
                raise RuntimeError(event.message)
        if completed is None:
            raise ProtocolError("provider stream ended without a terminal event")
        if deltas and "".join(deltas) != completed.content:
            raise ProtocolError("streamed text does not match completed message")
        return completed

    def _execute(self, call: ToolCall) -> ToolResultMessage:
        command = call.arguments.get("command")
        if call.name != "bash" or not isinstance(command, str):
            return ToolResultMessage(call.id, call.name, "invalid tool call", True)
        if not self.approve(command):
            return ToolResultMessage(call.id, call.name, "user denied command", True)
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = completed.stdout + completed.stderr or "(no output)"
        return ToolResultMessage(call.id, call.name, output, completed.returncode != 0)


def ask(command: str) -> bool:
    return input(f"允许执行 `{command}` 吗？[y/N] ").strip().lower() in {"y", "yes"}


def main() -> None:
    first = "我先查看当前目录。"

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
                    AssistantMessage(first, (ToolCall("call-1", "bash", {"command": "pwd"}),))
                ),
            ],
            finish,
        ]
    )
    for event in Agent(fake, ask).stream("告诉我当前目录"):
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
