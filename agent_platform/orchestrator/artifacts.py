from __future__ import annotations

from typing import Any, TypedDict

SESSION_ID_KEY = "session_id"
OLLAMA_HISTORY_KEY = "ollama_history"
PENDING_USER_TEXT_KEY = "pending_user_text"
LAST_ROUTE_KEY = "last_route"
ACTIVE_FLOW_KEY = "active_flow"


class OrchestratorArtifacts(TypedDict, total=False):
    """Known artifact keys persisted across orchestrator turns.

    Notes:
    - Some values (like LangChain message history) are runtime/library-specific,
      so they remain typed as `Any` until we define a stable serialization format.
    """

    session_id: str
    ollama_history: dict[str, Any]
    pending_user_text: str
    last_route: str
    active_flow: str


__all__ = [
    "SESSION_ID_KEY",
    "OLLAMA_HISTORY_KEY",
    "PENDING_USER_TEXT_KEY",
    "LAST_ROUTE_KEY",
    "ACTIVE_FLOW_KEY",
    "OrchestratorArtifacts",
]

