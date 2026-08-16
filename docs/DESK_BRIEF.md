# DESK BRIEF -- 2026-08-16 04:34Z

Machine-generated from measured desk state. Every number traces to an artifact in
`data/`. Nothing here is an argument. Respond to the evidence, not to another model.

## Standing rules that bind any proposal
1. Every proposal must name the MEASURABLE BOTTLENECK it removes, the metric that should
   move, and the observation that would kill it. Missing any of the three = rejected.
2. A proposal mapping to a FAMILY KILL below must present a NEW forced-flow or asymmetry
   story. A new dataset for a dead mechanism is not a new hypothesis.
3. Prefer DELETE/MERGE over ADD. This desk has 226 scripts and ~179 unwired.
4. Screening is unlimited and carries ZERO promotion authority. Only pre-registered
   forward clocks promote.

## Experiment record (45d, harvested from git -- one row per commit)
- experiments: **1805**; decided: 1041
- survival rate: **5.2%** (54 survived / 910 refuted / 77 inconclusive)
- unclassified commit decisions: 176 (commit-discipline defect)

| mechanism | tested | survived | rate |
|---|---:|---:|---:|
| M_UNMAPPED | 848 | 45 | 5% |
| M_ATTENTION_DELAY | 49 | 3 | 6% |
| M_LIQUIDITY_WITHDRAWAL | 46 | 2 | 4% |
| M_STRUCTURAL_BARRIER | 44 | 0 | 0% |
| M_FORCED_DELEVERAGE | 42 | 3 | 7% |
| M_SKILL_PERSISTENCE | 14 | 0 | 0% |
| M_FLOW_PRESSURE | 13 | 0 | 0% |
| M_FUNDAMENTAL_PROXY | 11 | 0 | 0% |
| M_PRICE_PATTERN | 5 | 1 | 20% |

### Why experiments died (45d)

- `E_DATA_QUALITY` 488 (37%)
- `B_WRONG_MEASUREMENT` 242 (18%)
- `H_OVERFIT` 201 (15%)
- `G_TOO_EXPENSIVE` 181 (14%)
- `C_WRONG_TIMING` 109 (8%)
- `F_REGIME_DEPENDENT` 80 (6%)
- `D_ALREADY_ARBITRAGED` 16 (1%)
- `A_NO_MECHANISM` 8 (1%)

**730/1325 = 55% of refutations are MEASUREMENT failures (data quality + wrong construction), not absent alpha.**

## FAMILY KILLS -- mechanisms closed by evidence

`M_PRICE_PATTERN`, `M_ATTENTION_DELAY`, `M_FLOW_PRESSURE`, `M_SKILL_PERSISTENCE`, `M_FUNDAMENTAL_PROXY`

Every future variant inherits this evidence.

## Transferable lessons (family -> dominant failure mode)

- **price-only/TA** -> `C_WRONG_TIMING` (n=56)
- **funding/positioning** -> `G_TOO_EXPENSIVE` (n=42)
- **attention/social** -> `C_WRONG_TIMING` (n=30)
- **regional premium** -> `A_NO_MECHANISM` (n=28)
- **on-chain/flow** -> `C_WRONG_TIMING` (n=26)
- **trader/behavioural** -> `C_WRONG_TIMING` (n=19)
- **other** -> `UNCLASSIFIED` (n=12)
- **developer** -> `C_WRONG_TIMING` (n=7)

## Proprietary moat (4.4GB order books, 30 symbols, top-20 snapshots)

M_LIQUIDITY_WITHDRAWAL, construction = negative z of near-touch depth vs 24h roll:
- raw lead rho pooled: +0.1059
- **after orthogonalising forward RV against current RV: residual rho +0.0154 (t +0.28), sign 1/5 -> the lead was vol clustering.**
- ONE construction tested only. The mechanism is NOT refuted. Untested: replenishment rate, one-sided withdrawal, book shape, migration, recovery half-life, d(book)/dt.

## Live carry

- entry gate `_DEFAULT_RT_BPS` 4.5 -> 39.5 (p90 of measured round-trip) on 2026-07-27; bar is now ~8.8x the funding floor. Effect unmeasured until 24-48h of rotations accumulate.
- pre-fix: funding harvested $113 vs implied costs $876 = **7.75x**.
- hold-time scan: 8h -39.2%/yr, 24h +5.8%/yr (LIVE), 48h +14.0%/yr, 72h +17.0%/yr. `_MIN_HOLD_H` is still 24. ~+11pp/yr unclaimed.

## Highest-ERV open hypotheses

- 1.000 — Market maker inventory stress
- 1.000 — Liquidity fragility score
- 0.037 — Developer retention momentum
- 0.037 — Bridge flow predicts rotation
- 0.006 — Attention efficiency ratio

## Known blockers

- OpenRouter 402: 4 written LLM roles have NEVER executed (code auditor, blind researcher, hypothesis generator, architecture board).
- `health.json` reports all_ok=True against 14 stub vs 13 real logs (fail-open).
- First forward-clock verdict: 2026-08-07 (OI/LS). Confirmed alphas to date: 0.
