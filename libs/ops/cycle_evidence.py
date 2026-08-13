"""ONE DEFINITION OF CYCLE EVIDENCE, shared by every fence that judges a cycle log (R0336).

WHY THIS MODULE EXISTS. Two fences scored a cycle on VOCABULARY and on FORMAT, and on
2026-08-01 they returned CONTRADICTORY verdicts about the same log:

    check_interrogation          -> "shows no self-interrogation evidence"   (absence)
    check_rubberstamp_enforcement-> "interrogation lacks verified-read evidence" (presence,
                                     uncited)

Both cannot be true. The first grepped for five magic words ('interrogat', 'probe',
'verified with a fresh read', 'self-interrog', 'angle') and the cycle had simply never typed
one -- while it had in fact verified its headline finding from the journal with timestamps and
values, disproved a CI-red by isolation, and carried an explicit skepticism section. A FALSE
POSITIVE on substance. The second counted path-shaped tokens, found one, and was CORRECT on
format: that cycle named its evidence as bare module attributes (``max_audit.CHECKS``,
``desk_memory._test_exists``) instead of by path.

So the desk held two instruments pointed at the same object, disagreeing, and BOTH were gameable
in the cheap direction and punishing in the expensive one: type the word "probe" once and the
first passes; paste five filenames you never opened and the second passes; write a genuinely
adversarial cycle in your own words and both fire. A fence that cries wolf on a good cycle gets
acknowledged into silence, and that is how enforcement actually dies -- both defects were acked
for 14 days rather than fixed, which is the observation that produced this module.

WHAT IS SCORED INSTEAD -- the three signals a real interrogation actually emits:

  1. CITED CLAIM (primary, structural, thresholded). A named artifact AND a value on the same
     line. This is not a proxy invented here; it is exactly what the cycle prompt already
     demands -- "CITE THE SPECIFIC ARTIFACT you read this cycle (file path + the value/line you
     saw), e.g. 'read web/growth_audit.json, capital_util=1.005'". The old fence counted only
     the path half of that pair and never looked for the value.
  2. SELF-CORRECTION (corroborating). A statement against the cycle's own interest: a duty
     recorded as unmet, a claim of its own withdrawn.
  3. REFUTATION (corroborating). A finding DISPROVED rather than asserted.

THE THRESHOLD IS NOT LOWERED, AND THAT IS DELIBERATE. ``CITED_FLOOR`` is 5, the same number the
fence it replaces used -- but each of those 5 must now carry a value, which is strictly HARDER
than naming five paths. Editing a guard to fit the violation it caught is a failure this desk
has paid for repeatedly; the fix here is a better MEASUREMENT at the same bar, never a smaller
bar. The only thing that gets easier is the question the interrogation fence asks, and only
because that question was being asked wrongly: it now fires on the TOTAL ABSENCE of evidence
rather than on the absence of five specific words.

WHY THIS MAKES CONTRADICTION STRUCTURALLY IMPOSSIBLE. Both fences read one ``CycleEvidence``
computed once. ``check_interrogation`` fires only when ``substance == 0`` -- nothing cited,
nothing corrected, nothing refuted. ``check_rubberstamp_enforcement`` fires when
``cited_claims < CITED_FLOOR``. Since ``cited_claims > 0`` implies ``substance > 0``, the first
can never assert absence while the second asserts presence. The 2026-08-01 state -- interrogated
well, cited badly -- is now expressible: exactly one fence fires, and it is the right one.

NO JUDGEABLE LOG IS ``UNMEASURED``, NEVER OK (L1.28a, L1.57). Both predecessors returned
silently when their glob found nothing (``if not cyc: return``), so "no cycle ran at all" was
byte-identical to "the cycle cited its reads well". That is the vacuous pass L1.57 exists to
refuse: a verdict earned over an empty scan set. ``measured=False`` is a first-class state here
and the caller must render it as its own defect, not fold it into health.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

#: Minimum distinct artifacts-cited-with-a-value before an interrogation counts as CITED.
#: Unchanged from the fence this replaces -- see the module docstring on why it does not move.
CITED_FLOOR = 5

#: An artifact reference: a real path. Either something carrying a known data/code extension, or
#: something under one of the repo's top-level directories. An optional ``:123`` line suffix is
#: kept because the prompt accepts a line as the value. Deliberately NOT widened to bare module
#: attributes (``max_audit.CHECKS``): those are what the desk cites when it is citing badly, and
#: the forward fix for them is the cycle PROMPT, not a looser fence.
_ARTIFACT_RE = re.compile(
    r"(?:data|web|docs|libs|scripts|ops|tests|reports)/[\w./*?-]+"
    r"|[\w./-]*[\w*?]\.(?:md|json|jsonl|log|csv|parquet|py|sh|sqlite|txt|ya?ml)\b"
)

#: A value: a number in any dialect this desk writes -- signed, thousands-separated, decimal,
#: percentage, bps, currency, ratio, or a bare line number. The unicode minus is included
#: because the desk's own reports use it (``net_pnl -1869.74``).
_VALUE_RE = re.compile(
    r"[-+−]?\$?\d[\d,]*(?:\.\d+)?\s*(?:%|bps?|bp|x|d|h|/day|/d)?"  # noqa: RUF001
)

#: Statements against the cycle's own interest. Short and curated ON PURPOSE: these corroborate,
#: they never carry the threshold, so widening them cannot buy a pass on their own.
_SELF_CORRECTION = (
    "not done", "no new hypotheses", "named as a debt", "corrections to the record",
    "i was wrong", "my own hypotheses were wrong", "shortfall", "i'm not dressing",
    "not dressing it as satisfied", "unmet floor", "did not do", "failed to",
)

#: A finding DISPROVED rather than asserted.
_REFUTATION = (
    "refuted", "disproved", "disproven", "rejected on", "premise refuted", "turned out to be",
    "false positive", "self-resolved", "is not a", "never happened", "does not hold",
)


@dataclass(frozen=True)
class CycleEvidence:
    """What one cycle log actually demonstrates. Every field is an observation, not a target."""

    log: str                    #: name of the log judged; "" when nothing was judgeable
    measured: bool              #: False -> UNMEASURED; the caller must NOT read this as health
    why_unmeasured: str
    cited_claims: int           #: distinct artifacts named WITH a value on the same line
    artifacts: int              #: distinct artifacts named at all (the old, weaker signal)
    self_corrections: int
    refutations: int

    @property
    def substance(self) -> int:
        """Any evidence of probing at all. Zero means the cycle asserted and never checked."""
        return self.cited_claims + self.self_corrections + self.refutations

    @property
    def cited(self) -> bool:
        """Did the interrogation carry its citations? The thresholded question."""
        return self.cited_claims >= CITED_FLOOR

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["substance"] = self.substance
        d["cited"] = self.cited
        return d


def unmeasured(why: str) -> CycleEvidence:
    """The honest verdict when there is no judgeable cycle log. Never OK, never a clean pass."""
    return CycleEvidence(log="", measured=False, why_unmeasured=why, cited_claims=0,
                         artifacts=0, self_corrections=0, refutations=0)


def _count_phrases(low: str, phrases: tuple[str, ...]) -> int:
    return sum(1 for p in phrases if p in low)


def score(text: str, *, log_name: str = "") -> CycleEvidence:
    """Score one cycle log's TEXT for the three substance signals.

    A CITED CLAIM is an artifact and a value on the SAME LINE. The artifact tokens are removed
    from the line before the value is looked for, so a log that merely names
    ``20260811_2000.log`` cannot satisfy itself with the digits inside its own filename.
    """
    artifacts: set[str] = set()
    cited: set[str] = set()
    for line in text.splitlines():
        found = _ARTIFACT_RE.findall(line)
        if not found:
            continue
        artifacts.update(found)
        residue = _ARTIFACT_RE.sub(" ", line)
        if _VALUE_RE.search(residue):
            cited.update(found)
    low = text.lower()
    return CycleEvidence(
        log=log_name,
        measured=True,
        why_unmeasured="",
        cited_claims=len(cited),
        artifacts=len(artifacts),
        self_corrections=_count_phrases(low, _SELF_CORRECTION),
        refutations=_count_phrases(low, _REFUTATION),
    )
