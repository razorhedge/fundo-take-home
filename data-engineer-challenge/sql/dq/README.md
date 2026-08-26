-- Example trust checks (from dq.py)

-- 1) Completeness: source active count vs warehouse raw count (per table)
-- 2) Gaps: source PKs missing from raw / unexpected raw PKs
-- 3) Soft deletes: deleted source customers must not remain in raw
-- 4) Scratch exclusion: tmp_scratch_imports must not be replicated
-- 5) Orphans: curated advances/cards must reference curated customers
-- 6) Card remap: cards from merged duplicates land on the survivor
-- 7) Dual-funded conflict: no auto-merge when two funded customers share identity
-- 8) Test exclusion: Testerman kept; fundo.com test accounts excluded
