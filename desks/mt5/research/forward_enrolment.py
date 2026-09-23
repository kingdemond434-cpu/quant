"""FORWARD ENROLMENT -- every certificate gets a clock the moment it exists. No quota, ever.

THE PRINCIPAL'S ORDER (2026-09-23): "remove the slots being scarce by design permanently so as
many certis as possible can be put on forward clocks immediately, no quota or scarcity ever on
forward evidence slots."

WHY THE QUOTA WAS NEVER A RISK CONTROL, AND THIS IS THE WHOLE ARGUMENT. A forward clock GATHERS
EVIDENCE AND DEPLOYS NO CAPITAL. `shadow_forward` replays a certified recipe against bars the
desk already holds and writes an R series; nothing it does reaches the gateway, the allocator or
a lot size -- promotion to LIVE is a separate, certificate-gated act by `research/promoter.py`
(sealed). So a cap on ENROLMENT buys no safety at all: it only reduces the number of hypotheses
that can ever accumulate the out-of-sample evidence needed to rule on them. It is a pure loss of
evidence throughput, paid for in months of latency, and the desk has already measured what that
costs -- 33 runnable certificates passing every one of the ten gates and accruing no forward
evidence at all, "the whole promotion pipeline stalled behind a missing hourly call".

WHAT IS REMOVED, AND WHAT IS EXPLICITLY NOT. The SLOT QUOTA is removed: no cap, no waiting queue,
no ranking gate, no capacity file standing between a certificate and its clock.

  THE STATISTICS ARE UNTOUCHED, AND THEY ARE NOT A KNOB. Multiplicity, the Holm/BH cohort, the
  deflated-Sharpe charge and the effective-trial ledger stay EXACTLY as they are. Enrolling more
  clocks makes every clock's bar HARDER, automatically, because m rises -- that is the honest
  price of testing more, and it is paid in full. `libs.research.slot_registry.MAX_FORWARD_SLOTS`
  therefore stays as the cohort size the bar is computed at; what stops being read is its use as
  a SEAT COUNT. `libs.validation.family_multiplicity` and `libs.research.trial_ledger` are not
  edited by this organ and must not be: the immutable floor is never a knob.

  `forward_slot_ranker.py` STAYS, as a REPORT. Priority order, slot value, diversification and
  the missed-growth lines are real evidence about what to look at first. It never gated enrolment
  (its own docstring: "REPLACEABLE IS A REPORT, NEVER AN ACT") and it never will.

HOW ENROLMENT NOW HAPPENS, in two places that agree:

  1. AT CERTIFICATION. `shadow_forward.certified_sleeves()` reads `shadow_admission.
     authorized_runs` -- every certificate, unfiltered and uncapped -- and the engine stamps
     `enrolled_at` on the state row the first time it writes one. A certificate minted at 03:12
     is on a clock on the next pass with no human act and nothing to wait behind.
  2. THE REPAIR SWEEP, hourly, here. Anything that somehow lacks a clock -- a selector with no
     window mapping, a family whose constructor is missing, a pass that died -- is found by
     comparing `authorized_runs` against every lane's state file by canonical key
     (`shadow_admission.run_key`, the engine's own `sleeve_key`), REPORTED BY NAME WITH ITS
     REASON, and the enrolment engine is re-run inside the remaining budget.

Clock: leg `forward_enrolment` in `research/hourly_cycle.py` (department validate,
`--once --budget-s 300`). Artifact: `desks/mt5/reports/FORWARD_ENROLMENT.json`. Consumers:
`scripts/check_forward_enrolment.py` (a law gate that fails when a certificate has been clockless
for longer than one cycle, or when any code path re-introduces a cap) and the desk's own
forward-clock census.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW_DIR = BASE / "reports" / "shadow"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = BASE / "reports" / "FORWARD_ENROLMENT.json"
ENGINE = BASE / "research" / "shadow_forward.py"

UNMEASURED = "UNMEASURED"

#: Every lane whose state file holds forward clocks. A certificate is enrolled if ANY of them
#: carries its key: the scalp lane runs `scalp.*` rows and the external lane the rest, and a
#: census that looked in one file reported 34 of 35 certificates clockless while all 35 ran.
LANE_FILES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
              "external_shadow_state.json")

#: One cycle. A certificate clockless for longer than this is the defect the fence fails on --
#: the hourly cycle is what enrols, so one hour is exactly the time enrolment is allowed to take.
CYCLE_HOURS = 1.0

#: THE TARGET IS ZERO. Not a threshold to pass: the number the report exists to hold the desk to.
TARGET_LATENCY_H = 0.0


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def clock_rows(shadow_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every forward clock the desk holds, keyed by the engine's own `sleeve_key`.

    The FIRST lane that carries a key wins, which is only a tie-break for reporting: a key present
    in any lane is enrolled, and that is the question this organ asks.
    """
    out: dict[str, dict[str, Any]] = {}
    root = Path(shadow_dir or SHADOW_DIR)
    for name in LANE_FILES:
        doc = _read_json(root / name, {}) or {}
        if not isinstance(doc, dict):
            continue
        for key, row in doc.items():
            if isinstance(row, dict) and key not in out:
                out[key] = {**row, "lane": name}
    return out


def certification_stamps() -> dict[tuple[str, str, str, str], str]:
    """(symbol, family, selector, side) -> the canon's `gated_at` for that certificate.

    This is the moment the certificate came into existence, and it is the numerator of the latency
    this organ publishes. A survivor row without `gated_at` contributes nothing: an un-stamped
    certificate makes latency UNMEASURED, never zero.
    """
    doc = _read_json(SURVIVORS, {}) or {}
    survivors = doc.get("survivors") if isinstance(doc, dict) else None
    out: dict[tuple[str, str, str, str], str] = {}
    if not isinstance(survivors, dict):
        return out
    for row in survivors.values():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec")
        stamp = row.get("gated_at")
        if not isinstance(spec, dict) or not isinstance(stamp, str):
            continue
        key = (str(spec.get("symbol") or ""), str(spec.get("family") or ""),
               str(spec.get("selector") or ""), str(spec.get("side") or "LONG"))
        prev = out.get(key)
        if prev is None or stamp < prev:
            out[key] = stamp
    return out


def certificates() -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
    """Every runnable certificate, and every one the admission door dropped, with its reason.

    NO FILTER, NO CAP, NO RANKING, NO HEAD-OF-QUEUE. `authorized_runs` returns the whole canon in
    every lane and this organ passes it straight through -- the absence of a slice here IS the
    removal of the quota, and `scripts/check_forward_enrolment.py` fails if one reappears.
    """
    try:
        from shadow_admission import DROPPED_CERTIFICATES, authorized_runs
    except ImportError:
        try:
            from research.shadow_admission import (  # type: ignore[no-redef]
                DROPPED_CERTIFICATES,
                authorized_runs,
            )
        except Exception as exc:
            return [], [], f"shadow_admission unavailable: {type(exc).__name__}: {exc}"
    except Exception as exc:
        return [], [], f"shadow_admission unavailable: {type(exc).__name__}: {exc}"
    try:
        runs = list(authorized_runs(BASE))
    except Exception as exc:
        return [], [], f"authorized_runs FAILED: {type(exc).__name__}: {exc}"
    return runs, list(DROPPED_CERTIFICATES), ""


def _run_key(run: dict[str, Any]) -> str | None:
    try:
        from shadow_admission import run_key
    except ImportError:
        try:
            from research.shadow_admission import run_key  # type: ignore[no-redef]
        except Exception:
            return None
    except Exception:
        return None
    try:
        return str(run_key(run))
    except Exception:
        return None


def census(runs: list[dict[str, Any]], clocks: dict[str, dict[str, Any]],
           stamps: dict[tuple[str, str, str, str], str],
           now: datetime | None = None) -> dict[str, Any]:
    """Per certificate: does it have a clock, and how long did it take to get one?

    LATENCY IS `enrolled_at - gated_at`, both measured. A row the engine wrote before
    `enrolled_at` existed reports UNMEASURED rather than a flattering zero, and a certificate with
    NO clock reports `clockless_hours` from its certification stamp -- which is what the fence
    reads.
    """
    t = _now(now)
    seen: list[dict[str, Any]] = []
    latencies: list[float] = []
    for run in runs:
        key = _run_key(run)
        ident = (str(run.get("symbol") or ""), str(run.get("family") or ""),
                 str(run.get("selector") or ""), str(run.get("side") or "LONG"))
        gated = stamps.get(ident)
        row = clocks.get(key or "")
        entry: dict[str, Any] = {
            "key": key or UNMEASURED, "symbol": ident[0], "family": ident[1],
            "selector": ident[2], "side": ident[3],
            "certified_at": gated or UNMEASURED,
            "enrolled": row is not None,
            "lane": (row or {}).get("lane", UNMEASURED),
            "status": (row or {}).get("status", UNMEASURED),
            "enrolled_at": (row or {}).get("enrolled_at", UNMEASURED),
            "latency_h": UNMEASURED,
            "clockless_hours": UNMEASURED,
        }
        g = _parse_ts(gated)
        if row is not None:
            e = _parse_ts(row.get("enrolled_at"))
            if g is not None and e is not None:
                lat = max(0.0, (e - g).total_seconds() / 3600.0)
                entry["latency_h"] = round(lat, 4)
                latencies.append(lat)
            elif e is not None and g is None:
                entry["why"] = ("enrolled, but the canon carries no gated_at for this cell: "
                                "latency is UNMEASURED, never zero")
        else:
            if g is not None:
                entry["clockless_hours"] = round(max(0.0, (t - g).total_seconds() / 3600.0), 4)
            entry["why"] = "NO CLOCK: certified and accruing no forward evidence"
        seen.append(entry)
    enrolled = [e for e in seen if e["enrolled"]]
    missing = [e for e in seen if not e["enrolled"]]
    overdue = [e for e in missing
               if isinstance(e["clockless_hours"], float) and e["clockless_hours"] > CYCLE_HOURS]
    return {
        "n_certificates": len(seen), "n_enrolled": len(enrolled), "n_missing": len(missing),
        "n_overdue": len(overdue),
        "latency_h": {
            "target": TARGET_LATENCY_H, "n_measured": len(latencies),
            "max": round(max(latencies), 4) if latencies else UNMEASURED,
            "mean": round(sum(latencies) / len(latencies), 4) if latencies else UNMEASURED,
            "at_target": (all(x <= TARGET_LATENCY_H for x in latencies)
                          if latencies else UNMEASURED),
            "why": ("enrolled_at - gated_at, in hours. UNMEASURED where either stamp is absent -- "
                    "an unstamped clock never reports zero latency"),
        },
        "certificates": seen, "enrolled": enrolled, "missing": missing, "overdue": overdue,
    }


def repair(missing: list[dict[str, Any]], deadline: float,
           engine: Path | None = None) -> dict[str, Any]:
    """Re-run the enrolment engine so anything clockless gets a clock inside the hour.

    A SUBPROCESS, bounded by whatever is left of this leg's budget, for the reason every other
    producer is one: the engine loads bars and can block on a terminal call, and a hang there must
    not take the leg -- or the hourly cycle -- with it. Nothing to repair means nothing is run:
    the sweep is a repair, not a second enroller competing with the `enrol_clocks` leg.
    """
    if not missing:
        return {"status": "NOT_NEEDED", "n_missing": 0,
                "why": "every certificate already holds a clock"}
    remaining = deadline - time.monotonic()
    if remaining < 30.0:
        return {"status": "SKIPPED_BUDGET", "n_missing": len(missing),
                "why": f"{remaining:.0f}s left of the leg budget: the sweep needs more than that, "
                       "and the next hourly pass repairs it"}
    script = Path(engine or ENGINE)
    if not script.exists():
        return {"status": "UNMEASURED", "n_missing": len(missing),
                "why": f"enrolment engine not found at {script}"}
    try:
        proc = subprocess.run([sys.executable, str(script)], cwd=str(BASE), timeout=remaining,
                              capture_output=True, text=True, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "n_missing": len(missing),
                "why": f"enrolment sweep exceeded {remaining:.0f}s; the next pass resumes it"}
    except Exception as exc:
        return {"status": "FAILED", "n_missing": len(missing),
                "why": f"{type(exc).__name__}: {exc}"}
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-3:]
    return {"status": "RAN" if proc.returncode == 0 else "RAN_NONZERO", "rc": proc.returncode,
            "n_missing": len(missing), "tail": tail}


def run(write: bool = True, now: datetime | None = None, budget_s: float = 300.0,
        do_repair: bool = True) -> dict[str, Any]:
    """Census every certificate against every clock, repair the gap, publish the evidence."""
    deadline = time.monotonic() + max(0.0, float(budget_s))
    runs, dropped, why = certificates()
    clocks = clock_rows()
    stamps = certification_stamps()
    body = census(runs, clocks, stamps, now)
    rep = (repair(body["missing"], deadline) if do_repair and not why
           else {"status": "NOT_RUN", "why": why or "repair disabled for this pass"})
    if rep.get("status") in {"RAN", "RAN_NONZERO"}:
        # RE-MEASURE AFTER THE REPAIR, because the whole point is the state AFTER the sweep. A
        # report that shows the gap it just closed is a report that will be read as a defect.
        body = census(runs, clock_rows(), stamps, now)
    payload: dict[str, Any] = {
        "at": _now(now).isoformat(timespec="seconds"),
        "status": UNMEASURED if why else "MEASURED",
        "why": why or "",
        "quota": {
            "capped": False, "waiting_queue": 0, "ranking_gate": False,
            "rule": ("NO QUOTA ON FORWARD EVIDENCE, EVER (principal 2026-09-23). Every certified "
                     "survivor is enrolled the moment it exists: no cap, no waiting queue, no "
                     "ranking gate, no capacity file. A forward clock gathers evidence and "
                     "deploys NO CAPITAL, so this raises evidence throughput without touching "
                     "risk."),
            "statistics_untouched": ("multiplicity, the Holm/BH cohort, the deflated-Sharpe "
                                     "charge and the effective-trial ledger are exactly as they "
                                     "were -- more clocks make every bar HARDER, and that price "
                                     "is paid in full. The immutable floor is never a knob; what "
                                     "was removed is the SLOT QUOTA, not the statistics."),
            "ranker": ("research/forward_slot_ranker.py remains, as a REPORT of order and "
                       "priority; it gates nothing"),
        },
        "n_dropped_at_admission": len(dropped),
        "dropped_at_admission": dropped[:50],
        "repair": rep,
        "lanes_read": list(LANE_FILES),
        "cycle_hours": CYCLE_HOURS,
    }
    payload.update(body)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        try:
            from libs.ops.events import leg_events
            leg_events("forward_enrolment", "OK", certificates=payload["n_certificates"],
                       enrolled=payload["n_enrolled"], missing=payload["n_missing"],
                       overdue=payload["n_overdue"])
        except Exception as exc:
            payload["events"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    return payload


def render(payload: dict[str, Any]) -> str:
    lat = payload.get("latency_h") or {}
    lines = [f"FORWARD ENROLMENT  certificates={payload.get('n_certificates')} "
             f"enrolled={payload.get('n_enrolled')} missing={payload.get('n_missing')} "
             f"overdue={payload.get('n_overdue')}",
             f"  latency_h max={lat.get('max')} mean={lat.get('mean')} "
             f"target={lat.get('target')} measured_on={lat.get('n_measured')}",
             f"  repair={(payload.get('repair') or {}).get('status')} "
             f"quota_capped={(payload.get('quota') or {}).get('capped')}"]
    for row in (payload.get("missing") or [])[:10]:
        lines.append(f"    NO CLOCK {row.get('key')} clockless_h={row.get('clockless_hours')} "
                     f"-- {row.get('why', '')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Enrol every certificate on a forward clock; no quota, ever.")
    ap.add_argument("--once", action="store_true", help="one pass (the leg's mode)")
    ap.add_argument("--budget-s", type=float, default=300.0,
                    help="seconds this pass may spend, including the repair sweep")
    ap.add_argument("--no-repair", action="store_true",
                    help="census only: report the gap, run no enrolment sweep")
    ap.add_argument("--dry-run", action="store_true", help="write no artifact")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run, budget_s=args.budget_s, do_repair=not args.no_repair)
    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
