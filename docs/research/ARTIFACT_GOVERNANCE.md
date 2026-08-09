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

| `docs/research/THREE_MECHANISM_PREREGISTRATION.md` | **TERMINAL** | Same class and the same reasoning as the row above: a pre-registration is terminal by definition. It fixes the three mechanisms the desk will run, their shared trial budget, and the crucial distinction between a TRIAL (can be promoted, deflates the Sharpe) and a CONTROL (pre-declared expected-to-fail, cannot promote anything, measures the harness's false-positive rate instead). Editing it to add a fourth mechanism would void the shared deflation, which is the whole thing it exists to protect. Superseded only by a NEW pre-registration with its own date. |

**Net: 3 cadenced, 5 doctrine, 7 terminal. Zero remain ungoverned.**

A note on why this row was written the same day the artifact was: an artifact classified late is
an artifact that was ungoverned for however long "late" was, and the register's own rationale for
existing is that the NEXT artifact arrives ungoverned by default. Writing the runbook and leaving
it for a later sweep would have reproduced, in one session, the exact failure this file was
created to end.

### Added 2026-08-04 (the branch's own 18 — three laws' scope decisions landed together)

`artifact-ungoverned` fired on **18** docs artifacts. Thirteen of them are one generated class and
are claimed as a class in `max_audit._TERMINAL_ARTIFACTS` (a trailing-slash claim, so `shard_14`
inherits the decision instead of arriving ungoverned); `docs/research/recent_changes.md` and
`docs/research/TIER1_BENCHMARK.md` are likewise recorded in code, because a *directory class* and
an *enforced staleness clock* are the two things this register's prose cannot express — the first
has no syntax here, and the second would be a promise with no clock behind it, which is the exact
failure §36 exists to end. The three below are classified here, where the reasoning belongs.

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/CONSTITUTION.md` | **DOCTRINE** | The governing law of the organism, permanent by its own first line and amendable only by principal order. It has no producer and no cadence — a clock cannot make a constitution truer — but it is emphatically not unchecked: its core is hash-locked in `data/constitution_core.lock` and enforced by `scripts/check_constitution_core.py`, with `scripts/check_law_families.py` and `scripts/check_timidity_language.py` reading it every cycle. It surfaced here only because §36(2) asks whether `max_audit.py`'s own source names a file, and the checks that govern this one live in their own scripts. The falsifier for this row is the standing one below: an edit not traceable to a principal decision in the ledger is a governance breach. | never |
| `docs/DISCRETIONARY_DESK.md` | **DOCTRINE** | The standing charter of the discretionary sleeve — its venue, its evidence ladder, its own place in the law gate. Cited as the L1.6 playbook evidence in `scripts/build_enforcement_matrix.py` and read by `scripts/run_cost_hunt.py`. It changes when the sleeve's *design* changes, never on a schedule; the sleeve's live state is carried by its organs and the register, so a staleness floor here would page about a document while the thing it describes is fine. | never |
| `docs/research/RESEARCH_EXCELLENCE.md` | **DOCTRINE** | Principal directive of 2026-07-28 binding the data, research and exploration layers — the *how to research* half of the pair whose *what to build* half, `OPERATING_DOCTRINE.md`, is already DOCTRINE above. `scripts/doctrine.py` loads the two together in a single list, so classifying one and leaving the other unclaimed was an omission rather than a decision. | never |

**Running net: 3 cadenced, 8 doctrine, 7 terminal in this register, plus three decisions recorded
in `max_audit.py` because they need code to be real (`docs/audit_shards/` as a class,
`recent_changes.md` as terminal, `TIER1_BENCHMARK.md` as an 8-day enforced clock). Zero remain
ungoverned.**

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

### Added 2026-08-06 (this session's own artifact, classified on arrival — the rule this register keeps having to re-apply to its author)

`artifact-ungoverned` fired on **1** artifact, `docs/RESEARCH_DATA_TRANSPORT.md`, written earlier
in this same session. Worth naming plainly rather than fixing quietly: the register's own standard
is "classified on arrival, not later", and it was not — the check caught it, on a branch whose
author had already read this file. That is the register working, and it is also the third time an
artifact created by the session doing the governing arrived ungoverned. **The default is
ungoverned, and no amount of knowing that changes the default** — which is precisely the argument
for the check existing rather than for asking authors to remember.

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/RESEARCH_DATA_TRANSPORT.md` | **TERMINAL** | Same class and the same reasoning as `docs/VPS_BRINGUP.md` and `docs/RECORDER_DEPLOY.md` directly above: it records one deployment decision under one constraint. The constraint is that the research data lives in `data/` on the VPS, `.gitignore` excludes `data/*`, and every analysis container is a fresh clone — so a study cannot reach its own inputs. The document names the two lawful routes (run the study on the VPS via `ops/run_study_on_vps.sh`, or ship a periodic snapshot via `ops/snapshot_research_data.sh` → `ops/restore_research_data.sh`) and the one hard exclusion, `data/secrets/**`, which must never enter a snapshot. It has no producer and no cadence; a clock cannot make a runbook true, so a staleness floor would be theatre. **Its superseding condition, named rather than dated:** the day the research data reaches analysis clones by any other route — a mounted volume, an object store the clone can read directly, a data service — this document describes a transport that no longer exists, and a new runbook must supersede it by name. That condition, not an age, retires it. | n/a |

**Running net: 3 cadenced, 8 doctrine, 8 terminal in this register, plus the three decisions
recorded in `max_audit.py` because they need code to be real. Zero remain ungoverned.**

### Added 2026-08-07 (a third pre-registration, classified on arrival)

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/research/ETHBTC_ROTATION_PREREGISTRATION.md` | **TERMINAL** | Same class and the same reasoning as the two pre-registrations above: a pre-registration is terminal **by definition, and that is the point of one**. It fixes kill criteria and a trial budget BEFORE the run, so refreshing it in place would destroy the only property that makes it evidence — criteria chosen after seeing a result are not criteria. It is superseded by its own RESULT, never edited: the run either fires a kill criterion or it does not, and the document stands as the record of what was promised beforehand either way. An amendment (as `FAILED_BREAKOUT_PREREGISTRATION.md` took) is appended and dated, never a rewrite, and it moves the shared deflation budget for all three. | n/a |

### Added 2026-08-07 (fourth pre-registration)

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/research/MANAGEMENT_SWEEP_PREREGISTRATION.md` | **TERMINAL** | Same class and reasoning as the three pre-registrations above: terminal by definition, because criteria chosen after seeing a result are not criteria. Superseded by its own RESULT, never edited; amendments are appended and dated and move the shared deflation budget for all four. | n/a |

### Added 2026-08-07 (fifth pre-registration)

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/research/FULL_SWEEP_PREREGISTRATION.md` | **TERMINAL** | Same class as the four pre-registrations above, and the declaration ordering is load-bearing here in a way it is not elsewhere: the universe size and the bar are fixed BEFORE any cell is evaluated, which is the entire statistical basis for a blind 898,560-cell sweep. Editing it after a result would not merely weaken the document, it would void the study. Superseded by its own result. | n/a |
| `docs/research/crypto_source_seeds.md` | **LIVING** | Claimed by L1.52 (information mining is permanently active) and by the miners' own anti-breadth-theater rule. It is deliberately NOT the catalogue: the catalogue (`data_axis_watchlist.md`) carries graded cards that owe verification decisions, and at 8 pending of 18 the desk's measured bottleneck is verification, not cataloguing. A seed map carries no verification debt, so it can hold 450 grounds without making that bottleneck worse — and a source only becomes a card by producing something. Grows as `kimi_hunter` discovers grounds absent from it; the list is seeds, never a ceiling. | n/a |

### Added 2026-08-09 (controller convergence mandate, classified on arrival)

| Artifact | Class | Rationale | Staleness floor |
|---|---|---|---|
| `docs/research/TIER1_CONTROLLER_MANDATE.md` | **DOCTRINE** | Principal-supplied standing controller law shared by Claude and Codex. It governs continuation, survivor conversion, open-world coverage, risk/statistical invariants, and atomic handoff of one persistent operation. It changes only by a later principal mandate; a cadence must execute it through the controller cycle, never rewrite it to look current. | never |