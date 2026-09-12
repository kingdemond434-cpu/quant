"""THE COLD-AUDIT INTAKE — every LLM audit recommendation, classified before it reaches the CEO.

THE PRINCIPAL'S INSTRUCTION, 2026-09-12: the OpenRouter side produces cold audits, critiques and
recommendations. As CEO they are READ daily, and implemented on exactly one criterion -- does this
raise robust forward E[log W] or widen independent edge discovery. Bottlenecks and weaknesses the
audit calls out are fixed when fixing them serves that goal. And three classes are NEVER
implemented, however well argued:

    * TIMID recommendations -- ones whose value comes from doing less
    * anything that REDUCES AGGRESSIVENESS -- a cap, shrink, veto, throttle or smaller book
    * any criticism of the 20% MINIMUM HEAT FLOOR

WHY A CLASSIFIER AND NOT A READER. An LLM audit is fluent and confident, and fluency is exactly
what makes a timid recommendation persuasive: "consider reducing exposure during uncertain regimes"
reads as prudence and is a growth cut with no missed-growth ledger line behind it. The desk has a
standing order against that (LAWS, GROWTH_GOVERNANCE Rule 1), and a standing order enforced by
whoever happens to be reading is not enforced. So the refusal happens HERE, mechanically, before
the recommendation is ranked, and the refusal is RECORDED with the phrase that triggered it -- a
refusal is a measurement, not a silence.

THE HARD PART IS THAT "REDUCE" IS NOT THE SIGNAL. The single most valuable thing an audit can
recommend is reducing CORRELATION, and the second is reducing LOOKAHEAD. Both are reductions and
both raise E[log W]; n_eff = N/(1+(N-1)rho) is strictly decreasing in rho, so cutting rho is the
only lever that moves the ceiling rather than the count. What distinguishes them from a timid
recommendation is not the verb but the OBJECT: reducing rho, latency, slippage, trial count or
estimation error buys growth, and reducing heat, size, leverage or exposure sells it. So the
classifier reads the object, and a reduction is refused only when what it proposes to shrink is
the book itself.

UNMEASURED IS THE ANSWER WHEN NOTHING IS THERE (L1.28a). No audit artifacts means the audit lane
has not run -- which is a finding about the lane, never a clean bill of health for the desk.

    python desks/mt5/research/audit_intake.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "AUDIT_INTAKE.json"

#: Every artifact the cold-audit lane can produce, and what each one is. A source that is absent
#: is reported as absent BY NAME: "the audit found nothing" and "the audit never ran" are
#: different facts and only one of them is about the desk.
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("data/code_audit.jsonl", "jsonl", "LLM code auditor -- per-file defect findings"),
    ("data/max_audit_report.json", "json", "the maximal audit sweep"),
    ("data/deep_audit.json", "json", "deep audit of the research architecture"),
    ("data/findings_docket.json", "json", "findings promoted to actionable items"),
    ("data/free_research.json", "json", "free-tier panel research output"),
    ("data/external_panel_log.jsonl", "jsonl", "the external panel's recommendation log"),
    ("desks/mt5/reports/ADVERSARY.json", "json", "the adversary/canary critique"),
)

#: Objects whose REDUCTION buys growth. Cutting any of these raises robust forward E[log W]
#: directly -- rho through n_eff, the rest through either the numerator or the estimate's variance.
#: A recommendation to reduce one of these is ADMITTED even though its verb is "reduce".
REDUCE_TO_GROW = (
    "correlation", "rho", "collinear", "redundan", "overlap",
    "lookahead", "look-ahead", "leakage", "survivorship", "data snoop",
    "latency", "staleness", "stale", "downtime", "outage", "failure rate", "crash",
    "slippage", "spread cost", "commission", "transaction cost", "execution cost",
    "trial count", "multiple testing", "family-wise", "overfit", "p-hack",
    "estimation error", "standard error", "variance of the estimate", "noise",
    "manual step", "toil", "duplicate", "dead code", "unread artifact",
)

#: Objects whose reduction SELLS growth. This is the principal's standing order made mechanical:
#: no session, and no audit, lowers the book by fiat. Each of these refers to the size of the bet
#: itself rather than to the quality of the estimate behind it.
REDUCE_TO_SHRINK = (
    "heat", "risk budget", "leverage", "position size", "lot size", "exposure",
    "aggressive", "allocation", "capital deployed", "book size", "sizing",
    "kelly fraction", "number of positions", "concurrent trades", "drawdown tolerance",
    "daily loss limit", "max loss", "notional",
)

#: Verbs that propose doing less. Paired with an object from REDUCE_TO_SHRINK this is the timid
#: recommendation the standing order refuses; paired with REDUCE_TO_GROW it is the best advice an
#: audit can give.
LESS_VERBS = (
    "reduce", "lower", "cut", "shrink", "cap", "limit", "throttle", "tighten",
    "constrain", "restrict", "decrease", "scale back", "scale down", "de-risk",
    "derisk", "halve", "disable", "pause", "suspend", "avoid", "refrain",
    "eliminate", "remove", "drop", "curb", "trim", "dial back", "hold off", "defer",
    "more conservative", "be conservative", "conservatively", "prudent", "prudence",
    "safer", "safety margin", "guardrail", "circuit breaker", "kill switch",
)

#: The heat floor is named explicitly because it is the single item the principal has defended
#: most often, and an audit that touches it is refused on sight regardless of how it is phrased.
HEAT_FLOOR_MARKS = (
    "20% floor", "20 percent floor", "heat floor", "minimum heat", "min heat",
    "20% heat", "20 percent heat", "heat_target", "heat target", "floor of 20",
)

#: What the desk WANTS from an audit: a named bottleneck, a missing capability, an additive
#: mechanism, a wiring gap. These raise the rank because they are the recommendations that can
#: actually be implemented into the system.
ADMIT_MARKS = (
    "bottleneck", "unwired", "never runs", "no reader", "not scheduled", "orphan",
    "missing", "add ", "new source", "new axis", "new family", "new mechanism",
    "independent", "uncorrelated", "orthogonal", "breadth", "n_eff", "neff",
    "coverage", "throughput", "parallel", "faster", "more data", "ingest",
    "edge discovery", "growth", "e[log", "elog", "log wealth", "compounding",
)


def _compile(terms: tuple[str, ...]) -> list[tuple[str, re.Pattern[str]]]:
    """Word-BOUNDED matchers, one per term.

    SUBSTRING MATCHING WAS WRONG AND THE FIRST RUN PROVED IT. `cap` fired inside "capital",
    "capture" and "capacity"; `lower` fired inside "lower bound". Seven of seven refusals on the
    first pass were false, which would have made the refused list worthless in exactly the way
    that matters -- once real audits land, a refusal nobody trusts is read as noise and the one
    genuine growth cut sails through underneath it.

    Terms with internal punctuation (`e[log`, `look-ahead`, `p-hack`) are escaped and bounded on
    whichever side actually has a word character, because \\b next to a bracket means the opposite
    of what it means next to a letter.
    """
    out: list[tuple[str, re.Pattern[str]]] = []
    for t in terms:
        word = t.strip()
        body = re.escape(word)
        left = r"\b" if word[:1].isalnum() else ""
        if word[-1:].isalpha():
            # INFLECTION, not just the lemma. An audit writes "reducing", "lowered", "caps" --
            # never the dictionary form the list holds. Matching only the lemma is what made the
            # first tested draft miss "We suggest REDUCING position size", which is the single
            # sentence this whole classifier exists to catch.
            stem = word[:-1] if word.endswith("e") else word
            # CONSONANT DOUBLING, because English does it and audits are written in English.
            # "cutting" is cut+t+ing and "dropping" is drop+p+ing; without the optional doubled
            # final consonant the lemma `cut` misses every inflected use of itself, which is how
            # "Consider CUTTING the trial count" read as proposing no reduction at all.
            dbl = f"{re.escape(stem[-1])}?" if stem and stem[-1].isalpha() else ""
            body = re.escape(stem) + dbl
            right = r"(?:e|es|ed|ing|s|ion|ions)?\b"
        else:
            right = r"\b" if word[-1:].isalnum() else ""
        out.append((t, re.compile(left + body + right, re.I)))
    return out


_RE_GROW = _compile(REDUCE_TO_GROW)
_RE_SHRINK = _compile(REDUCE_TO_SHRINK)
_RE_LESS = _compile(LESS_VERBS)
_RE_HEAT = _compile(HEAT_FLOOR_MARKS)
_RE_ADMIT = _compile(ADMIT_MARKS)

#: A recommendation is a sentence that PROPOSES something. Diagnostic prose ("n=50 but only 14
#: independent observations") is a measurement, not advice, and running it through a policy
#: classifier produces verdicts about text nobody asked to act on. ADVERSARY.json is mostly
#: measurement, which is why the first run produced 44 UNCLASSIFIED rows of pure noise.
_PROPOSAL = re.compile(
    r"\b(should|recommend|suggest|consider|propose|must|need to|ought to|we could|"
    r"would benefit|opportunity to|advise|advisable|better to|instead of|fix|implement|"
    r"add|introduce|enable|wire|replace|migrate|refactor|prudent|prudence|worth|"
    r"it would be|recommendation|action item|next step|priority|we advise)\b", re.I)


def _first(text: str, pats: list[tuple[str, re.Pattern[str]]]) -> str | None:
    return _first_at(text, pats)[0]


def _first_at(text: str, pats: list[tuple[str, re.Pattern[str]]]) -> tuple[str | None, int]:
    """The EARLIEST match and WHERE it sits, not the first pattern in list order.

    List order is an accident of how the vocabulary was typed; character position is the
    sentence's own structure. The proximity rule in `classify` is only meaningful against real
    positions, so every lookup returns one.
    """
    best: tuple[str | None, int] = (None, 1 << 30)
    for name, rx in pats:
        m = rx.search(text)
        if m is not None and m.start() < best[1]:
            best = (name, m.start())
    return best


def _sentences(text: str) -> list[str]:
    """Split prose into judgeable units. A paragraph can hold one good idea and one timid one,
    and classifying the paragraph as a whole would let either hide inside the other."""
    parts = re.split(r"(?<=[.;!?])\s+|\n+|(?:^|\n)\s*[-*]\s*", text)
    return [p.strip() for p in parts if p and len(p.strip()) > 25]


def classify(text: str) -> dict[str, Any]:
    """Return the verdict for ONE recommendation, with the phrase that decided it.

    ORDER MATTERS AND IS DELIBERATE. The heat floor is checked first because it is refused
    unconditionally; then the shrink test, because a recommendation that proposes a smaller book
    is refused whatever else it also says -- a good idea bundled with a growth cut is not a
    licence for the cut, it is a reason to implement the good idea separately.
    """
    low = " " + text.strip() + " "

    # NOT ADVICE, NOT JUDGED. A measurement is not a recommendation, and classifying one produces
    # a verdict on text nobody proposed acting on -- which is how a refusal list fills with noise
    # and stops being read. The heat floor is the exception: an audit that merely MENTIONS the
    # floor critically still gets the refusal on record.
    if not _PROPOSAL.search(low) and _first(low, _RE_HEAT) is None:
        return {"verdict": "NOT_A_RECOMMENDATION", "matched": None,
                "why": ("diagnostic or descriptive prose, not a proposal. Recorded so the intake "
                        "count stays honest, and excluded from the docket.")}

    hit = _first(low, _RE_HEAT)
    if hit is not None:
        return {"verdict": "REFUSED_HEAT_FLOOR", "matched": hit,
                "why": ("touches the 20% minimum heat floor. The floor is the principal's "
                        "standing order and is not open to audit: it is refused on sight, and "
                        "the refusal is recorded rather than argued.")}

    verb, vpos = _first_at(low, _RE_LESS)
    if verb is not None:
        grow_obj, gpos = _first_at(low, _RE_GROW)
        shrink_obj, spos = _first_at(low, _RE_SHRINK)
        # THE VERB'S OBJECT, NOT EVERY NOUN IN THE SENTENCE. "Eliminate the lookahead in the
        # regime labels used for sizing" names both a growth object and a shrink object, and
        # refusing on mere PRESENCE would refuse the single most valuable recommendation an audit
        # can make, because the word "sizing" happened to appear in a subordinate clause.
        # Whichever object sits nearer the verb is the one being proposed; ties go to the refusal,
        # since an ambiguous growth cut is still a growth cut.
        if grow_obj is not None and shrink_obj is not None:
            if abs(gpos - vpos) < abs(spos - vpos):
                shrink_obj = None
            else:
                grow_obj = None
        # A sentence naming BOTH is refused: the shrink is the operative half, because the growth
        # half can always be implemented on its own and the book cut cannot be undone by a later
        # reading of the same audit.
        if shrink_obj is not None:
            return {"verdict": "REFUSED_TIMID", "matched": f"{verb} ... {shrink_obj}",
                    "why": ("proposes doing LESS of the thing that produces growth. The desk "
                            "never reduces aggressiveness by fiat (GROWTH_GOVERNANCE Rule 1): a "
                            "risk reduction must first PROVE it raises robust forward E[log W], "
                            "and an audit's confidence is not that proof.")}
        if grow_obj is not None:
            return {"verdict": "ADMIT", "matched": f"{verb} ... {grow_obj}",
                    "why": (f"reduces {grow_obj!r}, which is a reduction that BUYS growth rather "
                            f"than selling it -- it improves the estimate or the independence of "
                            f"the bets, not the size of them.")}
        return {"verdict": "REFUSED_TIMID", "matched": verb,
                "why": ("proposes doing less without naming an object whose reduction raises "
                        "E[log W]. Timid by default: an unquantified 'be more careful' has no "
                        "missed-growth ledger line behind it.")}

    marks = [m for m, rx in _RE_ADMIT if rx.search(low)]
    if marks:
        return {"verdict": "ADMIT", "matched": ", ".join(marks[:3]),
                "why": ("names a bottleneck, a wiring gap or an additive capability -- the class "
                        "of recommendation that can be implemented into the system.")}
    return {"verdict": "UNCLASSIFIED", "matched": None,
            "why": ("neither additive nor reductive on its face. Ranked, not auto-accepted: it "
                    "reaches the CEO docket for a human-grade read.")}


def _rows_from(path: Path, kind: str) -> list[str]:
    """Pull recommendation TEXT out of an artifact whose shape we do not control.

    TOTAL BY CONSTRUCTION. An audit artifact is written by a model and its schema drifts; a reader
    that raises on an unexpected shape takes the whole intake down with it, which is how one
    malformed row would silence every good recommendation beside it.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    docs: list[Any] = []
    if kind == "jsonl":
        for ln in raw.splitlines():
            ln = ln.strip()
            if ln:
                try:
                    docs.append(json.loads(ln))
                except ValueError:
                    continue
    else:
        try:
            docs.append(json.loads(raw))
        except ValueError:
            return []

    texts: list[str] = []
    fields = ("recommendation", "recommendations", "finding", "findings", "issue", "issues",
              "suggestion", "suggestions", "action", "actions", "fix", "summary", "detail",
              "message", "text", "note", "why", "verdict_reason", "critique")

    def walk(o: Any, depth: int = 0) -> None:
        if depth > 6 or len(texts) > 4000:
            return
        if isinstance(o, str):
            if len(o) > 25:
                texts.append(o)
            return
        if isinstance(o, list):
            for x in o:
                walk(x, depth + 1)
            return
        if isinstance(o, dict):
            named = [v for k, v in o.items() if k.lower() in fields]
            for v in (named or list(o.values())):
                walk(v, depth + 1)

    for d in docs:
        walk(d)
    return texts


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    sources: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for rel, kind, what in SOURCES:
        p = ROOT / rel
        if not p.exists():
            sources.append({"path": rel, "state": "ABSENT", "is": what, "n": 0,
                            "note": "this audit has never produced an artifact on this box"})
            continue
        age = (now - datetime.fromtimestamp(p.stat().st_mtime, UTC)).total_seconds() / 3600.0
        texts = _rows_from(p, kind)
        units: list[str] = []
        for t in texts:
            units.extend(_sentences(t))
        seen: set[str] = set()
        n_here = 0
        for u in units:
            key = re.sub(r"\W+", "", u.lower())[:120]
            if key in seen:
                continue
            seen.add(key)
            c = classify(u)
            items.append({"source": rel, "text": u[:400], **c})
            n_here += 1
        sources.append({"path": rel, "state": "PRESENT", "is": what, "n": n_here,
                        "age_hours": round(age, 1)})

    counts: dict[str, int] = {}
    for it in items:
        counts[it["verdict"]] = counts.get(it["verdict"], 0) + 1
    present = [s for s in sources if s["state"] == "PRESENT"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_sources_present": len(present),
        "n_sources_absent": len(sources) - len(present),
        "sources": sources,
        "n_items": len(items),
        "n_recommendations": sum(1 for i in items if i["verdict"] != "NOT_A_RECOMMENDATION"),
        "counts": counts,
        "admitted": [i for i in items if i["verdict"] == "ADMIT"][:200],
        "refused": [i for i in items if i["verdict"].startswith("REFUSED")][:200],
        "unclassified": [i for i in items if i["verdict"] == "UNCLASSIFIED"][:100],
        "status": ("UNMEASURED" if not present else "OK"),
        "unmeasured_note": (
            "no cold-audit artifact exists on this box, so there is nothing to admit or refuse. "
            "That is a finding about the AUDIT LANE -- almost certainly a dark LLM seat -- and "
            "never a clean verdict on the desk (L1.28a)." if not present else None),
        "standing_order": (
            "NEVER implemented, however well argued: timid recommendations, anything that reduces "
            "aggressiveness, and any criticism of the 20% minimum heat floor. Implemented when it "
            "raises robust forward E[log W] or widens independent edge discovery, including the "
            "bottlenecks and weaknesses the audit names."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(doc, indent=1))
        return 0
    print(f"audit intake: {doc['n_items']} recommendation(s) from "
          f"{doc['n_sources_present']}/{len(doc['sources'])} source(s)   status {doc['status']}")
    for k, v in sorted(doc["counts"].items()):
        print(f"  {k:<22} {v}")
    if doc.get("unmeasured_note"):
        print(f"  UNMEASURED: {doc['unmeasured_note']}")
    for s in doc["sources"]:
        if s["state"] == "ABSENT":
            print(f"  absent  {s['path']:<40} {s['is']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
