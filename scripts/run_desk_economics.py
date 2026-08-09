"""What return the desk needs just to stand still -- the hurdle it had never computed.

`config/costs.yaml` models what a TRADE costs. Nothing modelled what the DESK costs, so the
question "is this book big enough to be worth running?" had no numeric answer anywhere in the
repo. This computes it from costs the PRINCIPAL declares in config/desk_costs.yaml.

Unknown costs are excluded from the total and named in the output, and every figure is labelled
a FLOOR until the cost base is complete. The alternative -- treating an undeclared cost as zero
-- produces a confident hurdle that omits the largest line item, which is the one output of this
script that could actually mislead a decision.

    python scripts/run_desk_economics.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from libs.research.capacity_policy import live_book_usd
from libs.research.desk_economics import assess

_ROOT = Path(__file__).resolve().parent.parent
_CFG = _ROOT / "config" / "desk_costs.yaml"
_OUT = _ROOT / "web" / "desk_economics.json"


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

    equity = live_book_usd()
    report = {"ts": datetime.now(tz=UTC).isoformat(), **assess(equity, cfg)}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")

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
