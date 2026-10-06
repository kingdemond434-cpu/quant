"""NEWS HAWKES -- self-exciting intensity of the world's news and macro releases, per event family,
as a point-in-time state, and the post-NFP persistence cell (ROMAN-0826, ROMAN-0830).

WHAT IT MEASURES. For each family (war_escalation, inflation_surprise, labour_surprise,
central_bank) a marked exponential Hawkes process (`libs.quant_models.hawkes`, the desk's one
Hawkes module) is fitted on a rolling window to two event streams:
  mark 0  news events: the sensor ledger's kind=document rows (`news_event_stream` writes them)
          with attributes.event_kind in the family, one event per event_id (syndicated copies
          dropped), stamped at knowable_at (world basis: the instant the world could know it)
  mark 1  scheduled releases: the agency's first-print instants (ALFRED vintages through
          `release_vintages.release_vintage` + `scheduled_utc`) and the calendar's own scheduled
          instants (ff_calendar_vintage) once they have passed; same-instant headlines of one
          release (payrolls, unemployment rate, earnings) are ONE event
The fit uses only events strictly before the refit instant; the intensity at every evaluation
instant uses only events strictly before it (`hawkes.intensity_at`). Published per family:
intensity, excess intensity over the fitted baseline, its scale-free z (log1p(excess / mu)),
branching ratio and excitation half-life (hours).

THE CLOCK. One row per calendar day at 21:00 UTC: never after the open of the next broker day
(the venue's day opens 21:00 UTC in US summer, 22:00 in winter -- `libs.regime.session_clock`),
so the row for day D forecasts broker day D+1 with nothing of D+1 in it.

THE CONTRACTS.
  ROMAN-0826  forecast_gain: does the excess intensity forecast the next broker day's realised
              range (Parkinson variance, QLIKE) and absolute return (MSE) of the family's mapped
              instruments, against an EWMA(10) of the same target? The model is the EWMA scaled
              by 1 + b (z - mean z), b an EXPANDING regression on pairs already knowable (daily
              close of day d knowable d+1 01:00 UTC), so under noise b -> 0 and the model IS the
              baseline: no intercept that could win by fixing the EWMA's own bias.
  ROMAN-0830  monotone_gain: post-NFP persistence (mean excess intensity over the 24h after a
              payrolls release / excess just after it, labour family) against the log ratio of
              realised vol over (tau+24h, tau+96h] to the 20 days before tau, averaged over
              EURUSD, USDJPY, XAUUSD, US500. Persistence is knowable at tau+24h, the vol after.

MAPPING (where to look, never which way): USD releases and central bank -> EURUSD, USDJPY,
XAUUSD, US500; war_escalation -> XAUUSD, USOIL, US500. Cells are emitted with both sides: an
intensity is a volatility state and does not fix a sign.

NO AUTHORITY. State and cells only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.quant_models import hawkes  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "news_hawkes"
SERIES = "ws_news_hawkes"
SERIES_NFP = "ws_news_hawkes_nfp"
REPORT = DESK / "reports" / "NEWS_HAWKES.json"
SENSOR_ROOT = DESK / "data" / "sensors"
UNMEASURED = "UNMEASURED"
CARD_INTENSITY = "ROMAN-0826"
CARD_NFP = "ROMAN-0830"
NFP_TITLE = "USD Non-Farm Employment Change"

#: Family -> the event kinds (news ontology / release spec kinds) it pools.
FAMILIES: dict[str, tuple[str, ...]] = {
    "war_escalation": ("war_escalation",),
    "inflation_surprise": ("inflation_surprise",),
    "labour_surprise": ("labour_surprise",),
    "central_bank": ("central_bank_surprise", "central_bank"),
}
KIND_TO_FAMILY = {k: fam for fam, kinds in FAMILIES.items() for k in kinds}
USD_MAP = ("EURUSD", "USDJPY", "XAUUSD", "US500")
FAMILY_SYMBOLS: dict[str, tuple[str, ...]] = {
    "war_escalation": ("XAUUSD", "USOIL", "US500"),
    "inflation_surprise": USD_MAP, "labour_surprise": USD_MAP, "central_bank": USD_MAP,
}
#: The numbers' origin for the cell door's terms gate: event times from the desk's own sensor
#: ledger (news documents) and release instants (ALFRED vintages / the free calendar).
DATA_SOURCE = "desk:sensor_ledger"
CB_TITLES = ("Federal Funds Rate", "FOMC Statement", "FOMC Press Conference")

WINDOW_D = 365
REFIT_D = 30
HISTORY_D = 6 * 365
MIN_EVENTS = 15
#: Excitation half-life bounds, hours: ten minutes to thirty days.
HALF_LIFE_BOUNDS_H = (1.0 / 6.0, 720.0)
EVAL_HOUR_UTC = 21
EWMA_HALF_LIFE = 10.0
MIN_SLOPE_PAIRS = 60
#: Declared: a daily close is knowable the next day at 01:00 UTC (CONVENTIONS PIT law).
CLOSE_LAG = timedelta(days=1, hours=1)


# ============================================================================== time helpers
def _h(t: datetime) -> float:
    return t.timestamp() / 3600.0


def _dt(hours: float) -> datetime:
    return datetime.fromtimestamp(hours * 3600.0, tz=UTC)


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text or text == UNMEASURED:
        return None
    try:
        got = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (got if got.tzinfo else got.replace(tzinfo=UTC)).astimezone(UTC)


@dataclass(frozen=True)
class Event:
    at: datetime
    family: str
    mark: int          # 0 news, 1 release
    label: str = ""


# ============================================================================== event intake
def ledger_events(root: Path = SENSOR_ROOT, now: datetime | None = None) -> list[Event]:
    """One event per news event_id, at its earliest knowable_at, for the four families."""
    folder = root / "observations"
    first: dict[str, tuple[datetime, str]] = {}
    if not folder.is_dir():
        return []
    for path in sorted(folder.glob("*.jsonl")):
        try:
            fh = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"document"' not in line or "event_kind" not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or row.get("kind") != "document":
                    continue
                attrs = row.get("attributes") or {}
                fam = KIND_TO_FAMILY.get(str(attrs.get("event_kind") or ""))
                if fam is None or attrs.get("copy_of"):
                    continue
                if str(row.get("knowable_basis") or UNMEASURED) == UNMEASURED:
                    continue
                at = _parse(row.get("knowable_at"))
                if at is None or (now is not None and at > now):
                    continue
                key = str(attrs.get("event_id") or row.get("provenance_hash")
                          or row.get("observation_id"))
                cur = first.get(key)
                if cur is None or at < cur[0]:
                    first[key] = (at, fam)
    return [Event(at, fam, 0, key) for key, (at, fam) in first.items()]


def release_events(now: datetime, *, vintages: Path | None = None,
                   alfred: Path | None = None) -> list[Event]:
    """Scheduled release instants that have passed: ALFRED first prints + the calendar."""
    from macro import release_vintages as rv
    out: dict[tuple[str, datetime], Event] = {}
    frames: dict[str, Any] = {}
    for spec in rv.RELEASES:
        fam = KIND_TO_FAMILY.get(spec.kind)
        if fam is None or spec.vintage_rank != 1:
            continue
        if spec.series not in frames:
            frames[spec.series] = rv.load_alfred(spec.series, alfred or rv.ALFRED)
        df = frames[spec.series]
        if df is None:
            continue
        for p in rv.release_vintage(df, spec):
            at = rv.scheduled_utc(spec, date.fromisoformat(p["vintage"]))
            if at <= now:
                out.setdefault((fam, at), Event(at, fam, 1, spec.title))
    for row in rv._vintage_rows(vintages or rv.VINTAGES):
        title = str(row.get("title") or "").strip()
        at = _parse(row.get("event_date"))
        if at is None or at > now or not title.startswith("USD"):
            continue
        spec = rv.BY_TITLE.get(title)
        fam = (KIND_TO_FAMILY.get(spec.kind) if spec is not None else
               ("central_bank" if any(c in title for c in CB_TITLES) else None))
        if fam is None:
            continue
        cur = out.get((fam, at))
        if cur is None or (title == NFP_TITLE and cur.label != NFP_TITLE):
            out[(fam, at)] = Event(at, fam, 1, title)
    return sorted(out.values(), key=lambda e: e.at)


def nfp_instants(releases: Sequence[Event]) -> list[datetime]:
    """Payroll release instants: ALFRED PAYEMS first prints or the calendar's NFP headline."""
    return sorted({e.at for e in releases if e.label == NFP_TITLE})


# ============================================================================== the rolling fit
@dataclass(frozen=True)
class FamilyPath:
    family: str
    grid_h: np.ndarray
    intensity: np.ndarray
    excess: np.ndarray
    mu_total: np.ndarray
    branching: np.ndarray
    half_life_h: np.ndarray
    n_fit: np.ndarray
    fits: list[tuple[float, hawkes.HawkesParams | None, dict[str, Any]]]
    times_h: np.ndarray
    marks: np.ndarray

    @property
    def excess_z(self) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.asarray(np.log1p(np.maximum(self.excess, 0.0) / self.mu_total),
                              dtype=float)

    def _fit_index(self, t_h: float) -> int:
        idx = -1
        for i, (r, _p, _m) in enumerate(self.fits):
            if r <= t_h:
                idx = i
            else:
                break
        return idx

    def excess_at(self, eval_h: Sequence[float]) -> np.ndarray:
        """Total excess intensity at arbitrary instants, each with the fit in force then (the
        latest refit at or before it); events strictly before each instant."""
        ev = np.asarray(eval_h, dtype=float)
        out = np.full(ev.size, np.nan)
        which = np.asarray([self._fit_index(float(t)) for t in ev], dtype=np.int64)
        for i in sorted(set(which.tolist())):
            p = self.fits[i][1] if i >= 0 else None
            if p is None:
                continue
            sel = which == i
            lam = hawkes.intensity_at(p, self.times_h, ev[sel], self.marks)
            out[sel] = lam.sum(axis=1) - float(p.mu.sum())
        return out


def fit_family(family: str, events: Sequence[Event], grid: Sequence[datetime], *,
               window_d: int = WINDOW_D, refit_d: int = REFIT_D,
               min_events: int = MIN_EVENTS) -> FamilyPath:
    evs = sorted((e for e in events if e.family == family), key=lambda e: e.at)
    present = sorted({e.mark for e in evs})
    remap = {m: i for i, m in enumerate(present)}
    times = np.asarray([_h(e.at) for e in evs], dtype=float)
    marks = np.asarray([remap[e.mark] for e in evs], dtype=np.int64)
    d = max(1, len(present))
    g = np.asarray([_h(t) for t in grid], dtype=float)
    n = g.size
    cols = {k: np.full(n, np.nan) for k in ("intensity", "excess", "mu", "br", "hl", "nfit")}
    fits: list[tuple[float, hawkes.HawkesParams | None, dict[str, Any]]] = []
    lo_b = math.log(2.0) / HALF_LIFE_BOUNDS_H[1]
    hi_b = math.log(2.0) / HALF_LIFE_BOUNDS_H[0]
    if n == 0:
        return FamilyPath(family, g, cols["intensity"], cols["excess"], cols["mu"], cols["br"],
                          cols["hl"], cols["nfit"], fits, times, marks)
    r = float(g[0])
    step = refit_d * 24.0
    while r <= g[-1]:
        start = r - window_d * 24.0
        sel = (times >= start) & (times < r)
        params: hawkes.HawkesParams | None = None
        meta: dict[str, Any]
        if int(sel.sum()) >= min_events:
            got = hawkes.fit(times[sel], marks=marks[sel], n_dims=d, t0=start, t_end=r,
                             beta_bounds=(lo_b, hi_b), min_events=min_events)
            if isinstance(got, hawkes.HawkesFit):
                params = got.params
                meta = got.to_dict()
            else:
                meta = dict(got)
        else:
            meta = {"status": UNMEASURED, "why": f"{int(sel.sum())} events < {min_events}"}
        fits.append((r, params, meta))
        blk = (g >= r) & (g < r + step)
        if params is not None and blk.any():
            keep = times >= start
            lam = hawkes.intensity_at(params, times[keep], g[blk], marks[keep])
            tot = lam.sum(axis=1)
            mu = float(params.mu.sum())
            cols["intensity"][blk] = tot
            cols["excess"][blk] = tot - mu
            cols["mu"][blk] = mu
            cols["br"][blk] = params.branching_ratio
            cols["hl"][blk] = params.half_life
            cols["nfit"][blk] = int(sel.sum())
        r += step
    return FamilyPath(family, g, cols["intensity"], cols["excess"], cols["mu"], cols["br"],
                      cols["hl"], cols["nfit"], fits, times, marks)


def eval_grid(now: datetime, history_d: int = HISTORY_D) -> list[datetime]:
    last = now.replace(hour=EVAL_HOUR_UTC, minute=0, second=0, microsecond=0)
    if last > now:
        last -= timedelta(days=1)
    return [last - timedelta(days=i) for i in range(history_d, -1, -1)]


# ============================================================================== the bars
def daily_ohlc(frame: Any, now: datetime) -> Any:
    """Broker-day OHLC from intraday bars that closed by `now` (index: broker date)."""
    import pandas as pd
    if frame is None or len(frame) == 0:
        return None
    f = frame[frame.index <= pd.Timestamp(now)]
    if len(f) == 0:
        return None
    g = f.groupby(f.index.date)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last()})
    out.index = pd.to_datetime(out.index)
    return out[(out["low"] > 0) & (out["high"] >= out["low"])]


def bar_frame(symbol: str, universe: Path | None = None) -> Any:
    """The LONGEST-history intraday chart the desk holds (H1 first, then M15), broker stamps
    under a UTC label as stored. `event_response_atlas.chart` prefers the FINEST chart, whose
    history is months where H1's is years -- the wrong trade for daily states."""
    import pandas as pd
    base = universe or DESK / "data" / "universe"
    for tf in ("H1", "M15"):
        path = base / f"{symbol}_{tf}.parquet"
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path)
        except (OSError, ValueError, ImportError):
            continue
        if frame.empty or not {"open", "high", "low", "close"} <= set(frame.columns):
            continue
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~frame.index.isna()].sort_index()
        if len(frame) > 10:
            return frame
    return None


def load_bars(symbols: Sequence[str], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """(daily OHLC by broker date, hourly frame with a true-UTC index) per symbol held."""
    from libs.regime.session_clock import server_to_utc
    daily: dict[str, Any] = {}
    hourly: dict[str, Any] = {}
    for s in symbols:
        frame = bar_frame(s)
        d = daily_ohlc(frame, now)
        if d is None or len(d) < 30:
            continue
        daily[s] = d
        h = frame.copy()
        h.index = server_to_utc(h.index)
        hourly[s] = h
    return daily, hourly


# ============================================================================== the contracts
def _ewma_through(y: np.ndarray, half_life: float) -> np.ndarray:
    lam = 0.5 ** (1.0 / half_life)
    out = np.full(y.size, np.nan)
    acc = wsum = 0.0
    for i, v in enumerate(y):
        if math.isfinite(v):
            acc = lam * acc + (1 - lam) * v
            wsum = lam * wsum + (1 - lam)
        out[i] = acc / wsum if wsum > 0 else np.nan
    return out


def forecast_frame(z_by_date: Mapping[date, float], dates: Sequence[date],
                   target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(y, model, base) aligned on broker dates. Base: EWMA of the target over days whose close
    was knowable at the forecast instant (date_j <= b - 2 days, see CLOSE_LAG). Model: base x
    (1 + slope (z - mean z)), slope by expanding regression of y/base on z over the same days."""
    n = len(dates)
    y = np.asarray(target, dtype=float)
    z = np.asarray([z_by_date.get(d, np.nan) for d in dates], dtype=float)
    ew = _ewma_through(y, EWMA_HALF_LIFE)
    dnum = np.asarray([d.toordinal() for d in dates], dtype=np.int64)
    base = np.full(n, np.nan)
    model = np.full(n, np.nan)
    sx = sy = sxx = sxy = 0.0
    cnt = 0
    added = 0
    for i in range(n):
        last = int(np.searchsorted(dnum, dnum[i] - 2, side="right")) - 1
        while added <= last:
            j = added
            prev_last = int(np.searchsorted(dnum, dnum[j] - 2, side="right")) - 1
            bj = ew[prev_last] if prev_last >= 0 else np.nan
            if math.isfinite(z[j]) and math.isfinite(y[j]) and math.isfinite(bj) and bj > 0:
                ratio = y[j] / bj
                sx += z[j]
                sy += ratio
                sxx += z[j] * z[j]
                sxy += z[j] * ratio
                cnt += 1
            added += 1
        if last < 0 or not math.isfinite(ew[last]):
            continue
        base[i] = ew[last]
        if cnt >= MIN_SLOPE_PAIRS and math.isfinite(z[i]):
            mx = sx / cnt
            var = sxx / cnt - mx * mx
            slope = ((sxy / cnt - mx * sy / cnt) / var) if var > 1e-12 else 0.0
            model[i] = base[i] * max(0.2, 1.0 + slope * (z[i] - mx))
    return y, model, base


def intensity_contracts(paths: Mapping[str, FamilyPath], daily: Mapping[str, Any]
                        ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fam, path in paths.items():
        # row at day D 21:00 UTC forecasts broker date D+1
        zz = path.excess_z
        z_by_date = {(_dt(float(t)).date() + timedelta(days=1)): float(v)
                     for t, v in zip(path.grid_h, zz, strict=True) if math.isfinite(v)}
        for sym in FAMILY_SYMBOLS[fam]:
            bars = daily.get(sym)
            for tgt, loss in (("range_var", "qlike"), ("abs_return", "mse")):
                common = {"engine": ENGINE, "cards": [CARD_INTENSITY],
                          "falsifier": (f"{fam} excess intensity does not lower the next-day "
                                        f"{tgt} loss of {sym} below its EWMA"),
                          "baseline": f"EWMA(half-life {EWMA_HALF_LIFE:g}d) of {tgt}"}
                if bars is None or not z_by_date:
                    row = se.contract(**common, metric=f"{loss}_reduction", value=None,
                                      baseline_value=None, n=0,
                                      why=("no bars for the symbol" if bars is None else
                                           "no measured intensity for the family"))
                else:
                    dates = [ts.date() for ts in bars.index]
                    hi, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
                    cl = bars["close"].to_numpy(float)
                    if tgt == "range_var":
                        target = np.log(hi / lo) ** 2 / (4 * math.log(2.0))
                    else:
                        # basis points: the spine rounds gains to 6 decimals
                        target = 1e4 * np.abs(np.diff(np.log(cl), prepend=np.nan))
                    y, model, base = forecast_frame(z_by_date, dates, target)
                    row = se.forecast_gain(y, model, base, loss=loss, **common)
                row.update({"family": fam, "symbol": sym, "target": tgt,
                            "label": f"{fam}:{sym}:{tgt}"})
                out.append(row)
    return out


def _rv_per_bar(frame: Any, lo: datetime, hi: datetime) -> float | None:
    import pandas as pd
    f = frame[(frame.index > pd.Timestamp(lo)) & (frame.index <= pd.Timestamp(hi))]
    c = f["close"].to_numpy(float)
    if c.size < 6 or np.any(c <= 0):
        return None
    r = np.diff(np.log(c))
    return float(np.sqrt(np.mean(r * r)))


def post_nfp_rows(path: FamilyPath, nfps: Sequence[datetime], hourly: Mapping[str, Any],
                  symbols: Sequence[str] = USD_MAP) -> list[dict[str, Any]]:
    """Per payrolls release: persistence (knowable tau+24h) and the later vol ratio."""
    rows: list[dict[str, Any]] = []
    if not nfps:
        return rows
    taus = np.asarray([_h(t) for t in nfps], dtype=float)
    offsets = np.concatenate([[1.0 / 60.0], np.arange(1, 25, dtype=float)])
    ex = path.excess_at((taus[:, None] + offsets[None, :]).ravel()).reshape(taus.size, -1)
    for tau, row_ex in zip(nfps, ex, strict=True):
        e0, e24 = float(row_ex[0]), row_ex[1:]
        if not (math.isfinite(e0) and e0 > 0 and np.all(np.isfinite(e24))):
            continue
        pers = float(np.mean(e24) / e0)
        ratios = []
        for s in symbols:
            fr = hourly.get(s)
            if fr is None:
                continue
            post = _rv_per_bar(fr, tau + timedelta(hours=24), tau + timedelta(hours=96))
            pre = _rv_per_bar(fr, tau - timedelta(days=20), tau - timedelta(hours=1))
            if post and pre:
                ratios.append(math.log(post / pre))
        rows.append({"nfp_at": tau.isoformat(timespec="seconds"),
                     "available_time": (tau + timedelta(hours=24)).isoformat(timespec="seconds"),
                     "post_nfp_persistence": round(pers, 6),
                     "post_nfp_excess_24h": round(float(np.mean(e24)), 8),
                     "post_vol_log_ratio": (round(float(np.mean(ratios)), 6) if ratios
                                            else None), "symbols": len(ratios)})
    return rows


def nfp_contract(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    x = [r["post_nfp_persistence"] for r in rows if r.get("post_vol_log_ratio") is not None]
    y = [r["post_vol_log_ratio"] for r in rows if r.get("post_vol_log_ratio") is not None]
    row = se.monotone_gain(x, y, engine=ENGINE, cards=[CARD_NFP],
                           falsifier=("post-NFP intensity persistence does not rank the "
                                      "realised vol of the following three days"),
                           baseline="no order (rho = 0)")
    row["label"] = "post_nfp_persistence:usd_basket:post_vol_log_ratio"
    return row


# ============================================================================== build
def build(now: datetime, *, news: Sequence[Event] | None = None,
          releases: Sequence[Event] | None = None,
          daily: Mapping[str, Any] | None = None, hourly: Mapping[str, Any] | None = None,
          history_d: int = HISTORY_D, window_d: int = WINDOW_D, refit_d: int = REFIT_D
          ) -> dict[str, Any]:
    news_ev = list(ledger_events(now=now) if news is None else news)
    rel_ev = list(release_events(now) if releases is None else releases)
    if daily is None or hourly is None:
        syms = sorted({s for v in FAMILY_SYMBOLS.values() for s in v})
        daily, hourly = load_bars(syms, now)
    events = [e for e in news_ev + rel_ev if e.at < now]
    grid = eval_grid(now, history_d)
    paths = {fam: fit_family(fam, events, grid, window_d=window_d, refit_d=refit_d)
             for fam in FAMILIES}
    series_rows: list[dict[str, Any]] = []
    for i, g in enumerate(grid):
        row: dict[str, Any] = {"available_time": g.isoformat(timespec="seconds"),
                               "event_time": g.isoformat(timespec="seconds"),
                               "source_id": SERIES}
        any_val = False
        for fam, p in paths.items():
            if math.isfinite(p.intensity[i]):
                any_val = True
                row[f"{fam}_intensity"] = round(float(p.intensity[i]), 8)
                row[f"{fam}_excess"] = round(float(p.excess[i]), 8)
                row[f"{fam}_excess_z"] = round(float(p.excess_z[i]), 6)
                row[f"{fam}_branching"] = round(float(p.branching[i]), 6)
                row[f"{fam}_halflife_h"] = round(float(p.half_life_h[i]), 4)
        if any_val:
            series_rows.append(row)
    nfps = [t for t in nfp_instants(rel_ev) if t + timedelta(hours=24) <= now]
    nfp_rows = post_nfp_rows(paths["labour_surprise"], nfps, hourly)
    contracts = intensity_contracts(paths, daily) + [nfp_contract(nfp_rows)]
    latest = {}
    for fam, p in paths.items():
        fin = np.isfinite(p.intensity)
        if fin.any():
            j = int(np.flatnonzero(fin)[-1])
            hist = p.excess_z[fin]
            latest[fam] = {"at": _dt(float(p.grid_h[j])).isoformat(timespec="seconds"),
                           "intensity": float(p.intensity[j]), "excess": float(p.excess[j]),
                           "excess_z": float(p.excess_z[j]),
                           "percentile": round(float(np.mean(hist <= p.excess_z[j])), 4),
                           "branching_ratio": float(p.branching[j]),
                           "half_life_h": float(p.half_life_h[j]), "n_fit": int(p.n_fit[j]),
                           "last_fit": p.fits[-1][2] if p.fits else None}
        else:
            last_meta = p.fits[-1][2] if p.fits else {}
            latest[fam] = {"status": UNMEASURED,
                           "why": str(last_meta.get("why") or "no events for the family")}
    counts = {fam: {"news": sum(1 for e in news_ev if e.family == fam),
                    "releases": sum(1 for e in rel_ev if e.family == fam)} for fam in FAMILIES}
    return {"engine": ENGINE, "at": now.isoformat(timespec="seconds"), "series": series_rows,
            "nfp_rows": nfp_rows, "contracts": contracts, "latest": latest,
            "event_counts": counts, "symbols_with_bars": sorted(daily),
            "nfp_releases": len(nfp_instants(rel_ev)),
            "pit": {"clock": f"daily {EVAL_HOUR_UTC}:00 UTC; events strictly before",
                    "event_basis": "world (knowable_at) for news; scheduled instant for releases",
                    "fit_window_d": window_d, "refit_d": refit_d},
            "authority": "NONE"}


def ledger_observations(rep: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    for fam, st in (rep.get("latest") or {}).items():
        if "excess" not in st:
            continue
        for sym in FAMILY_SYMBOLS[fam]:
            for metric, val in ((f"{fam}_excess_intensity", st["excess"]),
                                (f"{fam}_branching_ratio", st["branching_ratio"])):
                out.append(sc.make(
                    sensor_id=f"news_hawkes:{fam}", source_id=SERIES, metric=metric,
                    kind="state", sensor_class="news_hawkes", entity=sym, value=val,
                    event_time=st["at"], knowable_at=st["at"], knowable_basis="declared_lag",
                    received_at=received_at, parse_complete_at=received_at,
                    percentile=st["percentile"] if metric.endswith("intensity") else None,
                    unit="events/hour" if metric.endswith("intensity") else "ratio",
                    licence="derived from desk ledger and public release calendars",
                    attributes={"half_life_h": st["half_life_h"], "n_fit": st["n_fit"]}))
    return out


def publish_all(rep: Mapping[str, Any], received_at: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"lake": se.write_lake_series(SERIES, rep["series"])}
    out["lake_nfp"] = se.write_lake_series(
        SERIES_NFP, [{"available_time": r["available_time"], "event_time": r["nfp_at"],
                      "source_id": SERIES_NFP, "post_nfp_persistence": r["post_nfp_persistence"],
                      "post_nfp_excess_24h": r["post_nfp_excess_24h"]} for r in rep["nfp_rows"]])
    cells = []
    for fam, syms in FAMILY_SYMBOLS.items():
        cells.append(se.emit_conditioner_cells(
            SERIES, [f"{fam}_excess_z"], syms, sides=(1, -1), generator=ENGINE,
            data_source=DATA_SOURCE,
            mechanism=(f"{fam} news/releases are self-exciting: excess intensity over the fitted "
                       "baseline marks a live cluster, a volatility state for the mapped CFDs"),
            falsifier=f"{fam} excess intensity does not forecast next-day range (ROMAN-0826)"))
    cells.append(se.emit_conditioner_cells(
        SERIES_NFP, ["post_nfp_persistence"], USD_MAP, sides=(1, -1), generator=ENGINE,
        data_source=DATA_SOURCE,
        mechanism=("payrolls information that keeps exciting follow-on news for a day is not "
                   "yet absorbed: persistence marks a vol state for USD crosses, gold, US500"),
        falsifier="post-NFP persistence does not rank post-release realised vol (ROMAN-0830)"))
    out["cells"] = cells
    out["contracts_path"] = str(se.publish(ENGINE, rep["contracts"],
                                           extra={"latest": rep["latest"]}))
    try:
        from libs.research import sensor_contract as sc
        out["ledger"] = sc.SensorLedger().append(ledger_observations(rep, received_at))
    except Exception as exc:                             # pragma: no cover - ledger guard
        out["ledger"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--now", default="", help="ISO UTC evaluation instant (default: now)")
    ap.add_argument("--history-days", type=int, default=HISTORY_D)
    args = ap.parse_args(argv)
    now = _parse(args.now) or datetime.now(UTC)
    rep = build(now, history_d=args.history_days)
    verdicts = {v: sum(1 for c in rep["contracts"] if c["verdict"] == v)
                for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)}
    summary = {k: v for k, v in rep.items() if k not in ("series", "nfp_rows")}
    summary.update({"series_rows": len(rep["series"]), "nfp_rows": len(rep["nfp_rows"]),
                    "verdicts": verdicts})
    if not args.dry_run:
        summary["published"] = publish_all(rep, datetime.now(UTC))
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(summary, indent=1, default=str) + "\n", "utf-8")
    print(f"{ENGINE} rows={len(rep['series'])} nfp={len(rep['nfp_rows'])} verdicts={verdicts} "
          f"events={rep['event_counts']} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
