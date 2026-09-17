"""THE BANDIT'S SHARES SET THE RESEARCH LEGS' TIME BUDGETS -- authority, measured.

The closed-loop attestation asks `research.evig_controller_authoritative` and the honest answer
was no: `research_bandit` priced its arms and the hourly cycle ran every leg on a fixed budget
regardless (Tier-1 B11/B27). This is the smallest true authority: a budgeted leg asks here for
its seconds, and the answer is the leg's base budget scaled by the bandit's current share of the
arms that leg serves against those arms' equal-share baseline, clipped to [FLOOR, CEIL] so a
noisy share can neither starve a leg nor let it run away. Every answer is recorded in
reports/RESEARCH_BUDGET.json with the arms and the share behind it, and `research_bandit` reads
that record back to say whether it was authoritative this hour -- the claim is made by the
organ that OBEYED, never by the one that priced.

An unreadable bandit report returns the base budget and records that it did, so the cycle never
stalls on a missing price and the attestation never reads an absence as authority.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
BANDIT = DESK / "reports" / "RESEARCH_BANDIT.json"
OUT = DESK / "reports" / "RESEARCH_BUDGET.json"
FLOOR, CEIL = 0.5, 2.0
#: Which bandit arms each budgeted leg serves. The baseline for a leg is the equal share of its
#: arms among all arms, so a leg scales up only when the bandit prices its arms above average.
LEG_ARMS: dict[str, tuple[str, ...]] = {
    "alpha_evolution": ("mutate_survivor", "combine_survivors", "new_mechanism"),
    "deepen": ("new_mechanism", "external_screen", "alt_data_hypothesis", "failure_derived"),
}


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ladder_factor(leg: str) -> float:
    """The breadth ladder's per-leg factor (research is paid in n_eff per compute-hour);
    1.0 when the ladder is unmeasured or unavailable."""
    try:
        import breadth_ladder
        return float(breadth_ladder.budget_factor(leg))
    except Exception:
        return 1.0


def _department_factor(leg: str) -> float:
    """The resource exchange's elastic factor for the leg's department (1.0 when unmeasured)."""
    try:
        import research_departments
        return float(research_departments.factor_for(leg))
    except Exception:
        return 1.0


def _archive_factor(leg: str) -> float:
    """The active ResearchOS variant's leg factor (research_os_archive.active_policy); 1.0 when
    the archive is absent or refuses its own policy -- the incumbent is every factor at 1.0."""
    try:
        import research_os_archive
        f = float(research_os_archive.leg_factor(leg))
        return f if 0.0 < f < 10.0 else 1.0
    except Exception:
        return 1.0


def budget_s(leg: str, base: float) -> tuple[int, dict[str, Any]]:
    """(seconds, record) for `leg`: base x (share of its arms / equal-share baseline), clipped."""
    bandit = _read(BANDIT)
    shares = bandit.get("shares") if isinstance(bandit.get("shares"), dict) else {}
    arms = LEG_ARMS.get(leg, ())
    rec: dict[str, Any] = {"leg": leg, "base_s": float(base), "arms": list(arms),
                           "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "bandit_at": bandit.get("generated_utc")}
    if not shares or not arms or not all(isinstance(shares.get(a), (int, float)) for a in arms):
        rec.update({"applied_s": int(base), "factor": 1.0, "applied": False,
                    "why": "bandit shares unreadable for these arms; base budget"})
        return int(base), rec
    share = float(sum(float(shares[a]) for a in arms))
    baseline = len(arms) / max(1, len(shares))
    ladder = _ladder_factor(leg)
    dept = _department_factor(leg)
    archive = _archive_factor(leg)
    factor = max(FLOOR, min(CEIL, (share / baseline if baseline > 0 else 1.0) * ladder * dept
                            * archive))
    applied = round(base * factor)
    rec.update({"share": round(share, 4), "baseline": round(baseline, 4),
                "ladder_factor": round(ladder, 3), "department_factor": round(dept, 3),
                "archive_factor": round(archive, 3),
                "factor": round(factor, 3), "applied_s": applied, "applied": True,
                "why": f"share {share:.3f} of arms {list(arms)} vs equal-share baseline "
                       f"{baseline:.3f} -> x{factor:.2f}, clipped to [{FLOOR}, {CEIL}]"})
    return applied, rec


def record(rec: dict[str, Any]) -> None:
    """Merge one leg's record into RESEARCH_BUDGET.json (per-leg, latest wins)."""
    doc = _read(OUT)
    legs: dict[str, Any] = dict(doc["legs"]) if isinstance(doc.get("legs"), dict) else {}
    legs[str(rec.get("leg"))] = rec
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "legs": legs,
           "rule": "a leg's seconds are the bandit's share of its arms against an equal-share "
                   "baseline, clipped; `applied` false means the base budget ran"}
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError:
        pass


def authority(max_age_h: float = 3.0) -> tuple[bool, str]:
    """Was the bandit obeyed recently? True when a fresh RESEARCH_BUDGET.json shows at least one
    leg that applied a bandit-derived budget."""
    import time as _time
    doc = _read(OUT)
    legs = doc.get("legs") if isinstance(doc.get("legs"), dict) else {}
    if not legs:
        return False, "no RESEARCH_BUDGET.json: no leg has asked the bandit for its budget"
    try:
        age_h = (_time.time() - OUT.stat().st_mtime) / 3600.0
    except OSError:
        return False, "RESEARCH_BUDGET.json unreadable"
    if age_h > max_age_h:
        return False, f"RESEARCH_BUDGET.json is {age_h:.1f}h old"
    applied = [f"{k}={v.get('applied_s')}s (x{v.get('factor')})" for k, v in legs.items()
               if isinstance(v, dict) and v.get("applied")]
    if not applied:
        return False, "every budgeted leg ran on its base budget (bandit shares unreadable)"
    return True, f"the hourly cycle spent by the bandit's shares: {', '.join(applied)}"
