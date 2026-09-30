# Delegation protocol: who owns what, what goes where, how the operator audits

The desk is run by a team of AI agents with one human principal. Research is a coordination
problem before it is a coding problem, so this file is the contract between the agents. Every
agent (the Claude project coordinator, Claude thread sessions, the Claude session on the box, the
desktop Claude session and Codex) reads it before non-trivial work. `CLAUDE.md` and `AGENTS.md`
point here.

## 1. Roles

| Role | Who | Owns | Never does |
|---|---|---|---|
| Principal | zuck | Goals, standing orders, anything physically impossible without a human | Approvals of routine work. The desk runs without them |
| Portfolio manager of agents | Project coordinator (Claude) | Triage, one owner per task, forks decided on the recommended default, project memory | Code, merges, speaking inside a thread it does not own |
| Lane owner | One thread session per lane (table below) | Its lane's code, PRs, patches, journal rows, driving its PRs to green | Editing another lane's files. It hands them to the owner through the coordinator |
| Box operator | Claude on the trading box (Remote Control) | Read-only measurement of live state; box-side commands the lanes hand it | Mutating SSH or edits to the box's ledgers from origin |
| Desktop signer | Desktop Claude session, Remote Control | Sealed and money-path patches (allocator, promoter, gateway, sizing, judge, ci.yml) and merges the cloud classifier refuses | Anything not listed in `/mnt/project-files/patches/DESKTOP_PASS2_STATUS.md` |
| Midnight lane | Codex | The 00:00 CRO cycle (`docs/cro/CRO_CYCLE.md`) | n/a. Claude lanes never redo or re-check Codex's fixes |

## 2. Lanes and owners (one owner each; the journal records any change)

| Lane | Owner thread | Scope |
|---|---|---|
| Breadth and throughput | "Breadth and tier assessment" | Judging capacity, producers, datasets, conversions, cross-sectional books, alt data, the 24/7 media, news and macro factory |
| Research institution | "Tier S research institution build" | Orthogonality, occupancy, null labs, PIT, the Tier S door |
| Truth discipline | "Institutional truth discipline fixes" | Audit list, CI, order door, chaos lab, defect bank |
| Sizing and losses | "MT5 and E8 losses root cause" | Survival-max Kelly wiring into Fusion and E8 sizing |
| Control room | "Live control room layer" | Regime classifier as a sizing input, the allocator's regime inputs, bench-to-capital bridge, this protocol and `context/` |
| Graph representation | "Asian quant practices gap check" | GNN and graph families |
| Release and seals | "Release signing and canon hashes"; desktop pass | Manifests, canon hashes, sealed restores |
| Completion audit | "Independent blueprint completion audit" | Strict DONE verdicts on every builder batch |

## 3. What goes to the repo and what stays in chat

Written to the repo, because a later agent will need it:

- **A decision that changes what the desk does**: one row in `context/decision_journal.jsonl`
  (`python scripts/context.py decide ...`) with evidence pointers (paths, `sha:`, `pr:`, `url:`).
  Standing orders, sizing rules, admission verdicts, a lane handover and a refused item all
  count. A row that is later wrong is superseded by a new row (`--supersedes`), never edited.
- **Why a live sleeve exists**: `context/sleeves/<name>.md`, one per LIVE or STANDBY sleeve,
  created by `python scripts/context.py rationale --sync`. The generated block is refreshed from
  `desks/mt5/data/sleeves.json`. The thesis, who is on the other side, the kill criterion and
  the regime notes are written by whoever promotes or investigates the sleeve.
- **A measured result**: the artifact under `desks/mt5/reports/` that the code wrote. A number in
  chat without an artifact behind it is not evidence.
- **A lesson**: `scripts/learn.py add` (the 100%-retention corpus, `docs/desk_lessons.jsonl`).

Kept in chat: progress, questions, drafts, anything that stops being true within a day.

The box never writes under `context/`. `libs.ops.release` treats that folder as code, so a
box-side write would dirty the tree and refuse the seal. Box-generated summaries go to
`desks/mt5/reports/` (for example `OPERATOR_DIGEST.md`).

## 4. How the operator audits agent work without re-reading it

1. Read one page: `desks/mt5/reports/OPERATOR_DIGEST.md` on the box, or `context/DIGEST.md` on
   origin. It shows the control room state, the regime contract verdict, the bench-to-capital
   funnel with missed growth, memory health and the last 20 decisions with their evidence.
2. `python scripts/context.py verify` exits 1 if any journal row is malformed or cites a path
   that does not exist. An agent's claim that cannot point at a file, commit or PR is not a claim.
3. Spot-check one row per day: open its first evidence pointer. The admission rule (a subsystem
   ships only with a measured contract showing gain) means every capital-affecting row points at
   a contract artifact with a verdict field.
4. The strict completion audit thread re-derives DONE from the repo. Builders relay each batch to it.

## 5. Handoffs between agents

- A lane that needs a file another lane owns writes its change to a new file and sends it to the
  owner through the coordinator. It never edits the owner's file.
- Money-path and sealed edits (allocator, promoter, gateway, sizing, judge, ci.yml) go as tested
  patches under `/mnt/project-files/patches/` and a row in `DESKTOP_PASS2_STATUS.md`. The desktop
  pass applies them. A cloud refusal is recorded BLOCKED with its reason and never routed around.
- PRs merge once their CI failures are a subset of the live branch's. A refusal of the merge
  goes to the desktop merge queue.

## 6. Standing orders every agent carries

Autonomy with no approval asks. Never reduce mining, research or aggressiveness. Sizing is the
maximum E[log W] inside the survival limits. MT5/Fusion universe only. Absence of evidence is
UNMEASURED, never a clean pass. Full text: `docs/LAWS.md`, `docs/GROWTH_GOVERNANCE.md`.
