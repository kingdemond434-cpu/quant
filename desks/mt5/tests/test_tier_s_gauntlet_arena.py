"""Tier S layer 33: validator genomes compete on the REAL gauntlet's verdicts.

The genomes the Red Queen evolves used to be adopted on the reference validator's own score. Now
every genome is scored on the sealed cases the desk's real ten-gate certifier judged blind
(`libs/tiers/gauntlet_arena.py`), the Red Queen's defenders are ranked by that score, and the
twin adopts only on `gauntlet_arena.judge`'s verdict -- into research state, with the sealed
files fingerprinted around the write.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import gauntlet_arena as ga  # noqa: E402
from libs.tiers import meta_benchmark as mb  # noqa: E402
from libs.tiers import red_queen, traps  # noqa: E402

# ------------------------------------------------------------------------------ the arena


def _judged(n_traps: int = 240, n_genuine: int = 40, leak: int = 30,
            real_power: float = 1.0) -> list[ga.Judged]:
    """Synthetic real-gauntlet verdicts: the gauntlet accepts `real_power` of the genuine
    controls and lets `leak` traps through (all of kind 'leakage')."""
    out = []
    for i in range(n_traps):
        kind = "leakage" if i < leak else "selection"
        out.append(ga.Judged(kind, i, False, i < leak, SimpleNamespace(kind=kind, i=i)))
    for i in range(n_genuine):
        out.append(ga.Judged("true_signal", 10_000 + i, True, i < real_power * n_genuine,
                             SimpleNamespace(kind="true_signal", i=i)))
    return out


def _v(reject_kinds: set[str]) -> ga.Validator:
    def run(case: Any) -> tuple[bool, list[str]]:
        return (case.kind not in reject_kinds), []
    return run


def test_real_decisions_keep_only_the_current_code_and_measured_verdicts() -> None:
    verdicts = {"leakage|1": {"code": "c1", "passed": True},
                "leakage|2": {"code": "c0", "passed": False},
                "true_signal|3": {"code": "c1", "passed": False},
                "selection|4": {"code": "c1", "passed": False, "unmeasured": True},
                "garbage": {"code": "c1", "passed": True}}
    assert ga.real_decisions(verdicts, "c1") == {("leakage", 1): True,
                                                 ("true_signal", 3): False}


def test_judged_cases_regenerate_the_sealed_case_and_keep_every_leak_under_a_limit() -> None:
    dec = {(k, 100 + i): (k == "leakage" and i == 0)
           for i in range(5) for k in traps.ALL_KINDS}
    full = ga.judged_cases(dec, 120)
    assert len(full) == len(dec)
    c0 = next(c for c in full if c.kind == "leakage" and c.seed == 100)
    again, _t = traps.generate("leakage", 100, 120)
    assert np.array_equal(c0.case.prices, again.prices), "the SAME case the gauntlet judged"
    few = ga.judged_cases(dec, 120, limit=40)
    assert len(few) == 40
    assert ("leakage", 100) in {(c.kind, c.seed) for c in few}, "a real leak is always kept"
    assert sum(c.genuine for c in few) == 5 * len(traps.TRUE_KINDS)


def test_arena_scores_the_genome_laid_over_the_real_gates() -> None:
    cases = _judged()
    plain = ga.arena_score(_v(set()), cases)
    assert plain["joint"] == plain["real_gauntlet"]
    assert plain["real_gauntlet"]["immune"] == pytest.approx(210 / 240)
    catcher = ga.arena_score(_v({"leakage"}), cases)
    assert catcher["joint"]["immune"] == 1.0 and catcher["joint"]["power"] == 1.0
    assert catcher["traps_caught_beyond_real"] == 30 and catcher["real_power_lost"] == 0
    assert catcher["vs_gauntlet"] == {"genome_right": 30, "gauntlet_right": 0, "net": 30,
                                      "mcnemar_z": pytest.approx(30 / np.sqrt(30), abs=1e-3)}
    v = ga.judge(catcher, plain)
    assert v["verdict"] == "ADOPT" and "joint" in v["why"]
    killer = ga.arena_score(_v({"leakage", "true_signal"}), cases)
    assert killer["real_power_lost"] == 40
    assert ga.judge(killer, plain)["verdict"] == "REJECT"


def test_when_the_real_gates_reject_everything_the_disagreement_record_decides() -> None:
    cases = _judged(leak=0, real_power=0.0)          # the production certifier today
    incumbent = ga.arena_score(_v({"leakage", "selection", "true_signal"}), cases)
    sharp = ga.arena_score(_v({"leakage", "selection"}), cases)
    # laid over gates that accept nothing, no genome changes the joint decision ...
    assert sharp["joint"] == incumbent["joint"]
    # ... but where it disagrees with the gauntlet it is right (the genuine controls)
    assert sharp["vs_gauntlet"]["net"] == 40 and incumbent["vs_gauntlet"]["net"] == 0
    assert ga.judge(sharp, incumbent)["verdict"] == "ADOPT"
    assert ga.judge(incumbent, sharp)["verdict"] == "REJECT"


def test_judge_is_unmeasured_without_enough_real_verdicts() -> None:
    few = _judged(n_traps=50, n_genuine=5, leak=5)
    a, b = ga.arena_score(_v({"leakage"}), few), ga.arena_score(_v(set()), few)
    v = ga.judge(a, b)
    assert v["verdict"] == "UNMEASURED" and "need 200" in v["why"]


def test_sealed_fingerprint_names_every_never_edit_file() -> None:
    fp = ga.sealed_fingerprint()
    assert set(fp) == set(ga.SEALED_FILES)
    assert all(v is not None for v in fp.values()), "every sealed file exists in this clone"


# ------------------------------------------------------------------------------ Red Queen


def test_red_queen_defenders_compete_on_the_real_fitness() -> None:
    sealed = list(mb.Suite(per_kind=1, base_seed=5150, n=300).cases())
    calls: list[mb.ValidatorConfig] = []

    def real(cfg: mb.ValidatorConfig) -> dict[str, Any]:
        calls.append(cfg)
        # the real arena prefers a HIGHER dsr threshold, whatever the reference score says
        return {"n": 100, "joint": {"balanced": float(cfg.dsr_threshold)},
                "vs_gauntlet": {"net": 0}}

    res = red_queen.generation([], mb.ValidatorConfig(), sealed, seed=3, pop=4, defenders=6,
                               attack_seeds=1, real_fitness=real)
    assert res["defender_judge"] == "real_gauntlet"
    assert len(calls) == 7, "the incumbent and every mutant are judged on the real arena"
    if res["challenger"] is not None:
        assert res["challenger"]["dsr_threshold"] > mb.ValidatorConfig().dsr_threshold
        assert res["best_real"]["joint"]["balanced"] > res["incumbent_real"]["joint"][
            "balanced"]

    def never(cfg: mb.ValidatorConfig) -> dict[str, Any]:
        return {"n": 100, "joint": {"balanced": 0.9 if cfg == mb.ValidatorConfig() else 0.1},
                "vs_gauntlet": {"net": 0}}

    res2 = red_queen.generation([], mb.ValidatorConfig(), sealed, seed=3, pop=4, defenders=6,
                                attack_seeds=1, real_fitness=never)
    assert res2["challenger"] is None, "no mutant beat the incumbent on the real arena"
    plain = red_queen.generation([], mb.ValidatorConfig(), sealed, seed=3, pop=4, defenders=2,
                                 attack_seeds=1)
    assert plain["defender_judge"] == "reference_validator"


# ------------------------------------------------------------------------------ the twin


@pytest.fixture()
def arena_world(tmp_path: Path, monkeypatch: Any) -> dict[str, Any]:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts.authority, "suspended", lambda k: False)
    cases = _judged()
    monkeypatch.setattr(ts, "_real_arena", lambda limit=None: (
        cases, {"status": "MEASURED", "code": "gcode", "n": len(cases), "key": "k1"}))

    # a genome's dsr_threshold picks what it rejects: > 0.97 also rejects the leaking traps
    def ref(cfg: mb.ValidatorConfig | None = None) -> ga.Validator:
        c = cfg or mb.ValidatorConfig()
        return _v({"leakage"} if c.dsr_threshold > 0.97 else set())

    monkeypatch.setattr(ts.meta_benchmark, "reference_validator", ref)
    good = {**mb.ValidatorConfig(dsr_threshold=0.99).genome()}
    bad = {**mb.ValidatorConfig(dsr_threshold=0.9).genome()}
    chall = [{"component": "validator", "name": "rq_good", "genome": good, "genome_hash": "g1"},
             {"component": "validator", "name": "rq_bad", "genome": bad, "genome_hash": "g2"}]
    out = [{"name": c["name"], "component": "validator", "adoption": "PENDING"} for c in chall]
    return {"out": out, "chall": chall, "tmp": tmp_path}


def test_the_twin_adopts_only_on_the_real_verdict_and_stays_research_side(
        arena_world: dict[str, Any]) -> None:
    before = ga.sealed_fingerprint()
    rep = ts._judge_validators(arena_world["out"], arena_world["chall"], blocked=False)
    rows = {r["name"]: r for r in arena_world["out"]}
    assert rows["rq_good"]["adoption"] == "ADOPTED"
    assert rows["rq_good"]["judged_on"] == "real_gauntlet:gcode"
    assert rows["rq_good"]["real_arena"]["verdict"]["verdict"] == "ADOPT"
    assert rows["rq_good"]["sealed_files_unchanged"] is True
    assert rows["rq_bad"]["adoption"] == "REJECTED_BY_REAL_GAUNTLET"
    assert rep["adopted"] == ["rq_good"]
    ad = json.loads((arena_world["tmp"] / "adopted.json").read_text("utf-8"))
    assert ad["validator"]["dsr_threshold"] == 0.99
    assert ad["validator_judged_on"] == "real_gauntlet:gcode"
    # research-side only: the state dir holds the adoption, the sealed files never moved
    assert sorted(p.name for p in arena_world["tmp"].iterdir()) == ["adopted.json",
                                                                    "arena_scores.json"]
    assert ga.sealed_fingerprint() == before
    # and the next hour's incumbent is the adopted genome
    assert ts._incumbent_validator().dsr_threshold == 0.99


def test_the_twin_adopts_nothing_while_the_real_arena_is_unmeasured(
        arena_world: dict[str, Any], monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "_real_arena", lambda limit=None: (
        [], {"status": "UNMEASURED", "why": "BLOCKED: gauntlet not importable"}))
    ts._judge_validators(arena_world["out"], arena_world["chall"], blocked=False)
    assert {r["adoption"] for r in arena_world["out"]} == {"PENDING_REAL_VERDICT"}
    assert not (arena_world["tmp"] / "adopted.json").exists()


def test_a_blocked_desk_or_suspended_twin_never_adopts(arena_world: dict[str, Any],
                                                        monkeypatch: Any) -> None:
    ts._judge_validators(arena_world["out"], arena_world["chall"], blocked=True)
    assert arena_world["out"][0]["adoption"] == "BLOCKED_BY_SEALED_REGRESSION"
    assert not (arena_world["tmp"] / "adopted.json").exists()
    monkeypatch.setattr(ts.authority, "suspended", lambda k: True)
    for r in arena_world["out"]:
        r["adoption"] = "PENDING"
    ts._judge_validators(arena_world["out"], arena_world["chall"], blocked=False)
    assert arena_world["out"][0]["adoption"] == "PENDING_AUTHORITY"


def test_real_arena_reads_production_verdicts_through_the_real_gate(
        tmp_path: Path, monkeypatch: Any) -> None:
    """The arena's cases are exactly the verdicts `production_immune` kept for the gauntlet's
    CURRENT code, read back; the gauntlet itself is reached only through adversary.real_gate."""
    monkeypatch.setattr(ts, "STATE", tmp_path)
    import adversary
    gate = SimpleNamespace(_gauntlet=SimpleNamespace())
    monkeypatch.setattr(adversary, "real_gate", lambda: (gate, None))
    monkeypatch.setattr(ts, "_gauntlet_code_hash", lambda g: "live")
    (tmp_path / "immune_prod.json").write_text(json.dumps({"verdicts": {
        "leakage|20260930": {"code": "live", "passed": True, "kind": "leakage"},
        "true_signal|20267930": {"code": "live", "passed": False, "kind": "true_signal"},
        "leakage|20260931": {"code": "stale", "passed": True, "kind": "leakage"}}}))
    cases, status = ts._real_arena()
    assert status["status"] == "MEASURED" and status["code"] == "live"
    assert {(c.kind, c.real_passed) for c in cases} == {("leakage", True),
                                                       ("true_signal", False)}
    assert all(len(c.case.prices) == ts.PROD_SUITE.n for c in cases)
    monkeypatch.setattr(adversary, "real_gate", lambda: (None, "BLOCKED: x"))
    assert ts._real_arena()[1]["status"] == "UNMEASURED"
