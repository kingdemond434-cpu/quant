"""THE BINDING CONSTRAINT, CONVERTED INTO WORK -- and the state that makes it cheap.

`mechanism_census` ranks every untested mechanism class and lists the exact datasets each needs.
Nothing converted that into work, so the top-ranked gap on the desk's SINGLE binding constraint
(distinct mechanism supply: cross-mechanism N_eff 4.08 against the ~100 a weak-edge portfolio
needs) sat as a paragraph in a report.

The load-bearing design decision is the FOURTH state. The first version had only
reachable/blocked, which lumped "behind a paid vendor" together with "nobody has ever looked".
Those owe completely different work -- an expensive hunt that may fail, versus two minutes with a
browser -- and reporting the second as a wall is how the cheapest available progress on the
binding constraint stays invisible. Live, the top five gaps are ALL that second kind.
"""
from __future__ import annotations

from pathlib import Path

from scripts.report_mechanism_supply import classify


class TestTheFourStates:
    def test_all_free_datasets_are_buildable_now(self, tmp_path: Path) -> None:
        state, reach, unchecked, blocked = classify(
            ["public index methodology documents", "free RPC event logs"], tmp_path)
        assert state == "BUILDABLE-NOW"
        assert len(reach) == 2 and not unchecked and not blocked

    def test_an_unchecked_dataset_is_a_look_not_a_wall(self, tmp_path: Path) -> None:
        """THE DISTINCTION THE FIRST VERSION MISSED. Nobody has looked is not the same fact as
        somebody is charging, and only one of them is expensive to resolve."""
        state, _reach, unchecked, blocked = classify(
            ["constituent lists before and after each review"], tmp_path)
        assert state == "NEEDS-A-LOOK"
        assert unchecked and not blocked

    def test_a_paid_vendor_blocks_even_when_a_free_route_is_mentioned(self, tmp_path: Path) -> None:
        """This desk has been burned by treating 'reconstructable in principle' as 'available'."""
        state, _r, _u, blocked = classify(
            ["Tardis.dev historical book data, or reconstruct from a free public feed"], tmp_path)
        assert state == "BLOCKED" and blocked

    def test_a_mixed_gap_keeps_the_reachable_half_visible(self, tmp_path: Path) -> None:
        state, reach, _u, blocked = classify(
            ["public governance event logs", "Nansen wallet labels"], tmp_path)
        assert state == "PARTIALLY-BLOCKED"
        assert reach and blocked, "writing off the whole gap would lose work that can start today"

    def test_unchecked_never_counts_toward_buildable_now(self, tmp_path: Path) -> None:
        """Otherwise the worklist fills with work that stalls on first contact."""
        state, _r, unchecked, _b = classify(
            ["free public filings", "something nobody has ever checked"], tmp_path)
        assert state != "BUILDABLE-NOW" and unchecked

    def test_a_dataset_present_on_disk_counts_as_reachable(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        (tmp_path / "data/thing.jsonl").write_text("{}", "utf-8")
        _s, reach, _u, _b = classify(["data/thing.jsonl holds the series"], tmp_path)
        assert reach, "a file that exists is reachable, and that is checked not assumed"

    def test_a_named_file_that_is_absent_is_not_reachable(self, tmp_path: Path) -> None:
        """The census names CANDIDATE files. Whether they are present is a fact about this box."""
        _s, reach, unchecked, _b = classify(["data/never_written.jsonl holds it"], tmp_path)
        assert not reach and unchecked

    def test_an_empty_dataset_list_is_buildable_rather_than_blocked(self, tmp_path: Path) -> None:
        state, _r, _u, _b = classify([], tmp_path)
        assert state == "BUILDABLE-NOW"
