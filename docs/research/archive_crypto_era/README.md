# Archive — the retired crypto-exchange era (closed 2026-08-18)

**Everything in this directory is HISTORY, not a mandate.** The desk's traded and hunted universe
is the MT5/Fusion Markets book (see the repository `README.md` and `docs/LAWS.md`). The
crypto-exchange desk that produced the studies below was retired by principal order on
2026-08-18; nothing here authorizes hunting, screening or scoring a crypto-exchange universe, and
no miner may draw a ground from it.

## Why it is kept rather than deleted

These are **measured negatives with pre-registered protocols**, which is the most expensive kind
of knowledge this desk owns and the cheapest kind to lose. A pre-registration committed before the
data was downloaded, plus the result that falsified it, is the only artifact that can stop a
future session re-running the same study and mistaking a lucky window for an edge. The mechanism
the study tested — intraday rotation in range regimes, continuation after breakout — is not
crypto-specific; it recurs on every leveraged book, this desk's included. The finding transfers
even though the venue does not.

Read them the way you would read a lab notebook from a discontinued programme: the protocol, the
power analysis, the cost treatment and the verdict are reusable; the instruments are not.

## Contents

| File | What it is |
|---|---|
| `INTRADAY_ROTATION_PREREGISTRATION.md` | The grid, regimes, entries, stops and deployment gate, fixed in writing on 2026-08-04 **before** any bar was downloaded or any backtest code existed. Its value is that it was committed first. |
| `INTRADAY_ROTATION_RESULT.md` | The measured answer: **NO-GO on both strategies**, on 315,648 OOS 5-minute bars, walk-forward, costs and funding included, deflated-Sharpe probability ~0. A rigorous negative, which the pre-registration calls a successful output. |

## The transferable lessons, in one place

- A 91% hit rate over n=11 discretionary trades is consistent with anything from a modest true
  edge to a lucky trending week. The study existed to falsify that, and did.
- Rotation in range regimes lost **−0.445 R per trade net over 25,036 OOS trades**. That is not a
  marginal result to retune; it is a family answer, and it is why mean-reversion families rank
  last for marginal research effort in the miner briefs (`ops/frontier_common.txt`).
- Costs decided it. A backtest that omits spread, commission, funding or swap is a *different
  quantity* from the one this desk computes, not a slightly optimistic version of the same one.
- The engine passed a no-lookahead future-shuffle probe and pessimistic-fill tests **before** the
  run. A negative from an unvalidated engine would have been worthless.
