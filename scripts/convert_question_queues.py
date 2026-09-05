"""QUESTIONS MUST MEET A BRAIN -- naming/deepening queue items become research-queue cards.

The searcher routes strong-but-unnamed effects to the naming queue and the compiler routes
structurally-untestable families to the deepening queue; without a consumer both rot into
silence (the QUEUES watchdog pages at 48h). This converter is the fixer: each unconsumed item
becomes a research-queue card with the measured evidence attached and the queue row is marked
consumed (never deleted -- the queue stays the audit trail). Dedup by question identity so a
recurring effect asks once.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
RQ = DESK / "data" / "research_queue.json"


def _load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    queue = _load(RQ) or []
    known = {r.get("id") for r in queue if isinstance(r, dict)}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    added = 0

    naming_p = DESK / "data" / "hypotheses" / "mechanism_naming_queue.json"
    naming = _load(naming_p) or []
    for row in naming:
        if not isinstance(row, dict) or row.get("consumed_at"):
            continue
        ident = hashlib.sha256(f"{row.get('feature')}|{row.get('symbol')}"
                               .encode()).hexdigest()[:10]
        cid = f"qq-name-{ident}"
        if cid not in known:
            queue.append({
                "id": cid, "title": (f"NAME the mechanism: {row.get('feature')} on "
                                     f"{row.get('symbol')} (t={row.get('t_stat')})"),
                "status": "PENDING", "queued_at": now,
                "source": "edge_search mechanism-naming queue",
                "mechanism": ("UNNAMED measured effect -- find the economic cause with "
                              "evidence, or refute it; it may NOT trade unnamed. Naming it "
                              "re-opens gate 1 for the whole feature class via the map."),
                "evidence": {k: row.get(k) for k in ("feature", "symbol", "band", "horizon",
                                                     "side", "t_stat", "n_oos")},
                "discipline": "external prior, NOT evidence of alpha -- same 10 gates always",
            })
            known.add(cid)
            added += 1
        row["consumed_at"] = now
    if naming:
        naming_p.write_text(json.dumps(naming, indent=1, default=str), "utf-8")

    deep_p = DESK / "data" / "hypotheses" / "miner_deepening_queue.json"
    deep = _load(deep_p) or {}
    rows = deep if isinstance(deep, dict) else {}
    for key, row in rows.items():
        if not isinstance(row, dict) or row.get("consumed_at"):
            continue
        cid = f"qq-deep-{key[:10]}"
        if cid not in known:
            fam = row.get("family") or row.get("deepening_reason", "")[:30]
            queue.append({
                "id": cid, "title": f"DEEPEN parameterization: {fam} "
                                    f"({row.get('symbol') or 'multi'})",
                "status": "PENDING", "queued_at": now,
                "source": "miner deepening queue",
                "mechanism": (str(row.get("deepening_reason") or
                                  "structurally untestable at current parameters -- widen "
                                  "windows/pool events until 60 trading days are reachable")),
                "evidence": {k: row.get(k) for k in ("symbol", "family", "params", "source")
                             if row.get(k) is not None},
                "discipline": "wider parameters re-enter the SAME ten gates; nothing is waived",
            })
            known.add(cid)
            added += 1
        row["consumed_at"] = now
    if rows:
        deep_p.write_text(json.dumps(rows, indent=1, default=str), "utf-8")

    if added:
        RQ.write_text(json.dumps(queue, indent=1, default=str), "utf-8")
    print(f"question queues -> research queue: {added} card(s) added; queue now {len(queue)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
