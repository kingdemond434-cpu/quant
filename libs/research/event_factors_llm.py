"""THE OPTIONAL LLM TIER for event/policy factors -- a second reader, never the only one.

The lexicon tier (`libs.research.event_factors.tag`) runs on every document at zero cost and
always carries the run. This tier asks a model the same question -- which of the six factors does
this title speak to, with which pole, about which country -- for a BOUNDED batch of documents per
pass, through the desk's one seat (`libs.ops.llm_seat`, free tier by default).

IT NEVER REPLACES THE LEXICON. Its tags are published as their own `tier="llm"` panel rows beside
the lexicon's, so the gain test can say which reader earned anything; a model that disagrees with
the lexicon is a measurement, not an override.

NO SEAT IS UNMEASURED, NOT ZERO (L1.28a). With no key the status is `UNMEASURED` with the reason,
nothing is written as a measured absence, and the lexicon tier alone carries the pass. A model
reply that cannot be parsed is counted per document, never guessed at.

The chat function is injectable so the tier is testable without a network or a key.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from libs.research.event_factors import FACTORS, GLOBAL, Doc, FactorTag

UNMEASURED = "UNMEASURED"
BATCH = 20
DEFAULT_MAX_DOCS = 60

SYSTEM = ("You tag news and report titles for a research desk. You never forecast prices. For "
          "each item return the factors its TEXT speaks to and the pole of each, as JSON only.")
PROMPT_HEAD = (
    "Factors and poles (+1 / -1):\n"
    "  monetary_tone: +1 tightening/hawkish, -1 easing/dovish\n"
    "  fiscal_stimulus: +1 stimulus/expansion, -1 austerity\n"
    "  export_controls: +1 controls/sanctions imposed, -1 lifted/relieved/trade deal\n"
    "  supply_shock: +1 disruption/shortage, -1 restored/glut\n"
    "  earnings_guidance: +1 raised/beat, -1 cut/miss\n"
    "  geopolitical_risk: +1 escalation, -1 de-escalation\n"
    "Return a JSON list, one object per item: {\"id\": str, \"country\": ISO-2 or \"GLOBAL\", "
    "\"factors\": {factor: -1|0|1}}. Omit factors the text does not mention. Items:\n")

ChatFn = Callable[[str, str], tuple[str, str | None]]


def doc_hash(doc: Doc) -> str:
    return hashlib.sha256(f"{doc.doc_id}|{doc.text[:400]}".encode()).hexdigest()[:16]


def _default_chat() -> tuple[ChatFn | None, str]:
    try:
        from libs.ops import llm_seat
    except Exception as exc:                              # pragma: no cover - import context
        return None, f"llm_seat unimportable: {type(exc).__name__}"
    seat = llm_seat.primary_seat()
    if seat is None:
        return None, ("no LLM seat on this machine (no OPENROUTER_API_KEY / OPENAI_API_KEY and no "
                      "data/secrets/llm_panel.json); the lexicon tier carries the run")

    def call(prompt: str, system: str) -> tuple[str, str | None]:
        return llm_seat.chat(prompt, system=system, seat=seat, max_tokens=4000, temperature=0.0)

    return call, f"seat {seat.name} (free tier={llm_seat.free_tier_only()})"


def _parse(reply: str) -> list[dict[str, Any]]:
    m = re.search(r"\[.*\]", reply or "", flags=re.S)
    if not m:
        return []
    try:
        got = json.loads(m.group(0))
    except ValueError:
        return []
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


def _to_tag(row: Mapping[str, Any]) -> FactorTag | None:
    raw = row.get("factors")
    if not isinstance(raw, Mapping):
        return None
    counts: dict[str, int] = {}
    signed: dict[str, int] = {}
    for f, v in raw.items():
        if f not in FACTORS:
            continue
        try:
            s = round(float(v))
        except (TypeError, ValueError):
            continue
        counts[f] = 1
        signed[f] = max(-1, min(1, s))
    country = str(row.get("country") or GLOBAL).upper()[:6] or GLOBAL
    return FactorTag(lang="", countries=(country,), counts=counts, signed=signed, tier="llm")


def llm_tags(docs: Sequence[Doc], *, max_docs: int = DEFAULT_MAX_DOCS,
             cache: Mapping[str, Mapping[str, Any]] | None = None,
             chat: ChatFn | None = None) -> tuple[dict[str, FactorTag], dict[str, Any]]:
    """Tags for up to `max_docs` UNCACHED documents, plus a status the report publishes as is.

    Returns (doc_id -> FactorTag, status). `status["state"]` is UNMEASURED when there is no seat,
    OK when at least one batch parsed, FAILED when every call errored. `status["new_cache"]` holds
    the rows to append to the caller's cache so the same title is never paid for twice.
    """
    cache = cache or {}
    out: dict[str, FactorTag] = {}
    for d in docs:
        hit = cache.get(doc_hash(d))
        if hit is not None:
            t = _to_tag(hit)
            if t is not None:
                out[d.doc_id] = t
    todo = [d for d in docs if doc_hash(d) not in cache][: max(0, int(max_docs))]
    status: dict[str, Any] = {"tier": "llm", "from_cache": len(out), "asked": 0, "parsed": 0,
                              "unparsed": 0, "errors": [], "new_cache": []}
    if not todo:
        status["state"] = "OK" if out else UNMEASURED
        status["why"] = "nothing new to ask" if out else "no documents to tag"
        return out, status
    how = "injected"
    if chat is None:
        chat, how = _default_chat()
    status["seat"] = how
    if chat is None:
        status["state"], status["why"] = UNMEASURED, how
        return out, status
    ok_batches = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        items = "\n".join(json.dumps({"id": d.doc_id, "text": d.text[:300]}, ensure_ascii=False)
                          for d in batch)
        status["asked"] += len(batch)
        reply, err = chat(PROMPT_HEAD + items, SYSTEM)
        if err:
            status["errors"].append(str(err)[:160])
            continue
        ok_batches += 1
        by_id = {str(r.get("id")): r for r in _parse(reply)}
        for d in batch:
            row = by_id.get(d.doc_id)
            t = _to_tag(row) if row is not None else None
            if t is None:
                status["unparsed"] += 1
                continue
            status["parsed"] += 1
            out[d.doc_id] = t
            status["new_cache"].append({"hash": doc_hash(d), "doc_id": d.doc_id, **dict(row or {})})
    status["state"] = "OK" if ok_batches else "FAILED"
    return out, status
