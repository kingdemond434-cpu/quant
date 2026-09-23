"""A SYNTHETIC GRAVEYARD WITH ONE KNOWN DEATH OF EVERY KIND, and the organ has to name each one.

An organ that reopens graves is the last place a guess may pass for a diagnosis: whatever it
resurrects spends the same family-wise error budget every live hypothesis is charged against. So
the fixture buries one cell per failure class with the gate that caused it, plus the two that
must NOT spawn anything, and every test asserts the organ (a) named the class from the gate and
NOT from the family, (b) answered the cluster's questions from its own siblings with an n, and
(c) produced exactly the repair that class licenses.

The other half of the contract, which matters as much: `no_edge` and `redundant` lower the
mechanism prior instead of spawning; an unrecognised gate stays UNMEASURED rather than being
bucketed into the nearest class; the inverse is REFUSED where the ontology says the payer pays one
way; a cell the graph already carries is never re-donated; one family may never take more than
half the run's candidates; five identical deaths raise a counter-hypothesis; the discovery's
counters walk EXPANDED -> COMPILED -> QUEUED; the budget stops the sweep with its verdicts
deferred rather than invented; and `--dry-run` writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import axis_registry as ar  # noqa: E402
from research import graveyard_resurrection as gr  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: Six FX majors and one metal in the hypothesis lane, one equity that the two-lane mandate keeps
#: out of it. `bars` orders `instruments_by_class`, so the transfer targets are deterministic.
UNIVERSE = {
    "EURUSD": {"asset_class": "Forex Majors", "bars": 60000},
    "GBPUSD": {"asset_class": "Forex Majors", "bars": 50000},
    "AUDUSD": {"asset_class": "Forex Majors", "bars": 40000},
    "USDCHF": {"asset_class": "Forex Majors", "bars": 30000},
    "NZDUSD": {"asset_class": "Forex Majors", "bars": 20000},
    "USDCAD": {"asset_class": "Forex Majors", "bars": 10000},
    "XAUUSD": {"asset_class": "Metals", "bars": 70000},
    "APPLE": {"asset_class": "Equities", "bars": 9000},
}
#: (mechanism, information_source, execution_style) per family, as `axis_registry` holds it.
#: `carry_roll` is the one-way payer; `range_fade` is two-sided; `gap_decay`/`gap_limit` are two
#: expressions of ONE mechanism, which is what the combination move needs.
FAMILIES = {
    "gap_decay": ("session_handover", "price_only", "market"),
    "gap_limit": ("session_handover", "price_only", "limit"),
    "carry_roll": ("carry_rollover", "carry", "market"),
    "range_fade": ("range_reversion", "price_only", "limit"),
    "vol_break": ("breakout_liquidity", "price_only", "stop"),
}
DEFLATED = {"deflated_sharpe": {"passed": False}}


def _row(cid: str, sym: str, fam: str, fate: str, gates: dict[str, Any] | None = None,
         params: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {"id": cid, "symbol": sym, "family": fam, "fate": fate, "params": params or {},
            "gates": gates or {}, "source": "external", "at": f"2026-09-1{len(cid) % 7}", **extra}


def _graph() -> list[dict[str, Any]]:
    rows = [
        # ---- one family with a survivor elsewhere: a no_edge death here is the WRONG ASSET.
        _row("g_cert", "GBPUSD", "gap_decay", "CERTIFIED"),
        _row("g_noedge", "EURUSD", "gap_decay", "FAILED", DEFLATED, exp_r=0.01, t_stat=1.1),
        # A third judged sibling, so the family's questions clear MIN_SIBLINGS and are MEASURED.
        _row("g_unstable", "NZDUSD", "gap_decay", "FAILED", {"walk_forward": {"passed": False}}),
        # ---- the same MECHANISM alive under a different family: the combination move's evidence.
        _row("gl_cert", "AUDUSD", "gap_limit", "CERTIFIED"),
        _row("gl_dup", "USDCHF", "gap_limit", "FAILED", {"novelty_duplicate": {"passed": False}}),
        # ---- one death per repairable class, all in a family with no survivor anywhere.
        _row("r_cost", "EURUSD", "range_fade", "FAILED", {"stress_costs": {"passed": False}},
             {"lookback": 30, "entry_z": 2.0}),
        _row("r_unstable", "GBPUSD", "range_fade", "FAILED", {"walk_forward": {"passed": False}},
             {"lookback": 20}),
        _row("r_horizon", "AUDUSD", "range_fade", "FAILED", {"holding_period": {"passed": False}},
             {"ttl_bars": 8}),
        _row("r_exec", "USDCHF", "range_fade", "FAILED", {"slippage_model": {"passed": False}},
             {"atr_mult": 1.5}),
        _row("r_regime", "NZDUSD", "range_fade", "FAILED", {"one_regime_only": {"passed": False}},
             {"lookback": 15}),
        _row("r_flip", "USDCAD", "range_fade", "FAILED", DEFLATED, {"side": 1},
             exp_r=-0.02, t_stat=-3.1),
        _row("r_mystery", "XAUUSD", "range_fade", "FAILED", {"mystery_gate": {"passed": False}}),
        # ---- the widened repair of r_unstable ALREADY EXISTS in the graph: never re-donated.
        _row("r_known", "GBPUSD", "range_fade", "BORN", None, {"lookback": 40}),
        # ---- a one-way payer whose sign may not be mirrored.
        _row("c_flip", "EURUSD", "carry_roll", "FAILED", DEFLATED, {"side": 1},
             exp_r=-0.02, t_stat=-4.0),
    ]
    # ---- five identical no_edge deaths: barren ground, a lowered prior and a counter-hypothesis.
    rows += [_row(f"v_{s}", s, "vol_break", "FAILED", DEFLATED, exp_r=0.005, t_stat=0.4)
             for s in ("EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "NZDUSD")]
    return rows


GRAVEYARD_MD = """# Graveyard -- rejected hypotheses (do_not_repeat)

## `quarter_hour_clock_phase` -- KILLED 2026-08-12 on the authors' own arithmetic

The effect is 0.5bp against a 10bp round trip. Tagged `costs_killed_edge` and `crowded_known`.

### cash_and_carry_lore (RU 2014) -- CORROBORATED
Tagged `mechanism_refuted`.
"""


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A whole synthetic desk: tmp registry, tmp graph/ledger/shadow/graveyard, captured donate."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")

    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(ar, "UNIVERSE", uni)
    monkeypatch.setattr(ar, "FAMILY_TABLE", dict(FAMILIES))
    up._registry.cache_clear()

    graph = tmp_path / "hypothesis_graph.jsonl"
    graph.write_text("\n".join(json.dumps(r) for r in _graph()), "utf-8")
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in [
        {"cell": "XAUUSD.range_fade.p=abc", "sym": "XAUUSD", "family": "range_fade",
         "passed": False, "terminal_gate": "swap_cost", "at": "2026-09-16"},
        {"cell": "EURUSD.gap_decay.p=abc", "sym": "EURUSD", "family": "gap_decay",
         "passed": True, "terminal_gate": "PASSED", "at": "2026-09-16"},
    ]), "utf-8")
    shadow = tmp_path / "shadow_state.json"
    shadow.write_text(json.dumps({
        "NZDUSD.gap_decay": {"status": "RETIRED_ORPHAN", "n": 9, "exp_r": -0.01,
                             "gate_admission": "ORIGINAL_UNIVERSAL_10_PASS",
                             "last_attempt_at": "2026-09-15"},
        "USDCAD.gap_decay": {"status": "RETIRED_ORPHAN", "n": 2, "exp_r": 0.0,
                             "last_attempt_at": "2026-09-15"},      # never certified: not a decay
        "EURUSD.gap_decay": {"status": "ACTIVE", "n": 30},
    }), "utf-8")
    md = tmp_path / "graveyard.md"
    md.write_text(GRAVEYARD_MD, "utf-8")

    monkeypatch.setattr(gr, "GRAPH", graph)
    monkeypatch.setattr(gr, "GATE_LEDGER", ledger)
    monkeypatch.setattr(gr, "SHADOW", (shadow,))
    monkeypatch.setattr(gr, "GRAVEYARD_MD", md)
    monkeypatch.setattr(gr, "OUT", tmp_path / "GRAVEYARD_RESURRECTION.json")

    donated: list[dict[str, Any]] = []

    def _donate(source: str, rows: list[dict[str, Any]], tests_run: int) -> Path:
        donated.extend(rows)
        return tmp_path / f"discoveries_{source}.json"

    monkeypatch.setattr(gr.pc, "donate", _donate)
    monkeypatch.setattr(gr.pc, "donation_counts", lambda: {"donated": len(donated)})
    yield {"tmp": tmp_path, "donated": donated, "md": md, "out": tmp_path /
           "GRAVEYARD_RESURRECTION.json"}
    R.set_path(None)


def _by_kind(donated: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in donated:
        out.setdefault(str(row["evidence"]["kind_of_move"]), []).append(row)
    return out


def _cluster(doc: dict[str, Any], family: str, cls: str) -> dict[str, Any]:
    for c in doc["clusters"]:
        if c["family"] == family and c["failure_class"] == cls:
            return c
    raise AssertionError(f"no {family}/{cls} cluster in {[c['family'] for c in doc['clusters']]}")


# ------------------------------------------------------------------ 1. classification
@pytest.mark.parametrize(("gate", "cls"), [
    ("stress_costs", "cost_killed"), ("swap_cost", "cost_killed"), ("turnover_cap", "cost_killed"),
    ("one_regime_only", "regime_specific"), ("regime_split", "regime_specific"),
    ("deflated_sharpe", "no_edge"), ("reality_check", "no_edge"), ("in_sample_screen", "no_edge"),
    ("walk_forward", "unstable"), ("parameter_stability", "unstable"),
    ("novelty_duplicate", "redundant"), ("correlation_with_book", "redundant"),
    ("slippage_model", "execution_killed"), ("fill_refusal", "execution_killed"),
    ("holding_period", "wrong_horizon"),
])
def test_classification_reads_the_terminal_gate(gate: str, cls: str) -> None:
    assert gr.classify_failure(gate) == cls
    assert cls in R.FAILURE_CLASSES


def test_an_unrecognised_or_absent_gate_stays_unmeasured() -> None:
    for gate in ("mystery_gate", "", None, "UNKNOWN"):
        assert gr.classify_failure(gate) == "UNMEASURED"


def test_a_negative_expectancy_at_a_real_t_is_wrong_direction_not_no_edge() -> None:
    # The same gate, two evidence sets: the sign is a MEASUREMENT, not a re-reading of the gate.
    assert gr.classify_failure("deflated_sharpe", {"exp_r": 0.01, "t_stat": 1.0}) == "no_edge"
    assert gr.classify_failure("deflated_sharpe",
                               {"exp_r": -0.02, "t_stat": -3.1}) == "wrong_direction"
    # A negative mean with no |t| behind it is noise, and noise is not a mirrored sign.
    assert gr.classify_failure("deflated_sharpe", {"exp_r": -0.02, "t_stat": -0.4}) == "no_edge"
    assert gr.classify_failure("", {"exp_r": -0.02, "t_stat": -3.1}) == "wrong_direction"


def test_a_retired_certificate_is_forward_decay() -> None:
    assert gr.classify_failure("forward_retirement", {"forward_retired": True}) == "forward_decay"


def test_every_failure_class_the_organ_emits_is_one_the_registry_declares() -> None:
    emitted = {cls for _, cls in gr.GATE_CLASS} | {"forward_decay", "wrong_direction",
                                                   "wrong_asset"}
    assert emitted <= set(R.FAILURE_CLASSES)
    assert set(gr.RESURRECTION) | set(gr.BARREN) <= set(R.FAILURE_CLASSES)


def test_the_verdict_is_written_onto_the_candidate_when_one_exists(desk) -> None:
    R.enqueue_candidate(family="range_fade", symbol="EURUSD", params={"lookback": 30},
                        origin="EXTERNAL", mechanism="range_reversion", candidate_id="r_cost")
    doc = gr.build(max_rows=500)
    row = next(c for c in R.candidates() if c["id"] == "r_cost")
    assert row["failure_class"] == "cost_killed" and row["status"] == "judged"
    assert doc["verdicts_written"]["marked_judged"] >= 1


# ------------------------------------------------------------------ 2. the questions
def test_the_questions_are_answered_from_siblings_and_carry_their_n(desk) -> None:
    doc = gr.build(max_rows=500)
    q = _cluster(doc, "range_fade", "cost_killed")["questions"]
    assert set(q) == {
        "did_it_fail_everywhere", "only_high_vol", "only_asia", "only_xau", "only_after_costs",
        "only_because_of_entry", "did_the_opposite_direction_work", "did_the_residual_form_work",
        "did_another_asset_preserve_the_mechanism",
        "was_the_mechanism_right_and_the_expression_wrong"}
    # range_fade has seven judged siblings and no survivor: it DID fail everywhere, n carried.
    assert q["did_it_fail_everywhere"]["answer"] is True
    assert q["did_it_fail_everywhere"]["n"] == 7
    # Two of the seven CLASSIFIED range_fade deaths are cost_killed -- a share, with its n. The
    # eighth death is the unrecognised gate, and an UNMEASURED cell is not counted either way.
    assert q["only_after_costs"]["answer"] is False
    assert q["only_after_costs"]["n"] == 7
    assert q["only_after_costs"]["share"] == pytest.approx(2 / 7, abs=1e-4)
    assert q["only_because_of_entry"]["share"] == pytest.approx(1 / 7, abs=1e-4)
    # Nothing survived anywhere, so nothing can be SPECIFIC to a state -- and that is measured.
    assert q["only_high_vol"]["answer"] is False and q["only_high_vol"]["n_survivors"] == 0

    # The gap_decay cluster has a survivor on another symbol and another expression of the same
    # mechanism, and both answers name what they found.
    g = _cluster(doc, "gap_decay", "wrong_asset")["questions"]
    assert g["did_it_fail_everywhere"]["answer"] is False
    assert g["did_it_fail_everywhere"]["n"] == 3
    assert g["did_another_asset_preserve_the_mechanism"]["answer"] is True
    assert "GBPUSD" in g["did_another_asset_preserve_the_mechanism"]["symbols"]
    assert g["was_the_mechanism_right_and_the_expression_wrong"]["answer"] is True
    assert g["was_the_mechanism_right_and_the_expression_wrong"]["families"] == ["gap_limit"]


def test_a_question_with_too_few_siblings_is_unmeasured_with_its_n(desk) -> None:
    doc = gr.build(max_rows=500)
    q = _cluster(doc, "carry_roll", "wrong_direction")["questions"]
    # One judged carry_roll cell: absence of evidence is UNMEASURED with its count, never a False.
    assert q["did_it_fail_everywhere"]["answer"] == "UNMEASURED"
    assert q["did_it_fail_everywhere"]["n"] == 1
    assert "below" in q["did_it_fail_everywhere"]["why"]
    assert q["did_the_residual_form_work"]["answer"] == "UNMEASURED"
    assert doc["unmeasured"]["questions_unmeasured"] > 0


# --------------------------------------------------------- 3. failure -> the five kinds
def test_each_failure_class_produces_exactly_the_move_it_licenses(desk) -> None:
    doc = gr.build(max_rows=500)
    kinds = _by_kind(desk["donated"])
    assert set(kinds) == {"repair", "conditional", "inverse", "transfer", "combination"}

    cost = next(r for r in kinds["repair"] if r["evidence"]["parent_cell"] == "r_cost")
    assert cost["params"]["timeframe"] == "H4" and cost["params"]["entry_style"] == "limit"
    horizon = next(r for r in kinds["repair"] if r["evidence"]["parent_cell"] == "r_horizon")
    assert horizon["params"]["ttl_bars"] == 16
    execk = next(r for r in kinds["repair"] if r["evidence"]["parent_cell"] == "r_exec")
    assert execk["params"]["entry_delay_bars"] == 1

    cond = next(r for r in kinds["conditional"] if r["evidence"]["parent_cell"] == "r_regime")
    assert cond["params"]["regime"] and cond["evidence"]["failure_class"] == "regime_specific"
    decay = [r for r in kinds["conditional"] if r["evidence"]["failure_class"] == "forward_decay"]
    assert decay and decay[0]["symbol"] == "NZDUSD"       # the retired CERTIFICATE, not the orphan

    inv = kinds["inverse"][0]
    assert inv["evidence"]["parent_cell"] == "r_flip" and inv["params"]["side"] == -1

    transfers = {r["symbol"] for r in kinds["transfer"]}
    assert transfers and transfers <= {"AUDUSD", "USDCHF", "NZDUSD", "USDCAD"}
    assert all(r["family"] == "gap_decay" for r in kinds["transfer"])

    comb = kinds["combination"][0]
    assert comb["family"] == "gap_limit" and comb["symbol"] == "EURUSD"
    assert doc["candidates_donated"] == len(desk["donated"])


def test_no_edge_and_redundant_spawn_nothing_and_lower_the_prior_instead(desk) -> None:
    doc = gr.build(max_rows=500)
    assert not [r for r in desk["donated"]
                if r["evidence"]["failure_class"] in ("no_edge", "redundant")]
    assert _cluster(doc, "vol_break", "no_edge")["resurrections"] == 0
    assert _cluster(doc, "gap_limit", "redundant")["resurrections"] == 0

    priors = {r["mechanism"]: r for r in doc["priors_lowered"]}
    assert priors["breakout_liquidity"]["n_failed"] == 5
    assert priors["breakout_liquidity"]["classes"] == {"no_edge": 5}
    assert priors["session_handover"]["classes"] == {"redundant": 1}
    mem = {m["memory_key"]: m for m in R.memories(category="mechanism_prior")}
    row = mem["prior:breakout_liquidity"]
    assert json.loads(row["metrics_json"]) == {"n_failed": 5, "class": "no_edge"}
    assert row["kind"] == "mechanism_prior"


def test_the_inverse_is_refused_where_the_ontology_forbids_a_mirrored_sign(desk) -> None:
    ok, why = gr.allows_inverse("carry_rollover")
    assert ok is False and "one way" in why
    assert gr.allows_inverse("range_reversion")[0] is True
    assert gr.allows_inverse(ar.UNKNOWN)[0] is False
    assert gr.allows_inverse("FORCED_LIQUIDATION")[0] is False       # the ontology's own id
    assert gr.allows_inverse("CROSS_SECTIONAL_MOMENTUM")[0] is True

    doc = gr.build(max_rows=500)
    assert not [r for r in desk["donated"] if r["family"] == "carry_roll"]
    assert any(r["cell"] == "c_flip" and "inverse refused" in r["why"] for r in doc["refusals"])


def test_a_cell_the_graph_already_carries_is_never_re_donated(desk) -> None:
    doc = gr.build(max_rows=500)
    # r_unstable widens lookback 20 -> 40, and `r_known` already sits there.
    assert not [r for r in desk["donated"]
                if r["evidence"]["parent_cell"] == "r_unstable"]
    assert any(r["cell"] == "r_unstable" and "already carries" in r["why"]
               for r in doc["refusals"])
    hashes = [R.content_hash(r["family"], r["symbol"], r["params"]) for r in desk["donated"]]
    assert len(hashes) == len(set(hashes))                            # and never itself twice


def test_the_graveyards_do_not_repeat_list_blocks_a_family_it_names(desk, monkeypatch) -> None:
    parsed = gr.do_not_repeat(desk["md"])
    assert parsed["status"] == "OK" and parsed["n_entries"] == 2
    assert "costs_killed_edge" in parsed["tags"] and "mechanism_refuted" in parsed["tags"]
    # A whole-name match only: `carry_roll` is not blocked by an entry called cash_and_carry_lore.
    assert gr._blocked("carry_roll", parsed["names"]) == ""
    assert gr._blocked("cash_and_carry_lore", parsed["names"]) == "cash_and_carry_lore"

    killed = desk["tmp"] / "killed.md"
    md_text = "## `range_fade` -- KILLED 2026-09-01\n"
    killed.write_text(md_text + "Tagged `mechanism_refuted`.\n", "utf-8")
    monkeypatch.setattr(gr, "GRAVEYARD_MD", killed)
    doc = gr.build(max_rows=500)
    assert not [r for r in desk["donated"] if r["family"] == "range_fade"]
    assert any("do_not_repeat" in r["why"] for r in doc["refusals"])


def test_an_unreadable_graveyard_is_unmeasured_and_blocks_nothing(desk, monkeypatch) -> None:
    monkeypatch.setattr(gr, "GRAVEYARD_MD", desk["tmp"] / "absent.md")
    doc = gr.build(max_rows=500)
    assert doc["unmeasured"]["graveyard_markdown"] == "UNMEASURED"
    assert doc["candidates_generated"] > 0


# ------------------------------------------------------------------- 4. the cold floor
def test_the_run_is_capped_and_no_family_takes_more_than_half_of_it(desk) -> None:
    doc = gr.build(max_rows=500, max_candidates=4)
    assert doc["caps"]["max_per_family"] == 2
    assert doc["candidates_generated"] <= 4 and len(desk["donated"]) <= 4
    per_family: dict[str, int] = {}
    for r in desk["donated"]:
        key = str(r["evidence"]["trial_family"])
        per_family[key] = per_family.get(key, 0) + 1
    assert per_family and max(per_family.values()) <= 2


def test_an_uncapped_run_still_refuses_the_equity_lane(desk) -> None:
    gr.build(max_rows=500)
    assert "APPLE" not in {r["symbol"].upper() for r in desk["donated"]}


def test_the_budget_stops_the_sweep_and_defers_verdicts_rather_than_inventing_them(desk) -> None:
    doc = gr.build(max_rows=500, budget_s=0.0)
    assert doc["caps"]["budget_stop"] is True
    assert doc["candidates_generated"] == 0 and desk["donated"] == []
    assert doc["verdicts_written"]["deferred"] > 0
    assert doc["verdicts_written"]["marked_judged"] == 0
    assert doc["unmeasured"]["verdicts_deferred_by_budget"] == doc["verdicts_written"]["deferred"]


# ------------------------------------------------------------ 5. the record it leaves
def test_every_resurrection_is_a_discovery_with_parents_and_walked_counters(desk) -> None:
    doc = gr.build(max_rows=500)
    discs = R.discoveries(origin="MOAT")
    assert len(discs) == doc["candidates_generated"] > 0
    for d in discs:
        assert d["state"] == "QUEUED" and d["source_type"] == "graveyard"
        assert d["generator"].startswith("graveyard_resurrection:")
        assert (d["possible_cells"], d["generated_cells"], d["compiled_cells"],
                d["queued_cells"]) == (1, 1, 1, 1)
        assert json.loads(d["parent_ids_json"])                       # the dead cell it came from
    cands = [c for c in R.candidates(origin="MOAT") if c["source_id"] == "graveyard_resurrection"]
    assert len(cands) == len(discs)
    for c in cands:
        assert c["discovery_id"] and c["trial_family"] and c["status"] == "queued"
        assert 0.0 < float(c["novelty_vs_graveyard"]) <= 1.0
    yields = {y["generator"]: y for y in R.generator_yields()
              if y["generator"].startswith("graveyard_resurrection:")}
    assert yields and sum(int(y["generated"]) for y in yields.values()) == len(discs)
    assert sum(int(y["donated"]) for y in yields.values()) == len(discs)


def test_novelty_vs_graveyard_falls_as_the_cluster_repeats_the_same_death(desk) -> None:
    gr.build(max_rows=500)
    by_parent = {r["evidence"]["parent_cell"]: r["novelty_vs_graveyard"] for r in desk["donated"]}
    assert by_parent["r_cost"] == pytest.approx(1 - 2 / (2 + gr.NOVELTY_PSEUDO))
    assert by_parent["r_regime"] == pytest.approx(1 - 1 / (1 + gr.NOVELTY_PSEUDO))


def test_five_identical_deaths_raise_one_counter_hypothesis(desk) -> None:
    doc = gr.build(max_rows=500)
    counters = {c["family"]: c for c in doc["counter_hypotheses"]}
    assert set(counters) == {"vol_break"}                            # the only cluster at n >= 5
    c = counters["vol_break"]
    assert c["n"] == 5 and c["failure_class"] == "no_edge"
    assert c["alternative_mechanism"] == "execution_microstructure"
    mem = R.memories(kind="counter_hypothesis")
    assert len(mem) == 1 and mem[0]["memory_key"].startswith("counter:vol_break:")
    assert json.loads(mem[0]["metrics_json"])["n"] == 5


def test_the_report_names_its_sources_its_rule_and_what_it_could_not_measure(desk) -> None:
    doc = gr.build(max_rows=500)
    assert doc["rule"] == gr.RULE and "lower the prior" in doc["rule"]
    assert doc["n_failed_cells"] == 18                          # 16 graph + 1 ledger + 1 clock
    assert doc["by_failure_class"]["UNMEASURED"] == 1                 # r_mystery, and only it
    assert doc["unmeasured"]["cells_without_a_recognised_gate"] == 1
    assert doc["unmeasured"]["reclassified_no_edge_to_wrong_asset"] == 1
    assert doc["sources"]["forward_clocks"] == 1                 # the uncertified one is not one
    assert doc["sources"]["hypothesis_graph"] == 19
    assert doc["caps"]["explore_floor"] == gr.EXPLORE_FLOOR


# --------------------------------------------------------------------------- 6. the CLI
def test_dry_run_writes_absolutely_nothing(desk, capsys) -> None:
    assert gr.main(["--dry-run", "--max-rows", "500"]) == 0
    assert "nothing written" in capsys.readouterr().out
    assert not desk["out"].exists()
    assert desk["donated"] == []
    assert R.candidates() == [] and R.discoveries() == [] and R.memories() == []


def test_the_cli_writes_the_artifact_atomically(desk, capsys) -> None:
    assert gr.main(["--max-rows", "500", "--max-candidates", "6"]) == 0
    doc = json.loads(desk["out"].read_text("utf-8"))
    assert doc["candidates_generated"] <= 6 and doc["rule"] == gr.RULE
    assert not list(desk["tmp"].glob("*.tmp"))
    assert "graveyard resurrection:" in capsys.readouterr().out
