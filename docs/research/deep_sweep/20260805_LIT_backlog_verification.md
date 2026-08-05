# LIT deep-miner ITEM-1 seat — source-verification backlog clearance

**Date:** 2026-08-05
**Seat:** LITERATURE DEEP-MINER / ITEM-1 (verification, not cataloguing)
**Ground:** the desk's measured bottleneck is VERIFICATION. It catalogues faster than it verifies.
5 of the 9 pending items were catalogued by this very organ 5 days ago. Closing them beats any new source.
**Write freeze:** this file is the ONLY write. Read-only on scripts/, libs/, all shared ledgers.

## Provenance grades used
- `[FETCHED]` — the URL was opened from this box and the BODY was read. HTTP status recorded.
- `[ABSTRACT-ONLY]` — landing/abstract page read, full text not opened.
- `[SEARCH-SUMMARY]` — search snippet only. **A LEAD, NEVER EVIDENCE.**

## Failure-mode vocabulary (kept distinct on purpose)
- **ABSENT** — never existed.
- **UNREADABLE** — exists, blocked *from this box* (routing finding, NK-005 class; not a verdict about the source).
- **DEAD** — existed, now gone.
- **RESTRICTED-BY-LICENCE** — exists and is reachable, but §13 forbids the use. HARD STOP, never a hurdle.

## Checklist (updated live as each resolves)

| # | Item | Kind | Verdict |
|---|------|------|---------|
| 1 | NAVER DataLab (Korean search-attention) | VERIFY | PENDING |
| 2 | Carry↔liquidation (BIS WP1087) + COT-BTC extension | VERIFY | PENDING |
| 3 | Regulatory-event timeline (Auer–Claessens 5-class) | VERIFY | PENDING |
| 4 | Stablecoin run signature (NY Fed sr1073) | VERIFY | PENDING |
| 5 | KR venue-state layer (Upbit + Bithumb flags/notices) | VERIFY | PENDING |
| 6 | bitFlyer getexecutions + self-recorded candles | VERIFY | PENDING |
| 7 | Upbit Historical Market Data portal | DECIDE | PENDING |
| 8 | Glassnode / CryptoQuant vendor-replacement | DECIDE | PENDING |

---
## ITEM 2 — Carry↔liquidation (BIS WP1087) + COT-BTC extension — **VERIFIED, WITH THE HEADLINE CLAIM MATERIALLY WRONG**

**VERDICT: verified-clean on ACCESS and LICENCE; the "41y COT screen, one-contract extension" framing is REFUTED and must not be repeated.**

### (a) Does CFTC COT publish a BITCOIN row? YES. Keyless. `[FETCHED]`
Primary machine-readable route is the CFTC **Public Reporting Environment (Socrata)**, no key, no
registration, JSON/CSV, full SoQL (`$where/$select/$group`) supported:

- Traders in Financial Futures, futures-only: `https://publicreporting.cftc.gov/resource/gpe5-46if.json` → **HTTP 200, application/json, 89 columns**
- Legacy futures-only (the 41-year set): `https://publicreporting.cftc.gov/resource/6dca-aqww.json` → **HTTP 200**
- Human/text weekly file: `https://www.cftc.gov/dea/futures/financial_lf.htm` → **HTTP 200, 209,797 B text/html**

### (b) THE OBSERVATION COUNT — this is where the desk's claim breaks
Verbatim `$group` result over `market_and_exchange_names like '%BITCOIN%'` (both TFF and legacy sets agree):

| market_and_exchange_names | n (weekly rows) | first | last |
|---|---|---|---|
| **BITCOIN - CHICAGO MERCANTILE EXCHANGE** | **434** | **2018-04-10** | 2026-07-28 |
| MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE | 274 | 2021-05-04 | 2026-07-28 |
| BITCOIN-USD - CBOE FUTURES EXCHANGE | 72–73 | 2017-12-19 | **2019-04-30 (DEAD — Cboe delisted)** |
| Nano Bitcoin - LMX LABS LLC | 89 | 2023-11-07 | 2025-07-15 (DEAD) |
| Nano Bitcoin / NANO BITCOIN PERP STYLE - COINBASE DERIVATIVES | 54 each | 2025-07-22 | 2026-07-28 |
| BITCOIN CASH PERP STYLE - COINBASE DERIVATIVES | 13 | 2026-01-13 | 2026-07-28 |

**The legacy COT set really is 41 years — `min(report_date) = 1986-01-15`, `max = 2026-07-28`,
286,694 rows.** But that 41 years belongs to the REPORT, not to bitcoin. **The BTC row is 434 weekly
observations over 8.3 years, and it does not start at CME launch (2017-12-17) — it starts 2018-04-10,
~4 months late** (below the reportable-trader threshold until then). The Cboe contract that covers
2017-12-19→2018-04-10 is a *different, dead* contract on a *different* exchange.

> **CLAIM STATUS.** "One-contract extension of an existing 41-year COT screen" is TRUE as plumbing
> (same schema, same loader, one more `market_and_exchange_names` value) and **FALSE as statistics**.
> Anyone reading it as "41 years of BTC positioning" is wrong by a factor of ~5. Fix the wording in
> the source card.

### (c) POWER — **UNDERPOWERED, and here is the enabling change (NOT "no edge")**
Desk screen target ≈ **4,268 independent observations. BTC-CME COT supplies 434.** That is **9.8×
short**; at 52 obs/yr the series reaches 4,268 in **year 2100**. Per L1.25 this is an UNDERPOWERED
axis, never a null. Named enabling changes, in order of honesty:
1. **Change the unit of observation.** BIS WP1087's own mechanism is *carry → sell-side liquidation*.
   The dependent variable (liquidations) is available at minutes; only the COT *conditioner* is weekly.
   Run it as an event study on liquidation episodes conditioned on the most recent COT print — n is
   then the episode count, not the week count.
2. **Pool contracts.** BTC + MICRO BTC + ETH + MICRO ETH ≈ 1,400 rows, but they are near-collinear
   (same underlying, same reporting week) so **n_eff ≪ n** — this buys far less than it looks.
3. **Do not** pool the dead Cboe/LMX/Coinbase rows to inflate n. Different contract, different venue,
   different trader population.

### (d) EXACT REPORT AND COLUMN NAMES (so nobody has to guess)
Bitcoin sits in **Traders in Financial Futures (TFF)**, group `FINANCIAL INSTRUMENTS`, **not** the
Disaggregated commercial/non-commercial ag taxonomy. Verbatim latest BTC row (2026-07-28):
```
cftc_contract_market_code = 133741      contract_units = (5 Bitcoins)
futonly_or_combined = FutOnly           commodity_group_name = FINANCIAL INSTRUMENTS
open_interest_all = 20019               traders_tot_all = 122
dealer_positions_long_all = 6525        dealer_positions_short_all = 2445
asset_mgr_positions_long  = 4798        asset_mgr_positions_short  = 2499
lev_money_positions_long  = 3295        lev_money_positions_short  = 10168
nonrept_positions_long_all = 722
```
`lev_money_*` (leveraged money = hedge funds/CTAs) is the WP1087-relevant leg: **the short side is
3.1× the long side in the latest print**, which is the sign the carry→short-liquidation mechanism
predicts. Contract code **133741** is the stable join key (safer than the name string, which has
inconsistent whitespace — note `"Nano Bitcoin  -"` has a double space in TFF and a single space in
legacy: **the same contract has two different name strings across the two datasets**. Join on code.)

### (e) CADENCE AND PUBLICATION LAG
Weekly. Snapshot = **Tuesday** close; release = **Friday 15:30 ET**. **Publication lag = 3 days**, so
any live use must lag the conditioner by ≥3 days or it is look-ahead. (The `report_date` field is the
TUESDAY, not the release date — a classic trap: using `report_date` as the availability timestamp
back-dates the information by 3 days.)

### (f) §13 LICENCE — CLEAN
US federal government work product, CFTC public reporting. Keyless, no registration, no click-through,
no attribution requirement, explicitly published for public use. **No §13 obstacle.** Socrata applies a
soft rate limit for anonymous callers (app token optional, raises the limit; not required).

**ROUTE:** correct the "41y" wording on the source card; card is otherwise CLEARED TO BUILD.

---
