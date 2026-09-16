from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """Raised when a tool returns the `{ok:false,error:{...}}` envelope.

    This is part of the runtime boundary contract: orchestrators may catch this
    to implement retries/escalation/recovery.
    """

    def __init__(self, *, tool_name: str, error: dict[str, Any]):
        # Avoid dataclass(frozen/slots) on Exceptions: some runtimes/tool stacks
        # attach tracebacks by setting attributes on the exception instance.
        super().__init__()
        self.tool_name = tool_name
        self.error = error

    def __str__(self) -> str:  # pragma: no cover
        msg = str(self.error.get("message") or "Tool failed.")
        code = self.error.get("code")
        return (
            f"{self.tool_name} failed ({code}): {msg}"
            if code is not None
            else f"{self.tool_name} failed: {msg}"
        )


__all__ = ["ToolError"]

