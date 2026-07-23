# DAILY INTEGRITY WATCH — standing per-cycle duty (leaks & bugs: notice, root-cause, fix same cycle)

Binds every daily brain cycle. The desk's failure mode is not a single bad decision — it is a leak
or bug that runs SILENTLY for weeks (the 2026-07-10 phantom showed a breakeven book as −$865; three
latent bugs once silently disabled the automation). This duty makes every cycle *hunt* for those and
fix them the same cycle. "Pay for a mistake exactly once": a leak or bug noticed and NOT resolved in
the cycle that noticed it is itself a defect.

## Every cycle, run these checks (VERIFY-THEN-CLAIM — fresh read, never from memory)

1. **Carry-leak alarm.** Read `web/*` `molded.bleed_alert` / `bleed_verdict` (from
   `carry_bleed_report`). If `bleed_alert` is true, the hedge is losing more than the funding it
   earns — attribute the non-funding PnL to basis / fees / hedge-drift incidents (`tca` +
   `cashcarry_trades.json`) and fix the DOMINANT cause at source THIS cycle.
2. **Phantom-accounting reconcile.** Confirm the headline PnL is the exchange-ground-truth
   `derive_spot_realized` figure, not a raw accumulator. A book showing a loss its venue records
   don't explain is a phantom until proven real — reconcile before believing the red.
3. **Hedge integrity.** Check reconcile/orphan state — any stranded leg, broken hedge, or delta that
   drifted past band is force-re-hedged or paged, not left to bleed.
4. **Data liveness.** `data_health` — heartbeat ≠ data liveness (the 2026-07-09 silent-zero class);
   a STUCK/STALE feed under a deployed signal is a same-cycle fix.
5. **Code integrity.** If any pushed change is in play, `ruff` + `mypy` + `pytest` must be green; a
   red gate or a newly-failing test is a bug to fix this cycle, not to carry forward.

## The rule

Any alarm that fires (bleed, phantom, orphan, stale feed, red test) is ROOT-CAUSED (`root_cause`)
and FIXED in the same cycle — OR, if the fix needs live venue data / touches the money path beyond
what the cycle can safely verify, it is PAGED to the principal (ntfy) with the diagnosis, never
silently deferred. Log every check + verdict + action to the decision ledger. A clean check is a
first-class logged deliverable (proof it was looked at), exactly like a caught leak. Never report
"fine" without a fresh read that shows it.
