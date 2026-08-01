# Weekly Deep Cold Audit — META & BLIND SPOTS — 2026-08-01

STATUS: IN PROGRESS

Subsystem: meta-and-blindspots (the layer above: untested research ASSUMPTIONS, habit-persisting
workflows, misleading metrics, blind-spot transfer from outside fields, institutional curiosity,
research trajectory).

Working dir: /home/quant/quant-platform. READ-ONLY run.
Auditor: Claude (Opus). Cohort benchmark file read: docs/research/TIER1_BENCHMARK.md.

---

## SCORES (filled at end)

| metric | value |
|---|---|
| current_capability_pct | TBD |
| practical_ceiling_estimate | TBD |
| ceiling_gap | TBD |
| opportunity_cost_1y | TBD |
| confidence | TBD |
| unknown_unknown_score | TBD |
| info_gain_if_investigated | TBD |
| expected_alpha_contribution | TBD |
| expected_compounding_contribution | TBD |

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

_(filled incrementally)_

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

_(filled incrementally)_

---

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_(filled incrementally)_

---

## 4. WHAT WE TEST NEXT

_(filled incrementally)_

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

