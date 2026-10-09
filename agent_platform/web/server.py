"""HTTP API for the web UI: one chat at a time, driven exactly like the CLI loop."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from agent_platform.gate import WRITE_TOOLS
from agent_platform.graph import GATE_KEY, escalation_enabled, open_orchestrator
from agent_platform.specs import SPECS
from agent_platform.web import db
from config import load_config

INDEX = Path(__file__).resolve().parent / "index.html"
logger = logging.getLogger(__name__)


async def _tool_catalog() -> dict[str, list[dict[str, Any]]]:
    from softone_mcp.server import mcp

    summary = {
        t.name: (t.description or "").removeprefix("Business action: ").split(". ")[0].strip().rstrip(".")
        for t in await mcp.list_tools()
    }
    return {
        dept: [{"name": n, "write": n in WRITE_TOOLS, "description": summary.get(n, "")} for n in spec.tool_names]
        for dept, spec in SPECS.items()
    }


def create_app(*, open_chat: Callable[..., Any] = open_orchestrator, db_path: Path = db.DEFAULT_DB_PATH) -> Starlette:
    """`open_chat(runtime)` is an async context manager yielding an orchestrator (tests pass a fake)."""
    mock = load_config().mock
    lock = asyncio.Lock()  # one turn / chat change at a time
    chat: dict[str, Any] = {"stack": None, "app": None, "state": None, "runtime": "ollama"}

    async def close_chat() -> None:
        if chat["stack"]:
            await chat["stack"].aclose()
        chat.update(stack=None, app=None, state=None)

    async def start_chat(runtime: str) -> None:
        await close_chat()
        chat["runtime"] = runtime
        stack = AsyncExitStack()
        try:
            chat["app"] = await stack.enter_async_context(open_chat(runtime))
        except BaseException:
            await stack.aclose()
            raise
        chat.update(stack=stack, state={"artifacts": {}})

    def info() -> dict[str, Any]:
        return {"runtime": chat["runtime"], "ready": chat["app"] is not None, "escalation": escalation_enabled()}

    async def index(_: Request) -> FileResponse:
        return FileResponse(INDEX)

    async def get_info(_: Request) -> JSONResponse:
        return JSONResponse({**info(), "mock": mock, "tools": await _tool_catalog()})

    async def new_chat(request: Request) -> JSONResponse:
        runtime = (await request.json()).get("runtime", "ollama")
        if runtime not in ("ollama", "claude"):
            return JSONResponse({"error": f"unknown runtime {runtime!r}"}, status_code=400)
        async with lock:
            try:
                await start_chat(runtime)
            except Exception as exc:  # noqa: BLE001 - e.g. Ollama not running: show it, keep serving
                return JSONResponse({**info(), "error": f"{type(exc).__name__}: {exc}"}, status_code=503)
        return JSONResponse(info())

    async def turn(request: Request) -> JSONResponse:
        text = str((await request.json()).get("text", "")).strip()
        if not text:
            return JSONResponse({"error": "empty message"}, status_code=400)
        async with lock:
            if chat["app"] is None:
                try:
                    await start_chat(chat["runtime"])
                except Exception as exc:  # noqa: BLE001
                    return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=503)
            before = db.snapshot(db_path) if mock else None
            out: dict[str, Any] = {}
            try:
                chat["state"] = await chat["app"].ainvoke({**chat["state"], "user_text": text})
                out.update(route=chat["state"].get("route"), runtime=chat["state"].get("runtime"))
                out["response"] = chat["state"].get("response") or ""
            except Exception as exc:  # noqa: BLE001 - a failed turn shouldn't end the chat
                logger.debug("turn failed", exc_info=True)
                out["error"] = f"{type(exc).__name__}: {exc}"
            # The gate lives in the artifacts dict, which the graph mutates in place, so it's current even on error.
            gate = chat["state"]["artifacts"].get(GATE_KEY)
            out["trace"] = gate.trace if gate else []
            out["pending"] = bool(gate and gate.blocked)
            # The page shows blocked calls as an approval card; drop the CLI's text version of them.
            summary = gate.pending_summary() if gate else ""
            if summary and out.get("response", "").endswith(summary):
                out["response"] = out["response"][: -len(summary)].rstrip()
            out["diff"] = db.diff(before, db.snapshot(db_path)) if mock else None
        return JSONResponse(out)

    async def tables(_: Request) -> JSONResponse:
        if not mock:
            return JSONResponse({"error": "database view needs the mock backend"}, status_code=404)
        snap = db.snapshot(db_path)
        return JSONResponse({t: list(rows.values()) for t, rows in snap.items()})

    async def reset(_: Request) -> JSONResponse:
        if not mock:
            return JSONResponse({"error": "reset needs the mock backend"}, status_code=404)
        async with lock:
            await close_chat()  # stop the MCP servers before replacing their database file
            from mock_db.create_and_seed import build_db

            build_db(db_path)
        return JSONResponse(info())

    @asynccontextmanager
    async def lifespan(_: Starlette):
        yield
        await close_chat()

    return Starlette(
        routes=[
            Route("/", index),
            Route("/api/info", get_info),
            Route("/api/chat", new_chat, methods=["POST"]),
            Route("/api/turn", turn, methods=["POST"]),
            Route("/api/db", tables),
            Route("/api/reset", reset, methods=["POST"]),
        ],
        lifespan=lifespan,
    )
