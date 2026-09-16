from __future__ import annotations

from typing import TypedDict

from agent_platform.orchestrator.artifacts import OrchestratorArtifacts


class OrchestratorState(TypedDict, total=False):
    user_text: str
    route: str
    runtime: str
    response: str
    failures: int
    debug: bool
    # Shared artifacts across nodes (order_id, invoice_id, etc.)
    artifacts: OrchestratorArtifacts

