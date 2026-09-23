"""RESEARCH-LATENCY METRICS (Tier-5 mandate 133): idea -> cell -> verdict -> forward -> live,
each transition timed from the registry's own stamps, hourly.

`research_productivity` (daily) counts stage populations from artifacts and reports the median
age of what has NOT moved; `libs/research/promotion_latency` prices the shadow -> live queue.
Neither times a TRANSITION per item from the canonical registry. This organ does, per stage:

    idea->cell        discoveries.created_at      -> research_candidates.created_at  (discovery_id)
    cell->claimed     research_candidates.created_at -> claimed_at
    cell->verdict     research_candidates.created_at -> judged_at
    certified->forward UNIVERSAL_SURVIVORS gated_at  -> first forward ledger entry (by sleeve)
    forward->live     sleeves.json promoted_at (LIVE rows) against the forward clock's first row
    shadow->live      libs.research.promotion_latency.measure(), when it can be imported

Every stage reports n, median and p90 hours, and how many rows could NOT be timed and why. A
stage with no timed pair is UNMEASURED, which is the finding (on 2026-09-22 every one of 4,943
candidates carried a null judged_at: the gauntlet's verdict is not being stamped back).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "RESEARCH_LATENCY.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = BASE / "data" / "sleeves.json"
LEDGER_DIRS = (BASE / "reports" / "shadow", REPO / "backups" / "moat" / "shadow_ledgers")
MAX_ROWS = 20000


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


def _hours(a: Any, b: Any) -> float | None:
    da, db = _ts(a), _ts(b)
    if da is None or db is None:
        return None
    h = (db - da).total_seconds() / 3600.0
    return h if h >= 0 else None


def summarise(name: str, hours: list[float], untimed: int, why: str,
              basis: str) -> dict[str, Any]:
    hs = sorted(hours)
    if not hs:
        return {"stage": name, "n": 0, "untimed": untimed, "status": "UNMEASURED",
                "why": why, "basis": basis}
    p90 = hs[min(len(hs) - 1, round(0.9 * (len(hs) - 1)))]
    return {"stage": name, "n": len(hs), "untimed": untimed, "status": "MEASURED",
            "median_h": round(statistics.median(hs), 2), "p90_h": round(p90, 2),
            "max_h": round(hs[-1], 2), "basis": basis}


def registry_stages(conn: Any | None = None) -> list[dict[str, Any]]:
    from libs.moat import registry
    c = conn or registry.connect()
    out: list[dict[str, Any]] = []
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT id, created_at, claimed_at, judged_at, discovery_id FROM research_candidates "
            "ORDER BY seq DESC LIMIT ?", (MAX_ROWS,))]
        disc = {str(r["discovery_id"]): r["created_at"] for r in c.execute(
            "SELECT discovery_id, created_at FROM discoveries")}
        idea, ide_un = [], 0
        claim, cl_un = [], 0
        verdict, vd_un = [], 0
        for r in rows:
            d0 = disc.get(str(r.get("discovery_id") or ""))
            h = _hours(d0, r.get("created_at")) if d0 else None
            if h is None:
                ide_un += 1
            else:
                idea.append(h)
            h = _hours(r.get("created_at"), r.get("claimed_at"))
            if h is None:
                cl_un += 1
            else:
                claim.append(h)
            h = _hours(r.get("created_at"), r.get("judged_at"))
            if h is None:
                vd_un += 1
            else:
                verdict.append(h)
        out.append(summarise("idea->cell", idea, ide_un,
                             "no candidate row joins a discovery by discovery_id",
                             "discoveries.created_at -> research_candidates.created_at"))
        out.append(summarise("cell->claimed", claim, cl_un,
                             "claimed_at is null on every candidate (no worker claimed one)",
                             "research_candidates.created_at -> claimed_at"))
        out.append(summarise("cell->verdict", verdict, vd_un,
                             "judged_at is null on every candidate (verdicts are not stamped "
                             "back to the registry)",
                             "research_candidates.created_at -> judged_at"))
    finally:
        if conn is None:
            c.close()
    return out


def forward_first_rows(dirs: tuple[Path, ...] = LEDGER_DIRS) -> dict[str, str]:
    """sleeve -> earliest entry_time across the forward ledgers."""
    first: dict[str, str] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            name = f.stem.removeprefix("ledger_")
            times = [str(r.get("entry_time")) for r in rows
                     if isinstance(r, dict) and r.get("entry_time")]
            if times:
                t = min(times)
                first[name] = min(first.get(name, t), t)
    return first


def roster_stages(sleeves_doc: dict[str, Any], survivors_doc: dict[str, Any],
                  first_rows: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sv = survivors_doc.get("survivors")
    cert_fwd, cf_un = [], 0
    items = list(sv.values()) if isinstance(sv, dict) else (sv if isinstance(sv, list) else [])
    for s in items:
        if not isinstance(s, dict):
            cf_un += 1
            continue
        spec = _dct(s.get("shadow_spec"))
        name = str(spec.get("name") or s.get("name") or "")
        h = _hours(s.get("gated_at"), first_rows.get(name)) if name else None
        if h is None:
            cf_un += 1
        else:
            cert_fwd.append(h)
    out.append(summarise("certified->forward", cert_fwd, cf_un,
                         "no survivor's shadow_spec.name matches a forward ledger with rows",
                         "UNIVERSAL_SURVIVORS gated_at -> first forward ledger entry_time"))
    rows = _lst(sleeves_doc.get("sleeves"))
    fwd_live, fl_un = [], 0
    for r in rows:
        if not isinstance(r, dict) or str(r.get("status")) != "LIVE":
            continue
        h = _hours(first_rows.get(str(r.get("name") or "")), r.get("promoted_at"))
        if h is None:
            fl_un += 1
        else:
            fwd_live.append(h)
    out.append(summarise("forward->live", fwd_live, fl_un,
                         "LIVE rows carry no promoted_at joinable to a forward ledger",
                         "first forward ledger entry_time -> sleeves.json promoted_at"))
    return out


def promotion_latency() -> dict[str, Any]:
    try:
        from libs.research import promotion_latency as pl
        m = pl.measure()
        return {"status": "MEASURED", "days": getattr(m, "total_days", None),
                "components": {k: getattr(getattr(m, k, None), "days", None)
                               for k in ("queue_wait", "clock", "decision_lag")},
                "repr": repr(m)[:400]}
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def build(now: datetime | None = None, conn: Any | None = None,
          sleeves_doc: dict[str, Any] | None = None,
          survivors_doc: dict[str, Any] | None = None,
          first_rows: dict[str, str] | None = None,
          with_promotion: bool = True) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    stages: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    try:
        stages.extend(registry_stages(conn))
    except Exception as exc:
        unmeasured.append(f"registry unavailable: {type(exc).__name__}: {exc}")
    stages.extend(roster_stages(sleeves_doc if sleeves_doc is not None else _read(SLEEVES),
                                survivors_doc if survivors_doc is not None else _read(SURVIVORS),
                                first_rows if first_rows is not None else forward_first_rows()))
    measured = [s for s in stages if s.get("status") == "MEASURED"]
    slowest = max(measured, key=lambda s: float(s["median_h"])) if measured else None
    doc: dict[str, Any] = {
        "at": at, "stages": stages,
        "slowest": ({"stage": slowest["stage"], "median_h": slowest["median_h"]}
                    if slowest else None),
        "n_measured_stages": len(measured), "n_unmeasured_stages": len(stages) - len(measured),
        "shadow_to_live": promotion_latency() if with_promotion else {"status": "SKIPPED"},
        "unmeasured": unmeasured,
        "consumer": "bottleneck_law (cross-reference), research_dashboard",
        "rule": ("a stage is timed only from two stamps on the same item; a stage with no such "
                 "pair is UNMEASURED, and the count of untimed rows is the size of that gap"),
    }
    doc["headline"] = (f"{len(measured)}/{len(stages)} stages timed; slowest "
                       f"{slowest['stage']} median {slowest['median_h']}h" if slowest
                       else f"0/{len(stages)} stages timed -- every transition UNMEASURED")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"research latency: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
