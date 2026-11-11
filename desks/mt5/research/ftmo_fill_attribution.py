#!/usr/bin/env python3
"""FTMO FILL ATTRIBUTION -- every FTMO fill named to its sleeve, its signal and its size rule, then
scored with markouts against what that sleeve's certificate expected.

WHY (idea 621, 2026-11-11). FTMO opened its first live position at about 09:45Z (equity
99,627.86, floating -38.52). The Fusion book has `attribution_reconcile` and `markout`; the FTMO
lanes wrote intents (data/ftmo_exec_intents.jsonl, data/ftmo_follower_intents.jsonl) and closed
fills (data/live_ledger_prop.jsonl, book "ftmo") and nothing joined the two or asked whether a fill
behaved like the certificate that licensed it. This report is that join.

READ FROM WHAT THE FTMO LANES ALREADY WRITE, never a new store:

    data/live_ledger_prop.jsonl          closed FTMO positions (prop-fills-v1, ftmo_follower)
    data/ftmo_exec_intents.jsonl         the sleeve executor's rows: SENT carries order_id, sleeve,
                                         certificate, risk_frac, lot, risk_usd, side, entry, stop
    data/ftmo_follower_intents.jsonl     the gold copy's rows, same reading
    reports/FTMO_ACCOUNT_STATE.json      open positions (symbol, side, volume, profit), equity
    reports/FTMO_ALLOCATOR.json          `costs[sleeve].bias_r_per_trade`: FTMO's cost per trade
    reports/UNIVERSAL_SURVIVORS.json     the certificate's gates: expected_value.ev (R per trade),
      (or data/UNIVERSAL_SURVIVORS.canon.json)  stress_costs.exp_x3, any hit/win rate it carries
    data/universe_ftmo/<SYM>_M1.parquet  the price path for markouts (then data/universe/)

THE JOIN, strongest first: a fill's entry order == a SENT intent's order_id (ORDER_ID); a closed
fill's own `sleeve` field naming a certificate or sleeve the intents know (LEDGER_SLEEVE); an open
position whose symbol, side and volume match exactly ONE SENT intent (SYMBOL_SIDE_VOLUME). Anything
else is UNATTRIBUTED and LISTED -- never dropped, never guessed.

MARKOUTS. side x (price at entry + h - entry) / |entry - stop| in R, for h in +1m, +5m, +15m,
+60m, and to the close (the realised R for a closed fill). A horizon the price path does not reach,
or a fill with no stop, is UNMEASURED with its reason -- never 0.

REPORT ONLY. It sends, sizes and vetoes nothing: report_only true, consumer null.

    python desks/mt5/research/ftmo_fill_attribution.py --once
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
REPORTS = DESK / "reports"
PROP_LEDGER = DATA / "live_ledger_prop.jsonl"
INTENT_FILES = {"ftmo_executor": DATA / "ftmo_exec_intents.jsonl",
                "ftmo_follower": DATA / "ftmo_follower_intents.jsonl"}
ACCOUNT_STATE = REPORTS / "FTMO_ACCOUNT_STATE.json"
ALLOCATOR = REPORTS / "FTMO_ALLOCATOR.json"
SURVIVORS = (REPORTS / "UNIVERSAL_SURVIVORS.json", DATA / "UNIVERSAL_SURVIVORS.canon.json")
BAR_DIRS = (DATA / "universe_ftmo", DATA / "universe")
OUT = REPORTS / "FTMO_FILL_ATTRIBUTION.json"

SCHEMA = "ftmo-fill-attribution/1"
UNMEASURED = "UNMEASURED"
UNATTRIBUTED = "UNATTRIBUTED"
HORIZONS_MIN = (1, 5, 15, 60)
#: How each lane sizes, in its own words (prop/ftmo_executor.py step 5; prop/ftmo_follower.py).
SIZE_RULES = {
    "ftmo_executor": "allocator fraction x equity / loss per lot at the signal's stop "
                     "(ftmo_executor.lot_for_loss), capped by the follower's notional lot cap",
    "ftmo_follower": "the gold copy's own sizing (prop/ftmo_follower.py)",
}
SENT = "SENT"


# ------------------------------------------------------------------ readers

def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_jsonl(p: Path) -> list[dict[str, Any]] | None:
    """Rows, or None when the file is absent/unreadable (UNMEASURED, never an empty book)."""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    out = []
    for ln in text.splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _f(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return None
    try:
        v = float(x)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _t(x: Any) -> datetime | None:
    if not x:
        return None
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _dir(side: Any) -> int:
    s = str(side).lower()
    if s in ("buy", "long", "0"):
        return 1
    if s in ("sell", "short", "1"):
        return -1
    return 0


# ------------------------------------------------------------------ certificate expectations

def _find_rate(gates: dict[str, Any]) -> float | None:
    for g in gates.values():
        if isinstance(g, dict):
            for k in ("hit_rate", "win_rate", "hit"):
                v = _f(g.get(k))
                if v is not None:
                    return v
    return None


def expectations(cert_key: str | None, sleeve: str | None, store: dict[str, Any] | None,
                 alloc: dict[str, Any] | None) -> dict[str, Any]:
    """What the certificate said a trade is worth. Every absent field is UNMEASURED, never 0."""
    out: dict[str, Any] = {"certificate": cert_key}
    surv = (store or {}).get("survivors") if isinstance(store, dict) else None
    cert = surv.get(cert_key) if isinstance(surv, dict) and cert_key else None
    if not isinstance(cert, dict):
        out.update(status=UNMEASURED, why=(f"certificate {cert_key} is not in the store"
                                           if cert_key else "no certificate named for the fill"))
        gates: dict[str, Any] = {}
    else:
        g = cert.get("gates")
        gates = g if isinstance(g, dict) else {}
        out["status"] = "OK"
    ev = _f((gates.get("expected_value") or {}).get("ev"))
    out["expected_edge_r_per_trade"] = ev if ev is not None else UNMEASURED
    x3 = _f((gates.get("stress_costs") or {}).get("exp_x3"))
    out["edge_at_3x_cost_r"] = x3 if x3 is not None else UNMEASURED
    hr = _find_rate(gates)
    out["hit_rate"] = hr if hr is not None else UNMEASURED
    costs = (alloc or {}).get("costs") if isinstance(alloc, dict) else None
    c = costs.get(sleeve) if isinstance(costs, dict) and sleeve else None
    bias = _f(c.get("bias_r_per_trade")) if isinstance(c, dict) else None
    out["ftmo_cost_r_per_trade"] = bias if bias is not None else UNMEASURED
    out["expected_net_r_per_trade"] = (round(ev - bias, 6) if ev is not None and bias is not None
                                       else UNMEASURED)
    return out


# ------------------------------------------------------------------ price path

def load_path(symbol: str) -> Any:
    """A pandas Series of M1 closes indexed by UTC time, or None (markouts UNMEASURED)."""
    try:
        import pandas as pd
    except ImportError:
        return None
    for d in BAR_DIRS:
        p = d / f"{symbol}_M1.parquet"
        if p.exists():
            try:
                df = pd.read_parquet(p)
            except Exception:
                continue
            if "time" in df.columns:
                df = df.set_index("time")
            idx = pd.to_datetime(df.index, utc=True)
            if "close" in df.columns:
                return pd.Series(df["close"].to_numpy(dtype=float), index=idx).sort_index()
    return None


def price_at(path: Any, when: datetime) -> float | None:
    if path is None or len(path) == 0:
        return None
    import pandas as pd
    ts = pd.Timestamp(when)
    if ts > path.index[-1]:
        return None                                   # the path does not reach this horizon
    sub = path.loc[:ts]
    return _f(sub.iloc[-1]) if len(sub) else None


def markouts(fill: dict[str, Any], path: Any) -> dict[str, Any]:
    entry, stop = _f(fill.get("entry_price")), _f(fill.get("stop"))
    d = _dir(fill.get("side"))
    t0 = _t(fill.get("entry_time"))
    dist = abs(entry - stop) if entry is not None and stop is not None else None
    out: dict[str, Any] = {}
    for h in HORIZONS_MIN:
        key = f"+{h}m"
        if entry is None or t0 is None or not d:
            out[key] = {"status": UNMEASURED, "why": "no entry price, time or side on the fill"}
            continue
        px = price_at(path, t0 + timedelta(minutes=h))
        if px is None:
            out[key] = {"status": UNMEASURED,
                        "why": "no M1 price path reaches this horizon" if path is not None
                        else f"no M1 bars for {fill.get('symbol')}"}
            continue
        mo = {"status": "OK", "price": px, "move": round(d * (px - entry), 8)}
        mo["r"] = round(d * (px - entry) / dist, 4) if dist else UNMEASURED
        out[key] = mo
    rr = _f(fill.get("r_multiple"))
    if fill.get("open"):
        out["to_close"] = {"status": UNMEASURED, "why": "the position is still open"}
    elif rr is not None:
        out["to_close"] = {"status": "OK", "r": rr, "basis": "prop ledger r_multiple"}
    else:
        out["to_close"] = {"status": UNMEASURED, "why": "the ledger row carries no r_multiple"}
    return out


# ------------------------------------------------------------------ fills and the join

def collect_fills(ledger: list[dict[str, Any]] | None, state: Any) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    for r in ledger or []:
        if str(r.get("book")) != "ftmo":
            continue
        fills.append({"source": "live_ledger_prop", "open": False, "lane": r.get("lane"),
                      "symbol": str(r.get("symbol") or "").upper(),
                      "side": "buy" if r.get("entry_side") == 0 else "sell"
                      if r.get("entry_side") == 1 else None,
                      "entry_time": r.get("entry_time"), "exit_time": r.get("exit_time"),
                      "entry_price": r.get("entry_price"), "stop": r.get("sl"),
                      "volume": r.get("volume"), "entry_order": r.get("entry_order"),
                      "position_id": r.get("position_id"), "ledger_sleeve": r.get("sleeve"),
                      "r_multiple": r.get("r_multiple"), "pl_quote": r.get("pl_quote")})
    if isinstance(state, dict):
        for p in state.get("open_positions") or []:
            if isinstance(p, dict):
                fills.append({"source": "FTMO_ACCOUNT_STATE", "open": True,
                              "symbol": str(p.get("symbol") or "").upper(),
                              "side": "buy" if p.get("side") == "long" else "sell"
                              if p.get("side") == "short" else None,
                              "volume": p.get("volume"), "floating": p.get("profit"),
                              "observed_at": state.get("generated_at")})
    return fills


def attribute(fill: dict[str, Any], sent: list[dict[str, Any]]) -> tuple[dict[str, Any] | None,
                                                                          str]:
    eo = fill.get("entry_order")
    if eo is not None:
        hit = [s for s in sent if s.get("order_id") is not None and str(s["order_id"]) == str(eo)]
        if len(hit) == 1:
            return hit[0], "ORDER_ID"
    ls = fill.get("ledger_sleeve")
    if ls:
        hit = [s for s in sent if ls in (s.get("certificate"), s.get("sleeve"))
               and str(s.get("symbol") or "").upper() == fill["symbol"]]
        if len(hit) >= 1:
            return hit[-1], "LEDGER_SLEEVE"
        return {"sleeve": ls, "certificate": ls, "lane": fill.get("lane")}, "LEDGER_SLEEVE"
    vol = _f(fill.get("volume"))
    hit = [s for s in sent if str(s.get("symbol") or "").upper() == fill["symbol"]
           and _dir(s.get("side")) == _dir(fill.get("side")) and vol is not None
           and _f(s.get("lot")) is not None and abs(_f(s.get("lot")) - vol) < 1e-9]  # type: ignore[operator]
    if len(hit) == 1:
        return hit[0], "SYMBOL_SIDE_VOLUME"
    if len(hit) > 1:
        return None, f"{len(hit)} SENT intents match symbol/side/volume: ambiguous"
    return None, "no SENT intent matches by order id, ledger sleeve or symbol/side/volume"


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    ledger = _read_jsonl(PROP_LEDGER)
    state = _read_json(ACCOUNT_STATE)
    alloc = _read_json(ALLOCATOR)
    store = next((s for s in (_read_json(p) for p in SURVIVORS)
                  if isinstance(s, dict) and s.get("survivors")), None)
    inputs = {"live_ledger_prop": "OK" if ledger is not None else UNMEASURED,
              "account_state": "OK" if isinstance(state, dict) else UNMEASURED,
              "allocator": "OK" if isinstance(alloc, dict) else UNMEASURED,
              "certificates": "OK" if store else UNMEASURED}
    sent: list[dict[str, Any]] = []
    for lane, p in INTENT_FILES.items():
        rows = _read_jsonl(p)
        inputs[p.name] = "OK" if rows is not None else UNMEASURED
        for r in rows or []:
            if r.get("status") == SENT:
                sent.append({**r, "lane": r.get("lane_name") or lane, "_writer": lane})
    if ledger is None and not isinstance(state, dict):
        doc: dict[str, Any] = {"status": UNMEASURED,
                               "why": "no FTMO fill source is readable on this host "
                                      "(live_ledger_prop.jsonl and FTMO_ACCOUNT_STATE.json absent)",
                               "fills": [], "unattributed": [], "n_fills": UNMEASURED}
    else:
        rows_out, unatt = [], []
        paths: dict[str, Any] = {}
        for f in collect_fills(ledger, state):
            intent, how = attribute(f, sent)
            sym = f["symbol"]
            if sym not in paths:
                paths[sym] = load_path(sym)
            if intent is not None:
                if f.get("stop") is None:
                    f["stop"] = intent.get("stop")
                if f.get("entry_price") is None:
                    f["entry_price"] = intent.get("entry_ref")
                if f.get("entry_time") is None and intent.get("at"):
                    f["entry_time"] = intent.get("at")
                writer = intent.get("_writer") or f.get("lane") or "ftmo_follower"
                f.update(attribution=how, sleeve=intent.get("sleeve"),
                         signal={"certificate": intent.get("certificate"),
                                 "family": intent.get("family"),
                                 "timeframe": intent.get("timeframe"),
                                 "intent_at": intent.get("at")},
                         size_rule={"rule": SIZE_RULES.get(str(writer), UNMEASURED),
                                    "risk_frac": intent.get("risk_frac", UNMEASURED),
                                    "lot": intent.get("lot", UNMEASURED),
                                    "risk_usd": intent.get("risk_usd", UNMEASURED)},
                         expected=expectations(intent.get("certificate"), intent.get("sleeve"),
                                               store, alloc))
            else:
                f.update(attribution=UNATTRIBUTED, attribution_why=how, sleeve=None,
                         expected={"status": UNMEASURED, "why": "no sleeve, so no certificate"})
            f["markouts"] = markouts(f, paths[sym])
            exp = f["expected"].get("expected_net_r_per_trade", UNMEASURED)
            close = f["markouts"]["to_close"]
            f["vs_certificate"] = (
                {"realised_minus_expected_net_r": round(close["r"] - exp, 4)}
                if close.get("status") == "OK" and isinstance(exp, float)
                else {"status": UNMEASURED,
                      "why": "needs a closed fill's R and the certificate's net edge"})
            rows_out.append(f)
            if f["attribution"] == UNATTRIBUTED:
                unatt.append({k: f.get(k) for k in ("source", "symbol", "side", "volume",
                                                     "entry_order", "position_id",
                                                     "attribution_why")})
        n = len(rows_out)
        doc = {"status": "OK", "fills": rows_out, "unattributed": unatt, "n_fills": n,
               "n_attributed": n - len(unatt),
               "attributed_share": round((n - len(unatt)) / n, 4) if n else UNMEASURED}
    return {"schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
            "report_only": True, "consumer": None,
            "intended_consumer": "prop_challenge_allocator (FTMO sleeve edge vs certificate) "
                                 "and the CRO cycle's execution review",
            "horizons_min": list(HORIZONS_MIN), "inputs": inputs, **doc}


def write(doc: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = build()
    write(doc)
    print(f"ftmo_fill_attribution: {doc['status']} fills={doc.get('n_fills')} "
          f"unattributed={len(doc.get('unattributed') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
