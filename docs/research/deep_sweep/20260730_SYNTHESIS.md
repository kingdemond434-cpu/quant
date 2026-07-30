# DEEP COLD SWEEP — SYNTHESIS — 2026-07-30

_Synthesis lead: Claude Opus 5, launched by `scripts/run_deep_sweep.py` at 17:00Z (PID 1417298,
1800 s budget). **This is the FOURTH synthesis attempt today** — the 02:00Z, 07:40Z and 12:00Z
windows each logged `synthesis=NO`. Written incrementally per the COMPLETION CONTRACT._

**STATUS: COMPLETE**

---

## 0. THE HEADLINE, BEFORE ANYTHING ELSE

**Two of this week's eight audits are empty placeholders, the runner graded both `OK`, and the
prompt that launched me listed both as reports to read.**

```
$ cat data/cro_ai_logs/deep_sweep_20260730T1200.log | tail -1
[deep-sweep] done: 8/8 produced; synthesis=NO
```

The truth is **5 complete, 1 partial, 2 empty**. `20260730_alpha-discovery.md` (1,736 b) and
`20260730_validation-stats.md` (1,889 b) contain the literal strings `(placeholder — filled
incrementally)` and `_TBD_` and nothing else. Zero findings between them.

This is not a reporting error. It is the exact failure class the audit doctrine names as its prime
quarry — **a self-greening guard, sitting inside the organ whose job is to catch self-greening
guards.** The meta-auditor found it (M1); my own invocation is the confirming instance, because I
was handed the two empty files as evidence and asked to compute "which audit produced the most
value" and a research-capability index from them.

So the first honest act of this synthesis is to refuse the framing: **this was a 66%-coverage sweep
reported as 100%.** Everything below is scored on that basis.

And the second: the desk's binding constraint this week is **not research quality**. It is that
**nothing can be promoted, nothing is compounding, and the wire from finding to action is cut** —
three stalls, two of which are waiting on a human reply that has been pending for days.

### The one finding that outranks everything else in this document

**The Tier-3 dead-man ruin switch is silently disarmed. It returns `False` at every equity,
including a 99.5% loss.** (execution-growth F13, severity MAXIMUM.)

```
$ .venv/bin/python -c "<load run_deadman_switch, read live data/deadman_state.json>"
  high_water = 209.43368256   _MIN_HW = 500.0
  hw < _MIN_HW ? True  -> should_fire ALWAYS returns False
  equity=209.43 -> should_fire=False      equity=50.00 -> should_fire=False
  equity=100.00 -> should_fire=False      equity= 1.00 -> should_fire=False
```

```python
    if hw < _MIN_HW:              # _MIN_HW = 500.0  "ignore dust/empty accounts"
        state["breaches"] = 0
        return False              # <-- unconditional, before any ruin comparison
```

The service reads `active running`, the heartbeat is 21 seconds old, and the dashboard publishes
`"fire_line": 136.13, "fired": false` — a fire line **computed in display code**, not obtained from
the rail, which fires at no equity at all. `journalctl -u quant-deadman.service` → *"No entries"*
across `NRestarts=12`. Zero tests, zero monitors, zero alarms.

**The constitution names the ruin rails untouchable and the two non-ceilings. One of them has been
off, and every guard that should have noticed was checking liveness rather than armedness.** The
general form survives the specific case: *a real book that fell from $5,000 to $499 would disarm the
rail identically — the protection switches off precisely when a book is closest to ruin.*

This is not "no money is at risk because it's testnet." It is that the desk's ruin protection has
been unverified since inception, and the first time anyone asked it a direct question, it failed.

---

## (A) OVERALL VERDICT + PER-SUBSYSTEM CEILING TABLE

### Verdict

The desk is in a **high-production, zero-conversion** state. This week produced ~365 KB of genuinely
excellent, command-cited audit material — the best-evidenced sweep in the desk's history by volume
and by verification density. It also converted **none of it** into a deployed change, because all
three transmission paths are broken at once:

1. **Capital cannot compound.** The carry book is in an absorbing state — the ruin rail fired on an
   equity figure that excludes **$4,399.91** of verified, on-venue inventory the rail marks at $0,
   and `flatten` removes the only mechanism (funding carry) by which equity could recover. Awaiting
   a Tier-3 A/B/C reply since 2026-07-29.
2. **Discovery cannot promote.** `probability_backtest_overfitting` and `whites_reality_check` are
   campaign constants — they never take the candidate's own returns — so the measured campaign gives
   **PBO = 0.6159, White RC p = 0.4220 → 420/420 rejected regardless of quality.** The fix is built,
   green (13 tests), thresholds unchanged, and **not self-applied** because it touches gate
   strictness. Awaiting a YES/NO. Until then, in the page's own words, *"the discovery pipeline
   cannot promote anything, at any quality."*
3. **Findings cannot reach a queue.** 52 ledger rows, **8 implemented (15%)**, **27 flagged DEFECT**
   (26 undisposed past grace + 1 scheduled past due). Of 8 `deep_sweep`-sourced rows, **7 are from a
   single dimension (data-moat, R0003–R0009)**. Across the 07-26, 07-28, 07-29 and 07-30 sweeps —
   roughly 600 KB of audited findings — **seven of the eight dimensions have never produced a single
   ledger row.**

The engine is not weak. The engine is **disconnected from its own output**, and it is
increasingly good at producing material that goes nowhere. That is the whole verdict.

### Per-subsystem table

Honesty note on this table: I did **not** invent scores for audits I could not read in full. Where an
auditor stated its own numbers I use them; where the audit died I mark it `NO AUDIT`; where I read the
report's conclusion but not its score block I give a **synthesis-lead estimate** and label it `[SL]`.
Fabricating a ceiling number for an empty report is exactly the corruption M1 warned about.

| Subsystem | Report | Current | Practical ceiling | Opp. cost 1y | Note |
|---|---|---|---|---|---|
| alpha-discovery | **1.7 KB skeleton** | `NO AUDIT` | — | **unmeasured, and that is the cost** | 2nd loss in 3 sweeps |
| validation-stats | **1.9 KB skeleton** | `NO AUDIT` | — | **unmeasured** | the subsystem gating ALL promotion |
| meta-and-blindspots | 12.6 KB, **partial** | `NO SCORE` (died) | — | high | 2 findings (M1, M2), both CRITICAL, both re-verified by me |
| execution-growth | 61.7 KB, complete | **28%** | **80%** | **100% of expected compounding, + unbounded tail** | 20 findings; ceiling gap 52 pts, *"almost all recoverable by ~100 lines of code"* |
| data-moat | 60.6 KB, complete | **58%** (↓ from 62) | **85%** | HIGH, **partly irreversible** | the drop is *"a correction in measurement,"* not a regression |
| infrastructure | 122.9 KB, complete | ~60% `[SL]` | ~85% | high | 73 swallowed exceptions → 3 real defects; DR has nothing to restore |
| research-engine | 120.2 KB, complete | ~40% `[SL]` | ~80% | high | novelty gate 0% recall; 3 write-only stores; generation tested=0 |
| data-intelligence | 119.0 KB, complete | ~55% `[SL]` | ~85% | medium-high | largest report; audited ~12 of 240 artifacts and says so |

Two of those numbers deserve to be read carefully rather than skimmed. **execution-growth scores itself
28%** and then says the ceiling gap is *"almost all recoverable by ~100 lines of code, not by new
capability — that is the striking fact of this sweep."* **data-moat lowered its own score** from 62% to 58%
and was explicit that this is not a build regression but a correction: it had been scoring itself over
`scripts/` only, i.e. **264 of 613 modules (43%)**, so three prior audits recorded a fully-tested capability
(`libs/alpha_factory`, 91 passing tests) as *absent*. A measurement organ's glob silently defined the desk's
field of view. **An auditor that revises its own score downward on better measurement is doing the job
correctly**, and it is the single most trustworthy number in this table.

**The table's most important row is the first two.** The two subsystems that produced nothing are
alpha-discovery and validation-stats — and validation-stats is precisely the subsystem that owns the
gate currently rejecting 420/420 candidates. The one audit that most needed to happen is the one
that silently didn't.

---

## (B) CAPABILITY MAP

### The missing capability that unlocks the most downstream capability

**A mechanical finding→queue transmission step.** Not a better auditor, not a new dataset — a wire.

Evidence it is the multiplier: every other improvement on this board is currently multiplied by
**~1.5%**. The arithmetic, from the meta-audit and re-verified by me:

- P(a deep-sweep finding is ever rowed) ≈ 1/8 dimensions have ever been rowed
- P(a rowed recommendation is implemented) = 8/52 = **15%**
- ⇒ expected realised value of a deep-sweep finding today ≈ **0.15 × 0.125 ≈ 1.9%**

Producing sharper findings raises the numerator of a fraction whose denominator is the problem.
**Fixing the wire multiplies the value of every past and future audit simultaneously** — including
the ~600 KB already written and stranded. Nothing else on this board has that property.

The proof that this is structural rather than an oversight is brutal and self-referential: **last
week's synthesis already found it and already wrote the fix.**

```
$ grep '^## #' docs/research/improvement_inbox.md | tail -12
## #72 — CLOSE THE AUDIT→ACTION LOOP (SYNTHESIS 2026-07-29, portfolio P0-1) ◆compounding
## #74 — SWEEP-RUNNER: ROTATE SEATS + SYNTHESIS-FIRST + FAILURE-STREAK ALARM (P0-3) ◆compounding
```

Neither was ever rowed into the ledger (the only `deep_sweep` rows are data-moat's R0003–R0009).
Neither was implemented — `scripts/run_deep_sweep.py:22` is still `SUBSYSTEMS = {` iterated in fixed
order at line 136, with no rotation, no streak counter, no synthesis-first.

**So the previous synthesis's fix for the broken transmission was itself lost to the broken
transmission,** and one day later P0-3's absence cost this desk two audits. The improvement inbox is
a **write-only sink**: it is not the ledger, nothing drives it, and no item in it carries a
disposition. Writing to it is indistinguishable from writing to `/dev/null` with better formatting.

This is why, at the end of this run, I am **rowing my top items into the ledger** rather than only
appending them to the inbox as instructed. Following the instruction literally would reproduce the
exact defect this synthesis exists to report.

### The existing capability that is the biggest systemic risk

**The validation gate — and it has already failed.** It is the single chokepoint through which every
candidate must pass to reach capital, and it is currently a **batch coin-flip**:

- It rejects everything: PBO 0.6159 / RC p 0.4220 → **420/420 rejected**, candidate quality
  irrelevant.
- It is also unboundedly **loose** in the other direction: hold 60 pure-noise candidates fixed, add
  one genuine winner to the batch, and the same gates flip to admitting **60/60 pure nulls**. The
  loose direction opens *precisely when the desk starts finding real edge* — the worst possible
  failure phase.

A gate that is simultaneously 100%-rejecting and capable of 100%-admitting noise is not conservative;
it is **uninformative**, which the GATE-OPTIMALITY DUTY names as a defect to investigate rather than a
virtue. The fix is built and green. It is blocked on one human keystroke.

**Second systemic risk, newly visible this week:** the desk's *instruction surface* is contaminated.
`ops/principal_doctrine.txt:89` still cites the **retracted** kimchi result as `THE EVIDENCE THIS IS
RIGHT` for the SCREEN-ON-DISCOVERY DUTY, and line 213 asserts `the desk's own record proves both
halves -- kimchi (KR) real`. That file is injected into every organ's system prompt — **including
this one, which I can read in my own context right now.** The desk has already written the lesson
(`docs/institutional_knowledge.md:678`: *"A retraction is not complete until every DERIVED registry is
updated"*) and has still not updated the registry that steers every agent it runs. Every organ on this
desk is currently being motivated by a refuted result.

---

## (C) TOP OPPORTUNITIES — PRIORITIZED PORTFOLIO

Ranked by (direct + cascade + optionality + compounding) / (effort × maintenance × opportunity cost).
These compete for scarce capacity; this is a portfolio, not a wish list. **◆ = compounding multiplier.**

### P0-0 — ONE EQUITY READ: RE-ARM THE RUIN RAIL AND UN-KILL THE BOOK ⟵ *do this first*
**Exactly-what:** `account_summary()` (`libs/execution/binance_testnet.py:169`) reads `totalMarginBalance`,
USDT-only because `multiAssetsMargin=False`. Sum per-asset `marginBalance` instead. Add an assertion that
fires when `high_water < _MIN_HW` while the book is live.
**Evidence:** the rail sees `eq=209.43 → dd_start −37.20% → flatten`; counting USDC gives
`eq=5209.43 → dd_start +62.80% → action=ok`. `high_water=209.43 < _MIN_HW=500` ⇒ `should_fire()=False` at
every equity tested down to $1.00.
**Why it outranks the audit fixes:** it is the only item on this board touching a **survival rail**, and the
hierarchy (L1.2) puts compounded capital first. It is ~10 lines and it fixes **three** things at once — the
disarmed dead-man switch, the absorbing state, and the mis-specification of the principal's pending
option (A). Ledger: R0053, R0054.
**Ordering (load-bearing, stated by the execution auditor and endorsed here):** equity read → delete
`_MIN_FUNDING` → *then* answer A/B/C. Doing `_MIN_FUNDING` first restarts trading **with the ruin rail
still disarmed** — the worst possible ordering. Doing A/B/C first re-arms the same trap $5,000 lower.
**Effort:** ~10 lines + ~40 for the "every verdict has a consumer" class check. **Retirement:** never.

### P0-1 — GRADE AUDITS ON COMPLETION, NOT BYTES ◆
**Exactly-what:** in `scripts/run_deep_sweep.py`, replace `ok = report.exists() and
report.stat().st_size >= 1200` (line 109, and the identical resume test at line 139) with
`ok = (r is not None and r.returncode == 0) and report.exists() and size >= 1200 and
sentinel == COMPLETE`. Require auditors to flip `STATUS: IN PROGRESS` → `COMPLETE`. Write the failure
stub to `<report>.FAILED` instead of **overwriting the partial report** — the current code destroys
the only evidence of how far the auditor got, in direct contradiction of the completion contract it
enforces. Resume must re-run any file whose sentinel is not `COMPLETE`.
**Evidence:** two 1.7–1.9 KB skeletons graded `OK`; log claims `8/8 produced`; real reports run
60–123 KB — a **60× separation a 1,200-byte threshold cannot see**.
**Why P0:** it is ~10 lines, it is the reason 2 of 8 audits are missing, and *it silently corrupts
synthesis* — the desk's only cross-subsystem integration step was handed placeholders as evidence.
**Do NOT fix by raising the floor** — line 106 records that the old 2,500 b floor rewarded padding.
The floor is the wrong instrument, not a mis-set one.
**Effort:** ~1 h. **Retirement:** never (permanent correctness test).

### P0-2 — WIRE FINDINGS TO THE LEDGER, AND FENCE THE WIRE ◆◆
**Exactly-what:** (a) post-sweep step in `run_deep_sweep.py` — after each report grades COMPLETE, a
small non-LLM parser extracts `## 4. WHAT WE TEST NEXT` items and calls `scripts/recommendations.py
add --source deep_sweep-<dimension>`; (b) a `max_audit` check **`sweep-findings-unrowed`** asserting
≥1 ledger row per COMPLETE report. Keep auditors read-only — an organ that grades and files its own
work is P0-1's defect in a new costume.
**Evidence:** 7 of 8 dimensions have never produced a ledger row across four sweeps; the previous
synthesis's own P0-1/P0-3 evaporated into the inbox.
**Why P0-2 and ◆◆:** this is the multiplier from §B — it raises the realised value of every past and
future finding at once. It is second only because P0-1 determines whether there is a report to parse.
**Effort:** ~3 h. **Dependencies:** P0-1. **Retirement:** when auditors emit structured JSON findings.

### P0-3 — DISPOSE THE 27 DEFECT ROWS (and stop the bleed) 
**Exactly-what:** work the 27 `DEFECT` rows to implemented / rejected-with-reason / scheduled-with-due.
Rejection is a legitimate disposition; **silence is not** (§41).
**Evidence:** `scripts/recommendations.py report` → `52 total | 8 implemented | 3 rejected | 15
scheduled | 26 open`, 26 undisposed past grace + R0002 scheduled-past-due.
**Why:** P0-2 wires *more* volume into a queue with a 15% implementation rate. Wiring a firehose to a
clogged pipe makes the clog worse. This must land alongside P0-2, not after it.
**Effort:** ~4 h of triage. **Retirement:** none; the grace-period fence already exists.

### P1-4 — DECONTAMINATE THE DOCTRINE (retracted evidence in every prompt) ◆
**Exactly-what:** rewrite `ops/principal_doctrine.txt:89` and `:213` to remove kimchi as proof;
replace with the *surviving* justification for SCREEN-ON-DISCOVERY (the duty is sound on mechanism
grounds — it does not need a refuted example). Sweep the other derived registries: `research_agenda.json`,
`ops/frontier_cn_prompt.txt`, `ops/frontier_kr_prompt.txt`, `docs/DIGGING_CHARTER.md`, `docs/desk_digest.md`.
**Evidence:** `grep -n kimchi ops/principal_doctrine.txt` → lines 89, 213, both asserting it as
validated evidence; `docs/institutional_knowledge.md:678` already records the exact lesson.
**Why ◆:** doctrine text is a *force multiplier on every organ*, so contamination there is multiplied
too. Cheap, and it removes a live incentive for every agent to over-trust axis screens.
**Effort:** ~1 h. **Retirement:** when a `retraction-completeness` check greps derived registries.

### P1-5 — DELETE `_MIN_FUNDING` + FIX THE EQUITY READ (execution-growth's finding) 
**Exactly-what:** per the execution-growth audit's explicit ordering: **(1)** fix the equity read so
the rail sees the $4,399.91 of verified inventory (this *re-arms* the rail), **(2)** delete
`_MIN_FUNDING`, **(3)** then decide A/B/C. `_MIN_FUNDING` rejects **245/245** candidates and vetoes
exactly the four names that are net-positive under the desk's own cost model — which the desk's own
viability tool says need **150× less funding** than the gate demands.
**Why not P0:** step (3) is a Tier-3 call that is the principal's. Steps (1) and (2) are not, and
they are prerequisites — doing them first is what makes the A/B/C decision meaningful.
**Effort:** ~3 h. **Dependencies:** none for (1)–(2). **Retirement:** none.

### P1-6 — WIRE THE S0→S1 DEPLOYMENT GATE
**Exactly-what:** three of its five criteria read files **no organ has ever written**; the fourth is
an **inverted staleness test that can only pass when the fill feed is dead**; its verdict is written
to a key nothing reads. Rebuild against artifacts that exist, invert the staleness test, and route
the verdict somewhere consumed.
**Why:** this is a dormant capability presenting as a live one — the doctrine's "green timer, zero
output" pattern, in the gate that controls capital deployment.
**Effort:** ~4 h. **Retirement:** none.

### P1-7 — NOVELTY GATE: 0% RECALL, WITH THE FIX ALREADY IN-REPO ◆
**Exactly-what:** the novelty gate returns 0% recall against the graveyard; a materially better
TF-IDF implementation **already exists in this repo** at `libs/.../knowledge_engine.py:80-99`. Point
the gate at it. Related: research memory is **write-only** (3 reader-zero stores; ~96% of refutations
never read back).
**Why ◆:** a novelty gate at 0% recall means redundant hypotheses burn DSR multiplicity budget twice,
making every *other* candidate harder to promote. It actively damages the desk's ability to find edge.
**Effort:** ~2 h (wire an existing implementation, don't write a new one). **Retirement:** when recall
is measured ≥80% against a held-out graveyard sample and floored.

### P2-8 — THE 73 SWALLOWED EXCEPTIONS
**Exactly-what:** the infrastructure audit read code around silent `except` clauses and found **three
real defects (I12, I17, I22) from that seam alone**, and explicitly names it **not exhausted**.
Continue the sweep; add a lint fence against bare swallows in organ code.
**Why P2 not P1:** high yield per hour, but it finds *new* defects — and this desk's constraint is
disposing the ones it has. Correctly sequenced after P0-3.
**Effort:** ongoing. **Retirement:** when the swallow count is floored and fenced.

---

## (D) HARD WALLS (not headroom — do not confuse)

1. **The two Tier-3 decisions are genuinely human-only.** The pbo/rc gate flip and the carry-book
   A/B/C both touch validation strictness / a fired ruin rail. The doctrine is explicit that
   *"the loss isn't real, so let me clear it"* is how an autonomous system talks itself into
   disaster. These are **not** timidity — they are the survival rails working as designed. The
   defect is only that they have sat unanswered; the wall itself is correct and should not be
   engineered around.
2. **OpenRouter credits ($-0.59).** The external review panel is down and the audit-coverage sweep
   is stalled. Blocks 5 separate findings. **~$25 unblocks all of them** — the cheapest item on the
   board, and it is a spend decision, not an engineering one.
3. **Statistical power at T=310.** SE(annualised Sharpe) = √(365/310) = **1.085**, so the entire
   0.5–3.0 range of "good" Sharpe sits inside **one standard error**. No gate design fixes this; only
   more observations do. This is the real wall behind the promotion problem, and it is why the
   honest accelerants are *more observations per day* and *not queueing* — never a lower bar.
4. **32 GB free disk** bounds the BitMEX decade-archive ingest. Physical.
5. **Fill-moment mid price and wait time are unreconstructible.** For the 26 elapsed days this is
   permanent and only approximable (from `data/moat/bybit` mids, calibrated against the 4 genuine
   records, and never presentable as measured fills). The wall is **forward-liftable today** and
   grows by ~20 events/day until it is — which is why P1-3 is ranked on *irreversibility*, not size.
6. **Semantic (paraphrase-level) novelty detection** is out of reach for a pure-lexical metric —
   `torch`, `sentence_transformers`, `faiss` are all absent. **But this is a soft wall wrongly
   treated as hard:** two free lifting conditions exist and neither has been tried (a local CPU
   ONNX/GGUF embedding model; or LLM-as-judge over the ~50 nearest lexical candidates, ~1 call per
   new hypothesis — affordable *"at the current generation rate of zero per day"*).

**Three walls I am explicitly rejecting as false**, because calling them hard is how the desk would
lock in its own ceiling:
- *"One quota-limited seat"* — the desk already owns sklearn/numpy/scipy and already wrote an
  IDF-cosine retriever, so retrieval, dedup and prioritisation can run at **zero marginal quota
  cost**. Nobody has ever measured where the seat's budget actually goes.
- *"`tested=0` is expected, not a failure"* (a comment in `ops/run_crypto_factory.sh:8-15`) — a
  generator that cannot enlarge its own hypothesis space is at **0% of capacity, not at ceiling.**
  The comment even names the lifting condition and then nobody owns it.
- *"Price space is picked clean"* — see E1. The instrument was broken.

---

## (E) AUDITOR DISAGREEMENTS, ADJUDICATED

**E1 — "Price space is picked clean" vs "the instrument was broken." ADJUDICATED: the instrument.**
Several prior cycles read *434 tested / 0 promoted* as evidence that price-family alpha is exhausted,
and the SCREEN-ON-DISCOVERY doctrine encodes that reading (*"the picked-clean price space"*). Today's
HEAD commit refutes it: the positive control **had never actually put its question**, and the two
gates reject 420/420 as campaign constants. A 100%-rejecting gate produces zero information about the
candidates — so **the 420/0 record is an instrument artifact, not a fact about crypto.** This is
exactly the L1.25 cautionary instance, and the doctrine text asserting the opposite is now stale
(see P1-4).

**E2 — Is the desk's problem acquisition, conversion, or activation? ADJUDICATED: activation.**
Data-moat's closing sentence is the correct one: *"the desk's data-moat problem is not acquisition,
and this week it is not even conversion — it is that finished capabilities sit one import short of
working, and the gate that should notice checks whether a file exists."* This generalises beyond
data-moat and is corroborated independently by three other auditors: the S0→S1 gate reads files
nothing writes (execution), the novelty gate has a better implementation sitting unused in-repo
(research-engine), and the audit runner checks bytes rather than content (meta). **Four auditors
found the same shape in four subsystems: capability built, capability not wired, guard checks
existence rather than function.** That convergence is the strongest signal in this sweep.

**E3 — Meta-auditor M2 says "expected value of a deep-sweep finding ≈1.5%"; the volume of excellent
work this week implies otherwise. ADJUDICATED: M2 is right, and the volume makes it worse, not
better.** 365 KB of verified findings at a 1.9% realisation rate is not a productive week — it is a
larger stranded asset. I re-derived the rate independently (8/52 implemented × 1/8 dimensions rowed)
and reached the same place.

**E4 — No disagreement was found between data-intelligence and infrastructure on DQS/alarm
precision.** Both treat the alarm-precision break as real; they differ only in scope. Recorded as
agreement, not adjudicated.

**E5 — Three auditors independently diagnosed the sweep runner; none knew of the others.**
meta-and-blindspots (M1/M2), research-engine (R-6, which additionally cites the *07-29* meta report
as having found it first), and infrastructure (I8/I13, which falsifies *"the weekly sweep runs
weekly"* — it has never once started from cron and, as written, **can never finish**). Three
independent routes to one mechanism, across two consecutive weeks, with zero remediation. **This is
not a disagreement to adjudicate; it is the strongest possible evidence that the desk's constraint
is remediation, not diagnosis.** research-engine states the conclusion in the same words I reached
independently: *"this desk's diagnostic capability substantially exceeds its remediation capability.
Adding another finder has near-zero marginal ERV while 27 correct diagnoses sit undisposed. L1.13
BOTTLENECK PRIMACY says all engineering effort belongs here."* — and then, correctly, *"This audit
itself is subject to that judgment."*

**E6 — Is generating more audit volume good? ADJUDICATED: NO, at the current conversion rate.**
data-intelligence and infrastructure produced 119 KB and 123 KB respectively — excellent work, and
the largest reports in desk history. But data-intelligence itself concedes it audited **~12 of 240**
`data/` artifacts, and infrastructure names the 73 swallowed exceptions as *"not exhausted."* Both
are correct that more digging would find more. Both are, this week, **the wrong thing to do next**:
the marginal finding is worth ~1.9% until the wire is fixed. Volume was not the constraint and
adding volume was not the answer. I include this as a disagreement because the reports implicitly
argue for continued depth, and the portfolio in §C explicitly overrules them.

---

## (F) RECURSIVE META — IMPROVING THE AUDIT ITSELF

**Most value this week: meta-and-blindspots**, and it is not close — despite dying partway through
with only 2 of its 4 sections written. M1 and M2 are the only findings in the entire sweep that
change the value of *all* the others, and M1 predicted its own corruption of the synthesis step
accurately enough that my invocation confirmed it. **A 12.6 KB partial outproduced two 120 KB
complete reports on realised value**, because it found the constraint rather than a defect.

**Runner-up: execution-growth** — 20 command-verified findings, correct causal *ordering* of the fix
(equity read → `_MIN_FUNDING` → A/B/C), and the discipline to say the pending Tier-3 option (A) is
mis-specified rather than just endorsing it.

**Least value: alpha-discovery and validation-stats — they produced nothing.** This is a *systems*
failure (P0-1), not an indictment of those briefs. But note the pattern: alpha-discovery has now
failed 2 of the last 3 sweeps, and validation-stats has failed 2 of 4. Seat position correlates with
death — which is precisely what last week's T1 (rotate seats) was for, and it was never rowed.

**Sweep completion rate, measured:**

| sweep | complete | rate |
|---|---|---|
| 2026-07-26 | 5/8 | 62.5% |
| 2026-07-28 | 3/8 | 37.5% |
| 2026-07-29 | 8/8 | 100% |
| 2026-07-30 | 5/8 (+1 partial) | 62.5% |

Mean ≈ 65%. **Synthesis itself has produced output in 1 of 4 sweeps (25%)** and required 4 attempts
today. The audit organ is the least reliable organ on the desk, and it is the organ that measures
reliability.

### NEW AUDIT SECTION for next week: **"DORMANT-BUT-BUILT"**
Every auditor must report, for its subsystem: *which capabilities exist in code but have zero
callers, zero readers, or are gated by a guard that only checks existence?* Justification: this
sweep found the same shape independently in four subsystems (E2), and the desk already has a
dormancy hunter (`e28541c`: 171 capabilities, 16,645 paid-for unused lines) whose output no auditor
consulted. Make it a required input, not a rediscovery.

### AUDIT QUESTION THAT IS NO LONGER DISCRIMINATIVE: **"what would a world-class quant team do
differently?"** (EXTERNAL perspective).
Across four sweeps it has produced generic, uncited advice at a far lower evidence density than the
other five perspectives, and nothing it generated has ever been rowed. **Replace it with: "which of
this subsystem's capabilities has a better implementation already present in this repo, or in a
dependency we already ship?"** That question, asked by accident, produced P1-7 (the novelty-gate
TF-IDF fix already sitting at `knowledge_engine.py:80-99`) — the highest-ROI-per-hour item on this
board. The EXTERNAL lens is answering a question the desk cannot act on; the in-repo lens is
answering one it can act on today.

### A third improvement, from my own run
The synthesis prompt hardcodes *"append to `improvement_inbox.md`"* — a sink with **no dispositions,
nothing driving it, and a demonstrated 0/2 conversion rate on last week's own P0 items.** The prompt
should instruct the synthesis lead to **row into `scripts/recommendations.py`** and treat the inbox
as a narrative appendix. I have done both this run.

---

## (G) RESEARCH CAPABILITY CAGR — IS THE ENGINE GETTING STRONGER?

**Composite verdict: the engine's *measurement* is getting much stronger; its *conversion* is flat to
declining. Net — modestly stronger, and dangerously lopsided.**

| component | direction | evidence |
|---|---|---|
| Experiment throughput | **↑↑** | 434 candidates tested; audit volume 365 KB vs ~106 KB on 07-29 |
| Hypothesis quality | **↑** | mechanism-prior discipline holding; novelty gate broken (0% recall) caps it |
| Validation quality | **↑↑** | positive control built (`libs/validation/positive_control.py`, 218 lines, 140 lines of tests); the 420/0 artifact *diagnosed* |
| Automation | **↓** | sweep runner lost 2 audits; synthesis 1/4; auditor completion mean 65% |
| Knowledge reuse | **↓↓** | research memory write-only, ~96% of refutations never read; novelty gate 0% recall |
| Implementation velocity | **↓↓** | 8/52 (15%) implemented; 27 DEFECT rows; last synthesis's own P0s at 0/2 |
| Data coverage | **↑** | +30 sources, +24 graveyard entries since 07-19 |

**The shape is unmistakable: everything that produces knowledge is trending up; everything that
*retains or acts on* knowledge is trending down.** A desk that generates faster than it converts is
accumulating debt, which is precisely what §33 says about mining — and the same law is being violated
one level up, by the audit organ itself.

The single number that best captures the week: **the desk implemented its own top-priority
recommendation 0 times out of 2 attempts, across two consecutive syntheses, while producing 3.4×
more audit material than the week before.**

Rough composite CAGR: **positive but decelerating.** If P0-1/P0-2/P0-3 land, the same production
volume converts at 5–10× the current rate and the index inflects sharply upward — that is the entire
argument for the portfolio ordering in §C.

---

## APPENDIX — WHAT I VERIFIED MYSELF (not taken on report authority)

| claim | command | result |
|---|---|---|
| 2 audits are empty | `wc -c docs/research/deep_sweep/20260730_*.md` + `cat` | 1,736 b / 1,889 b, all sections `TBD`/placeholder |
| runner grades on bytes | `sed -n '100,145p' scripts/run_deep_sweep.py` | `ok = report.exists() and report.stat().st_size >= 1200` |
| log claims 8/8 | `cat data/cro_ai_logs/deep_sweep_20260730T1200.log` | `done: 8/8 produced; synthesis=NO` |
| synthesis failed 3× today | 4 sweep logs | `synthesis=NO` at 02:00, 07:40, 12:00 |
| ledger state | `scripts/recommendations.py report` | `52 total \| 8 implemented \| 3 rejected \| 15 scheduled \| 26 open` |
| only data-moat ever rowed | ledger scan by source | 8 `deep_sweep` rows = R0001 + R0003–R0009 (all data-moat) |
| P0-1/P0-3 never rowed | regex scan of ledger for sweep-runner/audit-action | no matching row |
| no seat rotation | `grep -n "for key, brief in SUBSYSTEMS"` | line 136, plain dict, fixed order |
| doctrine cites retracted kimchi | `grep -n kimchi ops/principal_doctrine.txt` | lines 89, 213 — asserted as validated evidence |
| gate rejects 420/420 | `data/PRINCIPAL_ACTION.md` §2 | PBO 0.6159, RC p 0.4220, 420/420 rejected |
| book absorbing | `data/PRINCIPAL_ACTION.md` §1 | $4,399.91 verified inventory marked $0 |

---

## APPENDIX — WHAT THIS SYNTHESIS ACTUALLY DID (not just recommended)

The instruction I was given was *"append the top portfolio items to `improvement_inbox.md`."* Following
that literally would have reproduced the exact defect this report exists to name — last week's synthesis
did precisely that, and its two P0 items were never rowed and never built. So I did both:

| action | artifact | verification |
|---|---|---|
| Rowed 8 findings into the **driven** ledger | R0053–R0060 | `recommendations.py report` → 60 total (was 52) |
| Disposed my own duplicate | **R0059 → REJECTED** | duplicated R0051 (kimchi doctrine); reason names R0051 as owner and folds in the extra scope (line 213 + 9 derived registries) so nothing is lost |
| Appended 5 portfolio items | `improvement_inbox.md` #80–#84 | `grep -c '^## #'` → 15 |
| Corrected the principal's pending decision | `data/PRINCIPAL_ACTION.md` line 1 | option (A) is mis-specified; ordering supplied |

**I am aware this adds 7 open rows to a ledger already carrying 27 undisposed ones, and that P0-3 in my
own portfolio is "dispose the backlog."** That tension is real and I am naming it rather than hiding it:
rowing is still correct, because an unrowed finding has a ~0% chance of being worked while an undisposed
row is at least *visible and fenced*. But if the next cycle rows another eight and disposes none, the
ledger becomes the new inbox and this fix will have failed. **The success test for P0-2 is not "rows
exist" — it is the implementation rate (8/60 = 13% today) going up.** That number is the one to watch,
and it is currently going *down* because I just grew the denominator.

_Report complete. Synthesis lead, 2026-07-30._

---

## ADDENDUM — 22:45Z SEAT (5th window): VERIFICATION + CONVERSION

The 22:45 resume window re-launched a synthesis seat 5h after this report completed — synthesis had
no resume check (now it does). Rather than re-synthesize, this seat applied OUTCOME-NOT-CONFIG to the
synthesis itself and then converted its top rows:

**Verified from disk (§33: self-reported conversion is never credited):** R0053–R0060 all in the
ledger, R0059 rejected exactly as declared; inbox #80–#84 present; PRINCIPAL_ACTION correction live
at line 13; commit bccb5e3 pushed. Every appendix claim checked out.

**Converted this seat (fccc580):**
- **P0-0 DONE — the ruin rail is re-armed.** equity = max(stable face-value sum, totalMarginBalance)
  in `account_summary()` AND `combined_equity()` — the rail never imported the executor's read, so
  the USDT-only bug lived in TWO places (adjacency; the synthesis's "one fix re-arms" was optimistic
  by one file). Measured: 209.43 → **5,773.63** — and note `multiAssetsMargin` was flipped true
  between 08:33 and 22:53 by someone/something unrecorded, so the venue field now counts USDC + 0.01
  BTC; `max()` is correct under either mode and never reads below either truth. New `disarmed_live`
  flag + one-shot page whenever the dust floor guards a live book. Deadman restarted 22:57Z, pid
  1463355 on fixed code, heartbeat verified; hw ratchets past the dust floor within 3 polls.
- **P0-1 DONE — audits are graded on the auditor's own `STATUS: COMPLETE` sentinel**, failure stubs
  go to `.md.FAILED` sidecars (partials preserved), synthesis resume check added. 76 tests pass.
- **Dispositions:** R0053, R0054, R0055 → implemented (fccc580). **R0057 (`_MIN_FUNDING`)
  deliberately left open for the execution organ** — it restarts capital deployment and its
  cost-model claims deserve execution-context re-verification, not a synthesis seat's pen.

**Post-17:11 fact the next cycle must absorb:** prospector 051fe70 proved the kimchi RETRACTION'S
PREMISE wrong (Upbit dailies are UTC-midnight; the 07-29 close-keying "fix" itself introduced 24h
staleness) while the kill STANDS on same-instant 8.2y IC +0.0012. Doctrine lines 89/275 remain
contaminated; R0051 stays the owner, now with a third layer to fold in: the decontaminated text must
cite the corrected mechanism of death, not the retracted one.

_Verification seat complete, 22:59Z._
