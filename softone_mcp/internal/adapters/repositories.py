from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient

from softone_mcp.business.ports import (
    CustomerRepository,
    InvoiceRepository,
    ItemRepository,
    ItemSnapshot,
    OrderItemsRepository,
    OrderRepository,
    PaymentRepository,
)
from softone_mcp.internal.customers import (
    customers_create,
    customers_delete,
    customers_get,
    customers_search,
    customers_update,
)
from softone_mcp.internal.invoices import invoices_create, invoices_get
from softone_mcp.internal.items import items_create, items_delete, items_get, items_update
from softone_mcp.internal.items import items_search
from softone_mcp.internal.orderitems import orderitems_add_line, orderitems_get_lines
from softone_mcp.internal.orderitems import orderitems_remove_line
from softone_mcp.internal.orders import (
    orders_create,
    orders_delete,
    orders_get_normalized,
    orders_list,
    orders_update,
)
from softone_mcp.internal.payments import (
    payments_create,
    payments_delete,
    payments_get,
    payments_list_for_invoice,
)


class SoftOneCustomerRepository(CustomerRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def create(self, *, code: str, name: str, **fields: Any) -> dict[str, Any]:
        return customers_create(self._client, self._session_id, code, name, **fields)

    def get(self, *, key: int, locateinfo: str = "") -> dict[str, Any]:
        return customers_get(self._client, self._session_id, key, locateinfo)

    def update(self, *, key: int, **fields: Any) -> dict[str, Any]:
        return customers_update(self._client, self._session_id, key, **fields)

    def delete(self, *, key: int) -> dict[str, Any]:
        return customers_delete(self._client, self._session_id, key)

    def resolve_id(self, *, q: str) -> int | None:
        return self._client.resolve_customer_id(session_id=self._session_id, q=q)

    def search(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]:
        return customers_search(self._client, self._session_id, q=q, limit=limit)


class SoftOneItemRepository(ItemRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def create(self, *, code: str, name: str, **fields: Any) -> dict[str, Any]:
        return items_create(self._client, self._session_id, code, name, **fields)

    def get(self, *, key: int, locateinfo: str = "") -> dict[str, Any]:
        return items_get(self._client, self._session_id, key, locateinfo)

    def update(self, *, key: int, **fields: Any) -> dict[str, Any]:
        return items_update(self._client, self._session_id, key, **fields)

    def delete(self, *, key: int) -> dict[str, Any]:
        return items_delete(self._client, self._session_id, key)

    def resolve_id(self, *, q: str) -> int | None:
        return self._client.resolve_item_id(session_id=self._session_id, q=q)

    def get_snapshot(self, *, key: int) -> ItemSnapshot:
        resp = items_get(self._client, self._session_id, key, "")
        row = ((resp.get("data") or {}).get("ITEM") or [{}])[0]
        return {
            "id": int(row.get("ID") or 0),
            "stock": int(row.get("STOCK") or 0),
            "price": float(row.get("PRICE") or 0.0),
            "reserved": int(row.get("RESERVED") or 0),
        }

    def search(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]:
        return items_search(self._client, self._session_id, q=q, limit=limit)


class SoftOneOrderRepository(OrderRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def create(self, *, customer_id: int, **fields: Any) -> int:
        resp = orders_create(self._client, self._session_id, customer_id=customer_id, **fields)
        order_id_raw = resp.get("id")
        if not order_id_raw:
            raise RuntimeError("SoftOne did not return an order ID after creation")
        return int(order_id_raw)

    def get(self, *, order_id: int) -> dict[str, Any]:
        return orders_get_normalized(self._client, self._session_id, order_id)

    def update(self, *, order_id: int, **fields: Any) -> dict[str, Any]:
        return orders_update(self._client, self._session_id, order_id, **fields)

    def delete(self, *, order_id: int) -> dict[str, Any]:
        return orders_delete(self._client, self._session_id, order_id)

    def list(self, *, filter: dict[str, Any]) -> dict[str, Any]:
        return orders_list(self._client, self._session_id, filter=filter)


class SoftOneOrderItemsRepository(OrderItemsRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def add_line(
        self,
        *,
        order_id: int,
        item_id: int,
        quantity: int,
        unit_price: float,
    ) -> dict[str, Any]:
        return orderitems_add_line(
            self._client,
            self._session_id,
            order_id=order_id,
            item_id=item_id,
            quantity=quantity,
            unit_price=unit_price,
        )

    def get_lines(self, *, order_id: int) -> list[dict[str, Any]]:
        return orderitems_get_lines(self._client, self._session_id, order_id)

    def remove_line(self, *, order_id: int, item_id: int) -> dict[str, Any]:
        return orderitems_remove_line(self._client, self._session_id, order_id, product_id=int(item_id))


class SoftOneInvoiceRepository(InvoiceRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def create(
        self,
        *,
        customer_id: int,
        amount: float,
        order_id: int | None = None,
        status: str = "",
    ) -> int:
        resp = invoices_create(
            self._client,
            self._session_id,
            customer_id=customer_id,
            amount=amount,
            order_id=order_id,
            status=status,
        )
        invoice_id_raw = resp.get("id")
        if not invoice_id_raw:
            raise RuntimeError("SoftOne did not return an invoice ID after creation")
        return int(invoice_id_raw)

    def get(self, *, invoice_id: int) -> dict[str, Any]:
        return invoices_get(self._client, self._session_id, key=invoice_id)

    def list(self, *, filter: dict[str, Any]) -> dict[str, Any]:
        return invoices_get(self._client, self._session_id, filter=filter)


class SoftOnePaymentRepository(PaymentRepository):
    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def create(
        self,
        *,
        invoice_id: int,
        amount: float,
        payment_date: str = "",
    ) -> dict[str, Any]:
        return payments_create(
            self._client,
            self._session_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_date=payment_date,
        )

    def get(self, *, payment_id: int) -> dict[str, Any]:
        return payments_get(self._client, self._session_id, payment_id)

    def delete(self, *, payment_id: int) -> dict[str, Any]:
        return payments_delete(self._client, self._session_id, payment_id)

    def list_for_invoice(self, *, invoice_id: int) -> list[dict[str, Any]]:
        return payments_list_for_invoice(self._client, self._session_id, invoice_id)

