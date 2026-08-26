"""Initialize DuckDB warehouse control + raw/curated schemas."""

from __future__ import annotations

from .db import warehouse_conn

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS curated;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.watermarks (
    table_name   VARCHAR PRIMARY KEY,
    watermark    VARCHAR NOT NULL,
    strategy     VARCHAR NOT NULL,
    updated_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    run_id       VARCHAR PRIMARY KEY,
    started_at   TIMESTAMP NOT NULL,
    finished_at  TIMESTAMP,
    status       VARCHAR NOT NULL,
    notes        VARCHAR
);

CREATE TABLE IF NOT EXISTS raw.customers (
    id INTEGER,
    external_id VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    email VARCHAR,
    phone VARCHAR,
    address VARCHAR,
    is_test BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.advances (
    id INTEGER,
    customer_id INTEGER,
    amount_cents INTEGER,
    status VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.transactions (
    id BIGINT,
    customer_id INTEGER,
    advance_id INTEGER,
    amount_cents INTEGER,
    txn_type VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.cards (
    id INTEGER,
    customer_id INTEGER,
    last_four VARCHAR,
    brand VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.customer_history (
    id BIGINT,
    customer_id INTEGER,
    change_type VARCHAR,
    payload VARCHAR,
    recorded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS curated.customers (
    id INTEGER PRIMARY KEY,
    external_id VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    email VARCHAR,
    phone VARCHAR,
    address VARCHAR,
    email_valid BOOLEAN,
    phone_valid BOOLEAN,
    merged_from VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.customer_survivor_map (
    source_customer_id INTEGER PRIMARY KEY,
    survivor_customer_id INTEGER NOT NULL,
    reason VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS curated.merge_conflicts (
    group_key VARCHAR,
    customer_ids VARCHAR,
    reason VARCHAR,
    detected_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS curated.advances (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount_cents INTEGER,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.transactions (
    id BIGINT PRIMARY KEY,
    customer_id INTEGER,
    advance_id INTEGER,
    amount_cents INTEGER,
    txn_type VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS curated.cards (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    last_four VARCHAR,
    brand VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.customer_history (
    id BIGINT PRIMARY KEY,
    customer_id INTEGER,
    change_type VARCHAR,
    payload VARCHAR,
    recorded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS curated.dq_results (
    check_name   VARCHAR,
    status       VARCHAR,
    detail       VARCHAR,
    checked_at   TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS curated.contact_quality (
    metric VARCHAR PRIMARY KEY,
    value  BIGINT
);
"""


def init_warehouse() -> None:
    from .config import WAREHOUSE_PATH

    with warehouse_conn() as con:
        con.execute(DDL)
    print(f"Warehouse initialized at {WAREHOUSE_PATH}")


if __name__ == "__main__":
    init_warehouse()
