"""R0272 -- an append-only ledger whose diff is unreviewable is not auditable in practice.

THE MEASURED DEFECT. On 2026-08-01 both Claude sessions independently produced multi-thousand-line
whole-file diffs on append-only ledgers by writing a different indent than the canonical writer: a
26-line append to ``data/decision_ledger.json`` rendered as 7,056 changed lines, and a sibling's
ledger commit as 6,360. The content was intact BOTH times, and that is precisely the danger -- at a
glance the diff is indistinguishable from the LEDGER CORRUPTION class that
``test_tracked_json_integrity.py`` exists to catch, so a real deletion inside one would pass review
unseen and the append-only guarantee becomes a claim rather than a property.

WHY THE EXISTING FENCE DOES NOT COVER THIS, and the distinction is the whole point.
``test_tracked_json_integrity`` asks whether the file PARSES and carries no conflict markers -- it
is a corruption detector. A wrong-indent rewrite parses perfectly. Format drift is invisible to
every check the desk had; it is caught only at review, by a human, on the one diff too large to
read. So the two fences are complements, not duplicates.

WHAT IS ASSERTED: the bytes on disk are exactly what the canonical writer would emit. Not "close
to", not "parses to the same object" -- byte-identical, because the diff is a property of BYTES and
anything weaker passes the exact drift this exists to stop.

THE REGISTRY IS DELIBERATELY EXPLICIT (and L1.57-checked below): a canonical form that discovered
itself from the current file contents would ratify whatever drift had already landed, which is the
denominator trick in format clothing. Each entry names its writer so a deliberate format change is
a one-line edit HERE plus the writer -- visible, reviewed, and paired.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

#: path -> (indent, trailing_newline, the canonical writer that defines this form)
#: Verified against the live files 2026-08-05; both writers emit indent=1 with no trailing newline.
_CANONICAL: dict[str, tuple[int, bool, str]] = {
    "docs/research/recommendation_ledger.json": (1, False, "scripts/recommendations.py:79"),
    "data/decision_ledger.json": (1, False, "scripts/run_decision_review.py:69"),
}


def test_registry_is_not_empty() -> None:
    """L1.57: a passing verdict over an empty scope is VACUOUS, not evidence."""
    assert _CANONICAL, "an empty canonical registry would make every assertion below vacuous"


@pytest.mark.parametrize("rel", sorted(_CANONICAL))
def test_ledger_is_byte_identical_to_its_canonical_writer(rel: str) -> None:
    indent, trailing, writer = _CANONICAL[rel]
    path = _ROOT / rel
    assert path.exists(), (
        f"{rel} is in the canonical registry but absent from disk -- a missing ledger must fail "
        f"here rather than silently reduce this fence's scope to nothing")

    raw = path.read_text("utf-8")
    canonical = json.dumps(json.loads(raw), indent=indent) + ("\n" if trailing else "")
    if raw == canonical:
        return

    # Name the drift precisely; "it differs" sends the next reader to diff 586KB by hand.
    found = next((f"indent={i}, trailing_newline={t}"
                  for i in (0, 1, 2, 4) for t in (False, True)
                  if json.dumps(json.loads(raw), indent=i) + ("\n" if t else "") == raw),
                 "no standard json.dumps indent")
    pytest.fail(
        f"{rel} is NOT byte-identical to its canonical writer ({writer}, indent={indent}, "
        f"trailing_newline={trailing}); on disk it matches {found}. The next append will rewrite "
        f"EVERY line, producing a whole-file diff in which a deletion cannot be seen. Fix the "
        f"writer and this entry together, or rewrite the file in canonical form -- do not widen "
        f"this fence to accept both.")
