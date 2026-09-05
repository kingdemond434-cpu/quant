"""Per-sleeve edge hazard: P(this edge breaks next horizon | history), and what it stands on.

    "Monitoring loop: prediction decay, PnL decay, state decay, cost drift, fill drift, factor
     drift, feature drift, relationship drift; hazard_i(t) = P(edge breaks next horizon |
     history); allocation changes BEFORE the formal retirement threshold."   -- the principal

The drift monitor measured bars and correlation; nothing on the desk asked whether a SLEEVE's
edge was breaking, and `libs/research/crowding_hazard.py` -- the one leading decay indicator the
desk owns -- had no importer at all. These pin the organ that closes that:

  * the hazard RISES as forward expectancy falls below the expectancy the certificate claimed,
    and is flat at zero when the sleeve is delivering what it promised;
  * every one of the nine channels reads its own ledger and reports n; a channel with no ledger
    is named UNMEASURED and does NOT average in as a calming zero (L1.28a);
  * a sleeve where every channel is absent gets no hazard at all, not 0.0;
  * `crowding_hazard.hazard` is actually called, and its probability joins the average through
    the same declared scale it was built with, so the crowding channel does not silently change
    weight when the horizon moves;
  * the verdict lines are probabilities, and the report NAMES -- it retires nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import drift_monitor as dm  # noqa: E402

from libs.research import crowding_hazard as ch  # noqa: E402
from libs.research import perishability as ph  # noqa: E402

N = ph.HAZARD_MIN_N
#: Two quiet SLEEVE-scoped channels to sit beside the one under test, so a case clears the
#: min-channels floor and every movement in the hazard belongs to the channel being varied.
QUIET = [ph.Pressure("pnl_decay", 0.0, 50), ph.Pressure("fill_drift", 0.0, 50)]


def _write(tmp_path: Path, name: str, doc: Any) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _trades(sleeve: str, rs: list[float]) -> list[SimpleNamespace]:
    return [SimpleNamespace(sleeve=sleeve, when=f"2026-08-{1 + i // 24:02d}T{i % 24:02d}:00:00Z",
                            r=r) for i, r in enumerate(rs)]


# ============================================================ the combination rule (pure)
def test_the_hazard_rises_as_forward_expectancy_falls_below_the_certified_one() -> None:
    """The principal's first channel. Same n, same claim, falling delivery -- the number must
    move monotonically, or it is not measuring decay."""
    claim = 0.40
    hazards = []
    for forward in (0.40, 0.30, 0.20, 0.10, 0.0, -0.10):
        p = ph.decay_pressure("prediction_decay", forward, claim, 50)
        assert p.value is not None and p.n == 50
        hazards.append(ph.edge_hazard([p, *QUIET])["hazard"])
    assert hazards == sorted(hazards), f"hazard did not rise as delivery fell: {hazards}"
    assert hazards[0] == 0.0, "an edge delivering its full claim carries no decay pressure"
    assert hazards[-1] > hazards[0]


def test_delivering_more_than_the_claim_is_zero_pressure_and_never_negative() -> None:
    """A sleeve beating its certificate is not evidence the book is safe, and letting it
    subtract would let one strong sleeve mask a book that is breaking."""
    p = ph.decay_pressure("prediction_decay", 4.0, 0.4, 50)
    assert p.value == 0.0 and "at or above" in p.why


def test_a_thin_sample_is_unmeasured_with_its_count_rather_than_a_zero_pressure() -> None:
    p = ph.decay_pressure("prediction_decay", 0.0, 0.4, N - 1)
    assert p.value is None and str(N) in p.why and p.n == N - 1


def test_an_unmeasured_channel_is_not_averaged_in_as_zero() -> None:
    """The whole reason `value` is `float | None`. One full-pressure channel beside eight
    absences must read as that channel, not as one ninth of it."""
    three = [ph.Pressure("prediction_decay", 1.0, 50), *QUIET]
    alone = ph.edge_hazard(three)
    with_absences = ph.edge_hazard(
        three + [ph.unmeasured_pressure(c, "no ledger") for c in ph.HAZARD_COMPONENTS
                 if c not in {p.name for p in three}])
    assert alone["hazard"] == with_absences["hazard"] > 0.0
    assert with_absences["n_measured"] == 3
    assert len(with_absences["unmeasured"]) == len(ph.HAZARD_COMPONENTS) - 3


def test_a_sleeve_with_no_measured_channel_gets_no_hazard_at_all() -> None:
    out = ph.edge_hazard([ph.unmeasured_pressure(c, "no ledger") for c in ph.HAZARD_COMPONENTS])
    assert out["hazard"] is None
    assert out["verdict"] == ph.UNMEASURED
    assert out["mean_pressure"] is None
    assert "absences" in out["why"]


def test_the_verdict_lines_are_probabilities_and_the_leading_channel_is_named() -> None:
    def _at(p: float) -> dict[str, Any]:
        return ph.edge_hazard([ph.Pressure("cost_drift", p, 50), *QUIET])

    low, mid, high = _at(0.05), _at(0.90), _at(3.0)
    assert low["verdict"] == ph.HOLDING
    assert mid["verdict"] == ph.AT_RISK and mid["leading_channel"] == "cost_drift"
    assert high["verdict"] == ph.BREAKING
    assert low["hazard"] < mid["hazard"] < high["hazard"]
    assert high["lines"]["at_risk"] == ph.HAZARD_AT_RISK


def test_one_channel_is_a_symptom_and_not_a_hazard(monkeypatch) -> None:
    """Measured on the desk's own tree: the only readable channel off-box was `state_decay`, and
    averaging it alone put 23 sleeves at BREAKING. This number moves capital."""
    out = ph.edge_hazard([ph.Pressure("prediction_decay", 1.0, 50),
                          ph.unmeasured_pressure("pnl_decay", "no ledger")])
    assert out["hazard"] is None and out["verdict"] == ph.UNMEASURED
    assert out["n_measured"] == 1 and str(ph.HAZARD_MIN_CHANNELS) in out["why"]
    assert out["components"]["prediction_decay"]["pressure"] == 1.0, (
        "the pressures are still reported: the refusal is of the COMBINATION, not the evidence")


def test_a_hazard_built_only_from_book_channels_is_a_statement_about_the_book() -> None:
    """State, factor and relationship drift are identical for every sleeve. Three of them are
    three copies of one fact, not three independent symptoms of this edge decaying."""
    book = [ph.book_scope(ph.Pressure(c, 1.0, 500)) for c in
            ("state_decay", "factor_drift", "relationship_drift")]
    out = ph.edge_hazard(book)
    assert out["hazard"] is None and out["verdict"] == ph.UNMEASURED
    assert out["n_measured"] == 3 and out["n_sleeve_channels"] == 0
    assert "about the book" in out["why"]
    with_own = ph.edge_hazard([*book, ph.Pressure("pnl_decay", 0.0, 50)])
    assert with_own["hazard"] is not None and with_own["n_sleeve_channels"] == 1


def test_the_crowding_probability_joins_the_average_through_its_own_declared_scale() -> None:
    """`crowding_hazard.hazard` returns P(competed away), not a pressure. Inverting it through
    the same 120-day scale recovers the microstructure pressure it was built from EXACTLY --
    which is the only way the channel weighs what the other eight do."""
    state = ch.CrowdingState("S", observations=ch.MIN_OBSERVATIONS, spread_ratio=0.4,
                             fill_rate_ratio=0.5, impact_ratio=1.6)
    p, _ = ch.hazard(state, horizon_days=ph.HAZARD_HORIZON_DAYS)
    micro, _parts, _ = ch.microstructure_pressure(state)
    assert p is not None and micro is not None
    assert ph.pressure_from_hazard(p) == pytest.approx(micro, abs=1e-9)
    assert ph.hazard_probability(micro) == pytest.approx(p, abs=1e-12)


def test_the_scale_is_the_one_crowding_hazard_already_declares() -> None:
    """Two decay scales on one desk would let two organs disagree about the same edge and both
    be defensible. `crowding_hazard.hazard` uses rate = pressure / 120 per day."""
    assert ph.HAZARD_SCALE_DAYS == 120.0
    full = ch.CrowdingState("S", observations=ch.MIN_OBSERVATIONS, spread_ratio=0.0,
                            basis_ratio=0.0, funding_ratio=0.0, queue_length_ratio=2.0,
                            impact_ratio=2.0, fill_rate_ratio=0.0)
    p, _ = ch.hazard(full, horizon_days=ph.HAZARD_HORIZON_DAYS)
    assert p == pytest.approx(ph.hazard_probability(1.0), abs=1e-12)


# ============================================================ the channels (desk ledgers)
def test_prediction_decay_joins_the_certificate_to_the_shadow_ledger_name(
        tmp_path: Path) -> None:
    """The canon names cells; the shadow ledgers name `<sym>_<family>_<window>`, with the
    founding family flattened to `<sym>_<window>`. Both joins must land."""
    canon = _write(tmp_path, "canon.json", {"survivors": {
        "a": {"gates": {"expected_value": {"ev": 0.40}},
              "shadow_spec": {"symbol": "EURUSD", "family": "dav_range_filter_adx",
                              "selector": "afternoon"}},
        "b": {"gates": {"expected_value": {"ev": 0.20}},
              "shadow_spec": {"symbol": "EURUSD", "family": "dav_range_filter_adx",
                              "selector": "afternoon"}},
        "c": {"gates": {"expected_value": {"ev": 0.55}},
              "shadow_spec": {"symbol": "XAUUSD", "family": dm.FLAT_LEDGER_FAMILY,
                              "selector": "asia"}}}})
    claims = dm.certified_expectancy(canon)
    assert claims == {"EURUSD_dav_range_filter_adx_afternoon": pytest.approx(0.30),
                      "XAUUSD_asia": pytest.approx(0.55)}
    decayed = dm.prediction_decay("XAUUSD_asia", [0.11] * 40, claims)
    assert decayed.value == pytest.approx(0.8, abs=1e-9) and decayed.n == 40
    healthy = dm.prediction_decay("XAUUSD_asia", [0.60] * 40, claims)
    assert healthy.value == 0.0
    orphan = dm.prediction_decay("GBPUSD_london", [0.1] * 40, claims)
    assert orphan.value is None and "certificate" in orphan.why


def test_pnl_decay_compares_the_recent_half_with_the_sleeves_own_earlier_half() -> None:
    fading = dm.pnl_decay([1.0] * 20 + [0.25] * 20)
    assert fading.value == pytest.approx(0.75) and fading.n == 20
    steady = dm.pnl_decay([0.5] * 40)
    assert steady.value == 0.0
    thin = dm.pnl_decay([1.0] * (dm.MIN_SLEEVE_TRADES - 1))
    assert thin.value is None and str(dm.MIN_SLEEVE_TRADES) in thin.why


def test_state_decay_weights_the_admission_verdicts_by_their_test_trades(
        tmp_path: Path) -> None:
    p = dm.state_decay(_write(tmp_path, "adm.json", {"verdicts": {
        "session": {"verdict": "ADMIT", "mse_gain": 0.31, "n_test": 300},
        "event": {"verdict": "GRAVEYARD", "mse_gain": -0.22, "n_test": 100},
        "weekday": {"verdict": "RETAIN_SHRUNK", "mse_gain": -0.02, "n_test": 100}}}))
    assert p.value == pytest.approx(200 / 500) and p.n == 500
    assert p.detail["dimensions"]["event"]["decayed"] is True
    assert p.detail["dimensions"]["session"]["decayed"] is False


def test_an_unjudged_dimension_is_set_aside_rather_than_counted_either_way(
        tmp_path: Path) -> None:
    """The gauntlet could not judge it (one bucket ever reached the training floor). Counting it
    as healthy or as decayed would put an absence of evidence into a pressure."""
    p = dm.state_decay(_write(tmp_path, "adm.json", {"verdicts": {
        "event": {"verdict": "UNJUDGED", "mse_gain": 0.0, "n_test": 9000,
                  "why": "only 1 bucket ever had 15 training trades"},
        "session": {"verdict": "ADMIT", "mse_gain": 0.31, "n_test": 300}}}))
    assert p.value == 0.0 and p.n == 300, "the unjudged dimension's 9000 trades must not vote"
    assert p.detail["unjudged"] == ["event"]
    empty = dm.state_decay(_write(tmp_path, "adm2.json", {"verdicts": {
        "event": {"verdict": "UNJUDGED", "mse_gain": 0.0, "n_test": 9000}}}))
    assert empty.value is None and "UNJUDGED" in empty.why


def test_state_decay_without_the_admission_report_is_unmeasured(tmp_path: Path) -> None:
    p = dm.state_decay(tmp_path / "absent.json")
    assert p.value is None and "absent" in p.why


def test_cost_and_fill_drift_read_the_execution_twins_realised_against_modelled(
        tmp_path: Path) -> None:
    twin = dm.twin_symbols(_write(tmp_path, "twin.json", {"recalibration": {"symbols": {
        "EURUSD": {"slip": {"n": 200, "modelled_frac": 0.00005, "realised_frac": 0.000075,
                            "verdict": "SIM_TOO_OPTIMISTIC"},
                   "fill": {"n": 200, "predicted_mean": 1.0, "realised_rate": 0.7,
                            "verdict": "SIM_TOO_OPTIMISTIC"}},
        "XAUUSD": {"slip": {"n": 3, "modelled_frac": 0.0001, "realised_frac": 0.0009},
                   "fill": {"n": 3, "predicted_mean": 1.0, "realised_rate": 0.2}}}}}))
    cost = dm.cost_drift("EURUSD", twin)
    assert cost.value == pytest.approx(0.5), "slip up 50% is halfway to 'costs doubled'"
    assert cost.detail["twin_verdict"] == "SIM_TOO_OPTIMISTIC"
    fill = dm.fill_drift("EURUSD", twin)
    assert fill.value == pytest.approx(0.3), "30% of the fills are gone"
    assert dm.cost_drift("XAUUSD", twin).value is None, "3 cases is not a cost drift"
    assert dm.cost_drift("GBPUSD", twin).value is None
    assert "EXECUTION_TWIN" in dm.cost_drift("GBPUSD", twin).why


def test_relationship_drift_is_the_driver_graphs_own_sign_stability(tmp_path: Path) -> None:
    stable = dm.relationship_drift(_write(tmp_path, "cag.json", {
        "edges": [{"driver": "XAUUSD", "target": "EURUSD", "stability": 1.0} for _ in range(12)]}))
    assert stable.value == 0.0 and stable.n == 12
    coin = dm.relationship_drift(_write(tmp_path, "cag2.json", {
        "edges": [{"stability": 0.5} for _ in range(12)]}))
    assert coin.value == pytest.approx(1.0), (
        "a relationship that agrees with itself half the time has no sign left to decay")
    thin = dm.relationship_drift(_write(tmp_path, "cag3.json", {"edges": [{"stability": 0.5}]}))
    assert thin.value is None
    assert dm.relationship_drift(tmp_path / "absent.json").value is None


def test_feature_and_factor_drift_reuse_this_passes_own_z_and_its_own_lines() -> None:
    per_symbol = {"EURUSD": {"hazard_max": 0.5, "n_windows": 700, "per_stat": {"vol": {}}},
                  "XAUUSD": {"hazard_max": 3.0, "n_windows": 700, "per_stat": {"vol": {}}}}
    assert dm.feature_drift("EURUSD", per_symbol).value == 0.0, "inside the WATCH line"
    assert dm.feature_drift("XAUUSD", per_symbol).value == pytest.approx(1.0)
    assert dm.feature_drift("GBPUSD", per_symbol).value is None
    assert dm.factor_drift({"z": 2.0, "n_days": 90}).value == pytest.approx(0.5)
    absent = dm.factor_drift({"z": None, "why": "need 90 rows for structure drift"})
    assert absent.value is None and "90 rows" in absent.why


def test_crowding_is_unmeasured_below_its_own_observation_floor(tmp_path: Path) -> None:
    """`crowding_hazard` refuses under 60 paired observations, and this must not overrule it:
    a trend in a spread over a shorter window is noise with a direction."""
    twin = dm.twin_symbols(_write(tmp_path, "twin.json", {"recalibration": {"symbols": {
        "EURUSD": {"slip": {"n": 10, "modelled_frac": 0.0001, "realised_frac": 0.0002},
                   "fill": {"n": 10, "predicted_mean": 1.0, "realised_rate": 0.5}}}}}))
    p = dm.crowding("EURUSD", twin, {})
    assert p.value is None and str(ch.MIN_OBSERVATIONS) in p.why


def test_crowding_reads_spread_compression_and_the_twins_fills_when_it_has_the_evidence(
        tmp_path: Path) -> None:
    n = ch.MIN_OBSERVATIONS + 40
    twin = dm.twin_symbols(_write(tmp_path, "twin.json", {"recalibration": {"symbols": {
        "EURUSD": {"slip": {"n": n, "modelled_frac": 0.0001, "realised_frac": 0.00016},
                   "fill": {"n": n, "predicted_mean": 1.0, "realised_rate": 0.6}}}}}))
    per_symbol = {"EURUSD": {"per_stat": {"spread_rank": {"forecast": 0.5, "baseline": 1.0}}}}
    p = dm.crowding("EURUSD", twin, per_symbol)
    assert p.value is not None and p.value > 0.0
    assert p.detail["spread_ratio"] == pytest.approx(0.5)
    assert p.detail["fill_rate_ratio"] == pytest.approx(0.6)
    assert p.detail["impact_ratio"] == pytest.approx(1.6)
    assert p.detail["crowding_hazard"] > 0.0
    # the pressure is exactly what crowding_hazard's own probability implies at this scale
    assert p.value == pytest.approx(ph.pressure_from_hazard(p.detail["crowding_hazard"]))


# ============================================================ the report
def test_hazard_by_sleeve_names_every_channel_and_the_report_retires_nothing(
        tmp_path: Path) -> None:
    claims = {"EURUSD_london": 0.40}
    per_symbol = {"EURUSD": {"hazard_max": 2.0, "n_windows": 700,
                             "per_stat": {"spread_rank": {"forecast": 0.4, "baseline": 0.8}}}}
    twin = dm.twin_symbols(_write(tmp_path, "twin.json", {"recalibration": {"symbols": {
        "EURUSD": {"slip": {"n": 200, "modelled_frac": 0.0001, "realised_frac": 0.00015},
                   "fill": {"n": 200, "predicted_mean": 1.0, "realised_rate": 0.8}}}}}))
    shared = [ph.share_pressure("state_decay", 0.4, 500),
              dm.factor_drift({"z": 2.0, "n_days": 90}),
              ph.agreement_pressure("relationship_drift", 0.9, 12)]
    rows = dm.hazard_by_sleeve(per_symbol, {}, _trades("EURUSD_london", [0.1] * 40),
                               claims=claims, twin=twin, shared=shared)
    row = rows["EURUSD_london"]
    assert set(row["components"]) == set(ph.HAZARD_COMPONENTS)
    assert row["n_measured"] == len(ph.HAZARD_COMPONENTS), "every channel had a ledger here"
    assert row["unmeasured"] == []
    assert row["symbol"] == "EURUSD" and row["n_trades"] == 40
    assert row["components"]["prediction_decay"]["pressure"] == pytest.approx(0.75)
    assert 0.0 < row["hazard"] < 1.0 and row["verdict"] in (ph.HOLDING, ph.AT_RISK, ph.BREAKING)
    for c in row["components"].values():
        assert "n" in c and "pressure" in c


def test_a_sleeve_delivering_its_claim_carries_less_hazard_than_one_that_is_not(
        tmp_path: Path) -> None:
    """The end-to-end version of the first channel: same book, same drift, two sleeves."""
    claims = {"EURUSD_london": 0.40, "EURUSD_asia": 0.40}
    per_symbol = {"EURUSD": {"hazard_max": 1.5, "n_windows": 700, "per_stat": {}}}
    trades = _trades("EURUSD_london", [0.40] * 40) + _trades("EURUSD_asia", [0.05] * 40)
    rows = dm.hazard_by_sleeve(per_symbol, {}, trades, claims=claims, twin={},
                               shared=[ph.unmeasured_pressure(c, "not in this fixture")
                                       for c in ("state_decay", "factor_drift",
                                                 "relationship_drift")])
    assert rows["EURUSD_asia"]["hazard"] > rows["EURUSD_london"]["hazard"]
    assert rows["EURUSD_asia"]["leading_channel"] == "prediction_decay"
    assert rows["EURUSD_london"]["unmeasured"] == ["state_decay", "cost_drift", "fill_drift",
                                                   "factor_drift", "relationship_drift",
                                                   "crowding"]


def test_the_summary_names_who_is_breaking_and_on_how_much_evidence() -> None:
    def _all(p: float) -> dict[str, Any]:
        return ph.edge_hazard([ph.Pressure(c, p, 50) for c in
                               ("prediction_decay", "pnl_decay", "fill_drift")])

    rows = {"A": _all(1.0), "B": _all(0.02),
            "C": ph.edge_hazard([ph.unmeasured_pressure("pnl_decay", "no ledger")])}
    s = dm.hazard_summary(rows)
    assert s["n_sleeves"] == 3 and s["n_measured"] == 2 and s["n_unmeasured"] == 1
    assert s["breaking"] == ["A"] and s["at_risk"] == []
    assert s["max"]["sleeve"] == "A" and s["max"]["n_measured_channels"] == 3
    assert s["channels"] == list(ph.HAZARD_COMPONENTS)
    assert "NAMES" in s["rule"] and "retirement stays a separate decision" in s["rule"]


def test_an_empty_ledger_produces_an_empty_table_and_a_summary_that_says_so() -> None:
    rows = dm.hazard_by_sleeve({}, {}, [], claims={}, twin={}, shared=[])
    assert rows == {}
    s = dm.hazard_summary(rows)
    assert s["n_sleeves"] == 0 and s["max"] is None and s["breaking"] == []
