"""A FAMILY MAY REFUSE A CELL. IT MAY NOT TAKE THE SWEEP DOWN.

MEASURED 2026-09-12. `MT5-Gauntlet` exited 1 mid-docket and produced no certificates for an hour:

    family_event_reaction.py:140:  if not events or mode not in MODES or ...
    ValueError: The truth value of a DatetimeIndex is ambiguous.

`events` arrives as whatever the caller holds its stamps in, and for a pandas Index or Series
`bool(obj)` RAISES rather than answering. So the guard that existed to REJECT an empty input
instead threw, the exception escaped the family, and the whole sweep died -- taking every other
cell in the docket with it, including thousands that had nothing to do with events.

THE BUG WAS LATENT FOR AS LONG AS THE FAMILY EXISTED. Nothing reached an event_reaction cell,
because the docket rotated by symbol and those cells sat at the tail forever. It surfaced the hour
never-judged cells were promoted to the front -- which is the correct behaviour finding a real
defect, not causing one.

THE PROPERTY, stated so it cannot regress: every family entrypoint must be TOTAL over its
declared inputs. Handed an empty list, an empty Index, an empty Series, or None, it returns no
signals. It does not raise. A cell the desk cannot judge is a cell REFUSED, which is a verdict;
an exception is an outage, and the difference is the whole docket.

WHY TRUTHINESS IS THE RULE AND NOT A STYLE NOTE. `if not x` on a container is fine for lists and
dicts and is a LANDMINE for anything pandas returns. The desk cannot audit every call site's
argument type forever, so the families are tested against the shapes they actually receive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _bars(n: int = 400) -> pd.DataFrame:
    """An ordinary H1 frame, tz-aware like the desk's own, so the family gets past its shape
    checks and actually reaches the guard under test."""
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    base = np.linspace(2000.0, 2100.0, n)
    return pd.DataFrame(
        {"open": base, "high": base + 1.0, "low": base - 1.0, "close": base,
         "tick_volume": np.full(n, 100.0)}, index=idx)


#: The shapes an "empty events" argument actually arrives as. The DatetimeIndex is the one that
#: took the sweep down; the others are here because the next caller will pick a different one.
EMPTY_SHAPES = [
    pytest.param([], id="empty-list"),
    pytest.param((), id="empty-tuple"),
    pytest.param(pd.DatetimeIndex([]), id="empty-DatetimeIndex"),
    pytest.param(pd.Index([]), id="empty-Index"),
    pytest.param(pd.Series(dtype="float64"), id="empty-Series"),
    pytest.param(pd.DataFrame(), id="empty-DataFrame"),
    pytest.param(None, id="None"),
]

#: A NON-empty index is just as dangerous: `bool(idx)` raises whether or not it holds anything, so
#: a guard that only got tested against `[]` would still take the sweep down on real data.
NONEMPTY_SHAPES = [
    pytest.param(pd.DatetimeIndex(pd.date_range("2026-01-02", periods=3, tz="UTC")),
                 id="nonempty-DatetimeIndex"),
    pytest.param(pd.Index([1, 2, 3]), id="nonempty-Index"),
    pytest.param(pd.Series([1.0, 2.0]), id="nonempty-Series"),
]


@pytest.mark.parametrize("events", EMPTY_SHAPES)
def test_event_reaction_refuses_empty_events_without_raising(events) -> None:
    from mt5desk.family_event_reaction import family_event_reaction
    out = family_event_reaction(_bars(), events=events, mode="drift", side=1,
                                symbol="XAUUSD", clock="utc")
    assert out == [] or len(out) == 0


@pytest.mark.parametrize("events", NONEMPTY_SHAPES)
def test_event_reaction_does_not_raise_on_index_like_events(events) -> None:
    """It may return nothing -- these carry no usable stamps -- but it must not throw."""
    from mt5desk.family_event_reaction import family_event_reaction
    out = family_event_reaction(_bars(), events=events, mode="drift", side=1,
                                symbol="XAUUSD", clock="utc")
    assert isinstance(out, list)


def test_the_truthiness_guard_itself_is_gone() -> None:
    """Pin the FIX, not only the behaviour.

    The behavioural tests above would pass again the moment somebody rewrote the guard back to
    `if not events` AND the caller happened to pass a list that day. This reads the source, so the
    landmine cannot be reintroduced and then hidden by a lucky argument type.
    """
    src = (_DESK / "mt5desk" / "family_event_reaction.py").read_text(encoding="utf-8")
    offenders = [ln.strip() for ln in src.splitlines()
                 if ln.strip().startswith("if not events")]
    assert not offenders, (
        "`if not events` is back. bool() on a pandas Index RAISES rather than answering, which "
        "took the whole gauntlet sweep down on 2026-09-12. Test emptiness with `len()` behind an "
        "`is None` guard:\n  " + "\n  ".join(offenders))
