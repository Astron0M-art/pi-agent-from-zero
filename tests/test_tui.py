import subprocess
import sys
from pathlib import Path

import pytest

import pi_agent_from_zero.tui as tui_module
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
    Tool,
    ToolCall,
    ToolCard,
    ToolCompleted,
    ToolDefinition,
    ToolOutcome,
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


def test_renderer_keeps_exact_height_at_minimum_viewport() -> None:
    state = TuiState(
        timeline=tuple(MessageView("assistant", f"line {index}") for index in range(3))
    )

    frame = TuiRenderer(width=48, height=8).render(state)

    assert len(frame.splitlines()) == 8
    assert "earlier entries hidden" in frame


def test_renderer_escapes_terminal_control_sequences() -> None:
    state = TuiState(
        timeline=(MessageView("assistant", "safe\x1b]0;owned\x07text"),),
        status_detail="bad\x1b[2Jstatus",
    )

    frame = TuiRenderer(width=72, height=10).render(state)

    assert "\x1b" not in frame
    assert "\x07" not in frame
    assert "\\x1b]0;owned\\x07" in frame
    assert "\\x1b[2J" in frame


def test_raw_tool_summary_escapes_terminal_controls(capsys) -> None:
    definition = ToolDefinition(
        "bash",
        "Return hostile terminal text.",
        {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    )
    tool = Tool(definition, lambda _arguments, _token: ToolOutcome("\x1b]0;owned\x07"))
    fake = FakeModel(
        [
            [
                ProviderCompleted(
                    AssistantMessage(tool_calls=(ToolCall("bash-1", "bash", {"command": "x"}),))
                )
            ],
            [ProviderCompleted(AssistantMessage("done"))],
        ]
    )
    app = TuiApp(Agent(fake, ToolRegistry([tool])))

    tui_module._run_turn(app, "run")
    output = capsys.readouterr().out

    assert "\x1b" not in output
    assert "\x07" not in output
    assert "TOOL> \\x1b]0;owned\\x07" in output


def test_raw_tool_summary_keeps_line_breaks_without_escaping_them(capsys) -> None:
    definition = ToolDefinition(
        "bash",
        "Return two safe lines.",
        {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    )
    tool = Tool(definition, lambda _arguments, _token: ToolOutcome("first\nsecond\n"))
    fake = FakeModel(
        [
            [
                ProviderCompleted(
                    AssistantMessage(tool_calls=(ToolCall("bash-1", "bash", {"command": "x"}),))
                )
            ],
            [ProviderCompleted(AssistantMessage("done"))],
        ]
    )

    tui_module._run_turn(TuiApp(Agent(fake, ToolRegistry([tool]))), "run")
    output = capsys.readouterr().out

    assert "TOOL> first\nsecond\n" in output
    assert "\\x0a" not in output


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


def _console_script() -> Path:
    script = Path(sys.executable).with_name("pi-agent-zero")
    assert script.is_file(), "install the project before running its CLI tests"
    return script


def test_module_cli_reports_success_when_demo_readme_exists() -> None:
    result = subprocess.run(
        [_console_script(), "--demo"],
        cwd=Path(__file__).parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "[SUCCEEDED] grep" in result.stdout
    assert "STATUS> completed" in result.stdout


def test_default_cli_keeps_context_across_chat_bash_and_chat(tmp_path: Path) -> None:
    result = subprocess.run(
        [_console_script()],
        cwd=tmp_path,
        input="你好\n/bash pwd\ny\n继续聊\n/exit\n",
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "离线模型收到第 1 轮" in result.stdout
    assert "第 2 轮完成，bash 返回" in result.stdout
    assert str(tmp_path) in result.stdout
    assert "离线模型收到第 3 轮" in result.stdout
    assert "再见" in result.stdout


def test_default_cli_combines_coding_tools_in_one_session(tmp_path: Path) -> None:
    result = subprocess.run(
        [_console_script()],
        cwd=tmp_path,
        input=(
            "/write note.txt alpha\ny\n/read note.txt\n"
            "/edit note.txt alpha beta\ny\n/grep beta note.txt\n/exit\n"
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "beta"
    assert "第 1 轮完成，write 返回" in result.stdout
    assert "第 2 轮完成，read 返回" in result.stdout
    assert "第 3 轮完成，edit 返回" in result.stdout
    assert "note.txt:1:beta" in result.stdout


def test_repl_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys) -> None:
    agent = Agent(FakeModel([]), ToolRegistry([]))
    app = TuiApp(agent)

    def interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    tui_module.repl(app)

    assert "再见" in capsys.readouterr().out


def test_approval_prompt_escapes_terminal_controls(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: print(prompt, end="") or "n")

    approved = tui_module._ask("bash printf '\x1b]52;clipboard\x07'")
    output = capsys.readouterr().out

    assert approved is False
    assert "\x1b" not in output
    assert "\x07" not in output
    assert "\\x1b]52;clipboard\\x07" in output


def test_module_cli_reports_failure_when_demo_readme_is_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [_console_script(), "--demo"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "[FAILED] grep" in result.stdout
    assert "STATUS> failed" in result.stdout
    assert "STATUS> completed" not in result.stdout


def test_module_cli_reports_failure_when_required_grep_has_no_matches(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("unrelated project\n", encoding="utf-8")

    result = subprocess.run(
        [_console_script(), "--demo"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "[SUCCEEDED] grep" in result.stdout
    assert "(no matches)" in result.stdout
    assert "README 中没有找到项目标题。" in result.stdout
    assert "STATUS> failed" in result.stdout


def test_demo_finalizer_ignores_optional_failure_after_required_success() -> None:
    state = TuiState(
        timeline=(
            ToolCard("read-optional", "read", {}, "failed", "optional failure"),
            ToolCard("grep-1", "grep", {}, "succeeded", "Pi Agent from Zero"),
        ),
        status="completed",
        status_detail="Task completed",
    )

    final_state, exit_code = tui_module._finalize_demo_state(state)

    assert final_state is state
    assert exit_code == 0


def test_demo_finalizer_preserves_existing_terminal_failure() -> None:
    state = TuiState(
        timeline=(ToolCard("grep-1", "grep", {}, "failed", "missing"),),
        status="failed",
        status_detail="timeout: deadline exceeded",
    )

    final_state, exit_code = tui_module._finalize_demo_state(state)

    assert final_state is state
    assert final_state.status_detail == "timeout: deadline exceeded"
    assert exit_code == 1
