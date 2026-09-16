from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from config import load_config
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError

from softone_mcp.deps import err, ok


class ConnectDefaultOut(BaseModel):
    session_id: str = Field(..., description="Wrapper-managed session_id (maps to a SoftOne clientID internally).")


class GetContextOut(BaseModel):
    session_id: str = Field(..., description="Wrapper-managed session_id.")
    company: str | None = Field(None, description="Selected company (COMPANY).")
    branch: str | None = Field(None, description="Selected branch (BRANCH).")
    module: str | None = Field(None, description="Selected module (MODULE).")
    refid: str | None = Field(None, description="Selected refid (REFID).")


def register_connect_tools(mcp: FastMCP, client: SoftOneClient) -> None:
    @mcp.tool(
        name="softone_connect_default",
        description="Connect using .env (SOFTONE_*) and return a session_id (auto-picks first COMPANY/BRANCH/MODULE/REFID).",
    )
    def softone_connect_default() -> dict[str, Any]:
        cfg = load_config()
        try:
            start = client.start_connection(
                base_url=cfg.base_url,
                username=cfg.username,
                password=cfg.password,
                app_id=cfg.app_id,
            )

            if start.session is not None:
                return ok(ConnectDefaultOut(session_id=start.session.session_id).model_dump())

            if not start.selections or not start.temp_client_id:
                raise SoftOneError(-9, "Invalid start_connection response", {"start": start})

            session = client.complete_connection(
                base_url=cfg.base_url,
                app_id=cfg.app_id,
                temp_client_id=start.temp_client_id,
                selection=start.selections[0],
            )
            return ok(ConnectDefaultOut(session_id=session.session_id).model_dump())
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="get_context",
        description=(
            "Return the session selection context (company/branch/module/refid) "
            "for a given session_id."
        ),
    )
    def get_context_tool(session_id: str) -> dict[str, Any]:
        try:
            data = client.get_session_context(session_id=session_id)
            return ok(GetContextOut(**data).model_dump())
        except SoftOneError as e:
            return err(e)

