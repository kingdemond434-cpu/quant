"""High-Flyer-style adapter (REBUILT) -- the published capability is SHARED-COMPUTE SCHEDULING with
utilisation as a first-class telemetry. The adapter reads the desk's own compute ledger (the
tail only, so a large file costs nothing) and reports where the last hours of compute went, by
leg. Utilisation the desk cannot see is utilisation it cannot reallocate; an absent ledger is
named as absent."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_highflyer"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True

LEDGER = "desks/mt5/data/compute_ledger.jsonl"
TAIL_BYTES = 200_000


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    p = root / LEDGER
    if not p.exists():
        return A.unmeasured(SYSTEM, bundle, f"{LEDGER} does not exist on this tree")
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()
            text = fh.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return A.unmeasured(SYSTEM, bundle, f"{type(exc).__name__}: {exc}"[:200])
    seconds: dict[str, float] = {}
    runs: dict[str, int] = {}
    n_rows = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        n_rows += 1
        leg = str(doc.get("leg") or doc.get("name") or doc.get("organ") or "UNNAMED")
        secs = doc.get("seconds", doc.get("elapsed_s", doc.get("cost_s")))
        runs[leg] = runs.get(leg, 0) + 1
        if isinstance(secs, (int, float)):
            seconds[leg] = seconds.get(leg, 0.0) + float(secs)
    if not n_rows:
        return A.unmeasured(SYSTEM, bundle, "the compute ledger tail carried no parsable rows")
    total = sum(seconds.values())
    top = sorted(seconds.items(), key=lambda kv: -kv[1])[:15]
    return A.packet(
        SYSTEM, bundle, trials=n_rows,
        representations=[{
            "kind": "compute_utilisation", "system": SYSTEM, "rows_read": n_rows,
            "tail_bytes": min(size, TAIL_BYTES), "total_seconds": total,
            "legs_seen": len(runs),
            "top_legs": [{"leg": k, "seconds": v, "share": (v / total) if total else None,
                          "runs": runs.get(k, 0)} for k, v in top],
            "representation": ("where the desk's shared compute actually went in the ledger's "
                               "tail -- utilisation as telemetry, never a cap")}],
        note=f"{n_rows} compute rows over {len(runs)} legs")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
