-- Operational source schema (synthetic stand-in for SQL Server)

CREATE TABLE customers (
    id              INTEGER PRIMARY KEY,
    external_id     TEXT,                -- bad schema choice: unbounded text identifier
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    address         TEXT,
    is_test         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE advances (
    id              INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    amount_cents    INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'funded', 'paid_off', 'cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    advance_id      INTEGER REFERENCES advances(id),
    amount_cents    INTEGER NOT NULL,
    txn_type        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- append-only: no updated_at / deleted_at by design
);

CREATE TABLE cards (
    id              INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    last_four       TEXT NOT NULL,
    brand           TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- Append-only history / version table
CREATE TABLE customer_history (
    id              BIGSERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    change_type     TEXT NOT NULL,
    payload         JSONB NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unused scratch table — pipeline must exclude it
CREATE TABLE tmp_scratch_imports (
    id              INTEGER PRIMARY KEY,
    junk            TEXT,
    imported_at     TIMESTAMPTZ DEFAULT NOW()
);
