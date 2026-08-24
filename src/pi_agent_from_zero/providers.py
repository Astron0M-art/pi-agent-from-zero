"""模型 Provider 边界与离线 FakeModel。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from pi_agent_from_zero.messages import AssistantMessage, Message


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Agent 交给 Provider 的稳定输入。"""

    model: str
    system_prompt: str
    messages: tuple[Message, ...]
    available_tools: tuple[str, ...]


class Provider(Protocol):
    """把统一请求适配到某个模型服务，再返回统一消息。"""

    provider_id: str

    def complete(self, request: ModelRequest) -> AssistantMessage: ...


ResponseFactory: TypeAlias = Callable[[ModelRequest], AssistantMessage]
ScriptedResponse: TypeAlias = AssistantMessage | ResponseFactory


class FakeModel:
    """按脚本响应并记录请求；测试不连接网络或付费模型。"""

    provider_id = "fake"

    def __init__(self, responses: Sequence[ScriptedResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> AssistantMessage:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("FakeModel has no scripted response left")
        response = self._responses.pop(0)
        return response(request) if callable(response) else response
