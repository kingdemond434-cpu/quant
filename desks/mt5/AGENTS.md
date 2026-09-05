# Agent instructions (binding)

1. Read `docs/UNIVERSAL_PROMOTION_PROTOCOL.md` before doing anything.
   It is binding on every session: fail closed, absence is never permission,
   and the universal 10-gate pass is the single path to capital.
2. Universal gate is the only survivor gate. Battery numbers are descriptive.
3. Survivors proceed: universal 10-gate → signal gate (INFORMED required,
   else excluded) → allocation → deployment. `reports/SURVIVORS_LEDGER.json`
   is the ledger; count `n` and act on every new survivor.
4. Architecture is frozen (protocol rule 11): new ideas go to
   `data/research_queue.json`, not into the codebase ad hoc.
5. Research pipeline ticks hourly (research_loop); desks are perpetual;
   supervisor respawns anything that dies (logs in local temp dir,
   NOT OneDrive).
6. Hold files `data/HOLD_<target>` pause a supervisor target. Lifting a hold
   resumes it. Do not fake markers.
7. VPS (quant@$QUANT_VPS -- host kept out of the public tree, desks/mt5) is the always-on research authority
   when this box is off; changes must be synced (scripts/sync_to_vps.ps1)
   and pushed so every brain sees them.
## Growth governance (principal 2026-09-04, binding; fenced by scripts/check_growth_governance.py)

- Every risk reduction mechanism must prove that it increases robust forward E[log W].
- Every strong opportunity must be allowed to increase capital above normal when the evidence supports it.

Timid is not risk-aware. The 20% utilisation floor is flat and deployed 24/7; growth is free
above it to the 30% ceiling; the resolved heat is filled, never reported short. A new veto, cap,
shrinkage or gate is not admissible without a rail entry in `libs/portfolio/rails.py` and its
measurement in `research/missed_growth.py`; a new capital modifier must be two-sided and
registered in `libs/portfolio/capital_modifiers.py`. See `docs/GROWTH_GOVERNANCE.md`.

## Deep-forest story mining (2026-09-04)

The Chinese deep web is mined as MECHANISM FUEL, not as a curiosity: `research/deep_forest_miner.py`
works the grounds in `data/deep_forest_sources.json` (七禾网/期货日报 interviews and competition records,
聚宽/优矿/米筐/BigQuant communities, 知乎/CSDN/雪球 through search-engine `site:` routes, Gitee, Bilibili
transcripts, 微信 via 搜狗, the forums) and every verbatim claim -- a sentence naming a quantity, a direction
and a horizon, in Chinese or English (`libs/research/mechanism_claims.py`) -- becomes a deepening task of
kind `story_mechanism` with the instrument mapped to its MT5 analogue (沪金 -> XAUUSD; no-analogue futures
carry a mechanism-class transfer note). The worker seat reverse-engineers an exact recipe or rejects;
nothing bypasses the compiler or the gates; a story's own performance numbers are never evidence. URLs found
feed the world crawler's frontier, and the crawler itself now keeps such claims (rows of kind `story`). The
repo miner reads Gitee beside GitHub with the same grammar. Crypto-exchange grounds remain forbidden and
the fence is counted on every report (`counts.dropped_venue`).

## Promotion is automatic and immediate (principal 2026-09-04)

Every forward clock -- `shadow_forward` (main lane), `qquant_shadow`, `scalp_shadow` -- feeds
`research/promoter.py` on the same shadow cycle. A PROMOTION CANDIDATE whose exact spec is in the
ten-gate authority set is written to `data/sleeves.json` as LIVE on that run; the gateway trades
it on its next pass. Scalp sleeves carry their exact recipe (timeframe, family, session, ATR
geometry) with `exec="scalp_market"` and are executed by `mt5desk/scalp_exec.py` through
`gateway.run_scalp_sleeves()` -- replay-faithful, one stated deviation (the stop's ATR is the last
closed bar's). The old gold-challenger wait/kill against the armed window is gone: the comparison
is recorded on the sleeve row (`vs_armed`) and capital is the allocator's ΔE[log W] decision.
Retirement stays automatic and kills the row in whichever lane owns it.
