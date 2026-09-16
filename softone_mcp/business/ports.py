"""
Business-layer ports (interfaces).

Business/use-case code should depend on these Protocols instead of importing
SoftOne-specific CRUD helpers or `SoftOneClient` directly.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class ItemLineInput(TypedDict):
    item_id: int
    quantity: int


class ReservationSnapshot(TypedDict):
    item_id: int
    prev_reserved: int


class ReservationToken(TypedDict):
    """
    Opaque-ish token returned by InventoryService.reserve().

    For now this is intentionally simple and serializable; it is only used
    in-process to rollback reservations on failure.
    """

    snapshots: list[ReservationSnapshot]


class ItemSnapshot(TypedDict):
    id: int
    stock: int
    price: float
    reserved: int


@runtime_checkable
class CustomerRepository(Protocol):
    def create(self, *, code: str, name: str, **fields: Any) -> dict[str, Any]: ...

    def get(self, *, key: int, locateinfo: str = "") -> dict[str, Any]: ...

    def update(self, *, key: int, **fields: Any) -> dict[str, Any]: ...

    def delete(self, *, key: int) -> dict[str, Any]: ...

    def resolve_id(self, *, q: str) -> int | None: ...

    def search(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]: ...


@runtime_checkable
class ItemRepository(Protocol):
    def create(self, *, code: str, name: str, **fields: Any) -> dict[str, Any]: ...

    def get(self, *, key: int, locateinfo: str = "") -> dict[str, Any]: ...

    def update(self, *, key: int, **fields: Any) -> dict[str, Any]: ...

    def delete(self, *, key: int) -> dict[str, Any]: ...

    def resolve_id(self, *, q: str) -> int | None: ...

    def get_snapshot(self, *, key: int) -> ItemSnapshot: ...

    def search(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]: ...


@runtime_checkable
class OrderRepository(Protocol):
    def create(self, *, customer_id: int, **fields: Any) -> int: ...

    def get(self, *, order_id: int) -> dict[str, Any]: ...

    def update(self, *, order_id: int, **fields: Any) -> dict[str, Any]: ...

    def delete(self, *, order_id: int) -> dict[str, Any]: ...

    def list(self, *, filter: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class OrderItemsRepository(Protocol):
    def add_line(
        self,
        *,
        order_id: int,
        item_id: int,
        quantity: int,
        unit_price: float,
    ) -> dict[str, Any]: ...

    def get_lines(self, *, order_id: int) -> list[dict[str, Any]]: ...

    def remove_line(self, *, order_id: int, item_id: int) -> dict[str, Any]: ...


@runtime_checkable
class InvoiceRepository(Protocol):
    def create(
        self,
        *,
        customer_id: int,
        amount: float,
        order_id: int | None = None,
        status: str = "",
    ) -> int: ...

    def get(self, *, invoice_id: int) -> dict[str, Any]: ...

    def list(self, *, filter: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class PaymentRepository(Protocol):
    def create(
        self,
        *,
        invoice_id: int,
        amount: float,
        payment_date: str = "",
    ) -> dict[str, Any]: ...

    def get(self, *, payment_id: int) -> dict[str, Any]: ...

    def delete(self, *, payment_id: int) -> dict[str, Any]: ...

    def list_for_invoice(self, *, invoice_id: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class InventoryService(Protocol):
    def reserve(self, *, lines: list[ItemLineInput]) -> ReservationToken: ...

    def rollback(self, *, token: ReservationToken) -> None: ...

    def release(self, *, lines: list[ItemLineInput]) -> None: ...

    def deduct_for_order(self, *, order_id: int) -> None: ...

