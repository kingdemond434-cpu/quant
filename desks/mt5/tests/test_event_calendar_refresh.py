"""The refresh leg writes only a calendar that passes, keeps the last good one otherwise, and
reports STALE loudly."""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import event_calendar_refresh as R  # noqa: E402

FIX = _DESK.parent.parent / "tests" / "fixtures" / "event_calendar"
NOW = datetime(2026, 11, 13, 20, 25, tzinfo=UTC)


def _fetch(drop: tuple[str, ...] = ()):
    pages = {f.name[:-8]: gzip.decompress(f.read_bytes()).decode("utf-8", "replace")
             for f in FIX.glob("*.html.gz")}
    for k in drop:
        pages[k] = None
    return lambda: (pages, {k: "HTTP 403" for k in drop})


def test_first_run_writes_a_fresh_calendar(tmp_path) -> None:
    out, hp = tmp_path / "cal.json", tmp_path / "health.json"
    rep = R.run(out=out, health_path=hp, now=NOW, fetch=_fetch())
    assert rep["refreshed"] and rep["health"]["state"] == "FRESH"
    doc = json.loads(out.read_text("utf-8"))
    assert doc["valid_through"] and doc["coverage"]["fed_fomc"]["status"] == "OK"
    assert json.loads(hp.read_text("utf-8"))["health"]["state"] == "FRESH"


def test_not_due_reads_and_does_not_fetch(tmp_path) -> None:
    out, hp = tmp_path / "cal.json", tmp_path / "health.json"
    R.run(out=out, health_path=hp, now=NOW, fetch=_fetch())

    def boom():
        raise AssertionError("fetched while fresh")
    rep = R.run(out=out, health_path=hp, now=NOW + timedelta(days=1), fetch=boom)
    assert not rep["refreshed"] and rep["due"] is None and rep["health"]["state"] == "FRESH"


def test_a_refused_write_keeps_the_last_good_calendar(tmp_path) -> None:
    out, hp = tmp_path / "cal.json", tmp_path / "health.json"
    R.run(out=out, health_path=hp, now=NOW, fetch=_fetch())
    before = out.read_text("utf-8")
    later = NOW + timedelta(days=60)
    rep = R.run(out=out, health_path=hp, now=later, fetch=lambda: ({}, {}))
    assert rep["refused_write"] and rep["missed_growth"]
    assert out.read_text("utf-8") == before


def test_a_core_publisher_unread_past_the_carry_reads_stale_and_exits_red(tmp_path,
                                                                          monkeypatch) -> None:
    out, hp = tmp_path / "cal.json", tmp_path / "health.json"
    R.run(out=out, health_path=hp, now=NOW, fetch=_fetch())
    later = NOW + timedelta(days=30)
    rep = R.run(out=out, health_path=hp, now=later, fetch=_fetch(("bls_cpi",)))
    assert rep["health"]["state"] == "STALE"
    monkeypatch.setattr(R, "run", lambda **_k: rep)
    assert R.main(["--out", str(out)]) == 2
