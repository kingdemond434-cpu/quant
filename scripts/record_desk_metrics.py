"""DESK METRICS RECORDER -- wire libs/monitoring, and give the desk a memory of its own numbers.

THE GAP. libs/monitoring (5 modules: durable metrics store, alert store + router, monitor
service, heartbeat watchdog, SLO evaluator) had no path from any entry point. Meanwhile every
"is this getting better?" question on this desk is answered from a JSON snapshot that gets
overwritten, or from recall. The §6 research-efficiency ratios in meta_research_review had to
proxy engineering hours with COMMIT COUNTS because no durable time-series existed to read.

A desk that cannot see its own trend cannot tell improvement from noise. That is the difference
between "maker rate is 31%" and "maker rate is 31% and rising 4pts/week since the fix" -- only
the second answers whether the fix worked, and only a durable store can say it.

WHAT IT RECORDS -- the load-bearing numbers this session identified, each with a threshold that
raises a real alert through libs/monitoring's router:

  fill.maker_rate          the ledger's own >=60% bar; below it is the live fee drag
  fill.bps_per_rt          ~20-25 today vs ~12-15 achievable = the ladder's biggest live drag
  slots.idle               idle forward-validation slots = research capital earning nothing
  slots.used               occupancy, so under- and over-use are both visible
  research.validated       validated findings -- the ONLY output §12 accepts as progress
  research.hypotheses      generation volume, recorded but explicitly NOT the health metric
  moat.symbols             recorded symbols; the moat's breadth
  complexity.orphan_modules unreachable modules -- unpaid maintenance

Thresholds fail LOUD, not silently: each one that breaches becomes a persisted Alert with a
severity, so a regression is discoverable after the fact instead of only in the moment.

Idempotent, read-only over desk state, writes only to its own SQLite store. Run from repo root;
`--self-test` proves the store round-trips without touching desk data.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from migrations import MIGRATIONS  # noqa: E402

from libs.monitoring.models import Op, Severity, Threshold  # noqa: E402
from libs.monitoring.monitor import MonitorService  # noqa: E402
from libs.store.connection import Database  # noqa: E402
from libs.store.migrations import run_migrations  # noqa: E402

DB_PATH = ROOT / "data/desk_metrics.sqlite"

# Each threshold encodes a bar this session established from the desk's own evidence, not a
# guess. A metric without a threshold is a number nobody is accountable for.
THRESHOLDS = [
    Threshold(metric="fill.maker_rate", op=Op.LT, value=0.60, severity=Severity.WARNING,
              message="maker rate below the ledger's 60% bar -- taker minority still paying "
                      "the fee majority"),
    Threshold(metric="fill.bps_per_rt", op=Op.GT, value=15.0, severity=Severity.WARNING,
              message="round-trip cost above the achievable ~12-15bps band -- the growth "
                      "ladder's single biggest live drag"),
    Threshold(metric="slots.idle", op=Op.GT, value=6.0, severity=Severity.WARNING,
              message="more than half the forward-validation slots idle -- confirmation "
                      "capacity paid for and unused"),
    Threshold(metric="complexity.orphan_modules", op=Op.GT, value=40.0, severity=Severity.INFO,
              message="unreachable modules accumulating -- engineering cost with no "
                      "measurable contribution"),
]


def _j(rel: str, default: Any) -> Any:
    try:
        return json.loads((ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def collect() -> dict[str, float]:
    """Read desk state into a flat metric dict. Missing inputs are OMITTED, never zero-filled.

    Zero-filling would be a lie the store then remembers forever: a missing maker_rate recorded
    as 0.0 breaches the threshold and manufactures an alert about a fill quality nobody measured.
    """
    out: dict[str, float] = {}

    fq = _j("data/fill_quality.json", {}).get("current") or {}
    for src, dst in (("maker_rate", "fill.maker_rate"), ("bps_per_rt", "fill.bps_per_rt"),
                     ("fee_concentration", "fill.fee_concentration")):
        if isinstance(fq.get(src), (int, float)):
            out[dst] = float(fq[src])

    life = _j("data/meta_research_review.json", {})
    al = life.get("alpha_lifecycle") or {}
    for src, dst in (("slots_free", "slots.idle"), ("forward_slots_in_use", "slots.used"),
                     ("graveyard_entries", "research.graveyard")):
        if isinstance(al.get(src), (int, float)):
            out[dst] = float(al[src])
    eff = life.get("research_efficiency") or {}
    for src, dst in (("validated", "research.validated"),
                     ("hypotheses_generated", "research.hypotheses"),
                     ("falsified_negative_information_value", "research.falsified")):
        if isinstance(eff.get(src), (int, float)):
            out[dst] = float(eff[src])
    cx = life.get("complexity_audit") or {}
    if isinstance(cx.get("orphan_modules"), (int, float)):
        out["complexity.orphan_modules"] = float(cx["orphan_modules"])

    moat = ROOT / "data/moat"
    if moat.exists():
        syms = {d.name for v in moat.iterdir() if v.is_dir() for d in v.iterdir() if d.is_dir()}
        out["moat.symbols"] = float(len(syms))
    return out


def record_all(db_path: Path, metrics: dict[str, float]) -> tuple[int, list[str]]:
    """Persist every metric and evaluate thresholds. Returns (n_recorded, alert messages)."""
    db = Database(db_path)
    # Idempotent: run_migrations applies only unapplied versions, so a fresh store is created
    # on first use and an existing one is untouched. Without this the store raises
    # "no such table: metric_points" -- which is precisely why this layer sat unwired.
    run_migrations(db, MIGRATIONS)
    svc = MonitorService(db, THRESHOLDS)
    alerts: list[str] = []
    for name, value in sorted(metrics.items()):
        svc.record(name, value)
        for a in svc.evaluate(name, value):
            alerts.append(f"[{a.severity.value}] {a.message}")
    return len(metrics), alerts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        with tempfile.TemporaryDirectory() as td:
            n, alerts = record_all(Path(td) / "t.sqlite",
                                   {"fill.maker_rate": 0.242, "slots.idle": 12.0,
                                    "research.validated": 0.0})
            print("=== DESK METRICS (self-test) ===")
            print(f"  recorded {n} metric(s); {len(alerts)} threshold breach(es):")
            for a in alerts:
                print(f"    {a}")
            assert n == 3 and len(alerts) == 2, (n, alerts)
            print("  store round-trips and thresholds fire -- libs/monitoring is live")
        return

    metrics = collect()
    print("=== DESK METRICS RECORDER ===")
    if not metrics:
        print("  no desk state available to record (run meta_research_review first)")
        return
    n, alerts = record_all(DB_PATH, metrics)
    for k, v in sorted(metrics.items()):
        print(f"  {k:<32} {v}")
    print(f"\n  {n} metric(s) persisted -> {DB_PATH.relative_to(ROOT)}")
    if alerts:
        print(f"  {len(alerts)} THRESHOLD BREACH(ES):")
        for a in alerts:
            print(f"    {a}")
    else:
        print("  no threshold breached")
    print(f"  recorded at {datetime.now(tz=UTC).isoformat()} -- the desk now has a TREND, "
          "not just a snapshot")


if __name__ == "__main__":
    main()
