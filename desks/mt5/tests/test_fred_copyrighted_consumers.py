"""THIRD-PARTY FRED SERIES ARE NEVER LIVE INPUT, at every writer and every reader (2026-10-20).

The writers (axis_ingest -> data/axes/fred.json, fetch_fred's lake, collect_fred_macro ->
data/fred_macro*.json) refuse them BEFORE any request and carry them by name as
UNMEASURED_NO_LICENSED_SOURCE with a missed_growth line. Every reader treats them as ABSENT even
when a stale, pre-ruling file still holds them: no crash, no zero, the dependent output named
UNMEASURED. No test touches the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import free_data as fd  # noqa: E402

from libs.data import terms_fence as tf  # noqa: E402

REFUSED = ("VIXCLS", "BAMLH0A0HYM2", "UMCSENT", "SP500", "NASDAQCOM", "NIKKEI225", "PCOPPUSDM",
           "GOLDAMGBD228NLBM", "GOLDPMGBD228NLBM")
NOT_HELD = ("DGS10", "DTWEXBGS", "SOFR", "RRPONTSYD", "ECBDFR", "IR3TIB01JPM156N",
            "CP0000EZ19M086NEST", "JPNCPIALLMINMEI", "DEXJPUS", "DCOILWTICO")


def _rows(n: int = 400, start: str = "2024-01-01", level: float = 20.0) -> list[list[Any]]:
    days = pd.date_range(start, periods=n, freq="D")
    vals = level + np.cumsum(np.random.default_rng(5).normal(0, 0.5, n))
    return [[d.date().isoformat(), float(v)] for d, v in zip(days, vals, strict=True)]


# ------------------------------------------------------------------ the register
def test_every_series_is_classified_from_its_own_notes() -> None:
    for sid in REFUSED:
        assert tf.fred_series_source(sid) == "fred_copyrighted", sid
        assert tf.SOURCE_POLICY["fred_copyrighted"]["terms"]["series_notes"][sid]
    for sid in NOT_HELD:
        assert tf.fred_series_source(sid) is None, sid
    not_held = tf.SOURCE_POLICY["fred_copyrighted"]["terms"]["not_held"]
    assert "free use of the information" in not_held["ECBDFR"]
    assert "not owned by a third-party" in tf.FRED_COPYRIGHTED_NOTES["PCOPPUSDM"]


@pytest.mark.parametrize("url", [
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10,SP500",
    "https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json",
    "https://alfred.stlouisfed.org/graph/fredgraph.csv?id=nikkei225&vintage_date=2026-01-01",
])
def test_a_fred_query_naming_a_third_party_series_is_never_live_input(url: str) -> None:
    assert tf.input_source(url) == "fred_copyrighted"
    assert tf.platform_of_url(url) is None, "IDEAS_ONLY, not held: ideas reads are untouched"


def test_a_public_domain_query_is_untouched() -> None:
    assert tf.input_source("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10") is None
    assert tf.input_source(
        "https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXBGS") is None


# ------------------------------------------------------------------ the writers
def test_axis_ingest_never_requests_them_and_carries_them_by_name(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import axis_ingest as ai
    asked: list[str] = []

    class _R:
        def __init__(self, body: str) -> None:
            self.body = body

        def __enter__(self) -> _R:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def read(self) -> bytes:
            return self.body.encode()

    def opener(req: Any, timeout: float) -> _R:
        asked.append(req.full_url)
        return _R("DATE,X\n2026-01-01,1.0\n2026-01-02,1.1\n")
    monkeypatch.setattr(ai, "_live_urlopen", opener)
    doc = ai.ingest_fred()
    assert not any("VIXCLS" in u or "BAMLH0A0HYM2" in u for u in asked)
    assert "VIXCLS" not in doc["series"] and "BAMLH0A0HYM2" not in doc["series"]
    assert doc["series"]["DGS10"]["n"] == 2
    cut = doc["unmeasured_no_licensed_source"]
    assert cut["VIXCLS"]["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert {x["fred_series"] for x in doc["missed_growth"]} == {"VIXCLS", "BAMLH0A0HYM2"}
    # the axis file is rewritten whole: a stale VIXCLS block cannot survive
    stale = tmp_path / "fred.json"
    stale.write_text(json.dumps({"series": {"VIXCLS": {"points": [{"d": "2020-01-01",
                                                                   "v": 15.0}]}}}), "utf-8")
    ai.publish("fred", doc, out_dir=tmp_path, report=None)
    assert "VIXCLS" not in json.loads(stale.read_text("utf-8"))["series"]


def test_fetch_fred_refuses_them_and_moves_the_stale_lake_aside(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import fetch_fred as ff
    asked: list[str] = []

    def fetch(sid: str) -> pd.DataFrame:
        asked.append(sid)
        return pd.DataFrame({sid: [1.0, 2.0]},
                            index=pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True))
    monkeypatch.setattr(ff, "fetch", fetch)
    pd.DataFrame({"VIXCLS": [15.0]}).to_parquet(tmp_path / "fred_VIXCLS.parquet")
    ff.main(out=tmp_path)
    assert not set(asked) & set(REFUSED)
    assert "DGS10" in asked
    assert not (tmp_path / "fred_VIXCLS.parquet").exists()
    assert (tmp_path / "fred_VIXCLS.parquet.ideas_only").exists()
    st = json.loads((tmp_path / "fred_fetch_state.json").read_text("utf-8"))
    assert st["series"]["VIXCLS"]["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert st["series"]["SP500"]["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert st["series"]["SP500"]["substitute"] == "mt5_own_bars:US500"
    assert all(x["delta_elogw"] == "UNMEASURED" for x in st["missed_growth"])


def test_collect_fred_macro_never_archives_vixcls(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    import collect_fred_macro as cfm
    asked: list[str] = []
    monkeypatch.setattr(cfm, "_key", lambda: "k")
    monkeypatch.setattr(cfm, "_fetch", lambda k, sid: asked.append(sid) or _rows(40))
    monkeypatch.setattr(cfm, "record", lambda *a, **k: 0)
    for name in ("_ARCHIVE", "_ARCHIVE_LONG", "_WEB"):
        monkeypatch.setattr(cfm, name, tmp_path / f"{name}.json")
    cfm.main()
    assert "VIXCLS" not in asked and "DGS10" in asked
    for name in ("_ARCHIVE", "_ARCHIVE_LONG"):
        doc = json.loads((tmp_path / f"{name}.json").read_text("utf-8"))
        assert "VIXCLS" not in doc["series"]
        assert doc["unmeasured_no_licensed_source"]["VIXCLS"]["status"] == \
            fd.UNMEASURED_NO_LICENSED_SOURCE
        assert doc["missed_growth"][0]["policy_row"] == "fred_copyrighted"


def test_the_bill_reads_the_new_carriers() -> None:
    import missed_growth as mg
    organs = [o for o, _ in mg.FRED_COPYRIGHTED_CUT_ARTIFACTS]
    assert "axis_ingest.fred" in organs and "collect_fred_macro" in organs


# ------------------------------------------------------------------ the readers, on a STALE file
def _stale_archive(tmp_path: Path) -> Path:
    p = tmp_path / "fred_macro.json"
    p.write_text(json.dumps({"series": {"VIXCLS": _rows(400, level=18.0),
                                        "DTWEXBGS": _rows(400, level=120.0),
                                        "DGS10": _rows(400, level=4.0)}}), "utf-8")
    return p


def test_macro_state_reads_no_vix_and_names_the_risk_dimension(tmp_path: Path) -> None:
    from libs.portfolio import macro_state as ms
    p = _stale_archive(tmp_path)
    series, _ = ms._load_archive(p)
    assert "VIXCLS" not in series and "DTWEXBGS" in series
    assert ms.alfred_rows("VIXCLS", tmp_path) is None
    st = ms.now(p)
    assert "risk" not in st["state"]
    assert st["unmeasured"]["risk"].startswith(ms.UNMEASURED_NO_LICENSED_SOURCE)
    w, meta = ms.kernel_weights(["2024-12-01"], p)
    assert "risk" not in meta.get("dims", []) and np.isfinite(w).all()


def test_leg_factors_never_serve_d_vix_even_from_a_cache(tmp_path: Path) -> None:
    from libs.portfolio import leg_factors as lf
    cache = tmp_path / "factor_returns.parquet"
    pd.DataFrame({"EUR": [0.01, -0.01], "d_vix": [0.1, -0.2], "d_r10": [0.0, 0.01]},
                 index=["2026-01-01", "2026-01-02"]).to_parquet(cache)
    got = lf.daily_factor_returns(universe=tmp_path / "none", cache=cache, max_age_s=1e9)
    assert "d_vix" not in got.columns and "d_r10" in got.columns
    why = lf.macro_unmeasured(got.columns, got)
    assert why["d_vix"].startswith("UNMEASURED_NO_LICENSED_SOURCE")
    assert "d_r10" not in why


def test_macro_view_publishes_no_risk_lean_rather_than_a_zero(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mt5desk import macro_view as mv
    monkeypatch.setattr(mv, "FRED", _stale_archive(tmp_path))
    v = mv.view()
    assert "VIXCLS" not in v["ranks"] and v["unmeasured"]["risk"].startswith(
        "UNMEASURED_NO_LICENSED_SOURCE")
    for c in (*mv.RISK_ON, *mv.HAVENS):
        assert c not in v["lean"], c
    assert v["lean"]["XAU"] == pytest.approx(max(-1.0, min(1.0, -0.6 * (
        2.0 * (v["ranks"]["DTWEXBGS"] - 0.5)))), abs=1e-3)
    assert mv.score("AUDJPY", v)[0] is None, "both legs absent: no score, never 0"
    s, why = mv.score("AUDUSD", v)
    assert s is not None and "AUD absent" in why


def test_shadow_institutional_reads_no_third_party_axis_point(tmp_path: Path) -> None:
    import shadow_institutional as si
    (tmp_path / "fred.json").write_text(json.dumps({"series": {
        "VIXCLS": {"points": [{"d": "2026-01-01", "v": 15.0}]},
        "DGS10": {"points": [{"d": "2026-01-01", "v": 4.0}]}}}), "utf-8")
    assert si.read_axis_points(tmp_path, "fred", "VIXCLS") == []
    assert si.read_axis_points(tmp_path, "fred", "*") == [("2026-01-01", 4.0)]


def test_dislocation_lab_p2_is_unmeasured_by_licence() -> None:
    from research import dislocation_lab as DL
    ctx = SimpleNamespace(fred={"series": {"VIXCLS": {"points": [
        {"date": "2026-01-01", "value": 15.0}]}}}, shadow={})
    assert DL._vix_points(ctx) == []
    r = DL.engine_p2(ctx, "US500", next(iter(DL.HB)), pd.DataFrame(), np.array([]))
    assert r.status != DL.MEASURED and "UNMEASURED_NO_LICENSED_SOURCE" in r.why


def test_free_shadows_never_loads_a_stale_third_party_lake(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import free_shadows as fs
    monkeypatch.setattr(fs, "LAKE", tmp_path)
    monkeypatch.setattr(fs, "REFUSED", {})
    pd.DataFrame({"VIXCLS": [15.0]}, index=pd.to_datetime(["2026-01-01"], utc=True)).to_parquet(
        tmp_path / "fred_VIXCLS.parquet")
    assert fs.load_fred("VIXCLS").empty and "VIXCLS" in fs.REFUSED


def test_orthogonal_sweep_never_conditions_on_vix(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import orthogonal_sweep as osw
    doc = {"series": {"VIXCLS": _rows(400)}}
    monkeypatch.setattr(osw, "_read", lambda p: doc)
    idx = pd.date_range("2024-06-01", periods=500, freq="h", tz="UTC")
    assert osw._macro_series(idx) is None
    assert osw._macro_series(idx, "VIXCLS") is None
    assert osw._macro_series_name() is None


def test_counterfactual_attribution_names_the_licence(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    import counterfactual_attribution as cfa
    cache = {"view": {"ranks": {"VIXCLS": 0.9}, "confidence": 1.0, "freshness": 1.0}}
    row, hist = cfa.read_source({"kind": "rank", "id": "VIXCLS"}, cache)
    assert row["status"] == "UNMEASURED" and "UNMEASURED_NO_LICENSED_SOURCE" in row["why"]
    assert "p" not in row and hist == []


def test_macro_region_reads_no_third_party_series(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    from macro_region import miners as mm
    (tmp_path / "fred.json").write_text(json.dumps({"series": {
        "VIXCLS": {"points": [{"d": "2026-01-01", "v": 15.0}]},
        "DGS10": {"points": [{"d": "2026-01-01", "v": 4.0}]}}}), "utf-8")
    monkeypatch.setattr(mm, "AXES_DIR", tmp_path)
    assert mm.default_series("fred:VIXCLS") == []
    assert mm.default_series("fred:DGS10") == [("2026-01-01", 4.0)]


def test_exposure_decomposition_never_fits_a_third_party_factor(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import exposure_decomposition as ed
    doc = {"series": {"VIXCLS": _rows(400)}}
    monkeypatch.setattr(ed, "_json", lambda p: doc)
    assert ed._fred_points(["VIXCLS"]) == (None, None)
