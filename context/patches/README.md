# Desktop-pass patches carried for terminals that cannot read /mnt/project-files

PR #162 Reddit-lineage quarantine, re-cut 2026-10-07 after the audit HOLD (rescore/PR162_v2.md).
Apply only after #162 (`libs/data/terms_fence.py`) has merged. Each patch applies to live on its
own and all three apply together.

- `pr162_usdjpy_lineage_quarantine_v2.patch`: a LINEAGE quarantine, not a symbol ban.
  - `live_policy.quarantined_sleeves` is a deny list by name. It holds the five Reddit-judged
    USDJPY session-breakout names. `live_sleeves.USDJPY` (the principal's 09-24 one-sleeve choice)
    is unchanged, so a clean re-certification of the same rr=2.5 cell is admitted.
  - The forgone growth is billed by the new `terms_lineage_quarantine` rail
    (`missed_growth.measure_terms_quarantine`).
  - central_bank and forexfactory also proposed the cell (`external_20260825_2054.json`). #162's
    `terms_recert_queue.json` queues that re-certification.
  - Replaces `pr162_usdjpy_rr25_live_policy_quarantine.patch`, which set `USDJPY: []`.
- `pr162_promoter_terms_quarantine_v2.patch`:
  - A fence that does not load fails closed on the quarantined keys only.
  - The rr=2.5 live aliases (`USDJPY.asia#rr=2.5`, `usdjpy_session_range_breakout_asia_rr25_wb12`)
    resolve to the certificate, whose fence row has `sleeve=None`.
- `pr162_allocator_terms_quarantine_v2.patch`:
  - A failed import prices every certificate except the quarantined ones (previously it returned
    `{}`, which priced nothing).
  - `acct["terms_fence"]` names which path ran.

Each patch carries its own test. Run with `git apply` and then the named tests.
