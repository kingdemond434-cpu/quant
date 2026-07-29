# DEEP COLD AUDIT — INFRASTRUCTURE — 2026-07-29

Auditor: weekly deep cold audit (v2 doctrine), subsystem = infrastructure.
Scope: services (correctness/latency/availability/resilience/recoverability/scaling/cost/
fault-tolerance/deploy+rollback/test-depth/observability/alert-quality/tech-debt/upgrade-readiness);
security + operational resilience; organizational entropy. READ-ONLY sweep; every claim carries its
proving command. Note: this file previously held a BRAIN_AUTH_FAILED stub (the 04:00 Sunday sweep
died on quota Sun→Wed; organ-catchup re-fired it — the retry harness itself worked).

STATUS: IN PROGRESS — first tranche of verified findings; final scores at end of sweep.

## 1. WHAT WE KNOW — validated strengths (each with proving command)

- **S1 Organ scheduling breadth + idempotent re-fire.** ~20 crontab entries with `flock` guards +
  8 `quant-*` systemd timers with `Persistent=true` (`crontab -l`; `systemctl list-timers`). The
  catch-up layer measurably works: `tail data/cro_ai_logs/organ_catchup.log` shows quota probes
  every 5 min ("owed=deep_sweep quota=DEAD -- no fire" 01:23→05:55), then "re-fired deep_sweep" at
  06:00 which really produced artifacts — `ls -la docs/research/deep_sweep/20260729*` shows
  data-intelligence.md 26KB (06:13) and data-moat.md 33KB (06:26) written this morning, while the
  four ~491-byte failure stubs correctly queue for re-run (resume-skip threshold 1200b). It also
  serializes brain work ("field busy ... holding retries so they do not share the window").
- **S2 Collectors/recorders are alive (outcome, not config).** `find data -name '*.jsonl' -mmin
  -120 | wc -l` → **56 files fresh <2h** (oi_ls bronze per-symbol, venue_divergence_shadow,
  defi_lending, mine_conversion_log...). `pgrep -af run_recorder` → 3 recorder processes running
  (bybit, spot, base). Caveat → W6 (their logs are 0-byte, so aliveness is only provable by pgrep +
  file mtimes, not by any heartbeat line).
- **S3 Secrets file hygiene baseline is right.** `ls -la data/secrets/` → all live secrets mode
  `-rw-------` (600), gitignored (`data/*` in .gitignore), loaded from files by `ops/brain_env.sh`
  rather than hardcoded. `git log -S 'ghp_Da2'` → empty: the GitHub PAT was never committed.
- **S4 CI gate on every push.** `.github/workflows/ci.yml`: ruff + `mypy --strict` + pytest on all
  branches + PRs, concurrency-cancelled, 20-min timeout. (Pass/fail status not verifiable from the
  box — see U3.)
- **S5 SSH hardened, fail2ban live.** `grep PasswordAuthentication /etc/ssh/sshd_config` →
  `PasswordAuthentication no`; `systemctl is-active fail2ban` → `active`.
- **S6 Dead-man switch is a live process.** `pgrep -af deadman` → pid 751665
  `run_deadman_switch.py` running. External heartbeat is wired into the 3-min loop:
  `systemctl cat quant-refresh.service` runs `run_alerts.py` every 180s and only `run_alerts.py`
  references `data/secrets/heartbeat_url.json` (`grep -rl heartbeat_url scripts/ libs/`), so an
  alert-loop death silences the external heartbeat → external page. Supervision of the deadman
  process itself: → U7.
- **S7 Per-change rollback snapshots exist.** `ls data/rollback/` → 20+ timestamped code snapshots
  (e.g. `20260729T060354_pbo-rc-per-candidate-gate/`), each carrying the libs tree of the change.
  (Same-disk only — this is change-rollback, not disaster recovery; see O1.)
- **S8 No OOM kill in 17 days despite thin RAM.** `journalctl -k | grep -iE 'out of memory|oom'` →
  empty over the full 17-day boot (`uptime` → up 17 days).
- **S9 Code + docs are off-box.** `git branch -vv` → master in sync with `origin/master`
  (github.com/kingdemond434-cpu/quant); docs/ (8MB) tracked. The *data lake is not* — O1.
- **S10 Quota-death was measured, not guessed.** `cat data/quota_watch.json` → verdict `max_needed`
  with evidence "cycles: 0 ok / 4 scheduled... overall quota-death rate 100%" (baseline
  2026-07-22). The desk knew its availability floor and escalated with a concrete billing fix.
  Caveat: that monitor is now dormant — W4.

## 2. WHAT WE DON'T KNOW — ignorance ledger

- **U1 Whether 0.0.0.0 binds are internet-reachable.** `sudo -n ufw status` / `iptables -L` →
  sudo denied for user quant. `ss -tlnp` shows `0.0.0.0:8080` (serve_dashboard.py) and `0.0.0.0:22`.
  A provider-level firewall may or may not exist. Unverifiable from this account; needs one probe
  from an external vantage point (→ T3).
- **U2 Whether dash.quanttt.xyz has Cloudflare Access in front.** `~/.cloudflared/config.yml`
  ingress goes straight to `http://localhost:8080` with no auth annotation; server-side CF config
  invisible from the box. The hostname is discoverable via certificate-transparency logs.
- **U3 CI pass/fail history.** `which gh` → not installed; no local CI-status artifact found. Only
  indirect evidence (commit messages "ci-green"). The desk cannot see its own gate from the box.
- **U4 GitHub PAT scope/expiry.** A classic `ghp_` token (in the remote URL — O3); classic PATs
  are frequently all-repo scope; cannot introspect without exercising it (not done in a read-only
  audit).
- **U5 Re-obtainability of data/moat (5.4G).** How much of the moat is re-downloadable vs
  vanished-source-archive is not recorded per-dataset anywhere machine-readable this audit found;
  the FREE-FRONTIER doctrine itself says sources decay. Treat as partially irreplaceable → O1.
- **U6 Whether a restore has ever been drilled.** `libs/ops/backup.py` ships a `RestoreDrill`
  class; `grep -rn 'ops.backup' scripts/ ops/ libs/` (excl. rollback copies) → **only
  `libs/ops/__init__.py`** re-exports it. No scheduler, no artifact, no drill log found. Restore
  capability is *configured*, provably never *exercised* (the exact outcome-not-config failure
  class this audit hunts).
- **U7 Deadman/dashboard/tunnel process supervision depth** — resolved partially below (F-series);
  what respawns `run_deadman_switch.py` if it dies is checked in the second tranche.
- **U8 Off-box copies held by the principal** (laptop clones, manual downloads) — invisible to
  this box; assumed ZERO for DR math until attested.

## 3. WHAT COULD MATTER MOST — ranked opportunities

(first tranche; final ranking at end of report)

- **O1 — DISASTER RECOVERY IS ABSENT: ~7GB of single-copy state on one disk.** Evidence:
  `du -sh data/*` → moat 5.4G + lake 1.5G; `.gitignore` → `data/*` excluded except 3 files;
  `grep -riEl 'rclone|restic|borg|duplicity|aws s3' scripts/ ops/ libs/` → no live match;
  `crontab -l | grep -iE 'backup|rsync|s3'` → nothing; `df` → everything on `/dev/sda1`.
  The forward-clock series (Stage-B promotion evidence), the bronze lake, the moat archives, 9
  SQLite SoRs, the graveyard/research-memory ledgers — one disk event deletes the desk's entire
  epistemic state and every forward clock restarts from zero. `libs/ops/backup.py` (SQLite online
  backup + sha256 manifest + restore drill) has existed since Jun 18 with ZERO callers (U6).
  This is the highest-severity infrastructure finding: both supreme objectives depend on forward
  evidence continuity, and its survival is currently one `fsck` away from zero. Cost of fix:
  restic→B2/S3 ≈ $0.03–0.30/mo for 7GB + a nightly cron line + weekly restore-drill cron.
- **O2 — QUOTA STARVATION is the desk's real availability ceiling.** Evidence: quota-death rate
  100% measured (S10); `systemctl list-units --failed` → quant-cro-ai, quant-dataaxis,
  quant-litminer, quant-prospector all `failed` (each ~7s CPU = brain-auth fast-fail at scheduled
  hour, all four of yesterday's scheduled runs); the WEEKLY Sunday-04:00 deep sweep is completing
  on WEDNESDAY (this report; organ_catchup starved 01:23→06:00 today alone). The desk's research
  cadence is bounded by brain-token supply and collision timing, not by compute, data, or ideas.
- **O3 — GitHub PAT in the git remote URL, one week after being flagged.** `git remote -v` →
  `https://ghp_…[REDACTED]…@github.com/…/quant.git`. Last week's audit
  (20260726_infrastructure.md D4) reported exactly this; it is still there 7 days later. That
  token is the write credential to the tree the VPS executes — compromise = supply-chain into a
  live-capital system. §41 disposition status checked in second tranche.
- **O4 — Watchdog "restarts" the public tunnel every 3 minutes, forever.** `grep -c
  'public-tunnel' data/cro_ai_logs/watchdog.log` → **2381** restart lines; meanwhile
  `pgrep -af cloudflared` → ONE stable process (pid 36532, running for weeks) actually serving
  the tunnel. The watchdog's aliveness check never sees the real tunnel, spawns
  `run_ngrok.py`/`run_tunnel.py` every tick, and floods its own log — a broken sensor + noise
  source inside the highest-frequency supervisor (inert-lever class). Root cause pinned in
  second tranche.
- **O5 — ~900MB of RAM burned by scratch files on tmpfs.** `df -h -t tmpfs` → /tmp 1.9G tmpfs,
  904M used; `du -sh /tmp/*` → qmine 374M, l2.csv.gz 152M, pytest-of-quant 115M,
  audit_branch_esc 48M… On a swapless (`swapon --show` → empty) 3.7G box that is ~24% of system
  RAM held by forgotten mining scratch. Two-line fix (write scratch under data/tmp on disk;
  tmpfiles age override) = largest single RAM headroom win available.
- **O6 — Alert-rail code is running uncommitted in prod.** `git diff --stat` → 12 dirty files
  incl. `scripts/run_alerts.py` (+37, the Holm slot-budget axis-visibility fix) executing every
  180s via quant-refresh while never having passed CI. §33: uncommitted output did not happen.
- **O7 — Dashboard double-exposure.** serve_dashboard.py binds `0.0.0.0:8080` by explicit default
  ("bind LAN so the phone can reach it" — on a public VPS there is no LAN) *and* is published at
  dash.quanttt.xyz via cloudflared. Read-only static server of web/ (NAV, positions, research
  state). Bind 127.0.0.1 (tunnel unaffected) + CF Access in front of the hostname.

## 4. WHAT WE TEST NEXT — concrete experiments

(final list at end of report)

## APPENDIX: PERSPECTIVE COVERAGE LOG

- INTERNAL: in progress (S1-S10, O2, O4)
- EXTERNAL: pending second tranche
- FUTURE: pending second tranche
- CONTRARIAN: pending second tranche
- GREENFIELD: pending second tranche
- FRONTIER: pending second tranche
- NEGATIVE-SPACE SWEEP: pending second tranche
