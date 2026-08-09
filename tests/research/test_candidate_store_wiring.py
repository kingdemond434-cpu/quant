"""The lab candidate store must be READ, and rejects must never be promoted (R0079).

WHY THESE EXIST. Four readers -- `run_promotion_queue`, `run_generation_diversity`, and both §42
capacity audits in `max_audit` -- pointed at `data/research_memory.db`, a path NOTHING in this
repo has ever written. That is the READ-WITHOUT-WRITER class (L1.40) and its signature is that it
never crashes: each reader took its empty branch and published a plausible zero. The promotion
queue reported 
_candidates: 0` every six hours, the collapse detector reported PERFECT diversity
(entropy 1.0) over an empty batch, and the two capacity audits reported OK for their entire
existence without having read a single candidate.

The repoint alone would have been actively harmful, which is the part worth pinning. The store
holds 1,673 candidates and every one is `survived = 0`; `run_promotion_queue._candidates` read
`store.survivors() or store.all()`, so the instant the path was corrected that `or` would have
fed 1,673 GAUNTLET-REJECTED candidates into the forward-slot queue as promotion inventory -- a
dormant defect converted into a live phantom-edge factory by a one-line path fix. The two changes
are therefore inseparable, and these tests fail if either half is reverted alone.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from scripts import max_audit, run_generation_diversity, run_promotion_queue


def _code_only(module) -> str:
    """Module source with every comment and string literal removed.

    Structural assertions below MUST NOT see prose. The first draft of this file matched raw
    source text and three of its assertions failed against the very comments that explain the
    fix -- a test that greps a file cannot tell a banned construct from a note saying "this
    construct is banned", so it reports a defect precisely where the defect is documented.
    """
    src = Path(module.__file__).read_text("utf-8")
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


class _FakeStore:
    """Mimics CandidateStore's two accessors with a knowable split."""

    def __init__(self, n_all: int, n_survivors: int) -> None:
        self._all = [f"cand-{i}" for i in range(n_all)]
        self._surv = self._all[:n_survivors]

    def all(self):
        return list(self._all)

    def survivors(self):
        return list(self._surv)


# --------------------------------------------------------------------- the paths are real paths

@pytest.mark.parametrize(
    ("module", "name", "expected"),
    [(run_promotion_queue, "_DB", "sor_crypto.sqlite"),
     (run_generation_diversity, "_DB", "sor_research.sqlite"),
     (max_audit, "_CANDIDATE_DB", "sor_research.sqlite")],
)
def test_reader_does_not_point_at_the_phantom_path(module, name, expected):
    """No reader may name research_memory.db again -- nothing has ever written it."""
    path = Path(getattr(module, name))
    assert path.name != "research_memory.db", (
        f"{module.__name__}.{name} points at the phantom store. Nothing in this repo writes it, "
        "so the reader will silently report a zero rather than fail.")
    assert path.name == expected


def test_the_two_capacity_audits_share_one_reader():
    """Two copies of a path is how one gets repointed and the other does not.

    Scoped to the two §42 capacity checks on purpose. `max_audit` legitimately opens the same
    sqlite file directly in four other checks, and asserting on the whole module would fail on
    code this change never touched -- a gate that cries wolf gets switched off.
    """
    import inspect
    for check in (max_audit.check_capacity_hunt, max_audit.check_capacity_runway):
        body = inspect.getsource(check)
        code = " ".join(
            t.string for t in tokenize.generate_tokens(io.StringIO(body).readline)
            if t.type not in (tokenize.COMMENT, tokenize.STRING))
        assert "_scored_capacities" in code, (
            f"{check.__name__} no longer reads through the shared _scored_capacities reader")
        assert "CandidateStore" not in code, (
            f"{check.__name__} constructs its own store again -- the duplication that let one "
            "call site keep a phantom path while the other was fixed")


# ------------------------------------------------------- rejects are never promotion inventory

def test_promotion_queue_never_falls_back_to_rejected_candidates(monkeypatch):
    """THE LOAD-BEARING ONE. Zero survivors must yield zero candidates, never `all()`."""
    store = _FakeStore(n_all=1673, n_survivors=0)
    monkeypatch.setattr(run_promotion_queue, "_DB", Path(__file__))  # any existing path
    monkeypatch.setattr(
        "libs.autodiscovery.memory.CandidateStore", lambda _db: store, raising=False)
    monkeypatch.setattr("libs.store.connection.Database", lambda *a, **k: object(), raising=False)

    assert run_promotion_queue._candidates() == [], (
        "a store with 1,673 rejects and 0 survivors produced promotion candidates -- the "
        "`survivors() or all()` fallback is back, and the forward-slot queue is now ranking "
        "gauntlet-REJECTED candidates as promotion inventory")


def test_promotion_queue_source_contains_no_all_fallback():
    """Pin the shape too: the bug was one `or`, and a behavioural test can be monkeypatched past."""
    code = _code_only(run_promotion_queue)
    assert "survivors ( ) or store . all ( )" not in code, (
        "the `survivors() or store.all()` fallback is back in run_promotion_queue")
    assert "store . survivors ( )" in code


def test_generation_diversity_deliberately_keeps_all(monkeypatch):
    """The MIRROR of the rule above, and it is not an inconsistency.

    Diversity is a property of what the desk GENERATES, so rejects belong in the sample; filtering
    to survivors here would measure the gauntlet rather than the generator, and would read as
    perfect diversity for the same reason the phantom path did -- an empty batch.
    """
    store = _FakeStore(n_all=200, n_survivors=0)
    monkeypatch.setattr(run_generation_diversity, "_DB", Path(__file__))
    monkeypatch.setattr(
        "libs.autodiscovery.memory.CandidateStore", lambda _db: store, raising=False)
    monkeypatch.setattr("libs.store.connection.Database", lambda *a, **k: object(), raising=False)

    rows, _gens = run_generation_diversity._batch()
    assert len(rows) == 200, "generation diversity must sample rejects too -- it measures the "\
                             "generator, not the gauntlet"


# ------------------------------------------------------------- an unreadable store is UNMEASURED

def test_unreadable_store_is_a_defect_not_a_silent_pass(monkeypatch):
    """REFUSAL HAS ITS OWN VOCABULARY (L1.41). A read that raises must not read as green."""
    monkeypatch.setattr(max_audit, "_CANDIDATE_DB", Path("/nonexistent/sor_research.sqlite"))
    caps, names, err = max_audit._scored_capacities()
    assert (caps, names) == ([], [])
    assert "absent" in err

    for check in (max_audit.check_capacity_hunt, max_audit.check_capacity_runway):
        defects: list = []
        check(defects)
        assert [k for k, _ in defects] == ["capacity-store-unreadable"], (
            f"{check.__name__} reported no defect on an unreadable store -- that is the exact "
            "state that looked identical to green for as long as the reader was broken")


def test_a_raising_store_is_reported_with_its_exception(monkeypatch):
    """The original bug -- CandidateStore(Path) -- raised, and the raise was swallowed."""
    monkeypatch.setattr(max_audit, "_CANDIDATE_DB", Path(__file__))  # exists, wrong contents

    def _boom(_db):
        raise AttributeError("'PosixPath' object has no attribute 'execute'")

    monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", _boom, raising=False)
    monkeypatch.setattr("libs.store.connection.Database", lambda *a, **k: object(), raising=False)

    caps, _names, err = max_audit._scored_capacities()
    assert caps == []
    assert "AttributeError" in err and "execute" in err, (
        "the exception text must survive into the defect -- swallowing it is what hid a type "
        "error in two audits for their entire existence")


# ------------------------------------------------------------------ one book size, and it is live

def test_capacity_hunt_bands_against_the_live_book_not_a_literal():
    """A ratio measured against a hardcoded number is the flat-floor bug one step removed.

    `check_capacity_hunt` banded against a module constant of $50,000 while its sibling
    `check_capacity_runway` banded the SAME candidates against `live_book_usd()` -- two answers to
    the one number every capacity band is a ratio to, in adjacent functions.
    """
    assert not hasattr(max_audit, "DESK_BOOK_USD"), (
        "the audit's private copy of the book size is back; capacity bands must divide by "
        "capacity_policy.live_book_usd(), which already falls back safely on a missing NAV chain")
    code = _code_only(max_audit)
    assert "DESK_BOOK_USD" not in code
