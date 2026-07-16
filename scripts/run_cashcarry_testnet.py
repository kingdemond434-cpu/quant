"""Paper CASH-AND-CARRY executor: long spot (spot testnet) + short perp (futures testnet).

Delta-neutral funding harvest: on the highest POSITIVE-funding perps that exist on BOTH testnets, it
BUYS spot (long leg) and SHORTS the perp (hedge leg), dollar-matched -> ~zero price exposure, and
collects funding on the short perp. Both legs are paper (testnet). dry-run DEFAULT; --live to send.

This is the executable form of the strongest backtest candidate. It is STILL UNVALIDATED (forward
shadow day 0/90), so this runs on PAPER only -- it builds an executed forward track record, it does
not touch real money. Only positive-funding names are traded (the long-spot/short-perp carry); the
reverse leg (short spot) needs margin and is skipped.

    python scripts/run_cashcarry_testnet.py                       # dry-run
    python scripts/run_cashcarry_testnet.py --live --top 5 --capital 2000
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from libs.data.crypto_source import current_funding
from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut

_WEB = Path("web/cashcarry_live.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="number of positive-funding carries")
    ap.add_argument("--capital", type=float, default=2000.0, help="total spot $ to deploy")
    ap.add_argument("--live", action="store_true", help="send orders (default = dry-run)")
    args = ap.parse_args()
    dry = not args.live
    if not (spot.has_keys() and fut.has_keys()):
        raise SystemExit("need BOTH spot-testnet and futures-testnet keys")

    funding = current_funding()
    spot_fl, fut_fl = spot.exchange_filters(), fut.exchange_filters()
    spot_px = spot.prices()
    # positive funding, tradeable on BOTH venues, USDT-quoted
    cands = sorted(((s, f) for s, f in funding.items()
                    if f > 0 and s in spot_fl and s in fut_fl and s.endswith("USDT")
                    and spot_px.get(s)),
                   key=lambda x: -x[1])[:args.top]
    if not cands:
        raise SystemExit("no positive-funding carry candidates on both venues right now")

    per = args.capital / len(cands)
    legs: list[dict[str, object]] = []
    for sym, f in cands:
        px = spot_px[sym]
        ffl = fut_fl[sym]
        step, prec = ffl["step"], int(ffl["qty_prec"])
        qty = round(round((per / px) / step) * step, prec) if step > 0 else round(per / px, prec)
        if qty < ffl["min_qty"] or qty <= 0:
            continue
        leg: dict[str, object] = {"symbol": sym, "funding_rate": round(f, 6), "qty": qty,
                                  "notional": round(qty * px, 2)}
        if dry:
            leg["status"] = "DRY (would BUY spot + SHORT perp)"
        else:
            try:
                sres = spot.place_market(sym, "BUY", qty)           # long leg
                fres = fut.place_market(sym, "SELL", qty)           # short-perp hedge leg
                leg["spot"] = str(sres.get("status", "?"))
                leg["perp"] = str(fres.get("status", "?"))
            except Exception as e:
                leg["error"] = repr(e)[:140]
        legs.append(leg)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mode": "dry" if dry else "live-paper",
        "strategy": "delta-neutral cash-and-carry (long spot + short perp, positive funding)",
        "n_carries": len(legs),
        "spot_usdt": round(spot.usdt_balance(), 2),
        "spot_account_value": spot.account_value_usdt(),
        "futures_equity": round(fut.account_summary()["equity"], 2) if fut.has_keys() else None,
        "legs": legs,
        "note": ("PAPER. Long spot hedges the short perp -> ~zero directional risk; you collect "
                 "funding on the short perp. Unvalidated (forward shadow day 0/90)."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    print(f"cash-carry {'DRY-RUN' if dry else 'LIVE-PAPER'}: {len(legs)} carries "
          f"(top funding {cands[0][0]} {cands[0][1]*100:.3f}%/8h) | spot ${out['spot_usdt']} "
          f"USDT | futures ${out['futures_equity']}")
    for lg in legs:
        print(f"  {lg['symbol']:12} funding {lg['funding_rate']} qty {lg['qty']} "
              f"~${lg['notional']} {lg.get('status') or (lg.get('spot'), lg.get('perp'))}")


if __name__ == "__main__":
    main()
