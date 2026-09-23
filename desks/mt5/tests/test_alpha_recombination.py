"""A RECOMBINATION ENGINE IS A MACHINE FOR MANUFACTURING OVERFITTING UNLESS IT REFUSES.

Two mechanisms multiplied together always fit better than either. Always, on any data. So the
dangerous version of this organ is not the one that finds nothing -- it is the one that ships a
cross product wearing mechanism names, spends the shared family-wise error budget that every FX
and metals cell has to clear, and calls it exploitation. Every test below pins one refusal:

  * ONLY DECLARED INTERACTIONS. A pair of mechanism classes that is not in the table is refused and
    COUNTED, and no combination containing it may ever appear.
  * EVERY COMBINATION CARRIES ITS `why`. One sentence per pair inside it -- which means a triple
    needs all three pairs declared, not two out of three.
  * MAX THREE GENES. Beyond that the `why` stops being readable by whoever has to defend it.
  * THE THREE LANES, AND THE 20% RULE. LIVE/STANDBY sleeves, certificates, and the near-survivors:
    a cell that died on the LAST gate, or whose deflated Sharpe came within 20% of the bar. A cell
    that failed by a mile is not a gene, and a cell that PASSED is not a near-survivor.
  * THE TWO-LANE MANDATE AT THE DOOR. A single-name equity is never a gene.
  * AN UNKNOWN MECHANISM IS COUNTED, NOT COMBINED. No `why` can be written for it.
  * HOSTED OR PAYLOAD, NEVER PRETEND. A tag the primary family's signature cannot carry would be
    dropped by the gauntlet's param filter, so the combination leaves as a `combination` payload
    for the discovery compiler instead of as a cell that is secretly its own parent.
  * PARENTS ARE RECORDED. A combination with no parent ids is untraceable to the genes that cost
    the campaigns to find.
  * THE CAP AND --dry-run BIND.

The mechanism table, the family signatures and the universe policy are all STUBBED here, so these
measure the organ's logic rather than today's contents of the desk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ar = pytest.importorskip("research.alpha_recombination", reason="the organ ships with the desk")
pc = pytest.importorskip("research.proposer_common")
mo = pytest.importorskip("libs.research.mechanism_ontology")
R = pytest.importorskip("libs.moat.registry")

#: The stubbed vocabulary. Each family maps to ONE mechanism class, and the classes are the desk's
#: own (`axis_registry.FAMILY_TABLE`) so the declared interaction table applies unchanged.
CLASS_OF: dict[str, str] = {
    "session_range_breakout": "breakout_liquidity",
    "overnight_gap_decay": "session_handover",
    "event_reaction": "macro_release",
    "carry": "carry_rollover",
    "vol_transition": "regime_transition",
    "cot_positioning": "positioning_crowding",
    "forced_flow": "forced_flow",
    "discovered": ar.UNKNOWN,
}
EQUITIES = {"APPLE"}
#: A pair the table deliberately does NOT declare: a rollover premium and a stop-liquidity break
#: have no mechanism acting between them, and the organ must refuse it every time.
INCOHERENT = frozenset({"carry_rollover", "breakout_liquidity"})


def _verdict(sym: str, family: str, *, passed: bool = False, terminal: str = "in_sample_screen",
             dsr: float | None = None, sr0: float | None = None,
             sharpe: float | None = None) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    if dsr is not None or sr0 is not None:
        stages["deflated_sharpe"] = {"passed": False, "dsr": dsr, "sr0": sr0, "n_trials": 597}
    if sharpe is not None:
        stages["in_sample_screen"] = {"passed": False, "sharpe": sharpe}
    return {"cell": f"{sym}.{family}.p=deadbeef", "sym": sym, "family": family, "passed": passed,
            "terminal_gate": terminal, "stages": stages}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A synthetic gene pool on tmp_path, with the mechanism table, the family signatures, the
    universe policy and the donation door all under the test's control."""
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    bar, _ = ar.dsr_bar()
    final, _ = ar.last_gate()

    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "gold_asia", "symbol": "XAUUSD", "family": "session_range_breakout",
         "timeframe": "H1", "session": "asia", "status": "LIVE", "rr": 2.0, "wait_bars": 12},
        {"name": "eur_gap", "symbol": "EURUSD", "family": "overnight_gap_decay",
         "timeframe": "H1", "session": "all", "status": "STANDBY", "max_hold": 6},
        {"name": "retired", "symbol": "USDCHF", "family": "carry", "status": "RETIRED"},
    ]}), "utf-8")

    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"n": 3,
        "survivors": {
            "c_event": {"cell": "c_event", "sym": "GBPUSD",
                        "shadow_spec": {"symbol": "GBPUSD", "family": "event_reaction",
                                        "selector": "london"},
                        "gates": {"expected_value": {"ev": 0.4}}},
            "c_carry": {"cell": "c_carry", "sym": "AUDUSD",
                        "shadow_spec": {"symbol": "AUDUSD", "family": "carry",
                                        "selector": "all"},
                        "gates": {"expected_value": {"ev": 0.2}}},
            "c_equity": {"cell": "c_equity", "sym": "Apple",
                         "shadow_spec": {"symbol": "Apple", "family": "event_reaction"},
                         "gates": {"expected_value": {"ev": 0.9}}},
            "c_unknown": {"cell": "c_unknown", "sym": "XAGUSD",
                          "shadow_spec": {"symbol": "XAGUSD", "family": "discovered"},
                          "gates": {"expected_value": {"ev": 0.5}}}}}), "utf-8")

    (tmp_path / "reports" / "universal_gates_external.json").write_text(json.dumps({"verdicts": [
        _verdict("USDJPY", "vol_transition", terminal=final),                # the last gate
        _verdict("NZDUSD", "cot_positioning", dsr=0.90 * bar, sr0=0.38),     # within 20%
        _verdict("USDCAD", "forced_flow", sr0=0.38, sharpe=0.90 * 0.38),     # within 20% of sr0
        _verdict("EURJPY", "session_range_breakout", dsr=0.40 * bar, sr0=0.38),   # a mile away
        _verdict("CADJPY", "carry", passed=True, terminal="PASSED"),         # passed: not near
    ]}), "utf-8")
    (tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"cell": "SGDJPY.overnight_gap_decay.p=1", "sym": "SGDJPY",
                    "family": "overnight_gap_decay", "passed": False,
                    "terminal_gate": final}) + "\n", "utf-8")

    monkeypatch.setattr(ar, "SLEEVES", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(ar, "SURVIVORS", tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(ar, "GATES_EXTERNAL",
                        tmp_path / "reports" / "universal_gates_external.json")
    monkeypatch.setattr(ar, "GATE_LEDGER",
                        tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(ar, "OUT", tmp_path / "reports" / "ALPHA_RECOMBINATION.json")
    monkeypatch.setattr(ar, "mechanism_class", lambda f: CLASS_OF.get(str(f), ar.UNKNOWN))
    monkeypatch.setattr(ar, "may_hypothesise", lambda s: str(s).upper() not in EQUITIES)
    #: NO FAMILY TAKES A CONDITION KNOB by default -- which is the measured state of this tree --
    #: so hosting happens only through the session tag every family honours. A test that wants the
    #: signature path puts the knob in here.
    knobs: dict[str, set[str]] = {}
    monkeypatch.setattr(ar, "family_knobs", lambda f: frozenset(knobs.get(str(f), set())))

    donations: list[dict[str, Any]] = []

    def fake_donate(source: str, candidates: list[dict[str, Any]], tests_run: int) -> Path:
        donations.append({"source": source, "candidates": candidates, "tests_run": tests_run})
        return tmp_path / "intake.json"

    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts",
                        lambda: {"donated": len(donations[-1]["candidates"]) if donations else 0})

    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield {"root": tmp_path, "bar": bar, "final": final, "knobs": knobs, "donations": donations}
    R.set_path(None)


def _pairs(combo: dict[str, Any]) -> set[frozenset[str]]:
    mechs = sorted({g["mechanism"] for g in combo["genes"]})
    return {frozenset({a, b}) for i, a in enumerate(mechs) for b in mechs[i + 1:]}


# ------------------------------------------------------------------ the genes
def test_genes_are_gathered_from_the_three_lanes(desk: dict[str, Any]) -> None:
    """LIVE/STANDBY sleeves, ten-gate certificates and near-survivors -- and nothing else. A
    RETIRED sleeve is not a gene, and neither is a cell that failed by a mile."""
    genes, unmeasured = ar.collect({})
    by_lane: dict[str, list[str]] = {}
    for g in genes:
        by_lane.setdefault(g["lane"], []).append(g["symbol"])
    assert sorted(by_lane["LIVE"]) == ["XAUUSD"]
    assert sorted(by_lane["STANDBY"]) == ["EURUSD"]
    assert sorted(by_lane["CERTIFIED"]) == ["AUDUSD", "GBPUSD"]
    assert sorted(by_lane["NEAR_SURVIVOR"]) == ["NZDUSD", "SGDJPY", "USDCAD", "USDJPY"]
    symbols = {g["symbol"] for g in genes}
    assert "USDCHF" not in symbols, "a RETIRED sleeve is not a gene"
    assert "EURJPY" not in symbols, "a cell that failed by a mile is not a near-survivor"
    assert "CADJPY" not in symbols, "a cell that PASSED is a certificate's business, not a near"
    assert "Apple" not in symbols and "APPLE" not in symbols
    assert "XAGUSD" not in symbols
    lane = next(u for u in unmeasured if u["what"] == "genes refused by the two-lane mandate")
    assert lane["symbols"] == ["Apple"]
    unknown = next(u for u in unmeasured
                   if u["what"] == "cells whose family has no named mechanism")
    assert unknown["n"] >= 1


def test_the_twenty_percent_rule_admits_and_refuses(desk: dict[str, Any]) -> None:
    """THE NEAR-SURVIVOR RULE, on its own. The last gate admits; within 20% of the deflated bar
    admits and records the ratio; a mile away refuses; and a PASS is never a near-survivor."""
    bar, final = desk["bar"], desk["final"]
    last = ar.near_survivor(_verdict("A", "carry", terminal=final), bar, final)
    assert last is not None and "last gate" in last["near_basis"]
    near = ar.near_survivor(_verdict("B", "carry", dsr=0.85 * bar, sr0=0.38), bar, final)
    assert near is not None and near["ratio"] == pytest.approx(0.85, abs=1e-3)
    edge = ar.near_survivor(_verdict("C", "carry", dsr=(1 - ar.NEAR_FRAC) * bar), bar, final)
    assert edge is not None, "exactly at the 20% line is INSIDE it"
    far = ar.near_survivor(_verdict("D", "carry", dsr=0.70 * bar, sr0=0.38), bar, final)
    assert far is None
    by_sharpe = ar.near_survivor(_verdict("E", "carry", sr0=0.40, sharpe=0.33), bar, final)
    assert by_sharpe is not None and "sr0" in by_sharpe["near_basis"]
    assert ar.near_survivor(_verdict("F", "carry", passed=True, terminal="PASSED"),
                            bar, final) is None


# ------------------------------------------------------------------ coherence
def test_only_declared_interactions_are_generated(desk: dict[str, Any]) -> None:
    """THE HEADLINE REFUSAL. Every pair inside every combination must be in the table, and the
    pair the table does not declare must be refused, counted, and absent from the output."""
    table, _ = ar.interaction_table()
    report, combos = ar.build()
    assert combos
    for c in combos:
        for pair in _pairs(c):
            assert pair in table, f"{sorted(pair)} was generated with no declared interaction"
        assert INCOHERENT not in _pairs(c)
    refused = report["refused_incoherent"]
    assert refused["n_refused"] > 0
    key = " x ".join(sorted(INCOHERENT))
    assert key in refused["by_pair"], "the refusal is counted by the pair that caused it"
    assert refused["samples"] and "no declared interaction" in refused["samples"][0]["why_refused"]


def test_two_genes_of_the_same_mechanism_class_are_refused(desk: dict[str, Any]) -> None:
    """Two breakouts are not a recombination: there is no second mechanism to interact with, and
    the pair would spend a trial to rediscover the first gene."""
    report, combos = ar.build()
    for c in combos:
        assert len({g["mechanism"] for g in c["genes"]}) == c["n_genes"]
    assert report["refused_incoherent"]["by_pair"].get("same_mechanism_class", 0) >= 1


def test_every_combination_records_why(desk: dict[str, Any]) -> None:
    """A combination with no stated reason is a cross product. One sentence PER PAIR, so a triple
    owes three."""
    _, combos = ar.build()
    for c in combos:
        assert isinstance(c["why"], list) and len(c["why"]) == len(_pairs(c))
        assert all(" x " in w and len(w) > 40 for w in c["why"])


def test_no_combination_exceeds_three_genes(desk: dict[str, Any]) -> None:
    """MAX THREE, and a triple only where all three pairs are declared."""
    table, _ = ar.interaction_table()
    _, combos = ar.build()
    assert combos
    assert all(2 <= c["n_genes"] <= ar.MAX_GENES <= 3 for c in combos)
    assert all(len(c["genes"]) == c["n_genes"] for c in combos)
    triples = [c for c in combos if c["n_genes"] == 3]
    assert triples, "the fixture holds a coherent triple and it must be reachable"
    for c in triples:
        assert len(_pairs(c)) == 3 and all(p in table for p in _pairs(c))


def test_a_triple_with_one_undeclared_pair_is_refused(desk: dict[str, Any]) -> None:
    """Two thirds of a `why` is not a `why`."""
    table, _ = ar.interaction_table()
    ok, whys = ar.coherent(("breakout_liquidity", "session_handover", "macro_release"), table)
    assert ok and len(whys) == 3
    bad, none = ar.coherent(("breakout_liquidity", "session_handover", "carry_rollover"), table)
    assert bad is False and none == []


# ------------------------------------------------------------------ expression
def test_a_session_tag_is_hosted_by_the_primary_family(desk: dict[str, Any]) -> None:
    """EVERY family honours `params["session"]` -- `family_call.signals` pops it and applies
    `session_filter` -- so a gene carrying a real window can always lend it."""
    _, combos = ar.build()
    hosted = [c for c in combos if c["hosted_by"]]
    assert hosted, "the fixture has genes on asia and london windows"
    c = hosted[0]
    assert c["hosted_by"] == c["primary"]
    session_tags = [t for t in c["tags"] if t["kind"] == "session"]
    assert session_tags and all(t["knob"] == "session" for t in session_tags)
    assert c["params"]["session"] in {"asia", "london"}
    assert all(t["knob"] is not None for t in c["tags"])


def test_an_unhostable_tag_leaves_as_a_combination_payload(desk: dict[str, Any]) -> None:
    """No registered family reads a regime knob on this tree, so a regime tag must NOT be written
    into params and pretended: the combination goes to the discovery compiler as a payload."""
    _, combos = ar.build()
    loose = [c for c in combos if not c["hosted_by"]]
    assert loose, "carry x regime_transition has no window to lend and no knob to land in"
    c = loose[0]
    assert c["hosted_by"] is None
    assert any(t["knob"] is None for t in c["tags"])
    assert "wearing a label" in c["host_note"]
    created, queued = ar.record([c], {})
    assert created == 1
    row = R.discoveries()[0]
    payload = json.loads(row["payload_json"])
    assert payload["kind"] == "combination"
    assert payload["hosted_by"] is None
    assert row["compiled_cells"] == 0 and row["queued_cells"] == 0 and row["blocked_cells"] == 1
    assert queued == 0
    assert R.counts()["research_candidates"] == 0


def test_a_signature_knob_hosts_a_state_tag(desk: dict[str, Any]) -> None:
    """THE SIGNATURE IS THE AUTHORITY. Give a family a `state` argument and the same combination
    that was a payload becomes a hostable cell -- and nothing else about the organ changes."""
    desk["knobs"]["vol_transition"] = {"state"}
    _, combos = ar.build()
    hosted = [c for c in combos if c["hosted_by"] == "vol_transition"]
    assert hosted
    tag = next(t for t in hosted[0]["tags"] if t["knob"] == "state")
    assert tag["kind"] == "state" and tag["value"] == "carry_rollover"
    assert hosted[0]["params"]["state"] == "carry_rollover"


def test_the_primary_is_chosen_for_hostability_when_lane_rank_cannot_host(
        desk: dict[str, Any]) -> None:
    """Lane rank answers WHICH gene is the base rule first; where that ordering cannot be expressed
    and another can, the hostable one wins and the report says why."""
    _, combos = ar.build()
    reasons = {c["primary_chosen_for"] for c in combos}
    assert reasons <= {"lane rank", "hostability"}
    swapped = [c for c in combos if c["primary_chosen_for"] == "hostability"]
    assert swapped, "the LIVE gold breakout has no knob; its gap-decay partner can host its window"
    c = swapped[0]
    assert c["hosted_by"] == c["primary"]
    assert ar.LANE_RANK[c["genes"][0]["lane"]] <= max(ar.LANE_RANK[g["lane"]] for g in c["genes"])


# ------------------------------------------------------------------ recording and donation
def test_discoveries_carry_their_parents_and_the_expanded_state(desk: dict[str, Any]) -> None:
    """A combination detached from the genes that produced it cannot be traced back to the
    campaigns that paid for them."""
    _, combos = ar.build(max_combinations=4)
    created, _ = ar.record(combos, {})
    assert created == len(combos)
    rows = {r["discovery_id"]: r for r in R.discoveries()}
    assert len(rows) == len(combos)
    by_hash = {json.loads(r["payload_json"])["combination_id"]: r for r in rows.values()}
    for c in combos:
        row = by_hash[c["combination_id"]]
        assert row["state"] == "EXPANDED"
        assert row["source_type"] == "recombination"
        assert row["origin"] == "MOAT"
        assert row["generator"] == ar.SEAT
        assert json.loads(row["parent_ids_json"]) == [g["gene_id"] for g in c["genes"]]
        assert row["possible_cells"] == 1 and row["generated_cells"] == 1
        assert json.loads(row["payload_json"])["why"] == c["why"]
    conn = R.connect()
    try:
        edges = conn.execute("SELECT * FROM provenance WHERE relation='recombined'").fetchall()
    finally:
        conn.close()
    assert len(edges) == sum(c["n_genes"] for c in combos)
    assert {str(e["from_kind"]) for e in edges} == {"cell"}


def test_the_rerun_records_nothing_new(desk: dict[str, Any]) -> None:
    """The content hash is the combination's identity, so an hourly organ does not mint the same
    gene pairing every hour."""
    _, combos = ar.build(max_combinations=4)
    assert ar.record(combos, {})[0] == len(combos)
    n = R.counts()["discoveries"]
    _, again = ar.build(max_combinations=4)
    assert ar.record(again, {})[0] == 0
    assert R.counts()["discoveries"] == n


def test_hosted_combinations_are_enqueued_and_donated(desk: dict[str, Any]) -> None:
    """A hostable combination becomes an ordinary candidate: donated under this seat's name, with
    the primary gene's family as its trial family, and enqueued in the registry at origin MOAT."""
    assert ar.main([]) == 0
    doc = json.loads(ar.OUT.read_text("utf-8"))
    hosted = [c for c in doc["combinations"] if c["hosted_by"]]
    assert hosted and all(c["queued"] for c in hosted)
    assert all(not c["queued"] for c in doc["combinations"] if not c["hosted_by"])
    assert doc["donated"] == len(hosted)
    call = desk["donations"][0]
    assert call["source"] == "alpha_recombination"
    assert len(call["candidates"]) == len(hosted)
    for row in call["candidates"]:
        assert row["trial_family"] == row["family"]
        assert row["evidence"]["genes"] and row["evidence"]["why"]
        assert row["mechanism"]
    cands = R.candidates(origin="MOAT")
    # THE SAME RULE TWICE IS ONE CANDIDATE. Two different gene sets can express the SAME executable
    # cell -- two genes lending the same window to the same family -- and the registry's content
    # hash collapses them with search_count rising, which is the behaviour the desk wants: a
    # duplicate cell would spend a second trial out of the shared error budget to learn nothing.
    assert 0 < len(cands) <= len(hosted)
    assert sum(int(c["search_count"] or 1) for c in cands) == len(hosted)
    assert {c["transformation"] for c in cands} == {"recombination"}
    assert all(json.loads(c["parent_ids_json"]) for c in cands)


def test_the_cap_binds(desk: dict[str, Any]) -> None:
    report, combos = ar.build(max_combinations=3)
    assert len(combos) == 3 == len(report["combinations"])
    assert report["refused_incoherent"]["n_coherent"] > 3
    assert report["refused_incoherent"]["n_crowded_out"] > 0
    assert ar.build(max_combinations=0)[1] == []


def test_the_cap_is_spent_on_distinct_mechanism_shapes_first(desk: dict[str, Any]) -> None:
    """A lopsided gene pool must not spend the whole cap on one pair: breadth first, then depth."""
    _, combos = ar.build(max_combinations=3)
    shapes = [frozenset(g["mechanism"] for g in c["genes"]) for c in combos]
    assert len(set(shapes)) == len(shapes), "three slots, three different mechanism shapes"


# ------------------------------------------------------------------ the table, the CLI, the report
def test_the_ontology_wins_when_it_declares_a_pair_table(desk: dict[str, Any],
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """The ontology owns the mechanism contracts. Two organs holding two opinions about which
    mechanisms touch is how a refusal here becomes a permission there."""
    table, source = ar.interaction_table()
    assert source.startswith("module") and "compatible" in source
    assert table is ar.INTERACTIONS
    monkeypatch.setattr(mo, "INTERACTIONS",
                        {("carry_rollover", "breakout_liquidity"): {"why": "declared upstream"}},
                        raising=False)
    table, source = ar.interaction_table()
    assert source == "mechanism_ontology.INTERACTIONS"
    assert table == {INCOHERENT: "declared upstream"}


def test_dry_run_writes_nothing_records_nothing_and_donates_nothing(
        desk: dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    assert ar.main(["--dry-run"]) == 0
    assert not ar.OUT.exists()
    assert R.counts()["discoveries"] == 0
    assert R.counts()["research_candidates"] == 0
    assert desk["donations"] == []
    out = capsys.readouterr().out
    assert "--dry-run: nothing written, nothing recorded, nothing donated" in out
    assert "ALPHA_RECOMBINATION" in out


def test_the_report_carries_the_shape_the_desk_reads(desk: dict[str, Any]) -> None:
    assert ar.main(["--max-combinations", "5"]) == 0
    doc = json.loads(ar.OUT.read_text("utf-8"))
    assert set(doc) >= {"at", "n_genes", "by_lane", "combinations", "refused_incoherent",
                        "discoveries_recorded", "donated", "unmeasured", "rule"}
    assert doc["rule"] == ("genes recombine only where the mechanisms plausibly interact; "
                           "exploitation of knowledge already paid for")
    assert doc["n_genes"] == sum(doc["by_lane"].values())
    assert doc["discoveries_recorded"] == len(doc["combinations"]) == 5
    assert all({"genes", "why", "hosted_by", "queued"} <= set(c) for c in doc["combinations"])
    assert not list(ar.OUT.parent.glob("*.tmp")), "the write is atomic and leaves no debris"
