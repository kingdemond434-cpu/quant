# BitMEX decade archive — disk-scoped ingest spec (directive `bitmex-ingest-spec`)

_Written 2026-07-31 (CRO cycle). Carve-out granted 2026-07-25; nothing may bulk-download until
this spec exists — it now does. [§33: wired -> docs/research/BITMEX_DECADE_INGEST_SPEC.md]_

## Why this is the T-lever, with numbers

`reports/gauntlet_certification.json` (2026-07-31) measures the whole discovery constraint: at
**T=310 days / N=420 trials** (se_annual_sharpe = 1.085) even the per-candidate path cannot admit
a true SR-3 edge — `min_passing_true_sharpe = 5.0`. The multiplicity bar is honest; the SAMPLE is
what is unpayably short. BitMEX XBTUSD is the longest continuous perp record in existence
(2014-11 →), with **funding since 2016-05**: ingesting it raises T for price- and funding-family
tests from ~310 to ~3,600+ days, which cuts the SE by ~√11 ≈ 3.3× and drops the admittable true
Sharpe from ~5 toward ~1.5 at the same trial count and the same unchanged gates. No gate is
touched; the evidence gets longer. It is also the pre-2017 asymmetric-information era (L1.11a)
and the raw feed for the black-swan library's real-tick replays (2016 hack era, 2017 mania,
2018-11 capitulation, 2020-03-12 cascade).

## Disk arithmetic (measured 2026-07-31: 23G free, hard fuse at 8G free)

| artifact | size | kept? |
|---|---|---|
| funding history XBTUSD+majors (8h rows, 2016-05→) | ~2-5 MB | KEPT, Bronze |
| trades day-file `.csv.gz` (public.bitmex.com/data/trade/) | 1-100+ MB/day, decade ≈ 25-60 GB | **TRANSIENT** — aggregated then deleted |
| derived 1m bars XBTUSD (parquet, ~5.3M rows) | ~300 MB | KEPT, Bronze |
| derived daily OHLCV+VWAP+trade-count | ~1 MB | KEPT, Bronze |
| raw tail for diff-verify | last 30 day-files ≈ 1-3 GB | rolling |
| quotes (L1) day-files | 5-10× trades | **NOT in v1** (see gate below) |

Raw ticks do not fit on this box. The FREE-FIRST "immutable Bronze" posture is honoured at the
*derived* layer; raw re-fetchability substitutes for raw retention because public.bitmex.com is a
stable versioned archive — its liveness joins the monthly free-source liveness check, and if the
principal approves the €4/mo Hetzner Storage Box (already on his page for the L2 moat), phase 3
upgrades to full raw-tick retention offsite. **Fuse:** the runner refuses to start a day-file if
free disk < 8 GB (`shutil.disk_usage`), pages instead — never trades disk against the recorders.

## Phases, strictly ordered

1. **Funding (same-day, trivial):** REST `/api/v1/funding` paginated full history XBTUSD (+ETH
   after) → `data/bitmex_funding.jsonl`. Diff-verify overlap vs Binance funding regime stats +
   the desk's carry model expectations (level/sign/8h cadence). This alone deepens the carry
   family's regime library by ~8 years and is the cheapest item on the whole spec.
2. **Trades → 1m bars (the bulk):** iterate day-files OLDEST-first from 2014-11-22; per file:
   download → stream-parse XBTUSD rows only → aggregate to 1m OHLCV+VWAP+count+buy/sell split →
   append `data/bitmex_xbtusd_1m.parquet` (idempotent by day; state file
   `data/bitmex_ingest_state.json` records last-completed day for resumability) → delete raw
   (keep rolling 30-day tail). Politeness: ≤1 file per ~2s, exponential backoff on 429/5xx.
   Runtime: days of background tranches — wire as `--tranche N` cron line exactly like
   `ingest_axes` (06:50Z, flock-guarded, CONFIDENCE tag per manifest house rules).
3. **Quotes (GATED, not in v1):** only after Storage Box approval AND a stated microstructure
   hypothesis that needs L1 (spread/imbalance families). A quote ingest without a mechanism prior
   is breadth-theater at 10× the disk.

## Verify-don't-trust (mandatory before any screen reads it)

- **Internal:** re-aggregate 20 random day-files a second time with an independent code path
  (pandas groupby vs the streaming aggregator); bars must match exactly.
- **External:** daily closes vs Coin Metrics BTC reference rate (free) over the full overlap —
  corr and level-diff bands; > 25 bps sustained divergence = investigate before adoption (BitMEX
  index vs spot basis is real and must be understood, not smoothed over).
- **Alignment declaration (SCREEN duty #4):** BitMEX day-files are UTC-dayed; bars are labelled
  by INTERVAL END, UTC. Any screen joining these to Coin Metrics daily rows uses UTC close ==
  UTC close; the kimchi/Turkey timezone-artifact class is the named hazard.
- Funding: cross-check 20 sampled rows against archived BitMEX announcements/period math
  (funding timestamp is the PAYMENT time; the rate applies to the preceding 8h window).

## What this feeds (pre-registered consumers, so the data is never idle on arrival)

- Re-run of the price-candidate families at T≈3,600 (Stage-A screen, ordering only — the
  two-stage law is unchanged; trials logged to the DSR ledger as always).
- Carry-family regime depth: funding-famine/inversion episodes 2016→ for the black-swan replay
  and the first-inversion probation calibration.
- Crisis replays with real ticks for the scenarios the library currently synthesises.

## Kill / rollback

State file + parquet are the only artifacts; `git clean` of the two data files reverts fully.
If the archive throttles or the box chokes, the tranche line is one manifest comment-out; the
fuse pages before disk is ever at risk. Success metric: `bitmex_xbtusd_1m.parquet` spans
2014-11→now, both verifications green, and the first T≈3,600 screen run logs its trial count.
