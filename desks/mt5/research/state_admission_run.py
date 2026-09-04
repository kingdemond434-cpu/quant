"""Judge the desk's state dimensions against its own realised trades, and write the verdicts.

The allocator reads `reports/STATE_ADMISSION.json` and refuses to condition on any dimension this
sent to the graveyard. Everything else keeps whatever access it has, protected by the k_state
shrinkage rather than by a passing grade -- see `libs.regime.state_admission` for why that
distinction matters and why RETAIN_SHRUNK is not a pass.

WHERE THE TRADES COME FROM. The shadow forward ledgers, which are the only realised evidence this
desk has that was NOT used to fit anything. Live fills join them automatically as they appear:
the loader reads both, tags each row with its basis, and refuses to mix them into one judgement,
because a shadow trade paid a modelled cost and a live one paid a real spread.

    python research/state_admission_run.py
    python research/state_admission_run.py --dimension session --dimension weekday
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import (  # noqa: E402
    GRAVEYARD,
    Trade,
    admitted,
    build_labeller,
    judge_all,
)

OUT = BASE / "reports" / "STATE_ADMISSION.json"
LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")
LIVE = BASE / "data" / "live_ledger.jsonl"

#: Dimensions judged by default. Only those reconstructible from a trade's timestamp are here;
#: asset regime, event phase and liquidity state need the state-vector history joined to the
#: ledgers, and labelling historical trades with today's fit would be worse than not judging them.
DEFAULT_DIMENSIONS = ("session", "weekday")


def _entry_time(row: dict) -> str:
    for key in ("entry_time", "opened_at", "open_time", "time"):
        v = row.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def _r(row: dict) -> float | None:
    for key in ("r_multiple", "r", "R"):
        v = row.get(key)
        try:
            if v is not None:
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def load_trades(basis: str = "shadow") -> list[Trade]:
    """Realised trades with their entry time, one basis at a time.

    NEVER MIXED. A shadow trade paid the modelled cost and a live one paid a real spread; pooling
    them to get a bigger sample would judge a state dimension on evidence whose noise differs
    between halves, and the direction of that error is not conservative.
    """
    out: list[Trade] = []
    if basis == "live":
        try:
            for line in LIVE.read_text("utf-8").splitlines():
                row = json.loads(line)
                when, r = _entry_time(row), _r(row)
                if when and r is not None:
                    out.append(Trade(sleeve=str(row.get("sleeve") or "?"), when=when, r=r))
        except (OSError, ValueError):
            return []
        return out
    for d in LEDGER_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            sleeve = f.stem.removeprefix("ledger_")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                when, r = _entry_time(row), _r(row)
                if when and r is not None:
                    out.append(Trade(sleeve=sleeve, when=when, r=r))
    return out


def label(trades: list[Trade], dimensions: tuple[str, ...]) -> tuple[list[Trade], dict[str, str]]:
    """Attach each dimension's bucket to every trade, recording dimensions that cannot be built."""
    gaps: dict[str, str] = {}
    fns = {}
    for d in dimensions:
        fn = build_labeller(d)
        if fn is None:
            gaps[d] = ("no labeller: this dimension cannot be reconstructed from a timestamp "
                       "alone, or its input (e.g. the broker clock) is unavailable here")
            continue
        fns[d] = fn
    out = []
    for t in trades:
        buckets = {}
        for d, fn in fns.items():
            b = fn(t.when)
            if b:
                buckets[d] = b
        out.append(Trade(sleeve=t.sleeve, when=t.when, r=t.r, buckets=buckets))
    return out, gaps


def run(dimensions: tuple[str, ...] = DEFAULT_DIMENSIONS, basis: str = "shadow") -> dict:
    trades = load_trades(basis)
    labelled, gaps = label(trades, dimensions)
    verdicts = judge_all(labelled, [d for d in dimensions if d not in gaps]) if labelled else {}
    doc = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "basis": basis,
        "n_trades": len(trades),
        "n_sleeves": len({t.sleeve for t in trades}),
        "dimensions_tried": len(verdicts),
        "verdicts": {d: v.to_dict() for d, v in verdicts.items()},
        "gaps": gaps,
        "admitted": list(admitted(verdicts)),
        "graveyard": sorted(d for d, v in verdicts.items() if v.verdict == GRAVEYARD),
        "rule": ("a dimension conditions capital only until it is MEASURED worse; "
                 "RETAIN_SHRUNK is a stay of execution granted by k_state, not a pass"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def read_graveyard() -> tuple[frozenset[str], str]:
    """Dimensions the allocator must NOT condition on. Fails open to nothing, and says so."""
    try:
        doc = json.loads(OUT.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return frozenset(), f"no admission report ({type(exc).__name__}); nothing is barred"
    barred = frozenset(str(d) for d in (doc.get("graveyard") or []))
    return barred, (f"admission report {doc.get('generated_utc')}: "
                    f"{len(barred)} dimension(s) barred, "
                    f"{len(doc.get('admitted') or [])} allowed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", action="append", default=None)
    ap.add_argument("--basis", default="shadow", choices=("shadow", "live"))
    args = ap.parse_args()

    doc = run(tuple(args.dimension) if args.dimension else DEFAULT_DIMENSIONS, basis=args.basis)
    print(f"STATE ADMISSION  basis={doc['basis']}  {doc['n_trades']} trades "
          f"across {doc['n_sleeves']} sleeves")
    for d, v in sorted(doc["verdicts"].items()):
        print(f"  {d:12s} {v['verdict']:14s} n_test={v['n_test']:5d} "
              f"buckets={v['n_buckets']:3d} t={v['t_paired']:+.2f} "
              f"t_defl={v['t_deflated']:+.2f}")
        print(f"    {v['why']}")
    for d, why in sorted(doc["gaps"].items()):
        print(f"  {d:12s} NO LABELLER   {why}")
    print(f"admitted: {doc['admitted'] or '(none)'}   graveyard: {doc['graveyard'] or '(none)'}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
