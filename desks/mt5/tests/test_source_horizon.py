"""DATA-46: each source declares the window its state can move a price over, its decay and its
release session; the compiler demotes (never drops) charts outside the window and labels every
session cell of a released state as an own-session or transfer test."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.mining import source_horizon as sh  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402


def _cand(source: str) -> dict:
    return {"symbol": "EURUSD", "family": "trend_ma_cross", "params": {"fast": 10},
            "source": f"miner:{source}", "mechanism_status": "NAMED"}


def test_every_declared_seat_is_a_real_window() -> None:
    doc = json.loads(sh.TABLE.read_text("utf-8"))
    for seat, d in doc["seats"].items():
        if d.get("kind") == "strategy":
            continue
        assert 0 < d["min_h"] < d["max_h"], seat
        assert 0 < d["decay_half_life_h"] <= d["max_h"], seat
        assert d.get("release_session") in (None, *sh.SESSION_ORDER), seat


def test_chart_fit_reads_the_window_and_undeclared_is_never_inside() -> None:
    weekly = {"min_h": 24, "max_h": 720}
    assert sh.chart_fit("M5", weekly) == "OUTSIDE"        # 24h spans 288 M5 bars
    assert sh.chart_fit("M30", weekly) == "INSIDE"
    assert sh.chart_fit("D1", weekly) == "INSIDE"
    fast = {"min_h": 0.05, "max_h": 8}
    assert sh.chart_fit("D1", fast) == "OUTSIDE" and sh.chart_fit("H4", fast) == "INSIDE"
    assert sh.chart_fit("H1", None) == "UNDECLARED"
    assert sh.declared("mql5_signals") is None             # a strategy carries its own horizon
    assert sh.declared("no_such_seat") is None


def test_a_row_overrides_its_seat() -> None:
    d = sh.declared("cot", {"max_h": 48, "release_session": "asia"})
    assert d is not None and d["max_h"] == 48 and d["release_session"] == "asia"
    assert d["min_h"] == 24                                 # untouched keys stay the seat's


def test_transfer_paths_follow_the_release_through_the_day() -> None:
    decl = {"release_session": "asia"}
    assert sh.session_transfer(decl, "asia") == {"from": "asia", "to": "asia",
                                                 "lag_sessions": 0, "kind": "own"}
    assert sh.session_transfer(decl, "ny")["lag_sessions"] == 2
    assert sh.session_transfer({"release_session": "ny"}, "asia")["lag_sessions"] == 1
    assert sh.session_transfer(decl, "all") is None and sh.session_transfer({}, "asia") is None


def test_the_compiler_demotes_outside_cells_and_keeps_every_one(tmp_path, monkeypatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    for tf in ("M5", "M30", "H1"):
        (uni / f"EURUSD_{tf}.parquet").write_bytes(b"")
    monkeypatch.setattr(mcc, "UNIVERSE", uni)
    plain = mcc.expand_axes([_cand("reddit")])
    cot = mcc.expand_axes([_cand("cot")])
    assert len(cot) == len(plain)                           # nothing removed
    m5 = [v for v in cot if v["axis"]["chart"] == "M5"]
    m30 = [v for v in cot if v["axis"]["chart"] == "M30"]
    assert all(v["source_horizon"]["fit"] == "OUTSIDE" and v["priority"] == 2 for v in m5)
    assert all(v["source_horizon"]["fit"] == "INSIDE" and v["priority"] == 0 for v in m30)
    paths = {v["axis"]["session"]: v.get("session_transfer") for v in cot if
             v["axis"]["chart"] == "H1"}
    assert paths["ny"]["kind"] == "own" and paths["asia"]["kind"] == "transfer"
    assert paths["all"] is None
    assert all(v["source_horizon"]["fit"] == "UNDECLARED" for v in plain)
    t = sh.tally(cot)
    assert t["fit"] == {"OUTSIDE": 4, "INSIDE": 8}
    assert t["session_transfer_paths"] == {"ny->asia": 3, "ny->london": 3, "ny->ny": 3}
