"""Provider 流、Agent 生命周期和协作式取消。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event
from typing import Literal, TypeAlias

from messages import AssistantMessage, ToolCall, ToolResultMessage


class Cancelled(RuntimeError):
    pass


class DeadlineExceeded(TimeoutError):
    pass


class CancellationToken:
    def __init__(self, timeout: float | None = None) -> None:
        self._cancelled = Event()
        self._reason = "cancelled by caller"
        self._deadline = None if timeout is None else time.monotonic() + timeout

    def cancel(self, reason: str = "cancelled by caller") -> None:
        self._reason = reason
        self._cancelled.set()

    def checkpoint(self) -> None:
        if self._cancelled.is_set():
            raise Cancelled(self._reason)
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise DeadlineExceeded("agent run exceeded its timeout")


@dataclass(frozen=True)
class ProviderTextDelta:
    delta: str


@dataclass(frozen=True)
class ProviderCompleted:
    message: AssistantMessage


@dataclass(frozen=True)
class ProviderFailed:
    message: str
    kind: Literal["error", "cancelled"] = "error"


ProviderEvent: TypeAlias = ProviderTextDelta | ProviderCompleted | ProviderFailed


@dataclass(frozen=True)
class AgentStarted:
    prompt: str


@dataclass(frozen=True)
class TextDelta:
    delta: str


@dataclass(frozen=True)
class AssistantCompleted:
    message: AssistantMessage


@dataclass(frozen=True)
class ToolStarted:
    call: ToolCall


@dataclass(frozen=True)
class ToolCompleted:
    result: ToolResultMessage


@dataclass(frozen=True)
class AgentCompleted:
    answer: str


@dataclass(frozen=True)
class AgentFailed:
    kind: Literal["cancelled", "timeout", "provider", "protocol", "budget", "runtime"]
    message: str


AgentEvent: TypeAlias = (
    AgentStarted
    | TextDelta
    | AssistantCompleted
    | ToolStarted
    | ToolCompleted
    | AgentCompleted
    | AgentFailed
)
