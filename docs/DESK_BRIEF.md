# DESK BRIEF -- 2026-07-27 20:38Z

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
- experiments: **369**; decided: 156
- survival rate: **9.6%** (15 survived / 131 refuted / 10 inconclusive)
- unclassified commit decisions: 25 (commit-discipline defect)

| mechanism | tested | survived | rate |
|---|---:|---:|---:|
| M_UNMAPPED | 102 | 10 | 10% |
| M_ATTENTION_DELAY | 22 | 2 | 9% |
| M_FORCED_DELEVERAGE | 10 | 2 | 20% |
| M_STRUCTURAL_BARRIER | 10 | 0 | 0% |
| M_LIQUIDITY_WITHDRAWAL | 9 | 0 | 0% |
| M_FUNDAMENTAL_PROXY | 7 | 0 | 0% |
| M_SKILL_PERSISTENCE | 6 | 0 | 0% |
| M_PRICE_PATTERN | 4 | 1 | 25% |
| M_FLOW_PRESSURE | 2 | 0 | 0% |

### Why experiments died (45d)

- `E_DATA_QUALITY` 61 (30%)
- `B_WRONG_MEASUREMENT` 46 (23%)
- `G_TOO_EXPENSIVE` 28 (14%)
- `C_WRONG_TIMING` 27 (13%)
- `H_OVERFIT` 24 (12%)
- `F_REGIME_DEPENDENT` 10 (5%)
- `D_ALREADY_ARBITRAGED` 4 (2%)
- `A_NO_MECHANISM` 1 (0%)

**107/201 = 53% of refutations are MEASUREMENT failures (data quality + wrong construction), not absent alpha.**

## FAMILY KILLS -- mechanisms closed by evidence

`M_PRICE_PATTERN`, `M_ATTENTION_DELAY`, `M_SKILL_PERSISTENCE`, `M_FLOW_PRESSURE`

Every future variant inherits this evidence.

## Transferable lessons (family -> dominant failure mode)

- **price-only/TA** -> `C_WRONG_TIMING` (n=41)
- **regional premium** -> `A_NO_MECHANISM` (n=20)
- **funding/positioning** -> `E_DATA_QUALITY` (n=16)
- **trader/behavioural** -> `C_WRONG_TIMING` (n=15)
- **on-chain/flow** -> `C_WRONG_TIMING` (n=13)
- **attention/social** -> `A_NO_MECHANISM` (n=9)
- **other** -> `UNCLASSIFIED` (n=4)

## Proprietary moat (4.4GB order books, 30 symbols, top-20 snapshots)

M_LIQUIDITY_WITHDRAWAL, construction = negative z of near-touch depth vs 24h roll:
- raw lead rho pooled: +0.3032
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
- First forward-clock verdict: 2026-09-01 (OI/LS). Confirmed alphas to date: 0.
