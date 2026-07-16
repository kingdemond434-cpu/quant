"""Combinatorial Purged Cross-Validation (CPCV) with purge + embargo.

Financial CV must drop training samples whose label windows overlap the test set (**purge**)
and a buffer immediately after it (**embargo**) — otherwise overlapping labels leak. CPCV
forms many train/test splits by choosing several test groups at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np

from libs.validation.errors import ValidationError


@dataclass(frozen=True)
class CPCVSplit:
    train: np.ndarray
    test: np.ndarray


class CPCV:
    """Combinatorial purged cross-validation splitter."""

    def __init__(
        self,
        *,
        n_groups: int = 6,
        n_test_groups: int = 2,
        purge: int = 0,
        embargo: float = 0.0,
    ) -> None:
        if n_test_groups >= n_groups or n_test_groups < 1:
            raise ValidationError("require 1 <= n_test_groups < n_groups")
        if purge < 0 or embargo < 0:
            raise ValidationError("purge and embargo must be non-negative")
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge = purge
        self.embargo = embargo

    def n_splits(self) -> int:
        return comb(self.n_groups, self.n_test_groups)

    @staticmethod
    def _contiguous_blocks(indices: np.ndarray) -> list[tuple[int, int]]:
        if len(indices) == 0:
            return []
        sorted_idx = np.sort(indices)
        blocks: list[tuple[int, int]] = []
        start = prev = int(sorted_idx[0])
        for value in sorted_idx[1:]:
            v = int(value)
            if v == prev + 1:
                prev = v
            else:
                blocks.append((start, prev))
                start = prev = v
        blocks.append((start, prev))
        return blocks

    def split(self, n_samples: int) -> list[CPCVSplit]:
        if n_samples < self.n_groups:
            raise ValidationError("n_samples must be >= n_groups")
        groups = np.array_split(np.arange(n_samples), self.n_groups)
        embargo_size = round(self.embargo * n_samples)
        splits: list[CPCVSplit] = []
        for test_ids in combinations(range(self.n_groups), self.n_test_groups):
            test = np.concatenate([groups[i] for i in test_ids])
            test_set = set(test.tolist())
            train_set = set(range(n_samples)) - test_set
            for a, b in self._contiguous_blocks(test):
                for i in range(a - self.purge, b + self.purge + 1):  # purge overlapping labels
                    train_set.discard(i)
                for i in range(b + 1, b + 1 + embargo_size):  # embargo after test
                    train_set.discard(i)
            train = np.array(sorted(train_set), dtype=int)
            splits.append(CPCVSplit(train=train, test=np.sort(test)))
        return splits
