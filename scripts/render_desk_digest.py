"""Render the desk's JSON state into docs/desk_digest.md -- the Obsidian-readable daily brief.

The knowledge base is markdown (Obsidian-native) but the measurable state (decision ledger,
executive KPIs, validation clocks, root cause) lives in JSON per governance. This renders a daily
digest so the whole desk is browsable in one vault. Generated file -- never hand-edit.

    python scripts/render_desk_digest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("docs/desk_digest.md")


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    lc = _load("web/live_combined.json")
    mo = lc.get("molded", {})
    rc = _load("web/root_cause.json")
    led = _load("data/decision_ledger.json").get("decisions", [])
    kpi = _load("data/executive_kpis.json")

    lines = [
        "# Desk digest (auto-generated daily -- do not hand-edit)",
        f"_updated {datetime.now(tz=UTC).isoformat()[:16]}Z · companion to "
        "[[institutional_knowledge]]_", "",
        "## Book",
        f"- Molded net: **${mo.get('net_pnl')}** | funding **${mo.get('funding')}** | "
        f"run-rate APR {mo.get('run_rate_apr_pct')}% | day {mo.get('days_live')}",
        f"- Root cause: **{rc.get('top_cause')}** ({rc.get('action')}) | tracking error "
        f"${rc.get('tracking_error_usd')}", "",
        "## Validation clocks",
    ]
    clocks = (("cashcarry_shadow", "carry (DEPLOYED)"), ("crypto_shadow", "perp L/S"),
              ("trend_shadow", "trend"), ("trend_regime_shadow", "trend regime-gated"),
              ("derivative_shadow", "OI/LS data"), ("stablecoin_flows", "stablecoin data"))
    for f, lbl in clocks:
        s = _load(f"web/{f}.json")
        days = s.get("forward_days", s.get("days_accumulated", s.get("forward_days", "?")))
        need = s.get("needs_days", s.get("min_days", 90))
        bt, fwd = s.get("backtest_ann_sharpe"), s.get("forward_ann_sharpe")
        extra = f" | bt {bt} fwd {fwd}" if bt is not None else ""
        lines.append(f"- **{lbl}**: {days}/{need}d{extra}")
    lines += ["", "## Open decisions (ledger)"]
    for dec in led:
        if dec.get("outcome") is None:
            lines.append(f"- `{dec.get('id')}` -- review {dec.get('review_due', '?')}: "
                         f"{dec.get('success_metric', '')[:90]}")
    lines += ["", "## Executive KPI snapshot",
              f"- CRO: {json.dumps(kpi.get('CRO', {}).get('current', {}))[:180]}",
              f"- CEO binding constraint: "
              f"{kpi.get('CEO', {}).get('current', {}).get('binding_constraint', '?')}", "",
              "_Full state: decision_ledger.json · executive_kpis.json · data_registry.json_"]
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(lines), "utf-8")
    print(f"desk digest -> {_OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
