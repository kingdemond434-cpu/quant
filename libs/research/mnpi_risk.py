"""MNPI_RISK: a public claim that may carry material non-public information is tagged and kept
out of the gauntlet, never silently dropped.

THE BOUNDARY IS LAWS 5e, NOT TASTE. Of everything publicly visible, the desk refuses five acts and
nothing else; carrying material non-public information is one of them. The intake already refuses
it at the SOURCE level (the access classifier's CONFIDENTIAL_MNPI / PRIVATE / STOLEN_UNAUTHORIZED
classes) and the frontier organ refuses it capital authority (`frontier_intel.claims.mnpi_guard`).
What had no fence was the ROW level: a forum post, a rumour thread or a seat's donation on a
perfectly public ground can still say "my contact at the company says the results are bad, not
announced yet", and the docket compiler would have turned that sentence into a judged cell. A
certificate minted from it would be a position sized off somebody else's breach of duty.

WHAT HAPPENS TO A TAGGED ROW. It is not deleted and not deepened (deepening would ask a seat to
extract a rule from the very sentence the fence refused). It is a NAMED refusal (`MNPI_RISK`)
in the compiler's per-seat dispositions, and every tagged row is listed, with its source, its
coordinate and the phrase that tripped the tag, under `mnpi_risk` in `miner_candidates.json`. A
person can read every one; the GENERAL mechanism such a row gestures at is usually public anyway
and reaches the docket through any other row that states it lawfully.

DELIBERATELY NARROW (growth governance, Rule 1). A fence that over-fires is a research veto, and
a veto must earn its place. So the vocabulary is the language of POSSESSION of undisclosed
material ("not yet public", "inside information", "a friend at the firm told me", "under
embargo"), never the words of lawful public disclosure: "insider buying", "Form 4", "13D",
"ahead of the release" (lawful event trading on a SCHEDULED disclosure), "leaked" in a published
news report and "confidential" in a court filing that has since been
published are all public information and are NOT tagged. The count of tagged rows is published
every pass, so an over-firing vocabulary is measured, not assumed.
"""
from __future__ import annotations

import re
from typing import Any

TAG = "MNPI_RISK"

#: Source access classes the intake's classifier already refuses (LAWS 5e). A row that carries
#: one of them is tagged whatever its text says.
REFUSED_ACCESS_CLASSES = frozenset({"CONFIDENTIAL_MNPI", "PRIVATE", "STOLEN_UNAUTHORIZED"})

#: Phrases that assert POSSESSION of undisclosed, price-relevant material. Each alternative names
#: the act (a tip, a leak to the writer, an embargo, a not-yet-public figure), not a topic.
_POSSESSION = re.compile(
    r"\b(?:"
    r"insider (?:tip|tips|info|information|knowledge|source)"
    r"|inside (?:info|information|knowledge|source|scoop)"
    r"|material(?:ly)? non[- ]?public"
    r"|non[- ]?public (?:info|information|data|figures|numbers|results)"
    r"|not yet (?:public|disclosed)|not public yet|before (?:it(?:'s| is) )?made public"
    r"|unannounced (?:results|earnings|deal|merger|acquisition|takeover|figures)"
    r"|under embargo|embargoed (?:data|figures|release|results|numbers)"
    r"|leaked to (?:me|us)"
    r"|(?:internal|confidential) (?:memo|document|figures|numbers|data|results)"
    r"|(?:my|a) (?:friend|cousin|brother|sister|contact|source|buddy|mate)"
    r" (?:at|inside|who works (?:at|for))"
    r"|(?:works|working) (?:at|for) the company (?:told|said|says)"
    r"|heard (?:it )?from (?:someone|somebody|a guy|a person) (?:at|inside|in)"
    r"|(?:under|signed an?) nda"
    r")\b",
    re.I,
)

#: The text fields a donated row states its claim in (the compiler's own `_TEXT_FIELDS` order).
TEXT_FIELDS = ("title", "text", "summary", "description", "abstract", "body", "content",
               "claim", "quote", "verbatim", "mechanism", "rationale", "note", "snippet")
_MAX_CHARS = 20_000


def _text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in TEXT_FIELDS:
        value = row.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    return " ".join(parts)[:_MAX_CHARS]


def mnpi_risk(row: dict[str, Any]) -> str | None:
    """The reason this row carries MNPI risk, or None.

    An explicit upstream flag wins (a seat or a ground that already judged the row), then the
    source's refused access class, then the possession vocabulary. Never raises on odd rows.
    """
    if not isinstance(row, dict):
        return None
    flag = row.get("mnpi_risk")
    tags = row.get("tags")
    if flag is True or (isinstance(tags, list) and TAG in tags):
        return "flagged upstream"
    for key in ("access_class", "access", "source_class"):
        value = row.get(key)
        if isinstance(value, str) and value.upper() in REFUSED_ACCESS_CLASSES:
            return f"access class {value.upper()}"
    match = _POSSESSION.search(_text(row))
    if match:
        return f"phrase {match.group(0).lower()!r}"
    return None


class MnpiTally:
    """Every tagged row of one compiler pass, listed in full: nothing is silently dropped."""

    def __init__(self) -> None:
        self.checked = 0
        self.rows: list[dict[str, Any]] = []
        self.by_source: dict[str, int] = {}
        self.by_reason: dict[str, int] = {}

    def add(self, source: str, row: dict[str, Any], reason: str | None) -> bool:
        """Record one checked row; True when it was tagged."""
        self.checked += 1
        if not reason:
            return False
        self.by_source[source] = self.by_source.get(source, 0) + 1
        self.by_reason[reason] = self.by_reason.get(reason, 0) + 1
        title = str(row.get("title") or row.get("description") or row.get("text") or "")
        self.rows.append({
            "tag": TAG,
            "source": source,
            "reason": reason,
            "url": str(row.get("url") or row.get("source_url") or "")[:500],
            "title": title[:300],
            "symbols": [s for s in (row.get("symbols") or []) if isinstance(s, str)][:8]
            if isinstance(row.get("symbols"), list) else [],
            "family": row.get("family") if isinstance(row.get("family"), str) else None,
        })
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": TAG,
            "checked": self.checked,
            "tagged": len(self.rows),
            "by_source": dict(sorted(self.by_source.items(), key=lambda kv: -kv[1])),
            "by_reason": dict(sorted(self.by_reason.items(), key=lambda kv: -kv[1])),
            "rows": self.rows,
            "rule": ("a row whose claim may carry material non-public information is tagged "
                     "MNPI_RISK, kept out of the docket and the deepening queue, and listed "
                     "here in full (LAWS 5e); its general mechanism reaches the gauntlet only "
                     "through a row that states it lawfully"),
        }
