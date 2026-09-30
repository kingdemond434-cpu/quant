"""CERTIFICATE DATA IS POINT-IN-TIME, AND EVERY READER IS ACCOUNTED FOR (2026-09-30).

    python -m pytest desks/mt5/tests/test_certificate_pit.py -q

WHAT MUST NOT REGRESS:

  1. `data_os.known_series` moves a valid-dated series to valid + declared lag; a FRED series
     with a cadence entry uses its own (longer) lag; `known_as_of` drops unpublished prints
  2. `edge_search.resolve_inputs` -- the gauntlet's and the forward engine's `ext_` input --
     hands a bar a CFTC report only after its release, and never before; the feature still
     exists (a knowledge time that matches no bar must not silently empty the series)
  3. a `macro_state` snapshot is admitted only from its own `updated` stamp, never broadcast
     over the history before it
  4. `run_hunt17`'s anchors never reach a bar on the day they describe
  5. the certificate-input fence passes on the repo, and fails on an undeclared provider, an
     unlagged source and a provider that applies no lag
  6. the known-by-date floor is EMPTY and every reader is routed or declared
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_known_by_date as kbd  # noqa: E402

from libs.tiers import data_os  # noqa: E402


# ------------------------------------------------------------------------------ 1 the doors
def test_known_series_shifts_by_the_declared_lag() -> None:
    s = pd.Series([1.0], index=pd.to_datetime(["2026-03-03"]))           # a Tuesday report
    k = data_os.known_series(s, "cot_fx")
    assert k.index[0] == pd.Timestamp("2026-03-07")                       # Saturday 00:00
    assert data_os.lag_of("fred_macro", "PCOPPUSDM") > data_os.lag_of("fred_macro", "DGS10")
    assert data_os.lag_of("fred_macro", "DGS10") == data_os.lag_of("fred_macro")


def test_known_as_of_drops_unpublished_prints() -> None:
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-03-02", "2026-03-03"], utc=True))
    got = data_os.known_as_of(s, "fred_macro", datetime(2026, 3, 4, 2, tzinfo=UTC))
    assert list(got.values) == [1.0]                   # 03-03's print is known 03-04 03:00


def test_assumed_lags_are_flagged_not_dropped() -> None:
    flagged = data_os.assumed_lags()
    assert "macro_state" in flagged and "fred:PCOPPUSDM" in flagged
    assert all("assumed" in b for b in flagged.values())
    census = kbd.lag_census_doc()
    assert census["assumed_flagged"] == flagged
    assert census["publication_lags"]["macro_state"]["assumed"] is True


# ------------------------------------------------------------------ 2-3 the certificate path
@pytest.fixture()
def edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from research import edge_search as es
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    days = pd.date_range("2024-01-02", "2026-03-31", freq="D")
    tuesdays = days[days.dayofweek == 1]
    daily = pd.Series(range(len(tuesdays)), index=tuesdays, dtype=float).reindex(days).ffill()
    pd.DataFrame({"XAUUSD": daily}).to_parquet(tmp_path / "data" / "cot_zcache.parquet")
    monkeypatch.setattr(es, "BASE", desk)
    monkeypatch.setattr(es, "_close", lambda sym: None)
    es._RESOLVE_CACHE.clear()
    yield es, desk
    es._RESOLVE_CACHE.clear()


def test_resolve_inputs_reads_cot_only_after_release(edge) -> None:
    es, _desk = edge
    index = pd.date_range("2026-03-02", "2026-03-10", freq="h")
    cot = es.resolve_inputs("XAUUSD", index, ["XAUUSD"])["cot_net"]
    tue = pd.Timestamp("2026-03-03")
    fri = pd.Timestamp("2026-03-06 12:00")                 # release day, before the release
    sat = pd.Timestamp("2026-03-07 01:00")
    report_of_tue = float(cot.loc[sat])
    assert cot.notna().sum() > 0                            # the feature still exists
    assert float(cot.loc[fri]) == report_of_tue - 1.0       # Friday still reads LAST week's
    assert float(cot.loc[tue]) == report_of_tue - 1.0       # the Tuesday never reads itself
    assert list(cot.index) == list(index)


def test_macro_snapshot_is_never_broadcast_back(edge) -> None:
    es, desk = edge
    (desk / "data" / "macro_state.json").write_text(json.dumps(
        {"updated": "2026-03-05T12:00:00+00:00", "vix_z": 1.5}), "utf-8")
    index = pd.date_range("2026-03-04", "2026-03-06", freq="h")
    got = es.resolve_inputs("XAUUSD", index, ["XAUUSD"])["macro_vix_z"]
    assert got.loc[:"2026-03-05 11:00"].isna().all()
    assert (got.loc["2026-03-05 12:00":] == 1.5).all()


def test_undated_macro_snapshot_contributes_nothing(edge) -> None:
    es, desk = edge
    (desk / "data" / "macro_state.json").write_text(json.dumps({"vix_z": 1.5}), "utf-8")
    index = pd.date_range("2026-03-04", "2026-03-05", freq="h")
    assert "macro_vix_z" not in es.resolve_inputs("XAUUSD", index, ["XAUUSD"])


def test_certificate_input_lags_name_the_ext_sources() -> None:
    ext = data_os.certificate_input_lags("discovered", {"feature": "ext_cot_net_z"})
    assert ext["declared"] and "cot_fx" in ext["sources"] and "macro_state" in ext["assumed"]
    own = data_os.certificate_input_lags("discovered", {"feature": "dd_24"})
    assert list(own["sources"]) == ["mt5_h1_universe"]
    assert "fred_macro" in data_os.certificate_input_lags("macro_conditional")["sources"]


# ------------------------------------------------------------------------------ 4 hunt17
def test_hunt17_anchor_never_reaches_its_own_day() -> None:
    import run_hunt17 as h17
    z = pd.Series([0.1, 0.2, 0.3], index=pd.to_datetime(["2026-03-02", "2026-03-03",
                                                           "2026-03-04"]))
    idx = pd.date_range("2026-03-03", "2026-03-05 20:00", freq="4h")
    k = h17._known_on(z, idx)
    assert k.loc["2026-03-03 04:00"] != 0.2               # the old same-date lookup
    assert k.loc["2026-03-04 04:00"] == 0.2
    assert k.loc["2026-03-05 04:00"] == 0.3


# ------------------------------------------------------------------ 5 the certificate fence
def test_certificate_fence_passes_on_the_repo() -> None:
    doc = kbd.certificate_fence()
    assert doc["verdict"] == "OK", doc["failures"]
    called = kbd.providers_called()
    assert {"_cot_frame", "_macro_series", "resolve_inputs"} <= set(called)
    assert set(called) <= set(data_os.CERTIFICATE_INPUTS)


def test_certificate_fence_fails_undeclared_unlagged_and_unapplied(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gaunt = tmp_path / "desks" / "mt5" / "scripts"
    gaunt.mkdir(parents=True)
    (gaunt / "external_gauntlet.py").write_text(
        "def build_cell(inputs):\n    return inputs._new_feed(), inputs._lazy()\n", "utf-8")
    mod = tmp_path / "m.py"
    mod.write_text("def _lazy():\n    return 1\n", "utf-8")
    monkeypatch.setattr(data_os, "CERTIFICATE_INPUTS", {
        "_lazy": {"module": "m.py", "families": ("f",), "sources": ("cot_fx",)},
        "_ghost": {"module": "m.py", "families": ("g",), "sources": ("no_such_source",)}})
    doc = kbd.certificate_fence(tmp_path)
    assert doc["verdict"] == "FAIL"
    text = " | ".join(doc["failures"])
    assert "_new_feed: called on the certificate path" in text
    assert "_lazy: reads a lagged source but applies no lag" in text
    assert "_ghost: source(s) no_such_source carry no publication lag" in text


def test_fence_is_what_main_returns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(kbd, "OUT", tmp_path / "k.json")
    monkeypatch.setattr(kbd, "LAG_OUT", tmp_path / "l.json")
    monkeypatch.setattr(kbd, "certificate_fence", lambda root=None: {
        "providers": {}, "failures": ["x: undeclared"], "verdict": "FAIL"})
    assert kbd.main([]) == 1
    assert json.loads((tmp_path / "l.json").read_text("utf-8"))["certificate_inputs"][
        "verdict"] == "FAIL"


# --------------------------------------------------------------------- 6 every reader counted
def test_floor_is_empty_and_every_reader_is_accounted_for() -> None:
    assert kbd.read_floor() == set()
    doc = kbd.scan()
    acc = doc["accounting"]
    assert doc["offenders"] == {}
    assert acc["undeclared"] == 0, doc["no_join"]["undeclared"]
    assert acc["routed_or_declared"] == acc["readers"]
    for rel in data_os.READER_ROUTES:
        assert (ROOT / rel).exists(), rel
