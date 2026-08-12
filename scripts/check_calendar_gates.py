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

import io
import re
import sys
import tokenize
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


def _hit(ln: str) -> tuple[str, int, int] | None:
    """The calendar gate on this line and the COLUMNS it occupies, or None.

    The columns are the whole point. A line-level answer is wrong in both directions and the
    measurement that drove this change made the mistake itself: `.days > 14` sitting beside
    `f["raised"]` is real code on a line that also holds a string, and a line-level "is this
    inside a string" test silently retires it.
    """
    m = _CONST.match(ln)
    if m:
        return f"{m.group(1)} = {m.group(2)}", m.start(1), m.end(2)
    c = _CMP.search(ln)
    # A bare `days > 0` is an existence test, not a confidence bar.
    if c and float(c.group(3)) > 1:
        return f"{c.group(1)} {c.group(2)} {c.group(3)}", c.start(1), c.end(3)
    return None


def _string_spans(text: str) -> dict[int, list[tuple[int, int]]] | None:
    """Columns occupied by string LITERAL text, per 1-based line -- None if it will not tokenize.

    CODE INSIDE A DOCSTRING CANNOT EXECUTE, so a day number written in prose is not a gate. This
    fence had counted them, and the only two ways to clear such a row were to reword correct
    documentation or to tag it CLOCK-EXEMPT -- a false exemption claim on a non-gate. Both are
    workarounds; both had already been used here (libs/research/evidence_clock.py 2026-08-05,
    libs/research/event_density.py the same day).

    None means UNPARSEABLE, and every caller must then report every hit in that file. A fence
    that cannot read a file must not conclude the file is clean (L1.28a); the degradation is
    counted by the caller so it is visible rather than inferred.
    """
    fstr = {getattr(tokenize, "FSTRING_MIDDLE", -1)}
    spans: dict[int, list[tuple[int, int]]] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.STRING and tok.type not in fstr:
                continue
            (sr, sc), (er, ec) = tok.start, tok.end
            for r in range(sr, er + 1):
                spans.setdefault(r, []).append(
                    (sc if r == sr else 0, ec if r == er else 1 << 30))
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError, UnicodeDecodeError):
        return None
    return spans


def _in_string(spans: dict[int, list[tuple[int, int]]] | None, line: int,
               lo: int, hi: int) -> bool:
    """True when the hit's columns sit wholly inside a string literal on that line."""
    if spans is None:
        return False
    return any(a <= lo and hi <= b for a, b in spans.get(line, ()))


#: Roots of git checkouts nested under _ROOT, memoised per directory. An agent worktree under
#: `.claude/worktrees/`, a submodule, a vendored clone -- each holds a COPY of this repo at a
#: different sha, so its sites are not distinct sites. They are the same lines, and NO COMMIT
#: HERE CAN EVER CLOSE A ROW REPORTED AGAINST A COPY: exactly the un-closable checklist item this
#: change exists to remove, at 90x the magnitude of the docstring class that named it.
#: Measured 2026-08-12: 362 of 436 items (83%) came from five agent worktrees, so the published
#: "MIGRATION CHECKLIST" number moved with how many agents happened to be running that hour.
#: The module docstring refuses to forgive whole directories, and this does not: the count is
#: printed on both exit paths. What it refuses is forgiving them in SILENCE (L1.60).
_CHECKOUT: dict[Path, bool] = {}


def _nested_checkout(d: Path, root: Path) -> bool:
    """True if `d` lies inside a git checkout other than `root` itself."""
    if d == root or root not in d.parents:
        return False
    seen = _CHECKOUT.get(d)
    if seen is None:
        seen = (d / ".git").exists() or _nested_checkout(d.parent, root)
        _CHECKOUT[d] = seen
    return seen


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

#: Paths dropped as copies of this repo inside a nested checkout, and files whose string bodies
#: could not be located because they would not tokenize. Both are DISCARDS THAT CHANGE THE
#: CHECKLIST, so both are counted and printed (L1.60): a duplicate that vanishes silently and a
#: file this fence could not parse are different facts, and only one of them is a defect here.
N_DUPLICATE = 0
N_UNPARSED = 0
#: Hits retired as PROSE -- a day number inside a string literal. Reported, never hidden: this is
#: the fence declining to count something it used to count, and that claim has to be auditable.
N_PROSE = 0


def scan(root: Path | None = None) -> tuple[
        list[tuple[str, int, str, str]], list[tuple[str, int, str, str]]]:
    global N_SCANNED, N_ATTEMPTED, N_UNREADABLE, N_DUPLICATE, N_UNPARSED, N_PROSE
    root = (root or _ROOT).resolve()
    violations, exempt = [], []
    n = attempted = unreadable = duplicate = unparsed = prose = 0
    for p in sorted(root.rglob("*.py")):
        # EVERY DISCARD IS COUNTED (L2.4/L1.60): `attempted` moves before any skip, so an
        # out-of-scope file and a file this fence COULD NOT READ stop being byte-identical to a
        # reader of N_SCANNED. Previously `n += 1` sat below the handler, which meant the
        # denominator L1.57 added here to reveal a hollow verdict was hollowed the same way.
        attempted += 1
        rel = p.relative_to(root).as_posix()
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        if _SKIP_NAME.search("/" + rel) or rel.endswith("check_calendar_gates.py"):
            continue
        if _nested_checkout(p.parent, root):
            duplicate += 1
            continue
        try:
            text = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue
        n += 1
        lines = text.splitlines()
        spans = _string_spans(text)
        if spans is None:
            unparsed += 1
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("#"):
                continue
            found = _hit(ln)
            if not found:
                continue
            hit, lo, hi = found
            if _in_string(spans, i + 1, lo, hi):
                prose += 1
                continue
            tag = _tagged(lines, i)
            (exempt if tag else violations).append((rel, i + 1, hit, tag or ""))
    N_SCANNED, N_ATTEMPTED, N_UNREADABLE = n, attempted, unreadable
    N_DUPLICATE, N_UNPARSED, N_PROSE = duplicate, unparsed, prose
    return violations, exempt


def _denominator_line() -> str:
    """What the walk offered, what it read, and every discard that moved the checklist (L1.60)."""
    out_of_scope = N_ATTEMPTED - N_SCANNED - N_UNREADABLE - N_DUPLICATE
    return (f"  denominator: {N_ATTEMPTED} offered -> {N_SCANNED} scanned, "
            f"{out_of_scope} out of scope, {N_DUPLICATE} in nested checkouts (copies of this "
            f"repo -- same lines, different sha), {N_UNREADABLE} UNREADABLE"
            + ("  <- these were not checked" if N_UNREADABLE else "")
            + (f"\n  {N_PROSE} hit(s) retired as PROSE (a day number inside a string literal "
               "cannot execute)" if N_PROSE else "")
            + (f"\n  {N_UNPARSED} file(s) would not tokenize, so their string bodies are UNKNOWN "
               "and every hit in them is reported" if N_UNPARSED else ""))


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
        # The failing path carries the denominator too. The checklist IS the work queue, so a
        # reader has to be able to tell a shrinking backlog from a shrinking SCOPE -- and this
        # fence's count moved 436 -> 74 the day the nested-checkout copies stopped being counted.
        print(_denominator_line())
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
    print(_denominator_line())
    # A clean verdict now carries its denominator (L1.57). Zero files read is not a clean tree,
    # and until this line the two printed the same sentence and returned the same code.
    return fence_exit("CLEAN", _PASSING, scanned=N_SCANNED, of="repo *.py files",
                      fence="check_calendar_gates.py")


if __name__ == "__main__":
    sys.exit(main())
