"""THE BOX'S STATE LIVES IN ONE PLACE, AND IT IS NOT THE CHECKOUT YOU HAPPEN TO BE IN (L1.55).

Every artifact that records what this BOX has actually done -- capital events, the execution tape,
the executor's published book, the kill file -- is gitignored (`.gitignore:11: data/*`). It is
therefore ABSENT from a linked worktree, by construction and on every single one.

That collides head-on with the desk's own standing order. R0423 has NINE recorded instances of two
sessions corrupting each other in a shared checkout, and the fix the desk mandates for all work --
including money-path work -- is `git worktree add`. So the environment in which this desk requires
its money-path changes to be made is exactly the environment in which its money-path state reads
as absent.

WHAT THAT COSTS, MEASURED 2026-08-19. `scripts/check_change_window.py` -- the L1.38 sterile-cockpit
gate -- resolves an absent `data/capital_events.jsonl` to "pre-launch: no capital event recorded,
so no live capital can be harmed by a money-path change" and returns OPEN, explicitly clearing its
own `unmeasured` list on the way past. Run in the main checkout the same fence returns STERILE:
RAIL_BREACH, CASHCARRY_KILL latched since 2026-08-15, 18.1 days since launch, 533 live fills. Same
commit, same box, same minute, opposite verdicts -- and the one that says "change the money path
freely" is the one every worker sees, because every worker was ordered into a worktree.

THE DISTINCTION THIS RESTORES, and it is the desk's most-repeated defect class (WS-005, L1.28a,
GAP_REGISTER #111): "this file is absent because nothing ever wrote it" and "this file is absent
because it is gitignored and I am not looking at the box" are different facts. Only the first is
evidence of anything. Collapsing them let an ABSENT input manufacture a clean verdict on the one
gate standing between a live rail breach and an unvalidated money-path change.

WHY RESOLVE RATHER THAN REFUSE. Refusing (UNMEASURED -> treated as STERILE) would be safe and
would also be wrong most of the time: it would freeze the money path for every worker in every
worktree on a box that is genuinely pre-launch, which is L1.28's timidity in fence costume. The
box's real data root is CHEAPLY AND EXACTLY KNOWABLE -- a linked worktree's `.git` is a file
naming the main worktree's gitdir -- so the honest move is to go and read the real answer. Refusal
is kept for the case where resolution genuinely fails, and there it is the correct conservative
direction, because a wrong OPEN costs unbounded real capital and a wrong STERILE costs a delayed
improvement.

THIS MODULE MOVES NO THRESHOLD AND OPENS NO GATE. It changes only WHERE a caller looks for the
box's state, so that a verdict about live capital is computed from the box that holds the capital.
On the main checkout every call here is a no-op returning the root it was handed.
"""
from __future__ import annotations

from pathlib import Path

#: How the data root was established. A caller that treats an ABSENT input as evidence about the
#: world (rather than merely about its own visibility) MUST check this first -- absence is only
#: informative when the basis is a resolved one.
OWN = "OWN"                     # this checkout is the main worktree (or an explicit test root)
MAIN_WORKTREE = "MAIN_WORKTREE"  # linked worktree: resolved to the main checkout that holds state
UNRESOLVED = "UNRESOLVED"        # a linked worktree whose main checkout could not be located

_RESOLVED = frozenset({OWN, MAIN_WORKTREE})

#: The marker git writes into a linked worktree's `.git` FILE. The main worktree root is the path
#: before `/.git/worktrees/<name>`. Parsed rather than shelled out to `git rev-parse
#: --git-common-dir` deliberately: this runs inside fences that must not depend on a subprocess
#: succeeding to reach a correct answer, and a fence that needs git to be healthy in order to say
#: "a rail is live" has a failure mode pointed the wrong way.
_GITDIR_PREFIX = "gitdir:"
_WORKTREES_SEG = "/.git/worktrees/"


def data_root(root: Path) -> tuple[Path, str]:
    """The box's real data root for `root`, and the BASIS on which it was established.

    Returns (path, basis). `basis` is OWN / MAIN_WORKTREE / UNRESOLVED -- never collapsed, because
    the whole point is that a caller can tell whether an absent file under the returned path is
    evidence about the box or evidence about its own vantage point.

    A root with no `.git` at all is OWN: that is a caller pointing us explicitly at a directory
    (every test does this), and second-guessing an explicit instruction would be its own defect.
    """
    dotgit = root / ".git"
    if not dotgit.is_file():
        # A real `.git` DIRECTORY is the main worktree; no `.git` is an explicit caller-supplied
        # root. Both mean: the place you were handed is the place to read.
        return root, OWN
    try:
        raw = dotgit.read_text("utf-8").strip()
    except (OSError, UnicodeDecodeError):
        # UnicodeDecodeError subclasses ValueError, NOT OSError -- caught by this module's own
        # test, which is the point of writing the refusal path a test can reach. A corrupt `.git`
        # must resolve to UNRESOLVED; crashing here would take the fence down instead, and a fence
        # that dies is a fence that enforces nothing (L1.37).
        return root, UNRESOLVED
    if not raw.startswith(_GITDIR_PREFIX):
        return root, UNRESOLVED
    gitdir = raw[len(_GITDIR_PREFIX):].strip()
    head, sep, _ = gitdir.partition(_WORKTREES_SEG)
    if not sep:
        # A `.git` file that is not a linked worktree (a submodule, say). We do not know where
        # this box keeps its state, and guessing is how a fabricated verdict gets made.
        return root, UNRESOLVED
    main = Path(head)
    if not (main / ".git").is_dir():
        # The main checkout named by the marker is gone or moved. UNRESOLVED, never a silent
        # fallback to this worktree -- that fallback IS the defect this module exists to remove.
        return root, UNRESOLVED
    return main, MAIN_WORKTREE


def resolved(basis: str) -> bool:
    """Is `basis` one on which an ABSENT file may be read as evidence about the box?"""
    return basis in _RESOLVED


def describe(root: Path, basis: str) -> str:
    """One line a fence can put in its report so the vantage point is never implicit."""
    if basis == OWN:
        return f"box state read from this checkout ({root})"
    if basis == MAIN_WORKTREE:
        return (f"box state read from the main checkout ({root}) -- this is a linked worktree and "
                "data/ is gitignored, so its own data/ is empty by construction, not by history")
    return (f"box state NOT resolvable from this linked worktree ({root}): the main checkout named "
            "by .git could not be located, so an absent artifact is evidence of nothing")
