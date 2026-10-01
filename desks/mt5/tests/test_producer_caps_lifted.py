"""The four producers sealed pass 2 unblocked carry no artificial breadth cap (2026-10-01).

cross_asset_graph swept `book_symbols()[:12]`, asia_transmission was on no clock, and the two
event_reaction organs donated 10 and 15 of their clearing cells. Each pin below fails if the
cap comes back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cross_asset_graph as cag  # noqa: E402
import event_response_atlas as era  # noqa: E402
import event_surprise as es  # noqa: E402

from research import producer_breadth as pb  # noqa: E402


def test_the_statistical_pair_space_is_every_ordered_pair_once() -> None:
    syms = [f"S{i:02d}" for i in range(30)]
    pairs = cag._pairs(syms, {}, set(syms))
    stat = [(a, b) for a, b, role in pairs if role is None]
    assert len(stat) == len(set(stat)) == 30 * 29


def test_the_universe_is_not_a_twelve_name_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    import universe_policy as up
    monkeypatch.setattr(up, "may_hypothesise", lambda s, f=None: not s.startswith("EQ"))
    have = {f"FX{i:02d}" for i in range(20)} | {"XAUUSD", "EQ1"}
    out = cag._universe(["XAUUSD", "FX05"], have)
    assert out[:2] == ["XAUUSD", "FX05"]                        # the book first
    assert len(out) == 21 and "EQ1" not in out                  # never a single name


def _bars(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1.0 + np.cumsum(rng.normal(0, 1e-3, n))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)


def test_the_cursor_walks_the_whole_space_and_the_graph_keeps_every_edge(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    syms = [f"S{i}" for i in range(5)]                          # 20 statistical pairs
    monkeypatch.setattr(cag, "GRAPH", tmp_path / "g.json")
    monkeypatch.setattr(cag, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(cag, "CURSOR", tmp_path / "c.json")
    monkeypatch.setattr(cag, "_book_symbols", lambda: syms)
    monkeypatch.setattr(cag, "_universe", lambda book, have: list(book))
    monkeypatch.setattr(cag, "_event_times", lambda: [])
    monkeypatch.setattr(cag.pc, "universe_meta", lambda: {})
    monkeypatch.setattr(cag.pc, "UNI", tmp_path)
    for s in syms:
        (tmp_path / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(cag.pc, "bars", lambda s: _bars(50, hash(s) % 97))
    calls = {"n": 0}

    def edge(d, t, plausible_role=None):
        calls["n"] += 1
        return {"verdict": "NO_EDGE", "t": 0.1}
    monkeypatch.setattr(cag.lead_lag, "edge", edge)
    clock = iter(range(0, 10_000))
    # each edge costs one "second"; a 14 s budget at GRAPH_SHARE 0.5 measures ~7 per pass
    monkeypatch.setattr(cag.time, "monotonic", lambda: float(next(clock)))
    for _ in range(4):
        cag.run(budget_s=14.0)
    doc = json.loads((tmp_path / "g.json").read_text("utf-8"))
    assert doc["coverage"]["pairs_in_space"] == 20
    assert doc["n_pairs"] == 20                                  # every pair held after wrap
    assert json.loads((tmp_path / "c.json").read_text("utf-8"))["n_stat"] == 20


def test_asia_transmission_is_on_the_hourly_clock() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    clocks = pb.clocks_for("asia_transmission", "asia_transmission",
                           {"hourly_cycle": src}, [])
    assert clocks == ["hourly_cycle:asia_transmission"]
    assert '"research/asia_transmission.py", "--propose"' in src


def test_the_event_reaction_organs_donate_every_clearing_cell() -> None:
    assert es.MAX_DONATIONS == es.MAX_PUBLISHED
    assert era.MAX_DONATIONS == era.MAX_PUBLISHED
    import inspect
    assert inspect.signature(era.run).parameters["max_donations"].default == era.MAX_PUBLISHED
    assert inspect.signature(es.build).parameters["max_donations"].default == es.MAX_PUBLISHED


def test_the_inventory_says_the_caps_are_lifted() -> None:
    for name in ("cross_asset_graph", "event_surprise", "event_response_atlas"):
        assert pb.INVENTORY[name]["status"] == "WIDENED"
    assert pb.INVENTORY["asia_transmission"]["status"] == "WIRED"
