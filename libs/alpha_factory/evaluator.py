"""EXECUTE a Combination -- the missing half of the generator.

MEASURED 2026-08-07: `combination_engine` had exactly two consumers, and neither ran anything. It
emitted 898,560 structured hypotheses and nothing could turn one into a number. A generator with no
evaluator is a list, and the desk had been treating the list as a pipeline.

COMPUTE IS THE CONSTRAINT, AND IT SCALES WITH THE SAMPLE, NOT WITH THE UNIVERSE. One candidate on
5,000 bars costs ~0.11 ms, which puts the full 898,560-candidate space at a couple of minutes --
but the cost is LINEAR IN BARS, so the same sweep over a 2M-row pooled tape is hours, not minutes.
An earlier version of this docstring quoted the small-sample figure as if it were the sweep's cost;
it is not, and `scripts/run_full_sweep.py` therefore MEASURES the per-cell cost on a calibration
batch and refuses to start a run it cannot finish inside a declared budget. Full-universe
evaluation is still the right default -- there is no sampling decision to justify -- but the
sample WINDOW is a real choice and has to be reported as one.

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

from dataclasses import dataclass, field

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
    #: Per-bar realised net return, on the SIGNAL'S OWN INDEX with NaN wherever the cell had no
    #: usable observation. Populated only when `keep_pnl=True`, because 898,560 of these would not
    #: fit in memory -- and it is kept index-aligned rather than compacted because
    #: `independence.cluster()` compares series POSITIONALLY, so two survivors that dropped
    #: different bars would otherwise be correlated against a misalignment.
    pnl: pd.Series | None = field(default=None, compare=False, repr=False)


def transform(x: pd.Series, tf: str, *, panel: pd.DataFrame | None) -> pd.Series | None:
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


def evaluate(c: Combination, feats: dict[str, pd.Series], fwd: pd.Series | np.ndarray, *,
             panel: pd.DataFrame | None = None, cost_bp: float = DEFAULT_COST_BP,
             min_obs: int = MIN_OBS, keep_pnl: bool = False) -> CellResult:
    """Evaluate one candidate against forward returns.

    THE SIGNAL IS SHIFTED ONE BAR BEFORE IT MEETS THE TARGET, unconditionally. Every leakage
    incident this desk has recorded came from a signal observable at or after the return it
    predicts, and at 898,560 cells a single alignment error does not produce one false positive --
    it produces a whole flattering distribution that looks like a discovery.

    **SIGNAL AND TARGET ARE ALIGNED POSITIONALLY, AND A LENGTH MISMATCH RAISES.** Index alignment
    would look friendlier and is the more dangerous default here: a caller whose target is on a
    different grid would get a silently-truncated intersection and a correlation computed about the
    misalignment. A `ValueError` costs one debugging minute; a quiet intersection costs a verdict.

    NON-FINITE VALUES ARE EXCLUDED FROM BOTH SIDES, not just NaN. A `ratio` operator divides, and an
    inf that survives into `corrcoef` does not produce a warning the reader will see -- it produces
    a number.
    """
    a0, b0 = feats.get(c.left), feats.get(c.right)
    if a0 is None or b0 is None:
        return CellResult(c.key, False, reason=f"feature missing: {c.left}/{c.right}")
    a = transform(a0, c.left_tf, panel=panel)
    b = transform(b0, c.right_tf, panel=panel)
    if a is None or b is None:
        return CellResult(c.key, False,
                          reason=f"transform unavailable ({c.left_tf}/{c.right_tf}) -- "
                                 "cross-sectional transforms need a panel")
    sig = _relate(a, b, c.operator)
    if sig is None:
        return CellResult(c.key, False, reason=f"unknown operator {c.operator}")

    sig = sig.shift(1)                                          # observable strictly before fwd
    s_all = sig.to_numpy(dtype=float, copy=False)
    f_all = np.asarray(fwd, dtype=float)
    if s_all.size != f_all.size:
        raise ValueError(
            f"signal ({s_all.size}) and forward returns ({f_all.size}) differ in length; they "
            "are aligned positionally, so a mismatch is a caller bug, not something to intersect")

    mask = np.isfinite(s_all) & np.isfinite(f_all)
    n = int(mask.sum())
    s, f = s_all[mask], f_all[mask]
    # A FLAT TARGET IS AS UNMEASURABLE AS A FLAT SIGNAL, and it is the one a regime-conditioned
    # slice actually hits. Without this guard `corrcoef` divides by zero, emits a RuntimeWarning
    # nobody reads in a 898,560-cell loop, and returns nan -- which downstream reads as "no edge".
    if n < min_obs or float(s.std()) == 0.0 or float(f.std()) == 0.0:
        return CellResult(c.key, False, n=n,
                          reason=f"UNMEASURED: {n} usable obs (<{min_obs}), flat signal or flat "
                                 "target")

    z = (s - s.mean()) / s.std()
    pos = np.clip(z, -3.0, 3.0) / 3.0                           # bounded exposure, unit-ish
    ic = float(np.corrcoef(s, f)[0, 1])
    gross = float((pos * f).mean()) * 10_000.0
    dpos = np.abs(np.diff(pos)) if pos.size > 1 else np.zeros(0)
    turn = float(dpos.mean()) if dpos.size else 0.0
    net = gross - turn * cost_bp

    pnl = None
    if keep_pnl:
        per_bar = pos * f - np.concatenate([[0.0], dpos]) * (cost_bp / 10_000.0)
        full = np.full(s_all.size, np.nan)
        full[mask] = per_bar
        pnl = pd.Series(full, index=sig.index)
    return CellResult(c.key, True, n, ic, gross, turn, net, "", pnl)


def sweep(cands: tuple[Combination, ...], feats: dict[str, pd.Series],
          fwd: pd.Series | np.ndarray, **kw: object) -> list[CellResult]:
    """Evaluate a declared universe. Returns EVERY cell, including the unmeasurable ones.

    FAILURES ARE RETURNED, NOT DROPPED. A sweep that silently discards cells it could not compute
    reports a denominator smaller than the universe it declared, which understates the search and
    therefore the hurdle -- the exact error the pre-declaration was meant to prevent.
    """
    arr = np.asarray(fwd, dtype=float)          # converted ONCE, not 898,560 times
    return [evaluate(c, feats, arr, **kw) for c in cands]  # type: ignore[arg-type]
