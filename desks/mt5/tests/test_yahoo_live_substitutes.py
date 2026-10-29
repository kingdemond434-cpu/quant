"""THE YAHOO CUT (coordinator + auditor ruling 2026-10-14), tested as behaviour.

Yahoo is an IDEAS_ONLY row of `libs/data/terms_fence.SOURCE_POLICY`, so it is never live input.
Every organ that read it now (a) asks THE ONE FETCH DOOR with live_input=True and is refused
before any request, (b) reads a licensed substitute from a register row whose own terms were
read and quoted, or (c) reports UNMEASURED_NO_LICENSED_SOURCE -- never filled, never
forward-filled, never zero -- with a missed_growth line. No test here touches the network.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import fetch_futures_curves as ffc  # noqa: E402
import free_data as fd  # noqa: E402
import macro_desk  # noqa: E402
import missed_growth as mg  # noqa: E402
import ops_redundancy as ops  # noqa: E402
from recorders import vol_archive as va  # noqa: E402
from tests.data.xls_builder import build_xls, cell_number, cell_sst  # noqa: E402

from libs.data import terms_fence as tf  # noqa: E402

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"


@pytest.fixture
def no_socket(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Any opener the fetch door builds is recorded and fails: a refusal must come first."""
    built: list[Any] = []

    def _opener(*a: Any, **k: Any) -> Any:
        built.append(a)
        raise AssertionError("an opener was built: the refusal did not come first")
    monkeypatch.setattr(tf, "guarded_opener", _opener)
    return built


def _h1(u: Path, symbol: str, start: str = "2026-06-01", days: int = 30,
        level: float = 100.0) -> None:
    u.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    close = level * np.exp(np.cumsum(np.random.default_rng(7).normal(0, 0.001, len(idx))))
    pd.DataFrame({"high": close * 1.001, "low": close * 0.999, "close": close},
                 index=idx).to_parquet(u / f"{symbol}_H1.parquet")


def _fred(series: dict[str, dict[str, float]]) -> Any:
    asked: list[str] = []

    def get(sid: str) -> dict[str, float] | None:
        asked.append(sid)
        return series.get(sid)
    get.asked = asked  # type: ignore[attr-defined]
    return get


# ------------------------------------------------------------------ the register
@pytest.mark.parametrize("key,clause", [
    ("fred_public_domain", "may be used for internal commercial uses"),
    ("eia_open_data", "You may use and/or distribute any of our data"),
    ("mt5_own_bars", "MT5/Fusion bars"),
])
def test_every_substitute_row_quotes_its_own_terms(key: str, clause: str) -> None:
    row = tf.SOURCE_POLICY[key]
    assert tf.terms_state(key) == "READ"
    assert any(clause in c for c in row["terms"]["clauses"].values())
    assert row["status"] not in (tf.IDEAS_ONLY, *tf.HOLDING)


def test_yahoo_is_refused_as_live_input_and_the_substitutes_are_not() -> None:
    assert tf.input_source(YAHOO) == "yahoo"
    assert tf.input_source("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10") is None
    assert tf.input_source("https://www.eia.gov/dnav/pet/hist_xls/RCLC1d.xls") is None
    assert tf.policy_of_url("https://fred.stlouisfed.org/graph/fredgraph.csv")["source"] == \
        "fred_public_domain"
    assert tf.policy_of_url("https://www.eia.gov/dnav/pet/hist_xls/RCLC1d.xls")["source"] == \
        "eia_open_data"


def test_the_copyrighted_fred_vix_is_named_as_not_a_substitute() -> None:
    labels = tf.SOURCE_POLICY["fred_public_domain"]["terms"]["series_labels"]
    assert "NOT a licensed substitute" in labels["VIXCLS"]
    assert all(v.get("series") != "VIXCLS" for v in fd.YAHOO_SUBSTITUTES.values())


# ------------------------------------------------------------------ free_data
def test_yahoo_daily_is_refused_before_any_request_and_ignores_its_cache(
        no_socket: list[Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fd, "CACHE", tmp_path)
    (tmp_path / "yahoo_^VIX.json").write_text(json.dumps({"2026-01-01": 15.0}), "utf-8")
    assert fd.yahoo_daily("^VIX") is None
    assert not no_socket


def test_an_mt5_substitute_is_read_from_the_desks_own_bars(tmp_path: Path) -> None:
    _h1(tmp_path, "USDX", level=98.0)
    got, prov = fd.licensed_daily("DX-Y.NYB", "t", universe_dir=tmp_path)
    assert got and len(got) == 30
    assert prov["status"] == "SUBSTITUTED" and prov["substitute"] == "mt5_own_bars:USDX"
    assert prov["pit_lag_h"] == 27.0, "a daily close is read under the anchors' 27h lag"
    assert prov["missed_growth"]["series_status"] == "SUBSTITUTED"


def test_a_fred_substitute_never_uses_the_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_fred(sid: str, start: str = "2010-01-01", vintage: Any = None, *,
                  alternate: bool = True) -> dict[str, float]:
        calls.append((sid, alternate))
        return {f"2026-01-{d:02d}": 4.1 for d in range(1, 10)}
    monkeypatch.setattr(fd, "fred_series", fake_fred)
    got, prov = fd.licensed_daily("^TNX", "t")
    assert got and calls == [("DGS10", False)]
    assert prov["substitute"] == "fred_public_domain:DGS10" and prov["pit_lag_h"] == 27.0
    _, fx = fd.licensed_daily("EURUSD=X", "t")
    assert fx["pit_lag_h"] == 192.0 and "weekly" in fx["pit_basis"], "H.10 is weekly"


def test_vix_is_unmeasured_no_licensed_source_with_a_missed_growth_line() -> None:
    got, prov = fd.licensed_daily("^VIX", "macro_desk.anchors")
    assert got is None
    assert prov["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    line = prov["missed_growth"]
    assert line["delta_elogw"] == "UNMEASURED" and line["kind"] == "ideas_only_refusal"
    assert line["policy_row"] == "yahoo" and line["source"] == "macro_desk.anchors:VIX"
    assert "Cboe" in line["why_unsubstituted"]


def test_an_unreachable_substitute_is_unmeasured_never_filled(tmp_path: Path) -> None:
    got, prov = fd.licensed_daily("GC=F", "t", universe_dir=tmp_path)   # no bars on this host
    assert got is None and prov["status"] == "UNMEASURED_NO_BARS_ON_HOST"
    assert prov["missed_growth"]["delta_elogw"] == "UNMEASURED"


# ------------------------------------------------------------------ macro_desk anchors
def test_the_anchors_use_substitutes_drop_yahoo_history_and_leave_vix_absent(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    u = tmp_path / "universe"
    for sym in ("USDX", "US500", "XAUUSD", "XTIUSD"):
        _h1(u, sym)
    monkeypatch.setattr(fd, "UNIVERSE_DIR", u)
    monkeypatch.setattr(macro_desk, "ANCHORS_F", tmp_path / "anchors.pkl")
    monkeypatch.setattr(macro_desk, "ANCHORS_PROV_F", tmp_path / "anchors.provenance.json")
    monkeypatch.setattr(macro_desk, "log", lambda m: None)
    fred = {f"2026-06-{d:02d}": 4.0 for d in range(1, 29)}
    monkeypatch.setattr(fd, "fred_series", lambda sid, *a, **k: dict(fred))
    # a Yahoo-era pickle: DXY and VIX history from before the cut
    old = pd.DataFrame({"DXY": [101.0, 102.0], "VIX": [15.0, 16.0], "DGS10": [3.9, 3.95]},
                       index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    old.to_pickle(tmp_path / "anchors.pkl")

    macro_desk.anchors()

    df = pd.read_pickle(tmp_path / "anchors.pkl")  # noqa: S301 -- this test wrote it
    assert "VIX" not in df.columns, "no licensed source: absent, never filled"
    assert df["DXY"].first_valid_index() >= pd.Timestamp("2026-06-01"), \
        "Yahoo's DXY history must not survive behind the substitute"
    assert df["DGS10"].loc["2020-01-02"] == 3.9, "a non-Yahoo column keeps its history"
    for c in ("DXY", "SPX", "GC", "CL", "TNX"):
        assert df[c].notna().any(), c
    prov = json.loads((tmp_path / "anchors.provenance.json").read_text("utf-8"))
    assert prov["columns"]["DXY"]["substitute"] == "mt5_own_bars:USDX"
    assert prov["columns"]["TNX"]["substitute"] == "fred_public_domain:DGS10"
    assert prov["unmeasured_no_licensed_source"] == ["VIX"]
    yahoo_lines = [x for x in prov["missed_growth"] if x.get("policy_row") == "yahoo"]
    assert len(yahoo_lines) == len(macro_desk.YAHOO_ANCHORS)
    assert prov["prior_columns"]["DXY"]["status"] == "SUBSTITUTED"

    # a second pass whose substitute is unreachable keeps the SUBSTITUTE's history (sticky)
    monkeypatch.setattr(fd, "UNIVERSE_DIR", tmp_path / "empty")
    macro_desk.anchors()
    df2 = pd.read_pickle(tmp_path / "anchors.pkl")  # noqa: S301 -- this test wrote it
    assert df2["DXY"].notna().sum() == df["DXY"].notna().sum()


# ------------------------------------------------------------------ ops_redundancy
def test_the_crosscheck_reads_the_fed_h10_never_yahoo(monkeypatch: pytest.MonkeyPatch,
                                                      no_socket: list[Any]) -> None:
    asked: list[tuple[str, bool]] = []

    def fake_fred(sid: str, start: str = "2010-01-01", vintage: Any = None, *,
                  alternate: bool = True) -> dict[str, float]:
        asked.append((sid, alternate))
        return {"2026-10-01": 1.10, "2026-10-02": 1.11}
    monkeypatch.setattr(fd, "fred_series", fake_fred)
    closes, src = ops._independent_closes("EURUSD")
    assert closes == {"2026-10-01": 1.10, "2026-10-02": 1.11}
    assert src == "fred_public_domain:DEXUSEU" and asked == [("DEXUSEU", False)]
    assert not no_socket


# ------------------------------------------------------------------ vol_archive
def test_the_vol_archive_records_no_licensed_iv_and_still_measures_realised(
        tmp_path: Path, no_socket: list[Any]) -> None:
    u = tmp_path / "universe"
    _h1(u, "XAUUSD", days=40)
    src = va.LicensedVolSource()
    obs = va.observe(src, {"XAUUSD": {}}, u)
    assert not no_socket and "^GVZ" in src.refusals
    assert {o.status for o in obs} == {va.UNMEASURED_NO_LICENSED_SOURCE}
    assert all(o.implied_vol is None and o.variance_risk_premium is None for o in obs), \
        "never filled"
    gold = next(o for o in obs if o.vol_ticker == "^GVZ")
    assert gold.mt5_symbol == "XAUUSD" and gold.realised_vol_cc is not None
    assert all(o.missed_growth["delta_elogw"] == "UNMEASURED" for o in obs)
    rep = va.report([], obs)
    assert set(rep["unmeasured_no_licensed_source"]) == {g.vol_ticker for g in va.GROUND}
    assert rep["realised_measured_on_mt5"] == ["XAUUSD"]
    assert len(rep["missed_growth"]) == len(va.GROUND) and rep["backtestable"] is False


# ------------------------------------------------------------------ futures curves
def _eia_xls(start_serial: int, n: int, level: float) -> bytes:
    records = cell_sst(0, 0, 0) + cell_sst(0, 1, 1)
    for row in range(1, n + 1):
        records += cell_number(row, 0, float(start_serial + row))
        records += cell_number(row, 1, level + row / 100.0)
    return build_xls([("Data 1", records), ("Contents", cell_sst(0, 0, 2))],
                     ["Date", "Cushing, OK Crude Oil Future Contract", "notes"])


def test_the_yahoo_contract_fetch_is_refused_at_its_first_url(no_socket: list[Any]) -> None:
    with pytest.raises(tf.TermsFenced) as ei:
        ffc.fetch_contract("GCZ26.CMX")
    assert ei.value.platform == "yahoo" and not no_socket


def test_eia_workbooks_parse_to_real_dates() -> None:
    got = ffc.parse_eia_daily(_eia_xls(46000, 10, 70.0))
    assert len(got) == 10 and min(got) == date(2025, 12, 10)
    assert got[date(2025, 12, 19)] == pytest.approx(70.10)


def test_the_cl_rule_derives_expiries_in_rank_order() -> None:
    assert ffc.cl_last_trade(2026, 12) == date(2026, 11, 20)
    d = date(2026, 10, 14)
    e = [ffc.cl_contract_expiry(d, k) for k in (1, 2, 3, 4)]
    assert e == sorted(e) and e[0] == date(2026, 10, 20)
    assert ffc.cl_contract_expiry(date(2026, 10, 21), 1) == date(2026, 11, 20), "rolled"


def test_the_curve_pass_publishes_eia_cl_and_reports_gc_unmeasured(tmp_path: Path) -> None:
    out, rp = tmp_path / "curves", tmp_path / "coverage.json"
    out.mkdir()
    # a Yahoo-era GC panel: moved aside, never read again, never deleted
    pd.DataFrame({"date": [pd.Timestamp("2026-01-02", tz="UTC")], "close": [2000.0],
                  "curve_rank": [1]}).to_parquet(out / "GC_curve.parquet")
    files = {f"RCLC{k}": _eia_xls(46000, 40, 60.0 + k) for k in (1, 2, 3, 4)}
    asked: list[str] = []

    def get(url: str) -> bytes:
        asked.append(url)
        return files[url.rsplit("/", 1)[-1].removesuffix("d.xls")]
    assert ffc.main([], get=get, out=out, report_path=rp) == 0
    assert all("eia.gov" in u for u in asked) and len(asked) == 4
    cl = pd.read_parquet(out / "CL_curve.parquet")
    assert cl["source"].str.startswith("eia_open_data:RCLC").all()
    assert cl["annualized_roll_yield"].notna().any()
    assert not (out / "GC_curve.parquet").exists()
    assert (out / "GC_curve.parquet.yahoo_ideas_only").exists()
    rep = json.loads(rp.read_text("utf-8"))
    assert rep["per_root"] == {"GC": ffc.UNMEASURED_NO_LICENSED_SOURCE, "CL": "MEASURED"}
    by = {x["source"]: x for x in rep["missed_growth"]}
    assert by["fetch_futures_curves:GC"]["series_status"] == ffc.UNMEASURED_NO_LICENSED_SOURCE
    assert by["fetch_futures_curves:CL"]["series_status"] == "SUBSTITUTED"
    assert all(x["delta_elogw"] == "UNMEASURED" for x in rep["missed_growth"])
    # the licensed CL panel survives the next pass's quarantine check
    assert ffc.quarantine_unlicensed("CL", out) is None


# ------------------------------------------------------------------ shadow bars
def test_yfinance_shadow_bars_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    import h1_source
    monkeypatch.setitem(sys.modules, "yfinance", None)   # would ImportError anyway
    assert h1_source.from_yfinance("XAUUSD", datetime(2026, 1, 1, tzinfo=UTC)) is None


# ------------------------------------------------------------------ the bill
def test_missed_growth_carries_every_cut_line_and_names_organs_without_artifacts(
        tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"missed_growth": [
        fd.yahoo_cut_line("^VIX", "macro_desk.anchors",
                          status=fd.UNMEASURED_NO_LICENSED_SOURCE),
        fd.yahoo_cut_line("^TNX", "macro_desk.anchors", status="SUBSTITUTED")]}), "utf-8")
    got = mg.yahoo_cut_lines((("macro_desk.anchors", a), ("vol_archive", tmp_path / "no.json")))
    assert got["n_cut"] == 2 and got["verdict"] == "UNMEASURED"
    assert got["unmeasured_no_licensed_source"] == ["macro_desk.anchors:VIX"]
    assert got["organs_without_artifact"] == ["vol_archive"]
