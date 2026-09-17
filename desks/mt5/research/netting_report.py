#!/usr/bin/env python3
"""NETTING REPORT -- what the book pays to cross itself, and how many directions it actually spans.

TWO MEASUREMENTS, ONE ARTIFACT, and they are the two halves of the same review finding (R1/R2,
2026-09-17).

1. THE EXECUTION ECONOMY. Forty LIVE sleeves send forty orders. Eight of them are EURCHF, three
   are AUDCAD, four are AUDUSD. Where two sleeves in one symbol point opposite ways the venue is
   crossed twice to arrive at a position the book could have reached without trading: two
   spreads, two commissions, two slippages, two chances of a rejection, for a net change of zero.
   Costs sit INSIDE the growth objective (`docs/GROWTH_GOVERNANCE.md` -- "commission, spread and
   swap are paid on every unit of size; an uncosted optimum sizes a quantity the desk cannot
   buy"), so a round trip that buys no exposure is a straight subtraction from E[log W]. This
   prices that subtraction with the desk's own cost surface, per symbol, per run.

2. THE DIRECTIONAL CEILING. A pair is a DIFFERENCE of two currency factors -- EURUSD is
   `EUR - USD` -- so eighteen pairs drawn from eight currencies span at most SEVEN independent
   directions, and empirically three or four (dollar, carry, commodity bloc, risk appetite). The
   desk's measured effective breadth of 4.879 is therefore not a number with headroom; it is
   pressed against the ceiling of what a pure-FX book can express. The nineteenth cross does not
   buy a bet. `libs/risk/fx_exposure.py` makes that ceiling measurable and this publishes the
   reading beside the netting, because they are the same fact seen twice: a book crossing itself
   at the venue is a book whose sleeves are the same bet.

WHY THIS LANDS FIRST, ALONE. Netting inside the gateway changes per-sleeve FILLS, and per-sleeve
fills are per-sleeve forward evidence -- promotion-firewall ground. So the diagnostic runs, on a
clock, writing what netting WOULD save; the gateway change is principal-gated and separate. A
measurement that publishes before it acts is also the only way to know afterwards whether the
action was worth taking.

NOTHING HERE SIZES, CAPS, VETOES, SHRINKS OR GATES ANYTHING. No number in this artifact reaches
an allocator, a heat budget or an order. The netted target is the sleeves' own arithmetic sum,
never a damped one, and it is checked against exactly the same heat floor and factor caps the
gross book faced -- netting can never be the reason a book is smaller (the principal's standing
order, given three times: NEVER REDUCE AGGRESSIVENESS).

WHAT IS MEASURED AND WHAT IS NOT, kept apart by name (L1.28a). The live registry writes
`"auto_ramp"` into most sleeves' `lot` field, which is not a lot; a symbol can lack a
`volume_step`, an H1 bar file, a contract size or a cost-surface cell. Every one of those is a
NAMED row in `unmeasured` and never a zero, because a zero lot reads exactly like a sleeve that
chose to hold nothing and a zero spread reads exactly like a free trade.

CLOCK. `--dry-run` computes and prints without writing, for a session that wants the number
without touching the artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _entry in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from libs.portfolio.netting import (  # noqa: E402
    NettedTarget,
    SleeveIntent,
    net_intents,
    netting_summary,
)
from libs.risk.errors import RiskError  # noqa: E402
from libs.risk.fx_exposure import (  # noqa: E402
    Position,
    effective_rank,
    exposure_matrix,
    factor_concentration,
    factors_from_registry,
    split_symbol,
)

SOURCE = "netting_report"
SCHEMA = "netting-1"
RULE = ("netting is an execution economy; the sleeves' intents are preserved; nothing here "
        "sizes")

#: The account the desk trades is EUR-denominated (`data/account_state.json`), so a USD-quoted
#: symbol's notional passes through EURUSD and a JPY-quoted one through EURJPY. The account
#: currency is READ, not assumed -- a hard-coded "USD" here would misprice the whole book.
DEFAULT_ACCOUNT_CCY = "EUR"

#: Parsed H1 closes, keyed by symbol. Cleared by tests that point `DESK` somewhere else.
_CLOSE: dict[str, float | None] = {}


def _at(*parts: str) -> Path:
    return DESK.joinpath(*parts)


def report_path() -> Path:
    return _at("reports", "NETTING.json")


def _json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


# ------------------------------------------------------------------ registry, bars, cost surface

def registry() -> dict[str, Any]:
    doc = _json(_at("data", "universe", "universe.json"))
    return {k: v for k, v in doc.items() if isinstance(v, dict)}


def _numeric(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    return None


def volume_steps(reg: Mapping[str, Any]) -> dict[str, float]:
    """`{symbol: volume_step}` for every symbol whose registry row carries a positive one."""
    out: dict[str, float] = {}
    for symbol, row in reg.items():
        step = _numeric(row, "volume_step") if isinstance(row, Mapping) else None
        if step is not None and step > 0:
            out[str(symbol)] = step
    return out


def contract_sizes(reg: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for symbol, row in reg.items():
        size = _numeric(row, "contract_size") if isinstance(row, Mapping) else None
        if size is not None and size > 0:
            out[str(symbol)] = size
    return out


def latest_close(symbol: str) -> float | None:
    """The last H1 close for `symbol`, or None when this box holds no bars for it.

    None is a REFUSAL and every caller must treat it as one: a substituted price would put a
    fabricated notional into a factor share, and a factor share is the number this report exists
    to publish.
    """
    if symbol in _CLOSE:
        return _CLOSE[symbol]
    value: float | None = None
    parquet = _at("data", "universe", f"{symbol}_H1.parquet")
    csv = _at("data", "universe", f"{symbol}_H1.csv")
    try:
        import pandas as pd
        frame = None
        if parquet.exists():
            frame = pd.read_parquet(parquet, columns=["close"])
        elif csv.exists():
            frame = pd.read_csv(csv, usecols=["close"])
        if frame is not None and len(frame) and "close" in frame.columns:
            last = frame["close"].dropna()
            if len(last):
                candidate = float(last.iloc[-1])
                if candidate > 0:
                    value = candidate
    except Exception:                                       # noqa: BLE001 - absence, not a crash
        value = None
    _CLOSE[symbol] = value
    return value


def cost_surface_doc() -> dict[str, Any]:
    return _json(_at("data", "cost_surface.json"))


def spread_points(surface: Mapping[str, Any], reg: Mapping[str, Any], symbol: str,
                  hour: int) -> tuple[float | None, str]:
    """Measured spread in POINTS for `symbol` at `hour`, with the basis that produced it.

    The hour-resolved cost surface is preferred because the pooled scalar is wrong by up to 6x on
    the crosses this book actually holds (`research/cost_surface.py`, measured 2026-08-29:
    USDZAR 329 pts pooled against 2,028 pts on its own fill bars). The registry median is the
    fallback and is NAMED as such, so nobody reads a pooled number as an hour-resolved one.
    """
    try:
        import cost_surface as cs
        value = cs.spread_pts(dict(surface), symbol, hour)
        if value is not None:
            return float(value), "cost_surface"
    except Exception:                                       # noqa: BLE001 - fall back and say so
        pass
    row = reg.get(symbol)
    if isinstance(row, Mapping):
        median = _numeric(row, "median_spread_pts")
        if median is not None and median >= 0:
            return median, "registry_median"
    return None, "UNMEASURED"


# --------------------------------------------------------------------------------- sleeve intents

def sleeve_rows(statuses: Sequence[str]) -> list[dict[str, Any]]:
    doc = _json(_at("data", "sleeves.json"))
    raw = doc.get("sleeves")
    wanted = {str(s).upper() for s in statuses}
    if not isinstance(raw, list):
        return []
    return [r for r in raw
            if isinstance(r, dict) and str(r.get("status") or "").upper() in wanted]


def gateway_targets(state: Mapping[str, Any]) -> dict[str, float]:
    """Per-sleeve target lots the gateway already publishes, or `{}` when it publishes none.

    Measured on the live box 2026-09-16: `gateway_state.json` carries `position`, `pending`,
    `scalp`, `generic` and an EMPTY `netting_booked`, and NO per-sleeve target block. So the
    fallback below (the sleeves' own lots) is the live path today, and this reader exists so the
    report picks the gateway's targets up the moment they appear rather than needing a new organ.
    """
    out: dict[str, float] = {}
    for key in ("sleeve_targets", "targets", "netting_booked"):
        block = state.get(key)
        if not isinstance(block, Mapping):
            continue
        for sleeve, value in block.items():
            lots: Any = value
            if isinstance(value, Mapping):
                lots = (value.get("target_lots") if value.get("target_lots") is not None
                        else value.get("lots") if value.get("lots") is not None
                        else value.get("lot") if value.get("lot") is not None
                        else value.get("volume"))
            if isinstance(lots, (int, float)) and not isinstance(lots, bool):
                out[str(sleeve)] = float(lots)
        if out:
            return out
    return out


def build_intents(rows: Sequence[Mapping[str, Any]], targets: Mapping[str, float],
                  steps: Mapping[str, float],
                  unmeasured: list[str]) -> tuple[list[SleeveIntent], dict[str, str]]:
    """One `SleeveIntent` per sleeve whose lot AND venue step are both measured.

    PRECEDENCE, and each tier is recorded per sleeve in the artifact's `intent_source`:
      1. `gateway_targets` -- the gateway's own published per-sleeve target;
      2. `sleeve_lot`      -- a numeric `lot` in the registry row;
      3. UNMEASURED        -- `"auto_ramp"`, `null` or anything else that is not a number.
    """
    intents: list[SleeveIntent] = []
    source: dict[str, str] = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        if not name or not symbol:
            continue
        lots: float | None = None
        basis = ""
        if isinstance(targets.get(name), (int, float)):
            lots, basis = float(targets[name]), "gateway_targets"
        elif isinstance(row.get("lot"), (int, float)) and not isinstance(row.get("lot"), bool):
            lots, basis = float(row["lot"]), "sleeve_lot"
        if lots is None:
            source[name] = "UNMEASURED"
            unmeasured.append(f"intent:{name} ({symbol} lot={row.get('lot')!r} is not a number)")
            continue
        if symbol not in steps:
            source[name] = "UNMEASURED"
            unmeasured.append(f"volume_step:{symbol} (absent from universe.json)")
            continue
        sign = -1.0 if str(row.get("side") or row.get("direction") or "").upper() in (
            "SHORT", "SELL") else 1.0
        intents.append(SleeveIntent(sleeve=name, symbol=symbol, target_lots=sign * lots))
        source[name] = basis
    return intents, source


# ------------------------------------------------------------------------------ factor exposure

def _legs(symbol: str, factors: Mapping[str, tuple[str, str]]) -> tuple[str, str] | None:
    override = factors.get(symbol) or factors.get(symbol.upper())
    if override is not None:
        return override
    try:
        return split_symbol(symbol)
    except RiskError:
        return None


def notional_books(rows: Sequence[Mapping[str, Any]], lots_by_sleeve: Mapping[str, float],
                   reg: Mapping[str, Any], factors: Mapping[str, tuple[str, str]],
                   equity: float | None, account_ccy: str,
                   unmeasured: list[str]) -> tuple[dict[str, tuple[Position, ...]], str]:
    """Per-sleeve books of ACCOUNT-CURRENCY notional, on ONE basis, with the basis named.

    TWO BASES EXIST AND THEY ARE NEVER MIXED, because summing a notional with a stop-risk is a
    unit error that produces a rank nobody can interpret:

      * `notional_from_lots`  -- `lot * contract_size * close * fx(quote -> account)`. Exact, and
        used whenever at least one sleeve's lot is measured and its rate chain resolves.
      * `risk_frac_x_equity`  -- `risk_frac * equity`, already in account currency. This is the
        desk's own established weight basis (`research/exposure_decomposition.py`) and is the
        LIVE path today, because the registry writes `"auto_ramp"` instead of a lot.

    A sleeve the chosen basis cannot price is NAMED and left out, never entered as zero.
    """
    sizes = contract_sizes(reg)
    priced: dict[str, float] = {}
    for row in rows:
        name, symbol = str(row.get("name") or ""), str(row.get("symbol") or "")
        if name not in lots_by_sleeve or symbol not in sizes:
            continue
        close = latest_close(symbol)
        legs = _legs(symbol, factors)
        if close is None or legs is None:
            continue
        quote = legs[1]
        conversion = 1.0 if quote == account_ccy else None
        if conversion is None:
            direct = latest_close(f"{quote}{account_ccy}")
            inverse = latest_close(f"{account_ccy}{quote}")
            if direct:
                conversion = float(direct)
            elif inverse:
                conversion = 1.0 / float(inverse)
        if conversion is None:
            unmeasured.append(
                f"fx_rate:{quote}->{account_ccy} (no {quote}{account_ccy} or "
                f"{account_ccy}{quote} H1 bars; {symbol} left out of the factor book)")
            continue
        priced[name] = lots_by_sleeve[name] * sizes[symbol] * close * conversion

    basis = "notional_from_lots" if priced else "risk_frac_x_equity"
    books: dict[str, tuple[Position, ...]] = {}
    for row in rows:
        name, symbol = str(row.get("name") or "").strip(), str(row.get("symbol") or "").strip()
        if not name or not symbol:
            continue
        if _legs(symbol, factors) is None:
            unmeasured.append(f"factor:{symbol} (unclassifiable; {name} left out)")
            continue
        if basis == "notional_from_lots":
            if name not in priced:
                unmeasured.append(f"notional:{name} ({symbol} has no lot, rate or contract size)")
                continue
            books[name] = (Position(symbol=symbol, notional_ccy=priced[name]),)
            continue
        risk = row.get("risk_frac")
        if equity is None or not isinstance(risk, (int, float)) or isinstance(risk, bool):
            unmeasured.append(f"notional:{name} (no lot, and no risk_frac x equity to fall back "
                              f"on: equity={equity!r} risk_frac={risk!r})")
            continue
        if not row.get("side") and not row.get("direction"):
            unmeasured.append(f"sleeve_side:{name} (undeclared; counted LONG)")
        sign = -1.0 if str(row.get("side") or row.get("direction") or "").upper() in (
            "SHORT", "SELL") else 1.0
        books[name] = (Position(symbol=symbol, notional_ccy=sign * float(risk) * equity),)
    return books, basis


def factor_block(books: Mapping[str, tuple[Position, ...]],
                 factors: Mapping[str, tuple[str, str]], basis: str) -> dict[str, Any]:
    """The book's signed factor vector, its concentration, and how many directions it spans."""
    if not books:
        return {"status": "UNMEASURED", "basis": basis, "names": [], "vector": [],
                "concentration": {}, "effective_rank": None, "n_sleeves": 0,
                "n_sleeves_nonzero": 0, "gross": 0.0,
                "why": "no sleeve could be priced on either basis"}
    sleeves, names, matrix = exposure_matrix(books, factors=dict(factors))
    net = matrix.sum(axis=0)
    nonzero = int(sum(1 for i in range(matrix.shape[0]) if bool((matrix[i] != 0).any())))
    gross = float(abs(net).sum())
    return {
        "status": "MEASURED" if nonzero else "UNMEASURED",
        "basis": basis,
        "names": list(names),
        "vector": [round(float(v), 4) for v in net],
        "concentration": {k: round(v, 6)
                          for k, v in factor_concentration(names, net).items()},
        "effective_rank": round(effective_rank(matrix), 4),
        "effective_rank_basis": "participation ratio of the sleeve x factor notional matrix",
        "ceiling": ("a book of n currencies spans at most n-1 directions; "
                    "a pair is a DIFFERENCE of two factors, not an asset"),
        "n_sleeves": len(sleeves),
        "n_sleeves_nonzero": nonzero,
        "gross": round(gross, 4),
    }


# ----------------------------------------------------------------------------- spreads and orders

def spreads_saved(targets: Sequence[NettedTarget], reg: Mapping[str, Any],
                  hour: int, unmeasured: list[str]) -> dict[str, Any]:
    """What the lots that never cross the spread would have cost, in ACCOUNT currency.

        cost = lots_not_sent * spread_pts * tick_value

    `tick_value` is the venue's own account-currency value of one tick on one lot and
    `spread_pts` is the spread in those same ticks, so the product is money without a further
    conversion. A symbol missing either is UNMEASURED and its saving is absent from the total
    rather than counted as zero -- the total then carries `n_symbols_unmeasured` so a partial
    number is never read as a complete one.
    """
    surface = cost_surface_doc()
    by_symbol: dict[str, Any] = {}
    total = 0.0
    measured = 0
    for target in targets:
        row = reg.get(target.symbol)
        row = row if isinstance(row, Mapping) else {}
        points, basis = spread_points(surface, reg, target.symbol, hour)
        tick_value = _numeric(row, "tick_value")
        lots = target.lots_not_sent
        cost: float | None = None
        if points is not None and tick_value is not None:
            cost = lots * points * tick_value
            total += cost
            measured += 1
        else:
            unmeasured.append(
                f"spread:{target.symbol} (spread_pts={points!r} tick_value={tick_value!r})")
        by_symbol[target.symbol] = {
            "orders_saved": target.orders_saved,
            "lots_not_sent": round(lots, 6),
            "spread_pts": points,
            "spread_basis": basis,
            "tick_value": tick_value,
            "cost_saved": None if cost is None else round(cost, 6),
            "status": "MEASURED" if cost is not None else "UNMEASURED",
        }
    return {
        "hour_utc": hour,
        "total": round(total, 6) if measured else None,
        "n_symbols_measured": measured,
        "n_symbols_unmeasured": len(targets) - measured,
        "status": "MEASURED" if measured and measured == len(targets)
                  else ("PARTIAL" if measured else "UNMEASURED"),
        "formula": "lots_not_sent * spread_pts * tick_value (account currency)",
        "by_symbol": by_symbol,
    }


# ------------------------------------------------------------------------------------------- run

def run(write: bool = True, statuses: Sequence[str] = ("LIVE", "STANDBY"),
        now: datetime | None = None) -> dict[str, Any]:
    """Build the report. `write=False` computes everything and touches no file."""
    stamp = now or datetime.now(UTC)
    unmeasured: list[str] = []

    reg = registry()
    if not reg:
        unmeasured.append("universe:universe.json (absent or unreadable; no steps, no sizes)")
    steps = volume_steps(reg)
    factors = factors_from_registry(reg)

    rows = sleeve_rows(statuses)
    state = _json(_at("data", "gateway_state.json"))
    account = _json(_at("data", "account_state.json"))
    account_ccy = str(account.get("currency") or DEFAULT_ACCOUNT_CCY).strip().upper()
    equity = account.get("equity")
    if not isinstance(equity, (int, float)) or isinstance(equity, bool) or equity <= 0:
        equity = state.get("equity")
    equity_f = float(equity) if isinstance(equity, (int, float)) and not isinstance(
        equity, bool) and equity > 0 else None
    if equity_f is None:
        unmeasured.append("equity (no account_state.json or gateway_state.json equity)")

    targets_in = gateway_targets(state)
    intents, intent_source = build_intents(rows, targets_in, steps, unmeasured)
    netted = net_intents(intents, volume_step=steps) if intents else ()
    lots_by_sleeve = {i.sleeve: i.target_lots for i in intents}

    books, basis = notional_books(rows, lots_by_sleeve, reg, factors, equity_f, account_ccy,
                                  unmeasured)
    factor = factor_block(books, factors, basis)
    saved = spreads_saved(netted, reg, stamp.hour, unmeasured)
    summary = netting_summary(netted)

    report: dict[str, Any] = {
        "at": stamp.isoformat(),
        "schema": SCHEMA,
        "source": SOURCE,
        "account_ccy": account_ccy,
        "n_sleeves_read": len(rows),
        "n_intents": len(intents),
        "intent_source": intent_source,
        "targets": [{
            "symbol": t.symbol,
            "gross_lots": round(t.gross_lots, 6),
            "net_lots": round(t.target_lots, 6),
            "netting_ratio": (None if t.netting_ratio == float("inf")
                              else round(t.netting_ratio, 6)),
            "netting_ratio_is_inf": t.netting_ratio == float("inf"),
            "orders_saved": t.orders_saved,
            "residual_lots": round(t.residual_lots, 8),
            "volume_step": t.volume_step,
            "contributors": [{"sleeve": c.sleeve, "target_lots": round(c.target_lots, 6),
                              "confidence": c.confidence} for c in t.contributors],
        } for t in netted],
        "book": summary,
        "spreads_saved_estimate": saved,
        "factor_exposure": factor,
        "unmeasured": sorted(set(unmeasured)),
        "rule": RULE,
    }
    if write:
        _write_atomic(report_path(), report)
        report["written"] = str(report_path())
    return report


def factor_rank_reading() -> dict[str, Any]:
    """The directional-span reading, shaped for `research/alpha_breadth.py` to consume.

    `alpha_breadth` publishes one row per breadth reading as
    `{name, n_eff, n_obs, status, why}` and takes the MINIMUM of the MEASURED ones as the
    headline. This reading is NOTIONAL, not realised-return: it needs no overlapping days, so it
    exists on the day a sleeve is born, and it answers the question the return readings cannot --
    how many directions the currency block leaves available at all. It is offered here rather
    than wired in: `alpha_breadth` is not edited by this change, and a reading that entered the
    headline minimum without the principal's sight of it would move a number the desk sizes on.
    """
    report = run(write=False)
    factor = report["factor_exposure"]
    rank = factor.get("effective_rank")
    measured = factor.get("status") == "MEASURED" and rank is not None
    n_names = len(factor.get("names") or [])
    return {
        "name": "exposure_notional_rank",
        "n_eff": float(rank) if measured else None,
        "n_obs": int(factor.get("n_sleeves_nonzero") or 0),
        "status": "MEASURED" if measured else "UNMEASURED",
        "why": (f"participation ratio of the sleeve x factor notional matrix over {n_names} "
                f"factors, basis {factor.get('basis')}; a pair is a DIFFERENCE of two currency "
                f"factors, so n currencies cap the book at n-1 directions"
                if measured else str(factor.get("why") or "no priceable sleeve")),
        "source": SOURCE,
        "artifact": str(report_path()),
    }


def _print(report: Mapping[str, Any]) -> None:
    book = report["book"]
    factor = report["factor_exposure"]
    print(f"NETTING  n_intents={report['n_intents']}  symbols={len(report['targets'])}  "
          f"gross={book['gross_lots']} net={book['net_lots']} "
          f"orders_saved={int(book['orders_saved'])}/{int(book['orders_gross'])}")
    for target in report["targets"][:20]:
        ratio = "inf" if target["netting_ratio_is_inf"] else target["netting_ratio"]
        print(f"  {target['symbol']:10s} gross={target['gross_lots']:<9} "
              f"net={target['net_lots']:<9} ratio={ratio!s:<9} "
              f"n={len(target['contributors'])} saved={target['orders_saved']}")
    saved = report["spreads_saved_estimate"]
    n_priced = saved["n_symbols_measured"] + saved["n_symbols_unmeasured"]
    print(f"  spreads saved: {saved['total']} {report['account_ccy']} ({saved['status']}, "
          f"{saved['n_symbols_measured']}/{n_priced} symbols)")
    print(f"  factor rank: {factor['effective_rank']} over {len(factor['names'])} factors "
          f"({factor['status']}, basis {factor['basis']})")
    top = sorted(factor["concentration"].items(), key=lambda kv: -kv[1])[:6]
    print("  top factors: " + ", ".join(f"{k} {v:.1%}" for k, v in top))
    if report["unmeasured"]:
        print(f"  UNMEASURED ({len(report['unmeasured'])}): "
              + "; ".join(report["unmeasured"][:6]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print; write no artifact")
    parser.add_argument("--json", action="store_true", help="print the whole report as JSON")
    args = parser.parse_args(argv)
    report = run(write=not args.dry_run)
    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        _print(report)
        print("dry run: nothing written" if args.dry_run else f"written: {report_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
