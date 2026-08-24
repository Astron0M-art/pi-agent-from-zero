import pytest

from pi_agent_from_zero import AssistantMessage, FakeModel, ModelRequest, UserMessage


def request() -> ModelRequest:
    return ModelRequest("fake", "system", (UserMessage("hello"),), ("bash",))


def test_fake_model_can_compute_response_from_request() -> None:
    fake = FakeModel([lambda model_request: AssistantMessage(model_request.messages[0].content)])

    assert fake.complete(request()) == AssistantMessage("hello")
    assert fake.requests == [request()]


def test_fake_model_fails_loudly_when_script_is_exhausted() -> None:
    fake = FakeModel([])

    with pytest.raises(RuntimeError, match="no scripted response"):
        fake.complete(request())
