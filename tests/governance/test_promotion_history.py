"""L1.30 append-only promotion history -- births become countable without becoming inventable.

Every test here is a phantom-birth trap. The fence this feeds sets the desk's read on whether the
pipeline outruns decay, so the failure that matters is not "no number" (which the fence already
handles honestly) but "a number that looks measured and is not".
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_replacement_rate import build_report

from libs.research.promotion_history import DECLARED, OBSERVED, UNKNOWN, update

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def _slot(name, kind="standing", started=None):
    return {"name": name, "kind": kind, "started": started, "source": f"data/{name}.json"}


# --- the writer -------------------------------------------------------------------------------

def test_bootstrap_never_stamps_today_on_an_undatable_clock():
    """THE BUG THIS MODULE EXISTS FOR. A watcher that starts today must not report twelve births
    today. Clocks already running with no declared start are UNKNOWN, not born-now."""
    hist, s = update([_slot("a"), _slot("b")], complete=True, now=NOW, previous=None)
    assert [r["provenance"] for r in hist] == [UNKNOWN, UNKNOWN]
    assert all(r["promoted_at"] is None for r in hist)
    assert s["born_this_run"] == [] and s["undated_rows"] == 2
    assert s["bootstrap"] is True


def test_a_declared_start_is_used_even_at_bootstrap():
    hist, s = update([_slot("a", started="2026-06-21T00:00:00+00:00")],
                     complete=True, now=NOW, previous=None)
    assert hist[0]["provenance"] == DECLARED
    assert hist[0]["promoted_at"].startswith("2026-06-21")
    assert s["born_this_run"] == ["a"] and s["undated_rows"] == 0


def test_a_clock_appearing_after_bootstrap_is_a_dated_birth():
    hist, _ = update([_slot("a")], complete=True, now=NOW, previous=None)
    hist, s = update([_slot("a"), _slot("b")], complete=True, now=NOW, previous=hist)
    row_b = next(r for r in hist if r["edge"] == "b")
    assert row_b["provenance"] == OBSERVED and row_b["promoted_at"] == NOW.isoformat()
    assert s["born_this_run"] == ["b"]


def test_history_is_append_only_and_reruns_do_not_duplicate():
    hist, _ = update([_slot("a"), _slot("b")], complete=True, now=NOW, previous=None)
    for _ in range(3):
        hist, s = update([_slot("a"), _slot("b")], complete=True, now=NOW, previous=hist)
    assert len(hist) == 2 and s["born_this_run"] == []


def test_disappearance_retires_only_on_a_complete_read():
    """An unreadable source shrinks the derived slot list. Retiring on that books a false death
    AND -- worse -- a false birth when the file comes back. Flapping storage would then read as a
    healthy pipeline."""
    hist, _ = update([_slot("a"), _slot("b")], complete=True, now=NOW, previous=None)
    hist, s = update([_slot("a")], complete=False, now=NOW, previous=hist)
    assert s["retired_this_run"] == [] and s["retirement_checked"] is False
    assert all(r["retired_at"] is None for r in hist)

    hist, s = update([_slot("a")], complete=True, now=NOW, previous=hist)
    assert s["retired_this_run"] == ["b"]
    assert next(r for r in hist if r["edge"] == "b")["retired_at"] == NOW.isoformat()


def test_a_restarted_clock_is_a_new_row_not_a_rewritten_one():
    hist, _ = update([_slot("a")], complete=True, now=NOW, previous=None)
    hist, _ = update([], complete=True, now=NOW, previous=hist)              # retired
    later = NOW + timedelta(days=3)
    hist, s = update([_slot("a")], complete=True, now=later, previous=hist)
    assert len(hist) == 2                                    # the retired row is never rewritten
    assert hist[0]["retired_at"] == NOW.isoformat()
    assert hist[1]["promoted_at"] == later.isoformat() and s["born_this_run"] == ["a"]


# --- the fence that reads it ------------------------------------------------------------------

def _seed(root: Path, *, graveyard: list[str], history) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "docs/graveyard.md").write_text("\n".join(graveyard) or "# empty", "utf-8")
    q = {"slots": {"occupied": 3, "cap": 12}}
    if history is not None:
        q["promotion_history"] = history
    (root / "data/promotion_queue.json").write_text(json.dumps(q), "utf-8")


def test_undated_rows_make_births_a_floor_and_block_a_dying_verdict(tmp_path):
    """A lower bound BELOW deaths is consistent with both DYING and OK, so neither may be
    published. This is the phantom-key births=0 defect pointed the other way."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    _seed(tmp_path,
          graveyard=[f"### edge_{i} -- KILLED {today}" for i in range(3)],
          history=[{"edge": "a", "promoted_at": today, "provenance": "DECLARED"},
                   {"edge": "b", "promoted_at": None, "provenance": "UNKNOWN"}])
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED-BIRTHS"        # NOT DYING -- the bound could flip it
    assert rep["births"] == 1 and rep["births_are_lower_bound"] is True
    assert rep["births_undated"] == 1


def test_a_floor_at_or_above_deaths_still_reads_ok(tmp_path):
    """When the LOWER bound already clears deaths, the undated rows cannot change the verdict."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    _seed(tmp_path,
          graveyard=[f"### edge_0 -- KILLED {today}"],
          history=[{"edge": "a", "promoted_at": today}, {"edge": "b", "promoted_at": today},
                   {"edge": "c", "promoted_at": None}])
    rep = build_report(tmp_path)
    assert rep["status"] == "OK" and rep["births"] == 2 and rep["births_are_lower_bound"] is True


def test_retired_clocks_count_as_deaths_and_dedupe_against_the_graveyard(tmp_path):
    """Counting only the graveyard UNDERSTATES deaths, which OVERSTATES the replacement rate --
    the complacent direction. A clock both retired and graveyarded still dies exactly once."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    _seed(tmp_path,
          graveyard=[f"### alpha_one -- KILLED {today}"],
          history=[{"edge": "alpha_one", "promoted_at": today, "retired_at": today},
                   {"edge": "beta_two", "promoted_at": today, "retired_at": today}])
    rep = build_report(tmp_path)
    assert rep["deaths_graveyard"] == 1
    assert rep["deaths_retired_clocks"] == 1            # beta_two only; alpha_one is deduped
    assert rep["deaths"] == 2


def test_absent_history_still_reports_uncountable(tmp_path):
    """The pre-existing contract is unchanged: no history at all is UNMEASURED-BIRTHS, never 0."""
    _seed(tmp_path, graveyard=["### x -- KILLED 2026-08-01"], history=None)
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED-BIRTHS" and rep["births_measured"] is False


def test_writer_and_fence_agree_on_the_field_names():
    """A writer and a reader that disagree on a key produce a silent zero -- the READ-WITHOUT-
    WRITER class. Pin the contract in a test so a rename breaks here and not in production."""
    hist, _ = update([_slot("a", started="2026-07-01T00:00:00+00:00")],
                     complete=True, now=NOW, previous=None)
    fence = Path("scripts/check_replacement_rate.py").read_text("utf-8")
    for key in ("promotion_history", "promoted_at", "retired_at", "edge"):
        assert key in fence, f"fence does not read `{key}`"
        if key != "promotion_history":
            assert key in hist[0], f"writer does not emit `{key}`"
