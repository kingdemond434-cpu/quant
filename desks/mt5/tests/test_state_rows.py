"""ROOTS R3 + R9 (2026-11-27): one bad row never kills an organ, and a stale input is never
read as fresh."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import state_rows as sr  # noqa: E402

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)
GOOD = {"name": "a", "status": "LIVE", "symbol": "XAUUSD", "certificate": {"cell": "c"}}


def _write(p: Path, rows, **extra) -> Path:
    p.write_text(json.dumps({"sleeves": rows, **extra}), encoding="utf-8")
    return p


def test_one_bad_row_is_quarantined_and_the_rest_are_read(tmp_path) -> None:
    rows = [GOOD, "junk", {**GOOD, "name": "b", "certificate": "XAUUSD.fam@M30#k=1"},
            {**GOOD, "name": "c", "certificate": 5}, {"status": "LIVE"},
            {**GOOD, "name": "d", "risk_frac": True}]
    got = sr.sleeve_rows(_write(tmp_path / "s.json", rows), now=NOW,
                         report=tmp_path / "Q.json")
    assert got.status == sr.OK and [r["name"] for r in got.rows] == ["a", "b"]
    assert [q["index"] for q in got.quarantined] == [1, 3, 4, 5]
    rep = json.loads((tmp_path / "Q.json").read_text("utf-8"))["inputs"]["sleeves.json"]
    assert rep["quarantined"] == 4 and rep["rows"] == 2


def test_absent_and_torn_are_never_a_partial_good_set(tmp_path) -> None:
    assert sr.sleeve_rows(tmp_path / "nope.json", publish=False).status == sr.ABSENT
    (tmp_path / "t.json").write_text("{torn", encoding="utf-8")
    got = sr.sleeve_rows(tmp_path / "t.json", publish=False)
    assert got.status == sr.UNMEASURED and got.rows == []
    (tmp_path / "l.json").write_text(json.dumps({"sleeves": {"a": 1}}), encoding="utf-8")
    assert sr.sleeve_rows(tmp_path / "l.json", publish=False).status == sr.UNMEASURED


def test_an_input_past_its_shelf_life_is_stale_by_its_own_stamp(tmp_path) -> None:
    p = tmp_path / "spreads.json"
    p.write_text(json.dumps({"measured_at": (NOW - timedelta(days=65)).isoformat()}), "utf-8")
    got = sr.load_doc(p, max_age_s=7 * 86400, now=NOW)
    assert got.status == sr.STALE and not got.usable and got.age_s > 60 * 86400
    p.write_text(json.dumps({"measured_at": (NOW - timedelta(hours=1)).isoformat()}), "utf-8")
    assert sr.load_doc(p, max_age_s=7 * 86400, now=NOW).usable


def test_an_unstamped_input_ages_by_its_mtime(tmp_path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    old = (NOW - timedelta(days=3)).timestamp()
    os.utime(p, (old, old))
    assert sr.load_doc(p, max_age_s=86400, now=NOW).status == sr.STALE


def test_a_checker_that_raises_quarantines_the_row_only(tmp_path) -> None:
    def boom(r):
        if r.get("name") == "x":
            raise KeyError("x")
        return None
    (tmp_path / "r.json").write_text(json.dumps([{"name": "x"}, {"name": "y"}]), "utf-8")
    got = sr.load_rows(tmp_path / "r.json", check=boom, publish=False)
    assert [r["name"] for r in got.rows] == ["y"] and "KeyError" in got.quarantined[0]["why"]


def test_the_gateway_roster_keeps_every_good_live_row_past_a_bad_one(tmp_path) -> None:
    """Before R3, one non-object row made load_sleeves_verbose return an empty roster."""
    p = _write(tmp_path / "sleeves.json", ["junk", {**GOOD, "status": "STANDBY", "name": "s"}])
    live, notes = dc.load_sleeves_verbose(p)
    assert live == [] and any("quarantined" in n for n in notes)
    assert (tmp_path / "STATE_QUARANTINE.json").exists()      # beside a non-desk sleeves file
