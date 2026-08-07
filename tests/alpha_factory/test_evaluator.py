"""EXECUTING a Combination -- the half the generator did not have.

The generator emitted 898,560 structured hypotheses and had exactly two consumers, neither of which
ran anything. A generator with no evaluator is a list, and the desk had been treating the list as a
pipeline.

At 898,560 cells the failure modes are not individually small. A single alignment error does not
produce one false positive; it produces a whole flattering DISTRIBUTION that looks like a
discovery. So most of this file tests alignment, refusal and accounting rather than arithmetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.alpha_factory.combination_engine import Combination
from libs.alpha_factory.evaluator import MIN_OBS, evaluate, sweep

_RNG = np.random.default_rng(5)


def _feats(n: int = 1000) -> tuple[dict[str, pd.Series], pd.Series]:
    a = pd.Series(_RNG.normal(size=n), name="a")
    b = pd.Series(_RNG.normal(size=n), name="b")
    fwd = pd.Series(_RNG.normal(scale=0.01, size=n), name="f")
    return {"a": a, "b": b}, fwd


def _c(op: str = "interaction", ltf: str = "identity", rtf: str = "identity") -> Combination:
    return Combination("x", "a", "b", op, "1d", "all", ltf, rtf)


def test_A_PLANTED_EDGE_IS_DETECTED() -> None:
    """POSITIVE CONTROL. An evaluator that cannot find a real edge is worthless, and at 898,560
    cells a silently-broken one would return a tidy field of nulls that reads as 'no alpha'."""
    n = 2000
    a = pd.Series(_RNG.normal(size=n), name="a")
    b = pd.Series(np.ones(n), name="b")
    # a[i-1] must predict fwd[i]: the evaluator shifts the signal BACK one bar, so a plant of
    # a.shift(-1) would be the future predicting the past and correctly scores ~0.
    fwd = pd.Series(a.shift(1).to_numpy() * 0.01 + _RNG.normal(scale=0.001, size=n), name="f")
    r = evaluate(_c(), {"a": a, "b": b}, fwd)
    assert r.ok and r.ic > 0.5, f"planted edge not found: ic={r.ic}"


def test_PURE_NOISE_DOES_NOT_PRODUCE_AN_EDGE() -> None:
    """NEGATIVE CONTROL, and the one that matters at scale: if noise scores, 898,560 cells of noise
    will produce a tail that looks exactly like discovery."""
    feats, fwd = _feats(3000)
    r = evaluate(_c(), feats, fwd)
    assert r.ok and abs(r.ic) < 0.10


def test_THE_SIGNAL_IS_SHIFTED_BEFORE_IT_MEETS_THE_TARGET() -> None:
    """THE LEAKAGE TEST. A signal built from the SAME bar as the return must not score, or every
    cell in the sweep inherits the contamination."""
    n = 2000
    fwd = pd.Series(_RNG.normal(scale=0.01, size=n), name="f")
    same_bar = pd.Series(fwd.to_numpy(), name="a")          # perfectly contemporaneous
    r = evaluate(_c(), {"a": same_bar, "b": pd.Series(np.ones(n), name="b")}, fwd)
    assert r.ok and abs(r.ic) < 0.15, (
        f"a contemporaneous feature scored ic={r.ic} -- the shift is not being applied, and every "
        "cell in the sweep would inherit it")


def test_COSTS_ARE_CHARGED_ON_TURNOVER() -> None:
    """WS-006 is the reason this is not tunable: a real, Holm-cleared signal died on exactly this
    number. A sweep with optimistic costs rediscovers 898,560 versions of the same illusion."""
    feats, fwd = _feats(2000)
    cheap = evaluate(_c(), feats, fwd, cost_bp=0.0)
    dear = evaluate(_c(), feats, fwd, cost_bp=50.0)
    assert cheap.gross_bps == dear.gross_bps, "cost must not touch gross"
    assert dear.net_bps < cheap.net_bps
    assert dear.turnover > 0


def test_A_THIN_SAMPLE_IS_UNMEASURED_NOT_NO_EDGE() -> None:
    """An IC on 40 bars is noise with a decimal point, and 898,560 of them would produce a
    flattering tail by construction."""
    feats, fwd = _feats(50)
    r = evaluate(_c(), feats, fwd)
    assert not r.ok and "UNMEASURED" in r.reason


def test_A_CROSS_SECTIONAL_TRANSFORM_REFUSES_WITHOUT_A_PANEL() -> None:
    """rank() over one symbol is a CONSTANT, and a constant signal gives ic=nan that a careless
    caller reads as zero -- an arm silently consuming a trial while testing nothing."""
    feats, fwd = _feats()
    r = evaluate(_c(ltf="rank"), feats, fwd)
    assert not r.ok and "panel" in r.reason


def test_A_CROSS_SECTIONAL_TRANSFORM_WORKS_WITH_A_PANEL() -> None:
    feats, fwd = _feats()
    panel = pd.DataFrame({"a": feats["a"], "b": feats["b"]})
    r = evaluate(_c(ltf="rank"), feats, fwd, panel=panel)
    assert r.ok


def test_A_MISSING_FEATURE_REFUSES_RATHER_THAN_GUESSES() -> None:
    r = evaluate(_c(), {"a": _feats()[0]["a"]}, _feats()[1])
    assert not r.ok and "missing" in r.reason


def test_THE_SWEEP_RETURNS_EVERY_CELL_INCLUDING_FAILURES() -> None:
    """A sweep that silently drops uncomputable cells reports a denominator smaller than the
    universe it declared -- understating the search and therefore the hurdle, which is the exact
    error pre-declaration exists to prevent."""
    feats, fwd = _feats()
    cands = (_c(), _c(ltf="rank"), Combination("x", "a", "MISSING", "ratio", "1d", "all"))
    out = sweep(cands, feats, fwd)
    assert len(out) == len(cands), "the sweep dropped cells"
    assert sum(r.ok for r in out) == 1
    assert all(r.reason for r in out if not r.ok), "a failure with no reason is unauditable"


def test_EVERY_OPERATOR_EVALUATES() -> None:
    """A KeyError mid-sweep surfaces after the enumeration cost is already paid."""
    feats, fwd = _feats()
    for op in ("interaction", "condition", "divergence", "ratio", "lead"):
        assert evaluate(_c(op), feats, fwd).ok, f"{op} failed to evaluate"


def test_THE_KEY_TRAVELS_WITH_THE_RESULT() -> None:
    """898,560 results are unusable without the identity that produced each one."""
    feats, fwd = _feats()
    c = _c("ratio", "delta", "sign")
    assert evaluate(c, feats, fwd).key == c.key
    assert MIN_OBS > 0
