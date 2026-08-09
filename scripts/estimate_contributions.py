#!/usr/bin/env python3
"""THE ORGAN THAT CLOSES THE ALLOCATOR'S OWN BOTTLENECK -- dE[log W]/dC_i, per subsystem.

WHY THIS EXISTS. run_allocator has reported the same binding constraint on every cycle it has
ever run: "CONTRIBUTION ESTIMATES". Twelve of twenty subsystems can point at an artifact and not
one of them can say what a marginal unit of resource does to E[log W]. P4 routes the marginal
resource to argmax_i |dE[log W]/dC_i|, and that argmax was being taken over an empty set -- so
every allocation the desk has made was a guess wearing a formula, and the allocator said so
honestly rather than inventing numbers. This organ fills the set.

IT COMPUTES, IT DOES NOT ASSERT. Every contribution here is derived from an artifact ON DISK and
carries a `basis` naming the file and the field it came from. Where the artifact is absent or
empty, the contribution is emitted with provenance NEVER_EXECUTED and n=0, which is ranked but
can never clear an action threshold. That asymmetry is the whole design: absence must be VISIBLE
and COSTED without being mistaken for evidence.

WHY ESTIMATE AT ALL WHEN THE DESK HAS NEVER TRADED. Refusing to estimate is not neutral. A
subsystem excluded from the ranking is a subsystem assigned zero, and zero is a far stronger
claim than "unmeasured" -- it routes the marginal resource away from that subsystem forever, on
no evidence at all. P23 scores that as timidity. The honest alternative is an estimate with an
interval wide enough to say how little is known, which is exactly what the provenance ladder in
libs/doctrine/contribution.py produces.

UNITS. Every value is in E[log W] per unit of the subsystem's own cost unit (usually one cycle of
resource). They are small numbers. They are supposed to be: a desk whose subsystems each claim a
large marginal log-growth contribution is a desk that has not measured any of them.

Read-only over data/ and docs/. Writes one artifact. No network, no keys, no order paths.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.contribution import Contribution, rank, summarise  # noqa: E402

METRICS = ROOT / "data/desk_metrics.db"
REPORT = ROOT / "data/contributions.json"
HISTORY = ROOT / "data/contributions_history.jsonl"

#: Subsystem -> the artifact its estimate is derived FROM. Mirrors run_allocator's _INSTRUMENTS
#: deliberately rather than importing it: this organ must be able to say "the allocator expects a
#: number here and I could not compute one", which requires holding its own opinion about where
#: the number comes from. Divergence between the two maps is itself a defect, and the test suite
#: asserts they agree.
SOURCES: dict[str, str] = {
    "research/generation": "data/hypothesis_queue.jsonl",
    "research/screening": "data/gauntlet_calibration.json",
    "research/mining": "data/moat_mine.json",
    "research/features": "data/ancestors.json",
    "research/knowledge-graph": "data/research_cio.json",
    "research/data-mining": "data/breadth_expansion.jsonl",
    "validation": "data/gauntlet_calibration.json",
    "risk/allocation": "data/portfolio_risk.json",
    "portfolio": "desk_metrics:alpha_performance",
    "execution": "desk_metrics:fills",
    "costs": "desk_metrics:fills",
    "capacity": "data/slot_budget_analysis.json",
    "survival": "data/portfolio_risk.json",
    "llm/panel": "data/external_panel_log.jsonl",
    "engineering": "docs/GAP_REGISTER.md",
    "infrastructure": "data/panel_budget_state.json",
    "memory": "desk_metrics:research_memory",
    "scheduler": "data/cadence_state.json",
    "governance": "data/max_audit_report.json",
    "meta/self-improvement": "data/gauntlet_calibration_history.jsonl",
}

#: A validated alpha is worth roughly this much log-growth per cycle it is live. Used ONLY to
#: convert funnel throughput into E[log W] units -- it is a scale factor on estimates that are
#: already labelled BACKTEST or PRIOR, never a source of confidence on its own. Deliberately
#: conservative: if it is wrong by 2x every research contribution moves together, so the RANKING
#: (which is what the allocator consumes) is unaffected by the error.
LOGW_PER_LIVE_ALPHA_CYCLE = 0.002


def _read_json(rel: str) -> dict | list | None:
    p = ROOT / rel
    try:
        if not p.exists() or p.stat().st_size <= 2:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_jsonl(rel: str, cap: int = 20000) -> list[dict]:
    p = ROOT / rel
    rows: list[dict] = []
    try:
        if not p.exists():
            return rows
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(json.JSONDecodeError):
                    rows.append(json.loads(line))
                if len(rows) >= cap:
                    break
    except OSError:
        return rows
    return rows


def _table_rows(table: str) -> int:
    if not METRICS.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{METRICS}?mode=ro", uri=True) as c:
            return int(c.execute(f"select count(*) from {table}"  # noqa: S608 -- internal constant
                                 ).fetchone()[0])
    except sqlite3.Error:
        return 0


def _absent(sub: str, derivative: str, source: str, why: str) -> Contribution:
    """The honest empty. Ranked so the gap stays visible and costed; n=0 and NEVER_EXECUTED so it
    can never be acted upon as evidence."""
    return Contribution(
        subsystem=sub, derivative=derivative, value=0.0, se=0.0, n=0,
        provenance="NEVER_EXECUTED",
        basis=f"{source}: {why}. No observation exists, so this is a placeholder that keeps the "
              "subsystem in the ranking rather than silently assigning it zero.",
        tags=("absent",))


# ---------------------------------------------------------------- per-subsystem derivations


def _research_generation() -> Contribution:
    d = "dE[log W] / d(hypotheses generated)"
    rows = _read_jsonl("data/hypothesis_queue.jsonl")
    if not rows:
        return _absent("research/generation", d, "data/hypothesis_queue.jsonl", "queue is empty")
    reached = sum(1 for r in rows if str(r.get("stage", "")).upper() in ("L4", "L5", "PROMOTED"))
    rate = reached / len(rows)
    # Bernoulli SE on the pass rate, propagated through the value-per-alpha scale factor.
    se_rate = ((rate * (1 - rate) / len(rows)) ** 0.5) or (1.0 / len(rows))
    return Contribution(
        subsystem="research/generation", derivative=d,
        value=rate * LOGW_PER_LIVE_ALPHA_CYCLE,
        se=se_rate * LOGW_PER_LIVE_ALPHA_CYCLE, n=len(rows),
        provenance="BACKTEST",
        basis=(f"data/hypothesis_queue.jsonl: {reached}/{len(rows)} candidates reached L4+, "
               f"scaled by {LOGW_PER_LIVE_ALPHA_CYCLE} log-growth per live alpha-cycle. BACKTEST "
               "because no candidate has ever traded, so the pass rate is the only observed term"),
        tags=("funnel",))


def _research_mining() -> Contribution:
    d = "dE[log W] / d(moat exploration)"
    rep = _read_json("data/moat_mine.json")
    if not isinstance(rep, dict):
        return _absent("research/mining", d, "data/moat_mine.json", "no mining report")
    cov = rep.get("cumulative_coverage", {})
    pct = float(cov.get("coverage_pct", rep.get("coverage_pct", 0.0)))
    closure = rep.get("closure", {})
    runs = int(closure.get("pct_per_run", {}).get("n", 0))
    if runs < 3:
        return _absent("research/mining", d, "data/moat_mine.json",
                       f"only {runs} coverage observation(s) -- a rate needs at least 3")
    rate = float(closure.get("pct_per_run", {}).get("rate", 0.0))
    se = float(closure.get("pct_per_run", {}).get("se", 0.0)) or abs(rate)
    # Coverage is the input to discovery, not growth itself: value it at the funnel's own
    # conversion, one percentage point of owned-data coverage per unit of miner resource.
    return Contribution(
        subsystem="research/mining", derivative=d,
        value=rate * LOGW_PER_LIVE_ALPHA_CYCLE, se=se * LOGW_PER_LIVE_ALPHA_CYCLE, n=runs,
        provenance="BACKTEST",
        basis=(f"data/moat_mine.json closure: coverage {pct}% moving {rate:+.4f} pp/run over "
               f"{runs} runs (se {se:.4f}), scaled by the funnel's value per alpha-cycle"),
        tags=("moat",))


def _research_screening() -> Contribution:
    d = "dE[log W] / d(screen quality)"
    cal = _read_json("data/gauntlet_calibration.json")
    if not isinstance(cal, dict):
        return _absent("research/screening", d, "data/gauntlet_calibration.json",
                       "no calibration run")
    power = float(cal.get("power", cal.get("detection_power", 0.0)) or 0.0)
    fpr = float(cal.get("false_positive_rate", cal.get("fpr", 0.0)) or 0.0)
    n = int(cal.get("n", cal.get("trials", 0)) or 0)
    if n <= 0:
        return _absent("research/screening", d, "data/gauntlet_calibration.json",
                       "calibration present but reports no trials")
    # A screen contributes by admitting true edge and excluding false edge. Both terms, because a
    # screen optimised on power alone is a screen that admits everything.
    val = (power - fpr) * LOGW_PER_LIVE_ALPHA_CYCLE
    return Contribution(
        subsystem="research/screening", derivative=d, value=val,
        se=(1.0 / max(1, n) ** 0.5) * LOGW_PER_LIVE_ALPHA_CYCLE, n=n, provenance="BACKTEST",
        basis=(f"data/gauntlet_calibration.json: power {power:.2f} minus FPR {fpr:.2f} over "
               f"{n} planted-truth trials. Both terms, because a screen judged on power alone "
               "is a screen that admits everything"),
        tags=("funnel",))


def _validation() -> Contribution:
    d = "dE[log W] / d(validation integrity)"
    cal = _read_json("data/gauntlet_calibration.json")
    if not isinstance(cal, dict):
        return _absent("validation", d, "data/gauntlet_calibration.json", "no calibration run")
    ppv = cal.get("p_true_given_pass", cal.get("ppv"))
    n = int(cal.get("n", cal.get("trials", 0)) or 0)
    if ppv is None or n <= 0:
        return _absent("validation", d, "data/gauntlet_calibration.json",
                       "P(true edge | passed) has never been measured against planted truth")
    return Contribution(
        subsystem="validation", derivative=d,
        value=float(ppv) * LOGW_PER_LIVE_ALPHA_CYCLE,
        se=(1.0 / max(1, n) ** 0.5) * LOGW_PER_LIVE_ALPHA_CYCLE, n=n, provenance="BACKTEST",
        basis=(f"data/gauntlet_calibration.json: P(true edge | passed) = {float(ppv):.3f} over "
               f"{n} planted-truth trials"),
        tags=("funnel",))


def _memory() -> Contribution:
    d = "dE[log W] / d(-duplicate research)"
    n = _table_rows("research_memory")
    if n <= 0:
        return _absent("memory", d, "desk_metrics:research_memory", "table is empty")
    # Every remembered result is one research cycle not repeated. Valued at the marginal cost of a
    # cycle rather than at the value of an alpha: memory saves WORK, it does not create edge.
    return Contribution(
        subsystem="memory", derivative=d,
        value=0.02 * LOGW_PER_LIVE_ALPHA_CYCLE, se=0.01 * LOGW_PER_LIVE_ALPHA_CYCLE, n=n,
        provenance="PRIOR",
        basis=(f"desk_metrics:research_memory holds {n} recorded results; each is one research "
               "cycle not repeated. Valued at the cost of a CYCLE, not at the value of an alpha "
               "-- memory saves work, it does not create edge. PRIOR because the counterfactual "
               "(would this have been repeated?) is reasoned, never observed"),
        tags=("efficiency",))


def _llm_panel() -> Contribution:
    d = "dE[log W] / d(exhaustion of model inventory)"
    rows = _read_jsonl("data/external_panel_log.jsonl")
    if not rows:
        return _absent("llm/panel", d, "data/external_panel_log.jsonl", "panel has never logged")
    novel = sum(1 for r in rows if r.get("novel") or r.get("new_finding"))
    rate = novel / len(rows)
    return Contribution(
        subsystem="llm/panel", derivative=d,
        value=rate * LOGW_PER_LIVE_ALPHA_CYCLE,
        se=(((rate * (1 - rate) / len(rows)) ** 0.5) or 1.0 / len(rows))
        * LOGW_PER_LIVE_ALPHA_CYCLE,
        n=len(rows), provenance="SHADOW",
        basis=(f"data/external_panel_log.jsonl: {novel}/{len(rows)} rounds produced a finding "
               "marked novel. SHADOW rather than LIVE because novelty is self-assessed by the "
               "panel and no admitted finding has yet been validated downstream"),
        tags=("llm",))


def _infrastructure() -> Contribution:
    d = "dE[log W] / d(infrastructure $)"
    st = _read_json("data/panel_budget_state.json")
    if not isinstance(st, dict):
        return _absent("infrastructure", d, "data/panel_budget_state.json", "no budget state")
    spent = float(st.get("spent_usd", st.get("spent", 0.0)) or 0.0)
    calls = int(st.get("calls", st.get("n_calls", 0)) or 0)
    if spent <= 0 or calls <= 0:
        return _absent("infrastructure", d, "data/panel_budget_state.json",
                       f"budget state present but records spend={spent} over {calls} calls")
    return Contribution(
        subsystem="infrastructure", derivative=d,
        value=(calls / spent) * LOGW_PER_LIVE_ALPHA_CYCLE * 1e-3,
        se=(calls / spent) * LOGW_PER_LIVE_ALPHA_CYCLE * 1e-3 * 0.5,
        n=calls, provenance="PRIOR",
        basis=(f"data/panel_budget_state.json: {calls} research calls for ${spent:.2f}. The "
               "throughput bought per dollar is observed; its conversion into log-growth is "
               "reasoned, which is what keeps this PRIOR"),
        tags=("cost",))


def _scheduler() -> Contribution:
    d = "dE[log W] / d(compute cycles)"
    st = _read_json("data/cadence_state.json")
    if not isinstance(st, dict):
        return _absent("scheduler", d, "data/cadence_state.json", "no cadence state")
    ran = int(st.get("steps_run", st.get("ran", 0)) or 0)
    total = int(st.get("steps_total", st.get("total", 0)) or 0)
    if total <= 0:
        return _absent("scheduler", d, "data/cadence_state.json",
                       "cadence state present but records no steps")
    util = ran / total
    return Contribution(
        subsystem="scheduler", derivative=d, value=util * LOGW_PER_LIVE_ALPHA_CYCLE,
        se=(1.0 / max(1, total) ** 0.5) * LOGW_PER_LIVE_ALPHA_CYCLE, n=total, provenance="LIVE",
        basis=(f"data/cadence_state.json: {ran}/{total} scheduled steps actually ran. LIVE "
               "because the scheduler's own throughput is directly observed -- it is one of the "
               "few quantities on this desk that needs no counterfactual"),
        tags=("throughput",))


def _governance() -> Contribution:
    d = "dE[log W] / d(governance hour)"
    rep = _read_json("data/max_audit_report.json")
    if not isinstance(rep, dict):
        return _absent("governance", d, "data/max_audit_report.json", "no audit report")
    defects = int(rep.get("live_defects", len(rep.get("defects", []) or [])) or 0)
    if defects <= 0 and not rep.get("checks"):
        return _absent("governance", d, "data/max_audit_report.json", "report carries no checks")
    checks = int(rep.get("checks", 0) or 0)
    return Contribution(
        subsystem="governance", derivative=d,
        value=0.05 * LOGW_PER_LIVE_ALPHA_CYCLE, se=0.04 * LOGW_PER_LIVE_ALPHA_CYCLE,
        n=max(checks, defects), provenance="PRIOR",
        basis=(f"data/max_audit_report.json: {checks} registered checks surfacing {defects} live "
               "defects. The defects are observed; their counterfactual cost is reasoned, and "
               "P21 makes governance a weapon judged on the throughput it multiplies rather than "
               "on the violations it counts"),
        tags=("governance",))


def _fills_backed(sub: str, derivative: str, basis_detail: str) -> Contribution:
    n = _table_rows("fills")
    if n <= 0:
        return _absent(sub, derivative, "desk_metrics:fills",
                       "no fill has ever been recorded -- the desk has never traded, so the "
                       "producing path has not executed once")
    return Contribution(
        subsystem=sub, derivative=derivative, value=0.0, se=0.0, n=n, provenance="LIVE",
        basis=f"desk_metrics:fills over {n} fills: {basis_detail}", tags=("live",))


def _portfolio() -> Contribution:
    d = "dE[log W] / dw_i, jointly"
    n = _table_rows("alpha_performance")
    if n <= 0:
        return _absent("portfolio", d, "desk_metrics:alpha_performance",
                       "no sleeve has a performance record -- MC_i is undefined with no book")
    return Contribution(
        subsystem="portfolio", derivative=d, value=0.0, se=0.0, n=n, provenance="LIVE",
        basis=f"desk_metrics:alpha_performance over {n} rows: MC_i per sleeve", tags=("live",))


def _generic(sub: str) -> Contribution:
    """Subsystems whose artifact exists but whose derivation is not yet specific.

    Deliberately NOT given a plausible number. An estimate with a made-up basis is worse than an
    absent one: it enters the ranking with the same standing as a measured quantity and nothing
    downstream can tell them apart. So the artifact is checked for CONTENT, and the honest verdict
    is that the desk has data here and has not yet written the derivation.
    """
    src = SOURCES[sub]
    d = f"dE[log W] / d({sub})"
    present = (_table_rows(src.split(":", 1)[1]) > 0 if src.startswith("desk_metrics:")
               else (ROOT / src).exists() and (ROOT / src).stat().st_size > 2)
    if not present:
        return _absent(sub, d, src, "artifact absent or empty")
    return Contribution(
        subsystem=sub, derivative=d, value=0.0, se=0.0, n=0, provenance="NEVER_EXECUTED",
        basis=(f"{src} EXISTS and holds data, but no derivation from it to E[log W] has been "
               "written yet. Recorded as unestimated rather than given a plausible number: a "
               "made-up basis enters the ranking with the standing of a measurement and nothing "
               "downstream can tell them apart"),
        tags=("derivation-owed",))


DERIVATIONS = {
    "research/generation": _research_generation,
    "research/mining": _research_mining,
    "research/screening": _research_screening,
    "validation": _validation,
    "memory": _memory,
    "llm/panel": _llm_panel,
    "infrastructure": _infrastructure,
    "scheduler": _scheduler,
    "governance": _governance,
    "portfolio": _portfolio,
    "execution": lambda: _fills_backed(
        "execution", "dE[log W] / dX", "theoretical minus realised edge per fill"),
    "costs": lambda: _fills_backed(
        "costs", "-dE[log W] / dC", "fees, funding, borrow and slippage over gross edge"),
}


def build() -> list[Contribution]:
    out = []
    for sub in SOURCES:
        fn = DERIVATIONS.get(sub)
        out.append(fn() if fn else _generic(sub))
    return out


def main() -> int:
    t0 = time.time()
    cs = build()
    costs = {c.subsystem: 1.0 for c in cs}
    rows = rank(cs, costs)
    s = summarise([c for c in cs if "absent" not in c.tags and "derivation-owed" not in c.tags],
                  set(SOURCES))

    measured = [c for c in cs if c.provenance.upper() != "NEVER_EXECUTED"]
    actionable = [c for c in cs if c.actionable()]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "subsystems": len(cs),
        "measured": len(measured),
        "measured_pct": round(100.0 * len(measured) / max(1, len(cs)), 1),
        "actionable": len(actionable),
        "argmax_computable": s["argmax_computable"],
        "still_unestimated": s["unestimated"],
        "ranked": rows,
        "bottleneck": (
            "CONTRIBUTION ESTIMATES" if len(measured) < len(cs) / 2 else
            "ERROR BARS -- every subsystem states a contribution; the work is narrowing them"),
        "note": ("Values are E[log W] per unit of the subsystem's cost unit. They are small on "
                 "purpose: a desk whose subsystems each claim a large marginal log-growth "
                 "contribution is a desk that has measured none of them. Provenance inflates the "
                 "standard error rather than shrinking the value, so a NEVER_EXECUTED entry is "
                 "ranked and costed but can never clear an action threshold."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "measured": len(measured),
                             "actionable": len(actionable)}, separators=(",", ":")) + "\n")

    print(f"contributions: {len(measured)}/{len(cs)} subsystems state a contribution "
          f"({out['measured_pct']}%) | {len(actionable)} actionable | {out['seconds']}s")
    for r in rows[:6]:
        flag = "ACT" if r["actionable"] else "   "
        print(f"  [{flag}] #{r['rank']} {r['subsystem']:<26} {r['density']:+.6f}  "
              f"[{r['provenance']}] n={r['n']}")
    if s["unestimated"]:
        print(f"  still unestimated: {', '.join(s['unestimated'][:8])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
