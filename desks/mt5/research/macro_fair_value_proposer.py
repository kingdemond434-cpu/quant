"""Mint `macro_fair_value` cells from the desk's macro axes and commodity bars (their consumer).

Three bases of one family (`mt5desk.family_macro_fair_value`), each with the symbols it can
actually reach on this host and its own declared grid:

  net_liquidity      FRED WALCL - WTREGEN (data/axes/fred.json, first-release or vintage-stable
                     series only; RRP is citation-required and excluded). Swept on XAUUSD,
                     NAS100, US500 and the hypothesis-lane USD forex pairs. Both directions are
                     open hypotheses (an injection may lift gold or the dollar).
  rate_differential  BIS `<PAIR>.carry_differential` (data/axes/bis.json), only the pairs the axis
                     carries. Declared direction: toward the currency whose advantage WIDENED.
  terms_of_trade     AUDUSD / NZDUSD / USDCAD against their commodity basket in the desk's own
                     bars. Declared direction: REVERSION of the residual.

For each symbol (a rotating cursor, so the whole reachable set is covered over hours) it runs the
family over its basis's grid, screens every variant net of the round trip with the shared
proposer screen, deflates by EVERYTHING it tried this pass across all bases, and donates one best
variant per (symbol, basis) cell through `proposer_common.donate`. The sealed gauntlet judges it
via `ORTHOGONAL_FAMILIES`; the family reloads its input from `basis`/`symbol` on the recipe.

A BASIS WITH NO INPUT PARKS, BY NAME AND BY COUNT: its block in the report says UNMEASURED with the
family's refusal code (`fred_net_liquidity_absent`, `fred_vintage_undeclared`,
`bis_rate_differential_absent`,
`tot_basket_absent`) and the symbols it would have swept. Nothing is screened for it, and a pass
where every basis parks is UNMEASURED as a whole -- never zero.

The screen is not the gauntlet: it only keeps the gauntlet from being handed every variant.

    python desks/mt5/research/macro_fair_value_proposer.py --once --budget-s 600
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_macro_fair_value as F  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "macro_fair_value"
FAMILY = "macro_fair_value"
REPORT = DESK / "reports" / "MACRO_FAIR_VALUE_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0
MIN_BARS = 2000

NET_LIQUIDITY_RISK = ("XAUUSD", "NAS100", "US500")
#: (move, direction) pairs each basis is allowed to test: the declared hypothesis, not every sign.
PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    "net_liquidity": (("up", "long"), ("up", "short"), ("down", "long"), ("down", "short")),
    "rate_differential": (("up", "long"), ("down", "short")),     # toward the widened advantage
    "terms_of_trade": (("up", "short"), ("down", "long")),        # reversion to fair value
}
#: One threshold per basis; the other free axis per basis is listed beside it.
GRID: dict[str, dict[str, Any]] = {
    "net_liquidity": {"min_abs": 1.5, "window": (52,), "lookback_days": (63,)},
    "rate_differential": {"min_abs": 0.25, "window": (52,), "lookback_days": (21, 63)},
    "terms_of_trade": {"min_abs": 2.0, "window": (480, 2400), "lookback_days": (63,)},
}
HOLDS: tuple[int, ...] = (24, 72)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def _lane(meta: dict[str, Any]) -> list[str]:
    from research import universe_policy as up
    return [s for s in sorted(meta) if isinstance(meta[s], dict) and up.may_hypothesise(s)]


def _bis_pairs(fallback: list[str]) -> list[str]:
    """The pairs the BIS axis declares in its `symbols` header, read from the file's head so an
    81 MB axis is not parsed once per pair just to learn its roster. The rows themselves are read
    only by the family's reader; a header that cannot be read falls back to probing `fallback`."""
    try:
        with open(Path(F.AXES) / "bis.json", encoding="utf-8-sig") as fh:
            head = fh.read(1 << 16)
        i = head.index('"symbols"')
        body = head[head.index("[", i):head.index("]", i) + 1]
        return sorted(str(s).upper() for s in json.loads(body))
    except OSError:
        return []
    except ValueError:
        return sorted(fallback)


def _n(s: Any) -> int:
    return 0 if s is None else len(s)


def reach(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per basis: the symbols it would sweep, or the named refusal that parks it."""
    lane = set(_lane(meta))
    out: dict[str, dict[str, Any]] = {}
    nl_syms = sorted({s for s in NET_LIQUIDITY_RISK if s in lane}
                     | {s for s in lane if "USD" in s
                        and str(meta[s].get("asset_class") or "").lower() == "forex"})
    try:
        nl = F.net_liquidity()
        out["net_liquidity"] = {"symbols": nl_syms, "prints": len(nl),
                                "last_knowable": str(nl.index.max().date()) if len(nl) else None}
    except F.MacroFairValueUnavailable as exc:
        code = str(exc).split(":", 1)[0]
        out["net_liquidity"] = {"parked_reason": code if code in (F.ABSENT_FRED,
                                                                  F.UNVINTAGED_FRED)
                                else F.ABSENT_FRED, "why": str(exc)[:300],
                                "symbols_parked": len(nl_syms)}
    fx = [s for s in lane if "forex" in str(meta[s].get("asset_class") or "").lower()]
    bis = [s for s in _bis_pairs(fx) if s in lane]
    held = {s: _n(F.axis_series("bis", f"{s}.carry_differential")) for s in bis}
    rd = sorted(s for s, n in held.items() if n)
    out["rate_differential"] = ({"symbols": rd, "points": held} if rd else
                                {"parked_reason": F.ABSENT_BIS, "symbols_parked": len(bis),
                                 "why": "the BIS axis carries no hypothesis-lane pair"})
    tot = sorted(s for s in F.TOT_BASKETS if s in lane)
    need = sorted({p for s in tot for p in F.TOT_BASKETS[s]})
    absent = [p for p in need if pc.bars(p) is None]
    out["terms_of_trade"] = ({"symbols": tot, "basket": need} if not absent else
                             {"parked_reason": F.ABSENT_TOT, "symbols_parked": len(tot),
                              "why": f"no H1 bars for {', '.join(absent)} on this host"})
    return out


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    meta = pc.universe_meta()
    bases = reach(meta)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/macro_fair_value_proposer.py",
                           "family": FAMILY, "consumes": ["data/axes/fred.json",
                                                          "data/axes/bis.json",
                                                          "data/universe/*_H1.parquet"],
                           "bases": bases}
    work = sorted({(s, b) for b, v in bases.items() for s in v.get("symbols", ())})
    if not work:
        rep.update({"status": UNMEASURED, "tests_run": UNMEASURED, "cells_proposed": UNMEASURED,
                    "why": "every basis is parked: see bases[*].parked_reason"})
        _write(REPORT, rep)
        return rep
    syms = sorted({s for s, _ in work})
    start = int(_read(REPORT).get("cursor_next", 0)) % len(syms)
    order = syms[start:] + syms[:start]
    rows: list[dict[str, Any]] = []
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in order:
        if time.monotonic() - t0 > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = "no or too few H1 bars"
            swept.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            swept.append(sym)
            continue
        unf = pc.artifact_hours(d)
        for basis in (b for s, b in work if s == sym):
            g = GRID[basis]
            for move, direction in PAIRS[basis]:
                for window in g["window"]:
                    for lookback in g["lookback_days"]:
                        for hold in HOLDS:
                            params: dict[str, Any] = {
                                "basis": basis, "move": move, "min_abs": g["min_abs"],
                                "direction": direction, "hold_bars": hold}
                            if basis != "net_liquidity":
                                params["symbol"] = sym
                            if basis != "rate_differential":
                                params["window"] = window
                            else:
                                params["lookback_days"] = lookback
                            try:
                                sig = F.family_macro_fair_value(d, **params)
                            except F.MacroFairValueUnavailable as exc:
                                skipped[f"{sym}.{basis}"] = str(exc)[:160]
                                continue
                            sc = pc.screen(d, sig, cost, unf)
                            if sc is None:
                                continue
                            rows.append({"cell": f"{sym}.{FAMILY}.{basis}", "symbol": sym,
                                         "params": params, **sc})
        swept.append(sym)
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"{r['params']['basis'].replace('_', ' ')} fair value moved "
                   f"{r['params']['move']} by at least {r['params']['min_abs']} on its own "
                   f"scale: holders reprice {r['symbol']} {r['params']['direction']} over the "
                   f"{r['params']['hold_bars']} bars after the reading is public"),
        title=f"{r['cell']} {r['params']['move']} {r['params']['direction']} "
              f"h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, len(rows))
    rep.update({"status": "OK", "symbols_available": len(syms), "symbols_swept": len(swept),
                "cursor_start": start, "cursor_next": (start + len(swept)) % len(syms),
                "tests_run": len(rows), "cells_proposed": len(proposals),
                "donated": len(cands) if donated else 0, "donation_path": str(donated or ""),
                "donation_refusals": dict(pc.LAST_DONATION) if donated is None and cands
                else None,
                "skipped": skipped, "elapsed_s": round(time.monotonic() - t0, 1),
                "proposals": proposals[:50]})
    _write(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s)
    parked = sorted(b for b, v in r.get("bases", {}).items() if "parked_reason" in v)
    print(f"macro_fair_value_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)} parked={','.join(parked) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
