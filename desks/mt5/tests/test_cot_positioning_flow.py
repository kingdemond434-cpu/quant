"""CFTC positioning-change cells: point-in-time, signed right, buildable, wired, seeded once.

WHAT THIS PINS:
  * the family's DEFAULT construction is unchanged by the new columns (box cells keep their
    verdicts), and an unknown series/transform/mode refuses rather than substituting;
  * the release clock: a Tuesday report is labelled no earlier than the following Monday, the
    same label the box's cache path uses, and no signal precedes its label;
  * the sign: a long JPY future is a SHORT USDJPY position; TFF cross-rate contracts are not
    spliced into a currency's own column;
  * `follow` is the mirror of `fade` on the same extremes;
  * the cells classify into positioning_flow and the sealed gauntlet can build the family;
  * the seeder never re-donates a cell already in its seat, even with no state file;
  * the hourly leg is wired into a department, a layer and a budget.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import cot_frames  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402


def _bars(start: str = "2018-01-01", weeks: int = 300, seed: int = 3) -> pd.DataFrame:
    idx = pd.date_range(start, periods=weeks * 120, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 1.0 + np.cumsum(rng.normal(0, 0.001, len(idx)))
    return pd.DataFrame({"open": close, "high": close + 0.002, "low": close - 0.002,
                         "close": close, "volume": 1.0}, index=idx)


def _cot(weeks: int = 300, seed: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2018-01-08", periods=weeks, freq="W-MON", tz="UTC")
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"net": rng.normal(0, 1, weeks),
                         "lev_net": np.cumsum(rng.normal(0, 1000, weeks))}, index=idx)


def test_default_construction_is_unchanged_by_extra_columns():
    d, cot = _bars(), _cot()
    a = fo.family_cot_positioning(d, cot=cot)
    b = fo.family_cot_positioning(d, cot=cot[["net"]])
    assert a and [(s.time, s.side, s.stop) for s in a] == [(s.time, s.side, s.stop) for s in b]


@pytest.mark.parametrize("kw", [{"series": "absent"}, {"transform": "zscore"},
                                {"mode": "sideways"}])
def test_unknown_construction_refuses(kw):
    assert fo.family_cot_positioning(_bars(), cot=_cot(), **kw) == []


def test_follow_mirrors_fade():
    d, cot = _bars(), _cot()
    kw = {"series": "lev_net", "transform": "change", "extreme_pct": 0.8, "ttl_bars": 110}
    fade = fo.family_cot_positioning(d, cot=cot, mode="fade", **kw)
    follow = fo.family_cot_positioning(d, cot=cot, mode="follow", **kw)
    assert fade and [s.time for s in fade] == [s.time for s in follow]
    assert all(a.side == -b.side for a, b in zip(fade, follow, strict=True))


def test_release_clock_is_the_monday_after_the_report():
    tue = pd.Timestamp("2026-08-11", tz="UTC")              # a Tuesday report date
    s = cot_frames.to_release_clock(pd.Series([1.0], index=[tue]))
    label = s.index[0]
    # released Friday 2026-08-14 15:30 ET; first usable label is Monday 2026-08-17 00:00
    assert label == pd.Timestamp("2026-08-17", tz="UTC")
    assert label > pd.Timestamp("2026-08-14 20:30", tz="UTC")


def test_no_signal_precedes_its_release_label():
    d, cot = _bars(), _cot()
    sigs = fo.family_cot_positioning(d, cot=cot, series="lev_net", transform="change",
                                     extreme_pct=0.8)
    labels = cot.index
    for s in sigs:
        assert any(lab <= s.time for lab in labels)
        last = labels[labels <= s.time].max()
        assert s.time - last < pd.Timedelta(days=7)


def _write(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_sign_inversion_and_tff_market_filter(tmp_path, monkeypatch):
    dates = pd.to_datetime(["2026-07-28", "2026-08-04"], utc=True)
    _write(tmp_path / "cot" / "jpy.parquet", pd.DataFrame({
        "report_date": dates, "noncomm_positions_long_all": [100, 300],
        "noncomm_positions_short_all": [50, 50], "comm_positions_long_all": [0, 0],
        "comm_positions_short_all": [10, 10]}))
    _write(tmp_path / "cot_tff" / "eur.parquet", pd.DataFrame({
        "report_date": list(dates) * 2,
        "market": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"] * 2
        + ["EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE"] * 2,
        "lm_l": [10, 20, 999, 999], "lm_s": [0, 0, 0, 0], "am_l": [0] * 4, "am_s": [0] * 4,
        "dealer_l": [0] * 4, "dealer_s": [0] * 4}))
    monkeypatch.setattr(cot_frames, "LEGACY", tmp_path / "cot")
    monkeypatch.setattr(cot_frames, "TFF", tmp_path / "cot_tff")
    jpy = cot_frames.raw_columns("USDJPY")
    assert list(jpy["noncomm_net"]) == [-50.0, -250.0]          # long yen = short USDJPY
    assert list(jpy["comm_net"]) == [10.0, 10.0]
    eur = cot_frames.raw_columns("EURUSD")
    assert list(eur["lev_net"]) == [10.0, 20.0]                 # the XRATE rows are excluded
    assert cot_frames.raw_columns("NOTASYMBOL") == {}


def test_enrich_keeps_the_cache_rows_exactly(monkeypatch):
    base = pd.DataFrame({"net": [0.1, 0.2]},
                        index=pd.to_datetime(["2026-08-10", "2026-08-17"], utc=True))
    extra = pd.DataFrame({"net": [9.0, 9.0, 9.0], "lev_net": [1.0, 2.0, 3.0]},
                         index=pd.to_datetime(["2026-08-03", "2026-08-10", "2026-08-17"],
                                              utc=True))
    monkeypatch.setattr(cot_frames, "frame", lambda _s: extra)
    out = cot_frames.enrich(base, "XAUUSD")
    assert list(out.index) == list(base.index)
    assert list(out["net"]) == [0.1, 0.2]
    assert list(out["lev_net"]) == [2.0, 3.0]


def test_cluster_and_sealed_buildability():
    from research.gauntlet_buildability import BUILDABLE, family_verdict

    from libs.research.alpha_clusters import classify_family
    assert classify_family("cot_positioning") == "positioning_flow"
    assert family_verdict("cot_positioning")[0] == BUILDABLE


def test_grid_covers_fx_and_metals_from_git():
    from research import cot_positioning_flow as cpf
    cells = cpf.grid()
    syms = {s for s, _p in cells}
    assert {"XAUUSD", "XAGUSD", "EURUSD", "USDJPY"} <= syms
    assert all(p["transform"] == "change" and p["mode"] in ("fade", "follow")
               for _s, p in cells)
    assert {p["series"] for _s, p in cells} <= set(cot_frames.COLUMNS)


def test_seat_is_the_record_of_donation(tmp_path, monkeypatch):
    from research import cot_positioning_flow as cpf
    monkeypatch.setattr(cpf, "SEAT", tmp_path / "seat")
    monkeypatch.setattr(cpf, "STATE", tmp_path / "state.json")
    params = {**cpf.PARAMS, "series": "mm_net", "mode": "fade"}
    (tmp_path / "seat").mkdir()
    (tmp_path / "seat" / "discoveries_20261006_0000.json").write_text(json.dumps({
        "generated_at": "2026-10-06T00:00:00+00:00",
        "discoveries": [{"symbol": "XAUUSD", "family": "cot_positioning", "params": params}]}))
    state = cpf._load_state()
    assert state["cells"][cpf.identity("XAUUSD", params)]["donated_at"].startswith("2026-10-06")


def test_verdicts_unmeasured_without_a_ledger(tmp_path, monkeypatch):
    from research import cot_positioning_flow as cpf
    monkeypatch.setattr(cpf, "VERDICTS", tmp_path / "absent.jsonl")
    assert cpf.verdicts()["status"] == "UNMEASURED"
    # The pre-2026-10-07 reader matched this literal inside `cell`; no real cell name holds it,
    # so a row shaped like it must NOT read as a verdict on a donated cell.
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"family": "cot_positioning", "passed": False,
                                  "terminal_gate": "deflated_sharpe",
                                  "cell": 'XAUUSD.cot_positioning.{"transform": "change"}'})
                      + "\n")
    monkeypatch.setattr(cpf, "VERDICTS", ledger)
    assert cpf.verdicts()["status"] == "UNMEASURED"


def test_hourly_leg_is_wired():
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("cot_positioning_flow"' in text
    assert '"research/cot_positioning_flow.py"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["cot_positioning_flow"] == "prediction"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.department_of("cot_positioning_flow") == "discovery"
    assert hc.LEG_BUDGET_SEC["cot_positioning_flow"] >= 300 + 150
