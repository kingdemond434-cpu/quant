# DEEP COLD AUDIT — META-AND-BLINDSPOTS — 2026-07-30

_Auditor: Claude Opus 5. **Provenance (verified, not assumed):** this IS the scheduled auditor.
`ps -eo pid,lstart,cmd` → PID 1380723, started `Thu Jul 30 12:27:30 2026`, `claude --effort max
--append-system-prompt "THE CONSTITUTION GOVERNS..."`. `tail data/cro_ai_logs/deep_sweep_20260730T1200.log`
ends on the bare line `[deep-sweep] auditor: meta-and-blindspots` with no verdict — I am position 8
of 8 in the 12:00Z catch-up window, the exact slot the 2026-07-29 meta-audit found starved. The file
I am overwriting was a `BRAIN_AUTH_FAILED` stub (494 bytes). Read-only run. Every claim carries its
proving command output. Written incrementally per the COMPLETION CONTRACT — if cut off, what is
below is the deliverable._

**STATUS: IN PROGRESS** — findings appended as verified.

## SCORES

_(placeholders — finalised at the end of the run)_

- current_capability_pct: TBD
- practical_ceiling_estimate: TBD
- ceiling_gap: TBD
- opportunity_cost_1y: TBD
- confidence: TBD
- unknown_unknown_score: TBD
- info_gain_if_investigated: TBD
- expected_alpha_contribution: TBD
- expected_compounding_contribution: TBD
- CEILING EXPANSION: TBD

## FINDINGS

### M1 — THE AUDIT ORGAN GRADES ITSELF ON FILE SIZE, SO TWO OF TODAY'S EIGHT AUDITS ARE PLACEHOLDERS MARKED "OK" AND ARE NOW PERMANENTLY UNRETRYABLE

**Severity: CRITICAL. This is a self-greening guard — the doctrine's prime quarry — inside the
organ whose entire job is to catch self-greening guards.**

`scripts/run_deep_sweep.py:109` is the whole defect:

```python
ok = report.exists() and report.stat().st_size >= 1200
```

`ok` is computed from **bytes on disk and nothing else**. It never consults `r.returncode`, never
consults `r is None` (the 1800 s timeout), never looks at the content. The resume gate in `main()`
(line 139) uses the identical test:

```python
if done.exists() and done.stat().st_size >= 1200:
    print(f"[deep-sweep] {key}: already produced today -- skipping (resume)")
    results.append((key, True))
```

**The interaction that makes it lethal.** `prompts/deep_sweep_core.txt`'s COMPLETION CONTRACT
correctly orders every auditor to *"WRITE THE SKELETON FIRST… create your report file with the four
output headings and your subsystem's scores as placeholders."* A conforming skeleton is
**~1,500–1,900 bytes** — comfortably over the 1,200-byte floor. So an auditor that obeys the
doctrine, writes its skeleton, and then dies **passes its own success test, suppresses the failure
stub, and is skipped by every subsequent resume window forever.** Two organs each individually
correct; jointly they silently delete audits.

**It fired twice TODAY.** Measured:

```
$ for f in docs/research/deep_sweep/20260730*.md; do printf "%-46s %7d\n" $(basename $f) $(wc -c <$f); done
20260730_alpha-discovery.md                        1736     <-- SKELETON ONLY
20260730_data-intelligence.md                    119011
20260730_data-moat.md                             60574
20260730_execution-growth.md                      61680
20260730_infrastructure.md                       122891
20260730_meta-and-blindspots.md                    1532     <-- this file, mid-run
20260730_research-engine.md                      120181
20260730_validation-stats.md                       1889     <-- SKELETON ONLY
```

`cat docs/research/deep_sweep/20260730_alpha-discovery.md` → every section body is the literal
string `(placeholder — filled incrementally)`; all ten scores read `TBD`.
`cat docs/research/deep_sweep/20260730_validation-stats.md` → `## 1. WHAT WE KNOW` … `_TBD_`,
`## FINDINGS` … `_TBD_`. **Zero findings between them.**

And the logs graded both as successes:

```
$ cat data/cro_ai_logs/deep_sweep_20260730T0200.log
[deep-sweep] alpha-discovery: OK                 <-- the 1,736-byte skeleton
...
[deep-sweep] done: 3/8 produced; synthesis=NO

$ cat data/cro_ai_logs/deep_sweep_20260730T0740.log
[deep-sweep] alpha-discovery: already produced today -- skipping (resume)   <-- locked in
...
[deep-sweep] validation-stats: OK                <-- the 1,889-byte skeleton
[deep-sweep] done: 6/8 produced; synthesis=NO
```

The real reports today run **60k–123k bytes**. The placeholders are **1.7k–1.9k**. That is a **60×
separation that a 1,200-byte threshold cannot see.** The desk's own log says `6/8 produced` when
the truth was `4/8`.

**Second-order damage — this corrupts synthesis, it does not merely lose data.** `main()` builds
`good = [f"{stamp}_{k}.md" for k, ok in results if ok]` and hands that list to the synthesis lead
with *"Read every auditor report… {', '.join(good)}"*. Both skeletons are in `good`. So when
synthesis fires it will ingest two files whose entire content is `TBD` **as if they were audits**,
and then compute output (F) "which of the 8 subsystem-audits produced the most value this week" and
(G) the RESEARCH CAPABILITY CAGR index from them. A placeholder read as a finding is worse than a
missing file: it silently biases the desk's only cross-subsystem integration step and its only
engine-health index.

**Self-implicating instance, stated plainly:** the file you are reading crossed 1,200 bytes the
moment I wrote its skeleton. Had I died at that point, this audit would have been recorded `OK`,
counted toward `8/8`, and fed to synthesis as evidence. I was one crash away from being the third
instance in the same run.

**Why the byte floor exists, and why that rationale is not wrong — the fix must preserve it.**
Line 106 records the history: *"1200b: a tight, command-cited report is a PASS. The old 2500b floor
rewarded padding — the exact failure the doctrine forbids."* Correct, and raising the floor is
therefore the WRONG fix: it re-introduces padding pressure and still cannot tell a 3k skeleton from
a 3k report. The floor is the wrong instrument, not a mis-set one.

**Fix (exact):** grade on **completion, not size**.
1. `ok = (r is not None and r.returncode == 0) and report.exists() and size >= 1200` — a
   non-zero exit or a timeout can never be graded OK regardless of bytes. This alone closes
   today's two instances.
2. Require a **terminal sentinel**: the contract already has auditors write a status line; make
   `STATUS: IN PROGRESS` → not-ok and demand the auditor flip it to `COMPLETE` (or require the
   four output headings to be non-placeholder). Cheap content test, no padding incentive.
3. **Never suppress the diagnosis.** When `not ok`, the current code *overwrites the partial report
   with the failure stub*, destroying the only evidence of how far the auditor got. Write the stub
   to `<report>.FAILED` and leave the partial in place — the completion contract's entire premise
   is that a partial report is the deliverable, and the runner deletes it.
4. Resume must re-run a file whose sentinel is not `COMPLETE`, even if it is large.

**Failure mode of the fix:** an auditor that finishes but exits non-zero on a trailing tool error
would be re-run and would overwrite a good report. Mitigate by ordering the tests — sentinel
`COMPLETE` wins over exit code — so a genuinely finished report is never discarded.

**Retirement condition:** none; this is a permanent correctness test. Retire the `.FAILED`
side-file convention only if the runner gains structured per-auditor result records.

---

### M2 — THE AUDIT SYSTEM HAS NO PATH TO ACTION: 7 OF 8 DIMENSIONS' FINDINGS WERE NEVER ROWED, INCLUDING ALL 8 OF THE LAST META-AUDIT'S OWN EXPERIMENTS

**Severity: CRITICAL — and it is the finding that determines the value of every other finding in
this report, including this one.**

The desk's §35/§41 law is explicit: *"A finding written in a review, an inbox, a panel ruling or a
chat and NOT rowed is invisible to you forever."* Measured against the ledger:

```
$ python3 -c "...Counter(r['source'] for r in rows)..."
 27  cycle
  8  deep_sweep
  4  cycle-2026-07-28
  3  cycle-2026-07-28-generation
  ...
$ # which dimensions do those 8 deep_sweep rows come from?
R0003 open  data-moat
R0004 open  data-moat
R0005 open  data-moat
R0006 open  data-moat
R0007 open  data-moat
R0008 open  data-moat
R0009 open  data-moat
```

**All 7 substantive `deep_sweep` rows are from ONE dimension: data-moat** (its O1–O7). The eighth
is `R0002`, sourced `max_audit`. **Zero rows** exist from meta-and-blindspots, research-engine,
validation-stats, infrastructure, execution-growth, alpha-discovery or data-intelligence — across
the 07-26, 07-28 and 07-29 sweeps, which produced ~250 KB of audited findings.

Grepped directly for the 07-29 meta-audit's eight named experiments:

```
$ python3 -c "...search ledger for meta-and-blind|starv|synthesis|rotation|doctrine_claims|alarm_telemetry|assumptions.md..."
HIT R0032 open cycle-2026-07-28-generation      # FRED lookback — unrelated, keyword collision only
$ grep -n "starv\|rotation\|DOCTRINE_CLAIMS\|alarm_telemetry\|ASSUMPTIONS.md\|DEADMAN series" docs/GAP_REGISTER.md
328:long-tail is by-design rotation (TIER-0 decision surface sent every run)...   # unrelated
```

**T1–T8 do not exist in the ledger or the register. Not one.** The 07-29 report closed with:
*"the next live cycle must row T1–T8… until rowed, by the desk's own law, these findings are
invisible."* One day later they are still invisible. **The audit correctly predicted its own
disposal and was disposed of anyway** — which means the failure is structural, not an oversight:
the sweep runner has no rowing step, and the auditors are launched read-only and *cannot* row their
own findings.

**The confirming consequence: T1 is why I am running at position 8 in a third catch-up window.**
T1 asked for order rotation and a failure-streak counter. `scripts/run_deep_sweep.py:22` still reads
`SUBSYSTEMS = {` — a plain dict — and line 136 still `for key, brief in SUBSYSTEMS.items():` with
no rotation, no shuffle, no streak counter. The fix was diagnosed with evidence, written up, and
then evaporated because nothing carried it to a queue.

**The measured cost of the missing path.** `scripts/recommendations.py report` →
`50 total | 6 implemented | 3 rejected | 12 scheduled | 29 open`, with **29 rows flagged
`DEFECT [UNDISPOSED past grace]`** and `R0002` additionally `SCHEDULED past due`. Implementation
rate **6/50 = 12%**. So even the findings that *do* get rowed face a 12% conversion rate — and the
audit organ's findings do not get rowed at all. **Expected realised value of a deep-sweep finding
today ≈ 0.12 × P(rowed) ≈ 0.12 × 1/8 ≈ 1.5%.**

This is the dominant term in the whole subsystem. Producing better audits has near-zero marginal
value while the transmission is disconnected; the highest-ROI act available to this organ is not a
sharper finding, it is a wire.

**Fix (exact), cheapest first:**
1. **Make the auditor's last act a rowing act.** Auditors run read-only by design (correct — an
   auditor that can edit state can launder its own findings). So add a *post-sweep* step in
   `run_deep_sweep.py`: after each report is graded COMPLETE, a small non-LLM parser extracts the
   `## 4. WHAT WE TEST NEXT` items and calls `scripts/recommendations.py add` with
   `--source deep_sweep-<dimension>`. Mechanical, deterministic, no judgment required.
2. Failing that, require the **synthesis lead** (which is not read-only — it already appends to
   `improvement_inbox.md` and `PRINCIPAL_ACTION.md`) to row every dimension's top-3. Note this is
   *currently* the intended path and it has never worked, because synthesis has run once ever
   (see M3) and rows nothing.
3. Add a `max_audit` check: **`sweep-findings-unrowed`** — for each `docs/research/deep_sweep/
   <today>_*.md` marked COMPLETE, assert ≥1 ledger row with matching `--source`. This is the fence
   that makes the ratchet real; without it the wire silently breaks again.

**Alternatives considered:** letting auditors write rows directly (rejected — breaks read-only
isolation, and an organ that grades and files its own work is the M1 defect in a new costume);
having the principal triage the reports (rejected — that is precisely the L1.22/§(d) failure the
doctrine scores as the top defect of a cycle).

**Retirement condition:** retire the parser step if and only if structured findings become a
first-class output format (auditors emit JSON alongside prose), at which point the row is a direct
insert.

## 2. WHAT WE DON'T KNOW (the ignorance ledger)

_(appended as verified)_

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_(appended as verified)_

## 4. WHAT WE TEST NEXT (concrete experiments)

_(appended as verified)_
