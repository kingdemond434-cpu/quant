#!/usr/bin/env python3
"""THE LEVERED ORDER PATH -- the same book, sized by Kelly, on borrowed money.

WHAT THIS ADDS OVER THE SPOT EXECUTOR, and it is exactly one thing: the gross exposure may exceed
1.0, because the margin wallet can borrow. Everything else -- target weights, delta-not-target,
free-cash clamping, floor-to-the-cent, the ruin rails -- is the same discipline, and where it is the
same it calls the same code.

**THE LEVERAGE IS COMPUTED, NEVER CONFIGURED.** `libs.execution.leverage_policy` returns the
smaller of the Kelly bound and the survival bound, at full Kelly on a confidence-discounted Sharpe.
There is no `--leverage` flag and there will not be one: a number typed at the command line is a
number chosen by mood, and this book's own arithmetic already answers the question. When the edge
is thin the policy returns less than 1.0x and this script borrows NOTHING -- that is the same
mechanism working, not a failure to lever.

**MEASURED 2026-08-15, so nobody has to rediscover it:** the live book's Kelly was 1.49x and its
ZERO-GROWTH point 2.99x. A 3x floor would have forced roughly zero expected growth while carrying
full liquidation risk. The floor was removed for that reason, and this script inherits the result:
it levers when the evidence supports it and declines when it does not.

**EQUITY IS NET ASSET, NOT BALANCE.** On margin the wallet's balance includes borrowed funds.
Sizing against it would compound leverage on leverage -- borrow, count the proceeds as equity,
borrow against those -- which is how a 2x book becomes a 5x book without anyone choosing it. Net
asset (assets minus liabilities INCLUDING accrued interest) is the only figure that means capital.

**IT NEVER MOVES CAPITAL.** The connector has no transfer surface, so this trades what is already
in the margin wallet and reports a zero balance rather than funding itself. Moving money between
wallets is the act that decides how much can be lost and stays the principal's, in the app.

    python scripts/run_margin_executor.py --quote USDC              # dry run
    python scripts/run_margin_executor.py --quote USDC --place      # borrows and buys
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

from libs.execution import maker_first
from libs.execution.leverage_policy import choose, realised_vol
from libs.execution.maker_first import maker_first_buy
from libs.execution.ruin_rail import frozen
from libs.execution.spot_order_path import floor_2dp, retarget, round_step

_TARGETS = Path("data/spot_momentum.json")
_JOURNAL = Path("data/margin_executor_journal.jsonl")
_OUT = Path("web/margin_executor.json")

#: Annualised cross-margin borrow rate assumed when the venue's own figure is unavailable. It
#: enters the KELLY NUMERATOR, so understating it over-levers by exactly the amount understated --
#: hence a deliberately high default rather than a flattering one.
#: NO LONGER A DEFAULT -- kept only so an operator can see what the placeholder WAS, and what it
#: cost. At 10% assumed against a book earning 8.2%/yr (Sharpe 0.48 at 17% vol), Kelly returns
#: 0.00x and the margin path reports "1.00x FLOOR BINDING": the account was moved to cross margin
#: for leverage the arithmetic was refusing on a number nobody had measured. The rate is now read
#: from the venue, which publishes it hourly and charges it hourly.
_HISTORICAL_PLACEHOLDER_BORROW_RATE = 0.10


def _targets(path: Path | None = None) -> tuple[
        dict[str, float], float | None, int | None, str, float]:
    """Target weights plus the book's own Sharpe and observation count, from one artifact.

    All three come from the same file BECAUSE THEY MUST DESCRIBE THE SAME BOOK. A Sharpe read from
    one run and weights from another would lever today's positions by yesterday's evidence.

    `path` selects which book. A SECOND BOOK IS A SECOND ARTIFACT, never a merge: combining two
    target sets here would produce weights no single organ published, sized against a Sharpe that
    describes neither, and leave nothing on disk that says what was actually intended.
    """
    src = path or _TARGETS
    try:
        d = json.loads(src.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {}, None, None, (f"{src} unreadable ({type(exc).__name__}) -- UNMEASURED. "
                                "Refusing: an empty book would read as 'go to cash' and would sell "
                                "everything on borrowed money"), 1.0
    w = d.get("target_weights")
    if not isinstance(w, dict) or not w:
        return {}, None, None, f"{src} carries no target_weights", 1.0
    sharpe = d.get("sharpe_excess")
    n = d.get("n_days")
    # `book_frac`: the share of the ACCOUNT this artifact claims. A sleeve that publishes 5% gross
    # is describing 5% of the book, not a 95% liquidation order for everything else.
    frac = d.get("book_frac")
    return ({str(k): float(v) for k, v in w.items()},
            float(sharpe) if isinstance(sharpe, (int, float)) else None,
            int(n) if isinstance(n, (int, float)) else None,
            f"{len(w)} weight(s), sharpe_excess={sharpe}, n={n}, book_frac={frac or 1.0}",
            float(frac) if isinstance(frac, (int, float)) and 0.0 < float(frac) <= 1.0 else 1.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quote", default="USDC")
    ap.add_argument("--place", action="store_true",
                    help="ACTUALLY BORROW AND BUY. Absent, prints what it would do")
    ap.add_argument("--borrow-rate", type=float, default=None,
                    help="annualised cost of borrowing. DEFAULT: read from the venue. This number "
                         "decides whether leverage exists at all -- Kelly is (mu-r)/sigma^2 -- and "
                         "it was a 10%% placeholder until 2026-08-15, which capped the book at 1x "
                         "against its own measured edge. Pass a number only to override a venue "
                         "read you have a reason to distrust")
    ap.add_argument("--cycle", default=None)
    ap.add_argument("--maker-wait", type=float, default=maker_first.DEFAULT_WAIT_S,
                    help="seconds an entry rests passively before the remainder is crossed "
                         f"(default {maker_first.DEFAULT_WAIT_S:g}s). 0 quotes and crosses "
                         "immediately, which is the old MARKET-order behaviour with an extra "
                         "round trip -- use it only if the passive fills prove adversely selected")
    ap.add_argument("--targets", default=None,
                    help="target-weights artifact to trade. Defaults to the momentum book. Point "
                         "it at data/mechanism_sleeve_targets.json to run the mechanism sleeves as "
                         "a SEPARATE book -- separate so each has its own weights, its own Sharpe "
                         "and its own row on disk, rather than one merged set nobody published")
    args = ap.parse_args()

    from libs.execution import binance_margin_live as m
    from libs.execution import binance_spot_live as spot

    cycle = args.cycle or datetime.now(tz=UTC).strftime("%Y%m%d")
    armed, why_armed = m.is_armed()
    rail, why_rail = frozen()
    place = bool(args.place) and not rail and armed

    weights, sharpe, n_obs, why_targets, book_frac = _targets(
        Path(args.targets) if args.targets else None)
    why_frac = ("1.0 -- this artifact declares no book_frac, so it claims the whole account (the "
                "momentum book always did)" if book_frac >= 1.0 else
                f"{book_frac:.1%} of the account, declared by the artifact itself")
    rep: dict[str, Any] = {"updated": datetime.now(tz=UTC).isoformat(), "cycle": cycle,
                           "armed": armed, "armed_why": why_armed, "rail_frozen": rail,
                           "rail_why": why_rail, "targets_why": why_targets,
                           "quote": args.quote, "dry_run": not place,
                           "placed": [], "refused": [], "reduced": []}

    def _finish(code: int) -> int:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
        _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with _JOURNAL.open("a", encoding="utf-8") as fh:
            for r in rep["placed"] + rep["reduced"] + rep["refused"]:
                fh.write(json.dumps({"at": rep["updated"], "cycle": cycle, **r}) + "\n")
        return code

    if not weights:
        rep["refused"].append({"why": why_targets})
        print(f"margin-executor: {why_targets}")
        return _finish(1)
    if not armed:
        rep["refused"].append({"why": f"NOT ARMED -- {why_armed}"})
        print(f"margin-executor: not armed ({why_armed}). data/MARGIN_ENABLE is the principal's "
              "act and no organ writes it")
        return _finish(1)

    try:
        acct = m.account()
        px = spot.prices()
        filters = spot.exchange_filters()
    except Exception as exc:
        why = (f"venue unreadable ({type(exc).__name__}: {exc}) -- refusing. Trading leverage "
               "against an unknown position is how a rebalance becomes a liquidation")
        rep["refused"].append({"why": why})
        print(f"margin-executor: {why}")
        return _finish(1)

    # EQUITY IS NET ASSET. The wallet balance includes borrowed funds, and sizing against it would
    # compound leverage on leverage without anyone choosing to.
    try:
        btc = float(px.get("BTCUSDT") or px.get("BTCUSDC") or 0.0)
        equity = float(acct.get("totalNetAssetOfBtc") or 0.0) * btc
    except (TypeError, ValueError):
        equity = 0.0
    if equity <= 0 or btc <= 0:
        why = ("net asset UNMEASURED (totalNetAssetOfBtc or the BTC price is missing) -- refusing "
               "rather than sizing leverage against a denominator nobody measured")
        rep["refused"].append({"why": why})
        print(f"margin-executor: {why}")
        return _finish(1)

    # THE LEVERAGE, COMPUTED. Portfolio sigma comes from the book's own recent returns; the Sharpe
    # and n come from the same artifact as the weights, so the evidence and the positions match.
    held = m.balances()
    owed = m.liabilities()
    rets = _recent_portfolio_returns(weights, px)
    sigma = realised_vol(rets) if rets else None
    # THE COST OF CAPITAL IS READ, NOT ASSUMED. An override is honoured; otherwise the venue is
    # asked. If the venue cannot answer, the rate is UNMEASURED and leverage is refused outright --
    # falling back to the old placeholder would restore exactly the defect this replaces, and an
    # unmeasured cost of borrowing is the one input on which guessing low ends the account.
    if args.borrow_rate is not None:
        rate, why_rate = float(args.borrow_rate), f"OVERRIDE from --borrow-rate: {args.borrow_rate}"
    else:
        rate, why_rate = m.borrow_rate(args.quote)
    rep["borrow_rate"] = rate
    rep["borrow_rate_why"] = why_rate
    if rate is None:
        lev = choose(sigma, sharpe=sharpe, n_obs=n_obs, borrow_rate=0.0, ceiling=1.0)
        lev["why"] = ("borrow rate UNMEASURED -- leverage held at 1.00x. " + why_rate
                      + ". Borrowing at an unknown cost is the one sizing input where a low guess "
                        "ends the account rather than merely underperforming")
    else:
        lev = choose(sigma, sharpe=sharpe, n_obs=n_obs, borrow_rate=rate)
    rep["book_frac"] = book_frac
    rep["book_frac_why"] = why_frac
    rep["equity_usd"] = round(equity, 2)
    rep["leverage"] = dict(lev)
    rep["margin_level"] = m.margin_level()
    rep["liabilities"] = {k: round(v, 8) for k, v in owed.items()}

    # THE BOOK SLICE. A targets artifact may claim only PART of the account, and until 2026-08-15
    # it could not: every weights file was read as THE WHOLE BOOK. Measured live -- the mechanism
    # sleeves published 5% gross across three symbols, and this executor therefore wanted to sell
    # 95% of an account it did not own, liquidating the momentum book to fund a 5% sleeve. Nothing
    # caught it except the unrelated rule that SELL legs are not placed here, which is a safety net
    # that happens to be in the way rather than a design.
    #
    # `book_frac` is declared BY THE ARTIFACT. Absent, it is 1.0 -- the momentum book is the whole
    # account and always was, so the old behaviour is preserved exactly where it was correct.
    gross_usd = equity * float(lev["leverage"]) * book_frac
    free_quote = float(held.get(args.quote, 0.0))
    spent = 0.0
    #: Routing outcomes, kept so the maker share is computed once by `maker_first.maker_share`
    #: rather than re-derived from the serialised rows here.
    routed_legs: list[maker_first.MakerOutcome] = []

    # REDUCE LEGS FIRST, then adds. A rebalance that buys before it sells asks for cash the run is
    # about to raise, and every buy leg is refused for insufficient funds while the sell that would
    # have funded it waits its turn. Ordering by delta ascending puts the sells at the front.
    def _delta_usd(kv: tuple[str, float]) -> float:
        sym_ = retarget(kv[0], args.quote)
        base_ = retarget(kv[0], "")
        price_ = float(px.get(sym_) or 0.0)
        return kv[1] * gross_usd - float(held.get(base_, 0.0)) * price_

    for research_sym, frac in sorted(weights.items(), key=_delta_usd):
        sym = retarget(research_sym, args.quote)
        base = retarget(research_sym, "")
        price = float(px.get(sym) or 0.0)
        want = frac * gross_usd
        have = float(held.get(base, 0.0)) * price
        delta = want - have
        f = filters.get(sym, {})
        min_notional = float(f.get("min_notional") or 0.0) or 5.0
        row: dict[str, Any] = {"symbol": sym, "weight": frac, "want_usd": round(want, 2),
                               "have_usd": round(have, 2), "delta_usd": round(delta, 2)}
        if price <= 0:
            row["why"] = f"{sym} carries no price -- it may not be listed in {args.quote}"
            rep["refused"].append(row)
            continue
        if abs(delta) < min_notional:
            row["why"] = (f"delta ${abs(delta):,.2f} below the venue minimum ${min_notional:,.2f}"
                          " -- the position stays where it is rather than paying a fee for noise")
            rep["refused"].append(row)
            continue
        if delta < 0:
            # THE REDUCE LEG. `place_market_reduce` -- AUTO_REPAY, deliberately never gated on the
            # margin level -- existed, was tested, and had NO CALLER on the money path (III.16).
            # The consequence was structural rather than cosmetic: a BUY-only executor cannot
            # rebalance down, cannot take profit, and cannot free quote. Measured 2026-08-15, the
            # account sat at $193 of equity in three coins with ONE CENT of USDC, and every leg it
            # wanted was a SELL -- so the book was fully invested, permanently, with no mechanism
            # to fund a new sleeve or trim a position that had run.
            #
            # SELLING IS THE OPERATION THAT RAISES THE MARGIN LEVEL. The original comment used
            # that as a reason to refuse; it is the reason to ALLOW. A book that can borrow but
            # never repay only moves toward liquidation.
            qty_wanted = abs(delta) / price
            held_base = float(held.get(base, 0.0))
            # NEVER MORE THAN IS HELD. Selling beyond the balance on cross margin does not fail --
            # it OPENS A SHORT by borrowing the base asset, converting a rebalance into a new
            # levered position nobody asked for. The min() is the whole guard.
            qty = round_step(min(qty_wanted, held_base), float(f.get("step") or 0.0))
            row["qty"] = qty
            row["held_base"] = held_base
            if qty <= 0 or qty * price < min_notional:
                row["why"] = (f"reduce leg of {qty_wanted:.8f} {base} rounds to {qty:.8f} against "
                              f"{held_base:.8f} held -- below the venue minimum "
                              f"${min_notional:,.2f}. The position stays rather than paying a fee "
                              "for noise")
                rep["refused"].append(row)
                continue
            if not place:
                row["why"] = f"DRY RUN -- would SELL {qty:.8f} {base} (${qty * price:,.2f})"
                rep["reduced"].append(row)
                free_quote += qty * price
                continue
            try:
                row["result"] = m.place_market_reduce(sym, "SELL", qty, cycle=cycle)
                rep["reduced"].append(row)
                # THE PROCEEDS FUND THE LATER BUY LEGS IN THIS SAME RUN. Without this the executor
                # would sell an overweight coin and then refuse the underweight one for lack of
                # cash it had just raised.
                free_quote += qty * price
            except Exception as exc:
                row["why"] = f"REDUCE REJECTED ({type(exc).__name__}: {exc})"
                rep["refused"].append(row)
            continue

        # BORROW ONLY WHAT THE CASH DOES NOT COVER. Spending free quote first keeps the liability
        # -- and its interest -- as small as the target allows.
        spend = floor_2dp(delta)
        borrow = spend > free_quote + 1e-9
        row["borrow"] = borrow
        if not place:
            row["why"] = ("DRY RUN -- would " + ("BORROW and " if borrow else "") +
                          f"buy ${spend:,.2f}; --place spends money")
            rep["placed"].append(row)
            free_quote = max(0.0, free_quote - spend)
            spent += spend
            continue
        try:
            # MAKER-FIRST. Until 2026-08-15 this line was a MARKET order and the margin book paid
            # the full spread on every entry -- on the alt legs the mechanism sleeves rotate
            # through, that is 5-20bps a side against an edge measured in tens of bps, charged on
            # every rebalance. `maker_first_buy` quotes at the bid, waits once, and crosses only
            # the unfilled remainder, so the worst case is this line's old behaviour plus the
            # drift across the wait. The daily signal horizon is what makes the wait affordable.
            routed = maker_first_buy(
                m, sym, spend, cycle=cycle, min_notional=min_notional,
                step=float(f.get("step") or 0.0), tick=float(f.get("tick") or 0.0),
                borrow=borrow, wait_s=float(args.maker_wait))
            routed_legs.append(routed)
            row["result"] = routed.result
            row["route"] = routed.mode
            row["maker_usd"] = round(routed.maker_usd, 2)
            row["route_why"] = routed.why
            rep["placed"].append(row)
            free_quote = max(0.0, free_quote - spend)
            spent += spend
        except Exception as exc:
            row["why"] = f"ORDER REJECTED ({type(exc).__name__}: {exc})"
            rep["refused"].append(row)

    mode = "RAIL FROZEN" if rail else ("LIVE" if place else "DRY RUN")
    print(f"=== MARGIN EXECUTOR [{mode}] === equity ${equity:,.2f} net asset, "
          f"leverage {lev['leverage']:.2f}x ({lev['state']}), gross ${gross_usd:,.2f}")
    print(f"  {str(lev['why'])[:200]}")
    print(f"  margin level {rep['margin_level']}  liabilities {rep['liabilities'] or '{}'}")
    for r in rep.get("reduced", []):
        print(f"  SELL {r['symbol']:<10} ${abs(r['delta_usd']):>9,.2f}  "
              f"qty={r.get('qty')}  [AUTO_REPAY]")
    # THE MAKER SHARE, BY NOTIONAL, OR None. The passive wait buys half the spread and pays for it
    # in adverse selection; which side of that trade this book is on is measurable only if the
    # split is recorded. None on an empty run rather than 0.0 -- no legs is not a bad maker share.
    # Computed by the SAME function the discretionary runner uses, so the two books cannot report
    # incomparable numbers under one name.
    rep["maker_share"] = maker_first.maker_share(routed_legs)
    for r in rep["placed"]:
        print(f"  BUY  {r['symbol']:<10} ${r['delta_usd']:>9,.2f}"
              f"{'  [BORROWED]' if r.get('borrow') else ''}"
              f"{'  [' + str(r['route']) + ']' if r.get('route') else ''}")
    if rep.get("maker_share") is not None:
        print(f"  maker share {rep['maker_share']:.0%} by notional "
              f"(waited {args.maker_wait:g}s per leg)")
    for r in rep["refused"]:
        print(f"  SKIP {r.get('symbol', '-'):<10} {str(r.get('why', ''))[:100]}")
    return _finish(0)


def _recent_portfolio_returns(weights: dict[str, float], px: dict[str, float]) -> list[float]:
    """The BOOK's daily returns, not the average of its constituents'.

    Those differ by exactly the diversification the portfolio provides, and using the constituent
    average would overstate sigma -- which understates leverage, in the direction that quietly
    costs growth rather than the one that costs the account.
    """
    try:
        from libs.autodiscovery.crypto_adapter import _read_frames
        from libs.data.timeframe import Timeframe
        frames = _read_frames(list(weights), Timeframe.D1, "data/lake")
    except Exception:
        return []
    series = []
    for sym, w in weights.items():
        df = frames.get(sym)
        if df is None or len(df) < 40:
            continue
        r = df["close"].pct_change(fill_method=None).fillna(0.0).to_numpy()[-60:]
        series.append(w * r)
    if not series:
        return []
    n = min(len(s) for s in series)
    return [float(sum(s[i] for s in series)) for i in range(n)]


if __name__ == "__main__":
    raise SystemExit(main())
