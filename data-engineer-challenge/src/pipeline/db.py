"""Database helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import duckdb
import psycopg

from .config import PG_DSN, WAREHOUSE_PATH


@contextmanager
def source_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(PG_DSN) as conn:
        yield conn


@contextmanager
def warehouse_conn() -> Iterator[duckdb.DuckDBPyConnection]:
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        yield con
    finally:
        con.close()
