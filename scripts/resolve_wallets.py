#!/usr/bin/env python3
"""RESOLVE ON-CHAIN ENTITIES -- the caller `libs/data/wallet_graph.py` did not have.

WHY IT EXISTS AT ALL. The module was built and left with no production caller, which is the desk's
own "built but never runs" class -- the one this codebase keeps convicting other organs of, found
here by a mechanical sweep for library modules nothing imports. A clustering library nobody calls
produces exactly as much realised asymmetry as not having written it, and the asymmetry ledger
scores that honestly: weight x depth, with depth 0 zeroing the product.

WHAT IT DOES. Reads a transfer log, resolves addresses to entities AS OF a cutoff, classifies them
by behaviour, and reports entity-level flow. Every step is as-of: clustering the full history and
labelling retroactively gives a signal that knows, years early, that an address WOULD LATER be
revealed as an exchange hot wallet -- the most damaging lookahead in on-chain work, because the
resulting backtest looks plausible rather than absurd.

INPUT. JSONL, one transfer per line: {"ts": <epoch>, "sender": .., "receiver": .., "value": ..,
"inputs": [..]}. `inputs` carries co-spent addresses on UTXO chains and is empty on EVM -- where
the common-input heuristic correctly yields nothing rather than inventing merges.

Read-only. Writes one artifact. No network, no keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.wallet_graph import Tx, cluster_asof, entity_flow, labels_asof  # noqa: E402

TRANSFERS = ROOT / "data/onchain/transfers.jsonl"
REPORT = ROOT / "data/wallet_entities.json"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load(path: Path) -> list[Tx]:
    out: list[Tx] = []
    if not path.exists():
        return out
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            out.append(Tx(float(d["ts"]), str(d["sender"]), str(d["receiver"]),
                          float(d.get("value", 0.0)),
                          tuple(str(x) for x in (d.get("inputs") or ()))))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue                      # a malformed row is skipped, never guessed at
    return sorted(out, key=lambda t: t.ts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--transfers", default=None)
    ap.add_argument("--asof", type=float, default=None,
                    help="epoch cutoff; defaults to the last transfer seen")
    a = ap.parse_args()

    src = Path(a.transfers) if a.transfers else TRANSFERS
    txs = load(src)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not txs:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO TRANSFERS",
            "reason": (f"{_rel(src)} absent or empty. data/ is gitignored, so this is expected in "
                       "a fresh checkout and a REAL blocker until a chain collector writes it."),
            "note": ("transfers are NOT synthesised: entity labels are consumed downstream as "
                     "ground truth, and a label derived from a generator would name noise"),
        }, indent=1), "utf-8")
        print(f"resolve-wallets: NO TRANSFERS at {_rel(src)} -- a collector is the blocker")
        return 0

    asof = float(a.asof) if a.asof is not None else txs[-1].ts
    clusters = cluster_asof(txs, asof)
    labels = labels_asof(txs, asof)
    tally = Counter(lab.etype for lab in labels.values())
    usable = {e: lab for e, lab in labels.items() if lab.usable}
    flows = {t: entity_flow(txs, clusters, labels, asof, etype=t)
             for t in sorted({lab.etype for lab in usable.values()})}

    out = {
        "ts": datetime.now(tz=UTC).isoformat(), "source": _rel(src),
        "transfers": len(txs), "asof": asof,
        "addresses": len(clusters), "entities": len(set(clusters.values())),
        "labelled": len(usable), "by_type": dict(tally),
        "flows": flows,
        "note": ("UNKNOWN is excluded from flow rather than bucketed as retail -- a residual "
                 "bucket quietly becomes the biggest one and then gets a signal built on it. "
                 "Every figure is AS OF the cutoff; labels are never applied retroactively."),
        "authority": "NONE. Produces features; promotes and trades nothing.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(f"resolve-wallets: {len(txs)} transfers -> {out['entities']} entities, "
          f"{len(usable)} labelled | {dict(tally)}")
    for t, f in flows.items():
        print(f"  {t:<14} net {f['net']:+.4f} over {int(f['transfers_counted'])} transfers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
