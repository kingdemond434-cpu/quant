"""GC, MULTI-COUNTRY -- per-country curve level and slope from the rate archives on this host.

WHY (DATA-22, the GC row). `market_state.curve` measures the US Treasury curve and nothing else,
so an FX pair's two legs had one curve between them. This builds, per country, the long-rate
level, the short rate and the long-minus-short slope with their trailing percentiles, from
every rate archive the desk ALREADY holds -- it fetches nothing.

THE SOURCES, in the order a country's leg is taken (the first present wins, per leg):

    fred:IRLTLT01<CC>M156N  OECD MEI long-term government bond yield (monthly)   long
    fred:IR3TIB01<CC>M156N  OECD MEI 3-month interbank rate (monthly)            short
        both read from data/fred_macro*.json / fred_market_state.json when a collector put them
        there. NOTE (recommendation_ledger, s38): FRED withdrew the IR3TIB01 family; an absent
        series is UNMEASURED for that leg, never a zero
    fred:DGS10 / DGS3MO     US H.15 (daily)                                       US
    ecb:yc                  ECB AAA euro-area spot curve, axes/ecb.json (10y, 1y)  EA
    boe:glc                 BoE nominal 10y, data/boe_glc_curves_10y.jsonl          GB long
    snb:yields              SNB Confederation curve, data/snb_chf_curve_daily.jsonl  CH
    bis:cbpol               BIS central-bank policy rates, axes/bis.json            short, any

TERMS. Every leg names its source id and the terms gate's verdict. A HELD source (ecb, boe, snb,
bis carry no recorded terms basis today) is MEASURED AND KEPT as state; it reaches no cell. Cells
go through `sensor_engines.emit_conditioner_cells`, which re-applies the same gate.

PIT. Each leg's observation is read as of its knowable instant: H.15 the next day 16:30 ET (via
`market_state.knowable`), the OECD monthly series a declared 75 days after their month-start
stamp (libs/tiers/data_os FRED_SERIES_LAGS, IR3TIB01JPM156N), the ECB/BoE/SNB daily curves the
next day 12:00 UTC, BIS policy rates at the row's own `knowable_at`. A country's slope pairs the
newest long and short legs each knowable by `now`; `age_days` says how old the older leg is.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
UNMEASURED = "UNMEASURED"
ENGINE = "global_curves"
ECB = DESK / "data" / "axes" / "ecb.json"
BIS = DESK / "data" / "axes" / "bis.json"
BOE = ROOT / "data" / "boe_glc_curves_10y.jsonl"
SNB = ROOT / "data" / "snb_chf_curve_daily.jsonl"
TRAIL = 252
MONTHLY_LAG = timedelta(days=75)
#: Country -> (OECD MEI two-letter code, BIS currency, MT5 instruments its curve is state for).
COUNTRIES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "US": ("US", "USD", ("US500", "NAS100", "US30")),
    "EA": ("EZ", "EUR", ("EURUSD", "GER40")),
    "DE": ("DE", "EUR", ("EURUSD", "GER40")),
    "GB": ("GB", "GBP", ("GBPUSD", "UK100")),
    "JP": ("JP", "JPY", ("USDJPY", "JP225")),
    "CH": ("CH", "CHF", ("USDCHF",)),
    "CA": ("CA", "CAD", ("USDCAD",)),
    "AU": ("AU", "AUD", ("AUDUSD", "AUS200")),
    "NZ": ("NZ", "NZD", ("NZDUSD",)),
    "SE": ("SE", "SEK", ("USDSEK",)),
    "NO": ("NO", "NOK", ("USDNOK",)),
}
SIGNALS = ("slope",)


Leg = list[tuple[datetime, str, float]]          # (knowable_at, value date, value)


def _un(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why}


def _terms(source_id: str) -> str:
    try:
        from libs.data.terms_hold import gauntlet_terms
        return "admitted" if gauntlet_terms(source_id)[0] else "HELD"
    except Exception:                                    # pragma: no cover - import context
        return "HELD"


def _next_noon(d: str) -> datetime:
    x = date.fromisoformat(d[:10]) + timedelta(days=1)
    return datetime(x.year, x.month, x.day, 12, tzinfo=UTC)


def _fin(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ============================================================================== the readers
def fred_leg(series: Mapping[str, Sequence[tuple[str, float]]], sid: str) -> Leg:
    rows = series.get(sid) or []
    if sid.startswith("DGS"):
        from macro.market_state import knowable
        return [(knowable(d, sid), d, v) for d, v in rows]
    return [(datetime.fromisoformat(d[:10]).replace(tzinfo=UTC) + MONTHLY_LAG, d, v)
            for d, v in rows]


def ecb_legs(path: Path = ECB) -> dict[str, Leg]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, Leg] = {}
    for key, name in (("eur_aaa_10y", "long"), ("eur_aaa_1y", "short")):
        pts = ((doc.get("series") or {}).get(key) or {}).get("points") or []
        leg = [(_next_noon(str(p["d"])), str(p["d"])[:10], v) for p in pts
               if isinstance(p, dict) and p.get("d") and (v := _fin(p.get("v"))) is not None]
        if leg:
            out[name] = sorted(leg)
    return out


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("date"):
            out.append(row)
    return out


def jsonl_leg(path: Path, column: str) -> Leg:
    return sorted((_next_noon(str(r["date"])), str(r["date"])[:10], v) for r in _jsonl(path)
                  if (v := _fin(r.get(column))) is not None)


def bis_legs(path: Path = BIS) -> dict[str, Leg]:
    """Policy rate per currency from the BIS axis rows (base and quote legs both carry one)."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    seen: dict[str, dict[str, float]] = {}
    for r in doc.get("rows") or []:
        if not isinstance(r, dict):
            continue
        day = str(r.get("knowable_at") or "")
        if len(day) == 7:
            day = f"{day}-01"
        if len(day) < 10:
            continue
        for ccy_k, rate_k in (("base", "base_rate"), ("quote", "quote_rate")):
            v = _fin(r.get(rate_k))
            if r.get(ccy_k) and v is not None:
                seen.setdefault(str(r[ccy_k]), {})[day[:10]] = v
    return {ccy: sorted((datetime.fromisoformat(d).replace(tzinfo=UTC), d, v)
                        for d, v in pts.items()) for ccy, pts in seen.items()}


# ============================================================================== the state
def _asof(leg: Leg, now: datetime) -> Leg:
    return [p for p in leg if p[0] <= now]


def _pct(hist: Sequence[float], x: float) -> float | None:
    if len(hist) < 20:
        return None
    return round((sum(1 for v in hist if v < x) + 0.5 * sum(1 for v in hist if v == x))
                 / len(hist), 4)


def country(name: str, long_opts: Sequence[tuple[str, Leg]],
            short_opts: Sequence[tuple[str, Leg]], now: datetime) -> dict[str, Any]:
    """One country's curve state from the first non-empty long and short legs as of `now`."""
    lg = next(((s, _asof(leg, now)) for s, leg in long_opts if _asof(leg, now)), None)
    sh = next(((s, _asof(leg, now)) for s, leg in short_opts if _asof(leg, now)), None)
    out: dict[str, Any] = {"country": name,
                           "long_source": lg[0] if lg else None,
                           "short_source": sh[0] if sh else None}
    if lg is None and sh is None:
        return {**out, **_un("no long or short rate for this country on this host as of now")}
    if lg:
        out.update(long=lg[1][-1][2], long_date=lg[1][-1][1],
                   long_terms=_terms(lg[0]))
    else:
        out["long"] = _un("no long-rate source on this host (OECD MEI IRLTLT01 absent)")
    if sh:
        out.update(short=sh[1][-1][2], short_date=sh[1][-1][1], short_terms=_terms(sh[0]))
    else:
        out["short"] = _un("no short-rate source on this host")
    if not (lg and sh):
        out["status"] = "PARTIAL"
        out["slope"] = _un("needs both a long and a short leg")
        return out
    # the slope history pairs each long observation with the newest short knowable by then
    shorts = sh[1]
    hist: list[tuple[str, datetime, float]] = []
    j = 0
    for t, d, v in lg[1]:
        while j + 1 < len(shorts) and shorts[j + 1][0] <= t:
            j += 1
        if shorts[j][0] <= t:
            hist.append((d, max(t, shorts[j][0]), v - shorts[j][2]))
    if not hist:
        out["status"] = "PARTIAL"
        out["slope"] = _un("no long observation has a short leg knowable by its own instant")
        return out
    d, at, slope = hist[-1]
    trail = [h[2] for h in hist[-TRAIL - 1:-1]]
    prev = hist[-21][2] if len(hist) > 20 else None
    older = min(date.fromisoformat(out["long_date"]), date.fromisoformat(out["short_date"]))
    terms_ok = out["long_terms"] == "admitted" and out["short_terms"] == "admitted"
    out.update(status="MEASURED", slope=round(slope, 4), slope_date=d,
               knowable_at=at.isoformat(), slope_percentile=_pct(trail, slope),
               slope_chg_20obs=round(slope - prev, 4) if prev is not None else None,
               level_percentile=_pct([p[2] for p in lg[1][-TRAIL - 1:-1]], out["long"]),
               age_days=(now.date() - older).days, history_obs=len(hist),
               terms="admitted" if terms_ok else "HELD",
               history=[{"available_time": h[1].isoformat(), "event_time": h[0],
                         "slope": round(h[2], 6)} for h in hist])
    return out


def build(*, now: datetime, series: Mapping[str, Sequence[tuple[str, float]]] | None = None,
          ecb: Path = ECB, bis: Path = BIS, boe: Path = BOE, snb: Path = SNB) -> dict[str, Any]:
    ser = series or {}
    eb, bs = ecb_legs(ecb), bis_legs(bis)
    out: dict[str, Any] = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"),
                           "countries": {}}
    for name, (cc, ccy, _syms) in COUNTRIES.items():
        longs: list[tuple[str, Leg]] = [(f"fred:IRLTLT01{cc}M156N",
                                         fred_leg(ser, f"IRLTLT01{cc}M156N"))]
        shorts: list[tuple[str, Leg]] = [(f"fred:IR3TIB01{cc}M156N",
                                          fred_leg(ser, f"IR3TIB01{cc}M156N"))]
        if name == "US":
            longs.insert(0, ("fred:DGS10", fred_leg(ser, "DGS10")))
            shorts.insert(0, ("fred:DGS3MO", fred_leg(ser, "DGS3MO")))
        if name == "EA":
            longs.append(("ecb:yc:aaa_10y", eb.get("long", [])))
            shorts.append(("ecb:yc:aaa_1y", eb.get("short", [])))
        if name == "GB":
            longs.append(("boe:glc:nominal_10y", jsonl_leg(boe, "nominal_10y")))
        if name == "CH":
            longs.append(("snb:yields:10y", jsonl_leg(snb, "10J0")))
            shorts.append(("snb:yields:1y", jsonl_leg(snb, "1J")))
        shorts.append((f"bis:cbpol:{ccy}", bs.get(ccy, [])))
        row = country(name, longs, shorts, now)
        out["countries"][name] = row
    states = [r.get("status") for r in out["countries"].values()]
    out["measured"] = sum(1 for s in states if s == "MEASURED")
    out["partial"] = sum(1 for s in states if s == "PARTIAL")
    out["unmeasured"] = sum(1 for s in states if s == UNMEASURED)
    out["status"] = "MEASURED" if out["measured"] else UNMEASURED
    if not out["measured"]:
        out["why"] = "no country has both a long and a short leg knowable as of now"
    return out


def public(block: Mapping[str, Any]) -> dict[str, Any]:
    """The block without the per-country slope histories (those go to the lake, not the report)."""
    doc = dict(block)
    doc["countries"] = {k: {kk: vv for kk, vv in v.items() if kk != "history"}
                        for k, v in (block.get("countries") or {}).items()}
    return doc


def series_id(name: str) -> str:
    return f"ws_gc_{name.lower()}"


def emit(block: Mapping[str, Any], *, dry_run: bool = False, lake_root: Any = None
         ) -> list[dict[str, Any]]:
    """Lake series and cells per MEASURED country; the gate holds every non-admitted source."""
    from libs.research import sensor_engines as se
    out: list[dict[str, Any]] = []
    for name, row in (block.get("countries") or {}).items():
        if row.get("status") != "MEASURED":
            continue
        sid = series_id(name)
        src = f"{row['long_source']}+{row['short_source']}"
        info: dict[str, Any] = {"country": name, "series_id": sid, "data_source": src}
        if row.get("terms") != "admitted":
            info["cells"] = {"series_id": sid, "emitted": 0, "status": "HELD_TERMS",
                             "data_source": src, "why": "a leg's source is held by the terms "
                                                        "gate: state only"}
            out.append(info)
            continue
        rows = [{**h, "source_id": src} for h in row.get("history") or []]
        if not dry_run and rows:
            info["lake"] = se.write_lake_series(sid, rows, root=lake_root)
        info["cells"] = se.emit_conditioner_cells(
            sid, list(SIGNALS), list(COUNTRIES[name][2]),
            mechanism=(f"{name} curve slope (long minus short rate) as state for its currency "
                       "and index: a flattening curve prices policy tightening ahead of growth, "
                       "a steepening one the reverse"),
            falsifier="gate effect indistinguishable from the shuffled-state gate across the "
                      "judged cells", generator=ENGINE, sides=(1, -1), dry_run=dry_run,
            data_source=src)
        out.append(info)
    return out


def observations(block: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    for name, row in (block.get("countries") or {}).items():
        if row.get("status") != "MEASURED":
            continue
        for metric, v, pct in (("slope", row["slope"], row.get("slope_percentile")),
                               ("long", row["long"], row.get("level_percentile")),
                               ("short", row["short"], None)):
            out.append(sc.make(sensor_class="market_state", kind="state",
                               sensor_id="market:global_curve",
                               source_id=f"{row['long_source']}+{row['short_source']}",
                               metric=metric, value=float(v), entity=name,
                               asset_domain="rates", event_time=row["slope_date"],
                               knowable_at=row["knowable_at"], knowable_basis="declared_lag",
                               received_at=received_at, parse_complete_at=received_at,
                               percentile=pct, terms=row.get("terms")))
    return out
