"""COMMITMENT PRESERVATION -- what a doctrine edit is allowed to change, and what it is not.

WHY THIS EXISTS BEFORE THE EDIT IT ENABLES. `principal_doctrine.txt` is prepended to EVERY
reasoning organ on this desk, so its length is a tax on every call the desk makes -- 34.5k chars
against a 16k bar, which max_audit has reported as `prompt-doctrine-bloat` for weeks. The audit's
own advice is "consolidate the stacked axiom blocks into tighter prose (preserve every commitment,
cut the repetition)".

The dangerous half of that sentence is the parenthesis. Rewriting thirty thousand characters of
principal-authored law by hand, with nothing verifying the result, is precisely the failure this
desk keeps finding in itself: a change that looks fine, ships, and silently drops an obligation
nobody notices is missing until it is needed. A shorter doctrine that lost a law is strictly worse
than a long one that kept it -- the tax is paid per call, but a dropped commitment is paid once,
catastrophically, at an unknown later date.

So consolidation is gated on a mechanical proof. A COMMITMENT here is anything that could be
ACTED ON or CHECKED AGAINST -- the parts of the text that do work rather than the parts that
explain:

  section marks     §33, §35, §41 -- laws referred to by number elsewhere in the codebase
  defect names      mine-law-ineffective, findings-scope-shrank -- checks that actually fire
  artifact paths    data/..., docs/..., scripts/..., web/... -- files the doctrine points at
  thresholds        2%, 25%, 40d, T1=8 -- numbers an organ is expected to honour
  named laws        NO-CEILING AXIOM, DEPTH PARITY -- clauses cited by name

Prose may be rewritten freely. Every token above must survive. That asymmetry is the whole design:
it makes "cut the repetition" safe and "cut the law" impossible.

Pure, dependency-free, no I/O.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "PATTERNS",
    "diff",
    "extract",
    "preserved",
]

#: name -> regex whose every match is a commitment that must survive an edit. Deliberately
#: over-inclusive: a false positive costs one phrase that must be kept, while a false negative
#: costs a law nobody notices is gone. That trade is not close.
PATTERNS: dict[str, str] = {
    # Section marks. Cited by number from max_audit, the cycle prompt and other docs, so losing
    # one silently breaks a cross-reference rather than merely shortening a file.
    "section": r"§\s?\d+",
    # Defect / check identifiers. These are the names checks actually emit, so a doctrine that
    # stops mentioning one leaves an organ with no instruction for a defect it will still see.
    "defect": r"\b[a-z][a-z0-9]+(?:-[a-z0-9]+){1,4}\b(?=[\s.,)\]]|$)",
    # Artifact paths the doctrine directs organs to read or write.
    "path": r"\b(?:data|docs|scripts|web|libs|ops)/[A-Za-z0-9_./-]+",
    # Numbers that an organ is expected to honour. Percentages, day-clocks, tier weights.
    "threshold": r"(?<![\w.])\d+(?:\.\d+)?\s?(?:%|d\b|h\b|-day\b|-cycle\b)",
    "tier_weight": r"\bT[1-4]\s?=\s?\d+",
    # Laws cited by NAME rather than by number -- an ALL-CAPS multi-word clause label.
    "named_law": r"\b[A-Z][A-Z-]{3,}(?:\s+[A-Z][A-Z-]{2,}){1,5}\b",
    # Inline disposition tokens, which are a literal grammar organs must emit.
    "disposition": r"\[§\s?\d+:\s?[a-z]+",
}

#: Matches that are noise rather than commitments. Kept explicit and small: every entry here is a
#: hole in the guarantee, so each one has to earn its place. These are English words that happen
#: to fit the hyphenated-identifier shape, never real check names.
_NOISE = frozenset({
    "self-improvement", "max-roi", "cross-reference", "day-to-day", "self-defeating",
    "half-built", "motion-for-its-own-sake", "activity-theater", "well-framed",
    "state-of-the-art", "long-term", "short-term", "so-called", "pre-live", "post-live",
    "read-only", "up-to-date", "end-to-end", "one-line", "high-water", "real-time",
})


def extract(text: str) -> dict[str, set[str]]:
    """Every commitment in `text`, grouped by kind.

    Case is preserved for named laws (they are cited verbatim) and lowered for defect names
    (which are always lowercase identifiers), so the comparison is exact where exactness matters
    and forgiving where it does not.
    """
    out: dict[str, set[str]] = {}
    for kind, pat in PATTERNS.items():
        found = set()
        for m in re.findall(pat, text):
            tok = m.strip()
            if kind == "defect":
                tok = tok.lower()
                if tok in _NOISE or tok.count("-") == 0:
                    continue
            if kind == "section":
                tok = tok.replace(" ", "")
            if kind == "threshold":
                tok = tok.replace(" ", "")
            if tok:
                found.add(tok)
        out[kind] = found
    return out


def preserved(before: str, after: str) -> bool:
    """Did `after` keep every commitment `before` made?"""
    return not any(diff(before, after).values())


def diff(before: str, after: str) -> dict[str, list[str]]:
    """Commitments present in `before` and MISSING from `after`, by kind.

    One-directional on purpose. Adding a commitment is a normal edit -- the doctrine grows when
    the principal decides something new. Removing one is the operation that needs a proof, and
    this is the proof.
    """
    b, a = extract(before), extract(after)
    return {k: sorted(v - a.get(k, set())) for k, v in b.items() if v - a.get(k, set())}


def report(before: str, after: str) -> dict[str, Any]:
    """Human-readable verdict for a consolidation attempt."""
    missing = diff(before, after)
    n_missing = sum(len(v) for v in missing.values())
    b_all = extract(before)
    total = sum(len(v) for v in b_all.values())
    return {
        "chars_before": len(before),
        "chars_after": len(after),
        "chars_saved": len(before) - len(after),
        "pct_saved": round(100.0 * (len(before) - len(after)) / max(1, len(before)), 1),
        "commitments_before": total,
        "commitments_kept": total - n_missing,
        "missing": missing,
        "safe": n_missing == 0,
        "note": (
            "every commitment survived -- the edit removed prose, not law"
            if n_missing == 0 else
            f"{n_missing} commitment(s) were LOST. A shorter doctrine that dropped a law is "
            "strictly worse than a long one that kept it: the length tax is paid per call, but a "
            "missing obligation is paid once, catastrophically, at an unknown later date."),
    }
