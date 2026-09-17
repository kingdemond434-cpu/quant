"""THE WEEKLY SIMPLIFIER: five detectors, each on a planted twin whose answer is known.

Every detector here is a claim about the tree that a person will act on by deleting code, so
each one is tested against a positive AND a negative: a planted duplicate that must be found,
and a near-miss that must not be. The dead-machinery detector gets the most attention, because
it is the only one whose proposal is irreversible -- an EXEMPT module and an UNMEASURED module
must both survive it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import module_rent as mr  # noqa: E402
import simplifier as sp  # noqa: E402

NOW = "2026-09-17T12:00:00+00:00"

#: Two organs that read and write exactly the same four artifacts: the overlap positive.
TWIN = '''"""Twin {tag}."""
import json
from pathlib import Path

OUT = Path("reports") / "TWIN.json"
A = Path("data") / "alpha.json"
B = Path("data") / "beta.json"
C = Path("data") / "gamma.json"


def load_all():
    rows = []
    for p in (A, B, C):
        rows.append(p)
    return rows


def score_rows(rows):
    total = 0
    for r in rows:
        total += 1
    return total


def publish(doc):
    text = json.dumps(doc)
    OUT.write_text(text)
    return len(text)


def main(argv=None):
    return 0
'''

#: The same helper, written by three different hands: the unify positive.
HELPER = '''"""Organ {tag}."""
import json
from pathlib import Path

OUT = Path("reports") / "{tag}.json"
IN_ONE = Path("data") / "{tag}_in.json"
IN_TWO = Path("data") / "{tag}_two.json"


def _read_doc({arg}):
    raw = {arg}.read_text()
    parsed = json.loads(raw)
    return parsed


def main(argv=None):
    return 0
'''

PLAIN = '''"""Organ {tag}."""
from pathlib import Path

OUT = Path("reports") / "{tag}.json"


def main(argv=None):
    return 0
'''


def _organ(root: Path, rel: str, body: str, **fmt: Any) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.format(**fmt), encoding="utf-8")
    return p


def _write(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _rent_row(module: str, **kw: Any) -> dict[str, Any]:
    row = {"module": module, "clock": "hourly_cycle:x", "attribution": "credited",
           "compute_h_7d": 1.0, "compute_h_30d": 4.0, "candidates_30d": 20,
           "admissions_30d": 5, "survivors_30d": 1, "defects_30d": 0,
           "maintenance_commits_30d": 2, "loc": 120, "complexity": 300.0, "roi": 5.0,
           "verdict": "KEEP", "merge_with": None}
    row.update(kw)
    return row


def _cost(run: str, minute: int) -> dict[str, Any]:
    return {"at": f"2026-09-16T{minute // 60:02d}:{minute % 60:02d}:00+00:00", "run": run,
            "kind": "hourly_cycle", "outcome": "ok", "wall_s": 60.0, "cpu_s": 1.0}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A synthetic repo with one of every finding planted in it."""
    mr._IMPORT_CACHE.clear()
    _organ(tmp_path, "desks/mt5/research/twin_left.py", TWIN, tag="left")
    _organ(tmp_path, "desks/mt5/research/twin_right.py", TWIN, tag="right")
    for tag, arg in (("hel_one", "p"), ("hel_two", "path"), ("hel_three", "src")):
        _organ(tmp_path, f"desks/mt5/research/{tag}.py", HELPER, tag=tag, arg=arg)
    _organ(tmp_path, "desks/mt5/research/alpha_leg.py", TWIN, tag="alpha")
    _organ(tmp_path, "desks/mt5/research/beta_leg.py", TWIN, tag="beta")
    _organ(tmp_path, "desks/mt5/research/dormant_prospector.py", PLAIN, tag="dormant")
    _organ(tmp_path, "desks/mt5/research/check_dead_law.py", PLAIN, tag="lawcheck")
    _organ(tmp_path, "desks/mt5/research/quiet_unknown.py", PLAIN, tag="quiet")
    clock = tmp_path / "desks" / "mt5" / "research" / "hourly_cycle.py"
    clock.write_text('_producer("alpha_leg", "research/alpha_leg.py")\n'
                     '_producer("beta_leg", "research/beta_leg.py")\n', encoding="utf-8")

    dt = tmp_path / "desks" / "mt5" / "data"
    rows: list[dict[str, Any]] = []
    for i in range(4):
        rows.append(_cost("alpha_leg", i * 20))
        rows.append(_cost("beta_leg", i * 20 + 5))
    (dt / "compute_ledger.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (dt / "compute_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows),
                                             encoding="utf-8")
    _write(dt / "store_a.json", {"k1": 1, "k2": 2, "k3": 3, "k4": 4, "k5": 5})
    _write(dt / "store_b.json", {"k1": 9, "k2": 9, "k3": 9, "k4": 9, "z9": 9})
    _write(dt / "store_c.json", {"q1": 1, "q2": 2, "q3": 3, "q4": 4, "q5": 5})
    _write(tmp_path / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json", {"rows": [
        _rent_row("desks/mt5/research/dormant_prospector.py", clock="none", candidates_30d=0,
                  admissions_30d=0, survivors_30d=0, maintenance_commits_30d=0, loc=411),
        _rent_row("desks/mt5/research/check_dead_law.py", clock="none", candidates_30d=0,
                  admissions_30d=0, survivors_30d=0, maintenance_commits_30d=0, loc=222),
        _rent_row("desks/mt5/research/quiet_unknown.py", clock="none", candidates_30d=None,
                  admissions_30d=None, survivors_30d=None, maintenance_commits_30d=0, loc=333),
        _rent_row("desks/mt5/research/twin_left.py"),
    ]})
    return tmp_path


# --------------------------------------------------------------------------- overlaps
def test_overlap_finds_the_planted_twin(tree: Path) -> None:
    doc = sp.build(tree)
    pairs = {(p["a"], p["b"]) for p in doc["overlaps"]}
    assert ("desks/mt5/research/twin_left.py", "desks/mt5/research/twin_right.py") in pairs
    hit = next(p for p in doc["overlaps"]
               if p["a"].endswith("twin_left.py") and p["b"].endswith("twin_right.py"))
    assert hit["artifact_jaccard"] == pytest.approx(1.0)
    assert hit["surface_jaccard"] == pytest.approx(1.0)
    assert "twin.json" in hit["shared_artifacts"]


def test_overlap_ignores_organs_that_share_too_little_to_judge(tree: Path) -> None:
    doc = sp.build(tree)
    pairs = {frozenset((p["a"], p["b"])) for p in doc["overlaps"]}
    assert frozenset(("desks/mt5/research/hel_one.py",
                      "desks/mt5/research/dormant_prospector.py")) not in pairs


def test_overlap_threshold_is_the_declared_one(tree: Path) -> None:
    doc = sp.build(tree)
    assert doc["thresholds"]["overlap_jaccard"] == sp.OVERLAP_JACCARD == 0.5
    for p in doc["overlaps"]:
        assert max(p["artifact_jaccard"], p["surface_jaccard"]) > sp.OVERLAP_JACCARD


# --------------------------------------------------------------------------- unify
def test_unify_finds_one_helper_written_three_ways(tree: Path) -> None:
    doc = sp.build(tree)
    groups = {g["function"]: g for g in doc["unify"]}
    assert "_read_doc" in groups
    g = groups["_read_doc"]
    assert g["copies"] == 3
    assert set(g["modules"]) == {"desks/mt5/research/hel_one.py",
                                 "desks/mt5/research/hel_two.py",
                                 "desks/mt5/research/hel_three.py"}
    assert g["loc_removable"] == pytest.approx(2 * g["median_body_loc"])


def test_unify_normalises_variable_names_but_not_structure(tmp_path: Path) -> None:
    """`p` and `path` hash alike; a body with an extra statement does not."""
    a = _organ(tmp_path, "desks/mt5/research/u_a.py", HELPER, tag="u_a", arg="p")
    b = _organ(tmp_path, "desks/mt5/research/u_b.py", HELPER, tag="u_b", arg="path")
    mr._IMPORT_CACHE.clear()
    fa, fb = sp.module_facts(a), sp.module_facts(b)
    assert fa["funcs"]["_read_doc"][0] == fb["funcs"]["_read_doc"][0]
    c = tmp_path / "desks" / "mt5" / "research" / "u_c.py"
    c.write_text(HELPER.format(tag="u_c", arg="p").replace(
        "    return parsed", "    parsed['x'] = 1\n    return parsed"), encoding="utf-8")
    assert sp.module_facts(c)["funcs"]["_read_doc"][0] != fa["funcs"]["_read_doc"][0]


def test_unify_needs_more_than_two_copies(tree: Path) -> None:
    doc = sp.build(tree)
    for g in doc["unify"]:
        assert g["copies"] >= sp.MIN_COPIES + 1


def test_a_one_line_wrapper_is_not_a_helper_worth_unifying(tmp_path: Path) -> None:
    p = tmp_path / "w.py"
    p.write_text("def tiny(x):\n    return x\n", encoding="utf-8")
    assert "tiny" not in sp.module_facts(p)["funcs"]
    assert "tiny" in sp.module_facts(p)["names"]


# --------------------------------------------------------------------------- registries
def test_duplicate_registries_are_named_as_pairs(tree: Path) -> None:
    doc = sp.build(tree)
    pairs = {(p["a"], p["b"]) for p in doc["duplicate_registries"]}
    assert ("store_a.json", "store_b.json") in pairs
    assert not any("store_c.json" in (p["a"], p["b"]) for p in doc["duplicate_registries"])
    hit = next(p for p in doc["duplicate_registries"] if p["a"] == "store_a.json")
    assert hit["key_overlap"] == pytest.approx(round(4 / 6, 3))
    assert hit["key_overlap"] > sp.REGISTRY_OVERLAP


def test_an_oversized_registry_is_skipped_by_name_not_silently(tree: Path) -> None:
    big = tree / "desks" / "mt5" / "data" / "huge_store.json"
    big.write_text('{"a": "' + "x" * (sp.MAX_REGISTRY_BYTES + 10) + '"}', encoding="utf-8")
    doc = sp.build(tree)
    assert any("huge_store.json" in u for u in doc["unmeasured"])


# --------------------------------------------------------------------------- services
def test_two_legs_that_never_run_apart_and_share_an_input_are_one_service(tree: Path) -> None:
    doc = sp.build(tree)
    legs = {tuple(s["legs"]) for s in doc["services"]}
    assert ("alpha_leg", "beta_leg") in legs
    hit = next(s for s in doc["services"] if tuple(s["legs"]) == ("alpha_leg", "beta_leg"))
    assert hit["adjacent_runs"] == 4
    assert hit["share_of_first"] == pytest.approx(1.0)
    assert hit["shared_inputs"]


def test_no_compute_ledger_means_no_service_candidate_and_it_says_so(tree: Path) -> None:
    (tree / "desks" / "mt5" / "data" / "compute_ledger.jsonl").unlink()
    doc = sp.build(tree)
    assert doc["services"] == []
    assert any("compute ledger" in u and "UNMEASURED" in u for u in doc["unmeasured"])


# --------------------------------------------------------------------------- dead machinery
def test_dead_is_unwired_zero_downstream_and_untouched(tree: Path) -> None:
    doc = sp.build(tree)
    dead = {d["module"] for d in doc["dead"]}
    assert "desks/mt5/research/dormant_prospector.py" in dead
    assert "desks/mt5/research/twin_left.py" not in dead, "it is on a clock"


def test_dead_never_includes_an_exempt_module(tree: Path) -> None:
    doc = sp.build(tree)
    dead = {d["module"] for d in doc["dead"]}
    assert "desks/mt5/research/check_dead_law.py" not in dead
    assert mr.exempt_reason("desks/mt5/research/check_dead_law.py", {}, ()) is not None


def test_dead_never_includes_an_unmeasured_module(tree: Path) -> None:
    doc = sp.build(tree)
    dead = {d["module"] for d in doc["dead"]}
    assert "desks/mt5/research/quiet_unknown.py" not in dead, "UNMEASURED is not dead"


def test_a_module_touched_in_the_last_thirty_days_is_not_dead(tree: Path) -> None:
    rp = tree / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json"
    doc = json.loads(rp.read_text(encoding="utf-8"))
    for r in doc["rows"]:
        if r["module"].endswith("dormant_prospector.py"):
            r["maintenance_commits_30d"] = 4
    _write(rp, doc)
    assert sp.build(tree)["dead"] == []


def test_no_rent_report_proposes_no_deletion_at_all(tree: Path) -> None:
    (tree / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json").unlink()
    doc = sp.build(tree)
    assert doc["dead"] == [] and doc["capability_at_risk"] == []
    assert any("module rent" in u for u in doc["unmeasured"])


def test_capability_at_risk_names_the_consumers_of_a_proposed_deletion(tmp_path: Path) -> None:
    mr._IMPORT_CACHE.clear()
    _organ(tmp_path, "desks/mt5/research/dormant_prospector.py", TWIN, tag="dormant")
    _organ(tmp_path, "desks/mt5/research/live_reader.py", TWIN, tag="reader")
    _write(tmp_path / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json", {"rows": [
        _rent_row("desks/mt5/research/dormant_prospector.py", clock="none", candidates_30d=0,
                  admissions_30d=0, survivors_30d=0, maintenance_commits_30d=0, loc=411)]})
    doc = sp.build(tmp_path)
    assert [d["module"] for d in doc["dead"]] == ["desks/mt5/research/dormant_prospector.py"]
    risk = doc["capability_at_risk"]
    assert risk and "desks/mt5/research/live_reader.py" in risk[0]["consumers"]
    assert doc["dead"][0]["n_consumers"] == 1


# --------------------------------------------------------------------------- the report
def test_a_widely_shared_artifact_is_not_evidence_of_a_consumer(tmp_path: Path) -> None:
    """Six organs naming `universe.json` are strangers, not readers of each other."""
    mr._IMPORT_CACHE.clear()
    _organ(tmp_path, "desks/mt5/research/dormant_prospector.py", TWIN, tag="dormant")
    for i in range(sp.CONSUMER_KEY_MAX_SHARERS + 1):
        _organ(tmp_path, f"desks/mt5/research/stranger_{i}.py", TWIN, tag=f"s{i}")
    _write(tmp_path / "desks" / "mt5" / "reports" / "MODULE_RENT_RESEARCH.json", {"rows": [
        _rent_row("desks/mt5/research/dormant_prospector.py", clock="none", candidates_30d=0,
                  admissions_30d=0, survivors_30d=0, maintenance_commits_30d=0, loc=411)]})
    doc = sp.build(tmp_path)
    assert doc["dead"][0]["n_consumers"] == 0
    assert doc["capability_at_risk"] == []


def test_loc_removable_counts_dead_plus_duplicate_helpers_only(tree: Path) -> None:
    doc = sp.build(tree)
    expect = (sum(int(d["loc"]) for d in doc["dead"])
              + sum(int(g["loc_removable"]) for g in doc["unify"]))
    assert doc["loc_removable"] == expect
    assert "the saving from a MERGE is UNMEASURED" in doc["loc_removable_basis"]


def test_the_plan_names_every_kind_of_proposal(tree: Path) -> None:
    plan = sp.build(tree)["consolidation_plan"]
    joined = " | ".join(plan)
    for verb in ("UNIFY", "MERGE", "ONE REGISTRY", "ONE SERVICE", "DELETE"):
        assert verb in joined, verb


def test_dry_run_writes_nothing_and_a_plain_run_writes_the_artifact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = {"at": NOW, "n_modules": 3, "elapsed_s": 0.1, "loc_removable": 12,
           "counts": {"overlaps": 0, "unify": 0, "duplicate_registries": 0, "services": 0,
                      "dead": 0},
           "consolidation_plan": ["DELETE x.py (12 LOC) -- dead"], "unmeasured": []}
    out = tmp_path / "SIMPLIFIER.json"
    monkeypatch.setattr(sp, "OUT", out)
    monkeypatch.setattr(sp, "build", lambda **kw: doc)
    assert sp.main(["--dry-run"]) == 0
    assert not out.exists()
    assert sp.main([]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["loc_removable"] == 12


def test_the_report_carries_its_rule(tree: Path) -> None:
    doc = sp.build(tree)
    assert doc["rule"] == ("capability up while complexity is controlled; the simplifier "
                           "proposes, a session decides")
    assert set(doc["counts"]) == {"overlaps", "unify", "duplicate_registries", "services", "dead"}
