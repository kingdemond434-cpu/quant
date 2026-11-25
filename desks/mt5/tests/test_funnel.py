"""The end-to-end funnel: stage joins, UNMEASURED inputs, the weakest stage, waste and the floors
that only ratchet up. Every input is synthetic and lives in `tmp_path`."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_spec as fs  # noqa: E402
from research import funnel as fn  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
EXOTIC = {"EURZAR"}


def _w(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _hyp(source: str, sym: str, params: dict[str, Any], prose: str = "") -> dict[str, Any]:
    r: dict[str, Any] = {"symbol": sym, "family": "trend_ma_cross", "params": params,
                         "source": source}
    if prose:
        r["exact_rules"] = prose
    return r


def _desk(tmp: Path, *, conversion: bool = True, provenance: bool = True,
          sleeves: bool = True) -> fn.Paths:
    p = fn.Paths.at(tmp)
    if conversion:
        _w(p.conversion, {"producers": [
            {"producer": "alpha", "discoveries": 100, "candidates": 40, "judged": 30,
             "certificates": 3}], "totals": {"judged": 55}})
    _w(p.reach, {"producers": [{"producer": "alpha", "judged_quality": {
        fs.EXECUTABLE: 30, fs.DEFAULTS_ONLY: 10, "UNMEASURED": 5}}]})
    hyps = ([_hyp("miner:gamma", "EURUSD", {"fast_ema": 7, "slow_ema": 30})] * 6
            + [_hyp("miner:gamma", "EURUSD", {})] * 3
            + [_hyp("miner:gamma", "GBPUSD", {}, prose="buy when it feels right")])
    _w(p.compiler, {"hypotheses": hyps, "per_source": {"gamma": {"rows": 20,
                                                                 "candidates": 10}}})
    _w(p.seen, {"EURUSD.trend_ma_cross.p=1": "t", "GBPUSD.trend_ma_cross.p=2": "t"})
    if provenance:
        _w(p.provenance, {"records": {
            c: {"cell": c, "producer": "alpha", "in_canon": True} for c in (
                "EURUSD.trend_ma_cross.p=1", "GBPUSD.trend_ma_cross.p=2",
                "EURZAR.trend_ma_cross.p=3")}})
    _w(p.shadow_dir / "shadow_state.json", {
        "EURUSD.trend_ma_cross.asia": {"status": "ACTIVE"},
        "GBPUSD.trend_ma_cross.asia": {"status": "KILL"}})
    if sleeves:
        _w(p.sleeves, {"sleeves": [
            {"name": "s1", "symbol": "EURUSD", "family": "trend_ma_cross", "status": "LIVE",
             "risk_frac": 0.01},
            {"name": "s2", "symbol": "GBPUSD", "family": "trend_ma_cross",
             "status": "STANDBY", "risk_frac": 0.0}]})
    p.fills.parent.mkdir(parents=True, exist_ok=True)
    p.fills.write_text(json.dumps({"sleeve": "s1", "filled_at": "2026-11-20T00:00:00Z"})
                       + "\n", "utf-8")
    return p


def _trades(name: str) -> list[dict[str, Any]]:
    return [{"r_multiple": 1.0, "time": "2026-11-24T00:00:00+00:00"}] if name == "s1" else []


def _build(p: fn.Paths) -> dict[str, Any]:
    return fn.build(p, now=NOW, budget_s=60, is_exotic=lambda s: s in EXOTIC,
                    trades_of=_trades)


def _row(rows: list[dict[str, Any]], key: str, name: str) -> dict[str, Any]:
    return next(r for r in rows if r[key] == name)


def test_stage_counts_join_from_every_input(tmp_path: Path) -> None:
    doc = _build(_desk(tmp_path))
    st = doc["desk"]["stages"]
    # RAW / ROWS: compiler intake (20 / 10) + registry (100 / 40)
    assert st["RAW"] == 120 and st["ROWS"] == 50
    # TESTABLE: 6 executable compiler rows + 40 * 30/40 estimated from the judge-reach sample
    assert st["TESTABLE"] == 36
    assert st["JUDGED"] == 55                       # the registry total wins over seen cells
    assert st["CERTIFIED"] == 3 and st["NON_EXOTIC_CERTIFIED"] == 2
    assert st["FORWARD_CLOCKED"] == 2 and st["PROMOTED"] == 2
    assert st["FILL_PROVEN"] == 1 and st["LIVE"] == 1 and st["LIVE_PROFIT"] == 1
    alpha = _row(doc["producers"], "producer", "alpha")["stages"]
    assert alpha["RAW"] == 100 and alpha["JUDGED"] == 30 and alpha["CERTIFIED"] == 3
    gamma = _row(doc["producers"], "producer", "gamma")["stages"]
    assert gamma["RAW"] == 20 and gamma["ROWS"] == 10 and gamma["TESTABLE"] == 6
    assert gamma["JUDGED"] == fn.UNMEASURED and gamma["CERTIFIED"] == 0
    fam = _row(doc["families"], "family", "trend_ma_cross")["stages"]
    assert fam["ROWS"] == 10 and fam["JUDGED"] == 2 and fam["RAW"] == fn.UNMEASURED
    rate = {t["transition"]: t["rate"] for t in doc["desk"]["transitions"]}
    assert rate["CERTIFIED->NON_EXOTIC_CERTIFIED"] == round(2 / 3, 6)
    assert rate["LIVE->LIVE_PROFIT"] == 1.0
    assert doc["desk"]["depth"]["breadth_units"]["CERTIFIED"] > 0


def test_defaults_only_and_prose_only_rows_are_waste_never_testable(tmp_path: Path) -> None:
    doc = _build(_desk(tmp_path))
    gamma = _row(doc["producers"], "producer", "gamma")
    assert gamma["waste"]["defaults_only"] == 3 and gamma["waste"]["prose_only"] == 1
    assert gamma["stages"]["TESTABLE"] == 6
    t = next(x for x in gamma["transitions"] if x["transition"] == "ROWS->TESTABLE")
    assert t["denominator"] == 10 and t["rate"] == 0.6
    w = doc["desk"]["waste"]
    assert w["defaults_only"] == 3 + 10 and w["prose_only"] == 1
    assert doc["desk"]["depth"]["testable_cells"] == 1     # six rows, one distinct cell


def test_an_unreadable_input_is_unmeasured_never_zero(tmp_path: Path) -> None:
    doc = _build(_desk(tmp_path, provenance=False, conversion=False))
    st = doc["desk"]["stages"]
    assert all(st[s] == fn.UNMEASURED for s in fn.CERT_STAGES)
    assert st["JUDGED"] == 2                        # falls back to the judge's seen cells
    assert doc["inputs"]["producer_conversion"] == fn.UNMEASURED
    doc = _build(_desk(tmp_path / "b", sleeves=False))
    st = doc["desk"]["stages"]
    assert st["FORWARD_CLOCKED"] == 2
    assert all(st[s] == fn.UNMEASURED for s in ("PROMOTED", "FILL_PROVEN", "LIVE",
                                                 "LIVE_PROFIT"))
    t = {x["transition"]: x["rate"] for x in doc["desk"]["transitions"]}
    assert t["FORWARD_CLOCKED->PROMOTED"] == fn.UNMEASURED


def test_a_stage_nothing_reached_is_no_inflow_not_unmeasured() -> None:
    n = dict.fromkeys(fn.STAGES, 0)
    t = {x["transition"]: x["rate"] for x in fn.transitions(n)}
    assert t["LIVE->LIVE_PROFIT"] == fn.NO_INFLOW


def _cut(**rates: tuple[int, float]) -> dict[str, Any]:
    return {"transitions": [{"transition": k.replace("__", "->"), "denominator": d, "rate": r}
                            for k, (d, r) in rates.items()]}


def test_weakest_stage_is_lowest_relative_to_the_median() -> None:
    rows = [_cut(A__B=(100, 0.5), B__C=(100, 0.1)), _cut(A__B=(100, 0.5), B__C=(100, 0.1)),
            _cut(A__B=(100, 0.1), B__C=(100, 0.09))]
    med = fn.medians(rows)
    assert med == {"A->B": 0.5, "B->C": 0.1}
    w = fn.weakest(rows[2], med)
    # 0.1 / 0.5 = 0.2 beats 0.09 / 0.1 = 0.9 even though 0.09 is the smaller rate
    assert w["transition"] == "A->B" and w["relative_to_median"] == 0.2
    thin = _cut(A__B=(5, 0.0), B__C=(100, 0.05))
    assert fn.weakest(thin, med)["transition"] == "B->C"     # under MIN_N is not ranked
    assert fn.weakest(_cut(A__B=(5, 0.0)), med)["status"] == "INSUFFICIENT_N"


def test_attack_order_names_owner_and_puts_violations_first(tmp_path: Path) -> None:
    p = _desk(tmp_path)
    _w(p.floors, {"stages": {"LIVE": {"count_floor": 5}}, "transitions": {}})
    doc = _build(p)
    att = doc["desk"]["attack_order"]
    assert att[0]["transition"] == "FILL_PROVEN->LIVE" and att[0]["floor_status"] == "VIOLATED"
    assert all(a["organ"] and a["remedy"] for a in att)
    assert {a["transition"] for a in att} == set(fn.OWNERS)
    assert "LIVE" in doc["desk"]["violated"]


def test_floors_ratchet_up_only_and_have_no_ceiling() -> None:
    assert fn.ratchet_one(None, 100, integer=True) == (90, "MET")
    assert fn.ratchet_one(90, 1000, integer=True) == (900, "MET")        # no ceiling
    assert fn.ratchet_one(90, 95, integer=True) == (90, "MET")           # met, never lowered
    assert fn.ratchet_one(90, 50, integer=True) == (90, "VIOLATED")
    assert fn.ratchet_one(90, fn.UNMEASURED, integer=True) == (90, fn.UNMEASURED)
    assert fn.ratchet_one(0.5, fn.NO_INFLOW, integer=False) == (0.5, fn.UNMEASURED)
    floor: Any = None
    for v in (10, 40, 3, fn.UNMEASURED, 25, 100, 0):
        new, _ = fn.ratchet_one(floor, v, integer=True)
        assert floor is None or new >= floor
        floor = new
    assert floor == 90


def test_the_writer_never_lowers_a_floor_on_disk(tmp_path: Path) -> None:
    p = _desk(tmp_path)
    _w(p.floors, {"stages": {"CERTIFIED": {"count_floor": 2}, "LIVE": {"count_floor": 50}},
                  "transitions": {"JUDGED->CERTIFIED": {"rate_floor": 0.9}}})
    fn.write(_build(p), p)
    got = json.loads(p.floors.read_text("utf-8"))
    assert got["stages"]["LIVE"]["count_floor"] == 50                 # violated: kept
    assert got["stages"]["CERTIFIED"]["count_floor"] == 2              # met at 3: max(2, 2)
    assert got["transitions"]["JUDGED->CERTIFIED"]["rate_floor"] == 0.9
    # a writer handed a LOWER floor document still cannot lower the file
    merged = fn.merge_up(got, {"stages": {"LIVE": {"count_floor": 1}}, "transitions": {}})
    assert merged["stages"]["LIVE"]["count_floor"] == 50
    assert json.loads(p.out.read_text("utf-8"))["organ"] == fn.SEAT
    assert "_floors" not in json.loads(p.out.read_text("utf-8"))


def test_the_committed_floors_cover_every_stage_and_never_hold_a_ceiling() -> None:
    doc = json.loads(fn.FLOORS.read_text("utf-8"))
    assert set(doc["stages"]) == set(fn.STAGES)
    assert set(doc["transitions"]) == set(fn.OWNERS)
    for block in ("stages", "transitions"):
        for v in doc[block].values():
            assert not any("ceiling" in k or k.startswith("max") for k in v)


def test_the_leg_is_wired_on_the_hourly_clock() -> None:
    src = " ".join((_DESK / "research" / "hourly_cycle.py").read_text("utf-8").split())
    assert '"funnel", "research/funnel.py", "--once", "--budget-s"' in src
    assert '"funnel": fnl' in src
    from research import hourly_cycle as hc
    assert "funnel" in hc.LEG_BUDGET_SEC and "funnel" in hc.CORE_LEGS
    assert hc.LEG_DEPARTMENT.get("funnel") == "meta"
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["funnel"] == "meta"
    contracts = json.loads((_ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))
    assert contracts["legs"]["funnel"]["metric"]["organ"] == "report:FUNNEL.json"
    oc = (_ROOT / "ops" / "organ_contract.py").read_text("utf-8")
    assert '"desks/mt5/reports/FUNNEL.json", 180' in oc
    sync = (_DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/FUNNEL.json"' in sync
