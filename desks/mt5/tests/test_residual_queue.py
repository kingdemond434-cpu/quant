"""THE RESIDUAL QUEUE, BUILT OVER A SYNTHETIC DESK WHOSE EVERY RESIDUAL IS PLANTED.

An organ that joins nine artifacts is exactly the organ nobody can eyeball on live data: a row
that silently failed to parse looks identical to a producer that had nothing to say. So every
producer here is written under tmp_path with ONE known residual in it, and each test asserts the
queue recovered THAT residual -- the right level, the right magnitude, the right family.

And the other half of the contract, which matters as much: ids are stable across passes, a
residual seen twice is one item whose recurrence is two, a producer that later explains an item
below 0.2 retires it to EXPLAINED, an item nobody has seen for fourteen days goes STALE, a family
the registry does not hold is refused rather than invented, a single-name equity may sit in the
queue and may never leave in a donation, and `--dry-run` writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import residual_queue as rq  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: The synthetic broker registry. EURUSD/GBPUSD/USDJPY/AUDUSD/NZDUSD/XAUUSD are the hypothesis
#: lane; Apple is a share CFD and is the EVENT lane -- tradable, never hunted.
REGISTRY = {s: {"asset_class": "forex"} for s in
            ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "AUDJPY", "USDCHF", "NAS100")}
REGISTRY["XAUUSD"] = {"asset_class": "metals"}
REGISTRY["Apple"] = {"asset_class": "equities"}


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, list):
        path.write_text("".join(json.dumps(r) + "\n" for r in payload), "utf-8")
    else:
        path.write_text(json.dumps(payload), "utf-8")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """One synthetic desk: every producer written, every path in the organ repointed at it."""
    _write(tmp_path / "universe.json", REGISTRY)
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "universe.json")
    up._registry.cache_clear()

    _write(tmp_path / "STANDING_QUESTIONS.json", {"at": "2026-09-16T00:00:00+00:00", "questions": {
        "Q1": {"findings": [{"target": "USDJPY", "feature": "clock_hour_01", "category": "clock",
                             "lift": 4.5, "p_perm": 0.005, "n_events": 118}]},
        "Q2": {"findings": [{"symbol": "EURUSD", "lead_bars": 2, "corr": 0.08, "n": 4067,
                             "t": 5.19, "p_bonf": 2.7e-05}]},
        "Q3": {"findings": [{"symbol": "XAUUSD", "axis": "ecb:eur_usd_ref", "corr": 0.5,
                             "n": 499, "p_bonf": 0.0},
                            {"symbol": "Apple", "axis": "ecb:eur_usd_ref", "corr": 0.5,
                             "n": 499, "p_bonf": 0.0},
                            {"symbol": "GBPUSD", "axis": "bis:credit", "corr": 0.95, "n": 499,
                             "p_bonf": 0.0}]},
        "Q4": {"findings": [{"symbol": "USDJPY", "session": "asia", "measure": "close_to_open",
                             "mean_bp": -17.3, "t": -20.5, "n_days": 178, "p_bonf": 0.0,
                             "survives_deflation": True}]},
        "Q5": {"findings": [{"symbol": "XAUUSD", "sleeve": "gold_asia", "mean_r": -0.4}]},
        "Q6": {"findings": [{"kind": "fixing", "family": "fx_fixing_reversal", "registered": True,
                             "covered": False, "events": 746, "events_per_quarter": 130.0,
                             "forced_actor": "importers settling at the TTM rate",
                             "symbols": ["AUDJPY"]}]}}})
    _write(tmp_path / "factor_residual.json", {"generated_at": "2026-09-16T00:00:00+00:00",
        "all": [
            {"cell": "EURUSD.triangle", "target": "EURUSD", "driver_set": "triangle",
             "drivers": ["USDCHF", "NAS100"], "horizon_bars": 8, "entry_z": 3.0,
             "side_mode": "revert", "n_independent": 549, "gross_per_trade": 0.0027,
             "t_gross": 18.3, "clears_cost": True, "proposed": True},
            {"cell": "USDJPY.market_beta", "target": "USDJPY", "driver_set": "market_beta",
             "drivers": ["NAS100"], "n_independent": 400, "gross_per_trade": 0.0011,
             "t_gross": 9.0, "clears_cost": True, "proposed": True},
            {"cell": "Apple.market_beta", "target": "Apple", "driver_set": "market_beta",
             "drivers": ["NAS100"], "n_independent": 214, "gross_per_trade": 0.0025,
             "t_gross": 14.0, "clears_cost": True, "proposed": True},
            {"cell": "AUDUSD.triangle", "target": "AUDUSD", "driver_set": "triangle",
             "drivers": ["USDCHF", "NAS100"], "n_independent": 300, "gross_per_trade": 0.0009,
             "t_gross": 7.0, "not_proposed_why": "cost basis is not trustworthy"}]})
    _write(tmp_path / "unknown_unknowns_queue.jsonl", [
        {"queued_at": "2026-09-16T00:00:00+00:00", "kind": "unexplained_move", "symbol": "XAUUSD",
         "at": "2026-09-10T03:00:00+00:00", "return": 0.021, "sigma": 6.1, "question": "what?"},
        {"kind": "decoupling", "symbol": "AUDUSD|NZDUSD", "recent_corr": -0.2,
         "historical_corr": 0.7, "delta": -0.9, "question": "what changed?"},
        {"kind": "dispersion_break", "symbol": "USDJPY", "recent_vol": 0.004, "band_vol": 0.001,
         "multiple": 4.0, "question": "which regime?"},
        {"kind": "cost_shock", "symbol": "EURUSD", "at": "2026-09-11T22:00:00+00:00",
         "multiple": 6.0, "question": "why is this hour six times its own median spread?"},
        {"kind": "not_a_kind_this_organ_knows", "symbol": "EURUSD"}])
    _write(tmp_path / "COUNTERFACTUAL_WORLD.json", {
        "top_decisions": [{"row_id": "a1", "symbol": "XAUUSD", "sleeve": "gold_asia",
                           "chosen": "skip", "best_class": "MISSED_TRADE_ALPHA",
                           "best_arm": "entered", "best_d_elog": -0.0038,
                           "abs_d_elog_max": 0.0038}],
        "headline_by_class": {"VETO_ALPHA": {"alpha": None, "n": 2, "status": "UNMEASURED"},
                              "EXIT_ALPHA": {"alpha": 0.02, "n": 40, "status": "MEASURED",
                                             "reads": "exits left 2 bp on the table"}}})
    _write(tmp_path / "OPPORTUNITY_GAP.json", {"components": [
        {"cause": "SUPPLY", "measured": 21391.0, "binding": False, "why": "deep docket",
         "status": "MEASURED"},
        {"cause": "EXECUTION", "measured": 0, "binding": True, "why": "markout needs fills",
         "status": "UNMEASURED"},
        {"cause": "LATENCY", "measured": 60, "binding": True, "why": "60 of 60 miners",
         "status": "MEASURED"}]})
    _write(tmp_path / "missed_growth.jsonl", [{"day": "2026-09-04", "rail": "ruin_guard",
                                               "value": 0.35, "at": "2026-09-04T21:47:12+00:00"}])
    _write(tmp_path / "FILL_ATTRIBUTION.json", {
        "why_rejected": {"by_code": {"10016 Invalid stops": 18}},
        "why_unfilled": {"count": 37, "cause": "the stop was never reached", "is_defect": False}})
    _write(tmp_path / "execution_quality.json", {"by_symbol_session": {
        "EURUSD.discovered_asia": {"fills": 27, "slippage_R": {"n": 27, "mean": 0.12},
                                   "markouts_R": {"m1": {"n": 0}, "m5": {"n": 0}}}}})
    _write(tmp_path / "live_ledger.jsonl", [
        {"time": "2026-09-07T17:04:15+00:00", "sleeve": "[sl 4443.90]", "symbol": "XAUUSD",
         "r_multiple": -1.0},
        {"time": "2026-09-07T18:04:15+00:00", "sleeve": "eurusd_disc_asia_p_ab",
         "symbol": "EURUSD", "r_multiple": -0.5},
        {"time": "2026-09-07T19:04:15+00:00", "sleeve": "eurusd_disc_asia_p_ab",
         "symbol": "EURUSD", "r_multiple": -0.1},
        {"time": "2026-09-07T20:04:15+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
         "r_multiple": -0.2}])
    _write(tmp_path / "POSTERIOR_ALPHA.json", {"sleeves": [
        {"name": "eurusd_disc_asia_p_abcdef01", "symbol": "EURUSD", "mu_mean": 0.5, "n": 21},
        # `gold_asia` prefixes BOTH of these, so its shortfall is unattributable and is dropped.
        {"name": "gold_asia_v2", "symbol": "XAUUSD", "mu_mean": 0.4},
        {"name": "gold_asia_v3", "symbol": "XAUUSD", "mu_mean": 0.3}]})

    for name, fname in (("STANDING", "STANDING_QUESTIONS.json"),
                        ("FACTOR", "factor_residual.json"),
                        ("UNKNOWN", "unknown_unknowns_queue.jsonl"),
                        ("COUNTERFACTUAL", "COUNTERFACTUAL_WORLD.json"),
                        ("GAP", "OPPORTUNITY_GAP.json"), ("MISSED", "missed_growth.jsonl"),
                        ("FILLS", "FILL_ATTRIBUTION.json"),
                        ("EXECQ", "execution_quality.json"), ("LEDGER", "live_ledger.jsonl"),
                        ("POSTERIOR", "POSTERIOR_ALPHA.json"),
                        ("QUEUE", "residual_queue.jsonl"), ("REPORT", "RESIDUAL_QUEUE.json")):
        monkeypatch.setattr(rq, name, tmp_path / fname)
    # THE INTAKE IS NEVER REACHED FROM A TEST. The default seam returns None -- the same thing
    # `proposer_common.donate` returns when every row was refused at the door -- so no test
    # writes into the desk's real discovery contract or its pre-registration ledger. Tests that
    # are ABOUT donating re-patch this with a recorder of their own.
    monkeypatch.setattr(rq, "_donate", lambda cands, tests: None)
    yield tmp_path
    up._registry.cache_clear()


def _by_key(rows, key):
    return next((r for r in rows if r["key"] == key), None)


# --------------------------------------------------------------------------------- the join
def test_every_producer_is_joined_and_an_absent_one_is_a_verdict(desk):
    built = rq.build()
    src = built["report"]["sources"]
    assert set(src) == {"standing_questions", "factor_residual", "unknown_unknowns",
                        "counterfactual_world", "opportunity_gap", "missed_growth",
                        "fill_attribution", "execution_quality", "live_ledger",
                        "posterior_alpha"}
    for name, block in src.items():
        assert block["status"] == "present", name
        assert block["n"] > 0, name

    (desk / "factor_residual.json").unlink()
    (desk / "unknown_unknowns_queue.jsonl").unlink()
    again = rq.build()["report"]["sources"]
    assert again["factor_residual"] == {"status": "absent", "n": 0,
                                        "path": str(desk / "factor_residual.json")}
    assert again["unknown_unknowns"]["status"] == "absent"
    assert again["standing_questions"]["n"] > 0        # an absent source is not a dark organ


def test_the_unknown_unknowns_queue_is_consumed_at_four_levels(desk):
    rows = rq.build()["rows"]
    move = _by_key(rows, "move:2026-09-10T03:00:00+00:00")
    assert move["level"] == "returns" and move["symbol"] == "XAUUSD"
    assert move["magnitude"] == pytest.approx(210.0)            # 0.021 -> bp
    # THE PRODUCER'S OWN CAVEAT: with no readable event ledger "unexplained" is by construction,
    # so the move's share is UNMEASURED rather than a confident 1.0.
    assert move["unexplained_measured"] is False
    assert move["unexplained_fraction"] == rq.UNMEASURED_SHARE
    assert move["family"] == "cross_asset_residual"

    dec = _by_key(rows, "decoupled:AUDUSD|NZDUSD")
    assert (dec["level"], dec["symbol"], dec["family"]) == ("correlation", "AUDUSD",
                                                            "relative_value")
    assert dec["params"] == {"peer_symbol": "NZDUSD"}
    assert _by_key(rows, "vol_regime_break")["level"] == "volatility"
    assert _by_key(rows, "vol_regime_break")["family"] == "vol_transition"
    assert _by_key(rows, "cost_shock:2026-09-11T22:00:00+00:00")["level"] == "spread"
    # A kind this organ has no level for is DROPPED, not filed under a guess.
    assert not [r for r in rows if r["source"] == "unknown_unknowns"
                and r["level"] not in ("returns", "correlation", "volatility", "spread")]


def test_each_producer_reaches_its_own_level_with_its_own_unit(desk):
    rows = rq.build()["rows"]
    assert _by_key(rows, "precursor:clock_hour_01")["level"] == "volatility"
    assert _by_key(rows, "drift:asia:close_to_open")["magnitude_unit"] == "bp"
    assert _by_key(rows, "gap:EXECUTION")["level"] == "slippage"
    assert _by_key(rows, "gap:SUPPLY") is None                  # not binding, not queued
    assert _by_key(rows, "rail:ruin_guard")["magnitude"] == pytest.approx(0.35)
    assert _by_key(rows, "reject:10016 Invalid stops")["magnitude"] == 18.0
    assert _by_key(rows, "unfilled:the stop was never reached")["level"] == "slippage"
    assert _by_key(rows, "slippage:discovered_asia")["unexplained_fraction"] == 1.0  # no markout
    assert _by_key(rows, "counterfactual:MISSED_TRADE_ALPHA:gold_asia")["level"] == "strategy_loss"
    assert _by_key(rows, "counterfactual_class:EXIT_ALPHA")["magnitude"] == pytest.approx(0.02)
    assert _by_key(rows, "counterfactual_class:VETO_ALPHA") is None      # alpha is null
    assert _by_key(rows, "forced_flow:fixing")["family"] == "fx_fixing_reversal"


def test_a_sleeve_below_its_posterior_is_a_strategy_loss_and_an_ambiguous_one_is_not(desk):
    rows = rq.build()["rows"]
    short = _by_key(rows, "sleeve_shortfall:eurusd_disc_asia_p_ab")
    assert short["level"] == "strategy_loss" and short["symbol"] == "EURUSD"
    assert short["magnitude"] == pytest.approx(0.8)      # 0.5 posterior - (-0.3) realised
    assert short["unexplained_fraction"] == 1.0
    # `gold_asia` prefixes two posterior sleeves: unattributable, so nothing is claimed about it.
    assert _by_key(rows, "sleeve_shortfall:gold_asia") is None
    # A broker bracket comment is not a sleeve and never becomes one.
    assert not [r for r in rows if r["key"].startswith("sleeve_shortfall:[")]


# ------------------------------------------------------------------------------ the queue
def test_ids_are_stable_and_two_passes_merge_rather_than_duplicate(desk):
    first = rq.build()["rows"]
    rq.main(["--max-donations", "0"])
    second = rq.build()["rows"]
    assert len(first) == len(second)
    assert {r["residual_id"] for r in first} == {r["residual_id"] for r in second}
    assert rq.residual_id("returns", "eurusd", "k") == rq.residual_id("returns", "EURUSD", "k")
    assert rq.residual_id("returns", "EURUSD", "k") != rq.residual_id("volatility", "EURUSD", "k")


def test_recurrence_increments_across_runs_and_first_seen_does_not_move(desk):
    rq.main(["--max-donations", "0"])
    one = {r["residual_id"]: r for r in rq._read_rows(desk / "residual_queue.jsonl")}
    assert one and all(r["recurrence"] == 1 for r in one.values())
    rq.main(["--max-donations", "0"])
    two = {r["residual_id"]: r for r in rq._read_rows(desk / "residual_queue.jsonl")}
    assert set(one) == set(two)
    assert all(r["recurrence"] == 2 for r in two.values())
    for rid, row in two.items():
        assert row["first_seen"] == one[rid]["first_seen"]
        assert row["last_seen"] >= one[rid]["last_seen"]


def test_priority_is_the_rule_and_the_queue_is_sorted_by_it(desk):
    rows = rq.build()["rows"]
    for row in rows:
        assert row["priority"] == pytest.approx(
            row["magnitude"] * row["recurrence"] * row["unexplained_fraction"], abs=1e-6)
    assert [r["priority"] for r in rows] == sorted((r["priority"] for r in rows), reverse=True)
    # Recurrence really moves the order: the same magnitude seen twice outranks it seen once.
    now = datetime.now(tz=UTC)
    a = rq.item("returns", "EURUSD", "a", 10.0, "bp", 1.0, "t", "why")
    b = rq.item("returns", "EURUSD", "b", 12.0, "bp", 1.0, "t", "why")
    once = rq.merge([], [a, b], now)
    twice = rq.merge(once, [a], now)
    assert [r["key"] for r in once] == ["b", "a"]
    assert [r["key"] for r in twice] == ["a", "b"]


def test_a_producer_that_explains_an_item_retires_it_and_an_unseen_one_goes_stale(desk):
    rows = {r["key"]: r for r in rq.build()["rows"]}
    # corr 0.95 -> 1 - r^2 = 0.0975, below the 0.2 bar: the axis explains it, it leaves the front.
    assert rows["axis:bis:credit"]["status"] == "EXPLAINED"
    assert rows["axis:ecb:eur_usd_ref"]["status"] == "OPEN"

    # The SAME item, explained by a later pass of the same producer, transitions.
    doc = json.loads((desk / "STANDING_QUESTIONS.json").read_text("utf-8"))
    doc["questions"]["Q3"]["findings"][0]["corr"] = 0.99
    _write(desk / "STANDING_QUESTIONS.json", doc)
    after = {r["residual_id"]: r for r in rq.build()["rows"]}
    assert after[rows["axis:ecb:eur_usd_ref"]["residual_id"]]["status"] == "EXPLAINED"

    old = dict(rows["rail:ruin_guard"])
    old["last_seen"] = (datetime.now(tz=UTC) - timedelta(days=rq.STALE_DAYS + 1)).isoformat()
    merged = {r["residual_id"]: r for r in rq.merge([old], [], datetime.now(tz=UTC))}
    assert merged[old["residual_id"]]["status"] == "STALE"
    # Still in the record: STALE is a verdict about attention, not a deletion.
    assert merged[old["residual_id"]]["magnitude"] == old["magnitude"]


# --------------------------------------------------------------------------- what leaves
def test_donations_carry_only_registered_families_and_never_a_single_name_equity(desk,
                                                                                monkeypatch):
    rows = rq.build()["rows"]
    assert any(r["symbol"] == "Apple" for r in rows), "the equity's residual is real and queued"

    monkeypatch.setattr(rq, "registered_families",
                        lambda: {"cross_asset_residual", "overnight_drift", "vol_transition"})
    cands, refused = rq.donation_candidates(rows, 50)
    assert cands, "the queue proposed nothing at all"
    assert {c["family"] for c in cands} <= {"cross_asset_residual", "overnight_drift",
                                            "vol_transition"}
    assert not [c for c in cands if c["symbol"] == "Apple"]
    assert not [c for c in cands if c["symbol"] == ""]
    whys = " ".join(r["why"] for r in refused)
    assert "two-lane mandate" in whys and "not in the family registry" in whys
    assert "no registered family expresses this level" in whys
    assert any(r.get("symbol") == "Apple" for r in refused)
    assert any(r.get("family") == "lead_lag" for r in refused)      # real, but not in this set
    # A slippage row has no family anywhere and stays a research task.
    slip = [r for r in rows if r["level"] == "slippage"]
    assert slip and all(r["family"] is None for r in slip)


def test_a_candidate_is_an_exact_recipe_the_intake_can_read(desk, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(rq, "_donate",
                        lambda cands, tests: seen.update(cands=cands, tests=tests) or desk / "d")
    built = rq.build(3)
    assert len(seen["cands"]) == 3 and seen["tests"] > 0
    for c in seen["cands"]:
        assert c["source"] == "residual_queue" and c["kind"] == "hypothesis"
        assert c["family"] in rq.registered_families()
        assert isinstance(c["params"], dict) and c["symbols"] == [c["symbol"]]
        assert rq.may_hypothesise(c["symbol"])
        assert c["evidence"]["priority"] > 0 and c["evidence"]["screen"] == rq.RULE
    donated = [r for r in built["rows"] if r["status"] == "DONATED"]
    assert len(donated) == 3 and all(r["donated_at"] for r in donated)
    assert built["report"]["n_donated"] == 3
    # A cell the PRODUCER refused stays queued -- the residual is real -- and carries no family,
    # so it can never be handed back to the intake that already declined it.
    audusd = next(r for r in built["rows"]
                  if r["symbol"] == "AUDUSD" and r["key"] == "driver_set:triangle")
    assert audusd["family"] is None and audusd["magnitude"] > 0
    assert not [c for c in seen["cands"] if c["symbol"] == "AUDUSD"]


def test_max_donations_bounds_what_leaves_and_zero_donates_nothing(desk, monkeypatch):
    calls: list = []
    monkeypatch.setattr(rq, "_donate", lambda cands, tests: calls.append(cands) or desk / "d")
    rq.build(2)
    assert len(calls[0]) == 2
    calls.clear()
    assert rq.build(0)["report"]["n_donated"] == 0
    assert not calls


# ------------------------------------------------------------------------------------ CLI
def test_cli_dry_run_writes_nothing_and_a_real_run_writes_both_artifacts(desk, capsys):
    assert rq.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert not (desk / "residual_queue.jsonl").exists()
    assert not (desk / "RESIDUAL_QUEUE.json").exists()
    assert len(out.strip().splitlines()) == 8
    assert "nothing written, nothing donated" in out

    assert rq.main([]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 8
    rows = rq._read_rows(desk / "residual_queue.jsonl")
    report = json.loads((desk / "RESIDUAL_QUEUE.json").read_text("utf-8"))
    assert rows and len(rows) == report["n_items"]
    assert report["rule"] == rq.RULE
    assert report["n_open"] + report["n_donated"] + report["n_explained"] \
        + report["n_stale"] == report["n_items"]
    assert len(report["top"]) == min(30, report["n_items"])
    assert set(report["by_level"]) == set(rq.LEVELS)
    assert report["top"][0]["priority"] >= report["top"][-1]["priority"]
    assert all(set(r) >= {"residual_id", "level", "symbol", "asset_class", "key", "magnitude",
                          "recurrence", "unexplained_fraction", "priority", "first_seen",
                          "last_seen", "source", "status"} for r in rows)
