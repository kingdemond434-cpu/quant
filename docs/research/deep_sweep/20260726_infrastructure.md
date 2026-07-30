# DEEP COLD AUDIT — INFRASTRUCTURE — 2026-07-26

_Auditor: weekly deep sweep, infrastructure subsystem. Doctrine v2 (outcome-not-config). Status: IN PROGRESS — findings appended incrementally; if this line is still here the run was cut off and the partial content below is the deliverable._

## SCORES (provisional until end)

- current_capability_pct: TBD
- practical_ceiling_estimate: TBD
- ceiling_gap: TBD
- opportunity_cost_1y: TBD
- confidence: TBD
- unknown_unknown_score: TBD
- info_gain_if_investigated: TBD
- expected_alpha_contribution: TBD
- expected_compounding_contribution: TBD
- ceiling_expansion: TBD

## 1. WHAT WE KNOW (validated strengths AND verified defects, each with proving command)

### 1a. Validated strengths

- **S1 — The survival chain is alive and producing, end to end.** `ps aux` shows `run_deadman_switch.py` (since 00:25), `run_cashcarry_executor.py --live` (respawned 11:33), `liquidation_listener.py`, three recorders. Heartbeats are seconds-fresh: `ls -la data/*heartbeat` → `deadman_heartbeat`, `recorder_heartbeat`, `recorder_spot_heartbeat`, `recorder_bybit_heartbeat`, `cashcarry_exec_heartbeat`, `liquidation_heartbeat` all mtime 11:46–11:47 during the audit. `cat data/deadman_state.json` → live v2 state, `breaches: 0`, high_water tracked. This is outcome, not config.
- **S2 — Single-book invariant actually fires.** `tail data/cashcarry_respawn.log` → `another live executor owns the book -- exiting (single-book invariant)`. The double-executor protection has been observed working in production, not just written.
- **S3 — No OOM kill in 14 days despite thin RAM.** `journalctl -k --since "14 days ago" | grep -i oom` → empty. The box has survived at its current memory footprint.
- **S4 — Incident discipline is real.** `data/INCIDENT_20260719_DEADMAN.md`, `INCIDENT_20260722_DEADMAN5.md`, `DEADMAN_RECONCILIATION_20260719.md` exist with evidence tables, mechanism analysis (`legs_v -> $0` unwind undercount + in-flight margin), ruled-out alternatives, and $-quantified real loss (-$63.60 vs a -56% latched read). Few retail-scale desks write post-mortems this good.
- **S5 — Code is off-box.** `git log --oneline -1` == `git log --oneline -1 origin/master` (e688772): the repo is pushed to GitHub, so code+docs survive box loss.
- **S6 — CI runs the whole tree and leaves a truth marker.** `scripts/run_ci.py` gates ruff + full `pytest tests/` (whole-tree since 2026-07-25) + stress harness, and writes `data/.ci_last_run.json` so a red gate is visible to `max_audit` even when the brain is quota-dead.
- **S7 — Scheduling redundancy caught a dead scheduler class once already.** Crontab comments record the watchdog/daily-cycle resurrection of 2026-07-23 (11.5-day frozen clocks) and the direct-cron fix; `systemctl list-timers` + `crontab -l` show both planes now firing on schedule with recent `LAST` timestamps.
- **S8 — System-level telemetry exists for retrospectives.** `systemctl list-timers` → `sysstat-collect.timer` every 10 min (sar history), `logrotate.timer`, `e2scrub`/`xfs_scrub`, `fail2ban-server` running (`ps aux`). Brute-force protection and disk scrubbing are on.

### 1b. Verified defects (each with the command that proves it)

- **D1 — SEV: watchdog↔tunnel control loop has been dead-firing every 3 minutes for ~2 weeks.** `grep -c '(re)started public-tunnel' data/cro_ai_logs/watchdog.log` → **1047**. Cause: `scripts/watchdog.py:33` monitors `data/tunnel_heartbeat`, whose writer died — `ls -la data/tunnel_heartbeat` → mtime **Jul 12 00:01** — while cloudflared itself is alive (`pgrep -a cloudflared` → pid 36532, tunnel `quant-dash`). The watchdog sees an eternally-stale heartbeat and "restarts" the tunnel every tick; 1047 futile restarts, log spam, and a monitoring channel that can never signal a REAL tunnel death. Classic self-greening-guard inverse: a permanently-red check acted on forever with no escalation. A control loop that fires 1047 times without effect must page after N failures, not loop silently.
- **D2 — SEV: 3.7 GiB RAM, 121 MiB free, ZERO swap, no memory limits on any organ.** `free -h` → Mem 3.7Gi total / 121Mi free / 1.0Gi available; `swapon --show` → empty. Meanwhile `ps aux` showed TWO concurrent full pytest runs (283 MB each, 96% CPU) racing next to the LIVE executor (231 MB). One heavy organ collision away from the kernel OOM-killer choosing a victim — and with no `MemoryMax=` on quant units and no swap, the victim can be the dead-man switch or the live executor. Survival-rail-adjacent infrastructure risk.
- **D3 — SEV: the 3.5 GB data moat exists on exactly one disk.** `du -sm data/*` → `data/moat` 3,569 MB + `data/lake` 1,449 MB; `.gitignore` → `data/*`; `git ls-files data/ | wc -l` → 7; no rsync/rclone/restic/borg anywhere in `scripts/ ops/` (grep). The desk's irreplaceable forward-recorded data — the explicit moat, unpurchasable at any price because it is time-indexed observation — has zero backup. Box loss = moat loss. Code survives (S5); the data does not.
- **D4 — SEC: GitHub PAT in cleartext in the remote URL.** `git remote -v` → `https://ghp_…[REDACTED]…@github.com/kingdemond434-cpu/quant.git`. A classic PAT sits in `.git/config`, readable by every process on the box, printed by any tooling that echoes remotes. Rotate + move to a credential helper or fine-grained deploy token.
- **D5 — SEC: an Anthropic OAuth token leaked into a FILENAME.** `ls data/secrets/` → a 0-byte file literally named `sk-ant-oat01-…[REDACTED]…` (mtime Jul 19 19:06, two minutes before `claude_oauth_token` was written properly). A fat-fingered shell redirect turned a secret into a directory entry that every `ls`, backup, and audit log now reproduces. Token must be treated as exposed; delete file, rotate token.
- **D6 — SEC: secret files world-readable, with .bak sprawl.** `ls -la data/secrets/` → `llm_panel.json` (13 API keys per `grep -c '"key"'`) is `-rw-r--r--`, plus `llm_panel.json.bak`, `.bak2` copies; `binance_testnet.json`, `netlify.json`, `ngrok.json`, `ntfy.json` also 644, while `databento.json`/`fred.json`/`claude_oauth_token` are correctly 0600. Inconsistent hygiene = the policy is manual, not enforced.
- **D7 — SEC/AVAIL: dashboard bound to 0.0.0.0:8080 with unverifiable firewall.** `ss -tlnp` → `0.0.0.0:8080` (python pid 11386, serve_dashboard). Exposure via cloudflared tunnel is intentional; the direct bind to all interfaces is not obviously so, and `sudo -n ufw status` → no sudo for user quant, so host-firewall state CANNOT be verified from inside the box. If provider firewall is open, the dashboard (equity curves, positions) is world-readable bypassing the tunnel.
- **D8 — CI gate is currently RED, self-inflicted weekly by the deep sweep itself.** `cat data/.ci_last_run.json` → `{"ok": false, …}`; `tail data/cro_ai_logs/full_suite.log` → `test_finding_registry.py::TestArtifactGovernance` fails: "15 docs artifact(s) claimed by NO law -- 20260726_alpha-discovery.md, … 20260726_infrastructure.md …". The weekly sweep organ writes 8 reports every Sunday that the §36 governance test rejects until manually classified → the desk's commit gate goes red every Sunday morning by design collision. (Ruff red in the same marker did NOT reproduce: `.venv/bin/python -m ruff check scripts libs tests` → "All checks passed!" — see D9.)
- **D9 — CI has no mutual exclusion and its truth-marker races.** `ps aux` during audit → two simultaneous `run_ci.py` → `pytest tests/ -q` processes (started 11:44 and 11:46). `scripts/run_ci.py` takes no lock (no flock/pgrep in file); `data/.ci_last_run.json` is last-writer-wins, so a stale red can overwrite a fresh green (or vice versa), and two full-tree pytest runs double the peak RAM on a 3.7 GiB box (see D2). The non-reproducing ruff red in D8 is consistent with exactly this race.
- **D10 — The pager path's delivery has no delivery evidence, and the ntfy topic is low-entropy on a public relay.** `cat data/cro_ai_logs/digest_page.log` → EMPTY despite a daily 08:30 cron appending to it since creation; `grep -c 'paged\|ntfy' data/cro_ai_logs/watchdog.log` → 0. `wc -c data/secrets/ntfy.json` → 25 bytes total JSON ⇒ topic ≈ 10–15 chars on ntfy.sh, a PUBLIC pub-sub where knowing the topic name = read AND write. Pages carrying equity numbers ride an unauthenticated public channel, and no artifact anywhere proves a page has ever been DELIVERED (received on a device). The desk's alerting endpoint is config, not verified outcome.
- **D11 — Stale heartbeat artifact from a retired organ still monitored.** `ls -la data/executor_heartbeat` → Jun 28 16:21; `scripts/watchdog.py:30` still loads it (`_HB`). Dead artifacts wired into live monitors either fire forever (D1) or train operators to ignore red.
- **D12 — Organizational entropy: two scheduler planes run overlapping organs; Windows-era remains.** Crontab runs `ops/run_cro_ai.sh` at 02:45/14:45/20:45 AND systemd `quant-cro-ai.timer` runs the same script daily 08:45 (`systemctl cat quant-cro-ai.service` → same ExecStart); crontab runs `daily_research_cycle.py` at 02:00 AND `quant-cro.timer` at 08:01 (same script, only the cron line has a pgrep guard — cross-plane mutual exclusion depends on the script's own flock, unverified). Plus 8 `.bak-20260716` file copies, 4 Windows `.ps1` scripts, `deploy/install-windows-service.ps1` (find output in audit log). Two planes = two places to forget, and the 2026-07-23 watchdog incident happened precisely in the seam between planes.
- **D13 — RECONCILE-FAIL retried 598× with no escalation.** `tail data/cashcarry_respawn.log` → `RECONCILE-FAIL COOKIEUSDT x598 (both market+limit rejected…)` and `x597` the cycle before; `data/cashcarry_error.log` (mtime 10:08) shows the COOKIE maker-path leg unfilled. An error state that persists ~600 consecutive cycles is not a retry, it is a stuck state — and nothing pages at x10, x100, x598. Alert-quality gap in the live-money path (execution owns the bug; infra owns the missing escalation ladder).

## 2. WHAT WE DON'T KNOW (ignorance ledger)

_(appending as verified)_

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_(ranked at end)_

## 4. WHAT WE TEST NEXT (experiments w/ success criteria)

_(written at end)_

## PERSPECTIVE COVERAGE TRACKER

- [ ] INTERNAL
- [ ] EXTERNAL
- [ ] FUTURE
- [ ] CONTRARIAN
- [ ] GREENFIELD
- [ ] FRONTIER
- [ ] NEGATIVE-SPACE SWEEP
