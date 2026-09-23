"""The source civilizations: families, descendants, priors, the two routers and the forge.

Every path is redirected into `tmp_path` and the registry is a throwaway file, so nothing here
touches the box's real record. The tests that matter most are the REFUSALS -- a seat row carrying
a size field, a copied flow claiming to be a participant's own decision, a single-name insider
signal trying to escape the event lane -- because those are the ones that would be silently
admitted if the guard were removed, and a green suite would not notice.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import source_civilizations as sc  # noqa: E402


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield R
    R.set_path(None)


@pytest.fixture
def run(registry, tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "AXES", tmp_path / "axes")
    monkeypatch.setattr(sc, "UNIVERSE", tmp_path / "universe")
    (tmp_path / "universe").mkdir()
    for sym in sc.TARGETS:
        for chart in ("M5", "M15", "H1", "H4", "D1"):
            (tmp_path / "universe" / f"{sym}_{chart}.parquet").write_bytes(b"")
    r = sc.Run(dry_run=False, budget_s=60.0)
    r.conn = R.connect()
    r.sensors = sc.sensor_bank(axes_dir=tmp_path / "axes")
    yield r
    r.conn.close()


# --------------------------------------------------------------------- the L1vsun families
@pytest.mark.parametrize("family,generator", [
    (sc.family_funding_ecology, "l1vsun:funding_ecology"),
    (sc.family_forced_flow, "l1vsun:forced_flow"),
    (sc.family_narrative, "l1vsun:narrative"),
])
def test_each_family_records_discoveries_with_descendants(run, family, generator):
    ids = family(run)
    assert ids, f"{generator} recorded nothing"
    rows = [d for d in run.discoveries if str(d["generator"]).startswith(generator)]
    assert rows, "no discovery carries this generator"
    kids = [d for d in rows if ":" in str(d["generator"]).removeprefix(generator)]
    assert kids, f"{generator} minted no descendants through the transformation miners"
    assert all(k["parents"] for k in kids), "a descendant with no parent is an orphan"
    # every descendant lands on an MT5 target and never on an equity
    for k in kids:
        sym = str(k["spec"].get("symbol") or "")
        assert sym in sc.TARGETS or sym == "", f"{sym} is not an MT5 target of this desk"


def test_a_family_is_never_a_bare_copy_of_the_published_rule(run):
    """The published threshold is ONE RUNG. If the family only ever mints it, the desk has
    inherited somebody else's overfit instead of measuring the parameter."""
    sc.family_funding_ecology(run)
    rungs = {float(d["spec"]["params"]["funding_percentile"])
             for d in run.discoveries
             if d["generator"] == "l1vsun:funding_ecology"}
    published = sc.PRIORS["funding_percentile"].published
    assert published in rungs, "the published rung must still be tested"
    assert len(rungs) > 1, "only the published value was minted: that is a copy, not research"
    assert rungs == set(sc.PRIORS["funding_percentile"].rungs())


def test_the_forced_flow_family_mints_all_three_populations(run):
    sc.family_forced_flow(run)
    pops = {str(d["spec"]["params"]["population"]) for d in run.discoveries
            if d["generator"] == "l1vsun:forced_flow"}
    assert pops == {"continuation", "reversal", "delayed_reversal"}


def test_a_descendant_needing_an_absent_sensor_is_blocked_by_name(run):
    sc.family_funding_ecology(run)
    assert run.blocked, "no descendant was blocked although every sensor leg is UNMEASURED here"
    blocked = run.blocked[0]
    assert blocked["legs"], "a block with no named leg is a silent drop"
    row = R.discoveries(state="BLOCKED", conn=run.conn)
    assert row and "UNMEASURED" in str(row[0]["blocked_reason"])


def test_an_absent_sensor_is_unmeasured_not_zero(tmp_path):
    bank = sc.sensor_bank(axes_dir=tmp_path / "nothing")
    assert set(bank) == set(sc.SENSOR_LEGS)
    assert all(r.verdict == sc.UNMEASURED and r.value is None for r in bank.values())
    assert all("crypto_" in r.path for r in bank.values())


def test_a_present_axis_file_is_read(tmp_path):
    axes = tmp_path / "axes"
    axes.mkdir()
    (axes / "crypto_funding_level.json").write_text(
        json.dumps({"value": 0.62, "at": "2026-09-17T00:00:00+00:00"}), encoding="utf-8")
    r = sc.sensor("funding_level", axes_dir=axes)
    assert r.measured and r.value == pytest.approx(0.62)


# --------------------------------------------------------------------- narrative lifecycle
def test_narrative_saturation_needs_a_population_denominator():
    now = datetime(2026, 9, 17, tzinfo=UTC)
    claims = [{"created_at": (now - timedelta(hours=h)).isoformat(), "source_id": f"s{h % 3}",
               "language": "en"} for h in range(1, 20)]
    without = sc.narrative_state(claims, now=now)
    assert without["saturation_share"] == sc.UNMEASURED
    withd = sc.narrative_state(claims, now=now, active_sources=4)
    assert withd["saturation_share"] == pytest.approx(3 / 4)
    assert withd["cross_platform_diffusion"] == 3


def test_narrative_with_no_timestamped_claim_is_unmeasured():
    assert sc.narrative_state([])["verdict"] == sc.UNMEASURED


# --------------------------------------------------------------------- thesis clocks
def test_thesis_clocks_for_planted_sleeves(tmp_path):
    now = datetime(2026, 9, 17, tzinfo=UTC)
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "xau_asia", "symbol": "XAUUSD", "family": "session_range_breakout",
         "status": "LIVE", "thesis_refreshed_at": (now - timedelta(days=45)).isoformat()},
        {"name": "fresh", "symbol": "USDJPY", "family": "carry", "status": "LIVE",
         "thesis_refreshed_at": (now - timedelta(days=2)).isoformat()},
        {"name": "never", "symbol": "AUDUSD", "family": "", "status": "STANDBY"},
    ]}), encoding="utf-8")
    shadow = tmp_path / "shadow.json"
    shadow.write_text(json.dumps({"XAUUSD.asia": {"n": 14, "first_entry":
                                                  (now - timedelta(days=9)).isoformat()}}),
                      encoding="utf-8")
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"events": [
        {"date": "2026-09-18", "kind": "central_bank", "name": "FOMC",
         "window_start_utc": (now + timedelta(hours=6)).isoformat()}]}), encoding="utf-8")
    out = sc.thesis_clocks(now=now, sleeves_path=sleeves, shadow_path=shadow, calendar_path=cal)

    assert out["tradeable"] is False, "a thesis clock must never present itself as tradeable"
    assert out["n"] == 4
    stale = out["clocks"]["sleeve:xau_asia"]
    assert stale["thesis_age_days"] == pytest.approx(45.0, abs=0.1)
    assert stale["model_still_applies"] is False        # stale AND a catalyst 6h away
    assert out["clocks"]["sleeve:never"]["thesis_age_days"] == sc.UNMEASURED
    assert out["clocks"]["sleeve:never"]["model_still_applies"] == sc.UNMEASURED
    assert out["unmeasured_refresh"] == 1
    assert out["clocks"]["clock:XAUUSD.asia"]["kind"] == "enrolled_clock"
    cat = stale["next_catalyst"]
    assert cat["verdict"] == "MEASURED" and cat["kind"] == "central_bank"


def test_next_catalyst_with_no_future_row_is_unmeasured():
    now = datetime(2026, 9, 17, tzinfo=UTC)
    past = [{"date": "2020-01-01", "kind": "central_bank", "name": "FOMC"}]
    assert sc.next_catalyst("XAUUSD", past, now)["verdict"] == sc.UNMEASURED


# --------------------------------------------------------------------- gate attribution
def test_gate_attribution_is_measured_when_both_arms_exist(tmp_path):
    shadow = tmp_path / "shadow.json"
    shadow.write_text(json.dumps({
        "GOOD.asia": {"r_series": [0.9, 1.1, 0.8, 1.2, 1.0]},
        "BAD.asia": {"r_series": [-0.6, -0.9, -0.4, -1.1, -0.7]},
    }), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in [
        {"cell": "GOOD.session_range_breakout.p=1", "sym": "GOOD", "passed": True,
         "terminal_gate": "deflated_sharpe"},
        {"cell": "BAD.session_range_breakout.p=2", "sym": "BAD", "passed": False,
         "terminal_gate": "deflated_sharpe"},
    ]), encoding="utf-8")
    out = sc.gate_attribution(shadow_path=shadow, ledger_path=ledger,
                              reconcile_path=tmp_path / "absent.json")
    ds = out["gates"]["deflated_sharpe"]
    assert ds["verdict"] == "MEASURED"
    assert ds["delta_elog"] > 0 and ds["pays_for_itself"] is True
    assert ds["n_with"] == 5 and ds["n_without"] == 5
    assert "deflated_sharpe" in out["measured_gates"]


def test_gate_attribution_is_unmeasured_by_name_when_the_counterfactual_is_absent(tmp_path):
    shadow = tmp_path / "shadow.json"
    shadow.write_text(json.dumps({"GOOD.asia": {"r_series": [0.5, 0.4, 0.6]}}), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"cell": "GOOD.x.p=1", "sym": "GOOD", "passed": True,
                                  "terminal_gate": "pbo"}), encoding="utf-8")
    out = sc.gate_attribution(shadow_path=shadow, ledger_path=ledger,
                              reconcile_path=tmp_path / "absent.json")
    for gate in sc.PROMOTION_GATES:
        row = out["gates"][gate]
        assert row["verdict"] == sc.UNMEASURED
        assert "UNMEASURED" in row["why"] and "not zero" in row["why"]
    assert out["measured_gates"] == []
    assert set(out["unmeasured_gates"]) == set(sc.PROMOTION_GATES)


# --------------------------------------------------------------------- bounded LLM contribution
def test_the_bounded_llm_policy_refuses_a_size_field():
    ok, why = sc.check_seat_row({"family": "carry", "symbols": ["XAUUSD"],
                                 "probability_delta": 0.05})
    assert ok and "no capital authority" in why
    for field in ("size", "lot", "risk_frac", "leverage", "position_size", "weight"):
        bad, why = sc.check_seat_row({"family": "carry", field: 0.01})
        assert bad is False, f"{field} was admitted: a seat just gained capital authority"
        assert field in why, "the refusal must name the offending field"


def test_the_bounded_llm_policy_bounds_the_probability_delta():
    assert sc.check_seat_row({"probability_delta": 0.10})[0] is True
    bad, why = sc.check_seat_row({"probability_delta": 0.4})
    assert bad is False and "0.10" in why
    assert sc.LLM_CONTRIBUTION["capital_authority"] is False


# --------------------------------------------------------------------- provenance firewall
def test_the_provenance_firewall_refuses_dust_and_copied_flow_and_admits_a_receipt():
    for kind in ("dust", "airdrop", "copied", "relayed", "wash"):
        ok, why = sc.genuine({"participant": "p1", "provenance": kind,
                              "receipt": {"initiator": "p1", "confirmed": True}})
        assert ok is False, f"{kind} flow was counted as this participant's own decision"
        assert kind in why
    ok, why = sc.genuine({"participant": "p1", "provenance": "self_initiated"})
    assert ok is False and "no receipt" in why
    ok, why = sc.genuine({"participant": "p1", "provenance": "self_initiated",
                          "receipt": {"initiator": "p2", "confirmed": True}})
    assert ok is False and "not the participant" in why
    ok, why = sc.genuine({"participant": "p1", "provenance": "self_initiated",
                          "receipt": {"initiator": "p1", "confirmed": True}})
    assert ok is True


# --------------------------------------------------------------------- skill posteriors
def test_skill_posteriors_control_for_beta():
    """A pure beta account has NO skill, and the posterior must say so after residualising."""
    rng = np.random.default_rng(5)
    market = rng.normal(0.02, 0.01, 400)
    beta_only = 1.5 * market + rng.normal(0.0, 0.004, 400)   # beta plus zero-mean noise
    naive = sc.skill_posterior(beta_only)
    controlled = sc.skill_posterior(beta_only, market=market)
    assert naive["p_skill"] > 0.99, "an uncontrolled read must look brilliant -- that is the trap"
    assert controlled["beta"] == pytest.approx(1.5, abs=0.02)
    assert controlled["p_skill"] == pytest.approx(0.5, abs=0.2)
    assert abs(controlled["t_stat"]) < abs(naive["t_stat"]) / 10.0
    assert "beta" in controlled["controls"] and "survival" in controlled["controls"]


def test_a_pure_beta_account_has_no_residual_to_be_confident_about():
    rng = np.random.default_rng(15)
    market = rng.normal(0.02, 0.01, 300)
    out = sc.skill_posterior(2.0 * market, market=market)
    assert out["p_skill"] == pytest.approx(0.5)
    assert out["residual_share"] < 1e-6 and "no residual" in out["why"]


def test_skill_posteriors_discount_leverage_copying_and_survival():
    rng = np.random.default_rng(6)
    r = rng.normal(0.01, 0.02, 300)
    plain = sc.skill_posterior(r)
    copied = sc.skill_posterior(r, copy_share=0.9)
    assert copied["n_effective"] < plain["n_effective"]
    assert copied["p_skill"] < plain["p_skill"], "copied flow must not buy confidence"
    shaded = sc.skill_posterior(r, survival_rate=0.2)
    assert abs(shaded["p_skill"] - 0.5) < abs(plain["p_skill"] - 0.5)
    assert sc.skill_posterior([0.1, 0.2])["verdict"] == sc.UNMEASURED


def test_ten_correlated_participants_count_as_one_event():
    rng = np.random.default_rng(9)
    leader = rng.normal(0, 1, 200)
    herd = [leader + rng.normal(0, 1e-6, 200) for _ in range(10)]
    out = sc.cohort_information(herd)
    assert out["mean_pairwise_corr"] > 0.99
    assert out["n_effective"] == pytest.approx(1.0, abs=0.05)
    independent = [rng.normal(0, 1, 200) for _ in range(10)]
    ind = sc.cohort_information(independent)
    assert ind["n_effective"] > 5.0


# --------------------------------------------------------------------- insider classifier
def test_the_insider_classifier_separates_routine_from_opportunistic():
    rows = []
    for year in (2023, 2024, 2025, 2026):                 # a March schedule: routine
        rows.append({"insider": "scheduled", "ticker": "Apple", "date": f"{year}-03-10"})
    rows.append({"insider": "discretionary", "ticker": "Apple", "date": "2026-07-02"})
    out = sc.classify_insider_rows(rows)
    labels = {(r["insider"], r["date"]): r["label"] for r in out["rows"]}
    assert labels[("scheduled", "2023-03-10")] == "opportunistic"     # no prior year yet
    assert labels[("scheduled", "2026-03-10")] == "routine"
    assert labels[("scheduled", "2024-03-10")] == "routine"
    assert labels[("discretionary", "2026-07-02")] == "opportunistic"
    # three of the four scheduled sales are routine; the first one and the discretionary sale
    # are not -- 2/5, which is the whole point of the split
    assert out["n_opportunistic"] == 2
    assert out["opportunistic_breadth"] == pytest.approx(2 / 5)


def test_the_insider_classifier_yields_only_an_index_level_sensor(run):
    rows = [{"insider": "a", "ticker": "Apple", "date": "2026-07-02"}]
    out = sc.classify_insider_rows(rows)
    assert out["single_name_signals"] == [], "a single-name signal escaped the event lane"
    assert out["index_sensor"]["targets"] == ["NAS100", "US500"]
    assert out["index_sensor"]["lane"] == "event"
    minted = sc.family_insider_breadth(run, rows)
    symbols = {d["spec"]["symbol"] for d in run.discoveries
               if d["generator"] == "primitive:insider_breadth"}
    assert len(minted) == 2 and symbols == {"NAS100", "US500"}


def test_the_insider_classifier_with_no_rows_is_unmeasured():
    out = sc.classify_insider_rows([])
    assert out["verdict"] == sc.UNMEASURED and out["index_sensor"] is None


# --------------------------------------------------------------------- the cheap/expensive router
def test_the_router_sends_only_high_value_items_and_counts_one_wire_once():
    items = [
        {"wire": "reuters:cpi", "novelty": 0.9, "surprise": 0.9, "evig": 0.9},
        *[{"wire": "reuters:cpi", "novelty": 0.9, "surprise": 0.9, "evig": 0.9}
          for _ in range(9)],                       # ten monitors, ONE wire
        {"wire": "blog:noise", "novelty": 0.9, "surprise": 0.1, "evig": 0.1},
        {"wire": "feed:routine", "novelty": 0.1, "surprise": 0.1, "evig": 0.1},
    ]
    out = sc.route(items)
    assert out["n_items"] == 12
    assert out["n_information_events"] == 3, "ten monitors on one wire must count as one event"
    assert out["n_expensive"] == 1
    cpi = next(r for r in out["routed"] if r["wire"] == "reuters:cpi")
    assert cpi["n_monitors"] == 10 and cpi["information_events"] == 1
    assert cpi["destination"] == "expensive_reasoner"
    assert all(r["destination"] == "deterministic_monitor"
               for r in out["routed"] if r["wire"] != "reuters:cpi")


def test_the_router_threshold_is_a_policy_object():
    items = [{"wire": "w", "novelty": 0.5, "surprise": 0.5, "evig": 0.5}]     # score 0.125
    assert sc.route(items)["n_expensive"] == 0
    assert sc.route(items, sc.RoutingPolicy(threshold=0.1))["n_expensive"] == 1


# --------------------------------------------------------------------- the interaction forge
def test_the_forge_records_agreement_and_disagreement_and_screens_when_legs_exist(run):
    rng = np.random.default_rng(4)
    driver = rng.normal(0, 1, 400)
    follower = np.concatenate([np.zeros(3), driver[:-3]]) + rng.normal(0, 0.2, 400)
    ids = sc.interaction_forge(run, {"funding_level": driver.tolist(),
                                     "prediction_probability": follower.tolist()})
    assert ids
    rows = [d for d in run.discoveries if str(d["generator"]).startswith("forge:")]
    stances = {str(d["spec"]["params"]["stance"]) for d in rows}
    assert stances == {"agreement", "disagreement"}, "only one arm of the forge was minted"
    cells = {str(d["spec"]["params"]["interaction_cell"]) for d in rows}
    assert cells == {c["cell"] for c in sc.INTERACTION_CELLS}

    screened = [d for d in rows
                if d["spec"]["params"]["interaction_cell"] == "funding_x_prediction"]
    assert screened[0]["spec"]["lead_lag_screen"]["verdict"] == "MEASURED"
    assert screened[0]["spec"]["lead_lag_screen"]["p_value"] < 0.05
    unscreened = [d for d in rows
                  if d["spec"]["params"]["interaction_cell"] == "hawkes_x_risk_off_x_gold"]
    assert unscreened[0]["spec"]["lead_lag_screen"]["verdict"] == sc.UNMEASURED


def test_lead_lag_reports_a_null_and_refuses_a_short_series():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 500)
    b = rng.normal(0, 1, 500)
    out = sc.lead_lag(a, b, permutations=100)
    assert out["verdict"] == "MEASURED" and 0.0 < out["p_value"] <= 1.0
    assert out["null"].startswith("block permutation")
    assert sc.lead_lag([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])["verdict"] == sc.UNMEASURED


# --------------------------------------------------------------------- Hawkes discoveries
def test_hawkes_discoveries_are_unmeasured_without_bars(run, monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "UNIVERSE", tmp_path / "nothing")
    ids = sc.hawkes_discoveries(run, charts=("H1",))
    assert ids, "the hypothesis must be minted even where the bars are absent"
    row = next(d for d in run.discoveries if d["generator"] == "primitive:hawkes")
    assert row["spec"]["measured_state"]["verdict"] == sc.UNMEASURED
    assert any("no bars" in n["why"] for n in run.notes)


# --------------------------------------------------------------------- the legality router
def test_legality_routes_rather_than_discarding():
    fringe = sc.classify_source({"source_id": "s", "access_label": "PUBLIC_SOCIAL",
                                 "credibility": "FRINGE"})
    assert fringe["route"] == "RESEARCHABLE" and fringe["may_consume_content"] is True
    assert fringe["evidence_weight"] == pytest.approx(0.15)
    assert fringe["refused"] is False, "fringe PUBLIC material must never be deleted"

    # LAWS 5e (2026-09-23): PUBLIC_WITH_TERMS routed to API_OR_MANUAL with
    # `machine_use_allowed is False` until then -- a machine-extraction veto the desk wrote for
    # itself. It is RESEARCHABLE and mined now; what the terms withhold is `redistribute`.
    terms = sc.classify_source({"source_id": "s", "access_label": "PUBLIC_WITH_TERMS",
                                "credibility": "AUTHORITATIVE"})
    assert terms["route"] == "RESEARCHABLE" and terms["machine_use_allowed"] is True
    assert terms["redistribute_allowed"] is False and terms["may_consume_content"] is True

    # ...and ACCESS_UNCLEAR was QUARANTINED with its content unconsumed. Also deleted: the label
    # still says the access path is unresolved, and the row is mined and tested with it attached.
    unclear = sc.classify_source({"source_id": "s"})
    assert unclear["access_label"] == "ACCESS_UNCLEAR", "unknown must not resolve to PUBLIC"
    assert unclear["quarantined"] is False and unclear["may_consume_content"] is True
    assert unclear["machine_use_allowed"] is True
    assert unclear["route"] == "RESEARCHABLE"

    # OPEN_DATA is the one label that also grants redistribution.
    assert sc.classify_source({"access_label": "OPEN_DATA"})["redistribute_allowed"] is True

    for label in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED"):
        row = sc.classify_source({"source_id": "s", "access_label": label})
        assert row["refused"] is True and row["may_consume_content"] is False
        assert row["why"]

    # The hard boundary is FIVE ACTS and no more -- the count is what a later session cannot
    # quietly grow, so it is asserted against the classifier that owns it.
    from libs.research import access_classifier as ac
    assert list(sc.HARD_BOUNDARY) == list(ac.HARD_BOUNDARY)
    assert len(sc.HARD_BOUNDARY) == ac.HARD_BOUNDARY_COUNT == 5
    assert not any(v["route"] == "QUARANTINE" for v in sc.ACCESS_BEHAVIOUR.values())

    assert list(sc.SOURCE_PIPELINE) == ["DISCOVER", "CAPTURE_METADATA", "ACCESS_CLASSIFICATION",
                                        "EVIDENCE_CLASSIFICATION", "RESEARCH"]
    assert all(lab in sc.ACCESS_BEHAVIOUR for lab in sc.ACCESS_LABELS)


def test_the_three_labels_are_independent():
    a = sc.classify_source({"access_label": "PUBLIC", "credibility": "CONTRADICTED"})
    b = sc.classify_source({"access_label": "PUBLIC", "credibility": "AUTHORITATIVE"})
    assert a["route"] == b["route"] == "RESEARCHABLE"
    assert a["evidence_weight"] < b["evidence_weight"]
    assert a["predictive_state"] == b["predictive_state"] == "UNTESTED"


# --------------------------------------------------------------------- recursive source discovery
def test_seed_nodes_are_expanded_but_never_monitored(run):
    out = sc.seed_source_scout(run)
    assert out["any_seed_monitored"] is False
    assert {s["handle"] for s in sc.SEED_NODES} == {"RohOnChain", "L1vsun", "bl888m"}
    assert all(s["monitored"] is False and s["feeds_or_posts_mined"] is False
               for s in sc.SEED_NODES)
    for seed in out["seeds"]:
        assert seed["stop_reason"], "a walk that stopped with no recorded reason is not exhaustion"
        assert seed["layers"], "no layer was walked"
    rows = run.conn.execute("SELECT source_id, kind FROM sources").fetchall()
    kinds = {str(r["kind"]) for r in rows}
    assert "seed_node" in kinds and "paper" in kinds


def test_every_expansion_hop_writes_a_provenance_edge(run):
    seed = next(s for s in sc.SEED_NODES if s["handle"] == "L1vsun")
    out = sc.expand_seed(run, seed)
    edges = R.descendants_of("source", "seed:L1vsun", conn=run.conn)
    assert edges, "no provenance edge: a survivor's credit could never walk back to the seed"
    assert all(str(e["relation"]).startswith("expanded:") for e in edges)
    assert out["layers_walked"] >= 1


def test_the_recursion_records_why_it_stopped(run):
    seed = next(s for s in sc.SEED_NODES if s["handle"] == "bl888m")
    out = sc.expand_seed(run, seed, floor=0.99)
    assert out["exhausted"] is False
    assert "marginal information value" in out["stop_reason"]
    assert "opportunity floor" in out["stop_reason"]


# --------------------------------------------------------------------- the pass
def test_dry_run_writes_nothing(tmp_path, monkeypatch, registry):
    report = tmp_path / "SOURCE_CIVILIZATIONS.json"
    clocks = tmp_path / "thesis_clocks.json"
    attribution = tmp_path / "GATE_ATTRIBUTION.json"
    monkeypatch.setattr(sc, "REPORT", report)
    monkeypatch.setattr(sc, "THESIS_CLOCKS", clocks)
    monkeypatch.setattr(sc, "GATE_ATTRIBUTION", attribution)
    monkeypatch.setattr(sc, "UNIVERSE", tmp_path / "universe")
    monkeypatch.setattr(sc, "AXES", tmp_path / "axes")
    monkeypatch.setattr(sc, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(sc, "SHADOW_STATE", tmp_path / "shadow.json")
    monkeypatch.setattr(sc, "CALENDAR", tmp_path / "cal.json")
    monkeypatch.setattr(sc, "GATE_LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(sc, "FORWARD_RECONCILE", tmp_path / "fr.json")

    out = sc.run_pass(dry_run=True, budget_s=20.0)
    assert out["dry_run"] is True and out["discoveries_recorded"] > 0
    assert not report.exists() and not clocks.exists() and not attribution.exists()
    assert not R.path().exists(), "a dry run opened the registry"
    assert out["no_author_monitored"] is True
    assert out["access_policy"]["hard_boundary"]
    assert out["sensor_gaps"] == list(sc.SENSOR_LEGS)


def test_the_report_publishes_the_specialist_checklist_and_the_forge(tmp_path, monkeypatch,
                                                                    registry):
    for name in ("UNIVERSE", "AXES"):
        monkeypatch.setattr(sc, name, tmp_path / name.lower())
    for name in ("SLEEVES", "SHADOW_STATE", "CALENDAR", "FORWARD_RECONCILE"):
        monkeypatch.setattr(sc, name, tmp_path / f"{name.lower()}.json")
    monkeypatch.setattr(sc, "GATE_LEDGER", tmp_path / "ledger.jsonl")
    out = sc.run_pass(dry_run=True, budget_s=20.0)
    disciplines = {d["discipline"] for d in out["specialist_discipline"]}
    assert disciplines == {"role_separation", "second_source_verification",
                           "explicit_candidate_identity", "falsification_before_execution",
                           "single_execution_authority", "permanent_failed_idea_log"}
    assert all(d["enforced_by"] and d["how"] for d in out["specialist_discipline"])
    assert len(out["interaction_cells"]) == 9
    assert out["families"]["l1vsun:specialist_discipline"] == 6


# ================= THE PARALLEL CIVILIZATION LAYER (frontier expansion, never a second miner)
def test_the_roster_is_imported_from_the_federation_never_restated():
    """Two rosters drift within a week. The systems here ARE external_federation.SEEDS."""
    systems = [e for e in sc.seed_universe() if e.kind == "system"]
    assert len(systems) == len(sc.XF.SEEDS)
    assert {e.entity_id for e in systems} == {f"system:{s.system_id}" for s in sc.XF.SEEDS}
    # the disposition vocabulary, the packet contract and the exhaustion law are the federation's
    assert sc.exhaustion("e", {})["conditions"] == list(sc.XF.EXHAUSTION_CONDITIONS)


def test_the_seed_universe_covers_every_kind_and_names_its_registry_gaps():
    u = sc.seed_universe()
    assert {e.kind for e in u} == set(sc.ENTITY_KINDS)
    names = {e.name for e in u}
    for expected in ("WorldQuant BRAIN", "arXiv q-fin / cs.LG", "Two Sigma", "L1vsun"):
        assert expected in names, expected
    gaps = sc.registry_gaps()
    assert "XTX" not in gaps, "XTX Markets is in FIRMS; the alias must stop a false gap"
    assert all(g in sc._INSTITUTIONS for g in gaps)


def test_public_lineages_are_nodes_and_are_never_monitored():
    lineages = [e for e in sc.seed_universe() if e.kind == "public_lineage"]
    assert {e.name for e in lineages} == {"RohOnChain", "L1vsun", "bl888m"}
    assert all(e.monitored is False for e in lineages)
    assert all("never monitored or mined" in e.note for e in lineages)


def test_the_twelve_roles_run_over_already_fetched_material_and_fetch_nothing(run):
    entity = next(e for e in sc.seed_universe() if e.kind == "system")
    material = sc.gather(entity, run)
    assert all("frontier" in f or "moat" in f for f in material.fetched_by)
    out = sc.run_roles(entity, material, run)
    assert list(out["roles"]) == list(sc.CIVILIZATION_ROLES)
    assert len(sc.CIVILIZATION_ROLES) == 12
    assert out["n_rows"] > 0
    # the surfaces nobody captured are REPORTED, never implied to have been read
    assert set(out["surfaces_missing"]) <= set(sc.REPO_SURFACES)
    assert "FAILURE_MINER" in out["silent_roles"] or material.rows("issues")


def test_a_raising_role_costs_the_other_eleven_nothing(run, monkeypatch):
    def boom(_e, _m, _r):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(sc.ROLE_FUNCS, "MECHANISM_DECOMPILER", boom)
    entity = next(e for e in sc.seed_universe() if e.kind == "system")
    out = sc.run_roles(entity, sc.gather(entity, run), run)
    assert out["roles"]["MECHANISM_DECOMPILER"] == 0
    assert out["roles"]["SOURCE_SCOUT"] == 1
    assert any("kaboom" in n["why"] for n in run.notes)


def test_the_extraction_schema_is_closed_and_every_field_is_present():
    row = sc.extraction_row(source_id="s", mechanism="m")
    assert set(row) == set(sc.EXTRACTION_FIELDS)
    assert len(sc.EXTRACTION_FIELDS) == 36
    assert row["leakage_risks"] == sc.UNMEASURED, "an unfilled field must be UNMEASURED BY NAME"
    with pytest.raises(ValueError, match="not extraction-schema fields"):
        sc.extraction_row(source_id="s", sharpe=2.0)


def test_schema_completeness_names_the_fields_nobody_ever_fills():
    rows = [sc.extraction_row(source_id="a", mechanism="m"),
            sc.extraction_row(source_id="b", mechanism="n", falsifier="f")]
    out = sc.schema_completeness(rows)
    assert out["filled"]["source_id"] == 2 and out["filled"]["falsifier"] == 1
    assert "leakage_risks" in out["never_filled"]
    assert sc.schema_completeness([])["verdict"] == sc.UNMEASURED


def test_the_capability_ledger_carries_every_field_and_joins_the_federation():
    entity = next(e for e in sc.seed_universe() if e.entity_id == "system:qlib")
    row = sc.capability_ledger(entity, capabilities_discovered=3, compute_spent=10.0,
                               forward_survivors=2, incremental_portfolio_elog=0.01)
    assert all(f in row for f in sc.CAPABILITY_LEDGER_FIELDS)
    assert len(sc.CAPABILITY_LEDGER_FIELDS) == 17
    assert row["federation"]["system_id"] == "qlib"
    assert row["source_roi_verdict"] == "MEASURED"
    lonely = sc.capability_ledger(next(e for e in sc.seed_universe() if e.kind == "institution"))
    assert lonely["federation"]["verdict"] == sc.UNMEASURED
    assert lonely["source_roi"] is None, "an ROI on zero spend is not a number"


def test_delta_scanning_costs_near_zero_on_an_unchanged_entity():
    surfaces = {"repo": "abc", "releases": "v1"}
    first = sc.delta_scan("e", surfaces)
    assert first["first_scan"] is True and first["compute_posture"] == "targeted_re_analysis"
    same = sc.delta_scan("e", surfaces, first)
    assert same["changed"] is False
    assert same["compute_posture"] == "maintenance_delta_scouting"
    assert same["next_delta_scan"] > same["last_deep_scan"]
    moved = sc.delta_scan("e", {"repo": "abc", "releases": "v2"}, first)
    assert moved["changed"] is True and moved["compute_posture"] == "targeted_re_analysis"
    assert "never switched off" in moved["rule"]


def test_source_roi_never_closes_a_frontier_only_throttles_it():
    poor = sc.source_roi_s({"compute_spent": 100.0, "forward_survivors": 0.0,
                            "incremental_portfolio_elog": 0.0})
    assert poor["verdict"] == "MEASURED" and poor["posture"] == "maintenance_delta_scouting"
    assert "never closes one" in poor["rule"]
    rich = sc.source_roi_s({"compute_spent": 1.0, "forward_survivors": 3.0,
                            "incremental_portfolio_elog": 1.0})
    assert rich["posture"] == "active"
    assert sc.source_roi_s({})["verdict"] == sc.UNMEASURED


def test_candidate_conservation_names_a_leak():
    assert sc.candidate_conservation({"DISCOVERED": 10, "TESTED": 4, "WAITING": 6})["balances"]
    leak = sc.candidate_conservation({"DISCOVERED": 10, "TESTED": 4})
    assert leak["balances"] is False and leak["unaccounted"] == 6
    assert set(sc.CANDIDATE_STATES) == {"DEDUPLICATED", "TESTED", "WAITING", "BLOCKED",
                                        "REJECTED", "NONTESTABLE"}


def test_every_dataset_gets_exactly_one_downstream_state():
    assert sc.route_dataset({"name": "order book fills"})["state"] == "EXECUTION_INPUT"
    assert sc.route_dataset({"name": "CPI release"})["state"] == "WORLD_MODEL_INPUT"
    assert sc.route_dataset({"name": "retracted factor"})["state"] == "NEGATIVE_KNOWLEDGE"
    orphan = sc.route_dataset({"name": "a thing nobody named"})
    assert orphan["state"] == "AWAITING_EXPERIMENT"
    assert "nobody reads" in orphan["why"]
    assert sc.route_dataset({"state": "PORTFOLIO_INPUT"})["state"] == "PORTFOLIO_INPUT"
    assert all(sc.route_dataset({"name": n})["state"] in sc.DATASET_STATES
               for n in ("x", "spread", "covariance", "tick"))


def test_descendants_are_priced_and_delay_is_a_real_cost():
    cheap = sc.descendant_value({"p_survive": 0.2, "d_elog": 0.02, "info": 1.0, "novelty": 1.0,
                                 "orthogonality": 1.0, "c_compute": 1.0})
    delayed = sc.descendant_value({"p_survive": 0.2, "d_elog": 0.02, "info": 1.0, "novelty": 1.0,
                                   "orthogonality": 1.0, "c_compute": 1.0, "c_delay": 9.0})
    assert cheap > delayed * 5, "a descendant blocked on an absent dataset must be priced down"
    assert sc.descendant_value({}) == 0.0
    assert len(sc.GENOME_AXES) == 7
    assert [a for a, _ in sc.GENOME_AXES] == ["D", "R", "S", "T", "H", "E", "P"]


def test_orthogonality_is_measured_across_all_eleven_axes():
    rng = np.random.default_rng(101)
    base = rng.normal(0, 1, 300)
    out = sc.orthogonality({"return": base.tolist(), "failure_mode": base.tolist()})
    assert out["verdict"] == "MEASURED"
    assert out["independent"] is False, "two identical axes are one bet"
    assert out["worst_abs_corr"] > 0.99
    assert len(out["unmeasured_axes"]) == 9, "the nine unmeasured axes must be NAMED"
    assert len(sc.ORTHOGONALITY_AXES) == 11
    assert sc.orthogonality({"return": base.tolist()})["verdict"] == sc.UNMEASURED


def test_new_civilizations_spawn_from_the_graph_never_from_a_roster_edit():
    out = sc.spawn([
        {"signal": "citation_cluster", "kind": "system", "name": "Nobody Has Named This"},
        {"signal": "contributor_graph", "kind": "system", "name": "Qlib"},
        {"signal": "somebody_said_so", "name": "Hype"},
        {"signal": "benchmark_leader", "name": ""},
    ])
    assert out["n_spawned"] == 1
    assert out["spawned"][0].seed is False
    assert out["spawned"][0].discovered_via == "citation_cluster"
    whys = " ".join(r["why"] for r in out["refused"])
    assert "not a spawn trigger" in whys and "no named entity" in whys
    assert len(sc.SPAWN_SIGNALS) == 10


def test_capabilities_not_brands():
    assert "mcts" in sc.CAPABILITY_MAP["agonalpha"]
    assert "ast novelty" in sc.CAPABILITY_MAP["alphaagent"]
    assert "research/live parity" in sc.CAPABILITY_MAP["lean"]
    cells = {c["cell"] for c in sc.SYNTHESIS_CELLS}
    assert cells == {"search_x_verify_x_evolve", "execution_scientist"}
    exec_cell = next(c for c in sc.SYNTHESIS_CELLS if c["cell"] == "execution_scientist")
    assert set(exec_cell["systems"]) == {"nautilus", "lean", "hummingbot"}


def test_every_worker_declares_a_consumer_and_a_postcondition():
    plane = sc.control_plane()
    assert {w["component_id"] for w in plane} == {"source_civilizations", "evidence_watchtower",
                                                  "prediction_markets"}
    for w in plane:
        assert set(w) == set(sc.CONTROL_PLANE_FIELDS)
        assert w["consumer"] and w["postcondition"] and "hourly" in w["cadence"]


def test_a_civilization_pass_is_delta_first_and_writes_a_ledger(run):
    out = sc.civilization_pass(run, max_entities=3)
    assert out["entities_processed"] == 3
    assert out["universe"] > 50
    assert out["extraction_rows"] > 0
    assert len(out["ledger"]) == 3
    assert out["candidate_conservation"]["balances"] is True
    assert all(r["delta"]["compute_posture"] == "targeted_re_analysis" for r in out["results"])
    assert "already captured" in out["not_a_fetcher"]
    assert out["completeness"]["verdict"] == "MEASURED"
