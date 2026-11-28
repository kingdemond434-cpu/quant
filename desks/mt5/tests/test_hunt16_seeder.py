"""The hunt16 seeder mints hunt16_cell over the book's gaps through the specialist path."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import hunt16_seeder as hs  # noqa: E402
from research import specialist_cell as sc  # noqa: E402


def test_the_grid_names_every_base_family_and_keeps_params_executable() -> None:
    cells = hs.plan([("gold", "XAUUSD")])
    bases = {c["params"]["base_family"] for c in cells}
    assert bases == set(hs.base_families()) and len(bases) >= 7
    assert len(cells) == len(bases) * 2 * len(hs.SIGNAL_HOURS) * len(hs.DAY_STATES)
    assert all(c["family"] == "hunt16_cell" and c["params"]["direction"] in ("LONG", "SHORT")
               for c in cells)
    assert {"dav_bb_meanrev", "dav_t3_trend", "dav_hull_trend"} <= bases


def test_symbols_are_the_books_gaps_and_never_exotic() -> None:
    syms = hs.gap_symbols()
    buckets = [b for b, _ in syms]
    assert buckets == sorted(buckets, key=["gold", "index", "usd_jpy_eur_cross"].index)
    for b, s in syms:
        if b == "usd_jpy_eur_cross":
            legs = {s[:3], s[3:]}
            assert legs & hs.CROSS_LEGS and not legs & hs.CROWDED_LEGS


def test_floor_donation_and_weekly_remeasure(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hs, "STATE", tmp_path / "state.json")
    calls: list[dict[str, Any]] = []

    def fake_measure(sym: str, fam: str, params: dict, meta: dict) -> dict:
        calls.append(params)
        lb = 80 if params.get("day_state") is None else 10
        return {"built": True, "signal_days": lb, "trade_days_lb": lb}

    donated: list[list[dict]] = []
    monkeypatch.setattr(sc, "measure", fake_measure)
    monkeypatch.setattr(sc, "_meta", lambda: {})
    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda src, rows, n: donated.append(rows) or tmp_path)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    rep = hs.seed(budget_s=60, symbols=[("gold", "XAUUSD")])
    n_any_state = len(hs.base_families()) * 2 * len(hs.SIGNAL_HOURS)
    assert rep["candidates_this_pass"] == n_any_state          # only the 80-day cells clear 66
    assert donated and all(r["source"] == "hunt16_seeder" for r in donated[0])
    first = len(calls)
    rep2 = hs.seed(budget_s=60, symbols=[("gold", "XAUUSD")])
    assert len(calls) == first and rep2["candidates_this_pass"] == 0   # measured this week, donated


def test_the_hourly_cycle_runs_it() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/hunt16_seeder.py", "--once"' in src and '"hunt16_seeder": h16s' in src


def test_a_raising_build_cell_publishes_no_message_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import external_gauntlet as eg

    def boom(*_a: Any, **_k: Any) -> None:
        raise ValueError("C:\\secret\\path leaked 42")
    monkeypatch.setattr(eg, "build_cell", boom)
    got = sc.measure("XAUUSD", "hunt16_cell", {"base_family": "dav_t3_trend"}, {})
    assert got == {"built": False, "why": "build_cell raised ValueError"}
    src = (DESK / "research" / "specialist_cell.py").read_text("utf-8")
    assert "{type(exc).__name__}: {exc}" not in src
