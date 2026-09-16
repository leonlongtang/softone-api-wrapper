from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_core.agent_spec import AgentSpec


@dataclass(slots=True)
class RunContext:
    """Execution context shared across orchestrator nodes (when applicable)."""

    # Ollama runtime uses a host-managed session_id tied to a persistent MCP session.
    session_id: str | None = None
    # Place for orchestrator to stash artifacts (order_id, invoice_id, etc.).
    artifacts: dict[str, Any] = field(default_factory=dict)


class RuntimeAdapter(Protocol):
    name: str

    async def run_turn(
        self,
        *,
        spec: AgentSpec,
        user_text: str,
        context: RunContext,
    ) -> str:
        """Execute one user turn and return assistant text.

        Runtime boundary contract:
        - May raise `agent_core.runtime.errors.ToolError` when an MCP tool returns
          an `{ok:false,error:{...}}` envelope.
        - May raise `RuntimeError` for misconfiguration/startup/connect failures.
        """


__all__ = ["RuntimeAdapter", "RunContext"]

