#!/usr/bin/env python3
"""CROSS-EXCHANGE FUNDING-SPREAD SCREEN (R0115) -- the desk's candidate SECOND SLEEVE.

WHY THIS IS THE HIGHEST-EV CANDIDATE ON THE BOARD. The deployed carry sleeve earns the funding
LEVEL: it makes money when perps are expensive and nothing when funding is flat, so its returns
are one bet on one regime. This earns the SPREAD between venues -- long funding where it is cheap,
short where it is rich -- which is a mechanically DIFFERENT payoff: the spread can be wide in
exactly the flat-level regimes that starve the carry book. A genuinely decorrelated second sleeve
is the single strongest lever on GEOMETRIC growth available to this desk, because reducing
variance drag raises the compounding mean directly (L1.23/Kelly: it is not just more return, it
is more return per unit of the risk the rail actually constrains).

THE MECHANISM, stated so it can be killed: perp funding is set per-venue by each venue's own
leverage imbalance, and the venues have SEGMENTED participants (retail-heavy vs institution-heavy,
different collateral, different KYC regimes, different liquidation engines). Segmentation means
the imbalances do not equalise instantly, so a spread persists beyond the cost of trading it.
FALSIFIER: if the measured spread is smaller than the round-trip cost of holding both legs, or if
it mean-reverts faster than one funding interval, the mechanism is real but UNHARVESTABLE and the
axis is graveyarded with that reason.

HONEST SCOPE, and this matters: this is STAGE A -- it screens whether the spread carries
predictive information, and earns at most a pre-registered forward clock. It has ZERO promotion
authority (L1.6) and this file places no orders. The delta-neutral-per-leg construction question
(each leg is itself a cash-and-carry) is an EXECUTION design owed before any sizing, and is
deliberately out of scope here.

    python scripts/screen_funding_spread.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.funding_mechanics import settlement_lag_periods  # noqa: E402

#: venue -> (jsonl path, timestamp field candidates, symbol field candidates, rate field
#: candidates). Collectors were written independently and do NOT share a schema, so the reader
#: is tolerant by design -- and a venue whose file is absent is REPORTED, never silently dropped
#: (a screen that quietly runs on 1 of 4 venues would report a null that means nothing).
_VENUES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "bitmex": ("data/bitmex_funding.jsonl", ("timestamp", "ts", "at", "time"),
               ("symbol", "coin", "asset"), ("fundingRate", "funding", "rate", "bn_funding")),
    "hyperliquid": ("data/hyperliquid_funding.jsonl", ("timestamp", "ts", "at", "time"),
                    ("coin", "symbol", "asset"), ("hl_funding", "funding", "rate")),
    "binance": ("data/binance_funding.jsonl", ("timestamp", "ts", "at", "time"),
                ("symbol", "coin"), ("bn_funding", "fundingRate", "funding", "rate")),
}


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def _norm_symbol(raw: object) -> str:
    """BTC / BTCUSDT / XBTUSD -> BTC. Cross-venue joins fail silently on symbol format, and a
    silent join failure produces an empty screen that looks like an honest null."""
    s = str(raw or "").upper()
    for suffix in ("USDT", "USD", "PERP", "-PERP", "_PERP"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return {"XBT": "BTC"}.get(s.strip("-_"), s.strip("-_"))


#: Nominal settlement interval used to convert a venue's payment LAG into hours. BitMEX XBTUSD
#: measures 11,126 of 11,147 gaps at exactly 8.0h, so 8h is the right nominal for the lag shift;
#: per-symbol interval switching is a separate fence (funding_mechanics.detect_interval_switches).
_NOMINAL_INTERVAL_H = 8.0


def _hour_key(raw: object, shift_h: float = 0.0) -> str | None:
    """Bucket to the hour -- funding stamps differ by seconds across venues; joining on exact
    timestamps yields near-zero overlap and a fake null.

    ``shift_h`` moves the stamp to the hour the rate is actually PAID. OKX and BitMEX apply a rate
    ONE PERIOD AFTER the window that computed it, so bucketing BitMEX on its computation stamp and
    joining it to Binance -- which pays immediately -- compared a rate already settled against one
    that had not settled yet, a full 8h of cross-venue misalignment on the exact series this screen
    is built from. §26(4): the alignment is now DECLARED (see `alignment` in the report), not
    inferred by whoever reads the output.
    """
    s = str(raw or "")
    try:
        if s.replace(".", "", 1).isdigit():
            ts = float(s)
            dt = datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts, tz=UTC)
        else:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, OSError, OverflowError):
        return None
    if shift_h:
        dt += timedelta(hours=shift_h)
    return dt.strftime("%Y-%m-%dT%H")


def venue_alignment(venue: str) -> tuple[float, str]:
    """(hours to shift, provenance) for ``venue``'s payment timing.

    REFUSES TO GUESS. A venue whose mechanics this desk has not read gets a 0.0 shift and says so
    as UNREAD -- it does NOT silently inherit Binance's immediate-payment convention, which is the
    assumption that produced the misalignment in the first place. Same discipline as the absent-file
    branch above: report the gap, never paper over it.
    """
    lag = settlement_lag_periods(venue)
    if lag is None:
        return 0.0, "UNREAD"
    return _NOMINAL_INTERVAL_H * lag, ("PAYMENT-LAGGED" if lag else "IMMEDIATE")


def load_venue(root: Path, venue: str) -> dict[tuple[str, str], float]:
    """(symbol, PAYMENT hour) -> funding rate. Missing file -> empty dict (reported by caller)."""
    rel, tsk, symk, ratek = _VENUES[venue]
    shift_h, _ = venue_alignment(venue)
    out: dict[tuple[str, str], float] = {}
    try:
        lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return out
    for ln in lines:
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        hour, sym, rate = _hour_key(_first(row, tsk), shift_h), \
            _norm_symbol(_first(row, symk)), _first(row, ratek)
        if hour and sym and isinstance(rate, (int, float)):
            out[(sym, hour)] = float(rate)
    return out


def build_spreads(root: Path) -> dict[str, Any]:
    """Every venue pair's per-(symbol,hour) funding spread, plus an honest coverage report."""
    loaded = {v: load_venue(root, v) for v in _VENUES}
    coverage = {v: len(d) for v, d in loaded.items()}
    pairs: dict[str, list[dict[str, Any]]] = {}
    names = sorted(loaded)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            keys = sorted(set(loaded[a]) & set(loaded[b]))
            if not keys:
                continue
            pairs[f"{a}|{b}"] = [
                {"symbol": s, "hour": h, "spread": loaded[a][(s, h)] - loaded[b][(s, h)],
                 a: loaded[a][(s, h)], b: loaded[b][(s, h)]} for s, h in keys]
    return {"coverage_rows": coverage, "pairs": pairs,
            "venues_absent": [v for v, n in coverage.items() if n == 0]}


def summarise(spreads: dict[str, Any], *, round_trip_bps: float = 8.0) -> dict[str, Any]:
    """Is the spread BIGGER than the cost of harvesting it? That question decides the axis.

    round_trip_bps is per-8h-cycle cost of holding both legs (two venues, two legs each). It is
    a MODEL input, not a measurement -- the real number comes from the tape once live, and a
    screen that ignores costs is how a phantom edge gets a clock (L1.5)."""
    out: dict[str, Any] = {}
    thresh = round_trip_bps / 10_000.0
    for pair, rows in spreads.get("pairs", {}).items():
        vals = [abs(float(r["spread"])) for r in rows]
        if not vals:
            continue
        n = len(vals)
        mean_abs = sum(vals) / n
        harvestable = sum(1 for v in vals if v > thresh)
        out[pair] = {
            "n_obs": n,
            "mean_abs_spread_bps": round(mean_abs * 10_000, 3),
            "max_abs_spread_bps": round(max(vals) * 10_000, 3),
            "pct_above_round_trip_cost": round(100.0 * harvestable / n, 1),
            "round_trip_bps_assumed": round_trip_bps,
            "verdict": ("HARVESTABLE-CANDIDATE" if harvestable / n > 0.10 else
                        "BELOW-COST -- mechanism may be real but is UNHARVESTABLE; graveyard "
                        "with that reason unless costs fall"),
        }
    return out


def build_report(root: Path | None = None, *, round_trip_bps: float = 8.0) -> dict[str, Any]:
    root = root or _ROOT
    sp = build_spreads(root)
    summary = summarise(sp, round_trip_bps=round_trip_bps)
    n_pairs = len(sp.get("pairs", {}))
    if not n_pairs:
        status = "NO-DATA"
        detail = (f"no overlapping (symbol,hour) rows across venues; coverage="
                  f"{sp['coverage_rows']}, absent={sp['venues_absent']}. This is UNMEASURED, "
                  "not a null -- fix collection or the join before reading anything into it")
    else:
        status = "SCREENED"
        detail = f"{n_pairs} venue pair(s) with overlap; " + "; ".join(
            f"{p}: {d['pct_above_round_trip_cost']}% of {d['n_obs']} obs above cost"
            for p, d in summary.items())
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "axis": "cross_exchange_funding_spread", "row": "R0115", "stage": "A",
        "status": status, "detail": detail,
        "coverage_rows": sp["coverage_rows"], "venues_absent": sp["venues_absent"],
        "pairs": summary,
        "mechanism": "segmented participants per venue -> leverage imbalances do not equalise "
                     "instantly -> a funding spread persists beyond its trading cost",
        "falsifier": "spread below round-trip cost, or reverting faster than one funding "
                     "interval => real but UNHARVESTABLE; graveyard with that reason",
        "authority": "STAGE A ONLY -- earns at most a pre-registered forward clock, never "
                     "capital (L1.6). This script places no orders.",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--round-trip-bps", type=float, default=8.0)
    args = ap.parse_args()
    rep = build_report(round_trip_bps=args.round_trip_bps)
    out = _ROOT / "data/funding_spread_screen.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"funding-spread screen (R0115): {rep['status']} -- {rep['detail']}\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
