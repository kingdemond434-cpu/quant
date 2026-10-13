"""SENTINEL-2 L2A ON THE AWS OPEN-DATA BUCKET: scene search, metadata, cloud mask, window reads.

THE SOURCE. ``s3://sentinel-cogs/sentinel-s2-l2a-cogs/<zone>/<band>/<square>/<yyyy>/<m>/
<SAT>_<TILE>_<yyyymmdd>_<seq>_L2A/`` holds one Sentinel-2 L2A granule as Cloud-Optimised GeoTIFFs
(B01..B12, SCL, TCI, ...) beside a STAC item JSON. The bucket answers anonymous S3
ListObjectsV2 over HTTPS (measured from the cloud container 2026-10-13, where the STAC API,
Copernicus, NASA and USGS all refuse), so scene search is a prefix listing, not an API query.

WHAT A SCENE CARRIES THAT THE FACTORY NEEDS, and where each comes from:

  acquisition time    STAC ``properties.datetime`` (the granule's sensing time, UTC)
  sun geometry        ``view:sun_azimuth`` / ``view:sun_elevation`` (degrees; azimuth clockwise
                      from north) -- the shadow of a tank wall falls on the roof on the side
                      TOWARD the sun (the wall nearest the sun casts it), see ``tanks.py``
  processing baseline ``s2:processing_baseline`` and ``earthsearch:boa_offset_applied``: from
                      baseline 04.00 the L2A DN carry a +1000 offset; reflectance is
                      (DN - 1000)/10000 unless the publisher already removed it
  publication instant the S3 ``LastModified`` of the item JSON, the last object written for the
                      granule -- MEASURED per scene, never assumed (``knowable_at``)
  cloud mask          the SCL band (20 m): 3 cloud shadow, 8/9 cloud, 10 cirrus, 11 snow are
                      refused; 0 no-data and 1 saturated/defective too

UTM is computed here (Krueger series, WGS84) because no projection library is installed; the
error is well under a metre inside a zone, two orders below a 10 m pixel.
"""
from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from libs.geoint.cog import COG, Fetch, GeoTransform, http_fetch

BUCKET_URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
PREFIX = "sentinel-s2-l2a-cogs"
#: SCL classes refused as unobserved ground (ESA L2A Scene Classification legend).
SCL_BAD = frozenset({0, 1, 3, 8, 9, 10, 11})
SCL_NAMES = {0: "no_data", 1: "saturated_defective", 2: "dark_area", 3: "cloud_shadow",
             4: "vegetation", 5: "not_vegetated", 6: "water", 7: "unclassified",
             8: "cloud_medium", 9: "cloud_high", 10: "thin_cirrus", 11: "snow"}
_SCENE_RE = re.compile(r"(S2[ABC])_(\d{1,2}[C-X][A-Z]{2})_(\d{8})_(\d+)_L2A")

Getter = Callable[[str], bytes]


def http_get(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-geoint/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return bytes(resp.read())


# ============================================================================== UTM
_A = 6378137.0
_F = 1 / 298.257223563
_K0 = 0.9996


def utm_zone(lon: float) -> int:
    return int((lon + 180.0) // 6.0) + 1


def lonlat_to_utm(lon: float, lat: float, zone: int | None = None) -> tuple[float, float, int]:
    """(easting, northing, zone) on WGS84 UTM, northern hemisphere convention for lat >= 0."""
    z = zone or utm_zone(lon)
    lon0 = math.radians((z - 1) * 6 - 180 + 3)
    n = _F / (2 - _F)
    a_ = _A / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    alpha = (n / 2 - 2 * n * n / 3 + 5 * n ** 3 / 16,
             13 * n * n / 48 - 3 * n ** 3 / 5,
             61 * n ** 3 / 240)
    phi, lam = math.radians(lat), math.radians(lon) - lon0
    t = math.sinh(math.atanh(math.sin(phi))
                  - 2 * math.sqrt(n) / (1 + n) * math.atanh(2 * math.sqrt(n) / (1 + n)
                                                            * math.sin(phi)))
    xi = math.atan2(t, math.cos(lam))
    eta = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    e = eta + sum(alpha[j - 1] * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                  for j in (1, 2, 3))
    nn = xi + sum(alpha[j - 1] * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                  for j in (1, 2, 3))
    easting = 500000.0 + _K0 * a_ * e
    northing = _K0 * a_ * nn + (0.0 if lat >= 0 else 10_000_000.0)
    return easting, northing, z


def utm_to_lonlat(easting: float, northing: float, zone: int) -> tuple[float, float]:
    """Inverse of `lonlat_to_utm` (northern hemisphere), by Newton on the forward map."""
    lon0 = (zone - 1) * 6 - 180 + 3
    lon, lat = lon0 + (easting - 500000.0) / 90000.0, northing / 111000.0
    for _ in range(8):
        e0, n0, _z = lonlat_to_utm(lon, lat, zone)
        e1, n1, _z = lonlat_to_utm(lon + 1e-5, lat, zone)
        e2, n2, _z = lonlat_to_utm(lon, lat + 1e-5, zone)
        j = np.array([[(e1 - e0) / 1e-5, (e2 - e0) / 1e-5], [(n1 - n0) / 1e-5, (n2 - n0) / 1e-5]])
        d = np.linalg.solve(j, np.array([easting - e0, northing - n0]))
        lon, lat = lon + float(d[0]), lat + float(d[1])
        if abs(d[0]) < 1e-10 and abs(d[1]) < 1e-10:
            break
    return lon, lat


# ============================================================================== scenes
@dataclass(frozen=True)
class Scene:
    scene_id: str
    tile: str
    prefix: str
    acquired: str = ""
    item_last_modified: str = ""
    cloud_cover: float | None = None
    sun_azimuth: float | None = None
    sun_elevation: float | None = None
    processing_baseline: str = ""
    boa_offset_applied: bool | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def url(self, asset: str) -> str:
        return f"{BUCKET_URL}/{self.prefix}{asset}"

    @property
    def dn_offset(self) -> float:
        """The DN offset to ADD before /10000: -1000 from baseline 04.00 unless already removed."""
        try:
            pb = float(self.processing_baseline or 0)
        except ValueError:
            pb = 0.0
        if pb >= 4.0 and self.boa_offset_applied is not True:
            return -1000.0
        return 0.0


def tile_prefix(tile: str) -> str:
    m = re.fullmatch(r"(\d{1,2})([C-X])([A-Z]{2})", tile.upper())
    if not m:
        raise ValueError(f"not an MGRS tile id: {tile!r}")
    return f"{PREFIX}/{int(m.group(1))}/{m.group(2)}/{m.group(3)}/"


def list_objects(prefix: str, get: Getter | None = None, delimiter: str = "/"
                 ) -> tuple[list[str], list[dict[str, str]]]:
    """(common prefixes, [{key, last_modified, size}]) for one S3 prefix, all pages."""
    g = get or http_get
    prefixes: list[str] = []
    objects: list[dict[str, str]] = []
    token = ""
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        raw = g(f"{BUCKET_URL}/?{urllib.parse.urlencode(q)}")
        root = ET.fromstring(raw)
        ns = {"s": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
        p = "s:" if ns else ""
        prefixes += [e.text or "" for e in root.findall(f"{p}CommonPrefixes/{p}Prefix", ns)]
        for c in root.findall(f"{p}Contents", ns):
            objects.append({"key": c.findtext(f"{p}Key", "", ns),
                            "last_modified": c.findtext(f"{p}LastModified", "", ns),
                            "size": c.findtext(f"{p}Size", "", ns)})
        if root.findtext(f"{p}IsTruncated", "false", ns) != "true":
            break
        token = root.findtext(f"{p}NextContinuationToken", "", ns)
        if not token:
            break
    return prefixes, objects


def search(tile: str, months: Iterable[tuple[int, int]], get: Getter | None = None
           ) -> list[Scene]:
    """Every granule of `tile` acquired in the given (year, month)s, by prefix listing."""
    base = tile_prefix(tile)
    out: list[Scene] = []
    for y, m in months:
        prefixes, _ = list_objects(f"{base}{y}/{m}/", get)
        for p in prefixes:
            mm = _SCENE_RE.search(p)
            if mm and mm.group(2).upper() == tile.upper():
                out.append(Scene(scene_id=mm.group(0), tile=tile.upper(), prefix=p))
    return sorted(out, key=lambda s: (s.scene_id.split("_")[2], s.scene_id))


def load_metadata(scene: Scene, get: Getter | None = None) -> Scene:
    """The scene with its STAC properties and the item JSON's S3 LastModified filled in."""
    g = get or http_get
    _, objs = list_objects(scene.prefix, g, delimiter="")
    item_key = f"{scene.prefix}{scene.scene_id}.json"
    lm = next((o["last_modified"] for o in objs if o["key"] == item_key), "")
    doc = json.loads(g(scene.url(f"{scene.scene_id}.json")))
    props = dict(doc.get("properties") or {})

    def num(k: str) -> float | None:
        v = props.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    return Scene(scene_id=scene.scene_id, tile=scene.tile, prefix=scene.prefix,
                 acquired=str(props.get("datetime") or ""), item_last_modified=lm,
                 cloud_cover=num("eo:cloud_cover"), sun_azimuth=num("view:sun_azimuth"),
                 sun_elevation=num("view:sun_elevation"),
                 processing_baseline=str(props.get("s2:processing_baseline") or ""),
                 boa_offset_applied=(props.get("earthsearch:boa_offset_applied")
                                     if isinstance(props.get("earthsearch:boa_offset_applied"),
                                                   bool) else None),
                 properties={k: props[k] for k in (
                     "eo:cloud_cover", "view:sun_azimuth", "view:sun_elevation",
                     "s2:processing_baseline", "s2:generation_time", "created",
                     "earthsearch:boa_offset_applied", "platform") if k in props})


def parse_time(v: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


@dataclass
class Window:
    """One scene's reflectance and valid-pixel mask over a UTM box (10 m grid)."""

    reflectance: np.ndarray
    valid: np.ndarray
    transform: GeoTransform
    scl_counts: dict[str, int]
    bytes_read: int


def read_window(scene: Scene, bbox_utm: tuple[float, float, float, float], band: str = "B08",
                fetch: Fetch | None = None) -> Window:
    """Reflectance of `band` (10 m) and the SCL-derived valid mask over `bbox_utm`."""
    f = fetch or http_fetch
    cog = COG(scene.url(f"{band}.tif"), f)
    dn, tr = cog.read_bbox(*bbox_utm)
    refl = (dn.astype(np.float64) + scene.dn_offset) / 10000.0
    valid = dn > 0
    scl_counts: dict[str, int] = {}
    read = cog.bytes_read
    try:
        scl = COG(scene.url("SCL.tif"), f)
        # the SCL grid is 20 m: read its covering window and upsample by the scale ratio
        sarr, str_ = scl.read_bbox(*bbox_utm)
        read += scl.bytes_read
        ratio = max(1, round(str_.dx / tr.dx))
        up = np.kron(sarr, np.ones((ratio, ratio), dtype=sarr.dtype))
        oc = round((tr.x0 - str_.x0) / tr.dx)
        orow = round((str_.y0 - tr.y0) / tr.dy)
        up = up[orow:orow + dn.shape[0], oc:oc + dn.shape[1]]
        if up.shape == dn.shape:
            valid &= ~np.isin(up, list(SCL_BAD))
            vals, cnts = np.unique(up, return_counts=True)
            scl_counts = {SCL_NAMES.get(int(v), str(int(v))): int(c) for v, c in zip(vals, cnts,
                                                                                     strict=True)}
        else:
            scl_counts = {"UNMEASURED": int(dn.size)}
    except Exception as exc:  # an unreadable mask is recorded, never read as clear
        scl_counts = {"UNMEASURED": int(dn.size), f"error:{type(exc).__name__}": 1}
        valid[:] = False
    return Window(reflectance=refl, valid=valid, transform=tr, scl_counts=scl_counts,
                  bytes_read=read)


__all__ = ["BUCKET_URL", "SCL_BAD", "Scene", "Window", "list_objects", "load_metadata",
           "lonlat_to_utm", "parse_time", "read_window", "search", "tile_prefix",
           "utm_to_lonlat", "utm_zone"]
