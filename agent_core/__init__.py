"""Core, runtime-agnostic agent definitions.

This package is the stable API that orchestrators and runtimes depend on.
"""

from agent_core.agent_spec import AgentSpec  # noqa: F401
from agent_core.prompting import PromptPolicy, build_system_prompt  # noqa: F401
from agent_core.tool_registry import (  # noqa: F401
    CONNECT_TOOL_NAME,
    MCP_SERVER_NAME,
    claude_allowed_tools_for_agent,
    mcp_prefixed_tool_name,
)

