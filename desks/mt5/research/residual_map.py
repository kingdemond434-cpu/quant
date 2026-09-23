"""B8 -- THE MAP OF WHAT THE DESK CANNOT EXPLAIN, and the prior that aims the search at it.

THE BLUEPRINT ITEM: "unknown-unknowns engine: search where the ontology is weakest". THE GAP, in
the ledger's words: "undirected exogenous search only; no residual/error map of unexplained P&L,
calibration holes or anomalous execution".

`unknown_unknowns` already hunts anomalies in PRICE space -- extreme moves with no event,
decouplings, volatility breaks -- and it hunts them in whatever order the live symbol list
happens to be in. That is a search with no aim. The observations that carry the most information
about a missing word are the ones where the desk's OWN models were wrong, and the desk measures
that in three places it never joined:

    UNEXPLAINED P&L   `allocator_attribution.json` -- realised growth per sleeve against the
                      model that sized it, and the `terms` block's realised_sd against model_sd.
                      Measured 2026-09-23 on this box: realised_sd 0.1399 against model_sd
                      0.0075, an eighteen-fold under-dispersion that no generator was ever told
                      about.
    CALIBRATION HOLES `EDGE_RELIABILITY.json` and `EDGE_CONFIDENCE.json` -- where a stated edge
                      and its realised frequency disagree, per sleeve.
    EXECUTION         `MARKOUT.json` and `FILL_ATTRIBUTION.json` -- slippage the cost model did
                      not predict, and the share of edge it ate.

WHAT IT PRODUCES. One ranked map of residual CELLS (symbol, sleeve, kind) by the size of what is
unexplained, and a per-symbol PRIOR weight written where `unknown_unknowns` reads it. The prior
ORDERS the scan; it never shortens it. Nothing is excluded, because a symbol the desk explains
today is exactly where an unknown unknown is most invisible, and a search that stopped looking
there would be a cap on discovery dressed as focus.

    python desks/mt5/research/residual_map.py [--once] [--budget-s N]
        -> desks/mt5/reports/RESIDUAL_MAP.json  (+ data/residual_prior.json)
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
R = DESK / "reports"
OUT = R / "RESIDUAL_MAP.json"
PRIOR = DESK / "data" / "residual_prior.json"

ATTRIBUTION = R / "allocator_attribution.json"
RELIABILITY = R / "EDGE_RELIABILITY.json"
CONFIDENCE = R / "EDGE_CONFIDENCE.json"
MARKOUT = R / "markout.json"
FILLS = R / "FILL_ATTRIBUTION.json"

#: The floor every symbol keeps in the prior. The map ORDERS the search; it never empties a cell.
FLOOR_W = 0.25


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _sym_of(name: str) -> str:
    """The instrument a sleeve name starts with. Sleeve names on this desk are
    `<SYMBOL>_<family>_<selector>` or `<SYMBOL>.<clock>`; both split here."""
    head = str(name or "").split(".", 1)[0]
    return head.split("_", 1)[0].upper()


def _pnl_residuals() -> list[dict[str, Any]]:
    """Growth the allocator's model did not account for, per sleeve, plus the dispersion gap."""
    doc = _read(ATTRIBUTION)
    rows: list[dict[str, Any]] = []
    per = doc.get("per_sleeve") if isinstance(doc.get("per_sleeve"), dict) else {}
    book = per.get("sleeves") if isinstance(per.get("sleeves"), dict) else {}
    model = doc.get("dlogw_per_day") if isinstance(doc.get("dlogw_per_day"), dict) else {}
    try:
        model_mu = float(model.get("value"))
    except (TypeError, ValueError):
        model_mu = None
    for name, row in book.items():
        if not isinstance(row, dict):
            continue
        try:
            v, n = float(row.get("value")), int(row.get("n") or 0)
        except (TypeError, ValueError):
            continue
        if model_mu is None or n <= 0:
            continue
        resid = v - model_mu
        rows.append({"kind": "unexplained_pnl", "cell": str(name), "symbol": _sym_of(name),
                     "residual": round(resid, 8), "magnitude": round(abs(resid), 8), "n": n,
                     "why": (f"realised {v:.6f} log-wealth/day against the book's modelled "
                             f"{model_mu:.6f} over {n} observation(s)")})
    terms = doc.get("terms") if isinstance(doc.get("terms"), dict) else {}
    for term, row in terms.items():
        if not isinstance(row, dict):
            continue
        try:
            rsd, msd = float(row.get("realized_sd")), float(row.get("model_sd"))
        except (TypeError, ValueError):
            continue
        if msd <= 0 or rsd <= 0:
            continue
        ratio = rsd / msd
        if ratio < 1.5 and ratio > 0.67:
            continue
        rows.append({"kind": "dispersion_gap", "cell": f"term:{term}", "symbol": "*",
                     "residual": round(math.log(ratio), 6),
                     "magnitude": round(abs(math.log(ratio)), 6),
                     "n": int(row.get("scored_days") or 0),
                     "why": (f"the {term} term's realised sd is {ratio:.1f}x its modelled sd -- "
                             f"the book is being sized by a model whose uncertainty is wrong by "
                             f"that factor")})
    return rows


def _calibration_holes() -> list[dict[str, Any]]:
    """Where a stated edge and what actually happened disagree."""
    rows: list[dict[str, Any]] = []
    rel = _read(RELIABILITY)
    sleeves = rel.get("sleeves") if isinstance(rel.get("sleeves"), dict) else {}
    for name, row in sleeves.items():
        if not isinstance(row, dict):
            continue
        stated = row.get("claimed_r") if row.get("claimed_r") is not None else row.get("expected_r")
        realised = (row.get("realised_r") if row.get("realised_r") is not None
                    else row.get("actual_r"))
        try:
            s, a = float(stated), float(realised)
        except (TypeError, ValueError):
            continue
        gap = a - s
        if abs(gap) < 1e-9:
            continue
        rows.append({"kind": "calibration_hole", "cell": str(name), "symbol": _sym_of(name),
                     "residual": round(gap, 6), "magnitude": round(abs(gap), 6),
                     "n": int(row.get("n") or row.get("n_trades") or 0),
                     "why": f"stated {s:.4f}R per trade, realised {a:.4f}R"})
    conf = _read(CONFIDENCE)
    edges = conf.get("edges") if isinstance(conf.get("edges"), dict) else {}
    for name, row in edges.items():
        if not isinstance(row, dict):
            continue
        z = row.get("z") if row.get("z") is not None else row.get("edge_z")
        try:
            zz = float(z)
        except (TypeError, ValueError):
            continue
        if abs(zz) < 2.0:
            continue
        rows.append({"kind": "confidence_outlier", "cell": str(name), "symbol": _sym_of(name),
                     "residual": round(zz, 4), "magnitude": round(abs(zz), 4),
                     "n": int(row.get("n") or 0),
                     "why": f"edge z = {zz:.2f}: the stated confidence and the sample disagree"})
    return rows


def _execution_anomalies() -> list[dict[str, Any]]:
    """Slippage and fill behaviour the cost model did not predict."""
    rows: list[dict[str, Any]] = []
    mk = _read(MARKOUT)
    try:
        slip = float(mk.get("mean_slip_r"))
        n = int(mk.get("n_matched") or 0)
    except (TypeError, ValueError):
        slip, n = None, 0
    if slip is not None and n > 0 and abs(slip) > 0.01:
        rows.append({"kind": "execution_slippage", "cell": "book", "symbol": "*",
                     "residual": round(slip, 5), "magnitude": round(abs(slip), 5), "n": n,
                     "why": (f"mean slippage {slip:.4f}R over {n} matched fill(s); the replay "
                             f"charged a pooled spread and the venue charged this")})
    fa = _read(FILLS)
    by_sleeve = fa.get("by_sleeve") if isinstance(fa.get("by_sleeve"), dict) else {}
    for name, row in by_sleeve.items():
        if not isinstance(row, dict):
            continue
        try:
            miss = float(row.get("unfilled_share") or row.get("miss_rate"))
        except (TypeError, ValueError):
            continue
        if miss <= 0.1:
            continue
        rows.append({"kind": "execution_unfilled", "cell": str(name), "symbol": _sym_of(name),
                     "residual": round(miss, 4), "magnitude": round(miss, 4),
                     "n": int(row.get("n") or 0),
                     "why": f"{miss:.0%} of this sleeve's intents did not become fills"})
    return rows


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rows = _pnl_residuals() + _calibration_holes() + _execution_anomalies()
    rows.sort(key=lambda r: -float(r["magnitude"]))
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[str(r["kind"])] = by_kind.get(str(r["kind"]), 0) + 1
    # THE PRIOR: a per-symbol weight in [FLOOR_W, 1.0], normalised on the largest residual seen.
    # `*` rows (book-level) lift every symbol equally rather than none, because a book-level
    # miscalibration is a question about every instrument in it.
    mags: dict[str, float] = {}
    globally = 0.0
    for r in rows:
        sym = str(r["symbol"])
        if sym == "*":
            globally = max(globally, float(r["magnitude"]))
            continue
        mags[sym] = max(mags.get(sym, 0.0), float(r["magnitude"]))
    top = max([*mags.values(), globally, 1e-12])
    prior = {sym: round(FLOOR_W + (1.0 - FLOOR_W) * (m / top), 4) for sym, m in mags.items()}
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK" if rows else "QUIET",
        "n_residuals": len(rows), "by_kind": by_kind,
        "residuals": rows[:80],
        "prior": {"by_symbol": prior, "floor": FLOOR_W,
                  "book_level_magnitude": round(globally, 6),
                  "rule": ("weight in [floor, 1] on the largest residual the desk carries for "
                           "that instrument; the floor guarantees every symbol is still "
                           "searched, because a symbol the models explain today is exactly "
                           "where an unknown unknown is least visible")},
        "inputs": {"allocator_attribution": ATTRIBUTION.exists(),
                   "edge_reliability": RELIABILITY.exists(),
                   "edge_confidence": CONFIDENCE.exists(),
                   "markout": MARKOUT.exists(), "fill_attribution": FILLS.exists()},
        "consumers": ["desks/mt5/research/unknown_unknowns.py::_live_symbols (search order)",
                      "desks/mt5/research/research_tree.py (residual branches, when present)"],
        "boundary": ("this organ measures and ranks. It trades nothing, sizes nothing and "
                     "excludes nothing from any search: it changes the ORDER a bounded scan "
                     "visits its cells in, which is the only lever a fixed budget leaves."),
        "why": ("a search that can only recombine what it already represents cannot find what it "
                "has no word for. The desk's own residuals are the only observations that carry "
                "information about the missing word, and until now nothing pointed the search "
                "at them."),
    }
    return doc


def load_prior() -> tuple[dict[str, float], str]:
    """Consumer helper: the per-symbol search weights, or an empty map with the reason."""
    doc = _read(PRIOR)
    by = doc.get("by_symbol") if isinstance(doc.get("by_symbol"), dict) else {}
    if not by:
        return {}, "no residual prior on disk: the search keeps its natural order"
    return ({str(k): float(v) for k, v in by.items()},
            f"{len(by)} symbol(s) weighted by measured residual, floor {doc.get('floor')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    PRIOR.parent.mkdir(parents=True, exist_ok=True)
    PRIOR.write_text(json.dumps({"at": doc["at"], **doc["prior"]}, indent=1), encoding="utf-8")
    print(f"residual map: {doc['status']}  {doc['n_residuals']} residual(s) {doc['by_kind']}")
    for r in doc["residuals"][:8]:
        print(f"  {r['kind']:<20} {str(r['cell'])[:34]:<34} |{r['magnitude']}|  {r['why'][:70]}")
    print(f"-> {OUT}; prior -> {PRIOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
