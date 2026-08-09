# CAPABILITY HUNT PROPOSALS 20260805 slot 1

LENS: SMALL-CAPACITY FRONTIER -- an edge too small for a tier-1 desk to touch and therefore ours for free (L1.18a): a niche venue, a long-tail pair, an era archive, a language ecosystem. Which structurally-abandoned band are we not harvesting?

## A -- Claude family

I read the four state artifacts, the tier-1 benchmark, the gap register, all 369 ledger rows, and mapped the desk's venue/instrument surface before proposing. Pushing the small-capacity lens to exhaustion led somewhere I did not expect.

---

## MISSING CAPABILITY

**A live forgone-yield meter on every non-deployed dollar and every clamp — denominated in the best yield *reachable at this account size*, which is a rule-capped band structurally forbidden to a tier-1 desk.** The desk prices what its capital *loses*. It has never priced what its capital *fails to earn while doing nothing*.

## WHY IT IS INVISIBLE TODAY

**A flat book generates no rows, and every meter here is trade-driven.** No fills → no TCA, no drawdown, no fee, no P&L line. `data/fee_burn_window.json` proves it: 15 samples across all of 2026-08-05, all identical (`funding 113.06, commission 1750.88`). Nothing changes, so nothing alarms.

The proof that the blindness is total is the fence built for exactly this law. `data/utilisation.json` is L1.28a's idle-capital fence, and today it reports:

```
"name": "deployed_capital", "limit": 13151.52, "used": 13151.52,
"utilisation": 1.0, "status": "SATURATED"
```

Three things are wrong at once and each hides the next. (1) `web/cashcarry_live.json` reads `n_carries: 0, deployed_notional: 0.0` — **the book holds zero positions.** (2) `_capital()` (`scripts/check_utilisation.py:103`) feeds the same equity figure to both limit and numerator, so the ratio is ≡1.0 by construction. (3) That figure is `molded_curve_usd` from `data/nav_attestation.jsonl`, whose own `_note` says *"a MOLDED/SIMULATED curve, not venue truth and not a track record"* — all 13/13 attestation rows are `mode: "PAPER (testnet) -- pre-Gate-0"`, and `data/LIVE_ENABLE` / `data/LIVE_VPS_VERIFIED` do not exist. **The desk's idleness fence reports full saturation of a simulated number on a book with no positions.** Point (2) is in my notes from the 2026-08-01 infra sweep; points (1) and (3) are not, and fixing (2) alone would leave the fence measuring a paper book.

Then the second layer: even a correct reading would be dismissed. L1.28a exempts idle headroom held by a survival rail — and `pause_opens` is a rail. Without a price tag the exemption is permanent and free.

## MECHANISM

`scripts/run_idle_cost.py` → `data/idle_cost.json`, plus `libs/research/idle_yield.py` as the single leaf that owns the reachable-yield floor (the `capacity_policy.py` pattern — one definition, no per-caller copies).

1. **Reachable-yield floor** = `max(risk_free, best stablecoin supply APY reachable at this book size)` − the desk's own mandated haircut. Both inputs already exist and are already collected: `data/hurdle_rate.json` (`risk_free = 0.34663%` over 33.92d ≈ 3.73%/yr) and `data/defi_lending.jsonl` (Aave/Compound/Morpho/Spark, hourly, 12.9 MB). Reuse `screen_collateral_allocation.py`'s `DEFAULT_HAIRCUT_BPS = 300.0` verbatim — no new risk judgement is introduced, and the haircut floor stays non-zero by refusal.
2. **Idle principal** = attested equity − `deployed_notional`, read via `libs.ops.fresh.read_fresh` (L1.44), and **refuse to compute on a `mode: PAPER` attestation** — emit `UNMEASURABLE-PAPER-BOOK` rather than a number. A simulated denominator is what welded the existing fence.
3. **Clamp register**: every active clamp (`risk.action`, `ramp.size_fraction` rung, bleed denylist, L1.38 freeze window, undeployed forward clocks) gets `{clamp, since, idle_usd, usd_per_day, cumulative_usd, lifting_condition}`.
4. **Fence status values** (`scripts/check_idle_cost.py`): `OK` (idle < 1 slice) · `PRICED` (idle, cost published, lifting condition named) · `UNPRICED` — a clamp with no `usd_per_day`, which is the L1.28a/anti-timidity breach · `UNMEASURABLE-PAPER-BOOK` · `STALE`. Never a *veto* — it publishes a number, it does not lift a rail. Registered in `_GOVERNED` per L1.41, `guard()` at top of `main()` per L1.42.
5. **The cascade wiring**: `usd_per_day` joins each `deferred(DATE)` row in `docs/GAP_REGISTER.md` and each `SCHEDULED` ledger row, so every delay carries an accruing dollar figure next to its ROI estimate.

## WHAT IT WOULD HAVE CAUGHT

**Right now, today, unreported.** The book has held zero positions since 2026-08-01 (`dd_from_peak_pct -17.64`, `pause_opens`) — and no live capital has *ever* been deployed: `LIVE_ENABLE` absent, 13/13 attestation days pre-Gate-0. The meter would print `UNMEASURABLE-PAPER-BOOK` against a real principal-signed inception of **$5,757.08** (`data/capital_events.jsonl`, authorised by zaid), which is the honest and much louder statement.

And the number that reframes the sleeve: `data/hurdle_rate.json` shows `funding = 113.06` against `implied_costs = 1973.57` over 34 days — **and that $113 is testnet.** Real funding harvested to date: $0. Real risk-free forgone on $5,757 over the same window: ≈**$20** (≈$215/yr; ≈$490/yr if the book reaches $13k). Estimate, not fact — the exact figure depends on where the real balance sits, which is itself unattested. **The desk's realised alpha is zero and its idle cost is real, and only one of those two numbers is currently computed.**

## ROI

Direct: **~$215–490/yr at current equity**, near-riskless, zero spread crossing — set against a sleeve whose entire *lifetime gross* harvest is $113 (testnet) and whose cost/funding ratio is **15.5x**. Net of the desk's own 300bps haircut it is still ~2x the sleeve's lifetime gross.

Cascade, which is the larger half: it puts a price on **the clock**. L1.27 requires every delay to answer "protecting capital, or avoiding uncertainty?" and the doctrine puts the burden of proof on the conservative choice — *"a clamp must cite QUANTIFIED ruin risk"*. Today no clamp on this desk carries a dollar figure, so that adjudication is rhetorical every time. This multiplies: the 105 past-due ledger rows, the `deferred(2026-08-12/19)` register rows, the ramp pinned at the 0.10 floor, the 12 forward clocks, Gate 0 itself. Timidity is the one cost the constitution insists be *"reported as loudly as a risk breach"* and it is the only one with no number.

Small-capacity leg (L1.18a, the purest instance I found): the yield band reachable here — per-account promotional stablecoin tiers and small lending pools — is capped **by rule** in the low thousands of dollars. Not "unattractive at size"; *forbidden* at size. The whole book fits inside the cap.

## COST

~6–9h build (both artifacts + fence + tests + `_GOVERNED` registration); ~0 maintenance (both inputs are already-scheduled collectors). Competes with: the 105 past-due ledger rows (repair-mode is on, `arrival 47.4/day vs disposition 20.9/day`), and the cost-surface underpower (12 usable fills vs `MIN_FILLS_FOR_RAMP=30`). **I rank the ramp/cost-surface work higher on direct EV** — it unblocks a pinned gate — but this is the higher *second-order* item (L1.15): it prices every future delay, including that one. It moves no capital; the allocation itself stays a principal decision with a number attached.

## FALSIFIER

Two, either one kills it. (a) The real balance is already earning ≥ the reachable floor at its custody location — then the meter measures a constant zero and is pure overhead; **check this first, it is one question to the principal and costs nothing.** (b) The measured reachable APY net of a *derived* (not assumed) haircut is < the risk-free rate the desk already uses — then `hurdle_rate.py` plus one scalar is sufficient and no new organ is warranted.

**NOVELTY-CHECK:** `grep -rilE "idle_yield|reachable_yield|clamp_cost|carrying cost|forgone_yield|foregone_yield|yield_floor|opportunity_cost_usd" libs scripts docs data` → **empty**; `grep -rilE "days_flat|time_flat|flat_since|zero_position|days_since_last_fill" libs scripts` → **empty**; ledger scan of all 369 rows for `idle collateral|yield on cash|stablecoin yield|while paused|forgone` → **0 rows**. Nearest neighbours, each checked and each a different question: `hurdle_rate.py` (ex-post scorecard of the *strategy's* return; cannot distinguish losing to T-bills *while trading* from *while flat*), R0120/`screen_collateral_allocation.py` (carry-vs-lending as *alternatives*; silent on the third state the book is actually in — neither), R0037 (detects absorbing rail states, does not price them), `desk_economics.Hurdle` (burn-rate *cost* hurdle, not an *opportunity* one), `check_utilisation.py` (measures the ceiling, welded to 1.0, fed a molded curve).

---

## BRAINSTORM

Everything below is raw generation from this run's evidence — not novelty-checked, for the builder to row and screen.

1. **Perp-vs-perp carry, no spot leg** — `data/cost_model.json` measures 1000CATUSDT `spot_buy` median **36.1bps** vs `fut_sell` **3.6bps** at $100, and spot is *flat* across $100→$2500 (pure spread; being small does not help). The spot leg is ~90% of the cost. `screen_funding_spread.py` (R0115) exists but its docstring explicitly puts the execution construction out of scope — that's the gap. — **S** — ledger.
2. **Rank carry candidates on funding NET of the modelled per-symbol spread** — funding richness and spot-book width are the same latent variable ("nobody wants to hold this"), so ranking on gross funding is adverse selection by construction; verify the ranker joins `cost_model.json` at *selection*, not just at execution. — **S** — fence.
3. **Negative funding is structurally unreachable** — `cost_model.json` has only `spot_buy`/`fut_sell`; there is no short-basis expression, so ~half the funding distribution (ARBUSDT −8.9e-05, PAXGUSDT −1.3e-05 in `cost_hunt.json`) is unharvestable. — **A** — ledger.
4. **Is the sleeve viable at all at the real book size?** — `carry_viability.py` exists; run it against the principal-signed **$5,757**, not the molded $13,151. At a 10% slice ($575) the cost model puts pair round-trip near 88bps. — **S** — ledger.
5. **Testnet↔live parity is unmeasured** — 13/13 attestation days are PAPER, so every spread, slippage and fill-rate number the desk owns comes from a testnet book with synthetic depth. Sim/prod parity is the named HRT/Jump T1 benchmark and has no row. — **S** — TIER1 register.
6. **Deribit surface has never been read** (`libs/research/cro_role.py:357`) — a daily-collected options-vol dataset with zero consumers; VRP is direction-agnostic, and the desk's own lesson says vol is predictable while direction is not. — **A** — axis watchlist.
7. **`fundingIntervalHours` has zero occurrences repo-wide** — Binance sets 4h on many high-funding alts, so `/8.0` under-counts *exactly the best names* by 2x. — **S** — fence.
8. **Funding-phase execution** — L1.47 measured 22.3% of closes walking away within an hour of a settlement already borne ~8h of basis risk for: **9.2% of all booked funding revenue** on the only deployed sleeve, at zero risk to fix. — **S** — ledger.
9. **BNB fee-token discount** — 10–25% off, costs only a small held balance, on a book whose fee/funding ratio is **15.5x**. — **A** — ledger.
10. **Rung-0 fee frontier** — enumerate every venue's VIP-0 maker/taker. The venues cheapest at rung 0 are cheap *because* they are small (they buy retail flow); their thin depth is disqualifying at size and irrelevant at $100/slice. — **A** — ledger.
11. **Maker fill-rate on opens** — the executor is "patient on opens" for the rebate (`run_cashcarry_executor.py:1731`) and `execution_bottleneck.py` notes every fallback converts a rebate into a taker fee; nothing publishes the achieved maker share. — **A** — fence.
12. **Venue-subsidy / rebate rent** — `mechanism_census.py:263-277` catalogues it and names the missing input as *"own-fill records proving the rebate tier is reachable at the desk's size"* — i.e. a mechanism catalogued and never tested, whose only open question *is* the small-capacity question. — **A** — ledger.
13. **The 45-symbol recorder cap silently defines the tradeable universe** — only recorded symbols can be cost-measured (`excitation.py:12`) and only cost-measured ones can be traded (R0251). The tail is the edge and the tail is exactly what the cap excludes: an L1.45 exclusion cycle with no path back. — **S** — gap register.
14. **Aster + Lighter funding, 34MB on disk back to 2021-08 / 2025-01** — the perp-DEX tail is the definitional small-capacity band; confirm it has been screened, not just collected. — **A** — axis watchlist.
15. **Hyperliquid leaderboard = counterparty-identified position transparency** — no CEX offers it; structurally unbuyable, already collected. — **A** — axis watchlist.
16. **Kalshi has no collector** while Polymarket does — a regulated USD venue with different participants and **per-account position limits** (rule-capped = ours by construction). Cross-venue probability spread. — **A** — axis watchlist.
17. **Airdrop/claim calendars** — universe-map row 72, catalogued and never built; dated public forced-seller flow, and the event-study harness already exists. §13 gate first. — **B** — axis watchlist.
18. **DeFi liquidation events** — universe map residual gap #8 concedes the liquidation stream is CEX-perp-only (Bybit), so the whole BIS DeFi-liquidation family is untestable. On-chain liquidations are free. — **A** — axis watchlist.
19. **Coin-margined / inverse perps** — 6 legacy `*USD` names, docs-only; different funding mechanism, smaller stickier participant base. — **B** — axis watchlist.
20. **Re-open dated futures on observation count, not instrument count** — killed for "breadth of 2", but L1.48 says evidence is the clock and calendar basis on BTC+ETH generates observations continuously. — **B** — graveyard re-entry (L1.16a: name the enabling change).
21. **Stablecoin cross-pair micro-band** — USDC/USDT/FDUSD/DAI quoted spot pairs; a $200 slice round-trips a 5–10bp depeg no institution can touch at size. — **B** — axis watchlist.
22. **The 300bps lending haircut is undrived** — `DEFAULT_HAIRCUT_BPS = 300.0` with no derivation, and it is large enough to kill the entire band single-handed. Derive from actual depeg/exploit base rates. — **A** — ledger.
23. **`defi_lending.jsonl` is a cross-section, not a series** — 39k rows over 8 distinct days (R0042). DefiLlama serves free historical APY per pool; backfill is cheap and turns a snapshot into an axis. — **A** — ledger.
24. **Single-counterparty tail is the desk's own named largest unpriced risk** — Alameda's death. `BYBIT_SECOND_VENUE_SPEC` §2 specs a ≤60% per-venue cap; it is spec-only, and `libs/execution/sub_accounts.py` already exists. — **S** — gap register.
25. **Sub-accounts multiply any per-account rule cap** — legitimacy/ToS check strictly first; if it fails, that is a clean documented negative. — **B** — ledger.
26. **Delisting unwinds** (§42 named ground) — `run_listing_watch.py` covers listings; the *delisting* forced-unwind side is dated, rule-driven and tiny. Note the survivorship trap: Upbit purges candles on delisting, erasing the treatment group. — **A** — axis watchlist.
27. **Regional premium venues are signal-only** — KR/JP/BR are collected but have no order path and face capital controls; verify nothing scores them as *tradeable* capacity. — **B** — fence.
28. **Run excitation on the testnet book now** — `cost_surface.json` is `UNDERPOWERED` at 12 usable fills vs `MIN_FILLS_FOR_RAMP=30`, so the ramp cannot advance by waiting; exercising the path pre-live buys the code-path observation for free. — **A** — ledger.
29. **Nothing watches whether our own *screens* are crowded** — R0119 detects crowding on held carry names, but funding/premium/listings are the three most-published crypto axes in existence. — **B** — fence.
30. **Deribit minimums vs our band** — 0.1 BTC contract minimums likely put options outside a $5.7k book; run the capacity check *before* funding more VRP research. — **A** — ledger.

Context is running long. Next I would have generated the **cross-venue inventory-rebalancing cost band** (whether a $200-per-venue split can even round-trip transfer fees, which decides whether *any* multi-venue idea above is reachable) — that is where the next run should resume.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
