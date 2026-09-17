"""RESEARCH_DEBT: what a mechanism tested on one coordinate still owes on every other.

The fixture is the case the ledger exists for -- `session_handover` judged on FX x H1 x asia and
nowhere else. The assertions are that the other charts, sessions, regimes, asset classes,
execution expressions and the residual expression all appear as UNMEASURED with a count, that the
economically impossible ones (D1 under a session window, a single-name equity) never appear at
all, and that a mechanism nobody has judged is listed as NEVER TESTED rather than carrying a debt
-- because "never tested" and "tested and found wanting on a thousand untried cells" are different
states and rendering them identically is how an unmined mechanism disappears into an average.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import research_debt as rd  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

CLASSES = ["forex", "commodities", "indices", "equities"]


@pytest.fixture
def reg(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


def _enqueue(**over: Any) -> str:
    row = {"family": "asia_momentum", "symbol": "EURUSD", "params": {}, "origin": "DESK",
           "mechanism": "session_handover", "status": "judged", "chart": "H1", "session": "asia",
           "regime": "unconditional", "horizon": "sub_4h", "asset_class": "forex",
           "information": "price_only", "economic_actor": "cross_session_risk_transferor"}
    row.update(over)
    family = row.pop("family")
    symbol = row.pop("symbol")
    params = row.pop("params")
    origin = row.pop("origin")
    mechanism = row.pop("mechanism")
    status = row.pop("status")
    cid, _created = R.enqueue_candidate(family=family, symbol=symbol, params=params,
                                        origin=origin, mechanism=mechanism, status=status, **row)
    return cid


# --------------------------------------------------------------------------- the closure
def test_admissible_axes_come_from_the_contract_and_drop_equities():
    axes = rd.admissible("session_handover", CLASSES)
    assert axes["chart"] == list(TM.CONTRACTS["session_handover"].charts)
    assert "D1" not in axes["chart"]
    assert axes["session"] == list(TM.SESSION_LADDER)
    assert axes["asset_class"] == ["commodities", "forex", "indices"]
    assert axes["regime"][0] == "unconditional"
    assert axes["expression"] == ["base", "residual"]          # not symmetric: no inverse arm


def test_a_symmetric_mechanism_carries_an_inverse_arm_and_a_directional_one_does_not():
    assert "inverse" in rd.admissible("range_reversion", CLASSES)["expression"]
    assert "inverse" not in rd.admissible("session_handover", CLASSES)["expression"]


def test_an_unknown_mechanism_gets_the_conservative_closure_not_the_widest():
    axes = rd.admissible(TM.UNKNOWN_MECHANISM, CLASSES)
    assert axes["session"] == ["all"] and axes["regime"] == ["unconditional"]
    assert axes["expression"] == ["base"]


def test_the_plausible_closure_never_contains_an_impossible_chart_session_pair():
    cells = rd.plausible_cells("session_handover", rd.admissible("session_handover", CLASSES))
    assert cells
    assert not [c for c in cells if c["chart"] == "D1"]
    assert not [c for c in cells if c["asset_class"] == "equities"]
    assert {c["session"] for c in cells} == set(TM.SESSION_LADDER)


def test_a_month_end_flow_contract_keeps_the_quarter_end_regime_and_the_daily_charts():
    axes = rd.admissible("calendar_seasonality", CLASSES)
    assert "quarter_end" in axes["regime"] and "month_end" in axes["regime"]
    assert set(axes["chart"]) == {"H4", "D1"}
    assert axes["session"] == ["all"]


# --------------------------------------------------------------------------- the ledger
def test_a_mechanism_tested_on_fx_h1_asia_owes_every_other_axis(reg):
    _enqueue()
    report = rd.build(classes=CLASSES)
    assert report["n_mechanisms"] == 1
    m = report["mechanisms"][0]
    assert m["mechanism_id"] == "session_handover"
    assert m["tested_cells"] == 1
    assert m["tested"] == {"asset_class": ["forex"], "chart": ["H1"], "session": ["asia"],
                           "regime": ["unconditional"], "execution": ["instant/market"],
                           "expression": ["base"]}
    assert m["unmeasured"]["chart"] == ["H4", "M15"]
    assert m["unmeasured"]["session"] == ["london", "ny"]
    assert m["unmeasured"]["asset_class"] == ["commodities", "indices"]
    assert m["unmeasured"]["regime"] == sorted(TM.REGIME_LADDER)
    assert m["unmeasured"]["expression"] == ["residual"]
    assert len(m["unmeasured"]["execution"]) == 3
    assert m["debt_cells"] == m["plausible_cells"] - 1
    assert 0.0 < m["coverage"] < 0.01
    assert report["total_debt"] == m["debt_cells"]
    assert m["contract"]["falsifier"] and m["contract"]["actor"]


def test_the_top_untested_rows_are_real_coordinates_a_session_could_be_run_on(reg):
    _enqueue()
    m = rd.build(classes=CLASSES)["mechanisms"][0]
    assert 0 < len(m["top_untested"]) <= rd.MAX_TOP_UNTESTED
    for cell in m["top_untested"]:
        assert set(cell) == set(rd.DEBT_AXES)
        assert cell["chart"] != "D1"
        assert cell["asset_class"] != "equities"


def test_a_queued_candidate_is_not_a_tested_one(reg):
    _enqueue(status="queued", symbol="GBPUSD")
    report = rd.build(classes=CLASSES)
    assert report["n_mechanisms"] == 0
    assert report["total_debt"] == 0
    assert any(u["what"] == "tested cells" for u in report["unmeasured"])
    assert "UNMEASURED rather than zero" in " ".join(u["why"] for u in report["unmeasured"])


def test_a_judged_at_stamp_counts_even_when_the_status_string_is_unfamiliar(reg):
    cid = _enqueue(status="odd_status", symbol="USDJPY")
    R.mark_candidate(cid, "odd_status", judged_at="2026-09-17T00:00:00+00:00",
                     terminal_gate="deflated_sharpe")
    assert rd.build(classes=CLASSES)["n_mechanisms"] == 1


def test_a_mechanism_nobody_judged_is_never_tested_not_a_debt(reg):
    _enqueue()
    report = rd.build(classes=CLASSES)
    never = {m["mechanism_id"] for m in report["untested_mechanisms"]}
    assert "session_handover" not in never
    assert {"carry_rollover", "breakout_liquidity", "fx_fixing_flow"} <= never
    assert all(m["plausible_cells"] > 0 for m in report["untested_mechanisms"])
    assert all("UNMEASURED" in m["why"] for m in report["untested_mechanisms"])


def test_prose_in_the_mechanism_field_is_interpreted_rather_than_dropped(reg):
    _enqueue(mechanism="the carry differential and the swap rollover on the exotic cross",
             symbol="USDJPY", chart="H4", session="all")
    report = rd.build(classes=CLASSES)
    assert [m["mechanism_id"] for m in report["mechanisms"]] == ["carry_rollover"]


def test_the_conversion_debt_section_rides_on_the_same_artifact(reg):
    _enqueue()
    R.record_discovery(source_id="s1", source_type="intelligence", mechanism="something",
                       origin="DESK", generator="t")
    cd = rd.build(classes=CLASSES)["conversion_debt"]
    assert cd["n_discoveries"] == 1
    assert cd["unprocessed_discoveries"] == 1
    assert "unexplained_missing_cells" in cd and "rule" in cd


def test_an_unresolved_instrument_registry_is_a_named_gap(reg):
    _enqueue()
    report = rd.build(classes=[])
    assert any(u["what"] == "asset classes" for u in report["unmeasured"])
    assert "understate" in " ".join(u["why"] for u in report["unmeasured"])


# --------------------------------------------------------------------------- the organ
def test_run_writes_the_artifact_and_dry_run_does_not(reg, tmp_path):
    _enqueue()
    out = tmp_path / "RESEARCH_DEBT.json"
    report = rd.run(dry_run=True, out=out, classes=CLASSES)
    assert not out.exists() and report["total_debt"] > 0
    rd.run(dry_run=False, out=out, classes=CLASSES)
    assert out.exists()
    assert "mechanisms" in out.read_text(encoding="utf-8")


def test_cli_dry_run(reg, monkeypatch, capsys, tmp_path):
    _enqueue()
    monkeypatch.setattr(rd, "OUT", tmp_path / "RESEARCH_DEBT.json")
    assert rd.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "research debt" in out and "untested chart" in out
    assert "NEVER TESTED" in out and "conversion coverage" in out
    assert not (tmp_path / "RESEARCH_DEBT.json").exists()


def test_the_rule_line_says_what_the_number_means():
    assert "claim requiring evidence" in rd.RULE
