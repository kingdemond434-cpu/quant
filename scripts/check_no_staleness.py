"""THE ANTI-STALENESS FENCE -- every artifact the desk publishes has an expected refresh
interval, and an artifact past it is a DEFECT with a name, a clock and a last exit.

    "make sure nothing is stale" (principal, 2026-09-22)

The desk publishes ~300 artifacts from ~1200 components. Each organ reports on itself, so an
organ that stopped a week ago keeps its last report on disk saying exactly what it said when it
was healthy. NOTHING reads the whole set and asks "is this still true?". That is what this is.

WHERE THE EXPECTATION COMES FROM, in order, and the answer is RECORDED either way:

  1. the artifact's LEASE -- `libs/ops/control_plane/lease.py` stamps a `valid_until` into an
     envelope beside the file, from `TTL_BY_CLASS[spec.artifact_class]`. A lease is the desk's
     own law about freshness and beats every inference.
  2. the component registry's CLASS -- `desks/mt5/ops/components.py` declares `artifact_class`
     per spec; `TTL_BY_CLASS` turns it into seconds. Used when the file carries no envelope.
  3. DERIVED FROM THE CLOCK -- two cadences of the organ's own leg (the standing rule: one
     missed pass is a hiccup, two is a stop). Every derivation lands in the report under
     `derived_expectations`, so an expectation that did not exist before this ran now exists
     and is visible, which is the brief's requirement.
  4. nothing -- UNMEASURED. NEVER a pass: it is counted, listed and named, because an artifact
     nobody declared a cadence for is a governance hole, not a healthy file (L1.28a).

HOSTS ARE MEASURED, NOT ASSUMED. The host detector is `loop_liveness.host_facts()` -- ONE
detector for both organs, not two that can disagree. A spec declared `host="box"` is judged only
on a trading box whose MT5 clocks are actually ENABLED; a `host="vps"` spec only on the VPS.
Everywhere else it is UNMEASURED with the host named, because a build box's copy of a gateway
artifact is legitimately old and calling it stale would train the desk to ignore this report.

REPAIRS GO THROUGH THE RECONCILER THAT ALREADY EXISTS. The principal's law is "stop adding
independent fixers", and `libs/ops/control_plane/reconciler.py` already treats STALE as a
`BROKEN_STATE` and plans an actuator for it. This fence therefore calls that module's PUBLIC
API -- `observe()` on the specs that own stale artifacts, `plan()` over those observations, and
with `--apply` on the box `apply_plan()` -- and records what the reconciler decided. It contains
no repair logic of its own and never restarts anything itself.

Exit: 2 on a ratchet breach or a stale REQUIRED artifact; 1 on stale optional artifacts;
0 clean. Artifact: desks/mt5/reports/NO_STALENESS.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "NO_STALENESS.json"

#: THE RATCHET, MEASURED, NEVER GUESSED. The number of artifacts judged STALE on the host this
#: was last measured on. It may only be LOWERED, and lowering it is the point of the organ: a
#: run that measures fewer stale artifacts prints the number to put here. A run that measures
#: MORE fails the gate (exit 2), which is how new staleness is caught the hour it appears.
#: 2026-09-23, host `box_clocks_off` (VMI3500897): see the report's `measured_for_ratchet`.
MAX_STALE = 12

#: Seconds. A stage is fresh while its newest write is inside this many cadences of its clock.
#: Two, for the same reason `lease.TTL_BY_CLASS["hourly"]` is 7200 against a 3600 s leg.
STALL_CADENCES = 2.0

FRESH, STALE, MISSING, UNMEASURED = "FRESH", "STALE", "MISSING", "UNMEASURED"

#: A path-shaped token: `a/b/NAME.ext`. The registry's `outputs` are derived from source, so some
#: carry a trailing note ("...ADVERSARY.json gate_detail") or a `(file.py:1605-1606)` citation.
#: Parsing tolerantly is correct here: the alternative is to edit components.py, which belongs to
#: another builder, and a fence that needs its input rewritten is a fence that never runs.
_PATHISH = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.(?:json|jsonl|csv|parquet|md|txt|sqlite|npz)")


def artifact_paths(spec: Any) -> tuple[str, ...]:
    """Repo-relative artifact paths a spec claims to OWN, parsed out of its `outputs`."""
    out: list[str] = []
    for raw in getattr(spec, "outputs", ()) or ():
        for m in _PATHISH.findall(str(raw)):
            if m not in out:
                out.append(m)
    return tuple(out)


# ------------------------------------------------------------------------------------- hosts
def measurable_here(spec_host: str, here: str) -> tuple[bool, str]:
    """Can this host judge a spec declared for `spec_host`? MEASURED, never assumed."""
    h = str(spec_host or "any")
    if h == "any":
        return True, ""
    if h == "box":
        if here == "trading_box":
            return True, ""
        return False, (f"owned by a `box` component; this host is `{here}`, where the box's "
                       f"clocks are not running it -- old here is not stale")
    if h == "vps":
        if here == "vps":
            return True, ""
        return False, (f"owned by a `vps` component; this host is `{here}` and never runs it -- "
                       f"this checkout's copy is a mirror, not the artifact")
    return True, ""


# ------------------------------------------------------------------------------ expectations
def expectation(spec: Any, ttl_by_class: Mapping[str, int]) -> tuple[int | None, str]:
    """(seconds, how it was derived). None = UNMEASURED, which is a verdict, never a pass."""
    cls = str(getattr(spec, "artifact_class", "") or "")
    if cls and cls in ttl_by_class:
        return int(ttl_by_class[cls]), f"class `{cls}` -> lease.TTL_BY_CLASS"
    cadence = getattr(spec, "cadence_s", None)
    if cadence:
        return (int(float(cadence) * STALL_CADENCES),
                f"DERIVED: {STALL_CADENCES:g} x the {int(cadence)}s cadence of "
                f"`{getattr(spec, 'schedule', UNMEASURED)}` (no artifact_class declared)")
    silence = getattr(spec, "max_silence_s", None)
    if silence:
        return int(silence), "DERIVED: the component's declared max_silence_s"
    return None, (f"`{getattr(spec, 'component_id', '?')}` declares neither an artifact_class "
                  f"nor a cadence -- UNMEASURED, which is a governance hole, not a pass")


# ---------------------------------------------------------------------------------- freshness
def _stamp_age(path: Path, now: float) -> tuple[float | None, str]:
    """(age in seconds, where the stamp came from). Prefers the document's own stamp."""
    if path.suffix == ".json":
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            doc = None
        if isinstance(doc, dict):
            for key in ("at", "generated_at", "generated", "swept_at", "measured_at",
                        "updated_at", "built_at"):
                raw = doc.get(key)
                if not raw:
                    continue
                try:
                    t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                except ValueError:
                    continue
                t = t if t.tzinfo else t.replace(tzinfo=UTC)
                return max(0.0, now - t.timestamp()), f"document field `{key}`"
    try:
        return max(0.0, now - path.stat().st_mtime), "mtime (no lease, no stamp field)"
    except OSError:
        return None, "unreadable"


def judge(rel: str, spec: Any, *, root: Path, now: float, here: str,
          ttl_by_class: Mapping[str, int], lease: Any) -> dict[str, Any]:
    """One artifact's verdict, with the organ, its clock and its expectation attached."""
    row: dict[str, Any] = {
        "artifact": rel,
        "organ": getattr(spec, "component_id", UNMEASURED),
        "clock": getattr(spec, "schedule", UNMEASURED),
        "criticality": getattr(spec, "criticality", "optional"),
        "component_host": getattr(spec, "host", "any"),
        "measured_on": here,
        "restart_action": getattr(spec, "restart_action", UNMEASURED),
    }
    ok_here, why_host = measurable_here(row["component_host"], here)
    exp_s, exp_why = expectation(spec, ttl_by_class)
    row["expected_refresh_s"] = exp_s
    row["expectation_from"] = exp_why
    row["derived"] = exp_why.startswith("DERIVED")

    p = root / rel
    if not p.exists():
        row.update(verdict=(UNMEASURED if not ok_here else MISSING),
                   age_s=None, stamp="absent",
                   why=(why_host or f"{rel} does not exist; its organ has never published here"))
        return row
    age, stamp = _stamp_age(p, now)

    # THE LEASE WINS WHERE THERE IS ONE: it is the desk's own declaration about this file.
    leased: bool | None = None
    if lease is not None:
        try:
            env = lease.read_envelope(p)
            if env is not None:
                leased = lease.valid(env, datetime.fromtimestamp(now, tz=UTC))
                stamp = "lease envelope"
        except (OSError, ValueError, TypeError):  # pragma: no cover - defensive
            leased = None
    row["age_s"] = None if age is None else round(age, 1)
    row["stamp"] = stamp
    if not ok_here:
        row.update(verdict=UNMEASURED, why=why_host)
        return row
    if leased is not None:
        row.update(verdict=FRESH if leased else STALE,
                   why=("inside its lease" if leased else "its freshness lease has expired"))
        return row
    if exp_s is None or age is None:
        row.update(verdict=UNMEASURED, why=exp_why if age is not None else "unreadable stamp")
        return row
    if age <= exp_s:
        row.update(verdict=FRESH,
                   why=f"{age / 3600.0:.1f}h old against a {exp_s / 3600.0:.1f}h expectation")
        return row
    row.update(verdict=STALE,
               why=(f"{age / 3600.0:.1f}h old against a {exp_s / 3600.0:.1f}h expectation "
                    f"({exp_why}); clock `{row['clock']}`"))
    return row


# --------------------------------------------------------------- repairs, via the reconciler
def raise_repairs(stale: Sequence[Mapping[str, Any]], registry: Any, *, apply: bool = False,
                  budget_s: float = 120.0, root: Path | None = None,
                  reconciler: Any = None, **observe_kw: Any) -> dict[str, Any]:
    """Hand every stale artifact's OWNER to the reconciler that already exists.

    NO REPAIR LOGIC LIVES HERE, by the principal's standing order. `reconciler.observe()` decides
    the component's state (it already treats an expired output lease as STALE, and STALE is
    already in its `BROKEN_STATES`), `reconciler.plan()` turns that into actuator work, and
    `apply_plan()` -- only with --apply, only on the box -- runs it and proves the postcondition.
    This function's whole job is routing: which specs to hand over, and recording the answer.
    """
    if reconciler is None:
        from libs.ops.control_plane import reconciler as reconciler_mod
        reconciler = reconciler_mod
    ids: list[str] = []
    for r in stale:
        cid = str(r.get("organ") or "")
        if cid and cid not in ids:
            ids.append(cid)
    specs = [s for s in (registry.get(cid) for cid in ids) if s is not None]
    if not specs:
        return {"observed": 0, "planned": [], "applied": [], "mode": "none",
                "why": "no stale artifact maps to a component the registry knows"}
    obs = [reconciler.observe(s, root=root, **observe_kw) for s in specs]
    work = reconciler.plan(obs, registry)
    applied: list[dict[str, Any]] = []
    if apply and work:
        applied = list(reconciler.apply_plan(work, registry, budget_s=budget_s))
    return {"observed": len(obs), "components": ids,
            "states": {o.component_id: o.state for o in obs},
            "planned": [dict(w) for w in work], "applied": applied,
            "mode": "apply" if apply else "observe",
            "why": ("raised through libs/ops/control_plane/reconciler.py (observe -> plan"
                    + (" -> apply_plan)" if apply else "); --apply runs them on the box)")),
            }


# ------------------------------------------------------------------------------------ audit
def audit(root: Path | None = None, *, now: float | None = None, here: str | None = None,
          registry: Any = None, apply: bool = False, budget_s: float = 300.0,
          reconciler: Any = None) -> dict[str, Any]:
    base = root or ROOT
    t = now if now is not None else time.time()
    t0 = time.monotonic()
    from libs.ops.control_plane import lease

    if here is None:
        from desks.mt5.research.loop_liveness import host_facts
        facts = host_facts()
    else:
        facts = {"kind": here, "why": "host supplied by the caller"}
    where = str(facts["kind"])

    if registry is None:
        from desks.mt5.ops import components as comp
        registry = comp.registry(base)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for spec in registry.all():
        for rel in artifact_paths(spec):
            key = (str(getattr(spec, "component_id", "")), rel)
            if key in seen:
                continue
            seen.add(key)
            rows.append(judge(rel, spec, root=base, now=t, here=where,
                              ttl_by_class=lease.TTL_BY_CLASS, lease=lease))

    by_verdict: dict[str, int] = {}
    for r in rows:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    stale = [r for r in rows if r["verdict"] == STALE]
    stale.sort(key=lambda r: (r["criticality"] != "required", -(r.get("age_s") or 0)))
    required_stale = [r for r in stale if r["criticality"] == "required"]
    derived = [{"artifact": r["artifact"], "organ": r["organ"],
                "expected_refresh_s": r["expected_refresh_s"], "from": r["expectation_from"]}
               for r in rows if r.get("derived")]

    repairs: dict[str, Any] = {"mode": "skipped", "why": "no stale artifact on this host"}
    if stale:
        try:
            repairs = raise_repairs(stale, registry, apply=apply, budget_s=budget_s, root=base,
                                    reconciler=reconciler)
        except Exception as exc:  # the fence must report, never crash the law gate
            repairs = {"mode": "error", "why": f"{type(exc).__name__}: {exc}"}

    breach = len(stale) > MAX_STALE or bool(required_stale)
    return {
        "at": datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds"),
        "host": where, "host_why": facts.get("why"),
        "artifacts_judged": len(rows),
        "verdicts": by_verdict,
        "measured_for_ratchet": len(stale),
        "ratchet": MAX_STALE,
        "ratchet_breach": breach,
        "required_stale": [r["artifact"] for r in required_stale],
        "stale": stale[:200],
        "unmeasured": [{"artifact": r["artifact"], "organ": r["organ"], "why": r["why"]}
                       for r in rows if r["verdict"] == UNMEASURED][:200],
        "derived_expectations": derived,
        "repairs": repairs,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("every published artifact has an expected refresh interval -- from its lease, "
                 "else its declared class, else DERIVED from its clock's cadence and recorded "
                 "here; past it is a DEFECT named with its organ, clock and last exit. "
                 "UNMEASURED is a verdict, never a pass. Repairs are raised only through "
                 "libs/ops/control_plane/reconciler.py, never by a fixer of this fence's own."),
    }


def _print(doc: Mapping[str, Any], limit: int = 12) -> None:
    v = doc.get("verdicts") or {}
    print(f"no-staleness on {doc.get('host')}: {doc.get('artifacts_judged')} artifacts -- "
          f"{v.get(FRESH, 0)} FRESH, {v.get(STALE, 0)} STALE, {v.get(MISSING, 0)} MISSING, "
          f"{v.get(UNMEASURED, 0)} UNMEASURED (ratchet {doc.get('ratchet')})")
    for r in (doc.get("stale") or [])[:limit]:
        print(f"  STALE [{r['criticality']}] {r['artifact']} <- {r['organ']} "
              f"(clock {r['clock']}): {r['why']}")
    extra = len(doc.get("stale") or []) - limit
    if extra > 0:
        print(f"  ... and {extra} more in {REPORT.name}")
    rep = doc.get("repairs") or {}
    if rep.get("planned"):
        print(f"  reconciler {rep.get('mode')}: {len(rep['planned'])} repair(s) planned for "
              f"{', '.join(str(w.get('component_id')) for w in rep['planned'][:5])}")
    n = doc.get("measured_for_ratchet")
    if isinstance(n, int) and n < MAX_STALE:
        print(f"  RATCHET: lower MAX_STALE to {n} in scripts/check_no_staleness.py")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="let the reconciler RUN the repairs it plans (box only)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    a = ap.parse_args(list(argv) if argv is not None else None)
    doc = audit(apply=a.apply, budget_s=a.budget_s)
    out = a.report or REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        _print(doc)
    if doc["ratchet_breach"]:
        return 2
    return 1 if doc["verdicts"].get(STALE) else 0


if __name__ == "__main__":
    raise SystemExit(main())
