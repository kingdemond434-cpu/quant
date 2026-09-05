"""L1.43 -- "has it EVER fired" is absorbing; these pin the decay that makes it falsifiable.

THE DEFECT THESE EXIST FOR, measured 2026-08-19 over the 16 registered fences: 10 had already
become permanently incapable of ever reading QUIET again, because a firing verdict entering a
deduplicated set never leaves it. Every test here fails if the dating is removed and the census
goes back to a set of strings.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from libs.ops.fence_history import QUIET_AFTER_RUNS, History, load


def _legacy(tmp_path, seen):
    p = tmp_path / "fence_yield_history.json"
    p.write_text(json.dumps({"seen": seen, "updated": "2026-08-19T20:06:15+00:00"}), "utf-8")
    return p


def test_the_absorbing_bug_is_gone_a_fence_that_stops_firing_reads_stale():
    """THE WHOLE POINT. Under the v1 set-of-strings this fence read FIRED forever."""
    h = History()
    h.bump()
    h.record("conversion", "REPAIR-MODE")
    assert h.recency("conversion", ("REPAIR-MODE",))["state"] == "FIRED-RECENTLY"
    for _ in range(QUIET_AFTER_RUNS + 1):       # it keeps running and only ever says OK
        h.bump()
        h.record("conversion", "OK")
    rec = h.recency("conversion", ("REPAIR-MODE",))
    assert rec["state"] == "FIRED-STALE", "a fence silent past the window must not read recent"
    assert rec["runs_since"] == QUIET_AFTER_RUNS + 1
    assert "REPAIR-MODE" in rec["fired_verdicts"]        # the catch is not forgotten, only dated


def test_the_legacy_migration_never_fabricates_a_date(tmp_path):
    """L1.28a -- the migration must not read as "every fence fired today" on the day it ships.

    Stamping `now` onto carried-over verdicts would have converted a fourteen-day blind spot
    into a fabricated clean bill of health, which is strictly worse than the bug it replaced.
    """
    h = load(_legacy(tmp_path, {"law_families": ["FAILING", "OK"]}))
    assert h.source == "LEGACY"
    rec = h.recency("law_families", ("FAILING",))
    assert rec["state"] == "FIRED-UNDATED"
    assert rec["runs_since"] is None and rec["days_since"] is None and rec["last"] is None
    assert rec["state"] != "FIRED-RECENTLY", "an undated firing must never read as recent"
    assert rec["state"] != "FIRED-STALE", "nor as an unearned accusation"


def test_an_undated_firing_self_heals_on_the_next_live_observation(tmp_path):
    h = load(_legacy(tmp_path, {"law_families": ["FAILING"]}))
    assert h.recency("law_families", ("FAILING",))["state"] == "FIRED-UNDATED"
    h.bump()
    h.record("law_families", "FAILING")
    assert h.recency("law_families", ("FAILING",))["state"] == "FIRED-RECENTLY"


def test_seeded_evidence_is_undated_because_it_proves_a_catch_not_a_cadence():
    h = History()
    h.bump()
    h.seed("law_families", "FAILING")
    rec = h.recency("law_families", ("FAILING",))
    assert rec["state"] == "FIRED-UNDATED", "a 2026-07-31 commit-record catch is not recent yield"


def test_unreadable_history_is_distinct_from_absent(tmp_path):
    """L1.55 -- one means no census ever ran, the other means one ran and wrote garbage."""
    assert load(tmp_path / "nope.json").source == "NEW"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    h = load(bad)
    assert h.source == "UNREADABLE"
    # and it must NOT resolve to a clean answer for any fence
    assert h.recency("conversion", ("REPAIR-MODE",))["state"] == "UNREADABLE"


def test_a_fence_with_no_firing_verdict_reads_never_not_quiet():
    h = History()
    h.bump()
    h.record("denominators", "PARTIAL")          # PARTIAL is deliberately NOT a catch
    assert h.recency("denominators", ("VACUOUS", "UNMEASURED"))["state"] == "NEVER"


def test_recency_reports_the_most_recent_of_several_firing_verdicts():
    h = History()
    h.bump()
    h.record("exploration", "DARK")
    for _ in range(5):
        h.bump()
        h.record("exploration", "OK")
    h.bump()
    h.record("exploration", "STALE")
    rec = h.recency("exploration", ("DARK", "STALE", "THIN"))
    assert rec["runs_since"] == 0 and "STALE" in rec["note"]
    assert sorted(rec["fired_verdicts"]) == ["DARK", "STALE"]


def test_a_malformed_entry_is_carried_as_undated_not_silently_dropped(tmp_path):
    """L1.60 -- a denominator member lost in silence is a coverage claim the desk cannot cash."""
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"seen": {"conversion": {"REPAIR-MODE": "not-a-dict"}}}), "utf-8")
    h = load(p)
    assert h.n_migrated == 1
    assert h.recency("conversion", ("REPAIR-MODE",))["state"] == "FIRED-UNDATED"


def test_the_window_is_denominated_in_runs_not_days():
    """L1.48 -- evidence is the clock. A cadence change must not silently redefine the window."""
    h = History()
    h.bump()
    h.record("conversion", "REPAIR-MODE",
             now=datetime.now(tz=UTC) - timedelta(days=365))
    rec = h.recency("conversion", ("REPAIR-MODE",))
    assert rec["state"] == "FIRED-RECENTLY", "one run ago is recent however long ago in wall time"
    assert rec["days_since"] is not None and rec["days_since"] > 300   # published, not keyed on


def test_a_dated_history_round_trips(tmp_path):
    h = History()
    h.bump()
    h.record("conversion", "REPAIR-MODE")
    p = tmp_path / "h.json"
    p.write_text(json.dumps(h.to_dict()), "utf-8")
    back = load(p)
    assert back.source == "DATED" and back.runs == 1
    assert back.recency("conversion", ("REPAIR-MODE",))["state"] == "FIRED-RECENTLY"
