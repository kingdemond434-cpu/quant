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
from typing import NamedTuple

import pytest

_ROOT = Path(__file__).resolve().parents[2]


class _Form(NamedTuple):
    """The exact bytes a canonical writer emits. Named rather than a bare tuple because
    `trailing_newline` and `ensure_ascii` are adjacent booleans, and a positional swap between
    them would silently assert the wrong form -- the failure this fence exists to catch."""

    indent: int
    trailing_newline: bool
    ensure_ascii: bool
    writer: str


#: Verified against the live files 2026-08-12; both writers emit indent=1, no trailing newline.
#: ensure_ascii=False since R0368: escaped CJK and `§` are unreadable AND ungreppable in the raw
#: file, so a term already mined returns a clean zero to grep and reads as unexplored ground.
_CANONICAL: dict[str, _Form] = {
    "docs/research/recommendation_ledger.json":
        _Form(1, False, False, "scripts/recommendations.py:85"),
    "data/decision_ledger.json": _Form(1, False, False, "scripts/run_decision_review.py:73"),
}


def test_registry_is_not_empty() -> None:
    """L1.57: a passing verdict over an empty scope is VACUOUS, not evidence."""
    assert _CANONICAL, "an empty canonical registry would make every assertion below vacuous"


@pytest.mark.parametrize("rel", sorted(_CANONICAL))
def test_ledger_is_byte_identical_to_its_canonical_writer(rel: str) -> None:
    form = _CANONICAL[rel]
    path = _ROOT / rel
    assert path.exists(), (
        f"{rel} is in the canonical registry but absent from disk -- a missing ledger must fail "
        f"here rather than silently reduce this fence's scope to nothing")

    raw = path.read_text("utf-8")
    canonical = (json.dumps(json.loads(raw), indent=form.indent, ensure_ascii=form.ensure_ascii)
                 + ("\n" if form.trailing_newline else ""))
    if raw == canonical:
        return

    # Name the drift precisely; "it differs" sends the next reader to diff 586KB by hand.
    found = next((f"indent={i}, trailing_newline={t}, ensure_ascii={e}"
                  for i in (0, 1, 2, 4) for t in (False, True) for e in (False, True)
                  if json.dumps(json.loads(raw), indent=i, ensure_ascii=e)
                  + ("\n" if t else "") == raw),
                 "no standard json.dumps form")
    pytest.fail(
        f"{rel} is NOT byte-identical to its canonical writer ({form.writer}, "
        f"indent={form.indent}, trailing_newline={form.trailing_newline}, "
        f"ensure_ascii={form.ensure_ascii}); on disk it matches {found}. The next append will "
        f"rewrite EVERY line, producing a whole-file diff in which a deletion cannot be seen. Fix "
        f"the writer and this entry together, or rewrite the file in canonical form -- do not "
        f"widen this fence to accept both.")


def test_no_canonical_form_escapes_non_ascii() -> None:
    """R0368: the registry may not quietly drift BACK to escaped form.

    The three costs R0368 measured were all about diff churn and were closed by this fence's
    byte-identity assertion. The cost that survives is legibility: `\\u97ed\\u83dc` is both
    unreadable to a reviewer and invisible to `grep 韭菜`, so ground the desk has already
    mined answers a search with a clean zero. Asserted on the REGISTRY rather than the files,
    so a future entry cannot reintroduce it for a new ledger.
    """
    escaped = {rel: f for rel, f in _CANONICAL.items() if f.ensure_ascii}
    assert not escaped, (
        f"these canonical forms escape non-ASCII: {sorted(escaped)}. A ledger whose non-English "
        f"rows cannot be grepped in their own alphabet makes mined ground read as unexplored.")
