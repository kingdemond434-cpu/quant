> **SUPERSEDED 2026-08-25 (principal consolidation order).** Operative law now lives in
> [docs/LAWS.md](/docs/LAWS.md) and [docs/RESEARCH.md](/docs/RESEARCH.md); dispositions in
> [docs/MANDATE_COVERAGE.md](/docs/MANDATE_COVERAGE.md). This file is the unabridged ANNEX —
> consult it for detail, never for standing orders; on conflict the compact documents govern.
> The MT5 UNIVERSE MANDATE (LAWS §1) voids every crypto-universe clause herein.

# TWO-STAGE DISCOVERY LAW — unlimited generation, permanently fixed bar (principal 2026-07-23)

**The principal's requirement:** hypothesis generation must NEVER move the validation bar — the
two supreme objectives must not conflict, ever. **This law delivers that exactly, with zero
statistical downside**, using the textbook separation the field settled on long ago:
screening on reused data is corrected for multiplicity; **confirmation on NEW data is immune to
generation volume by construction.**

## The law

**STAGE A — SCREEN (unlimited, zero promotion authority).**
The backtest gauntlet (CPCV/DSR/PBO/fixed-wall) is a RANKING DEVICE only. Its job is to order
candidates by quality and decide who gets a confirmation slot — nothing screened here is ever
"validated," so its multiplicity arithmetic **cannot create a phantom edge no matter what it is**.
Generation may run at any volume forever: objective #2 is unbounded here. (Corollary: the
fixed-wall deflation change becomes LOW-STAKES — it only affects screening ORDER. The panel
review stands, but the promotion pathway no longer depends on it.)

**STAGE B — CONFIRM (fixed slots, fixed bar, sole promotion authority).**
Promotion to capital happens ONLY from forward evidence accrued AFTER pre-registration.
Forward data is NEW data: a hypothesis registered before its window cannot have overfit that
window, **regardless of how many siblings were generated** — generation volume is statistically
invisible to Stage B. The only multiplicity that exists here is the number of CONCURRENT
confirmation slots, and that is already corrected by `forward_stats.holm_bar` over the cohort.

**THE FIXED WALL THAT ACTUALLY MATTERS: the SLOT BUDGET.**
`MAX_FORWARD_SLOTS = 12` concurrent confirmation slots (registry: `data/shadow_sleeves.json` +
the standing clocks). The Holm cohort correction is bounded by slot count — so with slots
capped, **the confirmation bar is a constant for life**: it never rises with generation, never
loosens with pressure. Expected false promotions ≈ cohort-alpha per slot-batch, fixed by
design, independent of whether the desk generated 10 hypotheses or 10 million.

**SLOT ADMISSION (the only place selection pressure survives, and it's harmless).**
Slots are filled by EV-rank (economics, orthogonality, capacity, measured cost) from Stage-A
survivors. Picking the best-looking backtest into a slot does NOT leak luck into Stage B: under
the null, forward Sharpe is ~0 regardless of how lucky the backtest was. Anti-gaming rules that
already exist and stay: graveyard/do_not_repeat (no retries without a materially new mechanism),
content-hash dedup, pre-registration mandatory, kill-basis rules.

## Why there is genuinely no downside
- **No phantom risk added:** Stage B's false-promotion rate is set by per-slot alpha × slot
  count — both constants. Generation volume never enters the formula.
- **No progress throttle:** Stage A is unbounded; the 8h evidence density + e-value peeks make
  Stage B as fast as honesty allows; slots recycle as clocks resolve (~40-90d, sooner on
  decisive e-values post-adoption).
- **The real constraint surfaces honestly:** if the desk ever has more Stage-A survivors than
  slots, that is a GOOD problem, solved by slot recycling and EV-ranking — not by bar movement.

## Mechanical enforcement (brain-free)
- `run_alerts` pages `slot_budget_exceeded` if the registry + standing clocks exceed 12.
- The clock-saturation check (max_audit) polices the opposite failure: slots sitting EMPTY.
  Together they pin the system to "always full, never over" — maximum honest throughput.