"""v0.4.0 快照沿用的事件和协作式取消。"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Literal, TypeAlias

from messages import AssistantMessage, ToolCall, ToolResultMessage


class Cancelled(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()
        self._reason = "cancelled by caller"

    def cancel(self, reason: str = "cancelled by caller") -> None:
        self._reason = reason
        self._event.set()

    def checkpoint(self) -> None:
        if self._event.is_set():
            raise Cancelled(self._reason)


@dataclass(frozen=True)
class ProviderTextDelta:
    delta: str


@dataclass(frozen=True)
class ProviderCompleted:
    message: AssistantMessage


ProviderEvent: TypeAlias = ProviderTextDelta | ProviderCompleted


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
    kind: Literal["cancelled", "provider", "protocol", "budget"]
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
