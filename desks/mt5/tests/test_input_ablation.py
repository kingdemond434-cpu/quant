"""Each allocator input is judged against the plain solve OUT OF SAMPLE (2026-10-27).

zuck 2026-10-27: "constantly maximise all so they have highest chanc of profitabilities n
beatings". An input earns money only by beating the allocator without it on outcomes it had not
seen; these tests pin the walk-forward, the as-of reads and the verdict bar.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import macro_state  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

ia = pytest.importorskip("research.input_ablation", reason="ships with the desk")


def _matrix(n: int = 420, seed: int = 0) -> pd.DataFrame:
    """Two sleeves whose winner flips with a hidden state that persists for whole windows."""
    rng = np.random.default_rng(seed)
    state = np.repeat(rng.integers(0, 2, n // 5 + 1), 5)[:n]
    a = np.where(state == 0, 0.05, -0.05) + rng.normal(0, 0.02, n)
    b = np.where(state == 1, 0.05, -0.05) + rng.normal(0, 0.02, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({"A": a, "B": b}, index=idx)
    df.attrs["state"] = state
    return df


def _evidence(seen: list[str] | None = None):
    def build(hist: pd.DataFrame) -> list[SleeveEvidence]:
        if seen is not None:
            seen.append(str(hist.index[-1]))
        return [SleeveEvidence(name=c, daily_r=hist[c].to_numpy(), family="f", symbol=c,
                               n_trials=1, forward_days=0, live_days=0, cost_r=0.0)
                for c in hist.columns]
    return build


def _fake(df: pd.DataFrame, seen: list[tuple[str, str]], *, unmeasured_every: int = 0,
          pit: bool = True):
    """`regime` sees the NEXT window's state (an input that truly knows something), `macro` sees
    it too but may be flagged not point-in-time; the solve funds whichever sleeve the arm names,
    or splits evenly when given nothing."""
    state = df.attrs["state"]
    pos = {d: i for i, d in enumerate(df.index)}
    calls = {"n": 0}

    def arm_inputs(arm, asof, hist):
        seen.append((asof, str(hist.index[-1])))
        calls["n"] += 1
        if unmeasured_every and arm == "regime" and calls["n"] % unmeasured_every:
            return ia.ArmInputs(measured=False, why="test: unreadable")
        nxt = int(state[pos[asof] + 1])
        pick = nxt if arm in ("regime", "macro") else 1 - nxt
        return ia.ArmInputs(regime_probs=(("pick", float(pick)),),
                            point_in_time=pit if arm == "macro" else True)

    def solve(ev_t, cfg):
        if not cfg.regime_probs:
            return {"A": 0.05, "B": 0.05}
        return {"A": 0.1, "B": 0.0} if cfg.regime_probs[0][1] == 0.0 else {"A": 0.0, "B": 0.1}
    return arm_inputs, solve


def _harmful(df: pd.DataFrame):
    state = df.attrs["state"]
    pos = {d: i for i, d in enumerate(df.index)}

    def arm_inputs(arm, asof, hist):
        return ia.ArmInputs(regime_probs=(("pick", float(1 - int(state[pos[asof] + 1]))),))
    return arm_inputs


def test_a_knowing_input_is_promoted_and_nothing_reads_ahead() -> None:
    df = _matrix()
    seen: list[tuple[str, str]] = []
    ev_seen: list[str] = []
    arm_inputs, solve = _fake(df, seen)
    res = ia.ablate(df, _evidence(ev_seen), arm_inputs, solve=solve, warmup=250)
    assert res["verdicts"]["regime"]["verdict"] == "PROMOTE"
    # Arms and evidence were built from history ending exactly on each rebalance day.
    assert seen and all(asof == last for asof, last in seen)
    assert ev_seen == [r["asof"] for r in res["windows"]]
    starts = [df.index.get_loc(r["asof"]) for r in res["windows"]]
    assert all(b - a == ia.STEP for a, b in pairwise(starts))


def test_a_harmful_input_is_demoted() -> None:
    df = _matrix()
    _, solve = _fake(df, [])
    res = ia.ablate(df, _evidence(), _harmful(df), solve=solve, warmup=250, arms=("plain", "x"))
    assert res["verdicts"]["x"]["verdict"] == "DEMOTE"


def test_unmeasured_windows_leave_the_sample_and_are_never_zeros() -> None:
    """Audit HOLD on cc12a0b2: 4 real windows plus 22 zero-difference fallbacks read n=26 and
    PROMOTE. A window the input could not be read on now leaves its sample."""
    df = _matrix()
    arm_inputs, solve = _fake(df, [], unmeasured_every=2)
    res = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, max_windows=30)
    v = res["verdicts"]["regime"]
    assert v["unmeasured_windows"] > 0
    assert v["n_periods"] == 30 - v["unmeasured_windows"] < ia.MIN_PERIODS
    assert v["verdict"] == "UNPROVEN"


def test_macro_cannot_promote_on_revisable_data() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [], pit=False)
    res = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250)
    assert res["verdicts"]["regime"]["verdict"] == "PROMOTE"
    assert res["verdicts"]["macro"]["verdict"] == "UNPROVEN"
    assert "point-in-time" in res["verdicts"]["macro"]["why"]
    arm_inputs, solve = _fake(df, [], pit=True)
    res = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250)
    assert res["verdicts"]["macro"]["verdict"] == "PROMOTE"


def test_too_few_windows_is_unproven_whatever_the_sign() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    res = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, max_windows=10)
    assert {v["verdict"] for v in res["verdicts"].values()} == {"UNPROVEN"}


def test_the_bar_is_the_constant_raised_for_several_inputs() -> None:
    assert ia.T_DECIDE == 2.0 and ia.MIN_PERIODS == 26
    assert ia.t_bar(26, 1) == pytest.approx(2.06, abs=0.01)
    assert ia.t_bar(26, 2) == pytest.approx(2.385, abs=0.01)
    assert ia.t_bar(10_000, 1) == ia.T_DECIDE
    flat = ia.paired_verdict([(0.001, 0.0), (-0.001, 0.0)] * 20)
    assert flat["verdict"] == "UNPROVEN"
    win = [(0.01 + 0.001 * (i % 3), 0.0) for i in range(30)]
    lose = [(-0.01 - 0.001 * (i % 3), 0.0) for i in range(30)]
    assert ia.paired_verdict(win, n_inputs=2)["verdict"] == "PROMOTE"
    assert ia.paired_verdict(lose, n_inputs=2)["verdict"] == "DEMOTE"
    # t = 2.2 passes a single input's bar and not two inputs'.
    rng = np.random.default_rng(3)
    d = rng.normal(0, 1, 30)
    d = (d - d.mean()) / d.std(ddof=1) + 2.2 / math.sqrt(30)
    pairs = [(float(x), 0.0) for x in d]
    assert ia.paired_verdict(pairs, n_inputs=1)["verdict"] == "PROMOTE"
    assert ia.paired_verdict(pairs, n_inputs=2)["verdict"] == "UNPROVEN"


def test_ruin_and_zero_variance_are_decided_explicitly() -> None:
    ok = [(0.01 + 0.001 * (i % 3), 0.0) for i in range(30)]
    v = ia.paired_verdict([*ok, (-math.inf, 0.01)])
    assert v["verdict"] == "DEMOTE" and v["ruined_windows"] == 1
    v = ia.paired_verdict([*ok, (0.01, -math.inf), (-math.inf, -math.inf)])
    assert v["plain_ruined_windows"] == 1 and v["unmeasured_windows"] == 1
    assert v["n_periods"] == 30 and v["verdict"] == "PROMOTE"
    v = ia.paired_verdict([(0.01, 0.0)] * 30)
    assert v["verdict"] == "UNPROVEN" and v["t"] is None


def test_realized_growth_is_log_of_the_book_return_and_ruin_is_minus_infinity() -> None:
    fwd = pd.DataFrame({"A": [0.1, -0.05], "B": [0.0, 0.2]})
    g = ia.realized_growth({"A": 0.5, "B": 0.25}, fwd)
    assert g == pytest.approx(np.log1p(0.05) + np.log1p(-0.025 + 0.05))
    assert ia.realized_growth({"A": 20.0}, fwd) == float("-inf")


def test_a_second_run_reuses_every_window_and_a_revised_input_does_not() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    cache: dict = {}
    persisted: list[int] = []
    first = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, cache=cache,
                      on_window=lambda: persisted.append(len(cache)))
    second = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, cache=cache)
    assert first["cache_hits"] == 0 and second["cache_hits"] == second["n_windows"]
    assert persisted == list(range(1, first["n_windows"] + 1))
    assert json.dumps(first["verdicts"]) == json.dumps(second["verdicts"])
    third = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, cache=cache,
                      window_key=lambda asof: "revised")
    assert third["cache_hits"] == 0


def test_past_the_deadline_no_new_window_is_solved_and_the_rest_wait() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    cache: dict = {}
    res = ia.ablate(df, _evidence(), arm_inputs, solve=solve, warmup=250, cache=cache,
                    deadline=0.0)
    assert res["n_windows"] == 0 and res["pending_windows"] > 0 and not cache
    assert {v["verdict"] for v in res["verdicts"].values()} == {"UNPROVEN"}


def test_verdict_for_fails_closed_and_reads_only_a_complete_measurement(tmp_path: Path) -> None:
    assert ia.verdict_for("regime", tmp_path / "absent.json") == "UNPROVEN"
    p = tmp_path / "r.json"
    doc = {"status": "MEASURED", "verdicts": {"regime": {"verdict": "PROMOTE"},
                                              "macro": {"verdict": "WHATEVER"}}}
    p.write_text(json.dumps(doc), "utf-8")
    assert ia.verdict_for("regime", p) == "PROMOTE"
    assert ia.verdict_for("macro", p) == "UNPROVEN"
    p.write_text(json.dumps({**doc, "status": "PARTIAL"}), "utf-8")
    assert ia.verdict_for("regime", p) == "UNPROVEN"
    p.write_text("{torn", "utf-8")
    assert ia.verdict_for("regime", p) == "UNPROVEN"


def test_the_hourly_cycle_runs_it_as_its_own_leg_and_the_daily_chain_does_not() -> None:
    import daily_cycle
    assert "input_ablation" not in [n for n, _ in daily_cycle.STEPS]
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"input_ablation", "research/input_ablation.py", "--budget-s", "600"' in src
    assert ia.BUDGET_S == 600.0


# ------------------------------------------------------------------ the as-of reads

def _archive(tmp_path: Path, rows: int | None = None) -> tuple[Path, list[str]]:
    n = 600
    end = datetime.now(tz=UTC).replace(tzinfo=None)
    days = [(end - pd.Timedelta(days=n - 1 - i)).date().isoformat() for i in range(n)]
    dxy = np.concatenate([np.linspace(125.0, 95.0, 300), np.linspace(95.0, 125.0, 300)])
    keep = set(days[:rows] if rows else days)
    doc = {"updated": end.isoformat(), "series": {
        "DTWEXBGS": [[d, float(v)] for d, v in zip(days, dxy, strict=True) if d in keep],
        "VIXCLS": [[d, 15.0] for d in days if d in keep],
        "DGS10": [[d, 4.0] for d in days if d in keep]}}
    p = tmp_path / f"fred_{rows or 'all'}" / "fred_macro.json"
    p.parent.mkdir()
    p.write_text(json.dumps(doc), "utf-8")
    macro_state._CACHE["key"] = None
    return p, days


def test_the_macro_kernel_as_of_a_past_day_reads_nothing_after_it(tmp_path: Path) -> None:
    full, days = _archive(tmp_path)
    k = 420
    asof = days[k - 1]
    w_replay, meta = macro_state.kernel_weights(days[:k], path=full, asof=asof)
    cut, _ = _archive(tmp_path, rows=k)
    w_then, meta_then = macro_state.kernel_weights(
        days[:k], path=cut, at=datetime.fromisoformat(asof).replace(tzinfo=UTC))
    assert meta["status"] == meta_then["status"] == "MEASURED"
    np.testing.assert_allclose(w_replay, w_then)
    w_now, _ = macro_state.kernel_weights(days[:k], path=full)
    assert not np.allclose(w_replay, w_now)


def test_regime_state_as_of_a_past_day_ignores_every_later_bar(tmp_path: Path,
                                                                 monkeypatch) -> None:
    """Audit should-fix on cc12a0b2: perturb every bar after the as-of day and the regime read
    as of that day must not move."""
    pa = pytest.importorskip("research.pf_allocator")
    rng = np.random.default_rng(7)
    n_days = 420
    hours = pd.date_range("2024-01-01", periods=n_days * 24, freq="h", tz="UTC")
    ret = np.concatenate([rng.normal(0.0004, 0.002, len(hours) // 2),
                          rng.normal(-0.0004, 0.006, len(hours) - len(hours) // 2)])
    close = 2000.0 * np.exp(np.cumsum(ret))
    days = sorted({str(d.date()) for d in hours})
    asof = days[359]
    daily = pd.DataFrame({"s": rng.normal(0, 1, 360)}, index=days[:360])

    def read(px_close: np.ndarray) -> tuple:
        root = tmp_path / f"b{abs(hash(px_close.tobytes())) % 10**8}"
        (root / "data" / "universe").mkdir(parents=True)
        pd.DataFrame({"time": hours, "close": px_close}).to_parquet(
            root / "data" / "universe" / "XAUUSD_H1.parquet")
        monkeypatch.setattr(pa, "BASE", root)
        labels, probs, _ = pa.regime_state(daily, asof=asof)
        return labels, probs

    base = read(close)
    later = np.array([str(t.date()) > asof for t in hours])
    shocked = close.copy()
    shocked[later] = shocked[later] * np.exp(rng.normal(0, 0.05, int(later.sum())))
    assert base[1], "the engine should fit on 360 days"
    assert read(shocked) == base
