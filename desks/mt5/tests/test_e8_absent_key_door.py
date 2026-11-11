"""The E8 absent-key door (D-20261111-071): an enabled cert book that does not name a gold window
sizes it at the fresh survival solve's fraction, only while the journal holds the release row."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.kelly_sizing import load_kelly_survival  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def _journal(tmp: Path, with_row: bool) -> Path:
    p = tmp / "decision_journal.jsonl"
    rows = [{"id": "D-20261105-043", "title": "other"}]
    if with_row:
        rows.append({"id": g.ABSENT_KEY_DOOR_ROW, "title": "absent-key door"})
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def _solve(tmp: Path, windows: dict[str, float], age_s: float = 60.0) -> dict[str, float] | None:
    p = tmp / "KELLY_SURVIVAL.json"
    p.write_text(json.dumps({
        "generated_at": (NOW - timedelta(seconds=age_s)).isoformat(),
        "e8": {"status": "OK", "windows": {w: {"risk_frac": v} for w, v in windows.items()}},
    }), encoding="utf-8")
    return load_kelly_survival(p, "e8", now=NOW)


def _size(tmp: Path, *, row: bool, book: dict[str, float], solve: dict[str, float] | None,
          name: str = "london_am") -> tuple[float, dict]:
    door = g.absent_key_door_open(_journal(tmp, row))
    kelly, cert, absent, void, doored = g.resolve_book(solve, book, door=door)
    frac, _src = g.window_risk(name, kelly)
    return frac, {"absent": absent, "doored": doored,
                  "sources": g.window_sources(solve, cert, absent, {}, void, doored)}


def test_door_open_sizes_absent_london_am_at_the_solve_fraction(tmp_path: Path) -> None:
    solve = _solve(tmp_path, {"asia": 0.004, "london_am": 0.0035, "afternoon": 0.003})
    frac, info = _size(tmp_path, row=True, book={"gold_asia": 0.005}, solve=solve)
    assert frac == 0.0035
    assert info["sources"]["london_am"] == "absent_key_door"
    assert info["sources"]["asia"] == "cert_book"
    assert "london_am" not in info["absent"]


def test_row_absent_keeps_the_whitelist_zero(tmp_path: Path) -> None:
    solve = _solve(tmp_path, {"london_am": 0.0035})
    frac, info = _size(tmp_path, row=False, book={"gold_asia": 0.005}, solve=solve)
    assert frac == 0.0
    assert info["sources"]["london_am"] == "cert_book_absent"
    assert "stands aside" in info["absent"]["london_am"]


def test_explicit_zero_key_stays_zero(tmp_path: Path) -> None:
    solve = _solve(tmp_path, {"london_am": 0.0035})
    frac, info = _size(tmp_path, row=True, book={"gold_asia": 0.005, "gold_london_am": 0.0},
                       solve=solve)
    assert frac == 0.0
    assert info["sources"]["london_am"] == "cert_book"


def test_stale_fraction_is_a_rail_block_not_a_guess(tmp_path: Path) -> None:
    solve = _solve(tmp_path, {"london_am": 0.0035}, age_s=10 * 86400)
    assert solve is None
    frac, info = _size(tmp_path, row=True, book={"gold_asia": 0.005}, solve=solve)
    assert frac == 0.0
    assert info["sources"]["london_am"] == "cert_book_absent"
    assert g.ABSENT_KEY_DOOR_ROW in info["absent"]["london_am"]


def test_fraction_breaching_the_daily_floor_is_blocked_by_the_guard(tmp_path: Path) -> None:
    solve = _solve(tmp_path, {"london_am": 0.02})
    frac, _info = _size(tmp_path, row=True, book={"gold_asia": 0.005}, solve=solve)
    assert frac == 0.02
    # A day already down 2% of a 100k start: the existing guard's room is what binds.
    st = {"day": e8_guard.server_day(NOW), "day_start": 100_000.0, "peak_equity": 100_000.0}
    d = e8_guard.assess(98_000.0, now=NOW, state=st, persist=False)
    fits, _why = g.risk_budget_allows(0.0, 98_000.0 * frac, float(d.room_to_daily_floor))
    assert not fits
