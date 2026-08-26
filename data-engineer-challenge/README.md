# Data Engineer challenge — local demo

Thin local stand-in for “SQL Server → BigQuery”: PostgreSQL source, DuckDB warehouse, Python pipeline. Covers incremental load, customer dedupe, and trust checks.

The original brief is preserved in [`CHALLENGE.md`](CHALLENGE.md). Engineering decisions are in [`SOLUTION.md`](SOLUTION.md).

## Prerequisites

- Docker with Compose (`docker compose` or `docker-compose`)
- Python 3.9+

## How to run

From this directory:

```bash
# 1. Start the source database (seeds automatically)
docker compose up -d

# 2. Install Python deps and create the DuckDB warehouse schemas
python3 -m venv .venv
source .venv/bin/activate
make setup

# 3. Initial extract + dedupe
make pipeline

# Expected: JSON for extract (row counts per table) and dedupe
# (survivors, merged_away, conflicts, malformed contact counts).
```

Re-running `make pipeline` with no source changes extracts **0** new rows and leaves the warehouse identical (idempotent).

### Trust checks

```bash
make check
```

Expected: every check `[PASS]` and `OVERALL: PASS`.

Results are also written to DuckDB table `curated.dq_results`.

### Failing-check demo

```bash
#  Deletes 10 raw transactions, corrupting the data within the warehouse, and making checks fail.
make check-fail
```

Expected: `count_match:transactions` and `pk_diff:transactions` **FAIL**; overall **FAIL**.

```bash
# Replay extract for the broken table and re-check
make check-fix
```

Expected: all checks **PASS** again.

### Measure full vs incremental

```bash
make measure
```

Resets the warehouse, runs a full load, applies a small source change (~1% of rows), runs incremental, and writes `data/measurement.json`. Labels in that file mark **measured** vs **estimated** numbers.

## What each Make target does

| Target | What it does |
|---|---|
| `make setup` | `pip install -r requirements.txt` + init DuckDB schemas |
| `make pipeline` | Wait for Postgres → incremental extract/apply → customer resolve |
| `make pipeline-full` | Same, ignoring watermarks (full raw reload) |
| `make check` | Source vs warehouse trust checks |
| `make check-fail` | Break warehouse, run checks (expects failure) |
| `make check-fix` | Restore via pipeline replay, run checks (expects pass) |
| `make measure` | Timed full vs incremental measurement |
| `make clean` | Delete local DuckDB / measurement artifacts |
| `make reset-db` | `docker compose down -v && up -d` (re-seed) |

## Layout

```
docker-compose.yml      # Postgres source
sql/seed/               # Schema + synthetic data (mounted on first boot)
src/pipeline/           # extract/apply, dedupe, DQ, measure, break demo
sql/dq/                 # Check catalog (logic in Python)
sql/warehouse/          # Layer notes (DDL created in code)
data/                   # warehouse.duckdb (gitignored)
```

## Clean reset

```bash
make clean
make reset-db
make setup
make pipeline
make check
```
