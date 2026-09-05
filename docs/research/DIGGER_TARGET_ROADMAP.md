# DIGGER TARGET ROADMAP — the 500-source dump, triaged for the digger (principal 2026-07-23)

> **UNIVERSE RETARGETED 2026-08-18, header added 2026-09-05.** The ~500-source dump this triages is a CRYPTO source list, supplied 2026-07-23 for the desk that was retired on 2026-08-18. It is kept for its TRIAGE METHOD -- how to cut 500 sources to the few worth a dig -- and as the record of which sources were graded. It is not a target list. The live source seeds are `docs/research/mt5_source_seeds.md`.
>
> Nothing below is deleted: a row recording what was tried, graded or exhausted on the retired
> desk is exactly the knowledge that stops a future session paying for the same thing twice. But
> it is a RECORD, not a queue. Every new row runs against the MT5/Fusion Markets universe -- FX
> majors/crosses/exotics, metals, equity indices, energy, softs, US share CFDs and the crypto CFDs
> Fusion itself lists. **No crypto-exchange venue may be hunted, screened or scored again**
> (`docs/LAWS.md` S1); crypto reference data is admissible only where a specific reading informs a
> Fusion-executable instrument, never as a universe of its own.


**Purpose:** the principal supplied ~500 multilingual crypto sources. Cataloging all 500 as
"sources we have" would be false and would bury the map in untested noise (source COUNT is not
edge — testable-signal-per-source is). Instead this triages the dump into PRIORITY TIERS for the
data-axis digger + Prospector to process AUTOMATICALLY at scale post-auth, with the reusable
`libs/research/axis_screen.py` gate applied to anything structured. Their effort becomes the
digger's roadmap, not a manual firehose.

## Tier 1 — STRUCTURED + TESTABLE + free (digger builds a collector + screens like kimchi)
The only tier that can produce a *tested* edge. Feasibility-checked from the VPS 2026-07-23:
- **Reachable free NOW:** HTX (`api.hbdm.com`, 200), Gate (`api.gateio.ws`, 200) funding/OI.
  Also standard: OKX, Bybit, Bitget, MEXC, BingX, KuCoin, Kraken, Coinbase, Deribit — funding,
  OI, basis, liquidations, insurance-fund, borrow-rate endpoints. Value: extends the queued
  cross-venue funding-DISPERSION sleeve to ~10 venues (marginal breadth, not orthogonal-new).
- **Regional VENUE PRICES (regional premiums):** Upbit (DONE = kimchi, the one real win),
  Bithumb/Coinone/Korbit (KR), bitFlyer/bitbank/Coincheck (JP), Indodax/Tokocrypto (ID),
  BtcTurk (TR = TESTED, timing artifact), Bitso/MercadoBitcoin (LatAm). CAVEAT proven this
  session: MOST regional premiums are timing artifacts (Turkey, Coinbase failed angle-20);
  Korea was rare. Screen each with the harness; expect ~1-in-10 to survive.
- **NOT free-sourceable from the box (checked):** Feixiaohao (SSL-blocked), AICoin (no free API)
  — the genuinely-new "Chinese retail attention/volume" signal is web-only/keyed. Needs a
  residential proxy or scrape infra = a real spend/effort decision, NOT free. Parked.

## Tier 2 — ON-CHAIN / data-vendor (mostly ALREADY covered or free-reconstructable)
Glassnode/CryptoQuant/Nansen/Kaiko/Amberdata/Tardis = PAID → free-first: reconstruct from
Dune/Flipside/DefiLlama/Footprint/GeckoTerminal/CoinMetrics-community + node RPC. The desk
already has stablecoin_flows, onchain_history, deribit_surface, liquidation_listener. Marginal.

## Tier 3 — DEV / CODE (the Prospector's job, charter already covers)
GitHub/Gitee/CSDN/Juejin/V2EX/SegmentFault + the quant frameworks (VNPy, Hummingbot, Freqtrade,
Nautilus, Lean, Qlib, FinRL...). The DIGGING_CHARTER is already GitHub-maximal + CJK-region-rich;
the Prospector mines these for strategy/factor code. No new action — it's doctrine.

## Tier 4 — NARRATIVE (news / social / VC / podcasts / research) — DEPRIORITIZED, mostly never
PANews/Odaily/Jinse/Weibo/Zhihu/Bilibili/DCInside/5ch/Habr/CoinTurk + all VC portfolios +
podcasts + house research. This is a research-CONTENT firehose: translation + NLP + entity
extraction, systematically hard to turn into a tested signal. `social_sentiment_nlp` is ALREADY
GRAVEYARDED ("NLP complex, paid data, crowded, not orthogonal"). The "narrative arrives earlier
in Chinese" claim is true and near-unmonetizable at solo scale. Digger may skim for a NAMED
mechanism only; NOT a monitoring target. Low/zero quant ROI.

## Tier 5 — LICENSE-GATED (do NOT free-source)
CNKI, Wanfang, DBpia, RISS, IEEE/ACM/Springer/Elsevier/Wiley/JSTOR paywalled, Kaiko/Nansen/
Glassnode paid tiers. These are the exact paid-institutional-DB / vendor class the DIGGING_CHARTER
§13 legitimacy gate excludes from free-sourcing. Open-access ONLY (arXiv/SSRN/Zenodo/OpenAlex/
SemanticScholar/DOAJ/CORE — already in the research feed).

## THE RULE (why this beats "monitor 500 sources")
The edge is testable-signal-per-source, not count. RenTech is clean-data-and-models, not 1000
forums. So: the digger works TIER 1 first (structured, screened, kept only if it survives the
gauntlet), TIER 3 on cadence (code mining), skims TIER 4 for named mechanisms only, and NEVER
free-sources TIER 5. Realistic yield from 500 sources ≈ a handful of Tier-1 survivors — the same
1-in-40 rate kimchi came from. All gated on: brain auth + connector. Building the intake while the
engine is off is premature; this roadmap is what the digger executes when it wakes.

## 2026-07-24 dump triage (principal's mempool/MEV/CN list -- ChatGPT-sourced, entries UNVERIFIED until probed)

**BUILT NOW (verified live first):** USDT/CNY P2P premium (ledger #76 unparked) --
`collect_cny_premium.py`, OKX P2P keyless (190 quotes verified from this box) vs open.er-api
USD/CNY; forward clock m=4, direction +1 pre-registered from mechanism; TRY-falsifier logged.

**QUEUED (real, free, one-at-a-time as clocks free up):** CN cross-venue flow axis -- OKX/Gate/
MEXC/HTX free public APIs (funding/taker-ratio spread vs Binance as CN-retail positioning proxy).
Distinct mechanism from price premiums (NOT the graveyarded regional-premium class). One
pre-registered construct when built; do not axis-spam.

**DEPRIORITIZED (free != worth it):** mempool/MEV stack (mempool.space, Ethernow, EigenPhi, MEV
dashboards, Xatu) -- latency-gated behind the 50ms gate per the frontier menu; not the desk's
daily-horizon cadence. Revisit only at live if venue-toxicity context is needed.

**CATALOG-ONLY (do not build without a mechanism hypothesis):** BRK/Bitview (8,000+ BTC on-chain
metrics) -- the desk's own screens graveyarded on-chain usage at daily horizon (throughput killed
by 11y held-out OOS); a bigger metrics menu does not revive a dead class. Aggregators
(tckr, coin-mcp, crypto-yfinance, free-crypto-news, cryptocurrency.cv) -- unverified ChatGPT
entries; wrappers around sources the desk already pulls direct (free-first doctrine prefers
direct pulls with owned methodology). Probe only if a specific gap appears.
