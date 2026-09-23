"""The QuantBench runs in the suite, so no refactor clears the gate without clearing the bench.

THE PRINCIPAL, 2026-09-12: "no new researcher, model or refactor may pass without clearing all of
them." A bench that only runs on its own daily clock is a report; a bench that runs in the suite
is a gate, and the difference is whether a change can land while a survived defect has returned.

WHY FAIL IS THE ONLY FAILURE. A case reports UNMEASURABLE when the artifact its probe reads is
absent -- on a fresh clone, before the daily lane has run once, that is most of them. Failing the
suite on UNMEASURABLE would make the bench impossible to satisfy from a clean checkout and would
be promptly deleted, which is a worse outcome than a bench that only catches returns. FAIL means
the probe READ the evidence and found the defect back; that is the assertion.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.quantbench import CASES, build  # noqa: E402


def test_no_survived_defect_has_returned() -> None:
    """Every case the bench could measure still holds."""
    doc = build()
    failed = [r for r in doc["results"] if r["verdict"] == "FAIL"]
    assert not failed, "\n".join(
        f"{r['case']} (first seen {r['defect_occurred']}): {r['detail']}" for r in failed)


def test_every_case_cites_a_dated_defect() -> None:
    """A case whose defect cannot be cited is a style opinion, not a benchmark."""
    for cid, (defect, when, _probe) in CASES.items():
        assert len(defect) > 60, f"{cid}: the defect is not described, only named"
        assert when.count("-") == 2 and len(when) == 10, f"{cid}: no ISO date on the defect"


def test_the_bench_cannot_quietly_shrink() -> None:
    """The case count is a ratchet, and `bench_erosion` is the case that enforces it."""
    assert "bench_erosion" in CASES
    doc = build()
    erosion = next(r for r in doc["results"] if r["case"] == "bench_erosion")
    assert erosion["verdict"] != "FAIL", erosion["detail"]


def test_unmeasurable_is_not_counted_as_a_pass() -> None:
    """A bench that scored absence as success would score highest on an empty box."""
    doc = build()
    tally = doc["tally"]
    assert doc["n_unmeasurable"] == tally.get("UNMEASURABLE", 0)
    assert doc["n_unmeasurable"] + tally.get("PASS", 0) + tally.get("FAIL", 0) == len(CASES)
    if doc["n_unmeasurable"]:
        assert doc["status"] != "PASS", "unmeasurable cases must not yield an overall PASS"
