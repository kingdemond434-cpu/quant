"""ARTIFACTS A TEST RUN MAY READ AND MAY NEVER WRITE (GAP 113).

THE DEFECT, MEASURED 2026-08-13. A full `pytest` run on a clone rewrote three TRACKED files:
`docs/research/next_law_number.txt` went 60 -> 43 (handing the next two laws a number already in
use -- the exact collision that file exists to prevent), `ops/principal_doctrine.txt` lost a whole
index block, and `docs/research/trade_forensics_latest.json` was overwritten with `n_closes: 0` on
a host holding no trade data. Nothing failed. Nothing printed. The regressions were found by
reading a diff, and they were reverted by hand -- which does not scale and would eventually land
inside an unrelated commit.

**A TEST RUN IS AN OBSERVATION AND MUST NEVER BE A WRITE TO THE THING OBSERVED.** That is the
whole rule. It is stronger than the owning-host guard used for GAP 111 and deliberately so: the
owning-host question ("is this box allowed to recompute state?") has a legitimate YES, but a
SUITE has no legitimate yes. On the VPS -- the one host that owns the state -- a suite run that
recomputed a ratchet from whatever happened to be loaded would be the most damaging version of
this bug, not the safe one, because there the overwrite lands on real evidence.

**WHY A DECLARED SET RATHER THAN "ALL TRACKED FILES".** Two reasons, and the second is the load
bearing one. First, tests do legitimately write inside the tree (caches, `.coverage`, generated
fixtures) and a blanket rule would drown the signal. Second -- a set that is written down is a set
that can be ARGUED WITH: each entry below carries the reason it is protected, so adding one is a
decision with a stated justification and removing one is visible in a diff. A rule inferred from
`git ls-files` would silently change meaning every time somebody committed a file.

**WHAT MAKES AN ARTIFACT BELONG HERE.** Exactly one property: re-deriving it from an incomplete
host produces a WELL-FORMED document that is quietly wrong, and is therefore indistinguishable
afterwards from a correct one. A ratchet recomputed downward, an evidence file recomputed over
missing data, a doctrine block regenerated from a stale module. Files that merely change often do
NOT belong here; files whose corrupted form looks exactly like their healthy form do.

Enforced by `tests/conftest.py`, which snapshots this set before the first test, restores any
member a test modified, names the test that did it, and fails the session. Stdlib only -- it is
imported from a conftest that must work before any project dependency is guaranteed importable.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["PROTECTED", "Snapshot", "changed", "restore", "snapshot"]

#: path -> why writing it during a suite run is a defect. The reason is not decoration: it is
#: what the failure message prints, and a guard that fires without saying what was lost gets
#: switched off by the next person who hits it in a hurry.
PROTECTED: dict[str, str] = {
    "docs/research/next_law_number.txt": (
        "the law-number ALLOCATOR. Recomputed from the laws a host can see, it moves DOWN and "
        "hands the next two laws a number already in use -- the one collision it exists to stop"),
    "ops/principal_doctrine.txt": (
        "injected verbatim as the system prompt of EVERY local organ. A block dropped here "
        "silently un-governs every brain on the desk, and the file still looks well-formed"),
    "docs/research/trade_forensics_latest.json": (
        "the tracked copy of REAL trade evidence. Re-derived on a host without "
        "data/cashcarry_trades.json it reports n_closes: 0 -- and an empty forensics doc is "
        "byte-identical to a desk that genuinely closed nothing (WS-005)"),
    "docs/research/COVERAGE_RATCHET.json": (
        "the coverage floors, which ratchet UP ONLY (L1.50). A floor recomputed to match "
        "whatever this run happened to measure is not a floor, it is a mirror"),
    "docs/research/test_suite_record.json": (
        "the max-collected high-water mark. Rewritten by a partial collection it records a "
        "SMALLER suite as the new best, which is how a dropped test stops being detectable"),
    "docs/research/CONSTITUTION_RATCHET.json": (
        "constitutional high-water marks per principle -- the record that a bar, once reached, "
        "is never quietly lowered"),
    "docs/research/PROMPT_RATCHET.json": (
        "invariant counts per governed prompt. Recomputed against a subset of prompts it "
        "licenses deleting the invariants it could not see"),
    "docs/research/PROMPT_RATCHET_WAIVERS.json": (
        "the explicit, ledgered exceptions to the prompt ratchet. A regenerated waiver file is a "
        "permission nobody granted"),
    "docs/research/LAW_COVERAGE.json": (
        "which laws have an enforcing fence. Recomputed from a partial import closure it reports "
        "unfenced laws as fenced -- the direction that lets an unenforced law read as enforced"),
    "docs/research/data_provenance.json": (
        "where each dataset came from. Regenerated on a clone with no lake it attests to "
        "provenance for data the host does not have"),
    "docs/graveyard.md": (
        "the record of what was tried and killed. Its whole value is that entries are never "
        "silently removed -- a rewritten graveyard buys back dead ground at full price (L1.17)"),
    "docs/desk_lessons.jsonl": (
        "the lesson ledger with recurrence counts. A recurrence counter reset by an observation "
        "is a repeated defect reported as a first occurrence"),
    "docs/research/recommendation_ledger.json": (
        "what external panels recommended and what the desk did about it. Rewritten, it loses "
        "the open items, which is the only half that costs anything"),
    "desks/mt5/data/universe/universe.json": (
        "the traded universe and its per-symbol cost fields. A dropped column is invisible -- "
        "every symbol is still there -- and prices the whole desk off a denomination it guessed. "
        "`currency_profit` was lost from all 251 rows on 2026-08-29 and `tick_value` before it"),
    "docs/GAP_REGISTER.md": (
        "the ranked open-defect list every session reads to choose work. Regenerated from a "
        "partial cycle it drops rows -- and a gap that vanishes reads exactly like a gap closed"),
}


class Snapshot(dict[str, tuple[str, bytes] | None]):
    """path -> (sha256, contents), or None for a member that was absent when taken.

    ABSENT IS RECORDED, NOT SKIPPED. A test that CREATES a protected artifact that did not exist
    is the same defect wearing different clothes: the next commit picks up a file nobody wrote on
    purpose, carrying whatever a test fixture happened to contain.
    """


def snapshot(root: Path | str) -> Snapshot:
    """Read every protected artifact. Cheap: fourteen small files, once per session."""
    base = Path(root)
    snap = Snapshot()
    for rel in PROTECTED:
        p = base / rel
        try:
            raw = p.read_bytes()
        except OSError:
            snap[rel] = None
            continue
        snap[rel] = (hashlib.sha256(raw).hexdigest(), raw)
    return snap


def changed(root: Path | str, snap: Snapshot) -> list[str]:
    """Which protected artifacts differ from the snapshot. Compares CONTENT, never mtime.

    An organ that rewrites a file with identical bytes has done nothing observable and is not a
    defect worth failing a suite over; an editor that touches mtime has not changed the artifact.
    Hashing fourteen small files is fast enough that there is no reason to accept either false
    positive to save the stat.
    """
    base = Path(root)
    out: list[str] = []
    for rel, before in snap.items():
        p = base / rel
        try:
            raw: bytes | None = p.read_bytes()
        except OSError:
            raw = None
        now = None if raw is None else (hashlib.sha256(raw).hexdigest(), raw)
        if (before is None) != (now is None) or (
                before is not None and now is not None and before[0] != now[0]):
            out.append(rel)
    return out


def restore(root: Path | str, rel: str, snap: Snapshot) -> str:
    """Put one protected artifact back as it was. Returns what it did.

    RESTORING IS NOT FORGIVING. The suite still fails: the point of putting the bytes back is that
    the NEXT run starts from a clean tree, so one write does not cascade into a second run that
    ratchets from an already-corrupted baseline while the report blames the second run.
    """
    base = Path(root)
    p = base / rel
    before = snap.get(rel)
    if before is None:
        try:
            p.unlink()
        except OSError:
            return "created-and-could-not-remove"
        return "removed (it did not exist before this run)"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(before[1])
    return "restored to its pre-run contents"
