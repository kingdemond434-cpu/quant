"""SEC fails-to-deliver squeeze state: parsing, PIT stamping, the robots gate and the event lane.

Offline only: every SEC answer here is a recorded-shape fixture served by a fake fetcher.
"""
from __future__ import annotations

import io
import json
import math
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import sec_ftd_squeeze as F  # noqa: E402

UA = "Example Research contact@example.invalid"
HEADER = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"
SYMS = {"Tesla": "TSLA", "Berkshire": "BRKB"}


def _zip(lines: list[str], name: str = "cnsfails.txt") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, "\n".join([HEADER, *lines, "Trailer total records: 9"]))
    return buf.getvalue()


def _file_for(pid: str, tsla: float, extra: list[str] | None = None) -> bytes:
    lo, _ = F.period_bounds(pid)
    days = [lo.replace(day=d) for d in (lo.day, lo.day + 1, lo.day + 2, lo.day + 3, lo.day + 4,
                                        lo.day + 5)]
    rows = []
    for d in days:
        ds = d.strftime("%Y%m%d")
        rows.append(f"{ds}|000000001|OTHR|5|OTHER CO|1.00")
        if tsla:
            rows.append(f"{ds}|88160R101|TSLA|{int(tsla)}|TESLA INC|250.00")
    return _zip(rows + (extra or []))


class FakeSEC:
    """Serves robots.txt and cnsfails files from dicts, and records every request."""

    def __init__(self, files: dict[str, tuple[bytes, datetime]], robots: tuple[int, str]
                 = (200, "User-agent: *\nDisallow: /cgi-bin/\n")) -> None:
        self.files, self.robots, self.calls = files, robots, []

    def __call__(self, url: str, headers: Any, deadline: float) -> F.Fetched:
        self.calls.append((url, dict(headers)))
        if url.endswith("/robots.txt"):
            return F.Fetched(status=self.robots[0], body=self.robots[1].encode())
        pid = url.rsplit("cnsfails", 1)[1][:-4]
        if pid not in self.files:
            return F.Fetched(status=404, error="HTTP 404")
        body, at = self.files[pid]
        return F.Fetched(status=200, body=body, headers={"last-modified": format_datetime(at)})


def _paths(tmp: Path) -> dict[str, Path]:
    return {"periods_dir": tmp / "periods", "state_path": tmp / "fetch_state.json",
            "series_dir": tmp / "event_lane" / "series", "state_out": tmp / "event_lane" / "s.json",
            "report_path": tmp / "REPORT.json"}


# ----------------------------------------------------------------------------- parsing
def test_parser_skips_header_and_trailer_sums_cusips_and_normalises_tickers() -> None:
    lines = [HEADER, "20261001|1|TSLA|100|TESLA|250.5", "20261001|2|TSLA|50|TESLA ALT|.",
             "20261002|3|BRK.B|7|BERKSHIRE B|410", "20261002|4|ZZZ|9|Z|1",
             "20261003|5|TSLA|notanumber|X|1", "Trailer record count 6"]
    days, rows, read, skipped = F.parse_ftd_lines(lines, ["TSLA", "BRK-B"])
    assert days == ["20261001", "20261002"]
    assert rows["TSLA"]["20261001"] == [150.0, 250.5]
    assert rows["BRKB"]["20261002"] == [7.0, 410.0]
    assert "ZZZ" not in rows
    assert (read, skipped) == (4, 3)


def test_period_arithmetic_and_freshness() -> None:
    assert F.period_bounds("202602b")[1].isoformat() == "2026-02-28"
    assert F.previous_period("202601a") == "202512b"
    assert F.previous_period("202603b") == "202603a"
    cands = F.candidate_periods(datetime(2026, 11, 22, tzinfo=UTC).date(), n=3)
    assert cands == ["202611a", "202610b", "202610a"]   # 11-15 is 7 days old on 11-22


def test_publication_stamp_never_earlier_than_the_period_or_later_than_held() -> None:
    seen = datetime(2026, 11, 18, 12, tzinfo=UTC)
    lm = datetime(2026, 10, 30, 14, 5, tzinfo=UTC)
    assert F.publication_stamp({"last-modified": format_datetime(lm)}, "202610a", seen) == \
        (lm, "last_modified")
    early = datetime(2026, 10, 10, tzinfo=UTC)          # before the period's last day: refused
    assert F.publication_stamp({"last-modified": format_datetime(early)}, "202610a", seen) == \
        (seen, "first_seen")
    assert F.publication_stamp({}, "202610a", seen) == (seen, "first_seen")
    future = datetime(2026, 12, 1, tzinfo=UTC)
    assert F.publication_stamp({"last-modified": format_datetime(future)}, "202610a", seen)[1] \
        == "first_seen"


# ----------------------------------------------------------------------------- access
def test_no_contact_ua_makes_no_request_at_all(tmp_path: Path) -> None:
    fake = FakeSEC({})
    rep = F.collect(now=datetime(2026, 11, 18, tzinfo=UTC), ua="", tickers=["TSLA"], fetch=fake,
                    deadline=time.monotonic() + 30, periods_dir=tmp_path / "p",
                    state_path=tmp_path / "s.json")
    assert rep["status"] == "BLOCKED_ON_CONTACT" and rep["missed_growth"]
    assert fake.calls == []


def test_robots_disallow_and_5xx_refuse_and_404_allows(tmp_path: Path) -> None:
    now = datetime(2026, 11, 18, tzinfo=UTC)
    kw = {"now": now, "ua": UA, "tickers": ["TSLA"], "deadline": time.monotonic() + 30,
          "periods_dir": tmp_path / "p", "state_path": tmp_path / "s.json"}
    barred = FakeSEC({}, robots=(200, "User-agent: *\nDisallow: /files/data/\n"))
    assert F.collect(fetch=barred, **kw)["status"] == "ROBOTS_REFUSED"
    assert [u for u, _ in barred.calls] == [F.HOST + "/robots.txt"]
    down = FakeSEC({}, robots=(503, ""))
    assert F.collect(fetch=down, **kw)["status"] == "ROBOTS_REFUSED"
    html = FakeSEC({}, robots=(200, "<!DOCTYPE html><html>"))
    assert F.collect(fetch=html, **kw)["status"] == "ROBOTS_REFUSED"
    absent = FakeSEC({}, robots=(404, ""))
    rep = F.collect(fetch=absent, **kw)
    assert rep["status"] == "FETCHED" and rep["not_published"]
    # the robots read and every file read went out under the SAME agent
    assert {h["User-Agent"] for _, h in absent.calls} == {UA}


def test_a_403_is_a_hard_stop(tmp_path: Path) -> None:
    class Refusing(FakeSEC):
        def __call__(self, url: str, headers: Any, deadline: float) -> F.Fetched:
            if url.endswith(".zip"):
                self.calls.append((url, headers))
                return F.Fetched(status=403, error="HTTP 403")
            return super().__call__(url, headers, deadline)
    fake = Refusing({})
    rep = F.collect(now=datetime(2026, 11, 18, tzinfo=UTC), ua=UA, tickers=["TSLA"], fetch=fake,
                    deadline=time.monotonic() + 30, periods_dir=tmp_path / "p",
                    state_path=tmp_path / "s.json")
    assert rep["status"] == "HARD_STOP"
    assert sum(u.endswith(".zip") for u, _ in fake.calls) == 1


# ----------------------------------------------------------------------------- end to end
def _history(now: datetime) -> dict[str, tuple[bytes, datetime]]:
    """Ten half-months, each published 14 days after its period ends; TSLA quiet, then a burst."""
    files = {}
    pids = list(reversed(F.candidate_periods(now.date(), n=10)))
    for i, pid in enumerate(pids):
        end = F.period_bounds(pid)[1]
        at = datetime(end.year, end.month, end.day, 21, tzinfo=UTC) + timedelta(days=14)
        tsla = 20_000 if i == len(pids) - 1 else 100 + 10 * i
        files[pid] = (_file_for(pid, tsla), min(at, now))
    return files


def test_end_to_end_state_is_point_in_time_and_lands_in_the_event_lane_door(tmp_path: Path
                                                                           ) -> None:
    now = datetime(2026, 11, 18, 6, tzinfo=UTC)
    files = _history(now)
    fake = FakeSEC(files)
    p = _paths(tmp_path)
    for _ in range(3):                                   # MAX_FETCH_PER_PASS per pass
        rep = F.run_once(now=now, fetch=fake, ua=UA, symbols=SYMS, aside=[], **p)
    assert len(rep["periods_held"]) == 10
    assert rep["lane"] == "event" and rep["verdict"] == "MEASURED"
    state = json.loads(p["state_out"].read_text())["states"]
    tsla = state["Tesla"]
    newest = max(files, key=lambda k: files[k][1])
    assert tsla["event_time"] == newest and tsla["lane"] == "event"
    assert tsla["available_time"] == files[newest][1].isoformat(timespec="seconds")
    assert tsla["regsho_proxy"] is True and tsla["state"] == "SQUEEZE_WATCH"
    assert tsla["surprise_z"] > 2
    # Berkshire never appears in a file: a MEASURED zero, never a missing row
    assert state["Berkshire"]["fails_max"] == 0.0
    # the event lane's executor reads the series as it reads any release series
    from mt5desk.family_alt_release import releases
    ev = releases(F.series_id("Tesla"), "surprise_z", root=p["series_dir"])
    assert ev and ev[-1][0] == files[newest][1] and ev[-1][1] > 2
    # the UA is never written anywhere
    for path in tmp_path.rglob("*.json"):
        assert UA not in path.read_text()
    # nothing goes to the hypothesis lane's intake or the globbed lake
    assert not (tmp_path / "intelligence").exists()
    assert "lake" not in str(F.SERIES_DIR) and "intelligence" not in str(F.SERIES_DIR)


def test_a_row_never_reads_a_file_published_after_it() -> None:
    """Period B is published BEFORE the earlier period A; B's z must not count A."""
    def doc(pid: str, at: str, tsla: float) -> dict[str, Any]:
        lo, _ = F.period_bounds(pid)
        day = lo.strftime("%Y%m%d")
        return {"period": pid, "available_time": at, "pit_basis": "last_modified",
                "settlement_days": [day], "rows": {"TSLA": {day: [tsla, 10.0]}}}
    pids = list(reversed(F.candidate_periods(datetime(2026, 11, 18, tzinfo=UTC).date(), n=9)))
    docs = [doc(pid, f"2026-0{1 + i // 2}-0{1 + i % 2}T00:00:00+00:00", 100.0 * (1 + i % 3))
            for i, pid in enumerate(pids[:7])]
    late = doc(pids[7], "2026-12-31T00:00:00+00:00", 5000.0)    # earlier period, published last
    b = doc(pids[8], "2026-12-01T00:00:00+00:00", 300.0)
    rows = F.build_states([*docs, late, b], {"Tesla": "TSLA"})["Tesla"]
    row_b = next(r for r in rows if r["event_time"] == pids[8])
    assert row_b["history_files"] == 7                     # the late file is not yet knowable
    row_late = next(r for r in rows if r["event_time"] == pids[7])
    assert row_late["available_time"] > row_b["available_time"]
    assert math.isfinite(row_b["surprise_z"])


def test_only_registry_event_lane_equities_are_built() -> None:
    from research import universe_policy as up
    symbols, aside = F.event_lane_symbols()
    assert symbols, "no event-lane share CFD resolved from the registry"
    for sym in symbols:
        assert up.is_equity(sym) and up.lane(sym) == up.EVENT
        assert not up.may_hypothesise(sym, "exogenous_conditioner")
    assert all(row.get("why") for row in aside)
