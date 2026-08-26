"""Measure full vs incremental extract volumes and timings."""

from __future__ import annotations

import json
import time
from typing import Any

from .db import source_conn, warehouse_conn
from .dedupe import resolve_customers
from .extract_apply import extract_and_apply
from .init_warehouse import init_warehouse


def _source_counts() -> dict[str, int]:
    tables = [
        "customers",
        "advances",
        "transactions",
        "cards",
        "customer_history",
        "tmp_scratch_imports",
    ]
    out: dict[str, int] = {}
    with source_conn() as pg:
        with pg.cursor() as cur:
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                out[t] = cur.fetchone()[0]
    return out


def _reset_warehouse() -> None:
    from .config import WAREHOUSE_PATH

    if WAREHOUSE_PATH.exists():
        WAREHOUSE_PATH.unlink()
    init_warehouse()


def apply_incremental_source_changes() -> None:
    """Mutate ~1% of seed to demonstrate incremental extract."""
    with source_conn() as pg:
        with pg.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                SET phone = '+15551119999', updated_at = NOW()
                WHERE id = 1
                """
            )
            cur.execute(
                """
                INSERT INTO transactions (customer_id, advance_id, amount_cents, txn_type)
                VALUES (1, 1, 42, 'fee')
                """
            )
            cur.execute(
                """
                UPDATE cards
                SET brand = 'visa', updated_at = NOW()
                WHERE id = 4
                """
            )
        pg.commit()


def run_measurement() -> dict[str, Any]:
    source_counts = _source_counts()
    total_replicated = sum(
        v
        for k, v in source_counts.items()
        if k != "tmp_scratch_imports"
    )
    # Estimated change rate from the challenge brief
    estimated_change_pct = 1.0

    _reset_warehouse()
    t0 = time.perf_counter()
    full_stats = extract_and_apply(full_refresh=True)
    full_seconds = time.perf_counter() - t0
    full_rows = sum(t["extracted"] for t in full_stats["tables"].values())

    apply_incremental_source_changes()

    t1 = time.perf_counter()
    incr_stats = extract_and_apply(full_refresh=False)
    incr_seconds = time.perf_counter() - t1
    incr_rows = sum(t["extracted"] for t in incr_stats["tables"].values())

    resolve_customers()

    measured_change_pct = (
        round(100.0 * incr_rows / full_rows, 2) if full_rows else 0.0
    )

    report = {
        "source_counts": source_counts,
        "total_replicated_rows": total_replicated,
        "excluded_scratch_rows": source_counts.get("tmp_scratch_imports", 0),
        "full_load": {
            "rows_extracted": full_rows,
            "seconds_measured": round(full_seconds, 4),
            "per_table": full_stats["tables"],
        },
        "incremental_load": {
            "rows_extracted": incr_rows,
            "seconds_measured": round(incr_seconds, 4),
            "per_table": incr_stats["tables"],
            "change_pct_measured": measured_change_pct,
            "change_pct_estimated_from_brief": estimated_change_pct,
        },
        "labels": {
            "measured": [
                "source_counts",
                "full_load.rows_extracted",
                "full_load.seconds_measured",
                "incremental_load.rows_extracted",
                "incremental_load.seconds_measured",
                "incremental_load.change_pct_measured",
            ],
            "estimated": [
                "incremental_load.change_pct_estimated_from_brief",
            ],
        },
    }
    return report


if __name__ == "__main__":
    print(json.dumps(run_measurement(), indent=2, default=str))
