> **SUPERSEDED 2026-08-25 (principal consolidation order).** Operative law now lives in
> [docs/LAWS.md](/docs/LAWS.md) and [docs/RESEARCH.md](/docs/RESEARCH.md); dispositions in
> [docs/MANDATE_COVERAGE.md](/docs/MANDATE_COVERAGE.md). This file is the unabridged ANNEX —
> consult it for detail, never for standing orders; on conflict the compact documents govern.
> The MT5 UNIVERSE MANDATE (LAWS §1) voids every crypto-universe clause herein.

# MEASUREMENT BEFORE OPTIMISATION

**Standing principle, principal 2026-07-27. Binds every research organ on this desk.**

> No research intelligence, model, allocator, or strategy optimisation layer may operate on
> unverified measurements. Before improving decisions, improve the truth of the inputs.
> The system should optimise reality, not noise.

## Why this one and not the other fifty-four

It is the only proposed upgrade this desk can justify from its own record, and two independent
samples agree:

| sample | measurement failures |
|---|---|
| 45-day experiment registry (369 experiments) | `E_DATA_QUALITY` 61 + `B_WRONG_MEASUREMENT` 46 = **53% of refutations** |
| single-day research autopsy | `E_DATA_QUALITY` + `C_WRONG_TIMING` + `B_WRONG_MEASUREMENT` = **64% of failures** |

Every other proposed layer — capital allocation, confidence propagation, LLM portfolios,
autonomous schedulers — optimises **decisions**. This one optimises the **inputs those decisions
are made from**, and is therefore strictly prior to all of them. An allocator fed a broken
timestamp column allocates confidently and wrongly, forever, and its own metrics will look fine.

## The five contracts

Enforced mechanically by `scripts/measurement_gate.py`.

1. **Timestamp integrity** — parseable, ordered, unique, no future stamps, regular spacing.
   Irregular spacing is the highest-yield check: a series believed daily but actually irregular
   manufactures `C_WRONG_TIMING`, 13% of refutations on its own.
2. **Data correctness** — schema stability, null rate, **frozen-value runs**, implausible values.
   A dead collector returns its last reading forever and is indistinguishable from live data by
   every statistical test except this one.
3. **Feature validity** — degenerate/constant series carry no cross-sectional information.
4. **Cost realism** — a *measured* cost model, fresh, with coverage. Unmeasured symbols are not a
   random subset; a symbol is unmeasured **because** it is illiquid, i.e. it is the expensive tail.
5. **Reproducibility** — an identifiable producer in `scripts/` or `libs/`. An artifact nothing
   can regenerate makes every result derived from it unauditable.

## Enforcement

Fail-closed, by import:

```python
from measurement_gate import require_verified
require_verified("oi_ls_history.jsonl")   # raises MeasurementError if not VERIFIED
```

**An unrun gate is not a pass — it is a refusal.** This desk has been bitten four times by
fail-open defaults (`_DEFAULT_RT_BPS = 4.5` cost real money), so the default here is refusal.

`WARN` and `FAIL` are kept separate. `data_sanity.py` had to be corrected twice for flagging
config constants as anomalies; a gate that cries wolf gets ignored, and an ignored gate is worse
than no gate because it launders unverified data as checked.

## The gate is bound by the principle too

Its first three runs produced false positives, each caught and fixed before shipping:

- **v1** applied time-series regularity checks to event logs — 6 false FAILs of 10. It flagged
  `experiment_registry.jsonl` for "357 duplicate timestamps (96.7%)" when many commits legitimately
  share a date, and `panel_verdicts.jsonl` likewise when one panel run writes 13 verdicts at one
  instant. Judging data against the wrong model of what it is **is** `B_WRONG_MEASUREMENT` — the
  gate committed the error it polices. Fixed with a structural `TIME_SERIES` / `EVENT_LOG` test.
- **v2** searched only `scripts/` for producers and falsely accused `information_value.jsonl` of
  being irreproducible when `libs/research/information_value.py` writes it. Fixed.
- **Stated limitation:** an event log with unique timestamps is structurally identical to an
  irregular time series. Nothing in the data separates them. The filename is used as a tiebreaker
  **only** in that ambiguous case, never as the primary signal.

A gate exempt from its own standard would be the loudest possible violation of this doctrine.

## Current state — 14 datasets, 8 VERIFIED, 6 FAILED

The most consequential failures:

- **`information_value.jsonl` — the desk's Information Gain accounting is dead.** 810 rows, every
  one identical: `name="factory_reject"`, `prior_survive=0.15` (hardcoded), `survived=false`,
  `info_bits=0.2345`, `lesson=""`. It is an odometer that only turns when the answer is "no", and
  turns by a constant. The architecture review asked us to *build* an Information Gain Engine; it
  already exists and it measures nothing. Any research allocation weighted on `info_bits` would
  have been optimising a constant.
- **`cny_otc_premium_history.jsonl` — no producer, 591 rows back to 2020-03-16.** The live
  collector `collect_cny_premium.py` writes a *different* file (`data/cny_premium.jsonl`); the
  historical backfill was built once by an uncommitted process (`provenance: wayback-cdx-replay`).
  This is the long-sample backbone of `M_STRUCTURAL_BARRIER`, **one of only two ALIVE mechanisms**.
  Forward data can be regenerated; 2020–2026 cannot be reproduced or audited.
  Its own rows also carry `"snapshot_local": "23:55 CST (UTC+8) assumed"` — the timestamp
  alignment against the USD/CNY reference is *assumed*, not verified. That is a textbook
  non-synchronous comparison and the gate cannot see it, because the caveat is prose in a string
  field. **Open item: verify that alignment before any CNY-premium result is promoted.**
- `kaiko_vwm_reference_rate.jsonl` — no timestamp field at all; temporal validity cannot be
  established.
- `blind_spot_ledger.jsonl`, `breadth_expansion.jsonl`, `micro_audit_log.jsonl` — frozen fields
  and high null rates.

## Consequence for the rest of the roadmap

Research capital allocation, confidence propagation and contributor-weighted routing stay
**blocked** until their inputs pass this gate. On present evidence the survival sample is also too
small to allocate on: `M_FORCED_DELEVERAGE` 2/10 vs `M_STRUCTURAL_BARRIER` 0/10 is one coin flip,
and allocating 45% against 10% on that is winner's-curse overfitting applied one level up.