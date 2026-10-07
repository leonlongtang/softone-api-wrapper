from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_platform.specs import AgentSpec


@dataclass(slots=True)
class RunContext:
    """Execution context the orchestrator carries across turns."""

    # Ollama runtime uses a host-managed session_id tied to its persistent MCP session.
    session_id: str | None = None
    # Cross-turn state (conversation history, etc.).
    artifacts: dict[str, Any] = field(default_factory=dict)


class ToolError(Exception):
    """Raised when an MCP tool returns the `{ok:false,error:{...}}` envelope.

    Orchestrators catch this to implement recovery and escalation.
    """

    def __init__(self, *, tool_name: str, error: dict[str, Any]):
        super().__init__()
        self.tool_name = tool_name
        self.error = error

    def __str__(self) -> str:
        msg = str(self.error.get("message") or "Tool failed.")
        code = self.error.get("code")
        return f"{self.tool_name} failed ({code}): {msg}" if code is not None else f"{self.tool_name} failed: {msg}"


class RuntimeAdapter(Protocol):
    name: str

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        """Execute one user turn and return assistant text.

        May raise `ToolError` on an `ok:false` tool envelope, or `RuntimeError` on
        misconfiguration / startup failures.
        """
        ...
