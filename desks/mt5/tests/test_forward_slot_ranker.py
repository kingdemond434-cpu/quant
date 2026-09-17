"""FORWARD SLOT RANKER -- the slot value is the product, so these pin the arithmetic.

What is fenced here, and why each one is worth a test:

  * P(certify) MOVES THE RIGHT WAY. It must rise with n and with the mean, because the whole
    claim of the organ is that a clock gathering good evidence is worth its slot more than one
    gathering little. If that monotonicity ever breaks, the ranking inverts silently and the desk
    spends its scarcest resource backwards;
  * A STRONG CLOCK IS KEPT AND A WEAK ONE IS ONLY REPORTED. REPLACEABLE needs BOTH domination on
    value and a weak posterior -- a clock with real forward evidence must never be displaced by
    an in-sample story -- and the verdict must arrive with its missed-growth line in the ledger's
    own field names, because a recommendation to stop a clock without the number it costs is the
    timid reflex the growth governance exists to forbid;
  * NOTHING IS EXECUTED. The ranker must not write to any clock state file. It reports.
  * DIVERSIFICATION BITES: a candidate on a symbol the book already clocks is worth less than the
    same candidate on a fresh one, and the only difference between the two rows is the ticker;
  * UNMEASURED IS A REAL ANSWER (L1.28a): a desk with no matured clock has NO decay measurement,
    so the prior 0.5 is used and NAMED rather than a base rate invented from one anecdote; a lane
    with no `forward_start` anywhere has UNMEASURED capacity rather than a zero;
  * CAPACITY IS MEASURED FROM HISTORY -- peak concurrency, not a guess -- and a declared file
    wins over the measurement when the desk has actually declared one.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import forward_slot_ranker as fsr  # noqa: E402

UNMEASURED = fsr.UNMEASURED
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
TH = {"VERDICT_MIN_TRADES": 50.0, "VERDICT_MIN_DAYS": 14.0, "PROMOTE_MIN_EXP": 0.05,
      "PROMOTE_MIN_DD": -25.0, "SEQ_MIN_TRADES": 20.0, "SEQ_MIN_T": 2.5}


# ------------------------------------------------------------------------------------ fixtures
@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Every path the organ reads or writes, moved into a tmp tree. Nothing touches the box."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    for name, path in (("SHADOW_DIR", shadow),
                       ("SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json"),
                       ("GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl"),
                       ("ALLOCATION", tmp_path / "pf_allocation.json"),
                       ("EXPOSURE", tmp_path / "EXPOSURE_DECOMPOSITION.json"),
                       ("CAPACITY_FILE", tmp_path / "forward_capacity.json"),
                       ("OUT", tmp_path / "FORWARD_SLOT_RANKER.json")):
        monkeypatch.setattr(fsr, name, path)
    return tmp_path


def clock(**over: Any) -> dict:
    row = {"status": "ACTIVE", "n": 10, "exp_r": 0.1, "days_active": 10, "forward_t": 0.0,
           "max_dd_r": -2.0, "forward_start": "2026-09-01T00:00:00+00:00",
           "last_entry": "2026-09-16 10:00:00+00:00"}
    row.update(over)
    return row


def write_state(desk_dir: Path, rows: dict, lane: str = "shadow") -> None:
    (desk_dir / "shadow" / fsr.LANE_FILES[lane]).write_text(
        json.dumps({"updated_at": NOW.isoformat(), **rows}), "utf-8")


def cell(symbol: str, family: str = "session_range_breakout", selector: str = "asia",
         ev: float = 0.5, sharpe: float = 0.5) -> dict:
    return {"cell": f"{symbol} {family} {selector}", "sym": symbol, "days": 300,
            "gates": {"expected_value": {"passed": True, "ev": ev},
                      "in_sample_screen": {"passed": True, "sharpe": sharpe},
                      "cpcv": {"passed": True, "mean_oos_sharpe": sharpe}},
            "shadow_spec": {"symbol": symbol, "family": family, "selector": selector}}


def write_survivors(desk_dir: Path, cells: dict) -> None:
    (desk_dir / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"n": len(cells), "survivors": cells}), "utf-8")


def row(**over: Any) -> fsr.Row:
    base = {"kind": "running", "key": "K.fam.sel", "lane": "shadow", "symbol": "K",
            "family": "fam", "selector": "sel", "n": 10.0, "days_active": 10.0, "mean_r": 0.1}
    base.update(over)
    return fsr.Row(**base)


# ------------------------------------------------------- P(certify) moves the way the claim says
def test_p_certify_rises_with_n_and_with_the_mean():
    low_n, _ = fsr.p_certify_running(row(n=5.0, mean_r=0.3), TH)
    mid_n, _ = fsr.p_certify_running(row(n=20.0, mean_r=0.3), TH)
    high_n, _ = fsr.p_certify_running(row(n=45.0, mean_r=0.3), TH)
    assert low_n < mid_n < high_n, (low_n, mid_n, high_n)

    flat, _ = fsr.p_certify_running(row(n=20.0, mean_r=0.0), TH)
    good, _ = fsr.p_certify_running(row(n=20.0, mean_r=0.3), TH)
    better, _ = fsr.p_certify_running(row(n=20.0, mean_r=0.6), TH)
    assert flat < good < better, (flat, good, better)
    # The promoter's bar is +0.05R: a clock sitting exactly on no edge must not read as a coin
    # flip on certifying, it must read as unlikely.
    assert flat < 0.5


def test_a_drawdown_past_the_promoters_bar_is_a_hard_zero():
    p, why = fsr.p_certify_running(row(n=30.0, mean_r=0.9, max_dd=-40.0), TH)
    assert p == 0.0
    assert "max_dd" in why


def test_p_certify_waiting_is_shrunk_by_the_measured_decay():
    waiting = fsr.Row("waiting", "c", "unenrolled", "S", "fam", mean_r=0.5, sigma_r=1.0)
    full, _ = fsr.p_certify_waiting(waiting, TH, 1.0)
    halved, basis = fsr.p_certify_waiting(waiting, TH, 0.5)
    assert halved == pytest.approx(full * 0.5, abs=1e-6)
    assert "decay" in basis


# ---------------------------------------------------------------------- decay, measured or not
def test_decay_is_unmeasured_without_history_and_falls_back_to_the_prior(desk):
    write_state(desk, {"A.fam.sel": clock(), "B.fam.sel": clock()})
    decay = fsr.measure_decay(fsr.lane_states())
    assert decay["decay"] == fsr.PRIOR_DECAY == 0.5
    assert decay["basis"] == UNMEASURED
    assert decay["n_matured"] == 0


def test_decay_is_measured_once_enough_clocks_have_ruled(desk):
    rows = {f"P{i}.fam.sel": clock(status="PROMOTION CANDIDATE") for i in range(8)}
    rows.update({f"K{i}.fam.sel": clock(status="KILL") for i in range(4)})
    write_state(desk, rows)
    decay = fsr.measure_decay(fsr.lane_states())
    assert decay["basis"] == "measured"
    assert decay["n_matured"] == 12
    assert decay["decay"] == pytest.approx(8 / 12, abs=1e-6)


# --------------------------------------------------------------------------- capacity from history
def test_capacity_is_the_measured_peak_concurrency(desk):
    write_state(desk, {
        "A.fam.sel": clock(status="KILL", forward_start="2026-01-01",
                           last_entry="2026-01-10", last_attempt_at="2026-01-10"),
        "B.fam.sel": clock(status="KILL", forward_start="2026-01-05",
                           last_entry="2026-01-20", last_attempt_at="2026-01-20"),
        "C.fam.sel": clock(status="KILL", forward_start="2026-01-08",
                           last_entry="2026-01-09", last_attempt_at="2026-01-09"),
        "D.fam.sel": clock(status="KILL", forward_start="2026-02-01",
                           last_entry="2026-02-02", last_attempt_at="2026-02-02"),
    })
    block = fsr.measure_capacity(fsr.lane_states(), NOW.date())["shadow"]
    assert block["capacity"] == 3                     # A, B and C overlap on 2026-01-08
    assert block["basis"] == "measured_max_concurrent"
    assert block["peak_on"] == "2026-01-08"
    assert block["running_now"] == 0
    assert block["free_slots"] == 3


def test_capacity_is_unmeasured_when_no_clock_recorded_a_start(desk):
    write_state(desk, {"A.fam.sel": {"status": "ACTIVE", "n": 3}})
    block = fsr.measure_capacity(fsr.lane_states(), NOW.date())["shadow"]
    assert block["capacity"] == UNMEASURED
    assert block["free_slots"] == UNMEASURED
    assert block["running_now"] == 1


def test_a_declared_capacity_wins_over_the_measurement(desk):
    write_state(desk, {"A.fam.sel": clock(), "B.fam.sel": clock()})
    (desk / "forward_capacity.json").write_text(json.dumps({"capacity": {"shadow": 9}}), "utf-8")
    block = fsr.measure_capacity(fsr.lane_states(), NOW.date())["shadow"]
    assert block["capacity"] == 9
    assert block["basis"].startswith("declared:")
    assert block["free_slots"] == 7


# ----------------------------------------------------------------------------- diversification
def test_a_same_symbol_candidate_is_worth_less_than_a_fresh_one(desk):
    write_state(desk, {"EURUSD.carry.continuous": clock(n=20, exp_r=0.2, days_active=20)})
    write_survivors(desk, {"hunt.same": cell("EURUSD", family="pca_residual", selector="asia"),
                           "hunt.fresh": cell("USDNOK", family="pca_residual", selector="asia")})
    payload = fsr.run(write=False, now=NOW)
    by_symbol = {e["symbol"]: e for e in payload["waiting"]}
    assert set(by_symbol) == {"EURUSD", "USDNOK"}
    same, fresh = by_symbol["EURUSD"], by_symbol["USDNOK"]
    # Identical cells: the ONLY difference is that one shares the running clock's instrument.
    assert same["diversification"] == pytest.approx(1.0 - fsr.SAME_SYMBOL_CORR)
    assert fresh["diversification"] == 1.0
    assert same["max_corr_basis"] == "same_symbol"
    assert same["slot_value"] < fresh["slot_value"]
    assert payload["waiting"][0]["symbol"] == "USDNOK"          # and the ranking says so


def test_a_same_family_candidate_is_charged_the_mechanism_proxy():
    a = fsr.Row("waiting", "a", "unenrolled", "AUDCAD", "carry")
    b = fsr.Row("running", "b", "shadow", "EURNOK", "carry")
    c = fsr.Row("running", "c", "shadow", "EURNOK", "vol_transition")
    assert fsr.pair_corr(a, b, {}) == (fsr.SAME_FAMILY_CORR, "same_family")
    assert fsr.pair_corr(a, c, {}) == (0.0, "unrelated")


# ------------------------------------------------------------- the verdicts, and what they cost
def _two_clock_desk(desk) -> dict:
    write_state(desk, {
        "STRONG.carry.continuous": clock(n=40, exp_r=0.4, days_active=20, forward_t=3.0),
        "WEAK.vol_mean_reversion.continuous": clock(n=5, exp_r=-0.3, days_active=10),
    })
    write_survivors(desk, {"hunt.NEWSYM": cell("NEWSYM")})
    return fsr.run(write=False, now=NOW)


def test_a_strong_clock_is_kept_and_a_weak_dominated_one_is_reported_replaceable(desk):
    payload = _two_clock_desk(desk)
    verdicts = {e["clock"]: e for e in payload["running"]}
    strong = verdicts["STRONG.carry.continuous"]
    weak = verdicts["WEAK.vol_mean_reversion.continuous"]

    assert strong["verdict"] == "KEEP"
    assert strong["p_certify"] >= fsr.REPLACE_P_MAX
    assert weak["verdict"] == "REPLACEABLE"
    assert weak["p_certify"] < fsr.REPLACE_P_MAX
    assert weak["slot_value"] < payload["waiting"][0]["slot_value"]
    assert payload["n_replaceable"] == 1
    assert payload["replaceable"][0]["clock"] == "WEAK.vol_mean_reversion.continuous"


def test_every_replaceable_verdict_carries_a_missed_growth_line(desk):
    payload = _two_clock_desk(desk)
    assert len(payload["missed_growth_lines"]) == payload["n_replaceable"] == 1
    line = payload["missed_growth_lines"][0]
    # The ledger's own field names (data/missed_growth.jsonl): day / rail / value / at.
    assert set(line) >= {"day", "rail", "value", "at", "units", "challenger", "clock"}
    assert line["day"] == "2026-09-17"
    assert line["rail"] == "forward_slot_occupancy:WEAK.vol_mean_reversion.continuous"
    assert line["value"] < 0.0                       # a cost, signed like a cost
    assert line["challenger"] == "hunt.NEWSYM"
    assert "never executed" in line["why"]


def test_a_clock_is_never_replaceable_without_a_waiting_candidate(desk):
    write_state(desk, {"WEAK.vol_mean_reversion.continuous": clock(n=5, exp_r=-0.3)})
    write_survivors(desk, {})
    payload = fsr.run(write=False, now=NOW)
    assert payload["running"][0]["verdict"] == "KEEP"
    assert payload["n_replaceable"] == 0
    assert payload["missed_growth_lines"] == []


def test_a_clock_with_no_measurable_rate_is_unmeasured_never_replaceable(desk):
    """No trades AND no elapsed time: there is nothing to divide by and nothing to conclude."""
    write_state(desk, {"COLD.fam.sel": clock(n=0, exp_r=None, days_active=0, forward_t=0.0,
                                             forward_start=None, first_entry=None,
                                             last_entry=None)})
    write_survivors(desk, {"hunt.NEWSYM": cell("NEWSYM")})
    payload = fsr.run(write=False, now=NOW)
    cold = payload["running"][0]
    assert cold["days_to_maturity"] == UNMEASURED
    assert cold["slot_value"] == UNMEASURED
    assert cold["verdict"] == UNMEASURED             # absence is not evidence against a clock
    assert payload["n_replaceable"] == 0


def test_a_clock_with_no_trades_yet_is_priced_low_not_hidden(desk):
    """Zero trades in forty days is a MEASUREMENT. Reporting it UNMEASURED would shelter exactly
    the slot the desk most wants to hear about, which is the timid failure in the other
    direction: measured 2026-09-17, 142 of 149 running clocks carry n = 0."""
    write_state(desk, {"BARREN.fam.sel": clock(n=0, exp_r=0.0, days_active=40),
                       "BUSY.fam.sel": clock(n=30, exp_r=0.4, days_active=20, forward_t=3.0)})
    write_survivors(desk, {})
    payload = fsr.run(write=False, now=NOW)
    barren = next(e for e in payload["running"] if e["clock"].startswith("BARREN"))
    busy = next(e for e in payload["running"] if e["clock"].startswith("BUSY"))
    assert barren["trade_rate_per_day"] == pytest.approx(fsr.RATE_SMOOTHING / 40)
    assert isinstance(barren["slot_value"], float)          # rankable, not sheltered
    assert barren["verdict"] == "KEEP"                      # nothing waiting, so nothing to lose to
    assert barren["days_to_maturity"] > busy["days_to_maturity"]
    assert barren["slot_value"] < busy["slot_value"]


def test_the_ranker_never_touches_a_clock_state_file(desk):
    state = desk / "shadow" / fsr.LANE_FILES["shadow"]
    _two_clock_desk(desk)
    before = state.read_bytes()
    fsr.run(write=True, now=NOW)
    assert state.read_bytes() == before


# --------------------------------------------------------------------------- ranking and output
def test_rows_are_ranked_by_slot_value_descending(desk):
    write_state(desk, {
        "A.carry.continuous": clock(n=30, exp_r=0.5, days_active=15, forward_t=3.0),
        "B.pca_residual.continuous": clock(n=20, exp_r=0.2, days_active=20),
        "C.vol_transition.continuous": clock(n=6, exp_r=0.02, days_active=12),
    })
    write_survivors(desk, {"hunt.X": cell("XSYM", ev=0.6), "hunt.Y": cell("YSYM", ev=0.2)})
    payload = fsr.run(write=False, now=NOW)
    for key in ("running", "waiting"):
        values = [e["slot_value"] for e in payload[key]]
        assert values == sorted(values, reverse=True), (key, values)
    assert len(payload["running"]) == 3
    assert payload["waiting"][0]["cell"] == "hunt.X"


def test_the_artifact_carries_the_rule_the_formula_and_every_term(desk):
    _two_clock_desk(desk)
    payload = fsr.run(write=True, now=NOW)
    written = json.loads((desk / "FORWARD_SLOT_RANKER.json").read_text("utf-8"))
    assert written["rule"] == fsr.RULE == payload["rule"]
    assert "never executed here" in written["rule"]
    assert "slot_value = P(certify forward)" in written["formula"]
    assert set(written) >= {"at", "capacity", "running", "waiting", "replaceable",
                            "missed_growth_lines", "decay_measured", "unmeasured"}
    for entry in written["running"]:
        assert set(entry) >= {"clock", "symbol", "family", "n", "p_certify", "days_to_maturity",
                              "delta_elogw", "diversification", "slot_value", "verdict"}
        assert entry["verdict"] in ("KEEP", "REPLACEABLE", UNMEASURED)


def test_thresholds_are_read_from_shadow_forward_not_copied():
    th = fsr.maturity_thresholds()
    assert th["basis"].startswith("parsed:shadow_forward")
    assert th["VERDICT_MIN_TRADES"] == 50.0
    assert th["VERDICT_MIN_DAYS"] == 14.0
    assert th["PROMOTE_MIN_EXP"] == 0.05


def test_a_certified_cell_already_on_a_clock_is_not_waiting_for_a_slot(desk):
    write_state(desk, {"EURUSD.session_range_breakout.asia": clock()})
    write_survivors(desk, {"hunt.enrolled": cell("EURUSD"), "hunt.free": cell("USDNOK")})
    payload = fsr.run(write=False, now=NOW)
    assert [e["symbol"] for e in payload["waiting"]] == ["USDNOK"]


def test_cli_dry_run_prints_and_writes_nothing(desk, capsys):
    _two_clock_desk(desk)
    out = desk / "FORWARD_SLOT_RANKER.json"
    assert fsr.main(["--dry-run"]) == 0
    assert not out.exists()
    printed = capsys.readouterr().out
    assert "FORWARD SLOT RANKER" in printed
    assert "dry run, nothing written" in printed

    assert fsr.main([]) == 0
    assert out.exists()
    assert json.loads(out.read_text("utf-8"))["rule"] == fsr.RULE
