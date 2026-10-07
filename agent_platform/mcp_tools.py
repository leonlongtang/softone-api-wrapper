"""How runtimes reach the SoftOne MCP server: launch command and tool naming."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MCP_SERVER_NAME = "softone"
CONNECT_TOOL_NAME = "softone_connect_default"


def mcp_server_params() -> dict:
    """stdio launch params for the SoftOne MCP server subprocess."""
    return {
        "command": sys.executable,
        "args": ["-m", "softone_mcp.server"],
        "cwd": str(REPO_ROOT),
        "env": dict(os.environ),
    }


def mcp_prefixed_tool_name(tool_name: str) -> str:
    """Convert an MCP tool name to the Claude Agent SDK namespace."""
    return f"mcp__{MCP_SERVER_NAME}__{tool_name}"


def claude_allowed_tools_for_agent(tool_names: tuple[str, ...]) -> list[str]:
    """Strict Claude SDK allowlist for an agent: connect + the agent's own tools."""
    return [mcp_prefixed_tool_name(t) for t in dict.fromkeys((CONNECT_TOOL_NAME, *tool_names))]
