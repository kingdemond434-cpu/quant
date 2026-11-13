"""Daily P&L EXPLAIN per account: every realised dollar split into signal, entry slippage,
commission, swap, fees and FX conversion -- with the unexplained remainder shown, not hidden.

Finding K4 (CRO noon pass 2026-11-13, GAP_MAP rank 112): the desk had no daily decomposition of
each account's realised P&L. `markout` measured book-level slippage, `allocator_attribution` and
`counterfactual_attribution` split by sleeve, and the live ledger carried the raw fields
(pl_quote, commission, swap) -- but nobody could answer "of yesterday's -$41 on FTMO, how much
was the signal being wrong, how much was the fill, how much the broker, how much the dollar".
A tier-1 desk reads that every morning, because each line has a different owner and a different
fix: a bad signal goes to research, slippage to execution, commission to venue choice, swap to
hold-period design, FX conversion to the hedge policy.

THE IDENTITY, per closed trade, in ACCOUNT currency (the ledger's `pl_quote` is the NET realised
P&L the gateway booked: deal profit + commission + swap + fee + allocated entry cost):

    net  =  signal  +  entry_slippage  +  commission  +  swap  +  fees  +  fx_conversion  + residual

  quote_gross     = (exit fill - entry fill) x direction x volume x contract   (profit currency)
  rate_entry      = profit-currency -> account-currency rate at ENTRY (1 when they match; the
                    traded pair's own entry price when it IS the conversion pair; otherwise the
                    H1 close of the conversion pair's bar containing the entry)
  rate_exit       = the rate MT5 actually used = deal profit / quote_gross (when |quote_gross|
                    is not ~0); the broker's own conversion, not a model
  signal          = (exit fill - INTENDED entry) x direction x volume x contract x rate_entry
                    -- what the trade earned had it filled exactly where the desk asked
  entry_slippage  = -(entry fill - intended) x direction x volume x contract x rate_entry
                    (negative = paid; positive = price improvement)
  commission      = the deal's commission;  swap = the deal's swap
  fees            = exit fee + the entry cost the gateway allocated to this close
  fx_conversion   = quote_gross x (rate_exit - rate_entry): the account-currency P&L that came
                    from the profit currency moving while the trade was open, not from the trade
  residual        = net - (all of the above). Reported per trade, per day and per account; a
                    trade with |residual| above RESIDUAL_TOL_ACCT is listed by deal, because an
                    unexplained dollar is a bookkeeping defect somewhere upstream.

UNMEASURED IS A REAL ANSWER (L1.28a). No matching intent -> slippage is UNMEASURED and the
split is reported as `signal_plus_slippage` (never a zero slip); no conversion rate -> FX is
UNMEASURED and stays inside `signal`; an unknowable direction or entry -> the trade is listed as
UNEXPLAINABLE with its reason. Every aggregate carries coverage: the share of |net| whose
slippage and FX components were MEASURED.

ACCOUNTS are separated by the ledger's provenance key (`mt5desk.provenance.row_account`: keyed
account, server, kind) -- Fusion live, Fusion demo, FTMO and E8 are never pooled. No login is
read or written; only the keyed `account_key` the ledgers already carry.

INPUTS (read-only): data/live_ledger.jsonl (audited view), data/live_ledger_prop.jsonl (prop
fills, FTMO/E8 lanes), data/order_intents.jsonl and the prop intents files (intended prices),
data/universe/universe.json (profit currency, contract size), data/universe/*_H1.parquet (entry
conversion rate), data/account_state.json (account currency of the account it describes).

OUTPUTS: reports/PNL_EXPLAIN.json (per account: daily table, sleeve table, cost-drag ratios,
coverage, the trades that do not reconcile) and data/pnl_explain_daily.jsonl (one row per
account x CLOSED UTC day, appended once and never rewritten). Hourly leg `pnl_explain`.

    python desks/mt5/research/pnl_explain.py [--days 90] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
LEDGER = DATA / "live_ledger.jsonl"
PROP_LEDGER = DATA / "live_ledger_prop.jsonl"
INTENT_FILES = (DATA / "order_intents.jsonl", DATA / "e8_intents.jsonl",
                DATA / "ftmo_follower_intents.jsonl")
UNIVERSE = DATA / "universe" / "universe.json"
ACCOUNT_STATE = DATA / "account_state.json"
REPORT = DESK / "reports" / "PNL_EXPLAIN.json"
DAILY = DATA / "pnl_explain_daily.jsonl"

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
#: A trade whose components miss its booked net by more than this (account currency) is listed.
RESIDUAL_TOL_ACCT = 0.05
#: |quote_gross| below this (profit currency) cannot yield an implied exit rate.
MIN_QUOTE_GROSS = 1e-6
#: Implied rate within this relative distance of 1.0 on profit-currency == candidate means the
#: account is denominated in that currency (inference used only when no state file names it).
CCY_INFER_TOL = 0.02
COMPONENTS = ("signal", "entry_slippage", "commission", "swap", "fees", "fx_conversion",
              "residual")


# --------------------------------------------------------------------------------- readers
def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        from libs.ops.live_ledger_view import ledger_path
        p = ledger_path(Path(path))
    except Exception:
        p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _f(x: Any) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ts(x: Any) -> datetime | None:
    if not x:
        return None
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


# --------------------------------------------------------------------------------- intents
def intent_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """{order ticket / deal ticket / intent id: intended price}. A rejected or unpriced intent
    contributes nothing (an order that never traded has no slippage)."""
    out: dict[str, float] = {}
    for r in rows:
        px = _f(r.get("intended"))
        if px is None or px <= 0:
            continue
        for k in ("ticket", "deal_ticket", "intent_id", "order"):
            v = r.get(k)
            if v not in (None, "", 0, "0"):
                out[f"{k.split('_')[0] if k != 'intent_id' else 'intent'}:{v}"] = px
                out[str(v)] = px
    return out


def _intended(row: Mapping[str, Any], intents: Mapping[str, float]) -> tuple[float | None, str]:
    px = _f(row.get("intended_entry"))
    if px:
        return px, "row.intended_entry"
    for k in ("entry_order", "position_id", "order", "entry_deal", "intent_id"):
        v = row.get(k)
        if v not in (None, "", 0) and str(v) in intents:
            return intents[str(v)], f"order_intents[{k}={v}]"
    return None, "no matching intent"


# --------------------------------------------------------------------------------- currency
@dataclass
class RateBook:
    """Profit-currency -> account-currency rates at an instant, from the desk's own bars."""

    meta: Mapping[str, Any]
    bars: Callable[[str], Any] | None = None
    _cache: dict[str, Any] = field(default_factory=dict)

    def _closes(self, sym: str) -> Any:
        if sym not in self._cache:
            got = None
            if self.bars is not None:
                try:
                    got = self.bars(sym)
                except Exception:
                    got = None
            self._cache[sym] = got
        return self._cache[sym]

    def _close_at(self, sym: str, when: datetime) -> float | None:
        d = self._closes(sym)
        if d is None or "close" not in getattr(d, "columns", ()):
            return None
        import pandas as pd
        idx = d.index
        # the bar index is broker time (UTC+2/+3); the bar containing `when` in either season
        # opened at or before when+3h, so take the last close at or before when+2h -- within an
        # hour of the entry, never a close from after the entry in either season
        t = pd.Timestamp(when + timedelta(hours=2))
        pos = int(idx.searchsorted(t, side="right")) - 1
        if pos < 0:
            return None
        v = _f(d["close"].iloc[pos])
        return v if v and v > 0 else None

    def rate(self, profit_ccy: str, acct_ccy: str, when: datetime,
             traded: str = "", traded_px: float | None = None) -> tuple[float | None, str]:
        p, a = profit_ccy.upper(), acct_ccy.upper()
        if not p or not a:
            return None, "currency unknown"
        if p == a:
            return 1.0, "same currency"
        direct, inverse = f"{p}{a}", f"{a}{p}"
        if traded_px and traded.upper().startswith(direct):
            return traded_px, f"traded pair {traded} entry price"
        if traded_px and traded.upper().startswith(inverse):
            return 1.0 / traded_px, f"traded pair {traded} entry price (inverted)"
        for sym in (direct, inverse):
            if sym in self.meta:
                c = self._close_at(sym, when)
                if c:
                    return (c, f"{sym} H1 close at entry") if sym == direct else \
                        (1.0 / c, f"{sym} H1 close at entry (inverted)")
        return None, f"no {direct}/{inverse} bars at entry on this host"


def account_currency(acct: tuple, rows: list[Mapping[str, Any]], meta: Mapping[str, Any],
                     state: Mapping[str, Any]) -> tuple[str, str]:
    """The account's deposit currency and how it was known."""
    for r in rows:
        c = r.get("account_currency") or r.get("currency")
        if c:
            return str(c).upper(), "ledger row"
    if state.get("currency") and acct[1] and state.get("server") == acct[1]:
        return str(state["currency"]).upper(), "account_state.json (same server)"
    votes: dict[str, int] = defaultdict(int)
    for r in rows:
        sym = str(r.get("symbol") or "")
        m = meta.get(sym) if isinstance(meta.get(sym), dict) else None
        if not m:
            continue
        g = _trade_geometry(r, m)
        prof = _deal_profit(r)
        if g is None or prof is None or abs(g["quote_gross"]) < MIN_QUOTE_GROSS:
            continue
        implied = prof / g["quote_gross"]
        # Two exact tells, no bars needed: the broker converted at ~1 (the account IS the profit
        # currency), or at ~1/price of the traded pair itself (the account IS its BASE currency,
        # e.g. EURCHF profit in CHF booked in EUR at 1/EURCHF).
        if abs(implied - 1.0) <= CCY_INFER_TOL:
            votes[str(m.get("currency_profit") or "").upper()] += 1
        elif len(sym) >= 6 and abs(implied * g["exit"] - 1.0) <= CCY_INFER_TOL:
            votes[sym[:3].upper()] += 1
    if votes:
        best = max(votes, key=lambda k: votes[k])
        return best, (f"inferred from the broker's own conversion on {votes[best]} trade(s) "
                      f"(implied rate ~1 or ~1/price of a {best}-based pair)")
    return "", "unknown"


# --------------------------------------------------------------------------------- a trade
def _direction(r: Mapping[str, Any]) -> int:
    es = r.get("entry_side")
    if es in (0, 1):
        return 1 if es == 0 else -1
    e, sl, tp = _f(r.get("entry_price")), _f(r.get("sl")), _f(r.get("tp"))
    if e and sl and sl > 0:
        return 1 if sl < e else -1
    if e and tp and tp > 0:
        return 1 if tp > e else -1
    s = r.get("side")       # the CLOSING deal's type: a closing BUY (0) ends a SHORT
    return -1 if s == 0 else (1 if s == 1 else 0)


def _deal_profit(r: Mapping[str, Any]) -> float | None:
    """The deal profit (account currency) the net was built from."""
    net = _f(r.get("pl_quote"))
    if net is None:
        return None
    return net - (_f(r.get("commission")) or 0.0) - (_f(r.get("swap")) or 0.0) - _fees(r)


def _fees(r: Mapping[str, Any]) -> float:
    return (_f(r.get("exit_fee")) or 0.0) + (_f(r.get("entry_cost_allocated")) or 0.0)


def _trade_geometry(r: Mapping[str, Any], m: Mapping[str, Any]) -> dict[str, Any] | None:
    e, x = _f(r.get("entry_price")), _f(r.get("fill_price"))
    vol = _f(r.get("volume"))
    cs = _f(r.get("contract_size")) or _f(m.get("contract_size"))
    d = _direction(r)
    if not (e and x and vol and cs) or d == 0:
        return None
    return {"entry": e, "exit": x, "vol": vol, "cs": cs, "dir": d,
            "quote_gross": (x - e) * d * vol * cs}


@dataclass
class Explained:
    deal: str
    account: str
    day: str
    sleeve: str
    symbol: str
    net: float
    signal: float | None = None
    entry_slippage: float | None = None
    commission: float = 0.0
    swap: float = 0.0
    fees: float = 0.0
    fx_conversion: float | None = None
    residual: float | None = None
    signal_plus_slippage: float | None = None
    slippage_status: str = UNMEASURED
    fx_status: str = UNMEASURED
    why: list[str] = field(default_factory=list)
    explainable: bool = True


def explain_trade(r: Mapping[str, Any], acct_key: str, acct_ccy: str, meta: Mapping[str, Any],
                  intents: Mapping[str, float], rates: RateBook) -> Explained:
    net = _f(r.get("pl_quote")) or 0.0
    when = _ts(r.get("exit_time")) or _ts(r.get("time")) or datetime(1970, 1, 1, tzinfo=UTC)
    ex = Explained(deal=str(r.get("deal") or r.get("position_id") or ""), account=acct_key,
                   day=when.date().isoformat(), sleeve=str(r.get("sleeve") or "?"),
                   symbol=str(r.get("symbol") or "?"), net=round(net, 4),
                   commission=_f(r.get("commission")) or 0.0, swap=_f(r.get("swap")) or 0.0,
                   fees=_fees(r))
    m = meta.get(ex.symbol) if isinstance(meta.get(ex.symbol), dict) else None
    g = _trade_geometry(r, m or {})
    prof = _deal_profit(r)
    if g is None or prof is None:
        ex.explainable = False
        ex.why.append("entry/exit fill, volume, contract or direction unknowable")
        ex.residual = None
        return ex
    pccy = str((m or {}).get("currency_profit") or "").upper()
    entry_at = _ts(r.get("entry_time")) or when
    rate_e, rate_why = rates.rate(pccy, acct_ccy, entry_at, ex.symbol, g["entry"])
    qg = g["quote_gross"]
    rate_x = prof / qg if abs(qg) >= MIN_QUOTE_GROSS else None
    if pccy and pccy == acct_ccy.upper():
        # SAME CURRENCY: the exit rate is 1 by definition. A booked profit that differs from the
        # price move is a bookkeeping gap and belongs in the residual, never in FX.
        rate_x = 1.0
    if rate_e is None:
        ex.why.append(f"FX unmeasured: {rate_why}")
        rate_e_used = rate_x if rate_x is not None else 1.0
        ex.fx_conversion = None
    else:
        ex.fx_status = MEASURED
        rate_e_used = rate_e
        ex.fx_conversion = qg * ((rate_x if rate_x is not None else rate_e) - rate_e)
    intended, iwhy = _intended(r, intents)
    at_entry_rate = qg * rate_e_used
    if intended:
        ex.slippage_status = MEASURED
        ex.entry_slippage = -(g["entry"] - intended) * g["dir"] * g["vol"] * g["cs"] * rate_e_used
        ex.signal = (g["exit"] - intended) * g["dir"] * g["vol"] * g["cs"] * rate_e_used
    else:
        ex.why.append(f"slippage unmeasured: {iwhy}")
        ex.signal_plus_slippage = at_entry_rate
    explained = ((ex.signal if ex.signal is not None else at_entry_rate)
                 + (ex.entry_slippage or 0.0) + ex.commission + ex.swap + ex.fees
                 + (ex.fx_conversion or 0.0))
    ex.residual = net - explained
    if abs(ex.residual) > RESIDUAL_TOL_ACCT:
        ex.why.append(f"residual {ex.residual:+.2f} exceeds {RESIDUAL_TOL_ACCT}")
    return ex


# --------------------------------------------------------------------------------- aggregates
def _blank() -> dict[str, Any]:
    return {"n_trades": 0, "n_unexplainable": 0, "net": 0.0, "signal": 0.0,
            "signal_plus_slippage_unsplit": 0.0, "entry_slippage": 0.0, "commission": 0.0,
            "swap": 0.0, "fees": 0.0, "fx_conversion": 0.0, "residual": 0.0,
            "abs_net": 0.0, "abs_net_slip_measured": 0.0, "abs_net_fx_measured": 0.0}


def _add(b: dict[str, Any], e: Explained) -> None:
    b["n_trades"] += 1
    b["net"] += e.net
    b["abs_net"] += abs(e.net)
    if not e.explainable:
        b["n_unexplainable"] += 1
        return
    if e.signal is not None:
        b["signal"] += e.signal
    if e.signal_plus_slippage is not None:
        b["signal_plus_slippage_unsplit"] += e.signal_plus_slippage
    b["entry_slippage"] += e.entry_slippage or 0.0
    b["commission"] += e.commission
    b["swap"] += e.swap
    b["fees"] += e.fees
    b["fx_conversion"] += e.fx_conversion or 0.0
    b["residual"] += e.residual or 0.0
    if e.slippage_status == MEASURED:
        b["abs_net_slip_measured"] += abs(e.net)
    if e.fx_status == MEASURED:
        b["abs_net_fx_measured"] += abs(e.net)


def _finish(b: dict[str, Any]) -> dict[str, Any]:
    out = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in b.items()}
    an = b["abs_net"]
    out["coverage_slippage"] = round(b["abs_net_slip_measured"] / an, 3) if an else UNMEASURED
    out["coverage_fx"] = round(b["abs_net_fx_measured"] / an, 3) if an else UNMEASURED
    gross_edge = b["signal"] + b["signal_plus_slippage_unsplit"]
    costs = b["entry_slippage"] + b["commission"] + b["swap"] + b["fees"]
    out["cost_drag"] = round(costs, 2)
    out["cost_drag_share_of_gross"] = (round(-costs / abs(gross_edge), 3)
                                       if abs(gross_edge) > 1e-9 else UNMEASURED)
    for k in ("abs_net", "abs_net_slip_measured", "abs_net_fx_measured"):
        out.pop(k, None)
    return out


def _acct_label(acct: tuple) -> str:
    key, server, kind = acct
    return f"{kind}|{server}|{str(key)[-8:] if key else 'unkeyed'}"


def explain(*, days: int = 90, now: datetime | None = None,
            ledger: list[dict[str, Any]] | None = None,
            prop: list[dict[str, Any]] | None = None,
            intents: list[dict[str, Any]] | None = None,
            meta: Mapping[str, Any] | None = None, state: Mapping[str, Any] | None = None,
            bars: Callable[[str], Any] | None = None) -> dict[str, Any]:
    from mt5desk.provenance import row_account
    now = now or datetime.now(UTC)
    rows = (ledger if ledger is not None else _jsonl(LEDGER)) + \
        (prop if prop is not None else _jsonl(PROP_LEDGER))
    if intents is None:
        intents = [r for p in INTENT_FILES for r in _jsonl(p)]
    meta = meta if meta is not None else _json(UNIVERSE)
    state = state if state is not None else _json(ACCOUNT_STATE)
    if bars is None:
        try:
            from research import proposer_common as pc
            bars = pc.bars
        except Exception:
            bars = None
    idx = intent_index(intents)
    rates = RateBook(meta, bars)
    by_acct: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("pl_quote") is None:
            continue
        by_acct[row_account(r)].append(r)
    since = (now - timedelta(days=days)).date()
    report: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/pnl_explain.py", "finding": "K4",
        "identity": "net = signal + entry_slippage + commission + swap + fees + fx_conversion "
                    "+ residual (account currency)",
        "window_days": days, "accounts": {}}
    trades_all: list[Explained] = []
    for acct, arows in sorted(by_acct.items(), key=lambda kv: str(kv[0])):
        ccy, ccy_why = account_currency(acct, arows, meta, state)
        label = _acct_label(acct)
        daily: dict[str, dict[str, Any]] = defaultdict(_blank)
        sleeves: dict[str, dict[str, Any]] = defaultdict(_blank)
        total = _blank()
        unreconciled: list[dict[str, Any]] = []
        for r in arows:
            e = explain_trade(r, label, ccy, meta, idx, rates)
            trades_all.append(e)
            if date.fromisoformat(e.day) < since:
                continue
            _add(daily[e.day], e)
            _add(sleeves[e.sleeve], e)
            _add(total, e)
            if not e.explainable or (e.residual is not None
                                     and abs(e.residual) > RESIDUAL_TOL_ACCT):
                unreconciled.append({k: v for k, v in asdict(e).items()
                                     if k in ("deal", "day", "sleeve", "symbol", "net",
                                              "residual", "why")})
        report["accounts"][label] = {
            "kind": acct[2], "server": acct[1], "account_currency": ccy or UNMEASURED,
            "account_currency_basis": ccy_why,
            "total": _finish(total),
            "daily": {d: _finish(b) for d, b in sorted(daily.items())},
            "by_sleeve": {s: _finish(b) for s, b in sorted(sleeves.items(),
                                                           key=lambda kv: kv[1]["net"])},
            "unreconciled": unreconciled[-50:],
            "n_unreconciled": len(unreconciled),
        }
    if not report["accounts"]:
        report["status"] = UNMEASURED
        report["why"] = "no closed trade with a booked net in any ledger on this host"
    else:
        report["status"] = "OK"
    report["latest_trades"] = [asdict(e) for e in sorted(trades_all, key=lambda e: e.day)[-60:]]
    return report


def append_closed_days(report: Mapping[str, Any], path: Path = DAILY,
                       now: datetime | None = None) -> int:
    """One row per (account, UTC day) for days that are OVER, appended once, never rewritten."""
    now = now or datetime.now(UTC)
    today = now.date().isoformat()
    seen: set[tuple[str, str]] = set()
    for r in _jsonl(path):
        seen.add((str(r.get("account")), str(r.get("day"))))
    new = []
    for label, a in (report.get("accounts") or {}).items():
        for d, b in (a.get("daily") or {}).items():
            if d >= today or (label, d) in seen:
                continue
            new.append({"account": label, "day": d, "account_currency":
                        a.get("account_currency"), **b,
                        "recorded_at": now.isoformat(timespec="seconds")})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in sorted(new, key=lambda r: (r["day"], r["account"])):
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return len(new)


def write_report(report: Mapping[str, Any], path: Path = REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    rep = explain(days=a.days)
    n_days = 0
    if not a.no_write:
        write_report(rep)
        n_days = append_closed_days(rep)
    for label, acc in rep["accounts"].items():
        t = acc["total"]
        print(f"  {label:<44} {acc['account_currency']:<4} n={t['n_trades']:<4} "
              f"net={t['net']:>9.2f} signal={t['signal']:>9.2f} "
              f"slip={t['entry_slippage']:>7.2f} comm={t['commission']:>7.2f} "
              f"swap={t['swap']:>7.2f} fx={t['fx_conversion']:>7.2f} resid={t['residual']:>7.2f}"
              f" cov_slip={t['coverage_slippage']}")
    print(f"pnl_explain: status={rep['status']} accounts={len(rep['accounts'])} "
          f"closed_days_appended={n_days}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
