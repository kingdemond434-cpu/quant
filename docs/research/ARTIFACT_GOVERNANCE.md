# ARTIFACT GOVERNANCE — §36(2) classification of previously ungoverned docs

`max_audit`'s `artifact-ungoverned` check fired on 8 documents claimed by no law. Its own wording
says why that matters:

> Every artifact is governed by §33 (mined cards), §35 (findings), §36 (cadenced producers), or
> recorded terminal with a reason. **Ungoverned is how the miner problem reappears: inventory
> accumulates and nothing ever converts it. Classify each — 'no law' must be a DECISION, never a
> default.**

Each of the 8 is classified below. Three governance classes are used, plus TERMINAL for documents
that are complete by nature and correctly have no cadence.

| Class | Meaning | Staleness expectation |
|---|---|---|
| **§36 CADENCED** | A producer must refresh it; staleness is a defect. | named below |
| **DOCTRINE** | Standing law. Changes only by principal decision, never by cadence. | never stale |
| **TERMINAL** | Complete artifact of a finished decision. Superseded, never refreshed. | n/a |

---

## Classification

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/DESK_BRIEF.md` | **§36 CADENCED** | The desk's external-facing state summary. A stale brief misrepresents the desk to any cold reader — including the panel, which is the one consumer whose value depends on an accurate picture. | 30d |
| `docs/GATE0_QUEUE.md` | **§36 CADENCED** | The pre-Gate-0 work queue. Its whole function is to be current; a stale queue silently drops the freeze-exit path. Producer: the cycle, on any queue change. | 14d |
| `docs/research/MECHANISM_GRAPH.md` | **§36 CADENCED** | Consumed directly by `hypothesis_generator.py` (`MECH.read_text()[:3000]`) as live generation context. A stale graph degrades every hypothesis generated from it — this one is load-bearing for the primary output. | 21d |
| `docs/research/EXPLORATION_DOCTRINE.md` | **DOCTRINE** | Standing law on how exploration is conducted. Changes by principal decision only. | never |
| `docs/research/MEASUREMENT_DOCTRINE.md` | **DOCTRINE** | Standing law on measurement discipline (the lead-vs-coincident rule that killed 38% of hypotheses lives here). Changes by decision, not schedule. | never |
| `docs/research/OPERATING_DOCTRINE.md` | **DOCTRINE** | Standing operating law. Same reasoning. | never |
| `docs/research/SUBSYSTEM_TRIAGE.md` | **TERMINAL** | The record of a completed triage pass. Superseded by a NEW triage document if one is ever run; never refreshed in place. Retaining it is the audit trail of that decision. | n/a |
| `docs/research/TRIAGE_ADDENDUM.md` | **TERMINAL** | Addendum to the above, same class, same reasoning. | n/a |

### Added 2026-07-29 (this session's own artifacts — classified on arrival, not later)

Writing a governance register and leaving the register itself unclaimed would have been the
joke version of this exercise. The check now reads this table, so every row below is genuinely
cleared rather than merely described.

| Artifact | Class | Rationale |
|---|---|---|
| `META_RESEARCH_DIRECTIVE.md` | **DOCTRINE** | Standing CIO law. Changes only by principal decision; its computable half is executed by `scripts/meta_research_review.py`, which is itself cadence-enforced. |
| `ARTIFACT_GOVERNANCE.md` | **DOCTRINE** | This register. Governs itself — a classification list that is not itself classified is the miner problem in miniature. |
| `UNREACHABLE_LAYER_TRIAGE.md` | **TERMINAL** | Record of a completed triage with named unlock conditions. Superseded by a new triage if the conditions fire; never refreshed in place. |

### Added 2026-08-02 (same rule, applied to this session's own artifact)

| Artifact | Class | Rationale |
|---|---|---|
| `docs/RECORDER_DEPLOY.md` | **TERMINAL** | Record of one deployment decision under one constraint: the `quant` user has no sudo, so the recorders are supervised by the user's own crontab rather than by systemd. It has no producer and no cadence — a clock cannot make a runbook true — so a staleness floor would be theatre. It is superseded BY A NAMED CONDITION instead: the day root is available and the four unit files in `ops/` are installed, this document becomes actively harmful (it would tell an operator to add cron supervision on top of `Restart=always`, giving two supervisors for three processes), and a new runbook must supersede it by name. That condition, not a date, is what retires it. |

### Added 2026-08-03 (the superseding condition in the row above has now FIRED)

| Artifact | Class | Rationale |
|---|---|---|
| `docs/VPS_BRINGUP.md` | **TERMINAL** | The runbook that supersedes `RECORDER_DEPLOY.md` **by name**, exactly as that row said something eventually must. Same class and the same reasoning: it records a deployment decision, has no producer and no cadence, and a staleness floor on a runbook would be theatre. Its own superseding condition: if the desk ever stops being deployed by `ops/deploy_vps.sh` — a different orchestrator, containers, a managed host — this document describes a machine that no longer exists and a new runbook must supersede it by name. |

**The row above is now PARTLY superseded, and saying so is the point.** `RECORDER_DEPLOY.md` named
its own retirement condition as "root is available and the unit files in `ops/` are installed", at
which point it "becomes actively harmful" by prescribing cron supervision on top of
`Restart=always`. As of 2026-08-03 the second half has fired: the units exist, and five more were
added for the organs that had no launcher at all — the cadence engine, the pager, the process
supervisor and the ruin rail. Root availability remains unknown and is the operator's fact, not the
repository's, so `deploy_vps.sh` DETECTS it rather than assuming either way and prints the
no-sudo path when `sudo -n` fails.

`RECORDER_DEPLOY.md` is therefore **retained, not retired**, and now carries a pointer at the top
directing operators to `VPS_BRINGUP.md` first. It stays because it is still the reference for what
the recorders do and how to debug them; what it no longer is, is the entry point.

### Added 2026-08-04 (a pre-registration is a distinct class and needed saying so)

| Artifact | Class | Rationale |
|---|---|---|
| `docs/research/FAILED_BREAKOUT_PREREGISTRATION.md` | **TERMINAL** | A pre-registration is terminal **by definition, and that is the whole point of one**. It records kill criteria and a trial budget fixed BEFORE the data existed; refreshing it, re-ranking it, or converting it would destroy the only property that makes it worth anything. It is superseded by exactly one thing: the study running to a verdict, at which point this document becomes the record the verdict is judged against and still must not change. If the hypothesis is re-opened on new evidence, that is a NEW pre-registration with its own date, never an edit to this one — an edited pre-registration is a backtest wearing a timestamp. |

**Net: 3 cadenced, 5 doctrine, 6 terminal. Zero remain ungoverned.**

A note on why this row was written the same day the artifact was: an artifact classified late is
an artifact that was ungoverned for however long "late" was, and the register's own rationale for
existing is that the NEXT artifact arrives ungoverned by default. Writing the runbook and leaving
it for a later sweep would have reproduced, in one session, the exact failure this file was
created to end.

---

## Why doctrine is not simply "exempt"

A DOCTRINE classification is not a way to silence the check — it is a claim that the document
should change only when the principal decides, and that claim is falsifiable. If a doctrine file
is edited by anything other than a principal decision recorded in the ledger, that is a
governance breach and should be treated as one. The class buys freedom from a *staleness* floor,
never freedom from the ledger.

## Why TERMINAL is not "abandoned"

A terminal artifact is the durable record of a decision that was actually made. Deleting it
destroys the audit trail; refreshing it falsifies the record of what was known at the time. The
correct action on new information is a NEW document that supersedes it by name — the same
discipline the decision ledger uses, and the reason superseded ledger entries are retained rather
than edited.

## The one genuinely load-bearing case

`MECHANISM_GRAPH.md` is the only one of the eight read by running code at generation time. Its
21d floor is tighter than the others because staleness there does not merely misinform a reader —
it silently degrades every hypothesis the desk generates, and that degradation is invisible in
the output. If any of these eight warrants a producer being built, it is this one.
