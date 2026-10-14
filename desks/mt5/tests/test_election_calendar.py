"""ELECTION CALENDAR: vote dates read by fixed code, PIT series, pre-registered cells.

  * a date is accepted only near a NATIONAL-vote keyword in the page's language, in any of the
    four shapes (English day-month, month-day, Spanish, Japanese, ISO), and only the one date
    that reads as the vote date (local votes, by-elections, referendums, "results declared",
    "first sat" and "registration closes" are refused);
  * near-duplicate dates merge into one vote, confirmed only when a second page reads it, and
    a voided date never returns;
  * day D's row is stamped max(D - 1, confirmation) for a vote confirmed before it was held and
    D - 1 (flagged statutory_history) for history; nothing is written after today;
  * cells exist only with two confirmed votes, with the sides fixed by MECHANISMS;
  * a pass that measured nothing says UNMEASURED;
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
PAGE_ES = "La jornada electoral federal del 2 de junio de 2024 fue la más grande.".encode()


def test_only_dates_near_an_election_keyword_are_read() -> None:
    got = [e["date"] for e in ec.extract(ec.page_text(PAGE_EN), "en", today=date(2026, 10, 13))]
    assert got == ["2019-05-08", "2024-05-29"], "script text and the unrelated date are ignored"
    assert [e["date"] for e in ec.extract(ec.page_text(PAGE_JA), "ja")] == ["2024-10-27"]
    assert [e["date"] for e in ec.extract(ec.page_text(PAGE_ES), "es")] == ["2024-06-02"]
    assert ec.extract("no keyword here 8 May 2019", "en") == []


@pytest.mark.parametrize(("text", "lang"), [
    ("The Tokyo gubernatorial election was held on 7 July 2024.", "en"),
    ("The 2023 by-election was held on 23 April 2023 alongside the general election.", "en"),
    ("A referendum on the general election law was held on 17 October 2020.", "en"),
    ("東京都知事選挙 投票日 2024年7月7日", "ja"),
    ("第20回統一地方選挙 総選挙 投票日 2023年4月9日", "ja"),
    ("総選挙 投票日 2024年10月27日", "ja"),        # no house named
    ("La jornada electoral local del 4 de junio de 2023", "es"),
])
def test_votes_that_are_not_national_are_refused(text: str, lang: str) -> None:
    assert ec.extract(text, lang, today=date(2026, 10, 14)) == []


def test_only_the_vote_date_is_taken() -> None:
    """Audit must-fix 2 on #388: the probes that took the wrong date from a segment."""
    today = date(2026, 10, 14)
    seg = ("After the general election held on 29 May 2024, results were declared "
           "2 June 2024 and the new parliament first sat on 14 June 2024.")
    assert [e["date"] for e in ec.extract(seg, "en", today=today)] == ["2024-05-29"]
    assert ec.extract("For the general election, registration closes 14 October 2026.", "en",
                      today=today) == []
    assert ec.extract("The general election was announced on 20 January 2024.", "en",
                      today=today) == []
    assert ec.extract("衆議院 総選挙 公示 2024年10月15日", "ja", today=today) == []
    hc = "参議院議員通常選挙 2025年7月20日\uff08日\uff09投票"
    assert [e["date"] for e in ec.extract(hc, "ja", today=today)] == ["2025-07-20"]


def test_a_vote_is_confirmed_only_by_a_second_page_and_voids_stick() -> None:
    store: dict[str, Any] = {}
    assert ec.merge_events(store, "za", [{"date": "2024-05-29", "quote": "q"}], "u1", "t1") == 1
    assert ec.confirmed(store["za"]) == []
    assert ec.merge_events(store, "za", [{"date": "2024-05-29", "quote": "q"}], "u1", "t2") == 0
    assert ec.confirmed(store["za"]) == [], "the same page twice is not a second source"
    assert ec.merge_events(store, "za", [{"date": "2024-05-30", "quote": "q"},
                                         {"date": "2019-05-08", "quote": "q"}], "u2", "t3") == 1
    assert [(r["date"], r["first_seen"]) for r in store["za"]] == [("2019-05-08", "t3"),
                                                                 ("2024-05-29", "t1")]
    got = ec.confirmed(store["za"])
    assert [(r["date"], r["confirmed_at"]) for r in got] == [("2024-05-29", "t3")]
    assert ec.confirmed(store["za"], ["2024-05-28"]) == [], "a voided vote never returns"


def test_a_vote_seen_before_it_is_held_is_stamped_from_its_confirmation() -> None:
    """Audit must-fix 4 on #388: vote 10-20, confirmed 10-18 09:00."""
    ev = [{"date": "2026-10-20", "confirmed_at": "2026-10-18T09:00:00+00:00",
           "sources": {"a": "x", "b": "y"}}]
    rows = ec.series_rows(ev, "jp", today=date(2026, 10, 22))
    pre = [r for r in rows if r["pre_event"] == 1]
    assert len(pre) == ec.PRE_DAYS
    assert all(r["available_time"] >= "2026-10-18T09:00:00+00:00" for r in pre)
    assert {r["stamp_basis"] for r in pre} == {"first_sight"}
    assert rows[0]["vintage_id"] != "v1"


def test_rows_are_stamped_the_day_before_and_lit_only_in_their_window() -> None:
    ev = [{"date": "2024-05-29", "confirmed_at": "2026-10-13T00:00:00+00:00"}]
    rows = ec.series_rows(ev, "za", today=date(2024, 6, 10))
    by = {r["available_time"][:10]: r for r in rows}
    # The row for day D is stamped D - 1.
    assert by["2024-05-23"]["pre_event"] == 1 and by["2024-05-22"]["pre_event"] == 0
    assert by["2024-05-27"]["pre_event"] == 1 and by["2024-05-27"]["post_event"] == 0
    assert by["2024-05-28"]["post_event"] == 1 and by["2024-06-02"]["post_event"] == 0
    assert rows[-1]["available_time"][:10] == "2024-06-09", "nothing is written after today"
    assert by["2024-05-27"]["retrieval_time"].startswith("2026-10-13")
    assert by["2024-05-27"]["stamp_basis"] == "statutory_history"


def test_cells_need_two_votes_and_carry_the_fixed_sides() -> None:
    uni = {"USDZAR": "fx", "NZDUSD": "fx", "AUDNZD": "fx"}

    def ok(d: str) -> dict[str, Any]:
        return {"date": d, "sources": {"a": "t", "b": "t"}, "confirmed_at": "t"}
    assert ec.cells({"za": [ok("2024-05-29")]}, uni) == []
    assert ec.cells({"za": [ok("2019-05-08"), {"date": "2024-05-29"}]}, uni) == [], \
        "an unconfirmed vote does not count"
    rows = ec.cells({"za": [ok("2019-05-08"), ok("2024-05-29")],
                     "nz": [ok("2020-10-17"), ok("2023-10-14")]}, uni)
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
    monkeypatch.setattr(ec, "VOIDED", tmp_path / "ec" / "voided.json")
    monkeypatch.setattr(ec, "SOURCES", (("za", "https://elections.example.org/", "en"),
                                        ("za", "https://list.example.org/", "en"),
                                        ("jp", "https://senkyo.example.jp/", "ja"),
                                        ("jp", "https://list.example.jp/", "ja")))
    return tmp_path


def test_a_pass_writes_series_and_donates_each_cell_once(tmp_ec: Path) -> None:
    calls: list[str] = []

    def get(url: str) -> tuple[int, bytes]:
        calls.append(url)
        if url.endswith("robots.txt"):
            return 404, b""
        return 200, (PAGE_EN if ".org" in url else
                     PAGE_JA + "\n前回の衆議院議員総選挙 投票日 2021年10月31日".encode())
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


def test_a_pass_that_measured_nothing_says_unmeasured(tmp_ec: Path) -> None:
    """Audit must-fix 5 on #388: pages with no vote date, or no confirmed vote, are not RAN."""
    def get(url: str) -> tuple[int, bytes]:
        return (404, b"") if url.endswith("robots.txt") else (200, b"<p>nothing here</p>")
    doc = ec.run(get=get, resolve=lambda h: ["93.184.216.34"], uni={},
                 lane_ok=lambda s, f: True)
    assert doc["state"] == "UNMEASURED" and "no national vote date" in doc["why"]

    def one_page(url: str) -> tuple[int, bytes]:
        if url.endswith("robots.txt"):
            return 404, b""
        return 200, PAGE_EN if url.startswith("https://elections.") else b"<p>none</p>"
    import json as _json
    (tmp_ec / "ec" / "fetched.json").write_text(_json.dumps({}))
    doc = ec.run(get=one_page, resolve=lambda h: ["93.184.216.34"], uni={},
                 lane_ok=lambda s, f: True)
    assert doc["state"] == "UNMEASURED" and doc["countries"]["za"]["confirmed"] == 0


def test_the_conditioner_reads_the_series_point_in_time(tmp_ec: Path) -> None:
    """The family's own loader reads the file: stamp column present, both signals readable."""
    from mt5desk.family_exogenous_conditioner import conditioner
    ev = [{"date": f"{y}-05-29", "confirmed_at": "x"} for y in range(2010, 2025)]
    ec.write_series("za", ec.series_rows(ev, "za", today=date(2025, 1, 1)))
    s = conditioner("election_za", "pre_event", "level_z", root=tmp_ec / "series")
    assert s is not None and float(s.max()) > 1.0
