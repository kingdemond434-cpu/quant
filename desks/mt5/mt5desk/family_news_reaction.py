"""UNSCHEDULED NEWS REACTION -- post-headline drift or reversal, conditioned on the reaction's
SIGN and SIZE. The family module `research/empty_cluster_forcer.MISSING_ARTIFACT` names for the
`news_reaction` cluster.

WHY THIS IS NOT `event_reaction` UNDER ANOTHER NAME. `event_reaction` (cluster `event_surprise`)
trades the SCHEDULED release, whose clock is the calendar and whose surprise is actual minus
consensus. This family trades the UNSCHEDULED headline: the rows `research/news_event_stream`
writes to `data/events/events.jsonl` whose `surprise_basis` says the world did not know it was
coming. A scheduled row -- even one the stream matched to a calendar z -- is EXCLUDED here; it
belongs to `event_surprise`, and relabelling it would make the cluster register green while
changing nothing (the forcer's own warning).

THE SURPRISE OF AN UNSCHEDULED HEADLINE HAS NO CONSENSUS, so its sign and size are the MARKET'S
first reading of it: the move from the last close before the headline to the close of the bar on
which the desk could first act, in units of the ATR known BEFORE the headline. `news_event_stream`
carries no signed number for an unscheduled row (`event_ontology.surprise_of` scores them all 1.0),
so the tape is the only honest signed measurement; it is read only up to the decision bar.

    mode="drift"     trade WITH the first reaction  (under-reaction, slow diffusion)
    mode="reversal"  trade AGAINST it                (over-reaction by the first repricers)

`surprise_sign` selects which reactions a cell trades (+1 up-moves, -1 down-moves), and `size_q`
keeps only reactions at or above that quantile of the SAME symbol's strictly-earlier reaction
sizes. The quantile is expanding and point-in-time: it needs MIN_HISTORY earlier events before it
exists, and until then nothing is traded rather than a threshold being guessed.

POINT-IN-TIME, BY CONSTRUCTION.
  * One story is one event: the FIRST row of an `id` (the stream's event id) is the headline;
    follow-ups on the same story are echo, not new events.
  * The headline instant is `knowable_at` (when the world could know), falling back to `seen_at`.
  * The row is USABLE only from the LATEST of `knowable_at`, `seen_at` and the stream's own pass
    stamp `at` -- the moment the row existed on the desk. A row with none of them is dropped.
  * Stamps are UTC; the bar index is broker time (New York + 7h, `libs/regime/session_clock`), so
    the instants are moved INTO the bars' frame (`family_alt_release.to_broker`); bars never move.
  * The decision bar is the bar whose interval contains the usable instant; the engine fills at
    the NEXT bar's open, which is therefore strictly after the instant.

Nothing here sizes or vetoes. No log, no matching row, no history: [] -- never a price-only
fallback. The family PROPOSES; the gauntlet judges.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Where `research/news_event_stream.py` appends its fast-lane rows (its EVENT_LOG).
EVENT_LOG = Path(__file__).resolve().parents[1] / "data" / "events" / "events.jsonl"

MODES = ("drift", "reversal")
#: Earlier reactions on the same symbol before a size quantile is defined.
MIN_HISTORY = 10
#: The prefix `event_ontology.surprise_of` writes on every unscheduled row.
UNSCHEDULED_BASIS = "unscheduled"

_CACHE: dict[tuple[str, float, int], list[dict[str, Any]]] = {}


def _ts(value: Any) -> pd.Timestamp | None:
    if not value or str(value).upper() == "UNMEASURED":
        return None
    try:
        t = pd.Timestamp(str(value))
    except (TypeError, ValueError):
        return None
    if t is pd.NaT:
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = (str(path), st.st_mtime, st.st_size)
    if key in _CACHE:
        return _CACHE[key]
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    if len(_CACHE) > 8:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def _assets(row: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for a in row.get("affected") or ():
        if isinstance(a, dict) and a.get("asset"):
            out.add(str(a["asset"]).upper())
        elif isinstance(a, str):
            out.add(a.upper())
    return out


def headlines(symbol: str, rows: Iterable[dict[str, Any]]
              ) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """(headline instant, usable instant, event id) per UNSCHEDULED story naming `symbol`, in UTC,
    first row of each story only, sorted by usable instant."""
    sym = str(symbol or "").upper()
    seen: set[str] = set()
    out: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for row in rows:
        if str(row.get("kind") or "other") == "other":
            continue
        if not str(row.get("surprise_basis") or "").startswith(UNSCHEDULED_BASIS):
            continue
        if sym not in _assets(row):
            continue
        eid = str(row.get("id") or row.get("event_id") or row.get("item_id") or "")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        known, seen_at, passed = (_ts(row.get("knowable_at")), _ts(row.get("seen_at")),
                                  _ts(row.get("at")))
        head = known or seen_at
        stamps = [t for t in (known, seen_at, passed) if t is not None]
        if head is None or not stamps:
            continue
        out.append((head, max(stamps), eid))
    out.sort(key=lambda r: r[1])
    return out


def news_reaction_signals(
    df: pd.DataFrame,
    *,
    symbol: str,
    mode: str = "drift",
    surprise_sign: int = 1,
    size_q: float = 0.5,
    hold_bars: int = 12,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    atr_n: int = 20,
    max_lag_bars: int = 4,
    event_log: Path | None = None,
) -> list[Any]:
    from mt5desk.families import Signal, _atr, _h1
    from mt5desk.family_alt_release import to_broker

    if mode not in MODES or int(surprise_sign) not in (1, -1) or not 0.0 <= float(size_q) < 1.0:
        return []
    ev = headlines(symbol, _rows(event_log or EVENT_LOG))
    if not ev:
        return []
    d = _h1(df)
    if len(d) < atr_n + 4:
        return []
    index = pd.DatetimeIndex(d.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    close = d["close"].astype(float).to_numpy()
    atr = _atr(d, atr_n).to_numpy()
    hold = max(1, int(hold_bars))
    history: list[float] = []
    out: list[Any] = []
    busy_until = -1
    for head, usable, eid in ev:
        # bar containing the headline, and the bar containing the usable instant (decision bar)
        c = int(index.searchsorted(to_broker(head), side="right")) - 1
        i0 = int(index.searchsorted(to_broker(usable), side="right")) - 1
        if c < 1 or i0 < c or i0 >= len(d) - 1 or i0 - c > int(max_lag_bars):
            continue
        a = float(atr[c - 1])  # ATR known before the headline
        if not np.isfinite(a) or a <= 0:
            continue
        r = float(close[i0] - close[c - 1])
        size = abs(r) / a
        if not np.isfinite(size):
            continue
        # the threshold is read from strictly-earlier events, then this event joins the history
        thr = (float(np.quantile(history, float(size_q))) if len(history) >= MIN_HISTORY
               else None)
        history.append(size)
        if thr is None or size < thr or r == 0:
            continue
        sign = 1 if r > 0 else -1
        if sign != int(surprise_sign) or i0 <= busy_until:
            continue
        s = sign if mode == "drift" else -sign
        a_now = float(atr[i0])
        if not np.isfinite(a_now) or a_now <= 0:
            continue
        px = float(close[i0])
        out.append(Signal(time=d.index[i0], side=s, stop=px - s * stop_atr * a_now,
                          target=px + s * stop_atr * a_now * rr, ttl_bars=hold,
                          tag=f"news_reaction:{mode}:{eid}", trigger=None, wait_bars=1))
        busy_until = i0 + hold
    return out
