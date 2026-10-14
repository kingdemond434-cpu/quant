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
from datetime import UTC, date, datetime
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

INDEX = (
    b'<ul><li><a href="/news/press-releases/jy0001">Quarterly Refunding Statement of '
    b'Assistant Secretary</a></li><li><a href="https://evil.example/qrs">Quarterly '
    b'Refunding Statement</a></li><li><a href="/news/press-releases/jy0002">TBAC Minutes'
    b'</a></li><li><a href="https://home.treasury.gov/news/press-releases/jy0003">'
    b"<span>Refunding</span> Statement (May)</a></li></ul>"
)


def _statement(day: str, s3: int, s10: int, s30: int, guide: str) -> bytes:
    return (
        f"<html><body><p>{day}</p><h1>Quarterly Refunding Statement</h1>"
        f"<p>Treasury plans to auction ${s3} billion of 3-year notes, ${s10} billion of "
        f"10-year notes and ${s30} billion of 30-year bonds. The 5-year note is "
        f"$70 billion.</p><p>{guide}</p></body></html>"
    ).encode()


HOLD = (
    "Treasury anticipates maintaining nominal coupon and FRN auction sizes for at least "
    "the next several quarters."
)
UP = "Treasury anticipates that it will need to increase nominal coupon auction sizes."
NONE = "Treasury will continue to monitor the market."


def test_only_treasury_statement_links_are_followed() -> None:
    got = tr.statement_links(INDEX, "https://home.treasury.gov/policy-issues/x")
    assert got == [
        "https://home.treasury.gov/news/press-releases/jy0001",
        "https://home.treasury.gov/news/press-releases/jy0003",
    ]


def test_the_statement_is_read_in_its_own_words() -> None:
    text = ec.page_text(_statement("May 1, 2024", 58, 42, 25, HOLD))
    st = tr.parse(text, "u", "seen", today=date(2026, 10, 14))
    assert st == {
        "date": "2024-05-01",
        "url": "u",
        "first_seen": "seen",
        "sizes": {"3": 58.0, "10": 42.0, "30": 25.0},
        "guidance": 0,
    }
    assert tr.guidance(ec.page_text(_statement("May 1, 2024", 1, 1, 1, UP))) == 1
    assert tr.guidance(ec.page_text(_statement("May 1, 2024", 1, 1, 1, NONE))) is None
    assert tr.parse("no date here", "u", "s") is None


def test_a_guided_change_is_no_surprise_and_a_change_against_guidance_is() -> None:
    rows = [
        {"date": "2023-05-03", "sizes": {"3": 40, "10": 35, "30": 21}, "guidance": 0},
        {"date": "2023-08-02", "sizes": {"3": 42, "10": 38, "30": 23}, "guidance": 1},
        {"date": "2023-11-01", "sizes": {"3": 48, "10": 40, "30": 24}, "guidance": 0},
        {"date": "2024-01-31", "sizes": {"3": 52, "10": 42, "30": 25}, "guidance": None},
    ]
    s = tr.surprises(rows)
    assert s[0]["size_surprise"] is None and s[0]["guidance_shift"] is None
    assert s[1]["size_surprise"] == pytest.approx(103 / 96 - 1, abs=1e-6)
    assert s[1]["guidance_shift"] == 1
    assert tr.surprises([]) == []
    assert s[2]["size_surprise"] == 0.0, "the August guidance said increases: priced"
    assert s[2]["guidance_shift"] == -1
    assert s[3]["size_surprise"] == pytest.approx(119 / 112 - 1, abs=1e-6), "guided 0, sizes rose"
    assert s[3]["guidance_shift"] is None, "no guidance read is UNMEASURED, not a shift"


def test_the_series_holds_each_surprise_from_its_release_stamp() -> None:
    scored = [
        {
            "date": "2026-10-01",
            "first_seen": "2026-12-01T00:00:00+00:00",
            "size_surprise": 0.05,
            "guidance_shift": None,
        }
    ]
    rows = tr.series_rows(
        scored, today=date(2026, 10, 8), measured_until=datetime(2026, 12, 1, tzinfo=UTC)
    )
    assert rows[0]["available_time"] == "2026-10-01T14:00:00+00:00"
    assert rows[0]["stamp_basis"] == "published_history" and rows[0]["vintage_id"] != "v1"
    assert [r["size_surprise"] for r in rows] == [0.05] * tr.POST_DAYS + [0.0] * 3
    assert rows[0]["guidance_shift"] == "" and rows[-1]["guidance_shift"] == 0.0
    assert rows[-1]["available_time"].startswith("2026-10-08")


def test_cells_need_two_measured_surprises_and_carry_fixed_sides() -> None:
    one = [{"size_surprise": 0.05, "guidance_shift": 0.0}]
    assert tr.cells(one) == []
    two = [*one, {"size_surprise": -0.02, "guidance_shift": 1.0}]
    got = tr.cells(two, uni={"UST10Y": "bond", "USDJPY": "fx"})
    assert {(c["symbol"], c["params"]["side_when_high"]) for c in got} == {
        ("UST10Y", -1),
        ("USDJPY", 1),
    }
    assert all(c["params"]["signal"] == "size_surprise" for c in got)
    assert all(not c["gauntlet_bypass"] and c["lineage"]["operator"] == "fixed_rule" for c in got)


def test_a_pass_reads_caches_and_donates_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"), ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")
    pages = {
        tr.INDEXES[0]: (
            b'<a href="/s1">Quarterly Refunding Statement</a>'
            b'<a href="/s2">Quarterly Refunding Statement</a>'
            b'<a href="/s3">Quarterly Refunding Statement</a>',
            "",
        ),
        tr.INDEXES[1]: (b"", "UNREACHABLE:DNS_TIMEOUT"),
        "https://home.treasury.gov/s1": (_statement("May 3, 2023", 40, 35, 21, HOLD), ""),
        "https://home.treasury.gov/s2": (_statement("August 2, 2023", 42, 38, 23, UP), ""),
        "https://home.treasury.gov/s3": (_statement("November 1, 2023", 48, 40, 24, HOLD), ""),
    }
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
    assert again["cells_donated"] == 0 and calls == [], (
        "statements are cached and each index is refreshed at most once per REFETCH_S"
    )
    assert json.loads((tmp_path / "REPORT.json").read_text())["statements_read"] == 0


def test_a_pass_that_measured_nothing_says_unmeasured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"), ("DONATE_DIR", "donate")):
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


def test_a_statement_read_late_is_stamped_from_its_first_sight() -> None:
    """Audit must-fix 5 on #394: first read 3 days after the release, inside its hold."""
    scored = [
        {
            "date": "2026-10-01",
            "first_seen": "2026-10-04T09:00:00+00:00",
            "size_surprise": 0.05,
            "guidance_shift": 1.0,
        }
    ]
    rows = tr.series_rows(scored, today=date(2026, 10, 8))
    held = [r for r in rows if r["size_surprise"] == 0.05]
    assert len(held) == tr.POST_DAYS
    assert all(r["available_time"] >= "2026-10-04T09:00:00+00:00" for r in held)
    assert {r["stamp_basis"] for r in held} == {"first_sight"}
    again = tr.series_rows([{**scored[0], "size_surprise": 0.06}], today=date(2026, 10, 8))
    assert again[0]["vintage_id"] != rows[0]["vintage_id"], "a re-read is a revision"


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury does not anticipate needing to increase nominal coupon or FRN auction sizes "
            "for at least the next several quarters.",
            0,
        ),
        (
            "Treasury anticipates maintaining nominal coupon and FRN auction sizes for at "
            "least the "
            "next several quarters. Treasury will increase the 5-year TIPS auction sizes.",
            0,
        ),
        ("Treasury will increase TIPS auction sizes.", None),
        ("Treasury anticipates that it will need to increase nominal coupon auction sizes.", 1),
        (
            "Treasury anticipates maintaining nominal coupon auction sizes; Treasury plans to "
            "increase nominal coupon auction sizes.",
            None,
        ),
    ],
)
def test_guidance_reads_nominal_coupons_and_negation(text: str, want: int | None) -> None:
    """Audit must-fixes 1 and 2 on #394."""
    assert tr.guidance(text) == want


def test_sizes_come_from_the_refunding_list_only() -> None:
    """Audit must-fix 4 on #394: an earlier reopening sentence never sets a tenor."""
    text = (
        "Treasury will auction a $39 billion 10-year note reopening next week.\n"
        "The securities are: a 3-year note in the amount of $58 billion, a 10-year note in "
        "the amount of $42 billion, and a 30-year bond in the amount of $25 billion."
    )
    assert tr.sizes(text) == {"3": 58.0, "10": 42.0, "30": 25.0}
    assert tr.sizes("Treasury will auction a $39 billion 10-year note reopening.") == {}


def test_an_unreadable_prior_guidance_leaves_the_size_surprise_unmeasured() -> None:
    """Audit must-fix 3 on #394."""
    s = tr.surprises(
        [
            {"date": "2024-01-31", "sizes": {"3": 52}, "guidance": None},
            {"date": "2024-05-01", "sizes": {"3": 54}, "guidance": 0},
        ]
    )
    assert s[1]["size_surprise"] is None and s[1]["guidance_shift"] is None


def test_a_day_nobody_looked_at_is_blank_never_zero() -> None:
    """Audit must-fix on #394 v2: indexes unreachable since the May statement, today 09-01."""
    scored = [
        {
            "date": "2024-05-01",
            "first_seen": "2024-05-01T15:00:00+00:00",
            "size_surprise": 0.05,
            "guidance_shift": 0.0,
        }
    ]
    rows = tr.series_rows(
        scored,
        today=date(2024, 9, 1),
        measured_until=datetime(2024, 6, 1, 9, tzinfo=UTC),
        now=datetime(2024, 9, 1, 10, tzinfo=UTC),
    )
    by_day = {r["published_time"][:10]: r for r in rows}
    assert by_day["2024-05-20"]["size_surprise"] == 0.0, "read the index after it: none"
    for day in ("2024-07-31", "2024-09-01"):
        assert by_day[day]["size_surprise"] == "" and by_day[day]["guidance_shift"] == ""
        assert by_day[day]["stamp_basis"] == tr.UNMEASURED
    blind = tr.series_rows(scored, today=date(2024, 9, 1))
    assert all(r["size_surprise"] == "" for r in blind[tr.POST_DAYS :]), "never read: blank"
    today_row = tr.series_rows(
        scored,
        today=date(2024, 9, 1),
        measured_until=datetime(2024, 9, 1, 12, tzinfo=UTC),
        now=datetime(2024, 9, 1, 10, tzinfo=UTC),
    )[-1]
    assert today_row["size_surprise"] == "", "today's 14:00 row is not published at 10:00"


def test_a_pass_with_unreachable_indexes_writes_no_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"), ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "statements.json").write_text(
        json.dumps(
            {
                "u": {
                    "date": "2024-05-01",
                    "first_seen": "2024-05-01T15:00:00+00:00",
                    "sizes": {"3": 58},
                    "guidance": 0,
                }
            }
        )
    )
    import collector_lab

    monkeypatch.setattr(
        collector_lab, "fetch", lambda url, _s, **_k: (b"", "UNREACHABLE:DNS_TIMEOUT")
    )
    doc = tr.run(uni={}, lane_ok=lambda s, f: True, today=date(2024, 9, 1))
    assert doc["measured_until"] is None and doc["rows_unmeasured"] == doc["rows"] - tr.POST_DAYS
    with (tmp_path / "series" / "treasury_refunding.csv").open() as fh:
        assert {r["size_surprise"] for r in csv.DictReader(fh)} == {""}


def test_a_missing_first_read_fails_closed() -> None:
    scored = [
        {"date": "2026-10-01", "size_surprise": 0.05, "guidance_shift": 1.0},
        {
            "date": "2026-10-20",
            "first_seen": "garbage",
            "size_surprise": 0.02,
            "guidance_shift": 0.0,
        },
    ]
    rows = tr.series_rows(
        scored, today=date(2026, 10, 22), measured_until=datetime(2026, 11, 1, tzinfo=UTC)
    )
    held = [r for r in rows if r["stamp_basis"] == "unstamped"]
    assert len(held) == tr.POST_DAYS + 3
    assert all(r["size_surprise"] == "" and r["guidance_shift"] == "" for r in held)


def test_each_row_is_vintaged_by_its_own_statement() -> None:
    a = {
        "date": "2026-01-01",
        "first_seen": "2026-01-01T15:00:00+00:00",
        "size_surprise": 0.05,
        "guidance_shift": 0.0,
    }
    b = {
        "date": "2026-04-01",
        "first_seen": "2026-04-01T15:00:00+00:00",
        "size_surprise": 0.02,
        "guidance_shift": 1.0,
    }
    end = datetime(2026, 12, 1, tzinfo=UTC)
    one = tr.series_rows([a], today=date(2026, 1, 3), measured_until=end)
    two = tr.series_rows([a, b], today=date(2026, 4, 3), measured_until=end)
    assert one[0]["vintage_id"] == two[0]["vintage_id"], "a new quarter never re-vintages"
    assert two[-1]["vintage_id"] != two[0]["vintage_id"]


def test_a_guided_increase_that_did_not_come_is_a_surprise() -> None:
    s = tr.surprises(
        [
            {"date": "2024-01-31", "sizes": {"3": 50}, "guidance": 0},
            {"date": "2024-05-01", "sizes": {"3": 55}, "guidance": 1},
            {"date": "2024-07-31", "sizes": {"3": 55}, "guidance": 0},
        ]
    )
    assert s[1]["size_surprise"] == pytest.approx(0.1, abs=1e-6)
    assert s[2]["size_surprise"] == pytest.approx(-0.1, abs=1e-6), "one typical step short"


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury anticipates maintaining nominal coupon and FRN auction sizes and will "
            "increase "
            "the 5-year TIPS auction sizes.",
            0,
        ),
        ("Treasury cannot foresee a need to increase nominal coupon auction sizes.", 0),
        ("Treasury is unlikely to increase nominal coupon auction sizes.", 0),
        ("Treasury never plans to cut nominal coupon auction sizes.", 0),
        ("Treasury believes increases to nominal coupon auction sizes will not be needed.", 0),
        ("Treasury will not only maintain but will increase nominal coupon auction sizes.", 1),
    ],
)
def test_guidance_follow_ups(text: str, want: int | None) -> None:
    """Audit #394 v2: TIPS behind a bare "and", wider negation, "not only"."""
    assert tr.guidance(text) == want


def test_sizes_skip_reopenings_and_misattached_amounts() -> None:
    same = (
        "The securities are a $58 billion 3-year note, a $42 billion 10-year note and a "
        "$25 billion 30-year bond. The $39 billion 10-year note reopening settles later."
    )
    assert tr.sizes(same) == {"3": 58.0, "10": 42.0, "30": 25.0}
    before = (
        "Treasury will reopen the $39 billion 10-year note and the $22 billion 30-year "
        "bond.\nThe refunding: a 3-year note in the amount of $58 billion, a 10-year note "
        "in the amount of $42 billion, and a 30-year bond in the amount of $25 billion."
    )
    assert tr.sizes(before) == {"3": 58.0, "10": 42.0, "30": 25.0}
    assert tr.sizes(
        "Treasury will sell a 3-year note, a 5-year note, and a $42 billion "
        "10-year note and a $25 billion 30-year bond."
    ) == {"10": 42.0, "30": 25.0}


def test_the_missed_step_is_measured_from_earlier_quarters_only() -> None:
    """Audit must-fix on #394 v3: later +50% quarters must not re-score July 2024."""
    base = [
        {"date": "2024-01-31", "sizes": {"3": 50}, "guidance": 0},
        {"date": "2024-05-01", "sizes": {"3": 55}, "guidance": 1},
        {"date": "2024-07-31", "sizes": {"3": 55}, "guidance": 0},
    ]
    later = [
        *base,
        {"date": "2024-10-30", "sizes": {"3": 82.5}, "guidance": 0},
        {"date": "2025-02-05", "sizes": {"3": 123.75}, "guidance": 0},
    ]
    end = datetime(2026, 1, 1, tzinfo=UTC)
    a, b = tr.surprises(base), tr.surprises(later)
    assert a[2]["size_surprise"] == b[2]["size_surprise"] == pytest.approx(-0.1, abs=1e-6)
    ra = tr.series_rows(a, today=date(2024, 8, 1), measured_until=end)
    rb = tr.series_rows(b, today=date(2024, 8, 1), measured_until=end)
    assert [r["vintage_id"] for r in ra] == [r["vintage_id"] for r in rb]
    first = tr.surprises(
        [
            {"date": "2024-01-31", "sizes": {"3": 50}, "guidance": 1},
            {"date": "2024-05-01", "sizes": {"3": 50}, "guidance": 0},
        ]
    )
    assert first[1]["size_surprise"] is None, "no earlier move measured: UNMEASURED"


@pytest.mark.parametrize("why", ["HTTP_404", "GATED", "ROBOTS", None])
def test_a_listed_statement_never_read_blocks_every_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, why: str | None
) -> None:
    """Audit must-fix on #394 v3: a refused or undated listed statement left 0.0 behind."""
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"), ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")
    pages = {
        tr.INDEXES[0]: (
            b'<a href="/s1">Quarterly Refunding Statement</a>'
            b'<a href="/s2">Quarterly Refunding Statement</a>',
            "",
        ),
        tr.INDEXES[1]: (b"", ""),
        "https://home.treasury.gov/s1": (_statement("May 1, 2026", 58, 42, 25, HOLD), ""),
        "https://home.treasury.gov/s2": (
            (b"", why) if why else (b"<p>no date on this page</p>", "")
        ),
    }
    import collector_lab

    monkeypatch.setattr(collector_lab, "fetch", lambda url, _s, **_k: pages[url])
    doc = tr.run(uni={}, lane_ok=lambda s, f: True, today=date(2026, 8, 10))
    assert doc["measured_until"] is not None
    assert doc["blocking_zeros"] == [
        {"url": "https://home.treasury.gov/s2", "from": None, "to": None}
    ], "one dated neighbour cannot orient it"
    with (tmp_path / "series" / "treasury_refunding.csv").open() as fh:
        rows = {r["published_time"][:10]: r for r in csv.DictReader(fh)}
    assert rows["2026-08-05"]["size_surprise"] == ""
    assert rows["2026-08-05"]["stamp_basis"] == tr.UNMEASURED
    calls: list[str] = []

    def counting(url: str, _s: str, **_k: Any) -> tuple[bytes, str]:
        calls.append(url)
        return pages[url]

    monkeypatch.setattr(collector_lab, "fetch", counting)
    tr.run(uni={}, lane_ok=lambda s, f: True, today=date(2026, 8, 10))
    assert "https://home.treasury.gov/s2" not in calls, "retried once per REFETCH_S, not hammered"
    monkeypatch.setattr(tr, "REFETCH_S", 0.0)
    pages["https://home.treasury.gov/s2"] = (_statement("August 5, 2026", 58, 42, 25, HOLD), "")
    again = tr.run(uni={}, lane_ok=lambda s, f: True, today=date(2026, 8, 10))
    assert again["blocking_zeros"] == [] and again["measured_until"] is not None
    with (tmp_path / "series" / "treasury_refunding.csv").open() as fh:
        assert {
            r["size_surprise"]
            for r in csv.DictReader(fh)
            if r["published_time"][:10] == "2026-07-01"
        } == {"0.0"}


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury will increase nominal coupon auction sizes because it can no longer rely on "
            "bills.",
            1,
        ),
        (
            "Treasury will increase nominal coupon auction sizes, since bills alone cannot "
            "absorb any "
            "increase.",
            1,
        ),
        ("Treasury anticipates increasing nominal coupon auction sizes.", 1),
        ("Treasury does not anticipate needing to increase nominal coupon auction sizes.", 0),
    ],
)
def test_negation_binds_to_the_guided_verb(text: str, want: int) -> None:
    assert tr.guidance(text) == want


def test_a_list_sentence_that_mentions_a_reopening_keeps_its_list() -> None:
    text = (
        "Treasury will sell a $58 billion 3-year note, a $42 billion 10-year note, the "
        "$39 billion 10-year reopening, and a $25 billion 30-year bond."
    )
    assert tr.sizes(text) == {"3": 58.0, "10": 42.0, "30": 25.0}


def _runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, sub in (("STATE_DIR", "state"), ("SERIES_DIR", "series"), ("DONATE_DIR", "donate")):
        monkeypatch.setattr(tr, name, tmp_path / sub)
    monkeypatch.setattr(tr, "STATEMENTS", tmp_path / "state" / "statements.json")
    monkeypatch.setattr(tr, "FETCHED", tmp_path / "state" / "fetched.json")
    monkeypatch.setattr(tr, "REPORT", tmp_path / "REPORT.json")


@pytest.mark.parametrize("descending", [False, True])
def test_an_unread_statement_blanks_only_the_dates_its_neighbours_allow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, descending: bool
) -> None:
    """Audit should-fix on #394 v4: one permanent 404 blanked the whole history."""
    _runner(tmp_path, monkeypatch)
    order = ["/s1", "/s2", "/s3", "/s4"]
    if descending:
        order.reverse()
    index = b"".join(f'<a href="{u}">Quarterly Refunding Statement</a>'.encode() for u in order)
    home = "https://home.treasury.gov"
    pages = {
        tr.INDEXES[0]: (index, ""),
        tr.INDEXES[1]: (b"", ""),
        f"{home}/s1": (_statement("February 1, 2025", 58, 42, 25, HOLD), ""),
        f"{home}/s2": (_statement("May 6, 2025", 58, 42, 25, HOLD), ""),
        f"{home}/s3": (b"", "HTTP_404"),
        f"{home}/s4": (_statement("November 4, 2025", 58, 42, 25, HOLD), ""),
    }
    import collector_lab

    monkeypatch.setattr(collector_lab, "fetch", lambda url, _s, **_k: pages[url])
    doc = tr.run(uni={}, lane_ok=lambda s, f: True, today=date(2025, 12, 1))
    assert doc["blocking_zeros"] == [
        {"url": f"{home}/s3", "from": "2025-05-06", "to": "2025-11-04"}
    ]
    with (tmp_path / "series" / "treasury_refunding.csv").open() as fh:
        rows = {r["published_time"][:10]: r for r in csv.DictReader(fh)}
    assert rows["2025-03-01"]["size_surprise"] == "0.0", "before the window: measured"
    assert rows["2025-08-05"]["size_surprise"] == "", "inside it: UNMEASURED"
    assert rows["2025-11-20"]["size_surprise"] == "0.0", "after it: measured"


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury does not currently anticipate that it will need to increase nominal coupon "
            "auction sizes.",
            0,
        ),
        (
            "Treasury does not, as of now, anticipate needing to increase nominal coupon auction "
            "sizes.",
            0,
        ),
        (
            "Treasury does not expect, as previously stated, to increase nominal coupon auction "
            "sizes.",
            0,
        ),
        ("Treasury will not, given current projections, increase nominal coupon auction sizes.", 0),
        (
            "It is not the case today that, over a long horizon, Treasury anticipates it will "
            "increase nominal coupon auction sizes.",
            None,
        ),
        ("Treasury will maintain nominal coupon auction sizes despite reduced demand.", None),
        ("Treasury will complete the cutover of nominal coupon auction systems.", None),
    ],
)
def test_negation_parentheticals_and_mixed_readings(text: str, want: int | None) -> None:
    """Audit must-fix and should-fixes on #394 v4: never the wrong sign."""
    assert tr.guidance(text) == want


def test_two_pages_on_one_date_are_one_statement() -> None:
    a = {"date": "2026-02-01", "url": "a", "sizes": {"3": 50}, "guidance": 0}
    same = {**a, "url": "b"}
    other = {**a, "url": "c", "sizes": {"3": 60}}
    prev = {"date": "2025-11-01", "url": "p", "sizes": {"3": 45}, "guidance": 0}
    assert len(tr.surprises([prev, a, same])) == 2
    got = tr.surprises([prev, a, other])
    assert len(got) == 2 and got[1]["size_surprise"] is None, "disagreeing pages: UNMEASURED"


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Treasury anticipates no increase in nominal coupon auction sizes.", 0),
        ("Treasury anticipates no need to increase nominal coupon auction sizes.", 0),
        (
            "Treasury anticipates that no increase in nominal coupon auction sizes will be needed.",
            0,
        ),
        (
            "There is no expectation that Treasury will need to increase nominal coupon auction "
            "sizes.",
            None,
        ),
        ("Treasury anticipates no changes to nominal coupon auction sizes.", 0),
        ("Treasury does not anticipate any change to nominal coupon auction sizes.", 0),
    ],
)
def test_a_bare_no_is_a_negation(text: str, want: int | None) -> None:
    """Audit must-fix on #394 v5: never +1 on "anticipates no increase"."""
    assert tr.guidance(text) == want


def test_an_out_of_order_listing_bounds_nothing() -> None:
    store = {
        u: {"date": d}
        for u, d in (
            ("a", "2023-01-04"),
            ("b", "2026-08-05"),
            ("c", "2026-02-04"),
            ("d", "2025-11-05"),
        )
    }
    fetched = {tr.INDEXES[0]: {"links": ["a", "b", "U", "c", "d"]}}
    assert tr.unread_windows(["U"], fetched, store) == [{"url": "U", "from": None, "to": None}]


def test_a_pair_an_unread_statement_could_split_is_not_measured() -> None:
    rows = [
        {"date": "2026-02-04", "sizes": {"3": 50}, "guidance": 0},
        {"date": "2026-08-05", "sizes": {"3": 55}, "guidance": 1},
        {"date": "2026-11-04", "sizes": {"3": 60}, "guidance": 1},
    ]
    gap = [(date(2026, 2, 4), date(2026, 8, 5))]
    got = tr.surprises(rows, gaps=gap)
    assert got[1]["size_surprise"] is None and got[1]["guidance_shift"] is None
    assert got[2]["guidance_shift"] == 0.0, "the pair after the gap is a real pair"
    assert tr.surprises(rows, gaps=[(None, None)])[2]["guidance_shift"] is None


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Treasury anticipates reductions to nominal coupon auction sizes, with no increases.", -1),
        (
            "Treasury expects that no later than the next refunding it will need to "
            "increase nominal "
            "coupon auction sizes.",
            1,
        ),
        ("Treasury will, no doubt, need to increase nominal coupon auction sizes.", 1),
        (
            "Treasury will, with no market disruption, be increasing nominal coupon auction sizes.",
            1,
        ),
        ("Treasury anticipates no increase in nominal coupon auction sizes.", 0),
        (
            "Treasury will increase nominal coupon auction sizes in some tenors and reduce them in "
            "others.",
            None,
        ),
    ],
)
def test_both_directions_are_read_before_answering(text: str, want: int | None) -> None:
    """Audit must-fix on #394 v6: a negated direction never hides an affirmed one, and a
    comparative or adverbial "no" never negates."""
    assert tr.guidance(text) == want


def test_a_voided_pair_is_no_step_either() -> None:
    rows = [
        {"date": "2026-02-04", "sizes": {"3": 50}, "guidance": 0},
        {"date": "2026-08-05", "sizes": {"3": 100}, "guidance": 1},
        {"date": "2026-11-04", "sizes": {"3": 110}, "guidance": 1},
        {"date": "2027-02-03", "sizes": {"3": 110}, "guidance": 0},
    ]
    got = tr.surprises(rows, gaps=[(date(2026, 2, 4), date(2026, 8, 5))])
    assert got[3]["size_surprise"] == pytest.approx(-0.1, abs=1e-6), "the +100% pair is void"


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury anticipates no further reductions in nominal coupon auction sizes; "
            "increases likely in the 2-year nominal coupon.",
            None,
        ),
        (
            "Treasury anticipates that, with no further reductions in bills, it will increase "
            "nominal coupon auction sizes.",
            1,
        ),
        (
            "Treasury anticipates no need to reduce nominal coupon auction sizes, and will "
            "increase them.",
            None,
        ),
        (
            "Treasury anticipates maintaining nominal coupon and FRN auction sizes for at least "
            "the next several quarters.",
            0,
        ),
    ],
)
def test_a_held_zero_needs_nothing_else_moving(text: str, want: int | None) -> None:
    """Audit must-fix on #394 v7: a false 0 against a true +1 is never written."""
    assert tr.guidance(text) == want


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (
            "Treasury anticipates maintaining nominal coupon auction sizes this quarter. "
            "Treasury anticipates that increases will likely be needed next quarter.",
            None,
        ),
        (
            "Treasury anticipates maintaining nominal coupon auction sizes; increasing bills "
            "and the 7-year note is likely.",
            None,
        ),
        (
            "Treasury anticipates maintaining nominal coupon auction sizes. Treasury expects "
            "to increase bill issuance.",
            0,
        ),
        (
            "Treasury anticipates maintaining nominal coupon and FRN auction sizes for at least "
            "the next several quarters. Treasury does not anticipate needing to increase them.",
            0,
        ),
    ],
)
def test_a_held_zero_is_judged_on_the_whole_statement(text: str, want: int | None) -> None:
    """Audit must-fix on #394 v8: any un-negated move in any sentence, unless its object is
    solely bills / TIPS / FRN, leaves the held 0 UNMEASURED."""
    assert tr.guidance(text) == want


def test_a_tips_tenor_is_not_a_coupon_object() -> None:
    assert tr._only_other_supply(" the 5-year TIPS auction sizes.")
    assert not tr._only_other_supply(" bills and the 7-year note is likely")


_HELD = "Treasury anticipates maintaining nominal coupon auction sizes. Treasury "


@pytest.mark.parametrize(
    ("tail", "want"),
    [
        ("will increase bills, and the 2-, 3- and 5-year.", None),
        ("will increase bills and, beginning in February, the 7-year note.", None),
        ("will increase the 5-year inflation-protected and 7-year nominal securities.", None),
        ("will increase bills and nominal auction sizes.", None),
        ("will increase TIPS and long-end issuance.", None),
        ("will continue to evaluate future increases to nominal coupon auction sizes.", 0),
        ("plans to reduce the size of the buybacks.", 0),
        ("will increase bill issuance.", 0),
    ],
)
def test_the_object_of_a_move_is_read_to_the_end_of_its_sentence(
    tail: str, want: int | None
) -> None:
    """Audit must-fix on #394 v9, and its coverage notes: hedges and buybacks are no move."""
    assert tr.guidance(_HELD + tail) == want


@pytest.mark.parametrize(
    ("tail", "want"),
    [
        ("will continue to evaluate future increases to nominal coupon auction sizes.", 0),
        ("will assess the need for any further reductions in coupon sizes.", 0),
        ("will monitor potential future increases to the 10-year note.", 0),
    ],
)
def test_a_governed_hedge_holds(tail: str, want: int | None) -> None:
    """Audit must-fix on #394 v10: the evaluation verb hedges only through a speculative
    modifier that binds it to the move."""
    assert tr.guidance(_HELD + tail) == want


@pytest.mark.parametrize(
    "text",
    [
        "Having assessed needs, it plans to increase the 2-year note auction sizes.",
        "Treasury will monitor demand and increase bills and the 5-year note.",
        "In its review, Treasury will increase the 2-year note auction size.",
        "Following its review, Treasury will increase the 2-year note auction size.",
        "Following a review of needs, Treasury will increase the 2-year note.",
        "Upon consideration, Treasury will increase the 2-year note auction size.",
        "Treasury, having studied demand, will increase the 2-year note auction size.",
        "After review, Treasury will cut the 20-year bond auction size.",
    ],
)
def test_an_evaluation_word_near_a_move_is_no_hedge(text: str) -> None:
    """Audit must-fix on #394 v10: each of these is a move, so the held 0 before it is
    UNMEASURED, never 0."""
    assert tr.guidance(_HELD.removesuffix("Treasury ") + text) is None


def test_a_reviewed_anticipation_is_guidance() -> None:
    text = "After review, Treasury anticipates increasing nominal coupon auction sizes."
    assert tr.guidance(text) == 1


@pytest.mark.parametrize(
    "tail",
    [
        "will consider increasing coupon sizes.",
        "maintains sizes but will consider increasing the 2-year next quarter.",
        "is reviewing a reduction in the 20-year bond.",
        "is studying whether to cut the 20-year bond.",
        "will consider further increasing the 2-year.",
        "will consider further reducing the 20-year bond.",
        "will assess the need for further increasing the 2-year.",
    ],
)
def test_a_considered_move_leaves_a_held_statement_unmeasured(tail: str) -> None:
    """A direction under consideration is not a held size: UNMEASURED, never 0."""
    assert tr.guidance(_HELD + tail) is None


def test_a_repeated_clause_is_read_from_its_own_place() -> None:
    """Audit should-fix on #394 v10: offsets come from each clause's own position."""
    sent = "Treasury will review sizes, and will review sizes; will increase bills"
    got = tr._clauses_at(sent)
    assert [sent[a : a + len(c)] for c, a in got] == [c for c, _ in got]
    assert got[0][1] < got[1][1]
