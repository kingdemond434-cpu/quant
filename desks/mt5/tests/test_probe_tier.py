"""The probe tier (research/probe_tier.py): admission, measured co-move groups, SPRT demotion to
forward test, hysteresis re-admission, the outcome ledger and the self-tuner; and the doors that
read it (promoter.apply_probe_tier, prop/e8_book probe rows)."""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import research.probe_tier as pt

NOW = datetime(2026, 11, 27, 1, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _open_class(monkeypatch: pytest.MonkeyPatch) -> None:
    # The registry is the box's; here every symbol is classified unless a test says otherwise.
    monkeypatch.setattr(pt, "_class_refusal",
                        lambda s: "exotic" if s in ("USDZAR", "EURNOK") else None)
    monkeypatch.setattr(pt, "_banned", lambda f: None)


def clock(n: int, cum: float, *, t: float = 1.0, status: str = "ACTIVE", first: str = "a",
          basis: str = "fill_hour_03", tail: list | None = None, s2: float | None = None
          ) -> dict:
    row = {"n": n, "cum_r": cum, "exp_r": cum / n if n else 0.0, "forward_t": t,
           "status": status, "spread_basis": basis, "first_entry": first, "last_entry": "z"}
    if tail is not None:
        row["r_tail"] = tail
    if s2 is not None:
        row["sum_r2"] = s2
    return row


def tail(rs: list[float], start: int = 1) -> list[list]:
    return [[f"2026-10-{start + i:02d} 01:00", r] for i, r in enumerate(rs)]


# ---------------------------------------------------------------- pure pieces
def test_shrink_is_n_over_n_plus_50() -> None:
    assert pt.shrink(50) == 0.5
    assert pt.shrink(0) == 0.0
    assert math.isclose(pt.shrink(10), 10 / 60)


def test_sprt_llr_signs() -> None:
    # a row earning its expectation produces evidence FOR H0 (negative LLR), a flat one against
    assert pt.sprt_llr(20, 20 * 0.2, 0.2, 1.0) < 0
    assert pt.sprt_llr(20, 0.0, 0.2, 1.0) > 0
    assert pt.sprt_llr(0, 0.0, 0.2, 1.0) == 0.0
    a, b = pt.bounds(0.05)
    assert a == pytest.approx(math.log(0.8 / 0.05)) and b == pytest.approx(math.log(0.2 / 0.95))


def test_sigma_from_sum_of_squares_then_t_then_floor() -> None:
    assert pt.sigma_of({"n": 4, "cum_r": 0.0, "sum_r2": 4.0}) == pytest.approx(math.sqrt(4 / 3))
    assert pt.sigma_of({"n": 16, "cum_r": 8.0, "forward_t": 2.0}) == pytest.approx(1.0)
    assert pt.sigma_of({"n": 16, "cum_r": 0.1, "forward_t": 50.0}) == pt.SIGMA_FLOOR


def test_parse_key_reads_family_selector_and_chart() -> None:
    m = pt.parse_key("AUDCAD.cross_asset_residual.asia@M30#factor_symbols=['BTCUSD']")
    assert m == {"symbol": "AUDCAD", "family": "cross_asset_residual", "selector": "asia",
                 "timeframe": "M30"}
    assert pt.parse_key("GBPAUD.asia#rr=1.5")["family"] == "session_range_breakout"
    assert pt.column_of(m) == "AUDCAD_cross_asset_residual_asia"


# ---------------------------------------------------------------- admission
def test_eligibility_doors() -> None:
    m = pt.parse_key("EURCHF.carry.asia")
    ok = clock(20, 4.0)
    assert pt.eligible("k", ok, m, 0.5) is None
    assert "n=9" in pt.eligible("k", clock(9, 4.0), m, 0.5)
    assert "not positive" in pt.eligible("k", clock(20, -1.0), m, 0.5)
    assert "T_IN" in pt.eligible("k", clock(20, 4.0, t=0.2), m, 0.5)
    assert "status" in pt.eligible("k", clock(20, 4.0, status="KILL"), m, 0.5)
    assert "fill-hour" in pt.eligible("k", clock(20, 4.0, basis="pooled_median"), m, 0.5)
    assert pt.eligible("k", clock(20, 4.0), pt.parse_key("USDZAR.carry.asia"), 0.5) == "exotic"
    gold = pt.parse_key("XAUUSD.asia#rr=2.5")
    assert "gold" in pt.eligible("k", clock(44, 13.0), gold, 0.5)
    # gold on any OTHER family is an ordinary probe
    assert pt.eligible("k", clock(20, 4.0), pt.parse_key("XAUUSD.cross_asset_residual.asia"),
                       0.5) is None


def test_fill_hour_basis_needs_a_real_hour() -> None:
    assert pt._fill_hour("fill_hour") and pt._fill_hour("fill_hour_07")
    assert not pt._fill_hour("fill_hour_7") and not pt._fill_hour("fill_hour_99")
    assert not pt._fill_hour(None)


def test_admits_positive_rows_at_shrink_and_names_refusals() -> None:
    shadow = {"EURCHF.carry.asia": clock(30, 6.0, first="x"),
              "USDZAR.carry.asia": clock(30, 6.0, first="y"),
              "GBPCHF.carry.asia": clock(5, 3.0, first="w")}
    art, state, events = pt.step(shadow, {}, now=NOW)
    assert list(art["live"]) == ["EURCHF.carry.asia"]
    assert art["live"]["EURCHF.carry.asia"]["shrink"] == pytest.approx(30 / 80)
    assert state["rows"]["EURCHF.carry.asia"]["mu0"] == pytest.approx(0.5 * 0.2)
    assert [e["event"] for e in events] == ["admit"]
    assert art["missed_growth"]["EURCHF.carry.asia"]["rail"] == "probe_shrink"


def test_off_marker_lists_nothing_and_demotes_live() -> None:
    shadow = {"EURCHF.carry.asia": clock(30, 6.0)}
    _, state, _ = pt.step(shadow, {}, now=NOW)
    art, state2, events = pt.step(shadow, state, now=NOW, off=True)
    assert art["live"] == {}
    assert state2["rows"]["EURCHF.carry.asia"]["status"] == "DEMOTED"


# ---------------------------------------------------------------- co-movement
def test_identical_records_are_one_bet() -> None:
    shadow = {"A.carry.asia": clock(30, 6.0, t=1.0, first="same"),
              "A.carry.asia#x=1": clock(30, 6.0, t=1.0, first="same"),
              "B.carry.asia": clock(30, 6.0, t=1.2, first="other")}
    art, _, _ = pt.step(shadow, {}, now=NOW)
    assert len(art["live"]) == 2
    assert len(art["aliases"]) == 1


def test_measured_correlation_merges_and_low_correlation_does_not() -> None:
    base = [1.0, -1.0, 0.5, -0.5, 1.2, -0.8, 0.9, -1.1, 0.3, 0.7]
    noisy = [r * 0.9 + 0.05 for r in base]
    unrelated = [0.5, 0.5, -1.0, 1.0, -0.5, -0.5, 1.0, -1.0, 0.2, -0.2]
    rows = {"A": clock(30, 6.0, first="1", tail=tail(base)),
            "B": clock(30, 5.0, first="2", tail=tail(noisy)),
            "C": clock(30, 4.0, first="3", tail=tail(unrelated))}
    groups = pt.comove_groups(rows)
    assert sorted(map(sorted, groups)) == [["A", "B"], ["C"]]


def test_same_symbol_without_measured_comovement_is_not_merged() -> None:
    rows = {"EURCHF.carry.asia": clock(30, 6.0, first="1"),
            "EURCHF.formula.asia": clock(31, 5.0, first="2")}
    assert len(pt.comove_groups(rows)) == 2


def test_new_row_comoving_with_a_live_row_is_an_alias_of_it() -> None:
    base = [1.0, -1.0, 0.5, -0.5, 1.2, -0.8, 0.9, -1.1, 0.3, 0.7]
    s1 = {"A.carry.asia": clock(30, 6.0, t=0.9, first="1", tail=tail(base))}
    _, state, _ = pt.step(s1, {}, now=NOW)
    s2 = {**s1, "B.carry.asia": clock(30, 9.0, t=3.0, first="2", tail=tail(base))}
    art, _, _ = pt.step(s2, state, now=NOW)
    assert list(art["live"]) == ["A.carry.asia"]          # the live member stays the carrier
    assert art["aliases"] == {"B.carry.asia": "A.carry.asia"}


# ---------------------------------------------------------------- demotion and re-admission
def _admitted(n: int = 40, cum: float = 12.0) -> tuple[dict, dict]:
    shadow = {"EURCHF.carry.asia": clock(n, cum, t=2.0, s2=n * 1.0 + cum * cum / n)}
    _, state = pt.step(shadow, {}, now=NOW)[:2]
    return shadow, state


def test_losing_after_admission_demotes_to_forward_never_retires() -> None:
    shadow, state = _admitted()
    rec = state["rows"]["EURCHF.carry.asia"]
    later = {"EURCHF.carry.asia": clock(52, 12.0 - 6.0, t=1.0)}
    art, state2, events = pt.step(later, state, now=NOW + timedelta(days=5))
    assert "EURCHF.carry.asia" not in art["live"]
    d = art["demoted"]["EURCHF.carry.asia"]
    assert "losing leg" in d["why"]
    assert state2["rows"]["EURCHF.carry.asia"]["status"] == "DEMOTED"
    assert any(e["event"] == "demote" and e["statistical"] for e in events)
    assert rec["status"] == "LIVE"


def test_a_flat_row_is_demoted_by_the_sprt() -> None:
    _, state = _admitted()
    later = {"EURCHF.carry.asia": clock(40 + 300, 12.0 + 0.5, t=1.0)}
    art, _, _ = pt.step(later, state, now=NOW + timedelta(days=20))
    assert "SPRT" in art["demoted"]["EURCHF.carry.asia"]["why"]


def test_earning_after_admission_stays_live() -> None:
    _, state = _admitted()
    later = {"EURCHF.carry.asia": clock(60, 12.0 + 20 * 0.3, t=2.5)}
    art, _, events = pt.step(later, state, now=NOW + timedelta(days=5))
    assert "EURCHF.carry.asia" in art["live"]
    assert not [e for e in events if e["event"] == "demote"]


def test_clock_killed_demotes_at_once() -> None:
    _, state = _admitted()
    killed = {"EURCHF.carry.asia": clock(41, 12.5, status="KILL")}
    art, _, _ = pt.step(killed, state, now=NOW)
    assert "clock status" in art["demoted"]["EURCHF.carry.asia"]["why"]


def test_readmission_needs_its_own_evidence_since_demotion() -> None:
    _, state = _admitted()
    s = {"EURCHF.carry.asia": clock(52, 6.0, t=1.0)}
    _, state, _ = pt.step(s, state, now=NOW)                            # demoted at n=52
    # three good trades since: not enough trades to re-admit
    s = {"EURCHF.carry.asia": clock(55, 9.0, t=1.0)}
    art, state, _ = pt.step(s, state, now=NOW)
    assert "EURCHF.carry.asia" not in art["live"]
    # twelve trades since, earning well above mu0: accepted, and eligible -> LIVE again
    s = {"EURCHF.carry.asia": clock(64, 6.0 + 12 * 0.6, t=1.5)}
    art, state, events = pt.step(s, state, now=NOW)
    assert "EURCHF.carry.asia" in art["live"]
    assert any(e["event"] == "readmit" for e in events)


def test_readmission_still_needs_eligibility() -> None:
    _, state = _admitted()
    _, state, _ = pt.step({"EURCHF.carry.asia": clock(52, 6.0, t=1.0)}, state, now=NOW)
    s = {"EURCHF.carry.asia": clock(64, 6.0 + 12 * 0.6, t=0.1)}           # t under T_IN
    art, _, _ = pt.step(s, state, now=NOW)
    assert "EURCHF.carry.asia" not in art["live"]


def test_a_shorter_replay_reanchors_and_credits_nothing() -> None:
    _, state = _admitted(n=40, cum=12.0)
    art, state2, _ = pt.step({"EURCHF.carry.asia": clock(30, 2.0, t=1.0)}, state, now=NOW)
    assert "EURCHF.carry.asia" in art["live"]
    assert state2["rows"]["EURCHF.carry.asia"]["n0"] == 30


# ---------------------------------------------------------------- outcomes and the tuner
def test_demote_outcome_is_scored_after_outcome_n_trades() -> None:
    _, state = _admitted()
    _, state, _ = pt.step({"EURCHF.carry.asia": clock(52, 6.0, t=1.0)}, state, now=NOW)
    _, state, events = pt.step({"EURCHF.carry.asia": clock(62, 9.0, t=1.0)}, state, now=NOW)
    out = [e for e in events if e["event"] == "outcome"]
    assert out and out[0]["kind"] == "demote" and out[0]["false_demote"] is True
    assert out[0]["forgone_r"] == pytest.approx(3.0)
    assert state["history"][-1]["kind"] == "demote"


def test_tuner_loosens_on_false_demotes_and_tightens_on_late_ones() -> None:
    false = [{"kind": "demote", "forgone_r": 3.0, "late_r": 0.5}] * 3
    late = [{"kind": "demote", "forgone_r": -1.0, "late_r": 4.0}] * 3
    t1 = pt.tune({"alpha": 0.05}, false)
    t2 = pt.tune({"alpha": 0.05}, late)
    assert t1["alpha"] < 0.05 < t2["alpha"]
    # bounded
    assert pt.tune({"alpha": 0.011}, false)["alpha"] >= pt.ALPHA_RANGE[0]
    assert pt.tune({"alpha": 0.19}, late)["alpha"] <= pt.ALPHA_RANGE[1]
    # too few outcomes: nothing moves
    assert pt.tune({"alpha": 0.05}, false[:2])["alpha"] == 0.05


def test_tuner_moves_t_in_by_what_marginal_admits_did() -> None:
    bad = [{"kind": "admit", "t_at_admit": 0.6, "post_r": -2.0}] * 3
    good = [{"kind": "admit", "t_at_admit": 0.6, "post_r": 2.0}] * 3
    assert pt.tune({"t_in": 0.5}, bad)["t_in"] == pytest.approx(0.6)
    assert pt.tune({"t_in": 0.5}, good)["t_in"] == pytest.approx(0.45)
    assert pt.tune({"t_in": 1.5}, bad)["t_in"] == pt.T_IN_RANGE[1]


# ---------------------------------------------------------------- I/O
def test_run_writes_artifact_state_and_ledger(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OUT", "LEDGER", "STATE", "OFF"):
        monkeypatch.setattr(pt, name, tmp_path / name)
    art = pt.run({"EURCHF.carry.asia": clock(30, 6.0)}, now=NOW)
    assert art["n_live"] == 1
    assert json.loads((tmp_path / "STATE").read_text())["rows"]
    assert '"admit"' in (tmp_path / "LEDGER").read_text()
    live, why = pt.load_live(tmp_path / "OUT", now=NOW + timedelta(hours=1))
    assert list(live) == ["EURCHF.carry.asia"]
    stale, why = pt.load_live(tmp_path / "OUT", now=NOW + timedelta(hours=4))
    assert stale == {} and "old" in why


def test_unreadable_shadow_is_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OUT", "LEDGER", "STATE", "OFF", "SHADOW"):
        monkeypatch.setattr(pt, name, tmp_path / name)
    art = pt.run(None, now=NOW)
    assert art["status"] == "UNMEASURED" and art["live"] == {}


# ---------------------------------------------------------------- the promoter's door
@pytest.fixture
def promoter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import research.promoter as pr
    monkeypatch.setattr(pr, "_class_refusal", lambda s: None)
    monkeypatch.setattr(pr, "_probe_executor_gap", lambda m, p: None)
    monkeypatch.setattr(pr, "blind_review_veto", lambda k, *a, **kw: None)
    monkeypatch.setattr(pr, "tier_s_block", lambda k: None)
    monkeypatch.setattr(pr, "_probe_rail", lambda *a, **kw: None)
    monkeypatch.setattr(pr, "note_door", lambda *a, **kw: None)
    monkeypatch.setattr(pr, "plog", lambda m: None)
    monkeypatch.setattr(pr, "registry_sleeve_id", lambda k: None)
    return pr


IDS = {"EURCHF.carry.asia": {"symbol": "EURCHF", "family": "carry", "selector": "asia",
                             "params": {"timeframe": "M15"}, "side": "LONG"}}


def _decision(live: dict | None = None, demoted: dict | None = None) -> dict:
    return {"live": live or {}, "demoted": demoted or {}}


def test_promoter_writes_probe_live_at_probe_size_when_unmeasured(promoter) -> None:
    sleeves: list[dict] = []
    dec = _decision({"EURCHF.carry.asia": {"n": 30, "shrink": 0.375}})
    assert promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=dec)
    row = sleeves[0]
    assert row["status"] == "LIVE" and row["probe"] is True
    assert row["risk_frac"] == pytest.approx(promoter.PROMOTED_RISK_FRAC * 0.375)
    assert row["risk_frac_source"] == "probe_tier"
    assert row["exec"] == "family_market" and row["params"] == {"timeframe": "M15"}


def test_promoter_defers_to_a_measured_allocator(promoter, monkeypatch) -> None:
    monkeypatch.setattr(promoter, "capital_verdict",
                        lambda *a, **kw: {"status": "STANDBY", "risk_frac": 0.0, "why": "no"})
    sleeves: list[dict] = []
    dec = _decision({"EURCHF.carry.asia": {"n": 30, "shrink": 0.375}})
    promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": True}, decision=dec)
    assert sleeves == []
    monkeypatch.setattr(promoter, "capital_verdict",
                        lambda *a, **kw: {"status": "LIVE", "risk_frac": 0.011, "why": "yes"})
    promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": True}, decision=dec)
    assert sleeves[0]["risk_frac"] == 0.011
    assert sleeves[0]["risk_frac_source"] == "allocator_marginal"


def test_promoter_demotes_to_standby_never_retired_and_readmits(promoter) -> None:
    sleeves: list[dict] = []
    live = _decision({"EURCHF.carry.asia": {"n": 30, "shrink": 0.375}})
    promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=live)
    gone = _decision(demoted={"EURCHF.carry.asia": {"why": "SPRT: LLR 3 >= 2.77"}})
    assert promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=gone)
    assert sleeves[0]["status"] == "STANDBY" and sleeves[0]["probe_status"] == "DEMOTED"
    assert sleeves[0]["risk_frac"] == 0.0 and "retired_at" not in sleeves[0]
    promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=live)
    assert sleeves[0]["status"] == "LIVE" and sleeves[0]["probe_status"] == "LIVE"


def test_promoter_never_reopens_a_retired_row_or_a_certified_live_one(promoter) -> None:
    sleeves = [{"name": "EURCHF.carry.asia", "status": "RETIRED"}]
    dec = _decision({"EURCHF.carry.asia": {"n": 30, "shrink": 0.375}})
    assert not promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=dec)
    sleeves = [{"name": "EURCHF.carry.asia", "status": "LIVE", "risk_frac": 0.02}]
    promoter.apply_probe_tier(sleeves, {}, IDS, {"fresh": False}, decision=dec)
    assert sleeves[0]["risk_frac"] == 0.02 and "probe" not in sleeves[0]


def test_promoter_refuses_a_probe_with_no_identity(promoter) -> None:
    sleeves: list[dict] = []
    dec = _decision({"EURCHF.carry.asia": {"n": 30, "shrink": 0.375, "family": "carry",
                                           "symbol": "EURCHF"}})
    promoter.apply_probe_tier(sleeves, {}, {}, {"fresh": False}, decision=dec)
    assert sleeves == []


def test_promoter_unmeasured_tier_changes_nothing(promoter) -> None:
    sleeves = [{"name": "x", "status": "LIVE", "probe": True}]
    assert not promoter.apply_probe_tier(sleeves, {}, {}, {}, decision={"status": "UNMEASURED"})
    assert sleeves[0]["status"] == "LIVE"


# ---------------------------------------------------------------- E8
def test_e8_probe_rows_and_their_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from prop import e8_book
    for name in ("OUT", "LEDGER", "STATE", "OFF"):
        monkeypatch.setattr(pt, name, tmp_path / name)
    pt.run({"EURCHF.carry.asia": clock(30, 6.0)}, now=datetime.now(UTC), identities=IDS)
    rows, why = e8_book.probe_rows()
    assert [r["key"] for r in rows] == ["EURCHF.carry.asia"]
    r = rows[0]
    assert r["params"] == {"timeframe": "M15"} and r["probe"]["n"] == 30
    assert e8_book.sleeve_risk(r) == pytest.approx(e8_book.RISK_FRAC * 30 / 80, abs=1e-6)
    doubted = {**r, "evidence_mult": e8_book.fill_shrink(e8_book.CERT_PRIOR_N) * 0.5}
    assert e8_book.sleeve_risk(doubted) == pytest.approx(e8_book.RISK_FRAC * 30 / 80 * 0.5,
                                                         abs=1e-6)
    kept, dropped = e8_book.fallback_filter([{**r, "risk_frac": 0.001},
                                             {**r, "probe": None, "key": "other",
                                              "risk_frac": 0.001}])
    assert [k["key"] for k in kept] == ["EURCHF.carry.asia"] and len(dropped) == 1


def test_e8_probe_rows_absent_artifact_adds_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from prop import e8_book
    monkeypatch.setattr(pt, "OUT", tmp_path / "none.json")
    rows, why = e8_book.probe_rows()
    assert rows == [] and "absent" in why
