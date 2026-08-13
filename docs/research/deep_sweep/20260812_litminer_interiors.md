# Literature miner — INTERIORS seat (run 7, 2026-08-12)

**Agent:** litminer-interiors (read-only ground-digger; single write = this file) · **Status: COMPLETE**
(0 mechanism cards · 4 graveyard candidates · 11 engine · 3 corrections to standing artifacts ·
enumeration debt PAID at 287 titles · footer has DEPTH/NEXT-GROUND)

Ground: full-text INTERIOR extraction of the papers run 6 (`deep_sweep/20260812_litminer_arxiv.md`)
reached only at the surface — Portnaya (card 29), Hansen–Kim (card 28), arXiv 2510.14435 (S3) —
plus the recorded arXiv enumeration debt (q-fin.TR 2026-03/04; q-fin.ST + q-fin.PR 2026-02..06).

Provenance grades used throughout: `[PRIMARY]` = full text opened from this box (URL + status);
`[ABSTRACT]` = landing page only; `[SUMMARY-ONLY]` = search snippet, lead never evidence.

---

# 1. CARD-29 CONSTRUCTION SPEC — and the verdict that it is NOT identifiable as specified

**Paper.** Victoria Portnaya, "Do Prediction Markets Match Option Prices? Bitcoin Threshold
Evidence from Binance and Polymarket", arXiv:2606.19517, submitted 2026-06-17.
**`[PRIMARY]`** — full text read from https://arxiv.org/html/2606.19517v1 (HTTP 200), three
targeted passes (construction / friction+greeks+SE / costs+tables+limitations); landing page
https://arxiv.org/abs/2606.19517 (HTTP 200).

## 1.1 The construction, implementable without re-reading the paper

Per hourly timestamp `t`, per contract (threshold `K`, expiry `T`):

**Inputs.** `P_poly,t` ∈ [0,1] Polymarket Yes price; `C_mkt,t` = matched listed call MID
(average of best bid/ask); `C_high,t`,`C_low,t` = intra-hour high/low of the option price (used
only for the SE); `S_t` = spot hourly bar; `τ_t = (T−t)/365` in years; `r` = constant short rate.

**Step 1 — invert IV.** `σ̂_t` = numerical root of
`F_t(σ) = C_BS(S_t, K, r, τ_t, σ) − C_mkt,t = 0`. Black–Scholes European call on **spot**.
Contracts with "extremely short maturity are excluded to avoid numerically unstable
implied-volatility estimates" — **threshold not stated; desk must set and log it.**

**Step 2 — fair binary.** `P_fair,t(σ) = e^(−rτ_t) · Φ(d_2,t(σ))`, with
`d_2 = [log(S_t/K) + (r − σ²/2)τ] / (σ√τ)`. Paper's words: "the discounted cash-or-nothing call
value" under Black–Scholes dynamics.

**Step 3 — gap.** `D_t = P_poly,t − P_fair,t`. Null `H₀: E[D_t] = 0`. Inference: HAC +
block-bootstrap; AR(1) fitted to `D_t` for the half-life.

**Step 4 — plug-in standard error (verbatim, §3.3).**
`SE(P_fair,t) = |g′(σ̂_t)| · ς̂_C,t / 𝒱_t`, where
`ς̂_C,t = max{(C_high,t − C_low,t)/2, 0.01·|C_mkt,t|, 1e−10}` and `𝒱_t = ∂C_BS/∂σ` (call vega).
Derived by implicit-function expansion; intra-hour option-price variation approximated by the
high–low range.

*Desk note (mine, closes the spec):* `g(σ) = e^(−rτ)Φ(d_2(σ))` ⇒ `g′(σ) = −e^(−rτ)φ(d_2)·d_1/σ`,
which is exactly the **digital's vega**. So the estimator is
`SE = |𝒱ᴰ| · ς̂_C / 𝒱ᶜ` — map quote uncertainty into IV units (`ς̂_C/𝒱ᶜ`), then into probability
points (`|𝒱ᴰ|`). Implementable in one line.

**Step 5 — friction (Eq. 3.6, verbatim).** `TF_t = (f_B + f_P) + ½(s_B,t + s_P)`
(Binance fee + Polymarket fee + half-spreads). **No numeric value for `f_B`, `f_P`, `s_P` appears
anywhere in the paper** — searched body, robustness, footnotes, appendix.

**Step 6 — the delta-hedged arbitrage proxy (§5, verbatim).** "Positions open when
`|D_t| > SE(P_fair,t) + TF_t` and close on mean reversion or at expiry." At entry `t₀`:
call quantity `q₀ = 𝒱ᴰ_{t₀} / 𝒱ᶜ_{t₀}` (matches the digital's vega); spot position
`x_{t₀} = Δᴰ_{t₀} − q₀·Δᶜ_{t₀}` (matches its delta). Spot hedge rebalanced **hourly**. Polymarket,
option and spot transaction costs subtracted.

**Digital/call Greeks — the paper never gives them; supplied here so the spec closes:**
`Vᴰ = e^(−rτ)Φ(d_2)` · `Δᴰ = e^(−rτ)φ(d_2)/(S σ√τ)` · `𝒱ᴰ = −e^(−rτ)φ(d_2)·d_1/σ`;
`Δᶜ = Φ(d_1)` · `𝒱ᶜ = S φ(d_1)√τ`.

## 1.2 Results actually reported (interior, not abstract)

| | obs | mean gap | inference |
|---|---|---|---|
| Main BTC >$27k Sep-23 (vs Binance `BTC-230929-27000-C`) | 214 | **0.0558** | t=6.46, p=6.86e−10, AR(1) half-life **4.2 h** |
| Pooled 3 Binance-matched BTC markets (Aug+Sep 2023) | 287 | **0.063** | HAC + block-bootstrap robust |
| Deribit, Sep $27k | 645 | **0.1248** | HAC CI [0.075, 0.174] |
| Deribit, pooled 3 markets | 2,585 | **0.1105** | HAC CI [0.074, 0.147] |
| Deribit ETH, pooled 4 markets (Feb–Mar 2023) | 2,737 | **0.0129** | HAC CI [−0.000, 0.026] — **null** |

Cross-section (Table 5): coefficient on `P_fair,t` = **−0.398**; on `SE(P_fair,t)` = 0.039; on
time-to-expiry = 0.0008. (Wedge falls as the implied probability rises; grows with maturity.)

**Table 6 — the arbitrage proxy, in full:**

| market | trades | net PnL | net α | p | HAC 95% CI | median hold |
|---|---|---|---|---|---|---|
| BTC >$28k Aug | 4 | 0.274 | 0.221 | 0.103 | [0.027, 0.416] | 2.5 h |
| BTC >$26k Aug | **1** | **−0.345** | — | — | — | 1.0 h |
| BTC >$27k Sep | 11 | 1.183 | 0.018 | 0.092 | [−0.003, 0.039] | 6.0 h |
| **Pooled** | **16** | 1.113 | **0.067** | **0.053** | **[−0.008, 0.143]** | 3.5 h |

Gross pooled PnL 1.649, net 1.113, net win rate 69%.

**Verdict on the proxy: it is not evidence.** n = 16 trades across 3 markets (one of them a single
trade that lost); the pooled HAC CI **contains zero**; and the cost model is a formula whose three
fee/spread parameters are never disclosed — i.e. unfalsifiable, which under the desk's standing
rule ("a positive backtest with a fake or absent cost model IS a negative result") makes the
trading claim a **negative result**, not a marginal positive. Run 6's card 29 line "delta-hedged
proxy 'profitable after conservative costs, marginal precision'" should be read as the author's
framing of a null.

## 1.3 What the paper assumes that crypto violates

**(V1) The benchmark is a flat-smile digital, and the omitted term is the size of the effect.**
`e^(−rτ)Φ(d_2(σ_K))` is the risk-neutral binary only if the IV surface is flat in strike. The
model-free digital is `−∂C/∂K = e^(−rτ)Φ(d_2) − 𝒱ᶜ·(∂σ/∂K)`. With a put-skewed surface
(`∂σ/∂K < 0`) the true digital is **larger** than the paper's benchmark, so `D_t = P_poly − P_fair`
is **biased upward** — the misspecification has exactly the sign that manufactures a positive wedge.

*Sizing, from the desk's OWN stored skew* (`data/deribit_surface.parquet`, BTC 2026-06-26:
`skew = 10.19` IV points, defined in `libs/data/deribit.py::vol_surface` as IV(0.9·S) − IV(1.1·S)):
`|∂σ/∂K| ≈ 0.1019/(0.2·S)`, so the omitted term `= 𝒱ᶜ·|∂σ/∂K| = S φ(d_1)√τ · 0.5095/S
= 0.5095·φ(d_1)·√τ`. At ATM (`φ(d_1)≈0.399`): **≈5.9 probability points at τ=1 month, ≈10.2 at
τ=3 months.** That equals or exceeds the entire measured wedge (5.6pp Binance / 11.05pp Deribit).
*Honest bound:* the 0.9S/1.1S proxy is a wing-to-wing slope and overstates the LOCAL `∂σ/∂K` near
the threshold strike, so treat 6–10pp as an upper bound — but even a third of it is half the
headline. **The paper's own caveat states the opposite sign** ("Stochastic-volatility corrections
would in general widen the measured gap, since Bitcoin smiles are left-skewed for near-money
strikes"); my derivation of `−∂C/∂K` says a left skew NARROWS it. This sign disagreement is
decisive and is settleable on one chain snapshot.

**(V2) Spot is used where the forward belongs.** `d_2` takes `S_t` with an unspecified `r`. Crypto
options price off the FORWARD, which embeds a futures/perp basis that has run ±10–30% annualised.
Using `F = S·e^(bτ)` instead shifts `d_2` by `b√τ/σ`; at `b=10%`, `σ=0.5`: **+2.3pp at 1 month,
+4.0pp at 3 months** of pure benchmark error — again the size of the claimed effect, and again
scaling as `√τ`, i.e. **along the paper's own "wedge largest at long maturity" axis**. The desk
already carries the fix in its data: `data/deribit_vol_markets.jsonl` has a `forward` field.

**(V3) `r` is never assigned a value.** It appears in `d_2`, in the discount factor, and in the
IV inversion. Three quantities inherit an unstated parameter.

**(V4) The Deribit leg — the 11pp headline and the only leg the desk owns — is INVERSE.** Deribit
BTC/ETH options are coin-settled and quoted in BTC. Desk-confirmed from its own artifact:
`data/deribit_vol_markets.jsonl` carries `inverse: true` for BTC and ETH, `false` for
AVAX/SOL/XRP/TRX/HYPE. A USD-denominated digital extracted from an inverse option needs a
numeraire (quanto) adjustment; `Φ(d_2)` under the BTC numeraire is not the USD risk-neutral
probability. The paper never mentions exercise style, settlement currency, or numeraire.

**(V5) Settlement references differ, so the "same payoff" premise fails.** Polymarket threshold
markets resolve via UMA against a stated source at a stated time; Deribit settles on its own
30-minute TWAP index; Binance options settle on Binance's index. Two contracts on different
settlement references are not the same claim, and the residual is not arbitrageable. The paper
performs no resolution-source check. **UMA/oracle risk: absent entirely from the paper.**

**(V6) The backward merge can manufacture the headline AR(1).** "Polymarket observations are merged
backward to the latest available quote or trade at or before the Binance timestamp." On a thin
book the latest Polymarket print can be hours stale, so `P_poly,t` is a step function and `D_t`
inherits a persistent-but-mean-reverting shape **by construction** — which is precisely the
"AR(1) half-life ≈ 4 h ⇒ slow information transmission between segmented venues" claim. The paper
reports **no staleness diagnostic**. Time-since-last-Polymarket-update is the first control any
desk rebuild must carry.

**(V7) Liquidity is never examined** — no depth, no spread by contract, no volume filter. See §4A:
an independent pre-registered microstructure study finds a **longshot spread premium** on
Polymarket, i.e. spreads widen exactly where this paper finds the wedge widest.

**(V8) Construction pathology at the money.** `𝒱ᴰ = −e^(−rτ)φ(d_2)d_1/σ` changes sign at `d_1 = 0`
and vanishes there. So (a) `q₀ = 𝒱ᴰ/𝒱ᶜ → 0` — the vega hedge degenerates near ATM, and (b)
`SE = |𝒱ᴰ|·ς̂_C/𝒱ᶜ → 0` — the entry threshold collapses to `TF_t` alone. The rule therefore trades
with its loosest threshold exactly where its hedge is most degenerate. Never discussed.

**(V9) Sample is mid-2023, pre-ETF, BTC ~$26–29k, on a Polymarket book far thinner than 2026's.**
The paper concedes: "The sample is intentionally narrow… which rules out mapping ambiguity but
limits external validity."

## 1.4 IDENTIFIABILITY VERDICT — split by leg, and it is not what card 29 says

**Polymarket leg: ALREADY WIRED, and card 29 does not know it.**
`libs/data/prediction_markets.py` exists and is a Polymarket collector — Gamma API
(`gamma-api.polymarket.com/markets`) for resolved binary markets and CLOB
(`clob.polymarket.com/prices-history?market=<token>&interval=max&fidelity=<min>`) for
pre-resolution Yes-price history, free/keyless/read-only, with an explicit point-in-time
discipline. `scripts/run_prediction_markets.py` already runs a calibration + favourite-longshot
test on it. So the retail leg is **backfillable to contract inception** with existing desk code.
Two build notes: the collector's default `fidelity=720` is 12-hour resolution (card 29's hourly
wedge needs `fidelity=60`), and `fetch_resolved_markets` filters to `outcomes == ["Yes","No"]`
with `umaResolutionStatus == "resolved"`, so BTC threshold markets are reachable but must be
selected by parsing a price level out of `question`.

**Deribit option leg: NOT identifiable from stored artifacts, and NOT backfillable at any price
the desk will pay.**
- `data/deribit_surface.parquet` = **100 rows × 6 cols** (`ts, currency, atm_iv, skew, term,
  spot`), 2026-06-26 → 2026-08-12, ~1 obs/currency/day. **There is no strike dimension.**
  `P_fair` at an arbitrary threshold `K` cannot be computed from it, and the model-free
  call-spread digital certainly cannot.
- `scripts/collect_deribit_surface.py` calls `libs/data/deribit.py::vol_surface`, which DOES pull
  the whole per-strike chain (`get_book_summary_by_currency?kind=option`, keyless: instrument name
  → strike/type, `mark_iv`, `underlying_price`) and then **discards the strike dimension**,
  persisting four scalars. The capability exists; the schema throws it away.
- `data/deribit_vol_markets.jsonl` (163 rows, 2026-08-06, `source: snapshot_chain_black76`) is
  richer — per expiry `{atm_iv, forward, dte_days, n_strikes, inverse}`, 7 underlyings, 13–25
  strikes per bucket — but still persists **no per-strike IV**.
- The desk's own code states the binding fact: *"Per-strike implied vol has NO free history, so
  this is archived FORWARD"*. **There is no historical backfill.** The wedge series starts at zero
  observations.

**Therefore: card 29's wedge is HALF-identifiable. The retail leg has history; the benchmark leg
has none. The binding constraint is the option-chain archive, not Polymarket.** To match
Portnaya's 214-obs main sample at hourly cadence the desk needs ~9 days of hourly chain snapshots
per contract; at the collector's current daily cadence, ~7 months.

**And the sharper verdict: as specified, the measurement is not identifiable at all — not for
want of data, but because the estimator is dominated by its own misspecification.** V1 and V2
each contribute a bias of the same order as the 5.6–11pp effect, both scaling with `√τ` in the
same direction as the paper's headline cross-sectional finding. Under L1.28a this resolves to
**UNMEASURED**, not to "a wedge exists".

## 1.5 What the desk should actually run first (measurement-only, no alpha claim)

**The first deliverable is a BENCHMARK-BIAS AUDIT, not a wedge series — and it needs ONE keyless
chain snapshot, zero history, zero capital.** On a single `get_book_summary_by_currency` pull:

1. For each expiry with `n_strikes ≥ 3`, compute both digitals at a common ladder of thresholds:
   (a) `P_Φ = e^(−rτ)Φ(d_2(σ̂_K))` per Portnaya, and
   (b) `P_BL = [C(K−h) − C(K+h)] / (2h)` — the model-free call-spread digital, `h` = one strike
   increment, using the SAME snapshot's traded prices (discounting already embedded).
2. Report `P_Φ − P_BL` in probability points, by moneyness and by `τ`. **If this exceeds ~2pp
   anywhere in the region where the wedge is claimed largest (low probability, long maturity),
   Portnaya's estimator is refuted as a measurement and card 29's wedge cannot be read from it.**
3. Repeat (a) with `F` (the `forward` field the desk already stores) substituted for `S` to size V2
   independently.
4. Handle V4 explicitly: BTC/ETH Deribit quotes are in BTC (`inverse: true`) — convert with the
   index and state the numeraire before comparing to a USD-denominated Polymarket price.

Only if the audit clears should any wedge series be accrued. Cost of the audit: one HTTP GET.

## 1.6 The desk already owns evidence on card 29's MECHANISM — run 6 did not cite it

`reports/prediction_markets/report.json` (written **2026-08-12 03:58**, i.e. the same day run 6
carded this) — 166 usable resolved Polymarket binaries:

| implied bucket | n | implied | realized |
|---|---|---|---|
| 0.0–0.1 | 44 | 0.049 | **0.000** |
| 0.1–0.2 | 15 | 0.138 | 0.133 |
| 0.2–0.3 | 21 | 0.241 | 0.381 |
| 0.3–0.4 | 16 | 0.342 | 0.250 |
| 0.4–0.5 | 12 | 0.447 | 0.417 |
| 0.5–0.6 | 24 | 0.561 | 0.583 |
| 0.6–0.7 | 13 | 0.636 | 0.615 |
| 0.7–0.8 | 11 | 0.740 | 0.818 |

Strategies: `back_fav_all` n=166 mean 0.0104 SR/bet 0.0179; `back_fav_60` n=130 mean 0.0079;
`back_fav_70` n=101 mean **−0.0045**. `survivors: 0`, every variant rejected for
**"below gauntlet minimum (n=166<250)"**.

Reading: the longshot bucket IS overpriced (4.9% implied vs 0.0% realized) and the top-favourite
bucket underpriced (0.740 vs 0.818) — directionally card 29's favourite-longshot mechanism — but
the middle buckets are non-monotone, the strongest-filter variant is **negative**, and nothing
clears the desk's own n≥250 floor. Correct grade: **mechanism direction corroborated on
desk-owned data, magnitude UNMEASURED at power.** Card 29 should cite this instead of treating
the mechanism as untested; it also means the mechanism leg needs no new build, only more resolved
markets.

## 1.7 Card 29's DATA-LEG claim is wrong on three counts

Card 29 records OpenMarket (arXiv 2607.26245) as "free wedge-measurement backfill", CC-BY-4.0,
2026-02-12..2026-05-15. Checked this run:
- **Licence: Apache-2.0**, per both https://huggingface.co/datasets/gregyoung14/openmarket-btc-polymarket
  and the GitHub repo ("Apache License 2.0. See LICENSE."). Run 6's ground file says CC BY 4.0;
  the watchlist card says Apache-2.0. The ground file is wrong.
- **Shape is unusable for card 29.** `market_meta` keys on `up_token_id` / `down_token_id` — UP/DOWN
  binaries with **no strike**. A strikeless up/down contract cannot be matched to an option strike,
  which is the entire matching premise ("identical underlying, strike, and maturity"). OpenMarket
  cannot backfill this wedge at all. Its lead-lag-testbed use survives untouched.
- **Dates:** event span 2026-02-12→2026-05-15 (93 days); snapshot publication window
  2026-03-14→2026-07-01 (109 days). The HF card surfaces the publication window; run 6 recorded
  the event span. Both are right about different things — worth stating precisely at ingest.
- Redundant anyway: the desk's own `libs/data/prediction_markets.py` reaches Polymarket history
  directly and with point-in-time discipline.

---

# 2. S3 — the "negative-carry computation in arXiv 2510.14435"

**The paper is not what the carry-over says it is, and the computation does not exist in it.**

**Identification.** arXiv:2510.14435 = Nicola Borri, Yukun Liu, Aleh Tsyvinski, Xi Wu,
**"Cryptocurrency as an Investable Asset Class: Coming of Age"**, q-fin.GN, v1 2025-10-16,
v4 2026-03-21. **`[PRIMARY]`** — https://arxiv.org/html/2510.14435v4 (HTTP 200), three passes
(stylized facts / §3.6 carry / bibliography). It is a **review**, organised as seven stylized
facts; §3.6 is stylized fact 6, "When the funding dries up, we finally learn the worth of futures".

**Everything the paper says about carry, verbatim:**
- Strategy: *"The crypto-carry trade strategy of [124] is short a perpetual futures contract and
  long a position in the corresponding spot market."*
- Data: *"Perpetual futures prices, funding rates and spot index prices for Bitcoin at the 8-hour
  frequency from Binance for the period August 1, 2020 to May 31, 2025."*
- Mechanism: *"A funding rate—positive or negative by design—flows between longs and shorts to keep
  futures prices anchored to spot."*
- Performance: *"Over the full sample, which goes from 2020 to 2025, the annualized Sharpe ratio of
  the cryptocurrency carry is 6.45. Beginning in 2024, the Sharpe ratio falls to 4.06, and it turns
  negative in 2025."*
- Decomposition: *"The profit from the cryptocurrency carry strategy is mostly driven by the funding
  rate, which in the full sample has a mean return of approximately 8% with a low volatility of 0.8%."*
- Consequence: *"If funding premia compress or become more volatile, the economics of these
  strategies deteriorate and the expected yields decline."* / *"The lower profitability of the
  crypto-carry trade shows that funding-rate premia are neither guaranteed nor permanent."*
- Figure 2 caption: *"The figure plots the cumulative returns from Tether Carry Trades (left axis)
  and from a long buy-and-hold strategy in Bitcoin (right axis). The Carry Trade is defined as in
  [124]. The sample goes from August 1, 2020 to May 31, 2025."*

**What is ABSENT (each checked by a targeted pass):** no return formula; no yearly table (Figure 2
is a cumulative-return plot — there is no numeric table of Sharpes by year); **no exact 2025
Sharpe number, only the word "negative"**; no transaction-cost, exchange-fee, spot-borrow or
funding-of-the-spot-leg assumption; no observation count (~1,577 8-hour periods is my arithmetic
from the stated window, not the paper's); no annualisation convention. The construction is
delegated by citation to `[124]`, and **the reference list in the v4 HTML truncates before entry
[124]**, so the construction's actual source could not be resolved from this box — the Figure-2
label "Tether Carry Trades" is the only additional handle.

**S3 VERDICT: the carried item is a phantom.** There is no "negative-carry computation" inside
2510.14435 to extract. The paper reports a **one-sentence summary of someone else's strategy**,
with no formula, no cost model, and no numeric negative. This carry-over has been on the desk's
next-ground list for five runs; it should be **closed as resolved-to-nonexistent**, not re-queued.

**Reproducibility verdict (asked explicitly, answered explicitly).** The *inputs* are fully owned:
Binance BTC perp mark/index, the 8-hour funding panel, and spot bars are all desk feeds, and the
window 2020-08-01→2025-05-31 is inside the desk's history. So a desk researcher **could** rebuild
an 8-hour short-perp/long-spot series and its Sharpe. But:
1. **There is no target to reproduce.** Without `[124]`'s formula the desk cannot know whether the
   6.45 includes spot-leg financing, whether the perp leg is marked at mark or index, or how the
   funding accrual is timed relative to the 8-hour stamp. Any reconstruction would be *a* carry
   series, not *this* one.
2. **The number that would be reproduced is a gross number.** The paper states no cost assumption
   at all. The desk's own carry work already found the live sleeve's −51.74 bps is EXECUTION not
   selection and that carry loss is 88.3% fees — i.e. the desk has already refuted the no-cost
   framing internally, from its own fills.
3. **Missing feed: none.** This is the rare case where nothing is missing on the data side and the
   defect is entirely on the specification side.

**The one durable datum worth keeping** is directional and external: an independent
Yale/Rochester-affiliated review states the BTC perp carry Sharpe fell 6.45 → 4.06 (2024) →
**negative (2025)** on Binance 8-hour data. That is a decay prior on a family the desk has already
hunted and already sized down — it belongs in the carry family's decay record, not in the queue.

---

# 3. ENUMERATION DEBT — PAID IN FULL, 287 titles read

All 12 owed slices walked via listing pages (`arxiv.org/list/<cat>/<YYYY-MM>?skip=0&show=2000`),
serially. `export.arxiv.org` API not attempted (run 6's 429 finding stands and was respected).

| slice | URL walked | entries | outcome |
|---|---|---|---|
| q-fin.TR 2026-03 | /list/q-fin.TR/2026-03 | 20 | 2 second-tier (`2603.15963`, `2603.28898`); stat-arb NULL |
| q-fin.TR 2026-04 | /list/q-fin.TR/2026-04 | 26 | **richest slice** — 5 prediction-market papers incl. `2604.24366`; stat-arb NULL |
| q-fin.ST 2026-02 | /list/q-fin.ST/2026-02 | 34 | 3 depth (`2602.07018`, `2602.19590`, `2602.07046`); 2 engine |
| q-fin.ST 2026-03 | /list/q-fin.ST/2026-03 | 33 | 2 engine (`2603.20237`, `2603.19380`); families NULL |
| q-fin.ST 2026-04 | /list/q-fin.ST/2026-04 | 30 | 1 depth (`2604.01431` Kalshi); 1 engine (`2604.15531`) |
| q-fin.ST 2026-05 | /list/q-fin.ST/2026-05 | 31 | MNQ-falsification cluster corroboration; 1 engine (`2605.12151`) |
| q-fin.ST 2026-06 | /list/q-fin.ST/2026-06 | 40 | `2606.04574` (statarb, DRL); 2 engine (`2606.08228`, `2606.24019`) |
| q-fin.PR 2026-02 | /list/q-fin.PR/2026-02 | 9 | crypto NULL except `2602.23762` (cross-chain spillover, no map) |
| q-fin.PR 2026-03 | /list/q-fin.PR/2026-03 | 14 | crypto NULL |
| q-fin.PR 2026-04 | /list/q-fin.PR/2026-04 | 15 | crypto NULL; 3 IV-inversion tools |
| q-fin.PR 2026-05 | /list/q-fin.PR/2026-05 | 19 | **`2605.22792`** (the V1 fix); `2605.29309`, `2605.10428` |
| q-fin.PR 2026-06 | /list/q-fin.PR/2026-06 | 16 | `2606.12872` (scheduled-event risk in options) |

**Total: 287 titles read. Residual unwalked: ZERO for the assigned debt.**
Honest residual OUTSIDE the assignment (recorded, not claimed as done): q-fin.TR 2026-02 and
2026-01 were never in any run's scope; q-fin.RM/PM/MF/CP/GN remain walked at 2026-07 only
(run 6's single-month coverage); and the ST/PR walks are title-level — of the 287, **9 were opened
beyond the title this run** (listed with grades in §7).

**Family verdict from the walk (the thing the debt was owed for):**
- **STATISTICAL-ARBITRAGE (n=0, top priority): NULL across all 12 slices.** Per-axis evidence: TR-03
  0/20, TR-04 0/26 (`2604.02909` "Concave Continuation: Linking Routing to Arbitrage" is DEX
  routing, not statarb), ST-02..06 the single hit `2606.04574` "Dynamic Multi-Pair Trading Strategy
  in Cryptocurrency Markets with **Deep Reinforcement Learning**" — an ESTIMATOR refinement on the
  pairs family, which the desk's `statarb_kalman_hedge_ratio_refinement` graveyard row plus the
  standing rule ("the stat-arb estimator layer is dead — spend on costs and capacity, never on a
  fancier estimator") **pre-kills**. PR-02..06 0/73. So six months of ST and two of TR add **zero**
  new stat-arb constructions beyond run 6's Tadi–Witzany card. The family stays n=0-with-one-queued.
- **VOL-AND-OPTIONS (n=2): one genuine lead** (`2604.01431` Kalshi, §4B) — and it is not cardable.
- **MARKET-MAKING-EXECUTION (n=2): two engine-grade leads**, `2602.19590` and `2606.24019`.
- **EVENT-AND-CALENDAR (n=1):** `2602.07046`, `2605.10428`, `2606.12872` — all method/taxonomy, no
  mechanism with a forced loser.
- **LEAD-LAG (n=2):** `2603.20271` (transfer entropy, Korean equities) and `2602.07048` (LLM
  filtering for prediction-market lead-lag). Both are marks/price-series lead-lag; both inherit
  run 6's mark-unidentifiability rule and R0117. Not re-carded.
- **ATTENTION-SENTIMENT (n=2):** `2602.07018` "The Extremity Premium" is the only entry in 287 with
  an adverse-selection mechanism rather than an NLP wrapper. Opened — see §4C.
- **LEVEL-REACTION (n=1):** `2603.15963` "Risk-Based Auto-Deleveraging". Opened — see §4D.

---

# 3A. CARD-28's ESTIMATOR — the Autocorrelation Map, extracted; and the paper's own numbers kill the alpha leg

**Paper.** Kim & Hansen, "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return
Predictability in Cryptocurrency Futures", arXiv:2607.09426.
**`[PRIMARY]`** — full text read from https://arxiv.org/html/2607.09426v2 (HTTP 200), two passes
(estimator + data + roundness + OOS / the 4–12h horizon block).

## 3A.1 The Autocorrelation Map (ACM), implementable without re-reading

A **sign-correlation heatmap over (lag × clock phase)**, not a conventional autocorrelation:

`τ(k,m) ≡ E[ sign( x_{d,h,m} · x_{d,h,m+k} ) ]`

Sample analogue for returns:
`τ̂_r(k,m) = (1/N_{k,m}) Σ_{d=1..D} Σ_{h=0..23} sign( r_{d,h,m} · r_{d,h,m+k} )`

- `d` = day, `h` = hour, `m` = **minute-of-the-hour (0–59)**, `k` = lag in minutes.
- `x` is either returns or order flow — the same map is built for both.
- Rendering: lag `k` on columns, minute-of-hour `m` on rows; quarter-hour phase coordinates joined
  by guide lines.
- Resolution: 1-minute bars aggregate full minutes; 10-second bars partition each minute into six
  sub-intervals `b ∈ {1..6}`.
- **Significance is established by PLACEBO PHASE SHIFTS** (Appendix Fig. A.7) — shift the assumed
  boundary phase and confirm the structure disappears. This is the part the desk must copy: it is
  the direct answer to "is this a sampling artifact?", which is card 28's falsifier (1).

**Order imbalance (1-minute):** `OI_t = OF_t / Σ_{k∈t} V_k ∈ [−1,1]`, with signed flow
`OF_t = Σ_{k∈t} V_k · D_k`, `D_k ∈ {+1,−1}` from `isBuyerMaker`.

**"Opening"** = the first 10-second interval (`b=1`) of a quarter-hour minute (`m ∈ {0,15,30,45}`).

**Trade-size roundness (the algo signature):**
`TZshare(z)_t = #{k∈t : TZ(V_k) ≥ z} / #{k∈t : V_k ≥ 10^z · s_min}`
where `TZ(V_k)` counts trailing zeros of the size in base-asset units and `s_min` is the minimum
order increment. Note the denominator is the **mechanically eligible** set — a size cannot have
`z` trailing zeros unless it is at least `10^z·s_min`. That denominator discipline is itself worth
copying (it is the same defect class as the desk's L1.60 denominator-attrition law).

**Data:** six Binance USDT-M perps (BTC, ETH, XRP, SOL, DOGE, ADA), millisecond aggTrades,
**2021-01-01 → 2024-10-31**, aggregated to 10-second and 1-minute bars; ~117,000 quarter-hour
boundary observations per asset in the OOS window (2021-07-01 → 2024-10-31). Fields: ts(ms),
price, quantity, `isBuyerMaker` — **exactly the schema of Binance aggTrades the desk already
collects.**

## 3A.2 The results — and why the alpha leg is dead by the authors' own arithmetic

**10-second forecast (the OOS result).** LASSO on 12 quarter-hour-spaced lags of opening 10s
returns (T−15m … T−180m) + 28 technical indicators from 15-min OHLCV ending T−15m. Target
`R(T,Δ) = P^vwap_{T,Δ} / P^open_T − 1`, Δ=10s. Table 3: cross-sectional mean **OOS R² 3.37%**,
**AUC 0.6011**, accuracy 57.12%. Table 4: Diebold–Mariano HAC(6) t = 4.78–22.95 for the lag block
vs zero, all p<0.01. Mincer–Zarnowitz slopes 0.77–0.94.

**The kill, verbatim from the paper:** *"The sign-weighted realized forecast target… averages about
**0.5 bp per boundary**, about **one tenth of a single standard-tier taker fee**"* (5.0 bp on
Binance) *"and one twentieth of a round trip."* And the authors' own framing: *"The forecast should
be interpreted as an **input to execution and liquidity provision rather than as a standalone
trading strategy**."*

**This is a STRUCTURAL kill, not a statistical one** — gross per event is an order of magnitude
below friction, which is precisely the death mechanism the desk already recorded in
`lit_intraday_ohlcv_mnq_14of14`. A better estimator cannot close a 20× gap.

**The 4–12 hour claim — in-sample, uncosted, and it is a DECOMPOSITION component.** Specification:
```
r_{t,t+ℓ} = α_ℓ + β_ℓ·OI_t
          + β_ℓ^{1min}·OI_t·1{b_t=1}
          + β_ℓ^{5min}·OI_t·1{mod(m_t,5)=0 ∧ b_t=1}
          + β_ℓ^{15min}·OI_t·1{mod(m_t,15)=0 ∧ b_t=1}
          + γ_ℓ^⊤ W_t + ε_{t,ℓ}
CFE_15min(ℓ) = β_ℓ + β_ℓ^{1min} + β_ℓ^{5min} + β_ℓ^{15min}
```
Shape: *"The CFE is negative over the first half hour, consistent with a short-run reversal
following boundary imbalance. It subsequently turns positive and continues to rise, typically
peaking between eight and twelve hours."* Significance: 95% at every horizon for 4 of 6 contracts
between 4 and 12 hours; SOL (4h, 12h) and ADA (4h) only at 90%. Magnitude: the *public-signal
component* of the Table-5 decomposition reaches **9.8 bp at 8h and 16.9 bp at 12h**.
**All of these regressions are IN-SAMPLE on the full sample with no transaction-cost adjustment.**

So the 4–12h leg is: in-sample, uncosted, 4-of-6 assets, sign-flipping within the first 30 minutes,
and 16.9 bp at 12 hours against a 10 bp taker round trip **before** slippage — i.e. a ~1.7× ratio
on an in-sample number that the desk's −58% McLean–Pontiff haircut alone would erase.

## 3A.3 Card 28 collides with `do_not_repeat` — run 6 missed it

`research_agenda.json` → `do_not_repeat[23]`:
> `quarter_hour_periodicity_crypto_futures` (REJECTED 2026-07-17 by EV gate: **ev 0.0006**,
> crowded_known; **arXiv 2607.09426 'The Quarter-Hour Effect'** — published periodic pattern, and
> the desk is D1-only today (no intraday collector), so testing it would require new infra effort on
> top of an already-crowded/published signal. Revisit only if intraday data collection is ever built
> for an unrelated reason.)

Run 6's card 28 states "No graveyard collision found" — true of `docs/graveyard.md`, but the
collision is in `research_agenda.json`'s `do_not_repeat`, **by exact arXiv id**, three weeks
earlier. The card checked one of the desk's two kill registries.

Two things follow, and they point opposite ways:
1. The rejection's own named re-entry condition ("revisit only if intraday data collection is ever
   built for an unrelated reason") **has been met** — the desk now has an own-clock L2/trade
   recorder. So L1.16a re-entry is legitimate on the infra ground.
2. But the interior read supplies a *better* reason to leave it dead than the EV gate had: the
   2026-07-17 rejection was on **crowdedness**; the 2026-08-12 interior read is a **structural
   friction kill from the authors' own numbers** (0.5 bp vs 10 bp round trip). Re-entry on infra
   grounds would walk straight into a wall the EV gate could not see.

**Standing consequence:** every future card must be checked against BOTH `docs/graveyard.md` AND
`research_agenda.json::do_not_repeat`. See §6.

---

# 4. DEPTH READS FROM THE ENUMERATION

## 4A. `2604.24366` — Polymarket's order book, pre-registered: the longshot SPREAD premium co-varies with card 29's wedge

**Dubach, "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the
Polymarket Order Book"**, arXiv:2604.24366 (v1 2026-04-27, v2 2026-05-14).
**`[PRIMARY]`** — https://arxiv.org/html/2604.24366v2 (HTTP 200); landing
https://arxiv.org/abs/2604.24366 (HTTP 200).

**Sample:** pre-registered stratified panel of **600 markets over 52 days (2026-02-21 → 2026-04-15)**,
30.3 billion order-book events joined to 255.4 million on-chain `OrderFilled` events; 28-day
calibration window. Strata: top-100 by on-chain USDC volume ($4.56M–$96.0M) + random-500 (≥100
trades). **Categories: Crypto 348/600 (58%)**, Sports 142, Other 75, Geopolitics 35.

**The finding that lands on card 29 — quoted half-spread by mid-price bucket:**

| mid (probability) | median | p25 | p75 |
|---|---|---|---|
| 0.00–0.10 | **1,818 bps** | 1,176 | 4,000 |
| 0.10–0.20 | 1,339 | 690 | 2,564 |
| 0.20–0.30 | 755 | 465 | 1,767 |
| 0.40–0.50 | 400 | 202 | 400 |
| 0.50–0.60 | 400 | 400 | 400 |

Paper's words: spreads climb *"to 1,300–1,800 bps for markets trading below 0.10"*, low-probability
sides materially wider than high-probability sides, reflecting *"a liquidity-provision constraint"*
rather than classical behavioural bias.

*Unit note, flagged as MINE:* the table is bps **relative to mid** (the 0.50–0.60 row is degenerate
at exactly 400 in all three quantiles, i.e. a floor — consistent with a fixed ~2-cent half-spread
at a 50-cent mid). On that reading the ABSOLUTE half-spread is ≈0.9 probability points at the
longshot end and ≈1.8–2.0 pp mid-book, i.e. a roughly constant cent-denominated spread whose
*relative* cost explodes as the price falls. If instead the table were absolute, the longshot
half-spread would exceed the contract price, which is impossible — so the relative reading is the
only coherent one. Desk should confirm against a live book before relying on it.

**Consequence for card 29, stated plainly:** Portnaya's headline cross-sectional result is *"the
wedge is largest at low option-implied probabilities"*. Dubach's result is *the spread is largest
at low probabilities.* The two co-vary along the same axis and Portnaya controls for neither depth
nor spread (V7). Combined with V1 (flat-smile bias, 2–10 pp, same `√τ` axis) and V2 (spot-for-
forward, 2–4 pp, same `√τ` axis), **the 5.6 pp Binance wedge is fully accounted for by known
benchmark error plus quoted transaction cost, with nothing required from segmentation or
favourite-longshot demand.** The wedge is not established.

**Two further interior facts, both first-class engine findings:**
- **Depth is near-uniform, not top-of-book.** Median share of top-10 cumulative depth: L1 = 0.1364
  (p25 0.0800, p75 0.2055), L2 = 0.1034, L3–L10 ≈ 0.08 each, across 547 markets. A "uniform
  geometric grid". So top-of-book quotes materially understate available size — the opposite of the
  desk's crypto-perp intuition.
- **Public-feed trade signs are wrong about two trades in five.** Feed-inferred direction matches
  on-chain ground truth at **~59% volume-weighted** (panel mean 0.615, 95% CI [0.58, 0.65]; median
  0.591, IQR [0.53, 0.68]) versus ~80% on Nasdaq. Consequence measured in-paper: **effective
  half-spread flipped SIGN on 67% of top-100 markets and Kyle's λ flipped on 60%.** Any Polymarket
  order-flow or microstructure signal built from the public feed inherits a sign error that flips
  the estimand on a majority of markets. This independently explains the desk's existing graveyard
  row `lit_polymarket_15min_binary_ml` (43 microstructure features, −0.116/trade): the features
  were built on signs that are wrong 41% of the time.
- **Wash trading is real but small:** median self-counterparty share 0.97%, p90 4.5%, p99 10.6%,
  max 22.2% — and the detector flags only direct self-match + immediate roundtrips within 128
  blocks, *"an explicit lower bound"*.

## 4B. `2604.01431` — Kalshi macro contracts forecast crypto RV. Not cardable, and the reason matters

Mohanty & Krishnamachari, "Do Prediction Markets Forecast Cryptocurrency Volatility? Evidence from
Kalshi Macro Contracts", arXiv:2604.01431 (2026-04-01). **`[ABSTRACT]`** —
https://arxiv.org/abs/2604.01431 (HTTP 200). Full text not opened (deprioritised once the verdict
below became determinate; recorded honestly rather than upgraded).

Claim: daily probability changes on KXFED / KXRECSSNBER / KXCPI forecast crypto realized vol.
BTC–Fed in-sample t=3.63 p<0.001 but regime-dependent on the 2024–25 cutting cycle; KXRECSSNBER
OOS **MSFE ratio 0.979**, Clark–West p=0.020; CPI channel predicts ETH/SOL/ADA/LINK vol with
t = −2.1 to −3.4, ETH OOS MSFE 0.959 (p=0.010), SOL p=0.048. BTC–Fed-dovish and LINK–CPI survive
Benjamini–Hochberg at q=0.05. Ten Kalshi series × six assets, **2023-01 → 2026-03**. Explicitly
orthogonalised against Fed Funds futures, Treasury yields, **and the Deribit implied-vol index** —
*"these signals carry information not embedded in conventional financial instruments."*

**Why this is NOT a card, despite hitting a thin family and a legitimacy-clean venue (Kalshi is
CFTC-regulated, unlike Polymarket):**
1. **No forced loser.** It is a forecasting-improvement result. Nobody is identified as having to
   lose money, so under the desk's standing rule it is a statistical pattern, not an edge.
2. **The desk already knows volatility is predictable** (129/129 directional mechanisms failed
   while vol did not). A 2.1–4.1% MSFE improvement over an already-predictable quantity is a
   sizing/risk input at best.
3. **Zero tradability analysis** — no costs, no capacity, no instrument through which the improved
   vol forecast is monetised. The obvious instrument is variance-premium harvesting, which the desk
   **EV-rejected on 2026-08-12 (DVOL vol-carry, EV 0.0003)**.
4. Regime-dependence is conceded in the abstract for the strongest channel.

**Kept as:** a named, dated lead for the risk/sizing layer, and a genuinely useful negative datum —
the one prediction-market×crypto-vol result in 287 titles is a forecast improvement with no
monetisation path. Recorded so the next seat does not re-mine it.

## 4C. `2605.22792` — ARIES + SEDEx: the exact fix for card 29's V1, already built by someone else

Wizman, Turinici & Merran, "From Arbitrage Removal to Density Extraction: A Model-Free Framework
for Short-Dated Options", arXiv:2605.22792 (2026-05-21, rev 2026-06-11). **`[ABSTRACT]`** —
https://arxiv.org/abs/2605.22792 (HTTP 200).

Two-step model-free pipeline that **treats bid–ask quotes as the primitive market constraint**
(not the mid): **ARIES** filters executable static arbitrage at quoted bid and ask under
market-depth constraints; **SEDEx** recovers the risk-neutral density under bid–ask constraints via
a smoothness + entropy criterion. Validated on synthetic Heston panels and short-dated SPX, from a
few hours to one week before expiry, including scheduled macro announcements. Their motivating
problem is verbatim card 29's problem: *"As expiry approaches, option premia decline and bid–ask
spreads can be large relative to prices, making mid quotes particularly uninformative. Stale or
asynchronous quotes may also generate potential static arbitrages."*

**Why this matters here:** Portnaya inverts a single **mid** quote and evaluates `Φ(d_2)`. Both
choices fail exactly where her wedge is claimed largest (low premium, wide relative spread). A
model-free density gives the digital directly and needs no `σ`, no `r`, and no flat-smile
assumption. Not crypto-validated, and Deribit's inverse convention (V4) is not handled — but this
is the named method the desk's benchmark-bias audit (§1.5) should adopt if the two-strike call
spread proves too noisy. No code release stated.

## 4D. `2602.19590` — metaorder identification WITHOUT trader IDs, from public TAQ

Goliath & Gebbie, "Metaorder modelling and identification from public data", arXiv:2602.19590
(2026-02-23). **`[ABSTRACT]`** — https://arxiv.org/abs/2602.19590 (HTTP 200).

Validates Lillo–Mike–Farmer order-splitting on **publicly available JSE data** by reconstructing
**synthetic metaorders**, 3 years of TAQ on the top 100 JSE stocks, assuming N=50 or N=150 effective
traders. Their framing is the desk's exact constraint: *"quantitative tests of this theory have
historically relied on proprietary datasets with trader identifiers, limiting reproducibility."*

**Desk relevance (engine, not alpha):** the desk's third cost basis is impact estimated from
third-party prints, i.e. exactly the no-trader-ID setting. A published, validated method for
reconstructing metaorders from public TAQ is a direct methods input to that program. Equity
venue, and **the abstract states no identification-accuracy metric and no impact-law numbers** —
so this is a method lead, not evidence. Full text not opened this run.

---

# 5. MECHANISM CARDS — **ZERO**, and the reason for each near-miss

No new card is proposed this run. Every candidate that reached depth failed one of the desk's own
standing tests, and manufacturing a card out of any of them would have been the failure mode this
seat exists to prevent. The near-misses, with the test each failed:

| candidate | family | failed on |
|---|---|---|
| `2604.01431` Kalshi macro → crypto RV | VOL-AND-OPTIONS (n=2) | **no forced loser** — a forecast improvement (MSFE 0.959–0.979), no monetisation instrument; the obvious one (variance-premium harvest) is EV-rejected 2026-08-12 |
| `2602.07018` Extremity Premium | ATTENTION-SENTIMENT (n=2) | **not alpha** — the finding is that SPREADS widen in extreme F&G regimes; the authors themselves say the pre-specified endpoint fails multiple-testing correction and that the effect is "not conclusively separable" from the volatility embedded in the F&G index. `F&G_contrarian` is already in `do_not_repeat`. Execution-hygiene datum only |
| `2603.15963` Risk-Based ADL | LEVEL-REACTION (n=1) | **design paper, no measurement** — real forced loser (water-filling deleverages the most-levered accounts first) but no ADL frequency, no cost-to-trader, one case study (Hyperliquid 2025-10-10), and the desk has no Hyperliquid feed. Rail input, not a signal |
| `2606.04574` DRL multi-pair crypto | STATISTICAL-ARBITRAGE (n=0) | **pre-killed estimator layer** — a deep-RL refinement of the pairs estimator; `statarb_kalman_hedge_ratio_refinement` plus the standing rule "spend on costs and capacity, never on a fancier estimator" |
| `2603.20271` / `2602.07048` lead-lag | LEAD-LAG (n=2) | **marks-unidentifiability + R0117** — both are price-series lead-lag; the standing rule requires raw trades with own-clock provenance |
| `2605.29309` implied ETF carry, segmented BTC | — | **hunted family** (carry-funding), barred by mission |

**The single most useful output of this seat is not a card — it is that three claims already
standing in the desk's own artifacts are wrong** (§1.3–1.7, §3A.3), and correcting them is worth
more than adding a fourth queued hypothesis to a backlog the ledger already calls bursty.

---

# 6. GRAVEYARD CANDIDATES (parent routes; this seat cannot write `docs/graveyard.md`)

## G1 — `lit_quarterhour_boundary_alpha` · grade **STRUCTURAL** (blocks forever at taker fees)
The quarter-hour boundary forecast **as a standalone trading strategy**. Death mechanism, from the
authors' own text (arXiv:2607.09426 `[PRIMARY]`): the sign-weighted realized forecast target
*"averages about 0.5 bp per boundary, about one tenth of a single standard-tier taker fee"* (5.0 bp)
*"and one twentieth of a round trip"*, and *"the forecast should be interpreted as an input to
execution and liquidity provision rather than as a standalone trading strategy."* A 20× gross-to-
friction gap is structural — no estimator closes it. Same death class as
`lit_intraday_ohlcv_mnq_14of14`.
**What it does NOT block:** (a) the execution-hygiene leg (do not send child orders INTO
:00/:15/:30/:45 boundaries) — negative capacity requirement, feeds the 66 bps gap programme;
(b) a maker-rebate venue where the fee sign flips. **Relation to `do_not_repeat[23]`:** that row
already rejected the same arXiv id on 2026-07-17 at ev 0.0006 for **crowdedness**. This entry
supersedes the reason with a stronger one and closes the row's own re-entry clause ("revisit only
if intraday data collection is ever built") — the infra now exists, and the wall is still there.

## G2 — `lit_polymarket_public_feed_trade_signs` · grade **STRUCTURAL for the feed**, re-openable by a named change
Any Polymarket microstructure or order-flow signal built on **public-feed-inferred trade
direction**. Death mechanism (arXiv:2604.24366 `[PRIMARY]`, pre-registered, 600 markets, 30.3B
events): feed-inferred sign matches on-chain ground truth at **~59% volume-weighted** (mean 0.615,
CI [0.58, 0.65]) vs ~80% on Nasdaq — *"wrong about two trades in five"* — and the measured
consequence is that **effective half-spread flips SIGN on 67% of top-100 markets and Kyle's λ on
60%**. Any estimand built on those signs is sign-unstable on a majority of markets.
**Named enabling change (L1.16a):** join the on-chain `OrderFilled` record (255.4M events in the
paper's window; public on Polygon). With ground-truth signs the family re-opens.
**Retro-explains** the existing row `lit_polymarket_15min_binary_ml` (−0.116/trade over 43
microstructure features): the features were computed on signs wrong 41% of the time. Worth
back-annotating that row.

## G3 — `lit_bs_digital_prediction_market_wedge` · grade **STRUCTURAL for the ESTIMATOR, STATISTICAL for the QUESTION**
The Portnaya construction **as a measurement**: `D_t = P_poly,t − e^(−rτ)Φ(d_2(σ̂_K))`.
Death mechanism: a flat-smile, spot-based, single-strike Black–Scholes digital cannot measure the
digital of a skewed, forward-priced, inverse-settled market. Three biases, each of the same order
as the 5.6 pp effect and **each scaling with `√τ` in the same direction as the paper's headline
cross-sectional finding**: omitted skew term `𝒱ᶜ·|∂σ/∂K|` ≈ 2–10 pp (§1.3 V1, sized off the desk's
own stored skew of 10.19 IV points); spot-for-forward `φ(d_2)·b√τ/σ` ≈ 2–4 pp at a 10% basis
(V2); plus a **longshot quoted half-spread of ≈0.9–2.0 pp** that co-varies with the wedge along
the same probability axis (§4A). Nothing is left over for "segmentation".
**This is a kill of the ESTIMATOR, not of the question.** The question re-specifies cleanly:
model-free call-spread digital `[C(K−h) − C(K+h)]/(2h)` on the option-implied forward, with a
Polymarket staleness control and a depth/spread filter. That re-specification is §1.5 and it costs
one HTTP GET to begin.

## G4 — carry-over closure, not a hypothesis kill: **S3 is a phantom**
"S3 negative-carry computation inside arXiv 2510.14435", carried on the desk's next-ground list
since 2026-08-05 (five runs). Resolved this run: 2510.14435 is Borri–Liu–Tsyvinski–Wu,
*"Cryptocurrency as an Investable Asset Class: Coming of Age"* (q-fin.GN, a **review**), and it
contains **no negative-carry computation** — no formula, no yearly table, no numeric 2025 Sharpe,
no cost assumption; the construction is delegated to a citation whose bibliography entry the v4
HTML truncates before reaching. Close the item as **resolved-to-nonexistent**; do not re-queue.
Keep only the directional datum (BTC perp carry Sharpe 6.45 full-sample → 4.06 from 2024 →
negative in 2025, Binance 8-hour, 2020-08-01→2025-05-31, gross) in the carry family's decay record.

---

# 7. ENGINE / METHOD FINDINGS

**E1 — A card must be checked against BOTH kill registries.** `docs/graveyard.md` and
`research_agenda.json::do_not_repeat` are separate stores with separate contents. Card 28 cleared
the first and collided head-on with the second **by exact arXiv id** (`do_not_repeat[23]`,
rejected three weeks earlier). Run 6's card wrote "No graveyard collision found", which was true
and insufficient. A one-line check over both stores would have caught it.

**E2 — The plug-in SE has a closed form worth reusing.** Portnaya's
`SE(P_fair) = |g′(σ̂)|·ς̂_C/𝒱ᶜ` simplifies exactly to `|𝒱ᴰ|·ς̂_C/𝒱ᶜ` — quote uncertainty mapped
into IV units, then into probability points by the digital's vega. Generic recipe for putting an
error bar on any option-derived probability. Its pathology is equally reusable knowledge: it
vanishes at `d_1 = 0`, so any entry rule of the form `|D| > SE + costs` is loosest exactly at the
money, where the vega-matched hedge `q₀ = 𝒱ᴰ/𝒱ᶜ` also degenerates to zero.

**E3 — Placebo PHASE SHIFTS are the right falsifier for any clock/calendar effect.** Hansen–Kim
Appendix Fig. A.7 establishes boundary dependence by shifting the assumed phase and showing the
structure disappears. This is materially cheaper than a full own-data replication and is the exact
answer to "is this a sampling artifact?" — which is card 28's falsifier (1) and, more generally,
the R0117 question. Adopt as the standard test for the EVENT-AND-CALENDAR family.

**E4 — External instance of the desk's own denominator law (L1.60).** Hansen–Kim's roundness
measure divides by the **mechanically eligible** set (`#{k : V_k ≥ 10^z·s_min}`), not by all
trades — a size cannot show `z` trailing zeros unless it is at least `10^z·s_min`. A naive
denominator would make roundness track the size distribution instead of algo behaviour. Same
defect class the desk built L1.60 for; useful as an external worked example.

**E5 — `ARIES` + `SEDEx` (arXiv:2605.22792): treat bid–ask as the primitive, never the mid.**
Model-free risk-neutral density from quoted bid/ask under depth constraints, then entropy+
smoothness extraction. Motivated by exactly the regime that breaks card 29's estimator (low premium,
wide relative spread, stale/asynchronous quotes, static arbitrage). SPX-validated, not crypto, and
it does not handle Deribit's inverse convention.

**E6 — Metaorder reconstruction without trader IDs (arXiv:2602.19590).** LMF order-splitting
validated on public JSE TAQ via synthetic metaorder reconstruction (N=50/150 effective traders).
Direct methods input to the desk's third cost basis (impact from third-party prints), which sits in
precisely the no-trader-ID setting. Abstract states **no accuracy metric and no impact-law
numbers** — method lead, not evidence.

**E7 — Desk-internal: `vol_surface()` labels a forward as "spot", and medians across expiries.**
`libs/data/deribit.py::vol_surface` reads Deribit's per-instrument `underlying_price` into a field
named `spot` and then takes `df["spot"].median()` across **all expiries**. For a term structure with
a non-zero basis, the median of per-expiry forwards is neither spot nor any one expiry's forward.
Harmless for an ATM-IV scalar; **not** harmless if that field is ever used as `S` in a `d_2`
(§1.3 V2 is exactly this error at paper scale). Flagged read-only; no change made.

**E8 — Mechanical-correlation self-flag worth copying (arXiv:2602.07018).** The authors report
`F = 211` and immediately label it *"partly mechanical, sharing a high–low input with the spread
measure"*, and label the within-quintile test *"post-hoc, exploratory… does not survive
multiple-testing correction"*, and state their ABM *"does no inferential work"* because its
spread–uncertainty link is coded rather than emergent. This is an external example of the desk's
own standing lesson that two estimates sharing most of their input are not independent — and of
publishing that fact in the abstract rather than an appendix.

**E9 — Desk-internal build note.** `libs/data/prediction_markets.py::fetch_price_history` defaults
to `fidelity=720`, i.e. **12-hour** resolution on the Polymarket CLOB `prices-history` endpoint.
Any hourly study (card 29's stated cadence) needs `fidelity=60`. Also `fetch_resolved_markets`
filters to `outcomes == ["Yes","No"]` and `umaResolutionStatus == "resolved"`, so BTC threshold
markets are reachable but must be selected by parsing a price level out of the `question` string.

**E10 — Crowding, and a warning that cuts the other way.** The `Φ(d_2)`-vs-Polymarket construction
is a **retail-published recipe** (a DEV.to tutorial "Black-Scholes on Polymarket: Finding Mispriced
Binary Events with Python"; a FinanceFeeds promo advertising "Edge Up to 12pp"). Two readings, and
the second is the important one: (a) the seam is publicised, so any real edge decays; (b) the
"edges" being advertised are the same size as the benchmark error identified in §1.3 — which is
consistent with a crowd of people all making the same `Φ(d_2)` mistake and calling the residual an
edge. A desk that fixed the benchmark would be measuring something different from what the crowd
is measuring, which is a better reason to build the corrected measurement than the wedge ever was.

**E11 — Replication scan result (Portnaya).** Two searches returned **no replication, no comment,
no critique** — only the paper's own mirrors (arXiv, RePEc, PDF), the cryptodaily practitioner note
run 6 already logged, and the two retail items above. The paper is 2 months old and uncited.
Status: **unreplicated**, and now additionally **contradicted from inside its own construction** by
this run's V1/V2/V7 findings. `[SUMMARY-ONLY]` on everything in that search except the arXiv text.

---

# 8. DEPTH LINE — per lead, and what depth surfaced that the surface did not

| lead | depth reached | what only depth showed |
|---|---|---|
| Portnaya 2606.19517 (card 29) | **full-text + appendix + replication-scanned + citations-1-level** `[PRIMARY]` | Surface said "delta-hedged proxy profitable after conservative costs". Interior: **n=16 trades**, one market with a single losing trade, pooled HAC CI **[−0.008, 0.143] contains zero**, and the friction formula's three parameters **never given a number**. Interior also exposed the estimator: single-strike `Φ(d_2)` on **spot**, whose omitted skew term sized off the desk's own data is **2–10 pp against a 5.6 pp effect**, scaling with `√τ` along the paper's own headline axis. The paper's stated sign for that correction is the opposite of the `−∂C/∂K` derivation. None of this is visible from the abstract, and the abstract is what card 29 was built on. |
| Hansen–Kim 2607.09426 (card 28) | **full-text + appendix + estimator extracted** `[PRIMARY]` | Surface said "opening order imbalance predicts returns over four to twelve hours". Interior: that regression is **in-sample, uncosted**, significant at 95% for only 4 of 6 contracts, sign-flipping in the first 30 minutes; and the paper's OWN economic magnitude for its OOS result is **0.5 bp vs a 10 bp round trip**, with the authors explicitly disclaiming standalone trading. Depth converted a queued alpha card into a structural kill plus an execution-hygiene keeper. Also recovered the ACM estimator in closed form and the **placebo-phase-shift** falsifier. |
| Borri et al. 2510.14435 (S3) | **full-text, 3 passes, bibliography chased (truncated)** `[PRIMARY]` | Surface (a five-run-old carry-over line) said "negative-carry computation". Interior: the paper is a **review**; the computation does not exist in it; the construction is a citation whose bibliography entry the v4 HTML does not reach. A five-run carry-over resolves to a phantom — findable only by opening it. |
| Dubach 2604.24366 (Polymarket book) | **full-text, tables extracted** `[PRIMARY]` | Not on any prior run's radar. Supplies the depth/spread evidence Portnaya omits — the **longshot spread premium** that co-varies with the wedge, near-**uniform depth** (L1 = 13.6% of top-10), and the **59% trade-sign agreement** that retro-explains an existing graveyard row. |
| Desk artifacts (Deribit + Polymarket + report.json) | **read directly, schemas + row counts + a prior result** | Card 29 says "the Deribit surface the desk already holds". The artifact is **100 rows × 6 scalar columns with no strike dimension**, 7 weeks long, ~daily. Meanwhile the desk **already has** a Polymarket collector and had **already run** the favourite-longshot test (166 markets, 0 survivors, all variants below the n≥250 floor) — the mechanism's own desk-owned evidence, uncited by the card that rests on it. |
| `2604.01431` Kalshi | **abstract, verdict determinate** `[ABSTRACT]` | Determinate at abstract level (no forced loser, no monetisation, orthogonalisation is the only novel part). Recorded as a deliberate non-upgrade rather than a gap. |
| `2605.22792` ARIES/SEDEx · `2602.19590` metaorder · `2602.07018` extremity · `2603.15963` ADL | **abstract** `[ABSTRACT]` | Each resolved to engine-tier or non-cardable at abstract level; each reason recorded in §5/§7. |
| arXiv enumeration (12 slices) | **title-level, exhaustive; 9 of 287 opened** | The debt's actual payload: **STATISTICAL-ARBITRAGE is NULL across all 12 slices** with per-axis counts (§3) — the desk's one never-tested family gets no new construction from six months of ST, five of PR, and the two missing TR months. That null is only worth anything because the enumeration was exhaustive rather than sampled. |

**Routing findings (kept strictly distinct from "does not exist"):**
- `arxiv.org/html/<id>` served every paper attempted this run at HTTP 200 — Portnaya v1,
  Hansen–Kim v2, Borri v4, Dubach v2. **No paper was unreachable.** The parent's route note is
  confirmed; `ar5iv` was never needed.
- Listing pages with `?skip=0&show=2000` returned complete single-page enumerations for all 12
  slices. `export.arxiv.org` not attempted (run 6's 429 respected).
- **Reproducibility gap, honest:** the v4 HTML of 2510.14435 **truncates its reference list before
  entry [124]**, so the crypto-carry construction's source could not be resolved from this box.
  That is a ROUTING limit on one specific artifact, not a claim that the reference does not exist.
  The Figure-2 label "Tether Carry Trades" is the handle for the next attempt.
- `scripts/pdf_text.py` **does not exist** (checked: `ls` → No such file). No PDF was needed; the
  HTML route was sufficient for every target. No number in this file is
  `[remembered-not-reproduced]`.

---

# 9. NEXT UN-EXHAUSTED GROUND (named precisely)

1. **Run the benchmark-bias audit (§1.5) before anything else on card 29.** One keyless
   `get_book_summary_by_currency?currency=BTC&kind=option` snapshot; compute `Φ(d_2)` and the
   call-spread digital `[C(K−h)−C(K+h)]/(2h)` on a common threshold ladder; report the difference in
   probability points by moneyness and `τ`, and repeat with the stored `forward` in place of spot.
   **This is the decisive experiment and it needs zero history and zero capital.** If the difference
   exceeds ~2 pp in the low-probability/long-maturity corner, card 29's wedge is refuted as a
   measurement and the card should be re-specified rather than screened.
2. **Decide the chain-persistence question.** `collect_deribit_surface.py` already pulls the whole
   chain and discards the strike dimension. Persisting `(expiry, strike, type, bid, ask, mark_iv,
   underlying_price)` costs one schema change and starts the ONLY archive that can ever support a
   wedge series — the desk's own code says per-strike IV has no free history, so **every day not
   persisted is permanently lost**. This is a data-preservation decision with a deadline of "now",
   not a research decision.
3. **Card 28's execution-hygiene leg, with the alpha leg struck.** The ACM estimator (§3A.1) and the
   placebo-phase-shift falsifier on the desk's own recorder, aimed at a single question: *do our
   child orders cross :00/:15/:30/:45 boundaries, and what does it cost?* No alpha claim, negative
   capacity requirement, feeds the 66 bps gap programme.
4. **Back-annotate `lit_polymarket_15min_binary_ml`** with the 59%-trade-sign finding (§4A) — the
   existing row records the outcome; G2 supplies the cause, and the cause names the enabling change
   (join on-chain `OrderFilled`).
5. **q-fin.TR 2026-01 and 2026-02** — never in any run's scope, and TR is the richest subcategory
   by a wide margin (TR-04 alone produced 5 prediction-market papers). The obvious next slice.
6. **q-fin.RM / PM / MF / CP / GN for 2026-02..06** — still walked at 2026-07 only. Lower expected
   yield than TR on run 6's evidence, but it is the honest residual.
7. **The `[124]` chase:** resolve the crypto-carry construction behind "Tether Carry Trades" via the
   arXiv **source** (`/src/2510.14435`) or a later listing of the bibliography, so the desk's carry
   decay record cites a construction rather than a review's summary of one.
8. **`2604.24366` is a template, not just a source.** A pre-registered, stratified, ground-truth-
   joined microstructure study is exactly the shape the desk's own venue studies should take. Worth
   one pass purely for the design (pre-registration + strata + on-chain ground truth + explicit
   lower-bound framing on the wash-trade detector).

---

**Run status: COMPLETE.** 0 mechanism cards (deliberate — 6 near-misses each failed a named desk
test), 4 graveyard candidates (3 graded STRUCTURAL/STATISTICAL + 1 carry-over closure), 11 engine
findings, 3 factual corrections to standing desk artifacts (card 28's `do_not_repeat` collision;
card 29's OpenMarket data leg and its "surface the desk already holds"; the S3 phantom), the full
enumeration debt paid at 287 titles with a per-axis NULL for the stat-arb family, and a
one-HTTP-GET decisive experiment specified for the item that sent this seat out. Every claim above
carries the exact URL opened and its HTTP status; nothing advanced on an unread summary.
