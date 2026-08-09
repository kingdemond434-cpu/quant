"""DAILY EXECUTION ECONOMICS -- what the desk actually netted, and where the rest went.

THE GAP THIS CLOSES. Every piece of this report already existed as an instrument and none of them
were ever added up:

    run_trade_forensics.py            hold-class economics + FUTURES commission attribution
                                      ("spot-leg fees not visible -> LOWER BOUND", R0027)
    libs/execution/carry_accounting   the UNEXPLAINED residual, whose docstring says it
                                      "deserves a page" -- nothing paged on it
    run_reality_gap.py::_cost_link    modelled-vs-realised cost, desk-wide, 1.5x GAP / 3.0x BREAK
    fill_quality_monitor.py           maker share and fee concentration
    run_cashcarry_executor::_net_bps  the funding-minus-round-trip the entry gate ranks on

So the desk could tell you its maker share, its hold-class bleed and its modelled cost -- and could
not tell you what one day of trading NETTED. The 2026-07 fee fire ($1,750.65 of venue commission
against a logged aggregate net of +$0.16) was inside all five instruments and named by none. This
script asks the one question none of them ask, for the trailing DAY and the trailing WEEK:

  1. NET APR REALISED, decomposed  gross funding - futures comm - SPOT comm - slippage - funding paid
  2. CHURN                         round trips/position/day, hold vs the gate's own minimum
  3. COST-MODEL DRIFT              realised round-trip bps vs data/cost_model.json, per symbol
  4. THE RESIDUAL                  money the desk cannot explain, with a DEFECT bar
  5. ACTIONS                       ranked by recoverable bps, each naming its specific fix

HONESTY IS THE FEATURE. Every artifact below is runtime state that lives on the VPS and is ABSENT
from a fresh checkout. An absent input reads NOT-READABLE-HERE. It never reads 0.0. A zero in an
execution report is a claim that money did not move, and this script is built so that claim cannot
be made by accident: the arithmetic lives in `libs/execution/economics`, where every quantity is
`float | None` and `None` has exactly one rendering.

NO THRESHOLD IS MINTED. `_COST_BAND`/`_COST_BREAK` are READ out of scripts/run_reality_gap.py;
`_MIN_HOLD_H`, `_DEFAULT_RT_BPS` and `_MIN_FILLS_FOR_REALISED` out of
scripts/run_cashcarry_executor.py; the residual's defect bar out of `carry_bleed_report`'s own
`alert_frac`. If any of them cannot be read, the section that needed it reads NOT-READABLE-HERE
rather than falling back to a plausible copy. READ-ONLY throughout: no orders, no state writes,
no executor edits -- it publishes data/execution_economics.json and prints a table.

EXIT: 0 when the report is clean OR honestly unmeasured (missing inputs are not a crash);
1 on an actionable defect class (DEFECT residual / CHURN / cost-model BREAK), so a bleeding day
leaves a non-zero trace in the cron log instead of a quiet success.

    python3 scripts/run_execution_economics.py [--json] [--self-test]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                     # runnable as a script, no packaging step
    sys.path.insert(0, str(ROOT))

from libs.execution import carry_accounting, economics  # noqa: E402  (path bootstrap first)
from libs.execution.economics import (  # noqa: E402
    MEASURED,
    NOT_READABLE,
    Action,
    Term,
    unmeasured_term,
)

# ---- inputs, all VPS-side runtime state -------------------------------------------------------
TAPE = ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
TRADES = ROOT / "data/cashcarry_trades.json"
LIVE = ROOT / "web/cashcarry_live.json"
FORENSICS = ROOT / "web/trade_forensics.json"
COST_MODEL = ROOT / "data/cost_model.json"
OUT = ROOT / "data/execution_economics.json"

# ---- constants READ from their owners, never re-declared ---------------------------------------
# See economics.read_source_constant for why this is a source read and not an import: the executor
# is the order-placing module, and a reporting organ must not be able to reach the order path.
REALITY_GAP_SRC = ROOT / "scripts/run_reality_gap.py"
EXECUTOR_SRC = ROOT / "scripts/run_cashcarry_executor.py"
RECONCILIATION_SRC = ROOT / "scripts/run_deadman_reconciliation.py"

COST_BAND = economics.read_source_constant(REALITY_GAP_SRC, "_COST_BAND")
COST_BREAK = economics.read_source_constant(REALITY_GAP_SRC, "_COST_BREAK")
MIN_HOLD_H = economics.read_source_constant(EXECUTOR_SRC, "_MIN_HOLD_H")
DEFAULT_RT_BPS = economics.read_source_constant(EXECUTOR_SRC, "_DEFAULT_RT_BPS")
MIN_FILLS_FOR_REALISED = economics.read_source_constant(EXECUTOR_SRC, "_MIN_FILLS_FOR_REALISED")
# The venue caps spot myTrades spans; run_deadman_reconciliation already discovered and paginated
# that cap (a wider window returns a SILENTLY truncated page, not an error), so its chunk size is
# read rather than guessed a second time.
SPOT_CHUNK_MS = economics.read_source_constant(RECONCILIATION_SRC, "_SPOT_CHUNK_MS")
BUFFER_MS = economics.read_source_constant(RECONCILIATION_SRC, "_BUFFER_MS")

WINDOWS: tuple[tuple[str, float], ...] = (("trailing_day", 1.0), ("trailing_week", 7.0))
#: Commission assets `run_deadman_reconciliation` can value in USDT today. A fee billed in any
#: other asset is COUNTED but not valued -- it makes the spot term a LOWER BOUND, never a zero.
USDT_ASSETS = ("USDT", "BUSD")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------------------------
# Tape
# ---------------------------------------------------------------------------------------------
def _load_rows() -> tuple[list[dict[str, Any]], str]:
    """Trade events + the SOURCE they came from. Prefers the permanent tape over the hot buffer.

    `data/cashcarry_trades.json` is a rolling `log[-500:]`; the append-only tape is the same
    records kept forever (libs/execution/execution_tape). For a 1-day and 7-day window either is
    usually enough, but the tape cannot silently lose the tail of a busy week, and which one was
    read is published so a reader can tell a thin week from a truncated one.
    """
    try:
        from libs.execution import execution_tape
        taped = execution_tape.read(path=TAPE)
    except Exception:                              # observer -- an unreadable tape is not a crash
        taped = []
    if taped:
        return [r for r in taped if isinstance(r, dict)], f"execution tape ({len(taped)} records)"
    rolling = _read_json(TRADES)
    if isinstance(rolling, list):
        rows = [r for r in rolling if isinstance(r, dict)]
        return rows, f"rolling buffer data/cashcarry_trades.json ({len(rows)} records, capped 500)"
    return [], NOT_READABLE


# ---------------------------------------------------------------------------------------------
# Venue reads -- futures income (funding split + commission) and SPOT commission (R0027)
# ---------------------------------------------------------------------------------------------
def _futures_income(since_ms: int) -> tuple[list[dict[str, Any]] | None, dict[str, float] | None]:
    """(raw income rows, income_summary) since `since_ms`. Either half may be None.

    TWO READS OF ONE LEDGER, ON PURPOSE. `income_summary` is the public, audited aggregate and is
    what the executor itself trusts -- but it SUMS SIGNED FUNDING_FEE rows, so it publishes net
    funding and cannot answer "how much did we capture" separately from "how much did we pay".
    The row-level split needs `_income_rows`, the same paginated reader `commission_events` calls
    (a direct limit=1000 call understated commission ~4.4x on 2026-07-26, so this is the only
    sanctioned path). It is module-private and may therefore fail on its own; when it does, the
    split reads NOT-READABLE-HERE and the aggregate still carries the harvest. Losing the split
    must not cost the desk the net.
    """
    rows: list[dict[str, Any]] | None = None
    summary: dict[str, float] | None = None
    try:
        from libs.execution import binance_testnet as fut
        if not fut.has_keys():
            return None, None
        summary = carry_accounting.read_income(lambda: fut.income_summary(since_ms))
        try:
            rows = list(fut._income_rows(since_ms))
        except Exception:
            rows = None
    except Exception:
        return rows, summary
    return rows, summary


def _income_split(rows: list[dict[str, Any]] | None, start_ms: int,
                  end_ms: int) -> tuple[float | None, float | None, float | None]:
    """(gross funding captured, funding paid, commission) in [start_ms, end_ms], POSITIVE = PAID.

    Splits the FUNDING_FEE stream by sign, which is the whole point: a carry book that captured
    $400 and paid $380 is a different desk from one that captured $20 and paid nothing, and the
    netted figure calls them identical.
    """
    if rows is None:
        return None, None, None
    captured = paid = commission = 0.0
    for r in rows:
        try:
            when = int(r.get("time") or 0)
            amount = float(r.get("income") or 0.0)
        except (TypeError, ValueError):
            continue
        if not (start_ms <= when <= end_ms):
            continue
        kind = r.get("incomeType")
        if kind == "FUNDING_FEE":
            if amount >= 0:
                captured += amount
            else:
                paid += -amount
        elif kind == "COMMISSION":
            commission += abs(amount)
    return captured, paid, commission


def _spot_fills(symbols: list[str], start_ms: int, end_ms: int) -> dict[str, Any] | None:
    """Per-symbol spot myTrades across the whole window, or None when the venue cannot be read.

    THIS IS R0027, WIRED. `run_trade_forensics._fee_attribution` reads only
    `binance_testnet.commission_events` -- the FUTURES income ledger -- and says so in its own
    scope string: "spot-leg fees not visible -> LOWER BOUND". Meanwhile
    `run_deadman_reconciliation.py:108-110` has been summing `commission` per spot fill from
    `binance_spot_testnet.my_trades` since 2026-07-19. The building block was one import away; this
    is that import, so the round trip is finally billed on BOTH legs.

    THE READ THAT LIES BY OMISSION. `binance_spot_testnet.my_trades` swallows every exception and
    returns `[]`, so "no fills" and "the read failed" are the same value. That ambiguity is
    resolved here rather than published: zero fills against symbols the tape says were traded is
    treated as a FAILED READ, not as free execution. Coverage (symbols that returned fills /
    symbols queried) travels with the number so a partial read is a labelled LOWER BOUND.
    """
    if not symbols:
        return None
    try:
        from libs.execution import binance_spot_testnet as spot
        if not spot.has_keys():
            return None
    except Exception:
        return None
    chunk = int(SPOT_CHUNK_MS) if SPOT_CHUNK_MS is not None else 20 * 3600 * 1000
    pad = int(BUFFER_MS) if BUFFER_MS is not None else 90_000
    per_symbol: dict[str, list[dict[str, Any]]] = {}
    for sym in symbols:
        seen: dict[str, dict[str, Any]] = {}
        cursor = start_ms - pad
        end = end_ms + pad
        while cursor < end:                        # page past the venue's span cap (silent trunc)
            stop = min(cursor + chunk, end)
            try:
                for fill in spot.my_trades(sym, cursor, stop):
                    if isinstance(fill, dict):
                        seen[str(fill.get("id"))] = fill
            except Exception:
                pass                               # one bad chunk lowers coverage, never crashes
            cursor = stop
        per_symbol[sym] = list(seen.values())
    return per_symbol


def _spot_commission_term(per_symbol: dict[str, Any] | None, start_ms: int, end_ms: int,
                          n_trips: int) -> Term:
    """The spot leg's commission bill for this window -- the R0027 hole, measured or refused."""
    source = ("binance_spot_testnet.my_trades commission per fill "
              "(the sum run_deadman_reconciliation.py:108-110 already performs)")
    if per_symbol is None:
        return unmeasured_term(
            "spot_commission", source,
            ("spot venue not readable here (no keys / no network / no symbols in window) -- "
             "R0027's hole stays open for this run. NOT a zero: an unread fee is not a free one"))
    valued = 0.0
    n_fills = 0
    other_asset = 0
    covered = 0
    for _sym, fills in per_symbol.items():
        hit = False
        for fill in fills:
            try:
                when = int(fill.get("time") or 0)
            except (TypeError, ValueError):
                continue
            if not (start_ms <= when <= end_ms):
                continue
            hit = True
            n_fills += 1
            try:
                amount = abs(float(fill.get("commission") or 0.0))
            except (TypeError, ValueError):
                continue
            if str(fill.get("commissionAsset")) in USDT_ASSETS:
                valued += amount
            elif amount > 0.0:
                other_asset += 1
        covered += 1 if hit else 0
    queried = len(per_symbol)
    coverage = (covered / queried) if queried else None
    if n_fills == 0 and n_trips > 0:
        return unmeasured_term(
            "spot_commission", source,
            (f"zero spot fills returned for {queried} symbol(s) that the tape says closed "
             f"{n_trips} round trip(s) in this window. my_trades swallows its errors and returns "
             "[], so this is a FAILED READ, not $0.00 of spot fees"))
    bound = economics.EXACT
    note = (f"{n_fills} spot fill(s) across {covered}/{queried} symbol(s); R0027 records the "
            "measured spot commission on this venue as $0.00 per reconciled leg -- a real zero "
            "backed by fills, which is why the fill count is published beside it")
    if n_fills == 0:
        # No fills AND no closed round trips: the venue was asked and returned nothing to bill.
        # That is a measured $0.00, distinguishable from the failed-read branch above only
        # because there was no trading in the window for a fee to have attached to.
        bound = economics.LOWER_BOUND
        note = (f"no spot fills and no round trips closed in this window across {queried} "
                "symbol(s) -- $0.00 is what the venue returned, not what this reader assumed")
    elif other_asset:
        bound = economics.LOWER_BOUND
        note = (f"{n_fills} spot fill(s); {other_asset} fill(s) billed in an asset outside "
                f"{USDT_ASSETS} are COUNTED but not valued in USDT -> LOWER BOUND")
    elif coverage is not None and coverage < 1.0:
        bound = economics.LOWER_BOUND
        note = (f"{n_fills} spot fill(s) but only {covered}/{queried} symbol(s) returned any -- "
                "the silent ones are unbilled here -> LOWER BOUND")
    return Term(name="spot_commission", usd=valued, status=MEASURED, source=source,
                bound=bound, coverage=coverage, note=note)


# ---------------------------------------------------------------------------------------------
# Assembly of one window
# ---------------------------------------------------------------------------------------------
def _build_window(label: str, days: float, now: datetime, rows: list[dict[str, Any]],
                  rows_source: str, income_rows: list[dict[str, Any]] | None,
                  income_summary: dict[str, float] | None, summary_covers_window: bool,
                  spot_fills: dict[str, Any] | None, deployed_now: float | None,
                  cost_model: Any) -> economics.WindowReport:
    start, end = economics.window_bounds(now, days)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    trips = economics.in_window(economics.parse_trips(rows), start, end)

    captured, paid, commission = _income_split(income_rows, start_ms, end_ms)
    income_src = "binance_testnet._income_rows FUNDING_FEE (paginated income ledger)"
    gross = (Term("gross_funding_captured", captured, MEASURED, income_src,
                  note="positive FUNDING_FEE rows in the window")
             if captured is not None
             else unmeasured_term("gross_funding_captured", income_src,
                                  "futures income ledger not readable here"))
    paid_term = (Term("funding_paid", paid, MEASURED, income_src,
                      note="negative FUNDING_FEE rows, sign-flipped to positive-means-paid")
                 if paid is not None
                 else unmeasured_term("funding_paid", income_src,
                                      "futures income ledger not readable here"))
    comm_src = "binance_testnet._income_rows COMMISSION (paginated income ledger)"
    fut_comm = (Term("futures_commission", commission, MEASURED, comm_src,
                     note="COMMISSION rows -- the venue's exact FUTURES fee bill (spot is separate)")
                if commission is not None
                else unmeasured_term("futures_commission", comm_src,
                                     "futures income ledger not readable here"))
    # SCOPE DISCIPLINE. `income_summary` is anchored at ONE `since_ms` -- the longest window's
    # start -- so it is window-scoped for that window and for NO OTHER. Serving it to the
    # trailing-day row would publish a WEEK of funding as a DAY's harvest and inflate the day's
    # APR sevenfold; the shorter window therefore reads NOT-READABLE-HERE unless the row-level
    # split (which IS filtered by fill time) supplied the harvest itself.
    summary_src = "binance_testnet.income_summary funding (signed sum)"
    if income_summary is not None and "funding" in income_summary and summary_covers_window:
        net_fund = Term("funding_net", float(income_summary["funding"]), MEASURED, summary_src,
                        note="net of captured and paid; used whole when the row split is absent")
    elif income_summary is not None and "funding" in income_summary:
        net_fund = unmeasured_term(
            "funding_net", summary_src,
            f"income_summary is anchored at the longest window's start, not this {days:g}-day "
            "one -- using it here would report a longer period's harvest as this window's")
    else:
        net_fund = unmeasured_term("funding_net", summary_src,
                                   "venue income read failed (carry_accounting.read_income)")

    slip_usd, slip_cov = economics.slippage_usd(trips)
    slip_src = "cashcarry tape spot_slip_bps + fut_slip_bps x notional (the executor's own _tca)"
    if slip_usd is None:
        slippage = unmeasured_term(
            "slippage_vs_mid", slip_src,
            ("no round trip in this window carries both legs' fill-vs-mid -- "
             f"{len(trips)} trip(s) seen" if trips else "no round trips in this window"))
    else:
        partial = slip_cov is not None and slip_cov < 1.0
        slippage = Term(
            "slippage_vs_mid", slip_usd, MEASURED, slip_src,
            bound=economics.LOWER_BOUND if partial else economics.EXACT, coverage=slip_cov,
            note=("signed, positive means we paid; a favourable fill is a real credit"
                  if not partial else
                  "TCA missing on some trips -- those cost something and are unbilled here"))

    spot_term = _spot_commission_term(spot_fills, start_ms, end_ms, len(trips))

    twa = economics.time_weighted_capital(trips, start, end)
    capital, capital_src = economics.capital_base(twa, deployed_now)

    decomposition = economics.build_decomposition(
        gross_funding=gross, funding_paid=paid_term, futures_commission=fut_comm,
        spot_commission=spot_term, slippage=slippage, funding_net_fallback=net_fund,
        capital_usd=capital, capital_source=capital_src, window_days=days)

    churn: list[economics.ChurnRow] = []
    if MIN_HOLD_H is not None and DEFAULT_RT_BPS is not None:
        churn = economics.churn_report(rows, trips, min_hold_h=MIN_HOLD_H, window_days=days,
                                       default_rt_bps=DEFAULT_RT_BPS)
    drift: list[economics.DriftRow] = []
    if COST_BAND is not None and COST_BREAK is not None and MIN_FILLS_FOR_REALISED is not None:
        drift = economics.cost_drift(trips, cost_model, band=COST_BAND, break_at=COST_BREAK,
                                     min_n=int(MIN_FILLS_FOR_REALISED))

    return economics.WindowReport(
        label=label, start=start, end=end, days=days, decomposition=decomposition,
        churn=churn, drift=drift, n_trips=len(trips),
        trips_source=rows_source if rows else NOT_READABLE)


# ---------------------------------------------------------------------------------------------
# The action list
# ---------------------------------------------------------------------------------------------
def _actions(day: economics.WindowReport, week: economics.WindowReport,
             residual: economics.ResidualReport, forensics: Any) -> list[Action]:
    """Ranked recoverable bps, each naming the fix that recovers it. Blind spots ride along
    UNQUANTIFIED -- an unmeasured cost is not a small one, and dropping it would make the
    ranking above it a lie by omission."""
    out: list[Action] = []

    for row in sorted(week.churn, key=lambda c: -(c.churn_cost_bps or 0.0)):
        if row.verdict == "CHURN" and row.churn_cost_bps is not None:
            out.append(Action(
                label=f"churn: {row.symbol}",
                bps=row.churn_cost_bps, basis=f"{row.symbol} traded notional, trailing week",
                fix=("hold to the entry gate's own floor: the churn guard "
                     "(run_cashcarry_executor._churn_guard) already blocks rotation-driven closes "
                     f"under {row.min_hold_h:g}h, so a short hold here means a RAIL forced it "
                     "(basis-stop / reconcile / flatten) or funding flipped past _FUNDING_PANIC. "
                     "Find which, on the tape, before touching the guard"),
                evidence=row.why))

    for row in sorted(week.drift, key=lambda d: -(d.ratio or 0.0)):
        if row.verdict in ("GAP", "BREAK") and row.realised_bps is not None \
                and row.modelled_bps is not None:
            out.append(Action(
                label=f"cost-model drift ({row.verdict}): {row.symbol}",
                bps=row.realised_bps - row.modelled_bps,
                basis=f"{row.symbol} per round trip, realised minus modelled",
                fix=("re-run scripts/run_cost_model.py for this symbol; the executor's _rt_bps "
                     "already floors the model with realised cost (max, never average), so the "
                     "gate is protected -- the DRIFT is the finding, and a BREAK means the "
                     "modelled number cannot describe this book at all"),
                evidence=row.detail))

    if residual.verdict == "DEFECT" and residual.residual_usd is not None:
        base = week.decomposition.capital_usd
        out.append(Action(
            label="UNEXPLAINED RESIDUAL",
            bps=(1e4 * abs(residual.residual_usd) / base) if base is not None and base > 0
            else None,
            basis="deployed capital" if base else "size unknown -- no capital base readable",
            fix=("attribute it: reconcile spot vs perp quantity per symbol "
                 "(scripts/hedge_integrity.py), then run scripts/run_deadman_reconciliation.py "
                 "to map the gap onto raw venue myTrades/income records. carry_accounting says "
                 "the residual absorbs SPOT commission, slippage and hedge-drift incidents -- "
                 "the first of those is now measured here, so what is left is the other two"),
            evidence=residual.why))

    if day.decomposition.net_usd is None:
        out.append(Action(
            label="THE DAY'S NET IS UNMEASURED",
            bps=None, status="UNQUANTIFIED", basis="unknown",
            fix=("restore the inputs this report reads: the funding harvest comes from the "
                 "futures income ledger (needs venue keys), the trips from the execution tape. "
                 "A desk that cannot state yesterday's net cannot be said to be monitoring "
                 "execution at all"),
            evidence=f"unmeasured terms: {', '.join(day.decomposition.unmeasured_terms) or 'all'}"))

    bounded = week.decomposition.net_usd is not None
    for term in week.decomposition.terms:
        if not term.measured:
            out.append(Action(
                label=f"blind term: {term.name}",
                bps=None, status="UNQUANTIFIED", basis="unknown",
                fix=(f"{term.name} is not readable, so the published net is an UPPER BOUND -- "
                     "close the read before trusting any APR on this page" if bounded else
                     f"{term.name} is not readable; with the harvest itself unread there is no "
                     "net to bound. Close this read first"),
                evidence=term.note or term.source))

    maker = forensics.get("maker_fill") if isinstance(forensics, dict) else None
    if isinstance(maker, dict):
        share, target = maker.get("maker_share"), maker.get("target")
        # BOTH legs' fees, now that the spot leg is measured (R0027) -- a maker-conversion estimate
        # built on the futures bill alone would understate its own prize.
        fee_terms = [t for t in week.decomposition.terms
                     if t.name in ("futures_commission", "spot_commission")
                     and t.measured and t.usd is not None]
        fee_bill = sum(t.usd or 0.0 for t in fee_terms)
        base = week.decomposition.capital_usd
        if isinstance(share, (int, float)) and not isinstance(share, bool) \
                and isinstance(target, (int, float)) and not isinstance(target, bool) \
                and share < target and fee_terms and fee_bill > 0.0 \
                and base is not None and base > 0:
            # First-order ESTIMATE, labelled: the taker shortfall against the desk's own target,
            # applied to the fee bill actually paid. The target is READ from the forensics
            # artifact, not restated here.
            legs = " + ".join(t.name for t in fee_terms)
            out.append(Action(
                label="maker conversion shortfall (ESTIMATE)",
                bps=1e4 * fee_bill * (float(target) - float(share)) / base,
                basis=f"deployed capital; = ({legs}) x (target - actual) maker share",
                fix=("raise maker share toward the desk's own target -- patient-maker opens are "
                     "shipped; scripts/fill_quality_monitor.py owns the verification loop and "
                     "reports STALLED when the fix did not move its metric"),
                evidence=(f"web/trade_forensics.json maker_share={share} target={target} "
                          f"over {maker.get('n_legs')} legs")))

    return economics.rank_actions(out)


# ---------------------------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------------------------
def _cell(value: float | None, fmt: str = "{:>12,.2f}") -> str:
    return f"{NOT_READABLE:>16}" if value is None else fmt.format(value).rjust(16)


def _print(report: dict[str, Any]) -> None:
    print("=" * 96)
    print(f"DAILY EXECUTION ECONOMICS  --  {report['generated']}  --  {report['status']}")
    print("=" * 96)
    for window in report["windows"]:
        dec = window["net_apr"]
        print(f"\n[{window['window']}]  {window['n_round_trips']} round trip(s)   "
              f"source: {window['trips_source']}")
        print(f"  {'term':<26}{'usd':>16}  {'status':<11}{'bound':<12}source")
        for term in dec["terms"]:
            usd = term["usd"]
            print(f"  {term['term']:<26}{_cell(usd)}  {term['status']:<11}"
                  f"{term['bound']:<12}{term['source'][:40]}")
        print(f"  {'= NET':<26}{_cell(dec['net_usd'])}  {dec['net_status']}")
        print(f"  {'NET APR':<26}{dec['net_apr_reads']:>16}   on capital "
              f"{dec['capital_usd'] if dec['capital_usd'] is not None else NOT_READABLE} "
              f"({dec['capital_source']})")
        if dec["unmeasured_terms"]:
            tail = ("-> the net above is an UPPER BOUND (an omitted cost only makes it worse)"
                    if dec["net_usd"] is not None else "-> there is no net to bound")
            print(f"  UNMEASURED: {', '.join(dec['unmeasured_terms'])} {tail}")
        print(f"  funding split cross-check: {dec['funding_split_crosscheck']}")

        if window["churn"]:
            print(f"  {'churn':<14}{'rt/day':>8}{'avg hold':>18}{'floor':>8}{'reopen<floor':>14}"
                  f"{'cost bps':>18}  verdict")
            for row in window["churn"]:
                print(f"  {row['symbol']:<14}{row['round_trips_per_day']:>8.2f}"
                      f"{row['avg_hold_reads']!s:>18}{row['gate_min_hold_h']:>8.0f}"
                      f"{row['reopens_inside_min_hold']:>14}"
                      f"{row['churn_cost_reads']!s:>18}  {row['verdict']}")
        else:
            print(f"  churn: {NOT_READABLE} (no closed round trips, or the gate's minimum hold "
                  "could not be read from the executor)")

        drifted = [d for d in window["cost_model_drift"] if d["verdict"] != "NO-DATA"]
        if drifted:
            print(f"  {'drift':<14}{'modelled':>18}{'realised':>18}{'ratio':>8}  verdict")
            for row in drifted:
                print(f"  {row['symbol']:<14}{row['modelled_reads']!s:>18}"
                      f"{row['realised_reads']!s:>18}{row['ratio']!s:>8}  {row['verdict']}")
        else:
            print(f"  cost-model drift: {NOT_READABLE} "
                  f"({len(window['cost_model_drift'])} symbol(s), none with both sides readable)")

    res = report["residual"]
    print(f"\n[residual]  {res['residual_reads']}   verdict {res['verdict']}")
    print(f"  {res['why']}")
    print(f"  scope: {res['scope']}")

    print("\n[actions] ranked by recoverable bps; UNQUANTIFIED items are blind spots, not small")
    if not report["actions"]:
        print(f"  none -- and with a {report['status']} status that is a statement about the "
              "READER, not the book")
    for i, action in enumerate(report["actions"], 1):
        print(f"  {i}. {action['recoverable_reads']!s:>16} bps  {action['action']}")
        print(f"       fix: {action['fix']}")
        print(f"       evidence: {action['evidence']}")


# ---------------------------------------------------------------------------------------------
def _self_test() -> int:
    """Prove the arithmetic on a hand-built book, with no venue and no artifacts.

    Same fixture as tests/execution/test_execution_economics.py: $120.00 captured, $12.00 paid,
    $18.00 futures commission, $6.00 spot commission, $24.00 slippage on $100,000 of deployed
    capital over one day -> net $60.00 -> 21.90% APR.
    """
    src = "self-test fixture"
    dec = economics.build_decomposition(
        gross_funding=Term("gross_funding_captured", 120.0, MEASURED, src),
        funding_paid=Term("funding_paid", 12.0, MEASURED, src),
        futures_commission=Term("futures_commission", 18.0, MEASURED, src),
        spot_commission=Term("spot_commission", 6.0, MEASURED, src),
        slippage=Term("slippage_vs_mid", 24.0, MEASURED, src),
        funding_net_fallback=Term("funding_net", 108.0, MEASURED, src),
        capital_usd=100_000.0, capital_source=src, window_days=1.0)
    print("=== EXECUTION ECONOMICS (self-test) ===")
    print(f"  net = 120.00 - 18.00 - 6.00 - 24.00 - 12.00 = {dec.net_usd:.2f} ({dec.net_status})")
    print(f"  APR = {dec.net_apr_pct:.2f}%   cross-check: {dec.funding_split_crosscheck}")
    blind = economics.build_decomposition(
        gross_funding=unmeasured_term("gross_funding_captured", src, "absent"),
        funding_paid=unmeasured_term("funding_paid", src, "absent"),
        futures_commission=unmeasured_term("futures_commission", src, "absent"),
        spot_commission=unmeasured_term("spot_commission", src, "absent"),
        slippage=unmeasured_term("slippage_vs_mid", src, "absent"),
        funding_net_fallback=unmeasured_term("funding_net", src, "absent"),
        capital_usd=None, capital_source=NOT_READABLE, window_days=1.0)
    print(f"  all-absent book reads: net={blind.as_dict()['net_reads']} "
          f"apr={blind.as_dict()['net_apr_reads']} (never 0.0)")
    ok = (dec.net_usd == 60.0 and blind.net_usd is None
          and blind.as_dict()["net_reads"] == NOT_READABLE)
    print(f"  arithmetic + absence handling: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily execution economics")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    parser.add_argument("--self-test", action="store_true",
                        help="prove the arithmetic with no inputs and no venue")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()

    now = datetime.now(tz=UTC)
    rows, rows_source = _load_rows()
    live = _read_json(LIVE)
    forensics = _read_json(FORENSICS)
    cost_model = _read_json(COST_MODEL)

    longest = max(days for _label, days in WINDOWS)
    week_start, _ = economics.window_bounds(now, longest)
    since_ms = int(week_start.timestamp() * 1000)
    income_rows, income_summary = _futures_income(since_ms)

    # ONE spot fetch for the longest window; each window then filters it by fill time. Paging the
    # venue once per window would double the signed-call count for the same rows.
    trips_all = economics.in_window(economics.parse_trips(rows), week_start, now)
    symbols = sorted({t.symbol for t in trips_all if t.symbol})
    spot_fills = _spot_fills(symbols, since_ms, int(now.timestamp() * 1000))

    deployed_now = None
    if isinstance(live, dict):
        raw = live.get("deployed_notional")
        deployed_now = float(raw) if isinstance(raw, (int, float)) else None

    windows = [_build_window(label, days, now, rows, rows_source, income_rows, income_summary,
                             days == longest, spot_fills, deployed_now, cost_model)
               for label, days in WINDOWS]
    day, week = windows[0], windows[-1]

    leak = live.get("leak_attribution") if isinstance(live, dict) else None
    harvest = live.get("funding_harvested") if isinstance(live, dict) else None
    residual = economics.residual_report(
        leak=leak,
        funding=float(harvest) if isinstance(harvest, (int, float)) else None,
        alert_frac=economics.bleed_alert_frac(),
        scope=("INCEPTION-TO-DATE, not windowed: the executor computes leak_attribution against "
               "its own book start, so this residual is cumulative and does not shrink with a "
               "good day. Read it as a standing balance of unexplained money"))

    status = economics.overall_status(windows, residual)
    report: dict[str, Any] = {
        "generated": now.isoformat(),
        "status": status,
        "law": ("L1.4 reality outranks simulation; carry_accounting: an unexplained residual "
                "deserves a page. Absent input reads NOT-READABLE-HERE, never 0.0"),
        "thresholds_read_not_declared": {
            "cost_gap_band": COST_BAND, "cost_break_band": COST_BREAK,
            "gate_min_hold_h": MIN_HOLD_H, "default_rt_bps": DEFAULT_RT_BPS,
            "min_fills_for_realised": MIN_FILLS_FOR_REALISED,
            "residual_defect_frac_of_harvest": economics.bleed_alert_frac(),
            "sources": {"cost bands": "scripts/run_reality_gap.py",
                        "hold + round-trip": "scripts/run_cashcarry_executor.py",
                        "residual bar": "libs/execution/carry_accounting.carry_bleed_report"},
        },
        "inputs": {
            "trades": rows_source,
            "live_book": "web/cashcarry_live.json" if isinstance(live, dict) else NOT_READABLE,
            "forensics": "web/trade_forensics.json" if isinstance(forensics, dict)
            else NOT_READABLE,
            "cost_model": "data/cost_model.json" if isinstance(cost_model, dict) else NOT_READABLE,
            "futures_income": ("binance_testnet income ledger" if income_rows is not None
                               else NOT_READABLE),
            "spot_fills": ("binance_spot_testnet.my_trades" if spot_fills is not None
                           else NOT_READABLE),
        },
        "windows": [w.as_dict() for w in windows],
        "residual": residual.as_dict(),
        "actions": [a.as_dict() for a in _actions(day, week, residual, forensics)],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        _print(report)
    # `relative_to` is cosmetic and OUT is configurable in tests -- a report organ must never
    # die on its own last print line.
    try:
        where: object = OUT.relative_to(ROOT)
    except ValueError:
        where = OUT
    print(f"\n-> {where}")
    # An actionable defect must leave a non-zero trace in the cron log. Missing inputs must NOT:
    # a checkout with no runtime state is an honest UNMEASURED, not a failure.
    return 1 if status in ("DEFECT", "CHURN", "BREAK") else 0


if __name__ == "__main__":
    raise SystemExit(main())
