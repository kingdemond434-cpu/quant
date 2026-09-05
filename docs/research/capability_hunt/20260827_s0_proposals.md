# CAPABILITY HUNT PROPOSALS 20260827 slot 0

LENS: NEW EDGE FAMILY -- name a mechanism class with a FORCED participant (month-end / quarter-end FX fixing, gold-ETF AP hedging, index/ETF rebalances, index-futures roll, options-dealer gamma, central-bank operations, commodity producer hedging, sovereign / real-money mandate flows) that this desk has never screened, and the free data that would test it. Mechanism first, never a pattern.

## A -- Claude family

## MISSING CAPABILITY
**A perishability gate on the acquisition queue — for every observable the desk *could* record and does not, does delay cost DELAY or does it cost THE DATA?** The first live occupant: the **financing leg** of the desk's own universe (`swap_long`/`swap_short`, 219 symbols), whose entire recorded history is **five snapshots inside one four-hour window on 2026-08-26**, and whose recorder has emitted `kind: "unmeasured"` on **all 21 runs since** — 21 consecutive hours announcing its own blindness into a directory nothing reads.

## WHY IT IS INVISIBLE TODAY
Three correct instruments, and the join between them exists nowhere:
- **The unwired register** (256 rows, incl. `swap_table_miner` at 0 callers / 0 artifacts) scores every row as *delay*. It has no column for "is this input backfillable?"
- **L1.65 recoverability** (`libs/research/recoverability.py`) is denominated in **streams that exist**. Zero rows recorded ⇒ zero span ⇒ zero loss ⇒ no alarm. It cannot see a stream never opened. WS-005 one level up.
- **The asymmetry ledger** (`scripts/asymmetry_ledger.py`) *has* a `PERISHABLE` class — and all 14 assets were verified **2026-08-03, before the 2026-08-18 MT5 mandate**. Both PERISHABLE rows (`funding_at_settlement`, `listing_announcements`) are crypto-exchange observables the desk may **never hunt again**. It still returns 14 rows and a ranking, so it reads green while containing nothing actionable.

And the mechanism census (32 classes, `data/mechanism_census.json`, generated 02:24 today) prices **every payer in the asset's spot price**. `fx_carry_rate_differential` ranks #1 with data = *"FRED policy rates + the desk's FX spot"* — the public, buyable, everyone-has-it **level**. The census has no class whose payer is a **balance-sheet-constrained dealer bank** compelled by a **regulatory reporting date**, because it does not know that price series exists.

## MECHANISM
Every CFD carries **two** prices from the same broker: the spot quote (recorded — 197 parquets, 9,739 bars each) and the overnight financing pair (recorded **once**). The financing leg is `broker markup + tom-next forward points`, and the forward points *are* the CIP-implied differential. Deviations from covered interest parity are the **cross-currency basis** — driven by dealer balance-sheet capacity, spiking on quarter/year-end leverage-ratio snapshot dates that are known years ahead. XAUUSD's swap is USD funding minus the **gold lease rate**, whose public benchmark (LBMA GOFO) was discontinued in 2015. The desk's live edges are on **gold and JPY crosses** — precisely where this is largest.

Concretely:
1. `desks/mt5/research/expand_universe.py:110–125` already reads `swap_long`/`swap_short` for all 197 symbols. It writes them into a dict that a downstream `universe.json` producer **deletes** — measured today: **0/197 carry a swap field** (`tick_value` survives on only 115/197). Fix: append `{stamp, symbol, swap_long, swap_short, swap_mode, triple_day}` to `desks/mt5/data/financing/swaps.parquet` at the point of read, before any merge can eat it.
2. New fence `scripts/check_perishability.py` → `data/perishability.json`. Row per candidate observable: `{observable, in_mandate, recordable_today, backfill_route, status}` with statuses **`RECORDING` / `PERISHING` / `BACKFILLABLE` / `UNMEASURED`**. `PERISHING` (in-mandate, no backfill route, not recording) is the only red, and it pages. Seeded by joining `check_unwired_capability.py` output × the asymmetry ledger × the census's `data_required` fields — which is the join nothing computes.

## WHAT IT WOULD HAVE CAUGHT
**The `tick_value` collision, same file, same week.** Memory `gap-wirer-20260826f`: three producers on one `universe.json` deleted `tick_value` → 0/197 costable + a 184× JPY commission undercharge. **The same collision deleted `swap_long`/`swap_short` in the same dict literal, and only `tick_value` was caught** — because `tick_value` had a downstream consumer that failed loudly and swap had none. The swap half is *still broken today*, 24 hours later, with the recorder shouting `unmeasured` into `desks/mt5/data/intelligence/broker_swaps/` 21 times.

And it inverts a **published null**. `desks/mt5/mt5desk/financing.py` concludes gold_afternoon has "roughly an order of magnitude of headroom" against its 176.05/lot/night breakeven, on the assumption "a raw-spread broker charges XAUUSD in the tens". The captured table says **XAUUSD long = −65.67, short = +32.04**. At 65.67 the drag is **37% of that sleeve's 0.0957R expectancy**, not 11% — and the number has been sitting in a discoveries file since yesterday morning. *(Unit check first: confirm `swap_mode` is account-currency-per-lot, not points. This desk has paid for units twice — L1.67, and the gold $/oz-vs-$/lot spread bug.)*

## ROI
- **Direct, today:** re-costs every overnight sleeve from measurement instead of inversion; `financing.py`'s `swap_per_lot = None` resolves. If the 37% holds, gold_afternoon was never a survivor at its published expectancy.
- **New axis:** opens the one price dimension the census cannot rank, on the exact two instruments carrying every live sleeve. Feeds L1.30 directly — replacement rate is **0.913 (21 births vs 23 deaths)**; the desk is losing edges faster than it makes them, and this is an orthogonal source of births.
- **Cascade:** the register makes "which of my 256 unwired rows is a *clock*" answerable for the first time, and re-points the asymmetry ledger at in-mandate ground.
- **Free kill already visible:** all 219 US share CFDs quote an *identical* swap (−7.31 / +2.81). No name-level borrow ⇒ **no hard-to-borrow / short-squeeze signal exists in this broker's share CFDs**. A whole hypothesis family retired for zero compute. Same for crypto CFDs (−15.0 both sides = pure rent, zero carry information).

## COST
~1h for the append (the read already happens; it is a write and a schema). ~4h for the fence + tests. Maintenance ≈ 0 (one parquet append/day). Competes with 216 past-due ledger rows, gap #148 and #145. **The 1h jumps the queue** — it is the only item I found where waiting is irreversible; the 4h competes normally.

## FALSIFIER
Runnable today on data already on disk, no waiting: `gateway.py:1063–1071` logs realised `swap` on every closed deal.
1. If realised swap on Wednesday/month-end rolls ÷ ordinary rolls ≈ **1.0**, the discrete-payment thesis dies and only the level matters.
2. If broker swap regresses on FRED rate differentials at **R² > 0.95** across the 244-symbol snapshot, there is no proprietary information in the financing leg and only the cost half survives.
3. If the unit check shows −65.67 is *points* not account currency, the 37% drag is wrong and `financing.py`'s null stands — kill the cost half, keep the recorder.

**NOVELTY-CHECK:** `grep -rli` over the repo returns **0** for `cross-currency basis`, `xccy`, `basis swap`, `tom-next`, `turn-of-year`, `year-end turn`, `leverage ratio`, `G-SIB`, `balance sheet constraint`, `point-in-time only`; `covered interest`/`turn of the year`/`window dressing` return **1 file each — all three are signature-token lists inside `mechanism_census.py` itself**, not implementations. `find . -type d -name "swap_table*"` → nothing. `grep -rn "swap_table_miner"` → one docstring line in `side_channels/__init__.py`, zero callers. Ledger scan of 674 rows and `docs/GAP_REGISTER.md` for `swap|financ|perishab|rollover|forward point` → no row on recording the financing leg or on perishability of unrecorded observables. Axis-watchlist card #62 explicitly grades the single-broker swap route **"ALREADY BUILT"** — measured false in the dimension that matters: 0/197 fields present, one day of snapshots, 21 hours dark.

---

## BRAINSTORM

**S — highest tier**
1. **`universe.json` has three producers and no field-level owner** — `tick_value` was eaten once and healed to 197/197 (memory 08-26), and is back to **115/197** today. Same file also lost `swap_long`, `swap_short`, `volume_step`, `updated_at`, `asset_class`. A per-field producer registry + a fence that reds when a field's population *falls* would have caught all six. → fence
2. **`desks/mt5/data_registry.json` is malformed JSON** (`Expecting ',' delimiter: line 30 col 16`). The MT5 desk's own data registry cannot be parsed by any consumer, and nothing reports it. Every registry/manifest on the desk should have a parse-gate. → fence
3. **A "producer emitted `unmeasured` N runs in a row" pager.** 21 consecutive honest-refusal rows is the *strongest possible* signal and it has zero consumers. Generalise: any organ whose output kind is UNMEASURED/UNTESTABLE for k consecutive runs pages. This is the general form of the deep proposal and probably worth more. → fence
4. **Arrivals collapsed (29/wk vs 161.25 baseline) may be a plumbing artifact, not a thin seam.** Miners are writing findings into `data/intelligence/<channel>/discoveries_*.json` and only `miner_candidate_compiler` reads some of them. Measure findings *produced* vs findings *arriving in the ledger* — if the ratio is low, the desk is not finding less, it is losing them in the pipe. → ledger, high priority
5. **Charge swap in `engine.Costs` at all.** It has no swap field; `book_years.py` lists "NO SWAP" as an assumption. 46.4% of 15,932 backtested trades cross a rollover. Once the table is recorded there is no excuse. → ledger
6. **Triple-swap day is a 3× discrete charge and nothing models it** (L1.47 is literally the desk's own law). Which weekday Fusion triples per asset class is one `symbol_info` field (`swap_rollover3days`) already reachable. → ledger

**A**
7. **US share CFD swaps are name-invariant (−7.31/+2.81 for all 219)** ⇒ hard-to-borrow / short-interest mechanisms are structurally unavailable on this broker. Retire the family for free, record it in the graveyard so no future run re-proposes it. → graveyard
8. **Crypto CFDs quote −15.0 both sides** ⇒ symmetric pure rent. Any long-*or*-short crypto-CFD carry hypothesis is dead on arrival; also means overnight crypto-CFD holding is a guaranteed bleed on both sides. → graveyard + cost model
9. **The swap `diff` (long+short) is the broker's markup, and it is per-symbol.** `USDTHB` diff = +396.75, `GBPUSD` = +0.32. That spread *is* a direct read on which symbols the broker prices aggressively — a free execution-venue map, and a candidate proxy for where its own hedging is cheapest. → axis watchlist
10. **XAUUSD short pays +32.04/lot/night.** Any short-gold sleeve has a *positive* carry the backtest scores as zero — a systematic understatement of every short-side edge, opposite in sign to the long-side overstatement. Asymmetric mis-costing is worse than uniform. → ledger
11. **Sign-check the whole table against theory as a data-integrity gate:** `AUDHUF long=-1402.52` and `CHFHUF long=-7774.0` are enormous; if any high-yielder shows a negative long swap where rates say positive, either the sign convention or the unit is inverted. One-line assertion, catches the class that produced the L1.67 risk-units incident. → fence
12. **The census's `data_required` fields are still crypto-worded post-mandate** — `collateral_rule_deleveraging` wants "Aave/Compound governance logs", `treasury_cost_base_liquidation` wants "mining-pool payout addresses". Those classes are un-screenable as written on MT5 ground, so they sit permanently NO-CANDIDATE and the gap ranking is distorted. Re-word the data requirements for the mandated universe. → ledger
13. **Add a mechanism class the taxonomy lacks: `financing_capacity_rent`** — payer = a balance-sheet-constrained intermediary compelled by a regulatory reporting date. Distinct from `fx_carry_rate_differential` (level, public) and `fiscal_calendar_flow` (taxpayer). → census taxonomy
14. **Add its mirror: `forced_abstention`** — every class names who must trade; none names who is mandated *not to* (post-deletion index names, exclusion mandates, sanctions). Absence of a bid is as mechanical as presence of an offer. → census taxonomy
15. **The EET/EEST clock bug (R0660) is priced at ~40% of the SGE premium's variance and is stated as "named, not applied".** Every session/calendar/event-window study on this lake — including `flowcal`'s Tokyo-fix and month-end work, and the *entire* asia-session sleeve family — carries a 2–3h misattribution with a DST seam. This is the single largest unapplied known correction I saw. → chase to applied
16. **The asymmetry ledger needs an in-mandate filter and an MT5 repopulation.** 14/14 assets are crypto-era. Candidate MT5 EXCLUSIVE rows: own fills, the financing leg, per-symbol spread menus, the broker's stop-level/freeze-level, rejection/requote records. → ledger
17. **Record `symbol_info.stops_level` / `freeze_level` per symbol per day.** They bound the *minimum achievable stop distance*, they change with volatility, and they are a hard constraint on every backtested stop the desk has ever run. Also perishable — point-in-time only. → deep proposal's register
18. **Record the spread *series*, not `median_spread_pts` as a scalar.** Spread is stored as one overwritten number; its intraday and rollover-window path is what decides whether the asia sleeve's fills are real. Same perishability class. → same

**B**
19. **A positive control for the census.** It has never been shown to *classify a known member correctly under adversarial wording* — only its rejections are observed (the desk's own certify_gauntlet lesson, one domain over).
20. **`n_eff` for the MT5 universe is unmeasured because `asset_class` is 0/197.** Gap #145 names the grouping absence; nobody has measured what the *breadth* number actually is on 197 CFDs — and the crypto answer (1.54 raw) was the finding that killed a whole family.
21. **Deflated-Sharpe trial accounting vs the discovery feed.** If miners generate candidates into `intelligence/` that never reach the compiler, the *declared* trial count and the *actual* search are diverging — in the direction that makes the bar too lenient.
22. **Reconcile realised deal `swap` (gateway) against the snapshot table.** Two independent measurements of the same quantity; a mismatch is either a unit bug or a broker mid-day revision, and both are findings.
23. **Measure whether the broker revises swaps intra-week.** Five snapshots four hours apart show whether the table is static within a day. If it moves, the *revision* is the signal, not the level.
24. **A `RECORDERS_OFF`-equivalent audit for MT5:** 168MB of banned crypto recorders idle (gap #144) while the *mandated* financing recorder is dark. The box is spending resident memory on the forbidden universe and none on the perishable in-mandate one.
25. **Cross-broker swap dispersion** (watchlist card #62's surviving half) — but note it is *strictly lower value* than fixing the single-broker series first, and the card currently implies the reverse.
26. **Ex-dividend adjustment schedule for index and share CFDs.** Broker-published, dated, mechanical; the long/short asymmetry (withholding-tax treatment) is a measurable broker-specific constant and a candidate cost leak on any index-CFD sleeve held over an ex-div date.
27. **Contract-roll schedule for energy/softs CFDs** (XTIUSD, XBRUSD, XNGUSD, CORN, WHEAT…). The desk trades them; the CFD references a dated future that rolls; nothing on the desk knows the roll calendar, so any multi-week backtest on those symbols silently splices contracts.
28. **A "verdict published from a guessed input" fence.** `financing.py` published a null on an assumed rate; `data_axis_watchlist` card #62 published "ALREADY BUILT" on an unverified field. Both are the same defect: a conclusion whose load-bearing input was never measured. Grep-able signature: a docstring conclusion citing a number with no artifact path beside it.
29. **Rate-limit / cooldown map per source**, so a `fetch_error` streak (10 consecutive on 08-25/26 here) distinguishes *walled* from *broken route* automatically — the §13-wall vs route-bug split memory already names.
30. **Instrument the gap between "capability emits an honest refusal" and "desk acts on it."** The `unmeasured` kind is the desk's best invention and its worst-served output: it is produced correctly everywhere and consumed nowhere.

Context is not the limit yet, but the seam here is: I was about to work #4 (findings produced vs findings arriving) into a measurement — count rows across all `data/intelligence/*/discoveries_*.json` for the last 7 days and compare against `arrivals_7d: 29`. If that ratio is ≫1, `ARRIVALS-COLLAPSED` is a pipe defect, not a hunting defect, and the standing "HUNT HARDER" instruction is pointed at the wrong organ. **That is the next thing to generate on, and it is probably bigger than the deep proposal above.**


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
