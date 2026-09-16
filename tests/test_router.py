"""Router & dispatch: services discoverable by name, unknown ones rejected,
session enforcement on authenticated services.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mock_db.mock_ws import WsError, handle_request


class TestServiceDispatch:
    def test_unknown_service_returns_invalid_call(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            handle_request(
                {"service": "doTheNeedful", "clientID": final_session},
                db_path=db_path,
            )
        assert exc_info.value.code == -12

    def test_get_objects_lists_seeded_business_objects(
        self, final_session: str, db_path: Path
    ) -> None:
        resp = handle_request(
            {"service": "getObjects", "clientID": final_session},
            db_path=db_path,
        )
        assert resp["success"] is True
        names = {o["name"] for o in resp["objects"]}
        assert {"CUSTOMER", "ITEM", "ORDER"} <= names

    def test_sql_data_returns_seeded_rows(
        self, final_session: str, db_path: Path
    ) -> None:
        resp = handle_request(
            {"service": "SqlData", "clientID": final_session, "SqlName": "myItems"},
            db_path=db_path,
        )
        assert resp["success"] is True
        assert resp["totalcount"] >= 1
        # Every row should expose the documented field set.
        first = resp["rows"][0]
        assert {"MTRL", "CODE", "NAME", "PRICEW", "PRICER"} == first.keys()

    def test_einvoice_lookup_happy_path(
        self, final_session: str, db_path: Path
    ) -> None:
        # Seeded eInvoice record uses doc_key="47", template="102".
        resp = handle_request(
            {"service": "eInvoice", "clientID": final_session,
             "key": "47", "template": "102"},
            db_path=db_path,
        )
        assert resp["success"] is True
        assert {"integritySignature", "signature", "uid", "mark", "authenticationCode"} \
            <= resp["data"].keys()

    def test_einvoice_unknown_combination_returns_2001(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            handle_request(
                {"service": "eInvoice", "clientID": final_session,
                 "key": "9999", "template": "9999"},
                db_path=db_path,
            )
        assert exc_info.value.code == 2001

    def test_calculate_delegates_to_get_data(
        self, final_session: str, db_path: Path
    ) -> None:
        # `calculate` is a read-only preview in the mock -- it must echo
        # the same shape `getData` would for the same OBJECT/KEY.
        get_resp = handle_request(
            {"service": "getData", "clientID": final_session,
             "OBJECT": "ITEM", "KEY": 1001},
            db_path=db_path,
        )
        calc_resp = handle_request(
            {"service": "calculate", "clientID": final_session,
             "OBJECT": "ITEM", "KEY": 1001},
            db_path=db_path,
        )
        assert calc_resp["data"]["ITEM"][0]["ID"] == get_resp["data"]["ITEM"][0]["ID"]


class TestSessionEnforcement:
    """Every authenticated service must reject calls without a valid session."""

    @pytest.mark.parametrize(
        "service_payload",
        [
            {"service": "getObjects"},
            {"service": "getData", "OBJECT": "CUSTOMER", "KEY": 47},
            {"service": "setData", "OBJECT": "ORDER",
             "data": {"ORDER": [{"CUSTOMER_ID": 47}]}},
            {"service": "delData", "OBJECT": "ORDER", "KEY": "5005"},
            {"service": "SqlData", "SqlName": "myItems"},
            {"service": "eInvoice", "key": "47", "template": "102"},
        ],
        ids=["getObjects", "getData", "setData", "delData", "SqlData", "eInvoice"],
    )
    def test_missing_client_id_rejected(
        self, db_path: Path, service_payload: dict
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            handle_request({**service_payload, "clientID": ""}, db_path=db_path)
        assert exc_info.value.code == -1

    def test_unknown_client_id_rejected(self, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            handle_request(
                {"service": "getObjects", "clientID": "not-a-real-token"},
                db_path=db_path,
            )
        assert exc_info.value.code == -1
