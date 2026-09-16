from __future__ import annotations

import json

from softone_wrapper import SoftOneClient

from config import load_config


def _print(title: str, payload: dict) -> None:
    print()
    print(f"== {title} ==")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    cfg = load_config()

    client = SoftOneClient.mock() if cfg.mock else SoftOneClient()

    start = client.start_connection(
        base_url=cfg.base_url,
        username=cfg.username,
        password=cfg.password,
        app_id=cfg.app_id,
    )

    if not start.selections or not start.temp_client_id:
        raise RuntimeError("Expected selections + temporary clientID from login")

    selection = start.selections[0]
    session = client.complete_connection(
        base_url=cfg.base_url,
        app_id=cfg.app_id,
        temp_client_id=start.temp_client_id,
        selection=selection,
    )

    print(f"session_id = {session.session_id}")

    _print("getObjects", client.getObjects(session_id=session.session_id))
    _print("getObjectTables(CUSTOMER)", client.getObjectTables(session_id=session.session_id, OBJECT="CUSTOMER"))
    _print(
        "getTableFields(CUSTOMER,CUSTOMER)",
        client.getTableFields(session_id=session.session_id, OBJECT="CUSTOMER", TABLE="CUSTOMER"),
    )
    _print(
        "selectorFields(CUSTOMER TRDR=47)",
        client.selectorFields(
            session_id=session.session_id,
            TABLENAME="CUSTOMER",
            KEYNAME="TRDR",
            KEYVALUE=47,
            RESULTFIELDS="CODE,NAME,AFM",
        ),
    )
    _print("SqlData(myItems)", client.SqlData(session_id=session.session_id, SqlName="myItems", param1="1000%"))
    _print("eInvoice(key=47, template=102)", client.eInvoice(session_id=session.session_id, key="47", template="102"))

    # CRUD-style services
    _print(
        "getData(CUSTOMER KEY=47)",
        client.getData(
            session_id=session.session_id,
            OBJECT="CUSTOMER",
            KEY=47,
            FORM="",
            LOCATEINFO="CUSTOMER:CODE,NAME,AFM;CUSEXTRA:VARCHAR02",
        ),
    )

    set_resp = client.setData(
        session_id=session.session_id,
        OBJECT="CUSTOMER",
        KEY="47",
        data={
            "CUSTOMER": [
                {
                    "CODE": "100",
                    "NAME": "Soft One Technologies S.A.",
                    "AFM": "999863881",
                    "IRSDATA": "IV Athens",
                    "EMAIL": "johng@softone.gr",
                    "WEBPAGE": "www.softone.gr",
                    "PHONE01": "+302109484797",
                    "PHONE02": "+302108889999",
                    "FAX": "9484094",
                    "ADDRESS": "6 Poseidonos street",
                    "ZIP": "17674",
                    "DISTRICT": "Kallithea",
                    "DISCOUNT": 10,
                    "REMARKS": "Hello World! (updated)",
                }
            ],
            "CUSEXTRA": [{"VARCHAR01": "Extra 1", "VARCHAR02": "Extra 2 (updated)"}],
        },
    )
    _print("setData(CUSTOMER KEY=47)", set_resp)
    _print(
        "getData(CUSTOMER KEY=47 after setData)",
        client.getData(session_id=session.session_id, OBJECT="CUSTOMER", KEY=int(set_resp["id"]), FORM=""),
    )

    calc_resp = client.calculate(
        session_id=session.session_id,
        OBJECT="CUSTOMER",
        KEY="47",
        LOCATEINFO="CUSTOMER:CODE,NAME,AFM",
        data={
            "CUSTOMER": [{"CODE": "100", "NAME": "Soft One Technologies S.A.", "AFM": "999863881"}],
            "CUSEXTRA": [{"VARCHAR01": "Extra 1", "VARCHAR02": "Extra 2"}],
        },
    )
    _print("calculate(CUSTOMER KEY=47)", calc_resp)

    # Demonstrate delete on a newly inserted record.
    ins = client.setData(
        session_id=session.session_id,
        OBJECT="CUSTOMER",
        KEY=None,
        data={"CUSTOMER": [{"CODE": "TMP-1", "NAME": "Temp Customer", "AFM": "000000000"}]},
    )
    _print("setData(insert new CUSTOMER)", ins)
    _print("delData(new CUSTOMER)", client.delData(session_id=session.session_id, OBJECT="CUSTOMER", KEY=int(ins["id"])))

    try:
        client.getData(session_id=session.session_id, OBJECT="CUSTOMER", KEY=int(ins["id"]), FORM="")
        print("ERROR: expected getData after delData to fail, but it succeeded")
    except Exception as e:  # noqa: BLE001
        print()
        print("== getData(after delData) expected failure ==")
        print(repr(e))


if __name__ == "__main__":
    main()

