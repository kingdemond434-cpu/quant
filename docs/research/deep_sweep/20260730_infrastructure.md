# DEEP COLD AUDIT — INFRASTRUCTURE — 2026-07-30

Auditor: weekly deep cold audit (v2 doctrine + 2026-07-28 exhaustion mandate), subsystem =
infrastructure. READ-ONLY. Every claim carries its proving command.

This file previously held a `BRAIN_AUTH_FAILED` stub (489 bytes, committed in `9dddc49`); this is
the resume run. **Yesterday's sweep (`20260729_infrastructure.md`, 29KB, O1–O12 + T1–T8) is the
baseline: this audit's first duty is OUTCOME verification of those findings — what was actually
FIXED in 24h, not what was recommended — then one layer past where that report stopped.**

_Status: IN PROGRESS — findings appended as verified. Skeleton written first per the completion
contract._

## SCORES

- **current_capability_pct: 48** (yesterday: 62). **This is a measurement change, not a regression** —
  and saying so matters, because the honest reading is that last week's 62 was too generous. Nothing
  found today broke in the last 24 h; the public source-bundle exposure has been live since ~07-12,
  the Holm-bar fail-open path has been there since the slot registry was written, the sweep organ has
  been in a retry loop for a week. What is genuinely strong: data integrity (S2, 16,940 files
  verified), clock discipline (S1, sub-ms), collector breadth (S4, 326 fresh series), cron delivery
  (S5, 288/288 × 3 days), and the fact that **every fix in this report is a wiring job on a primitive
  that already exists** (S8).
- **practical_ceiling_estimate: 90** for a single-VPS autonomous desk. Residual single-box and
  single-vendor-quota risk is irreducible without a second node.
- **ceiling_gap: 42 points** — of which roughly 30 are purchasable for **under $5/month plus ~3 days
  of wiring** (bundle removal + bind + CF Access; one `artifacts=` tuple; `concurrent_m()` fail-closed;
  disk alarm; restic + drill; pager lanes + topic rotation; ledger wire), and ~8 more require only two
  root actions the desk cannot perform itself (journal group membership, a read-only provider token).
- **opportunity_cost_1y, ranked by expectation:** (1) **I1 — unbounded and undetectable.** The
  constitution names the transformation pipeline as the *only* durable moat; it is downloadable now,
  and a silent read leaves no trace, so the loss can never be measured — only prevented. (2) **I12 —
  a loosened Holm bar is the one failure that costs *negative* discovery**: it promotes a phantom
  edge to real capital, which the doctrine ranks worse than finding nothing. (3) **I11 — a forced
  outage in ~32 days** that simultaneously truncates non-atomic state; this is the only item with a
  date. (4) **I13/I14 — measurable and immediate:** ~9 redundant 8-auditor sweeps per week plus
  ~610 dead-pool probes, spent from the pool whose starvation is the desk's stated availability
  floor; this is discovery-rate lost to a one-line bug. (5) **I2 — P(disk/VM loss) ≈ 2–5%/yr × the
  entire forward-evidence record**, whose accumulation the desk's own cycle names as the binding
  constraint. (6) **I5/I6/I7/I25 — the alerting rail**, where the tail is small in probability and
  unbounded in consequence, and where I25 makes the tail *attacker-selectable*.
- **confidence: 0.9** on the findings (every claim carries its command; the load-bearing ones —
  I1's HTTP 200s, I5's dead `_ERR`, I12's `concurrent_m()`, I13's `OrganSpec`, I17's zero
  dereferences, I18's inert-vs-active contradiction — I re-verified personally rather than accepting
  a delegated result). **0.65** on the ranking between I2/I11/I12, which trade off differently
  depending on whether the next adverse event is a disk, a crash, or a promotion.
- **unknown_unknown_score: 0.45** (yesterday 0.5). Down slightly because the two biggest blind layers
  are now *named with a closing probe* rather than vaguely feared (journal → T11, provider → T12).
  Still substantial because the 73-swallowed-exception seam yielded three genuine defects on first
  contact, which strongly suggests it is not exhausted.
- **info_gain_if_investigated: very high for two cheap actions** — journal group membership (T11)
  converts an entire unread diagnostic stream, and a read-only provider token (T12) converts every
  backup/firewall claim from hearsay to measurement. Both are minutes of work and neither is
  performable by the desk.
- **expected_alpha_contribution:** indirect but first-order, through two channels the constitution
  ranks highly — **bar integrity** (I12/I19: a wrong statistic or a loose bar corrupts every
  promotion decision) and **discovery rate** (I13/I14/I15: quota reclaimed and starved organs made
  retryable is directly more hypotheses per week).
- **expected_compounding_contribution: high.** I4 (mechanised rowing) multiplies every future audit;
  T11 (journal) multiplies every future diagnosis; I16a (7-day retention) makes the *next* audit
  strictly better-informed than this one; I19 (one statistic) makes every future screen comparable.
- **CEILING EXPANSION — the assumption that most artificially lowers the ceiling is not technological,
  and it is new to this report.** Last week's answer was "one VPS, one vendor quota pool". The deeper
  one is the **privilege boundary**: the desk cannot enable a timer, clear a failed unit, set an OOM
  priority, reboot, or *read its own services' logs* (I15/I16b). That boundary has silently shaped
  the architecture — cron accreted 21 lines duplicating units nobody can touch — and it caps
  self-healing at "whatever can be done from a working tree". It is lifted by **one group membership
  and one API token**, i.e. two minutes of principal time, not a purchase or a rebuild. Until then,
  every "the desk should self-heal X" recommendation is measuring against a ceiling that a `usermod`
  would raise. Second constraint, unchanged: the 40-hour log horizon (I16a) means the desk's own
  history is shorter than its audit cadence — a ceiling on *learning*, not on capability.

## 0. CARRY-OVER VERIFICATION — what happened to yesterday's O1–O12 / T1–T8

The doctrine's outcome-not-config rule applied to the audit organ itself. Yesterday's report
carried 12 ranked opportunities and 8 named experiments. **24 hours later: 0 of 12 fixed, 0 of 8
run, 0 of 20 entered the tracking ledger.** Each line below is re-verified today, not copied.

| # | yesterday's claim | state today | proving command |
|---|---|---|---|
| O1 | DR absent, 7GB single-copy | **STILL ABSENT** — no backup tool, no cron line, `libs/ops/backup.py` still has exactly one importer (its own package `__init__`) | `grep -riEl 'rclone\|restic\|borg\|duplicity\|aws s3' scripts/ ops/ libs/` → *(empty)*; `crontab -l \| grep -iE 'backup\|restic\|rclone\|snapshot'` → `NONE`; `grep -rn 'BackupManager' scripts/ libs/` → `libs/ops/__init__.py:10` only; `find data -iname '*restore*' -o -iname '*backup*' \| grep -v rollback` → *(empty)* |
| O2 | quota starvation, ~0% first-attempt | **STILL LIVE** — `auth_broken` is in the currently-paged set as of 00:52 today | `python -c` on `data/.last_alerts.json` → `"_paged": [auth_broken, cadence_floor_violation, growth_defect, principal_action_needed, trade_class_bleeding]`; `auth_broken 2026-07-30T00:52:31 age=6.9h` |
| O3 | pager 429, 7 ntfy impls | **WORSE THAN MEASURED** — 12 files carry their own ntfy push, incl. 2 `.bak-*` copies | `grep -rln 'ntfy' scripts/ libs/ \| wc -l` → `12` |
| O4 | reboot pending, never rebooted | **STILL PENDING**, now 18 days uptime; running kernel is `7.0.0-15` while the patched image is installed | `ls -la /var/run/reboot-required*` → present, `Jul 29 06:36`; `uname -r` → `7.0.0-15-generic`; `uptime -s` → `2026-07-11 23:49:15` |
| O5 | PAT in remote URL, 8 days old | **STILL PRESENT**, and `.git/config` is still group/world-readable | `git remote -v` → `https://ghp_…@github.com/kingdemond434-cpu/quant.git`; `ls -la .git/config` → `-rw-rw-r--` |
| O6 | /tmp 904M on swapless 3.7GB box | **GREW to 1009M**; free RAM 355MB, still zero swap | `df -h -t tmpfs` → `/tmp 1.9G 1009M 53%`; `free -m` → `free 355`; `swapon --show` → *(empty)* |
| O7 | dashboard 0.0.0.0 + no auth (CF-side unknown, U2) | **CONFIRMED AT THE WORST CASE — see I1, the top finding of this audit** | `ss -tlnp` → `0.0.0.0:8080`; external GET → HTTP 200 unauthenticated |
| O8 | CI tests py3.11, prod runs 3.12 | unchanged (agent-verified below) | `.github/workflows/ci.yml` |
| O9 | watchdog ngrok loop, 2381 futile spawns | unchanged direction (agent-verified below) | see §3 |
| O10 | no disk/RAM alarm | **STILL NONE** | `grep -nE 'disk\|statvfs\|df' scripts/data_health.py` → *(empty)* |
| O11 | entropy inventory | probe litter still in repo root: `_audit_gate_probe.py`, `_audit_gate_probe2.py`, `_audit_rows.pkl`, 5.9MB `_audit_prepared.pkl`; `llm_panel.json.bak`/`.bak2` still in the secrets dir | `ls -la` root; `ls -la data/secrets/` |
| O12 | no dependency-vuln scanning | **STILL NONE** | `grep -rn 'pip-audit\|osv-scanner\|safety' .github/ ops/ pyproject.toml` → only unrelated word-matches (`"safety"` in `capacity_simulator.py`) |
| T1–T8 | 8 experiments | **none run**: no backup to restore (T1), no port-probe artifact in docs (T2), no synthetic URGENT page log (T3), no reboot (T4), no schedule change (T5), /tmp grew instead of shrinking (T6), ci.yml unchanged (T7), zero ledger rows (T8) | as above + §I4 |

**The carry-over verdict is itself the finding (I4): this is the second consecutive week the
infrastructure sweep produced a detailed report that changed nothing on disk.** The 07-26 sweep's
D4 (PAT) and the 07-29 sweep's O1–O12 both went nowhere. The mechanism of that failure is
identified below and it is not laziness — it is a missing wire between this organ and the only
ledger that drives work.

## 1. WHAT WE KNOW — validated strengths (each with proving command)

Only outcomes, measured today. Where a parallel probe supplied a number, I re-ran it myself before
listing it here.

- **S1 The clock is excellent, and this is load-bearing rather than cosmetic.** `chronyc tracking`
  → `System time 0.000464 s fast of NTP time`, `RMS offset 0.000522 s`, stratum 3, NTS-authenticated
  Canonical sources; `timedatectl` → `System clock synchronized: yes`, `NTP service: active`,
  `Etc/UTC`, RTC in UTC. Sub-millisecond discipline is exactly what the SCREEN-ON-DISCOVERY duty's
  timestamp-alignment requirement depends on — **no screen result on this box is at risk from clock
  skew.** That closes a failure mode nobody had checked.
- **S2 The data on disk is intact — verified, not assumed.** `PRAGMA integrity_check` → `ok` on all
  10 SQLite DBs; every `-wal` file 0 bytes and no stray `-journal` (checkpointing works); `find
  data/moat -name '*.gz' | xargs -P4 gzip -t` → **16,940 files, 0 failures**; the 8 largest
  `data/*.jsonl` plus all 278 `data/lake/**/*.jsonl` (438,561 lines) → 0 unparseable lines, 0
  truncated final lines, 0 duplicate records once the identity key is correct. **No collector has an
  idempotency bug and no tape file is truncated.** This is the strongest result in the report.
- **S3 The money path is alive to the second.** `date -u` → 08:02:49; heartbeats:
  `cashcarry_exec 08:02:13`, `deadman 08:02:23`, `liquidation 08:02:42`, `recorder 08:02:43`,
  `recorder_spot 08:02:40`, `recorder_bybit 08:02:08`. `ls data/DEADMAN_FIRED data/FREEZE` → absent
  (no latch, no kill-file), which is the correct state.
- **S4 Collector breadth is real and much larger than last week's measurement.**
  `find data -name '*.jsonl*' -mmin -120 | wc -l` → **326 files fresh inside 2 hours** (yesterday's
  report measured 56 — the difference is the `.gz` tape now included; either way the acquisition
  layer is not the bottleneck).
- **S5 Cron delivery itself is 100%.** `organ_catchup` logged exactly 288/288 expected `*/5` ticks
  on each of 07-27, 07-28 and 07-29. **The scheduler is not the problem** — every availability
  finding in this report is about what the ticks then fail to do, which is a much more useful
  conclusion than "cron is flaky".
- **S6 The dual-ownership guard works — for the four services it covers.** `_systemd_owns()` in
  `scripts/watchdog.py:53-58` maps four scripts to their units and declines to spawn duplicates (9
  log lines prove it firing). Single instances confirmed: `pgrep -af run_recorder` → 3 distinct
  recorders, one each. **Nothing on the box runs unsupervised:** all 15 live python processes
  reconcile to an owner (4 systemd `Restart=always` daemons, 3 cron-respawned recorders, the tunnel
  unit, the sweep, 3 system procs, 2 transient agent shells). The tunnel branch is the sole
  omission (I23/O9).
- **S7 The security baseline is right where the desk controls it.** `PasswordAuthentication no`,
  `PubkeyAuthentication yes`, exactly 1 authorized key (`wc -l ~/.ssh/authorized_keys` → 1),
  `systemctl is-active fail2ban` → `active`, `20auto-upgrades` → `1/1`, all live secrets mode `600`.
  The GitHub repo is **private** (unauthenticated API → `HTTP 404`), the source bundle is **not**
  tracked in git, and the bundle contains **no live credential** (key-shaped grep returned only
  hyphenation artifacts like `sk-parit` from "risk-parity"). The failure in I1 is a *publishing*
  defect, not a credential-hygiene defect.
- **S8 The correct primitives exist — they are just under-applied.** `libs/store/connection.py:17-26`
  sets `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, and **all nine writers that
  use it are clean** (0 raw connects). `os.replace` atomicity is applied to precisely the two most
  survival-critical writers: `scripts/run_deadman_switch.py:62` (the Tier-3 rail) and
  `libs/execution/ea_bridge.py:46`. `libs/ops/backup.py` implements online backup + sha256 manifest
  + `RestoreDrill` correctly. **Every fix in §3 is a wiring job, not a build.** That is the single
  most encouraging fact in this audit.
- **S9 The catch-up layer's concurrency control genuinely works.** 85 logged holds of the form
  "field busy (brain running) -- holding retries so they do not share the window", and it really
  does produce artifacts (this report is one). Its defects (I13/I14/I15) are all at the *entry* and
  *exit* conditions, never in the serialisation itself.
- **S10 Change-rollback exists and is exercised on every code change.** `ls data/rollback/` → 20
  timestamped full-tree snapshots, newest `20260730T070521_slot-cohort-truth` (this morning).
  Same-disk, so it is change-rollback and not DR (I2), but it is real and current.
- **S11 Environment reproducibility is pinned.** `requirements-vps.txt` exact `==` pins, Python
  3.12.13, `.venv` 704 MB. `pip list --outdated` returned nothing actionable in the window checked.
- **S12 Log volume is a non-problem, and that deserves saying plainly.**
  `find . -name '*.log' -not -path '*/.venv/*' -printf '%s\n' | awk '{s+=$1}END{print s}'` →
  **675,998 bytes total across 50 files**; nothing >1 MB written in 24 h; `journalctl --disk-usage`
  bounded. There is **no** log-rotation configuration anywhere (`grep -rn 'RotatingFileHandler|logrotate'`
  → 0 hits, `/etc/logrotate.d` has no quant entry) — unbounded *by design* but immaterial at this
  scale. **The real cost of the logs is signal-to-noise (I23, 95% of `watchdog.log` is one repeated
  line), not bytes.** Recording this as a strength prevents a future sweep from "fixing" the wrong
  thing.

## 2. WHAT WE DON'T KNOW — ignorance ledger

Known-unknowns first, each with the probe that would close it. Suspected unknown-unknowns last.

- **U1 Whether `0.0.0.0:8080` is reachable on the raw public IP** (as distinct from through the
  tunnel, which I1 proved wide open). No sudo → `ufw`/provider-firewall invisible; a probe from
  *this* box would succeed regardless of any firewall and prove nothing. **Needs one off-box
  `nmap -Pn <ip> -p 22,8080`.** Note that I1's fix (`--host 127.0.0.1`) closes this branch whatever
  the answer is, which is why it should not wait for the probe.
- **U2 RESOLVED THIS SWEEP, to the worst case.** `dash.quanttt.xyz` has no authentication and serves
  the full source bundle (I1).
- **U3 GitHub Actions pass/fail history** — `which gh` → absent; the hosted gate's record is
  unverifiable from the box. Local evidence says the *scheduled* gate is 7/7 red (I10).
- **U4 The PAT's scope and expiry** — not introspected (that would mean exercising the credential in
  a read-only audit). It is a classic `ghp_` token in a `.git/config` readable by every process
  (I0/O5). One `curl -I -H "Authorization: token …" https://api.github.com` answers it; rotating it
  makes the question moot, which is the better move.
- **U5 Whether Hetzner backups exist at all.** GAP #13 asserts they were enabled on 07-16; nothing on
  the box can confirm or refute it (I2). **Closable in 60 seconds with a read-only Hetzner API token
  and `GET /v1/images?type=backup&bound_to=149983008`** — the instance ID is already known from the
  metadata service. Until then, DR must be planned as if the answer is "no".
- **U6 Whether the healthchecks.io check is actually receiving pings.** Deliberately not tested: a
  probe ping would register a heartbeat and destroy the evidence of the outage being investigated
  (I3). Closable with a healthchecks.io read API key (free) — the *right* form of the test, because
  it verifies from the outside in.
- **U7 Whether any silent SQLite write loss has already happened.** A clean grep for `database is
  locked` across every log is **not** evidence (I22): the read path converts `OperationalError` into
  an empty result, 73 `except Exception: pass|continue` sites swallow the rest, and 5 cron lines
  discard stderr. **The detector does not exist**, so this stays open by construction until a
  lock/error counter is added. This is the most uncomfortable unknown in the ledger — the desk cannot
  currently distinguish "no contention" from "contention that was silently absorbed".
- **U8 Whether the Sunday-04:00 cron has ever executed.** The missing `deep_sweep.log` says no (I8),
  but `/var/spool/cron/crontabs/quant` is unreadable and `journalctl -u cron` returns "No entries"
  without group membership (I15). **Closable by observation on 2026-08-02**, or instantly with
  journal access.
- **U9 Full test-suite runtime, pass/fail count, and money-path coverage.** Yesterday's U9 remains
  open at the time of writing: collection alone exceeded 100 s in two attempts, and the scheduled
  gate times out at 300 s (I10). A measurement was running in parallel with this sweep and had not
  returned when the report was finalised — **named as unresolved rather than guessed**, because "the
  suite is fine" is exactly the assumption I10 falsifies.
- **U10 Root-owned state**: root crontab, the cause of the 3-day-old `user@0.service` failure,
  provider-level config. Sudo-blind. Note the *new* fact that sharpens this: the desk is not even in
  `systemd-journal`, so it cannot read its own units' failure output (I15) — the ignorance is
  structural, not incidental.
- **U11 Off-box copies held by the principal.** GAP #13 mentions "laptop copy is frozen at 07-12",
  which is the only attestation and is 18 days stale. DR math in I2 assumes zero.
- **U12 Re-obtainability of `data/moat` (6.1 GB) and `data/lake` (1.5 GB) if lost.** No per-dataset
  provenance/re-fetchability record was found; FREE-FRONTIER doctrine says sources decay. Treat as
  partly irreplaceable.
- **U13 Whether the ntfy topic has already been subscribed to by anyone else.** Unknowable by
  construction on an unauthenticated topic — see I25 for why that matters more than it sounds.
- **Suspected unknown-unknowns (where confidence is lowest, probed deliberately):** (a) the
  **provider/console layer** — every claim about backups, firewall and snapshots is hearsay from
  inside the guest, and one API token converts the whole layer from faith to measurement; (b) the
  **journal layer** — an entire stream of failure diagnostics exists on this machine that no desk
  organ has ever read; (c) **whatever the 73 swallowed exceptions have been hiding** — this sweep
  found three genuine defects (I12 fail-open, I22 locked-as-empty, I17 discarded gate) purely by
  reading code around silent `except` clauses, which suggests the seam is not exhausted.

## 3. WHAT COULD MATTER MOST — ranked opportunities

Ranked by expected impact × confidence / (cost × maintenance). **CM** = compounding multiplier;
**P** = principal-required (I16b). Cost is engineering time unless stated.

| # | finding | cost | why it ranks here |
|---|---|---|---|
| **I1** | 552-file source bundle + live P&L served unauthenticated to the internet | ~30 min | the only item whose loss is *unbounded and undetectable*; it is the constitutional moat, downloadable now |
| **I13** | sweep organ can never be marked done → 10 re-fires for 1 run | **1 tuple** | best ROI on the board: one line recovers the quota that every starved organ needs · **CM** |
| **I12** | Holm bar fails open when a state file is unreadable | ~3 lines | the only multiplicity control on the only path to capital; a phantom edge is *negative* discovery |
| **I11** | disk full in ~32 days + 324 non-atomic writes that truncate on full | ~1 h + policy | the only finding with a **date**; failure mode is silent state truncation, not a clean outage |
| **I4** | infra sweep has never rowed a finding — 2 weeks, ~32 recommendations | ~30 lines | multiplies every future audit; explains §0's 0/12 · **CM** |
| **I5** | delta-neutral invariant log: single-slot, side-less, read by nothing | ~5 lines | money path; fired 17 min before this audit and nobody would have known |
| **I2** | DR marked `resolved` in the register, absent in reality | ~2 h (+€3/mo) | a *false green* immunises the item against every future sweep · **P** for the token |
| **I6** | watchdog can crash before reaching the pager, and has | ~2 lines | ruin-rail adjacency; re-arms a documented 11.5-day pager silence |
| **I7** | pager delivers 16.5% of conditions; ~49% of delivered pages permanently false | ~1 line + lanes | trains the reader to ignore the channel that carries ruin alarms |
| **I25** | guessable public alert topic ⇒ third party can read pages *and* mute the rail | ~5 min | converts an availability nuisance into an attacker-controlled kill switch |
| **I15** | starved organs invisible to retry; desk cannot read its own journals | ~4 lines · **P** | observability floor; `usermod -aG systemd-journal` is the highest-leverage root action |
| **I17** | §33 conversion gate computed by 5 organs, result discarded (0 uses) | ~5 lines | a governance law that is a literal no-op while the code asserts it fires |
| **I19** | 8 divergent Spearman/IC impls; `0.0` conflates "not measured" with "no edge" | ~1 h | bad negatives poison the graveyard and burn multiplicity budget · **CM** |
| **I16a** | 40-hour log horizon (count-based prune over a shared dir) | ~2 lines | the desk's memory is shorter than its audit cadence · **CM** |
| **I10** | certification gate 7/7 failed, 5 by timeout; cycle proceeds | ~2 h | a gate that always fails carries zero information (GATE-OPTIMALITY duty) |
| **I18** | running service classified `INERT`, withheld from 13 external seats | ~1 h | this is *how* I1 escaped external review |
| **I20** | zero resource limits / OOM priority, swapless, 153 MB floor | ~15 min · **P** | the correct OOM victim order is currently an accident of RSS |
| **I14** | 4th unlocked brain spawner racing the catch-up layer | ~1 glob | self-inflicted quota starvation |
| **I21** | 3 unsynchronised writers on the only human-escalation channel | ~30 min | a clobber here already destroyed 4 days of principal pages |
| **I22** | `busy_timeout` in one file; lock errors render as "honest empty" | ~1 h | makes silent write loss undetectable by construction (U7) |
| **I8** | two weekly cadences have never fired from their primary scheduler | ~15 min | the fallback is the real scheduler and nobody knew |
| **I23** | one alarm surface, both failure modes (daily reds + a unit that can't fail) | ~10 min | alarm desensitisation on the desk's only unit-level surface |
| **I9** | quota meter has written 0 bytes in ~11 runs | ~1 h | the metric behind a billing decision is frozen 7 days stale |
| **I3** | both independent alert paths fail silently (no logging at all) | ~3 lines | the remedies for two documented silent deaths reproduce the property |
| **I24** | measured entropy: 25 orphans, dead stratum, 11 prompt copies of the Holm bar | ~1 day | the Holm bar in 11 hand-synced copies is a bar that will drift again |
| **I16b** | the privilege boundary itself | 2 min · **P** | not a defect — the *frame*; it invalidated half of yesterday's fix list |

### I1 — THE ENTIRE 552-FILE SOURCE BUNDLE AND LIVE P&L ARE PUBLISHED TO THE OPEN INTERNET, UNAUTHENTICATED. [severity: TOP — moat + security + L1.11]

Yesterday's O7 called this "dashboard double-exposure … serves web/ (NAV, positions, research
state), read-only, no auth" and left the decisive question in the ignorance ledger as U2 ("whether
dash.quanttt.xyz has Cloudflare Access in front"). **U2 resolves to: no, it does not — and the
exposed payload is far larger than positions.** Proven by GET from this box out through the public
Cloudflare edge (no credentials, no cookies):

```
$ curl -sS -o /dev/null -w 'index.html -> HTTP %{http_code}, %{size_download}b, ip=%{remote_ip}\n' https://dash.quanttt.xyz/
index.html -> HTTP 200, 54374b, ip=2606:4700:3033::6815:c8b

$ curl -sS -o /dev/null -w 'algo_complete.txt -> HTTP %{http_code}, %{size_download}b\n' https://dash.quanttt.xyz/algo_complete.txt
algo_complete.txt -> HTTP 200, 1976145b

$ curl -sS https://dash.quanttt.xyz/cashcarry_live.json
{ "updated": "2026-07-30T07:46:21.891363+00:00", "mode": "live-paper",
  "strategy": "delta-neutral cash-and-carry (long spot + short perp, positive funding)",
  "net_pnl": -1860.14, "funding_harvested": 113.04, "spot_realized_pnl": 2930.43,
  "fut_leg_net": -4790.57, "bleed_alert": true, "bleed_verdict": "BLEED: non-funding PnL …" …
```

What that 1,976,145-byte file is — read from disk:

```
$ head -c 200 web/algo_complete.txt
QUANT PLATFORM -- COMPLETE SOURCE BUNDLE (552 files)
Consolidated 2026-06-26T20:38:49.783568+00:00 from C:/Users/dell/quant-platform
Every Python module (libs + scripts + tests) in one file. Search '# FILE:' to jump.
```

**This is the moat itself.** L1.11 states the moat is the transformation pipeline, never the raw
dataset. The transformation pipeline — every module in `libs` and `scripts`, tests included — is
downloadable by anyone who resolves the hostname, and the hostname is discoverable in
certificate-transparency logs regardless of never being advertised. `web/algo_full.txt` (68KB, the
execution-pipeline-ordered core) is served alongside it.

The rest of the served payload, all `curl`-able, all fresh (mtimes today):

- `cashcarry_live.json` (07:46 today, rewritten every refresh tick) — live P&L, funding harvested,
  per-leg attribution, and the live `bleed_alert` verdict.
- `binance.json` — `"balance": 3891.48, "equity": 3869.92, "n_trades": 739, "win_rate": 0.372`.
- `capital_plan.json` — `"capital_usd": 3846.0, "leverage": 0.25, "capacity_usd": 2000000.0`.
- `axis_shadows.json` (07:07 today) — **the entire Stage-B forward cohort**: axis names, forward
  day counts, `holm_bar`, `m_concurrent: 12`. This is the desk's live candidate pipeline —
  precisely the "sustainable information advantage" that sits third in the L1.2 hierarchy.
- `crypto_portfolio.json`, `crypto_shadow.json`, `allocation.json` — sleeve names, per-sleeve
  Sharpes, gate pass/fail, concentration caps.
- `autodiscovery_crypto.json` — `cumulative_tested: 434, cumulative_survivors: 0` and the
  per-gate rejection counts, i.e. the desk's validation-bar internals.

Confirmed NOT leaked (checked, so the finding is scoped honestly, and this bounds the blast
radius): the GitHub repo is **private** — `curl https://api.github.com/repos/kingdemond434-cpu/quant`
unauthenticated → `HTTP 404 / "Not Found"`; the bundle is **not tracked in git** —
`git ls-files | grep -cE 'algo_complete|algo_full'` → `0`, and only 2 files under `web/` are
tracked at all; **no live credential is in the bundle** — `grep -ohE 'ghp_[A-Za-z0-9]{6}|sk-…|AKIA…|Bearer …'`
returned only hyphenation false-positives (`sk-parit` from "risk-parity", 17×; `sk-adjus` from
"risk-adjusted", 6×); **no directory listing** — `GET /` returns index.html, so enumeration needs
the filenames (which the source bundle supplies). What the bundle *does* hand an attacker is the
exact credential map: `grep -ohE 'data/secrets/[a-z_]+\.json' web/algo_complete.txt | sort | uniq -c`
→ `5 data/secrets/binance_testnet.json`, `4 …binance_spot_testnet.json`, `3 …netlify.json`.

- **Why it matters, in the desk's own terms:** (a) L1.11 moat — a competitor gets the whole
  pipeline for one HTTP GET; the constitution's stated *only* durable advantage is the thing being
  served. (b) L1.2 rank-3 information advantage — publishing the live forward cohort tells anyone
  watching which axes the desk believes in *before* promotion. (c) Security — the bundle is a
  free map for finding an exploitable path into a box that will hold live keys, and it names the
  key files by path. (d) Adversarial targeting — live position/PnL disclosure on a real book is
  exploitable directly.
- **Cost of NOT fixing, 1y:** unbounded and unmeasurable-by-design (you cannot detect a silent
  read). The moat's whole value is at risk for the price of a hostname lookup. Nothing else in
  this report has that property.
- **Fix (minutes, three independent layers, all free):** (1) `rm web/algo_complete.txt
  web/algo_full.txt` and stop `bundle_algo.py`/`bundle_all.py` writing into the served directory
  — a source bundle has no business in a web root; (2) `--host 127.0.0.1` in
  `scripts/serve_dashboard.py:47` (the tunnel is unaffected — cloudflared already connects to
  localhost, `ss -tlnp` → `127.0.0.1:20241`); (3) a Cloudflare Access policy (free tier) on
  `dash.quanttt.xyz`, or at minimum tunnel-level auth. Then re-probe: expect `HTTP 403`.
- **Failure mode of the fix:** breaking the principal's phone dashboard. Mitigation: CF Access
  with a one-click email OTP keeps phone access and costs nothing; verify with the same curl.
- **Validation:** the identical three `curl` commands must return 403/404 for the bundle and for
  `cashcarry_live.json` from an unauthenticated vantage. That check is 10 seconds; it belongs in
  `data_health` as a permanent regression test (an exposure that recurs silently is worse than
  one found once).
- **Monitoring / retirement:** never retire; add the unauthenticated-GET probe to the daily
  integrity watch so the *outcome* is asserted, not the config.
- **Interactions:** none with the survival rails; touches only the presentation layer.
- **Alternatives considered:** IP-allowlist at Cloudflare (fragile — the principal's phone IP
  roams); basic-auth at the origin (weaker, and cloudflared would need the header); leaving the
  bundle but removing the tunnel (fails — `0.0.0.0:8080` is still bound and the provider firewall
  remains unverified, U1). The three-layer fix above is strictly dominant.
- **Time-horizon:** 1w–3y — the leak is already live and has been since the tunnel was set up
  (`web/dashboard_url.json` dates the stable hostname to 2026-07-12; the bundle predates it,
  2026-06-26). Treat the pipeline as *already* compromised for threat-modelling purposes: assume
  read, and prioritise accordingly (the desk's edge must not depend on code secrecy alone).

### I2 — THE #1 INFRA RISK IS MARKED "RESOLVED" IN THE REGISTER AND ABSENT IN REALITY, AND THE PREMISE THAT KEPT IT THERE IS FALSE. [severity: HIGH — config-vs-outcome, on the evidence engine]

Yesterday's O1 said DR is absent. It is (verified again today, §0). But the *reason nobody acted*
is more interesting than the gap, and it is a new finding: the desk's own driving register already
says the problem is solved.

```
$ grep -n 'OFFSITE BACKUP' docs/GAP_REGISTER.md
221:| 13 | **NO OFFSITE BACKUP / disaster recovery** | … | HUMAN CHOICE (both cheap): (a) Hetzner
auto-backups (~€1/mo, one click in console), or (b) free private GitHub repo … RESOLVED
2026-07-16: operator enabled Hetzner auto-backups (console-side; **not verifiable from inside the
guest** -- operator should confirm the first snapshot appears in the Hetzner console within 24h).
… | operator+brain | 07-16 | resolved (verify first snapshot) |
```

Three separate defects stack in that one row:

1. **A status of `resolved (verify first snapshot)` has stood for 14 days with the verification
   never performed.** The row itself specifies a 24-hour verification deadline. No artifact
   anywhere records a snapshot: `find data -iname '*snapshot*' -o -iname '*backup*' | grep -v rollback`
   → *(empty)*. So the register asserts DR while holding, in the same sentence, the admission
   that nothing was checked. This is exactly the shape the 07-29 re-rank stamp says is now the
   thing to hunt — *"a channel reporting health while carrying nothing"* — applied to the highest-
   consequence row on the board.
2. **"Not verifiable from inside the guest" is a route failure recorded as a capability failure**
   — proactive-battery move 9 (SCOPE THE NEGATIVE RESULT), the exact error that once turned one
   blocked YouTube endpoint into "video is blocked". The guest is *not* blind to its provider:
   ```
   $ curl -s http://169.254.169.254/hetzner/v1/metadata | head -4
   instance-id: 149983008
   hostname: ubuntu-4gb-hel1-5
   region: eu-central
   availability-zone: hel1-dc2
   ```
   The metadata service answers, and the instance ID is known. Hetzner's public API exposes
   `GET /v1/servers/149983008` (→ `backup_window`, and whether the `backups` flag is set) and
   `GET /v1/images?type=backup&bound_to=149983008` (→ the actual snapshot list with dates).
   All that is missing is a **read-only API token** — free, one console click — which no secret on
   the box provides today (`grep -rli 'hetzner\|hcloud\|HCLOUD_TOKEN' data/secrets/` → *(empty)*;
   `which hcloud` → absent). With that token the check becomes a cron one-liner that pages when
   the newest backup image is older than N days. The desk chose to record DR as permanently
   unverifiable rather than spend one click, and then closed the row on that basis.
3. **Even if the provider snapshots exist, they are the wrong control for this desk and nobody
   said so.** Provider snapshots restore a *whole machine* on operator action in a console; they
   do not detect corruption, do not give per-file recovery of a truncated forward-clock series,
   and — critically — are unusable by an autonomous organ. The desk's binding constraint is
   calendar-time accumulation of forward evidence; the recovery objective is "get that series
   back intact", which needs file-level, integrity-checked, restore-drilled backup. Yesterday's O1
   fix (restic → storage box, weekly scripted drill) remains right; the addition today is that
   **the register row must be re-opened, because a false `resolved` is worse than an open gap** —
   it immunises the item against every future sweep. That is why O1 has survived a full week of
   audits: two organs disagreed and the wrong one was authoritative.

Adjacent rows carrying the same stale-status shape (same grep, `docs/GAP_REGISTER.md`):
`| 17 | External heartbeat … | wired-awaiting-signup |` — but the signup **has** happened:
`ls -la data/secrets/heartbeat_url.json` → present since `Jul 16 23:02`, and its contents are a
real `https://hc-ping.com/25e953b1…` URL. The register has understated a live capability for 14
days (harmless direction, same defect class). `| 3 | Pager delivery unverified on new topic … | open |`
since 07-16 — still open, still unverified, and yesterday's O3 429s prove why it matters.
**Recommendation: a register-row status is a claim; every `resolved`/`closed`/`awaiting` row needs
a dated proving artifact or it reverts to open automatically.** That is a one-time sweep plus a
lint in the re-rank step, and it protects every future cycle from inheriting a false green.

### I3 — BOTH INDEPENDENT ALERT PATHS — THE ONES BUILT *BECAUSE* OF SILENT DEATHS — FAIL SILENTLY THEMSELVES. [severity: HIGH — ruin-rail adjacency]

Yesterday's O3 covered pager saturation (429 + one global mute). This is the layer underneath, and
it is worse: the two paths that exist precisely to survive a pager failure cannot report their own
failure.

```
$ sed -n '385,399p' scripts/run_alerts.py
    # EXTERNAL HEARTBEAT (2026-07-16, v8-blueprint triage 8.13): an off-box dead-man for the
    # box itself. Everything above -- deadman, pager, watchdog -- dies WITH the host; a 3-min
    # ping to an external healthchecks-class URL makes the outside world notice silence …
    try:
        hb = json.loads(Path("data/secrets/heartbeat_url.json").read_text("utf-8")).get("url")
        if hb:
            with urllib.request.urlopen(hb, timeout=10):
                pass
    except Exception:
        pass
```

```
$ sed -n '138,151p' scripts/run_alerts.py
def _second_channel(text: str) -> None:
    """INDEPENDENT alert path (gap #38). ntfy is a single point of failure -- a header-encoding
    bug killed it silently for 29h across a live dead-man fire. healthchecks.io is already
    configured for the heartbeat; POSTing to its /fail endpoint triggers whatever notification
    the operator set up there, through completely different infrastructure. Best-effort: this
    must NEVER raise into the primary alert path."""
    with contextlib.suppress(Exception):
        …
            with urllib.request.urlopen(req, timeout=10):
                pass
```

- `except Exception: pass` and `contextlib.suppress(Exception)` with **no logging, no counter, no
  state file, no page**. A wrong URL, an expired check, a DNS failure, an egress block, a
  healthchecks.io free-tier change, or a 429 produces *byte-identical behaviour to success*.
- The off-box heartbeat's entire purpose is to notice silence. Its feed is unobservable from the
  box, and unverified off it: `grep -rn 'healthcheck\|hc-ping\|heartbeat ping' data/cro_ai_logs/*.log`
  → *(empty)* — in two weeks of operation not one line records whether a single ping landed.
- The docstring on `_second_channel` names the precedent explicitly: a header-encoding bug killed
  ntfy **silently for 29 hours across a live dead-man fire**. The remedy built in response
  reproduces the same property one level up. "Best-effort must never raise into the primary path"
  is correct; "best-effort must never be *counted*" is the bug — those are separable, and the fix
  is 3 lines.
- **Fix:** capture the HTTP status, write `{ts, status}` to `data/heartbeat_ping.json` on every
  tick, and raise a *local* alert condition (`external_heartbeat_unfed`) when the last success is
  older than ~15 min. Same for `_second_channel`: record last-success, and let `max_audit` fail on
  staleness. Cost: half an hour. This is the cheapest ruin-rail-adjacent fix in the report.
- **Validation:** point the URL at an intentionally-wrong path in a scratch copy → the new
  condition must fire; restore → it must clear. That is a real negative control, which the current
  code cannot have by construction.
- **Retirement:** never. **Monitoring:** the staleness condition IS the monitor.
- Note on read-only discipline: this audit deliberately did **not** curl the hc-ping URL. A ping
  would have registered a fresh heartbeat and masked exactly the outage being investigated —
  measuring the thing would have changed it. The correct external check is a read of the
  healthchecks.io API with an API key (free), which is the T-item below.

### I4 — THE INFRASTRUCTURE SWEEP HAS NEVER PUT A SINGLE ROW IN THE LEDGER THAT DRIVES WORK — TWO WEEKS, ~32 RECOMMENDATIONS, ZERO WIRED. [severity: HIGH — this is the mechanism behind §0]

§41 says every recommendation gets exactly one row and must reach a disposition. Measured against
the actual ledger:

```
$ python -c "json.load(open('docs/research/recommendation_ledger.json'))['recommendations']"
total rows: 46   status: {'open': 27, 'scheduled': 10, 'implemented': 6, 'rejected': 3}
=== OPEN >24h (§41 DEFECT) === 27
[('R0003',92.0h),('R0004',92.0),('R0005',92.0),('R0006',92.0),('R0007',92.0),('R0008',92.0),
 ('R0009',92.0),('R0011',88.3),('R0012',88.3),('R0013',83.3),('R0015',83.2),('R0019',40.5),
 ('R0020',40.5),('R0023',40.3),('R0024',40.3),('R0025',35.3),('R0026',35.3),('R0027',35.3),
 ('R0028',35.3),('R0029',35.3),('R0030',35.2),('R0031',35.2),('R0032',35.2),('R0033',25.5),
 ('R0034',25.3),('R0035',25.3),('R0036',25.2)]
=== SCHEDULED PAST DUE (§41 DEFECT) === 1
[('R0002','2026-07-27')]
```

**27 rows are undisposed past the 24-hour bar — 59% of the whole ledger is in the state §41 calls
a DEFECT, not backlog** — and R0002 (prompt-doctrine-bloat) is 3 days past its enforced due date.
The oldest offenders are 92 hours old. That is the general failure; the infrastructure-specific one
is sharper:

```
$ python -c "… rows where 'deep_sweep' in source"
R0001 2026-07-26 scheduled  wire CPCV/SPA/FDR/lockbox …
R0003 2026-07-26 open       O1 data-moat: screen the desk's own L2 tape …
R0004 … O2 data-moat …  R0005 … O3 data-moat …  R0006 … O4 data-moat …
R0007 … O5 data-moat …  R0008 … O6 data-moat …  R0009 … O7 data-moat hygiene …
```

All 8 `deep_sweep`-sourced rows are from the **2026-07-26 data-moat** sweep. A keyword sweep for
every one of yesterday's twelve infrastructure findings finds nothing:

```
O1 backup/DR   -> ABSENT      O5 PAT in remote   -> (only 'path','patched' false hits)
O2 quota sched -> ABSENT      O6 tmpfs/swap      -> ABSENT
O3 pager/429   -> ABSENT      O7 dashboard bind  -> ABSENT
O4 reboot/timer-> ABSENT      O8 CI parity       -> ABSENT
O9 supervision -> ABSENT      O10 disk monitor   -> (only unrelated 'disk' in R0041/R0042)
O11 entropy    -> ABSENT      O12 vuln scan      -> ABSENT
```

- **Diagnosis:** the deep-sweep organ writes a markdown file and stops. Nothing in
  `run_deep_sweep.sh`/`.py` calls `scripts/recommendations.py add`, so a sweep's output is
  *institutionally invisible* the moment the file is written — §35's own warning ("a finding not
  rowed is invisible to you forever") describing this organ exactly. Yesterday's report *noticed*
  the symptom (O5's meta-half: last week's PAT finding had no row) and wrote T8 to fix it by hand.
  T8 did not run, because T8 was also only in the markdown. **A self-referential dead end: the fix
  for unrowed findings was itself an unrowed finding.**
- **Why this outranks most technical items:** it is the multiplier on every other line in this
  report and every future sweep. Fixing it converts ~32 already-paid-for recommendations from prose
  into tracked work. Leaving it means next week's auditor re-derives the same twelve findings a
  third time — which is precisely what happened between 07-26 and 07-29 on the PAT.
- **Fix (the only durable form): make rowing mechanical, not a duty.** Add to the sweep runner, at
  the end of each subsystem report: parse `### I<n> —` / `- **O<n> —` headers and shell out to
  `scripts/recommendations.py add --source deep_sweep-<subsystem>-<date> --summary "<header>"`;
  fail the organ if the row count added is 0 while the report exceeds the 1200-byte liveness floor.
  Complexity: low (~30 lines in the runner). Dependencies: none. **Failure mode:** row spam —
  bounded by only rowing top-level findings and de-duplicating on summary prefix.
- **Validation:** after wiring, `grep -c 'deep_sweep-infrastructure'` in the ledger must be ≥ the
  number of I-headers in this file; a sweep that produces a report and zero rows must fail loudly.
- **Interactions:** feeds §35/§41 clocks, which then start firing on the 27-row backlog — that
  pressure is the *point*, but expect the first cycle after wiring to look worse before better.
- **Retirement condition:** when the sweep runner's row-count assertion has held green for 4
  consecutive weekly sweeps, the manual back-row duty can retire.

**Verification of the diagnosis (fresh reads, because "the runner doesn't row" is the load-bearing
claim), plus the generalisation MEASURED rather than asserted:**

```
$ grep -n 'recommendations\|track_findings\|research_memory\|blind_spot' ops/run_deep_sweep.sh scripts/run_deep_sweep.py
(empty)
$ grep -nE 'row|ledger|recommend|§41|§35' scripts/run_deep_sweep.py
(no matches beyond two unrelated subsystem-description strings)
$ grep -rln 'recommendations.py' scripts/ ops/ libs/
ops/principal_doctrine.txt
ops/run_cro_ai.sh
$ for f in ops/run_*_dig.sh ops/run_frontier_*.sh ops/run_cro_ai.sh ops/run_deep_sweep.sh; do
    echo "$(basename $f): recommendations=$(grep -c 'recommendations.py' $f) other_ledgers=$(grep -c 'track_findings\|research_memory\|blind_spot' $f)"; done
run_blindrediscovery_dig.sh: recommendations=0 other_ledgers=0
run_dataaxis_dig.sh:        recommendations=0 other_ledgers=0
run_litminer_dig.sh:        recommendations=0 other_ledgers=0
run_prospector_dig.sh:      recommendations=0 other_ledgers=0
run_frontier_miner.sh:      recommendations=0 other_ledgers=0
run_frontier_rotation.sh:   recommendations=0 other_ledgers=0
run_cro_ai.sh:              recommendations=1 other_ledgers=1     ← the only wired organ
run_deep_sweep.sh:          recommendations=0 other_ledgers=0
```

The ledger CLI is referenced by the *brain cycle* runner and by prose doctrine — **and by no code
path in any other organ**. The auditor is never told to row, and nothing checks that it did. That
asymmetry is exactly visible in the ledger's own source distribution: `Counter(source)` →
`cycle: 23, deep_sweep: 8, cycle-2026-07-28: 4, cycle-…-generation: 3, proactive_battery: 2,
cycle-2026-07-30: 2, …, max_audit: 1`. **Every row in the ledger traces to the one runner that
mentions the CLI.** The other seven organs — six diggers/miners and the deep sweep — have
contributed nothing, which is a far bigger hole than the infrastructure half: the SCREEN-ON-DISCOVERY
duty and the UNIVERSAL DUTY SET both bind those diggers to the research-memory and blind-spot
ledgers, and not one of their runners invokes either.

And the tool's own docstring predicted this failure verbatim, which is the strongest possible
evidence that the gap is a missing wire rather than a missing idea:

```
$ head -12 scripts/recommendations.py
THE HOLE. … Everything else this desk produces a recommendation from -- max_audit defects, the
weekly deep cold audit, cycle reports, the proactive battery, external reviews -- had no ledger and
no forced disposition. A deep sweep could name eight high-ROI improvements, the report gets
written, the window closes, and by the next Sunday nobody knows they existed.
```

**And there is a structural contradiction underneath, which this audit is living inside right now
and must state rather than quietly reproduce.** This sweep's own operating instruction is
*"READ-ONLY, do NOT modify code/state/cron/git"*. Calling `scripts/recommendations.py add` writes to
`docs/research/recommendation_ledger.json` — i.e. **the organ is simultaneously bound by §41 to row
every recommendation and forbidden by its own harness from writing anything but its report.** Every
previous infrastructure auditor faced the same contradiction and resolved it the only way available:
write the report, row nothing. So the missing wire is not merely absent, it is *prohibited* at the
point where a human-equivalent would fix it by hand. That is why T8 must be **mechanical in the
runner** (which is not read-only) rather than a duty on the auditor: `run_deep_sweep.py` should parse
the finished report and row its headers after the read-only session ends. A duty that the harness
forbids is not a duty, it is a defect generator.

The remedy for that stated hole was built on 07-26. Four days later the deep sweep has still never
used it. **A law that lives only in prose is enforced only when an LLM happens to remember it;
§41's own anti-gaming argument ("rows are never deleted") is irrelevant when rows are never
created.** Generalising (proactive-battery move 6 — a law written for one organ is a blind spot on
the others): every organ runner needs a post-run assertion that it invoked the ledgers its output is
subject to. That is one shared shell function called by eight runners, and it converts §35/§41 from
an honour system into a mechanism.

### I5 — THE DELTA-NEUTRAL BOOK'S INVARIANT-BREACH LOG IS SINGLE-SLOT, SIDE-LESS, AND READ BY NOTHING — AND IT FIRED 17 MINUTES BEFORE THIS AUDIT LOOKED. [severity: HIGH — money path]

```
$ ls -la data/cashcarry_error.log && cat data/cashcarry_error.log
-rw-r--r-- 1 quant quant 190 Jul 30 07:34 data/cashcarry_error.log
2026-07-30T07:34:40.929867+00:00 unfilled leg MOVEUSDT spot_ok=True fut_ok=False
  spot_res={'status': 'FILLED', 'executedQty': '47306.0'} fut_res={'status': 'REJECTED', 'executedQty': '0.0'}
```

One leg of a delta-neutral pair executed on the venue; the hedging leg was rejected. Three
independent defects turn that event into an invisible one:

1. **The pager's handle on this file is dead code.**
   `$ grep -n '_ERR' scripts/run_alerts.py` → `46:_ERR = Path("data/cashcarry_error.log")` — **one
   line, the definition, and no other reference in the file.** The alert script imports the path to
   the book's invariant-breach log and never reads it.
2. **The only other reader is never scheduled.** `grep -rn 'cashcarry_error' scripts/ libs/` →
   `scripts/rollback_guard.py:59` (records `error_log_bytes` as a baseline, does not alert) and the
   executor that writes it. `crontab -l | grep -c rollback_guard` → **0**.
3. **The writer destroys its own history.** Every one of the six call sites uses
   `_ERR.write_text(...)`, not append: `grep -n '_ERR' scripts/run_cashcarry_executor.py` → lines
   457 (`reconcile fail`), 954 (`unfilled leg (maker path)`), 1071 (`maker fail`), 1086
   (`unfilled leg`), 1329 (`cycle error`). The file is a **single-slot mailbox**: a burst of five
   unhedged legs leaves one line, and the comment on line 47 calls it a *"visible cycle-error log
   (not swallowed to null)"*. It is swallowed — just to a slot instead of to null.

**On the direction, deliberately not overclaimed.** The log line records `spot_ok`/`fut_ok` but
**not the side**, so from the box's own artifacts you cannot tell whether this left a naked long, a
naked short, or was harmless. Reading the writer (`sed -n '1060,1090p'
scripts/run_cashcarry_executor.py`) shows the close path sets `_reduce_only_leg = spot_side ==
"SELL"`, and the circumstantial evidence points to a *benign* close-path rejection: `web/venue_reconcile.json`
→ `"open_futures_shorts": 0` (a reduceOnly buy with nothing to reduce is *expected* to be
rejected), `data/cashcarry_positions.json` (07:50) → `"positions": {}`, `"last_risk_action":
"flatten"`, and `web/live_combined.json` shows MOVEUSDT's real close at `2026-07-28T15:19:58` with
the same qty 47,306. **That is the finding, not a reassurance: the desk got lucky on the direction
and its instrumentation cannot tell the difference.** The same code path, on an open (spot BUY
filled / futures SELL rejected), produces an unhedged long with no page, no history, and no reader.
- The failure is not hypothetical at scale — `data/cro_ai_logs/cashcarry_respawn.log` carries 86
  `RECONCILE-FAIL`/`CLOSE-FAIL` lines across EGLD/MANA/XLM/AGLD/COOKIE, and
  `data/cashcarry_positions.json` still shows `"reconcile_fail_counts": {"ONEUSDT": 1}`. Meanwhile
  `web/venue_reconcile.json` measures `"stranded_uncredited_value": 4399.91` across 12 spot assets,
  every one `"credited_by_rail": false` — the residue of exactly this class of event, and the
  subject of GAP #91.
- **Fix (≈5 lines, highest severity-per-line in this report):** (a) `_ERR.write_text` →
  append-with-`os.replace`-safe append (`open(..., "a")`) so history survives; (b) include the
  side (`spot_side`/`fut_side`) and the resulting net exposure in the message; (c) add an alert
  condition in `run_alerts.py` on `_ERR` mtime-newer-than-last-seen — the handle is *already*
  imported, so this is one function; (d) schedule `rollback_guard.py` or delete it.
- **Validation:** touch a scratch copy of the log and assert the new condition fires; assert the
  message names the side. **Failure mode:** page noise if reconcile-fails are routine — bounded by
  deduping on symbol+side for 6h (the pager already has that machinery).
- **Retirement:** never — this is the delta-neutral invariant, which is what makes the book
  ruin-bounded in the first place.

### I6 — THE WATCHDOG CAN CRASH BEFORE IT REACHES THE PAGER, AND HAS. [severity: HIGH — ruin-rail adjacency]

```
$ sed -n '208,221p' scripts/watchdog.py
    subprocess.run([py, "scripts/run_leverage_opt.py"], cwd=str(_ROOT), timeout=60,
                   capture_output=True, check=False)
    subprocess.run([py, "scripts/run_live_combined.py"], cwd=str(_ROOT), timeout=60, …)
    subprocess.run([py, "scripts/data_health.py"], cwd=str(_ROOT), timeout=30, …)
    # PAGER: push CRITICAL alerts (dead heartbeat / stuck kill / root-cause / growth defect) …
    subprocess.run([py, "scripts/run_alerts.py"], cwd=str(_ROOT), timeout=30, …)
$ grep -n 'if __name__' scripts/watchdog.py
239:if __name__ == "__main__":          # ← main() is NOT wrapped in try/except
$ grep -c 'TimeoutExpired' data/cro_ai_logs/watchdog.log
6
$ grep -n 'TimeoutExpired: Command' data/cro_ai_logs/watchdog.log | tail -1
2292:subprocess.TimeoutExpired: Command '[…/python', 'scripts/run_leverage_opt.py']' timed out after 60 seconds
```

`check=False` suppresses non-zero exits; it does **not** suppress `TimeoutExpired`, which
`subprocess.run(timeout=…)` raises. `main()` has no handler and the module has no top-level guard,
so a single slow child aborts the tick — and **everything sequenced after it is skipped: the live
feed refresh, `data_health`, the PAGER, the daily-research-cycle spawn, and the netlify publish.**
The pager is the fourth of five unguarded subprocess calls; it is last in line behind the three
most likely to be slow.

- Measured: it has happened (2 full tracebacks in the log). Each occurrence is a 3-minute window
  with no alerting at all; a correlated slowdown (the same RAM/quota pressure that makes
  `leverage_opt` slow) makes consecutive misses likely exactly when alerting matters most.
- This re-arms a documented incident: `watchdog.py`'s own header comments record an 11.5-day
  pager silence. The remedy then was a supervisor; the supervisor now has the same failure mode
  through a different exception.
- **Fix (1 line each):** wrap lines 208–221 in `try/except subprocess.SubprocessError` (log and
  continue), **and re-order so `run_alerts.py` executes FIRST** — the pager must never be
  downstream of optional work. Better still: `for cmd, t in _TICK_STEPS: with contextlib.suppress(…)`.
- **Validation:** inject a `sleep 90` stub for `run_leverage_opt.py` in a scratch tree; the tick
  must still page. This is a real negative control the current code cannot pass.

### I7 — THE PAGER DELIVERS ~16% OF WHAT IT TRIES TO SAY, AND HALF OF WHAT IT DOES DELIVER IS A PERMANENT FALSE POSITIVE. [severity: HIGH — alert quality]

Yesterday's O3 established saturation. Quantified over 7 days:

```
$ journalctl -u quant-refresh --since '7 days ago' | grep -oE 'alerts: [0-9]+ page' | sort | uniq -c
   3309 alerts: 0 page      36 alerts: 1 page      9 alerts: 2 page      1 alerts: 3 page
$ … | grep -oE 'pager push failed: .{0,50}' | sed -E 's/[0-9]+/N/g' | sort | uniq -c
    252 pager push failed: RuntimeError('pager N backoff: Nm remaining')
     36 pager push failed: <HTTPError N: 'Too Many Requests'>
$ cat data/cro_ai_logs/digest_page.log
digest paged (6 lines) / digest page failed: <HTTPError 429> / digest page failed: <HTTPError 429>
```

**57 pages delivered; 36 hard-rejected by ntfy 429; 252 suppressed by the global 1-hour backoff.**
Attempt success 61%; condition coverage 57/345 = **16.5%**. The last two daily digests were never
delivered. There is no durable delivery record on disk — `run_alerts.py:369` swallows push failure
by design and its stdout goes only to the journal.

And the largest single consumer of that scarce budget is structurally guaranteed to be wrong:

```
$ sed -n '105,111p' scripts/run_alerts.py
_CRED = Path("/home/quant/.claude/.credentials.json")
def _auth_broken() -> bool:
    """… No active credentials => nothing can reason. Free, definitive, no quota burned."""
    return not _CRED.exists()
$ ls -la /home/quant/.claude/.credentials.json
ls: cannot access …: No such file or directory
$ sed -n '10,12p' ops/brain_env.sh
#      CURRENT: `claude setup-token` output from the principal's Max account.
#      setup-token does NOT update ~/.claude/.credentials.json -- the token only
#      works via this env var, which also outranks any stale stored login
$ tail -1 data/cro_ai_logs/20260730_0700.log
=== cro-ai exit 0 at Thu Jul 30 07:39:58 AM UTC 2026 ===
```

**`_auth_broken()` returns True unconditionally, forever, and the desk's own auth documentation
says why** — the credential file it probes is never written under the current auth scheme. The
brain authenticated and exited 0 forty minutes ago. `data/.last_alerts.json` shows `auth_broken`
in the live `_paged` set at 00:52 today. At the 6h dedupe, that is ~28 of the 57 delivered pages
(~49%) spent on an unfixable false alarm whose own remediation text (`claude setup-token`) cannot
clear it. This is a **100%-constant gate** — the doctrine's named prime quarry — pointed at the
pager instead of at a validation bar, and it is the mechanism that trains the reader to ignore
pages. It also compounds I3/O3 directly: false pages burn the same ntfy budget that then 429s a
real one.
- **Fix (1 line):** `return not (_CRED.exists() or Path("data/secrets/claude_oauth_token").exists()
  or Path("data/secrets/anthropic_api_key").exists())` — mirroring `brain_env.sh`'s documented
  precedence. Better: assert on *outcome* (last successful brain exit within N hours) rather than
  credential-file presence, which is the same config-vs-outcome error one level down.
- **Validation:** run `scripts/run_alerts.py` with the token present → `auth_broken` must not fire;
  move the token aside in a scratch env → it must.
- **Also fix (O3 carry-over, still unbuilt):** two lanes, so a ruin-rail page is never muted by a
  routine-lane 429.

### I8 — TWO OF THE DESK'S WEEKLY CADENCES HAVE NEVER FIRED FROM THEIR PRIMARY SCHEDULER; 100% OF SWEEPS HAVE COME FROM THE FALLBACK. [severity: MED-HIGH — cadence integrity]

```
$ crontab -l | grep -n deep_sweep
37:0 4 * * 0 cd /home/quant/quant-platform && flock -n /tmp/deep_sweep.lock \
   .venv/bin/python scripts/run_deep_sweep.py >> data/cro_ai_logs/deep_sweep.log 2>&1
$ crontab -l | grep -oE '>> [^ ]+\.log' | sed 's/>> //' | sort -u | while read f; do [ -f "$f" ] || echo "MISSING: $f"; done
MISSING: data/cro_ai_logs/deep_sweep.log
MISSING: data/cro_ai_logs/roster_frontier_watch.log
$ grep -rn 'os.remove\|unlink()\|rm -f.*\.log' scripts/*.py ops/*.sh | grep -i log
(empty — nothing deletes logs)
```

A shell redirection creates its target **before** exec, so the file appears even if `flock` blocks
or python dies instantly. Its absence is proof the cron line has never executed. The organ existed
in time to be scheduled (`git log --diff-filter=A -- scripts/run_deep_sweep.py` → **2026-07-24**),
so Sunday 2026-07-26 04:00 was a real opportunity that produced nothing — that day's reports are
timestamped 11:18–15:37 (`ls -la --time-style=long-iso docs/research/deep_sweep/20260726_*`), not
04:xx. Meanwhile every sweep that has ever run shows the fallback as its parent:

```
$ grep 'fired deep_sweep' data/cro_ai_logs/organ_catchup.log | tail -3
2026-07-29T21:00:03 re-fired deep_sweep (ops/run_deep_sweep.sh)
2026-07-30T02:00:03 re-fired deep_sweep (ops/run_deep_sweep.sh)
2026-07-30T07:40:03 re-fired deep_sweep (ops/run_deep_sweep.sh)   ← this run
```

- **What it means:** the catch-up poller is not a safety net, it is *the* scheduler — and it is a
  5-minute poller gated on quota, so "weekly Sunday 04:00" is really "some hours-to-days after
  Sunday, if the pool allows". `roster_frontier_watch` (`30 5 * * 1`, Monday) has the same
  never-fired signature with no fallback at all, so that cadence is simply not running.
- **Alternative explanation, stated for honesty:** the crontab line may have been *added* after
  04:00 on 07-26, in which case 08-02 is the first true opportunity. `/var/spool/cron/crontabs/quant`
  is unreadable to this account and `journalctl -u cron` returns "No entries" without sudo, so the
  audit cannot close this from here. **Either way the conclusion holds** — no sweep has ever been
  observed to start from cron, and nothing on the box would notice if none ever did.
- **Fix:** move both to systemd timers with `Persistent=true` (the desk already runs 8 of these
  and they are its most reliable layer, S1), or at minimum have `organ_catchup` log *which* path
  fired and alert when the primary misses. **Test:** on 2026-08-02, assert `deep_sweep.log` exists
  and its first line predates 04:05.

### I9 — THE ORGAN THAT MEASURES THE DESK'S BINDING CONSTRAINT HAS WRITTEN ZERO BYTES IN 11 SCHEDULED RUNS. [severity: MED — green timer, dead organ]

```
$ ls -la data/cro_ai_logs/quota_watch.log
-rw-rw-r-- 1 quant quant 0 Jul 28 21:20 data/cro_ai_logs/quota_watch.log
$ crontab -l | grep quota_verdict
20 */3 * * * … .venv/bin/python scripts/quota_verdict.py >> data/cro_ai_logs/quota_watch.log 2>&1
$ grep -c 'quota=DEAD' data/cro_ai_logs/organ_catchup.log
894        # 203 of them in the last 24h
```

Eight runs a day since 07-28 21:20, **zero bytes of output**, while the constraint it measures
produced 203 `quota=DEAD` lines in the last 24 hours alone. Yesterday's O11(g) called this
"dormant-by-design since 07-23 (`verdict_sent: true`)" — dormancy explains silence but not the
right design: **the desk's #2 finding for two weeks running is quota starvation, and the quota
meter is switched off.** A one-shot verdict organ is the wrong shape; a continuous meter
(first-attempt success per organ per day, which `organ_catchup.log` already contains) is the right
one. This is the specific measurement that would make O2/T5 (quota-aligned scheduling) an
evidence-based change instead of a guess.

### I10 — THE CERTIFICATION GATE HAS FAILED EVERY TIME IT HAS RUN, MOSTLY BY TIMEOUT, AND THE CYCLE CONTINUES REGARDLESS. [severity: MED-HIGH — validation adjacency]

```
$ grep -o "ci_gate[^}]*}" data/cro_ai_logs/daily_research_cycle.log
ci_gate] {'ok': False, 'rc': 1, 'tail': "CI: FAILED -> ['lint (ruff)', 'tests (pytest)']"}
ci_gate] {'ok': False, 'rc': 1, 'tail': "CI: FAILED -> ['lint (ruff)']"}
ci_gate] {'ok': False, 'rc': 'timeout', 'tail': 'timeout after 300s'}   × 5
```

**7 invocations in the surviving log, 7 failures, 5 of them timeouts at 300s** — and against the
full cycle history, **12 consecutive red gates over 6 days** (`data/cro_cycle_log.json`, 49 cycles,
`ci_gate` tally `{True: 29, False: 18, None: 2}`, every cycle 07-24 → 07-30 False).

**The mechanism is arithmetic, and it means the gate is structurally incapable of passing:**

```
$ grep -n 'ci_gate' scripts/daily_research_cycle.py
34:    ("ci_gate",  "scripts/run_ci.py",  300),          ← 300-second budget
$ sed -n '34,42p' scripts/run_ci.py
_STEPS = [("lint (ruff)", […ruff check scripts libs tests]),
          ("tests (pytest)", […pytest tests/ -q]),        ← WHOLE TREE since 2026-07-25
          ("stress harness", […run_stress.py])]
$ timeout 900 .venv/bin/python -m pytest -q -p no:randomly
1320 passed, 3 skipped in 653s        ← the pytest step alone is 2.2× the entire gate budget
```

So today's red is *provably* a timeout and not a defect: ruff passes in 0.54 s, the suite is
1320/0/0, stress exits 0 — nothing else in the gate can fail. The streak starts 07-24, immediately
before `run_ci.py` was widened from ~147 tests to the whole tree on 07-25 (the comment in
`_STEPS` documents the widening as "proven safe" — it was, on correctness; nobody re-checked the
*budget*). **Yesterday's S5 ("CI gate exists and is green today") was measuring the manual
invocation, not the scheduled one.**

**Three independent reasons nothing stops or is heard — each verified:**

1. **A red gate cannot halt anything.** `scripts/daily_research_cycle.py:122` → `def main() -> None`
   and `:161` → `sys.exit(main())`. `main` returns `None` ⇒ **exit code is always 0**, whatever
   failed. All 65 steps run in an unconditional loop, so `stage_a_executor`, `run_leverage_opt`,
   `run_live_combined` and `git_snapshot` proceed on a red gate.
2. **The alarm cannot see the red.** `scripts/max_audit.py:618-624` fires `ci-gate-red` only when
   `data/.ci_last_run.json` says `ok: false`. On a 300 s `TimeoutExpired`, `run_ci.py` is SIGKILLed
   **before** it writes that marker — so the marker retains the last *completed* run's result, and
   there is **no staleness bound** on it: `cat data/.ci_last_run.json` → `{"ok": true, "ts":
   "2026-07-30T07:37:38", "failed": []}`. **12 consecutive red gates produced zero escalations, and
   the marker says green right now.** The comment above that check states it exists because a red
   gate once "sat UNDETECTED for 81h" — the same failure mode is still open, having moved from
   "nobody ran it" to "the runner is killed before it can report".
3. **Gate step 3 cannot fail on a bad verdict.** `scripts/run_stress.py` has `def main() -> None`
   and no `sys.exit`; its `PASS`/`REVIEW` verdict goes to `web/stress.json` and stdout only. Only an
   uncaught exception can fail that step.

**And the hosted gate is red for a different reason the local gate cannot see:**

```
$ grep -nE 'python-version|ruff|mypy|pytest' .github/workflows/ci.yml
27: python-version: "3.11"      35: ruff check .      38-39: Types (mypy --strict) → mypy      42: pytest
$ .venv/bin/python -m mypy
Found 6 errors in 3 files (checked 370 source files)
scripts/run_trade_forensics.py:254: error: Unsupported operand types for <= ("int" and "None")
scripts/run_trade_forensics.py:254: error: Unsupported operand types for >= ("str" and "int")
scripts/run_trade_forensics.py:254: error: Unsupported operand types for <  ("str" and "float")
libs/data/lake.py:53,77: error: Call to untyped function … [no-untyped-call]
libs/core/config.py:24: error: Library stubs not installed for "yaml"
```

`ci.yml` runs `mypy --strict` as a gate step; `run_ci.py::_STEPS` does **not** include mypy. **So the
local gate reports green on a tree the hosted gate rejects** — the two gates disagree by
construction, on top of yesterday's O8 python-version/pin divergence (verified unchanged: CI 3.11
vs prod 3.12.13, `pip install -e ".[dev]"` vs 22 `==` pins, and **0 of 22 pins drift** so
`requirements-vps.txt` is an accurate prod description that CI simply ignores). One of the six is
worth a second look on its own merits: at `run_trade_forensics.py:254` the guard
`maker["maker_share"] is not None and maker["n_legs"] >= 20 and maker["maker_share"] < 0.60` runs on
a heterogeneous dict whose values include strings, so mypy cannot prove the comparisons safe — and
the adjacent comment explicitly anticipates a null (*"a null share is thin data, not a regression"*).
pyproject lists this file among those that *"can PLACE ORDERS or MOVE FUNDS"*.

**The one path that would genuinely revert on red has no automated caller.**
`scripts/rollback_guard.py:102` → `if not _ci_green(): reasons.append("CI regression …")` → verdict
`REVERT` → `revert()` restores files, and it invokes run_ci with **no timeout**, so it can actually
finish. `grep -rn rollback_guard scripts/ ops/ libs/` finds only a prose mention inside an LLM
prompt. 20 checkpoints exist in `data/rollback/` (so `checkpoint` gets called), but running
`evaluate` is agent-discretionary. **The desk built working enforcement and never wired it.**

HEAD's own commit message — *"the migration that measured well and got reverted anyway — because the
thing certifying it is still broken"* — is the downstream cost, paid in validation-stats' currency.
- **Fix, cheapest first (all one-liners except the last):** (1) raise the `ci_gate` budget above
  ~900 s — *one integer* — or split into a blocking fast lane (`ruff` + `pytest -m 'not slow'`) plus
  a nightly full suite; (2) make `daily_research_cycle.main()` return a non-zero code and record
  `timeout` distinctly from `fail`; (3) add a staleness bound to the `.ci_last_run.json` check so an
  unwritten marker is itself the alarm; (4) add `sys.exit(1)` on a `REVIEW` verdict in
  `run_stress.py`; (5) add `mypy` to `run_ci.py::_STEPS` and install `types-PyYAML`; (6) give
  `rollback_guard evaluate` an automated caller.
- **Validation:** after (1)–(3), force a deliberate red (break one test in a scratch checkout) and
  assert the cycle exits non-zero **and** `ci-gate-red` escalates within one `max_audit` run. That
  end-to-end negative control has never existed.
- **Retirement:** never; this is the gate that stands between an unvalidated edit and the money path.

### I11 — THE DISK RUNS OUT IN ~32 DAYS (≈2026-08-30), NOTHING WATCHES IT, AND DISK-FULL TURNS 324 NON-ATOMIC WRITES INTO TRUNCATIONS. [severity: TOP-3 — the only hard deadline in this report]

```
$ df -h /
/dev/sda1  38G  13G  24G  35% /
$ for d in 1 2 3 7; do find data -type f -mtime -$d -printf '%s\n' | awk '{s+=$1} END {print s}'; done
last 1d: 0.75 GB   last 2d: 1.45 GB   last 3d: 2.14 GB   last 7d: 4.75 GB
$ find data/moat -type f -newermt '2026-07-27' -printf '%TY-%Tm-%Td %s\n' | awk …
2026-07-27 692.9 MB   2026-07-28 688.2 MB   2026-07-29 686.1 MB   2026-07-30 219.5 MB (partial)
```

**0.72–0.75 GB/day, sustained and near-constant (the recorder tape dominates) ÷ 24 GB free ⇒ ~32
days.** Two measurements taken independently (mine by mtime-bucket, a parallel agent's by
directory) agree to within 5%. Nothing warns: `grep -nE 'disk|statvfs|df' scripts/data_health.py`
→ *(empty)* — yesterday's O10 unchanged. `data/rollback/` adds 20 full-tree snapshots (100 MB,
~5.8 MB each, one per code change) with **no pruning policy**.

The second half is what makes it a correctness problem and not just an outage:

```
$ grep -rn "write_text(" libs/ scripts/ | wc -l   → 324
$ grep -rn "os.replace(" libs/ scripts/           → 2
$ grep -rnE "fsync|O_DSYNC|O_SYNC" --include='*.py' .   → 0
```

`Path.write_text()` truncates the target **before** writing. On a full disk, every one of those 324
call sites converts a state file into a zero-byte file. The desk built the correct primitive and
applied it to exactly two places — `libs/execution/ea_bridge.py:46` and
`scripts/run_deadman_switch.py:62`, i.e. the broker bridge and the dead-man rail. **Neither is in
the research-state path**, which is where the forward-evidence record lives, and which has no
backup (I2/O1). So the failure sequence on day ~32 is: disk fills → a `write_text` on
`data/axis_shadow_state.json` / `data/forward_slots.json` / `research_state.json` truncates → and
per I12 a truncated slot file *silently loosens the Holm bar* rather than failing.
- **Fix, in order:** (1) a disk-percent + inode check in `data_health.py` with a page at 80%/90%
  — the single cheapest item in this report; (2) tape rotation/compaction policy for `data/moat`
  (or cold-rotate to the storage box from I2's fix — one lever solves DR and disk together);
  (3) prune `data/rollback/` to the last N; (4) `os.replace` on the ~10 highest-value state files.
- **Validation:** simulate with a scratch loop-device filesystem at 100% and assert the writers
  fail *closed* (exception, old file intact) rather than truncating.
- **Retirement:** the alarm never retires; the compaction policy retires if the tape is moved off-box.

### I12 — THE HOLM BAR FAILS OPEN: A MISSING STATE FILE SILENTLY SHRINKS THE MULTIPLICITY COHORT, AND THE PAYLOAD'S OWN NOTE ASSERTS THE OPPOSITE. [severity: TOP-3 — recurrence of `9dddc49` by a new mechanism]

Read the whole path (`libs/research/slot_registry.py:70-131`):

```python
axis_doc = _read_json(_AXIS_STATE)
if axis_doc is None:
    unknown.append(_AXIS_STATE)      # ← recorded …
else:
    … slots.append(…)                # ← … but the slots are simply never added
…
return {"m_concurrent": len(slots), "complete": not unknown, "unknown_sources": unknown, …
        "note": ("… Unreadable sources are counted as UNKNOWN, never zero: understating m "
                 "loosens every bar. …")}

def concurrent_m() -> int:
    """The Holm cohort size. Never returns 0 …"""
    return max(1, int(derive_slots()["m_concurrent"]))     # ← `complete` is NEVER consulted
```

`derive_slots()` computes the guard (`complete: False`, `unknown_sources: [...]`) and **no consumer
reads it.** `concurrent_m()` — the function that sets the Holm bar for every Stage-B forward clock
in `scripts/run_axis_shadows.py:143` — takes only `m_concurrent`. So an unreadable source removes
its slots from the count and the bar drops:

- live state: `m_concurrent=12` (4 from `data/axis_shadow_state.json`, 6 standing clocks, 2 sleeves)
- `axis_shadow_state.json` unreadable → **m = 8** (bar ~1.5× too loose)
- axis + standing unreadable → **m = 2** (bar ~6× too loose)

**The `note` field in the very same payload states the opposite of what the code does.** And the
file that would go missing is written non-atomically, under a SIGKILL timeout, by the same script
that later derives its own bar from it (`run_axis_shadows.py:151-152` → two consecutive
`write_text` calls; `daily_research_cycle.py:103-110` SIGKILLs steps on timeout, which has already
happened 5 times — all `ci_gate`, per I10). **A crash therefore loosens the next run's own
multiplicity control.**

This is the *same defect class* the desk fixed 8 hours ago in `9dddc49` ("THE HOLM BAR WAS COMPUTED
ON m=4 WHILE 12 CLOCKS ACCRUED … ~3.2x too loose") — the hardcoded-m instance was repaired while
the derived-m instance fails open through a different door. Under the TWO-STAGE DISCOVERY LAW the
Holm bar is the *only* multiplicity control on the *only* path to capital, so this is the highest-
consequence software defect in this audit even though nothing has visibly broken.
- **Fix (≈3 lines):** `concurrent_m()` must fail **closed** — if `complete is False`, raise, or
  hold the last-known-good m from `data/forward_slots.json` and page. Delete or correct the `note`.
  Add a unit test: unreadable axis state ⇒ `concurrent_m()` does not decrease.
- **Validation:** in a scratch tree, corrupt `axis_shadow_state.json` and assert the bar does not
  loosen and an alert fires. That negative control cannot pass today.
- **Interaction:** raises the bar back where it belongs; expect fewer promotions, which is correct.

### I13 — THE MOST EXPENSIVE ORGAN ON THE BOX CANNOT BE MARKED DONE, SO IT HAS BEEN RE-FIRED 10 TIMES FOR ONE SCHEDULED RUN — THIS AUDIT IS RE-FIRE #10. [severity: HIGH — largest recoverable quota waste]

```
$ sed -n '69,71p' libs/ops/organ_catchup.py
    OrganSpec("deep_sweep", "ops/run_deep_sweep.sh", "deep_sweep*.log", 1200,
              "run_deep_sweep", period_days=7),        # ← NO artifacts=(...) argument
$ ls -la data/cro_ai_logs/deep_sweep_*.log | awk '{print $5, $9}'
691 …20260728T2000.log   721 …20260729T0100.log   679 …20260729T0600.log   678 …20260729T1100.log
650 …20260729T1600.log   641 …20260729T2110.log   691 …20260730T0200.log   255 …20260730T0740.log
$ grep -o 're-fired [a-z_]*' data/cro_ai_logs/organ_catchup.log | sort | uniq -c
     10 re-fired deep_sweep      5 re-fired brain      2 re-fired litminer      1 re-fired frontier
```

The success test is "an attempt log ≥ 1200 bytes". The runner's log captures only
`run_deep_sweep.py`'s stdout — the eight auditors write their reports through file tools — so the
log **can never reach 1200 bytes**: all eight attempts are 255–721 b. `organ_owed("deep_sweep")` is
therefore permanently True, every re-fire refreshes the mtime that keeps it True, and the loop runs
forever: fire → 45-min cooldown → owed → probe → fire. Every other organ has an `artifacts=(…)`
escape hatch (litminer explicitly `artifacts=()`, frontier
`artifacts=("docs/research/search_operator_library.md",)`); the weekly sweep — 8 max-effort auditor
sessions per fire, the single largest quota consumer — is the one that lacks it. The same
`OrganSpec`'s own comment block documents a *previous* patch to this exact problem (widening the
glob to catch cron's `deep_sweep.log`, "the BETTER attempt marker") — and per I8 that file has never
existed, so the patch is inert.

**This is self-referential and worth stating plainly: the audit you are reading is re-fire #10 of a
run that was scheduled once, and on completion it will still be marked owed.** Cost: ~9 redundant
8-auditor sweeps, plus 610 `owed=deep_sweep quota=DEAD` CLI probes that each walk the model chain.
That is the desk's scarcest resource — the same pool whose starvation is O2/I9 — spent re-running
finished work.
- **Fix (one tuple):** `artifacts=("docs/research/deep_sweep/",)`, or test for
  `docs/research/deep_sweep/<date>_SYNTHESIS.md`, or measure the *reports'* bytes rather than
  stdout's. **This is the single highest-ROI line-edit in the report** — it recovers quota for the
  organs in I15 that currently cannot run at all.
- **Validation:** after the change, `grep -c 're-fired deep_sweep'` must stop increasing once
  today's reports exist; assert `organ_owed` flips False within one tick of the last report write.
- **Generalise (battery move 6):** every `OrganSpec` success test should key on the artifact the
  organ *exists to produce*, never on its runner's stdout. Audit the other five specs for the same
  shape.

### I14 — A FOURTH, UNLOCKED BRAIN SPAWNER FIRES DETERMINISTICALLY INTO OTHER ORGANS' WINDOWS, GATED ON THE NEWEST FILE IN A SHARED DIRECTORY. [severity: HIGH — this is a *mechanism* of the quota starvation, not a symptom]

```
$ sed -n '313,327p' scripts/run_alerts.py
    logs = sorted(Path("data/cro_ai_logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
    if logs:
        last = logs[-1]
        healthy_today = (last.stat().st_size >= 2048 and now - last.stat().st_mtime < 20*3600)
    …
    subprocess.Popen(["setsid","nohup","bash","ops/run_cro_ai.sh"], … start_new_session=True)
```

`healthy_today` — the gate on whether the brain needs rescuing — is computed from **whatever `.log`
in a 31-file shared directory happens to have the newest mtime**. That directory also holds
`watchdog.log`, `organ_catchup.log`, `oi_ls_live.log`, `defi_lending.log`, and the
`deep_sweep_*.log` stubs from I13. So *any* organ that touches a small log flips `healthy_today`
to False, and with an event-trigger alert live (`cadence_floor_violation` was paged 06:59 today) a
brain is launched. The only guard is `_brain_running()` (a `pgrep`, i.e. TOCTOU) — **it never takes
`/tmp/cro_ai.cron.lock`**, which the cron path does take. And `run_alerts.py` itself runs from two
owners every 180 s (watchdog cron `*/3` + `quant-refresh.timer`), ≈40 invocations/hour.

Observed twice today, both ~40 s after `organ_catchup` started a deep-sweep:
`02:00:03` catchup fires deep_sweep → `02:00:16` a small `deep_sweep_…0200.log` appears →
**`02:00:43` run_alerts spawns a brain** → `02:45:46` cron fires a *second* brain (the lock was
free, because the 02:00 spawn never took it) → both die on `session limit · resets 7am` →
`07:40:11` catchup fires deep_sweep again → `07:41:02` **run_alerts spawns a brain again**
(`data/.last_alerts.json` → `_brain_trigger 2026-07-30T07:41:02`). The 07:41 spawn also consumed
the 3-hour trigger token, so a *legitimate* retry is blocked until 10:41.

`organ_catchup` serialises the pool correctly (85 logged "field busy … holding retries so they do
not share the window" holds). `run_alerts` walks straight past that gate. **The desk's quota
scarcity is partly self-inflicted by an unlocked spawner racing its own catch-up layer.**
- **Fix:** (a) glob the brain's own log pattern (`20*_*.log`), not `*.log`; (b) take the same
  `flock` the cron path takes — or better, per I15's fix, put the lock **inside** `ops/run_*.sh`
  where all four owners converge; (c) consult `organ_catchup`'s busy gate before spawning.
- **Validation:** replay: touch a 300-byte file in `data/cro_ai_logs/` and assert no brain spawns.

### I15 — THE TWO MOST-STARVED ORGANS ARE INVISIBLE TO THE RETRY LAYER, AND THE DESK CANNOT READ ITS OWN SERVICES' FAILURE LOGS. [severity: HIGH — observability floor]

```
$ grep -n 'brain_auth_check\|LOG=' ops/run_litminer_dig.sh
5:brain_auth_check || exit 1
17:LOG="data/cro_ai_logs/litminer_$(date -u +%Y%m%dT%H%M).log"
$ grep -c 'owed=dataaxis' data/cro_ai_logs/organ_catchup.log     → 0
$ grep -c 'owed=prospector' data/cro_ai_logs/organ_catchup.log   → 1   (of 1153 ticks)
$ id -nG quant
quant                       # not in adm, not in systemd-journal
$ journalctl -u quant-dataaxis --since '3 days ago'
-- No entries --
```

The auth/quota check exits at line 5; the log file is created at line 17. A quota death at second
~10 therefore leaves **no artifact at all** — and `organ_owed()` returns False when no attempt log
exists in the window ("timer has not fired yet today"). So the organs that fail *hardest* are the
ones the retry layer never sees. Across 1153 catch-up ticks, `dataaxis` was never once owed and
`prospector` once. Staleness against their own cadences: `prospector_watchlist.md` **275 h old vs a
30 h cadence (9.2×)**, litminer 98 h (3.3×), dataaxis 40.7 h (1.4×).

Compounding it: the `quant` user is in no group that can read the journal, so the *reason* those
units failed — which systemd captured faithfully — is unreadable to the desk's own automation and
to this audit. **The desk is structurally unable to diagnose its own service failures**; that is
the deepest observability gap found this sweep, and it is one `usermod -aG systemd-journal quant`
away (principal action — see I16b).
- **Fix (desk-reachable):** create `LOG=` and write the attempt line **before** `brain_auth_check`
  in all four `ops/run_*_dig.sh`. Then a 10-second death leaves a marker, the retry layer sees it,
  and `dataaxis`/`prospector` become retryable for the first time.
- **Validation:** temporarily point one wrapper's auth check at a bad token in a scratch copy and
  assert an attempt log is created and `organ_owed` flips True.

### I16 — TWO STRUCTURAL LIMITS THAT INVALIDATE PART OF YESTERDAY'S FIX LIST AND THIS AUDIT'S OWN MEASUREMENT WINDOW. [severity: MED-HIGH — meta]

**(a) The evidence horizon is 40 hours, because a count-based prune runs over a shared directory.**
```
$ grep -n 'tail -n +31' ops/run_cro_ai.sh
98: ls -1t data/cro_ai_logs/*.log | tail -n +31 | xargs -r rm -f   # "keep last 30 logs"
```
That directory holds ~13 always-fresh operational logs, so "keep 30" ≈ **keep 40 hours**. Effects:
`deep_sweep`'s 7-day `period_days` window is enforced against logs that live 40 h; the documented
07-26 patch that made cron's `deep_sweep.log` the attempt marker is defeated *twice over* (the file
was never created per I8, and would have been pruned anyway); `roster_frontier_watch.log` has no
surviving record. **And it bounds this report: a 7-day first-attempt success rate is not
computable from this box.** Fix: prune by age and by pattern (`20*_*.log` only), or move organ logs
into per-organ subdirectories.

**(b) Half of yesterday's "15-minute fixes" are not desk-reachable at all, and were mis-filed.**
```
$ sudo -n -l   → sudo: a password is required / user quant may not run sudo
$ id -nG quant → quant
```
`systemctl enable quant-blindrediscovery.timer`, `systemctl reset-failed`, unit edits
(`OOMScoreAdjust`, `MemoryMax`), the reboot, and journal access are **all root-gated**. Yesterday's
O4 called the timer-enable a "15 min" fix; it is a principal action that the desk cannot perform,
which is a large part of why 0/5 of those items moved in 24 h. **This reframes the whole carry-over
verdict:** the desk's fix lists must separate DESK-REACHABLE from PRINCIPAL-REQUIRED, and the
principal-required set must be paged as a batch, not buried in a report the pager cannot deliver
(I7). It also explains the cron/systemd duplication in I17/F9: cron is the only scheduler the desk
can edit, so it accretes lines that duplicate units it cannot touch. **That is not a design error;
it is the shape of the privilege boundary, and no cleanup will hold until the boundary is named.**

### I17 — §33'S CONVERSION-PRIORITY GATE IS COMPUTED BY ALL FIVE DIG ORGANS AND THE RESULT IS THROWN AWAY. [severity: HIGH — a governance law that is a literal no-op]

```
$ grep -rn '_MINE_PRIORITY' ops/
ops/run_frontier_miner.sh:23       _MINE_PRIORITY="$(.venv/bin/python scripts/mine_gate.py 2>/dev/null || true)"
ops/run_prospector_dig.sh:11      (same)
ops/run_blindrediscovery_dig.sh:11 (same)
ops/run_litminer_dig.sh:11        (same)
ops/run_dataaxis_dig.sh:12        (same)
$ grep -rho '\$_MINE_PRIORITY\|\${_MINE_PRIORITY' ops/*.sh | wc -l
0
```

**Five assignments, zero dereferences.** The adjacent comment claims the value is prepended to the
run's instructions "so the dig spends its FIRST effort converting". It is not prepended anywhere —
the variable is computed (paying the subprocess cost) and dropped. §33 states the gate is
"RECOMPUTED by `scripts/mine_gate.py` at dig time, not read from a file"; it is recomputed and
discarded, so mined-to-wired priority, tier ordering, and the `mine_generation_priors` steer have
**no effect on any dig**, in every organ they were written for, while the code asserts they fire.
This is the same class as I7's constant gate and I12's ignored `complete` flag: **a computed guard
with no consumer.** Fix: one line per wrapper (interpolate it into the prompt), plus a test that
the rendered prompt contains the gate text.

### I18 — THE MODULE THAT SERVES THE PUBLIC LEAK WAS WITHHELD FROM 13 EXTERNAL AUDITOR SEATS AS "INERT". [severity: HIGH — this is *how* I1 survived review]

```
$ sed -n '7p' docs/audit_shards/shard_01.md
- WITHHELD: 87 modules classified INERT (nothing reads them; deleting breaks nothing). They are
  named below. **If you believe an exclusion is wrong, say so** …
$ grep -n 'serve_dashboard' docs/audit_shards/shard_01.md
11:  …, screen_oi_ls_axes, serve_dashboard, setup_netlify, …
8012:  "quant-dashboard": "scripts/serve_dashboard.py",
$ systemctl is-enabled quant-dashboard; systemctl is-active quant-dashboard
enabled
active
```

`serve_dashboard` — the live, enabled, running systemd service that publishes the 552-file source
bundle and live P&L to the internet (I1) — is on the withheld-as-inert list, and the *same file*
maps `quant-dashboard → scripts/serve_dashboard.py` 8000 lines later. The document contradicts
itself, and 13 external review seats were steered away from the one module whose exposure is the
most severe finding of this sweep. `backfill_oi_ls_oos` (scheduled via `ops/run_oils_chain.sh`) is
mislabelled the same way. **The tier-1/tier-2 review split is generated by the same classifier**, so
the error is systematic, not a typo: whatever computes "nothing reads them" does not consult
`/etc/systemd/system/quant-*` or `ops/*.sh`. Fix: derive INERT from the same reference graph that
includes cron, units, and shell wrappers; add an assertion that no scheduled target can be
classified inert. **Validation:** `comm -12 inert_list scheduled_list` must be empty — it currently
returns 2 entries.

### I19 — EIGHT HAND-ROLLED SPEARMAN/IC IMPLEMENTATIONS DISAGREE ON TIES AND CONFLATE "NOT MEASURED" WITH "NO EDGE"; THE CORRECT ONE HAS ONE IMPORTER. [severity: HIGH — research correctness delivered as infrastructure]

```
$ sed -n '16,27p' libs/research/ic.py          # the canonical implementation
def _spearman(a, b):    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 3: return float("nan")
    ra = rankdata(a[m]); rb = rankdata(b[m])   # scipy rankdata → AVERAGE ranks for ties
$ sed -n '71,80p' scripts/stage_a_executor.py  # what the screening path actually uses
def _spearman(a, b):
    if n < 8: return 0.0, 0.0                  # ← "no edge", not "not measured"
    ra = sorted(range(n), key=lambda i: a[i])   # ← ORDINAL ranks: ties broken by array index
$ grep -rln 'from libs.research.ic' scripts/ libs/
scripts/run_crossexchange_backtest.py          # ← the only importer, of 264 scripts
```

Eight independent implementations (`micro_factory.py:120`, `stage_a_executor.py:71`,
`hl_skill_persistence.py:49`, `build_dev_factor.py:111`, `leakage_detector.py:53`,
`funding_persistence.py:60`, `iros_batch.py:40`, plus the canonical one) diverge on four axes: tie
handling (7 ordinal vs 1 average), NaN masking (2 of 8 mask), minimum-n (none/3/4/5/8), and the
failure sentinel (`nan` once, **`0.0` seven times**). Two consequences, both real:
1. **Ordinal ranks break ties by array index** — an artifact of input ordering. The affected inputs
   are heavily quantised by nature: `funding_persistence` ranks funding rates, `screen_oi_ls_axes`
   ranks OI/LS ratios. Ties are the normal case there, not an edge case.
2. **Returning `0.0` for insufficient/NaN data makes "we could not measure this" indistinguishable
   from "we measured it and there is no edge."** Under the SCREEN-ON-DISCOVERY duty every screen is
   a logged trial; a silent `0.0` becomes a recorded negative result, and the desk's negative record
   is supposed to be permanent knowledge. **Bad negatives poison the graveyard, which the
   constitution calls sacred, and they consume multiplicity budget for a trial that never ran.**
- **Fix:** delete all seven; import `libs.research.ic`. If a caller genuinely needs pure-Python,
  make it a thin re-export. Add a test asserting `nan` (never 0.0) on n<min and on all-NaN input.
- **Why this is an infrastructure finding:** the defect is not a wrong formula, it is the absence of
  one canonical implementation with one owner — the same shape as the 12 ntfy senders (O3) and the
  83 ad-hoc HTTP helpers. **A desk whose statistics live in eight copies cannot state its own
  method.**

### I20 — NOT ONE UNIT HAS A RESOURCE LIMIT OR AN OOM PRIORITY, ON A SWAPLESS BOX THAT HITS 153 MB FREE. [severity: HIGH — the ruin rail's survival is currently luck]

```
$ systemctl show quant-cashcarry -p MemoryMax,MemoryHigh,MemoryMin,CPUQuotaPerSecUSec,OOMScoreAdjust
MemoryMax=infinity  MemoryHigh=infinity  MemoryMin=0  CPUQuotaPerSecUSec=infinity  OOMScoreAdjust=0
   (identical on quant-deadman, quant-dashboard, quant-liquidations, quant-tunnel, quant-cro-ai, quant-dataaxis)
$ systemctl status systemd-oomd → not-found;   swapon --show → (empty);   free -m → free 355
$ sar -r  (07:50) → %commit 82.97, kbmemfree ≈ 153 MB
```

No `MemoryMax` on the organs, no `MemoryMin`/`OOMScoreAdjust` on the rails, no swap, no `earlyoom`,
no `systemd-oomd`. The kernel therefore picks its OOM victim by badness ≈ RSS, and today's RSS
ranking happens to be `claude` (this auditor, 347 MB) > `pytest` (294 MB) > `run_cashcarry_executor`
(143 MB) > `liquidation_listener` (126 MB) > `run_deadman_switch` (23 MB). **The correct victim
order — auditor first, dead-man last — is an accident of memory footprint, not a policy.** One
memory-hungry organ inverts it. No OOM kill has occurred (`dmesg | grep -ci oom` → 0), which is
survival bias, not safety (yesterday's S8 said the same thing about a 199 MB floor; it is 153 MB
today).
- **Fix (principal-gated, per I16b):** `OOMScoreAdjust=-900` + `MemoryMin=64M` on `quant-deadman`
  and `quant-cashcarry`; `MemoryMax=1G` on the organ/auditor units; a 2–4 GB swapfile or zram as a
  pressure valve (24 GB free today, though see I11 — do this before the disk fills, not after).
- **Desk-reachable half:** move scratch off `/tmp` (still 1009 MB of tmpfs RAM, O6 unfixed and
  growing) — that alone returns ~26% of total RAM.

### I21 — THE ONLY HUMAN-ESCALATION CHANNEL HAS THREE UNSYNCHRONISED READ-MODIFY-WRITE WRITERS, AND A CLOBBER ON IT ALREADY DESTROYED FOUR DAYS OF PAGES. [severity: HIGH]

`data/PRINCIPAL_ACTION.md` is written by three scripts, each reading-then-rewriting the whole file,
with **no lock of any kind**: `scripts/max_audit.py:2891` (read) → `:2922/:2926` (write);
`scripts/quota_verdict.py:115` → `:117` (`PA.write_text(existing + block)`);
`scripts/claim_escalate.py:58` (`PAGER.write_text(… + prev)`). Cron schedules two of them **five
minutes apart** (`15 12` max_audit, `20 */3` quota_verdict). `max_audit.py:2895` records that a
clobber bug on this exact file **destroyed every human-written page from 2026-07-24 to 2026-07-28** —
the incident behind commit `bd550c6` ("THE PAGE THAT DELETED THE PRINCIPAL'S DECISIONS"). The
specific bug was fixed; **the read-modify-write race that can reproduce the same outcome was not.**
Given I16b (many fixes are principal-only) and I7 (the pager delivers 16%), this file is the desk's
last reliable channel to a human — and it is the least protected shared state on the box.
- **Fix:** one append-only writer behind a `flock` (or an `os.replace` on a merged copy); the file
  becomes a rendered *view* of an append-only `principal_actions.jsonl`. Retirement: never.

### I22 — SQLITE CONTENTION IS UNDETECTABLE BY CONSTRUCTION: `busy_timeout` EXISTS IN ONE FILE, SIX WRITERS BYPASS IT, AND THE READ PATH REPORTS LOCK ERRORS AS "HONEST EMPTY". [severity: MED-HIGH]

```
$ grep -rn 'busy_timeout' libs/ scripts/          → libs/store/connection.py:17-26 only (2 lines)
$ grep -rn 'sqlite3.connect' libs/ scripts/ | wc -l   → 15   (6 bypass libs.store entirely)
$ sed -n '47,49p' api/db.py
except sqlite3.OperationalError:
    return []      # table/column missing -> empty, not an error
```

`libs/store/connection.py` is correct (`journal_mode=WAL`, `synchronous=NORMAL`,
`busy_timeout=5000`) and all nine writers that use it are clean. But six raw connects run with
`busy_timeout=0` — the **first** contended write raises immediately — and they include
`scripts/research_memory.py:46`, the writer of the hypothesis ledger the UNIVERSAL DUTY SET requires
every organ to append to (a lost insert there is a permanently lost experiment record), and
`run_crypto_testnet.py:136`, which also does inline DDL on the one DB still in `journal_mode=delete`
(`data/crypto_trades.sqlite` — readers block writers, crash-mid-write can corrupt).

Worse, `database is locked` **is** an `OperationalError`, so `api/db.py:47` renders every lock
collision as an empty result labelled honest, and `scripts/max_audit.py:108-119/137-145` wraps its
`sor_research.sqlite` reads in `except Exception: pass|continue` — the desk's own auditor silently
reports a smaller trial set under contention. There are 73 `except Exception: pass|continue` sites
across `libs/`+`scripts/`, and 5 cron lines discard both stdout and stderr. **A clean grep for
`database is locked` (which is what a parallel probe found — zero hits across all logs) is therefore
not evidence of health; the detector does not exist.** Contention pressure is real: 148 minutes/day
launch ≥4 cron jobs simultaneously and 6 minutes/day launch 8, with no cross-job mutual exclusion
anywhere (11 flock names, each used exactly once — all self-exclusion).
- **Fix:** route all 15 connects through `libs.store`; narrow the `except` clauses to the specific
  expected error and **log** the rest; add a `locked`/`OperationalError` counter that pages.
- **Genuinely clean, and worth recording:** `PRAGMA integrity_check` → `ok` on all 10 DBs; all
  `-wal` files 0 bytes, no stray `-journal`; 16,940 moat tape files `gzip -t` clean, 0 failures;
  the 8 largest `data/*.jsonl` and all 278 lake files (438,561 lines) parse with 0 unparseable
  lines, 0 truncated final lines, 0 duplicates. **The data is intact today. It is the machinery
  protecting it that is not** — and six orphan `-shm` files with 0-byte `-wal` (mtimes 07-30
  02:38–02:42) are the fingerprint of connections killed rather than closed, consistent with I12's
  SIGKILL path.

### I23 — ONE ALARM SURFACE, BOTH FAILURE MODES: `systemctl --failed` IS RED DAILY FOR ORGANS NOBODY READS, AND ONE ORGAN CAN NEVER GO RED AT ALL. [severity: MED-HIGH]

```
$ systemctl --failed
quant-cro-ai (exit-code/1, ran 9s)  quant-dataaxis (10s)  quant-prospector (11s)
quant-litminer (10s)  user@0.service (failed 3d16h)
$ systemctl show quant-frontier.service -p Result -p ExecMainStatus
Result=success  ExecMainStatus=0            ← while producing nothing
$ grep -n '|| echo' ops/run_frontier_rotation.sh
21: bash ops/run_frontier_miner.sh "$r" || echo "rotation: ${r} failed -- next invocation resumes it"
$ find data -maxdepth 3 -name 'frontier_*.log' | grep -v rollback
data/cro_ai_logs/frontier_cn_20260728T1524.log        ← one file, the unit's entire life
```

Yesterday called the four reds "stale". They are not stale — they are **refreshed every day**, each
organ dying at second ~10 (I15). Meanwhile `quant-frontier` is structurally incapable of failing:
`|| echo` swallows each region's exit code and `echo` is the last command, so the oneshot exits 0
whether 0 or 7 regions ran. **The same surface simultaneously over-reports (4 daily reds nobody
reads) and under-reports (1 organ that never goes red)** — and `prompts/panel_missions/production.txt`
names this exact class ("the timer is enabled is not the miner produced a dig"). Adjacent, same
shape: `data/recorder_bybit.log` and `data/recorder_spot.log` are 0 bytes and 9 days old while the
recorders are demonstrably alive (heartbeats fresh to the second) — the two files an operator would
check first are permanently misleading. Fix: `set -o pipefail` + accumulate region exit codes and
`exit 1` if any failed; `reset-failed` after successful catch-up (principal-gated); make the digger
wrappers log first (I15) so the reds carry a reason.

### I24 — ORGANIZATIONAL ENTROPY, MEASURED. [severity: MED — individually small, collectively the "desk never finishes its moves" tax]

- **25 true orphan scripts** of 264 (no cron, no unit, no shell wrapper, no python caller, no doc
  reference outside the mechanical `audit_shards` dump). Two corpus traps had to be removed first or
  the graph is noise: `data/rollback/` holds 20 full-tree snapshots (14,893 `.py` files) so every
  script self-matches, and `docs/audit_shards/shard_*.md` is a whole-repo dump so `docs_refs=13` is
  the noise floor. Six have **never** produced their artifact (`llm_code_auditor`, `hl_filter_test`,
  `hl_oos_elite`, `run_live_demo`, `run_onchain_history_backtest`, `run_reversal_costtest`).
- **One dead stratum, not many problems:** 17 scripts last wrote an artifact 33–40 days ago, and
  `api/` (imports FastAPI — `python -c "import fastapi"` → ModuleNotFoundError), `app/`,
  `migrations/`, `deploy/` (`WorkingDirectory=/opt/quant-platform`, which does not exist),
  `dist/` (41-day-old zip), `Dockerfile`/`docker-compose.yml` (`command -v docker` → not found) all
  share the same 38–40-day boundary. It is the pre-migration Windows/MT5 era. Nothing live depends
  on it; the cost is audit surface — including two `libs` packages (`libs/features`,
  `libs/stage14_5`, 18 files) with zero non-test importers, and **a second Kelly engine**
  (`libs/stage14/kelly.py`, Bernoulli/half-cap) sitting unreachable next to the live
  `libs/risk/kelly.py` (Gaussian) — a file that reads as money-path and is not.
- **21 duplicate module basenames** in `libs/` (5× `audit.py`, 6× `engine.py`, 3× `capacity.py`,
  2× `kelly.py`). This is the mechanism behind I18's misclassification: an import-name grep cannot
  tell which engine sizes capital.
- **The multiplicity bar lives in 11 hand-synced prompt copies.** `grep -lF 'Holm' ops/*_prompt.txt
  prompts/*.txt prompts/panel_missions/*.txt | wc -l` → 11; the 7 `frontier_*_prompt.txt` share 69
  of 83 lines (83%), and `blindrediscovery_dig_prompt.txt` shares **0 of those 69** — it has already
  fallen out of sync. Given that the desk fixed a Holm-bar defect this morning, **a bar that lives
  in 11 copies is a bar that will drift again.** Fix: one included `GOVERNANCE.md` fragment, one
  edit site.
- **One panel seat is missing the desk's #2 supreme objective**, and it is the production auditor:
  `for f in prompts/panel_missions/*.txt; do grep -q 'CO-SUPREME OBJECTIVE #2' $f || echo MISSING: $f; done`
  → `MISSING: prompts/panel_missions/production.txt`. The blind-spot law firing on itself.
- **Repo litter:** 8 `.bak-20260716` files including two inside `libs/execution/` (the money-path
  package: `binance_testnet.py.bak-20260716`, `binance_spot_testnet.py.bak-20260716`), tracked root
  strays `_audit_gate_probe.py`, `_audit_gate_probe2.py`, `_audit_rows.pkl`, plus an untracked 6.1 MB
  `_audit_prepared.pkl`; `tools/` is empty and referenced nowhere; `data/sor.sqlite` is a 0-table
  decoy still probed by `max_audit.py:132`; `data/tunnel_heartbeat` frozen 18 days; `llm_panel.json.bak`
  and `.bak2` still in the secrets directory.
- **`ops/run_oils_chain.sh` has no scheduler and is the only caller of `backfill_oi_ls_oos.py`** —
  the pre-registered cross-sectional OOS test for the OI/LS axis can only run by hand, while its
  upstream collector runs daily. The desk accumulates the input and never runs the test.
- **Git history is squashed** to a single `2026-07-16 "baseline: desk state 2026-07-16"` commit for
  every pre-migration path, so filesystem mtime is the only dating evidence for the dead stratum.
  Worth knowing before anyone tries `git log` archaeology on a deletion decision.

### I25 — THE ALERT CHANNEL IS AN UNAUTHENTICATED PUBLIC TOPIC WITH A GUESSABLE NAME, SO A THIRD PARTY CAN BOTH READ EVERY PAGE AND SILENCE THE RUIN RAIL ON DEMAND. [severity: HIGH — security × ruin rail]

```
$ python -c "json.load(open('data/secrets/ntfy.json'))"      # shape only, value withheld
key: topic | len(value): 12 | looks_random_suffix: False
$ stat -c '%s bytes, mtime %y' data/secrets/ntfy.json
25 bytes, mtime 2026-07-16 12:42:31
$ grep -n 'guessable' docs/GAP_REGISTER.md
213:| 3 | **Pager delivery unverified on new topic** | … | Test page auto-fires … to
    ntfy.sh/Quant_Alerts … SECURITY: guessable public topic — rotate to suffixed topic after
    confirmation. | operator+brain | 07-16 | open |
```

Twelve characters, no random suffix, untouched since 2026-07-16 — i.e. still exactly the topic the
register names and flags. `ntfy.sh` topics without auth are **world-readable *and*
world-writable**. Three consequences, of increasing severity:

1. **Confidentiality:** anyone who guesses the topic subscribes to every page — heartbeat deaths,
   risk actions, growth defects, principal escalations. Guessing is not hard once I1 tells an
   observer the desk exists and what it trades.
2. **Integrity:** anyone can *publish* to it. Injected pages are indistinguishable from real ones on
   the principal's phone.
3. **Availability — the one that matters most:** `scripts/run_alerts.py:43-89` mutes **all** pushes
   for one hour after any 429 (yesterday's O3). ntfy rate-limits per topic. Therefore **a third
   party who knows the topic can deliberately flood it and switch off the desk's entire alerting —
   including a Tier-3 ruin-rail page — for an hour at a time, repeatably, with a shell loop.** That
   converts an availability nuisance into an attacker-controlled kill switch on the alerting rail.
   The desk has already experienced the failure accidentally (36 hard 429s and 252 suppressed pushes
   in 7 days, I7); nothing distinguishes an accident from an attack.

Verified *not* leaked: the topic string does not appear in the publicly served bundle
(`grep -c 'Quant_Alerts' web/algo_complete.txt web/algo_full.txt` → `0/0`) and no `hc-ping` URL is in
`web/`. So this is guessability, not disclosure — but it has been a known, documented, *open*
finding for 14 days on the channel that carries ruin-rail alarms.
- **Fix (5 minutes, free):** rotate to a long random topic suffix; better, move URGENT to an
  authenticated provider (ntfy supports access tokens; healthchecks.io is already wired as the
  second channel) and keep the public topic for routine digests only — which is O3's two-lane
  design, now with a security reason as well as a capacity reason. **And make the backoff
  per-lane**, so flooding the routine topic cannot mute the urgent one.
- **Validation:** publish to the old topic after rotation and confirm nothing arrives; confirm an
  URGENT page still lands while the routine lane is in backoff (that is O3's T3 test, which has
  never been run).

### I26 — COVERAGE IS INVERTED ON THE MONEY PATH, AND THE CONFIG MAKES THE MOST IMPORTANT CODE UNMEASURABLE. [severity: HIGH — test depth]

Measured, not configured (`COVERAGE_FILE` redirected to `/tmp` so the repo artifact stayed pristine):

```
pytest tests/execution tests/risk tests/ops tests/monitoring tests/scripts tests/self_improvement \
  --cov=libs/execution --cov=libs/risk --cov=libs/ops … --cov-report=term-missing
→ 371 passed in 13.31s, TOTAL 74% (3496 stmts, 804 miss)
```

| module | coverage | uncovered |
|---|---|---|
| `libs/execution/binance_testnet.py` | **18%** | 173/224 |
| `libs/execution/binance_live.py` | **22%** | 155/215 |
| `libs/execution/binance_spot_testnet.py` | **22%** | 94/127 |
| `libs/execution/binance_spot_live.py` | **41%** | 67/119 |
| `scripts/run_deadman_switch.py` (Tier-3 rail) | **17%** | body 120–297, 8 tests total |
| `scripts/run_deadman_stranded_sweep.py` | **0%** | 21–94 |
| `libs/self_improvement/forecast_calibration.py` | **0%** | 43 stmts, imported by `research_cycle.py`, zero tests |

**The code that actually places orders is the least-covered code on the money path**, and the
Tier-3 ruin rail's entire operational body is untested. Contrast with what *is* well covered —
`engine.py` 96%, `staging.py` 95%, `sizing.py` 95%, `risk_controls.py` 95%, `drawdown.py` 94%,
`gate.py` 92%, `kelly.py` 90%, `libs/ops/watchdog.py` 100%, `kill_switch.py` 100%. **The pattern is
that pure logic is tested and I/O boundaries are not**, which is the normal shape of this problem and
also where venue-truth bugs live (the desk's own incident history — COOKIE walked through zero, the
reduceOnly fix, the fee-blind attribution — is entirely I/O-boundary bugs).

Two config defects hide it:
1. `pyproject.toml:158-159` → `[tool.coverage.run] source = ["libs"]`. **`scripts/` is never in
   scope, so `scripts/run_cashcarry_executor.py` — 1353 lines of live executor — appears in no
   coverage number the default config can produce.**
2. `--cov=<path>.py` (file form) is **silently ignored** by coverage — it emits
   `CoverageWarning: module-not-imported` and `No data was collected`. So an explicit attempt to
   measure the rail returns nothing, with no error a human would notice.
- **Fix:** add `scripts` to `source`; set a per-file floor for the four venue clients and the
  deadman; write boundary tests against recorded venue responses (the desk already has an
  `execution_tape` at 94% — replaying real fills is the cheap path to those 173 uncovered lines).
- **Also:** `.coverage` in the repo root is **git-tracked, 41 days stale, and was produced on a
  Windows box** — `paths: C:\Users\dell\quant-platform\libs\stage15\*`, 11 files, one non-money
  subpackage, zero execution/risk files. The only coverage artifact in the repo describes neither
  this machine nor the money path. Delete it or regenerate it in CI.

### I27 — THE ADVERSARIAL CROSS-ENGINE CHECK IS DECORATIVE: IT RUNS NOWHERE AND HAS NO PRODUCTION CALLER. [severity: MED-HIGH — L1.7 adversarial validation]

```
$ pytest -q … | grep SKIPPED
SKIPPED tests/backtest/test_cross_engine.py:45: could not import 'backtrader'
SKIPPED tests/backtest/test_cross_engine.py:53: could not import 'vectorbt'
$ grep -nE 'pip install' .github/workflows/ci.yml
33: pip install -e ".[dev]"          ← never the `crosscheck` extra
$ grep -rn 'verify_against_backtrader|verify_against_vectorbt' libs/ scripts/ app/
libs/backtest/__init__.py:  (re-exports only — no caller anywhere)
```

`vectorbt` and `backtrader` are absent locally **and** never installed by CI, so
`test_engine_matches_backtrader` / `test_engine_matches_vectorbt` execute **nowhere, ever** — the
suite's only 2 permanent skips are exactly these. pyproject describes the safeguard as *"adversarial
finding W3.2 — never trust a single bespoke engine."* What does run is `verify_against_vectorized`,
a numpy re-implementation by the same author — **agreement between two implementations of the same
idea is not independent corroboration**, which is precisely what L1.7 (adversarial validation:
"surviving disproof increases confidence, agreement never does") warns against. Fix: install the
`crosscheck` extra in CI (or a weekly job), and call the verifier from the gauntlet on at least one
candidate per campaign so the check has a *production* caller and not only a test.

## 4. WHAT WE TEST NEXT — concrete experiments

Every item names its success criterion and its retirement condition. **Yesterday's T1–T8 remain
valid and unrun** (§0) and are not repeated here except where this sweep sharpened them. Ordered by
ROI, and split by who can actually perform them (I16b).

**DESK-REACHABLE (working-tree edits, no root, today):**

- **T1 — Un-stick the sweep organ, then measure the quota recovered.** Add
  `artifacts=("docs/research/deep_sweep/",)` to the `deep_sweep` `OrganSpec`
  (`libs/ops/organ_catchup.py:69`). *Success:* `grep -c 're-fired deep_sweep'` stops increasing once
  a day's reports exist; `owed=deep_sweep quota=DEAD` probe count per day drops from ~200 toward 0;
  and — the real metric — `dataaxis`/`prospector` first-attempt success rises now that they are not
  competing with 9 redundant sweeps. *Retirement:* never; convert into a standing assertion that
  every `OrganSpec`'s success test keys on an artifact, not on stdout.
- **T2 — Make the exposure regression-tested, not just fixed (I1).** After removing the bundles,
  binding `127.0.0.1`, and adding CF Access: assert from an unauthenticated vantage that
  `/algo_complete.txt` and `/cashcarry_live.json` return 403/404. *Success:* both non-200, with the
  principal's phone still able to load the dashboard. *Then wire the same two `curl`s into
  `data_health.py`* — an exposure that recurs silently is worse than one found once. *Retirement:*
  never.
- **T3 — Negative control on the Holm bar (I12).** In a scratch tree, corrupt
  `data/axis_shadow_state.json`; assert `concurrent_m()` does **not** decrease and that an alert
  fires. *Success:* the test fails today (proving the defect) and passes after `concurrent_m()` is
  made to fail closed. *Retirement:* never — it guards the only multiplicity control on the only path
  to capital.
- **T4 — Negative control on the pager's own paths (I3, I7).** (a) Point the heartbeat URL at a
  wrong path in a scratch env → the new `external_heartbeat_unfed` condition must fire; (b) run
  `run_alerts.py` with the OAuth token present → `auth_broken` must **not** fire; (c) inject a
  `sleep 90` stub for `run_leverage_opt.py` → the tick must still page (I6). *Success:* all three
  currently-impossible assertions pass. *Retirement:* never.
- **T5 — Restore drill, and run it BEFORE building the backup (I2/O1).** Attempt a restore first and
  document the failure — that is the artifact proving O1 and refuting GAP #13's `resolved`. Then wire
  restic → storage box/B2 nightly + a weekly scripted drill asserting sha256 manifest + row counts on
  3 sentinel tables + one jsonl line count. *Success:* two consecutive green drill artifacts.
  *Retirement:* never (rail-adjacent).
- **T6 — Disk deadline (I11).** Add a disk-% + inode check to `data_health.py` with pages at 80/90%;
  independently, on a scratch loop-device filesystem at 100%, assert the top ~10 state writers fail
  *closed* rather than truncating. *Success:* the alarm exists and the truncation test passes after
  `os.replace` is applied. *Retirement:* the alarm never; the compaction policy retires if the tape
  moves off-box.
- **T7 — One canonical statistic (I19).** Delete the seven hand-rolled Spearman implementations,
  import `libs.research.ic`, and add a test asserting `nan` (never `0.0`) on n<min and on all-NaN
  input. *Success:* `grep -rc 'def _spearman' scripts/` → 0, and re-running the two most recent axis
  screens reproduces their verdicts within tolerance — **or does not, which would be a far more
  important result and must be reported either way.** *Retirement:* never.
- **T8 — Mechanise the ledger wire (I4).** Have the sweep runner parse `### I<n> —` headers and call
  `scripts/recommendations.py add`, failing the organ if a ≥1200-byte report produced 0 rows; add the
  same post-run assertion to the other seven organ runners. *Success:* row count for
  `source=deep_sweep-infrastructure-20260730` ≥ the number of I-headers in this file; a sweep that
  reports and rows nothing fails loudly. *Retirement:* after 4 consecutive green weekly sweeps the
  manual back-row duty retires.
- **T9 — Close the observability floor (I15, I16a).** Move `LOG=` above `brain_auth_check` in all
  four dig wrappers; change `run_cro_ai.sh:98`'s prune to age-based and pattern-scoped. *Success:* a
  simulated auth death leaves an attempt marker and `organ_owed` flips True; log retention exceeds 7
  days so the next sweep can compute a real first-attempt success rate. *This test's success
  criterion is that the NEXT audit can measure something this one could not.*
- **T10 — Rotate the alert topic and prove the lane split (I25, O3).** *Success:* publishing to the
  old topic delivers nothing; an URGENT page arrives while the routine lane is deliberately held in
  429 backoff (set the backoff file first — that is the actual test, and it has never been run).

**PRINCIPAL-REQUIRED (root; batch these into one page — they cannot be done by the desk, I16b):**

- **T11** `usermod -aG systemd-journal quant` — *the single highest-leverage root action*: it converts
  an entire stream of failure diagnostics from invisible to readable and unblocks U8/U10 permanently.
- **T12** A read-only Hetzner API token in `data/secrets/` → closes U5 forever and makes the backup
  claim in GAP #13 continuously monitorable instead of hearsay.
- **T13** `systemctl enable quant-blindrediscovery.timer`; `systemctl reset-failed`;
  `OOMScoreAdjust=-900` + `MemoryMin=64M` on `quant-deadman`/`quant-cashcarry`, `MemoryMax=1G` on the
  organ units; a 2–4 GB swapfile (before the disk fills, T6).
- **T14** The reboot drill (kernel + libc6 pending 18 days). *Success:* every heartbeat fresh <10 min
  post-boot, tunnel serving, zero human intervention — which also converts "has this box ever
  recovered unattended?" from an assumption into evidence.

## APPENDIX A: PERSPECTIVE COVERAGE LOG

- **INTERNAL (measured, not configured):** public unauthenticated `HTTP 200` on a 1.98 MB source
  bundle (I1); 0/12 of yesterday's findings fixed (§0); disk 0.75 GB/day → ~32 days (I11); 10
  re-fires of one weekly organ (I13); pager condition-coverage 16.5% with ~49% of delivered pages a
  permanent false positive (I7); 2885 futile respawns, +504 in 25 h (I23/O9); 7/7 CI gate failures
  (I10); 27 ledger rows undisposed past the 24 h bar (I4); RAM floor 153 MB, zero swap (I20); clock
  offset 0.46 ms (S1); 16,940 tape files intact (S2).
- **EXTERNAL (how a world-class desk would differ):** auth on anything that serves positions;
  offsite DR with drilled restores; one canonical statistics library; one pager library with priority
  lanes and delivery receipts; resource limits and OOM policy on every unit; a reference graph that
  cannot classify a running service as inert; env parity between gate and prod. **None of it exotic
  — all commodity practice, skipped while rarer things were built well** (the catch-up layer's
  serialisation, S9, is better than commodity).
- **FUTURE (2–3 y):** the cheap-model tail of `_BRAIN_MODEL_CHAIN` should absorb mechanical organ
  steps (log triage, collection digests, ledger rowing) so frontier-model quota stops being the
  availability floor; litestream-style continuous SQLite replication turns the SoR backup into a
  background stream rather than a nightly event; one declarative orchestrator replaces
  cron+watchdog+ensure+catchup — **but note I16b: the desk cannot edit units, so "systemd-only" is
  only reachable if the privilege boundary moves first.** That boundary, not the tooling, is the real
  2–3-year constraint.
- **CONTRARIAN (assumptions actively tested, several falsified):** *"the data is probably fine"* →
  **confirmed** for once, with 16,940 files checked (S2) — worth stating because it redirects effort
  to the machinery. *"a clean grep for `database is locked` means no contention"* → **falsified**
  (I22: the detector cannot exist while `OperationalError` renders as empty). *"the register knows
  what's done"* → **falsified** (I2: DR marked resolved for 14 days). *"the alert channel is a
  capacity problem"* → **falsified** (I25: it is also an attacker-controlled mute). *"unfixed
  findings mean the desk was lazy"* → **falsified** (I16b: half were never desk-reachable). *"more
  supervisors = more resilience"* → **falsified again** (I6: the supervisor's own crash path skips the
  pager). *"the weekly sweep runs weekly"* → **falsified** (I8/I13: it has never started from cron
  and can never finish).
- **GREENFIELD:** rebuilt today with only validated knowledge: one pinned env; systemd-only
  scheduling with `Persistent=true`; ONE SoR with a streaming replica; one pager library, two lanes,
  authenticated, with receipts; every organ's success test keyed to its artifact; a private dashboard
  behind Access with no source bundle anywhere near the web root; one statistics module; restic timer
  + weekly drill; no Windows residue. **Historical-baggage score: moderate-to-high** — one coherent
  dead stratum (I24) plus a privilege boundary that has silently shaped the architecture. **Lock-in:
  low** — every component is commodity; the entropy list in I24 is the worthwhile subset of a
  migration, not the whole thing.
- **FRONTIER (recently practical, unexploited):** Cloudflare Access free tier (fixes I1 in minutes,
  keeps phone access); Hetzner API + read-only token (fixes U5 forever, ~1 min); Hetzner storage box
  €3.2/mo or B2 at ~$0.03/mo for 7 GB compressed (fixes I2); litestream for SQLite; `systemd-oomd`
  (absent — `not-found`) or `earlyoom` for I20; ntfy access tokens + priority topics for I25;
  healthchecks.io read API for U6; `uv lock` (uv is already on the box, half-adopted);
  `pip-audit`/`osv-scanner` in CI (O12, still nothing).
- **NEGATIVE-SPACE SWEEP (never done, now named):** never probed the raw public IP (U1); never
  restored a backup (T5 — there is nothing to restore); never rebooted in the box's entire life
  (T14); never read the systemd journal, ever, by any organ (I15 — the desk is not in the group);
  never verified an external heartbeat landed (U6); never rotated the alert topic despite a 14-day-old
  security note (I25); never tested that an URGENT page survives a routine-lane 429 (T10); never
  measured a full-suite runtime (U9); never checked whether `INERT` classifications agree with the
  scheduler (I18); never counted how many statistics implementations the desk has (I19); never
  asked whether a computed guard has a consumer — three did not (I12 `complete`, I17
  `_MINE_PRIORITY`, I5 `_ERR`).

## APPENDIX B: five-things classification

- **Weaknesses (current failures):** I1 public bundle + live P&L; I5 dead invariant log; I6 pager
  decapitation; I7 constant-true auth alarm + 16.5% coverage; I10 7/7 CI failures; I12 fail-open Holm
  bar; I13 infinite sweep retry; I14 unlocked brain spawner; I17 discarded conversion gate; I18
  inert-vs-running contradiction; I19 eight statistics; I23 both alarm failure modes on one surface;
  I25 guessable alert topic.
- **Bottlenecks (limit improvement):** the brain quota pool — now partly self-inflicted (I13, I14);
  RAM/no-swap ceiling on organ concurrency (I20); **the privilege boundary (I16b), which is the
  bottleneck nobody had named**; the 40-hour evidence horizon (I16a), which bounds what any audit can
  measure; CI runtime (I10), which bounds change velocity.
- **Capability gaps (simply do not exist):** offsite DR + drill (I2); disk/RAM alarms (I11);
  lock-contention detection (I22); page-delivery receipts (I7); journal access (I15); dependency-vuln
  scanning (O12); a units/ownership manifest; an exposure regression test (T2).
- **Compounding multipliers (raise the value of every future improvement):** **I4** (mechanised
  ledger rowing — turns every future audit's output into tracked work; the single highest multiplier
  here); **T11** (journal access — makes every future failure diagnosable); **I13's one-tuple fix**
  (recovers the quota that all other organs need); **I16a** (a 7-day evidence horizon makes the next
  audit measurably better than this one); **T5** (protects all accumulated forward evidence forever);
  **I19** (one canonical statistic makes every future screen comparable).
- **Unknown unknowns (probed where confidence was lowest):** the provider/console layer, closable
  with one token (U5); the never-read journal stream (U10); and the 73 swallowed exceptions — reading
  code around silent `except` clauses produced three real defects this sweep (I12, I17, I22), so that
  seam is **not** exhausted and is the recommended starting point for the next infrastructure audit.
