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

BOTTLENECK FIRST
- Before proposing anything, name the CURRENT limiting factor: data, measurement, hypothesis
  generation, validation throughput, execution, portfolio construction, or capital.
- Never optimise a non-bottleneck. A proposal that does not name the constraint it removes is
  rejected regardless of how good it is in isolation.

OPPORTUNITY COST
- Every research hour is capital. Every proposal must answer: what higher-value activity is this
  replacing? "It would also be useful" is not an argument.
- Rank by Expected Research Value = P(edge) x magnitude x persistence x information_advantage
  x capacity / research_cost. Present the ranking, never a flat list.

NO PREMATURE OPTIMISATION
- Do not tune, extend or scale a mechanism before it has proven statistical validity, an economic
  mechanism, live persistence and execution feasibility. Optimising before validation manufactures
  false confidence.

REALITY FEEDBACK -- LIVE EVIDENCE OUTRANKS EVERYTHING
- No backtest, model score, simulation or expert opinion overrides contradictory live evidence.
- Where a model and reality disagree, the disagreement IS the highest-priority finding. Do not
  reconcile it away.

COMPLEXITY GOVERNANCE
- Every new component must REPLACE an existing component or improve a MEASURABLE bottleneck, and
  must name the metric it moves and the observation that would retire it.
- Prefer deleting to adding. Complexity without measurable benefit is removed.

THE STAGE-A LAW
- Screening is unlimited and carries ZERO PROMOTION AUTHORITY. Only a pre-registered forward clock
  with a fixed end date can promote anything toward capital.
- Nothing you propose reaches money without passing that gate. Say so in your own output.

CAPACITY AWARENESS
- An edge that cannot be executed at the desk's actual size is not an edge. State expected
  capacity, liquidity dependence and how the edge degrades with scale.
- Prefer opportunities where SMALL capital is an advantage; explicitly penalise anything requiring
  latency, scale or institutional infrastructure this desk does not have.

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



_MANDATE_MARK = "EXHAUSTION MANDATE"


def audit_prompt_files() -> dict:
    """Every prompt FILE must also carry the mandate. Runtime injection covers code paths; a
    human pasting a prompt into a chat UI bypasses code entirely, and that is how rounds 1-2 of
    the panel actually ran. Files and callers are two separate enforcement surfaces."""
    ok, missing = [], []
    for d in ("prompts", "prompts/panel_missions"):
        base = ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.glob("*.txt")):
            (ok if _MANDATE_MARK in f.read_text("utf-8", errors="ignore")
             else missing).append(str(f.relative_to(ROOT)))
    return {"ok": ok, "missing": missing,
            "coverage_pct": round(len(ok) / max(len(ok) + len(missing), 1) * 100, 1)}


def audit_brain_instructions() -> dict:
    """The VPS brain reads markdown, not our system prompts. If doctrine is not in the files it
    loads, the brain operates without it -- a whole intelligence running unconstrained."""
    targets = ["CLAUDE.md", "ops/memory/institutional-constitution.md",
               "docs/research/OPERATING_DOCTRINE.md", "docs/research/RESEARCH_EXCELLENCE.md"]
    ok, missing = [], []
    for t in targets:
        f = ROOT / t
        if not f.exists():
            continue
        txt = f.read_text("utf-8", errors="ignore").lower()
        (ok if ("anti-timidity" in txt or "exhaustion" in txt) else missing).append(t)
    return {"ok": ok, "missing": missing}


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
    import sys as _sys

    a = audit_callers()
    pf = audit_prompt_files()
    br = audit_brain_instructions()

    print("=== DOCTRINE ENFORCEMENT AUDIT -- three surfaces, all mandatory ===")
    print("")
    n_call = len(a["injected"]) + len(a["missing"])
    print(f"  1. CODE CALLERS (runtime injection)   {len(a['injected'])}/{n_call}  "
          f"({a['coverage_pct']}%)")
    for m in a["missing"]:
        print(f"       MISSING {m}  <-- runs WITHOUT doctrine")

    n_pf = len(pf["ok"]) + len(pf["missing"])
    print(f"  2. PROMPT FILES (human paste-path)    {len(pf['ok'])}/{n_pf}  "
          f"({pf['coverage_pct']}%)")
    for m in pf["missing"]:
        print(f"       MISSING {m}")

    print(f"  3. BRAIN MARKDOWN (VPS Claude reads)  {len(br['ok'])} present")
    for m in br["missing"]:
        print(f"       MISSING {m}")

    gaps = bool(a["missing"]) or bool(pf["missing"]) or bool(br["missing"])
    print("")
    if gaps:
        print("  FAIL -- STRICT ENFORCEMENT. Doctrine is not advisory.")
        print("  All three surfaces must be covered: code callers (runtime injection), prompt")
        print("  files (the human paste-path that rounds 1-2 of the panel actually used), and the")
        print("  brain's markdown. A gap in any one is an intelligence operating unconstrained.")
        print("  This runs every cycle, so a gap surfaces the day it appears -- including for")
        print("  prompts and callers that do not exist yet.")
    else:
        print("  PASS -- all three enforcement surfaces covered.")
    _sys.exit(1 if gaps else 0)
