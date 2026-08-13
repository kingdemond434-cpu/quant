"""WHICH EXTRACTORS CAN PROVE THEIR PARSE, AND WHICH ONLY LOOK RIGHT (R0318, OP-024).

THE DEFECT CLASS. A hand-rolled extractor -- markup scraped with regex, CSV sliced by hand, bytes
decoded from a spec -- fails in one characteristic way: it does not crash, it returns a plausible
result, and every number downstream is wrong. The desk has paid for this repeatedly. A selector
rename yields zero rows and reads as a thin ground (OP-034); a `.xls` keyed on ``(row, col)``
merged five sheets into one grid that looked entirely reasonable; a truncated fetch understates
every total it feeds. NONE of these raise. The only defence that survives contact with plausible
output is a check the DATA has to satisfy, declared in advance.

WHAT COUNTS AS AN INVARIANT, and the range is deliberate. An arithmetic conservation law is the
strongest form (:mod:`libs.research.conservation`) but most sources have no totals to close: an RSS
listing has no accounting. Demanding arithmetic everywhere would reject ~100% of the population,
and a gate nobody can pass is not a bar, it is a wall -- it gets switched off and enforces nothing
(L1.43, L1.49). So a STRUCTURAL invariant counts too: a row-count floor, a required-field census, a
monotone timestamp, a refusal when the parse comes back empty. What does NOT count is nothing at
all, which is the actual state this fence exists to make visible.

THE DENOMINATOR IS DISCOVERED, NEVER LISTED (L1.57). A fence about unvalidated extractors carrying
a hardcoded list of extractors would BE the defect it detects: the list cannot fall when a module
disappears, and it silently omits whatever the author forgot. :func:`discover` re-derives the
population from source on every run, so the count is a measurement.

COVERAGE IS A RATCHET, NOT A CLIFF. Below 100% this reports PARTIAL and exits 0. The gap is the
work queue (L1.0). A fence that goes red on the day it ships gets disabled within a week, and a
disabled fence enforces nothing at all.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: Module-level constant an extractor sets to name the invariant it enforces on its own output.
#: A STRING, not a boolean: the value is the claim, and a claim that cannot be read cannot be
#: audited later. Empty or whitespace does not count -- that is a checkbox, not a declaration.
DECLARATION: Final = "EXTRACTOR_INVARIANT"

#: Importing the conservation helper is itself a declaration: the module cannot use it without
#: stating an identity.
_CONSERVATION_MODULE: Final = "libs.research.conservation"

#: Markup that only appears in a pattern when a foreign document format is being torn apart by
#: hand. Matched against regex/split STRING LITERALS, never against prose.
_MARKUP = re.compile(
    # The trailing class covers the four shapes a tag pattern takes: `<item>`, `<opensearch:x>`,
    # `<tr `, and `<tr[^>]*>` -- the attribute-bearing form, which is the most common of all and
    # was the one this pattern missed on its first pass.
    r"</|<[a-zA-Z][a-zA-Z0-9]*[\s>:\[]|<\[\^>\]|<\.\*\?>|&nbsp;|CDATA|class=|href=|"
    r"<Key>|<Prefix>|<item>|<entry>",
    re.IGNORECASE,
)

#: Functions whose string arguments are worth inspecting for markup.
_PARSE_CALLS: Final = frozenset(
    {"split", "findall", "search", "match", "finditer", "sub", "compile"}
)

#: Byte-level decoding: no library is interpreting the format, so nothing but the author's reading
#: of a spec stands between the file and the artifact.
_BYTE_CALLS: Final = frozenset({"unpack", "unpack_from", "from_bytes"})

#: A regex NAMED GROUP is spelled exactly like an XML tag -- `(?P<file>[^:]+)` reads as `<file>`.
#: Stripped before markup matching, because mypy-output and log parsers are full of them and every
#: one was a false positive on the first calibration run.
_NAMED_GROUP = re.compile(r"\(\?P[<=]\w+>?|\(\?\(\w+\)")

#: Iterables whose elements are LINES. A comma split is only extraction when it slices fields out
#: of one of these; `str(args.symbols).split(",")` is an argument being read, not a format being
#: parsed. Matching the receiver NAME rather than the module as a whole is what separates them --
#: a module-level "does this file mention lines anywhere" test flagged CLI parsing as CSV.
_LINEY = re.compile(r"line|row|record|content|body|payload|text|csv", re.IGNORECASE)

_SKIP_DIRS: Final = ("__pycache__", ".claude", "node_modules", ".venv")

#: This module carries markup patterns as DATA, so it matches its own detector. It parses Python
#: with `ast`, which is the stdlib doing the interpreting -- the opposite of a hand-rolled parse.
_SELF: Final = "libs/research/extractor_invariants.py"


@dataclass(frozen=True)
class Extractor:
    """One module that parses a foreign format by hand and writes something research reads."""

    path: str
    techniques: tuple[str, ...]
    declared: bool
    declaration: str

    @property
    def status(self) -> str:
        return "DECLARED" if self.declared else "UNDECLARED"


def _literals(node: ast.AST) -> list[str]:
    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _line_bound_names(tree: ast.AST) -> set[str]:
    """Names bound to something line-shaped: ``for row in text.splitlines()``, ``lines = ...``.

    This is the cheap half of dataflow and it is enough, because the two cases being separated
    look nothing alike once the receiver is known -- one is a loop variable over split text, the
    other is an argparse attribute.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            source_text = ast.dump(node.iter)
            liney = _LINEY.search(source_text)
            if "splitlines" in source_text or "readlines" in source_text or liney:
                for target in ast.walk(node.target):
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        elif isinstance(node, ast.Assign):
            value = ast.dump(node.value)
            if "splitlines" in value or "readlines" in value:
                for target in node.targets:
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
    return names


def _receiver_is_a_line(node: ast.Call, line_names: set[str]) -> bool:
    """Is ``x`` in ``x.split(",")`` a line of a document, or just a string someone passed in?"""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    receiver = func.value
    if isinstance(receiver, ast.Subscript):  # lines[0].split(",") -- the header row idiom
        receiver = receiver.value
    if isinstance(receiver, ast.Name):
        return receiver.id in line_names or bool(_LINEY.fullmatch(receiver.id))
    return False


def techniques_in(tree: ast.AST, source: str) -> tuple[str, ...]:
    """Which hand-rolled parsing techniques a module uses, by inspecting what it actually calls.

    Reading the CALL rather than grepping the file matters: ``<`` appears in prose, comparisons and
    type hints constantly, so a plain text search over a 900-line module is nearly always a hit.
    The literal has to be an argument to something that parses.
    """
    found: set[str] = set()
    line_names = _line_bound_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in _BYTE_CALLS:
            found.add("byte-level")
        if name not in _PARSE_CALLS:
            continue
        for literal in _literals(node):
            if _MARKUP.search(_NAMED_GROUP.sub("", literal)):
                found.add("markup-by-regex")
            elif (
                name == "split"
                and literal in (",", "\t", ";", "|")
                and _receiver_is_a_line(node, line_names)
            ):
                found.add("delimited-by-hand")
    if re.search(r"\bcsv\.(reader|DictReader)", source):
        # The stdlib parser handles quoting, embedded delimiters and line breaks; a module using it
        # is not hand-rolling that layer even if it splits something else somewhere.
        found.discard("delimited-by-hand")
    return tuple(sorted(found))


def declaration_in(tree: ast.AST, source: str) -> str:
    """The invariant a module declares, or an empty string.

    Two forms count. An explicit ``EXTRACTOR_INVARIANT = "..."`` states the claim in the module's
    own words. Importing the conservation helper is the stronger form and needs no restatement,
    because an identity has to be passed to use it at all.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if DECLARATION in targets and isinstance(node.value, ast.Constant):
                text = str(node.value.value).strip()
                if text:
                    return text
    # An IMPORT, read from the syntax tree -- never a substring of the source. A module that only
    # MENTIONS the conservation helper (in a docstring, a comment, or a list of module names, as
    # this very file does) has not used it, and crediting prose as validation would let the fence
    # be satisfied by writing about the fix.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            _CONSERVATION_MODULE
        ):
            return "checks its parse with libs.research.conservation"
        if isinstance(node, ast.ImportFrom) and node.module == "libs.research" and any(
            alias.name == "conservation" for alias in node.names
        ):
            return "checks its parse with libs.research.conservation"
        if isinstance(node, ast.Import) and any(
            alias.name == _CONSERVATION_MODULE for alias in node.names
        ):
            return "checks its parse with libs.research.conservation"
    return ""


def discover(root: Path) -> list[Extractor]:
    """Every hand-rolled extractor that feeds a research artifact, re-derived from source.

    A module that cannot be parsed is REPORTED, never skipped: "we could not read it" and "it is
    fine" are different claims, and only one of them is evidence (L1.28a).
    """
    out: list[Extractor] = []
    for base in ("libs", "scripts"):
        for path in sorted((root / base).rglob("*.py")):
            relative = path.relative_to(root)
            rel = str(relative)
            # Skip-matching is against the path RELATIVE to the root, never the absolute one: a
            # checkout living under a directory that happens to be named `.claude` (every git
            # worktree here does) would otherwise skip every file in the repo and discover
            # nothing -- which this fence reports as UNMEASURED, correctly but for the wrong
            # reason. An exclusion list must describe the repo, not the machine.
            if any(part in _SKIP_DIRS for part in relative.parts) or rel == _SELF:
                continue
            source = path.read_text("utf-8", errors="replace")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                out.append(Extractor(str(path.relative_to(root)), ("unparseable",), False,
                                     "module does not parse -- cannot be audited"))
                continue
            techniques = techniques_in(tree, source)
            if not techniques:
                continue
            declaration = declaration_in(tree, source)
            out.append(Extractor(str(path.relative_to(root)), techniques,
                                 bool(declaration), declaration))
    return out


def summarise(root: Path) -> dict[str, object]:
    """Coverage over the discovered population, with the refusal states kept distinct."""
    found = discover(root)
    declared = [e for e in found if e.declared]
    n = len(found)
    if n == 0:
        # Zero is never a clean board here: this repo is full of scrapers, so an empty population
        # means the DETECTOR broke, not that the defect was solved.
        return {
            "status": "UNMEASURED",
            "n_extractors": 0,
            "n_declared": 0,
            "coverage": None,
            "detail": "discovery found no hand-rolled extractors at all -- in this repo that is a "
                      "broken detector, not a clean result",
            "extractors": [],
        }
    coverage = len(declared) / n
    return {
        "status": "OK" if coverage == 1.0 else "PARTIAL",
        "n_extractors": n,
        "n_declared": len(declared),
        "coverage": coverage,
        "detail": (
            f"{len(declared)}/{n} hand-rolled extractors that feed a research artifact declare an "
            f"in-data invariant ({coverage:.0%}); the rest are validated by nothing but how their "
            f"output looks"
        ),
        "extractors": [
            {
                "path": e.path,
                "techniques": list(e.techniques),
                "status": e.status,
                "declaration": e.declaration,
            }
            for e in sorted(found, key=lambda e: (e.declared, e.path))
        ],
    }
