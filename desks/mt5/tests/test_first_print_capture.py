"""first_print_capture: offline fixtures only -- no request leaves the test."""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import first_print_capture as fpc  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "first_prints"
KEY = "fixture-not-a-real-key-123"


def _grounds(tmp: Path) -> Path:
    real = json.loads(fpc.GROUNDS.read_text("utf-8"))
    keep = {"bls_payrolls", "bls_unemployment_rate", "census_retail_sales"}
    real["series"] = [r for r in real["series"] if r["id"] in keep]
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "grounds.json"
    p.write_text(json.dumps(real), "utf-8")
    return p


class Fake:
    """url -> bytes. Records every call so a test can see what was (not) requested."""

    def __init__(self, bls: str = "bls_v2_oct.json", robots: str = "User-agent: *\nAllow: /\n",
                 bls_error: int | None = None) -> None:
        self.bls, self.robots, self.bls_error = bls, robots, bls_error
        self.calls: list[tuple[str, bytes | None]] = []

    def __call__(self, url: str, data: bytes | None, headers: Any) -> bytes:
        self.calls.append((url, data))
        if url.endswith("/robots.txt"):
            return self.robots.encode()
        if "api.bls.gov" in url:
            if self.bls_error:
                raise urllib.error.HTTPError(url, self.bls_error, "x", {}, io.BytesIO())  # type: ignore[arg-type]
            return (FIX / self.bls).read_bytes()
        if "api.census.gov" in url:
            return (FIX / "census_marts.json").read_bytes()
        raise AssertionError(f"unexpected url {url}")


@pytest.fixture(autouse=True)
def _fresh_robots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fpc, "_ROBOTS", {})


def _run(tmp: Path, fake: Fake, now: datetime, key: str = KEY) -> dict[str, Any]:
    return fpc.run(grounds_path=_grounds(tmp), lake=tmp / "lake", report=tmp / "report.json",
                   fetch=fake, now=now, key_reader=lambda: (key, "BLS_API_KEY" if key else ""))


def _rows(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


# 2026-10-02 is a Friday; 13:00 UTC = 09:00 New York
T1 = datetime(2026, 10, 2, 13, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 6, 13, 5, tzinfo=UTC)      # Friday 08:05 ET -> before the 08:30 slot


def test_first_read_is_baseline_never_a_first_print(tmp_path: Path) -> None:
    doc = _run(tmp_path, Fake(), T1)
    lake = tmp_path / "lake" / "bls_payrolls"
    assert not (lake / "first_prints.jsonl").exists()
    assert {r["period"] for r in _rows(lake / "baseline.jsonl")} == {"2026-08", "2026-09"}
    assert doc["this_pass"]["first_prints"] == 0
    # M13 annual averages and the "-" missing value are never stored
    assert all(r["period"] != "2026-13" for r in _rows(lake / "baseline.jsonl"))
    assert not (tmp_path / "lake" / "bls_unemployment_rate" / "baseline.jsonl").read_text(
        "utf-8").count("2026-08")


def test_a_revision_never_overwrites_the_first_print(tmp_path: Path) -> None:
    _run(tmp_path, Fake(), T1)
    later = datetime(2026, 11, 6, 14, 0, tzinfo=UTC)
    _run(tmp_path, Fake("bls_v2_nov.json"), later)
    lake = tmp_path / "lake" / "bls_payrolls"
    fp = _rows(lake / "first_prints.jsonl")
    assert [(r["period"], r["value"], r["vintage"]) for r in fp] == [("2026-10", 159731.0, 1)]
    revs = _rows(lake / "revisions.jsonl")
    assert [(r["period"], r["previous_value"], r["value"]) for r in revs] == [
        ("2026-09", 159612.0, 159655.0)]
    frozen = (lake / "first_prints.jsonl").read_bytes()

    # next month the October print is revised: it lands in revisions, the first print is untouched
    rev = json.loads((FIX / "bls_v2_nov.json").read_text("utf-8"))
    rev["Results"]["series"][0]["data"][0]["value"] = "159690"
    (tmp_path / "rev.json").write_text(json.dumps(rev), "utf-8")
    fake = Fake()
    fake.bls = str(tmp_path / "rev.json")  # FIX / absolute path -> the absolute path
    _run(tmp_path, fake, later + timedelta(days=30))
    assert (lake / "first_prints.jsonl").read_bytes() == frozen
    revs = _rows(lake / "revisions.jsonl")
    assert revs[-1]["period"] == "2026-10" and revs[-1]["value"] == 159690.0
    assert revs[-1]["first_print"] == 159731.0 and revs[-1]["vintage"] == 2
    assert fpc.series_state(tmp_path / "lake", "bls_payrolls")["first"]["2026-10"] == 159731.0

    # the same value again is not a revision
    n = len(revs)
    _run(tmp_path, fake, later + timedelta(days=31))
    assert len(_rows(lake / "revisions.jsonl")) == n


def test_stamp_has_no_lookahead() -> None:
    # Friday 09:00 ET: today's 08:30 slot
    rel, basis = fpc.release_instant(datetime(2026, 11, 6, 14, 0, tzinfo=UTC), "08:30", "2026-10")
    assert rel == datetime(2026, 11, 6, 13, 30, tzinfo=UTC) and basis.startswith("scheduled")
    # Friday 08:05 ET: today's slot is in the future, so the previous weekday's (Thursday)
    rel, _ = fpc.release_instant(T2, "08:30", "2026-10")
    assert rel == datetime(2026, 11, 5, 13, 30, tzinfo=UTC)
    # Monday 06:00 ET: back over the weekend to Friday
    rel, _ = fpc.release_instant(datetime(2026, 11, 9, 11, 0, tzinfo=UTC), "08:30", "2026-10")
    assert rel == datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
    # a slot on or before the period's own end is impossible: the stamp is first sight
    seen = datetime(2026, 10, 30, 15, 0, tzinfo=UTC)
    assert fpc.release_instant(seen, "08:30", "2026-10") == (seen, "seen_at")

    # exhaustively: whatever weekday slot the true release was on, at or before first sight,
    # the stamp is never before it (no lookahead) and never after first sight
    start = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)
    for h in range(0, 24 * 14):
        seen = start + timedelta(hours=h, minutes=17)
        rel, _ = fpc.release_instant(seen, "08:30", "2026-09")
        assert rel <= seen
        for back in range(0, 12):
            d = (seen.astimezone(fpc.NY) - timedelta(days=back)).date()
            true = datetime(d.year, d.month, d.day, 8, 30, tzinfo=fpc.NY)
            if d.weekday() < 5 and true <= seen:
                assert rel >= true


def test_first_print_rows_carry_release_and_availability(tmp_path: Path) -> None:
    _run(tmp_path, Fake(), T1)
    _run(tmp_path, Fake("bls_v2_nov.json"), T2)
    for sid in ("bls_payrolls", "bls_unemployment_rate"):
        for r in _rows(tmp_path / "lake" / sid / "first_prints.jsonl"):
            rel, avail = fpc._t(r["release_at"]), fpc._t(r["available_at"])
            assert rel and avail and rel <= avail == fpc._t(r["seen_at"])
            assert rel.date() > fpc.period_end(r["period"])


def test_key_goes_to_v2_body_only_and_keyless_falls_back_to_v1(tmp_path: Path) -> None:
    fake = Fake()
    doc = _run(tmp_path, fake, T1)
    bls = [(u, d) for u, d in fake.calls if "publicAPI" in u]
    assert bls[0][0] == fpc.BLS_V2 and json.loads(bls[0][1] or b"{}")["registrationkey"] == KEY
    assert doc["publishers"]["bls"]["key_found_under"] == "BLS_API_KEY"
    assert KEY not in (tmp_path / "report.json").read_text("utf-8")
    assert not any(KEY in p.read_text("utf-8") for p in (tmp_path / "lake").rglob("*.json*"))

    fake2 = Fake()
    doc2 = _run(tmp_path / "k", fake2, T1, key="")
    bls2 = [(u, d) for u, d in fake2.calls if "publicAPI" in u]
    assert bls2[0][0] == fpc.BLS_V1 and "registrationkey" not in json.loads(bls2[0][1] or b"{}")
    assert doc2["publishers"]["bls"]["api"] == "v1_keyless"
    # keyless: the next pass inside 110 minutes does not spend another of v1's 25 a day
    fake3 = Fake()
    doc3 = _run(tmp_path / "k", fake3, T1 + timedelta(minutes=60), key="")
    assert doc3["publishers"]["bls"]["status"] == "NOT_DUE"
    assert not any("api.bls.gov" in u for u, _ in fake3.calls)


def test_robots_disallow_stops_the_data_request(tmp_path: Path) -> None:
    fake = Fake(robots="User-agent: *\nDisallow: /\n")
    doc = _run(tmp_path, fake, T1)
    assert doc["publishers"]["bls"]["status"] == "BLOCKED_ROBOTS"
    assert doc["publishers"]["census"]["status"] == "BLOCKED_ROBOTS"
    assert all(u.endswith("/robots.txt") for u, _ in fake.calls)


def test_429_holds_the_publisher_for_a_day(tmp_path: Path) -> None:
    doc = _run(tmp_path, Fake(bls_error=429), T1)
    assert doc["publishers"]["bls"]["status"] == "HARD_STOP"
    fake = Fake()
    doc = _run(tmp_path, fake, T1 + timedelta(hours=2))
    assert doc["publishers"]["bls"]["status"] == "HELD"
    assert not any("publicAPI" in u for u, _ in fake.calls)


def test_api_error_is_recorded_not_stored(tmp_path: Path) -> None:
    doc = _run(tmp_path, Fake("bls_error.json"), T1)
    assert doc["publishers"]["bls"]["status"] == "API_ERROR"
    assert "threshold" in doc["publishers"]["bls"]["errors"][0]
    assert not (tmp_path / "lake" / "bls_payrolls").exists()


def test_census_parse_skips_error_rows_and_unbuilt_publishers_are_never_fetched(
        tmp_path: Path) -> None:
    obs = fpc.parse_census((FIX / "census_marts.json").read_bytes(), "census_retail_sales")
    assert sorted((o.period, o.value) for o in obs) == [("2026-08", 728930.0),
                                                        ("2026-09", 731402.0)]
    fake = Fake()
    doc = _run(tmp_path, fake, T1)
    assert doc["publishers"]["dol"]["status"] == "NOT_BUILT"
    assert doc["publishers"]["bea"]["status"] == "NOT_BUILT"
    hosts = {u.split("/")[2] for u, _ in fake.calls}
    assert hosts <= {"api.bls.gov", "api.census.gov"}
    assert not any("stlouisfed" in u or "alfred" in u.lower() for u, _ in fake.calls)
    assert doc["no_fred_no_alfred"] is True and doc["money_path"] is False


def test_futures_state_reads_the_lake_when_alfred_is_not_fetched(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    from research import futures_state as fs
    _run(tmp_path, Fake(), T1)
    _run(tmp_path, Fake("bls_v2_nov.json"), T2)
    prints = fs.lake_first_prints("bls_payrolls", tmp_path / "lake")
    assert list(prints.columns) == ["period", "released", "value"]
    assert prints["value"].tolist() == [159731.0]          # the first print, not the baseline
    assert str(prints["released"].iloc[0].date()) == "2026-11-05"
    assert fs.lake_first_prints("no_such_series", tmp_path / "lake").empty
    text = fs.REGISTRY.read_text("utf-8")
    lake_ids = set(re.findall(r'"first_print_lake":\s*"([^"]+)"', text))
    grounds = {r["id"] for r in json.loads(fpc.GROUNDS.read_text("utf-8"))["series"]}
    assert lake_ids and lake_ids <= grounds
