# Solution notes

The runnable demo lives under this folder; original brief in `CHALLENGE.md`. AI was used to write this solution document, but it was reviewed manually.

## Original Challenge

1. **Incremental load** (CDC-style watermarks, not log-based CDC)
2. **Duplicate customer resolution** with explicit identity rules
3. **Trust checks** with an intentional fail/pass demo

## Stack tradeoffs

| Choice | Why |
|---|---|
| **PostgreSQL** instead of SQL Server | Same relational ops model; avoids ARM/license friction for local Docker. In production we would use SQL Server CHANGE TRACKING (Log-based) CDC for true deletes and transactional consistency. |
| **DuckDB** warehouse | Local BigQuery stand-in; zero cloud credentials; easy SQL for DQ. Better than SQLite for Columnar data.|
| **Python** | Fast to ship; extract/apply/dedupe/DQ stay readable. |

## Per-table strategy

| Table | Strategy | Trade-off |
|---|---|---|
| `customers`, `advances`, `cards` | Watermark on `updated_at` + soft-delete (`deleted_at`); upsert by PK; purge soft-deletes from `raw` | Needs app discipline to bump `updated_at` and soft-delete. Hard deletes covered by a PK reconciliation pass. |
| `transactions`, `customer_history` | Append-only high-watermark on `id` | Cheap and correct while rows are insert-only. Wrong if updates appear later — then switch to mutable strategy. |
| `tmp_scratch_imports` | **Excluded** | Scratch is operational junk; replicating it wastes cost and pollutes trust. |

Reliability:

- Watermarks commit **only after** a successful apply for that run (failed runs leave the previous watermark → safe replay). 
- This is the equivalent of an audit-table pattern, but for CDC, without using transaction logs
- Apply is idempotent (delete+insert by PK).
- Soft-deleted source rows are removed from `raw`; key reconciliation drops raw orphans if a hard delete slipped through.

## Measurements (local seed)

From `make measure` / `data/measurement.json`:

| Metric | Value | Label |
|---|---|---|
| Replicated source rows (excl. scratch) | 154 | **measured** |
| Scratch rows excluded | 2 | **measured** |
| Full load rows extracted | 154 | **measured** |
| Full load time | ~0.14 s | **measured** (tiny laptop seed) |
| Incremental rows after ~1% mutation | 3 | **measured** |
| Incremental time | ~0.04 s | **measured** |
| Incremental / full row ratio | 1.95% | **measured** on this seed |
| Brief’s production change rate | ~1% | **estimated** (from challenge statement) |

Cost narrative: today’s bill is driven by **daily full-database transfer**. At ~1% change, incremental extract should move about 1% of rows (plus control overhead). This demo shows the shape of that saving on a toy volume; production savings scale with table size and network egress, not with these millisecond timings.

## Identity and merge rules

**Proves identity (auto-merge allowed):**

- Normalized **valid** email
- Non-empty `external_id` (even though the column is unbounded text — a bad schema we still use carefully)

**Suggests only:**

- Name similarity (e.g. two “Alex Rivera” rows with different emails stay separate). Fuzzy logic here creates a deletion risk.
- Phone / address fragments. Requires normalization using additional methods.

**Business rules implemented:**

- **Funded / paid-off untouchable:** Jane Doe group — customer `1` has a funded advance; `2` merges into `1`. Cards on `2` remap to `1`. Getting this wrong orphans payment instruments or attaches them to the wrong person.
- **Two funded in one identity group:** Morgan Blake `10`/`11` — **no merge**; row written to `curated.merge_conflicts`.
- **Test data excluded, not merged:** `is_test` flag and `fundo.com` email domain. We do **not** substring-match `"test"` in names — Sam **Testerman** stays.
- **Malformed contacts:** validate email/phone, **flag + count** in `curated.contact_quality`, leave values as-is (no silent “fixes”).

Curated layer excludes test customers and remaps FKs for advances, cards, and transactions onto survivors.

## Trust checks

Checks answer: is the warehouse complete and correct **right now**?

- Active row counts source ↔ `raw` (scratch excluded)
- PK set diffs
- Soft-deleted customers absent from `raw`
- Scratch table absent from warehouse
- No orphan FKs in curated advances/cards
- Card remap + dual-funded + test-exclusion assertions

`make check-fail` deletes raw transactions; checks fail visibly. `make check-fix` clears the watermark for that table and replays — checks pass.

## Production evolution

- **Tools:** SQL Server CDC → staging (GCS/S3 or Pub/Sub) → BigQuery; dbt for curated models; Elementary / Great Expectations for DQ gates.
- **One-time:** historical backfill, first-pass dedupe of the existing data, scratch-table inventory.
- **Permanent:** incremental CDC job, DQ on every run, conflict queue for dual-funded (and later soft-match review).
- **Ship first:** incremental load + trust checks — cuts transfer cost and stops silent gaps. Dedupe next; write-path uniqueness after that.

A few days of production work would replace soft-delete watermarks with real CDC and DuckDB with BigQuery; the control-plane ideas (watermarks, raw vs curated, explicit identity rules, failing checks) stay.
