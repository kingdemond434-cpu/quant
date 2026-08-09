# CYCLE REPORT — 2026-07-29 closure cycle

Every claim below carries the command that proves it (L2.4). 18 commits, 69 files,
+8,753/−2,914 lines. Branch `claude/wonderful-darwin-7uiobi`, pushed.

## Ratchet board (the answer to "how far from 100%")

`python scripts/check_ratchets.py --report-only` → **0 defects, 4 metrics below 100%**

| metric | value | floor | gap | note |
|---|---:|---:|---:|---|
| findings_coverage | 100.0% | 100.0% | 0.0% | at ceiling |
| test_strength (min kill rate) | 90.0% | 90.0% | 10.0% | was UNMEASURED before today |
| scripts mypy-clean | 40.7% | 40.7% | 59.3% | was UNMEASURED before today |
| miner seats productive | 0.0% | 0.0% | 100.0% | **one unarmed credential, 11 seats** |
| pager delivered <24h | 0.0% | 0.0% | 100.0% | no channel armed in this sandbox |

## Rows closed, with proof

| row | what changed | proving command / value read |
|---|---|---|
| **#87** | per-candidate gates live at **all 19** call sites; campaign constants demoted to diagnostics | `grep -rln campaign_pbo_rc scripts/ libs/` → only the deprecated fn; 143 tests green |
| **#53** | mutation testing installed **and measured**: 55% → **90.0%** | `python scripts/run_mutation.py --target libs/validation/stepwise.py …` |
| **#58** | manifest + checker + idempotent installer; **DR drilled end-to-end** | install → `check_scheduler_manifest` → *"live crontab: matches manifest"*; re-run stays 26 lines / 2 markers |
| **#56** | structured logger **activated** on the money path (it already existed) | `pytest tests/execution tests/risk` 87 passed before **and** after |
| **#38** | delivery ledger + canary + `--status`; failed attempts do **not** clear silence | `pytest tests/ops/test_alert_channels.py` 9 passed |
| **#39** | traded names now outrank majors; hourly in-flight refresh | `pytest tests/scripts/test_recorder_universe.py` 16 passed (8 × both recorders) |
| **#52** | backlog is a ratchet: **1118 errors / 263 files / 107 clean** | `python scripts/check_mypy_ratchet.py` |
| **#29** | cause isolated: **11/11 seats `creds-missing`**, blast radius 11 | `python scripts/check_miner_runway.py --report-only` |
| **#77** | 41 years of COT read; **GHR replicated**, pooled lagged NW-t **−0.64** | `python scripts/run_cot_screen.py --years 1986-2026` |

## Two results that change what the desk believes

1. **"420 tested, 0 survivors" was an instrument artifact, not a fact about crypto.** Two of nine
   gates never took the candidate's own returns (campaign PBO 0.6159, White RC p 0.4220 → all 420
   rejected at any quality). The flip is live; the honest status is **UNKNOWN until the campaign
   re-runs**, and L1.25 now forbids reading zero survivors as absence of alpha.
2. **The borrowed −58% post-publication haircut cannot be validated on owned data.** Every asset
   with a real pre-2000 sample shows a **negative** pre-publication Sharpe — there is nothing to
   decay. The prior stays explicitly borrowed rather than being quietly replaced with a number.

## Defects this cycle found in its own instruments

Recorded because each would have produced a false negative — an instrument reporting a fact about
the world when it was reporting a fact about itself:

- **mypy** aborted every batch (`Source file found twice: scripts.doctrine vs doctrine`) and the
  first run scored **263 files UNCHECKABLE**. One missing flag, not an unmeasurable backlog.
- **COT parsing**: `"Commercial Positions-Long"` is a substring of `"NONCommercial…"` and the
  noncommercial column comes first → all 12 commercial series computed to exactly **0.00** and
  printed as "no edge". Plus contract-name drift by era (`LIGHT 'SWEET'`, `POUND STERLING`) and
  three S&P contracts stacked into one series.
- **§36 artifact governance** fired on this cycle's own four new documents. Classified with
  reasoning, not silenced.
- **mutation survivors** split into equivalent vs real: CSCV PBO is rank-based, so
  `(n−1)→(n+1)` and `s**2→s**3` are unobservable **by construction** (verified directly). The real
  gaps were validator **boundaries** — the suite asserted illegal inputs raise and never asserted
  the smallest legal input is accepted.

## Laws installed (each with a fence — a law without one is prose)

**L1.0 THE UNIVERSAL RATCHET** (placed first, governs execution of all others): today's value is
the floor, 100% is the target, **the gap is the work queue**, self-initiated, "maxed" is never a
state, and **100% subsystem breadth coverage in every cycle** (rotation for depth only). Fenced by
`check_ratchets.py`, which is structurally incapable of lowering a floor — the load-bearing test
asks it to record a regression and asserts the floor holds.

Also: **L1.11a** asymmetric information archaeology (time/geography/language/era as search
dimensions; CN pre-ban and Arabic/Gulf-MENA named explicitly), **L1.16a** opportunity resurrection
(narrow door, named enabling change), **L1.24** information advantage not activity, **L1.25** alpha
discovery persistence, **L1.26** investment objective priority, **L1.27** opportunity cost of
inaction, **L2.0** ratchet fence, **L2.9** capability audit loop, **L2.10** reality gap detection.
All mirrored into `ops/principal_doctrine.txt` so every organ receives them on every call.

## Organs built and wired (idle capability is a defect, L2.9)

`run_execution_intel.py` (cross-feed cost-DRIFT, recommend-only, never self-applies),
`run_reality_gap.py` (backtest→shadow→live→venue-truth; the 7.75× and 36.4% classes become standing
detectors), `libs/research/dist_shift.py` (has the measuring stick moved — downward-only haircuts),
`libs/research/pre_filter.py` (HYPOTHESIS_MAX #1; rejects charge trials, never skip the ledger),
`check_ratchets.py`, `check_miner_runway.py`, `check_mypy_ratchet.py`, `run_mutation.py`,
`check_scheduler_manifest.py`, `run_alert_canary.py`. All 6 new checks added to the daily cycle
(77 → 83 steps) **and** the crontab manifest.

## Autonomy installed

**Weekly gap-max sweep scheduled** (Tue 09:00 UTC, fresh session, notifications on) with a binding
**effort floor**: at least as exhaustive as this session, no self-imposed quota, every ratchet
re-measured and pushed in the same run. A sweep reporting "nothing to do" without a per-metric
value/floor/distance-to-100% table **has not run**. Contract: `docs/WEEKLY_MAX_CYCLE.md`.

## What is blocked, on whom, and what unblocks the most

Three human steps dominate everything else on the board:

1. **Miner credentials** (`bash ops/setup_brain_token.sh`) → unblocks **11 seats**. Prompts,
   runners and scheduling are all verified present; the miners are unarmed, not misconfigured.
2. **OpenRouter top-up (~$25–50)** → unblocks **8 defects**, including the 13-seat panel and the
   second-model-family fuzz half of the v8 8.2 bar (which mutation testing does **not** substitute
   for, and this cycle does not claim it does).
3. **`crontab -l` + `systemctl list-timers` paste** → closes #58's other half. The manifest names
   17 cron lines where the box shows ~20–22; the gap is stated in its own header rather than
   invented.

Also principal-owned: **register #80** (the anti-bot-gate ruling) is now the binding blocker on the
COT screen's largest improvement — metals/grains/softs need a licence-clean price leg, and Stooq
sits behind a proof-of-work gate that was **not** defeated.

## The deepest problem, unchanged and not papered over

Across 420 candidates, none was simultaneously profitable, walk-forward-stable, capacity-viable and
tail-acceptable. #87 proves two gates were lying, which **re-opens** that question rather than
answering it. The candidate-quality problem upstream of every gate is still the binding constraint
on validated alpha, and the honest next move is the campaign re-run through corrected gates — not a
claim that the space is picked clean.
