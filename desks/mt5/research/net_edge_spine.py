"""THE NET-EDGE SPINE: the whole desk's currency becomes edge AFTER every cost it actually pays.

THE PRINCIPAL'S ORDER: an institution that trades all global public information for "maximum
edge possible of NET". Before this organ the desk ranked candidates on `expected_value.ev`,
ranked forward slots on a gross `slot_value`, and sized the book on a gross posterior -- while
the spread lived in `cost_surface`, the swap in `cost_to_edge`, the commission in `fusion_cost`,
the impact in `impact_lab` and the multiplicity charge inside the sealed gauntlet. Five organs
each knew one cost and NO decision saw all five at once.

This is the spine that joins them. `libs/research/net_edge.py` is the one function; this organ
feeds it the desk's own artifacts and applies it at THREE DOORS:

  (a) INTAKE       `data/net_edge_ranks.json` carries net, gross, the decomposition and the
                   verdict per (symbol, family). `miner_candidate_compiler` reads it, ranks its
                   compiled candidates by NET, and stamps a COST_DEAD cell with its
                   decomposition instead of dropping it. Every COST_DEAD cell is DONATED back
                   to the intake as a LOWER-TURNOVER descendant (seat `net_edge`), which is the
                   `cost_dead -> lower_turnover_descendant` route `libs.research.coevolution_lab`
                   already declares. A cell killed by cost is a cell that must be retried at a
                   longer horizon, never a cell that disappears.
  (b) FORWARD SLOT `forward_slot_ranker` publishes `net_slot_value` beside `slot_value`: the
                   same slot value scaled by the cell's own net/gross ratio, so the scarcest
                   thing this desk owns goes to the highest NET expected E[log W]. `slot_value`
                   is never overwritten -- a reader must be able to see the two disagree.
  (c) ALLOCATOR    `libs/portfolio/allocator_evidence.py` gains a `net_of_cost` term built from
                   this artifact and a per-sleeve CAPACITY (the size at which net decays to
                   zero), so the book sizes on what it can actually carry.

AND BACKWARD (item 3): every closed live trade in `COUNTERFACTUAL_ATTRIBUTION.json` is compared
against what this cost model PREDICTED, so the model that prices the book is itself priced. A
cost model that is never scored against the tape is a claim the desk cannot cash (L1.49).

GROWTH GOVERNANCE, both rules. Nothing here vetoes, caps or shrinks anything: COST_DEAD is a
RANKING and a DONATION, not a gate, the sealed judge is untouched, and every COST_DEAD verdict
is billed as a missed-growth line in forward log-wealth. `reweight_preserving_heat` moves heat
toward higher net and returns a book with exactly the heat it was given, so the published
reallocation is provably two-sided: it reallocates, it never reduces.

    python desks/mt5/research/net_edge_spine.py --once --budget-s 600 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import net_edge as NE  # noqa: E402

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "NET_EDGE.json"
#: The small, stable join file the three doors read. The big report is for humans; this is the
#: contract, so a door never has to parse the whole decomposition to rank on net.
RANKS = DATA / "net_edge_ranks.json"

COST_TO_EDGE = REPORTS / "COST_TO_EDGE.json"
FUSION_COST = REPORTS / "FUSION_COST.json"
EXEC_SURFACE = REPORTS / "EXECUTION_COST_SURFACE.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
POSTERIOR = REPORTS / "POSTERIOR_ALPHA.json"
SLOTS = REPORTS / "FORWARD_SLOT_RANKER.json"
CAPACITY = REPORTS / "CAPACITY.json"
ATTRIBUTION = REPORTS / "COUNTERFACTUAL_ATTRIBUTION.json"
IMPACT = REPORTS / "IMPACT_LAB.json"
ALLOCATION = REPORTS / "pf_allocation.json"

SEAT = "net_edge"
RULE = ("net = gross - spread/slippage at the cell's own size and state - market impact at that "
        "size - financing and swap over the holding period - commission - the multiplicity "
        "charge already owed. An UNMEASURED term is never a zero: it makes the net a BOUND and "
        "the verdict says so. Nothing here vetoes, caps or sizes: COST_DEAD is a ranking and a "
        "donation, every refusal is billed as a missed-growth line, and the heat total is "
        "preserved exactly by reweight_preserving_heat.")


# ------------------------------------------------------------------------------------ inputs


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def cost_index(doc: Any) -> dict[tuple[str, str], dict[str, Any]]:
    """(symbol, family) -> the desk's measured spread and swap in R, from `cost_to_edge`.

    The empty family is also indexed, so a row whose family the cost report never priced still
    falls back to the same SYMBOL's reading rather than to nothing. It never falls back to a
    desk-wide average: a pooled scalar is the thing the cost surface exists to end.
    """
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in ((doc or {}).get("by_cost") or []) if isinstance(doc, dict) else []:
        if not isinstance(row, dict) or not row.get("measured"):
            continue
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
        if not sym:
            continue
        out.setdefault((sym, fam), row)
        out.setdefault((sym, ""), row)
    return out


def fusion_index(doc: Any) -> dict[str, dict[str, Any]]:
    """symbol -> the venue's round-trip split, so commission is its OWN term and not a blur."""
    out: dict[str, dict[str, Any]] = {}
    for row in ((doc or {}).get("symbols") or []) if isinstance(doc, dict) else []:
        if isinstance(row, dict) and row.get("symbol"):
            out[str(row["symbol"])] = row
    return out


def rate_index(doc: Any) -> dict[tuple[str, str], float]:
    """(symbol, family) -> measured trades per day, from the forward slot ranker's own rows."""
    out: dict[tuple[str, str], float] = {}
    for block in ("running", "waiting"):
        for row in ((doc or {}).get(block) or []) if isinstance(doc, dict) else []:
            if not isinstance(row, dict):
                continue
            rate = _f(row.get("trade_rate_per_day"))
            if rate is None or rate <= 0:
                continue
            key = (str(row.get("symbol") or ""), str(row.get("family") or ""))
            out.setdefault(key, rate)
            out.setdefault((key[0], ""), rate)
    return out


def slot_index(doc: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for block in ("running", "waiting"):
        for row in ((doc or {}).get(block) or []) if isinstance(doc, dict) else []:
            if isinstance(row, dict):
                key = f"{row.get('symbol') or ''}|{row.get('family') or ''}"
                out.setdefault(key, row)
    return out


def impact_reference(impact_doc: Any, capacity_doc: Any) -> dict[str, Any]:
    """The one measured (size, realised impact) pair every capacity number is solved from.

    `CAPACITY.json` already records why it has none -- "market impact needs realised fills and
    matched_fills is 0" -- and that is repeated here rather than replaced by an assumption. No
    reference means every capacity is UNMEASURED, which is NOT the same as unlimited.
    """
    lab = impact_doc if isinstance(impact_doc, dict) else {}
    ref_lots = _f(lab.get("reference_lots")) or _f((lab.get("kyle") or {}).get("reference_lots"))
    ref_r = _f(lab.get("reference_impact_r")) or _f((lab.get("kyle") or {}).get("impact_r"))
    if ref_lots and ref_r and ref_lots > 0 and ref_r > 0:
        return {"ref_lots": ref_lots, "ref_impact_r": ref_r, "status": NE.MEASURED,
                "source": "reports/IMPACT_LAB.json"}
    why = "reports/IMPACT_LAB.json carries no measured (size, impact) reference on this host"
    cap = capacity_doc if isinstance(capacity_doc, dict) else {}
    for row in (cap.get("rows") or []):
        if isinstance(row, dict) and row.get("ceiling_why"):
            why = str(row["ceiling_why"])
            break
    return {"ref_lots": None, "ref_impact_r": None, "status": NE.UNMEASURED, "why": why}


# ------------------------------------------------------------------------------- the terms


def spread_term(cost_row: dict[str, Any] | None, exec_cell: dict[str, Any] | None) -> NE.CostTerm:
    """The desk's REALISED all-in execution cost where it has traded the cell; the venue's
    modelled spread where it has not. Never zero for a cell nobody has priced."""
    if exec_cell and _f(exec_cell.get("cost_r")) is not None:
        return NE.measured("spread_slippage", float(exec_cell["cost_r"]),
                           "reports/EXECUTION_COST_SURFACE.json",
                           f"realised, resolved at {exec_cell.get('resolved_at')} "
                           f"over n={exec_cell.get('n')}")
    if cost_row and _f(cost_row.get("spread_r")) is not None:
        return NE.modelled("spread_slippage", float(cost_row["spread_r"]),
                           "reports/COST_TO_EDGE.json spread_r",
                           f"{cost_row.get('spread_pts')} pts over a "
                           f"{cost_row.get('stop_pts')} pt stop")
    return NE.unpriced("spread_slippage",
                       "no realised deal and no modelled spread for this cell: the crossing "
                       "cost is unmeasured, which is not the same as free")


def financing_term(cost_row: dict[str, Any] | None) -> NE.CostTerm:
    """Swap and carry over the holding period, from the desk's own overnight determination."""
    if cost_row is None or _f(cost_row.get("swap_r")) is None:
        return NE.unpriced("financing",
                           "no swap reading for this cell; financing is the one SIGNED term "
                           "(a carry can be a credit), so its absence is not a zero either way")
    holds = bool(cost_row.get("holds_overnight"))
    return NE.measured("financing", float(cost_row["swap_r"]),
                       "reports/COST_TO_EDGE.json swap_r",
                       f"{'holds overnight' if holds else 'intraday: no rollover is paid'}; "
                       f"worse side {cost_row.get('swap_pts_worse_side')} pts")


def commission_term(cost_row: dict[str, Any] | None,
                    fusion_row: dict[str, Any] | None) -> NE.CostTerm:
    """Commission as its OWN term, from the venue's round-trip split.

    `fusion_cost` publishes the round trip per lot under RAW (spread + commission) and ZERO
    (commission only), so commission/spread = ZERO/(RAW - ZERO) is exact and needs no lot-to-R
    conversion: it rides on the spread term already in R. A symbol charged ZERO spread has no
    spread to ride on, and its commission is UNMEASURED rather than invented.
    """
    if cost_row is None or fusion_row is None:
        return NE.unpriced("commission", "no fusion round-trip reading joins this cell")
    spread_r = _f(cost_row.get("spread_r"))
    rt = fusion_row.get("round_trip_per_lot") or {}
    raw, zero = _f(rt.get("RAW")), _f(rt.get("ZERO"))
    if spread_r is None or raw is None or zero is None or raw <= zero:
        return NE.unpriced("commission",
                           f"{fusion_row.get('symbol')} is charged no separable spread "
                           f"(RAW={raw}, ZERO={zero}): its commission cannot be expressed as a "
                           "multiple of the spread term and is unmeasured, not zero")
    ratio = zero / (raw - zero)
    return NE.modelled("commission", spread_r * ratio, "reports/FUSION_COST.json",
                       f"commission is {zero:.4f}/{raw:.4f} of the raw round trip -> "
                       f"{ratio:.4f}x the spread term")


def multiplicity_term(gates: dict[str, Any] | None, sigma_r: float | None) -> NE.CostTerm:
    """The deflated-Sharpe hurdle the SEALED gauntlet already charged, restated in R."""
    if not isinstance(gates, dict):
        return NE.unpriced("multiplicity",
                           "this cell carries no gauntlet certificate, so the trial charge it "
                           "owes is unmeasured; it is not a cell that owes nothing")
    ds = gates.get("deflated_sharpe") or {}
    return NE.multiplicity_charge(_f(ds.get("sr0")), sigma_r,
                                  n_trials=int(_f(ds.get("n_trials")) or 0) or None)


# ------------------------------------------------------------------------------- the rows


def survivor_rows(surv: Any, costs: dict[tuple[str, str], dict[str, Any]],
                  fusion: dict[str, dict[str, Any]], exec_cells: dict[str, dict[str, Any]],
                  ) -> list[NE.NetEdge]:
    """Every ten-gate certificate, priced in R PER TRADE -- the intake's own unit."""
    rows: list[NE.NetEdge] = []
    for key, rec in (((surv or {}).get("survivors") or {}) if isinstance(surv, dict)
                     else {}).items():
        if not isinstance(rec, dict):
            continue
        spec = rec.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or rec.get("sym") or "")
        fam = str(spec.get("family") or "")
        gates = rec.get("gates") or {}
        ev = _f((gates.get("expected_value") or {}).get("ev"))
        sharpe = _f((gates.get("in_sample_screen") or {}).get("sharpe"))
        # sigma per trade from the cell's OWN two published numbers: mean / Sharpe.
        sigma = (abs(ev) / sharpe) if (ev is not None and sharpe and sharpe > 0) else None
        cost_row = costs.get((sym, fam)) or costs.get((sym, ""))
        rows.append(NE.net_edge(
            str(key), ev, unit=NE.R_PER_TRADE, symbol=sym, family=fam, lane="certificate",
            gross_source="UNIVERSAL_SURVIVORS gates.expected_value.ev", n=_f(rec.get("days")),
            spread_slippage=spread_term(cost_row, exec_cells.get(sym)),
            financing=financing_term(cost_row),
            commission=commission_term(cost_row, fusion.get(sym)),
            multiplicity=multiplicity_term(gates, sigma)))
    return rows


def posterior_rows(post: Any, costs: dict[tuple[str, str], dict[str, Any]],
                   fusion: dict[str, dict[str, Any]], exec_cells: dict[str, dict[str, Any]],
                   rates: dict[tuple[str, str], float],
                   sr0_by_cell: dict[tuple[str, str], tuple[float, int]]) -> list[NE.NetEdge]:
    """Every forward sleeve's hierarchical posterior, priced in R PER DAY at its measured rate.

    A sleeve with no measured trade rate keeps its per-day edge and gets every cost term
    UNMEASURED with the reason, because a per-trade cost and a per-day edge do not compare.
    """
    rows: list[NE.NetEdge] = []
    for rec in ((post or {}).get("sleeves") or []) if isinstance(post, dict) else []:
        if not isinstance(rec, dict):
            continue
        sym, fam = str(rec.get("symbol") or ""), str(rec.get("family") or "")
        mu = _f(rec.get("mu_mean"))
        sharpe_pp = _f(rec.get("sharpe_pp"))
        rate = rates.get((sym, fam)) or rates.get((sym, ""))
        sigma_trade = (abs(mu) / sharpe_pp / rate) if (
            mu is not None and sharpe_pp and sharpe_pp > 0 and rate) else None
        cost_row = costs.get((sym, fam)) or costs.get((sym, ""))
        sr0 = sr0_by_cell.get((sym, fam)) or sr0_by_cell.get((sym, ""))
        mult = (NE.multiplicity_charge(sr0[0], sigma_trade, n_trials=sr0[1],
                                       source="UNIVERSAL_SURVIVORS sr0 joined on "
                                              "(symbol, family)")
                if sr0 else NE.unpriced(
                    "multiplicity", "no certificate on this (symbol, family) carries a "
                                    "deflated-Sharpe hurdle to charge this sleeve"))
        per_trade = NE.net_edge(
            str(rec.get("name") or f"{sym}.{fam}"), mu, unit=NE.R_PER_TRADE, symbol=sym,
            family=fam, lane=str(rec.get("lane") or "forward"),
            gross_source="POSTERIOR_ALPHA.json mu_mean", n=_f(rec.get("n")),
            spread_slippage=spread_term(cost_row, exec_cells.get(sym)),
            financing=financing_term(cost_row),
            commission=commission_term(cost_row, fusion.get(sym)),
            multiplicity=mult)
        rows.append(NE.rescale_to_unit(per_trade, unit=NE.R_PER_DAY, per_trade_to_unit=rate))
    return rows


def sr0_index(surv: Any) -> dict[tuple[str, str], tuple[float, int]]:
    """(symbol, family) -> the HARSHEST deflated-Sharpe hurdle a certificate there has owed."""
    out: dict[tuple[str, str], tuple[float, int]] = {}
    for rec in (((surv or {}).get("survivors") or {}) if isinstance(surv, dict)
                else {}).values():
        if not isinstance(rec, dict):
            continue
        spec = rec.get("shadow_spec") or {}
        sym, fam = str(spec.get("symbol") or rec.get("sym") or ""), str(spec.get("family") or "")
        ds = (rec.get("gates") or {}).get("deflated_sharpe") or {}
        sr0, n = _f(ds.get("sr0")), int(_f(ds.get("n_trials")) or 0)
        if not sym or sr0 is None:
            continue
        for key in ((sym, fam), (sym, "")):
            prev = out.get(key)
            if prev is None or sr0 > prev[0]:
                out[key] = (sr0, n)
    return out


def exec_cell_index(doc: Any) -> dict[str, dict[str, Any]]:
    """symbol -> its realised all-in cost cell from `cost_surface`'s execution surface."""
    out: dict[str, dict[str, Any]] = {}
    for row in ((doc or {}).get("net_alpha") or []) if isinstance(doc, dict) else []:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("asset") or "")
        if sym and row.get("cost_basis") in ("MEASURED", "SHRUNK_TO_PARENT") \
                and _f(row.get("cost_r")) is not None:
            out.setdefault(sym, {"cost_r": row["cost_r"], "n": row.get("cost_n"),
                                 "resolved_at": row.get("cost_resolved_at")})
    return out


# --------------------------------------------------------------------- backward attribution


def realised_errors(attr: Any, by_cell: dict[str, NE.NetEdge]) -> list[dict[str, Any]]:
    """Every closed live trade against what this cost model predicted for its cell.

    `counterfactual_attribution` already decomposes the realised deals; this CONSUMES its rows
    and edits nothing there. The join is on the symbol, because the live ledger's `sleeve` field
    is a broker comment and that organ says so itself.
    """
    rows = (((attr or {}).get("trades") or {}).get("rows") or []) if isinstance(attr, dict) \
        else []
    by_symbol: dict[str, NE.NetEdge] = {}
    for row in by_cell.values():
        if row.symbol and row.unit == NE.R_PER_TRADE and row.net is not None:
            prev = by_symbol.get(row.symbol)
            if prev is None or (prev.net or 0) < (row.net or 0):
                by_symbol[row.symbol] = row
    out: list[dict[str, Any]] = []
    for deal in rows:
        if not isinstance(deal, dict):
            continue
        sym = str(deal.get("symbol") or "")
        pred = by_symbol.get(sym)
        realised = _f(deal.get("r_realised"))
        if pred is None:
            out.append({"cell": sym or "?", "status": NE.UNMEASURED, "deal": deal.get("deal"),
                        "why": f"no priced net-edge row joins symbol {sym!r}: this closed trade "
                               "cannot judge the cost model"})
            continue
        err = NE.prediction_error(pred, realised)
        err["deal"] = deal.get("deal")
        err["at"] = deal.get("at")
        out.append(err)
    return out


# ------------------------------------------------------------------------------ the doors


def intake_contract(ranked: list[NE.NetEdge]) -> dict[str, Any]:
    """Door (a): the join file `miner_candidate_compiler` ranks its compiled candidates by."""
    by_cell: dict[str, dict[str, Any]] = {}
    for row in ranked:
        key = f"{row.symbol}|{row.family}"
        prev = by_cell.get(key)
        if prev is not None and (_f(prev.get("net")) or -9e9) >= (row.net if row.net is not None
                                                                 else -9e9):
            continue
        by_cell[key] = {"net": None if row.net is None else round(float(row.net), 8),
                        "gross": None if row.gross is None else round(float(row.gross), 8),
                        "unit": row.unit, "verdict": row.verdict, "status": row.status,
                        "cost_priced": round(row.cost_priced, 8),
                        "net_is_bound": bool(row.unpriced_terms),
                        "unpriced_terms": list(row.unpriced_terms),
                        "cell": row.key,
                        "terms": {n: row.term(n).as_dict() for n in NE.TERMS}}
    return by_cell


def slot_ranking(ranked: list[NE.NetEdge],
                 slots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Door (b): each forward clock's slot value scaled by its own net/gross ratio.

    The ratio, never a re-derivation: `forward_slot_ranker` owns the slot arithmetic and this
    only says what share of it survives costs. A ratio at or below zero is a COST_DEAD clock and
    it is PUBLISHED as such -- no clock is stopped here, because this organ stops nothing.
    """
    out: list[dict[str, Any]] = []
    for row in ranked:
        key = f"{row.symbol}|{row.family}"
        slot = slots.get(key)
        if slot is None or row.net is None or row.gross is None or row.gross <= 0:
            continue
        value = _f(slot.get("slot_value"))
        ratio = float(row.net) / float(row.gross)
        out.append({"lane": slot.get("lane"), "symbol": row.symbol, "family": row.family,
                    "slot_value": value, "net_over_gross": round(ratio, 6),
                    "net_slot_value": (None if value is None else round(value * ratio, 14)),
                    "verdict": row.verdict, "net_is_bound": bool(row.unpriced_terms)})
    out.sort(key=lambda r: -(r["net_slot_value"] if isinstance(r["net_slot_value"], float)
                             else -9e99))
    return out


def allocator_contract(ranked: list[NE.NetEdge], ref: dict[str, Any]) -> dict[str, Any]:
    """Door (c): net-of-cost posterior inputs and per-sleeve CAPACITY for the allocator."""
    out: dict[str, Any] = {}
    for row in ranked:
        if row.lane == "certificate":
            continue
        cap = NE.capacity_size(row, ref_lots=ref.get("ref_lots"),
                               ref_impact_r=ref.get("ref_impact_r"))
        if "why" not in cap or cap.get("status") == NE.UNMEASURED:
            cap.setdefault("why", ref.get("why", ""))
        out[row.key] = {
            "symbol": row.symbol, "family": row.family, "unit": row.unit,
            "gross": None if row.gross is None else round(float(row.gross), 8),
            "net": None if row.net is None else round(float(row.net), 8),
            "net_is_bound": bool(row.unpriced_terms), "verdict": row.verdict,
            "cost_priced": round(row.cost_priced, 8), "capacity": cap,
        }
    return out


def heat_reallocation(alloc: Any, ranked: list[NE.NetEdge]) -> dict[str, Any]:
    """The two-sided proof: reallocate the live book toward net and show the heat is UNCHANGED."""
    book_raw = ((alloc or {}).get("book") or (alloc or {}).get("fractions") or {}) \
        if isinstance(alloc, dict) else {}
    book = {str(k): float(v) for k, v in book_raw.items()
            if isinstance(v, (int, float)) and math.isfinite(float(v))}
    if not book:
        return {"status": NE.UNMEASURED, "heat_before": None, "heat_after": None,
                "why": "reports/pf_allocation.json publishes no book fractions on this host: "
                       "there is no heat to reallocate and none is taken away"}
    tilt = NE.net_tilt(ranked)
    after = NE.reweight_preserving_heat(book, tilt)
    before_sum, after_sum = sum(book.values()), sum(after.values())
    return {"status": NE.MEASURED, "n_sleeves": len(book),
            "heat_before": round(before_sum, 10), "heat_after": round(after_sum, 10),
            "heat_preserved": abs(before_sum - after_sum) <= 1e-9 * max(1.0, abs(before_sum)),
            "n_tilted": sum(1 for k in book if k in tilt),
            "shifts": {k: round(after[k] - book[k], 10) for k in
                       sorted(book, key=lambda n: -abs(after[n] - book[n]))[:12]},
            "why": "heat moves toward higher net and the total is preserved exactly: this "
                   "reallocates, it never reduces (GROWTH GOVERNANCE rules 1 and 2)"}


def cost_dead_donations(dead: list[NE.NetEdge], limit: int = 40) -> list[dict[str, Any]]:
    """The COST_DEAD descendants: the same idea at a LONGER horizon, donated to the intake."""
    rows: list[dict[str, Any]] = []
    try:
        from research.proposer_common import candidate
    except Exception:  # pragma: no cover - intake unavailable on a bare host
        return rows
    for row in dead[:limit]:
        if not row.symbol or not row.family:
            continue
        req = NE.descendant_request(row)
        rows.append(candidate(
            SEAT, row.symbol, row.family,
            {"timeframe": "H4", "lower_turnover": True},
            mechanism=("the mechanism is unchanged and its GROSS edge survives; only its "
                       "TURNOVER kills it. This descendant trades the same idea at a longer "
                       f"horizon so the per-trade cost is amortised: {req['why']}"),
            title=f"{row.symbol} {row.family} -- lower-turnover descendant of a COST_DEAD cell",
            evidence={"failure_kind": "cost_dead", "descendant_kind": "lower_turnover_descendant",
                      "parent_cell": row.key, "gross": row.gross, "net": row.net,
                      "net_decomposition": req["net_decomposition"],
                      "route": "libs.research.coevolution_lab FAILURE_RULES['cost_dead']"}))
    return rows


# ------------------------------------------------------------------------------- the pass


def run(*, budget_s: float = 600.0, write: bool = True, now: datetime | None = None,
        donate_rows: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    docs = {p.name: _json(p) for p in (COST_TO_EDGE, FUSION_COST, EXEC_SURFACE, SURVIVORS,
                                       POSTERIOR, SLOTS, CAPACITY, ATTRIBUTION, IMPACT,
                                       ALLOCATION)}
    inputs = {k: ("present" if v else "absent") for k, v in docs.items()}
    unmeasured: list[str] = [f"{k}: absent on this host" for k, v in inputs.items()
                             if v == "absent"]

    costs = cost_index(docs[COST_TO_EDGE.name])
    fusion = fusion_index(docs[FUSION_COST.name])
    exec_cells = exec_cell_index(docs[EXEC_SURFACE.name])
    rates = rate_index(docs[SLOTS.name])
    slots = slot_index(docs[SLOTS.name])
    sr0s = sr0_index(docs[SURVIVORS.name])
    ref = impact_reference(docs[IMPACT.name], docs[CAPACITY.name])
    if ref["status"] == NE.UNMEASURED:
        unmeasured.append(f"market impact: {ref['why']}")

    rows = survivor_rows(docs[SURVIVORS.name], costs, fusion, exec_cells)
    if time.monotonic() - started < budget_s:
        rows += posterior_rows(docs[POSTERIOR.name], costs, fusion, exec_cells, rates, sr0s)
    else:
        unmeasured.append(f"the forward posterior was not priced: --budget-s {budget_s:g} "
                          "elapsed after the certificates")
    ranked = NE.rank_by_net(rows)
    dead = NE.cost_dead(ranked)
    dead_unconfirmed = [r for r in ranked if r.verdict == NE.COST_DEAD_UNCONFIRMED]

    by_cell = intake_contract(ranked)
    alloc_rows = allocator_contract(ranked, ref)
    errors = realised_errors(docs[ATTRIBUTION.name], {r.key: r for r in ranked}) \
        if time.monotonic() - started < budget_s else []
    calib = NE.calibration(errors)
    if calib.get("status") == NE.UNMEASURED:
        unmeasured.append(f"cost model calibration: {calib.get('why')}")

    missed = [NE.missed_growth_line(r, trades_per_day=rates.get((r.symbol, r.family))
                                    or rates.get((r.symbol, "")))
              for r in dead]
    donations = cost_dead_donations(dead) if donate_rows else []

    per_family: dict[str, dict[str, Any]] = {}
    per_symbol: dict[str, dict[str, Any]] = {}
    for row in ranked:
        for bucket, key in ((per_family, row.family or "(unnamed)"),
                            (per_symbol, row.symbol or "(unnamed)")):
            cell = bucket.setdefault(key, {"n": 0, "gross": 0.0, "net": 0.0, "n_priced": 0,
                                           "n_cost_dead": 0})
            cell["n"] += 1
            if row.gross is not None and row.net is not None:
                cell["n_priced"] += 1
                cell["gross"] += float(row.gross)
                cell["net"] += float(row.net)
            if row.verdict in (NE.COST_DEAD, NE.COST_DEAD_UNCONFIRMED):
                cell["n_cost_dead"] += 1
    for bucket in (per_family, per_symbol):
        for cell in bucket.values():
            cell["gross"] = round(cell["gross"], 6)
            cell["net"] = round(cell["net"], 6)
            cell["net_over_gross"] = (round(cell["net"] / cell["gross"], 6)
                                      if cell["gross"] else None)

    report: dict[str, Any] = {
        "at": stamp, "schema": "net-edge-1", "rule": RULE,
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 3),
        "inputs": inputs,
        "n_rows": len(ranked), "n_priced": sum(1 for r in ranked if r.net is not None),
        "n_sign_flips": NE.sign_flips(ranked),
        "n_cost_dead": len(dead), "n_cost_dead_unconfirmed": len(dead_unconfirmed),
        "n_net_positive": sum(1 for r in ranked
                              if r.verdict in (NE.NET_POSITIVE, NE.NET_POSITIVE_UNCONFIRMED)),
        "term_coverage": {t: sum(1 for r in ranked if r.term(t).priced) for t in NE.TERMS},
        "net_vs_gross_by_family": dict(sorted(per_family.items())),
        "net_vs_gross_by_instrument": dict(sorted(per_symbol.items())),
        "impact_reference": ref,
        "capacity_by_sleeve": alloc_rows,
        "cost_model_calibration": calib,
        "prediction_errors": errors[:60],
        "ranked_if_net_were_the_only_ranking": [r.as_dict() for r in ranked[:60]],
        "cost_dead": [r.as_dict() for r in dead[:60]],
        "forward_slot_ranking_by_net": slot_ranking(ranked, slots)[:40],
        "missed_growth_lines": missed[:60],
        "heat_reallocation": heat_reallocation(docs[ALLOCATION.name], ranked),
        "cost_dead_donated": len(donations),
        "unmeasured": unmeasured,
        "doors": {
            "intake": "data/net_edge_ranks.json -> desks/mt5/research/miner_candidate_compiler.py",
            "forward_slot": "reports/NET_EDGE.json -> desks/mt5/research/forward_slot_ranker.py",
            "allocator": "reports/NET_EDGE.json -> libs/portfolio/allocator_evidence.py "
                         "net_of_cost_factors / net_capacity_rows",
            "backward": "reports/COUNTERFACTUAL_ATTRIBUTION.json (consumed, never edited)",
        },
    }

    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        RANKS.parent.mkdir(parents=True, exist_ok=True)
        RANKS.write_text(json.dumps(
            {"at": stamp, "rule": RULE, "n_rows": len(ranked),
             "n_sign_flips": report["n_sign_flips"],
             "order": [r.key for r in ranked],
             "by_cell": by_cell,
             "capacity_by_sleeve": alloc_rows}, indent=1, sort_keys=True, default=str) + "\n",
            "utf-8")
        if donations:
            try:
                from research.proposer_common import donate
                donate(SEAT, donations, tests_run=len(ranked))
            except Exception as exc:  # pragma: no cover - intake unavailable
                report["unmeasured"].append(
                    f"cost-dead descendants not donated ({type(exc).__name__}): the rows are in "
                    "the report and nothing was dropped")
        try:
            from libs.ops.events import leg_events
            leg_events("net_edge", "OK", n_rows=len(ranked),
                       n_sign_flips=report["n_sign_flips"], n_cost_dead=len(dead),
                       artifact=str(OUT))
        except Exception:  # pragma: no cover - events optional
            pass
    return report


def _print(rep: dict[str, Any]) -> None:
    print(f"NET_EDGE  rows={rep['n_rows']} priced={rep['n_priced']} "
          f"sign_flips={rep['n_sign_flips']} (COST_DEAD {rep['n_cost_dead']}, "
          f"unconfirmed {rep['n_cost_dead_unconfirmed']})  net_positive={rep['n_net_positive']}")
    print("  term coverage: " + ", ".join(f"{k} {v}/{rep['n_rows']}"
                                          for k, v in rep["term_coverage"].items()))
    heat = rep["heat_reallocation"]
    print(f"  heat {heat.get('heat_before')} -> {heat.get('heat_after')} "
          f"(preserved={heat.get('heat_preserved')}, {heat['status']})")
    cal = rep["cost_model_calibration"]
    print(f"  cost model: n={cal.get('n')} {cal.get('verdict', cal.get('status'))} "
          f"bias={cal.get('bias')}")
    for row in rep["ranked_if_net_were_the_only_ranking"][:6]:
        print(f"    {row['key'][:44]:44s} gross={row['gross']} net={row['net']} "
              f"{row['verdict']}")
    for note in rep["unmeasured"][:4]:
        print(f"  UNMEASURED: {note}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled shape)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run(budget_s=args.budget_s, write=not args.dry_run, donate_rows=not args.dry_run)
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        _print(rep)
        print("dry run: nothing written" if args.dry_run else f"written: {OUT} and {RANKS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
