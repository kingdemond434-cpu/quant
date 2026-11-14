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
         "params": {"rr": 1.8, "ttl_bars": 12, "session": "asia", "timeframe": "H1"},
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
    cell = _child(params={"regime": "high_vol"})
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
    # A spent budget still expands MIN_EXPAND (2026-11-14: a pass that converts nothing is the
    # failure); everything past that is deferred, never dropped.
    n = report["intake"]["n"]
    assert n > dc.MIN_EXPAND, "the fixture must leave something to defer"
    assert report["budget_stopped"] is True and report["expanded"] == dc.MIN_EXPAND
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
         "params": {"rr": 1.8, "ttl_bars": 12, "session": "asia", "timeframe": "H1"},
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


def _many_rows(n: int) -> dict[str, Any]:
    return {"source": "seatx", "discoveries": [
        {"kind": "anomaly", "symbol": "EURUSD", "family": "asia_momentum",
         "params": {"timeframe": "H1", "rr": 1.0 + i / 100}, "mechanism": f"handover {i}"}
        for i in range(n)]}


def test_a_seat_file_refused_for_room_is_resumed_not_marked_read(desk, ctx):
    """Tier S 2026-11-13: rows refused at the limit were marked read and never revisited."""
    path = desk["paths"]["INTEL"] / "seatx" / "discoveries_1.json"
    _write(path, _many_rows(10))
    cursor = dc.load_cursor()
    taken: list[dict[str, Any]] = []
    for _ in range(6):
        got, _b, _u = dc.intake(cursor, limit=4)
        taken += [g for g in got if g.get("source_type") == "intelligence"]
        if cursor["files"].get(str(path), {}).get("next_row") is None and len(taken) >= 10:
            break
    assert len(taken) == 10
    assert cursor["files"][str(path)].get("next_row") is None
    got, _b, _u = dc.intake(cursor, limit=4)                 # fully read: nothing re-taken
    assert not [g for g in got if g.get("source_type") == "intelligence"]


def test_the_registry_backlog_cannot_starve_the_seats(desk, ctx, monkeypatch):
    backlog = [{"discovery_id": f"b{i}", "source_type": "registry"} for i in range(50)]
    monkeypatch.setattr(dc.R, "discoveries",
                        lambda state=None, limit=0, conn=None: backlog[:limit])
    monkeypatch.setattr(dc, "registry_parent", lambda row, *a: dict(row))
    _write(desk["paths"]["INTEL"] / "seatx" / "discoveries_1.json", _many_rows(10))
    got, by_source, _u = dc.intake(dc.load_cursor(), limit=10)
    assert by_source.get("intelligence") == 5 and by_source.get("registry_unprocessed") == 5
    _write(desk["paths"]["INTEL"] / "seatx" / "discoveries_1.json", _many_rows(2))
    got, by_source, _u = dc.intake(dc.load_cursor(), limit=10)    # unused seat room returns
    assert len(got) == 10 and by_source.get("registry_unprocessed", 0) >= 8


def test_a_growing_seat_jsonl_resumes_at_its_new_rows(desk, ctx):
    """Auditor MF2: keying the offset on size/mtime reset every appended .jsonl to row 0."""
    path = desk["paths"]["INTEL"] / "seatx" / "hypotheses.jsonl"
    rows = _many_rows(6)["discoveries"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows[:4]), "utf-8")
    cursor = dc.load_cursor()
    got, _b, _u = dc.intake(cursor, limit=100)
    assert len([g for g in got if g.get("source_type") == "intelligence"]) == 4
    with path.open("a", encoding="utf-8") as fh:                  # the seat appends next hour
        fh.write("".join(json.dumps(r) + "\n" for r in rows[4:]))
    got, _b, _u = dc.intake(cursor, limit=100)
    new = [g for g in got if g.get("source_type") == "intelligence"]
    assert [g.get("params", {}).get("rr") for g in new] == [1.04, 1.05]
    assert cursor["files"][str(path)]["rows_taken"] == 6


def test_owed_files_are_taken_before_newer_ones(desk, ctx):
    import os
    old = desk["paths"]["INTEL"] / "seatx" / "a_old.json"
    _write(old, _many_rows(6))
    os.utime(old, (1_000_000, 1_000_000))
    cursor = dc.load_cursor()
    dc.intake(cursor, limit=4)                                    # takes 4 of 6: owed 2
    assert cursor["files"][str(old)].get("next_row") is not None
    _write(desk["paths"]["INTEL"] / "seatx" / "b_new.json", _many_rows(8))
    got, _b, _u = dc.intake(cursor, limit=4)
    assert cursor["files"][str(old)].get("next_row") is None      # the owed file finished first


def test_one_large_seat_cannot_starve_the_other_seats(desk, ctx):
    """2026-11-14 (LLM lab): one seat's big file filled the whole seat share and four seats read
    0 cells/h. Round one gives every seat with fresh rows an equal share."""
    intel = desk["paths"]["INTEL"]
    _write(intel / "big" / "discoveries_1.json", _many_rows(40))
    for seat in ("standing_questions", "research_tree", "world"):
        _write(intel / seat / "discoveries_1.json", _many_rows(3))
    got, _b, _u = dc.intake(dc.load_cursor(), limit=12)
    seats = [g.get("source_seat") for g in got if g.get("source_type") == "intelligence"]
    for seat in ("standing_questions", "research_tree", "world"):
        assert seat in seats, seat
    assert len(got) == 12


def test_intake_cannot_spend_the_expansion_budget(desk, ctx, monkeypatch):
    """Box 2026-11-14: intake ran out the whole 180s budget and nothing was ever interpreted.
    Intake is held to INTAKE_SHARE of the budget, and a pass always expands MIN_EXPAND."""
    seen: dict[str, float] = {}
    real = dc.intake

    def slow_intake(cursor, *, deadline=None, **kw):
        seen["deadline"] = deadline
        return real(cursor, deadline=deadline, **kw)

    monkeypatch.setattr(dc, "intake", slow_intake)
    _write(desk["paths"]["INTEL"] / "seatx" / "discoveries_1.json", _many_rows(20))
    import time as _t
    t0 = _t.monotonic()
    report = dc.run(budget_s=100, max_discoveries=20, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert seen["deadline"] <= t0 + 100 * dc.INTAKE_SHARE + 5
    assert set(report["timings_s"]) >= {"context", "intake", "prepare", "expand"}
    assert report["expanded"] >= min(dc.MIN_EXPAND, report["intake"]["n"])
    # An already-expired budget still expands the minimum: a slow pass converts something.
    import itertools
    ticks = itertools.count(t0 + 10_000, 1_000)
    monkeypatch.setattr(dc.time, "monotonic", lambda: next(ticks))
    _write(desk["paths"]["INTEL"] / "seaty" / "discoveries_1.json", _many_rows(12))
    monkeypatch.setattr(dc, "intake", lambda cursor, **kw: (
        [{"discovery_id": f"x{i}", "source_type": "intelligence", **r}
         for i, r in enumerate(_many_rows(12)["discoveries"])], {"intelligence": 12}, []))
    report = dc.run(budget_s=1, max_discoveries=12, cursor_path=desk["paths"]["CURSOR"],
                    out=desk["paths"]["OUT"], ctx=ctx)
    assert report["expanded"] == dc.MIN_EXPAND and report["budget_stopped"]


def test_expansion_order_interleaves_every_source() -> None:
    rows = ([{"discovery_id": f"r{i}", "source_type": "registry"} for i in range(4)]
            + [{"discovery_id": f"a{i}", "source_type": "intelligence", "source_seat": "a"}
               for i in range(2)]
            + [{"discovery_id": "b0", "source_type": "intelligence", "source_seat": "b"}])
    order = [d["discovery_id"] for d in dc.interleave_sources(rows)]
    assert order[:3] == ["r0", "a0", "b0"] and sorted(order) == sorted(d["discovery_id"]
                                                                       for d in rows)
