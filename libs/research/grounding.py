"""Verbatim grounding for model-extracted claims: a claim the source cannot quote back is not evidence.

Source of the rule: github.com/LLMQuant/quant-mind (MIT, Copyright (c) 2025 LLMQuant),
`quantmind/knowledge/paper.py` (`PaperGlobalSummary.from_drafts`, `PaperCitationValidationError`)
and `quantmind/flows/_paper_summary.py`. Its extraction agents return prose plus a citation per
finding, and code -- never the model -- rejects any citation whose quote is not an exact substring
of the chunk it names; long documents are tiled into fixed groups BY CODE so every chunk is read
exactly once. Desk-native rewrite, no dependency on quantmind; the notice is
`libs/research/LICENSE_quant-mind`.

WHY THE DESK NEEDS IT. The public strategy hunter asks a model to read a page or a transcript
and return a mechanism, a performance claim and an evidence class, and its prompt says "do not
upgrade evidence, infer unseen text". Nothing checked that it obeyed. A model that writes
`evidence_class: LIVE_BROKER_EXCHANGE` about a page that never mentions a broker statement has
promoted a story into a tier, and the hunter's evidence tier is what ranks sources.

WHAT IS CHECKED, AND WHAT IT CHANGES.
  * The model returns `evidence_quotes`: {field: quote or [quotes]} copied from the content.
  * A quote counts only if it is at least `MIN_QUOTE_CHARS` long and appears in the content
    after both sides are normalised (Unicode NFKC, case, whitespace, curly quotes and dashes), so
    a transcript's line breaks cannot fail an honest quote and a three-word fragment cannot pass.
  * A claim field is GROUNDED when one of its quotes verifies. The row records which fields are
    grounded and which are not; nothing is dropped, because the gauntlet, not this check, decides
    whether a mechanism works.
  * Evidence above MARKETING_CLAIM must be quoted: an evidence class or performance claim with
    no verified quote is capped at the MARKETING_CLAIM tier. A tier is a statement about what the
    source SHOWS, and an unquoted one is the model's statement.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

MIN_QUOTE_CHARS = 12
#: The fields whose content is a claim about the source, and so must be quotable.
CLAIM_FIELDS: tuple[str, ...] = ("mechanism", "hypothesis", "signal", "entry", "exit",
                                 "performance_claim", "evidence_class", "falsifier", "costs",
                                 "data")
#: Fields that move a source's evidence tier; unquoted, the tier is capped.
EVIDENCE_FIELDS: tuple[str, ...] = ("evidence_class", "performance_claim")
#: Characters for a tile of a long document (quant-mind's fixed-group map step).
TILE_CHARS = 12_000

_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                       "–": "-", "—": "-", " ": " "})


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text)).translate(_FOLD).casefold()
    return re.sub(r"\s+", " ", t).strip()


def _quotes(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if isinstance(v, str)]
    return []


def verify(content: str, quote: str) -> bool:
    q = normalise(quote).strip(" .\"'")
    return len(q) >= MIN_QUOTE_CHARS and q in normalise(content)


def ground(extracted: Mapping[str, Any], content: str,
           fields: tuple[str, ...] = CLAIM_FIELDS) -> dict[str, Any]:
    """Which of the extraction's claim fields the content quotes back."""
    quotes = extracted.get("evidence_quotes")
    quotes = quotes if isinstance(quotes, Mapping) else {}
    norm = normalise(content)
    claimed = [f for f in fields if extracted.get(f) not in (None, "", [], {})]
    grounded, ungrounded, checked, verified = [], [], 0, 0
    for f in claimed:
        ok = False
        for q in _quotes(quotes.get(f)):
            checked += 1
            qn = normalise(q).strip(" .\"'")
            if len(qn) >= MIN_QUOTE_CHARS and qn in norm:
                verified += 1
                ok = True
        (grounded if ok else ungrounded).append(f)
    if not claimed:
        state = "NO_CLAIMS"
    elif not quotes:
        state = "NO_QUOTES"
    elif not ungrounded:
        state = "GROUNDED"
    else:
        state = "PARTIAL" if grounded else "UNGROUNDED"
    return {"state": state, "grounded_fields": grounded, "ungrounded_fields": ungrounded,
            "quotes_checked": checked, "quotes_verified": verified}


def capped_tier(tier: int, grounding: Mapping[str, Any], *, ceiling: int = 0) -> int:
    """The evidence tier, capped at `ceiling` (MARKETING_CLAIM) unless an evidence field is
    grounded."""
    if tier <= ceiling:
        return tier
    if set(EVIDENCE_FIELDS) & set(grounding.get("grounded_fields", ())):
        return tier
    return ceiling


def tiles(text: str, size: int = TILE_CHARS) -> list[tuple[int, int]]:
    """Fixed, contiguous, non-overlapping spans covering `text` exactly once, cut at the last
    whitespace before the boundary when there is one."""
    spans, start, n = [], 0, len(text)
    while start < n:
        end = min(n, start + size)
        if end < n:
            cut = text.rfind(" ", start + size // 2, end)
            end = cut if cut > start else end
        spans.append((start, end))
        start = end
    return spans


PROMPT_CLAUSE = (
    "Also return evidence_quotes: an object mapping each non-null claim field among "
    + ", ".join(CLAIM_FIELDS)
    + " to one or more EXACT contiguous substrings (at least "
    + str(MIN_QUOTE_CHARS)
    + " characters) copied from the RETRIEVED CONTENT that state it. Code checks every quote "
    "against the content; a field with no verifiable quote is recorded as ungrounded, and an "
    "evidence_class or performance_claim without one is capped at MARKETING_CLAIM."
)
