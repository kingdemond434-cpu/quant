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
