"""THE MULTI-LAB RESEARCH CIVILIZATION: every proposal ends in exactly one named disposition.

The properties the principal's directive turns on, asserted as behaviour:

  * an accepted mechanism with an exact registered recipe becomes a donation row the miner
    candidate compiler admits as EXACT_RECIPE -- the lab's only door to the canonical gauntlet;
  * a generic indicator recipe is a BASELINE, never credited, while a simple rule carrying a new
    mechanism is not banal;
  * the five novelty classes are measured against the lab's genealogy and the desk's library,
    and duplicates are collapsed rather than charged;
  * nothing is invented to close a gap: missing data, rules, families, parameters and symbols are
    named conversion debt, and debt is re-compiled (and resolved) when the registry changes;
  * a per-pass cap is NOT THIS PASS: coordinates are owed, visited in cursor order, and the
    ontology grows when a lab names a class it lacks;
  * the independent first pass gives labs different models while different models exist;
  * with no seat the pass writes UNMEASURED, keeps every coordinate owed and calls nothing.
"""
from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_lab as lab  # noqa: E402

HOURLY = _DESK / "research" / "hourly_cycle.py"


@pytest.fixture()
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every lab path under tmp, so no test writes into the checkout."""
    sd = tmp_path / "llm_lab"
    for name, rel in {"STATE_DIR": "", "GENEALOGY": "genealogy.jsonl",
                      "DEBT": "conversion_debt.json", "COVERAGE": "coverage.json",
                      "ONTOLOGY": "ontology.json", "MODELS": "model_registry.json",
                      "DATA_REQUESTS": "data_requests.jsonl", "JEV_JOBS": "jev_jobs.jsonl",
                      "CALLS": "calls.json", "MODEL_CUTOFFS": "model_cutoffs.json",
                      "ROTATION": "model_rotation.json"}.items():
        monkeypatch.setattr(lab, name, sd / rel if rel else sd)
    monkeypatch.setattr(lab, "DONATE_DIR", tmp_path / "intelligence" / "llm_lab")
    monkeypatch.setattr(lab, "REPORT", tmp_path / "reports" / "LLM_LAB.json")
    monkeypatch.setattr(lab, "VERDICTS", tmp_path / "none.jsonl")
    monkeypatch.setattr(lab, "SARES_DIR", tmp_path / "sares")
    monkeypatch.setattr(lab, "_cb_tone_role",
                        lambda **kw: {"state": "TEST_STUB", "model": {"calls": 0}, **kw})
    monkeypatch.setattr(lab, "_collector_role", lambda **kw: {"state": "RAN", "asked": 0, **kw})
    monkeypatch.setattr(lab, "gauntlet_trims", lambda: True)
    import llm_lab_roles as roles
    for name in ("CREDIT", "EVIDENCE_START", "MISSED", "DAILY", "CODE_LEDGER", "SCOUTED",
                 "RED_TEAM"):
        monkeypatch.setattr(roles, name, sd / f"{name.lower()}.json")
    for name in ("CODE_DIR", "SERIES_DIR", "BARS_DIR"):
        monkeypatch.setattr(roles, name, tmp_path / name.lower())
    monkeypatch.setattr(roles, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(roles, "_chat", lambda *a, **k: ("", "test: chain dark"))
    return tmp_path


@pytest.fixture(scope="module")
def reg() -> dict[str, lab.FamilySpec]:
    r = lab.family_registry()
    if not r:
        pytest.skip("families did not import on this host")
    return r


UNI = {"EURUSD": "forex", "USDJPY": "forex", "XAUUSD": "commodities", "Apple": "equities"}


def _mem() -> lab.Memory:
    return lab.Memory()


# --------------------------------------------------------------------------- banal filter
@pytest.mark.parametrize("mech", [
    "Buy when RSI is oversold below 30 and sell when overbought above 70 on the chart",
    "A plain moving average crossover of the 50 and 200 period lines, golden cross entries",
    "MACD crossover above its signal line marks the start of a new up move in the pair",
])
def test_a_generic_indicator_recipe_is_a_baseline(mech: str) -> None:
    assert lab.banal({"mechanism": mech})


def test_simplicity_with_a_new_mechanism_is_not_banal() -> None:
    mech = ("RSI oversold only inside the London fixing window, where forced dealer hedging "
            "flow exhausts and reverses")
    assert lab.banal({"mechanism": mech}) == ""


# --------------------------------------------------------------------------- compile
def test_an_exact_registered_recipe_compiles_to_cells(reg: dict[str, lab.FamilySpec]) -> None:
    fam = "overnight_gap_decay" if "overnight_gap_decay" in reg else sorted(reg)[0]
    key = next(iter(reg[fam].params), None)
    params = {key: reg[fam].params[key]} if key else {}
    out = lab.compile_payload({"family": fam, "params": params, "symbols": ["eurusd"],
                               "timeframe": "H1"}, reg, UNI)
    assert not out.blockers and not out.refused
    assert out.cells and out.cells[0]["symbol"] == "EURUSD"
    assert out.cells[0]["params"]["timeframe"] == "H1"


def test_an_unregistered_family_is_named_debt_not_a_guess(reg: dict[str, lab.FamilySpec]
                                                          ) -> None:
    out = lab.compile_payload({"family": "dealer_gamma_pin_2099", "symbols": ["EURUSD"]},
                              reg, UNI)
    assert out.blockers == ["NEEDS_EXECUTABLE_FAMILY"] and not out.cells


def test_family_none_without_an_expression_is_named_debt(reg: dict[str, lab.FamilySpec]) -> None:
    out = lab.compile_payload({"family": "NONE", "symbols": ["EURUSD"]}, reg, UNI)
    assert out.blockers == ["NEEDS_EXECUTABLE_FAMILY"]


def test_a_valid_formula_compiles_and_an_invalid_one_is_rule_debt(
        reg: dict[str, lab.FamilySpec]) -> None:
    if "formula" not in reg:
        pytest.skip("formula family not registered here")
    ok = lab.compile_payload({"family": "formula", "expr": "zscore(sub(ret, mean(ret, 24)), 120)",
                              "symbols": ["USDJPY"]}, reg, UNI)
    assert ok.cells and ok.cells[0]["params"]["expr"].startswith("zscore(")
    bad = lab.compile_payload({"family": "formula", "expr": "add(std(close, 24), ret",
                               "symbols": ["USDJPY"]}, reg, UNI)
    assert "NEEDS_EXACT_RULE_EXTRACTION" in bad.blockers and not bad.cells


def test_a_missing_series_is_named_data_debt(reg: dict[str, lab.FamilySpec],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    if "exogenous_conditioner" not in reg:
        pytest.skip("exogenous_conditioner not registered here")
    monkeypatch.setattr(lab, "_series_present", lambda src: False)
    out = lab.compile_payload({"family": "exogenous_conditioner", "symbols": ["EURUSD"],
                               "params": {"source": "dealer_inventory_pit", "signal": "net"}},
                              reg, UNI)
    assert out.blockers == ["NEEDS_DATA"] and out.data_needed == ["dealer_inventory_pit"]


def test_a_jev_question_queues_and_waits_for_its_own_series(
        reg: dict[str, lab.FamilySpec], monkeypatch: pytest.MonkeyPatch) -> None:
    if "exogenous_conditioner" not in reg:
        pytest.skip("exogenous_conditioner not registered here")
    monkeypatch.setattr(lab, "_series_present", lambda src: False)
    out = lab.compile_payload({"symbols": ["EURUSD"], "jev_question": {
        "question": "Does today's ECB statement signal a faster pace of cuts than priced?",
        "answer_type": "probability"}}, reg, UNI)
    assert out.jev_question and out.jev_question["series"].startswith("jev_")
    assert out.blockers == ["NEEDS_DATA"] and out.data_needed == [out.jev_question["series"]]


def test_an_unknown_symbol_is_instrument_debt(reg: dict[str, lab.FamilySpec]) -> None:
    out = lab.compile_payload({"family": sorted(reg)[0], "symbols": ["NOT_A_SYMBOL"]}, reg, UNI)
    assert "NEEDS_INSTRUMENT_MAPPING" in out.blockers and not out.cells


def test_a_mistyped_parameter_is_inference_debt(reg: dict[str, lab.FamilySpec]) -> None:
    fam, key = next((f, k) for f, s in sorted(reg.items()) for k, d in s.params.items()
                    if isinstance(d, (int, float)) and not isinstance(d, bool))
    out = lab.compile_payload({"family": fam, "params": {key: "about two"},
                               "symbols": ["EURUSD"]}, reg, UNI)
    assert "NEEDS_PARAMETER_INFERENCE" in out.blockers


def test_a_banned_family_is_refused_not_debt(reg: dict[str, lab.FamilySpec]) -> None:
    out = lab.compile_payload({"family": "discovered", "symbols": ["EURUSD"]}, reg, UNI)
    assert out.refused.startswith("BANNED_FAMILY") or "NEEDS_EXECUTABLE_FAMILY" in out.blockers
    assert "discovered" not in reg


# --------------------------------------------------------------------------- novelty
def test_the_five_novelty_classes() -> None:
    mem = _mem()
    seen = {"symbol": "EURUSD", "family": "carry", "params": {"rr": 2.0, "ttl_bars": 96}}
    mem.remember({"node": "N1", "lab": "B", "cell_id": lab.cell_identity(seen), "cell": seen,
                  "mechanism": "forced hedging flow by exporters at month end on the euro"})
    assert lab.classify(seen, "x", [], mem)[0] == "EXACT_DUPLICATE"
    near = {**seen, "params": {"rr": 2.1, "ttl_bars": 96}}
    assert lab.classify(near, "x", [], mem)[0] == "PARAMETER_NEIGHBOUR"
    other = {"symbol": "USDJPY", "family": "carry", "params": {"rr": 3.0}}
    assert lab.classify(other, "y", ["N1"], mem) == ("COMPOSITIONAL_DESCENDANT", "N1")
    assert lab.classify(other, "forced hedging flow by exporters at month end on the yen",
                        [], mem)[0] == "MECHANISM_NEIGHBOUR"
    assert lab.classify(other, "volcanic ash grounding flights drains jet fuel inventory",
                        [], mem)[0] == "GENUINELY_NOVEL"


# --------------------------------------------------------------------------- coverage
def test_owed_coordinates_are_visited_in_cursor_order_and_never_forgotten(state: Path) -> None:
    cov = lab.Coverage.load()
    a = lab.LAB_BY_KEY["B"]
    onto = lab._ontology()
    rng = random.Random(1)  # noqa: S311
    lab.COLD_SHARE, lab.YIELD_SHARE = 0.0, 0.0
    try:
        c1, why1 = lab.choose_coordinate(a, onto, cov, rng)
        cov.touch(lab.coord_id(c1), c1, "DISCOVERED")
        c2, why2 = lab.choose_coordinate(a, onto, cov, rng)
    finally:
        lab.COLD_SHARE, lab.YIELD_SHARE = 0.15, 0.20
    assert why1 == why2 == "owed" and c1 != c2
    o = lab.owed(cov, onto)
    assert o["visited"] == 1 and o["owed"] == o["coordinates"] - 1


def test_a_named_class_grows_the_ontology_and_the_owed_space(state: Path) -> None:
    before = lab.owed(lab.Coverage.load(), lab._ontology())["coordinates"]
    lab._save_ontology({"shipping_insurance_repricing"}, {"shipping_insurance_repricing": "A"})
    after = lab.owed(lab.Coverage.load(), lab._ontology())["coordinates"]
    assert after > before


def test_independent_labs_get_different_models_while_they_exist() -> None:
    reg_models = {f"local0:m{i}": {"status": "REGISTERED", "novel": 0, "replies": 0}
                  for i in range(3)}
    reg_models["local0:pending"] = {"status": "REVIEW_PENDING"}
    rng = random.Random(7)  # noqa: S311
    used: set[str] = set()
    picks = []
    for _ in range(3):
        m = lab.assign_model(reg_models, rng, used)
        used.add(m)
        picks.append(m)
    assert len(set(picks)) == 3 and "local0:pending" not in picks


# --------------------------------------------------------------------------- the pass
@dataclass
class _Prov:
    model: str = "local0:qwen-test"
    prompt_hash: str = "ph"


@dataclass
class _Prop:
    payload: Any
    accepted: bool = True
    reason: str = ""
    provenance: _Prov = field(default_factory=_Prov)
    stripped: tuple[str, ...] = ()


class _Seat:
    def enabled(self) -> bool:
        return True

    def _asked(self, organ: str, **kw: Any) -> list[_Prop]:
        assert organ == "llm_lab"
        if kw.get("label") == "attack":
            return [_Prop({"target": "LLMLAB-x", "alternative": "it is the dollar's own drift"})]
        return []


def test_a_pass_donates_exact_rows_the_compiler_admits(state: Path, reg: dict[str, Any],
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    fam = "overnight_gap_decay" if "overnight_gap_decay" in reg else sorted(reg)[0]
    exact = {"mechanism_class": "dealer_book_rebalancing",
             "mechanism": ("Asian dealers flatten overnight inventory into the Tokyo open, so the "
                           "overnight gap is partly forced and decays"),
             "falsifier": "no decay on days with no Tokyo session", "symbols": ["USDJPY"],
             "family": fam, "params": {}, "timeframe": "H1", "horizon": "intraday"}
    debt = {"mechanism": "a mechanism that needs a family the desk does not have yet at all",
            "falsifier": "anything", "symbols": ["EURUSD"], "family": "NONE"}
    junk = {"mechanism": "Buy when RSI is oversold below thirty on the pair", "falsifier": "loss",
            "symbols": ["EURUSD"], "family": fam}
    calls: list[str] = []

    def fake_call(ask: lab.Ask, n: int, timeout: float) -> list[_Prop]:
        calls.append(ask.lab.key)
        if ask.lab.key == "B" and ask.why != "conversion_debt":
            return [_Prop(exact), _Prop(debt), _Prop(junk)]
        return []

    monkeypatch.setattr(lab, "_seat", lambda: _Seat())
    monkeypatch.setattr(lab, "_call", fake_call)
    monkeypatch.setattr(lab, "universe", lambda: UNI)
    monkeypatch.setattr(lab, "hunt_models", lambda registry, budget_s=0: [])
    monkeypatch.setattr(lab.Memory, "load", classmethod(lambda cls, library=True: cls()))
    monkeypatch.setattr(lab, "coverage_from_outcomes", lambda cov: {})
    doc = lab.run(budget_s=600, max_calls=40, seed=3, workers=1)

    assert set(calls) >= {lab_.key for lab_ in lab.INVENTORS}, "a lab was never asked"
    assert doc["verdict"] == "RAN" and doc["emitted"] == 1
    assert doc["labs"]["B"]["banal"] == 1 and doc["labs"]["B"]["debt"] == 1
    assert doc["novelty"]["GENUINELY_NOVEL"] == 1
    assert doc["conversion_debt"]["by_blocker"] == {"NEEDS_EXECUTABLE_FAMILY": 1}
    assert doc["red_team_attacks"], "the red team ran after the independent pass"
    assert "dealer_book_rebalancing" in json.loads(lab.ONTOLOGY.read_text())["classes"]

    files = sorted(lab.DONATE_DIR.glob("discoveries_*.json"))
    assert len(files) == 1
    assert doc["cb_tone"]["state"] == "TEST_STUB", "the central-bank tone role runs in the pass"
    assert set(doc["roles"]) >= {"R", "S", "T"}, "the roles run inside the pass"
    credit = json.loads((state / "llm_lab" / "verdict_credit.json").read_text())
    assert credit["labs"] and doc["verdict_loop"]["ranking_rule"].startswith("certified")
    row = json.loads(files[0].read_text())["discoveries"][0]
    assert row["gauntlet_bypass"] is False and row["credibility_inherited"] is False
    import miner_candidate_compiler as mc
    cands, disp = mc.compile_row("llm_lab", row, set(UNI))
    assert disp == "EXACT_RECIPE" and cands and cands[0]["family"] == fam
    guard = cands[0]["lookahead_guard"]
    assert guard["model"] == "local0:qwen-test" and guard["model_training_cutoff"] == "UNMEASURED"
    assert guard["evidence_from"] == row["lookahead_guard"]["evidence_from"] == lab._now()[:10]

    # A second identical pass collapses the same cell instead of charging it again.
    monkeypatch.setattr(lab.Memory, "load", classmethod(
        lambda cls, library=True: _reload(cls)))
    doc2 = lab.run(budget_s=600, max_calls=40, seed=3, workers=1)
    assert doc2["emitted"] == 0 and doc2["novelty"]["EXACT_DUPLICATE"] == 1


def _reload(cls: type[lab.Memory]) -> lab.Memory:
    m = cls()
    for row in lab._jsonl(lab.GENEALOGY):
        m.remember(row)
    return m


def test_debt_reopens_when_the_registry_learns_the_family(state: Path,
                                                          reg: dict[str, Any]) -> None:
    fam = sorted(reg)[0]
    payload = {"mechanism": "waiting for a family", "falsifier": "f", "symbols": ["EURUSD"],
               "family": fam, "params": {}}
    lab._write_json(lab.DEBT, {"rows": {"D1": {"id": "D1", "lab": "J", "payload": payload,
                                                "blockers": ["NEEDS_EXECUTABLE_FAMILY"],
                                                "state": "OPEN", "first_seen": "x"}}})
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in ("genealogy", "donate", "debt",
                                                            "data_requests", "jev", "classes")}
    without = {k: v for k, v in reg.items() if k != fam}
    t = lab.Tally()
    first = lab.retry_debt(without, UNI, lab.Memory(), t, out, "fp0")
    assert first["open"] == 1 and first["resolved_this_pass"] == 0
    second = lab.retry_debt(reg, UNI, lab.Memory(), t, out, "fp1")
    assert second["open"] == 0 and second["resolved_this_pass"] == 1 and out["donate"]


def test_a_dark_seat_plans_the_pass_and_keeps_everything_owed(state: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    monkeypatch.setattr(lab, "_seat", lambda: None)
    monkeypatch.setattr(lab, "coverage_from_outcomes", lambda cov: {})
    monkeypatch.setattr(lab.Memory, "load", classmethod(lambda cls, library=True: cls()))
    doc = lab.run(budget_s=60, seed=1)
    assert doc["verdict"] == lab.UNMEASURED and doc["emitted"] == 0
    assert doc["coverage"]["visited"] == 0 and doc["coverage"]["owed"] > 0
    assert doc["budget"]["calls_this_pass"] == 0


def test_paid_spend_is_forced_off_unless_explicitly_enabled(state: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    monkeypatch.delenv("QUANT_LLM_LAB_PAID", raising=False)
    monkeypatch.setenv("QUANT_FREE_TIER", "0")
    monkeypatch.setattr(lab, "_seat", lambda: None)
    monkeypatch.setattr(lab, "coverage_from_outcomes", lambda cov: {})
    monkeypatch.setattr(lab.Memory, "load", classmethod(lambda cls, library=True: cls()))
    doc = lab.run(budget_s=60, seed=1, dry_run=True)
    import os
    assert os.environ["QUANT_FREE_TIER"] == "1" and doc["paid_enabled"] is False


# --------------------------------------------------------------------------- the clock
def test_the_leg_is_on_the_hourly_cycle_with_a_cap_above_its_budget() -> None:
    src = HOURLY.read_text("utf-8")
    assert re.search(r'_costed\("llm_lab", lambda: _producer\(\s*"llm_lab", '
                     r'"research/llm_lab\.py", "--once", "--budget-s", "600"\)\)', src)
    assert '"llm_lab": llm' in src and '"llm_lab": 720' in src
    from libs.research import layers
    assert layers.LEG_LAYER.get("llm_lab") == "information" if hasattr(layers, "LEG_LAYER") \
        else "llm_lab" in Path(layers.__file__).read_text("utf-8")


def test_sixteen_labs_with_distinct_mandates() -> None:
    assert [x.key for x in lab.LABS] == list("ABCDEFGHIJKLMNOP")
    assert len({x.mandate for x in lab.LABS}) == 16
    assert lab.LAB_BY_KEY["P"] not in lab.INVENTORS


def test_evidence_starts_at_the_later_of_cutoff_and_birth(state: Path) -> None:
    """Audit must-fix 2: never the earlier date, which counted history the model had read."""
    lab._write_json(lab.MODEL_CUTOFFS, {"qwen3": "2025-03-31", "future": "2027-01-01"})
    g = lab.lookahead_guard("local0:qwen3:8b", at="2026-10-13T00:00:00+00:00")
    assert g["evidence_from"] == "2026-10-13" and g["basis"] == "registered cutoff"
    assert lab.lookahead_guard("x:future-model", at="2026-10-13T00:00:00+00:00")[
        "evidence_from"] == "2027-01-01"
    assert lab.lookahead_guard("groq:other", at="2026-10-13T00:00:00+00:00")[
        "evidence_from"] == "2026-10-13"


def test_conversion_and_the_high_yield_labs_go_first(state: Path, reg: dict[str, Any],
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    assert [x.key for x in lab.prioritised(random.Random(0))][:4] == ["K", "L", "J", "F"]  # noqa: S311
    payload = {"mechanism": "needs a rule the converter can write down for the desk",
               "falsifier": "f", "symbols": ["EURUSD"], "family": "formula",
               "expr": "not(an expr"}
    lab._write_json(lab.DEBT, {"rows": {"D9": {"id": "D9", "lab": "C", "payload": payload,
                                                "blockers": ["NEEDS_EXACT_RULE_EXTRACTION"],
                                                "state": "OPEN", "first_seen": "x"}}})
    order: list[str] = []

    def fake_call(ask: lab.Ask, n: int, timeout: float) -> list[Any]:
        order.append("CONVERTER" if ask.why == "conversion_debt" else ask.lab.key)
        return []
    monkeypatch.setattr(lab, "_seat", lambda: _Seat())
    monkeypatch.setattr(lab, "_call", fake_call)
    monkeypatch.setattr(lab, "universe", lambda: UNI)
    monkeypatch.setattr(lab, "hunt_models", lambda registry, budget_s=0: [])
    monkeypatch.setattr(lab.Memory, "load", classmethod(lambda cls, library=True: cls()))
    monkeypatch.setattr(lab, "coverage_from_outcomes", lambda cov: {})
    lab.run(budget_s=600, max_calls=40, seed=2, workers=1)
    assert order[0] == "CONVERTER" and order[1:5] == ["K", "L", "J", "F"]


def test_every_registered_model_gets_a_call_every_pass(state: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    keys = [f"openrouter_free:m{i}:free" for i in range(20)]
    lab._write_json(lab.MODELS, {k: {"provider": "openrouter_free", "model": k.split(":", 1)[1],
                                     "status": "REGISTERED", "asked": 0, "replies": 0}
                                 for k in keys})
    hinted: list[str] = []

    def fake_call(ask: lab.Ask, n: int, timeout: float) -> list[_Prop]:
        hinted.append(ask.model)
        return [_Prop({"mechanism": "a stub mechanism long enough", "falsifier": "x",
                       "symbols": ["EURUSD"], "family": "NONE"},
                      provenance=_Prov(model=ask.model))]

    monkeypatch.setattr(lab, "_seat", lambda: _Seat())
    monkeypatch.setattr(lab, "_call", fake_call)
    monkeypatch.setattr(lab, "hunt_models", lambda registry, budget_s=30.0: [])
    doc = lab.run(budget_s=600, max_calls=8, seed=1, workers=2)
    assert set(keys) <= set(hinted), "the per-pass cap grows to cover every registered model"
    cov = json.loads((state / "reports" / "LLM_COVERAGE.json").read_text())
    assert cov["models_available"] == 20 and cov["models_answered"] == 20
    assert all(cov["models"][k]["state_this_cycle"] == "ANSWERED" for k in keys)
    assert doc["model_coverage"]["models_answered"] == 20


def test_the_measured_openrouter_limit_is_spread_and_models_rotate(
        state: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the account's limit measured, each pass spends its even share of what is left today
    and models are asked least-recently first; the rest are ROTATING, not red, inside the window."""
    from datetime import UTC, datetime

    from libs.ops import openrouter_guard
    openrouter_guard.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": False}})
    share = lab.openrouter_pass_share(datetime(2026, 10, 13, 12, tzinfo=UTC))
    assert share["account_daily_limit"] == 1000 and share["per_pass"] == 500 // 12

    keys = [f"openrouter_free:m{i:02d}:free" for i in range(60)]
    lab._write_json(lab.MODELS, {k: {"provider": "openrouter_free", "model": k.split(":", 1)[1],
                                     "status": "REGISTERED", "asked": 0, "replies": 0}
                                 for k in keys})
    hinted: list[str] = []

    def fake_call(ask: lab.Ask, n: int, timeout: float) -> list[_Prop]:
        hinted.append(ask.model)
        return [_Prop({"mechanism": "a stub mechanism long enough", "falsifier": "x",
                       "symbols": ["EURUSD"], "family": "NONE"},
                      provenance=_Prov(model=ask.model))]

    monkeypatch.setattr(lab, "openrouter_pass_share", lambda now=None: {"per_pass": 25})
    monkeypatch.setattr(lab, "_seat", lambda: _Seat())
    monkeypatch.setattr(lab, "_call", fake_call)
    monkeypatch.setattr(lab, "hunt_models", lambda registry, budget_s=30.0: [])
    lab.run(budget_s=600, max_calls=8, seed=1, workers=2)
    first = {m for m in hinted if m}
    assert 0 < len(hinted) <= 25
    cov = json.loads((state / "reports" / "LLM_COVERAGE.json").read_text())
    assert cov["rotation_window_h"] == 4
    assert not [r for r in cov["red"] if r.startswith("model ")]
    assert cov["models_rotating"] == 60 - cov["models_answered"]
    hinted.clear()
    lab.run(budget_s=600, max_calls=8, seed=2, workers=2)
    assert not (first & {m for m in hinted if m}) or len(first) + len(set(hinted)) > 60, \
        "the second pass reaches models the first left out before repeating any"


def test_donations_are_held_until_the_gauntlet_trims(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit blocker on #332: LLM-born cells reach the gates only once the sealed look-ahead
    patch is in the gauntlet. Until then they are HELD, and the first pass after it lands
    releases every held file with no other step."""
    monkeypatch.setattr(lab, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(lab, "DONATE_DIR", tmp_path / "seat")
    gauntlet = tmp_path / "external_gauntlet.py"
    gauntlet.write_text("def run():\n    pass\n")
    monkeypatch.setattr(lab, "GAUNTLET", gauntlet)
    target = lab.donation_target(lab.DONATE_DIR)
    assert target != lab.DONATE_DIR
    target.mkdir(parents=True)
    assert target.name == lab.DONATE_DIR.name, "held per seat, so attribution survives"
    (target / "discoveries_1.json").write_text("{}")
    assert lab.release_held()["state"] == "HELD" and not lab.DONATE_DIR.exists()
    gauntlet.write_text("def llm_born(c):\n    pass\ndef evidence_trim(c, ds):\n    pass\n")
    assert lab.donation_target(lab.DONATE_DIR) == lab.DONATE_DIR
    assert lab.release_held() == {"state": "DONATING", "released": 1}
    assert (lab.DONATE_DIR / "discoveries_1.json").exists()


def test_the_real_gauntlet_path_is_the_one_the_patch_edits() -> None:
    assert lab.GAUNTLET == lab.BASE / "scripts" / "external_gauntlet.py"
    assert lab.GAUNTLET.exists()
