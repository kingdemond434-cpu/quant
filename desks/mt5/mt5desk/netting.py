"""Theoretical sleeve positions, netted into one portfolio target per instrument.

WonderTrader's separation, reimplemented: each sleeve keeps its THEORETICAL position (what its
strategy wants, in lots, signed) and its own virtual P&L; the venue sees only the NET target per
symbol. Two sleeves long and short the same instrument at once do not pay two spreads, two
swaps and double margin to hold a position the account does not have.

    theoretical:  A XAUUSD +0.20   B XAUUSD -0.08   C XAUUSD +0.05
    net target:   XAUUSD +0.17
    saved:        0.16 lots of round trips that would have cancelled

ATTRIBUTION IS PRESERVED. Virtual P&L is marked per sleeve from the sleeve's own theoretical
position and the instrument's price path, never from the netted fills, so netting changes what
the broker sees and nothing about what each edge is credited with.

WHAT THIS MODULE DOES ON THE DESK TODAY. The bracket sleeves place two-sided pending stops and
resolve their direction only on a fill, so netting applies to the family-market sleeves and to
open positions. `net_targets` is the pure function; `savings_report` measures, from the intent
ledger, how much opposing exposure the desk has actually been carrying -- the number that says
whether routing through the netting engine is worth the execution change. Routing itself is a
money-path change and is left to a separate, box-verified step; this measures first.

THE RUNNING LEDGER (`TheoreticalBook`). The pure function answers "what would the net be"; it
cannot answer "what must the executor trade NOW", because that needs what the venue has already
given us. The book is that ledger: every sleeve's theoretical target and every fill the account
received, appended to a JSONL file and replayed on load, so a restart rebuilds the same book the
previous process held rather than trusting whatever the terminal happens to show. Its one
identity is the netting rule:

    delta(symbol) = net target - account position = SUM over sleeves (target - filled)

which is why opposite theoretical positions across sleeves net at the account while the ledger
keeps each sleeve whole. `route` turns the delta into the ONE order the venue should see; the
book never sends anything, and today the gateway still sends per sleeve -- so the book measures
(net target against what per-sleeve orders actually built) before it is ever allowed to route.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
INTENTS = BASE / "data" / "order_intents.jsonl"
REPORT = BASE / "reports" / "NETTING.json"
#: The theoretical-position ledger: one row per target change or fill, append-only, replayed on
#: load. Position truth lives here, not in the terminal, so the file is written BEFORE the
#: in-memory state is trusted and an unwritable ledger raises rather than diverging silently.
NETTING_LEDGER = BASE / "data" / "theoretical_positions.jsonl"
#: The book-measured savings report. Kept apart from REPORT (the intent-ledger measurement the
#: daily execution-intelligence cycle writes) so the two measurements never overwrite each other.
REPORT_BOOK = BASE / "reports" / "NETTING_BOOK.json"
#: Sleeve tag for a fill the book could not attribute to any sleeve's outstanding delta.
UNATTRIBUTED = "net"


@dataclass(frozen=True)
class Theoretical:
    sleeve: str
    symbol: str
    lots: float                      # signed: +long, -short


def net_targets(positions: Iterable[Theoretical], lot_step: float = 0.01
                ) -> dict[str, dict[str, Any]]:
    """Per symbol: the net target, the gross the sleeves wanted, and what netting saved."""
    by_sym: dict[str, list[Theoretical]] = {}
    for p in positions:
        by_sym.setdefault(p.symbol, []).append(p)
    out: dict[str, dict[str, Any]] = {}
    for sym, ps in by_sym.items():
        net = sum(p.lots for p in ps)
        gross = sum(abs(p.lots) for p in ps)
        net_r = round(round(net / lot_step) * lot_step, 8)
        out[sym] = {"net_lots": net_r, "gross_lots": round(gross, 8),
                    "saved_lots": round(gross - abs(net), 8),
                    "legs": {p.sleeve: p.lots for p in ps},
                    "opposing": bool(any(p.lots > 0 for p in ps) and any(p.lots < 0 for p in ps))}
    return out


def virtual_pnl(theoretical: Mapping[str, Theoretical], price_now: Mapping[str, float],
                price_prev: Mapping[str, float], point_value: Mapping[str, float]
                ) -> dict[str, float]:
    """Mark each sleeve's theoretical position on the instrument's move. Attribution survives
    netting because it never looks at the netted fill."""
    out: dict[str, float] = {}
    for name, t in theoretical.items():
        if t.symbol not in price_now or t.symbol not in price_prev:
            continue
        dp = float(price_now[t.symbol]) - float(price_prev[t.symbol])
        out[name] = round(t.lots * dp * float(point_value.get(t.symbol, 1.0)), 6)
    return out


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _bucket_savings(xs: list[tuple[datetime, float]], window_h: float) -> tuple[float, float]:
    """Gross lots, and the lots that opposing legs inside one `window_h` bucket would have
    collapsed. Buckets open at the first leg and close `window_h` later; one pass, no overlap."""
    xs = sorted(xs)
    gross = sum(abs(x) for _, x in xs)
    saved = 0.0
    i = 0
    while i < len(xs):
        j = i
        bucket = []
        while j < len(xs) and (xs[j][0] - xs[i][0]).total_seconds() <= window_h * 3600:
            bucket.append(xs[j][1])
            j += 1
        saved += sum(abs(x) for x in bucket) - abs(sum(bucket))
        i = j
    return gross, saved


def _verdict(tot_gross: float, tot_saved: float) -> str:
    return ("NETTING_WORTH_ROUTING" if tot_gross > 0 and tot_saved / tot_gross > 0.05
            else ("NETTING_IMMATERIAL" if tot_gross > 0 else "UNMEASURED"))


def savings_report(intents: list[dict[str, Any]] | TheoreticalBook | None = None, *,
                   window_h: float = 24.0, write: bool = True,
                   spread_frac: Mapping[str, float] | None = None) -> dict[str, Any]:
    """How much opposing exposure the desk carried, per symbol, from the intent ledger.

    Intents within `window_h` of each other on the same symbol with opposite sides are the
    round trips netting would have collapsed. Reported in lots and as a share of gross.

    Given a `TheoreticalBook` instead of intents, the same measurement is taken on the sleeves'
    theoretical target changes (see `book_savings`), which is the honest version: intents are
    what was sent, targets are what was WANTED, and the gap between them is the engine's job.
    """
    if isinstance(intents, TheoreticalBook):
        return book_savings(intents, window_h=window_h, write=write, spread_frac=spread_frac)
    rows = intents if intents is not None else _rows(INTENTS)
    by_sym: dict[str, list[tuple[datetime, float]]] = {}
    for r in rows:
        try:
            t = datetime.fromisoformat(str(r.get("time")))
            lot = float(r.get("lot") or 0.0)
            side = str(r.get("side") or "")
        except (TypeError, ValueError):
            continue
        sgn = 1.0 if side.startswith("buy") else (-1.0 if side.startswith("sell") else 0.0)
        if sgn == 0.0 or lot <= 0:
            continue
        by_sym.setdefault(str(r.get("symbol")), []).append((t, sgn * lot))
    per: dict[str, dict[str, float]] = {}
    tot_gross = tot_saved = 0.0
    for sym, xs in by_sym.items():
        gross, saved = _bucket_savings(xs, window_h)
        per[sym] = {"gross_lots": round(gross, 4), "opposing_lots": round(saved, 4),
                    "share": round(saved / gross, 4) if gross > 0 else 0.0}
        tot_gross += gross
        tot_saved += saved
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "intents": len(rows),
           "window_h": window_h, "per_symbol": per, "gross_lots": round(tot_gross, 4),
           "opposing_lots": round(tot_saved, 4),
           "opposing_share": round(tot_saved / tot_gross, 4) if tot_gross > 0 else 0.0,
           "verdict": _verdict(tot_gross, tot_saved),
           "rule": "opposing exposure inside one window on one symbol is what a netting engine "
                   "would have collapsed; attribution stays per sleeve on theoretical positions"}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


# --------------------------------------------------------------------------- the running ledger
def _iso(at: datetime | str | None) -> str:
    if at is None:
        return datetime.now(tz=UTC).isoformat()
    return at.isoformat() if isinstance(at, datetime) else str(at)


def _when(at: str) -> datetime | None:
    """A ledger timestamp as an aware datetime; a naive one is read as UTC, an unreadable one
    is dropped from time-bucketed measurements rather than guessed."""
    try:
        t = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _sign(x: float) -> float:
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _blank_state() -> dict[str, Any]:
    return {"lots": 0.0, "avg_entry": None, "realised": 0.0, "filled": 0.0, "fill_notional": 0.0,
            "reason": "", "at": "", "row": None}


class TheoreticalBook:
    """Append-only ledger of per-sleeve theoretical positions and account fills.

    WHY A LEDGER AND NOT A DICT. The netting decision is a function of two things the process
    does not otherwise remember across restarts: what every sleeve currently WANTS and what the
    venue has already GIVEN. The terminal can report open positions but not which sleeve's
    intent they serve; the intent ledger records orders, not desired positions. So the book
    writes each change as it happens and rebuilds itself by replay, and the file is the truth --
    which is why `_append` raises on failure instead of logging and carrying on: a book whose
    memory and disk disagree would send the wrong delta after the next restart.

    Idempotent by construction: re-stating the target a sleeve already holds appends nothing, so
    a gateway pass that re-asserts every sleeve every minute does not grow the file.

    ATTRIBUTION FROM THE SLEEVE'S OWN MARKS. `set_target(..., price=)` records the price the
    sleeve wanted its position at; the book carries each sleeve's average entry and realised
    P&L from those marks, never from the netted fills. Two sleeves long and short the same
    instrument therefore show equal and opposite P&L while the account shows none -- netting
    changed what the broker saw, not what each edge is credited with. A target set without a
    price leaves the sleeve UNMARKED and it is omitted from attribution rather than shown at
    zero, because a zero would be a claim.
    """

    def __init__(self, path: Path | str | None = None, *, persist: bool = True) -> None:
        self.path: Path | None = (Path(path) if path is not None else NETTING_LEDGER) if persist \
            else None
        self._sleeves: dict[str, dict[str, dict[str, Any]]] = {}
        self._flow: dict[str, list[tuple[datetime, float]]] = {}
        self.routes: list[dict[str, Any]] = []
        self.rows = 0
        if self.path is not None:
            self.replay()

    # -- persistence ---------------------------------------------------------------------------
    def replay(self) -> int:
        """Rebuild the in-memory book from the ledger. Rows that cannot be read are counted and
        skipped, never guessed at; the count is in `snapshot()['unreadable']`."""
        self._sleeves.clear()
        self._flow.clear()
        self.rows = 0
        self.unreadable = 0
        if self.path is None or not self.path.exists():
            return 0
        for ln in self.path.read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
                self._apply(row)
            except (ValueError, KeyError, TypeError):
                self.unreadable += 1
                continue
            self.rows += 1
        return self.rows

    def _append(self, row: dict[str, Any]) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")
        self.rows += 1

    def _state(self, symbol: str, sleeve: str) -> dict[str, Any]:
        return self._sleeves.setdefault(symbol, {}).setdefault(sleeve, _blank_state())

    def _apply(self, row: dict[str, Any]) -> None:
        kind = row["kind"]
        s = self._state(str(row["symbol"]), str(row["sleeve"]))
        lots = float(row["lots"])
        if kind == "fill":
            s["filled"] = round(s["filled"] + lots, 8)
            s["fill_notional"] += lots * float(row["price"])
            return
        if kind != "target":
            raise ValueError(f"unknown ledger row kind {kind!r}")
        old = float(s["lots"])
        px = row.get("price")
        px = float(px) if px is not None else None
        if px is not None:
            if old != 0.0 and (lots == 0.0 or _sign(lots) != _sign(old)):
                # Closing everything the sleeve held (flat, or flipping): realise the whole leg
                # at this mark; a flip opens the new leg at the same mark.
                if s["avg_entry"] is not None:
                    s["realised"] += old * (px - s["avg_entry"])
                s["avg_entry"] = px if lots != 0.0 else None
            elif old != 0.0 and abs(lots) < abs(old):
                # Reducing: realise the closed part, the average entry of the rest stands.
                if s["avg_entry"] is not None:
                    s["realised"] += (old - lots) * (px - s["avg_entry"])
            elif abs(lots) > abs(old):
                # Adding (or opening from flat): lot-weighted average entry.
                if s["avg_entry"] is None or old == 0.0:
                    s["avg_entry"] = px
                else:
                    s["avg_entry"] = ((abs(old) * s["avg_entry"] + (abs(lots) - abs(old)) * px)
                                      / abs(lots))
        elif lots == 0.0:
            s["avg_entry"] = None
        s["lots"] = lots
        s["reason"] = str(row.get("reason") or "")
        s["at"] = str(row.get("at") or "")
        s["row"] = row
        t = _when(s["at"])
        if t is not None and lots != old:
            self._flow.setdefault(str(row["symbol"]), []).append((t, lots - old))

    # -- writes --------------------------------------------------------------------------------
    def set_target(self, sleeve: str, symbol: str, lots_signed: float, reason: str = "",
                   at: datetime | str | None = None, *, price: float | None = None
                   ) -> dict[str, Any]:
        """Record what `sleeve` wants to hold in `symbol` (signed lots). Returns the row, with
        `appended=False` when the sleeve already held exactly this target (idempotent)."""
        lots = round(float(lots_signed), 8)
        cur = self._sleeves.get(symbol, {}).get(sleeve)
        if (cur is None and lots == 0.0) or (cur is not None and cur["lots"] == lots):
            base = cur["row"] if cur is not None and cur["row"] else \
                {"kind": "target", "sleeve": sleeve, "symbol": symbol, "lots": lots}
            return {**base, "appended": False}
        row: dict[str, Any] = {"kind": "target", "sleeve": sleeve, "symbol": symbol, "lots": lots,
                               "reason": str(reason or ""), "at": _iso(at)}
        if price is not None:
            row["price"] = float(price)
        self._apply(row)
        self._append(row)
        return {**row, "appended": True}

    def fill(self, sleeve: str, symbol: str, lots_signed: float, price: float,
             at: datetime | str | None = None) -> dict[str, Any] | None:
        """Record what the venue gave (signed lots at `price`), tagged with the sleeve whose
        order it answered -- or `UNATTRIBUTED` for a net order. A zero fill is not a row."""
        lots = round(float(lots_signed), 8)
        if lots == 0.0:
            return None
        row = {"kind": "fill", "sleeve": sleeve, "symbol": symbol, "lots": lots,
               "price": float(price), "at": _iso(at)}
        self._apply(row)
        self._append(row)
        return row

    def allocate_fill(self, symbol: str, lots_signed: float, price: float,
                      at: datetime | str | None = None) -> list[dict[str, Any]]:
        """Split one ACCOUNT-level fill (a net order's) across the sleeves whose outstanding
        delta has its sign, pro rata, so per-sleeve `filled` stays meaningful once the venue
        sees net orders. Anything beyond every sleeve's outstanding is tagged `UNATTRIBUTED`."""
        lots = round(float(lots_signed), 8)
        if lots == 0.0:
            return []
        sgn = _sign(lots)
        want = [(c["sleeve"], c["outstanding"]) for c in self.contributions(symbol)
                if _sign(c["outstanding"]) == sgn]
        total = sum(abs(o) for _, o in want)
        rows: list[dict[str, Any]] = []
        left = abs(lots)
        for k, (sleeve, out) in enumerate(want):
            share = abs(out) if k == len(want) - 1 else abs(out) / total * abs(lots)
            take = round(min(share, abs(out), left), 8)
            if take <= 0:
                continue
            r = self.fill(sleeve, symbol, sgn * take, price, at)
            if r is not None:
                rows.append(r)
            left = round(left - take, 8)
        if left > 0:
            r = self.fill(UNATTRIBUTED, symbol, sgn * left, price, at)
            if r is not None:
                rows.append(r)
        return rows

    # -- reads ---------------------------------------------------------------------------------
    def symbols(self) -> list[str]:
        return sorted(self._sleeves)

    def theoretical(self, symbol: str) -> dict[str, float]:
        """Each sleeve's theoretical (signed) lots. Flat sleeves are not positions."""
        return {k: s["lots"] for k, s in self._sleeves.get(symbol, {}).items() if s["lots"]}

    def filled(self, symbol: str) -> dict[str, float]:
        return {k: s["filled"] for k, s in self._sleeves.get(symbol, {}).items() if s["filled"]}

    def net_target(self, symbol: str) -> float:
        return round(sum(s["lots"] for s in self._sleeves.get(symbol, {}).values()), 8)

    def account_position(self, symbol: str) -> float:
        return round(sum(s["filled"] for s in self._sleeves.get(symbol, {}).values()), 8)

    def delta(self, symbol: str) -> float:
        """What the executor must trade now: net target less what the account already holds."""
        return round(self.net_target(symbol) - self.account_position(symbol), 8)

    def contributions(self, symbol: str) -> list[dict[str, Any]]:
        """Per sleeve: target, filled and the outstanding difference. The outstandings sum to
        `delta(symbol)` exactly -- that identity is the netting rule."""
        out = []
        for sleeve, s in sorted(self._sleeves.get(symbol, {}).items()):
            if not s["lots"] and not s["filled"]:
                continue
            out.append({"sleeve": sleeve, "target": s["lots"], "filled": s["filled"],
                        "outstanding": round(s["lots"] - s["filled"], 8),
                        "reason": s["reason"]})
        return out

    def attribution(self, symbol: str, price_now: float, *, point_value: float = 1.0
                    ) -> dict[str, float]:
        """Each sleeve's P&L on its THEORETICAL position from its own average entry (realised
        plus open), in quote currency once `point_value` (per lot per price unit) is supplied.
        Unmarked sleeves are omitted, not zeroed."""
        out: dict[str, float] = {}
        for sleeve, s in self._sleeves.get(symbol, {}).items():
            if s["lots"] and s["avg_entry"] is None:
                continue
            if not s["lots"] and not s["realised"]:
                continue
            open_pnl = s["lots"] * (float(price_now) - s["avg_entry"]) if s["lots"] else 0.0
            out[sleeve] = round((s["realised"] + open_pnl) * float(point_value), 6)
        return out

    def snapshot(self) -> dict[str, Any]:
        syms: dict[str, Any] = {}
        for sym in self.symbols():
            sleeves = {k: {"lots": s["lots"], "avg_entry": s["avg_entry"],
                           "realised": round(s["realised"], 8), "filled": s["filled"],
                           "fill_vwap": (round(s["fill_notional"] / s["filled"], 8)
                                         if s["filled"] else None),
                           "reason": s["reason"], "at": s["at"]}
                       for k, s in sorted(self._sleeves[sym].items())
                       if s["lots"] or s["filled"] or s["realised"]}
            syms[sym] = {"net_target": self.net_target(sym),
                         "account_position": self.account_position(sym),
                         "delta": self.delta(sym),
                         "unmarked": sorted(k for k, s in self._sleeves[sym].items()
                                            if s["lots"] and s["avg_entry"] is None),
                         "sleeves": sleeves}
        return {"generated_utc": datetime.now(tz=UTC).isoformat(),
                "path": str(self.path) if self.path is not None else None,
                "rows": self.rows, "unreadable": getattr(self, "unreadable", 0),
                "symbols": syms, "routes": len(self.routes)}

    def flow(self, symbol: str) -> list[tuple[datetime, float]]:
        """Signed target changes over time -- the orders the sleeves would have sent alone."""
        return list(self._flow.get(symbol, []))


def route(book: TheoreticalBook, symbol: str, price_now: float, *, lot_step: float = 0.01,
          lot_min: float = 0.01) -> dict[str, Any]:
    """The ONE order the venue should see for `symbol` given every sleeve's target and fill.

    Rounds the delta to the symbol's lot step (nearest, as `net_targets` does) and refuses --
    lots 0, with `why` -- when the rounded delta is under the minimum lot; the remainder is not
    lost, it stays outstanding in the book until it accumulates into a sendable order. Records
    the saving on the decision: the gross lots the sleeves would have sent on their own against
    the net actually routed. Never sends.
    """
    contribs = book.contributions(symbol)
    delta = book.delta(symbol)
    gross = round(sum(abs(c["outstanding"]) for c in contribs), 8)
    lots = round(round(abs(delta) / lot_step) * lot_step, 8) if lot_step > 0 else abs(delta)
    side = "buy" if delta > 0 else ("sell" if delta < 0 else "flat")
    out: dict[str, Any] = {"symbol": symbol, "side": side, "lots": lots, "delta": delta,
                           "gross_lots": gross, "netted_lots": round(gross - abs(delta), 8),
                           "price_now": float(price_now), "sleeves": contribs, "why": None,
                           "at": datetime.now(tz=UTC).isoformat()}
    if lots <= 0.0 or lots + 1e-12 < lot_min:
        out["lots"] = 0.0
        out["why"] = ("sleeves net to flat: nothing to send" if delta == 0.0 else
                      f"delta {delta:+.6g} rounds to {lots} lots, under lot_min {lot_min}; "
                      f"carried forward in the book")
    last = next((r for r in reversed(book.routes) if r["symbol"] == symbol), None)
    keys = ("side", "lots", "delta", "netted_lots")
    if last is None or any(last[k] != out[k] for k in keys):
        book.routes.append(out)
    return out


def book_savings(book: TheoreticalBook, *, window_h: float = 24.0, write: bool = True,
                 spread_frac: Mapping[str, float] | None = None) -> dict[str, Any]:
    """`savings_report` semantics on the book: gross vs net lots, plus the spread not paid.

    Two measurements, named apart because they are different money. `per_symbol` buckets the
    sleeves' target CHANGES exactly as the intent report buckets sent orders (`window_h`), so the
    verdict is comparable with the intent-ledger report. `carried` is the opposing exposure the
    sleeves hold right now -- margin and swap the account is spared while both legs stand.
    `spread_saved_frac` is the collapsed lots times each symbol's spread as a fraction of price
    (caller-supplied), i.e. sum of lots x fraction; multiply by price x contract size for quote
    currency. Symbols without a supplied spread report null there rather than zero.
    """
    spreads = dict(spread_frac or {})
    per: dict[str, dict[str, Any]] = {}
    tot_gross = tot_saved = tot_spread = 0.0
    for sym in book.symbols():
        gross, saved = _bucket_savings(book.flow(sym), window_h)
        sf = spreads.get(sym)
        per[sym] = {"gross_lots": round(gross, 4), "opposing_lots": round(saved, 4),
                    "share": round(saved / gross, 4) if gross > 0 else 0.0,
                    "spread_frac": sf,
                    "spread_saved_frac": (round(saved * float(sf), 8) if sf is not None
                                          else None)}
        tot_gross += gross
        tot_saved += saved
        tot_spread += saved * float(sf) if sf is not None else 0.0
    carried = net_targets(Theoretical(k, sym, lots) for sym in book.symbols()
                          for k, lots in book.theoretical(sym).items())
    routed = {"n": len(book.routes),
              "sent_lots": round(sum(r["lots"] for r in book.routes), 4),
              "netted_lots": round(sum(r["netted_lots"] for r in book.routes), 4),
              "refused": sum(1 for r in book.routes if r["why"])}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "source": "theoretical_book",
           "ledger": str(book.path) if book.path is not None else None, "rows": book.rows,
           "window_h": window_h, "per_symbol": per, "gross_lots": round(tot_gross, 4),
           "opposing_lots": round(tot_saved, 4),
           "opposing_share": round(tot_saved / tot_gross, 4) if tot_gross > 0 else 0.0,
           "spread_saved_frac": round(tot_spread, 8),
           "carried": {sym: {"gross_lots": v["gross_lots"], "net_lots": v["net_lots"],
                             "saved_lots": v["saved_lots"], "opposing": v["opposing"]}
                       for sym, v in carried.items()},
           "routed": routed,
           "verdict": _verdict(tot_gross, tot_saved),
           "rule": "opposing target changes inside one window on one symbol are what the engine "
                   "collapses at the venue; attribution stays per sleeve on theoretical "
                   "positions from the sleeve's own marks"}
    if write:
        REPORT_BOOK.parent.mkdir(parents=True, exist_ok=True)
        REPORT_BOOK.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc
