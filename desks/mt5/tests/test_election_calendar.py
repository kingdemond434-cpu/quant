"""ELECTION CALENDAR: vote dates read by fixed code, PIT series, pre-registered cells.

  * a date is accepted only near an election keyword in the page's language, in any of the
    four shapes (English day-month, month-day, Spanish, Japanese, ISO);
  * near-duplicate dates merge into one event, and the first sight is kept;
  * day D's row is stamped D - 1 and is 1 only inside its window; nothing is written after today;
  * cells exist only with two votes on record, with the sides fixed by MECHANISMS;
  * a pass fetches through the collector's fence, refreshes a page at most once per REFETCH_S,
    and donates each cell once.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import election_calendar as ec  # noqa: E402

PAGE_EN = (b"<html><head><title>x</title><script>var d='1 January 2001 general election';"
           b"</script></head><body><p>The 2019 general election was held on 8 May 2019.</p>"
           b"<p>The office opened on 3 March 2015.</p><table><tr><td>2024 general election"
           b"</td><td>May 29, 2024</td></tr></table></body></html>")
PAGE_JA = "第50回衆議院議員総選挙 投票日 2024年10月27日 (日)".encode()
PAGE_ES = "La jornada electoral del 2 de junio de 2024 fue la más grande.".encode()


def test_only_dates_near_an_election_keyword_are_read() -> None:
    got = [e["date"] for e in ec.extract(ec.page_text(PAGE_EN), "en", today=date(2026, 10, 13))]
    assert got == ["2019-05-08", "2024-05-29"], "script text and the unrelated date are ignored"
    assert [e["date"] for e in ec.extract(ec.page_text(PAGE_JA), "ja")] == ["2024-10-27"]
    assert [e["date"] for e in ec.extract(ec.page_text(PAGE_ES), "es")] == ["2024-06-02"]
    assert ec.extract("no keyword here 8 May 2019", "en") == []


def test_near_duplicates_merge_and_first_sight_is_kept() -> None:
    store: dict[str, Any] = {}
    assert ec.merge_events(store, "za", [{"date": "2024-05-29", "quote": "q"}], "u1", "t1") == 1
    assert ec.merge_events(store, "za", [{"date": "2024-05-30", "quote": "q"},
                                         {"date": "2019-05-08", "quote": "q"}], "u2", "t2") == 1
    assert [(r["date"], r["first_seen"]) for r in store["za"]] == [("2019-05-08", "t2"),
                                                                 ("2024-05-29", "t1")]


def test_rows_are_stamped_the_day_before_and_lit_only_in_their_window() -> None:
    ev = [{"date": "2024-05-29", "first_seen": "2026-10-13T00:00:00+00:00"}]
    rows = ec.series_rows(ev, "za", today=date(2024, 6, 10))
    by = {r["available_time"][:10]: r for r in rows}
    # The row for day D is stamped D - 1.
    assert by["2024-05-23"]["pre_event"] == 1 and by["2024-05-22"]["pre_event"] == 0
    assert by["2024-05-27"]["pre_event"] == 1 and by["2024-05-27"]["post_event"] == 0
    assert by["2024-05-28"]["post_event"] == 1 and by["2024-06-02"]["post_event"] == 0
    assert rows[-1]["available_time"][:10] == "2024-06-09", "nothing is written after today"
    assert by["2024-05-27"]["retrieval_time"].startswith("2026-10-13")


def test_cells_need_two_votes_and_carry_the_fixed_sides() -> None:
    uni = {"USDZAR": "fx", "NZDUSD": "fx", "AUDNZD": "fx"}
    assert ec.cells({"za": [{"date": "2024-05-29"}]}, uni) == []
    rows = ec.cells({"za": [{"date": "2019-05-08"}, {"date": "2024-05-29"}],
                     "nz": [{"date": "2020-10-17"}, {"date": "2023-10-14"}]}, uni)
    sides = {(r["symbol"], r["params"]["signal"]): r["params"]["side_when_high"] for r in rows}
    assert sides == {("USDZAR", "pre_event"): 1, ("USDZAR", "post_event"): -1,
                     ("NZDUSD", "pre_event"): -1, ("NZDUSD", "post_event"): 1,
                     ("AUDNZD", "pre_event"): 1, ("AUDNZD", "post_event"): -1}
    assert all(r["producer"] == "election_calendar" and r["family"] == "exogenous_conditioner"
               and r["params"]["source"].startswith("election_") for r in rows)
    assert len({r["cell_id"] for r in rows}) == len(rows)


@pytest.fixture()
def tmp_ec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, rel in {"STATE_DIR": "ec", "EVENTS": "ec/events.json", "FETCHED": "ec/fetched.json",
                      "SERIES_DIR": "series", "DONATE_DIR": "donate",
                      "REPORT": "reports/ELECTION_CALENDAR.json"}.items():
        monkeypatch.setattr(ec, name, tmp_path / rel)
    import collector_lab
    monkeypatch.setattr(collector_lab, "HOST_STATE", tmp_path / "hosts.json")
    monkeypatch.setattr(ec, "SOURCES", (("za", "https://elections.example.org/", "en"),
                                        ("jp", "https://senkyo.example.jp/", "ja")))
    return tmp_path


def test_a_pass_writes_series_and_donates_each_cell_once(tmp_ec: Path) -> None:
    calls: list[str] = []

    def get(url: str) -> tuple[int, bytes]:
        calls.append(url)
        if url.endswith("robots.txt"):
            return 404, b""
        return 200, (PAGE_EN if "elections" in url else
                     PAGE_JA + " 前回の総選挙 投票日 2021年10月31日".encode())
    uni = {"USDZAR": "fx", "USDJPY": "fx"}
    doc = ec.run(get=get, resolve=lambda h: ["93.184.216.34"], uni=uni,
                 lane_ok=lambda s, f: True, today=date(2026, 10, 13))
    assert doc["state"] == "RAN" and doc["countries"]["za"]["events"] == 2
    assert doc["countries"]["jp"]["events"] == 2 and doc["cells_donated"] == 4
    with (tmp_ec / "series" / "election_jp.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert sum(int(r["pre_event"]) for r in rows) == 2 * ec.PRE_DAYS
    donated = json.loads(next((tmp_ec / "donate").glob("discoveries_*.json")).read_text())
    assert {r["symbol"] for r in donated["discoveries"]} == {"USDZAR", "USDJPY"}
    n = len(calls)
    again = ec.run(get=get, resolve=lambda h: ["93.184.216.34"], uni=uni,
                   lane_ok=lambda s, f: True, today=date(2026, 10, 13))
    assert len(calls) == n and again["state"] == "FRESH" and again["cells_donated"] == 0


def test_an_unreachable_page_is_named_and_dark(tmp_ec: Path) -> None:
    doc = ec.run(get=lambda u: (503, b""), resolve=lambda h: ["93.184.216.34"], uni={},
                 lane_ok=lambda s, f: True)
    assert doc["state"] == "DARK"
    assert {p["status"] for p in doc["sources"]} == {"ROBOTS_UNAVAILABLE"}


def test_the_conditioner_reads_the_series_point_in_time(tmp_ec: Path) -> None:
    """The family's own loader reads the file: stamp column present, both signals readable."""
    from mt5desk.family_exogenous_conditioner import conditioner
    ev = [{"date": f"{y}-05-29", "first_seen": "x"} for y in range(2010, 2025)]
    ec.write_series("za", ec.series_rows(ev, "za", today=date(2025, 1, 1)))
    s = conditioner("election_za", "pre_event", "level_z", root=tmp_ec / "series")
    assert s is not None and float(s.max()) > 1.0
