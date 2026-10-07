from __future__ import annotations

from softone_mcp.business.ports import InventoryService, ItemLineInput, ReservationToken
from softone_mcp.internal.items import items_get, items_update
from softone_mcp.internal.orderitems import orderitems_get_lines
from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError


class SoftOneInventoryService(InventoryService):
    """
    SoftOne-backed inventory behavior.

    Owns the details of how inventory reservation and deduction are performed
    using ITEM.STOCK and ITEM.RESERVED.
    """

    def __init__(self, client: SoftOneClient, session_id: str) -> None:
        self._client = client
        self._session_id = session_id

    def reserve(self, *, lines: list[ItemLineInput]) -> ReservationToken:
        # Snapshot previous reserved values once per unique item id.
        prev_by_item: dict[int, int] = {}
        running_reserved: dict[int, int] = {}

        for ln in lines:
            item_id = int(ln["item_id"])
            qty = int(ln["quantity"])

            if item_id not in prev_by_item:
                resp = items_get(self._client, self._session_id, item_id, "")
                row = ((resp.get("data") or {}).get("ITEM") or [{}])[0]
                prev_by_item[item_id] = int(row.get("RESERVED") or 0)

            current_reserved = running_reserved.get(item_id, prev_by_item[item_id])
            new_reserved = current_reserved + qty

            items_update(
                self._client,
                self._session_id,
                item_id,
                reserved=new_reserved,
            )
            running_reserved[item_id] = new_reserved

        return {
            "snapshots": [
                {"item_id": item_id, "prev_reserved": prev}
                for item_id, prev in prev_by_item.items()
            ]
        }

    def rollback(self, *, token: ReservationToken) -> None:
        # Best-effort: never mask original errors.
        for snap in token.get("snapshots", []):
            try:
                items_update(
                    self._client,
                    self._session_id,
                    int(snap["item_id"]),
                    reserved=max(0, int(snap["prev_reserved"])),
                )
            except SoftOneError:
                continue

    def release(self, *, lines: list[ItemLineInput]) -> None:
        """Release (decrease) reservations for the given items.

        Used when removing lines from Draft orders (draft-only edits).
        Best-effort: never raise in a way that masks the caller's primary error.
        """
        for ln in lines:
            item_id = int(ln["item_id"])
            qty = int(ln["quantity"])
            if qty <= 0:
                continue
            try:
                resp = items_get(self._client, self._session_id, item_id, "")
                row = ((resp.get("data") or {}).get("ITEM") or [{}])[0]
                current_reserved = int(row.get("RESERVED") or 0)
                items_update(
                    self._client,
                    self._session_id,
                    item_id,
                    reserved=max(0, current_reserved - qty),
                )
            except SoftOneError:
                continue

    def deduct_for_order(self, *, order_id: int) -> None:
        """
        Deduct stock and release reservations for all lines in the order.

        Mirrors the previous behavior in `business/invoices.py::_deduct_stock`.
        """
        lines = orderitems_get_lines(self._client, self._session_id, order_id)

        for line in lines:
            item_id = int(line.get("item_id") or 0)
            qty = int(line.get("quantity") or 0)
            if not item_id or qty <= 0:
                continue

            try:
                resp = items_get(self._client, self._session_id, item_id, "")
            except SoftOneError:
                continue

            row = ((resp.get("data") or {}).get("ITEM") or [{}])[0]
            current_stock = int(row.get("STOCK") or 0)
            current_reserved = int(row.get("RESERVED") or 0)

            items_update(
                self._client,
                self._session_id,
                item_id,
                stock=max(0, current_stock - qty),
                reserved=max(0, current_reserved - qty),
            )

