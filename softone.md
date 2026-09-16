# Soft1 Web Services (SoftOne) — JSON request/response reference

Source: SoftOne public WS reference at `https://www.softone.gr/ws/`.

## Base URL

When Soft1 Web Services are installed and configured, calls are made to:

- `https://[RegisteredNameOrSerial].oncloud.gr/s1services`
- Example: `https://demo.oncloud.gr/s1services`

Ping check:

- `https://[...].oncloud.gr/s1services?ping`
- Expected text includes: `Ping from Softone WebModule`

## Common JSON shape (envelope)

- **Requests**: JSON object with at least `"service": "<serviceName>"`.
  - Many calls also require `"clientID"` and `"appId"`.
  - Other parameters are service-specific (e.g. `OBJECT`, `FILTERS`, `KEY`, etc).
- **Responses**: JSON object that typically contains:
  - `"success": true|false`
  - service-specific payload fields (e.g. `clientID`, `rows`, `reqID`, `fields`, `data`, etc)

## Authentication flow

SoftOne WS uses a `clientID` session token.

- **Step 1 (`login`)**: authenticates the Web Account (`username`, `password`, `appId`) and returns a *temporary* `clientID` plus possible selections (`COMPANY`, `BRANCH`, `MODULE`, `REFID`).
- **Step 2 (`authenticate`)**: uses the temporary `clientID` and your selected `COMPANY/BRANCH/MODULE/REFID` and returns a *final* `clientID` to use in all subsequent calls.

There’s also an alternative: if you already know `COMPANY/BRANCH/MODULE/REFID`, you can include them in the `login` request and skip `authenticate`.

## `login`

Authenticates a Web Account for web service use and returns possible login selections and a temporary `clientID`.

### Request

```json
{
  "service": "login",
  "username": "john",
  "password": "aitis",
  "appId": "2001",
  "LOGINDATE": "2017-12-31 13:59:59",
  "TIMEZONEOFFSET": -120
}
```

- `LOGINDATE` and `TIMEZONEOFFSET` are optional in the reference.

### Response

```json
{
  "success": true,
  "clientID": "Wj8T3tvs...tlrT8",
  "objs": [
    {
      "COMPANY": "1000",
      "COMPANYNAME": "Demo Company SA",
      "BRANCH": "1000",
      "BRANCHNAME": "Athens",
      "MODULE": "0",
      "MODULENAME": "Center",
      "REFID": "1",
      "REFIDNAME": "Administrator"
    }
  ]
}
```

### `login` (alternative: skip `authenticate`)

If you already know `COMPANY/BRANCH/MODULE/REFID`, you can pass them to `login` and receive a final `clientID` directly.

#### Request

```json
{
  "service": "login",
  "username": "john",
  "password": "aitis",
  "appId": "2001",
  "COMPANY": "1000",
  "BRANCH": "1000",
  "MODULE": "0",
  "REFID": "1",
  "LOGINDATE": "2017-12-31 13:59:59",
  "TIMEZONEOFFSET": -120
}
```

#### Response

```json
{
  "success": true,
  "clientID": "Wj8Te8EqWghDM...PrG8t"
}
```

## `authenticate`

Exchanges the temporary `clientID` from `login` plus your selected environment (`COMPANY`, `BRANCH`, `MODULE`, `REFID`) for a final `clientID`.

### Request

```json
{
  "service": "authenticate",
  "clientID": "Wj8T3tvs...tlrT8",
  "COMPANY": "1000",
  "BRANCH": "1000",
  "MODULE": "0",
  "REFID": "1"
}
```

### Response

```json
{
  "success": true,
  "clientID": "Wj8Te8EqWghDM...PrG8t"
}
```

## Example metadata calls

### `getObjects`

Returns all application business objects.

#### Request

```json
{
  "service": "getObjects",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001"
}
```

#### Response (shape)

```json
{
  "success": true,
  "count": 1354,
  "objects": [
    {
      "name": "CUSTOMER",
      "type": "EditMaster",
      "caption": "Customers"
    }
  ]
}
```

### `getObjectTables`

Returns all tables for a business object.

#### Request

```json
{
  "service": "getObjectTables",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "OBJECT": "CUSTOMER"
}
```

#### Response (shape)

```json
{
  "success": true,
  "count": 10,
  "tables": [
    {
      "name": "CUSTOMER",
      "dbname": "TRDR",
      "caption": "Customers",
      "filltype": "SQL"
    }
  ]
}
```

### `getTableFields`

Returns fields for a table of a business object.

#### Request

```json
{
  "service": "getTableFields",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "TABLE": "CUSTOMER"
}
```

#### Response (shape)

```json
{
  "success": true,
  "count": 136,
  "fields": [
    {
      "name": "CODE",
      "alias": "",
      "fullname": "CUSTOMER.CODE",
      "caption": "Code",
      "size": "25",
      "type": "String",
      "edittype": "Simple",
      "defaultvalue": "",
      "decimals": "",
      "editor": "",
      "readOnly": false,
      "visible": true,
      "required": true,
      "calculated": false
    }
  ]
}
```

## Example UI-driven calls (browser/report)

### `getBrowserInfo`

Executes a browser and returns a `reqID`, total record count, plus fields and column metadata.

#### Request

```json
{
  "service": "getBrowserInfo",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "LIST": "",
  "FILTERS": "CUSTOMER.CODE=30*&CUSTOMER.AFM=046156989&....."
}
```

## CRUD-style services

The following services are SoftOne’s typical **read / write** operations for Business Objects.

### `getData`

Returns all data (or the selected ones from `LOCATEINFO`) of a record of a Business Object.

#### Request

```json
{
  "service": "getData",
  "clientID": "Wj8T3tvs...tlrT8",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "FORM": "",
  "KEY": 47,
  "LOCATEINFO": "CUSTOMER:CODE,NAME,AFM;CUSEXTRA:VARCHAR02,DATE01"
}
```

#### Response (shape)

```json
{
  "success": true,
  "readOnly": true,
  "data": {
    "CUSTOMER": [
      {
        "CODE": "100",
        "NAME": "Soft One Technologies S.A.",
        "AFM": "999863881"
      }
    ]
  }
}
```

### `setData`

Insert or modify the data of a record in a Business Object identified by a `KEY`.

- If `KEY` is empty or missing, a record is inserted.

#### Request

```json
{
  "service": "setData",
  "clientID": "Wj8T3tvs...tlrT8",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "KEY": "47",
  "data": {
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
        "REMARKS": "Hello World!"
      }
    ],
    "CUSEXTRA": [
      {
        "VARCHAR01": "Extra 1",
        "VARCHAR02": "Extra 2"
      }
    ]
  }
}
```

#### Response

```json
{
  "success": true,
  "id": "47"
}
```

### `calculate`

Calculates and returns (optionally filtered by `LOCATEINFO`) a record of a Business Object for which we input/modify data **without saving**.

#### Request

```json
{
  "service": "calculate",
  "clientID": "Wj8T3tvs...tlrT8",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "KEY": "47",
  "LOCATEINFO": "CUSTOMER:CODE,NAME,AFM;CUSEXTRA:VARCHAR02,DATE01",
  "data": {
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
        "REMARKS": "Hello World!"
      }
    ],
    "CUSEXTRA": [
      {
        "VARCHAR01": "Extra 1",
        "VARCHAR02": "Extra 2"
      }
    ]
  }
}
```

#### Response (shape)

```json
{
  "success": true,
  "readOnly": true,
  "data": {
    "CUSTOMER": [
      {
        "CODE": "100",
        "NAME": "Soft One Technologies S.A.",
        "AFM": "999863881"
      }
    ]
  }
}
```

### `delData`

Deletes the record of a Business Object.

#### Request

```json
{
  "service": "delData",
  "clientID": "Wj8T3tvs...tlrT8",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "FORM": "",
  "KEY": 47
}
```

#### Response

```json
{
  "success": true
}
```

#### Response (shape)

```json
{
  "success": true,
  "formDesign": "CUSTOMER",
  "reqID": "1558138811436159279",
  "totalcount": 1,
  "fields": [
    { "name": "ZOOMINFO", "type": "string" },
    { "name": "CUSTOMER.CODE", "type": "string" }
  ],
  "columns": [
    {
      "dataIndex": "CUSTOMER.CODE",
      "header": "Code",
      "width": 120,
      "sortable": true
    }
  ]
}
```

#### Variant (server-side limiting)

```json
{
  "service": "getBrowserInfo",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "OBJECT": "CUSTOMER",
  "LIST": "",
  "VERSION": 2,
  "LIMIT": 200,
  "FILTERS": "CUSTOMER.CODE=30*&CUSTOMER.AFM=046156989&....."
}
```

## Selector helpers

### `selectorFields`

Returns data for selected fields from a table record.

#### Request

```json
{
  "service": "selectorFields",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "TABLENAME": "CUSTOMER",
  "KEYNAME": "TRDR",
  "KEYVALUE": 47,
  "RESULTFIELDS": "CODE,NAME,AFM"
}
```

#### Response

```json
{
  "success": true,
  "totalcount": 1,
  "rows": [
    {
      "CODE": "100",
      "NAME": "Soft One Technologies S.A.",
      "AFM": "999863881"
    }
  ]
}
```

## SQL execution

### `SqlData`

Executes an SQL Script by code (`SqlName`) and returns result rows. The reference notes parameters are declared in the SQL Script like `{param1}`.

#### Request

```json
{
  "service": "SqlData",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "SqlName": "myItems",
  "param1": "1000%"
}
```

#### Response (shape)

```json
{
  "success": true,
  "totalcount": 9,
  "rows": [
    {
      "MTRL": "1191",
      "CODE": "10001",
      "NAME": "Τηλεόραση LCD 32\"",
      "PRICEW": "900",
      "PRICER": "900"
    }
  ]
}
```

## e-Invoicing

### `eInvoice`

Transmits a sales document to AADE via provider and returns signatures. The reference suggests using:

- Preview URL formula: `https://einvoice-portal.s1ecos.gr/v/` + `<signature>`

#### Request

```json
{
  "service": "eInvoice",
  "clientID": "Wj8Te8EqWghDM...PrG8t",
  "appId": "2001",
  "key": "47",
  "template": "102"
}
```

#### Response (shape)

```json
{
  "success": true,
  "data": {
    "integritySignature": "5A4E71D3...",
    "signature": "EL000000001-900000-...",
    "uid": "A871D37B...",
    "mark": 402474254224724,
    "authenticationCode": "3876DGHJHJ8976..."
  }
}
```

## Error codes (from reference)


| Code | Message                                                                        | Reason / hint                           |
| ---- | ------------------------------------------------------------------------------ | --------------------------------------- |
| -101 | Invalid Request, session has expired!                                          | Web Account time expiration             |
| -100 | Invalid Request, session has expired!                                          | Deep linking smart command              |
| -12  | Invalid Web Service call.                                                      |                                         |
| -11  | Invalid Request. Licence must include a "Web Service Connector" module.        |                                         |
| -10  | Login fails. Username contains illegal characters.                             |                                         |
| -9   | Invalid Request. Ensure that your request is valid                             |                                         |
| -8   | Invalid request. User account is not active!                                   |                                         |
| -7   | Session has expired                                                            | Web Account "FinalDate" expired         |
| -6   | Invalid AppId. Ensure that your request includes a valid AppId                 | Different AppId in Request and ClientId |
| -5   | Web Services Licenses Exceeded!                                                | More license accounts than allowed      |
| -4   | Number of registered devices exceeded!                                         | More registered devices than allowed    |
| -3   | Access denied. Selected module not activated!                                  |                                         |
| -2   | Authenticate fails due to invalid credentials.                                 |                                         |
| -1   | Invalid request. Please login first                                            |                                         |
| 0    | Business error                                                                 | Check error message                     |
| 11   | Internal error                                                                 | Check error message                     |
| 12   | Deprecated service                                                             |                                         |
| 13   | Invalid request, "reqID" expired.                                              |                                         |
| 14   | Invalid request.(WS)                                                           | Check SerialNumber                      |
| 20   | Internal error                                                                 | Check error message                     |
| 99   | Internal error                                                                 | Check error message                     |
| 101  | Invalid request. Insufficient access rights to perform the operation!          | Check module / web account licences     |
| 102  | "ReqId" not found on Server!                                                   |                                         |
| 112  | Invalid editor                                                                 |                                         |
| 213  | Invalid request, "reqID" expired.                                              |                                         |
| 1001 | Please ensure :Username, Password, User is Active and has Administrator right. |                                         |
| 1002 | Invalid domain ('DOMAIN') or already in use                                    |                                         |
| 1010 | General Web Account Error                                                      |                                         |
| 2001 | Invalid request, Data does not exist.                                          |                                         |

## Local mock database (for development)

This repo includes a simple SQLite database schema and seeder that contains **mock data matching the examples above**.

- **Schema**: `mock_db/schema.sql`
- **Seeder**: `mock_db/create_and_seed.py`
- **Output DB file** (generated): `mock_db/mock_softone.db`

Run:

```bash
python mock_db/create_and_seed.py
```

It prints the created DB path plus example credentials and mock `clientID`s you can use in local tests.


