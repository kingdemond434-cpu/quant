"""WHAT CLOCK ARE THE DESK'S BARS ON? Measured against a venue whose clock is known.

THE RESULT, and it is the reason this file is not called what it was going to be called. The
question started as "does COMEX gold price the metal before the CFD does" -- an entry in the
`cross_asset_lead_lag` cluster, which `alpha_breadth` reports EMPTY IN BOTH the traded and the
certified book. The first run answered: contemporaneous correlation 0.10, with a spike at minus
three bars. Two instruments tracking the same metal cannot correlate 0.10 within the hour. That
was not a lead, it was a CLOCK, and chasing it as a lead would have produced a certified sleeve
that traded a timezone.

MEASURED 2026-09-10, by shifting the futures returns in whole hours and taking the best
correlation, split by season:

    2025 May-Sep     +3h   corr 0.9578   n=2087
    2024-12..2025-02 +2h   corr 0.9081   n=1114
    2026 May-Sep     +3h   corr 0.9855   n=1828
    2025-12..2026-02 +2h   corr 0.9956   n=1084

The desk's H1 parquet index is BROKER TIME carrying a UTC tzinfo, and the offset is +2 in winter
and +3 in summer. At the correct offset the correlation is 0.91-0.99, which is what two series on
the same metal should look like; at zero offset it is 0.10.

IT RESOLVES A DISAGREEMENT THE DESK HAD ALREADY RECORDED AND COULD NOT SETTLE.
`data/broker_clock_measured.json` measures the offset from the diurnal shape of tick volume and
reports, for all ten symbols, `offset_by_trough: 2`, `offset_by_peak: 3`, `disagreement_h: 1`. It
stores the trough's answer as a single scalar `utc_offset_hours: 2`. BOTH READINGS WERE RIGHT --
in different seasons -- and a single scalar is therefore wrong for half of every year. This is a
third and independent method, and a far stronger one: it aligns actual RETURNS against a series
whose stamps are epoch seconds and therefore UTC by definition, rather than inferring a clock
from the shape of a volume curve.

WHY A STORED SCALAR IS EXPENSIVE. Anything joining an external, genuinely-UTC source to these bars
inherits the error for six months of the year: the event lane's filing acceptance times, the macro
calendar, and this feed. An hour is not a rounding error at H1 -- it is the whole bar, and a bar
mis-joined by one is an observation attributed to the wrong hour of the session.

ONLY THEN THE LEAD. With the clock removed, the residual correlation at lag 0 is the CFD tracking
its underlying and is not an edge. A lead is lag <= -1 AFTER the offset is applied, and this
refuses to report one until the aligned lag-0 correlation clears `MIN_ALIGNED_CORR` -- because an
unresolved alignment produces exactly the pattern a lead would, and that is the trap this file
walked into on its first run and now exists to prevent.

AND EVEN THEN IT IS AN ECONOMIC LEAD, NEVER A MICROSTRUCTURE ONE. Both sides are hourly. A
microstructure lead is measured in milliseconds and needs a tick tape on both venues; the artifact
carries `resolution: H1` so no reader can quote it as one.

MANDATE: the futures side is REFERENCE DATA informing an MT5 instrument, never a hunted universe
of its own.

    python desks/mt5/research/futures_lead_lag.py
    python desks/mt5/research/futures_lead_lag.py --no-fetch    # cached reference bars only
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The reference contracts, and the MT5 instrument each one prices.
PAIRS: tuple[tuple[str, str, str], ...] = (
    ("GC=F", "XAUUSD", "COMEX gold, the venue where gold's price is made"),
    ("SI=F", "XAGUSD", "COMEX silver"),
    ("CL=F", "USOUSD", "NYMEX WTI crude"),
)

#: Whole-hour offsets to try when locating the clock. Wide enough to find any plausible broker
#: timezone and narrow enough that the winner is unambiguous.
OFFSETS: tuple[int, ...] = tuple(range(-6, 7))

#: Lags in BARS, applied AFTER the clock offset. Negative means the futures moved first.
LAGS: tuple[int, ...] = (-3, -2, -1, 0, 1, 2, 3)

#: Below this the aligned lag-0 correlation is too weak to call the clock resolved, and no lead is
#: reported. Two series on the same metal reach 0.91-0.99 when aligned; anything far below that
#: means the alignment is still wrong and every "lead" is an artifact of it.
MIN_ALIGNED_CORR = 0.80

#: Overlapping hours below which nothing is a number (L1.28a).
MIN_OVERLAP = 200

#: Season windows used to separate the DST regimes. Deliberately EXCLUDES the changeover weeks --
#: a window straddling the switch contains both offsets and resolves to neither.
SEASONS: tuple[tuple[str, str, str], ...] = (
    ("summer", "05-01", "09-15"),
    ("winter", "12-01", "02-15"),
)

CACHE = BASE / "data" / "reference" / "futures"
OUT_REL = "desks/mt5/reports/FUTURES_LEAD_LAG.json"
CLOCK_REL = "desks/mt5/reports/BAR_CLOCK.json"

_CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _clean_returns(close: pd.Series) -> pd.Series:
    """Log returns over CONSECUTIVE hours only.

    A return spanning a weekend or a session break is not an hourly return, and leaving them in
    puts a handful of enormous observations into a correlation that is otherwise made of small
    ones -- which is enough to move the answer on its own.
    """
    r = np.log(close.astype(float)).diff()
    return r[close.index.to_series().diff() == pd.Timedelta("1h")].dropna()


def align(fut_r: pd.Series, cfd_r: pd.Series, *, offsets: tuple[int, ...] = OFFSETS
          ) -> tuple[int | None, float | None, int, dict[int, float]]:
    """Find the whole-hour offset that makes the two series agree, and how well it does.

    THE SHIFT IS IN TIME AND NEVER IN ROWS. `Series.shift(n)` moves n POSITIONS, and on an index
    with weekend and session gaps a position is not an hour -- so a row shift silently compares
    Friday's close with Monday's open at some lags and not others. Shifting the INDEX by a
    Timedelta is the only version that means what it says.
    """
    scores: dict[int, float] = {}
    for h in offsets:
        shifted = fut_r.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=h)
        joined = pd.concat([shifted.rename("f"), cfd_r.rename("c")], axis=1, join="inner").dropna()
        if len(joined) < MIN_OVERLAP or joined["f"].std() == 0 or joined["c"].std() == 0:
            continue
        scores[h] = round(float(joined["f"].corr(joined["c"])), 5)
    if not scores:
        return None, None, 0, scores
    best = max(scores, key=lambda k: scores[k])
    shifted = fut_r.copy()
    shifted.index = shifted.index + pd.Timedelta(hours=best)
    n = len(pd.concat([shifted, cfd_r], axis=1, join="inner").dropna())
    return best, scores[best], n, scores


def seasonal_offsets(fut_r: pd.Series, cfd_r: pd.Series) -> dict[str, Any]:
    """The offset per DST season, over every year the overlap covers.

    PER SEASON AND NOT POOLED, because a pooled measurement over both regimes finds neither: the
    two offsets split the correlation between two adjacent shifts and the winner is whichever
    regime happened to supply more bars.
    """
    years = sorted({int(y) for y in cfd_r.index.year.unique()})
    out: dict[str, list[dict[str, Any]]] = {name: [] for name, _, _ in SEASONS}
    for name, start, end in SEASONS:
        for yr in years:
            # Winter straddles the new year: Dec of yr-1 through Feb of yr.
            lo = f"{yr - 1 if name == 'winter' else yr}-{start}"
            hi = f"{yr}-{end}"
            try:
                f, c = fut_r[lo:hi], cfd_r[lo:hi]
            except (KeyError, TypeError):
                continue
            if len(f) < MIN_OVERLAP or len(c) < MIN_OVERLAP:
                continue
            best, corr, n, _ = align(f, c)
            if best is None or corr is None or corr < MIN_ALIGNED_CORR:
                continue
            out[name].append({"window": f"{lo}..{hi}", "offset_h": best,
                              "corr": corr, "n": n})
    verdict: dict[str, Any] = {}
    for name, rows in out.items():
        offs = {r["offset_h"] for r in rows}
        verdict[name] = {
            "readings": rows,
            "offset_h": (rows[0]["offset_h"] if len(offs) == 1 and rows else None),
            "agrees": len(offs) == 1 and bool(rows),
            "why": ("every window in this season resolved to one offset" if len(offs) == 1 and rows
                    else "no window cleared the alignment floor" if not rows
                    else f"windows disagree: {sorted(offs)} -- not a clock, or not enough bars"),
        }
    return verdict


def apply_clock(fut_r: pd.Series, seasons: dict[str, Any]) -> tuple[pd.Series, dict[str, Any]]:
    """Shift each futures return by the offset measured for ITS OWN season, and drop the rest.

    THE SHOULDER MONTHS ARE DROPPED, NOT GUESSED. March, April, October and November lie between
    the two season windows, so which offset applies depends on the exact changeover date and on
    whether the broker follows EU or US rules -- and this measures neither. Assigning them the
    nearer season's offset would put an hour of error into a fraction of every year while looking
    like full coverage; dropping them and REPORTING the share is the honest version, and the
    share is itself the number that says how much a proper DST rule would buy.
    """
    resolved = {name: v["offset_h"] for name, v in seasons.items()
                if v.get("agrees") and v.get("offset_h") is not None}
    if not resolved:
        return fut_r.iloc[0:0], {"covered": 0.0, "offsets": {}, "why": "no season resolved"}
    parts = []
    for name, start, end in SEASONS:
        if name not in resolved:
            continue
        # THE MASK USES MONTH AND DAY, not month alone. The season windows end mid-month --
        # 09-15 and 02-15 -- precisely to stay clear of the changeover, and a month-only mask
        # would hand the offset to exactly the days the fit refused to use.
        mmdd = (fut_r.index.month * 100 + fut_r.index.day)
        lo, hi = int(start[:2]) * 100 + int(start[3:]), int(end[:2]) * 100 + int(end[3:])
        mask = ((mmdd >= lo) & (mmdd <= hi)) if lo <= hi else ((mmdd >= lo) | (mmdd <= hi))
        chunk = fut_r[mask]
        if chunk.empty:
            continue
        shifted = chunk.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=resolved[name])
        parts.append(shifted)
    out = pd.concat(parts).sort_index() if parts else fut_r.iloc[0:0]
    return out, {
        "covered": round(len(out) / len(fut_r), 4) if len(fut_r) else 0.0,
        "offsets": resolved,
        "why": ("shoulder months are dropped rather than assigned a neighbouring season's "
                "offset, because which one applies depends on a changeover date this does not "
                "measure"),
    }


@dataclass(frozen=True)
class Reading:
    """One (futures, CFD) pair: the clock first, then whatever lead survives it."""

    future: str
    symbol: str
    why: str
    status: str
    offset_h: int | None
    aligned_corr: float | None
    n_overlap: int
    offset_scores: dict[int, float]
    seasons: dict[str, Any]
    applied: dict[str, Any]
    by_lag: dict[int, float | None]
    note: str

    @property
    def best_lead(self) -> tuple[int, float] | None:
        leads = {k: v for k, v in self.by_lag.items() if k < 0 and v is not None}
        if not leads:
            return None
        k = max(leads, key=lambda k: abs(leads[k]))
        return k, leads[k]

    def to_dict(self) -> dict[str, Any]:
        bl = self.best_lead
        return {
            "future": self.future, "symbol": self.symbol, "why": self.why,
            "status": self.status, "resolution": "H1",
            # The POOLED best-fit offset, kept as a diagnostic only: when the clock varies
            # with DST no single shift fits the whole sample, and this one reports whichever
            # season supplied more bars. The per-season offsets in `clock_applied` are the answer.
            "pooled_offset_h_diagnostic": self.offset_h,
            "aligned_corr": self.aligned_corr,
            "min_aligned_corr": MIN_ALIGNED_CORR,
            "n_overlap": self.n_overlap,
            "offset_scores": {str(k): v for k, v in sorted(self.offset_scores.items())},
            "seasons": self.seasons, "clock_applied": self.applied,
            "by_lag_after_alignment": {str(k): v for k, v in sorted(self.by_lag.items())},
            "contemporaneous_after_alignment": self.by_lag.get(0),
            "best_lead_bars": (bl[0] if bl else None),
            "best_lead_corr": (bl[1] if bl else None),
            "note": self.note,
        }


def fetch_bars(symbol: str, *, rng: str = "2y", interval: str = "1h",
               timeout: int = 60) -> pd.DataFrame | None:
    """Hourly bars for one reference contract, or None with nothing written.

    A FAILED FETCH RETURNS None AND NEVER TOUCHES THE CACHE. A partial write would shorten the
    sample on the next run without saying so, and a clock measured on a silently shorter window
    is a different measurement wearing the same name.
    """
    url = _CHART.format(sym=symbol.replace("=", "%3D"), rng=rng, iv=interval)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            doc = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    try:
        res = doc["chart"]["result"][0]
        stamps, close = res["timestamp"], res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return None
    if not stamps or not close:
        return None
    # EPOCH SECONDS ARE UTC BY DEFINITION. That is the entire reason this feed can measure a
    # clock: it carries no timezone convention of its own to be wrong about.
    idx = pd.to_datetime(pd.Series(stamps, dtype="int64"), unit="s", utc=True)
    return pd.DataFrame({"close": close}, index=pd.DatetimeIndex(idx, name="time")).dropna()


def cached(symbol: str) -> pd.DataFrame | None:
    path = CACHE / f"{symbol.replace('=', '_')}_H1.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError):
        return None
    frame.index = pd.DatetimeIndex(frame.index).tz_convert(UTC)
    return frame


def store(symbol: str, frame: pd.DataFrame) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol.replace('=', '_')}_H1.parquet"
    if path.exists():
        with contextlib.suppress(OSError, ValueError):
            frame = pd.concat([pd.read_parquet(path), frame])
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame.to_parquet(path, compression="zstd")
    return path


def desk_bars(symbol: str) -> pd.DataFrame | None:
    path = BASE / "data" / "universe" / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, KeyError):
        return None
    frame.index = pd.DatetimeIndex(frame.index).tz_convert(UTC)
    return frame


def lagged_correlations(fut_r: pd.Series, cfd_r: pd.Series, offset_h: int,
                        lags: tuple[int, ...] = LAGS) -> dict[int, float | None]:
    """Correlate at each lag AFTER the clock offset has been removed. Time shifts throughout."""
    out: dict[int, float | None] = {}
    for lag in lags:
        shifted = fut_r.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=offset_h + lag)
        joined = pd.concat([shifted.rename("f"), cfd_r.rename("c")], axis=1, join="inner").dropna()
        if len(joined) < MIN_OVERLAP or joined["f"].std() == 0 or joined["c"].std() == 0:
            out[lag] = None
            continue
        out[lag] = round(float(joined["f"].corr(joined["c"])), 5)
    return out


def read_pair(future: str, symbol: str, why: str, *, fetch: bool = True) -> Reading:
    fut = fetch_bars(future) if fetch else None
    if fut is not None:
        store(future, fut)
    else:
        fut = cached(future)
    cfd = desk_bars(symbol)

    empty: dict[int, float | None] = dict.fromkeys(LAGS)
    if fut is None:
        return Reading(future, symbol, why, "UNMEASURED", None, None, 0, {}, {}, {}, empty,
                       f"no bars for {future}: the fetch failed and nothing is cached. A feed "
                       "gap, not a finding about the clock or the lead")
    if cfd is None:
        return Reading(future, symbol, why, "UNMEASURED", None, None, 0, {}, {}, {}, empty,
                       f"{symbol} has no H1 parquet in this tree")

    fut_r, cfd_r = _clean_returns(fut["close"]), _clean_returns(cfd["close"])
    offset, corr, n, scores = align(fut_r, cfd_r)
    if offset is None or corr is None:
        return Reading(future, symbol, why, "UNMEASURED", None, None, n, scores, {}, {}, empty,
                       f"no offset reached {MIN_OVERLAP} overlapping hours")

    seasons = seasonal_offsets(fut_r, cfd_r)
    aligned, applied = apply_clock(fut_r, seasons)

    # A LOW POOLED CORRELATION IS EVIDENCE FOR DST, NOT A REASON TO GIVE UP. When the offset
    # differs between seasons no SINGLE whole-hour shift can align the whole sample -- the two
    # regimes split the correlation between two adjacent shifts, which is exactly the 0.615 the
    # pooled fit returns here against 0.91-0.99 within each season. So the pooled fit is reported
    # as a diagnostic and the SEASONAL fits decide the verdict.
    if not applied["offsets"]:
        return Reading(future, symbol, why, "CLOCK_UNRESOLVED", offset, corr, n, scores, seasons,
                       applied, empty,
                       f"no season resolved an offset above the {MIN_ALIGNED_CORR} floor; the "
                       f"best pooled whole-hour alignment reaches only {corr}. Until the "
                       "alignment is resolved every apparent lead is the clock")

    # Lags are taken on the DST-CORRECTED series, so lag 0 is genuinely the same hour.
    by_lag: dict[int, float | None] = {}
    for lag in LAGS:
        shifted = aligned.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=lag)
        joined = pd.concat([shifted.rename("f"), cfd_r.rename("c")], axis=1, join="inner").dropna()
        by_lag[lag] = (round(float(joined["f"].corr(joined["c"])), 5)
                       if len(joined) >= MIN_OVERLAP and joined["f"].std() and joined["c"].std()
                       else None)

    lag0 = by_lag.get(0)
    if lag0 is None or lag0 < MIN_ALIGNED_CORR:
        # THE REFUSAL THAT MATTERS. An unresolved alignment produces exactly the pattern a lead
        # would -- near-zero at lag 0 and a spike a few bars out -- so reporting a lead from here
        # would be reporting the clock. This is what the first version of this file did.
        return Reading(future, symbol, why, "CLOCK_UNRESOLVED", offset, lag0, n, scores, seasons,
                       applied, empty,
                       f"even with the per-season offsets applied, lag 0 reaches only {lag0}, "
                       f"below the {MIN_ALIGNED_CORR} floor. Two series on the same underlying "
                       "should reach 0.9+, so the alignment is still wrong and every apparent "
                       "lead is the clock")

    return Reading(future, symbol, why, "MEASURED", offset, lag0, n, scores, seasons, applied,
                   by_lag,
                   "lag 0 after alignment is the CFD tracking its underlying and is not an edge; "
                   "only lag <= -1 is a lead, and at H1 that is an ECONOMIC lead and never a "
                   "microstructure one")


def clock_verdict(rows: list[Reading]) -> dict[str, Any]:
    """The desk's bar clock, from every pair that resolved one, against what is on file."""
    stored: Any = None
    try:
        doc = json.loads((BASE / "data" / "broker_clock_measured.json").read_text("utf-8"))
        stored = doc.get("utc_offset_hours")
    except (OSError, ValueError):
        pass
    per_season: dict[str, dict[str, Any]] = {}
    for name, _, _ in SEASONS:
        offs = {r.seasons.get(name, {}).get("offset_h") for r in rows
                if r.seasons.get(name, {}).get("agrees")}
        offs.discard(None)
        per_season[name] = {
            "offset_h": (next(iter(offs)) if len(offs) == 1 else None),
            "agrees_across_pairs": len(offs) == 1,
            "readings": {r.symbol: r.seasons.get(name) for r in rows if r.seasons},
        }
    summer, winter = per_season.get("summer", {}), per_season.get("winter", {})
    varies = (summer.get("offset_h") is not None and winter.get("offset_h") is not None
              and summer["offset_h"] != winter["offset_h"])
    return {
        "measured_by": ("cross-venue return alignment against a feed stamped in epoch seconds, "
                        "which is UTC by definition and carries no convention to be wrong about"),
        "per_season": per_season,
        "varies_with_dst": varies,
        "stored_scalar": stored,
        "stored_is_wrong_half_the_year": bool(varies and stored is not None
                                              and stored in (summer.get("offset_h"),
                                                             winter.get("offset_h"))),
        "why": (
            "`broker_clock_measured.json` infers the offset from the diurnal shape of tick volume "
            "and records offset_by_trough 2 against offset_by_peak 3 on all ten symbols, a "
            "disagreement it cannot settle, storing the trough's answer as ONE scalar. Both "
            "readings are right in different seasons, so a scalar is wrong for half of every "
            "year -- and anything joining a genuinely-UTC external source to these bars inherits "
            "that hour: the event lane's filing acceptance times, the macro calendar, this feed"),
    }


def census(*, fetch: bool = True) -> dict[str, Any]:
    rows = [read_pair(f, s, w, fetch=fetch) for f, s, w in PAIRS]
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "resolution": "H1",
        "lags_bars": list(LAGS),
        "min_overlap": MIN_OVERLAP,
        "min_aligned_corr": MIN_ALIGNED_CORR,
        "n_pairs": len(rows),
        "n_measured": sum(1 for r in rows if r.status == "MEASURED"),
        "clock": clock_verdict(rows),
        "pairs": [r.to_dict() for r in rows],
        "cluster": "cross_asset_lead_lag",
        "rule": (
            "the clock is measured BEFORE any lead is reported, and no lead is reported at all "
            "until the aligned lag-0 correlation clears the floor -- an unresolved alignment "
            "produces exactly the pattern a lead would. Every shift is in TIME and never in "
            "rows, because a row is not an hour on an index with weekend and session gaps. An "
            "hourly lead is an ECONOMIC lead and never a microstructure one"),
    }


def render(doc: dict[str, Any]) -> str:
    c = doc["clock"]
    lines = [f"BAR CLOCK  summer {c['per_season']['summer']['offset_h']}h  "
             f"winter {c['per_season']['winter']['offset_h']}h  "
             f"(stored scalar: {c['stored_scalar']})"]
    if c["varies_with_dst"]:
        lines.append("  THE OFFSET VARIES WITH DST and the desk stores one scalar, so every join "
                     "from a true-UTC source is an hour out for half the year")
    lines.append(f"FUTURES LEAD-LAG  {doc['n_measured']} of {doc['n_pairs']} pairs "
                 f"measured at {doc['resolution']}  (cluster: {doc['cluster']})")
    for p in doc["pairs"]:
        if p["status"] != "MEASURED":
            lines.append(f"  {p['future']:6s} -> {p['symbol']:8s} {p['status']}  {p['note']}")
            continue
        lags = "  ".join(f"{k:>3s}:{'    -' if v is None else f'{v:+.4f}'}"
                         for k, v in p["by_lag_after_alignment"].items())
        offs = p["clock_applied"].get("offsets") or {}
        shown = " ".join(f"{k} {v:+d}h" for k, v in sorted(offs.items()))
        lines.append(f"  {p['future']:6s} -> {p['symbol']:8s} [{shown}] "
                     f"lag0 {p['aligned_corr']:+.4f} n={p['n_overlap']} "
                     f"coverage {p['clock_applied'].get('covered')}")
        lines.append(f"      after alignment  {lags}")
        lead = p["best_lead_corr"]
        lines.append(f"      LEAD: best {lead} at {p['best_lead_bars']} bars -- "
                     + ("no measurable lead at H1; the two price the metal in the same hour"
                        if lead is not None and abs(lead) < 0.05
                        else "a lead survives the alignment and is worth a hypothesis"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="what clock the desk's bars are on, then any lead")
    ap.add_argument("--no-fetch", action="store_true", help="use cached reference bars only")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = census(fetch=not args.no_fetch)
    for rel, payload in ((OUT_REL, doc), (CLOCK_REL, {"at": doc["at"], **doc["clock"]})):
        out = ROOT / Path(*rel.split("/"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {OUT_REL} and {CLOCK_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
