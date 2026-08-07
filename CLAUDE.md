# quant — orientation for a fresh context

This repo is an **Obsidian vault** (`.obsidian/`, content in `docs/`) as well as a codebase. The
vault is ACTIVE institutional memory, not archive. **Nothing loads it for you.** A new session — or
a session after compaction — starts blind to every standing law below unless it reads them. This
file exists because that was the gap: the vault was declared active and nothing pointed here.

Keep this file SHORT. It sits in every context window, so it is an INDEX, never a copy.

## Read before acting

| When | Read |
|---|---|
| any non-trivial change | `docs/CONSTITUTION.md` — L1.x standing laws, hash-locked core |
| deciding what to work on | `docs/GAP_REGISTER.md` — ranked open defects; **row 91 is the current top item** |
| touching research/studies | `docs/research/*PREREGISTRATION.md` — kill criteria bind BEFORE a run |
| adding a doc under `docs/` | `docs/research/ARTIFACT_GOVERNANCE.md` — every artifact must be claimed by a law, on arrival |
| data sources | `docs/research/data_axis_watchlist.md`, `scripts/source_backlog_next.py` |

## Laws most often violated by a fresh session

- **Coverage floors ratchet UP only** (`docs/research/COVERAGE_RATCHET.json`, L1.50). A floor edited
  to fit a measurement is not a floor. Repo and money path are tracked SEPARATELY.
- **UNMEASURED is a real answer** (L1.28a). Absence must never resolve to a clean verdict — that is
  WS-005, the desk's most-repeated defect class.
- **A gate that never ran is a claim the desk cannot cash** (L1.49).
- **"Exhausted" requires per-axis evidence** (L1.51) — for hypotheses as well as sources.
- **Tier-3 ruin rail** (`scripts/run_deadman_switch.py`) is never modified autonomously. Arming live
  trading is the principal's act. It is deliberately absent from mypy's `files`.
- `data/secrets/**` never leaves the box, and no tool ever prints a key.

## Gates (all three, before any push)

```
ruff check .          # NOT `ruff | tail` — tail exits 0 whatever ruff found
python -m mypy        # bare mypy; uses files=[] from pyproject, not --strict .
python -m pytest --cov=libs --cov-branch --cov-report=json:coverage.json
python scripts/check_coverage_floors.py --report coverage.json
```

`filterwarnings = error` is set: a RuntimeWarning is a test failure.

Use `python -m mypy`, not `mypy` — the PATH binary is a uv tool install that cannot see project deps.

## Current state (update when it changes)

- Coverage: repo **92.46%**, money path **70.45%** over 748 stmts. Both floors at those values.
- Research: **16,560 pre-registered trials, 0 executed.** 16,200 of them run today via
  `bash ops/run_study_on_vps.sh failed_breakout` — on the VPS, where the data and the venue are
  reachable. This analysis clone is network-policy-denied for venue hosts (GAP row 91).
- **434 candidates, 0 survivors.** Attribution and the maturity ladder correctly return NOT MEASURED
  until experiments execute. Do not read that as "nothing works" — read it as "nothing has run".
