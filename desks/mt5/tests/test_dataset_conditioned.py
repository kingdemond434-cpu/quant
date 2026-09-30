"""Every dataset feeds three uses: the point-in-time loader, the conditioned family, the dataset
census in PRODUCER_BREADTH.json, and the swarm's dataset and culture producers.

Synthetic datasets, bars and registry only, all under `tmp_path`; nothing here writes box state.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import dataset_series as DS  # noqa: E402
from mt5desk import families_orthogonal as FO  # noqa: E402
from mt5desk import family_dataset_conditioned as FDC  # noqa: E402

from research import dataset_census as DC  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402
from research import producer_breadth as pb  # noqa: E402
from research import producer_swarm as ps  # noqa: E402

BASE = "session_range_breakout"


def bars(days: int = 700, seed: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2022-01-03", periods=days * 24, freq="h", tz="UTC")
    idx = idx[idx.weekday < 5]
    rng = np.random.default_rng(seed)
    close = 1.2 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
    opn = np.r_[close[0], close[:-1]]
    wig = np.abs(rng.normal(0, 0.0005, len(idx)))
    df = pd.DataFrame({"open": opn, "close": close, "high": np.maximum(opn, close) + wig,
                       "low": np.minimum(opn, close) - wig, "tick_volume": 100.0}, index=idx)
    df.index.name = "time"
    return df


def cot_file(root: Path, rel: str = "cot/syn", weeks: int = 150, seed: int = 1,
             start: str = "2022-03-01") -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=weeks, freq="W-TUE")
    df = pd.DataFrame({"report_date": dates.strftime("%Y-%m-%d"),
                       "noncomm_positions_long_all": rng.integers(1000, 9000, weeks),
                       "noncomm_positions_short_all": rng.integers(1000, 9000, weeks),
                       "open_interest_all": rng.integers(10000, 20000, weeks)})
    p = root / f"{rel}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    return p


# ------------------------------------------------------------------ the loader
def test_a_cot_reading_is_never_available_before_the_saturday_after_its_report(tmp_path):
    cot_file(tmp_path)
    s = DS.raw("cot:cot/syn", "noncomm_positions_long_all-noncomm_positions_short_all",
               root=tmp_path)
    assert s is not None and len(s) == 150
    assert (s.index.dayofweek == 5).all() and (s.index.hour == 0).all()     # Saturday 00:00
    assert s.index[0] == pd.Timestamp("2022-03-05", tz="UTC")                 # Tue 1st + 4d
    # the shaped series is lagged a publication day more, before any join
    c = DS.conditioned("cot:cot/syn", "open_interest_all", transform="level", root=tmp_path)
    assert c is not None and c.index[0] == pd.Timestamp("2022-03-06", tz="UTC")
    assert DS.pair_fields(["noncomm_positions_long_all", "noncomm_positions_short_all",
                           "lm_l", "lm_s"]) == ["noncomm_positions_long_all-"
                                                "noncomm_positions_short_all", "lm_l-lm_s"]
    assert DS.raw("cot:../../etc/passwd", "x", root=tmp_path) is None


def test_an_intelligence_snapshot_is_stamped_by_its_name_never_its_mtime(tmp_path):
    seat = tmp_path / "gauge"
    seat.mkdir()
    (seat / "discoveries_20260901_0930.json").write_text(json.dumps(
        [{"symbol": "USDJPY", "value": 1.0}, {"symbol": "EURUSD", "value": 5.0}]))
    (seat / "discoveries_20260902_0930.json").write_text(json.dumps(
        [{"symbol": "USDJPY", "value": 3.0}]))
    (seat / "rollup_20260903.jsonl").write_text(json.dumps({"symbol": "USDJPY", "value": 7}))
    (seat / "latest.json").write_text(json.dumps([{"symbol": "USDJPY", "value": 99.0}]))
    s = DS.intel_raw("gauge", "value", match="symbol=USDJPY", roots=(tmp_path,))
    assert s is not None and list(s) == [1.0, 3.0, 7.0]                     # no unstamped file
    assert list(s.index) == [pd.Timestamp("2026-09-01 09:30", tz="UTC"),
                             pd.Timestamp("2026-09-02 09:30", tz="UTC"),
                             pd.Timestamp("2026-09-04 00:00", tz="UTC")]    # rollup: day's end
    both = DS.intel_raw("gauge", "value", roots=(tmp_path,))
    assert both is not None and both.iloc[0] == 3.0                         # mean of the rows
    assert DS.intel_raw("../gauge", "value", roots=(tmp_path,)) is None


# ------------------------------------------------------------------ the family
def test_the_states_partition_the_base_exactly_and_nothing_fires_before_the_data(tmp_path):
    cot_file(tmp_path)
    df = bars()
    from mt5desk.families import get_family_func
    base = get_family_func(BASE)(df)
    kw = {"base_family": BASE, "dataset": "cot:cot/syn",
          "field": "noncomm_positions_long_all-noncomm_positions_short_all",
          "series_root": tmp_path}
    got = {st: FDC.family_dataset_conditioned(df, **kw, state=st) for st in FDC.STATES}
    first = DS.conditioned("cot:cot/syn", kw["field"], root=tmp_path).index[0]
    before = [s for s in base if s.time < first]
    assert got["high"] and got["low"] and got["mid"] and before
    n = sum(len(v) for v in got.values())
    assert n == len(base) - len(before)
    assert all(s.time >= first for v in got.values() for s in v)
    times = {st: {s.time for s in v} for st, v in got.items()}
    assert not (times["high"] & times["low"]) and not (times["high"] & times["mid"])


def test_the_join_is_causal_future_readings_never_move_a_past_entry(tmp_path):
    full = tmp_path / "full"
    part = tmp_path / "part"
    cot_file(full)
    p = cot_file(part)
    d = pd.read_parquet(p)
    d.iloc[:120].to_parquet(p)
    df = bars()
    kw = {"base_family": BASE, "dataset": "cot:cot/syn", "field": "open_interest_all",
          "state": "high", "threshold": 0.5}
    a = FDC.family_dataset_conditioned(df, **kw, series_root=full)
    b = FDC.family_dataset_conditioned(df, **kw, series_root=part)
    cut = DS.raw("cot:cot/syn", "open_interest_all", root=part).index[-1]
    assert [s.time for s in a if s.time <= cut] == [s.time for s in b if s.time <= cut]


def test_it_refuses_rather_than_falling_back_to_the_unconditioned_base(tmp_path):
    cot_file(tmp_path, weeks=20)                                      # under MIN_OBSERVATIONS
    df = bars(200)
    kw = {"dataset": "cot:cot/syn", "field": "open_interest_all", "series_root": tmp_path}
    assert FDC.family_dataset_conditioned(df, base_family=BASE, **kw) == []
    cot_file(tmp_path)
    assert FDC.family_dataset_conditioned(df, base_family="carry", **kw) == []    # unwrappable
    assert FDC.family_dataset_conditioned(df, base_family="dataset_conditioned", **kw) == []
    assert FDC.family_dataset_conditioned(df, base_family=BASE, state="sideways", **kw) == []
    assert FDC.family_dataset_conditioned(df, base_family=BASE, dataset="cot:none",
                                          field="x", series_root=tmp_path) == []


def test_registered_buildable_only_with_its_inputs_h1_only_with_an_axis_group():
    from research import axis_registry as AX
    fam = "dataset_conditioned"
    assert FO.ORTHOGONAL_FAMILIES[fam] is FDC.family_dataset_conditioned
    assert AX.FAMILY_TABLE[fam][0] == "UNKNOWN"
    p = {"base_family": BASE, "dataset": "cot:cot/gbp", "field": "open_interest_all"}
    assert gb.cell_verdict(fam, {})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict(fam, p)[0] == gb.BUILDABLE
    assert gb.cell_verdict(fam, {**p, "timeframe": "H4"})[0] == gb.TIMEFRAME_REFUSED


# ------------------------------------------------------------------ the census
def _registry(path: Path, rows: list[dict[str, Any]]) -> Path:
    con = sqlite3.connect(path)
    con.execute("create table research_candidates (id text, created_at text, family text, "
                "symbol text, params_json text, source_id text)")
    for i, r in enumerate(rows):
        con.execute("insert into research_candidates values (?,?,?,?,?,?)",
                    (f"c{i}", r.get("at", "2026-09-30T10:00:00"), r["family"], "EURUSD",
                     json.dumps(r.get("params", {})), r.get("source_id", "")))
    con.commit()
    con.close()
    return path


def _ds(did: str, usable: bool = True, names: list[str] | None = None) -> dict[str, Any]:
    kind = did.split(":")[0]
    return {"id": did, "kind": kind, "path": None, "source_names": names or [],
            "fields": [{"field": "v", "match": ""}], "source_culture": "JP",
            "pit": {"usable": usable, "why": "" if usable else "no stamp"}}


def test_the_census_names_every_unfed_dataset_with_its_three_uses(tmp_path, monkeypatch):
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    db = _registry(tmp_path / "r.sqlite", [
        {"family": "dataset_conditioned", "params": {"dataset": "intel:fed_indirect"}},
        {"family": "exogenous_conditioner", "source_id": "fed_direct"},
        {"family": "dataset_conditioned", "params": {"dataset": "intel:stale"},
         "at": "2026-09-01T00:00:00"}])
    monkeypatch.setattr(DC, "COMPILED", tmp_path / "absent.json")
    ds = [_ds("intel:fed_indirect"), _ds("lake:fed_direct", names=["fed_direct"]),
          _ds("intel:stale"), _ds("grounds:nothing", usable=False)]
    c = DC.census(now, db, datasets=ds)
    rows = c["datasets"]
    assert rows["intel:fed_indirect"]["uses"]["indirect"]["cells_7d"] == 1
    assert rows["lake:fed_direct"]["uses"]["direct"]["cells_7d"] == 1
    assert c["unfed"] == ["grounds:nothing", "intel:stale"]           # 7d window, not lifetime
    assert c["unfed_conditionable"] == ["intel:stale"]
    for r in rows.values():
        assert set(r["uses"]) == {"direct", "indirect", "allocation"}
        assert isinstance(r["uses"]["allocation"]["organs"], list)
        assert r["uses"]["direct"]["compiler_candidates_last_pass"] == "UNMEASURED"
    assert "NO_PIT_SERIES" in rows["grounds:nothing"]["why"]
    # nothing readable -> UNMEASURED, never "unfed"
    c2 = DC.census(now, tmp_path / "no.sqlite", datasets=ds)
    assert c2["unfed"] == [] and c2["totals"]["unmeasured"] == len(ds)


def test_the_census_finds_the_real_cftc_files_and_who_reads_them():
    found = {d["id"]: d for d in DC.cot_datasets()}
    if "cot:cot/gbp" not in found:
        pytest.skip("no CFTC files on this tree")
    d = found["cot:cot/gbp"]
    assert d["pit"]["usable"] and d["pit"]["points"] > 1000
    assert d["fields"][0]["field"].endswith("-noncomm_positions_short_all") or \
        "-" in d["fields"][0]["field"]
    texts = DC._corpus()
    assert "desks/mt5/research/dataset_census.py" not in texts["producers"]


def test_the_headline_puts_unfed_datasets_first():
    ds = {"totals": {"datasets": 2, "feeding": 0, "unfed": 2, "unmeasured": 0,
                     "conditionable": 1, "unfed_conditionable": 1},
          "unfed_conditionable": ["cot:cot/gbp"],
          "datasets": {"cot:cot/gbp": {"why": "UNWIRED"}}}
    h = pb.headline({}, {}, [{"cluster": "trend", "why": "UNMINTED: x"}],
                    {"clusters": ["carry"]}, ds)
    assert h["top_gaps"][0].startswith("dataset cot:cot/gbp feeds no producer")
    assert h["datasets"]["unfed_conditionable"] == 1


# ------------------------------------------------------------------ the swarm
KEEP = ("session_range_breakout", "overnight_gap_decay")
BARS = {"H1": {"EURUSD", "USDJPY", "EURJPY", "XAUUSD", "USDZAR"}, "M15": {"USDJPY"}}


def _reg(**over: Any) -> dict[str, Any]:
    reg = ps.load_registry()
    fams, _ = ps.swarm_families(reg)
    excl = dict(reg["families"]["exclude"])
    excl.update({f: "narrowed for the test" for f in fams if f not in KEEP})
    reg = {**reg, "families": {**reg["families"], "exclude": excl}, "charts": ["H1", "M15"],
           "sessions": ["all", "london"], "transforms": {"base": {}}}
    reg.update(over)
    return reg


def test_culture_producers_trade_their_own_instruments_in_their_home_session():
    reg = _reg(dataset_conditioning={})
    roster, census = ps.instantiate(reg, bars=BARS, datasets=[])
    jp = [p for p in roster if p.culture == "JP"]
    assert jp and all(set(p.lane) <= {"USDJPY", "EURJPY"} for p in jp)
    assert all(p.session == "asia" for p in jp)                   # home session, not a sweep
    assert all(p.participant == "retail_heavy" and "Tokyo" in p.failure_mode for p in jp)
    za = [p for p in roster if p.culture == "ZA"]
    assert za and all("USDZAR" in p.lane for p in za)
    glob = [p for p in roster if p.culture == "GLOBAL"]
    assert glob and all(p.failure_mode == ps.GLOBAL_FAILURE_MODE for p in glob)
    assert census["culture_producers"] == len(roster) - len(glob)
    assert 0 < census["non_global_share"] < 1


def test_dataset_producers_mint_buildable_conditioned_cells_state_by_state():
    reg = _reg(cultures={})
    ds = [_ds("cot:cot/gbp"), _ds("intel:dead", usable=False)]
    roster, census = ps.instantiate(reg, bars=BARS, datasets=ds)
    dp = [p for p in roster if p.dataset and p.use == "conditioning"]
    assert dp and {p.dataset for p in dp} == {"cot:cot/gbp"}      # an unusable one: none
    assert {p.base["base_family"] for p in dp} == set(KEEP)
    # the DIRECT use beside it (CRO D18): one dataset_stance producer per field, same dataset
    direct = [p for p in roster if p.dataset and p.use == "direct"]
    assert direct and {p.family for p in direct} == {"dataset_stance"}
    assert {p.dataset for p in direct} == {"cot:cot/gbp"}
    assert census["datasets"]["datasets_wired"] == 1
    p = dp[0]
    cells, outcome = ps.visit(p, 10, reg, set(), ({}, {}))
    assert outcome == "MINTED"
    assert {c["params"]["state"] for c in cells} <= {"high", "low"}
    for c in cells:
        assert gb.cell_verdict("dataset_conditioned", c["params"])[0] == gb.BUILDABLE


def test_the_hour_visits_unfed_datasets_then_cultures_and_never_starves_the_lap():
    reg = _reg(hourly_cell_ceiling=60, visit_lap_hours=4, hole_visit_share=0.25,
               culture_visit_share=0.30,
               dataset_conditioning={**ps.load_registry()["dataset_conditioning"],
                                     "unfed_visit_share": 0.20})
    ds = [_ds("cot:cot/gbp"), _ds("cot:cot/jpy")]
    roster, _ = ps.instantiate(reg, bars=BARS, datasets=ds)
    pl = ps.plan(roster, reg, {"pos": 0}, {"clusters": [], "asset_classes": [], "charts": [],
                                            "sessions": []}, 0, unfed={"cot:cot/jpy"})
    assert pl["dataset"] and all(p.dataset == "cot:cot/jpy" for p in pl["dataset"])
    assert pl["culture"] and all(p.culture != "GLOBAL" and not p.dataset for p in pl["culture"])
    ids = [p.pid for k in ("dataset", "culture", "ring") for p in pl[k]]
    assert len(ids) == len(set(ids))
    assert len(pl["ring"]) == pl["ring_k"]                        # the lap keeps its floor
    total = sum(len(pl[k]) for k in ("dataset", "culture", "hole", "ring")) * pl["quota"]
    assert total <= 60


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


def test_every_swarm_cell_carries_its_culture_provenance(sandbox: Path) -> None:
    reg = _reg(hourly_cell_ceiling=200)
    doc = ps.run(now=datetime(2026, 9, 30, 12, tzinfo=UTC), reg=reg, bars=BARS,
                 out_dir=sandbox / "out", known=set(), datasets=[_ds("cot:cot/gbp")],
                 breadth={})
    assert doc["hour"]["cells_minted"] > 0
    assert doc["hour"]["culture_visits"] > 0 and doc["hour"]["dataset_visits"] > 0
    con = sqlite3.connect(sandbox / "alpha_registry.sqlite")
    rows = con.execute("select lineage_json, region from research_candidates "
                       "where generator='producer_swarm'").fetchall()
    con.close()
    assert len(rows) == doc["write"]["created"]
    keys = ("source_culture", "participant_structure", "failure_mode_hypothesis")
    cultures = set()
    for lj, _region in rows:
        lin = json.loads(lj)
        assert all(lin.get(k) for k in keys)
        cultures.add(lin["source_culture"])
    assert cultures - {"GLOBAL"}                    # the non-Western slice minted this hour
    for s in doc["cell_sample"]:
        assert all(s.get(k) for k in keys)
