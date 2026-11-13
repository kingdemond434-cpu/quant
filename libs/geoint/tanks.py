"""FLOATING-ROOF TANK FILL FROM 10 m IMAGERY: detect the tanks, then read each roof's shadow.

THE PHYSICS (owner's brief, 2026-10-13). A floating roof rides on the oil. The tank wall stands
above it by ``h = H * (1 - fill)``; the sun at elevation ``el`` throws the wall's shadow onto the
roof for a length ``L = h / tan(el)``, on the half of the roof NEAREST the sun (the sun-side wall
casts it inward). An emptier tank therefore has a longer crescent, and at a 60 m tank imaged at
10 m that crescent is SUB-PIXEL: it is not seen, it is AVERAGED into the roof's brightness.

TWO LESSONS FROM THE SOURCE, BOTH BUILT IN:

  1. NORMALISE AGAINST THE GROUND RING. The raw before/after difference was ~0 because the whole
     scene darkened (gain, haze, sensor ageing). Every roof statistic here is divided by the
     median of the same scene's ground ring around that tank (``RING_IN``..``RING_OUT`` pixels
     beyond the wall, excluding other tanks), so a scene-wide gain cancels exactly.
  2. MEASURE THE SHADOW-SIDE HALF. Averaging the whole disk buries a crescent that covers a
     fixed side. The sun-side half-disk (sun azimuth from the scene's own metadata) carries the
     whole shadow on half the area, which doubles its contrast against the same pixel noise.

THE SUN-GEOMETRY CORRECTION. With the anti-sun half of the same roof as the lit reference
(same tank, same scene, same albedo), the shadow contrast is ``c = 1 - half_sun / half_anti``.
For a crescent narrow against the radius the shaded share of the half-disk is ~``4L / (pi r)``,
and a shaded roof pixel keeps ``1 - SHADOW_DEPTH`` of its brightness, so

    1 - fill = c * pi * r * tan(el) / (4 * SHADOW_DEPTH * WALL_H)

``WALL_H`` (wall height above the lowest roof position) and ``SHADOW_DEPTH`` are DECLARED priors,
recorded on every output, never fitted on the series they then explain. Their error is a scale on
the index, which the calibration against EIA Cushing stocks measures; the CHANGE in fill a tank
shows between scenes is what the factory trades on, and a scale does not move a z-score.

UNCERTAINTY is propagated from pixel noise: the ground ring's robust spread (MAD) is the
per-pixel sigma, the two half means carry sigma / sqrt(n), and the delta method carries that to
fill. A tank whose disk or ring is cloud-masked past ``MAX_MASKED`` is refused, by name.

DETECTION derives the registry from the imagery itself (no invented coordinates): bright compact
components against a local-median background on a median composite of clear high-sun scenes,
kept when their equivalent diameter is 40..120 m and they are round (moments + compactness);
radius is refined by fractional area so a 61 m tank is not quantised to 60 or 70.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy import ndimage

from libs.geoint.cog import GeoTransform

#: DECLARED PRIORS (not fitted). Cushing floating-roof tanks are ~12-15 m tall with the roof's
#: lowest rest a couple of metres up; 13 m of travel is the midpoint. A shaded roof pixel keeps
#: ~30% of its sunlit NIR brightness (diffuse sky light), so SHADOW_DEPTH = 0.7.
WALL_H_M = 13.0
SHADOW_DEPTH = 0.7
PIXEL_M = 10.0
RING_IN = 2.0       # pixels beyond the wall where the ground ring starts (clear of the rim)
RING_OUT = 5.0
ROOF_INSET = 0.5
SUBSAMPLE = 5       # sub-pixel samples per axis for fractional pixel weights
MAX_MASKED = 0.2
MIN_D_M, MAX_D_M = 40.0, 120.0


@dataclass(frozen=True)
class Tank:
    tank_id: str
    x: float            # UTM easting of the centre (m)
    y: float            # UTM northing (m)
    radius_m: float
    lon: float = float("nan")
    lat: float = float("nan")
    contrast: float = float("nan")
    roundness: float = float("nan")
    method: str = ""

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("x", "y", "radius_m", "lon", "lat", "contrast", "roundness"):
            v = d[k]
            d[k] = None if v is None or not math.isfinite(v) else round(float(v), 3)
        return d


# ============================================================================== detection
def detect_tanks(img: np.ndarray, valid: np.ndarray, transform: GeoTransform, *,
                 rel_threshold: float = 0.3, min_d_m: float = MIN_D_M, max_d_m: float = MAX_D_M,
                 min_roundness: float = 0.6, background_px: int = 31,
                 bbox: tuple[float, float, float, float] | None = None,
                 cluster_m: float = 250.0, min_neighbours: int = 2
                 ) -> tuple[list[Tank], dict[str, int]]:
    """Bright round components 40..120 m across, as Tanks, plus the rejection counts by reason.

    A TANK FARM IS A CLUSTER: a round bright blob with fewer than `min_neighbours` other
    detections within `cluster_m` is a roof, a pad or a field patch, not a hub tank, and is
    rejected as `isolated` (declared rule, counted)."""
    a = np.where(valid, img, np.nan)
    fill_val = float(np.nanmedian(a)) if np.isfinite(a).any() else 0.0
    a0 = np.where(np.isfinite(a), a, fill_val)
    bg = ndimage.median_filter(a0, size=background_px, mode="nearest")
    rel = (a0 - bg) / np.where(bg > 1e-6, bg, 1e-6)
    binary = (rel > rel_threshold) & valid
    labels, n = ndimage.label(binary)
    reasons = {"candidates": int(n), "too_small": 0, "too_large": 0, "not_round": 0,
               "outside_bbox": 0, "kept": 0}
    out: list[Tank] = []
    min_a = math.pi * (min_d_m / 2 / transform.dx) ** 2 * 0.5
    max_a = math.pi * (max_d_m / 2 / transform.dx) ** 2 * 1.6
    for idx, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        mask = labels[sl] == idx
        area = int(mask.sum())
        if area < min_a:
            reasons["too_small"] += 1
            continue
        if area > max_a:
            reasons["too_large"] += 1
            continue
        rr, cc = np.nonzero(mask)
        cy, cx = rr.mean() + sl[0].start, cc.mean() + sl[1].start
        # roundness: minor/major axis ratio of the second moments, times compactness
        cov = np.cov(np.vstack([rr, cc])) if area > 2 else np.eye(2)
        ev = np.sort(np.linalg.eigvalsh(cov))
        axis_ratio = float(math.sqrt(max(ev[0], 1e-9) / max(ev[1], 1e-9)))
        rmax = float(np.sqrt((rr + sl[0].start - cy) ** 2 + (cc + sl[1].start - cx) ** 2).max())
        compact = area / (math.pi * (rmax + 0.5) ** 2)
        roundness = axis_ratio * min(1.0, compact / 0.7)
        if roundness < min_roundness:
            reasons["not_round"] += 1
            continue
        # refine centre and radius by fractional area over a window around the component
        r_guess = math.sqrt(area / math.pi)
        w = math.ceil(r_guess + 4)
        y0, y1 = max(int(cy) - w, 0), min(int(cy) + w + 1, a0.shape[0])
        x0, x1 = max(int(cx) - w, 0), min(int(cx) + w + 1, a0.shape[1])
        win, bgw = a0[y0:y1, x0:x1], bg[y0:y1, x0:x1]
        lab_w = labels[y0:y1, x0:x1]
        roof = float(np.percentile(win[lab_w == idx], 75))
        bgl = float(np.median(bgw))
        if roof - bgl <= 0:
            reasons["not_round"] += 1
            continue
        frac = np.clip((win - bgl) / (roof - bgl), 0.0, 1.0)
        frac[(lab_w != idx) & (lab_w != 0)] = 0.0   # a neighbouring tank is not this one's area
        yy, xx = np.mgrid[y0:y1, x0:x1]
        near = (yy - cy) ** 2 + (xx - cx) ** 2 <= (r_guess + 1.5) ** 2
        f = frac * near
        if f.sum() <= 0:
            reasons["not_round"] += 1
            continue
        cy2, cx2 = float((f * yy).sum() / f.sum()), float((f * xx).sum() / f.sum())
        r_px = math.sqrt(float(f.sum()) / math.pi)
        d_m = 2 * r_px * transform.dx
        if d_m < min_d_m:
            reasons["too_small"] += 1
            continue
        if d_m > max_d_m:
            reasons["too_large"] += 1
            continue
        x, y = transform.to_map(cx2 + 0.5, cy2 + 0.5)
        if bbox is not None and not (bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]):
            reasons["outside_bbox"] += 1
            continue
        out.append(Tank(tank_id="", x=x, y=y, radius_m=r_px * transform.dx,
                        contrast=float(np.median(rel[labels == idx])), roundness=roundness,
                        method="bright_component+fractional_area"))
    if cluster_m > 0 and min_neighbours > 0:
        xy = np.array([[t.x, t.y] for t in out]) if out else np.zeros((0, 2))
        keep: list[Tank] = []
        for t in out:
            d = np.hypot(xy[:, 0] - t.x, xy[:, 1] - t.y)
            if int(((d > 0) & (d <= cluster_m)).sum()) >= min_neighbours:
                keep.append(t)
            else:
                reasons["isolated"] = reasons.get("isolated", 0) + 1
        out = keep
    out.sort(key=lambda t: (-t.y, t.x))
    out = [Tank(**{**asdict(t), "tank_id": f"T{i + 1:03d}"}) for i, t in enumerate(out)]
    reasons["kept"] = len(out)
    return out, reasons


# ============================================================================== measurement
def _weights(shape: tuple[int, int], cx: float, cy: float, r_in: float, r_out: float | None = None
             ) -> np.ndarray:
    """Fraction of each pixel whose area lies within radius r_in (and beyond r_out if given),
    by SUBSAMPLE x SUBSAMPLE point sampling; pixel (i, j) spans [j, j+1) x [i, i+1)."""
    h, w = shape
    s = (np.arange(SUBSAMPLE) + 0.5) / SUBSAMPLE
    yy = np.arange(h)[:, None, None, None] + s[None, None, :, None]
    xx = np.arange(w)[None, :, None, None] + s[None, None, None, :]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    inside = (d2 <= r_in ** 2) if r_out is None else (d2 > r_in ** 2) & (d2 <= r_out ** 2)
    return np.asarray(inside.mean(axis=(2, 3)), dtype=float)


def sun_unit(azimuth_deg: float) -> tuple[float, float]:
    """Unit vector TOWARD the sun in image coordinates (col right, row DOWN)."""
    az = math.radians(azimuth_deg)
    return math.sin(az), -math.cos(az)


def measure_tank(img: np.ndarray, valid: np.ndarray, transform: GeoTransform, tank: Tank, *,
                 sun_azimuth: float, sun_elevation: float,
                 others: Sequence[Tank] = (), wall_h_m: float = WALL_H_M,
                 roof_valid: np.ndarray | None = None,
                 shadow_depth: float = SHADOW_DEPTH) -> dict[str, Any]:
    """One tank in one scene: ring-normalised roof halves, shadow contrast, fill and its sigma."""
    col, row = transform.to_pixel(tank.x, tank.y)
    r = tank.radius_m / transform.dx
    pad = math.ceil(r + RING_OUT + 2)
    c0, r0 = math.floor(col) - pad, math.floor(row) - pad
    h, w = img.shape
    out: dict[str, Any] = {"tank_id": tank.tank_id, "radius_m": round(tank.radius_m, 2)}
    if c0 < 0 or r0 < 0 or c0 + 2 * pad + 1 > w or r0 + 2 * pad + 1 > h:
        return {**out, "status": "REFUSED", "why": "tank window leaves the scene window"}
    win = img[r0:r0 + 2 * pad + 1, c0:c0 + 2 * pad + 1].astype(float)
    ok = valid[r0:r0 + 2 * pad + 1, c0:c0 + 2 * pad + 1]
    # the roof is judged on its own mask when one is given (a bright roof reads as cloud to SCL)
    rok = ok if roof_valid is None else roof_valid[r0:r0 + 2 * pad + 1, c0:c0 + 2 * pad + 1]
    cx, cy = col - c0, row - r0
    roof_r = max(r - ROOF_INSET, 0.75)
    disk = _weights(win.shape, cx, cy, roof_r)
    ring = _weights(win.shape, cx, cy, r + RING_IN, r + RING_OUT)
    for o in others:   # a neighbour's roof and rim are not this tank's ground
        if o.tank_id == tank.tank_id:
            continue
        oc, orr = transform.to_pixel(o.x, o.y)
        ro = o.radius_m / transform.dx
        if abs(oc - col) > pad + ro + 2 or abs(orr - row) > pad + ro + 2:
            continue
        ring = ring * (1.0 - _weights(win.shape, oc - c0, orr - r0, ro + 1.5))
    ux, uy = sun_unit(sun_azimuth)
    yy, xx = np.mgrid[0:win.shape[0], 0:win.shape[1]]
    proj = (xx + 0.5 - cx) * ux + (yy + 0.5 - cy) * uy
    sun_half = disk * (proj > 0)
    anti_half = disk * (proj < 0)
    masked = 1.0 - float((disk * rok).sum() / max(disk.sum(), 1e-9))
    ring_masked = 1.0 - float((ring * ok).sum() / max(ring.sum(), 1e-9))
    if masked > MAX_MASKED or ring_masked > MAX_MASKED:
        return {**out, "status": "REFUSED", "masked_roof": round(masked, 3),
                "masked_ring": round(ring_masked, 3), "why": "cloud/defect mask over the tank"}
    okf = ok.astype(float)
    rokf = rok.astype(float)
    ring_vals = win[(ring * okf) > 0.5]
    if ring_vals.size < 8:
        return {**out, "status": "REFUSED", "why": f"ground ring has {ring_vals.size} pixels"}
    ring_med = float(np.median(ring_vals))
    sigma = 1.4826 * float(np.median(np.abs(ring_vals - ring_med)))
    if ring_med <= 0:
        return {**out, "status": "REFUSED", "why": "ground ring is not positive"}

    def wmean(wt: np.ndarray) -> tuple[float, float]:
        wt = wt * rokf
        s = float(wt.sum())
        return (float((wt * win).sum() / s), s) if s > 0 else (float("nan"), 0.0)

    m_sun, n_sun = wmean(sun_half)
    m_anti, n_anti = wmean(anti_half)
    m_full, _n_full = wmean(disk)
    b_sun, b_anti, b_full = m_sun / ring_med, m_anti / ring_med, m_full / ring_med
    if not (n_sun > 0 and n_anti > 0) or not b_anti > 0:
        return {**out, "status": "REFUSED", "why": "an empty roof half"}
    c = 1.0 - b_sun / b_anti
    # delta method on c = 1 - m_sun/m_anti, independent pixel noise sigma
    s_sun, s_anti = sigma / math.sqrt(n_sun), sigma / math.sqrt(n_anti)
    sc = math.sqrt((s_sun / m_anti) ** 2 + (m_sun * s_anti / m_anti ** 2) ** 2) if m_anti > 0 \
        else float("nan")
    el = max(min(sun_elevation, 89.0), 5.0)
    k = math.pi * tank.radius_m * math.tan(math.radians(el)) / (4.0 * shadow_depth * wall_h_m)
    emptiness = c * k
    fill = 1.0 - emptiness
    return {**out, "status": "MEASURED", "b_sun_half": round(b_sun, 5),
            "b_anti_half": round(b_anti, 5), "b_full_disk": round(b_full, 5),
            "ring_median": round(ring_med, 5), "pixel_sigma": round(sigma, 5),
            "n_sun_px": round(n_sun, 2), "n_anti_px": round(n_anti, 2),
            "shadow_contrast": round(c, 5), "shadow_contrast_sigma": round(sc, 5),
            "fill_index": round(fill, 4), "fill_sigma": round(abs(k) * sc, 4),
            "masked_roof": round(masked, 3), "masked_ring": round(ring_masked, 3)}


def hub_index(rows: Sequence[Mapping[str, Any]], trim: float = 0.1) -> dict[str, Any]:
    """Hub-level aggregate over MEASURED tanks: count, mean, robust mean, dispersion, and the
    capacity-weighted (r^2) mean -- a big tank holds more oil than a small one."""
    m = [r for r in rows if r.get("status") == "MEASURED" and r.get("fill_index") is not None
         and math.isfinite(float(r["fill_index"]))]
    if not m:
        return {"n_tanks": 0, "status": "UNMEASURED", "why": "no tank measured in this scene"}
    f = np.array([float(r["fill_index"]) for r in m])
    s = np.array([float(r.get("fill_sigma") or 0.0) for r in m])
    w = np.array([float(r["radius_m"]) ** 2 for r in m])
    lo, hi = np.quantile(f, [trim, 1 - trim])
    tm = f[(f >= lo) & (f <= hi)]
    med = float(np.median(f))
    return {"status": "MEASURED", "n_tanks": len(m),
            "fill_mean": round(float(f.mean()), 4),
            "fill_trimmed_mean": round(float(tm.mean()), 4) if tm.size else None,
            "fill_median": round(med, 4),
            "fill_capacity_weighted": round(float((w * f).sum() / w.sum()), 4),
            "fill_dispersion_mad": round(1.4826 * float(np.median(np.abs(f - med))), 4),
            "fill_mean_sigma": round(float(math.sqrt((s ** 2).sum()) / len(m)), 4),
            "b_sun_half_mean": round(float(np.mean([float(r["b_sun_half"]) for r in m])), 5),
            "b_full_disk_mean": round(float(np.mean([float(r["b_full_disk"]) for r in m])), 5)}


__all__ = [
    "MAX_MASKED",
    "SHADOW_DEPTH",
    "WALL_H_M",
    "Tank",
    "detect_tanks",
    "hub_index",
    "measure_tank",
    "sun_unit",
]
