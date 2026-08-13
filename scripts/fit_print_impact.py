"""Fit an execution-cost curve from OTHER TRADERS' PRINTS -- the third cost basis (L1.11b).

WHAT WAS MISSING. `data/cost_model.json` decides which names the book may hold, and it is
produced by walking DISPLAYED DEPTH only (`scripts/run_cost_model.py` reads no trade row at all).
L1.45 states why that cannot be the whole answer -- "a book-walk measures DISPLAYED depth in a
book that existed WITHOUT OUR ORDER IN IT" -- and the desk's answer was excitation, bounded to its
own 531 fills because L1.11(b) says an Execution Reality Model comes from "our own fills". That
scope word was written to stop the desk trusting a vendor's coefficient. It was read as "only our
own fills count", and it left unread the largest execution dataset on the box: every print on the
tape is a completed execution experiment at a known size with a published aggressor side, against
the same book we snapshot, paid for by somebody else.

This script fits that third basis and publishes it ALONGSIDE the book walk, labelled by basis.

WHAT IT DOES NOT DO, AND WHY THAT IS NOT TIMIDITY. It does not feed `_rt_bps`, size anything, or
admit anything. The print basis reads CHEAPER than the book walk on thin books (it sees liquidity
the snapshot does not), so wiring it into `_entry_gate` today would LOOSEN the gate on exactly the
books that produced COOKIEUSDT's 130bps round-trip -- on an estimator whose out-of-sample check
currently has 12 usable rows. That is EVIDENCE restraint, the kind L1.28 protects, not scope
restraint: the build is complete and the consumer is blocked on a falsifier reaching power, which
is rowed rather than left implicit. The executor's tighten-only `max(modelled, realised)` rule is
untouched by this file.

STATUS (rollup, and per (venue,symbol)):
    MEASURED      lambda separated from zero on n_eff independent intervals
    UNDERPOWERED  too few independent intervals, or |t| below the bar
    UNIDENTIFIED  net flow carries no usable variance, or the fitted slope is non-positive
    NO-DATA       no usable depth/print pairing
    UNMEASURED    rollup only: nothing measured anywhere -- never reads as OK (L1.28a)

    python scripts/fit_print_impact.py [--json] [--hours N] [--venue fut] [--symbol SYM]
"""
from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: pages, does not block -- a governance fault must never silently stop an
# organ that only reads the tape and writes one advisory artifact.
from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import moat_microstructure as mm  # noqa: E402
from libs.research import print_impact as pi  # noqa: E402

_MOAT = _ROOT / "data/moat"
_OUT = _ROOT / "data/print_impact.json"
_COST_MODEL = "data/cost_model.json"

#: Hours of tape per (venue, symbol). One partition is one hour. 24 keeps a full pass near a
#: minute of I/O while giving every liquid name several thousand intervals; --hours raises it.
_DEFAULT_HOURS = 24
#: The size the book actually trades. run_cost_model.py prices the pair at $500/leg for the same
#: reason; keeping the two comparable is the entire point of publishing a second basis.
_DESK_NOTIONAL = 450.0
#: Venues carrying both a depth and a print stream. Bybit is included: its prints additionally
#: carry isBlockTrade/isRPITrade, which no feature code on this desk reads yet.
_VENUES = ("fut", "spot", "bybit")


def _symbols(venue: str) -> list[str]:
    d = _MOAT / venue
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def _fit_one(venue: str, symbol: str, hours: int) -> pi.ImpactFit:
    parts = sorted((_MOAT / venue / symbol).glob("*.jsonl.gz"))[-hours:]
    if not parts:
        return pi.fit([], symbol=symbol, venue=venue)
    recs = itertools.chain.from_iterable(mm.read_partition(p) for p in parts)
    return pi.fit(pi.intervals(recs, venue), symbol=symbol, venue=venue)


def _as_row(f: pi.ImpactFit, notional: float) -> dict[str, Any]:
    return {
        "status": f.status,
        "n_intervals": f.n,
        "n_eff": f.n_eff,
        "lambda_bps_per_1k": f.lam_controlled_bps_per_1k,
        "lambda_raw_bps_per_1k": f.lam_bps_per_1k,
        "momentum_share": f.momentum_share,
        "t_stat": f.t_stat,
        "r2": f.r2,
        "half_spread_bps": f.half_spread_bps,
        "median_print_usd": f.median_print_usd,
        "prints_in_desk_range": f.prints_in_desk_range,
        "flow_p50_usd": f.flow_p50_usd,
        "identified_to_usd": f.identified_to_usd,
        f"cost_bps_at_{int(notional)}": f.cost_bps(notional),
        "detail": f.detail,
    }


def _pair_compare(fits: dict[tuple[str, str], pi.ImpactFit], cost_model: Any,
                  notional: float) -> list[dict[str, Any]]:
    """Print-basis pair cost vs the book-walk pair cost, per symbol.

    Both bases price the same thing -- spot BUY + perp SELL for one open -- so they are directly
    comparable, and the DISAGREEMENT is the deliverable. Agreement corroborates the desk's
    most-consumed derivative from an independent direction; divergence names a book where one of
    the two is wrong and research has somewhere to go.
    """
    out: list[dict[str, Any]] = []
    symbols = {s for (v, s) in fits if v in ("fut", "spot")}
    cm_syms = cost_model.get("symbols", {}) if isinstance(cost_model, dict) else {}
    for sym in sorted(symbols):
        spot, fut = fits.get(("spot", sym)), fits.get(("fut", sym))
        if spot is None or fut is None:
            continue
        s_cost = spot.cost_bps(notional)
        f_cost = fut.cost_bps(notional)
        if s_cost is None or f_cost is None:
            # One leg unmeasured means the PAIR is unmeasured. Substituting the measured leg and
            # calling it a pair would publish half a cost as a whole one.
            out.append({"symbol": sym, "print_pair_open_bps": None,
                        "spot_status": spot.status, "fut_status": fut.status,
                        "book_walk_pair_open_bps": None, "ratio": None,
                        "detail": "one or both legs unmeasured"})
            continue
        pair = s_cost + f_cost
        bw = None
        entry = cm_syms.get(sym, {}).get("pair", {}) if isinstance(cm_syms, dict) else {}
        for key in ("500", "250"):
            v = entry.get(key, {}).get("pair_open_bps") if isinstance(entry, dict) else None
            if v is not None:
                bw = float(v)
                break
        out.append({
            "symbol": sym,
            "print_pair_open_bps": round(pair, 4),
            "spot_status": spot.status, "fut_status": fut.status,
            "spot_half_spread_bps": spot.half_spread_bps,
            "fut_half_spread_bps": fut.half_spread_bps,
            # Impact's share of the print-basis cost. Near zero means the desk is a SPREAD taker
            # at this size and trading smaller buys nothing -- an operational answer the blended
            # book-walk number cannot give.
            "impact_share_of_cost": round(
                1.0 - ((spot.half_spread_bps or 0.0) + (fut.half_spread_bps or 0.0)) / pair, 4)
            if pair > 0 else None,
            "book_walk_pair_open_bps": bw,
            "ratio": round(pair / bw, 3) if bw else None,
        })
    return out


def _falsifier(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Does the print basis rank OUR OWN realised slippage? The estimator's own kill criterion.

    Pre-registered before the fit was run: if predicted cost has ~zero rank correlation with
    realised slippage across the symbols where both exist, the estimator is confounded (large
    prints arrive BECAUSE the book is already moving) and adds nothing over the book walk.

    The honest answer today is UNDERPOWERED and it is reported as such rather than skipped: only
    12 of 531 execution_tape rows carry spot_slip_bps/fut_slip_bps at all -- the proposal that
    motivated this build asserted all 531 did. A rank correlation on a handful of symbols is not
    evidence either way, and calling it one would be the phantom-validation this desk kills.
    """
    tape = _ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
    realised: dict[str, list[float]] = {}
    n_rows = 0
    try:
        for line in tape.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_rows += 1
            sp, ft = r.get("spot_slip_bps"), r.get("fut_slip_bps")
            if sp is None:
                continue
            try:
                realised.setdefault(str(r.get("symbol")), []).append(
                    abs(float(sp)) + abs(float(ft or 0.0)))
            except (TypeError, ValueError):
                continue
    except OSError:
        return {"status": "NO-DATA", "detail": "execution_tape unreadable",
                "n_tape_rows": 0, "n_with_slippage": 0, "n_paired": 0, "spearman": None}

    pred = {p["symbol"]: p["print_pair_open_bps"] for p in pairs
            if p.get("print_pair_open_bps") is not None}
    paired = [(pred[s], statistics.median(v)) for s, v in realised.items() if s in pred]
    n_slip = sum(len(v) for v in realised.values())

    if len(paired) < 8:
        return {
            "status": "UNDERPOWERED",
            "detail": (f"{len(paired)} symbols carry both a print-basis prediction and a realised "
                       f"slippage reading ({n_slip} slipped rows of {n_rows} tape rows). A rank "
                       "correlation here would be noise reported as validation."),
            "n_tape_rows": n_rows, "n_with_slippage": n_slip, "n_paired": len(paired),
            "spearman": None,
            "unblock": ("instrument every close with spot_slip_bps/fut_slip_bps -- the executor "
                        "already computes both and writes them on only 12 of 531 rows"),
        }
    import numpy as np
    a = np.array([p for p, _ in paired], dtype=float)
    b = np.array([r for _, r in paired], dtype=float)
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    rho = float(np.corrcoef(ra, rb)[0, 1])
    return {
        "status": "MEASURED" if abs(rho) >= 0.3 else "REFUTED",
        "detail": f"Spearman {rho:.3f} over {len(paired)} symbols",
        "n_tape_rows": n_rows, "n_with_slippage": n_slip, "n_paired": len(paired),
        "spearman": round(rho, 4),
    }


def build_report(hours: int, venues: tuple[str, ...], only: str | None,
                 notional: float) -> dict[str, Any]:
    inp = Inputs("fit_print_impact.build_report")
    # required=False is the honest declaration: the FIT depends only on the tape, so an absent
    # cost_model costs the desk the comparison, not the measurement. Marking it required would
    # publish `measured: false` over numbers that were in fact measured -- an honest-gap flag
    # pointed at the wrong organ (L1.55).
    cost_model = inp.read_json(_COST_MODEL, default={}, max_age_h=72.0, required=False)

    fits: dict[tuple[str, str], pi.ImpactFit] = {}
    per_venue: dict[str, dict[str, Any]] = {}
    for venue in venues:
        syms = [s for s in _symbols(venue) if (only is None or s == only)]
        rows: dict[str, Any] = {}
        for sym in syms:
            f = _fit_one(venue, sym, hours)
            fits[(venue, sym)] = f
            rows[sym] = _as_row(f, notional)
        per_venue[venue] = rows

    all_fits = list(fits.values())
    n_scanned = len(all_fits)
    by_status: dict[str, int] = {}
    for f in all_fits:
        by_status[f.status] = by_status.get(f.status, 0) + 1
    n_measured = by_status.get(pi.MEASURED, 0)

    pairs = _pair_compare(fits, cost_model, notional)
    priced = [p for p in pairs if p.get("print_pair_open_bps") is not None]
    ratios = [p["ratio"] for p in priced if p.get("ratio") is not None]
    shares = [p["impact_share_of_cost"] for p in priced
              if p.get("impact_share_of_cost") is not None]

    # ROLLUP. An empty measurement set must never read as OK (L1.28a), and the denominator here is
    # a COUNT OF WHAT THIS RUN FOUND rather than of a hardcoded symbol list (L1.57) -- if the
    # recorder universe shrinks to nothing, n_scanned goes to 0 and the status goes UNMEASURED
    # rather than reporting a clean pass over an empty set.
    if n_scanned == 0:
        status, detail = "UNMEASURED", "no (venue, symbol) pairs scanned -- is data/moat present?"
    elif n_measured == 0:
        status = "UNMEASURED"
        detail = f"0 of {n_scanned} (venue,symbol) fits measured: {by_status}"
    else:
        status = "MEASURED"
        detail = (f"{n_measured} of {n_scanned} fits measured; {len(priced)} symbols priced on "
                  f"both legs at ${int(notional)}")

    return {
        "generated": datetime.now(UTC).isoformat(),
        "law": "L1.11b third basis -- execution cost from third-party prints",
        "status": status,
        "detail": detail,
        "basis": "third_party_prints",
        "promotion_authority": "NONE -- advisory second basis, published alongside the book walk",
        "hours_per_symbol": hours,
        "desk_notional_usd": notional,
        "n_scanned": n_scanned,
        "n_measured": n_measured,
        "by_status": by_status,
        "convention": ("cost_bps(N) = half_spread_bps + 0.5 * lambda * N; lambda is the CONTROLLED "
                       "slope of mid return (bps) on net signed interval flow, per $1,000. Pair = "
                       "spot BUY + perp SELL, matching run_cost_model.py so the two are "
                       "comparable. Intervals are assigned by FILE ORDER (receipt), never by "
                       "mixing the venue-stamped trade clock with the receipt-stamped depth "
                       "clock (L1.46)."),
        "agreement_with_book_walk": {
            "n_compared": len(ratios),
            "median_ratio_print_over_bookwalk": round(statistics.median(ratios), 3)
            if ratios else None,
            "median_impact_share_of_cost": round(statistics.median(shares), 4) if shares else None,
            # THE RATIO IS NOT THE HEADLINE AND MUST NOT BE READ AS ONE. Measured 2026-08-12:
            # impact is 0.25%-8.6% of the print-basis cost at $450, so 91-99.75% of BOTH bases is
            # the same quoted half-spread, read off the same depth snapshots. A ratio near 1 is
            # therefore very largely TAUTOLOGICAL rather than independent corroboration, and
            # publishing it without this line would manufacture a validation the data does not
            # support. The bases are only genuinely independent where impact_share_of_cost is
            # large -- which is where they diverge.
            "independence": ("LIMITED -- both bases read the same quoted spread, which is "
                             "91-99.75% of the number at this size. Agreement is mostly shared "
                             "input, not confirmation. Weight the DIVERGENCES, not the median."),
            "note": ("ratio << 1 names a book whose DISPLAYED depth is thin relative to the "
                     "liquidity that actually trades -- the book walk charges a full level walk "
                     "the print tape does not see paid."),
        },
        # The operationally useful answer, and the one the blended book-walk number cannot give:
        # at the desk's size, is execution cost a SPREAD problem or a SIZE problem?
        "spread_vs_impact": {
            "median_impact_share_of_cost": round(statistics.median(shares), 4) if shares else None,
            "reading": ("At $450 the desk is a SPREAD TAKER, not an impact maker: trading in "
                        "smaller clips cannot recover a cost that is ~97% half-spread. Cost "
                        "reduction on this book comes from PASSIVE placement and from symbol "
                        "selection, never from slicing.") if shares and
            statistics.median(shares) < 0.2 else
                       ("Impact is a material share of cost -- order slicing and size discipline "
                        "are live levers here."),
        },
        "falsifier": _falsifier(pairs),
        "pairs": sorted(priced, key=lambda p: -(p.get("ratio") or 0.0)),
        "per_venue": per_venue,
        "inputs": inp.block(),
        "measured": inp.measured() and status == "MEASURED",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hours", type=int, default=_DEFAULT_HOURS,
                    help="partitions (hours) of tape per symbol")
    ap.add_argument("--venue", action="append", choices=_VENUES,
                    help="restrict to one venue (repeatable)")
    ap.add_argument("--symbol", help="restrict to one symbol")
    ap.add_argument("--notional", type=float, default=_DESK_NOTIONAL)
    args = ap.parse_args()

    rep = build_report(args.hours, tuple(args.venue) if args.venue else _VENUES,
                       args.symbol, args.notional)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1, default=str) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"print impact (L1.11b third basis): {rep['status']} -- {rep['detail']}")
        agr = rep["agreement_with_book_walk"]
        sv = rep["spread_vs_impact"]
        print(f"  spread vs impact: impact is {sv['median_impact_share_of_cost']} of cost at "
              f"${int(rep['desk_notional_usd'])} -- {sv['reading'].split('.')[0]}.")
        print(f"  vs book walk: n={agr['n_compared']} median ratio "
              f"{agr['median_ratio_print_over_bookwalk']} "
              f"(independence: {agr['independence'].split('--')[0].strip()})")
        fal = rep["falsifier"]
        print(f"  falsifier: {fal['status']} -- {fal['detail']}")
        # The DIVERGENCES are the deliverable, so print both tails rather than one.
        rated = [p for p in rep["pairs"] if p.get("ratio") is not None]
        for label, rows in (("book-walk DEARER", rated[-4:][::-1]), ("book-walk cheaper",
                                                                     rated[:2])):
            for p in rows:
                print(f"    [{label:17s}] {p['symbol']:12s} print "
                      f"{p['print_pair_open_bps']:8.3f}  book-walk "
                      f"{p['book_walk_pair_open_bps']:8.3f}  ratio {p['ratio']}")
        print(f"  wrote {_OUT.relative_to(_ROOT)}")
    # A starved fit is a REPORT, not a gate failure -- this organ cannot conjure prints that were
    # never recorded. Exit 1 only when NOTHING measured, so a silent total failure cannot pass.
    return 0 if rep["status"] == "MEASURED" else 1


if __name__ == "__main__":
    sys.exit(main())
