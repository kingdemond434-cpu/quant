# CAPABILITY HUNT PROPOSALS 20260806 slot 3

LENS: DATA ASYMMETRY -- information that could exist ONLY because of how WE combine data (our own-timestamp L2, our execution tape, cross-source joins). What proprietary feature is a competitor structurally unable to buy? (L1.11a: rank by reconstruction cost.)

## A -- Claude family

Verified end to end. Here is the finding.

## MISSING CAPABILITY

**A fill-probability model in TIME — P(fill | wait) estimated from our own resting quotes.** The desk is already running a pre-registered randomised experiment on the wait axis and paying for it; its Execution Reality Model has no time parameter, so the one experiment the desk actually runs is the one its estimator cannot consume.

## WHY IT IS INVISIBLE TODAY

`identifiability()` (`libs/execution/passive_impact.py:381`) asks exactly one question: is there variance in `_OFFSET_FIELDS = ("quote_px","placed_px","quote_offset_bps","spot_quote_px","fut_quote_px")` — the *distance* axis. It finds none (we always quote at the touch), returns `UNIDENTIFIED`, and names the remedy: "needs an OFFSET ARM in the excitation design." That verdict is honest and it is about the wrong axis.

`data/excitation_design.json` arms are `{baseline: 240.0, medium: 60.0, brief: 15.0}` — **`maker_wait_s` only**, ε=0.25, capped at $2,000/day. Meanwhile `fill_probability_curve(distance_bps, *, lam_bps, p0)` takes **no time argument**, and `data/passive_impact.json` carries `rest_seconds: 15.0` as a **hardcoded constant** baked into how `fill_prob` was computed.

The generalisation, which is the real prize here:

> **An identifiability check built from the model's own variable list cannot report an omitted variable.** It answers "can I fit the model I wrote?" and is read as "can this be learned?" Every `UNIDENTIFIED` verdict on this desk is conditional on a specification, and none of them say so. L1.41 has since installed refusal paths desk-wide, so this defect class is now systematically replicated.

The falsification is already on disk, in two artifacts regenerated hours apart, and **nothing reads both** (verified):

| artifact | quantity | value |
|---|---|---|
| `data/passive_impact.json` | model P(fill at touch), **15s**, self-labelled UPPER BOUND | **8.08%** |
| `data/fill_quality.json` | realised maker rate at touch, **240s** open wait | **60.0%** (18/30, CI [42.3, 75.4]) |

7.42×, and the CI excludes the "upper bound" by a wide margin. The honest reading is not "the model is wrong" — it is that **the gap IS the omitted axis**, and the UPPER-BOUND label silently inherits the frozen 15s constant. (Caveats stated: n=30 is thin, and the counterfactual basis spans 45 symbols vs the traded book. Neither weakens the point — the *absence of the comparison* is the defect.)

## MECHANISM

1. **Capture the covariate that already arrives free.** `binance_live/testnet/spot_live/spot_testnet.book_ticker()` parse `bidPrice`/`askPrice` and discard `bidQty`/`askQty` — **zero occurrences repo-wide** — in the very call `_maker_pair` makes one line before placing the quote (`run_cashcarry_executor.py:1506`). Add `book_ticker_full()`; leave the existing 2-tuple signature untouched.
2. **Stamp the placement record onto the tape**: `{quote_px, touch_px, queue_ahead_base, t_place, t_resolve, outcome, exc_arm}`. `_maker_pair` already computes the outcome and throws it away (line 1546-1548) — L1.47's "a flag computed and dropped is evidence destroyed at zero saving."
3. **Add the time axis**: `fit_fill_survival(wait_s, queue_ahead, outcome)` → P(fill | t, Q), a survival curve per symbol. Wait variance comes free from the three excitation arms; **queue-ahead variance comes free from other market participants — no new arm, no new operating point, no incremental risk.**
4. **Extend `identifiability()` to a per-regressor verdict** — `{offset: UNIDENTIFIED, wait: OK, queue: OK}` — instead of one scalar. Fence status: `OK / UNDERPOWERED / UNIDENTIFIED(per-axis) / SPEC-INCOMPLETE` where the last fires when an excitation arm varies an axis the model has no parameter for.
5. **Reconcile**: one artifact comparing modelled vs realised fill probability at the operating point actually used. Feeds `libs/backtest/queue_fill.py` — a real hftbacktest-derived queue model with **zero callers, whose `queue_ahead` is a parameter with no estimator anywhere.**

## WHAT IT WOULD HAVE CAUGHT

R0267 (disposed **implemented**, 2026-08-06) concluded from its own tape that own-fill identification "needs an OFFSET ARM, not more fills." That prescription adds a new operating point with real execution risk and a larger excitation budget — while the desk was *already buying* variance on a second axis the model had no slot for. A per-regressor identifiability check would have printed `wait: OK` on the day R0267 shipped and redirected the remedy to a free one. This is L1.14 exactly: the higher-EV alternative was cheaper, safer, and already funded.

## ROI

Direct: `_MAKER_WAIT_OPEN = 240.0` governs every open on the only deployed sleeve, whose loss is **88.3% fees, not thesis**. It is set by neither half of the trade-off — `run_cost_identification.py` measures `causal_wait_slope_bps_per_s` (the *cost* of waiting) and nothing measures the *benefit*. Cascade: it deepens `own_execution_fills`, the one EXCLUSIVE-class asset sitting at **depth 0** in `data/asymmetry_ledger.json` — and the ledger's own scoring says a proposal adding a new source instead of deepening this one **scores negatively by construction**. It gives `queue_fill.py` its missing estimator (sim-prod parity T2→T1), and `queue_position_estimate` — the highest-ranked manufacture spec at REC 3.24 — its first ground truth. Unbuyable by construction: no venue sells "how long Quant Desk's quote rested and whether it filled."

## COST

~6-8h. Four one-line connector additions, one tape-field extension, one survival fit, one fence change. No order behaviour changes, so **L1.38 sterile-cockpit does not bind** (instrumentation, not a money-path improvement). Competes with R0058 (ERM, due 08-12) — which it belongs inside; R0058's declared content is *TCA coverage*, i.e. fill-conditional by construction, structurally blind to non-fills.

## FALSIFIER

Fit P(fill | wait) on the accumulated tape: if the 15s/60s/240s arms are statistically indistinguishable, wait is not a live knob and 240s is as good as 15s — build nothing. Equally fatal: if realised maker rate is ≥95%, there is no decision to improve. Current 60% [42.3, 75.4] says otherwise but is thin; **the honest first step is powering the measurement, not the model.**

**NOVELTY-CHECK:** `grep -rl fill_quality --include=*.py libs/ scripts/ | xargs grep -l passive_impact` → empty (nothing reconciles the two). `grep -n "_OFFSET_FIELDS\s*=" libs/execution/passive_impact.py` → distance-only vocabulary. Ledger scan of 436 rows for `maker_wait|time-to-fill|fill probability|P(fill` → **1 hit, R0267**, whose remedy is the *offset* arm. `grep -rn "bidQty\|askQty" --include=*.py libs/ scripts/` → **zero**.

---

## ⚠ THREE LIVE DEFECTS FOUND EN ROUTE — these outrank the proposal

1. **P0, irreplaceable data being lost right now.** All three recorders contain the L1.46 clock-provenance code, but the running processes (PIDs 3242010/11/12, started 2026-08-05 02:50:07) loaded it ~3 min before the source files were written (mtime 02:53). On disk: `zcat data/moat/fut/BTCUSDT/20260806_01.jsonl.gz | grep -c '"c":'` → **0**; same for `"E"`, and `"vt"` on Bybit. Since 2026-08-05 03:00 every GB of tape accrues **without the venue stamp**, so Δ = t_recv − t_venue — the series L1.46 calls "structurally unbuyable" — is not being captured at all. This is the desk's #1 lesson class (stale-code daemon); `scripts/ship_restart.py` exists for exactly this. `ops/start_recorders_nosudo.sh` starts only what is *down* and will **not** fix it.
2. **Gate-0 evidence reads a fixture.** `data/moat/execution_tape/cashcarry_trades.jsonl` lines 526-527 are synthetic (`OLDUSDT`, `closed: 2020-01-01`), so `coverage()` returns `days: 2404.91` against a real span of 30.7d. The Gate-0 criterion is "≥4 weeks of live fills." `check_gate0_ready.py:66` happens to read `n`, not `days` — the protection is an accident. Tape also stale since 2026-08-01 21:55.
3. **The moat-utilisation meter has never produced.** Cron `56 5 * * *` is installed; neither `data/moat_utilisation.json` nor its log exists. The one measurement answering "what fraction of the 11GB moat has ever been read" is silent — which is why the write-only list below went undetected.

---

## BRAINSTORM

- **`bidQty`/`askQty` capture** — zero repo-wide; it is the `queue_ahead` estimator `libs/backtest/queue_fill.py` was written to need — **S** — ledger
- **Bybit `meta` rows carry `fr`, `oi`, `mp`; only `fr` is ever read** — two free proprietary series already on disk — **S** — ledger
- **We write a free 240s option to the market** — a visible post-only quote at the touch *is* an option; adverse selection is its premium and nobody has priced what we give away — **S** — ledger
- **Recorder universe is selected on what we traded** — L1.45's never-traded⇒never-recorded⇒never-measured cycle, one layer down at the data tier — **S** — GAP_REGISTER
- **`venue_latency_asymmetry`** — ranked FUSE, REC 3.04, ranked/costed/written down, **zero references repo-wide** — **A** — ledger
- **`inventory_stress_proxy`** — same: ranked, never written — **B** — ledger
- **WebSocket recorders instead of REST poll** — ~100× resolution, and it retires R0117's poll-phase-alias refutation rather than accepting it — **S** — ledger
- **Liquidation listener discards our recv clock** — WS delivery latency permanently unmeasurable on 58,983 rows — **A** — ledger
- **L2 × liquidations join** — `screen_liquidation_reversion` joins liquidations to *trades*, never to *depth*, despite "large relative to resting depth" being its own stated mechanism — **A** — axis watchlist
- **Identify our own prints in the public tape** — self-labelled exogenous flow, a known treatment for impact estimation nobody else can construct — **A** — ledger
- **No order-lifecycle events anywhere** — no submit/ack/amend/cancel/partial, no client or venue exec IDs — **A** — ledger
- **Venue `amend` (`PUT /fapi/v1/order`) preserves queue position** — free execution upgrade over cancel+replace — **A** — ledger
- **Binance spot depth (531MB)** — the only stream with no free daily substitute, never once named as a moat asset — **A** — asymmetry ledger
- **Graveyard as a *fitted* prior** — `_PRIORS` in `alpha_economics.py` is a hand-written literal; the desk's own 420-trial record is EXCLUSIVE depth-4 and unbuyable — **S** — ledger
- **The declined-trade tape** — shadow P&L of every entry the rails blocked prices clamps *without* live capital, closing L1.51's UNMEASURABLE-PAPER-BOOK refusal — **S** — ledger
- **`moat_series.jsonl` (33MB) write-only** — the mined microstructure measurements feed nothing — **A** — max-push
- **`perpdex_funding.jsonl` (33MB, 182k rows, 5-year span) write-only** — deepest history on the box, zero consumers — **A** — axis watchlist
- **`bybit_ob200_20250821.zip` (149MB) downloaded 2026-08-05, never opened** — zero references of any kind — **B** — ledger
- **Excitation budget essentially unspent** — `exc_arm` on **1 of 531** tape rows against a $2,000/day declared cap; L1.28a idleness on the desk's only identification instrument — **S** — fence
- **`data/cost_identification.json` does not exist** — the *cost* half of the wait trade-off has never produced either — **A** — ledger
- **Fill-quality coverage is 5%** — 475 of 500 rows unmeasurable; the maker-rate denominator is 30 (L1.57) — **A** — fence
- **No fee field on any fill (0/500)** — fees are 88.3% of the sleeve's loss and are UNMEASURED, not zero — **S** — ledger (R0371 open)
- **Fill probability conditional on funding phase** — L1.47's clock × execution: liquidity and adverse selection are not phase-invariant near settlement — **A** — axis watchlist
- **Symbol-level fill heterogeneity** — route size toward names where maker fills are cheap; currently one global 240s constant for all — **A** — ledger
- **Persist the executor's existing jitter draw** — a free instrumental variable for latency→fill-quality, already computed and discarded — **A** — ledger
- **Cross-venue L2×L2** — three venues recorded on deliberately identical schemas ("so downstream loaders treat both identically") and no downstream loader ever does — **A** — ledger
- **Delta-encode the Bybit depth tree** — ~10× retention on the 9GB that is 82% of the moat — **B** — ledger
- **Markout (R0249) is the cost half of the same trade-off** — pair it with P(fill|wait) or neither is decision-grade alone — **A** — ledger
- **`libs/execution/tca.py` `PostTradeTCA`/`SlippageAttribution`** — built, tested, zero production callers — **B** — max-push
- **Fee-tier reachability as a live input** — `screen_venue_subsidy.py` says its own cadence is "the REQUEST, not the installation"; not in any crontab — **B** — fence
- **Every 3+ source fusion the desk runs is on public data** — `fusion_engine` fuses DefiLlama+Upbit+Yahoo+Binance, all COLLECT-class, reconstruction cost ~0, while the proprietary tape participates in **no** fusion at all — **S** — GAP_REGISTER

Next in the queue, unwritten: the adversary-lens sweep on quote-pattern fingerprinting (whether a 240s constant wait + touch-only placement makes our order flow trivially identifiable across sessions, and what a randomised placement schedule would cost) — resume generation there.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
