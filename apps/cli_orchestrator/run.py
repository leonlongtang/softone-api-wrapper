from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import load_dotenv  # noqa: E402

from agent_core.orchestration.policy import RuntimePolicy
from agent_platform.orchestrator.graph import build_orchestrator
from agent_platform.orchestrator.state import OrchestratorState
from agent_platform.settings import configure_logging, load_agent_platform_settings


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Department Orchestrator CLI (Sales/Inventory/Finance).")
    p.add_argument("prompt", nargs="?", default="", help="Optional single-turn prompt. If omitted, run REPL.")
    p.add_argument("--debug", action="store_true", help="Enable MCP tool I/O tracing (Ollama runtime).")
    return p


def _ollama_only_policy() -> RuntimePolicy:
    # Never route to Claude.
    return RuntimePolicy(default_runtime="ollama", escalation_runtime="ollama", max_ollama_failures_before_escalate=10**9)


async def _run_repl(*, initial: str, debug: bool) -> None:
    print("Starting CLI orchestrator…", flush=True)
    # Import heavy runtime deps lazily so we can always show startup text
    # (and make it easier to pinpoint import-time hangs).
    print("Importing runtimes…", flush=True)
    from agent_platform.runtime.ollama_runtime import OllamaRuntime  # noqa: WPS433
    from agent_platform.runtime.claude_sdk_runtime import ClaudeSdkRuntime  # noqa: WPS433

    print("Initializing runtimes…", flush=True)
    async with OllamaRuntime(debug=debug) as ollama, ClaudeSdkRuntime() as claude:
        app = build_orchestrator(ollama=ollama, claude=claude, policy=_ollama_only_policy())
        state: OrchestratorState = {"failures": 0, "artifacts": {}}

        if initial.strip():
            state["user_text"] = initial.strip()
            state = await app.ainvoke(state)  # type: ignore[attr-defined]
            print(state.get("response") or "")
            return

        print("Workflow Orchestrator (V1). Type /exit to quit.", flush=True)
        while True:
            try:
                user_text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not user_text:
                continue
            if user_text.lower() in {"/exit", "/quit", "exit", "quit"}:
                return

            state["user_text"] = user_text
            state = await app.ainvoke(state)  # type: ignore[attr-defined]
            print(f"\nAgent[{state.get('route')}|{state.get('runtime')}]: {state.get('response') or ''}")


async def main() -> None:
    load_dotenv()
    args = _build_argparser().parse_args()
    settings = load_agent_platform_settings(cli_debug=bool(args.debug))
    configure_logging(debug=settings.debug)
    await _run_repl(initial=args.prompt, debug=settings.debug)


if __name__ == "__main__":
    asyncio.run(main())

