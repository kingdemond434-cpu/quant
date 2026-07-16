"""Walk-forward validation splits (anchored / rolling)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.validation.errors import ValidationError


@dataclass(frozen=True)
class WalkForwardSplit:
    train: np.ndarray
    test: np.ndarray


def walk_forward_splits(
    n_samples: int,
    *,
    n_splits: int,
    test_size: int,
    anchored: bool = True,
    embargo: int = 0,
) -> list[WalkForwardSplit]:
    """Generate sequential out-of-sample windows.

    Anchored: training starts at 0 and expands. Rolling: training is a fixed-size window. An
    optional ``embargo`` drops bars between train and test.
    """
    if test_size < 1 or n_splits < 1:
        raise ValidationError("n_splits and test_size must be >= 1")
    min_train = n_samples - n_splits * test_size
    if min_train <= 0:
        raise ValidationError("n_samples too small for the requested splits")

    splits: list[WalkForwardSplit] = []
    for i in range(n_splits):
        test_start = min_train + i * test_size
        test_end = test_start + test_size
        train_end = max(0, test_start - embargo)
        train_start = 0 if anchored else max(0, train_end - min_train)
        train = np.arange(train_start, train_end)
        test = np.arange(test_start, test_end)
        splits.append(WalkForwardSplit(train=train, test=test))
    return splits
