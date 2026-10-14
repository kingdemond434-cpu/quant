"""TREASURY REFUNDING: QRA coupon sizes and guidance read by fixed code, surprise vs guidance.

  * only treasury.gov links whose text names a refunding statement are followed;
  * the release date, the first size per refunding tenor and the size guidance are read from the
    statement's own words, and a statement that says none of them is UNMEASURED, never zero;
  * a size change Treasury had guided toward is no surprise; one against guidance is;
  * the series holds each surprise POST_DAYS days from the release-day stamp, never past today;
  * cells exist only once two non-zero surprises of a signal are measured, sides fixed;
  * a pass reads statements through the collector's fence, caches them, and donates once.
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
import treasury_refunding as tr  # noqa: E402

INDEX = (b'<ul><li><a href="/news/press-releases/jy0001">Quarterly Refunding Statement of '
         b'Assistant Secretary</a></li><li><a href="https://evil.example/qrs">Quarterly '
         b'Refunding Statement</a></li><li><a href="/news/press-releases/jy0002">TBAC Minutes'
         b'</a></li><li><a href="https://home.treasury.gov/news/press-releases/jy0003">'
         b'<span>Refunding</span> Statement (May)</a></li></ul>')


def _statement(day: str, s3: int, s10: int, s30: int, guide: str) -> bytes:
    return (f"<html><body><p>{day}</p><h1>Quarterly Refunding Statement</h1>"
            f"<p>Treasury plans to auction ${s3} billion of 3-year notes, ${s10} billion of "
            f"10-year notes and ${s30} billion of 30-year bonds. The 5-year note is "
            f"$70 billion.</p><p>{guide}</p></body></html>").encode()


HOLD = ("Treasury anticipates maintaining nominal coupon and FRN auction sizes for at least "
        "the next several quarters.")
UP = "Treasury anticipates that it will need to increase nominal coupon auction sizes."
NONE = "Treasury will continue to monitor the market."


def test_only_treasury_statement_links_are_followed() -> None:
    got = tr.statement_links(INDEX, "https://home.treasury.gov/policy-issues/x")
    assert got == ["https://home.treasury.gov/news/press-releases/jy0001",
                   "https://home.treasury.gov/news/press-releases/jy0003"]


def test_the_statement_is_read_in_its_own_words() -> None:
    text = ec.page_text(_statement("May 1, 2024", 58, 42, 25, HOLD))
    st = tr.parse(text, "u", "seen", today=date(2026, 10, 14))
    assert st == {"date": "2024-05-01", "url": "u", "first_seen": "seen",
                  "sizes": {"3": 58.0, "10": 42.0, "30": 25.0}, "guidance": 0}
    assert tr.guidance(ec.page_text(_statement("May 1, 2024", 1, 1, 1, UP))) == 1
    assert tr.guidance(ec.page_text(_statement("May 1, 2024", 1, 1, 1, NONE))) is None
    assert tr.parse("no date here", "u", "s") is None


def test_a_guided_change_is_no_surprise_and_a_change_against_guidance_is() -> None:
    rows = [{"date": "2023-05-03", "sizes": {"3": 40, "10": 35, "30": 21}, "guidance": 0},
            {"date": "2023-08-02", "sizes": {"3": 42, "10": 38, "30": 23}, "guidance": 1},
            {"date": "2023-11-01", "sizes": {"3": 48, "10": 40, "30": 24}, "guidance": 0},
            {"date": "2024-01-31", "sizes": {"3": 52, "10": 42, "30": 25}, "guidance": None}]
    s = tr.surprises(rows)
    assert s[0]["size_surprise"] is None and s[0]["guidance_shift"] is None
    assert s[1]["size_surprise"] == pytest.approx(103 / 96 - 1, abs=1e-6) and s[1]["guidance_shift"] == 1
    assert s[2]["size_surprise"] == 0.0, "the August guidance said increases: priced"
    assert s[2]["guidance_shift"] == -1
    assert s[3]["size_surprise"] == pytest.approx(119 / 112 - 1, abs=1e-6), "guided 0, sizes rose"
    assert s[3]["guidance_shift"] is None, "no guidance read is UNMEASURED, not a shift"


def test_the_series_holds_each_surprise_from_its_release_stamp() -> None:
    scored = [{"date": "2026-10-01", "first_seen": "f", "size_surprise": 0.05,
               "guidance_shift": None}]
    rows = tr.series_rows(scored, today=date(2026, 10, 8))
    assert rows[0]["available_time"] == "2026-10-01T14:00:00+00:00"
    assert [r["size_surprise"] for r in rows] == [0.05] * tr.POST_DAYS + [0.0] * 3
    assert rows[0]["guidance_shift"] == "" and rows[-1]["guidance_shift"] == 0.0
    assert rows[-1]["available_time"].startswith("2026-10-08")


def test_cells_need_two_measured_surprises_and_carry_fixed_sides() -> None:
    one = [{"size_surprise": 0.05, "guidance_shift": 0.0}]
    assert tr.cells(one) == []
    two = [*one, {"size_surprise": -0.02, "guidance_shift": 1.0}]
    got = tr.cells(two, uni={"UST10Y": "bond", "USDJPY": "fx"})
    assert {(c["symbol"], c["params"]["side_when_high"]) for c in got} == {
        ("UST10Y", -1), ("USDJPY", 1)}
    assert all(c["params"]["signal"] == "size_surprise" for c in got)
    assert all(not c["gauntlet_bypass"] and c["lineage"]["operator"] == "fixed_rule"
               for c in got)


def test_a_pass_reads_caches_and_donates_once(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"),
                      ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")
    pages = {tr.INDEXES[0]: (b'<a href="/s1">Quarterly Refunding Statement</a>'
                             b'<a href="/s2">Quarterly Refunding Statement</a>'
                             b'<a href="/s3">Quarterly Refunding Statement</a>', ""),
             tr.INDEXES[1]: (b"", "UNREACHABLE:DNS_TIMEOUT"),
             "https://home.treasury.gov/s1": (_statement("May 3, 2023", 40, 35, 21, HOLD), ""),
             "https://home.treasury.gov/s2": (_statement("August 2, 2023", 42, 38, 23, UP), ""),
             "https://home.treasury.gov/s3": (_statement("November 1, 2023", 48, 40, 24,
                                                         HOLD), "")}
    calls: list[str] = []

    def fake_fetch(url: str, _src: str, **_kw: Any) -> tuple[bytes, str]:
        calls.append(url)
        return pages[url]
    import collector_lab
    monkeypatch.setattr(collector_lab, "fetch", fake_fetch)
    doc = tr.run(uni={"UST10Y": "bond"}, lane_ok=lambda s, f: True, today=date(2023, 11, 10))
    assert doc["state"] == "RAN" and doc["statements_on_record"] == 3
    assert doc["measured"] == {"size_surprise": 2, "guidance_shift": 2}
    # Guidance shifted twice (+1 then -1): two non-zero, so the guidance cell exists; size
    # surprised once (August, against May's hold) and was priced once (November), so it waits.
    assert doc["cells_total"] == 1 and doc["cells_donated"] == 1
    with (tmp_path / "series" / "treasury_refunding.csv").open() as fh:
        series = list(csv.DictReader(fh))
    assert series[-1]["available_time"].startswith("2023-11-10")
    calls.clear()
    again = tr.run(uni={"UST10Y": "bond"}, lane_ok=lambda s, f: True, today=date(2023, 11, 10))
    assert again["cells_donated"] == 0 and calls == [], \
        "statements are cached and each index is refreshed at most once per REFETCH_S"
    assert json.loads((tmp_path / "REPORT.json").read_text())["statements_read"] == 0


def test_a_pass_that_measured_nothing_says_unmeasured(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"),
                      ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")
    import collector_lab
    monkeypatch.setattr(collector_lab, "fetch", lambda url, _s, **_k: (b"<p>none</p>", ""))
    doc = tr.run(uni={}, lane_ok=lambda s, f: True)
    assert doc["state"] == "UNMEASURED" and "no refunding statement" in doc["why"]
    monkeypatch.setattr(collector_lab, "fetch", lambda url, _s, **_k: (b"", "REFUSED:x"))
    monkeypatch.setattr(tr, "REFETCH_S", 0.0)
    assert tr.run(uni={}, lane_ok=lambda s, f: True)["state"] == "DARK"
