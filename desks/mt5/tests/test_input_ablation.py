"""Each allocator input is judged against the plain solve OUT OF SAMPLE (2026-10-27).

zuck 2026-10-27: "constantly maximise all so they have highest chanc of profitabilities n
beatings". An input earns money only by beating the allocator without it on outcomes it had not
seen; these tests pin the walk-forward, the as-of reads and the verdict bar.
"""
from __future__ import annotations

import json
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


def _ev(df: pd.DataFrame) -> list[SleeveEvidence]:
    return [SleeveEvidence(name=c, daily_r=df[c].to_numpy(), family="f", symbol=c, n_trials=1,
                           forward_days=0, live_days=0, cost_r=0.0) for c in df.columns]


def _fake(df: pd.DataFrame, seen: list[tuple[str, str]]):
    """`regime` sees the NEXT window's state (an input that truly knows something), `macro` sees
    its opposite (one that is truly harmful). The solve funds whichever sleeve the arm names, or
    splits evenly when given nothing."""
    state = df.attrs["state"]
    pos = {d: i for i, d in enumerate(df.index)}

    def arm_inputs(arm, asof, hist):
        seen.append((asof, str(hist.index[-1])))
        nxt = int(state[pos[asof] + 1])
        pick = nxt if arm == "regime" else 1 - nxt
        return ia.ArmInputs(regime_probs=(("pick", float(pick)),))

    def solve(ev_t, cfg):
        if not cfg.regime_probs:
            return {"A": 0.05, "B": 0.05}
        return {"A": 0.1, "B": 0.0} if cfg.regime_probs[0][1] == 0.0 else {"A": 0.0, "B": 0.1}
    return arm_inputs, solve


def test_a_knowing_input_is_promoted_a_harmful_one_demoted_and_nothing_reads_ahead() -> None:
    df = _matrix()
    seen: list[tuple[str, str]] = []
    arm_inputs, solve = _fake(df, seen)
    res = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250)
    assert res["n_windows"] >= ia.MIN_PERIODS
    assert res["verdicts"]["regime"]["verdict"] == "PROMOTE"
    assert res["verdicts"]["macro"]["verdict"] == "DEMOTE"
    # Every arm was built from history ending exactly on its own rebalance day.
    assert seen and all(asof == last for asof, last in seen)
    # Holding windows never overlap.
    starts = [df.index.get_loc(r["asof"]) for r in res["windows"]]
    assert all(b - a == ia.STEP for a, b in pairwise(starts))


def test_too_few_windows_is_unproven_whatever_the_sign() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    res = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250, max_windows=10)
    assert {v["verdict"] for v in res["verdicts"].values()} == {"UNPROVEN"}


def test_the_bar_is_the_constant() -> None:
    assert ia.T_DECIDE == 2.0 and ia.MIN_PERIODS == 26
    flat = ia.paired_verdict([0.001, -0.001] * 20)
    assert flat["verdict"] == "UNPROVEN"
    assert ia.paired_verdict([0.01 + 0.001 * (i % 3) for i in range(30)])["verdict"] == "PROMOTE"
    assert ia.paired_verdict([-0.01 - 0.001 * (i % 3) for i in range(30)])["verdict"] == "DEMOTE"


def test_realized_growth_is_log_of_the_book_return_and_ruin_is_minus_infinity() -> None:
    fwd = pd.DataFrame({"A": [0.1, -0.05], "B": [0.0, 0.2]})
    g = ia.realized_growth({"A": 0.5, "B": 0.25}, fwd)
    assert g == pytest.approx(np.log1p(0.05) + np.log1p(-0.025 + 0.05))
    assert ia.realized_growth({"A": 20.0}, fwd) == float("-inf")


def test_a_second_run_reuses_every_window_and_gives_the_same_answer() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    cache: dict = {}
    first = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250, cache=cache)
    second = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250, cache=cache)
    assert first["cache_hits"] == 0 and second["cache_hits"] == second["n_windows"]
    assert json.dumps(first["verdicts"]) == json.dumps(second["verdicts"])
    # A revised input (different data_key) re-solves everything.
    third = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250, cache=cache,
                      data_key="revised")
    assert third["cache_hits"] == 0


def test_verdict_for_fails_closed(tmp_path: Path) -> None:
    assert ia.verdict_for("regime", tmp_path / "absent.json") == "UNPROVEN"
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"verdicts": {"regime": {"verdict": "PROMOTE"},
                                          "macro": {"verdict": "WHATEVER"}}}), "utf-8")
    assert ia.verdict_for("regime", p) == "PROMOTE"
    assert ia.verdict_for("macro", p) == "UNPROVEN"
    p.write_text("{torn", "utf-8")
    assert ia.verdict_for("regime", p) == "UNPROVEN"


def _archive(tmp_path: Path, rows: int | None = None) -> tuple[Path, list[str]]:
    n = 600
    end = datetime.now(tz=UTC).replace(tzinfo=None)
    days = [(end - pd.Timedelta(days=n - 1 - i)).date().isoformat() for i in range(n)]
    dxy = np.concatenate([np.linspace(125.0, 95.0, 300), np.linspace(95.0, 125.0, 300)])
    keep = days[:rows] if rows else days
    doc = {"updated": end.isoformat(), "series": {
        "DTWEXBGS": [[d, float(v)] for d, v in zip(days, dxy, strict=True) if d in keep],
        "VIXCLS": [[d, 15.0] for d in keep], "DGS10": [[d, 4.0] for d in keep]}}
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
    # And it differs from today's reading, which knows the dollar's later turn.
    w_now, _ = macro_state.kernel_weights(days[:k], path=full)
    assert not np.allclose(w_replay, w_now)


def test_past_the_deadline_no_new_window_is_solved_and_the_rest_wait() -> None:
    df = _matrix()
    arm_inputs, solve = _fake(df, [])
    cache: dict = {}
    res = ia.ablate(df, _ev(df), arm_inputs, solve=solve, warmup=250, cache=cache, deadline=0.0)
    assert res["n_windows"] == 0 and res["pending_windows"] > 0 and not cache
    assert {v["verdict"] for v in res["verdicts"].values()} == {"UNPROVEN"}


def test_the_daily_cycle_judges_inputs_after_state_admission_and_before_the_book() -> None:
    import daily_cycle
    names = [n for n, _ in daily_cycle.STEPS]
    assert names.index("state_admission") < names.index("input_ablation") < names.index(
        "portfolio")
