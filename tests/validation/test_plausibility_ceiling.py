"""Too good to be true is a question: flagged cells go to forensics; only proven leaks fail."""
from __future__ import annotations

import numpy as np

from libs.validation.plausibility import MAX_ANNUAL_SHARPE, forensics, plausibility_stage, screen


def _hot(seed: int = 7, n: int = 500) -> np.ndarray:
    return np.abs(np.random.default_rng(seed).normal(0.5, 0.2, n))


def _noise(seed: int, n: int = 500) -> np.ndarray:
    return np.random.default_rng(seed).normal(-0.01, 1.0, n)


def test_an_ordinary_weak_edge_is_not_flagged() -> None:
    r = np.random.default_rng(7).normal(0.03, 1.0, 750)
    st = plausibility_stage(r)
    assert st["passed"] is True and st["verdict"] == "PLAUSIBLE"


def test_thresholds_alone_never_reject() -> None:
    hot = _hot()
    assert screen(hot)["suspect"] and screen(hot)["annual_sharpe"] > MAX_ANNUAL_SHARPE
    st = plausibility_stage(hot)  # no forensics ran
    assert st["passed"] is True and st["verdict"] == "SUSPECT_UNFORENSICED"


def test_a_real_monster_survives_forensics_and_is_fast_tracked() -> None:
    hot = _hot()
    fx = forensics(hot, delayed=hot * 0.7, flipped=-hot,
                   shuffled=[_noise(s) for s in range(5)], pit_violations=[])
    st = plausibility_stage(hot, fx)
    assert fx["verdict"] == "MONSTER_CANDIDATE"
    assert st["passed"] is True and st["fast_track"] is True


def test_a_harness_leak_is_proven_by_both_nulls_and_refused() -> None:
    hot = _hot()
    fx = forensics(hot, delayed=hot, flipped=hot, shuffled=[_hot(s) for s in range(5)])
    st = plausibility_stage(hot, fx)
    assert fx["verdict"] == "LEAK_PROVEN" and st["passed"] is False


def test_a_pit_violation_is_proof() -> None:
    hot = _hot()
    fx = forensics(hot, pit_violations=["fred:GDP vintage after decision"])
    assert fx["verdict"] == "LEAK_PROVEN"


def test_delay_collapse_alone_is_not_proof() -> None:
    hot = _hot()
    fx = forensics(hot, delayed=_noise(1), flipped=-hot, shuffled=[_noise(s) for s in range(5)])
    st = plausibility_stage(hot, fx)
    assert fx["verdict"] == "DELAY_FRAGILE" and st["passed"] is True and st["fast_track"]


def test_build_arms_runs_on_real_signals() -> None:
    import dataclasses

    import pandas as pd

    from libs.validation.plausibility import build_arms

    @dataclasses.dataclass(frozen=True)
    class S:
        time: pd.Timestamp
        side: int
        stop: float
        target: float
        trigger: float | None = None

    idx = pd.date_range("2025-01-01", periods=200, freq="h")
    df = pd.DataFrame({"close": np.linspace(100, 120, 200)}, index=idx)
    sigs = [S(idx[i], 1, 99.0, 130.0) for i in range(0, 190, 10)]
    seen: list[list] = []
    arms = build_arms(df, sigs, lambda sg: (seen.append(sg), np.ones(len(sg)))[1], n_shuffles=2)
    assert {"delayed", "flipped", "shuffled"} <= set(arms)
    assert all(a.time > b.time for a, b in zip(seen[0], sigs, strict=False))
    assert all(f.side == -1 and f.stop > f.target for f in seen[1])


def _bars(n: int = 600):
    import pandas as pd
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    c = 100 + np.cumsum(np.random.default_rng(3).normal(0, 0.2, n))
    import pandas as pd
    return pd.DataFrame({"close": c}, index=idx)


def _sig(t, side, px):
    import dataclasses

    import pandas as pd

    @dataclasses.dataclass(frozen=True)
    class S:
        time: pd.Timestamp
        side: int
        stop: float
        target: float
        trigger: float | None = None
    return S(t, side, px - side, px + side * 0.2)


def test_truncation_proves_a_peek_ahead_leak() -> None:
    from libs.validation.plausibility import truncation_test

    def leak(f):
        c = f["close"].to_numpy()
        return [_sig(f.index[i], 1 if c[i + 2] > c[i + 1] else -1, c[i])
                for i in range(0, len(f) - 3, 7)]
    df = _bars()
    out = truncation_test(df, leak(df), leak)
    assert out["leak"] is True and out["changed"] > 0


def test_truncation_clears_an_honest_family() -> None:
    from libs.validation.plausibility import truncation_test

    def honest(f):
        c = f["close"].to_numpy()
        return [_sig(f.index[i], 1 if c[i] > c[i - 1] else -1, c[i])
                for i in range(1, len(f) - 1, 7)]
    df = _bars()
    out = truncation_test(df, honest(df), honest)
    assert out["ran"] is True and out["leak"] is False and out["changed"] == 0
