"""由 AgentEvent 驱动的确定性 TUI 状态与文本帧渲染。"""

from __future__ import annotations

import json
import shlex
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
from pi_agent_from_zero.messages import (
    AssistantMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_from_zero.providers import FakeModel, ModelRequest
from pi_agent_from_zero.tools import ToolRegistry

UiRole = Literal["user", "assistant"]
ToolCardStatus = Literal["running", "succeeded", "failed"]
RunStatus = Literal["idle", "running", "completed", "failed"]

_REQUIRED_DEMO_CALL_ID = "grep-1"
_NO_GREP_MATCHES = "(no matches)"


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
    """按 Python 字符数渲染固定逻辑宽高、无 ANSI 的教学帧。"""

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
        clipped = _safe_inline_text(content)[:width]
        return f"| {clipped.ljust(width)} |"


def _safe_inline_text(content: str) -> str:
    """Make terminal controls visible instead of letting content execute them."""

    return "".join(
        character if ord(character) >= 32 and ord(character) != 127 else f"\\x{ord(character):02x}"
        for character in content
    )


def _safe_multiline_text(content: str) -> str:
    return "\n".join(_safe_inline_text(line) for line in content.splitlines())


def _wrap(prefix: str, content: str, width: int) -> list[str]:
    normalized = " ".join(_safe_inline_text(line) for line in content.splitlines())
    available = max(1, width - len(prefix))
    chunks = textwrap.wrap(normalized, width=available) or [""]
    continuation = " " * len(prefix)
    return [
        f"{prefix if index == 0 else continuation}{chunk}" for index, chunk in enumerate(chunks)
    ]


class TuiApp:
    """连接输入区、Agent 事件流和渲染器，并在多轮间保留状态。"""

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
    if result.is_error:
        text = "搜索失败。"
    elif result.content.strip() == _NO_GREP_MATCHES:
        text = "README 中没有找到项目标题。"
    else:
        text = "找到 README 中的项目标题。"
    yield ProviderTextDelta(text)
    yield ProviderCompleted(AssistantMessage(text))


class ReplProvider:
    """默认离线 Provider：普通对话回显，``/bash`` 走真实工具事件。"""

    provider_id = "repl-fake"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> Iterator[ProviderTextDelta | ProviderCompleted]:
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
    """把斜杠命令转换为可显示、可审批、可关联的 ToolCall。"""

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


def _ask(operation: str) -> bool:
    try:
        answer = input(f"允许执行操作 `{operation}` 吗？[y/N] ")
    except EOFError:
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


def _run_turn(app: TuiApp, prompt: str) -> None:
    existing_cards = len(app.state.tool_cards)
    app.type_text(prompt)
    frames = list(app.frames())
    for card in app.state.tool_cards[existing_cards:]:
        print(f"TOOL> {_safe_multiline_text(card.output)}")
    if frames:
        print(frames[-1])


def repl(app: TuiApp) -> None:
    """持续读取终端输入；TUI 是显示层，不截断 Agent 的会话历史。"""

    print("Pi Agent from Zero v0.6.2 · TUI 状态与文本帧")
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
            _run_turn(app, prompt)
        except KeyboardInterrupt:
            print("\n再见。")
            return


def _finalize_demo_state(state: TuiState) -> tuple[TuiState, int]:
    """Validate this scripted demo's one required grep result."""

    if state.status == "failed":
        return state, 1
    if state.status != "completed":
        return reduce_event(state, AgentFailed("runtime", "demo did not terminate")), 1

    required = next(
        (card for card in state.tool_cards if card.call_id == _REQUIRED_DEMO_CALL_ID),
        None,
    )
    if required is None:
        detail = "required grep result is missing"
    elif required.status == "failed":
        detail = "required grep tool failed"
    elif required.status != "succeeded":
        detail = "required grep tool did not finish"
    elif required.output.strip() == _NO_GREP_MATCHES:
        detail = "required grep found no matches"
    else:
        return state, 0
    return reduce_event(state, AgentFailed("runtime", detail)), 1


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行多轮 TUI 文本帧 Agent")
    parser.add_argument("prompt", nargs="?", help="提供后只运行一轮；省略则进入多轮对话")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="运行 v0.6.1 的一次性 README grep 演示（旧默认行为）",
    )
    args = parser.parse_args()
    if args.demo:
        opening = "我先搜索 README。"
        fake = FakeModel(
            [
                [
                    ProviderTextDelta(opening),
                    ProviderCompleted(
                        AssistantMessage(
                            opening,
                            (
                                ToolCall(
                                    _REQUIRED_DEMO_CALL_ID,
                                    "grep",
                                    {"query": "Pi Agent", "path": "README.md"},
                                ),
                            ),
                        )
                    ),
                ],
                _finish,
            ]
        )
        demo_agent = Agent(
            fake,
            ToolRegistry(create_coding_tools(Path.cwd(), lambda _operation: False)),
            model="fake-scripted",
        )
        demo_app = TuiApp(demo_agent)
        demo_app.type_text(args.prompt or "在 README 里搜索 Pi Agent")
        list(demo_app.frames())
        demo_app.state, exit_code = _finalize_demo_state(demo_app.state)
        print(demo_app.renderer.render(demo_app.state))
        if exit_code:
            raise SystemExit(exit_code)
        return
    agent = Agent(
        ReplProvider(),
        ToolRegistry(create_coding_tools(Path.cwd(), _ask)),
        model="repl-fake",
    )
    app = TuiApp(agent)
    if args.prompt is not None:
        _run_turn(app, args.prompt)
        return
    repl(app)


if __name__ == "__main__":
    main()
