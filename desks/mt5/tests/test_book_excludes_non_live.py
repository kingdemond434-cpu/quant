"""An ARMED book never funds a roster row the desk may not trade (2026-10-20 23:14Z incident)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pf_allocator as pa  # noqa: E402


def _roster(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
    return p


def test_retired_and_standby_rows_get_zero_and_nothing_is_respread(tmp_path: Path) -> None:
    p = _roster(tmp_path, [
        {"name": "xau_m5_anti_breakout_overlap", "symbol": "XAUUSD", "status": "RETIRED"},
        {"name": "eur_standby", "symbol": "EURUSD", "status": "STANDBY"},
        {"name": "gold_asia_v2", "symbol": "XAUUSD", "status": "LIVE"},
    ])
    book = {"xau_m5_anti_breakout_overlap": 0.042909, "eur_standby": 0.01,
            "gold_asia": 0.05, "unrostered_key": 0.02}
    kept, excluded = pa.exclude_non_live(book, p)
    assert set(excluded) == {"xau_m5_anti_breakout_overlap", "eur_standby"}
    assert "RETIRED" in excluded["xau_m5_anti_breakout_overlap"]
    # gold_asia is joined by the LIVE gold_asia_v2; a key naming no row is left to the gateway.
    assert kept == {"gold_asia": 0.05, "unrostered_key": 0.02}
    assert sum(kept.values()) < sum(book.values())        # total falls: no re-spread


def test_unreadable_roster_excludes_nothing(tmp_path: Path) -> None:
    kept, excluded = pa.exclude_non_live({"a": 0.1}, tmp_path / "absent.json")
    assert kept == {"a": 0.1} and excluded == {}
