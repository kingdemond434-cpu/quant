# WEEKLY DEEP COLD AUDIT — INFRASTRUCTURE — 2026-08-01

STATUS: COMPLETE

Auditor: infrastructure subsystem, weekly deep cold sweep (doctrine v2).
Method: outcome-not-config — every claim carries its proving command + output. READ-ONLY run.
Predecessor: `docs/research/deep_sweep/20260731_infrastructure.md` (F1–F10, T1–T8). **This sweep's
first duty is CONVERSION PARITY (L1.28b): which of yesterday's findings actually moved.**

## SCORES

- **current_capability_pct: 54%** (yesterday: 62% — this is a *measurement* correction, not a
  regression; three findings converted and the sweep went deeper). The load-bearing infrastructure
  genuinely works: data integrity is provably clean at 1.67M records (S1), executor recovery is
  observed not configured (S2), the ruin rail is armed (S12), secrets hygiene survived hard probing
  (S4), and the test suite's discipline is tier-1 (S5). What drags it to 54% is that **the
  measurement layer is the weakest layer** — a ~29%-precision pager (G27), 11 fences that green on
  absent input (G28), a capital ceiling that is a tautology (G0), an organ-liveness metric reading
  back a log-retention constant (G7), and a backup drill that compares a file to itself (G29). A
  desk whose instruments are broken does not know its own state, and five of this sweep's findings
  were *invisible to the desk's own fences by construction*.
- **practical_ceiling_estimate: 92%.** Nearly everything here is in-repo and self-serviceable; the
  residual ~8% is off-box DR and a second box, which need a small recurring spend and an operator
  action.
- **ceiling_gap: 38 pts** — and unusually cheap. **T1, T2, T3, T7 and T13 are hours of work in
  total** and between them fix a live unhedged-position blind spot, eleven decorative fences, the
  destruction of the desk's forensic record, and both false CRITICALs.
- **opportunity_cost_1y: VERY HIGH, and concentrated in three tails.** (1) *Security*: G2 is not a
  risk, it is a **live disclosure** — the research web root and capital plan are being served
  anonymously right now, and G1+G3 together are a working RCE into the box that will hold live
  keys. (2) *Capital*: G0b means every capacity band divides by a number ~3× too large, so the
  gauntlet is retiring fillable edges as "outgrown" — a direct, ongoing L1.18a defect. (3)
  *Permanent loss*: G29's irreplaceable set is smaller than believed (7.4 MB + 0.82 GB, not 8.7 GB)
  but has **zero verified copies**, and the organ meant to protect it self-certifies PASS. Chronic
  costs: G16 burns LLM quota on a loop and starves every other organ; G8 runs unvetted code ~50% of
  the time and taxes both cores continuously.
- **confidence: 0.92.** Every finding carries a reproduced command with output; the two headline
  ones (G0's tautology, G7's reaper) were each derived twice by independent paths, and G7 was found
  independently by two sweeps from opposite directions. Softest: U2 (futures depth
  replaceability), G0b's 3× harm estimate (depends on which venue figure is correct — that is the
  pending decision, not an error), and U8 (OOM risk argued, not measured).
- **unknown_unknown_score: 0.35** — down from 0.4. The largest previously-unknown seam (Cloudflare
  Access) was *resolved*, and it resolved badly. Remaining uncertainty concentrates in things one
  operator command settles (U1, U3, U5, U6) rather than in unexplored architecture. The genuine
  unknown-unknown risk now sits in what the broken instruments have been hiding: G7 deleted the
  evidence base, so **any prior conclusion about organ liveness is unreliable and must be
  re-derived after T3.**
- **info_gain_if_investigated: VERY HIGH for U1, U3, U9, U10** — each is a yes/no that swings the
  risk picture, and U10 resolves itself for free at 03:55 today. HIGH for U2 (sets the storage
  spend). MED for U5–U8, U11, U12.
- **expected_alpha_contribution: indirect but larger than it looks.** G0b is the direct one — a 3×
  book overstatement is silently rejecting the small-capacity edges §42 exists to hunt. G16 is the
  throughput one — a weekly organ re-firing every 45 min starves every research seat on the desk.
  G17's 1,390 undeduped rows are a live 2× inflation on two axes that any Stage-A screen would
  inherit, which under L1.25a is *negative* discovery.
- **expected_compounding_contribution: VERY HIGH — this is where the real return is.** T2 (one
  token, eleven fences), T3 (one glob, restores the entire evidence base the audit layer runs on),
  and T5 (scratch-checkout gating, closes an RCE and the unvetted-execution window together) are
  the ⚙ multipliers: each removes a whole recurring silent-failure class rather than one instance,
  and each raises the reliability floor every future organ compounds on. **T3 in particular is
  prerequisite to trusting any future infrastructure audit.**
- **ceiling_expansion: the ceiling here is bounded ORGANIZATIONALLY and by ONE BOX, not
  technologically** — and both bounds are movable. The organizational bound is the cron⊕systemd
  split (two planes, no shared locks, a manifest fence structurally blind to duplicates, 12 seat
  lines that are permanent no-ops); collapsing to one plane deletes G14, G17 and G18 at the root.
  The physical bound is 2 cores / 3.8 GB / no swap shared between the money path and every research
  organ — a second small VM for the research pool deletes G14's OOM exposure, G16's starvation,
  G8's CPU contention and makes G5 measurable, for one recurring line item. **Notably, nothing here
  is gated on a new model, paper, dataset or API** — the frontier lens came back empty, and that
  emptiness is itself the finding: this subsystem's gap to tier-1 is entirely one of engineering
  discipline and measurement honesty, both of which the desk already demonstrably possesses (S6,
  S7, S9) and applies unevenly.

**THE ONE-LINE READ:** the desk's *machinery* is in better shape than its *instruments*, and
almost every finding in this report is a case of something measuring a proxy its producer stopped
writing — a key name (`generated` vs `ts`), a file existence, a log that gets deleted, a number
divided by itself. **Nine of this sweep's findings share that single shape**, and the desk has
already written the correct pattern down in twelve places (S6). Copying it to the other eleven is
the cheapest high-value work available.

## 0. CONVERSION LEDGER — what happened to yesterday's F1–F10

L1.28b makes a found-unfixed defect an unbooked loss aging at its stated ROI. Yesterday's report
carried 10 findings. This is what the artifacts say happened to them, in one day of 157 commits
(`git log --since="2026-07-31 00:00" --oneline | wc -l` → `157`).

| # | yesterday's finding | status today | evidence |
|---|---|---|---|
| F9 | `miner_seats_productive` floor welded at 0.0 | **CONVERTED** | `data/ratchet_floors.json` → `0.090909`, recorded `2026-07-31T07:07:01Z` |
| F10 | `pager_delivered_24h` floor welded at 0.0 | **CONVERTED** | same file → `1.0`, recorded `2026-07-31T07:07:01Z` |
| F5a | no disk fence anywhere | **CONVERTED** | commit `c5f2ed4` "Moat writers measured the wrong filesystem: disk guard now probes the path it writes to" |
| F2 | push-capable PAT in the remote URL | **NOT FIXED** | see G1 — same 40-char `ghp_` token, unchanged since Jul 18, no credential helper |
| F8 | both HTTP servers bind `0.0.0.0`, tunnel Access unknown | **NOT FIXED, AND WORSE** | see G2 — `serve_dashboard.py:47` `default="0.0.0.0"`, `ops_server.py:53` `("0.0.0.0", …)`; and the Access question is now **answered: there is none** |
| F4 | quota referee dead 8 days | **NOT FIXED — and now diagnosed** | see G4 — it is a one-shot latch, not a crash |
| F5b | zero offsite copy of the moat | pending (durability sweep in flight) | — |
| F1/F3/F6/F7 | cron duplication / CI non-determinism / false pager / tunnel respawns | pending (sweeps in flight) | — |

**Conversion read:** three of ten converted inside 24h, and the two ratchet floors were converted
within ~7 hours of the report landing — that is a genuinely fast repair loop and it is the
strongest thing this subsystem did all week. But the **two CRITICAL items (F2, F8) did not move**,
and they are the two whose blast radius is the whole desk. The repair loop is preferentially
converting the CHEAP findings. That ordering is itself the defect (see G8).

## 1. WHAT WE KNOW (validated strengths, each with proving command)

These are outcome-verified, not configured. Several are genuinely tier-1 and should not be touched.

**S1. Data integrity under concurrent append is CLEAN — and structurally so, not luckily.** The
long-standing worry (multiple processes appending to shared `.jsonl`) was measured, not assumed:
**505,493 lines across all 330 `.jsonl` files under `data/` → 0 unparseable, 0 duplicates**; plus
**1,168,671 records across 240 sampled `.jsonl.gz` → 0 bad, 0 gzip CRC errors**. The classic
`json.dump(obj, f)` + separate `f.write("\n")` interleave bug **does not exist anywhere in the
repo** — all hot writers pre-concatenate and issue one `write()` per record. Zero gzip CRC errors
across 1.17M records is decisive: interleaved DEFLATE would be catastrophic and unmissable. Writers
also target provably disjoint trees. **This closes a suspected risk with evidence — worth as much
as a finding.**

**S2. Recovery of the live executor has been SEEN to work, dated and unattended.**
`journalctl -u quant-cashcarry --since "5 days ago"` shows six distinct PIDs at ~3.4-min intervals
on 2026-07-31 08:39→08:58, each dying on `HTTP Error 418`, each restarted by systemd
`Restart=always`. The autonomy check (battery #7) passes for the executor — this is *observed*
recovery, not configured recovery. (Its dark side is G13/G14.)

**S3. Clock discipline is excellent.** `chronyc tracking` → `System time: 0.000248287 seconds fast
of NTP time`, RMS offset 152 µs, skew 0.033 ppm, stratum 3, synchronized. For a desk timestamping
venue data this is a real asset. (Monitoring of it is absent — U-block.)

**S4. Secrets hygiene at the filesystem layer is correct and was probed hard.**
`data/secrets/` is `drwx------`, all 14 real secrets `-rw-------`, only `*.example.json` templates
world-readable. `find / -maxdepth 4 -name "*.json" -path "*secret*"` → **zero** stray copies.
`grep -rl "api_key\|apiKey\|secret_key" data/cro_ai_logs/` → **zero files**. Four strict secret
patterns across all 73 files in the public web root → **0 hits**. Live-tested path traversal
(`/../data/secrets/binance_live.json`, URL-encoded, `/../../../../etc/passwd`, `/../.git/config`)
→ **all HTTP 404**, no symlinks in `web/`. `quant` has **no sudo at all**. SSH is pubkey-only
(`PasswordAuthentication no`). Repo is **private** (unauthenticated API → 404). CI is safe from
fork PRs (`pull_request`, not `pull_request_target`; zero `secrets.` references). ufw is active
with default DROP; fail2ban and unattended-upgrades both active+enabled, 0 pending security
updates. **The PAT (G1) and the tunnel (G2) are the exceptions, not the rule.**

**S5. The test suite's *shape* is tier-1.** 2,754 tests / 278 files, **0 collection errors**;
`tests/ops` 138/138 in 19 s; **zero unconditional skips, zero xfails**; no vacuous tests (AST-swept
all 278 files — 4 candidates, all legitimate exception-as-assertion smoke tests); **59/59 RNG uses
seeded**, 0 unseeded; no live network (the single `urlopen` is monkeypatched); no test directories
excluded in `pyproject.toml`. **TODO/FIXME/XXX/HACK density is 0** across libs/ and scripts/, and
there are **zero truly bare `except:`** (94 uses of the sanctioned `contextlib.suppress`). The
coverage *targets* are the gap (G24), not the discipline.

**S6. Twelve fences refuse correctly on absent input, and they are the template for fixing the
other eleven.** `check_ratchets`, `check_conversion`, `check_exploration`, `check_freshness`,
`check_law_families`, `check_strategy_breadth`, `check_scheduler_manifest`, `check_shell_hygiene`,
`check_constitution_core`, `check_miner_runway`, `check_sizing_derivation`, `run_alert_canary` all
exit non-zero on `UNMEASURED`. `check_ratchets.py:180/222/288` is the model implementation.

**S7. `run_alert_canary.py` is the best-behaved monitor on the desk.** It reports its own SPOF
every hour rather than greening it: `NOT-ARMED (human step owed): drop credentials at
data/secrets/alert_channels.json -- until then ntfy is the only path, which is the single point of
failure gap #38 exists to remove`. It also fails **closed** on a missing ledger. This is exactly
the refusal vocabulary L1.41 condition 1 demands, implemented before the law existed.

**S8. The GitHub deploy path's *network* handling is the best-hardened code in the repo** —
4 retries with 0/2/4/8 s backoff, fail-closed on dirty tree / divergence / ff-failure, a durable
`fetch-failed` record, and a mid-gate tree-move guard. (Its *ordering* is G8 and its *trust model*
is G3 — but the retry engineering itself is exemplary and should be copied to the venue connectors,
which have none.)

**S9. Both ratchet floors flagged yesterday were converted within ~7 hours**, and the ratchet
system now has **zero information-free floors, zero stale floors (>7 d), and zero proving commands
pointing at missing scripts** — all 10 entries verified, all 5 referenced scripts `ls`-clean. The
repair loop, when it engages, is genuinely fast.

**S10. `flock` is working where it is applied, and no stale locks exist.** `lslocks` shows all six
held locks mapping to live PIDs; the previously-doubled watchdog is now a single
`sh → flock → python` chain. All 45 distinct lock paths were inventoried. (Where locks are *absent*
or *mismatched* is G17/G18.)

**S11. Code and the decision ledger have a real offsite copy.**
`git rev-list --left-right --count origin/master...HEAD` → `0  0`; repo 39.85 MiB packed,
`garbage: 0`, no large blobs in history. Code, docs and 13 tracked `data/` files (including
`decision_ledger.json`, 545 KB) survive box loss. The gap is everything else (G29).

**S12. The dead-man switch is armed and healthy right now.** `data/deadman_heartbeat` and
`deadman_state.json` both **0.2 min** fresh; state `{"disarmed_live": false, "breaches": 0}`. The
off-box healthchecks.io heartbeat is configured and fired every 3 min by two independent
schedulers. The kill-file path is correctly wired (`_KILL` read at `run_alerts.py:265`,
`kill_switch_stuck` at >1 h). *The rail itself is alive; what is broken is the watching of it
(G21) and the honesty of its page (G9, G19).*

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1. Are ports 8080/8090 actually reachable from the internet? — the single most important
unknown, and it is one command away.** `/etc/ufw/user.rules` is `root:root 640`; `iptables -L` and
`nft list ruleset` both require root. ufw is confirmed *active with default DROP*, but the allow-list
is unreadable, and **no `ufw allow` appears anywhere in the repo** — the rules were set by hand with
no record. This decides whether G2's raw-port half is theoretical or live. **Resolves with:
`sudo ufw status numbered`.**

**U2. Is the ~0.82 GB of L2 depth genuinely irreplaceable?** High confidence for spot (Binance
publishes no spot depth archive), **medium for futures** (the public archive carries percentile-band
`bookDepth`, not a 20-level ladder). This number sets the entire offsite-storage decision, so it
deserves one external check rather than an assumption.

**U3. Did the Hetzner console backup ever produce a snapshot?** `GAP_REGISTER.md:463` marks it
`resolved` on 2026-07-16 with an explicit *"operator should confirm within 24h"* that has no
evidence of ever happening. Provider snapshots are not detectable from the guest. **This is the
desk's only claimed defence against disk death, and it is unverified — the register counting it as
`resolved` is itself the defect.**

**U4. Is the ntfy topic guessable?** `data/secrets/ntfy.json` holds a 12-char mixed-case alpha
topic (no digits) — a shape consistent with BOTH a random string and a CamelCase dictionary phrase.
ntfy.sh topics are world-subscribable **and world-publishable**: a guessable topic means anyone can
read every page *and forge pages to the principal's phone*. Needs a human eyeball; deliberately not
printed. Carried over from yesterday, still open.

**U5. Failed SSH volume / fail2ban ban counts.** `auth.log` is `syslog:adm`, `btmp` is `root:utmp`,
`last`/`lastb` not installed, journalctl denied. **Resolves with: `sudo lastb -n 50` and
`sudo fail2ban-client status sshd`.**

**U6. Effective `PermitRootLogin`.** Not set in `sshd_config` or `sshd_config.d/` → inferred as
OpenSSH's default `prohibit-password`, i.e. **key-based root SSH is permitted and in routine use** —
two `State=closing` UID-0 sessions from `93.107.49.143` match the recorder start times exactly
(operator activity, not intrusion, but it should be confirmed as the operator's IP). **Resolves
with: `sudo sshd -T | grep permitrootlogin`.**

**U7. Which of the 12 `ci-red` events in 24 h were real breakage vs "could not gate"?**
Unrecoverable from the log — G8(b) means both statuses write the same string. Future events will be
attributable only after the status split lands.

**U8. Per-job peak RSS across the 03:00–07:00 window.** 56 of 97 fixed-hour daily fires (58%) land
in that five-hour block on a 3.8 GB no-swap box now running at load 4.77, with `certify_gauntlet`
(>25 min, no flock, no timeout) overlapping eight other jobs. The OOM risk is *argued*, not
*measured* — nobody has instrumented it. **Yesterday's 08:21 OOM prediction is unfalsified rather
than refuted**: the herd was dissolved (17→6→0) before its first fire, and `sar -r` confirms no
memory pressure at 08:20 on 07-31 (19.56% used). The herd moved; it was not sized down.

**U9. Whether the healthchecks.io off-box ping is actually arriving.** It is fired inside a bare
`except: pass` with no ledger row (G19), so success is unrecorded. **This is the only wire that
survives total host death, and its health is unknown.** Resolves by outcome: pause the check and
confirm a page arrives.

**U10. The root cause of `run_moat_backup`'s ABSENT verdicts on files that exist.** The worktree /
CWD hypothesis is strongly supported (`not_covered_bytes: {}`, `disk_free_pct: 11.41` vs actual
59.48%) but not proven. The cron line's first real firing was `03:55` today — reading the resulting
`backups/moat/manifest.json` settles it immediately, and that is a free experiment.

**U11. Dependency drift.** `.venv/bin/pip` does not exist (uv-managed); `pip list --outdated` not
run. `backtrader` and `vectorbt` are declared but not installed. mypy reports `total_errors: 1116`
against a 40.7% clean-scripts floor, last measured 2026-07-30. No fence exists for venv package
staleness.

**U12. Whether any consumer of `defi_lending.jsonl` / `oi_ls_live.jsonl` aggregates by hour or by
`ts`.** 1,390 + 40 duplicate rows remain across 2026-07-30T23→07-31T03 and cannot be collapsed by a
`(ts, key)` dedupe (the batches are 27 ms apart). Whether that 2× inflation has reached any screen
is unchecked.

## 3. WHAT COULD MATTER MOST (ranked findings + opportunities)

Perspective tags: [INT]ernal · [EXT]ernal · [FUT]ure · [CON]trarian · [GRE]enfield · [FRO]ntier.

### G0. CRITICAL / WELDED GATE — the anti-timidity capital fence is a TAUTOLOGY: it divides a number by itself, reads 100% SATURATED forever, and the row it parses says deployed notional is ZERO. [INT][CON]

This is the most important finding in this sweep. L1.28a exists to make idle capital visible, and
`scripts/check_utilisation.py` is the fence that enforces it. Its headline ceiling cannot fail.

**The arithmetic.** `_capital()` (`scripts/check_utilisation.py:103-116`) builds its ceiling from
two functions:

```python
book, eq = float(live_book_usd()), float(_desk_equity_usd())
...
Ceiling("deployed_capital", eq, book, "USD", measured, ...)     # limit=eq, used=book
```

But `_desk_equity_usd()` (`libs/autodiscovery/validation.py:100`) *begins* with
`venue = float(live_book_usd(fallback=0.0)); if venue > 0: return venue`. So on every box where
the NAV ledger is readable and fresh — the normal operating state — **`eq` and `book` are the same
call**. Proven:

```
$ .venv/bin/python -c "from libs.autodiscovery.validation import _desk_equity_usd; \
    from libs.research.capacity_policy import live_book_usd; \
    b,e=live_book_usd(),_desk_equity_usd(); print(b,e,b==e,b/e)"
18675.73 18675.73 True 1.0
```

`utilisation = used/limit = 18675.73/18675.73 ≡ 1.0`. The fence reports
`SATURATED deployed_capital 100.0% 18,676/18,676 USD` and **is structurally incapable of
reporting anything else.**

**What the truth actually is.** The very NAV row the fence reads carries the real number:

```
$ tail -1 data/nav_attestation.jsonl
{"date":"2026-07-31", … "molded_curve_usd":18675.73,"equity_marked":18675.73,
 "_note":"molded_curve_usd is a MOLDED/SIMULATED curve, not venue truth and not a track record;
  venue truth is the dead-man's combined_equity",
 "deployed_notional":0,"n_carries":0, … "mode":"PAPER (testnet) -- pre-Gate-0"}
```

`deployed_notional: 0`, `n_carries: 0`. **True capital utilisation is 0%.** The fence installed by
L1.28a to make idle capital "reported as loudly as a risk breach" reports maximum saturation on a
book with zero deployed notional, while the correct field sits unread in the same JSON object.

**Why the existing OVER-LIMIT guard does not catch it.** The dataclass has a deliberate,
well-commented defence (`check_utilisation.py:70-78`) against exactly the previous version of this
bug — `if self.limit > 0 and self.used > self.limit * 1.02: return "OVER-LIMIT"`, with a comment
recording the 2026-07-30 `13,155/4,500` incident. That guard catches *divergent* sources. It is
blind to *identical* ones. The 07-30 fix repointed `_desk_equity_usd` at `live_book_usd` to kill
the two-source-of-truth bug — correctly, for the capacity gates — and in doing so silently
converted this ceiling from "two sources that disagree" into "one source compared to itself." **A
correct fix in one module welded a fence in another.** That is the strongest instance of L1.43
("a gate that accepts ~100% carries zero information however rigorous it looks") the desk has, and
it is on its own governance layer.

**Exactly-what.** Read `deployed_notional` (and `n_carries`) from the NAV row as `used`, keep
equity as `limit`. Then add the missing self-check to the `Ceiling` dataclass: a ceiling whose
`limit` and `used` derive from the same call is UNMEASURED, not SATURATED — the same refusal
vocabulary L1.41 already requires. Complexity: low (one function + one guard). Validation: the
fence must read `deployed_capital 0.0% IDLE` today, and `check_utilisation` must fail rather than
green. Failure mode of the fix: `deployed_notional` is itself paper-mode; label the mode in the
output so 0% pre-Gate-0 is read as "not funded yet", not as a repair target. ROI: restores the
desk's only instrument for its most expensive failure class. Confidence: **0.97** (arithmetic,
reproduced). Retirement: never. 1w/1y: the number becomes honest immediately; over a year it is
the difference between noticing and not noticing an unfunded book.

### G0b. CRITICAL / FABRICATED DOCSTRING — `live_book_usd()` says "venue truth first"; the code has no venue-truth rung, and venue truth is 3.0x lower than the number every capacity band divides by. [INT][CON]

**The contradiction.** `libs/research/capacity_policy.py:283` opens: *"The book the desk ACTUALLY
has: venue truth first, NAV chain second, constant last… Venue truth now wins; the NAV chain is a
fallback for machines where the rail has not run."* The function body is lines 300-311 and reads
**only** `_NAV_LEDGER`, taking `row.get("molded_curve_usd", row.get("equity_marked"))` — which the
row's own `_note` field declares to be *"a MOLDED/SIMULATED curve, not venue truth"*. There is no
venue-truth rung in the code. `grep -n "venue" libs/research/capacity_policy.py` shows
`venue_book_usd()` exists at line 257 — and `live_book_usd` never calls it.

**In fairness — the non-wiring is deliberate and test-fenced, and I checked before claiming a bug.**
`venue_book_usd`'s own docstring says *"NOT WIRED INTO `live_book_usd` -- deliberately"* with a
real reason (`high_water` is a high-water mark, so wiring it would tighten capacity during a
drawdown and reject the small §42 edges), and `tests/test_desk_integrity_checks.py:276` asserts
`"venue_book_usd()" not in inspect.getsource(cp.live_book_usd)`. So this is **not** built-never-wired.
The defect is that `live_book_usd`'s docstring asserts the *opposite* of both the code and the
sibling docstring. Two docstrings in one file contradict each other about the same wiring, and the
one that lies is on the function the whole desk calls.

**The number that matters.** The deliberate decision was explicitly conditional: *"Exposed so the
principal can compare it against the molded curve and decide; switching the default needs that
comparison on real data first."* That comparison is now available and nobody has run it:

```
$ .venv/bin/python -c "from libs.research import capacity_policy as cp; \
    print(cp.live_book_usd(), cp.venue_book_usd(), cp.live_book_usd()/cp.venue_book_usd())"
18675.73  6257.58667698  2.984
```

**Every capacity band in the desk is a ratio to a number 3.0x larger than venue truth.** Under
L1.18a the minimum slice is ≥10% of book: ~$1,868 on the molded curve, ~$626 on venue truth. The
gauntlet is therefore retiring as "OUTGROWN" every edge with capacity between ~$626 and ~$1,868 —
edges the desk can actually fill. That is L1.18a's own proving instance (the $100k floor, and the
07-30 `13,155/4,500` inversion) growing back a third time through a third door: *a capacity
threshold evaluated against a number that is not the book.*

**Exactly-what.** (1) Delete the false three-rung claim from `live_book_usd`'s docstring or make
the code match it — the docstring is currently the single most misleading comment in the repo,
because every organ reading it believes the desk sizes against venue truth. (2) Route the pending
decision: the comparison the docstring demands is done (2.98x); row it with a due date instead of
leaving it latent. The honest middle path is `min(molded, venue_spot)` — but note `venue_book_usd`
returns `high_water`, not spot, so spot equity (`last_eq` = `6226.85`) needs exposing first.
Complexity: trivial (docstring) + low (decision). Validation: `grep "venue truth first"` returns
nothing, or `live_book_usd` calls `venue_book_usd`. ROI: unblocks the small-capacity edges §42 is
built to hunt. Confidence: **0.9** on the contradiction (verbatim), **0.75** on the 3x harm
estimate (depends on which venue figure is correct — that is exactly the pending decision).

### G1. CRITICAL / SECURITY — F2 unfixed: the push-capable PAT is unchanged, and it has now leaked into LLM vendor transcripts by construction. [EXT][CON]

```
$ git config --get remote.origin.url | grep -oE 'ghp_[A-Za-z0-9]+' | awk '{print "prefix="substr($0,1,4)"  len="length($0)}'
prefix=ghp_  len=40
$ git config --get credential.helper        # system / global / local
system: (none)   global: (none)   local: (none)
$ ls -la .git/config
-rw-rw-r-- 1 quant quant 363 Jul 18 12:22 .git/config
```

Same 40-char classic PAT yesterday flagged, untouched since Jul 18.

**One correction to yesterday's severity claim, and one escalation.** Yesterday (and the 07-30
sweep) called `.git/config` "world-readable to any process on the box." In practice that is inert:
`/home/quant` is `drwxr-x---` and `getent group quant` → `quant:x:1000:` — the group has **no other
members**, and `quant` is the only non-system account. So the file mode is not the leak.

The real vector is worse and is not about file modes: **the token is in the output of
`git remote -v`, and this desk runs dozens of autonomous LLM organs as `quant` that pipe shell
output to third-party APIs.** It leaked verbatim into this audit's own tooling within seconds of
starting, from a command the audit doctrine itself prescribes. Every prior audit transcript that
ran `git remote -v` contains it. **Treat the token as already disclosed to every vendor in the
model chain.** Git history is clean of the full token (only the redacted `ghp_…kasoI` tail appears,
in audit docs). Rotation is not a hygiene improvement here; it is incident response.

### G2. CRITICAL / SECURITY — F8 unfixed, and the unknown is now ANSWERED: there is NO Cloudflare Access on the public tunnel. The full research web root — 73 files, 7.7 MB — is anonymously readable from the internet. [EXT]

Yesterday listed "is there an Access policy?" as unknowable from the box (U2). It is knowable from
*outside* the box, and the sweep checked: an unauthenticated off-box fetch of
`https://dash.quanttt.xyz/` returns **application content, not a login page** — titled
"QUANT DESK · CRYPTO", carrying equity curves, PnL across books, trade history with winrate,
leverage and ruin-boundary controls, Sharpe, capital allocation, cash-carry trades, and the
autonomous edge-discovery output.

```
$ cat ~/.cloudflared/config.yml
tunnel: 9b96e3d1-…
ingress:
  - hostname: dash.quanttt.xyz
    service: http://localhost:8080
  - service: http_status:404
```

**Scope is much larger than "a dashboard."** Port 8080 serves the whole `web/` directory: 73 files,
7.7 MB, all world-readable — `alpha_factory.json`, `autodiscovery_crypto.json`, `allocation.json`,
`capital_plan.json`, `crypto_portfolio.json`, `desk_economics.json`, `cashcarry_*.json`, and a
1.9 MB `algo_complete.txt`. That is the alpha research output and the capital plan, **published**.
The constitution's moat pillar (L1.11: the moat is the transformation pipeline) is precisely what
is being served. Bind addresses unchanged in source: `serve_dashboard.py:47 default="0.0.0.0"`,
`ops_server.py:53 HTTPServer(("0.0.0.0", args.port), Handler)`.

Amplifier (**M1**): `serve_dashboard.py:37` sets `Access-Control-Allow-Origin: *` on the same
unauthenticated public origin — so any website an operator visits can silently read the whole
dashboard from their browser.

Fix order matters: **Cloudflare Access on `dash.quanttt.xyz` is a dashboard-side change needing no
deploy**, and it closes the proven-live hole immediately. Rebinding to `127.0.0.1` is correct too
but closes only the raw-port half, whose live reachability is still gated on an unverifiable ufw
rule (see U-block).

### G3. CRITICAL / SECURITY — NEW: the auto-deploy gate EXECUTES the fetched code before deciding whether to trust it. The PAT is not a "kill chain"; it is direct RCE with a 10-minute SLA. [EXT][GRE]

Yesterday framed F2 as a chain that ends in an attacker-controlled restart. It is shorter than
that. `deploy/pull_deploy.sh` runs every 10 minutes (`crontab -l:81`) and its ordering is:

```sh
git merge --ff-only FETCH_HEAD                              # attacker tree now on disk
...
if ! "$PY" "$ROOT/scripts/run_ci.py" --fail-on-lock; then   # ← executes attacker's Python
```

Three attacker-controlled execution paths fire **before any restart decision**:
1. `scripts/run_ci.py` is executed *from the fetched tree*;
2. `cp "$ROOT/deploy/git_hooks/pre-push" "$ROOT/.git/hooks/pre-push"; chmod +x` — installs an
   attacker-supplied hook;
3. on manifest-hash change, `sh "$ROOT/deploy/reconstitute_cron.sh"` runs from the fetched tree →
   arbitrary crontab install.

**Every safety property in that script gates restarts, not execution.** Dirty-tree refusal,
`--ff-only`, revert-on-red, escalate-don't-restart — all downstream. A commit that *deliberately*
fails CI still achieves execution and is then tidily reverted, leaving a clean-looking `ci-red`
row in `pull_deploy_state.json`. No signature or committer check exists anywhere in the script.
Blast radius is the `quant` user, which owns `data/secrets/binance_live.json`.

This inverts the mitigation the desk has been relying on: the CI gate was counted as a safety
control, and it is in fact **the payload trigger**. Structural fix: run CI on the fetched commit in
a **scratch checkout** before merging into the live tree, and require a signed-commit /
allowed-committer check before fast-forward. Confidence: 0.9 (read from the script's own ordering).

### G4. HIGH — F4 diagnosed: the quota referee is not crashed, it is LATCHED OFF. It has fired ~80 times since rendering its one verdict and returned instantly every time. [INT][CON]

Yesterday reported the referee dead with an unknown cause (U8). The cause is one line.
`scripts/quota_verdict.py` main() opens:

```python
st = _load()
if st.get("verdict_sent"):
    return                                        # one definitive verdict is what was asked
```

and the state says it already fired:

```
$ cat data/quota_watch.json
{"baseline":"2026-07-22T00:27:16","verdict_sent":true,"verdict":"max_needed",
 "evidence":"30h clean window | cycles: 0 ok / 4 scheduled (1 quota-died) | miners: 0 ok / ~8
  scheduled (0 quota-died) | overall quota-death rate 100%"}
$ ls -la data/quota_watch.json          →  Jul 23 06:20   (10 days stale)
$ ls -la data/cro_ai_logs/quota_verdict_cron.log →  0 bytes, mtime Jul 31 21:00
```

The 0-byte log with a *fresh mtime* is the tell: cron fires it every 3 hours (`0 */3`), it opens
the log, returns on the latch, and writes nothing. **It is a one-shot organ on a permanent
schedule** — 8 wake-ups a day producing nothing, for 10 days.

Two consequences, and the second is the serious one. (1) The verdict itself — `max_needed`, on
evidence of a **100% quota-death rate** — was rendered on 2026-07-22 and has never been
re-evaluated; whatever happened next, nobody measured it. (2) Nothing else measures quota fit
either — see G5. Under L1.28c, cadence decisions are supposed to be "settled by MEASUREMENT, not
opinion", and both instruments for that measurement are dark.

**Exactly-what.** Make it re-arm: verdict on a rolling window, latch only the *page* (dedup), not
the *measurement*. Complexity: low. Validation: `quota_watch.json` mtime advances daily and the
cron log is non-empty. Confidence: 0.95 (code + artifact).

### G5. HIGH / UNMEASURABLE-BY-CONSTRUCTION — `brain_seat_throughput`, the ceiling L1.28c names as the arbiter for "raise cadence vs buy a second seat", can never be measured, and its stated binding constraint is misdiagnosed. [INT][CON]

```
$ .venv/bin/python scripts/check_utilisation.py
  UNMEASURED   brain_seat_throughput   0.0%   0/34 organ runs/24h (vs attempted)
               └─ bound by: brain_mutex.log absent on this host -- measurable only where organs actually run
```

**The binding constraint is wrong, and being wrong is what makes it permanent.** Organs
demonstrably run on this host — the same line counts 34 attempts, and this audit is one of them.
The metric's only data source is `data/cro_ai_logs/brain_mutex.log` (`check_utilisation.py:269`),
which `ops/brain_env.sh:56-58` writes **only on the deferral branch** (`if ! flock -n 9`). And a
*different* layer prevents deferrals from ever happening: `organ_catchup` holds retries back before
they reach the mutex —

```
$ tail -3 data/cro_ai_logs/organ_catchup.log
2026-08-01T00:45:06 field busy (deep_sweep running) -- holding retries so they do not share the window
2026-08-01T00:50:10 field busy (deep_sweep running) -- holding retries so they do not share the window
$ ls -la data/cro_ai_logs/brain_mutex.log   →  No such file or directory
$ cat /tmp/quant_brain.owner                →  deep_sweep pid=1708920 since=2026-08-01T00:00:17Z
```

The mutex works (it is held right now, by this audit). Contention is real and is being managed.
But it is managed *upstream of the only place it gets recorded*, so the log never comes into
existence, and the ceiling reads UNMEASURED forever. Because the fence blames "organs don't run
here", the fix it points at is already true and would never resolve it — a misdiagnosed binding
constraint is worse than a blank one, because it terminates the investigation.

Under L1.28a **unmeasured counts as zero utilisation**, so the desk's single most contended
resource — one brain seat — is formally at 0% with no path to a real number. Combined with G4, the
desk has two instruments for LLM-quota fit and both are dark: one latched off, one structurally
unwritable.

**Exactly-what.** Record contention where it actually happens: have `organ_catchup` append its
"field busy" decisions to `brain_mutex.log` (it already computes exactly the fact the metric
wants), or have `brain_mutex` log *acquisitions* as well as deferrals so throughput has a
denominator. Complexity: low. Validation: `brain_mutex.log` exists and `brain_seat_throughput`
leaves UNMEASURED. Confidence: 0.9.

### G6. HIGH / LAW-COVERAGE — L1.42 says "no act is exempt". Measured: 30 of 94 scheduled organs call the law guard. 68% of the desk's scheduled surface, including the enforcement organs themselves, still starts under no gate. [INT]

L1.42 was installed on 2026-07-31 precisely because ~60 organs bypassed the spawn gate. Measured
today against the live crontab:

```
$ crontab -l | grep -oE "scripts/[a-z0-9_]+\.py" | sort -u   →  94 distinct scheduled scripts
$ ... for each: grep -qE "guard\s*\(" && grep -q "lawful"
scheduled organs: 94 ; with a real guard() call: 30 ; coverage 31.9%
```

The 64 uncovered include the money-path and enforcement layer:
`run_live_guard.py` (the size governor **and** stage-demotion evaluator that L1.44 names as a
compound risk), `max_audit.py`, `check_ratchets.py`, `check_law_families.py`,
`check_utilisation.py`, `check_timidity_language.py`, `run_recorder_bybit.py`,
`run_recorder_spot.py`, `collect_defi_lending.py`, `collect_oi_ls_live.py`,
`daily_research_cycle.py`, `certify_gauntlet.py`, `run_promotion_queue.py`,
`organ_catchup.py`, `quota_verdict.py`.

**Being fair about two of them:** `check_constitution_core.py` and `run_law_gate.py` arguably
*should* be exempt — they ARE the gate, and calling `guard()` inside them is circular. That is a
legitimate exemption and should be *recorded as one* (L1.41 condition 3: exempt-with-a-reason,
never by default). The other ~62 have no such argument.

**The strength worth naming:** the executor does it right —
`scripts/run_cashcarry_executor.py:1421` `_law_guard(strict=True)`, with the comment *"an unlawful
trade cannot be undone"*. Exactly as doctrine specifies. The pattern is proven; it is the coverage
that is missing.

**And the ratchet gap:** `grep -rn "guard_coverage\|law_guard" scripts/check_*.py data/ratchet_floors.json`
finds no coverage metric and no floor. Under L1.0(a) a capability with no number is a defect and a
number with no floor is a defect — **31.9% is being reported here for the first time, so today it
becomes the floor.** Complexity: low per organ, mechanical. Validation: the coverage command above
is the proving command; wire it into `check_build_standard.py` so a new scheduled organ without
`guard()` fails the build. Confidence: 0.95 (mechanical count).

### G7. CRITICAL / OBSERVABILITY — the desk DELETES ITS OWN EVIDENCE: a log reaper written for one organ's session logs uses a `*.log` glob and destroys the outcome trail of ~68 organs, three times a day — then the liveness fences read the survivors as ground truth. [INT][GRE]

Found independently by two sweeps on this run, from opposite directions, which is why I am
confident in it. `ops/run_cro_ai.sh:98-99`, verbatim:

```sh
# keep last 30 logs
ls -1t data/cro_ai_logs/*.log | tail -n +31 | xargs -r rm -f
```

**The mechanism is a glob that is one character too wide.** The CRO brain writes its own dated
session log — `LOG="data/cro_ai_logs/$(date -u +%Y%m%d_%H%M).log"` (`ops/run_cro_ai.sh:16`) — and
the cap was written to bound *those*. The glob is `*.log`, so it sweeps the entire shared
directory. It runs on every brain cycle, `45 2,14,20 * * *` — three times a day.

**The arithmetic is brutal:**

```
$ crontab -l | grep -oE "data/cro_ai_logs/[a-z0-9_]+\.log" | sort -u | wc -l   →  98
$ ls -1 data/cro_ai_logs/*.log | wc -l                                        →  50
$ ls -lat data/cro_ai_logs/ | tail -2      →  oldest file: Jul 31 20:22   (<5h of history)
$ du -sh data/cro_ai_logs/                 →  576K
$ df -h / | tail -1                        →  23G available
```

**98 declared log targets, a 30-file cap, 576K of data, and 23GB free.** The reaper is destroying
the desk's entire forensic record to reclaim 0.002% of free disk. Retention is by mtime rank, so
it deterministically evicts exactly the organs that run *least often* — the daily fences — while
high-frequency writers (`organ_catchup.log`, 146KB, every 5 min) always win the race.

**How I found it, and why the finding is the reaper and not "52 dead organs".** My first pass
measured cron redirect targets and found 52 of 95 missing — `max_audit`, `check_ratchets`,
`check_law_families`, `check_calibration`, `check_exploration`, `check_replacement_rate`,
`certify_gauntlet`, `run_drills`, `run_moat_backup`, `run_max_push` — the entire fence layer with
no log file at all. A `>>` redirect creates its file on first execution regardless of output, so
that reads as "never fired." I ruled out the alternatives before believing it: `QUANT_ROOT` **is**
defined in the crontab (so `cd "$QUANT_ROOT" &&` does not short-circuit), fresh and missing lines
use byte-identical patterns, and `/etc/logrotate.d/` contains **no quant entry**. The reaper is
what is left, and it explains every observation — including why all 50 surviving files are <48h old.

**The compounding harm — it starves the detectors that would catch it.** Three consumers read
this directory as evidence of organ health:
- `scripts/check_utilisation.py:135` — `fresh = {… for p in _LOGS.glob("*.log") if mtime >= cutoff}`.
  Its numerator is **capped by the reaper**, not by organ health. It reports
  `scheduler_cadence 33.0% — 31/94 organs run in 48h`. That number is reading back the retention
  constant. **A ratchet metric measuring its own log-rotation policy** — and under L1.0 it would be
  floored and tracked as if it meant something.
- `scripts/max_audit.py:47-60` — the `brain-cycle` organ's liveness pattern is `"2026*_*.log"`,
  which is *precisely* the dated-session filename the reaper evicts first. Exactly **1** such file
  survives. The fence reads the reaper's output as ground truth.
- `scripts/run_alerts.py:317` and `:434` — `brain_down` / `brain_noop` pages, and the brain
  auto-trigger decision, are all computed from `sorted(Path("data/cro_ai_logs").glob("*.log"))[-1]`.

This is the desk's own "outcome-not-config" doctrine sawing off the branch it sits on: the audit
method is *"verify what a thing PRODUCED"*, and the artifact proving production is deleted on an
8-hour cycle. Every audit that ever concluded "organ X never ran" from a missing log — including
parts of yesterday's — was reading a deletion, not a failure.

**Exactly-what.** One character: `data/cro_ai_logs/*.log` → `data/cro_ai_logs/2026*_*.log`, so the
cap bounds only the CRO's own dated session logs as intended. Then, separately, give the shared
directory real rotation (logrotate is installed and covers zero desk logs) with per-organ
retention measured in days, not global file count. Complexity: **trivial** (one glob) + low
(logrotate stanza). Validation: after one brain cycle, `ls data/cro_ai_logs/*.log | wc -l` exceeds
30 and daily-fence logs survive; `scheduler_cadence` moves off 33% and starts measuring organs.
Failure mode: unbounded growth — bound it by age and size in the logrotate stanza, which is what
logrotate is for. **Interaction: this must be fixed BEFORE trusting `scheduler_cadence`,
`check_organs`, or any "organ is dead" finding in this or any prior sweep.** ROI: restores the
evidence base the entire audit layer runs on. Confidence: **0.95**. Retirement: never.

### G8. CRITICAL / DEPLOY — the gate runs AFTER the merge, so the live desk executes unvetted code for the whole CI window; "could not gate" is recorded as "code is broken"; and the state artifact names the wrong commit as live. [INT][EXT]

Yesterday's F3 called the gate non-deterministic. That was half right and the wrong half. Three
distinct defects, all verified live during this sweep:

**(a) Fast-forward first, gate second.** `deploy/pull_deploy.sh` merges at line 180 and only then
runs the gate at line 187. Verified at `00:57:35Z` mid-sweep:

```
$ git rev-parse --short HEAD          →  787620a
$ ps -o pid,etimes,cmd | grep run_ci
1734402  438  .venv/bin/python scripts/run_ci.py --fail-on-lock
1734439  436  .venv/bin/python -m pytest tests/ -q
```

HEAD is `787620a` — the exact commit recorded `ci-red` and "reverted" 27 minutes earlier. Every
safety property in that script (dirty-tree refusal, `--ff-only`, revert-on-red) gates *restarts*;
the code is already on disk and already executing. **Duty cycle: the desk runs unvetted code for
roughly 10 of every 20 minutes**, because `flock -n` silently drops a tick when the ~10-min gate
overruns its 10-min cadence (the 00:20 and 00:40 ticks are simply absent from the log).

**(b) rc3 "could not gate" is treated as red and triggers a revert — this is the real
non-determinism.** `scripts/run_ci.py:76` states the contract in its own words: `--fail-on-lock`
returns 3, *"which a deployer must treat as not-green and retry."* `deploy/pull_deploy.sh:187`
implements `if ! "$PY" … run_ci.py --fail-on-lock; then` → straight to `git reset --hard "$OLD"`.
No retry. There are three concurrent invokers of `run_ci` — `pull_deploy.sh:187` (every 10 min),
`scripts/rollback_guard.py:83`, and `scripts/daily_research_cycle.py:36` (a **1200s** budget,
spanning two pull_deploy ticks). **When the daily cycle holds the lock, a perfectly green commit is
reverted and logged as `ci-red`.** That is the mechanism behind yesterday's "same commit red twice
then green" — not load flakiness. And the log has no distinct status for it, so of the 12 ci-red
events in 24h, **none can be attributed** to broken-code vs could-not-check.

Worse: `daily_research_cycle.py:36` invokes `run_ci.py` *without* `--fail-on-lock`, and
`run_ci.py:80-81` returns **0** on a held lock — so the known false-green path is live there.

**(c) The state artifact lies about what code owns the book.**

```
$ cat data/pull_deploy_state.json
{"ts":"2026-08-01T00:30:01Z","status":"ci-red","from":"750129a","to":"787620a",
 "note":"reverted -- run_ci.py not green on the new commit"}
$ git rev-parse --short HEAD   →  787620a
```

It reads "reverted, box is on 750129a." The box is on `787620a`. Any monitor consuming this gets
the wrong answer to the only question it asks. (Also `NOW` is captured at script *start*, so every
log line is stamped ~10 min before the event it describes.)

**(d) The deadlock class, and it is armed right now.** The tree is dirty on two *tracked* files
(`docs/research/conversion_record.json`, `holdings_record.json`) written by cron organs.
`pull_deploy.sh:90` refuses on a dirty tree **before** it can revert. If an organ dirties a tracked
file while HEAD sits on red, **the box is parked on the red commit permanently.** The 24h outcome
census shows this is not theoretical: `73 refused-dirty, 37 up-to-date, 12 ci-red, 4
refused-diverged, 4 deployed` — the puller spent most of yesterday refusing to deploy at all.

**(e) The test that "pins" this contract is a change-detector.** `tests/ops/test_ci_gate_lock.py:45-46`
asserts two *strings* exist in a shell file (`assert "run_ci.py\" --fail-on-lock" in src`). It
passes while the implementation violates the contract it documents. False confidence, in the test
that guards the deploy.

**(f) The active incident is one auto-fixable import sort.** Reproducible 3/3, rc=1:
`ruff check scripts libs tests` → `I001 Import block is un-sorted` at
`tests/validation/test_gate_power_audit.py:7:1`, `[*] 1 fixable`. On the prior commit `750129a`,
`ruff check .` → `All checks passed!`.

**Exactly-what,** in dependency order: (1) `ruff check --fix` the one file — stops the loop today.
(2) **Gate in a scratch checkout before merging into the live tree** — this fixes (a) and G3's RCE
in the same change, and is the single highest-leverage infra fix available. (3) Handle rc3
distinctly: retry, and record `could-not-gate` as its own status. (4) Memoize the red SHA so the
gate stops re-proving it (currently ~10 min of both cores, every 10 min, forever). (5) Make the
state artifact record actual `HEAD`, not intent. Complexity: (1) trivial, (2) medium, (3-5) low.
Confidence: 0.95 (reproduced live).

### G9. HIGH / SURVIVAL RAIL — the dead-man switch swallows failures in the flatten loop and then pages "book flattened" unconditionally. A partial or failed flatten reports as a completed one. [INT][CON]

This is the highest-severity item that is not a security hole, because it is on a Tier-3 rail and
it corrupts the one signal the principal cannot afford to disbelieve.

`scripts/run_deadman_switch.py:243` — `except Exception: pass` wrapping the **spot-flatten market
SELL order loop**; `:254` — a second `except Exception: pass` wrapping the ntfy page. The page
`"DEADMAN SWITCH FIRED: book flattened at ruin rail"` is emitted regardless of whether any order
succeeded.

L2.4 bans exactly this (*"an `except: pass` converts a failure into a SUCCESS SIGNAL for every
caller downstream"*), and `check_build_standard.py` enforces it — but only over its 37 `_GOVERNED`
organs, and `run_deadman_switch.py` is not one of them. **97 silent swallows exist outside the
fence**; 5 are on the money path; these two are on the ruin rail. The fence is real and the rail is
outside it.

Note the interaction with G6: the dead-man is also not in the L1.42 guard set. The desk's most
survival-critical process is outside both its build fence and its law gate.

**Exactly-what.** Collect per-order outcomes; page the *truth* (`flattened 7/9 legs, 2 FAILED:
<symbol> <error>`); never let the pager path's own failure mask the flatten result. Add
`run_deadman_switch.py` to `_GOVERNED`. Complexity: low. Validation: a drill with a forced order
rejection must produce a page naming the failure. Confidence: 0.9. **Retirement: never — this is a
Tier-3 rail.** 1y opportunity cost of not fixing: a believed-flat book that is not flat, which is
the precise failure mode the rail exists to prevent.

### G10. HIGH / DURABILITY — the moat backup is INERT and self-certifies a PASSED restore drill over a near-empty replica: 7.2 GB of irreplaceable data has a 52 KB "backup". [INT][FUT]

Desk memory already flagged `run_moat_backup` as inert. This sweep re-measured it and the numbers
are worse and now specific:

```
$ du -sh data/moat backups
7.2G    data/moat
52K     backups
```

`backups/moat/manifest.json` (committed to git, `generated: 2026-07-31T12:19:43`):

```
execution_tape    ABSENT      path=data/moat/execution_tape
research_memory   ABSENT      path=data/research_memory.db
sor_research      REPLICATED  bytes=0      path=data/sor_research.sqlite
capital_events    ABSENT      path=data/capital_events.jsonl
cost_model        ABSENT      path=data/cost_model.json
graveyard         REPLICATED  bytes=36861
restore_drill_passed: True    status: DISK-FUSE
```

Against what is actually on disk: `data/cost_model.json` **exists** (54,109 bytes),
`data/moat/execution_tape` **exists** (135,453 bytes), `data/sor_research.sqlite` **exists**
(835,584 bytes — recorded as "REPLICATED" at **0 bytes**). Only `capital_events.jsonl` and
`research_memory.db` are genuinely absent.

So the module's own docstring calls the execution tape *"the only copy of stores that CANNOT be
re-earned — fills at our own timestamps"*, records it ABSENT while it sits on disk, replicates
another store at zero bytes, and stamps **`restore_drill_passed: True`**. `run_moat_backup.py:145`
gates on `src.exists()`, so the ABSENT verdicts are most likely a CWD/path-resolution bug — that
needs a root-cause pass rather than my assertion, and it is the first thing to check.

This is the desk's named worst class — *unmeasured reported as OK* — sitting on L1.23 survival
data. **A drill that passes over an empty replica is worse than no drill**, because it converts an
open risk into a closed one in the reader's mind. Confidence: 0.9 (manifest vs `ls`, both cited).

### G11. HIGH / STALE-CONSUMER ON THE MONEY PATH — the executor sizes orders against a venue-truth file frozen 5 days ago whose producer is unreachable. [INT]

`libs/execution/binance_spot_testnet.py` — the module the money path actually imports
(`run_cashcarry_executor`, `run_stranded_recovery`) — reads `data/capacity_floor.json` for venue
minimum notionals. Its own docstring records why: `run_stranded_recovery` previously hardcoded
`10.0` for every symbol *"against the desk's own measured venue truth (`capacity_floor.json`:
spot_min 5.0), which silently refused recoverable balances in the $5-10 band."* The hardcode was a
real capital bug and reading measured truth was the right fix.

**The producer of that truth is `scripts/capacity_simulator.py`, which is unreachable from any
entry point, and the file has not moved since 2026-07-27.** Venue minimums change. The money path
now trusts a frozen snapshot that nothing will ever refresh — the same bug one step removed, and
invisible because the *value* looks measured.

Six more of the same shape (producer orphaned, consumer scheduled and live):
`data/structural_spreads.json` → `data_sanity.py`; `data/optimal_hold.json` →
`research_exchange.py`; `data/information_class_map.json` → `breadth_expander.py`,
`blindspot_prober.py`; `data/horizon_discovery.json` → `negative_knowledge.py`;
`data/micro_features.json` → `research_exchange.py`; and the cleanest case —
**`data/suggestion_ledger.jsonl` is 0 bytes** and is read every 3 hours by `kimi_hunter.py` (cron
`5 */3 * * *`) and by `research_exchange.py`, with its writer orphaned.

This is precisely the class L1.44 was built for, and it shows the freshness law is **installed but
not yet applied to these reads**: none of these consumers goes through `read_fresh()`. Fixing them
is mechanical and is the highest-value first use of the new law.

### G12. HIGH / MONEY PATH — the executor swallows `BaseException` around order placement, and all four venue connectors have ZERO idempotency keys while the retry module's docstring asserts they all carry one. [INT][EXT]

`scripts/run_cashcarry_executor.py:951-957`, verbatim:

```python
class _safe:
    """Best-effort order context -- a single leg failing must not abort the whole rebalance."""
    def __enter__(self) -> _safe:
        return self
    def __exit__(self, *exc: object) -> bool:
        return True                                       # swallow leg errors (logged via web)
```

Returning `True` unconditionally swallows **everything, including `KeyboardInterrupt` and
`SystemExit`** — functionally `except BaseException: pass` wrapped around the order POSTs.

```
$ grep -rc "newClientOrderId\|clientOrderId" libs/execution/binance_*.py
binance_live.py:0   binance_spot_live.py:0   binance_testnet.py:0   binance_spot_testnet.py:0
```

Zero idempotency keys across all four connectors — while `libs/execution/retry.py:1-6` states
*"Retries are only safe because every order carries an idempotency key."* That docstring describes
the unused MT5 broker. **Second fabricated docstring of this sweep, and this one is on the order
path** (cf. G0b).

**The concrete failure:** on a 5xx or a mid-flight socket drop, `urlopen` raises → `_safe` swallows
→ `spot_res`/`fut_res` stay `None` → `_filled(None)` is `False` → **recorded as unfilled, when the
order may have filled at the venue.** A 5xx and a dropped socket are indistinguishable. The desk's
own `libs/execution/errors.py:20-24` defines exactly this state (`BrokerTimeout`: *"the order may
or may not have been placed... Never assume a fill"*) — and the Binance connectors never raise it.
Reconciliation is per-tick (600s) only; **there is no startup reconcile before the loop begins.**
The `_filled()` check (added after the 2026-07-19 $2,150 stranded-inventory incident) and
`reduceOnly` on closes are the only things standing between this and a doubled position.

### G13. HIGH / MONEY PATH — the 418 ban circuit-breaker was built on 2026-07-31 and never wired to the order path, so the executor still extends its own venue ban. [INT]

Commit `963df91` added a real cross-process breaker (`data/BINANCE_BAN_UNTIL`, 7200s latch on 418,
120s on 429) in `libs/data/crypto_source.py:27-46`, after a measured incident. Verified:

```
$ grep -rln "BINANCE_BAN_UNTIL\|_ban_remaining" libs/ scripts/
libs/data/crypto_source.py                       ← the ONLY file
$ grep -n "^from libs.execution import" scripts/run_cashcarry_executor.py
28:from libs.execution import binance_spot_testnet as spot
29:from libs.execution import binance_testnet as fut
```

The executor's two connectors never consult the latch. **During a latched IP ban the market-data
reader correctly stands down while the order path keeps hammering the banned endpoint and extending
the ban** — the exact loop the fix was written to stop. Built-never-wired, on the money path, one
day old. This is L1.42's "name the production caller" rule failing on its first test case.

The incident it was built for is documented and real (`journalctl -u quant-cashcarry`, six distinct
PIDs at ~3.4-min intervals on 2026-07-31 08:39→08:58, each `HTTP Error 418: I'm a teapot`).

### G14. HIGH / RESILIENCE — not one systemd unit has a resource limit, and the restart rate-limiter is mathematically unreachable on all five always-on units. [INT][EXT]

```
$ grep -l "StartLimit\|MemoryMax\|CPUQuota\|OOMScoreAdj\|WatchdogSec" /etc/systemd/system/quant-*.service
(empty — none of the 13)
$ systemctl show quant-cashcarry -p RestartUSec -p StartLimitIntervalUSec -p StartLimitBurst
RestartUSec=15s   StartLimitIntervalUSec=10s   StartLimitBurst=5
```

Triggering the limiter needs **5 restarts inside 10 seconds**, but `RestartSec ≥ 10s` on every
unit makes that impossible. **The limiter can never fire; effective policy on all five is unlimited
restarts, forever** — which is precisely the mechanism behind the 5,354-respawn incident the
watchdog's own comments document (`watchdog.py:68-78`).

And nothing protects the money path under memory pressure:

```
$ free -m           →  total 3814, available 524, Swap 0
$ uptime            →  load average: 4.77 on 2 cores
$ systemd-cgtop -n1 →  cron.service 45 tasks 1.8G   |  all quant-*.service combined: 294M
PID      OOM_SCORE  RSS_MB  CMD
1731200  718        297     claude --effort max
1734439  713        269     python -m pytest
1626623  691        141     run_cashcarry_executor.py     ← THE LIVE EXECUTOR
1463355  670         22     run_deadman_switch.py
```

**The live executor is the highest-scoring persistent process on the box**, every process carries
`oom_score_adj=0`, and the cron organ pool (1.8G, no unit file, no limit, no supervision) outweighs
every supervised service **6×**. The box has already OOM-killed once
(`Jul 26 01:07:56 systemd[423803]: dbus.service: Failed with result 'oom-kill'`).

Hidden consumer worth naming: **`/tmp` is a 1.9G tmpfs holding 1.1G — that is RAM, not disk**
(`free`'s `shared 1094`): `/tmp/qmine` 374M, `/tmp/pytest-of-quant` 198M, `/tmp/l2.csv.gz` 152M,
nothing reaping any of it. **29% of system RAM is scratch files.**

Fix: `MemoryMax=` on always-on units, `OOMScoreAdjust=-500` on executor and dead-man,
`StartLimitIntervalUSec > RestartSec`, and a `/tmp` reaper. Complexity: low. Confidence: 0.95.

### G15. HIGH — F7 is NOT fixed, it is still firing every 3 minutes, and yesterday's prescribed fix would have MISSED. [INT]

`watchdog.py:57-62` `_UNITS` maps cashcarry / deadman / liquidations / dashboard. **`quant-tunnel`
is still absent.** But the interesting part is why yesterday's one-line fix would not have worked:

```python
# watchdog.py:200-204
if not _fresh(_TUN_HB, 120):
    tun = "scripts/run_ngrok.py" if (_ROOT/"data"/"secrets"/"ngrok.json").exists() \
        else "scripts/run_tunnel.py"
    _spawn([tun], "public-tunnel")
```

`data/secrets/ngrok.json` **exists**, so the spawn target is `run_ngrok.py`, not `run_tunnel.py` —
and yesterday's F7 prescribed mapping `run_tunnel.py`. The loop would have survived the fix.
Both targets are dead anyway: `run_ngrok.py:26` → `tools/ngrok.exe`, `run_tunnel.py:25` →
`tools/cloudflared.exe` — **Windows paths from the pre-migration era, and `tools/` is empty.**
`data/tunnel_heartbeat` has mtime Jul 12 (20.0 days) and nothing writes it, so the gate is
permanently open.

Measured live, growing:

```
$ grep -c "re)started public-tunnel" data/watchdog.log        →  519
$ grep -oE "watchdog: \(re\)started [a-z-]+" data/watchdog.log | sort | uniq -c
    519 watchdog: (re)started public-tunnel
T0  00:52:26  tunnel=520      NOW 00:56:16  tunnel=521      (+1 per 3-min tick, as predicted)
```

**Every single spawn event in the entire watchdog log is the doomed tunnel. Not one real recovery.**
~17/hour, ~3,768 cumulative. That is the crying-wolf channel where a genuine executor respawn is
supposed to stand out.

**Contrarian note that changes the recommendation:** the watchdog is now largely *redundant*.
`quant-refresh.service` runs the identical four scripts (`run_leverage_opt`, `run_live_combined`,
`data_health`, `run_alerts`) every 3 min, and systemd `Restart=always` independently covers all
four supervised daemons. So the watchdog's *only unique behaviour today is the doomed spawn.* The
greenfield answer is not "fix the map" — it is **delete the tunnel branch and evaluate retiring the
watchdog entirely** (L2.9 KEEP/UPGRADE/MERGE/ACTIVATE/RETIRE: this is a MERGE candidate).

### G16. HIGH / SELF-INFLICTED QUOTA BURN — `organ_catchup` re-fires the WEEKLY deep sweep every 45 minutes forever, because a fully-successful run writes 783 bytes against a 1200-byte success threshold. [INT][CON]

```python
# libs/ops/organ_catchup.py:70-71
OrganSpec("deep_sweep", "ops/run_deep_sweep.sh", "deep_sweep*.log", 1200, "run_deep_sweep",
          period_days=7)
# :24  RETRY_COOLDOWN_S = 45 * 60
```

`organ_owed()` clears only `if any(p.stat().st_size >= spec.success_bytes …)`. A complete,
correctly-resuming sweep writes:

```
$ cat data/cro_ai_logs/deep_sweep_20260731T2310.log
[deep-sweep] infrastructure: already COMPLETE today -- skipping (resume)
... [deep-sweep] done: 9/9 COMPLETE; synthesis=yes
$ stat -c '%s  %n' data/cro_ai_logs/deep_sweep_*.log
783  deep_sweep_20260731T2025.log   783  ...2130.log   783  ...2220.log   783  ...2310.log
```

**783 < 1200 → permanently "owed" → re-fired every 45 min.** Observed 8 fires in under 7 hours for
an organ whose declared cadence is **weekly** (`0 4 * * 0`).

The knock-on is severe and explains G5: each re-fire takes the desk-wide brain mutex
(`/tmp/quant_brain.owner` → `deep_sweep pid=1708920 since=2026-08-01T00:00:17Z`, held 57 min at
audit time) and `organ_catchup` then holds back **every other LLM organ** for the duration. The
seat services show the result — `quant-dataaxis` and `quant-prospector` exit in **0 seconds** with
`Result=success`, because `brain_mutex` `exit 0`s on a held lock, so **a deferral is byte-identical
to a success at the scheduler layer**. Artifact corroboration: `prospector_watchlist.md` is 26h
stale behind a green 18:00 "success".

**A success threshold that a successful run cannot reach** is the purest form of the desk's
welded-gate class, and here it converts into unbounded LLM-quota burn plus starvation of every
other research organ. It is also the direct cause of the "quota-death rate 100%" the referee
measured in G4 and never re-measured. Fix: make the success test artifact-based (the sweep writes
dated reports — check those), or drop the threshold below the resume-path's real output.
Complexity: trivial. Confidence: 0.95.

### G17. MEDIUM-HIGH / SCHEDULER — the duplicate class F1 named cannot be detected by the fence built to guard it, and the installer that caused it was never changed. [INT][GRE]

Two structural facts, either of which guarantees recurrence:

**(a) The fence is set-based, so duplication is invisible by construction.**
`scripts/check_scheduler_manifest.py:207-214` builds `want` and `have` as **Python sets**;
duplicates collapse before comparison. Measured:

```
live job lines (raw)       : 120
live job lines (as a SET)  : 119        ← the duplicate vanishes here
$ .venv/bin/python scripts/check_scheduler_manifest.py
  live crontab: matches manifest (normalized)
scheduler-manifest: OK      RC=0
```

**A 2× duplication of every line would still report OK.**

**(b) The installer was never fixed.** `git log -3 -- deploy/reconstitute_cron.sh` shows no commit
after F1 was found; its contract is unchanged (*"everything outside the fence … is preserved
byte-for-byte"*) and it has zero dedupe against pre-existing legacy lines. Yesterday's fix was
manual crontab surgery — the next run on any box carrying legacy lines reproduces F1 exactly.

**Good news on the outcome side, and it is real:** the mass duplication IS gone (one surviving
byte-identical duplicate, `check_freshness.py`, which sits *above* the `QUANT_ROOT=` assignment and
therefore silently no-ops), the `21 8` herd was cut 17→6→0 before its first fire, and the doubling
stopped at 2026-07-31T04:00Z after exactly 5 hours:

```
278 2026-07-30T22 | 556 …T23 | 556 …T00-03 | 278 2026-07-31T04 → 279 2026-08-01T00
```

**But the contaminated rows were never cleaned.** 2,780 rows exist across those 5 hours where
~1,390 belong (+40 extra in `oi_ls_live.jsonl`), and because the duplicate batches carry `ts`
values **27 ms apart**, a `(ts, key)` dedupe *cannot* collapse them. Any rate/count computed over
2026-07-30T23→2026-07-31T03 is 2× inflated. Also proven by those 27ms: `flock` did not serialize
them — the two lines used different lock paths, the failure mode still live for
`ops/run_crypto_factory.sh` (`data/.cron_crypto_factory.lock` vs `/tmp/crypto_factory.lock`).

**And L1.28c's declared fence does not exist.** The constitution says
`check_scheduler_manifest.py` "requires every manifest line to carry its evidence and confidence."
The checker `continue`s on every comment line (`:88-92`) and requires nothing. Measured: **107 of
119 cadences name no ceiling type at all** — by L1.28c(c)'s own words, unmeasured and therefore
idle.

### G18. MEDIUM-HIGH — 12 seat cron lines are permanent no-ops, and one dated double-fire is predicted for TODAY 20:00Z. [INT]

Every seat line is `{ systemctl is-enabled <timer> >/dev/null 2>&1 || flock … ; }`. For
dataaxis/frontier/prospector/litminer, `is-enabled` returns 0 → the `||` short-circuits → **all 12
cron lines never execute.** The declared "3 runs/day per seat" is actually **1/day** from the timer.

The inverse bug is armed today: `quant-blindrediscovery.timer` is `ActiveState=active` but
`UnitFileState=disabled`. `is-enabled` returns non-zero → **the cron path fires**; the timer is
active with `OnCalendar=*-*-01 20:00:00` → **the timer path also fires**; systemd's `ExecStart`
takes no flock, so `/tmp/seat_blindrediscovery.lock` does not serialize them.

**Today is Saturday 2026-08-01 — dow=6 AND the 1st — so at 20:00 UTC two concurrent headless-Claude
digs (~250MB each) launch into ~138MB of free RAM.** Only `brain_mutex` will save it, and it will
record the loser as a 0-second success (G16). `enabled ≠ active` is the bug. **This is a dated,
falsifiable prediction and the cheapest fix on this list: swap the guard to `is-active`.**

### G19. MEDIUM — the only off-box detector of total host death fires inside a bare `except: pass`. [INT][CON]

Total box loss is the desk's longest-recovery failure (G20). Detection rests entirely on the
healthchecks.io dead-man ping — which `run_alerts.py:531-537` fires inside `except Exception: pass`
with no log and no ledger row. **A rotated, expired or misconfigured URL fails completely
invisibly, and the desk would believe it has an off-box dead-man while having none.** It is the
only wire that survives the failure it exists to report, and its success is unrecorded.

Same shape on the ruin rail: `run_deadman_switch.py:249-255` `_page()` does **not** use
`run_alerts._push` — no second channel, no delivery ledger, no backoff — so if ntfy is down when
the rail fires, the page evaporates (compounding G9).

**Exactly-what:** record every ping outcome to `alert_delivery.jsonl` like every other channel, and
verify by outcome (pause the check, confirm a page arrives). Complexity: trivial. Confidence: 0.9.

### G20. MEDIUM — the executor FAILS OPEN on its own audit trail at 80% disk, and its error log truncates. [INT]

`libs/execution/execution_tape.py:34` sets `_DISK_MAX_FRAC = 0.80`; `append()` returns `False`
silently above it. `run_cashcarry_executor.py:127` calls `execution_tape.append(rec)` and
**discards the return value**, with a docstring saying the append *"never blocks the executor."*
Consequence: **above 80% disk the executor keeps placing orders while the permanent fill tape
silently stops recording** — and the tape is what "unrecorded fills" is measured against. Trips at
29.8 GB used; currently 13.5 GB with `data/moat` growing ~0.7 GB/day → **~23 weeks of runway, not
imminent, but it fails in the dangerous direction.** `run_recorder_bybit.py` has no disk guard at all.

Compounding it: `data/cashcarry_error.log` is written with `_ERR.write_text(...)` at **five** sites
(`:479, :1133, :1250, :1265, :1525`) — `write_text`, not append. `wc -l` → **1**. Every error
overwrites the last, so during the Jul 31 six-restart storm the file could only ever show one
event. Crash *patterns* are structurally unknowable.

### G21. MEDIUM — the ruin rail's liveness floor is checked once every 24 hours by an organ that is not scheduled. [INT]

`scripts/run_cadence.py:47-53` declares `data/deadman_heartbeat: 0.2` (12 min) as a *"principal
invariant… Tier-3-class"* floor. But `crontab -l | grep -c run_cadence` → **0**. Its only invoker
is `daily_research_cycle.py:46`, which runs `0 2 * * *` — **once per day**, so a 12-minute floor is
sampled every 1,440 minutes. `data/cadence_violation.json` is 17h stale and carries an open breach.

Net effect on the rail: a dead dead-man switch is *restarted* within 3 min (watchdog + systemd) but
**not paged to a human for up to 24 h** — `data_health._HEARTBEATS` covers only
`cashcarry_executor` and `liquidation_listener`, and `run_alerts._checks()` watches
`cashcarry_exec_heartbeat` and the `DEADMAN_FIRED` latch, never `deadman_heartbeat` staleness. If
both auto-restart paths were failing — e.g. under the very memory pressure that killed it (G14) —
nothing tells anyone. Confidence: 0.9.

### G22. MEDIUM — the orphan checker is laundered by the desk's own documentation: 73 scripts / ~10,000 LOC are unreachable and reported clean. [INT][GRE]

```
$ .venv/bin/python scripts/max_audit.py       →  live defects: 8  (no orphan-scripts defect)
$ .venv/bin/python scripts/check_build_standard.py  →  OK -- 37/37 organs meet the build standard
```

An independent transitive pass (roots = cron + systemd + ops/ + deploy/ + .github; edges =
top-level imports and `scripts/X.py` subprocess strings) gives **263 reached, 73 UNREACHED,
10,033 unexplained orphan LOC**.

The mechanism: `check_orphan_scripts` (`max_audit.py:2459`) builds a text blob including `docs/**`
and marks a script reachable if `\b<stem>\b` matches **anywhere**. So a documentation table row is
enough:

```
$ grep -n "hl_flow_alpha" docs/EXECUTION_QUEUE.md
143:| `run_kama_squeeze_backtest.py`, …, `hl_flow_alpha.py`, `capacity_simulator.py` | outbound HTTPS … 403 …
```

**A table row saying "these scripts are blocked in this sandbox" is what marks them alive.** The
checker's own docstring documents three prior instances of this laundering and excludes
`deep_sweep` and `audit_shards` — but not the rest of `docs/`. It also has **no transitivity**, so
an orphan citing another orphan counts (`scripts/hl_breadth_flow.py:2` cites `hl_dir_flow`, and the
citer is itself an orphan) — the exact defect GAP_REGISTER row 83 records as fixed for
`check_orphan_code` and never fixed here.

This matters beyond tidiness because it is *why G11 exists*: `capacity_simulator.py` is one of the
laundered orphans, and the money path depends on its output.

### G23. MEDIUM — a DR restore from `requirements-vps.txt` produces a box that cannot run the desk. [INT][FUT]

```
DECLARED in pyproject, ABSENT from requirements-vps.txt:
  ['arch', 'backtrader', 'pre-commit', 'scikit-learn', 'statsmodels', 'types-pyyaml', 'vectorbt']
PINNED in vps, NOT declared in pyproject:
  ['idna', 'psutil', 'python-dateutil', 'pytz', 'requests', 'tzdata', 'urllib3', 'websockets']
```

`requirements-vps.txt` claims to be *"pinned to the exact versions the desk was built and tested
on."* A restore from it yields a box missing **scikit-learn** (annotated in pyproject as *"a LIVE
entrypoint dep"* for `libs/regime`), plus `statsmodels` and `arch`. Conversely `requests`,
`websockets` and `psutil` are load-bearing at runtime and undeclared in pyproject — the same class
as the `certifi` defect the desk caught and fixed on 2026-07-31 (commit `ea693b8`), still present
in seven other packages.

**And there is no runbook at all:** `find docs/ ops/ deploy/ -iname "*runbook*" -o -iname
"*recovery*" -o -iname "*disaster*" -o -iname "*restore*"` → **no results.** Combined with G10
(inert backup) and G23 (broken requirements), the desk's recovery story is: no documented
procedure, no verified backup, and a dependency manifest that would not rebuild the box.

Dead infra alongside it: `Dockerfile` + `docker-compose.yml` (Jun 20) on a box where
`which docker` → not installed; `requirements-deploy.txt` pins `MetaTrader5>=5.0.45`, Windows-only,
from a platform the desk migrated off.

### G24. MEDIUM — the CI gate's own step is untested, and the risk-control module has zero direct tests. [INT]

Test suite is genuinely large and healthy in shape — **2,754 tests / 278 files, 0 collection
errors**, `tests/ops` 138/138 in 19 s, zero unconditional skips, **zero xfails**, no vacuous tests
(AST-swept), 59/59 RNG uses seeded, no live network. That is a real strength.

The gap is *which* code it covers. Zero test imports:

| module | why it matters |
|---|---|
| `libs/risk/risk_controls.py` | **the risk-control module** — reached only via `scripts/run_stress.py`, which itself has zero tests |
| `scripts/run_stress.py` | **is one of the three CI gate steps.** A green gate partly means "an untested script exited 0" |
| `scripts/rollback_guard.py` | the auto-revert mechanism — untested code that reverts code |
| `libs/risk/capital_events.py` | deposits/withdrawals accounting |
| `libs/execution/retry.py` | order retry/backoff on the live order path (and see G12 — its docstring is false) |
| `libs/ops/alert_channels.py` | the pager delivery path |
| 6 × `libs/data/*_source.py` | six data connectors |

Six `check_*.py` fences have zero test references (`check_gate0_ready`, `check_mypy_ratchet`,
`check_readiness`, `check_shell_hygiene`, `check_spot_testnet`, `check_testnet`); 14 more have
exactly one.

**Mutation score is fresh by luck, not by cadence.** `data/mutation_score.json` measured
`2026-07-30T22:50:32Z` (1.05 d), bar 0.9, `libs/risk/gate.py` at 1.0. But **`run_mutation` is
scheduled nowhere** — absent from `ops/crontab.manifest`, `daily_research_cycle.py`, and
`.github/workflows/`. It runs only when a human types it. And `libs/autodiscovery/validation.py`
scores **0.357** and is `budget_truncated` (14 of 137 sites), so `check_ratchets` **excludes it
entirely** — the anti-false-positive module has never had a complete measurement and is invisible
to the ratchet. Duplicate harness: `run_mutation_test.py` writes `data/mutation_report.json`, which
**does not exist** — never produced its artifact.

**CI parity is broken in both directions:** local `run_ci.py` runs no mypy and no law gate;
GitHub runs no stress harness; local ruff scans only `scripts libs tests` while GitHub scans `.`.
**Green GitHub CI does not imply deployable, and vice versa.**

### G25. LOW-MEDIUM — five divergent Sharpe implementations with no parity test; the promotion pre-gate and the screens feeding it disagree on `ddof` and annualisation. [INT][CON]

Canonical exists (`libs/validation/dsr.py:19 sharpe_ratio(returns, *, ddof=1)`). Five local
reimplementations disagree with it and each other:

```
libs/validation/baselines.py:21      r.std(ddof=1)        NO annualization   ← the promotion pre-gate
scripts/run_derivative_shadow.py:34  np.std(r) (ddof=0)   × sqrt(365)
scripts/run_cot_screen.py:226        a.std()   (ddof=0)   × sqrt(52)
scripts/run_combined_stats.py:76     np.std(r) (ddof=0)   × sqrt(_PPY)
```

`ddof=1` sites: 14. Bare `.std()`: 120. Rolled-own Sharpe bypassing the canonical: 16. On short
samples `ddof=0` inflates Sharpe. The desk already found and fixed this exact class in
`libs/research/axis_screen.py:83-88` (*"the old hardcoded sqrt(365) overstated Sharpe by…"*), and
`scripts/finalize_axis_screens.py:215` records the identical defect as an open finding — **but that
script is an orphan (G22), so the finding never propagates.** ~20 call sites still hardcode
`np.sqrt(365)`. **No parity test exists between any two Sharpe implementations.**

Same shape in the venue layer: `exchangeInfo` parsers have grown from the 4 the desk logged to
**11 files**, with one parity test covering the *spot* pair only — the futures parsers
(`binance_live.py:116-122`, `binance_testnet.py:80-86`) are byte-identical copies and entirely
unpinned. `libs/execution/binance_spot_live.py:101` carries an inline *"one of FOUR near-duplicate
exchangeInfo parsers"* warning that is itself now stale.

---

## 3b. THE THREE THAT OUTRANK EVERYTHING ABOVE (found last, belong first)

### G26. **URGENT / LIVE — a naked unhedged leg was opened 17 minutes before this audit, and the pager is structurally incapable of seeing it. The executor writes an error log that NOTHING reads.** [INT]

`data/cashcarry_error.log`, mtime `2026-08-01 00:34:20`, verbatim:

```
2026-08-01T00:34:20.680978+00:00 unfilled leg MOVEUSDT spot_ok=True fut_ok=False
spot_res={'status': 'FILLED', 'executedQty': '47306.0'}
fut_res={'status': 'REJECTED', 'executedQty': '0.0'}
```

**Spot filled 47,306 units; the futures hedge was REJECTED.** That is a naked directional position
on a book that is supposed to be frozen and delta-neutral. It is testnet/paper (G0's NAV row:
`mode: "PAPER (testnet)"`), which caps the money at risk — but it does **not** cap the finding,
because the *detection* gap is identical on live capital and this is exactly the shape of the
2026-07-19 $2,150 stranded-inventory incident.

**Why nothing fired:**

```
$ grep -n "_ERR" scripts/run_alerts.py
46:_ERR = Path("data/cashcarry_error.log")
$ grep -c "_ERR" scripts/run_alerts.py
1
```

**The variable is declared and never read.** Contrast `_HB` (read at `:258-259`) and `_KILL`
(read at `:265`), which are wired correctly. The executor writes its error log; the pager defines
a path to it and never opens it. Dead-code observability hole, on the money path.

Compounding it, from G20: that same file is written with `write_text` at five sites, so it holds
exactly **one line** — this naked leg has already overwritten whatever preceded it, and will itself
be overwritten by the next error.

**Exactly-what.** (1) Wire `_ERR` into `_checks()` with a freshness window and page on any
`unfilled leg` line — one function, minutes of work. (2) Switch the five `write_text` sites to
append. (3) Reconcile the MOVEUSDT position now. Complexity: trivial. Validation: a synthetic
unfilled-leg line produces a page within one watchdog tick. Confidence: **0.95** (artifact + grep).
**This is the single highest-priority item in this report that is not a security hole.**

### G27. **CRITICAL / PAGER INTEGRITY — the pager runs at ~29% precision: two of the seven standing CRITICALs are provably false, and one of them is the L1.44 guard-death page, which is structurally incapable of ever being true.** [INT][CON]

**(a) `live_guard_dead` — a key-name mismatch makes it fire forever.** `run_alerts.py:293-306`
reads the key `generated`; `run_live_guard.py:265` writes the key `ts`. The key is absent, the
epoch default applies:

```
lg.get("generated", default)      -> 1970-01-01T00:00:00+00:00
computed lg_age MINUTES           = 29,759,099
fires live_guard_dead (>900s)?    = True
REAL freshness from the ts field  = 2026-08-01T00:55:07   (real age 3.4 min)
```

The page body reads *"live guard stale 29759099min (cadence 5min)"*. The comment directly above it
says `# Content 'generated' over mtime (deploys lie fresh).` — it correctly chose content over
mtime, then named a key the writer never emits. **Because the epoch fallback always exceeds 900s,
this check can never distinguish a live guard from a dead one.** L1.44 names this exact page as the
mitigation for the run_live_guard compound risk (*"nothing paged on its age — run_alerts now pages
live_guard_dead within 15 minutes"*). It is installed, it is firing, and it carries zero
information. Adjacent defect: `live_guard_missing` is reachable only via
`except (OSError, ValueError, TypeError)`, so a present-but-malformed artifact routes to
`live_guard_dead` with a nonsense number instead.

**(b) F6's fix was applied and did not work.** `_auth_broken` was correctly rewritten
(`run_alerts.py:193-209`) with an honest docstring naming the 12-day false-page and its role in
feeding the derisk ladder that froze the book on 07-31. But it swapped one dead proxy for two:

```
CRED exists: False
/home/quant/.claude/history.jsonl   mtime=2026-07-16  age_h=376.06
/home/quant/.claude/projects        mtime=2026-07-12  age_h=472.08     → both > 36h → fires
```

**Directory mtime does not propagate from subdirectories.** All activity is one level deeper
(`~/.claude/projects/-home-quant-quant-platform/…jsonl`, mtime `2026-08-01 00:49`), and
`~/.claude/sessions/1731754.json` is seconds fresh. The probe should point at
`~/.claude/sessions/` or the project subdirectory. **F6 is NOT closed** — and it re-fired at
`2026-08-01T00:39:04`.

**(c) The delivery ledger cannot audit itself.** `grep -c auth_broken data/alert_delivery.jsonl`
returns 0 — not because it never fired, but because the ledger's schema is
`['channel','detail','ok','title_sha','ts']` and `title_sha` is a **hash**. Which alert was
delivered is unrecoverable, so **false-page rate cannot be computed even retroactively**. And
`grep -rn "false_page\|alert_quality\|page_precision" scripts/ libs/` → **0 hits**: nothing measures
it. By L1.28a, unmeasured is zero — the desk has now shipped two consecutive false-CRITICAL classes
with no instrument that would catch either.

**(d) Single channel, and the "47% success rate" is an artifact.** 24h of
`data/alert_delivery.jsonl`: 55 deliveries — `ntfy: 26` (all `http 200`), `none: 29` (all
`NOT-ARMED: data/secrets/alert_channels.json absent or empty`). Every page writes one
guaranteed-failure row for the unarmed second channel, so any naive success rate over this file is
meaningless. **Credit where due:** `run_alert_canary.py` is the best-behaved monitor in this audit
— it names the gap, names the owed human step, and refuses to report green:
`NOT-ARMED (human step owed): drop credentials at data/secrets/alert_channels.json -- until then
ntfy is the only path, which is the single point of failure gap #38 exists to remove`.

**Current standing pages (7 simultaneous criticals):** `auth_broken`(false),
`cadence_floor_violation`(stale by 16.7h — content generated 07-31T08:12 still paged verbatim),
`growth_defect`, `kill_switch_stuck`, `live_guard_dead`(false), `principal_action_needed`,
`trade_class_bleeding`. **≥2 of 7 provably false, ≥1 stale → ~29% precision at best.** That is the
same cry-wolf state that fed the derisk ladder into the 07-31 book freeze. A dead-man-adjacent
pager cannot afford it.

### G28. **CRITICAL / SYSTEMIC — 11 fences report OK on absent input, and they share ONE fixable shape. Including `check_utilisation`, whose entire stated thesis is "unmeasured counts as zero".** [INT][CON][GRE]

This is the desk's self-named worst bug class, and it turns out to be *systemic with a single root
cause*. Most fences compute a **correct** refusal status into their JSON artifact (`UNMEASURED`,
`BLIND`, `NEVER-PRODUCED`) — then `main()` maps only **one specific failure string** to a nonzero
exit:

```python
return 2 if rep["status"] == "DARK"           else 0   # check_organ_liveness.py:218
return 2 if rep["status"] == "UNATTRIBUTED"   else 0   # check_mechanism_attribution.py:184
return 2 if rep["status"] == "RETURN-TARGETING" else 0 # check_return_targeting.py:167
return 2 if rep["status"] == "DYING"          else 0   # check_replacement_rate.py:178
return 2 if rep["status"] == "OVERDUE"        else 0   # check_calibration.py:110
```

`UNMEASURED` is not that string → falls through `else 0`. **To cron, systemd and CI these exit
green while measuring nothing.** It survived because the governance tests assert the *status field*
and never the *exit code* (`tests/governance/test_organ_liveness.py:88`).

**Eleven confirmed greens-on-absent:** `data_health.py`, `check_utilisation.py`,
`check_organ_liveness.py`, `check_mypy_ratchet.py`, `check_mechanism_attribution.py`,
`check_return_targeting.py`, `check_replacement_rate.py`, `check_calibration.py`, `data_vitals.py`,
`check_testnet.py`, `check_spot_testnet.py`.

The three that matter most:

- **`data_health.py:83-85`** — `if not p.exists(): checks.append({... "MISSING"}); continue
  # MISSING (not yet started) is not an alert`. `all_ok` is only ANDed *inside* the exists-branch,
  so **every dataset can be missing and it prints `[OK]`** — and `data_health` is one of the 19
  pager keys, so the pager's data-integrity page is fed by a check that greens on absent data.
- **`check_utilisation.py:64-66 + 342`** — the fence whose module docstring says *"unmeasured counts
  as zero"* returns `0.0` for unmeasured rows, and its exit code reads only `idle_unexplained`,
  which `UNMEASURED` rows short-circuit before entering. **All eight ceilings unmeasured → exit 0.**
  (This is a second, independent defect in the same fence as G0.)
- **`check_mechanism_attribution.py`** — docstring at `:37` promises *"UNMEASURED never reads as
  OK"*; `:184` makes it read as OK. Third fabricated docstring of this sweep.

**The fix is one token, and the model implementation already exists in-repo.**
`check_law_families.py:143` and `check_strategy_breadth.py:178` use `!= "OK"` instead of
`== "<one string>"` — **that change fixes five of the eleven immediately.** Twelve fences already
refuse correctly (`check_ratchets`, `check_conversion`, `check_exploration`, `check_freshness`,
`check_law_families`, `check_strategy_breadth`, `check_scheduler_manifest`, `check_shell_hygiene`,
`check_constitution_core`, `check_miner_runway`, `check_sizing_derivation`, `run_alert_canary`), so
this is a consistency gap, not a missing capability.

Two amplifiers: `check_fence_yield.py:56` counts `"UNMEASURED"` as a **firing** value, so an absent
input makes that fence read `FIRED` ("has caught something real") — an inverted signal. And
`check_ratchets` evaluates **9 of the 10 recorded floors**: `test_strength_min_kill_rate` is in
`ratchet_floors.json` but absent from `_METRICS`/`_FILE_METRICS`. **A recorded floor that is never
checked cannot catch a regression.** Also note `pager_delivered_24h` (F10's "fix") is a *boolean*,
not a rate — `_alert_delivery` returns 1.0 on the first `ok` row in 24h, so it cannot see the dead
second channel, the 29 failed rows, or a degradation from 26 pages to 1, and its `max_age` is
`None`. **F10's floor was raised; the metric underneath it is still nearly information-free.**

Complexity: **low, and it is the single highest-leverage change in this report** — it converts
eleven decorative fences into real ones. Confidence: 0.95 (code quoted per file).

### G29. HIGH / DURABILITY — CORRECTING YESTERDAY BY 10×: the irreplaceable set is **7.4 MB**, not 8.7 GB. It would fit in one commit. The organ built to save it replicates 2 of 6 stores, one of them empty, and its drill compares the replica **to itself**. [INT][FUT]

Yesterday's F5 framed the loss as "the moat, 6.6G + 1.5G". That is wrong and the correction changes
the whole recommendation. Classified by re-creatability:

- **Irreplaceable, non-depth: 7,411,081 bytes (7.4 MB)** — `moat/execution_tape/cashcarry_trades.jsonl`
  (135 KB, our own fills at our own timestamps), `external_panel_log.jsonl` (1.68 MB),
  `sor_research.sqlite` (835 KB), `alpha_registry.sqlite` (483 KB),
  `venue_divergence_shadow.jsonl` (441 KB), `cro_ai_logs/` (425 KB), `oi_ls_live.jsonl` (396 KB),
  `live_combined_state.json` (378 KB), `cashcarry_trades.json` (128 KB),
  **`cashcarry_positions.json` (1,066 bytes — the live book)**, `deadman_state.json` (268 bytes).
- **Irreplaceable, depth ladders: ~0.82 GB** (`moat/fut` 0.627 + `moat/spot` 0.195) — 20-level
  ladders at ~7.85 s cadence, 07-17 → 08-01. Binance's public archive has `aggTrades` and
  futures-only percentile `bookDepth`, not a 20-level ladder, and nothing for spot depth.
  *(Confidence: high for spot, medium for futures — worth one external check.)*
- **Re-downloadable, ~8.2 GB** — `moat/bybit` 6.12 GB (already refuted as a moat: free first-party
  archive at quote-saver.bycsi.com is strictly better — 200 levels vs our 25, 100 ms vs 4080 ms,
  345 d vs 10.6 d), `lake/bronze` 1.365 GB, aggTrades share 0.67 GB, `data/rollback` 0.084 GB.

**So the recommendation flips.** Yesterday proposed a €4/mo Storage Box for 8 GB. The honest answer
is: **the entire irreplaceable non-depth set fits in a single git commit to a remote the desk
already pushes to, today, for free.** The depth ladders are the only part that needs object
storage, and only ~0.82 GB of it.

**And the organ that exists to do this is worse than inert.** `backups/` totals **52 K**:

```
$ .venv/bin/python -c "...sqlite_master..."
REPLICA tables: []
SOURCE  tables: [22 tables, 575 rows]
```

`backups/moat/manifest.json` certifies `sor_research: REPLICATED, bytes: 0`, four stores `ABSENT`
(three of which **exist on disk**), `not_covered_bytes: {}` (meaning `data/moat` was `.exists() ==
False` at run time, while it is 7.2 G here), `disk_free_pct: 11.41` (actual: 59.48%), and
**`restore_drill_passed: true`**. Both committed runs executed against a tree where `data/` did not
exist — **the signature of a git worktree or fresh clone**, where `.gitignore:11 data/*` guarantees
it is empty.

**The drill's exact defect, in three lines:** `run_moat_backup.py:95` `return _sha256(dst)` — the
snapshot function returns the **destination** hash; `:151` stores that as the manifest digest;
`:125` then checks `_sha256(p) != digest` where `p` is the **destination**. **It compares the
replica to itself and is always true.** It genuinely catches post-hoc corruption of the replica
(and a test proves that) — it can never verify *fidelity to the source*. Line `:119`
`if entry["status"] != "REPLICATED": continue` means the four ABSENT stores are never drilled at
all. The test fixture seeds `data/research_memory.db`, **a phantom with 5 readers and 0 creators
that does not exist in production**, and `test_absent_store_is_recorded_never_silent` *asserts the
real production store is ABSENT* — the suite bakes the failure in as expected behaviour.

**New and worse than "inert":** `backups/` is a **tracked** path and every run overwrites in place,
so any future run from a worktree **clobbers a good replica with an empty one**, and
`git_snapshot.py:26`'s `git add -A` pushes the clobber. *(Note: the cron line `55 3 * * *` was added
07-31 08:39 and had not yet fired at audit time — the first real firing is imminent.)*

**Two more durability defects worth their own lines:**

**(a) The disk fuse ordering is inverted.** `run_moat_backup.py:48 FUSE_PCT = 15.0` fires at 85%
used; the recorders and the execution tape stop writing at **80%** used
(`run_recorder.py:113`, `run_recorder_spot.py:112`, `execution_tape.py:34`). **80% is reached
first**, so on the measured trajectory the recorders go silent at ~22 days and the "early warning"
fires at ~25 days — **three days after the event it exists to warn about**, while its own docstring
asserts the opposite ordering. Measured growth is `0.715 GB/day` (stable across 6 days: 0.674,
0.734, 0.729, 0.728, 0.704, 0.728), giving **write-stop ≈ 2026-08-23, disk-full ≈ 2026-09-03**.
And still **no fence pages a human**: `grep -cE "disk_usage|statvfs|disk_free|DISK"` over
`data_health.py`, `max_audit.py`, `check_ratchets.py`, `run_alerts.py` → **0, 0, 0, 0**.

**(b) The live book is written NON-atomically, while the fix sits one file away.**
`run_deadman_switch.py:45-62` does it right, with a docstring naming this exact hazard (*"a death in
that window (OOM kill, host reboot, container stop, disk full) leaves EMPTY or PARTIAL json"*):
`tmp.write_text(...); os.replace(tmp, _STATE)`. But `run_cashcarry_executor.py:923-924` is
`_STATE.write_text(json.dumps(state, indent=2), "utf-8")` — truncate-then-write on
`data/cashcarry_positions.json`, **the record of every open carry**. Every reader
(`libs/portfolio/live_book.py:26-30`, `run_stranded_recovery.py:83`,
`run_deadman_stranded_sweep.py:47`, `run_recorder.py:61`) falls back to `{}` on `JSONDecodeError`,
so **a torn file reads as "the book is flat"** — and `run_deadman_stranded_sweep` treats symbols
absent from that file as sweepable. Crash-during-write plus disk-full is a plausible joint event
(see (a)). Atomic helpers exist correctly at 6+ other sites; there is **no shared `atomic_write`
helper**, so the idiom is re-derived at 8+ places and was simply not re-derived here.

**Hetzner backups are claimed but never verified.** `docs/GAP_REGISTER.md:463` row #13 is marked
`resolved` with the note *"operator should confirm the first snapshot appears in the Hetzner console
within 24h"* — dated 2026-07-16. **No evidence that confirmation ever happened**, and the register
counts it as closed. The desk's only claimed defence against disk death is an unverified 16-day-old
promise. `lsblk` → single `sda`; `/proc/mdstat` → no RAID; one filesystem, one box, one region
(Hetzner CX, hel1/Helsinki). **No runbook exists** (`find docs/ ops/ deploy/ -iname "*runbook*" -o
-iname "*recovery*" -o -iname "*disaster*"` → nothing), no RTO, and **no data restore has ever been
performed** — `data/drill_log.jsonl`'s three drills are *rail* drills
(`host_death_naked_clock`, `derisk_ladder`, `ruin_rail_reentry`), not restores.

## 3c. PERSPECTIVE COVERAGE — the four lenses not yet carried by a finding above

**FUTURE (2-3 years out).** Two of this report's largest classes are *artifacts of a single box*
and dissolve at the next capacity step, so they should not be over-engineered now: the OOM
contention (G14), the 03:00–07:00 herd (U8), and the CI-gate CPU tax (G8) are all "2 cores, 3.8 GB,
no swap" problems. The compounding-correct move is **not** to tune schedules — it is to split the
research organ pool off the money-path box. A second €4-6/mo VM running every LLM organ and every
research fence would: delete the executor's OOM exposure, delete brain-mutex starvation (G16),
delete the deploy gate's CPU contention with the executor, and make `brain_seat_throughput` (G5)
measurable by construction. That is one recurring line item against six findings, and it is the
highest-ROI *structural* change on this list.

**GREENFIELD (rebuild from validated knowledge only).** Rebuilt today, three things would not
exist: (a) **the cron⊕systemd split** — 120 cron lines + 21 units, with 12 seat lines that are
permanent no-ops (G18), two planes that don't share locks, and a manifest fence blind to duplicates
(G17); one plane with real units, `MemoryMax`, and timers would delete G14, G17 and G18 together.
(b) **The watchdog** — its only unique behaviour today is a doomed spawn (G15); `quant-refresh`
already runs its four scripts and systemd already restarts its four daemons. L2.9 verdict: **MERGE
into quant-refresh, retire the rest**. (c) **`max_audit.py` at 3,958 lines** holding ~40 detectors
*and* their allowlist in one file — that co-location is precisely where G22's laundering hides.

**FRONTIER (recently possible, unexploited).** Nothing here needs a new model or a new paper —
which is itself the finding, and it is a *negative* one worth stating plainly: **this subsystem's
gap to tier-1 is not technological.** The one genuinely new capability the desk should adopt is
**gating CI in a scratch checkout / ephemeral worktree before merge** (`git worktree` + a
throwaway venv). It closes G3's RCE and G8(a)'s unvetted-execution window in one change, and it is
free.

**NEGATIVE SPACE (never asked, never collected).** What no one has ever built, in descending order
of harm: (1) **any time-series store at all** — `grep -rln "prometheus\|statsd\|influx\|
opentelemetry\|datadog\|grafana" scripts/ libs/` → **0 files**; all monitoring is point-in-time JSON
re-read per tick, so **no rate, derivative, or trend alert is possible by construction** — this is
the single root cause behind five of the ABSENT rows below and behind `pager_delivered_24h` having
to collapse to a boolean. (2) **No alert exists for**: disk free, memory/OOM, CPU saturation, clock
drift, certificate expiry, venue API error rate, restart storms, log growth, network egress
failure, git push failure, backup lag, **CI red** (`grep -ciE "ci_red|ci_fail|run_ci"
scripts/run_alerts.py` → 0, while master is red *right now*), and **unhedged leg** (G26).
(3) **No run/correlation id in any log** — 49 files, all free text, zero JSON; one organ run cannot
be traced end-to-end. (4) **No false-page rate, ever measured.** (5) **No shared `atomic_write`
helper** — the idiom is re-derived at 8+ sites and simply not re-derived at the one that holds the
live book (G29b). (6) **No runbook, no RTO, no rehearsed restore.**

**EXTERNAL — the motive-similar tier-1 cohort.** Three concrete practice gaps, each transferable
at our capacity band: **HRT/Jump (sim-prod parity)** would not tolerate a deploy gate whose local
and CI step-sets are non-overlapping in both directions (G24) — parity means one gate, run once,
before merge. **Jane Street (correctness culture, "what makes this trade wrong")** is the direct
inversion of G26: their answer to an unfilled hedge leg is a hard stop and a human, not a line in a
file nothing reads. **Wintermute/GSR (24/7 crypto ops)** run venue-error-rate and ban-state as
first-class paged metrics — the desk built exactly that breaker on 07-31 and did not wire it to the
order path (G13). **Negative exemplars:** the rail that would have stopped *Alameda* — segregated
accounting plus a ruin rail that cannot be overridden — **exists here and is armed** (S12); the
rail that would have caught *Archegos* — position truth independent of the trader's own record —
is the one **G29b undermines**, because a torn `cashcarry_positions.json` reads as a flat book to
every consumer including the stranded sweep.

**Tier-1 register impact (per the standing rule that the sweep re-grades on evidence):**
`monitoring_observability` should drop **T2 → T3** (a ~29% precision pager, no time-series, no
false-page metric, and 11 fences greening on absent input do not meet a T2 bar).
`security_opsec` should drop **T3 → T4** (a proven-anonymous public research web root plus a live
push-capable PAT feeding auto-deploy is below "advanced independent").
`data_moat` should drop **T2 → T3** (its stated closer was "backups/moat replicas live
(run_moat_backup)" — that organ is now measured inert with a self-certifying drill).
`simulation_prod_parity` holds at T2 but its closer text should name the local-vs-CI step
divergence. `risk_rails` holds at T2 — the rails are armed and drilled, but G9 and G21 must be in
its closer.

## 4. WHAT WE TEST NEXT (concrete experiments, success criteria, retirement conditions)

Ranked by (impact × confidence) / (cost × maintenance). **T1–T4 are same-day; T1 is minutes.**

**T1 — Reconcile the naked leg and wire `_ERR` (G26).** Check the venue for the MOVEUSDT spot
position opened at 00:34:20Z against a rejected futures hedge; flatten or hedge it. Then add
`_ERR` to `run_alerts._checks()` with a freshness window, and switch the five `write_text` sites to
append. **Success:** a synthetic `unfilled leg` line pages within one watchdog tick; `wc -l
data/cashcarry_error.log` grows instead of staying at 1. **Retire:** never.

**T2 — One-token fix to eleven fences (G28).** Change `== "<one string>"` to `!= "OK"` in the five
named `main()` returns; give `data_health`, `check_utilisation`, `check_testnet`,
`check_spot_testnet`, `check_mypy_ratchet`, `data_vitals` the same refusal path. **Success:** each
of the eleven, run against a tree with its input renamed away, exits non-zero. **Add the missing
assertion** — the governance tests assert `rep["status"]` and never the exit code, which is why
this survived. **Retire:** never; add exit-code assertions to the fence test template.

**T3 — Fix the log reaper and re-measure everything that depended on it (G7).** Change
`data/cro_ai_logs/*.log` → `2026*_*.log` in `ops/run_cro_ai.sh:99`; add a logrotate stanza bounded
by age and size. **Success:** after one brain cycle, `ls data/cro_ai_logs/*.log | wc -l` > 30 and
daily-fence logs survive; `scheduler_cadence` moves off 33%. **Then re-run the organ-liveness
question from scratch** — every "organ never ran" conclusion in this and prior sweeps was measured
against deleted evidence and must be re-derived. **Retire:** never.

**T4 — Unstick the deploy and make the gate honest (G8).** `ruff check --fix
tests/validation/test_gate_power_audit.py`; split rc3 into its own `could-not-gate` status with a
retry; memoize the red SHA; record actual `HEAD` in `pull_deploy_state.json`. **Success:**
`pull_deploy_state.json.status == "deployed"` with `to == HEAD`; zero revert-flaps on unchanged
HEAD over 24 h; CI stops re-running on a known-red commit. **Retire:** when the flap-rate fence
reads 0 for 7 days.

**T5 — Gate in a scratch checkout before merge (G3 + G8a).** `git worktree add` the fetched commit,
run the gate there, merge only on green. **Success:** an intentionally-malicious test commit pushed
to a scratch remote executes **nothing** on the live tree; `HEAD` never equals an ungated commit.
**This is the single highest-leverage structural fix in the report** — it closes an RCE and the
unvetted-execution window together. **Retire:** never.

**T6 — Rotate the PAT and put Access on the tunnel (G1 + G2).** Treat the token as disclosed
(it is in this and every prior audit transcript); reissue fine-grained `contents:read` via a
credential helper outside the repo dir. Enable a Cloudflare Access policy on `dash.quanttt.xyz` —
**dashboard-side, no deploy needed**. Then rebind both servers to `127.0.0.1` and drop the
`Access-Control-Allow-Origin: *`. **Success:** off-box `curl https://dash.quanttt.xyz/` returns an
Access challenge, not desk HTML; the old token 401s. **Then run `sudo ufw status numbered` (U1).**

**T7 — Prove or refute the 20:00Z double-fire, today (G18).** Watch
`quant-blindrediscovery.timer` and `/tmp/seat_blindrediscovery.lock` at 20:00 UTC on 2026-08-01
(Saturday **and** the 1st — both paths fire). **Success criterion is the prediction itself:** either
two Claude digs launch into ~138 MB free (confirming `enabled ≠ active` is the bug), or one defers
and is logged as a 0-second success (confirming G16's deferral-looks-like-success). **Either
outcome is a finding.** Fix: swap the guard to `is-active`. **This is the cheapest falsifiable test
on the list and it expires today.**

**T8 — Read `backups/moat/manifest.json` after the 03:55 firing (U10, G29).** The cron line's
first real firing on a tree where `data/` exists happens ~3 h after this report. **Success:** ≥4 of
6 stores `REPLICATED` with non-zero bytes. **If it still reports ABSENT on files that exist, the
CWD hypothesis is confirmed and the fix is a `chdir`/root-resolution change.** Then fix the drill
to hash the **source** (`run_moat_backup.py:95` returns `_sha256(dst)`; it must return the source
digest) and make an `ABSENT` store fail rather than `continue` at `:119`. **Retire:** never — and
add a real restore drill, which has never once been performed.

**T9 — Commit the 7.4 MB irreplaceable set (G29).** Add `alpha_registry.sqlite`,
`cashcarry_positions.json`, `cashcarry_trades.json`, `venue_divergence_shadow.jsonl`,
`oi_ls_live.jsonl`, `external_panel_log.jsonl`, `live_combined_state.json` to `_STORES`. **Success:**
the offsite copy exists at the next push. **This supersedes yesterday's €4/mo Storage Box
recommendation for everything except the ~0.82 GB of depth ladders** — resolve U2 before spending.
Watch the repo-growth side effect: an 835 KB sqlite committed daily as a full blob is
~0.3-1 MB/day of unprunable growth on a 40 MB repo.

**T10 — Make the atomic-write fix one file over (G29b).** Apply
`run_deadman_switch.py:45-62`'s `tmp + os.replace` to `run_cashcarry_executor.py:923-924`, `:126`,
`:1376`, and extract a shared `libs/ops/atomic_write` helper for the 8+ re-derived sites.
**Success:** a `kill -9` mid-write leaves `cashcarry_positions.json` either fully old or fully new,
never empty. **Retire:** never — a torn book file reads as "flat" to the stranded sweep.

**T11 — Wire the ban breaker to the order path (G13).** Import `_ban_remaining()` into
`binance_testnet.py` and `binance_spot_testnet.py`. **Success:** with `data/BINANCE_BAN_UNTIL` set
in the future, an order attempt fails fast instead of hitting the venue. **Retire:** never.

**T12 — Resource-limit the money path (G14).** `MemoryMax=` on the five always-on units,
`OOMScoreAdjust=-500` on executor and dead-man, `StartLimitIntervalUSec > RestartSec` so the
limiter can actually fire, and a `/tmp` reaper (1.1 GB of RAM in tmpfs). **Success:** `systemctl
show quant-cashcarry -p MemoryMax` is finite; the executor is no longer the top persistent
`oom_score`; `free -m` shared drops below ~300 MB. **Retire:** when the research pool moves off-box
(§3c FUTURE), which deletes the contention entirely.

**T13 — Fix the two pager falsehoods and start measuring precision (G27).** Point `_auth_broken`
at `~/.claude/sessions/` (or the project subdirectory — directory mtime does not propagate); change
`run_alerts.py:293` to read `ts` (or make `run_live_guard.py:265` write `generated`). Add the alert
*key* to `alert_delivery.jsonl` rows so false-page rate becomes computable, and add a
`false_page_rate` ratchet. **Success:** 48 h with zero `auth_broken` and zero `live_guard_dead`
pages while both subsystems demonstrably run; standing criticals drop from 7. **Retire:** never —
precision becomes a ratcheted metric.

**T14 — Schedule `run_cadence` and page on dead-man staleness directly (G21).** A 12-minute
Tier-3 floor evaluated once per day is not a floor. Add `data/deadman_heartbeat` to
`data_health._HEARTBEATS` so absence is not indistinguishable from health. **Success:** killing the
dead-man in a drill pages within 15 min. **Retire:** never.

**T15 — Fix `organ_catchup`'s unreachable success threshold (G16).** Make the deep-sweep success
test artifact-based (dated reports exist) or drop the 1200-byte bar below the resume path's 783.
**Success:** ≤1 deep-sweep fire per declared cadence; brain-mutex hold time per day falls; the seat
services stop exiting in 0 s. **Retire:** never — and add a fence for "success threshold a
successful run cannot reach", which is a reusable defect class.

**T16 — Give `brain_seat_throughput` a denominator (G5).** Have `organ_catchup` append its
"field busy" decisions to `brain_mutex.log`, or log acquisitions as well as deferrals. **Success:**
the ceiling leaves UNMEASURED and L1.28c's "raise cadence vs buy a second seat" becomes arithmetic.
**Retire:** never.
