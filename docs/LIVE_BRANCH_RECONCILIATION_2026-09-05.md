# Reconciling the box's branch with `desk-sync-clean` (2026-09-05)

The Windows trading box (Contabo, `C:\opt\quant`) runs `claude/llm-auto-upgrade-verify-gcjac3`.
The VPS and every research seat run `desk-sync-clean`. On 2026-09-05 the two were 364 / 1147
commits apart with a merge base of 2026-08-20, and a plain `git merge` reported 87 conflicts.
This document records how the merge was resolved, so the next one is a fast-forward and not
another judgement call.

## Why the plain merge was wrong even where it was clean

The merge base is not where the box's code actually forked. The box's copies of the money-path
modules were **ported** from `desk-sync-clean` on 2026-09-02 ("money path: bring the five modules
the desk box runs up to desk-sync-clean") and changed on the box afterwards. Against the
2026-08-20 base, both sides look like they rewrote everything and git cannot tell a box fix from a
desk fix. Against the *port blob* -- the newest `desk-sync-clean` blob that is an ancestor of the
box's copy -- the box's own delta is small and specific.

So every conflicted code file was classified by blob ancestry:

* **the box's blob is a past `desk-sync-clean` blob** (gateway, sizing, promoter, shadow_forward,
  h1_source, tape, universal_gate, sleeve_registry, shadow_admission, shadow_cycle,
  qquant_shadow, allocation, the ops scripts, the midnight-controller tests): the box has nothing
  the desk lacks -> **desk's version**.
* **the box changed the file after the port**: a three-way merge with the port blob as base, then
  each box delta was read and judged:
  * kept as a union -- `hourly_cycle.py` (launch verified, not assumed: `launch_ok`, `time.sleep`,
    `restart_failed`), `portfolio_projection.py` (UNPRICEABLE survivors reported, never a crash or
    a silently smaller book), `families.py` (the six dip-buy / fair-value-gap / order-block /
    macro-swing families), `daily_cycle.py` (desk's superset of STEPS), `test_daily_cycle.py`
    (relative order pinned, `export_aurum` last).
  * **trample reverts refused** -- `run_hunt17.py`'s box delta *removed* `Costs.stressed` and the
    L1.68 `d1_session_filtered` wiring: the revert loop the sync script's own header describes,
    not a fix. Desk's version.
  * **desk-side regressions refused** -- `desk-sync-clean`'s `qquant_gates.py` and `run_hunt12.py`
    were themselves trampled copies (the laptop path `C:\Users\dell`, `REAL_SURVIVORS.json`, a
    positional trial matrix, `E_MAX = 1.5` with no sweep sizing). The box's copies carried the
    calibrated census, the charged trial count, the date-aligned matrix, the gate policy
    attestation and the multiplicity override sized to the real grid. Result: the box's
    `qquant_gates.py` plus desk's stricter commission term (`3.50 * mult`); desk's `run_hunt12.py`
    (the bar-calendar `day_states` with the L1.68 levels) plus the box's multiplicity import,
    `E_MAX` override in `main()` and `Costs.from_symbol`.
* **the box's own tooling** (`scripts/sync_to_vps.ps1`): the box's version.
* **`scripts/run_cashcarry_executor.py`**: removed. Desk retired it under the MT5 universe
  mandate; the box's only change was a docstring saying the same thing.

## State files: newer wins

Every conflicted file under `desks/mt5/data/` and `desks/mt5/logs/` was taken from whichever
branch committed it more recently. That is `desk-sync-clean` for all of them but
`gateway_state.json`: the VPS has been pulling the box's artifacts and committing them through
2026-09-04, while the box itself has not pushed since 2026-08-26. The box's working copies are
newer than either branch and survive the merge on the box (its sync script parks and restores
dirty files around a merge), so the branch content only has to be the newer of the two commits.

## Verified

`desks/mt5` suite and the root desk tests in the merged tree: green except one test that fails
identically on `desk-sync-clean` (`tests/desks/test_universe_pull_guard.py::
test_the_live_failure_is_refused`, pre-existing). Every merged Python file compiles; no conflict
markers remain; the box's four synced state files stay tracked.

## Standing rule from here

Every merge to `desk-sync-clean` is followed by a merge into the box's branch. Code that lands
on one branch only is inert on the box that trades, and that is how certificates and forward
clocks were lost: the box ran a `sleeve_registry.py` predating `behaviour_hash` and killed all
52 clocks on a code edit that read as a strategy change. The VPS's drift healer
(`scripts/check_desk_module_drift.py`) now also carries the box's sync script and the money-path
modules, so the box receives code by ssh even while its own git sync is broken.
