"""FRED release dates -> calendar backfill rows. No network: the getter is a fake."""
from __future__ import annotations

import gzip
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fred_release_calendar as frc  # noqa: E402

REG = json.loads(frc.REGISTRY.read_text("utf-8"))
FOMC = next(r for r in REG["releases"] if r["slug"] == "fomc")
KEY = "k" * 32


def _fred(names: dict[int, str], dates: dict[int, list[str]], status: int = 200,
          no_data: tuple[str, ...] | None = None):
    calls: list[str] = []

    def get(url: str) -> tuple[int | None, Any]:
        calls.append(url)
        rid = int(url.split("release_id=")[1].split("&")[0])
        if status != 200:
            return status, None
        if "/release/dates?" in url:
            ds = dates[rid] if "no_data=true" in url else [
                d for d in dates[rid] if d not in (no_data or ())]
            return 200, {"release_dates": [{"release_id": rid, "date": d} for d in ds]}
        return 200, {"releases": [{"id": rid, "name": names[rid]}]}

    get.calls = calls  # type: ignore[attr-defined]
    return get


def _kw(tmp_path: Path, get: Any, rels: list[dict]) -> dict[str, Any]:
    return {"get": get, "registry": {"releases": rels}, "out": tmp_path / "cal",
            "report": tmp_path / "r.json", "today": date(2026, 11, 10), "key": KEY}


def _rows(p: Path) -> list[dict]:
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return [json.loads(x) for x in fh.read().splitlines()]


def test_the_statement_is_stamped_in_new_york_time_through_both_seasons(tmp_path: Path) -> None:
    get = _fred({101: "FOMC Press Release"},
                {101: ["2012-12-12", "2026-01-28", "2026-06-17", "2026-06-20", "2026-12-09"]},
                no_data=("2026-12-09",))
    rep = frc.refresh(**_kw(tmp_path, get, [FOMC]))
    rows = _rows(tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz")
    assert [r["event_date"] for r in rows] == [
        "2026-01-28T19:00:00+00:00",          # 14:00 EST
        "2026-06-17T18:00:00+00:00",          # 14:00 EDT
        "2026-12-09T19:00:00+00:00"]
    assert [r["scheduled"] for r in rows] == [False, False, True]
    assert {r["currency"] for r in rows} == {"USD"} and all(r["timing_only"] for r in rows)
    fomc = rep["releases"]["fomc"]
    assert fomc["dropped"] == {"before_from": 1, "weekend": 1, "unreadable": 0,
                               "past_no_data": 0}
    assert all(r["time_basis"].startswith("unverified convention") for r in rows)
    assert fomc["rows"] == 3 and fomc["scheduled_ahead"] == 1 and rep["unmeasured"] == []


def test_a_wrong_name_for_the_id_writes_nothing(tmp_path: Path) -> None:
    get = _fred({101: "Something Else Entirely"}, {101: ["2026-01-28"]})
    rep = frc.refresh(**_kw(tmp_path, get, [FOMC]))
    assert rep["unmeasured"] == ["fomc"] and "name" in rep["releases"]["fomc"]["status"]
    assert not (tmp_path / "cal").exists() and len(get.calls) == 1


def test_a_past_date_with_no_data_is_left_out_and_counted(tmp_path: Path) -> None:
    get = _fred({101: "FOMC Press Release"},
                {101: ["2026-01-28", "2026-03-18", "2026-12-09"]},
                no_data=("2026-03-18", "2026-12-09"))        # one postponed day, one future
    rep = frc.refresh(**_kw(tmp_path, get, [FOMC]))
    rows = _rows(tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz")
    assert [r["event_date"][:10] for r in rows] == ["2026-01-28", "2026-12-09"]
    assert rep["releases"]["fomc"]["dropped"]["past_no_data"] == 1


def test_a_release_that_is_really_daily_loads_writes_nothing(tmp_path: Path) -> None:
    from datetime import timedelta
    days = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(700)]
    ok = _fred({101: "FOMC Press Release"},
               {101: [f"{y}-{m:02d}-15" for y in (2024, 2025) for m in range(1, 9)]})
    rep = frc.refresh(**_kw(tmp_path, ok, [FOMC]))
    fomc = rep["releases"]["fomc"]
    assert fomc["per_year_ok"] and fomc["typical_year"] <= 8 and fomc["per_year"]["2025"] <= 8
    assert fomc["off_usual_weekday"] > 0                     # the 15th is not always Tue/Wed
    bad = _fred({101: "FOMC Press Release"}, {101: days})
    rep = frc.refresh(**{**_kw(tmp_path, bad, [FOMC]), "today": date(2026, 11, 11)})
    assert rep["unmeasured"] == ["fomc"] and "not used" in rep["releases"]["fomc"]["status"]
    assert not (tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz").exists()
    gone = rep["removed"][0]                                 # the drop is named, with its size
    assert gone["release"] == "fomc" and gone["rows_removed"] == fomc["rows"] > 0
    assert gone["date"] == "2026-11-11" and rep["rows_total"] == 0


def test_asked_once_a_day_and_the_key_never_reaches_the_report(tmp_path: Path) -> None:
    get = _fred({101: "FOMC Press Release"}, {101: ["2026-01-28"]})
    kw = _kw(tmp_path, get, [FOMC])
    frc.refresh(**kw)
    frc.refresh(**kw)
    assert len(get.calls) == 3                               # name + two date lists, once
    assert KEY not in (tmp_path / "r.json").read_text()
    frc.refresh(**{**kw, "today": date(2026, 11, 11)})
    assert len(get.calls) == 6                               # a new day asks again


def test_a_refusal_stops_every_release_for_the_day_and_keeps_the_old_file(tmp_path: Path) -> None:
    ppi = next(r for r in REG["releases"] if r["slug"] == "ppi")
    ok = _fred({101: "FOMC Press Release", 46: "Producer Price Index"},
               {101: ["2026-01-28"], 46: ["2026-01-14"]})
    frc.refresh(**_kw(tmp_path, ok, [FOMC, ppi]))
    before = (tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz").read_bytes()
    no = _fred({}, {}, status=429)
    kw = {**_kw(tmp_path, no, [FOMC, ppi]), "today": date(2026, 11, 11)}
    rep = frc.refresh(**kw)
    assert len(no.calls) == 1 and rep["unmeasured"] == [] and rep["stale"] == ["fomc", "ppi"]
    assert rep["hard_stop"] == 429 and rep["releases"]["fomc"]["stale_days"] == 1
    assert rep["rows_total"] == 2                            # the files are still being read
    frc.refresh(**kw)
    assert len(no.calls) == 1                                # not asked again that day
    assert (tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz").read_bytes() == before


def test_no_key_is_unmeasured_and_the_registry_does_not_repeat_first_print_releases(
        tmp_path: Path) -> None:
    get = _fred({}, {})
    rep = frc.refresh(**{**_kw(tmp_path, get, [FOMC]), "key": ""})
    assert rep["unmeasured"] == ["fomc"] and not get.calls
    # payrolls, CPI, claims, retail sales, PCE, industrial production and JOLTS already come
    # from first prints; a second row per release would double the event
    assert not {10, 50, 54, 9, 13, 180, 192} & {int(r["rid"]) for r in REG["releases"]}
    assert "intelligence" not in frc.CALENDAR_BACKFILL.parts


def test_central_bank_meeting_days_from_their_own_pages(tmp_path: Path) -> None:
    from datetime import datetime as dt
    reg = json.loads(frc.MEETINGS.read_text("utf-8"))
    rep = frc.write_meetings(registry=reg, out=tmp_path, today=date(2026, 11, 10))
    assert rep["banks"]["boj"]["status"] == "ok" and rep["banks"]["boe"]["status"] == "ok"
    assert [u["bank"] for u in rep["unmeasured"]] == ["ECB"]          # nothing written for it
    assert not list(tmp_path.glob("*ecb*"))
    boj = _rows(tmp_path / "backfill_cbmeet_boj.jsonl.gz")
    per_year: dict[int, int] = {}
    for r in boj:
        per_year[int(r["event_date"][:4])] = per_year.get(int(r["event_date"][:4]), 0) + 1
        assert dt.fromisoformat(r["event_date"]).weekday() < 5 and r["currency"] == "JPY"
    assert all(per_year[y] in (8, 9) for y in range(2016, 2028))       # 2020 had extra meetings
    assert boj[0]["event_date"] == "2015-01-21T03:00:00+00:00"          # 12:00 Tokyo, no DST
    assert sum(1 for r in boj if r.get("single_day_meeting")) == 4
    boe = _rows(tmp_path / "backfill_cbmeet_boe.jsonl.gz")
    stamps = {r["event_date"][:10]: r["event_date"][11:16] for r in boe}
    assert stamps["2026-06-18"] == "11:00" and stamps["2026-12-17"] == "12:00"  # BST vs GMT
    assert all("12 noon" in r["time_basis"] for r in boe)
    assert all(r["timing_only"] and r["page_read"] == "2026-11-10" for r in boj + boe)
    assert rep["banks"]["boj"]["scheduled_ahead"] == 9                  # Dec 2026 + all 2027
