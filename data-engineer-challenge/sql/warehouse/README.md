-- Warehouse DDL is created by src/pipeline/init_warehouse.py (DuckDB).

-- meta.watermarks / meta.pipeline_runs  — incremental control
-- raw.*                                 — 1:1 extract from source (soft-deletes purged)
-- curated.*                             — deduped customers, remapped FKs, dq_results
