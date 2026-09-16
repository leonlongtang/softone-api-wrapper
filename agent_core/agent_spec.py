from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """A runtime-agnostic agent definition.

    The orchestrator and runtimes agree on this shape. It intentionally contains
    no runtime/provider details.
    """

    name: str
    system_prompt: str
    tool_names: tuple[str, ...] = field(default_factory=tuple)
    # Optional MCP resources an agent should read "up front" (prompt policy).
    resource_uris: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["AgentSpec"]

