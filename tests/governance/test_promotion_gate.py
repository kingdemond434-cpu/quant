"""R0147 promotion gate -- what evidence buys what expansion, fixed before the evidence exists.

The kill condition gave the sleeve a defined way to DIE. Without this it had no defined way to
GROW, which makes expansion an improvised decision taken in the mood of a good week -- and a week
of wins is the exact moment that decision is worst.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.check_promotion_gate import _RUNGS, BREAKEVEN_HIT, evaluate


def _book(tmp_path, *, n, days, hit=0.40, beats=True, mdd=0.10):
    (tmp_path / "data").mkdir(exist_ok=True)
    start = datetime.now(tz=UTC) - timedelta(days=days)
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps({
        "n_resolved": n, "win_rate": hit, "beats_buy_and_hold": beats,
        "sleeve_return": 0.4, "buy_and_hold_return": 0.1,
        "equity": {"max_drawdown": mdd},
        "marks": [{"exit_at": start.isoformat()}]}))
    (tmp_path / "data/mechanism_attribution.json").write_text(json.dumps({"status": "ATTRIBUTED"}))
    (tmp_path / "data/calibration_probe.json").write_text(json.dumps(
        {"verdict": {"state": "INFORMATIVE"}}))
    (tmp_path / "data/sleeve_allocation.json").write_text(json.dumps({"status": "DIVERSIFIED"}))


def test_nothing_measured_grants_only_paper(tmp_path):
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 0 and "PAPER" in rep["granted"]


def test_a_great_week_does_not_buy_live_money(tmp_path):
    # THE TRAP THIS CLOSES: 50 trades in 7 days is ONE REGIME. Cadence can manufacture sample size
    # but never calendar time, so a blazing week grants rung 1 at most -- and that is still paper.
    _book(tmp_path, n=60, days=7)
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 0
    assert any("calendar days" in str(u) for u in rep["ladder"][0]["unmet"])


def test_two_weeks_of_good_evidence_buys_size_but_not_live(tmp_path):
    _book(tmp_path, n=60, days=15)
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 1
    assert "PAPER" in rep["granted"] and "half-Kelly" in rep["granted"]


def test_the_first_live_rung_is_deliberately_tiny(tmp_path):
    _book(tmp_path, n=120, days=31)
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 2
    assert "1% of book" in rep["granted"] and "tuition" in rep["granted"]


def test_a_rung_cannot_be_skipped_on_trade_count_alone(tmp_path):
    # Meeting rung 3's counts while failing rung 2's benchmark grants the EARLIER rung.
    _book(tmp_path, n=500, days=200, beats=False)
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 1                 # hit rate + attribution pass, benchmark fails
    assert "ladder, not a maximum" in rep["no_skipping"]


def test_a_hit_rate_below_breakeven_blocks_everything(tmp_path):
    _book(tmp_path, n=500, days=200, hit=BREAKEVEN_HIT - 0.02)
    assert evaluate(tmp_path)["granted_rung"] == 0


def test_an_unmeasurable_criterion_blocks_rather_than_passes(tmp_path):
    # A promotion granted by a broken reader is the worst possible failure of this organ.
    _book(tmp_path, n=500, days=200)
    (tmp_path / "data/mechanism_attribution.json").write_text("{ corrupt")
    rep = evaluate(tmp_path)
    assert rep["criteria"]["attribution_clean"]["state"] == "UNMEASURED"
    assert rep["granted_rung"] == 0


def test_the_top_rung_is_capped_and_needs_two_regimes(tmp_path):
    _book(tmp_path, n=999, days=999)
    rep = evaluate(tmp_path)
    assert rep["granted_rung"] == 3                 # two_regimes is UNMEASURED by design
    assert "15% of book" in _RUNGS[3]["grants"] and "ceiling" in _RUNGS[3]["grants"]
