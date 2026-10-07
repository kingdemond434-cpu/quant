#!/usr/bin/env python3
"""THE CONSTRAINED BOOK, AS A MEASURED SHADOW (Tier-1 audit item #6, 2026-09-29).

    What would the book be if ruin, margin/stop-out, tail loss, concentration, liquidity and
    execution feasibility were HARD CONSTRAINTS inside the posterior E[log W] solve -- and how
    does that book differ from the one the gateway is trading?

The arithmetic is `libs/portfolio/constrained_elog.py` (pure, tested). This organ gathers its
inputs from what the allocator already published and writes one artifact:

    paths     data/pf_allocator_cache/worlds.npz -- the allocator's OWN world population
              (posterior mean draws, decay, crisis overlay, cost doubt), so the shadow and the
              live book are scored on the same futures
    book      reports/pf_allocation.json `book` -- the published (traded) book
    margin    `heat.envelope.survival.margin_use` (the allocator's broker reading), else the
              terminal directly; stop-out level from the terminal's `margin_so_so`
    capacity  reports/CAPACITY.json -- per-sleeve min-lot risk (execution feasibility) and the
              market-impact ceiling where MEASURED (none is today; the clause says UNMEASURED)
    symbols   data/sleeves.json name -> symbol, else the sleeve name's own leading token

    -> reports/CONSTRAINED_BOOK.json

IT DECIDES, EVERY HOUR, ON ITS PROOF (2026-09-30). `constrained_elog.decide` reads this pass's
paired contest against the LIVE book and switches the feed ON only while the constrained book's
robust E[log W] beats the traded book's (dE > 0 with the bootstrap interval excluding zero, no
more ruinous, never below the heat floor, on a fresh world population). The decision is written
to reports/CONSTRAINED_BOOK_SWITCH.json; `research/pf_allocator.py` reads it and adopts the
constrained book only after re-contesting it on its own paths (`constrained_elog.adopt_if_proven`).
There is no hand switch: `constrained_elog.FEEDS_LIVE` is the fiat switch and stays False.

    python desks/mt5/research/constrained_book.py
"""
from __future__ import annotations

import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_REPO_ROOT = str(_Path(__file__).resolve().parents[3])
if _REPO_ROOT not in _sys.path:  # libs.ops.mt5_readonly must be importable
    _sys.path.insert(0, _REPO_ROOT)

import argparse
import json
import math
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ALLOCATION = BASE / "reports" / "pf_allocation.json"
WORLDS = BASE / "data" / "pf_allocator_cache" / "worlds.npz"
CAPACITY = BASE / "reports" / "CAPACITY.json"
SLEEVES = BASE / "data" / "sleeves.json"
ACCOUNT = BASE / "data" / "account_state.json"
OUT = BASE / "reports" / "CONSTRAINED_BOOK.json"
SWITCH = BASE / "reports" / "CONSTRAINED_BOOK_SWITCH.json"

#: Paths cut from the world population, and their length in days. 400 x 5 is the allocator's
#: own posterior challenger's shape (`posterior_growth.DEFAULT_*`), so the two are comparable.
N_PATHS = 400
HORIZON = 5
#: A world population older than this is reported STALE beside the result (not refused: a
#: shadow on yesterday's worlds is still a measurement, and the age is on the artifact).
STALE_S = 6 * 3600


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def symbol_map(names: list[str]) -> dict[str, str]:
    """name -> symbol from data/sleeves.json, else the name's leading token when it is a ticker."""
    out: dict[str, str] = {}
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    by_name = {str(r.get("name")): str(r.get("symbol") or "") for r in rows or []
               if isinstance(r, dict) and r.get("name")}
    for n in names:
        sym = by_name.get(n, "")
        if not sym:
            head = n.replace(".", "_").split("_")[0].upper()
            if head in ("GOLD", "XAU"):
                sym = "XAUUSD"
            elif head in ("SILVER", "XAG"):
                sym = "XAGUSD"
            elif len(head) >= 5 and head.isalnum():
                sym = head
        if sym:
            out[n] = sym
    return out


def class_map(symbols: dict[str, str]) -> dict[str, str]:
    from libs.portfolio.robust_elog import _asset_class
    out: dict[str, str] = {}
    for n, s in symbols.items():
        c = _asset_class(s)
        if c:
            out[n] = c
    return out


def _terminal_account() -> tuple[dict[str, float | None], str]:
    """(margin, equity, stop_out_level) straight from the terminal, or Nones with the reason."""
    none: dict[str, float | None] = {"margin": None, "equity": None, "stop_out_level": None}
    try:
        from libs.ops.mt5_readonly import readonly_mt5  # read-only terminal (ARCH-12)
        mt5 = readonly_mt5()
    except ImportError:
        return none, "MetaTrader5 is not importable on this host"
    opened = False
    try:
        if mt5.terminal_info() is None:
            try:
                from mt5desk.config import terminal_path
                path = terminal_path()
            except Exception:
                path = ""
            opened = bool(mt5.initialize(path=path) if path else mt5.initialize())
            if not opened:
                return none, f"terminal unreachable ({mt5.last_error()})"
        acc = mt5.account_info()
        if acc is None:
            return none, "the terminal reports no account"
        so = float(getattr(acc, "margin_so_so", 0.0) or 0.0)
        return {"margin": float(acc.margin), "equity": float(acc.equity),
                "stop_out_level": (so / 100.0 if so > 1.0 else so) or None}, "terminal"
    except Exception as exc:
        return none, f"{type(exc).__name__}: {exc}"
    finally:
        if opened:
            with suppress(Exception):
                mt5.shutdown()


def margin_inputs(art: dict[str, Any], deployed: float,
                  terminal: dict[str, float | None]) -> tuple[float | None, float | None, str]:
    """(margin per unit heat, max margin use, why). The allocator's reading first."""
    env = ((art.get("heat") or {}).get("envelope") or {}).get("survival") or {}
    mu = env.get("margin_use") if isinstance(env, dict) else None
    max_mu = None
    if isinstance(mu, dict):
        with suppress(TypeError, ValueError):
            max_mu = float(mu["max_margin_use"]) if mu.get("max_margin_use") is not None else None
        by = mu.get("by_heat") or {}
        per = [float(v) / float(k) for k, v in by.items()
               if _num(k) and _num(v) and float(k) > 0]
        if mu.get("status") == "MEASURED" and per:
            return sum(per) / len(per), max_mu, "pf_allocation survival.margin_use (MEASURED)"
    m, eq = terminal.get("margin"), terminal.get("equity")
    if m and eq and deployed > 0 and m > 0 and eq > 0:
        return (m / eq) / deployed, max_mu, "terminal margin / equity at the traded book's heat"
    return None, max_mu, ("UNMEASURED: the allocator's margin reading is UNMEASURED and the "
                          "terminal shows no margin in use (a flat book is 0/0, not free)")


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def capacity_inputs(names: list[str], equity: float | None
                    ) -> tuple[dict[str, float], dict[str, Any]]:
    """Measured liquidity ceilings (heat) and the per-sleeve min-lot feasibility floor (heat)."""
    doc = _read(CAPACITY)
    caps: dict[str, float] = {}
    min_lot: dict[str, float] = {}
    rows = doc.get("rows") if isinstance(doc, dict) else None
    eq = equity or (_num(doc.get("equity_eur")) if isinstance(doc, dict) else None)
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("sleeve"):
            continue
        nm = str(r["sleeve"])
        ceil_eur = _num(r.get("ceiling_eur"))
        if r.get("ceiling_status") == "MEASURED" and ceil_eur and eq:
            caps[nm] = ceil_eur / eq
        mlr = _num(r.get("min_lot_risk_eur"))
        if mlr and eq:
            min_lot[nm] = mlr / eq
    return caps, {"equity_eur": eq, "min_lot_heat": {k: round(v, 6) for k, v in min_lot.items()
                                                     if k in names or not names}}


def feasibility(book: dict[str, float], min_lot_heat: dict[str, float]) -> dict[str, Any]:
    """A funded sleeve whose heat is below one minimum lot's risk cannot trade AS SIZED."""
    if not min_lot_heat:
        return {"status": "UNMEASURED", "why": "CAPACITY.json carries no min-lot risk per sleeve"}
    below = {k: {"heat": round(v, 6), "min_lot_heat": round(min_lot_heat[k], 6)}
             for k, v in book.items() if k in min_lot_heat and 0 < v < min_lot_heat[k]}
    covered = sum(1 for k in book if k in min_lot_heat)
    return {"status": "MEASURED" if covered else "UNMEASURED",
            "n_funded": len(book), "n_covered": covered, "n_below_min_lot": len(below),
            "below_min_lot": below,
            "why": ("heat below one minimum lot's risk is executed AT the minimum lot, so the "
                    "venue carries more risk than the book priced")}


def build(now: datetime | None = None, *, seed: int = 0) -> dict[str, Any]:
    t0 = time.time()
    now = now or datetime.now(tz=UTC)
    from libs.portfolio import constrained_elog as ce
    base: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                            "feeds_live": False,
                            "fiat_switch": ce.FEEDS_LIVE,
                            "source": {"worlds": str(WORLDS.relative_to(ROOT)),
                                       "allocation": str(ALLOCATION.relative_to(ROOT))}}
    doc = _build(base, now, seed=seed, t0=t0)
    # THE DECISION, on every outcome: an UNMEASURED pass decides OFF by name.
    switch = ce.decide(doc, now_iso=base["generated_utc"])
    doc["feeds_live"] = bool(switch["feeds_live"])
    doc["switch"] = switch
    return doc


def _build(base: dict[str, Any], now: datetime, *, seed: int, t0: float) -> dict[str, Any]:
    from libs.portfolio import constrained_elog as ce
    art = _read(ALLOCATION)
    if not isinstance(art, dict) or not isinstance(art.get("book"), dict):
        return {**base, "status": "UNMEASURED",
                "why": f"no published allocator book at {ALLOCATION.relative_to(ROOT)}"}
    if not WORLDS.exists():
        return {**base, "status": "UNMEASURED",
                "why": f"no allocator world population at {WORLDS.relative_to(ROOT)}"}
    import numpy as np

    from libs.portfolio.posterior_growth import compare, sample_paths
    from libs.portfolio.robust_elog import Worlds
    try:
        z = np.load(WORLDS, allow_pickle=False)
        worlds = Worlds(r=z["r"], names=tuple(str(x) for x in z["names"]), crisis=z["crisis"],
                        mu_draws=z["mu"], note="allocator world cache")
    except (OSError, ValueError, KeyError) as exc:
        return {**base, "status": "UNMEASURED", "why": f"world cache unreadable: {exc}"}
    worlds_age_s = round(time.time() - WORLDS.stat().st_mtime, 1)
    names = list(worlds.names)
    current = {k: float(v) for k, v in art["book"].items()
               if k in names and _num(v) and float(v) > 0}
    off_universe = sorted(k for k in art["book"] if k not in names)
    paths = sample_paths(None, n_paths=N_PATHS, horizon=HORIZON, worlds=worlds, seed=seed)
    heat = art.get("heat") or {}
    ceiling = _num(heat.get("hard_ceiling")) or 0.30
    floor = _num(heat.get("target")) or 0.20
    floor = min(floor, ceiling)
    terminal, term_why = _terminal_account()
    deployed = sum(current.values())
    mph, max_mu, m_why = margin_inputs(art, deployed, terminal)
    acct = _read(ACCOUNT) if ACCOUNT.exists() else None
    equity = terminal.get("equity") or (_num(acct.get("equity")) if isinstance(acct, dict)
                                        else None)
    caps, cap_meta = capacity_inputs(names, equity)
    sym = symbol_map(names)
    cls = class_map(sym)
    spec = ce.ConstraintSpec(margin_per_heat=mph, stop_out_level=terminal.get("stop_out_level"),
                             max_margin_use=max_mu, liquidity_cap=caps, floor=floor,
                             ceiling=ceiling)
    cur_eval = ce.evaluate(paths, current, spec, symbol_of=sym, class_of=cls)
    solved = ce.solve_constrained(paths, spec, symbol_of=sym, class_of=cls, h_prev=current)
    con_eval = ce.evaluate(paths, solved["book"], spec, symbol_of=sym, class_of=cls)
    try:
        contest = compare(solved["book"], current, paths, n_boot=1000, seed=seed)
    except Exception as exc:
        contest = {"error": f"{type(exc).__name__}: {exc}"}
    delta = {k: round(float(solved["book"].get(k, 0.0)) - float(current.get(k, 0.0)), 6)
             for k in sorted(set(solved["book"]) | set(current))}
    delta = {k: v for k, v in delta.items() if abs(v) > 1e-6}
    feas_cur = feasibility(current, cap_meta["min_lot_heat"])
    feas_con = feasibility(solved["book"], cap_meta["min_lot_heat"])
    status = "MEASURED" if current else "UNMEASURED"
    return {
        **base,
        "status": status,
        "why": ("the traded book and the fully-constrained posterior solve, scored on the "
                "allocator's own world paths" if current else
                "the published book funds no sleeve in the world population"),
        "worlds_age_s": worlds_age_s,
        "worlds_stale": worlds_age_s > STALE_S,
        "paths": {"n": paths.n_paths, "horizon_days": paths.horizon, "note": paths.note},
        "spec": spec.as_dict(),
        "inputs": {"margin": m_why, "terminal": term_why,
                   "stop_out_level": terminal.get("stop_out_level"),
                   "equity": equity, "n_symbol_mapped": len(sym), "n_class_mapped": len(cls),
                   "n_sleeves": len(names), "n_liquidity_caps": len(caps),
                   "book_sleeves_outside_worlds": off_universe},
        "current": {"book": {k: round(v, 6) for k, v in sorted(current.items(),
                                                                key=lambda t: -t[1])},
                    **cur_eval, "execution_feasibility": feas_cur},
        "constrained": {**solved, **{k: v for k, v in con_eval.items() if k != "total_heat"},
                        "execution_feasibility": feas_con},
        "delta_heat": delta,
        "delta_total_heat": round(float(solved["total_heat"]) - deployed, 6),
        "contest_constrained_vs_current": contest,
        "direction": ("MORE heat than the traded book" if solved["total_heat"] > deployed + 1e-6
                      else "LESS heat than the traded book" if solved["total_heat"] <
                      deployed - 1e-6 else "the same total heat, redistributed"),
        "current_violates": cur_eval["violated"],
        "elapsed_s": round(time.time() - t0, 2),
        "rule": ("a shadow: every MEASURED risk clause is a hard constraint inside the posterior "
                 "E[log W] solve; an UNMEASURED clause constrains nothing and is never reported "
                 "as slack; the flat 20% floor holds unless the ruin guard itself binds"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
        SWITCH.write_text(json.dumps(doc["switch"], indent=2, default=str), "utf-8")
    print(f"constrained_book: {doc['status']} feeds_live={doc['feeds_live']} "
          f"({doc['switch']['why'][:160]}) -- "
          f"{doc.get('direction') or doc.get('why')}; current violates "
          f"{doc.get('current_violates', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
