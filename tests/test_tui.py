from pathlib import Path

import pytest

from pi_agent_from_zero import (
    Agent,
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    AssistantMessage,
    FakeModel,
    InputBuffer,
    MessageView,
    ProviderCompleted,
    ProviderTextDelta,
    TextDeltaEvent,
    ToolCall,
    ToolCard,
    ToolCompleted,
    ToolRegistry,
    ToolResultMessage,
    ToolStarted,
    TuiApp,
    TuiRenderer,
    TuiState,
    create_coding_tools,
    reduce_event,
)


def test_input_buffer_edits_at_cursor_and_rejects_empty_submit() -> None:
    buffer = InputBuffer().insert("ac")
    buffer = InputBuffer(buffer.text, 1).insert("b")

    assert buffer == InputBuffer("abc", 2)
    assert buffer.backspace() == InputBuffer("ac", 1)
    assert buffer.submit() == ("abc", InputBuffer())
    with pytest.raises(ValueError, match="must not be empty"):
        InputBuffer("   ", 3).submit()
    with pytest.raises(ValueError, match="inside"):
        InputBuffer("x", 2)


def test_reducer_coalesces_stream_and_updates_tool_card() -> None:
    state = reduce_event(TuiState(), AgentStarted("inspect"))
    state = reduce_event(state, TextDeltaEvent("hel"))
    state = reduce_event(state, TextDeltaEvent("lo"))
    state = reduce_event(state, AssistantCompleted(AssistantMessage("hello")))
    call = ToolCall("read-1", "read", {"path": "README.md"})
    state = reduce_event(state, ToolStarted(call))
    state = reduce_event(
        state,
        ToolCompleted(ToolResultMessage("read-1", "read", "content")),
    )
    state = reduce_event(state, AgentCompleted("done"))

    assert state.messages == (
        MessageView("user", "inspect"),
        MessageView("assistant", "hello"),
    )
    assert state.tool_cards[0].status == "succeeded"
    assert state.tool_cards[0].output == "content"
    assert state.status == "completed"


def test_failed_tool_card_and_failed_run_remain_visible() -> None:
    call = ToolCall("write-1", "write", {"path": "x", "content": "x"})
    state = reduce_event(TuiState(), ToolStarted(call))
    state = reduce_event(
        state,
        ToolCompleted(ToolResultMessage("write-1", "write", "denied", is_error=True)),
    )
    state = reduce_event(state, AgentFailed("runtime", "boom"))

    assert state.tool_cards[0].status == "failed"
    assert state.status == "failed"
    assert state.status_detail == "runtime: boom"


def test_renderer_has_fixed_viewport_and_keeps_input_and_status() -> None:
    state = TuiState(
        input_buffer=InputBuffer("next", 4),
        timeline=tuple(MessageView("assistant", f"line {index}") for index in range(20)),
        status="running",
        status_detail="Agent is working",
    )
    renderer = TuiRenderer(width=48, height=12)

    frame = renderer.render(state)
    lines = frame.splitlines()

    assert len(lines) == 12
    assert all(len(line) == 48 for line in lines)
    assert "earlier entries hidden" in frame
    assert "INPUT> next|" in frame
    assert "STATUS> running" in frame


def test_tui_app_projects_agent_events_without_changing_model_history(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Pi Agent", encoding="utf-8")
    opening = "searching"
    fake = FakeModel(
        [
            [
                ProviderTextDelta(opening),
                ProviderCompleted(
                    AssistantMessage(
                        opening,
                        (ToolCall("grep-1", "grep", {"query": "Pi", "path": "README.md"}),),
                    )
                ),
            ],
            [ProviderCompleted(AssistantMessage("found"))],
        ]
    )
    agent = Agent(fake, ToolRegistry(create_coding_tools(tmp_path, lambda _operation: False)))
    app = TuiApp(agent, TuiRenderer(width=52, height=14))
    app.type_text("inspect")

    frames = list(app.frames())

    assert len(frames) == 7
    assert app.state.status == "completed"
    assert app.state.messages[-1] == MessageView("assistant", "found")
    assert app.state.tool_cards[0].status == "succeeded"
    assert isinstance(app.state.timeline[2], ToolCard)
    assert app.state.timeline[3] == MessageView("assistant", "found")
    assert len(agent.messages) == 4
    assert not any(isinstance(message, MessageView) for message in agent.messages)


@pytest.mark.parametrize(("width", "height"), [(31, 18), (72, 7)])
def test_renderer_rejects_unusable_viewport(width: int, height: int) -> None:
    with pytest.raises(ValueError):
        TuiRenderer(width=width, height=height)
