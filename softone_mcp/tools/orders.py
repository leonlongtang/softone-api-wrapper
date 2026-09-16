"""
Agent-facing order tools.

Layer contract:
    - This layer OWNS the `{ok, data}` / `{ok, error}` envelope.
    - Wrap every successful business-layer result with ok(...).
    - Catch SoftOneError and domain exceptions, and return err(...).

Tool inputs are intentionally FLAT (no nested `inp: SomeModel` wrapper):
LLMs generate tool-calls far more reliably against flat JSON schemas than
against nested ones. `OrderLineInput` is kept only as the element type for
the `items` array — each line still has just `item_id` and `quantity`.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from softone_mcp.business.constants import SOFTONE_BAD_INPUT_CODE, SOFTONE_NOT_FOUND_CODE
from softone_mcp.business.orders import (
    add_order_line_bl,
    approve_order_bl,
    cancel_order_bl,
    create_order_bl,
    get_order_bl,
    get_order_lines_bl,
    list_orders_bl,
    remove_order_line_bl,
    update_order_notes_bl,
)
from softone_mcp.business.customers import search_customers_bl
from softone_mcp.business.exceptions import (
    CustomerNotFoundError,
    InsufficientStockError,
    InvalidOrderStatusError,
    ItemNotFoundError,
    OrderNotFoundError,
)
from softone_mcp.deps import err, ok
from softone_mcp.internal.adapters.inventory import SoftOneInventoryService
from softone_mcp.internal.adapters.repositories import (
    SoftOneCustomerRepository,
    SoftOneItemRepository,
    SoftOneOrderItemsRepository,
    SoftOneOrderRepository,
)
from softone_mcp.observability import Trace
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError


# ---------------------------------------------------------------------------
# Order line element (kept as a BaseModel so the JSON schema for each array
# entry is precise — not a nested wrapper around the whole tool input).
# ---------------------------------------------------------------------------

class OrderLineInput(BaseModel):
    item_id: int = Field(..., description="ID of the item to order")
    quantity: int = Field(..., gt=0, description="Quantity (must be > 0)")


class WorkflowOrderLineInput(BaseModel):
    item_name_or_id: str = Field(..., description="Item id or name/code")
    quantity: int = Field(..., gt=0, description="Quantity (must be > 0)")


# ---------------------------------------------------------------------------
# MCP tool registrations
# ---------------------------------------------------------------------------

def register_order_tools(mcp: FastMCP, client: SoftOneClient) -> None:

    @mcp.tool(name="create_order", description=(
        "Create a new sales order for a customer. "
        "Validates customer and stock, reserves inventory, calculates total. "
        "Returns order with status 'Draft' or 'Confirmed' (auto-approved if total < threshold)."
    ))
    def create_order_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        customer_id: Annotated[
            int, Field(description="ID of the customer placing the order")
        ],
        items: Annotated[
            list[OrderLineInput],
            Field(description="List of items and quantities"),
        ],
        notes: Annotated[
            str, Field(description="Optional order notes")
        ] = "",
    ) -> dict[str, Any]:
        customers_repo = SoftOneCustomerRepository(client, session_id)
        items_repo = SoftOneItemRepository(client, session_id)
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)
        try:
            data = create_order_bl(
                customers_repo,
                items_repo,
                orders_repo,
                orderitems_repo,
                inventory,
                customer_id=customer_id,
                items=[line.model_dump() for line in items],
                notes=notes,
            )
            return ok(data)
        except CustomerNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"customer_id": e.customer_id}
            ))
        except ItemNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"item_id": e.item_id}
            ))
        except InsufficientStockError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "item_id": e.item_id,
                    "requested": e.requested,
                    "available": e.available,
                },
            ))
        except ValueError as e:
            return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(e), {}))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="workflow_create_order",
        description=(
            "Deterministic workflow: resolve customer/items, validate stock, "
            "reserve inventory, create order, and (optionally) auto-approve based on policy. "
            "This is the preferred tool for 'place an order' intents."
        ),
    )
    def workflow_create_order_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        customer: Annotated[
            str,
            Field(description="Customer id or name/code (mock supports name/code lookup)."),
        ],
        items: Annotated[
            list[WorkflowOrderLineInput],
            Field(description="List of items and quantities (item id or name/code)."),
        ],
        notes: Annotated[str, Field(description="Optional order notes")] = "",
        auto_approve: Annotated[
            str,
            Field(description="Auto-approve policy: never | if_under_threshold | always."),
        ] = "if_under_threshold",
    ) -> dict[str, Any]:
        trace = Trace(
            tool="workflow_create_order",
            input_redacted={
                "session_id": "<redacted>",
                "customer": customer,
                "items": [ln.model_dump() for ln in items],
                "notes": notes,
                "auto_approve": auto_approve,
            },
        )

        customers_repo = SoftOneCustomerRepository(client, session_id)
        items_repo = SoftOneItemRepository(client, session_id)
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)

        # 1) Resolve customer
        cust_q = customer.strip()
        if not cust_q:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid request. customer is required.",
                    {"customer": customer},
                ),
                meta=trace.meta(),
            )

        with trace.action("resolve_customer_id", detail={"q": cust_q}) as ctx:
            try:
                customer_id = int(cust_q)
                ctx["resolution"] = "int"
            except ValueError:
                ctx["resolution"] = "lookup"
                found = customers_repo.resolve_id(q=cust_q)
                if found is None:
                    return err(
                        SoftOneError(
                            SOFTONE_NOT_FOUND_CODE,
                            "Invalid request, Data does not exist.",
                            {"customer": cust_q},
                        ),
                        meta=trace.meta(),
                    )
                customer_id = found
            ctx["customer_id"] = customer_id

        # 2) Resolve items (deterministically, left-to-right)
        resolved_lines: list[dict[str, Any]] = []
        with trace.action("resolve_item_ids", detail={"lines": len(items)}):
            for ln in items:
                q = (ln.item_name_or_id or "").strip()
                if not q:
                    return err(
                        SoftOneError(
                            SOFTONE_BAD_INPUT_CODE,
                            "Invalid request. item_name_or_id is required for every line.",
                            {"line": ln.model_dump()},
                        ),
                        meta=trace.meta(),
                    )
                try:
                    item_id = int(q)
                except ValueError:
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
                    item_id = found

                resolved_lines.append({"item_id": int(item_id), "quantity": int(ln.quantity)})

        # 3) Run the business workflow (single deterministic entrypoint)
        with trace.action("create_order", detail={"customer_id": customer_id, "lines": len(resolved_lines)}):
            try:
                data = create_order_bl(
                    customers_repo,
                    items_repo,
                    orders_repo,
                    orderitems_repo,
                    inventory,
                    customer_id=int(customer_id),
                    items=resolved_lines,
                    notes=notes,
                    auto_approve_policy=auto_approve,
                )
                return ok(data, meta=trace.meta())
            except CustomerNotFoundError as e:
                return err(
                    SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"customer_id": e.customer_id}),
                    meta=trace.meta(),
                )
            except ItemNotFoundError as e:
                return err(
                    SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"item_id": e.item_id}),
                    meta=trace.meta(),
                )
            except InsufficientStockError as e:
                return err(
                    SoftOneError(
                        SOFTONE_BAD_INPUT_CODE,
                        str(e),
                        {"item_id": e.item_id, "requested": e.requested, "available": e.available},
                    ),
                    meta=trace.meta(),
                )
            except ValueError as e:
                return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(e), {}), meta=trace.meta())
            except SoftOneError as e:
                return err(e, meta=trace.meta())

    @mcp.tool(name="approve_order", description=(
        "Approve a Draft order, moving it to Confirmed status. "
        "Once confirmed, an invoice can be generated. "
        "Raises an error if the order is not in Draft status."
    ))
    def approve_order_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        order_id: Annotated[
            int, Field(description="ID of the Draft order to approve")
        ],
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        try:
            data = approve_order_bl(orders_repo, order_id=order_id)
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}
            ))
        except InvalidOrderStatusError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "order_id": e.order_id,
                    "current_status": e.current,
                    "expected_status": e.expected,
                },
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(name="get_order", description="Fetch a sales order by ID.")
    def get_order_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        order_id: Annotated[
            int, Field(description="ID of the order to fetch")
        ],
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        try:
            data = get_order_bl(orders_repo, order_id=order_id)
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="get_order_lines",
        description=(
            "Fetch line items for a sales order by order_id. "
            "Each line includes item_id, quantity, and unit_price."
        ),
    )
    def get_order_lines_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        order_id: Annotated[
            int, Field(description="ID of the order whose lines to fetch")
        ],
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        try:
            data = get_order_lines_bl(orders_repo, orderitems_repo, order_id=order_id)
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="list_orders",
        description=(
            "List orders (mock-only). Optional filters: customer_id, status. "
            "Use this for visibility/debugging and to discover existing orders."
        ),
    )
    def list_orders_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        customer_id: Annotated[
            str,
            Field(description="Filter by customer ID. Leave empty for all customers."),
        ] = "",
        status: Annotated[
            str,
            Field(description="Filter by status (e.g. 'Draft', 'Confirmed'). Leave empty for all."),
        ] = "",
        limit: Annotated[
            str,
            Field(description="Max rows to return. Leave empty for default."),
        ] = "",
    ) -> dict[str, Any]:
        cust: int | None = None
        if customer_id.strip():
            try:
                cust = int(customer_id)
            except ValueError:
                return err(SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    "Invalid customer_id. Expected an integer.",
                    {"customer_id": customer_id},
                ))

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

        orders_repo = SoftOneOrderRepository(client, session_id)
        try:
            data = list_orders_bl(
                orders_repo,
                customer_id=cust,
                status=status,
                limit=lim,
            )
            return ok(data)
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="cancel_order",
        description=(
            "Cancel a Draft order. MVP semantics: cancellation deletes the order. "
            "Confirmed orders cannot be cancelled in this MVP."
        ),
    )
    def cancel_order_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        order_id: Annotated[
            int,
            Field(description="ID of the Draft order to cancel."),
        ],
        reason: Annotated[
            str,
            Field(description="Optional cancellation reason (informational only in MVP)."),
        ] = "",
    ) -> dict[str, Any]:
        _ = reason  # kept for forward-compatibility (audit trails) without changing behavior yet.
        orders_repo = SoftOneOrderRepository(client, session_id)
        try:
            data = cancel_order_bl(orders_repo, order_id=order_id)
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(
                SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}
            ))
        except InvalidOrderStatusError as e:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(e),
                {
                    "order_id": e.order_id,
                    "current_status": e.current,
                    "expected_status": e.expected,
                },
            ))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="update_order",
        description=(
            "Update a Draft order header (Draft-only). "
            "Use this for notes or other small header changes. "
            "Raises an error if the order is not Draft."
        ),
    )
    def update_order_tool(
        session_id: Annotated[str, Field(description="Session obtained from softone_connect_default().")],
        order_id: Annotated[int, Field(description="ID of the Draft order to update")],
        notes: Annotated[str, Field(description="New notes (replaces existing notes).")] = "",
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        try:
            data = update_order_notes_bl(orders_repo, order_id=order_id, notes=notes)
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}))
        except InvalidOrderStatusError as e:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    str(e),
                    {"order_id": e.order_id, "current_status": e.current, "expected_status": e.expected},
                )
            )
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="add_order_line",
        description=(
            "Add (or merge) a line onto a Draft order (Draft-only). "
            "Reserves inventory for the added quantity and updates order total."
        ),
    )
    def add_order_line_tool(
        session_id: Annotated[str, Field(description="Session obtained from softone_connect_default().")],
        order_id: Annotated[int, Field(description="ID of the Draft order to modify")],
        item_id: Annotated[int, Field(description="Item ID to add")],
        quantity: Annotated[int, Field(gt=0, description="Quantity to add (must be > 0)")],
    ) -> dict[str, Any]:
        customers_repo = SoftOneCustomerRepository(client, session_id)
        items_repo = SoftOneItemRepository(client, session_id)
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)
        try:
            data = add_order_line_bl(
                customers_repo,
                items_repo,
                orders_repo,
                orderitems_repo,
                inventory,
                order_id=order_id,
                item_id=item_id,
                quantity=quantity,
            )
            return ok(data)
        except (CustomerNotFoundError, OrderNotFoundError) as e:
            code = getattr(e, "order_id", None) or getattr(e, "customer_id", None)
            return err(SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"id": code}))
        except ItemNotFoundError as e:
            return err(SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"item_id": e.item_id}))
        except InsufficientStockError as e:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    str(e),
                    {"item_id": e.item_id, "requested": e.requested, "available": e.available},
                )
            )
        except InvalidOrderStatusError as e:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    str(e),
                    {"order_id": e.order_id, "current_status": e.current, "expected_status": e.expected},
                )
            )
        except ValueError as ve:
            return err(SoftOneError(SOFTONE_BAD_INPUT_CODE, str(ve), {}))
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="remove_order_line",
        description=(
            "Remove all lines for an item from a Draft order (Draft-only). "
            "Releases the reserved quantity for that item and updates order total."
        ),
    )
    def remove_order_line_tool(
        session_id: Annotated[str, Field(description="Session obtained from softone_connect_default().")],
        order_id: Annotated[int, Field(description="ID of the Draft order to modify")],
        item_id: Annotated[int, Field(description="Item ID to remove from the order")],
    ) -> dict[str, Any]:
        orders_repo = SoftOneOrderRepository(client, session_id)
        orderitems_repo = SoftOneOrderItemsRepository(client, session_id)
        inventory = SoftOneInventoryService(client, session_id)
        try:
            data = remove_order_line_bl(
                orders_repo,
                orderitems_repo,
                inventory,
                order_id=order_id,
                item_id=item_id,
            )
            return ok(data)
        except OrderNotFoundError as e:
            return err(SoftOneError(SOFTONE_NOT_FOUND_CODE, str(e), {"order_id": e.order_id}))
        except InvalidOrderStatusError as e:
            return err(
                SoftOneError(
                    SOFTONE_BAD_INPUT_CODE,
                    str(e),
                    {"order_id": e.order_id, "current_status": e.current, "expected_status": e.expected},
                )
            )
        except SoftOneError as e:
            return err(e)

    @mcp.tool(
        name="search_customers",
        description=(
            "Search customers by name/code/AFM (mock-only). "
            "Returns a list of matches with ids you can use in create_order."
        ),
    )
    def search_customers_tool(
        session_id: Annotated[
            str,
            Field(description="Session obtained from softone_connect_default()."),
        ],
        q: Annotated[
            str,
            Field(description="Search query (name/code/AFM substring)."),
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

        customers_repo = SoftOneCustomerRepository(client, session_id)
        try:
            data = search_customers_bl(customers_repo, q=q, limit=lim)
            return ok(data)
        except ValueError as ve:
            return err(SoftOneError(
                SOFTONE_BAD_INPUT_CODE,
                str(ve),
                {"q": q, "limit": lim},
            ))
        except SoftOneError as e:
            return err(e)
