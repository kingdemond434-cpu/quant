"""Regression tests for the public-dataset acquisition format boundary."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from tests.data.xls_builder import build_xls, cell_number, cell_sst

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import acquire_datasets as acquisition  # noqa: E402


def test_legacy_eia_workbook_is_parsed_and_excel_dates_are_real_dates() -> None:
    records = cell_sst(0, 0, 0) + cell_sst(0, 1, 1)
    for row in range(1, 206):
        records += cell_number(row, 0, 43_000.0 + row)
        records += cell_number(row, 1, 70.0 + row / 100.0)
    raw = build_xls(
        [("Data 1", records), ("Notes", cell_sst(0, 0, 2))], ["Date", "WTI spot", "notes"]
    )

    frame = acquisition._parse(raw, "https://www.eia.gov/example.xls")
    assert frame is not None
    assert list(frame.columns)[:2] == ["Date", "WTI spot"]
    dated = acquisition._dated(frame)
    assert dated is not None and len(dated) == 205
    assert dated.index.min() == pd.Timestamp("2017-09-23", tz="UTC")
    assert float(dated["WTI spot"].iloc[-1]) == 72.05


def test_markup_never_falls_through_to_delimited_parser() -> None:
    assert (
        acquisition._parse(
            b"<html><table><tr><td>2026-01-01</td></tr></table></html>",
            "https://example.test/data.xls",
        )
        is None
    )


def test_acquired_endpoints_are_refreshed_after_one_hour(
    tmp_path: Path,
    monkeypatch,
) -> None:
    now = datetime(2026, 9, 28, 8, tzinfo=UTC)
    seed = acquisition._SEED_ENDPOINTS[0]
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"by_url": {seed: {"at": (now - timedelta(hours=2)).isoformat()}}}), "utf-8"
    )
    monkeypatch.setattr(acquisition, "REGISTRY", registry)
    monkeypatch.setattr(acquisition, "WORLD", tmp_path / "world")
    assert seed in [url for url, _host in acquisition._endpoints(40, now=now)]

    registry.write_text(
        json.dumps({"by_url": {seed: {"at": (now - timedelta(minutes=30)).isoformat()}}}), "utf-8"
    )
    assert seed not in [url for url, _host in acquisition._endpoints(40, now=now)]


def test_refused_endpoint_yields_its_seat_for_a_day(tmp_path: Path, monkeypatch) -> None:
    now = datetime(2026, 9, 28, 8, tzinfo=UTC)
    refused = acquisition._SEED_ENDPOINTS[0]
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "by_url": {
                    refused: {"at": (now - timedelta(hours=2)).isoformat(), "status": "REFUSED"}
                }
            }
        ),
        "utf-8",
    )
    monkeypatch.setattr(acquisition, "REGISTRY", registry)
    monkeypatch.setattr(acquisition, "WORLD", tmp_path / "world")
    assert refused not in [url for url, _host in acquisition._endpoints(40, now=now)]


def test_country_pack_frontier_is_region_balanced(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(acquisition, "_SEED_ENDPOINTS", ())
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "missing.json")
    monkeypatch.setattr(acquisition, "WORLD", tmp_path / "world")
    endpoints = acquisition._endpoints(40, now=datetime(2026, 9, 28, tzinfo=UTC))
    hosts = {host for _url, host in endpoints}
    # This does not encode a fixed source list. It proves the first bounded pass is not captured
    # by one country/continent and reaches globally distinct public institutions.
    assert len(endpoints) == 40
    assert len(hosts) >= 8


@pytest.mark.parametrize("all_fail", [True, False])
def test_persistence_failure_never_claims_success(tmp_path, monkeypatch, all_fail):
    monkeypatch.setattr(acquisition, "STORE", tmp_path)
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(acquisition, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(
        acquisition, "_endpoints", lambda limit: [("https://example.test/data", "example.test")]
    )
    monkeypatch.setattr(acquisition, "_fetch", lambda url: (b"data", "csv"))
    frame = pd.DataFrame({"value": [1.0, 2.0]}, index=pd.date_range("2020-01-01", periods=2))
    monkeypatch.setattr(acquisition, "_parse", lambda raw, url: frame)
    monkeypatch.setattr(acquisition, "_dated", lambda df: df)
    monkeypatch.setattr(
        acquisition, "_numeric_series", lambda df, stem: {"bad": frame.value, "good": frame.value}
    )

    def persist(self, path, **kwargs):
        if all_fail or path.stem == "bad":
            raise OSError("disk unavailable")

    def no_certificate(*args, **kwargs):
        raise ValueError("no publication timing")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", persist)
    monkeypatch.setattr(acquisition, "certify", no_certificate)
    report = acquisition.acquire()
    registry = json.loads(acquisition.REGISTRY.read_text())
    endpoint = registry["by_url"]["https://example.test/data"]
    assert endpoint["status"] == ("REFUSED" if all_fail else "PARTIAL")
    assert endpoint["series"] == ([] if all_fail else ["good"])
    assert report["datasets_kept"] == (0 if all_fail else 1)
    assert report["new_series"] == endpoint["series"]


@pytest.mark.parametrize("authority", [False, None, "false", "true", 1])
def test_nonboolean_authority_never_reaches_primitives(tmp_path, monkeypatch, authority):
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"series": {"x": {"path": "unused", "pit_authority": authority}}})
    )
    monkeypatch.setattr(acquisition, "REGISTRY", registry)
    reads = []
    monkeypatch.setattr(pd, "read_parquet", lambda path: reads.append(path))
    assert acquisition.acquired_series() == {}
    assert reads == []


def test_parity_lane_is_additive_and_terms_gated(monkeypatch, tmp_path: Path) -> None:
    """The regional-parity lane gets its own seats ON TOP of the pass and fails closed on terms."""
    world = tmp_path / "world"
    world.mkdir()
    monkeypatch.setattr(acquisition, "_SEED_ENDPOINTS", ())
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "missing.json")
    monkeypatch.setattr(acquisition, "WORLD", world)
    now = datetime(2026, 9, 28, tzinfo=UTC)
    base = acquisition._endpoints(40, now=now)
    permitted = [f"https://www.cftc.gov/files/dea/history/x{i}.zip" for i in range(9)]
    held = ["https://home.treasury.gov/resource-center/x.csv", "https://example.org/y.csv"]
    rows = [{"kind": "dataset", "lane": acquisition.PARITY_LANE, "host": "www.cftc.gov",
             "endpoints": held + permitted},
            {"kind": "dataset", "host": "www.cftc.gov", "endpoints": ["https://www.cftc.gov/z"]}]
    (world / "discoveries_parity_20261006.json").write_text(json.dumps(rows), "utf-8")
    endpoints = acquisition._endpoints(40, now=now)
    urls = [u for u, _ in endpoints]
    assert len(endpoints) == 40 + acquisition.PARITY_LANE_MAX
    assert urls[:40] == [u for u, _ in base], "no other lane loses a seat"
    assert urls[40:] == permitted[:acquisition.PARITY_LANE_MAX]
    assert not set(held) & set(urls), "a URL no terms quote permits is never fetched"
    assert "https://www.cftc.gov/z" not in urls[40:], "only lane-marked rows ride the lane"
