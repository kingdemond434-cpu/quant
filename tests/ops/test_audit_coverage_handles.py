"""build_audit_coverage.refresh() must not leak the file handles it counts lines with.

WHY THIS IS A TEST AND NOT A TIDY-UP. `sum(1 for _ in p.open(...))` closed only when CPython's
refcount happened to reap it, and it emitted a ResourceWarning on the way. This repo sets
`filterwarnings = error`, so the warning was a hard test failure for anything that reached
refresh() -- which is load(), record_blank(), tune_budget() and audit_payload(), i.e. the whole
coverage ledger AND the panel's per-dead-seat failure handler, which calls record_blank once per
seat. Net effect: the panel's total-failure path was structurally untestable, and it is exactly
the path that shipped the R0343 exit-code bug. The leak did not corrupt data; it removed the
ability to observe a code path, which is the more expensive failure.

HOW THE ASSERTION FIRES, since it is not an `assert`. A ResourceWarning from a deallocator is
raised inside __del__, so it is UNRAISABLE -- `warnings.simplefilter("error")` cannot propagate
it and a test written that way passes with or without the leak. pytest's unraisableexception
plugin is what makes it observable: it converts the unraisable into a
PytestUnraisableExceptionWarning, which this repo's `filterwarnings = error` then turns into a
failure. So the mechanism is the plugin, and the test body must simply reach the code and let it
fire. VERIFIED BOTH WAYS 2026-08-12: reverted to the leaking line, this test FAILS with
PytestUnraisableExceptionWarning; with the fix it passes.
"""
from __future__ import annotations

from scripts import build_audit_coverage as bac


def test_refresh_closes_every_file_it_counts(tmp_path, monkeypatch):
    src = tmp_path / "a.py"
    src.write_text("one\ntwo\nthree\n", "utf-8")
    monkeypatch.setattr(bac, "ROOT", tmp_path)
    monkeypatch.setattr(bac, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(bac, "_eligible", lambda: [src])

    m = bac.refresh({"files": {}})

    assert m["files"]["a.py"]["loc"] == 3          # still counts what it counted before


def test_a_budget_arm_that_cannot_move_says_so(tmp_path, monkeypatch):
    """THE WELD (measured 2026-08-12). The budget sat at exactly CODE_BUDGET_MIN while the last
    eight firings carried 2-4 blanks of 4: max(40_000, int(40_000*0.6)) is 40_000, so the shrink
    arm moved nothing eight times and the history read `from 40000 to 40000` -- indistinguishable
    from a budget that adapted. That weld is why the same free seats blank forever: they fail on
    a 40k payload and the response that exists to shrink it cannot.

    This asserts VISIBILITY, not slack -- `new` is unchanged and the floor is not lowered."""
    monkeypatch.setattr(bac, "MANIFEST", tmp_path / "m.json")
    monkeypatch.setattr(bac, "_eligible", lambda: [])
    monkeypatch.setattr(bac, "ROOT", tmp_path)
    bac.save({"files": {}, "code_budget_chars": bac.CODE_BUDGET_MIN})

    new = bac.tune_budget(blanked=3, total=4)

    assert new == bac.CODE_BUDGET_MIN                 # floor HELD -- nothing loosened
    h = bac.load()["budget_history"][-1]
    assert h["welded_at"] == "floor"                  # ...and the inertness is on the record
    assert h["wanted"] < h["to"]


def test_a_moving_arm_is_not_marked_welded(tmp_path, monkeypatch):
    """The marker must appear only when the arm was actually inert, or it is noise."""
    monkeypatch.setattr(bac, "MANIFEST", tmp_path / "m.json")
    monkeypatch.setattr(bac, "_eligible", lambda: [])
    monkeypatch.setattr(bac, "ROOT", tmp_path)
    bac.save({"files": {}, "code_budget_chars": bac.CODE_BUDGET_MIN * 4})

    new = bac.tune_budget(blanked=1, total=4)

    assert new < bac.CODE_BUDGET_MIN * 4              # it really shrank
    assert "welded_at" not in bac.load()["budget_history"][-1]
