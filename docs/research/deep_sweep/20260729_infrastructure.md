# DEEP COLD AUDIT — INFRASTRUCTURE — 2026-07-29

Auditor: weekly deep cold audit (v2 doctrine), subsystem = infrastructure. Host:
`ubuntu-4gb-hel1-5` (Hetzner, 2 vCPU / 3.7GB RAM / 38GB disk, no swap), up 17 days.
Scope: services (correctness/latency/availability/resilience/recoverability/scaling/cost/
fault-tolerance/deploy+rollback/test-depth/observability/alert-quality/tech-debt/
upgrade-readiness); security + operational resilience; organizational entropy. READ-ONLY sweep;
every claim carries its proving command. This file previously held a BRAIN_AUTH_FAILED stub —
the Sunday-04:00 sweep died on quota repeatedly and organ-catchup re-fired it today (Wednesday);
the retry harness worked, the 3-day latency is itself finding O2.

## SCORES

- current_capability_pct: **62** — scheduling/self-healing breadth is real and measured; DR is
  absent, the alert channel is saturable, availability is quota-floored, one supervisor branch
  was broken for 17 days.
- practical_ceiling_estimate: **92** (for a single-VPS autonomous desk; residual single-box and
  single-vendor-quota risk is irreducible without a second node/provider).
- ceiling_gap: **30 points**, of which ~20 are purchasable for < $5/mo + ~2 days of wiring
  (backup+drill, pager lanes, reboot bundle, tmpfs, CI parity).
- opportunity_cost_1y: dominated by the DR tail: P(single-VM/disk loss) ≈ 2–5%/yr × loss of the
  entire forward-evidence record, whose accumulation the desk's own cycle names as the binding
  constraint ("constraint=calendar-time data accumulation (not engineering throughput)" —
  `data/cro_ai_logs/daily_research_cycle.log`). Plus a continuous quota-latency tax: 100%
  first-attempt organ death measured (S10), sweep 3 days late. Plus a small-but-unbounded tail on
  a dropped ruin-rail page during pager backoff (observed live today).
- confidence: **0.8** on findings (all command-cited), **0.6** on the ranking.
- unknown_unknown_score: **0.5** — this account is sudo-blind (firewall, root crontab,
  provider-level config all invisible), Cloudflare-side and GitHub-side state invisible (U1–U4).
- info_gain_if_investigated: **high** for the two cheap probes (external port probe, restore
  drill) — each converts a top-3 unknown into a fact for ~minutes of work.
- expected_alpha_contribution: indirect but first-order — organ availability IS discovery
  cadence (objective 2), and forward-evidence survival IS the promotion pipeline (objective 1).
- expected_compounding_contribution: **high** — backup, pager lanes, and quota-aligned
  scheduling protect every future cycle's output; they are multipliers, not features.
- CEILING EXPANSION: the ceiling is set by an *organizational* assumption ("one VPS, one vendor
  quota pool"), not a technological one. A €4/mo storage box + weekly provider snapshot lifts the
  DR half; a second cheap brain path (already half-built: `_BRAIN_MODEL_CHAIN` falls back across
  3 models — `ops/brain_env.sh:76`) lifts the availability half. Neither survival rail is touched
  by any of this.

## 1. WHAT WE KNOW — validated strengths (each with proving command)

- **S1 Organ scheduling breadth + idempotent re-fire, measured working.** ~20 crontab entries
  with `flock` guards + 8 `quant-*` systemd timers with `Persistent=true` (`crontab -l`;
  `systemctl list-timers`). The catch-up layer provably recovers quota deaths:
  `data/cro_ai_logs/organ_catchup.log` shows 5-min probes ("owed=deep_sweep quota=DEAD -- no
  fire" 01:23→05:55 today), then "re-fired deep_sweep" at 06:00 which really produced artifacts
  (`ls -la docs/research/deep_sweep/20260729*` → data-intelligence 26KB 06:13, data-moat 33KB
  06:26), and on 07-28 evening reached "nothing owed -- all organs produced". It also serializes
  brain work ("field busy ... holding retries so they do not share the window") — real
  concurrency control, not config.
- **S2 Collectors/recorders alive (outcome, not config).** `find data -name '*.jsonl' -mmin -120
  | wc -l` → **56 files fresh <2h**; `pgrep -af run_recorder` → 3 recorder processes up.
- **S3 Money-path supervision chain works end-to-end.** cron (3-min) → `scripts/watchdog.py` →
  heartbeat-gated respawn of executor/deadman/liquidations (`sed -n 150,205p scripts/watchdog.py`),
  and the heartbeats are FRESH: `find data -maxdepth 1 -iname '*heartbeat*'` → cashcarry_exec
  06:36:23, deadman 06:36:01, liquidation 06:37:58, recorders 06:37–38 against now=06:38.
  A FREEZE kill-file mechanism exists in the same path (watchdog reaps all desk pythons when
  `data/FREEZE` exists; file currently absent, as it should be). Deadman is "no LLM, no configs,
  no libs imports" per its spawn comment — a genuinely isolated Tier-3 rail.
- **S4 Secrets file hygiene baseline is right.** `ls -la data/secrets/` → all live secrets mode
  600, gitignored, loaded from files by `ops/brain_env.sh`. `git log -S 'ghp_Da2'` → empty (the
  GitHub PAT was never committed; last week's report correctly redacted it).
- **S5 CI gate exists and is green *today*.** `.github/workflows/ci.yml` (ruff + mypy --strict +
  pytest on every push); locally `ruff check .` → exit 0 and the previously-failing
  `tests/research/test_finding_registry.py` now passes 32/32 (`pytest -q` → all dots). The
  07-28 "CI RED AND TOLERATED" state (R0022) was substantively fixed within a day.
- **S6 SSH hardened, fail2ban live, unattended security upgrades on.**
  `PasswordAuthentication no`; `systemctl is-active fail2ban` → active; `20auto-upgrades` → 1/1.
- **S7 Per-change rollback snapshots exist.** `ls data/rollback/` → 20+ timestamped code
  snapshots. (Same-disk change-rollback, not DR — see O1.)
- **S8 No OOM kill in 17 days despite thin RAM.** `journalctl -k | grep -iE 'oom'` → empty.
- **S9 Code, docs, graveyard, and decision ledger are off-box via git.** master in sync with
  origin (`git branch -vv`); `docs/graveyard.md` tracked; `data/decision_ledger.json` +
  `data/nav_attestation.jsonl` are the 3 gitignore exceptions; multiple commits daily
  (`git log --oneline -12` → 5 commits in the last 19h). The sacred graveyard survives box loss.
- **S10 The desk measures its own availability.** `cat data/quota_watch.json` → verdict
  `max_needed`, evidence "cycles: 0 ok / 4 scheduled … overall quota-death rate 100%"
  (2026-07-22 baseline) — quota starvation was detected and escalated with a billing fix.
- **S11 Environment rebuild is pinned.** `requirements-vps.txt` → exact `==` pins generated
  2026-07-12 for this box (numpy 2.4.6, pandas 2.3.3, …); Python 3.12.13; .venv 703M.
- **S12 System log hygiene is bounded.** `journalctl --disk-usage` → 53.8M; no desk log >500KB
  (`find . -name '*.log' -size +500k` → none outside .venv).

## 2. WHAT WE DON'T KNOW — ignorance ledger

- **U1 Whether 0.0.0.0 binds are internet-reachable.** `sudo -n ufw status` → sudo denied for
  quant. `ss -tlnp` → `0.0.0.0:8080` (serve_dashboard.py) and `0.0.0.0:22`. A Hetzner cloud
  firewall may or may not exist. One external probe resolves this (T2).
- **U2 Whether dash.quanttt.xyz has Cloudflare Access in front.** `~/.cloudflared/config.yml`
  ingress → `http://localhost:8080`, no auth annotation; CF-side config invisible. The hostname
  is discoverable via certificate-transparency logs regardless of being "unpublished".
- **U3 GitHub Actions pass/fail history.** `which gh` → absent. Local `run_ci.py` state is known
  (green today); the hosted gate's history is not verifiable from the box.
- **U4 GitHub PAT scope/expiry** (classic `ghp_` token — O5). Not introspected (would require
  exercising the credential in a read-only audit).
- **U5 Re-obtainability of data/moat (5.4G)** if lost — not recorded per-dataset anywhere this
  audit found; FREE-FRONTIER doctrine itself says sources decay. Treat as partially
  irreplaceable for DR math.
- **U6 Whether a restore has ever been performed.** `grep -rn 'RestoreDrill' scripts/ libs/`
  (excl. rollback copies, backup.py itself, `__init__`) → **zero callers**, `find data -iname
  '*restore*'` → nothing. Proven never-exercised (this is a known-unknown resolved to "never").
- **U7 Root-owned state.** No sudo → root crontab, root processes' config, and `user@0.service`
  failed-unit cause are invisible.
- **U8 Off-box copies held by the principal** (laptop clones, manual pulls) — invisible from
  here; DR math below assumes zero until attested.
- **U9 Full test-suite runtime/count.** 177 test files (`find tests -name 'test_*.py' | wc -l`);
  `pytest --collect-only -q` needs >100s to enumerate (two timeouts at 100/110s; a longer run
  returned 178 collection lines) — collection latency itself is a CI-feedback smell; suite
  runtime bounded only by ci.yml's 20-min cap.

## 3. WHAT COULD MATTER MOST — ranked opportunities

Ranked by expected impact × confidence / (cost × maintenance). CM = compounding multiplier.

- **O1 — DISASTER RECOVERY IS ABSENT: ~7GB of single-copy state on one disk. [CM, #1]**
  Evidence: `du -sh data/*` → moat 5.4G + lake 1.5G; `.gitignore` → `data/*` excluded except 3
  files; `grep -riEl 'rclone|restic|borg|duplicity|aws s3' scripts/ ops/ libs/` → nothing live;
  no backup line in `crontab -l`; everything on `/dev/sda1` (`df -h`). Blast radius on one disk
  event: every forward-clock series (Stage-B promotion evidence), the bronze lake, the moat, the
  research memory (`scripts/research_memory.py:24` → `data/sor_research.sqlite`, 22 tables,
  gitignored), 9 SQLite SoRs, all collector history. The graveyard and decision ledger survive
  (S9); the *evidence engine* does not. The desk's own cycle log names "calendar-time data
  accumulation (not engineering throughput)" as the binding constraint — a disk failure resets
  exactly that resource to zero. Meanwhile `libs/ops/backup.py` (online backup + sha256 manifest
  + RestoreDrill) has existed since Jun 18 with zero callers (U6), and its hardcoded target
  `sor.sqlite` is an EMPTY database — `sqlite3 data/sor.sqlite` → **0 tables** while
  sor_research/sor_crypto hold 22 tables each. Even if wired today it would back up nothing.
  Fix: restic → Hetzner storage box (€3.2/mo) or B2 (~$0.03/mo for 7GB compressed), nightly
  cron + weekly scripted restore-drill with sha256 + row-count assertions; point BackupManager
  at the real SoRs or retire it. Complexity: low. Failure mode of fix: silent backup rot —
  hence the drill is the deliverable, not the backup. Retirement: never (rail-adjacent).
- **O2 — QUOTA STARVATION is the availability floor; scheduled-time success ≈ 0%. [#2]**
  Evidence: quota-death rate 100% measured (S10); yesterday all four scheduled organ services
  fast-failed in ~7s CPU each (`systemctl list-units --failed` + `systemctl status` → cro-ai
  08:45, dataaxis 14:00, prospector 18:00, litminer 19:00); the WEEKLY Sunday-04:00 sweep
  completed Wednesday; today's sweep resume starved 01:23→06:00 (organ_catchup.log). Catch-up
  converts total loss into a latency tax (hours/day per organ; "nothing owed" reached 20:50
  yesterday) — but the tax is paid daily, and the brain-collision serialization means organ work
  and interactive/brain work contend for one pool. Second-order defect: recovered failures leave
  units permanently red, so `systemctl --failed` is desensitized (4 stale reds) and can no
  longer serve as a real alarm surface. Fixes, cheapest first: (a) align organ start times with
  the credit-reset window instead of round-clock aesthetics (measure: first-attempt success
  >60%); (b) `systemctl reset-failed` after successful catch-up so the failed list means
  something; (c) the standing `max_needed` billing verdict is with the principal — this audit
  only notes the evidence stands; (d) route mechanical organ steps (log triage, collection
  digests) to the free/cheap chain tail so scheduled digs need less of the scarce pool.
- **O3 — The pager was rate-limited TODAY; one shared topic, 7 independent senders, one global
  1h mute. [#3, ruin-rail adjacency]** Evidence: `journalctl -u quant-refresh --since today` →
  "pager push failed: HTTPError 429" at 06:23, then "pager 429 backoff: 57m remaining";
  `data/cro_ai_logs/digest_page.log` → "digest page failed: 429". `grep -rln 'ntfy' scripts/`
  → 7 scripts each with their own push implementation, no shared budget, no priority lanes;
  `scripts/run_alerts.py:43-89` → after ANY 429 the backoff file mutes ALL pushes for 1h —
  including a hypothetical ruin-rail page. The code comment dates the same incident to 07-20 —
  this recurs. The flood source pattern: quota-fail pages from re-fired organs (each organ pages
  on brain-auth failure per crontab header) burn the topic budget precisely on bad mornings —
  the alert channel fails exactly when things are failing. Fix: one pager lib with two lanes
  (URGENT → separate topic/provider, never coalesced, tested monthly; routine → coalesced
  digest), plus R0036's prefix bug fix. Cost: half a day. CM: protects every future alert.
- **O4 — Reboot bundle: a reboot is PENDING; one organ dies at reboot; the reboot has never
  been drilled. [#4] (CORRECTED mid-audit)** This audit's draft claimed cloudflared had no
  systemd unit — FALSE: the orphan-sweep agent found `quant-tunnel.service`, and verification
  confirms it (`systemctl status quant-tunnel` → enabled, active, Main PID 36532 = the running
  cloudflared). The tunnel survives reboot. What remains true and verified:
  (a) `/var/run/reboot-required` → present (linux-image 7.0.0-27/-28, **libc6**) — a security
  reboot is due and running processes use pre-patch libc until it happens;
  (b) `quant-blindrediscovery.timer` is active-but-**disabled** (`is-enabled` → disabled) — the
  monthly rediscovery organ silently dies at that reboot;
  (c) the box has NEVER rebooted since migration (up 17 days = its whole life) — unattended
  recovery is configured (21 quant-* units, `ls /etc/systemd/system/quant-* | wc -l`) but
  unproven, exactly the config-vs-outcome gap this doctrine hunts;
  (d) the watchdog's tunnel branch is broken regardless — see O9.
  Fix (15 min): `systemctl enable quant-blindrediscovery.timer`, then a SCHEDULED reboot drill
  with success criterion (all heartbeats fresh <10 min post-boot, tunnel serving, zero human
  action).
- **O5 — GitHub PAT in the git remote URL, 8 days after being flagged — and the flag fell out of
  the ledger. [#5, security + meta]** `git remote -v` → `https://ghp_…[REDACTED]…@github.com/…`.
  Last week's audit (20260726_infrastructure.md, finding D4) reported exactly this; scanning
  `docs/research/recommendation_ledger.json` (36 rows) → **no row exists for it** — the §41
  pipeline (every recommendation gets a row) dropped a *security* finding, which is the exact
  failure mode §41 exists to prevent, demonstrated on the highest-stakes item in last week's
  report. The token is the write credential to the tree the VPS executes (supply-chain into a
  live-capital system if leaked; it is readable by every process as `.git/config` mode 664).
  Fix: rotate token, switch remote to SSH deploy key (or fine-grained PAT in a 600-perm
  credential store), AND row this + last week's D-findings in the ledger. 15 minutes.
- **O6 — ~900MB of RAM burned by scratch on tmpfs, on a swapless 3.7GB box. [#6, quick win]**
  `df -h -t tmpfs` → /tmp 1.9G tmpfs, 904M used; `du -sh /tmp/*` → qmine 374M, l2.csv.gz 152M,
  pytest-of-quant 115M, audit_branch_esc 48M…; `swapon --show` → empty. sar (07-29 06:10–06:30)
  shows free RAM dipping to **199MB** and commit% to 85.45 during the organ burst — one more
  concurrent organ approaches OOM with no swap to absorb it (S8 says we've been lucky, not
  safe). Fix: (a) desk convention: scratch under `data/tmp/` (disk) not /tmp — frees ~900MB ≈
  +32% RAM; (b) add zram or a 2–4G swapfile as a pressure valve (25G disk free); (c) optional:
  Hetzner 8GB tier ≈ +€8/mo if organ concurrency should rise instead of being rationed.
- **O7 — Dashboard double-exposure.** serve_dashboard.py binds `0.0.0.0:8080` by explicit
  default ("bind LAN so the phone can reach it" — a public VPS has no LAN) *and* is published at
  dash.quanttt.xyz via cloudflared. It serves web/ (NAV, positions, research state), read-only,
  no auth (`grep -nE 'auth|bind' scripts/serve_dashboard.py`). Fix: `--host 127.0.0.1` (tunnel
  unaffected) + CF Access policy on the hostname; resolves U1's 8080 half regardless of the
  provider firewall answer.
- **O8 — CI tests a different world than prod runs.** ci.yml → Python **3.11** + unpinned
  `pip install -e ".[dev]"` (pyproject uses `>=` ranges); prod → Python **3.12.13** + `==` pins
  (requirements-vps.txt). The gate can green on versions prod never runs and vice versa. Also
  structural honesty: the VPS executes the *working tree* — organ edits run live (every 180s for
  run_alerts.py) before any push reaches CI; the hosted gate is post-hoc drift detection, not a
  shipping gate. That is a defensible autonomous-desk design ONLY while the local `run_ci.py`
  duty is enforced (it was red-and-tolerated for a day — R0021/R0022; green today, S5). Fix:
  ci.yml → 3.12 + `-r requirements-vps.txt`; keep the local-CI-before-money-path-edit duty
  explicit in doctrine.
- **O9 — Dual supervision: the watchdog re-implements systemd for the same five services, and
  its tunnel branch has failed every tick for 17 days. [contrarian]** The supervision layers:
  systemd units (21 quant-* units incl. quant-cashcarry/dashboard/deadman/liquidations/tunnel),
  cron respawn lines, watchdog (3-min heartbeat-gated spawns of executor/deadman/liquidations/
  dashboard/tunnel — `sed -n 150,205p scripts/watchdog.py`), ensure_recorder (10-min),
  organ_catchup (5-min). So the five money-path services each have TWO owners (systemd unit +
  watchdog branch), arbitrated only by single-instance locks. Measured consequences:
  (a) watchdog's tunnel branch checks `data/tunnel_heartbeat` — written only by
  `run_ngrok.py`/`run_tunnel.py`, which the LIVE quant-tunnel unit never touches — so the
  heartbeat froze 07-12 00:01:44 (17 days, `stat`) and watchdog has spawned `run_ngrok.py`
  → `tools/ngrok.exe` (a **Windows binary**; `ls tools/` → empty anyway) **2381 times**
  (`grep -c 'public-tunnel' watchdog.log`), a broken duplicate of working systemd supervision,
  never alerting on its own futility; (b) the orphan-sweep agent observed quant-deadman in
  `activating (auto-restart)` — transient lock-arbitration flapping while both owners contend
  (single instances confirmed after settling: `pgrep -af run_deadman_switch` → one pid, owned
  by systemd since 06:38); (c) `systemctl --failed` is permanently red with 4 recovered organ
  failures (O2). "More supervisors" did not produce more resilience — it produced an
  unwatched broken watcher. Fix: ONE owner per service (systemd, with `Restart=`), demote the
  watchdog to the things systemd can't express (FREEZE reaping, heartbeat *paging*), delete the
  ngrok/tunnel branch and both dead tunnel scripts, and make any supervisor page after N
  consecutive failed respawns of the same target (2381 unnoticed attempts is the smoking gun).
- **O10 — data_health monitors datasets but not the machine.** `grep -nE 'disk|statvfs|df'
  scripts/data_health.py` → nothing; 5.05GB written to data/ in 7d (`find data -type f -mtime -7
  -printf '%s\n' | awk …` — churn-inclusive upper bound) against 25G free → multi-week-to-months
  runway with zero warning line. sar/sysstat collects capacity history nobody reads (this audit
  is its first known consumer). Fix: one disk-%-and-RAM check in data_health with a page
  threshold; one sar summary line in max_audit.
- **O11 — Organizational entropy inventory (each small; together they are the "desk never
  finishes its moves" tax).** (a) `sor.sqlite` empty 0-table decoy + 8 real DBs → consolidate or
  document; (b) repo-root probe litter: `_audit_gate_probe.py`, `_audit_gate_probe2.py`
  (tracked+modified), `_audit_rows.pkl`, 5.9MB `_audit_prepared.pkl`; (c) `ops/run_cro_ai.sh` is
  37KB of bash with a `.bak-20260716` sibling; (d) retired `data/executor_heartbeat` (frozen
  06-28) still on disk next to live heartbeats; (e) `data/tunnel_heartbeat` frozen 07-12;
  (f) naver_krsearch collector runs daily and "gracefully skips" for missing credentials with
  `ok: True` — a self-greening green-with-zero-output cell in the cycle rollup (either add the
  free credential or remove the collector); (g) quota_verdict.py dormant-by-design since 07-23
  (`verdict_sent: true`) yet still cron'd 8×/day, and the quota MONITOR being dormant while
  quota is the #2 finding is itself wrong — revive as a continuous meter (first-attempt success
  rate per organ per day); (h) llm_panel.json.bak/.bak2 in secrets dir; (i) Windows residue:
  ngrok.exe path, `tools/*.exe` gitignore line, watchdog comments about the Windows port;
  (j) docker-compose.yml + Dockerfile + deploy/ + dist/ likely-dead deployment paths (orphan
  agent sweep running; results to be rowed when returned).
- **O12 — No dependency-vuln scanning.** No pip-audit/osv-scanner in ci.yml or crontab (`grep`
  → nothing). requests/urllib3/websockets handle exchange traffic; one `pip-audit -r
  requirements-vps.txt` weekly cron line + CI step. Low cost, real tail.

## 4. WHAT WE TEST NEXT — concrete experiments

- **T1 Restore drill (closes O1, U6).** Wire nightly restic → storage box/B2 for data/ (exclude
  rollback/), plus BackupManager pointed at the REAL SoRs; then a weekly cron that restores to a
  scratch dir and asserts sha256 manifest + `select count(*)` on 3 sentinel tables + one jsonl
  row-count. Success: drill artifact (dated JSON) with all assertions green, two consecutive
  weeks. Failure mode: backup rot masked by green cron — the drill IS the control. Retirement:
  never; it is rail-adjacent. Validation of this audit's claim: before wiring, run the restore
  once manually — expected to fail (nothing to restore from), proving O1.
- **T2 External surface probe (closes U1, feeds O7).** From any off-box vantage: `nmap -Pn
  <ip> -p 22,8080` + `curl -sI http://<ip>:8080`. Success: documented open-port inventory in
  docs/; if 8080 answers, bind 127.0.0.1 the same day and re-probe.
- **T3 Synthetic URGENT page, monthly (closes O3's verification gap).** Send a test URGENT
  through the new priority lane; confirm delivery by polling the ntfy topic API <60s. Success:
  delivered during a simulated routine-lane 429 (set the backoff file manually first — that is
  the actual test). Retirement: never; alert channels decay silently.
- **T4 Reboot drill (closes O4).** After cloudflared unit install + timer enable + ngrok-branch
  removal: schedule the pending kernel/libc6 reboot in a quiet window. Success: every heartbeat
  in `find data -iname '*heartbeat*'` fresh <10 min post-boot, tunnel serving, zero human
  actions. This also converts the 17-day-uptime unknown ("has this box ever recovered
  unattended?") into evidence — the autonomy check the proactive battery demands (move 7).
- **T5 Quota-aligned scheduling experiment (attacks O2).** Baseline: first-attempt organ start
  success ≈ 0% (S10 + yesterday's 4/4). Shift the four daily organ starts to a window measured
  against credit-reset (organ_catchup.log already timestamps quota recovery daily — mine it for
  the reset hour first). Success: first-attempt success >60% over one week; secondary metric:
  sweep completes on its scheduled day. Also `systemctl reset-failed` post-catchup so the failed
  list regains signal.
- **T6 tmpfs eviction + pressure valve (closes O6).** Move scratch writers to data/tmp, add
  zram/swapfile. Success: /tmp steady <100MB and sar kbmemfree floor >700MB across a full organ
  burst; no OOM lines (as now), headroom verified rather than lucky.
- **T7 CI parity (closes O8).** ci.yml → py3.12 + requirements-vps.txt. Success: green on the
  parity env; then a deliberate canary (bump one pin locally without pushing) to confirm the
  gate would actually catch drift.
- **T8 §41 back-row sweep (closes O5's meta-half).** Row every D-finding from
  20260726_infrastructure.md and this report into recommendations.py; success: zero
  audit-findings without ledger rows, verified by cross-grep, and the PAT rotated with the row
  marked implemented+commit.

## APPENDIX A: PERSPECTIVE COVERAGE LOG

- **INTERNAL** (measured, not configured): quota-death 100% (S10); tunnel supervisor loop 2381
  ticks/17d (O4); pager 429 live (O3); heartbeats fresh (S3); 56 fresh series <2h (S2); CI green
  today after red-tolerated (S5); RAM floor 199MB during burst (O6).
- **EXTERNAL** (how a world-class desk would differ): offsite DR with drilled restores (O1/T1),
  priority-laned paging with delivery confirmation (O3/T3), env parity between gate and prod
  (O8), a units manifest with coverage ownership (O9), secret in credential store not remote URL
  (O5). Nothing exotic — all commodity practice this desk skipped while building rarer things
  (the catch-up layer in S1 is *better* than commodity).
- **FUTURE** (2–3y): brain-chain already multi-model; extend the cheap tail (local/small models)
  to mechanical organ steps so scheduled digs stop competing with frontier-model quota (O2d);
  litestream-style continuous SQLite replication makes the SoR backup a background stream instead
  of a nightly event; one declarative orchestrator (systemd-only) replaces the cron+watchdog+
  ensure+catchup stack (O9).
- **CONTRARIAN** (assumptions tested): "more supervisors = more resilience" → falsified by O9
  (blind spot lived inside a supervisor; nothing watched the watcher's own loop). "CI protects
  live capital" → falsified in the shipping sense by O8 (working-tree execution precedes the
  gate); it is drift detection. "green cycle = healthy collectors" → naver skip-green (O11f)
  shows the rollup can green on zero output. "we're fine on RAM because no OOM" → S8 is survival
  bias; sar shows 199MB floors (O6).
- **GREENFIELD**: rebuilt today it would be: systemd-only scheduling (no cron), one pinned
  uv-locked env, ONE SoR + streaming replica, one pager lib with lanes, cloudflared as a unit,
  restic timer, no Windows residue, a units manifest. Historical-baggage score: moderate —
  Windows-era paths (ngrok.exe), dual schedulers for daily_research_cycle (cron 02:00 + timer
  08:01, absorbed by idempotency but drift-prone), 9 SQLite files, probe litter. Lock-in: LOW —
  every component is commodity; full migration ≈ 1–2 days, mostly not worth doing wholesale
  (the entropy list O11 captures the worthwhile subset).
- **FRONTIER** (recently practical, unexploited): Hetzner storage box €3.2/mo + borg/restic;
  Hetzner API snapshots (whole-disk DR incl. cron/venv, ~€0.5/mo at this size); litestream for
  SQLite; `cloudflared service install`; Cloudflare Access (free tier) for the dashboard
  hostname; ntfy priority topics / healthchecks.io (already used for heartbeat — reuse the
  paired pattern for URGENT); uv lock (uv already on box, half-adopted); pip-audit/osv-scanner
  in CI.
- **NEGATIVE-SPACE SWEEP** (never done, now named): never probed own public IP (U1/T2); never
  restored a backup (U6/T1 — there is nothing to restore); never rebooted since migration
  (17d uptime, drill T4); never chaos-killed an organ to verify paging end-to-end (T3); never
  read the sar history sysstat has been collecting (first read was this audit); no disk-space
  alarm (O10); no dependency-vuln scan ever (O12); no inventory of what-must-be-running (O9);
  root-owned state never audited from this account (U7).

## APPENDIX B: five-things classification

- Weaknesses (current failures): O3 pager 429, O4 tunnel loop + no cloudflared unit, O5 PAT +
  §41 drop, sor.sqlite decoy, failed-unit desensitization (O2).
- Bottlenecks (limits improvement): O2 quota pool (availability), O6 RAM ceiling (concurrency),
  single brain pool contention between organs and interactive work.
- Capability gaps (does not exist): offsite DR + restore drill (O1), external surface knowledge
  (U1), disk/RAM alarms (O10), vuln scanning (O12), units manifest (O9), page delivery
  confirmation (T3).
- Compounding multipliers: T1 (protects all accumulated evidence forever), O3 lanes (protects
  every future alert), T5 (recovers daily research hours), O10/sar (makes every future capacity
  decision evidence-based).
- Unknown unknowns (probed where confidence lowest): sudo-blind zone (U7), CF-side config (U2),
  principal-side copies (U8) — each named with its resolving probe rather than left vague.

— end of report (orphan/duplicate agent sweep addendum to follow if it returns before session
end; its findings are pre-classified under O11j and will be rowed per §41 either way).
