"""WHAT WAS NOT TESTED THIS HOUR, BY NAME: the research opportunity-cost artifact.

MEASURED 2026-09-08 (Tier-1 programme item A13): the cost side of research is instrumented and
nearly empty, and no artifact anywhere names WHAT was left untested because resources went
elsewhere. The compiler's MAX_ROWS_PER_PASS shortfall was a printed line; the gauntlet's
budget-deferred cells were a status string inside a 20 MB verdict file; the deepening queue's
backlog was a histogram nobody joined to a family or a symbol. Three organs each knew a piece
of the same fact -- "this hour's compute chose X and therefore not Y" -- and the desk could
name X but never Y.

An opportunity cost that cannot be named cannot be priced, and an allocator that cannot price
what it skipped is not allocating, it is queueing. This module joins the three pieces into one
file so the NOT-tested set is as concrete as the tested one:

    compiler   files the intake bound left unopened (miner_candidates.json `intake`)
    gauntlet   cells deferred by the build budget (universal_gates_external.json verdicts)
    queue      pending rows by kind/family/symbol, and how old the oldest is (queue_store)
    ledger     the hours that went elsewhere instead (compute_ledger.cost_by_run)

READ-ONLY, BOUNDED. It opens the queue through `queue_store.iter_rows` and stops after
SAMPLE rows of pending work -- the artifact names the shape of the backlog, not every row.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

COMPILED = BASE / "data" / "hypotheses" / "miner_candidates.json"
GATES = BASE / "reports" / "universal_gates_external.json"
OUT = BASE / "reports" / "opportunity_cost.json"
DEFERRED = "NOT_RUN_BUILD_BUDGET_DEFERRED"
SAMPLE = 5000


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def compiler_shortfall(compiled: dict[str, Any]) -> dict[str, Any]:
    intake = compiled.get("intake") or {}
    return {"bound_hit": bool(intake.get("bound_hit")),
            "files_deferred": int(intake.get("deferred_files") or 0),
            "max_rows_per_pass": intake.get("max_rows_per_pass"),
            "seats_dark": list(compiled.get("seats_dark") or [])}


def gauntlet_deferred(gates: dict[str, Any], limit: int = 50) -> dict[str, Any]:
    verdicts = gates.get("verdicts") or []
    deferred = [v for v in verdicts if isinstance(v, dict)
                and str(v.get("downstream_status") or "") == DEFERRED]
    by_sym = Counter(str(v.get("sym") or "?") for v in deferred)
    return {"cells_deferred": len(deferred), "of_verdicts": len(verdicts),
            "by_symbol": dict(by_sym.most_common(12)),
            "cells": [str(v.get("cell")) for v in deferred[:limit]],
            "swept_at": gates.get("swept_at") or gates.get("at")}


def queue_backlog(now: datetime | None = None, path: Path | None = None) -> dict[str, Any]:
    from queue_store import TERMINAL, iter_rows
    now = now or datetime.now(tz=UTC)
    kinds: Counter[str] = Counter()
    fams: Counter[str] = Counter()
    syms: Counter[str] = Counter()
    oldest: float | None = None
    n = 0
    for row in iter_rows(path):
        if str(row.get("status") or "").lower() in TERMINAL:
            continue
        n += 1
        kinds[str(row.get("kind") or "None")] += 1
        fams[str(row.get("family") or "?")] += 1
        syms[str(row.get("symbol") or row.get("sym") or "?")] += 1
        stamp = row.get("created_at") or row.get("at") or row.get("enqueued_at")
        try:
            age = (now - datetime.fromisoformat(str(stamp))).total_seconds() / 86400.0
            oldest = age if oldest is None or age > oldest else oldest
        except (TypeError, ValueError):
            pass
        if n >= SAMPLE:
            break
    return {"pending_sampled": n, "sample_cap": SAMPLE, "by_kind": dict(kinds.most_common(8)),
            "by_family": dict(fams.most_common(12)), "by_symbol": dict(syms.most_common(12)),
            "oldest_pending_days": round(oldest, 2) if oldest is not None else None}


def spent(cost_by_run: dict[str, dict[str, Any]], top: int = 15) -> dict[str, Any]:
    rows = sorted(((k, float(v.get("hours") or 0.0)) for k, v in cost_by_run.items()),
                  key=lambda kv: -kv[1])
    return {"hours_by_run": {k: round(h, 4) for k, h in rows[:top]},
            "total_hours": round(sum(h for _, h in rows), 4), "costed_runs": len(rows)}


def build(now: datetime | None = None) -> dict[str, Any]:
    from libs.ops.compute_ledger import cost_by_run
    compiled = _read(COMPILED)
    gates = _read(GATES)
    doc = {
        "at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "not_tested": {
            "compiler": compiler_shortfall(compiled),
            "gauntlet": gauntlet_deferred(gates),
            "queue": queue_backlog(now),
        },
        "spent": spent(cost_by_run()),
        "sources": {"compiled": COMPILED.name, "gates": GATES.name, "queue": "queue_store",
                    "ledger": "libs/ops/compute_ledger"},
        "why": ("the tested set is what the hour's compute chose; this is the set it therefore "
                "did not choose, named so the choice can be priced"),
    }
    nt = doc["not_tested"]
    doc["headline"] = (f"{nt['compiler']['files_deferred']} intake files unopened, "
                       f"{nt['gauntlet']['cells_deferred']} gauntlet cells budget-deferred, "
                       f"{nt['queue']['pending_sampled']}+ queue rows pending "
                       f"(oldest {nt['queue']['oldest_pending_days']}d) against "
                       f"{doc['spent']['total_hours']}h costed in the window")
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"opportunity cost: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
