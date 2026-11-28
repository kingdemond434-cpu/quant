"""DAILY P&L EXPLAIN PER ACCOUNT, AND THE PER-FILL COST TAPE UNDER IT (tier-1 K4 + P1).

THE GAP (2026-11-18). The desk measured slippage per fill (`research/fill_recorder.py` ->
`data/fill_corpus.jsonl`) and the gateway stamps commission and swap on every closing deal,
but no organ ever added them up
by ACCOUNT and DAY. So "what did E8 / FTMO / Fusion make yesterday, and how much of it was the
signal versus the round trip?" had no artifact. A tier-1 desk answers that every morning.

WHAT IT PUBLISHES, per account per UTC day (exit date), in account currency:

    net         what the account booked: gross + commission + swap + fees
    gross       the price move at the fills, before any fee
    signal      gross with slippage added back: what the trade made at the DECISION price
    slippage    -(fill - decision) x direction x contract x lots x conversion, joined per deal
                from the fill corpus. Negative is adverse. Unjoined deals carry 0 and are COUNTED
                (n_slip_joined / n_trades), never assumed clean
    commission, swap, fees   as the broker stamped them
    fx          UNMEASURED by design: MT5 books profit in account currency already, so the FX
                leg is inside gross. Each trade's measured conversion rate (account currency per
                quote unit, from its own profit) is published instead, and it is what converts
                slippage

Identity checked on every row: signal + slippage + commission + swap + fees == net.

Per account it also publishes the per-fill tape summary: slippage in points against the decision
quote and against the decision MID, spread paid at decision, commission and swap per trade.

Sources: `data/live_ledger.jsonl` (gateway: Fusion and whatever account the gateway holds),
`data/live_ledger_prop.jsonl` (FTMO/E8 prop fills), `data/fill_corpus.jsonl` (per-fill slippage).
Accounts are told apart by the keyed `account_key` + server, never a login. Absent sources read
UNMEASURED. Report only: consumer None; intended consumers are the judge's cost-aware scoring and
the allocator's E[log W] cost term. No LLM anywhere in this path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
LEDGER = BASE / "data" / "live_ledger.jsonl"
PROP_LEDGER = BASE / "data" / "live_ledger_prop.jsonl"
CORPUS = BASE / "data" / "fill_corpus.jsonl"
OUT = BASE / "reports" / "PNL_EXPLAIN.json"
INTENDED_CONSUMER = ("judge cost-aware scoring; pf_allocator / prop_challenge_allocator "
                     "E[log W] cost term")
COMPONENTS = ("signal", "slippage", "commission", "swap", "fees")
MAX_DAYS = 60


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _rows(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    out = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict):
                out.append(d)
    return out


def account_label(row: dict[str, Any]) -> str:
    """Firm | kind | short key. The firm is read off the server name."""
    server = str(row.get("server") or "")
    s = server.upper()
    firm = ("FTMO" if "FTMO" in s else "E8" if "E8" in s else
            "Fusion" if "FUSION" in s else (server or "unknown"))
    kind = str(row.get("account_kind") or "unknown")
    key = str(row.get("account_key") or "")
    return f"{firm}|{kind}|{key[:8] or 'nokey'}"


def _day(row: dict[str, Any]) -> str | None:
    t = str(row.get("exit_time") or row.get("time") or "")
    return t[:10] if len(t) >= 10 else None


def _side(row: dict[str, Any]) -> int:
    es = row.get("entry_side")
    if es in (0, "0", "buy", "BUY", "long"):
        return 1
    if es in (1, "1", "sell", "SELL", "short"):
        return -1
    return 0


def decompose(row: dict[str, Any], slip: dict[str, Any] | None) -> dict[str, Any] | None:
    """One closed trade -> its components in account currency. None when unpriced."""
    pl = _f(row.get("pl_quote"))
    if pl is None:
        return None
    comm = _f(row.get("commission")) or 0.0
    swap = _f(row.get("swap")) or 0.0
    fees = (_f(row.get("exit_fee")) or 0.0) + (_f(row.get("fee")) or 0.0)
    # prop ledger: pl_quote is gross of fees; gateway: pl_quote = profit + commission + swap
    gross = pl if "gross" in str(row.get("pl_basis") or "") else pl - comm - swap
    net = gross + comm + swap + fees
    entry, exit_, vol = _f(row.get("entry_price")), _f(row.get("fill_price")), _f(row.get("volume"))
    contract, d = _f(row.get("contract_size")), _side(row)
    conv, conv_basis = 1.0, "assumed_1"
    if entry and exit_ and vol and contract and d and abs(exit_ - entry) > 0:
        move = d * (exit_ - entry) * contract * vol
        if move and gross and (move > 0) == (gross > 0):
            conv, conv_basis = abs(gross / move), "measured_from_trade"
    slippage, joined = 0.0, False
    if slip is not None:
        pts, point, lots = _f(slip.get("slip_points")), _f(slip.get("point")), _f(slip.get("lots"))
        if pts is not None and point and (lots or vol) and contract:
            slippage = -pts * point * contract * (lots or vol or 0.0) * conv
            joined = True
    return {"gross": gross, "net": net, "signal": gross - slippage, "slippage": slippage,
            "commission": comm, "swap": swap, "fees": fees, "fx_rate": conv,
            "fx_basis": conv_basis, "slip_joined": joined}


def _slip_index(corpus: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for r in corpus or []:
        if r.get("status") == "FILLED" and r.get("deal") is not None:
            idx[str(r["deal"])] = r
    return idx


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 6) if xs else None


def explain(trades: list[dict[str, Any]], corpus: list[dict[str, Any]] | None) -> dict[str, Any]:
    idx = _slip_index(corpus)
    days: dict[tuple[str, str], dict[str, Any]] = {}
    tape: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    unpriced = 0
    for r in trades:
        day = _day(r)
        s = idx.get(str(r.get("deal"))) if r.get("deal") is not None else None
        c = decompose(r, s)
        if c is None or day is None:
            unpriced += 1
            continue
        acct = account_label(r)
        k = (acct, day)
        d = days.setdefault(k, {"account": acct, "day": day, "n_trades": 0, "n_slip_joined": 0,
                                "gross": 0.0, "net": 0.0, **dict.fromkeys(COMPONENTS, 0.0)})
        d["n_trades"] += 1
        d["n_slip_joined"] += int(c["slip_joined"])
        for x in ("gross", "net", *COMPONENTS):
            d[x] += c[x]
        t = tape[acct]
        t["commission"].append(c["commission"])
        t["swap"].append(c["swap"])
        if s is not None:
            for key in ("slip_points", "spread_points_at_decision"):
                v = _f(s.get(key))
                if v is not None:
                    t[key].append(v)
            mid, fill, point = (_f(s.get("quote_mid_at_decision")), _f(s.get("fill_price")),
                                _f(s.get("point")))
            dr = _f(s.get("direction")) or 0.0
            if mid and fill and point and dr:
                t["slip_vs_mid_points"].append((fill - mid) * dr / point)
    rows = sorted(days.values(), key=lambda d: (d["day"], d["account"]), reverse=True)
    for d in rows:
        resid = d["net"] - sum(d[x] for x in COMPONENTS)
        for x in ("gross", "net", *COMPONENTS):
            d[x] = round(d[x], 2)
        d["identity_residual"] = round(resid, 6)
    accounts: dict[str, Any] = {}
    for acct in sorted({d["account"] for d in rows}):
        mine = [d for d in rows if d["account"] == acct]
        tot = {x: round(sum(d[x] for d in mine), 2) for x in ("gross", "net", *COMPONENTS)}
        n = sum(d["n_trades"] for d in mine)
        t = tape.get(acct, {})
        accounts[acct] = {
            "n_trades": n, "n_days": len(mine), "totals": tot,
            "cost_share_of_signal": (round((tot["signal"] - tot["net"]) / abs(tot["signal"]), 4)
                                     if tot["signal"] else None),
            "per_fill": {"mean_slip_points_vs_decision": _mean(t.get("slip_points", [])),
                         "mean_slip_points_vs_mid": _mean(t.get("slip_vs_mid_points", [])),
                         "mean_spread_points_at_decision": _mean(
                             t.get("spread_points_at_decision", [])),
                         "mean_commission_per_trade": _mean(t.get("commission", [])),
                         "mean_swap_per_trade": _mean(t.get("swap", [])),
                         "n_fills_with_slippage": len(t.get("slip_points", []))}}
    return {"accounts": accounts, "daily": rows[: MAX_DAYS * max(1, len(accounts))],
            "n_unpriced": unpriced,
            "identity_ok": all(abs(d["identity_residual"]) < 1e-6 for d in rows)}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "report_only": True, "consumer": None,
                           "intended_consumer": INTENDED_CONSUMER,
                           "currency": "account currency per account",
                           "fx": ("UNMEASURED as a separate leg: MT5 books profit in account "
                                  "currency, so FX conversion is inside gross; each trade's "
                                  "measured conversion rate is used to convert slippage")}
    gw, prop, corpus = _rows(LEDGER), _rows(PROP_LEDGER), _rows(CORPUS)
    doc["sources"] = {"live_ledger": gw is not None, "live_ledger_prop": prop is not None,
                      "fill_corpus": corpus is not None}
    trades = (gw or []) + (prop or [])
    if not trades:
        doc.update(status="UNMEASURED", why="no closed-trade ledger on this host", n_accounts=0)
        return doc
    doc.update(explain(trades, corpus))
    doc["n_accounts"] = len(doc["accounts"])
    doc["status"] = "OK" if doc["identity_ok"] else "IDENTITY_BROKEN"
    return doc


def write(doc: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="daily per-account P&L explain").parse_args(argv)
    doc = build()
    write(doc)
    print(f"pnl_explain: {doc['status']} accounts={doc.get('n_accounts')} "
          f"days={len(doc.get('daily') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
