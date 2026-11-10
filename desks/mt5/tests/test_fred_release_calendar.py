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


def _fred(names: dict[int, str], dates: dict[int, list[str]], status: int = 200):
    calls: list[str] = []

    def get(url: str) -> tuple[int | None, Any]:
        calls.append(url)
        rid = int(url.split("release_id=")[1].split("&")[0])
        if status != 200:
            return status, None
        if "/release/dates?" in url:
            return 200, {"release_dates": [{"release_id": rid, "date": d} for d in dates[rid]]}
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
                {101: ["2012-12-12", "2026-01-28", "2026-06-17", "2026-06-20", "2026-12-09"]})
    rep = frc.refresh(**_kw(tmp_path, get, [FOMC]))
    rows = _rows(tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz")
    assert [r["event_date"] for r in rows] == [
        "2026-01-28T19:00:00+00:00",          # 14:00 EST
        "2026-06-17T18:00:00+00:00",          # 14:00 EDT
        "2026-12-09T19:00:00+00:00"]
    assert [r["scheduled"] for r in rows] == [False, False, True]
    assert {r["currency"] for r in rows} == {"USD"} and all(r["timing_only"] for r in rows)
    fomc = rep["releases"]["fomc"]
    assert fomc["dropped"] == {"before_from": 1, "weekend": 1, "unreadable": 0}
    assert fomc["rows"] == 3 and fomc["scheduled_ahead"] == 1 and rep["unmeasured"] == []


def test_a_wrong_name_for_the_id_writes_nothing(tmp_path: Path) -> None:
    get = _fred({101: "Something Else Entirely"}, {101: ["2026-01-28"]})
    rep = frc.refresh(**_kw(tmp_path, get, [FOMC]))
    assert rep["unmeasured"] == ["fomc"] and "name" in rep["releases"]["fomc"]["status"]
    assert not (tmp_path / "cal").exists() and len(get.calls) == 1


def test_asked_once_a_day_and_the_key_never_reaches_the_report(tmp_path: Path) -> None:
    get = _fred({101: "FOMC Press Release"}, {101: ["2026-01-28"]})
    kw = _kw(tmp_path, get, [FOMC])
    frc.refresh(**kw)
    frc.refresh(**kw)
    assert len(get.calls) == 2                               # name + dates, once
    assert KEY not in (tmp_path / "r.json").read_text()
    frc.refresh(**{**kw, "today": date(2026, 11, 11)})
    assert len(get.calls) == 4                               # a new day asks again


def test_a_refusal_stops_every_release_for_the_day_and_keeps_the_old_file(tmp_path: Path) -> None:
    ppi = next(r for r in REG["releases"] if r["slug"] == "ppi")
    ok = _fred({101: "FOMC Press Release", 46: "Producer Price Index"},
               {101: ["2026-01-28"], 46: ["2026-01-14"]})
    frc.refresh(**_kw(tmp_path, ok, [FOMC, ppi]))
    before = (tmp_path / "cal" / "backfill_fredrel_fomc.jsonl.gz").read_bytes()
    no = _fred({}, {}, status=429)
    kw = {**_kw(tmp_path, no, [FOMC, ppi]), "today": date(2026, 11, 11)}
    rep = frc.refresh(**kw)
    assert len(no.calls) == 1 and rep["unmeasured"] == ["fomc", "ppi"]
    assert rep["hard_stop"] == 429
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
