# CAPABILITY HUNT PROPOSALS 20260801 slot 5

LENS: BOUNDARY / OFF-BY-ONE -- find an inequality, window edge, timezone join or rounding step that is wrong at the boundary. Cross-source timestamp joins are the desk's repeat offender.

## A -- Claude family

Read the state artifacts, the ledger (350 rows), the gap register, and pushed the boundary lens through the data-construction, join, split and settlement surfaces. One proposal clears the bar.

---

## MISSING CAPABILITY

**Nothing on this desk audits the *payout* side of a backtest. Every leakage instrument validates the FEATURE; the return/P&L series is the axiom all of them assume. There is no test that a cash flow credited at time `t` was *earnable* by a position established after the last observation used to select it.**

## WHY IT IS INVISIBLE TODAY

The desk's leak stack is complete — and single-sided. `scripts/leakage_detector.py:78` is `audit(feature, fwd_ret, same_ret)`: all 8 contracts (suspect magnitude, contemporaneous, orthogonality, reverse causality, shift test, horizon adjacency, survivorship, constructive proof) regress the **feature** against `fwd_ret`. `libs/features/validation.py:155` "target leakage" means *the feature reads the label column* — the opposite direction. `axis_screen`'s angle-20 gate de-contaminates the **signal**. CPCV purge/embargo protects the **split**. Not one of them takes `fwd_ret` as the object under test.

That makes payout contamination not merely undetected but **anti-detected**: a P&L series crediting unearnable flows passes every instrument *more cleanly than a real edge would*, because the contamination sits in the term each test treats as ground truth. It also lands in the residual bucket — L1.47 already established that any funding phase error attributes to EXECUTION, "where R0219 is hunting a ~66bps gap it CANNOT POSSIBLY FIND THERE."

**The live boundary instance** (`libs/data/crypto_source.py:194`):

```python
daily = funding.set_index("timestamp")["funding"].resample("1D").sum()
klines["funding"] = daily.reindex(klines.index).fillna(0.0)
```

`resample("1D")` labels bins by their **left** edge, so bar `t` is credited the settlements stamped `00:00`, `08:00`, `16:00` of day `t`. Binance pays whoever is open **at** the settlement instant. Every consumer (`cashcarry.py:22`, `crypto_xsec.py`, `crypto_sleeves.py`) decides `w[t]` from `funding.rolling(k).mean().shift(1)` — information through the close of `t-1`, i.e. `00:00:00` of day `t` — then credits `w[t] * funding.iloc[t]`, whose first term settled *at that same instant*. **The funding stream runs 8 hours out of phase with the position that earns it, in the favourable direction, on the desk's only repeat-survivor family.** Real capture is `f(08:00 t) + f(16:00 t) + f(00:00 t+1)`; the model books `f(00:00 t) + f(08:00 t) + f(16:00 t)`.

Count is preserved, so this is a *phase* error, not a free settlement — which is exactly why it survived review, and exactly the L1.47 shape one layer up. The bias is second-order but **signed**, because selection and phase are coupled: `f(00:00 t)` is the settlement immediately adjoining the signal window and `f(00:00 t+1)` is a day further away, so on names selected *for extreme recent funding* the model over-credits by one day of funding-autocorrelation decay, evaluated at the extreme of the cross-section where reversion is strongest. Every round trip pays it once.

`grep -rn funding_clock` returns **one non-test consumer**: `check_funding_capture.py`, its own fence. L1.47's "import the ONE clock, never restate an interval" reached zero research code.

## MECHANISM

`libs/research/earnability.py`:
- `attributable(flows, decision_ts, entry_ts, exit_ts, latency_s)` → per credited flow, assert `settle_ts >= decision_ts + latency` and `entry_ts <= settle_ts <= exit_ts`. Returns `unearnable_bps` — bps of backtested edge from flows the position could not have held for.
- `phase_sensitivity(build_returns, panel, shifts=(-1, 0, +1))` — the metamorphic test on the payout side: rebuild P&L with the settlement→bin assignment moved one settlement, report ΔSharpe / Δbps-per-day. **A result whose sign or significance depends on a binning convention is a convention artifact, not an edge.**

`scripts/check_earnability.py`, status values `NO-DATA / UNMEASURED / UNEARNABLE-FLOW / CONVENTION-DEPENDENT / OK` — never OK on absent input (L1.41). Generalises to every discrete flow: funding, maker rebates, staking, unlock cliffs, index rebalances, airdrops.

## WHAT IT WOULD HAVE CAUGHT

R0219's ~66bps backtest-vs-realised carry gap and R0206's −51.74bps, both currently attributed to execution after the entry rule was exonerated (basis leg +0.65bps/day, t+3.11). L1.47 proved a funding phase error is *structurally invisible* in the execution bucket where both are being hunted — this is the instrument that would look in the right bucket. Adjacent and unmeasured: 48% of closes held <8h against a daily bar that has no vocabulary for "held less than one settlement."

## ROI

Direct: a correction to the measured edge of the **only deployed sleeve** — and under L1.29 an over-stated edge is an over-sized Kelly bet, not just a wrong number. Cascade: it prices the R0219 repair correctly (fixing fills to close a gap that is partly a bin convention buys nothing), and it is a general instrument for every future carry/flow candidate — the family with the desk's only repeat survivor.

## COST

~4–6h build + fence + tests. Maintenance ~0 (pure function of a flow list). Competes directly with the 48 past-due ledger rows while `conversion_status` reads REPAIR-MODE — this is a *new* build against a live repair backlog, and that is the honest argument against doing it this window.

## FALSIFIER

Rebuild `cashcarry_returns` on the existing panel with settlements assigned to the earnable phase. If |ΔSharpe| < 0.1 **and** |Δ mean| < 2 bps/day, the live instance is immaterial — build only the generic fence (~1h), not the audit. That test is one script and settles it decisively before any of the 4–6h is spent.

**NOVELTY-CHECK:** `grep -rniE "earnab|unearnab|attainab|payout.*leak|settle.*boundar|bin.edge" --include=*.py --include=*.md libs scripts docs` → zero hits on the concept (only `screen_select.py:75` "p=0 is attainable", unrelated). `grep -rn "funding_clock"` → 1 non-test consumer. `grep -rn "def audit"` → 15 audit functions, none taking a return series as the object under test. The deep-sweep "funding-settlement boundary study" (`20260726_alpha-discovery.md:298`) is the **opposite** direction — hunting an edge *at* the boundary, not asking whether the boundary manufactures our measured edge.

---

## BRAINSTORM

- **Phase-shift the funding join by one settlement and re-run every promoted carry result** — the single cheapest test of the above; produces the number that decides the build — **S** — ledger
- **`libs/validation/walk_forward.py::generate_splits` has ZERO production callers**; every `walk_forward_passed` is a **bool the caller supplies**, defaulting to `True` (`libs/stage14/engine.py:122`). A validation gate whose input is an assertion, not a measurement — **S** if stage14 is live, **B** if legacy; verify liveness first — ledger
- **`embargo: int = 0` is the walk-forward default and it only trims train-end — it never purges h-bar label overlap.** With an h-bar forward target every split boundary leaks exactly h bars — **A** — ledger (adjacency of the known-inert CPCV purge)
- **`pit_join` uses `merge_asof(direction="backward")` with `allow_exact_matches=True` and NO tolerance**: a value stamped at exactly `t` (a bar-close aggregate) joins into base row `t`, and a dataset that stopped updating in 2024 forward-fills silently forever — **A** — a fence
- **`bars_with_funding(interval="8h")` uses `reindex(method="nearest", tolerance=4h)`, which drops every settlement not on an 8h boundary** — on the 4h-interval symbols L1.47 named (the highest-funding alts), half the carry cost is invisible in 8h research bars — **A** — ledger
- **`.fillna(0.0)` makes "no funding data" indistinguishable from "funding was zero"** at every join in `crypto_source.py` — a missingness/zero boundary that biases toward free carry — **A** — a fence
- **Nothing measures the RATCHET'S DERIVATIVE.** L1.0 fires when a floor falls; a metric pinned exactly at its floor for months reads OK forever (`miner_seats_productive` current 0.0909 = floor 0.090909, status OK). Add `last_improved_at` per metric; a ratchet with no motion in N days is the "welded gate" at the boundary — **A** — a fence
- **`replacement_rate` has reported `UNMEASURED-BIRTHS` with `births: null` since it was built** — the desk's countdown-to-zero-edges metric has *never once produced a number*; write the dated promotion history it needs — **S** — ledger
- **`n_forecasts 124 / n_resolved 22`** — 82% of logged forecasts will never be graded, and the 2 "overdue" are self-answering price probes. Calibration is measured on a non-random 18% subsample; the reported `bias 0.0773` is a statistic about which forecasts were *convenient to resolve* — **A** — a fence
- **A per-edge decay half-life is computed nowhere**, so L1.30's "edges die on a half-life measured in months" has no instrument — replacement rate cannot be forecast, only observed after the fact — **A** — ledger
- **Two-leg lot-size rounding leaves a signed residual delta on every carry trade**: spot `stepSize` ≠ perp `stepSize`, so the hedge is never exact and the residual is systematically signed by the rounding rule — measure realised residual delta per round trip — **A** — a fence
- **Sub-settlement holds earn zero funding but a daily-bar backtest credits a full day** — with 48% of live closes under 8h, quantify the granularity gap between the bar the sleeve is validated on and the horizon it is traded at — **S** — ledger
- **The desk has no maker/taker *counterfactual*** — L1.45 excites *how*, but no arm ever tests "would this fill have happened at all"; unfilled maker attempts are the missing half of the Execution Reality Model — **A** — axis watchlist
- **Adverse-selection measurement on our own fills**: mark every fill against mid at +1s/+10s/+60s. A systematically negative profile is the venue reading us, and it is the cheapest crowding detector that exists — **S** — axis watchlist
- **No fence looks for CYCLES** (L1.45 found one by hand). Write the graph check: any exclusion whose *evidence for re-entry can only be generated by re-entering* is unfalsifiable by construction — **A** — a fence
- **The 4h-vs-8h funding interval is a free cross-sectional instrument**, not just a bug: Binance assigns 4h intervals to high-funding names, so `fundingIntervalHours` is an exchange-published, forward-looking stress label the desk currently discards — **A** — axis watchlist
- **`data/moat` is 7.1GB / 82% of desk data with zero screens run against it** — the largest idle asset on the box under L1.28a; one mechanism-prior screen per week beats any new collector — **S** — ledger
- **Cross-venue funding *dispersion* is measured on the 14 most-arbitraged names** (R0295 adjacency) — the mechanism lives in the tail, so the panel is selected against the hypothesis — **A** — axis watchlist
- **Hyperliquid-vs-Binance funding spread is already on disk** (`data/hyperliquid_funding.parquet`, 18,292 rows, `spread` column) and has never been screened — a same-instrument, two-venue, mechanically-forced divergence, capacity squarely in the §42 band — **S** — axis watchlist, screen-on-discovery owed
- **A "positive control" for the *payout* side**: plant a known-unearnable flow in a synthetic panel and confirm the gauntlet passes it — the desk certified its gauntlet against signal-side controls only, so the certification's own coverage is untested on this axis — **A** — a fence
- **Every fence reports level, none reports *time since last state change*** — a detector that has said OK for 60 days and one that has never run are the same artifact to `max_push`; L1.43 classifies FIRED/QUIET/NEVER-RUN but does not age QUIET — **B** — a fence
- **The `>= 10%` capacity band boundary is evaluated against a `live_book_usd` running 2.98× hot** (known measurement defect) — so the band's *edge* is mispriced even where the policy is single-sourced; the ratio and its denominator need separate freshness contracts — **B** — ledger
- **Nothing tests that two organs reading the same artifact interpret it identically** — `check_conversion` and `recommendations.py` disagree on past-due (0 vs 9) because one compares date *strings*; a cross-consumer consistency fence would catch the whole class — **A** — a fence
- **Venue-published `fundingIntervalHours`, `nextFundingTime` and `lastFundingRate` are fetched and discarded** (`crypto_source.py:144` keeps only the rate) — three free forward-looking fields dropped at the boundary of a payload already being read — **A** — ledger
- **An "assumption inventory" for every deployed sleeve**: enumerate each convention the P&L depends on (bin edge, fill instant, lot rounding, fee tier, mark source) and require each to carry a measured sensitivity. The deep proposal is one row of this table; the table itself is the general capability — **A** — ledger

I stopped here on context, not on seam. Next lines I was about to write: the settlement-phase distribution of *forced* vs *chosen* closes (L1.47 named the flag as computed-and-dropped, so the falsifier is currently unanswerable); whether `basis` in `daily_enriched` joins perp and spot closes from venues with different maintenance windows; and a cross-source check that `data/moat` L2 snapshots and the trade tape agree on sequence at the same millisecond.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
