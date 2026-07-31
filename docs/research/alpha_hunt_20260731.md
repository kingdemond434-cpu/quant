# ALPHA HUNT — Claude family, 2026-07-31 (the 6 offensive lenses, actually run)

Honest provenance: these are the six alpha lenses executed as a real hunt pass, NOT the lens text.
SINGLE-FAMILY (GPT-9 seat dark until OpenRouter funded — so none of this is cross-family
confirmed; that is a weaker signal by construction, L1.33). Every candidate is novelty-checked
against the watchlist + existing screens before listing, mechanism-first, and free-data-only.
Stage-A only: zero promotion authority (L1.6). Screen-on-discovery still owed per candidate.

## LENS 1 — NEW EDGE FAMILY (forced participant)

- **ETF creation/redemption → next-session basis/spot** — ALREADY OWNED: `screen_etf_flows.py`
  exists + Farside collected. Verdict: not novel; check whether it's screened as a TIMING signal
  vs a level, and if not, that refinement is the only gap. (routed: existing screen)
- **Stablecoin mint/redeem → market beta** — ALREADY OWNED: watchlist card 9, screened. Not novel.
- **★ POST-LIQUIDATION-CASCADE REVERSION (regime-gated)** — NEW. `liquidation_listener.py`
  collects the feed; no reversion screen exists (grep clean). Forced participant: liquidation
  engines market-close underwater leverage at any price, overshooting past fair value; the
  overshoot is mechanically transient because the forced flow ends when the cascade clears.
  Mechanism, falsifiable: in the 5–30 min AFTER a liquidation-intensity z-score spike > k, does
  price mean-revert a measurable fraction of the cascade move? Regime gate = the z-score itself,
  so it only trades when the forced flow is present. Data: owned. → axis watchlist + R-row.
- **PRE/POST 8h-FUNDING-BOUNDARY MICRO-REVERSAL** — NEW-ish. Forced participant: leveraged perp
  holders on the paying side have an incentive to flatten before settlement, then re-enter after.
  Mechanism: predictable drift into the funding timestamp + reversal out. The desk harvests
  funding LEVEL but does not trade the boundary TIMING (grep clean). Cheap to screen on owned
  perp data. Caveat: heavily arbed on majors — screen on second-tier perps first. → watchlist.

## LENS 2 — DATA ASYMMETRY (moat feature no competitor can buy)

- **★ CROSS-VENUE QUOTE LEAD-LAG at our own synchronized timestamps** — NEW, pure moat. The desk
  records multiple venues' books at synced LOCAL timestamps (the L2 moat). Vendor data cannot
  reconstruct this: their cross-venue timestamps are normalized/interpolated, ours are the actual
  capture instants. Mechanism: which venue's book-imbalance moves FIRST predicts the others'
  mid over sub-minute horizons. This is information that exists ONLY because of how we capture.
  Extends `micro_factory.py` (same L2 store, new feature family). → improvement_inbox (engine) +
  R-row. Highest reconstruction-cost item on the page (L1.11a).
- **REALIZED-vs-MODELED SLIPPAGE as a proprietary liquidity-stress gauge** — NEW. Our execution
  tape records what WE actually paid; cost_model.json records what we EXPECTED. The gap is a
  liquidity-stress signal nobody else has (they have neither our fills nor our model). Mechanism:
  a widening realized-minus-modeled slippage precedes vol/liquidity events. Bootstraps only once
  live fills accrue (ties to probe capital, R0106). → R-row, gated on live fills.

## LENS 3 — CAPACITY & COMPOUNDING

- **★ CROSS-EXCHANGE FUNDING-SPREAD as a decorrelated 2nd sleeve** — NEW. Long funding on the
  cheap venue, short on the rich venue when |spread| > round-trip cost. Genuinely DECORRELATED
  from single-venue carry because it earns the SPREAD, not the level — so it pays in regimes where
  flat-funding kills the carry sleeve. Funding collected on 4+ venues already
  (hyperliquid/bitmex/…). This is the single most valuable item here: a second sleeve is the
  variance-drag reduction that raises the GEOMETRIC mean directly (the R0101 portfolio lever made
  concrete). → R-row, high priority.
- Maker-first routing / BNB fee tier — ALREADY ROWED (tier register). Not novel.

## LENS 4 — REGIME-CONDITIONED

- **HIGH-FUNDING-REGIME CARRY SIZING** — NEW-ish refinement. The carry edge is fat when funding is
  extreme and thin when flat; size the existing sleeve UP only in the detectable high-funding
  regime (z-score on the funding the desk already collects) rather than sizing flat. Pure
  Sharpe-per-turn improvement on an edge already deployed. Low effort, owned data. → R-row.
- Post-liquidation reversion (above) is also regime-conditioned — the strongest cross-lens hit.

## LENS 5 — SMALL-CAPACITY FRONTIER

- **★ NEWLY-LISTED-PERP FUNDING NORMALIZATION** — NEW. A brand-new perp's funding is wild for
  ~24–72h then normalizes predictably; too small and too operationally annoying for a tier-1 desk,
  so it's ours for free (L1.18a). Mechanism: fade extreme early funding toward the cross-sectional
  norm. Data: owned (new-listing detection + funding). Capacity-limited by design → hunt, fill,
  retire on arithmetic. → watchlist.
- Aster/Lighter perp-DEX funding, KR/CN premium — ALREADY ROWED / prospector ground. Not novel.

## LENS 6 — FASTER PROMOTION

- **EVENT-DENSITY PROMOTION CLOCK** — NEW. Event-driven edges (funding, liquidations, ETF flows)
  accrue evidence PER EVENT, not per calendar day, so their forward clock should count EVENTS, not
  days — a funding edge sees ~3 obs/day, a liquidation edge sees dozens on a volatile day. The
  desk's 28-day calendar clock under-credits them. Mechanism: a per-mechanism event-count clock
  that promotes an event-driven survivor faster WITHOUT lowering the statistical bar (same n_eff,
  reached sooner). This directly attacks bottleneck #1 (calendar-time accrual). → R-row.
- 8h shadow panels / paper-sleeve auto-spawn — ALREADY RUNNING / ROWED. Not novel.

---

## THE HUNT'S OWN VERDICT — top 4 to row (by validated-compounding per unit effort)

1. **Cross-exchange funding-spread sleeve** (Lens 3) — a genuinely decorrelated second sleeve;
   variance-drag reduction raises geometric growth directly. Highest EV.
2. **Post-liquidation-cascade reversion** (Lens 1+4) — forced-flow overshoot, regime-gated, data
   fully owned, cheap to screen. Strongest single new edge.
3. **Cross-venue quote lead-lag** (Lens 2) — pure moat, highest reconstruction cost, extends an
   organ that already runs (micro_factory).
4. **Event-density promotion clock** (Lens 6) — not an edge but a multiplier: makes every
   event-driven edge promote faster, attacking the #1 bottleneck for free.

Rowed as R-rows this pass; the other candidates sit on the axis watchlist for screen-on-discovery.
When the GPT-9 seat funds, this exact pass reruns cross-family and the CONFIRMED/CONTESTED deltas
become the real signal.
