# Autonomous 24/7 Research Platform — Operations

Continuous, self-healing research with **zero manual intervention**. Reuses the existing research/
discovery/validation/audit logic unchanged; adds durable orchestration around it.

## Loop
```
Research Memory → Campaign Generator → [queue] → Worker → Discovery → Validation → Audit
   → Research Ledger → (refill) → … forever
```

## Components

| Piece | File | Role |
|---|---|---|
| **Campaign queue** | `libs/ops/campaign_queue.py` | durable, lease-based, dedup'd work queue (SQLite WAL) |
| **Worker registry** | `libs/ops/workers.py` | heartbeats → dead-worker detection |
| **Worker** | `libs/ops/research_daemon.py` (`ResearchWorker`) + `scripts/run_worker.py` | leases a campaign, runs `AutoDiscoveryLab.cycle`, completes/fails — crash-isolated |
| **Supervisor (daemon)** | `Supervisor` + `scripts/run_supervisor.py` | spawns/restarts workers, reclaims dead leases, refills queue, cleans up — runs forever |
| **OS watchdog** | systemd / NSSM / `restart: always` | resurrects the **supervisor itself** |
| **Dashboard** | `api/` (`/api/orchestration`) + `web/`, `frontend/` | queue depth, worker status, throughput, survivors |

## Queue design (`campaigns` table, migration m0006)
- **Dedup**: unique `content_hash` of the spec → identical campaigns never queued twice.
- **Atomic lease**: `BEGIN IMMEDIATE` → exactly one worker claims a campaign; sets `lease_expires_at`.
- **Crash recovery**: a dead worker's lease expires → `reclaim_stale()` re-queues it. Re-running is
  safe because the lab dedups candidates by content hash (idempotent / resumable).
- **Bounded retries**: `attempts < max_attempts` → re-queue; else parked `failed` (never dropped,
  never infinite-looped).
- **Priority**: lower `priority` runs first; FIFO within a priority.

## Fault tolerance matrix
| Failure | Recovery |
|---|---|
| Worker process crash | Supervisor `poll()` detects exit → respawns; lease expires → campaign reclaimed |
| Supervisor crash | OS watchdog (systemd/NSSM/Docker `restart: always`) restarts it; on boot it `reclaim_stale()` first |
| Power loss | On restart: WAL recovers the DB; supervisor reclaims all orphaned leases |
| Hung worker | Heartbeat goes stale; lease expires → reclaimed by another worker |
| Corrupted/failed campaign | Retried up to `max_attempts`, then parked `failed` with the error for inspection |

## Resource management
- **CPU/Memory**: capped via Docker `deploy.resources.limits`, systemd `CPUQuota`/`MemoryMax`. An
  OOM-killed worker is just another crash the supervisor recovers from.
- **Runtime**: campaigns are small (1 symbol-batch); a stuck one is bounded by the lease (reclaimed).
- **Cleanup**: `queue.cleanup(keep_days)` prunes terminal campaigns each tick; workers pruned when stale.
- **Queue prioritization**: `enqueue(spec, priority=…)`.

## Inbound deploy — "merge is deploy" (`deploy/pull_deploy.sh`)

`scripts/git_snapshot.py` pushes **VPS → GitHub**. Until 2026-07-30 nothing came back, so merging
to master deployed **nothing** and every change needed a manual SSH. That gap cost the desk 8h on
2026-07-26, when an orphaned executor ran pre-fix code while the fix sat committed.

```bash
sh deploy/pull_deploy.sh --dry-run      # fetch + print the full restart plan, change nothing
sh deploy/pull_deploy.sh                # apply (scheduled */10 in ops/crontab.manifest)
```

Run `--dry-run` first on any box, and any time the plan might include the executor.

**Every dangerous direction is a refusal, not a guess:**

| Situation | Behaviour |
|---|---|
| Modified tracked files | **Refuse** — that's an operator hotfix a fast-forward would destroy |
| Diverged / box has local commits | **Refuse** — fast-forward only; no unattended merge on the box that owns the book |
| CI gate red on the new commit | **Revert** to the exact prior commit, exit non-zero, restart nothing |
| `quant-deadman` invalidated | **Escalate to a human** — a ruin-rail restart is a window with no ruin rail |
| Nothing new upstream | Exits after `git fetch`, *before* the CI gate — so a 10-min poll is nearly free |

**What restarts is computed, not listed.** `libs/ops/deploy_plan.py` derives each supervised
process's blast radius from its real first-party import closure (`ast`, at plan time), so adding an
import widens it automatically. A hand-kept path list would rot silently and leave stale code
owning the book — the same failure by a second route. Measured: only the executor has a
first-party closure at all (53 files); the deadman, liquidation listener and dashboard import
nothing from `libs/`, which is why an ordinary `libs/` commit cannot touch the ruin rail.

**Evidence:** `data/pull_deploy_state.json` + `data/cro_ai_logs/pull_deploy.log`. `max_audit`'s
`deploy-path` fence fails on stale / never-ran / CI-red-hold / **action-owed** — that last one is
"new code on disk, old code still owning the book", which is the state a plain freshness check
would call healthy.

## Deploy

### Docker / VPS (recommended for 24/7 Linux)
```bash
# 1) Ingest history once on Windows (needs MT5): python scripts/ingest_history.py
# 2) Copy the repo (incl. data/lake) to the VPS, then:
docker compose up -d
docker compose logs -f supervisor        # watch the loop
# dashboard API: http://<vps>:8000/docs   (GET /api/orchestration for live queue+workers)
```

### Linux systemd
```bash
sudo cp deploy/quant-research.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now quant-research
journalctl -u quant-research -f
```

### Windows service
```powershell
powershell -ExecutionPolicy Bypass -File deploy\install-windows-service.ps1   # NSSM, auto-restart
# or the Task Scheduler fallback the script prints if NSSM is absent
```

### Bare process (dev)
```bash
python scripts/run_supervisor.py --workers 3 --db data/sor_research.sqlite --lake data/lake
```

## Cadence — scheduled ticks, not a hot loop (recommended)

Running the supervisor 24/7 on a **static** lake burns CPU for no new alpha (and raises the
cross-campaign deflation bar). Prefer a **bounded research tick** triggered when there is genuinely
new work — new data, fresh bars, or re-validation. `scripts/run_research_tick.py` seeds only NEW
campaigns (dedup), drains them, and exits.

**After ingestion (the real trigger):**
```bash
python scripts/ingest_history.py && python scripts/run_research_tick.py
```

**Linux cron (daily 02:00):**
```cron
0 2 * * * cd /opt/quant-platform && .venv/bin/python scripts/run_research_tick.py >> data/logs/tick.log 2>&1
```

**Windows Task Scheduler (daily):**
```powershell
schtasks /Create /TN QuantResearchTick /SC DAILY /ST 02:00 /RL HIGHEST /F `
  /TR "C:\Users\dell\quant-platform\.venv\Scripts\python.exe C:\Users\dell\quant-platform\scripts\run_research_tick.py"
```

Use the always-on supervisor (`run_supervisor.py` + systemd/NSSM/Docker) only when you have a
continuous *stream* of new data or many promoted alphas under live re-validation. Until then, ticks
are the higher-ROI cadence.

## Monitoring
- `GET /api/orchestration` → `{queued, leased, done, failed, depth, workers[], running}`.
- `GET /api/research` / `/api/overview` → candidate + survivor throughput.
- Logs: Docker `compose logs`, systemd `journalctl`, Windows `data/logs/supervisor.*.log` (NSSM).

## Invariants (never violated by orchestration)
Validation thresholds, statistical methodology, and the append-only audit log + research ledger are
**untouched**. The queue is operational state only. Honest results stand: more uptime ≠ weaker gates.
Finding zero survivors continuously is the expected, acceptable outcome.
