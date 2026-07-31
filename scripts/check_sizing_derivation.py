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
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Modules whose module-level numbers decide position size, leverage or risk. Kept to the money
#: path on purpose -- a fence that flags every constant in the repo is a fence nobody reads.
_SIZING_MODULES: tuple[str, ...] = (
    "scripts/run_conviction_trader.py",
    "scripts/run_llm_trader.py",
    "scripts/resolve_paper_book.py",
)

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
    "exchange minimum", "tier", "documented",
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


def _comment_block(lines: list[str], lineno: int) -> str:
    """The comment attached to a constant: the `#:` block above it plus any trailing comment.

    `#:` above and `#` trailing are both idiomatic here, and the justification legitimately lives
    in either -- so both are read rather than mandating a style nobody would follow."""
    out = []
    i = lineno - 2                                   # line above the assignment (0-indexed)
    while i >= 0 and lines[i].lstrip().startswith("#"):
        out.append(lines[i])
        i -= 1
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
        "status": "OK" if not bad else "UNJUSTIFIED-CONSTANTS",
        "n_modules": len(mods), "n_unjustified": n_bad,
        "detail": (f"{sum(m.get('n_constants', 0) for m in mods)} money-path constants across "
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
