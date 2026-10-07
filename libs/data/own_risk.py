"""THE PERMITTED RISK STATE -- a drop-in for VIXCLS built only from the desk's own data.

WHY (coordinator, 2026-10-07). FRED's ToU FAQ Q3: "Series with a copyright notice are owned by
third parties ... the Federal Reserve Bank of St. Louis cannot give you such permission." VIXCLS
carries CBOE's notice and BAMLH0A0HYM2 carries ICE's, so both are held by the terms gate
(`libs.data.terms_hold`), and VIXCLS fed the live capital path three ways: the allocator's regime
kernel `risk` dimension, the `d_vix` factor in the factor covariance, and the gateway macro lean.
This module is the stable name and the point-in-time reader those consumers switch to. The
builder is `desks/mt5/macro/own_risk_index.py` (hourly leg `ws_own_risk_index`).

THE SERIES (archive `data/own_risk_index.json`, the same `{"series": {id: [[d, v, avail], ...]}}`
shape as `data/fred_macro.json`, so a loader that reads `p[0], p[1]` reads it unchanged):

    OWN_VIX            the risk level. The broker's own VIX CFD close when the account lists one;
                       otherwise OWN_VIX_RV. Source named per row in the archive's `source`.
    OWN_VIX_RV         annualised Garman-Klass realised vol over 21 broker days, in PERCENT,
                       averaged over US500 and NAS100 (whichever this account lists)
    OWN_VIX_TERM       log(rv5 / rv63) on the same members: > 0 is the short end above the long
    OWN_VIX_INVERTED   1.0 when OWN_VIX_TERM > 0, else 0.0 (the term-inversion flag)
    OWN_CREDIT_STRESS  equity-implied credit stress: minus the 21-day log return of the US bank
                       basket and of US2000, each relative to US500, averaged. NOT a spread: a
                       Merton-style proxy from credit-sensitive equity CFDs. UNMEASURED (absent)
                       when the members are not listed or have no bars.

SCALE. OWN_VIX_RV is in the same units as VIX (annualised vol, percentage points) but it is
REALISED, not implied: it runs below VIX on average by the variance risk premium and reacts to a
shock one bar late rather than ahead of it. Every current VIXCLS consumer is scale-free --
`macro_view` and the regime kernel use its trailing RANK, `leg_factors` its DLOG change -- so the
swap needs no rescaling. Any consumer with an absolute VIX threshold must re-derive it on
OWN_VIX's own history; the builder writes a research-only fit against VIXCLS, where a held copy
exists on the host, to the gitignored `data/own_risk_vs_vixcls.json`, and that fit is never used
in production or tracked.

POINT IN TIME. Every point carries `available_time`: the close of the last H1 bar of its day
(our own bars), or for the CFD its daily close. `load_pit(as_of=t)` returns only points whose
available_time <= t, so a backtest reading it cannot see a value before the desk could.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data" / "own_risk_index.json"
DATA_SOURCE = "mt5:bars"

RISK = "OWN_VIX"
RISK_RV = "OWN_VIX_RV"
TERM = "OWN_VIX_TERM"
INVERTED = "OWN_VIX_INVERTED"
CREDIT = "OWN_CREDIT_STRESS"
SERIES = (RISK, RISK_RV, TERM, INVERTED, CREDIT)
#: the held FRED series each own series stands in for
REPLACES: dict[str, str] = {RISK: "VIXCLS", CREDIT: "BAMLH0A0HYM2"}


def _utc(text: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def load_doc(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or ARCHIVE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def load_pit(path: Path | None = None, as_of: datetime | None = None,
             names: tuple[str, ...] = SERIES) -> dict[str, list[tuple[str, float]]]:
    """series id -> [(date, value), ...] sorted, only points knowable by `as_of` (default now).
    A point without a readable available_time is dropped: unknown availability is never known."""
    cut = as_of or datetime.now(UTC)
    cut = cut if cut.tzinfo else cut.replace(tzinfo=UTC)
    out: dict[str, list[tuple[str, float]]] = {}
    for sid, pts in (load_doc(path).get("series") or {}).items():
        if sid not in names or not isinstance(pts, list):
            continue
        rows: list[tuple[str, float]] = []
        for p in pts:
            try:
                d, v, avail = str(p[0])[:10], float(p[1]), _utc(p[2])
            except (TypeError, ValueError, IndexError):
                continue
            if avail is not None and avail <= cut and math.isfinite(v) and len(d) == 10:
                rows.append((d, v))
        if rows:
            out[sid] = sorted(rows)
    return out


def available_at(series: str, day: str, path: Path | None = None) -> datetime | None:
    """When the desk first held `series` for `day`, or None."""
    for p in (load_doc(path).get("series") or {}).get(series) or []:
        if isinstance(p, list) and len(p) >= 3 and str(p[0])[:10] == day:
            return _utc(p[2])
    return None


def risk_series(path: Path | None = None, as_of: datetime | None = None
                ) -> dict[str, list[tuple[str, float]]]:
    """{"OWN_VIX": rows}: the permitted risk level under its OWN name. It is realised (or the
    broker's CFD), never VIXCLS, so a consumer re-keys to OWN_VIX rather than relabelling it."""
    got = load_pit(path, as_of, (RISK,))
    return {RISK: got[RISK]} if RISK in got else {}


__all__ = ["ARCHIVE", "CREDIT", "DATA_SOURCE", "INVERTED", "REPLACES", "RISK", "RISK_RV",
           "SERIES", "TERM", "available_at", "load_doc", "load_pit", "risk_series"]
