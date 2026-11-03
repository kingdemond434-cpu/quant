"""INSIDER CLUSTER DRIFT -- the share-CFD event lane's executor for dated single-name filings.

THE MECHANISM. Several officers and directors buying their own company's stock with their own
money, inside a few days, is information the market under-reacts to: the filing is public within
two business days, but attention is finite and the names are many, so the price drifts toward the
insiders' view over the following days (Seyhun 1986; Lakonishok & Lee 2001; Cohen, Malloy &
Pomorski 2012 on "opportunistic" buys). The payer is the under-reacting holder; the constraint is
attention.

THE EVENTS ARE THE LANE'S OWN, POINT-IN-TIME. `research/insider_event_lane.py` (with
`research/form4_lane.py`) keeps only open-market purchases (code P), freezes each cluster at
`knowable_at` -- the LATEST SEC acceptance time in it, never a transaction date -- and appends it
to `data/insider_events/clusters.jsonl`. This family reads that store for `symbol` only, converts
each UTC stamp onto the bars' broker clock (`libs.research.bar_clock`; an unconvertible stamp is
DROPPED, never used raw) and enters on the first bar that OPENS at or after it, with the event
lane's one entry rule (`family_analyst_revision._signals`).

`source="congress"` READS DISCLOSED CONGRESSIONAL NET BUYS INSTEAD, and only while the principal's
switch `QUANT_CONGRESS_ATTEST` reads exactly "1" (5 U.S.C. 13107(c); the gate of draft PR #641).
Switched off, the family returns no signals whatever is on disk.

A SHARE CFD IS ADMITTED BECAUSE THIS IS THE EVENT LANE: the family fires only on a dated public
filing ABOUT the name (`universe_policy.NEWS_LANE_FAMILIES`). `symbol` is a REQUIRED keyword, so
the orthogonal sweep can never call it blind, and the sealed gauntlet builds it through its plain
`fn(h1, **params)` call because the family loads its own events.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from mt5desk.engine import Signal
from mt5desk.family_analyst_revision import _signals

#: The lane's stores. An environment override exists for tests and a moved tree.
STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "insider_events"
STORES = {"form4": "clusters.jsonl", "congress": "congress_events.jsonl"}
_CACHE: dict[str, Any] = {}


def store_path(source: str = "form4") -> Path | None:
    name = STORES.get(str(source))
    if name is None:
        return None
    raw = os.environ.get("QUANT_INSIDER_EVENTS_DIR", "")
    return (Path(raw) if raw else STORE_DIR) / name


def _congress_on() -> bool:
    try:
        from libs.data import congress_gate as cg  # type: ignore[attr-defined]
        return bool(cg.attested())
    except ImportError:
        return str(os.environ.get("QUANT_CONGRESS_ATTEST", "")).strip() == "1"


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    hit = _CACHE.get(str(path))
    if isinstance(hit, tuple) and hit[0] == key:
        return list(hit[1])
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except OSError:
        rows = []
    _CACHE[str(path)] = (key, rows)
    return list(rows)


def event_times(symbol: str, *, source: str = "form4", min_score: float = 0.0,
                path: Path | None = None) -> list[tuple[pd.Timestamp, int]]:
    """(knowable instant in the BARS' clock, +1) per event on `symbol`, sorted."""
    from libs.research.bar_clock import to_bar_time
    if source == "congress" and not _congress_on():
        return []
    p = path or store_path(source)
    if p is None:
        return []
    out: list[tuple[pd.Timestamp, int]] = []
    for r in _rows(p):
        if str(r.get("symbol")) != symbol:
            continue
        try:
            score = float(r.get("score") or 0.0)
        except (TypeError, ValueError):
            continue
        if score < float(min_score):
            continue
        try:
            at = pd.Timestamp(str(r.get("knowable_at") or r.get("at")))
        except (TypeError, ValueError):
            continue
        if at is pd.NaT:
            continue
        if at.tzinfo is None:
            at = at.tz_localize("UTC")
        moved, _status, _why = to_bar_time(at.to_pydatetime())
        if moved is None:
            continue                       # an unplaceable stamp is dropped, never used raw
        out.append((pd.Timestamp(moved), 1))
    out.sort(key=lambda x: x[0])
    return out


def family_insider_cluster_drift(
    df: pd.DataFrame,
    *,
    symbol: str,
    source: str = "form4",
    hold_days: int = 5,
    min_score: float = 0.0,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Long `symbol` from the first bar after a dated insider (or, attested, congressional)
    purchase became public, held about `hold_days` trading days. No store: no signals."""
    ev = event_times(symbol, source=source, min_score=min_score)
    return list(_signals(df, ev, side=1, hold_days=hold_days, atr_n=atr_n, stop_atr=stop_atr,
                    rr=rr, tag=f"insider_cluster_drift:{source}"))
