-- SQLite schema for mocked SoftOne WS-like data.
-- This is not an official SoftOne schema; it only models the JSON examples in softone.md.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS web_accounts (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL,
  password TEXT NOT NULL,
  app_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_selections (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES web_accounts(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  company_name TEXT NOT NULL,
  branch TEXT NOT NULL,
  branch_name TEXT NOT NULL,
  module TEXT NOT NULL,
  module_name TEXT NOT NULL,
  refid TEXT NOT NULL,
  refid_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  client_id TEXT PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES web_accounts(id) ON DELETE CASCADE,
  -- 0 = temporary (from login), 1 = final (from authenticate or login-with-selection)
  is_final INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  company TEXT,
  branch TEXT,
  module TEXT,
  refid TEXT
);

CREATE TABLE IF NOT EXISTS business_objects (
  name TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  caption TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS object_tables (
  id INTEGER PRIMARY KEY,
  object_name TEXT NOT NULL REFERENCES business_objects(name) ON DELETE CASCADE,
  name TEXT NOT NULL,
  dbname TEXT NOT NULL,
  caption TEXT NOT NULL,
  filltype TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_object_tables_object_name_name
ON object_tables(object_name, name);

CREATE TABLE IF NOT EXISTS table_fields (
  id INTEGER PRIMARY KEY,
  object_name TEXT NOT NULL,
  table_name TEXT NOT NULL,
  name TEXT NOT NULL,
  alias TEXT NOT NULL DEFAULT '',
  fullname TEXT NOT NULL,
  caption TEXT NOT NULL,
  size TEXT NOT NULL,
  type TEXT NOT NULL,
  edittype TEXT NOT NULL,
  defaultvalue TEXT NOT NULL DEFAULT '',
  decimals TEXT NOT NULL DEFAULT '',
  editor TEXT NOT NULL DEFAULT '',
  readOnly INTEGER NOT NULL DEFAULT 0,
  visible INTEGER NOT NULL DEFAULT 1,
  required INTEGER NOT NULL DEFAULT 0,
  calculated INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(object_name, table_name)
    REFERENCES object_tables(object_name, name)
    ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_table_fields_object_table_field
ON table_fields(object_name, table_name, name);

-- Minimal mock "CUSTOMER" table.
CREATE TABLE IF NOT EXISTS customers (
  trdr INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  afm TEXT,
  email TEXT,
  phone TEXT,
  address TEXT,
  balance REAL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Minimal mock "CUSEXTRA" data (1:1 with customers.trdr for convenience).
CREATE TABLE IF NOT EXISTS cusextra (
  trdr INTEGER PRIMARY KEY REFERENCES customers(trdr) ON DELETE CASCADE,
  varchar01 TEXT,
  varchar02 TEXT
);

-- Mocked SQL scripts ("SQL Scripts" code) and their results.
CREATE TABLE IF NOT EXISTS sql_scripts (
  name TEXT PRIMARY KEY,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sql_rows (
  id INTEGER PRIMARY KEY,
  script_name TEXT NOT NULL REFERENCES sql_scripts(name) ON DELETE CASCADE,
  mtrl TEXT,
  code TEXT,
  name TEXT,
  pricew TEXT,
  pricer TEXT
);

-- Mocked eInvoice response data (key + template => signatures).
CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY,
  doc_key TEXT NOT NULL,
  template TEXT NOT NULL,
  integritySignature TEXT NOT NULL,
  signature TEXT NOT NULL,
  uid TEXT NOT NULL,
  mark INTEGER NOT NULL,
  authenticationCode TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_invoices_doc_key_template
ON invoices(doc_key, template);

-- NOTE on CHECK constraints below:
-- SQLite does not support `ALTER TABLE ... ADD CONSTRAINT`, so every defensive
-- rule lives inline on the table definition. The seed/business code recreates
-- the DB from scratch via this file, so inline is equivalent to the ALTERs in
-- the upgrade notes.
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  price REAL NOT NULL CHECK (price >= 0),
  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  -- Optional: enable once the reservation logic in business/orders.py is
  -- atomic (single transaction, SELECT ... FOR UPDATE-equivalent). Until
  -- then, concurrent reservations can legitimately push reserved past stock
  -- and we don't want the mock to mask that by raising a CHECK error.
  --   CHECK (reserved <= stock),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  -- RESTRICT: a customer with order history must not be deletable. Previously
  -- this defaulted to NO ACTION (same effective behavior, but implicit);
  -- spelled out so the ERP intent is obvious from the schema.
  customer_id INTEGER NOT NULL REFERENCES customers(trdr) ON DELETE RESTRICT,
  -- Status vocabulary mirrors business/orders.py (`Draft` -> `Confirmed`).
  status TEXT NOT NULL DEFAULT 'Draft'
    CHECK (status IN ('Draft', 'Confirmed')),
  total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
  -- CASCADE: lines are children of the order. Deleting the order naturally
  -- discards its lines.
  order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
  -- RESTRICT: deleting a product (SKU) must NOT silently rewrite historical
  -- orders. Real ERPs deactivate items rather than delete them; the mock now
  -- enforces the same rule by refusing the delete when any order line still
  -- references the item. This used to be CASCADE -- a latent data-loss bug.
  product_id INTEGER REFERENCES items(id) ON DELETE RESTRICT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  price REAL NOT NULL CHECK (price >= 0),
  PRIMARY KEY (order_id, product_id)
);

CREATE TABLE IF NOT EXISTS invoices_business (
  id INTEGER PRIMARY KEY,
  -- RESTRICT for the same reason as orders.customer_id: an invoiced customer
  -- has business history we don't silently delete.
  customer_id INTEGER NOT NULL REFERENCES customers(trdr) ON DELETE RESTRICT,
  -- RESTRICT: an order that has already been invoiced should not vanish out
  -- from under the invoice. Order_id may still be NULL (ad-hoc invoice).
  order_id INTEGER REFERENCES orders(id) ON DELETE RESTRICT,
  amount REAL NOT NULL CHECK (amount >= 0),
  -- Status is recomputed from sum(payments) by mock_ws.refresh_invoice_status,
  -- which only ever writes one of these three values.
  status TEXT NOT NULL DEFAULT 'unpaid'
    CHECK (status IN ('unpaid', 'partial', 'paid')),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER REFERENCES invoices_business(id) ON DELETE CASCADE,
  amount REAL NOT NULL CHECK (amount > 0),
  payment_date TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Defensive indexes
-- ---------------------------------------------------------------------------

-- One business invoice per order (NULL order_id = ad-hoc invoice, allowed
-- multiple times). Partial unique index makes "no duplicate invoicing"
-- enforceable at the DB level instead of relying on app-side checks.
CREATE UNIQUE INDEX IF NOT EXISTS ux_invoice_per_order
  ON invoices_business(order_id)
  WHERE order_id IS NOT NULL;

-- AFM (Greek tax ID) is unique per customer when present. NULL is allowed
-- and not indexed — matches how a real ERP handles unregistered counterparts.
CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_afm
  ON customers(afm)
  WHERE afm IS NOT NULL;

-- Hot lookup paths for the mocked queries.
CREATE INDEX IF NOT EXISTS idx_orders_customer       ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product   ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice      ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_business_customer
  ON invoices_business(customer_id);