"""The conversion maximiser fits inside its cap, resumes where it stopped, and writes first.

Noon CRO 2026-09-30: the leg "times out every pass and moves 0 artifacts"; its carry was last
written a week earlier. These pin the four causes: a status write that scanned the table, a lock
wait that could outlive the pass, a tail that ran after the budget, and nothing written until the
very end -- plus the cursor that stops each pass re-reading the head the last one already worked.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_DESK = _TESTS.parent
for _p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research"), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conversion_maximiser as cm  # noqa: E402
from test_conversion_maximiser import _plant, _run, desk  # noqa: E402,F401  (shared fixture)

from libs.moat import registry as R  # noqa: E402


def test_a_status_write_searches_and_never_scans(desk) -> None:  # noqa: F811
    plan = desk["conn"].execute(
        "EXPLAIN QUERY PLAN UPDATE research_candidates SET status='x' "
        "WHERE id=? OR donated_cell=?", ("a", "a")).fetchall()
    text = " ".join(str(r[3]) for r in plan)
    assert "SCAN research_candidates" not in text, text
    assert "ix_candidates_donated_cell" in text


def test_the_budget_never_outlives_the_cycle_cap() -> None:
    assert cm.effective_budget_s(900, {}) == 900
    assert cm.effective_budget_s(900, {"QUANT_LEG_BUDGET_S": "1035"}) == 900
    assert cm.effective_budget_s(900, {"QUANT_LEG_BUDGET_S": "600"}) == 465
    assert cm.effective_budget_s(900, {"QUANT_LEG_BUDGET_S": "junk"}) == 900


def test_the_lock_is_never_waited_for_past_the_end_of_the_pass(desk) -> None:  # noqa: F811
    ms = cm._bound_lock_window(desk["conn"], cm.Budget(5.0))
    assert ms is not None and ms <= 5_000
    assert cm._bound_lock_window(desk["conn"], cm.Budget(10_000.0)) == cm.LOCK_WAIT_MS


def test_the_tail_is_skipped_by_name_when_the_budget_is_spent(desk) -> None:  # noqa: F811
    for i in range(3):
        _plant(desk["conn"], f"c_t{i}", family="range_reversion", symbol="TESTFX",
               mechanism="mean reversion after an overnight gap")
    t0 = time.monotonic()
    out = _run(desk, budget_s=0.01)
    assert time.monotonic() - t0 < 30.0
    tail = out["bounds"]["tail_stages_s"]
    assert tail and set(tail.values()) == {"SKIPPED_BUDGET"}
    assert out["judged_vs_docket"]["status"] == "SKIPPED_BUDGET"
    assert out["debt_after"]["total_debt"] is None, "a skipped count is a gap, never a zero"


def test_the_next_pass_resumes_after_the_cursor(desk) -> None:  # noqa: F811
    for i in range(10):
        _plant(desk["conn"], f"c_k{i:02d}", family="", symbol="",
               mechanism="something nobody has named yet and no instrument is given")
    carry = desk["root"] / "carry.json"
    first = _run(desk, max_rows=4, carry_path=carry)
    cursor = json.loads(carry.read_text(encoding="utf-8"))["cursor"]
    assert cursor["untestable"] or cursor["donated"], cursor
    second = _run(desk, max_rows=4, carry_path=carry)
    one = {e["id"] for e in first["still_blocked_rows"]}
    two = {e["id"] for e in second["still_blocked_rows"]}
    assert one and two and not one & two, "a stuck row is revisited once a lap, not every pass"


def test_the_cursor_wraps_to_the_oldest_row_and_counts_the_lap(desk) -> None:  # noqa: F811
    for i in range(3):
        _plant(desk["conn"], f"c_w{i}", family="", symbol="", mechanism="unnamed thing")
    cur = cm._Cursor(desk["conn"], pool=30, state={"donated": ("9999", "z")})
    rows = cur.draw(set())
    assert len(rows) == 3
    assert cur.laps.get("donated") == 1


def test_an_identical_disposition_is_not_rewritten(desk) -> None:  # noqa: F811
    cid = _plant(desk["conn"], "c_same", family="", symbol="", mechanism="unnamed")
    reason = "PROSE_ONLY (owner: o): d"
    desk["conn"].execute("UPDATE research_candidates SET status='queued', failure_class=?, "
                         "rejection_reason=?, updated_at='frozen' WHERE id=?",
                         ("PROSE_ONLY", reason, cid))
    desk["conn"].commit()
    row = dict(desk["conn"].execute("SELECT * FROM research_candidates WHERE id=?",
                                    (cid,)).fetchone())
    assert cm._keep_queued(desk["conn"], cid, "PROSE_ONLY", "o", "d", current=row)
    after = desk["conn"].execute("SELECT updated_at FROM research_candidates WHERE id=?",
                                 (cid,)).fetchone()[0]
    assert after == "frozen"


def test_the_pass_checkpoints_and_a_checkpoint_is_not_a_trend(
        desk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    out = tmp_path / "CONVERSION_MAXIMISER.json"
    out.write_text(json.dumps({"generated_utc": "t0", "debt_after": {"total_debt": 7}}),
                   encoding="utf-8")
    seen: list[str] = []
    real = cm._checkpoint

    def spy(path: Path, stage: str, prior: dict, body: dict) -> None:
        seen.append(stage)
        real(path, stage, prior, body)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        assert doc["pass_status"] == stage
        assert cm.previous_pass(Path(path)) == {"at": "t0", "debt_after": 7}

    monkeypatch.setattr(cm, "_checkpoint", spy)
    _run(desk, out_path=out)
    assert seen == [cm.STAGE_RUNNING, cm.STAGE_CONVERTED]


def test_the_indexes_the_cursor_walks_are_used(desk) -> None:  # noqa: F811
    built = cm._ensure_cursor_indexes(desk["conn"])
    assert set(built.values()) == {"present"}, built
    for pop in cm.DEBT_POPULATIONS:
        sql, args = cm.page_sql(pop, ("2026-09-01", "x"), 5, indexed=True)
        plan = " ".join(str(r[3]) for r in desk["conn"].execute(f"EXPLAIN QUERY PLAN {sql}",
                                                                  args))
        assert f"SEARCH research_candidates USING INDEX ix_cvm_{pop}" in plan, plan
    assert R.path().exists()


def test_every_repaired_row_is_charged_and_the_charge_fits_the_budget(monkeypatch) -> None:
    recs = [{"id": f"r{i}", "family": "f1" if i % 2 else "f2", "params": {"i": i},
             "symbol": "TESTFX"} for i in range(60)]
    full = cm._charge_trials(recs, None, dry_run=True)
    assert full["families_priced"] == 2 and full["families_charged_raw"] == 0
    assert full["n_raw"] == 60 and 0 < full["n_effective"] <= 60
    monkeypatch.setattr(cm, "CHARGE_FAMILY_S", 10_000.0)
    coarse = cm._charge_trials(recs, None, dry_run=True, budget=cm.Budget(60.0))
    assert coarse["families_priced_coarse"] == 2
    none_left = cm._charge_trials(recs, None, dry_run=True, budget=cm.Budget(0.001))
    assert none_left["families_charged_raw"] == 2
    assert none_left["n_effective"] == 60.0, "an unpriced family is charged raw, never short"
