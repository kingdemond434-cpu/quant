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
| 5 | hunt16 Davidd corpus (14 fams × 2 sides × 4 wins × 2 states) | run_hunt16.py | supervisor auto-restart (proved: crashed 04:20, restarted 04:24, now sweeping) | RUNNING, partial 05:30:49 | hunt16_partial.json | candidates entering battery | LIVE |
| 6 | Placebo machinery audit | placebo_test.py (bar-return null, 4-bar blocks) | supervisor auto-restart | fixed 04:53 crash bug; RUNNING (pid 25656) | report pending | audit not yet re-issued | PARTIAL (verdict pending, old report superseded) |
| 7 | Battery/walk-forward/2x-cost stress | mt5desk/engine, families | in every hunt | hunt results show WF cols | PASS cells recorded | gates every candidate | LIVE |
| 8 | Orthogonality/portfolio/allocation | research/orthogonality.py, portfolio_*.py, allocation.py | manual runs | reports 02:23-02:42 | fresh | sleeves sizing | LIVE |
| 9 | Execution truth (next-bar open, intrabar fills, costs inside) | mt5desk/engine.py | all backtests | code-audited | — | every candidate | LIVE |
| 10 | Live gateway | mt5desk/gateway.py + MT5-Gateway task | task next 05:31 | GATEWAY_PAUSED (by design, Fusion pending) | gateway_state.json | paused until Fusion | PAUSED-OK |
| 11 | Promoter/shadow forward/auto-retire | promoter.py, shadow_forward.py, regime_monitor.py | QuantShadow daily 00:00 | runs nightly | live_ledger.jsonl | sleeves absent (nothing promoted yet) | LIVE-BUT-IDLE |
| 12 | Research supervisor (self-healing) | research/research_supervisor.py | MT5-ResearchSupervisor task (boot+5min) + running instance | PROVED: hunt12 died → auto-restarted → COMPLETED 22 syms | supervisor.log | keeps all hunts alive | LIVE |
| 13 | Hourly cycle | research/hourly_cycle.py | MT5Hourly.cmd in Startup (installed 05:33) | tested once: sync_marker + frontier_inbox written | 08-17 05:33 | frontier + health | LIVE |
| 14 | Hourly VPS sync | scripts/sync_to_vps.ps1 | MT5Sync.cmd in Startup (installed 05:33) | last sync 05:03 manual | VPS commit b55ce661 | both brains one system | LIVE (next auto at login) |
| 15 | Mandate docs (4) + provenance registry | docs/*.md | on VPS desks/mt5/docs (verified) | committed | b55ce661 | governance | LIVE |
| 16 | External intelligence mining | hourly_cycle web pass | hourly | inbox written, empty [] | frontier_inbox.json 05:33 | nothing absorbed this pass | PARTIAL (pipeline live, sources thin) |
| 17 | PBO/CPCV selection-bias audit | pbo_cpcv.py | supervisor | DONE hunt12: PBO=0.0 (best-IS never OOS<=0), median all-tested OOS −0.24 | pbo_cpcv_hunt12.json | survivor trust | LIVE |
| 18 | MARGINAL_ELOGW score fields on candidates | — | — | — | — | — | MISSING (queued) |
| 19 | Fusion broker layer | validate_fusion.py | — | not installed (user tomorrow) | — | blocked | BLOCKED-EXTERNAL |
| 20 | Crisis/drawdown alpha miner | hunt15 (done: 0 AUD-family candidates) | — | hunt15.json 03:40 | — | — | PARTIAL (families exhausted, wider search queued) |

## Proof of self-healing (the key fix this audit verified)
- 04:20-05:07: hunt12 + hunt16 + placebo died silently (hunt16: pandas 2.x `Index.between` removed → AttributeError; placebo: null-market length/broadcast bugs → ValueError; hunt12: died once on XAUUSD workload).
- 05:24: supervisor respawned hunt12 from partial → it COMPLETED all 22 symbols (DONE_hunt12 written 05:24:31).
- Supervisor now runs as a persistent process + scheduled task (boot + 5-min tick, single-instance guarded); completion markers prevent re-running finished hunts; 30-min quarantine prevents restart storms; every respawn logs to logs/supervisor.log and stderr to logs/<name>_super.log.

## Root causes fixed this session
1. run_hunt16.py: 14× `h1.index.hour.between(...)` → pandas 2.x AttributeError → replaced with range comparisons.
2. placebo_test.py null_market: synthetic path shorter than index (length mismatch) and range array misaligned (broadcast error) → exact-length reconstruction + tail padding.
3. Research processes had no restart path → research_supervisor.py (+ scheduled task + Startup installation of MT5Hourly/MT5Sync).
4. No auto-sync/hourly cycle running → installed into Startup; cycle tested.

## Honest open items
- Placebo verdict on the corrected null: RUNNING, expect ~20-40 min; old placebo_test.json (03:53, day-permutation null) is SUPERSEDED and must not be quoted.
- frontier_inbox.json empty this pass — mining needs more source diversity (Reddit only so far).
- PBO/CPCV, MARGINAL_ELOGW fields, cross-engine truth: still to be built (next queue).
- Live trading remains paused (GATEWAY_PAUSED) until Fusion install + €300 deposit (user, tomorrow).