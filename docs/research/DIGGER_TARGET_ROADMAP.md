# DIGGER TARGET ROADMAP — the 500-source dump, triaged for the digger (principal 2026-07-23)

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
