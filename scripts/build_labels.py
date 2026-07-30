#!/usr/bin/env python3
"""PROPRIETARY LABEL FACTORY runner -- writes data/label_registry.json (RANK 6).

Generates the four event-label families from the bronze panel, validates each as a well-formed
EVENT marker (testable base rate, event-not-state, no lookahead at its declared knowability lag),
versions it by content hash, and records it as a research asset with lineage back to the RANK 4
data registry.

WHAT IT DELIBERATELY DOES NOT DO: decide whether a label PREDICTS anything. That is a hypothesis
test, it costs multiplicity, and it goes through libs.research.axis_screen. A factory that scored
labels on forward returns would manufacture trials nobody counted.

    python scripts/build_labels.py                  # all symbols found in the lake
    python scripts/build_labels.py --symbol BTCUSDT
    python scripts/build_labels.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/label_registry.json"
LAKE = ROOT / "data/lake/bronze/crypto"


def _load_panels(symbol: str | None, limit: int) -> list[tuple[str, Any]]:
    """(symbol, bars) from the bronze daily panel -- the desk's best panel per GAP_REGISTER #77."""
    try:
        import pandas as pd
    except ImportError:
        return []
    if not LAKE.is_dir():
        return []
    out: list[tuple[str, Any]] = []
    syms = sorted(p.name for p in LAKE.iterdir() if p.is_dir())
    if symbol:
        syms = [s for s in syms if s == symbol]
    for sym in syms[:limit]:
        files = sorted((LAKE / sym).rglob("*.parquet"))
        if not files:
            continue
        try:
            df = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
        except Exception:
            continue
        if len(df) >= 120:                               # below this, no label has power
            out.append((sym, df))
    return out


def _lineage() -> tuple[str, ...]:
    """The RANK 4 registry asset ids these labels are built FROM.

    Derived, not hardcoded: rank 4 is rank 6's stated prerequisite precisely so a label carries the
    identity of its source panel. A hardcoded string would still say "lake_crypto" after the panel
    moved or was renamed, and a label whose lineage points at the wrong panel is worse than one with
    none -- it invites sizing a study off a span the data never had (GAP_REGISTER #77).
    """
    try:
        from libs.research.data_registry import build
        for asset in build(ROOT):
            if Path(asset.path.rstrip("/*")).as_posix() in LAKE.as_posix():
                return (asset.id,)
    except Exception:
        pass
    return ()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default=None, help="restrict to one symbol")
    ap.add_argument("--limit", type=int, default=40, help="max symbols (default 40)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from libs.research.label_factory import build_catalogue, default_specs

    panels = _load_panels(a.symbol, a.limit)
    specs = default_specs(inputs=_lineage())

    if not panels:
        # NO-INPUT is reported as a DATA gap, never a silent skip (L2.9). The specs and their
        # versions are still emitted so the catalogue is reviewable without the panel present.
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "NO-INPUT",
            "detail": f"no usable panel under {LAKE.relative_to(ROOT)} (needs >=120 bars/symbol) "
                      "-- this box has no bronze lake; run on the collecting box",
            "specs": [{"id": s.id, "version": s.version, "family": s.family,
                       "params": dict(s.params), "known_at_lag": s.known_at_lag,
                       "inputs": list(s.inputs), "rationale": s.rationale} for s in specs],
            "labels": [],
        }
    else:
        per_symbol = {sym: build_catalogue(bars, specs) for sym, bars in panels}
        # A label is only a research asset if it validates on MORE than one symbol -- a marker that
        # is well-formed on exactly one venue/symbol is a coincidence, not a proprietary label.
        usable_counts: dict[str, int] = {}
        for recs in per_symbol.values():
            for r in recs:
                usable_counts[r["qualified_id"]] = usable_counts.get(r["qualified_id"], 0) + int(
                    r["usable"])
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "ACTIVE",
            "n_symbols": len(per_symbol),
            "usable_on_n_symbols": usable_counts,
            "portable": [k for k, v in usable_counts.items() if v >= max(2, len(per_symbol) // 2)],
            "labels": dict(per_symbol),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"label-factory | {payload['status']}")
    if payload["status"] == "NO-INPUT":
        print(f"  {payload['detail']}")
        for s in payload["specs"]:
            print(f"  {s['id']:<22} v{s['version']}  lag={s['known_at_lag']}  "
                  f"inputs={','.join(s['inputs'])}")
    else:
        print(f"  {payload['n_symbols']} symbol(s); {len(payload['portable'])} label(s) valid on "
              f"a majority of them (a label well-formed on ONE symbol is a coincidence)")
        for qid, n in sorted(payload["usable_on_n_symbols"].items(), key=lambda kv: -kv[1]):
            mark = "PORTABLE" if qid in payload["portable"] else "thin"
            print(f"  {mark:<9} {qid:<38} valid on {n}/{payload['n_symbols']}")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
