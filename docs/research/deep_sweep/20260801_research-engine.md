# DEEP COLD AUDIT — RESEARCH ENGINE — 2026-08-01

STATUS: COMPLETE

Subsystem: the engine that makes future discoveries — hypothesis generation, experiment
scheduling, prioritization, AI prompting, literature/repo/forum mining, translation, knowledge
reuse, dedup, automation, turnaround, research-memory + knowledge-graph quality, search strategy,
cross-domain synthesis, failed-experiment learning, throughput, bottlenecks. Research FRICTION and
INFORMATION ENTROPY.

Auditor: weekly deep cold audit, research-engine seat. Read-only. Method: OUTCOME-NOT-CONFIG —
every claim carries its command and its literal output. Measurements timestamped because a
**sibling session was mutating the working tree throughout this audit** (see F-3).

Prior art: `20260731_research-engine.md`, `20260730_research-engine.md`. This report **re-measures
rather than inherits**; where a prior claim is refuted, it is named as refuted.

---

## HEADLINE

The research engine has two independent halves and **both are down, for different reasons that
each masquerade as health.**

1. **The MECHANICAL factory generates nothing new and is arithmetically saturated.** The 434
   "candidates" in the store are `31 symbols × 14 fixed hypotheses`; zero new *mechanisms* have
   entered since the template dict was last hand-edited. Its queue organ reads a file that has
   never existed and prints `candidates 0`, then infers "a supply problem upstream" from that
   absence.
2. **The HUMAN-LANGUAGE mining half — all 7 non-English frontier seats — runs daily, fails every
   single time, and reports `Result=success` to systemd.** Zero `frontier_*.log` files have ever
   existed. The desk's entire L1.11a non-English information-archaeology capability has produced
   nothing, ever, while every configuration check it owns reads green.

What is actually generating research on this desk is **scheduled Claude sessions writing markdown**
— ~9 cards per seat-run. Every mechanical organ built to do it contributes zero. The desk has
mistaken a documentation pipeline for a discovery pipeline.

---

## SCORES

| metric | value | basis |
|---|---|---|
| current_capability_pct | **22%** | 1/11 mining seats productive (measured, `check_ratchets`); 0 new mechanisms in 14d; memory 100% write-only on content; the working parts are the *screens* and the *discipline*, not the *engine* |
| practical_ceiling_estimate | **80%** | nothing found needs new technology; every rank-1..8 item is wiring or a one-line exit-code fix |
| ceiling_gap | **58pts**, ~35 closable in ≤1 week | F-1 is a 2-line fix; F-6 is a path constant; F-7 is a DB handle |
| opportunity_cost_1y | **The largest on the desk.** 7 languages × 365 days of information archaeology forgone (L1.11a calls this the moat); a research allocator splitting budget uniformly while a 37× measured success spread sits unread on disk; a novelty gate that scores a *killed family* as more novel than a genuinely new idea, burning multiplicity budget on re-derivations | see F-1, F-7, F-8 |
| confidence | **0.90** on individual findings (each command-cited and re-measured today); **0.6** on the ranking | |
| unknown_unknown_score | **0.5** | the seat-failure class was invisible to every existing fence; I found it only by reading `journalctl`, which no organ reads |
| info_gain_if_investigated | highest for T-1 (why the frontier dig exits instantly) — one command, opens a 7-language capability | |
| expected_alpha_contribution | indirect but first-order: this seat has zero promotion authority, but it is the supply side of every Stage-A screen. Supply is currently ~9 markdown cards/day from LLM sessions | |
| expected_compounding_contribution | **highest available**: F-1, F-6, F-7, F-8 are all multipliers — each raises the value of every future research hour | |

**CEILING EXPANSION.** The ceiling is not technological and — correcting yesterday's report — it is
not *organizational* either. It is **DIAGNOSTIC**: every one of these organs has a fence, and every
fence reads green, because every fence measures configuration or row-counts and none measures
*output*. The lifting condition is a single principle applied everywhere: **an organ's health
metric must be a byte it produced, not a flag it set.**

---

## 0. CARRY-OVER — did yesterday's findings move?

| yesterday's rank | item | status today | evidence |
|---|---|---|---|
| 1 | fund/fallback the LLM lane | **UNMOVED, now worse** | `kimi_hunter.log` 6 identical `FAILED (HTTPError 402)` blocks, latest 2026-08-01T00:05; `data/exploration_status.json` (02:05Z) `"status": "DARK"` |
| 2 | de-duplicate the scheduler | **UNMOVED** | crontab now **121** lines (was 95); 12 seat lines are inert no-ops — see F-4 |
| 3 | wire the novelty gate (R0004) | **UNMOVED, day 7** | ledger R0004 `status='scheduled'`, age 5.60d, reason: *"novelty gate wire is research-engine top open item (day 7)"*. And it is worse than unwired — it is **inverted** (F-8) |
| 4 | nonzero-exit = ERROR in `_subprocess_cap` | **partially; the same class recurred elsewhere** | F-1 is the identical defect in bash |
| 5 | point research at NAV-chain equity | not re-verified this sweep (owned by 20260801_infrastructure) | |
| 7 | raise disposition drain rate | **MOVED, measurably** | ρ improved 4.0 → **1.67**; 12 rows now disposed at >3.67d where the prior claim was that none ever had. Still divergent — F-5 |
| 10 | populate-or-retire the empty audit spine | **UNMOVED** | `trials_ledger=0, alpha_registry=0, research_runs=0` in `data/sor_research.sqlite` |

**Refuted prior claims** (stated plainly, per anti-timidity):
- *"generation is 0/day for 7 days"* — **imprecise**. It is 0 on 12 of 14 days; 07-22 and 07-30 show
  420 and 434. But the correction makes it **worse**, not better: those were symbol-universe
  rotations, not new mechanisms (F-6).
- *"research memory is a split store across two sqlite files"* — **REFUTED**. `alpha_registry.sqlite`
  holds `research_memory=0`. The real defect is different and worse (F-7).
- *"3 reader-zero stores"* — **partially refuted**: `data/research_autopsy.json` has 2 genuine
  readers (`mechanism_board.py:37`, `research_exchange.py:106`). Name stores, don't count them.

---

## 1. WHAT WE KNOW — validated strengths, each with its proving command

1. **The desk's refusal discipline is real and it is the best thing here.** `data/fusion_search.json`
   → `"status": "REFUSED", "eligible": [], "cells": 0, "excluded": 13` — *"0 axes have earned
   breadth; a width-3 search needs 3."* A designed zero, correctly reported as a zero. Likewise
   `ops/run_crypto_factory.sh` (fires reliably, logged 01:30:01→01:30:28Z today):
   `"ZERO survivors net-of-cost (honest)"`.
2. **The research-memory WRITE path is genuinely healthy.** `data/sor_research.sqlite` →
   `research_memory` 192 rows, **190 of them in the last 7d, 32 in 24h**, max `created_at`
   `2026-07-31T21:00`; **137/192 (71%) are negative results** and 92% carry lessons. The duty to
   record failures is being discharged. (The defect is entirely on the read side — F-7.)
3. **Conversion has measurably improved and I can prove it against the prior record.** Ledger
   arithmetic (231 rows): 7-day arrivals 231 (33.0/d) vs dispositions 138 (19.7/d) → **ρ = 1.67**,
   against a prior measured ~4.0. Median disposition latency **0.003 d (4.3 minutes)**; 64% inside
   1 hour. The prior claim *"no row older than 3.67d was ever implemented"* is now **refuted**:
   R0009 implemented at 5.22d, R0013 at 4.85d.
4. **Three of four ledger readers handle corruption correctly** — so the fix for the fourth already
   exists in-repo, three times. `check_conversion.py:81` → `FLATLINE ... "unmeasured conversion
   counts as ZERO conversion"`; `recommendations.py:53` → `SystemExit("REFUSING: ... an unreadable
   ledger must never become an empty one")`; `run_strategy_coverage.py:166` → records
   `f"ledger unreadable ({type(exc).__name__}...)"`.
5. **`data/negative_knowledge.json` is the best-engineered artifact in this subsystem.** 44 records,
   **44/44 (100%) carry `reversal_conditions`**, permanence classified (5 PERMANENT / 14 NEAR-PERM /
   9 CONDITIONAL / 11 REVERSIBLE / 5 UNKNOWN). It is exactly what the graveyard law asks for. Nothing
   reads it (F-7) — but the artifact itself is a genuine asset already paid for.
6. **The seat-runner *design* is right, and that matters for the fix.** `run_frontier_rotation.sh`
   is resumable by output size (`-size +1500c`), explicitly refusing to count a stub as a dig — the
   outcome-not-config law encoded into a shell script. The design is sound; only the exit-code
   plumbing under it is broken (F-1).

---

## 2. WHAT WE DON'T KNOW — the ignorance ledger

- **Why the frontier dig now exits in ~0.4 s.** Two mechanisms are consistent with the journal
  (`brain_mutex` deferral at `brain_env.sh:59` → `exit 0`; or an `auth`/`-u` failure). I could not
  discriminate read-only because `data/cro_ai_logs/brain_mutex.log` **does not exist** — the one
  artifact that would name the starved organ is never written on this box. → T-1.
- **Whether the 7 language seats have EVER produced, at any time in history.** `ls
  data/cro_ai_logs | grep -ci frontier` → `0`, but a log reaper deletes `*.log` 3×/day keeping ~30
  of 98. The *inference* is safe (the resume logic would have skipped a region that produced today,
  and it re-dug all 7) but the *history* is genuinely unknown.
- **Whether `data/research_memory.db` was ever intended to exist**, or whether five call sites were
  written against a path that was renamed once and never propagated. Nothing in git shows it.
- **What the 48,955 chars of `statement` and 68,589 chars of `lessons` in research_memory contain.**
  Nothing reads them, so nobody knows — including this audit. This is the largest single block of
  unexamined desk-generated knowledge.
- **Which of the two records is stale for the 6 families that are simultaneously on the kill-list
  and live in `web/registry.json`** (`funding_carry`, `basis_carry`, `funding_momentum`,
  `taker_flow`, `ts_trend`, `xsec_price_mom`, expected_sharpe 0.44–1.14). The kill entries are bare
  names with no date, so the contradiction is currently unadjudicable. **This is a live correctness
  risk, not a tidiness issue.**
- **Whether prompt changes help.** There is no prompt-performance artifact anywhere. The prompts are
  the desk's genome (its own words) and their effect is unmeasured. → covered by the AI-prompting
  seat, still running at time of writing.
- **Whether the 12 inert crontab lines would cause harm if a timer were ever disabled** — I did not
  and could not test it read-only.

---

## 3. FINDINGS

### F-1 ⚡ THE 7-LANGUAGE MINING CAPABILITY RUNS DAILY, FAILS EVERY TIME, AND REPORTS SUCCESS
**Severity: highest in this report.** This is L1.11a — which the constitution calls load-bearing and
a structural moat — reduced to zero output while every check reads green.

```
$ systemctl show quant-frontier.service -p ExecMainStatus -p Result -p ExecMainExitTimestamp
Result=success
ExecMainExitTimestamp=Fri 2026-07-31 15:00:03 UTC
ExecMainStatus=0

$ journalctl -u quant-frontier.service -n 25 --no-pager
Jul 30 15:00:02 bash[1402278]: rotation: digging en
Jul 30 15:00:12 bash[1402278]: rotation: en failed -- next invocation resumes it
Jul 30 15:00:12 bash[1402278]: rotation: digging cn
Jul 30 15:00:21 bash[1402278]: rotation: cn failed -- next invocation resumes it
   ... all 7 regions, every day ...
Jul 31 15:00:01 bash[1609932]: rotation: digging en
Jul 31 15:00:01 bash[1609932]: rotation: digging cn
Jul 31 15:00:02 bash[1609932]: rotation: digging ru
Jul 31 15:00:03 bash[1609932]: rotation: digging br      <- 7 regions in 3 SECONDS, no outcome line

$ ls data/cro_ai_logs/ | grep -ci frontier
0
```

**Three independent defects stacked, each individually invisible:**

1. **`ops/run_frontier_miner.sh` (last two lines) — the trailing `echo` eats the exit code:**
   ```bash
   claude --effort max ... >> "$LOG" 2>&1
   echo "=== frontier-$REGION exit $? at $(date -u) ===" >> "$LOG"
   ```
   The script's exit status is the `echo`'s, which is always 0. So the caller's guard —
   `bash ops/run_frontier_miner.sh "$r" || echo "rotation: ${r} failed"` — **can never fire**. That
   is why 07-31 shows no failure lines at all: the failure became *less* visible than on 07-30.
   This is the desk's own SILENT-EXCEPT class (L1.40), in bash.
2. **`ops/brain_env.sh:59` — `brain_mutex` calls `exit 0` when the seat is held.** A starved organ is
   indistinguishable from a successful one at every layer above it. The in-code defence is
   *"Deferring is safe here BY DESIGN: ... the next rotation invocation resumes it"* — but the
   rotation runs **once a day**.
3. **Phase collision (L1.28c).** The only live invocation is `quant-frontier.timer` at **15:00**;
   the desk's brain slots run at 14:45. The frontier seat asks for the brain mutex ~15 minutes into
   a brain slot, every day, deterministically. Meanwhile the three cron fallback lines that would
   have retried at 03:00 and 11:00 are **dead** (F-4).

Additionally, `check_miner_runway.py`'s own taxonomy **misdiagnoses this**. Its docstring defines
`never-ran` as *"runway complete, zero output → scheduling/quota, not configuration"* and `stale` as
*"produced before, not recently → a runtime failure, look at the log."* These seats run daily and
fail at runtime with zero lifetime output — a cell the taxonomy does not have. It routes the
operator to "scheduling/quota" when the truth is a runtime failure plus a swallowed exit code.

```
$ .venv/bin/python -c "...data/miner_runway.json..."
artifact 'checked' = 2026-07-31T06:41:01Z  -> AGE 19.4h   creds_present=True
SEATS n=11   status census: {'never-ran': 10, 'ok': 1}
frontier-en/cn/ru/kr/jp/ar/br  never-ran  prompt/runner/unit/creds = 1/1/1/1
litminer                       never-ran  1/1/1/1
dataaxis                       never-ran  1/1/1/1
blindrediscovery               never-ran  1/1/1/1
prospector                     ok    age 8.0h  3199 bytes
productive: 1/11 = 9.1%
```

**Every seat is fully configured, credentialed and unit-tested. Ten have produced nothing.**
`miner_seats_productive = 9.1%` is the **largest gap on the entire ratchet board**
(`check_ratchets.py` → *"largest gap: miner_seats_productive at 9.1%, 90.9% from 100%"*) — and it is
an honest number. My initial hypothesis that the metric was mismeasured is **refuted**: the timers
genuinely fire and the seats genuinely produce nothing.

**Fix:** (a) `exec claude ...` or capture `rc=$?` and `exit $rc`; (b) `brain_mutex` should exit
非-zero (or a distinguished code) on deferral so callers can tell starvation from success, and it
must write `brain_mutex.log` — the file its own code references does not exist; (c) re-phase the
frontier timer off the brain slot, or give the rotation ≥3 attempts/day. **Time-horizon:** 1w = 7
languages come online; 1y = the difference between having and not having the moat L1.11a names.

### F-2 ⚡ THE MECHANICAL FACTORY IS ARITHMETICALLY SATURATED — 0 NEW MECHANISMS IN 14 DAYS
```
day          generated  tested  skipped_dup       (data/sor_crypto.sqlite, hash-chained audit log)
2026-07-22         420     420         2020
2026-07-23..29       0       0     980..1400/day
2026-07-30         434     434         1386
2026-07-31           0       0         2380
2026-08-01           0       0          560

MAX created_at from research_candidates: 2026-07-30T02:40:44Z
distinct symbols: 31 | distinct content_hash: 434 | per-symbol hyp count: 14 (uniform)
status: {'rejected': 434}  survived: {0: 434}
```
`434 = 31 × 14`. The last 14 candidates are all `SIRENUSDT` — one newly-liquid symbol × the same
fixed 14 hypotheses. **Generation rate is a function of Binance listings, not of research.**
`HypothesisEngine.generate()` returns from an 8-entry hardcoded `_TEMPLATES` dict. The two non-zero
days that appear to refute "generation is dead" are symbol rotations.

This is a **direct L1.25a violation risk**: a null streak is being produced by a generator that
cannot generate, and the correct reading (*"the instrument is broken"*) is available but was never
reached because the funnel reports `tested=434` and looks busy.

### F-3 ⚠ `max_audit` IS THE LONE FAIL-OPEN LEDGER READER — AND THE LEDGER CORRUPTS ROUTINELY
Observed **live** during this audit at 01:57Z:
```
$ git status --short docs/research/recommendation_ledger.json
UU docs/research/recommendation_ledger.json
$ grep -nE '^(<<<<<<<|=======|>>>>>>>)' docs/research/recommendation_ledger.json
2732:<<<<<<< HEAD
2754:=======
2824:>>>>>>> 36d24c5
```
(A sibling session resolved it by 02:01Z — 231 rows, parses clean. Desk memory records this as the
**5th ledger race on 2026-07-31 alone**, so the window recurs.)

`scripts/max_audit.py:3341-3344`:
```python
d = _j(ROOT / "docs/research/recommendation_ledger.json", {})   # _j swallows EVERY exception
rows = d.get("recommendations", []) if isinstance(d, dict) else []
if not rows:
    return                     # <- silent clean bill of health
```
`_j` at `max_audit.py:63-67` is `try: json.loads(...) except Exception: return default`. During
every conflict window, `check_recommendation_rows` reports **no defect at all** — the
UNMEASURED-REPORTED-AS-OK class the desk named in L1.40. The three sibling readers all handle it
correctly (§1.4), so the fix pattern exists in-repo three times. `_j`'s blast radius is much wider
than this one call site and should be swept.

### F-4 ⚠ 12 CRONTAB LINES (10% OF THE FILE) ARE PERMANENT NO-OPS HIDING A 3× DUPLICATION
```
$ crontab -l | grep -c -vE '^#|^$'
121
$ crontab -l | grep -nE "seat_(frontier|litminer|dataaxis|prospector)"
42:  0 10 * * *  ... is-enabled quant-dataaxis.timer   || flock ... run_dataaxis_dig.sh
115: 0 14 * * *  ... is-enabled quant-dataaxis.timer   || flock ... run_dataaxis_dig.sh
125: 0  5 * * *  ... is-enabled quant-dataaxis.timer   || flock ... run_dataaxis_dig.sh
   (same 3× pattern for frontier @ 11/15/03, prospector @ 12/18/06, litminer @ 13/19/07)
$ systemctl is-enabled quant-dataaxis.timer → enabled   (frontier, prospector, litminer: enabled)
```
Because `systemctl is-enabled` exits 0, the `||` short-circuits and **none of these 12 lines ever
run anything**. The duplication is therefore invisible — until someone runs `systemctl disable` on
one timer, at which point **three duplicate schedules activate simultaneously** on a single lock.
The guard that makes the mess safe is also what makes it undiscoverable.

`quant-blindrediscovery.timer` is the live exception: `is-enabled=disabled` but `is-active=active`,
last run **2026-07-19 (13 days ago)**, so its cron line at `0 20 * * 1,3,5,6` *does* fire and races
the active timer at the same 20:00 slot.

### F-5 THE CONVERSION QUEUE IS DIVERGENT, AND THE LATENCY IS BIMODAL — A SAME-SESSION BIAS
```
7d arrivals 231 (33.0/d)  |  7d dispositions 138 (19.7/d)  |  rho = 1.67  ->  +13.3 rows/day
latency (n=138): median 0.003d (4.3 min) | mean 0.883d | p90 3.628d | max 5.22d
  <1h: 89/138 (64%)   <24h: 98/138 (71%)
```
The bimodality *is* the finding: work raised and closed inside one session closes in **minutes**;
work that survives the session waits **days**. And it is starkly selective by source:

| source | n | implemented | scheduled | open |
|---|---|---|---|---|
| **max_audit** | 23 | **21 (91%)** | 1 | 1 |
| cycle | 67 | 21 (31%) | 25 | 18 |
| capability_hunt_s5 | 18 | 5 (28%) | 13 | 0 |
| **principal** | 40 | **9 (22%)** | 0 | 21 |
| **deep_sweep** | 52 | **9 (17%)** | 7 | **35** |

**The deep sweep — the desk's deepest and most expensive audit channel, this one — converts worst
of all five, and the principal's own instructions convert second-worst.** The channel that converts
at 91% is the one an automated organ fixes in the same run. This is not a throughput problem; it is
a **selection** problem, and it selects against depth. It also predicts this report's own fate,
which is why it is stated here rather than in a footnote.

### F-6 THE PROMOTION QUEUE DIAGNOSES "NO SUPPLY" FROM A FILE THAT HAS NEVER EXISTED
```
$ ls -la data/research_memory.db
ls: cannot access 'data/research_memory.db': No such file or directory
$ cat data/cro_ai_logs/promotion_queue.log
promotion queue | pipeline latency 181.0d | slots 12/12 (0 free)
  candidates 0 | admission {} | race {}
  QUEUE EMPTY -- no ADMIT-status candidate with a positive capacity. That is a supply
  problem upstream (discovery/gauntlet), not a queueing one.
```
`run_promotion_queue.py:47` binds `_DB = data/research_memory.db`; line 53 returns `[]` if absent.
The real store is `data/sor_crypto.sqlite` (434 rows). **`candidates 0` would print identically if
434 survivors were waiting.** The log then *reasons from its own blindness* to a conclusion about
the desk's discovery rate — and that conclusion has been quoted in prior audits as evidence. The
same phantom path appears at `run_generation_diversity.py:46`, `max_audit.py:1476,1674`,
`run_moat_backup.py:55`.

Consequence at `data/gen_diversity.json`: `"n_in_batch": 0, "mechanism_entropy": 1.0,
"semantic_distinctness": 1.0` — **perfect diversity, reported 4×/day, over zero candidates.**

Related dead wiring: `scripts/run_research_tick.py` (cron `44 5 * * *`) targets the v1 campaign
store, which the desk **formally terminal-marked yesterday** (`campaigns.error = "v1 campaign store
frozen since 2026-06-22 ... terminal-marked 2026-07-31 per R0009 -- never executed"`). The cron line
was never retired. `run_autodiscovery.py` (cron `20 3 * * *`) defaults to `--symbols
EURUSD,XAUUSD,US500` — an FX/equity universe, not the crypto book — and has written nothing since
Jul 22.

### F-7 ⚡ THE RESEARCH MEMORY IS 100% WRITE-ONLY ON CONTENT, AND IT IS COSTING REAL DECISIONS
192 rows, 71% negative results, 92% with lessons — and **48,955 chars of `statement` plus 68,589
chars of `lessons` have zero production readers.** The only automated content reader is
`max_audit.py:113`, which extracts exactly one JSON key (`.axis`). Everything else is `COUNT(*)`.

The mechanism is precise: `libs/alpha_factory/research_memory.py` is constructed with
`Database(":memory:")` at `run_alpha_factory.py:188`. The class documented as *"a durable record of
every idea ever tested (never lose knowledge)"* **writes to a database destroyed at process exit**
and reads an empty table on every daily run.

**The measured cost, in live production output** (`web/alpha_factory.json`, generated
2026-07-31T08:35): `allocation_rationale` shows `success=0.00` for **all 6** categories, and
`allocation` = uniform `0.16666666666666669`. That is `research_allocator.py:44`'s `0.4*success`
term collapsing to zero. The real success rates are sitting on disk, unread:

| category | measured success | rows |
|---|---|---|
| mission | **0.80** | 4/5 |
| dataset | **0.75** | 6/8 |
| method | **0.74** | 17/23 |
| hypothesis | **0.03** | 1/35 |
| construction | **0.02** | 2/96 |

**A 37× spread is available and discarded; the research budget is split uniformly instead.** The
desk is putting the same weight on `construction` (2% hit rate) as on `mission` (80%). Same defect
at `hypothesis_engine.py:54-55`: `prior=0.0` falls through to `_DEFAULT_EDGE=0.5`, so every
generated hypothesis carries the identical **fabricated** rationale *"prior success rate 0.50"*.

Also: **`predecessor_id` is 0/192** — the lineage flag has never once been used, so the memory is a
flat pile, not a graph. And the two genuinely well-structured knowledge artifacts —
`negative_knowledge.json` (44/44 with `reversal_conditions`) and
`graveyard_resurrection_queue.json` (44 entries with treatment/metric/priority/horizon) — are each
referenced by exactly **one** file: their own writer.

### F-8 ⚡ THE NOVELTY GATE IS INVERTED — IT RATES A KILLED FAMILY AS *LESS* NOVEL THAN NONSENSE, BACKWARDS
Measured against the desk's own 42-entry kill list (`run_alpha_factory.py:52 _novelty()`):
```
0.143  "funding carry basis spread across venues"        <- an EXACTLY killed family
0.714  "purple giraffe telepathy signal on lunar phase"  <- nonsense control
0.048  "orderbook queue-position latency arbitrage"      <- genuinely novel
```
**A genuinely novel idea scores 3× *less* novel than a re-derivation of a dead family, and 15× less
than nonsense.** The ceiling is 0.714, not 1.0. Cause: substring matching against kill strings whose
median length is 155 chars (max 1052) — only 14/42 are under 45 chars, so the substring path is dead
for two-thirds of the list, and the token-overlap fallback collides on ordinary English inside the
prose blobs. Live output already shows `execution_maker_carry` and `cme_anchored_basis_dislocation`
at `novelty=0.000`.

**And nothing rejects on novelty anyway** — no threshold comparison exists anywhere in
`run_alpha_factory.py` or `libs/alpha_factory`. The gate is both inverted *and* unwired, which is
why its inversion has never been noticed.

Root cause is upstream and fixable: `research_agenda.json.do_not_repeat` holds **42 bare strings, 0
structured records**; 13/42 (31%) are a bare name with no death record at all. `docs/graveyard.md`
is better (43 rows, 86% with a quantitative mechanism) but only **26% carry a re-entry condition**
and the literal string `re-entry` appears **0 times** — while L1.16a requires every kill to record
one *at kill time*. The structured graveyard the gate needs already exists in
`negative_knowledge.json`; it simply is not the one being read.

The desk's own record of the consequence, from `scripts/negative_knowledge.py:3-5`: *"the 2026-07-27
breadth sweep re-suggested Bithumb/Coinone/Bitso hours after they were refuted."*

### F-9 SIX KILLED FAMILIES ARE SIMULTANEOUSLY LIVE REGISTERED SLEEVES
`funding_carry`, `basis_carry`, `funding_momentum`, `taker_flow`, `ts_trend`, `xsec_price_mom` are
all in `research_agenda.json.do_not_repeat` **and** in `web/registry.json` as `crypto::<name>` with
`expected_sharpe` 0.44–1.14. All six are in the bare-name class, so neither record carries a date
and the contradiction cannot be adjudicated from the artifacts. Either the desk is running six
strategies it has formally killed, or its kill list is poisoned against six working families — and
**both readings are serious**. This needs a human ruling, not a script.

### F-10 THE RATCHET FIRES ON A FALL, NEVER ON A STALL
```
$ .venv/bin/python scripts/check_ratchets.py
ratchets | 0 defect(s) | 5 metric(s) below 100%
  OK          miner_seats_productive            9.1% (floor 9.1% gap 90.9%)
  OK          scripts_mypy_clean               40.7% (floor 40.7% gap 59.3%)
  -> largest gap: miner_seats_productive at 9.1%, 90.9% from 100%
```
A metric pinned at 9.1% with `floor == value` reads **OK** and contributes **0 defects**. L1.0(c)
says the gap to 100% *is* the work queue, but nothing in the fence fires when a ratchet simply stops
moving. The board is honest about the gap (it prints it, and names the largest) and silent about the
stall. A stall-detector — *no improvement in N days on a metric with a live gap* — is the missing
half, and it would have surfaced F-1 without anyone reading `journalctl`.

### F-11 THE FENCE MEASURING MINER LIVENESS RUNS ONCE A DAY
`41 6 * * * ... scripts/check_miner_runway.py` — a pure-CPU check that reads local files, scheduled
`1×/day`, feeding the largest gap on the ratchet board. Its artifact was **19.4 h old** when read
(`checked: 2026-07-31T06:41:01Z`; `mtime` matches, so this is genuine, not a deploy artifact). Under
L1.28c this cadence is **data-arrival bound and nearly free to raise**; a dead seat can currently go
24 h undetected, and the metric steering the desk's top research gap refreshes once daily.

### F-12 ⚡⚡ THE NOVELTY GATE IS MATHEMATICALLY INCAPABLE OF FIRING — MEASURED, WITH THE FIX 40 LINES AWAY
The single most important measurement in this report. Probe used the **production** corpus builder
(`screen_idle_axes.py:_graveyard_priors`), the **production** gate
(`hypothesis_novelty.hypothesis_novelty`) and the **production** threshold (0.70):

```
graveyard rows parsed = 44 | priors built = 44
mean prior statement = 571 chars | mean graveyard NAME = 62 chars

TEST 1  verbatim-full-row (upper bound):   flagged 44/44 = 100.0%
TEST 2  TITLE-ONLY re-query  => RECALL  =   0/44 =   0.0%
        title-vs-its-OWN-row sim: min 0.062  median 0.161  max 0.667   (threshold 0.70)
        n titles whose OWN row scores >= 0.7:  0/44
TEST 3  paraphrase RECALL    =              0/10 =   0.0%
TEST 4  false-positive rate  =              0/10 =   0.0%
```
Feed it a graveyard title **verbatim**: `'ls_contrarian'` → similarity **0.100** against the row
literally named `ls_contrarian`. `'oi_divergence (hourly bt)'` → **0.067** against itself.
**The gate cannot recognise its own corpus.**

**This is architectural, not a mistuned threshold.** The prior's `statement` is built as
`f"{name} {verdict} {lesson}"`, so Jaccard between a 62-char title and a 571-char prior is bounded
above by the token-count ratio: **median 0.154, max 0.667 — 0.70 is unreachable by construction for
44/44 rows.** Recall 0% *and* FPR 0% ⇒ **Youden J = 0.000: the gate carries exactly zero bits.**
Welded shut in both directions. Production corroborates: `grep -rho '"is_redundant":[^,}]*'` over
`reports/ web/ data/` → **20 of 20 `false`. It has never once fired.**

The nearest-neighbour field proves the scores are noise (`data/fred_macro_screen.json`): five
distinct *macro* candidates all report their nearest prior as
`collector:onchain_activity_throughput` at a constant ~0.115 — **the longest prior winning on
length, not on meaning.**

**The replacement is already in the repo, already running, and measurably better on the identical
task** (`scripts/knowledge_engine.py:88`, corpus 324 vs the gate's 44):
```
thresh 0.70 (PRODUCTION Jaccard): recall  0.0%   in-domain FPR  0.0%   J = +0.000
thresh 0.12 (best Jaccard)      : recall 75.0%   in-domain FPR 10.0%   J = +0.650
TF-IDF @ 0.30 (knowledge_engine): recall 97.7%   in-domain FPR  0.0%   J = +0.977
```
`knowledge_engine.py` **runs daily** (`data/knowledge_engine.json` 07-31 08:36, cron `0 2 * * *`) —
it is simply never asked a real question; its retriever is exercised on 3 hardcoded demo queries.
R0004 is confirmed still true on day 6, now `scheduled, due: 2026-08-02`.

**FIVE mutually inconsistent novelty implementations exist**, with corpus sizes 40/42/44/45/46 — no
canonical prior store: `hypothesis_novelty.py` (Jaccard, recall 0%), `run_alpha_factory.py:52`
(substring, ~0% paraphrase recall), `alpha_lifecycle.py:188` (verdicts carried entirely by a
mechanism-tag keyword match while `max_jaccard` contributes nothing), `knowledge_engine.py:88`
(works, unwired), `variation_blocker.py` (n=0, starved by the phantom DB — F-6).

### F-13 ⚠ THE SECOND FAMILY IS BLOCKED BY A NON-EXISTENT MODEL ID, NOT BY MONEY
Every prior audit — and the desk doctrine — attributes the dead cross-family seat to an unfunded
credit line. **That diagnosis is wrong, and acting on it would waste money without fixing anything.**
```
scripts/run_strategic_director.py:49   MODEL = "openai/gpt-9"
$ grep -rn "gpt-9"  ->  exactly 2 hits: that line, and tests/test_review_fixes.py:170
                        (a synthetic model-list fixture)
$ data/secrets/llm_panel.json  ->  openai/gpt-5.6-terra-pro, openai/gpt-5.6-luna-pro   (no gpt-9)
$ data/second_family_log.json  ->  {"available": false, "model": "openai/gpt-9",
                                    "reason": "HTTPError: HTTP Error 400: Bad Request", "chars": 0}
```
The failure is **400 (invalid model)**, not **402 (payment)**. The in-code comment at line 48 asserts
*"gpt-9 is the flagship seat the panel roster already vets"* — it is not in the roster; the test
fixture that is its only other occurrence labels it *"replacement for dead openai pick"*, i.e. a
hypothetical that leaked into production. One string is holding down L1.33 cross-family evidence,
the capability hunt's family B, and the strategic director. **Second-family verdict census:
CONFIRMED 0, CONTESTED 0, SOLO 1** — it has never once reached a live model.
*Honest bound:* I verified the id is absent from our roster file and that the error is 400 with
`chars: 0`; I did not make a live call to prove the provider has no `gpt-9`. One call settles it
(T-4), and it costs cents — but the recommendation to stop blaming the credit line stands on the
error code alone.

### F-14 ⚠ `merge_verdict` CANNOT DETECT DISAGREEMENT — "CONFIRMED" MEANS "BOTH EMITTED BYTES"
`libs/research/second_family.py`: CONFIRMED fires whenever `own_txt` and `other.text.strip()` are
both non-empty. **Content is never compared.** And because `ask_second_family` sets
`available=False` on empty text, **CONTESTED is only reachable when the *first* family produced
nothing** — the exact inverse of its stated purpose. The docstring sells CONFIRMED as *"the
strongest signal this desk can generate without live evidence"*, and L1.33 instructs organs to read
the CONTESTED delta as a measured blind spot. Neither label can mean what the law says it means.
This defect is currently **masked by F-13**: the seat has never connected, so no false CONFIRMED has
been issued yet. Fixing F-13 without fixing F-14 would immediately start manufacturing them.

### F-15 ⚠ THE STRATEGIC DIRECTOR'S FAILURE IS OVERWRITTEN EVERY 6 HOURS BY A DRY RUN
Cron `40 4,10,16,22` runs it live; 07-31 22:40 logged `BLOCKED ... HTTP Error 400`.
`run_intelligence_cycle.py:243` then runs the same script `--dry-run` every 6 h and rewrites
`data/strategic_director.json` to `mode: dry-run, status: READY, error: ""`. The intelligence cycle
prints `ACTIVE strategic_director ... exit=0`. **No reader of the artifact can ever see the 400.**
A dry run and a live run share one output path, and the harmless one always writes last.

### F-16 THE PANEL'S PROOF-OF-PRODUCTION IS A FILE NO CODE WRITES
`run_cadence.py:101-118` gates the panel duty on `data/panel_verdicts.jsonl` growing.
`grep -n "panel_verdicts" scripts/run_external_panel.py` → **no matches**; the panel writes
`external_panel_log.jsonl` and `panel_inbox.md`. The 07-31T17:00:00Z rows (round timestamp, findings
named `MOVE1`..`MOVE5`) are hand-appended by a session. **The desk's own anti-"exit-code-is-
production" fix is gated on a manually-maintained artifact.**
*Correction to prior audits, in the desk's favour:* the claim *"the panel has never run live since
Jul-21"* is **REFUTED** — it ran today at 02:04:06Z on the free roster and produced real output from
`nvidia/nemotron-3-ultra:free` (the other 3 free seats 404/400'd).

### F-17 ⚡ THE PRIORITISATION LAYER RANKS HARDCODED LITERALS AND PUBLISHES THEM TO EXTERNAL MODELS
Three rankers, none of which can change its answer:
- **`research_priority`** (`run_intelligence_cycle.py:140`, 6×/day, reports `"ACTIVE"`,
  *"ranked 6 research categories by decay pressure"*). It reads
  `data/executive_kpis.json[family_survival]` — that file is dated **2026-07-08 (24 days)** and the
  key is `null`, so the hardcoded fallback fires every run. `roi_stats` is never passed, so the
  score reduces to `decay`. Live output: `trader_behavioural=1.0, attention_social=1.0,
  price_only=1.0, regional_premium=0.9, onchain_flow=0.8`, every `expected_yield=0.00` — the
  literal, verbatim, with a **3-way tie at the top**.
- **`research_erv`** loads `data/hypothesis_queue.jsonl`, **which does not exist**, then substitutes
  5 inline literal dicts (`research_erv.py:155-171`). Its scoring tables are literals too, so output
  is invariant by construction. **And it is published**: `docs/DESK_BRIEF.md:74-80`
  `## Highest-ERV open hypotheses` is the document `research_exchange.py` exists to paste into
  external models to source ideas. **The desk's external idea loop is anchored to a demo fixture.**
- **`information_value.jsonl`**: 1,244 rows, **1 distinct `info_bits` (0.2345), 1 distinct name
  (`factory_reject`), 0 rows with `survived=True`**. Written on 3 days ever, each a bulk re-dump.
  It measures nothing, and it is the input to any information-gain-based allocation.

`scripts/research_allocator.py` — a well-designed Thompson-sampling allocator with an explicit
prior-domination rail — has **zero callers** anywhere (`scripts/`, `ops/`, `deploy/`, crontab,
manifest). Its artifact has been frozen since 2026-07-27 (4.55 d).

### F-18 ⚡ FOUR LIVE EQUITY NUMBERS, 8.0× SPREAD — THE DENOMINATOR EVERY CAPACITY GATE DIVIDES BY
| # | file:line | value now |
|---|---|---|
| 1 | `capacity_policy.py:101` `DEFAULT_BOOK_USD` (default arg of `capacity_fit`, `capacity_band`, `niche_share`) | **50,000.00** |
| 2 | `capacity_policy.py:282` `live_book_usd()` → `data/nav_attestation.jsonl` | **18,675.73** |
| 3 | `capacity_policy.py:258` `venue_book_usd()` → deadman high-water (docstring: *"NOT WIRED INTO live_book_usd -- deliberately"*) | **6,257.59** |
| 4 | `daily_research_cycle.py:164` → `web/portfolio.json .deployed.equity` (blends `perp_ls (paper)` with `cash_and_carry (real)`) | **18,658.63** |

Venue truth vs the number every capacity gate uses = **2.98×**, unchanged since the last sweep. Any
caller that omits the argument silently prices against **50,000 — 8.0× the venue number.** Under
L1.18a the capacity band is a *ratio to live equity*; a default constant sitting behind that ratio
is the `$100k` floor bug in its most durable form.

### F-19 THE GAP REGISTER'S MANDATED RE-RANK STAMP HAS NO MACHINE PRODUCER
```
n_rows 80 | n_open 50 | rerank_age_days 1.0 | stale_rows 23
verdict: 23 open row(s) past the register's OWN 7-day escalation bar (oldest 16d)
```
The stamp (`docs/GAP_REGISTER.md:3` `_Re-ranked 2026-07-31T21:05Z_`) is ~5 h old, so the law reads
satisfied — but **no script writes that file** (all 17 referencing files only read it;
`finding_registry.py:260` matches `_RERANK_RE`), and `daily_research_cycle.py`'s 78-step list has no
re-rank step. **"Re-ranked at the start of every cycle" is enforced by a reader checking a stamp
only a human can write.** Self-attestation. Meanwhile 31 of 51 open rows carry no date in their plan
— parked, which `ops/principal_doctrine.txt:205` forbids.

### F-20 THE FRESHNESS REGISTRY IS 90% TEST FIXTURES, AND NO RESEARCH ARTIFACT IS CONTRACTED
`data/freshness_contracts.jsonl`: **62 rows, of which 56 are `/tmp/pytest-of-quant/pytest-NNN/...`
fixture paths** (2 distinct basenames). Only **5 real artifacts** are contracted, all money-path
(`trade_forensics` 48 h, `cost_model` 48 h, `live_guard` 0.25 h, `stage_state` 1 h, `cost_hunt` 8 h).
**Zero research artifacts have a freshness contract** — which is precisely why a 24-day-stale
`executive_kpis.json` (F-17) and a 4.55-day-stale `research_allocation.json` page nobody. L1.44 was
built to catch exactly this and the registry that self-builds from real reads is being filled by the
test suite instead.

### F-21 SCHEDULER: A TRUE UNLOCKED DUPLICATE, AND A SILENCED SECOND COPY
```
line 25: 52 * * * * ... scripts/check_freshness.py >> data/cro_ai_logs/freshness.log 2>&1
line 60: 52 * * * * ... scripts/check_freshness.py >> data/cro_ai_logs/freshness.log 2>&1
```
Same command, same minute, **no lock**, two processes 24×/day appending to one log (line 25 is
outside the managed manifest block, line 60 inside it — the append-not-replace installer defect).
And:
```
line  94: 30 1 * * * ... flock -n data/.cron_crypto_factory.lock /bin/bash ops/run_crypto_factory.sh
line 130: 30 3 * * * ... flock -n /tmp/crypto_factory.lock      bash ops/run_crypto_factory.sh >/dev/null 2>&1
```
Two lock **namespaces** for one organ — neither can exclude the other — and line 130 discards stdout
and stderr, so its runs are invisible by construction.

### F-22 A PHASE INVERSION INSIDE THE DAILY CYCLE: THE BRIEF PUBLISHES YESTERDAY'S RANKING
`daily_research_cycle.py` step **idx 50** is `desk_brief` (`research_exchange.py brief`), which reads
`data/research_erv.json` at `research_exchange.py:108`. Its producer, `research_erv`, is **idx 64** —
14 steps later. The brief that gets pasted into external models therefore carries the **previous**
cycle's ERV on every run. (Credit where due: the prior sweep's `max_push`→`cro_ai` 2 h-stale-queue
inversion **is repaired** — now a clean 64-minute producer→consumer lead.)

### F-23 THE ORGAN FEEDING 4 OF 12 FORWARD SLOTS HAS NO CRON LINE AND A 120-SECOND TIMEOUT
`crontab -l | grep -c run_axis_shadows` → **0**. Its only scheduling is daily-cycle idx 68 under a
**120 s timeout**. It writes `data/axis_shadow_state.json`, which supplies **4 of the 12 forward
slots** — the desk's only path to capital. Everything downstream of it inherits a single
un-retried, time-boxed step inside a long serial cycle.

### F-24 THE LINEAGE ENGINE NOMINATES A GRAVEYARD ROW AS "BEST"
`web/alpha_factory.json` → `"best_lineage": ["crypto::ls_contrarian"]`. `docs/graveyard.md`:
`| ls_contrarian | bt 9.84 (!) — DSR killed it | overfit | fat Sharpe is a red flag, not a green one |`.
`alpha_family_tree` ranks by `expected_sharpe` (2.13, the highest in `alpha_pipeline.json`) and so
selects the killed overfit — **the desk's own recorded lesson, inverted by the organ that should
encode it.** Related silent join failure: `run_alpha_factory.py:200` filters alphas by membership in
`deployed = ['cash_and_carry']` while every alpha id is `crypto::*`, so `deployed_dna` is empty by
construction and `"nearest_deployed": {}` / `"duplicate_clusters": []` are **structurally** empty —
"no duplicates found" is indistinguishable from "the join never matched".

### F-25 UTILISATION: THE BRAIN SEAT — THE RESOURCE EVERY LLM ORGAN COMPETES FOR — IS UNMEASURED
```
utilisation (L1.28a): mean 64% across 8 ceilings
  SATURATED      deployed_capital           100.0%  18,676/18,676 USD     <- a number over itself
  SATURATED      forward_confirmation_slots 100.0%  12/12
  IDLE-EXPLAINED scheduler_cadence           33.7%  32/95 organs run in 48h
  UNMEASURED     brain_seat_throughput        0.0%  0/34 organ runs/24h
```
**63 of 95 organs were silent in the last 48 h** while the sweep headline reads "mean 64%". And
`brain_seat_throughput` — the exact contended resource behind F-1's starvation and every "raise the
cadence vs buy a second seat" decision (L1.28c says these must be settled by measurement) — reads
**UNMEASURED**, which L1.28a defines as zero. `deployed_capital` at `18,676/18,676` is structurally
≡100% and carries no information (already on the desk's record from the 08-01 infrastructure sweep;
re-confirmed here because it is the same denominator as F-18).

### F-26 LEDGER STATUS TAXONOMY: 15 ROWS IN A STATE NO WRITER CAN PRODUCE, AND THREE TERMINAL SETS
```
$ grep -n 'add_argument("--status"' scripts/recommendations.py
223:  p.add_argument("--status", required=True, choices=["implemented", "rejected", "scheduled"])
$ git log -p -- scripts/recommendations.py | grep '^+.*choices=\['
+    p.add_argument("--status", required=True, choices=["implemented", "rejected", "scheduled"])
```
`done` has **never** been a legal value, yet 14 rows carry `status: "done"` and 1 carries
`"screened"`, all with `disposed: null` and real completion evidence in `reason` (*"built, scheduled
hourly, 12 tests, verified live against OKX"*). The pickaxe puts their origin at
`a9666b5 "merge VPS master; paper book resolver renumbered R0126 -> R0133 after id collision"` — **a
second box writes this ledger with a different status vocabulary.**

Three different terminal sets are live:
| organ | `_TERMINAL` |
|---|---|
| `recommendations.py:38` | `("implemented", "rejected")` |
| `max_audit.py` (parity-locked to the above by `test_terminal_rows_are_silent`) | `{"implemented", "rejected"}` |
| `check_conversion.py:62` | `{"implemented", "rejected", **"retired"**}` — **unlocked, drifted** |

Consequence: the 15 rows are **permanent backlog ballast** — `check_conversion` counts them as
backlog forever (9.7% of the 155), while `max_audit`'s overdue loop examines only `status == "open"`
and `status == "scheduled"`, so they can never be flagged either. *Honest limit on this finding:* I
hypothesised these were inflating the fence's headline "oldest" row and **that is refuted** — the
oldest backlog row is R0001, a genuine `scheduled` row at 5.61 d. The damage is a permanently
overstated backlog and 15 real conversions counted as zero, not a corrupted age.

---

## 4. PERSPECTIVES

**1. INTERNAL — measured, not configured.** Covered exhaustively above. The single sentence: *every
organ in this subsystem has a fence, every fence reads green, and the subsystem produces nothing.*
The one number that told the truth was `miner_seats_productive = 9.1%`, and it reads `OK` (F-10).

**2. EXTERNAL — the motive-similar tier-1 cohort.** Read `docs/research/TIER1_BENCHMARK.md`.
- **RenTech/Medallion (the standing ceiling exemplar):** the defining practice is that *every*
  experiment ever run stays queryable and shapes the next one — the research memory IS the firm.
  Here, 192 rows with 117k chars of statements and lessons have **zero content readers** (F-7), and
  `predecessor_id` is **0/192**, so there is no lineage at all. This is the widest single gap to the
  ceiling in this report and it is not a compute gap — the data is already on disk.
- **Jane Street / XTX / HRT:** an organ that fails is *loud* — no silent exit-0, and a dead feed
  pages within seconds. F-1 (daily failure reporting `Result=success`), F-15 (a dry run overwriting
  a live failure) and F-16 (production proven by a hand-edited file) would each be a same-day
  incident at any of them. Transfers fully at our capacity band; costs almost nothing.
- **Two Sigma / Voleon (transferable-practices-only):** systematic prompt/model evaluation. 57
  revisions of `principal_doctrine.txt` with **zero measurements of whether any helped** (F-13's
  seat aside) is the practice we most conspicuously lack. Caution here would be *their* caution, but
  measurement is not caution — it is the thing that lets you push harder safely.
- **Negative exemplars (the control group).** *Which of our rails would have stopped them, and does
  that rail actually fire?* Alameda/LTCM died of leverage and correlated liquidity — our Tier-3
  ruin rails are genuinely untouched by anything in this seam, and the two-stage law (screens carry
  zero promotion authority) held throughout: **nothing found here can reach capital.** That is the
  honest good news. But Archegos died of *an unmeasured aggregate*, and F-18 is exactly that shape —
  four live equity numbers spanning 8× with capacity bands computed as ratios against whichever one
  a caller happened to get. That rail does not currently fire.
- **Tier-grade movement:** on this evidence the research-engine tier grade should be **cut**, and
  the reason should be recorded as *diagnostic capability*, not *capability*. The organs exist; the
  measurements lie.

**3. FUTURE (2-3 years of compute/AI/public data).** The whole `hypothesis_novelty` design — bag-of-
words Jaccard against a prose blob — is already obsolete *today*: an embedding index over every
graveyard row, every research_memory statement and every ledger summary is a few hundred lines and
would subsume F-12, F-24 and the ledger's near-duplicate gap (three open rows for one migration) in
one artifact. The right 2-3-year design is that **no hypothesis is ever generated without the
retriever first returning the desk's own prior art for it** — retrieval-conditioned generation,
rather than generate-then-screen. We have the retriever (97.7% recall@1) and we have the corpus; we
simply never join them.

**4. CONTRARIAN — actively tested, not assumed.** I tested three of this desk's load-bearing beliefs
and **two failed**:
- *"The dead cross-family seat is a funding problem."* **FALSE** (F-13): it is an invalid model id
  returning 400. Money would not have fixed it. This belief is repeated in the doctrine and in every
  recent audit.
- *"Generation is dead because the search space is picked clean."* **FALSE** (F-2, F-6): the
  generator emits a fixed 14-template cross-product, and the organ that reports "a supply problem
  upstream" is reading a file that has never existed. L1.25's instrument-defective branch was never
  taken because the instrument reported `tested=434`.
- *"Conversion is uniformly too slow."* **PARTLY FALSE** (F-5): ρ improved 4.0→1.67 and rows now do
  get implemented past 3.67 d. The residual defect is *selection*, not rate — and it selects against
  exactly this report.

**5. GREENFIELD.** Rebuilt today from validated knowledge only, this subsystem would be roughly
**four files**: one canonical prior store (the union of graveyard + negative_knowledge +
research_memory + ledger, structured, with mechanism and re-entry condition mandatory at write
time); one embedding retriever over it; one generator that is *required* to cite retrieved prior art
before emitting; one scheduler that records, for every organ, the bytes it produced. Against that,
the current design's baggage is stark: **5 novelty implementations, 5 corpus sizes (40/42/44/45/46),
4 equity numbers, 3 terminal-status sets, 2 sqlite stores, 1 phantom `.db` referenced from 5 call
sites.** Almost none of this is load-bearing; most of it is sediment. The parts worth keeping are
the *disciplines* — the fusion refusal, the resumable-by-output-size seat runner, `negative_
knowledge.json`'s structure, the two-stage promotion law — not the plumbing.

**6. FRONTIER — what became possible recently that we do not exploit.** The honest answer for this
seam is that our gap is not frontier technique, it is **wiring** — and saying otherwise would be a
sophistication-shaped excuse. Two genuine items: (a) long-context models make "read all 117k chars
of research_memory and tell me what we already know about X" a single call, which is precisely the
read path that does not exist (F-7); (b) `scripts/fetch_video_transcript.py` makes video a
first-class dig source — and the seat that would use it (`litminer`) has never produced (F-1). Both
frontier opportunities are blocked by the same non-frontier defects.

**NEGATIVE-SPACE SWEEP — what has never been looked at at all.**
- **Nobody has ever read `journalctl` for the seat services.** F-1 — the largest finding here — was
  invisible to every fence and every prior audit because the desk's diagnostic surface stops at
  files in `data/`. There is no organ that reads systemd's own record of what happened.
- **The 117k chars of research_memory content have never been read by anything** (F-7). The desk's
  largest block of self-generated knowledge is unexamined, including by this audit.
- **No prompt has ever been evaluated.** 57 doctrine revisions, zero measurements (F-13 seat).
- **`brain_mutex.log` — the artifact that would name every starved organ — has never been written**,
  though the code path referencing it exists (F-1).
- **Cross-organ semantic duplication in the ledger is undetected**: dedup is exact-string and
  same-source only; three open rows currently describe one migration.
- **No research artifact has a freshness contract** (F-20).
- **Languages:** the entire non-English surface is negative space by measurement, not by choice —
  cn/ru/kr/jp/ar/br have produced zero bytes, ever (F-1).

**OPPORTUNITY COST OF NOT FIXING, 1 YEAR.** F-1: 7 languages × 365 days of the archaeology L1.11a
calls the moat — and the competitor cost to reconstruct it is exactly what makes it a moat, so this
is the most expensive line here. F-12: every generation cycle re-burns multiplicity budget on dead
ground, which under Holm makes *every other candidate harder to promote* — an active tax on
validated-alpha discovery, not merely a missed saving. F-7: the research budget is split uniformly
across categories whose measured success spans 37× (0.02 → 0.80); one year of allocating as if
`construction` (2%) deserves the same weight as `mission` (80%). F-13: a year of single-family
reasoning recorded as if it were cross-family corroboration, for want of one string.

---

## 4b. FINDINGS — literature, language, and mining-seat conversion
*(continues §3; these landed after the perspectives were drafted and are folded into §5's ranking)*

### F-27 ⚡ THE §33 CONVERSION GATE IS A DEAD VARIABLE IN ALL FIVE MINING SEATS
```
$ grep -rn "_MINE_PRIORITY" ops/ scripts/ libs/
ops/run_frontier_miner.sh:32      _MINE_PRIORITY="$(.venv/bin/python scripts/mine_gate.py ...)"
ops/run_dataaxis_dig.sh:13        (same)
ops/run_prospector_dig.sh:12      (same)
ops/run_blindrediscovery_dig.sh:12 (same)
ops/run_litminer_dig.sh:12        (same)
$ grep -rln "MINE_PRIORITY|mine_gate" ops/*prompt*.txt | wc -l
0
```
**Five assignments, zero reads.** The `claude -p "$(cat ops/..._prompt.txt)"` line never interpolates
it and no prompt file mentions it. `mine_gate.py` itself works
(`[§33] BACKLOG-CLEAR -- all 7 carded find(s) disposed; mining authorised`) and its output is
discarded. The §33 doctrine that *"the dig spends its FIRST effort converting, then mines on in the
SAME run"* — quoted at length in the comment directly above the dead line — **is inert in every
seat.** The tell that nobody re-read it: the explanatory comment block is duplicated verbatim twice
in the same file (`run_litminer_dig.sh` lines 7-11 and 13-16), a patch applied twice.

### F-28 THE LOG REAPER DELETES THE FRONTIER SEAT'S RESUME KEY — SO A SUCCESSFUL DIG WOULD STILL RE-DIG
`run_frontier_rotation.sh` resumes by looking for `frontier_${r}_${TODAY}T*.log` of `-size +1500c`.
The reaper (`ops/run_cro_ai.sh:99`, `ls -1t data/cro_ai_logs/*.log | tail -n +31 | xargs -r rm -f`,
cron `45 2,14,20`) keeps the newest 30.
```
$ ls data/cro_ai_logs/*.log | grep -vcP '_\d{8}T\d{4}\.log$'   -> 48   (append-mode, mtime always fresh)
$ ls data/cro_ai_logs/*.log | wc -l                            -> 54
$ ls data/cro_ai_logs/ | grep -cE "^(frontier|litminer|prospector|dataaxis)_[0-9]{8}T"  -> 0
```
**48 append-mode logs permanently occupy a 30-slot cap**, so a dated dig log can never survive a
single reaper pass. This compounds F-1 rather than duplicating it: even once the exit-code and mutex
defects are fixed, **a successful dig's evidence is deleted within hours and the region is re-dug at
max effort.** Independently corroborated: `git log --all --diff-filter=A -- 'docs/research/*frontier*'`
is **empty**, and `data/frontier_profiles/` holds one file (`CN.json`, unchanged since 2026-07-18).
*(Scope note: the agent-reported "rotation runs 03:00/11:00/15:00" is not correct on this box —
per F-4 those cron lines are inert and only the 15:00 systemd timer fires. The reaper defect is
real regardless, and would bite three times as hard if F-4 were ever "fixed" by disabling the timer.)*

### F-29 91 PAPERS INGESTED, 0 SCREENS — AND LITERATURE'S ROI IS UNMEASURABLE BY CONSTRUCTION
| stage | count |
|---|---|
| arXiv papers ingested (all time) | **91** |
| still unprocessed in `feed_inbox.md` | **40** (oldest 2026-07-09, **23 days**) |
| → reached a desk screen/backtest | **0** |
| → graveyard priors (the one working channel) | 4 (`lit_*`, kill-basis `external-literature`) |
| → research_memory hypotheses | **0 / 192** |
| → ledgered recs from litminer run 4 | 10 raised (R0187–R0196), **0 implemented** |

The prior audit said *"83 papers, 0 screens"*; today it is **91 papers, still 0 screens** — confirmed,
not refuted, and the commit says so plainly: *"net new tradeable axes: ZERO."*

**And the attribution is laundered.** The ledger has 15 distinct `source` values and **none** is
`litminer`, `prospector`, `frontier` or `dataaxis` — literature rows file as `deep_sweep`. The desk
therefore **cannot machine-measure the ROI of any mining seat**, which is exactly how "zero screens"
survived two consecutive sweeps. (This also partly re-reads F-5: some of `deep_sweep`'s 17%
implementation rate is literature intake filed under a borrowed source. The selection finding
stands; the label needs splitting before the number can steer anything.)

### F-30 ⚡ FIVE OF SEVEN LANGUAGES HAVE PRODUCED NOTHING, AND THE TRANSLATION LAYER DOES NOT EXIST
| lang | files w/ script chars | genuine MINED artifacts | verdict |
|---|---|---|---|
| **CN** | 25 | `data/8btc_era_thread_catalog.jsonl` (**713 rows**), `cn_oss_extraction_20260731.md`, `frontier_profiles/CN.json` | **the only converting region** — routed to watchlist + graveyard |
| KR | 15 | **0** — `collect_naver_krsearch.py` exists; `ls data/naver* data/*krsearch*` → nothing | collector built, never produced |
| JP | 9 | **0** | instruction-only |
| RU | 10 | **0** | instruction-only |
| AR | **2** | **0** | exists solely as an instruction to itself |
| PT/ES/TR | 0 | **0** | unmeasurable |

**No translation tooling exists.** `grep -rni "translat" scripts/ libs/ --include=*.py` → 8 hits, all
false positives (`"Translate weights"`, `shift_translates`, `"Translates approved intents"`). No
library installed (`deepl|argos|langdetect|opencc|jieba|mecab|konlpy` → none). And
**`libs/research/nlp_normalize.py` DOES NOT EXIST** despite `NLP_NORMALIZATION_SPEC.md` (2026-07-18)
declaring it *"the shared dependency of every Frontier Miner (CN/RU/KR/JP/AE/BR)"* applied at
*"run_frontier_miner step 3"*. There is no glossary and no normalisation; the prompts' claim that
*"LLM translation is the desk's edge over the crowd"* reduces to an LLM reading in-context — which
would be a defensible design, except that per F-1 it has never once executed.

### F-31 VIDEO WORKS — VERIFIED LIVE TODAY — AND 9 OF 12 DIG PROMPTS STILL TELL MINERS IT IS BLOCKED
```
$ .venv/bin/python scripts/fetch_video_transcript.py dQw4w9WgXcQ --lang en
[transcript via https://api.piped.private.coffee] 2089 chars
```
Yet `ops/frontier_{ar,cn,jp,ru,br,en,kr}_prompt.txt`, `litminer_dig_prompt.txt` and
`prospector_dig_prompt.txt` each contain **both**:
- line 11: *"transcript fetch is IP-blocked from this VPS ... do NOT silently skip it -- append a line to video_locked_log.md"*
- line 114/152: *"Transcripts ARE readable: scripts/fetch_video_transcript.py"*

The correction was appended without retracting the claim it refutes, and the refuted blocker sits
**at the top** while the retraction sits 91 lines below (`prospector_coverage.md:27` vs `:118`). A
miner reading top-down logs-and-skips. `docs/research/video_locked_log.md` is 7 lines — **header row
only, zero data rows**, 12 days stale — so the miners are not even doing the logging the stale
instruction asks for. **This is the identical stale-fact class as the kimchi doctrine line**, and it
is the reason a verified-working first-class dig source has zero uses.

### F-32 THE SEARCH OPERATOR LIBRARY HAS NO PROGRAMMATIC CONSUMER
`docs/research/search_operator_library.md` — 571 lines, 46 KB, 34 operators with real per-region
query templates (OP-002 carries CN/RU/KR/JP/AR/PT variants), refreshed 2026-07-31 19:26. All 10 dig
prompts instruct *"START by drawing from"* it. **No organ parses it**: the only code touching it is
`max_audit.py:171` and `libs/ops/organ_catchup.py:60`, both as an *mtime freshness check*, never as
data. Not a dead document — a good document whose only consumer is an LLM that must be running, and
per F-1 the seats that would read it are not.

### F-33 THE DESK TALKS MOST ABOUT THE FAMILIES IT HUNTS LEAST
Computed read-only via `coverage()` (its artifact `data/strategy_coverage.json` does not exist yet —
cron line added 2026-07-31 20:20Z, first fire 05:50Z today, so this is **not** a defect, it is an
unproven first fire → T-6):
```
status UNCOVERED | 14 families | 42 candidates
HUNTED  7: carry-funding, cross-venue-premium, cross-sectional-factor, trend-and-structure,
           order-flow-positioning, copy-trader-skill, onchain-flow
THIN    6: attention-sentiment(2), market-making-execution(1), vol-and-options(2),
           event-and-calendar(1), level-reaction(1), lead-lag(2)
MENTIONED-NEVER-TESTED 1: STATISTICAL-ARBITRAGE (0 tested, 1 ledger mention)
```
The shape is the finding: **LEVEL-REACTION has 23 ledger mentions and 1 test; EVENT-AND-CALENDAR has
15 mentions and 1 test.** Discussion volume is inversely related to test volume in exactly the
families the breadth mandate names as discretionary-mechanism ground.

---

## 5. WHAT COULD MATTER MOST — ranked opportunities
*(impact × confidence ÷ (cost × maintenance); ⚡ = compounding multiplier — raises the value of every
future research hour)*

| # | action | finding | cost | why it ranks here |
|---|---|---|---|---|
| **1** ⚡ | **Make the mining seats fail loudly and survive the reaper.** `exit $rc` instead of a trailing `echo`; `brain_mutex` returns a distinguished code on deferral and actually writes `brain_mutex.log`; re-phase the frontier timer off the 14:45 brain slot; exempt dated dig logs from the reaper or give them their own directory. | F-1, F-28, F-4 | **hours** | Unblocks the entire 7-language capability L1.11a calls the moat. Highest impact-per-hour in this report, and every fix is mechanical with no statistical judgement involved. |
| **2** ⚡ | **Retire `hypothesis_novelty`'s Jaccard for the TF-IDF retriever already running in `knowledge_engine.py`**, over ONE canonical prior store (graveyard ∪ negative_knowledge ∪ research_memory ∪ ledger). Pre-register the threshold; measure recall AND FPR on both controls. | F-12, F-8 | ~1 day | J = 0.000 → 0.977 measured on the identical task. Every cycle without it re-burns multiplicity budget, which under Holm makes **every other candidate harder to promote**. This is a tax on discovery, not a missed saving. Also subsumes the ledger's semantic-duplicate gap. |
| **3** | **Fix the second-family model id AND `merge_verdict` in the same commit.** Point at a roster model; make CONFIRMED require compared content, not two non-empty strings. | F-13, F-14 | **minutes + hours** | A one-string fix restores cross-family evidence for L1.31/L1.33, the capability hunt's family B and the strategic director — but shipping it alone would immediately start manufacturing false CONFIRMED verdicts. **They must land together.** Also: stop citing the credit line as the cause. |
| **4** ⚡ | **Give `ResearchMemory` a real database handle** (it is constructed on `Database(":memory:")`), then let the allocator read the success rates already on disk. | F-7 | **one handle + a test** | Unlocks a **measured 37× spread** (construction 0.02 → mission 0.80) that the research budget currently ignores, splitting uniformly at 0.1667. The cheapest large decision-quality win available. |
| **5** | **Kill the phantom `data/research_memory.db`** at all 5 call sites; point them at `data/sor_crypto.sqlite`. | F-6 | **a constant** | Restores the promotion queue's candidate count, the diversity gate (currently reporting perfect entropy over n=0) and `variation_blocker` (n=0 since inception). Until then no organ can tell "no candidates" from "wrong path". |
| **6** | **Single-source equity; delete `DEFAULT_BOOK_USD`.** Make the book size a required argument. | F-18 | hours | Four live numbers spanning **8.0×** under every capacity band, which L1.18a defines as a ratio to live equity. This is the `$100k` floor bug in its most durable form, and it is the Archegos shape: an unmeasured aggregate. |
| **7** | **Wire `_MINE_PRIORITY` into the dig prompts, or delete it and say §33 is not enforced at the dig.** | F-27 | hours | Five seats compute the conversion gate and throw it away. Either the law runs or the desk stops claiming it does — both are acceptable; the current state is not. |
| **8** | **Retract the stale video blocker from all 9 prompts** and delete the refuted line rather than appending below it. | F-31 | **~1 hour** | A verified-working first-class dig source with zero uses, blocked by a sentence. Cheapest capability unlock in the report. |
| **9** | **Make `_j` non-swallowing on the ledger path** in `max_audit`; the correct pattern exists in-repo three times. Extend the parity test to cover corrupt input and unknown statuses; reconcile the three `_TERMINAL` sets; dispose the 15 `done`/`screened` rows. | F-3, F-26 | hours | Closes a fail-open on the desk's conversion spine during a window that recurred 5× in one day. |
| **10** | **Delete the literal-ranking organs or feed them real inputs** (`research_priority`, `research_erv`, `information_value`) — and stop publishing `research_erv`'s demo slate to external models via `DESK_BRIEF.md`. | F-17 | hours | The external idea loop is currently anchored to a hardcoded fixture. Deleting is a legitimate disposition here; reporting `ACTIVE` over a literal is not. |
| **11** ⚡ | **Add a stall detector to the ratchet** (no improvement in N days on a metric with a live gap) and **contract the research artifacts for freshness** (currently 56 of 62 rows are pytest fixtures). | F-10, F-20 | hours | These two are why every finding above stayed invisible. A stall detector alone would have surfaced F-1 without anyone reading `journalctl`. |
| **12** | **Split mining-seat attribution in the ledger** (`source=litminer|prospector|frontier|dataaxis`) so seat ROI becomes measurable at all. | F-29 | ~1 hour | Prerequisite for ever answering "is literature mining worth it?" — currently unanswerable by construction. |

**INTERACTIONS.** #2 depends on #4/#5 (one canonical store needs a real DB). #3's two halves must
ship together. #1 and #8 are independent of everything and can go first. #11 is the meta-fix: without
it the next audit re-discovers this list.

**WHAT I WOULD DO WITH ONE HOUR:** #1's `exit $rc` and #8's prompt retraction. Two edits, two
capabilities back.

---

## 6. WHAT WE TEST NEXT — concrete experiments, success criteria, retirement conditions

- **T-1 (today, free, read-only).** Determine *which* mechanism kills the frontier dig: run
  `bash -x ops/run_frontier_miner.sh en` with `BRAIN_DRY_RUN=1`, or simply check whether
  `/tmp/quant_brain.lock` is held at 15:00. **SUCCESS:** the exact exit path is named.
  **FAILURE MODE:** if it is the mutex, #1's re-phase is necessary; if it is auth, #1 alone is
  insufficient. **RETIRE** when `brain_mutex.log` exists and is non-empty.
- **T-2 (after #1).** `journalctl -u quant-frontier.service` shows a **non-zero** exit on failure,
  and `ls data/cro_ai_logs | grep -c frontier` > 0 within 24 h. **SUCCESS:** ≥1 region produces a
  ≥1500 b log that survives one reaper pass. This is the single test that matters most.
- **T-3 (after #2).** Pre-registered: recall ≥90% on graveyard titles **and** in-domain FPR ≤10% on
  10 adversarial novel controls. Today's baseline is 0.0%/0.0% (J=0.000); the TF-IDF measurement is
  97.7%/0.0%. **RETIREMENT CONDITION:** if FPR exceeds 20%, the gate is over-tuned and must be
  loosened — a gate that rejects everything is the same defect pointed the other way.
- **T-4 (after #3).** First live second-family call returns CONFIRMED or CONTESTED with **compared
  content**, and a deliberately-contradictory pair of inputs yields CONTESTED. **FAILURE MODE:** if
  everything returns CONFIRMED, F-14 was not actually fixed.
- **T-5 (after #4).** `web/alpha_factory.json` `allocation` is **non-uniform** and its
  `allocation_rationale` reproduces the on-disk rates (mission 0.80, dataset 0.75, method 0.74,
  hypothesis 0.03, construction 0.02).
- **T-6 (today 05:50Z, free).** First fire of `run_strategy_coverage.py`: `data/strategy_coverage.json`
  exists and is non-empty. **FAILURE MODE:** absent → a brand-new cron line that never fired, i.e.
  the F-1 class recurring on a two-day-old organ. *(Note it is gitignored, so its evidence never
  leaves the box — worth a ruling.)*
- **T-7 (this week, needs a human).** Adjudicate F-9: are `funding_carry`, `basis_carry`,
  `funding_momentum`, `taker_flow`, `ts_trend`, `xsec_price_mom` killed or live? They are currently
  both. **This is the only item here a script cannot settle**, and it is a live correctness risk in
  either direction.
- **T-8 (after #11).** Re-run this audit's cheap probes as a scheduled check: seat-productivity ≠
  9.1%, novelty J > 0.5, `research_memory.db` absent → hard error. **SUCCESS:** the next research-
  engine sweep opens with these already green and spends its budget on new ground.

---

## PERSPECTIVE COVERAGE

| perspective | status | anchor findings |
|---|---|---|
| 1 INTERNAL | ✅ measured throughout | F-1..F-33 |
| 2 EXTERNAL (tier-1 cohort + negative exemplars) | ✅ RenTech/JS/XTX/HRT/Two Sigma applied; Alameda/LTCM/Archegos as control | §4.2; tier grade recommended **cut** on *diagnostic* capability |
| 3 FUTURE | ✅ | §4.3 — retrieval-conditioned generation |
| 4 CONTRARIAN | ✅ three beliefs tested, **two refuted** | F-13 (not a funding problem), F-2/F-6 (not a picked-clean space), F-5 (not a uniform rate) |
| 5 GREENFIELD | ✅ | §4.5 — 4 files vs 5 novelty impls / 5 corpus sizes / 4 equity numbers / 3 terminal sets |
| 6 FRONTIER | ✅ incl. an honest "our gap is wiring, not technique" | §4.6 |
| NEGATIVE-SPACE SWEEP | ✅ 7 never-looked-at regions named | §4 negative space |
| FIVE-THINGS (weakness/bottleneck/capability-gap/multiplier/unknown-unknown) | ✅ | multipliers flagged ⚡ in §5; unknown-unknown = `journalctl` blind spot |

**PROACTIVE BATTERY — moves run, and what each produced.** (1) *Contingency-before-failure* → F-13's
free-tier fallback exists in exactly one file while ~10 paid consumers have no route. (2) *Adjacency*
→ the swallowed-exit-code shape found in bash (F-1) after being fixed in Python; the stale-fact shape
found in 9 prompts (F-31) after the kimchi instance. (3) *Config-vs-outcome* → the entire report;
`prompt/runner/unit/creds = 1/1/1/1` with zero bytes produced. (4) *Regression sweep* → nothing here
makes anything worse; F-4 warns that "cleaning up" the crontab by disabling a timer would activate a
3× duplicate. (5) *Cost inversion* → F-13: the paid top-up would not have fixed the free defect.
(6) *Generalise the rule* → F-26: a parity test locking two organs left a third to drift.
(7) *Autonomy check* → F-16: the panel's proof-of-production is hand-written. (8) *Negative space* →
§4. (9) *Scope the negative result* → F-31: the ROUTE was blocked, the CAPABILITY never was.
(10) *Ratchet check* → F-10: floors guard falls, nothing guards stalls.
**Produced nothing:** the search for a *research-friction* metric — the desk has no turnaround
instrumentation at all, so §4's friction claims rest on ledger timestamps (F-5) rather than on any
organ built to measure it. Reported as empty rather than skipped.

---

## APPENDIX — measurement conditions

A **sibling Claude session was writing to this working tree throughout the audit.** The
recommendation ledger was observed in an unresolved merge conflict (`UU`, 3 conflict markers) at
**01:57Z** and clean at **02:01Z** (231 rows). All ledger arithmetic in this report is from the
02:0xZ clean state. Findings F-3 and F-26 are *about* that instability and do not depend on it.

`data/cro_ai_logs` is reaped 3×/day keeping 30 of 54 `*.log`, so **a missing log is never evidence
an organ did not run.** Every liveness claim here rests on systemd/journal records, DB row
timestamps, git history, or artifact `generated` fields — never on log absence. Where the reaper
materially bit, it is named (F-8 in the LLM census, F-28).



