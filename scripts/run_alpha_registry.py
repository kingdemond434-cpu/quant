"""#4 Alpha Registry integration -- persist every crypto sleeve as an AlphaCard.

Reuses the orphaned institutional registry (libs/alpha: AlphaLifecycleManager + AlphaCardStore +
migrations) instead of building a new one. Each live sleeve (from the portfolio engine) and each
derivative-data candidate (from the historical backtest) is registered/updated with its metrics and
validation state. This is the single source of truth the tournament + meta-portfolio read from.
Idempotent (keyed by name). Status stays CANDIDATE -- nothing is validated, and the registry will
not lie about it. Writes web/registry.json + data/alpha_registry.sqlite.

    python scripts/run_alpha_registry.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from migrations import MIGRATIONS

from libs.alpha.card import NewAlpha
from libs.alpha.manager import AlphaLifecycleManager
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_DB = Path("data/alpha_registry.sqlite")
_PORT = Path("web/crypto_portfolio.json")
_BT = Path("web/derivative_backtest.json")
_OUT = Path("web/registry.json")


def _max_corr(corr: dict[str, dict[str, float]], name: str) -> float:
    row = corr.get(name, {})
    vals = [abs(float(v)) for k, v in row.items() if k != name]
    return round(max(vals), 3) if vals else 0.0


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8")) if _PORT.exists() else {}
    corr = port.get("correlations", {})
    inc = port.get("incremental_sharpe", {})
    sleeves = [r for r in port.get("results", []) if not str(r["sleeve"]).startswith("portfolio")]
    bt = json.loads(_BT.read_text("utf-8")) if _BT.exists() else {}

    _DB.parent.mkdir(parents=True, exist_ok=True)
    db = Database(_DB)
    run_migrations(db, MIGRATIONS)
    mgr = AlphaLifecycleManager(db)
    existing = {c.name: c for c in mgr.list_all()}
    new_count = 0

    for r in sleeves:
        name = f"crypto::{r['sleeve']}"
        extra = {"gates": r.get("gates"), "survived": bool(r.get("survived", False)),
                 "fails": r.get("fails", []), "incremental_sharpe": inc.get(r["sleeve"]),
                 "max_corr": _max_corr(corr, r["sleeve"]), "source": "portfolio"}
        sh = float(r["ann_sharpe"])
        if name in existing:
            mgr.update_alpha(existing[name].id, expected_sharpe=sh, extra=extra)
        else:
            mgr.register_alpha(NewAlpha(
                name=name, market="BINANCE-PERP", category="crypto-sleeve",
                thesis=f"{r['sleeve']} -- dollar-neutral cross-sectional perp sleeve",
                entry_logic="cross-sectional rank, inverse-vol, turnover band",
                exit_logic="daily rebalance; funding cashflow; ADV-tier cost",
                expected_sharpe=sh, extra=extra))
            new_count += 1

    for r in bt.get("results", []):
        name = f"crypto::{r['sleeve']}"
        extra = {"gates": r.get("gates"), "survived": bool(r.get("survived", False)),
                 "failed_gates": r.get("failed_gates", []), "n_obs": r.get("n_obs"),
                 "source": "derivative-backtest"}
        if name in existing:
            mgr.update_alpha(existing[name].id, expected_sharpe=float(r.get("ann_sharpe", 0)),
                             extra=extra)
        else:
            mgr.register_alpha(NewAlpha(
                name=name, market="BINANCE-PERP", category="derivative-data",
                thesis=f"{r['sleeve']} -- derivative-data sleeve (historical backtest)",
                entry_logic="cross-sectional hourly", exit_logic="hourly rebalance, net of cost",
                expected_sharpe=float(r.get("ann_sharpe", 0)), extra=extra))
            new_count += 1

    cards = mgr.list_all()
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_alphas": len(cards),
        "n_survived": sum(1 for c in cards if (c.extra or {}).get("survived")),
        "db": str(_DB),
        "alphas": [{
            "id": c.id, "name": c.name, "category": c.category, "status": str(c.status),
            "expected_sharpe": c.expected_sharpe, "decay_score": c.decay_score,
            "survived": (c.extra or {}).get("survived"), "gates": (c.extra or {}).get("gates"),
            "incremental_sharpe": (c.extra or {}).get("incremental_sharpe"),
            "max_corr": (c.extra or {}).get("max_corr"),
        } for c in sorted(cards, key=lambda c: -(c.expected_sharpe or -9))],
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    db.close()
    print(f"registry: {len(cards)} alphas ({new_count} new), "
          f"{out['n_survived']} survived gauntlet -> {_OUT}")


if __name__ == "__main__":
    main()
