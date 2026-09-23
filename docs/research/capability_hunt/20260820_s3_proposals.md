# CAPABILITY HUNT PROPOSALS 20260820 slot 3

LENS: CAPACITY & COMPOUNDING -- what lets the book carry more risk-adjusted size or compound FASTER: a decorrelated sleeve, a cost-tier cut (every bp is pure CAGR), a funding-harvest cadence, a capacity band we are leaving on the table.

## A -- Claude family

Verified. Both corrections land, and the second one sharpens the proposal rather than killing it.

## Correction to my proposal — and where it actually bites

**My falsifier partly fired, and I'm reporting it as such.** Two claims I made were wrong:

1. **Equity.** I read €633.89 from `MT5_DESK_STATE.json`; `data/gateway_state.json` carries €1,833.89. Two money-path artifacts disagree by 2.9× — an L1.61 finding in its own right. At the higher figure gold's floor **under**-sizes (`realised_q` 0.958% vs `Q_OPT` 1.27%) rather than over-sizing, so my "2.18× over policy" applies only at the lower one.
2. **`cap_by_heat`'s single-q is latent, not live.** `data/sleeves.json` does not exist, `load_sleeves()` returns `[]`, and the gateway has been PAUSED since Aug 17 (*"Fusion switch in progress"*). The book is gold-only by construction, so one q is currently harmless — exactly the falsifier I named.

**And `auto_lot` is not the blowup I was about to claim.** `gateway.py:253` really is gold-hardcoded (`CONTRACT_OZ=100`, `FX_EUR=0.92`), and on a JPY cross that formula understates risk-per-lot 5.9× (EURUSD: 939×) — but `promoter.py:180` writes `"lot": PROMOTED_LOT = 0.01` as a **literal**, so `gateway.py:973-975` takes the `else float(s["lot"])` branch and never reaches `auto_lot`. Defused by a constant, not by design.

**Which is where the real defect is, and it points at timidity, not ruin.** At €1,833.89, for a promoted CADJPY sleeve:

- it trades a **fixed 0.01 lot forever** ≈ €0.98 risk = **0.053%** of equity, against `Q_OPT` 1.27% — **24× under policy**;
- `cap_by_heat` charges it `realised_q(equity)` = gold's **0.958%** — **18× its actual risk**;
- `room = int(0.0381 / 0.00958)` = **3**, and `GOLD_WINDOWS` holds exactly 3 live legs (`ny_open` quarantined 2026-08-17), all senior by `sleeve_set()`.

**So every JPY-cross sleeve the promoter can ever promote is deferred, at current equity, for heat it does not use** — while the shadow register holds 7 non-gold candidates (`shadow_forward.py:52-55`) and `daily_cycle.py` runs the promoter automatically. The desk's only diversification path is structurally closed by a phantom denominator, and a deferred sleeve writes one log line and no artifact.

That is the same missing capability — per-instrument EUR-risk-per-lot, read from `universe.json`'s `tick_size`/`tick_value` which are already fetched — now with a live mechanism and the anti-timidity direction the constitution scores as a defect. `PROMOTED_LOT = 0.01` is also an unpriced clamp (L1.51): a hardcoded constant with no derivation holding a validated sleeve at 4% of its policy size.

**Added brainstorm rows from the map (each verified in the report, not asserted by me):**

31. `shadow_forward.py:97` prices gold spread at `0.48` — 3% of the measured `16.0`. That is **the only artifact accruing forward evidence for promotion**, so the two-stage law's promotion evidence is generated at 3% of true cost. GAP #114 names `portfolio_projection.py`; this instance is on the promotion path. — **S**
32. `libs/research/capacity_policy.py` never migrated — `deadman_state.json`, Binance `exchangeInfo` floors, `nav_attestation.jsonl`, `DEFAULT_BOOK_USD=50_000`. Zero importers under `desks/mt5/`. **MT5 capacity is undefined**, not merely mis-scoped. — **S**
33. `swap_long`/`swap_short`/`swap_mode` are unread `symbol_info` fields and the converter is already written at `libs/costs/mt5_calibration.py:86-95`. `financing.py` refuses to invent the rate while the rate is one field away. — **A**
34. `account_info().leverage` is read nowhere in the repo; `order_calc_margin` is a boolean skip guard only. 1:500 is documentation. — **A**
35. `markout.py` is wired into `daily_cycle.py:93` but `data/order_intents.jsonl` and `data/live_ledger.jsonl` do not exist — slippage measurement is wired and starved. Crypto precedent: modelled 0.35bps, realised ~16bps. — **A**
36. Root `desks/mt5/run_hunt12.py` shadows `research/run_hunt12.py` and is **missing the multiplicity correction**; root `portfolio_projection.py` lacks the API `research/allocation.py:28` imports. Diverged twins on the import path. — **A**
37. `research/ceiling.py:55` and `calibrate_engine.py` insert `/home/user/Aurum`; the tree is `/home/quant/Aurum`. Cannot import on this box. — **B**
38. Last live pass: all four sleeves rejected, `10015 Invalid price` + `10017 Trade disabled`. Item 26's fence has a confirmed instance. — **S**
39. `universe.json` holds 22 symbols, **no indices, energy or softs**, while the MT5 mandate names them and the desk holds COT parquet for sp500/nasdaq100/dxy. `fetch_universe.py:122-129` reports the absence and nothing acts on it. — **A**
40. Only H1 is ingested. Three `_M15.parquet` files exist with no reader or writer. — **B**

*Next: whether `_HEAT_BASE_LEGS = 3` silently encodes the gold book, making the budget shrink if gold retires; and pricing the deferred-sleeve clamp in euros per L1.51.*


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
