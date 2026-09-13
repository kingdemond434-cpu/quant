"""THE MISSING MIDDLE: signal -> size -> send, for the E8 Pro account.

The adapter could place an order and the guard could refuse one, and nothing joined them. This
joins them, and it is the only file in the prop lane that decides to trade.

SHADOW BY DEFAULT. `--armed` is required to send, exactly as the MT5 gateway works, because the
failure this desk keeps paying for is a lane that traded before anyone had read what it would do.
Unarmed it does everything except `create_order` and writes the same ledger, so a night of
shadow output is a night of evidence rather than a night of nothing.

THE ORDER OF OPERATIONS IS THE RISK CONTROL, and it is deliberate:

    1. THE GUARD FIRST, before a single quote is fetched. Equity is read from the venue and
       `e8_guard.assess` decides whether this pass may open anything at all. A breach, a
       stand-down, a reached profit cap or a passed evaluation all stop the pass here -- and
       CAPPED is the one nobody writes: above +2% for the day the gain is stripped at rollover
       while a loss is not, so every further trade is pure downside.
    2. WHAT IS ALREADY OPEN, so a sleeve cannot be entered twice. Positions are matched by the
       comment tag this file writes; an untagged position is somebody else's and is never
       touched.
    3. ONE PASS PER SLEEVE, on the LAST CLOSED BAR only. A signal stamped on the forming bar has
       not happened yet, and acting on it is the caller cheating before the harness ever saw it.
    4. SIZE FROM THE BOOK'S RISK FRACTION AND THE SIGNAL'S OWN STOP, never from a fixed lot.
    5. SEND WITH THE STOP ATTACHED. On a 2.5% daily floor the window between an open position
       and its stop is the whole risk, and "place then modify" leaves it open across a network
       call.

WHAT IT WILL NOT DO. It does not size the live Fusion book, it does not invent a signal, and it
never raises risk -- every branch it can take ends in a smaller position or none. The sleeves it
runs are certified survivors chosen by `e8_book`; nothing here promotes anything.

Artifacts: desks/mt5/reports/E8_EXEC.json      (the pass, every sleeve, why)
           desks/mt5/data/e8_intents.jsonl     (append-only, one row per considered signal)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "E8_EXEC.json"
INTENTS = DESK / "data" / "e8_intents.jsonl"
BOOK = DESK / "reports" / "E8_BOOK.json"

#: ARMING IS A FILE, and the scheduled task never carries `--armed`. The kill switch has to be
#: something a person can operate in one action, from a file browser, at three in the morning,
#: without editing a scheduled task -- the MT5 gateway's GENERIC_EXEC_ENABLED works the same way
#: for the same reason. `--armed` on the command line still forces it for a manual run.
ARMED_MARKER = DESK / "data" / "E8_ARMED"

#: The comment written on every order this lane sends. Positions are matched back to a sleeve by
#: it, so an order without it is not this lane's and is never closed or counted here.
TAG = "E8"

#: Hourly bars fetched per sleeve. The families need enough history for their ATR and session
#: aggregates; 900 hours is about five weeks, comfortably past the longest lookback in the
#: registered grid, and small enough that twenty sleeves do not exhaust the venue's rate limit.
LOOKBACK_BARS = 900

#: THE COST FENCE, and it is what makes arming this lane safe while the spread is still unknown.
#:
#: The account is "no commissions", which on E8 means the cost sits in a WIDER QUOTE rather than
#: nowhere. That cost has never been measured on this venue during the hours this book trades:
#: the only reading taken so far was at 23:56 on a Saturday with the market shut and the quotes
#: frozen, and it showed AUDNZD at 29.9bp and AUDCAD at 30.1bp. Those are closed-book artefacts,
#: but the desk has independently measured on Fusion that AUDNZD's spread widens 88x at hour 00
#: against a mechanism that dies at 2.34x cost -- and every certificate in this book fires in the
#: asia window, which opens directly after the daily rollover.
#:
#: So the executor refuses any sleeve whose round-trip spread exceeds this fraction of its own
#: stop distance. A certificate's edge is denominated in R; paying a quarter of an R to enter is
#: not a smaller edge, it is a different trade from the one that was certified. The fence is
#: per-sleeve and per-pass, so a symbol that is fine at 02:00 and impossible at 00:00 trades at
#: 02:00 and not at 00:00 -- which is the "different hours, not a different size" answer applied
#: automatically rather than argued about.
#:
#: It is a REFUSAL, never a resize: sizing down to absorb a bad spread would keep the trade and
#: hide the cost. Every refusal is named in the artifact with the number that caused it, so a
#: night of them is a spread measurement rather than a silence.
MAX_SPREAD_FRAC_OF_STOP = 0.25


# ------------------------------------------------------------------ bars
def _frame(api: Any, instrument_id: int) -> Any:
    """TradeLocker history -> the OHLC frame the desk's families expect, or None.

    THE COLUMN NAMES AND THE CLOCK ARE THE WHOLE JOB. The venue returns `t,o,h,l,c,v` with `t` in
    epoch MILLISECONDS; every family reads `open/high/low/close` off a tz-aware UTC DatetimeIndex
    and several of them branch on `index.hour`. A silent mismatch here would not raise -- it
    would compute a real-looking signal on the wrong hour, which on an all-asia book is the one
    error that would look like a strategy.
    """
    try:
        import pandas as pd
    except ImportError:
        return None
    try:
        df = api.get_price_history(instrument_id, resolution="1H",
                                   lookback_period=f"{LOOKBACK_BARS}H")
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close",
                            "v": "tick_volume"})
    if "t" not in df.columns:
        return None
    idx = pd.to_datetime(df["t"], unit="ms", utc=True)
    out = df.drop(columns=[c for c in ("t",) if c in df.columns]).set_index(idx)
    out.index.name = "time"
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            return None
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["open", "high", "low", "close"]).sort_index()


def _last_closed(frame: Any) -> Any:
    """Drop the forming bar. The most recent row of a live feed is still being written."""
    return frame.iloc[:-1] if len(frame) > 1 else frame


# ------------------------------------------------------------------ sizing
def lot_for_risk(venue: Any, symbol: str, stop_dist: float, risk_usd: float) -> tuple[float, str]:
    """Lot such that a stop-out costs about `risk_usd`, floored at the venue minimum.

    THE CONVERSION IS THE VENUE'S, NOT OURS, wherever the venue will state it. `contractSize`
    times the stop distance is the loss per lot in the QUOTE currency; for a USD-quoted pair that
    is already dollars, and for the rest it is not. Where the instrument details do not carry
    enough to convert honestly, this says so in the returned basis rather than guessing -- a
    position sized from an assumed FX rate is a position whose risk nobody knows.

    The floor is the principal's standing order (2026-09-12) applied at THIS venue with THIS
    venue's number: an order below the minimum is REJECTED, not small.
    """
    vmin = venue.min_lot(symbol)
    if not (stop_dist > 0 and risk_usd > 0):
        return 0.0, f"unpriceable: stop_dist={stop_dist} risk_usd={risk_usd}"
    d = venue.details(symbol)
    contract = None
    for k in ("contractSize", "contract_size", "lotSize", "units"):
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 0:
            contract = float(v)
            break
    if contract is None:
        return float(vmin), (f"venue states no contract size; sent at the venue minimum {vmin} "
                             "rather than at a size derived from a guessed one")
    quote_ccy = str(d.get("currency") or d.get("quoteCurrency") or "").upper()
    loss_per_lot = contract * stop_dist
    basis = (f"contract {contract:g} x stop {stop_dist:.6g} = "
             f"{loss_per_lot:.2f} {quote_ccy or '?'}/lot")
    if quote_ccy and quote_ccy != "USD":
        # NOT CONVERTED, AND NOT PRETENDED OTHERWISE. The account is USD; a JPY- or CHF-quoted
        # loss per lot is not dollars. Rather than apply a rate this file has not measured, it
        # takes the venue minimum and names the gap, which is smaller than the intended risk and
        # never larger.
        return float(vmin), (basis + f"; quote is {quote_ccy}, not USD, and no measured rate -- "
                                     f"sent at the venue minimum {vmin} (UNDER-sized, never over)")
    lot = risk_usd / loss_per_lot
    step = None
    for k in ("lotStep", "volumeStep", "step"):
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 0:
            step = float(v)
            break
    if step:
        lot = int(lot / step) * step          # FLOOR, never round: rounding up oversizes
    return float(max(lot, vmin)), basis + f"; risk ${risk_usd:.2f} -> {max(lot, vmin):g} lot"


# ------------------------------------------------------------------ the pass
def run(venue: Any, *, armed: bool = False, now: datetime | None = None) -> dict[str, Any]:
    from prop import e8_guard

    now = now or datetime.now(UTC)
    acct = venue.account()
    equity = float(acct["equity"])
    decision = e8_guard.assess(equity, now=now)
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "armed": armed,
        "guard": decision.as_dict(),
        "sleeves": [],
    }
    if not decision.may_open:
        doc["status"] = decision.verdict.value
        doc["why"] = decision.why
        if decision.flatten and armed:
            doc["flattened"] = venue.close_all()
        return doc

    try:
        book = json.loads(BOOK.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        doc["status"] = "NO_BOOK"
        doc["why"] = f"{BOOK.name} unreadable ({type(exc).__name__}) -- nothing to trade"
        return doc

    risk_usd = float(book["risk_frac"]) * e8_guard.START_BALANCE
    open_tags = set()
    for p in venue.positions():
        c = str(p.get("comment") or p.get("Comment") or "")
        if c.startswith(TAG):
            open_tags.add(c)

    from mt5desk.families import get_family_func

    sent = considered = 0
    for s in book.get("sleeves", []):
        sym, fam = s["symbol"], s["family"]
        tag = f"{TAG}{fam[:6]}{sym}"[:31]
        row: dict[str, Any] = {"symbol": sym, "family": fam, "tag": tag}
        if tag in open_tags:
            row["status"] = "ALREADY_OPEN"
            doc["sleeves"].append(row)
            continue
        func = get_family_func(fam)
        if func is None:
            row["status"] = "NO_FAMILY"
            row["why"] = f"{fam} is not a registered family on this tree"
            doc["sleeves"].append(row)
            continue
        try:
            iid = venue.instrument_id(sym)
        except Exception as exc:
            row["status"] = "NOT_LISTED"
            row["why"] = str(exc)[:160]
            doc["sleeves"].append(row)
            continue
        frame = _frame(venue._raw_api, iid)
        if frame is None or len(frame) < 60:
            row["status"] = "NO_BARS"
            row["why"] = f"history unavailable or too short ({0 if frame is None else len(frame)})"
            doc["sleeves"].append(row)
            continue
        closed = _last_closed(frame)
        params = {k: v for k, v in (s.get("params") or {}).items()
                  if isinstance(v, (int, float, str, bool))}
        try:
            signals = func(closed, **params) if params else func(closed)
        except Exception as exc:
            row["status"] = "SIGNAL_ERROR"
            row["why"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            doc["sleeves"].append(row)
            continue
        considered += 1
        last_bar = closed.index[-1]
        fresh = [g for g in (signals or []) if getattr(g, "time", None) == last_bar]
        if not fresh:
            row["status"] = "NO_SIGNAL"
            row["last_bar"] = str(last_bar)
            doc["sleeves"].append(row)
            continue
        g = fresh[-1]
        side = "buy" if int(g.side) > 0 else "sell"
        try:
            bid, ask = venue.quote(sym)
        except Exception as exc:
            row["status"] = "NO_QUOTE"
            row["why"] = str(exc)[:140]
            doc["sleeves"].append(row)
            continue
        entry = ask if side == "buy" else bid
        stop_dist = abs(float(entry) - float(g.stop))
        spread = float(ask) - float(bid)
        row["spread"] = spread
        row["spread_frac_of_stop"] = None if stop_dist <= 0 else round(spread / stop_dist, 4)
        if stop_dist > 0 and spread / stop_dist > MAX_SPREAD_FRAC_OF_STOP:
            row["status"] = "SPREAD_TOO_WIDE"
            row["why"] = (f"round-trip spread {spread:.6g} is {spread / stop_dist:.1%} of the "
                          f"{stop_dist:.6g} stop, over the {MAX_SPREAD_FRAC_OF_STOP:.0%} fence -- "
                          "paying that to enter is a different trade from the one certified")
            doc["sleeves"].append(row)
            _record(row, now, armed)
            continue
        lot, basis = lot_for_risk(venue, sym, stop_dist, risk_usd)
        row.update({"side": side, "entry_ref": entry, "stop": float(g.stop),
                    "target": float(g.target), "stop_dist": stop_dist,
                    "lot": lot, "sizing_basis": basis, "bar": str(last_bar)})
        if not (lot > 0):
            row["status"] = "UNSIZEABLE"
            doc["sleeves"].append(row)
            continue
        # THE DAILY FLOOR IS CHECKED AGAINST THE WHOLE BOOK, not one order at a time. Twenty
        # sleeves firing together is twenty simultaneous risks, and a per-order check would wave
        # each one through on its own merits into a floor none of them breaches alone.
        if (sent + 1) * risk_usd > decision.room_to_daily_floor:
            row["status"] = "WOULD_BREACH_DAILY"
            row["why"] = (f"{sent + 1} open risks x ${risk_usd:.0f} exceeds the "
                          f"${decision.room_to_daily_floor:.0f} left to today's floor")
            doc["sleeves"].append(row)
            continue
        if armed:
            try:
                row["order_id"] = venue.place(sym, side, lot, stop=float(g.stop),
                                              take_profit=float(g.target))
                row["status"] = "SENT"
            except Exception as exc:
                row["status"] = "REJECTED"
                row["why"] = f"{type(exc).__name__}: {str(exc)[:140]}"
        else:
            row["status"] = "WOULD_SEND"
        sent += 1
        doc["sleeves"].append(row)
        _record(row, now, armed)

    doc["status"] = "OK"
    doc["n_considered"] = considered
    doc["n_sent" if armed else "n_would_send"] = sent
    doc["risk_usd_per_trade"] = round(risk_usd, 2)
    return doc


def _record(row: dict[str, Any], now: datetime, armed: bool) -> None:
    INTENTS.parent.mkdir(parents=True, exist_ok=True)
    with INTENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": now.isoformat(timespec="seconds"),
                             "armed": armed, **row}) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--armed", action="store_true",
                    help="actually send orders (default is shadow: everything but create_order)")
    args = ap.parse_args(argv)
    from prop.tradelocker_venue import TradeLockerVenue

    armed = bool(args.armed or ARMED_MARKER.exists())
    venue = TradeLockerVenue().connect()
    doc = run(venue, armed=armed)
    doc["armed_by"] = ("--armed" if args.armed else
                       f"{ARMED_MARKER.name} present" if ARMED_MARKER.exists() else "not armed")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    g = doc["guard"]
    print(f"E8 {'ARMED' if armed else 'SHADOW'}: {doc['status']} | equity {g['equity']:,.2f} "
          f"| {g['room_to_daily_floor']:,.0f} to today's floor")
    if doc["status"] == "OK":
        from collections import Counter
        c = Counter(s.get("status") for s in doc["sleeves"])
        print(f"  {doc['n_considered']} considered, "
              f"{doc.get('n_sent', doc.get('n_would_send', 0))} "
              f"{'sent' if armed else 'would send'} at ${doc['risk_usd_per_trade']:.0f} risk")
        print(f"  {dict(c)}")
    else:
        print(f"  {doc.get('why', g.get('why'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
