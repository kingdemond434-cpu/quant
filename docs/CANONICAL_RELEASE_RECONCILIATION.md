# Canonical release reconciliation -- measured, not estimated

The desk runs TWO code lines. This is the P0 behind every 'is it really live?' question, and
this file is the measurement, taken 2026-09-05T00:02Z. Nothing here is an estimate.

## The three states

| state | ref | sha |
|---|---|---|
| canonical (has tier1-batch + all P0 feature branches) | `origin/desk-sync-clean` | `f9fd6a26d3` |
| what the TRADING BOX actually runs | `claude/llm-auto-upgrade-verify-gcjac3` | `0953da9d9f` |
| common ancestor | -- | `79ab470551` (2026-08-20, 16 days) |

Immutable backups taken before any merge work:

- `backup/boxbranch-20260905T000250Z`
- `backup/canonical-20260905T000250Z`
- `backup/vps-local-20260905T000250Z`

## Already consolidated (good news)

`origin/desk-sync-clean` ALREADY contains `claude/tier1-batch` and every major P0 branch:
allocator-p0, validator-p0, lockbox-recert, state-admission, execution-attribution,
dynamic-allocator, factor-residuals, regime-hazard, session-conditioning,
verify-the-unverified, event-liquidity-states. The integration branch is not missing --
the BOX is simply not on it.

## What reconciliation actually costs

A real `git merge` (not merge-tree) leaves **87 unmerged files**:

- **38 Python**, 182 conflict hunks
- 36 generated data artifacts (json/jsonl/pkl)
- 5 docs, 8 other

**Every one of the 87 conflicts is BOTH-SIDES-CHANGED.**
There is no 'one side is stale, take the other' shortcut anywhere in this merge. Both lines
were developed against the same ancestor for 16 days.

## The money path is the danger, and it has burned twice already

`gateway.py` alone: canonical +2098/-46 over 30 commits; box +1527/-42 over 6. Both sides
rewrote it independently -- hence 32 conflict hunks in the order gateway.

Two commits already in the box branch's own history record this exact accident:

- `06518c4a` "The Windows box's working copy overwrote the repo, and it took the money-path fixes with it"
- `ecb2c195` "Restore gateway.py and config.py from a same-night regression that reintroduced the L1.67 over-risking bug -- reported as a 'gateway margin fix'"

A careless resolution here does not produce a merge conflict. It produces an over-risking bug
on a live account that reports itself as a fix. That is why this merge is NOT automated and
NOT done at market open.

## Resolution order (money path last, behind its own tests)

1. Generated data artifacts -- regenerate, never hand-merge; they are outputs, not source.
2. Docs/config (`CLAUDE.md`, `AGENTS.md`, `.gitignore`) -- union of both sides.
3. Non-money research modules -- resolve, then run the module's own tests.
4. Forward/registry (`shadow_forward`, `sleeve_registry`, `shadow_admission`) -- resolve, then
   prove IDENTITY_BROKEN stays 0 and no forward_start moves.
5. **Money path LAST** (`gateway.py`, `sizing.py`, `allocation.py`, `promoter.py`,
   `universal_gate.py`) -- per-hunk, with `test_risk_units.py` and an explicit L1.67
   over-risking assertion green before the hunk is accepted.

Deploy the merged SHA to the box only after 3-5 pass, and record that SHA as the one canonical
live release.

## Per-file inventory

`canon`/`box` = commits touching that file on each side since the ancestor.

| file | canon | box | hunks | class |
|---|---|---|---|---|
| `desks/mt5/mt5desk/gateway.py` | 30 | 6 | 32 | MONEY PATH |
| `desks/mt5/research/shadow_forward.py` | 42 | 9 | 12 | code |
| `desks/mt5/research/qquant_gates.py` | 9 | 6 | 9 | code |
| `desks/mt5/tests/test_risk_units.py` | 6 | 3 | 9 | MONEY PATH |
| `desks/mt5/research/promoter.py` | 23 | 4 | 8 | MONEY PATH |
| `desks/mt5/research/scalp_shadow.py` | 5 | 4 | 8 | code |
| `desks/mt5/research/qquant_shadow.py` | 6 | 1 | 7 | code |
| `desks/mt5/research/shadow_cycle.py` | 9 | 4 | 6 | code |
| `scripts/audit_mt5_capability_reuse.py` | 2 | 1 | 6 | code |
| `tests/scripts/test_build_mt5_midnight_state.py` | 4 | 4 | 6 | test |
| `desks/mt5/research/h1_source.py` | 7 | 1 | 5 | code |
| `desks/mt5/research/hourly_cycle.py` | 6 | 4 | 5 | code |
| `desks/mt5/research/shadow_admission.py` | 10 | 2 | 5 | code |
| `desks/mt5/research/sleeve_registry.py` | 10 | 1 | 5 | code |
| `desks/mt5/research/universal_gate.py` | 16 | 8 | 5 | MONEY PATH |
| `scripts/build_mt5_midnight_state.py` | 3 | 4 | 5 | code |
| `tests/ops/test_midnight_controller.py` | 7 | 5 | 5 | test |
| `desks/mt5/mt5desk/tape.py` | 4 | 2 | 4 | code |
| `desks/mt5/tests/test_shadow_admission_policy.py` | 8 | 6 | 4 | test |
| `desks/mt5/mt5desk/sizing.py` | 2 | 1 | 3 | MONEY PATH |
| `desks/mt5/research/allocation.py` | 6 | 2 | 3 | MONEY PATH |
| `desks/mt5/research/portfolio_projection.py` | 7 | 1 | 3 | code |
| `desks/mt5/research/run_hunt12.py` | 8 | 2 | 3 | code |
| `desks/mt5/tests/test_hunt_deflate_policy.py` | 3 | 2 | 3 | test |
| `desks/mt5/tests/test_shadow_cycle.py` | 7 | 2 | 3 | test |
| `desks/mt5/tests/test_stop_aware_sizing.py` | 3 | 2 | 3 | MONEY PATH |
| `desks/mt5/research/run_hunt17.py` | 7 | 2 | 2 | code |
| `desks/mt5/tests/test_scalp_shadow.py` | 1 | 3 | 2 | test |
| `desks/mt5/tests/test_universe_discovery.py` | 2 | 1 | 2 | test |
| `tests/scripts/test_audit_mt5_capability_reuse.py` | 2 | 1 | 2 | test |
| `desks/mt5/mt5desk/families.py` | 12 | 3 | 1 | code |
| `desks/mt5/mt5desk/gateway_config_fallback.py` | 3 | 2 | 1 | code |
| `desks/mt5/research/daily_cycle.py` | 15 | 6 | 1 | code |
| `desks/mt5/tests/test_compendium_data.py` | 6 | 5 | 1 | test |
| `desks/mt5/tests/test_daily_cycle.py` | 1 | 3 | 1 | test |
| `desks/mt5/tests/test_portfolio_heat.py` | 4 | 1 | 1 | test |
| `desks/mt5/tests/test_state_chain.py` | 4 | 1 | 1 | test |
| `scripts/run_cashcarry_executor.py` | 5 | 1 | 0 | code |

Plus 36 data artifacts, 5 docs, 8 other -- see git for the full list.

