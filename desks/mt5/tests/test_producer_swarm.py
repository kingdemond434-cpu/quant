"""The producer swarm: a roster from data, buildable cells only, least-judged first, no duplicates,
holes first, a lap that reaches every producer, every cell charged, every producer measured.

Registry, bars and outputs are redirected into `tmp_path`; nothing here writes box state.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import gauntlet_buildability as gb  # noqa: E402
from research import producer_breadth as pb  # noqa: E402
from research import producer_swarm as ps  # noqa: E402

KEEP = ("session_range_breakout", "cross_sectional_class_momentum", "overnight_gap_decay")
BARS = {"H1": {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD", "XAGUSD"},
        "M15": {"EURUSD", "XAUUSD"}}


def _reg(**over: Any) -> dict[str, Any]:
    """The real registry, narrowed to three families by its own exclusion list (data, not code)."""
    reg = ps.load_registry()
    fams, _aside = ps.swarm_families(reg)
    excl = dict(reg["families"]["exclude"])
    excl.update({f: "narrowed for the test" for f in fams if f not in KEEP})
    reg = {**reg, "families": {**reg["families"], "exclude": excl},
           "charts": ["H1", "M15"], "sessions": ["all", "london"],
           "transforms": {"base": {}, "high_vol": {"regime": "high_vol"}},
           # the culture and dataset producers have their own tests
           "cultures": {}, "dataset_conditioning": {}}
    reg.update(over)
    return reg


def test_the_roster_is_instantiated_from_the_data_file() -> None:
    roster, census = ps.instantiate(_reg(), bars=BARS)
    assert roster and census["producers"] == len(roster)
    ids = {p.pid for p in roster}
    assert len(ids) == len(roster)                              # every producer its own id
    assert {p.family for p in roster} == set(KEEP)
    assert {p.chart for p in roster} <= {"H1", "M15"}
    assert {p.transform for p in roster} == {"base", "high_vol"}
    # the class book is H1-only by its own declaration: no M15 producer, counted by reason
    assert not [p for p in roster if p.family == "cross_sectional_class_momentum"
                and p.chart == "M15"]
    assert census["not_instantiated"].get("timeframe_refused_by_family", 0) > 0
    # the data file decides: one more transform, more producers
    more, _ = ps.instantiate(_reg(transforms={"base": {}, "high_vol": {"regime": "high_vol"},
                                              "delayed": {"entry_timing": "delayed"}}),
                             bars=BARS)
    assert len(more) == len(roster) * 3 // 2
    # each producer's lane is its class's symbols with bars on its chart
    p = next(p for p in roster if p.pid == "session_range_breakout.metals.M15.all.base")
    assert p.lane == ("XAUUSD",)


def test_every_minted_cell_is_buildable_and_a_class_book_carries_its_symbol() -> None:
    reg = _reg()
    roster, _ = ps.instantiate(reg, bars=BARS)
    known: set[str] = set()
    for p in roster:
        cells, _outcome = ps.visit(p, 3, reg, known, ({}, {}))
        for c in cells:
            assert gb.cell_verdict(p.family, c["params"])[0] == gb.BUILDABLE
            assert c["symbol"] in p.lane
            if p.family == "cross_sectional_class_momentum":
                assert c["params"]["symbol"] == c["symbol"]
            if p.chart != "H1":
                assert c["params"]["timeframe"] == p.chart
            if p.session != "all":
                assert c["params"]["session"] == p.session


def test_a_class_book_without_its_symbol_is_not_buildable() -> None:
    """Measured: 0 signals at symbol='' on real EURUSD bars, >0 with it."""
    import pandas as pd
    from mt5desk.families_cross_sectional import family_cross_sectional_class_momentum as f
    path = _DESK / "data" / "universe" / "EURUSD_H1.parquet"
    if not path.exists():
        pytest.skip("no EURUSD bars on this tree")
    df = pd.read_parquet(path)
    assert f(df) == [] and len(f(df, symbol="EURUSD")) > 0
    assert gb.cell_verdict("cross_sectional_class_momentum", {})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("cross_sectional_class_momentum",
                           {"symbol": "EURUSD"})[0] == gb.BUILDABLE


def test_a_producer_walks_least_judged_first_and_never_mints_a_known_cell() -> None:
    from research.frontier_identity import cell_id
    reg = _reg()
    roster, _ = ps.instantiate(reg, bars=BARS)
    p = next(p for p in roster if p.pid == "session_range_breakout.fx.H1.all.base")
    judged = {("EURUSD", p.family): 9, ("GBPUSD", p.family): 5, ("AUDUSD", p.family): 1}
    cells, outcome = ps.visit(p, 1, reg, set(), ({}, judged))
    assert outcome == "MINTED" and cells[0]["symbol"] == "USDJPY"     # never judged: first
    known = {cell_id({"sym": s, "family": p.family, "params": dict(p.base)}) for s in p.lane}
    cells, _ = ps.visit(p, 1, reg, set(known), ({}, judged))
    assert cells and cells[0]["variant"] != "defaults"               # defaults done: a move
    # every reachable cell known -> EXHAUSTED, never a copy
    everything: set[str] = set()
    while True:
        got, outcome = ps.visit(p, 50, reg, everything, ({}, {}))
        if not got:
            break
    assert outcome == "EXHAUSTED"


def test_the_lap_visits_every_producer_and_holes_go_first() -> None:
    reg = _reg(hourly_cell_ceiling=40, hole_visit_share=0.25, visit_lap_hours=6)
    roster, _ = ps.instantiate(reg, bars=BARS)
    seen: set[str] = set()
    cursor: dict[str, Any] = {"pos": 0}
    for turn in range(6):
        pl = ps.plan(roster, reg, cursor, {"clusters": [], "asset_classes": [], "charts": [],
                                           "sessions": []}, turn)
        seen |= {p.pid for p in pl["ring"]}
        cursor = {"pos": (pl["pos"] + len(pl["ring"])) % len(roster)}
    assert seen == {p.pid for p in roster}
    hole = {"clusters": [], "asset_classes": ["metals"], "charts": [], "sessions": []}
    pl = ps.plan(roster, reg, {"pos": 0}, hole, 0)
    assert pl["hole"] and all(p.klass == "metals" for p in pl["hole"])
    assert len(pl["hole"]) * pl["quota"] <= 10                       # 25% of a 40-cell ceiling
    assert (len(pl["ring"]) + len(pl["hole"])) * pl["quota"] <= 40


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


def test_a_pass_writes_through_the_registry_door_charges_every_cell_and_never_repeats(
        sandbox: Path) -> None:
    reg = _reg(hourly_cell_ceiling=30)
    out = sandbox / "out"
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    known: set[str] = set()
    doc = ps.run(now=now, reg=reg, bars=BARS, out_dir=out, known=known)
    minted = doc["hour"]["cells_minted"]
    assert minted > 0 and doc["write"]["created"] == minted and not doc["write"]["why"]
    rows = [json.loads(x) for x in (out / "PRODUCER_SWARM_TRIALS.jsonl").read_text().splitlines()]
    assert sum(r["cells_screened"] for r in rows) == minted          # every cell charged
    from libs.research import experiment_ledger as EL
    total, by_fam = EL._mass_screen_counts(out / "PRODUCER_SWARM_TRIALS.jsonl")
    assert total == minted and set(by_fam) <= set(KEEP)
    visits = (out / "producer_swarm_visits.jsonl").read_text().splitlines()
    assert len(visits) == doc["hour"]["visits"]
    cur = json.loads((out / "producer_swarm_cursor.json").read_text())
    assert cur["pos"] == doc["hour"]["ring_visits"] % doc["roster"]["producers"]
    # the next hour starts where this one stopped and mints nothing already minted
    doc2 = ps.run(now=now, reg=reg, bars=BARS, out_dir=out, known=known)
    assert doc2["hour"]["cells_minted"] > 0
    assert doc2["write"]["already_present"] == 0
    # the registry holds them under the swarm's generator, one source_id per producer
    import sqlite3
    con = sqlite3.connect(sandbox / "alpha_registry.sqlite")
    got = con.execute("select count(*), count(distinct source_id) from research_candidates "
                      "where generator='producer_swarm'").fetchone()
    con.close()
    assert got[0] == minted + doc2["hour"]["cells_minted"] and got[1] > 1


def test_producer_breadth_measures_every_swarm_producer_individually(
        sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _reg(hourly_cell_ceiling=30)
    now = datetime.now(UTC)
    doc = ps.run(now=now, reg=reg, bars=BARS, out_dir=sandbox / "out", known=set())
    roster, census = ps.instantiate(reg, bars=BARS)
    monkeypatch.setattr(ps, "instantiate", lambda *a, **k: (roster, census))
    monkeypatch.setattr(pb, "SWARM_VISITS", sandbox / "out" / "producer_swarm_visits.jsonl")
    b = pb.build(now=now, db=sandbox / "alpha_registry.sqlite")
    sw = b["swarm"]
    assert sw["status"] == "MEASURED" and len(sw["producers"]) == len(roster)
    minted = sum(r["cells_24h"] for r in sw["producers"].values())
    assert minted == doc["hour"]["cells_minted"]
    active = [r for r in sw["producers"].values() if r["cells_24h"]]
    idle = [r for r in sw["producers"].values() if not r["cells_24h"]]
    assert active and all("IDLE" not in r["flags"] for r in active)
    assert all(r["buildable_share"] == 1.0 for r in active)
    assert idle and all("IDLE" in r["flags"] and r["reasons"]["IDLE"] for r in idle)
    # rolled up by family, and in the headline
    assert set(sw["by_family"]) == {p.family for p in roster}
    h = b["headline"]
    assert h["swarm"]["producers"] == len(roster) and h["swarm"]["active"] == len(active)
    assert h["producers_total"] == h["swarm"]["producers"] + h["hand_written"]["producers"]


def test_the_leg_is_wired() -> None:
    import hourly_cycle as HC

    from libs.research.layers import LEG_LAYER
    assert HC.department_of("producer_swarm") == "discovery"
    assert LEG_LAYER["producer_swarm"] == "prediction"
    assert HC.LEG_BUDGET_SEC["producer_swarm"] >= 300
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("producer_swarm", producer_swarm)' in src
    assert src.index('_costed("producer_swarm"') < src.index('_costed("merge_docket"')
    assert '"producer_swarm": psw' in src
    clocks = pb.clocks_for("producer_swarm", "producer_swarm", {"hourly_cycle": src}, [])
    assert clocks == ["hourly_cycle:producer_swarm"]
