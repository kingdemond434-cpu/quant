# GLOBAL GOLD DATA DISCOVERY MANDATE

Status: BINDING. Goal: gold desk becomes a proprietary data organism assembled from hundreds of
first-party public sources — not "free Bloomberg", but point-in-time, authoritative, and deeper
than retail systems on information axes others aren't combining.

## Discovery targets (hierarchy: official > exchange > issuer > academic > regional)
1. **SGE** — Shanghai Gold Benchmark Price + reports (official daily gold benchmark).
2. **SHFE** — Gold futures volume/OI/market statistics.
3. **LBMA** — London vault holdings, clearing statistics (monthly/quarterly).
4. **Swiss Customs** — gold imports/exports by country; monthly from 2012, granular gold
   classifications since 2021.
5. **SPDR GLD** — historical holdings XLSX + gold bar lists (blocked URLs at
   spdrgoldshares.com — register as miner task, retry mirrors/archives).
6. **WGC Goldhub** — supply/demand datasets.
7. **CME** — GC futures/options OI, volatility analytics, settlement (public).
8. **CFTC** — COT positioning (public historical reporting environment).
9. **FRED / ALFRED** — point-in-time macro vintages; DGS2/10, DFII10, T10YIE, DFF, DTWEXBGS,
   VIXCLS (fetch_fred.py working: 1962–2026 lake).
10. **GDELT 2.0** — translated global news every 15 min, 100+ languages (quarantined input).
11. **BIS / IMF / ECB SDMX, BoE, BEA, BLS, Treasury TIC, EIA, SEC EDGAR** — macro/FX/flows/
    fundamentals mesh.
12. Regional-language sources: Chinese, Hindi, Arabic, Turkish, Russian gold-market reporting.

## Rules
- Discovered web material is **quarantined research input**, never authoritative data, until
  provenance + point-in-time checks pass (event_time/published/available/ingested, source,
  source_version, revision_id, raw_hash, license, quality_flags).
- Original raw responses immutable forever; normalized/feature layers derived.
- Register every candidate dataset in `data_registry.json` (infer schema, publication schedule,
  historical archive depth). Dataset lifecycle: DISCOVERED → INGESTED → QUALITY-PASSED →
  RESEARCH-USEFUL → OOS-INCREMENTAL → FORWARD-INCREMENTAL → CORE; demotion allowed.
- Score every dataset by ROI_data; a free dataset consuming hours with zero unique information
  is more expensive than a paid feed.

## Gold-specific combination (depth target)
MT5 executable ticks + SGE benchmark + SHFE volume/OI + CFTC positioning + CME OI/options +
LBMA vaults/clearing + Swiss flows + GLD holdings + WGC + macro PIT + GDELT sentiment →
mechanism mining for XAUUSD across asia/london/ny sessions.