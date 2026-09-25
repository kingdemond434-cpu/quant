"""THE BUG CORPUS IS BEATEN WHOLE OR NOT AT ALL (Tier-1 B18).

    cd desks/mt5 && python -m pytest tests/test_quantbench.py -q

This is the consumer `research/quantbench.py` exists for: every defect the desk has already paid
for is replayed against THIS tree, in one pass, and the suite fails while any case reads
REGRESSED. A case that cannot run reads UNMEASURED and is reported -- never a pass (L1.28a), and
never a failure either, because an absent input is not a returning bug.

The corpus is data (`data/quantbench/corpus.jsonl`) and its probes are code. A new defect is added
by appending a row and registering a probe; a case NEVER leaves by being edited into agreement
with a tree that broke it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import quantbench as qb  # noqa: E402


def test_the_corpus_has_cases_and_each_names_a_probe() -> None:
    rows = qb.cases()
    assert len(rows) >= 6, "the shipped corpus must hold the defects the ledger cites"
    assert [r["id"] for r in rows if str(r.get("check")) not in qb.CHECKS] == []


def test_no_historical_defect_has_returned() -> None:
    doc = qb.build(budget_s=120.0)
    regressed = [r for r in doc["cases"] if r["verdict"] == "REGRESSED"]
    assert regressed == [], "\n".join(
        f"{r['id']}: {r.get('why')} ({r.get('lesson')})" for r in regressed)
    assert doc["counts"].get("PASS", 0) >= 1, "a bench where nothing could run proves nothing"
