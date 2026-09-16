"""Every non-banned family, every chart, every session (principal 2026-09-16)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_sweep as bs  # noqa: E402
from mt5desk import family_call as fc  # noqa: E402


def test_the_session_filter_keeps_only_bars_inside_the_window_and_all_keeps_everything():
    sigs = [SimpleNamespace(time=pd.Timestamp(f"2026-09-16 {h:02d}:00", tz="UTC")) for h in
            (1, 7, 8, 13, 15, 21, 23)]
    assert [g.time.hour for g in fc.session_filter(sigs, "asia")] == [1, 7]
    assert [g.time.hour for g in fc.session_filter(sigs, "london")] == [8, 13, 15]
    assert [g.time.hour for g in fc.session_filter(sigs, "ny")] == [15, 21]
    assert fc.session_filter(sigs, "all") == sigs and fc.session_filter(sigs, None) == sigs
    assert fc.session_filter(sigs, "nonsense") == sigs
    # The call path strips the session before the family sees it and filters what comes back.
    seen: dict = {}

    def fam(bars, **kw):
        seen.update(kw)
        return sigs

    out = fc.signals(fam, None, side=1, params={"session": "asia", "k": 2})
    assert seen == {"k": 2} and [g.time.hour for g in out] == [1, 7]


def test_every_default_family_is_swept_on_every_chart_and_session_except_the_banned(
        tmp_path, monkeypatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    for tf in ("M5", "M15", "H1", "D1"):
        (uni / f"EURUSD_{tf}.parquet").write_bytes(b"")
    monkeypatch.setattr(bs, "UNIVERSE", uni)
    monkeypatch.setattr(bs, "CORE", ("EURUSD",))
    cells = bs.cells()
    fams = {c["family"] for c in cells}
    assert "discovered" not in fams
    assert "vol_transition" in fams                      # a READY grid
    sweepable, blocked = bs.default_families()
    assert "trend_ma_cross" in sweepable and "trend_ma_cross" in fams
    assert "discovered" in blocked and "generic" in blocked
    tmc = [c for c in cells if c["family"] == "trend_ma_cross" and c["symbol"] == "EURUSD"]
    charts = {str(c["params"].get("timeframe") or "H1") for c in tmc}
    assert charts == {"M5", "M15", "H1", "D1"}
    sessions_m5 = {str(c["params"].get("session") or "all") for c in tmc
                   if c["params"].get("timeframe") == "M5"}
    assert sessions_m5 == {"all", "asia", "london", "ny"}
    # Daily bars carry no session.
    assert all("session" not in c["params"] for c in tmc if c["params"].get("timeframe") == "D1")
    # Most intraday first, so a capped merge reaches the charts ranked highest.
    ranks = [bs._tf_rank(str(c["params"].get("timeframe") or "H1")) for c in cells]
    assert ranks == sorted(ranks)
