# quant — orientation for a fresh context

This repo is an **Obsidian vault** (`.obsidian/`, content in `docs/`) as well as a codebase. The
vault is ACTIVE institutional memory, not archive. **Nothing loads it for you.** A new session — or
a session after compaction — starts blind to every standing law below unless it reads them. This
file exists because that was the gap: the vault was declared active and nothing pointed here.

Keep this file SHORT. It sits in every context window, so it is an INDEX, never a copy.

## Read before acting

| When | Read |
|---|---|
| any non-trivial change | `docs/MASTER_QUANT_CONSTITUTION.md` first; then `docs/CONSTITUTION.md`, its machine-enforced companion |
| deciding what to work on | `docs/GAP_REGISTER.md` — ranked open defects; **row 91 is the current top item** |
| touching research/studies | `docs/research/*PREREGISTRATION.md` — kill criteria bind BEFORE a run |
| adding a doc under `docs/` | `docs/research/ARTIFACT_GOVERNANCE.md` — every artifact must be claimed by a law, on arrival |
| data sources | `docs/research/data_axis_watchlist.md`, `scripts/source_backlog_next.py` |
| frontier / competitor / outlier hunting | `docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md` — standing principal law, all three seats |

## Search the vault before deciding — 208k lines, one hop

Do not grep blind, and do not decide something the desk already decided.

```
python scripts/vault_search.py "reduce_only close leg"          # humans + sessions
python scripts/vault_search.py --json --limit 20 "liquidation"  # cycles / audits / sweeps
```

Claude also has it as the `vault_search` MCP tool (`.mcp.json` -> `scripts/vault_mcp_server.py`).
Same index (`libs/research/vault_index.py`), so an organ and a session can never disagree about
what the vault says.

**LEXICAL (BM25), not semantic** — no embedding model is reachable from a network-denied clone. An
empty result means THESE TOKENS are absent, **not** that the question was never settled. Re-query
with the vocabulary the document itself would use.

## Laws most often violated by a fresh session

- **Coverage floors ratchet UP only** (`docs/research/COVERAGE_RATCHET.json`, L1.50). A floor edited
  to fit a measurement is not a floor. Repo and money path are tracked SEPARATELY.
- **UNMEASURED is a real answer** (L1.28a). Absence must never resolve to a clean verdict — that is
  WS-005, the desk's most-repeated defect class.
- **A gate that never ran is a claim the desk cannot cash** (L1.49).
- **"Exhausted" requires per-axis evidence** (L1.51) — for hypotheses as well as sources.
- **Never share a worktree with another live session** (R0423). Cron starts several: if session
  start printed `SHARED TREE`, either stage EXPLICIT PATHS on every commit (never `git commit -a`)
  or take your own — `git worktree add -b <branch> ../qp-<branch>` — and merge back. **Never
  `git stash`**: it restores to the index and a sibling can check the tree out from under you.
  Three recorded instances of a sibling's broad commit sweeping another session's staged files
  into an unrelated commit; the code survived every time, the rationale did not.
- **Tier-3 ruin rail** (`scripts/run_deadman_switch.py`) is never modified autonomously. Arming live
  trading is the principal's act. It is deliberately absent from mypy's `files`.
- `data/secrets/**` never leaves the box, and no tool ever prints a key.

## Gates (all four, before any push)

```
./ops/gates.sh          # the three fast gates, ~1 min — RUN THIS
./ops/gates.sh --full   # adds the suite + coverage floors (~60-80 min)
git config core.hooksPath ops/githooks   # once per clone: pre-push runs the fast gates
```

Equivalent by hand, if you need one step in isolation:

```
ruff check .          # NOT `ruff | tail` — tail exits 0 whatever ruff found
python -m pytest --co -q      # 8s. RUN THIS FIRST — see below
python -m mypy        # bare mypy; uses files=[] from pyproject, not --strict .
python -m pytest --cov=libs --cov-branch --cov-report=json:coverage.json
python scripts/check_coverage_floors.py --report coverage.json
```

**COLLECTION IS A SEPARATE GATE AND RUFF+MYPY DO NOT COVER IT.** An uncollectable module is not
a failing test — it is a test that does not run, and the suite reports it as an error count next
to a green pass count. mypy's `files` excludes `tests/`, and ruff does not resolve names, so a
dropped function or a changed return type passes both while the suite cannot start. That is how
the 08-09 merge shipped with the L1.6 Holm-bar fence reading `m=0 [REFUSED]` for four days, and
how three later batches landed with a test that raises `TypeError` on import of its own subject.
It costs **8 seconds**. There is no run too small for it.

(mypy over `tests/` was measured as the alternative and rejected on evidence: 6345 errors, ~550
with every style check off, and the `attr-defined` signal is drowned by `ast.AST` false positives
and legitimate monkeypatch access. Silencing that is not a gate.)

`filterwarnings = error` is set: a RuntimeWarning is a test failure.

Use `python -m mypy`, not `mypy` — the PATH binary is a uv tool install that cannot see project deps.

## Current state

**Not written here on purpose.** `.claude/desk-state.sh` runs at session start and prints coverage
vs floors, the OI/LS 40-day clock, study execution state and the top open gap rows -- READ LIVE from
the artifacts. A number typed into this file is correct the day it is typed and quietly wrong
afterwards, and a stale number in an always-loaded file is worse than none: it is confidently
misleading in every future session. This file holds the map; the hook holds the odometer.

If you did not see a `=== DESK STATE ===` block at session start, the hook did not run -- treat
every number you think you know as UNKNOWN and read the artifacts directly.
