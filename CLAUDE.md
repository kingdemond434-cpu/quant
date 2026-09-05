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

## COMMITTING CODE FROM THIS BOX (read this before your first commit)

`ops/githooks/pre-commit` runs `moneypath_precommit_guard.py`, whose FIRST layer fires whenever
`SSH_CONNECTION` is set -- which it is for every Claude session here. It **unstages your staged
`desks/mt5/**/*.py` change and `git checkout HEAD` over your working copy**, then lets the commit
succeed with the file silently absent. It is not a bug: an hourly Dell-side sync (`Codex mt5 desk
hourly sync`, still running) once scp'd stale code over `desks/mt5` and committed it, removing
1,078 lines from `gateway.py`. The guard is what stops that.

It cannot tell your session from that sync, so YOUR code edits are reverted too:

```bash
QUANT_ALLOW_SSH_PY=1 git commit -m "..."
```

Measured 2026-09-04: four attempts at one `shadow_forward.py` fix were silently reverted this way,
and one "shipped and hash-verified identical" check compared two files that had BOTH been reverted.
If a `.py` edit you just made is missing from disk, this is why. Sibling overrides for the other
two layers: `QUANT_ALLOW_EVIDENCE_FALL=1`, `ALLOW_PROTECTED_RECORD_LOSS=1`.

## MT5 UNIVERSE MANDATE (2026-08-18, principal's standing order)

The desk's primary market universe is the full MT5/Fusion Markets universe: FX
majors/crosses/exotics, gold (XAUUSD), silver, metals, equity indices, energy, soft commodities,
US share CFDs. **No crypto-exchange universe (Binance/Bybit/OKX/Hyperliquid etc.) may EVER be
hunted again** -- no miner, hunter, query, channel list, scoring vocabulary or research mandate
may target crypto-exchange-native opportunities. Fusion-executable crypto CFDs are part of the
MT5 universe; crypto reference data may be used only WHEN it informs an MT5 instrument, never as
a hunted universe of its own.

## ONE CODE, TWO BOXES (2026-09-05)

The VPS (95.216.191.70, `quant`, `/home/quant/quant-platform`, branch `desk-sync-clean`) runs the
research pipeline, the fences and the dashboard. The Windows trading box (Contabo, `C:\opt\quant`,
branch `claude/llm-auto-upgrade-verify-gcjac3`) runs the gateway, the forward clocks and the
promoter. The two branches were reconciled on 2026-09-05 so they carry the SAME code; the box's
branch differs only by the state files the box commits. Every merge to `desk-sync-clean` must be
followed by a merge into the box's branch -- code that lands on one branch only is inert on the
box that trades, and that is how certificates and forward clocks were lost before.

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

## GROWTH GOVERNANCE (principal's standing order, 2026-09-04 — binding on every session)

Two rules, applied everywhere, now and in future, fenced by `scripts/check_growth_governance.py`
at every law-gate boundary and `scripts/check_heat_floor_wiring.py` on the box. Full text:
`docs/GROWTH_GOVERNANCE.md`.

- **Rule 1.** Every risk reduction mechanism must prove that it increases robust forward E[log W].
- **Rule 2.** Every strong opportunity must be allowed to increase capital above normal when the evidence supports it.

Timid is not risk-aware. Never read restraint language (minimise, only, never, bounded) as a
licence to do less; never add a veto, cap, shrinkage or gate without its missed-growth ledger
line (`libs/portfolio/rails.py`, `research/missed_growth.py`); every capital modifier must be
two-sided (`libs/portfolio/capital_modifiers.py`). The heat law: **20% floor, flat, 24/7;
growth free above it to the 30% ceiling; the resolved heat is filled, never reported short; the
gateway deploys the allocator's fractions un-re-shrunk and falls back to the best baseline at
the floor when the proof is stale.** Research is anti-timid (weak public claims are hypotheses,
never privileged); capital is evidence-hard (nothing gets authority for sounding institutional).
- **DEEP-FOREST MINING (2026-09-04, principal standing order)** — the deep Chinese web is worth
  mining to exhaustion: competition records (期货日报实盘大赛, 蓝海密剑), 七禾网/私募排排网 trader
  interviews, 聚宽/优矿/米筐/BigQuant communities, 知乎/CSDN/雪球, Gitee, Bilibili transcripts,
  微信 via 搜狗, the futures forums — because even a dubious trader story names a testable
  mechanism. The world crawler and `desks/mt5/research/deep_forest_miner.py` mine these (and the
  JP/KR/RU sibling forests) for verbatim claims, map instruments to MT5 analogues, and push every
  claim to the gauntlet through the deepening worker (`story_mechanism`). Grounds live in
  `desks/mt5/data/deep_forest_sources.json`; new grounds are added there, never hard-coded.
- **AUTOMATIC PROMOTION (2026-09-04, principal standing order)** — "all promotion candidates get
  into the live account immediately, no waiting, no permission, fully automatically, always."
  Every forward lane (main shadow, qquant, scalp) feeds `research/promoter.py`; a candidate whose
  exact spec holds a ten-gate certificate is written LIVE on the same cycle its clock matures,
  the gateway trades it on its next pass, and capital is the allocator's decision by ΔE[log W].
  No champion wait, no kill-by-comparison, no human act. Retirement stays automatic too.
