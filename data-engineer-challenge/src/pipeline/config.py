"""Shared configuration for the local pipeline."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WAREHOUSE_PATH = Path(os.environ.get("WAREHOUSE_PATH", DATA_DIR / "warehouse.duckdb"))

PG_DSN = os.environ.get(
    "SOURCE_DSN",
    "postgresql://fundo:fundo@localhost:5432/ops",
)

# Domains that mark synthetic/test accounts (not substring matching on names).
TEST_EMAIL_DOMAINS = frozenset({"fundo.com"})

# Mutable tables: watermark on updated_at + soft-delete via deleted_at
MUTABLE_TABLES = ("customers", "advances", "cards")

# Append-only tables: watermark on id
APPEND_TABLES = ("transactions", "customer_history")

# Never replicate
EXCLUDED_TABLES = ("tmp_scratch_imports",)

REPLICATED_TABLES = MUTABLE_TABLES + APPEND_TABLES
