"""Tier S kernels (libs/tiers): each test pins the property the layer's contract relies on."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.tiers import (  # noqa: E402
    bitemporal,
    chaos,
    contracts,
    epistemic,
    evolution,
    failure_memory,
    firewall,
    formal,
    frontier,
    meta_benchmark,
    online_fdr,
    opportunity_exchange,
    prediction_accounting,
    replay,
    researcher_market,
    self_model,
    theory,
    topology,
    traps,
    truth_kernel,
    twin,
    world_edges,
)

# ---- truth kernel -------------------------------------------------------------------------------

def test_journal_is_content_addressed_idempotent_and_detects_edits(tmp_path: Path) -> None:
    j = truth_kernel.Journal(tmp_path / "j.jsonl")
    raw = j.put("raw_data", {"src": "bars", "sym": "XAUUSD"}, at="2026-09-29T00:00:00+00:00")
    again = j.put("raw_data", {"src": "bars", "sym": "XAUUSD"}, at="2026-09-29T00:00:00+00:00")
    assert raw.id == again.id and len(j.nodes()) == 1
    assert j.verify()["ok"]
    rows = (tmp_path / "j.jsonl").read_text("utf-8").splitlines()
    doc = json.loads(rows[0])
    doc["payload"]["sym"] = "EURUSD"
    (tmp_path / "j.jsonl").write_text(json.dumps(doc) + "\n", "utf-8")
    assert not truth_kernel.Journal(tmp_path / "j.jsonl").load().verify()["ok"]


def test_journal_refuses_unknown_parents_and_kinds(tmp_path: Path) -> None:
    j = truth_kernel.Journal(tmp_path / "j.jsonl")
    with pytest.raises(truth_kernel.KernelError):
        j.put("not_a_kind", {})
    with pytest.raises(truth_kernel.KernelError):
        j.put("hypothesis", {"x": 1}, parents=["deadbeef" * 8])


def test_a_loosened_constitution_is_a_violation_until_ratified() -> None:
    sealed = truth_kernel.constitution_doc()
    rules = {k: (v["value"], v["stricter"]) for k, v in sealed["rules"].items()}
    tight = dict(rules, **{"cert.dsr_threshold": (0.97, "up")})
    loose = dict(rules, **{"cert.dsr_threshold": (0.90, "up")})
    assert truth_kernel.constitution_status(sealed, sealed, [])["status"] == "SEALED"
    assert truth_kernel.constitution_status(
        sealed, truth_kernel.constitution_doc(tight), [])["status"] == "TIGHTENED"
    ld = truth_kernel.constitution_doc(loose)
    assert truth_kernel.constitution_status(sealed, ld, [])["status"] == "VIOLATION"
    agent = [{"hash": ld["hash"], "by": "agent"}]
    assert truth_kernel.constitution_status(sealed, ld, agent)["status"] == "VIOLATION"
    ok = [{"hash": ld["hash"], "by": "principal"}]
    assert truth_kernel.constitution_status(sealed, ld, ok)["status"] == "RATIFIED"


def test_committed_constitution_equals_the_sealed_default() -> None:
    live = json.loads((ROOT / "docs/research/tier_s_constitution.json").read_text("utf-8"))
    assert truth_kernel.constitution_status(truth_kernel.constitution_doc(), live,
                                            [])["status"] == "SEALED"


def test_evidence_seal_tells_append_from_rewrite_from_shrink(tmp_path: Path) -> None:
    p = tmp_path / "ledger.jsonl"
    p.write_text('{"a":1}\n', "utf-8")
    s1 = truth_kernel.seal_ledgers([p], None, tmp_path)
    p.write_text('{"a":1}\n{"a":2}\n', "utf-8")
    s2 = truth_kernel.seal_ledgers([p], s1, tmp_path)
    assert s2["violations"] == []
    p.write_text('{"a":9}\n{"a":2}\n', "utf-8")
    assert [v["kind"] for v in truth_kernel.seal_ledgers([p], s2, tmp_path)["violations"]] \
        == ["REWRITTEN"]
    p.write_text('{"a":1}\n', "utf-8")
    assert [v["kind"] for v in truth_kernel.seal_ledgers([p], s2, tmp_path)["violations"]] \
        == ["SHRANK"]


# ---- firewall -----------------------------------------------------------------------------------

def test_firewall_audits_real_organs_and_ratchets(tmp_path: Path) -> None:
    a = firewall.audit(ROOT)
    assert all(n > 0 for n in a["organs_checked"].values()), a["organs_checked"]
    assert not firewall.ratchet(a, a)["breach"]
    worse = {**a, "violations": [*a["violations"], {"role": "reviewer", "organ": "x.py",
                                                     "kind": "WRITE", "token": "sleeves.json"}]}
    assert firewall.ratchet(worse, a)["breach"]


# ---- planted traps / meta-benchmark -------------------------------------------------------------

def test_traps_are_deterministic_and_the_suite_seal_is_stable() -> None:
    a, _ = traps.generate("leakage", 7, 600)
    b, _ = traps.generate("leakage", 7, 600)
    assert a.case_id == b.case_id and np.allclose(a.prices, b.prices)
    s = meta_benchmark.Suite(per_kind=1, n=600)
    assert s.seal() == meta_benchmark.Suite(per_kind=1, n=600).seal()


def test_reference_validator_rejects_blatant_traps() -> None:
    v = meta_benchmark.reference_validator(meta_benchmark.ValidatorConfig())
    for kind in ("leakage", "impossible_fills", "cost_fake"):
        case, truth = traps.generate(kind, 3, 1200)
        assert not truth.genuine
        assert not v(case)[0], kind


def test_immune_verdict_freezes_below_the_floor() -> None:
    res = {"immune_score": 0.8, "power": 0.9, "balanced": 0.85}
    assert meta_benchmark.immune_verdict(res, [], floor=0.9)["verdict"] == "FREEZE"
    res_ok = {"immune_score": 0.95, "power": 0.9, "balanced": 0.925}
    assert meta_benchmark.immune_verdict(res_ok, [], floor=0.9)["verdict"] != "FREEZE"


# ---- online FDR ---------------------------------------------------------------------------------

def test_online_fdr_spends_less_than_alpha_on_nulls() -> None:
    rng = np.random.default_rng(0)
    tests = [online_fdr.Test(f"t{i}", f"2026-01-01T{i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}",
                             p=float(rng.uniform()), family="fam") for i in range(2000)]
    r = online_fdr.replay(tests, alpha=0.05)
    assert r["lord_discoveries"] <= 5 and r["elond_discoveries"] <= 5
    strong = [online_fdr.Test("s", "2026-01-01T00:00:00", p=1e-9, certified=True)]
    assert online_fdr.replay(strong)["over_budget"] == 0


# ---- topology -----------------------------------------------------------------------------------

def test_participation_ratio_counts_independent_bets() -> None:
    assert topology.participation_ratio(np.eye(5)) == pytest.approx(5.0)
    assert topology.participation_ratio(np.ones((5, 5))) == pytest.approx(1.0)


def test_exact_descriptor_repeats_are_not_new_discoveries() -> None:
    nodes = {f"n{i}": {"parents": [], "descriptors": {"family": "carry", "symbol": "EURUSD"}}
             for i in range(50)}
    nodes["x"] = {"parents": [], "descriptors": {"family": "gap", "symbol": "XAUUSD"}}
    eff = topology.effective_discoveries(topology.novelty(nodes))
    assert eff["effective"] == pytest.approx(2.0)


# ---- theory -------------------------------------------------------------------------------------

def test_theory_posterior_weights_live_over_backtest() -> None:
    m = theory.compile_mechanism({"payer": "hedgers", "trigger": "fix"}, family="fix_flow")
    g = theory.TheoryGraph()
    t = g.theory(m)
    for i in range(5):
        t.add(experiment=f"b{i}", supports=True, source="backtest")
    before = t.posterior()["confidence"]
    t.add(experiment="l0", supports=False, source="live")
    t.add(experiment="l1", supports=False, source="live")
    assert t.posterior()["confidence"] < before


# ---- researcher market / evolution / frontier ---------------------------------------------------

def test_market_never_cuts_floors_and_caps_any_single_share() -> None:
    rs = [researcher_market.Researcher(f"r{i}", successes={"survive": i}, trials={"survive": 10},
                                       floor_s=60.0) for i in range(4)]
    out = researcher_market.allocate(rs, 1000.0, seed=1, max_share=0.35)
    assert all(a["budget_s"] >= 60.0 for a in out["allocations"].values())
    assert all(a["headroom_s"] <= 0.35 * 1000 + 10 for a in out["allocations"].values())
    assert out["total_budget_s"] <= 4 * 60 + 1000 + 1e-6


def test_archive_keeps_the_best_per_niche() -> None:
    arch = evolution.Archive(axes=("family", "tf"))
    assert arch.add("a", {"family": "carry", "tf": "H1"}, 0.1)
    assert not arch.add("b", {"family": "carry", "tf": "H1"}, 0.05)
    assert arch.add("c", {"family": "carry", "tf": "H1"}, 0.2)
    assert arch.coverage()["filled"] == 1


def test_chao1_sees_unseen_species_from_singletons() -> None:
    est = frontier.chao1({"a": 1, "b": 1, "c": 1, "d": 5})
    assert est["chao1"] > 4 and est["unseen"] > 0


# ---- failure memory -----------------------------------------------------------------------------

def test_failure_memory_compresses_repeated_failures_into_a_theorem() -> None:
    rows = [{"family": "carry", "sym": "EURUSD", "tf": "H1", "passed": False,
             "terminal_gate": "deflated_sharpe"} for _ in range(40)]
    mem = failure_memory.compress(rows, min_trials=20)
    assert mem["theorems"], mem


# ---- formal verification / chaos / replay -------------------------------------------------------

def test_the_desk_order_protocol_is_proven_and_each_knob_is_load_bearing() -> None:
    res = formal.ablations()
    assert res["desk_all_proven"]
    assert "recheck_alloc_at_send" in res["depends_on"]["ZERO_MEANS_NO_ORDER"]
    assert "check_cert_at_send" in res["depends_on"]["CERTIFICATE_REQUIRED"]
    assert "clamp_data_to_clock" in res["depends_on"]["NO_FUTURE_DATA"]


def test_corruption_drill_flags_a_loader_that_accepts_garbage(tmp_path: Path) -> None:
    src = tmp_path / "x.json"
    src.write_text(json.dumps({"k": [1, 2, 3]}), "utf-8")

    def lenient(p: Path) -> object:
        return {"k": [1]}

    def strict(p: Path) -> object:
        try:
            d = json.loads(p.read_text("utf-8"))
        except ValueError:
            return {}
        return d if isinstance(d, dict) and d.get("k") == [1, 2, 3] else {}

    assert chaos.drill("lenient", src, lenient, lambda o: not o)["status"] == "FAIL"
    assert chaos.drill("strict", src, strict, lambda o: not o)["status"] == "PASS"


def test_replay_never_reads_the_future() -> None:
    rows = [{"t": "2026-09-01T00:00:00+00:00", "sym": "A"},
            {"t": "2026-09-03T00:00:00+00:00", "sym": "B"}]
    s = replay.Stream("x", rows, "t", key=lambda r: str(r["sym"]))
    out = replay.replay([s], datetime(2026, 9, 2, tzinfo=UTC))
    assert set(out["state"]["x"]) == {"A"} and out["stats"]["x"]["after_t"] == 1


# ---- data OS / world model ----------------------------------------------------------------------

def test_bitemporal_as_of_returns_what_was_known_then() -> None:
    st = bitemporal.BitemporalStore([
        bitemporal.Datum("US", "gdp", 1.0, "2026-06-30", "2026-07-30", revision=0),
        bitemporal.Datum("US", "gdp", 1.4, "2026-06-30", "2026-09-25", revision=1)])
    assert st.as_of("2026-08-01")[("US", "gdp", "2026-06-30")].value == 1.0
    assert st.as_of("2026-09-29")[("US", "gdp", "2026-06-30")].value == 1.4
    audit = bitemporal.pit_audit([{"valid_time": "2026-01-02", "knowledge_time": "2026-01-01"}])
    assert audit["impossible"] == 1


def test_world_edges_call_noise_false_and_a_real_edge_not_false() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=2000)
    assert world_edges.classify_edge(x, rng.normal(size=2000), 0)["class"] == "FALSE"
    assert world_edges.classify_edge(x, 0.5 * x + rng.normal(size=2000), 0)["class"] != "FALSE"


# ---- prediction accounting / exchange / twin ----------------------------------------------------

def test_a_forecast_made_after_its_outcome_is_refused() -> None:
    led: list[prediction_accounting.Forecast] = []
    f = prediction_accounting.Forecast("k", "2026-09-02T00:00:00+00:00",
                                       "2026-09-03T00:00:00+00:00", 0.1, 1.0)
    with pytest.raises(prediction_accounting.RegistrationError):
        prediction_accounting.register(led, f, outcome_time="2026-09-01T00:00:00+00:00")
    prediction_accounting.register(led, f, outcome_time="2026-09-03T00:00:00+00:00")
    assert len(led) == 1


def test_exchange_fills_the_heat_floor_and_stays_under_the_ceiling() -> None:
    bids = [opportunity_exchange.Bid(f"b{i}", mu=0.002, mu_sd=0.0005, sigma=0.02,
                                     capacity=10.0) for i in range(6)]
    out = opportunity_exchange.clear(bids, heat_floor=0.2, heat_ceiling=0.3)
    assert 0.2 - 1e-6 <= out["heat"] <= 0.3 + 1e-6
    # capacity binding below the floor: the floor cannot be filled and says so
    tight = [opportunity_exchange.Bid(f"b{i}", mu=0.002, mu_sd=0.0005, sigma=0.02,
                                      capacity=0.1) for i in range(6)]
    assert opportunity_exchange.clear(tight)["heat"] <= 6 * 0.1 * 0.02 + 1e-9
    assert set(out["action_counts"]) == set(opportunity_exchange.ACTIONS)


def test_twin_counts_only_evidence_after_registration_and_money_path_only_proposes() -> None:
    ch = twin.Challenger("allocator", "c", "2026-09-10T00:00:00+00:00", "h")
    pairs = [(f"2026-09-{d:02d}T00:00:00+00:00", 0.0, 1.0 + 0.01 * d) for d in range(1, 31)]
    pairs += [(f"2026-10-{d:02d}T00:00:00+00:00", 0.0, 1.0 + 0.01 * d) for d in range(1, 31)]
    res = twin.evaluate(ch, pairs)
    assert res["dropped_before_registration"] == 10 and res["verdict"] == "PROPOSE"
    res0 = twin.evaluate(ch, [])
    assert res0["verdict"] == "CONTINUE" and res0["money_path"] is True
    research = twin.Challenger("validator", "v", "2026-09-10T00:00:00+00:00", "h")
    assert twin.evaluate(research, pairs)["verdict"] == "PROMOTE"


# ---- contracts / epistemics / self-model --------------------------------------------------------

def test_contract_verdicts() -> None:
    c = contracts.Contract.parse({"gain": "FALSIFICATION", "metric": "m", "better": "up"})
    assert contracts.evaluate(c, [0.5])["verdict"] == "UNMEASURED"
    assert contracts.evaluate(c, [0.5, 0.5, 0.5, 0.9, 0.9, 0.9])["verdict"] == "ADMITTED"
    assert contracts.evaluate(c, [0.5, 0.6, 0.5, 0.6, 0.5, 0.6, 0.5, 0.6])["verdict"] \
        == "REJECTED"
    assert contracts.problems({"gain": "SOUNDS_SOPHISTICATED", "metric": "m"})
    assert contracts.problems(None)


def test_absence_is_never_a_decision() -> None:
    q = epistemic.mean_quantity("edge", [])
    assert epistemic.decide(q, 0.0) == epistemic.Decision.INSUFFICIENT_EVIDENCE


def test_self_model_ranks_deficiencies() -> None:
    ranked = self_model.rank([{"area": "a", "gap": 0.1, "gain": "PRODUCTIVITY", "p_fix": 0.5,
                               "cost": 1.0}, {"area": "b", "gap": 1.0, "gain": "CALIBRATION",
                                              "p_fix": 0.8, "cost": 0.5}])
    assert ranked[0]["area"] == "b"


# ---- the programme ledger is its own admission gate ---------------------------------------------

def test_programme_ledger_passes_its_gate() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_tier_s_program as chk
    ledger = json.loads(chk.LEDGER.read_text("utf-8"))
    problems, counts = chk.check(ledger, ROOT)
    assert problems == [] and sum(counts.values()) == 46


def test_a_layer_without_a_contract_is_refused() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_tier_s_program as chk
    ledger = json.loads(chk.LEDGER.read_text("utf-8"))
    ledger["layers"][0] = {k: v for k, v in ledger["layers"][0].items() if k != "contract"}
    problems, _ = chk.check(ledger, ROOT)
    assert any("contract" in p for p in problems)


def test_grammar_round_trip_and_learned_bias(tmp_path) -> None:
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    import numpy as _np

    from libs.research import alpha_grammar as ag
    from libs.tiers import grammar_bias

    e = ["zscore", ["sub", "close", "open"], 20]
    assert ag.from_str(ag.to_str(e)) == e
    # no weights: the draw is the uniform one, identical for the same seed
    a = ag.random_expr(_np.random.default_rng(3), 3)
    b = ag.random_expr(_np.random.default_rng(3), 3, op_weights=None, primitives=None)
    assert a == b
    p = tmp_path / "grammar.json"
    p.write_text(_json.dumps({"generated_utc": _dt.now(_UTC).isoformat(),
                              "operator_weights": {"add": 3.0, "sub": 0.05},
                              "primitives": [{"expression": ag.to_str(e)}]}))
    got = grammar_bias.bias(p)
    assert got["op_weights"]["add"] == 3.0 and got["primitives"] == [e]
    # a retired operator is drawn less, never never
    rng = _np.random.default_rng(0)
    picks = [ag._pick(rng, ("add", "sub"), got["op_weights"]) for _ in range(4000)]
    assert 0 < picks.count("sub") < picks.count("add")
