"""Intentionally break / restore warehouse state for the DQ demo."""

from __future__ import annotations

from .db import warehouse_conn


def break_warehouse() -> None:
    """Delete raw transactions so completeness checks fail."""
    with warehouse_conn() as con:
        con.execute("DELETE FROM raw.transactions WHERE id <= 10")
    print("Broke warehouse: deleted raw.transactions id <= 10")


def restore_via_pipeline() -> None:
    """Re-run extract+dedupe to repair (caller may also invoke make pipeline)."""
    from .dedupe import resolve_customers
    from .extract_apply import extract_and_apply

    # Force full refresh of transactions by clearing watermark and re-extracting
    with warehouse_conn() as con:
        con.execute("DELETE FROM meta.watermarks WHERE table_name = 'transactions'")
        con.execute("DELETE FROM raw.transactions")
    stats = extract_and_apply(full_refresh=False)
    resolve_customers()
    print("Restored via pipeline replay:", stats["tables"].get("transactions"))


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "break"
    if cmd == "break":
        break_warehouse()
    elif cmd == "restore":
        restore_via_pipeline()
    else:
        raise SystemExit(f"Unknown command: {cmd}")
