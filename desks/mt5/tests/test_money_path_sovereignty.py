"""MONEY-PATH SOVEREIGNTY, pinned (principal's audit, 2026-09-30, and the blueprint re-score).

    I1 allocator zero / absent / non-finite  -> no order, and the sizers return 0.0
    I2 UNMEASURED (or absent) admission      -> shadow
    I3 banned family (read, never restated)  -> no new risk
    I4 UNMEASURED material cost              -> shadow, decided by cost_surfaces.cost_for
    I5 UNMEASURED marginal dE[log W]         -> shadow
    I6 principal override outside the declared experimental budget -> no new risk

plus the fence that keeps every new-risk placement site calling the guard, and the identity tag
every new order now carries.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import money_path as mp  # noqa: E402
from research import cost_surfaces as cs  # noqa: E402
from research import missed_growth as mg  # noqa: E402
from scripts import check_money_path_sovereignty as fence  # noqa: E402

MEASURED = {"status": mp.MEASURED, "source": "test"}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _row(**kw):
    row = {"name": "s1", "symbol": "EURUSD", "family": "overnight_gap_decay",
           "origin": "registry", "sized_by": "allocator_book", "risk_frac": 0.01,
           "admission": {"status": "LIVE", "risk_frac": 0.01, "heat_earned": 0.01}}
    row.update(kw)
    return row


def _v(row, *, banned=frozenset({"discovered"}), cost=MEASURED, budget=None):
    return mp.verdict(row, banned=banned, cost=cost, budget=budget, now=NOW)


def _refused_by(v):
    return {r["invariant"] for r in v["refusals"]}


# ------------------------------------------------------------------------------ I1
def test_a_sleeve_meeting_every_invariant_is_admitted():
    v = _v(_row())
    assert v["ok"] and v["refusals"] == [] and v["first"] is None


@pytest.mark.parametrize("frac", [0.0, -0.01, None, float("nan"), float("inf"), "junk"])
def test_allocator_zero_absent_or_nonfinite_is_no_order(frac):
    v = _v(_row(risk_frac=frac))
    assert not v["ok"] and mp.ALLOCATOR_ZERO in _refused_by(v)
    assert mp.reason_of(v) == "sovereignty_allocator_zero"


def test_no_allocator_source_at_all_is_absent_and_refused():
    v = _v(_row(sized_by=None, admission={"status": "LIVE", "heat_earned": 0.01}))
    assert mp.allocator_fraction(_row(sized_by=None, admission=None))[1] == "absent"
    assert mp.ALLOCATOR_ZERO in _refused_by(v)


def test_the_rows_own_risk_frac_is_not_the_allocators_number():
    """The 31 UNMEASURED rows carry risk_frac 0.005882 beside admission.risk_frac 0.0."""
    row = _row(sized_by=None, risk_frac=0.005882,
               admission={"status": "UNMEASURED", "risk_frac": 0.0})
    assert mp.allocator_fraction(row) == (0.0, "admission.risk_frac")
    assert mp.ALLOCATOR_ZERO in _refused_by(_v(row))


@pytest.mark.parametrize("frac", [0.0, None, float("nan"), -1.0, "junk"])
def test_the_sizers_return_no_lot_for_a_zero_fraction(frac):
    assert dc.promoted_lot(10_000.0, 0, 0.005, "EURUSD", None, frac, None, from_book=True) == 0.0
    lot, basis = dc.gold_book_lot(10_000.0, 19.1, None, frac)
    assert lot == 0.0 and basis.startswith("no order")


def test_an_explicit_zero_off_the_book_is_no_lot_but_absent_keeps_its_default():
    assert dc.promoted_lot(10_000.0, 0, 0.005, "EURUSD", None, 0.0) == 0.0
    assert dc.promoted_lot(10_000.0, 0, 0.005, "EURUSD", None, None) >= dc.min_lot()


def test_the_floors_still_bind_above_zero():
    """Aggressiveness is untouched: any fraction > 0 still reaches the venue minimum and gold's
    0.02 floor."""
    assert dc.promoted_lot(10_000.0, 0, 5.0, "EURUSD", None, 1e-6, None,
                           from_book=True) >= dc.venue_min_lot("EURUSD")
    lot, _ = dc.gold_book_lot(10_000.0, 19.1, None, 1e-6)
    assert lot >= dc.gold_min_lot()


# ------------------------------------------------------------------------------ I2 / I5
@pytest.mark.parametrize("adm", [{"status": "UNMEASURED", "risk_frac": 0.01}, None, {}])
def test_an_unmeasured_or_absent_admission_is_shadow(adm):
    v = _v(_row(admission=adm))
    assert mp.ADMISSION_UNMEASURED in _refused_by(v)


def test_a_canonical_gold_window_is_admitted_by_the_allocators_book():
    gw = {"name": "gold_asia", "symbol": "XAUUSD", "origin": mp.GOLD_WINDOW_ORIGIN,
          "sized_by": "allocator_book", "risk_frac": 0.02}
    assert _v(gw)["ok"]
    assert mp.ALLOCATOR_ZERO in _refused_by(_v(dict(gw, sized_by=None)))


def test_a_live_admission_without_a_marginal_reading_is_shadow():
    v = _v(_row(admission={"status": "LIVE", "risk_frac": 0.01}))
    assert _refused_by(v) == {mp.MARGINAL_UNMEASURED}
    ok = _v(_row(admission={"status": "LIVE", "risk_frac": 0.01, "delta_elogw_per_day": 1e-5}))
    assert ok["ok"]


# ------------------------------------------------------------------------------ I3
def test_a_banned_family_is_refused_case_insensitively():
    assert mp.BANNED_FAMILY in _refused_by(_v(_row(family="Discovered")))


def test_an_unreadable_ban_list_fails_closed():
    assert mp.BANNED_FAMILY in _refused_by(_v(_row(), banned=None))


def test_the_ban_list_is_read_from_the_declared_sources(tmp_path):
    fam = tmp_path / "banned_families.json"
    fam.write_text(json.dumps({"banned": {"some_new_family": {"why": "test"}}}), "utf-8")
    banned, why = mp.banned_families(family_file=fam, policy_file=tmp_path / "absent.json")
    from research.family_policy import PERMANENT
    assert "some_new_family" in banned and set(PERMANENT) <= banned
    assert "research/family_policy" in why and "mt5desk/live_policy" in why


def test_the_module_restates_no_ban():
    """S5, directly: no string constant outside a docstring names a banned family."""
    tree = ast.parse((DESK / "mt5desk" / "money_path.py").read_text("utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr)}
    lits = {n.value.lower() for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs}
    banned, _ = mp.banned_families()
    assert not (lits & set(banned))


# ------------------------------------------------------------------------------ I4
def _surface(spread_status="PRIOR", basis="cost_surface.json session median of hourly p50"):
    prior = {"status": spread_status, "value": 1.0, "basis": basis} \
        if spread_status == "PRIOR" else {"status": cs.UNMEASURED}
    return {"levels": {}, "size_bucket_edges_lots": [], "vol_bucket_edges_frac": [],
            "priors": {"EURUSD": {s: prior for s in ("asia", "london", "ny", "late")}}}


def test_cost_is_decided_by_cost_for_and_the_tape_prior_counts():
    got = mp.cost_basis("EURUSD", "asia", surface=_surface())
    assert got["status"] == mp.MEASURED and got["source"] == "cost_for:prior(tape)"
    assert mp.check_cost(got) is None


def test_the_pooled_registry_fallback_is_not_a_measurement():
    s = _surface(basis="universe.json pooled median_spread_pts (no measured hour this session)")
    got = mp.cost_basis("EURUSD", "asia", surface=s)
    assert got["status"] == mp.UNMEASURED
    assert mp.COST_UNMEASURED in _refused_by(_v(_row(), cost=got))


def test_a_measured_fill_cell_counts(monkeypatch):
    def fake_cost_for(sym, **kw):
        return {"terms": {"spread_points": {"status": cs.MEASURED, "level": "instrument",
                                            "n": 5, "value": 2.0}}}
    monkeypatch.setattr(cs, "cost_for", fake_cost_for)
    got = mp.cost_basis("EURUSD", "asia", surface={"levels": {}})
    assert got["status"] == mp.MEASURED and got["source"] == "cost_for:instrument"


@pytest.mark.parametrize("surface", [None, {}])
def test_no_surface_is_unmeasured(surface):
    assert mp.cost_basis("EURUSD", "asia", surface=surface)["status"] == mp.UNMEASURED
    assert mp.COST_UNMEASURED in _refused_by(_v(_row(), cost=None))


def test_an_absent_artifact_is_built_from_the_committed_inputs(tmp_path):
    surface, source = mp.load_cost_surface(tmp_path)
    assert "build()" in source and "levels" in surface


def test_the_artifact_validator_now_finds_a_measured_basis():
    """The producer bug: artifact.ok was false on all 40 LIVE rows because the promoter looks
    for cost_hash/cost_r on the SLEEVE row, which no row carries. The validator now resolves the
    instrument's measured cost itself."""
    from libs.research import strategy_artifact as sa
    a = sa.StrategyArtifact(
        strategy_id="x", mechanism="m", source="forward_clock", family="carry", params={},
        symbols=["CHFNOK"], timeframes=["H1"], entry={}, exit={}, execution={},
        state_conditioning={}, data_requirements=[], feature_ids=[],
        cost_assumptions={"cost_hash": None, "cost_r": None},
        validation_certificate={"status": "PASS"})
    v = sa.validate(a)
    assert v["ok"] and v["cost_basis"]["status"] == "MEASURED"
    a.symbols = ["NOPE_NOT_A_SYMBOL"]
    assert "no cost basis" in sa.validate(a)["problems"]


# ------------------------------------------------------------------------------ I6
def _budget(**kw):
    doc = {"at": (NOW - timedelta(hours=1)).isoformat(),
           "budget": {"declared_max_heat": 0.02, "status": "WITHIN"},
           "sleeves": [{"sleeve": "s1"}]}
    doc.update(kw)
    return doc


def test_an_override_inside_a_declared_budget_may_trade():
    assert _v(_row(principal_override={"by": "p"}), budget=_budget())["ok"]


@pytest.mark.parametrize("budget", [
    None,
    {},
    _budget(budget={"declared_max_heat": None, "status": "UNDECLARED"}),
    _budget(budget={"declared_max_heat": 0.02, "status": "OVER"}),
    _budget(sleeves=[{"sleeve": "someone_else"}]),
    _budget(at=(NOW - timedelta(hours=30)).isoformat()),
])
def test_an_override_outside_the_budget_may_not(budget):
    v = _v(_row(principal_override={"by": "p"}), budget=budget)
    assert _refused_by(v) == {mp.OVERRIDE_OUTSIDE_BUDGET}


def test_a_non_override_row_ignores_the_budget():
    assert _v(_row(), budget=None)["ok"]


# ------------------------------------------------------------------------------ ledgers
def test_every_refusal_gets_an_unmeasured_missed_growth_line_deduped_per_day(tmp_path):
    v = _v(_row(risk_frac=0.0, family="discovered"))
    lines = mp.missed_growth_line(v, sleeve="s1", symbol="EURUSD", day="2026-09-30",
                                  at="t", lane="family_market")
    assert {ln["rail"] for ln in lines} == {"money_path_sovereignty.allocator_zero",
                                            "money_path_sovereignty.banned_family"}
    assert all(ln["value"] is None and ln["status"] == mp.UNMEASURED for ln in lines)
    p = tmp_path / "missed_growth.jsonl"
    assert mp.append_missed_growth(lines, p) == 2
    assert mp.append_missed_growth(lines, p) == 0
    summary = mg.sovereignty_refusals([json.loads(x) for x in p.read_text().splitlines()])
    assert summary["allocator_zero"]["sleeve_days"] == 1
    assert summary["allocator_zero"]["verdict"] == mg.UNMEASURED


# ------------------------------------------------------------------------------ committed data
def test_on_the_committed_registry_no_banned_or_unmeasured_row_is_tradable():
    rows = json.loads((DESK / "data" / "sleeves.json").read_text("utf-8"))["sleeves"]
    banned, _ = mp.banned_families()
    surface, _ = mp.load_cost_surface()
    rep = mp.measure_registry(rows, banned=banned, surface=surface,
                              budget=mp.load_experimental_budget())
    by = {r["name"]: r for r in rep["rows"]}
    live = [r for r in rows if r.get("status") == "LIVE"]
    for r in live:
        got = by[r["name"]]
        if str(r.get("family") or "").lower() in banned:
            assert not got["ok"]
        if mp.admission_status(r) in mp.UNMEASURED_ADMISSIONS:
            assert not got["ok"]
    assert rep["tradable_under_invariants"] <= rep["live"]


# ------------------------------------------------------------------------------ identity tag
def test_the_tagged_comment_format_is_exact():
    """THE ONE PIN ON THE COMMENT FORMAT: 16 characters of DW<name>, '#', 12 hex = 29, the
    terminal's measured comment bound (gateway.COMMENT_MAX)."""
    c = dc.tagged_comment("gold_london_am", "0123456789ab")
    assert c == "DWgold_london_am#0123456789ab" and len(c) == 29
    long = dc.tagged_comment("chfnok_carry_asia_p_98d776f3e210d3e2", "0123456789ab")
    assert long == "DWchfnok_carry_a#0123456789ab" and len(long) == 29
    assert dc.comment_tag(long) == ("DWchfnok_carry_a", "0123456789ab")
    assert dc.comment_tag("DWgold_asia") is None and dc.comment_tag("[sl 4300.1]") is None


def test_the_order_identity_is_content_addressed():
    s = {"name": "gold_asia", "window": "asia", "sized_by": "allocator_book", "risk_frac": 0.02}
    a = dc.order_identity(s, symbol="XAUUSD", order={"lot": 0.02}, at="t")
    b = dc.order_identity(s, symbol="XAUUSD", order={"lot": 0.02}, at="t")
    c = dc.order_identity(s, symbol="XAUUSD", order={"lot": 0.03}, at="t")
    assert a["head"] == b["head"] and a["head"] != c["head"]
    assert len(a["tag"]) == 12 and a["tag"] == a["head"][:12]
    assert a["kinds"] == ["hypothesis", "certificate", "sleeve", "allocation", "order"]


def test_a_tagged_deal_is_still_its_sleeves_witness():
    deal = SimpleNamespace(entry=0, comment="DWeurgbp_overnig#0123456789ab", time=0, ticket=7)
    legacy = "DWeurgbp_overnight_gap_decay_a"[:29]
    assert dc.bar_already_traded([deal], legacy) is None
    assert dc.bar_already_traded([deal], legacy, canon=lambda c: legacy) == (
        7, "1970-01-01T00:00:00+00:00")


# ------------------------------------------------------------------------------ the fence
def test_the_fence_passes_on_this_tree():
    rep = fence.run()
    assert rep["ok"], rep["findings"]
    assert {s.split(":")[0] for s in rep["new_risk_sites"]} >= fence.KNOWN_SITES


_BAD = '''
def place_bracket(st):
    money_path_guard(st, {}, lane="x")
    mt5.order_send({"action": mt5.TRADE_ACTION_PENDING, "comment": _ident["comment"]})

def run_family_sleeves(st):
    mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "comment": _ident["comment"]})

def run_scalp_sleeves(st):
    money_path_guard(st, {}, lane="x")
    mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "comment": order_comment(name)})

def close_it(p):
    mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "position": p.ticket})

def main(st):
    place_bracket(st)
'''


def test_the_fence_catches_an_unguarded_site_an_untagged_order_and_an_unguarded_caller():
    checks = {f["check"]: f["why"] for f in fence.check_sites(_BAD)}
    assert "S1_UNGUARDED_PLACEMENT" in checks and "run_family_sleeves" in checks[
        "S1_UNGUARDED_PLACEMENT"]
    assert "S7_IDENTITY_TAG" in checks and "run_scalp_sleeves" in checks["S7_IDENTITY_TAG"]
    assert "S2_UNGUARDED_CALLER" in checks
    assert "S6_REFUSAL_ROWS" in checks        # no money_path_guard definition at all
    closes = [s for s in fence.placement_sites(_BAD) if s["function"] == "close_it"]
    assert closes and closes[0]["new_risk"] is False, "a position close is never gated"


def test_the_fence_is_on_the_law_gate():
    src = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_money_path_sovereignty.py", ())' in src
