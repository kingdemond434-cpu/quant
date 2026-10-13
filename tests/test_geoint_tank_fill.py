"""The GEOINT tank-fill factory on synthetic rasters: what it must recover and what it must refuse.

Every scene here is RENDERED from the physics the estimator claims to read -- a floating roof at
1 m resolution, the sun-side wall's shadow on it of length H(1 - fill)/tan(el), block-averaged to
10 m pixels -- so a pass means the estimator inverts the mechanism, not that it fits a fixture.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from libs.geoint import cog as cogmod
from libs.geoint import sensor_bridge as bridge
from libs.geoint import sentinel2 as s2
from libs.geoint import tanks as tk
from libs.geoint.cog import GeoTransform
from libs.research import ceiling as ceil

ROOT = Path(__file__).resolve().parents[1]
SUN_AZ, SUN_EL = 150.0, 35.0
GROUND, ROOF = 0.25, 0.55


def render(tanks: list[tuple[float, float, float, float]], *, size_px: int = 60,
           az: float = SUN_AZ, el: float = SUN_EL, gain: float = 1.0, noise: float = 0.0,
           seed: int = 0) -> tuple[np.ndarray, GeoTransform]:
    """A 10 m scene of `size_px` square holding tanks (cx_m, cy_m, radius_m, fill) in metres
    from the top-left corner, rendered at 1 m and block-averaged."""
    n = size_px * 10
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    img = np.full((n, n), GROUND)
    ux, uy = tk.sun_unit(az)
    for cx, cy, r, fill in tanks:
        inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r ** 2
        length = tk.WALL_H_M * (1 - fill) / math.tan(math.radians(el))
        sx, sy = xx + length * ux, yy + length * uy
        shaded = inside & ((sx - cx) ** 2 + (sy - cy) ** 2 > r ** 2)
        img[inside] = ROOF
        img[shaded] = ROOF * (1 - tk.SHADOW_DEPTH)
    small = img.reshape(size_px, 10, size_px, 10).mean(axis=(1, 3)) * gain
    if noise:
        small = small + np.random.default_rng(seed).normal(0, noise, small.shape)
    return small, GeoTransform(x0=500000.0, y0=4000000.0, dx=10.0, dy=10.0)


def tank_at(tr: GeoTransform, cx_m: float, cy_m: float, r: float, tid: str = "T001") -> tk.Tank:
    x, y = tr.to_map(cx_m / 10.0, cy_m / 10.0)
    return tk.Tank(tank_id=tid, x=x, y=y, radius_m=r)


def measure(img: np.ndarray, tr: GeoTransform, tank: tk.Tank, el: float = SUN_EL,
            az: float = SUN_AZ) -> dict:
    return tk.measure_tank(img, np.ones(img.shape, bool), tr, tank, sun_azimuth=az,
                           sun_elevation=el)


# ------------------------------------------------------------------ the COG reader
def test_cog_round_trip_reads_a_window_across_tile_boundaries():
    rng = np.random.default_rng(3)
    arr = rng.integers(0, 12000, size=(700, 600), dtype=np.uint16)
    url = "mem://b08.tif"
    reader = cogmod.COG(url, cogmod.bytes_fetch({url: cogmod.write_cog(arr, 600000, 4000000,
                                                                       10, 10, tile=256)}))
    assert (reader.width, reader.height, reader.tile_w) == (600, 700, 256)
    assert np.array_equal(reader.read_window(200, 250, 150, 300), arr[250:550, 200:350])
    # a window hanging off the raster reads zeros there, the rest exactly
    out = reader.read_window(550, 650, 100, 100)
    assert np.array_equal(out[:50, :50], arr[650:700, 550:600]) and not out[50:, :].any()
    win, tr = reader.read_bbox(601000.0, 3996000.0, 602000.0, 3997000.0)
    assert win.shape == (100, 100) and (tr.x0, tr.y0) == (601000.0, 3997000.0)
    assert np.array_equal(win, arr[300:400, 100:200])


def test_cog_refuses_bigtiff_rather_than_misreading_it():
    url = "mem://big.tif"
    with pytest.raises(cogmod.CogUnsupported):
        cogmod.COG(url, cogmod.bytes_fetch({url: b"II+\x00" + b"\x00" * 64}))


def test_utm_forward_and_inverse_agree_inside_a_metre():
    e, n, z = s2.lonlat_to_utm(-96.767, 35.985)
    assert z == 14 and 700_000 < e < 703_000 and 3_983_000 < n < 3_986_000
    lon, lat = s2.utm_to_lonlat(e, n, 14)
    assert abs(lon + 96.767) < 1e-6 and abs(lat - 35.985) < 1e-6


def test_s3_listing_parse_reads_prefixes_and_objects():
    xml = (b'<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/'
           b'2006-03-01/"><IsTruncated>false</IsTruncated><Contents><Key>a/S2A_14SPE_20240702_0_'
           b'L2A/S2A_14SPE_20240702_0_L2A.json</Key><LastModified>2024-07-03T03:21:39.000Z'
           b'</LastModified><Size>9</Size></Contents><CommonPrefixes><Prefix>sentinel-s2-l2a-'
           b'cogs/14/S/PE/2024/7/S2A_14SPE_20240702_0_L2A/</Prefix></CommonPrefixes>'
           b'</ListBucketResult>')
    scenes = s2.search("14SPE", [(2024, 7)], get=lambda url: xml)
    assert [s.scene_id for s in scenes] == ["S2A_14SPE_20240702_0_L2A"]
    _, objs = s2.list_objects("x", get=lambda url: xml)
    assert objs[0]["last_modified"] == "2024-07-03T03:21:39.000Z"


def test_dn_offset_follows_the_processing_baseline():
    assert s2.Scene("s", "t", "p", processing_baseline="05.10",
                    boa_offset_applied=False).dn_offset == -1000.0
    assert s2.Scene("s", "t", "p", processing_baseline="05.10",
                    boa_offset_applied=True).dn_offset == 0.0
    assert s2.Scene("s", "t", "p", processing_baseline="02.14").dn_offset == 0.0


# ------------------------------------------------------------------ the estimator
def test_a_planted_tank_whose_fill_changes_is_recovered():
    tr = render([(300, 300, 30, 0.9)])[1]
    t = tank_at(tr, 300, 300, 30)
    fills = {}
    for f in (0.2, 0.5, 0.9):
        img, _ = render([(300, 300, 30, f)])
        fills[f] = measure(img, tr, t)["fill_index"]
    assert fills[0.2] < fills[0.5] < fills[0.9]
    # the geometric inversion recovers the change to within a third of its size at 10 m
    assert abs((fills[0.9] - fills[0.2]) - 0.7) < 0.25


def test_a_global_gain_change_alone_moves_no_fill():
    tr = render([(300, 300, 30, 0.4)])[1]
    t = tank_at(tr, 300, 300, 30)
    base, _ = render([(300, 300, 30, 0.4)])
    dark, _ = render([(300, 300, 30, 0.4)], gain=0.7)
    a, b = measure(base, tr, t), measure(dark, tr, t)
    # the raw roof brightness moved by 30%: the owner's ~0 before/after difference, inverted
    assert abs(float(dark[30, 30]) - float(base[30, 30])) > 0.05
    assert a["fill_index"] == pytest.approx(b["fill_index"], abs=1e-9)
    assert a["b_sun_half"] == pytest.approx(b["b_sun_half"], abs=1e-9)


def test_the_shadow_side_half_beats_the_full_disk_on_snr():
    """Same pixel noise, same fill change: the sun-side half separates the two states by more
    standard deviations than the whole disk does."""
    tr = render([(300, 300, 30, 0.9)])[1]
    t = tank_at(tr, 300, 300, 30)
    half = {0.3: [], 0.8: []}
    full = {0.3: [], 0.8: []}
    for f in (0.3, 0.8):
        for seed in range(60):
            img, _ = render([(300, 300, 30, f)], noise=0.02, seed=seed + int(f * 1000))
            m = measure(img, tr, t)
            half[f].append(m["b_sun_half"])
            full[f].append(m["b_full_disk"])

    def snr(d: dict) -> float:
        a, b = np.array(d[0.3]), np.array(d[0.8])
        return abs(b.mean() - a.mean()) / math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)

    assert snr(half) > 1.3 * snr(full)


def test_sun_geometry_correction_makes_fill_independent_of_sun_elevation():
    tr = render([(300, 300, 30, 0.5)])[1]
    t = tank_at(tr, 300, 300, 30)
    lo = measure(render([(300, 300, 30, 0.5)], el=30.0)[0], tr, t, el=30.0)["fill_index"]
    hi = measure(render([(300, 300, 30, 0.5)], el=55.0)[0], tr, t, el=55.0)["fill_index"]
    raw_lo = measure(render([(300, 300, 30, 0.5)], el=30.0)[0], tr, t, el=30.0)
    raw_hi = measure(render([(300, 300, 30, 0.5)], el=55.0)[0], tr, t, el=55.0)
    assert raw_lo["shadow_contrast"] > 1.5 * raw_hi["shadow_contrast"]
    assert abs(lo - hi) < 0.2


def test_a_cloud_masked_tank_is_refused_by_name():
    img, tr = render([(300, 300, 30, 0.5)])
    valid = np.ones(img.shape, bool)
    valid[27:34, 27:34] = False
    m = tk.measure_tank(img, valid, tr, tank_at(tr, 300, 300, 30), sun_azimuth=SUN_AZ,
                        sun_elevation=SUN_EL)
    assert m["status"] == "REFUSED" and "mask" in m["why"]


def test_detection_finds_a_planted_tank_farm_and_ignores_a_lone_blob():
    spots = [(150 + 120 * i, 150 + 120 * j, 28 + 3 * ((i + j) % 3), 0.95)
             for i in range(3) for j in range(3)]
    img, tr = render([*spots, (1050, 1050, 30, 0.95)], size_px=120, el=70.0)
    found, why = tk.detect_tanks(img, np.ones(img.shape, bool), tr)
    assert len(found) == 9 and why.get("isolated", 0) == 1
    for cx, cy, r, _ in spots:
        x, y = tr.to_map(cx / 10, cy / 10)
        best = min(found, key=lambda t: math.hypot(t.x - x, t.y - y))
        assert math.hypot(best.x - x, best.y - y) < 4.0
        assert abs(best.radius_m - r) / r < 0.15
    hub = tk.hub_index([measure(img, tr, t, el=70.0) for t in found])
    assert hub["n_tanks"] == 9 and hub["status"] == "MEASURED"


# ------------------------------------------------------------------ PIT
def test_no_value_is_knowable_before_acquisition_plus_latency():
    from desks.mt5.research import geoint_tank_fill as g
    acq = datetime(2024, 7, 2, 17, 24, tzinfo=UTC)
    gen = acq + timedelta(hours=7)
    printed = g.pit_stamp(acq, gen, gen + timedelta(hours=3))
    assert s2.parse_time(printed["knowable_at"]) == gen + timedelta(hours=g.DIST_LAG_H)
    assert printed["mirror_lag_h"] == 3 and printed["mirror_live"] is True
    # a mirror that re-uploaded the archive years later is recorded, never the world clock
    late = g.pit_stamp(acq, gen, acq + timedelta(days=900))
    assert late["mirror_live"] is False and late["knowable_at"] == printed["knowable_at"]
    for bad in (None, acq - timedelta(hours=1)):
        d = g.pit_stamp(acq, bad, None)
        assert d["knowable_basis"] == "declared_lag" and d["mirror_lag_h"] == "UNMEASURED"
        assert s2.parse_time(d["knowable_at"]) == acq + timedelta(hours=g.DECLARED_LATENCY_H)
    store = {"a": {"scene_id": "a", "registry": "R", "status": "MEASURED", "acquired":
                   acq.isoformat(), "received_at": "x", **printed,
                   "hub": {"fill_capacity_weighted": 0.5, "n_tanks": 3}}}
    ser = g.hub_series(store, "R")
    assert s2.parse_time(ser[0]["knowable_at"]) > s2.parse_time(ser[0]["event_time"])
    row = bridge.observation_row(entity="hub", metric="m", value=0.5,
                                 event_time=ser[0]["event_time"],
                                 knowable_at=ser[0]["knowable_at"],
                                 knowable_basis=ser[0]["knowable_basis"],
                                 received_at=(acq + timedelta(hours=11)).isoformat(),
                                 uncertainty=0.01, raw_pointer="p")
    assert row["knowable_at"] >= row["event_time"] and row["authority"] == "NONE"


def test_the_disagreement_slope_uses_only_released_weeks():
    from desks.mt5.research import geoint_tank_fill as g
    pairs = [{"week_end": f"2024-0{m}-0{d}", "fill": 0.1 * k, "eia_kbbl": 1000.0 * k}
             for k, (m, d) in enumerate([(1, 5), (2, 2), (3, 1), (4, 5), (5, 3), (6, 7),
                                         (7, 5), (8, 2), (9, 6)])]
    early = datetime(2024, 3, 1, tzinfo=UTC)
    assert g._slope_before(pairs, early) is None          # 2 weeks released: no slope
    late = datetime(2024, 10, 1, tzinfo=UTC)
    assert g._slope_before(pairs, late) == pytest.approx(10000.0)


# ------------------------------------------------------------------ terms and cells
class _Engines:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def write_lake_series(self, series_id, rows):
        self.calls.append("lake")
        return {"status": "WRITTEN", "rows": len(rows)}

    def emit_conditioner_cells(self, series_id, signals, symbols, **kw):
        self.calls.append(f"cells:{kw.get('data_source')}")
        return {"emitted": len(signals) * len(symbols), "created": 0}


def _with_organs(monkeypatch, terms_ok: bool | None, engines: _Engines) -> None:
    def organ(name):
        if name == "libs.data.terms_hold":
            return None if terms_ok is None else SimpleNamespace(
                gauntlet_terms=lambda sid: (terms_ok, "" if terms_ok else "HELD_TERMS: test"))
        if name == "libs.research.sensor_engines":
            return engines
        return None
    monkeypatch.setattr(bridge, "_organ", organ)


@pytest.mark.parametrize("terms_ok", [False, None])
def test_held_terms_emit_no_cell(monkeypatch, terms_ok):
    eng = _Engines()
    _with_organs(monkeypatch, terms_ok, eng)
    res = bridge.emit_cells("s", [{"available_time": "2024-01-01T00:00:00Z"}], ["fill_level"],
                            ["XTIUSD"], judge=True, judge_why="", mechanism="m", falsifier="f")
    assert res["status"] == "HELD_TERMS" and res["emitted"] == 0 and eng.calls == []


def test_cleared_terms_still_wait_for_the_ceiling_then_emit(monkeypatch):
    eng = _Engines()
    _with_organs(monkeypatch, True, eng)
    held = bridge.emit_cells("s", [], ["fill_level"], ["XTIUSD"], judge=False,
                             judge_why="UNMEASURED", mechanism="m", falsifier="f")
    assert held["status"] == "WITHHELD_CEILING" and eng.calls == []
    ok = bridge.emit_cells("s", [{"available_time": "2024-01-01T00:00:00Z", "fill_level": 0.5}],
                           ["fill_level", "fill_change"], ["XTIUSD"], judge=True,
                           judge_why="GAIN", mechanism="m", falsifier="f")
    assert ok["emitted"] == 2 and eng.calls == ["lake", f"cells:{bridge.DATA_SOURCE}"]


def test_the_sentinel_clearance_carries_a_url_and_a_verbatim_quote():
    doc = json.loads((ROOT / "desks/mt5/data/terms_clearances.json").read_text("utf-8"))
    row = doc["geoint:sentinel2_l2a"]
    assert row["status"] == "CLEARED" and row["terms_url"].startswith("https://")
    assert row["terms_quote"].startswith("Access to Sentinel data is free, full and open")
    assert "owed" in row      # the Copernicus legal notice itself is still owed a read


# ------------------------------------------------------------------ the ceiling
def _ceiling_world(lead_effect: float, n: int = 160, seed: int = 5):
    rng = np.random.default_rng(seed)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    times = [start + timedelta(hours=h) for h in range(n * 7 * 24 + 24 * 10)]
    rets = rng.normal(0, 0.002, len(times))
    state = []
    for i in range(n):
        rel = start + timedelta(days=7 * i + 8, hours=15)
        s = float(rng.normal())
        state.append((rel, s))
        # the state moves the price over the three days before its release
        k = int((rel - start).total_seconds() // 3600)
        rets[k - 72:k] += lead_effect * s / 72
    closes = 70 * np.exp(np.cumsum(rets))
    return state, times, closes


def test_ceiling_reads_gain_on_a_planted_lead_and_no_gain_on_noise():
    state, times, closes = _ceiling_world(0.02)
    hit = ceil.ceiling_test(state, times, closes, n_null=300)
    assert hit["verdict"] == ceil.GAIN and hit["n"] >= ceil.MIN_N
    assert ceil.decision(hit)["judge_cells"] is True
    # an independent world (its own seed: at alpha = 0.05 one noise world in twenty reads GAIN,
    # which is the test's size, measured 2/40 over seeds 10..49)
    state, times, closes = _ceiling_world(0.0, seed=6)
    miss = ceil.ceiling_test(state, times, closes, n_null=300)
    assert miss["verdict"] == ceil.NO_GAIN and ceil.decision(miss)["judge_cells"] is False


def test_ceiling_below_its_sample_is_unmeasured_never_a_pass():
    state, times, closes = _ceiling_world(0.02, n=20)
    res = ceil.ceiling_test(state, times, closes, n_null=100)
    assert res["verdict"] == ceil.UNMEASURED and ceil.decision(res)["judge_cells"] is False


def test_a_white_roof_classed_as_cloud_is_measured_when_its_ground_is_clear():
    """SCL reads a white floating roof as cloud (measured on 14SPE 2020-10-06: 256 of 280 tank
    centres in class 9). The roof is judged on its own mask; a real cloud covers the ring too."""
    img, tr = render([(300, 300, 30, 0.5)])
    t = tank_at(tr, 300, 300, 30)
    ground = np.ones(img.shape, bool)
    ground[27:34, 27:34] = False                     # SCL cloud on the roof only
    roof = np.ones(img.shape, bool)
    m = tk.measure_tank(img, ground, tr, t, sun_azimuth=SUN_AZ, sun_elevation=SUN_EL,
                        roof_valid=roof)
    assert m["status"] == "MEASURED"
    assert m["fill_index"] == pytest.approx(measure(img, tr, t)["fill_index"], abs=1e-9)
    cloud = np.ones(img.shape, bool)
    cloud[20:41, 20:41] = False                      # a real cloud: roof AND ring
    m2 = tk.measure_tank(img, cloud, tr, t, sun_azimuth=SUN_AZ, sun_elevation=SUN_EL,
                         roof_valid=roof)
    assert m2["status"] == "REFUSED"
