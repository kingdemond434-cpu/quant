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
- **The MT5 box PULLS (2026-09-08).** `desks/mt5/scripts/Adopt-And-Seal.ps1`, registered as
  `MT5-AdoptRelease` (hourly at :12, between the :05 and :20 sync slots; both writers hold the
  named mutex `Local\MT5-GitWriter`), lands the branch's tree in place,
  re-seals only on a clean tree, commits `RELEASE.json` alone and restarts the gateway. Until it
  was written the box only ever pushed, and a day of fixes sat on origin while the gateway ran a
  tree that could not import `libs`. If the box is not adopting, that task is the first thing to
  check. One-time: `desks\mt5\scripts\install_adopt_release_task.ps1` registers it AND runs the
  first adoption immediately (re-running the whole installer on a live box has failed with
  "Access is denied" on the S4U principals; this touches one task).
- **Box memory: 8 GB by every counter the box has published; the principal says 80 GB.** Four
  independent readings agree on 8 GB (`stall_watch` 2026-08-28: free RAM cycling 3329→448 MB
  around a 3.7 GB searcher; 2026-09-08: `phys 142MB free / virt 11719MB`; a page file "full at
  12,756MB"; `external_gauntlet` 2026-09-05: one 4882 MB process "leaving 280MB free"). An
  80 GB box does not starve on a 4.9 GB process; **80 GB is the DISK** (the Hetzner CX32 shape:
  4 vCPU / 8 GB / 80 GB). Never size a floor off the claim: the 8192 MB gauntlet floor of
  2026-09-08 morning would have refused every hourly sweep (`rc=75`) and was reverted the same
  day. `stall_watch.json` now publishes `memory.total_phys_mb` and the six largest commit
  holders, so the dashboard answers this; read it before arguing it.
- **Reaching the box without pasting: Claude Code ON the box, in Remote Control.** This cloud
  container has no SSH to anything (HTTPS through its proxy only), so an SSH server on the box
  helps the principal's laptop, never a cloud session. The principal was told 2026-09-08 to run
  `irm https://claude.ai/install.ps1 | iex`, `cd C:\opt\quant`, `claude`, `/login`,
  `/remote-control` over RDP. Once that session exists, `/list-agents` here shows it and
  SendMessage reaches it: hand it the box commands (install_adopt_release_task.ps1,
  check_gold_live.py, task tables) instead of handing them to the principal.
- **The seven sleeves' clocks (traced 2026-09-08).** The four XAUUSD.asia registry rows are
  forward clocks that all map to ONE gateway window, `gold_asia`, which places at 07:00 broker
  (= 04:00 UTC in summer; the venue is UTC+3 in summer, the measured file's +2 is the winter
  anchor). `gold_london_am` places at 10:00 UTC and `gold_afternoon` at 14:00 UTC. GOLD_RETIRED
  entries are RE-DERIVED by the promoter against the account in hand, on POSITIVE evidence only
  (a degenerate admissible series, or the file holding the recorded n rows all stamped to another
  account); an empty, short, unreadable or unstamped ledger never voids -- the entry stands
  (voids go to GOLD_RETIRED_VOIDED.json and the window is re-judged on the same pass). The three promoted scalp sleeves reach the gateway only as LIVE rows in
  data/sleeves.json; that needs a MEASURED heavy admission scan (MT5-Hourly now runs heavy when
  the last scan is missing or >2h old) and two admitting promoter readings for a STANDBY row.
  CLOSE_HOUR (19:30 UTC) closes the gold book only; the scalp lane runs to its own time exit.
- **The box's state is the box's.** `Adopt-Release.ps1` keeps every state path (the
  `STATE_PREFIXES` in `libs/ops/release.py`, minus `docs/`) that the box changed since it
  diverged, adopts code and origin-only inputs, and records the merge. The next push carries the
  box's state up and REVERTS any origin edit to a state path both sides changed — so never fix
  the box by editing a ledger/registry/docket on origin; fix the organ that writes it.
- **TWO BRANCHES, ONE SILENT ABORT (measured 2026-09-08).** The VPS checks out and commits to
  `desk-sync-clean` (author "Codex"; `ops/run_seed_miners_hourly.sh` rebase-pulls and pushes it
  at :22, `ops/run_deepseek_factory.sh` at :20). `quant-desk-refresh` merges the desk branch
  INTO it every 3 min (`ops/refresh_desk_state.sh`) and ABORTS on conflict with no artifact.
  The two diverged 2026-09-06 17:08 → 2026-09-08 21:00 on three paths (two box-written state
  stumps the VPS only holds as scp copies from `ops/pull_desk_state.sh`, and hourly_cycle.py);
  ~960 silent aborts, 57 VPS commits (4,822 intelligence artifacts) never reached the box's
  compiler, 147 desk commits never ran on the VPS. Converged in 7264e420. RULE: after any commit
  that touches a path both machines write, run `git merge-base --is-ancestor origin/<desk>
  origin/desk-sync-clean`; if false, merge here (desk first-parent, box versions of box-written
  state) and push the SAME commit to `desk-sync-clean`, the desk branch and seats-and-chain.
  `quant-unit-health` (every 10 min) copies `ops/quant-*.{service,timer}` into the VPS's
  systemd user dir and daemon-reloads, so a pushed timer change is live within the hour of the
  VPS taking the commit; it never enables or disables units.
- **THE VPS IS ALIVE AND ITS CHECKOUT IS BEHIND (measured 2026-09-09 01:36 UTC, over HTTPS —
  this container has no SSH).** `dash.quanttt.xyz/desk_state.json` regenerates continuously
  (`generated_at` current to the minute, `breadth.measured_at` 01:19), so the refresh loop and
  the miners ARE running. But that payload has no `graph` block, its `execution` block has no
  `attributed_deals` / `attributed_share`, and `dash.quanttt.xyz/refresh_status.json` 404s —
  three fields that landed in 738632ff, 14dd6ae9 and fcf57929. So the VPS is serving a build
  from BEFORE 2026-09-08 21:29 while `desk-sync-clean` carries everything since. HOW TO CHECK
  IT ADOPTED, from any session with no SSH: fetch `refresh_status.json` (a 200 means the VPS
  runs the post-738632ff `ops/refresh_desk_state.sh`) and look for `graph` in `desk_state.json`.
  No VPS-authored ("Codex") commit has appeared on `desk-sync-clean` since 2026-09-08 21:00.
- **SEAT OUTPUT GOES THROUGH `data/intelligence/<seat>/` (2026-09-08).** The compiler reads
  `data/intelligence/**` (both roots) and nothing else; `data/suggestion_ledger.jsonl` and
  `data/kimi_hunt.json` are gitignored audit trails read by no scheduled organ. kimi donates to
  `data/intelligence/kimi/discoveries_*.json`, DeepSeek to `data/intelligence/deepseek/`. A
  `{"kind":"hypothesis","family":<registered price-only>,"symbols":[...]}` row compiles as
  STRUCTURED_HYPOTHESIS with the family defaults; declared instruments are read before the
  prose. `miner_candidates.json["seats"]` is the seats' measured conversion — a seat that
  donated nothing in the window shows zeros there, which is the measurement, not an absence.

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

### TWO LANES: WHICH PROCESS MAY MINT A HYPOTHESIS (2026-09-06, principal's standing order)

**Single-name equities are traded on news, financial reports and earnings reaction -- never
hunted for statistical hypotheses.** Forex, metals, energy, soft commodities, indices, bonds and
Fusion's crypto CFDs remain the hypothesis-discovery universe. This does NOT narrow the universe
above: share CFDs stay tradable, their bars and ticks are still collected, and their edge is
sought in the event lane.

Routing is by ASSET CLASS from MetaTrader's own registry, never a symbol list, in
`desks/mt5/research/universe_policy.py`; `run_external_backtest.route_by_lane` enforces it and
reports what it set aside in `BACKTEST_COVERAGE.json`. A symbol absent from the registry is
UNCLASSIFIED and hunted by nothing until it is classified -- absence is not a permission.

The reason is not only that a single name's hourly path is dominated by its own scheduled
disclosures. **Trial count is a shared cost**: the deflated-Sharpe charge and the program-level
SPA/PBO tests divide one family-wise error budget across every hypothesis the desk tested, so
each equity cell raised the bar every FX and metals cell had to clear. Measured 2026-09-06:
10,575 of 23,627 docket cells (44.8%) were single-name equities and 3,839 more were equity
tickers from a non-Fusion vocabulary -- about 61% of the multiple-testing charge, spent on the
asset class least suited to the method, and paid for by the classes best suited to it. On that
same campaign `deflated_sharpe` rejected 42 of 42 judged cells at 597 trials.

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
- **NEVER REDUCE AGGRESSIVENESS (2026-09-08, principal's standing order, given three times).**
  No session lowers risk by fiat: the 20% heat floor, the 0.02-lot gold floor, the daily-loss
  and size parameters and the allocator's fractions stay as they are. Dynamic sizing the
  allocator DERIVES from evidence is fine; a cap, shrink, veto or "conditional exception" added
  because a reviewer called the book aggressive is not (Rule 1: prove robust forward E[log W]
  rises, or leave it). The external review's "drop the 0.02 exception / conditional-on-ruin"
  item is REFUSED, not deferred. Tier-1 means MORE independent positive-Elog bets inside the
  same heat, never a smaller book.
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

## PROP FIRM (E8) — principal's standing intent, 2026-09-07

Plan recorded in `docs/PROP_FIRM_E8.md`. One-line summary: **E8 One £100k, 8% drawdown /
12% target, 0.50% risk per trade, 3-4 INDEPENDENT mechanisms** (session_range_breakout +
overnight_gap_decay + carry) -> ~92% pass, ~36 days median. E8's target is always 1.5x the
drawdown chosen, so the barrier ratio is fixed and only the arena size changes.

**Readiness is counted in independent MECHANISMS, never certificates.** Adding more sleeves of
the SAME mechanism buys speed with leverage and costs pass probability (4 correlated -> 77%,
8 -> 60%). Not ready as of 2026-09-07: one mechanism has forward evidence, `matched_fills` is 0,
and n=7 per sleeve. Read the doc before discussing it -- the numbers there are measured.

# Desk memory: 100% retention, and how to reach it

- **Every lesson is retained and reachable. Nothing is forgotten between sessions.**
  `docs/desk_lessons.jsonl` is the source of truth (228 lessons). `libs/research/desk_memory.py`
  injects them; `BUDGET_CHARS` now fits the WHOLE corpus (~116k chars, ~29k tokens), so
  `reach()` is 228/228 with 0 unreached and 0 lost. It was 12,000 chars until 2026-09-06, which
  silently withheld 69 lessons from every organ and dropped 23 entirely.
- **Look up anything, any session:** `python scripts/lessons.py <query>` searches the whole
  corpus; `--id L0099`, `--tag governance`, `--all`, `--orphans` (must stay 0). Injection gives
  an organ what is most relevant unasked; this is how it reaches the rest ON PURPOSE.
- **Browse the corpus as a graph:** `python scripts/build_lesson_vault.py` regenerates
  `docs/lesson_vault/` as an Obsidian vault (cross-linked, tagged, INDEX.md). It is a DERIVED
  VIEW — edit `docs/desk_lessons.jsonl`, never the vault, or the two drift.
- **Adding a lesson:** `scripts/learn.py add`. A lesson leaves the corpus one way only — retired
  with a named falsifier that actually arrived. Silence is not retirement.
