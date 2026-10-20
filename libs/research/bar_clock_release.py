"""The bar clock MEASURED FROM THE DESK'S OWN DATA, for when `BAR_CLOCK.json` is absent.

WHY (2026-10-20, judge never_fires follow-up). `bar_clock.offsets()` reads one file,
`desks/mt5/reports/BAR_CLOCK.json`, which `research/futures_lead_lag.py` writes from a Yahoo feed
stamped in epoch seconds. That file is gitignored and box-local, and where it is missing every
UTC join is dropped: `family_event_reaction` placed 0 of 198 calendar events, so 3,209
event_reaction cells per sweep came back never_fires on bars that were present. The cells were not
scarce; the clock was unread.

THE MEASUREMENT. A high-impact scheduled release is an instant stamped in genuine UTC by the
calendar (`event_date` carries its own offset, e.g. `-04:00`), and it makes the largest bar range
of its day on the instruments quoted in its currency. So for each candidate offset k the bar the
release WOULD sit in -- the bar labelled `release + k hours` -- is looked up, and its range is
compared with the instrument's median bar range. On the broker's clock the spike sits at exactly
one k. Measured on this tree (summer, 2026-08-23..09-12, 6-8 releases per instrument), every
instrument resolves +3 and no other hour comes close:

    XAUUSD M5   k=+3 10.35x   next best k=+4 2.64x
    EURUSD H1   k=+3  3.12x   next best k=+4 1.88x
    GBPUSD H1   k=+3  2.14x   next best k=+4 1.20x
    USDJPY H1   k=+3  3.14x   next best k=+4 1.82x
    AUDUSD H1   k=+3  2.72x   next best k=+4 1.03x

That agrees with the +3 summer offset `futures_lead_lag` documents, by a different instrument
(the release, not a futures feed) with the same property: the reference stamp is UTC by
construction and carries no convention to be wrong about.

WHAT IT KEEPS FROM `bar_clock`, unchanged:

  * NO GUESS. A season resolves only when at least MIN_INSTRUMENTS instruments each resolve one k
    clearly (best spike >= MIN_SPIKE x the median bar and >= MIN_MARGIN x the runner-up) on at
    least MIN_EVENTS releases, and all of them agree. Otherwise the season is absent and the
    caller drops the join exactly as before.
  * SEASONS ARE MEASURED SEPARATELY, from releases inside that season's window only. The shoulder
    months are still refused by `bar_clock.to_bar_time`; this never answers for them.
  * NAIVE STAMPS ARE NOT USED. A release time with no offset of its own is on an unknown clock and
    cannot be a reference for one.
  * NOTHING IS WRITTEN. The reading is computed in-process from files already on disk and cached
    for the process; the measured file, when present, always wins.

It reads only the price path's RANGE around a release, never its direction, so it cannot favour
either side of a drift/fade hypothesis that is later judged on the same bars.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

#: The desk's own UTC-stamped release calendar.
CALENDAR_REL = "desks/mt5/data/intelligence/ff_calendar_vintage"
UNIVERSE_REL = "desks/mt5/data/universe"

#: Liquid instruments quoted in the currencies the calendar's high-impact releases name. The
#: first chart that exists, finest first, is read; an absent instrument simply does not vote.
INSTRUMENTS: tuple[str, ...] = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
                                "NZDUSD", "USDCHF")
CHARTS: tuple[str, ...] = ("M5", "M15", "H1")

#: Candidate offsets, wider than any broker uses so the answer is not boxed in by the search.
CANDIDATES: tuple[int, ...] = tuple(range(-2, 7))

MIN_EVENTS = 5
MIN_INSTRUMENTS = 3
MIN_SPIKE = 2.0
MIN_MARGIN = 1.5

#: Re-check the inputs' signature at most this often inside one process.
RECHECK_S = 600.0

_CACHE: dict[str, tuple[float, tuple[tuple[str, int, int], ...], dict[str, Any]]] = {}


def _rows(path: Path) -> list[dict[str, Any]]:
    """Every row of one calendar vintage: a JSON list/{rows}, or JSON lines (optionally gzip)."""
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = path.read_text(encoding="utf-8")
    except (OSError, ValueError, EOFError):
        return []
    try:
        doc = json.loads(text)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows", [])
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except ValueError:
        pass
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def calendar_files(root: Path) -> list[Path]:
    base = root / Path(*CALENDAR_REL.split("/"))
    return sorted(base.glob("*.json*")) if base.exists() else []


def _releases(root: Path) -> list[tuple[Any, frozenset[str]]]:
    """(UTC instant, currencies) of every high-impact release with an explicit offset."""
    import pandas as pd
    seen: dict[Any, set[str]] = {}
    for path in calendar_files(root):
        for row in _rows(path):
            if str(row.get("impact", "")).lower() != "high":
                continue
            raw = row.get("event_date")
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                ts = pd.Timestamp(raw)
            except (TypeError, ValueError):
                continue
            if ts is pd.NaT or ts.tzinfo is None:
                continue
            ccys = {str(c).upper() for c in (row.get("symbols") or []) if isinstance(c, str)}
            seen.setdefault(ts.tz_convert("UTC"), set()).update(ccys)
    return sorted((t, frozenset(c)) for t, c in seen.items())


def _bars(root: Path, symbol: str) -> tuple[str, Any] | None:
    import pandas as pd
    base = root / Path(*UNIVERSE_REL.split("/"))
    for chart in CHARTS:
        path = base / f"{symbol}_{chart}.parquet"
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path, columns=["high", "low", "close"])
        except (OSError, ValueError, KeyError):
            continue
        if not isinstance(frame.index, pd.DatetimeIndex) or len(frame) < 100:
            continue
        idx = frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
        frame = frame.set_axis(idx).sort_index()
        return chart, frame[~frame.index.duplicated(keep="last")]
    return None


def _instrument(chart_frame: tuple[str, Any], times: list[Any]) -> dict[str, Any]:
    """The offset at which this instrument's release spike sits, or None when unclear."""
    import numpy as np
    import pandas as pd
    chart, frame = chart_frame
    rng = ((frame["high"] - frame["low"]) / frame["close"]).astype(float)
    rng = rng[np.isfinite(rng)]
    base = float(rng.median()) if len(rng) else 0.0
    if base <= 0:
        return {"chart": chart, "offset_h": None, "why": "no measurable bar range"}
    step = pd.Timedelta(frame.index.to_series().diff().median())
    width = max(step, pd.Timedelta(minutes=10))
    index = rng.index
    spikes: dict[int, float] = {}
    n_used = 0
    for k in CANDIDATES:
        vals = []
        for t in times:
            start = (t.tz_convert("UTC").tz_localize(None) + pd.Timedelta(hours=k)).floor(step)
            lo = int(index.searchsorted(start, side="left"))
            hi = int(index.searchsorted(start + width, side="left"))
            if hi > lo:
                vals.append(float(rng.iloc[lo:hi].max()) / base)
        if vals:
            spikes[k] = float(np.median(vals))
            n_used = max(n_used, len(vals))
    out: dict[str, Any] = {"chart": chart, "n_releases": n_used,
                           "spike_by_offset": {str(k): round(v, 3) for k, v in spikes.items()}}
    if n_used < MIN_EVENTS or len(spikes) < 2:
        return {**out, "offset_h": None, "why": f"{n_used} releases on bars, under {MIN_EVENTS}"}
    ranked = sorted(spikes.items(), key=lambda kv: kv[1], reverse=True)
    (best_k, best), (_k2, second) = ranked[0], ranked[1]
    if best < MIN_SPIKE or best < MIN_MARGIN * second:
        return {**out, "offset_h": None,
                "why": f"no clear spike: best {best:.2f}x at {best_k:+d}h, next {second:.2f}x"}
    return {**out, "offset_h": int(best_k)}


def measure(root: Path) -> dict[str, Any]:
    """{per_season: {name: {offset_h, agrees_across_pairs, readings}}} from the release spikes."""
    from libs.research.bar_clock import SEASON_WINDOWS, season_of
    releases = _releases(root)
    frames = {s: fb for s in INSTRUMENTS if (fb := _bars(root, s)) is not None}
    per_season: dict[str, Any] = {}
    for season in SEASON_WINDOWS:
        readings: dict[str, Any] = {}
        for sym, fb in frames.items():
            ccys = {sym[:3], sym[3:6]}
            times = [t for t, c in releases
                     if c & ccys and season_of(t.to_pydatetime()) == season]
            readings[sym] = _instrument(fb, times)
        offs = {r["offset_h"] for r in readings.values() if r.get("offset_h") is not None}
        voters = sum(1 for r in readings.values() if r.get("offset_h") is not None)
        agrees = len(offs) == 1 and voters >= MIN_INSTRUMENTS
        per_season[season] = {"offset_h": next(iter(offs)) if agrees else None,
                              "agrees_across_pairs": agrees, "instruments_resolved": voters,
                              "readings": readings}
    return {"measured_by": ("release-spike alignment: the bar labelled release+k hours carries "
                            "the day's range spike only at the broker's true offset; releases are "
                            "UTC-stamped by the calendar with their own offset"),
            "n_releases": len(releases), "per_season": per_season}


def _signature(root: Path) -> tuple[tuple[str, int, int], ...]:
    sig: list[tuple[str, int, int]] = []
    paths = list(calendar_files(root))
    base = root / Path(*UNIVERSE_REL.split("/"))
    paths += [base / f"{s}_{c}.parquet" for s in INSTRUMENTS for c in CHARTS]
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        sig.append((p.name, int(st.st_mtime), int(st.st_size)))
    return tuple(sig)


def reading(root: Path) -> dict[str, Any]:
    """The cached measurement for `root`; recomputed only when its inputs change. Never raises."""
    key = str(Path(root).resolve())
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < RECHECK_S:
        return hit[2]
    sig = _signature(Path(root))
    if hit is not None and hit[1] == sig:
        _CACHE[key] = (now, sig, hit[2])
        return hit[2]
    try:
        doc = measure(Path(root)) if sig else {"per_season": {}}
    except Exception as exc:                                            # fail closed: no clock
        doc = {"per_season": {}, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    _CACHE[key] = (now, sig, doc)
    return doc


def offsets(root: Path) -> dict[str, int]:
    """Season -> offset, for seasons the release spikes resolve unanimously. {} otherwise."""
    out: dict[str, int] = {}
    for name, block in (reading(root).get("per_season") or {}).items():
        if isinstance(block, dict) and isinstance(block.get("offset_h"), int) \
                and block.get("agrees_across_pairs"):
            out[str(name)] = int(block["offset_h"])
    return out
