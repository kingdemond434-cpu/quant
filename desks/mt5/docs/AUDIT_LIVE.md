# LIVE IMPLEMENTATION AUDIT — MT5 Desk

Audit date: 2026-08-17 05:35 UTC
Method: every claimed capability checked as CODE (exists) + WIRED (scheduled/launched) + RUNNING (process/report evidence) + MEASURED (artifact with timestamps) + INFLUENCING (feeds research or capital). No claim accepted from docs alone.

## Verdict by capability

| # | Capability | Code | Wired | Running | Measured | Influencing | Status |
|---|-----------|------|-------|---------|----------|-------------|--------|
| 1 | Data: H1 universe + costs | mt5desk/families, data/universe | fetch tasks (MT5-Hunt6 etc.) | parquets present, 22 symbols | universe.json + rv_triangle.json 08-16 21:54 | feeds every hunt | LIVE |
| 2 | Free-data frontier | data/free_data_frontier.json 08-17 00:32 | manual refetch | one pass done | 14,393b | queued sources | PARTIAL (refetch cadence not yet automated) |
| 3 | Hunt pipeline (1-12, 15 universe sweeps) | research/run_hunt*.py | supervisor auto-restarts | hunt12 DONE 05:24:31 (105 survivors, 22 syms) | hunt12.json fresh | survivors into battery/orthogonality | LIVE |
| 4 | hunt13 component decomposition | run_hunt13.py | supervisor | DONE 03:52:17 | hunt13.json | TREND_DAY provenance | LIVE |
| 5 | hunt16 Davidd corpus (14 fams × 2 sides × 4 wins × 2 states) | run_hunt16.py | supervisor auto-restart (proved: crashed 04:20, restarted 04:24, now sweeping) | DONE: 77 survivors, PBO=0.0, median OOS 2.31 | hunt16.json + DONE_hunt16 | candidates into REAL survivors | LIVE |
| 6 | Placebo machinery audit | placebo_test.py (bar-return null, 4-bar blocks) | supervisor auto-restart | fixed 04:53 crash bug; RUNNING (pid 25656) | CLEAN: 0 survivors / 180 cells, max_t_per_rep ~ -31 | placebo_test.json 08-17 04:45 | old SUSPECT verdicts retracted | LIVE |
| 7 | Battery/walk-forward/2x-cost stress | mt5desk/engine, families | in every hunt | hunt results show WF cols | PASS cells recorded | gates every candidate | LIVE |
| 8 | Orthogonality/portfolio/allocation | research/orthogonality.py, portfolio_*.py, allocation.py | manual runs | reports 02:23-02:42 | fresh | sleeves sizing | LIVE |
| 9 | Execution truth (next-bar open, intrabar fills, costs inside) | mt5desk/engine.py | all backtests | code-audited | — | every candidate | LIVE |
| 10 | Live gateway | mt5desk/gateway.py + MT5-Gateway task | task next 05:31 | GATEWAY_PAUSED (by design, Fusion pending) | gateway_state.json | paused until Fusion | PAUSED-OK |
| 11 | Promoter/shadow forward/auto-retire | promoter.py, shadow_forward.py, regime_monitor.py | QuantShadow daily 00:00 | runs nightly | live_ledger.jsonl | sleeves absent (nothing promoted yet) | LIVE-BUT-IDLE |
| 12 | Research supervisor (self-healing) | research/research_supervisor.py | MT5-ResearchSupervisor task (boot+5min) + running instance | PROVED: hunt12 died → auto-restarted → COMPLETED 22 syms | 5 targets: hunt12/16/17, placebo, fragility, qquant_gates, regime_oos, merge (per-target python) | supervisor.log | keeps all hunts alive | LIVE |
| 13 | Hourly cycle | research/hourly_cycle.py | MT5Hourly.cmd in Startup (installed 05:33) | tested once: sync_marker + frontier_inbox written | 08-17 05:33 | frontier + health | LIVE |
| 14 | Hourly VPS sync | scripts/sync_to_vps.ps1 | MT5Sync.cmd in Startup (installed 05:33) | last sync 05:03 manual | VPS commit b55ce661 | both brains one system | LIVE (next auto at login) |
| 15 | Mandate docs (4) + provenance registry | docs/*.md | on VPS desks/mt5/docs (verified) | committed | b55ce661 | governance | LIVE |
| 16 | External intelligence mining | hourly_cycle web pass | hourly | inbox written, empty [] | frontier_inbox.json 05:33 | nothing absorbed this pass | PARTIAL (pipeline live, sources thin) |
| 17 | PBO/CPCV selection-bias audit | pbo_cpcv.py | supervisor | DONE hunt12: PBO=0.0 (best-IS never OOS<=0), median all-tested OOS −0.24 | pbo_cpcv_hunt12.json | survivor trust | LIVE |
| 18 | MARGINAL_ELOGW score fields on candidates | — | — | — | — | — | MISSING (queued) |
| 19 | Fusion broker layer | validate_fusion.py | — | not installed (user tomorrow) | — | blocked | BLOCKED-EXTERNAL |
| 20 | Crisis/drawdown alpha miner | hunt15 (done: 0 AUD-family candidates) | — | hunt15.json 03:40 | — | — | PARTIAL (families exhausted, wider search queued) |
| 21 | QQUANT UNIVERSAL GATES (10) | qquant_gates.py runs the ORIGINAL quant-platform gauntlet libs verbatim (DSR, CSCV-PBO, Hansen SPA, CPCV, WalkForwardEngine, X3 stress, EV, prior, lockbox) | supervisor | RUNNING (trial matrices hunt12=352 + hunt16=345 cells, checkpoint-cached) | QQUANT_GATES.json pending | REAL3 = all 10 gates | BUILDING |
| 22 | DSR + fragility + correlation audit (182) | fragility.py (Acklam DSR, worst-decile, p99, max-consec-loss, pairwise corr) | supervisor | RUNNING (CPU ~4500s) | REAL_SURVIVORS.json pending (REAL2) | REAL2 gate | BUILDING |
| 23 | Latent regime OOS validation | regime_discovery.py reports cluster-conditional exp on OOS 30% fold only | supervisor | DONE: regime split REPLICATES OOS on all 4 syms (XAUUSD c2 +0.893R t=5.05; AUDCAD c2/c3 positive; EURUSD control same) | latent_regimes.json 12:1x | regime permission filter | LIVE |
| 24 | hunt17 H4/D1 swing factory (5 fams, LONG+SHORT, 2 params, 22 syms) | run_hunt17.py (d1_trend_pullback, d1_swing_break, h4_momentum, h4_vol_break, d1_inside) | supervisor | DONE: 0/440 survivors (honest null) | hunt17.json + DONE_hunt17 | mechanism bucket closed | LIVE |
| 25 | RFT corpus hunt19 (Aroon+candle, Retrack, RMI+inside, S/R reject, candle break, fail-seq) | run_hunt19.py + docs/RFT_LINEAGE.md (RFT_001-081) | supervisor | RUNNING (pid 10052) | hunt19_partial.json | Tier S RFT mechanisms | BUILDING |
| 26 | SALEH corpus hunt20 (squeeze, EMA bank/runner, Turtle, KAMA, Alligator ablation, pairs RV) | run_hunt20.py + docs/SALEH_LINEAGE.md (SALEH_001-145); engine bank_frac/bank_protect/runner_trail; docs/QUANT_AGENT_PROTOCOL.md | supervisor | RUNNING (pid 18256) | hunt20_partial.json | Tier S Saleh mechanisms | BUILDING |
| 27 | SIGNAL_INFORMATION_GATE (Jesse rule-significance, strengthened) | signal_gate.py (horizons 1/2/5/10, LONG/SHORT split, block-bootstrap null) | manual post-hunt | not yet run | pending | every future strategy pre-screen | BUILDING |
| 28 | Cross-market residual desk hunt21 (XAU factor resid/lag + 6 triangles) | run_hunt21.py + docs/NEWS_LINEAGE.md; fixed: log-LEVELS bug → log returns; lag condition = |y|<=0.3|p| | supervisor | DONE: 15 cells swept, 0+ survivors pending universal gate | hunt21.json + DONE_hunt21 | cross-asset lead/lag + correlation/residuals coverage | BUILDING |
| 29 | Event-hour effects hunt22 (usmacro/us1400 drift+rev; H4 hours 12/16) | run_hunt22.py; fixed: 18/19h windows don't exist on H4 → hour 16 bar contains 14:00 ET | supervisor | RUNNING (pid 15956) | hunt22_partial.json | macro reaction coverage | BUILDING |
| 30 | News capture desk (NEWS_001-036, latency taxonomy, no-MNPI boundary) | news_desk.py + docs/NEWS_LINEAGE.md | supervisor | RUNNING idle (pid 17584; schedule EMPTY until licensed source) | — | instant public-news reaction | IDLE-BY-DESIGN |
| 31 | UNIVERSAL 10-GATE survivor desk (THE only survivor gate; battery retired) | research/universal_gate.py (qquant libs verbatim; hunt17/19/20/21/22 + hunt18_*; UNIVERSAL_CELLS; PARAMS patch) | supervisor (venv python) | RUNNING waiting on DONE_qquant_gates (pid 12656) | universal_gates_*.json + UNIVERSAL_SURVIVORS.json pending | REAL4 = all new hunts verdicts | WAITING |
| 32 | Meta desk — 15 architecture items (state JSONs + DONE_meta) | research/meta_desk.py; fixed tprint flush bug; venv python | supervisor (venv) | RUNNING waiting on DONE_merge + DONE_universal_* (pid 22592) | state_*.json + DONE_meta pending | allocation/decay/discovery decisions | WAITING |
| 33 | Architecture moratorium + conversion ladder | docs/DESK_ARCHITECTURE.md + QUANT_AGENT_PROTOCOL.md v2 (VALIDATION_SCHEMA_VERSION=2) | binding protocol rule 11 | in force 08-17 | protocol v2 | no new architecture; convert inventory | LIVE |

## Proof of self-healing (the key fix this audit verified)
- 04:20-05:07: hunt12 + hunt16 + placebo died silently (hunt16: pandas 2.x `Index.between` removed → AttributeError; placebo: null-market length/broadcast bugs → ValueError; hunt12: died once on XAUUSD workload).
- 05:24: supervisor respawned hunt12 from partial → it COMPLETED all 22 symbols (DONE_hunt12 written 05:24:31).
- Supervisor now runs as a persistent process + scheduled task (boot + 5-min tick, single-instance guarded); completion markers prevent re-running finished hunts; 30-min quarantine prevents restart storms; every respawn logs to logs/supervisor.log and stderr to logs/<name>_super.log.

## Root causes fixed this session
1. run_hunt16.py: 14× `h1.index.hour.between(...)` → pandas 2.x AttributeError → replaced with range comparisons.
2. placebo_test.py null_market: synthetic path shorter than index (length mismatch) and range array misaligned (broadcast error) → exact-length reconstruction + tail padding.
3. Research processes had no restart path → research_supervisor.py (+ scheduled task + Startup installation of MT5Hourly/MT5Sync).
4. No auto-sync/hourly cycle running → installed into Startup; cycle tested.

## Honest open items (updated 08-17 13:45 UTC)
- Fragility (REAL2) restarted 13:32 (original instance died ~13:32; new run already at correlation phase, CPU climbing), qquant 10-gate (REAL3, 80+/352), merge, universal, meta_desk: all supervised; verdicts pending on completion markers.
- hunt19 DONE 13:20 (16 battery-pass cells → universal gate); hunt21 DONE 13:31 (15 cells); hunt22 RUNNING; news_desk idle by design (no licensed feed).
- SIGNAL_INFORMATION_GATE: run on hunt19/hunt20 when they complete; CANDLE_MONTE_CARLO, PERIOD_STABILITY_MATRIX, PARAMETER_PLATEAU queued (SALEH_LINEAGE.md infra steals).
- Cross-asset anchors (SALEH_017: DXY/yields/commodities → Gold, JPY crosses, AUD/CAD) blocked on external series (queued).
- Fusion go-live remains blocked on user install + EUR300 deposit (tomorrow).
- MARGINAL_ELOGW score fields and full 182-population orthogonality sleeve list: next queue after merge.
- VPS sync pending (last verified commit f1943219; force sync after this audit).
## Audit row 34 (08-17 16:30 UTC)
- qquant_gates fully parallel (8 workers): 697 cell series DONE (1150s), program-level PBO+SPA running; old serial path (332/18548) killed; cache removed.
- hunt23 rerun DONE: 8 cells (XAUUSD gold_dxy_resid/gold_yield_lag, AUDCAD cad_oil_lag, USDCAD usdcad_oil_lag; jpy_risk_lag 28/47 n<60 skipped). TZ bug fixed (anchor naive vs UTC resample) - lag families now fire.
- Fragility (REAL2) SKIPPED per user directive (16:2x) - universal gate covers DSR/fragility equivalence; DONE_fragility marked skipped.
- options_desk LIVE: Deribit BTC/ETH surfaces via instrument_name parse; archive 2 rows (16:01).
- macro_desk LIVE: FRED states + ALFRED PIT lake + cross_asset_anchors.pkl (4232x11) each cycle.
- crowding_miner LIVE: crowding_state.json (first cycle: gh_stars empty - GitHub unauth search degraded, LOW publicity).
- news_desk: poll_official_rss() added (4 clocks, dedupe, deep lane).
