"""Crop-belt weather for the soft and grain CFDs: what the growing regions are living through.

Source of the facts: github.com/AgriQuantAI/AgriQuant-AI (`config/regions.py`-style tables in its
coffee, cocoa, sugar, corn and wheat modules: each growing region's centroid, its production
share and the crop's damage thresholds, plus the 1994-2021 Brazilian frost record). The repo
carries no LICENSE file (only an MIT badge in its README), so nothing is copied: the region
coordinates are facts and the rest is a desk-native rewrite. Regions the repo does not cover
(robusta, soybean, cotton, orange juice) were chosen by the desk and are marked `desk` below.
EVERY PRODUCTION SHARE IS UNVERIFIED -- the repo author's or the desk's estimate -- and only
weights an average; the gauntlet, not the weight, decides whether a conditioner earns anything.

WHERE THE NUMBERS COME FROM. NASA POWER's daily point API (power.larc.nasa.gov, community AG):
keyless, US-government public data, 1981 to a couple of days ago. AgriQuant reads Open-Meteo,
whose free tier is non-commercial, and INMET/NWS station feeds, which cover one country each;
POWER is one global source the terms allow.

WHAT LEAVES, per crop and day (`cropwx_<crop>_<feature>`), production-share weighted:
  * `tmin`, `tmax` (deg C), `prcp` (mm) -- the belt's day;
  * `prcp30` -- the trailing 30-day rainfall, and `prcp30_z` -- that total against the SAME
    season in PRIOR years only (day-of-year +-7 days, every earlier year held), so a drought or a
    flood reads the same in the wet and the dry season and no future year enters a climatology;
  * `frost7` -- the share of the belt that saw a 2 m minimum at or below the crop's frost line in
    the last 7 days (coffee, sugar, orange juice: the 1994 / 2021 coffee frosts are the canonical
    case);
  * `heat7` -- the share that saw a maximum at or above the crop's heat line (corn and soybean
    pollination, cotton boll set, wheat grain fill).

POINT IN TIME. POWER publishes a day about two days late and REVISES it (near-real-time inputs
are replaced by the final reanalysis weeks later). So each region keeps a FIRST-PRINT ledger: a
day already held is never overwritten, and a value is available at
`max(day + LAG, min(first_seen, day + SETTLE))` -- the moment the desk first saw it, or, for
history that pre-dates the ledger, `SETTLE` after the day (the declared assumption that the
reanalysis has settled by then). A derived value is available when the latest day it reads is.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

API = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = ("T2M_MIN", "T2M_MAX", "PRECTOTCORR")
HISTORY_START = date(1991, 1, 1)
LAG = timedelta(days=2)
SETTLE = timedelta(days=60)
REGIONS_PER_PASS = 12
#: Years one request asks for, so a backfill fits the acquirer's fetch timeout; a region's
#: history arrives over a few passes.
CHUNK_DAYS = 8 * 365
MISSING = -999.0
#: Fewest prior years a seasonal climatology needs before `prcp30_z` reads.
MIN_CLIM_YEARS = 5
#: A crop's value needs regions carrying at least this much of its weight.
MIN_WEIGHT = 0.5


@dataclass(frozen=True)
class Region:
    rid: str
    lat: float
    lon: float
    share: float
    origin: str            # "AgriQuant-AI" or "desk"


@dataclass(frozen=True)
class Crop:
    name: str
    symbols: tuple[str, ...]
    regions: tuple[Region, ...]
    frost_c: float | None = None
    heat_c: float | None = None


_IA, _IL = Region("us_iowa", 42.0, -93.6, 0.18, "AgriQuant-AI"), Region(
    "us_illinois", 40.6, -89.2, 0.16, "AgriQuant-AI")
_ES = Region("br_espirito_santo_conilon", -19.2, -40.3, 0.25, "AgriQuant-AI")
CROPS: tuple[Crop, ...] = (
    # Frost line 2 C at 2 m: leaf frost forms on clear nights with screen-height air near 2 C.
    Crop("coffee_arabica", ("COFARA",), (
        Region("br_sul_de_minas", -21.7, -45.9, 0.52, "AgriQuant-AI"),
        Region("br_cerrado_mineiro", -19.5, -46.5, 0.18, "AgriQuant-AI"),
        Region("br_matas_de_minas", -20.8, -42.5, 0.15, "AgriQuant-AI"),
        Region("br_sao_paulo_mogiana", -20.5, -47.4, 0.05, "AgriQuant-AI"),
        Region("co_eje_cafetero", 4.8, -75.7, 0.10, "desk")), frost_c=2.0),
    Crop("coffee_robusta", ("COFROB",), (
        Region("vn_dak_lak", 12.7, 108.05, 0.35, "desk"),
        Region("vn_lam_dong", 11.9, 108.4, 0.15, "desk"), _ES,
        Region("id_lampung", -5.1, 105.0, 0.15, "desk"),
        Region("ug_central", 0.4, 32.5, 0.10, "desk"))),
    Crop("cocoa", ("USCOCOA", "UKCOCOA"), (
        Region("gh_ashanti", 6.7, -1.6, 0.22, "AgriQuant-AI"),
        Region("gh_western", 5.9, -2.6, 0.18, "AgriQuant-AI"),
        Region("ci_bas_sassandra", 5.4, -6.1, 0.25, "AgriQuant-AI"),
        Region("ci_lacs", 7.0, -5.0, 0.20, "AgriQuant-AI"),
        Region("ci_nawa", 5.0, -6.5, 0.15, "AgriQuant-AI"))),
    Crop("sugar", ("SUGAR", "SUGARRAW"), (
        Region("br_center_south", -22.0, -47.9, 0.38, "AgriQuant-AI"),
        Region("in_maharashtra", 17.5, 75.3, 0.18, "AgriQuant-AI"),
        Region("in_uttar_pradesh", 26.5, 80.9, 0.15, "AgriQuant-AI"),
        Region("th_central", 14.5, 100.5, 0.12, "AgriQuant-AI")), frost_c=2.0),
    Crop("corn", ("CORN",), (
        _IA, _IL,
        Region("us_nebraska", 41.5, -99.9, 0.14, "AgriQuant-AI"),
        Region("us_minnesota", 44.9, -93.1, 0.09, "AgriQuant-AI"),
        Region("us_indiana", 40.3, -86.1, 0.08, "AgriQuant-AI")), heat_c=35.0),
    Crop("wheat", ("WHEAT",), (
        Region("us_kansas", 38.7, -98.3, 0.28, "AgriQuant-AI"),
        Region("us_oklahoma", 35.5, -97.5, 0.11, "AgriQuant-AI"),
        Region("us_texas_panhandle", 35.2, -101.8, 0.09, "AgriQuant-AI"),
        Region("us_washington", 46.9, -119.1, 0.07, "AgriQuant-AI")), heat_c=34.0),
    Crop("soybean", ("SOYBEAN",), (
        _IA, _IL,
        Region("br_mato_grosso_sorriso", -12.5, -55.7, 0.30, "desk"),
        Region("br_parana_cascavel", -24.9, -53.5, 0.12, "desk"),
        Region("ar_pergamino", -33.9, -60.6, 0.15, "desk")), heat_c=35.0),
    Crop("cotton", ("COTTON",), (
        Region("us_lubbock", 33.6, -101.9, 0.25, "desk"),
        Region("in_gujarat_rajkot", 22.3, 70.8, 0.25, "desk"),
        Region("cn_xinjiang_aksu", 41.2, 80.3, 0.30, "desk"),
        Region("br_mato_grosso_cotton", -13.0, -55.9, 0.20, "desk")), heat_c=38.0),
    # Florida's damaging freezes put screen-height air at or below 0 C for hours.
    Crop("oj", ("OJ",), (
        Region("us_florida_polk", 27.9, -81.6, 0.45, "desk"),
        Region("br_sao_paulo_araraquara", -21.8, -48.2, 0.55, "desk")), frost_c=0.0),
)


def regions() -> dict[str, Region]:
    return {r.rid: r for c in CROPS for r in c.regions}


def url(r: Region, start: date, end: date) -> str:
    return (f"{API}?parameters={','.join(PARAMS)}&community=AG&longitude={r.lon}"
            f"&latitude={r.lat}&start={start:%Y%m%d}&end={end:%Y%m%d}&format=JSON")


def parse(payload: bytes) -> dict[str, list[float]]:
    """{YYYY-MM-DD: [tmin, tmax, prcp]} for the days POWER filled in all three (it pads the
    days it has not produced yet with -999)."""
    body = json.loads(payload.decode("utf-8", errors="replace"))
    par = (body.get("properties") or {}).get("parameter") or {}
    cols = [par.get(p) or {} for p in PARAMS]
    out: dict[str, list[float]] = {}
    for k in cols[0]:
        vals = [c.get(k) for c in cols]
        if all(isinstance(v, (int, float)) and math.isfinite(v) and v > MISSING + 1 for v in vals):
            out[f"{k[:4]}-{k[4:6]}-{k[6:8]}"] = [float(v) for v in vals]  # type: ignore[arg-type]
    return out


def _load(path: Path) -> dict[str, Any]:
    try:
        held: dict[str, Any] = json.loads(path.read_text("utf-8"))
        return held
    except (OSError, ValueError):
        return {"days": {}}


def ingest(root: Path, *, fetch: Callable[[str], tuple[bytes | None, str]],
           now: datetime | None = None, per_pass: int = REGIONS_PER_PASS) -> dict[str, Any]:
    """Extend the stalest regions' first-print ledgers (`root/<region>.json`) to the newest day
    POWER has published. A held day is never rewritten."""
    now = now or datetime.now(UTC)
    newest = (now - LAG).date()
    stale: list[tuple[str, Region, dict[str, Any]]] = []
    for rid, r in regions().items():
        held = _load(root / f"{rid}.json")
        last = max(held["days"], default=None)
        if last is None or date.fromisoformat(last) < newest:
            stale.append((last or "", r, held))
    stale.sort(key=lambda t: t[0])
    done: list[str] = []
    refused: dict[str, str] = {}
    for last, r, held in stale[:per_pass]:
        start = date.fromisoformat(last) + timedelta(days=1) if last else HISTORY_START
        raw, why = fetch(url(r, start, min(newest, start + timedelta(days=CHUNK_DAYS))))
        if raw is None:
            refused[r.rid] = why or "unreachable"
            continue
        try:
            got = parse(raw)
        except (ValueError, AttributeError):
            refused[r.rid] = "unparseable"
            continue
        seen = now.isoformat(timespec="seconds")
        new = {d: [*v, seen] for d, v in got.items() if d not in held["days"]}
        if not new:
            continue
        held["days"].update(new)
        held.setdefault("ledger_started", seen)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{r.rid}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(held, sort_keys=True), "utf-8")
        tmp.replace(path)
        done.append(r.rid)
    status = "OK" if done or not stale else ("UNREACHABLE" if refused else "NOTHING_NEW")
    return {"status": status, "regions_extended": done, "refused": refused,
            "regions_stale": max(0, len(stale) - len(done))}


def _region_frame(root: Path) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for rid in regions():
        days = _load(root / f"{rid}.json")["days"]
        if not days:
            continue
        idx = pd.DatetimeIndex(sorted(days), tz="UTC").as_unit("ns")
        rows = [days[d.date().isoformat()] for d in idx]
        seen = pd.to_datetime([r[3] for r in rows], utc=True).as_unit("ns")
        f = pd.DataFrame([r[:3] for r in rows], index=idx, columns=["tmin", "tmax", "prcp"])
        avail = np.maximum(idx + LAG, np.minimum(seen, idx + SETTLE))
        f["avail"] = pd.DatetimeIndex(avail)
        out[rid] = f.asfreq("D")
    return out


def seasonal_z(s: pd.Series, *, half_window: int = 7, min_years: int = MIN_CLIM_YEARS) -> pd.Series:
    """`s` against the same calendar window (+-`half_window` days) in every PRIOR year."""
    s = s.asfreq("D")
    samples = []
    for k in range(1, 60):
        shifted = s.shift(365 * k)
        if shifted.notna().sum() == 0:
            break
        for j in range(-half_window, half_window + 1, 2):
            samples.append(shifted.shift(j).rename(f"{k}_{j}"))
    if not samples:
        return pd.Series(np.nan, index=s.index)
    m = pd.concat(samples, axis=1)
    years = m.notna().sum(axis=1) / (half_window + 1)
    mu, sd = m.mean(axis=1), m.std(axis=1).replace(0.0, np.nan)
    z = (s - mu) / sd
    return z.where(years >= min_years)


def _crop_features(crop: Crop, reg: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    present = [r for r in crop.regions if r.rid in reg]
    if not present:
        return {}
    idx = reg[present[0].rid].index
    for r in present[1:]:
        idx = idx.union(reg[r.rid].index)
    per: dict[str, dict[str, pd.Series]] = {}
    for r in present:
        f = reg[r.rid].reindex(idx)
        p30 = f["prcp"].rolling(30, min_periods=30).sum()
        cols = {"tmin": f["tmin"], "tmax": f["tmax"], "prcp": f["prcp"], "prcp30": p30,
                "prcp30_z": seasonal_z(p30)}
        if crop.frost_c is not None:
            cols["frost7"] = (f["tmin"] <= crop.frost_c).astype(float).where(
                f["tmin"].notna()).rolling(7, min_periods=7).max()
        if crop.heat_c is not None:
            cols["heat7"] = (f["tmax"] >= crop.heat_c).astype(float).where(
                f["tmax"].notna()).rolling(7, min_periods=7).max()
        # NANOSECONDS BY NAME, both ways (audit PR166_v2): `astype("int64")` returns the frame's
        # own resolution (us or s under pandas 2), and line 279 reads it back as ns.
        av = (f["avail"].astype("datetime64[ns, UTC]").astype("int64")
              .where(f["avail"].notna()).astype(float))
        cols["_avail1"], cols["_avail30"] = av, av.rolling(30, min_periods=1).max()
        per[r.rid] = cols
    total = sum(r.share for r in crop.regions)
    out: dict[str, pd.DataFrame] = {}
    for feat in [k for k in per[present[0].rid] if not k.startswith("_")]:
        val = pd.DataFrame({r.rid: per[r.rid][feat] for r in present})
        w = pd.Series({r.rid: r.share for r in present})
        have = val.notna().mul(w, axis=1)
        num = val.fillna(0.0).mul(w, axis=1).sum(axis=1)
        weight = have.sum(axis=1)
        v = (num / weight.replace(0.0, np.nan)).where(weight >= MIN_WEIGHT * total)
        which = "_avail1" if feat in ("tmin", "tmax", "prcp") else "_avail30"
        av = pd.DataFrame({r.rid: per[r.rid][which] for r in present}).where(val.notna())
        avail = pd.to_datetime(av.max(axis=1), unit="ns", utc=True)
        f = pd.DataFrame({"value": v, "available_time": avail}).dropna()
        out[f"cropwx_{crop.name}_{feat}"] = f
    return out


def frames(root: Path, now: datetime | None = None) -> dict[str, pd.DataFrame]:
    """Per (crop, feature): event-dated `value` + `available_time`, for the PIT certificate."""
    now = now or datetime.now(UTC)
    reg = _region_frame(root)
    out: dict[str, pd.DataFrame] = {}
    for crop in CROPS:
        for name, f in _crop_features(crop, reg).items():
            out[name] = f.loc[f["available_time"] <= pd.Timestamp(now)]
    return out


def symbols_for(series: str) -> tuple[str, ...]:
    """The MT5 CFDs a `cropwx_<crop>_...` series conditions."""
    for crop in CROPS:
        if series.startswith(f"cropwx_{crop.name}_"):
            return crop.symbols
    return ()
