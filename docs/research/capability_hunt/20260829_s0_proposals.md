# CAPABILITY HUNT PROPOSALS 20260829 slot 0

LENS: REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime (high-carry / wide-swap, high-vol / risk-off, post-stop-run, low-liquidity / holiday session) we could switch on and off. What regime do we not yet detect, and what edge would it gate?

## A -- Claude family

I have a fully measured finding. Writing it up.

**MISSING CAPABILITY:** A **cost surface** — spread as a per-symbol × per-hour *state*, measured from the tape the desk already owns — plus the live regime detector on top of it (`spread_z` vs that hour's own baseline). Today the desk holds exactly **one scalar per symbol for all 24 hours**, and it is the number every gate, certificate and forward clock divides by.

**WHY IT IS INVISIBLE TODAY:** Three correct-looking layers.
1. `expand_universe.py:136` / `fetch_universe.py:103` collapse the per-bar `spread` column to `float(df["spread"].median())` **at ingest**. The hour structure is thrown away before any consumer exists, so no consumer can miss it.
2. `Costs.from_symbol` → `engine.py:248 per_oz_cost = costs.per_oz_roundtrip()/contract_oz` → `engine.py:422 r -= per_oz_cost*units/stop_dist`. The engine knows the fill bar's timestamp and never asks the cost model about it. ~25 hunt/screen modules read `median_spread_pts`; **all 25 agree**, so cross-checks pass.
3. The desk *does* have a `spread_gate` family flag (`families.py:519`) — but it **filters** entries and never changes the **cost charged**, so the base and `spread_gate` arms are scored at the identical wrong number. Having the filter is what makes the missing cost model look handled.

The error is also **not uniform**, which is why sampling never caught it. Measured across 578 symbol×session cells / 196 symbols: **71.6% are within ±25% of the scalar** (it is fine), and the damage is concentrated — Forex Exotics **30.5%** of cells wrong by ≥2×, Forex 10.7%, and Commodities/Crypto/Energy/Equities **0.0%**. Any spot-check on gold or EURUSD returns clean.

**MECHANISM:**
- Producer `desks/mt5/research/cost_surface.py` → `desks/mt5/data/cost_surface.json`, keyed `SYM → {hour: {p50, p75, p90, n_nonzero, zero_frac}, session, dow}`, built from the same `*_H1.parquet` the engine already loads. Two exclusions, both verified necessary: drop days with <20 bars (the D1/H1 splice — I tested it, see below), and drop `spread==0` bars while **recording `zero_frac`**, because zero is absence, not a free trade.
- `Costs.from_symbol(meta, *, hour=None)` — `hour=None` reproduces today's arithmetic exactly, so no call site changes silently (the same discipline the class already documents for `quote_per_account`). `run_backtest` passes the **fill bar's** hour.
- Fence `scripts/check_cost_surface.py`, statuses: `OK` / `STALE` / `SURFACE-MISSING` / **`COST-BASIS-MISMATCH`** (a certified cell whose charged spread differs from its own entry-hour surface by ≥2×) / **`UNMEASURED`** (<200 non-zero bars in that hour — never resolves to OK; L1.28a/WS-005).
- The surface's own measured `p90/p50` replaces the **guessed** 3× cost-stress multiple.
- Live half: publish `spread_z = (spread_now − p50[sym,hour]) / IQR[sym,hour]`. That is the regime — nameable, detectable, switchable — and the gateway refuses entry above a preregistered `k`.

**WHAT IT WOULD HAVE CAUGHT** — measured this run, on the desk's own artifacts:

`family_overnight_gap_decay` (`families_orthogonal.py:681`) fires on `first_bar = day != day.shift(1)`, `wait_bars=1`, market entry at that bar's open. On USDZAR/EURZAR that bar is hour 00 on 3,923/2,881 of days. On **full-24-bar days only** (splice excluded), hour 00 carries median tick_volume **127 vs 4,286** at hour 14 and a genuine 1-hour range of 15.6 bp — a real thin book, not a daily bar.

| sleeve | shadow_exp_r | charged | true spread on its **actual entry bars** | error | missing cost |
|---|---|---|---|---|---|
| `USDZAR\|overnight_gap_decay_asia` | **+0.8481 R** | 329 pts | **4,432 pts** (n=436) | **13.5×** | **0.623 R / round trip** |
| `EURZAR\|overnight_gap_decay_asia` | **+0.6929 R** | 310 pts | **5,161 pts** (n=511) | **16.6×** | **0.728 R / round trip** |

These are the **#1 and #2 shadow expectancies in the entire book**, both hold gauntlet certificates in `UNIVERSAL_SURVIVORS.canon.json`, and both are on live forward clocks (`shadow_forward.py:201` → `per_symbol_costs` → the scalar). Corrected: USDZAR **+0.225 R**; **EURZAR −0.035 R — the sleeve is negative**. At the p90 entry-bar spread the round trip costs **1.60 R / 1.83 R**, i.e. more than the stop.

I tested the obvious confound before claiming this. The vault records that these parquets are a **D1/H1 splice** with daily bars stamped 00:00. Refuted as an explanation: the spliced bars carry `spread==0` in 2,200/2,202 and 1,151/1,152 cases, and only **2% / 1%** of the family's signal bars land on them. The 24-hour shape is also **stable** — corr(log) of the hourly profile, first half vs second half of a ~8-year tape: USDZAR 0.983, EURZAR 0.935, CADJPY 0.918, EURUSD 1.000, USDTRY 0.972. This is a stationary structure, not drift.

Prior incidents the `COST-BASIS-MISMATCH` status catches on sight: the XAUUSD `0.48` hardcode (`engine.py` docstring: *"every gold backtest on this desk has run very nearly spread-free"*, and *"the 3x cost-stress gate meant to catch exactly this was stressing 3% up to 9%"*), and **R0695** (EURUSD charged 0.05/lot vs a tape truth of 12 — 240×). Both are charged-vs-tape disagreements that no fence compares.

**ROI:** Direct — retracts one false survivor and re-prices another before either reaches capital; that is the whole point of the two-stage law and today it is being decided on a number that is 13–17× wrong. Cascade, and it is larger: **35 cells are overcharged ≥2×** (GBPCHF london_am charged 70 pts, true **5**; GBPCAD 47 → **4**; EURRUB ny_open 250 → **26**) — that is the **false-null direction, the one that produces no alert**, killing real edges in the cheap window. It multiplies the gauntlet (every verdict on Forex/Exotics), the certificate (`cost_hash` becomes a surface hash), the 3× stress (measured, not guessed), the decay monitor (a "decaying" sleeve may just be in a widened book), and it hands GAP #138 the varying, economically-meaningful moat weight it asked for. It also opens a pure execution alpha with no new research: EURZAR asia/ny = **7.1×**, USDZAR **4.9×** — the same signal filled in the cheap window saves **0.11–0.12 R per trade**.

**COST:** ~6–8h for the producer + `Costs` optional arg + fence + tests; the data is already on disk and already loaded. Maintenance ~0 (it is a re-aggregation of an existing collector). Competes with draining the 236-row past-due conversion backlog — but this is itself a conversion (it disposes the live-clock question those two certificates are currently answering wrongly), and the money path is frozen under L1.38 anyway, so this lands in the research half.

**FALSIFIER:** Pull live `symbol_info_tick` bid/ask for USDZAR/EURZAR at hour 00 broker-time for 10 sessions. If the executable spread there is within ~2× the pooled median — i.e. the H1 `spread` field at the rollover bar is a stale-quote artifact rather than a quotable price — the headline collapses to a tape-integrity defect and the cost surface is worth building only for the 35 overcharged cells. **Also falsified** if `run_backtest` turns out to skip bars flagged by some upstream filter I did not find, so these entries never actually fill at hour 00.

**NOVELTY-CHECK:** `recommendation_ledger.json` (712 rows) regex-searched — `hour[- ]of[- ]day|per[- ]hour|hourly (spread|cost)` → **0 hits**; `(session|window)[- ](conditioned|specific|dependent).{0,10}(cost|spread)` → **0**; `pooled median|24[- ]hour median|averaged across (hours|sessions)` → **0**. The 25 spread rows are all registry-value-wrong (R0695/R0664/R0644), slippage-measured-at-zero (R0673/R0679/R0680) or retired-crypto. `grep -niE "hour[- ]of[- ]day|entry.bar spread|cost (surface|map).{0,30}(hour|session)" docs/GAP_REGISTER.md` → 0 (row 138 proposes session-boundary behaviour as a *search-ranking* weight, explicitly "NOT urgent", and never touches the cost model). `vault_search.py "hour of day spread cost surface entry bar rollover"` and `"spread varies by hour session cost model one scalar per symbol"` → nothing on the statistic; all 15 prior `capability_hunt/*_proposals.md` MISSING CAPABILITY lines read, none is this.

---

## THE BRAINSTORM

1. **Rollover-bar entry audit across every family** — any family keyed on "first bar of day" structurally trades the broker's day-roll (23× fewer ticks, 20–35× spread). Enumerate every family whose signal index can equal `first_bar`. — **S** — ledger.
2. **Entry-hour migration as a free axis** — for every certified cell, re-screen the identical signal with the fill deferred to that symbol's cheapest hour. Same information, 2–7× less cost on exotics. — **S** — axis watchlist.
3. **Live `spread_z` entry gate on the gateway** — refuse a bracket when the book is wider than its own hour baseline by preregistered `k`. Pure downside removal, no alpha claim. — **S** — a fence + gateway.
4. **Measured cost-stress replaces the guessed 3×** — read `p90/p50` per symbol×hour off the surface. USDZAR's entry hour alone is 2.4× on top of a 13.5× base error. — **A** — gate_policy.
5. **Fixed-spread vs floating-spread classifier** — EURUSD is *exactly* 12 pts at all 24 hours, XAUUSD *exactly* 16; ZAR crosses swing 50×. A flat 24h profile is an **administered** spread, not a market one — it labels which symbols the broker marks up rather than passes through, i.e. where it is likely taking the other side. Nothing records this. — **S** — new axis.
6. **Cost-observability coverage fence** — USDZAR's `spread` column is **100% zero for 2010–2019 and 94% for 2020**. Any backtest spanning that era has no cost observable at all. Per symbol×year `n_nonzero_spread_bars`, `UNMEASURED` never rendering as OK. — **A** — fence.
7. **Holiday / thin-session detector from the desk's own tape** — the broker calendar publishes only as a PNG (prospector s9), but tick_volume vs the same-weekday-hour baseline gives it for free, and holidays are currently screened as normal days. — **A** — new organ.
8. **Session-label clock audit** — sleeve windows and `regime_discovery.SESSIONS` use index hours, but 191/197 parquets carry broker EET stamped `+00:00`. "asia" may denote 21:00–03:00 UTC. Every session-conditioned verdict inherits the offset. — **A** — ledger.
9. **Re-score the `spread_gate=True` arms under corrected cost** — the filter arms were compared against base at an identical wrong cost; the ranking may invert. — **A** — re-run.
10. **Certificate freezes a cost *surface* hash, not a scalar `cost_hash`** — today a re-measure of one number mints a new identity (shadow_forward.py:294 documents the churn); a surface hash is stable and carries the hour. — **B** — registry.
11. **Realised-vs-charged spread term in `forward_reconcile.py`** — the desk reconciles forward R but never reconciles the cost it assumed against the cost the tape recorded at the fill bar. — **A** — fence.
12. **Triple-swap Wednesday as a declared cost regime** — a deterministic, calendar-known 3× financing charge; audit which sleeves hold across the Wednesday roll and whether the engine charges it at all (R0670 says the tester applies *today's* swap table to all history). — **A** — ledger.
13. **Regime-conditioned orthogonality** — two sleeves decorrelated over the full sample can be perfectly correlated *within* a regime; the portfolio's `k_eff` is computed unconditionally and therefore overstates diversification exactly when it matters. — **S** — portfolio_evidence.
14. **Cost-regime-aware decay monitor (L1.59)** — a sleeve flagged FADE may simply be trading through a widened-book period; without conditioning, the desk retires a live edge for a cost excursion. That is the plumber fixing the water. — **A** — decay_monitor.
15. **Regime-conditioned sizing rather than binary on/off** — size ∝ expected edge / expected cost at the fill hour, instead of hibernate/wake. Kelly already wants this; the surface makes it computable. — **A** — book_sizing.
16. **Spread widening as a *signal*, not only a cost** — dealer widening is inventory/uncertainty information and leads short-horizon vol; direction-agnostic, which is the class the desk's own record says survives. — **B** — axis watchlist.
17. **Bid/ask asymmetry by side** — the tape carries one spread number; if the broker skews, buy and sell halves differ and every symmetric cost model is wrong in one direction per side. Testable against R0679's per-side slippage panel. — **B** — ledger.
18. **The 16:00 London WMR fix as a nameable regime** — a known forced participant (index/passive funds must trade the fix) on a fixed wall clock, on the desk's exact universe. The mechanism census has no class whose payer is a mandated benchmark trader. — **S** — axis watchlist.
19. **News-window regime with no calendar feed** — joint spread-spike + tick-burst on the desk's own tape identifies scheduled-release windows without buying a calendar, and closes the "we can't detect news" gap from the inside. — **A** — new organ.
20. **Capacity is regime-conditioned too** — tick_volume at the fill hour caps deployable size; a sleeve entering at hour 00 has ~1/23rd the liquidity its pooled capacity model assumes. — **A** — capacity model.
21. **Weekend-gap regime as distinct from overnight** — Monday's first bar spans 48–65h of closure; `monday_gap` and `overnight_gap_decay` currently share a cost basis and a gap-normalisation that assumes one night. — **B** — families.
22. **Ratchet floor on the cost surface** — a per-symbol×hour cost floor artifact so a re-measure can never *lower* a charged cost silently (the exact direction `engine.Costs` documents as having cost this desk dearly). L2.0 fence. — **A** — ratchet.
23. **Cross-broker cost surface** — R0673/R0679 established that MQL5 publishes per-symbol × per-broker-server real-account slippage keylessly; joining it to this surface answers whether the asia widening is a market fact or a Fusion markup, which decides whether the edge is portable. — **A** — ledger.
24. **Post-stop-run regime** — a sweep of the prior session's extreme followed by rejection is detectable on the desk's own bars and is the one regime with a named forced participant (stopped-out retail); currently only `failed_breakout` approaches it and that study is halted MECHANISM-UNMEASURABLE. — **B** — axis watchlist.
25. **Prop-firm 00:00 CE(S)T reset as a live regime** (already carded in the watchlist, not yet a *detector*) — the forced-flattening wall clock is one hour off the swap rollover; the desk can detect the resulting flow in its own tape as a volume/spread signature and gate on it. — **A** — watchlist → screen.
26. **Equity/index auction regimes** — cash open and close auctions on the 64 equity CFD cells; measured 0% cost-scalar error means the broker administers those spreads, which makes the *auction* the only place their real cost lives. — **B** — new axis.
27. **`UNMEASURED` propagation through the gauntlet** — a cell whose entry hour has <200 cost observations should return `INSUFFICIENT-EVIDENCE`, not a pass; today the scalar always exists so no gate can express "I don't know what this costs." — **S** — gate_policy.
28. **Regime-conditioned promotion slots** — 12 forward slots allocated with no regime-coverage term means the book can fill with 12 sleeves that all require the same regime; an uncovered regime is a named gap (RESEARCH §6c) with no instrument. — **A** — promoter.
29. **Cheapest-hour ranking as the moat pointer weight** — closes GAP #138 directly: `dear_over_cheap` varies 1.0–423× across the universe, where coverage-days is uniform at 18.0 for 189/193 symbols. — **A** — mined_ground.
30. **Rollover-hour exclusion as a preregistered arm, not a fix** — rather than patching, run the whole certified roster with hour-00 entries excluded as a declared arm; the difference *is* the measurement of how much of the book is rollover artifact. — **S** — re-run.
31. **A "cost that was never paid" graveyard query** — every historically graveyarded cell in a cell that is now known to be **overcharged ≥2×** is an L1.16a reopen candidate under a named enabling change (the surface). 35 cells' worth of dead ground to re-open. — **S** — graveyard.
32. **Tick-volume stationarity as a regime-validity check** — the hour profile is stable at corr 0.92–1.00, but a *break* in it is the broker changing its liquidity provision, which is the one regime change that invalidates every session-conditioned certificate at once. Watch the profile, not just the level. — **A** — fence.

Context is the only stop. Next I was going to write: **the swap-table-change detector as a regime** (the broker's risk desk sets swaps from a book nobody else sees — R0658(a) routes the conditioning variable but nothing detects the *change event*), and **an inverted-fence item: what checks that a regime we claim to detect is actually detectable live rather than only in hindsight** — the `regime_discovery` K-means is fitted in-fold but its live assignment path has no latency or availability test, so a regime that is only computable a day late reads identically to one the gateway can act on.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
