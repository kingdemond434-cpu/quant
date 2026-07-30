"""TIMIDITY FENCE (L1.28) -- every restraint in the constitution declares which KIND it is.

THE DEFECT THIS EXISTS FOR. Roughly two thirds of this constitution's principles contain restraint
language -- minimise, reject, only, never, discipline, bounded, narrow, scarce. Each is correct in
its own context, and each is misreadable by a language model as a general licence to do less. The
misreading is systematic rather than occasional: it yields smaller changes, deferred subsystems,
proposals instead of builds, "conservative versions". It is silent, and it looks like good
judgement, which is why it needs a fence rather than an intention.

WHAT IT CHECKS, and the design choice that keeps it from becoming noise. A naive keyword scan flags
32 of 44 principles -- including the aggressive ones, where "never" means "never rank a small edge
down". A fence that fires on healthy text gets acknowledged into silence, which is the failure mode
`check_orphan_code` already taught this desk. So the rule is CLASSIFICATION, not absence:

  every principle containing scope-restraint language must be EITHER
    (a) named in L1.28's disambiguation table, which states its correct non-timid reading, OR
    (b) declared EVIDENCE/RISK restraint -- a bar on what may be believed or what capital may be
        exposed to, which L1.21a/L1.28 explicitly do NOT loosen, OR
    (c) carrying its own anti-timidity sentence inline.

An unclassified restraint is the defect, because in practice it defaults to the timid reading.

DIRECTION OF FAILURE, chosen deliberately: a NEW principle is guilty until classified. Adding one
row to the L1.28 table is a minute of work; a principle that quietly teaches every organ to do less
costs forward compounding that is never recovered and never itemised.

    python scripts/check_timidity_language.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_OUT = _ROOT / "data/timidity_audit.json"

# Words that, read out of context by a model, license doing less. Deliberately broad: the fence
# does not decide whether restraint is PRESENT, it decides whether it has been CLASSIFIED.
_SCOPE_RESTRAINT = (
    "minimise", "minimize", "ruthless", "reject", "avoid", "restrict", "conservat", "cautio",
    "discipline", "narrow", "bounded", "defer", "wait", "restraint", "prudent", "scarce",
    "sparingly", "limit", "smallest", "fewer", "less ", "slow",
)

# Principles that are EVIDENCE/RISK restraint: bars on belief and on capital exposure. These are
# absolute, are NOT loosened by L1.21a/L1.28, and need no anti-timidity rider -- rigour here is
# what makes aggression elsewhere survivable. Each is listed with why it qualifies.
_EVIDENCE_RESTRAINT: dict[str, str] = {
    "L1.6": "statistical validation -- the confirmation bar and the two-stage law",
    "L1.7": "adversarial validation -- every success triggers disproof attempts",
    "L1.23": "the survival rails -- ruin probability and Tier-3 isolation",
    "L1.3": "no proxy becomes a god -- a bar on what a number is allowed to mean",
    "L1.4": "reality anchoring -- forward evidence outranks historical",
    "L2.8a": "the immutable core, including the rule that it is immutable",
    "L2.0": "the ratchet fence -- floors only rise",
    "L2.2": "mechanical fences -- the enforcement layer itself",
    "L2.4": "artifact over claim -- a bar on claiming a capability exists",
    "L2.10": "reality gap detection -- measures the backtest-to-live chain",
}

# Clauses where a restraint WORD appears inside an explicitly AGGRESSIVE instruction. These are
# the fence's false positives, and each is retired by QUOTING the phrase that proves it -- a
# blanket exemption list would be indistinguishable from muting the check, which is how a fence
# dies. If any quoted phrase ever stops matching, the clause was rewritten and re-classifies.
_AGGRESSIVE_CONTEXT: dict[str, str] = {
    "L1.1": "disciplined deployment",                    # inside "as fast as evidence permits"
    "L1.11a": "search universe is never restricted",
    "L1.12": "ruthlessly deleted or replaced",           # ruthless toward dead weight, not scope
    "L1.17": "rejected hypothesis and invalidated assumption is preserved",
    "L1.18": "every fillable edge scores the same regardless of size",
    "L1.18a": "never defers hunting a mechanism because its capacity looks modest",
    "L1.22": "needs the human for direction less and less",
    "L1.27": "am I protecting capital, or avoiding uncertainty?",   # the anti-paralysis law itself
    "L2.3": "must reach implemented (with commit) / rejected (with substantive reason)",
}

# Sentences that count as an inline anti-timidity declaration.
_INLINE_MARKERS = (
    "timid", "not a licence", "not a license", "never a reason to build less",
    "default is build", "l1.21a", "l1.28", "anti-timidity", "scope restraint",
)


def _clauses() -> dict[str, str]:
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    ms = list(re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s", text, re.MULTILINE))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.start():end]
    return out


def _table_rows(clauses: dict[str, str]) -> set[str]:
    """Principle ids named in L1.28's disambiguation table."""
    body = clauses.get("L1.28", "")
    return set(re.findall(r"\*\*(L\d+\.\d+[a-z]?)\*\*", body))


# --------------------------------------------------------------------------------------------
# SECOND SURFACE: the DOCTRINE, which matters more than the constitution for organ behaviour --
# it is the text actually injected into every model call. A timid INSTRUCTION here is not a
# misreadable law, it is a direct order to do less, so these are matched as literal phrases and
# any hit is a defect regardless of surrounding context.
_DOCTRINE = _ROOT / "ops/principal_doctrine.txt"

_TIMID_INSTRUCTIONS = (
    "prefer the smaller change", "propose rather than build", "propose instead of building",
    "when in doubt, do not", "when in doubt, don't", "err on the side of caution",
    "keep it minimal", "smallest possible change", "avoid adding", "avoid building",
    "hold off", "only if strictly necessary", "unless strictly necessary",
    "ship the conservative version", "leave it alone for now", "do not add new",
)


def audit_doctrine() -> dict[str, Any]:
    """Timid ORDERS in the injected doctrine. Quoted-misreading text is exempt by construction:
    L1.21a and L1.28 both quote these phrases in order to forbid them, so a hit only counts when
    it is NOT inside a line that also names the law forbidding it."""
    if not _DOCTRINE.exists():
        return {"present": False, "hits": []}
    hits = []
    for i, line in enumerate(_DOCTRINE.read_text("utf-8").splitlines(), 1):
        low = line.lower()
        forbidding = any(m in low for m in ("l1.21a", "l1.28", "timid", "misreading"))
        for phrase in _TIMID_INSTRUCTIONS:
            if phrase in low and not forbidding:
                hits.append({"line": i, "phrase": phrase, "text": line.strip()[:160]})
    return {"present": True, "hits": hits}


def audit() -> dict[str, Any]:
    clauses = _clauses()
    classified_by_table = _table_rows(clauses)
    rows: list[dict[str, Any]] = []
    for pid, body in sorted(clauses.items()):
        low = body.lower()
        hits = sorted({w.strip() for w in _SCOPE_RESTRAINT if w in low})
        if not hits:
            rows.append({"principle": pid, "restraint_words": [], "status": "NO-RESTRAINT",
                         "via": ""})
            continue
        if pid in _EVIDENCE_RESTRAINT:
            status, via = "EVIDENCE-RESTRAINT", _EVIDENCE_RESTRAINT[pid]
        elif pid in _AGGRESSIVE_CONTEXT:
            quote = _AGGRESSIVE_CONTEXT[pid]
            if " ".join(quote.lower().split()) in " ".join(low.split()):
                status, via = "AGGRESSIVE-CONTEXT", f'restraint word inside: "{quote}"'
            else:
                # The proof phrase no longer exists -- the clause was rewritten and the exemption
                # is now unverified. Falling back to UNCLASSIFIED is the safe direction.
                status, via = "UNCLASSIFIED", (
                    f'declared AGGRESSIVE-CONTEXT but the proving phrase "{quote}" is GONE -- '
                    "the clause was rewritten; re-read it and re-classify")
        elif pid in classified_by_table:
            status, via = "CLASSIFIED", "named in the L1.28 disambiguation table"
        elif any(m in low for m in _INLINE_MARKERS):
            status, via = "CLASSIFIED", "carries an inline anti-timidity declaration"
        else:
            status, via = "UNCLASSIFIED", ("scope-restraint language with no stated non-timid "
                                           "reading -- defaults to the timid reading in practice")
        rows.append({"principle": pid, "restraint_words": hits, "status": status, "via": via})

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    doctrine = audit_doctrine()
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28 -- timidity is a scored defect. Every scope restraint states its non-timid "
               "reading; every evidence/risk restraint is declared as such and stays strict.",
        "counts": counts,
        "unclassified": [r["principle"] for r in rows if r["status"] == "UNCLASSIFIED"],
        "doctrine_injected": "l1.28" in (_DOCTRINE.read_text("utf-8").lower()
                                         if _DOCTRINE.exists() else ""),
        "doctrine_timid_instructions": doctrine["hits"],
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    rep = audit()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"timidity audit (L1.28): {rep['counts']} | doctrine L1.28 injected: "
              f"{rep['doctrine_injected']}")
        for pid in rep["unclassified"]:
            words = next(r["restraint_words"] for r in rep["rows"] if r["principle"] == pid)
            print(f"  UNCLASSIFIED {pid} -- restraint words {words}: add a row to the L1.28 table, "
                  f"declare it EVIDENCE-RESTRAINT, or state its non-timid reading inline")
        for h in rep["doctrine_timid_instructions"]:
            print(f"  TIMID-ORDER  principal_doctrine.txt:{h['line']} \"{h['phrase']}\" -- this is "
                  f"an instruction to every organ to do less: {h['text']}")
        if not rep["doctrine_injected"]:
            print("  NOT-INJECTED L1.28 is absent from ops/principal_doctrine.txt -- the law is "
                  "not reaching any organ (L2.1)")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    failed = (rep["unclassified"] or rep["doctrine_timid_instructions"]
              or not rep["doctrine_injected"])
    return 0 if (args.report_only or not failed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
