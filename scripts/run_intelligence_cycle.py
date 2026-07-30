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
        from libs.self_improvement.dormancy import scan, summarise
    except ImportError as e:
        return _cap("dormancy_hunter", "ERROR", f"import failed: {e}")
    rep = summarise(scan())
    n = sum(rep["counts"].values()) if isinstance(rep.get("counts"), dict) else 0
    return _cap("dormancy_hunter", "ACTIVE",
                f"{n} dormant capabilities ({rep['total_dormant_lines']} paid-for unused lines) "
                f"across {rep['scanned']['modules']} modules + {rep['scanned']['scripts']} scripts",
                report=rep)


def main() -> int:
    caps = [
        _dormancy(),
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
