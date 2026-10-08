"""The box must PULL on a schedule, not as a side effect of losing a push race.

WHY THE BOX RAN CODE NOBODY HAD SHIPPED IT. `sync_shadow_to_git.ps1` fetched only after a push was
REJECTED, so the machine that holds live capital pulled purely as conflict resolution. When its
push SUCCEEDS -- which it does whenever nobody else pushed in the same minute, i.e. almost always
-- it never fetched at all.

MEASURED 2026-09-06: the box's branch was 41 commits behind desk-sync-clean and still running
`GATEWAY_FAMILY_POPULATIONS = ("hunt16",)` (65 of 66 certificates unexecutable) and a
shadow_admission with no CANON_SOURCES (nothing could enrol at all). Both had been fixed days
earlier. The dashboard's CERTIFIED-NOT-ENROLLED rows and its dead certificates were not desk
defects -- they were a DELIVERY defect wearing their clothes.

These tests read the PowerShell rather than run it: there is no pwsh on the research host, and the
property worth fencing is structural anyway. A test that needs the box to be reachable would be a
test that never runs, which is the same class of defect one level up.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_SYNC = _ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def _src() -> str:
    return _SYNC.read_text("utf-8", errors="ignore")


def _code() -> str:
    """The script with COMMENT LINES STRIPPED.

    A source-text fence that greps the whole file breaks on the file's own explanation of itself:
    this script's header says "never rebase, never stash", and a test asserting `"git stash" not
    in src` fails on the sentence promising not to do it. Third time that trap has fired tonight,
    so the helper exists rather than the habit.
    """
    return "\n".join(ln for ln in _SYNC.read_text("utf-8", errors="ignore").splitlines()
                      if not ln.lstrip().startswith("#"))


def test_the_sync_script_exists() -> None:
    """If it moves, every assertion below would vacuously pass on an empty string."""
    assert _SYNC.is_file(), f"{_SYNC} is gone -- the box's delivery path is unfenced"


def test_the_pull_runs_before_every_early_exit() -> None:
    """THE DEFECT, AND IT NEEDED TWO ACCIDENTS AT ONCE.

    The only fetch lived inside the push-rejection retry loop, and BOTH guards above it exit 0
    first: "none of the tracked state files exist yet" and "no change since last sync". So the box
    pulled only when it had state worth committing AND lost a push race. A quiet box never
    contacted origin at all.
    """
    src = _src()
    pull = src.index("Sync-Pull -RepoRoot")
    for guard in ('Write-SyncLog "SKIP: none of the tracked',):
        assert pull < src.index(guard), (
            f"the pull now runs AFTER `{guard[14:50]}...` -- a box with nothing to say stops "
            "receiving code, which is how it ended up 41 commits behind while holding live "
            "capital")
    assert pull < src.index("$ok = Publish-StateOnto -RepoRoot"), "the pull moved after the push"


def test_pulling_depends_on_nothing() -> None:
    """Not on local changes, not on a push, not on a rejection.

    Push stays conditional on having something to push -- an empty commit every fifteen minutes
    is noise. Delivery is not noise, so it is unconditional.
    """
    src = _src()
    head = src[:src.index("Sync-Pull -RepoRoot")]
    assert "git\", \"push" not in head and '"push", "origin"' not in head, (
        "something pushes before the pull -- the pull must not be downstream of a push outcome")


def test_the_functions_are_defined_before_they_are_called() -> None:
    """PowerShell is interpreted top-down: a helper defined below its call site is a runtime
    error on the box and a silent no-op nowhere. There is no pwsh on this host to catch it."""
    src = _src()
    for fn, call in (("Sync-Pull", "Sync-Pull -RepoRoot"),
                     ("Request-Adoption", "Request-Adoption -Branch")):
        assert src.index(f"function {fn}") < src.index(call), (
            f"{fn} is called before it is defined")


def _sync_pull_body() -> str:
    """The body of `Sync-Pull` only.

    Both fences below are about what the PULL does on failure. Grepping the whole file would pass
    on the push loop's own fetch handling, which is a different code path with a different correct
    answer -- the push path may abort, the pull path may not.
    """
    src = _src()
    start = src.index("function Sync-Pull")
    return src[start:src.index("\n}", start)]


def test_a_failed_fetch_does_not_abort_the_sync() -> None:
    """A network blink must not cost state publication.

    The old behaviour (push, fetch only on rejection) is still a correct fallback, so a failed
    pull degrades to it rather than aborting. Refusing to sync because a fetch failed would trade
    a delivery bug for an availability one -- and on this box, not publishing means the dashboard
    stops being told anything at all.
    """
    body = _sync_pull_body()
    fail = body.index("fetch failed rc=")
    terminal_fail = body.index("if ($rc -ne 0)", fail)
    terminal_block = body[terminal_fail:body.index("\n    }", terminal_fail)]
    assert "return" in terminal_block, (
        "a failed fetch no longer returns -- if it exits or throws, one unreachable minute of "
        "network costs the box its commit AND its push, which is strictly worse than the bug "
        "this pull was added to fix")
    assert "exit" not in terminal_block, (
        "the fetch-failure path exits; delivery is best-effort, publication is not")


def test_inbound_code_is_delegated_to_the_release_adopter() -> None:
    """The publisher must never own an inbound merge.

    Task Scheduler can terminate the parent publisher while a child Git merge remains alive.
    That orphan releases the mutex with its parent but keeps the index lock, so the canonical
    adopter collides with it. Inbound code belongs exclusively to MT5-AdoptRelease.
    """
    body = _sync_pull_body()
    assert "Request-Adoption -Branch $Branch" in body
    assert "Merge-FetchHead -RepoRoot" not in body
    src = _src()
    assert 'Start-ScheduledTask -TaskName "MT5-AdoptRelease"' in src
    assert "if ($script:InboundAdoptionRequired)" in src


def test_no_publisher_path_invokes_the_legacy_merge_helper() -> None:
    """The retained helper documents the old recovery path but must have no callers."""
    src = _src()
    assert src.count("function Merge-FetchHead") == 1
    assert "Merge-FetchHead -RepoRoot" not in src


def test_inbound_code_after_a_commit_is_still_left_to_the_adopter() -> None:
    """The one delivery path never merges; a pass that saw inbound code says the adopter owns it."""
    src = _src()
    tail = src[src.index("# ONE DELIVERY PATH"):]
    assert "if ($script:InboundAdoptionRequired)" in tail
    assert "inbound code is left to MT5-AdoptRelease" in tail
    assert "Merge-FetchHead -RepoRoot" not in tail

def test_dirty_files_are_parked_and_restored_never_discarded() -> None:
    """universe.json is a protected registry whose records may not vanish, and R0423 forbids
    `git stash` in a shared tree. The parked copies must be restored, not dropped."""
    code = _code()
    assert "Copy-Item" in code and "$parked" in code
    assert "stash" not in code, "R0423: never stash in a shared tree"


def test_merge_blockers_are_read_from_one_native_merge_probe() -> None:
    """Large discovery fetches must not monopolise the global Git-writer mutex.

    The old loop ran ``git status`` separately for every incoming path. A 38k-path fetch could
    therefore consume the Windows task's entire ten-minute allowance while holding the mutex,
    preventing the canonical release adopter from ever starting. Whole-tree and bounded-path dirty
    scans also failed on the multi-million-path box. Git's own merge preflight already identifies
    tracked and untracked blockers in one index-native operation, so both lists must come from it.
    """
    code = _code()
    start = code.index("function Merge-FetchHead")
    body = code[start:code.index("\n}", start)]
    assert "-c merge.autoStash=false merge --no-commit --no-ff FETCH_HEAD" in body
    assert "local changes to the following files would be overwritten" in body
    assert "untracked working tree files would be overwritten" in body
    assert "$probeRc" in body and "$blockers" in body and "$untracked" in body
    assert "status --porcelain -- $rel" not in body
    assert "diff --name-only --no-ext-diff HEAD" not in body


def test_sync_log_does_not_contaminate_boolean_function_results() -> None:
    """PowerShell returns every success-stream object a function emits.

    A log line emitted with Write-Output plus ``$false`` becomes a truthy array, causing the caller
    to report a refused merge as successful. Task output belongs on the host stream instead.
    """
    code = _code()
    start = code.index("function Write-SyncLog")
    body = code[start:code.index("\n}", start)]
    assert "Write-Host $line" in body
    assert "Write-Output $line" not in body
