"""The posterior-sized book against a static size per sleeve: a report, both ways, no look-ahead."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "research"))
sys.path.insert(0, str(HERE.parent))

import hourly_cycle  # noqa: E402
import missed_growth  # noqa: E402
import posterior_sizing_missed_growth as psm  # noqa: E402

from libs.research.layers import LEG_LAYER  # noqa: E402

N = 14


def _stream(good: bool) -> dict:
    """Alternating -1R / +1R. `good`: the recorded fraction is 0.02 into winners and 0 into
    losers after a first post of 0.02; otherwise the reverse."""
    r = [(-1.0 if i % 2 == 0 else 1.0) for i in range(N)]
    f = [0.02] + [(0.02 if (x > 0) == good else 0.0) for x in r[1:]]
    return {"kind": "live", "r": r, "recorded": f, "sources": ["ledger_row"] * N}


def _line(series: dict) -> dict:
    res = psm.evaluate(series)
    return psm.missed_growth_line(res["aggregate"], "2026-11-10T00:00:00+00:00")


def test_as_sized_beating_static_is_a_gain() -> None:
    res = psm.evaluate({("a", f"s{i}"): _stream(True) for i in range(4)})
    ag = res["aggregate"]["recorded"]["static_first"]
    assert ag["status"] == "MEASURED" and ag["wins"] == 4 and ag["losses"] == 0
    assert ag["win_share"] == 1.0 and ag["delta_logw_sum"] > 0
    assert ag["sign_test_p_as_sized_better"] == 0.0625          # 1 / 2**4, exact
    assert ag["t_stat"] is not None and ag["t_stat"] > 0
    line = psm.missed_growth_line(res["aggregate"], "t")
    assert line["verdict"] == "EARNS_ITS_PLACE" and line["basis"] == "recorded"
    assert line["significant"] is True and line["t_stat"] >= psm.SIGNIFICANT_T
    assert line["direction"] == "gained" and line["value"] > 0 and line["forgone_logw"] == 0
    assert "diffs" not in res["streams"]["a|s0"]["recorded"]["static_first"]


def test_as_sized_losing_to_static_is_forgone_growth() -> None:
    series = {("a", f"s{i}"): _stream(False) for i in range(4)}
    line = _line(series)
    assert line["verdict"] == "COSTS_GROWTH" and line["direction"] == "forgone"
    assert line["significant"] is True and line["t_stat"] <= -psm.SIGNIFICANT_T
    assert line["value"] < 0 and line["forgone_logw"] == -line["value"]
    assert line["sign_test_p"] == 0.0625 and line["win_share"] == 0.0


def test_short_streams_are_unmeasured_never_zero() -> None:
    short = {"kind": "live", "r": [1.0, -1.0, 1.0], "recorded": [0.02, 0.01, 0.02],
             "sources": ["ledger_row"] * 3}
    line = _line({("a", "s"): short})
    assert line["verdict"] == "UNMEASURED" and line["value"] is None
    assert line["forgone_logw"] is None and "floor" in line["why"]
    # two scored streams are still under the cross-stream floor of three
    two = _line({("a", "s1"): _stream(True), ("a", "s2"): _stream(True)})
    assert two["verdict"] == "UNMEASURED" and two["value"] is None


def test_absent_inputs_are_unmeasured(tmp_path: Path) -> None:
    doc = psm.build(tmp_path / "live_ledger.jsonl", tmp_path / "decision_ledger.jsonl",
                    tmp_path / "shadow")
    assert doc["mode"] == "REPORT" and doc["live_sizing_changed"] is False
    assert doc["status"] == "UNMEASURED"
    assert all(v["status"] == "UNMEASURED" for v in doc["inputs"].values())
    line = doc["missed_growth_line"]
    assert line["verdict"] == "UNMEASURED" and line["value"] is None
    assert "no trade stream" in line["why"]


def test_ledger_join_keys_by_account_dedupes_and_reads_the_decision_fraction(
        tmp_path: Path) -> None:
    ledger = tmp_path / "live_ledger.jsonl"
    rows = []
    for acct in (1, 2):
        for i in range(3):
            rows.append({"time": f"2026-10-0{i + 1}T10:00:00+00:00", "sleeve": "gold_asia",
                         "account": acct, "deal": acct * 100 + i, "r_multiple": 0.5,
                         "entry_order": acct * 1000 + i, "r_unreconstructible": False})
    rows.append(dict(rows[0]))                                   # the same deal written twice
    rows.append({"time": "2026-10-09T10:00:00+00:00", "sleeve": "gold_asia", "account": 1,
                 "deal": 999, "r_multiple": 1.0, "risk_usd": 50.0, "equity": 10000.0})
    rows.append({"time": "2026-10-09T11:00:00+00:00", "sleeve": "gold_asia", "account": 1,
                 "deal": 998, "r_multiple": 9.0, "r_unreconstructible": True})
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    dec = tmp_path / "decision_ledger.jsonl"
    dec.write_text("".join(json.dumps(d) + "\n" for d in [
        {"outcome": "EXECUTED", "ticket": 1000, "portfolio_context": {"h": 0.004}},
        {"outcome": "EXECUTED", "ticket": 1001, "portfolio_context": {"h": None}},
        {"outcome": "RISK_REJECTED", "ticket": 1002, "portfolio_context": {"h": 0.5}},
    ]), encoding="utf-8")
    live = psm.load_live(ledger, psm.load_decisions(dec))
    assert set(live) == {("1", "gold_asia"), ("2", "gold_asia")}
    one = live[("1", "gold_asia")]
    assert one["r"] == [0.5, 0.5, 0.5, 1.0]
    assert one["recorded"] == [0.004, None, None, 0.005]
    assert one["sources"] == ["allocator_decision_h", None, None, "ledger_row"]
    assert live[("2", "gold_asia")]["recorded"] == [None, None, None]


def test_forward_ledgers_use_forward_phase_only(tmp_path: Path) -> None:
    sh = tmp_path / "shadow"
    sh.mkdir()
    (sh / "ledger_EURUSD_asia.json").write_text(json.dumps([
        {"entry_time": "2026-01-02", "r_multiple": 2.0, "phase": "historical"},
        {"entry_time": "2026-10-02", "r_multiple": -1.0, "phase": "forward"},
        {"entry_time": "2026-10-01", "r_multiple": 0.5, "phase": "forward"}]), encoding="utf-8")
    fwd = psm.load_forward(sh)
    assert fwd[("forward", "EURUSD_asia")]["r"] == [0.5, -1.0]
    assert fwd[("forward", "EURUSD_asia")]["recorded"] == [None, None]


def test_no_look_ahead_the_fraction_at_t_ignores_trade_t() -> None:
    r = [0.8, -1.0, 1.2, 0.9, -1.0, 1.1, 0.7, -1.0, 1.3, 0.6, 1.0, -1.0]
    t = 8
    base = psm.fractions(r, [0.01] * len(r))
    other = list(r)
    other[t] = -25.0                                            # the trade about to be realised
    moved = psm.fractions(other, [0.01] * len(r))
    for book in ("recorded", "replay", "static_expanding"):
        assert moved[book][: t + 1] == base[book][: t + 1], book
    assert base["replay"][psm.WARMUP - 1] is None and base["replay"][psm.WARMUP] is not None
    # and the solve is not blind: a different PAST does move a later fraction
    past = list(r)
    past[0] = -25.0
    assert psm.fractions(past)["static_expanding"][t] != base["static_expanding"][t]


def test_replay_calls_the_live_solve_and_scores_without_a_recorded_fraction() -> None:
    wins = {"kind": "live", "r": [1.0] * 6 + [0.9, 1.1] * 6, "recorded": [], "sources": []}
    res = psm.evaluate({("a", f"s{i}"): dict(wins) for i in range(3)})
    blk = res["streams"]["a|s0"]["replay"]
    assert blk["n_with_fraction"] == 18 - psm.WARMUP
    assert 0.0 < blk["first_fraction"] <= psm.F_CAP
    assert res["aggregate"]["recorded"]["static_first"]["status"] == "UNMEASURED"
    line = psm.missed_growth_line(res["aggregate"], "t")
    assert line["basis"] == "replay" and "REPLAY" in line["basis_note"]


def test_the_leg_is_wired_and_has_a_layer() -> None:
    name = "posterior_sizing_missed_growth"
    assert LEG_LAYER[name] == "sizing"
    # a sizing-layer measurement sits with the allocator's department, not the macro brain's
    assert hourly_cycle.LEG_DEPARTMENT[name] == "forward"
    assert hourly_cycle.LEG_DEPARTMENT["pf_allocator"] == "forward"
    assert callable(getattr(hourly_cycle, name))
    src = (HERE.parent / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert f'_costed("{name}", {name})' in src and f'"{name}": psmg' in src
    # a report leg: no trading entry point's import closure may name it
    assert name not in (REPO / "ops" / "money_closure.txt").read_text(encoding="utf-8")
    rows = json.loads((REPO / "docs" / "research" / "runtime_state.json")
                      .read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else next(v for v in rows.values()
                                                    if isinstance(v, list))
    assert any(r.get("organ") == f"leg:{name}" for r in rows if isinstance(r, dict))


def test_missed_growth_republishes_the_line_two_sided(tmp_path: Path, monkeypatch) -> None:
    rep = tmp_path / "posterior_sizing_missed_growth.json"
    monkeypatch.setattr(missed_growth, "POSTERIOR_SIZING", rep)
    assert missed_growth.published_posterior_sizing_line()["verdict"] == "UNMEASURED"
    now = datetime.now(tz=UTC)
    for good, verdict, sign in ((True, "EARNS_ITS_PLACE", 1), (False, "COSTS_GROWTH", -1)):
        res = psm.evaluate({("a", f"s{i}"): _stream(good) for i in range(3)})
        line = psm.missed_growth_line(res["aggregate"], now.isoformat())
        rep.write_text(json.dumps({"generated_at": now.isoformat(),
                                   "missed_growth_line": line}), encoding="utf-8")
        got = missed_growth.published_posterior_sizing_line()
        assert got["verdict"] == verdict and got["value_logw"] * sign > 0
        assert got["significant"] is True and got["t_stat"] == line["t_stat"]
        assert got["sign_test_p"] == line["sign_test_p"]
    rep.write_text(json.dumps({"generated_at": (now - timedelta(hours=9)).isoformat(),
                               "missed_growth_line": line}), encoding="utf-8")
    assert missed_growth.published_posterior_sizing_line()["verdict"] == "UNMEASURED"
    rep.write_text(json.dumps({"generated_at": now.isoformat(), "missed_growth_line": {
        "verdict": "UNMEASURED", "value": None, "why": "short"}}), encoding="utf-8")
    got = missed_growth.published_posterior_sizing_line()
    assert got["verdict"] == "UNMEASURED" and got["why"] == "short" and "value_logw" not in got
    assert got["significant"] is False


def _aggs(delta: float, t: float | None, basis: str = "replay") -> dict:
    """An aggregate block with one MEASURED basis carrying this summed delta and t-stat."""
    unmeasured = {"status": "UNMEASURED", "why": "no recorded fraction"}
    ag = {"status": "MEASURED", "scored_streams": 5, "wins": 2, "losses": 3, "ties": 0,
          "n_trades": 180, "win_share": 0.4, "delta_logw_sum": delta,
          "delta_logw_per_trade": delta / 180, "sign_test_p_as_sized_better": 0.8125,
          "sign_test_p_static_better": 0.5, "t_stat": t,
          "t_stat_note": None if t is not None else "fewer than 20 pooled differences"}
    return {b: {"static_first": ag if b == basis else unmeasured} for b in psm.BASES}


def _published(line: dict, tmp_path: Path, monkeypatch) -> dict:
    rep = tmp_path / "posterior_sizing_missed_growth.json"
    monkeypatch.setattr(missed_growth, "POSTERIOR_SIZING", rep)
    rep.write_text(json.dumps({"generated_at": datetime.now(tz=UTC).isoformat(),
                               "missed_growth_line": line}), encoding="utf-8")
    return missed_growth.published_posterior_sizing_line()


def test_the_two_significance_thresholds_are_one_number() -> None:
    assert psm.SIGNIFICANT_T == missed_growth.POSTERIOR_SIZING_SIGNIFICANT_T == 2.0
    assert psm.NOT_SIGNIFICANT == missed_growth.NOT_SIGNIFICANT == "NOT_SIGNIFICANT"


def test_a_non_significant_negative_sum_is_not_published_as_a_cost(
        tmp_path: Path, monkeypatch) -> None:
    """The real case: sum -0.055 at t -1.05 on the replay basis. Not a cost, not a gain."""
    line = psm.missed_growth_line(_aggs(-0.055, -1.05), "t")
    assert line["verdict"] == "NOT_SIGNIFICANT" and line["significant"] is False
    assert line["direction"] == "not_significant" and line["forgone_logw"] is None
    assert line["value"] == -0.055 and line["t_stat"] == -1.05 and line["sign_test_p"] == 0.5
    got = _published(line, tmp_path, monkeypatch)
    assert got["verdict"] == "NOT_SIGNIFICANT" and got["significant"] is False
    assert got["verdict"] != missed_growth.COSTS and got["direction"] == "not_significant"
    assert got["value_logw"] == -0.055 and got["t_stat"] == -1.05 and got["sign_test_p"] == 0.5
    assert "cost" not in got["verdict"].lower() and "forgone" not in str(got["direction"])


def test_a_bare_sign_verdict_from_an_older_report_cannot_bill_a_cost(
        tmp_path: Path, monkeypatch) -> None:
    """The published line re-derives significance from the t-stat; it never trusts the verdict."""
    old = {"verdict": "COSTS_GROWTH", "direction": "forgone", "value": -0.055, "t_stat": -1.05,
           "sign_test_p": 0.5, "basis": "replay"}
    got = _published(old, tmp_path, monkeypatch)
    assert got["verdict"] == "NOT_SIGNIFICANT" and got["significant"] is False


def test_a_significant_sum_publishes_its_sign_on_both_lines(
        tmp_path: Path, monkeypatch) -> None:
    for delta, t, verdict, direction in ((0.31, 2.4, "EARNS_ITS_PLACE", "gained"),
                                         (-0.31, -2.0, "COSTS_GROWTH", "forgone")):
        line = psm.missed_growth_line(_aggs(delta, t), "t")
        got = _published(line, tmp_path, monkeypatch)
        for ln in (line, got):
            assert ln["verdict"] == verdict and ln["significant"] is True
            assert ln["direction"] == direction and ln["t_stat"] == t
        assert got["value_logw"] == delta and got["sign_test_p"] == line["sign_test_p"]
    assert line["forgone_logw"] == 0.31


def test_a_missing_t_stat_is_never_significant(tmp_path: Path, monkeypatch) -> None:
    for delta in (0.4, -0.4):
        line = psm.missed_growth_line(_aggs(delta, None), "t")
        assert line["verdict"] == "NOT_SIGNIFICANT" and line["significant"] is False
        assert line["t_stat"] is None and "no t-stat" in line["why"]
        got = _published(line, tmp_path, monkeypatch)
        assert got["verdict"] == "NOT_SIGNIFICANT" and got["significant"] is False
        assert got["t_stat"] is None and got["value_logw"] == delta
    assert psm.is_significant(None) is False and psm.is_significant(True) is False
    assert psm.is_significant(float("nan")) is False and psm.is_significant(-2.0) is True
