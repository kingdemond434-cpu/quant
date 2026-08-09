# CAPABILITY HUNT PROPOSALS 20260801 slot 0

LENS: DATA ASYMMETRY -- information that could exist ONLY because of how WE combine data (our own-timestamp L2, our execution tape, cross-source joins). What proprietary feature is a competitor structurally unable to buy? (L1.11a: rank by reconstruction cost.)

## A -- Claude family

Three agents back, all three converge. Here it is.

---

## MISSING CAPABILITY

**Clock provenance on every market-data record** — each row declares *which clock stamped it* and carries the venue's own stamp beside ours, making **timestamp alignment a measured number instead of an assumption**, and creating the venue↔receipt offset series Δ that no competitor can buy or backfill.

## WHY IT IS INVISIBLE TODAY

The desk's 7.5 GB moat corpus stamps depth with `int(time.time()*1000)` (`run_recorder.py:232`, `run_recorder_spot.py:243`, `run_recorder_bybit.py:152`) and stamps trades with the venue's `tr["T"]` (`run_recorder.py:249`). **Same field name `t`, two different clocks, same file, discriminated only by `k`.** Verified on disk in `data/moat/fut/BTCUSDT/`: a `k:"d"` row timestamped ~256 s *after* the `k:"t"` row preceding it — the file is not monotonic in `t`, and nothing says so.

Nothing can see this because every fence checks whether the **collector ran**, never whether the **timestamps mean what the schema implies**. Gapless collection was verified GOOD in the data-moat sweep. `moat_audit.py:71` crystallises the blind spot in one line — `"t": d.get("t") or d.get("E") or d.get("ts")` — the desk's own auditor coalescing three different clocks into one field.

And the question was asked once, in the wrong register: infrastructure sweep U10 (`20260731_infrastructure.md:59`) said *"for a venue-timestamp-sensitive desk this should be a fenced metric, not an assumption"* — then the next day it was answered as **ops health** (chrony RMS 152 µs) with no research use. Closed as green.

Verified live just now, both venues return the stamp we discard:
- `fapi/v1/depth` → `['lastUpdateId','E','T','bids','asks']`, `now−E = 172 ms` — read at `run_recorder.py:231`, dropped at `:233`.
- `v5/market/orderbook` → `result.{ts,u,seq,cts}` + top-level `time`, `now−ts = 249 ms` — dropped at `:152`. **Bybit depth rows carry no venue identifier at all** — no time, no sequence.
- Binance **spot** genuinely returns `['lastUpdateId','bids','asks']` — a real venue limitation, not a dropped field.

## MECHANISM

1. **Retain both stamps.** 3 lines: `"E"/"T"` (Binance fut), `"vt"/"u"/"sq"` (Bybit), plus a `"c"` clock-provenance marker per record (`venue` / `recv` / `recv_only`). Spot gets a periodic `/api/v3/time` offset probe or is honestly marked `recv_only`.
2. **Δ = t_recv − t_venue** becomes a first-class series: our end-to-end observation latency, per venue, per symbol, per second. Structurally unbuyable — a vendor sells you the venue's stamp or *their* box's receipt; nobody can sell you when a message reached *ours*, and it cannot be backfilled.
3. **The venue stamp is the join key** to the free first-party Bybit archive the moat sweep already found (200 levels / 100 ms / 345 d vs our 25 / 4080 ms / 11 d). Public deep book (anyone) ⋈ our receipt tape (only us) = a measurement of **our own information disadvantage**, per symbol, per regime. R0243 owns the *download* as recorder validation; the join is impossible today because our Bybit rows have no key.
4. **Fence** `check_clock_provenance.py`: `OK / MIXED-CLOCK / RECV-ONLY / UNMEASURED` — never OK on absent input (L1.41).
5. **Free pilot before any build:** Bybit trades already carry both clocks (outer `t` = our poll receipt, inner `time` = venue) across ~11 days. Δ is measurable **retroactively, today, at zero collection cost**. The archive contains its own control.

## WHAT IT WOULD HAVE CAUGHT

**`kimchi_premium` — the desk's flagship edge, retracted 2026-07-29 as a ~73% timestamp artifact** (`GAP_REGISTER.md:132`, registry `E-02f2917dfb`). `coinbase_premium_timing` was graveyarded as *"close-timestamp microstructure"*. R0060 records a third: leaky Upbit look-ahead copies surviving their own retraction. **Three of the desk's most prominent kills are one defect class** — and the institutional response was a *prose duty* ("DECLARE TIMESTAMP ALIGNMENT for every cross-source series... unstated alignment voids the screen") with **no instrument**. The corpus that is now 82% of all desk data cannot report its own alignment, so that duty is unsatisfiable by construction on the desk's primary dataset.

**And it is about to fire again.** R0117 (`open`, graded *"highest reconstruction-cost item, L1.11a"*, SCREEN-OWED on the axis watchlist) reads: *"CROSS-VENUE QUOTE LEAD-LAG **at own synchronized L2 timestamps** — pure moat... ours are actual capture instants."* The premise is false. The two recorders are independent processes at `_DEPTH_EVERY_S = 5.0` (fut) and `4.0` (Bybit) — **different periods, no common trigger**, so their sampling phase drifts continuously through the full cycle. R0117 targets sub-minute lead-lag; the sampling alias is ±4–5 s. **The measurement error is larger than the effect.** It would print a plausible, mechanism-consistent number, and nothing in the stack — angle-20 de-contamination, artifact gate, Holm, DSR — tests for sampling-phase aliasing. That is the 420/0 instrument-artifact class (L1.25), one layer further down, on the desk's self-declared crown jewel.

## ROI

**Direct (money path):** `run_cost_model.py` → `data/cost_model.json` is the *one* L2 artifact gating real capital (`run_cashcarry_executor.py:339`). It walks books of unknown age. `binance_live.py:141` reads `/fapi/v1/depth` for live decisions and drops `E`/`T`. Repo-wide grep for `book_age|snapshot_age|quote_age|stale_book|md_age` → **zero hits**: the executor prices maker-vs-taker against a book whose age it cannot know, and staleness is worst exactly when it costs most.

**Cascade (the multiplier):** R0003, R0084, R0117, R0203, R0208, R0243, BR-07 and the 450-cell feature grammar (`feature_library.py`, 3 tested) **all run on this corpus**. Clock provenance doesn't add one feature — it makes ~450 planned cells interpretable and stops one queued row from manufacturing a phantom moat edge. It also restores compliance with a standing law the desk currently cannot obey.

## COST

~4–6 h: 3 recorder lines, one `"c"` field, fix `moat_audit.py:71` to branch on `k`, one fence, and the free retro-pilot first. Maintenance ≈ 0. Competes with the repair-mode drain (171 backlog / 42 past due) — but this is a §33 **T1 defect-closer** that unblocks four rowed items, and the collector half is L1.28b(f)-protected: every day without it is a permanently unrecoverable Δ day.

## FALSIFIER

Run the free Bybit-trades pilot on 11 days. **Reject if all three hold:** (1) Δ's `p99−p50` < ~50 ms, stationary, and residual-after-poll-phase uncorrelated with realized vol → the venue-stress-signal claim dies; (2) re-running `micro_factory`'s lead/coincident/residual Spearman with `k`-branched clocks reproduces current numbers within noise → the research-bias claim dies; (3) a phase-alias simulation shows a 5.0 s/4.0 s poller pair recovers true sub-second lead-lag unbiased → the R0117 cascade argument dies. All three → this is bookkeeping, reject it.

**NOVELTY-CHECK:** `grep -rn --include=*.py -iE "clock_offset|clock_skew|serverTime|time_offset|drift_ms|recv_ts|receipt_ts|local_ts|ingest_ts" libs scripts` → **empty**; `grep -rn --include=*.py -iE "book_age|snapshot_age|quote_age|stale_book|data_age_ms|md_age" libs scripts` → **empty**; 275 ledger rows scanned, 62 broad-pattern matches, **none on clock provenance or venue-stamp retention** — and an independent overlap sweep pre-labelled latency/clock-skew (U5/U7/U10), venue engine load, and ours×public joins as **zero-coverage, owned by nobody**.

---

## BRAINSTORM

**S — trade tape is the only clean-clock series in the corpus, and the sole micro producer filters it out.** `micro_factory.py:95` keeps only `"k":"d"`; a sample hour is 357 depth vs **31,877 trade** rows — 99% of records, venue-stamped (clean), nearly free in bytes, and unused. Aggressor imbalance, trade-size distribution, inter-arrival times. → ledger + axis watchlist.

**S — ~50% of depth polls are silently lost.** 357 snapshots/hr observed vs ~720 expected at 5 s; swallowed by a bare `except: pass` (`run_recorder.py:235-236`) with no counter. Half the crown jewel is missing and no artifact reports it. → fence.

**S — R0249 markout may need no collector change at all.** It is rowed as *"a collector change plus a statistic"*, but the fill tape and the depth records are **both our clock, same box** — so fill → book at t+1 s/10 s/60 s is joinable *today* for any symbol in the recorder universe. Trades are venue-clock and are not. Exactly the distinction provenance makes visible. → ledger (unblocks R0249).

**S — `libs/signal_engine` gates on constants.** `models.py:99-102` defaults `spread_bps=1.0, liquidity_score=1.0, microstructure_score=1.0`, and `app/feed.py:75` builds `MarketState(symbol=symbol)` with all defaults — so `edge_estimator`, `quality`, `selection`, `confidence_engine` evaluate microstructure gates against literals. A welded gate under GATE-OPTIMALITY DUTY. → ledger.

**S — venue fill truth is fetched and thrown away.** `binance_live.py:159-164` calls `/fapi/v1/userTrades` (carries `isMaker`, `commission`, `orderId`, `realizedPnl`, venue `time`) and collapses it to a scalar VWAP. Persisting those rows gives venue-truth maker/taker + fees + venue fill time on every fill, free, closing R0058's 1.9% TCA coverage from the venue side. → ledger.

**S — `liquidations.parquet` mixes two clocks in one column.** 50,362 rows, genuinely irreplaceable (no REST liquidation history at any venue), and `liquidation_listener.py:95-96` silently substitutes `datetime.now()` when venue `T` is absent — no discriminator. Same defect shape, WS feed, where a receipt stamp would have been high-resolution. → fence.

**A — WebSocket instead of REST is the single largest free resolution upgrade.** `wss://` has zero matches in the execution path. WS gives event-by-event books, true dissemination latency, ~100× resolution, at *lower* rate-limit cost than polling. → ledger.

**A — Bybit `result.u`/`result.seq` are returned and dropped**, so there is no sequence-gap detection on depth: a dropped poll and a quiet book are indistinguishable. → fence.

**A — venue `amend` preserves queue position.** `PUT /fapi/v1/order` exists; our maker path cancel/replaces and goes to the back of the queue every requote (`20260731_execution-growth.md:276`). Direct bps on every maker fill. → ledger.

**A — `libs/backtest/queue_fill.py` is a real hftbacktest-derived queue model with zero callers**, and `queue_ahead` is a *parameter with no estimator* — our own L2 plus `u`/`seq` could estimate it. Orphan class (L1.45). → ledger.

**A — `libs/execution/tca.py` `PostTradeTCA`/`SlippageAttribution`: built, tested, zero production callers.** Live TCA is an inline `_tca()` in the executor. → ledger.

**A — storage: Bybit is 6.0 GB for 11 d/20 symbols vs fut 989 MB for 15 d/30 symbols.** Raw JSON, 25 full levels, un-delta'd, every 4 s. Delta-encoding buys ~10× retention on the same disk against an 80% disk fence. → ledger.

**A — supervision is asymmetric on the crown jewel.** `ensure_recorder.py:19` `_PAT = r"python.*run_recorder\.py"` covers only the futures recorder; spot and Bybit rely on a separate cron pgrep guard. → fence.

**A — `micro_factory` reads only `data/moat/fut`.** Spot + Bybit — 6.5 GB, the majority of the corpus — are never read by the only micro-feature producer. → ledger.

**A — cache the corpus pass.** 5 of 9 features are `computed_unused` and `feature_library.py:167` says each cost a full 4.4 GB read. One pass → a columnar intermediate makes the 450-cell grammar cheap instead of prohibitive. → ledger.

**A — staleness-weighted cost model.** Down-weight book-walks taken from stale snapshots; `_COST_MODEL` gates real money. → money path (change-window check first).

**A — free 345-day/200-level Bybit archive is a 31× extension of the microstructure research window**, not just a recorder check. Our history is 11 d. → axis watchlist.

**B — Δ as a risk rail before it is alpha.** If observation latency spikes, widen the entry gate / don't cross. Costs nothing, protects capital exactly when a venue degrades — the FTX/Alameda lens. → risk.

**B — the recorder polls on a fixed 5.0 s/4.0 s grid from a fixed IP.** The executor jitters (`rng.uniform(0.85,1.15)`) specifically to avoid being fingerprinted; the recorder does not. Adversary lens. → ledger.

**B — persist the executor's existing jitter draw** as an instrumental variable for identifying latency→fill-quality effects. The randomisation is already running and already discarded — L1.45 shape, different knob. → ledger.

**B — venue-concentration blind spot (Archegos lens).** All three feeds and both legs sit on Binance+Bybit; nothing measures aggregate exposure to a single matching engine. Δ doubles as the early warning. → risk register.

**B — data-quality SLO with burn-rate alerting** (reliability-engineering transfer): a 50% poll-loss rate should trip a budget alarm, not be discovered by a sweep. → fence.

**B — `crypto_trades.sqlite` last written 2026-06-28** (34 d stale, 760 rows) and `libs/execution/journal.py` `TradeJournal` is not wired into the executor that actually trades. Two orphaned execution stores. → ledger.

**B — `libs/research/microstructure.py` docstring claims `crypto_sleeves._book` consumes `book_imbalance`; it never calls it.** Stale-fact defect in a file whose zero-caller status R0003 already cites. → ledger.

**B — control for mechanical calendar instants.** Funding settlement and scheduled venue maintenance produce book/trade patterns that a naive screen will read as signal; nothing appears to control for them. → validation.

**B — measure the corpus's information content honestly.** 25 levels @ 4 s vs 200 @ 100 ms is a computable bits ratio — the honest denominator for "is our own recorder worth keeping, or is the free archive strictly better?" The moat sweep answered that by intuition; it is arithmetic. → ledger.

Next I would have gone after the **execution-tape schema itself** — no order submit time, no ack time, no venue `orderId`, no confirmed maker/taker on 523 rows — enumerating each missing field against the specific statistic it blocks; and then the **`micro_factory` de-contamination question**, since F002 `depth5` died to same-period RV orthogonalisation and it is worth asking whether that control is itself removing the signal at 4 s resolution.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
