"""Tests for CPCV and walk-forward splitters."""

from __future__ import annotations

import pytest

from libs.validation.cpcv import CPCV
from libs.validation.errors import ValidationError
from libs.validation.walk_forward import walk_forward_splits


def test_cpcv_split_count_and_disjoint() -> None:
    cpcv = CPCV(n_groups=6, n_test_groups=2, purge=0, embargo=0.0)
    splits = cpcv.split(120)
    assert cpcv.n_splits() == 15
    assert len(splits) == 15
    for split in splits:
        assert set(split.train).isdisjoint(set(split.test))


def test_cpcv_purge_removes_neighbours() -> None:
    cpcv = CPCV(n_groups=5, n_test_groups=1, purge=3, embargo=0.0)
    for split in cpcv.split(100):
        train = set(split.train.tolist())
        for t in split.test:
            for k in range(1, 4):
                assert t - k not in train  # purged before
                assert t + k not in train  # purged after


def test_cpcv_embargo_creates_gap() -> None:
    cpcv = CPCV(n_groups=5, n_test_groups=1, purge=0, embargo=0.1)  # 10 bars on n=100
    for split in cpcv.split(100):
        train = set(split.train.tolist())
        last_test = int(split.test.max())
        for k in range(1, 11):
            if last_test + k < 100:
                assert last_test + k not in train


def test_cpcv_invalid_params() -> None:
    with pytest.raises(ValidationError):
        CPCV(n_groups=4, n_test_groups=4)
    with pytest.raises(ValidationError):
        CPCV(n_groups=4, n_test_groups=1, purge=-1)


def test_walk_forward_anchored() -> None:
    splits = walk_forward_splits(100, n_splits=5, test_size=10, anchored=True)
    assert len(splits) == 5
    assert splits[0].train[0] == 0
    for i in range(1, len(splits)):
        assert len(splits[i].train) > len(splits[i - 1].train)  # expanding
    for split in splits:
        assert int(split.train.max()) < int(split.test.min())  # no overlap


def test_walk_forward_rolling_fixed_window() -> None:
    splits = walk_forward_splits(100, n_splits=5, test_size=10, anchored=False)
    lengths = {len(split.train) for split in splits}
    assert len(lengths) == 1  # constant training window


def test_walk_forward_embargo_gap() -> None:
    splits = walk_forward_splits(100, n_splits=5, test_size=10, anchored=True, embargo=3)
    for split in splits:
        assert int(split.test.min()) - int(split.train.max()) >= 3


def test_walk_forward_too_small() -> None:
    with pytest.raises(ValidationError):
        walk_forward_splits(20, n_splits=5, test_size=10)
