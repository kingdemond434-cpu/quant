"""§37 -- work owed survives an outage and is handed back, and a SKIP is told apart from a MISS.

The distinction is the whole point: a long queue looks identical whether nobody was home or
everybody walked past it. Blaming the desk for a quota outage is unfair; excusing avoidance is
expensive. Only the second is a defect."""

from __future__ import annotations

import time
from pathlib import Path

from libs.ops.carryover import (
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
