#!/usr/bin/env python3
"""SIZING DERIVATION (R0135) -- no number that moves money may be chosen by feel.

WHY THIS FENCE EXISTS, stated as the pattern that produced it rather than as a principle someone
liked. Four constants in the money path were found defective in a single session, ALL of the same
shape -- a round number picked by analogy or by taste, never computed:

  MAX_LEVERAGE = 10        picked as "aggressive but not crazy". It was ANTI-aggression: it made a
                           0.9pct structural stop deploy 9pct of a 20pct risk budget while a lazy
                           2pct stop deployed the full 20pct, penalising the exact behaviour the
                           calculated stop exists to produce.
  MIN_STOP_PCT = 0.5       one number for gold and for SOL. Measured, the median adverse excursion
                           over a 24h hold is 0.64pct on PAXG and 1.28pct on SOL -- the flat floor
                           was ~2.5x too loose on one and about right on the other.
  trail = 1R               a trailed stop one R behind price sits AT the noise floor, because the
                           entry stop is permitted to sit at the noise floor. It failed the same
                           test the entry stop has to pass.
  MAX_RISK_PER_TRADE=0.20  chosen by analogy to the leverage in a screenshot. Simulated, it meets a
                           -90pct drawdown with ~certainty EVEN WHEN THE STRATEGY IS PROFITABLE,
                           and past full Kelly more size makes growth NEGATIVE.

Every one was caught by hand, late, and only because someone happened to look. Four of four is not
bad luck, it is a missing mechanism -- and this desk's own standard is that a defect caught by hand
is not caught (L1.41). A money-path constant is exactly where a comfortable-looking number does the
most damage, because it never errors; it just quietly sets the growth rate.

THE RULE: every module-level numeric constant in a sizing/risk module must either be DERIVED at
runtime (computed from a measurement) or carry, in the comment attached to it, the derivation that
set it -- a simulation, a measurement, a cited law, or an explicit "this is a hard external limit".
"I picked it" is not a derivation. The fence reads the comments because that is where the
justification has to live for the next reader anyway.

DELIBERATELY NOT AUTOMATED FURTHER: this cannot check that the cited derivation is CORRECT, only
that one exists and is specific. That is still most of the value -- three of the four defects above
would have been caught at the moment of writing, because none of them had anything to cite.

    python scripts/check_sizing_derivation.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Modules whose module-level numbers decide position size, leverage or risk. Kept to the money
#: path on purpose -- a fence that flags every constant in the repo is a fence nobody reads.
#: EMPTY SINCE 2026-09-05 (universe mandate), and that is a MEASURED state, not a disabled fence.
#: All three modules -- run_conviction_trader, run_llm_trader, resolve_paper_book -- were deleted
#: with the retired book, so this repo currently holds no scripts/-level module whose top-level
#: constants set position size. `build()` must therefore report its empty-scope verdict rather
#: than "OK", because a sizing fence that grades zero modules and prints OK is indistinguishable
#: from one that found nothing wrong. The MT5 sizing constants live under desks/mt5/ and are
#: fenced there; pointing this scope at them is a wiring decision, not a cleanup's to make.
_SIZING_MODULES: tuple[str, ...] = ()

#: Words that mark a real derivation. A comment must contain at least one AND a digit, so
#: "measured" alone does not pass -- the number itself has to appear in the justification.
#: EXTERNAL FACTS are a legitimate derivation category and were missing on the first run: a
#: published venue fee schedule is not a number anyone chose, and rewording the comment to hit the
#: vocabulary would be gaming the fence. Widen the list on a false positive; never reword an organ
#: to satisfy a check -- the same rule the build standard learned.
_DERIVATION_WORDS = (
    "simulat", "measur", "derived", "computed", "observed", "median", "backtest", "kelly",
    "exchange limit", "venue limit", "hard limit", "protocol", "law l1", "law l2", "l1.", "l2.",
    "empirical", "calibrat", "estimated from", "fitted", "per the", "found by",
    "published", "fee schedule", "venue schedule", "quoted", "top-of-book", "spread on",
    "exchange minimum", "venue minimum", "minimum notional", "rejects orders", "tier",
    "documented",
    # STATISTICAL derivations -- the third false-positive class this fence produced. A threshold
    # placed a standard error below a breakeven IS derived; the vocabulary simply lacked the words.
    "standard error", "binomial", "sigma", "power", "breakeven", "posterior", "variance",
    # SCHEDULE derivations -- the fourth false-positive class (2026-08-05). A staleness threshold
    # set from a producer's known firing rate is derived from a fact you can look up in the
    # manifest, exactly as a fee schedule is: CHART_STALE_H=2.0 because the builder's cron cadence
    # is 20 minutes, so 2h is five consecutive missed builds -- the organ has STOPPED, not
    # hiccuped. Widening is the sanctioned response here (this list's own rule, three classes
    # above); rewording run_conviction_trader to hit the vocabulary would be gaming the fence.
    "cadence", "cron", "consecutive", "schedule",
    # PAIRED-DESIGN / SIGNIFICANCE-LEVEL derivations -- the fifth false-positive class
    # (2026-08-29). `resolve_paper_book.py` derives TRAIL_FWD_T=1.7 as the one-sided ~0.05
    # critical value, TRAIL_FWD_DECIDE_N=25 as the earliest read of a PAIRED design, and
    # TRAIL_FWD_HARD_N=50 by alignment with the sleeve's own KILL_AFTER_N -- all three stated
    # plainly in one preregistration block, none of them reachable by the vocabulary above.
    # Widening is this list's own sanctioned response ("Widen the list on a false positive;
    # never reword an organ to satisfy a check"), and the alternative was worse than cosmetic:
    # four false breaches held `run_law_gate --laws-only` RED, and a gate red on correct code
    # is how a gate red on a real breach stops being read.
    # `alpha` is deliberately ABSENT: this desk uses it to mean edge on nearly every line, so it
    # would match everything and the fence would stop asking anything.
    "one-sided", "two-sided", "paired", "|t|", "t-stat", "p-value", "significance",
    "critical value", "aligned with",
)

#: Constants that are pure plumbing, not sizing. Naming them is a DECISION, same as the schedule
#: exemptions in the build standard -- "it's obviously fine" has to be written down to count.
_EXEMPT: dict[str, str] = {
    "MAX_PAGES": "http paging bound, touches no size",
    "BAR": "bar interval string, not a number",
    "PIVOT_K": "chart-reading parameter, not a sizing input",
    "MAX_LEVELS": "display/brief truncation, not a sizing input",
    "LEVEL_TOL_PCT": "chart-reading parameter, not a sizing input",
    "NOISE_LOOKBACK_HOURS": "measurement window length; the MEASUREMENT is the derived thing",
    "TRADEABLE_MAX_AGE_MIN": "staleness gate on news, not a sizing input",
    "MIN_PROB": "domain bound on a probability (below 0.5 is the other side of the trade)",
    "MAX_PROB": "domain bound on a probability (over-confidence tell, see L1.29)",
    "STOP_MISMATCH_TOL": "consistency tolerance between two stated numbers, not a size",
    "MAX_CHARS": "prompt truncation, not a sizing input",
    "_BAR_MS": "milliseconds in the bar interval -- a unit conversion, not a decision",
    "_INTERVALS": "venue interval-name mapping table, no sizing content",
    "_TFS": "which timeframes to chart, not a sizing input",
}


#: A module-level CONSTANT assignment, e.g. `TRAIL_FWD_T = 1.7` or `MAX: int = 5`. Used only to
#: decide whether a line above a constant is a SIBLING in the same declaration group -- so it is
#: deliberately strict: no indentation (module level), an ALL-CAPS name, one `=`.
_RE_CONST_ASSIGN = re.compile(r"^[A-Z][A-Z0-9_]*\s*(?::[^=]+)?=")


def _comment_block(lines: list[str], lineno: int) -> str:
    """The comment attached to a constant: the `#:` block above it plus any trailing comment.

    `#:` above and `#` trailing are both idiomatic here, and the justification legitimately lives
    in either -- so both are read rather than mandating a style nobody would follow."""
    out = []
    i = lineno - 2                                   # line above the assignment (0-indexed)
    # A `#:` BLOCK DOCUMENTS ITS WHOLE GROUP (gap-fixer 2026-08-29). This walk used to stop at
    # the first non-comment line, so a block covering several related constants was credited to
    # exactly one of them -- whichever happened to sit directly beneath it -- and its siblings
    # were reported as undocumented. MEASURED: `scripts/resolve_paper_book.py` carries one
    # preregistration block explaining TRAIL_FWD_DECIDE_N=25, TRAIL_FWD_HARD_N=50 and
    # TRAIL_FWD_T=1.7 together ("25 paired differences at |t|>=1.7 (one-sided ~0.05) is the
    # earliest read; 50 is the hard stop"), and this fence reported three of them plus
    # TRAIL_FWD_CHALLENGER as `no derivation cited`. Those four false breaches held
    # `run_law_gate --laws-only` RED, and a gate that is red on correct code is how a gate that
    # is red on a REAL breach stops being read (L1.43, gate-optimality).
    #
    # The rule is deliberately narrow: skip only CONTIGUOUS sibling constant assignments, never
    # a blank line and never any other statement. A group is a block of adjacent constants under
    # one comment; the moment anything separates them they are no longer one declaration and the
    # comment no longer speaks for them. Both directions are pinned by test.
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            out.append(lines[i])
            i -= 1
            continue
        if out:
            break                                    # the block ended; do not reach past it
        if _RE_CONST_ASSIGN.match(lines[i]):
            i -= 1                                   # a sibling in the same group -- keep walking
            continue
        break
    if lineno - 1 < len(lines) and "#" in lines[lineno - 1]:
        out.append(lines[lineno - 1].split("#", 1)[1])
    return " ".join(out).lower()


def audit_module(root: Path, rel: str) -> dict[str, Any]:
    p = root / rel
    try:
        src = p.read_text("utf-8")
    except OSError as exc:
        return {"module": rel, "state": "UNREADABLE", "why": str(exc), "undocumented": []}
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"module": rel, "state": "UNPARSEABLE", "why": str(exc), "undocumented": []}

    checked, bad = [], []
    for node in tree.body:                            # module level only
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if not isinstance(t, ast.Name) or not t.id.isupper():
                continue
            val = node.value
            nums = [n for n in ast.walk(val) if isinstance(n, ast.Constant)
                    and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)] if val else []
            if not nums:
                continue
            if t.id in _EXEMPT:
                checked.append({"name": t.id, "state": "EXEMPT", "why": _EXEMPT[t.id]})
                continue
            blob = _comment_block(lines, node.lineno)
            has_word = any(w in blob for w in _DERIVATION_WORDS)
            has_digit = any(c.isdigit() for c in blob)
            if has_word and has_digit:
                checked.append({"name": t.id, "state": "DERIVED"})
            else:
                bad.append({"name": t.id, "line": node.lineno,
                            "why": ("no derivation cited" if not has_word else
                                    "derivation words present but no numbers -- cite the "
                                    "measurement or simulation that produced this value")})
                checked.append({"name": t.id, "state": "UNJUSTIFIED", "line": node.lineno})
    return {"module": rel, "state": "OK" if not bad else "UNJUSTIFIED-CONSTANTS",
            "n_constants": len(checked), "n_bad": len(bad),
            "undocumented": bad, "constants": checked}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    mods = [audit_module(root, m) for m in _SIZING_MODULES]
    bad = [m for m in mods if m["state"] != "OK"]
    n_bad = sum(m.get("n_bad", 0) for m in mods)
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.41/L2.4 -- a number that moves money is a decision, and an undocumented "
               "decision cannot be reviewed, disputed or improved. Four money-path constants were "
               "found defective in one session, all of them round numbers picked by analogy.",
        # AN EMPTY SCOPE IS "UNMEASURED", NEVER "OK" (L1.28a). `_SIZING_MODULES` emptied on
        # 2026-09-05 when the retired book's three sizing modules were deleted, and a fence that
        # grades zero modules and prints OK is indistinguishable from one that looked and found
        # nothing wrong -- the exact conflation this desk fences everywhere else. Reported as its
        # own state so the day someone re-points this scope, the gap is visible in the artifact.
        "status": ("UNMEASURED" if not mods
                   else "OK" if not bad else "UNJUSTIFIED-CONSTANTS"),
        "n_modules": len(mods), "n_unjustified": n_bad,
        "detail": ("no module is in scope -- the money path this fence was built for was deleted "
                   "with the retired universe (2026-09-05) and no replacement scope has been "
                   "wired, so NOTHING was graded. This is a wiring gap, not a clean bill of health"
                   if not mods else
                   f"{sum(m.get('n_constants', 0) for m in mods)} money-path constants across "
                   f"{len(mods)} modules, {n_bad} without a cited derivation"
                   + ("" if not n_bad else ": " + ", ".join(
                       f"{m['module'].split('/')[-1]}:{b['name']}"
                       for m in mods for b in m["undocumented"]))),
        "modules": mods,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/sizing_derivation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"sizing derivation (L1.41): {rep['status']} -- {rep['detail']}")
        for m in rep["modules"]:
            for b in m.get("undocumented", []):
                print(f"  {m['module']}:{b['line']} {b['name']}: {b['why']}")
    return 0 if args.report_only or rep["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
