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

**Net: 3 cadenced, 3 doctrine, 2 terminal. Zero remain ungoverned.**

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
