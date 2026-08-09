"""Molded LIVE account -> live_combined.json: cash-carry's futures + spot legs, equalised capital.

TOP = combined molded (both legs on equal $BASE so it's fair); then the PnL breakdown; then the
futures account gains (rich); then the spot account (simple). Perp book retired -- not shown. Each
level reports equity, net PnL, daily %, monthly %, unrealised + realised since start. Real Binance
numbers (futures = the short legs, spot = the long legs); molded net is the delta-neutral truth.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut
from libs.execution.carry_accounting import (
    carry_bleed_report,
    derive_spot_realized,
    read_income,
    reconcile_futures_leg,
)
from libs.portfolio.live_book import LivePortfolio
from libs.risk import capital_events

_CC = Path("web/cashcarry_live.json")
_STATE = Path("data/cashcarry_positions.json")
_CURVE = Path("data/live_combined_state.json")
_LEVLAB = Path("data/levered_lab_state.json")    # experimental levered sim (fresh, paper)
_TRADES = Path("data/cashcarry_trades.json")
_SHADOW = Path("web/crypto_shadow.json")         # perp L/S book (paper) -> combined into molded
_TREND = Path("web/trend_shadow.json")           # trend candidate -- OWN shadow only, NOT in molded
_TREND_RG = Path("web/trend_regime_shadow.json")  # regime-gated challenger (own clock)
_OUT = Path("web/live_combined.json")
_PORT = Path("web/portfolio.json")
_BASE = 5000.0                                   # equalised start per leg = fresh testnet balance


def _load(p: Path) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(p.read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


def _pct_ago(curve: list[list[Any]], equity: float, hours: float) -> float | None:
    """% return over the trailing `hours` window. None if the curve doesn't span that window yet.

    Honest: returns None (dashboard shows "-") until there is genuinely `hours` of history, so a
    young/just-reset curve can't report a fake gain measured off an arbitrary post-reset baseline.
    """
    if len(curve) < 2:
        return None
    try:
        oldest = datetime.fromisoformat(curve[0][0]).timestamp()
    except (ValueError, TypeError):
        return None
    cutoff = datetime.now(tz=UTC).timestamp() - hours * 3600
    if oldest > cutoff:
        return None                                  # not enough history for this window
    base = equity
    for t, e in curve:
        try:
            if datetime.fromisoformat(t).timestamp() >= cutoff:
                base = e
                break
        except (ValueError, TypeError):
            continue
    return round((equity / base - 1.0) * 100, 3) if base else None


def _curve_winrate(feed: dict[str, Any]) -> float | None:
    """Daily win rate = % of UP-days on a shadow equity curve (paper books have no discrete trades,
    so % positive daily steps is the honest hit-rate analog). None until >=5 steps exist."""
    curve = feed.get("equity") if isinstance(feed.get("equity"), list) else []
    vals = [c.get("v") for c in curve if isinstance(c, dict) and c.get("v") is not None]
    n = len(vals) - 1
    if n < 5:
        return None
    wins = sum(1 for i in range(1, len(vals)) if vals[i] > vals[i - 1])
    return round(100.0 * wins / n, 1)


def _start_equity(st: dict[str, Any], fut_eq: float) -> float:
    """R0322: the inception THIS book measures from -- the same one the executor measures from.

    This file publishes portfolio.json; scripts/run_cashcarry_executor.py publishes
    cashcarry_live.json. Both report "net PnL since start", and this one read the raw
    `start_futures_equity` while the executor had already moved to the capital-events-aware
    baseline (R0071b). A single ledgered deposit therefore split the desk into two published
    books measuring from two different inceptions -- and the molded book, the one that reads as
    the account of record, would have shown the whole deposit as fabricated P&L. One function,
    one inception, both books.

    Reporting only: `effective_start_equity` is the INCEPTION (P&L + ruin rail). The pause rail's
    baseline is the flow-adjusted high-water (R0320, `capital_events.flow_adjusted_rail`), which
    lives in the executor because it is the organ that computes combined equity from venue truth.
    """
    return float(capital_events.effective_start_equity(_num(st.get("start_futures_equity"),
                                                            fut_eq)))


def main() -> None:
    cc, st = _load(_CC), _load(_STATE)

    fa = fut.account_summary() if fut.has_keys() else {}
    fut_eq = round(_num(fa.get("equity")), 2)
    fut_unrl = round(_num(fa.get("unrealized_pnl")), 2)
    fut_start_real = _start_equity(st, fut_eq)
    # `funding` is None until MEASURED, for the same reason `venue_realized` already was: a venue
    # read that fails must not decay into a zero harvest. The old `0.0` seed plus an
    # `except (ValueError, TypeError)` that could not even catch the venue's HTTPError meant this
    # book either crashed outright or published a fabricated zero (2026-07-26 -- the executed book
    # published $0.00 against a true $101.96). `read_income` retries transient 5xx and reports
    # honestly when it cannot measure.
    realized = 0.0
    funding = None
    venue_realized = None
    fut_commission = None
    fut_winrate = None
    if fut.has_keys() and st.get("start"):
        sms = int(datetime.fromisoformat(str(st["start"])).timestamp() * 1000)
        inc = read_income(lambda: fut.income_summary(sms))
        if inc is not None:
            funding = round(_num(inc.get("funding")), 2)            # carry income (the edge)
            venue_realized = _num(inc.get("realized_pnl"))          # exact futures realized
            fut_commission = abs(_num(inc.get("commission")))       # the fee bill, for the recon
            realized = round(_num(inc.get("funding")) + venue_realized
                             + _num(inc.get("commission")), 2)
            _nw, _nl = _num(inc.get("n_wins")), _num(inc.get("n_losses"))
            fut_winrate = round(100.0 * _nw / (_nw + _nl), 1) if (_nw + _nl) > 0 else None
    spot_usdt = round(spot.usdt_balance(), 2) if spot.has_keys() else 0.0

    # spot side = OPEN long-leg marks + realized of CLOSED spot legs. DERIVE the realized from
    # exchange ground truth (deduped trade-log basis - venue futures realized) rather than trusting
    # the stored accumulator, so a stale/crashed executor can NEVER fabricate a dashboard loss
    # (the 2026-07-10 phantom). Falls back to the stored value only if the venue realized is absent.
    if venue_realized is not None:
        spot_realized = derive_spot_realized(venue_realized, _load(_TRADES) or [])
    else:
        spot_realized = _num(st.get("realized_spot_pnl"))
    spot_pnl = round(_num(cc.get("spot_leg_pnl")) + spot_realized, 2)
    fut_pnl = round(fut_eq - fut_start_real, 2)              # futures leg net (short + funding)
    carries = cc.get("carries", []) if isinstance(cc.get("carries"), list) else []
    avg_f = (sum(_num(c.get("funding_8h")) for c in carries) / len(carries)) if carries else 0.0

    # perp L/S book -- PAPER (shadow), combined into the molded account on the same $BASE. Kept as
    # paper (marked from the forward shadow) so its directional risk NEVER touches the delta-neutral
    # carry account -- the "perp + cash-carry combined" book, testnet-only, honestly labelled.
    shadow = _load(_SHADOW)
    perp_days = int(_num(shadow.get("forward_days")))
    perp_active = perp_days > 0
    perp_net = round(_BASE * _num(shadow.get("forward_cum_return")), 2) if perp_active else 0.0
    perp_book = round(_BASE + perp_net, 2)

    # TREND book -- PAPER CANDIDATE (passed in-sample gauntlet, forward day N/90, not yet valid).
    # Auto-added to the molded per the promotion policy; marked paper from its own forward shadow so
    # its directional risk never touches real accounts. Real capital only after 90d + human OK.
    trend_sh = _load(_TREND)
    trend_rg = _load(_TREND_RG)
    trend_days = int(_num(trend_sh.get("forward_days")))
    trend_active = trend_days > 0
    trend_net = round(_BASE * _num(trend_sh.get("forward_cum_return")), 2) if trend_active else 0.0
    trend_book = round(_BASE + trend_net, 2)

    # equalised rebase: each leg/book starts at $BASE. TREND IS EXCLUDED from the molded totals
    # (decision 2026-07-09, see ledger): a day-5 unvalidated candidate lives ONLY in its own 90d
    # shadow + its own card so it cannot distort combined P&L; it re-enters only if it validates.
    fut_book = round(_BASE + fut_pnl, 2)
    spot_book = round(_BASE + spot_pnl, 2)
    n_books = 2 + (1 if perp_active else 0)
    m_start = round(n_books * _BASE, 2)
    m_eq = round(fut_book + spot_book + (perp_book if perp_active else 0.0), 2)
    net = round(fut_pnl + spot_pnl + perp_net, 2)     # carry (real) + perp (paper); NO trend
    # SAME NEIGHBOUR, SAME LEAK (2026-08-05). This book inherits the executor's inception by
    # design (R0322 pinned them together so one deposit could not split the desk into two published
    # truths) -- and therefore it inherited the R0322 defect too: `effective_start_equity` is the
    # RUIN RAIL's inception, which a signed re-base moves, so `fut_pnl` above carries every dollar
    # of that re-base as fabricated profit. Pinning two books to one number made them agree; it did
    # not make them right. The cross-check below is what makes the shared number auditable.
    recon = reconcile_futures_leg(
        equity_delta=fut_pnl, venue_realized=venue_realized, funding=funding,
        commission=fut_commission, unrealized=fut_unrl,
        rebase_usd=round(_num(st.get("start_futures_equity"), fut_eq) - fut_start_real, 2))
    # standing carry-leak alarm: is the funding harvest surviving, or is the hedge bleeding it?
    bleed = carry_bleed_report(funding=funding, spot_pnl=spot_pnl, fut_pnl=fut_pnl,
                               open_legs=len(carries), recon=recon)
    net_reported = (net if recon.reporting_pnl is None
                    else round(recon.reporting_pnl + spot_pnl + perp_net, 2))

    # gross P&L for the COMBINED book: split each book's net P&L by sign -> total gains vs total
    # losses. They sum EXACTLY to the molded net.
    _books = [fut_pnl, spot_pnl] + ([perp_net] if perp_active else [])
    gross_profit = round(sum(b for b in _books if b > 0), 2)
    gross_loss = round(sum(b for b in _books if b < 0), 2)
    # maintain curves for daily / monthly / drawdown
    now = datetime.now(tz=UTC).isoformat()
    cs = _load(_CURVE)
    if abs(_num(cs.get("start"), -1) - m_start) > 0.01:
        cs = {"start": m_start, "mcurve": [], "fcurve": []}
    mcurve = cs.get("mcurve", [])
    fcurve = cs.get("fcurve", [])
    mcurve.append([now, m_eq])
    fcurve.append([now, fut_book])
    mcurve, fcurve = mcurve[-4000:], fcurve[-4000:]
    peak = max(e for _, e in mcurve) if mcurve else m_eq
    dd = round((m_eq / peak - 1.0) * 100, 2) if peak > 0 else 0.0
    _CURVE.parent.mkdir(parents=True, exist_ok=True)
    _CURVE.write_text(json.dumps({"start": m_start, "mcurve": mcurve, "fcurve": fcurve}), "utf-8")

    # EXPERIMENTAL levered lab (SIMULATED, fresh from inception): _LEV x the go-forward P&L of the
    # real carry (fut+spot legs) + the perp paper. HONEST -- it amplifies LOSSES as well as gains.
    # NOT real orders (no free testnet accounts for a 2nd hedged book) and does NOT touch the real
    # deployed book or its 90-day validation. Fresh clock: starts at 2x $BASE at inception, so the
    # real book's slow accumulated history is NOT dragged in. CAVEAT: a sim cannot model a margin
    # liquidation, so it UNDER-states real-leverage tail risk (a genuine 3x carry can be wiped
    # out by a violent move; this cannot show that).
    _LEV = 3.0
    ls = _load(_LEVLAB)
    if "inception" not in ls:
        ls = {"inception": now, "lev": _LEV, "fut0": fut_pnl, "spot0": spot_pnl,
              "perp0": perp_net, "fund0": funding, "curve": []}
    lev = _num(ls.get("lev"), _LEV)
    lfut = round(lev * (fut_pnl - _num(ls.get("fut0"))), 2)      # 3x each book's go-forward P&L
    lspot = round(lev * (spot_pnl - _num(ls.get("spot0"))), 2)
    lperp = round(lev * (perp_net - _num(ls.get("perp0"))), 2)
    # Self-heal a baseline seeded during a venue outage: anchoring the levered harvest to a
    # fabricated zero would overstate it forever, so an unset fund0 is adopted on first real read
    # rather than defaulted to 0.0.
    if ls.get("fund0") is None and funding is not None:
        ls["fund0"] = funding
    f0 = ls.get("fund0")
    lfund = (round(lev * (funding - f0), 2)
             if funding is not None and f0 is not None else None)
    lev_net = round(lfut + lspot + lperp, 2)                     # NO trend (own shadow only)
    lev_start = round(3 * _BASE, 2)                              # 3 books x $5k, fresh
    lev_eq = round(lev_start + lev_net, 2)
    lgp = round(sum(x for x in (lfut, lspot, lperp) if x > 0), 2)
    lgl = round(sum(x for x in (lfut, lspot, lperp) if x < 0), 2)
    lcurve = ls.get("curve", [])
    lcurve.append([now, lev_eq])
    lcurve = lcurve[-4000:]
    ls["curve"] = lcurve
    _LEVLAB.write_text(json.dumps(ls), "utf-8")
    lpeak = max(e for _, e in lcurve) if lcurve else lev_eq
    ldd = round((lev_eq / lpeak - 1.0) * 100, 2) if lpeak > 0 else 0.0
    lev_step = max(1, len(lcurve) // 240)
    lev_chart = lcurve[::lev_step]
    if lcurve and lev_chart[-1] is not lcurve[-1]:
        lev_chart.append(lcurve[-1])

    # single deployed-portfolio object -> day-count, winrate, deployed Sharpe, portfolio.json.
    # Combined book: cash_and_carry is REAL testnet capital; perp_ls is PAPER (shadow) -- labelled.
    port = LivePortfolio.load(_BASE, fut=fut, spot=spot)
    pub = port.to_public()
    pub["deployed"]["sleeves"] = (["cash_and_carry (real)"]
                                  + (["perp_ls (paper)"] if perp_active else []))
    pub["deployed"]["start_capital"] = m_start
    pub["deployed"]["equity"] = m_eq
    pub["deployed"]["net_pnl"] = net
    pub["deployed"]["return_pct"] = round(net / m_start * 100, 3) if m_start else 0.0
    pub["deployed"]["perp_paper_net"] = perp_net
    _PORT.write_text(json.dumps(pub, indent=2), "utf-8")
    trades = _load(_TRADES)
    trade_hist = list(reversed(trades if isinstance(trades, list) else []))[:40]
    # downsample the curve for the chart (cap points, keep first + last)
    step = max(1, len(mcurve) // 240)
    chart = mcurve[::step]
    if mcurve and chart[-1] is not mcurve[-1]:
        chart.append(mcurve[-1])

    out = {
        "updated": now,
        "molded": {
            # Honest net (venue income ledger) under the headline name; see the executor's note --
            # the equity-delta reading keeps its own key so the disagreement stays auditable.
            "start": m_start, "equity": m_eq, "net_pnl": net_reported,
            "net_pnl_equity_delta": net,
            "return_pct": round(net_reported / m_start * 100, 3) if m_start else 0.0,
            "daily_pct": _pct_ago(mcurve, m_eq, 24), "monthly_pct": _pct_ago(mcurve, m_eq, 720),
            "unrealized": round(fut_unrl + _num(cc.get("spot_leg_pnl")), 2), "realized": realized,
            "gross_profit": gross_profit, "gross_loss": gross_loss,
            "max_dd_pct": dd, "funding": funding,
            "non_funding_pnl": bleed.non_funding_pnl,
            "harvest_eaten_frac": bleed.harvest_eaten_frac,
            "bleed_alert": bleed.alert, "bleed_verdict": bleed.verdict,
            # Both readings of the futures leg, and the honest net beside the published one.
            "fut_leg_reconciliation": recon.model_dump(),
            "run_rate_apr_pct": round(avg_f * 3 * 365 * 100, 1),
            "days_live": port.days_live, "winrate_pct": port.winrate,
            "n_closed_trades": port.n_closed, "deployed_sharpe": port.deployed_sharpe,
            "live_sleeves": list(port.LIVE_SLEEVES) + (["perp_ls"] if perp_active else []),
        },
        "perp": {"start": _BASE, "equity": perp_book, "net_pnl": perp_net,
                 "return_pct": round(perp_net / _BASE * 100, 3), "days": perp_days,
                 "active": perp_active, "winrate": _curve_winrate(shadow), "winrate_kind": "daily",
                 "kind": "paper (shadow) — combined, not real orders"},
        "trend": {"start": _BASE, "equity": trend_book, "net_pnl": trend_net,
                  "return_pct": round(trend_net / _BASE * 100, 3), "days": trend_days,
                  "active": trend_active, "winrate": _curve_winrate(trend_sh),
                  "winrate_kind": "daily",
                  "kind": ("paper CANDIDATE — own 90d shadow ONLY; excluded from molded + 3x "
                           "totals until it validates")},
        "trend_regime": {
            "net_pnl": round(_BASE * _num(trend_rg.get("forward_cum_return")), 2),
            "days": int(_num(trend_rg.get("forward_days"))),
            "kind": "pre-registered challenger: same trend, flat in weak-trend regimes"},
        "levered_lab": {
            "leverage": lev, "start": lev_start, "equity": lev_eq, "net_pnl": lev_net,
            "return_pct": round(lev_net / lev_start * 100, 3) if lev_start else 0.0,
            "fut_net": lfut, "spot_net": lspot, "perp_net": lperp,
            "funding": lfund, "gross_profit": lgp, "gross_loss": lgl, "max_dd_pct": ldd,
            "winrate_pct": port.winrate,
            "daily_pct": _pct_ago(lcurve, lev_eq, 24), "monthly_pct": _pct_ago(lcurve, lev_eq, 720),
            "inception": ls.get("inception"), "curve": lev_chart,
            "kind": f"SIMULATED {lev:g}x · fresh · NOT real orders · no liquidation modelled"},
        "curve": chart,
        "trades": trade_hist,
        "futures": {
            "balance": fut_eq, "start": _BASE, "equity": fut_book, "net_pnl": fut_pnl,
            "return_pct": round(fut_pnl / _BASE * 100, 3),
            "daily_pct": _pct_ago(fcurve, fut_book, 24),
            "monthly_pct": _pct_ago(fcurve, fut_book, 720),
            "unrealized": fut_unrl, "realized": realized, "funding": funding,
            "winrate": fut_winrate, "winrate_kind": "trade",
        },
        "spot": {"usdt": spot_usdt, "start": _BASE, "equity": spot_book, "net_pnl": spot_pnl,
                 "return_pct": round(spot_pnl / _BASE * 100, 3),
                 "winrate": None, "winrate_kind": "n/a (no spot trade history via API)"},
        "n_carries": len(carries),
        "carries": [{"symbol": c.get("symbol"), "funding_8h": _num(c.get("funding_8h"))}
                    for c in carries],
        "note": ("Combined book (testnet), $5,000 per leg/book. Cash-carry = REAL orders: "
                 "futures short legs + spot long legs, delta-neutral (net = funding harvested "
                 "8-hourly). Perp L/S = PAPER (shadow-marked) so its directional risk never hits "
                 "the carry account. Molded = carry (real) + perp (paper)."),
    }
    # VENUE-TRUTH EQUITY (2026-07-16 incident: mark-based books recorded -$55 while venue cash
    # fell 41% from HWM -- the dead-man's independent measure was invisible outside its state
    # file). Surface it beside the molded numbers so mark-vs-venue divergence is always on the
    # dashboard and in audit briefs. Read-only: the rail's state is never written from here.
    try:
        dm = json.loads(Path("data/deadman_state.json").read_text("utf-8"))
        hw = float(dm.get("high_water", 0.0))
        out["venue_truth"] = {
            "equity": round(float(dm.get("last_eq", 0.0)), 2), "high_water": round(hw, 2),
            "fire_line": round(0.65 * hw, 2), "breaches": int(dm.get("breaches", 0)),
            "fired": bool(dm.get("fired", False)),
            "kind": ("dead-man measure: fut margin + tracked spot legs + USDT delta -- venue "
                     "ground truth, immune to mark-based accounting blindness"),
        }
        Path("web/venue_equity.json").write_text(
            json.dumps({"updated": now, **out["venue_truth"]}, indent=2), "utf-8")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"MOLDED ${m_eq} (start ${m_start}, net {net:+.2f}) | carry: fut ${fut_eq} "
          f"spot ${spot_usdt} | perp(paper) ${perp_book} active={perp_active}")


if __name__ == "__main__":
    main()
