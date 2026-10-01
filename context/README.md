# context/ -- the desk's research memory for agents

Read this folder before non-trivial work. Every agent writes to it the moment its work changes
what the desk does. Chat is not memory, and a session that ends takes its chat with it.

| File | What it holds | Who writes it |
|---|---|---|
| `DELEGATION_PROTOCOL.md` | Roles, lane owners, what goes to the repo and what stays in chat, and how the operator audits | The control-room lane. Changes are journalled |
| `decision_journal.jsonl` | One row per decision that changes what the desk does, with evidence pointers | Any agent: `python scripts/context.py decide ...` |
| `sleeves/<name>.md` | Why each LIVE or STANDBY sleeve exists: thesis, the other side, kill criterion, regime notes | `python scripts/context.py rationale --sync` creates it. Whoever promotes or investigates the sleeve writes the thesis |
| `DIGEST.md` | The operator's one-page audit, derived | `python scripts/context.py digest`. Never edit by hand |

Read order for a fresh session: `DELEGATION_PROTOCOL.md`, then `python scripts/context.py show`
(the last 20 decisions), then the sleeve files for anything you are about to touch.

Rules:

- Append, never rewrite. A wrong journal row is superseded by a new row with `--supersedes`.
- Evidence is a pointer (repo path, `path:line`, `sha:`, `pr:`, `url:`, `/mnt/project-files/...`).
  `python scripts/context.py verify` fails on a malformed row or a repo path that does not exist,
  and CI runs it (`tests/research/test_context_memory.py`).
- The box never writes here. This folder is code to `libs.ops.release`. The box's daily digest
  goes to `desks/mt5/reports/OPERATOR_DIGEST.md`.
- Lessons (what went wrong and the rule it taught) still go to `scripts/learn.py`; the journal is
  for decisions.
