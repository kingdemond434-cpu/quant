"""GEOINT hazards (N3 natural-hazard shocks, N4 chokepoint transit) and the leg join: fixtures."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.alt_proxies as A  # noqa: E402
import research.geoint_hazards as G  # noqa: E402
from mt5desk import family_hazard_shock as H  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "geoint_hazards"
NOW = datetime(2026, 10, 14, 1, 0, tzinfo=UTC)


def _run(tmp: Path, **kw: object) -> dict:
    return G.run(fixtures=FIX, now=NOW, report=tmp / "GEOINT_HAZARDS.json",
                 state_path=tmp / "state.json", series_dir=tmp / "series",
                 style_novelty_path=tmp / "absent.json", **kw)  # type: ignore[arg-type]


def test_usgs_keeps_m6_quakes_inside_the_declared_boxes_only() -> None:
    rows = G.parse_usgs((FIX / "usgs_4.5_day.geojson").read_bytes(), NOW)
    assert sorted((r["kind"], r["magnitude"]) for r in rows) == [("quake_cl", 7.1),
                                                                  ("quake_jp", 6.4)]
    jp = next(r for r in rows if r["kind"] == "quake_jp")
    origin = datetime.fromisoformat(jp["event_time"])
    assert datetime.fromisoformat(jp["available_time"]) == origin + G.PUBLICATION_SLACK


def test_a_gulf_cone_is_an_event_at_its_advisory_issuance_and_an_open_ocean_cone_is_not() -> None:
    storms = {s["id"]: s for s in G.parse_nhc_current(
        (FIX / "nhc_current_storms.json").read_bytes())}
    assert set(storms) == {"al052026", "al062026"}                 # the EP storm is not Atlantic
    gulf = G.storm_event(storms["al052026"], (FIX / "nhc_cone_al052026.kmz").read_bytes(), NOW)
    assert gulf is not None and gulf["kind"] == "storm_gulf"
    assert gulf["available_time"] == "2026-10-13T21:00:00+00:00"
    assert G.storm_event(storms["al062026"], (FIX / "nhc_cone_al062026.kmz").read_bytes(),
                         NOW) is None


def test_the_leg_writes_the_lake_frame_terms_cells_and_novelty(tmp_path: Path) -> None:
    doc = _run(tmp_path, donate=False)
    assert doc["N3"]["events_by_kind"] == {"quake_jp": 2, "quake_tw": 0, "quake_cl": 1,
                                           "storm_gulf": 1}
    frame = pd.read_csv(tmp_path / "series" / G.SERIES_FILE)
    assert set(frame["kind"]) == {"quake_jp", "quake_cl", "storm_gulf"}
    assert {"available_time", "event_time", "first_seen_at"} <= set(frame.columns)
    on_disk = json.loads((tmp_path / "GEOINT_HAZARDS.json").read_text("utf-8"))
    assert on_disk["terms"]["usgs_earthquakes"]["verdict"] == "CONFIRMED"
    assert "programatic interface" in on_disk["terms"]["usgs_earthquakes"]["automation_quote"]
    assert on_disk["N3"]["n_cells"] == 8 * 8 and on_disk["N3"]["n_donatable"] == 0
    assert on_disk["N3"]["trials_charged_here"] == 0
    assert {v["verdict"] for v in on_disk["novelty"]["lanes"].values()} == {"UNMEASURED"}
    assert set(on_disk["novelty"]["lanes"]) == {"N3", "N4"}
    assert on_disk["geoint_sources"]["copernicus_s5p"]["status"] == "NEEDS_KEY"
    assert on_disk["geoint_sources"]["copernicus_s5p"]["cdsapi_key_grants_cdse"] == "NO"
    assert on_disk["N4"]["terms"] == "confirmed"


def test_a_second_pass_does_not_duplicate_events(tmp_path: Path) -> None:
    _run(tmp_path, donate=False)
    doc = _run(tmp_path, donate=False)
    assert doc["N3"]["n_events"] == 4 and doc["collect"]["added"] == 0


def test_a_held_or_failing_source_is_named_not_zeroed(tmp_path: Path) -> None:
    def boom(url: str) -> bytes:
        raise OSError("refused")
    store: dict = {}
    rec = G.collect(store, {}, NOW, fetch=True, fixtures=None, deadline=1e18, getter=boom)
    assert rec["requests"] >= 2 and rec["errors"] and store == {}


# ------------------------------------------------------------------------------ the family
def _bars(start: datetime, n: int, drift: float = 0.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    c = 150.0 + drift * np.arange(n)
    return pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c}, index=idx)


def _frame(tmp: Path, at: datetime, kind: str = "quake_jp") -> Path:
    d = tmp / "series"
    d.mkdir(exist_ok=True)
    pd.DataFrame([{"event_id": "e1", "kind": kind, "magnitude": 6.5,
                   "available_time": at.isoformat()}]).to_csv(d / f"{H.SERIES_ID}.csv",
                                                              index=False)
    H._CACHE.clear()
    return d


def test_drift_enters_on_the_first_bar_opening_after_the_notice(tmp_path: Path) -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    notice = start + timedelta(hours=40, minutes=20)
    root = _frame(tmp_path, notice)
    sigs = H.family_hazard_shock(_bars(start, 120), symbol="USDJPY", kind="quake_jp",
                                 prior_side=-1, series_root=root)
    assert len(sigs) == 1 and sigs[0].side == -1
    assert sigs[0].time == pd.Timestamp(start + timedelta(hours=41))   # never the bar holding it


def test_fade_trades_against_the_move_since_the_notice(tmp_path: Path) -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    root = _frame(tmp_path, start + timedelta(hours=40))
    sigs = H.family_hazard_shock(_bars(start, 120, drift=0.05), symbol="USDJPY", kind="quake_jp",
                                 mode="fade", series_root=root)
    assert len(sigs) == 1 and sigs[0].side == -1                      # price rose -> fade short


def test_hazard_family_refuses_without_its_frame_or_its_kind(tmp_path: Path) -> None:
    bars = _bars(datetime(2026, 3, 1, tzinfo=UTC), 120)
    H._CACHE.clear()
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="quake_jp",
                                 series_root=tmp_path) == []
    root = _frame(tmp_path, datetime(2026, 3, 2, tzinfo=UTC))
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="quake_tw", series_root=root) == []
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="volcano", series_root=root) == []


def test_hazard_family_is_registered() -> None:
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    from research.axis_registry import FAMILY_TABLE
    assert ORTHOGONAL_FAMILIES["hazard_shock"] is H.family_hazard_shock
    assert FAMILY_TABLE["hazard_shock"] == ("volatility_shock", "event", "market")


# ------------------------------------------------------------------------------ N4 and wiring
def test_chokepoint_transits_now_map_to_oil_gold_and_usdjpy() -> None:
    src = A.BY_ID["imf_portwatch_chokepoints"]
    assert set(src.instruments) == {"XTIUSD", "XBRUSD", "XAUUSD", "USDJPY"}
    assert src.terms == "confirmed" and "commercial" in A.TERMS_EVIDENCE[src.id]["terms_quote"]
    assert "suez_canal_transits" in src.signal_series


def test_alt_proxies_and_geoint_ride_a_department_that_reaches_the_tail() -> None:
    import hourly_cycle as hc
    assert hc.department_of("alt_proxies") == "intel"
    assert hc.department_of("geoint_hazards") == "intel"
    assert hc.LEG_BUDGET_SEC["geoint_hazards"] >= 120
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["geoint_hazards"] == "information"


@pytest.mark.parametrize("sid", ["cn_firms_industrial", "imf_portwatch_ports",
                                 "imf_portwatch_chokepoints"])
def test_geoint_series_sources_are_confirmed_and_on_the_alt_proxies_clock(sid: str) -> None:
    src = A.BY_ID[sid]
    assert src.terms == "confirmed"
    status = A.status_of(src, environ={"FIRMS_MAP_KEY": "x"})
    assert status == "UNMEASURED_LIVE_YIELD"
