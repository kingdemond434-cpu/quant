# COIN-M vs USDT-M CONVEXITY-DIFFERENTIAL — PRE-REGISTRATION

**Ledger row:** R0462. **Mechanism:** `coinm_usdtm_basis_convexity_rv`. **Axis:** `data_axis_watchlist`
card 31 (`98-binance-coinm-dapi`, `99-binance-coinm-vision-archive`).
**Written:** 2026-08-13, BEFORE any screen was run. **Class:** DOCTRINE-adjacent → **TERMINAL** once
the trigger below resolves (see governance note at the end).

This file exists because the standing pre-registration is a **promotion trigger, not a screen
design**. CLAUDE.md binds kill criteria BEFORE a run; the parts that were never written down are
written down here, ahead of execution, and are marked **[NEW]** so no reader can mistake them for
something the 2026-08-12 miner decided.

---

## 1. WHAT WAS ACTUALLY PRE-REGISTERED (verbatim, 2026-08-12)

From `docs/research/prospector_watchlist.md`, section
*"coinm_usdtm_basis_convexity_rv — EV-REJECTED, logged as watchlist memory (not a card)"*:

> **SINGLE PROMOTION TRIGGER (measurement, not construction-shopping):** once the COIN-M axis is
> backfilled (card 31), compute the measured quarterly basis differential minus theoretical
> convexity value, net of 2× taker fees both legs. If |residual| persists on ≥3 of 5 underlyings
> across ≥2 quarterly rolls, re-score with MEASURED est_sharpe in place of the 0.5 prior —
> measured inputs, not tag relitigation, are the only path back.

> **Mechanism:** inverse (coin-margined) futures settle PnL in coin ⇒ convex USD payoff ⇒ fair
> COIN-M basis ≠ USDT-M basis by a computable convexity adjustment (∝ σ²T). Clienteles are
> segmented by collateral custody (coin-only hedgers cannot use USDT-M), so the differential can
> sit away from fair value persistently. Trade = same-expiry basis spread, market-neutral to
> first order, 5 quarterly underlyings (BTC/ETH/BNB/SOL/XRP).

> **Strongest spurious argument (written first):** every delta-neutral basis desk already watches
> this spread; post-2022 COIN-M OI share shrank (the coin-collateral clientele thinned), so the
> residual may be exactly fee-sized — the axis measurement decides, not this card.

Prior EV gate (stands, not re-litigated here): **EV 0.0009 < 0.002 REJECT**, p_survive 0.105,
est_sharpe **0.5 (a PRIOR, not a measurement)**, breadth 5, orth 0.5, tags
`funding_family`+`crowded_known`; narrow-tag variant 0.0002.

`VARIANTS_TRIED` already on the record: (a) quarterly-convexity — scored, mechanism-true;
(b) 20-pair perp funding-differential — **named, weaker mechanism (clientele demand, not
convexity), explicitly NOT scored as a rescue.**

### 1a. What the pre-registration did NOT specify — the holes filled below

| Missing | Consequence if left open |
|---|---|
| **Direction/sign** of the residual | a two-sided read is a free extra trial |
| **Window / sampling frequency** | window-shopping is data-mining our own collector (L1.42/§42) |
| Definition of **"persists"** | "persists" with no threshold is unfalsifiable |
| The **σ estimator** behind σ²T | choosing the estimator after seeing the residual is a fork |
| **Fee numbers** for "2× taker fees both legs" | an unstated cost bar can be tuned to the answer |
| **Any screen at all** (signal → target → horizon) | the trigger is a MEASUREMENT; `axis_screen` needs a design |

---

## 2. MEASURED BEFORE THE SCREEN: the trigger's breadth clause is UNSATISFIABLE

This is a **universe measurement** (what instruments exist), executed before any screen was
designed or run, so it is not a look at the answer. Method: paginated S3 listing of
`data.binance.vision` (continuation-token followed to `IsTruncated=false` — the recorded
MaxKeys=1000 truncation failure mode, `99-binance-coinm-vision-archive`), plus live
`exchangeInfo` on both books.

    COIN-M (cm) archive: 272 kline symbols | 222 quarterlies over 14 roots | 50 perps
    USDT-M (um) archive: 986 kline symbols |  50 quarterlies over  3 roots | 0 "_PERP" spelling

    cm quarterly roots (14): ADAUSD BCHUSD BNBUSD BTCUSD DOTUSD EOSUSD ETCUSD ETHUSD
                             FILUSD LINKUSD LTCUSD SOLUSD TRXUSD XRPUSD
    um quarterly roots (3):  BTCBUSD  BTCUSDT  ETHUSDT

**Binance has never listed a USDT-M quarterly for BNB, SOL or XRP — not live, not in the full
archive.** The pre-registered construction is a **same-expiry** COIN-M-vs-USDT-M spread. Three of
its five named underlyings therefore have **no second leg that has ever existed**.

    MATCHED same-expiry pairs, whole archive:
      BTC  24 expiries  210326 .. 261225
      ETH  24 expiries  210326 .. 261225
      BNB   0     SOL   0     XRP   0

> **The "≥3 of 5 underlyings" clause cannot fire at any residual magnitude. The measured ceiling
> is 2 of 5.** This is a DESIGN kill on the trigger's breadth clause, not a result — nothing
> about the residual is known at the time of writing. It is L1.25's `unmeasurable_by_construction`
> shape, and it is recorded as such: the mechanism is NOT refuted by it.

The other half of the clause — **"across ≥2 quarterly rolls"** — is satisfiable with enormous
room: 24 rolls per underlying, 2021-03-26 → 2026-12-25.

**Second, independent collector constraint found this run (extends card 31's):** card 31 warns
against building the universe from `exchangeInfo`. Measured today, the constraint is stronger —
**the dapi kline endpoint itself refuses expired symbols**:

    GET /dapi/v1/klines?symbol=BTCUSD_250926  ->  HTTP 400 {"code":-1121,"msg":"Invalid symbol."}
    GET /fapi/v1/klines?symbol=BTCUSDT_250926 ->  HTTP 200, data

So COIN-M expired-quarterly history is **archive-only**, on both the universe axis and the price
axis, while USDT-M serves its own expired contracts over REST. A collector that reached for REST
symmetrically would have read "COIN-M has no quarterly history" and been wrong.

---

## 3. THE DESIGN THAT WILL BE RUN — fixed before execution **[NEW]**

Because 3 of 5 underlyings are structurally absent, the trigger is run **at its measured maximum
breadth (2 of 5)** and its verdict is reported against the honest denominator. **Clearing "2 of 2"
does NOT satisfy "≥3 of 5" and will not be reported as if it did.**

### 3.1 Quantities

Per underlying `u ∈ {BTC, ETH}` and matched expiry `e`, on each UTC day `d` where both legs trade:

    b_cm(d,e)  = ln( F_cm(d,e)  / S_cm(d)  )       COIN-M  log basis   (S_cm = dapi index, coin/USD)
    b_um(d,e)  = ln( F_um(d,e)  / S_um(d)  )       USDT-M  log basis   (S_um = fapi index, coin/USDT)
    T(d,e)     = (deliveryDate - d) / 365.0        years to expiry
    D(d,e)     = b_cm - b_um                       the measured LOG basis differential
    D_ann      = D / T                             annualised

### 3.2 The theoretical convexity value — estimator fixed NOW **[NEW]**

The card specifies "∝ σ²T" and nothing else. Fixed here:

    convexity_theory(d,e) = -sigma(d)^2 * T(d,e)          [log-basis units]
    convexity_theory_ann  = -sigma(d)^2                   [annualised]

`sigma(d)` = **annualised realised vol from a 30-day trailing window of daily log returns of the
COIN-M index `S_cm`, × sqrt(365)**. 30d/daily/index-leg is chosen for one stated reason and is not
swept: it is the shortest window that is not dominated by estimation noise at daily sampling, and
the index is the leg both books share a definition of. **Any other window would be a fork and is
forbidden by this document.**

Sign derivation, stated so the reader can check it rather than trust it: with `S_T` lognormal and
`E[S_T] = F_lin`, Jensen gives `E[1/S_T] = e^{σ²T}/F_lin`. An inverse contract quoted so that
`1/F_inv = E[1/S_T]` therefore prices `F_inv = F_lin·e^{-σ²T}` — **COIN-M basis should sit BELOW
USDT-M basis by σ²T.**

**HONEST CAVEAT, WRITTEN BEFORE THE RESULT.** Under the exact coin-numeraire change of measure the
first-order convexity term *cancels* (`E^coin[1/S_T] = 1/(S₀e^{(r-q)T})` ⇒ `F_inv = F_lin`), so the
σ²T form is the **practitioner** adjustment the card names, not a theorem. The measurement is
therefore reported against **both** nulls, declared here in advance and both counted as trials:

    NULL-A (pre-registered, the card's):  residual = D_ann - (-sigma^2)  =  D_ann + sigma^2
    NULL-B (zero-adjustment control):     residual = D_ann - 0           =  D_ann

### 3.3 Cost bar — fixed NOW **[NEW]**

"2× taker fees both legs" = 4 taker crossings (in and out, two legs). Using the desk's own published
constant `scripts/resolve_paper_book.TAKER_FEE = 0.00045` (Binance non-VIP taker, 4.5 bps/side) —
**imported, not re-typed, and not loosened**:

    cost_roundtrip = 4 * 0.00045 = 0.0018          (18 bps of spread notional)
    cost_ann(d,e)  = 0.0018 / T(d,e)               charged over the actual holding horizon

A slippage-inclusive reading (`+4*SLIPPAGE`) is computed as a **declared robustness variant** and
may only ever TIGHTEN the verdict. It is not a rescue path.

### 3.4 "Persists" — defined NOW **[NEW]**

For an (underlying, expiry) contract to count as a **persistent** residual:

    frac_days(|residual_ann| > cost_ann)  >=  0.60   of that contract's observed days
    AND the contract has >= 30 observed days
    AND the residual's SIGN is stable on >= 80% of those days (a sign-flipping residual is not
        a tradeable clientele premium; it is noise around fair value)

An **underlying** counts as persistent if ≥2 of its expiries qualify (the "≥2 quarterly rolls"
clause). Thresholds 0.60 / 30 / 0.80 are set here, before the numbers are seen, and are not swept.

### 3.5 The SCREEN — design fixed NOW **[NEW]**

The trigger is a measurement; the SCREEN-ON-DISCOVERY duty additionally requires an `axis_screen`
verdict. Harness: `libs.research.axis_screen` only (never hand-rolled). Two constructions, both
declared in advance, **both counted as trials, neither reported as "the" result**:

**C1 — convexity residual → basis-differential convergence (the mechanism-true one).**
* **signal[t]** = `residual_ann(t)` under NULL-A, per contract.
* **target_ret[t]** = `D(t) - D(t-1)`, the change in the *unannualised* log differential realised
  over period t. This is the P&L of a **unit short position in the spread**, sign-flipped at read
  time by the harness's own momentum/reversal split.
* **Predicted direction: REVERSAL.** A positive residual (COIN-M rich vs convexity-fair) should be
  followed by a *fall* in D. `sharpe_reversal` is the pre-registered read; `sharpe_momentum` is
  reported but a momentum-only pass is **not** a confirmation of this mechanism.
* **Panel:** columns = (underlying × contract-slot), slot ∈ {front, next}. K = 4.
* **Horizon:** 1 day, `overlap_periods=1.0` (targets are non-overlapping daily first differences).

**C2 — perp funding differential (the secondary unlock; named in the card as the WEAKER mechanism).**
* **signal[t]** = `funding_cm(t) - funding_um(t)`, 8h-stamp funding differential per matched root.
* **target_ret[t]** = next-period differential change, same convergence logic.
* **Panel:** the 20 COIN-M perps matched to their USDT-M counterparts. K = 20.
* This is **not** a rescue for C1 and will not be reported as one. It is the CN miner's
  synthetic-dollar-clientele prior (`8btc` thread-172717), which is a *demand* story, not convexity.

**L1.62 binds:** both are panels, so `xs_neff` comes from
`libs.research.panel_breadth.measure_panel_breadth` **on this panel**, never assumed. An unmeasured
panel is stamped `breadth_basis: UNMEASURED`, can never be `powered`, and therefore can never
produce the graveyard-grade `SCREEN-WEAK`.

### 3.6 TIMESTAMP ALIGNMENT + LOOK-AHEAD DECLARATION (mandatory, L1.46)

* Both legs are Binance-native and both are stamped by **the venue's own clock** (`open_time`,
  ms epoch, UTC, bar-OPEN labelled). There is **no cross-venue clock join** in C1 or C2, which is
  the property that made kimchi/coinbase fail. The stale-leg rail in `axis_screen` still runs.
* Every collected row is written with `clock_provenance.MARKER` = `venue` and the venue stamp
  retained. Nothing in this backfill is receipt-stamped.
* **Look-ahead risks named in advance:**
  1. **Universe look-ahead** — expired contracts are taken from the ARCHIVE, so delisted/expired
     instruments are present and the universe is point-in-time. Building it from `exchangeInfo`
     would have been a look-ahead in the UNIVERSE (card 31 / `99-binance-coinm-vision-archive`).
  2. **Index-definition asymmetry** — `S_cm` is a coin/**USD** index, `S_um` a coin/**USDT** index.
     `D` therefore contains the **USDT-vs-USD basis**. This is declared as a KNOWN CONFOUND, not
     netted out: it is part of the CN miner's demand-side story and cannot be separated with the
     data collected here.
  3. **Delivery-window microstructure** — the last days before expiry have T→0, so `D_ann` and
     `cost_ann` both explode. Contract-days with **T < 7/365** are **dropped before any statistic
     is computed**, declared here, not after inspection.
  4. **Bar-open labelling** — `signal[t]` and `target[t]` are both built from bar `t`'s own
     close-to-close quantities, and `axis_screen` shifts the target itself (`np.roll(r,-1)`).
     No manual forward shift is applied anywhere (double-shifting destroyed a true IC of 0.45 in
     the harness's own test).

---

## 4. KILL CRITERIA — binding

1. **Trigger clause (breadth):** already **DEAD ON MEASUREMENT** — max 2 of 5 < required 3 of 5.
   No residual magnitude can revive it. Re-scoring `est_sharpe` from a 2-of-5 measurement is
   **forbidden**; the EV REJECT at 0.0009 stands regardless of what section 3.4 returns.
2. **C1/C2 screen:** the `axis_screen` verdict is the verdict. `SCREEN-WEAK` is recorded as
   graveyard-grade **only if `powered` is true with `breadth_basis: MEASURED`**. `SCREEN-UNDERPOWERED`
   is recorded as UNMEASURED (L1.28a) and refutes nothing.
3. **`SUSPECT-LOOKAHEAD` or `SUSPECT-STALE-LEG` on any cell** ⇒ that cell is an artifact, earns no
   clock, and the collector is re-audited before anything is claimed.
4. **No promotion under any outcome.** Stage A has zero promotion authority; the ceiling is a
   pre-registered forward clock. Not a cent.
5. **Trial count is the denominator.** NULL-A/NULL-B × C1/C2 × the harness's own cells are ALL
   counted and ALL reported. Reporting a best cell without `n_trials` is a forking-paths result.

---

## 5. GOVERNANCE

Class **TERMINAL** (`docs/research/ARTIFACT_GOVERNANCE.md`): this is the record of one
pre-registration for one mechanism. It has no producer and no cadence — a clock cannot make a
pre-registration true — and a staleness floor on it would be theatre. **Superseding condition, by
name:** if Binance ever lists a USDT-M quarterly for BNB, SOL or XRP, section 2's structural kill
expires and a NEW pre-registration must supersede this file by name before the trigger is re-run.
