# FRONTIER_AI_LAYER — 15-item mandate (absorbed 2026-08-17, advisor round 3)

Rule of the layer: AI/ML improves WHERE we trade, WHICH strategy trades, WHICH trades we reject,
HOW we size, HOW we manage winners, WHEN a strategy is dying, and what our own live history says
we are systematically getting wrong. It NEVER replaces the deterministic alpha base and NEVER
freestyles entries. Every module needs its own P&L attribution (FILTER ROI); if a module does not
increase forward portfolio utility, delete it.

Statuses: EXISTS (already live/wired) | BUILDING (in progress) | QUEUED (codified, not started)

1. AI_META_LABELER (QUEUED): deterministic base unchanged; ML layer estimates per proposed trade:
   P(edge_positive|state), expected_R, tail_loss_probability, trade_quality → VETO/REDUCE/NORMAL/BOOST.
2. PERSONALIZED_FAILURE_MEMORY (QUEUED, live-ledger ready): every live trade searchable by entry
   state, regime, spread, session, direction, family, confidence, MFE, MAE, exit path, result;
   before a trade, find 50-500 nearest historical trades, estimate conditional outcome. Compounds
   as trades accumulate. (live_ledger.jsonl already records the raw stream.)
3. VETO_ALPHA (QUEUED): separate model over losers only: P(loss>1R), P(MAE>thr), P(false_breakout),
   P(stop_then_target), P(strategy_failure|state). Removing the worst 10-20% of trades without
   killing winners > finding another mediocre strategy.
4. MISSED_TRADE_ALPHA (QUEUED): log every signal not traded + why (confidence, capital, veto,
   corr cap, spread, regime gate, execution). Per gate: P&L_WITH vs WITHOUT, MARGINAL_DD,
   MARGINAL_ELOGW, FALSE/TRUE_VETO_RATE. Filters that cost money get deleted.
5. SIGNAL SELF-GRADING (QUEUED): signal → trade/veto → MFE/MAE path → expected vs actual →
   calibration error → feature/regime attribution → edge-health update. Continuous feedback loop.
6. STRATEGY_SELECTOR_ALPHA (BUILDING — this is what latent_regimes.json delivers): predict
   P(strategy family profitable | current state) and route research/capital to the families with
   edge NOW, instead of predicting only price direction.
7. MODEL_DISAGREEMENT (QUEUED): multiple independent estimators (rules, boosting, regime model,
   kNN history, Bayesian, cross-asset); MODEL_DISPERSION / DIRECTIONAL_DISAGREEMENT as features
   (extreme disagreement → unstable regimes / vol expansion / false breakouts).
8. SIGNAL_INVERSION MINER (PARTIAL-EXISTS): hunt16 already sweeps LONG+SHORT separately and the
   sweep/fakeout families ARE inversions; remaining cheap variants (fade_after_failure,
   trade_stop_event, trade_missed_breakout, reverse_exit_only) queued as hypothesis generation.
9. SOCIAL ATTENTION VELOCITY (QUEUED): mention velocity/acceleration, unique-author growth,
   comment-depth growth, sentiment×volume, sentiment dispersion, narrative concentration,
   bot-coordination, influencer diffusion — replacing raw sentiment scores (arXiv-supported).
10. NARRATIVE → PRICE RESPONSE DIVERGENCE (QUEUED): price response per unit sentiment shock;
    "bullish news, market fails to rally" = information. Generalizes event-reaction.
11. H4/D1 SWING FACTORY (QUEUED — next hunt): 2-15 day holding, macro+trend+carry+positioning+
    cross-asset, intentionally different participant/noise/cost structure from M5/H1 sleeves.
12. DYNAMIC EXIT/PYRAMID INTELLIGENCE (PARTIAL-EXISTS): exit_study.json + profit-lock/runner
    architecture exist; add P(next +1R before −0.5R | open winner state) → BANK/HOLD/TRAIL/ADD/
    TIGHTEN/EXIT selection.
13. STOP-THEN-WIN MINER (QUEUED): cluster SL-hit-then-target trades; classify stop distance vs
    entry timing vs spread spike vs liquidity sweep vs vol state vs session; yields adaptive SL /
    wait-for-sweep entry / profit-lock re-entry instead of loosening stops.
14. EDGE-CONFIDENCE → SIZE (QUEUED): posterior buckets (weak→0, modest→0.25×, normal→0.5×,
    strong→1×, exceptional+independent→>1× under portfolio risk); buckets calibrated OOS only.
15. FILTER ROI ATTRIBUTION (QUEUED, standing rule): every AI/filter/regime module reports gross
    added R, trades removed, wrongly-removed winners, DD reduction, incremental E[log W].

## What we will NOT add
- LLM with unrestricted chart authority / freestyle entries.
- A giant network optimized directly against total P&L.
- Raw sentiment alone as a directional predictor.
- Blind copying of posted equity curves.

## Priority (advisor order, adopted)
Wave 1: failure memory → veto alpha → missed-trade alpha → signal grading → strategy-selector
meta-alpha → dynamic position management → inversion miner → H4/D1 swing factory.
Wave 2: model disagreement → social attention velocity → narrative-vs-price divergence →
adaptive sizing → filter ROI.
Crypto-only items are mapped to MT5/all-universe equivalents per standing mandate.