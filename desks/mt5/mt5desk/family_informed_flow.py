"""INFORMED FLOW DRIFT -- the executor for `desks/mt5/research/informed_capital.py`.

THE MECHANISM. People with an information or attention advantage -- an issuer's own officers and
directors, an activist crossing 5%, an institution enlarging a position, a legislator, and the
crowd pricing a macro contract -- disclose what they did, and the market under-reacts to the
disclosure because reading it is costly (the payer: holders who do not read filings) and acting
on it is limited (the constraint: short-sale cost on a sell, a benchmark that pins a long-only
book, and for the aggregate, the fact that no single name moved enough to be news). So the
instrument drifts after the instant the disclosure became public.

THREE RELATIONS, ONE FAMILY:
  direct     a filing about the issuer a share CFD tracks (news lane, `universe_policy.
             NEWS_LANE_FAMILIES`)
  aggregate  the day's abnormal insider or congressional buy share across every issuer, on the
             US index CFDs
  odds       a macro prediction-market contract's daily probability move, on the FX, index,
             gold, oil and rates legs its category names

THE FAMILY LOADS ITS OWN EVIDENCE, AND ONLY THE POINT-IN-TIME PART OF IT. Events come from the
organ's append-only store through `libs.research.informed_capital.observations` on the
OBSERVABLE clock -- SEC acceptance instant, or a date-only filing at the next UTC day 04:00, or
the venue's own price timestamp. The transaction date never reaches this file. The stamp is UTC
and the bar index is broker time, so it is converted by `libs.research.bar_clock` and an
unconvertible stamp is DROPPED, never used raw. Entry is the first bar OPENING at or after it,
through the same `_signals` the analyst families use (reused, not copied).

`symbol`, `source`, `relation` ARE REQUIRED KEYWORD ARGUMENTS so the sweep cannot call this blind
(`orthogonal_sweep._unsuppliable` names them): which events belong to which instrument is the
organ's measured evidence, not a searched parameter. `side` is the tracker's MEASURED sign.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from mt5desk.engine import Signal
from mt5desk.family_analyst_revision import _signals

from libs.research import analyst_views as av
from libs.research import informed_capital as ic

#: The organ's store. An environment override exists for tests and for a box with a moved tree.
STORE = Path(__file__).resolve().parents[1] / "data" / "informed_capital" / "events.jsonl"
RELATIONS = ("direct", "aggregate", "odds")
_CACHE: dict[str, Any] = {}


def store_path() -> Path:
    raw = os.environ.get("QUANT_INFORMED_CAPITAL_STORE", "")
    return Path(raw) if raw else STORE


def read_rows(path: Path) -> list[dict[str, Any]]:
    import json
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _observations(path: Path) -> list[av.Observation]:
    """Observable-clock observations, cached on (path, mtime, size): a sweep reads it once."""
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") != key:
        obs, _ = ic.observations(read_rows(path))
        _CACHE["key"] = key
        _CACHE["obs"] = obs
    obs = _CACHE.get("obs")
    return obs if isinstance(obs, list) else []


def event_times(symbol: str, source: str, relation: str, lead: str = "", *,
                path: Path | None = None) -> list[tuple[pd.Timestamp, int]]:
    """(knowable instant in the BARS' clock, net direction) per daily-netted observation."""
    mine = [o for o in _observations(path or store_path())
            if o.target == symbol and o.source == source and o.relation == relation
            and (not lead or o.lead == lead)]
    clock = av.bar_clock()
    out: list[tuple[pd.Timestamp, int]] = []
    for o in av.daily_net(mine):
        moved = clock(o.at)
        if moved is None:
            continue                      # an unplaceable stamp is dropped, never used raw
        out.append((pd.Timestamp(moved), o.direction))
    out.sort(key=lambda x: x[0])
    return out


def family_informed_flow_drift(
    df: pd.DataFrame,
    *,
    symbol: str,
    source: str,
    relation: str,
    lead: str = "",
    side: int = 1,
    hold_days: int = 5,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Follow (side=+1) or fade (-1) the net direction of the day's disclosed informed flow
    about `symbol` from `source`, holding about `hold_days` trading days. No store, no signals."""
    if relation not in RELATIONS:
        return []
    ev = event_times(symbol, source, relation, lead)
    return _signals(df, ev, side=side, hold_days=hold_days, atr_n=atr_n, stop_atr=stop_atr,
                    rr=rr, tag="informed_flow_drift")
