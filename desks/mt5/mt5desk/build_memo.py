"""BUILD MEMO -- compute an intermediate once per sweep worker, not once per cell.

WHY (measured 2026-09-29 on a 600-cell sample of the live docket, synthetic bars,
`desks/mt5/tests/test_judging_speed_equivalence.py`). The sealed gauntlet spends its whole
FRESH_BUILD_BUDGET_SEC building cells, and most of that time was the SAME work repeated:

  * `exit_operated` is 28% of the docket. Each (symbol, chart, base family, base params) is minted
    as ~12 cells that differ only in the exit operator (`expansion_mult` x `exit_on_anchor_flip`),
    and every one of them rebuilt the base family's signals from scratch -- including the
    60-iteration HMM fits under `regime_transition`, the single most expensive family.
  * `regime_transition` cells that differ only in their entry threshold, age, side or stop/target
    re-fit the identical hazard path on the identical daily closes.

A memo returns the SAME value the computation would have returned: keys are a content hash of
the bars (every column, the index, the dtypes) plus the exact arguments, so two frames that
differ in any byte never share an entry. Nothing here changes which cells are built, their order,
or any gate; it only stops paying twice for one answer. Values are handed out as copies so a
caller that mutates what it received cannot poison the next cell.

BOUNDED: each memo is an LRU of a few dozen small entries (signal lists, per-day series), so a
worker's memory stays a constant, not a function of the sweep's length.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

MEMO_ENTRIES = 48


def frame_fingerprint(df: pd.DataFrame | pd.Series) -> str:
    """A content hash of a frame or series: index, column names, dtypes and every value."""
    h = hashlib.blake2b(digest_size=20)
    obj = df.to_frame() if isinstance(df, pd.Series) else df
    idx = obj.index
    h.update(repr((type(idx).__name__, str(idx.dtype), len(idx),
                   getattr(idx, "name", None))).encode())
    if isinstance(idx, pd.DatetimeIndex):
        h.update(str(idx.tz).encode())
        h.update(np.ascontiguousarray(idx.asi8).tobytes())
    else:
        h.update(pd.util.hash_pandas_object(pd.Index(idx), index=False).to_numpy().tobytes())
    for col in obj.columns:
        s = obj[col]
        h.update(repr((str(col), str(s.dtype))).encode())
        values = s.to_numpy()
        if values.dtype.kind in "biufcmM":
            h.update(np.ascontiguousarray(values).tobytes())
        else:
            h.update(pd.util.hash_pandas_object(s, index=False).to_numpy().tobytes())
    return h.hexdigest()


def args_key(*parts: Any) -> str:
    """A stable key for plain arguments (dicts in any key order, lists, scalars)."""
    return json.dumps(parts, sort_keys=True, default=repr)


class Memo:
    """A small LRU mapping a key to a value, handing out copies made by `copier`."""

    def __init__(self, entries: int = MEMO_ENTRIES,
                 copier: Callable[[Any], Any] = copy.deepcopy) -> None:
        self.entries = entries
        self.copier = copier
        self._d: OrderedDict[tuple, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key: tuple, compute: Callable[[], Any]) -> Any:
        if key in self._d:
            self._d.move_to_end(key)
            self.hits += 1
            return self.copier(self._d[key])
        self.misses += 1
        value = compute()
        self._d[key] = self.copier(value)
        while len(self._d) > self.entries:
            self._d.popitem(last=False)
        return value

    def clear(self) -> None:
        self._d.clear()
        self.hits = self.misses = 0


def copy_signals(sigs: Any) -> Any:
    """A new list of shallow-copied signals. A `Signal`'s fields are immutable scalars
    (floats, ints, str, Timestamp), so a shallow copy per signal is a full copy of the value."""
    if sigs is None:
        return None
    return [copy.copy(s) for s in sigs]
