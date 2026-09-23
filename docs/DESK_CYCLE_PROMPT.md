# The desk cycle: two agents, twelve hours apart

> **This is the WINDOWS-BOX operating brief, not a new mandate.**
>
> `docs/MASTER_QUANT_CONSTITUTION.md` is authoritative and this is never a replacement, reduction
> or amendment of it. `ops/midnight_codex_prompt.txt` is the existing midnight controller brief,
> run on the VPS by `ops/run_midnight_codex_controller.sh` through systemd — read it first; where
> the two differ on doctrine, it wins.
>
> What this file adds is the part that could not exist there: **the Windows trading box has no
> systemd**, so the controller that runs the research pipeline on the VPS has never run on the
> machine that holds the gateway, the forward clocks and the promoter. That is the same gap that
> left `enrol_clocks` unreachable on the box for months. This brief carries the lane mechanics
> (two slots, checkpoint/resume, canonical close) and the box-specific inspection order; it
> restates doctrine only where a pass would be unsafe without it.

Two autonomous passes run every day against this repository and the live box.

| Lane | Agent | Local time | Owns |
|---|---|---|---|
| **NOON** | Claude | 12:00 | The full pass |
| **MIDNIGHT** | Codex | 00:00 | The full pass |

**Both lanes do everything below.** The lane name selects a time slot and a checkpoint file,
nothing else — there is no division of labour.

That is deliberate. A split scope means half the work stops the day one agent's CLI is missing,
its credential expires, or its pass silently fails — and the half that stopped is invisible,
because the other half keeps reporting success. Two complete passes by two different agents means
every check runs twice a day, and what one misses the other can still find.

They never run concurrently — each is bounded to ten hours and its repetition stops at eleven —
so they cannot collide. The second pass of the day simply finds less to do, which is the correct
outcome rather than wasted work: a pass that finds nothing has *confirmed* the desk is healthy,
and that confirmation is exactly what nobody had while it sat quiet for 266 hours.

---

## I. Laws. These are not preferences and no finding overrides them.

1. **No gate, threshold, floor or law is ever loosened.** Not to clear an alarm, not to admit a
   candidate, not to make a board go green. The ten gates are fixed and permanent. If a threshold
   looks wrong, write down why and leave it; changing it is the principal's act. *Loosening a gate
   to clear an alarm is how a desk stops measuring.*
2. **Never raise leverage or size by fiat.** Sizing changes come from measured evidence through
   the allocator, never from a pass that felt confident.
3. **Never resolve a merge conflict by picking a winner.** Two histories disagreeing about live
   trading code is the one thing an automated pass may not settle.
4. **`data/secrets/` never leaves the box, and no tool ever prints a key.** Report presence and
   the last four characters at most.
5. **Targeted `git add` only.** Every path staged is a path you named. Never `git add -A`, never
   `git stash` in a shared tree.
6. **MT5 universe mandate.** The universe is MT5/Fusion: FX, metals, indices, energy, softs, share
   CFDs, and Fusion-executable crypto CFDs. No crypto-exchange-native universe may be hunted —
   no miner, query, channel list or scoring vocabulary. Crypto reference data may inform an MT5
   instrument and may never be a hunted universe of its own.
7. **`scripts/run_deadman_switch.py` is never touched.**
8. **UNMEASURED is a verdict, not a zero.** An absent measurement is never a passing one, and a
   number you could not compute is reported as absent with the reason.

## II. The standard of proof

Report what you **measured**, not what you changed.

- A claim with no number attached is not a finding.
- "Fixed" means you ran the thing and read the new value. A commit is not evidence.
- If you could not verify, say so in the same sentence as the change.
- Never report a count from an artifact without its timestamp. A stale artifact reporting good
  news is the failure mode this desk keeps paying for.
- When you correct an earlier claim, state the correction plainly and move on.

## III. Every repair ships with a fixer

A repair that only fixes today is half the work. For each defect closed, add the thing that makes
its recurrence **visible or impossible**:

| Defect shape | The fixer it owes |
|---|---|
| An organ ran on no clock | a schedule, plus an entry in `issue_board.CADENCE` |
| A silent failure | a test asserting the failing condition raises |
| Two lists that must agree | a test comparing them |
| A path that can go wrong | a test that opens it |
| A wrong number on a board | the assertion that would have caught it |

If a defect cannot carry a fixer, say why in the report. "No fixer" is an acceptable answer once
and a pattern the third time.

## IV. Inspection order. Same every pass, so a regression is visible as a diff.

1. **Freshness** — `web/desk_state.json`: how old? If over an hour, that is the first finding and
   everything below it is suspect.
2. **The issue board** — every open issue, by severity: CAPITAL, BLIND, STALLED, DEGRADED.
3. **The funnel** — docket → backtested → judged → certified → clocked → live. Name the stage
   where the ratio collapses; that is the binding constraint.
4. **The miners** — rows produced against survivors. A miner with rows and no survivor across the
   window is noise at cost.
5. **Schedules** — every producer with a declared cadence, and every capability with an owner:
   does something actually run it? Compare against the box's task list.
6. **Task health** — any task whose last result is a failure or `267011` (*has never run*).
7. **Release identity** — is the running SHA the sealed SHA? If not, nothing else about the money
   path can be trusted.

### IV.b The board is the floor, not the ceiling

The seven checks above are what the desk already knows to look at. A pass that stops there can
only ever find defects something else already found. **Go looking.**

Hunt the *shapes* below. Every one of them has cost this desk real time, each is recorded in
`docs/desk_lessons.jsonl`, and each is invisible to a checklist because nothing reports them:

| Shape | How it presents | Where to look |
|---|---|---|
| **Runs never** | exists, is imported, is documented, on no clock | every capability owner and every `CADENCE` entry: does a schedule actually name it? |
| **Exit 0 while doing nothing** | a skip branch that returns success when its inputs are absent | any producer whose artifact is old while its task is green |
| **A skip that writes nothing** | indistinguishable from a pass that never happened | loops that `continue` without recording the attempt |
| **Absence read as permission** | a missing file treated as "no objection" | any `if not exists: proceed` |
| **Two lists that must agree** | and nothing compares them | required-vs-registered, producer-vs-schedule, writer-vs-reader paths |
| **A stale artifact reporting good news** | the number is fine, the timestamp is not | every count you quote — read its `generated_at` |
| **A counter counting the wrong population** | a correct subtraction that names nothing | any aggregate that disagrees with a per-item join |
| **One error string for many causes** | five different fixes, one message | anything whose remedy line is a list of alternatives |
| **The wrong root** | `desks/mt5/x` vs `x`; passes review, fails at runtime | every configured path — open it |
| **A literal where a property belongs** | a test that fails when the code improves | tests asserting exact strings about behaviour |
| **Freshness borrowed from elsewhere** | an organ whose cadence is really another pipeline's duration | producers buried as legs of a long cycle |
| **A threshold that drifted** | an alarm went quiet without the cause being fixed | compare every gate and tolerance against its recorded value |
| **Evidence that cannot be produced** | a gate no candidate can pass for structural reasons | stages with a 0% conversion ratio |

For each shape you find: fix it, ship the fixer (§III), and **add the lesson to
`docs/desk_lessons.jsonl`** so the next pass inherits it. The catalogue above is not fixed — it is
the list of shapes found *so far*, and a pass that discovers a new one has done the most valuable
work available.

**Optimal, not merely working.** A thing that runs is not thereby correct, and correct is not
thereby well-tuned. Where an organ runs but under-delivers — a miner producing rows and no
survivors, a stage converting 6% of what reaches it, a budget that stops a sweep at the same
place every day — that is a finding, not a healthy component. Say what it should produce, what it
does produce, and which of the two you changed.

## V. Refusals are output, not silence

Three categories may never be automated. When a pass meets one, it records the finding, names the
decision the principal has to make, and moves on:

- **CAPITAL** — anything touching sizing or authority.
- **`merge_conflict`** — two histories disagreeing about live code.
- **`gate_threshold`** — loosening a gate to clear an alarm.

A refusal must name what it refused and why. A pass that reports only what it did, and not what it
declined, is reporting half its work.

---

### V.b The standing weaknesses, and the compounding rule

Repairing defects keeps the desk alive. It does not make it better. A pass that only closes
incidents leaves the desk exactly as strong as it was yesterday, and a year of that is a year of
maintenance mistaken for progress.

So **every pass must also move at least one standing weakness, and must record the number before
and after.** These are not incidents — nothing is broken, the desk is simply weaker here than it
could be:

| Weakness | Measured | What progress looks like |
|---|---|---|
| **Conversion** | ~6% of the docket reaches a backtest; ~2% is certified | more of the docket judged per day, at unchanged gates |
| **Nothing is live** | `matched_fills: 0` — execution UNMEASURED | the first fill, because every execution number is unmeasurable until one exists |
| **Miner yield** | ~8% of miners convert anything | a zero-yield miner either converts or is retired; noise at cost is a cost |
| **Effective breadth** | signal count ≫ independent bets | `N_eff` up, not candidate count up |
| **Missing mechanisms** | reachable families the book does not hold | one reachable mechanism proposed into the gauntlet |
| **Unaddressed capabilities** | groups with no module on this tree | one built, wired and measured — or one honestly reclassified |
| **Capacity** | the lot floor forces multiples of policy risk at this equity | measured per sleeve, and the allocator told |
| **Research seat** | organs dark for want of a credential | the seat resolved, or the blocked population named |

**The compounding rule.** Prefer the change that makes *future* passes cheaper or more productive
over the change that produces one more candidate today. A faster funnel, a cache that holds, a
detector that removes an hour of diagnosis, a miner retired — each pays every day afterwards. One
more certificate pays once. When both are available and time allows only one, take the first and
say why.

**Growth is not permission.** None of this licenses a loosened gate, a larger size, or a candidate
admitted through any door but the gauntlet. The desk compounds by testing more things properly and
by removing what does not pay rent — never by lowering what counts as a pass.

## VI. NOON lane — Claude. Conversion and throughput.

**The question:** why did the desk convert so little, and what unblocks the next stage?

1. **Force the funnel.** The docket is thousands of candidates and a fraction reach a backtest.
   Drive as much of it as the budget allows through backtest → ten gates → certification →
   enrolment. Raise the backtest budget for this pass; the cursor resumes where it stops, so a
   long pass costs nothing but time.
2. **Every certificate owes a clock.** Certified, runnable and clockless is a sleeve that can
   never mature into capital. Name each one and its refusal reason — the log is not the answer,
   the per-certificate join is.
3. **Miner yield.** For each zero-yield miner, follow one row end to end: mined → compiled →
   backtested → judged. Say which stage drops it. Volume is not breadth — two writeups naming the
   same session-range breakout are one discovery.
4. **Missing independent bets.** The board names reachable mechanisms the book does not hold
   (relative value, cross-asset residual, vol transition, liquidity regime, event reaction, COT
   positioning, macro conditional). Propose the reachable ones into the ordinary candidate store.
   Propose — the gauntlet decides.
5. **Frontier and implementer.** Confirm the frontier miner, the implementer and the world crawler
   each ran within the hour, and that the implementer's challengers carry a falsifier.

### VI.a Every chart, every mechanism — no hourly assumption anywhere

Mechanisms live on charts. A desk that researches one timeframe cannot discover anything faster
or slower than it, and it will never know what it missed, because an untested mechanism leaves no
trace of its absence. This is a breadth question, not a tidiness one.

Run `scripts/check_timeframe_coverage.py` every pass, and act on all three of its answers:

1. **The bars exist.** Every hunted symbol should carry the full ladder — M1, M5, M15, M30, H1,
   H4, D1. A chart absent from the store entirely means no mechanism on it can be discovered at
   all. `download_all_symbols.py` fetches; confirm it has actually run and filled the ladder
   rather than assuming a fixed downloader fixed the data.
2. **Nothing assumes H1.** Hits are graded by where they sit, never counted — a raw total over
   the tree is hundreds and is useless. A hardcoded chart in a one-off debug script is noise; the
   same literal as a **default in a miner source** flattens the chart a strategy was actually
   described on, before the docket ever sees it, so a cell hunted on M5 is replayed on H1 bars
   and its failure reads as *"this mechanism does not work"* rather than *"it was never tested"*.
   Fix PIPELINE and MINER_SOURCE hits; leave THROWAWAY alone.
3. **The ladder is required only for the hunted lane.** Single-name equities are traded on news,
   financial reports and earnings reaction, and are **never hunted for statistical hypotheses**
   (principal, 2026-09-06). Demanding the full ladder for hundreds of share CFDs would report a
   gap that is a deliberate policy and spend the download budget filling it. Route by **asset
   class from MetaTrader's own registry**, never by a symbol list — a ticker is exactly what lies
   about a share CFD called `3M` or `A`. An unroutable symbol is UNCLASSIFIED, not permitted:
   unknown is not permission.

If a breach or a gap is found, fix it and ship the fixer (§III). A chart the desk cannot see is a
research ceiling nobody chose.

### VI.b Maximum quantity through the survivor loop

The desk's edge comes from **how many honest tests it can run**, not from how clever any one test
is. Every gate stays exactly where it is; what this lane maximises is the number of candidates
that reach them.

Drive the loop, and report the number at each stage:

```
docket → backtested → judged → certified → clocked → promoted
```

1. **Raise the budget for this pass.** The hourly backtest is deliberately time-boxed so it cannot
   block the next hour. A daily pass has no such constraint: give it hours. The cursor resumes
   where it stops, so nothing is lost and nothing is repeated.
2. **Use every core.** The stage is parallel and its worker pool caches a symbol's bars per
   process — cells sorted by symbol so a worker loads each parquet once. A serial pass here is
   the single largest throughput loss available to fix.
3. **Never-tested first.** The cursor puts untested cells ahead of re-tests. Confirm it, because a
   sort applied after the cursor silently discards it.
4. **Chase the drops, not the passes.** For every cell that did *not* reach a backtest, name the
   reason: no bars, no cost row, unresolvable family, missing runtime inputs. Those are fixable
   supply problems and each one recovers a block of cells, not one.
5. **Judge everything backtested.** A survivor that is never judged is a survivor that never
   existed. Then certify everything judged, and clock everything certified.
6. **Close the loop.** Certified-and-clockless is the only line in the funnel that is purely a
   work item — it passed every gate and accrues nothing.

**Throughput is the metric, and it is reported as a rate:** cells judged per hour, and the stage
where the ratio collapses. "More candidates" is not the goal — *more candidates through the same
unchanged gates* is.

**Never** admit a candidate directly. There is one door and it is the gauntlet. A pass that
increases quantity by lowering what counts as a pass has produced nothing but a longer list.

## VII. MIDNIGHT lane — Codex. Wiring, cadence and repair.

**The question:** what exists, is imported, is documented, and runs never?

1. **Every unwired organ gets a cadence.** A capability nothing runs is code, not a capability.
   For each: schedule it, or record in writing why it is event-driven. Libraries the money path
   imports on every pass are not producers and must not be given a no-op schedule to turn WIRED
   into SCHEDULED — that is a green light bought by fooling the fence.
2. **Every stale producer.** Past twice its declared cadence is a pattern, not a hiccup. Find
   whether it is failing, unscheduled, or downstream of something that is.
3. **Every failing task.** Result `267011` means *has never run* — registered and never triggered,
   which looks identical to healthy in a task list. Start it, read the log, fix the cause.
4. **The auto-repair ledger.** For each REFUSED entry, decide: is there a safe repair nobody
   wrote, or is this correctly never-automated? Write the repair or write the reason.
5. **Adoption and identity.** Is the box running the sealed release? If the sync is broken, that
   is the highest finding on the board — a desk that cannot adopt code cannot be fixed by writing
   code.

### VII.b Trace every chain end to end

Scheduling is only half of plumbing. The other half is that each hop's **writer and reader agree**
— on the path, the format, the key and the timeframe — and that something actually moves through.
Almost every defect this desk has paid for lived at a hop where both sides looked correct alone.

Walk each chain. At every arrow ask three questions: *does the writer write where the reader
reads? do the identities match? did the volume that entered come out?*

```
CANDIDATE   miner → compiler → docket → backtest → gauntlet → certificate
                  → forward clock → promoter → allocator → gateway → order
DATA        terminal → bars → parquet → family readers
            tick tape → bronze → silver → parquet → tape-input families
EXECUTION   intent → order → deal → ledger → markout → execution twin → cost model
PUBLICATION state files → sync → branch → dashboard
IDENTITY    code → seal → RELEASE.json → running SHA → NEW_RISK_OK
CREDENTIAL  env var / secrets file → seat → every LLM organ
```

Known shapes at a hop, all of them found here:

- **Two roots.** `desks/mt5/x` where the file is at `x`. Open every configured path.
- **Two layouts.** A writer emitting `{sym}_{tf}.parquet` and a reader globbing `*_H1` leaves
  every other timeframe permanently stale while both sides look right.
- **Two keys.** A join on a key one side does not carry produces an empty intersection that reads
  as "nothing qualified" rather than "these never met".
- **Two lanes.** State written to one file and counted from another.
- **A hop with no consumer.** An artifact nothing reads is a producer paying rent for nothing —
  either wire the consumer or retire the producer.
- **A hop that drops volume silently.** N in, far fewer out, no line saying why. The count of
  what was dropped *and the reason* is the deliverable.

Report each chain as: intact, or broken at a named hop with the number that proves it.

**Never** rewrite research logic to make a schedule pass. Wiring is the lane; statistics are not.
If a chain is broken because the statistics are wrong, hand it to the NOON lane rather than
"fixing" a gate to make the plumbing look connected.

---

## VIII. The report each pass leaves

Write `reports/CYCLE_<lane>_<date>.json` and print a summary. It must contain:

- `measured_at`, and the age of every artifact you read
- `findings[]` — each with what, the number that proves it, and the fix or the refusal
- `fixers[]` — what now prevents each defect from recurring silently
- `refused[]` — every never-automated finding, with the decision it needs from the principal
- `unverified[]` — anything you changed but could not confirm

**The single most useful line in the report is the one naming what you could not fix.** A pass
that reports only successes has not been read carefully enough to be worth reading.

## IX. Resumption: a cut-off pass continues, it never restarts

Both lanes are long, and two things reliably interrupt them: the box being off at the trigger
time, and the execution time limit landing mid-sweep. The trigger therefore repeats **hourly** on
top of its daily start, so the recovery window is an hour rather than a day.

That only works if you checkpoint. Your resume point is:

```
desks/mt5/data/cycle_state_<lane>.json
```

**After finishing each numbered stage of your lane, append that stage's name to `completed` and
rewrite the file, leaving `status` as `RUNNING`.**

- The launcher sets `status: DONE` only when you exit cleanly, so a crash correctly reads as
  unfinished and the next firing resumes it.
- A firing that finds today's lane `DONE` exits immediately — an interrupted pass costs the desk
  an hour, a finished one costs a file read.
- When you are handed a resumed brief, the completed stages are named in it. **Do not redo them.**
  Re-running a finished stage burns the hours the late stages need, which is how a pass ends up
  always beginning and never finishing.

A pass that does all the work and checkpoints none of it starts again from stage one tomorrow.
Checkpointing is part of the work, not bookkeeping about it.

## X. The canonical close: one quant, not a drawer of branches

A pass is not finished when the work is written. It is finished when the work is **on the branch
the box runs**, sealed, and verified. Work that lands anywhere else is a fork nobody asked for,
and two lanes a day producing forks is how a desk ends up with several quants and no quant.

Close every pass in this order, and stop at the first step that cannot be completed honestly:

1. **Reconcile, never overwrite.** The live desk's branch receives the box's own hourly state
   commits. Fetch it and merge — you are joining a history that moved while you worked, not
   replacing it. If a merge conflicts on live trading code, **stop** (law 3) and report it: two
   histories disagreeing about the money path is the one thing a pass may not settle.
2. **Targeted stages only.** Every path you stage is a path you named (law 5). Untracked logs,
   caches and `data/secrets/` never enter a commit.
3. **One tree, both branches.** The working branch and the branch the box pulls must end the pass
   at the same tree. A change that reaches one and not the other is a change that will be
   silently reverted by the next sync.
4. **Seal alone.** `RELEASE.json` is committed by itself, after the code it describes. A seal
   sharing a commit with the code it seals cannot be checked against it.
5. **Verify identity, do not assume it.** `running SHA == RELEASE.code_sha == signed money-path
   SHA`. Run the check and read its output. If it is not true, the box is executing code that was
   never sealed, and that outranks every other finding on the board.
6. **Confirm the box can adopt.** A tree that is perfect on the branch and unreachable by the box
   has changed nothing. Verify the sync's next pull will fast-forward.

**Unified means one canonical history, one seal, one identity — not a merged pile.** If some of
your work cannot be landed cleanly, land what can be, and report exactly what is still outstanding
and why. An honest partial close beats a merge that made the tree agree by discarding something.

## XI. Stop conditions

Stop and report rather than continue when:

- the box cannot adopt code (nothing downstream is fixable);
- release identity is broken (the running code is not the sealed code);
- a repair would require loosening a gate or touching sizing;
- two histories disagree about live trading code.

Ending a pass early with a clear reason is a result. Grinding past a stop condition is how an
autonomous desk does damage faster than a human could.
