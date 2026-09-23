"""A cell may not be called JUDGED until its verdict is durable.

`lost` is the conservation ledger's only alarm for a dropped record, and the sweep's write order
was manufacturing the very thing it watches for. `_save_seen_cells` stamped cells as judged, and
`_append_gate_ledger` wrote the durable verdict THIRTY-THREE LINES LATER, inside a `_safe(...)`.
A sweep that died, was killed by the memory guard, or simply raised between the two left cells
marked judged with no verdict anywhere.

MEASURED 2026-09-14: 10 lost cells, every one `discovered`, ALL TEN carrying the same seen-stamp
`2026-09-12T03:19:08+00:00`. One interrupted sweep, one instant, ten cells that can never be
re-judged (they are no longer new) and can never be accounted for (they hold no verdict).

Stamping AFTER means the worst case is a cell judged twice -- one rotation slot. Stamping BEFORE
meant the worst case was a cell lost forever. Those are not symmetric, which is why the order is
pinned here rather than left to whoever edits the function next.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

eg = pytest.importorskip("external_gauntlet")


def _sweep_source() -> str:
    """The function body that writes both ledgers."""
    src = Path(eg.__file__).read_text(encoding="utf-8")
    return src


def test_the_verdict_index_is_written_before_the_seen_stamp():
    src = _sweep_source()
    append = [m.start() for m in re.finditer(r"_append_gate_ledger\(", src)
              if "def _append_gate_ledger" not in src[max(0, m.start() - 60):m.start()]]
    stamp = [m.start() for m in re.finditer(r"_save_seen_cells\(", src)
             if "def _save_seen_cells" not in src[max(0, m.start() - 60):m.start()]]
    assert append and stamp, "both ledger writes must exist"
    assert min(append) < min(stamp), (
        "the durable verdict must be written BEFORE cells are stamped as judged: a sweep "
        "interrupted between them loses those cells permanently")


def test_both_ledgers_are_still_written():
    src = _sweep_source()
    assert "_append_gate_ledger" in src
    assert "_save_seen_cells" in src
    assert 'result["gate_ledger"]' in src, "the artifact's shape must be unchanged for consumers"


def test_only_ruled_cells_are_stamped():
    """A deferred or blocked cell carries passed=None and must NOT be stamped -- stamping work
    nobody has looked at drops it out of the new-first queue silently."""
    src = _sweep_source()
    i = src.index("_save_seen_cells(_seen")
    window = src[i:i + 260]
    assert 'v.get("passed") is not None' in window
