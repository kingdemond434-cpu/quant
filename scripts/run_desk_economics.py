"""What return the desk needs just to stand still -- the hurdle it had never computed.

`config/costs.yaml` models what a TRADE costs. Nothing modelled what the DESK costs, so the
question "is this book big enough to be worth running?" had no numeric answer anywhere in the
repo. This computes it from costs the PRINCIPAL declares in config/desk_costs.yaml.

Unknown costs are excluded from the total and named in the output, and every figure is labelled
a FLOOR until the cost base is complete. The alternative -- treating an undeclared cost as zero
-- produces a confident hurdle that omits the largest line item, which is the one output of this
script that could actually mislead a decision.

    python scripts/run_desk_economics.py

MEASURED, NOT ONLY DECLARED (ARCH-28, 2026-10-07). The organ had no box clock and every cost in
the YAML was null, so it answered nothing. It now runs on the box's `organs` battery and reads
the desk's own ledgers: model spend ESTIMATED from `data/llm_spend.jsonl` (written over the YAML's
`llm_api`), what the broker charged from `desks/mt5/data/cost_truth_quotes.json` deals (reported,
never added to the burn), and the operator's alert burden from `data/alert_ledger.json` and the
event log. Host invoices have no API the desk holds a key for, so those lines stay as declared
and a null stays UNKNOWN. Writes `desks/mt5/reports/DESK_ECONOMICS.json` beside the web copy.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from libs.research.capacity_policy import live_book_usd
from libs.research.desk_economics import (
    alert_burden,
    assess,
    measure_broker,
    measure_llm,
    merge_measured,
)

_ROOT = Path(__file__).resolve().parent.parent
_CFG = _ROOT / "config" / "desk_costs.yaml"
_OUT = _ROOT / "web" / "desk_economics.json"
_REPORT = _ROOT / "desks" / "mt5" / "reports" / "DESK_ECONOMICS.json"
_QUOTES = _ROOT / "desks" / "mt5" / "data" / "cost_truth_quotes.json"
_ALERTS = _ROOT / "data" / "alert_ledger.json"
#: Event kinds that are a defect the operator might be asked about.
_DEFECT_KINDS = ("LEG_FAILED", "PLUMBING_DEFECT", "PLACEMENT_HALTED", "PLACEMENT_UNMEASURED",
                 "STATE_FLOW_STALLED", "REFERENCE_STAND_DOWN")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    except OSError:
        pass
    return out


def measured_lines(now: datetime) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """({cost line: measurement}, broker block) from the desk's own ledgers."""
    from libs.ops.llm_seat import SPEND_LEDGER, is_free_model
    llm = measure_llm(_jsonl(SPEND_LEDGER), now, is_free_model)
    try:
        q = json.loads(_QUOTES.read_text("utf-8"))
    except (OSError, ValueError):
        q = {}
    deals = q.get("deals") if isinstance(q, dict) else None
    if isinstance(deals, list):
        broker = measure_broker(deals, now, (q.get("account") or {}).get("currency"))
    else:
        broker = {"status": "UNMEASURED", "why": f"{_QUOTES.name} absent or has no deals "
                  "(written by cost_truth on the trading box)"}
    return {"llm_api": llm}, broker


def burden(now: datetime) -> dict[str, Any]:
    from datetime import timedelta

    from libs.ops import events
    from libs.ops.alert_ledger import AlertLedger
    if _ALERTS.exists():
        led = AlertLedger(_ALERTS)
        summary = led.summary()
        esc = [{"id": a.id, "state": a.state, "message": a.message[:200],
                "age_h": round(a.age_hours(), 1)} for a in led.escalations()]
    else:
        summary, esc = {}, []
    counts: dict[str, int] = {}
    for r in events.since(now - timedelta(days=7), kinds=_DEFECT_KINDS):
        k = str(r.get("kind"))
        counts[k] = counts.get(k, 0) + 1
    out = alert_burden(summary, esc, counts)
    out["status"] = "MEASURED" if _ALERTS.exists() else "UNMEASURED"
    if not _ALERTS.exists():
        out["why"] = f"{_ALERTS.name} absent: no alert lifecycle on this host"
    return out


def _load_cfg() -> dict[str, Any]:
    try:
        d = yaml.safe_load(_CFG.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def main() -> int:
    cfg = _load_cfg()
    if not cfg:
        print(f"desk economics: {_CFG.name} missing or unreadable -- nothing to compute")
        return 0

    now = datetime.now(tz=UTC)
    measured, broker = measured_lines(now)
    merged = merge_measured(cfg, measured)
    equity = live_book_usd()
    report = {"ts": now.isoformat(), **assess(equity, merged),
              "line_basis": merged["basis"], "measured": measured,
              "broker_charges": broker, "alert_burden": burden(now)}
    for out in (_OUT, _REPORT):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str), "utf-8")

    print(f"desk economics: {report['verdict']}")
    if report["undeclared_line_items"]:
        print(f"  UNDECLARED (excluded from the total, so every figure is a floor): "
              f"{', '.join(report['undeclared_line_items'])}")
        print(f"  -> declare them in config/{_CFG.name}")
    need = report["capital_needed_for_acceptable_hurdle_usd"]
    if need is not None and report["hurdle_acceptable"] is False:
        print(f"  hurdle {report['hurdle_annual_pct']:.2f}%/yr exceeds the "
              f"{report['max_acceptable_annual_hurdle_pct']:.1f}% policy bar -- "
              f"${need:,.0f} of equity would bring it in line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
