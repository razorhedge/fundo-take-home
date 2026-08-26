"""Incremental extract from Postgres → DuckDB raw, then build curated mirrors.

Watermarks advance only after a successful apply (supports mid-run recovery).
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import APPEND_TABLES, MUTABLE_TABLES
from .db import source_conn, warehouse_conn
from .init_warehouse import init_warehouse

MUTABLE_COLUMNS = {
    "customers": [
        "id",
        "external_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "is_test",
        "created_at",
        "updated_at",
        "deleted_at",
    ],
    "advances": [
        "id",
        "customer_id",
        "amount_cents",
        "status",
        "created_at",
        "updated_at",
        "deleted_at",
    ],
    "cards": [
        "id",
        "customer_id",
        "last_four",
        "brand",
        "created_at",
        "updated_at",
        "deleted_at",
    ],
}

APPEND_COLUMNS = {
    "transactions": [
        "id",
        "customer_id",
        "advance_id",
        "amount_cents",
        "txn_type",
        "created_at",
    ],
    "customer_history": [
        "id",
        "customer_id",
        "change_type",
        "payload",
        "recorded_at",
    ],
}


def _get_watermark(con, table: str) -> str | None:
    row = con.execute(
        "SELECT watermark FROM meta.watermarks WHERE table_name = ?",
        [table],
    ).fetchone()
    return row[0] if row else None


def _set_watermark(con, table: str, watermark: str, strategy: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    con.execute(
        """
        INSERT INTO meta.watermarks (table_name, watermark, strategy, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (table_name) DO UPDATE SET
            watermark = excluded.watermark,
            strategy = excluded.strategy,
            updated_at = excluded.updated_at
        """,
        [table, watermark, strategy, now],
    )


def _fetch_mutable(pg, table: str, watermark: str | None) -> list[tuple]:
    cols = MUTABLE_COLUMNS[table]
    col_sql = ", ".join(cols)
    if watermark is None:
        sql = f"SELECT {col_sql} FROM {table}"
        params: tuple[Any, ...] = ()
    else:
        sql = f"SELECT {col_sql} FROM {table} WHERE updated_at > %s::timestamptz"
        params = (watermark,)
    with pg.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _fetch_append(pg, table: str, watermark: str | None) -> list[tuple]:
    cols = APPEND_COLUMNS[table]
    col_sql = ", ".join(cols)
    if watermark is None:
        sql = f"SELECT {col_sql} FROM {table}"
        params: tuple[Any, ...] = ()
    else:
        sql = f"SELECT {col_sql} FROM {table} WHERE id > %s"
        params = (int(watermark),)
    with pg.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    # JSONB → str for DuckDB
    if table == "customer_history":
        fixed = []
        for r in rows:
            payload = r[3]
            if payload is not None and not isinstance(payload, str):
                payload = str(payload)
            fixed.append((r[0], r[1], r[2], payload, r[4]))
        return fixed
    return rows


def _upsert_raw(con, table: str, columns: list[str], rows: list[tuple]) -> None:
    if not rows:
        return
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(columns)
    # Idempotent apply: delete existing PKs then insert
    ids = [r[0] for r in rows]
    con.executemany(
        f"DELETE FROM raw.{table} WHERE id = ?",
        [(i,) for i in ids],
    )
    con.executemany(
        f"INSERT INTO raw.{table} ({col_list}) VALUES ({placeholders})",
        rows,
    )


def _purge_soft_deleted(con, table: str) -> int:
    """Remove soft-deleted rows from raw so active warehouse mirrors source actives."""
    before = con.execute(
        f"SELECT COUNT(*) FROM raw.{table} WHERE deleted_at IS NOT NULL"
    ).fetchone()[0]
    con.execute(f"DELETE FROM raw.{table} WHERE deleted_at IS NOT NULL")
    return int(before)


def _max_updated_at(rows: list[tuple], updated_idx: int) -> str | None:
    if not rows:
        return None
    values = [r[updated_idx] for r in rows if r[updated_idx] is not None]
    if not values:
        return None
    mx = max(values)
    if isinstance(mx, datetime):
        return mx.isoformat()
    return str(mx)


def _max_id(rows: list[tuple]) -> str | None:
    if not rows:
        return None
    return str(max(r[0] for r in rows))


def reconcile_hard_deletes(pg, con) -> dict[str, int]:
    """Key reconciliation: drop raw rows whose PK no longer exists in source."""
    removed: dict[str, int] = {}
    for table in MUTABLE_TABLES + APPEND_TABLES:
        with pg.cursor() as cur:
            cur.execute(f"SELECT id FROM {table}")
            source_ids = {r[0] for r in cur.fetchall()}
        raw_ids = {
            r[0]
            for r in con.execute(f"SELECT id FROM raw.{table}").fetchall()
        }
        orphans = raw_ids - source_ids
        for oid in orphans:
            con.execute(f"DELETE FROM raw.{table} WHERE id = ?", [oid])
        removed[table] = len(orphans)
    return removed


def extract_and_apply(*, full_refresh: bool = False) -> dict[str, Any]:
    init_warehouse()
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    stats: dict[str, Any] = {"run_id": run_id, "tables": {}, "seconds": 0.0}
    t0 = time.perf_counter()

    with warehouse_conn() as con:
        con.execute(
            """
            INSERT INTO meta.pipeline_runs (run_id, started_at, status)
            VALUES (?, ?, 'running')
            """,
            [run_id, started.replace(tzinfo=None)],
        )

        try:
            with source_conn() as pg:
                for table in MUTABLE_TABLES:
                    wm = None if full_refresh else _get_watermark(con, table)
                    if full_refresh:
                        con.execute(f"DELETE FROM raw.{table}")
                    rows = _fetch_mutable(pg, table, wm)
                    _upsert_raw(con, table, MUTABLE_COLUMNS[table], rows)
                    deleted = _purge_soft_deleted(con, table)
                    # updated_at is always second-to-last before deleted_at for our schemas
                    updated_idx = MUTABLE_COLUMNS[table].index("updated_at")
                    new_wm = _max_updated_at(rows, updated_idx)
                    if new_wm is not None:
                        prev = wm
                        # Keep the max of previous and new
                        if prev and prev > new_wm:
                            new_wm = prev
                        _set_watermark(con, table, new_wm, "updated_at")
                    elif wm is None and not rows:
                        _set_watermark(con, table, "1970-01-01T00:00:00+00:00", "updated_at")
                    stats["tables"][table] = {
                        "extracted": len(rows),
                        "soft_deleted_purged": deleted,
                        "strategy": "updated_at+soft_delete",
                        "watermark": _get_watermark(con, table),
                    }

                for table in APPEND_TABLES:
                    wm = None if full_refresh else _get_watermark(con, table)
                    if full_refresh:
                        con.execute(f"DELETE FROM raw.{table}")
                        wm = None
                    rows = _fetch_append(pg, table, wm)
                    _upsert_raw(con, table, APPEND_COLUMNS[table], rows)
                    new_wm = _max_id(rows)
                    if new_wm is not None:
                        _set_watermark(con, table, new_wm, "id")
                    elif wm is None:
                        _set_watermark(con, table, "0", "id")
                    stats["tables"][table] = {
                        "extracted": len(rows),
                        "strategy": "append_id",
                        "watermark": _get_watermark(con, table),
                    }

                removed = reconcile_hard_deletes(pg, con)
                stats["hard_delete_reconciled"] = removed

            finished = datetime.now(timezone.utc).replace(tzinfo=None)
            con.execute(
                """
                UPDATE meta.pipeline_runs
                SET finished_at = ?, status = 'success'
                WHERE run_id = ?
                """,
                [finished, run_id],
            )
        except Exception as exc:
            finished = datetime.now(timezone.utc).replace(tzinfo=None)
            con.execute(
                """
                UPDATE meta.pipeline_runs
                SET finished_at = ?, status = 'failed', notes = ?
                WHERE run_id = ?
                """,
                [finished, str(exc), run_id],
            )
            raise

    stats["seconds"] = round(time.perf_counter() - t0, 4)
    return stats


if __name__ == "__main__":
    import json

    print(json.dumps(extract_and_apply(), indent=2, default=str))
