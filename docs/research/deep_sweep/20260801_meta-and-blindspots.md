# Weekly Deep Cold Audit — META & BLIND SPOTS — 2026-08-01

STATUS: COMPLETE

Subsystem: meta-and-blindspots (the layer above: untested research ASSUMPTIONS, habit-persisting
workflows, misleading metrics, blind-spot transfer from outside fields, institutional curiosity,
research trajectory).

Working dir: /home/quant/quant-platform. READ-ONLY run.
Auditor: Claude (Opus). Cohort benchmark file read: docs/research/TIER1_BENCHMARK.md.

---

## SCORES

*Convention declared, because M8 proves this seat's scores were previously incomparable across seats
and days: here, **finding an unknown class RAISES `unknown_unknown_score`** (discovering that a whole
failure mode existed is evidence more exist). Other seats use the opposite convention. Until a
convention is fixed desk-wide, these numbers must not be averaged or trended across seats.*

| metric | value | basis |
|---|---|---|
| current_capability_pct | **52** (07-31: 58) | **Lowered on evidence, not mood.** Yesterday's 58 assumed "scheduled" was a working disposition (0/6, M1), that the exploration fence measured yield (it measures mtime, M6), that the retraction had landed (1 of ~45 sites, M11), and that the family fences had teeth (substring whitelists, M16). Four load-bearing assumptions of the prior score were falsified today. Real gains since (sentinel adoption 1/8→6/7, ratchet fence sound, repeat-fraction now measurable) are held. |
| practical_ceiling_estimate | 85 | unchanged from 07-31 |
| ceiling_gap | 33 | |
| opportunity_cost_1y | **HIGH, quantified** | ~85 % of eight seats' max-effort output converts to nothing (M17: 15.2 % closure, 25.9–34.9 % repeat, 0 synthesis today, 0/26 due dates); apparatus cost ~3–4.5 serial brain-h/day; **11,728 bps of stated ROI aging undisposed across 131 priced rows**; and one refuted premise is actively routing research compute away from the 420 re-score (M11d/X8). |
| confidence | 0.85 | four audits of this layer; every headline claim carries its command, and the four load-bearing delegated claims were re-verified by hand |
| unknown_unknown_score | **0.60** (07-31: 0.45) | **Deliberately raised.** Today found an entire un-named failure class (mtime-as-proxy-for-work, hit by 3 independent seats), a retraction that propagated to 1 of ~45 sites *discovered by accident*, and a governance estate whose authority is inversely allocated to its information. U9 is the live suspicion: nobody has run the reverse-graveyard query, and there is no reason kimchi is unique. |
| info_gain_if_investigated | **HIGH** — concentrated in X1 (`d`), X3 (adjacency base rate), X7 (reverse-graveyard) | each converts a currently-unbounded unknown into a number |
| expected_alpha_contribution | **direct via X8**, indirect otherwise | X8 (420 re-score under the fixed gate) is a genuine L1.16a resurrection with a named, dated enabling change, currently blocked by a docstring |
| expected_compounding_contribution | **HIGHEST of the eight seats** | X1 retroactively re-prices every audit the desk has ever run and every one it will run; every μ-side repair multiplies every future finding from every organ, permanently |
| ceiling_expansion | the ceiling assumption is **"repair is voluntary and detection is trusted"** | Both are organizational, not technological. `d` (X1) makes detection *measured* rather than trusted; the adjacency field (X3/#6) makes repair *scoped* rather than voluntary. Either moves the ceiling itself, not the gap. |

---

## READ-ONLY DISCLOSURE (stated first, because the run was specified read-only)

One unintended write occurred. A delegated sub-audit called
`check_fence_yield.build_report()`, whose signature is `(root=None, *, record: bool = True)` —
`record` defaults to True, which rewrote `data/fence_yield_history.json` (mtime 02:29:42). The write
is a de-duplicated set-union (`if verdict not in hist`), so no verdict was added that the file did
not already hold or that the organ's own 07:25 cron run would not have added; only the `updated`
timestamp moved. The file is gitignored (`.gitignore:11 data/*`), so no git state changed. No other
write occurred: every other organ was exercised by importing its builder, never `main()`.
**Reported rather than omitted — an audit that hides its own side effects is worth nothing.** Note
the shape: a function named `build_report` that persists state by default is itself a small instance
of the class this report is about.

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1. The ratchet fence is genuinely well-built — I hunted for the weld and did not find one.**
`.venv/bin/python scripts/check_ratchets.py --report-only` → `0 defect(s) | 5 metric(s) below 100%`.
`floor == value` on every row is *correct* (`--ratchet`, cron `7 7 * * *`, records improvements only;
`_ratchet()` cannot lower a floor by construction). It special-cases the three traps that kill this
class: `UNMEASURED` is a defect not a pass (`:180`), `NO-FLOOR` is a defect (`:182`), and
born-at-zero-with-zero-floor is handled (`:189`). Its exclusion of the budget-truncated mutation
target is honestly documented and correct (*"a floor set from a partial run is a fabricated
constraint"*). This is the standard the rest of the estate should be held to. (One gap: M14.)

**S2. `check_exploration` is a true-positive detector, and its DARK verdict is real.**
`.venv/bin/python scripts/check_exploration.py` → `DARK -- 4/6 organs produced within their own
cadence; 2 never produced`. Independently confirmed: `data/kimi_hunt.json` does not exist despite an
8×/day cron, and `kimi_hunter.log` shows `FAILED (HTTPError 402)`. It exits 2 and is consumed by
`run_law_gate:158`. (Its grading criterion is the M6 defect — but the verdict it produced today is
correct and actionable.)

**S3. `recommendations.py report` is the one governance tool that both fires and is honestly wired.**
It produced 9 concrete DEFECT lines this morning with correct datetime comparison, its loud-refusal
path blocks disposition reversal (`:122`), and it has a real automated caller that inspects the
return code (`run_strategic_director.py:131`). Where it and the fence disagree (M2), **it is the one
that is right.**

**S4. The completion contract works, and its adoption is the desk's clearest improving signal.**
`grep -H "^STATUS" docs/research/deep_sweep/*.md`: sentinel adoption went 1/8 (07-29) → 0/8 (07-30)
→ **7/8 (07-31)** → 6/7 present today. Five of seven seats now publish an explicit carry/ratchet
table naming what did and did not move — **that convention is the only reason M17 was measurable at
all.** A process improvement made a measurement possible two days later; that is the compounding the
constitution asks for, and it is worth protecting.

**S5. `check_fence_yield` (L1.43) is honest about its own limits.** It correctly reports
`NEVER-RUN-PRESENT`, names `moat_backup` as NEVER-RUN and `change_window` as QUIET, and explicitly
refuses to propose retirements or fail a build (`:194 return 0  # evidence organ`). Its
rail-vs-detector distinction is load-bearing and correctly implemented. It is the model for how a
governance organ should express uncertainty.

**S6. The desk finds its own gaps at sustained volume.** `data/blind_spot_ledger.jsonl` → 97 rows;
self-origin by day 07-28: 10, 07-29: 6, 07-30: 14, 07-31: 22. The *rate* is real and rising. (What
the derived self-sufficiency **score** claims from it is M7.)

**S7. Two seats demonstrably re-scope to new ground each cycle.** data-intelligence (8.6 % repeat)
and data-moat (16.7 %) are the healthy end of M17's table, against execution-growth's 59.1 %. The
difference is a **process** difference, not a subject-matter one, and it is reproducible — worth
extracting into the sweep prompt rather than admiring.

---

## 2. WHAT WE DON'T KNOW (the ignorance ledger)

**U1. The audit apparatus's recall, `d`.** Nobody knows what fraction of a realistic planted defect
population `max_audit` or a sweep seat finds. Until `d` exists, every "we found N findings" is a
count with no denominator, `unknown_unknown_score` is unestimable (M8), and L1.43's "quiet detector
— clean desk or inert check?" ambiguity is unresolvable. **X1 closes this and it is the highest
compounding item in the report.**

**U2. ~~Detection marginal yield~~ — ANSWERED today (M17): 25.9 % strict / 34.9 % broad repeat
fraction, 15.2 % prior-finding closure.** Carried from 07-31 U2. What remains unknown is the
*trend*: one observation is not a series, and the measurement is currently impossible to automate
because every seat renumbers its findings daily (M20 item 1).

**U3. Whether "implemented" means the class died or only the named instance.** M11/M12 give one
proven case (R0051: ~45 sites survived a row closed as implemented). 71 rows carry that status. The
base rate is unmeasured and is the single most important unknown about the ledger's meaning. **X3.**

**U4. Whether the sweep's daily cadence is right.** M18 shows nobody chose it. Rising repeat-fraction
argues it fires faster than its subject changes; L1.28c argues cadences should hunt upward. Both
readings are currently unfalsifiable — the deciding evidence is `d` (X1) plus a repeat-fraction
series.

**U5. `docs/research/ASSUMPTIONS.md` still does not exist** — carried unmoved from 07-29 U7 and
07-31 U5, now **three consecutive audits**. The desk cannot enumerate its own load-bearing
assumptions. M11 is what that costs.

**U6. Whether the GPT-9 HTTP 400 is a funding wall or a request-shape bug.** One call, ever, and
nobody has retried or read the request. The doctrine's framing pre-supposes funding; the status code
says otherwise. A possibly-one-line fix gates M13's entire capture–recapture estimator. **X2.**

**U7. Doctrine→behaviour compliance rates** (carried from 07-29 U3 and 07-31 U4, unmoved): what
fraction of organ runs actually execute screen-on-discovery, log battery moves, run the novelty
gate. Still unmeasured. M11 raises the stakes — organs are provably being taught from ~45 stale
sites, and nobody knows what they do with them.

**U8. How much of the 07-31 governance spike was value.** 73 % of the desk's highest-volume day
(114 substantive commits) was governance + ledger bookkeeping, including merges titled *"ledger race
(4th today)"*. Whether that bought more than the 9 research commits it displaced is unknown, and
L1.26 says that question must be asked, not assumed.

**U9. Suspected unknown-unknown: how many *other* retracted facts are still live.** M11 was found
by grepping one known-refuted claim. The desk has a graveyard of 47 rows and no propagation
mechanism. Nobody has run the reverse query — "for each graveyard entry, where is the pre-kill
claim still asserted?" — and there is no reason to expect kimchi is the only one. **X7.**

---

## 3. WHAT COULD MATTER MOST (ranked by impact × confidence ÷ (cost × maintenance))

Compounding multipliers flagged ⚙. Interactions noted.

| # | opportunity | why it ranks here | cost | conf |
|---|---|---|---|---|
| **1** | ⚙ **Measure audit recall `d` by planting defects (M13/X1)** | Converts every past and future sweep from a count into an estimate, *retroactively*. Gives `unknown_unknown_score` its first estimator (M8), resolves L1.43's quiet-detector ambiguity, and decides U4. Needs no money, no second family, no new dependency — the desk owns the pattern twice already (`positive_control.py`, `mutation_score.json`) and has never pointed it at the audit layer. | 1 session | 0.85 |
| **2** | **Propagate the kimchi/420 retraction to all ~45 sites (M11)** | The only item here with a *direct* alpha path: `reject_rescore.py:4` is routing research compute away from the 420 re-score on a refuted premise, and the gate has since been fixed and re-certified (`baf342e`) — a NAMED enabling change under L1.16a. Also un-teaches ~45 organ-facing sites and puts the missing kill row in the graveyard. | 1 session | 0.95 |
| **3** | **Fix the two disagreeing conversion meters + the 15 invisible rows (M2/M3)** | The desk's daily work queue currently reads the meter that says `past_due: 0` while nine defects exist. Three one-line fixes (`<` → `<=` on a datetime not a string; count `open` past grace; add `done`/`screened` to `_TERMINAL` or migrate them). Interacts with everything: this meter gates repair-mode for the whole desk. | hours | 0.95 |
| **4** | ⚙ **Give the exploration fence a yield term (M6)** | Today an auth-failed hunt that proposed nothing turns its organ GREEN. One extra condition (`proposals > 0` in the window) makes the L1.32 fence measure what its own docstring says it measures. Cheap, and it is the difference between exploration decay being visible or not. Interacts with #1: `d` is meaningless if organs can green themselves by writing empty files. | hours | 0.9 |
| **5** | **Repair the blind-spot origin gauge (M7)** | The desk's answer to "am I still dependent on the human?" is structurally guaranteed to be "no". Two fixes: log the 24 principal orders that were never logged, and switch `check_self_sufficiency` to the 7-day window helper that already exists 10 lines below it. Without this, L1.0(d)'s "principal noticed first = TOP defect" can never fire. | hours | 0.95 |
| **6** | ⚙ **An `adjacency` field + a fence on it (M12)** | Makes "did we fix the class or the instance?" a recorded fact instead of an assumption. This is the structural fix for the failure that produced M11, and it is the difference between the ledger's 71 `implemented` rows meaning something or not. Depends on X3 to size the problem first. | 1 session | 0.8 |
| **7** | **Re-grade `self_audit_layer` T1 → T2 in TIER1_BENCHMARK.md (M15)** | A T1 grade *de-queues* the row from `run_max_push.py`. The grade cites planted controls that do not exist. Re-grading is a one-line edit that restores this whole layer to the daily queue — the cheapest item in the table and it makes items 1/4/6 self-sustaining. | minutes | 0.9 |
| **8** | **Un-weld the repair-mode trigger (M4)** | `backlog ≤ 25` is unreachable at ρ≈3 with 15 immortal rows, so `repair_mode: true` is a constant and steers nothing. Replace with a *rate* trigger (dispositions < arrivals over a trailing window) that can actually toggle. Do **not** raise the line — that is the denominator trick. | hours | 0.85 |
| **9** | **Give `check_freshness` an honest denominator (M16a)** | `fresh_fraction: 1.0` after dropping 56 of 62 rows — and the dropped ones are the executor's. Stop the test suite writing into the production registry, then report `n_discarded` in the artifact. Zeroes out the highest-leverage row on the max-push board today. | hours | 0.9 |
| **10** | ⚙ **Name and grep the `mtime-as-proxy-for-work` class (M19)** | Three independent seats found this shape today. Naming it makes it enumerable: every `stat()`-based fence in the estate becomes a candidate. Classic compounding multiplier — one taxonomy entry, N future catches. | hours | 0.8 |
| 11 | **Stable per-seat finding IDs (M20 item 1)** | Without them, M17's repeat-fraction can never be automated and U2's trend never exists. Cheap, but explicitly ranked *below* capacity work per M20's ordering argument. | 1 session | 0.8 |
| 12 | **Diagnose the GPT-9 400 (M5/U6)** | Possibly one line; unlocks the capture–recapture estimator (M13) and restores actual model-family diversity (M10). Ranked here only because it may turn out to be a genuine funding wall. | hours | 0.6 |

**Opportunity cost of not fixing, 1 year.** The dominant term is not any single item — it is that
**~85 % of everything eight max-effort audit seats produce converts to nothing** (M17), while the
apparatus consumes ~3–4.5 serial brain-hours/day of a one-brain-mutex desk. At today's arrival rate
that is on the order of 5,000+ findings/year detected and ~750 repaired. The stated-ROI stock
already sitting undisposed in the backlog is **11,728 bps across 131 priced rows**, aging. And the
compounding term: a desk that cannot propagate a retraction (M11) will keep making decisions on
refuted premises, and the only reason we know about one is that someone grepped for it.

---

## 4. WHAT WE TEST NEXT (concrete, with success criteria and retirement conditions)

**X1 — PLANTED-DEFECT RECALL for the audit layer.** *(closes U1; enables #1, decides U4)*
Fork to a scratch worktree. Plant K=12 governance defects drawn from the desk's **own** historical
taxonomy — welded gate; number divided by itself; `except: pass`; writer-with-no-reader; off-by-one
date compare; fence exiting 0 on absent input; stale-consumed artifact; duty with no artifact;
hardcoded constant beside a ratio; status the tooling cannot write; cron line whose organ was
renamed; alert threshold above its failure point. Every one is a class this desk has actually
shipped, so the seeds are realistic by construction. Run `max_audit.py` and one sweep seat blind.
**Success: `d = k/12` exists and is published with its floor in the same commit (L2.0/L1.41).**
**Retirement: re-run quarterly or on any change to the audit prompt genome; `d` is a ratchet.**
**Failure mode to watch: planting only defects we already know how to find inflates `d`** — hold out
4 of the 12 as an unseen set.

**X2 — CROSS-FAMILY CAPTURE–RECAPTURE.** *(closes U6; enables M13's estimator)*
First diagnose the GPT-9 HTTP 400 (read the request, not the balance). If it is request-shape, fix
and run 5 paired hunts. Compute `N̂ = n_A·n_B/m` and the never-found residual.
**Success: a numeric lower bound on the unknown-unknown count replaces the asserted decimal in the
next sweep's score block.** **Report it explicitly as a LOWER bound** — detector dependence,
heterogeneous catchability and an open population all bias `N̂` down. **Retirement: if `m` stays 0
across 5 paired runs, the detectors are not sampling the same population and the estimator is
retired with that finding recorded.**

**X3 — THE ADJACENCY BASE RATE.** *(closes U3; sizes #6)*
Sample 15 of the 71 `implemented` rows at random. For each, grep the repo for the defect's *shape*
(not its filename). Count how many still have live instances elsewhere.
**Success: a published fraction.** **Prediction, logged now under L1.29, resolve-by 2026-08-08: I
forecast ≥ 40 % of sampled rows still have at least one live instance of their class (confidence
0.65).** **Retirement: re-measure after the adjacency field ships; if the rate falls below 10 % the
field has done its job.**

**X4 — DRAIN THE SIX P1 ROWS AND MEASURE WHAT IT COSTS.** *(the capacity experiment M20 says must
come first)*
R0002, R0020, R0025, R0043, R0058, R0062 — the cohort that scored 0/6 today. R0058 (6,500 bps,
active data destruction) first. Record wall-clock per row.
**Success: 6/6 terminal within 48 h, with per-row cost recorded — this is the desk's first real
measurement of repair capacity μ, which every queue argument since 07-31 has been guessing.**
**Retirement: none — this is a measurement, and μ becomes a standing ratchet.**

**X5 — DUE DATES ON THE 25 PARKED SYNTH0731 ROWS.** *(M17 fact 2)*
25 of 26 rows from the desk's own synthesis are `open` with **no due date**, violating the register's
own no-parked-rows rule. **Success: every row carries implement / defer-with-date / retire-with-
reason.** **This is the cheapest test of whether "scheduled" can convert at all when a date is
actually set — the direct follow-up to M1's 0/6.**

**X6 — STABLE FINDING IDs, one seat, one week.** Pick execution-growth (worst repeat fraction,
59.1 %). Persist IDs across dates. **Success: next week's repeat fraction for that seat is computed
by script, not by judgement.** **Ranked below X4/X5 deliberately (M20).**

**X7 — THE REVERSE-GRAVEYARD QUERY.** *(closes U9 — the suspected unknown-unknown)*
For each of the 47 graveyard rows, grep the repo for the pre-kill claim still asserted as true.
M11 found ~45 live sites from **one** refuted claim, discovered by accident.
**Success: a count. If it is zero, that is a genuine and valuable null and the graveyard's
propagation is proven healthy.** **Prediction, logged under L1.29, resolve-by 2026-08-08: ≥ 3 further
graveyard entries have live pre-kill assertions (confidence 0.7).**

**X8 — INSTITUTIONAL CURIOSITY / L1.16a RESURRECTION: re-score the 420 under the fixed gate.**
The named enabling change exists and is dated: the gate was certified WELDED (07-31) and then fixed
and re-certified (`baf342e`, sensitivity floor 10.0 → 5.0, null rejection unchanged). That change
addresses the **exact** mechanism of death — the original rejection was produced by a broken
instrument. The only thing blocking it is a docstring encoding a refuted premise (M11d). This is the
one item in this report with a direct path to deployable alpha, and it is currently blocked by a
prose sentence.
**Success: the 420 re-scored as one pre-registered resurrection batch, with the trial count
honestly declared.** **Retirement: if 0 survive under the fixed gate, that is a real result — and it
is the first time that claim would rest on a working instrument.**

---

## FINDINGS LOG (appended as verified)

### M1 [INTERNAL — the headline; yesterday's P1 prediction RESOLVED]. "scheduled" has a MEASURED conversion rate of 0/6 on its first-ever due date. The disposition is a deferral with no consumer.

Yesterday's meta audit logged U1: *"20 scheduled rows now exist… Zero historical scheduled→implemented
transitions exist to estimate a rate. First evidence arrives 2026-08-01 when 9 rows come due at once
(prediction P1)."* Today is 2026-08-01. The cohort came due. **Nothing happened.**

```
$ git show d707ab9:docs/research/recommendation_ledger.json   # last ledger commit of 07-31
  R0002: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
  R0020: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
  R0025: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
  R0043: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
  R0058: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
  R0062: 07-31 status=scheduled  ->  NOW status=scheduled commit=None
P1 RESULT: 0/6 scheduled-due-today rows reached a terminal disposition = 0%
```

This is the desk's most load-bearing governance assumption falsified on first contact. L2.3 declares
three legal dispositions — implemented / rejected / **scheduled** — and treats scheduling as a real
decision. Measured: it is not. It is the `open` state with a date attached, and the date has no
consumer that acts on it (M2 proves why).

**What is sitting in that cohort matters.** R0058 (`roi_bps=6500`, the single highest-ROI row in the
entire 231-row ledger) reads *"PERMANENT DATA DESTRUCTION IN PROGRESS: Execution Reality Model (L1.11
named moat component) accruing at 0.8%…"*. An **actively-destructing named moat component** was
scheduled, came due, and was not touched. Under L1.28b this is an unbooked loss that has now aged
past its own deadline.

Note the asymmetry that makes this dangerous: scheduling *feels* like a conversion (the fence counts
it — see M3 — and `check_conversion.py` counts scheduled rows in `dispositions_7d` only if terminal,
but the ledger stamps `disposed` on them, so every human-facing read of "we dispositioned 138 rows"
is inflated). Measured terminal conversion for the cohort: **0%**.

*Perspective: INTERNAL. Confidence 0.95 (direct git-diff of the ledger, whole cohort, no sampling).*

---

### M2 [INTERNAL — misleading metric, root cause of M1]. Two organs read the SAME ledger in the same minute and disagree: the fence says `past_due: 0`, the tool says **9 DEFECTS**. The desk's daily work queue is wired to the forgiving one.

```
$ .venv/bin/python scripts/recommendations.py report
recommendations: 231 total | 71 implemented | 5 rejected | 62 scheduled | 78 open
  DEFECT [UNDISPOSED past grace] R0067 (cycle, 1.2d): …
  DEFECT [UNDISPOSED past grace] R0068 (cycle, 1.2d): …
  DEFECT [UNDISPOSED past grace] R0069 (cycle, 1.2d): …
  DEFECT [SCHEDULED past due]    R0002 (max_audit, 5.6d): …
  DEFECT [SCHEDULED past due]    R0020 (cycle, 3.5d): …
  DEFECT [SCHEDULED past due]    R0025 (cycle-2026-07-28, 3.2d): …
  DEFECT [SCHEDULED past due]    R0043 (cycle-2026-07-30-generation, 2.0d): …
  DEFECT [SCHEDULED past due]    R0058 (deep_sweep, 1.4d): …
  DEFECT [SCHEDULED past due]    R0062 (cycle, 1.4d): …

$ cat data/conversion_status.json      # written 2026-08-01T02:05:17Z by check_conversion.py
  "past_due": 0,
  "past_due_ids": [],
```

Nine defects and zero defects, same file, same morning. **Three independent causes, all in
`scripts/check_conversion.py`:**

1. **Off-by-one-day on every scheduled row.** `past_due = [r for r in backlog if isinstance(r.get("due"), str) and r["due"] < today]` (check_conversion.py:~104) — a *string* compare, strictly less-than, against `now.date().isoformat()`. A row due `2026-08-01` is not `< "2026-08-01"`, so it is invisible **on the day it comes due**. `recommendations.py:owed()` uses `datetime.fromisoformat(due) < now` and correctly flags it. The fence is systematically one day more forgiving than the tool, on every row, forever.
2. **The `open` backlog cannot be past-due at all.** All 78 `open` rows carry `due: None` (verified: `backlog rows with NO due date: 93`, `status=open: 78 of which no due: 78`), and the `isinstance(..., str)` guard drops every one. L2.3/the doctrine's 24h rule ("Undisposed past 24h is a DEFECT") is *not measured by the fence at all* — only `recommendations.py` measures it, and only it found R0067/68/69.
3. **The queue reads the fence, not the tool.** `grep -n "conversion_status" scripts/run_max_push.py` → line 239 `d = _json("data/conversion_status.json")`, line 245 branches on `d.get("repair_mode")`. `run_max_push.py` is the artifact that orders the desk's daily work. It consumes the meter that reports zero.

This is the desk's own **two-sources-of-truth** failure class — the same shape as the 13,155/4,500
equity split named in L1.28a — reappearing inside the governance layer that exists to catch it.
Direction of the error is the dangerous one: the authoritative-for-work meter under-reports.

*Perspective: INTERNAL / CONTRARIAN (a metric that misleads). Confidence 0.95 (both commands run
minutes apart against one file).*

---

### M3 [INTERNAL — a third status the ledger's own tooling cannot see]. 15 rows are in a state no organ recognises: permanently backlog, permanently un-dispositioned, and silently dropped from the summary line.

`scripts/recommendations.py` will only *write* three dispositions:
```
$ grep -n 'choices=\["implemented"' scripts/recommendations.py
223:    p.add_argument("--status", required=True, choices=["implemented", "rejected", "scheduled"])
```
But the ledger contains 15 rows in two statuses it cannot write, all with `disposed: None`:
```
status counts: {'scheduled': 62, 'implemented': 71, 'rejected': 5, 'open': 78, 'done': 14, 'screened': 1}
  R0133 done  disposed=None commit=d3d4c27 :: PAPER BOOK RESOLVER …
  R0134..R0144, R0170, R0171, R0173  done  disposed=None commit=None
  R0140 screened disposed=None commit=None :: COPYTRADING SCREENED, Stage A …
```
Consequences, each verified:
- **`_TERMINAL = frozenset({"implemented","rejected","retired"})`** (check_conversion.py:63) excludes `done`/`screened` → all 15 count as **backlog forever** and can never count as a disposition. ~10% of the 155-row "conversion debt" the desk is in REPAIR-MODE over is *completed work*.
- **The report line does not sum.** `231 total | 71 implemented | 5 rejected | 62 scheduled | 78 open` → 71+5+62+78 = **216**, not 231. Fifteen rows are printed in no bucket. Nothing in `report()` reconciles the total, so a reader (human or LLM) who assumes the buckets partition the ledger is silently wrong by 15.
- **`dispose` refuses to re-dispose them.** `if row["status"] in _TERMINAL: raise SystemExit(...)` — `done` is *not* in `_TERMINAL`, so these can be re-dispositioned; but nothing knows to. They are invisible to `owed()` too (`status == "open"` and `status != "scheduled"` both exclude them), so they will never appear in any DEFECT line. **A row can be parked forever simply by writing an unrecognised status into it** — the exact "quietly dropping an inconvenient row" escape L2.3 says is closed.

*Perspective: INTERNAL / GREENFIELD. Confidence 0.95.*

---

### M4 [CONTRARIAN — the gate-optimality duty turned on governance]. REPAIR-MODE is a welded flag: it is unreachable-off by arithmetic, so it steers nothing.

```
$ cat data/conversion_status.json
  "status": "REPAIR-MODE", "repair_mode": true,
  "backlog": 155, "repair_mode_line": 25,
  "arrival_rate_per_day": 33.0, "disposition_rate_per_day": 10.857,
```
The flag turns off only when `backlog <= 25`. To get from 155 to 25 requires 130 net dispositions
while arrivals run at 33/day and dispositions at 10.9/day — i.e. **net +22/day in the wrong
direction**. There is no arrival rate at which this line is reachable without either a ~3× capacity
increase or admission control, and 15 of the 155 are immortal by M3. So `repair_mode: true` is a
**constant**, and every consumer branching on it (`run_max_push.py:245`) takes the same branch every
run, forever.

The desk's own GATE-OPTIMALITY DUTY: *"A gate that accepts ~0% or rejects ~100% of candidates carries
ZERO information and is a defect to investigate, not a virtue."* L1.43 applies the same logic to
governance explicitly. This fence was built 2026-07-31 and has, as far as the artifact shows, never
been anything but REPAIR-MODE. A permanently-on repair flag is indistinguishable from no flag: it
cannot tell a good day from a bad one, and "flip effort from finding to fixing" that fires 100% of
the time is not an admission-control signal, it is wallpaper.

Note this is NOT an argument to raise the line to make it green — that is the denominator trick. It
is an argument that **the fence currently has no discriminating output**, and the honest fix is a
*rate*-based trigger (dispositions < arrivals over a trailing window) which can actually toggle,
plus real admission control, which is what queueing theory says is the only thing that drains a
ρ≈3 queue.

*Perspective: CONTRARIAN + EXTERNAL. Confidence 0.9 (arithmetic on published rates).*

---

### M5 [INTERNAL — L1.33 is 0-for-1 and nothing pages]. Every "cross-family" exploration organ on this desk is running SOLO, and the partner has never once succeeded.

L1.33 makes the GPT-9 seat a standing partner on every exploration organ, and makes the CONFIRMED /
CONTESTED / SOLO verdict "the whole value". The complete log:
```
$ cat data/second_family_log.json
{"calls": [{"available": false, "model": "openai/gpt-9", "context": "blindspot_max",
            "at": "2026-07-31T19:10:08.218821+00:00",
            "reason": "HTTPError: HTTP Error 400: Bad Request", "chars": 0}]}
$ stat -c '%y' data/second_family_log.json  ->  2026-07-31 19:10
```
**One call, ever. It failed. Nothing has called it since.** The law was written 2026-07-31 and the
partner has a lifetime success rate of 0/1 across ~1 day. Memory of the 08-01 capability hunt
independently records "SOLO (GPT-9 HTTP 400)". So:
- every blind-spot organ is reasoning in exactly one model family's priors — *the precise failure
  L1.33 exists to detect, turned on itself*;
- HTTP 400 is a **request-shape / model-id error, not a funding error**. The law's framing ("the
  partner is dead for want of funding" as a dated measured fact) pre-supposes the failure mode is
  money; the evidence says it is a bad request. Nobody has tested the distinction, so a
  possibly-one-line fix is sitting behind an assumed budget wall.
- L1.33 says an unavailable partner must yield the label SOLO, "explicitly NOT confirmed" — that
  part is working. But there is no fence that *fails* when the partner has been unavailable for N
  consecutive calls, so a permanent single-family desk generates no alarm.

*Perspective: INTERNAL + FUTURE. Confidence 0.9 (the log is the complete record by construction).*

---

### M6 [INTERNAL — CONFIG-VS-OUTCOME, and the sharpest finding of this sweep]. The fence built to detect zero-yield exploration organs grades file **mtime**, not yield. A hunt that failed on auth and produced nothing turns its organ **GREEN**.

L1.32's own justification: *"UNMEASURED YIELD — an organ producing nothing looks identical to one
producing steadily."* The fence it produced still cannot tell those apart. Its entire grader:
```
$ grep -n "state = \|_age_hours" scripts/check_exploration.py
75: def _age_hours(p: Path, now: datetime) -> float | None:
95:     age = _age_hours(root / rel, now)
97:     state = "NEVER-PRODUCED"     # age is None
100:    state = "STALE"              # age > max_h
103:    state = "FRESH"              # else
```
There is **no yield term anywhere** — not a proposal count, not a non-empty check, nothing but the
artifact's modification time. Now the proof that this is not hypothetical:
```
$ cat data/cro_ai_logs/capability_hunt.log
=== capability-hunt start Fri Jul 31 09:30:02 PM UTC 2026 ===
[hunt] {"stamp":"20260731","slot":2,…,"claude_proposed": false, "gpt_proposed": false,
        "cross_family": false, "built": false, …}
[hunt] builder tail: BRAIN_AUTH_FAILED
=== capability-hunt exit 0 at Fri Jul 31 09:37:03 PM UTC 2026 ===
```
That run **failed on authentication**, proposed nothing, built nothing — and the wrapper **exited 0**
and rewrote the artifact. Under `check_exploration.py` that write is indistinguishable from a
productive hunt; it refreshes `age_hours` and the organ reads FRESH. Today's artifact confirms the
grading is live and age-only: `"capability_hunt": {"state": "FRESH", "age_hours": 0.4}`.

Three compounding consequences:
1. **An infrastructure failure is recorded as a research result.** L1.25's central lesson is that
   "no survivors" must first be tested against "the instrument is broken". Here the desk cannot even
   *ask* the question, because auth-failure and honest-null are written into the same record with the
   same shape. L1.40 says "an empty brainstorm is a FAILED RUN, not a thin seam" — the record makes
   them identical.
2. **The sibling organ already has the fix.** `scripts/run_deep_sweep.py:150-170` distinguishes
   `returncode == 90` → *"BRAIN_AUTH_FAILED … This is RETRYABLE"*, writes a `.FAILED` sidecar, and
   preserves the partial. `run_capability_hunt.py:341` emits the identical `exit 90` sentinel and
   **nothing consumes it** — the wrapper swallows it into `exit 0`. This is the proactive battery's
   ADJACENCY move: one instance is never one instance, and here the repaired sibling sits 200 lines
   away in the same repo.
3. **Nothing pages.** `grep -rn "BRAIN_AUTH_FAILED" scripts/ libs/ ops/` → three hits, all
   *producers* of the string, zero consumers that alert. (Caveat, per the log-reaper finding: the
   reaper keeps 30 of 98 logs 3×/day, so the observed count of 1 auth failure is a **floor**, not a
   total — the true rate is unmeasurable from disk.)

*Perspective: INTERNAL / FUTURE. Confidence 0.95 (grader code + a real failed run in the log).*

---

### M7 [INTERNAL — misleading metric, the most important one on the desk, and it reads BACKWARDS]. The "is the principal still finding our gaps?" gauge has logged **zero** principal-origin rows for 7.75 days — a window in which the doctrine records **24 principal orders**.

The UNIVERSAL DUTY SET calls this the failure signal: *"PRINCIPAL-FOUND IS THE FAILURE SIGNAL — if he
is still the primary gap-finder, the maximization system is not working and that is the cycle's top
defect."* The gauge:
```
$ .venv/bin/python … data/blind_spot_ledger.jsonl
origin: {'principal': 14, 'self': 78, 'guard': 5}
LAST principal-origin ts: 2026-07-24T08:18:50   (7.75 days ago)
LAST any-origin ts      : 2026-07-31T21:02:45
$ grep -oE "principal (order )?[^)]{0,30}2026-07-(2[5-9]|3[01])" ops/principal_doctrine.txt | wc -l
24
```
**Zero logged. Twenty-four in the doctrine.** And these were not trivia — the doctrine's own text
credits the principal with finding the flat-$100k capacity floor, the 13,155/4,500 two-source equity
split, L2.3 being fenced but absent from every organ's doctrine, and the 2h-stale max_push phasing.
Every one is a textbook blind spot; none was logged as one.

**The consuming check is also welded off.** `scripts/max_audit.py:764`:
```python
if by["principal"] > by["self"] + by["guard"]:
    defects.append(("system-not-self-sufficient", …"TOP defect."))
```
Current values: 14 > 78 + 5 → False. Worse, `live = [r for r in rows if not r.get("baseline")]` uses
**all-time** counts with no time filter — while `_blind_rows_window(days=7)` is defined **10 lines
below in the same file** and used by a different check. So the threshold recedes monotonically with
uptime: every self-found gap the desk logs makes it permanently harder for this check to ever fire,
*regardless of how much the principal is actually doing*. It is a self-awareness gauge whose
sensitivity decays to zero as a function of runtime.

Two independent defects stacked: the **input** is not being populated (24 unlogged), and the
**threshold** is arithmetically unreachable. Either alone would blind the gauge; together the desk's
answer to "am I still dependent on the human?" is structurally guaranteed to be "no".

*Perspective: INTERNAL / CONTRARIAN. Confidence 0.95. Carried and now quantified from 07-31 M6 —
second consecutive audit, unmoved.*

---

### M8 [INTERNAL — the most-published number on this desk has no estimator at all]. `unknown_unknown_score` appears in **40** sweep reports and is computed nowhere.

```
$ grep -rn "unknown_unknown_score" docs/research/deep_sweep/*.md | wc -l
40
$ grep -rn "unknown_unknown" scripts/ libs/ ops/
(no output)
```
Forty published instances, zero lines of code. It is asserted by an LLM, moved with a narrative
reason, and then **aggregated by the synthesis** into a desk-wide picture
(`20260731_SYNTHESIS.md:56` — *"every seat independently put the ceiling at 80–93%… median ceiling
≈ 85%"*). Two failures follow:

1. **It is not comparable across seats, because the seats use opposite conventions.** Both of these
   are in the corpus, from the same week:
   - `20260801_data-intelligence.md:47` — *"8/10 — **up from 7**. This sweep found that the two instruments…"* (finding an unknown class **raises** the score)
   - `20260801_data-moat.md:61` — *"**0.30**, down from 0.35, for a specific reason: the glob/scope frame error…"* (finding an unknown class **lowers** the score)
   Both are defensible Bayesian readings, and that is exactly the problem: no convention is declared,
   so the number's *direction* is a free parameter of the author. Averaging or trending it across
   seats is meaningless, and the synthesis does both.
2. **It escapes L1.29 entirely.** L1.29 requires every consequential probability to be logged with a
   resolve-by date and graded, on the grounds that *"a prediction the desk refuses to grade is a
   BELIEF, not a forecast."* `unknown_unknown_score` is a probability-shaped assertion about how much
   the desk does not know, it steers where effort goes next, it is never logged to
   `forecast_calibration`, and it is never resolved. It is the largest un-calibrated belief on the
   desk hiding in plain sight inside the calibration law's own blind spot.

The honest position: this score should either get a real estimator (M11 gives one that is buildable
today) or be demoted from a number to prose. A fabricated decimal invites arithmetic that the
underlying judgement cannot support.

*Perspective: CONTRARIAN / GREENFIELD. Confidence 0.95 (grep is exhaustive over the repo).*

---

### M9 [INTERNAL — a resource guard that measures the wrong quantity, and whose page is calibrated above its own failure point]. The LLM budget gauge passed on **6/6** logged runs while the provider was returning 402 out-of-credit.

```
$ cat data/cro_ai_logs/kimi_hunter.log        # 6 identical blocks
    budget: MTD $49.66 of $120.00 envelope
  WAVE 1 -- SHADOW MAPPING
    FAILED (HTTPError 402)
    OpenRouter is out of credit. The hunt is BLOCKED, not broken --
```
The guard (`scripts/kimi_hunter.py:254-259`) computes
`mtd = usage_at_run_start - usage_at_month_start` and passes if `mtd < monthly_envelope_usd`.
It measures **monthly spend against a monthly envelope**. The constraint that actually binds is a
**prepaid balance**, which does not reset monthly. These are different quantities, and the guard has
no visibility into the second one at all. Three consequences, each verified:

1. **The page can never fire before the outage.** `alert_at_usd: 90.0`, but the account was already
   out of credit at an observed MTD of **$49.66** — the alert threshold sits ~1.8× *above* the real
   failure point. `"alerted": false` in the state file confirms it has never fired.
2. **The month roll makes it read maximally healthy exactly when it is least true.** As of now:
   ```
   usage_at_run_start = 60.58668487 ; usage_at_month_start = 60.58668487
   MTD as computed = 0.0 ;  budget_ok -> True ;  alert reachable -> False
   ```
   A number minus itself. Same shape as the `deployed_capital` ≡100% defect the infrastructure sweep
   found — the READ-WITHOUT-WRITER / self-referential class L1.40 names as the desk's most prolific.
3. **`kimi_hunter` never writes the field it reads.** `grep -rn "usage_at_run_start"` → the only
   writer is `scripts/run_external_panel.py:252`. If that organ stops, kimi_hunter's numerator
   freezes at the month-start value and MTD reads $0.00 indefinitely. A guard whose freshness depends
   on an unrelated organ, with no contract between them, is exactly the L1.44 consumption-freshness
   gap — and this read is **not** wired through `read_fresh`.

Net: an organ scheduled **8×/day** (`5 */3 * * *`) has produced nothing, ever
(`check_exploration.py` → `"kimi_hunter": {"state": "NEVER-PRODUCED"}`), the guard that should have
escalated says everything is fine, and the log's own words — *"BLOCKED, not broken"* — is a phrase
that has repeated six times with nothing acting on it.

*Perspective: INTERNAL / EXTERNAL. Confidence 0.95.*

---

### M10 [INTERNAL — both independent-family lanes are down simultaneously; the desk is single-family and nothing says so]. 

Combining M5 and M9: the desk has exactly two routes to a second model family, and both are dead
today, for **different** reasons:
- **GPT-9 seat** — `data/second_family_log.json`: 1 call ever, `HTTPError: HTTP Error 400: Bad Request`.
- **Kimi (OpenRouter)** — `data/cro_ai_logs/kimi_hunter.log`: `HTTPError 402`, out of credit.

`check_exploration.py` still grades the family **4/6 FRESH**, because the four surviving organs
(`capability_hunt`, `blindspot_max`, `blindspot_prober`, `deep_sweep_meta`) are **all Claude**. So
the exploration-family fence reports the family as two-thirds healthy at the precise moment its
model-family diversity is **zero** — and model-family diversity is the entire premise of L1.33
(*"a model cannot see its own blind spot"*). The fence counts organs; the law is about **families**.
Nothing measures families.

The 400/402 distinction is load-bearing and is being lost: 402 is a funding problem (the doctrine's
framing, "dead for want of funding"), 400 is a **request-shape/model-id** problem that costs nothing
to fix. Filing both under "partner unavailable" means a possibly-one-line fix is parked behind an
assumed budget wall.

*Perspective: INTERNAL / NEGATIVE-SPACE. Confidence 0.9.*

---

### M11 [INTERNAL — THE HEADLINE FINDING]. The kimchi retraction was closed as IMPLEMENTED after correcting **4 lines in 1 file**. The refuted claim is still asserted at **~45 sites**, including the charter 11 dig prompts are ordered to "OBEY … IN FULL", a graveyard with no kimchi kill row, and a **code module that routes research compute on it**.

R0051's own text names the scope correctly, then the fix does not match it:
```
$ .venv/bin/python … R0051
summary: "EVERY ORGAN IS BEING TAUGHT FROM A RETRACTED RESULT. ops/principal_doctrine.txt line 89 …
          This text is injected into every miner, digger and brain …"
status:  "implemented"
reason:  "Both doctrine sites corrected in ops/principal_doctrine.txt …"
commit:  "4048e1e"
$ git show --stat --format="" 4048e1e | grep principal_doctrine
 ops/principal_doctrine.txt | 4 +-
```
**Four lines, one file.** Verified still-live sites (each read directly, not inferred):

**(a) `docs/DIGGING_CHARTER.md:215` — the retracted proof-text, verbatim, uncorrected:**
```
$ sed -n '215p' docs/DIGGING_CHARTER.md
… THE EVIDENCE THIS IS RIGHT: 420 price-family hypotheses produced 0 survivors, while ONE new axis
(kimchi premium) screened in about an hour produced IC +0.148 and momentum timing Sharpe 1.3 --
beating every price-only sleeve the desk ever rejected. The edges are in untouched axes, not the
picked-clean price space.
```
This is the *original* of the sentence `principal_doctrine.txt:89` was rewritten to retract. Its
readership:
```
$ grep -rn "DIGGING_CHARTER" ops/*.txt ops/*.sh
ops/frontier_{ar,br,cn,en,jp,kr,ru}_prompt.txt:3:  OBEY docs/DIGGING_CHARTER.md IN FULL
ops/litminer_dig_prompt.txt:1 / prospector_dig_prompt.txt:1 / dataaxis_dig_prompt.txt:1 /
ops/blindrediscovery_dig_prompt.txt:1 / ops/run_cro_ai.sh:87
```
Eleven organ prompts, seven of them with the words **"OBEY … IN FULL"**. `max_audit.py:2536` also
lists the charter in `_LAW_DOCS`, so the audit organ treats it as co-equal law.

**(b) `docs/graveyard.md` — 47 rows, and not one of them is the kimchi kill:**
```
$ grep -c "^|" docs/graveyard.md            ->  47
$ grep -in "kimchi" docs/graveyard.md
78: … Kimchi is RARE, not a generic regional-premium pattern.
80: … Value = corroborates kimchi's realness; NOT a separate clock.
81: … Regional-premium class is now exhausted: kimchi is the lone survivor across KR/JP/BR/TR/Coinbase tested.
87: … DIRECTLY RELEVANT TO THE LIVE KIMCHI CLOCK …
```
The desk's canonical dead-list contains **three rows asserting kimchi survived and zero recording
that it died** — for the desk's own flagship refutation. `ops/prospector_dig_prompt.txt:8` makes
consulting this file **MANDATORY** before regenerating a candidate, so a digger that rediscovers a
Korean-premium idea finds no kill row, finds three endorsements, and proceeds. The graveyard is
called sacred by L1.17; on its single most important entry it is *inverted*.

**(c) `research_agenda.json:190-194` — the retired clock is still an active agenda item:**
```
"id": "kimchi_premium_timing", …
"forward_clock": "data/kimchi_premium.jsonl from 2026-07-23; needs >=40 timestamp-aligned live
                  days then gauntlet + slot."
```

**(d) — and this is the one that costs real research — `libs/validation/reject_rescore.py:4`
makes a live COMPUTE-ROUTING decision on the refuted claim:**
```
Re-scoring ALL rejects is wasteful: the 420 picked-clean price rejects are almost all genuinely
dead, and burning compute confirming that recovers nothing.
```
This is not prose in a doc. It is the stated ROI rationale, inside the rejection-shadow feeder, for
**not re-scoring the 420**. The 420/0 record is a *known instrument artifact* (welded gate, L1.25),
and the alpha-discovery audit's standing open item is precisely *"420 never re-scored under the
fixed gate."* The reason it has never been re-scored is written into the module that decides. A
refuted premise is silently allocating the desk's research compute away from the exact experiment
its refutation makes valuable.

**Aggregate scale** (subagent sweep, spot-verified on the four sites above): ~45 POSITIVE-STALE
sites across `docs/`, `ops/`, `scripts/`, `libs/` and `research_agenda.json`, spanning the digging
charter, `docs/CONSTITUTION.md:331`, `MECHANISM_GRAPH.md:49` (kimchi = **LIVE CLOCK**, read by
`llm_blind_researcher.py` and `hypothesis_generator.py`), `literature_coverage.md:97` (both dead
facts as *"Graveyard priors loaded and binding"*), `run_llm_trader.py:209,220` (dead fact returned
to the trading LLM as a refusal reason), `run_discretionary_hunt.py:25`, `fusion_engine.py:8`,
`screen_fx_debasement.py:6`, `max_audit.py:1169,1281`, `ops/CRO_CONSTITUTION.md:515` (*"390 tested /
0 survivors shows the gauntlet bar does the protecting"* — the welded gate misread as gate
*validation*). Coinbase/Turkey premiums are **clean** — all 97 hits correctly mark them graveyarded.

*Perspective: INTERNAL / CONTRARIAN. Confidence 0.95 on the four sites I read directly; 0.85 on the
~45 aggregate (subagent grep, sampled).*

---

### M12 [GREENFIELD — the defect class M11 belongs to, and it is the reason M11 could happen]. "Implemented" on this desk means *the example named in the finding was fixed*, not *the defect class was eliminated*. Nothing checks the difference.

M11 is not carelessness — it is the ledger working exactly as designed. R0051 named
`principal_doctrine.txt line 89`; the fix corrected `principal_doctrine.txt`; the disposition is
literally true (*"Both doctrine sites corrected"*) and the row is honestly closed. The defect is
that **the ledger has no representation for a finding's blast radius.** A row has `summary`,
`commit`, `reason` — and no field for *"where else does this shape exist?"*.

The desk already owns the countermeasure and did not run it. The PROACTIVE BATTERY DUTY, move 2:
> *ADJACENCY — whatever was just fixed, find where else that exact failure SHAPE exists and fix
> those in the same pass, because one instance is never one instance.*

There is no fence that fails when a row is closed without an adjacency sweep, and no field that
records one was done. So ADJACENCY is a duty with no artifact — and per the desk's own
OUTCOME-NOT-CONFIG rule, a duty with no artifact is unmeasured, and unmeasured counts as zero.

**This generalises to the whole `implemented` bucket.** 71 rows are marked implemented. If the
R0051 pattern is typical, an unknown fraction closed on their named instance while the class
survived elsewhere — and the ledger would look identical either way. That is a measurable question
nobody has asked (test X3, §4).

Why this is the *right* frame rather than "someone was sloppy": the same session that closed R0051
also wrote a 444-line meta audit and a 372-line synthesis in one commit. The failure is not effort,
it is that **the desk's unit of repair is the instance and its unit of harm is the class.** Until
those match, high-effort sessions will keep closing rows while leaving the damage in place, and
every metric will read green.

*Perspective: GREENFIELD / CONTRARIAN. Confidence 0.9.*

---

### M13 [BLIND-SPOT TRANSFER — EPIDEMIOLOGY & SOFTWARE-RELIABILITY: **capture–recapture** and **defect seeding**]. The desk publishes an unknown-unknown score it cannot estimate, while owning both standard estimators and applying neither to the audit layer.

*(Prior transfers by this seat: CONTROL THEORY 07-29, OPERATIONS RESEARCH/QUEUEING 07-31. This one
is fresh and, unlike most transfers, it is buildable this week with no new dependency.)*

**The problem it solves.** M8 established that `unknown_unknown_score` appears in 40 reports with
zero lines of estimating code. Epidemiology has faced exactly this question for a century — *how
many cases exist that no surveillance system saw?* — and it does **not** answer it by asking
experts to assert a decimal. It answers it with two estimators, and the desk already owns the
machinery for both.

**(1) CAPTURE–RECAPTURE (Lincoln–Petersen / Chapman).** Two independent detectors sweep the same
population. Detector A finds `n_A`, detector B finds `n_B`, and `m` items are found by **both**.
Then the population estimate is `N̂ = n_A·n_B/m`, and the count **neither detector found** is
`N̂ − (n_A + n_B − m)`. That last number is a *measured unknown-unknown count* with a confidence
interval, replacing a vibe.

The desk's data structure is **already a 2×2 capture–recapture table** and nobody noticed:
```
$ cat data/capability_hunt.json
  "claude_proposed": true, "gpt_proposed": false, "cross_family": false
```
`claude_proposed` = captured by A. `gpt_proposed` = captured by B. `cross_family` = the **overlap
cell m**. L1.33 built this to *label* a verdict (CONFIRMED/CONTESTED/SOLO); it is simultaneously the
input to an estimator nobody runs. Across all 3 logged runs `m = 0` and `n_B = 0`, so `N̂` is
currently undefined — **because the second detector is dead (M5/M10), not because the method
doesn't fit.** Fixing the GPT-9 HTTP 400 does not just restore a second opinion; it switches on the
desk's only path to a *quantified* unknown-unknown count.

*The honest caveats, which happen to point the useful way.* Three assumptions are violated here:
detector **independence** (Claude and GPT-9 share training-corpus structure), **homogeneous
catchability** (some blind spots are easy, some are hard), and a **closed population** (new code
creates new blind spots daily). All three biases run in the **same direction — they make `N̂` too
small.** So the estimate is a defensible **lower bound** on the unknown-unknown count, which is
precisely the decision-useful quantity and is infinitely more than the desk has now. With ≥3
detectors (Claude / GPT-9 / the fence battery), the Fienberg log-linear variant relaxes the
independence assumption and gives an interval rather than a point.

**(2) DEFECT SEEDING (Mills' "bebugging"; Basili–Selby).** Plant `K` known defects; run the
inspection; count `k` of them recovered. The detector's recall is `d = k/K`, so the true defect
count is `N̂ = observed_real / d`. This one needs **no second model family, no money, and no new
dependency** — and the desk has built it twice already, for two *other* layers:
```
$ ls libs/validation/positive_control.py          # planted controls FOR THE GAUNTLET
"""Positive/negative controls … Two readings explain that equally well: price space is picked
clean, or the gate is welded shut. Telling them apart needs a candidate whose quality is KNOWN…"""
$ cat data/mutation_score.json                    # planted mutants FOR THE CODE  (bar 0.9)
$ grep -rn "plant" scripts/max_audit.py scripts/run_deep_sweep.py
(no output)
```
**The desk plants controls to certify its alpha gate, plants mutants to certify its tests, and has
never once planted a defect to certify its AUDITS** — the layer that finds everything else. The
argument in `positive_control.py`'s own docstring transfers verbatim: *"0 survivors" and "the gate
is welded" are indistinguishable without a known-good input.* Substitute "the sweep found 12
findings" for "0 survivors" and the sentence is exactly as true — and exactly as unanswered.

**Why this is the highest-compounding item in this report.** Every audit organ's output is currently
un-normalised: "we found N things" with no denominator. A measured recall `d` converts every past
and future sweep from a count into an estimate, retroactively — it is a multiplier on the entire
audit apparatus, which yesterday's audit priced at ~3–4.5 serial brain-hours/day. It also gives
`unknown_unknown_score` a real estimator, gives L1.43's "quiet detector — clean desk or inert
check?" ambiguity an actual answer, and gives the sweep a falsifiable claim about its own value.

**Concrete design (test X1, §4).** Fork the repo to a scratch worktree; plant K=12 governance
defects drawn from the desk's *own* historical defect taxonomy (a welded gate; a metric divided by
itself; a `except: pass`; an artifact with a writer and no reader; an off-by-one in a date compare;
a fence exiting 0 on absent input; a stale-consumed artifact; a duty with no artifact; a hardcoded
constant beside a ratio; a status the tooling cannot write; a cron line whose organ was renamed; an
alert threshold above its failure point) — every one of those is a real class this desk has actually
shipped, so the seeds are realistic by construction rather than by imagination. Run `max_audit.py`
and one deep-sweep seat against it blind. Recall `d = k/12`. **Success criterion: the number
exists.** **Retirement condition: re-run quarterly, or whenever the audit prompt genome changes —
`d` is itself a ratchet under L1.0 and is born with its floor in the same commit (L2.0/L1.41).**

*Perspective: FRONTIER / FUTURE / NEGATIVE-SPACE. Confidence 0.85 that a first `d` is measurable
within one session; 0.6 that `d < 0.5` (i.e. the sweep misses more than half of a realistic planted
population) — that second number is itself a forecast and should be logged under L1.29.*

---

### M14 [INTERNAL — a genuine strength, plus the one gap inside it]. The ratchet fence is sound, honestly reasoned, and correctly refuses to fabricate a floor — but nothing counts what it could not measure.

Reported as a strength because it survived an adversarial read:
```
$ .venv/bin/python scripts/check_ratchets.py --report-only
ratchets | 0 defect(s) | 5 metric(s) below 100%
  OK      test_strength_targets_at_bar   75.0% (floor 75.0% gap 25.0%)
  OK      miner_seats_productive          9.1% (floor  9.1% gap 90.9%)
  OK      scripts_mypy_clean             40.7% (floor 40.7% gap 59.3%)
  …  -> largest gap: miner_seats_productive at 9.1%, 90.9% from 100%
```
`floor == value` on every row is **correct**, not self-greening: `--ratchet` (cron `7 7 * * *`)
records improvements only, and `_ratchet()` is structurally incapable of lowering a floor. The fence
also handles the traps that catch this class — `UNMEASURED` is a defect not a pass (line 180),
`NO-FLOOR` is a defect (182), and a metric born at zero with a zero floor is specially cased (189)
so "OK forever at zero" cannot happen. It reports distance-to-100% rather than a quality verdict,
by explicit design. This is a well-built organ; I looked for the weld and did not find one.

**The gap:** `libs/autodiscovery/validation.py` scored 35.7% and is **excluded** from the ratchet —
for a correct and honestly documented reason:
> *"A BUDGET-TRUNCATED RUN IS NOT A MEASUREMENT… validation.py got 14 of 137 sites through a 1500s
> budget… Excluded entirely rather than floored low: a floor set from a partial run is a fabricated
> constraint."*

The reasoning is right. The consequence is not tracked: **the code that runs the validation gauntlet
— the module deciding which alphas reach capital — has no test-strength floor at all, and the
summary line says `0 defect(s)`.** Excluded-because-unmeasurable and measured-and-fine are
indistinguishable in the output. Under L1.28a unmeasured counts as *zero*; here it counts as
*absent*, which reads better than zero. One extra row (`n_targets_never_fully_measured: 1`) closes
it. **10 % of the ratchet's own target list is currently unmeasurable within its compute budget and
the artifact does not say so.**

*Perspective: INTERNAL / NEGATIVE-SPACE. Confidence 0.9.*

---

### M15 [EXTERNAL — the benchmark register fossilizing into flattery, exactly as its own footer warns]. `self_audit_layer` is graded **T1** on a capability that does not exist — and the T1 grade **removes it from the daily work queue**.

```
$ grep "self_audit_layer" docs/research/TIER1_BENCHMARK.md
| self_audit_layer | T1 | hold: 9-seat sweep + planted controls + recursive meta | no |
$ grep -rn "plant" scripts/max_audit.py scripts/run_deep_sweep.py
(no output)
```
There are **no planted controls in the audit layer** (M13). The grade's justification names three
things and one of them was never built. This is not cosmetic, because the register is machine-read:
```
$ sed -n '279,285p' scripts/run_max_push.py
        score = _TIER_SCORE.get(tier)
        if score is not None and score < 1.0:
            out.append(_item(f"tier1::{layer}", "tier1_process_gap", …))
```
**Only sub-T1 rows are queued.** A row graded T1 is *silently removed from the desk's daily work
queue*. So an over-generous grade does not merely misinform — it de-queues the work, permanently and
invisibly, which is the exact mechanism by which a benchmark becomes flattery. The file's own footer
anticipates this (*"so the benchmark can never fossilize into flattery"*) and the guard it relies on
is a human remembering to re-grade.

Per the sweep charter's instruction to re-grade where evidence moves a tier, this seat's evidence
says: **`self_audit_layer` is not T1.** M6 (the exploration fence grades mtime not yield), M7 (the
self-sufficiency gauge is welded off), M11 (a retraction propagated to 1 of ~45 sites), M13 (no
planted controls), and M16 (the two fences with CI/push authority are config-checkers with
unreachable failure states) are jointly incompatible with "the process standard of Jane Street /
XTX / RenTech." **Proposed re-grade: T2**, closer = *planted-defect recall `d` measured for
max_audit and the sweep (X1) + the exploration fence given a yield term (X2) + an adjacency field on
the ledger (X4)*. `research_governance` (also T1, "matrix zero-orphans is the standing bar") should
be re-examined by the synthesis in light of M12 and M16(b).

*Cohort note.* The transferable practice here is not exotic. Every firm in the cohort runs
**production control testing** — Jane Street's correctness culture and HRT/Jump's simulation/prod
parity both rest on deliberately injecting known conditions and checking the system notices.
RenTech's standing exemplar property is that *the process distrusts its own output by construction*.
The desk applies that to its alpha gate (`positive_control.py`) and to its tests
(`mutation_score.json`) and **not** to the organ that audits both.

*Perspective: EXTERNAL. Confidence 0.9.*

---

### M16 [INTERNAL — the fence estate audited as a portfolio; the through-line is the finding]. **Authority and information are inversely allocated:** the two fences that block pushes and CI are substring-checkers with unreachable failure states, while the two organs that actually measure outcomes have their exit codes deliberately discarded by their only caller.

Sub-audit of 13 governance organs (delegated; load-bearing items re-verified by me). These are the
ones I proved directly:

**(a) `check_freshness` reports `fresh_fraction 1.0` after discarding 90 % of its own registry —
and the discarded rows are the money-path reads.**
```
$ … data/freshness_contracts.jsonl
total contract rows: 62  ->  {'judged': 6, 'FOREIGN': 56}
FOREIGN callers: {'run_cashcarry_executor._structurally_bleeding': 32,
                  'run_cashcarry_executor._rt_bps': 24}
$ … data/freshness_status.json
{'status': 'OK', 'n_contracts': 5, 'fresh_fraction': 1.0}   by_verdict {'FRESH': 5, …, 'FOREIGN': 49}
```
The registry is polluted by the **test suite writing into the production artifact**
(`/tmp/pytest-of-quant/...`), the fence drops those rows as FOREIGN, and what it drops is the
**executor's own** freshness contracts. It then publishes `fresh_fraction: 1.0` and `OK`. Downstream
this zeroes `freshness::contracts_fresh` under leverage **1.00** — the highest weight on the
max-push board. It is also growing: 49 FOREIGN in the 01:52 artifact, 56 on live recompute at 02:22.
L1.44's own rule is that zero contracts is UNMEASURED, never OK; a count of 5 after silently
dropping 56 is the same failure with a friendlier number.

**(b) `check_law_families` — the desk's highest-authority fence (blocks push **and** CI) — reduces
to a status-string whitelist plus `Path(fence).exists()`.**
```
$ sed -n '113p' scripts/check_law_families.py
   if m in const and not (enforced.get(m, {}).get("fences") …
laws governed: 35 | laws with a truthy 'fences' key: 0 | passing ONLY via status whitelist: 35
```
No matrix row carries a `fences` key, so that disjunct is dead code and every law passes on
`status ∈ {ENFORCED, STANDING, HUMAN-ONLY}` — which covers 100 % of the matrix. "GUARDED" is a
**file-existence test**. Commit `067d471` (*"Two laws read ENFORCED while their only enforcement was
called by nothing"*) already established that matrix `ENFORCED` can mean *enforcement called by
nothing*; this fence accepts that wholesale and reports **6/6 families fully enforced**.

**(c) `check_build_standard` certifies 38/38 on five substring greps**, and its own docstring records
that the vocabulary was widened to stop it firing (*"Kept deliberately BROAD… Add vocabulary here
rather than reword an organ"*). Its silent-swallow detector matches `except X: pass` and misses
`contextlib.suppress(Exception)` — the idiom this repo actually uses, including in `blind_spot.py:47`.

**(d) `check_utilisation` cannot exit non-zero.** All eight ceiling producers hardcode a non-empty
`binding_constraint` in the else-branch of the saturation test, so `IDLE-UNEXPLAINED` is a
contradiction in terms and exit 1 is unreachable. Its `deployed_capital` reads
`18675.73/18675.73 = SATURATED` because `_desk_equity_usd()`'s first rung *is* `live_book_usd()` — a
number divided by itself, zeroing `capital_utilisation` (leverage 0.90, 2nd of 10). This is the
*repaired* version of the 13,155/4,500 two-source bug L1.28a was written for: collapsing two sources
into one function converted a **wrong** number into a **tautological** one.

**(e) The verdict history needed to audit any of this is destroyed 3×/day by design.**
`ops/run_cro_ai.sh:99` keeps 30 of ~98 logs; artifacts are gitignored (`data/*`), so
`git log -- data/utilisation.json` → 0 commits. For 4 of 13 organs the question "has this ever
fired?" is **unanswerable from disk**.

**The through-line, which is the actual finding:** the desk allocated *enforcement authority* to the
checks that are cheapest to satisfy and *withheld* it from the checks that measure reality.
`run_max_push.py:114` invokes six fences with `--report-only` (forcing `return 0`) and
`check=False`, binding the result to nothing. That is not an oversight in one place; it is the
estate's shape.

*Perspective: INTERNAL / CONTRARIAN / GREENFIELD. Confidence 0.9 on (a)–(d), re-verified by me;
0.8 on (e).*

---

### M17 [INTERNAL — RESEARCH TRAJECTORY, measured for the first time]. Findings grew **+57 %** in one cycle while prior-finding closure held at **15.2 %**, and **~26–35 % of today's findings are re-findings**. Yesterday's U2 is now answered, and the answer is bad.

Yesterday's ignorance ledger U2 was *"detection marginal yield — nobody measures what fraction of
each day's sweep findings are NEW vs re-findings."* Measured (delegated extraction over the dated
report corpus; two seats cross-checked by hand):

| seat | n_prev (07-31) | n_today (08-01) | repeat (strict) | repeat (broad) |
|---|---|---|---|---|
| execution-growth | 16 | 22 | **59.1 %** | 59.1 % |
| validation-stats | 18 | 28 | 42.9 % | 42.9 % |
| research-engine | 22 | 33 | 18.2 % | 39.4 % |
| infrastructure | 10 | 31 | 19.4 % | 29.0 % |
| data-moat | 12 | 12 | 16.7 % | 25.0 % |
| data-intelligence | 16 | 35 | 8.6 % | 14.3 % |
| **total (7 seats)** | **106** | **166** | **25.9 %** | **34.9 %** |

And the reciprocal, from each report's **own** carry table: pooled **10/66 = 15.2 %** of prior
findings closed in one cycle (validation-stats 0/18; execution-growth *"4 FIXED, 4 PARTIAL, 10
STALLED, 1 REGRESSED-IN-PRODUCTION"*). Detection is scaling; repair is not — M4's queue arithmetic
restated in research terms.

**Three structural facts make this worse than the ratios suggest, each verified by me:**
1. **Today's ~166 findings have no path to the ledger.** `ls docs/research/deep_sweep/*SYNTHESIS*`
   → 0729, 0730, 0731 only — **no 08-01 synthesis**. Ledger rows raised by `deep_sweep` on 08-01: **0**.
2. **The one batch that ever fired is parked.** All 26 `SYNTH0731` rows: `{'open': 25,
   'implemented': 1}`, **`with due dates: 0/26`**. The GAP_REGISTER's own rule — *"A row with no
   date is PARKED, which the register's own rule forbids"* — is violated by 25 of 26 rows written by
   the desk's own synthesis seat.
3. **A seat vanished and nothing noticed.** `ls docs/research/deep_sweep/20260801_*` → **7 files**,
   no `alpha-discovery`. It produced 18 findings yesterday and nothing today. There are **zero
   `.FAILED` sidecars** in the directory, so an absent seat and a healthy seat are the same
   observation — the M6 shape again, one layer up.

*Perspective: INTERNAL / FUTURE. Confidence 0.85 (repeat-fraction is judgement-assisted; the 15.2 %
closure, 0 synthesis, 0/26 due dates and missing seat are exact).*

---

### M18 [CONTRARIAN — a workflow persisting by pure accident]. The desk's flagship self-audit is **scheduled weekly** and **runs daily**, because a byte-count success test mis-reads success as failure. Nobody chose this cadence.

```
$ crontab -l | grep deep_sweep
0 4 * * 0 … flock -n data/.cron_deep_sweep.lock /bin/bash ops/run_deep_sweep.sh      # WEEKLY, Sundays
$ ls docs/research/deep_sweep/                                                        # DAILY in fact
20260726… 20260728… 20260729… 20260730… 20260731… 20260801…
```
The mechanism (corroborated by today's infrastructure seat, G16): `organ_catchup` (cron `*/5`)
re-fires the sweep because a fully-successful run writes fewer bytes than its success threshold. So
the desk's most expensive research organ — yesterday's audit priced the apparatus at ~3–4.5 serial
brain-hours/day — runs **7× its declared cadence** as a side effect of a failure heuristic.

L1.28c is explicit: *"every scheduled line carries a DECIDED cadence with its reason… 'it has always
run daily' is NOT a reason"*, and *"a cadence whose ceiling type is UNNAMED is unmeasured, and
unmeasured counts as IDLE."* This cadence was never decided at all. **And the honest reading cuts
both ways, which is why this is CONTRARIAN rather than a bug report:** daily may well be *right*
(L1.28c says cadences hunt their ceiling upward), but M17 shows repeat-fraction rising and closure
flat — the signature of an audit organ firing **faster than its subject's state changes**, which is
the information-arrival ceiling L1.28c names. The desk cannot currently tell which, because it has
never measured the sweep's marginal yield. X1 and the repeat-fraction series are exactly the two
numbers that would decide it.

*Perspective: CONTRARIAN / INTERNAL. Confidence 0.9 on the mechanism; 0.5 on which direction the
cadence should move — deliberately unresolved, and that is the point.*

---

### M19 [NEGATIVE-SPACE SWEEP — what has never been looked at at all]. **52 % of the desk's finding stores (14 of 27) have no content reader.** ~1,500 recorded items are unreachable by any script.

The desk's own memory records one instance (*"improvement_inbox.md is write-only"*). The measurement
shows it is the **dominant pattern**, not an instance:

| store | items | who reads the CONTENT |
|---|---|---|
| `docs/research/improvement_inbox.md` | **92 entries / 113 KB** | **nobody** — 5 string mentions, one of which (`run_deep_sweep.py:235`) is *prompt text telling the LLM the file is write-only* |
| `data/information_value.jsonl` | **1,244 rows** | nobody |
| `docs/research/blind_rediscovery_log.md` | 23 entries / 49 KB | nobody (3 scope-registration strings) |
| `docs/research/literature_coverage.md` | 43 KB | nobody — fenced at **30 h age / 50 bytes** |
| `docs/research/panel_inbox.md` | 15 sections / 37 KB | nobody (write-only by construction) |
| `docs/research/weak_signal_registry.md` | 8 entries, last written **07-28** | nobody; its cadence fence is mtime-only |
| `docs/EXECUTION_QUEUE.md` | 12 ranks | nobody — 9 mentions, **all docstrings** |
| `data/suggestion_ledger.jsonl` | **0 rows**, 3 writers | never produced |

**The sharpest sub-finding, and it is the same shape as M6:** for at least six of these,
`max_audit.py` *does* have a fence — and every one is an **mtime + min-bytes** test (e.g.
`("litminer-product", "docs/research/*iterature*coverage*.md", 30, 50)`). **Any 50 bytes written in
the last 30 hours passes.** The fence certifies that a file was touched, never that anything in it
was true, new, or read. Three independent seats found this identical shape today — infrastructure
(11 fences OK on absent input), research-engine (F-7), and this one — which is itself evidence that
`mtime-as-proxy-for-work` is a **class the desk has not named. It should be named, because naming it
is what makes it greppable:** every `stat()`-based fence in the estate is then a candidate.

Other negative space, checked and genuinely empty: **`docs/research/ASSUMPTIONS.md` still does not
exist** (`ls` → No such file), carried unmoved from 07-29 U7 and 07-31 U5 — **third consecutive
audit**. The desk cannot enumerate its own load-bearing assumptions, which is exactly the capability
that would have caught M11 in one query.

*Perspective: NEGATIVE-SPACE / GREENFIELD. Confidence 0.85.*

---

### M20 [FUTURE — 2–3 year redesign, and the cheap version available now]. The whole meta layer is a **document-shaped** system pretending to be a **database-shaped** one, and most findings above are symptoms.

M3 (a status the tooling cannot write), M12 (no blast-radius field), M17 (seats renumber findings
every day, so repeats cannot be detected automatically), M19 (14 write-only markdown stores) and M11
(a fact asserted at ~45 sites with no propagation path) share one root cause: **findings, facts and
dispositions live in prose, and prose has no referential integrity.**

With 2–3-year compute this is trivial: every finding is a row with a stable ID that survives across
cycles; every doctrinal claim is a node with an edge to its evidence; retracting the evidence
**automatically flags every dependent claim** — M11 becomes a query, not an archaeology project.
The 2026 version is not exotic either, and is the actual recommendation: (1) stable per-seat finding
IDs that persist across dates — without them M17's repeat-fraction can never be automated; (2) a
`claims` table mapping each load-bearing doctrinal assertion to its evidence artifact, which *is* the
missing `ASSUMPTIONS.md` in machine-readable form; (3) one queue with N views (yesterday's M10, still
open).

The reason this sits in FUTURE rather than at the top of the portfolio: items (1) and (2) are cheap
and high-leverage, but they are **multipliers on a repair capacity currently running at 15 %**
(M17). Building better finding infrastructure while 25 of 26 synthesis rows sit parked would raise
the arrival rate into an already-unstable queue — the exact L1.28b failure. **Order matters:
capacity first (X4/X5), structure second (X6).** That ordering is itself the recommendation.

*Perspective: FUTURE / GREENFIELD. Confidence 0.8.*

