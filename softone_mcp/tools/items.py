"""
Agent-facing item tools.

Layer contract:
    - This layer OWNS the `{ok, data}` / `{ok, error}` envelope.
    - Wrap every successful business-layer result with ok(...).
    - Catch SoftOneError and domain exceptions, and return err(...).

Tool inputs are intentionally FLAT (no nested `inp: SomeModel` wrapper):
LLMs generate tool-calls far more reliably against flat JSON schemas than
against nested ones. Validation/descriptions are preserved via
`Annotated[type, Field(...)]`.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from softone_mcp.business.constants import SOFTONE_BAD_INPUT_CODE, SOFTONE_NOT_FOUND_CODE
from softone_mcp.business.exceptions import ItemNotFoundError
from softone_mcp.business.items import (
    create_item_bl,
    delete_item_bl,
    get_item_bl,
    get_stock_balance_bl,
    inventory_adjustment_bl,
    search_items_bl,
    update_item_bl,
)
from softone_mcp.deps import err, ok
from softone_mcp.internal.adapters.repositories import SoftOneItemRepository
from softone_mcp.observability import Trace
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError

from .utils import deterministic_suffix, slug


def register_item_tools(mcp: FastMCP, client: SoftOneClient) -> None:

    @mcp.tool(name="create_item", description="Business action: create an item.")
    def create_item_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name: Annotated[str, Field(description="Item name.")],
        price: Annotated[
            str, Field(description="Price. Leave empty to omit.")
        ] = "",
        stock: Annotated[
            str, Field(description="Stock. Leave empty to omit.")
        ] = "",
    ) -> dict[str, Any]:
        code = f"IT-{slug(name)[:16]}-{deterministic_suffix(name)}"
        items_repo = SoftOneItemRepository(client, session_id)
        try:
            data = create_item_bl(
                items_repo,
                code=code,
                name=name,
                price=price,
                stock=stock,
            )
            return ok(data)
        except ValueError as ve:
            return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(ve), {"name": name}))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="get_item",
        description="Business action: get an item by id or name/code (mock supports name/code lookup).",
    )
    def get_item_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
        locateinfo: Annotated[
            str,
            Field(description="Optional locateinfo projection string (advanced)."),
        ] = "",
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        items_repo = SoftOneItemRepository(client, session_id)

        # 1. Resolve `name_or_id` to a numeric id.
        try:
            key: int = int(q)
        except ValueError:
            try:
                found = items_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        # 2. Delegate to the business layer and envelope the result.
        try:
            data = get_item_bl(
                items_repo,
                key=key,
                locateinfo=locateinfo,
            )
            return ok(data)
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"item_id": e.item_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="update_item",
        description=(
            "Patch an item by id or name/code (mock resolves name/code). "
            "Omit fields (empty string) to leave them unchanged."
        ),
    )
    def update_item_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
        name: Annotated[str, Field(description="New name. Leave empty to skip.")] = "",
        price: Annotated[str, Field(description="New price. Leave empty to skip.")] = "",
        stock: Annotated[str, Field(description="New stock. Leave empty to skip.")] = "",
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        items_repo = SoftOneItemRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = items_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        patch: dict[str, Any] = {}
        if name.strip():
            patch["name"] = name.strip()
        if price.strip():
            patch["price"] = price.strip()
        if stock.strip():
            patch["stock"] = stock.strip()

        try:
            get_item_bl(items_repo, key=key, locateinfo="")
            data = update_item_bl(items_repo, key=key, **patch)
            return ok(data)
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"item_id": e.item_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="delete_item",
        description=(
            "Delete an item by id or name/code (mock resolves name/code). "
            "Fails with referential integrity if the item is referenced on orders."
        ),
    )
    def delete_item_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        items_repo = SoftOneItemRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = items_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        try:
            get_item_bl(items_repo, key=key, locateinfo="")
            data = delete_item_bl(items_repo, key=key)
            return ok(data)
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"item_id": e.item_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="get_stock_balance",
        description=(
            "Get stock balance for an item: stock, reserved, available. "
            "Accepts item id or name/code (mock resolves name/code)."
        ),
    )
    def get_stock_balance_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
    ) -> dict[str, Any]:
        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        items_repo = SoftOneItemRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = items_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        try:
            data = get_stock_balance_bl(items_repo, key=key)
            return ok(data)
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"item_id": e.item_id},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="check_inventory",
        description=(
            "Check inventory for an item: stock, reserved, available. "
            "Accepts item id or name/code (mock resolves name/code)."
        ),
    )
    def check_inventory_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        item_name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
    ) -> dict[str, Any]:
        trace = Trace(
            tool="check_inventory",
            input_redacted={"session_id": "<redacted>", "item_name_or_id": item_name_or_id},
        )

        q = item_name_or_id.strip()
        if not q:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid request. item_name_or_id is required.",
                    {"item_name_or_id": item_name_or_id},
                ),
                meta=trace.meta(),
            )

        items_repo = SoftOneItemRepository(client, session_id)

        with trace.action("resolve_item_id", detail={"q": q}) as ctx:
            try:
                key: int = int(q)
                ctx["resolution"] = "int"
            except ValueError:
                ctx["resolution"] = "lookup"
                found = items_repo.resolve_id(q=q)
                if found is None:
                    return err(
                        SoftOneError(
                            SOFTONE_NOT_FOUND_CODE,
                            "Invalid request, Data does not exist.",
                            {"item_name_or_id": q},
                        ),
                        meta=trace.meta(),
                    )
                key = found
            ctx["item_id"] = key

        with trace.action("get_stock_balance", detail={"item_id": key}):
            try:
                data = get_stock_balance_bl(items_repo, key=key)
                return ok(data, meta=trace.meta())
            except ItemNotFoundError as e:
                return err(
                    SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"item_id": e.item_id}),
                    meta=trace.meta(),
                )
            except SoftOneError as e:
                return err(e, meta=trace.meta())

    @mcp.tool(
        name="inventory_adjustment",
        description=(
            "Adjust stock for an item by delta_qty (integer). "
            "Guarded: cannot make stock negative or below reserved."
        ),
    )
    def inventory_adjustment_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        name_or_id: Annotated[
            str,
            Field(description="Item id or name/code (mock supports name/code lookup)."),
        ],
        delta_qty: Annotated[
            str,
            Field(description="Signed integer delta, e.g. '-2' or '5'."),
        ],
        reason: Annotated[
            str,
            Field(description="Optional reason (informational only in MVP)."),
        ] = "",
    ) -> dict[str, Any]:
        _ = reason  # forward-compatibility for audit trails

        q = name_or_id.strip()
        if not q:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid request. name_or_id is required.",
                {"name_or_id": name_or_id},
            ))

        try:
            parsed_delta = int(delta_qty)
        except ValueError:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                "Invalid delta_qty. Expected an integer.",
                {"delta_qty": delta_qty},
            ))

        items_repo = SoftOneItemRepository(client, session_id)

        try:
            key: int = int(q)
        except ValueError:
            try:
                found = items_repo.resolve_id(q=q)
            except SoftOneError as e:
                return err(e)
            if found is None:
                return err(SoftOneError(
                    SOFTONE_NOT_FOUND_CODE,
                    "Invalid request, Data does not exist.",
                    {"name_or_id": q},
                ))
            key = found

        try:
            data = inventory_adjustment_bl(items_repo, key=key, delta_qty=parsed_delta)
            return ok(data)
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE,
                str(e),
                {"item_id": e.item_id},
            ))
        except ValueError as ve:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(ve),
                {"item_id": key, "delta_qty": parsed_delta},
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="search_items",
        description=(
            "Search items by name/code (mock-only). Returns a list of matches with ids."
        ),
    )
    def search_items_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        q: Annotated[
            str,
            Field(description="Search query (name/code substring)."),
        ],
        limit: Annotated[
            str,
            Field(description="Max rows to return. Leave empty for default."),
        ] = "",
    ) -> dict[str, Any]:
        lim: int | None = None
        if limit.strip():
            try:
                lim = int(limit)
            except ValueError:
                return err(SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid limit. Expected an integer.",
                    {"limit": limit},
                ))

        items_repo = SoftOneItemRepository(client, session_id)
        try:
            data = search_items_bl(items_repo, q=q, limit=lim)
            return ok(data)
        except ValueError as ve:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(ve),
                {"q": q, "limit": lim},
            ))
        except SoftOneError as e:
            return err(e)
