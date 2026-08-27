"""可替换的流式 Provider 和完全离线的 FakeModel。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from events import CancellationToken, ProviderEvent
from messages import Message


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system_prompt: str
    messages: tuple[Message, ...]
    available_tools: tuple[str, ...]


class Provider(Protocol):
    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> Iterable[ProviderEvent]: ...


StreamFactory: TypeAlias = Callable[[ModelRequest, CancellationToken], Iterable[ProviderEvent]]
ScriptedStream: TypeAlias = Sequence[ProviderEvent] | StreamFactory


class FakeModel:
    def __init__(self, streams: Sequence[ScriptedStream]) -> None:
        self._streams = list(streams)
        self.requests: list[ModelRequest] = []

    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        if not self._streams:
            raise RuntimeError("FakeModel has no scripted stream left")
        scripted = self._streams.pop(0)
        events = scripted(request, cancellation) if callable(scripted) else scripted
        for event in events:
            cancellation.checkpoint()
            yield event
