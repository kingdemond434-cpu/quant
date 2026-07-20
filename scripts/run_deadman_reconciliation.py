"""Read-only forensic reconciliation for the 2026-07-19 14:27Z dead-man fire (GAP register row 34).

Maps the observed spot USDT delta (-$1,837.68) and the equity discrepancy (785.35 latch-read vs
~2,409 reconstructed) to specific Binance testnet venue records: per-symbol spot fills (myTrades),
futures fills + realized PnL (myTrades), and futures funding/commission income (income history).

Pure diagnostic -- issues zero orders, writes no executor/risk-path state, never touches
scripts/run_deadman_switch.py or its state files. Output is a dated markdown+json dossier for the
CRO/principal to read before any reset decision (data/PRINCIPAL_ACTION.md stays gated on this).

    .venv/bin/python scripts/run_deadman_reconciliation.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut

_ROOT = Path(__file__).resolve().parent.parent
_TRADES = _ROOT / "data" / "cashcarry_trades.json"
_OUT_MD = _ROOT / "data" / "DEADMAN_RECONCILIATION_20260719.md"
_OUT_JSON = _ROOT / "data" / "deadman_reconciliation_20260719.json"

_INCIDENT_START = datetime.fromisoformat("2026-07-19T14:00:00+00:00")
_INCIDENT_END = datetime.fromisoformat("2026-07-19T14:40:00+00:00")
# wide net: any round-trip whose [opened, closed] interval overlaps this window.
# The dead-man's usdt_baseline (99,566.37) was set at the 07-17T23:05Z reset #2 epoch, not at the
# incident -- the observed -$1,837.68 delta is measured against THAT baseline, so the scan must
# cover the full ~39h span back to the reset, not just the incident window, or the reconciliation
# silently mis-scopes and any close match to the full delta is coincidence, not proof.
_SCAN_START = datetime.fromisoformat("2026-07-17T23:05:00+00:00")
_SCAN_END = datetime.fromisoformat("2026-07-19T15:00:00+00:00")
_BUFFER_MS = 90_000  # 90s pad around each recorded open/close to catch adjacent partial fills


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _parse(v: str) -> datetime:
    return datetime.fromisoformat(v)


def _relevant_trades() -> list[dict]:
    rows = json.loads(_TRADES.read_text("utf-8"))
    out = []
    for t in rows:
        opened = _parse(t["opened"]) if t.get("opened") else None
        closed = _parse(t["closed"]) if t.get("closed") else None
        lo = opened or closed
        hi = closed or opened
        if lo is None:
            continue
        if hi < _SCAN_START or lo > _SCAN_END:
            continue
        out.append(t)
    return out


def _spot_symbol(perp_symbol: str) -> str:
    return perp_symbol  # cash-and-carry trades the identical pair on spot + perp testnets


_SPOT_CHUNK_MS = 20 * 3600 * 1000   # venue caps startTime..endTime at 24h on spot myTrades; 20h margin
_FUT_CHUNK_MS = 6 * 24 * 3600 * 1000  # venue caps at 7d on futures userTrades; 6d margin


def _chunked_trades(fetch_fn, sym: str, start: int, end: int, chunk_ms: int) -> list[dict]:
    """Page a myTrades-style call across venue-imposed start/end span caps.

    A silent-truncation trap: querying past the cap does not error, it returns an empty (or
    partial) list -- the exact failure class documented in institutional_knowledge.md (paginate
    every venue history endpoint). De-dupes on (id) since chunk boundaries can double-fetch."""
    out: dict[str, dict] = {}
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + chunk_ms, end)
        for t in fetch_fn(sym, cursor, chunk_end):
            out[str(t.get("id"))] = t
        cursor = chunk_end
    return list(out.values())


def _reconcile_symbol(sym: str, opened: datetime | None, closed: datetime | None) -> dict:
    start = _ms(opened or closed) - _BUFFER_MS
    end_anchor = closed or opened or _INCIDENT_END
    end = _ms(end_anchor) + _BUFFER_MS

    spot_fills = _chunked_trades(lambda s, a, b: spot.my_trades(_spot_symbol(s), a, b), sym,
                                  start, end, _SPOT_CHUNK_MS)
    fut_fills = _chunked_trades(fut.my_trades, sym, start, end, _FUT_CHUNK_MS)
    fut_income = fut._income_rows(start, fetch=None, symbol=sym)
    fut_income = [r for r in fut_income if start <= int(r.get("time", 0)) <= end]

    spot_buy_quote = sum(float(t["quoteQty"]) for t in spot_fills if t.get("isBuyer"))
    spot_sell_quote = sum(float(t["quoteQty"]) for t in spot_fills if not t.get("isBuyer"))
    spot_commission = sum(float(t.get("commission", 0.0)) for t in spot_fills
                           if t.get("commissionAsset") in ("USDT", "BUSD"))
    spot_net_usdt = spot_sell_quote - spot_buy_quote - spot_commission

    fut_realized = sum(float(t.get("realizedPnl", 0.0)) for t in fut_fills)
    fut_commission = sum(float(t.get("commission", 0.0)) for t in fut_fills)
    funding = sum(float(r["income"]) for r in fut_income if r.get("incomeType") == "FUNDING_FEE")
    income_realized = sum(float(r["income"]) for r in fut_income if r.get("incomeType") == "REALIZED_PNL")
    income_commission = sum(float(r["income"]) for r in fut_income if r.get("incomeType") == "COMMISSION")

    return {
        "symbol": sym,
        "opened": opened.isoformat() if opened else None,
        "closed": closed.isoformat() if closed else None,
        "spot_fills_n": len(spot_fills),
        "spot_buy_quote_usdt": round(spot_buy_quote, 4),
        "spot_sell_quote_usdt": round(spot_sell_quote, 4),
        "spot_commission_usdt": round(spot_commission, 4),
        "spot_net_usdt": round(spot_net_usdt, 4),
        "fut_fills_n": len(fut_fills),
        "fut_realized_pnl_from_fills": round(fut_realized, 4),
        "fut_commission_from_fills": round(fut_commission, 4),
        "fut_income_realized_pnl": round(income_realized, 4),
        "fut_income_commission": round(income_commission, 4),
        "fut_income_funding": round(funding, 4),
        "combined_net_usdt": round(spot_net_usdt + income_realized - income_commission + funding, 4),
    }


def main() -> None:
    if not (spot.has_keys() and fut.has_keys()):
        print("ABORT: testnet keys not available -- cannot read venue records")
        sys.exit(1)

    trades = _relevant_trades()
    by_symbol: dict[str, list[dict]] = {}
    for t in trades:
        by_symbol.setdefault(t["symbol"], []).append(t)

    rows = []
    for sym, evs in sorted(by_symbol.items()):
        opened = min((_parse(e["opened"]) for e in evs if e.get("opened")), default=None)
        closed = max((_parse(e["closed"]) for e in evs if e.get("closed")), default=None)
        try:
            rows.append(_reconcile_symbol(sym, opened, closed))
        except Exception as e:  # a single symbol's venue read failing must not kill the report
            rows.append({"symbol": sym, "error": repr(e)[:200]})

    total_combined = sum(r.get("combined_net_usdt", 0.0) for r in rows if "error" not in r)
    total_spot_net = sum(r.get("spot_net_usdt", 0.0) for r in rows if "error" not in r)
    total_funding = sum(r.get("fut_income_funding", 0.0) for r in rows if "error" not in r)
    total_fut_realized = sum(r.get("fut_income_realized_pnl", 0.0) for r in rows if "error" not in r)
    total_fut_commission = sum(r.get("fut_income_commission", 0.0) for r in rows if "error" not in r)

    observed_usdt_delta = -1837.68  # data/INCIDENT_20260719_DEADMAN.md fact #5, SPOT-only USDT baseline delta
    observed_equity_gap = 2409.0 - 785.35  # fact #6 vs deadman_state.json last_eq at latch

    # deadman_state.json's usdt_baseline is a SPOT-wallet-only figure (see run_deadman_switch.py) --
    # the correct like-for-like comparison is spot_net_usdt alone. Futures funding/realized/commission
    # live on a DIFFERENT account and never move the spot USDT balance; they explain the separate
    # combined-book equity picture, not this specific baseline delta. Comparing "combined" against a
    # spot-only observed figure was the first-draft bug in this script -- keep both, label correctly.
    spot_residual = round(observed_usdt_delta - total_spot_net, 4)

    report = {
        "generated": datetime.now(UTC).isoformat(),
        "incident_window": [_INCIDENT_START.isoformat(), _INCIDENT_END.isoformat()],
        "scan_window": [_SCAN_START.isoformat(), _SCAN_END.isoformat()],
        "symbols_reconciled": len(rows),
        "per_symbol": rows,
        "totals": {
            "spot_net_usdt": round(total_spot_net, 4),
            "futures_funding_usdt": round(total_funding, 4),
            "futures_realized_pnl_usdt": round(total_fut_realized, 4),
            "futures_commission_usdt": round(total_fut_commission, 4),
            "combined_net_usdt": round(total_combined, 4),
        },
        "observed": {
            "spot_usdt_baseline_delta": observed_usdt_delta,
            "equity_gap_latch_vs_reconstructed": round(observed_equity_gap, 4),
        },
        "spot_only_residual_usdt": spot_residual,
        "unexplained_residual_usdt_full_book_vs_spot_baseline_INVALID_COMPARISON": round(observed_usdt_delta - total_combined, 4),
    }
    _OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Dead-man fire 2026-07-19 -- venue-record reconciliation (read-only, auto-generated)",
        f"_Generated {report['generated']}_",
        "",
        "Maps every carry round-trip active around the incident window to raw Binance testnet",
        "myTrades/income records. Diagnostic only -- issues zero orders, touches no risk-path or",
        "Tier-3 state. See data/PRINCIPAL_ACTION.md for the reset decision this unblocks.",
        "",
        f"**Observed spot USDT baseline delta:** {observed_usdt_delta}",
        f"**Observed equity gap (latch read 785.35 vs reconstructed ~2409):** {observed_equity_gap:.2f}",
        "",
        "## Totals across all reconciled symbols",
        f"- Spot net USDT (sells - buys - commission): **{total_spot_net:.4f}**",
        f"- Futures funding income: **{total_funding:.4f}**",
        f"- Futures realized PnL (income ledger): **{total_fut_realized:.4f}**",
        f"- Futures commission (income ledger): **{total_fut_commission:.4f}**",
        f"- **Combined net USDT explained by venue records: {total_combined:.4f}**",
        f"- **Unexplained residual vs the observed -1,837.68 delta: {report['unexplained_residual_usdt']:.4f}**",
        "",
        "## Per-symbol detail",
        "| symbol | opened | closed | spot fills | spot net USDT | fut funding | fut realized | fut commission | combined |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['symbol']} | ERROR: {r['error']} | | | | | | | |")
            continue
        lines.append(
            f"| {r['symbol']} | {r['opened']} | {r['closed']} | {r['spot_fills_n']} | "
            f"{r['spot_net_usdt']} | {r['fut_income_funding']} | {r['fut_income_realized_pnl']} | "
            f"{r['fut_income_commission']} | {r['combined_net_usdt']} |"
        )
    lines.append("")
    lines.append(
        "**Interpretation guardrail:** a small residual (roughly in line with observed per-trade "
        "price_pnl noise already recorded in data/cashcarry_trades.json) supports the 'measurement "
        "hole, not real loss' reading. A residual comparable in size to the full $1,838 gap means "
        "venue records do NOT explain it and the accounting break is real and still open -- do not "
        "round either way; report the number."
    )
    _OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Reconciled {len(rows)} symbols.")
    print(f"Combined net USDT explained by venue records: {total_combined:.4f}")
    print(f"Unexplained residual vs observed -1,837.68 delta: {report['unexplained_residual_usdt']:.4f}")
    print(f"Wrote {_OUT_MD} and {_OUT_JSON}")


if __name__ == "__main__":
    main()
