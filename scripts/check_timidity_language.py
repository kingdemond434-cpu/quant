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
    # prudence is priced as a COST here, not prescribed (R0438 false positive, widened per L1.41)
    "L1.57": "has not been prudent; it has declined to participate",
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
#: Where brain_env builds the payload it injects. Parsed rather than restated so this fence and
#: the injector can never disagree about what an organ actually receives.
_BRAIN_ENV = _ROOT / "ops/brain_env.sh"


def _injected_doctrine_files() -> list[Path]:
    """Every file `brain_env.sh` concatenates into the injected doctrine.

    THE CONSOLIDATION OF 2026-08-25 SPLIT THE DOCTRINE IN TWO and this fence did not follow it.
    `brain_env.sh` injects `ops/principal_doctrine.txt` AND `docs/LAWS.md` together; the sealed
    core states the principle in prose ("TIMIDITY IS SCORED ON EVERY AXIS") while the token
    `L1.28` lives in LAWS.md, six times. Reading only the first file, this fence reported
    "the law is not reaching any organ" every run while the law was demonstrably reaching every
    organ -- a fence that is WRONG is worse than no fence, because it teaches the reader to skip
    the line where a real one would appear (L1.43).
    """
    files: list[Path] = []
    try:
        for line in _BRAIN_ENV.read_text("utf-8").splitlines():
            if "_DOCTRINE=" in line and "cat " in line:
                for tok in re.findall(r'\$_BRAIN_ROOT/([\w./-]+)', line):
                    cand = _ROOT / tok
                    if cand.exists():
                        files.append(cand)
                break
    except OSError:
        pass
    if not files:
        # UNPARSEABLE is not a pass: fall back to the known pair and say so in the artifact.
        files = [f for f in (_DOCTRINE, _ROOT / "docs/LAWS.md") if f.exists()]
    return files


def _injected_doctrine_text() -> str:
    return "\n".join(f.read_text("utf-8", errors="replace") for f in _injected_doctrine_files())

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


# ---------------------------------------------------------------------------------------------
# PROMPT-SURFACE SWEEP (L1.28 hardening, principal order 2026-07-31: "strict military maximum").
# THE GAP THIS CLOSES: this fence guarded the constitution and the doctrine and NOTHING ELSE --
# yet an organ's behaviour is set by its PROMPT, so a timid line in a miner brief throttled that
# seat every single run while the fence reported green. Every prompt surface is now in scope.
# ---------------------------------------------------------------------------------------------

#: Every file that instructs an organ. Missing one means an unguarded surface.
def _prompt_surfaces() -> list[Path]:
    out = sorted(_ROOT.glob("ops/*prompt*.txt")) + sorted(_ROOT.glob("prompts/*.txt"))
    # organ scripts carrying inline briefs (the hunt/sweep/hunter genomes)
    for rel in ("scripts/kimi_hunter.py", "scripts/run_capability_hunt.py",
                "scripts/run_deep_sweep.py", "libs/research/strategic_director.py",
                "libs/research/second_family.py"):
        p = _ROOT / rel
        if p.exists():
            out.append(p)
    # A DOC A PROMPT ORDERS THE ORGAN TO READ *IS* A PROMPT SURFACE. The sweep above covers the
    # files the desk hands an organ directly and stopped there, but every dig prompt opens by
    # delegating: blindrediscovery_dig_prompt.txt:1 says "Read the Blind-Rediscovery companion
    # section of docs/research/PROSPECTOR_SPEC.md and docs/DIGGING_CHARTER.md". Instructions
    # reached by one hop of indirection bind the organ exactly as hard as inline ones and were
    # invisible here -- the same transitive-reachability blindness check_orphan_code was fixed
    # for. Measured on the day this was added: PROSPECTOR_SPEC.md:124 carried "invent up to 5
    # mechanisms", a QUOTA-CAP that survived the principal's 2026-07-19 exhaustion order because
    # that order was applied to the prompt and never followed through the delegation.
    #
    # NAMED EXPLICITLY, NOT GLOBBED, and the distinction is what keeps this fence trusted: the
    # first draft derived this list by regexing prompt text for *SPEC*/*CHARTER* paths, which
    # also swept docs/research/prospector_coverage.md and fired QUOTA-CAP on "up to 26 years" --
    # a DATA SPAN in a coverage RECORD, not a bound on effort. Records describe what was found;
    # only charters and specs instruct. A gate that cries wolf gets switched off, and a switched-
    # off gate enforces nothing (L1.43), so records stay out until one is shown to instruct.
    for rel in ("docs/DIGGING_CHARTER.md", "docs/research/PROSPECTOR_SPEC.md",
                "docs/research/LITERATURE_SPEC.md",
                "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md"):
        p = _ROOT / rel
        if p.exists():
            out.append(p)
    return out


#: NUMERIC QUOTA CAPS -- the sneakiest timidity, because a cap reads as helpful specificity.
#: "top 3" in a hunter brief silently converts an unbounded mandate into a 3-item chore.
_QUOTA_PATTERNS = (
    r"\btop\s+(?:3|5|10|three|five|ten)\b",
    r"\b(?:at most|no more than|limit yourself to|maximum of|up to)\s+\d+\b",
    r"\b(?:a few|a handful of|two or three|one or two)\s+(?:findings|items|ideas|sources)\b",
    r"\bpick\s+(?:the\s+)?(?:best|top)\s+\d+\b",
)

#: HEDGED ORDERS -- an instruction that permits the organ to decline is not an instruction.
_HEDGED_ORDERS = (
    "if appropriate", "if time permits", "if you have time", "you may want to",
    "consider whether you should", "feel free to skip", "optionally", "if convenient",
    "where practical", "if it seems worthwhile", "at your discretion",
)


def audit_prompts() -> list[dict[str, Any]]:
    """Timid language in the files that actually drive organ behaviour.

    EXEMPTIONS are deliberate and narrow: a line that also names the law forbidding the pattern
    is quoting it in order to ban it (this file's own laws do exactly that), and a line bounding
    BREADTH-PER-RUN is a completion bound, not a scope bound -- L1.35 requires runs to finish, so
    'bounded per run' must stay legal while 'bounded per seat' must not."""
    hits: list[dict[str, Any]] = []
    for path in _prompt_surfaces():
        try:
            lines = path.read_text("utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            low = line.lower()
            # NARROW exemptions only. An earlier draft exempted any line containing "never",
            # which is most lines in an aggressive prompt -- the fence reported a clean sweep
            # because it was skipping almost everything. Exempt ONLY lines that explicitly
            # forbid the pattern or bound breadth PER RUN (a completion bound, legal under
            # L1.35) -- never a line that merely sounds assertive.
            if any(m in low for m in ("l1.21a", "l1.28", "l1.35", "timid", "misreading",
                                      "breadth-per-run", "breadth per run", "is a defect",
                                      "never cap", "no quota", "is forbidden")):
                continue
            for pat in _QUOTA_PATTERNS:
                if re.search(pat, low):
                    hits.append({"file": str(path.relative_to(_ROOT)), "line": i,
                                 "kind": "QUOTA-CAP", "text": line.strip()[:150],
                                 "why": "a numeric cap silently converts an unbounded mandate "
                                        "into a chore -- state the bound as breadth-PER-RUN or "
                                        "remove it (L1.35)"})
                    break
            for phrase in _HEDGED_ORDERS:
                if phrase in low:
                    hits.append({"file": str(path.relative_to(_ROOT)), "line": i,
                                 "kind": "HEDGED-ORDER", "phrase": phrase,
                                 "text": line.strip()[:150],
                                 "why": "an instruction the organ may decline is not an "
                                        "instruction -- make it an order or delete it"})
                    break
    return hits


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
    prompt_hits = audit_prompts()
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28 -- timidity is a scored defect. Every scope restraint states its non-timid "
               "reading; every evidence/risk restraint is declared as such and stays strict.",
        "counts": counts,
        "unclassified": [r["principle"] for r in rows if r["status"] == "UNCLASSIFIED"],
        "doctrine_injected": "l1.28" in _injected_doctrine_text().lower(),
        "doctrine_files_injected": [str(f.relative_to(_ROOT))
                                    for f in _injected_doctrine_files()],
        "doctrine_timid_instructions": doctrine["hits"],
        "prompt_surfaces_scanned": len(_prompt_surfaces()),
        "prompt_timid_hits": prompt_hits,
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
        for h in rep["prompt_timid_hits"]:
            print(f"  {h['kind']:<12} {h['file']}:{h['line']} -- {h['why']}\n"
                  f"               {h['text']}")
        if not rep["doctrine_injected"]:
            print("  NOT-INJECTED L1.28 is absent from the payload brain_env injects "
                  f"({', '.join(rep['doctrine_files_injected']) or 'NO FILES RESOLVED'}) -- "
                  "the law is not reaching any organ (L2.1)")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    # THE TWO DENOMINATORS THIS VERDICT RESTS ON, NEITHER OF WHICH WAS CONSULTED (L1.57).
    # `prompt_surfaces_scanned` was computed, published into the artifact, and then left out of
    # the failure expression entirely: an empty glob yields zero hits, and zero hits read as full
    # compliance. That matters here more than almost anywhere, because L1.36's aggression-family
    # hardening rests on this sweep reaching ALL 18 prompt surfaces -- organ behaviour is set by
    # prompts, so a silent zero-surface sweep certifies the one layer that decides how hard every
    # organ pushes. `counts` is the same story for the constitution's own clauses.
    n_surfaces = rep["prompt_surfaces_scanned"]
    n_clauses = sum(rep["counts"].values()) if isinstance(rep["counts"], dict) else 0
    blind = []
    if not n_surfaces:
        blind.append("ZERO prompt surfaces matched -- the L1.36 prompt sweep scanned nothing")
    if not n_clauses:
        blind.append("ZERO constitution clauses classified -- the L1.28 sweep scanned nothing")
    for b in blind:
        print(f"  UNMEASURED  {b}")
    failed = (rep["unclassified"] or rep["doctrine_timid_instructions"]
              or rep["prompt_timid_hits"] or not rep["doctrine_injected"] or blind)
    return 0 if (args.report_only or not failed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
