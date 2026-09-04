# Growth governance (binding, principal order 2026-09-04)

Two rules, applied everywhere, now and in future. They are enforced by
`scripts/check_growth_governance.py` at every law-gate boundary (organ spawn, push, CI, hourly)
and by `scripts/check_heat_floor_wiring.py` on the box.

> **Rule 1.** Every risk reduction mechanism must prove that it increases robust forward E[log W].
>
> **Rule 2.** Every strong opportunity must be allowed to increase capital above normal when the evidence supports it.

## What they mean

**Timid is not risk-aware.** A timid system says "risk looks scary, therefore size smaller".
This desk says "take as much risk as the evidence, diversification, execution quality and ruin
probability justify, and take more when the opportunity set is unusually strong". The objective
is

    max_h  E[ log(1 + h'R - C) ]     subject to  P(ruin) < eps,  P(broker stop-out) < eps_s

and nothing else: not volatility, not a pretty drawdown, not Sharpe, not "avoid losing trades".
Drawdown matters only through future geometric wealth and survivability.

**Anti-timid research, evidence-hard capital.** Ingestion accepts almost any legal public
mechanism, including weak and anecdotal claims (graded, never privileged). Research mutates,
combines and tests them aggressively. Capital is granted by evidence alone: nothing gets
authority because it sounds institutional, came from a famous fund, or has a nice backtest.
Source reputation is a prior, never proof.

## The heat law, as wired

* The utilisation floor is **20% (HEAT_TARGET), flat, 24/7**. It does not ramp with readiness;
  readiness is measured and reported, never gating.
* Growth is **free above the floor to the 30% catastrophe ceiling** (HEAT_HARD_CEILING): if the
  robust E[log W] optimum says 23%, the book runs 23%; if it says 30%, it runs 30%.
* The resolved heat is **filled, never reported short**: when per-sleeve bounds cannot fund it,
  the bounds yield in order (drawdown leg, mechanism cap, share cap, proportional scale) and each
  relaxation is billed to that rail by the missed-growth ledger.
* The gateway **deploys the allocator's fractions un-re-shrunk** (`promoted_lot(from_book=True)`:
  no 3% floor clamp, no authority ramp on top of a posterior that already shrinks by evidence)
  and, when the proof certificate is stale or failed, sizes the floor with the **best baseline
  at the same total heat** (`book_fallback`) rather than with nothing.
* The **only** layers permitted below the floor are integrity kill switches (broker down, stale
  quotes, unreconciled exposure, margin anomaly) and the ruin guard (a book wiped out in a
  sampled world). Both are registered rails and both are measured.

## Modifiers are two-sided

Every capital modifier in `libs/portfolio/capital_modifiers.REGISTRY` must be able to say
BOOST as well as REDUCE. The AI capital modifier emits STRONG_VETO / REDUCE / NORMAL / BOOST /
STRONG_BOOST and each category must prove its increment out of sample (`CAPITAL_MODIFIERS.json`).
A state that makes a sleeve abnormally good gets more capital, subject to portfolio interactions.

## Every rail pays rent

`libs/portfolio/rails.py` registers every veto, gate, shrinkage, cap, inertia threshold and
kill switch. `research/missed_growth.py` bills each one daily:

    OpportunityCost(rail) = E[log W without rail] - E[log W with rail]

A rail that persistently COSTS_GROWTH is weakened within its declared bounds (tunable rails:
position inertia, state shrinkage) or queued for removal (binary rails). A rail is never
strengthened by this loop. The Aggression Governor (`libs/portfolio/aggression.py`) audits every
pass and names UNUSED_UPSIDE whenever growth wanted more, the Kelly surface bore it, and the book
got less.

## Where timidity would hide, and what watches it

| Component | Timid failure | Watcher |
|---|---|---|
| static heat cap | same cap regardless of opportunity | growth free to 30%; `hard_ceiling` rail billed |
| state shrinkage | shrinks a real emerging edge | `state_shrinkage` rail, admission t-stats |
| hard vetoes | binary where sizing would do | vetoes replayed by `counterfactual_markout`, billed |
| factor concentration | estimate uncertainty blocks | `factor_k_floor` rail |
| proof certificate | stale cert forces old sizing | `book_fallback` deploys the floor regardless |
| position inertia | misses fast regime change | `position_inertia` rail, calibrated down when it costs |
| cost stress | 2x cost used live | live allocation charges measured cost only (`cost_stress` rail) |
| all gates must pass | one weak gate blocks | gate value measured in the funnel; graveyard model |
| fixed fractional Kelly | tiny fraction despite evidence | posterior sizing on worlds; Kelly surface reported |
| cash preference | thresholds too hard | `floor_mandate` rail: 20% is deployed 24/7 |

### Accidental timidity found and removed (2026-09-04)

- **The daily reopen refused every hold of a day or more on gold.** `proposer_common.screen`
  treated the bar after the daily trading gap like a marked rollover print and refused any trade
  whose window contained it, so a 23-hour instrument could never be proposed on a daily horizon:
  the style-premia and tail-diversity sweeps reported zero tests on XAUUSD for that reason alone.
  Measured: the reopen gap is unsigned (t = +0.99) while the reopen bar's open-to-close is +2.7bp
  on the bid (t = +5.6) as the spread normalises. So a FILL at the reopen stays refused (it books
  the spread reversion as edge) and now waits for the next clean open, a one-bar exit onto the
  reopen stays refused, and holding THROUGH the reopen is allowed, because the gap is real
  exposure in both directions. Marked opens (finite t) are unchanged. Result: 28 style-premia
  tests on gold and silver where there were none. A refusal that only ever removed candidates and
  never proved a growth gain is exactly the class rule 1 exists to catch.

## What is reckless, not aggressive

Forcing trades with no edge, maximising leverage, ignoring correlations, sizing from backtest
expectancy, bypassing out-of-sample evidence because an edge looks amazing, adding leverage to
make weak alpha hit a return target. None of these maximise long-run growth and none are
licensed by these rules.
