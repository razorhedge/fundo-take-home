"""CLI entrypoints for the local data pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from .dedupe import resolve_customers
from .demo_break import break_warehouse, restore_via_pipeline
from .dq import print_report, run_checks
from .extract_apply import extract_and_apply
from .init_warehouse import init_warehouse
from .measure import run_measurement


def cmd_pipeline(args: argparse.Namespace) -> int:
    stats = extract_and_apply(full_refresh=args.full)
    print(json.dumps({"extract": stats}, indent=2, default=str))
    dedupe_stats = resolve_customers()
    print(json.dumps({"dedupe": dedupe_stats}, indent=2))
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    summary = run_checks()
    print_report(summary)
    return 0 if summary["ok"] else 1


def cmd_measure(_: argparse.Namespace) -> int:
    report = run_measurement()
    out = __import__("pathlib").Path(__file__).resolve().parents[2] / "data" / "measurement.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    print(f"Wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fundo / Niuro DE local pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create DuckDB schemas")
    p_init.set_defaults(func=lambda _: (init_warehouse() or 0))

    p_pipe = sub.add_parser("pipeline", help="Extract/apply + dedupe")
    p_pipe.add_argument(
        "--full",
        action="store_true",
        help="Ignore watermarks and reload raw tables",
    )
    p_pipe.set_defaults(func=cmd_pipeline)

    p_check = sub.add_parser("check", help="Run trust checks")
    p_check.set_defaults(func=cmd_check)

    p_break = sub.add_parser("break", help="Corrupt warehouse for DQ demo")
    p_break.set_defaults(func=lambda _: (break_warehouse() or 0))

    p_restore = sub.add_parser("restore", help="Repair after break demo")
    p_restore.set_defaults(func=lambda _: (restore_via_pipeline() or 0))

    p_meas = sub.add_parser("measure", help="Measure full vs incremental")
    p_meas.set_defaults(func=cmd_measure)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
