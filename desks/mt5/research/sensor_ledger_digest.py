"""The sensor ledger's hourly digest: what `libs.research.sensor_contract.SensorLedger` holds.

    python desks/mt5/research/sensor_ledger_digest.py            # write the report
    python desks/mt5/research/sensor_ledger_digest.py --dry-run  # print it

The ledger's day shards under `desks/mt5/data/sensors/` are box-local state and are gitignored:
they grow every day and git is not their store. This leg is the ledger's clock and its declared
artifact. Each hour it reads the last two receipt days and publishes their intake metrics
(throughput, PIT completeness, latency distributions, and the downstream clock joins to the
allocator), the shard census and the revision-index size. An empty ledger is UNMEASURED, never 0.
Nothing here writes to the ledger, sizes anything or carries authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = DESK / "reports" / "SENSOR_LEDGER.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)
    from libs.research import sensor_contract as sc
    doc = sc.digest(days=args.days)
    text = json.dumps(doc, indent=1, sort_keys=True, default=str)
    if args.dry_run:
        print(text)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(f"sensor_ledger: {doc['status']} shards={doc['shards']} "
          f"index_keys={doc['index_keys']} revised={doc['revised_keys']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
