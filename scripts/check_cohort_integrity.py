#!/usr/bin/env python3
"""FORWARD-COHORT INTEGRITY FENCE (L1.6) -- is every Stage-B bar computed against the REAL cohort?

WHY THIS FENCE EXISTS. The Holm cohort size `m` is, in the words of the module that owns it, "the
single most load-bearing integer on the desk's only path from research to capital": the forward bar
is fixed for life only while `m` is counted correctly, and `m` is the ONLY multiplicity the
two-stage law recognises. It had no test and no fence, and it was being counted by four different
files that disagreed.

WHAT IT COST, measured 2026-08-05. scripts/run_axis_shadows.py charged its clocks
`holm_bar(len(_AXES))` = holm_bar(3) = 2.13 while eleven forward clocks were accruing concurrently,
whose correct bar is holm_bar(11) = 2.61. That is alpha 0.0167 per clock against a designed 0.0045
-- a family-wise error rate 3.67x the design, running in the PHANTOM-EDGE direction, because
UNDERSTATING m LOOSENS THE BAR. No clock had yet landed in the exposed band [2.13, 2.61), so the
trap had not fired; it was live and loaded, and the next lucky t-stat in that band would have been
promoted to ELIGIBLE on evidence the law says is insufficient. slot_registry's own docstring records
that three deep sweeps (2026-07-26/28/29) each found this and each carried it; this is the fourth
finding and the first fix.

THE ASYMMETRY THIS FENCE ENCODES. Over-counting m costs a real edge a few extra days of clock.
Under-counting m admits noise as edge and sizes capital on it. Those are not symmetric, so every
ambiguous state here resolves toward the tighter bar and every degraded state is LOUD.

STATUS (exit 2 on everything except OK -- a gate, not a report):
  NO-DATA        the registry cannot be read at all; there is no cohort to check.
  UNMEASURED     artifacts exist but none records the `m` it used -- never reads as fine (L1.28a).
  BAR-TOO-LOOSE  an artifact was judged against m BELOW the true cohort, so its bar is looser than
                 the law requires. WORST status: this is the direction that manufactures edge.
  COHORT-INCOMPLETE  a cohort source is unreadable, so m is a LOWER bound. Bars are floored at the
                 law cap meanwhile, but the desk is flying on a floor rather than a measurement.
  DIVERGENT      a consumer's slot count disagrees with the registry without loosening a bar (the
                 idleness/bottleneck reporting shape -- wrong, but not edge-manufacturing).
  OK             every bar site and every consumer agrees with libs.research.slot_registry.

THE ONE THING THIS FENCE MAY NEVER DO is report OK because it found nothing to compare. An absent
registry, an artifact with no recorded m, and a cohort with an unreadable source all rank ABOVE OK.

Pure stdlib -- deliberately. `holm_bar` lives in a module that imports numpy, and a fence that a
missing dependency can silence is not a fence, so the threshold is recomputed here from
NormalDist and CROSS-CHECKED against the real implementation whenever that is importable.

    python scripts/check_cohort_integrity.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Artifacts that record the cohort size they were judged against, and the field carrying it.
#: An artifact here that carries NO m is UNMEASURED, never assumed correct.
_BAR_ARTIFACTS: dict[str, str] = {
    "web/axis_shadows.json": "m_concurrent",
    "data/axis_shadow_state.json": "m_concurrent",
}

#: Consumers that report cohort OCCUPANCY. Wrong numbers here do not loosen a bar, but they steer
#: the desk's bottleneck ranking -- meta_research_review reported 12 free slots against 1 actual.
_OCCUPANCY_ARTIFACTS: dict[str, tuple[str, str]] = {
    "data/meta_research_review.json": ("alpha_lifecycle", "forward_slots_in_use"),
}

def _is_holm_bar(fn: ast.expr) -> bool:
    return ((isinstance(fn, ast.Name) and fn.id == "holm_bar")
            or (isinstance(fn, ast.Attribute) and fn.attr == "holm_bar"))


def _local_holm_bar(m: int, rank: int = 1, alpha: float = 0.05) -> float:
    """Holm step-down one-sided t threshold, recomputed in stdlib so no import can silence us."""
    m, rank = max(1, int(m)), max(1, int(rank))
    adj = alpha / max(1, m - min(rank, m) + 1)
    return round(NormalDist().inv_cdf(1.0 - adj), 2)


def _read_json(rel: str) -> Any | None:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _scan_bad_bar_sites() -> tuple[list[str], list[str]]:
    """(offending call sites, unparseable files) -- `holm_bar(len(...))` as CODE, via the AST.

    Deliberately not a regex. The first cut of this fence grepped the source text and promptly
    flagged its own docstring, plus slot_registry's, for QUOTING the defect while explaining it --
    a fence that fires on the documentation of the bug it prevents is a fence someone switches
    off, which is the substring-whitelist failure this desk has already had to cut once. The AST
    sees calls, so prose describing `holm_bar(len(_AXES))` is invisible to it and a real call is
    not, which is the only discrimination that matters here.
    """
    hits: list[str] = []
    unparseable: list[str] = []
    for path in sorted((_ROOT / "scripts").glob("*.py")) + sorted((_ROOT / "libs").rglob("*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        rel = path.relative_to(_ROOT)
        try:
            # utf-8-SIG: a byte-order mark decodes to a literal U+FEFF under plain utf-8 and
            # SyntaxErrors the parse, which is how scripts/research_memory.py -- a script the
            # universal duty set makes mandatory -- was invisible to every AST tool on this desk
            # while importing perfectly (CPython's loader strips the BOM; ast.parse does not).
            tree = ast.parse(path.read_text("utf-8-sig"))
        except (OSError, SyntaxError, ValueError):
            # Cannot parse => cannot rule the defect out. Surfaced, never silently skipped.
            unparseable.append(str(rel))
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and _is_holm_bar(node.func) and node.args
                    and isinstance(node.args[0], ast.Call)
                    and isinstance(node.args[0].func, ast.Name)
                    and node.args[0].func.id == "len"):
                hits.append(f"{rel}:{node.lineno}")
    return hits, unparseable


def build_report(now: datetime | None = None) -> dict[str, Any]:
    """Pure: compare every bar site and consumer against the registry. No writes -- tests call
    this directly rather than through the fence's side effects."""
    now = now or datetime.now(tz=UTC)

    registry_error: str | None = None
    m_true = cap = 0
    complete = False
    unknown: list[str] = []
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, cohort_m_for_bar, derive_slots
        snap = derive_slots()
        cohort = cohort_m_for_bar()
        m_true, cap = int(cohort.m), int(MAX_FORWARD_SLOTS)
        complete = bool(snap["complete"])
        unknown = [str(u) for u in (snap.get("unknown_sources") or [])]
        provenance, detail = cohort.provenance, cohort.detail
    except (ImportError, OSError, ValueError, KeyError, TypeError) as exc:
        registry_error = f"{type(exc).__name__}: {exc}"
        provenance, detail = "REFUSED", registry_error

    # Cross-check the local threshold against the shipped implementation where importable. A
    # divergence here would mean this fence is measuring against a bar the desk does not use.
    bar_check = "not-importable"
    if m_true:
        try:
            from libs.validation.forward_stats import holm_bar as _shipped
            bar_check = ("agrees" if abs(float(_shipped(m_true, rank=1))
                                         - _local_holm_bar(m_true)) < 1e-9 else "DIVERGES")
        except (ImportError, OSError, ValueError):
            bar_check = "not-importable"

    too_loose: list[dict[str, Any]] = []
    divergent: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    checked = 0

    for rel, field in _BAR_ARTIFACTS.items():
        doc = _read_json(rel)
        if not isinstance(doc, dict):
            unmeasured.append(f"{rel} (missing or unreadable)")
            continue
        raw = doc.get(field)
        if not isinstance(raw, int):
            # Fall back to the per-row m the axis runner writes on each result.
            rows = doc.get("axes") if isinstance(doc.get("axes"), list) else []
            found = [r.get(field) for r in rows
                     if isinstance(r, dict) and isinstance(r.get(field), int)]
            raw = found[0] if found else None
        if not isinstance(raw, int):
            unmeasured.append(f"{rel} (records no `{field}`)")
            continue
        checked += 1
        if m_true and raw < m_true:
            too_loose.append({
                "artifact": rel, "m_used": raw, "m_true": m_true,
                "bar_used": _local_holm_bar(raw), "bar_required": _local_holm_bar(m_true),
                "why": (f"judged against m={raw} when {m_true} clocks were accruing -- bar "
                        f"{_local_holm_bar(raw)} against a required {_local_holm_bar(m_true)}, "
                        f"alpha {0.05 / max(raw, 1):.4f}/clock against a designed "
                        f"{0.05 / max(m_true, 1):.4f}")})
        elif m_true and raw != m_true:
            divergent.append({"artifact": rel, "m_used": raw, "m_true": m_true,
                              "why": "over-counted -- tighter than required, the safe direction"})

    for rel, (section, field) in _OCCUPANCY_ARTIFACTS.items():
        doc = _read_json(rel)
        if not isinstance(doc, dict):
            unmeasured.append(f"{rel} (missing or unreadable)")
            continue
        sec = doc.get(section)
        used = sec.get(field) if isinstance(sec, dict) else None
        if used is None:
            # An explicit UNMEASURED from the producer is CORRECT behaviour, not a defect.
            if isinstance(sec, dict) and sec.get("provenance") == "UNMEASURED":
                continue
            unmeasured.append(f"{rel} ({section}.{field} absent)")
            continue
        checked += 1
        if m_true and int(used) != m_true:
            divergent.append({
                "artifact": rel, "m_used": int(used), "m_true": m_true,
                "why": (f"reports {int(used)} slots in use and "
                        f"{max(0, cap - int(used))} free against the registry's {m_true} -- this "
                        "feeds record_desk_metrics and the bottleneck ranking")})

    bad_sites, unparseable = _scan_bad_bar_sites()
    unmeasured.extend(f"{p} (unparseable -- cannot rule out a local bar)" for p in unparseable)

    # ---- STATUS -- worst first; every empty-input case ranks ABOVE OK (L1.28a) --------------
    if registry_error is not None:
        status = "NO-DATA"
        detail_msg = (f"slot registry unusable ({registry_error}) -- there is no cohort to check "
                      "and every Stage-B bar is running on an unverifiable m")
    elif checked == 0:
        status = "UNMEASURED"
        detail_msg = (f"registry reports m={m_true} but no artifact records the m it used "
                      f"({'; '.join(unmeasured[:4])}) -- nothing could be compared")
    elif bad_sites:
        status = "BAR-TOO-LOOSE"
        detail_msg = (f"{len(bad_sites)} site(s) recompute a Holm bar from a local len() instead "
                      f"of the registry: {', '.join(bad_sites[:4])} -- this is the exact shape "
                      "that ran the axis clocks at 3.67x their designed error rate")
    elif too_loose:
        w = too_loose[0]
        status = "BAR-TOO-LOOSE"
        detail_msg = (f"{w['artifact']} judged at m={w['m_used']} (bar {w['bar_used']}) against a "
                      f"true cohort of {w['m_true']} (bar {w['bar_required']}) -- a t-stat in "
                      f"[{w['bar_used']}, {w['bar_required']}) would be promoted on evidence the "
                      "two-stage law says is insufficient")
    elif not complete:
        status = "COHORT-INCOMPLETE"
        detail_msg = (f"{len(unknown)} cohort source(s) unreadable ({', '.join(unknown[:3])}) -- "
                      f"m={m_true} is a LOWER bound, floored at the cap {cap}; bars are safe but "
                      "the desk is flying on a floor rather than a measurement")
    elif unmeasured:
        status = "UNMEASURED"
        detail_msg = (f"{len(unmeasured)} artifact(s) record no cohort size: "
                      f"{'; '.join(unmeasured[:4])}")
    elif divergent:
        d = divergent[0]
        status = "DIVERGENT"
        detail_msg = (f"{d['artifact']} reports m={d['m_used']} against the registry's "
                      f"{d['m_true']} -- {d['why']}")
    else:
        status = "OK"
        detail_msg = (f"{checked} bar site(s) and consumer(s) all agree with the registry at "
                      f"m={m_true} (bar {_local_holm_bar(m_true)}), every source readable")

    return {
        "generated": now.isoformat(),
        "law": ("L1.6 -- the forward confirmation bar is fixed for life, which is only true while "
                "the concurrent cohort m is counted correctly; understating m loosens every bar "
                "and is the phantom-edge direction"),
        "status": status,
        "detail": detail_msg,
        "m_true": m_true,
        "m_provenance": provenance,
        "m_detail": detail,
        "cap": cap,
        "cohort_complete": complete,
        "unknown_sources": unknown,
        "required_bar": _local_holm_bar(m_true) if m_true else None,
        "shipped_bar_crosscheck": bar_check,
        "artifacts_checked": checked,
        "too_loose": too_loose,
        "divergent": divergent,
        "unmeasured": unmeasured,
        "local_bar_sites": bad_sites,
        "next_action": (
            "Restore libs/research/slot_registry.py -- no Stage-B bar can be trusted without it"
            if status == "NO-DATA" else
            "Make the bar sites record the `m_concurrent` they used, so the bar they applied is "
            "auditable from its own artifact rather than inferred from source"
            if status == "UNMEASURED" else
            "Route the named site(s) through slot_registry.cohort_m_for_bar(); a Holm bar computed "
            "from a local len() charges the desk's multiplicity to one script's roster"
            if status == "BAR-TOO-LOOSE" else
            "Fix the unreadable cohort source(s) -- until then every bar is floored at the cap, "
            "which is safe but costs real candidates clock time"
            if status == "COHORT-INCOMPLETE" else
            "Point the named consumer at slot_registry; its slot count steers the bottleneck "
            "ranking and record_desk_metrics"
            if status == "DIVERGENT" else
            "Hold. Next: wire the five inert `FAILING FORWARD -> kill` verdicts to a reader so a "
            "dead clock VACATES its seat instead of taxing every neighbour's bar forever"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/cohort_integrity_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"cohort integrity (L1.6): {rep['status']} -- {rep['detail']}")
        print(f"  m={rep['m_true']} [{rep['m_provenance']}] cap={rep['cap']} "
              f"bar={rep['required_bar']} complete={rep['cohort_complete']} "
              f"checked={rep['artifacts_checked']} crosscheck={rep['shipped_bar_crosscheck']}")
        for t in rep["too_loose"]:
            print(f"    TOO-LOOSE {t['artifact']}: {t['why']}")
        for d in rep["divergent"]:
            print(f"    DIVERGENT {d['artifact']}: {d['why']}")
        for u in rep["unmeasured"]:
            print(f"    UNMEASURED {u}")
        for s in rep["local_bar_sites"]:
            print(f"    LOCAL-BAR {s}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 0 if rep["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
