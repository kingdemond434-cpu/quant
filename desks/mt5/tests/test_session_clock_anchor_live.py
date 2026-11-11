"""No LIVE sleeve with a session selector loses a signal to the pass-2 clock (2026-10-06).

The filter moved from server hours (asia 0-8, london 8-16, ny 14-22) to each market's own clock,
and anchor-clocked families (open / close / gap / rollover) keep their anchor. Pinned per LIVE
sleeve in `data/sleeves.json`: on every weekday hour of 2024-2026, every signal the old filter
kept is still kept, so its signal count can only stay level or rise; and on a real tape the
sleeve's own family still fires in its session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import family_call as fc  # noqa: E402

#: The shared filter before pass 2 (family_call.SESSIONS on LIVE 2d61e69a1), server hours.
LEGACY = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22)}
#: Never measured or traded by research (binding rule); their live path is the gateway's own
#: WINDOWS table, which this change does not touch.
EXCLUDED_FAMILIES = {"discovered"}


def _live_selector_sleeves() -> list[dict]:
    path = _DESK / "data" / "sleeves.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else doc.get("sleeves", doc)
    rows = list(rows.values()) if isinstance(rows, dict) else rows
    return [r for r in rows if isinstance(r, dict) and r.get("status") == "LIVE"
            and r.get("selector") in LEGACY and r.get("family")
            and r["family"] not in EXCLUDED_FAMILIES]


def _legacy(sigs: list, session: str) -> list:
    lo, hi = LEGACY[session]
    return [g for g in sigs if lo <= g.time.hour < hi]


def _sleeve(r: dict) -> dict:
    return {"family": r["family"], "params": {"session": r["selector"]}}


def test_every_live_selector_sleeve_keeps_every_signal_the_old_filter_kept() -> None:
    rows = _live_selector_sleeves()
    if not rows:
        pytest.skip("no LIVE sleeve with a session selector in this tree")
    idx = pd.date_range("2024-01-01", "2026-09-30 23:00", freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    for r in rows:
        sigs = [SimpleNamespace(time=t, tag=r["family"]) for t in idx]
        before = _legacy(sigs, r["selector"])
        after = fc.certified_session_filter(sigs, _sleeve(r))
        assert len(after) >= len(before) > 0, r["name"]
        kept = {id(g) for g in after}
        assert all(id(g) in kept for g in before), r["name"]


def test_the_gap_family_still_fires_in_asia_on_a_real_tape() -> None:
    bars_path = _DESK / "data" / "universe" / "EURUSD_H1.parquet"
    fams = {r["family"] for r in _live_selector_sleeves()}
    if "overnight_gap_decay" not in fams or not bars_path.exists():
        pytest.skip("no LIVE overnight_gap_decay sleeve or no EURUSD H1 tape here")
    from mt5desk import families
    from mt5desk.families_orthogonal import family_overnight_gap_decay as fn
    bars = families._h1(pd.read_parquet(bars_path))
    raw = list(fn(bars))
    after = fc.signals(fn, bars, side=1, params={"session": "asia"})
    assert len(after) >= len(_legacy(raw, "asia")) > 0
