"""EVERY LIVE SLEEVE RESOLVES TO CODE THAT CAN RUN IT, OR THIS FAILS.

THE PRINCIPAL'S ASK, 2026-09-12: "make all the 43 executable permanently" and "never reverting".
A sleeve written LIVE in `data/sleeves.json` is a claim that the gateway will trade it. If no
lane on this tree can construct its signals, that claim is false and the sleeve is a row that
looks funded and places nothing -- the quietest failure this desk has, because every count, every
heat calculation and every dashboard tile includes it.

MEASURED 2026-09-12, which is why this exists. Of 43 LIVE sleeves, `get_family_func` resolved 35.
The eight it missed were not eight dead sleeves; they were THREE DIFFERENT THINGS, and only one
was a defect:

  * `dav_range_filter_adx` -- a REAL defect. It lives in hunt16, and `get_family_func` fell
    through to ORTHOGONAL_FAMILIES but never to hunt16, while `executables.resolve_family` checks
    hunt16 FIRST. Two lanes disagreeing about whether a live sleeve could be executed at all.
  * `anti_donchian_breakout` -- the SCALP lane's family, resolved by the scalp lane.
  * six `gold_*_v2/v3/v4` rows -- forward-clock registry rows that carry no family by design and
    map onto ONE gateway window each (CLAUDE.md: "The four XAUUSD.asia registry rows are forward
    clocks that all map to ONE gateway window, gold_asia").

SO THE TEST ASKS THE RIGHT QUESTION, WHICH IS NOT "does families.py know it". It asks whether ANY
lane the gateway actually uses can run this row. A row that no lane answers for is the defect; a
row answered by a lane other than the one you first thought of is not.

WHY A TEST AND NOT A HEALER. A healer repairs the symptom on a schedule and the cause comes back
-- which is precisely the "it keeps reverting" the principal has reported for days. A test fails
the suite the moment a LIVE row stops being executable, so the cause is fixed once. That is what
"permanently" has to mean for it to mean anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = _DESK / "data" / "sleeves.json"

#: Rows the gateway runs WITHOUT a family constructor, because another lane owns them.
#:
#: The gold book is executed from `decision_core.GOLD_WINDOWS` on the bracket lane: the registry
#: rows exist so each window has its own forward clock and its own promotion record, and several
#: rows intentionally map onto one window. Requiring a family of them would be requiring the wrong
#: thing -- and inventing one to satisfy this test would put a second, disagreeing executor behind
#: the only forward-evidenced book on the desk.
_BRACKET_LANE_PREFIXES = ("gold_asia", "gold_london_am", "gold_afternoon", "gold_ny_open")


def _rows() -> list[dict]:
    if not SLEEVES.exists():
        pytest.skip(f"{SLEEVES} absent on this checkout")
    doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    return [r for r in rows if isinstance(r, dict)]


def _live() -> list[dict]:
    return [r for r in _rows() if str(r.get("status", "")).upper() == "LIVE"]


def _resolves(fam: str) -> bool:
    """Any lane. `resolve_family` is the forward engine's order (hunt16, families, orthogonal);
    `get_family_func` is the backtest/pipeline lane. Either answering is enough for the row to be
    runnable, and the two are checked separately so a future divergence between them is visible
    rather than hidden behind an `or`."""
    ok = False
    try:
        from mt5desk.executables import resolve_family
        ok = ok or resolve_family(fam) is not None
    except Exception:
        pass
    try:
        from mt5desk.families import get_family_func
        ok = ok or get_family_func(fam) is not None
    except Exception:
        pass
    return ok


def test_every_live_sleeve_is_runnable_by_some_lane() -> None:
    dead: list[str] = []
    for r in _live():
        name = str(r.get("name") or "?")
        fam = str(r.get("family") or "")
        if not fam:
            # No family is only legitimate on the bracket lane, which runs from GOLD_WINDOWS.
            if name.startswith(_BRACKET_LANE_PREFIXES):
                continue
            dead.append(f"{name}: LIVE with no family and not a bracket-lane row")
            continue
        if not _resolves(fam):
            dead.append(f"{name}: family {fam!r} resolves in NO lane "
                        f"(hunt16, families, families_orthogonal)")
    assert not dead, (
        f"{len(dead)} LIVE sleeve(s) cannot be executed by any lane on this tree. A LIVE row is a "
        f"claim the gateway will trade it; a row nothing can construct places nothing while "
        f"counting toward every sleeve count, heat figure and dashboard tile:\n  "
        + "\n  ".join(dead))


def test_the_two_family_lanes_agree_about_every_live_sleeve() -> None:
    """They disagreed on 2026-09-12 and a live sleeve fell in the gap. Pin that they cannot again.

    `resolve_family` checked hunt16 first; `get_family_func` never checked it at all. So
    `dav_range_filter_adx` was executable to the forward engine and unknown to the backtest lane,
    which means the two lanes were testing and trading different books.
    """
    try:
        from mt5desk.executables import resolve_family
        from mt5desk.families import get_family_func
    except Exception as exc:  # pragma: no cover - import environment
        pytest.skip(f"family lanes unimportable here: {exc}")
    disagree = []
    for r in _live():
        fam = str(r.get("family") or "")
        if not fam:
            continue
        a = resolve_family(fam) is not None
        b = get_family_func(fam) is not None
        if a != b:
            disagree.append(f"{fam}: resolve_family={a} get_family_func={b}")
    assert not disagree, (
        "the forward lane and the backtest lane disagree about which LIVE families exist, so the "
        "desk is testing one book and trading another:\n  " + "\n  ".join(sorted(set(disagree))))


def test_every_live_sleeve_names_a_symbol() -> None:
    """A sleeve with no symbol cannot be priced, sized, or sent, whatever its family says."""
    missing = [str(r.get("name") or "?") for r in _live() if not str(r.get("symbol") or "").strip()]
    assert not missing, f"LIVE sleeve(s) with no symbol: {missing}"
