"""MODULE RENT: what it measures per module, the ROI formula, and each verdict by its own rule.

Every input is synthetic and every path lands inside `tmp_path`. The organ reads eight real
artifacts on the box and all eight may be absent, so the tests that matter most are the ones
proving an absent input produces UNMEASURED rather than a clean zero -- a zero is a verdict about
the module, UNMEASURED is a verdict about the desk, and the two must never be the same row.

`git` is stubbed at `_git_name_only` (the ONE seam the organ has for it) and the registry is
pointed at a tmp sqlite with `registry.set_path` + a monkeypatched `BACKUP`, so nothing here
touches the real tree, the real history or the real registry.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import module_rent as mr  # noqa: E402

from libs.moat import registry as R  # noqa: E402

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

#: A synthetic organ. `main()` makes it an organ; the PRODUCER_MARKS token makes it a module the
#: desk could ever credit with downstream research.
ORGAN = '''"""A synthetic organ."""
import json
from pathlib import Path

OUT = Path("reports") / "{out}"
IN = Path("data") / "{inp}"


def helper(a, b):
    total = a + b
    rows = [total]
    return rows


def main(argv=None):
    """writes a hypothesis_graph candidate"""
    print(json.dumps({{"out": str(OUT), "in": str(IN)}}))
    return 0
'''

#: An organ with no candidate-minting vocabulary at all: an allocator, a cost model, a recorder.
QUIET = '''"""A synthetic organ that mints nothing."""
from pathlib import Path

OUT = Path("reports") / "{out}"


def main(argv=None):
    return 0
'''


def _organ(root: Path, rel: str, out: str = "A.json", inp: str = "b.json",
           body: str = ORGAN) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.format(out=out, inp=inp), encoding="utf-8")
    return p


def _graph(root: Path, rows: list[dict[str, Any]]) -> None:
    p = root / "desks" / "mt5" / "data" / "hypothesis_graph.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _row(source: str, family: str, symbol: str, fate: str = "BORN", days: float = 1.0
         ) -> dict[str, Any]:
    return {"id": f"{source}:{family}:{symbol}:{fate}:{days}", "source": source, "family": family,
            "symbol": symbol, "fate": fate,
            "gates": {"g": 1} if fate != "BORN" else {},
            "at": (NOW - timedelta(days=days)).isoformat()}


def _ledger(root: Path, rows: list[dict[str, Any]]) -> None:
    p = root / "desks" / "mt5" / "data" / "compute_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _cost(run: str, wall_s: float, days: float = 1.0) -> dict[str, Any]:
    return {"at": (NOW - timedelta(days=days)).isoformat(), "run": run, "kind": "hourly_cycle",
            "outcome": "ok", "wall_s": wall_s, "cpu_s": wall_s}


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole synthetic repo: four organs, a clock that names two of them, and a tmp registry."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "registry.sqlite")
    mr._IMPORT_CACHE.clear()
    _organ(tmp_path, "desks/mt5/research/zeta_prospector.py", "ZETA.json", "zeta_in.json")
    _organ(tmp_path, "desks/mt5/research/kappa_prospector.py", "KAPPA.json", "kappa_in.json")
    _organ(tmp_path, "desks/mt5/research/check_zeta_law.py", "ZLAW.json", "zeta_in.json")
    _organ(tmp_path, "desks/mt5/research/quiet_sizer.py", "QUIET.json", body=QUIET)
    clock = tmp_path / "desks" / "mt5" / "research" / "hourly_cycle.py"
    # A clock names a PATH (or a module), never a leg's display name -- see `clock_index`.
    clock.write_text("\n".join(
        f'_costed("{s}", lambda: _producer("{s}", "research/{s}.py"))'
        for s in ("zeta_prospector", "kappa_prospector", "check_zeta_law", "quiet_sizer")),
        encoding="utf-8")
    monkeypatch.setattr(mr, "_git_name_only", lambda root, budget: "")
    yield tmp_path
    R.set_path(None)


# --------------------------------------------------------------------------- the census
def test_census_finds_organs_and_reads_their_clock(tree: Path) -> None:
    cen = mr.census(tree)
    assert "desks/mt5/research/zeta_prospector.py" in cen
    assert cen["desks/mt5/research/zeta_prospector.py"]["clock"] != "none"
    _organ(tree, "desks/mt5/research/orphan_prospector.py", "ORPH.json")
    mr._IMPORT_CACHE.clear()
    cen = mr.census(tree)
    assert cen["desks/mt5/research/orphan_prospector.py"]["clock"] == "none"


def test_a_legs_display_name_is_not_a_clock(tree: Path) -> None:
    """The bug this pins, found on the real tree the hour this organ landed: `daily_cycle` holds
    the tuple `("module_rent", _module_rent)` for a leg that runs libs/ops/module_rent.py, and a
    word-token clock index read desks/mt5/research/module_rent.py as SCHEDULED -- and therefore
    as a RETIRE_CANDIDATE -- while nothing ran it."""
    _organ(tree, "desks/mt5/research/named_only.py", "NAMED.json")
    clock = tree / "desks" / "mt5" / "research" / "daily_cycle.py"
    clock.write_text('LEGS = [("named_only", _named_only)]\n', encoding="utf-8")
    mr._IMPORT_CACHE.clear()
    assert mr.census(tree)["desks/mt5/research/named_only.py"]["clock"] == "none"


def test_a_shared_basename_in_a_clock_schedules_neither_file(tree: Path) -> None:
    _organ(tree, "desks/mt5/research/twin_name.py", "T1.json")
    (tree / "libs" / "ops").mkdir(parents=True, exist_ok=True)
    (tree / "libs" / "ops" / "twin_name.py").write_text("def main():\n    return 0\n",
                                                        encoding="utf-8")
    ops = tree / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    (ops / "run.sh").write_text("python libs/ops/twin_name.py\n", encoding="utf-8")
    mr._IMPORT_CACHE.clear()
    cen = mr.census(tree)
    assert cen["desks/mt5/research/twin_name.py"]["clock"] == "none"


def test_an_organ_a_clocked_organ_imports_runs_on_that_clock(tree: Path) -> None:
    helper = tree / "desks" / "mt5" / "research" / "helper_prospector.py"
    helper.write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
    caller = tree / "desks" / "mt5" / "research" / "zeta_prospector.py"
    caller.write_text("import helper_prospector\n\n\ndef main(argv=None):\n    return 0\n",
                      encoding="utf-8")
    mr._IMPORT_CACHE.clear()
    cen = mr.census(tree)
    assert cen["desks/mt5/research/helper_prospector.py"]["clock"].startswith("imported by")


def test_path_suffixes_never_reduce_to_a_bare_basename() -> None:
    assert mr.path_suffixes("desks/mt5/research/x.py") == {
        "research/x.py", "mt5/research/x.py", "desks/mt5/research/x.py"}
    assert mr.path_suffixes("x.py") == set()


def test_a_file_without_main_is_not_an_organ(tree: Path) -> None:
    p = tree / "desks" / "mt5" / "research" / "not_an_organ.py"
    p.write_text("def helper():\n    return 1\n", encoding="utf-8")
    assert "desks/mt5/research/not_an_organ.py" not in mr.organ_files(tree)


# --------------------------------------------------------------------------- measurement
def test_measures_candidates_novel_admissions_and_survivors_per_module(tree: Path) -> None:
    _graph(tree, [
        _row("miner:zeta_prospector", "carry", "EURUSD", "CERTIFIED"),
        _row("miner:zeta_prospector", "carry", "EURUSD", "FAILED"),     # same cell: not novel
        _row("miner:zeta_prospector", "breakout", "XAUUSD", "BORN"),    # new cell: novel
        _row("miner:kappa_prospector", "carry", "EURUSD", "BORN"),      # cell already occupied
    ])
    _ledger(tree, [_cost("zeta_prospector", 3600.0)])
    doc = mr.build(tree, now=NOW)
    by = {r["module"]: r for r in doc["rows"]}
    z = by["desks/mt5/research/zeta_prospector.py"]
    assert z["candidates_30d"] == 3
    assert z["survivors_30d"] == 1
    assert z["admissions_30d"] == 2                 # CERTIFIED + FAILED
    assert z["novel_mechanisms_30d"] == 2           # carry|EURUSD and breakout|XAUUSD
    assert z["compute_h_7d"] == pytest.approx(1.0)
    k = by["desks/mt5/research/kappa_prospector.py"]
    assert k["candidates_30d"] == 1 and k["novel_mechanisms_30d"] == 0


def test_a_seven_day_window_is_not_the_thirty_day_window(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD", days=1),
                  _row("miner:zeta_prospector", "carry", "GBPUSD", days=20)])
    _ledger(tree, [_cost("zeta_prospector", 3600.0, days=1),
                   _cost("zeta_prospector", 7200.0, days=20)])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    z = by["desks/mt5/research/zeta_prospector.py"]
    assert z["candidates_7d"] == 1 and z["candidates_30d"] == 2
    assert z["compute_h_7d"] == pytest.approx(1.0)
    assert z["compute_h_30d"] == pytest.approx(3.0)


def test_compute_is_unmeasured_for_an_organ_that_is_not_a_leg(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    _ledger(tree, [_cost("zeta_prospector", 3600.0)])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    assert by["desks/mt5/research/kappa_prospector.py"]["compute_h_7d"] is None


def test_defects_are_read_from_logs_and_the_stall_watch(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    logs = tree / "desks" / "mt5" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "hourly.log").write_text("LEG FAILED zeta_prospector: boom\nall well\n",
                                     encoding="utf-8")
    stall = tree / "desks" / "mt5" / "data" / "stall_watch.json"
    stall.write_text(json.dumps({"actions": ["STACKED heal for zeta_prospector"]}),
                     encoding="utf-8")
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    assert by["desks/mt5/research/zeta_prospector.py"]["defects_30d"] == 2
    assert by["desks/mt5/research/kappa_prospector.py"]["defects_30d"] == 0


def test_maintenance_comes_from_one_stubbed_git_call(tree: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def _stub(root: Path, budget: float) -> str:
        calls.append(root)
        return ("desks/mt5/research/zeta_prospector.py\n"
                "desks/mt5/research/zeta_prospector.py\n"
                "desks/mt5/research/kappa_prospector.py\n")

    monkeypatch.setattr(mr, "_git_name_only", _stub)
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    assert len(calls) == 1, "one bounded git call for the whole census, never one per module"
    assert by["desks/mt5/research/zeta_prospector.py"]["maintenance_commits_30d"] == 2
    assert by["desks/mt5/research/kappa_prospector.py"]["maintenance_commits_30d"] == 1


def test_git_unavailable_reads_unmeasured_not_zero(tree: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_git_name_only", lambda root, budget: None)
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    doc = mr.build(tree, now=NOW)
    by = {r["module"]: r for r in doc["rows"]}
    assert by["desks/mt5/research/zeta_prospector.py"]["maintenance_commits_30d"] is None
    assert any("maintenance" in u for u in doc["unmeasured"])


def test_the_registry_credits_a_generator_the_graph_never_named(tree: Path) -> None:
    R.generator_yield_update("kappa_prospector", generated=40, judged=20, survivors=2,
                             delta_n_eff=0.5)
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    k = by["desks/mt5/research/kappa_prospector.py"]
    assert k["candidates_30d"] == 40 and k["survivors_30d"] == 2
    assert k["delta_n_eff"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- the ROI formula
def test_roi_is_the_declared_formula() -> None:
    useful = {"survivors": 2.0, "admissions": 5.0, "novel_mechanisms": 3.0, "candidates": 100.0}
    cost = {"compute_h": 2.0, "maintenance": 3.0, "complexity": 1000.0}
    # (2*10 + 5*1 + 3*3 + 100*0.1) / (2 + 3 + 1) = 44 / 6
    assert mr.roi(useful, cost) == pytest.approx(44.0 / 6.0)


def test_roi_never_divides_by_zero() -> None:
    assert mr.roi({"survivors": 1.0}, {}) == pytest.approx(10.0 / mr.MIN_COST)


def test_complexity_counts_loc_and_fan(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    z = by["desks/mt5/research/zeta_prospector.py"]
    assert z["complexity"] == pytest.approx(z["loc"] + mr.COMPLEXITY_FAN_WEIGHT * z["fan"])


# --------------------------------------------------------------------------- verdicts by rule
def _verdicts(doc: dict[str, Any]) -> dict[str, str]:
    return {r["module"]: r["verdict"] for r in doc["rows"]}


def test_retire_candidate_needs_zero_downstream_a_clock_and_no_exemption(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD", "CERTIFIED")])
    doc = mr.build(tree, now=NOW)
    v = _verdicts(doc)
    assert v["desks/mt5/research/kappa_prospector.py"] == "RETIRE_CANDIDATE"
    assert v["desks/mt5/research/zeta_prospector.py"] != "RETIRE_CANDIDATE"


def test_an_unwired_organ_is_never_a_retire_candidate(tree: Path) -> None:
    _organ(tree, "desks/mt5/research/orphan_prospector.py", "ORPH.json")
    mr._IMPORT_CACHE.clear()
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    doc = mr.build(tree, now=NOW)
    by = {r["module"]: r for r in doc["rows"]}
    o = by["desks/mt5/research/orphan_prospector.py"]
    assert o["clock"] == "none" and o["verdict"] != "RETIRE_CANDIDATE"


def test_an_exempt_module_is_never_a_retire_candidate(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    doc = mr.build(tree, now=NOW)
    by = {r["module"]: r for r in doc["rows"]}
    law = by["desks/mt5/research/check_zeta_law.py"]
    assert law["exempt_why"], "a check_ organ is governance and declares its reason"
    assert law["verdict"] != "RETIRE_CANDIDATE"


def test_every_exempt_token_carries_a_reason() -> None:
    assert all(isinstance(v, str) and v.strip() for v in mr.EXEMPT_TOKENS.values())
    assert mr.exempt_reason("desks/mt5/research/publish_state.py", {}, ()) is not None
    assert mr.exempt_reason("desks/mt5/research/zeta_prospector.py", {}, ()) is None


def test_merge_names_the_pair() -> None:
    rows = {
        "a.py": {"keys": {"x.json", "y.json", "z.json"}, "imports": {"json", "os", "re"}},
        "b.py": {"keys": {"x.json", "y.json", "z.json"}, "imports": {"json", "os", "re"}},
        "c.py": {"keys": {"q.json", "r.json", "s.json"}, "imports": set()},
    }
    pairs = mr.merge_pairs(rows)
    assert [(p["a"], p["b"]) for p in pairs] == [("a.py", "b.py")]
    assert pairs[0]["jaccard"] == pytest.approx(1.0)


def test_merge_ignores_a_thin_coincidental_overlap() -> None:
    rows = {"a.py": {"keys": {"universe.json", "bars.json"}, "imports": set()},
            "b.py": {"keys": {"universe.json", "bars.json"}, "imports": set()}}
    assert mr.merge_pairs(rows) == [], "two keys is not evidence of a duplicate organ"


def test_merge_by_shared_imports_needs_shared_outputs_too() -> None:
    rows = {"a.py": {"keys": {"x.json", "y.json", "z.json"}, "imports": {"np", "json", "os"}},
            "b.py": {"keys": {"x.json", "y.json", "w.json"}, "imports": {"np", "json", "os"}}}
    pairs = mr.merge_pairs(rows)
    assert len(pairs) == 1 and "shared imports" in pairs[0]["why"]


def test_reduce_is_the_expensive_half_of_the_unproductive_half() -> None:
    cheap = {"module": "cheap.py", "clock": "leg", "roi": 0.1, "compute_h_30d": 0.1,
             "candidates_30d": 1, "admissions_30d": 0, "survivors_30d": 0, "attribution": "cr"}
    dear = {**cheap, "module": "dear.py", "compute_h_30d": 50.0}
    assert mr._verdict(dear, 1.0, 1.0)[0] == "REDUCE"
    assert mr._verdict(cheap, 1.0, 1.0)[0] == "KEEP"
    good = {**cheap, "roi": 9.0}
    assert mr._verdict(good, 1.0, 1.0)[0] == "KEEP"


def test_reduce_suggests_a_longer_cadence() -> None:
    dear = {"module": "d.py", "clock": "leg", "roi": 0.1, "compute_h_30d": 50.0,
            "candidates_30d": 1, "admissions_30d": 0, "survivors_30d": 0, "attribution": "cr"}
    assert "cadence" in mr._verdict(dear, 1.0, 1.0)[1]


# --------------------------------------------------------------------------- UNMEASURED
def test_an_absent_graph_and_an_empty_registry_read_unmeasured_not_zero(tree: Path) -> None:
    doc = mr.build(tree, now=NOW)
    assert all(r["roi"] is None for r in doc["rows"])
    assert set(doc["by_verdict"]) == {"UNMEASURED"}
    assert doc["median_roi"] is None
    assert any("hypothesis_graph" in u for u in doc["unmeasured"])


def test_a_module_with_no_attribution_channel_is_unmeasured_not_zero(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    by = {r["module"]: r for r in mr.build(tree, now=NOW)["rows"]}
    quiet = by["desks/mt5/research/quiet_sizer.py"]
    assert quiet["attribution"] == "none"
    assert quiet["roi"] is None and quiet["verdict"] == "UNMEASURED"
    assert "UNMEASURED, not zero" in quiet["why"]


def test_the_unmeasured_block_counts_the_attribution_gap(tree: Path) -> None:
    _graph(tree, [_row("miner:zeta_prospector", "carry", "EURUSD")])
    doc = mr.build(tree, now=NOW)
    assert any("no channel that could ever credit them" in u for u in doc["unmeasured"])


# --------------------------------------------------------------------------- the artifacts
def test_history_appends_once_per_module_per_day(tmp_path: Path) -> None:
    led = tmp_path / "module_rent_research.jsonl"
    doc = {"at": "2026-09-17T12:00:00+00:00",
           "rows": [{"module": "a.py", "clock": "leg", "roi": 1.0, "verdict": "KEEP",
                     "compute_h_7d": 0.5, "candidates_30d": 3, "survivors_30d": 0, "loc": 10},
                    {"module": "b.py", "clock": "none", "roi": None, "verdict": "UNMEASURED",
                     "compute_h_7d": None, "candidates_30d": None, "survivors_30d": None,
                     "loc": 20}]}
    assert mr.append_history(doc, led) == 2
    assert mr.append_history(doc, led) == 0, "the same day is written once, never twice"
    rows = [json.loads(ln) for ln in led.read_text(encoding="utf-8").splitlines()]
    assert [r["module"] for r in rows] == ["a.py", "b.py"]
    assert rows[0]["day"] == "2026-09-17" and rows[1]["roi"] is None
    doc2 = {**doc, "at": "2026-09-18T12:00:00+00:00"}
    assert mr.append_history(doc2, led) == 2


def test_dry_run_writes_nothing_and_a_plain_run_writes_both(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    doc = {"at": "2026-09-17T12:00:00+00:00", "n_modules": 1, "elapsed_s": 0.1,
           "median_roi": 1.0, "by_verdict": {"KEEP": 1}, "unmeasured": [],
           "rows": [{"module": "a.py", "clock": "leg", "roi": 1.0, "verdict": "KEEP", "why": "ok",
                     "compute_h_7d": 0.5, "candidates_30d": 3, "survivors_30d": 0, "loc": 10}]}
    out, led = tmp_path / "MODULE_RENT_RESEARCH.json", tmp_path / "rent.jsonl"
    monkeypatch.setattr(mr, "OUT", out)
    monkeypatch.setattr(mr, "LEDGER", led)
    monkeypatch.setattr(mr, "build", lambda **kw: doc)
    assert mr.main(["--dry-run"]) == 0
    assert not out.exists() and not led.exists()
    assert mr.main([]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["n_modules"] == 1
    assert len(led.read_text(encoding="utf-8").splitlines()) == 1


def test_the_report_carries_its_rule_and_its_formula(tree: Path) -> None:
    doc = mr.build(tree, now=NOW)
    assert "every module pays rent in measured downstream research" in doc["rule"]
    assert "never silently" in doc["rule"]
    assert doc["formula"].startswith("ROI =")
    assert doc["weights"] == mr.WEIGHTS


def test_the_artifact_paths_do_not_collide_with_the_rail_rent_ledger() -> None:
    """`libs/ops/module_rent.py` owns MODULE_RENT.json and data/module_rent.jsonl -- they are
    declared as its writes in libs/ops/capability_graph.py and read by
    scripts/check_acceptance_properties.py. One artifact, one producer."""
    assert mr.OUT.name == "MODULE_RENT_RESEARCH.json"
    assert mr.LEDGER.name == "module_rent_research.jsonl"
    assert mr.OUT != mr.DESK / "reports" / "MODULE_RENT.json"
