"""从零构建本地 Coding Agent 的教学实现。"""

from pi_agent_from_zero.agent import Agent, AgentRunError
from pi_agent_from_zero.events import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentStarted,
    AssistantCompleted,
    CancellationRequested,
    CancellationToken,
    DeadlineExceeded,
    ProviderCompleted,
    ProviderEvent,
    ProviderFailed,
    ProviderTextDelta,
    TextDeltaEvent,
    ToolCompleted,
    ToolStarted,
)
from pi_agent_from_zero.messages import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_from_zero.providers import FakeModel, ModelRequest, Provider
from pi_agent_from_zero.tools import (
    SchemaDefinitionError,
    SchemaValidationError,
    Tool,
    ToolDefinition,
    ToolExecutionError,
    ToolOutcome,
    ToolRegistry,
    create_bash_tool,
    validate_arguments,
)

__all__ = [
    "Agent",
    "AgentCompleted",
    "AgentEvent",
    "AgentFailed",
    "AgentRunError",
    "AgentStarted",
    "AssistantMessage",
    "AssistantCompleted",
    "CancellationRequested",
    "CancellationToken",
    "DeadlineExceeded",
    "FakeModel",
    "Message",
    "ModelRequest",
    "Provider",
    "ProviderCompleted",
    "ProviderEvent",
    "ProviderFailed",
    "ProviderTextDelta",
    "TextDeltaEvent",
    "Tool",
    "ToolCall",
    "ToolResultMessage",
    "ToolCompleted",
    "ToolDefinition",
    "ToolExecutionError",
    "ToolOutcome",
    "ToolRegistry",
    "ToolStarted",
    "UserMessage",
    "SchemaDefinitionError",
    "SchemaValidationError",
    "__version__",
    "create_bash_tool",
    "validate_arguments",
]

__version__ = "0.4.0"
