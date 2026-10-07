"""SoftOneClient end to end against the mock WS: two-step login, metadata, CRUD, delete."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import load_config
from softone_wrapper import SoftOneClient


@pytest.fixture
def client_and_sid(db_path: Path) -> tuple[SoftOneClient, str]:
    cfg = load_config()
    client = SoftOneClient.mock(db_path=db_path)
    start = client.start_connection(
        base_url=cfg.base_url, username=cfg.username, password=cfg.password, app_id=cfg.app_id
    )
    assert start.selections and start.temp_client_id
    session = client.complete_connection(
        base_url=cfg.base_url, app_id=cfg.app_id, temp_client_id=start.temp_client_id, selection=start.selections[0]
    )
    return client, session.session_id


def test_metadata_services(client_and_sid: tuple[SoftOneClient, str]) -> None:
    client, sid = client_and_sid
    assert client.getObjects(session_id=sid)["success"] is True
    assert client.getObjectTables(session_id=sid, OBJECT="CUSTOMER")["success"] is True
    assert client.getTableFields(session_id=sid, OBJECT="CUSTOMER", TABLE="CUSTOMER")["success"] is True


def test_set_get_delete_customer(client_and_sid: tuple[SoftOneClient, str]) -> None:
    client, sid = client_and_sid
    client.setData(session_id=sid, OBJECT="CUSTOMER", KEY="47", data={"CUSTOMER": [{"NAME": "Renamed S.A."}]})
    got = client.getData(session_id=sid, OBJECT="CUSTOMER", KEY=47, FORM="")
    assert got["data"]["CUSTOMER"][0]["NAME"] == "Renamed S.A."

    ins = client.setData(
        session_id=sid, OBJECT="CUSTOMER", KEY=None, data={"CUSTOMER": [{"CODE": "TMP-1", "NAME": "Temp", "AFM": "0"}]}
    )
    client.delData(session_id=sid, OBJECT="CUSTOMER", KEY=int(ins["id"]))
    with pytest.raises(Exception):  # noqa: B017 - any SoftOne error is fine; the record must be gone
        client.getData(session_id=sid, OBJECT="CUSTOMER", KEY=int(ins["id"]), FORM="")
