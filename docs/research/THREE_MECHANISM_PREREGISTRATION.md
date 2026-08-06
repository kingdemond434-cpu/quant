# Pre-registration — the three mechanisms this desk will actually run

**Written 2026-08-04.** Three, named in advance, because the alternative is the fastest way to
manufacture a false positive: test twenty, report the best, and the trial count is twenty whether
or not the other nineteen appear in the write-up.

---

## First, the thing that makes this necessary — where the data actually is

The desk **does** hold the data. `docs/research/data_provenance.json` declares `moat_depth.jsonl`,
`moat_trades.jsonl` and `funding_history.jsonl`, and the moat miner has been converting tape into
coverage for weeks. None of it is on the machine that runs the research.

The cause is one line, and it is deliberate:

```
# .gitignore
data/*        # "the journal is data/, not git"
```

Every analysis container is a **fresh clone**. Git carries code; git was explicitly chosen not to
carry data. So the desk has a **transport gap, not a data gap**:

> **research runs where there is no data; data accumulates where there is no research, and nothing
> moves one to the other.**

That is why every study this session reported BLOCKED, and it is not fixed by writing more
analysis code. It is fixed by one of: running the study **on** the VPS, or shipping a periodic
snapshot from the VPS to somewhere a clone can fetch. Until then the harnesses below are correct,
tested, and idle — which is a better state than absent, and a worse state than running.

---

## The three

Chosen for **mechanism strength × capacity**, not for how interesting the pattern looks.

### 1. Funding carry — short perp / long spot

**Mechanism.** Persistent positive funding is crowded longs *paying* to stay in. That is a
transfer, not a forecast: the carry accrues whether or not price moves, which is why it is the
only candidate here with institutional-scale capacity.

**Why this one first.** It is the closest thing on the list to a real edge rather than a pattern,
and capacity is the constraint that kills everything else. `libs/research/cashcarry.py` and
`crypto_xsec.xsec_funding_returns` already exist — this is a validation job, not a build.

**Primary kill criterion:** net-of-cost Sharpe after **borrow, both legs' fees, and the spot leg's
funding drag**. The carry looks free until the costs of holding the hedge are charged against it.

### 2. OI divergence — price up + OI down is short-covering, not buying

**Mechanism.** Open interest is the count of *open positions*. Price rising while OI falls means
shorts are closing, not longs opening: the move is being paid for by people leaving, and it has
different continuation odds than price rising on rising OI. Four regimes, cleanly separable:

| | OI ↑ | OI ↓ |
|---|---|---|
| **price ↑** | new longs — continuation | short covering — exhaustion |
| **price ↓** | new shorts — continuation | long liquidation — exhaustion |

**Why this one.** It is directly measurable, it is *rarely tested properly* because most people
never join OI to price at the bar level, and the mechanism is arithmetic rather than behavioural —
it does not depend on anyone's psychology being stable.

**Primary kill criterion:** if the four quadrants' forward returns are not distinguishable
(**|d| < 0.2** between continuation and exhaustion quadrants), OI adds nothing to price alone and
this is dead.

### 3. Liquidation cascade exhaustion — already pre-registered

`docs/research/FAILED_BREAKOUT_PREREGISTRATION.md`, written earlier today. Eight kill criteria,
4,860 nominal trials declared, harness built and tested, currently BLOCKED on the same transport
gap. **It counts as one of the three** and no fourth is added.

---

## What is NOT in the three, and why that matters for the arithmetic

**The crowded set — ICT/order-block/FVG, RSI divergence, VWAP reversion, opening-range breakout,
moving-average crosses — is run as a NEGATIVE CONTROL, not as a candidate.**

The distinction is not cosmetic and it changes the trial count:

- A **trial** is a hypothesis that *could be promoted*. Testing twenty and reporting the best
  requires deflating by twenty, because the best of twenty is an order statistic.
- A **control** is pre-declared as expected-to-fail and **cannot promote anything whatever it
  scores**. Its purpose is to measure the harness's false-positive rate — if the harness finds
  "edge" in five things everyone already trades, the harness is broken and every other number it
  has produced is suspect.

So the controls are reported with their results, and they do **not** enter the DSR deflation for
the three above. What they *do* enter is a standing figure: **observed false-positive rate of this
harness**, which is the number that tells you how much to believe a survivor.

If a crowded control comes back with a strong edge, the correct conclusion is **"the harness is
broken"**, not "we found something." That inference is pre-registered here so it cannot be
re-litigated later when the number is in front of me and looks exciting.

---

## Trial budget across all three

| study | nominal | notes |
|---|---|---|
| liquidation cascade (already registered) | ~~4,860~~ **16,200** | grid in its own document; raised by AMENDMENT 1 |
| funding carry | 2 venues × 3 holding rules × 3 funding thresholds × 10 symbols = **180** | |
| OI divergence | 3 OI windows × 3 price windows × 2 timeframes × 10 symbols = **180** | |
| **total** | ~~5,220~~ **16,560** | deflation uses this, not the per-study count |

**Revised 2026-08-06 by AMENDMENT 1** to `FAILED_BREAKOUT_PREREGISTRATION.md`, which added a
management-ablation arm (structural stop, breakeven ratchet) and two higher timeframes. The shared
hurdle moves **4.138 → 4.408 (+6.5%)** on `√(2 ln N)`. Recorded here rather than only in the other
document because these three share one deflation: an axis added to any of them makes the bar
harder for all three, and a budget that is only updated where the axis was added is not shared.

**Still three studies.** The amendment widened one, it did not add a fourth — the arithmetic above
is the whole reason that distinction is enforced rather than trusted.

**The three studies share a deflation.** Running them in one campaign and deflating each against
its own grid would be the same manufacturing this document exists to prevent, one level up.

---

## Order of work when the data lands

1. **Controls first.** Run the crowded set and measure the false-positive rate *before* looking at
   any candidate. A harness that finds edge in moving-average crosses does not get to opine on
   funding carry.
2. Funding carry — mechanism (is funding actually extreme and persistent?), then costs, then score.
3. OI divergence — quadrant separation first; if the quadrants do not separate, stop.
4. Liquidation cascade — per its own document.

Controls first is deliberate: it is the only ordering where the calibration number cannot be
influenced by having already seen a candidate's result.

---

## What would make me abandon each

- **Funding carry** — net Sharpe < 0.5 after borrow and both legs' costs, or capacity < $250k
  (higher bar than the others: capacity is this candidate's entire reason for being on the list).
- **OI divergence** — quadrant separation |d| < 0.2, or the effect confined to a single symbol.
- **Liquidation cascade** — its eight pre-registered criteria, unchanged.

Stated in advance, in one place, before any of it can be run.
