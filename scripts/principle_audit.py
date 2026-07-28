"""Are ALL principles enforced, or only the five I happened to write into the preamble?

THE GAP I SUSPECT IN MY OWN WORK. doctrine.py enforces PRESENCE of a marker on three surfaces. It
never checks WHICH principles are present. I wrote five sections into the preamble; the doctrine
documents accumulated roughly fifteen principles across this session. Enforcing a marker while the
content is a subset is enforcement theatre -- the check passes, and two thirds of the doctrine
never reaches a single model.

This enumerates every principle the desk has committed to, and reports which are actually in the
runtime preamble that models receive.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data/principle_audit.json"

# Every principle this desk has adopted, with the phrases that would evidence it in a prompt.
PRINCIPLES = {
    "anti_timidity": ("hedging is a failure", "refusing to conclude", "say it is wrong"),
    "exhaustion_no_quota": ("no quota", "no ceiling", "exhaustion"),
    "evidence_discipline": ("verified", "inferred", "unsourced claim"),
    "measurement_before_optimisation": ("assume the data is lying", "measuring the thing"),
    "north_star": ("validated alpha discovery rate", "north star"),
    "mechanism_first": ("mechanism before prediction", "who is forced", "forced participant"),
    "bottleneck_first": ("bottleneck first", "current limiting factor"),
    "opportunity_cost": ("opportunity cost", "highest expected-value use", "next research hour"),
    "no_premature_optimisation": ("premature optimis", "before it proves"),
    "reality_feedback": ("live evidence", "reality overrides", "market is the final judge"),
    "complexity_governance": ("replace an existing component",),
    "stage_a_law": ("zero promotion authority", "stage-a", "forward clock"),
    "never_exhausted_exploration": ("never exhausted", "no ceiling", "one layer past"),
    "capacity_awareness": ("cannot be executed at the desk", "degrades with scale"),
    "kill_fast": ("would falsify", "rejected regardless"),
}


def main() -> None:
    from scripts.doctrine import preamble
    text = preamble().lower()
    rows, present, absent = [], [], []
    for name, kws in PRINCIPLES.items():
        hits = [k for k in kws if k in text]
        ok = bool(hits)
        (present if ok else absent).append(name)
        rows.append({"principle": name, "in_preamble": ok, "matched": hits})

    print("=== PRINCIPLE COVERAGE IN THE RUNTIME PREAMBLE ===")
    print("    doctrine.py enforces that a marker EXISTS on three surfaces. It never checked")
    print("    WHICH principles the preamble actually contains -- a passing check with a subset")
    print("    of the doctrine is enforcement theatre.\n")
    for r in rows:
        print(f"  {'IN ' if r['in_preamble'] else 'OUT'}  {r['principle']:<34}"
              f"{('matched: ' + r['matched'][0]) if r['matched'] else 'NOT PRESENT'}")
    pct = len(present) / len(PRINCIPLES) * 100
    print(f"\n  {len(present)}/{len(PRINCIPLES)} principles reach the models ({pct:.0f}%)")
    if absent:
        print(f"  ABSENT: {', '.join(absent)}")
        print("  These live only in documents. A model never sees them, so for every LLM call")
        print("  they do not exist. That is the difference between written and enforced.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "coverage_pct": round(pct, 1), "present": present,
                               "absent": absent}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    sys.exit(1 if absent else 0)


if __name__ == "__main__":
    main()
