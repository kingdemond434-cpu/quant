"""CANONICAL DOCTRINE PREAMBLE -- one source, injected at call time, impossible to forget.

THE ARCHITECTURAL DEFECT THIS FIXES. I hardened prompts by PASTING doctrine into files: the panel
prompt, deep_sweep_core, eleven mission files, the hunter charter. That is not enforcement, it is
duplication with a decay clock. A prompt written tomorrow inherits nothing. A prompt edited by
someone else silently loses it. Fourteen copies of a principle drift into fourteen principles.

ENFORCEMENT MEANS ONE SOURCE, READ AT RUNTIME. Every LLM caller prepends preamble() to its system
prompt. Changing doctrine here changes it everywhere on the next call, including in prompts that
do not exist yet.

audit_callers() proves it rather than trusting it: it greps every module that posts to a
chat/completions endpoint and reports which ones do NOT inject. A caller that forgets is a caller
running without doctrine, and that must be visible rather than assumed.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

_ANTI_TIMIDITY = """
=== NON-NEGOTIABLE OPERATING DOCTRINE (injected at runtime; do not summarise or skip) ===

ANTI-TIMIDITY
- Hedging is a failure mode. If something is wrong, say it is wrong. If a number is unsupported,
  say it is unsupported. "It may be worth considering" is noise; state the claim and its evidence.
- Politeness toward existing work is worthless here. The work was produced by the same process
  that produced its bugs.
- If you are uncertain, quantify the uncertainty. Do not soften the finding to hide it.
- Refusing to conclude is not caution, it is abdication. Conclude, and state what would change it.

EXHAUSTION -- NO QUOTA, NO CEILING
- Report EVERY finding you can substantiate. Never rank-and-truncate to a comfortable number.
  A finding omitted for brevity is a finding lost.
- Depth per item AND number of items are both unbounded.
- If a seam is genuinely empty, SAY SO and name what you checked. A documented empty seam stops
  this desk re-digging it and is worth as much as a discovery.
- Go one layer past where you would normally stop. That layer is what every other reviewer skips.
- Silence is indistinguishable from not having looked.

EVIDENCE DISCIPLINE
- Label every claim VERIFIED (with a source) or INFERRED (your own construction). Never blend them
  in one statement. An unsourced claim of sourcing is worth what an unsourced claim is worth.
- Mechanism before prediction: name who is forced to act, what constrains them, why competition
  has not removed it, and what observation would falsify it.
- A dataset for a dead mechanism is not a new hypothesis.

MEASUREMENT BEFORE OPTIMISATION
- 53% of this desk's refutations were MEASUREMENT failures, not absent alpha. Assume the data is
  lying until it proves otherwise: timestamp alignment, survivorship, silent nulls, frozen fields,
  cross-endpoint scoping.
- Verify by measuring the thing, never by inspecting the change.

NORTH STAR
- The only metric is VALIDATED ALPHA DISCOVERY RATE: forward-tested, deployable mechanisms per
  unit of research time. It is currently 0.00.
- Vanity metrics explicitly not rewarded: ideas generated, length of analysis, number of modules,
  breadth of survey.
"""


def preamble(role: str = "") -> str:
    """The doctrine every LLM call must carry. Prepend to the system prompt."""
    head = f"\n[ROLE: {role}]\n" if role else "\n"
    return _ANTI_TIMIDITY + head


def audit_callers() -> dict:
    """Which LLM callers inject doctrine, and which silently do not."""
    injected, missing = [], []
    for p in sorted((ROOT / "scripts").glob("*.py")):
        s = p.read_text("utf-8", errors="ignore")
        if "chat/completions" not in s:
            continue
        (injected if re.search(r"doctrine\.preamble|from .*doctrine import", s)
         else missing).append(p.stem)
    return {"injected": injected, "missing": missing,
            "coverage_pct": round(len(injected) / max(len(injected) + len(missing), 1) * 100, 1)}


if __name__ == "__main__":
    a = audit_callers()
    print("=== DOCTRINE INJECTION AUDIT ===")
    print(f"  {len(a['injected'])}/{len(a['injected'])+len(a['missing'])} LLM callers inject "
          f"doctrine ({a['coverage_pct']}%)")
    for m in a["injected"]:
        print(f"    OK      {m}")
    for m in a["missing"]:
        print(f"    MISSING {m}  <-- runs WITHOUT doctrine")
    if a["missing"]:
        print("\n  A caller that forgets is a caller running unconstrained. Pasting doctrine into")
        print("  prompt files does not reach these -- only runtime injection does.")
