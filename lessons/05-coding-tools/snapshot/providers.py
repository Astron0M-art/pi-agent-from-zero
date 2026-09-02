"""携带工具 Schema 的 ModelRequest 和离线 FakeModel。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from events import CancellationToken, ProviderEvent
from messages import Message
from tools import ToolDefinition


@dataclass(frozen=True)
class ModelRequest:
    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...]


StreamFactory: TypeAlias = Callable[[ModelRequest, CancellationToken], Iterable[ProviderEvent]]
ScriptedStream: TypeAlias = Sequence[ProviderEvent] | StreamFactory


class FakeModel:
    def __init__(self, streams: Sequence[ScriptedStream]) -> None:
        self._streams = list(streams)
        self.requests: list[ModelRequest] = []

    def stream(self, request: ModelRequest, token: CancellationToken) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        if not self._streams:
            raise RuntimeError("FakeModel has no scripted stream left")
        scripted = self._streams.pop(0)
        events = scripted(request, token) if callable(scripted) else scripted
        for event in events:
            token.checkpoint()
            yield event
