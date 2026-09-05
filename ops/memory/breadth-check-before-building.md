---
name: breadth-check-before-building
description: "Before adding crypto sleeves or data collectors, check the graveyard + existing pipeline — the breadth campaign is exhausted and OI/LS/on-chain already exist."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4af772ee-24a6-45c2-aa20-7c72e83a9443
---

> **ARCHIVED 2026-09-05 — the retired crypto-exchange era.** Every artifact this note names (`collect_binance_metrics.py`, `libs/research/crypto_sleeves.py`, `crypto-desk-state.md`) belongs to the crypto-exchange desk retired on 2026-08-18, and several are deleted. **The RULE it teaches is not retired and is one of the most useful things in this directory:** before building a sleeve or a collector, grep the graveyard and the existing pipeline for prior work — the desk has repeatedly rebuilt what it had already tried and rejected. Apply that rule against the MT5 graveyard (`docs/graveyard.md`) and `desks/mt5/`.
On 2026-07-04, asked to "max data breadth + alpha pipeline for growth," I built two things that were **already done or already falsified**, then reverted both. Don't repeat this.

**What already exists (do NOT rebuild):**
- **OI + long/short positioning**: `collect_binance_metrics.py` archives to `data/crypto_metrics.parquet` (called BY the always-on cash-carry executor + QuantResearchTick, so it ticks reliably), consumed by `run_derivative_shadow.py` (forward, ~day 8/40) and `run_derivative_backtest.py` (real ~30d **hourly** gauntlet: CPCV/DSR/PBO/RC). I built a duplicate `run_positioning_flows.py` — deleted it.
- The free-data layer is broad already: stablecoin on-chain reserves, hyperliquid cross-venue funding, cross-exchange dispersion, options VRP/DVOL, F&G, liquidations (forward). See `desks/mt5/` (the crypto-desk-state note was deleted 2026-09-05 with the retired desk).

**What is already FALSIFIED (do NOT re-wire into the shadow):**
- `xsec_lowvol_returns` — REJECTED, Sharpe −0.83, the low-vol anomaly **inverts** in crypto (lottery-demand: high-vol names win).
- price/`funding_reversal` (short-term reversal) — REJECTED, negative **gross** Sharpe (−0.48), unprofitable even at zero cost.
These live in `libs/research/crypto_sleeves.py` as graveyard functions, NOT as unused good sleeves. I mistakenly read "exists in library = free breadth." The trailing-Sharpe combiner zero-weights losers, so adding them *looked* like it raised backtest Sharpe (0.52→0.57) — that was an **artifact**, not edge (the same frozen book also read 0.66 on another run = the number is universe-noise).

**Why:** the breadth campaign is genuinely exhausted — the desk's own record is "0 survivors, carry is the lone net-positive; more families = diminishing returns; the lever is genuinely-new (mostly paid) data or forward-validation TIME." Re-adding rejected sleeves is the "re-litigate falsified hypothesis" anti-pattern the constitution forbids.

**How to apply:** before adding any sleeve → grep `web/discovery.json` + `desks/mt5/` (the crypto-desk-state note was deleted 2026-09-05 with the retired desk) for prior rejection. Before adding any data collector → read `scripts/run_daily_research.py` `_STEPS` (the full pipeline list). New candidates go through the discovery GAUNTLET, never wired straight into the frozen certification shadow. Cost of ignoring this: I reset the perp shadow forward clock 3→1 day for nothing. Reversibility (`rollback_guard`) cleanly undid it — checkpoint before subsystem edits.
