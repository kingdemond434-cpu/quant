# WEEKLY DEEP COLD AUDIT — meta-and-blindspots — 2026-07-31

STATUS: COMPLETE

_Third completed audit of this layer (07-29 first-ever, 07-30 cut off mid-run at finding M2 —
its sections 2–4 died as placeholders and, note, it never flipped its sentinel). Read-only.
Every claim carries its proving command. This sweep's outside-field transfer: OPERATIONS
RESEARCH / QUEUEING THEORY. Central question, per charter: is each cycle making the next
stronger — and the answer is now measurable, so it is measured._

## SCORES

- current_capability_pct: 58 (07-29 audit: 45). Real movement: sentinel grading (R0055,
  same-day), synthesis has now run 2 consecutive days, first-ever rowing of sweep findings
  (R0053–R0060), global brain mutex, a 28-row triage burst on 07-30.
- practical_ceiling_estimate: 85
- ceiling_gap: 27
- opportunity_cost_1y: HIGH, now quantified. Findings arrive ~14/day; cross-session
  implementation runs ~0.6/day; the undone stock grows ~+10/day (33→41→53 across three
  audits). ≥80% of everything every audit organ produces currently converts to nothing.
  The audit apparatus consumes ~3–4.5 serial brain-hours/day (~15–19% of the 24h
  one-brain-mutex ceiling) with its conversion wire open. A falsified doctrine claim has
  steered every organ for 8 days.
- confidence: 0.85 (three audits of this layer; core claims measured directly from ledgers)
- unknown_unknown_score: 0.45 (down from 0.7 — the layer is no longer unaudited; residual
  unknowns are concentrated in compliance rates and detection marginal-yield)
- info_gain_if_investigated: high for four named measurements (MTTR / P(fix|finding),
  repeat-finding fraction per sweep, brain-hours by organ, scheduled→done conversion)
- expected_alpha_contribution: indirect but decisive — the open gate-fix rows (R0030, R0033,
  R0043, R0044) are exactly what decides which alphas live; they sit in the starving queue
  this report is about.
- expected_compounding_contribution: HIGHEST of the eight subsystems — every μ-side
  (repair-capacity) fix multiplies every future finding from every organ permanently.
- ceiling_expansion: the ceiling assumption is "detection and repair share one serial brain
  and repair is voluntary." That is organizational, not technological. Structured
  (schema-forced) findings + a standing repair consumer moves the ceiling itself.

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**S1. The loop CAN close same-day at criticality.** `scripts/recommendations.py` ledger:
R0053 (Tier-3 dead-man silently disarmed), R0054, R0055 all raised 2026-07-30, all
implemented 0.24d later in commit fccc580 — a survival rail re-armed within ~6h of a cold
audit finding it. When a finding is loud enough and the finding session acts, the desk is
fast.

**S2. The runner is now outcome-asserted.** `sed -n '96,116p' scripts/run_deep_sweep.py` →
`_complete()` grades on the `STATUS: COMPLETE` sentinel, keeps the 1200b floor only against
binary stubs, writes failure diagnoses to a `.FAILED` sidecar and preserves partials. The
07-30 M1 finding (size-only self-greening) was implemented the same day (R0055). Today all
7 sibling reports carry the sentinel: `grep -H "^STATUS" docs/research/deep_sweep/20260731_*.md`
→ 7× COMPLETE + this file.

**S3. Synthesis now exists and rows.** `ls docs/research/deep_sweep/*SYNTHESIS*` →
20260729_SYNTHESIS.md, 20260730_SYNTHESIS.md — after 0/3 ever as of 07-29. The 07-30
synthesis rowed 8 findings (R0053–R0060) into the ledger — the first sweep findings ever
rowed from any dimension other than data-moat. (Caveat in M4: it did this by exceeding its
own prompt.)

**S4. The global brain mutex is real, kernel-safe, and documented with its own falsifier.**
`ops/brain_env.sh` → flock on a held FD (dropped on death), defer = exit 0 + logged owner;
built in response to a measured two-brains-one-tree incident (fc7302d). Contention is
currently low: `wc -l data/cro_ai_logs/brain_mutex.log` → 7 lines total (2 on 07-30, 5
today).

**S5. Disposition capacity exists when aimed.** Ledger analysis (command in M1): 2026-07-30
saw 10 terminal dispositions + 18 scheduled stamps in one day — a 28-row triage burst. The
constraint is not ability; it is that nothing summons the ability (M2).

**S6. Self-origin gap-finding is sustained at volume.** `data/blind_spot_ledger.jsonl` →
73 rows; self-origin by day: 07-28: 10, 07-29: 6, 07-30: 14. The desk finds its own gaps
daily. (The principal-channel blindness of this same metric is M6.)

**S7. The 214-item blind-spot map has consumers.** `grep -rln blindspot_max scripts/ libs/`
→ daily_research_cycle.py, stage_a_executor.py, conversion_engine.py, blindspot_max.py —
unlike the stores in M2/M4, this queue is read by live organs.

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1. Whether "scheduled" converts.** 20 scheduled rows now exist; the disposition was used
at scale for the first time on 07-30. Zero historical scheduled→implemented transitions
exist to estimate a rate. First evidence arrives 2026-08-01 when 9 rows come due at once
(prediction P1, section 4).

**U2. Detection marginal yield.** Nobody measures what fraction of each day's sweep findings
are NEW vs re-findings of open items. Today's research-engine audit is explicitly a
"delta-and-depth" audit re-verifying yesterday (its lines 7–9); its rank-1 item from
yesterday is "day 5 open" (line 81), and "yesterday's O-5 stands, now with worse numbers"
(line 91). Re-detection is running but unpriced.

**U3. Brain-hours utilisation by organ.** The one-brain mutex makes brain time the desk's
scarce serial resource; no artifact allocates or even measures it by organ.
`tail data/cro_ai_logs/utilisation.log` → empty (check_utilisation.py was cron'd only at
02:40Z today via the manifest; its first scheduled artifact is pending). Until measured,
per L1.28a this utilisation counts as zero.

**U4. Doctrine→behavior compliance rates** (carried from 07-29 U3, unmoved): what fraction
of organ runs execute screen-on-discovery, log battery moves, run the novelty gate. Still
no measurement.

**U5. The assumptions inventory still does not exist** (carried from 07-29 U7/T7, unmoved):
`ls docs/research/ASSUMPTIONS.md` → No such file. The desk still cannot list its own
load-bearing assumptions; the kimchi timestamp kill remains the proof of what that costs.

**U6. P(synthesis rows a report's findings).** Sample size 2: the 07-29 synthesis rowed
nothing; the 07-30 one rowed 8. Selection rule unknown. Today's synthesis is the third
sample; this report's section 4 is written to be trivially rowable as the test.

**U7. Whether the audit's own value survives subtraction.** Nobody has computed what the
8×daily-max-effort sweep would need to convert per week to beat its brain-hours cost.
Unmeasurable until U2/U3 exist — which is why X8 builds them.

---

## FINDINGS (all six perspectives; feeds sections 3–4)

### M1 [INTERNAL — the trajectory, measured]. The desk implements what it finds in the same
session or almost never: cross-session repair capacity is ~0.6 rows/day against ~14/day arrivals.

The recommendation ledger, measured (`.venv/bin/python` over
`docs/research/recommendation_ledger.json`):

```
ARRIVALS by day:      07-26: 17 | 07-28: 15 | 07-29: 7 | 07-30: 30   (69 total, ~14/day)
TERMINAL by day:      07-26: 2  | 07-28: 2  | 07-29: 2 | 07-30: 10   (16 total, ~3.2/day)
SCHEDULED stamps:     07-30: 18 (plus 2 earlier)
OPEN:                 33, ALL past the 24h grace; oldest 4.7d
IMPLEMENTED ages:     R0014 0.0d, R0018 0.0d, R0021 0.0d, R0037 0.0d, R0038 0.0d,
                      R0061 0.0d, R0053/54/55 0.24d, R0036 1.26d, R0016 3.24d, R0017 3.67d
```

Nine of twelve implementations happened within ~6 hours of the row being raised; exactly
three rows in desk history crossed a session boundary before being implemented (R0016,
R0017, R0036); **no row older than 3.67 days has ever been implemented.** The undone stock
(open+scheduled) across the three meta-audit snapshots: 31 (07-29) → 41 (07-30) → 53
(07-31): **+10/day**. Today's 7 COMPLETE sibling audits (~310KB) have produced 0 rows so
far (arrivals-by-day shows no 07-31 entries) — the synthesis is the single remaining wire.

This is the charter's trajectory question answered: cycles improve what they touch
same-day (S1, S2), and everything handed to "later" decays at a measured hazard of roughly
zero. The audit system is a detection machine whose repair machine is an accident of
whichever session is standing nearby.

### M2 [INTERNAL — root cause of M1]. The cross-session repair path is missing at all three
places it could exist — and the desk's own "guaranteed implementation" law has no enforcer.

Verified one by one:
1. **Not in max_audit:** `grep -n "recommendation" scripts/max_audit.py` → 2 hits, both
   prose in comments; no check fires on undisposed/past-due R-rows. The §42 text calls them
   DEFECTS; no gate ever raises them to a cycle.
2. **Not in the §37 carry-over brief:** `tail data/carryover_sweeps.jsonl` → the carried ID
   namespace is max_audit gate names (`directive-overdue-*`, `clock-saturation`, …). No
   R-row has ever been carried. The one mechanism §37 provides for delivering work across
   sessions excludes the recommendation ledger entirely.
3. **Not in the cycle's order of operations:** `ops/run_cro_ai.sh` STEP 0–4 sequence
   (integrity → mechanical sweeps → GENERATION → triage/build → meta). The §42 duty text in
   that file binds cycles to *ledger what this cycle produces* — the produce side only.
   Working the existing backlog appears in no step. (Generation-first is correct law
   (L1.24); the conclusion is not "put the ledger first" but "give repair its own capacity"
   — X1/X3.)

The sharpest instance: `ops/run_cro_ai.sh` carries the principal's GUARANTEED
IMPLEMENTATION law — "any proposal ≥5 bps CAGR uplift is PERMANENTLY QUEUED and GUARANTEED
implementation … in strict EV-per-complexity order." R0026 (root-cause the −51.74 bps
price_pnl on delta-neutral round-trips) carries roi_bps=100 and has been open 2.3 days.
A 100-bps guaranteed row is sitting in a queue no organ reads. The guarantee is prose;
nothing tracks it.

### M3 [CONTRARIAN + INTERNAL — workflow persisting by habit, mechanized]. The "weekly"
audit became daily because a reconstruction script codified a crash loop as policy, and the
desk's own flow-control law (§33) was never generalized to its audit organs.

`ops/crontab.manifest:374-378`:

```
# deep cold-audit organ: header says weekly (ops/run_deep_sweep.sh:2) yet dated artifacts
# landed 07-26/07-28/07-29 (docs/research/deep_sweep/) and organ_catchup re-fires it as an
# owed organ -- so the live cadence is at least daily-rotating perspectives. Daily slot chosen.
# CONFIDENCE: inferred
0 1 * * * ... ops/run_deep_sweep.sh
```

The 07-26/07-28 artifacts it read as evidence of daily cadence were BRAIN_AUTH_FAILED crash
stubs and catch-up re-fires (the 07-30 meta-audit documented them; `ls -la` shows 48–494
byte files). The reconstitution inferred intent from pathology and wrote it into cron —
`CONFIDENCE: inferred`, installed 2026-07-31T02:40Z. The original weekly line survives too
(`crontab -l` line 34, Sun 04:00, `/tmp/deep_sweep.lock`) alongside the daily manifest line
82 (`data/.cron_deep_sweep.lock` — split locks; only the brain mutex prevents overlap).

No decision, ledger row, or measurement ever chose daily. The cost side is real: 8 auditors
× ~25–35 min × max effort ≈ 3–4.5 serial brain-hours/day (~15–19% of the mutex ceiling)
producing findings into a queue growing +10/day. And the desk already owns the correct
pattern for exactly this situation: §33 suspends NEW mining while dispositions are owed —
flow control written for mined finds, never generalized (battery move 6) to audit organs.
To be precise per gate-optimality symmetry: detection is still yielding genuine new finds
(data-moat today: "one live catch"; this report's M4/M5 are new) — the defect is not "too
much detection," it is unmetered cadence with zero backpressure and unpriced re-detection
(U2).

### M4 [INTERNAL — the recursive-improvement wire is cut in two places]. The synthesis
prompt routes findings into a store the desk already knows is write-only, and the audit
genome has not absorbed a single synthesis improvement.

`scripts/run_deep_sweep.py` synthesis prompt (lines ~190–212): "THEN: append the top
portfolio items as dated entries to **docs/research/improvement_inbox.md** … add ONE line
to data/PRINCIPAL_ACTION.md". The 07-29 meta-audit (M7) and the desk's operational record
both establish improvement_inbox.md as a written store nothing consumes. The one action
that made the 07-30 sweep convert — rowing R0053–R0060 into `scripts/recommendations.py` —
was the synthesis lead **exceeding its own instructions** (its prompt never mentions the
ledger; grep "recommendations" in the synthesis prompt → nothing). Institutional survival
currently depends on the organ disobeying its genome in the right direction.

Second cut: the doctrine header calls prompts "versioned software … improved recursively by
the meta-auditor." `git log --follow prompts/deep_sweep_core.txt` → last edit ae9e509
2026-07-28 11:51. The 07-29 and 07-30 syntheses both computed output (F) — concrete genome
improvements, including "instruct the synthesis lead to row into scripts/recommendations.py"
verbatim (20260730_SYNTHESIS.md:450) — and no edit followed. (F) has no consumer. The audit
improves everything except itself.

### M5 [INTERNAL — doctrine genome integrity]. Every organ has now been taught a retracted
result for 8 days; the fix is parked behind a due date while the falsehood compounds, and
the doctrine's own bloat guard has been red for 4 days.

- `grep -n kimchi ops/principal_doctrine.txt` → line 89 still recites "IC +0.148 and
  momentum timing Sharpe 1.3 — beating every price-only sleeve" as the proving evidence of
  SCREEN-ON-DISCOVERY; line 275 (L1.11a) doubles down: "kimchi (KR) real". `grep -n retract`
  → no marker anywhere. The retraction landed 2026-07-29 (rm-20260729T111104, commit
  02f2917); this report's own injected system prompt still carries both claims — the
  auditor writing this paragraph was taught the falsehood this morning.
- Ledger state: R0059 (deep_sweep, roi=6000) REJECTED as "DUPLICATE of R0051 … which
  already owns ops/principal_doctrine.txt:89" — correct dedup discipline, but R0051 is
  `scheduled due=2026-08-01` with measured cross-session μ≈0.6/day (M1). A one-line prose
  edit correcting the desk's central strategic narrative has waited behind a due date for
  two days.
- R0002 (doctrine bloat: 27k chars vs its own 16k guard) — `scheduled due=2026-07-27`,
  now 4 days past due, flagged `SCHEDULED past due` in every report since. The genome
  injected into every organ run fails its own guard and the failure is normalized.
- Note the compounding interaction: axis freed (kimchi is out of the forward cohort —
  `data/axis_shadow_state.json` → 3 axes, none kimchi), doctrine not — so organs are still
  being steered toward an evidence base the validation layer already burned. The 07-31
  alpha-discovery audit holds the slot-accounting piece (m_concurrent=11 vs 3 live axes).

### M6 [INTERNAL — misleading metric]. The principal-origin gauge still cannot see its own
signal: ≥6 principal doctrine orders since 07-26, zero principal-origin rows logged.

`data/blind_spot_ledger.jsonl` by day/origin: principal 12 (07-22), 2 (07-24), **0 since**
— across the very window in which the principal delivered the UNIVERSAL DUTY SET (07-26),
L1.24–L1.27 + L2.9/L2.10 (07-29), L1.11a/L1.16a (07-29), L1.0 ratchet (07-29), capacity
parity L1.18a (07-30), L1.21a (07-30), L1.28/L1.28a (07-30). Each order names gaps the desk
had not found ("closes the desk's oldest leak", "correcting a live misreading"). Doctrine-
channel principal finds bypass `scripts/blind_spot.py` entirely, so the metric defined as
THE failure signal reads green while the failure occurs. Found 07-29 (M5), still unfixed,
and unrowed because the finder was read-only — the M1/M2 mechanism eating its own detector.

### M7 [CONTRARIAN — misleading metrics, two more]. The ledger's priority field mixes
fabricated ordinals with measured basis points, and "scheduled" has silently become a
deferral instrument whose first stress test is tomorrow.

- roi_bps: R0053–R0060 carry 9999/9000/8000/7500/7000/6500/6000/5500 — descending
  rank-encoding cosplaying as basis points — while cycle rows carry measured 5–120. Any
  roi-sorted triage across sources is meaningless; the 100-bps R0026 (real money, measured)
  sorts below five rank-encoded audit items.
- The 07-30 triage burst (S5) resolved 18 rows by scheduling: due dates 2026-08-01 ×9,
  08-02 ×5, 08-03..06 ×5 (`recommendations.py` scheduled list). Scheduled is a legitimate
  §42 disposition — but at measured cross-session μ≈0.6/day, 9 rows due tomorrow is a
  predictable mass past-due event, i.e., debt moved one column right. Registered as
  falsifiable prediction P1 (section 4).
- Headline "12/69 implemented = 17%" overstates the system property that matters: for a
  finding that outlives its session, P(implemented) ≈ 3/57 ≈ 5%.

### M8 [BLIND-SPOT TRANSFER — OPERATIONS RESEARCH / QUEUEING THEORY]. The meta-layer is an
unstable queue: λ/μ ≈ 4, no aging, no WIP cap, no admission dedup — and OR names each
standard remedy the desk already half-owns.

With arrivals λ≈14/day and terminal service μ≈3.2/day (M1), utilization ρ≈4: Little's law
says work-in-progress and waiting time grow without bound, matching the measured +10/day
stock growth and the never-implemented-past-3.7d record. Service discipline is effectively
newest-loudest-first with no aging — starvation of the tail is structural, not moral.
Standard remedies, mapped to what exists:
  (a) **WIP cap / backpressure** — §33 already implements this for mining
  (`data/mining_suspended`); generalize to audit organs: open+past-due > K flips the next
  sweep window into repair mode (X3).
  (b) **Aging** — priority escalates with wait time so the tail cannot starve; trivially,
  effective_priority = roi_rank × age_days (X7).
  (c) **Dedicated server capacity** — μ must be owned by an organ, not volunteered.
  (X1: put R-rows in the §37 brief; or a standing repair slot.)
  (d) **Admission control / dedup on arrival** — three duplicate pairs entered in 69 rows
  (R0023/R0034, R0040/R0044, R0051/R0059; one caught only at rejection). The desk built
  `hypothesis_novelty` to stop re-testing dead hypotheses and never generalized it
  (battery move 6) to its own recommendation queue (X2 includes it).
The transfer's one-line summary: the desk has been treating a capacity problem as a
discipline problem. Queueing theory says with ρ≈4, exhortation cannot work — only capacity,
caps, or admission control can.

### M9 [FRONTIER]. Structured (schema-forced) findings became free capability and would
mechanize the entire finding→row wire; meanwhile the repo's frontier methods keep dying
unwired — the desk's frontier gap is wiring, not knowledge.

The desk auto-upgrades models with no human in the loop (`git log` a83fb4d
"models: auto-upgrade to newer flagships"; scripts/run_model_upgrade.py --apply in cron).
Current-generation models emit schema-validated JSON reliably; auditors could emit findings
as structured rows alongside prose, making R0056's parser unnecessary — rowing becomes a
file append, dedup becomes a field match. Nothing in the runner exploits this. The
established pattern this repeats: R0001 (CPCV/SPA/FDR/lockbox "exists but is never called",
scheduled 08-03), the quarantined anytime-valid module vs the measured ×4.9 Stage-B peeking
inflation (07-31 validation-stats audit — an L1.16a named-enabling-change resurrection
candidate), the free options-VRP unlock (07-31 alpha-discovery audit). Methods enter the
repo faster than wires leave it — same λ≫μ signature as M1, one layer down.

### M10 [GREENFIELD]. Rebuilt from scratch: ONE work queue with N views — and the evidence
this week says the R-ledger is winning de facto, so finish the consolidation instead of
maintaining five stores.

Carried from 07-29 M7 with new evidence: sweep findings now flow to the ledger (16
deep_sweep rows), while improvement_inbox.md remains a prompt-mandated dead drop (M4),
GAP_REGISTER/panel_inbox/carryover carry disjoint ID spaces (M2.2), and duplicates enter
across stores (M7). Greenfield design: one queue, one schema (source, ERV, owner, SLA,
disposition), max_audit gates and R-rows in ONE namespace so §37 carries everything; views
for the register/inbox use cases. Historical-baggage score: high; replaceability: high;
the migration is mostly deletion.

### M11 [EXTERNAL]. A world-class desk manages repair like an SRE org: MTTR and P(fix) per
finding class are first-class, floored, fenced metrics. This desk computed them for the
first time in this report.

Computed above (M1): median time-to-implement (when it happens) ≈ same-session; P(fix |
survived first session) ≈ 5%; stock growth +10/day. None of these numbers existed anywhere
before this audit; none has a floor artifact or fence. Under L1.0 a metric first measured
must be born with its floor and fence in the same commit — X4.

### M12 [FUTURE — 2–3y redesign]. Continuous event-driven micro-verification with a repair
fleet sized to keep ρ<1, replacing the daily monolith.

With cheap abundant agents: (a) audits trigger on diffs, artifact staleness, and gate
flips, not on a clock; (b) every finding is a structured row at birth (M9); (c) a repair
fleet consumes the queue continuously in worktree isolation, sized against measured λ so
ρ<1 is a design constraint, not a hope; (d) detection cadence auto-tunes to marginal new-
finding yield (U2). Every component has a present-day seed in X1–X8.

**Perspective coverage:** INTERNAL M1/M2/M4/M5/M6; EXTERNAL M11; FUTURE M12; CONTRARIAN
M3/M7; GREENFIELD M10; FRONTIER M9; TRANSFER M8. **Negative-space sweep:** no MTTR/P(fix)
metric (M11), no detection marginal-yield metric (U2), no brain-hours-by-organ artifact
(U3), no assumptions inventory (U5, carried 3rd audit running), R-ledger absent from all
three cross-session surfaces (M2), no admission dedup (M8d), synthesis output (F) has no
consumer (M4). **Institutional curiosity:** organ stub-death/deferral is normalized weather
(brain_env.sh's own comment: "7 stub-deaths/48h"; mutex defer is silent-by-design exit 0 —
honest, but no one audits deferral rates yet at 7 log lines); rejected-now-unlockable
capabilities: anytime-valid (enabling change: measured ×4.9 peeking inflation) and options
VRP (enabling change per 07-31 alpha-discovery) — both legitimate L1.16a re-opens with
named changes. **Battery moves run:** adjacency (M2→guarantee law; M8d→novelty gate
generalization), config-vs-outcome (M4 synthesis prompt vs behavior; M6 gauge vs channel),
regression sweep (M3: what the cadence-max/reconstitution change made worse), generalise-
the-rule (§33→audits, hypothesis_novelty→queue), ratchet check (M11: metrics born unfloored),
negative space (list above), scope-the-negative-result (M3: detection still yields — the
defect is unmetered cadence, not detection itself). Contingency and cost-inversion produced
nothing beyond sibling coverage — stated per the no-silent-skip rule.

---

## 3. WHAT COULD MATTER MOST (ranked by impact × confidence / (cost × maintenance))

1. **Give repair a standing consumer (M1/M2), cheapest wire first: put the top-10 open/due
   R-rows into the §37 carry-over brief** (one edit in libs/ops/carryover or
   carryover_brief.py) **and add the missing max_audit gate** (`recommendations-undisposed`
   / `-past-due`). COMPOUNDING MULTIPLIER: raises P(action) for every future finding from
   every organ. Cost: hours.
2. **Fix the synthesis prompt today (M4):** replace the improvement_inbox.md instruction
   with `scripts/recommendations.py add --source deep_sweep-<dim>` + dedup-against-open
   duty; implement existing R0056 (auto-row parser) as the mechanical backstop; adopt
   structured findings (M9) when convenient. COMPOUNDING MULTIPLIER.
3. **Audit backpressure, §33-generalized (M3/M8a):** open+past-due > K ⇒ next sweep window
   runs repair-mode (write-enabled, worktree-isolated, consuming own-dimension rows
   highest-roi-first) until under K. Constitution-consistent: conversion scales UP using
   the same slots; detection capacity is never permanently cut.
4. **Correct the doctrine NOW (M5):** line 89 retraction marker + line 275, and the R0002
   bloat fix — these are prose edits gated behind due dates while every organ mis-learns
   daily. Then T3-0729's claims manifest so the class dies (doctrine-claim-stale check).
5. **MTTR / P(fix) / stock-growth as ratchet metrics (M11):** compute from the ledger
   (this report's commands), floor + fence in the same commit per L1.0.
6. **Cadence by measured yield (M3/U2):** tag each sweep finding new-vs-repeat; publish
   marginal new-finding yield and brain-hours by organ (U3); decide daily-vs-weekly from
   the artifact, replacing `CONFIDENCE: inferred` with a decision. Also collapse the dual
   cron entries (line 34 vs 82).
7. **Aging + roi normalization (M7/M8b):** age-escalating effective priority; split
   roi_bps into measured-bps vs rank fields.
8. **Principal-doctrine auto-logging (M6):** any diff to ops/principal_doctrine.txt logs an
   origin=principal blind-spot row automatically; restores the failure-signal metric.

Interactions: 1↔3 (both add μ; 1 is the wire, 3 is the capacity), 2 feeds 1's queue
cleanly, 5 is the gauge that proves 1–3 worked, 6 prices what 3 regulates, 4 is
independent and same-day-able.

## 4. WHAT WE TEST NEXT (concrete, success criteria, retirement conditions)

_Read-only constraint: this auditor cannot row. SYNTHESIS LEAD: rows X1, X3, X4, X6, X8
are NEW (no existing row — verified against all 69 summaries); X2=R0056, X5=R0051+R0002,
X7 extends R-ledger schema. Do not duplicate the existing rows — implement or re-date them._

- **X1 (M2):** §37 brief includes top-10 open/past-due R-rows + max_audit gate
  `recommendations-past-due`. Success: ≥3 cross-session implementations within 7 days;
  implemented-age distribution grows a tail past 1 day. Retire: never (it is the wire).
- **X2 (M4/M9, = existing R0056):** synthesis prompt rows to the ledger; parser backstop;
  admission dedup against open rows (generalize hypothesis_novelty). Success: 100% of
  COMPLETE sweep reports produce ≥1 row same-day; duplicate admission rate → 0.
- **X3 (M3/M8):** repair-mode flip at open+past-due > 25. Success: ρ (7d rolling
  arrivals/terminal) < 1 within two weeks; stock stops growing. Failure mode: repair-mode
  starves detection of a genuinely new critical — mitigate: integrity-watch class exempt.
- **X4 (M11):** data/repair_metrics.json {MTTR_median, P_fix_after_session, stock_growth}
  + fence, floors born same commit. Success: check fires on regression; numbers appear in
  cycle reports.
- **X5 (M5, = existing R0051 + R0002):** doctrine line 89 retraction + line 275 + bloat
  fix, TODAY, not on the due date; then claims manifest (T3-0729) with kimchi as row 1.
  Success: `grep -n "IC +0.148" ops/principal_doctrine.txt` returns only a retraction-
  marked line; a seeded stale claim fires within one audit cycle.
- **X6 (M6):** principal_doctrine.txt diff → auto blind-spot row origin=principal.
  Success: next principal order produces a row with no human action.
- **X7 (M7):** roi field split + age escalator. Success: no open row crosses 7d without
  an escalation artifact.
- **X8 (M3/U2/U3):** per-sweep new-vs-repeat tagging + brain-hours-by-organ from
  brain_mutex.log & run logs; cadence decision recorded with evidence. Success: the
  manifest's deep-sweep line cites a measured yield, not `CONFIDENCE: inferred`.
- **P1 (prediction, M7/U1):** Of the 9 rows due 2026-08-01, ≥6 will be past-due on
  2026-08-02 unless X1 or X3 lands first. Whoever reads this on 08-02: check
  `scripts/recommendations.py report` and log the outcome against this prediction —
  either result calibrates the queue model this report is built on.

_Owed by this read-only run, for the next live cycle: blind_spot.py rows for M4 (self,
config-vs-outcome), M6 (self, metric-blindness); research_memory.py log row for the M1
measurement (category: meta, negative-and-positive)._

---

**Trajectory verdict (charter question):** improving where sessions touch (sentinel
grading, synthesis, mutex, first rowing — all inside 48h), flat-to-degrading where work
must cross sessions (T-scan 07-29→07-31: ~1.5/8 moved; stock +10/day; doctrine falsehood
8 days). The system's next-strongest move is not another finding — all eight of this
report's opportunities are μ-side for exactly that reason.

_Report complete: 12 findings (M1–M12), 7 strengths, 7 ignorance-ledger rows, 8 ranked
opportunities, 8 experiments + 1 registered prediction, all command-cited. Sentinel flipped
as the final edit of this run._
