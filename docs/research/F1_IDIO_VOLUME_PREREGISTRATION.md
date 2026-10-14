# Pre-registration — F1, the idiosyncratic tick-volume spike, faded

**Written 2026-10-14T03:16Z. This is AFTER a measurement on the same history, and that measurement
is disclosed below.** It is not a "before any data" preregistration and does not claim to be one.
The family code and the 21 cells were committed at 2026-10-14T02:36Z (`a15263891`). The direction
measurement in `market_ecology._flow_pressure` was taken while that commit was being written. No
document in `docs/research/` fixed the parameters below before that. What this file does is
freeze them now, against the gauntlet's own run, so that nothing below moves in response to a
result.

---

## The mechanism, and the direction it fixes

Tick volume on a retail CFD feed counts quote updates. Most of its hour-to-hour variation is
**common**: the London open, a US print or a risk-off afternoon raises every symbol together. What
remains, after the cross-sectional activity factor and the hour-of-week rhythm are removed, is
activity peculiar to **one** instrument: a large order working through it, a stop cascade, a
fixing hedge. That burst moves price through **inventory pressure, not information**. The
liquidity provider who absorbed it (axis_registry: `inventory_shock / microstructure / market`)
lays the inventory off over the following hours, so the move retraces.

**Direction: FADE the spike bar's close-vs-open move.** This comes from the mechanism. It is not
fitted, and no measurement chose it.

## The cells: fixed, 21, one trial each

| parameter | value |
|---|---|
| family | `idio_volume_reversal` (`desks/mt5/mt5desk/family_idio_volume.py`) |
| symbols (7) | EURUSD, GBPUSD, AUDUSD, USDJPY, EURZAR, USDZAR, XAUUSD |
| spike threshold | hour-of-week residual **z > 3.0** |
| holds | **1, 2 and 4** H1 bars, entered at the next bar's open |
| timeframe | H1 |
| cost cap | refuse an entry whose fill spread exceeds **0.25 × ATR(20)** |
| stop / target | 1.5 ATR stop, rr 1.0 |
| peers (factor) | EURUSD GBPUSD USDJPY AUDUSD USDCAD USDCHF NZDUSD EURJPY XAUUSD XAGUSD US500 NAS100 GER40 (min 4 loaded) |
| trailing windows | beta 500 bars (lagged one bar); demean 500; at least 8 prior same-hour-of-week observations |

7 symbols × 3 holds = **21 cells**, donated once by `market_ecology.donate_f1` and charged as
**21 trials**. The orthogonal sweep declines the family (`NOT_SOURCED_HERE`), so no second
charge arises under other identities. The Tier S bar is unchanged.

## Disclosure: the measurement taken before this was written

`market_ecology._flow_pressure` measured the forward return after z > 3 spikes on EURUSD, signed
against the spike, on **the same history the gauntlet will test**:

- h = 2: mean fade return **−0.00053**, block-permutation **p = 0.0125**. That is **CONTINUATION,
  not reversal**, and significant at that level.

This result contradicts the preregistered direction, and it was seen before this file was written.
The cells were not changed in response. They fade, as the mechanism says, and the gauntlet judges
them as written. A reader should weigh the F1 result knowing that the in-sample evidence already
on file points the other way.

## Continuation is a different hypothesis

Any **continuation** variant is a **new, separately charged trial**: a new family name or a new
identity, with its own preregistration and its own trial count. Under this preregistration **none
is minted**, and none is to be minted by flipping a sign on these 21 cells. Flipping the
direction after seeing p = 0.0125 would be choosing the hypothesis from the data.

## Costs: what is point-in-time and what is not

- **Point-in-time:** the fill bar's **own recorded MT5 `spread`** (points × the symbol's tick size)
  is used whenever the bar recorded one (> 0). Caveat: MT5 bar spread is commonly the bar's
  minimum, so it can understate the fill.
- **Not point-in-time (disclosed):** where a bar recorded no spread (0 or missing), the filter falls
  back to **today's** per-symbol, per-hour p50 from `data/cost_surface.json`. That applies today's
  costs to history. The sealed gauntlet separately charges its modal fill-hour spread, which is
  its own cost model and is unchanged here.

## Kill criteria

These are the gauntlet's standing ones (deflated Sharpe on the honest trial count, the
program-level SPA/PBO, net-of-cost Sharpe), applied to each of the 21 cells. A dead cell is not
revived with a different z, hold, symbol set or direction under this preregistration.
