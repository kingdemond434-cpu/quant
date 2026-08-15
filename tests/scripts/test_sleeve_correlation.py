"""Rho, measured -- the number every return projection on this desk has been assuming.

k_eff = n/(1+(n-1)rho) ASYMPTOTES TO 1/rho. At rho=0 six sleeves at s=0.48 reach S=1.18 and
40%/yr; at rho=0.2 combined Sharpe caps at s*sqrt(5)=1.07 however many sleeves are added, so 40%
is unreachable at ANY n. Those two futures are identical in every artifact the desk publishes
except this one, and `libs/research/breadth` refuses to assume the difference away.

That refusal is only useful if something is trying to END it. These tests pin the four ways this
tracker could quietly turn an honest UNMEASURED into a confident wrong number.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.track_sleeve_correlation as T


def _history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             rows: list[dict]) -> Path:
    p = tmp_path / "returns.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    monkeypatch.setattr(T, "_STATE", p)
    return p


def _day(i: int) -> str:
    return (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)).strftime("%Y-%m-%d")


def _walk(n: int, a_path: list[float], b_path: list[float]) -> list[dict]:
    """Two sleeves, one symbol each, marked forward on a shared daily grid."""
    return [{"day": _day(i), "at": _day(i),
             "weights": {"A": {"AAA": 1.0}, "B": {"BBB": 1.0}},
             "marks": {"A": {"AAA": a_path[i]}, "B": {"BBB": b_path[i]}}}
            for i in range(n)]


def test_A_SHORT_OVERLAP_IS_UNMEASURED_NOT_A_POINT_ESTIMATE(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE FAILURE THAT WOULD MAKE THIS TRACKER WORSE THAN NOTHING. A correlation from nine
    overlapping days has a standard error near 0.33 -- compatible with anything from -0.3 to +0.9.
    Printing the point estimate replaces an honest UNMEASURED with a confident wrong number, and
    the whole breadth module then sizes against it."""
    n = 6
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch,
             _walk(n, [100 + i for i in range(n)], [100 + 2 * i for i in range(n)]))
    rep = T.report(min_overlap=20)
    assert rep["rho_state"] == "UNMEASURED"
    assert rep["mean_rho"] is None
    pair = rep["pairs"][0]
    assert pair["rho"] is None and "confident wrong number" in pair["why"]


def test_A_PERFECT_CO_MOVER_MEASURES_AS_ONE(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sleeves holding the same directional exposure ARE one bet, and the number must say so
    rather than crediting the book with two."""
    n = 40
    path = [100.0 * (1.0 + 0.01 * ((i % 7) - 3)) for i in range(n)]
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch, _walk(n, path, path))
    rep = T.report(min_overlap=20)
    assert rep["rho_state"] == "MEASURED"
    assert rep["mean_rho"] == pytest.approx(1.0, abs=1e-6)
    assert rep["effective_breadth"] == pytest.approx(1.0, abs=0.01), \
        "two identical sleeves are ONE effective bet"


def test_AN_OPPOSING_SLEEVE_MEASURES_NEGATIVE(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    """A hedge is worth more than an uncorrelated sleeve and the sign must survive -- an
    absolute-value or clipped correlation would report the desk's best diversifier as its worst."""
    n = 40
    up = [100.0 * (1.0 + 0.01 * ((i % 7) - 3)) for i in range(n)]
    down = [100.0 * (1.0 - 0.01 * ((i % 7) - 3)) for i in range(n)]
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch, _walk(n, up, down))
    rep = T.report(min_overlap=20)
    assert rep["mean_rho"] is not None and rep["mean_rho"] < -0.9


def test_THE_STANDARD_ERROR_TRAVELS_WITH_THE_VALUE(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """At the n this desk will have for months, the SE is WIDE -- and that is the finding, not a
    footnote to it. A rho published bare invites sizing against a number that has not settled."""
    n = 40
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch,
             _walk(n, [100 + (i % 5) for i in range(n)], [100 + (i % 3) for i in range(n)]))
    pair = T.report(min_overlap=20)["pairs"][0]
    assert pair["se"] == pytest.approx(1.0 / (pair["n_overlap"] - 3) ** 0.5, abs=1e-4)
    assert pair["se"] > 0.15, "at this sample the estimate is not settled and must not look it"


def test_YESTERDAYS_WEIGHTS_AGAINST_TODAYS_PRICES(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """THE LOOKAHEAD THAT WOULD FLATTER EVERY SLEEVE IDENTICALLY. A day's return belongs to the
    position that was HELD into the move; marking today's weights against today's prices credits
    a sleeve with a position it had not yet taken."""
    rows = _walk(3, [100.0, 110.0, 121.0], [100.0, 100.0, 100.0])
    # sleeve A flips SHORT on the final day -- if the return used TODAY's weight, day 3 would
    # score negative; held from yesterday it is the +10% the long actually earned
    rows[2]["weights"]["A"] = {"AAA": -1.0}
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch, rows)
    series = T._daily_returns()
    assert series["A"][_day(2)] == pytest.approx(0.10, abs=1e-9)


def test_NON_OVERLAPPING_SLEEVES_ARE_NOT_ASSUMED_INDEPENDENT(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sleeves that ran in different months have no correlation to measure. Filling the gap
    with zeros would MANUFACTURE independence -- the exact flattering error the breadth module
    exists to prevent, committed by the tool built to end it."""
    rows = [{"day": _day(i), "at": _day(i), "weights": {"A": {"AAA": 1.0}},
             "marks": {"A": {"AAA": 100.0 + i}}} for i in range(30)]
    rows += [{"day": _day(60 + i), "at": _day(60 + i), "weights": {"B": {"BBB": 1.0}},
              "marks": {"B": {"BBB": 100.0 + i}}} for i in range(30)]
    monkeypatch.setattr(T, "_prices", lambda: {})
    _history(tmp_path, monkeypatch, rows)
    rep = T.report(min_overlap=20)
    assert rep["pairs"][0]["n_overlap"] == 0
    assert rep["pairs"][0]["rho"] is None
    assert rep["rho_state"] == "UNMEASURED"


def test_AN_UNREADABLE_DAY_IS_NOT_RECORDED_AS_A_FLAT_ONE(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A row of zeros enters every correlation as a real day on which nothing moved together --
    which drags rho toward zero and manufactures the diversification being measured."""
    monkeypatch.setattr(T, "_STATE", tmp_path / "returns.jsonl")
    monkeypatch.setattr(T, "_prices", lambda: {})
    out = T.append_today()
    assert out["written"] is False and "UNMEASURED" in out["why"]
    assert not (tmp_path / "returns.jsonl").exists(), "nothing may be written"


def test_ONE_ROW_PER_DAY_HOWEVER_OFTEN_IT_RUNS(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """Two rows for one day double-count it in every correlation and inflate n without adding
    information -- an SE that narrows because the script ran twice."""
    p = tmp_path / "returns.jsonl"
    monkeypatch.setattr(T, "_STATE", p)
    monkeypatch.setattr(T, "_prices", lambda: {"AAAUSDC": 100.0})
    monkeypatch.setattr(T, "_weights_today", lambda: {"A": {"AAA": 1.0}})
    T.append_today()
    T.append_today()
    T.append_today()
    assert len([ln for ln in p.read_text("utf-8").splitlines() if ln.strip()]) == 1
