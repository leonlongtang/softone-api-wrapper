"""SoftOne MCP agent (Claude runtime), powered by the shared agent platform.

Run from the repo root:
    python -m agent.agent                 # interactive chat (Claude)
    python -m agent.agent --demo          # run the demo workflow (Claude)
    python -m agent.agent "Your prompt"   # single-turn run (Claude)

The implementation lives in `agent_platform/` so both Claude and Ollama
entrypoints share the same agent definitions and prompt policy.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

# Reuse the project's minimal .env loader (defined in config.py at repo root).
from config import load_dotenv

from agent_platform.runtime.claude_sdk_runtime import ClaudeSdkRuntime
from agent_platform.specs import sales_agent_spec

REPO_ROOT = Path(__file__).resolve().parent.parent


DEMO_PROMPT = """
You are an operations agent for a SoftOne-backed ERP, connected via MCP.

Rules:
- Start every session by calling `mcp__softone__softone_connect_default` to
  get a session_id. Reuse that session_id in every subsequent tool call.
- Every tool returns `{ "ok": true, "data": ... }` on success or
  `{ "ok": false, "error": { code, message, details } }` on failure.
  If `ok` is false, DO NOT retry blindly — explain the error and stop.
- Prefer numeric IDs when you already have them (avoid name lookups).

Task — a full order-to-cash run against the seeded mock DB:
1. Connect and obtain a session_id.
2. Fetch customer TRDR=47 to confirm it exists.
3. Create an order for customer 47 with 1x item 1001 and 2x item 1002.
4. If the returned order status is "Draft", call approve_order to move it
   to "Confirmed". If it's already "Confirmed", skip that step.
5. Create an invoice from that order with payment_terms="net_30".
6. Record a single payment whose amount equals the invoice total.
7. Fetch the invoice again and confirm its status is "paid".

Return a short bullet summary with the order_id, invoice_id, invoice amount,
final invoice status, and payment_id.
""".strip()


async def _run_one_turn(runtime: ClaudeSdkRuntime, prompt: str) -> None:
    from agent_platform.runtime.base import RunContext

    spec = sales_agent_spec()
    text = await runtime.run_turn(spec=spec, user_text=prompt, context=RunContext())
    print(text)


def _print_chat_help() -> None:
    print(
        "\nCommands:\n"
        "  /help           show this help\n"
        "  /demo           run the built-in end-to-end demo\n"
        "  /model <name>   switch model for this chat\n"
        "  /exit           quit\n"
        "\nTips:\n"
        "  - You can paste multi-line text; finish with an empty line.\n"
    )


def _read_multiline_input(prompt: str = "> ") -> str:
    """Read one message; supports multi-line paste (end with blank line)."""
    try:
        first = input(prompt)
    except EOFError:
        return "/exit"

    lines = [first]
    while True:
        try:
            nxt = input()
        except EOFError:
            break
        if nxt == "":
            break
        lines.append(nxt)
    return "\n".join(lines).strip()


async def main() -> None:
    load_dotenv()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to .env (at the repo root) or export it before running."
        )

    async with ClaudeSdkRuntime(repo_root=REPO_ROOT) as runtime:
        # Single-turn mode (explicit prompt argument).
        import sys

        if len(sys.argv) > 1 and sys.argv[1] not in {"--demo", "/demo"}:
            await _run_one_turn(runtime, sys.argv[1])
            print()
            return

        # Demo mode.
        if len(sys.argv) > 1 and sys.argv[1] in {"--demo", "/demo"}:
            await _run_one_turn(runtime, DEMO_PROMPT)
            print()
            return

        # Interactive chat mode.
        print("SoftOne MCP Agent (interactive). Type /help for commands.")
        _print_chat_help()
        while True:
            user_text = _read_multiline_input("> ")
            if not user_text:
                continue

            cmd = user_text.strip()
            if cmd.startswith("/model"):
                parts = cmd.split(maxsplit=1)
                if len(parts) == 1 or not parts[1].strip():
                    print("Usage: /model <model-id-or-alias>  (e.g. claude-sonnet-4-5 or sonnet)")
                    continue
                new_model = parts[1].strip()
                await runtime.set_model(new_model)
                print(f"Model set to: {new_model}")
                continue
            if cmd in {"/exit", "exit", "quit"}:
                print("Bye.")
                return
            if cmd in {"/help", "help"}:
                _print_chat_help()
                continue
            if cmd in {"/demo"}:
                await _run_one_turn(runtime, DEMO_PROMPT)
                print()
                continue

            await _run_one_turn(runtime, user_text)
            print()

    print()


if __name__ == "__main__":
    asyncio.run(main())
