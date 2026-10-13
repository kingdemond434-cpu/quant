"""THE FIRST GEOINT FACTORY: Cushing crude tank fill from free Sentinel-2 imagery, PIT, judged.

THE OWNER'S ASK (2026-10-13). A GEOINT / physical-economy alpha factory that treats every remotely
observable physical variable as a candidate economic state, starting with free imagery. The first
slice is the oil-tank idea: Sentinel-2 L2A (free, 10 m, ~5-day revisit, sun-synchronous so the
shadow geometry repeats) over Cushing, Oklahoma -- ~300 floating-roof tanks ~60 m wide whose roof
shadow lengthens as they empty.

ONE PASS (`--once`), on the hourly cycle (leg `geoint_tank_fill`):

  1. SCENES. List the 14SPE granules on the AWS open-data bucket (current and previous month every
     pass; the whole archive back to ``START`` once a day, cached), read each new scene's STAC item
     (acquisition time, sun azimuth/elevation, cloud cover, processing baseline) and the S3
     LastModified of that item -- the instant the scene became public on this bucket.
  2. TANKS. ``desks/mt5/data/geoint/cushing_tanks.json`` is DERIVED FROM THE IMAGERY: bright round
     40..120 m components on a median composite of clear high-sun scenes, inside the hub box, in a
     cluster (see ``libs/geoint/tanks.detect_tanks``). Built once when absent, with its scene ids.
  3. FILL. Per tank per scene: sun-side half-disk brightness over the ground ring, shadow contrast
     against the anti-sun half, the sun-geometry correction to a fill index and its sigma; per
     scene the hub aggregate (count, mean, trimmed mean, median, capacity-weighted, MAD, sigma).
  4. PIT. ``event_time`` = acquisition; ``knowable_at`` = the item's S3 LastModified (MEASURED,
     basis printed_stamp), else acquisition + ``DECLARED_LATENCY_H`` (basis declared_lag).
  5. CALIBRATION. Against EIA weekly Cushing crude stocks (``W_EPC0_SAX_YCUOK_MBBL``) when the
     owner archive (``data/owner_macro.json``) carries it: level and change correlation, and the
     satellite's lead over the Wednesday release. Absent -> UNMEASURED, by name.
  6. CEILING. ``libs/research/ceiling.ceiling_test``: what a PERFECT, k-days-early reading of the
     Cushing stock change would have been worth on XTIUSD / XBRUSD. Cells are judged only where it
     shows GAIN (decision recorded per sensor x entity x asset).
  7. LEDGER AND CELLS through ``libs/geoint/sensor_bridge``: SensorLedger rows and conditioner
     cells (level, change, satellite-minus-official disagreement), terms-gated and fail-closed.

Artifact: ``desks/mt5/reports/GEOINT_TANK_FILL.json``. Imagery is never stored: windows are read,
measured and dropped; per-scene measurements go to the gitignored ``desks/mt5/data/geoint/
scene_store.jsonl``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from libs.geoint import sensor_bridge as bridge  # noqa: E402
from libs.geoint import sentinel2 as s2  # noqa: E402
from libs.geoint import tanks as tk  # noqa: E402
from libs.research import ceiling as ceil  # noqa: E402

UNMEASURED = "UNMEASURED"
GEO = BASE / "data" / "geoint"
REGISTRY = GEO / "cushing_tanks.json"
STORE = GEO / "scene_store.jsonl"
LISTING = GEO / "listing_cache.json"
REPORT = BASE / "reports" / "GEOINT_TANK_FILL.json"
OWNER_ARCHIVE = REPO / "data" / "owner_macro.json"
UNIVERSE = BASE / "data" / "universe"

TILE = "14SPE"
BAND = "B08"
#: The Cushing hub box (lon/lat), from the imagery: every tank farm of the hub lies inside it on
#: the 2024-07 composite (the town is excluded by the cluster rule, not by the box).
HUB_LONLAT = (-96.79, 35.905, -96.70, 36.035)
START = (2019, 1)
#: L2A on this bucket: measured 2024-07-02 17:24 UTC acquisition -> item LastModified 2024-07-03
#: 03:21 UTC (~10 h). The declared fallback, used only when a scene's stamp is absent, is 48 h --
#: conservative: a late knowable_at only makes a measured reaction later, never earlier.
DECLARED_LATENCY_H = 48.0
MIN_VALID_FRAC = 0.8
MAX_CLOUD_PCT = 60.0
REGISTRY_SCENES = 6
REGISTRY_MIN_ELEV = 60.0
EIA_CUSHING = "W_EPC0_SAX_YCUOK_MBBL"
ASSETS = ("XTIUSD", "XBRUSD")
SERIES_ID = "geoint_cushing_tank_fill"
SIGNALS = ("fill_level", "fill_change", "sat_minus_official")
MECHANISM = ("Cushing is the WTI delivery hub: its crude stocks set the front spread and the "
             "outright, and the EIA prints them weekly with a lag. Floating-roof tank shadows "
             "read the same stocks from orbit days before the print; a satellite fill that "
             "disagrees with the consensus/last print anticipates the print's surprise.")
FALSIFIER = ("the satellite fill change does not order the next EIA Cushing change, or the "
             "WTI/Brent return into the release, out of sample")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime | None) -> str:
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z") if t else UNMEASURED


def hub_bbox_utm() -> tuple[float, float, float, float]:
    lo0, la0, lo1, la1 = HUB_LONLAT
    x0, y0, _ = s2.lonlat_to_utm(lo0, la0, 14)
    x1, y1, _ = s2.lonlat_to_utm(lo1, la1, 14)
    x2, y2, _ = s2.lonlat_to_utm(lo0, la1, 14)
    x3, y3, _ = s2.lonlat_to_utm(lo1, la0, 14)
    return min(x0, x2), min(y0, y3), max(x1, x3), max(y1, y2)


# ============================================================================== stores
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=False, default=str)
        fh.write("\n")
    os.replace(tmp, path)


def load_store(path: Path = STORE) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("scene_id"):
            out[str(row["scene_id"])] = row
    return out


def append_store(row: Mapping[str, Any], path: Path = STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def months(start: tuple[int, int], end: date) -> list[tuple[int, int]]:
    y, m = start
    out = []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def list_scenes(full: bool, today: date, listing_path: Path = LISTING) -> list[s2.Scene]:
    """Scene ids by month: the last two months every pass, the archive when `full` (cached; a
    month two or more back is final once listed)."""
    cache = _read_json(listing_path) or {}
    months_all = months(START, today)
    recent = set(months_all[-2:])
    want = months_all if full else [m for m in months_all if f"{m[0]}-{m[1]}" not in cache
                                    or m in recent]
    for ym in want:
        key = f"{ym[0]}-{ym[1]}"
        if key in cache and ym not in recent:
            continue
        try:
            cache[key] = [sc.scene_id for sc in s2.search(TILE, [ym])]
        except Exception as exc:  # a failed listing is recorded, the month is retried next pass
            cache.pop(key, None)
            print(f"[geoint] listing {key} failed: {type(exc).__name__}: {str(exc)[:80]}")
    _write_json(listing_path, cache)
    scenes = []
    for key, ids in cache.items():
        y, m = (int(x) for x in key.split("-"))
        base = s2.tile_prefix(TILE)
        for sid in ids:
            scenes.append(s2.Scene(scene_id=sid, tile=TILE, prefix=f"{base}{y}/{m}/{sid}/"))
    return sorted(scenes, key=lambda s: (s.scene_id.split("_")[2], s.scene_id))


# ============================================================================== registry
def build_registry(candidates: Sequence[s2.Scene], bbox: tuple[float, float, float, float]
                   ) -> dict[str, Any]:
    """Detect the tanks on a median composite of clear high-sun scenes; never invented."""
    stack, used, tr = [], [], None
    for sc in candidates:
        try:
            m = s2.load_metadata(sc)
        except Exception:
            continue
        if (m.cloud_cover is None or m.cloud_cover > 2.0 or m.sun_elevation is None
                or m.sun_elevation < REGISTRY_MIN_ELEV):
            continue
        try:
            w = s2.read_window(m, bbox, BAND)
        except Exception:
            continue
        if float(w.valid.mean()) < 0.97:
            continue
        if tr is not None and (w.reflectance.shape != stack[0].shape):
            continue
        stack.append(np.where(w.valid, w.reflectance, np.nan))
        used.append({"scene_id": m.scene_id, "acquired": m.acquired,
                     "sun_elevation": m.sun_elevation, "cloud_cover": m.cloud_cover})
        tr = w.transform
        if len(stack) >= REGISTRY_SCENES:
            break
    if not stack or tr is None:
        return {"status": UNMEASURED, "why": "no clear high-sun scene could be read",
                "tanks": []}
    comp = np.nanmedian(np.array(stack), axis=0)
    valid = np.isfinite(comp)
    tanks, reasons = tk.detect_tanks(np.nan_to_num(comp), valid, tr, bbox=bbox)
    rows = []
    for t in tanks:
        lon, lat = s2.utm_to_lonlat(t.x, t.y, 14)
        rows.append(tk.Tank(**{**asdict(t), "lon": lon, "lat": lat}).to_row())
    return {"status": "DERIVED", "derived_at": _iso(_now()),
            "derived_from": {"tile": TILE, "band": BAND, "crs": "EPSG:32614",
                             "composite": "per-pixel median of SCL-clear reflectance",
                             "scenes": used},
            "method": ("bright round components against a 31-px local median background; "
                       "relative contrast > 0.3; equivalent diameter 40..120 m; roundness "
                       ">= 0.6; >= 2 other detections within 250 m (cluster rule); centre and "
                       "radius refined by fractional area (libs/geoint/tanks.detect_tanks)"),
            "hub_lonlat": list(HUB_LONLAT), "rejections": reasons,
            "not_detected": ("dark- and grey-roofed tanks (fixed roofs, unpainted or "
                             "low-contrast floating roofs) do not pass the bright-component "
                             "rule and are UNMEASURED by this registry"),
            "n_tanks": len(rows), "tanks": rows}


def registry_tanks(reg: Mapping[str, Any]) -> list[tk.Tank]:
    out = []
    for r in reg.get("tanks") or []:
        try:
            out.append(tk.Tank(tank_id=str(r["tank_id"]), x=float(r["x"]), y=float(r["y"]),
                               radius_m=float(r["radius_m"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def registry_id(reg: Mapping[str, Any]) -> str:
    return f"{reg.get('derived_at', '')}/{reg.get('n_tanks', 0)}"


# ============================================================================== one scene
def pit_stamp(acquired: datetime, stamped: datetime | None) -> dict[str, Any]:
    """The world clock of one scene. The S3 LastModified of its item JSON is the measured instant
    the scene became public here (printed_stamp); a stamp that is absent or precedes the
    acquisition is not trusted, and the declared latency stands in (declared_lag)."""
    if stamped is not None and stamped >= acquired:
        return {"knowable_at": _iso(stamped), "knowable_basis": "printed_stamp",
                "publication_latency_h": round((stamped - acquired).total_seconds() / 3600, 3)}
    return {"knowable_at": _iso(acquired + timedelta(hours=DECLARED_LATENCY_H)),
            "knowable_basis": "declared_lag", "publication_latency_h": UNMEASURED}


def measure_scene(sc: s2.Scene, tanks: Sequence[tk.Tank], bbox: tuple[float, float, float, float],
                  reg_id: str) -> dict[str, Any]:
    received = _now()
    m = s2.load_metadata(sc)
    acquired = s2.parse_time(m.acquired)
    stamped = s2.parse_time(m.item_last_modified)
    row: dict[str, Any] = {"scene_id": m.scene_id, "registry": reg_id,
                           "acquired": _iso(acquired), "item_last_modified":
                           m.item_last_modified or UNMEASURED,
                           "cloud_cover": m.cloud_cover, "sun_azimuth": m.sun_azimuth,
                           "sun_elevation": m.sun_elevation,
                           "processing_baseline": m.processing_baseline,
                           "received_at": _iso(received)}
    if acquired is None:
        return {**row, "status": "REFUSED", "why": "no acquisition time in the STAC item"}
    row.update(pit_stamp(acquired, stamped))
    if m.sun_azimuth is None or m.sun_elevation is None:
        return {**row, "status": "REFUSED", "why": "no sun geometry in the STAC item"}
    if m.cloud_cover is not None and m.cloud_cover > MAX_CLOUD_PCT:
        return {**row, "status": "CLOUDY", "why": f"tile cloud cover {m.cloud_cover:.1f}%"}
    w = s2.read_window(m, bbox, BAND)
    vf = float(w.valid.mean())
    row.update(valid_fraction=round(vf, 4), bytes_read=w.bytes_read, scl=w.scl_counts)
    if vf < MIN_VALID_FRAC:
        return {**row, "status": "CLOUDY", "why": f"hub window {vf:.0%} clear < "
                                                   f"{MIN_VALID_FRAC:.0%}"}
    rows = [tk.measure_tank(w.reflectance, w.valid, w.transform, t, sun_azimuth=m.sun_azimuth,
                            sun_elevation=m.sun_elevation, others=tanks) for t in tanks]
    hub = tk.hub_index(rows)
    compact = [{k: r.get(k) for k in ("tank_id", "status", "fill_index", "fill_sigma",
                                      "shadow_contrast", "b_sun_half", "b_full_disk",
                                      "b_anti_half")} for r in rows]
    return {**row, "status": hub.get("status", UNMEASURED), "hub": hub, "tanks": compact}


# ============================================================================== series
def hub_series(store: Mapping[str, Mapping[str, Any]], reg_id: str) -> list[dict[str, Any]]:
    """One row per MEASURED scene (same registry), in acquisition order, with the change."""
    rows = sorted((r for r in store.values() if r.get("registry") == reg_id
                   and r.get("status") == "MEASURED"), key=lambda r: str(r.get("acquired")))
    out: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for r in rows:
        hub = r.get("hub") or {}
        f = hub.get("fill_capacity_weighted")
        if f is None:
            continue
        item = {"scene_id": r["scene_id"], "event_time": r["acquired"],
                "knowable_at": r["knowable_at"], "knowable_basis": r["knowable_basis"],
                "received_at": r.get("received_at", UNMEASURED),
                "publication_latency_h": r.get("publication_latency_h"),
                "sun_elevation": r.get("sun_elevation"), "n_tanks": hub.get("n_tanks"),
                "fill_level": f, "fill_median": hub.get("fill_median"),
                "fill_trimmed_mean": hub.get("fill_trimmed_mean"),
                "fill_dispersion_mad": hub.get("fill_dispersion_mad"),
                "fill_sigma": hub.get("fill_mean_sigma"),
                "fill_change": None if prev is None else round(f - prev["fill_level"], 5)}
        out.append(item)
        prev = item
    return out


def load_eia(path: Path = OWNER_ARCHIVE, series: str = EIA_CUSHING
             ) -> tuple[list[tuple[str, float]], str]:
    doc = _read_json(path)
    rows = ((doc or {}).get("series") or {}).get(series) if isinstance(doc, dict) else None
    if not rows:
        return [], (f"{series} absent from {path.relative_to(REPO).as_posix()}: the owner feed "
                    f"must collect PET.{series}.W (api.eia.gov v2 seriesid) on the box")
    clean = []
    for r in rows:
        try:
            clean.append((str(r[0])[:10], float(r[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(c for c in clean if math.isfinite(c[1])), ""


def eia_release_at(week_end: str) -> datetime:
    """The WPSR release instant for a week ending `week_end`: the desk's calendar when present,
    else the conservative Thursday-noon-ET bound (week end + 6 days, 17:00 UTC; never early)."""
    try:
        import importlib
        ps = importlib.import_module("desks.mt5.macro.physical_state")
        at = ps.release_at(week_end)[0]
        if isinstance(at, datetime):
            return at
    except Exception:  # the conservative bound below is the fallback
        pass
    d = date.fromisoformat(week_end[:10]) + timedelta(days=6)
    return datetime(d.year, d.month, d.day, 17, 0, tzinfo=UTC)


def _corr(a: Sequence[float], b: Sequence[float]) -> dict[str, Any]:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 8:
        return {"n": n, "pearson": None, "spearman": None, "p_spearman": None,
                "verdict": UNMEASURED, "why": f"n={n} < 8"}
    pr = float(np.corrcoef(x[ok], y[ok])[0, 1])
    rho, p, _ = ceil.spearman_perm(x[ok], y[ok], n_null=999)
    return {"n": n, "pearson": round(pr, 4), "spearman": None if rho is None else round(rho, 4),
            "p_spearman": p, "verdict": "MEASURED"}


def calibrate(series: Sequence[Mapping[str, Any]], eia: Sequence[tuple[str, float]]
              ) -> dict[str, Any]:
    """Satellite fill vs EIA Cushing stocks: the scene nearest each week end (within 3 days),
    levels and week-on-week changes, and the satellite's lead over the release."""
    if not eia:
        return {"status": UNMEASURED, "why": "no EIA Cushing series"}
    if not series:
        return {"status": UNMEASURED, "why": "no satellite series"}
    st = [(s2.parse_time(r["event_time"]), r) for r in series]
    pairs = []
    for we, val in eia:
        d = datetime.fromisoformat(we).replace(tzinfo=UTC) + timedelta(hours=12)
        best = min(st, key=lambda p: abs((p[0] - d).total_seconds()) if p[0] else 1e18)
        if best[0] is None or abs((best[0] - d).total_seconds()) > 3 * 86400:
            continue
        rel = eia_release_at(we)
        kn = s2.parse_time(best[1]["knowable_at"])
        pairs.append({"week_end": we, "eia_kbbl": val, "scene_id": best[1]["scene_id"],
                      "fill": best[1]["fill_level"],
                      "lead_h": None if kn is None else round((rel - kn).total_seconds() / 3600,
                                                              2)})
    lv = _corr([p["fill"] for p in pairs], [p["eia_kbbl"] for p in pairs])
    ch_s = [b["fill"] - a["fill"] for a, b in pairwise(pairs)]
    ch_e = [b["eia_kbbl"] - a["eia_kbbl"] for a, b in pairwise(pairs)]
    leads = [p["lead_h"] for p in pairs if p["lead_h"] is not None]
    return {"status": "MEASURED" if lv["verdict"] == "MEASURED" else UNMEASURED,
            "n_matched_weeks": len(pairs), "levels": lv, "changes": _corr(ch_s, ch_e),
            "lead_over_release_h": {"median": float(np.median(leads)) if leads else None,
                                    "min": min(leads) if leads else None,
                                    "max": max(leads) if leads else None},
            "pairs": pairs}


def load_bars(symbol: str) -> tuple[list[datetime], list[float]] | None:
    p = UNIVERSE / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or len(df) < 100:
        return None
    idx = pd.to_datetime(df.index, utc=True)
    return [t.to_pydatetime() for t in idx], [float(v) for v in df["close"]]


def ceilings(eia: Sequence[tuple[str, float]]) -> dict[str, Any]:
    """The perfect-information ceiling per asset for the Cushing weekly change."""
    out: dict[str, Any] = {}
    if len(eia) < 2:
        for a in ASSETS:
            c = {"verdict": UNMEASURED, "why": "no EIA Cushing series to test", "n": 0,
                 "asset": a, "entity": "cushing_crude_stocks"}
            out[a] = {"ceiling": c, "decision": ceil.decision(c)}
        return out
    state = [(eia_release_at(b[0]), b[1] - a[1]) for a, b in pairwise(eia)]
    for a in ASSETS:
        bars = load_bars(a)
        if bars is None:
            c = {"verdict": UNMEASURED, "why": f"no {a}_H1.parquet bars on this host", "n": 0,
                 "asset": a, "entity": "cushing_crude_stocks"}
        else:
            c = ceil.ceiling_test(state, bars[0], bars[1], entity="cushing_crude_stocks",
                                  asset=a)
        out[a] = {"ceiling": c, "decision": ceil.decision(c)}
    return out


def _slope_before(pairs: Sequence[Mapping[str, Any]], at: datetime) -> float | None:
    """Stocks per unit fill, fitted ONLY on weeks whose EIA release precedes `at` (PIT)."""
    xs, ys = [], []
    for p in pairs:
        rel = eia_release_at(str(p["week_end"]))
        if rel <= at:
            xs.append(float(p["fill"]))
            ys.append(float(p["eia_kbbl"]))
    if len(xs) < 8 or float(np.std(xs)) <= 0:
        return None
    return float(np.polyfit(xs, ys, 1)[0])


def lake_rows(series: Sequence[Mapping[str, Any]], eia: Sequence[tuple[str, float]],
              pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The conditioner frame: level, change and satellite-minus-official per scene, stamped at
    knowable_at. The disagreement converts the satellite's fill change to barrels with a slope
    fitted only on weeks already released at the scene's knowable instant, and subtracts the last
    OFFICIAL change knowable then; without both it is left empty, never filled."""
    releases = [(eia_release_at(we), v) for we, v in eia]
    out = []
    for r in series:
        kn = s2.parse_time(r["knowable_at"])
        dis = None
        if kn is not None and r.get("fill_change") is not None:
            slope = _slope_before(pairs, kn)
            known = [(t, v) for t, v in releases if t <= kn]
            if slope is not None and len(known) >= 2:
                last_official_change = known[-1][1] - known[-2][1]
                dis = round(slope * float(r["fill_change"]) - last_official_change, 3)
        out.append({"available_time": r["knowable_at"], "event_time": r["event_time"],
                    "source_id": bridge.SOURCE_ID, "fill_level": r["fill_level"],
                    "fill_change": r.get("fill_change"), "sat_minus_official": dis})
    return out


# ============================================================================== the pass
def run(*, max_scenes: int = 6, budget_s: float = 600.0, full_listing: bool | None = None,
        pick: str = "newest", emit: bool = True, dry_run: bool = False,
        report_path: Path = REPORT) -> dict[str, Any]:
    t0 = time.time()
    now = _now()
    bbox = hub_bbox_utm()
    prev = _read_json(report_path) or {}
    last_full = s2.parse_time(str(prev.get("last_full_listing") or ""))
    if full_listing is None:
        full_listing = last_full is None or (now - last_full) > timedelta(hours=24)
    errors: list[str] = []
    try:
        scenes = list_scenes(bool(full_listing), now.date())
    except Exception as exc:
        scenes = []
        errors.append(f"listing: {type(exc).__name__}: {str(exc)[:120]}")
    reg = _read_json(REGISTRY)
    if not isinstance(reg, dict) or not reg.get("tanks"):
        summer = [s for s in scenes if s.scene_id.split("_")[2][4:6] in ("06", "07")]
        reg = build_registry(list(reversed(summer)), bbox)
        if reg.get("tanks"):
            _write_json(REGISTRY, reg)
    tanks = registry_tanks(reg)
    reg_id = registry_id(reg)
    store = load_store()
    todo = [s for s in scenes if s.scene_id not in store
            or store[s.scene_id].get("registry") != reg_id]
    if pick == "spread" and todo:
        idx = np.unique(np.linspace(0, len(todo) - 1, num=min(max_scenes, len(todo)))
                        .round().astype(int))
        todo = [todo[i] for i in idx]
    else:
        todo = list(reversed(todo))   # newest first: the current state before the backfill
    measured = 0
    for sc in todo[:max_scenes] if tanks else []:
        if time.time() - t0 > budget_s:
            break
        try:
            row = measure_scene(sc, tanks, bbox, reg_id)
        except Exception as exc:
            row = {"scene_id": sc.scene_id, "registry": reg_id, "status": "ERROR",
                   "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
            errors.append(f"{sc.scene_id}: {row['why']}")
        append_store(row)
        store[sc.scene_id] = row
        measured += 1
    series = hub_series(store, reg_id)
    eia, eia_why = load_eia()
    cal = calibrate(series, eia)
    if eia_why:
        cal["why"] = eia_why
    ceil_rows = ceilings(eia)
    obs = [bridge.observation_row(
        entity="cushing_hub", metric="tank_fill_capacity_weighted", value=float(r["fill_level"]),
        event_time=r["event_time"], knowable_at=r["knowable_at"],
        knowable_basis=r["knowable_basis"], received_at=r["received_at"],
        uncertainty=r.get("fill_sigma"),
        raw_pointer=f"{s2.BUCKET_URL}/{s2.tile_prefix(TILE)}{r['scene_id']}",
        attributes={"scene_id": r["scene_id"], "n_tanks": r["n_tanks"],
                    "registry": reg_id, "band": BAND}) for r in series]
    ledger = bridge.append_ledger(obs) if (emit and not dry_run) else {
        "status": "NOT_RUN", "why": "emit disabled for this pass"}
    pairs = list(cal.pop("pairs", None) or [])
    cal["pairs_tail"] = pairs[-12:]
    lake = lake_rows(series, eia, pairs)
    cells: dict[str, Any] = {}
    for asset, c in ceil_rows.items():
        d = c["decision"]
        cells[asset] = (bridge.emit_cells(SERIES_ID, lake, SIGNALS, [asset],
                                          judge=bool(d["judge_cells"]), judge_why=d["why"],
                                          mechanism=MECHANISM, falsifier=FALSIFIER,
                                          dry_run=dry_run or not emit)
                        if emit else {"status": "NOT_RUN"})
    lat = [float(r["publication_latency_h"]) for r in series
           if isinstance(r.get("publication_latency_h"), (int, float))]
    fills = [float(r["fill_level"]) for r in series]
    statuses: dict[str, int] = {}
    for r in store.values():
        if r.get("registry") == reg_id:
            statuses[str(r.get("status"))] = statuses.get(str(r.get("status")), 0) + 1
    report = {
        "schema": "geoint_tank_fill/1", "generated_at": _iso(now),
        "last_full_listing": _iso(now) if full_listing else prev.get("last_full_listing"),
        "sensor_id": bridge.SENSOR_ID, "source_id": bridge.SOURCE_ID,
        "data_source": bridge.DATA_SOURCE, "tile": TILE, "band": BAND,
        "hub_lonlat": list(HUB_LONLAT),
        "priors": {"wall_h_m": tk.WALL_H_M, "shadow_depth": tk.SHADOW_DEPTH,
                   "roof_inset_px": tk.ROOF_INSET, "ring_px": [tk.RING_IN, tk.RING_OUT],
                   "declared_latency_h": DECLARED_LATENCY_H,
                   "note": "declared, never fitted: the absolute fill level is a geometric-prior "
                           "index UNCALIBRATED until the EIA join below is MEASURED"},
        "registry": {"path": REGISTRY.relative_to(REPO).as_posix(), "id": reg_id,
                     "status": reg.get("status"), "n_tanks": len(tanks),
                     "derived_from": [s.get("scene_id") for s in
                                      (reg.get("derived_from") or {}).get("scenes") or []]},
        "scenes": {"listed": len(scenes), "measured_this_pass": measured,
                   "by_status": statuses, "series_n": len(series)},
        "publication_latency_h": ({"n": len(lat), "median": float(np.median(lat)),
                                   "p95": float(np.percentile(lat, 95)), "max": max(lat)}
                                  if lat else UNMEASURED),
        "index": ({"n": len(fills), "first": series[0]["event_time"],
                   "last": series[-1]["event_time"], "mean": round(float(np.mean(fills)), 4),
                   "sd": round(float(np.std(fills)), 4), "min": round(min(fills), 4),
                   "max": round(max(fills), 4),
                   "median_sigma": round(float(np.median([r["fill_sigma"] for r in series
                                                          if r.get("fill_sigma") is not None])),
                                         4)} if fills else UNMEASURED),
        "series": series,
        "calibration_eia": cal,
        "ceiling": {a: {"verdict": c["ceiling"].get("verdict"), "n": c["ceiling"].get("n"),
                        "best_lead_days": c["ceiling"].get("best_lead_days"),
                        "best_rho": c["ceiling"].get("best_rho"),
                        "why": c["ceiling"].get("why"), "leads": c["ceiling"].get("leads"),
                        "decision": c["decision"]} for a, c in ceil_rows.items()},
        "decisions": [{"sensor": bridge.SENSOR_ID, "entity": "cushing_hub", "asset": a,
                       **c["decision"]} for a, c in ceil_rows.items()],
        "ledger": ledger,
        "observations": {"n": len(obs), "contract": sorted({str(o.get("contract"))[:40]
                                                            for o in obs}),
                         "tail": obs[-3:]},
        "cells": cells,
        "terms": dict(zip(("ok", "why"), bridge.terms(), strict=True)),
        "errors": errors[:10], "elapsed_s": round(time.time() - t0, 1),
    }
    if not dry_run:
        _write_json(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--max-scenes", type=int, default=6)
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--full-listing", action="store_true")
    ap.add_argument("--pick", choices=("newest", "spread"), default="newest")
    ap.add_argument("--no-emit", action="store_true", help="measure and report, no ledger/cells")
    a = ap.parse_args(argv)
    rep = run(max_scenes=a.max_scenes, budget_s=a.budget_s,
              full_listing=True if a.full_listing else None, pick=a.pick, emit=not a.no_emit)
    idx = rep.get("index")
    print(f"[geoint] tanks={rep['registry']['n_tanks']} scenes listed={rep['scenes']['listed']} "
          f"measured={rep['scenes']['measured_this_pass']} series={rep['scenes']['series_n']} "
          f"index={idx if not isinstance(idx, dict) else (idx['mean'], idx['sd'])} "
          f"ceiling={[(k, v['verdict']) for k, v in rep['ceiling'].items()]} "
          f"terms={rep['terms']['ok']} elapsed={rep['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
