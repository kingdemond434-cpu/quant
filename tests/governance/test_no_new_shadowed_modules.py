"""TWO FILES WITH ONE MODULE NAME MEAN sys.path ORDER DECIDES WHICH CODE RUNS.

THE TRAP, and it has fired at least three times on this desk. `desks/mt5/` and
`desks/mt5/research/` are BOTH on sys.path, so `import run_hunt12` resolves to whichever directory
comes first -- a property of the importing process, not of the code. The two copies then diverge:
the missing-import repair of 2026-08-19 landed in `research/run_hunt12.py` only, and
`portfolio_projection` diverged so far that the top-level copy died on its first data read because
`Path(__file__).parent.parent` means something different one directory up.

WHAT MAKES IT EXPENSIVE IS THE DIAGNOSIS, NOT THE FAILURE. The stale copy fails in a way that looks
exactly like a bug in the live one. Reading the top-level `portfolio_projection` crash and
concluding "the projection is unrunnable" was wrong and cost a round trip; a test asserting on the
live loader silently imported the superseded stub and reported "has no attribute BASE", which reads
like the live module lost an attribute rather than like the wrong file was opened.

RATCHETED, NOT ZERO, AND DELIBERATELY SO. Five of the six known duplicates are still real diverged
copies rather than stubs. Deleting them is the right end state and is NOT this fence's business:
the Windows box may invoke them by path, and that cannot be verified from a container with no
access to it. What this fence does is stop the set GROWING while that verification is pending --
a new shadowed module is a new instance of a trap the desk has already paid for three times.

To clear a name from the list: delete the stale copy, or turn it into a refusing stub that names
its replacement (as `desks/mt5/portfolio_projection.py` already is), then lower MAX_SHADOWED.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

#: Directories that are BOTH importable as roots, so a module name in two of them is ambiguous.
_IMPORT_ROOTS = ("desks/mt5", "desks/mt5/research")

#: Module names living at more than one import root. RATCHET: may fall, never rise. 5, measured
#: 2026-09-05 -- portfolio_projection is excluded because its top-level copy has already been
#: converted into a stub that refuses to run and names its replacement, which is the fix.
MAX_SHADOWED = 5


def _shadowed() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = defaultdict(list)
    for root in _IMPORT_ROOTS:
        base = _ROOT / root
        if not base.is_dir():
            continue
        for p in base.glob("*.py"):
            if p.name == "__init__.py":
                continue
            seen[p.stem].append(f"{root}/{p.name}")
    out = {}
    for name, paths in seen.items():
        if len(paths) < 2:
            continue
        # A copy that REFUSES to run is not a shadow -- it is the documented fix. It cannot be
        # imported and silently used in place of the live module, which is the whole hazard.
        live = [q for q in paths
                if "SUPERSEDED" not in (_ROOT / q).read_text("utf-8", errors="ignore")[:2000]]
        if len(live) > 1:
            out[name] = sorted(paths)
    return out


def test_no_new_module_name_exists_at_two_import_roots() -> None:
    shadowed = _shadowed()
    assert len(shadowed) <= MAX_SHADOWED, (
        f"{len(shadowed)} module names exist at more than one import root, above the ratchet of "
        f"{MAX_SHADOWED}. sys.path ORDER then decides which code runs, the copies diverge, and the "
        f"stale one fails in a way that looks like a bug in the live one:\n  "
        + "\n  ".join(f"{n}: {ps}" for n, ps in sorted(shadowed.items())))


def test_the_ratchet_is_not_slack() -> None:
    """A ratchet set above the real count is a ratchet that never binds.

    Without this, MAX_SHADOWED could be raised to 20 in the same commit that adds a duplicate and
    the fence above would keep passing -- which is how a ratchet becomes a comment.
    """
    assert len(_shadowed()) == MAX_SHADOWED, (
        f"the real count is {len(_shadowed())} and the ratchet says {MAX_SHADOWED}. If a duplicate "
        "was cleared, lower the ratchet in the same commit.")


def test_the_documented_stub_is_not_counted_as_a_shadow() -> None:
    """L1.28a in miniature: the exemption must be earned by the file, not assumed.

    `desks/mt5/portfolio_projection.py` is exempt because it REFUSES to run and names its
    replacement. If someone restores a runnable body to it, the exemption must evaporate rather
    than persist because a test once decided it was fine.
    """
    stub = _ROOT / "desks/mt5/portfolio_projection.py"
    body = stub.read_text("utf-8")
    assert "SUPERSEDED" in body, "the stub stopped declaring itself superseded"
    assert "portfolio_projection" not in _shadowed(), (
        "a refusing stub is being counted as a live shadow -- the exemption check is broken")
