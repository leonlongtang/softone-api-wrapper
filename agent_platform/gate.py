"""Code-enforced write confirmation: the model cannot run a write tool the user hasn't approved.

Turn N:   the agent calls `create_order(...)` -> blocked, recorded, the user is shown the exact call.
Turn N+1: the user replies "yes ..." -> each blocked tool may run once. Any other reply clears them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

WRITE_TOOLS = frozenset(
    {
        "create_customer", "update_customer", "delete_customer",
        "create_item", "update_item", "delete_item", "inventory_adjustment",
        "create_order", "update_order", "add_order_line", "remove_order_line", "approve_order", "cancel_order",
        "create_invoice", "record_payment", "refund_payment",
        "workflow_create_order", "workflow_order_to_cash",
    }
)  # fmt: skip
READ_PREFIXES = ("get_", "list_", "search_", "check_")

APPROVAL_WORDS = {"yes", "y", "confirm", "confirmed", "approve", "proceed", "ok"}

NEEDS_CONFIRMATION = (
    "BLOCKED: `{tool}` changes data and the user has not approved it. Do not retry. "
    "Tell the user exactly what this call will change and ask them to reply 'yes' to approve."
)

ALREADY_DONE = "`{tool}` already ran with these exact arguments this turn. Do not repeat it; use its earlier result."


def is_approval(text: str) -> bool:
    t = text.strip().lower()
    first = re.match(r"[a-z]+", t)
    return t.startswith("go ahead") or bool(first and first.group() in APPROVAL_WORDS)


@dataclass
class WriteGate:
    # ponytail: approval is per tool name, not per exact args (model re-sends args with small
    # differences). Upgrade path: normalize args and compare them too.
    blocked: dict[str, dict[str, Any]] = field(default_factory=dict)  # tool -> args, this turn
    approved: set[str] = field(default_factory=set)
    ran: set[str] = field(default_factory=set)  # writes executed this turn, as "tool:args-json"

    def start_turn(self, user_text: str) -> None:
        self.approved = set(self.blocked) if is_approval(user_text) else set()
        self.blocked, self.ran = {}, set()

    def check(self, tool: str, args: dict[str, Any]) -> str | None:
        """Return None if the call may run, else a refusal message for the model."""
        if tool not in WRITE_TOOLS:
            return None
        call = f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"
        if call in self.ran:
            # Small models sometimes emit the same call twice in one turn; never write twice.
            return ALREADY_DONE.format(tool=tool)
        if tool in self.approved:
            self.approved.discard(tool)  # one call per approval
            self.ran.add(call)
            return None
        self.blocked[tool] = args
        return NEEDS_CONFIRMATION.format(tool=tool)

    def pending_summary(self) -> str:
        if not self.blocked:
            return ""
        calls = "\n".join(
            f"  - {tool}({json.dumps({k: v for k, v in args.items() if k != 'session_id'}, default=str)})"
            for tool, args in self.blocked.items()
        )
        return f"Needs your approval:\n{calls}\nReply `yes` to run it."

