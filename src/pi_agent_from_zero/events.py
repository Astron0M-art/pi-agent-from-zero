"""Provider 流事件、Agent 运行事件与协作式取消。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event
from typing import Literal, TypeAlias

from pi_agent_from_zero.messages import AssistantMessage, ToolCall, ToolResultMessage


class CancellationRequested(RuntimeError):
    """调用方请求停止当前运行。"""


class DeadlineExceeded(TimeoutError):
    """当前运行超过统一截止时间。"""


class CancellationToken:
    """在线程安全标记或截止时间命中时，于检查点终止工作。"""

    def __init__(
        self,
        timeout_seconds: float | None = None,
        *,
        parent: CancellationToken | None = None,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds must not be negative")
        self._event = Event()
        self._reason = "cancelled by caller"
        self._deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        self._parent = parent

    def cancel(self, reason: str = "cancelled by caller") -> None:
        self._reason = reason
        self._event.set()

    def checkpoint(self) -> None:
        if self._parent is not None:
            self._parent.checkpoint()
        if self._event.is_set():
            raise CancellationRequested(self._reason)
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise DeadlineExceeded("agent run exceeded its timeout")


@dataclass(frozen=True, slots=True)
class ProviderTextDelta:
    delta: str


@dataclass(frozen=True, slots=True)
class ProviderCompleted:
    message: AssistantMessage


@dataclass(frozen=True, slots=True)
class ProviderFailed:
    message: str
    kind: Literal["error", "cancelled"] = "error"


ProviderEvent: TypeAlias = ProviderTextDelta | ProviderCompleted | ProviderFailed


@dataclass(frozen=True, slots=True)
class AgentStarted:
    prompt: str


@dataclass(frozen=True, slots=True)
class TextDeltaEvent:
    delta: str


@dataclass(frozen=True, slots=True)
class AssistantCompleted:
    message: AssistantMessage


@dataclass(frozen=True, slots=True)
class ToolStarted:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCompleted:
    result: ToolResultMessage


@dataclass(frozen=True, slots=True)
class AgentCompleted:
    answer: str


FailureKind: TypeAlias = Literal[
    "cancelled", "timeout", "provider", "protocol", "budget", "runtime"
]


@dataclass(frozen=True, slots=True)
class AgentFailed:
    kind: FailureKind
    message: str


AgentEvent: TypeAlias = (
    AgentStarted
    | TextDeltaEvent
    | AssistantCompleted
    | ToolStarted
    | ToolCompleted
    | AgentCompleted
    | AgentFailed
)
