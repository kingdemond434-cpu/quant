"""L1.48 ENFORCEMENT: no calendar gate may stand in for a confidence bar, and none may hide.

WHY A SCANNER AND NOT A CHECKLIST. A hand-written list of offending sites is stale the moment
someone adds the fifteenth. L1.48 binds code NOT YET WRITTEN, so its enforcement has to be
mechanical or it is decoration -- the same reason the doctrine fence strings are checked rather
than trusted. This scans the tree, and the list it prints IS the migration checklist: authoritative
because it is derived from the code rather than from anyone's memory of the code.

HOW A SITE CLEARS THIS CHECK. Either it stops gating on calendar time -- ask
libs/research/evidence_clock.sufficient() for sample size and t-statistic instead -- or it declares
which of L1.48's three exemptions it claims, with a tag on the same line or the line above:

    CLOCK-EXEMPT(physical):    venue or physical reality -- funding stamps, rate limits, maker rest
                               times, data release lags. The world imposes these; we do not.
    CLOCK-EXEMPT(data-window): a data-window DEFINITION such as an out-of-sample split boundary or
                               a collector lookback. Defines which rows exist, gates nothing.
    CLOCK-EXEMPT(attestation): a principal law measuring a NON-STATISTICAL claim. The 7-day Gate 0
                               soak floor is the type case: it attests the desk RUNS UNATTENDED,
                               which no t-statistic can express, so swapping it would be a category
                               error rather than a modernisation.

The tag is deliberately a claim a human must write and a reviewer can dispute. It cannot be
satisfied by renaming a constant, and an untagged constant is a DEFECT by L1.48 regardless of
whether its author believed it was fine.

WHAT IT REFUSES TO DO. It does not auto-exempt anything by filename, directory, or "looks like
infrastructure". Every exemption is explicit and attributable. A scanner that quietly forgives
whole directories would recreate exactly the invisible-waiting problem L1.48 exists to end.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.denominator import record  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402

_PASSING = frozenset({"CLEAN"})

#: Constant assignments whose NAME implies a calendar gate.
_CONST = re.compile(
    r"^\s*(_?[A-Z][A-Z0-9_]*(?:DAYS|WARMUP|WARM_IN|BURN_IN|PROBATION|COOLDOWN|GRACE|LATENCY_D"
    r"|_D|CLOCK|TREADMILL|REENTRY|SUSTAIN))\s*(?::\s*[^=]+)?=\s*([0-9][0-9_.]*)")

#: Comparisons that gate on a day count inline.
_CMP = re.compile(r"\b([a-z_]*days?)\s*(<|<=|>|>=)\s*([0-9][0-9_.]*)")

_TAG = re.compile(r"CLOCK-EXEMPT\((physical|data-window|attestation)\)")

_SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "data", "web", "docs"}
#: Tests may reference day numbers freely -- they assert ABOUT gates, they are not gates.
_SKIP_NAME = re.compile(r"(^test_|_test\.py$|/tests?/)")


def _tagged(lines: list[str], i: int) -> str | None:
    """A tag on this line or the line above claims an exemption for this site."""
    for j in (i, i - 1):
        if 0 <= j < len(lines):
            m = _TAG.search(lines[j])
            if m:
                return m.group(1)
    return None


#: How many files the last scan() actually read. THE DENOMINATOR OF THE "CLEAN" VERDICT (L1.57):
#: this fence walks `_ROOT.rglob("*.py")` and prints CLEAN when it finds no untagged gate --
#: which is exactly what it prints when the walk matched nothing at all. A moved root, a
#: mis-parsed skip pattern or an unreadable tree all render as a clean codebase.
N_SCANNED = 0

#: How many paths the walk OFFERED, and how many it could not read (L1.60). N_SCANNED alone
#: cannot distinguish "897 files were out of scope" from "897 files could not be opened"; both
#: leave it unchanged, and only one is a defect.
N_ATTEMPTED = 0
N_UNREADABLE = 0


def scan() -> tuple[list[tuple[str, int, str, str]], list[tuple[str, int, str, str]]]:
    global N_SCANNED, N_ATTEMPTED, N_UNREADABLE
    violations, exempt = [], []
    n = attempted = unreadable = 0
    for p in sorted(_ROOT.rglob("*.py")):
        # EVERY DISCARD IS COUNTED (L2.4/L1.60): `attempted` moves before any skip, so an
        # out-of-scope file and a file this fence COULD NOT READ stop being byte-identical to a
        # reader of N_SCANNED. Previously `n += 1` sat below the handler, which meant the
        # denominator L1.57 added here to reveal a hollow verdict was hollowed the same way.
        attempted += 1
        rel = p.relative_to(_ROOT).as_posix()
        if any(part in _SKIP_DIRS for part in p.relative_to(_ROOT).parts[:-1]):
            continue
        if _SKIP_NAME.search("/" + rel) or rel.endswith("check_calendar_gates.py"):
            continue
        try:
            lines = p.read_text("utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue
        n += 1
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("#"):
                continue
            hit = None
            m = _CONST.match(ln)
            if m:
                hit = f"{m.group(1)} = {m.group(2)}"
            else:
                c = _CMP.search(ln)
                # A bare `days > 0` is an existence test, not a confidence bar.
                if c and float(c.group(3)) > 1:
                    hit = f"{c.group(1)} {c.group(2)} {c.group(3)}"
            if not hit:
                continue
            tag = _tagged(lines, i)
            (exempt if tag else violations).append((rel, i + 1, hit, tag or ""))
    N_SCANNED, N_ATTEMPTED, N_UNREADABLE = n, attempted, unreadable
    return violations, exempt


def main() -> int:
    violations, exempt = scan()
    print("L1.48 CALENDAR-GATE SCAN -- evidence is the clock\n")
    if exempt:
        by = {}
        for rel, ln, hit, tag in exempt:
            by.setdefault(tag, []).append((rel, ln, hit))
        print(f"  {len(exempt)} site(s) claiming a constitutional exemption:")
        for tag in sorted(by):
            print(f"    [{tag}] {len(by[tag])}")
            for rel, ln, hit in by[tag][:40]:
                print(f"       {rel}:{ln}  {hit}")
        print()
    if violations:
        print(f"  {len(violations)} UNTAGGED calendar gate(s) -- each is a defect under L1.48.")
        print("  Either migrate to libs/research/evidence_clock.sufficient(), or tag with")
        print("  CLOCK-EXEMPT(physical|data-window|attestation) naming the exemption claimed.\n")
        for rel, ln, hit, _ in violations:
            print(f"    {rel}:{ln}  {hit}")
        print(f"\n  MIGRATION CHECKLIST: {len(violations)} item(s) outstanding.")
        # Declare on the FAILING path too (L1.57). This fence early-returns here without touching
        # fence_exit, so while the 69-item migration backlog stands it would never reach its
        # declaration site -- and a permanently-failing fence would be indistinguishable from an
        # unwired one in the coverage ratchet. The exit code is deliberately left at 1: this path
        # is not a vacuity refusal and consumers of it predate L1.57.
        record("check_calendar_gates.py", "repo *.py files", N_SCANNED, passed=False)
        return 1
    print(f"  CLEAN: no untagged calendar gate remains in {N_SCANNED} file(s) scanned "
          f"({len(exempt)} exempt, all declared).")
    # The denominator says what it LOST as well as what it counted (L1.60). An unreadable file
    # is a fence that did not check, not a fence that found nothing.
    print(f"  denominator: {N_ATTEMPTED} offered -> {N_SCANNED} scanned, "
          f"{N_ATTEMPTED - N_SCANNED - N_UNREADABLE} out of scope, {N_UNREADABLE} UNREADABLE"
          + ("  <- these were not checked" if N_UNREADABLE else ""))
    # A clean verdict now carries its denominator (L1.57). Zero files read is not a clean tree,
    # and until this line the two printed the same sentence and returned the same code.
    return fence_exit("CLEAN", _PASSING, scanned=N_SCANNED, of="repo *.py files",
                      fence="check_calendar_gates.py")


if __name__ == "__main__":
    sys.exit(main())
