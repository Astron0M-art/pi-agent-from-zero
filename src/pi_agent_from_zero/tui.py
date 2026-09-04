"""由 AgentEvent 驱动的确定性 TUI 状态与文本帧渲染。"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypeAlias

from pi_agent_from_zero.agent import Agent
from pi_agent_from_zero.coding_tools import create_coding_tools
from pi_agent_from_zero.events import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    CancellationToken,
    ProviderCompleted,
    ProviderTextDelta,
    TextDeltaEvent,
    ToolCompleted,
    ToolStarted,
)
from pi_agent_from_zero.messages import AssistantMessage, ToolCall, ToolResultMessage
from pi_agent_from_zero.providers import FakeModel, ModelRequest
from pi_agent_from_zero.tools import ToolRegistry

UiRole = Literal["user", "assistant"]
ToolCardStatus = Literal["running", "succeeded", "failed"]
RunStatus = Literal["idle", "running", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class InputBuffer:
    """最小输入区：插入、退格与提交。"""

    text: str = ""
    cursor: int = 0

    def __post_init__(self) -> None:
        if self.cursor < 0 or self.cursor > len(self.text):
            raise ValueError("cursor must stay inside the input text")

    def insert(self, value: str) -> InputBuffer:
        if "\n" in value or "\r" in value:
            raise ValueError("input buffer only accepts one line")
        return InputBuffer(
            self.text[: self.cursor] + value + self.text[self.cursor :],
            self.cursor + len(value),
        )

    def backspace(self) -> InputBuffer:
        if self.cursor == 0:
            return self
        return InputBuffer(
            self.text[: self.cursor - 1] + self.text[self.cursor :],
            self.cursor - 1,
        )

    def submit(self) -> tuple[str, InputBuffer]:
        prompt = self.text.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        return prompt, InputBuffer()


@dataclass(frozen=True, slots=True)
class MessageView:
    role: UiRole
    content: str


@dataclass(frozen=True, slots=True)
class ToolCard:
    call_id: str
    name: str
    arguments: Mapping[str, object]
    status: ToolCardStatus = "running"
    output: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


TimelineItem: TypeAlias = MessageView | ToolCard


@dataclass(frozen=True, slots=True)
class TuiState:
    """仅供显示的状态；不是模型上下文，也不是持久 Session。"""

    input_buffer: InputBuffer = field(default_factory=InputBuffer)
    timeline: tuple[TimelineItem, ...] = ()
    status: RunStatus = "idle"
    status_detail: str = "Ready"
    assistant_streaming: bool = False

    @property
    def messages(self) -> tuple[MessageView, ...]:
        return tuple(item for item in self.timeline if isinstance(item, MessageView))

    @property
    def tool_cards(self) -> tuple[ToolCard, ...]:
        return tuple(item for item in self.timeline if isinstance(item, ToolCard))


def reduce_event(state: TuiState, event: AgentEvent) -> TuiState:
    """把一个不可变 Agent 事件归约成新的显示状态。"""

    if isinstance(event, AgentStarted):
        return replace(
            state,
            input_buffer=InputBuffer(),
            timeline=(*state.timeline, MessageView("user", event.prompt)),
            status="running",
            status_detail="Agent is working",
            assistant_streaming=False,
        )
    if isinstance(event, TextDeltaEvent):
        if (
            state.assistant_streaming
            and state.timeline
            and isinstance(state.timeline[-1], MessageView)
        ):
            current = state.timeline[-1]
            timeline = (
                *state.timeline[:-1],
                MessageView("assistant", current.content + event.delta),
            )
        else:
            timeline = (*state.timeline, MessageView("assistant", event.delta))
        return replace(state, timeline=timeline, assistant_streaming=True)
    if isinstance(event, AssistantCompleted):
        if (
            state.assistant_streaming
            and state.timeline
            and isinstance(state.timeline[-1], MessageView)
        ):
            timeline = (
                *state.timeline[:-1],
                MessageView("assistant", event.message.content),
            )
        elif event.message.content:
            timeline = (*state.timeline, MessageView("assistant", event.message.content))
        else:
            timeline = state.timeline
        return replace(state, timeline=timeline, assistant_streaming=False)
    if isinstance(event, ToolStarted):
        card = ToolCard(event.call.id, event.call.name, event.call.arguments)
        return replace(
            state,
            timeline=(*state.timeline, card),
            status="running",
            status_detail=f"Running {event.call.name}",
        )
    if isinstance(event, ToolCompleted):
        timeline = tuple(
            replace(
                card,
                status="failed" if event.result.is_error else "succeeded",
                output=event.result.content,
            )
            if isinstance(card, ToolCard) and card.call_id == event.result.tool_call_id
            else card
            for card in state.timeline
        )
        outcome = "failed" if event.result.is_error else "finished"
        return replace(
            state, timeline=timeline, status_detail=f"Tool {event.result.tool_name} {outcome}"
        )
    if isinstance(event, AgentCompleted):
        return replace(
            state,
            status="completed",
            status_detail="Task completed",
            assistant_streaming=False,
        )
    if isinstance(event, AgentFailed):
        return replace(
            state,
            status="failed",
            status_detail=f"{event.kind}: {event.message}",
            assistant_streaming=False,
        )
    return state


class TuiRenderer:
    """渲染固定宽高、无 ANSI 的教学帧，便于快照测试。"""

    def __init__(self, *, width: int = 72, height: int = 18) -> None:
        if width < 32:
            raise ValueError("width must be at least 32")
        if height < 8:
            raise ValueError("height must be at least 8")
        self.width = width
        self.height = height

    def render(self, state: TuiState) -> str:
        inner = self.width - 4
        border = "+" + "-" * (self.width - 2) + "+"
        body = self._body_lines(state, inner)
        available = self.height - 7
        if len(body) > available:
            body = ["... earlier entries hidden ...", *body[-(available - 1) :]]
        body.extend([""] * (available - len(body)))

        lines = [border, self._row("Pi Agent from Zero · TUI", inner), border]
        lines.extend(self._row(line, inner) for line in body)
        lines.extend(
            [
                border,
                self._row(self._input_line(state.input_buffer), inner),
                self._row(f"STATUS> {state.status} · {state.status_detail}", inner),
                border,
            ]
        )
        return "\n".join(lines)

    def _body_lines(self, state: TuiState, width: int) -> list[str]:
        lines: list[str] = []
        for item in state.timeline:
            if isinstance(item, MessageView):
                prefix = "YOU> " if item.role == "user" else "AI > "
                lines.extend(_wrap(prefix, item.content, width))
            else:
                arguments = json.dumps(dict(item.arguments), ensure_ascii=False, sort_keys=True)
                lines.extend(_wrap(f"[{item.status.upper()}] {item.name} ", arguments, width))
                if not item.output:
                    continue
                preview = " ".join(item.output.splitlines())
                lines.extend(_wrap("  -> ", preview, width))
        return lines

    @staticmethod
    def _input_line(buffer: InputBuffer) -> str:
        return f"INPUT> {buffer.text[: buffer.cursor]}|{buffer.text[buffer.cursor :]}"

    @staticmethod
    def _row(content: str, width: int) -> str:
        clipped = content[:width]
        return f"| {clipped.ljust(width)} |"


def _wrap(prefix: str, content: str, width: int) -> list[str]:
    normalized = " ".join(content.splitlines())
    available = max(1, width - len(prefix))
    chunks = textwrap.wrap(normalized, width=available) or [""]
    continuation = " " * len(prefix)
    return [
        f"{prefix if index == 0 else continuation}{chunk}" for index, chunk in enumerate(chunks)
    ]


class TuiApp:
    """连接输入区、Agent 事件流和渲染器；本版一次只运行一个 prompt。"""

    def __init__(self, agent: Agent, renderer: TuiRenderer | None = None) -> None:
        self.agent = agent
        self.renderer = renderer or TuiRenderer()
        self.state = TuiState()

    def type_text(self, text: str) -> None:
        self.state = replace(self.state, input_buffer=self.state.input_buffer.insert(text))

    def frames(self) -> Iterator[str]:
        prompt, cleared = self.state.input_buffer.submit()
        self.state = replace(self.state, input_buffer=cleared)
        for event in self.agent.stream(prompt):
            self.state = reduce_event(self.state, event)
            yield self.renderer.render(self.state)


def _finish(
    request: ModelRequest, cancellation: CancellationToken
) -> Iterator[ProviderTextDelta | ProviderCompleted]:
    del cancellation
    result = request.messages[-1]
    assert isinstance(result, ToolResultMessage)
    text = "找到 README 中的项目标题。" if not result.is_error else "搜索失败。"
    yield ProviderTextDelta(text)
    yield ProviderCompleted(AssistantMessage(text))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行离线 TUI 文本帧演示（非交互式终端）")
    parser.add_argument("prompt", nargs="?", default="在 README 里搜索 Pi Agent")
    args = parser.parse_args()
    opening = "我先搜索 README。"
    fake = FakeModel(
        [
            [
                ProviderTextDelta(opening),
                ProviderCompleted(
                    AssistantMessage(
                        opening,
                        (ToolCall("grep-1", "grep", {"query": "Pi Agent", "path": "README.md"}),),
                    )
                ),
            ],
            _finish,
        ]
    )
    agent = Agent(
        fake,
        ToolRegistry(create_coding_tools(Path.cwd(), lambda _operation: False)),
        model="fake-scripted",
    )
    app = TuiApp(agent)
    app.type_text(args.prompt)
    frames = list(app.frames())
    print(frames[-1])


if __name__ == "__main__":
    main()
