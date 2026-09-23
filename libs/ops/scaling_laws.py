"""THE DESK'S OWN SCALING LAW: how many survivors an hour of compute buys, and whether that
number is rising, flat or falling.

MEASURED 2026-09-08 (Tier-1 programme item I15, recorded EXISTS-DARK): the reference
architecture asks for survivor production as a function of CPU-hours, tokens and data volume.
The desk could not draw that curve at all, for a specific reason -- `libs/ops/compute_ledger`
held four rows against fifty-nine costed legs an hour, so the x-axis did not exist. That
denominator is now recorded on every leg, which makes this a join rather than a research
programme, exactly as the compute ledger's own docstring promised.

WHAT IS FITTED. Per day inside the window: hours costed (the ledger) against survivors born and
certified (the hypothesis graph's fates). The law is fitted in logs -- log(survivors + 1) on
log(hours) -- so the slope is an elasticity: 1.0 means survivors scale linearly with compute,
below 1.0 means the desk is on the flat part of its own curve and the next hour buys less than
the last, above 1.0 means compounding. The intercept is the productivity level.

WHY log(y + 1) AND NOT log(y). Days with zero survivors are the most informative points on a
diminishing-returns curve and dropping them is how a saturating desk convinces itself it is
still scaling. The +1 keeps them, and `basis` says so.

REFUSES RATHER THAN GUESSES. Fewer than MIN_DAYS days with any compute recorded, or no variation
in hours, is UNMEASURED with the reason named -- a two-point slope through noise is not a scaling
law, it is a line. Tokens and data volume are named as ABSENT axes rather than silently omitted:
the desk buys no tokens through a metered API it records, and no byte counter is wired.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
OUT = DESK / "reports" / "scaling_laws.json"

WINDOW_DAYS = 30
MIN_DAYS = 7          # below this a slope is a line through noise
BORN, CERTIFIED = "BORN", "CERTIFIED"


def _day(stamp: Any) -> str | None:
    try:
        d = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).date().isoformat()


def hours_by_day(rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        day = _day(r.get("at"))
        if day:
            out[day] += float(r.get("wall_s") or 0.0) / 3600.0
    return dict(out)


def survivors_by_day(graph_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"born": 0, "certified": 0})
    for r in graph_rows:
        day = _day(r.get("at"))
        if not day:
            continue
        fate = str(r.get("fate") or BORN)
        if fate == BORN:
            out[day]["born"] += 1
        elif fate == CERTIFIED:
            out[day]["certified"] += 1
    return {k: dict(v) for k, v in out.items()}


def _fit(points: list[tuple[float, float]]) -> dict[str, Any]:
    """Least squares on (log hours, log(y + 1)). Returns the elasticity and its fit quality."""
    xs = [math.log(x) for x, _ in points]
    ys = [math.log(y + 1.0) for _, y in points]
    n = float(len(xs))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return {"status": "UNMEASURED", "why": "every day cost the same hours: no x variation"}
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 1e-12 else None
    return {"status": "MEASURED", "elasticity": round(slope, 4),
            "intercept": round(intercept, 4), "r2": round(r2, 4) if r2 is not None else None,
            "n_days": int(n),
            "reading": ("compounding" if slope > 1.05 else
                        "linear" if slope >= 0.95 else
                        "diminishing" if slope > 0.0 else "negative")}


def fit(hours: dict[str, float], survivors: dict[str, dict[str, int]],
        min_days: int = MIN_DAYS) -> dict[str, Any]:
    days = sorted(d for d, h in hours.items() if h > 0.0)
    if len(days) < min_days:
        return {"status": "UNMEASURED",
                "why": (f"{len(days)} day(s) with recorded compute, below the {min_days} a slope "
                        f"needs; the compute ledger has not been running long enough"),
                "days_with_compute": len(days)}
    out: dict[str, Any] = {"status": "MEASURED", "days_with_compute": len(days),
                           "total_hours": round(sum(hours[d] for d in days), 4)}
    for key in ("born", "certified"):
        pts = [(hours[d], float((survivors.get(d) or {}).get(key, 0))) for d in days]
        out[key] = _fit(pts)
        out[key]["total"] = int(sum(y for _, y in pts))
        out[key]["per_hour"] = (round(out[key]["total"] / out["total_hours"], 4)
                                if out["total_hours"] > 0 else None)
    return out


def build(ledger_rows: list[dict[str, Any]], graph_rows: list[dict[str, Any]],
          now: datetime | None = None, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    cut = (now - timedelta(days=window_days)).date().isoformat()
    hours = {d: h for d, h in hours_by_day(ledger_rows).items() if d >= cut}
    surv = {d: v for d, v in survivors_by_day(graph_rows).items() if d >= cut}
    law = fit(hours, surv)
    return {
        "at": now.isoformat(timespec="seconds"), "window_days": window_days,
        "law": law,
        "by_day": [{"day": d, "hours": round(hours[d], 4), **surv.get(d, {"born": 0,
                                                                          "certified": 0})}
                   for d in sorted(hours)][-window_days:],
        "axes": {
            "cpu_hours": "MEASURED (libs/ops/compute_ledger wall_s per costed leg)",
            "tokens": ("ABSENT: the desk's LLM seats are not metered into any artifact this "
                       "module can read, so a tokens axis would be invented"),
            "data_volume": ("ABSENT: no byte counter is wired to the bar refresh or the tape "
                            "recorder"),
        },
        "basis": ("log(survivors + 1) regressed on log(hours) per day; the +1 keeps zero-survivor "
                  "days, which are the most informative points on a diminishing-returns curve and "
                  "the first ones a saturating desk drops"),
        "consumer": "the compute allocator's numerator; the principal",
    }


def _graph_rows(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    from libs.ops.compute_ledger import rows as ledger_rows
    doc = build(ledger_rows(WINDOW_DAYS), _graph_rows(GRAPH))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    law = doc["law"]
    if law["status"] == "MEASURED":
        b = law["born"]
        print(f"scaling law: {law['days_with_compute']} days, {law['total_hours']}h; "
              f"born elasticity {b.get('elasticity')} ({b.get('reading')}), "
              f"{b.get('per_hour')} born/hour; certified "
              f"{law['certified'].get('per_hour')}/hour")
    else:
        print(f"scaling law: UNMEASURED -- {law['why']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
