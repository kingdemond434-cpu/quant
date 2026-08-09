"""R0213 -- "surpass me" is only an instruction if something measures it."""
from __future__ import annotations

import json

from scripts.run_principal_benchmark import (
    MIN_FOR_VERDICT,
    PRINCIPAL_RISK,
    build_report,
    growth_at,
    net_r_per_trade,
)


def _book(tmp_path, wins, losses, *, f=0.06, win_r=2.756, loss_r=-1.244):
    marks = ([{"closed": True, "sizing": {"risk_fraction": f}, "equity_return": win_r * f}] * wins
             + [{"closed": True, "sizing": {"risk_fraction": f}, "equity_return": loss_r * f}]
             * losses)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps({"marks": marks}), "utf-8")
    return marks


def test_net_r_is_recovered_size_independently(tmp_path):
    """Cost in R is size-independent, so dividing the realised return by the risk fraction that
    produced it removes size exactly -- which is what makes re-pricing at another size arithmetic
    rather than a second model."""
    _book(tmp_path, 1, 0, f=0.06)
    a = net_r_per_trade(json.loads((tmp_path / "data/paper_book_pnl.json").read_text())["marks"])
    _book(tmp_path, 1, 0, f=0.12)
    b = net_r_per_trade(json.loads((tmp_path / "data/paper_book_pnl.json").read_text())["marks"])
    assert a == b            # same trade, different size, identical net R


def test_the_verdict_is_not_foregone_and_flips_at_the_crossover():
    """The whole reason this is worth computing: below the crossover the desk's cap earns its
    keep, above it the principal's size wins and the cap is costing growth."""
    thin = [2.756] * 8 + [-1.244] * 16                    # ~33% hit
    assert growth_at(thin, 0.06)["g_per_trade"] > growth_at(thin, PRINCIPAL_RISK)["g_per_trade"]
    rich = [2.756] * 11 + [-1.244] * 13                   # ~46% hit
    assert growth_at(rich, 0.06)["g_per_trade"] < growth_at(rich, PRINCIPAL_RISK)["g_per_trade"]


def test_ruin_is_reported_never_computed_around():
    """Dropping the trade that ended the sequence is how a backtest hides a blow-up."""
    out = growth_at([-9.0] + [1.0] * 20, 0.12)
    assert out["state"] == "RUIN" and out["n_ruinous"] == 1
    assert "hides a blow-up" in out["why"]


def test_a_thin_record_reports_unmeasured_never_a_lead(tmp_path):
    """His record is ONE trade; an early claim here would be two small samples flattering each
    other."""
    _book(tmp_path, 3, 5)
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED"
    assert rep["verdict"]["need"] == MIN_FOR_VERDICT
    assert "must not read as a lead" in rep["verdict"]["why"]


def test_a_full_record_produces_a_directional_verdict(tmp_path):
    _book(tmp_path, 8, 16)                                 # 24 closed, thin hit rate
    rep = build_report(tmp_path)
    assert rep["status"] == "AHEAD"                        # the cap beats his size at this rate
    assert rep["verdict"]["edge_per_trade"] > 0
    assert rep["desk"]["state"] == "MEASURED" and rep["principal"]["state"] == "MEASURED"


def test_the_scope_limit_is_stated_in_the_artifact(tmp_path):
    """The comparison is seductive and it is NOT a claim about who picks better -- his selection
    is unmeasured. Saying so in the output is what stops the next reader over-reading it."""
    _book(tmp_path, 8, 16)
    rep = build_report(tmp_path)
    assert "does NOT show the machine beats the principal" in rep["scope_limit"]
    assert "selection is unmeasured" in rep["scope_limit"].replace("his SELECTION", "selection")
    # and the honest ledger of both sides is carried, not just the flattering half
    assert rep["where_the_human_still_wins"] and rep["where_the_machine_should_win"]
