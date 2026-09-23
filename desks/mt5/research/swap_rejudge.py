"""Re-price every certificate against the financing the engine never charged.

THE DEFECT IS NOW FIXED UPSTREAM AND THAT DOES NOT HELP THE CERTIFICATES ALREADY MINTED.
`mt5desk.engine.Costs` gained `swap_per_lot_per_night` on 2026-09-15 and `from_symbol` reads
`swap_long`/`swap_short` out of the registry, so every gauntlet run FROM NOW ON charges overnight
financing. Every certificate minted BEFORE that was judged with zero swap, and those are the ones
holding forward clocks and drawing capital today. A fix that only protects future work leaves the
live book priced on the old arithmetic.

SO THIS IS THE RECONCILIATION PASS, and it is a cost delta rather than a re-run on purpose. The
swap charge is an exact arithmetic consequence of three measured numbers -- the venue's published
swap points, the nights the sleeve's own trades actually crossed, and its stop distance -- none of
which requires re-simulating anything. Re-running 58 cells through the gauntlet would take hours
and would answer the same question with more moving parts and a new set of trials to charge for.

NIGHTS ARE MEASURED FROM THE SLEEVE'S OWN LEDGER, NOT FROM A FAMILY TABLE. `cost_to_edge` assumes
NIGHTS_HELD = 1.0 for a list of families believed to hold overnight, and that was the right
expedient for a fence written at speed. It is wrong in both directions: `session_range_breakout`
is on the intraday list and its afternoon window can hold through a rollover, and a family that
holds is charged one night when its median trade crosses two. The shadow ledgers carry entry_time
and exit_time per trade, so `rollovers_between` counts the real thing -- including Wednesday's
triple charge, which is 43% of a week's financing on one instant.

A CERTIFICATE WITH NO LEDGER IS UNMEASURED, NEVER ZERO. That is the whole of L1.28a and it is the
failure mode this pass exists to avoid: a sleeve whose financing cannot be counted must not clear
a financing fence by default, because that is precisely how an unpriced instrument gets funded.

    python desks/mt5/research/swap_rejudge.py
    python desks/mt5/research/swap_rejudge.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SHADOW = BASE / "reports" / "shadow"
UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
OUT = BASE / "reports" / "SWAP_REJUDGE.json"

#: Share of a certificate's measured edge that FINANCING ALONE may consume before the certificate
#: is called cost-negative. Deliberately the same bar `cost_to_edge` applies to total round-trip
#: cost, and deliberately applied to financing ALONE here: spread and commission were already in
#: the backtest that minted the certificate, so this pass is measuring the charge that was NOT.
MAX_SWAP_FRACTION_OF_EDGE = 0.50

#: Below this the certificate is flagged AT_RISK rather than passed silently. Edge is an estimate
#: with a standard error; financing is a published rate. When the uncertain half is only twice the
#: certain half, one bad estimate is the difference between funded and negative.
AT_RISK_FRACTION = 0.25


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _stop_distance(symbol: str) -> tuple[float | None, str]:
    """2 x ATR20 on the finest chart on disk, in PRICE UNITS. The desk's standing stop unit."""
    try:
        import pandas as pd
    except ImportError:
        return None, "pandas unavailable"
    for tf in ("H1", "M15", "M5", "M30", "M1"):
        f = UNIVERSE / f"{symbol}_{tf}.parquet"
        if not f.exists():
            continue
        try:
            df = pd.read_parquet(f, columns=["high", "low"])
        except Exception:
            continue
        if len(df) < 25:
            continue
        atr = float((df["high"] - df["low"]).rolling(20).mean().iloc[-1])
        if atr > 0:
            return 2.0 * atr, f"2xATR20 on {tf} ({len(df)} bars)"
    return None, f"no chart on disk carries 20 usable bars for {symbol}"


def _ledger_nights(symbol: str, family: str, window: str) -> dict[str, Any]:
    """Nights per trade from the sleeve's OWN forward ledger.

    THE MEAN, NOT THE MEDIAN, AND THE FIRST VERSION OF THIS FILE GOT IT WRONG. It took the median
    and reported AUDCAD as owing zero financing because only 5% of its trades cross a rollover --
    but the number being charged against is an EXPECTANCY, and the expected financing per trade is
    E[nights], which those 5% are part of. A median charges the typical trade and lets the tail
    that actually pays disappear; on a family where one trade in twenty holds through a weekend
    that tail is the whole cost.

    The median and the share crossing are still reported, because they say something the mean
    cannot: whether this is a family that holds, or an intraday family with an occasional
    straggler. Those want different remedies.

    WHICH FILE ANSWERED IS PART OF THE ANSWER. The exact ledger is preferred, then symbol+family,
    then symbol alone -- and the fallback is NAMED in the record rather than silently pooling
    another sleeve's holding behaviour into this one's cost.
    """
    from mt5desk.engine import rollovers_between

    match = "exact"
    exact = SHADOW / f"ledger_{symbol}_{family}_{window}.json"
    cands = [exact] if exact.exists() else []
    if not cands:
        match = "symbol+family"
        cands = sorted(SHADOW.glob(f"ledger_{symbol}_{family}_*.json"))
    if not cands:
        match = "symbol only (POOLED: another sleeve's holding behaviour)"
        cands = sorted(SHADOW.glob(f"ledger_{symbol}_*.json"))
    if not cands:
        return {"nights": None, "why": f"no shadow ledger on disk for {symbol}", "n": 0,
                "ledgers": [], "match": "none"}
    rows: list[dict[str, Any]] = []
    for c in cands:
        r = _read(c, [])
        if isinstance(r, list):
            rows.extend(x for x in r if isinstance(x, dict))
    nights: list[float] = []
    for r in rows:
        a, b = r.get("entry_time"), r.get("exit_time")
        if not a or not b:
            continue
        try:
            nights.append(float(rollovers_between(a, b)))
        except Exception:
            continue
    if not nights:
        return {"nights": None, "why": f"ledger(s) for {symbol} carry no dated trade", "n": 0,
                "ledgers": [c.name for c in cands], "match": match}
    mean = sum(nights) / len(nights)
    ordered = sorted(nights)
    med = ordered[len(ordered) // 2]
    frac_over = sum(1 for n in nights if n > 0) / len(nights)
    return {
        "nights": mean, "n": len(nights), "match": match,
        "ledgers": [c.name for c in cands][:6],
        "median_nights": med, "share_crossing_a_rollover": round(frac_over, 4),
        "max_nights": max(nights),
        "why": (f"MEAN over {len(nights)} recorded trade(s) from {len(cands)} ledger(s) "
                f"[{match}]; median {med:.0f}, {frac_over:.0%} cross a rollover, worst "
                f"{max(nights):.0f}"),
    }


def rejudge() -> dict[str, Any]:
    from mt5desk.engine import Costs

    doc = _read(SURVIVORS, {})
    survivors = doc.get("survivors") or {}
    registry = _read(REGISTRY, {})
    rows: list[dict[str, Any]] = []

    for key, cert in sorted(survivors.items()):
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or cert.get("sym") or "").upper()
        fam = str(spec.get("family") or "")
        win = str(spec.get("selector") or spec.get("window") or "")
        gates = cert.get("gates") or {}
        ev = (gates.get("expected_value") or {}).get("ev")
        edge_r = float(ev) if isinstance(ev, (int, float)) else None

        rec: dict[str, Any] = {"certificate": key, "symbol": sym, "family": fam, "window": win,
                               "edge_r": edge_r}
        meta = registry.get(sym)
        if not isinstance(meta, dict):
            rec.update({"verdict": "UNMEASURED",
                        "why": f"{sym} is not in the universe registry: no swap rate to charge"})
            rows.append(rec)
            continue

        costs = Costs.from_symbol(meta)
        per_unit_night = costs.swap_per_lot_per_night / (costs.contract_oz or 1.0)
        rec["swap_points_worse_side"] = round(
            max(abs(float(meta.get("swap_long") or 0.0)),
                abs(float(meta.get("swap_short") or 0.0))), 2)
        rec["swap_price_units_per_night"] = round(per_unit_night, 8)

        led = _ledger_nights(sym, fam, win)
        nights, why_n = led["nights"], led["why"]
        rec["nights_per_trade"] = round(nights, 4) if nights is not None else None
        rec["nights_basis"] = why_n
        rec["nights_detail"] = {k: v for k, v in led.items() if k not in ("nights", "why")}
        stop, why_s = _stop_distance(sym)
        rec["stop_distance"] = round(stop, 6) if stop else None
        rec["stop_basis"] = why_s

        if nights is None or stop is None:
            rec.update({"verdict": "UNMEASURED",
                        "why": why_n if nights is None else why_s})
            rows.append(rec)
            continue

        swap_r = (per_unit_night * nights) / stop
        rec["swap_charge_r"] = round(swap_r, 5)
        if edge_r is None or not (edge_r > 0):
            rec.update({"verdict": "UNMEASURED",
                        "why": "the certificate records no positive expected value to charge "
                               "against"})
            rows.append(rec)
            continue
        rec["edge_r_after_swap"] = round(edge_r - swap_r, 5)
        frac = swap_r / edge_r
        rec["swap_fraction_of_edge"] = round(frac, 4)
        if frac >= 1.0:
            rec.update({"verdict": "COST_NEGATIVE",
                        "why": (f"financing alone is {frac:.0%} of the certified edge "
                                f"{edge_r:.3f}R. This certificate was minted by an engine that "
                                f"charged no swap; charged, it does not exist.")})
        elif frac > MAX_SWAP_FRACTION_OF_EDGE:
            rec.update({"verdict": "COST_NEGATIVE",
                        "why": (f"financing is {frac:.0%} of the certified edge, over the "
                                f"{MAX_SWAP_FRACTION_OF_EDGE:.0%} bar. Cost is a published rate "
                                f"and edge is an estimate; the uncertain half is the small one.")})
        elif frac > AT_RISK_FRACTION:
            rec.update({"verdict": "AT_RISK",
                        "why": (f"financing takes {frac:.0%} of the certified edge. Survives, "
                                f"and one revision of the estimate away from not.")})
        else:
            rec.update({"verdict": "SURVIVES",
                        "why": (f"financing is {frac:.0%} of the certified edge"
                                if nights else
                                "the sleeve's own trades cross no rollover: none is owed")})
        rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    negative = [r for r in rows if r["verdict"] == "COST_NEGATIVE"]
    negative.sort(key=lambda r: -(r.get("swap_fraction_of_edge") or 0))
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("every certificate on this desk was minted by an engine that charged ZERO "
                 "overnight financing. This re-prices each one against the venue's published "
                 "swap and the nights its OWN trades crossed. Unmeasured is a verdict, never a "
                 "pass."),
        "engine_fix": ("mt5desk.engine.Costs.swap_per_lot_per_night, wired through from_symbol "
                       "on 2026-09-15; runs from now on charge it automatically"),
        "max_swap_fraction_of_edge": MAX_SWAP_FRACTION_OF_EDGE,
        "n_certificates": len(rows),
        "census": dict(census),
        "cost_negative": negative,
        "records": rows,
    }


def cost_negative_keys() -> set[str]:
    """Certificates the financing re-judge refuses. Read by the promoter; fails OPEN on absence.

    Fails open deliberately: this report is the evidence, and a missing report is not evidence of
    a refusal. What must never happen is the opposite -- a COST_NEGATIVE row silently promoted --
    and `check_swap_pricing.py` is what keeps the report present.
    """
    doc = _read(OUT, {})
    return {str(r.get("certificate")) for r in (doc.get("cost_negative") or [])
            if isinstance(r, dict) and r.get("certificate")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the document and write nothing")
    args = ap.parse_args(argv)

    doc = rejudge()
    if args.json:
        print(json.dumps(doc, indent=1))
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"swap re-judge: {doc['n_certificates']} certificate(s) re-priced -> {doc['census']}")
    if doc["cost_negative"]:
        print("\n  COST_NEGATIVE -- certified with zero financing, negative with it:")
        print(f"  {'certificate':56} {'edge_R':>8} {'swap_R':>8} {'nights':>7} {'share':>7}")
        for r in doc["cost_negative"][:20]:
            print(f"  {str(r['certificate'])[:56]:56} {r.get('edge_r') or 0:8.3f} "
                  f"{r.get('swap_charge_r') or 0:8.3f} {r.get('nights_per_trade') or 0:7.1f} "
                  f"{(r.get('swap_fraction_of_edge') or 0):7.0%}")
    unmeasured = [r for r in doc["records"] if r["verdict"] == "UNMEASURED"]
    if unmeasured:
        print(f"\n  UNMEASURED {len(unmeasured)} -- a verdict, not a pass:")
        for r in unmeasured[:6]:
            print(f"    {str(r['certificate'])[:52]:52} {str(r.get('why'))[:60]}")
    print(f"  -> {OUT}")
    # COST_NEGATIVE is the fatal verdict: those certificates are drawing capital on an edge that
    # was never net of its largest cost.
    return 1 if doc["census"].get("COST_NEGATIVE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
