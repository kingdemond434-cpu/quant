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
from datetime import date

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


# --------------------------------------------------------------------------------------------
# THE REGISTER'S OWN HEALTH. §35 and §36 route everything INTO the register, which makes it the
# load-bearing organ for both -- and it was never checked itself. Its rules ("re-ranked at the
# START of every daily cycle", "items stale >7 days MUST be escalated", "never empty without
# written justification") are written INSIDE the register, which is precisely the shape §36 names
# as a rule with no clock. Routing findings into a bucket nobody empties is not an improvement.
# --------------------------------------------------------------------------------------------

_RERANK_RE = re.compile(r"Re-ranked\s+(\d{4}-\d{2}-\d{2})")
#: A register row: | id | **title** | mechanism | plan | owner | added | status |
_ROW_RE = re.compile(
    r"^\|\s*(?P<id>\d+)\s*\|\s*\*\*(?P<title>.+?)\*\*\s*\|(?P<body>.*?)\|\s*(?P<owner>[a-z+ ]*?)"
    r"\s*\|\s*(?P<added>[\d-]*)\s*\|\s*(?P<status>[^|]*?)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_OPEN_STATUS = ("open", "in-progress", "in progress", "queued", "watch", "pending")
#: Any date-shaped token in the plan text -- evidence the "defer WITH A DEADLINE" exit was taken.
_HAS_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}\b")


class RegisterRow(BaseModel):
    """One tracked obligation."""

    model_config = ConfigDict(frozen=True)

    row_id: int
    title: str
    owner: str
    added: str
    status: str
    plan_has_date: bool

    @property
    def is_open(self) -> bool:
        return self.status.strip().lower().startswith(_OPEN_STATUS)

    def age_days(self, today: date) -> float:
        """Days since this row was ADDED. -1 when the date is missing or unparseable.

        The register writes `MM-DD` with no year. A date that would land in the future is read as
        last year's -- the only reading that does not turn a December row into a -300-day-old one
        every January, which would silently exempt the oldest rows exactly when they matter most.
        """
        raw = self.added.strip()
        if not raw:
            return -1.0
        try:
            month, day = (int(x) for x in raw.split("-")[:2])
            when = date(today.year, month, day)
        except (ValueError, TypeError):
            return -1.0
        if when > today:
            try:
                when = date(today.year - 1, month, day)
            except ValueError:      # pragma: no cover - 29 Feb on a non-leap year
                return -1.0
        return float((today - when).days)


class RegisterHealth(BaseModel):
    """Is the desk's only work-driving organ actually being driven?"""

    model_config = ConfigDict(frozen=True)

    n_rows: int
    n_open: int
    rerank_age_days: float      # -1 when no stamp was ever written
    rerank_stale: bool
    rerank_breach: bool         # past the register's own 7-day escalation bar
    undated_open: tuple[str, ...]
    ownerless: tuple[str, ...]
    #: Open rows older than the register's OWN escalation bar. THE rule the register actually
    #: states is about ITEMS ("items stale >7 days MUST be escalated"), not about the re-rank
    #: stamp -- and measuring the stamp instead let a daily re-rank make every row immortal.
    stale_rows: tuple[str, ...]
    oldest_open_days: float
    verdict: str


def parse_register(text: str) -> list[RegisterRow]:
    """Extract every tracked row from the register table."""
    out = []
    for m in _ROW_RE.finditer(text):
        out.append(RegisterRow(
            row_id=int(m.group("id")), title=m.group("title").strip(),
            owner=m.group("owner").strip(), added=m.group("added").strip(),
            status=m.group("status").strip(),
            plan_has_date=bool(_HAS_DATE.search(m.group("body") or "")),
        ))
    return out


def register_health(
    text: str, *, today: date, rerank_bar_days: float = 2.0, escalate_days: float = 7.0
) -> RegisterHealth:
    """Hold the register to the rules it states about itself.

    The re-rank age is read from the register's SELF-DECLARED ``Re-ranked <date>`` stamp, never
    from file mtime or commit time -- touching the file must not be able to fake a re-rank that
    did not happen. Same artifact-only credit principle §33 applies to conversion claims: the
    evidence has to be the thing itself, not a side effect of editing it.
    """
    rows = parse_register(text)
    open_rows = [r for r in rows if r.is_open]
    stamps = _RERANK_RE.findall(text)
    age = -1.0
    if stamps:
        with_dates = []
        for s in stamps:
            try:
                with_dates.append(date.fromisoformat(s))
            except ValueError:  # pragma: no cover
                continue
        if with_dates:
            age = float((today - max(with_dates)).days)

    # An open row whose plan carries no date took NONE of the register's three exits (implement /
    # defer WITH A DEADLINE / retire with reason) -- it is parked, which is the state the rule
    # exists to forbid.
    undated = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.plan_has_date)
    ownerless = tuple(f"#{r.row_id} {r.title[:48]}" for r in open_rows if not r.owner)

    # ROW-LEVEL STALENESS -- the rule the register actually writes down. It says "items stale >7
    # days MUST be escalated"; the first version of this function measured the RE-RANK STAMP
    # instead, so re-stamping the header each morning made every row immortal: 15 rows sat 9-10
    # days untouched while the check reported clean. Measuring the artifact the rule names, rather
    # than a proxy that correlates with tidiness, is the whole point of §36(3).
    aged = sorted(((r.age_days(today), r) for r in open_rows), key=lambda x: -x[0])
    stale_rows = tuple(f"#{r.row_id} ({a:.0f}d) {r.title[:44]}" for a, r in aged
                       if a > escalate_days)
    oldest = aged[0][0] if aged else -1.0

    stale = age > rerank_bar_days
    breach = age > escalate_days

    if not rows:
        verdict = ("register parsed ZERO rows -- either empty or the table shape changed. Its own "
                   "rule is 'never empty without written justification'; a register that cannot "
                   "be parsed drives nothing, and everything §35/§36 routes into it is lost.")
    elif stale_rows:
        verdict = (f"{len(stale_rows)} open row(s) past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar (oldest {oldest:.0f}d), while the re-rank stamp reads "
                   f"{age:.0f}d old. Re-ranking the header is not escalating the rows: each one "
                   "owes implement / defer-with-a-deadline / retire-with-reason.")
    elif breach:
        verdict = (f"re-rank {age:.0f}d old, past the register's OWN {escalate_days:.0f}-day "
                   f"escalation bar, with {len(open_rows)} open row(s). The rule is written in the "
                   "register and was enforced by nothing.")
    elif stale:
        verdict = (f"re-rank {age:.0f}d old against 'at the START of every daily cycle'. "
                   f"{len(open_rows)} open row(s) are not being re-prioritised.")
    else:
        verdict = f"re-rank current ({age:.0f}d), {len(open_rows)} open row(s) under active rank"
    return RegisterHealth(
        stale_rows=stale_rows, oldest_open_days=round(oldest, 1),
        n_rows=len(rows), n_open=len(open_rows), rerank_age_days=age,
        rerank_stale=stale, rerank_breach=breach,
        undated_open=undated[:8], ownerless=ownerless[:8], verdict=verdict,
    )
