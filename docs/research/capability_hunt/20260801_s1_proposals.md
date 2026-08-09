# CAPABILITY HUNT PROPOSALS 20260801 slot 1

LENS: CAPACITY & COMPOUNDING -- what lets the book carry more risk-adjusted size or compound FASTER: a decorrelated sleeve, a cost-tier cut (every bp is pure CAGR), a funding-harvest cadence, a capacity band we are leaving on the table.

## A -- Claude family

## MISSING CAPABILITY

**Funding-settlement PHASE as a control variable.** The desk has optimised *how long* to hold a carry (two dedicated organs: `scripts/hold_optimizer.py`, `scripts/optimal_hold.py`) and has never once asked *where in the 8h funding cycle* to open or close it. Phase is a free coordinate with the same P&L units as duration, it is fully under the desk's control, and no code, fence, or ledger row touches it.

## WHY IT IS INVISIBLE TODAY

Three layers hide it, and each is individually reasonable:

1. **The mark is a continuous accrual of a discrete payment.** `run_cashcarry_executor.py:870` — `est_funding = funding * notl * (held / 8.0)`. Funding is paid at 00/08/16 UTC only. This booking is *unbiased in expectation* (I measured mean delta **−0.013 settlements** over 265 closes), which is exactly why it has survived review — but its per-trade error is **sd 0.481 settlements**, and `est_funding` flows straight into `net` (`:876`), which is the field `run_trade_forensics` buckets. The accounting cannot show the coin flip because it books the expectation.
2. **Realised funding exists only as a book-level scalar.** `binance_live.py:251` — `elif t == "FUNDING_FEE": out["funding"] += amt`. No symbol key, no per-position attribution. `carry_accounting.py:181` then does `non_funding = real_net - funding`, so any phase error lands in the **execution** bucket at book level.
3. **The clock is fetched and discarded.** `crypto_source.py:144` calls `/fapi/v1/premiumIndex` and keeps one field: `{d["symbol"]: float(d.get("lastFundingRate", 0.0))}`. `nextFundingTime` arrives in that same payload, every cycle, and is thrown away. `nextFundingTime` has **zero occurrences** in `scripts/` or `libs/`.

## MECHANISM

- `libs/execution/funding_clock.py` — `next_settlement(t, sym)`, `settlements_in(t0, t1, sym)`; single-sources the `3*365` constant currently hardcoded at 9 sites (`tail_funding.py:27`, `run_live_combined.py:257`, `run_shadow_8h.py:39`, …), same pattern as `capacity_policy.py` under §42.
- Executor: `_entry_gate:466` `periods = max(1.0, min_hold_h/8.0)` → actual settlements in the prospective window; `_churn_guard:344` gains a phase term (hold past an imminent stamp when funding > 0); `est_funding` logged **twice** — discrete and continuous — so the delta becomes a measured quantity.
- Ground truth: `funding_events()` as a ~15-line twin of the working `commission_events()` (`binance_testnet.py:269`), attributed into `[opened, closed]` spans by the existing matcher at `run_trade_forensics.py:105`. `_income_rows(symbol=…)` is currently called with `"COMMISSION"` only.
- Artifact `data/funding_capture.json`; fence `scripts/check_funding_capture.py` → `NO-DATA` / `UNMEASURED` (no per-position truth — never OK) / `PHASE-BLIND` / `FORFEITING` / `OK`.

## WHAT IT WOULD HAVE CAUGHT — measured today on 265 real closes

```
close phase octiles (0 = just after a stamp, 7 = final hour before one), uniform = 33.1, sd 5.4
  opens  [21, 42, 14, 28, 28, 41, 26, 65]   <- octile 7 = +5.9 sigma
  closes [15, 21, 54, 15, 15, 44, 42, 59]   <- octile 7 = +4.8 sigma
```

**The executor's schedule is already phase-locked to the hour before settlement — the optimal phase for opens and the worst possible phase for closes.** 59 closes (22%) walked away within 60 minutes of a payment they had already borne ~8h of basis risk to earn. Nobody chose this; nobody has ever looked. Separately, **110/265 closes (41.5%) are mis-marked by ≥ half a settlement** and **58 closes booked funding while capturing zero settlements**.

This is the direct, unnamed fourth candidate for R0219's open localisation — *"~66 bps therefore sits in execution/accounting… next repair hour goes to decomposing that gap against trade_forensics + tca"*. That repair hour is about to be spent inside a decomposition built on `est_funding`, which is phase-free by construction, so a phase error cannot be found there. At R0219's own +7.77 bps/day paper-gross, one settlement is **2.59 bps of notional** — 33% of a 24h hold's entire gross revenue, currently decided by cron alignment.

## ROI

Direct: making closes settlement-aware converts an unbiased coin flip into systematic `ceil(H/8)` capture ≈ **+0.5 settlements/rotation ≈ +1.3 bps of notional per rotation**, at zero incremental capital and at most 8h of extra hold *during which the position also earns* — on the revenue line of the **only deployed sleeve**. Cascade: (a) de-noises the evidence surface *before* R0219's repair hour is spent; (b) supplies the clock R0250's revenue reconciliation needs; (c) makes R0121 (cross-venue interval arbitrage) buildable — you cannot arbitrage calendars you do not model; (d) the adverse-selection test (is the pre-stamp window worse-quoted?) runs entirely on `data/moat`'s 7.1 GB Binance-fut depth tape, which per R0203 has had **zero screens ever run on it**.

## COST

~6–8h: clock module 1h, executor wiring 2h, `funding_events()` 1h, fence + artifact 2h, phase/depth screen 2h. Maintenance ≈ 0 (pure function + one fence). Competes with R0219's scheduled repair hour — and **that is the argument for doing it first**, not against.

## FALSIFIER

Per-position `FUNDING_FEE` truth shows realised settlements matching `held/8.0` within noise (i.e. Binance accrues continuously, not discretely) — that kills it outright. Weaker kill: the pre-stamp depth screen shows spread/impact in the T-minus window costs more than 2.59 bps, making the capture unharvestable. Also: if rails/panic force most closes, phase is not actually controllable — measurable from the existing close reasons.

**NOVELTY-CHECK:** `grep -rIn -E "nextFundingTime|settlement|phase" scripts/run_cashcarry_executor.py libs/execution/*.py` → **empty**; `grep -lIn -i funding scripts/check_*.py` → **0 of 30 fences**; ledger regex `captur|forfeit|phase|settlement|stamp` → 26 hits, none about capture phase (R0121 = cross-venue interval *arbitrage*; R0250 = revenue reconciliation, names neither cause nor lever; R0219 lists three gap candidates, not this one); `hold_optimizer.py:56` and `optimal_hold.py` both search duration only via `fund = n * f * (h/8.0)`.

*Honesty caveat I will not paper over: the settlements-captured P&L cut (0→−9.82, 1→+29.65, 2→−38.07, 3→+31.37 bps) is notional-weighted, small-n, and contaminated by the churn-loop fee fire (R0285, 1,746 commissions). I stand behind the arithmetic and phase facts, which are contamination-free; not behind that gradient.*

---

## BRAINSTORM

1. **`fundingIntervalHours` has zero occurrences repo-wide** — Binance sets funding interval per symbol (4h for high-funding alts); every `/8.0` and `3*365` assumes uniform 8h, so the entry gate under-ranks by 2× exactly the highest-funding names, and `_FUNDING_PANIC = -0.0005 # per-8h` lets the desk hold through 2× the bleed it thinks. **S** → money-path fix + ledger.
2. **The premiumIndex payload is fetched every cycle and 90% discarded** (`crypto_source.py:144`) — it carries both the settlement clock *and* the running premium accumulating toward the next print, which is a strictly better next-funding forecast than `lastFundingRate`. R0252 names the martingale assumption; nothing names the free replacement already in hand. **S** → executor.
3. **Funding N_eff of the carry cross-section is never measured.** The desk measured return N_eff (1.54 raw / 29 neutral) but carry income is *funding* correlation, not return correlation — all 12 legs track one leverage-demand cycle. If funding N_eff ≈ 2, Kelly is sized on phantom breadth. **S** → ledger + `cohort_independence`.
4. **Do our rails fire when execution is most expensive?** (LTCM's death.) Basis-stop / ADL / panic closes are forced exits; nothing measures their fill cost *conditional on market state*. If rails cluster with basis widening, the stop distance is mispriced. **S** → fence.
5. **Live-constant evidence freshness fence.** L1.44 contracts freshness for artifact *reads*; nothing contracts it for the evidence behind a hardcoded constant. `_MIN_HOLD_H=24`'s justifying comment cites ">24h earns +16.9 bps"; today's 265 closes read **−4.20 bps** for that bucket. Every money-path constant carries its artifact + date and fires on staleness or sign flip. **S** → new fence.
6. **`bnb-burn-unfunded` is an ack whose condition has expired.** Acked as "testnet limitation"; at live it is ~25% off the desk's largest cost line, silently, with the flag reading ON. Nothing re-opens an ack when its stated condition changes. **A** → the general class is *acks with no expiry trigger*.
7. **est_funding uses entry cost basis** (`notl = spot_qty * spot_cost`, `:869`) while funding is paid on *mark* notional at each stamp — a third accounting error stacked on the phase error, growing with price drift. **A** → executor.
8. **Does the executor check `status` before opening?** R0292 found 123 perps with a real `deliveryDate`, all `status=SETTLING`. A carry opened on a settling symbol eats a forced close. **A** → money-path safety.
9. **`_PM_EFFICIENCY = 1.8`** (`run_capital_plan.py:25`) — a magic number standing in for a venue-published margin quantity, setting the entire capacity plan, never reconciled. **B** → venue-parameter drift fence (same class as 1, 6).
10. **Venue-parameter drift fence (the general form of 1, 9, and Binance funding caps).** Every money-path constant shadowing a venue-published field reconciled daily: `DRIFTED` / `UNVERIFIABLE` / `OK`. One fence covers a class. **S** → new fence.
11. **Idle collateral earns zero.** `screen_collateral_allocation.py` frames carry-vs-lending as an either/or for the *whole* base and never applies supply APY to the unallocated residual; last NAV row reads `deployed_notional: 0`. **A** → ledger.
12. **Ruin and CAGR are computed on different time bases.** `growth_leverage.py:57` strips flat days (`a = a[a != 0.0]`) inside `risk_of_ruin`'s bootstrap only, while `cagr` counts them. Distinct from R0286 (252-vs-365). **A** → fix.
13. **Return on capital *employed* does not exist.** `live_book.py:178` publishes return on *allocated*; `pre_filter.py:40` computes the active fraction and discards it. A sleeve in the market 20% of the time is having its Sharpe understated and its safe leverage under-set. **A** → metrics.
14. **Maker-patience keyed on time-to-stamp.** 24.2% maker fill pays 96.5% of fees (R0219); patience is nearly free early in the funding cycle and expensive near the stamp. Unifies the fee problem with idea #1 of the deep proposal. **S** → executor.
15. **Adverse selection *at* the stamp** — markout conditioned on minutes-to-settlement, not R0249's generic markout. If snipers crowd the pre-stamp window, our maker quotes there are picked off. Testable on `data/moat`. **A**.
16. **`data/funding_persistence.json` is 552 bytes and 5 days stale** — an organ producing a number no consumer reads (L1.43 quiet detector). Funding *persistence* should rank the entry gate; today it ranks on level alone, so a symbol whose funding flips sign costs a full round trip. **A**.
17. **Executor loop period vs the 8h forcing function.** L1.46 caught recorder period drift; the same aliasing question one level up decides whether the desk can even *land* in a chosen phase window. Measurable from inter-trade spacing in the existing log. **B**.
18. **What sets `top`** (`if len(pos) >= top`)? It caps the number of concurrent bets, and IR = IC·√N. Was it ever optimised against measured funding correlation (#3), or is it a constant? **A**.
19. **Compounding transmission lag** — `_compounded_capital` reads daily NAV attestation while positions rotate hourly, so realised gains take up to 24h to become size. Classic lag in a compounding controller's feedback path. **B**.
20. **Quarterly-vs-perp calendar spread as a decorrelated sleeve** — term-structure premium is a *different* risk premium from perp funding, same venue, same margin, same infrastructure, and the desk's only repeat-survivor family is carry. **B**.
21. **Deleveraging stress test on the carry book** using the decade BitMEX funding archive already on disk (`data/bitmex_funding.jsonl`, 1.4 MB, idle). Carry income is one macro factor; the question is what it earned across the three largest historical deleveragings — a capacity question, not a risk question. **A**.
22. **Spot/perp lot-size dust accumulates as un-hedged delta** across rotations; the desk has a naked-leg incident on record and `_ERR` declared-never-read. **B**.
23. **Rail-close sizing should be phase-aware** — the same stop distance costs strictly more P&L just before a stamp than just after. **B**.
24. **Fee-tier progression as a credited output of turnover**, not only a cost — churn is currently all debit, no credit. Low value at current size, one line to check where the desk sits vs the next tier. **C**.
25. **Capture-efficiency as a ratchet metric** (realised settlements ÷ modelled), floored under L1.0/L2.0 on the day it is first measured. **B**.

Next up, had I more context: the parallel question for the **cost** side — whether `_rt_bps`'s p90 fail-closed default for unmeasured names interacts with the phase lever (a name that is only ever traded in the expensive phase records an inflated cost forever, which is L1.45's absorbing cycle wearing a clock).


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
