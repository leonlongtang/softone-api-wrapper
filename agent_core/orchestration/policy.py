from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimePolicy:
    """Cost-aware runtime selection.

    This is intentionally simple at first; later you can replace this with:
    - confidence scoring
    - tool-error-aware routing
    - budget-aware scheduling
    """

    default_runtime: str = "ollama"
    escalation_runtime: str = "claude"
    max_ollama_failures_before_escalate: int = 1

    def choose(self, *, failures: int) -> str:
        if failures >= self.max_ollama_failures_before_escalate:
            return self.escalation_runtime
        return self.default_runtime


__all__ = ["RuntimePolicy"]

