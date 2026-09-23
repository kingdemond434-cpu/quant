"""Seven state files at the desk root read as CODE, and that is what stopped the box sealing.

`libs.ops.release.is_state_path` decides whether a changed path is EVIDENCE (the box's own
records, which the box owns and pushes up) or CODE (which origin owns and the box adopts). Every
entry in `STATE_PREFIXES` ends in a directory, so a state artifact written beside the code rather
than inside `data/` fell to the code side.

MEASURED ON THE BOX 2026-09-10, on the first adoption that reached the current branch after the
`.git` ACL repair -- the run that was supposed to end weeks of the box trading stale code:

    ADOPT RELEASE
      head   ad5a23551b0a
      target 5cd23afe8932
      adopting 183 path(s) in place...
      wrote 85 modified, 4 added, 0 deleted in place
      kept 94 state path(s) this box wrote since it diverged

    REFUSING to record the merge: 9 path(s) still differ from the target.
        desks/mt5/gateway_state.json      desks/mt5/portfolio_projection.json
        desks/mt5/hunt11.json             desks/mt5/regime_state.json
        desks/mt5/mech_battery.json       desks/mt5/sync_marker.json
        desks/mt5/mech_split.json         desks/mt5/research/_sum6.py
                                          desks/mt5/research/free_shadows.py
    adopt-and-seal: Adopt-Release exited 1 -- partial adoption; NOT sealing a tree that only
    half-matches the branch

THE REFUSAL IS RIGHT AND THE CLASSIFICATION UNDER IT WAS WRONG. `merge -s ours` writes down a
parent and keeps this tree, so recording it while the tree still differs would bury the
difference under a commit claiming to contain it. Refusing is correct. But seven of those nine
are a gateway state file, a regime stamp, a cycle marker and four sweep outputs -- evidence by
every word of the paragraph `STATE_PREFIXES` is documented with -- sitting at the desk root only
because one commit put them there in August (aa90ee81) and nothing moved them.

AND IT WAS PERMANENT, NOT A BAD DAY. The box rewrites those files, so the drift reappears every
pass: adoption refuses, the seal is never recorded, the gateway is never restarted, and the box
goes on running code from before whatever fix was just adopted. That is the "tested fixes
remained undeployed while older bugs kept running" line of the operator's own assessment, with a
mechanism under it.

TWO LISTS IN TWO LANGUAGES, PINNED TO EACH OTHER. `Adopt-Release.ps1` cannot import Python, so it
carries the same list in PowerShell. A test that reads both is the only thing that stops them
drifting -- and a divergence here is invisible until an adoption refuses on a live box.

THE NINTH PATH WAS DEAD SCRATCH. `desks/mt5/research/_sum6.py` was nine lines with no importer,
reading a report that no longer has that shape, carrying a UTF-8 BOM -- which made it invisible
to `ast.parse` and was the sole cause of a failing cohort-integrity test. Deleting it closed the
test and removed a blocking path in the same stroke. `free_shadows.py` is the opposite and is
left alone: 230 lines, imported by `run_gateway_loop`, live code that must converge by being
adopted rather than by being exempted.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import release  # noqa: E402

PS1 = _ROOT / "desks" / "mt5" / "scripts" / "Adopt-Release.ps1"

#: The exact nine the box refused on, kept verbatim so this test still names the real event.
REFUSED_ON_THE_BOX = (
    "desks/mt5/gateway_state.json", "desks/mt5/hunt11.json", "desks/mt5/mech_battery.json",
    "desks/mt5/mech_split.json", "desks/mt5/portfolio_projection.json",
    "desks/mt5/regime_state.json", "desks/mt5/research/_sum6.py",
    "desks/mt5/research/free_shadows.py", "desks/mt5/sync_marker.json",
)


def test_the_seven_desk_root_records_are_state():
    """Each is evidence the box writes and owns. Before this they classified as code, so the
    box's own copy read as unexplained drift."""
    for rel in REFUSED_ON_THE_BOX:
        if rel.endswith(".py"):
            continue
        assert release.is_state_path(rel), f"{rel} still classifies as CODE"


def test_live_code_at_the_desk_root_is_still_code():
    """The exemption must not creep. `free_shadows.py` is imported by run_gateway_loop and is the
    reason an exact-path list was used instead of a `desks/mt5/` prefix: a prefix would have
    classified gateway.py, decision_core.py and every family as state, which is the identity
    fence disarmed rather than corrected."""
    for rel in ("desks/mt5/research/free_shadows.py", "desks/mt5/mt5desk/gateway.py",
                "desks/mt5/mt5desk/decision_core.py", "desks/mt5/research/pf_allocator.py",
                "desks/mt5/research/hourly_cycle.py"):
        assert not release.is_state_path(rel), f"{rel} was classified as STATE"


def test_no_state_file_entry_is_a_python_source():
    """A .py on this list would be code the box may keep against origin -- the exact divergence
    the whole adopt-and-seal machine exists to end."""
    bad = sorted(p for p in release.STATE_FILES if p.endswith(".py"))
    assert bad == [], f"code exempted as state: {bad}"


def test_every_state_file_is_under_the_desk_and_absolute_from_the_repo_root():
    for p in release.STATE_FILES:
        assert p.startswith("desks/mt5/"), f"{p} is not a desk path"
        assert not p.startswith("/") and "\\" not in p, f"{p} is not repo-relative posix"
        assert not any(p.startswith(pre) for pre in release.STATE_PREFIXES), (
            f"{p} is already covered by a prefix; listing it twice makes the list lie about "
            f"what it is for")


def test_the_powershell_side_carries_the_same_list():
    """`Adopt-Release.ps1` cannot import Python and decides this on the box. Two copies of one
    rule drift silently, and the drift only shows up as a live adoption refusing to seal."""
    src = PS1.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\$StateFiles\s*=\s*@\((.*?)\)", src, re.S)
    assert m, "Adopt-Release.ps1 has no $StateFiles list"
    ps_files = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert ps_files == set(release.STATE_FILES), (
        "the PowerShell and Python state-file lists disagree: "
        f"only in ps1={sorted(ps_files - set(release.STATE_FILES))}, "
        f"only in release.py={sorted(set(release.STATE_FILES) - ps_files)}")


def test_the_powershell_test_consults_the_list_before_the_prefixes():
    """Present but unread is the same as absent, and it is the failure mode this desk names most
    often. The membership check must be inside Test-StatePath."""
    src = PS1.read_text(encoding="utf-8", errors="replace")
    body = src.split("function Test-StatePath", 1)[1].split("\n}", 1)[0]
    assert "$StateFiles -contains" in body, (
        "Test-StatePath does not consult $StateFiles, so the list is declared and never read")


def test_the_dead_scratch_file_is_gone_from_the_tree():
    """Nine lines, no importer, a UTF-8 BOM that hid it from every AST tool on the desk, and one
    of the nine paths blocking the seal. It was also the sole cause of a failing cohort-integrity
    test, so removing it closed a red test and a live stall at once."""
    assert not (_ROOT / "desks" / "mt5" / "research" / "_sum6.py").exists()
    tracked = subprocess.run(["git", "ls-files", "desks/mt5/research/_sum6.py"],
                             cwd=_ROOT, capture_output=True, text=True, check=False)
    assert not tracked.stdout.strip(), "_sum6.py is still tracked"


def test_no_tracked_python_file_carries_a_bom_any_more():
    """The guard that _sum6.py was failing. It is asserted here too because the fix was a
    deletion, and a deletion is the kind of repair that gets quietly reverted by a sync."""
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=_ROOT,
                         capture_output=True, text=True, check=False)
    bad = []
    for rel in out.stdout.splitlines():
        p = _ROOT / rel
        if p.is_file() and p.read_bytes()[:3] == b"\xef\xbb\xbf":
            bad.append(rel)
    assert bad == [], f"BOM-prefixed sources are invisible to ast.parse: {bad}"
