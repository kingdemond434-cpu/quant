"""Every finding must reach the loop that drives it -- the desk's own map-vs-territory rule,
turned on the desk's findings themselves.

The desk has exactly one organ that DRIVES work to completion: ``docs/GAP_REGISTER.md``, with its
weekly re-rank and 7-day staleness escalation. Everything else -- SYSTEM_REVIEW, BLIND_SPOT_AUDIT,
the micro-audit inbox, the improvement inbox, an external panel ruling, an audit delivered in a
chat window -- is a place findings are WRITTEN, not a place they are WORKED. A finding that never
reaches the register is invisible to the daily cycle, and the cycle only ever acts on what it can
see. It does not rot loudly; it simply never happened.

This was measured, not theorised: of eleven engineering defects found in a full-repo audit, three
were detected by any check and one had a register row. The other eight existed only in a
conversation, and would have vanished with it.

``max_audit.check_review_risks_tracked`` already enforced this -- for THREE HARDCODED KEYS
(counterparty, key-person, per-venue). That is the same brittleness one level up: it can only
catch risks somebody remembered to hardcode, so the next un-tracked finding is invisible again by
construction. This module generalises it: parse findings from wherever they are written, match
them against the register, and report the ones with no trace.

MATCHING IS DELIBERATELY GENEROUS. A finding counts as tracked when any distinctive token from its
title appears in the register. False ACCEPTS are cheap -- the item was probably tracked under
another phrasing. False ALARMS are expensive: a check that flags everything gets ignored, and an
ignored check is worse than no check because it looks like coverage. The same lesson the §33 card
parser learned by firing 92/92 on its first real run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

#: A finding: a numbered item with a bolded title. Covers the prose form used by SYSTEM_REVIEW and
#: BLIND_SPOT_AUDIT (``3. **Name** ...``) and the table form used by the audit inboxes
#: (``| 3 | **CHANGE** thing | ...``). Free prose is deliberately NOT matched -- an unnumbered
#: paragraph is a remark, and treating remarks as obligations is how a check becomes noise.
#: PROSE form: ``3. **Name** ...`` as used by SYSTEM_REVIEW / BLIND_SPOT_AUDIT.
_PROSE_RE = re.compile(r"^\s*(?P<num>\d+)[.)]\s*\*\*(?P<title>[^*]{4,140})\*\*", re.MULTILINE)
#: TABLE form: ``| 3 | **CHANGE** `run_ci` -- fix the job | why | ...``. The whole first cell is
#: the title: capturing only the bolded span yields the VERB ("CHANGE"), which carries no
#: distinctive token and made every audit-inbox row look untracked on the first real run.
_TABLE_RE = re.compile(r"^\s*\|\s*(?P<num>\d+)\s*\|\s*(?P<title>[^|]{4,200})\|", re.MULTILINE)
#: Headings whose contents are already settled. Anything under one of these is reported as
#: resolved rather than owed -- the inboxes carry large "already live" and "closed" sections, and
#: demanding register rows for them would bury the real items.
_SETTLED_HEAD = re.compile(
    r"already live|duplicat|closed|resolved|done|shipped|complete|history|archive|graveyard",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<h>.+?)\s*$", re.MULTILINE)
#: Words too common to prove a match -- "risk" appearing in the register means nothing.
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "onto", "your", "our", "not",
    "add", "fix", "wire", "change", "risk", "data", "test", "tests", "code", "live", "desk",
    "new", "old", "all", "any", "one", "two", "use", "using", "make", "made", "gap", "audit",
    "check", "checks", "build", "built", "run", "runs", "only", "per", "via", "its", "has",
}


class Finding(BaseModel):
    """One numbered finding, wherever it was written."""

    model_config = ConfigDict(frozen=True)

    source: str
    number: int
    title: str
    settled: bool = False   # written under an already-live / closed heading

    @property
    def tokens(self) -> tuple[str, ...]:
        """Distinctive words that would identify this finding in another document."""
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_.-]{3,}", self.title.lower())
        return tuple(w for w in words if w not in _STOP)


def parse_findings(text: str, *, source: str) -> list[Finding]:
    """Extract numbered, bolded findings and mark the ones sitting under a settled heading."""
    heads = [(m.start(), m.group("h")) for m in _HEADING_RE.finditer(text)]
    out: list[Finding] = []
    matches = sorted(list(_PROSE_RE.finditer(text)) + list(_TABLE_RE.finditer(text)),
                     key=lambda m: m.start())
    for m in matches:
        title = re.sub(r"[*`]", "", m.group("title"))
        title = re.sub(r"\s+", " ", title).strip(" -—:")
        if not title:
            continue
        prior = [h for pos, h in heads if pos < m.start()]
        settled = bool(prior and _SETTLED_HEAD.search(prior[-1]))
        out.append(Finding(source=source, number=int(m.group("num")),
                           title=title, settled=settled))
    return out


def is_tracked(finding: Finding, register: str) -> bool:
    """Does the register carry any trace of this finding?

    Generous by design: one distinctive token is enough. The check exists to catch findings with
    NO representation at all, not to police wording.
    """
    reg = register.lower()
    if not finding.tokens:
        # Nothing distinctive to search for -- unjudgeable, so it is NOT accused. A check that
        # reports items it cannot actually evaluate is manufacturing work, not finding it.
        return True
    return any(tok in reg for tok in finding.tokens)


def untracked(findings: Iterable[Finding], register: str) -> tuple[Finding, ...]:
    """Open findings with no trace in the register -- the ones the daily cycle cannot see."""
    return tuple(f for f in findings if not f.settled and not is_tracked(f, register))


class CoverageReport(BaseModel):
    """How much of what the desk has FOUND is actually being DRIVEN."""

    model_config = ConfigDict(frozen=True)

    n_findings: int
    n_settled: int
    n_open: int
    n_untracked: int
    coverage: float          # tracked / open; 1.0 = every open finding reaches the register
    untracked_names: tuple[str, ...]
    verdict: str


def coverage_report(
    findings: Sequence[Finding], register: str, *, max_shown: int = 10
) -> CoverageReport:
    """Measure finding -> register coverage. Below 1.0, the cycle is blind to real work."""
    settled = [f for f in findings if f.settled]
    open_ = [f for f in findings if not f.settled]
    ut = untracked(findings, register)
    cov = 1.0 if not open_ else round(1.0 - len(ut) / len(open_), 3)
    if not open_:
        verdict = "no open findings parsed -- nothing owed"
    elif not ut:
        verdict = (f"all {len(open_)} open finding(s) have a register trace "
                   "-- the cycle can see them")
    else:
        verdict = (
            f"{len(ut)}/{len(open_)} open finding(s) have NO register trace ({cov:.0%} coverage). "
            "The daily cycle acts on the register; anything absent from it is invisible and will "
            "never be worked, however carefully it was found."
        )
    return CoverageReport(
        n_findings=len(findings), n_settled=len(settled), n_open=len(open_),
        n_untracked=len(ut), coverage=cov,
        untracked_names=tuple(f"{f.source.rsplit('/', 1)[-1]}#{f.number} {f.title[:60]}"
                              for f in ut[:max_shown]),
        verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# THE COVERAGE RATCHET. A one-off 100% is a snapshot; the law needs a floor that only ever rises.
# And the cheapest way to reach 100% is NOT to row the findings -- it is to SHRINK THE DENOMINATOR:
# exclude a doc from scope, or delete the finding. That is the same loophole §34 closed for mining
# (fake a conversion rate by mining less), so it is closed the same way: scope size and finding
# count ratchet UP alongside coverage, and all three are held against the desk's own best.
# --------------------------------------------------------------------------------------------

class CoverageRatchet(BaseModel):
    """Best-ever finding→register coverage AND the scope it was achieved over."""

    model_config = ConfigDict(frozen=True)

    best_coverage: float = 0.0
    max_open_findings: int = 0   # denominator high-water mark -- scope may never shrink
    max_docs_scanned: int = 0
    best_at: str = ""
    n_records: int = 0


class RatchetVerdict(BaseModel):
    """Did coverage hold, improve, or regress -- and was the denominator honest?"""

    model_config = ConfigDict(frozen=True)

    improved: bool
    coverage_regressed: bool
    scope_shrank: bool
    verdict: str


def update_coverage_ratchet(
    prior: CoverageRatchet,
    report: CoverageReport,
    *,
    n_docs: int,
    at: str = "",
) -> tuple[CoverageRatchet, RatchetVerdict]:
    """Hold coverage against the desk's own best, over a scope that may never shrink.

    THREE things ratchet, because any one alone is gameable:
      COVERAGE        -- the share of open findings the cycle can see; never allowed to fall.
      OPEN FINDINGS   -- the denominator. Deleting findings raises coverage arithmetically while
                        making the desk blinder, so the count is a high-water mark too.
      DOCS SCANNED    -- excluding a findings doc raises coverage the same dishonest way.

    A worse cycle NEVER relaxes any of the three; it produces a defect instead. That asymmetry is
    the whole mechanism -- a standard that can fall is a standard the desk drifts past.
    """
    cov_record = report.coverage > prior.best_coverage
    cov_regressed = bool(prior.best_coverage and report.coverage < prior.best_coverage - 1e-9)
    shrank = bool(
        (prior.max_open_findings and report.n_open < prior.max_open_findings)
        or (prior.max_docs_scanned and n_docs < prior.max_docs_scanned)
    )
    improved = bool(cov_record or report.n_open > prior.max_open_findings
                    or n_docs > prior.max_docs_scanned)

    new = CoverageRatchet(
        best_coverage=max(prior.best_coverage, report.coverage),
        max_open_findings=max(prior.max_open_findings, report.n_open),
        max_docs_scanned=max(prior.max_docs_scanned, n_docs),
        best_at=(at or prior.best_at) if improved else prior.best_at,
        n_records=prior.n_records + (1 if improved else 0),
    )

    if shrank:
        verdict = (
            f"SCOPE SHRANK: {report.n_open} open findings over {n_docs} docs vs a high-water "
            f"{prior.max_open_findings} over {prior.max_docs_scanned}. Coverage rises "
            "arithmetically when findings or docs disappear -- that is a blinder desk, not a "
            "better one. Restore the scope or record why the items are legitimately closed."
        )
    elif cov_regressed:
        verdict = (
            f"COVERAGE REGRESSED: {report.coverage:.0%} vs best-ever {prior.best_coverage:.0%}. "
            "New findings were written without register rows. Row them; the floor only rises."
        )
    elif report.coverage >= 1.0:
        verdict = (
            f"100% -- all {report.n_open} open finding(s) across {n_docs} docs reach the register. "
            "Hold it: the bar is now this, permanently."
        )
    elif cov_record:
        verdict = (f"coverage record {report.coverage:.0%} (prev {prior.best_coverage:.0%}) -- "
                   "floor raised, it never lowers. Target is 100%.")
    else:
        verdict = (f"coverage {report.coverage:.0%} holding at the floor. Holding is not reaching: "
                   f"{report.n_untracked} finding(s) are still invisible to the cycle.")
    return new, RatchetVerdict(improved=improved, coverage_regressed=cov_regressed,
                               scope_shrank=shrank, verdict=verdict)
