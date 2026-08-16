# MANDATE — MAX NET COMPOUNDING / SURVIVAL-FIRST GROWTH

Binding human mandate. 2026-08-16. Applies to **every desk and every brain in
this repo** — including the MT5 XAUUSD desk, any future sleeves, and the
frozen crypto-information pipeline. A high-return strategy with a high
drawdown must NEVER be abandoned merely because the drawdown looks
uncomfortable. (Exhibit: the current MT5 4-sleeve book — model ~116%/yr
arithmetic at 0.01 lot/sleeve with worst historical DD -51%.)

## PRIMARY OBJECTIVE

Maximize robust forward **net geometric growth / E[log wealth]**, not
smoothness, low drawdown, win rate, or arithmetic return.

High drawdown is acceptable **if it remains survivable and increases long-run
compounded wealth**.

The desk must never reduce sizing merely because a drawdown looks
uncomfortable. It must reduce sizing only when higher leverage lowers expected
geometric growth through excessive tail risk, margin pressure, stop-out
probability, parameter uncertainty, or meaningful risk of ruin.

## SIZING DISCIPLINE (mandatory for every candidate risk/lot size)

Estimate:

```text
net geometric CAGR
median terminal wealth
5th-percentile terminal wealth

P(DD > 30%)
P(DD > 50%)
P(DD > 70%)

P(margin call)
P(broker stop-out)
P(ruin)

worst stress DD
margin headroom
cross-sleeve correlation
tail/gap exposure
forward expectancy after all costs
```

Use dependence-aware **block bootstrap / Monte Carlo / stress testing**,
preserving correlations between simultaneous sleeves and adverse market
regimes.

Evaluate a full sizing curve rather than selecting size manually:

```text
0.005 lot, 0.0075, 0.010, 0.0125, 0.015, 0.020, ...
```

Choose the sizing region that maximizes **robust expected geometric growth**,
accounting for uncertainty in the estimated edge.

## NON-NEGOTIABLE PRINCIPLES

- **Drawdown ≠ ruin.** A deep but recoverable drawdown may be economically
  optimal.
- **Arithmetic CAGR ≠ compounding CAGR.** Never maximize headline return by
  using leverage that reduces long-run geometric wealth.
- **Pretty equity curves have no inherent value.** Risk reduction must earn its
  place through higher expected forward economic value.
- **Ruin is qualitatively different from drawdown.** Sizing that introduces
  meaningful probability of liquidation, margin failure, or permanent capital
  destruction is unacceptable even if arithmetic expected return is higher.
- **Costs and tail events are mandatory.** Spread, slippage, commissions,
  swaps, gaps, correlated sleeve losses, broker constraints and extreme
  historical/stressed moves must be included.

## FINAL INVARIANT

> **MAXIMIZE SUSTAINABLE NET COMPOUNDING. ACCEPT LARGE DRAWDOWNS WHEN THEY ARE
> THE ECONOMICALLY OPTIMAL PRICE OF HIGHER LONG-RUN GROWTH, BUT NEVER ACCEPT
> LEVERAGE THAT MATERIALLY INCREASES THE PROBABILITY OF RUIN OR REDUCES ROBUST
> GEOMETRIC WEALTH.**

maximize forward net geometric growth, subject only to avoiding ruin / forced
liquidation / account constraints.

Not: minimize drawdown.

A strategy with 100%+ expected annual return and a 50% drawdown can be
economically preferable to one doing 25% with a 10% drawdown, depending on the
return distribution and leverage. Kelly-style growth theory is explicitly about
maximizing long-run geometric growth rather than minimizing volatility or
drawdown.

**The objective is not the safest equity curve. It is the highest survivable
compounding rate.**

## OPERATING RULES FOR THIS REPO

1. No brain may deprioritize, "simplify away", or propose deleting a strategy
   because of drawdown size while P(ruin) is negligible and geometric growth
   is positive. Any such proposal must instead quantify
   `E[log wealth]` at the sizing curve's optimum.
2. Sizing changes must reference a sizing-curve study (block bootstrap/MC,
   costs inside, stress variants). See `desks/mt5/docs/SIZING_STUDY.md` for
   the flagship book's study.
3. The MT5 desk keeps hunting and testing more and more sleeves on the same
   pipeline as the crypto system used to: gate (t>2, n>60, WF OOS, param
   robustness, cost stress), verdict, deploy. Crypto data feeds remain
   information inputs only.