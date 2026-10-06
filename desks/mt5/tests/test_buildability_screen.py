"""The judge is never handed a cell it cannot build, and no such cell leaves the trial census.

Measured 2026-10-06 on the committed docket: 2,284 of 57,538 rows (4.0%) were unbuildable by the
sealed judge's own lookups -- relational families on sub-hour charts, `calendar_month` with no
month, `clock_transition` with no stamp hour, COT/fx claims whose frame the judge never loads,
and a hunt16 family handed a worded side. These tests pin both halves: the producers mint the
cells the judge can build, and the merge screen holds the rest OUT of the docket and IN the
census.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import experiment_ledger as el  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402
from research import merge_hypotheses as mh  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402


def _all_buildable(cells: list[tuple[str, dict]]) -> bool:
    return bool(cells) and all(
        gb.cell_verdict(f, p, p.get("timeframe"))[0] == gb.BUILDABLE for f, p in cells)


def test_a_relational_family_is_rehomed_to_its_declared_charts_never_dropped() -> None:
    from mt5desk.families_orthogonal import timeframe_domain
    for fam in ("relative_value", "correlation_regime", "cross_asset_residual", "pca_residual",
                "style_premia", "macro_conditional", "lead_lag"):
        params = {"timeframe": "M15"}
        if fam == "lead_lag":
            params["driver_symbol"] = "XPTUSD"
        cells, why = gb.repair_cell(fam, params)
        charts = {str(p.get("timeframe") or "H1") for _f, p in cells}
        assert charts == set(timeframe_domain(fam)), (fam, why)
        assert all(gb.cell_verdict(f, p, p.get("timeframe"))[0] != gb.TIMEFRAME_REFUSED
                   for f, p in cells)


def test_an_m5_only_family_minted_on_h1_moves_to_m5() -> None:
    cells, _ = gb.repair_cell("lvc_asia_london", {})
    assert [p.get("timeframe") for _f, p in cells] == ["M5"]


def test_calendar_month_with_no_month_becomes_the_explicit_grid() -> None:
    cells, why = gb.repair_cell("calendar_month", {})
    assert len(cells) == 24 and _all_buildable(cells) and "charged" in why
    one, _ = gb.repair_cell("calendar_month", {"active_month": 3})
    assert {p["active_month"] for _f, p in one} == {3} and len(one) == 2


def test_clock_transition_gets_its_stamp_hours_from_the_catalogue() -> None:
    cells, why = gb.repair_cell("clock_transition", {
        "label": "cash_equity_close", "stamp_hour": None, "mode": "fade", "side": 1,
        "lead_bars": 1, "hold_bars": 2})
    assert _all_buildable(cells) and "catalogue" in why
    assert all(0 <= p["stamp_hour"] <= 23 for _f, p in cells)


def test_cot_claims_route_to_the_conditioner_the_judge_supplies() -> None:
    for fam in ("cot_comm_follow", "cot_change_momentum"):
        cells, why = gb.repair_cell(fam, {"session": "asia"})
        assert [f for f, _p in cells] == ["cot_positioning"] and _all_buildable(cells), why


def test_an_unsupplied_input_is_not_repaired_and_says_why() -> None:
    cells, why = gb.repair_cell("usd_session_shock", {"representation": "regional_interaction"})
    assert cells == [] and "fx" in why


def test_hunt16_resolves_and_a_worded_side_becomes_numeric() -> None:
    assert gb.family_verdict("dav_range_filter_adx")[0] == gb.BUILDABLE
    assert gb.cell_verdict("dav_range_filter_adx", {"side": "SHORT"})[0] == gb.MISSING_PARAMS
    assert gb.cell_verdict("dav_range_filter_adx", {})[0] == gb.MISSING_PARAMS
    cells, _ = gb.repair_cell("dav_range_filter_adx", {"side": "SHORT", "timeframe": "M15"})
    assert cells == [("dav_range_filter_adx", {"side": -1, "timeframe": "M15"})]


def test_requeue_reads_the_side_its_certificate_key_states() -> None:
    from research import requeue_unrunnable as rq
    row = {"_key": "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY",
           "shadow_spec": {"symbol": "AUDNZD", "family": "dav_range_filter_adx"}}
    cand = rq._candidate(row, "params absent")
    assert cand["params"] == {"side": -1}


def test_the_compiler_mints_an_exact_recipe_as_buildable_cells() -> None:
    row = {"family": "correlation_regime", "params": {"timeframe": "M15"},
           "symbol": "AUDCAD", "title": "horizon of AUDCAD -> AUDCAD M15 london"}
    cands, disp = mcc.compile_row("discovery_compiler", row, {"AUDCAD"})
    assert disp == "EXACT_RECIPE" and cands
    assert all(gb.cell_verdict(c["family"], c["params"], c["params"].get("timeframe"))[0]
               == gb.BUILDABLE for c in cands)
    assert all(c["repaired"]["from_params"] == {"timeframe": "M15"} for c in cands)
    # an unrepairable recipe is still minted, with its reason, for the merge screen to charge
    keep, disp2 = mcc.compile_row("moat_factory", {"family": "usd_session_shock", "params": {},
                                                   "symbol": "USDZAR"}, {"USDZAR"})
    assert disp2 == "EXACT_RECIPE" and len(keep) == 1 and "fx" in keep[0]["buildability"]


def test_axis_expansion_never_mints_a_chart_the_family_declares_inexpressible(
        monkeypatch) -> None:
    monkeypatch.setattr(mcc, "_charts_with_bars", lambda s: ["M5", "M15", "M30"])
    monkeypatch.setattr(mcc, "_invariance", lambda s, f: None)
    monkeypatch.setattr(mcc, "_session_slots", lambda f, b, s: [("all", b, None)])
    out = mcc.expand_axes([{"symbol": "AUDCAD", "family": "relative_value", "params": {}},
                           {"symbol": "AUDCAD", "family": "session_range_breakout",
                            "params": {}}])
    rv = {c["axis"]["chart"] for c in out if c["family"] == "relative_value"}
    srb = {c["axis"]["chart"] for c in out if c["family"] == "session_range_breakout"}
    assert rv == {"H1"}
    assert srb == {"M5", "M15", "M30", "H1"}          # an undeclared family keeps every chart


def _refused_rows() -> list[dict]:
    return [
        {"symbol": "AUDCAD", "family": "relative_value", "params": {"timeframe": "M15"}},
        {"symbol": "AUDJPY", "family": "calendar_month", "params": {}},
        {"symbol": "USDZAR", "family": "usd_session_shock", "params": {}},
    ]


def test_the_screen_holds_unbuildable_rows_and_keeps_everything_else() -> None:
    ok = {"symbol": "EURUSD", "family": "session_range_breakout", "params": {}}
    keep, refused = gb.screen_rows([ok, *_refused_rows()])
    assert keep == [ok] and len(refused) == 3
    assert {r["refusal_verdict"] for r in refused} == {
        gb.TIMEFRAME_REFUSED, gb.MISSING_PARAMS, gb.INPUT_NOT_SUPPLIED}


def test_an_unreadable_verdict_refuses_nothing(monkeypatch) -> None:
    """L1.28a: a screen that cannot read the judge's code holds no row."""
    monkeypatch.setattr(gb, "cell_verdict", lambda *a, **k: (gb.UNMEASURED, "unimportable"))
    keep, refused = gb.screen_rows(_refused_rows())
    assert len(keep) == 3 and refused == []

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(gb, "cell_verdict", boom)
    assert gb.screen_rows(_refused_rows()) == (_refused_rows(), [])


def test_holding_cells_out_of_the_docket_never_lowers_the_lifetime_trial_census(
        tmp_path, monkeypatch) -> None:
    """BEFORE: the unbuildable cells reached the judge and were charged as judged cells.
    AFTER: the screen holds them and the screened-refused ledger charges them. Equal, and a
    second hourly merge of the same rows charges nothing twice."""
    rows = _refused_rows()
    base_judged = 1000
    monkeypatch.setattr(el, "_proposer_counts", lambda: (500, {"x": 500}))
    monkeypatch.setattr(el, "_mass_screen_counts", lambda path=None: (7, {"m": 7}))
    monkeypatch.setattr(el, "_claim_selection_counts", lambda: (3, {"s": 3}))
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)
    ledger = tmp_path / mh.SCREENED_REFUSED_NAME
    monkeypatch.setattr(el, "SCREENED_REFUSED_TRIALS", ledger)

    monkeypatch.setattr(el, "_graph_counts", lambda: (base_judged + len(rows), {}))
    before = el.lifetime(write=False)["lifetime_trials"]

    _keep, refused = gb.screen_rows(rows)
    monkeypatch.setattr(el, "_graph_counts", lambda: (base_judged, {}))
    rep = mh.record_screened_refusals(refused, ledger, "2026-10-06T00:00:00+00:00")
    after = el.lifetime(write=False)
    assert rep["new_cells"] == len(rows)
    assert after["lifetime_trials"] == before
    assert after["screened_refused_cells"] == len(rows)

    again = mh.record_screened_refusals(refused, ledger, "2026-10-06T01:00:00+00:00")
    assert again["new_cells"] == 0
    assert el.lifetime(write=False)["lifetime_trials"] == before
    assert len(ledger.read_text("utf-8").splitlines()) == len(rows)
    assert all(json.loads(ln)["reason"] for ln in ledger.read_text("utf-8").splitlines())
