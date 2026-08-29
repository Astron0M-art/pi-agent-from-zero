"""流式 Provider 边界与离线 FakeModel。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from pi_agent_from_zero.events import CancellationToken, ProviderEvent
from pi_agent_from_zero.messages import Message
from pi_agent_from_zero.tools import ToolDefinition


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Agent 交给 Provider 的稳定输入。"""

    model: str
    system_prompt: str
    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...]


class Provider(Protocol):
    """把统一请求适配成可取消的 Provider 事件流。"""

    provider_id: str

    def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> Iterable[ProviderEvent]: ...


StreamFactory: TypeAlias = Callable[[ModelRequest, CancellationToken], Iterable[ProviderEvent]]
ScriptedStream: TypeAlias = Sequence[ProviderEvent] | StreamFactory


class FakeModel:
    """按脚本产生流事件并记录请求；测试不连接网络或付费模型。"""

    provider_id = "fake"

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
