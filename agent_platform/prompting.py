from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RESOURCE_URIS: tuple[str, ...] = (
    "softone://capabilities",
    "softone://glossary",
)


@dataclass(frozen=True, slots=True)
class PromptPolicy:
    """Shared prompt policy knobs used across runtimes."""

    # If true, instruct the agent to read these resources before using tools.
    resource_uris: tuple[str, ...] = DEFAULT_RESOURCE_URIS

    # Enforce the MCP envelope rules explicitly in the system prompt.
    enforce_envelope: bool = True

    # If true, the system prompt tells the model to stop on ok:false rather than auto-retry.
    stop_on_tool_error: bool = True


def build_system_prompt(
    *,
    base: str,
    session_instruction: str | None,
    policy: PromptPolicy,
    extra_resource_uris: tuple[str, ...] = (),
) -> str:
    parts: list[str] = []
    parts.append(base.strip())

    if policy.resource_uris or extra_resource_uris:
        uniq = list(dict.fromkeys((*policy.resource_uris, *extra_resource_uris)))
        if uniq:
            parts.append(
                "BEFORE USING TOOLS:\n"
                + "\n".join([f"- Read resource: `{u}`" for u in uniq])
            )

    if session_instruction:
        parts.append(session_instruction.strip())

    if policy.enforce_envelope:
        parts.append(
            "TOOL RESPONSE ENVELOPE:\n"
            "- Success: `{ \"ok\": true, \"data\": ..., \"meta\": {\"trace_id\", \"tool\", \"actions\"} }`\n"
            "- Error: `{ \"ok\": false, \"error\": { \"code\", \"message\", \"details\" }, \"meta\": {\"trace_id\", \"tool\", \"actions\"} }`"
        )

    if policy.stop_on_tool_error:
        parts.append(
            "ON TOOL ERRORS (`ok: false`) — STRICT:\n"
            "- Stop and explain the error.\n"
            "- Do NOT retry blindly or adjust inputs without user confirmation."
        )

    parts.append(
        "WRITE CONFIRMATION (enforced by the platform, not by you):\n"
        "- When you have every input for a write, call the write tool directly. Do not ask first.\n"
        "- The platform blocks the call and shows the user the exact call to approve.\n"
        "- If a tool result says BLOCKED, briefly say what the call will change and wait. Do not retry it."
    )

    return "\n\n".join(p for p in parts if p).strip() + "\n"


