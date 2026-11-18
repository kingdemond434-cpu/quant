---
id: L0359
cost: blind
tags: ["registry", "moat"]
enforced_by: tests/moat/test_registry.py::test_sync_from_desk_pours_the_record_in_and_is_idempotent
---

# L0359

A store that nothing writes is a claim, not a record: when a registry, ledger or table exists in a backup manifest with zero rows in its research tables, treat the machinery as dormant and wire every producer to it before building anything that reads it (2026-09-17: the replicated alpha registry held 8 cards and 1,344 events and zero research_candidates, research_runs, research_memory, trials_ledger and workers rows; the file was not even on the trading box; research_os.sqlite had six empty tables).

## Evidence

backups/moat/manifest.json table_rows 2026-08-29; libs/moat/registry.py; desks/mt5/reports/RESEARCH_REGISTRY.json

## Enforced by

`tests/moat/test_registry.py::test_sync_from_desk_pours_the_record_in_and_is_idempotent`

## Tags

#registry #moat

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
