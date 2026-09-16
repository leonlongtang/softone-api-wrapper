from __future__ import annotations

from dataclasses import dataclass

CONNECT_TOOL_NAME = "softone_connect_default"
MCP_SERVER_NAME = "softone"


@dataclass(frozen=True, slots=True)
class ToolMeta:
    name: str
    side_effects: str = "reads"  # "reads" | "writes"


def mcp_prefixed_tool_name(tool_name: str, *, server_name: str = MCP_SERVER_NAME) -> str:
    """Convert an MCP tool name to the Claude SDK tool namespace format."""
    return f"mcp__{server_name}__{tool_name}"


def claude_allowed_tools_for_agent(tool_names: tuple[str, ...]) -> list[str]:
    """Return a strict allowlist for Claude Agent SDK from an AgentSpec tool list."""
    # Always allow connect so the runtime can establish its own session.
    tools = [CONNECT_TOOL_NAME, *tool_names]
    # De-dup while preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for t in tools:
        if t in seen:
            continue
        seen.add(t)
        out.append(mcp_prefixed_tool_name(t))
    return out


__all__ = [
    "CONNECT_TOOL_NAME",
    "MCP_SERVER_NAME",
    "ToolMeta",
    "claude_allowed_tools_for_agent",
    "mcp_prefixed_tool_name",
]

