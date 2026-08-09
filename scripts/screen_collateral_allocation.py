#!/usr/bin/env python3
"""COLLATERAL ALLOCATION SCREEN (R0120) -- is cash-and-carry actually the best use of our USDT?

THE UNASKED ASSUMPTION THIS TESTS, and it sits under every capacity decision the desk makes.
Every sizing band, every capacity ratio, every "deployed capital" number assumes the base
allocation for the desk's collateral is CASH-AND-CARRY. Nobody ever computed the alternative --
while `data/defi_lending.jsonl` has been collected DAILY and read by nothing. The same USDT can
sit in a lending pool earning a measurable, near-riskless supply APY with no basis risk, no perp
leg, no liquidation engine and no venue counterparty on the derivative side.

THE COMPARISON, per period, net of what each side actually costs:
    carry_net   = annualised funding harvest  -  round-trip execution cost amortised over the
                  expected hold  -  the borrow/margin drag of the perp leg
    lending_net = supply APY  -  gas/bridging amortised  -  a HAIRCUT for smart-contract and
                  depeg risk, which is NOT zero and must never be modelled as zero
The verdict is deliberately NOT "pick the winner once". Funding is regime-dependent and lending
is comparatively stable, so the honest output is a REGIME MAP: which allocation wins in the
high-funding regime, which wins in the flat regime, and how often each regime occurs. If lending
wins the flat regime by more than the switching cost, the correct book is REGIME-SWITCHED, and
the desk has been leaving that yield on the table in every flat window it has ever traded.

WHY THIS IS NOT A "MOVE TO DEFI" PROPOSAL. Lending carries risks the carry book does not:
contract exploit, oracle failure, stablecoin depeg, withdrawal queues in stress -- exactly when
you want the capital back. So the haircut is a first-class input, the screen REFUSES to run with
haircut=0, and the output is evidence for an allocation decision, never an instruction. Stage A,
zero promotion authority (L1.6); this file moves no funds.

    python scripts/screen_collateral_allocation.py [--haircut-bps N] [--json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
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

#: Funding above this |8h rate| is the "high-funding regime" (~11% annualised at 3 prints/day).
HIGH_FUNDING_8H = 0.0001
#: Smart-contract + depeg + withdrawal-queue haircut on lending yield. NEVER zero: the risks are
#: real, rare and correlated with exactly the moments you need the collateral back.
DEFAULT_HAIRCUT_BPS = 300.0
_PERIODS_PER_YEAR = 3 * 365                       # 8h funding prints


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        out = []
        for ln in path.read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
        return out
    except OSError:
        return []


def best_lending_apy(root: Path, *, stable_only: bool = True) -> tuple[float | None, str]:
    """Best observed stablecoin SUPPLY apy, as a fraction. Returns (apy, provenance)."""
    rows = _rows(root / "data/defi_lending.jsonl")
    if not rows:
        return None, "data/defi_lending.jsonl absent or empty on this host"
    best, where = None, ""
    for r in rows:
        # Bound ONCE and then narrowed. Calling r.get("data") twice -- once in the isinstance
        # test, once for the value -- gives mypy nothing to narrow, and is genuinely two reads of
        # a mutable mapping besides.
        data = r.get("data")
        pools = data if isinstance(data, list) else [r]
        for p in pools:
            if not isinstance(p, dict):
                continue
            sym = str(p.get("symbol") or p.get("asset") or p.get("token") or "").upper()
            if stable_only and not any(s in sym for s in ("USDT", "USDC", "DAI", "USD")):
                continue
            apy = p.get("supply_apy", p.get("apy", p.get("supplyApy")))
            if isinstance(apy, (int, float)):
                # feeds publish either percent (5.2) or fraction (0.052)
                val = float(apy) / 100.0 if float(apy) > 1.0 else float(apy)
                if best is None or val > best:
                    best, where = val, f"{p.get('project', p.get('chain', '?'))}:{sym}"
    return best, (where or "no stablecoin supply rows found")


def funding_regimes(root: Path) -> dict[str, Any]:
    """Split observed funding into high/flat regimes -- the axis the allocation question turns on."""
    rates: list[float] = []
    for name in ("bitmex_funding.jsonl", "hyperliquid_funding.jsonl", "binance_funding.jsonl"):
        for r in _rows(root / "data" / name):
            for k in ("fundingRate", "funding", "rate", "bn_funding", "hl_funding"):
                v = r.get(k)
                if isinstance(v, (int, float)):
                    rates.append(abs(float(v)))
                    break
    if not rates:
        return {"n": 0, "measured": False}
    high = [x for x in rates if x >= HIGH_FUNDING_8H]
    flat = [x for x in rates if x < HIGH_FUNDING_8H]
    return {
        "n": len(rates), "measured": True,
        "pct_high_regime": round(100.0 * len(high) / len(rates), 1),
        "high_regime_apy": round(statistics.mean(high) * _PERIODS_PER_YEAR, 4) if high else None,
        "flat_regime_apy": round(statistics.mean(flat) * _PERIODS_PER_YEAR, 4) if flat else None,
    }


def build_report(root: Path | None = None, *, haircut_bps: float = DEFAULT_HAIRCUT_BPS,
                 carry_cost_bps_annual: float = 200.0) -> dict[str, Any]:
    if haircut_bps <= 0:
        raise ValueError(
            "haircut_bps must be > 0: smart-contract, depeg and withdrawal-queue risk are real "
            "and correlated with the moments you need the collateral back. Modelling them as "
            "zero is how a screen manufactures a winner (L1.5).")
    root = root or _ROOT
    apy, prov = best_lending_apy(root)
    reg = funding_regimes(root)
    lending_net = None if apy is None else apy - haircut_bps / 10_000.0

    verdict, detail = "UNMEASURED", ""
    regime_map: dict[str, Any] = {}
    if apy is None or not reg.get("measured"):
        missing = [x for x, ok in (("lending feed", apy is not None),
                                   ("funding history", reg.get("measured"))) if not ok]
        detail = (f"cannot compare: missing {', '.join(missing)}. UNMEASURED is NOT 'carry wins' "
                  "-- the assumption stays untested until both sides are readable")
    else:
        # `apy is None` was handled above, so lending_net is real here -- but it was computed
        # through a separate name and mypy cannot carry the narrowing across it. Re-derived from
        # the narrowed `apy` rather than asserted or ignored: an assert would be a runtime cost
        # for a fact the branch already guarantees, and a type-ignore would hide the next genuine
        # None that arrives here.
        lending_net_f = float(apy) - haircut_bps / 10_000.0
        cost = carry_cost_bps_annual / 10_000.0
        for name, key in (("high_funding", "high_regime_apy"), ("flat_funding", "flat_regime_apy")):
            gross = reg.get(key)
            if gross is None:
                continue
            carry_net = float(gross) - cost
            regime_map[name] = {
                "carry_net_apy": round(carry_net, 4),
                "lending_net_apy": round(lending_net_f, 4),
                "winner": "carry" if carry_net > lending_net_f else "lending",
                "edge_apy": round(abs(carry_net - lending_net_f), 4),
            }
        winners = {v["winner"] for v in regime_map.values()}
        if winners == {"carry"}:
            verdict = "CARRY-DOMINANT"
            detail = "carry beats haircut-adjusted lending in every measured regime -- the base "
        elif winners == {"lending"}:
            verdict = "LENDING-DOMINANT"
            detail = ("haircut-adjusted lending beats carry in EVERY measured regime -- this "
                      "questions the desk's base allocation outright and owes a principal "
                      "decision, not a code change")
        elif winners:
            verdict = "REGIME-SWITCHED"
            detail = ("the winner CHANGES with the funding regime -- the correct book switches "
                      "allocation rather than always-carry; size the switch against its cost")
        if verdict == "CARRY-DOMINANT":
            detail += "assumption is VALIDATED (first time it has ever been tested)"

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "axis": "collateral_allocation_carry_vs_lending", "row": "R0120", "stage": "A",
        "status": verdict, "detail": detail,
        "best_lending_apy": apy, "lending_provenance": prov,
        "haircut_bps": haircut_bps, "lending_net_apy": lending_net,
        "carry_cost_bps_annual": carry_cost_bps_annual,
        "funding_regimes": reg, "regime_map": regime_map,
        "authority": "STAGE A -- evidence for an allocation decision. Moves no funds, places no "
                     "orders, and never auto-switches the book (L1.6).",
        "note": "the haircut is a MODEL input, not a measurement: contract exploit, oracle "
                "failure, depeg and withdrawal queues in stress. Re-run at several haircuts "
                "before believing any verdict -- if the winner flips inside a plausible haircut "
                "range, the honest answer is 'too close to call'.",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--haircut-bps", type=float, default=DEFAULT_HAIRCUT_BPS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(haircut_bps=args.haircut_bps)
    out = _ROOT / "data/collateral_allocation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"collateral allocation (R0120): {rep['status']} -- {rep['detail']}\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
