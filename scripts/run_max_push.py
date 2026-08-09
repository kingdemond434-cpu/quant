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
_FRONTIER_OUT = _ROOT / "data/economic_frontier.json"

from libs.research.frontier import Action, ResourcePrices  # noqa: E402
from libs.research.frontier import summarise as frontier_summary  # noqa: E402
from libs.research.gap_contract import load_published, to_queue_rows  # noqa: E402

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
    "calibration_debt": (
        0.80, "every Kelly bet and every promotion rests on a probability the desk assigned; if "
              "those are systematically over-confident the desk over-bets EVERY position and "
              "the error is invisible per-decision (L1.29). Unscored forecasts inflate the "
              "apparent hit rate by never counting the misses"),
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
                  # "queue" as well as "slot": forward_queue_depth (R0205) measures what is
                  # STAGED BEHIND the cohort, which is evidence throughput and not capital. The
                  # default branch below is capital_utilisation, so an unmatched research ceiling
                  # is silently filed against the wrong bottleneck rather than left unrouted.
                  "evidence_throughput" if ("slot" in name or "queue" in name) else
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
    # THREE STATES, NOT TWO. This read `if d.get("repair_mode")`, which was `status != "OK"` at
    # the source and therefore TRUE for ARRIVALS-COLLAPSED -- so the desk's top-ranked queue told
    # a window that had found almost nothing to go and convert instead of hunting. The direction
    # field (L1.28b(d)) separates "the queue is deep" from "the hunt has gone quiet"; they demand
    # opposite work and only one of them is a conversion problem.
    _ACTION = {
        "DRAIN": ("repair-mode: flip the next audit/brain window from finding to fixing; drain "
                  "past-due rows first (each names its own fix)"),
        "FIND-HARDER": ("arrivals collapsed: HUNT HARDER this window -- do NOT redirect it to "
                        "the backlog; raising the ratio by finding less is the denominator "
                        "trick L1.28b(f) forbids"),
        "STEADY": "keep dispositions >= arrivals; a row nobody closes is a cost already paid",
    }
    action = _ACTION.get(str(d.get("direction") or ""),
                         "conversion state UNREADABLE -- treat as owing work, not as nothing "
                         "owing (L1.28a); run scripts/check_conversion.py")
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


def _from_calibration() -> list[dict[str, Any]]:
    """Is the desk's own confidence measured and honest? (L1.29)

    Reliability (1 - Brier) is the aspect; an UNFORECASTING or OVERDUE desk reports UNMEASURED,
    which outranks everything -- a desk that never grades its predictions cannot know whether
    it is over-betting."""
    d = _json("data/calibration_status.json") or {}
    st = str(d.get("status", "UNFORECASTING"))
    rel = d.get("reliability")
    measured = st not in ("UNFORECASTING", "OVERDUE") and rel is not None
    return [_item("calibration::forecast_reliability", "calibration_debt",
                  float(rel) if measured else None, 1.0,
                  str(d.get("detail", "no calibration artifact")),
                  "log a probability at every real decision point and RESOLVE it by its "
                  "deadline; the measured bias then shrinks future confidence automatically "
                  "(forecast_calibration.calibrated_confidence)",
                  "data/calibration_status.json")]


def _from_freshness() -> list[dict[str, Any]]:
    """Are live decisions consuming frozen inputs? (L1.44)

    fresh_fraction is the aspect. STALE-CONSUMED means a decision path is being steered by a
    dead producer's last output RIGHT NOW -- money_path_correctness by definition, because the
    bootstrap contracts are the executor's own read sites. UNMEASURED (zero contracts) reports
    unmeasured and ranks above partially-complete work, as everywhere else."""
    d = _json("data/freshness_status.json") or {}
    st = str(d.get("status", "UNMEASURED"))
    frac = d.get("fresh_fraction")
    measured = st != "UNMEASURED" and frac is not None
    return [_item("freshness::contracts_fresh", "money_path_correctness",
                  float(frac) if measured else None, 1.0,
                  str(d.get("detail", "no freshness artifact")),
                  "revive the dead producer or re-wire the caller through "
                  "libs.ops.fresh.read_fresh -- check_freshness.py names both ends of every "
                  "stale edge",
                  "data/freshness_status.json")]


def _from_stranding() -> list[dict[str, Any]]:
    """CONVERSION FAILURES the wiring source structurally cannot see, and that is the whole point.

    `_from_wiring` reads `wiring_agent.json`, which counts scripts nothing SCHEDULES. That misses
    the two states an importer count cannot reach (L1.54(a)): a module IMPORTED and never called,
    and a module that runs while nothing reads its output. Both look reachable from every angle
    the older sources have.

    MEASURED 2026-08-08 and the reason this function exists rather than a note in the register:
    `run_intelligence_cycle` imports `capital_reallocator` and `health_monitor` purely to prove
    they import, then reads the artifacts itself and reports both ACTIVE. The detector found them
    the same morning it was built -- and the queue could not see the finding, so the desk could
    discover a real gap and never prioritise it. Detection without ranking is half a control.

    Scored as `dormant_capability` rather than as a new class: it IS paid-for engineering
    returning zero, and inventing a weight would rank worse while looking more precise.
    """
    d = _json("data/intelligence_cycle.json") or {}
    caps = d.get("capabilities") if isinstance(d, dict) else None
    rows: list[dict[str, Any]] = []
    if isinstance(caps, list):
        for c in caps:
            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
                rows = c.get("report", {}).get("imported_but_never_called", []) or []
                break
    if not isinstance(rows, list):
        return []
    scanned = 0
    if isinstance(caps, list):
        for c in caps:
            if isinstance(c, dict) and c.get("name") == "dormancy_hunter":
                scanned = int((c.get("report", {}).get("scanned", {}) or {}).get("modules", 0))
                break
    if not scanned:
        # UNMEASURED, NOT ZERO. An absent cycle artifact means nobody looked, and letting that
        # read as "no conversion failures" is WS-005 aimed at the queue's own inputs.
        return [_item("capability::conversion_failures", "dormant_capability", None, 1.0,
                      "no intelligence-cycle artifact -- the stranding scan has not run here",
                      "run scripts/run_intelligence_cycle.py; UNMEASURED outranks a partial "
                      "number because an unknown quantity is being ignored, not worked",
                      "data/intelligence_cycle.json")]
    n = len(rows)
    worst = ", ".join(str(r.get("path", "?")) for r in rows[:3]) or "none"
    return [_item("capability::conversion_failures", "dormant_capability",
                  (scanned - n) / scanned, 1.0,
                  f"{n} module(s) imported by a live consumer that NEVER call them, of {scanned} "
                  f"scanned; worst by size: {worst}",
                  "call it from the consumer that already imports it, or delete the import -- an "
                  "import kept to prove a module loads reports ACTIVE while the capability has "
                  "never run once (L1.54(a))",
                  "data/intelligence_cycle.json")]


def _from_wealth() -> list[dict[str, Any]]:
    """THE ECONOMIC ROWS -- and they belong at the top of the queue, not appended to it.

    Every other `_from_*` reader above measures the desk's PROCESS: floors, fences, wiring,
    conversion, calibration. All of them are proxies for the only thing that decides whether this
    enterprise was worth running, and none of them can fall while real wealth is being lost. A
    queue built purely from process metrics can be entirely green on the day the book round-trips.

    So `data/wealth_report.json` enters the same ranking as everything else, and its DAILY BOARD
    QUESTION becomes a queue row rather than a line in a log. The specification's instruction is
    literal: the highest-value answer becomes the next task.

    Two shapes come through. An UNMEASURED section is scored as unmeasured, which the ranker
    already puts above partially-complete work -- correct here, because "we do not know whether we
    are keeping what we make" outranks any known-and-being-worked number. A MEASURED section with
    a finding (a round trip, hidden beta, process-bound survivors) comes through as a money-path
    row, the heaviest weight the ranker carries.
    """
    d = _json("data/wealth_report.json")
    if not isinstance(d, dict):
        # UNMEASURED, NOT ABSENT-THEREFORE-FINE. No wealth report means nobody asked the board
        # question today, and letting that read as a clean board is WS-005 pointed at the one
        # artifact that outranks the rest of this file.
        return [_item("wealth::board_question", "money_path_correctness", None, 1.0,
                      "no wealth report -- the desk has not asked what is preventing it from "
                      "generating and retaining more real net wealth",
                      "run scripts/run_wealth_report.py; it is wired into the research cycle and "
                      "its absence means the cycle did not complete",
                      "data/wealth_report.json")]
    out: list[dict[str, Any]] = []
    answer = str(d.get("ANSWER", "?"))
    out.append(_item(
        "wealth::board_question", "money_path_correctness", None, 1.0,
        f"BOARD QUESTION answer: {answer}", str(d.get("why", ""))[:400],
        "data/wealth_report.json"))
    for name in d.get("unmeasured_sections") or []:
        sec = (d.get("sections") or {}).get(name) or {}
        out.append(_item(
            f"wealth::{name}", "capital_utilisation", None, 1.0,
            str(sec.get("headline", ""))[:200],
            f"produce {sec.get('missing_artifact', 'the input artifact')} -- until it exists this "
            "section is UNMEASURED, which is a fact about the inputs and not a clean result",
            "data/wealth_report.json"))
    sections = d.get("sections") or {}
    conv = sections.get("conversion") or {}
    process_bound = int(conv.get("process_bound") or 0)
    if process_bound:
        out.append(_item(
            "wealth::process_bound_survivors", "conversion_debt", 0.0, 1.0,
            f"{process_bound} candidate(s) hold sufficient evidence and are not moving, costing "
            f"at least {conv.get('total_process_waiting_cost_bps', 0)}bp",
            "advance each PROCESS_BOUND candidate to its next stage; this latency buys nothing "
            "and is not an evidence question", "data/wealth_report.json"))
    hidden = (sections.get("return_engines") or {}).get("hidden_beta") or []
    if hidden:
        out.append(_item(
            "wealth::hidden_beta", "money_path_correctness", 0.0, 1.0,
            f"{len(hidden)} engine(s) declared independent behave as market exposure",
            "reclassify or re-measure: capital sized against the wrong covariance is the "
            "mechanism behind a round trip", "data/wealth_report.json"))
    return out


#: Shadow prices, declared. THE HONEST STATE IS THAT MOST ARE UNMEASURED, and the frontier report
#: names every unpriced resource rather than letting a total read as a full accounting. Capital
#: carries the only non-zero price today because it is the one resource this desk demonstrably
#: cannot replace: compute and engineering time regenerate daily, a lost stack does not.
_SHADOW_PRICES: dict[str, float] = {"capital": 0.01}

#: How a queue row's declared leverage weight becomes an expected log-wealth contribution. This is
#: a UNIT CONVERSION, not a claim: the weights were never in log-wealth units, and pretending they
#: were would put a fabricated number at the top of the desk's ranking. The frontier report carries
#: the caveat, and the conversion is one constant so it can be argued with in one place.
_LEVERAGE_TO_ELOGW: float = 0.01


def _from_books() -> list[dict[str, Any]]:
    """THE RETURN ENGINES -- an UNMEASURED book is a ranked gap, not a quiet line in a report.

    `scripts/run_opportunity_books.py` runs eleven books every cycle and most of them correctly
    report UNMEASURED, each naming the exact artifact it needs. Left in the report, that reads as
    housekeeping. Ranked here, each missing artifact becomes a queue row competing with everything
    else on the same scale -- which is right, because a return engine with no input is a decision
    the desk is currently making by default rather than by evidence.

    THE DISTINCTION THAT MATTERS AND IS EASY TO LOSE: a book UNMEASURED because this clone has no
    live positions is a fact about the clone. A book UNMEASURED because nobody wrote its
    declaration is a fact about the desk, and only the second is actionable today. The row detail
    carries the book's own headline so the reader can tell which they are looking at.
    """
    d = _json("data/opportunity_books.json")
    if not isinstance(d, dict):
        return [_item("books::opportunity_books", "unenforced_law", None, 1.0,
                      "no opportunity-books report -- eleven return engines exist and none of "
                      "them ran, so where capital would go is unranked",
                      "run scripts/run_opportunity_books.py; it is wired into the research cycle "
                      "and its absence means the cycle did not complete",
                      "data/opportunity_books.json")]
    books = d.get("books")
    if not isinstance(books, dict):
        return []
    out: list[dict[str, Any]] = []
    for name, body in books.items():
        if not isinstance(body, dict):
            continue
        if body.get("measured") is False:
            missing = str(body.get("missing_artifact", "?"))
            out.append(_item(
                f"books::{name}", "money_path_correctness", None, 1.0,
                f"return engine {name} is UNMEASURED -- {missing} is absent",
                str(body.get("headline", ""))[:400],
                "data/opportunity_books.json"))
            continue
        # A MEASURED BOOK IS NOT AUTOMATICALLY A CLEAN ONE, and ranking only the unmeasured ones
        # would have made a book that FOUND something the only book that never reaches the queue.
        # That is the inverse of what this file is for.
        for key, source, label in (
                ("over_privileged", "unenforced_law",
                 "component(s) hold authority above what their work needs"),
                ("capital_sensitive_without_principal", "money_path_correctness",
                 "component(s) sit on a CAPITAL-SENSITIVE rung with no principal authorisation"),
                ("unbounded_blast_radius", "money_path_correctness",
                 "component(s) can propagate failure or destroy irrecoverable data"),
                ("unmeasured_blast_radius", "measurement_quality",
                 "component(s) have never had their blast radius assessed"),
                ("not_sandboxed", "money_path_correctness",
                 "component(s) are not confined to an isolated sub-account or scoped key")):
            found = body.get(key)
            if isinstance(found, list) and found:
                out.append(_item(
                    f"books::{name}::{key}", source, None, 1.0,
                    f"{name}: {len(found)} {label} -- {found}",
                    str(body.get("headline", ""))[:400],
                    "data/opportunity_books.json"))
    return out


def _from_practitioners() -> list[dict[str, Any]]:
    """CORPORA READ WITHOUT EXTRACTING ANY PROCESS AXIS -- the expensive half left behind.

    Reading a practitioner's signal rules and stopping is the cheapest possible extraction and the
    one that feels complete. It is ranked here because it is silently recoverable value: the
    corpus has already been paid for, and the part that compounds is still sitting in it.
    """
    d = _json("data/intelligence/external_intel.json")
    if not isinstance(d, dict):
        return []
    pc = d.get("practitioner_corpus")
    if not isinstance(pc, dict) or pc.get("measured") is not True:
        return []
    out: list[dict[str, Any]] = []
    shallow = pc.get("read_but_no_process_extracted") or []
    if isinstance(shallow, list) and shallow:
        out.append(_item(
            "intel::practitioner_process_axes", "conversion_debt", None, 1.0,
            f"{len(shallow)} practitioner corpus/corpora read with NO process axis extracted: "
            f"{shallow}",
            "The signal rules were taken and the research, validation, retirement and replacement "
            "processes were not. That corpus is already paid for and the part that compounds is "
            "still in it -- re-extract along the process axes before enumerating anything new.",
            "data/intelligence/practitioner_corpus.json"))
    untested = pc.get("untested_disagreements")
    if isinstance(untested, int) and untested > 0:
        out.append(_item(
            "intel::practitioner_disagreements", "conversion_debt", None, 1.0,
            f"{untested} untested disagreement(s) between credible practitioners",
            "Where two people who both made money contradict each other, the answer is "
            "CONDITIONAL and the condition is the thing worth finding. Each is a ready-made "
            "hypothesis with an external prior already attached.",
            "data/intelligence/practitioner_corpus.json"))
    return out


def _frontier(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-rank the queue by ECONOMIC SURPLUS rather than by distance-from-ceiling.

    THE TWO ORDERINGS DISAGREE IN A WAY THAT DECIDES DAYS. This file ranks by how far a metric sits
    from 100%, which is correct for a ratchet and wrong for an allocator: a research module at 0%
    outranks deploying a validated survivor at "done", even when the survivor's marginal
    contribution is larger and its opportunity cost is a euro of compute rather than a euro of
    capital. The frontier answers the allocator's question instead.

    Both are published. The queue is the RATCHET -- it never reports done and escalates when
    everything is green. The frontier is the ALLOCATOR. Replacing one with the other would lose a
    control the desk relies on, so neither is deleted.

    The surplus numbers here are DERIVED FROM DECLARED WEIGHTS, not measured, and the report says
    so. Their ordering is informative; their magnitudes are not yet.
    """
    actions: list[Action] = []
    for i in items[:40]:
        gap = float(i.get("gap_fraction") or 0.0)
        lev = float(i.get("leverage") or 0.0)
        if gap <= 0:
            continue
        mean = gap * lev * _LEVERAGE_TO_ELOGW
        # UNMEASURED aspects carry a WIDER posterior, not a larger mean. An unknown quantity is
        # ranked above a known one by the queue's own rule; it must not also be treated as
        # confidently valuable by the allocator.
        sigma = mean * (0.8 if not i.get("measured") else 0.3)
        actions.append(Action(
            action_id=str(i.get("aspect", "?"))[:80],
            category=str(i.get("source", "unknown")),
            elogw_mean=mean, elogw_sigma=max(sigma, 1e-9),
            resources={"research_attention": 1.0},
            proposer=str(i.get("source", "")),
        ))
    rep = frontier_summary(actions, ResourcePrices(dict(_SHADOW_PRICES)))
    rep["derivation_caveat"] = (
        "Surpluses are DERIVED from run_max_push's declared leverage weights via a single "
        f"conversion constant ({_LEVERAGE_TO_ELOGW}), because those weights were never in "
        "log-wealth units. The ORDERING is informative; the MAGNITUDES are not yet, and no sizing "
        "decision may cite them. They become real when actions carry measured posterior "
        "distributions from the wealth report and the live ladder.")
    return rep


def build(*, refresh: bool = True) -> dict[str, Any]:
    if refresh:
        for s in ("check_ratchets.py", "check_utilisation.py", "build_enforcement_matrix.py",
                  "check_conversion.py", "check_calibration.py", "check_freshness.py"):
            _refresh(s)
    items = (_from_ratchets() + _from_utilisation() + _from_matrix()
             + _from_wiring() + _from_register() + _from_conversion()
             + _from_tier_benchmark() + _from_calibration() + _from_freshness()
             + _from_stranding() + _from_wealth()
             + _from_books() + _from_practitioners()
             # THE GENERIC CHANNEL. Every `_from_*` above is a bespoke reader that knows the shape
             # of one artifact, and adding the tenth made the cost visible: a detector written
             # today cannot influence tomorrow's priorities until somebody edits THIS file, which
             # makes the ranker a gatekeeper on discovery. Detectors now publish `Gap` rows to
             # data/published_gaps/ and are ranked with no edit here. The readers above stay --
             # rewriting working producers to prove a point is the bloat this contract avoids.
             + to_queue_rows(load_published(), _item))
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
    # THE ALLOCATOR'S VIEW, published alongside the ratchet's. Neither replaces the other.
    front = _frontier(rep["queue"])
    _FRONTIER_OUT.write_text(json.dumps(front, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"MAX PUSH [{rep['verdict']}] {rep['n_aspects']} aspects | "
              f"mean completion {rep['mean_completion']:.1%} | "
              f"{rep['n_unmeasured']} UNMEASURED | {rep['n_at_ceiling']} at ceiling")
        for i, r in enumerate(rep["queue"][:args.top], 1):
            cur = "UNMEASURED" if not r["measured"] else f"{float(r['current']):.1%}"
            print(f"{i:3}. [{r['score']:.3f}] {r['aspect']:44} {cur:>11}  {r['detail'][:60]}")
        print(f"FRONTIER: {front['headline']}")
        print(f"-> {_OUT.relative_to(_ROOT)}, {_FRONTIER_OUT.relative_to(_ROOT)}")
    # Never fails the build: this is the WORK QUEUE, not a gate. A queue that fails CI would be
    # muted within a week, and the whole point is that it is read every morning.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
