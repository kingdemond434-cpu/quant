"""INSIDER CLUSTER DRIFT -- the share-CFD event lane's executor for Form 4 purchase clusters.

THE MECHANISM. Several officers and directors buying their own company's stock with their own
money, inside a few days, is information the market under-reacts to: the filing is public within
two business days, but attention is finite and the names are many, so the price drifts toward the
insiders' view over the following days (the classic insider-purchase drift; Seyhun 1986, Lakonishok
& Lee 2001, Cohen-Malloy-Pomorski 2012 on "opportunistic" buys). The PAYER is the under-reacting
holder (`axis_registry`: trend_persistence / event); the constraint is attention.

THE EVENTS ARE THE LANE'S OWN, POINT-IN-TIME. `research/form4_lane.py` parses Form 4 filings,
keeps only open-market purchases (code `P`; `libs.research.form4.NOT_A_DECISION` names why every
other code is not a decision), scores clusters with `libs.research.form4.clusters` and writes them
to `data/form4/clusters.jsonl` stamped at `knowable_at` -- the LATEST SEC acceptance time in the
cluster, never a transaction date. This family reads that store for `symbol` only, converts each
UTC stamp into the bars' own broker clock (`libs.research.bar_clock`, an unconvertible stamp is
DROPPED), and enters on the first bar that OPENS at or after it. The placement and the hold are
`family_analyst_revision._signals`, the event lane's one entry rule, reused rather than copied.

A SHARE CFD IS ADMITTED BECAUSE THIS IS THE EVENT LANE (the two-lane order, amended 2026-09-30:
"cross sectional and news"). The family fires only on a dated public filing ABOUT the name, so it
sits in `universe_policy.NEWS_LANE_FAMILIES`; no statistical hunt over the name's price path runs.

`symbol` IS A REQUIRED KEYWORD so the orthogonal sweep can never call it blind.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from mt5desk.engine import Signal
from mt5desk.family_analyst_revision import _signals

#: The lane's cluster store. An environment override exists for tests and a moved tree.
STORE = Path(__file__).resolve().parents[1] / "data" / "form4" / "clusters.jsonl"
_CACHE: dict[str, Any] = {}


def store_path() -> Path:
    raw = os.environ.get("QUANT_FORM4_STORE", "")
    return Path(raw) if raw else STORE


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") != key:
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
        _CACHE.update({"key": key, "rows": rows})
    out = _CACHE.get("rows")
    return out if isinstance(out, list) else []


def event_times(symbol: str, *, min_score: float = 0.0, path: Path | None = None
                ) -> list[tuple[pd.Timestamp, int]]:
    """(knowable instant in the BARS' clock, +1) per cluster on `symbol`, sorted."""
    from libs.research.bar_clock import to_bar_time
    out: list[tuple[pd.Timestamp, int]] = []
    for r in _rows(path or store_path()):
        if str(r.get("symbol")) != symbol:
            continue
        try:
            score = float(r.get("score") or 0.0)
        except (TypeError, ValueError):
            continue
        if score < float(min_score):
            continue
        try:
            at = pd.Timestamp(str(r.get("knowable_at")))
        except (TypeError, ValueError):
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
    hold_days: int = 5,
    min_score: float = 0.0,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Long `symbol` from the first bar after an insider purchase cluster became public, held
    about `hold_days` trading days. No store, or no cluster on this name: no signals."""
    ev = event_times(symbol, min_score=min_score)
    return _signals(df, ev, side=1, hold_days=hold_days, atr_n=atr_n, stop_atr=stop_atr,
                    rr=rr, tag="insider_cluster_drift")
