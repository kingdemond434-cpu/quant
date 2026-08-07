"""EXECUTE a Combination -- the missing half of the generator.

MEASURED 2026-08-07: `combination_engine` had exactly two consumers, and neither ran anything. It
emitted 898,560 structured hypotheses and nothing could turn one into a number. A generator with no
evaluator is a list, and the desk had been treating the list as a pipeline.

Compute was never the constraint and the estimate settles it: one candidate on 5,000 bars costs
~0.11 ms, so the FULL 898,560-candidate universe evaluates in **under two minutes single-core**.
That is what makes full-universe evaluation the right default rather than an aspiration -- there is
no sampling decision to justify, because there is nothing to save.

**THE FULL UNIVERSE IS DECLARED BEFORE EXECUTION, NOT AFTER.** Testing 20,000 and then deciding what
the remaining 878,560 mean is adaptive selection wearing a sweep's clothing. Declaring all of them
first removes the selection problem for this family entirely (L1.52's first edge) -- and it is the
only reason a blind sweep of this size is statistically legitimate at all.

**AND IT STAYS A SEPARATE FAMILY FROM THE PRE-REGISTERED STUDIES.** The 20,052 trials in
FAILED_BREAKOUT / THREE_MECHANISM / ETHBTC / MANAGEMENT_SWEEP are MECHANISM hypotheses with named
kill criteria; this is blind enumeration. Merging the two budgets would raise the bar on studies
that argued for their hypotheses in advance, to pay for a sweep that argued for nothing. They are
different epistemic objects, they are reported separately, and neither may be used to select within
the other -- which is what keeps them separate families rather than one 918,612-trial pool.

WHAT THIS DOES NOT DO. It computes an IC and a net-of-cost number. It does not promote, size, or
decide. Every survivor here still owes out-of-sample, CPCV/DSR, independence clustering and a
portfolio contribution before the word means anything (L1.52(a)'s four counts).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from libs.alpha_factory.combination_engine import CROSS_SECTIONAL, Combination

#: Round-trip cost in basis points, charged on TURNOVER. Not a parameter to tune: the whole
#: liquidity finding (WS-006) is that a real signal died on this number, so a sweep that leaves it
#: optimistic will rediscover 898,560 versions of the same illusion.
DEFAULT_COST_BP: float = 10.0

#: Below this many usable observations the cell reports UNMEASURED rather than a number. An IC on
#: 40 bars is noise with a decimal point, and 898,560 of them would produce a flattering tail by
#: construction.
MIN_OBS: int = 200


@dataclass(frozen=True)
class CellResult:
    """One candidate, evaluated. `ok=False` means NOT MEASURED, never 'no edge'."""

    key: tuple[str, ...]
    ok: bool
    n: int = 0
    ic: float = 0.0
    gross_bps: float = 0.0
    turnover: float = 0.0
    net_bps: float = 0.0
    reason: str = ""


def _transform(x: pd.Series, tf: str, *, panel: pd.DataFrame | None) -> pd.Series | None:
    """Apply one unary transform. None when the transform's data requirement is unmet.

    CROSS-SECTIONAL TRANSFORMS RETURN None WITHOUT A PANEL rather than degenerating. `rank` over a
    single symbol is a constant, and a constant signal produces IC=nan which a careless caller
    reads as zero -- one more arm silently consuming a trial while testing nothing.
    """
    if tf == "identity":
        return x
    if tf in CROSS_SECTIONAL:
        if panel is None or panel.shape[1] < 2:
            return None
        if tf == "rank":
            return panel.rank(axis=1, pct=True)[x.name]
        return ((panel.sub(panel.mean(axis=1), axis=0))
                .div(panel.std(axis=1).replace(0.0, np.nan), axis=0))[x.name]
    if tf == "delta":
        return x.diff()
    if tf == "ts_rank":
        return x.rolling(60, min_periods=30).rank(pct=True)
    if tf == "decay":
        return x.ewm(halflife=10, min_periods=10).mean()
    if tf == "sign":
        return np.sign(x)
    if tf == "abs":
        return x.abs()
    return None


def _relate(a: pd.Series, b: pd.Series, op: str) -> pd.Series | None:
    """Combine two transformed features under the declared relation."""
    if op == "interaction":
        return a * b
    if op == "condition":
        return a * (b > b.median()).astype(float)   # a, gated by b being high
    if op == "divergence":
        return a.rank(pct=True) - b.rank(pct=True)
    if op == "ratio":
        return a / b.replace(0.0, np.nan)
    if op == "lead":
        return a.shift(1) * b                        # a leads b
    return None


def evaluate(c: Combination, feats: dict[str, pd.Series], fwd: pd.Series, *,
             panel: pd.DataFrame | None = None, cost_bp: float = DEFAULT_COST_BP,
             min_obs: int = MIN_OBS) -> CellResult:
    """Evaluate one candidate against forward returns.

    THE SIGNAL IS SHIFTED ONE BAR BEFORE IT MEETS THE TARGET, unconditionally. Every leakage
    incident this desk has recorded came from a signal observable at or after the return it
    predicts, and at 898,560 cells a single alignment error does not produce one false positive --
    it produces a whole flattering distribution that looks like a discovery.
    """
    a0, b0 = feats.get(c.left), feats.get(c.right)
    if a0 is None or b0 is None:
        return CellResult(c.key, False, reason=f"feature missing: {c.left}/{c.right}")
    a = _transform(a0, c.left_tf, panel=panel)
    b = _transform(b0, c.right_tf, panel=panel)
    if a is None or b is None:
        return CellResult(c.key, False,
                          reason=f"transform unavailable ({c.left_tf}/{c.right_tf}) -- "
                                 "cross-sectional transforms need a panel")
    sig = _relate(a, b, c.operator)
    if sig is None:
        return CellResult(c.key, False, reason=f"unknown operator {c.operator}")

    sig = sig.replace([np.inf, -np.inf], np.nan).shift(1)      # observable strictly before fwd
    df = pd.DataFrame({"s": sig, "f": fwd}).dropna()
    if len(df) < min_obs or float(df["s"].std()) == 0.0:
        return CellResult(c.key, False, n=len(df),
                          reason=f"UNMEASURED: {len(df)} usable obs (<{min_obs}) or flat signal")

    z = (df["s"] - df["s"].mean()) / df["s"].std()
    pos = z.clip(-3, 3) / 3.0                                   # bounded exposure, unit-ish
    ic = float(np.corrcoef(df["s"], df["f"])[0, 1])
    gross = float((pos * df["f"]).mean()) * 10_000.0
    turn = float(pos.diff().abs().mean())
    net = gross - turn * cost_bp
    return CellResult(c.key, True, len(df), ic, gross, turn, net)


def sweep(cands: tuple[Combination, ...], feats: dict[str, pd.Series], fwd: pd.Series,
          **kw: object) -> list[CellResult]:
    """Evaluate a declared universe. Returns EVERY cell, including the unmeasurable ones.

    FAILURES ARE RETURNED, NOT DROPPED. A sweep that silently discards cells it could not compute
    reports a denominator smaller than the universe it declared, which understates the search and
    therefore the hurdle -- the exact error the pre-declaration was meant to prevent.
    """
    return [evaluate(c, feats, fwd, **kw) for c in cands]  # type: ignore[arg-type]
