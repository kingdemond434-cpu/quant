# PREREGISTRATION — Cluster-9 bounded scale-in ("grid recovery") on EURUSD

**Governance class: §36 CADENCED** until the run completes, then **TERMINAL** (the record of one
measured decision). Classified on arrival per `ARTIFACT_GOVERNANCE.md`.

**Status: WRITTEN BEFORE THE RUN.** No result from this design has been observed at the time of
commit. Kill criteria below bind (L1: kill criteria bind BEFORE a run). If any criterion is
edited after results are seen, this preregistration is void and the candidate is dead.

**Cluster:** #9 `mean_reversion` — *"Impatient liquidity takers... Overshoot after a shock, gap
decay, failed breakouts, and the half-life of the return to value."* Currently occupied by one
sleeve (`xau_m15_anti_breakout`).

---

## 1. Why this hypothesis, and why it is not the EA

A retail "grid recovery" EA (ATS Origin, published 2026-09-21) claims a five-year positive record
on EURUSD with: 20 pip take-profit, first scale-in at 120 pips adverse, subsequent adds every
40 pips, fixed lot, basket exits at +20 pips on the volume-weighted average entry.

The desk does not adopt EAs. But the mechanism encodes a testable cluster-9 claim the desk has
never measured: **after an adverse excursion of ~120 pips, does EURUSD retrace far enough, often
enough, to make a bounded scale-in positive-expectancy net of costs?**

The arithmetic that makes this non-trivial: with k positions entered at 0, 120, 160, ... pips
adverse, the VWAP sits near the middle of the ladder, so closing the basket at VWAP+20 requires a
retrace of roughly **48% of the total adverse excursion** (worked example: 14 positions at 620
pips adverse => VWAP ~-344, exit target ~-324, required bounce ~296 pips). That is a substantial
mean reversion, not a small one. Whether it arrives before the excursion extends is an empirical
question about EURUSD's conditional retrace distribution, and it is the actual hypothesis.

Note the payoff asymmetry is NOT a cost problem. Because every position in the basket gains the
full 20 pips on exit, a recovered basket earns `k x (20 - cost)` and larger baskets earn MORE.
All risk is concentrated in the non-recovery tail. This preregistration therefore measures the
tail, not the average.

---

## 2. Hypotheses

- **H1 (edge).** A bounded fixed-lot scale-in on EURUSD H1 has positive realized expectancy net
  of measured spread and commission.
- **H2 (survival).** A $500 account at 0.01 lots — the configuration the source explicitly calls
  viable — survives the full sample without margin liquidation.
- **H0 (the null this must beat).** The same entries with a hard 120-pip stop and no scale-in.

**The decisive control is RANDOM ENTRY.** Entries are taken unconditionally at fixed intervals
with randomised direction. If the scale-in has edge, it must show on entries carrying no signal;
if it only "works" behind a signal, the edge belongs to the signal and this cluster-9 claim is
false. This uses the same logic as `libs/validation/random_baseline.py` and `positive_control.py`.

---

## 3. Data, and its declared limits

`desks/mt5/universe/EURUSD_H1.parquet` — 53,660 H1 bars, **2018-01-02 to 2026-08-14**.
Columns include a per-bar `spread` in points, so cost is charged from **measured historical
spread**, not an assumed median.

Three limits, declared now so they cannot be discovered later as excuses:

1. **The tail sample is n=1, not n=3.** The window contains the 2021–22 decline
   (1.2350 -> 0.9536, 2,814 pips). It does **not** contain 2008 (3,708 pips) or 2014–15
   (3,532 pips). The loss distribution of this mechanism is defined by multi-year trends that
   arrive roughly three times in twenty years. Passing on this window is therefore **weak
   evidence of tail survival, and must never be reported as strong**.
2. **H1 bars cannot resolve intra-bar ordering.** Within one bar, a 60-pip range may touch both
   the next grid level and the basket target. Which came first is unknowable at this resolution.
   The desk holds sub-H1 data for only four symbols (XAUUSD M1/M5/M15; AUDCAD/AUDNZD/NZDCAD M15)
   and **EURUSD is not among them**. Mitigation: run BOTH conventions and bracket the answer
   (criterion K4).
3. **Swap/carry is NOT modelled** — the bar data does not carry it. Baskets in this mechanism are
   held for weeks (the source's own example: first add seven days after entry). Unmodelled swap on
   a multi-week, multi-position basket makes **every result in this study optimistic**. A pass is
   weaker than it appears; a fail is decisive.

---

## 4. Specification (frozen)

```
instrument      EURUSD, H1
entry           unconditional, every 24h, direction ~ Bernoulli(0.5), seed fixed and recorded
take profit     +20 pips on the basket VWAP
first scale-in  120 pips adverse from initial entry
grid step       40 pips thereafter
sizing          fixed 0.01 lot per position (no martingale)
grid stop       variant A: none (pure mechanism)
                variant B: $1,500 scaled to lot (the source's published value)
costs           per-bar `spread` column, charged on entry and exit of every position
                + $3.00 per lot per side commission (BlackBull Prime, as stated by the source)
margin model    leverage 1:500, stop-out at margin level 50%, equity checked EVERY BAR
accounts        $500 (the source's "theoretically viable") and $5,000 (the source's live size)
```

**Trial count for DSR: ONE.** This preregistration declares a single primary configuration. The
two fill conventions, two cost levels, two account sizes and two stop variants are **robustness
checks on one hypothesis**, not independent trials. Any parameter sweep requires a NEW
preregistration with its own trial declaration. This is explicit because the source's own result
is a selected configuration with no trial count published, which is the defect this desk has
shipped nine times.

---

## 5. KILL CRITERIA — binding, all must pass

| # | Criterion | Fail => |
|---|---|---|
| **K1** | Random-entry net expectancy > 0 with t > 2.0 | KILL — the mechanism has no standalone edge |
| **K2** | **Zero** margin liquidations, $500 account @ 0.01 lot, full sample | KILL — one liquidation ends it; there is no partial credit on ruin |
| **K3** | Terminal realized equity beats the hard-120-stop null (H0) | KILL — the scale-in adds nothing over taking the loss |
| **K4** | Sign of expectancy identical under BOTH intra-bar conventions | If it flips: verdict **UNRESOLVED-ON-H1**, never PASS. Escalates to "acquire EURUSD M5" as a data-axis task |
| **K5** | Sign survives cost stress at 2x measured spread | KILL — it was a cost artefact |

**A PASS on all five does not promote anything.** It qualifies the candidate to enter the
standard gauntlet (CPCV, PBO, DSR against the true ledger count, SPA, lockbox) per
`UNIVERSAL_PROMOTION_PROTOCOL.md`. There is one door, and this preregistration is not it.

**Predicted outcome, recorded in advance so the desk can score its own calibration:** K2 fails.
The mechanism is expected to be a payoff transformation — frequent small wins, rare large loss —
whose realized expectancy is near zero before costs and negative after, with liquidation of the
$500 account during the 2021–22 decline. Recording this prediction is not a thumb on the scale;
it is the desk's own forecast being made falsifiable alongside the hypothesis.

---

## 6. What a PASS would mean, and what it would not

A pass would say only: *on one instrument, one window containing one tail event, at H1 resolution,
without swap, a bounded scale-in was net positive and did not liquidate.* It would NOT establish
that the mechanism survives 2008 or 2014–15, that it works on any other instrument, or that it is
deployable at any size. Those are separate measurements and each requires its own preregistration.
