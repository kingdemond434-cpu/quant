"""IS OUR OWN BOOK MARTINGALE-SHAPED? -- Aurum's forensics, pointed inward.

`provider_reverse` was ported from the Aurum desk to read a COPY PROVIDER's mechanism out of its
fills. The desk mines 205 mql5_signals captures and 205 darwinex ones, so that was the obvious
target -- and it is not usable yet, which is worth stating rather than hiding: those captures are
raw PAGE HTML, not per-fill rows. Feeding an HTML blob to a module that wants `Trade(ticket,
symbol, direction, lots, open_utc, ...)` would be fabrication dressed as analysis, so it is not
done. When the provider miner starts extracting fills, the same functions read them unchanged.

WHAT THE DESK CAN ANSWER TODAY, and it is the more urgent question anyway: does the desk's OWN
book have the structure it would condemn in somebody else's? `data/live_ledger.jsonl` holds real
fills from account 495044 on FusionMarkets-Live -- entry, exit, lots, SL, TP, realised PnL -- and
that is exactly the shape `build_baskets` -> `infer_structure` -> `ruin_forensics` consumes.

WHY IT MATTERS MORE THAN IT SOUNDS. The principal asked on 2026-09-12 about an EA advertising a
91.67% win rate, 73 consecutive wins, max 2 consecutive losses and a Sharpe of 43.65. The answer
was that those numbers diagnose a martingale: you win small constantly and the loss is deferred,
not avoided, so the curve looks impossibly smooth right up until it is not. A desk that can say
that about somebody else's book and has never checked its own is asserting, not measuring. This
measures.

UNMEASURED IS THE EXPECTED ANSWER AT FIRST, AND IT IS A REAL ONE. `infer_structure` needs enough
baskets to separate a ladder from a coincidence, and the live ledger currently holds a handful of
fills. Reporting UNMEASURED against a stated minimum is the honest output; reporting "no
martingale detected" off four trades would be the lie L1.28a exists to prevent.

    python desks/mt5/research/book_forensics.py [--apply]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "BOOK_FORENSICS.json"


def _reverse():
    """Load the ported module by path, registered so dataclasses can resolve it."""
    spec = importlib.util.spec_from_file_location(
        "provider_reverse", DESK / "research" / "provider_reverse.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["provider_reverse"] = mod
    spec.loader.exec_module(mod)
    return mod


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _trades(mod) -> tuple[list, list[str]]:
    """Ledger rows -> Trade objects, and the rows that could not be read.

    MT5 encodes side as 0/1 rather than BUY/SELL, and the ledger's `time` is the CLOSE. The entry
    instant is not recorded per row, so open_utc falls back to the close: that flattens the
    HOLDING PERIOD, which `build_baskets` uses only to decide which fills belong together inside
    BASKET_WINDOW. The distortion is recorded here rather than left for a reader to discover,
    because a basket window applied to collapsed timestamps groups more aggressively than it
    should -- it can merge, never split, so it biases toward FINDING structure. A finding under a
    bias toward finding is worth less, and saying so is the difference between analysis and a
    number.
    """
    rows: list = []
    skipped: list[str] = []
    try:
        lines = LEDGER.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"ledger unreadable: {type(exc).__name__}: {exc}"]
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            skipped.append("unparseable json line")
            continue
        close = _ts(r.get("time"))
        sym = str(r.get("symbol") or "")
        lots = r.get("volume")
        entry = r.get("entry_price")
        if not (sym and close and lots and entry):
            skipped.append(f"{r.get('deal')}: missing symbol/time/volume/entry_price")
            continue
        side = r.get("side")
        direction = "BUY" if side in (0, "0", "BUY", "buy") else "SELL"
        try:
            rows.append(mod.Trade(
                ticket=str(r.get("deal") or r.get("order") or "?"),
                symbol=sym, direction=direction, lots=float(lots),
                open_utc=close, close_utc=close,
                open_price=float(entry),
                close_price=(float(r["fill_price"]) if r.get("fill_price") is not None else None),
                sl=(float(r["sl"]) if r.get("sl") else None),
                tp=(float(r["tp"]) if r.get("tp") else None),
                profit=(float(r["pl_quote"]) if r.get("pl_quote") is not None else None),
            ))
        except (TypeError, ValueError) as exc:
            skipped.append(f"{r.get('deal')}: {type(exc).__name__}: {exc}")
    return rows, skipped


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    mod = _reverse()
    if mod is None:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "provider_reverse not loadable -- UNMEASURED, never 'no structure'"}

    trades, skipped = _trades(mod)
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "source": str(LEDGER.relative_to(ROOT)),
        "n_trades": len(trades),
        "n_skipped": len(skipped),
        "skipped": skipped[:10],
        "min_baskets_required": getattr(mod, "MIN_BASKETS", None),
        "open_utc_caveat": ("the ledger records the CLOSE instant only, so open_utc falls back to "
                            "it. That collapses holding periods and makes the basket window group "
                            "more aggressively than it should -- it can merge, never split, so it "
                            "biases toward FINDING structure, and a finding under that bias is "
                            "worth correspondingly less."),
    }
    if not trades:
        doc |= {"status": "UNMEASURED",
                "why": "no readable fills in the live ledger -- absence of trades is not absence "
                       "of structure (L1.28a)"}
        return doc

    try:
        baskets = mod.build_baskets(trades)
        doc["n_baskets"] = len(baskets)
        need = int(getattr(mod, "MIN_BASKETS", 0) or 0)
        if len(baskets) < need:
            doc |= {"status": "UNMEASURED",
                    "why": (f"{len(baskets)} basket(s) against a stated minimum of {need}. "
                            f"Reporting 'no martingale' from fewer would be exactly the claim "
                            f"L1.28a forbids -- the desk has not traded enough for this question "
                            f"to have an answer yet.")}
            return doc
        structure = mod.infer_structure(baskets)
        doc["structure"] = (
            {k: v for k, v in vars(structure).items() if not k.startswith("_")}
            if hasattr(structure, "__dict__") else str(structure))
        forensics = mod.ruin_forensics(baskets, structure, equity=None)
        doc["ruin_forensics"] = ({k: v for k, v in vars(forensics).items()
                                  if not k.startswith("_")}
                                 if hasattr(forensics, "__dict__") else str(forensics))
        doc["status"] = "OK"
    except Exception as exc:
        doc |= {"status": "UNMEASURED",
                "why": f"forensics raised {type(exc).__name__}: {exc}"}
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    print(f"book forensics: {doc.get('status')}  {doc.get('n_trades', 0)} fill(s), "
          f"{doc.get('n_baskets', '-')} basket(s)")
    if doc.get("why"):
        print(f"  {doc['why'][:160]}")
    if doc.get("structure"):
        print(f"  structure: {json.dumps(doc['structure'], default=str)[:200]}")
    if doc.get("ruin_forensics"):
        print(f"  ruin:      {json.dumps(doc['ruin_forensics'], default=str)[:200]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
