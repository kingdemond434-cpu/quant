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


def _ecb_frame() -> pd.DataFrame:
    """An ECB reference-rate series as `_dated` hands it on: business days at 00:00 UTC."""
    idx = pd.bdate_range("2019-01-01", "2026-09-30", tz="UTC")
    return pd.DataFrame({"value": [1.1 + (i % 50) * 1e-3 for i in range(len(idx))]}, index=idx)


def test_declared_ecb_reference_rates_earn_authority_and_join_after_publication(
        tmp_path, monkeypatch):
    """ARCH-26: the declaration maps were empty, so `pit_authority` was unreachable for every
    acquired series. A declared ECB reference rate earns it on its second certification (the
    first records the schema hash), an undeclared source never does, and the authorised series is
    joined from the NEXT UTC midnight -- never the morning before the ECB published it."""
    ecb = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata"
    other = "https://example.test/undeclared.csv"
    assert acquisition._SELECTION[ecb] == "all_rows_as_published"
    assert acquisition._REVISED[ecb] is False
    assert acquisition._PUBLICATION_LAG_S[ecb] == 86400
    assert other not in acquisition._SELECTION
    monkeypatch.setattr(acquisition, "STORE", tmp_path)
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(acquisition, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(acquisition, "write_certificate", lambda cert: None)
    monkeypatch.setattr(acquisition, "_endpoints",
                        lambda limit: [(ecb, "data-api.ecb.europa.eu"), (other, "example.test")])
    monkeypatch.setattr(acquisition, "_fetch", lambda url: (b"data", "csv"))
    frame = _ecb_frame()
    monkeypatch.setattr(acquisition, "_parse", lambda raw, url: frame)
    monkeypatch.setattr(acquisition, "_dated", lambda df: df)
    monkeypatch.setattr(acquisition, "_numeric_series",
                        lambda df, stem: {stem: df["value"]})

    acquisition.acquire()
    first = json.loads(acquisition.REGISTRY.read_text())["series"]
    ecb_name = next(n for n, m in first.items() if m["url"] == ecb)
    other_name = next(n for n, m in first.items() if m["url"] == other)
    assert first[ecb_name]["pit_authority"] is False
    assert first[ecb_name]["pit_blocking"] == ["schema"], "only the first-sight schema hash"
    assert set(first[other_name]["pit_blocking"]) >= {"revision", "availability", "survivorship"}

    acquisition.acquire()
    second = json.loads(acquisition.REGISTRY.read_text())["series"]
    assert second[ecb_name]["pit_authority"] is True, second[ecb_name]["pit_blocking"]
    assert second[ecb_name]["publication_lag_s"] == 86400
    assert second[other_name]["pit_authority"] is False

    got = acquisition.acquired_series()
    assert set(got) == {ecb_name}, "an undeclared source never reaches the vocabulary"
    assert got[ecb_name].index[0] == frame.index[0] + pd.Timedelta(days=1)
    bars = pd.date_range("2026-09-29 00:00", periods=48, freq="h", tz="UTC")
    joined = acquisition.acquired_series(bars)[ecb_name]
    # the 2026-09-29 fixing is published that afternoon: no bar of the 29th may read it
    assert joined.loc["2026-09-29 15:00"] == frame["value"].loc["2026-09-28"]
    assert joined.loc["2026-09-30 00:00"] == frame["value"].loc["2026-09-29"]


def test_an_authorised_series_with_no_recorded_lag_is_withheld(tmp_path, monkeypatch):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"series": {"x": {"path": "unused", "pit_authority": True}}}))
    monkeypatch.setattr(acquisition, "REGISTRY", registry)
    reads: list[str] = []
    monkeypatch.setattr(pd, "read_parquet", lambda path: reads.append(path))
    assert acquisition.acquired_series() == {}
    assert reads == []


# ---- ARCH-26: the Treasury, BIS and EIA seeds, declared from each publisher's own practice
from libs.data.pit_certificate import certify  # noqa: E402

_DECLARED = (
    # (url attribute, host fragment, declared lag in days)
    ("TREASURY_CURVE", "home.treasury.gov", 2),
    ("BIS_POLICY_RATES", "data.bis.org", 9),
    ("EIA_WTI_SPOT", "www.eia.gov", 9),
)


@pytest.mark.parametrize(("attr", "host", "lag_days"), _DECLARED)
def test_declared_publisher_sources_fail_revision_honestly(attr, host, lag_days):
    """Each publisher restates or documents no final-at-publication policy, and none carries a
    vintage: the certificate FAILS revision and withholds authority, while availability and
    survivorship -- the parts the publisher's release practice does answer -- PASS."""
    url = getattr(acquisition, attr)
    assert host in url and url in acquisition._SEED_ENDPOINTS
    assert acquisition._SELECTION[url] == "all_rows_as_published"
    assert acquisition._REVISED[url] is True
    assert acquisition._PUBLICATION_LAG_S[url] == lag_days * 86400
    meta = {"dataset": attr.lower(), "url": url, "host": host, "provider": host,
            "selection": acquisition._SELECTION[url], "revised": acquisition._REVISED[url],
            "publication_lag_s": acquisition._PUBLICATION_LAG_S[url],
            "history_starts": None, "schema_hash": None}
    cert = certify(meta, _ecb_frame(), now=pd.Timestamp("2026-10-07", tz="UTC").to_pydatetime())
    verdict = {c.name: c.verdict for c in cert.checks}
    assert verdict["revision"] == "FAIL"
    assert verdict["availability"] == "PASS" and verdict["survivorship"] == "PASS"
    assert cert.authority is False and "revision" in cert.failures()


def test_reordering_the_seeds_cannot_misattach_a_declaration():
    """Declarations are looked up by host, never by position in the seed tuple."""
    for attr, host, _ in _DECLARED:
        assert [u for u in acquisition._SEED_ENDPOINTS if host in u] == [getattr(acquisition, attr)]
    with pytest.raises(ValueError):
        acquisition._seed("no-such-publisher.example")


# ---- ARCH-26: first-seen vintage capture makes a revised source usable point-in-time
T1 = pd.Timestamp("2026-10-01 12:00", tz="UTC")
T2 = pd.Timestamp("2026-10-03 12:00", tz="UTC")


def _daily(start: str, n: int, base: float = 4.0) -> pd.Series:
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    return pd.Series([base + i * 0.01 for i in range(n)], index=idx, name="value")


def test_vintages_append_only_and_a_revision_never_leaks_backwards(tmp_path):
    path = tmp_path / "v.parquet"
    s1 = _daily("2026-09-01", 20)
    a = acquisition.capture_vintages(path, s1, T1.to_pydatetime())
    assert a["appended"] == 20 and a["revisions"] == 0
    first = acquisition.read_vintages(path)
    # the publisher restates the LATEST event, and adds nothing else
    s2 = s1.copy()
    s2.iloc[-1] = 99.0
    b = acquisition.capture_vintages(path, s2, T2.to_pydatetime())
    assert b["appended"] == 1 and b["revisions"] == 1
    # an unchanged re-read appends nothing
    assert acquisition.capture_vintages(path, s2, T2.to_pydatetime())["appended"] == 0
    after = acquisition.read_vintages(path)
    # an earlier vintage is never rewritten
    pd.testing.assert_frame_equal(after.iloc[:20], first)
    assert len(after) == 21

    lag = 2 * 86400
    view = acquisition.vintage_view(acquisition.vintage_frame(after, lag))
    bars = pd.date_range("2026-09-30", "2026-10-06", freq="h", tz="UTC")
    joined = acquisition._join(view, bars)
    last_event = s1.index[-1]
    # between the two captures the desk reads the value it HAD; the revision appears only from T2
    assert (joined[(joined.index >= T1) & (joined.index < T2)] == s1.iloc[-1]).all()
    assert (joined[joined.index >= T2] == 99.0).all()
    assert last_event + pd.Timedelta(seconds=lag) <= T1, "fixture: lag elapsed before capture"


def test_reads_before_the_first_capture_are_unmeasured(tmp_path, monkeypatch):
    monkeypatch.setattr(acquisition, "STORE", tmp_path)
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "registry.json")
    s = _daily("2020-01-01", 300)
    acquisition.capture_vintages(acquisition.vintage_path("x"), s, T1.to_pydatetime())
    (tmp_path / "registry.json").write_text(json.dumps({"series": {"x": {
        "path": "unused", "pit_authority": True, "publication_lag_s": 86400,
        "pit_view": "vintage", "vintage_path": str(acquisition.vintage_path("x"))}}}))
    bars = pd.date_range("2026-09-30", "2026-10-02", freq="h", tz="UTC")
    joined = acquisition.acquired_series(bars)["x"]
    assert joined[joined.index < T1].isna().all(), "history first seen at T1 is not backfilled"
    assert (joined[joined.index >= T1] == s.iloc[-1]).all()
    assert acquisition.as_of("x", pd.Timestamp("2025-06-01", tz="UTC")) == "UNMEASURED"
    assert acquisition.as_of("x", T1 + pd.Timedelta(hours=1)) == s.iloc[-1]


def _revised_run(tmp_path, monkeypatch, frames, suffix=""):
    """Run acquire() once per (capture time, frame) on the Treasury seed alone."""
    url = acquisition.TREASURY_CURVE
    monkeypatch.setattr(acquisition, "STORE", tmp_path)
    monkeypatch.setattr(acquisition, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(acquisition, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(acquisition, "write_certificate", lambda cert: None)
    monkeypatch.setattr(acquisition, "_endpoints", lambda limit: [(url, "home.treasury.gov")])
    monkeypatch.setattr(acquisition, "_fetch", lambda u: (b"data", "csv"))
    monkeypatch.setattr(acquisition, "_dated", lambda df: df)
    monkeypatch.setattr(acquisition, "_numeric_series",
                        lambda df, stem: {f"{stem}{suffix}": df["value"]})
    out = []
    for at, frame in frames:
        monkeypatch.setattr(acquisition, "_parse", lambda raw, u, f=frame: f.to_frame())
        acquisition.acquire(now=at.to_pydatetime())
        reg = json.loads((tmp_path / "registry.json").read_text())["series"]
        out.append(next(iter(reg.values())))
    return out


def test_the_vintage_view_earns_authority_once_it_reaches_the_floor(tmp_path, monkeypatch):
    floor = 25
    monkeypatch.setattr(acquisition, "MIN_ROWS", floor)
    idx = pd.bdate_range(end="2026-09-30", periods=300, tz="UTC")
    hist = pd.Series([4.0 + i * 0.01 for i in range(300)], index=idx, name="value")
    days = pd.bdate_range("2026-10-01", periods=floor + 2, tz="UTC")
    frames = []
    for i, d in enumerate(days):
        # one new trading day published per capture, read the morning after publication
        grown = pd.concat([hist, pd.Series([5.0 + i * 0.001], index=[d], name="value")])
        hist = grown
        frames.append((d + pd.Timedelta(days=2, hours=9), grown))
    runs = _revised_run(tmp_path, monkeypatch, frames)
    assert all(r["pit_view"] == "vintage" for r in runs)
    # the first capture: all 300+ history rows are ONE point-in-time instant -- no depth earned
    assert runs[0]["vintage_observations"] == 1 and runs[0]["pit_authority"] is False
    assert any(b.startswith("vintage_floor") for b in runs[1]["pit_blocking"])
    assert "revision" not in runs[1]["pit_blocking"], "revision PASSES on the vintage view"
    reached = [i for i, r in enumerate(runs) if r["vintage_observations"] >= floor]
    assert reached, [r["vintage_observations"] for r in runs]
    k = reached[0]
    assert all(r["pit_authority"] is False for r in runs[:k])
    assert runs[k]["pit_authority"] is True, runs[k]["pit_blocking"]
    # the publisher's own file, certified as published, still FAILS revision
    from libs.data.pit_certificate import certify as _certify
    raw = _certify({"dataset": "raw", "revised": True, "selection": "all_rows_as_published",
                    "publication_lag_s": 172800}, hist.to_frame(),
                   now=frames[-1][0].to_pydatetime())
    assert "revision" in raw.failures()


# ---- ARCH-26: archival vintages from ALFRED (fixtures: this container's proxy blocks the API)
LAG2 = 2 * 86400


def _alfred_rows(obs_dates, vintages):
    """ALFRED output_type=1 rows. `vintages` maps observation date -> [(realtime_start, value)]."""
    rows = []
    for d in obs_dates:
        for rt, val in vintages.get(d, []):
            rows.append({"realtime_start": rt, "realtime_end": "9999-12-31", "date": d,
                         "value": "." if val is None else str(val)})
    return acquisition.alfred_frame(rows)


def _publisher(dates, values):
    return pd.Series(values, index=pd.DatetimeIndex(dates, tz="UTC"), name="value")


def _fixture(n=30):
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=n)]
    vint = {d: [((pd.Timestamp(d) + pd.offsets.BDay(1)).strftime("%Y-%m-%d"), 4.0 + i / 100)]
            for i, d in enumerate(days)}
    pub = _publisher(days, [4.0 + i / 100 for i in range(n)])
    return days, vint, pub


def test_an_alfred_vintage_is_never_usable_before_its_realtime_start(tmp_path):
    days, vint, pub = _fixture()
    path = tmp_path / "v.parquet"
    rep = acquisition.ingest_alfred(path, pub, _alfred_rows(days, vint), LAG2, 0.0051, "DGS10")
    assert rep["status"] == "INGESTED" and rep["verified"] == 30 and rep["mismatches"] == 0
    store = acquisition.read_vintages(path)
    assert set(store["source"]) == {"alfred"}
    view = acquisition.vintage_view(acquisition.vintage_frame(store, LAG2))
    d0 = days[0]
    rt0 = vint[d0][0][0]
    usable = acquisition.alfred_capture_time(rt0, LAG2)
    assert usable == pd.Timestamp(rt0).tz_localize("America/New_York").tz_convert("UTC") \
        + pd.Timedelta(seconds=LAG2)
    bars = pd.DatetimeIndex([usable - pd.Timedelta(minutes=1), usable])
    joined = acquisition._join(view, bars)
    assert pd.isna(joined.iloc[0]), "nothing before the archive says the value existed"
    assert joined.iloc[1] == 4.0
    # idempotent: a second ingest appends nothing and rewrites nothing
    again = acquisition.ingest_alfred(path, pub, _alfred_rows(days, vint), LAG2, 0.0051, "DGS10")
    assert again["appended"] == 0
    pd.testing.assert_frame_equal(acquisition.read_vintages(path), store)


def test_a_later_alfred_vintage_does_not_leak_backwards(tmp_path):
    days, vint, pub = _fixture()
    last = days[-1]
    first_rt = vint[last][0][0]
    later_rt = (pd.Timestamp(first_rt) + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    vint[last] = [(first_rt, 3.10), (later_rt, float(pub.iloc[-1]))]  # revised to the current
    path = tmp_path / "v.parquet"
    acquisition.ingest_alfred(path, pub, _alfred_rows(days, vint), LAG2, 0.0051, "DGS10")
    view = acquisition.vintage_view(acquisition.vintage_frame(acquisition.read_vintages(path),
                                                              LAG2))
    t1 = acquisition.alfred_capture_time(first_rt, LAG2)
    t2 = acquisition.alfred_capture_time(later_rt, LAG2)
    bars = pd.date_range(t1, t2 + pd.Timedelta(days=1), freq="6h")
    joined = acquisition._join(view, bars)
    assert (joined[bars < t2] == 3.10).all(), "the first print is what the desk had"
    assert (joined[bars >= t2] == float(pub.iloc[-1])).all()


def test_alfred_is_cross_checked_against_the_publisher(tmp_path):
    days, vint, pub = _fixture(40)
    bad = pub.copy()
    bad.iloc[5] += 0.25                                   # one date disagrees: excluded, recorded
    rep = acquisition.ingest_alfred(tmp_path / "a.parquet", bad, _alfred_rows(days, vint),
                                    LAG2, 0.0051, "DGS10")
    assert rep["status"] == "INGESTED" and rep["mismatches"] == 1
    assert rep["mismatch_sample"][0]["date"] == days[5]
    assert days[5] not in {str(d.date()) for d in
                           acquisition.read_vintages(tmp_path / "a.parquet")["event_time"]}
    wrong = pub * 1.5                                      # a different series: nothing taken
    rep = acquisition.ingest_alfred(tmp_path / "b.parquet", wrong, _alfred_rows(days, vint),
                                    LAG2, 0.0051, "DGS10")
    assert rep["status"] == "REJECTED" and not (tmp_path / "b.parquet").exists()


@pytest.mark.parametrize(("sid", "notes", "held"), [
    ("VIXCLS", "", True), ("BAMLH0A0HYM2", "", True),
    ("DGS10", "Copyright, 2024, ICE Data Indices", True),
    ("DGS10", None, True),
    ("DGS10", "For further information see the H.15 release notes.", False),
])
def test_fred_copyrighted_series_stay_held(sid, notes, held):
    assert (acquisition.alfred_held(sid, notes) is not None) is held


def test_the_seed_map_is_identity_only():
    t = acquisition.TREASURY_CURVE
    assert acquisition.alfred_id(t, "home_treasury_gov_x_10_Yr") == "DGS10"
    assert acquisition.alfred_id(t, "home_treasury_gov_x_1_Yr") == "DGS1"
    assert acquisition.alfred_id(t, "home_treasury_gov_x_2_Mo") is None
    assert acquisition.alfred_id(acquisition.EIA_WTI_SPOT, "www_eia_gov_RWTCd_x") == "DCOILWTICO"
    assert acquisition.alfred_id(acquisition.BIS_POLICY_RATES, "data_bis_org_x") is None


def test_acquire_ingests_alfred_depth_and_never_writes_the_key(tmp_path, monkeypatch):
    days, vint, pub = _fixture(260)
    monkeypatch.setattr(acquisition, "MIN_ROWS", 200)
    monkeypatch.setattr(acquisition, "_alfred_key", lambda: "KEY-SECRET-123")
    monkeypatch.setattr(acquisition, "_alfred_notes", lambda sid, key: "H.15 notes")
    seen = []

    def fetch(sid, key):
        seen.append((sid, key))
        return _alfred_rows(days, vint)
    monkeypatch.setattr(acquisition, "_alfred_fetch", fetch)
    captures = [(pd.Timestamp("2026-10-07 09:00", tz="UTC"), pub),
                (pd.Timestamp("2026-10-08 09:00", tz="UTC"), pub)]
    # the publisher's file names its column `10 Yr`, as Treasury's CSV does
    runs = _revised_run(tmp_path, monkeypatch, captures, suffix="_10_Yr")
    first, second = runs
    assert first["alfred"]["status"] == "INGESTED" and first["alfred"]["series_id"] == "DGS10"
    assert seen == [("DGS10", "KEY-SECRET-123")], "fetched once; INGESTED is not re-asked"
    assert first["vintage_observations"] >= 200, "the archive's instants are real depth"
    assert first["pit_authority"] is False and first["pit_blocking"] == ["schema"]
    assert second["pit_authority"] is True, second["pit_blocking"]
    assert "KEY-SECRET-123" not in (tmp_path / "registry.json").read_text()
    store = acquisition.read_vintages(acquisition.vintage_path(next(iter(
        json.loads((tmp_path / "registry.json").read_text())["series"]))))
    assert set(store["source"]) == {"capture", "alfred"}
    assert second["vintage_appended"] == 0, "the live re-read matched: nothing new captured"


def test_no_key_is_unmeasured_and_retried_next_run(tmp_path, monkeypatch):
    days, vint, pub = _fixture(30)
    monkeypatch.setattr(acquisition, "_alfred_key", lambda: None)
    runs = _revised_run(tmp_path, monkeypatch,
                        [(pd.Timestamp("2026-10-07 09:00", tz="UTC"), pub)], suffix="_10_Yr")
    a = runs[0]["alfred"]
    assert a["status"] == "UNMEASURED" and "retry_after" not in a
