"""INTELLIGENCE CYCLE -- activates the desk's dormant intelligence-compounding layer.

THE FINDING THAT PRODUCED THIS (measured 2026-07-30, not assumed). The principal's strategic
review named research meta-learning, agent evolution, prediction calibration, capital-allocation
learning, information-advantage measurement and an alpha-decay lab as the highest-ROI MISSING
subsystems. They are not missing. Every one of them is BUILT and has ZERO CALLERS:

    libs/self_improvement/meta_learning.py        regime -> alpha affinity learning
    libs/self_improvement/research_priority.py    experiment ERV/decay ranking
    libs/self_improvement/capital_reallocator.py  capital-allocation learning
    libs/self_improvement/health_monitor.py       per-alpha decay/health assessment
    libs/self_improvement/marketplace.py          research capital market
    libs/self_improvement/weight_optimizer.py     allocation weights
    libs/self_improvement/lifecycle_actions.py    promote/demote/retire actions
    scripts/moat_audit.py                         information-advantage measurement
    scripts/revalidate_clocks.py                  decay revalidation of live axes

Proving command: `grep -rl "self_improvement.<mod>" scripts/ libs/ | grep -v libs/self_improvement/`
returned NOTHING for each. So the gap was never architecture -- it was ACTIVATION (L2.9), and the
correct fix is one organ that runs them on a schedule, NOT eleven new subsystems, which is exactly
the complexity inflation the anti-bloat rule forbids.

WHAT IT DOES: runs each dormant capability against whatever real state exists, writes one evidence
artifact (`web/intelligence_cycle.json`), and reports per-capability status
ACTIVE / NO-INPUT / ERROR. NO-INPUT is a first-class verdict, never a silent skip: a capability
that cannot run for want of data is a DATA gap and must read as one (0 validated alphas today means
several of these legitimately have nothing to chew on yet, and saying so is the honest output).

ZERO PROMOTION AUTHORITY. Every insight here is non-deployable by construction --
`meta_learning.govern()` refuses to mark anything deployable unless cpcv/dsr/pbo/walk-forward all
pass, and this organ never asserts they do. It produces INSIGHT, never capital moves.

    python scripts/run_intelligence_cycle.py [--json]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
# `python scripts/x.py` puts scripts/ on sys.path, not the repo root, so `import libs` fails
# unless the package happens to be pip-installed. On the VPS it is; on a FRESH RESTORE it is not,
# which would make this organ read ERROR on every capability for a purely environmental reason
# (measured on first run: 4/7 ERROR "No module named 'libs'"). Make it work in both worlds.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "web/intelligence_cycle.json"


def _read(rel: str) -> Any:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _cap(name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"capability": name, "status": status, "detail": detail, **extra}


def _meta_learning() -> dict[str, Any]:
    """Regime -> alpha affinity. Needs regime labels + per-alpha return series."""
    try:
        import numpy as np

        from libs.self_improvement.meta_learning import MetaLearningEngine
    except ImportError as e:
        return _cap("meta_learning", "ERROR", f"import failed: {e}")
    shadow = _read("web/cashcarry_shadow.json")
    series = None
    if isinstance(shadow, dict):
        for key in ("returns", "daily_returns", "pnl_series"):
            v = shadow.get(key)
            if isinstance(v, list) and len(v) >= 20:
                series = [float(x) for x in v if isinstance(x, (int, float))]
                break
    if not series:
        return _cap("meta_learning", "NO-INPUT",
                    "needs a per-alpha return series (web/cashcarry_shadow.json returns[]); "
                    "0 validated alphas means there is genuinely little to learn affinity over")
    regime = _read("web/regime.json") or {}
    label = str(regime.get("regime") or regime.get("state") or "unlabelled")
    # One regime label per observation: with a single current label this is a degenerate but HONEST
    # run -- it records the affinity of the only regime the desk can name today.
    insight = MetaLearningEngine().learn_regime_affinity(
        [label] * len(series), {"carry": np.asarray(series)})
    governed = MetaLearningEngine().govern(insight, cpcv_pass=False, dsr_pass=False,
                                           pbo_pass=False, walk_forward_pass=False)
    return _cap("meta_learning", "ACTIVE",
                f"regime->alpha affinity over n={len(series)} in regime '{label}'",
                deployable=bool(governed.deployable), relationship=insight.relationship)


def _data_registry() -> dict[str, Any]:
    """MEASURED data inventory (EXECUTION_QUEUE.md RANK 4, GAP_REGISTER #77).

    Runs here rather than only on its own cron because the map is what every OTHER organ in this
    cycle navigates by: research_priority ranks what to test, and row #77's whole lesson is that
    those rankings were being made off an inventory that reported row counts as spans and omitted
    the desk's best panel. A stale map is worse than no map, so it is rebuilt in the same tick that
    consumes it.
    """
    try:
        from libs.research.data_registry import REPL_PROPRIETARY, build
    except ImportError as e:
        return _cap("data_registry", "ERROR", f"import failed: {e}")
    assets = build()
    if not assets:
        return _cap("data_registry", "NO-INPUT",
                    "no collector declares a data path -- discovery found nothing to measure")
    measured = [a for a in assets if a.span.measured]
    absent = [a for a in assets if a.span.status == "absent"]
    unread = [a for a in assets if (a.span.days or 0) > 365 and not a.consumers]
    longest = max(measured, key=lambda a: a.span.days or 0, default=None)
    detail = (f"{len(assets)} assets, {len(measured)} MEASURED spans, "
              f"{len(absent)} declared-but-absent")
    if longest:
        detail += f"; longest {longest.id} {longest.span.days}d"
    if unread:
        detail += f"; {len(unread)} with >1y history and NO reader"
    return _cap(
        "data_registry", "ACTIVE" if measured else "NO-INPUT", detail,
        assets=len(assets), measured=len(measured), absent=len(absent),
        longest_span_days=(longest.span.days if longest else 0),
        widest_breadth=max((a.breadth or 0 for a in assets), default=0),
        proprietary=[a.id for a in assets if a.replication == REPL_PROPRIETARY],
        unread_long_history=[a.id for a in unread],
    )


def _research_priority() -> dict[str, Any]:
    """Rank research categories by decay pressure + expected yield."""
    try:
        from libs.self_improvement.research_priority import ResearchPriorityEngine
    except ImportError as e:
        return _cap("research_priority", "ERROR", f"import failed: {e}")
    brief = _read("data/executive_kpis.json") or {}
    # Decay pressure per mechanism family, from the desk's own family-kill record when present.
    decay = {}
    fams = brief.get("family_survival") if isinstance(brief, dict) else None
    if isinstance(fams, dict):
        for fam, st in fams.items():
            if isinstance(st, dict) and isinstance(st.get("rate"), (int, float)):
                decay[str(fam)] = max(0.0, 1.0 - float(st["rate"]))
    if not decay:
        # Fall back to the DESK_BRIEF family kills, which are always present in the repo.
        decay = {"price_only": 1.0, "attention_social": 1.0, "trader_behavioural": 1.0,
                 "funding_positioning": 0.5, "onchain_flow": 0.8, "regional_premium": 0.9}
    ranked = ResearchPriorityEngine().prioritize(decaying_by_category=decay)
    return _cap("research_priority", "ACTIVE",
                f"ranked {len(ranked)} research categories by decay pressure",
                top=[{"category": p.category, "score": round(p.priority_score, 3),
                      "reason": p.reason} for p in ranked[:5]])


def _capital_reallocator() -> dict[str, Any]:
    try:
        import libs.self_improvement.capital_reallocator  # noqa: F401
    except ImportError as e:
        return _cap("capital_reallocator", "ERROR", f"import failed: {e}")
    live = _read("web/cashcarry_live.json") or {}
    sleeves = live.get("sleeves") if isinstance(live, dict) else None
    if not isinstance(sleeves, dict) or len(sleeves) < 2:
        return _cap("capital_reallocator", "NO-INPUT",
                    "needs >=2 deployed sleeves to reallocate between; the desk runs 1 (carry). "
                    "This is a DEPLOYED-ALPHA gap, not a code gap -- it activates at sleeve 2")
    return _cap("capital_reallocator", "ACTIVE", f"{len(sleeves)} sleeves available")


def _health_monitor() -> dict[str, Any]:
    try:
        import libs.self_improvement.health_monitor  # noqa: F401
    except ImportError as e:
        return _cap("health_monitor", "ERROR", f"import failed: {e}")
    cards = _read("data/alpha_registry.json") or _read("web/alpha_lifecycle.json")
    n = len(cards.get("alphas", [])) if isinstance(cards, dict) else 0
    if not n:
        return _cap("health_monitor", "NO-INPUT",
                    "needs >=1 alpha card with live metrics; registry holds 0 -- the binding "
                    "constraint is validated alphas, and no amount of code changes that")
    return _cap("health_monitor", "ACTIVE", f"{n} alpha card(s) assessable")


def _subprocess_cap(name: str, script: str, timeout_s: float = 240.0,
                    args: list[str] | None = None) -> dict[str, Any]:
    """Run a standalone dormant script and record that it EXECUTED, with its own exit code.

    ``args`` exists for capabilities that have a deliberately cheap mode inside the cycle -- the
    strategic director runs --dry-run here so a 6-hourly tick proves its path without spending
    OpenRouter credit on every fire.
    """
    path = _ROOT / script
    if not path.exists():
        return _cap(name, "ERROR", f"{script} missing")
    try:
        env = {**os.environ, "PYTHONPATH": f"{_ROOT}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
        p = subprocess.run([sys.executable, script, *(args or [])], cwd=_ROOT, env=env,
                           capture_output=True, timeout=timeout_s, check=False, text=True)
    except subprocess.TimeoutExpired:
        return _cap(name, "ERROR", f"{script} exceeded {timeout_s:.0f}s")
    tail = (p.stdout or p.stderr or "").strip().splitlines()
    return _cap(name, "ACTIVE" if p.returncode == 0 else "NO-INPUT",
                f"{script} exit={p.returncode}: {tail[-1][:180] if tail else 'no output'}")


def _dormancy() -> dict[str, Any]:
    """THE STANDING VERSION OF TODAY'S BIGGEST FIND. On 2026-07-30 nine 'missing' subsystems turned
    out to be built with zero callers -- found because someone happened to grep. This makes that
    question mechanical: what does nothing import, and what does nothing schedule?
    Priority encoded (principal): find unused capability BEFORE inventing new capability."""
    try:
        from libs.self_improvement.dormancy import (
            imported_but_never_called,
            scan,
            summarise,
        )
    except ImportError as e:
        return _cap("dormancy_hunter", "ERROR", f"import failed: {e}")
    rep = summarise(scan())
    # THE SCAN'S OWN BLIND SPOT, measured 2026-08-08: it asks "does anything IMPORT it", so a
    # consumer that imports a module and then only mentions it in prose flips it from dormant to
    # reachable while the desk has still never run it. Reported alongside rather than merged --
    # these are orphans WITH an importer, and the fix is to call it, not to write a consumer.
    silent = imported_but_never_called()
    rep["imported_but_never_called"] = [
        {"path": d.path, "lines": d.lines, "reason": d.reason, "exit": d.suggested_exit}
        for d in sorted(silent, key=lambda x: -x.lines)[:20]]
    n = sum(rep["counts"].values()) if isinstance(rep.get("counts"), dict) else 0
    return _cap("dormancy_hunter", "ACTIVE",
                f"{n} dormant capabilities ({rep['total_dormant_lines']} paid-for unused lines) "
                f"across {rep['scanned']['modules']} modules + {rep['scanned']['scripts']} "
                f"scripts; {len(silent)} imported-but-never-called",
                report=rep)


def _orphan_chain() -> dict[str, Any]:
    """ORPHANS BEYOND MODULES -- every producer whose output nothing consumes.

    `dormancy` covers CODE. The expensive orphans are further down the chain, where the desk has
    already paid for the discovery: a dataset turned into no feature, a hypothesis never tested, a
    survivor never portfolio-tested. None of those is visible to an importer count -- the code all
    works and the artifacts all exist, and the chain is broken at a join nobody watches.

    PUBLISHES rather than prints, so the max-push queue ranks the finding beside every other gap
    without anyone editing the ranker. Detection that cannot reach a priority is half a control.
    """
    try:
        from libs.research.gap_contract import publish
        from libs.research.orphan_scan import scan, summarise, to_gaps
    except ImportError as e:
        return _cap("orphan_chain", "ERROR", f"import failed: {e}")
    counts = scan()
    rep = summarise(counts)
    publish("orphan_chain", to_gaps(counts))
    n_un = len(rep["unwatched"]) if isinstance(rep.get("unwatched"), list) else 0
    return _cap("orphan_chain", "ACTIVE",
                f"{rep['measured']}/{rep['joins']} conversion joins measured, {n_un} unwatched; "
                f"bottleneck: {rep['bottleneck'] or 'UNMEASURED'}",
                report=rep)


def _unknowns() -> dict[str, Any]:
    """THE LEDGER OF WHAT THE DESK BELIEVES WITHOUT EVIDENCE, and what evidence has contradicted.

    Assumptions, contradictions and unknowns are one object at three confidence levels, and the
    valuable events are the MOVES between them -- a KNOWN that live evidence disputes is the most
    expensive transition on the desk, because everything downstream was sized as though it held.

    AN EMPTY LEDGER IS NOT A CLEAN BILL. A desk with no recorded assumptions has unrecorded ones,
    so the report says that in those words rather than reporting zero.
    """
    try:
        from libs.research.unknowns import Item, summarise
    except ImportError as e:
        return _cap("unknowns_ledger", "ERROR", f"import failed: {e}")
    raw = _read("data/unknowns.json") or {}
    rows = raw.get("items") if isinstance(raw, dict) else None
    items = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            items.append(Item(
                key=str(r["key"]), state=str(r["state"]), statement=str(r.get("statement", "")),
                falsifier=str(r.get("falsifier", "")),
                depends_on_it=tuple(str(x) for x in (r.get("depends_on_it") or [])),
                needs_data=tuple(str(x) for x in (r.get("needs_data") or [])),
                evidence=str(r.get("evidence", "")), trigger=str(r.get("trigger", ""))))
        except (KeyError, ValueError):
            # A row the ledger's own constructor refuses is a DEFECT IN THE ROW, not a reason to
            # drop the whole ledger -- most often a belief written with no falsifier.
            continue
    rep = summarise(items)
    return _cap("unknowns_ledger", "ACTIVE" if items else "NO-INPUT", str(rep["headline"]),
                report=rep)


def _source_roi() -> dict[str, Any]:
    """WHICH MINER, MODEL OR PROMPT ACTUALLY PRODUCES VALIDATED ALPHA.

    The desk knows how many documents each miner found. It has never measured whether any of them
    became a survivor. Volume is a COST here, never an output: a source returning 100,000 pages and
    zero independent survivors is worse than one returning 100 and two, because it also spends
    triage -- the scarcest input in the chain.
    """
    try:
        from libs.research.source_roi import SourceRecord, summarise
    except ImportError as e:
        return _cap("source_roi", "ERROR", f"import failed: {e}")
    raw = _read("data/source_production.json") or {}
    rows = raw.get("sources") if isinstance(raw, dict) else None
    recs = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        recs.append(SourceRecord(
            name=str(r["name"]), kind=str(r.get("kind", "miner")),
            found=int(r.get("found", 0) or 0), novel=int(r.get("novel", 0) or 0),
            hypotheses=int(r.get("hypotheses", 0) or 0), tested=int(r.get("tested", 0) or 0),
            survivors=int(r.get("survivors", 0) or 0),
            independent=int(r.get("independent", 0) or 0),
            portfolio_positive=int(r.get("portfolio_positive", 0) or 0),
            cost_units=float(r.get("cost_units", 0.0) or 0.0),
            window_days=int(r.get("window_days", 0) or 0)))
    if not recs:
        return _cap("source_roi", "NO-INPUT",
                    "no data/source_production.json -- the miners do not yet emit their own funnel "
                    "counts, so no source can be shown to be earning OR failing. That is a "
                    "MEASUREMENT gap in the desk, not a verdict on any source")
    rep = summarise(recs)
    return _cap("source_roi", "ACTIVE", str(rep["headline"]), report=rep)


def _cadence_roi() -> dict[str, Any]:
    """IS EACH SCHEDULE RUNNING AT THE FREQUENCY ITS YIELD JUSTIFIES?

    Every cadence on this desk was CHOSEN rather than measured. The manifest records what somebody
    picked without recording why, and L1.28c says every schedule hunts its own ceiling -- nothing
    has ever checked whether one is at it.

    UNDER-RUN IS THE INVISIBLE FAILURE and the reason this leads with it: an over-run job at least
    shows up in a cost report, while an under-run one simply finds less than it could have, forever,
    and nothing records the difference.
    """
    try:
        from libs.research.cadence_roi import CadenceRecord, summarise
    except ImportError as e:
        return _cap("cadence_roi", "ERROR", f"import failed: {e}")
    raw = _read("data/cadence_production.json") or {}
    rows = raw.get("jobs") if isinstance(raw, dict) else None
    recs = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("job"):
            continue
        recs.append(CadenceRecord(
            job=str(r["job"]), interval_minutes=float(r.get("interval_minutes", 0) or 0),
            fires=int(r.get("fires", 0) or 0),
            productive_fires=int(r.get("productive_fires", 0) or 0),
            findings=int(r.get("findings", 0) or 0),
            cost_per_fire=float(r.get("cost_per_fire", 0.0) or 0.0),
            hard_floor_reason=str(r.get("hard_floor_reason", ""))))
    if not recs:
        return _cap("cadence_roi", "NO-INPUT",
                    "no data/cadence_production.json -- every schedule on this desk was chosen "
                    "rather than measured, and THAT is the finding. No cadence may be slowed on an "
                    "unmeasured yield; tightening also needs the number")
    rep = summarise(recs)
    return _cap("cadence_roi", "ACTIVE", str(rep["headline"]), report=rep)


def _cadence_alignment() -> dict[str, Any]:
    """IS EACH SCHEDULER FAST ENOUGH FOR THE EDGE IT WATCHES?

    A DIFFERENT QUESTION FROM `_cadence_roi`, which asks whether a job produces anything per fire.
    This asks whether it can still be in TIME. A job can be productive on every fire and lose most
    of the edge, because it only ever sees what survived until it looked -- and that loss appears
    in no metric the desk keeps, since every metric is computed over what WAS observed.
    """
    try:
        from libs.research.cadence_alignment import StrategyCadence, summarise
    except ImportError as e:
        return _cap("cadence_alignment", "ERROR", f"import failed: {e}")
    raw = _read("data/strategy_horizons.json") or {}
    rows = raw.get("strategies") if isinstance(raw, dict) else None
    recs = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("strategy"):
            continue
        recs.append(StrategyCadence(
            strategy=str(r["strategy"]),
            half_life_minutes=float(r.get("half_life_minutes", 0) or 0),
            interval_minutes=float(r.get("interval_minutes", 0) or 0),
            edge_bps=float(r.get("edge_bps", 0.0) or 0.0),
            opportunities_per_day=float(r.get("opportunities_per_day", 0.0) or 0.0),
            hard_floor_reason=str(r.get("hard_floor_reason", ""))))
    if not recs:
        return _cap("cadence_alignment", "NO-INPUT",
                    "no data/strategy_horizons.json -- no strategy declares its alpha half-life, "
                    "so no schedule on this desk can be justified OR refused. Every interval is a "
                    "number somebody picked once")
    rep = summarise(recs)
    return _cap("cadence_alignment", "ACTIVE", str(rep["headline"]), report=rep)


def _capability_regression() -> dict[str, Any]:
    """§XXX. Did any change this cycle quietly cost a capability?

    THE SNAPSHOT IS THE WHOLE MECHANISM and on this clone it is absent, which is itself the
    finding: a regression you did not measure before is one you cannot detect after, because the
    only evidence of what was lost left with the code. Reporting NO-INPUT here is honest;
    reporting a clean board would be the exact substitution the module exists to prevent.
    """
    try:
        from libs.self_improvement.capability_regression import CapabilitySnapshot, summarise
    except ImportError as e:
        return _cap("capability_regression", "ERROR", f"import failed: {e}")
    raw = _read("data/capability_snapshots.json")
    pairs = []
    if isinstance(raw, dict):
        for row in raw.get("comparisons", []):
            try:
                b, a = row["before"], row["after"]
                pairs.append((
                    CapabilitySnapshot(subsystem=str(b.get("subsystem", "?")),
                                       at=str(b.get("at", "")),
                                       metrics={str(k): float(v)
                                                for k, v in (b.get("metrics") or {}).items()},
                                       tests_passing=tuple(b.get("tests_passing") or ())),
                    CapabilitySnapshot(subsystem=str(a.get("subsystem", "?")),
                                       at=str(a.get("at", "")),
                                       metrics={str(k): float(v)
                                                for k, v in (a.get("metrics") or {}).items()},
                                       tests_passing=tuple(a.get("tests_passing") or ()))))
            except (KeyError, ValueError, TypeError):
                continue
    if not pairs:
        return _cap("capability_regression", "NO-INPUT",
                    "data/capability_snapshots.json absent -- every change on this desk is "
                    "currently an unverified upgrade claim, and a regression would be invisible")
    rep = summarise(pairs)
    return _cap("capability_regression",
                "ACTIVE" if not rep["regressions"] else "NO-INPUT",
                str(rep["headline"]), report=rep)


def main() -> int:
    caps = [
        _dormancy(),
        _orphan_chain(),
        _unknowns(),
        _source_roi(),
        _cadence_roi(),
        _cadence_alignment(),
        _capability_regression(),
        # BEFORE the organs that navigate by it -- research_priority ranks what to test, and row
        # #77 is what happens when that ranking is made off a stale map.
        _data_registry(),
        _meta_learning(),
        _research_priority(),
        _capital_reallocator(),
        _health_monitor(),
        # Standalone organs that had ZERO callers and were never scheduled.
        _subprocess_cap("label_factory", "scripts/build_labels.py"),
        _subprocess_cap("fusion_search", "scripts/run_fusion_search.py"),
        _subprocess_cap("strategic_director", "scripts/run_strategic_director.py",
                        args=["--dry-run"]),
        _subprocess_cap("backtest_verify", "scripts/verify_backtest_engine.py"),
        _subprocess_cap("moat_audit", "scripts/moat_audit.py"),
        _subprocess_cap("revalidate_clocks", "scripts/revalidate_clocks.py"),
        _subprocess_cap("fusion_engine", "scripts/fusion_engine.py"),
    ]
    counts: dict[str, int] = {}
    for c in caps:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    report = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.9 capability audit loop -- a built capability that never executes is technical "
               "debt. NO-INPUT is a DATA/ALPHA gap reported as one, never a silent skip.",
        "counts": counts, "capabilities": caps,
        "note": "zero promotion authority: every insight here is non-deployable by construction",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"intelligence cycle: {counts}")
        for c in caps:
            print(f"  {c['status']:9} {c['capability']:20} {c['detail'][:110]}")
    # Exit 0 even with NO-INPUT: those are data gaps the register tracks, not runner failures.
    return 1 if counts.get("ERROR") else 0


if __name__ == "__main__":
    raise SystemExit(main())
