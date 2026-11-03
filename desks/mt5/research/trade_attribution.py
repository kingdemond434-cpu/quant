"""TRADE ATTRIBUTION (blueprint AC7, 2026-11-03): signal -> fill -> markout, and each live trade's
R split into five layers, with a weekly per-sleeve rollup.

REPORT-ONLY. It sizes, vetoes and trades nothing; it measures where a live trade's R went.

(a) AC7 chain, per live fill. The decision row (decision_ledger.jsonl, joined on the entry order
    ticket) carries the signal price; the live ledger carries the fill. Entry slippage is
    `dir * (fill - signal)` in points (positive = adverse). Markouts at +1m/+5m/+60m are read
    from the finest bars on disk (M1, else M15/H1 for the horizons they can resolve), only from
    bars whose period had ENDED by the horizon.

(b) Five layers, all in R of the trade's own stop distance:
    signal_edge     the certificate's expectancy (sleeves.json shadow_exp / cert expectancy)
    entry_timing    -slip / stop distance (the fill versus the signal price)
    execution_cost  -(spread + commission + swap) in R; slip is booked in entry_timing ONCE
    exit_policy     realised R versus hold-to-SL/TP, from recorded MFE/MAE; versus the best
                    exit-grid variant only when an exit-grid artifact exists
    sizing          realised R * (filled volume / decided lot - 1)

Every absent input is UNMEASURED, never 0: a layer with no input carries the string, the rollup
averages only measured trades and reports n_measured, and residual is computed only when every
layer is measured.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The live readers are the loss learner's and the archaeologist's, reused, not re-written.
from research.loss_learner import _jsonl, _ledger_path, _num, _ts  # noqa: E402
from research.missed_trade_archaeologist import _atomic_write, _sym  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
LIVE = DATA / "live_ledger.jsonl"
DECISIONS = DATA / "decision_ledger.jsonl"
SLEEVES = DATA / "sleeves.json"
UNIVERSE = DATA / "universe"
EXIT_GRID_CANDIDATES = (REPORTS / "EXIT_GRID.json", DATA / "exit_grid.json")
OUT = REPORTS / "TRADE_ATTRIBUTION.json"
LOSS_OUT = DATA / "loss_learning" / "ATTRIBUTION_BY_SLEEVE.json"

UNMEASURED = "UNMEASURED"
LAYERS = ("signal_edge", "entry_timing", "execution_cost", "exit_policy", "sizing")
HORIZONS_MIN = (1, 5, 60)
TF_MIN = {"M1": 1, "M15": 15, "H1": 60}
WEEK = timedelta(days=7)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(v: Any) -> float | None:
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError:
            return None
    out: float | None = _num(v)
    return out


def _direction(row: dict[str, Any]) -> int | None:
    """+1 long, -1 short, from the trade's own geometry (the deal `side` is the CLOSING deal's)."""
    e, sl, tp = _f(row.get("entry_price")), _f(row.get("sl")), _f(row.get("tp"))
    if e is not None and tp is not None and tp != e:
        return 1 if tp > e else -1
    if e is not None and sl is not None and sl != e:
        return 1 if sl < e else -1
    es = str(row.get("entry_side") or "").lower()
    if es in ("buy", "0", "long"):
        return 1
    if es in ("sell", "1", "short"):
        return -1
    return None


def decision_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in rows:
        if str(d.get("outcome") or "") == "EXECUTED" and d.get("ticket") not in (None, ""):
            out[str(d["ticket"])] = d
    return out


def symbol_meta(universe: Path = UNIVERSE) -> dict[str, dict[str, Any]]:
    doc = _read(universe / "universe.json")
    return doc if isinstance(doc, dict) else {}


def load_bars(symbol: str, universe: Path = UNIVERSE) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tf in TF_MIN:
        p = universe / f"{_sym(symbol)}_{tf}.parquet"
        if not p.exists():
            continue
        try:
            import pandas as pd
            df = pd.read_parquet(p)
            if len(df) and "close" in df.columns:
                df = df.copy()
                df.index = pd.to_datetime(df.index, utc=True)
                out[tf] = df.sort_index()
        except Exception:
            continue
    return out


def markout(bars: dict[str, Any], t0: datetime | None, entry: float | None, d: int | None,
            point: float | None, h_min: int) -> Any:
    """dir * (close at t0+h - entry) in points, from the finest bars that resolve h, using only
    a bar whose period had ended by t0+h and that opened at or after t0."""
    if t0 is None or entry is None or d is None or not point:
        return UNMEASURED
    for tf, m in TF_MIN.items():
        if m > h_min or tf not in bars:
            continue
        df = bars[tf]
        horizon = t0 + timedelta(minutes=h_min)
        sel = df.loc[(df.index >= t0) & (df.index <= horizon - timedelta(minutes=m))]
        if len(sel):
            return round(d * (float(sel["close"].iloc[-1]) - entry) / point, 3)
    return UNMEASURED


def _cert_exp(sleeve: str, sleeves_doc: Any) -> float | None:
    for s in (sleeves_doc or {}).get("sleeves", []) if isinstance(sleeves_doc, dict) else []:
        if isinstance(s, dict) and s.get("name") == sleeve:
            for k in ("cert_expectancy_r", "expectancy_r", "cert_expectancy", "shadow_exp"):
                v = _f(s.get(k))
                if v is not None:
                    return v
    return None


def _exit_grid_best(sleeve: str, grid: Any) -> float | None:
    if not isinstance(grid, dict):
        return None
    blk = (grid.get("sleeves") or grid).get(sleeve)
    if isinstance(blk, dict):
        return _f(blk.get("best_r") or blk.get("best_expectancy_r"))
    return None


def attribute(row: dict[str, Any], dec: dict[str, Any] | None, meta: dict[str, Any],
              bars: dict[str, Any], sleeves_doc: Any, grid: Any) -> dict[str, Any]:
    d = _direction(row)
    entry, sl, tp = _f(row.get("entry_price")), _f(row.get("sl")), _f(row.get("tp"))
    digits = meta.get("digits")
    point = 10.0 ** -int(digits) if isinstance(digits, int) else None
    stop = abs(entry - sl) if entry is not None and sl is not None and entry != sl else None
    risk_q = _f(row.get("risk_quote"))
    pl = _f(row.get("pl_quote"))
    r = _f(row.get("r_multiple"))
    if (r is None or r == 0.0) and pl is not None and risk_q:
        r = pl / abs(risk_q)
    signal = _f((dec or {}).get("price"))
    slip_pts: Any = UNMEASURED
    if signal is not None and entry is not None and d is not None and point:
        slip_pts = round(d * (entry - signal) / point, 3)
    # The fill's own time; a decision time stands in only for a market order (a pending stop's
    # decision precedes its fill by hours, so it would mark out the wrong bar).
    t0 = _ts(row.get("entry_time"))
    if t0 is None and dec and "pending" not in str(dec.get("execution") or ""):
        t0 = _ts(dec.get("decided_at"))
    sleeve = str(row.get("sleeve") or "")
    layers: dict[str, Any] = dict.fromkeys(LAYERS, UNMEASURED)
    ce = _cert_exp(sleeve, sleeves_doc)
    if ce is not None:
        layers["signal_edge"] = round(ce, 4)
    if isinstance(slip_pts, float) and stop and point:
        layers["entry_timing"] = round(-slip_pts * point / stop, 4)
    spread_pts = _f((dec or {}).get("spread_pts"))
    spread_src = "decision" if spread_pts is not None else None
    if spread_pts is None:
        spread_pts, spread_src = _f(meta.get("median_spread_pts")), "universe_median"
    fees = [_f(row.get("commission")), _f(row.get("swap"))]
    if spread_pts is not None and point and stop and risk_q and None not in fees:
        layers["execution_cost"] = round(
            -(spread_pts * point / stop) + sum(x for x in fees if x is not None) / abs(risk_q), 4)
    mfe, mae = _f(row.get("mfe_r")), _f(row.get("mae_r"))
    tp_r = abs(tp - entry) / stop if tp is not None and entry is not None and stop else None
    hold: Any = UNMEASURED
    if mfe is not None and mae is not None and tp_r is not None:
        # Hold-to-SL/TP: TP if the path reached it without first breaching the stop. With only
        # extremes recorded, order is unknown when both were touched -> UNMEASURED.
        hit_tp, hit_sl = mfe >= tp_r, mae <= -1.0
        hold = tp_r if hit_tp and not hit_sl else (-1.0 if hit_sl and not hit_tp else UNMEASURED)
    if isinstance(hold, float) and r is not None:
        layers["exit_policy"] = round(r - hold, 4)
    best = _exit_grid_best(sleeve, grid)
    lot, vol = _f((dec or {}).get("lot")), _f(row.get("volume"))
    if lot and vol is not None and r is not None:
        layers["sizing"] = round(r * (vol / lot - 1.0), 4) + 0.0
    measured = all(isinstance(v, float) for v in layers.values())
    return {
        "deal": row.get("deal"), "sleeve": sleeve, "symbol": row.get("symbol"),
        "time": row.get("exit_time") or row.get("time"), "direction": d,
        "decision_id": (dec or {}).get("decision_id") or UNMEASURED,
        "signal_price": signal if signal is not None else UNMEASURED,
        "fill_price": entry if entry is not None else UNMEASURED,
        "entry_slip_points": slip_pts,
        "markout_points": {f"+{h}m": markout(bars, t0, entry, d, point, h) for h in HORIZONS_MIN},
        "realised_r": round(r, 4) if r is not None else UNMEASURED,
        "layers": layers,
        "exit_vs_best_grid": (round(r - best, 4) if best is not None and r is not None
                              else UNMEASURED),
        "spread_source": spread_src if layers["execution_cost"] != UNMEASURED else UNMEASURED,
        "residual_r": (round(r - sum(layers.values()), 4) if measured and r is not None
                       else UNMEASURED),
    }


def rollup(trades: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        ts = _ts(t.get("time"))
        if ts is not None and now - WEEK <= ts <= now:
            by[t["sleeve"]].append(t)
    out: dict[str, Any] = {}
    for sleeve, ts_ in sorted(by.items()):
        layer_doc: dict[str, Any] = {}
        for k in LAYERS:
            vals = [t["layers"][k] for t in ts_ if isinstance(t["layers"][k], float)]
            layer_doc[k] = {"mean_r": round(sum(vals) / len(vals), 4) if vals else UNMEASURED,
                            "n_measured": len(vals)}
        leaky = [(v["mean_r"], k) for k, v in layer_doc.items()
                 if k != "signal_edge" and isinstance(v["mean_r"], float)]
        worst = min(leaky) if leaky else None
        out[sleeve] = {"n_trades": len(ts_), "layers": layer_doc,
                       "leak_layer": worst[1] if worst and worst[0] < 0 else
                       (UNMEASURED if not leaky else "none"),
                       "unmeasured_layers": [k for k, v in layer_doc.items()
                                             if v["mean_r"] == UNMEASURED]}
    return out


def run(now: datetime | None = None, live: Path = LIVE, decisions: Path = DECISIONS,
        sleeves: Path = SLEEVES, universe: Path = UNIVERSE, out: Path = OUT,
        loss_out: Path = LOSS_OUT, grid_paths: tuple[Path, ...] = EXIT_GRID_CANDIDATES
        ) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    lpath = Path(_ledger_path(live))
    rows = [r for r in _jsonl(lpath) if str(r.get("account_kind") or "live") == "live"]
    decs = decision_index(_jsonl(decisions))
    meta_all = symbol_meta(universe)
    sdoc = _read(sleeves)
    grid = next((g for g in (_read(p) for p in grid_paths) if g is not None), None)
    bars_cache: dict[str, dict[str, Any]] = {}
    trades = []
    for r in rows:
        sym = _sym(r.get("symbol"))
        if sym not in bars_cache:
            bars_cache[sym] = load_bars(sym, universe)
        dec = decs.get(str(r.get("entry_order") or "")) or decs.get(str(r.get("order") or ""))
        trades.append(attribute(r, dec, meta_all.get(sym) or {}, bars_cache[sym], sdoc, grid))
    per_sleeve = rollup(trades, now)
    inputs = {
        "live_ledger": f"MEASURED: {len(rows)} live rows" if lpath.exists()
        else f"{UNMEASURED}: absent {lpath}",
        "decision_ledger": f"MEASURED: {len(decs)} executed" if decisions.exists()
        else f"{UNMEASURED}: absent {decisions}",
        "exit_grid": "MEASURED" if grid is not None else f"{UNMEASURED}: no exit-grid artifact",
        "mfe_mae": ("MEASURED" if any("mfe_r" in r for r in rows)
                    else f"{UNMEASURED}: live ledger records no mfe_r/mae_r"),
    }
    joined = sum(1 for t in trades if t["decision_id"] != UNMEASURED)
    doc = {"generated_at": now.isoformat(), "blueprint_row": "AC7", "report_only": True,
           "inputs": inputs, "n_trades": len(trades), "n_joined_to_decision": joined,
           "weekly_by_sleeve": per_sleeve, "trades": trades}
    _atomic_write(out, doc)
    _atomic_write(loss_out, {"generated_at": now.isoformat(), "source": str(out.name),
                             "window_days": 7, "inputs": inputs, "sleeves": per_sleeve})
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = run()
    print(json.dumps({"n_trades": doc["n_trades"], "joined": doc["n_joined_to_decision"],
                      "sleeves": len(doc["weekly_by_sleeve"]), "inputs": doc["inputs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
