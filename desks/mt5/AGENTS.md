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

## CANONICAL LIVE BOX (2026-08-22, standing until superseded here)

**Contabo (`C:\opt\quant`, Windows) is the sole canonical live execution box.**
It runs MT5-Gateway/MT5-Hourly/MT5-Shadow/MT5-ShadowSync/MT5-ResearchSupervisor
against the FUSION LIVE account (server `FusionMarkets-Live`). Its
`reports/shadow/shadow_health.json` (committed to git every 15 min by MT5-ShadowSync running
scripts/sync_shadow_to_git.ps1, and pulled by the VPS every 2 min for the dashboard) is the ONE
authoritative shadow-evidence state -- it also carries `gateway_armed` and
`promoted_live_sleeves` so live-arm state is visible without a shell on the box.

**The principal's laptop (`C:\Users\dell\mt5-research`) is RETIRED, not idle.**
Its MT5-*, QuantMT5Frontier and MarkerTest scheduled tasks are disabled ON
PURPOSE -- that collector reads a VANTAGE account (`VantageMarkets-Live 14`),
which is why its own `promotion_authority` correctly reads `false`
(`"fusion" in server.casefold()` fails for Vantage; that is the safety check
working, not a defect to fix). **DO NOT RE-ENABLE IT** to "restore Fusion bars" or "fix"
`promotion_authority=false`. If a brain cannot reach Contabo directly that is a REACHABILITY
problem to solve on its own terms, never a reason to re-enable the laptop as a stand-in.

Any brain finding this note stale (a new box, the laptop un-retired on purpose, Contabo
decommissioned) should update this section in the same commit that changes the topology.

## VERIFYING CONTABO WITHOUT A SHELL ON IT

**THE SUPPORTED PATH: read the git-committed shadow state.** MT5-ShadowSync commits and pushes
`desks/mt5/reports/shadow/shadow_health.json` (plus `data/gateway_state.json`,
`data/sleeves.json`, `data/regime_state.json`) to the box's branch every 15 minutes, and the
VPS's `run_external_pipeline.sh` reaches the box over the `contabo-mt5` ssh alias. If the
committed state looks stale (older than ~20 minutes), the finding is "the sync task may be
down on Contabo," not "Contabo may be down" -- different problems, different fixes.

**IF DIRECT SSH TO CONTABO IS GENUINELY NEEDED** and it presents a host key that doesn't match
a cached one: DO NOT accept-and-continue, and DO NOT disable host-key checking. Verify the
fingerprint out-of-band from the provider's VNC/KVM console first
(`ssh-keygen -lf "C:\ProgramData\ssh\ssh_host_ed25519_key.pub"`). Match -> remove ONLY that
known_hosts entry and reconnect. Mismatch -> stop, treat as a possible compromise and involve
the principal before doing anything else.

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

## Every miner hourly, minimum (principal 2026-09-05)

"All miners etc should be hourly minimum or 24/7 -- for maximum datasets, moats and edge
discoveries, for max geometric growth potential." `research/hourly_discovery.py` runs every world
miner, data organ and proposer sweep once an hour on the VPS (`ops/quant-hourly-discovery.timer`,
:35), each in its own subprocess on a bandit-weighted budget behind the memory guard; an organ
that overruns is killed at its budget, one that cannot get memory is DEFERRED with the reason,
one that raises is recorded -- never silently skipped. The :05 pipeline compiles what the pass
donated into gauntlet cells; the daily cycle keeps its full-budget runs. Per-organ status:
`reports/HOURLY_DISCOVERY.json`. A new miner or proposer is added to `hourly_discovery.ORGANS`
in the same commit that creates it, or it is a daily organ by accident.

## Promotion is automatic and immediate (principal 2026-09-04)

Every forward clock -- `shadow_forward` (main lane), `qquant_shadow`, `scalp_shadow` -- feeds
`research/promoter.py` on the same shadow cycle. **Universal rule (principal 2026-09-05, "make it
universal"):** a forward clock that reads PROMOTION CANDIDATE is the promotion authority for its
own sleeve, in every lane. The clock exists only because a ten-gate certificate enrolled it, so
the promoter does not re-ask the authority set: a spec whose exact tuple has drifted from the
authority set is recorded on the row as `certificate_drift` and promoted anyway, never blocked.
The two things that DO refuse are named on the row: a fresh COST_REGRADE_FAIL from
`scripts/recertify_canon.py` (`BLOCKED_COST_REGRADE`, the certificate no longer passes its own
gates at today's costs) and `executor_gap` (`mt5desk/executables.py`: the family's constructor
resolves but the gateway cannot trade that population yet -- a wiring defect to fix, never a LIVE
row the book would hold as air). Scalp sleeves carry their exact recipe (timeframe, family,
session, ATR geometry) with `exec="scalp_market"` and are executed by `mt5desk/scalp_exec.py`
through `gateway.run_scalp_sleeves()` -- replay-faithful, one stated deviation (the stop's ATR is
the last closed bar's); the scalp lane admits any clock row, not only `authorized_specs`. Other
families promote as `exec="family_market"` rows. The old gold-challenger wait/kill against the
armed window is gone: the comparison is recorded on the sleeve row (`vs_armed`) and capital is
the allocator's ΔE[log W] decision. Retirement stays automatic and kills the row in whichever
lane owns it.

What made certificates and forward clocks vanish before, and what now stops each: (1) the box ran
code the VPS never shipped -- every box-run module is now on the drift healer's list and the live
branch is reconciled into `desk-sync-clean` after every merge; (2) the VPS pull clobbered the
canon -- canon and clocks are pulled newer-wins, never overwritten by a fetch; (3) a stale sleeve
registry killed clocks it could not name -- the registry is rebuilt before the kill; (4) the scalp
lane quarantined every clock not in a hand-typed list -- gone, above; (5) a fetch with no bars
dropped a certified spec silently -- it is now a `BLOCKED_NO_BARS` row with `last_error`, and the
fence prints it as CERTIFIED-BLOCKED. A clock or certificate that disappears without one of those
rows is a bug, not a policy.

## The capital brain has a clock (principal 2026-09-05, "that is goal")

The end state: every minute, rebuild the state vector X_t from whatever is fresh, condition each
sleeve's posterior (μ, σ, cost, tail | X_t), solve h* = argmax E[log(1 + h·R − C(h)) | X_t]
inside the 20–30% heat band, and execute only when ΔE[log W] clears turnover + slippage + the
uncertainty buffer. The chain is Global Forest → PIT data hub → features/mechanisms → gauntlet →
admitted conditional relationships → live state engine → allocator; the crawler never touches
capital directly. `research/pf_allocator.py` was that solver and ran on nobody's schedule (the
gateway fails closed on a book older than an hour, so the derived formula sized every position).
It now runs from the research supervisor's `PERIODIC` clock: fast every 5 min (re-solve on the
cached worlds), normal every 15 min (rebuild evidence and the no-trade verdict), heavy hourly
(resample worlds, re-measure the growth curve); one allocator process at a time, the most overdue
mode wins, a heavier pass resets the lighter clocks, `data/HOLD_pf_allocator` pauses it. The
gateway reads the newest book every minute and the no-trade filter -- not the clock -- decides
whether to trade toward it. Data cadence is truthful: a feature carries the `available_time` of
its source, and a minute solve over hourly data is a minute solve over the same hour.
