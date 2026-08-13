"""THE DENOMINATOR THAT LEAKS (L1.60) -- L1.57 asked whether a count exists; this asks what it lost.

WHAT L1.57 CANNOT SEE, AND IT IS THE HALF THAT MOVES A VERDICT. ``libs/ops/denominator.py``
closed the vacuous-pass hole: a fence that examined nothing may not pass. Its whole test is
``is_vacuous`` -- ``n_scanned`` must be an ``int >= 1``. That is a test on the NUMBER, and it is
blind to the only other way a denominator lies:

    for p in files:                       # 1000 files
        try:
            text = p.read_text("utf-8")
        except OSError:
            continue                      # <- 991 unreadable ones leave the count entirely
        n += 1                            # 9
        ...
    return fence_exit(status, PASSING, scanned=n, of="*.py")   # scanned=9. Not vacuous. CLEAN.

Nine is an ``int >= 1``, so L1.57 records the row DECLARED, non-vacuous, and the board is green.
The fence read 1% of its scope and said so nowhere. THE NUMBER IS HONEST ABOUT WHAT IT COUNTED
AND SILENT ABOUT WHAT IT LOST, and silence is what a reader scores as coverage.

THE PROVING INSTANCE IS THE L1.57 FENCE'S OWN SUPPLIER. ``scripts/check_calendar_gates.py``
declares ``fence_exit(..., scanned=N_SCANNED)``. ``N_SCANNED`` comes from ``n += 1`` sitting one
line BELOW ``except (OSError, UnicodeDecodeError): continue``. So the denominator L1.57 built to
reveal a hollow verdict is itself hollowed by the same mechanism, one level up. A law's own
instrument being defeated by the law's own failure mode is the strongest evidence available that
the mechanism -- not the diligence -- is what needs fixing.

WHY THE ORDINARY SWALLOW DETECTORS ARE BLIND TO ALL OF IT. The desk has two, and both require a
``Pass`` body: ``check_build_standard._has_silent_swallow`` (``all(isinstance(b, ast.Pass))``)
and ``max_audit.check_silent_swallows_on_the_rails`` (stricter still -- a single ``Pass`` under a
broad ``Exception``). Every instance in the class above uses ``continue`` or ``return <default>``.
R0166 recorded this in prose on 2026-07-31 and scheduled the widening; nothing was built. A DUTY
WITH NO INSTRUMENT IS A WISH (L1.46).

THE RULE, AND IT IS ONE RULE WITH ONE REPAIR. A loop that produces a scope denominator must
publish how many iterations it ATTEMPTED. Not "never skip" -- skipping is often correct, and a
scope filter that drops 900 of 1000 files is fine. What is never correct is skipping INVISIBLY,
because it makes two different facts byte-identical to every reader:

    a file that was out of scope        }  both leave `n` unchanged,
    a file the fence could not read     }  and only one of them is a defect

The repair is a single counter incremented before the first exit, which is precisely what this
desk already does where it does it well -- ``libs/research/extractor_invariants.py`` turns a
``SyntaxError`` into an ``("unparseable",)`` row that STAYS in the denominator;
``scripts/check_funding_capture.py`` writes ``malformed += 1; continue``;
``libs/research/axis_screen.target_horizon_sweep`` increments ``attempted`` before every guard.
This module does not invent a practice. It enforces one the desk already wrote down as L2.4
("EVERY DISCARD IS COUNTED") and never once checked.

WHAT COUNTS AS A SCOPE DENOMINATOR, and the precision this buys. Not every accumulator in a loop
is a measurement denominator, and treating them alike is how a fence earns its way into
``# noqa``. A name qualifies here only when the run's own value flows into a published measure of
SCOPE: the ``scanned=`` kwarg of ``fence_exit``, or a division whose result is returned or stored
under a scope-shaped name (``*_pct``, ``*_fraction``, ``*_ratio``, ``coverage``, ...). Measured on
the 53 governed fences the day this was written: 8 raw hits, of which the restriction plus the
counted-discard exemption leave 3 real ones -- and all 3 were independently verified by hand
before this module existed. ``check_row_atomicity``'s log-rank ``var`` accumulator (a
mathematical risk-set guard, no scope claim) and ``check_funding_capture``'s exemplary
``malformed += 1`` are both correctly left alone.

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). A MEASUREMENT duty and a SCOPE
EXPANSION. It lifts nothing, sizes nothing, promotes nothing, and loosens no statistical bar; it
has no vocabulary for turning a failing verdict into a passing one. It does not forbid a single
skip -- it requires that skips be COUNTED, which strictly increases what the desk can see. The
direction of the error it catches is always the same and always toward false comfort: every
uncounted discard makes a fence's coverage look larger than it was.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: A name whose value is published as a measure of SCOPE rather than as an intermediate. The
#: point of the restriction is precision: `var` in a log-rank statistic is a divisor too, and
#: flagging it would bury the three real findings under arithmetic.
_SCOPE_NAME = re.compile(r"(_pct|_fraction|_ratio|_share|_rate|coverage|scanned|n_examined)",
                         re.IGNORECASE)

#: An explicit, REASONED exemption at a skip site. Silence is never an exemption; a tag with no
#: reason is not a tag. Exempt sites are REPORTED, never hidden -- an invisible exemption is the
#: defect this module exists to detect, wearing a comment.
_TAG = re.compile(r"#\s*attrition-ok:\s*(\S.*)$")


@dataclass(frozen=True)
class Finding:
    """One loop whose scope denominator can be skipped without the skip being counted."""

    path: str
    counter: str
    counter_line: int
    skip_lines: tuple[int, ...]
    kinds: tuple[str, ...]          # "except" | "guard", per skip site
    exempt_reason: str = ""

    @property
    def has_handler(self) -> bool:
        """A skip inside an ``except`` is a CAUGHT FAILURE leaving the count -- the sharp case."""
        return "except" in self.kinds

    def as_row(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "counter": self.counter,
            "counter_line": self.counter_line,
            "skip_lines": list(self.skip_lines),
            "kinds": list(self.kinds),
            "from_handler": self.has_handler,
            "exempt_reason": self.exempt_reason,
            "repair": (f"count the attempt before the first skip: add `attempted += 1` above "
                       f"line {self.skip_lines[0]} and publish it beside `{self.counter}`"),
        }


@dataclass
class FileResult:
    """Per-file outcome. An unparseable file STAYS HERE rather than vanishing (L2.4).

    This module refusing to commit its own defect is not decoration: a scanner that drops the
    files it cannot read reports a smaller, cleaner world every time its input degrades.
    """

    path: str
    parsed: bool
    findings: list[Finding] = field(default_factory=list)
    exempt: list[Finding] = field(default_factory=list)
    error: str = ""


def _scope_denominators(tree: ast.AST) -> set[str]:
    """Names consumed as a published measure of scope."""
    names: set[str] = set()

    def add(node: ast.AST | None) -> None:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "len" and node.args
              and isinstance(node.args[0], ast.Name)):
            names.add(node.args[0].id)

    def divisors(node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
                add(sub.right)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):                     # fence_exit(scanned=n)
            for kw in node.keywords:
                if kw.arg == "scanned":
                    add(kw.value)
        elif isinstance(node, ast.Assign):                 # coverage = a / b
            if any(isinstance(t, ast.Name) and _SCOPE_NAME.search(t.id) for t in node.targets):
                divisors(node.value)
        elif isinstance(node, ast.Dict):                   # {"money_path_pct": a / b}
            for key, val in zip(node.keys, node.values, strict=False):
                if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                        and _SCOPE_NAME.search(key.value)):
                    divisors(val)
    # DELIBERATELY NOT: "any division inside a `return`". A bare `return (obs - exp) ** 2 / var`
    # is a statistic, not a claim about how much of the world was examined, and treating the two
    # alike buries the real findings under arithmetic. A returned ratio that IS a scope claim
    # travels in a dict with a scope-shaped key, which the branch above already reads wherever
    # it appears -- including inside a return.

    # One hop of aliasing: `N_SCANNED = n` then `fence_exit(scanned=N_SCANNED)`. Without this the
    # module-global publication idiom -- which is exactly what check_calendar_gates uses -- hides
    # the counter from the analysis that exists to find it.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)):
            names.add(node.value.id)
    return names


def _counts_something(stmt: ast.stmt) -> bool:
    """True if this statement increments a counter or appends to a list."""
    for node in ast.walk(stmt):
        if isinstance(node, ast.AugAssign):
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("append", "add")):
            return True
    return False


def _counts_attempts_before(body: list[ast.stmt], first_skip: int) -> bool:
    """True if this loop tallies the attempt BEFORE its first skip -- the prescribed repair.

    A statement above every exit runs on every iteration, so a plain ``attempted += 1`` there is
    a true count of attempts and the attrition becomes visible in the artifact. The increment
    must be by a literal 1 (or an append): ``total += price`` also runs unconditionally, but it
    publishes a SUM, and a sum cannot tell a reader how many members the count lost.
    """
    for stmt in body[:first_skip]:
        for node in ast.walk(stmt):
            if (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)
                    and isinstance(node.value, ast.Constant) and node.value.value == 1):
                return True
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("append", "add")):
                return True
    return False


def _counters(body: list[ast.stmt]) -> list[tuple[str, int, int]]:
    """(name, statement index, line) for every counter written in this loop body."""
    out: list[tuple[str, int, int]] = []
    for i, stmt in enumerate(body):
        for node in ast.walk(stmt):
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                out.append((node.target.id, i, node.lineno))
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in ("append", "add")
                  and isinstance(node.func.value, ast.Name)):
                out.append((node.func.value.id, i, node.lineno))
    return out


def _skips(body: list[ast.stmt]) -> list[tuple[int, int, str, bool]]:
    """(statement index, line, kind, counts_its_discard) for every early exit in this body."""
    out: list[tuple[int, int, str, bool]] = []
    for i, stmt in enumerate(body):
        counted = _counts_something(stmt)
        for node in ast.walk(stmt):
            if isinstance(node, (ast.Continue, ast.Return)):
                inside_handler = any(
                    node in ast.walk(h)
                    for h in ast.walk(stmt) if isinstance(h, ast.ExceptHandler))
                out.append((i, node.lineno, "except" if inside_handler else "guard", counted))
    return out


def _tag_for(lines: list[str], line_nos: tuple[int, ...]) -> str:
    """A reasoned exemption tagged on, or just above, any skip site in this loop."""
    for ln in line_nos:
        for j in (ln - 1, ln - 2):
            if 0 <= j < len(lines):
                m = _TAG.search(lines[j])
                if m:
                    return m.group(1).strip()
    return ""


def analyse_source(src: str, path: str = "<src>") -> FileResult:
    """Findings for one module. A SyntaxError is a RESULT, never a skipped file."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return FileResult(path=path, parsed=False, error=f"{type(exc).__name__}: {exc}")

    lines = src.splitlines()
    denominators = _scope_denominators(tree)
    res = FileResult(path=path, parsed=True)
    if not denominators:
        return res

    for loop in [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]:
        counters = _counters(loop.body)
        skips = _skips(loop.body)
        if not counters or not skips:
            continue
        for name, idx, line in counters:
            if name not in denominators:
                continue
            # Only skips that can reach THIS counter matter: one positioned after it has
            # already let the attempt be counted.
            before = [s for s in skips if s[0] < idx]
            if not before:
                continue
            # THE EXEMPLAR EXEMPTION (L2.4): if every skip that precedes the counter records
            # its own discard, the attrition is visible and the loop is compliant. Punishing
            # the desk's own correct practice is how a fence gets switched off (L1.43).
            if all(s[3] for s in before):
                continue
            # THE PRESCRIBED REPAIR, RECOGNISED: a tally above the first skip makes every
            # discard visible at once, which is why the law asks for one counter rather than a
            # counter per branch. A fence that still fired after the fix it demanded would
            # teach the desk to ignore it.
            if _counts_attempts_before(loop.body, min(s[0] for s in before)):
                continue
            uncounted = tuple(s for s in before if not s[3])
            skip_lines = tuple(sorted({s[1] for s in uncounted}))
            finding = Finding(
                path=path, counter=name, counter_line=line, skip_lines=skip_lines,
                kinds=tuple(sorted({s[2] for s in uncounted})),
                exempt_reason=_tag_for(lines, skip_lines),
            )
            (res.exempt if finding.exempt_reason else res.findings).append(finding)
    return res


def analyse_paths(paths: list[Path], root: Path) -> list[FileResult]:
    """Every path yields exactly one FileResult -- including the ones that cannot be read.

    An OSError here produces a ``parsed=False`` row rather than a ``continue``. This module is
    subject to its own law, and a scanner that quietly shrinks its own denominator when a file
    goes unreadable would be an unusually direct joke.
    """
    out: list[FileResult] = []
    for p in paths:
        rel = p.relative_to(root).as_posix() if p.is_absolute() else p.as_posix()
        try:
            src = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            out.append(FileResult(path=rel, parsed=False, error=f"{type(exc).__name__}: {exc}"))
            continue
        out.append(analyse_source(src, rel))
    return out


def summarise(results: list[FileResult]) -> dict[str, Any]:
    """Roll the per-file results into the fence's verdict inputs.

    ``n_examined`` is this module's OWN denominator, and it counts every path handed in --
    parsed or not -- so that a tree that stops being readable cannot read as a smaller clean one.
    """
    findings = [f for r in results for f in r.findings]
    exempt = [f for r in results for f in r.exempt]
    unparsed = [{"path": r.path, "error": r.error} for r in results if not r.parsed]
    return {
        "n_examined": len(results),
        "n_parsed": sum(1 for r in results if r.parsed),
        "n_unparsed": len(unparsed),
        "n_findings": len(findings),
        "n_from_handler": sum(1 for f in findings if f.has_handler),
        "n_exempt": len(exempt),
        "findings": [f.as_row() for f in findings],
        "exempt": [f.as_row() for f in exempt],
        "unparsed": unparsed,
    }
