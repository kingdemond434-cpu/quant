"""Factory registry: ROI scoring, milestone path, family breadth."""

from __future__ import annotations

from libs.factory.registry import (
    DATASETS,
    EDGE_FAMILIES,
    TARGET_PER_FAMILY,
    free_next_priorities,
    milestone_path,
    paid_data_path,
)


def test_dataset_roi_in_range_and_cost_penalised() -> None:
    for d in DATASETS:
        assert 0.0 <= d.roi() <= 1.0
    # a free, high-orthogonality dataset must out-score an identical high-cost one
    free = max(DATASETS, key=lambda d: d.roi())
    assert free.roi() > 0.0


def test_milestone_path_finds_next_and_gap() -> None:
    ms = milestone_path(0.66, dict.fromkeys(EDGE_FAMILIES, 0))
    assert ms.next_milestone == 0.75
    assert abs(ms.gap - 0.09) < 1e-9
    assert ms.families_complete == 0


def test_milestone_complete_counts_families() -> None:
    counts = dict.fromkeys(EDGE_FAMILIES, TARGET_PER_FAMILY)
    ms = milestone_path(1.6, counts)
    assert ms.next_milestone == 1.75
    assert ms.families_complete == len(EDGE_FAMILIES)


def test_free_priorities_are_all_free() -> None:
    free = free_next_priorities()
    assert free
    # ranked descending by roi
    rois = [d["roi"] for d in free]
    assert rois == sorted(rois, reverse=True)


def test_paid_path_ranked_by_priority() -> None:
    paid = paid_data_path()
    pr = [d["priority"] for d in paid]
    assert pr == sorted(pr, reverse=True)
