"""Warehouse trust checks: completeness, gaps, stale deletes, orphans."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import APPEND_TABLES, MUTABLE_TABLES
from .db import source_conn, warehouse_conn


def _record(con, check_name: str, status: str, detail: str) -> None:
    con.execute(
        """
        INSERT INTO curated.dq_results (check_name, status, detail, checked_at)
        VALUES (?, ?, ?, ?)
        """,
        [check_name, status, detail, datetime.utcnow()],
    )


def run_checks() -> dict[str, Any]:
    results: list[dict[str, str]] = []
    all_ok = True

    with source_conn() as pg, warehouse_conn() as con:
        con.execute("DELETE FROM curated.dq_results")

        # 1) Active row counts for mutable tables (source active vs raw)
        for table in MUTABLE_TABLES:
            with pg.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE deleted_at IS NULL"
                )
                src_count = cur.fetchone()[0]
            raw_count = con.execute(
                f"SELECT COUNT(*) FROM raw.{table} WHERE deleted_at IS NULL"
            ).fetchone()[0]
            # After purge, deleted_at should always be null in raw — count all
            raw_all = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
            ok = src_count == raw_all
            status = "pass" if ok else "fail"
            detail = f"source_active={src_count} raw={raw_all}"
            _record(con, f"count_match:{table}", status, detail)
            results.append({"check": f"count_match:{table}", "status": status, "detail": detail})
            all_ok = all_ok and ok

        for table in APPEND_TABLES:
            with pg.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                src_count = cur.fetchone()[0]
            raw_count = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
            ok = src_count == raw_count
            status = "pass" if ok else "fail"
            detail = f"source={src_count} raw={raw_count}"
            _record(con, f"count_match:{table}", status, detail)
            results.append({"check": f"count_match:{table}", "status": status, "detail": detail})
            all_ok = all_ok and ok

        # 2) PK set diffs for each replicated table
        for table in list(MUTABLE_TABLES) + list(APPEND_TABLES):
            with pg.cursor() as cur:
                if table in MUTABLE_TABLES:
                    cur.execute(f"SELECT id FROM {table} WHERE deleted_at IS NULL")
                else:
                    cur.execute(f"SELECT id FROM {table}")
                src_ids = {r[0] for r in cur.fetchall()}
            raw_ids = {r[0] for r in con.execute(f"SELECT id FROM raw.{table}").fetchall()}
            missing = sorted(src_ids - raw_ids)
            unexpected = sorted(raw_ids - src_ids)
            ok = not missing and not unexpected
            status = "pass" if ok else "fail"
            detail = f"missing={missing[:10]} unexpected={unexpected[:10]}"
            _record(con, f"pk_diff:{table}", status, detail)
            results.append({"check": f"pk_diff:{table}", "status": status, "detail": detail})
            all_ok = all_ok and ok

        # 3) Soft-deleted source customers must not be active in raw
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM customers WHERE deleted_at IS NOT NULL")
            deleted_ids = {r[0] for r in cur.fetchall()}
        raw_present = {
            r[0]
            for r in con.execute("SELECT id FROM raw.customers").fetchall()
            if r[0] in deleted_ids
        }
        ok = len(raw_present) == 0
        status = "pass" if ok else "fail"
        detail = f"soft_deleted_still_in_raw={sorted(raw_present)}"
        _record(con, "soft_delete_purged:customers", status, detail)
        results.append(
            {"check": "soft_delete_purged:customers", "status": status, "detail": detail}
        )
        all_ok = all_ok and ok

        # 4) Scratch table must not exist in warehouse
        scratch_tables = con.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema IN ('raw', 'curated')
              AND table_name = 'tmp_scratch_imports'
            """
        ).fetchall()
        ok = len(scratch_tables) == 0
        status = "pass" if ok else "fail"
        detail = f"scratch_present={bool(scratch_tables)}"
        _record(con, "scratch_excluded", status, detail)
        results.append({"check": "scratch_excluded", "status": status, "detail": detail})
        all_ok = all_ok and ok

        # 5) Orphan FKs in curated after dedupe
        orphan_adv = con.execute(
            """
            SELECT COUNT(*) FROM curated.advances a
            LEFT JOIN curated.customers c ON a.customer_id = c.id
            WHERE c.id IS NULL
            """
        ).fetchone()[0]
        orphan_cards = con.execute(
            """
            SELECT COUNT(*) FROM curated.cards a
            LEFT JOIN curated.customers c ON a.customer_id = c.id
            WHERE c.id IS NULL
            """
        ).fetchone()[0]
        ok = orphan_adv == 0 and orphan_cards == 0
        status = "pass" if ok else "fail"
        detail = f"orphan_advances={orphan_adv} orphan_cards={orphan_cards}"
        _record(con, "orphan_fks:curated", status, detail)
        results.append({"check": "orphan_fks:curated", "status": status, "detail": detail})
        all_ok = all_ok and ok

        # 6) Cards from merged-away customers remapped to survivor
        card2 = con.execute(
            "SELECT customer_id FROM curated.cards WHERE id = 2"
        ).fetchone()
        ok = card2 is not None and card2[0] == 1
        status = "pass" if ok else "fail"
        detail = f"card_2_customer_id={None if card2 is None else card2[0]} expected=1"
        _record(con, "card_remap:duplicate_group_a", status, detail)
        results.append(
            {"check": "card_remap:duplicate_group_a", "status": status, "detail": detail}
        )
        all_ok = all_ok and ok

        # 7) Dual-funded conflict preserved (no merge of 10 and 11)
        both = con.execute(
            """
            SELECT COUNT(*) FROM curated.customers WHERE id IN (10, 11)
            """
        ).fetchone()[0]
        conflict_rows = con.execute(
            "SELECT COUNT(*) FROM curated.merge_conflicts"
        ).fetchone()[0]
        ok = both == 2 and conflict_rows >= 1
        status = "pass" if ok else "fail"
        detail = f"dual_funded_survivors={both} conflicts={conflict_rows}"
        _record(con, "dual_funded_no_merge", status, detail)
        results.append({"check": "dual_funded_no_merge", "status": status, "detail": detail})
        all_ok = all_ok and ok

        # 8) Testerman kept; test@fundo.com excluded
        testerman = con.execute(
            "SELECT COUNT(*) FROM curated.customers WHERE id = 5"
        ).fetchone()[0]
        test_excluded = con.execute(
            "SELECT COUNT(*) FROM curated.customers WHERE id IN (6, 7)"
        ).fetchone()[0]
        ok = testerman == 1 and test_excluded == 0
        status = "pass" if ok else "fail"
        detail = f"testerman={testerman} test_accounts_in_curated={test_excluded}"
        _record(con, "test_exclusion_rules", status, detail)
        results.append({"check": "test_exclusion_rules", "status": status, "detail": detail})
        all_ok = all_ok and ok

    summary = {"ok": all_ok, "results": results}
    return summary


def print_report(summary: dict[str, Any]) -> None:
    print("=== DQ REPORT ===")
    for r in summary["results"]:
        mark = "PASS" if r["status"] == "pass" else "FAIL"
        print(f"[{mark}] {r['check']}: {r['detail']}")
    print("=== OVERALL:", "PASS" if summary["ok"] else "FAIL", "===")


if __name__ == "__main__":
    s = run_checks()
    print_report(s)
    raise SystemExit(0 if s["ok"] else 1)
