"""alt_proxies' paid-replica builds (2026-11-18): Indeed Hiring Lab job postings (the free
replica of LinkUp / Revelio job-postings panels) and Sentinel-2 crop greenness from the scene
classification (the free replica of satellite crop-condition analytics).

Fixtures are SYNTHETIC files shaped like the publishers'; nothing here touches the network.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402
from research import universe_policy  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)


def test_indeed_reads_total_postings_only_and_skips_blanks() -> None:
    obs = A.parse_indeed_postings((FIX / "jobs_indeed_postings.csv").read_bytes(), A.Ctx())
    assert len(obs) == 60 and {o.series for o in obs} == {"us_postings"}
    first = min(obs, key=lambda o: o.period)
    assert first.period == date(2026, 8, 1) and first.value == pytest.approx(100.0)
    assert all(o.published_at is None for o in obs)        # the calendar rule stamps them


def test_indeed_rows_are_available_late_never_early() -> None:
    src = A.BY_ID["jobs_indeed_postings"]
    t = src.rule(date(2026, 11, 13))
    assert t >= datetime(2026, 11, 24, tzinfo=UTC)


def test_s2_item_gives_the_green_share_of_clear_land_and_its_weight() -> None:
    body = (FIX / "sat_s2_crop_green.json").read_bytes()
    (o,) = A.parse_s2_item(body, A.Ctx())
    assert o.series == "scene_15TVG" and o.period == date(2026, 7, 16)
    assert o.value == pytest.approx(70 / 75)
    assert o.published_at == datetime(2026, 7, 16, 23, 22, tzinfo=UTC)
    assert A.s2_weight(body) == pytest.approx(75 * 0.9)
    cloudy = json.loads(body)
    cloudy["properties"].update({"s2:vegetation_percentage": 3.0,
                                 "s2:not_vegetated_percentage": 2.0})
    assert A.parse_s2_item(json.dumps(cloudy).encode(), A.Ctx()) == []


def test_s2_listing_keeps_the_latest_processing_per_scene() -> None:
    pre = "sentinel-s2-l2a-cogs/15/T/VG/2025/7"
    xml = "".join(f"<CommonPrefixes><Prefix>{pre}/{i}/</Prefix></CommonPrefixes>" for i in (
        "S2A_15TVG_20250716_0_L2A", "S2A_15TVG_20250716_1_L2A", "S2B_15TVG_20250709_0_L2A"))
    got = A.s2_list_items(xml.encode())
    assert [i for _, i in got] == ["S2A_15TVG_20250716_1_L2A", "S2B_15TVG_20250709_0_L2A"]
    assert A.s2_list_url("15TVG", 2025, 7).endswith("prefix=sentinel-s2-l2a-cogs/15/T/VG/2025/7/")


def _scenes(values: dict[int, float]) -> dict[str, dict]:
    out = {}
    tiles = A.S2_REGIONS["us_corn_soy"][0]
    for year, v in values.items():
        for t in tiles:
            out[f"{t}|{year}"] = {"tile": t, "d": f"{year}-07-05", "v": v, "w": 50.0,
                                  "created": f"{year}-07-06T01:00:00+00:00"}
    return out


def test_dekads_compose_in_season_and_the_anomaly_uses_prior_years_only() -> None:
    obs = A.s2_dekads(_scenes({2023: 0.90, 2024: 0.80, 2025: 0.70}), NOW)
    by = {(o.series, o.period): o for o in obs}
    lvl = by[("us_corn_soy_green", date(2025, 7, 10))]
    assert lvl.value == pytest.approx(0.70)
    # available when the dekad has closed, never at the scene's own instant before it
    assert lvl.published_at == datetime(2025, 7, 11, tzinfo=UTC)
    anom = by[("us_corn_soy_green_anom", date(2025, 7, 10))]
    assert anom.value == pytest.approx(0.70 - 0.85)
    assert ("us_corn_soy_green_anom", date(2024, 7, 10)) not in by     # one prior year only
    winter = _scenes({2025: 0.5})
    for s in winter.values():
        s["d"] = "2025-01-05"
    assert A.s2_dekads(winter, NOW) == []                              # out of season


def test_a_dekad_waits_until_it_settles_and_needs_half_the_tiles() -> None:
    sc = {t: {"tile": t, "d": "2026-11-17", "v": 0.9, "w": 50.0,
              "created": "2026-11-17T20:00:00+00:00"} for t in A.S2_REGIONS["brazil_soy"][0]}
    assert A.s2_dekads(sc, NOW) == []                                  # dekad ends 11-20
    later = NOW + timedelta(days=A.S2_SETTLE_DAYS + 3)
    assert [o.series for o in A.s2_dekads(sc, later)] == ["brazil_soy_green"]
    one = {k: v for k, v in _scenes({2025: 0.9}).items() if k.startswith("15TVG")}
    assert A.s2_dekads(one, NOW) == []                                 # 1 of 4 tiles


def test_s2_fixture_pass_writes_scenes_and_composes_nothing_out_of_season(
        tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    src = A.BY_ID["sat_s2_crop_green"]
    sst: dict = {}
    rec = A.collect_s2(paths, src, sst, {}, NOW, fetch=False, fixtures=FIX,
                       deadline=time.monotonic() + 30)
    assert rec["parsed"] == 1 and rec["scenes_held"] == 1 and rec["errors"] == []
    held = json.loads((paths.obs_dir / "sat_s2_crop_green.scenes.json").read_text("utf-8"))
    assert next(iter(held.values()))["tile"] == "15TVG"


def test_s2_backfill_walks_forward_and_stops_on_a_refusal(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    src = A.BY_ID["sat_s2_crop_green"]
    sst: dict = {"s2_month": "2019-01"}

    def refuse(url: str, headers: dict | None = None) -> tuple[bytes, str]:
        raise PermissionError("REFUSED: robots.txt disallows /")

    rec = A.collect_s2(paths, src, sst, {}, NOW, fetch=True, fixtures=None,
                       deadline=time.monotonic() + 30, getter=refuse)
    assert rec["errors"] and sst["s2_month"] == "2019-01" and "stop_until" in sst
    item = (FIX / "sat_s2_crop_green.json").read_bytes()

    def ok(url: str, headers: dict | None = None) -> tuple[bytes, str]:
        if "list-type=2" in url:
            return (b"<CommonPrefixes><Prefix>sentinel-s2-l2a-cogs/15/T/VG/2019/1/"
                    b"S2A_15TVG_20190105_0_L2A/</Prefix></CommonPrefixes>"), "application/xml"
        return item, "application/json"

    sst2: dict = {"s2_month": "2019-01"}
    rec2 = A.collect_s2(paths, src, sst2, {}, NOW, fetch=True, fixtures=None,
                        deadline=time.monotonic() + 30, getter=ok)
    # one pass walks every month up to the live window's edge (the same scene is fetched once)
    assert rec2["listed"] >= 1 and rec2["parsed"] == 1 and rec2["errors"] == []
    assert sst2["s2_month"] == "2026-10" and rec2["walk"] == "live"


def test_robots_gate_fails_closed() -> None:
    url = "https://example.org/data.csv"
    assert A.robots_refusal(url, fetch=lambda u: (404, "")) is None
    assert A.robots_refusal(url, fetch=lambda u: (403, ""))
    assert A.robots_refusal(url, fetch=lambda u: (500, ""))
    assert A.robots_refusal(url, fetch=lambda u: (200, "User-agent: *\nDisallow: /data"))
    assert A.robots_refusal(url, fetch=lambda u: (200, "User-agent: *\nAllow: /")) is None

    def boom(u: str) -> tuple[int, str]:
        raise OSError("down")
    assert A.robots_refusal(url, fetch=boom)


def test_new_sources_are_confirmed_with_evidence_and_map_only_admissible_instruments() -> None:
    # sat_s2_crop_green fails closed: its operative terms are the Sentinel Data Legal Notice,
    # which nobody has read yet (audit 2026-11-18); it is never fetched until that is quoted
    assert A.BY_ID["jobs_indeed_postings"].terms == "confirmed"
    assert A.BY_ID["sat_s2_crop_green"].terms == "to_confirm"
    assert A.status_of(A.BY_ID["sat_s2_crop_green"], {}).startswith("BLOCKED_ON_TERMS")
    for sid in ("jobs_indeed_postings", "sat_s2_crop_green"):
        src = A.BY_ID[sid]
        assert sid in A.TERMS_EVIDENCE and sid in A.ROBOTS_GATED
        assert src.substitutes_for and src.vintage == "current"
        for m in (src.instruments, *src.series_instruments.values()):
            for sym in m:
                assert universe_policy.may_hypothesise(sym, A.DIRECT_FAMILY), (sid, sym)
    assert A.credit_of("jobs_indeed_postings") == "Source: Indeed Hiring Lab"


def test_s2_seen_set_is_pruned_to_the_months_still_listed(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    sst: dict = {"s2_month": "2026-10", "s2_seen": {"old": "2019-03", "keep": "2026-10"}}
    A.collect_s2(paths, A.BY_ID["sat_s2_crop_green"], sst, {}, NOW, fetch=False, fixtures=None,
                 deadline=time.monotonic() + 5)
    assert sst["s2_seen"] == {"keep": "2026-10"}


def test_every_family_the_new_sources_emit_has_a_registered_builder() -> None:
    """The Judge's condition (2026-11-18): a cell whose family no code builds lands as
    NO_REGISTERED_BUILDER and never gets a verdict. Every direct cell the two builds can donate
    names a family `mt5desk.executables.resolve_family` (the forward engine's own constructor
    lookup) answers to; indirect children inherit a certified parent's family and are refused
    before donation when it does not resolve (`_parent_signal_returns`)."""
    from mt5desk.executables import resolve_family

    from research import paid_substitute_engine as pse
    gains = {}
    for sid in ("jobs_indeed_postings", "sat_s2_crop_green"):
        src = A.BY_ID[sid]
        for series in src.signal_series:
            for sym in src.instruments_for(series):
                gains[f"{sid}|{series}|{sym}"] = {"verdict": "PASS", "ic": 0.1, "n": 100}
    cells = A.direct_cells(gains, NOW)
    assert cells
    for fam in {c["family"] for c in cells}:
        assert resolve_family(fam) is not None, fam
    # the engine's indirect use is emitted only when its family is buildable here
    if pse.gate_family_available():
        assert resolve_family("exogenous_gate") is not None
