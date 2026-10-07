"""The ERA5 (Copernicus CDS) reader, with a FAKE cdsapi client -- no network anywhere.

Pinned here, each as a property a later edit cannot quietly lose:
  * terms fail closed: no evidence, or evidence without a permitting quote, fetches nothing;
  * a missing key is BLOCKED_AUTH and a missing package UNAVAILABLE -- named, never a crash, and
    the key is read through libs.ops.env_keys.read_key and never written anywhere;
  * point in time: available_time = end of the valid date + the ERA5 release lag (>= 5 days),
    no request ever asks for a day younger than that, fetching is incremental, and the first
    value seen is kept;
  * the region config is valid and every region is registered in the paid-substitute library;
  * cells: a passing (region, field, instrument) becomes an exogenous_conditioner cell whose
    lake series the family itself loads (source-to-outcome), and the engine judges the ERA5
    substitute by its measured correlation (COVERED only at >= 0.5);
  * the leg is on the hourly clock with a budget and a layer.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
import types
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import era5_reader as e5  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
FAKE_KEY = "fake-cds-token-for-tests-only"
UNMEASURED_V = e5.UNMEASURED
CDS_LICENCE = "https://cds.climate.copernicus.eu/licences/cc-by"
CC_BY_TEXT = (
    "Creative Commons Attribution 4.0 International Public License. Section 2 - Scope. "
    "a. License grant. 1. Subject to the terms and conditions of this Public License, the "
    "Licensor hereby grants You a worldwide, royalty-free, non-sublicensable, non-exclusive, "
    "irrevocable license to exercise the Licensed Rights in the Licensed Material to:\n\n"
    "   A. reproduce and Share the Licensed Material, in whole or in part; and\n\n"
    "   B. produce, reproduce, and Share Adapted Material. Section 3 - License Conditions. "
    "a. Attribution. If You Share the Licensed Material, You must retain identification of "
    "the creator(s).")


# --------------------------------------------------------------------------- fixtures
def _small_regions() -> dict[str, Any]:
    return {
        "dataset": {"name": "reanalysis-era5-single-levels-timeseries",
                    "variables": ["2m_temperature", "total_precipitation"],
                    "data_format": "csv"},
        "release_lag_days": 5, "backfill_start": "2022-01-01", "chunk_days": 400,
        "climatology_min_years": 2,
        "regions": [{
            "id": "us_test_belt", "label": "test belt", "library_region": "US",
            "hdd_base_c": 18.3,
            "points": [{"id": "p_a", "lat": 42.0, "lon": -93.5, "weight": 0.6},
                       {"id": "p_b", "lat": 40.0, "lon": -89.0, "weight": 0.4}],
            "instruments": {"cdd_anom_7d": {"CORN": 1}, "precip_anom_30d": {"CORN": -1},
                            "hdd_anom_7d": {"XNGUSD": 1}},
            "headline": "cdd_anom_7d", "mechanism": "test"}]}


def _desk(tmp: Path, regions: dict[str, Any] | None = None) -> e5.Paths:
    desk = tmp / "desk"
    (desk / "data").mkdir(parents=True)
    (desk / "data" / "era5_regions.json").write_text(json.dumps(regions or _small_regions()),
                                                      "utf-8")
    return e5.Paths(desk)


def _confirm(paths: e5.Paths) -> None:
    ev = e5.confirm_terms(paths, text_file=_licence(paths.desk.parent, CC_BY_TEXT),
                          text_url=CDS_LICENCE, now=NOW)
    assert ev["verdict"] == "confirmed"


def _licence(tmp: Path, text: str) -> Path:
    p = tmp / "licence.txt"
    p.write_text(text, "utf-8")
    return p


class FakeClient:
    """The cdsapi.Client surface the reader uses: retrieve(name, request, target)."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail = fail

    def retrieve(self, name: str, request: dict[str, Any], target: str) -> None:
        self.calls.append((name, request))
        if self.fail is not None:
            raise self.fail
        start, end = (date.fromisoformat(x) for x in request["date"][0].split("/"))
        lat = float(request["location"]["latitude"])
        lines = ["valid_time,t2m,tp,latitude,longitude"]
        d = start
        while d <= end:
            doy = d.timetuple().tm_yday
            base = 283.15 + 15 * math.sin(2 * math.pi * (doy - 110) / 365) - (lat - 40) * 0.3
            for h in range(24):
                t = base + 4 * math.sin(2 * math.pi * (h - 9) / 24) + (d.year - 2022) * 0.5
                tp = 0.0002 if (doy + h) % 11 == 0 else 0.0
                lines.append(f"{d.isoformat()} {h:02d}:00:00,{t:.3f},{tp},{lat},0")
            d += timedelta(days=1)
        Path(target).write_text("\n".join(lines), "utf-8")


def _factory(client: FakeClient) -> Any:
    return lambda: (client, e5.OK, "fake")


def _never() -> Any:
    raise AssertionError("the client must not be built when terms are not confirmed")


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text("utf-8", errors="ignore") for p in root.rglob("*")
                     if p.is_file())


# --------------------------------------------------------------------------- region config
def test_region_config_is_valid_mapped_to_the_universe_and_in_the_library() -> None:
    doc = e5.load_regions()
    uni = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    assert e5.region_config_errors(doc, set(uni)) == []
    assert e5.lag_days(doc) >= e5.ERA5_LAG_DAYS
    ids = {r["id"] for r in doc["regions"]}
    assert {"us_midwest_corn_soy", "brazil_coffee", "brazil_sugar", "west_africa_cocoa",
            "europe_gas_demand", "us_natgas_demand"} <= ids
    lib = {s["id"]: s for s in json.loads(
        (_DESK / "data" / "paid_substitute_library.json").read_text("utf-8"))["sources"]}
    for r in doc["regions"]:
        row = lib[e5.substitute_id(r["id"])]
        assert row["auth"] == "free_key" and row["auth_env"] == e5.KEY_NAME
        assert row["terms_evidence"] == "data/era5/terms_evidence.json"
        assert row["endpoint"].startswith("https://")
        assert row["classes"] == ["weather"] and row["region"] == r["library_region"]
        assert sorted(row["instruments"]) == sorted(
            {s for m in r["instruments"].values() for s in m})
        assert row["lake_series"] == e5.psub_lake_id(r["id"])


def test_region_config_errors_are_named() -> None:
    bad = {"regions": [{"id": "Bad Id", "points": [{"id": "x", "lat": 99, "lon": 0, "weight": 1}],
                        "instruments": {"nope": {"CORN": 2}}, "headline": "nope"}]}
    errs = " | ".join(e5.region_config_errors(bad, {"CORN"}))
    for frag in ("not a short slug", "out of range", "unknown field nope", "prior must be",
                 "headline", "hdd_base_c"):
        assert frag in errs, frag
    assert e5.region_config_errors({}) == ["no regions"]


# --------------------------------------------------------------------------- terms
def test_terms_fail_closed_without_evidence(tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    rep = e5.run(paths, now=NOW, client_factory=_never, mint=lambda s: True)
    assert rep["status"] == "BLOCKED_ON_TERMS:to_confirm"
    assert rep["terms_evidence"]["evidence"]["judgement"].startswith("needs-box-confirmation")
    assert any("--confirm-terms" in s for s in rep["box_steps"])
    assert not (paths.series).exists() and not paths.points.exists()


def test_evidence_that_says_confirmed_without_a_permitting_quote_stays_blocked(
        tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    paths.terms_evidence.parent.mkdir(parents=True)
    paths.terms_evidence.write_text(json.dumps({
        "verdict": "confirmed", "kind": "cc-by-4.0", "terms_quote": "all rights reserved",
        "terms_url": "https://x", "checked_at": "2026-10-06", "sha256": "0"}), "utf-8")
    assert e5.terms_status(paths)[0] == "to_confirm"
    assert e5.run(paths, now=NOW, client_factory=_never)["status"].startswith("BLOCKED_ON_TERMS")


def test_confirm_terms_quotes_the_clause_and_refuses_non_commercial(tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    nc = CC_BY_TEXT.replace("Attribution 4.0", "Attribution-NonCommercial 4.0")
    ev = e5.confirm_terms(paths, text_file=_licence(tmp_path, nc), text_url=CDS_LICENCE,
                          now=NOW)
    assert ev["verdict"] == "to_confirm"
    assert e5.terms_status(paths)[0] == "to_confirm"
    _confirm(paths)
    verdict, ev = e5.terms_status(paths)
    assert verdict == "confirmed" and ev["kind"] == "cc-by-4.0"
    assert "grants You a worldwide, royalty-free" in ev["terms_quote"]
    assert len(ev["sha256"]) == 64


def test_confirm_terms_follows_the_catalogue_licence_link_without_network(tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    seen: list[str] = []

    def get(url: str) -> tuple[int, str, bytes]:
        seen.append(url)
        if url.endswith("/collections/reanalysis-era5-single-levels-timeseries"):
            return 200, "application/json", json.dumps({"links": [
                {"rel": "license", "href": CDS_LICENCE + ".txt"}]}).encode()
        return 200, "text/plain", CC_BY_TEXT.encode()

    ev = e5.confirm_terms(paths, get=get, now=NOW)
    assert ev["verdict"] == "confirmed" and ev["terms_url"].endswith("cc-by.txt")
    assert seen[0].startswith(e5.CDS_URL)

    def pdf(url: str) -> tuple[int, str, bytes]:
        if "collections" in url:
            return 200, "application/json", json.dumps({"links": [{"rel": "license",
                                                       "href": CDS_LICENCE + ".pdf"}]}).encode()
        return 200, "application/pdf", b"%PDF-1.7 ..."

    ev = e5.confirm_terms(paths, get=pdf, now=NOW)
    assert ev["verdict"] == "to_confirm" and ev["unread"][0]["why"].startswith("PDF")


PROHIBITING = (
    "Use of the data is free and worldwide, but commercial use is not permitted. Attribution "
    "is required.",
    "This licence is free of charge and worldwide and prohibits commercial exploitation; "
    "attribution is required.",
    "Free worldwide use of the products is granted except commercial use, with attribution.",
    "Users may not use the data commercially; otherwise access is free and worldwide with "
    "attribution.",
)


@pytest.mark.parametrize("text", PROHIBITING)
def test_negated_or_prohibiting_clauses_never_confirm(tmp_path: Path, text: str) -> None:
    assert e5.permitting_clause(text, CDS_LICENCE) is None
    paths = _desk(tmp_path)
    ev = e5.confirm_terms(paths, text_file=_licence(tmp_path, text), text_url=CDS_LICENCE,
                          now=NOW)
    assert ev["verdict"] == "to_confirm" and e5.terms_status(paths)[0] == "to_confirm"
    # a stored quote that prohibits is refused on re-read too, whatever its verdict says
    assert not e5.clause_holds("licence_clause", text, CDS_LICENCE)
    # and the positive shape still confirms, so the fence is not a blanket refusal
    ok = ("Access to the products is free of charge, worldwide, for any purpose including "
          "commercial use, with attribution to the source.")
    got = e5.permitting_clause(ok, CDS_LICENCE)
    assert got is not None and got["kind"] == "licence_clause"


def test_only_copernicus_and_ecmwf_hosts_count(tmp_path: Path) -> None:
    from libs.data.licence_evidence import allowed_url
    for good in ("https://cds.climate.copernicus.eu/licences/cc-by",
                 "https://www.copernicus.eu/en/access-data/copyright-and-licences",
                 "https://confluence.ecmwf.int/display/CKB/ERA5", "https://apps.ecmwf.int/x"):
        assert allowed_url(good), good
    for bad in ("http://cds.climate.copernicus.eu/licences/cc-by", "https://cds.example/l",
                "https://copernicus.eu.evil.example/l", "https://evilcopernicus.eu/l",
                "https://ecmwf.int.example/l", "file:licence.txt", "", None):
        assert not allowed_url(bad), bad
    paths = _desk(tmp_path)
    seen: list[str] = []

    def get(url: str) -> tuple[int, str, bytes]:
        seen.append(url)
        if "collections" in url:
            return 200, "application/json", json.dumps({"links": [
                {"rel": "license", "href": "https://licences.example/cc-by.txt"}]}).encode()
        return 200, "text/plain", CC_BY_TEXT.encode()

    ev = e5.confirm_terms(paths, get=get, now=NOW)
    assert ev["verdict"] == "to_confirm"
    assert seen == [seen[0]], "a licence link on a foreign host is never fetched"
    assert any(t.get("rejected") for t in ev["tried"])


def test_cc_by_text_counts_only_from_an_allowed_host(tmp_path: Path) -> None:
    spdx = "https://raw.githubusercontent.com/spdx/license-list-data/main/text/CC-BY-4.0.txt"
    assert e5.permitting_clause(CC_BY_TEXT, spdx) is None
    got = e5.permitting_clause(CC_BY_TEXT, CDS_LICENCE)
    assert got is not None and got["kind"] == "cc-by-4.0"
    # an evidence file holding the genuine CC BY grant, but read from SPDX, is not evidence
    paths = _desk(tmp_path)
    paths.terms_evidence.parent.mkdir(parents=True)
    paths.terms_evidence.write_text(json.dumps({
        "verdict": "confirmed", "kind": "cc-by-4.0", "terms_quote": got["quote"],
        "terms_url": spdx, "checked_at": "2026-10-06", "sha256": "a" * 64}), "utf-8")
    assert e5.terms_status(paths)[0] == "to_confirm"
    assert e5.run(paths, now=NOW, client_factory=_never)["status"].startswith("BLOCKED_ON_TERMS")


@pytest.mark.parametrize("url", [None, "https://spdx.org/licenses/CC-BY-4.0.html",
                                 "http://cds.climate.copernicus.eu/licences/cc-by"])
def test_terms_text_without_an_allowed_terms_url_never_writes_confirmed(
        tmp_path: Path, url: str | None) -> None:
    paths = _desk(tmp_path)
    ev = e5.confirm_terms(paths, text_file=_licence(tmp_path, CC_BY_TEXT), text_url=url,
                          now=NOW)
    assert ev["verdict"] == "to_confirm"
    stored = json.loads(paths.terms_evidence.read_text("utf-8"))
    assert stored["verdict"] != "confirmed" and "terms_quote" not in stored
    assert e5.terms_status(paths)[0] == "to_confirm"


def test_a_licence_not_accepted_reply_is_blocked_on_terms(tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    _confirm(paths)
    client = FakeClient(fail=RuntimeError("403 Client Error: required licences not accepted"))
    rep = e5.run(paths, now=NOW, client_factory=_factory(client), key_reader=lambda n: None,
                 mint=lambda s: True)
    assert rep["status"] == "BLOCKED_ON_TERMS:licence_not_accepted"
    assert len(client.calls) == 1, "a licence refusal stops the pass"
    assert any("accept the ERA5 dataset licence" in s for s in rep["box_steps"])


# --------------------------------------------------------------------------- key and package
def _fake_cdsapi(record: dict[str, Any]) -> types.ModuleType:
    mod = types.ModuleType("cdsapi")

    class Client:
        def __init__(self, **kw: Any) -> None:
            record.update(kw)

    mod.Client = Client  # type: ignore[attr-defined]
    return mod


def test_missing_key_is_blocked_auth_and_missing_package_unavailable() -> None:
    rec: dict[str, Any] = {}
    client, st, why = e5.make_client(read=lambda n: None, importer=lambda n: _fake_cdsapi(rec))
    assert client is None and st == e5.BLOCKED_AUTH and e5.KEY_NAME in why and not rec

    def no_pkg(name: str) -> Any:
        raise ImportError(name)

    client, st, why = e5.make_client(read=lambda n: FAKE_KEY, importer=no_pkg)
    assert client is None and st == e5.UNAVAILABLE and "climate" in why


def test_key_and_url_go_through_read_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import env_keys, env_secret
    monkeypatch.setattr(env_secret, "_registry", lambda hive, name: None)
    monkeypatch.setenv(e5.KEY_NAME, FAKE_KEY)
    monkeypatch.delenv(e5.URL_NAME, raising=False)
    assert env_keys.read_key(e5.KEY_NAME) == FAKE_KEY
    rec: dict[str, Any] = {}
    client, st, _ = e5.make_client(importer=lambda n: _fake_cdsapi(rec))
    assert st == e5.OK and rec["key"] == FAKE_KEY and rec["url"] == e5.CDS_URL
    # the machine registry beats a stale inherited copy (a setx /M after the resident started)
    monkeypatch.setattr(env_secret, "_registry",
                        lambda hive, name: "https://mirror.example/api"
                        if hive == "machine" and name == e5.URL_NAME else None)
    e5.make_client(importer=lambda n: _fake_cdsapi(rec))
    assert rec["url"] == "https://mirror.example/api"


def test_client_takes_url_and_key_from_machine_scope_with_no_cdsapirc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A SYSTEM task has no profile and no ~/.cdsapirc: both values come from the Machine scope
    through read_key and are handed to cdsapi.Client explicitly."""
    from libs.ops import env_secret
    machine = {e5.KEY_NAME: FAKE_KEY, e5.URL_NAME: "https://cds.climate.copernicus.eu/api"}
    monkeypatch.setattr(env_secret, "_registry",
                        lambda hive, name: machine.get(name) if hive == "machine" else None)
    for n in (e5.KEY_NAME, e5.URL_NAME, "CDSAPI_RC"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert not (tmp_path / ".cdsapirc").exists()
    rec: dict[str, Any] = {}
    client, st, why = e5.make_client(importer=lambda n: _fake_cdsapi(rec))
    assert st == e5.OK and client is not None, why
    assert rec["key"] == FAKE_KEY and rec["url"] == machine[e5.URL_NAME]
    # no URL anywhere: the default endpoint, still with the explicit key
    machine.pop(e5.URL_NAME)
    rec.clear()
    e5.make_client(importer=lambda n: _fake_cdsapi(rec))
    assert rec["url"] == e5.CDS_URL and rec["key"] == FAKE_KEY
    assert FAKE_KEY not in why


def test_missing_key_on_a_full_run_is_a_named_state_and_no_key_is_written(
        tmp_path: Path) -> None:
    paths = _desk(tmp_path)
    _confirm(paths)
    rep = e5.run(paths, now=NOW, client_factory=lambda: e5.make_client(
        read=lambda n: None, importer=lambda n: _fake_cdsapi({})), mint=lambda s: True)
    assert rep["status"] == e5.BLOCKED_AUTH
    assert any(s.startswith("setx /M CDSAPI_KEY") for s in rep["box_steps"])
    assert paths.report.exists()
    # and a full fetch never writes the key it was handed
    client = FakeClient()
    e5.run(paths, now=NOW, client_factory=_factory(client), key_reader=lambda n: FAKE_KEY,
           mint=lambda s: True, donor=lambda *a, **k: {"donated": 0})
    assert FAKE_KEY not in _all_text(paths.desk)
    assert e5.redact(f"boom {FAKE_KEY}", FAKE_KEY) == "boom <redacted>"
    assert "<redacted>" in e5.redact("key d3d3c160-2e3f-41ee-bdf2-9a934f0a08dc leaked")


# --------------------------------------------------------------------------- point in time
def _fetched(tmp_path: Path) -> tuple[e5.Paths, FakeClient, dict[str, Any]]:
    paths = _desk(tmp_path)
    _confirm(paths)
    client = FakeClient()
    # a pass advances each cursor by at most one chunk (400 days here), so the backfill takes
    # several hourly passes; run them until the cursors stop moving, as the box would
    rep: dict[str, Any] = {}
    seen: dict[str, Any] | None = None
    for _ in range(8):
        rep = e5.run(paths, now=NOW, budget_s=600, client_factory=_factory(client),
                     key_reader=lambda n: None, mint=lambda s: True,
                     donor=lambda *a, **k: {"donated": 0})
        if rep.get("cursors") == seen:
            break
        seen = rep.get("cursors")
    return paths, client, rep


def test_pit_lag_and_no_request_younger_than_the_release(tmp_path: Path) -> None:
    paths, client, rep = _fetched(tmp_path)
    assert rep["status"] == e5.OK, rep.get("fetch")
    youngest = NOW.date() - timedelta(days=e5.ERA5_LAG_DAYS + 1)
    for _, req in client.calls:
        end = date.fromisoformat(req["date"][0].split("/")[1])
        assert end <= youngest
    import pandas as pd
    lake = pd.read_csv(paths.series / f"{e5.lake_id('us_test_belt', 't2m_c')}.csv")
    ev = pd.to_datetime(lake["event_time"], utc=True)
    av = pd.to_datetime(lake["available_time"], utc=True)
    assert ((av - ev) >= pd.Timedelta(days=e5.ERA5_LAG_DAYS + 1)).all()
    assert (av <= NOW).all()
    assert set(lake["pit_quality"]) <= {"backfill", "live"}
    # the fields need prior years: an anomaly is NaN (absent) until two prior years exist
    anom = pd.read_csv(paths.series / f"{e5.lake_id('us_test_belt', 'cdd_anom_7d')}.csv")
    assert pd.to_datetime(anom["event_time"], utc=True).min() >= pd.Timestamp("2024-01-01",
                                                                             tz="UTC")


def test_fetch_is_incremental_and_first_value_wins(tmp_path: Path) -> None:
    paths, client, _ = _fetched(tmp_path)
    state = json.loads(paths.state.read_text("utf-8"))
    nxt = {k: v["next"] for k, v in state["points"].items()}
    assert set(nxt) == {"p_a", "p_b"}
    later = FakeClient()
    e5.run(paths, now=NOW + timedelta(days=3), client_factory=_factory(later),
           key_reader=lambda n: None, mint=lambda s: True, donor=lambda *a, **k: {})
    for _, req in later.calls:
        start = date.fromisoformat(req["date"][0].split("/")[0])
        assert start.isoformat() in nxt.values()
    before = e5.read_point(paths, "p_a")
    d0 = min(before)
    changed = {d0: {"t2m_mean": 99.0, "t2m_min": 99.0, "t2m_max": 99.0, "precip_mm": 9.0}}
    res = e5.merge_point(paths, "p_a", changed, NOW)
    assert res == {"added": 0, "revisions_ignored": 1}
    assert e5.read_point(paths, "p_a")[d0]["t2m_mean"] == before[d0]["t2m_mean"]


def test_parse_handles_a_zip_of_per_variable_csvs_in_kelvin_and_metres() -> None:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("t2m.csv", "valid_time,t2m\n" + "\n".join(
            f"2026-01-01 {h:02d}:00:00,273.15" for h in range(24)))
        z.writestr("tp.csv", "valid_time,tp\n" + "\n".join(
            f"2026-01-01 {h:02d}:00:00,0.001" for h in range(24)))
    days = e5.daily(e5.parse_hourly(buf.getvalue()))
    assert days[date(2026, 1, 1)]["t2m_mean"] == pytest.approx(0.0)
    assert days[date(2026, 1, 1)]["precip_mm"] == pytest.approx(24.0)
    partial = e5.daily(e5.parse_hourly(b"valid_time,t2m,tp\n2026-01-02 00:00:00,280,0\n"))
    assert partial == {}


# --------------------------------------------------------------------------- the three uses
def test_cell_donation_reaches_a_series_the_family_loads(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _, rep = _fetched(tmp_path)
    assert rep["uses"]["conditioning_series"] > 0
    assert (paths.axes / "era5_us_test_belt.json").exists()
    assert (paths.series / f"{e5.psub_lake_id('us_test_belt')}.csv").exists()
    key = "us_test_belt|cdd_anom_7d|CORN"
    monkeypatch.setattr(e5, "gain_tests", lambda *a, **k: {
        key: {"verdict": "PASS", "ic": -0.12, "n": 60},
        "us_test_belt|hdd_anom_7d|XNGUSD": {"verdict": "FAIL", "ic": 0.01, "n": 60}})
    donated: list[Any] = []
    rep = e5.run(paths, now=NOW, fetch=False, mint=lambda s: True,
                 donor=lambda p, cands, tested, now: donated.append((cands, tested)) or
                 {"donated": len(cands)})
    cands, tested = donated[0]
    assert tested == 2 and len(cands) == 1
    c = cands[0]
    assert c["family"] == "exogenous_conditioner" and c["symbol"] == "CORN"
    assert c["params"]["side_when_high"] == -1, "side is the MEASURED sign, not the +1 prior"
    assert c["prior_sign"] == 1
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner(c["params"]["source"], "value", "level_z", root=paths.series)
    assert s is not None and len(s) > 100
    intel = json.loads(paths.allocation_intel.read_text("utf-8"))
    corn = intel["instruments"]["CORN"]["components"]
    assert {x["sign_basis"] for x in corn} == {"measured_ic", "prior"}


def test_share_cfds_never_mint(tmp_path: Path) -> None:
    gains = {"us_test_belt|cdd_anom_7d|CORN": {"verdict": "PASS", "ic": 0.2}}
    assert e5.direct_cells(_small_regions(), gains, NOW, mint=lambda s: False) == []


# --------------------------------------------------------------------------- the engine
def test_engine_fences_era5_on_terms_and_reads_the_key_by_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import paid_substitute_engine as pse
    row = next(s for s in pse.load_library() if s["id"] == "era5_us_midwest_corn_soy")
    monkeypatch.setattr(pse, "DESK", tmp_path)
    assert pse.usable(row, {e5.KEY_NAME: FAKE_KEY}) == (False, "BLOCKED_ON_TERMS:to_confirm")
    ev = tmp_path / "data" / "era5" / "terms_evidence.json"
    ev.parent.mkdir(parents=True)
    ev.write_text(json.dumps({"verdict": "confirmed", "terms_quote": "a quote"}), "utf-8")
    assert pse.usable(row, {})[0] is False
    ok, why = pse.usable(row, {e5.KEY_NAME: FAKE_KEY})
    assert ok and FAKE_KEY not in why


def _series_csv(path: Path, values: list[float], start: str = "2015-01-01") -> None:
    import pandas as pd
    idx = pd.date_range(start, periods=len(values), freq="D", tz="UTC")
    pd.DataFrame({"event_time": idx.astype(str), "available_time": (idx + pd.Timedelta(days=6))
                  .astype(str), "value": values}).to_csv(path, index=False)


def test_engine_covers_only_at_measured_correlation_of_at_least_half(tmp_path: Path) -> None:
    import numpy as np
    import paid_substitute_engine as pse
    rng = np.random.default_rng(7)
    walk = np.cumsum(rng.normal(size=3000))
    sub = {"id": "era5_us_midwest_corn_soy", "classes": ["weather"], "region": "US"}
    paid = {"id": "paid:test:degree_days", "class": "weather", "region": "US",
            "public_sample": {"status": "MACHINE_SERIES", "endpoints": []}}
    _series_csv(tmp_path / f"{pse.sample_id(paid)}.csv", list(walk))
    _series_csv(tmp_path / f"{pse.dataset_id(sub)}.csv",
                list(walk + rng.normal(scale=0.3, size=walk.size)))
    assert pse.dataset_id(sub) == e5.psub_lake_id("us_midwest_corn_soy")
    corr = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(corr, float) and corr >= pse.MIN_CORRELATION
    good = {"components": {"class": 1.0, "region": 1.0}, "coverage": 0.9, "correlation": corr}
    assert pse.verification(good) == "VERIFIED"
    _series_csv(tmp_path / f"{pse.dataset_id(sub)}.csv", list(rng.normal(size=3000)))
    low = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(low, float) and low < pse.MIN_CORRELATION
    assert pse.verification({**good, "correlation": low}) == "REJECTED"
    unpaid = {**paid, "public_sample": {"status": "NONE_KNOWN"}}
    assert pse.correlation(unpaid, sub, lake=tmp_path) == pse.UNMEASURED
    assert pse.verification({**good, "correlation": pse.UNMEASURED}) == "MATCHED_UNVERIFIED"


# --------------------------------------------------------------------------- the clock
def test_leg_is_on_the_hourly_clock_with_a_budget_and_a_layer() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert re.search(r'_costed\("era5_reader", lambda: _producer\(\s*"era5_reader", '
                     r'"research/era5_reader.py"', src)
    assert '"era5_reader": 900' in src
    assert '"era5_reader": e5r' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["era5_reader"] == "information"


def test_pyproject_declares_cdsapi_in_an_extra_with_a_cap() -> None:
    import tomllib
    extras = tomllib.loads((_ROOT / "pyproject.toml").read_text("utf-8"))["project"][
        "optional-dependencies"]
    spec = next(s for s in extras["climate"] if s.startswith("cdsapi"))
    assert "<" in spec and ">=" in spec


def test_tree_carries_no_key_value() -> None:
    for p in (_DESK / "research" / "era5_reader.py", _DESK / "data" / "era5_regions.json"):
        assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                             p.read_text("utf-8")), p


@pytest.fixture(autouse=True)
def _no_leftovers(tmp_path: Path) -> Any:
    yield
    shutil.rmtree(tmp_path / "desk", ignore_errors=True)


# --------------------------------------------------------------------------- trial charges
def test_two_identical_passes_charge_once_and_new_data_recharges(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _, _ = _fetched(tmp_path)
    verdicts = {"us_test_belt|cdd_anom_7d|CORN": {"verdict": "PASS", "ic": 0.2, "n": 60},
                "us_test_belt|hdd_anom_7d|XNGUSD": {"verdict": "FAIL", "ic": 0.01, "n": 60},
                "us_test_belt|precip_anom_30d|CORN": {"verdict": UNMEASURED_V, "why": "no bars"}}
    monkeypatch.setattr(e5, "gain_tests", lambda *a, **k: dict(verdicts))
    calls: list[tuple[int, int]] = []

    def donor(p: Any, cands: list[Any], tested: int, now: Any) -> dict[str, Any]:
        calls.append((len(cands), tested))
        return {"donated": len(cands)}

    first = e5.run(paths, now=NOW, fetch=False, mint=lambda s: True, donor=donor)
    second = e5.run(paths, now=NOW, fetch=False, mint=lambda s: True, donor=donor)
    assert calls == [(1, 2)], "two identical passes charge the two tested cells ONCE"
    assert first["gains"]["charged"] == 2 and second["gains"]["charged"] == 0
    assert second["gains"]["unchanged_not_recharged"] == 2
    assert second["donation"]["donated"] == 0
    # a later pass that fetched new ERA5 days changes the data fingerprint: charged again
    e5.run(paths, now=NOW + timedelta(days=3), client_factory=_factory(FakeClient()),
           key_reader=lambda n: None, mint=lambda s: True, donor=donor)
    assert calls[-1] == (1, 2) and len(calls) == 2
    # and a spec change re-charges too
    monkeypatch.setattr(e5, "CELL_SPEC_VERSION", "era5-cell/test-bump")
    e5.run(paths, now=NOW + timedelta(days=3), fetch=False, mint=lambda s: True, donor=donor)
    assert len(calls) == 3

