#!/usr/bin/env python3
"""THE BREADTH-ENFORCER FENCE -- saturated families stay at their floor, the unknown get mined.

    "make sure the breadth mining discovering enforcer 24/7 is working where families or saturated
     things already like 10 families currently in certies don't get mined n unknowns r forced to be
     mined instead"                                               -- the principal, 2026-10-13

Reads `desks/mt5/reports/BREADTH_ENFORCER.json`, which `research/breadth_enforcer.py` writes every
hour, and FAILS when the mining share drifts:

  * JUDGE HOUR (judge_coverage quota, the docket order every producer's rows ship in): the
    saturated share above its bound plus `SHARE_TOLERANCE`, or the frontier / unknown share below
    its target minus the tolerance. Bounds are work-conserving and come from what the backlog can
    supply -- a target the frontier's own backlog cannot fill is a minting debt, never a failure.
  * SEALED JUDGE (the gauntlet's yield split and its verdicts): the same test, ENFORCED once the
    sealed patch is in force (`steer_in_force`). Before that it prints the measured drift as a
    loud WARN naming the patch -- failing every gate on code no branch may edit would only teach
    the desk to switch the fence off.
  * MINT, per producer: a producer whose head `apportion()` guarantees (`mint_enforced`) whose
    saturated share passes the floor plus tolerance FAILS. Every other producer is named with its
    share as a WARN, with the reason it is not steered yet.

PORTABLE BY DEFAULT: no report reads UNMEASURED and passes. `--require-state` (the box half, in
`run_law_gate._STATE_FENCES`): an absent, stale or unmeasured report is a FAILURE -- the enforcer
stopping is exactly the silent drift this fence exists for.

    python scripts/check_breadth_enforcer.py [--require-state] [--report PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from libs.ops.fence_exit import fence_exit

_PASSING = frozenset({"OK", "UNMEASURED"})

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "desks" / "mt5" / "reports" / "BREADTH_ENFORCER.json"
STALE_H = 6.0
DEFAULT_TOLERANCE = 0.05
PATCH = "patches/breadth_enforcer_judge_yield.patch"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _age_h(stamp: object, now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return max(0.0, (now - at).total_seconds() / 3600.0)


def _drift(name: str, s: Mapping[str, Any], b: Mapping[str, Any], tol: float) -> list[str]:
    """The drift reasons for one measured share block against its bounds; [] when inside."""
    if s.get("status") != "MEASURED" or not b:
        return []
    out: list[str] = []
    sat, smax = float(s.get("saturated_share") or 0.0), float(b.get("saturated_max", 1.0))
    if sat > smax + tol:
        out.append(f"{name}: saturated share {sat:.3f} > floor {smax:.3f} + {tol:.2f}")
    fr, fmin = float(s.get("frontier_share") or 0.0), float(b.get("frontier_min", 0.0))
    if fr < fmin - tol:
        out.append(f"{name}: frontier share {fr:.3f} < target {fmin:.3f} - {tol:.2f}")
    un, umin = float(s.get("unknown_share") or 0.0), float(b.get("unknown_min", 0.0))
    if un < umin - tol:
        out.append(f"{name}: unknown share {un:.3f} < target {umin:.3f} - {tol:.2f}")
    return out


def judge(report: Path | None = None, *, require_state: bool = False,
          now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    doc = _read(report or REPORT)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "checks": [],
                           "failures": [], "warnings": []}
    fail, warn, checks = out["failures"], out["warnings"], out["checks"]
    if not isinstance(doc, dict):
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        why = "BREADTH_ENFORCER.json absent or unreadable"
        (fail if require_state else warn).append(why)
        return out
    age = _age_h(doc.get("generated_utc"), at)
    out["report_age_h"] = round(age, 2) if age is not None else None
    if require_state and (age is None or age > STALE_H):
        fail.append(f"report stale: {age if age is None else round(age, 1)}h > {STALE_H}h -- "
                    "the enforcer stopped")
    steer = doc.get("steer") or {}
    if steer.get("status") != "MEASURED":
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        (fail if require_state else warn).append(f"steer UNMEASURED: {steer.get('why')}")
        return out
    tol = float((steer.get("params") or {}).get("share_tolerance") or DEFAULT_TOLERANCE)
    floor = float((steer.get("params") or {}).get("sat_explore_share") or 0.10)
    out["saturated"] = steer.get("saturated")

    # 1. THE JUDGE HOUR -- enforced.
    j = doc.get("judge") or {}
    shipped = j.get("shipped") or {}
    reasons = _drift("judge hour", shipped, j.get("bounds") or {}, tol)
    fail.extend(reasons)
    checks.append({"metric": "judge_hour_share", "state": "FAIL" if reasons else (
        "OK" if shipped.get("status") == "MEASURED" else "UNMEASURED"),
        "shipped": shipped, "bounds": j.get("bounds"), "steer_in_force": j.get("steer_in_force")})
    if shipped.get("status") == "MEASURED" and not j.get("steer_in_force"):
        warn.append("judge_coverage's last hour ran WITHOUT the steer (first hour, or the steer "
                    "was stale when it ran)")

    # 2. THE SEALED JUDGE -- enforced once the patch is in force, a loud WARN until then.
    g = doc.get("gauntlet") or {}
    v = doc.get("verdicts") or {}
    g_reasons = _drift("gauntlet build split", g.get("built") or {}, g.get("bounds") or {}, tol)
    v_reasons = _drift("sealed-judge verdicts", v, g.get("bounds") or {
        "saturated_max": floor, "frontier_min": 0.0, "unknown_min": 0.0}, tol)
    if g.get("steer_in_force"):
        fail.extend(g_reasons + v_reasons)
    else:
        warn.extend(f"{r} [SEALED, pending {PATCH}]" for r in g_reasons + v_reasons)
    checks.append({"metric": "sealed_judge_share",
                   "state": ("FAIL" if g.get("steer_in_force") and (g_reasons or v_reasons)
                             else "WARN" if (g_reasons or v_reasons) else "OK"),
                   "gauntlet": g.get("built"), "verdicts": {k: v.get(k) for k in (
                       "n", "saturated_share", "frontier_share", "unknown_share", "basis")},
                   "steer_in_force": bool(g.get("steer_in_force"))})

    # 3. MINT, per producer.
    m = doc.get("mint") or {}
    enforced = set(doc.get("mint_enforced") or [])
    heavy: list[str] = []
    for name, s in (m.get("producers") or {}).items():
        if not isinstance(s, dict) or s.get("status") != "MEASURED":
            continue
        sat = float(s.get("saturated_share") or 0.0)
        if name in enforced and sat > floor + tol:
            fail.append(f"mint {name}: saturated share {sat:.3f} > floor {floor:.2f} + {tol:.2f}")
        elif sat > floor + tol:
            heavy.append(f"{name} {sat:.2f} (n={s.get('n')})")
    if heavy:
        warn.append("producers minting saturated ground above the floor, not yet steered: "
                    + ", ".join(heavy[:12]))
    checks.append({"metric": "mint_share", "state": "OK" if m.get("status") == "MEASURED"
                   else "UNMEASURED", "all_producers": m.get("all_producers"),
                   "enforced": sorted(enforced), "basis": m.get("basis")})

    # 3b. RESIDUAL / RV BASKETS (GAP_MAP L5): the apportioned docket head may not hold MORE
    # saturated ground (same-class baskets included) than both the floor and what the producer's
    # own order already gave it -- the steer can only redirect toward cross-class baskets.
    bd = (doc.get("baskets") or {}).get("docket") or {}
    heads = sorted(k for k in bd if k.startswith("head_") and k.endswith("_before"))
    for kb in heads:
        ka = kb[: -len("_before")] + "_after"
        hb, ha = bd.get(kb) or {}, bd.get(ka) or {}
        sb, sa_ = float(hb.get("saturated_share") or 0.0), float(ha.get("saturated_share") or 0.0)
        if sa_ > max(floor, sb) + tol:
            fail.append(f"baskets {ka}: saturated share {sa_:.3f} > max(floor {floor:.2f}, "
                        f"before {sb:.3f}) + {tol:.2f} -- same-class residual/RV ground grew")
        owed = float(bd.get("forced_first_owed_share") or 0.0)
        got = float(ha.get("forced_first_share") or 0.0)
        if owed and got < owed - tol:
            fail.append(f"baskets {ka}: forced-first share {got:.3f} < owed {owed:.3f} - "
                        f"{tol:.2f} -- {', '.join(bd.get('forced_first_tags') or [])} markets "
                        "not mined first")
    if bd.get("status") == "MEASURED":
        checks.append({"metric": "residual_rv_baskets", "state": "OK",
                       "same_class": bd.get("same_class"), "cross_class": bd.get("cross_class"),
                       "certified": (doc.get("baskets") or {}).get("certified")})

    # 4. TOTAL NEVER REDUCED -- the replay must hand out exactly what the legacy walk did.
    tl, ts = j.get("total_cells_legacy"), j.get("total_cells_steered")
    if isinstance(tl, int) and isinstance(ts, int) and ts < tl:
        fail.append(f"judge replay REDUCED mining: {ts} < {tl} cells -- the steer must only "
                    "redirect")
    out["verdict"] = "FAIL" if fail else "OK"
    return out


def render(doc: Mapping[str, Any]) -> list[str]:
    lines = [f"breadth enforcer fence: {doc.get('verdict')}  (saturated: "
             f"{', '.join(doc.get('saturated') or []) or '-'})"]
    lines += [f"  FAIL  {r}" for r in doc.get("failures") or []]
    lines += [f"  WARN  {r}" for r in doc.get("warnings") or []]
    for c in doc.get("checks") or []:
        lines.append(f"  {c.get('state'):10s} {c.get('metric')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--require-state", action="store_true",
                    help="box mode: an absent, stale or unmeasured report is a FAILURE")
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = judge(Path(a.report) if a.report else None, require_state=bool(a.require_state))
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print("\n".join(render(doc)))
    # R0237: the PASSING set is named, everything else fails. UNMEASURED passes only in the
    # portable mode, where an absent report is the documented UNMEASURED-and-pass; the box mode
    # (--require-state) already turns it into FAIL inside judge().
    return fence_exit(doc["verdict"], _PASSING, fail=1)


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
