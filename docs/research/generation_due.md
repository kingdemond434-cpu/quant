# Generation due -- 2026-07-16T23:23Z (stage S0)

The cadence engine flags these; the brain executes SCOPED generate runs (graveyard-excluded, pre-registration mandatory) and then marks them done by setting gen_done_<name> / last_live_generate in data/cadence_state.json.

- fred_macro family: deep history available -- scoped generate run owed
  - **CLOSED. This file is a 2026-07-16 snapshot and was never regenerated -- the item has been
    stale since 2026-07-17.** The cadence condition (`run_cadence.py:202`) clears on
    `gen_done_fred_macro_family`, which `data/cadence_state.json` has carried since
    2026-07-17T08:55:24Z. Paper duty closed then (3 FRED-family overlays EV-rejected 0.004-0.013;
    later `net_liquidity_impulse` 0.0026 and `dxy_shock_beta_rotation` 0.0052 on 07-22).
  - **2026-07-28: the EMPIRICAL half, never done before, is now done.** 5 mechanism-first
    candidates screened through the audited harness against deep FRED history aligned to the Coin
    Metrics BTC close -- 12 cells, 0 SCREEN-INTERESTING, 10 SCREEN-UNDERPOWERED, 2 TIMING-ARTIFACT
    (VIXCLS 5b/20b: same-period corr -0.18/-0.21, residual IC collapses -- VIX coincides with BTC
    drawdowns, it does not lead them). No forward clock started. `scripts/screen_fred_macro_axis.py`
    -> `data/fred_macro_screen.json`; deep series archived to `data/fred_macro_deep.json`.
  - **"Deep history available" was wrong, twice over.** `collect_fred_macro.py` caps at
    `_LOOKBACK_DAYS=1200` despite a docstring claiming FRED "serves deep history on day one", so
    `data/fred_macro.json` holds only 2023-04-17+ (818-846 obs). And even with the full FRED pull
    (DGS10 1962, VIXCLS 1990, DTWEXBGS 2006) the sample is hard-capped by BTC starting 2010-07 at
    ~4030 US business days -- still short of the 4268 independent observations `stage_a_screen`
    needs to call a daily cell powered at `ic_min=0.03`. This axis cannot produce a powered daily
    verdict, ever. Reported, not worked around; the gate was not touched.

## STANDING TARGETING ORDER (principal 2026-07-19, founders review #4)
All generate runs target CROSS-SECTIONAL FACTOR FAMILIES -- carry, momentum, basis
(incl. cross-venue once Bybit data matures), and vol/short-vol -- ranked across the
FULL perp universe. Single-name candidates enter only as members of a cross-sectional
rank, never as standalone silver bullets. Weak signals that portfolio together beat
one perfect backtest; the count-uncapped gauntlet + trials-scaled multiplicity floor
make the breadth statistically honest.

## HYPOTHESIS-ENGINE MECHANISMS (principal 2026-07-24 upgrade -- run ALONGSIDE the standard miners every cycle)
Generation is no longer data-mining alone. Every cycle also generates via three mandatory mechanisms:
1. COMBINATORIAL SYNTHESIS: force hypotheses that COMBINE two low-correlation axes from the Data
   Universe Map and test joint predictive power (dev-activity x capital-flow, OI x on-chain,
   funding x LS). Every conjunction is a DSR-counted trial; the composite must beat its parts OOS.
2. GENETIC FEATURE MUTATION: apply non-linear transforms to already-screened features before
   retesting -- z-scores, higher-order derivatives/accelerations, divergences, ratios, regime-
   conditioned versions. Each mutation is a counted trial; log every construction tried.
3. FORCED-MECHANISM MODELING: generate from known INELASTIC market constraints -- leverage caps,
   auto-liquidation thresholds/cascades, scheduled miner selling, funding settlement boundaries,
   options-expiry pinning, stablecoin-supply mechanics. Structural mechanisms, not price patterns.
These feed the SAME gauntlet at the SAME bar; no promotion authority. They exist to turn idle
mined data into tested hypotheses (DATA-UTILIZATION LAW) and to break out of the picked-clean
price-only space that produced 420/0.
