from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_platform.gate import WriteGate
from agent_platform.specs import AgentSpec

# Shared conversation history in RunContext.artifacts (a list of LangChain messages).
HISTORY_KEY = "history"
# ToolError code for malformed tool input: a model mistake, the one error worth escalating.
BAD_TOOL_INPUT = "BAD_TOOL_INPUT"


@dataclass(slots=True)
class RunContext:
    """Execution context the orchestrator carries across turns."""

    # Ollama runtime uses a host-managed session_id tied to its persistent MCP session.
    session_id: str | None = None
    # Cross-turn state (conversation history, etc.).
    artifacts: dict[str, Any] = field(default_factory=dict)
    # Write confirmation shared by all runtimes; runtimes must consult it before any tool call.
    gate: WriteGate = field(default_factory=WriteGate)


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
