# CAPABILITY HUNT PROPOSALS 20260813 slot 4

LENS: FOLLOW A NUMBER NOBODY OWNS -- a quantity that sets terminal wealth and is computed nowhere.

## A -- Claude family

Verified all four claims directly. Here is the proposal.

---

## MISSING CAPABILITY

**A measured TIME denominator for the screen's power figure.** `axis_screen` decides `powered` from `n_eff = len(zv) / (t_deflator × xs_deflator)`. As of two days ago `xs_deflator` is a *measurement* with a `breadth_basis` of MEASURED/UNMEASURED/SINGLE-SERIES (L1.62). On the same line, `t_deflator = float(horizon_days)` (`libs/research/axis_screen.py:185`) is a **declared constant with no basis field, no measurement path, and no way to report itself as unmeasured.**

## WHY IT IS INVISIBLE TODAY

Three layers, each individually reasonable:

1. **It cannot be flagged, because "unmeasured" is not one of its states.** `xs_deflator` carries `breadth_basis` (`axis_screen.py:203-209`); there is no `time_basis`. `grep -l "overlap_periods\|t_deflator" scripts/check_*.py` returns **nothing** — L1.62 shipped `check_panel_breadth.py` for one axis of the same fraction and there is no analogue for the other.
2. **Its only symptom is a verdict nobody appeals.** Overstating `n_eff` *understates* `min_detectable_ic` (`:212`), which flips SCREEN-UNDERPOWERED → **SCREEN-WEAK**. That is the desk's "tested and refuted", graveyard-grade. L1.62's own text names this exact direction as "the false-null direction no other gate catches" — and closed it on the cross-section only.
3. **The desk already wrote the finding down and left it local.** `scripts/screen_venue_subsidy.py:576-579`, verbatim: *"A fee tier is highly persistent, so the signal's serial correlation is severe and is NOT deflated here — this power figure is an UPPER BOUND and the true effective sample is closer to the number of TIER CHANGES than to the number of days."* One screen confessed in prose. Nothing generalised it, measured it, or fenced it. A duty with no instrument is a wish (L1.46).

## MECHANISM

`libs/research/panel_breadth.py` already materialises the product matrix `m` of pooled-IC summands (`:182`) to measure `xs_neff` across columns. Measure serial dependence **down** that same matrix in the same pass:

- New `measure_panel_persistence(m)` → lag-1 ρ of the summands over dates, `t_neff = n_dates·(1−ρ)/(1+ρ)`. The instrument already exists and is live elsewhere: `print_impact._ar1` + `effective_n` (`libs/research/print_impact.py:300-335`, daily via `daily_research_cycle.py:143`). **Upgrade-before-build (L2.9), not a new estimator.**
- `axis_screen` gains `time_basis ∈ {MEASURED, ASSUMED-OVERLAP, UNMEASURED}` beside `breadth_basis`, and `t_deflator = max(horizon_days, measured_dependence)`.
- **`powered` requires `time_basis != UNMEASURED`**, exactly as L1.62 requires it of breadth. Absence resolves to the tighter answer, never a clean one (L1.28a).
- Fence `scripts/check_time_denominator.py` → `data/time_denominator.json`, statuses `MEASURED / PARTIAL / UNMEASURED / OVERCLAIMED`. Only OVERCLAIMED (a `powered:true` or SCREEN-WEAK on an unmeasured time basis) fails; coverage below 100% reads PARTIAL and exits 0 — a ratchet whose gap is the work queue, because a fence red on day one gets switched off (L1.43).

## WHAT IT WOULD HAVE CAUGHT

L1.62's first run, **2026-08-13 — two days ago** — "converted 29 SILENT SCREEN-UNDERPOWERED cells into graveyard-grade SCREEN-WEAK refutations." Every one of those 29 was minted from an `n_eff` whose time denominator is the constant `horizon_days`. The signals involved are persistent by construction (`z20` is a 20-day z-score; `stablecoin_supply_momentum`, `defi_utilisation`, OI levels, fee tiers). A graveyard entry is **permanent** (L1.17) and the novelty gate then blocks that ground forever through a deliberately narrow door (L1.16a). Also standing: `libs/validation/type2_cost.py` — `autocorr_deflator` has **zero callers**, and the single `effective_years(` call site (`:541`) passes no `deflator=`, so the Type-2 power model runs at 1.0 across seven live screens.

## ROI

Direct: stops permanent, irreversible retirement of live search space on an unmeasured denominator — the one error class that destroys *future* edges silently and forever. Cascade: `powered` gates SCREEN-WEAK, which gates the graveyard, which gates the novelty gate, which gates what may ever be re-tested. It multiplies the whole Stage-A funnel, and it is the false-null direction — the direction L1.25a exists to prevent the desk from mistaking for "alpha does not exist here."

## COST

~4-6h. The matrix is already in hand; the estimator is already written and live; the fence follows `check_panel_breadth.py` line for line. Maintenance ≈ zero (one more basis field). Competes with R0566 (DSR/PSR autocorrelation deflation) — **same family, different organ**: R0566 tightens a p-value in `libs/validation/dsr.py`; this refuses a *refutation* in `axis_screen`. Do this one first: a wrong p-value costs a trial, a wrong graveyard entry costs the ground.

## FALSIFIER

Run `measure_panel_persistence` on the desk's own 139-symbol futclose panel **before building the fence**. If the measured lag-1 ρ of the *product terms* is ≈0, `horizon_days` is already sufficient and this is not worth building. This is the honest objection and I will not hide it: the summands are signal×target, and a near-white target can decorrelate a persistent signal. L1.62's own falsifier corrected its proposal's number (product-term breadth, not return breadth) — the same measurement must run first here. Note the claim survives either way in weaker form: the defect is that the basis **cannot be reported at all**, not that the number is presumed wrong.

**NOVELTY-CHECK:** `grep -l "overlap_periods\|t_deflator" scripts/check_*.py` → empty (vs `check_panel_breadth.py` present); `grep -rn "effective_years(\|autocorr_deflator" libs/ scripts/` → declaration sites only, no caller passes `deflator=`; ledger scan of 576 rows — R0566 is `libs/validation/dsr.py`, R0461(c) is a methods shelf item, GAP #44 is the forward funding panel, R0086 is DSR's `n_eff`; **none names `axis_screen`'s time deflator.**

---

# BRAINSTORM

1. **`type2_cost.autocorr_deflator` is dead code** — `effective_years` permanently 1.0 across 7 live screens (`screen_venue_subsidy`, `screen_orderbook_state`, `screen_vol_risk_premium`, `screen_primary_market_flow`, `announcement_diffusion`, `unlock_supply_series`, `run_type2_report`) — **S** — ledger, one-line wiring.
2. **`run_wealth_report.py` has never run and structurally cannot** — all 8 inputs (`nav_path.json`, `conversion_records.json`, `sample_geometry.json`, …) absent with **no producer anywhere in the repo**, yet `wealth::board_question` is max_push rank #1 and prescribes "run it" daily — **S** — the queue's own #1 row.
3. **Nothing checks that a max_push `next_action` is executable** — an unreachable remedy makes a row immortal at rank #1 and absorbs the top of the work queue forever (L1.49 applied to remedies, not gates) — **A** — new fence.
4. **The compounding frequency is capped at 1/day, not 600s** — `_compounded_capital()` re-sizes every 10 min but reads `realized_spot_pnl` from `nav_attestation.jsonl`, written once daily; both current rows carry identical `2921.35` — **A** — ledger.
5. **`_NAV_STALE_DAYS = 2.0` falls back to `DEFAULT_BOOK_USD = 50_000`** — a 48h-stale NAV sizes the book against ~3× its real value; the fail-direction is *dangerous*, not conservative — **S** — money path, check against R0539.
6. **The book's own PnL autocorrelation is never computed** — five ρ implementations exist, all aimed at research candidates; `vol_headroom.from_nav_chain` is the sole consumer of the book's return series and has no ρ term, so its Sharpe and vol are uncorrected — **A**.
7. **Executor downtime is never integrated into a rate** — all 8 heartbeat consumers treat it as binary alive/dead; no fraction-of-calendar-deployed exists anywhere; "time-in-market" has zero occurrences in 576 ledger rows and 130 aspects — **A**.
8. **`strategy_pool.market_exposure_fraction` exists, commented "THE FIELD THIS DESK DID NOT HAVE"** — its input `data/strategy_pool.json` is ABSENT, so the field the desk built to fix this is unfed — **A** — wiring.
9. **Nobody multiplies queue depth × latency × decay** — 71 candidates against 12 slots at a measured 181-day pipeline; `conversion_velocity.economic_waiting_cost()` prices exactly this and its only caller is the report that has never run — **S**.
10. **`capacity_race` compares latency to CAPACITY runway, never to ALPHA-DECAY runway** — two different half-lives; capacity erodes as equity grows, alpha erodes as the world learns, and in crypto the second is far faster — **S** — the DOA verdict is computed against the wrong clock.
11. **`cohort_independence.measure` has zero production callers** — the desk built the "how many independent bets is this cohort actually making" instrument, benchmarked it against a published 101-alpha study, and never pointed it at a live cohort — **A**.
12. **15 concurrent forward clocks all started inside a 17-day window** (2026-06-21→07-08 standing, 07-24→08-02 axis); Holm's `m` assumes independence and there is no dependence field anywhere in `forward_slots.json` or `axis_shadow_state.json` — **A** — partially owned via R0338/R0480.
13. **`desk_economics` publishes `hurdle_acceptable: true` from a 100%-undeclared cost base** — all four line items (`vps`, `llm_subscription`, `llm_api`, `domains_misc`) are `null`, so the hurdle is $0.00/yr and reads as health — **A**.
14. **Two organs, one paper book, opposite honesty policies** — `run_growth_audit` refuses to price it (`UNMEASURABLE-PAPER-BOOK`) while `desk_economics` computes a hurdle against the same $17,732 paper equity without refusing (L1.61 class) — **B**.
15. **No data-driven block length anywhere** — every stationary/moving-block bootstrap hardcodes `mean_block` 5 or 10, across Reality Check, Romano-Wolf, per-candidate, track record and portfolio Monte Carlo — **B**.
16. **`statsmodels` is a declared dependency and HAC is never used** — only `adfuller`/`coint` in `stationarity.py`; no `cov_type='HAC'` repo-wide — **B**.
17. **`effective_sample.py`'s six deflators are dead**, including the only `REGIME_CONCENTRATION` implementation — fed by `sample_geometry.json`, which has no producer (already on COMPLETION_LEDGER:2167) — **A**.
18. **`event_density.event_clock` is dead** — five live shadow runners import only `forward_verdict`, which uses raw `n_obs` — **A**.
19. **`evidence_clock.regime_penalty` is welded at 0.5** — its only live caller hardcodes `distinct_regimes=0` — a gate that can never move (L1.43) — **A**.
20. **R0173 deleted the `two_regimes` gate as unmeasurable and nothing measurable replaced it** — the regime count of the evidence base is genuinely unowned, and the register's only regime flags are binary "≥1 event" — **S**.
21. **`target_horizon_sweep` passes neither `xs_neff` nor `overlap_periods`** — every cell through that entry point is `breadth_basis: UNMEASURED` *and* deflated by full `h`; it is also the duty-mandated sweep path — **A**.
22. **`axis_screen`'s numerator `len(zv)` is symbol-days, never dates** — the date axis is never materialised; `panel_breadth` captures `n_dates` at `:150` and uses it in no calculation — **A**.
23. **P(operational termination) is uncomputed and every rail is a market-ruin rail** — the desk's realistic death is a lapsed API key, an unpaid VPS or the principal stopping; the GPT-9 seat's `402 Payment Required` is an *observed partial death* with no cost line — **S**.
24. **No discount rate and no horizon T** — E[log W_T] is parameterised by T, and every cross-horizon ERV comparison (L1.14/L1.15) is therefore incommensurable — **B**.
25. **The opportunity tape does not exist** — available funding across the universe over time is never recorded, so a rail latch's cost has no numerator; crucially, that numerator needs **no live book** and would falsify the standing `UNMEASURABLE-PAPER-BOOK` refusal on its available-edge half — **S**.
26. **Reinvestment lag is never measured** — nothing records "PnL realized at T, entered the sizing base at T+x"; no `deploy_lag`/`reinvest_lag` identifier exists — **A**.
27. **`realized_log_growth` returns a bare float with no standard error** — the desk's supreme objective, when finally computed, will be a point estimate with no way to tell it from zero; the SE machinery exists in `ensemble_gate.py:654` and is never pointed at `g` — **S**.
28. **`paper_sleeve_forward.py:169-181` is the only place honouring both distinct timestamps and serial correlation** — generalise it; also check its `dependence = max(overlap, autocorr)` — two independent dependence sources arguably compound rather than max — **A**.
29. **Single-venue counterparty concentration** — the Bybit spec exists and is unbuilt; this is the FTX death and no metric tracks it — **A** — tier1 `venue_breadth_counterparty`.
30. **`min_detectable_ic = 1.96/√n_eff` carries no multiplicity** — the power floor uses an uncorrected two-sided 5% while the screen runs hundreds of cells; the power bar and the significance bar disagree — **A**.
31. **The UNMEASURED path is asymmetric inside one expression** — `xs_deflator` keeps the conservative full-K on absence; `t_deflator` has no conservative fallback because it has no concept of absence — **A** (the deep proposal's narrower sibling).
32. **`screen_idle_axes` double-deflates by `h`** (declared, safe direction) — but its power figures are then not comparable to any other screen's, so cross-screen "which axis is best powered" rankings are apples-to-oranges — **B**.
33. **The de-contamination angle-20 gate is a low-pass filter** (recorded lesson) — "price-only alpha is dead" was only ever a claim about *slow* daily-resolution price alpha; sub-daily price space has never been screened — **S** — axis watchlist.
34. **MARKOUT is absent** (R0249 scheduled) — adverse selection on the desk's own fills is unmeasured, and it is the term that turns a positive gross edge negative at scale — **A**.
35. **`_COMPOUND_FRACTION` clamps at 0.5–4.0×** — an unexamined pair of constants directly on the compounding path, with no derivation in the repo (the `DEFAULT_HAIRCUT_BPS=300` pattern) — **B**.
36. **The only options dataset is an executor side-effect** — ~1 obs/day with 15 gaps >24h in 35 days; `collect_deribit_surface` should be hourly and decoupled — **A** — tier1 `vol_surface_expertise`.
37. **Principal key-person risk (GAP #55) has no metric** — the desk's single largest point of failure is tracked in prose only, while every $1.34/day clamp is priced to the cent — **A**.
38. **`gate_calibration.would_have_paid` measures gate over-strictness** (the leak rate of rejects that later cleared the deploy bar) — verify it is live and fed; an over-strict gate loses real edges silently and that is the L1.43 welded-gate question pointed at the *reject* side — **A**.
39. **Nothing measures the desk's own base rate π₁** — the fraction of candidates entering forward confirmation that are genuinely real; without it a Holm-cleared p-value carries no probability, and every frequentist gate is unconditional on it by construction — **S**.
40. **Ask of every meter: what does its absence look like?** — L1.51 found trade-driven meters cannot see a flat book; generalise that as a standing review question and sweep every artifact whose "healthy" and "no data" renderings are byte-identical — **A** — self-interrogation patterns file (L1.31 recursion rule).

Next, had I more context: the LLM-seat spend ledger as a first-class cost line (item 13's missing input, and the `402` in item 23 is its first measured data point); whether `_breadth_deflator`'s clamp interacts with the time deflator multiplicatively in a way that can drive `n_eff` below 1 and hit the `max(..., 1.0)` floor silently; and an audit of every `max(a, b)` used where `a×b` is the correct composition of two independent discounts.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
