# Gap #34 forensic — the "$1.8-2.6k unexplained" resolved (2026-07-22)

**Verdict: no money is missing. The figure conflated THREE different numbers, two of which are
now fully attributed, and the residual third is a HEDGE FAILURE concentrated in 3 symbols.**

## 1. The USDT movement is 100% attributed -- nothing is missing
`data/deadman_reconciliation_20260719.json`:
- `observed.spot_usdt_baseline_delta` = **-1837.68**
- sum of per-symbol `spot_net_usdt` over 25 reconciled symbols = **-1837.68**
- `spot_only_residual_usdt` = **-0.0019** (a fifth of a cent)

Every dollar of the spot-wallet decrease traces to actual reconciled fills. The "unexplained /
unattributed" framing in gap #34 is **false** on this component.

## 2. The equity gap is a MEASUREMENT artifact -- mechanism independently confirmed
`observed.equity_gap_latch_vs_reconstructed` = **1623.65** (latch read ~785 vs reconstruction
~2409). The 07-19 dossier hypothesised the cause ("legs_v counts spot ONLY for currently-shorted
symbols"); **incident #5 on 07-22 independently confirmed exactly that mechanism** -- closing the
futures short first collapses `legs_v` to $0 while the spot leg is still held, plus `fut_eq`
depressed by margin locked in-flight. This component is explained and already fixed at the rail
level (sustained-high-water, ruin factor untouched).

## 3. What is REAL -- and it is a hedge failure, not slippage
`totals.combined_net_usdt` = **-1804.82** over the scan window. It is NOT spread across the book:

| symbol | spot | futures | net | fills spot/fut |
|---|---|---|---|---|
| GTCUSDT | -1057.88 | **+0.28** | -1057.60 | 5 / **22** |
| SHELLUSDT | -429.62 | +4.82 | -424.80 | 4 / 12 |
| ONEUSDT | -363.46 | -3.80 | -367.26 | 7 / 8 |

Those three = **-1849.66**, i.e. the entire combined net (partly offset by IOTA +28.82 and
JASMY +86.96). 5 of 25 symbols failed to offset by >$20; 20 of 25 behaved.

**Signature: futures P&L ~= 0 against large one-directional spot losses.** For a delta-neutral
pair that is a hedge that was not on. Heavy futures churn on the same names (GTC 22 futures fills
vs 5 spot; JASMY 62 futures fills) points at repeated re-hedge/trim cycling rather than a held
hedge. No symbol had <2 spot fills, so this is not unsold inventory being mis-scored.

## 4. CRO self-implication (stated plainly)
GTCUSDT, SHELLUSDT and ONEUSDT are **exactly** the names the CRO's 07-19 full-deployment topup
deployed into hours earlier (`topup GTCUSDT +7556.8`, `topup SHELLUSDT +20357.0`,
`topup ONEUSDT +308521.0`), and that deploy tick produced the trim-excess<->topup churn burst --
which is the "rapid rebalance churn" gap #34 itself names as the trigger condition for the
leg/cash race. Causation is NOT proven by this data (the window is 14h later and the reconcile
scan spans 07-17->07-19), but the symbol overlap is too specific to omit. Treat the topup path as
a prime suspect for producing unhedged windows.

## 5. Disposition
- Gap #34's "unexplained money" framing: **CLOSED** (attributed, residual -$0.0019).
- Measurement component: **CLOSED** (legs_v, confirmed by incident #5).
- **NEW gap #41 opened**: hedge-failure mode -- spot leg loses while the futures leg contributes
  ~0 during churn on the same symbol. This is the real, unresolved, money-losing defect and it is
  more serious than the accounting question it was hiding behind.
