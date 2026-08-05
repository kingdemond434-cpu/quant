"""§37 -- work owed survives an outage and is handed back, and a SKIP is told apart from a MISS.

The distinction is the whole point: a long queue looks identical whether nobody was home or
everybody walked past it. Blaming the desk for a quota outage is unfair; excusing avoidance is
expensive. Only the second is a defect."""

from __future__ import annotations

import json
import time
from pathlib import Path

from libs.ops.carryover import (
    TREADMILL_DAYS,
    brief,
    carryover_state,
    load_sweeps,
    record_sweep,
)

_DAY = 86400.0


def _ledger(tmp: Path, rows: list[tuple[list[str], float, bool]]) -> Path:
    p = tmp / "sweeps.jsonl"
    for ids, ts, alive in rows:
        record_sweep(p, ids, ts=ts, brain_alive=alive)
    return p


def _ledger_acked(
    tmp: Path, rows: list[tuple[list[str], list[str], float, bool]], *, state: str = "known"
) -> Path:
    """Ledger with the ack column populated: (owed_ids, acked_ids, ts, brain_alive)."""
    p = tmp / "sweeps_acked.jsonl"
    for ids, acked, ts, alive in rows:
        record_sweep(p, ids, ts=ts, brain_alive=alive, acked_ids=acked, ack_state=state)
    return p


class TestRecording:
    def test_round_trips(self, tmp_path: Path) -> None:
        p = _ledger(tmp_path, [(["a", "b"], 1000.0, True)])
        rows = load_sweeps(p)
        assert rows[0]["ids"] == ["a", "b"] and rows[0]["alive"] is True

    def test_ids_are_deduped_and_sorted(self, tmp_path: Path) -> None:
        p = _ledger(tmp_path, [(["b", "a", "b"], 1.0, True)])
        assert load_sweeps(p)[0]["ids"] == ["a", "b"]

    def test_corrupt_line_does_not_lose_history(self, tmp_path: Path) -> None:
        p = _ledger(tmp_path, [(["a"], 1.0, True), (["a"], 2.0, True)])
        p.write_text(p.read_text("utf-8") + "{not json\n")
        assert len(load_sweeps(p)) == 2


class TestSkipDetection:
    def test_item_seen_by_a_live_brain_twice_is_skipped(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 3 * _DAY, True),
                               (["x"], now - 2 * _DAY, True),
                               (["x"], now - _DAY, True)])
        st = carryover_state(load_sweeps(p), now=now)
        assert st.skipped_items and st.skipped_items[0].defect_id == "x"
        assert "walked past it" in st.verdict

    def test_outage_alone_is_never_a_skip(self, tmp_path: Path) -> None:
        # the brain was dead for every sweep -- accumulating is not avoidance
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 3 * _DAY, False),
                               (["x"], now - 2 * _DAY, False),
                               (["x"], now - _DAY, False)])
        st = carryover_state(load_sweeps(p), now=now)
        assert st.skipped_items == () and st.n_dead_sweeps == 3
        assert "no fault of the cycle" in st.verdict

    def test_a_single_live_sighting_is_not_yet_a_skip(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 2 * _DAY, False), (["x"], now - _DAY, True)])
        assert carryover_state(load_sweeps(p), now=now).skipped_items == ()

    def test_resolved_item_leaves_the_queue(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x", "y"], now - 2 * _DAY, True), (["y"], now - _DAY, True)])
        ids = {i.defect_id for i in carryover_state(load_sweeps(p), now=now).items}
        assert ids == {"y"}  # x stopped firing -> no longer owed

    def test_age_is_measured_from_first_sighting(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 10 * _DAY, True), (["x"], now, True)])
        assert carryover_state(load_sweeps(p), now=now).items[0].age_days == 10.0

    def test_most_skipped_ranks_first(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["old"], now - 5 * _DAY, True),
                               (["old"], now - 4 * _DAY, True),
                               (["old", "new"], now - _DAY, True)])
        items = carryover_state(load_sweeps(p), now=now).items
        assert items[0].defect_id == "old"


class TestBrief:
    def test_empty_queue_says_so(self) -> None:
        assert "queue empty" in brief(carryover_state([], now=time.time()))

    def test_brief_marks_skipped_items(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 3 * _DAY, True),
                               (["x"], now - 2 * _DAY, True),
                               (["x"], now - _DAY, True)])
        text = brief(carryover_state(load_sweeps(p), now=now))
        assert "[SKIPPED]" in text and "do these FIRST" in text

    def test_brief_reports_lost_cycles(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 2 * _DAY, False), (["x"], now - _DAY, False)])
        assert "2 lost to quota" in brief(carryover_state(load_sweeps(p), now=now))


class TestDeferralIsNotAvoidance:
    """§37's third category: shown, judged, and disposed of with a DATED ack.

    Regression for 2026-08-01: every dated ack was recorded as owed, so 26 disposed items were
    reported as "shown the work and not done" and the 12 ranked FIRST were 12/12 acked.
    """

    def test_acked_item_is_never_reported_as_skipped(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger_acked(tmp_path, [([], ["a"], now - 3 * _DAY, True),
                                     ([], ["a"], now - 2 * _DAY, True),
                                     ([], ["a"], now - _DAY, True)])
        st = carryover_state(load_sweeps(p), now=now)
        assert st.skipped_items == ()
        assert st.items == ()
        assert [i.defect_id for i in st.deferred] == ["a"]

    def test_brief_does_not_order_the_brain_to_redo_disposed_work(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger_acked(tmp_path, [([], ["a"], now - 2 * _DAY, True),
                                     ([], ["a"], now - _DAY, True)])
        text = brief(carryover_state(load_sweeps(p), now=now))
        assert "[SKIPPED]" not in text
        assert "queue empty" in text and "deferred under a dated ack" in text

    def test_a_live_item_alongside_an_acked_one_still_fires(self, tmp_path: Path) -> None:
        """The fix must not mute the real signal -- only the false one."""
        now = time.time()
        p = _ledger_acked(tmp_path, [(["live"], ["ack"], now - 3 * _DAY, True),
                                     (["live"], ["ack"], now - 2 * _DAY, True),
                                     (["live"], ["ack"], now - _DAY, True)])
        st = carryover_state(load_sweeps(p), now=now)
        assert [i.defect_id for i in st.skipped_items] == ["live"]
        assert [i.defect_id for i in st.deferred] == ["ack"]
        assert "[SKIPPED] live" in brief(st)

    def test_age_of_a_deferred_item_counts_its_owed_history(self, tmp_path: Path) -> None:
        """Acking an old defect does not reset how long it has been a defect."""
        now = time.time()
        p = _ledger_acked(tmp_path, [(["a"], [], now - 10 * _DAY, True),
                                     ([], ["a"], now - _DAY, True)])
        st = carryover_state(load_sweeps(p), now=now)
        assert st.deferred[0].age_days == 10.0


class TestTreadmill:
    """A legal ack renewed forever is burial by instalments -- the 30d cap exists to stop it."""

    def test_deferral_past_the_burial_line_fires(self, tmp_path: Path) -> None:
        now = time.time()
        rows = [([], ["a"], now - d * _DAY, True) for d in (40, 30, 20, 10, 1)]
        st = carryover_state(load_sweeps(_ledger_acked(tmp_path, rows)), now=now)
        assert [i.defect_id for i in st.treadmill_items] == ["a"]
        assert st.deferred[0].deferred_days >= TREADMILL_DAYS
        assert "TREADMILL" in brief(st)

    def test_fresh_deferral_does_not_fire(self, tmp_path: Path) -> None:
        now = time.time()
        rows = [([], ["a"], now - d * _DAY, True) for d in (3, 2, 1)]
        st = carryover_state(load_sweeps(_ledger_acked(tmp_path, rows)), now=now)
        assert st.treadmill_items == ()
        assert "TREADMILL" not in brief(st)

    def test_a_live_spell_breaks_the_deferral_run(self, tmp_path: Path) -> None:
        """Re-acking after the item came back live is a fresh decision, not 40 unbroken days."""
        now = time.time()
        rows = [([], ["a"], now - 40 * _DAY, True),
                (["a"], [], now - 20 * _DAY, True),      # live again -> run broken
                ([], ["a"], now - 1 * _DAY, True)]
        st = carryover_state(load_sweeps(_ledger_acked(tmp_path, rows)), now=now)
        assert st.treadmill_items == ()
        assert st.deferred[0].deferred_days < TREADMILL_DAYS

    def test_unmeasurable_deferral_never_reads_as_clean(self, tmp_path: Path) -> None:
        """Legacy rows carry no ack column, so the span is None -- unmeasurable, not fine."""
        p = _ledger(tmp_path, [(["a"], time.time() - _DAY, True)])
        st = carryover_state(load_sweeps(p), now=time.time())
        assert st.items[0].deferred_days is None
        assert st.items[0].treadmill is False


class TestAckStateRefusal:
    def test_unknown_ack_state_is_declared_in_the_brief(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger_acked(tmp_path, [(["a"], [], now - 2 * _DAY, True),
                                     (["a"], [], now - _DAY, True)], state="unknown")
        text = brief(carryover_state(load_sweeps(p), now=now))
        assert "ACK STATE UNMEASURED" in text

    def test_known_ack_state_is_silent(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger_acked(tmp_path, [(["a"], [], now - 2 * _DAY, True),
                                     (["a"], [], now - _DAY, True)], state="known")
        assert "ACK STATE UNMEASURED" not in brief(carryover_state(load_sweeps(p), now=now))

    def test_legacy_rows_without_the_column_load_and_report_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "legacy.jsonl"
        p.write_text(json.dumps({"ts": time.time() - _DAY, "ids": ["a"], "alive": True}) + "\n")
        st = carryover_state(load_sweeps(p), now=time.time())
        assert [i.defect_id for i in st.items] == ["a"]
        assert st.ack_state == "unknown"


class TestRecurrenceIsNotASkip:
    """A defect FIXED and later re-fired is not a defect nobody touched.

    Measured live 2026-08-05: `findings-scope-unmonitored` alternated present/absent across 5 of
    the last 12 sweeps -- it was closed every time and fired again on a newly-written doc -- and
    the brief still printed "age 10.3d, 12 sweeps with the brain awake, shown the work and not
    done". Section 37 makes this brief the FIRST thing every organ reads, so a false skip
    accusation misdirects the most valuable slot of every cycle onto a treadmill while genuinely
    untouched rows rank below it.
    """

    def test_fixed_then_refired_is_recurring_not_skipped(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 5 * _DAY, True),   # owed
                               (["x"], now - 4 * _DAY, True),   # owed
                               ([], now - 3 * _DAY, True),      # FIXED -- the run breaks here
                               (["x"], now - _DAY, True)])      # fired again on new input
        st = carryover_state(load_sweeps(p), now=now)
        item = st.items[0]
        assert st.skipped_items == (), "a fixed-then-refired defect was never walked past"
        assert item.recurring and item.recurrences == 2
        assert st.recurring_items and st.recurring_items[0].defect_id == "x"
        assert "RECURRING" in st.verdict

    def test_age_and_survival_measure_the_current_run_only(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 10 * _DAY, True),
                               ([], now - 9 * _DAY, True),      # fixed
                               (["x"], now - 2 * _DAY, True)])  # back
        item = carryover_state(load_sweeps(p), now=now).items[0]
        assert item.age_days == 2.0, "owed-since dates from the re-appearance, not the first ever"
        assert item.sweeps_survived == 1, "one unbroken sweep, not two sightings"
        assert item.age_days_ever == 10.0, "the full history is kept, never dropped"
        assert item.total_occurrences == 2

    def test_continuously_owed_still_reports_full_age_and_skip(self, tmp_path: Path) -> None:
        """The fix must not soften a genuine skip -- no gap means nothing changes."""
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 6 * _DAY, True),
                               (["x"], now - 4 * _DAY, True),
                               (["x"], now - 2 * _DAY, True)])
        item = carryover_state(load_sweeps(p), now=now).items[0]
        assert item.skipped and not item.recurring
        assert item.age_days == 6.0 and item.sweeps_survived == 3

    def test_untouched_rows_outrank_the_treadmill(self, tmp_path: Path) -> None:
        """Ordering decides which row a cycle works first -- neglect must beat recurrence."""
        now = time.time()
        p = _ledger(tmp_path, [(["neglected", "churn"], now - 6 * _DAY, True),
                               (["neglected"], now - 4 * _DAY, True),
                               (["neglected", "churn"], now - _DAY, True)])
        items = carryover_state(load_sweeps(p), now=now).items
        assert [i.defect_id for i in items] == ["neglected", "churn"]

    def test_brief_labels_a_recurrence_and_keeps_its_history(self, tmp_path: Path) -> None:
        now = time.time()
        p = _ledger(tmp_path, [(["x"], now - 9 * _DAY, True),
                               ([], now - 5 * _DAY, True),
                               (["x"], now - _DAY, True)])
        out = brief(carryover_state(load_sweeps(p), now=now))
        assert "[RECURRING]" in out
        assert "RECURRED 2x over 9.0d" in out, "the long history is stated, never hidden"
        assert "generalise the rule" in out.lower()
