import pytest

from pi_agent_from_zero import (
    AssistantMessage,
    CancellationToken,
    FakeModel,
    ModelRequest,
    ProviderCompleted,
    UserMessage,
)


def request() -> ModelRequest:
    return ModelRequest("fake", "system", (UserMessage("hello"),), ("bash",))


def test_fake_model_can_compute_stream_from_request() -> None:
    def factory(model_request: ModelRequest, _token: CancellationToken):
        return [ProviderCompleted(AssistantMessage(model_request.messages[0].content))]

    fake = FakeModel([factory])

    assert list(fake.stream(request(), CancellationToken())) == [
        ProviderCompleted(AssistantMessage("hello"))
    ]
    assert fake.requests == [request()]


def test_fake_model_fails_loudly_when_script_is_exhausted() -> None:
    fake = FakeModel([])

    with pytest.raises(RuntimeError, match="no scripted stream"):
        list(fake.stream(request(), CancellationToken()))


def test_fake_model_checks_cancellation_before_each_event() -> None:
    token = CancellationToken()
    token.cancel("stop")
    fake = FakeModel([[ProviderCompleted(AssistantMessage("too late"))]])

    with pytest.raises(RuntimeError, match="stop"):
        list(fake.stream(request(), token))
