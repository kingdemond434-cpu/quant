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

**THE TARGET, STATED IN FULL (principal, 2026-09-05).** `max E[log W]` is the whole objective, and
the deductions in `C` are not a footnote to it — each one is a place where a growth number that
ignores it is simply wrong:

| charged against growth | why it is inside the objective, not beside it |
|---|---|
| costs | commission, spread and swap are paid on every unit of size; an uncosted optimum sizes a quantity the desk cannot buy |
| slippage | the fill, not the signal, is what compounds — measured, never modelled flat |
| uncertainty | the posterior, not the point estimate: sizing on an overestimated edge is how Kelly kills accounts |
| correlation | four sleeves that are one bet lose like one bet at four times the size |
| tails | ruin is absorbing, so a growth rate conditioned on surviving is the only one that means anything |
| capacity | `d(cost)/d(size)` — an edge that dies at size is an edge at that size only |
| turnover | churn pays the spread repeatedly for the same idea; the fitness shape penalises it |

Anything that reduces exposure must price itself against that objective (rule 1). Anything that
raises exposure must be supported by it (rule 2). There is no third criterion.

### The four terms of the growth identity

Compounding enters through exactly four inputs, and an organ hunting one while three sit
unexamined is polishing a wall, not pushing a ceiling:

| term | symbol | what moves it |
|---|---|---|
| independent bets | N | more uncorrelated sleeves — the only term with a square-root law behind it |
| hit rate | p | better entries and better filters |
| winner shape | W/L | exits, trail width, and how far a winner is allowed to run |
| size | f | the heat actually deployed |

**SIZE IS THE ANTI-LEVER, and it is the one dial where "uncap it" and "achieve it" point in
opposite directions.** Growth rises with size only up to full Kelly and FALLS after it; the odds
of a doubling year peak earlier still. Its gradient past the optimum is NEGATIVE, so it is
`HELD-BY-ARITHMETIC` — held for a reason that is arithmetic, never caution, so that holding it is
not re-litigated as timidity under rule 1. This is exactly why `heat_policy.measured_ceiling`
refuses to bound above the point where the measured growth curve turns over: past that point,
more size buys less wealth.

*(Recorded here 2026-09-05. These two statements used to be fenced against
`scripts/run_discretionary_max.py`, an organ of the retired crypto-exchange desk, deleted with it.
The claim is a law about compounding rather than a property of any one organ, so it lives with the
mandate now.)*

**Anti-timid research, evidence-hard capital.** Ingestion accepts almost any legal public
mechanism, including weak and anecdotal claims (graded, never privileged). Research mutates,
combines and tests them aggressively. Capital is granted by evidence alone: nothing gets
authority because it sounds institutional, came from a famous fund, or has a nice backtest.
Source reputation is a prior, never proof.

## The heat law, as wired

* The utilisation floor is **20% (HEAT_TARGET), flat, 24/7**, and it is a STANDING MANDATE. It
  does not ramp with readiness; readiness is measured and reported, never gating.
* **The fixed 30% ceiling was REMOVED on 2026-09-05 by principal order** — *"if growth optimum
  permits 32 35 40 45 wtv in future w new edges etc it can use those w 20 as minimum floor"*. The
  bound above the floor is no longer a constant. It is **measured from the growth curve every
  pass** by `desks/mt5/research/heat_policy.measured_ceiling`, and it moves BOTH ways: when new
  edges lift the curve and it still climbs at 42%, the allocator may deploy 42%; when the
  opportunity set is thin, the bound comes in below 30% and holds the book tighter than the old
  constant ever did. `H_actual = clip(H*_robust, HEAT_TARGET, measured_ceiling(curve))`.
* Deleting the old constant outright would have been the wrong reading of that order, and the
  constant says why: `HEAT_HARD_CEILING = 0.30` was never a round number somebody liked. It
  records a measurement from 2026-09-02 across 256 sampled worlds on the 109-sleeve matrix, where
  the robust score ran +0.00133/day at the free optimum, +0.00072 at 20%, +0.00011 at 25% and
  **negative at 30%**. On that book, 30% already destroyed wealth. It survives as the recorded
  FALLBACK for when the curve cannot be read.
* Three properties keep the measured bound on the aggression side of gambling:
  **never past the last measured point** (42% must be sampled before 42% can be deployed — the
  bound follows evidence, never extrapolation); **never where growth has turned** (the bound is
  the last heat still within tolerance of the peak rate and still positive); and
  **absence is never permission** (too few points, an unreadable curve, or a non-positive peak
  all fall back to the recorded constant or to the floor — a monitoring gap must never read as
  "unlimited").
* **The floor's growth cost is MEASURED every pass, not assumed.** `heat_policy.heat_accounting`
  writes the unconstrained optimum, the robust optimum, what was deployed, which bound bit
  (`floor_binding` / `ceiling_binding`), the ceiling's stated reason, and — when the floor was
  the thing that bit — `growth_cost_of_floor_per_day` and `_per_year`. A floor nobody audits is a
  belief; a floor whose price is on the dashboard every pass is a decision, with the evidence
  standing by to overturn it if it turns out to be wrong.
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
| static heat cap | same cap regardless of opportunity | the cap IS the opportunity: `heat_policy.measured_ceiling` reads it off the growth curve each pass; `hard_ceiling` rail billed |
| the 20% floor itself | a mandate that quietly costs growth | `heat_accounting` prices it every pass (`growth_cost_of_floor_per_day/_per_year`) |
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
