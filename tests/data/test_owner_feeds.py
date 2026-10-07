"""The public-domain owners' own feeds (ruling on FRED prohibition (j)): parsers, clocks, the
archive merge and the collector, on SYNTHETIC fixtures only -- the cloud container cannot reach
treasury.gov, bls.gov or eia.gov, so live behaviour is UNMEASURED until the box runs it."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from libs.data import owner_feeds as of
from libs.data.terms_hold import gauntlet_terms

ROOT = Path(__file__).resolve().parents[2]
NOMINAL_CSV = ('"Date","1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr",'
               '"5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
               '10/06/2026,4.30,4.29,4.28,4.20,4.15,4.05,3.90,3.60,3.55,3.62,3.80,4.05,4.50,4.62\n'
               '10/05/2026,4.31,,4.27,4.21,4.14,4.04,3.91,3.58,3.54,3.60,3.79,4.02,4.48,4.60\n')
REAL_CSV = ('Date,5 YR,7 YR,10 YR,20 YR,30 YR\n'
            '10/06/2026,1.30,1.55,1.80,2.10,2.20\n'
            '10/05/2026,1.28,N/A,1.79,2.09,2.19\n')


def _collector() -> Any:
    spec = importlib.util.spec_from_file_location(
        "collect_owner_macro", ROOT / "scripts" / "collect_owner_macro.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["collect_owner_macro"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_treasury_csv_parses_by_column_name() -> None:
    got = of.parse_treasury_csv(NOMINAL_CSV, of.TREASURY_NOMINAL)
    assert got["DGS10"] == {"2026-10-06": 4.05, "2026-10-05": 4.02}
    assert got["DGS3MO"]["2026-10-06"] == 4.20 and got["DGS30"]["2026-10-05"] == 4.60
    real = of.parse_treasury_csv("﻿" + REAL_CSV, of.TREASURY_REAL)
    assert real["DFII10"] == {"2026-10-06": 1.80, "2026-10-05": 1.79}
    assert real["DFII5"]["2026-10-05"] == 1.28
    assert of.parse_treasury_csv("", of.TREASURY_REAL) == {"DFII5": {}, "DFII10": {}}
    assert of.parse_treasury_csv("<html>blocked</html>", of.TREASURY_REAL)["DFII10"] == {}


def test_spreads_are_computed_from_the_owner_legs() -> None:
    legs = {**of.parse_treasury_csv(NOMINAL_CSV, of.TREASURY_NOMINAL),
            **of.parse_treasury_csv(REAL_CSV, of.TREASURY_REAL)}
    d = of.derive(legs)
    assert d["T10YIE"]["2026-10-06"] == pytest.approx(4.05 - 1.80)
    assert d["T5YIE"]["2026-10-05"] == pytest.approx(3.60 - 1.28)
    assert d["T10Y2Y"]["2026-10-06"] == pytest.approx(4.05 - 3.60)


def test_bls_parse_skips_annual_averages_and_unpublished_months() -> None:
    doc = {"status": "REQUEST_SUCCEEDED", "Results": {"series": [
        {"seriesID": "CUSR0000SA0", "data": [
            {"year": "2025", "period": "M13", "value": "320.0"},
            {"year": "2025", "period": "M10", "value": "-"},
            {"year": "2025", "period": "M09", "value": "324.245"},
            {"year": "2025", "period": "M11", "value": "325.031"}]}]}}
    got, status = of.parse_bls(doc)
    assert status == "REQUEST_SUCCEEDED"
    assert got["CUSR0000SA0"] == {"2025-09-01": 324.245, "2025-11-01": 325.031}
    assert of.parse_bls("nonsense")[0] == {}
    body = of.bls_payload(of.BLS_SERIES, 2007, 2026, "k")
    assert body["seriesid"] == list(of.BLS_SERIES) and body["registrationkey"] == "k"
    assert "registrationkey" not in of.bls_payload(of.BLS_SERIES, 2007, 2026, None)


def test_eia_parse() -> None:
    doc = {"response": {"data": [{"period": "2026-10-02", "value": "416123"},
                                 {"period": "2026-09-25", "value": 415000},
                                 {"period": "2026-09-18", "value": None}]}}
    assert of.parse_eia(doc) == {"2026-10-02": 416123.0, "2026-09-25": 415000.0}
    assert of.parse_eia({}) == {}


def test_available_is_the_earlier_of_first_held_and_the_declared_clock() -> None:
    # Treasury: next day 09:00 ET (13:00 UTC in summer)
    assert of.declared_available("DGS10", "2026-10-05") == datetime(2026, 10, 6, 13, 0,
                                                                     tzinfo=UTC)
    seen = "2026-10-05T23:10:00+00:00"
    assert of.available("DGS10", ("2026-10-05", 4.0, seen)) == datetime(2026, 10, 5, 23, 10,
                                                                         tzinfo=UTC)
    late = "2027-01-01T00:00:00+00:00"                   # a backfilled point: the calendar bound
    assert of.available("DGS10", ("2026-10-05", 4.0, late)) == datetime(2026, 10, 6, 13, 0,
                                                                         tzinfo=UTC)
    # BLS: reference month + 45 days 13:30 UTC; the 2025 shutdown releases overridden
    assert of.declared_available("CUSR0000SA0", "2026-08-01") == datetime(2026, 9, 15, 13, 30,
                                                                           tzinfo=UTC)
    assert of.declared_available("CUSR0000SA0", "2025-09-01") == datetime(2025, 10, 24, 12, 30,
                                                                           tzinfo=UTC)
    # EIA: never earlier than the regular Wednesday 10:30 ET release
    assert of.declared_available("WCESTUS1", "2026-10-02") > datetime(2026, 10, 7, 14, 30,
                                                                       tzinfo=UTC)


def test_merge_keeps_history_and_first_seen() -> None:
    prev = [["2026-10-05", 4.02, "2026-10-05T23:00:00+00:00"]]
    got = of.merge(prev, {"2026-10-06": 4.05, "2026-10-05": 4.03}, "2026-10-06T23:00:00+00:00")
    assert got == [["2026-10-05", 4.03, "2026-10-05T23:00:00+00:00"],
                   ["2026-10-06", 4.05, "2026-10-06T23:00:00+00:00"]]
    assert of.merge(prev, {}, "x") == prev                # a dead fetch erases nothing


def test_every_archived_id_passes_the_terms_gate_and_the_held_owners_do_not() -> None:
    for sid in of.PROVIDER:
        assert gauntlet_terms(of.source_id(sid))[0] is True, sid
    for sid in of.HELD:
        assert gauntlet_terms(sid)[0] is False, sid


def _fake(responses: dict[str, Any]) -> Any:
    calls: list[str] = []

    def fetch(url: str, body: dict[str, Any] | None = None) -> bytes:
        calls.append(url)
        for frag, out in responses.items():
            if frag in url:
                if isinstance(out, BaseException):
                    raise out
                return out if isinstance(out, bytes) else json.dumps(out).encode()
        raise URLError("unreachable")
    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


NOW = datetime(2026, 10, 7, 2, 0, tzinfo=UTC)


def test_collector_builds_the_archive_and_fails_soft() -> None:
    col = _collector()
    bls = {"status": "REQUEST_SUCCEEDED", "Results": {"series": [
        {"seriesID": "CUSR0000SA0", "data": [{"year": "2026", "period": "M08",
                                              "value": "330.1"}]}]}}
    eia = {"response": {"data": [{"period": "2026-10-02", "value": "416123"}]}}
    fetch = _fake({"daily_treasury_yield_curve&field_tdr_date_value=2026": NOMINAL_CSV.encode(),
                   "daily_treasury_real_yield_curve&field_tdr_date_value=2026":
                       REAL_CSV.encode(),
                   "api.bls.gov": bls,
                   "PET.WCESTUS1.W": eia,
                   "PET.WCSSTUS1.W": HTTPError("u", 500, "x", None, None)})  # type: ignore[arg-type]
    doc = col.collect(fetch, {"bls": "k", "eia": "SECRETKEY"}, NOW, {})
    ser = doc["series"]
    assert ser["DGS10"][-1][:2] == ["2026-10-06", 4.05]
    assert ser["T10YIE"][-1][1] == pytest.approx(4.05 - 1.80)
    assert ser["CUSR0000SA0"] == [["2026-08-01", 330.1, NOW.isoformat(timespec="seconds")]]
    assert ser["WCESTUS1"][0][:2] == ["2026-10-02", 416123.0]
    assert "WCSSTUS1" not in ser                         # failed: absent, never zero
    assert doc["feeds"]["eia"]["status"] == "PARTIAL"
    assert doc["feeds"]["eia"]["failed"]["WCSSTUS1"] == "HTTPError 500"
    # backfill years were tried and stopped after two consecutive failures
    assert doc["feeds"]["treasury"]["status"] == "PARTIAL"
    assert len(doc["feeds"]["treasury"]["years"]["daily_treasury_yield_curve"]) == 3
    assert doc["source_ids"]["DGS10"] == "treasury:DGS10"
    assert set(doc["held"]) == set(of.HELD)
    assert "SECRETKEY" not in json.dumps(doc)            # the key is never written


def test_collector_without_keys_or_network_keeps_the_previous_archive() -> None:
    col = _collector()
    prev = {"series": {"DGS10": [["2026-10-05", 4.02, "2026-10-05T23:00:00+00:00"]],
                       "DGS2": [["2026-10-05", 3.58, "2026-10-05T23:00:00+00:00"]],
                       "WCESTUS1": [["2026-09-25", 415000.0, "2026-10-01T15:00:00+00:00"]]}}
    doc = col.collect(_fake({}), {"bls": None, "eia": None}, NOW, prev)
    assert doc["feeds"]["treasury"]["status"] == "FAILED"
    assert doc["feeds"]["bls"]["status"] == "NO_KEY"
    assert doc["feeds"]["eia"]["status"] == "NO_KEY"
    assert doc["series"]["DGS10"] == prev["series"]["DGS10"]
    assert doc["series"]["WCESTUS1"] == prev["series"]["WCESTUS1"]
    assert doc["series"]["T10Y2Y"][0][1] == pytest.approx(4.02 - 3.58)


def test_collector_main_writes_the_archive(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    col = _collector()
    monkeypatch.setattr(col, "_keys", lambda: {"bls": None, "eia": None})
    monkeypatch.setattr(col, "_ROOT", tmp_path)
    target = tmp_path / "owner_macro.json"
    fetch = _fake({"daily_treasury_yield_curve": NOMINAL_CSV.encode(),
                   "daily_treasury_real_yield_curve": REAL_CSV.encode()})
    assert col.main(fetch, target) == 0
    loaded = of.load_archive(target)
    assert loaded["DGS10"][-1][:2] == ("2026-10-06", 4.05)
    obs = of.observations(loaded, "DFII10")
    assert obs and all(isinstance(t, datetime) for t, _ in obs)
    assert of.load_archive(tmp_path / "absent.json") == {}
