"""ARCH-32: the seven principles mapped to their organs, measured, ratcheted and wired.

What these pin, each the property that decides whether the organ is real:

  * ABSENCE IS UNMEASURED, NEVER MET -- every measure on an empty tree reads UNMEASURED;
  * A PRINCIPLE WITH NO RESOLVING ORGAN IS UNENFORCED and fails the fence, and an organ the map
    names that disappears is a MISSING_ORGAN arrival;
  * each measure turns VIOLATED on the defect it exists for (a sacred constant, a LIVE row with
    no retirement path, an unanswered structural-change trigger, an optimiser that forces full
    investment, a silent judge, a relaxed gate bound, a fallen floor, a stale research consumer,
    a closed registry);
  * the queue producer turns a structural change into exactly ONE `recertify` task;
  * the ratchet: pre-existing debt passes, an arrival fails, `--require-state` fails a new
    UNMEASURED;
  * on THIS tree every principle resolves every organ, the fence is green, and the leg, the layer
    and both law-gate halves are wired.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import queue_cycle  # noqa: E402
from libs.ops.task_queue import TaskQueue  # noqa: E402
from libs.tiers import principles as P  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def _w(root: Path, rel: str, body: object) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return p


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _ledger(root: Path, rows: list[dict]) -> None:
    _w(root, P.COMPUTE_LEDGER_REL, "\n".join(json.dumps(r) for r in rows) + "\n")


# ------------------------------------------------------------------------------- the organs
def test_each_organ_kind_resolves_only_when_present(tmp_path):
    _w(tmp_path, P.HOURLY_REL, 'x = _costed("mine", mine)\n')
    _w(tmp_path, "scripts/check_x.py", "")
    _w(tmp_path, P.LAW_GATE_REL, '("check_x.py", ()),\n')
    _w(tmp_path, "scripts/check_unwired.py", "")
    _w(tmp_path, P.BOX_TASKS_REL, 'TASK name="T1" trigger="hourly" runs="a/b.py" installer=""\n')
    _w(tmp_path, "a/b.py", "")
    _w(tmp_path, "lib.py", "def here(): pass\n")
    cases = [({"kind": "leg", "name": "mine"}, True), ({"kind": "leg", "name": "gone"}, False),
             ({"kind": "fence", "name": "check_x.py"}, True),
             ({"kind": "fence", "name": "check_unwired.py"}, False),
             ({"kind": "task", "name": "T1"}, True), ({"kind": "task", "name": "T2"}, False),
             ({"kind": "code", "path": "lib.py", "token": "def here"}, True),
             ({"kind": "code", "path": "lib.py", "token": "def gone"}, False),
             ({"kind": "weird", "name": "x"}, False)]
    for organ, want in cases:
        assert P.resolve_organ(tmp_path, organ)["ok"] is want, organ


def test_a_principle_with_no_resolving_organ_is_unenforced_and_fails(tmp_path):
    pmap = {"principles": [{"id": "PX", "measure": "cash_is_allocation",
                            "organs": [{"kind": "leg", "name": "nowhere"}]}]}
    doc = P.evaluate(tmp_path, now=NOW, principle_map=pmap)
    row = doc["principles"][0]
    assert row["verdict"] == P.UNENFORCED
    assert "PX:missing_organ:leg:nowhere" in row["findings"]
    rat = P.ratchet(doc, {"findings": ["PX:missing_organ:leg:nowhere"], "unmeasured": []})
    assert not rat["ok"] and rat["unenforced"] == ["PX"], "debt never excuses an unenforced one"


def test_an_empty_tree_measures_nothing_as_met(tmp_path):
    """ABSENCE IS UNMEASURED: no measure may read MET on a tree with no artifacts."""
    pmap = P.load_map(_ROOT)
    for spec in pmap["principles"]:
        if spec["measure"] == "no_sacred":
            continue  # its code lint has nothing to scan, which is checked separately below
        m = P.MEASURES[spec["measure"]](tmp_path, spec, NOW)
        assert m["verdict"] != P.MET, spec["id"]


# ---------------------------------------------------------------------- P1 nothing is sacred
def test_the_sacred_lint_names_exemption_constants_and_nothing_else(tmp_path):
    _w(tmp_path, "desks/mt5/research/a.py", "NEVER_RETIRE_FAMILIES = {'gold'}\n"
                                            "EXEMPT = {'x': 'lint allow-list'}\n")
    _w(tmp_path, "libs/b.py", "_GAUNTLET_BYPASS: set[str] = set()\n")
    _w(tmp_path, "libs/tests/test_c.py", "SACRED = 1\n")
    _w(tmp_path, "libs/d.py", "def f():\n    NEVER_RETIRE = 1\n")  # not module level
    assert P.sacred_constants(tmp_path) == ["desks/mt5/research/a.py:NEVER_RETIRE_FAMILIES",
                                            "libs/b.py:_GAUNTLET_BYPASS"]


def test_a_live_row_needs_a_retirement_path(tmp_path):
    rows = [{"name": "auto", "status": "LIVE"},
            {"name": "po_falsifier", "status": "LIVE",
             "principal_override": {"by": "p", "reverts_if": "n>=30 and t<0"}},
            {"name": "gold_london_am_v3", "status": "LIVE", "principal_override": {"by": "p"}},
            {"name": "po_bare", "status": "LIVE", "principal_override": {"by": "p"}},
            {"name": "po_standby", "status": "STANDBY", "principal_override": {"by": "p"}}]
    _w(tmp_path, P.SLEEVES_REL, {"sleeves": rows})
    m = P.measure_no_sacred(tmp_path, {}, NOW)
    assert m["verdict"] == P.VIOLATED
    assert m["findings"] == ["P1:live_without_retirement_path:po_bare"]


def test_an_exemption_flag_on_a_registry_row_is_a_finding(tmp_path):
    _w(tmp_path, P.SLEEVES_REL, {"sleeves": [{"name": "a", "status": "LIVE"}]})
    _w(tmp_path, "desks/mt5/data/free_stack_sources.json",
       {"sources": [{"name": "reddit", "never_retire": True}, {"name": "ok", "sacred": False}]})
    m = P.measure_no_sacred(tmp_path, {}, NOW)
    assert m["findings"] == [
        "P1:exempt_row:desks/mt5/data/free_stack_sources.json:reddit:never_retire"]


# ------------------------------------------------------------ P2 change triggers relearning
def _shift(root: Path, at: datetime) -> None:
    _w(root, P.DIST_SHIFT_REL, {"at": _iso(at), "status": "ATTENTION", "n_shifted": 1,
                                "shifted": [{"symbol": "EURUSD", "verdict": "SHIFT",
                                             "sleeves": ["s1", "s2"]}]})


def test_the_producer_queues_one_recertify_per_trigger_ever(tmp_path):
    _shift(tmp_path, NOW)
    _w(tmp_path, P.DECAY_REL, {"checked_at": _iso(NOW),
                               "verdicts": {"s9": {"verdict": "FADE"}, "s8": {"verdict": "OK"}}})
    q = TaskQueue(tmp_path / P.TASK_QUEUE_REL)
    got = queue_cycle._structural_change(tmp_path, q)
    assert sorted(got["queued"]) == ["decay_fade:s9", "dist_shift:EURUSD"]
    tasks = list(q.tasks().values())
    assert {t.kind for t in tasks} == {"recertify"}
    # finished work is NOT re-queued next hour for the same detector day
    for _ in range(2):
        t = q.claim("w", kinds=("recertify",))
        q.complete(t.id, "w", why="done")
    again = queue_cycle._structural_change(tmp_path, q)
    assert again["queued"] == [] and len(q.tasks()) == 2


def test_relearning_is_violated_when_a_trigger_is_never_queued(tmp_path):
    old = NOW - timedelta(hours=5)
    _shift(tmp_path, old)
    m = P.measure_relearn_on_change(tmp_path, {}, NOW)
    assert m["findings"] == ["P2:trigger_without_rejudge:dist_shift:EURUSD"]
    queue_cycle._structural_change(tmp_path, TaskQueue(tmp_path / P.TASK_QUEUE_REL))
    m = P.measure_relearn_on_change(tmp_path, {}, NOW)
    assert m["verdict"] == P.MET and m["evidence"]["answered"] == 1


def test_a_fresh_trigger_has_a_grace_window(tmp_path):
    _shift(tmp_path, NOW - timedelta(minutes=20))
    m = P.measure_relearn_on_change(tmp_path, {}, NOW)
    assert m["verdict"] == P.MET and m["evidence"]["within_grace"]


def test_a_stale_detector_is_a_finding_only_where_the_cycle_runs(tmp_path):
    _w(tmp_path, P.DECAY_REL, {"checked_at": _iso(NOW - timedelta(days=9)), "verdicts": {}})
    m = P.measure_relearn_on_change(tmp_path, {}, NOW)
    assert m["verdict"] == P.UNMEASURED, "a stale artifact on a non-desk host says nothing"
    _ledger(tmp_path, [{"at": _iso(NOW - timedelta(minutes=5)), "run": "mine"}])
    m = P.measure_relearn_on_change(tmp_path, {}, NOW)
    assert m["findings"] == ["P2:detector_stale:decay_live"]


# --------------------------------------------------------------- P3 cash is an allocation
def test_cash_is_met_only_with_a_published_free_optimum(tmp_path):
    src = (_ROOT / P.ROBUST_ELOG_REL).read_text("utf-8")
    _w(tmp_path, P.ROBUST_ELOG_REL, src)
    assert P.measure_cash_is_allocation(tmp_path, {}, NOW)["verdict"] == P.UNMEASURED
    _w(tmp_path, P.ALLOCATION_REL, {"heat": {"total": 0.2, "free_optimum": 0.12,
                                             "hard_ceiling": 0.3}})
    m = P.measure_cash_is_allocation(tmp_path, {}, NOW)
    assert m["verdict"] == P.MET and m["evidence"]["cash_heat_at_free_optimum"] == 0.18
    _w(tmp_path, P.ALLOCATION_REL, {"heat": {"total": 0.2}})
    assert P.measure_cash_is_allocation(tmp_path, {}, NOW)["findings"] == [
        "P3:allocator_publishes_no_free_optimum"]


def test_an_optimiser_that_must_spend_everything_violates_cash(tmp_path):
    _w(tmp_path, P.ROBUST_ELOG_REL,
       "def project_capped_simplex(v, cap):\n    return v / v.sum() * cap\n")
    assert P.measure_cash_is_allocation(tmp_path, {}, NOW)["findings"] == [
        "P3:optimiser_forces_full_investment"]


# --------------------------------------------------------------- P4 research never stops
def test_research_liveness_on_a_running_host(tmp_path):
    fresh = _iso(NOW - timedelta(minutes=10))
    _ledger(tmp_path, [{"at": fresh, "run": "mine"}, {"at": fresh, "run": "external_gauntlet"}])
    assert P.measure_research_never_stops(tmp_path, {}, NOW)["verdict"] == P.MET
    _ledger(tmp_path, [{"at": fresh, "run": "mine"},
                       {"at": _iso(NOW - timedelta(hours=20)), "run": "external_gauntlet"}])
    _w(tmp_path, P.THROUGHPUT_REL, {"verdicts_per_hour": 0})
    assert P.measure_research_never_stops(tmp_path, {}, NOW)["findings"] == [
        "P4:judge_silent", "P4:zero_judging_throughput"]


def test_research_liveness_is_unmeasured_where_no_cycle_runs(tmp_path):
    _ledger(tmp_path, [{"at": _iso(NOW - timedelta(days=3)), "run": "mine"}])
    assert P.measure_research_never_stops(tmp_path, {}, NOW)["verdict"] == P.UNMEASURED


# --------------------------------------------------------- P5 validation never relaxes
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "HOME": str(root), "PATH": "/usr/bin:/bin:/usr/local/bin"})


SPEC = """gates:
  - name: deflated_sharpe
    threshold: "dsr >= {dsr}"
  - name: pbo
    threshold: "pbo < {pbo}"
"""


def test_the_gate_ratchet_reads_direction_from_the_operator(tmp_path):
    _git(tmp_path, "init", "-q")
    for dsr, pbo in ((0.95, 0.5), (0.97, 0.4)):
        _w(tmp_path, P.GATE_SPEC_REL, SPEC.format(dsr=dsr, pbo=pbo))
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "tighten")
    assert P.gate_threshold_ratchet(tmp_path)["relaxed"] == []
    _w(tmp_path, P.GATE_SPEC_REL, SPEC.format(dsr=0.95, pbo=0.45))  # both looser than best
    got = P.gate_threshold_ratchet(tmp_path)
    assert [r["bound"] for r in got["relaxed"]] == ["deflated_sharpe:threshold:dsr",
                                                    "pbo:threshold:pbo"]
    _w(tmp_path, P.GATE_SPEC_REL, SPEC.format(dsr=0.99, pbo=0.3))  # tighter is always fine
    assert P.gate_threshold_ratchet(tmp_path)["relaxed"] == []


def test_a_floor_below_its_high_water_mark_is_a_finding(tmp_path):
    _git(tmp_path, "init", "-q")
    for v in (80.0, 86.0):
        _w(tmp_path, "docs/f.json", {"high_water": {"pct": v}})
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "raise")
    floors = [{"path": "docs/f.json", "keys": ["high_water.pct"], "direction": "up"}]
    assert not P.floor_ratchet(tmp_path, floors)[0]["fell"]
    _w(tmp_path, "docs/f.json", {"high_water": {"pct": 83.0}})
    m = P.measure_validation_never_relaxes(tmp_path, {"floors": floors}, NOW)
    assert m["findings"] == ["P5:floor_fell:docs/f.json:high_water.pct"]


# --------------------------------------------------------- P6 execution teaches research
def test_fills_must_reach_a_fresh_research_consumer(tmp_path):
    spec = {"feeds": [{"artifact": "live_ledger.jsonl", "consumers": ["r/c.py"]}],
            "consumer_reports": ["desks/mt5/reports/C.json"]}
    _w(tmp_path, "r/c.py", "LEDGER = 'live_ledger.jsonl'\n")
    _w(tmp_path, P.LIVE_LEDGER_REL, json.dumps({"time": _iso(NOW - timedelta(hours=1))}) + "\n")
    assert P.measure_execution_teaches_research(tmp_path, spec, NOW)["verdict"] == P.UNMEASURED
    _w(tmp_path, "desks/mt5/reports/C.json", {"generated_utc": _iso(NOW - timedelta(days=5))})
    _ledger(tmp_path, [{"at": _iso(NOW - timedelta(minutes=5)), "run": "mine"}])
    assert P.measure_execution_teaches_research(tmp_path, spec, NOW)["findings"] == [
        "P6:research_consumers_stale"]
    _w(tmp_path, "desks/mt5/reports/C.json", {"generated_utc": _iso(NOW)})
    assert P.measure_execution_teaches_research(tmp_path, spec, NOW)["verdict"] == P.MET
    _w(tmp_path, "r/c.py", "# reads nothing\n")
    assert "P6:no_research_consumer:live_ledger.jsonl" in P.measure_execution_teaches_research(
        tmp_path, spec, NOW)["findings"]


# --------------------------------------------------------------- P7 ontology stays open
def test_a_closed_registry_is_a_finding(tmp_path):
    reg = {"path": "fam.py", "symbol": "REG", "register": "add"}
    _w(tmp_path, "fam.py", "REG: dict[str, dict] = {}\ndef add(n):\n    REG[n] = {}\n")
    assert P.registry_open(tmp_path, reg)[0]
    _w(tmp_path, "fam.py", "REG = frozenset({'a'})\ndef add(n):\n    pass\n")
    assert not P.registry_open(tmp_path, reg)[0]
    _w(tmp_path, "fam.py", "REG = {}\n")
    assert not P.registry_open(tmp_path, reg)[0], "no registration path"
    m = P.measure_ontology_open(tmp_path, {"registries": [reg]}, NOW)
    assert m["findings"] == ["P7:registry_closed:fam.py:REG"]


# ------------------------------------------------------------------------------ the ratchet
def test_the_ratchet_passes_debt_and_fails_arrivals():
    doc = {"principles": [{"id": "P1", "verdict": P.VIOLATED, "findings": ["P1:a", "P1:b"]},
                          {"id": "P2", "verdict": P.UNMEASURED, "findings": []}]}
    assert P.ratchet(doc, {"findings": ["P1:a", "P1:b"], "unmeasured": []})["ok"]
    rat = P.ratchet(doc, {"findings": ["P1:a"], "unmeasured": []})
    assert not rat["ok"] and rat["arrived"] == ["P1:b"]
    assert P.ratchet(doc, {"findings": ["P1:a", "P1:b"]}, require_state=False)["ok"]
    rat = P.ratchet(doc, {"findings": ["P1:a", "P1:b"]}, require_state=True)
    assert not rat["ok"] and rat["new_unmeasured"] == ["P2"]
    assert P.ratchet(doc, {"findings": ["P1:a", "P1:b", "P1:c"]})["healed"] == ["P1:c"]


def test_update_only_ever_shrinks_the_floor():
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_principles",
                                                  _ROOT / "scripts" / "check_principles.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    doc = {"principles": [{"id": "P1", "verdict": P.VIOLATED, "findings": ["P1:new", "P1:a"]},
                          {"id": "P2", "verdict": P.UNMEASURED, "findings": []}]}
    new = mod.shrink_floor({"findings": ["P1:a", "P1:gone"], "unmeasured": []}, doc)
    assert new["findings"] == ["P1:a"] and new["unmeasured"] == []


# ---------------------------------------------------------------- this tree, and the wiring
def test_every_principle_on_this_tree_resolves_every_organ():
    doc = P.evaluate(_ROOT)
    assert len(doc["principles"]) == 7
    for row in doc["principles"]:
        assert row["verdict"] != P.UNENFORCED, row["id"]
        assert row["missing_organs"] == [], (row["id"], row["missing_organs"])
    assert doc["caps_capital"] is False


def test_the_fence_is_green_on_this_tree():
    r = subprocess.run([sys.executable, str(_ROOT / "scripts" / "check_principles.py")],
                       capture_output=True, text=True, cwd=_ROOT, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_leg_layer_and_both_gate_halves_are_wired():
    hourly = (_ROOT / P.HOURLY_REL).read_text("utf-8")
    assert '_costed("principles", principles)' in hourly
    assert '_producer("principles", "research/principles_enforcement.py")' in hourly
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["principles"] == "meta"
    gate = (_ROOT / P.LAW_GATE_REL).read_text("utf-8")
    assert '("check_principles.py", ())' in gate
    assert '("check_principles.py", ("--require-state",))' in gate
    assert "structural_change" in queue_cycle.PRODUCERS


@pytest.mark.parametrize("name", ["NEVER_RETIRE", "SACRED_SOURCES", "GAUNTLET_BYPASS",
                                  "EXEMPT_FROM_GAUNTLET", "_GRANDFATHERED"])
def test_the_exemption_pattern_matches_the_names_it_exists_for(name):
    assert P._EXEMPTION_NAME.match(name)


@pytest.mark.parametrize("name", ["EXEMPT", "_EXEMPT_NAMES", "RETIRED_FILE", "GAUNTLET_PATH"])
def test_the_exemption_pattern_spares_ordinary_names(name):
    assert not P._EXEMPTION_NAME.match(name)
