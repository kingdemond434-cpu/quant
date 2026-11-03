#!/usr/bin/env python3
"""COST BASIS -- what each live order REALLY paid, joined to the decision that sent it.

Blueprint rows AC4 / I7 / CS2 / DP8 and D4. `cost_surfaces.py` keys the cost model by cell but
reads the fill corpus, where the decision join is fuzzy (0 matched fills on 2026-11-03), and no
admission or sizing path reads it. LIVE rows in `sleeves.json` carry no cost basis at all. This
leg closes the measurement half of both, and stops there:

  (1) MATCH every closed live deal (`live_ledger.jsonl`) to its decision row
      (`decision_ledger.jsonl`, EXECUTED, by ticket == the deal's entry order / position id --
      the same exact join `trade_attribution.py` uses), and measure per trade
        slip_points  = (fill - requested) x direction / point   (positive = paid)
        slip_r       = (fill - requested) x direction / stop distance
        commission_r = -(commission + entry_cost_allocated + exit_fee) / risk in account ccy
        spread_points from the fill corpus row of the same ticket, when it recorded one.
      Rolled up per symbol and per symbol x session into a REAL-FILL surface with n, and a
      shrinkage toward the MODELLED surface (`COST_SURFACES.json` via `cost_surfaces.cost_for`):
          shrunk = (n x realised + K x modelled) / (n + K),   K = SHRINK_K
      Where the model has no number the realised median stands alone at n >= MIN_N; below that
      the term is UNMEASURED with its n. Never zero (L1.28a).
  (2) GIVE EVERY LIVE ROW a cost basis: modelled vs realised, source, n.
  (3) REPORT ONLY, for admission and sizing: the certificate expectancy net of the realised cost
      drift (realised minus modelled cost, in R) and the delta E[log W] per trade if sizing used
      it -- at the row's current fraction (first order) and re-optimised (unit-R variance, stated).
      SIGNED_CONSUMERS names the signed functions that would have to read it. Nothing here
      changes a size, a status or a gate; the adoption is a separate, principal-signed change.

    python desks/mt5/research/cost_basis.py --once
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import cost_surfaces as cs  # noqa: E402

DATA = DESK / "data"
LEDGER = cs.LEDGER
DECISIONS = DATA / "decision_ledger.jsonl"
CORPUS = cs.CORPUS
SLEEVES = DATA / "sleeves.json"
UNIVERSE = cs.UNIVERSE
SURFACE = cs.OUT
OUT = DESK / "reports" / "COST_BASIS.json"
REAL_SURFACE = DESK / "reports" / "REAL_FILL_COST_SURFACE.json"

SCHEMA = "cost-basis-1"
UNMEASURED = "UNMEASURED"
MIN_N = cs.MIN_N
#: Pseudo-observations the modelled value is worth in the shrinkage.
SHRINK_K = 10.0
REAL_TERMS = ("spread_points", "slippage_points", "slippage_r", "commission_r")

#: Signed (immutable-evaluator) or sizing functions that would have to READ this to act on it.
SIGNED_CONSUMERS = (
    {"function": "desks/mt5/research/promoter.py:admission_of",
     "signed": True, "reads": "live_rows[].admission_view.cert_net_exp_r",
     "why": "admission judges certificate expectancy at modelled cost only"},
    {"function": "desks/mt5/scripts/external_gauntlet.py:costs_for",
     "signed": True, "reads": "real_surface.by_symbol_session[].terms (shrunk)",
     "why": "the sealed judge charges the pooled modelled spread"},
    {"function": "libs/portfolio/rails.py (survival rails / heat)",
     "signed": True, "reads": "live_rows[].sizing_view.delta_elogw_*",
     "why": "every capital modifier must prove its E[log W] -- this is the proof's input"},
    {"function": "libs/portfolio/capital_modifiers.py",
     "signed": True, "reads": "live_rows[].sizing_view",
     "why": "a realised-cost modifier must be two-sided and registered here"},
    {"function": "desks/mt5/research/pf_allocator.py:_execution_costs (cost_r, cost_bias_r)",
     "signed": False, "reads": "live_rows[].cost_basis.drift_r",
     "why": "cost_bias_r is the deterministic uncharged R; realised drift is its measured value"},
    {"function": "desks/mt5/mt5desk/sizing.py:risk_lot / decision_core.py:promoted_lot, "
                 "gold_book_lot",
     "signed": False, "reads": "nothing directly -- they size the allocator's fraction",
     "why": "allocator sovereignty: the change belongs upstream in pf_allocator, not here"},
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = cs._jsonl(path)
    return out


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(v: object) -> float | None:
    out: float | None = cs._f(v)
    return out


def direction_of_deal(row: dict[str, Any]) -> int | None:
    """+1 long / -1 short from the trade's own geometry (the deal `side` is the CLOSING deal's)."""
    e, sl, tp = _f(row.get("entry_price")), _f(row.get("sl")), _f(row.get("tp"))
    if e is not None and tp is not None and tp != e:
        return 1 if tp > e else -1
    if e is not None and sl is not None and sl != e:
        return 1 if sl < e else -1
    return None


def decision_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in rows:
        if str(d.get("outcome") or "") == "EXECUTED" and d.get("ticket") not in (None, ""):
            out[str(d["ticket"])] = d
    return out


def _risk_ccy(row: dict[str, Any], meta: dict[str, Any]) -> float | None:
    pl, r = _f(row.get("pl_quote")), _f(row.get("r_multiple"))
    if pl is not None and r and abs(r) > 1e-9 and not row.get("r_unreconstructible"):
        v = abs(pl / r)
        if v > 0:
            return v
    rq = _f(row.get("risk_quote"))
    if rq and rq > 0:
        return rq
    return cs._risk_account(row, meta)


def match(ledger: list[dict[str, Any]], decisions: list[dict[str, Any]],
          corpus: list[dict[str, Any]], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """One measured trade per closed deal whose decision row is found by exact ticket."""
    idx = decision_index(decisions)
    spreads: dict[str, float] = {}
    for c in corpus:
        t, pt = c.get("ticket"), _f(c.get("point"))
        sp = _f(c.get("spread_points_at_decision"))
        if sp is None:
            sf = _f(c.get("spread_frac_at_fill")) or _f(c.get("spread_frac_at_decision"))
            px = _f(c.get("fill_price")) or _f(c.get("requested_price"))
            ts = _f((meta.get(str(c.get("symbol") or "")) or {}).get("tick_size"))
            pt = pt or ts
            if sf is not None and px and pt:
                sp = sf * px / pt
        if t not in (None, "") and sp is not None:
            spreads[str(t)] = sp
    out = []
    for row in ledger:
        dec = None
        for k in ("entry_order", "position_id", "order"):
            v = row.get(k)
            if v not in (None, "") and str(v) in idx:
                dec = idx[str(v)]
                break
        if dec is None:
            continue
        sym = str(row.get("symbol") or dec.get("symbol") or "")
        m = meta.get(sym) or {}
        point = _f(m.get("tick_size")) or _f(m.get("point"))
        d = direction_of_deal(row)
        fill, req = _f(row.get("entry_price")), _f(dec.get("price"))
        sl = _f(row.get("sl")) or _f(dec.get("sl"))
        slip_px = (fill - req) * d if (fill is not None and req is not None and d) else None
        stop = abs(fill - sl) if (fill is not None and sl) else None
        risk = _risk_ccy(row, meta)
        fees = [x for x in (_f(row.get("commission")), _f(row.get("entry_cost_allocated")),
                            _f(row.get("exit_fee"))) if x is not None]
        # entry_cost_allocated duplicates commission when both are booked; take the larger cost.
        fee = (min(_f(row.get("commission")) or 0.0, _f(row.get("entry_cost_allocated")) or 0.0)
               + (_f(row.get("exit_fee")) or 0.0)) if fees else None
        hour = cs._hour(row.get("entry_time") or dec.get("decided_at") or row.get("time"))
        tk = next((str(row.get(k)) for k in ("entry_order", "position_id")
                   if str(row.get(k)) in spreads), None)
        out.append({
            "sleeve": str(row.get("sleeve") or dec.get("sleeve") or ""),
            "symbol": sym, "session": cs.session_of(hour), "hour": hour,
            "ticket": dec.get("ticket"), "decision_id": dec.get("decision_id"),
            "spread_points": spreads.get(tk) if tk else None,
            "slippage_points": (slip_px / point) if (slip_px is not None and point) else None,
            "slippage_r": (slip_px / stop) if (slip_px is not None and stop) else None,
            "commission_r": (-fee / risk) if (fee is not None and risk) else None,
            "r_multiple": (None if row.get("r_unreconstructible")
                           else _f(row.get("r_multiple"))),
        })
    return out


def _shrink(values: list[float], modelled: float | None) -> dict[str, Any]:
    n = len(values)
    realised = statistics.median(values) if values else None
    out: dict[str, Any] = {"n": n, "modelled": modelled,
                           "realised": None if realised is None else round(realised, 6)}
    if modelled is not None and realised is not None:
        out.update(status="SHRUNK", value=round((n * realised + SHRINK_K * modelled)
                                                / (n + SHRINK_K), 6), source="realised_shrunk")
    elif modelled is not None:
        out.update(status="MODELLED", value=modelled, source="modelled_only")
    elif n >= MIN_N and realised is not None:
        out.update(status="MEASURED", value=round(realised, 6), source="realised_only")
    else:
        out.update(status=UNMEASURED, source="none")
    return out


def _modelled(symbol: str, session: str | None, surface: dict[str, Any]) -> dict[str, Any]:
    c = cs.cost_for(symbol, session=session, surface=surface) if surface else {"terms": {}}
    out: dict[str, Any] = {}
    for t in REAL_TERMS:
        v = (c.get("terms") or {}).get(t) or {}
        out[t] = _f(v.get("value")) if v.get("status") in ("MEASURED", "PRIOR") else None
    return out


def _cell(trades: list[dict[str, Any]], modelled: dict[str, Any]) -> dict[str, Any]:
    terms = {t: _shrink([x[t] for x in trades if x.get(t) is not None], modelled.get(t))
             for t in REAL_TERMS}
    return {"n": len(trades), "terms": terms}


def surface_of(trades: list[dict[str, Any]], surface: dict[str, Any]) -> dict[str, Any]:
    by_sym: dict[str, list[dict[str, Any]]] = {}
    by_ss: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        by_sym.setdefault(t["symbol"], []).append(t)
        by_ss.setdefault(f"{t['symbol']}|{t['session']}", []).append(t)
    return {
        "by_symbol": {s: _cell(v, _modelled(s, None, surface)) for s, v in sorted(by_sym.items())},
        "by_symbol_session": {k: _cell(v, _modelled(k.split("|", 1)[0], k.split("|", 1)[1],
                                                     surface))
                              for k, v in sorted(by_ss.items())},
    }


def _cost_r(terms: dict[str, Any], key: str) -> float | None:
    """Slip + commission in R from a cell's terms (spread is in points, already in the fill)."""
    vals = [(terms.get(t) or {}).get(key) for t in ("slippage_r", "commission_r")]
    if any(v is None for v in vals):
        return None
    return float(sum(vals))  # type: ignore[arg-type]


def _cert_exp(row: dict[str, Any]) -> float | None:
    for k in ("cert_expectancy_r", "expectancy_r", "cert_expectancy", "shadow_exp"):
        v = _f(row.get(k))
        if v is not None:
            return v
    return None


VAR_MIN_N = 5
VAR_KEYS = (("shadow_var_r", 1), ("forward_var_r", 1), ("shadow_sd_r", 2),
            ("forward_sd_r", 2), ("shadow_sd", 2), ("forward_sd", 2))
NESTED_STATS = ("shadow", "forward", "shadow_stats", "forward_stats")


def r_variance(row: dict[str, Any], own: list[dict[str, Any]]) -> tuple[float, str]:
    """The sleeve's measured per-trade R variance: own fills (n>=5), then shadow/forward
    stats, else 1.0 as a LABELLED fallback (never presented as measured)."""
    rs = [x["r_multiple"] for x in own if x.get("r_multiple") is not None]
    if len(rs) >= VAR_MIN_N:
        v = statistics.variance(rs)
        if v > 0:
            return v, f"own_matched_trades(n={len(rs)})"
    cands: list[tuple[str, dict[str, Any]]] = [("row", row)]
    cands += [(k, row[k]) for k in NESTED_STATS if isinstance(row.get(k), dict)]
    for where, d in cands:
        for k, power in VAR_KEYS + (("var_r", 1), ("sd_r", 2), ("var", 1), ("sd", 2),
                                    ("std", 2)):
            if where == "row" and not k.startswith(("shadow", "forward")):
                continue
            x = _f(d.get(k))
            if x is not None and x > 0:
                return x ** power, f"{where}.{k}" if where != "row" else k
    return 1.0, "FALLBACK_UNIT_VARIANCE"


def basis_for(row: dict[str, Any], trades: list[dict[str, Any]], real: dict[str, Any],
              surface: dict[str, Any]) -> dict[str, Any]:
    name, sym = str(row.get("name") or ""), str(row.get("symbol") or "")
    own = [t for t in trades if t["sleeve"] == name]
    if len(own) >= MIN_N:
        cell, source = _cell(own, _modelled(sym, None, surface)), "own_fills"
    elif sym in real["by_symbol"]:
        cell, source = real["by_symbol"][sym], "symbol_fills"
    else:
        cell, source = _cell([], _modelled(sym, None, surface)), "modelled_only"
    terms = cell["terms"]
    real_r = _cost_r({t: {"v": (terms[t].get("realised") if terms[t]["n"] >= MIN_N else None)}
                      for t in terms}, "v")
    model_r = _cost_r({t: {"v": terms[t].get("modelled")} for t in terms}, "v")
    shrunk_r = _cost_r({t: {"v": terms[t].get("value")} for t in terms}, "v")
    drift = (shrunk_r - model_r) if (shrunk_r is not None and model_r is not None) else (
        shrunk_r if (shrunk_r is not None and cell["n"] >= MIN_N) else None)
    basis = {"symbol": sym, "source": source if cell["n"] else "modelled_only",
             "n": cell["n"], "n_own": len(own), "terms": terms,
             "modelled_cost_r": model_r, "realised_cost_r": real_r,
             "shrunk_cost_r": shrunk_r,
             "drift_r": None if drift is None else round(drift, 6),
             "drift_basis": ("shrunk minus modelled slip+commission" if model_r is not None else
                             "realised slip+commission: the certificate's judge (external_gauntlet"
                             ".costs_for) charges spread only, so these terms were uncharged"),
             "status": "MEASURED" if drift is not None else UNMEASURED}
    cert = _cert_exp(row)
    f = _f(row.get("risk_frac")) or _f((row.get("admission") or {}).get("risk_frac")) or 0.0
    adm: dict[str, Any] = {"cert_exp_r": cert, "cert_net_exp_r": None, "status": UNMEASURED}
    var_r, var_src = r_variance(row, own)
    siz: dict[str, Any] = {"risk_frac": f, "delta_elogw_at_current_f": None,
                           "delta_elogw_reoptimised": None, "status": UNMEASURED,
                           "variance_r": var_r, "variance_source": var_src,
                           "assumption": ("E[log W] ~ f mu - f^2 var/2; re-optimised f* = mu/var"
                                          + ("; var=1 is a FALLBACK, not measured"
                                             if var_src == "FALLBACK_UNIT_VARIANCE" else ""))}
    if cert is not None and drift is not None:
        net = cert - drift
        adm.update(cert_net_exp_r=round(net, 6), status="MEASURED",
                   would_flip_sign=(cert > 0) != (net > 0))
        siz.update(status="MEASURED",
                   delta_elogw_at_current_f=round(f * (net - cert), 8),
                   delta_elogw_reoptimised=round(
                       (max(net, 0.0) ** 2 - max(cert, 0.0) ** 2) / (2 * var_r), 8))
    return {"name": name, "status": row.get("status"), "cost_basis": basis,
            "admission_view": adm, "sizing_view": siz}


def build(*, ledger: list[dict[str, Any]] | None = None,
          decisions: list[dict[str, Any]] | None = None,
          corpus: list[dict[str, Any]] | None = None, sleeves: Any = None,
          universe: Any = None, surface: dict[str, Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    ledger = _jsonl(LEDGER) if ledger is None else ledger
    decisions = _jsonl(DECISIONS) if decisions is None else decisions
    corpus = _jsonl(CORPUS) if corpus is None else corpus
    sleeves = _json(SLEEVES) if sleeves is None else sleeves
    universe = _json(UNIVERSE) if universe is None else universe
    surface = (_json(SURFACE) or {}) if surface is None else surface
    u = universe or {}
    meta = u.get("symbols", u) if isinstance(u, dict) else {}
    meta = meta if isinstance(meta, dict) else {}
    trades = match(ledger, decisions, corpus, meta)
    real = surface_of(trades, surface)
    rows = (sleeves or {}).get("sleeves", []) if isinstance(sleeves, dict) else []
    live = [r for r in rows if isinstance(r, dict) and r.get("status") == "LIVE"]
    live_rows = [basis_for(r, trades, real, surface) for r in live]
    traded = sorted({t["sleeve"] for t in trades} - {r.get("name") for r in live})
    n_closed = len(ledger)
    return {
        "schema": SCHEMA, "report_only": True,
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "n_closed_deals": n_closed, "n_matched": len(trades),
        "matched_share": (round(len(trades) / n_closed, 4) if n_closed else UNMEASURED),
        "n_live_rows": len(live), "n_live_with_basis": sum(
            1 for r in live_rows if r["cost_basis"]["status"] == "MEASURED"),
        "shrink_k": SHRINK_K, "min_n": MIN_N,
        "join": "decision_ledger EXECUTED ticket == live_ledger entry_order | position_id | order",
        "real_surface": real, "live_rows": live_rows,
        "traded_sleeves_not_live_in_sleeves_json": traded,
        "signed_consumers": list(SIGNED_CONSUMERS),
        "note": "Report only: no size, status or gate reads this until a signed change adopts it.",
    }


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--surface-out", type=Path, default=REAL_SURFACE)
    args = ap.parse_args(argv)
    doc = build()
    _write(args.out, doc)
    _write(args.surface_out, {"schema": SCHEMA, "generated_at": doc["generated_at"],
                              "n_matched": doc["n_matched"], **doc["real_surface"]})
    print(f"cost_basis: matched {doc['n_matched']}/{doc['n_closed_deals']} deals, "
          f"{doc['n_live_with_basis']}/{doc['n_live_rows']} LIVE rows with a measured basis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
