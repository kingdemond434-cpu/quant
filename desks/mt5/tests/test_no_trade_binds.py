"""The no-trade verdict binds the book the allocator publishes.

Recompute every pass, execute only when the move pays: with the allocator on a five-minute
clock, a NO CHANGE verdict that still published the fresh solve would have the gateway re-size
toward every re-solve. Pinned: NO CHANGE publishes the held book with the held book's growth
numbers; the declined solve is carried as `proposed_book`; a held book outside the mandated heat
band, or one the worlds cannot score, never binds; REBALANCE publishes the solve; and `run()`
wires the binding between the verdict and the artifact so `heat.total` is the published book's.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pf_allocator as pa  # noqa: E402

from libs.portfolio.robust_elog import AllocationResult  # noqa: E402

HELD = {"mean_log_growth": 0.0004, "robust_score": 0.0003, "cvar_log_growth": -0.002,
        "annual_growth_pct": 10.5, "prob_annual_loss": 0.2}


def _solve(heat: dict[str, float]) -> AllocationResult:
    return AllocationResult(heat=dict(heat), total_heat=float(sum(heat.values())),
                            robust_score=0.0005, mean_log_growth=0.0006, cvar_log_growth=-0.001,
                            annual_growth_pct=16.0, prob_annual_loss=0.15,
                            marginal={"a": 0.1, "b": 0.05})


def _nt(verdict: str) -> dict:
    return {"verdict": verdict, "benefit_over_horizon": 0.0001, "cost": 0.0009}


def test_no_change_publishes_the_held_book_and_its_own_growth(monkeypatch) -> None:
    monkeypatch.setattr(pa, "_log", lambda msg: None)
    prev = {"a": 0.12, "b": 0.09}                       # 21%: inside the [20%, 30%] band
    solve = _solve({"a": 0.15, "b": 0.10})
    nt = _nt("NO CHANGE")
    book, funded = pa.bind_verdict(nt, prev, HELD, solve, dict(solve.heat), floor=0.20,
                                   ceiling=0.30)
    assert nt["binding"] is True
    assert funded == {"a": 0.12, "b": 0.09}
    assert book.total_heat == 0.21
    assert book.mean_log_growth == HELD["mean_log_growth"]
    assert book.annual_growth_pct == HELD["annual_growth_pct"]
    assert book.marginal == solve.marginal                # the ranking stays the fresh one
    assert "held" in book.note


def test_rebalance_publishes_the_solve(monkeypatch) -> None:
    monkeypatch.setattr(pa, "_log", lambda msg: None)
    solve = _solve({"a": 0.15, "b": 0.10})
    nt = _nt("REBALANCE")
    book, funded = pa.bind_verdict(nt, {"a": 0.12, "b": 0.09}, HELD, solve, dict(solve.heat))
    assert nt["binding"] is False
    assert book is solve
    assert funded == solve.heat


def test_a_held_book_outside_the_band_never_binds(monkeypatch) -> None:
    monkeypatch.setattr(pa, "_log", lambda msg: None)
    solve = _solve({"a": 0.15, "b": 0.10})
    for prev in ({"a": 0.05, "b": 0.03}, {"a": 0.20, "b": 0.15}):
        nt = _nt("NO CHANGE")
        book, funded = pa.bind_verdict(nt, prev, HELD, solve, dict(solve.heat), floor=0.20,
                                       ceiling=0.30)
        assert nt["binding"] is False
        assert "band" in nt["why_not_binding"]
        assert book is solve and funded == solve.heat


def test_an_unscorable_or_empty_held_book_never_binds(monkeypatch) -> None:
    monkeypatch.setattr(pa, "_log", lambda msg: None)
    solve = _solve({"a": 0.15, "b": 0.10})
    nt = _nt("NO CHANGE")
    book, _ = pa.bind_verdict(nt, {}, HELD, solve, dict(solve.heat))
    assert nt["binding"] is False and "scorable" in nt["why_not_binding"]
    nt = _nt("NO CHANGE")
    ruinous = dict(HELD, mean_log_growth=float("-inf"))
    book, _ = pa.bind_verdict(nt, {"a": 0.12, "b": 0.09}, ruinous, solve, dict(solve.heat),
                              floor=0.20, ceiling=0.30)
    assert nt["binding"] is False and book is solve


def test_run_binds_the_verdict_before_the_artifact_is_written() -> None:
    src = inspect.getsource(pa.run)
    i_nt = src.index("nt = no_trade(")
    i_bind = src.index("book, funded = bind_verdict(nt, prev_book, held, book, funded)")
    i_art = src.index('"proposed_book": proposed_book')
    assert i_nt < i_bind < i_art
    # the heat the gateway caps at is the PUBLISHED book's, not the solve's, when the verdict binds
    assert 'book.total_heat if nt.get("binding") else verdict.total_heat' in src
    assert '"held": bool(nt.get("binding"))' in src
