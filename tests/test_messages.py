import pytest

from pi_agent_from_zero import ToolCall


def test_tool_call_copies_and_freezes_arguments() -> None:
    source: dict[str, object] = {"command": "pwd"}
    call = ToolCall("call-1", "bash", source)

    source["command"] = "rm -rf demo"

    assert call.arguments["command"] == "pwd"
    with pytest.raises(TypeError):
        call.arguments["command"] = "changed"
