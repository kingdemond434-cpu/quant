> **SUPERSEDED 2026-08-25 (principal consolidation order).** Operative law now lives in
> [docs/LAWS.md](/docs/LAWS.md) and [docs/RESEARCH.md](/docs/RESEARCH.md); dispositions in
> [docs/MANDATE_COVERAGE.md](/docs/MANDATE_COVERAGE.md). This file is the unabridged ANNEX —
> consult it for detail, never for standing orders; on conflict the compact documents govern.
> The MT5 UNIVERSE MANDATE (LAWS §1) voids every crypto-universe clause herein.

# OPERATING DOCTRINE — research prioritisation and asymmetric information

**Principal, 2026-07-27. Supersedes accumulated architecture proposals.**

> Do not create unnecessary subsystems. Use this as the operating doctrine for prioritising
> research, discovering asymmetric information, and improving the probability of validated alpha.
> **Execution reliability and deployment are the current bottleneck.**

## North star — the only success metric

**Validated Alpha Discovery Rate**: economically-plausible, statistically-validated,
forward-tested mechanisms per unit of research time.

Measured 2026-07-27 over 45 days: 369 experiments → 156 decided → 15 survived screening →
**0 through forward test → 0 deployed → capital contribution negative.**

Vanity metrics, explicitly not tracked: hypotheses generated, papers read, agents run, datasets
collected, scripts written.

The reward shape is `10,000 ideas → 9,900 killed → 100 tested → 5 survive → 1 deployed`.

## The binding rule

Every proposal must **replace a component** or **improve a measurable bottleneck**, naming the
metric that moves and the observation that kills it. This desk has 226 scripts and ~179 unwired;
the failure mode is not scarcity of ideas.

## Current bottleneck: execution reliability, not discovery

Established by evidence on 2026-07-27, not by preference:

- The carry's most-traded symbol (COOKIEUSDT) cost a **measured 130.47bps** round-trip to earn
  6.7bps — funding-first universe ranking selects for illiquidity, because funding *is* the
  compensation for illiquidity. Fixed: candidates now rank by net.
- A hedge silently **inverted from short to long twice** (+916,772 then +1,138,985) because
  oversized market orders were rejected on `MARKET_LOT_SIZE`, fell back to resting limits, and
  accumulated fills through zero. Nothing detected it. Fixed: chunking + reduceOnly + closes
  bypass the maker path.
- Cost is still an **implied residual**, not attributed. TCA fields remain outstanding.
- There is **no working process-level kill switch** — systemd respawns the executor and the
  `quant` user has no sudo.

Discovery is not the constraint: the moat sits at **0.4% construction coverage** with 447
enumerated untested constructions, and the queue is not what's limiting the desk.

## Information Advantage Score — applied, not theorised

| data | uniqueness | replication | verdict |
|---|---|---|---|
| `data/moat` order books | high — snapshots at *our* timestamps | high | **the only real moat** |
| funding / OI / LS | low | trivial | crowded, but holds the one live edge |
| on-chain, TVL, developer, attention | low | trivial | no advantage |

Prefer: hard to collect, hard to replicate, economically meaningful, persistent.
Reject: crowded, trivially computed, no mechanism.

## Mechanism ranking — from this desk's own record, not intuition

- `M_FORCED_DELEVERAGE` — **best supported**, 2/10 survival, contains the only confirmed signal
  (funding persistence, IC +0.432, t +29.7). Liquidation/leverage work belongs here.
- `M_LIQUIDITY_WITHDRAWAL` — untested at 0.4% coverage, on the only moat. Highest upside.
- `M_SKILL_PERSISTENCE` — **FAMILY KILL, with one exception that matters.** Wallet *returns* do
  not persist (refuted at n=1,400, gapped control). Wallet *risk behaviour* **did** replicate
  out-of-sample. Pursue risk-behaviour features; never performance ranking.
- `M_ATTENTION_DELAY`, `M_PRICE_PATTERN`, `M_FLOW_PRESSURE` — FAMILY KILLS. New datasets do not
  revive a dead mechanism; only a new forced-flow or asymmetry story does.

## Measurement precedes optimisation

No allocator, model or optimisation layer may run on unverified inputs. 53% of 45-day refutations
were measurement failures (`E_DATA_QUALITY` 61 + `B_WRONG_MEASUREMENT` 46); an independent
single-day autopsy said 64%. `scripts/measurement_gate.py` is fail-closed by import.

## Verification standard — the session's hardest-won lesson

Four fixes on 2026-07-27 were wrong in ways **no amount of re-reading the diff would have caught**,
and every one was found by asserting a *value*:

- `_req` vs `_get` → would have silently disabled the chunker (fail-open inside a fail-open fix)
- mainnet vs testnet module → chunker in dead code, plus a TypeError on every close
- market fallback vs the maker default → the hedge inverted again within minutes
- keyword-bleed in mechanism tagging → flat 6–11% survival across all nine families

**Verify by measuring the thing, never by inspecting the change.** A number that disagrees with
reality (COOKIE maxQty 5,000,000 vs the venue's 150,000) is the only reliable tell.

## Order of work

1. Execution reliability and deployment — the current bottleneck.
2. Measurement integrity on whatever execution touches.
3. Only then: moat construction coverage, ranked by distinguishability from known nulls.

Research capital allocation, confidence propagation, contributor routing and any autonomous
meta-layer stay **blocked**: `info_bits` is a constant 0.2345 across all 810 rows, and
per-mechanism survival samples (2/10 vs 0/10) are one coin flip apart.


## Anti-timidity and exhaustion (enforced, not aspirational)

These are checked every cycle by `scripts/doctrine.py`, which exits non-zero on any gap across
three surfaces: code callers (runtime injection), prompt files (the human paste-path), and this
markdown (what the VPS brain reads).

**ANTI-TIMIDITY** — hedging is a failure mode. State the claim and its evidence. Refusing to
conclude is abdication, not caution. Politeness toward existing work is worthless: that work came
from the same process that produced its bugs.

**EXHAUSTION** — no quota, no ceiling. Report everything substantiable; never truncate to a
comfortable number. A documented empty seam is worth as much as a find. Go one layer past where
you would normally stop — that layer is what every other reviewer skips.