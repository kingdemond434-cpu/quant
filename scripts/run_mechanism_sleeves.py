#!/usr/bin/env python3
"""LIVE MECHANISM SLEEVES -- generator signals become target weights, under a DECLARED EXCEPTION.

**THIS RUNS UNDER A SUSPENSION OF THE TWO-STAGE LAW, AT THE PRINCIPAL'S EXPLICIT DIRECTION.**
L1.6 says the backtest gauntlet has ZERO promotion authority and capital comes only from
pre-registered FORWARD evidence. The principal has directed that these sleeves go live now and be
judged on realised P&L: "if they earn they stay n considered validated". That decision is theirs to
make and it is recorded in `docs/research/LIVE_EXCEPTION_LEDGER.json` rather than absorbed silently
into the code -- an exception nobody wrote down becomes the rule nobody remembers agreeing to.

**WHAT THE EXCEPTION COSTS, STATED ONCE AND NOT REPEATED AT EVERY LINE.** Live P&L over weeks is
very weak evidence: at these Sharpes the standard error of a one-month return swamps the mean, so a
sleeve that "earned" over 30 days and one that did not are, statistically, the same observation.
That is not an argument against running it -- forward evidence has to start somewhere and paper
clocks are strictly slower -- it is the reason the KILL RULE below is fixed BEFORE the first fill.

**THE KILL RULE IS PRE-REGISTERED HERE, TODAY, AND IT IS THE WHOLE POINT.** "If they earn they
stay" decided after seeing the returns is not a rule, it is a garden of forking paths with money in
it: whichever sleeve looks best gets kept for a reason invented afterwards. Fixed now:

    * the book's TOTAL envelope is fixed at `EQUAL_CLIP_FRAC * len(SLEEVES)` and no sleeve is ever
      sized up for performing well -- that is progression, and progression is what III.15 forbids.
      The envelope is divided by INVERSE VOLATILITY (see `_sleeve_vol`), which reads a second
      moment and never a return: two sleeves with the same volatility get the same clip whether one
      of them tripled and the other halved;
    * a sleeve is RETIRED when its realised return since inception is below KILL_DRAWDOWN, or
      when REVIEW_DAYS have elapsed and its realised return is negative;
    * a sleeve that survives the review is NOT thereby validated -- it has bought the right to
      keep its clip while its forward clock keeps accruing. Live P&L starts the evidence; it does
      not finish it.

**WHAT IS ACTUALLY NEW HERE, WHICH IS LESS THAN IT LOOKS.** Of the four mechanisms proposed, one
(`taker_flow`) HAS NO GENERATOR IN THIS REPO at all, and two are already live inside the
discretionary book -- informed_order_flow via H5_cvd_divergence, liquidity_provision_immediacy via
H7/H11. Deploying all four as "four uncorrelated strategies" would have double-counted two of them
and shipped one that does not exist. The genuinely new pair is below, and two is the honest number.

**IT PLACES NOTHING.** It writes target weights. `run_margin_executor` places, the risk kernel
bounds, the gross cap binds, the ruin rails stop everything regardless of what this concluded.

    python scripts/run_mechanism_sleeves.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.execution.spot_order_path import retarget

_OUT = Path("data/mechanism_sleeve_targets.json")
_STATE = Path("data/mechanism_sleeve_state.json")
_LEDGER = Path("docs/research/LIVE_EXCEPTION_LEDGER.json")
_LAKE = "data/lake"

#: The two mechanisms this sleeve set deploys, each named by its CENSUS class rather than by the
#: generator's search-budget family -- the census is the authority on what mechanism a thing tests,
#: and `funding_stress_reversal` is filed under LIQUIDITY while testing positioning/crowding.
SLEEVES: tuple[tuple[str, str, str, dict[str, float]], ...] = (
    ("positioning_crowding_unwind", "funding_stress_reversal", "fade crowded perp leverage: "
     "positive funding means longs are paying to stay long, and that inventory unwinds on the "
     "venue's schedule rather than the holder's", {"window": 30, "z_entry": 1.5}),
    ("relative_value_convergence", "intermarket_difference", "trade the ATR-normalised residual "
     "against a reference, so the shared market factor both legs carry is differenced away rather "
     "than traded twice", {"lookback": 24, "threshold": 0.25}),
    # ADDED 2026-08-15 at the principal's direction, under the same standing exception. The
    # census files it as price_continuation (orthogonality 0.03), so it joins CORRELATED_CORE and
    # adds close to nothing to k_eff -- that is the honest expectation and it is recorded here
    # rather than discovered from the correlation tracker in a month.
    ("price_continuation", "hawkes_vol_expansion", "volatility is SELF-EXCITING: one large move "
     "causes the next through margin calls, maker withdrawal and stop cascades, and a decaying "
     "sum of past events sees that clustering where a rolling window cannot",
     {"beta": 0.2, "k": 2.0, "lookback": 20}),
    # THE HIGHEST-ORTHOGONALITY GENERATOR IN THE REPO (0.70), built, collector wired, and NOT
    # DEPLOYED until now. The desk holds NOTHING in treasury_cost_base_liquidation, so unlike
    # hawkes this is a genuinely new family rather than a fifth name in correlated_core.
    #
    # THE PAYER IS NAMED AND IT IS NOT A PRICE PATTERN: a miner carries a FIAT cost base -- power,
    # hosting, leased rigs, debt service -- against coin-denominated revenue. Those obligations do
    # not reschedule for a drawdown, so coin is sold on the operator's calendar and hardest when
    # price is weakest. Difficulty falling is the LAGGING, mechanical admission that the marginal
    # producer already switched off and sold; nothing here forecasts miner behaviour.
    ("treasury_cost_base_liquidation", "producer_margin_stress", "a miner's fiat obligations do "
     "not reschedule for a drawdown, so coin is sold on the operator's calendar rather than the "
     "market's -- and difficulty adjusting DOWN is the mechanical confirmation the marginal "
     "producer has already exited", {"window": 90, "z_entry": 1.0}),
    # THE DESK'S FIRST TRUE CARRY TEST. Family.CARRY held exactly one generator since inception --
    # `drift_proxy`, which is momentum(200) on OHLC with no funding, swap or basis in its inputs,
    # and which the census correctly files as price_continuation. The funding data was in the lake
    # the whole time and exactly one generator read it: the FADE. This supplies the spot leg and
    # collects what the levered long pays for it.
    ("derivative_carry_basis", "funding_carry", "the levered long pays funding to hold his "
     "position and someone must supply the other side -- this collects that payment rather than "
     "forecasting the price it is paid on", {"window": 30, "z_entry": 0.5}),
)

#: Fraction of the book each sleeve carries ON AVERAGE. Sizing by backtest SHARPE would let the
#: gauntlet allocate capital, which is precisely the authority the two-stage law withholds and
#: which this exception did NOT suspend -- the principal suspended the requirement for forward
#: evidence before going live, not the rule against letting a backtest decide position size. The
#: TOTAL book fraction is still `EQUAL_CLIP_FRAC * len(SLEEVES)` and is unchanged by the split
#: below; only how that fixed envelope is divided moves.
EQUAL_CLIP_FRAC = 0.05

#: Days of history the per-sleeve volatility is measured over. Long enough that the estimate is not
#: one week's weather, short enough to track a regime.
RISK_PARITY_WINDOW = 60

#: How far a sleeve's clip may travel from the equal one, in either direction. A volatility
#: estimate near zero -- which a generator that is flat most of the time will produce -- inverts to
#: an unbounded weight, and the sleeve holding the whole book would be the one that trades least.
#: The cap is the entire reason this is safe to run unattended.
MAX_CLIP_MULTIPLE = 3.0

#: Realised return since inception at which a sleeve is retired, no discussion. Fixed before the
#: first fill so it cannot be renegotiated by the sleeve that breaches it.
KILL_DRAWDOWN = -0.15

#: Days after which a non-negative realised return is required to keep the clip.
REVIEW_DAYS = 30

#: CANDIDATES, not the universe. What actually trades is derived every run by
#: `libs.research.sleeve_universe.select` from the capital present, the history in the lake and a
#: liquidity ranking -- so funding is the only lever needed to widen the book, and a symbol whose
#: leg would fall under the venue minimum is excluded BEFORE it is published rather than refused
#: after. The first six are the momentum book's set and stay at the front of the candidate list:
#: a new mechanism tested on a different universe confounds the mechanism with the universe.
SYMBOLS: tuple[str, ...] = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "ADAUSDT",
    # WIDENING CANDIDATES. Liquid, USDC-tradeable on Binance spot, and each one is only a
    # CANDIDATE: it enters the book if the lake carries enough history for it and capital reaches
    # its leg, and is named in `rejected` with a reason when it does not.
    "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT",
    "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "FILUSDT", "INJUSDT", "SUIUSDT", "TIAUSDT", "SEIUSDT", "AAVEUSDT",
    # EXTENDED 2026-08-16. At $1,000 and 3x the previous 24-name list BOUND BEFORE CAPITAL DID,
    # which put the ceiling back in a constant -- the exact defect deriving the universe was meant
    # to remove. The list must always be longer than money can reach, so that `binding_constraint`
    # reads CAPITAL and funding stays the only lever. Ordering is irrelevant: `select` ranks by
    # measured liquidity and truncates, so a name that is thin or missing from the lake simply
    # never gets picked rather than diluting anything.
    "ETCUSDT", "XLMUSDT", "ALGOUSDT", "VETUSDT", "HBARUSDT", "ICPUSDT",
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GRTUSDT", "CRVUSDT",
    "MKRUSDT", "LDOUSDT", "RUNEUSDT", "THETAUSDT", "EOSUSDT", "CAKEUSDT",
    "GALAUSDT", "CHZUSDT", "ENSUSDT", "SNXUSDT", "COMPUSDT", "DYDXUSDT",
)

#: The venue floor a single leg must clear. Binance publishes per-symbol minimums; 5.0 is
#: the conservative floor the order path already uses when a symbol declares none.
MIN_NOTIONAL_USD = 5.0

#: Equity assumed when the venue cannot be read. Only ever SHRINKS the universe: an unreadable
#: balance must not widen the book, because the failure mode is publishing legs that get refused.
_FALLBACK_EQUITY = 0.0


def _exception_recorded() -> tuple[bool, str]:
    """Is the principal's suspension on record? NO LEDGER, NO SLEEVES.

    Fail-closed on purpose. This module exists only because a standing law was suspended, and a
    suspension that is not written down is indistinguishable from the law never having applied --
    which is how an exception becomes the default without anyone deciding it should.
    """
    try:
        doc = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return False, (f"{_LEDGER} unreadable ({type(exc).__name__}) -- these sleeves run under a "
                       "SUSPENSION of the two-stage law, and an unrecorded suspension is not one. "
                       "Refusing to publish targets")
    rows = doc.get("exceptions") if isinstance(doc, dict) else None
    for r in rows or []:
        if isinstance(r, dict) and r.get("id") == "live-mechanism-sleeves" and r.get("active"):
            return True, (f"exception on record: granted {r.get('granted')} by "
                          f"{r.get('granted_by')} -- {str(r.get('scope', ''))[:120]}")
    return False, (f"{_LEDGER} carries no ACTIVE 'live-mechanism-sleeves' exception. The law it "
                   "suspends is L1.6; nothing here may run without the record")


def _series(symbols: tuple[str, ...]) -> dict[str, Any]:
    """MarketSeries per symbol from the lake, funding attached where the lake holds it."""
    import dataclasses

    import numpy as _np
    from scripts.collect_perp_funding import load as _load_funding

    from libs.autodiscovery.crypto_adapter import _read_frames, lake_provider
    from libs.data.timeframe import Timeframe

    provider = lake_provider(list(symbols), lake_root=_LAKE)
    # THE FRAMES CARRY THE DATE AXIS AND `MarketSeries` DOES NOT. lake_provider builds the series
    # from these same frames and drops the index, so reading them here is the only way to align a
    # second series to the first. The first attempt used `getattr(ser, "dates", None)`, which is
    # always None -- a dead branch that would have left funding permanently unattached while
    # looking like it handled the case.
    try:
        frames = _read_frames(list(symbols), Timeframe.D1, _LAKE)
    except Exception:
        frames = {}

    out: dict[str, Any] = {}
    for s in symbols:
        try:
            ser = provider(s)
        except Exception:
            ser = None
        if ser is None:
            continue
        # FUNDING FROM THE SIDECAR WHEN THE LAKE DOES NOT CARRY IT. `data/lake` holds OHLCV, so
        # MarketSeries.funding was None on every symbol and `funding_stress_reversal` degraded to
        # zeros -- honestly, and to no effect: a live sleeve that could never produce a signal.
        #
        # ALIGNED BY DATE, NEVER ZIPPED. The two series come from different fetches, and a
        # positional join offsets funding from price the moment either has a gap -- which reads as
        # a signal and is a join bug. A date with no funding row stays 0.0, which for THIS
        # generator is the neutral value rather than an invented one.
        if getattr(ser, "funding", None) is None:
            fmap = _load_funding(s)
            df = frames.get(s)
            if fmap and df is not None and len(df) == len(ser.close):
                vals = [fmap.get(str(d)[:10]) for d in df.index]
                if any(v is not None for v in vals):
                    ser = dataclasses.replace(ser, funding=_np.array(
                        [0.0 if v is None else float(v) for v in vals], dtype="float64"))
        out[s] = ser
    return out


def _positions(subtype: str, series: Any, params: dict[str, float]) -> np.ndarray | None:
    from libs.autodiscovery.generators import GENERATORS

    for g in GENERATORS:
        if g.subtype == subtype:
            return np.asarray(g.fn(series, params), dtype="float64")
    return None


def _sleeve_vol(positions: dict[str, np.ndarray], frames: dict[str, Any],
                window: int = RISK_PARITY_WINDOW) -> float | None:
    """Realised daily volatility of THIS SLEEVE'S OWN position series. None when unmeasurable.

    **THE SECOND MOMENT ONLY, AND THAT DISTINCTION IS THE WHOLE LEGAL ARGUMENT.** L1.6 withholds
    from the backtest the authority to allocate capital, and this exception did not restore it.
    What the backtest may not supply is the MEAN -- the edge claim, the contested quantity, the
    thing forward evidence exists to establish. The VARIANCE is not an edge claim: it is a risk
    measurement, it is estimable in weeks rather than years, and `leverage_policy.realised_vol`
    already sizes the entire book from exactly this quantity computed exactly this way. Using sigma
    from history here is the desk's existing practice; using mu would be the violation.

    **AND IT IS NOT ASSUMPTION-FREE -- IT IS A BETTER ASSUMPTION.** Inverse-volatility weighting
    implicitly assumes EQUAL SHARPE across sleeves. Equal-dollar weighting also makes an assumption
    and a stranger one: that Sharpe is PROPORTIONAL to volatility, i.e. that the wilder sleeve has
    proportionally more edge. Neither is measured. The first is the one this desk would state out
    loud if asked, which is the test that decides between them.

    NOT progression under III.15 either: a sleeve that made money and one that lost money get the
    same clip if their volatilities match. Nothing here reads a return.
    """
    rets: list[np.ndarray] = []
    for sym, pos in positions.items():
        ser = frames.get(sym)
        close = None if ser is None else np.asarray(getattr(ser, "close", []), dtype="float64")
        if close is None or len(close) < 3 or len(pos) != len(close):
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.diff(close) / close[:-1]
        # LAGGED BY ONE BAR. A position multiplied by the SAME bar's return is the sleeve trading
        # on a close it could not have seen, and the volatility of that series is not the
        # volatility of anything tradeable.
        pnl = np.asarray(pos[:-1], dtype="float64") * r
        pnl = pnl[np.isfinite(pnl)]
        if len(pnl) >= 3:
            rets.append(pnl[-window:])
    if not rets:
        return None
    n = min(len(r) for r in rets)
    if n < 3:
        return None
    stacked = np.vstack([r[-n:] for r in rets])
    sd = float(np.std(stacked.mean(axis=0), ddof=1))
    return sd if np.isfinite(sd) and sd > 0 else None


def _risk_parity_clips(vols: dict[str, float | None]) -> tuple[dict[str, float], str]:
    """Inverse-volatility shares of the fixed envelope, summing to 1.0 across ALL sleeves.

    NORMALISED ACROSS EVERY SLEEVE, NOT ONLY THE LIVE ONES. A sleeve with no signal today holds
    cash, and its share must stay unspent rather than be redistributed -- otherwise the book's
    gross exposure would rise on exactly the days fewest mechanisms found anything to trade.

    A sleeve whose volatility is UNMEASURABLE gets the equal share. Not the largest, not zero: an
    unmeasured risk is not a licence to size up and not evidence the sleeve is idle (L1.28a).
    """
    n = len(vols)
    if n == 0:
        return {}, "no sleeves"
    equal = 1.0 / n
    measured = {k: v for k, v in vols.items() if v is not None and v > 0}
    if not measured:
        return (dict.fromkeys(vols, equal),
                f"every sleeve's volatility is UNMEASURABLE -- equal {equal:.1%} shares, which is "
                "the honest fallback rather than a computed-looking number built on nothing")
    inv = {k: 1.0 / float(v) for k, v in measured.items()}
    mean_inv = sum(inv.values()) / len(inv)
    raw = {k: (inv.get(k, mean_inv)) for k in vols}          # unmeasured -> the average inverse
    total = sum(raw.values())
    shares = {k: v / total for k, v in raw.items()}
    # THE CAP, APPLIED THEN RE-NORMALISED. Clipping alone would leave the shares not summing to 1
    # and quietly change the book's total exposure, which is the one thing this rewrite must not
    # touch: the envelope is fixed and only its division moves.
    lo, hi = equal / MAX_CLIP_MULTIPLE, equal * MAX_CLIP_MULTIPLE
    capped = {k: min(hi, max(lo, v)) for k, v in shares.items()}
    tot = sum(capped.values())
    out = {k: v / tot for k, v in capped.items()}
    n_capped = sum(1 for k in shares if abs(shares[k] - capped[k]) > 1e-12)
    return out, (f"inverse-volatility over {RISK_PARITY_WINDOW}d on {len(measured)}/{n} sleeves, "
                 f"{n_capped} clipped at {MAX_CLIP_MULTIPLE:g}x the equal share. SECOND MOMENT "
                 "ONLY -- no return, no Sharpe, so the backtest is not allocating capital")


def _equity_and_leverage() -> tuple[float, float, str]:
    """(net equity, leverage, why) from the margin executor's own last run.

    DELIBERATELY NOT A SECOND VENUE READ. The executor resolves equity against live balances and
    computes leverage from the book's own arithmetic; re-deriving either here would give two organs
    two answers about one account, and the one that sized the orders is the one that is true.
    UNREADABLE COLLAPSES THE UNIVERSE TO NOTHING rather than assuming a number -- an unknown balance
    must never WIDEN the book, because the failure it causes is legs the venue refuses.
    """
    try:
        d = json.loads(Path("web/margin_executor.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return _FALLBACK_EQUITY, 1.0, (
            f"web/margin_executor.json unreadable ({type(exc).__name__}) -- equity UNMEASURED, so "
            "the universe collapses to empty. An unknown balance must never widen a book")
    eq = d.get("equity_usd")
    lev = (d.get("leverage") or {}).get("leverage")
    if not isinstance(eq, (int, float)) or float(eq) <= 0:
        return _FALLBACK_EQUITY, 1.0, "margin executor reports no equity -- universe empty"
    return (float(eq), float(lev) if isinstance(lev, (int, float)) and lev > 0 else 1.0,
            f"equity ${float(eq):,.2f} at {lev}x, from the executor's last run")


def _history_and_liquidity(candidates: tuple[str, ...]) -> tuple[dict[str, int], dict[str, float]]:
    """{symbol: n_bars} and {symbol: dollar-volume proxy} from the lake. Absent symbols simply do
    not appear, which `select` reads as no history rather than as a short one."""
    from libs.autodiscovery.crypto_adapter import _read_frames
    from libs.data.timeframe import Timeframe

    try:
        frames = _read_frames(list(candidates), Timeframe.D1, _LAKE)
    except Exception:
        return {}, {}
    hist: dict[str, int] = {}
    liq: dict[str, float] = {}
    for s, df in (frames or {}).items():
        if df is None or not len(df):
            continue
        hist[s] = len(df)
        try:
            # Median dollar volume over the last 90 days. MEDIAN, not mean: one listing-day volume
            # spike would otherwise rank a thin name above a consistently deep one.
            tail = df.tail(90)
            liq[s] = float(np.median(np.asarray(tail["close"]) * np.asarray(tail["volume"])))
        except Exception:
            continue          # ranks LAST in `select`; unmeasured is not disqualifying
    return hist, liq

def _input_state(subtype: str, series: Any, params: dict[str, float]) -> tuple[bool, str]:
    """Distinguish a valid neutral signal from a generator's missing-input zero fallback.

    Both relevant generators deliberately return an all-zero vector when their required sidecar
    is absent.  The vector therefore cannot answer whether zero means *neutral now* or *never
    measured*.  Inspect the actual declared input instead; otherwise a healthy funding feed is
    repeatedly misdiagnosed and the repair loop wastes every night fixing data that already works.
    """
    # EXTENDED 2026-08-16 FROM TWO SLEEVES TO FOUR. `_input_state` covered only
    # `funding_stress_reversal` and `intermarket_difference`, and returned "declares no sidecar
    # contract" -- i.e. MEASURED -- for the other two, which both have one:
    #
    #   `funding_carry`           reads MarketSeries.funding, exactly as the fade does
    #   `producer_margin_stress`  returns np.zeros() outright when MarketSeries.hashprice is None
    #
    # So a starved carry or producer sleeve was reported NEUTRAL -- "no symbol crosses the entry
    # condition" -- when the truth was "the feed is absent". That is precisely the conflation this
    # function exists to prevent, surviving in the two sleeves it did not enumerate. Caught by
    # test_A_GENERATOR_WITHOUT_ITS_INPUT_IS_FLAT_AND_SAYS_SO, whose `needs_external` set already
    # named all four.
    if subtype in {"funding_stress_reversal", "funding_carry"}:
        raw = getattr(series, "funding", None)
        if raw is None:
            return False, "funding is absent"
        values = np.asarray(raw, dtype="float64")
        finite = values[np.isfinite(values)]
        needed = max(2, int(params.get("window", 1)) + 1)
        if len(finite) < needed:
            return False, f"funding has {len(finite)} finite rows; needs at least {needed}"
        if not np.any(np.abs(finite) > 1e-15):
            return False, "funding contains no observed non-zero print"
        return True, f"funding measured ({len(finite)} finite rows)"
    if subtype == "intermarket_difference":
        needed = max(2, int(params.get("lookback", 1)) + 1)
        counts = []
        for name in ("ref_close", "ref_high", "ref_low"):
            raw = getattr(series, name, None)
            if raw is None:
                return False, f"{name} is absent"
            values = np.asarray(raw, dtype="float64")
            counts.append(int(np.isfinite(values).sum()))
        if min(counts, default=0) < needed:
            return False, f"reference range has finite rows {counts}; needs at least {needed}"
        return True, f"reference close/high/low measured ({min(counts)} aligned rows)"
    if subtype == "producer_margin_stress":
        raw = getattr(series, "hashprice", None)
        if raw is None:
            return False, "hashprice is absent"
        values = np.asarray(raw, dtype="float64")
        finite = values[np.isfinite(values)]
        needed = max(2, int(params.get("window", 1)) + 1)
        if len(finite) < needed:
            return False, f"hashprice has {len(finite)} finite rows; needs at least {needed}"
        return True, f"hashprice measured ({len(finite)} finite rows)"
    return True, "generator declares no sidecar input contract"


def _marks() -> dict[str, float]:
    """Live prices, wallet-agnostic. Empty when the venue is unreadable -- and an EMPTY mark set
    must never be read as a zero return, which would trip the kill on every sleeve at once."""
    try:
        from libs.execution import binance_spot_live

        return {str(k): float(v) for k, v in binance_spot_live.prices().items()}
    except Exception:
        return {}


def _track(rep: dict[str, Any], px: dict[str, float]) -> dict[str, Any]:
    """Mark each sleeve since inception and APPLY THE KILL RULE.

    **THE RULE WAS DECLARED AND ENFORCED BY NOTHING.** `KILL_DRAWDOWN`, `REVIEW_DAYS` and `_STATE`
    were constants with no reader: the ledger promised a sleeve would be retired below -15% and
    the code would have traded it to zero. That is III.16 on the SAFETY half of an exception to a
    standing law -- the half whose absence is invisible precisely while things are going well.

    **THE MEASURE IS THE SLEEVE'S OWN WEIGHTS MARKED FORWARD, AND IT EXCLUDES COSTS.** Per-fill
    attribution across two books sharing one margin account is not available here. Marking the
    published weights is therefore OPTIMISTIC -- a real book pays fees, slippage and borrow that
    this does not subtract. The direction matters and it is the safe one: a kill that trips on an
    optimistic measure is definitely a kill, because the realised book did worse. It would be the
    reverse error -- a flattering measure used to KEEP a sleeve -- that this must never make, and
    surviving here is explicitly not evidence of anything (see the ledger).
    """
    try:
        state = json.loads(_STATE.read_text("utf-8"))
    except (OSError, ValueError):
        state = {}
    now = datetime.now(tz=UTC)
    rows = state.get("sleeves") if isinstance(state, dict) else None
    sleeves: dict[str, Any] = dict(rows or {})

    for row in rep["sleeves"]:
        key = str(row["census_class"])
        prior = sleeves.get(key) or {}
        if prior.get("retired"):
            row["state"] = "RETIRED"
            row["why"] = prior.get("retired_why", "retired by the pre-registered kill rule")
            continue
        held = {k: v for k, v in (row.get("symbols") or {}).items() if abs(float(v)) > 1e-12}
        if row.get("state") != "LIVE" or not held:
            continue

        marks = prior.get("marks") or {}
        if not marks:
            # INCEPTION. Recorded on the first LIVE run, from live prices. A sleeve with no
            # inception marks has no return to judge and must not be killed for it.
            fresh = {k: px[retarget(k, "USDC")] for k in held if retarget(k, "USDC") in px}
            if fresh:
                sleeves[key] = {"inception": now.isoformat(), "marks": fresh,
                                "weights": {k: float(v) for k, v in held.items()}}
            row["tracking"] = "INCEPTION recorded" if fresh else "no marks available yet"
            continue

        w = prior.get("weights") or {}
        contribs = []
        for sym, w0 in w.items():
            p0, p1 = float(marks.get(sym, 0.0)), float(px.get(retarget(sym, "USDC"), 0.0))
            if p0 > 0 and p1 > 0:
                contribs.append((1.0 if float(w0) > 0 else -1.0) * (p1 / p0 - 1.0))
        if not contribs:
            # UNMEASURED, NOT ZERO. An unreadable price set must never present as a flat return --
            # that is a measurement failure wearing the shape of a healthy sleeve.
            row["tracking"] = "UNMEASURED -- no marks readable this run; the kill rule cannot bind"
            continue
        ret = float(np.mean(contribs))
        age_days = (now - datetime.fromisoformat(str(prior["inception"]))).total_seconds() / 86400
        prior["last_return"], prior["age_days"] = round(ret, 6), round(age_days, 2)
        row["return_since_inception"] = round(ret, 6)
        row["age_days"] = round(age_days, 2)

        why = None
        if ret <= KILL_DRAWDOWN:
            why = (f"RETIRED: return since inception {ret:+.2%} at or below the pre-registered "
                   f"kill of {KILL_DRAWDOWN:+.0%}. Fixed before the first fill, so it is not "
                   "renegotiable by the sleeve that breached it")
        elif age_days >= REVIEW_DAYS and ret < 0:
            why = (f"RETIRED: {age_days:.0f} days elapsed (review at {REVIEW_DAYS}) with a return "
                   f"of {ret:+.2%}. The review test was non-negative, declared in advance")
        if why:
            prior["retired"], prior["retired_why"] = True, why
            row["state"], row["why"] = "RETIRED", why
            # A RETIRED SLEEVE PUBLISHES NO WEIGHTS. Its slice falls out of the target book and
            # the executor's reduce leg unwinds it on the next run -- which only works because
            # that leg now exists.
            for sym in list(w):
                rep["target_weights"].pop(sym, None)
        sleeves[key] = prior

    state = {"updated": now.isoformat(), "sleeves": sleeves,
             "measure": ("published weights marked forward, EXCLUDING fees, slippage and borrow. "
                         "Optimistic by construction, so a kill it trips is conservative -- the "
                         "realised book did worse. Never used to justify KEEPING a sleeve"),
             "kill_drawdown": KILL_DRAWDOWN, "review_days": REVIEW_DAYS}
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), "utf-8")
    rep["n_retired"] = sum(1 for v in sleeves.values() if v.get("retired"))
    return rep


def build() -> dict[str, Any]:
    ok, why_exc = _exception_recorded()
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "exception_active": ok, "exception_why": why_exc,
        "law_suspended": "L1.6 -- capital from pre-registered FORWARD evidence only",
        "kill_rule": {"clip_frac": EQUAL_CLIP_FRAC, "kill_drawdown": KILL_DRAWDOWN,
                      "review_days": REVIEW_DAYS,
                      "fixed": "BEFORE the first fill, so it cannot be renegotiated by the sleeve "
                               "that breaches it"},
        "sleeves": [], "target_weights": {}, "refused": [],
        # THE SHARE OF THE ACCOUNT THIS ARTIFACT CLAIMS, and it must be declared or the executor
        # reads these weights as the WHOLE book. Measured live 2026-08-15: 5% gross across three
        # symbols was interpreted as an instruction to sell 95% of the account -- liquidating the
        # momentum book to fund a 5% sleeve. Only the unrelated "SELL legs are not placed here"
        # rule stopped it, which is a safety net in the way rather than a design.
        "book_frac": round(EQUAL_CLIP_FRAC * len(SLEEVES), 6),
        "book_frac_why": (
            f"{len(SLEEVES)} sleeve(s) at {EQUAL_CLIP_FRAC:.0%} each ON AVERAGE -- the envelope is "
            "fixed and inverse-volatility decides only how it is divided. These are shares of "
            "THAT slice, never of the account -- a sleeve describing 10% of the book is not a "
            "90% liquidation order for everything else"),
    }
    if not ok:
        rep["refused"].append(why_exc)
        return rep

    # THE UNIVERSE, DERIVED. Capital first, then history, then a liquidity ranking. Widening is
    # therefore automatic on funding and impossible without it -- which is the correct direction:
    # the failure from publishing legs below the venue floor is silent underweight, and the failure
    # from holding six names on capital that funds eighteen is unbought turnover at the same edge.
    from libs.research.sleeve_universe import select as _select_universe

    equity, leverage, why_equity = _equity_and_leverage()
    hist, liq = _history_and_liquidity(SYMBOLS)
    uni = _select_universe(
        SYMBOLS, equity_usd=equity, leverage=leverage,
        book_frac=EQUAL_CLIP_FRAC * len(SLEEVES), n_sleeves=len(SLEEVES),
        min_notional=MIN_NOTIONAL_USD, history=hist, liquidity=liq)
    uni["equity_why"] = why_equity
    rep["universe"] = uni
    symbols = tuple(uni["symbols"])
    if not symbols:
        rep["refused"].append(
            f"{uni.get('why')} ({why_equity})")
        return rep

    frames = _series(symbols)
    if not frames:
        rep["refused"].append(
            f"no lake series for any of {list(SYMBOLS)} -- UNMEASURED. Publishing an empty target "
            "book would read as 'go to cash' and SELL the account, which is a position nobody "
            "chose")
        return rep

    # PASS ONE: every sleeve's position series AND its input state, computed ONCE.
    #
    # The volatility that sets the clips and the last value that sets the signal come from the same
    # arrays, so the weight a sleeve gets and the trade it publishes can never be derived from two
    # different runs of a generator. THE INPUT STATE IS CAPTURED IN THE SAME PASS, for the same
    # reason: "was the feed there" asked in a second sweep could answer about a different read than
    # the one the positions came from, and the entire point of `_input_state` is to say which of
    # two identical-looking zero vectors is a market view and which is a missing sidecar.
    series_by_sleeve: dict[str, dict[str, np.ndarray]] = {}
    inputs_by_sleeve: dict[str, dict[str, dict[str, Any]]] = {}
    for census_class, subtype, _mech, params in SLEEVES:
        got: dict[str, np.ndarray] = {}
        input_states: dict[str, dict[str, Any]] = {}
        for sym, ser in frames.items():
            input_ok, input_why = _input_state(subtype, ser, params)
            input_states[sym] = {"measured": input_ok, "why": input_why}
            pos = _positions(subtype, ser, params)
            if pos is not None and len(pos):
                got[sym] = pos
        series_by_sleeve[census_class] = got
        inputs_by_sleeve[census_class] = input_states

    vols = {c: _sleeve_vol(series_by_sleeve.get(c, {}), frames) for c, _s, _m, _p in SLEEVES}
    clips, clips_why = _risk_parity_clips(vols)
    rep["sizing"] = "RISK PARITY (inverse volatility)"
    rep["sizing_why"] = clips_why
    rep["sleeve_vol"] = {k: (None if v is None else round(v, 6)) for k, v in vols.items()}

    weights: dict[str, float] = {}
    for census_class, subtype, mechanism, params in SLEEVES:
        share = float(clips.get(census_class, 1.0 / len(SLEEVES)))
        row: dict[str, Any] = {"census_class": census_class, "generator": subtype,
                               "mechanism": mechanism, "params": params, "symbols": {},
                               "vol": None if vols[census_class] is None
                               else round(float(vols[census_class]), 6),
                               "share_of_slice": round(share, 6),
                               "clip_frac": round(share * EQUAL_CLIP_FRAC * len(SLEEVES), 6)}
        live: dict[str, float] = {}
        pos_map = series_by_sleeve.get(census_class, {})
        # FROM PASS ONE, NOT RE-DERIVED. Same read as the positions above it.
        input_states = inputs_by_sleeve.get(census_class, {})
        if not pos_map and frames:
            row["error"] = f"no generator named {subtype!r} in this repo, or it returned nothing"
        for sym in frames:
            pos = pos_map.get(sym)
            if pos is None or len(pos) == 0:
                continue
            last = float(pos[-1])
            # A GENERATOR THAT DEGRADES TO FLAT IS SAYING ITS INPUT IS MISSING, NOT THAT THE
            # MARKET IS NEUTRAL. funding_stress_reversal returns zeros without funding data, and
            # intermarket_difference returns zeros without the reference's RANGE. Recording the
            # all-zero case separately is what keeps "no data" from being published as "no signal".
            live[sym] = last
        row["symbols"] = live
        row["inputs"] = input_states
        measured_inputs = sum(bool(v["measured"]) for v in input_states.values())
        row["input_coverage"] = {
            "measured": measured_inputs,
            "attempted": len(input_states),
        }
        nonzero = {k: v for k, v in live.items() if abs(v) > 1e-12}
        if not nonzero and live:
            if measured_inputs == len(input_states):
                row["state"] = "NEUTRAL"
                row["why"] = (
                    "required input is measured for every attempted symbol; no symbol crosses "
                    "the predeclared entry condition now"
                )
            elif measured_inputs:
                row["state"] = "PARTIAL-INPUT"
                row["why"] = (
                    f"required input measured for {measured_inputs}/{len(input_states)} symbols; "
                    "zeros on the remainder are not market-neutral observations"
                )
            else:
                row["state"] = "NO-INPUT"
                row["why"] = (
                    "every zero came from a generator whose required sidecar input is absent or "
                    "insufficient; this is UNMEASURED, not a market view"
                )
        elif not live:
            row["state"] = "NO-SERIES"
        else:
            row["state"] = "LIVE"
            # LONG-ONLY, because the book settles on a spot-margin account where a short is a
            # borrow of the base asset rather than of quote. Refusals are recorded, never inverted.
            longs = {k: v for k, v in nonzero.items() if v > 0}
            row["shorts_refused"] = sorted(k for k, v in nonzero.items() if v < 0)
            if longs:
                # WITHIN THE SLICE. Each sleeve owns `share` of book_frac -- its inverse-volatility
                # share, which sums to 1.0 across ALL sleeves including the flat ones -- and splits
                # that equally across its own longs. The published weights therefore sum to at most
                # 1.0 across the slice and the executor scales them by book_frac. Publishing
                # account-shares here would make a weight mean different things in different files.
                per = share / len(longs)
                for k in longs:
                    weights[k] = round(weights.get(k, 0.0) + per, 6)
        rep["sleeves"].append(row)

    rep["target_weights"] = weights
    rep = _track(rep, _marks())
    weights = rep["target_weights"]
    rep["gross_frac_of_slice"] = round(sum(weights.values()), 6)
    rep["gross_frac_of_account"] = round(sum(weights.values()) * rep["book_frac"], 6)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    print(f"mechanism-sleeves: exception={'ACTIVE' if rep['exception_active'] else 'ABSENT'} -- "
          f"{rep['exception_why'][:150]}")
    for r in rep["sleeves"]:
        print(f"  [{r.get('state','?'):<16}] {r['census_class']:<30} {r['generator']}")
        if r.get("why"):
            print(f"      {r['why']}")
        if r.get("shorts_refused"):
            print(f"      shorts refused (long-only book): {', '.join(r['shorts_refused'])}")
    for w in rep["refused"]:
        print(f"  REFUSED: {w}")
    if rep["target_weights"]:
        print(f"  slice {rep['book_frac']:.1%} of the account; weights are shares OF THAT SLICE "
              f"({rep['gross_frac_of_slice']:.0%} of it = {rep['gross_frac_of_account']:.1%} of "
              f"the book): "
              + ", ".join(f"{k} {v:.3%}" for k, v in sorted(rep["target_weights"].items())))
    print(f"-> {_OUT}")
    return 0 if rep["exception_active"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
