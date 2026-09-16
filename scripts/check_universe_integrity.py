"""Universe bars integrity: an unreadable parquet is quarantined, a stale one is named.

MEASURED 2026-09-16. The build box's copy of `US500_H1.parquet` raised `ArrowInvalid` on read,
which every consumer -- the residual lane (`factor_residual_engine._bars`), the gauntlet's cell
builder, the leg factors -- reports as "no H1 bars for US500". A corrupt file is worse than a
missing one: the fetcher sees it exists and appends to it, the readers fail, and the instrument
drops out of every study without any organ saying so. On the trading box 56 share-CFD files had
not moved since 2026-08-17 while the rest of the universe was current to the hour.

WHAT THIS DOES. Every `*_<TF>.parquet` under the universe directory is opened (metadata + the
close column). One that cannot be read is MOVED to `universe/_corrupt/<name>.<utc>` -- never
deleted -- so the fetcher rebuilds it from the terminal on its next pass and the bytes remain for
a post-mortem. One whose last bar is older than `STALE_DAYS` is reported by asset class. The
artifact is `reports/UNIVERSE_INTEGRITY.json`; the exit code is 0 unless a file could not even be
moved, because a report that stops the cycle is worse than a stale instrument.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "desks" / "mt5" / "data" / "universe"
OUT = ROOT / "desks" / "mt5" / "reports" / "UNIVERSE_INTEGRITY.json"
STALE_DAYS = 7


def _asset_class(symbol: str) -> str:
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5"))
        from research.universe_policy import asset_class_of  # type: ignore[import-not-found]
        return asset_class_of(symbol) or "unregistered"
    except Exception:
        return "unknown"


def scan(universe: Path = UNIVERSE, *, quarantine: bool = True,
         stale_days: int = STALE_DAYS) -> dict[str, Any]:
    import pandas as pd

    now = pd.Timestamp.now(tz="UTC")
    corrupt: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    n = 0
    for f in sorted(universe.glob("*_*.parquet")):
        n += 1
        try:
            df = pd.read_parquet(f, columns=["close"])
            if len(df) == 0:
                raise ValueError("zero rows")
            last = pd.Timestamp(df.index[-1])
            last = last.tz_localize("UTC") if last.tzinfo is None else last.tz_convert("UTC")
        except Exception as exc:
            rec = {"file": f.name, "error": f"{type(exc).__name__}: {str(exc)[:80]}"}
            if quarantine:
                qdir = universe / "_corrupt"
                qdir.mkdir(exist_ok=True)
                dest = qdir / f"{f.name}.{now.strftime('%Y%m%dT%H%M%S')}"
                try:
                    f.replace(dest)
                    rec["quarantined_to"] = str(dest.relative_to(universe))
                except OSError as mv:
                    rec["quarantine_failed"] = f"{type(mv).__name__}: {str(mv)[:60]}"
            corrupt.append(rec)
            continue
        age_days = (now - last).total_seconds() / 86400.0
        if age_days > stale_days:
            sym = f.name.rsplit("_", 1)[0]
            stale.append({"file": f.name, "symbol": sym, "last_bar": str(last)[:19],
                          "age_days": round(age_days, 1), "asset_class": _asset_class(sym)})
    by_class = Counter(s["asset_class"] for s in stale)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "universe": str(universe), "n_files": n, "stale_days": stale_days,
        "n_corrupt": len(corrupt), "corrupt": corrupt,
        "n_stale": len(stale), "stale_by_class": dict(by_class), "stale": stale[:200],
        "rule": ("unreadable -> moved to _corrupt/ for the fetcher to rebuild and a post-mortem "
                 "to read; stale -> reported by asset class; nothing is deleted"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-quarantine", action="store_true")
    args = ap.parse_args(argv)
    doc = scan(quarantine=not args.no_quarantine)
    print(f"universe integrity: {doc['n_files']} files, {doc['n_corrupt']} corrupt "
          f"(quarantined), {doc['n_stale']} stale >{doc['stale_days']}d "
          f"{doc['stale_by_class']} -> {OUT}")
    return 1 if any(c.get("quarantine_failed") for c in doc["corrupt"]) else 0


if __name__ == "__main__":
    sys.exit(main())
