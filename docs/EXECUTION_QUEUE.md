# EXECUTION QUEUE — the ranked, unbuilt remainder (opened 2026-07-30)

Principal order: *"do every single not-done not-maxxed thing, max everything."* This file is that
order made deterministic, so it survives session boundaries and is worked in RANK ORDER by the next
cycle, the weekly GAP-MAX sweep, or any fresh session. **Nothing here may be silently dropped: each
item exits as implemented (with commit) / rejected (with reason) / scheduled (with date), per §41.**

## THE MEASUREMENT THAT SETS THE RANKING

`libs/self_improvement/dormancy.py`, first run 2026-07-30:
**171 dormant capabilities / 16,645 paid-for unused lines** across 239 modules + 274 scripts.

That number changes the priority order and must not be forgotten while working this queue: the
desk's demonstrated failure mode is *building capability faster than it wires it*. Authoring
subsystem #172 while 171 sit disconnected is negative-ROI by the desk's own arithmetic (L1.24
activity-is-not-output, L2.9 activate-before-build). **So ACTIVATION outranks AUTHORING here, and
any new build in this queue must ship wired + scheduled + evidenced or it is not done.**

---

## RANK 1 — DISPOSITION THE DORMANCY REPORT (activation, not authoring)

The highest-EV work available, and it needs no new design.

    python scripts/run_intelligence_cycle.py --json | python -c "import json,sys; \
      d=json.load(sys.stdin); r=[c for c in d['capabilities'] if c['capability']=='dormancy_hunter'][0]; \
      [print(x['lines'], x['path']) for x in r['report']['dormant'][:40]]"

For each of the top 40 by size, take exactly one L2.9 exit and record it:
- **ACTIVATE** — wire it into a live caller or schedule it (preferred; this is where the value is)
- **MERGE** — fold into an existing reachable module (duplicate capability)
- **RETIRE** — with a written mechanism-of-death, into the graveyard
- **UNLOCK-CONDITION** — legitimately waiting on evidence (e.g. needs ≥1 validated alpha); record
  the trigger so it auto-activates rather than being rediscovered. **This is a real exit, not an
  excuse** — several genuinely are in this state and saying so is honest; but it may never be the
  default, and a count of how many took this exit is reported each cycle.

Acceptance: dormant count falls, and every top-40 entry has a recorded disposition.

## RANK 2 — CONSTITUTION → ENFORCEMENT MATRIX (machine-readable)

Named the single biggest remaining gap by the strategic review, and it is the fence that would have
caught today's finds automatically.

Build `scripts/build_enforcement_matrix.py` emitting `data/enforcement_matrix.json`:

    principle_id -> requirement -> subsystem -> code_path -> scheduler -> runtime_metric
                 -> test -> dashboard -> evidence_artifact -> last_verified

Sources already on disk: `docs/CONSTITUTION.md` (L1.x/L2.x/L4 ids), `scripts/max_audit.py` (~40
fences), `ops/crontab.manifest` (scheduling), `tests/` (test coverage), `web/*.json` (evidence).
**Two failure directions, both required:** a principle with no enforcement is an engineering gap;
an enforcement with no principle is unjustified complexity. Fail the check on either.
Wire into `max_audit` so it fires; schedule daily in the manifest.

Acceptance: every L1/L2 principle has a row; unenforced principles are listed and rowed on the
register; the check runs on a schedule.

## RANK 3 — GPT STRATEGIC DIRECTOR, as a runtime role not a document

Principal was explicit: *"not as another dormant doctrine document."* So it ships as a **prompt +
input dossier + output contract inside the intelligence cycle**, not as prose in the constitution.
- INPUT: dormancy report, gate histogram, reality-gap report, register rank, DESK_BRIEF, execution
  intel, moat audit — the artifacts that already exist.
- OUTPUT: ranked recommendations, each with the measurable bottleneck it removes, expected impact,
  opportunity cost, and success metric; written to the recommendation ledger so §41 forces a
  disposition. **Priority rule encoded: find unused capability BEFORE inventing new capability.**
- Blocked on: OpenRouter credit (same blocker as the panel). Must be activation-ready so it fires
  the moment credit lands — no redesign.

## RANK 4 — DATA ASSET REGISTRY

`data/data_assets.json` + `scripts/build_data_registry.py`: one row per dataset — id, source,
collector, span (first→last), breadth, update cadence, quality/DQS, alpha contribution,
dependencies, maintenance cost, replication difficulty, moat score, last validation.
Register row #77 already proved the need: the inventory reported ROW COUNTS AS SPANS and omitted
the desk's best panel (267 symbols from 2019-09), so organs were choosing what to test from a
misleading map. Feed `moat_audit.py` (which exists and is now scheduled).

## RANK 5 — FUSION SEARCH ENGINE (distinct from the existing `fusion_engine.py`)

The existing module transforms; it does not SEARCH. Build the combinatorial search: enumerate
dataset triples from the registry (rank 4 is its prerequisite), generate candidate
representations, screen through `libs.research.axis_screen` + the tiered pre-filter, log EVERY
cell as a DSR-counted trial, and record survivors in the knowledge graph.
**The multiplicity trap to respect:** combinatorial search is a trial-count explosion, and the
desk's own law says breadth is EARNED per axis after a single-axis screen shows signal. So the
search must be mechanism-prior-gated, not exhaustive-by-default.

## RANK 6 — PROPRIETARY LABEL FACTORY

Generate and validate event labels (liquidity stress, forced deleveraging, accumulation window,
regime transition) from the bronze panel; version them; treat each as a research asset with its own
validation record. Prerequisite: rank 4 (registry) so labels have lineage.

## RANK 7 — INBOUND DEPLOY PATH (found 2026-07-30, no row yet)

`git_snapshot.py` pushes VPS→GitHub; **nothing pulls GitHub→VPS.** So merging to master deploys
NOTHING and every change needs a manual SSH. Build `deploy/pull_deploy.sh`: fetch, run the CI gate,
refuse on red, restart only what changed, log an evidence line — then cron it. This converts
"principal must SSH for every change" into "merge is deploy" and is a genuine autonomy multiplier.

---

## BOX-SIDE TRUTHS STILL UNVERIFIED (cannot be closed from a sandbox)

Recorded so they are not mistaken for done:
1. **Miner credentials** — `check_miner_runway.py` returned "No such file" on the VPS because the
   box was on an older checkout. Master now carries it. Re-run after the box pulls.
2. **`revalidate_clocks` / `fusion_engine`** read NO-INPUT here only because Binance is geo-blocked
   from this sandbox (HTTP 451). They should read ACTIVE on the box.
3. **Live crontab drift** — the 23-entry manifest is a RECONSTRUCTION; the live box was documented
   at ~20-22 lines. `check_scheduler_manifest.py --report-only` prints the true drift.
   ⚠️ Do not run `deploy/reconstitute_cron.sh` before reviewing that drift — the box has unfenced
   cron lines and would double-schedule the recorders.
4. **Binance USDC multi-asset margin** ($209 → $5,767 per the other session) — needs venue keys;
   unverified from here.

## RANK 1 PROGRESS (2026-07-30, this session) — 14/40 RETIRED, 32/40 EVIDENCED-BLOCKED, 7/40 ACTIVATE-PENDING

**RETIRED (14, committed `3be2e3e`):** the entire `libs/discovery/` Alpha Discovery Factory
cluster — see `docs/graveyard.md` § CODE / CAPABILITY RETIREMENTS for the mechanism-of-death.
Dormant count fell 171 → 158 (16,645 → 15,150 lines), confirming the item actually closed rather
than just moving.

**THE NEXT 32 (all `scripts/*.py`) — actually executed here, not just grepped, to get a real
disposition instead of trusting the report blind.** Every one hit a real, reproducible wall in
THIS sandbox — missing bronze data lake files, missing `data/secrets/*.json`, or outbound network
403/Tunnel-failed to Binance/exchange APIs. That is a box-dependency, not dead code, and none of
the 32 crashed on a code bug. **Disposition: UNLOCK-CONDITION**, trigger = "run on the live VPS
box, which has the data lake, the venue/API secrets, and unrestricted egress" — record here so
the next session with box access converts these to ACTIVATE/MERGE/RETIRE with real output instead
of re-discovering the same blocker:

| script | blocked on |
|---|---|
| `screen_idle_axes.py`, `screen_fx_debasement.py`, `screen_etf_flows.py` | no crypto/FX bronze lake locally (`pandas.concat`: no objects) |
| `screen_mining.py` | `data/lake/bronze/mining/hash-rate.csv` missing |
| `screen_wikipedia.py` | `data/lake/bronze/wikipedia/*.json` missing |
| `screen_exchange_netflow.py` | `data/coinmetrics_flows.jsonl` missing (NB: this axis is already KILLED per graveyard — script's remaining value is nil, borderline RETIRE, not re-run) |
| `screen_fred_macro_axis.py` | `data/secrets/fred.json` missing |
| `build_axis_screen_reports.py`, `finalize_axis_screens.py` | depend on `reports/axis_screens/*.json` raw trial logs that were never generated here |
| `run_kama_squeeze_backtest.py`, `run_carry_crowding.py`, `hl_flow_alpha.py`, `capacity_simulator.py` | outbound HTTPS to Binance/exchange APIs returns 403 (proxy/geo-block) in this sandbox |
| `run_xsec_funding.py` | needs `ingest_crypto.py --universe all` run first (>=12 perps) |
| `run_stranded_recovery.py` | needs spot testnet API keys |
| `run_venue_reconcile.py`, `reconcile_venue.py` | venue credentials unreadable / `data/deadman_state.json` missing |
| `hold_optimizer.py`, `carry_viability.py` | `data/cashcarry_trades.json` / `data/cost_model.json` missing |
| `compute_performance.py` | "no lake data; run `scripts/ingest_history.py` first" |
| `collector_author.py`, `meta_architect.py`, `llm_code_auditor.py` | "no panel keys" / OpenRouter 402 (llm_code_auditor.py's own docstring already says "WRITTEN BUT NEVER EXECUTED" — same OpenRouter credit blocker as RANK 3) |
| `run_autodiscovery.py` | needs a live MetaTrader5 terminal connection (box-only, on-demand by design) |
| `run_cot_screen.py`, `screen_oi_ls_axes.py`, `iros_batch.py` | ran to completion but logged **0 trials** — code path is sound, underlying panel data absent here |
| `certify_gauntlet.py`, `run_trend_gauntlet.py`, `run_onchain_history_backtest.py`, `research_alpha_optimizer.py`, `reconstruct_kaiko_reference_rate.py` | CLI tools that ran cleanly to their argument parser / entry point here; genuinely on-demand-by-design (paid CSV drop, specific research campaign), not scheduler candidates — worth adding to `dormancy.py`'s `_ON_DEMAND` allowlist once someone confirms they're invoked this way in practice, rather than re-flagging them as dormant every cycle |

**THE 7 `libs/` MODULES (real infrastructure, no wired caller found even outside the strict
dotted-path scope — verified by hand, not just the tool) — disposition: ACTIVATE, with the actual
integration point identified so this isn't a vague "wire it in somewhere":**

- `libs/execution/algos.py` (TWAP/POV/Implementation-Shortfall child-order schedules) — its own
  docstring says *"the `ExecutionEngine` submits the slices"*, but `libs/execution/engine.py`
  **does not import it**. CORRECTED 2026-07-30 while building RANK 7: `libs/execution/__init__.py:10`
  *does* re-export it, so the module loads and is not literally unreferenced — but no consumer ever
  calls `ExecutionScheduler`. That is worse than plain dormancy, not better: a package-level
  re-export makes it *look* wired to exactly the grep a reviewer would run. The schedules were
  built for a consumer that was never connected to them.
- `libs/backtest/engine.py` (`BacktestEngine`, the actual event-driven engine) — zero callers
  outside its own package and tests; even `cross_engine.py` only imports it for verification, not
  to run a real backtest. Nothing in `scripts/` or `app/` runs a backtest through it.
- `libs/backtest/cross_engine.py` — depends on the above; only reachable from `max_audit.py`'s own
  text-inspection fence and tests. Should run automatically whenever a strategy backtest is
  certified (`certify_gauntlet.py` is the natural caller), not be available-but-unused.
- `libs/validation/gate_calibration.py` (rejection-shadow + backfill-safety audits) — only called
  from `libs/validation/rejection_shadow.py` (same package) and its own test. Should run on the
  weekly gate-audit cadence alongside the other validation-stack checks.
- `libs/store/snapshots.py` (database/dataset snapshot-and-restore) — only referenced from its own
  package `__init__` and test. Should be called wherever a candidate is promoted, to bind the
  promotion to an exact, restorable data version (Stage 3's own stated purpose for it).
- `libs/self_improvement/controller.py` (Stage 13 improvement controller) — zero external callers;
  should be scheduled inside `run_intelligence_cycle.py` so it actually produces and journals
  `ImprovementPlan` recommendations instead of sitting fully built and inert.
- `libs/features/validation.py` (leakage/parity checks) — only called by `libs/features/registry.py`
  (same package), which **itself** has zero external callers either. The whole `libs/features`
  registry path may be shadowed by the separately-wired `scripts/leakage_detector.py` contract
  (used by `daily_research_cycle.py`, `stage_a_executor.py`) — worth a MERGE review, not a
  reflexive ACTIVATE, since two leakage-detection paths existing side by side is exactly the kind
  of duplication RANK 1 exists to catch.

None of these seven were wired in this pass: money-path/execution and backtest-engine code
deserves review before connecting it to anything live, and that review is bigger than a queue
item. Recorded here, evidenced, so the next pass starts from a concrete integration point instead
of a bare dormancy line.

## STANDING RULE FOR WHOEVER WORKS THIS

Work in rank order. Ship each item wired + scheduled + evidenced, or do not count it. Re-run the
dormancy hunter after every item: **if the dormant count went UP, the item was not finished.**
