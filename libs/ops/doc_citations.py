"""THE DOC->CODE CITATION (R0468) -- nothing on this desk checked that a cited MECHANISM exists.

THE PROVING INSTANCE, AND IT SAT FOR SEVEN DAYS IN A DATED PRE-REGISTRATION.
``docs/research/axis_generation_20260805.md`` asserted, in the indicative:

    Recurrence detector: scripts/check_axis_clocks.py (daily cron) pages the cycle when any
    verified axis's clock exceeds 7d again

That file **has never existed in any tree** and is in no crontab. The claim was written by a
GENERATOR, so every future run would have reproduced it, and it was read by humans and by seats
as a live rail for a week (repaired in ``bbfce84``, at the doc AND at the generator). The same
shape hid the phantom ``research_memory.db`` behind four separate references.

WHY NO EXISTING INSTRUMENT COULD SEE IT. The desk owns two reachability walkers and they walk in
the wrong directions. ``check_orphan_code`` walks CODE -> CODE (does anything import this
module?). ``check_organ_liveness`` walks SCHEDULED -> PRODUCED (did the thing on the clock write
its artifact?). ``check_citation_integrity`` (R0369) walks LEDGER -> COMMIT. **Nothing walked
DOC -> CODE**, so a document could name a mechanism that was never built and every gate on the
desk stayed green -- there was no denominator in which the claim appeared at all.

THE HARD PART IS NOT FINDING UNRESOLVED PATHS; IT IS THAT MOST OF THEM ARE CORRECT.
Measured over 274 documents on 2026-08-13: **2,838** repo-path citations outside fenced blocks,
of which **66** do not resolve. Read by hand, the overwhelming majority are the desk working
properly, in three classes that a naive checker would flag and must not:

  * FORWARD-LOOKING. A capability-hunt proposal, a spec, a premortem's "Missing Rail" all name
    the file they are asking to have BUILT. ``scripts/collect_venue_yield.py`` in
    ``20260812_s3_proposals.md`` is a design, not a claim.
  * DELIBERATELY NEGATIVE. ``scripts/pdf_text.py`` appears ELEVEN times saying, correctly,
    "does not exist", "has NOT landed", "still does not exist (checked this run)" -- it is open
    gap R0358. A fence that reddens on those punishes the desk's single most honest documentation
    habit, and the habit would go first.
  * QUOTED SOURCE. ``docs/audit_shards/*.md`` embed whole modules inside fenced blocks to hand a
    panel real code; **1,721** citations live inside such blocks and none of them is an assertion
    by this desk at all.

SO THE UNIT OF ENFORCEMENT IS NOT A PATH, IT IS AN ASSERTION OF PRESENT EXISTENCE, and exactly
two forms of it are machine-readable without guessing at prose:

  LINE-CITED  ``libs/discovery/factory.py:256`` -- a line number is a claim to have READ the
              file. No proposal ever cites a line of something that does not exist yet, so this
              form cannot be forward-looking; it can only be true or fabricated.
  ASSERTED-LIVE  a path next to a present-tense mechanism marker -- ``(daily cron)``,
              ``(hourly)``, "enforced by", "producer:", "consumed by". This is the R0468 shape
              verbatim, and it is the form a *generator* emits when it manufactures a rail.

Everything else is MENTIONED: counted, published, and never a failure. That is a decision with a
denominator behind it, not a gap -- the artifact carries ``n_mentioned`` so the fraction this
fence declines to judge is visible rather than implied.

THE NEGATION EXEMPTION CARRIES ITS REASON FROM THE DOCUMENT, NOT FROM A LIST. An asserted
citation on a line that also says "does not exist" / "never existed" / "would" / "propose" /
"retired" is exempt, and the artifact records THE MATCHED PHRASE as the reason. This desk's
allowlists rot because they are maintained by hand somewhere else; this one cannot go stale
because it is re-read out of the sentence on every run. The proving case is this fence's own
proving case: the correction note that FIXED R0468 quotes ``scripts/check_axis_clocks.py
(daily cron)`` in order to say it never existed, and a fence that fired on the repair would have
been switched off the day it shipped (L1.43).

PORTABILITY IS MEASURED, NOT ASSUMED. A verdict that depends on files this box happens to have
is a verdict CI will contradict. Resolution is ``git ls-files`` UNION on-disk, and the artifact
publishes ``n_untracked_resolved`` -- citations that resolved ONLY because an untracked file is
present here. Measured 2026-08-13: **0 of 355**, so today's verdict is clone-invariant, and the
day that stops being true the number says so instead of CI saying it.

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). A MEASUREMENT duty and a
SCOPE EXPANSION. It lifts nothing, sizes nothing, promotes nothing and loosens no statistical
bar; it has no vocabulary for turning a failing verdict into a passing one. Its whole effect is
to make "this document names a rail that exists" distinguishable from "this document names a
rail" -- byte-identical on this desk until now, and only one of them is evidence. Every error it
catches points the same way: toward the desk believing it owns a mechanism it does not own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Directory names that are never desk-authored documents or source. ``.claude`` holds sibling
#: git WORKTREES: scanning them reports another checkout's copy of a doc as a finding in this
#: one, which is duplication wearing the costume of scale (the L1.60 scope argument, verbatim).
SKIP_PARTS = frozenset({".venv", "node_modules", "__pycache__", ".git", "build", "dist",
                        ".claude", ".mypy_cache", ".pytest_cache", ".ruff_cache"})

#: Extensions that name a MECHANISM. Deliberately code-only. A ``.json``/``.jsonl``/``.db``
#: citation is usually a RUNTIME ARTIFACT under a gitignored tree (``data/*`` and ``web/*`` are
#: both ignored here), so its absence in a clone is expected rather than a defect, and a fence
#: keyed on it would be green on this box and red in CI -- the exact non-portability that gets a
#: fence switched off. R0468's own subject is a script; the artifact half belongs to L1.55
#: input-provenance and L1.44 freshness, which already own it.
CODE_EXT: tuple[str, ...] = (".py", ".sh")

#: Path segments are word-shaped: NO dot is allowed except the one before the extension. Written
#: this way to reject ``libs/.../knowledge_engine.py`` -- a HUMAN ELISION, not a path, and the
#: only false positive the first hand-audit of the line-cited class turned up.
_SEG = r"[A-Za-z0-9_+-]+"
_PATH = rf"(?:{_SEG}/)+{_SEG}(?:{'|'.join(re.escape(e) for e in CODE_EXT)})"

#: A repo-relative path token. The leading segment is checked against the roots DISCOVERED on
#: disk rather than a hardcoded tuple -- a fence about unbacked claims that carried a hand list
#: of the repo's own directories would be the defect it detects (the L1.57 substrate argument).
CITE_RE = re.compile(rf"(?<![\w./-])({_PATH})(?![\w])")

#: ``path.py:256`` / ``path.py:45-52`` -- the doc claims to have read a specific line.
LINE_RE = re.compile(rf"(?<![\w./-])({_PATH}):(\d+)(?:\s*[-–]\s*\d+)?(?![\w])")

#: Present-tense mechanism markers. A parenthetical cadence is the R0468 shape exactly; the verb
#: forms are how this vault states that something is wired RIGHT NOW.
LIVE_RE = re.compile(
    r"\((?:daily|hourly|nightly|weekly|[a-z ]{0,12}cron[a-z ]{0,12}|systemd[a-z ]*)\)"
    r"|\b(?:enforced by|fenced by|producer:|produced by|written by|consumed by|"
    r"runs (?:daily|hourly|nightly|every)|is scheduled|on the manifest|cron line)\b",
    re.IGNORECASE)

#: How far either side of the path a live marker still counts as attached to it. 60 characters is
#: roughly one clause: wide enough for ``Recurrence detector: <path> (daily cron) pages...``,
#: narrow enough that a marker about a DIFFERENT sentence on the same line does not reach.
LIVE_WINDOW = 60

#: An explicit statement that the path is absent, historical, or wanted-but-unbuilt. The matched
#: text is recorded as the exemption's REASON, so the exemption is re-read from the sentence on
#: every run and cannot go stale the way a hand allowlist does.
NEGATION_RE = re.compile(
    r"(does ?n[o']?t exist|do(?:es)? not exist|never existed|no such file|not exist|"
    r"absent|missing|phantom|removed|deleted|retired|graveyard|not landed|"
    r"would |should |propose|proposal|to be built|not yet|never built|no longer|"
    r"deprecat|renamed|superseded|corrected|previously cited|land(?:ing)? it as|"
    r"buildable|MECHANISM:|MODULE:|new file)", re.IGNORECASE)

#: Illustrative stand-ins. ``scripts/X.py`` in CONSTITUTION.md is a worked example of the FORM of
#: a path, and reading it as a claim about a file would be reading the wrong noun.
PLACEHOLDER_RE = re.compile(
    r"^(x|y|z|foo|bar|baz|qux|example|sample|name|module|test_x|your_\w*|my_\w*)$",
    re.IGNORECASE)

#: A fenced block holds QUOTED material -- embedded source, shell examples, JSON dumps. Nothing
#: inside one is this desk asserting anything, and audit_shards alone put 1,721 citations there.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

LINE_CITED = "line-cited"
ASSERTED_LIVE = "asserted-live"
MENTIONED = "mentioned"


@dataclass(frozen=True)
class Citation:
    """One repo path named by one line of one document."""

    doc: str
    line: int
    path: str
    form: str                       # LINE_CITED | ASSERTED_LIVE | MENTIONED
    exempt_reason: str = ""         # the negating phrase, quoted from the document itself
    snippet: str = ""
    resolved: bool = False
    resolved_by: str = ""           # "tracked" | "disk" | ""

    @property
    def asserts_existence(self) -> bool:
        """True when the document claims, in the present tense, that this path IS there."""
        return self.form in (LINE_CITED, ASSERTED_LIVE) and not self.exempt_reason

    def as_row(self) -> dict[str, Any]:
        return {
            "doc": self.doc, "line": self.line, "path": self.path, "form": self.form,
            "exempt_reason": self.exempt_reason, "snippet": self.snippet,
            "resolved": self.resolved, "resolved_by": self.resolved_by,
            "repair": (f"{self.doc}:{self.line} asserts `{self.path}` exists and it does not -- "
                       "repoint it at the real module, or state plainly that it is absent"),
        }


@dataclass
class DocResult:
    """Per-document outcome. A document that could NOT be read stays here rather than vanishing.

    L1.60, and this module is subject to it: a scanner that drops the files it cannot open
    reports a smaller, cleaner world every time its input degrades, and the shrinkage is
    invisible to every reader of the count that survives.
    """

    doc: str
    read: bool
    citations: list[Citation] = field(default_factory=list)
    error: str = ""


def repo_roots(root: Path) -> frozenset[str]:
    """Top-level directory names, DISCOVERED on disk.

    A citation whose first segment is not a real directory of this repo is not a citation about
    this repo -- it is a foreign path, an import-looking string, or prose. Discovering the set
    rather than listing it means adding a directory cannot silently narrow the fence's scope.
    """
    try:
        return frozenset(p.name for p in root.iterdir()
                         if p.is_dir() and p.name not in SKIP_PARTS)
    except OSError:
        return frozenset()


def _classify_form(line: str, path: str, start: int, end: int,
                   line_cited: frozenset[str]) -> str:
    if path in line_cited:
        return LINE_CITED
    window = line[max(0, start - LIVE_WINDOW): end + LIVE_WINDOW]
    return ASSERTED_LIVE if LIVE_RE.search(window) else MENTIONED


def extract(text: str, doc: str, roots: frozenset[str]) -> list[Citation]:
    """Every repo-path citation in one document, with its assertion form.

    Fenced blocks are skipped as QUOTED material. The fence state is tracked across lines, so an
    unterminated block swallows the tail of the document -- which is the conservative direction:
    it can only ever remove candidates, never invent one.
    """
    out: list[Citation] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line_cited = frozenset(m.group(1) for m in LINE_RE.finditer(line))
        neg = NEGATION_RE.search(line)
        reason = neg.group(0).strip() if neg else ""
        for m in CITE_RE.finditer(line):
            path = m.group(1)
            if path.split("/", 1)[0] not in roots:
                continue
            if PLACEHOLDER_RE.match(Path(path).stem):
                continue
            form = _classify_form(line, path, m.start(1), m.end(1), line_cited)
            out.append(Citation(
                doc=doc, line=lineno, path=path, form=form,
                exempt_reason=reason if form != MENTIONED else "",
                snippet=line.strip()[:180]))
    return out


def scan(root: Path, tracked: frozenset[str]) -> list[DocResult]:
    """One DocResult per document found -- including the ones that could not be read.

    Nothing here is an invisible ``except OSError: continue``. The count of documents this fence
    examined is a published denominator (L1.57) and the count it LOST is published beside it
    (L1.60); a read failure produces a ``read=False`` row and stays inside both.
    """
    roots = repo_roots(root)
    docs = sorted((root / "docs").rglob("*.md")) if (root / "docs").is_dir() else []
    out: list[DocResult] = []
    for p in docs:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            out.append(DocResult(doc=rel, read=False, error=f"{type(exc).__name__}: {exc}"))
            continue
        out.append(DocResult(doc=rel, read=True,
                             citations=resolve(extract(text, rel, roots), root, tracked)))
    return out


def resolve(citations: list[Citation], root: Path, tracked: frozenset[str]) -> list[Citation]:
    """Mark each citation resolved, and record WHICH evidence resolved it.

    ``tracked`` first, disk second, and the distinction is kept rather than collapsed: a path
    that resolves only on disk resolves only on THIS BOX, and a fence whose verdict depends on
    that is a fence CI will contradict. Callers publish the count.
    """
    out: list[Citation] = []
    for c in citations:
        if c.path in tracked:
            out.append(Citation(**{**c.__dict__, "resolved": True, "resolved_by": "tracked"}))
        elif (root / c.path).exists():
            out.append(Citation(**{**c.__dict__, "resolved": True, "resolved_by": "disk"}))
        else:
            out.append(c)
    return out


def summarise(results: list[DocResult]) -> dict[str, Any]:
    """Roll per-document results into the fence's verdict inputs.

    ``n_docs_found`` counts every document handed in, read or not, so a tree that stops being
    readable cannot read as a smaller clean one (L1.60).
    """
    cits = [c for r in results for c in r.citations]
    asserted = [c for c in cits if c.asserts_existence]
    broken = [c for c in asserted if not c.resolved]
    exempt = [c for c in cits
              if c.form in (LINE_CITED, ASSERTED_LIVE) and c.exempt_reason and not c.resolved]
    unreadable = [{"doc": r.doc, "error": r.error} for r in results if not r.read]
    return {
        "n_docs_found": len(results),
        "n_docs_read": sum(1 for r in results if r.read),
        "n_docs_unreadable": len(unreadable),
        "n_citations": len(cits),
        "n_asserted": len(asserted),
        "n_line_cited": sum(1 for c in cits if c.form == LINE_CITED),
        "n_asserted_live": sum(1 for c in cits if c.form == ASSERTED_LIVE),
        "n_mentioned": sum(1 for c in cits if c.form == MENTIONED),
        "n_exempt": len(exempt),
        "n_broken": len(broken),
        # THE PORTABILITY CANARY. Asserted citations that resolved only because an untracked file
        # is present on this box -- every one of them is a verdict a clean clone would not
        # reproduce. Measured 0 of 355 on 2026-08-13; published so the day it moves, the artifact
        # says so rather than CI.
        "n_untracked_resolved": sum(1 for c in asserted if c.resolved_by == "disk"),
        "broken": [c.as_row() for c in broken],
        "exempt": [c.as_row() for c in exempt],
        "unreadable": unreadable,
    }
