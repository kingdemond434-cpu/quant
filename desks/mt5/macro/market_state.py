"""MARKET STATE ENGINES -- implied vol, its term structure, implied vs realised, the Treasury curve
and cross-asset beta, from free public data and the desk's own MT5 bars.

WHY (principal 2026-10-05, "OPTIONS, VOL AND CURVE ENGINES"): the desk had a VIX close in its macro
archive and nothing else about how the market PRICES uncertainty. The terminal functions it named
map onto free equivalents as follows, and each is measured or carries its reason:

    OVDV / OMON / HVG           READ, NEVER RECOMPUTED, from `recorders/vol_archive.py` (task
                                MT5-VolArchive): its own point-in-time observations of the CBOE
                                indices (GVZ, OVX, VIX with its 9D/3M/6M term, VXN, VXD, EVZ),
                                joined to THIS broker's realised vol. Added here: each index's
                                and each premium's percentile and z against the archive's OWN
                                history, the term shape as a conditioning key, and the rows in
                                the sensor ledger. Until 2026-10-06 nothing read that archive.
    GC (curve)                  3m/2y/5y/10y/30y Treasury: level, 10y-3m and 10y-2y slopes,
                                2x5y-2y-10y curvature, five-print changes
    BETA                        63-day beta and correlation of every charted MT5 instrument's
                                daily return to US500's
    OMST (per-strike chains)    EXTERNALLY BLOCKED: no per-strike chain source is cleared by the
                                terms gate; routed to discovery as an acquisition target, never
                                approximated

PIT. Every number is read AS OF the instant the desk held it: a vol_archive row at its own
`observed_at`, a Treasury constant-maturity yield the next business afternoon (16:30 ET, H.15)
after its date, and bars only up to `now`.

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
BETA_DAYS = 63

CURVE = ("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30")
BETA_SYMBOLS = ("XAUUSD", "XAGUSD", "USOIL", "UKOIL", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
                "USDCAD", "USDCHF", "NAS100", "US30", "GER40", "JP225")
#: Where each state comes from, for the terms gate (audit #211: a terms gate on the J sources).
#: The vol indices are CBOE values read through Yahoo's chart API by `recorders/vol_archive.py`;
#: the curve is the Federal Reserve's H.15 via FRED (public domain); betas are the desk's own bars.
VOL_SOURCE = "yahoo:cboe_indices"
CURVE_SOURCE = "fred:h15"
#: The discovery request for per-strike chains: written into the acquisition organ's candidate
#: folder (`source_evig` prices every row there and proposes the next ground to acquire).
CHAIN_REQUEST = DESK / "data" / "intelligence" / "asia_endpoints" / "endpoints_world_sensor.json"
CHAIN_TARGETS = ("US500", "NAS100", "US30", "XAUUSD", "USOIL", "EURUSD", "USDJPY")
CHAINS_BLOCKED = ("no per-strike option chain source is cleared by the terms gate on this desk "
                  "(free delayed chains exist but their machine-use terms are unconfirmed); "
                  "OMST/OMON per-strike skew and open interest are an acquisition target, never "
                  "approximated from an index")


def terms(source_id: str) -> dict[str, Any]:
    """The terms gate's verdict for one source: admitted to cells/conditioning or HELD."""
    try:
        from macro.release_vintages import gauntlet_terms
    except Exception as exc:                             # pragma: no cover - import-context only
        return {"gauntlet": "HELD", "why": f"terms gate unavailable: {type(exc).__name__}"}
    ok, why = gauntlet_terms(source_id)
    return {"gauntlet": "admitted" if ok else "HELD", "why": why or "no terms hold on this source"}


def route_chains_to_discovery(path: Path | None = None) -> dict[str, Any]:
    """Per-strike option chains are an ACQUISITION TARGET, routed to discovery as a candidate row
    with its terms unconfirmed: `source_evig` prices it among the proposals, the terms review
    decides machine use, and nothing here fetches it or approximates it from an index."""
    target = path or CHAIN_REQUEST
    row = {"id": "option_chains_per_strike", "url": None, "targets": list(CHAIN_TARGETS),
           "cadence": "daily", "plane": "options", "access": "public",
           "observable": "per-strike implied vol, open interest and volume",
           "mechanism": "dealer gamma, skew and positioning states for the underlying CFD",
           "machine_use_allowed": None, "terms": "UNCONFIRMED: needs a terms review",
           "requested_by": "macro/market_state.py (OMST/OMON)"}
    try:
        doc = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    rows = [r for r in (doc.get("endpoints") or []) if isinstance(r, dict)
            and r.get("id") != row["id"]] if isinstance(doc, dict) else []
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"endpoints": [*rows, row]}, indent=1), "utf-8")
        tmp.replace(target)
    except OSError as exc:
        return {"status": "EXTERNALLY_BLOCKED", "why": CHAINS_BLOCKED,
                "routed": UNMEASURED, "route_error": type(exc).__name__}
    return {"status": "EXTERNALLY_BLOCKED", "why": CHAINS_BLOCKED,
            "routed": "discovery", "request": str(target.relative_to(DESK))
            if target.is_relative_to(DESK) else str(target), "candidate_id": row["id"]}


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


def _chart(symbol: str) -> Any:
    try:
        sys.path.insert(0, str(DESK / "research"))
        import event_response_atlas as atlas  # type: ignore[import-not-found]
        got = atlas.chart(symbol)
        return None if got is None else got[0]
    except Exception:
        return None


# ============================================================================== the engines
def read_vol_archive(path: Path | None = None) -> list[dict[str, Any]]:
    try:
        sys.path.insert(0, str(DESK))
        from recorders import vol_archive as va
        return list(va.read_archive(path or va.ARCHIVE))
    except Exception:
        return []


def vol_state(rows: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    """Per CBOE index: the newest observation the desk HELD by `now`, with percentiles of the
    implied level and the premium against that index's own earlier observations."""
    by_ticker: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        at = r.get("observed_at")
        try:
            seen = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=UTC)
        if seen <= now and isinstance(r.get("implied_vol"), int | float):
            by_ticker.setdefault(str(r.get("vol_ticker")), []).append(r)
    out: dict[str, Any] = {}
    for tk, hist in by_ticker.items():
        hist.sort(key=lambda r: (str(r.get("value_date")), str(r.get("observed_at"))))
        last = hist[-1]
        prior = [h for h in hist[:-1] if str(h.get("value_date")) < str(last.get("value_date"))]
        iv = float(last["implied_vol"])
        ivs = [float(h["implied_vol"]) for h in prior][-TRAIL:]
        row: dict[str, Any] = {"status": "MEASURED", "symbol": last.get("mt5_symbol"),
                               "date": last.get("value_date"),
                               "knowable_at": last.get("observed_at"),
                               "value_age_days": last.get("value_age_days"),
                               "implied": iv, "implied_percentile": percentile(ivs, iv),
                               "implied_z": zscore(ivs, iv), "desk_vintages": len(hist),
                               "term_shape": last.get("term_shape") or None,
                               "term_slope_short": last.get("term_slope_short"),
                               "term_slope_long": last.get("term_slope_long")}
        vrp = last.get("variance_risk_premium")
        if isinstance(vrp, int | float):
            vrps = [float(h["variance_risk_premium"]) for h in prior
                    if isinstance(h.get("variance_risk_premium"), int | float)][-TRAIL:]
            row.update({"realised_21d": last.get("realised_vol_cc"), "vrp": float(vrp),
                        "iv_rv_ratio": last.get("iv_over_rv"),
                        "vrp_percentile": percentile(vrps, float(vrp)),
                        "vrp_z": zscore(vrps, float(vrp))})
        else:
            row["realised"] = _un(last.get("reason") or "no realised-vol join on this row")
        term = last.get("term") or {}
        if isinstance(term, dict) and term.get("^VIX") and term.get("^VIX3M"):
            row["vix_vix3m_ratio"] = round(float(term["^VIX"]) / float(term["^VIX3M"]), 4)
        out[tk] = row
    if not out:
        return {"_status": _un("vol_archive holds no observation as of now "
                               "(MT5-VolArchive has not run, or its archive is absent)")}
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


def regime_from(vol: Mapping[str, Any]) -> str:
    """A bucket KEY for conditioning: the VIX term shape x the VIX level tercile."""
    vix = vol.get("^VIX") or {}
    if vix.get("status") != "MEASURED" or not vix.get("term_shape"):
        return UNMEASURED
    pct = vix.get("implied_percentile")
    if not isinstance(pct, float):
        return f"vol_{vix['term_shape']}"
    tier = "low" if pct < 1 / 3 else ("high" if pct > 2 / 3 else "mid")
    return f"vol_{vix['term_shape']}_{tier}"


def build(*, now: datetime | None = None, series: Mapping[str, list[tuple[str, float]]] | None
          = None, charts: Mapping[str, Any] | None = None,
          vol_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    ser = load_series() if series is None else series
    if charts is None:
        charts = {s: _chart(s) for s in sorted(set(BETA_SYMBOLS) | {"US500"})}
    vol = vol_state(read_vol_archive() if vol_rows is None else vol_rows, when)
    gc = curve(ser, when)
    bt = betas(charts, when)
    vol_terms = terms(VOL_SOURCE)
    return {"at": when.isoformat(timespec="seconds"), "source": "market_state",
            "vol": vol, "curve": gc, "beta": bt,
            "option_chains": {"status": "EXTERNALLY_BLOCKED", "why": CHAINS_BLOCKED},
            "terms": {"vol": vol_terms, "curve": terms(CURVE_SOURCE),
                      "beta": {"gauntlet": "admitted", "why": "the desk's own MT5 bars"}},
            # a held source's states stay stored and in the ledger, never a conditioning key
            "regime": (regime_from(vol) if vol_terms["gauntlet"] == "admitted"
                       else f"HELD_TERMS: {vol_terms['why']}"),
            "series_present": sorted(ser),
            "rule": "states, never directions; every number PIT as of its knowable instant"}


def regime_label(now: datetime | None = None) -> str:
    """The conditioning key `event_surprise` buckets on. UNMEASURED when nothing is read."""
    if terms(VOL_SOURCE)["gauntlet"] != "admitted":
        return UNMEASURED                                # held by the terms gate, never a key
    try:
        return regime_from(vol_state(read_vol_archive(), now or datetime.now(UTC)))
    except Exception:
        return UNMEASURED


# ============================================================================== sensor ledger
def observations(report: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    common = {"sensor_class": "market_state", "kind": "state",
              "received_at": received_at, "parse_complete_at": received_at}
    provenance = {
        "vol": {"source_id": VOL_SOURCE, "commercial_rights": UNMEASURED,
                "licence": "CBOE index values via Yahoo's chart API: terms UNCLEARED, held from "
                           "the gauntlet by the terms gate"},
        "rates": {"source_id": CURVE_SOURCE, "commercial_rights": "public domain",
                  "licence": "Federal Reserve H.15 via FRED: public domain"}}

    def add(sensor: str, metric: str, value: Any, row: Mapping[str, Any], entity: str,
            **kw: Any) -> None:
        if not isinstance(value, int | float) or isinstance(value, bool):
            return
        domain = kw.pop("domain", "vol")
        basis = kw.pop("basis", "declared_lag")
        clocks = {**common, **provenance[domain]}
        if basis == "bounded_by_receipt":
            # vol_archive's own observation instant IS the receipt: the desk read the index then.
            clocks.update(received_at=row.get("knowable_at"),
                          parse_complete_at=row.get("knowable_at"))
        out.append(sc.make(**clocks, sensor_id=sensor, metric=metric, value=float(value),
                           entity=entity, asset_domain=domain, event_time=row.get("date"),
                           knowable_at=row.get("knowable_at"), knowable_basis=basis, **kw))

    for tk, row in (report.get("vol") or {}).items():
        if not isinstance(row, dict) or row.get("status") != "MEASURED":
            continue
        ent = row.get("symbol") or tk
        add("market:implied_vol", tk, row["implied"], row, ent, basis="bounded_by_receipt",
            percentile=row.get("implied_percentile"), surprise_z=row.get("implied_z"))
        if isinstance(row.get("vrp"), float):
            add("market:vrp", f"{tk}_vrp", row["vrp"], row, ent, basis="bounded_by_receipt",
                percentile=row.get("vrp_percentile"), surprise_z=row.get("vrp_z"))
        if isinstance(row.get("vix_vix3m_ratio"), float):
            add("market:vol_term", "vix_vix3m_ratio", row["vix_vix3m_ratio"], row, ent,
                basis="bounded_by_receipt")
    gc = report.get("curve") or {}
    if gc.get("status") == "MEASURED":
        for k in ("level", "slope_10y3m", "slope_10y2y", "curvature"):
            add("market:ust_curve", k, gc[k], gc, "US", domain="rates",
                percentile=gc.get(f"{k}_percentile"), delta=gc.get(f"{k}_chg_5"))
    return out


def main(argv: list[str] | None = None) -> int:
    rep = build()
    rep["option_chains"] = route_chains_to_discovery()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    try:
        from libs.research import sensor_contract as sc
        led = sc.SensorLedger().append(observations(rep, datetime.now(UTC)))
    except Exception as exc:                             # pragma: no cover - ledger guard
        led = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    print(f"market_state regime={rep['regime']} vol={len(rep['vol'])} "
          f"curve={rep['curve'].get('status')} beta={rep['beta'].get('status')} ledger={led}")
    return 0


if __name__ == "__main__":
    for _p in (str(ROOT), str(DESK)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    raise SystemExit(main())
