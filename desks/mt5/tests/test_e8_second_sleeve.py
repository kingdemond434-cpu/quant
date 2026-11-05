"""The E8 second-sleeve ranker (BACKLOG 26): its gates, its verdicts and its clock.

`research/e8_second_sleeve.py` ranks every candidate beside gold_asia for the E8 book. These pin
that an absent input reads UNMEASURED (never a pass), that a same-mechanism or venue-refused
candidate is named with the gate it misses, that a genuinely independent listed sleeve is ranked
eligible, that the ranker writes only its own report, and that the leg is on the hourly clock.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import e8_second_sleeve as e8s  # noqa: E402
import kelly_survival as ks  # noqa: E402


# ------------------------------------------------------------------ naming and static gates

@pytest.mark.parametrize("col,want", [
    ("gold_asia", ("XAUUSD", "session_range_breakout", "asia", "H1")),
    ("CADCHF_overnight_gap_decay_asia", ("CADCHF", "overnight_gap_decay", "asia", "H1")),
    ("USDJPY_session_range_breakout_asia", ("USDJPY", "session_range_breakout", "asia", "H1")),
    ("CADJPY_asia_FAILED_BREAK", ("CADJPY", "failed_breakout", "asia", "H1")),
    ("xau_m15_anti_breakout", ("XAUUSD", "anti_breakout", "all", "M15")),
    ("xau_m5_anti_momentum_ny", ("XAUUSD", "anti_momentum", "ny", "M5")),
])
def test_column_identity_reads_every_naming_shape(col: str, want: tuple[str, ...]) -> None:
    ident = e8s.column_identity(col)
    assert (ident["symbol"], ident["family"], ident["selector"], ident["timeframe"]) == want


def test_symbol_gate_scandi_em_documented_and_unknown() -> None:
    assert e8s.symbol_gate("GBPSEK", None)["verdict"] == e8s.FAIL
    assert e8s.symbol_gate("EURNOK", {"EURNOK"})["verdict"] == e8s.FAIL   # principal rule wins
    assert e8s.symbol_gate("USDZAR", None)["verdict"] == e8s.FAIL
    assert e8s.symbol_gate("USDTRY", None)["verdict"] == e8s.FAIL        # EM cross
    assert e8s.symbol_gate("CADCHF", None)["verdict"] == e8s.PASS
    # ABSENCE IS NOT PERMISSION: a symbol nobody measured is UNMEASURED, never PASS.
    assert e8s.symbol_gate("NZDCHF", None)["verdict"] == e8s.UNMEASURED
    # The measured catalogue, when present, decides both ways.
    assert e8s.symbol_gate("NZDCHF", {"NZDCHF"})["verdict"] == e8s.PASS
    assert e8s.symbol_gate("CADCHF", {"EURUSD"})["verdict"] == e8s.FAIL


def test_mechanism_session_and_opposite_gates() -> None:
    assert e8s.mechanism_gate("session_range_breakout")["verdict"] == e8s.FAIL
    assert e8s.mechanism_gate("overnight_gap_decay")["verdict"] == e8s.PASS
    assert e8s.mechanism_gate("")["verdict"] == e8s.UNMEASURED
    assert e8s.session_gate("M15", "asia")["verdict"] == e8s.FAIL
    assert e8s.session_gate("H1", "asia")["verdict"] == e8s.PASS
    others = e8s.other_account_symbols({"fusion": {"gold_asia": 0.01, "EURUSD_x_asia": 0.0},
                                        "ftmo": {"gold_asia": 0.009}})
    assert others == {"XAUUSD": ["fusion", "ftmo"]}
    assert e8s.opposite_gate("XAUUSD", others)["verdict"] == e8s.FENCE
    assert e8s.opposite_gate("CADCHF", others)["verdict"] == e8s.PASS


def test_policy_gate_reads_exclusions_quarantine_and_principal_zero() -> None:
    excl = {"CHFNOK_carry_asia": "carry lookahead"}
    assert e8s.policy_gate("CHFNOK_carry_asia", "CHFNOK", set(), excl)["verdict"] == e8s.FAIL
    assert e8s.policy_gate("EURUSD_x_asia", "EURUSD", {"EURUSD"}, {})["verdict"] == e8s.FAIL
    assert e8s.policy_gate("gold_london_am", "XAUUSD", set(), {})["verdict"] == e8s.FAIL
    assert e8s.policy_gate("CADCHF_overnight_gap_decay_asia", "CADCHF", set(),
                           {})["verdict"] == e8s.PASS


def test_evidence_gate_forward_decides_then_costed_backtest_then_unmeasured() -> None:
    assert e8s.evidence_gate({"n": 20, "exp_r": -0.2, "forward_t": -1.0},
                             {"exp_x3_costs": 0.3})["verdict"] == e8s.FAIL
    assert e8s.evidence_gate({"n": 4, "exp_r": -0.2}, {"exp_x3_costs": 0.3})["verdict"] == e8s.PASS
    assert e8s.evidence_gate({"n": 4, "exp_r": 0.5}, None)["verdict"] == e8s.UNMEASURED
    assert e8s.evidence_gate(None, None)["verdict"] == e8s.UNMEASURED


# ------------------------------------------------------------------ the build, on a synthetic tree

def _world(seed: int = 7, n_w: int = 24, n_t: int = 256) -> tuple[np.ndarray, np.ndarray]:
    g = np.random.default_rng(seed)
    fire = g.random((n_w, n_t)) < 0.6
    gold = np.where(fire, np.where(g.random((n_w, n_t)) < 0.42, 2.0, -1.0), 0.0)
    fire2 = g.random((n_w, n_t)) < 0.6
    indep = np.where(fire2, np.where(g.random((n_w, n_t)) < 0.45, 2.0, -1.0), 0.0)
    crisis = np.zeros(n_w, dtype=bool)
    crisis[:4] = True
    return np.stack([gold, indep], axis=2), crisis


def _tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str], r: np.ndarray,
          crisis: np.ndarray, clocks: dict | None = None) -> Path:
    worlds = tmp_path / "worlds.npz"
    np.savez(worlds, r=r.astype(np.float32), names=np.array(names), crisis=crisis,
             mu=r.mean(axis=1))
    book = tmp_path / "CERT_BOOK_LIVE.json"
    book.write_text(json.dumps({"e8": {"gold_asia": 0.006}, "fusion": {"gold_asia": 0.01}}))
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps(clocks or {}))
    monkeypatch.setattr(ks, "WORLDS", worlds)
    monkeypatch.setattr(ks, "LEDGER", tmp_path / "no_ledger.jsonl")
    monkeypatch.setattr(ks, "E8_REPORT", tmp_path / "no_e8.json")
    monkeypatch.setattr(e8s, "CERT_BOOK", book)
    monkeypatch.setattr(e8s, "E8_CATALOGUE", tmp_path / "no_catalogue.json")
    monkeypatch.setattr(e8s, "ENROLMENT", tmp_path / "no_enrolment.json")
    monkeypatch.setattr(e8s, "SURVIVORS", tmp_path / "no_survivors.json")
    monkeypatch.setattr(e8s, "CURE_ROSTER", tmp_path / "no_roster.json")
    monkeypatch.setattr(e8s, "CURE_SNAPSHOT", tmp_path / "no_snapshot.json")
    monkeypatch.setattr(e8s, "SHADOW_DIR", shadow)
    return book


def test_an_independent_listed_sleeve_with_forward_evidence_is_eligible(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _world()
    clocks = {"CADCHF.overnight_gap_decay.asia": {"n": 30, "exp_r": 0.5, "forward_t": 4.0,
                                                  "status": "ACTIVE"}}
    book = _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r,
                 crisis, clocks)
    before = book.read_text()
    doc = e8s.build(n_paths=300)
    assert doc["status"] == "OK", doc["verdict"]
    top = doc["top"][0]
    assert top["candidate"] == "CADCHF_overnight_gap_decay_asia" and top["eligible"]
    assert top["d_elog_per_day_mix"] > 0 and abs(top["rho"]) < 0.2
    assert top["mechanism_novelty"] == "NEW_MECHANISM"
    assert doc["n_independent_mechanisms_eligible"] == 1
    assert book.read_text() == before          # a ranker writes no CERT_BOOK block


def test_same_mechanism_and_correlated_are_named_none_eligible(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _world()
    twin = r[:, :, :1] * 1.0                                   # gold's own rows: rho 1
    r3 = np.concatenate([r[:, :, :1], twin, r[:, :, 1:]], axis=2)
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_carry_asia",
                                  "USDJPY_session_range_breakout_asia"], r3, crisis)
    doc = e8s.build(n_paths=200)
    assert doc["status"] == "NONE_ELIGIBLE"
    by = {c["candidate"]: c for c in doc["candidates"]}
    assert "correlation" in by["CADCHF_carry_asia"]["missing_gates"]
    assert "mechanism" in by["USDJPY_session_range_breakout_asia"]["missing_gates"]
    # no clock and no certificate anywhere: evidence is UNMEASURED, so it is a missing gate too
    assert all("evidence" in c["missing_gates"] for c in doc["candidates"])
    assert doc["verdict"].startswith("NONE_ELIGIBLE: ")


def test_unreadable_worlds_is_unmeasured_never_ok(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _world()
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r, crisis)
    monkeypatch.setattr(ks, "WORLDS", tmp_path / "missing.npz")
    doc = e8s.build(n_paths=100)
    assert doc["status"] == "UNMEASURED" and doc["measured"] is False
    assert doc["n_eligible"] == 0 and doc["top"] == []


def test_a_forward_only_candidate_misses_joint_series_by_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _world()
    clocks = {"GBPCHF.spread_state.asia#hold_bars=4": {"n": 15, "exp_r": 0.4, "forward_t": 3.0,
                                                       "status": "ACTIVE"}}
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r, crisis,
          clocks)
    doc = e8s.build(n_paths=100)
    row = next(c for c in doc["unpriced_candidates"] if c["candidate"] ==
               "GBPCHF.spread_state.asia")
    assert row["eligible"] is False and row["missing_gates"][0] == "joint_series"
    assert row["gates"]["correlation"]["verdict"] == e8s.UNMEASURED


def test_write_is_atomic_and_main_writes_the_report(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _world()
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r, crisis)
    out = tmp_path / "E8_SECOND_SLEEVE.json"
    assert e8s.main(["--paths", "100", "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["status"] in ("OK", "NONE_ELIGIBLE") and "generated_at" in doc
    assert not out.with_name(out.name + ".tmp").exists()


# ------------------------------------------------------------------ the clock and the contract

def test_the_leg_is_on_the_hourly_clock_with_a_contract() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"e8_second_sleeve", "research/e8_second_sleeve.py"' in src
    assert '"e8_second_sleeve": e8s,' in src
    import hourly_cycle as hc
    assert "e8_second_sleeve" in hc.CORE_LEGS
    assert hc.LEG_BUDGET_SEC.get("e8_second_sleeve", 0) > 0
    contracts = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text(encoding="utf-8"))["legs"]
    from libs.tiers.experiment_contract import problems
    c = dict(contracts["e8_second_sleeve"], budget={"seconds": 300}, owner="portfolio")
    assert problems(c) == []
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER.get("e8_second_sleeve") == "portfolio"


# ------------------------------------------------------------------ audit #724 SF: dependence + decay

def _negative_prior_world(seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    """gold_asia as above, beside a candidate whose PRIOR loses (25% wins at 2R = -0.25R/trade)."""
    r, crisis = _world(seed)
    g = np.random.default_rng(seed + 1)
    fire = g.random(r.shape[:2]) < 0.6
    r[:, :, 1] = np.where(fire, np.where(g.random(r.shape[:2]) < 0.25, 2.0, -1.0), 0.0)
    return r, crisis


def _costed_survivor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    surv = tmp_path / "survivors.json"
    surv.write_text(json.dumps({"survivors": {"external.CADCHF.overnight_gap_decay.p=1": {
        "sym": "CADCHF", "shadow_spec": {"symbol": "CADCHF", "family": "overnight_gap_decay",
                                         "selector": "asia"},
        "gates": {"stress_costs": {"exp_x3": 0.2}}}}}))
    monkeypatch.setattr(e8s, "SURVIVORS", surv)


def test_posterior_dependence_is_in_the_top_row_verdict_text(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _negative_prior_world()
    clocks = {"CADCHF.overnight_gap_decay.asia": {"n": 30, "exp_r": 1.0, "forward_t": 5.0,
                                                  "status": "ACTIVE"}}
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r, crisis,
          clocks)
    doc = e8s.build(n_paths=300)
    assert doc["status"] == "OK", doc["verdict"]
    top = doc["top"][0]
    assert top["posterior_dependence"] == "POSTERIOR_DEPENDENT"
    assert top["prior_only"]["d_elog_per_day"] <= 0 or top["prior_only"]["d_p_pass"] < 0
    # the verdict TEXT itself carries it, so the E8 book owner cannot read past it
    assert "POSTERIOR_DEPENDENT" in doc["verdict"] and "forward n=30" in doc["verdict"]


def test_forward_n_decaying_under_the_floor_takes_eligibility_away_by_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r, crisis = _negative_prior_world()
    key = "CADCHF.overnight_gap_decay.asia"
    _tree(tmp_path, monkeypatch, ["gold_asia", "CADCHF_overnight_gap_decay_asia"], r, crisis,
          {key: {"n": 30, "exp_r": 1.0, "forward_t": 5.0, "status": "ACTIVE"}})
    _costed_survivor(tmp_path, monkeypatch)
    first = e8s.build(n_paths=300)
    assert first["top"][0]["eligible"]
    # decay: the clock re-froze and holds only 6 forward observations now
    (e8s.SHADOW_DIR / "shadow_state.json").write_text(json.dumps(
        {key: {"n": 6, "exp_r": 1.0, "forward_t": 2.0, "status": "ACTIVE"}}))
    second = e8s.build(n_paths=300, previous=first)
    row = next(c for c in second["candidates"]
               if c["candidate"] == "CADCHF_overnight_gap_decay_asia")
    assert not row["eligible"] and "forward_depth" in row["missing_gates"]
    assert row["gates"]["evidence"]["verdict"] == e8s.PASS      # it is the depth, not the sign
    lost = second["no_longer_eligible"]
    assert [x["candidate"] for x in lost] == ["CADCHF_overnight_gap_decay_asia"]
    assert "forward_depth" in lost[0]["missing_gates"] and lost[0]["forward_n"] == 6
    assert "NO_LONGER_ELIGIBLE" in second["verdict"]


def test_forward_depth_gate_passes_when_the_prior_alone_supports_it() -> None:
    assert e8s.forward_depth_gate("PRIOR_SUPPORTS", {"n": 2})["verdict"] == e8s.PASS
    assert e8s.forward_depth_gate("POSTERIOR_DEPENDENT", {"n": 2})["verdict"] == e8s.FAIL
    assert e8s.forward_depth_gate("UNMEASURED", None)["verdict"] == e8s.FAIL
    assert e8s.posterior_dependence({"d_elog_per_day": 0.001, "d_p_pass": 0.0}) == \
        "PRIOR_SUPPORTS"
    assert e8s.posterior_dependence({"d_elog_per_day": 0.001, "d_p_pass": -0.1}) == \
        "POSTERIOR_DEPENDENT"
