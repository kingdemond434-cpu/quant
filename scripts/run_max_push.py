"""MAX PUSH (L1.0) -- one ranked queue of everything this desk is not yet at 100% on.

PRINCIPAL ORDER (2026-07-30): *"every aspect of quant should always aim and hunt to maximise
itself 100% every single day, believing it never is, and always max pushed."*

WHAT WAS ACTUALLY MISSING. The law already existed -- L1.0(c) says the gap between today's value
and 100% IS the work queue. What did not exist was the queue. The desk had FIVE separate
"what is left" artifacts, each true, none comparable:

    data/ratchet_report.json      metric floors and their distance to 100%
    data/utilisation.json         ceilings and their idle headroom (L1.28a)
    data/enforcement_matrix.json  principles with no fence
    data/wiring_agent.json        built capability nothing runs
    docs/GAP_REGISTER.md          open defects
    data/conversion_status.json   findings aging unconverted (L1.28b, added 2026-07-31)

Five lists nobody can rank against each other is the same as no list: the desk works whichever one
it happened to open. This merges them into ONE queue ordered by expected contribution, so "what is
the highest-value thing not yet at 100%" has an answer every morning without anyone deciding.

=================================================================================================
THE ANTI-COMPLACENCY PROPERTY, which is the part the principal actually asked for
=================================================================================================
This organ NEVER reports "done". When every measured aspect reaches its ceiling it does not
congratulate the desk -- it escalates, because at that point the MEASUREMENT SET is the suspect,
not the desk. A system that can reach 100% on everything it measures is a system measuring too
little; the honest reading of an all-green board is "we are no longer looking hard enough", and
that is emitted as the top queue item rather than as a clean bill of health.

This is why UNMEASURED aspects rank ABOVE partially-complete ones. An aspect at 60% is a known
quantity being worked; an aspect with no number is an unknown quantity being ignored, and it has
historically been where every expensive defect lived (capacity parity was "fine" until measured;
test strength was "fine" until measured at 55%; capital utilisation read over 100% the first time
anyone computed it, exposing two sources of truth for the desk's own equity).

LEVERAGE IS DECLARED, NOT COMPUTED. Ranking pretends to no EV model it does not have. Each source
carries a weight with a stated reason, and the weights are visible in one dict below so they can
be argued with -- an invented EV number would be less honest and no more useful.

    python scripts/run_max_push.py [--json] [--top N]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/max_push_queue.json"

# Leverage per source class: how much does closing one unit of this gap move the two supreme
# objectives? Declared with reasons rather than computed, because the desk has no EV model for
# heterogeneous engineering work and a fabricated one would rank worse while looking rigorous.
_LEVERAGE: dict[str, tuple[float, str]] = {
    "money_path_correctness": (
        1.00, "an undetected fault on the money path can end compounding outright (L1.23); every "
              "other guarantee sits on top of it"),
    "capital_utilisation": (
        0.90, "an idle dollar is compounding that never starts, and the loss is unbooked -- it "
              "appears in no P&L and raises no error (L1.28a)"),
    "evidence_throughput": (
        0.85, "forward slots and discovery rate set how fast validated edges can EXIST at all; an "
              "empty slot is evidence that will never be accrued"),
    "unenforced_law": (
        0.70, "a principle with no fence is prose -- it cannot fire and degrades silently into "
              "decoration (L2.0). Every defect found 2026-07-30 was of this shape"),
    "dormant_capability": (
        0.55, "engineering already paid for, returning zero forever, and rotting into a liability "
              "because nobody maintains what nobody runs (L2.9)"),
    "measurement_quality": (
        0.65, "test strength and type coverage bound how much of the above the desk can TRUST"),
    "open_defect": (
        0.50, "a known defect nobody closed; its cost is already being paid"),
    "conversion_debt": (
        0.95, "a finding aging in the queue is alpha already paid for and never collected; the "
              "measured spread between build-rate (~14 findings/day) and convert-rate "
              "(~0.6/day, deep sweep 2026-07-31) is the desk's largest single loss, and it "
              "multiplies every other row -- every queue item IS conversion (L1.28b)"),
    "tier1_process_gap": (
        0.75, "the principal's standing order (2026-07-31): every gap to tier-1 PROCESS closes "
              "autonomously, without being told -- only calendar-time walls are exempt. A layer "
              "below T1 is a known distance to the best practice that exists, with its closer "
              "named in the benchmark register"),
}

# Aspects with no number at all rank above partially-complete ones -- see module docstring.
_UNMEASURED_PRIORITY = 1.15


def _json(rel: str) -> Any:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _refresh(script: str) -> None:
    """Re-run a producer so the queue is built on today's numbers, not last week's."""
    try:
        subprocess.run([sys.executable, str(_ROOT / "scripts" / script), "--report-only"],
                       check=False, capture_output=True, timeout=300, cwd=_ROOT,
                       env={**dict(__import__("os").environ), "PYTHONPATH": str(_ROOT)})
    except (OSError, subprocess.TimeoutExpired):
        return


def _item(aspect: str, source: str, current: float | None, ceiling: float, detail: str,
          action: str, artifact: str) -> dict[str, Any]:
    measured = current is not None
    gap = 1.0 if not measured else max(0.0, (ceiling - current) / ceiling if ceiling else 0.0)
    weight, why = _LEVERAGE[source]
    score = gap * weight * (_UNMEASURED_PRIORITY if not measured else 1.0)
    return {"aspect": aspect, "source": source, "measured": measured,
            "current": None if not measured else round(float(current), 4),
            "ceiling": ceiling, "gap_fraction": round(gap, 4), "leverage": weight,
            "score": round(score, 4), "why_it_matters": why, "detail": detail,
            "next_action": action, "artifact": artifact}


def _from_ratchets() -> list[dict[str, Any]]:
    d = _json("data/ratchet_report.json") or {}
    out = []
    for r in d.get("rows", d.get("metrics", [])) or []:
        name = str(r.get("metric", r.get("name", "?")))
        val = r.get("value", r.get("current"))
        source = ("measurement_quality" if "strength" in name or "mypy" in name
                  else "evidence_throughput")
        out.append(_item(
            f"ratchet::{name}", source, None if val is None else float(val), 1.0,
            f"floor {r.get('floor')} status {r.get('status')}",
            "close the gap to 100%; the survivor/failure list IS the work queue (L1.0c)",
            "data/ratchet_report.json"))
    return out


def _from_utilisation() -> list[dict[str, Any]]:
    d = _json("data/utilisation.json") or {}
    out = []
    for c in d.get("ceilings", []) or []:
        name = str(c.get("name"))
        source = ("capital_utilisation" if "capital" in name else
                  "evidence_throughput" if "slot" in name else
                  "dormant_capability" if "capability" in name else
                  "measurement_quality" if "kill_rate" in name else "capital_utilisation")
        out.append(_item(
            f"ceiling::{name}", source,
            None if not c.get("measured") else float(c.get("utilisation", 0.0)), 1.0,
            f"{c.get('used')}/{c.get('limit')} {c.get('unit')} -- {c.get('status')}",
            c.get("binding_constraint") or "no binding constraint named -- L1.28a defect",
            "data/utilisation.json"))
    return out


def _from_matrix() -> list[dict[str, Any]]:
    d = _json("data/enforcement_matrix.json") or {}
    unenforced = d.get("unenforced", []) or []
    orphans = d.get("fences_without_a_principle", []) or []
    n_prin = max(int(d.get("n_principles", 1)), 1)
    n_fence = max(int(d.get("n_fences", 1)), 1)
    return [
        _item("law::principles_enforced", "unenforced_law",
              (n_prin - len(unenforced)) / n_prin, 1.0,
              f"{len(unenforced)} unenforced: {unenforced[:5]}",
              "map each to a fence, or record it HUMAN-ONLY with the reason",
              "data/enforcement_matrix.json"),
        _item("law::fences_claimed", "unenforced_law", (n_fence - len(orphans)) / n_fence, 1.0,
              f"{len(orphans)} fences claimed by no law",
              "name the governing law in _FENCE_OWNERS, or retire the fence",
              "data/enforcement_matrix.json"),
    ]


def _from_wiring() -> list[dict[str, Any]]:
    """The DORMANT-SCRIPT backlog awaiting a human cadence decision.

    The obvious metric here -- AUTO-WIRE / (AUTO-WIRE + PROPOSE) -- is backwards, and it read 0%
    on the first run of this queue. Once the agent has wired everything it can prove inert, those
    scripts become SCHEDULED and drop out of the dormancy scan entirely, so the auto-wire count
    falls to zero precisely when the automation is fully caught up. Zero there is the FINISHED
    state being reported as total failure.

    What actually remains open is the PROPOSE set: scripts the agent deliberately withheld because
    they touch the money path, can spend, or write outside data/ -- each needing a decision no
    agent is allowed to make. Measured against all scripts scanned, that is a real backlog that
    shrinks as decisions are taken.
    """
    d = _json("data/wiring_agent.json") or {}
    counts = d.get("counts", {}) or {}
    scanned = int(d.get("n_scripts_scanned", 0) or 0)
    proposed = int(counts.get("PROPOSE", 0))
    if not scanned:
        return []
    return [_item("capability::wiring_decisions_pending", "dormant_capability",
                  (scanned - proposed) / scanned, 1.0,
                  f"{proposed} scripts awaiting a cadence decision, of {scanned} scanned "
                  f"({counts}); AUTO-WIRE=0 means the agent is caught up, not stalled",
                  "each PROPOSE row names why it was withheld (money-path / spend / writes "
                  "outside data+web) -- decide a cadence or record why it stays unscheduled",
                  "data/wiring_agent.json")]


def _from_register() -> list[dict[str, Any]]:
    p = _ROOT / "docs/GAP_REGISTER.md"
    if not p.exists():
        return []
    text = p.read_text("utf-8", errors="ignore")
    rows = re.findall(r"^\|\s*#?(\d+)\s*\|", text, re.MULTILINE)
    open_rows = len(re.findall(r"\bOPEN\b", text))
    total = max(len(rows), 1)
    return [_item("register::rows_closed", "open_defect",
                  max(0.0, (total - open_rows) / total), 1.0,
                  f"{open_rows} OPEN of {total} rows",
                  "close highest-EV rows first; a row nobody closes is a cost already being paid",
                  "docs/GAP_REGISTER.md")]


def _from_conversion() -> list[dict[str, Any]]:
    """Conversion debt (L1.28b) ranks in the SAME queue as every other gap.

    Two aspects: the all-time dispositioned fraction (how much of everything ever found reached
    a verdict) and the 7-day flow ratio (is conversion keeping pace with detection RIGHT NOW).
    A missing artifact reports both as unmeasured, which outranks everything (L1.28a: unmeasured
    counts as zero) -- the fence being unwired is itself the top conversion defect.
    """
    d = _json("data/conversion_status.json") or {}
    ratio = d.get("queue_dispositioned")
    arr, disp = d.get("arrivals_7d"), d.get("dispositions_7d")
    flow = None if arr is None or disp is None else min(1.0, disp / arr) if arr else 1.0
    detail = d.get("detail") or "data/conversion_status.json missing -- run check_conversion.py"
    action = ("repair-mode: flip the next audit/brain window from finding to fixing; drain "
              "past-due rows first (each names its own fix)" if d.get("repair_mode")
              else "keep dispositions >= arrivals; a row nobody closes is a cost already paid")
    return [
        _item("conversion::queue_dispositioned", "conversion_debt",
              None if ratio is None else float(ratio), 1.0, detail, action,
              "data/conversion_status.json"),
        _item("conversion::flow_keeps_pace_7d", "conversion_debt", flow, 1.0,
              f"7d: {arr} raised vs {disp} dispositioned; status {d.get('status')}",
              action, "data/conversion_status.json"),
    ]


_TIER_SCORE = {"T1": 1.00, "T2": 0.66, "T3": 0.40, "T4": 0.15}


def _from_tier_benchmark() -> list[dict[str, Any]]:
    """The tier-1 process benchmark (principal 2026-07-31): sub-T1 layers hunt themselves.

    Parses docs/research/TIER1_BENCHMARK.md. time_bound rows are walls, not work -- listed in
    the register, excluded here. A missing register is UNMEASURED (ranks top): the benchmark
    being deleted is itself the largest tier gap.
    """
    p = _ROOT / "docs/research/TIER1_BENCHMARK.md"
    if not p.exists():
        return [_item("tier1::benchmark_register", "tier1_process_gap", None, 1.0,
                      "docs/research/TIER1_BENCHMARK.md missing -- the standing gap register "
                      "was deleted or never synced", "restore the register; the deep sweep "
                      "re-grades it weekly", "docs/research/TIER1_BENCHMARK.md")]
    out = []
    for m in re.finditer(
            r"^\|\s*(\w+)\s*\|\s*(T[1-4]|—)\s*\|\s*(.+?)\s*\|\s*\**(yes|no)\**\s*\|\s*$",
            p.read_text("utf-8"), re.MULTILINE):
        layer, tier, closer, time_bound = m.groups()
        if time_bound == "yes" or tier == "—":
            continue
        score = _TIER_SCORE.get(tier)
        if score is not None and score < 1.0:
            out.append(_item(f"tier1::{layer}", "tier1_process_gap", score, 1.0,
                             f"graded {tier} -- distance to tier-1 process is named work",
                             closer, "docs/research/TIER1_BENCHMARK.md"))
    return out


def build(*, refresh: bool = True) -> dict[str, Any]:
    if refresh:
        for s in ("check_ratchets.py", "check_utilisation.py", "build_enforcement_matrix.py",
                  "check_conversion.py"):
            _refresh(s)
    items = (_from_ratchets() + _from_utilisation() + _from_matrix()
             + _from_wiring() + _from_register() + _from_conversion()
             + _from_tier_benchmark())
    items.sort(key=lambda r: -float(r["score"]))
    at_ceiling = [i for i in items if i["measured"] and i["gap_fraction"] <= 0.0]
    unmeasured = [i for i in items if not i["measured"]]

    # THE ANTI-COMPLACENCY ESCALATION. All-green means the measurement set is too small, not that
    # the desk is finished. Emitted as the top item so it cannot be read as a clean board.
    verdict = "PUSH"
    if items and len(at_ceiling) == len(items):
        verdict = "MEASUREMENT-SET-TOO-SMALL"
        items.insert(0, _item(
            "meta::measurement_coverage", "unenforced_law", None, 1.0,
            f"all {len(items)} measured aspects are at their ceiling",
            "A system that reaches 100% on everything it measures is measuring too little. "
            "The correct next action is to ADD ceilings -- name an aspect of this desk that "
            "currently carries no number and give it one (L1.0a: a capability with no number "
            "is a defect).", "data/max_push_queue.json"))
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.0 -- the gap between today's value and 100% IS the work queue. This organ "
               "never reports done: all-green escalates to MEASUREMENT-SET-TOO-SMALL.",
        "verdict": verdict,
        "n_aspects": len(items), "n_unmeasured": len(unmeasured),
        "n_at_ceiling": len(at_ceiling),
        "mean_completion": round(
            sum(1.0 - float(i["gap_fraction"]) for i in items) / max(len(items), 1), 4),
        "queue": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--no-refresh", action="store_true", help="use existing artifacts as-is")
    args = ap.parse_args()
    rep = build(refresh=not args.no_refresh)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"MAX PUSH [{rep['verdict']}] {rep['n_aspects']} aspects | "
              f"mean completion {rep['mean_completion']:.1%} | "
              f"{rep['n_unmeasured']} UNMEASURED | {rep['n_at_ceiling']} at ceiling")
        for i, r in enumerate(rep["queue"][:args.top], 1):
            cur = "UNMEASURED" if not r["measured"] else f"{float(r['current']):.1%}"
            print(f"{i:3}. [{r['score']:.3f}] {r['aspect']:44} {cur:>11}  {r['detail'][:60]}")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    # Never fails the build: this is the WORK QUEUE, not a gate. A queue that fails CI would be
    # muted within a week, and the whole point is that it is read every morning.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
