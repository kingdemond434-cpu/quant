"""MARKET STATE ENGINES -- implied vol, its term structure, implied vs realised, the Treasury curve
and cross-asset beta, from free public data and the desk's own MT5 bars.

WHY (principal 2026-10-05, "OPTIONS, VOL AND CURVE ENGINES"): the desk had a VIX close in its macro
archive and nothing else about how the market PRICES uncertainty. The terminal functions it named
map onto free equivalents as follows, and each is measured or carries its reason:

    OVDV (vol term structure)   VIX against VIX3M (CBOE, via FRED): ratio, slope, backwardation,
                                percentile against its own trailing year
    OMON (implied by underlying) CBOE's implied-vol indices for the instruments the desk trades:
                                GVZ -> XAUUSD, OVX -> USOIL, EVZ -> EURUSD, VIX -> US500,
                                VXN -> NAS100, VXD -> US30, RVX -> US2000, VXEEM (no MT5 pair)
    HVG (implied vs realised)   the index against 21-day realised vol from the desk's own bars:
                                the variance risk premium, and its percentile
    GC (curve)                  3m/2y/5y/10y/30y Treasury: level, 10y-3m and 10y-2y slopes,
                                2x5y-2y-10y curvature, five-print changes
    BETA                        63-day beta and correlation of every charted MT5 instrument's
                                daily return to US500's
    OMST (per-strike chains)    EXTERNALLY BLOCKED: no per-strike chain source is cleared by the
                                terms gate; routed to discovery as an acquisition target, never
                                approximated

PIT. Every series is read AS OF a knowable instant, never its observation date: a CBOE close is
knowable the next morning (09:00 ET, when FRED carries it), a Treasury constant-maturity yield the
next business afternoon (16:30 ET, H.15). Bars are read only up to `now`.

NOTHING HERE HAS A DIRECTION. These are states. `regime_label` hands a bucket key to
`event_surprise` (conditioning, never a sign) and every number goes to the sensor ledger.
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
ARCHIVES = (ROOT / "data" / "fred_market_state.json", ROOT / "data" / "fred_macro_long.json")
REPORT = DESK / "reports" / "MARKET_STATE.json"
UNMEASURED = "UNMEASURED"
ET = ZoneInfo("America/New_York")
TRAIL = 252
RV_DAYS = 21
BETA_DAYS = 63

#: CBOE implied-vol index -> the MT5 instrument it prices (None: no tradable pair here).
VOL_PAIRS: dict[str, str | None] = {
    "VIXCLS": "US500", "VXNCLS": "NAS100", "VXDCLS": "US30", "RVXCLS": "US2000",
    "OVXCLS": "USOIL", "GVZCLS": "XAUUSD", "EVZCLS": "EURUSD", "VXEEMCLS": None,
}
CURVE = ("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30")
BETA_SYMBOLS = ("XAUUSD", "XAGUSD", "USOIL", "UKOIL", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
                "USDCAD", "USDCHF", "NAS100", "US30", "GER40", "JP225")
CHAINS_BLOCKED = ("no per-strike option chain source is cleared by the terms gate on this desk "
                  "(free delayed chains exist but their machine-use terms are unconfirmed); "
                  "OMST/OMON per-strike skew and open interest are an acquisition target, never "
                  "approximated from an index")


# ============================================================================== series and PIT
def knowable(day: str, sid: str) -> datetime:
    """When the desk could first hold the observation dated `day`."""
    d = date.fromisoformat(day[:10])
    if sid.startswith("DGS"):
        return datetime(d.year, d.month, d.day, 16, 30, tzinfo=ET).astimezone(UTC) + timedelta(
            days=1)
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=ET).astimezone(UTC) + timedelta(days=1)


def load_series(paths: Sequence[Path] = ARCHIVES) -> dict[str, list[tuple[str, float]]]:
    """Every series in the archives; the first archive that holds a series wins."""
    out: dict[str, list[tuple[str, float]]] = {}
    for p in paths:
        try:
            doc = json.loads(Path(p).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for sid, rows in ((doc or {}).get("series") or {}).items():
            if sid in out or not isinstance(rows, list):
                continue
            clean = []
            for r in rows:
                try:
                    v = float(r[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if math.isfinite(v):
                    clean.append((str(r[0])[:10], v))
            if clean:
                out[sid] = sorted(clean)
    return out


def as_of(rows: Sequence[tuple[str, float]], sid: str, now: datetime) -> list[tuple[str, float]]:
    return [r for r in rows if knowable(r[0], sid) <= now]


def percentile(history: Sequence[float], x: float) -> float | None:
    h = [v for v in history if math.isfinite(v)]
    if len(h) < 20:
        return None
    below = sum(1 for v in h if v < x) + 0.5 * sum(1 for v in h if v == x)
    return round(below / len(h), 4)


def zscore(history: Sequence[float], x: float) -> float | None:
    h = [v for v in history if math.isfinite(v)]
    if len(h) < 20:
        return None
    m = sum(h) / len(h)
    sd = math.sqrt(sum((v - m) ** 2 for v in h) / (len(h) - 1))
    return round((x - m) / sd, 4) if sd > 0 else None


def _un(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why}


# ============================================================================== the bars
def daily_closes(frame: Any, now: datetime) -> list[tuple[str, float]]:
    """Last close per UTC day, from bars that CLOSED by `now`."""
    if frame is None or len(frame) == 0:
        return []
    f = frame[frame.index <= now]
    if len(f) == 0:
        return []
    closes = f["close"].groupby(f.index.date).last()
    return [(str(d), float(v)) for d, v in closes.items() if math.isfinite(float(v)) and v > 0]


def _returns(closes: Sequence[tuple[str, float]]) -> dict[str, float]:
    return {closes[i][0]: math.log(closes[i][1] / closes[i - 1][1])
            for i in range(1, len(closes))}


def realised_vol(closes: Sequence[tuple[str, float]], days: int = RV_DAYS) -> float | None:
    rets = list(_returns(closes).values())[-days:]
    if len(rets) < days:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * 252.0) * 100.0


def _chart(symbol: str) -> Any:
    try:
        sys.path.insert(0, str(DESK / "research"))
        import event_response_atlas as atlas  # type: ignore[import-not-found]
        got = atlas.chart(symbol)
        return None if got is None else got[0]
    except Exception:
        return None


# ============================================================================== the engines
def term_structure(series: Mapping[str, list[tuple[str, float]]], now: datetime) -> dict[str, Any]:
    vix = dict(as_of(series.get("VIXCLS", []), "VIXCLS", now))
    v3m = dict(as_of(series.get("VXVCLS", []), "VXVCLS", now))
    common = sorted(set(vix) & set(v3m))
    if not common:
        return _un("VIX and VIX3M are not both in the archive as of now (fred_market_state.json "
                   "is written by collect_fred_macro once the FRED key is found)")
    ratios = [vix[d] / v3m[d] for d in common if v3m[d] > 0]
    d = common[-1]
    ratio = vix[d] / v3m[d]
    return {"status": "MEASURED", "date": d, "vix": vix[d], "vix3m": v3m[d],
            "ratio": round(ratio, 4), "slope": round(v3m[d] - vix[d], 4),
            "state": "backwardation" if ratio > 1.0 else "contango",
            "ratio_percentile": percentile(ratios[-TRAIL - 1:-1], ratio),
            "ratio_z": zscore(ratios[-TRAIL - 1:-1], ratio),
            "knowable_at": knowable(d, "VIXCLS").isoformat()}


def implied_vs_realised(series: Mapping[str, list[tuple[str, float]]], now: datetime,
                        charts: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, symbol in VOL_PAIRS.items():
        rows = as_of(series.get(sid, []), sid, now)
        if not rows:
            out[sid] = {"symbol": symbol, **_un(f"{sid} absent from the archive as of now")}
            continue
        d, iv = rows[-1]
        hist = [v for _d, v in rows[-TRAIL - 1:-1]]
        row: dict[str, Any] = {"symbol": symbol, "status": "MEASURED", "date": d,
                               "implied": iv, "implied_percentile": percentile(hist, iv),
                               "implied_z": zscore(hist, iv),
                               "implied_chg_5": (round(iv - rows[-6][1], 4)
                                                 if len(rows) > 5 else None),
                               "knowable_at": knowable(d, sid).isoformat()}
        if symbol is None:
            row["realised"] = _un("no MT5 instrument is priced by this index")
            out[sid] = row
            continue
        closes = daily_closes(charts.get(symbol), now)
        rv = realised_vol(closes)
        if rv is None:
            row["realised"] = _un(f"fewer than {RV_DAYS + 1} daily closes for {symbol}")
            out[sid] = row
            continue
        implied_by_day = dict(rows)
        vrp_hist = []
        for i in range(RV_DAYS + 1, len(closes)):
            day = closes[i - 1][0]
            if day in implied_by_day:
                r = realised_vol(closes[:i])
                if r is not None:
                    vrp_hist.append(implied_by_day[day] - r)
        vrp = iv - rv
        row.update({"realised_21d": round(rv, 4), "vrp": round(vrp, 4),
                    "iv_rv_ratio": round(iv / rv, 4) if rv > 0 else None,
                    "vrp_percentile": percentile(vrp_hist[-TRAIL:], vrp),
                    "vrp_z": zscore(vrp_hist[-TRAIL:], vrp)})
        out[sid] = row
    return out


def curve(series: Mapping[str, list[tuple[str, float]]], now: datetime) -> dict[str, Any]:
    tenors = {sid: dict(as_of(series.get(sid, []), sid, now)) for sid in CURVE}
    common = sorted(set.intersection(*(set(v) for v in tenors.values()))) if all(
        tenors.values()) else []
    if not common:
        missing = [s for s, v in tenors.items() if not v]
        return _un(f"tenor(s) {missing or 'without a common date'} absent as of now")

    def at(d: str) -> dict[str, float]:
        y = {s: tenors[s][d] for s in CURVE}
        return {"level": y["DGS10"], "slope_10y3m": y["DGS10"] - y["DGS3MO"],
                "slope_10y2y": y["DGS10"] - y["DGS2"],
                "curvature": 2 * y["DGS5"] - y["DGS2"] - y["DGS10"]}

    d = common[-1]
    now_s = at(d)
    hist = [at(x) for x in common[-TRAIL - 1:-1]]
    prev = at(common[-6]) if len(common) > 5 else None
    out: dict[str, Any] = {"status": "MEASURED", "date": d,
                           "knowable_at": knowable(d, "DGS10").isoformat()}
    for k, v in now_s.items():
        out[k] = round(v, 4)
        out[f"{k}_chg_5"] = round(v - prev[k], 4) if prev else None
        out[f"{k}_percentile"] = percentile([h[k] for h in hist], v)
    out["inverted_10y3m"] = now_s["slope_10y3m"] < 0
    return out


def betas(charts: Mapping[str, Any], now: datetime, bench: str = "US500") -> dict[str, Any]:
    b = _returns(daily_closes(charts.get(bench), now))
    if len(b) < BETA_DAYS:
        return {"benchmark": bench, **_un(f"fewer than {BETA_DAYS} daily returns for {bench}")}
    out: dict[str, Any] = {"benchmark": bench, "status": "MEASURED", "window_days": BETA_DAYS,
                           "symbols": {}}
    for sym in BETA_SYMBOLS:
        r = _returns(daily_closes(charts.get(sym), now))
        days = sorted(set(r) & set(b))[-BETA_DAYS:]
        if len(days) < BETA_DAYS:
            out["symbols"][sym] = _un(f"fewer than {BETA_DAYS} common days with {bench}")
            continue
        x = [b[d] for d in days]
        y = [r[d] for d in days]
        mx, my = sum(x) / len(x), sum(y) / len(y)
        cov = sum((a - mx) * (c - my) for a, c in zip(x, y, strict=True)) / (len(x) - 1)
        vx = sum((a - mx) ** 2 for a in x) / (len(x) - 1)
        vy = sum((c - my) ** 2 for c in y) / (len(y) - 1)
        out["symbols"][sym] = {"status": "MEASURED", "beta": round(cov / vx, 4) if vx else None,
                               "corr": (round(cov / math.sqrt(vx * vy), 4)
                                        if vx > 0 and vy > 0 else None),
                               "last_day": days[-1]}
    return out


def regime_from(ts: Mapping[str, Any], ivrv: Mapping[str, Any]) -> str:
    """A bucket KEY for conditioning: term-structure state x VIX level tercile."""
    if ts.get("status") != "MEASURED":
        return UNMEASURED
    pct = (ivrv.get("VIXCLS") or {}).get("implied_percentile")
    if not isinstance(pct, float):
        return f"vol_{ts['state']}"
    tier = "low" if pct < 1 / 3 else ("high" if pct > 2 / 3 else "mid")
    return f"vol_{ts['state']}_{tier}"


def build(*, now: datetime | None = None, series: Mapping[str, list[tuple[str, float]]] | None
          = None, charts: Mapping[str, Any] | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    ser = load_series() if series is None else series
    if charts is None:
        wanted = {s for s in VOL_PAIRS.values() if s} | set(BETA_SYMBOLS) | {"US500"}
        charts = {s: _chart(s) for s in sorted(wanted)}
    ts = term_structure(ser, when)
    ivrv = implied_vs_realised(ser, when, charts)
    gc = curve(ser, when)
    bt = betas(charts, when)
    return {"at": when.isoformat(timespec="seconds"), "source": "market_state",
            "term_structure": ts, "implied_vs_realised": ivrv, "curve": gc, "beta": bt,
            "option_chains": {"status": "EXTERNALLY_BLOCKED", "why": CHAINS_BLOCKED},
            "regime": regime_from(ts, ivrv),
            "series_present": sorted(ser),
            "rule": "states, never directions; every number PIT as of its knowable instant"}


def regime_label(now: datetime | None = None) -> str:
    """The conditioning key `event_surprise` buckets on. UNMEASURED when nothing is read."""
    try:
        when = now or datetime.now(UTC)
        ser = load_series()
        return regime_from(term_structure(ser, when), implied_vs_realised(ser, when, {}))
    except Exception:
        return UNMEASURED


# ============================================================================== sensor ledger
def observations(report: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    common = {"source_id": "fred:cboe+h15", "sensor_class": "market_state", "kind": "state",
              "received_at": received_at, "parse_complete_at": received_at,
              "licence": "FRED: public data; CBOE index values redistributed by FRED",
              "commercial_rights": UNMEASURED}

    def add(sensor: str, metric: str, value: Any, row: Mapping[str, Any], entity: str,
            **kw: Any) -> None:
        if not isinstance(value, int | float) or isinstance(value, bool):
            return
        domain = kw.pop("domain", "vol")
        out.append(sc.make(**common, sensor_id=sensor, metric=metric, value=float(value),
                           entity=entity, asset_domain=domain, event_time=row.get("date"),
                           knowable_at=row.get("knowable_at"), **kw))

    ts = report.get("term_structure") or {}
    if ts.get("status") == "MEASURED":
        add("market:vol_term", "vix_vix3m_ratio", ts["ratio"], ts, "US500",
            percentile=ts.get("ratio_percentile"), surprise_z=ts.get("ratio_z"))
    for sid, row in (report.get("implied_vs_realised") or {}).items():
        if row.get("status") != "MEASURED":
            continue
        ent = row.get("symbol") or sid
        add("market:implied_vol", sid, row["implied"], row, ent,
            percentile=row.get("implied_percentile"), surprise_z=row.get("implied_z"))
        if isinstance(row.get("vrp"), float):
            add("market:vrp", f"{sid}_vrp", row["vrp"], row, ent,
                percentile=row.get("vrp_percentile"), surprise_z=row.get("vrp_z"))
    gc = report.get("curve") or {}
    if gc.get("status") == "MEASURED":
        for k in ("level", "slope_10y3m", "slope_10y2y", "curvature"):
            add("market:ust_curve", k, gc[k], gc, "US", domain="rates",
                percentile=gc.get(f"{k}_percentile"), delta=gc.get(f"{k}_chg_5"))
    return out


def main(argv: list[str] | None = None) -> int:
    rep = build()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    try:
        from libs.research import sensor_contract as sc
        led = sc.SensorLedger().append(observations(rep, datetime.now(UTC)))
    except Exception as exc:                             # pragma: no cover - ledger guard
        led = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    print(f"market_state regime={rep['regime']} term={rep['term_structure'].get('status')} "
          f"curve={rep['curve'].get('status')} beta={rep['beta'].get('status')} ledger={led}")
    return 0


if __name__ == "__main__":
    for _p in (str(ROOT), str(DESK)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    raise SystemExit(main())
