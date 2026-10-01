"""The large intelligence transfer must not monopolise the worktree/index writer lock."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "intel_ship_adopt.ps1"


def _code() -> str:
    return "\n".join(line for line in SCRIPT.read_text("utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def test_network_fetch_precedes_the_writer_mutex() -> None:
    code = _code()
    # The fetch carries `-c maintenance.auto=false -c gc.auto=0` since 8dc29efac (so no detached
    # maintenance outlives it), which sits between `git` and `fetch`; match the invocation, not
    # the exact spelling of its config flags.
    found = re.search(r"&\s*git\b[^\n]*?\bfetch --no-write-fetch-head", code)
    assert found, "the intelligence transport fetch is gone"
    fetch = found.start()
    lock = code.index("Open-GitWriterMutex")
    wait = code.index("WaitOne(540000)")
    checkout = code.index("git checkout $shipRef")
    assert fetch < lock < wait < checkout


def test_transport_fetch_uses_a_dedicated_ref_not_fetch_head() -> None:
    code = _code()
    assert '$shipRef = "refs/remotes/intel-ship/send"' in code
    assert '"+refs/heads/intel-ship/send:$shipRef"' in code
    assert "git checkout FETCH_HEAD" not in code
    assert "git rev-parse --short FETCH_HEAD" not in code
