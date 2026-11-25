"""The universal discovery-to-cell compiler: intake, interpretation, closure, gates, conversion.

Every path the organ reads is redirected into `tmp_path`, the registry is a throwaway file
(`registry.set_path`), the donation door is monkeypatched and the bars probe is a stub. The tests
that matter most are the ones that prove a REFUSAL is recorded with its reason and counted --
because the principal's rule of 2026-09-17 is not "convert everything", it is "nothing leaves
without a disposition", and a silent drop looks exactly like a successful run from the outside.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import discovery_compiler as dc  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

INSTRUMENTS: dict[str, list[str]] = {
    "forex": ["EURUSD", "GBPUSD", "USDJPY"],
    "commodities": ["XAUUSD", "XAGUSD"],
    "indices": ["US500"],
}
EQUITIES = ["APPLE"]
FAMILIES = frozenset({"asia_momentum", "session_range_breakout", "level_breakout",
                      "cross_asset_residual", "carry", "overnight_drift", "clock_transition",
                      "monday_gap", "overnight_gap_decay"})

INTEL_DOC = {
    "source": "factor_residual", "generated_at": "2026-09-17T00:00:00+00:00", "tests_run": 8780,
    "discoveries": [
        {"kind": "factor_residual", "symbol": "EURUSD", "family": "asia_momentum",
         "params": {"rr": 1.8, "ttl_bars": 12, "session": "asia", "timeframe": "H1",
                    "mom_thresh": 0.5},
         "mechanism": "asia session handover: risk carried out of tokyo is repriced in london",
         "title": "EURUSD asia handover"},
        {"kind": "anomaly", "symbol": "XAUUSD", "family": "level_breakout",
         "params": {"timeframe": "H1", "session": "london"},
         "mechanism": "a breakout through the level runs the resting stops beyond it"},
    ],
}
FRONTIER_ROW = {"at": "2026-09-05T21:23:30+00:00", "candidate_id": "F-1", "state": "DISCOVERED",
                "firm": "Citadel Securities", "capability": "MACRO", "source_url": "",
                "claim": "carry differential and swap rollover drive the exotic crosses",
                "evidence_grade": "B", "source_kind": "public_forum"}
STANDING = {"at": "2026-09-16T21:11:39+00:00", "questions": {
    "Q1": {"status": "OK", "n": 550, "why": "clock features",
           "findings": [{"target": "XAUUSD", "feature": "clock_hour_01", "category": "clock",
                         "lift": 4.48, "p_perm": 0.005, "n_events": 118}]}}}
RESIDUALS = {"at": "2026-09-17T00:00:00+00:00", "rows": [
    {"id": "resid-1", "symbol": "GBPUSD", "chart": "H1",
     "mechanism": "unexplained residual after the dollar factor is removed"}]}
GRAVEYARD_MD = """# Graveyard

### XAUUSD momentum on H1 -- KILLED 2026-08-01

**Mechanism of death:** the round trip cost exceeded the mean edge at every parameter tried.

### EURUSD range fade -- KILLED 2026-08-02

**Mechanism of death:** duplicate of an existing certified cell; redundant with the live book.
"""


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload,
                    encoding="utf-8")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The organ pointed at a synthetic tree, a throwaway registry and a stubbed donation door."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    paths = {"INTEL": tmp_path / "intel", "FRONTIER_QUEUE": tmp_path / "frontier_queue.jsonl",
             "GRAVEYARD_MD": tmp_path / "graveyard", "GRAVEYARD_JSON": tmp_path / "graveyard.json",
             "RESIDUAL_QUEUE": tmp_path / "RESIDUAL_QUEUE.json",
             "STANDING_QUESTIONS": tmp_path / "STANDING_QUESTIONS.json",
             "NOVELTY_GATE": tmp_path / "NOVELTY_GATE.json", "UNIVERSE": tmp_path / "universe",
             "AXES": tmp_path / "axes", "CURSOR": tmp_path / "cursor.json",
             "OUT": tmp_path / "DISCOVERY_COMPILER.json"}
    for name, path in paths.items():
        monkeypatch.setattr(dc, name, path)
    donated: list[dict[str, Any]] = []
    monkeypatch.setattr(dc, "donate", lambda rows, n: donated.extend(rows) or "STUB")
    yield {"tmp": tmp_path, "paths": paths, "donated": donated}
    R.set_path(None)


@pytest.fixture
def ctx() -> TM.Context:
    return TM.Context(
        instruments={k: list(v) for k, v in INSTRUMENTS.items()}, families=FAMILIES,
        defaults={"asia_momentum": {"rr": 1.8, "ttl_bars": 12},
                  "level_breakout": {"rr": 2.0, "wb": 8}},
        macro_states={"policy": ["carry_high", "carry_low"]},
        bars_available=lambda _s, c: str(c).upper() in ("M15", "H1", "H4"),
        lane_ok=lambda s: s not in EQUITIES, max_per_miner=6)


def _populate(desk) -> None:
    _write(desk["paths"]["INTEL"] / "factor_residual" / "discoveries_20260917_0000.json",
           INTEL_DOC)
    _write(desk["paths"]["FRONTIER_QUEUE"], json.dumps(FRONTIER_ROW))
    _write(desk["paths"]["STANDING_QUESTIONS"], STANDING)
    _write(desk["paths"]["RESIDUAL_QUEUE"], RESIDUALS)
    _write(desk["paths"]["GRAVEYARD_MD"], GRAVEYARD_MD)


def _child(**over: Any) -> dict[str, Any]:
    base = {"symbol": "XAUUSD", "family": "asia_momentum", "chart": "H1", "session": "asia",
            "regime": "unconditional", "horizon": "sub_4h", "asset_class": "commodities",
            "information": "price_only", "mechanism_id": "session_handover", "params": {},
            "content_hash": "deadbeef" * 4}
    return {**base, **over}


def test_unexecutable_descendant_is_disposed_before_donation(ctx):
    cell = _child(params={"conditioner": "carry"})
    ok, why = dc._dispose(cell, ctx, coverage={}, hashes=set(), redundant=set(), conn=None)
    assert not ok
    assert why.startswith("execution:modifier_unavailable")
    assert "conditioner='carry'" in why


def test_executable_descendant_keeps_the_same_door(ctx):
    cell = _child(params={"regime": "high_vol", "mom_thresh": 0.5})
    ok, why = dc._dispose(cell, ctx, coverage={}, hashes=set(), redundant=set(), conn=None)
    assert ok, why


# --------------------------------------------------------------------------- intake
def test_intake_reads_every_live_source_shape(desk, ctx):
    _populate(desk)
    cursor = dc.load_cursor(desk["paths"]["CURSOR"])
    got, by_source, unmeasured = dc.intake(cursor, limit=100)
    assert by_source.get("intelligence") == 2
    assert by_source.get("frontier_queue") == 1
    assert by_source.get("standing_question") == 1
    assert by_source.get("residual_queue") == 1
    assert by_source.get("graveyard") == 2
    assert {d["discovery_id"] for d in got} == {d["discovery_id"] for d in got if d["discovery_id"]}
    assert unmeasured == []
    assert R.discoveries(state="UNPROCESSED", limit=100)


def test_intake_is_idempotent_by_cursor_and_by_content_hash(desk, ctx):
    _populate(desk)
    cursor = dc.load_cursor(desk["paths"]["CURSOR"])
    first, by_first, _ = dc.intake(cursor, limit=100)
    # The graveyard and the card table are NOT cursor-gated -- they are re-read every pass -- so
    # a second intake proves the registry's own content-hash dedupe, not just the file cursor.
    second, by_second, _ = dc.intake(cursor, limit=100)
    assert first and by_first
    assert by_second == {"registry_unprocessed": len(first)}
    assert len(second) == len(first)


def test_an_absent_source_is_a_named_gap_not_a_clean_sweep(desk, ctx):
    cursor = dc.load_cursor(desk["paths"]["CURSOR"])
    _got, by_source, unmeasured = dc.intake(cursor, limit=10)
    assert by_source == {}
    what = " ".join(u["what"] for u in unmeasured)
    why = " ".join(u["why"] for u in unmeasured)
    assert "RESIDUAL_QUEUE.json" in what and "STANDING_QUESTIONS.json" in what
    assert "UNMEASURED" in why or "no " in why


def test_rows_of_reads_the_three_shapes_live_on_this_box():
    assert len(dc.rows_of(INTEL_DOC)) == 2
    assert len(dc.rows_of([{"kind": "hypothesis"}, {"kind": "hypothesis"}])) == 2
    assert len(dc.rows_of({"anomalies": [{"symbol": "X"}], "trials": 9})) == 1
    assert dc.rows_of({"unrelated": 3}) == []


def test_the_graveyard_yields_a_failure_class_the_resurrection_miner_can_act_on(desk):
    _write(desk["paths"]["GRAVEYARD_MD"], GRAVEYARD_MD)
    rows = dc._graveyard_rows()
    classes = {r["failure_class"] for r in rows}
    assert classes == {"cost_killed", "redundant"}
    assert all(cls in R.FAILURE_CLASSES for cls in classes)


# --------------------------------------------------------------------------- interpret
@pytest.mark.parametrize(("text", "expect"), [
    ("risk carried out of the asia session is repriced at the london session open",
     "session_handover"),
    ("month end rebalancing flow into the london fix", "calendar_seasonality"),
    ("COT positioning is crowded on the net long side", "positioning_crowding"),
    ("the carry differential and the swap rollover", "carry_rollover"),
    ("a breakout through the level runs the resting stops", "breakout_liquidity"),
])
def test_interpret_maps_a_claim_to_one_canonical_mechanism(text, expect):
    assert dc.interpret(text, "")[0] == expect


def test_interpret_admits_unknown_and_records_why():
    mid, why = dc.interpret("something entirely outside the desk's vocabulary", "")
    assert mid == TM.UNKNOWN_MECHANISM
    assert "UNKNOWN is recorded rather than guessed" in why


def test_a_declared_mechanism_that_names_a_contract_wins_over_the_text():
    assert dc.interpret("a breakout through the level", "carry_rollover")[0] == "carry_rollover"


# --------------------------------------------------------------------------- closure
def test_closure_never_yields_d1_for_a_session_mechanism_nor_an_equity(desk, ctx):
    ctx.instruments = {**ctx.instruments, "equities": list(EQUITIES)}
    parent = dc.parent_of({"discovery_id": "d1", "symbol": "XAUUSD", "family": "asia_momentum",
                           "chart": "H1", "session": "asia", "params": {"rr": 1.8},
                           "declared_mechanism": "session_handover", "why": "asia handover"}, ctx)
    children, counts, possible = dc.closure(parent, ctx)
    assert parent["mechanism_id"] == "session_handover"
    assert "D1" not in {c.get("chart") for c in children}
    assert not ({c.get("symbol") for c in children} & set(EQUITIES))
    assert possible >= len(children)
    assert set(counts) == set(TM.MINERS)


def test_closure_dedupes_by_content_hash(desk, ctx):
    parent = dc.parent_of({"discovery_id": "d1", "symbol": "XAUUSD", "family": "asia_momentum",
                           "chart": "H1", "session": "asia", "params": {"rr": 1.8},
                           "declared_mechanism": "session_handover", "why": "asia handover"}, ctx)
    children, _counts, _possible = dc.closure(parent, ctx)
    hashes = [c["content_hash"] for c in children]
    assert len(hashes) == len(set(hashes))
    assert dc._hash_of(parent) not in hashes


def test_missing_chart_is_not_silently_promoted_to_h1(ctx):
    """A source lead without a clock is UNMEASURED, not an H1 hypothesis."""
    parent = dc.parent_of({"discovery_id": "clockless", "symbol": "XAUUSD",
                           "family": "asia_momentum", "session": "asia",
                           "declared_mechanism": "session_handover",
                           "why": "asia handover"}, ctx)

    assert parent["chart"] == ""
    assert parent["horizon"] == "unknown"
    ok, why = dc.gate_data(parent, ctx)
    assert ok is False and why == "data:no_chart"
    children, _counts, _possible = dc.closure(parent, ctx)
    assert children  # the other independent transformations still report their attempts
    assert {child["chart"] for child in children} == {""}
    assert {dc.gate_data(child, ctx)[1] for child in children} == {"data:no_chart"}


def test_explicit_params_timeframe_remains_a_declared_chart(ctx):
    """The repair preserves a clock explicitly carried in the source parameter envelope."""
    parent = dc.parent_of({"discovery_id": "clocked", "symbol": "XAUUSD",
                           "family": "asia_momentum", "session": "asia",
                           "params": {"timeframe": "m15"},
                           "declared_mechanism": "session_handover",
                           "why": "asia handover"}, ctx)

    assert parent["chart"] == "M15"
    assert parent["horizon"] == "intrabar"


# --------------------------------------------------------------------------- the three gates
def test_gate_economic_refuses_an_equity_by_the_two_lane_mandate(ctx):
    ok, why = dc.gate_economic(_child(symbol="APPLE"), ctx)
    assert ok is False and why == "economic:two_lane_mandate"


def test_gate_economic_refuses_a_d1_session_cell(ctx):
    ok, why = dc.gate_economic(_child(chart="D1"), ctx)
    assert ok is False and why.startswith("economic:incompatible")


def test_gate_economic_refuses_a_family_the_desk_does_not_carry(ctx):
    ok, why = dc.gate_economic(_child(family="not_a_family"), ctx)
    assert ok is False and why.startswith("economic:family_not_registered")
    ok2, why2 = dc.gate_economic(_child(family=""), ctx)
    assert ok2 is False and why2 == "economic:no_family_implements_this_mechanism"


def test_gate_data_refuses_a_cell_with_no_bars_and_names_the_file(ctx):
    ok, why = dc.gate_data(_child(chart="D1"), ctx)
    assert ok is False and "XAUUSD_D1.parquet" in why


def test_gate_data_refuses_a_macro_conditioner_with_no_axis_file(ctx):
    ctx.macro_states = {}
    ok, why = dc.gate_data(_child(params={"macro_axis": "policy"}), ctx)
    assert ok is False and why.startswith("data:macro_axis_absent")
    ok2, why2 = dc.gate_data(_child(information="positioning"), ctx)
    assert ok2 is False and why2 == "data:no_axis_file_for_positioning"


def test_pit_status_is_bar_close_for_price_only_and_stamped_for_a_held_axis(ctx):
    assert dc.pit_status(_child(), ctx) == "PIT_BAR_CLOSE"
    assert dc.pit_status(_child(params={"macro_axis": "policy"}), ctx) == "PIT_STAMPED"
    ctx.macro_states = {}
    assert dc.pit_status(_child(params={"macro_axis": "policy"}), ctx) == "UNKNOWN"


def test_gate_novelty_refuses_an_exact_twin_and_a_named_redundancy(desk, ctx):
    child = _child()
    ok, _why = dc.gate_novelty(child, ctx, coverage={}, hashes=set(), redundant=set())
    assert ok is True
    ok2, why2 = dc.gate_novelty(child, ctx, coverage={}, hashes={child["content_hash"]},
                                redundant=set())
    assert ok2 is False and why2 == "novelty:exact_twin_already_enqueued"
    ok3, why3 = dc.gate_novelty(child, ctx, coverage={}, hashes=set(),
                                redundant={"XAUUSD.asia_momentum"})
    assert ok3 is False and why3.startswith("novelty:redundant_in_novelty_gate")


def test_the_novelty_gate_artifact_supplies_the_redundancy_census(desk):
    _write(desk["paths"]["NOVELTY_GATE"],
           {"twins_named": {"external.XAUUSD.session_range_breakout.rr=1.5": 1}})
    assert "XAUUSD.session_range_breakout.rr=1.5" in dc._redundant_keys()


# --------------------------------------------------------------------------- the whole organ
def test_a_run_compiles_enqueues_donates_and_leaves_no_cell_undisposed(desk, ctx):
    _populate(desk)
    report = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert report["intake"]["n"] > 0 and report["expanded"] == report["interpreted"]
    assert report["compiled"] > 0 and report["queued"] == report["compiled"]
    assert report["rule"] == dc.RULE

    cands = R.candidates(limit=500)
    assert len(cands) == report["compiled"]
    assert all(c["discovery_id"] and c["transformation"] for c in cands)
    assert all(str(c["generator"]).startswith("discovery_compiler:") for c in cands)
    assert {c["transformation"] for c in cands} <= set(TM.MINERS)
    assert all("unknown" not in str(c["grid_cell"]).split("|")[:2] for c in cands)

    assert len(desk["donated"]) == report["compiled"]
    assert all(d["kind"] == "hypothesis" and d["source"] == "discovery_compiler"
               for d in desk["donated"])
    assert report["donation_path"] == "STUB"

    debt = report["conversion_debt"]
    assert debt["unexplained_missing_cells"] == 0
    assert report["conversion_coverage"] == 1.0
    assert debt["by_state"].get("UNPROCESSED", 0) == 0
    assert desk["paths"]["OUT"].exists()


def test_every_blocked_child_carries_a_named_reason_and_a_counter(desk, ctx):
    _populate(desk)
    report = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    reasons = report["blocked"]["by_reason"]
    assert reasons and report["blocked"]["n"] == sum(reasons.values())
    assert all(":" in r for r in reasons)
    assert any(r.startswith(("economic:", "data:", "novelty:", "budget:")) for r in reasons)
    per_miner = sum(c["blocked"] for c in report["by_miner"].values())
    budget = sum(n for r, n in reasons.items() if r.startswith("budget:"))
    assert per_miner + budget == report["blocked"]["n"]
    assert R.memories(kind="blocked_cell")


def test_provenance_runs_discovery_to_mechanism_to_cell(desk, ctx):
    _populate(desk)
    dc.run(budget_s=60, max_discoveries=5, cursor_path=desk["paths"]["CURSOR"],
           out=desk["paths"]["OUT"], ctx=ctx)
    cid = R.candidates(limit=1)[0]["id"]
    edges = R.provenance_of("cell", cid)
    kinds = {(e["from_kind"], e["relation"]) for e in edges}
    assert any(k == "discovery" for k, _ in kinds)
    assert any(k == "mechanism" for k, _ in kinds)
    assert any(k == "miner" for k, _ in kinds)


def test_tested_is_never_set_by_the_compiler(desk, ctx):
    _populate(desk)
    dc.run(budget_s=60, max_discoveries=5, cursor_path=desk["paths"]["CURSOR"],
           out=desk["paths"]["OUT"], ctx=ctx)
    assert "TESTED" not in {d["state"] for d in R.discoveries(limit=500)}
    assert R.conversion_debt()["tested_cells"] == 0


def test_a_second_run_changes_nothing(desk, ctx):
    _populate(desk)
    first = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                   out=desk["paths"]["OUT"], ctx=ctx)
    n_first = len(R.candidates(limit=500))
    second = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert first["compiled"] > 0
    assert second["intake"]["n"] == 0 and second["compiled"] == 0
    assert len(R.candidates(limit=500)) == n_first
    assert any(u["what"] == "intake" for u in second["unmeasured"])
    assert dc.load_cursor(desk["paths"]["CURSOR"])["runs"] == 2


def test_the_budget_stops_the_run_and_defers_rather_than_drops(desk, ctx, monkeypatch):
    _populate(desk)
    clock = iter([0.0])
    monkeypatch.setattr(dc.time, "monotonic", lambda: next(clock, 1_000_000.0))
    report = dc.run(budget_s=240, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert report["budget_stopped"] is True
    assert report["expanded"] == 0 and report["compiled"] == 0
    assert any("budget ran out" in u["why"] and "never dropped" in u["why"]
               for u in report["unmeasured"])
    assert R.discoveries(state="UNPROCESSED", limit=500)


def test_dry_run_touches_neither_the_registry_nor_the_disk(desk, ctx):
    _populate(desk)
    report = dc.run(dry_run=True, budget_s=60, max_discoveries=20,
                    cursor_path=desk["paths"]["CURSOR"], out=desk["paths"]["OUT"], ctx=ctx)
    assert report["intake"]["n"] > 0 and report["compiled"] > 0
    # A dry run that had already recorded the intake would not be a dry run: the second, real
    # pass would find every discovery deduped away and convert nothing.
    assert R.discoveries(limit=500) == []
    assert R.candidates(limit=500) == []
    assert R.memories(kind="blocked_cell") == []
    assert desk["donated"] == []
    assert not desk["paths"]["OUT"].exists()
    assert not desk["paths"]["CURSOR"].exists()
    assert all(str(d["discovery_id"]).startswith("dry_")
               for d in dc.intake(dc.load_cursor(desk["paths"]["CURSOR"]), record=False)[0])


def test_a_real_run_after_a_dry_run_still_converts_everything(desk, ctx):
    _populate(desk)
    dry = dc.run(dry_run=True, budget_s=60, max_discoveries=20,
                 cursor_path=desk["paths"]["CURSOR"], out=desk["paths"]["OUT"], ctx=ctx)
    real = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                  out=desk["paths"]["OUT"], ctx=ctx)
    assert real["intake"]["n"] == dry["intake"]["n"]
    assert real["compiled"] == dry["compiled"] > 0


def test_cli_dry_run(desk, ctx, monkeypatch, capsys):
    _populate(desk)
    monkeypatch.setattr(dc, "build_context", lambda **_kw: ctx)
    assert dc.main(["--dry-run", "--budget-s", "60", "--max-discoveries", "5"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "conversion coverage" in out
    assert not desk["paths"]["OUT"].exists()


# --------------------------------------------------------------------------- culture provenance
CULTURE_DOC = {
    "source": "followme_cn", "generated_at": "2026-09-30T00:00:00+00:00", "tests_run": 10,
    "discoveries": [
        {"kind": "copy_trader", "symbol": "EURUSD", "family": "asia_momentum",
         "params": {"rr": 1.8, "ttl_bars": 12, "session": "asia", "timeframe": "H1",
                    "mom_thresh": 0.5},
         "url": "https://www.followme.cn/trader/123",
         "mechanism": "散户 chase the asia session handover: risk carried out of tokyo is "
                      "repriced in london",
         "title": "EURUSD asia handover by a FollowMe trader"}],
}


def test_every_emitted_cell_carries_the_sources_culture_url_and_seat(desk, ctx):
    """THE DEFECT (Tier S cross-culture test, 2026-09-30): 24 live FX sleeves born in this
    compiler carried no seat, no URL and no culture -- the compiler dropped them between the
    donation it read and the cells it emitted. Every emitted cell now carries them forward."""
    _write(desk["paths"]["INTEL"] / "followme_cn" / "discoveries_20260930_0000.json",
           CULTURE_DOC)
    report = dc.run(budget_s=60, max_discoveries=5, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert report["compiled"] > 0
    assert desk["donated"], "the compiler donated nothing"
    for row in desk["donated"]:
        assert row["source_culture"] == "CN/zh"
        assert row["participant_structure"] == "retail_heavy"
        assert row["failure_mode_hypothesis"] not in ("", None, "UNMEASURED")
        assert row["crowding_prior"] in ("low", "medium", "high", "UNMEASURED")
        assert row["source_url"] == "https://www.followme.cn/trader/123"
        assert row["source_seat"] == "followme_cn"
        assert row["source_file"].endswith("discoveries_20260930_0000.json")
        assert row["culture_derivation"]["source_culture"].startswith("inferred:")
    cands = R.candidates(limit=500)
    assert cands and all(c["source_culture"] == "CN/zh" for c in cands)
    disc = R.discoveries(limit=50)
    assert any(d.get("source_culture") == "CN/zh" for d in disc)


def test_a_row_with_no_evidence_carries_unmeasured_never_a_guess():
    prov = dc.provenance({"symbol": "XAUUSD", "family": "carry", "mechanism": "carry"})
    assert prov["source_culture"] == "UNMEASURED"
    assert prov["culture_derivation"]["source_culture"] == "UNMEASURED"
    assert "source_url" not in prov and "source_seat" not in prov


# --------------------------------------------------------------------------- real settings
# THE DEFECT (funnel, 2026-11-25): 24,711 of this compiler's 26,008 docket rows were
# DEFAULTS_ONLY -- a family at its defaults with a session / regime / conditioner variant -- and
# only 132 were testable. A stated setting never reached the family's own keyword, and a child
# with none was donated anyway, to be judged as the family's defaults.
from research import family_spec as FS  # noqa: E402


def test_stated_params_reads_structured_and_rule_text_settings():
    row = {"symbol": "EURUSD", "parameters": {"lookback": 40},
           "exact_rule": "fade the range when RSI(9) < oversold=25; hold_bars: 6"}
    got = dc.stated_params(row)
    assert got == {"lookback": 40, "rsi_n": 9, "oversold": 25, "hold_bars": 6}
    # structured wins over text, and a sandbox row's evidence.parameters is read too
    assert dc.stated_params({"params": {"rsi_n": 14}, "exact_rule": "rsi_n=9"}) == {"rsi_n": 14}
    assert dc.stated_params({"evidence": {"parameters": {"w": 30}}}) == {"w": 30}
    assert dc.stated_params({"mechanism": "a 20-day drift, nothing named"}) == {}


def test_a_child_with_stated_numbers_becomes_executable_under_the_familys_names():
    child = _child(family="range_reversion",
                   params={"lookback": 40, "session": "asia", "regime": "high_vol",
                           "mechanism_genome": {"actor": "x"}})
    out = dc.translate_params(child)
    assert out["spec_status"] == FS.EXECUTABLE
    assert out["params"] == {"range_n": 40, "session": "asia", "regime": "high_vol"}
    assert out["params_mapped"] == {"lookback": "range_n"}
    assert out["params_unread"] == ["mechanism_genome"]
    assert out["content_hash"] != child["content_hash"]
    assert FS.judged_quality("range_reversion", out["params"]) == FS.EXECUTABLE
    ok, why = dc.gate_spec(out)
    assert ok and why == "spec:executable"


def test_a_child_with_nothing_the_replay_applies_is_refused_by_name():
    """Blocked: nothing differs from the defaults, only a label, only geometry, a variant the
    replay REFUSES (residual, an undefined conditioner or regime, a limit fill), or prose."""
    cases = (({"representation": "external_engine"}, "spec:defaults_only"),
             ({"rr": 1.0, "ttl_bars": 6}, "spec:defaults_only"),
             ({"regime": "unconditional", "side_mode": "follow"}, "spec:defaults_only"),
             ({"residual": "usd", "residual_tag": "residual"}, "spec:unhonoured_variant"),
             ({"conditioner": "carry"}, "spec:unhonoured_variant"),
             ({"regime": "risk_off"}, "spec:unhonoured_variant"),
             ({"execution_style": "limit"}, "spec:unhonoured_variant"),
             ({}, "spec:prose_only"))
    for params, expect in cases:
        out = dc.translate_params(_child(params=params, session="all"), prose="asia handover")
        ok, why = dc.gate_spec(out)
        assert not ok and why.startswith(expect), (params, why)
    # an applied session does not rescue a refused variant: the gauntlet NOT_RUNs the cell
    out = dc.translate_params(_child(params={"residual": "usd"}, session="london"))
    assert out["spec_status"] == FS.UNHONOURED_VARIANT


def test_a_session_filtered_child_at_the_defaults_is_an_executable_variant():
    """A family at its defaults traded only in London (or only in high vol) is a DIFFERENT
    rule the replay really applies -- breadth, not waste. Its window rides IN its params, where
    the docket keeps it instead of fanning the row out over every session."""
    out = dc.translate_params(_child(params={"representation": "price_only"},
                                     session="london", chart="M15"))
    assert out["spec_status"] == FS.EXECUTABLE_VARIANT
    assert out["params"] == {"representation": "price_only", "session": "london",
                             "timeframe": "M15"}
    assert dc.gate_spec(out) == (True, "spec:executable_variant")
    assert FS.judged_quality("asia_momentum", out["params"]) == FS.EXECUTABLE_VARIANT
    for params in ({"regime": "high_vol"}, {"side_mode": "revert"},
                   {"entry_timing": "delayed"}):
        got = dc.translate_params(_child(params=params, session="all"))
        assert got["spec_status"] == FS.EXECUTABLE_VARIANT, params
    # session "all" is the fan-out's own slot: nothing is folded in
    assert "session" not in dc.translate_params(_child(params={"regime": "high_vol"},
                                                       session="all"))["params"]


def test_a_run_donates_only_executable_rows_and_counts_the_rest(desk, ctx):
    """End to end: a parent that STATES its setting in its rule text yields donated rows that
    carry it under the family's keyword; a parent with nothing executable yields no donation
    and a named, counted `spec:` reason -- and every closure member is still disposed."""
    _write(desk["paths"]["INTEL"] / "seat" / "discoveries_20261125_0000.json", {
        "source": "seat", "discoveries": [
            {"kind": "lead", "symbol": "EURUSD", "family": "asia_momentum",
             "params": {"timeframe": "H1", "session": "asia"},
             "exact_rule": "go with the asia drift when mom_thresh=0.6",
             "mechanism": "asia session handover: risk carried out of tokyo is repriced"},
            {"kind": "lead", "symbol": "XAUUSD", "family": "level_breakout",
             "params": {"timeframe": "H1", "session": "london"},
             "mechanism": "a breakout through the level runs the resting stops beyond it"}]})
    report = dc.run(budget_s=60, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert desk["donated"], "the stated rule produced nothing"
    for row in desk["donated"]:
        q = FS.judged_quality(row["family"], row["params"])
        assert FS.is_testable(q), row
        if q == FS.EXECUTABLE_VARIANT:          # the variant rides in the params it needs
            assert FS.to_executable(row["family"], row["params"])["variants"], row
    stated = [r for r in desk["donated"] if r["symbol"] == "EURUSD"
              and r["family"] == "asia_momentum"]
    # every one carries the stated setting -- as stated, or its declared x0.5 / x2 neighbour
    assert stated and all(r["params"].get("mom_thresh") in (0.6, 0.3, 1.2) for r in stated)
    assert any(r["params"].get("mom_thresh") == 0.6 for r in stated)
    # the parent with no setting reaches the docket ONLY as variants the replay applies
    bare = [r for r in desk["donated"] if r["family"] == "level_breakout"]
    assert all(FS.judged_quality("level_breakout", r["params"]) == FS.EXECUTABLE_VARIANT
               for r in bare)
    reasons = report["blocked"]["by_reason"]
    assert any(k.startswith("spec:") for k in reasons), reasons
    assert report["compiled"] + report["blocked"]["n"] == report["possible_cells"]
    assert report["conversion_debt"]["unexplained_missing_cells"] == 0
    assert R.memories(kind="blocked_cell")


def test_the_moat_exchange_donates_only_executable_claims_and_marks_the_rest(
        tmp_path, monkeypatch):
    """moat_factory (0 of 608 docket rows testable, 2026-11-25) forwards the registry's queue,
    which holds the compiler's older defaults-only variants. A claim with no real setting (only a
    label, or a variant the replay refuses) is
    counted by verdict and marked `not_executable` with its reason -- never donated, never left
    to be re-claimed; one with a stated setting is donated under the family's keyword."""
    pytest.importorskip("pandas")
    import moat_candidate_compiler as mcc

    from libs.ops import throughput
    from research import proposer_common as pc
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(throughput, "SAMPLES", tmp_path / "throughput_samples.jsonl")
    monkeypatch.setattr(pc, "_preregister", lambda _s, _c: {
        "preregistered": 0, "failed": 0, "already": 0, "reasons": {}, "failures": []})
    conn = R.connect()
    try:
        bare, _ = R.enqueue_candidate(
            family="range_reversion", symbol="AUDCAD", status="queued", origin="DESK",
            params={"representation": "external_engine"}, mechanism="m" * 20, conn=conn)
        refused, _ = R.enqueue_candidate(
            family="range_reversion", symbol="AUDCAD", status="queued", origin="DESK",
            params={"residual": "usd", "residual_tag": "residual"}, mechanism="m" * 20,
            conn=conn)
        variant, _ = R.enqueue_candidate(
            family="range_reversion", symbol="EURGBP", status="queued", origin="DESK",
            params={"representation": "external_engine"}, session="london",
            mechanism="m" * 20, conn=conn)
        real, _ = R.enqueue_candidate(
            family="range_reversion", symbol="AUDCAD", status="queued", origin="DESK",
            params={"lookback": 40, "session": "asia"}, mechanism="m" * 20, conn=conn)
        out = mcc.claim_and_donate(conn, per_department=50)
        assert out["status"] == "CLAIMED", out
        assert out["not_executable"]["rows"] == 2
        assert out["not_executable"]["by_reason"] == {FS.DEFAULTS_ONLY: 1,
                                                      FS.UNHONOURED_VARIANT: 1}
        files = list((tmp_path / "intel" / mcc.SOURCE).glob("discoveries_*.json"))
        rows = json.loads(files[0].read_text("utf-8"))["discoveries"]
        assert sorted((r["symbol"], json.dumps(r["params"], sort_keys=True)) for r in rows) == [
            ("AUDCAD", json.dumps({"range_n": 40, "session": "asia"}, sort_keys=True)),
            ("EURGBP", json.dumps({"representation": "external_engine", "session": "london"},
                                  sort_keys=True))]
        got = {r["id"]: (r["status"], r["rejection_reason"]) for r in conn.execute(
            "SELECT id, status, rejection_reason FROM research_candidates "
            "WHERE id IN (?, ?, ?, ?)", (bare, refused, variant, real))}
        assert got[bare][0] == mcc.NOT_EXECUTABLE_STATUS
        assert str(got[bare][1]).startswith("spec:defaults_only")
        assert str(got[refused][1]).startswith("spec:unhonoured_variant")
        assert got[real][0] != mcc.NOT_EXECUTABLE_STATUS
        assert got[variant][0] != mcc.NOT_EXECUTABLE_STATUS
    finally:
        conn.close()
        R.set_path(None)
