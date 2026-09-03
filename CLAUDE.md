# quant — orientation for a fresh context

This repo is an **Obsidian vault** (`.obsidian/`, content in `docs/`) as well as a codebase. The
vault is ACTIVE institutional memory. **Nothing loads it for you** — a fresh or compacted session
starts blind to every standing law unless it reads them. Keep this file SHORT: it sits in every
context window, so it is an INDEX, never a copy.

## THE TWO GOVERNING DOCUMENTS (consolidation of 2026-08-25 — read these, they are short)

| Document | Governs |
|---|---|
| `docs/LAWS.md` | **Everyone and everything.** Universe (MT5/Fusion ONLY — crypto-exchange ground is never hunted again), objective, the full law compendium, survival rails, Tier-3 never-touch, promotion firewall, operating laws, enforcement wiring |
| `docs/RESEARCH.md` | **The whole research system** — every miner, hunter, digger, generator, screen, test: hunt space, sources and search discipline, track-record/leaderboard/championship mining, §33 conversion, validation gauntlet, survivor factory, cadence |

Everything else governance-shaped is a bannered ANNEX (unabridged detail, never standing orders);
`docs/MANDATE_COVERAGE.md` maps every document's disposition. The sealed immutable core lives in
`ops/principal_doctrine.txt` and is verified by `scripts/check_constitution_core.py` on every
law-gate run; per-study preregistrations under `docs/research/` still bind their studies.

## Search the vault before deciding — one hop

```
python scripts/vault_search.py "reduce_only close leg"          # humans + sessions
python scripts/vault_search.py --json --limit 20 "liquidation"  # cycles / audits / sweeps
```

Also the `vault_search` MCP tool. **LEXICAL (BM25), not semantic** — an empty result means THESE
TOKENS are absent, not that the question was never settled; re-query with the document's own
vocabulary. Do not decide something the desk already decided.

## Standing facts (box + branches)

- **VPS: `ubuntu-4gb-hel1-5`, Hetzner Helsinki, 95.216.191.70**, user `quant`, NO sudo by
  design. Non-root controls: `data/RECORDERS_OFF` idles all crypto recorders/listeners (set
  2026-08-25, permanent under the MT5 mandate); `~/.cloudflared/config.yml` ingress (emptied —
  the old crypto dashboard is retired). Root-owned crypto units (recorders, liquidations,
  cashcarry, deadman, tunnel, dashboard) idle harmlessly; final removal needs the console.
- **Tier-3 deadman rail** (`scripts/run_deadman_switch.py`): never modified autonomously.
  STANDING DEFECT: it watches retired crypto-testnet endpoints and protects no live MT5 risk —
  repointing is queued principal-gated work (LAWS §4).
- The MT5 desk lives in `desks/mt5/`; universe registry `desks/mt5/data/universe/universe.json`.
  Branch pointers rot — trust `git branch --show-current` and recent `git log`, not this file.

## Laws a fresh session most often violates (full set: LAWS §6)

- **UNWIRED OR IDLE IS A DEFECT (III.16)** — done means RUNS on a schedule and leaves an
  artifact; never report "built" as a status.
- **UNMEASURED is a real answer (L1.28a)** — absence never resolves to a clean verdict (WS-005).
- **Coverage floors ratchet UP only (L1.50); a gate that never ran is a claim the desk cannot
  cash (L1.49); "exhausted" requires per-axis evidence (L1.51).**
- **Never share a worktree with another live session (R0423)** — stage EXPLICIT PATHS, never
  `git commit -a`, never `git stash`.
- `data/secrets/**` never leaves the box; no tool ever prints a key.
- **COMMIT BEFORE YOU RUN PYTEST (R0748, measured 2026-09-03)** — a test writes to a
  tracked file, and the suite's integrity guard repairs it by restoring *git HEAD*, which
  silently reverts YOUR uncommitted edits in the same sweep. Its message reads identically
  whether the tree was clean or your work was just discarded. Gate, commit, then test.

## Gates (all four, before any push)

```
./ops/gates.sh          # the three fast gates, ~1 min — RUN THIS
./ops/gates.sh --full   # adds the suite + coverage floors (~60-80 min)
git config core.hooksPath ops/githooks   # once per clone
```

**COLLECTION IS A SEPARATE GATE:** `python -m pytest --co -q` costs 8 seconds and catches what
ruff+mypy cannot; there is no run too small for it. Use `python -m mypy` (never bare `mypy`).
`filterwarnings = error`: a RuntimeWarning is a test failure.

## Current state

**Not written here on purpose.** `.claude/desk-state.sh` prints coverage vs floors, study state
and top gap rows at session start, read LIVE from artifacts. If you did not see a
`=== DESK STATE ===` block, the hook did not run — treat every number you think you know as
UNKNOWN and read the artifacts directly.
