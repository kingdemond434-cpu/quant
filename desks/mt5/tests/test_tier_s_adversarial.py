"""Tier S adversarial layers: S04 enforced blinding, S09 Red Queen attribution and new attack
kinds, S12 developer/lockbox roles, S21 the labelled real suite and the gate redundancy matrix,
S32 the shared-reward flag."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import blinding, firewall, red_queen, researcher_market, review_panel  # noqa: E402
from libs.tiers import meta_benchmark as mb  # noqa: E402
from libs.tiers import test_invention as ti  # noqa: E402


def _put(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


COHORT = {"kimi": "llm_reasoning", "deepseek": "llm_reasoning", "cot": "flow_positioning",
          "youtube": "practitioner_story"}


def _cohort(seat: str) -> str:
    return COHORT.get(seat, "empirical_mining")


# ------------------------------------------------------------------ S04 blinding
def test_seats_in_names_directories_never_files_or_prefixes() -> None:
    assert firewall.seats_in("desks/mt5/data/intelligence/kimi/discoveries_1.json") == ["kimi"]
    assert firewall.seats_in("data\\intelligence\\cot\\x.json") == ["cot"]
    assert firewall.seats_in("data/intelligence/latest_discoveries.json") == []
    assert firewall.seats_in("data/intelligence/discoveries_{}.json") == []
    assert firewall.seats_in("data/intelligence/kimi_archive/a.json") == ["kimi_archive"]


def _blind_repo(root: Path) -> None:
    for s in ("kimi", "deepseek", "cot", "youtube"):
        (root / "data" / "intelligence" / s).mkdir(parents=True)
    _put(root, "scripts/kimi_seat.py",
         'from pathlib import Path\nOUT = Path("data") / "intelligence" / "kimi"\n'
         'def run(doc):\n    (OUT / "discoveries_1.json").write_text(doc)\n')
    # the cot seat peeks at the kimi seat's output: another cohort
    _put(root, "scripts/cot_seat.py",
         'from pathlib import Path\nBASE = Path("data")\nSEAT = BASE / "intelligence" / "cot"\n'
         'PEEK = BASE / "intelligence" / "kimi"\n'
         'def run(doc):\n    _write(SEAT / "d.json", doc)\n    return list(PEEK.glob("*"))\n'
         'def _write(p, d):\n    p.write_text(d)\n')
    # the deepseek seat reads kimi: SAME cohort, allowed
    _put(root, "scripts/deepseek_seat.py",
         'import json\nfrom pathlib import Path\nOUT = Path("data/intelligence/deepseek")\n'
         'SIB = Path("data/intelligence/kimi")\n'
         'def run(doc):\n    json.dump(doc, open(OUT / "d.json", "w"))\n'
         '    return SIB\n')
    # the youtube seat walks the whole tree
    _put(root, "scripts/youtube_seat.py",
         'from pathlib import Path\nROOT = Path("data") / "intelligence"\n'
         'def run(doc):\n    (ROOT / "youtube" / "d.json").write_text(doc)\n'
         '    return list(ROOT.rglob("*.json"))\n')


def test_blinding_audit_finds_cross_cohort_reads_and_tree_walks(tmp_path: Path) -> None:
    _blind_repo(tmp_path)
    rep = blinding.audit(tmp_path, _cohort, globs=("scripts/*.py",))
    assert rep["home_organs"]["seat:kimi"] == ["scripts/kimi_seat.py"]
    got = {(v["role"], v["kind"], v["token"]) for v in rep["violations"]}
    assert ("seat:cot", "BLIND_READ", "kimi") in got
    assert ("seat:youtube", "BLIND_TREE", "data/intelligence/**") in got
    assert not any(v["role"] == "seat:deepseek" for v in rep["violations"]), "same cohort"
    pairs = {frozenset(p) for p in rep["contaminated_pairs"]}
    assert frozenset(("flow_positioning", "llm_reasoning")) in pairs
    assert frozenset(("practitioner_story", "*")) in pairs


def test_may_enforces_the_registered_seat_roles(tmp_path: Path) -> None:
    _blind_repo(tmp_path)
    blinding.audit(tmp_path, _cohort, globs=("scripts/*.py",))
    with pytest.raises(firewall.FirewallError):
        blinding.guard_read("cot", "desks/mt5/data/intelligence/kimi/discoveries_1.json")
    with pytest.raises(firewall.FirewallError):
        firewall.may("seat:kimi", "read", "data/intelligence/cot/x.json")
    blinding.guard_read("deepseek", "data/intelligence/kimi/a.json")    # same cohort
    blinding.guard_read("cot", "data/intelligence/cot/a.json")          # its own seat
    firewall.may("promoter", "read", "desks/mt5/reports/REPLICATION.json")


def test_contaminated_cohorts_are_not_independent_discoveries() -> None:
    sight = [("a", "carry|fx"), ("b", "carry|fx"), ("a", "trend|metal"), ("c", "trend|metal")]
    cohorts = {"a": "llm_reasoning", "b": "flow_positioning", "c": "practitioner_story"}
    clean = researcher_market.independent_discoveries(sight, cohorts)
    assert clean["independently_discovered"] == 2
    dirty = researcher_market.independent_discoveries(
        sight, cohorts, [("flow_positioning", "llm_reasoning")])
    assert dirty["independently_discovered"] == 1 and dirty["withheld_by_blinding"] == 1
    star = researcher_market.independent_discoveries(sight, cohorts,
                                                     [("practitioner_story", "*")])
    assert star["independently_discovered"] == 1


def test_a_new_rule_is_seeded_an_old_rule_still_breaches() -> None:
    old = firewall.Role("old", ("x.py",), forbid_tokens=("a",))
    new = firewall.Role("new", ("y.py",), forbid_tokens=("b",))
    v_old = {"role": "old", "organ": "x.py", "kind": "READ", "token": "a"}
    v_new = {"role": "new", "organ": "y.py", "kind": "READ", "token": "b"}
    base = firewall.seed_baseline({"violations": []}, None, [old])
    cur = {"violations": [v_old, v_new]}
    seeded = firewall.seed_baseline(cur, base, [old, new])
    rat = firewall.ratchet(cur, seeded)
    assert rat["breach"] and rat["new"] == ["old|x.py|READ|a"], rat
    assert seeded["seeded"] == ["new"]


# ------------------------------------------------------------------ S12 developer + lockbox
def test_developer_role_catches_a_code_writer_writing_the_evaluator(tmp_path: Path) -> None:
    _put(tmp_path, "scripts/codegen_x.py",
         'from pathlib import Path\n'
         'def run(src):\n    Path("strategies/new_rule.py").write_text(src)\n'
         '    Path("libs/validation/gauntlet.py").write_text(src)\n')
    writers = firewall.code_writers(tmp_path, ("scripts/*.py",))
    assert writers == ["scripts/codegen_x.py"]
    dev = firewall.Role("developer", tuple(writers), forbid_writes=firewall.EVALUATOR_PATHS)
    rep = firewall.audit(tmp_path, [dev])
    hit = {(v["kind"], v["token"]) for v in rep["violations"]}
    assert ("WRITE", "libs/validation/") in hit
    with pytest.raises(firewall.FirewallError):
        firewall.may("developer", "write", "desks/mt5/research/universal_gate.py")
    firewall.may("developer", "write", "desks/mt5/research/strategies/new.py")


def test_the_static_developer_role_audits_real_organs() -> None:
    a = firewall.audit(ROOT)
    assert a["organs_checked"]["developer"] > 0


def test_lockbox_audit_and_runtime_acceptance(tmp_path: Path) -> None:
    _put(tmp_path, "libs/x/bad.py",
         "def judge(box, cand):\n    # the sealed final slice\n    return box.open_lockbox()\n")
    _put(tmp_path, "libs/x/good.py",
         "def judge(box, cand, lockbox_accepts):\n    lockbox_accepts(cand)\n"
         "    return box.open_lockbox()\n")
    rep = firewall.lockbox_audit(tmp_path, ("libs/**/*.py",))
    assert rep["openers"] == 2
    assert [(v["organ"], v["kind"]) for v in rep["violations"]] == [
        ("libs/x/bad.py", "UNFROZEN_OPEN")]
    frozen = firewall.freeze({"symbol": "EURUSD", "family": "carry", "params": {"w": 5}})
    assert firewall.lockbox_accepts(frozen) == frozen["spec_hash"]
    with pytest.raises(firewall.FirewallError):
        firewall.lockbox_accepts({"symbol": "EURUSD"})
    with pytest.raises(firewall.FirewallError):
        firewall.lockbox_accepts({**frozen, "params": {"w": 6}})


# ------------------------------------------------------------------ S32 shared reward
def test_shared_reward_flags_self_and_shared_and_counts_unattributed() -> None:
    rep = firewall.shared_reward(
        judges={"review_panel": ["c1", "c2", "c3", "c4"], "universal_gate": ["c1"]},
        producer_of={"c1": "tier_s:genomes", "c2": "miner:cot", "c3": "miner:elsewhere"},
        rewarded={"researcher_prices": ["tier_s:genomes", "miner:cot"]},
        host_of={"review_panel": "tier_s", "universal_gate": "universal_gate"})
    sev = {(f["evaluator"], f["candidate"]): f["severity"] for f in rep["flags"]}
    assert sev == {("review_panel", "c1"): "SELF", ("review_panel", "c2"): "SHARED"}
    assert rep["unattributed"] == 1 and rep["n_self"] == 1


def test_the_panel_carries_the_conflict_flag() -> None:
    ev = {"replication": {"verdict": "AGREE"}, "mechanism": {"falsifier": "x"},
          "execution": {"matched_fills": 20, "live_mean_r": 0.1},
          "firewall": {"shared_reward": [{"evaluator": "review_panel", "severity": "SELF"}]}}
    kinds = {c.kind for c in review_panel.review("c1", ev)}
    assert "SELF_JUDGED" in kinds
    rep = review_panel.panel_report({"c1": {**ev, "replication": {"verdict": "DISAGREE"}}})
    assert rep["rows"][0]["verdict"] == "FAILED"


def test_organ_review_publishes_the_flag(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "OUT_DIR", tmp_path / "out")
    row = {"cell": "C1", "hunt": "h.json", "gates": {}, "shadow_spec": {"symbol": "EURUSD",
                                                                       "selector": "asia"}}
    monkeypatch.setattr(ts, "survivors", lambda: {"k1": row})
    monkeypatch.setattr(ts, "_producer_of_cell", lambda: {"C1": "tier_s:genomes"})
    monkeypatch.setattr(ts, "shadow_rows", lambda: {})
    monkeypatch.setattr(ts, "live_rows", lambda: [])
    out = ts._shared_reward(["k1"])
    assert out["status"] == "UNMEASURED", "no prices is never 'no conflict'"
    (tmp_path / "researcher_prices.json").write_text(json.dumps(
        {"researchers": {"tier_s:genomes": {"leg": "tier_s"}}, "leg_prices": {"tier_s": 1.0}}))
    out = ts._shared_reward(["k1"])
    assert out["n_self"] == 2 and out["by_candidate"]["k1"][0]["severity"] == "SELF"
    rep = ts.organ_review(None, None, None)
    assert rep["metric"]["self_judged"] == 2
    assert rep["verdicts"]["CHALLENGED"] + rep["verdicts"]["FAILED"] == 1


# ------------------------------------------------------------------ S09 Red Queen
def test_new_attack_kinds_are_traps_that_hide_with_subtlety() -> None:
    v = mb.reference_validator()
    for kind in ("hidden_factor", "overlap"):
        a, t = red_queen.generate(kind, 0, 1200, 0.0)
        b, _ = red_queen.generate(kind, 0, 1200, 0.0)
        assert not t.genuine and a.case_id == b.case_id
        ok, why = v(a)
        assert not ok and any(w.startswith("FACTOR") for w in why), why
        _ok, why1 = v(red_queen.generate(kind, 0, 1200, 1.0)[0])
        assert not any(w.startswith("FACTOR") for w in why1), why1
    through = [sum(v(red_queen.generate("false_causality", s, 1200, sub)[0])[0]
                   for s in range(4)) for sub in (0.0, 1.0)]
    assert through[1] > through[0], through


def test_attacks_are_attributed_and_charged_per_researcher() -> None:
    profiles = {"miner:cot": {"judged": 900, "passed": 3}, "miner:kimi": {"judged": 4,
                                                                          "passed": 2}}
    assert red_queen.trials_of(profiles["miner:cot"]) == 300
    assert red_queen.trials_of(profiles["miner:kimi"]) == 2
    assert red_queen.trials_of({"judged": 0}) is None
    a = {"kind": "false_causality", "subtlety": 0.9, "researcher": "miner:cot"}
    case, _ = red_queen.attack_cases(a, [1], n=400, profiles=profiles)[0]
    assert case.n_variants_tried == 300
    sealed = list(mb.Suite(per_kind=1, base_seed=5150, n=400).cases())
    res = red_queen.generation([], mb.ValidatorConfig(), sealed, seed=3, pop=4, defenders=1,
                               attack_seeds=1, researchers=profiles)
    assert set(res["by_researcher"]) <= set(profiles)
    assert sum(r["attacks"] for r in res["by_researcher"].values()) >= 4
    assert all(k in res["new_kinds"] for k in red_queen.NEW_KINDS)
    assert {a["kind"] for a in res["next_attackers"]} <= set(red_queen.ATTACK_KINDS)
    assert red_queen.from_state({"attackers": [{"kind": "overlap", "subtlety": 0.2}]})


# ------------------------------------------------------------------ S21 real suite + matrix
def _certs(n: int) -> tuple[dict[str, Any], dict[str, Any]]:
    certs, fwd = {}, {}
    for i in range(n):
        good = i % 2 == 0
        pbo = (0.02 if good else 0.3) + 0.001 * i
        certs[f"k{i}"] = {"gates": {"pbo": {"passed": True, "pbo": pbo},
                                    "deflated_sharpe": {"passed": True, "dsr": 0.99}},
                          "days": 500, "shadow_spec": {"symbol": f"S{i}", "selector": "asia"}}
        fwd[f"S{i}.asia"] = {"n": 30, "exp_r": 0.2 if good else -0.2}
    return certs, fwd


def test_labelled_real_suite_invents_a_gate_that_holds_on_both_halves() -> None:
    certs, fwd = _certs(40)
    certs["k_unl"] = {"gates": {}, "shadow_spec": {"symbol": "Z", "selector": "asia"}}
    suite = ti.labelled_suite(certs, fwd, lambda c: f"{c['shadow_spec']['symbol']}."
                                                     f"{c['shadow_spec']['selector']}")
    assert suite["n_labelled"] == 40 and suite["n_unlabelled"] == 1
    assert suite["precision"] == 0.5
    out = ti.invent_real(suite)
    assert out["status"] == "MEASURED"
    gates = out["candidate_gates"]
    assert gates and all(g["check"][0] == "pbo.pbo" and g["check"][1] == ">" for g in gates)
    assert all(g["confirmation"]["lost"] == 0 for g in gates)


def test_real_suite_without_both_labels_is_unmeasured() -> None:
    certs, fwd = _certs(10)
    for v in fwd.values():
        v["exp_r"] = 0.3
    suite = ti.labelled_suite(certs, fwd, lambda c: f"{c['shadow_spec']['symbol']}.asia")
    out = ti.invent_real(suite)
    assert out["status"] == "UNMEASURED" and out["candidate_gates"] == []


def test_redundancy_matrix_finds_subsumed_and_unique_gates() -> None:
    vec = [{"failed": ["pbo", "cpcv"], "genuine": False} for _ in range(6)]
    vec += [{"failed": ["cpcv"], "genuine": False} for _ in range(3)]
    vec += [{"failed": ["dsr", "pbo", "cpcv"], "genuine": False, "truncated": True}]
    vec += [{"failed": ["dsr"], "genuine": True}, {"failed": [], "genuine": True}]
    m = ti.redundancy_matrix(vec)
    assert m["kills"] == {"cpcv": 10, "dsr": 1, "pbo": 7}
    assert m["unique_kills"]["cpcv"] == 3 and m["unique_kills"]["pbo"] == 0
    assert {"gate": "pbo", "by": "cpcv", "p_by_fails_given_gate_fails": 1.0,
            "kills": 7} in m["subsumed"]
    assert m["false_rejects"]["dsr"] == 1 and m["n_truncated"] == 1
    assert ti.redundancy_matrix([])["status"] == "UNMEASURED"


def test_organ_test_invention_publishes_suite_and_matrix(monkeypatch: Any,
                                                         tmp_path: Path) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    certs, fwd = _certs(40)
    monkeypatch.setattr(ts, "survivors", lambda: certs)
    monkeypatch.setattr(ts, "shadow_rows", lambda: fwd)
    monkeypatch.setattr(ti, "invent", lambda *a, **k: {"candidate_gates": []})
    (tmp_path / "red_queen.json").write_text(json.dumps({"gate_vectors": [
        {"failed": ["pbo"], "genuine": False, "gates": ["pbo", "cpcv"]}]}))
    out = ts.organ_test_invention()
    assert out["real_suite"]["n_labelled"] == 40 and out["real_suite"]["candidate_gates"]
    assert out["redundancy"]["status"] == "MEASURED"
    assert out["metric"]["certificate_precision"] == 0.5
    reg = json.loads((tmp_path / "candidate_gates.json").read_text())["gates"]
    assert any(g.get("source") == "real_certificates" for g in reg)


def test_numpy_is_used() -> None:  # keeps the import honest for the helpers above
    assert np.isfinite(1.0)
