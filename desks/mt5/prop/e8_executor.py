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
from datetime import UTC, datetime, timedelta
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
#: Desk chart -> the resolution string TradeLocker expects, and the unit its lookback is counted
#: in. THE MAP IS EXPLICIT AND UNKNOWN CHARTS ARE REFUSED: guessing a resolution string would
#: fetch SOMETHING for every sleeve, and a family that branches on `index.hour` computes a
#: real-looking signal off the wrong bars rather than raising. On an all-asia book that is the
#: one error that would look like a strategy.
_RESOLUTION = {
    "M1": ("1m", "m"), "M5": ("5m", "m"), "M15": ("15m", "m"), "M30": ("30m", "m"),
    "H1": ("1H", "H"), "H4": ("4H", "H"), "D1": ("1D", "D"),
}


#: Why the last reconstruction refused, per sleeve tag -- so NO_INPUTS carries its reason instead
#: of joining NO_SIGNAL as another silent outcome.
_LAST_INPUT_REFUSAL: dict = {}

#: Resolved venue inputs for one PASS only. Cleared at the top of every run -- see `_call_params`.
_INPUT_CACHE: dict = {}


def _call_params(s: dict, symbol: str = "", bars: object = None) -> dict | None:
    """The parameters a certified E8 cell is actually called with.

    TWENTY SLEEVES REPORTED NO_SIGNAL EVERY PASS AND THIS IS WHY (measured 2026-09-14). The E8
    guard was green -- `may_open: true`, equity 100,000, day_pnl 0, 2,500 to the daily floor --
    the lane was armed, twenty sleeves were considered, and `n_sent` was 0 with every row reading
    NO_SIGNAL. The signals were never computed with the cell's parameters.

    TWO FAULTS, EITHER ONE FATAL ALONE.

    1. THE PARAMS ARE NESTED. `e8_book` writes the docket row's own shape through:

           "params": {"condition": null,
                      "params": {"feature": "dd_24", "band": [0.75, 0.9],
                                 "horizon": 6, "side": -1}}

       The executor spread the OUTER dict, so `family_discovered` would have been offered
       `condition=` and `params=` -- neither of which it takes -- instead of feature/band/
       horizon/side.

    2. THE FILTER KEPT ONLY SCALARS. `isinstance(v, (int, float, str, bool))` drops `condition`
       (None) and the inner dict, leaving `{}` -- so the call fell through to the unparameterised
       `func(closed)` branch and produced nothing, silently. And the filter would have been fatal
       even with the nesting fixed: `band` is a LIST, and a `discovered` cell without its band
       selects no rows at all.

    `strip_identity_keys` is the desk's own rule for which params name an INPUT rather than
    parameterise a family, and `_family_call_params` in the gateway uses it for the same purpose.
    Using it here keeps one reconstruction rather than a fourth copy to drift -- the drift this
    desk keeps paying for.
    """
    raw = s.get("params") or {}
    if not isinstance(raw, dict):
        return {}
    # UNWRAP ONE LEVEL when the row carries the docket's {condition, params} envelope. Checked by
    # SHAPE, not by family name: a future producer writing flat params must keep working.
    inner = raw.get("params")
    if isinstance(inner, dict):
        raw = inner
    # AND `condition` IS AN ENVELOPE KEY EVEN WHEN THE ENVELOPE HAS NO `params` HALF.
    # Measured 2026-09-15 against the live E8 account: four sleeves returned
    # `TypeError: family_session_range_breakout() got an unexpected keyword argument 'condition'`
    # because `e8_book` writes `"params": {"condition": null}` -- the envelope with its second
    # half absent. The unwrap above only fires when `params` is a dict, so on that shape `raw`
    # keeps `condition` and it is spread into the family call as a keyword no family takes.
    #
    # `condition` names the REGIME a cell was certified in; it is docket metadata and never a
    # family parameter, so it is dropped on every shape rather than only on the nested one. This
    # is the same {condition, params} envelope fault the desk has now found in five producers,
    # and the reason it keeps recurring is that each fix handled the shape in front of it.
    raw = {k: v for k, v in raw.items() if k != "condition"}
    # AND `side` ARRIVES AS A WORD WHERE THE FAMILIES TAKE A SIGN. The qquant certificates carry
    # `"side": "SHORT"` because that is how the hunt named it; every family in `families.py`
    # compares `side` numerically, so the string reaches a `>` and raises
    # `'>' not supported between instances of 'str' and 'int'` -- which the caller records as
    # SIGNAL_ERROR and a reader mistakes for a broken strategy rather than a broken word.
    #
    # Coerced here rather than in the families: the families' contract is already numeric and
    # correct, and the desk's own convention is +1 long / -1 short (see `engine.Signal.side`).
    # An unrecognised word is left ALONE so it surfaces as an error instead of silently becoming
    # a long position -- guessing a direction is the one wrong answer available here.
    _side = raw.get("side")
    if isinstance(_side, str):
        _sign = {"SHORT": -1, "SELL": -1, "S": -1, "LONG": 1, "BUY": 1, "L": 1}.get(_side.upper())
        if _sign is not None:
            raw = dict(raw, side=_sign)
    try:
        from mt5desk.family_inputs import resolve, strip_identity_keys
    except Exception:
        return {k: v for k, v in raw.items()
                if k not in ("timeframe", "peer_symbol", "factor_symbols",
                             "input_symbol", "input_source")}
    call = dict(strip_identity_keys("", raw))
    if bars is None:
        return call
    # AND THE NAMED INPUTS MUST BE LOADED, NOT PASSED AS NAMES. Five of the twenty book sleeves
    # produced ZERO signals even with their parameters restored, because a `discovered` cell whose
    # feature is `ext_resid_EURGBP_z` needs that residual SERIES, and stripping identity keys only
    # removes the name -- it does not fetch the thing. `family_inputs.resolve` is the same
    # reconstruction `build_cell` and the gateway both use; a fourth copy here is the drift this
    # desk keeps paying for.
    #
    # FAIL CLOSED: a cell whose inputs cannot be rebuilt returns None and the caller refuses it by
    # NAME. Returning `call` regardless would run the family with a feature it cannot resolve and
    # report the resulting silence as "no signal" -- exactly the defect being repaired.
    # ONE FETCH PER DISTINCT INPUT SET, PER PASS. `resolve` loads peer, factor and macro series
    # from the venue and sleeves share drivers, so called blind it refetches identical series.
    #
    # THIS IS NOT WHY THE PASS IS SLOW, AND THE FIRST VERSION OF THIS COMMENT SAID IT WAS.
    # Measured afterwards: `_call_params` costs 0.0s per sleeve, frame fetch 1.7s and signal
    # computation 1.6s -- about 1.1 minutes of work for twenty sleeves against a pass that takes
    # fifteen. Roughly fourteen minutes are somewhere none of that touches, and caching this
    # changed the wall clock not at all. The cache is kept because avoiding a duplicate venue
    # fetch is correct on its own terms, not because it bought any time.
    #
    # The key is the symbol, the family and the exact params: `bars` is derived from the symbol
    # and is one frame per symbol within a pass, so two sleeves agreeing on all three necessarily
    # resolve to the same inputs.
    #
    # CLEARED AT THE START OF EVERY PASS (`_INPUT_CACHE.clear()` in the run loop), never across
    # them: these are live series, and a cache that outlived its bar would feed one hour's
    # decision from the previous hour's data -- a silent staleness far worse than the refetch.
    _key = (str(symbol), str(s.get("family") or ""),
            json.dumps(raw, sort_keys=True, default=str))
    if _key in _INPUT_CACHE:
        extra, why = _INPUT_CACHE[_key]
        if extra is None:
            _LAST_INPUT_REFUSAL[str(s.get("tag") or symbol)] = str(why)[:160]
            return None
        call.update(extra)
        return call
    try:
        extra, why = resolve(str(symbol), str(s.get("family") or ""), raw, bars)
    except Exception as exc:
        _LAST_INPUT_REFUSAL[str(s.get("tag") or symbol)] = (
            f"input reconstruction raised ({type(exc).__name__}: {str(exc)[:80]})")
        return None
    _INPUT_CACHE[_key] = (extra, why)
    if extra is None:
        _LAST_INPUT_REFUSAL[str(s.get("tag") or symbol)] = str(why)[:160]
        return None
    call.update(extra)
    return call


def _frame(api: Any, instrument_id: int, timeframe: str = "H1") -> Any:
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
    # THE SLEEVE'S OWN CHART, NOT A CONSTANT (fixed 2026-09-14). This asked for "1H" for every
    # sleeve. While H1 was the only chart the desk collected that was merely redundant; the
    # moment an M15 certificate exists it becomes a silent defect -- the executor would evaluate
    # an M15 mechanism on hourly bars, produce a plausible signal, and place a real order on it.
    tf = str(timeframe or "H1").upper()
    res = _RESOLUTION.get(tf)
    if res is None:
        return None
    resolution, unit = res
    try:
        df = api.get_price_history(instrument_id, resolution=resolution,
                                   lookback_period=f"{LOOKBACK_BARS}{unit}")
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
#: The MT5 desk's own live record for the same mechanism on the same symbol -- the roster with
#: its FADE flags and the live ledger with real R. The E8 book is built from certificates alone,
#: so a mechanism the MT5 lane has measured 0-for-9 live kept full risk here (measured 2026-09-16:
#: the `discovered` EURCHF/AUDCAD/AUDNZD sleeves, 22% wins on MT5, were E8's entire order flow).
MT5_SLEEVES = DESK / "data" / "sleeves.json"
MT5_LEDGER = DESK / "data" / "live_ledger.jsonl"
TWIN_TRAIL_DAYS = 45
TWIN_FADE_N = 5
TWIN_FADE_R = 0.25
TWIN_FADE_FACTOR = 0.5


def twin_fade(symbol: str, family: str, *, now: datetime | None = None) -> tuple[float, str]:
    """0.5 when the MT5 twins of this (symbol, family) are faded or measured doing bad, else 1.0.

    Two readings, either one fades: (1) any MT5 roster row for the same symbol and family carries
    `decay_faded` (the decay monitor's own verdict on real R); (2) the pooled trailing live record
    of those twins has no win in its first TWIN_FADE_N trades or loses >= TWIN_FADE_R per trade.
    Two-sided: the multiplier returns to 1.0 the moment the twins are unfaded and the record
    turns. Unreadable files read as 1.0 with the reason -- absence is not a verdict.
    """
    stem = f"{str(symbol).lower()}_{str(family).lower()}"
    if not stem.strip("_"):
        return 1.0, "twin fade 1.00: no symbol/family"
    faded: list[str] = []
    try:
        doc = json.loads(MT5_SLEEVES.read_text("utf-8"))
        rows = doc.get("sleeves") if isinstance(doc, dict) else doc
        rows = list(rows.values()) if isinstance(rows, dict) else (rows or [])
        for r in rows:
            if isinstance(r, dict) and str(r.get("name", "")).lower().startswith(stem)                     and r.get("decay_faded"):
                faded.append(str(r.get("name"))[:30])
    except (OSError, ValueError):
        pass
    rs: list[float] = []
    try:
        cutoff = (now or datetime.now(tz=UTC)) - timedelta(days=TWIN_TRAIL_DAYS)
        for ln in MT5_LEDGER.read_text("utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not str(r.get("sleeve", "")).lower().startswith(stem):
                continue
            if not isinstance(r.get("r_multiple"), (int, float)):
                continue
            try:
                ts = datetime.fromisoformat(str(r.get("time", "")).replace("Z", "+00:00"))
                ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
            except ValueError:
                ts = None
            if ts is None or ts >= cutoff:
                rs.append(float(r["r_multiple"]))
    except OSError:
        pass
    n, wins = len(rs), sum(1 for x in rs if x > 0)
    exp = (sum(rs) / n) if n else 0.0
    if faded:
        return TWIN_FADE_FACTOR, (f"twin fade {TWIN_FADE_FACTOR:.2f}: MT5 twin(s) faded by the decay "
                                  f"monitor ({', '.join(faded[:3])}); pooled live n={n} exp={exp:+.2f}R")
    if n >= TWIN_FADE_N and (wins == 0 or exp <= -TWIN_FADE_R):
        return TWIN_FADE_FACTOR, (f"twin fade {TWIN_FADE_FACTOR:.2f}: MT5 twins {wins}-for-{n} live, "
                                  f"exp={exp:+.2f}R (bar n>={TWIN_FADE_N}, no wins or exp<=-{TWIN_FADE_R}R)")
    return 1.0, f"twin fade 1.00: MT5 twins n={n} wins={wins} exp={exp:+.2f}R"


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
        # FLOOR, never round: rounding up oversizes. Then QUANTISE TO THE STEP'S OWN PRECISION.
        #
        # `int(lot / step) * step` is exact in decimal and not in binary: 114 * 0.01 is
        # 1.1400000000000001, which the venue rejects outright with "Order cannot be created
        # since order amount is not multiple of lot step". Measured 2026-09-15: two EURCHF
        # orders refused for exactly this, at 1.1400000000000001 and 0.9500000000000001, while
        # their USDCAD siblings on the same pass went through because their arithmetic happened
        # to land clean. A sizing bug that only bites some lots is worse than one that bites all
        # of them, because the lane looks healthy.
        from decimal import Decimal
        d_step = Decimal(str(step))
        lot = float((Decimal(str(lot)) / d_step).to_integral_value(rounding="ROUND_FLOOR")
                    * d_step)
    return float(max(lot, vmin)), basis + f"; risk ${risk_usd:.2f} -> {max(lot, vmin):g} lot"


# ------------------------------------------------------------------ the pass
def _quantise(lot: float, venue: Any, symbol: str) -> float:
    """Floor `lot` to the venue's lot step, exactly, and never below its minimum.

    Shares `lot_for_risk`'s rule because a lot that is legal when sized and illegal after a
    multiplier is the same rejection in a different place: the venue refuses anything that is not
    an exact multiple of its step, and binary float arithmetic produces 1.1400000000000001 from
    114 * 0.01.
    """
    from decimal import Decimal
    try:
        d = venue.details(symbol)
        vmin = float(venue.min_lot(symbol))
    except Exception:                                               # noqa: BLE001
        return float(lot)
    step = None
    for k in ("lotStep", "volumeStep", "step"):
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 0:
            step = float(v)
            break
    if not step:
        return float(max(lot, vmin))
    ds = Decimal(str(step))
    q = float((Decimal(str(lot)) / ds).to_integral_value(rounding="ROUND_FLOOR") * ds)
    return float(max(q, vmin))


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
    # THE DEDUPE KEY IS THE INSTRUMENT AND SIDE, BECAUSE THIS VENUE HAS NO COMMENTS.
    #
    # MEASURED 2026-09-15, and it cost the account 0.85% in half an hour. This read
    # `p.get("comment")` and kept the tags that start with TAG -- the MT5 idiom, where the order
    # comment IS the sleeve tag. TradeLocker returns positions as
    # {id, tradableInstrumentId, routeId, side, qty, avgPrice}: THERE IS NO COMMENT FIELD. So
    # `open_tags` was unconditionally empty, `ALREADY_OPEN` could never fire, and every sleeve
    # re-entered on every pass. At a 15-minute cadence that is the same trade every quarter hour:
    # EURCHF sell at 13:21, 13:37, 13:52 and USDCAD sell alongside it, 23 orders in total, until
    # the daily guard stood the account down at -846.
    #
    # A dedupe key that the venue does not return is not a weak guard, it is no guard, and it
    # fails OPEN -- the one direction a position guard must never fail. Matching on what the
    # venue DOES return cannot silently become a no-op the same way.
    open_keys: set[tuple[int, str]] = set()
    for p in venue.positions():
        iid = p.get("tradableInstrumentId") or p.get("instrumentId") or p.get("id")
        sd = str(p.get("side") or p.get("Side") or "").lower()
        if iid is not None and sd:
            open_keys.add((int(iid), sd))

    # THE LEG BOOK, IN SYMBOLS. `leg_balance` decomposes currency pairs, so the venue's instrument
    # ids have to be mapped back to the names the decomposition understands; `_by_key` is the
    # catalogue the venue itself reported at connect time, inverted here rather than guessed.
    _iid_to_sym = {int(v): k for k, v in getattr(venue, "_by_key", {}).items()}

    class _Pos:
        """The shape `leg_balance.book_exposures` reads: symbol, volume, MT5-style type."""
        __slots__ = ("symbol", "volume", "type")

        def __init__(self, symbol: str, volume: float, typ: int) -> None:
            self.symbol, self.volume, self.type = symbol, volume, typ

    _leg_positions = []
    for p in venue.positions():
        iid = p.get("tradableInstrumentId") or p.get("instrumentId") or p.get("id")
        nm = _iid_to_sym.get(int(iid)) if iid is not None else None
        if not nm:
            continue
        qty = float(p.get("qty") or p.get("quantity") or 0.0)
        _leg_positions.append(_Pos(nm, abs(qty),
                                   0 if str(p.get("side") or "").lower() == "buy" else 1))
    _pending_legs: dict[str, float] = {}

    from mt5desk.families import get_family_func

    sent = considered = 0
    # A CACHE THAT OUTLIVES ITS BAR IS WORSE THAN THE REFETCH IT SAVES. Cleared here so every pass
    # resolves its inputs from this hour's data and never from the last one's.
    _INPUT_CACHE.clear()
    _LAST_INPUT_REFUSAL.clear()
    for s in book.get("sleeves", []):
        sym, fam = s["symbol"], s["family"]
        tag = f"{TAG}{fam[:6]}{sym}"[:31]
        row: dict[str, Any] = {"symbol": sym, "family": fam, "tag": tag}
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

        # ONE POSITION PER INSTRUMENT. Checked here rather than at the top of the loop because
        # this venue's key is the instrument id, which is only known once it resolves. A prop
        # account with a hard daily floor has no use for a second helping of a trade it already
        # holds: the second entry doubles the risk of the first without adding a bet.
        if any(k[0] == int(iid) for k in open_keys):
            row["status"] = "ALREADY_OPEN"
            row["why"] = f"a position is already open on {sym} (instrument {iid})"
            doc["sleeves"].append(row)
            continue
        # The chart travels in the sleeve's params exactly as it does through the gauntlet's
        # `timeframe_of`, and H1 is the default for every certificate minted before the desk
        # collected anything else.
        _tf = str((s.get("params") or {}).get("timeframe") or "H1").upper()
        row["timeframe"] = _tf
        frame = _frame(venue._raw_api, iid, _tf)
        if frame is None or len(frame) < 60:
            row["status"] = "NO_BARS"
            row["why"] = (f"history unavailable or too short on {_tf} "
                          f"({0 if frame is None else len(frame)})")
            doc["sleeves"].append(row)
            continue
        closed = _last_closed(frame)
        params = _call_params(s, s.get("symbol") or "", closed)
        if params is None:
            row["status"] = "NO_INPUTS"
            row["why"] = _LAST_INPUT_REFUSAL.get(
                str(s.get("tag") or s.get("symbol") or ""), "inputs could not be rebuilt")
            doc["sleeves"].append(row)
            continue
        try:
            # THE FAMILY IS GIVEN THE FRAME *INCLUDING* THE FORMING BAR, AND JUDGED ON THE LAST
            # CLOSED ONE. Every family emits over `for i in range(n, len(d) - 1)`: the `- 1` is a
            # backtest convention, because the engine fills at the open of bar i+1, so the family
            # CANNOT emit on the final bar of whatever frame it is handed. Passing `closed` and
            # then keeping only signals whose time equals `closed.index[-1]` asks for the one bar
            # it is structurally incapable of producing -- the filter matches nothing, on every
            # sleeve, on every pass, forever. That is the same defect the MT5 gateway carried
            # (see `family_signal_step`'s `signal_bars`), and it is why this lane reported
            # NO_SIGNAL for all 18 sleeves while the families were emitting normally.
            #
            # The appended bar extends the RANGE and is never read as a value: these families
            # index i and i-1, never i+1. Live, the fill that the backtest's bar i+1 stands for
            # is the market order this pass is about to send.
            signals = func(frame, **params) if params else func(frame)
        except Exception as exc:
            row["status"] = "SIGNAL_ERROR"
            row["why"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            doc["sleeves"].append(row)
            continue
        considered += 1
        last_bar = closed.index[-1]
        fresh = [g for g in (signals or []) if getattr(g, "time", None) == last_bar]
        if not fresh:
            # NO_SIGNAL MEANT TWO OPPOSITE THINGS AND NAMED NEITHER: "this family produced forty
            # signals, none on the bar I am judging" and "this family produced nothing at all".
            # That conflation is what hid a book-wide outage for days -- every sleeve was called
            # with empty params, returned an empty list, and reported NO_SIGNAL exactly as a quiet
            # market does. The counts below are what tell the two apart on the NEXT pass rather
            # than after another investigation.
            row["status"] = "NO_SIGNAL"
            row["last_bar"] = str(last_bar)
            row["n_signals_in_window"] = len(signals or [])
            _times = [getattr(g, "time", None) for g in (signals or [])]
            _times = [t for t in _times if t is not None]
            row["last_signal_seen"] = str(max(_times)) if _times else None
            # THE BAR THE SIGNAL CARRIES vs THE BAR BEING JUDGED, as the equality actually sees
            # them. If a feed or a dtype ever makes these differ while looking identical in a log,
            # this is the line that shows it.
            row["bar_repr"] = f"{last_bar!r}"
            row["last_signal_repr"] = f"{max(_times)!r}" if _times else None
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
        # THE BRACKET IS LAID FROM THIS ENTRY, NOT FROM THE SIGNAL BAR'S CLOSE (2026-09-16): the
        # MT5 lane's `family_bracket`, same rule for the same reason (L0352). The family's levels
        # sit around its bar's close; this pass reaches the sleeve minutes later at a quote that
        # has moved, and an absolute stop can then be a pip from the fill while `lot_for_risk`
        # inflates the size against that pip. Past a quarter of the certified stop the certified
        # DISTANCES are re-laid from the entry; a signal the market has already stopped or paid
        # is stale and not opened. Unmeasurable keeps the levels as they are.
        try:
            from mt5desk.decision_core import family_bracket, signal_with_levels
            _close = float(closed["close"].iloc[-1])
            _sgn = 1 if side == "buy" else -1
            _e, _stop, _target, _d, _note, _drift, _verdict = family_bracket(
                g, _sgn, float(bid), float(ask), _close)
            row["entry_drift"], row["entry_drift_note"] = _drift, _note
            if _verdict == "stale":
                row["status"] = "STALE_SIGNAL"
                row["why"] = _note
                doc["sleeves"].append(row)
                _record(row, now, armed)
                continue
            if _verdict == "re_anchored":
                g = signal_with_levels(g, _stop, _target)
        except Exception as exc:
            row["entry_drift_note"] = f"UNMEASURED ({type(exc).__name__}: {exc})"
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
        # THE MT5 LANE'S LIVE VERDICT ON THE SAME MECHANISM, applied here too (2026-09-16).
        _fm, _fw = twin_fade(sym, str(fam or ""), now=now)
        if _fm != 1.0:
            lot = _quantise(lot * _fm, venue, sym)
        row["fade_mult"], row["fade_why"] = float(_fm), _fw
        row.update({"side": side, "entry_ref": entry, "stop": float(g.stop),
                    "target": float(g.target), "stop_dist": stop_dist,
                    "lot": lot, "sizing_basis": basis, "bar": str(last_bar)})
        if not (lot > 0):
            row["status"] = "UNSIZEABLE"
            doc["sleeves"].append(row)
            continue
        # CURRENCY-LEG BALANCE, the same two-sided rule the MT5 gateway applies, and it matters
        # MORE here. This account has a hard 8% drawdown and a voluntary 0.75% daily stand-down:
        # a book that is six positions deep on one currency does not lose six small amounts, it
        # loses one large one and ends the trading day. On 2026-09-15 the sent orders were EURCHF
        # short and USDCAD short together -- both short the non-USD leg against a dollar move.
        #
        # It damps an order piling onto a held leg and BOOSTS one opening a leg the book does not
        # hold, so the risk budget is spent on more independent bets rather than reduced.
        # `pending` carries what this pass has already decided to send, because every sleeve here
        # is judged before any of them is placed.
        try:
            from mt5desk import leg_balance
            _lm, _lw = leg_balance.multiplier(sym, 1 if side == "buy" else -1,
                                              _leg_positions, pending=_pending_legs)
            # The same macro lean the MT5 lane applies -- a prop account with a hard drawdown
            # has the most to gain from not fighting the currency regime.
            try:
                from mt5desk import macro_view
                _mm, _mw = macro_view.multiplier(sym, 1 if side == "buy" else -1,
                                                 family=str(fam or ""),
                                                 ttl_bars=getattr(g, "ttl_bars", None))
            except Exception as _exc:                          # noqa: BLE001
                _mm, _mw = 1.0, f"macro UNMEASURED ({type(_exc).__name__})"
            lot = _quantise(lot * _lm * _mm, venue, sym)
            row["leg_mult"], row["leg_why"] = float(_lm), _lw
            row["macro_mult"], row["macro_why"] = float(_mm), _mw
        except Exception as exc:                                    # noqa: BLE001
            # UNMEASURED IS 1.0. A decomposition that cannot be trusted must never become a
            # silent reason to trade smaller.
            row["leg_mult"], row["leg_why"] = 1.0, f"UNMEASURED ({type(exc).__name__}: {exc})"
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
                _pending_legs[sym] = (_pending_legs.get(sym, 0.0)
                                      + (1.0 if side == "buy" else -1.0) * float(lot))
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
