"""The RECORDER half -- daily sleeve return streams, and the ways it could lie.

k_eff = n/(1+(n-1)rho) ASYMPTOTES TO 1/rho. At rho=0.2 combined Sharpe caps at s*sqrt(5) however
many sleeves are added, so 40%/yr is unreachable at ANY n; at rho=0 six sleeves reach it. Those
two futures are identical in every artifact this desk publishes.

`track_sleeve_correlation` is the ANALYSER -- complete, correct, and with nothing to read. This
is the half it lacked. These tests pin the ways a RECORDER can turn an honest UNMEASURED into a
confident wrong number before the statistics ever see it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.record_sleeve_returns as T


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
