"""Federal Register regulatory pressure: the terms switch and robots fail closed, the stop codes
halt the pass, the daily aggregation by agency, the midnight-window calendar, comment-deadline
clustering, the effective-date clock, the idempotent point-in-time store, and cells only on the
allowed symbols. No network: every request is served by a synthetic fake."""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fedreg_pressure as fr  # noqa: E402

T0 = datetime(2026, 11, 18, 15, tzinfo=UTC)


def _docs(n_days: int, end: date) -> list[dict[str, Any]]:
    """Synthetic documents on weekdays: two rules (one by two agencies) and one proposed rule."""
    out: list[dict[str, Any]] = []
    d = end - timedelta(days=n_days)
    i = 0
    while d <= end:
        if d.weekday() < 5:
            i += 1
            ds = d.isoformat()
            out.append({"document_number": f"R-{i}", "type": "Rule", "publication_date": ds,
                        "effective_on": (d + timedelta(days=30)).isoformat(),
                        "page_length": 5 + (i % 7),
                        "agencies": [{"slug": "epa"}, {"slug": "energy-department"}],
                        "significant": i % 10 == 0, "title": f"rule {i}"})
            out.append({"document_number": f"S-{i}", "type": "Rule", "publication_date": ds,
                        "start_page": 100, "end_page": 102, "agencies": [{"slug": "sec"}],
                        "title": f"short {i}"})
            out.append({"document_number": f"P-{i}", "type": "Proposed Rule",
                        "publication_date": ds,
                        "comments_close_on": (d + timedelta(days=5)).isoformat(),
                        "page_length": 3, "agencies": [{"slug": "epa"}], "title": f"prop {i}"})
        d += timedelta(days=1)
    return out


class FakeFR:
    def __init__(self, docs: list[dict[str, Any]], *,
                 robots: tuple[int, bytes] = (200, b"User-agent: *\nDisallow: /my/\n"),
                 stop: int | None = None, outside: bool = False) -> None:
        self.docs, self.robots, self.stop, self.outside = docs, robots, stop, outside
        self.urls: list[str] = []

    def api(self) -> list[str]:
        return [u for u in self.urls if not u.endswith("/robots.txt")]

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        assert parts.netloc == "www.federalregister.gov"
        if parts.path == "/robots.txt":
            return self.robots
        if self.stop:
            return self.stop, b""
        assert parts.path == fr.API_PATH
        q = urllib.parse.parse_qs(parts.query)
        assert set(q["conditions[type][]"]) == {"RULE", "PRORULE"}
        lo = q["conditions[publication_date][gte]"][0]
        hi = q["conditions[publication_date][lte]"][0]
        rows = [r for r in self.docs if lo <= r["publication_date"] <= hi]
        if self.outside and rows:
            rows = [{**rows[0], "publication_date": "1999-01-01"}]
        return 200, json.dumps({"count": len(rows), "total_pages": 1,
                                "results": rows}).encode()


def _paths(tmp_path: Path, symbols: tuple[str, ...] = ("US500", "US2000", "US30")) -> fr.Paths:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    uni = {s: {"asset_class": "Indices"} for s in symbols}
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(uni), "utf-8")
    return fr.Paths(desk=tmp_path)


def _run(paths: fr.Paths, fake: FakeFR, now: datetime = T0,
         minted: list[Any] | None = None) -> dict[str, Any]:
    def donate(seat: str, cands: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if minted is not None:
            minted.extend(cands)
        return {"donated": len(cands)}
    return fr.run(paths, get=fake, now=now, sleep=lambda _s: None, donate=donate)


# ------------------------------------------------------------------------------ gates
def test_terms_switch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(fr.TERMS_EVIDENCE, "machine_use_allowed", False)
    fake = FakeFR(_docs(10, T0.date()))
    doc = _run(_paths(tmp_path), fake)
    assert doc["status"] == "BLOCKED_ON_TERMS"
    assert fake.urls == []
    assert doc["missed_growth"] and doc["fetch"]["missed_growth"]


def test_robots_refusal_stops_before_the_api(tmp_path: Path) -> None:
    fake = FakeFR(_docs(10, T0.date()), robots=(200, b"User-agent: *\nDisallow: /api/\n"))
    doc = _run(_paths(tmp_path), fake)
    assert doc["status"] == "ROBOTS_REFUSED"
    assert fake.api() == []


@pytest.mark.parametrize("robots", [(500, b""), (200, b"<!DOCTYPE html><p>hi</p>")])
def test_unreadable_robots_refuses(tmp_path: Path, robots: tuple[int, bytes]) -> None:
    fake = FakeFR([], robots=robots)
    assert _run(_paths(tmp_path), fake)["status"] == "ROBOTS_REFUSED"
    assert fake.api() == []


def test_robots_404_means_no_rules(tmp_path: Path) -> None:
    fake = FakeFR(_docs(5, T0.date()), robots=(404, b""))
    assert _run(_paths(tmp_path), fake)["status"] == "OK"


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_stop_codes_halt_and_hold(tmp_path: Path, code: int) -> None:
    paths = _paths(tmp_path)
    fake = FakeFR([], stop=code)
    doc = _run(paths, fake)
    assert doc["status"] == "HARD_STOP"
    assert len(fake.api()) == 1
    state = json.loads(paths.state.read_text("utf-8"))
    assert state["hard_stop"]["code"] == code
    assert (state["hard_stop"]["until"] is None) == (code == 451)
    again = FakeFR(_docs(5, T0.date()))
    assert _run(paths, again, T0 + timedelta(hours=2))["status"] == "HARD_STOP"
    assert again.urls == []


def test_row_outside_the_window_is_a_metadata_mismatch(tmp_path: Path) -> None:
    doc = _run(_paths(tmp_path), FakeFR(_docs(5, T0.date()), outside=True))
    assert doc["status"] == "METADATA_MISMATCH"


def test_unknown_type_is_a_metadata_mismatch() -> None:
    with pytest.raises(fr.Refused, match="METADATA_MISMATCH"):
        fr.parse_rows([{"document_number": "x", "type": "Notice",
                        "publication_date": "2026-11-02"}], date(2026, 11, 1),
                       date(2026, 11, 30))


def test_requests_are_throttled_and_bounded() -> None:
    slept: list[float] = []
    c = fr.Client(lambda u: (200, b'{"results": []}'), sleep=slept.append, max_requests=2)
    c.json(fr.API)
    c.json(fr.API)
    assert slept and slept[0] > 0
    with pytest.raises(fr.Refused, match="BUDGET"):
        c.json(fr.API)


# ------------------------------------------------------------------------------ store
def test_idempotent_append_and_revision(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    docs = _docs(20, T0.date())
    store: dict[str, dict[str, Any]] = {}
    rows = fr.parse_rows(docs, T0.date() - timedelta(days=30), T0.date())
    first = fr.merge(paths, store, rows, T0, backfill=False)
    assert first == {"added": len(rows), "revised": 0}
    assert fr.merge(paths, store, rows, T0, backfill=False) == {"added": 0, "revised": 0}
    reloaded = fr.load_store(paths)
    assert fr.merge(paths, reloaded, rows, T0, backfill=False) == {"added": 0, "revised": 0}
    moved = [{**rows[0], "effective_on": "2027-06-01"}]
    assert fr.merge(paths, reloaded, moved, T0 + timedelta(days=1), False)["revised"] == 1
    again = fr.load_store(paths)
    k = rows[0]["document_number"]
    assert again[k]["effective_on"] == rows[0]["effective_on"]       # PIT first value kept
    assert again[k]["last"]["effective_on"] == "2027-06-01"
    assert again[k]["n_revisions"] == 1


def test_available_time_is_end_of_day_new_york_or_later(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    store: dict[str, dict[str, Any]] = {}
    row = fr.parse_rows([{"document_number": "a", "type": "Rule",
                          "publication_date": "2026-11-16"}], date(2026, 11, 1),
                        date(2026, 11, 30))
    fr.merge(paths, store, row, datetime(2026, 11, 16, 12, tzinfo=UTC), backfill=False)
    assert store["a"]["available_time"] == "2026-11-17T05:00:00+00:00"   # EST midnight
    store2: dict[str, dict[str, Any]] = {}
    fr.merge(paths, store2, row, T0, backfill=True)
    assert store2["a"]["available_time"] == "2026-11-18T05:00:00+00:00"   # + backfill lag


def test_pass_twice_appends_nothing_and_not_due(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    fake = FakeFR(_docs(30, T0.date()))
    one = _run(paths, fake)
    assert one["status"] == "OK" and one["fetch"]["added"] > 0
    two = _run(paths, fake, T0 + timedelta(hours=1))
    assert two["status"] == "NOT_DUE"
    three = _run(paths, fake, T0 + timedelta(hours=7))
    assert three["status"] == "OK"
    assert three["fetch"]["added"] == 0 and three["fetch"]["revised"] == 0
    assert three["store_rows"] == one["store_rows"]


# ------------------------------------------------------------------------- aggregation
def test_daily_aggregation_by_agency(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    store: dict[str, dict[str, Any]] = {}
    rows = fr.parse_rows(_docs(0, date(2026, 11, 16)), date(2026, 11, 1), date(2026, 11, 30))
    fr.merge(paths, store, rows, T0, backfill=False)
    day = fr.daily_aggregate(store)["2026-11-16"]
    assert day["totals"]["RULE"]["n"] == 2                      # the two-agency rule counts once
    rule_pages = rows[0]["page_length"] + 3                     # S- has start/end 100..102
    assert day["totals"]["RULE"]["pages"] == rule_pages
    assert day["totals"]["PRORULE"] == {"n": 1, "pages": 3, "pages_unmeasured": 0}
    assert day["by_agency"]["epa"]["RULE"]["n"] == 1
    assert day["by_agency"]["energy-department"]["RULE"]["n"] == 1
    assert day["by_agency"]["epa"]["PRORULE"]["n"] == 1
    assert day["by_agency"]["sec"]["RULE"]["pages"] == 3


def test_missing_pages_are_unmeasured_not_zero(tmp_path: Path) -> None:
    store: dict[str, dict[str, Any]] = {}
    rows = fr.parse_rows([{"document_number": "a", "type": "Rule",
                           "publication_date": "2026-11-16"}], date(2026, 11, 1),
                         date(2026, 11, 30))
    fr.merge(_paths(tmp_path), store, rows, T0, backfill=False)
    tot = fr.daily_aggregate(store)["2026-11-16"]["totals"]["RULE"]
    assert tot == {"n": 1, "pages": 0, "pages_unmeasured": 1}


# ---------------------------------------------------------------------------- midnight
def test_midnight_window_calendar() -> None:
    assert fr.election_day(2024) == date(2024, 11, 5)
    assert fr.election_day(2028) == date(2028, 11, 7)
    assert fr.election_day(2020) == date(2020, 11, 3)
    assert fr.election_day(2026) is None
    assert fr.election_day(2032) == date(2032, 11, 2)       # Nov 1 is a Monday: the 2nd
    assert fr.midnight_window(2024) == (date(2024, 11, 5), date(2025, 1, 20))
    assert fr.midnight_state(date(2024, 12, 15))["in_window"] is True
    assert fr.midnight_state(date(2025, 1, 20))["in_window"] is True
    assert fr.midnight_state(date(2025, 1, 21))["in_window"] is False
    s = fr.midnight_state(date(2026, 11, 18))
    assert s["in_window"] is False and s["next_start"] == "2028-11-07"
    assert fr.midnight_state(date(2028, 3, 1))["next_start"] == "2028-11-07"
    assert fr.midnight_state(date(2024, 11, 4))["in_window"] is False


# --------------------------------------------------------------------------- comments
def test_comment_deadline_clustering(tmp_path: Path) -> None:
    store: dict[str, dict[str, Any]] = {}
    raw = [{"document_number": f"c{i}", "type": "Proposed Rule", "publication_date": "2026-11-02",
            "comments_close_on": cc, "agencies": [{"slug": "epa" if i < 3 else "fcc"}]}
           for i, cc in enumerate(["2026-11-20", "2026-11-20", "2026-11-23", "2026-12-30",
                                   "2027-03-01"])]
    rows = fr.parse_rows(raw, date(2026, 11, 1), date(2026, 11, 30))
    fr.merge(_paths(tmp_path), store, rows, T0, backfill=False)
    c = fr.comment_clusters(store, date(2026, 11, 18))
    assert c["per_day"] == {"2026-11-20": 2, "2026-11-23": 1, "2026-12-30": 1}
    assert c["per_week"]["2026-W47"] == 2 and c["per_week"]["2026-W48"] == 1
    assert c["busiest_weeks"][0] == {"week": "2026-W47", "closing": 2}
    assert c["n_closing"] == 4 and c["busiest_agencies"]["epa"] == 3
    nxt = fr.comment_close_next(store, ["2026-11-01", "2026-11-16", "2026-11-19"])
    assert nxt["2026-11-01"] == 0                    # nothing published yet: point-in-time
    assert nxt["2026-11-16"] == 2 and nxt["2026-11-19"] == 2   # 20th x2; 23rd is 7d from 16th


# ---------------------------------------------------------------------------- the clock
def test_event_clock_output(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    doc = _run(paths, FakeFR(_docs(120, T0.date())))
    clock = json.loads(paths.clock.read_text("utf-8"))
    assert clock["n_events"] == doc["clock"]["n_events"] > 0
    assert clock["size_threshold_pages"] is not None
    for e in clock["events"]:
        assert e["kind"] == "fedreg_rule_effective"
        assert e["instruments"] == ["US500", "US2000"]
        assert e["significant"] is True or e["page_length"] >= clock["size_threshold_pages"]
        assert e["at"].endswith("+00:00") and e["agencies"]
    assert any(e["upcoming"] for e in clock["events"])
    assert not any(e["document_number"].startswith("S-") for e in clock["events"])
    # the atlas reads it as a ground: its normaliser accepts every row
    from research import event_response_atlas as A
    rows, status = A._rows_from(paths.clock, "fedreg_effective")
    assert status == "READ" and all(A._normalise(r, "fedreg_effective") for r in rows)


def test_clock_effective_time_is_new_york_open() -> None:
    assert fr.effective_at(date(2026, 7, 1)).isoformat() == "2026-07-01T13:30:00+00:00"
    assert fr.effective_at(date(2026, 12, 1)).isoformat() == "2026-12-01T14:30:00+00:00"


def test_clock_without_size_sample_names_its_missed_growth() -> None:
    c = fr.build_clock({}, T0, ["US500"], source_status="NO_FETCH")
    assert c["status"] == fr.UNMEASURED and "missed_growth_size" in c


# ---------------------------------------------------------------------------- cells
def test_cells_only_on_allowed_symbols(tmp_path: Path) -> None:
    paths = _paths(tmp_path, symbols=("US500", "US30"))             # US2000 not in registry
    minted: list[Any] = []
    doc = _run(paths, FakeFR(_docs(400, T0.date())), minted=minted)
    assert doc["symbols"] == ["US500"]
    assert "US2000" in doc["cells"]["skipped"]
    assert doc["cells"]["grid"] > 0 and minted
    assert {c["symbol"] for c in minted} == {"US500"}
    for c in minted:
        assert c["family"] == "exogenous_conditioner"
        assert c["params"]["source"].startswith("fedreg_")
        assert c["params"]["source"].removeprefix("fedreg_") in fr.CELL_SERIES
    lake = paths.series / "fedreg_rule__pages.csv"
    assert lake.exists()
    head = lake.read_text("utf-8").splitlines()[0].split(",")
    assert {"event_time", "available_time", "value"} <= set(head)


def test_cells_fail_closed_without_policy(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    import keyed_sources
    monkeypatch.setattr(keyed_sources, "universe_gate", lambda: (None, "BLOCKED_DEPENDENCY:x"))
    syms, skipped = fr.allowed_symbols(_paths(tmp_path))
    assert syms == [] and "universe_policy" in skipped


def test_short_history_mints_nothing_and_says_why(tmp_path: Path) -> None:
    minted: list[Any] = []
    doc = _run(_paths(tmp_path), FakeFR(_docs(30, T0.date())), minted=minted)
    assert minted == [] and doc["cells"]["grid"] == 0
    assert all("stands down" in v for k, v in doc["cells"]["skipped"].items()
               if k in fr.CELL_SERIES)


def test_window_over_the_pagination_cap_is_halved() -> None:
    calls: list[tuple[str, str]] = []

    def get(url: str) -> tuple[int, bytes]:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        lo = q["conditions[publication_date][gte]"][0]
        hi = q["conditions[publication_date][lte]"][0]
        calls.append((lo, hi))
        span = (date.fromisoformat(hi) - date.fromisoformat(lo)).days
        n = 3000 if span > 7 else 1
        return 200, json.dumps({"count": n, "results": [] if n > 2000 else [
            {"document_number": f"{lo}", "type": "Rule", "publication_date": lo}]}).encode()
    c = fr.Client(get, sleep=lambda _s: None)
    rows = fr.pull_window(c, date(2026, 10, 1), date(2026, 10, 31))
    assert len(calls) > 1 and rows
    assert all((date.fromisoformat(b) - date.fromisoformat(a)).days <= 31 for a, b in calls)
