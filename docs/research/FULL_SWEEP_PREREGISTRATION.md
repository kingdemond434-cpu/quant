# FULL-UNIVERSE SWEEP — PRE-REGISTRATION (2026-08-07)

**Status: PRE-REGISTERED, NOT RUN.** The universe, the bar and the kill criteria are fixed below
**before any cell is evaluated**. That ordering is the entire statistical basis for this study.

## The declared universe

Every candidate `enumerate_space()` emits over the desk's feature set, with the full transform
axis. Nothing is sampled and nothing is held back.

    features × features × operator × transform_L × transform_R × horizon × regime

At 13 features and 8 transforms that is **898,560 candidates**, and the count is written into the
artifact **before the first result**, from `space_size()` rather than from what happened to
evaluate.

**WHY THE WHOLE UNIVERSE RATHER THAN A SAMPLE.** There is no sampling decision to justify, and any
sample would need a rule for choosing it — a degree of freedom this design does not have to spend.
**AND IT ANSWERS A QUESTION A SAMPLE CANNOT:** *what happens if we search the entire expression
space?* A partial sweep can only answer *what happened in the part we chose*.

**THE COST, CORRECTED.** Per-candidate cost is linear in the SAMPLE, not in the universe: ~0.47 ms
on a 9,000-row pooled tape, so the full universe is ~7 minutes there and hours on a 2M-row archive.
An earlier draft of this document quoted a small-sample figure as the sweep's cost. It is not.
`scripts/run_full_sweep.py` therefore measures the per-cell cost on a calibration batch, projects
the run, and **refuses to start** past `--max-minutes` — this box collects tape that cannot be
re-acquired at any price, and an unprojected multi-hour job competing with the recorders is how the
desk would lose the one asset it cannot rebuild.

**THE SAMPLE WINDOW IS THEREFORE A DECLARED CHOICE, NOT AN IMPLEMENTATION DETAIL.** A run that used
`--tail-bars` measured a window, the report says so, and no such result may be described as a
statement about the archive.

## How the universe is executed — fixed before the run

| Decision | Choice | Why the alternative would flatter the result |
|---|---|---|
| Cross-section | symbols intersected onto **one timestamp grid** | a cross-sectional transform on ragged grids ranks against absent symbols |
| Trial accounting | candidates evaluated **once, pooled across symbols** | per-symbol evaluation is 898,560 × S trials against a hurdle declared for 898,560 |
| Symbol boundaries | 2 NaN rows between pooled blocks | without them the first bar of ETH is predicted by the last bar of BTC |
| Horizon returns | h-bar forward return divided by h (**per-bar**) | a raw weekly return against a per-bar cost makes 1w look 168× better for arithmetic reasons alone, and the sweep would find every survivor there |
| Overlap | t computed on **n/h** effective observations | overlapping windows reuse each bar h times and inflate t by ~√h |
| Regime thresholds | trailing statistic vs **expanding** median | a full-sample percentile encodes the answer in the threshold |
| Undetermined regime | belongs to **neither** high nor low | forcing early bars into an arm puts the least-contextualised tape wherever the operator happens to point |

The regimes are: `high_vol`/`low_vol` split on 60-bar realised vol against its expanding median;
`trending`/`ranging` split on |60-bar return| ÷ (60-bar vol × √60) against its expanding median;
`all` unconditional. Every input is lagged one bar before use.

## The bar

`√(2 ln 898560)` = **5.236**, computed from the DECLARED universe.

**NOT from the number of cells that turn out to be measurable.** Cells refused for thin samples or
missing panels still consumed a hypothesis; deflating on the survivors' denominator would shrink
the bar in proportion to how many cells failed, which is the most flattering possible accounting.

**THIS IS A SEPARATE FAMILY FROM THE 20,052 PRE-REGISTERED MECHANISM TRIALS.** Those studies argued
for a mechanism in advance and carry named kill criteria; this argues for nothing and enumerates.
Merging the budgets would raise the bar on reasoned hypotheses to pay for a blind sweep. The two
are reported separately and **neither may be used to select within the other** — which is exactly
what keeps them two families and not one 918,612-trial pool.

## Kill criteria — BINDING, fixed before the run

| # | Criterion | Kills |
|---|---|---|
| F1 | Deflated significance | \|t\| < **5.236** on the full-sample IC, t computed on n/h effective observations |
| F2 | Net of cost | `net_bps ≤ 0` at **10bp** round-trip charged on realised turnover |
| F3 | **Walk-forward sign** | on a **70/30 time split**, IS and OOS net must **both be positive**; a flip is fitting, and two negative arms "share a sign" while describing a cell that loses money in both halves |
| F4 | **OOS magnitude** | `oos_net < 0.25 × is_net` → decay, not edge |
| F5 | Sample floor | **<200** usable observations in either split arm → **UNMEASURED**, never "no edge" |
| F6 | **Leakage** | with **one extra bar of lag**, net must keep its sign and **≥25%** of its magnitude; a collapse means the edge was living on the entry bar |
| F7 | **Independence** | survivors clustered at \|corr\| ≥ **0.7** on realised returns; the reported count is MECHANISMS, not cells. Clustering is O(k²) and is capped at the **top 500 by \|t\|** — fewer items can only produce fewer clusters, so a capped count is a **LOWER bound** and the report says when the cap bound |
| F8 | **Liquidity disclosure** | per-symbol net reported beside per-symbol median spread. **A run without this section is INVALID** — WS-006 predicts survivors concentrate at the tight end, and an absent spread column makes it UNMEASURED, never "no concentration" |

**F3 and F4 are the ones a 898,560-cell sweep needs most.** At this width, the best cells are order
statistics; a genuine effect persists across a time split and a fitted one does not. F7 is the
count that matters: twenty variants of one mechanism are one discovery.

**F6's threshold is 25% and not 100% on purpose.** A real edge decays under extra latency — that is
what makes it tradeable rather than instantaneous — so demanding full retention would kill genuine
signals. A *collapse* to near-zero or a sign flip is the leak tell, and 105 of 360 leak probes in
WS-006 did exactly that.

## What is predicted, recorded so the result can falsify it

**Most likely outcome: zero survivors.** WS-006 already measured the strongest thing on this desk —
order-flow momentum, t = +3.95, Holm-cleared — netting **−0.656 bp/bar**. A blind sweep over the
same feature set has no reason to do better, and the negative control confirms the harness returns
**0 net-positive cells on pure noise**.

**A NULL HERE IS A RESULT, AND A VALUABLE ONE.** It would bound the entire expression language:
that no combination of these 13 features under these 8 transforms clears costs at these horizons.
That is a far stronger statement than "the 20,052 we chose didn't work", and it is precisely what
licenses spending the next cycle on NEW DATA rather than new formulas.

**If survivors appear, the burden shifts to F7 and F8**: how many independent mechanisms, and does
their spread distribution differ from WS-006's? A survivor set that is one mechanism concentrated
at the tight end of the book is the WS-006 finding again, not a new one.

## Authority

**NONE.** Stage A. Promotes nothing, sizes nothing, trades nothing. A survivor here earns
out-of-sample, CPCV/DSR and a portfolio-contribution test — the last two of L1.52(a)'s four counts
— before the word means anything.
