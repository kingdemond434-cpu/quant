#!/usr/bin/env python3
"""EXECUTION FEEDBACK -- what each live sleeve pays to get filled, and what the tape says to change.

WHY (principal 2026-10-13: "mine our own Fusion and E8 fills for spread, slippage and swap timing,
and feed the gains back into entry timing for existing sleeves")

The desk already MEASURES execution in eight places (fill_recorder, execution_twin, markout,
execution_alpha_miner, execution_science, execution_resolver, fill_attribution, swap_exposure) and
none of them is read per sleeve against the sleeve's own risk, so no number says "sleeve X loses
0.04R a trade to the spread and the tape says a 10 s wait at its hour recovers 0.02R of it". This
organ is that join. It is the one place a per-sleeve execution change is proposed, priced in R and
in E[log W], and carried until evidence arms it.

WHAT IT COMPUTES, per sleeve, from the live ledgers only (no simulation):

  * COST DECOMPOSITION IN R, on the trade's INITIAL risk (intent price to intent stop, the risk it
    was sized on -- `markout.risk_price`): entry slippage, the half spread paid at decision,
    commission and swap, beside the realised R. The R denominator is what makes sleeves on gold,
    FX and indices comparable, and the initial stop is what keeps a break-even-trailed stop from
    turning a fill into -44R (the markout unit bug fixed in the same change).
  * FILL RATE AND LATENCY: intents sent, deals joined, brackets that never filled, median
    decision-to-ack milliseconds.
  * TAPE PROPOSALS: every `EXECUTION_ALPHA.json` discovery on the sleeve's own instrument and in
    the session its entries actually fall in becomes a candidate rule (delayed_entry, limit_entry,
    spread_gate, session_avoid), priced as delta-R per trade = effect_bps x entry price / 1e4 /
    initial risk, and as delta E[log W] per year ~= trades/yr x sleeve fraction x delta-R.

WHAT IT NEVER DOES. It sends no order, sizes nothing, vetoes nothing. GROWTH GOVERNANCE Rule 1: a
restriction that has not proven it raises robust forward E[log W] restricts nothing, so every
proposal is CANDIDATE until the tape's own interval excludes zero on the sleeve's instrument AND
the delta is material (SUPPORTED); arming a SUPPORTED rule is a money-path change to
`mt5desk/gateway.py`, which goes through the sealed release like every other gateway edit.

E8 IS NAMED, NOT IMPLIED. The prop executor records orders as sent with no fill price and no
deal ledger, so every E8 sleeve reads UNMEASURED here -- an absence, never a clean zero (L1.28a).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = BASE / "data"
REPORTS = BASE / "reports"
OUT = REPORTS / "EXECUTION_FEEDBACK.json"
INTENTS = DATA / "order_intents.jsonl"
LEDGER = DATA / "live_ledger.jsonl"
E8_INTENTS = DATA / "e8_intents.jsonl"
EXECUTION_ALPHA = REPORTS / "EXECUTION_ALPHA.json"
SLEEVES = DATA / "sleeves.json"
UNMEASURED = "UNMEASURED"

#: A tape effect smaller than this per trade is not worth a money-path change: below it the
#: proposal stays CANDIDATE however tight its interval.
MATERIAL_R = 0.01
#: The sleeve fraction used to price delta E[log W] when the allocator's own is unreadable. Stated,
#: because a guessed fraction priced silently would read as the allocator's.
DEFAULT_FRACTION = 0.01


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    from mt5desk.markout import load_jsonl
    return load_jsonl(path) if path.exists() else []


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _stats(xs: list[float]) -> dict[str, Any]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "status": UNMEASURED}
    return {"n": len(xs), "mean": round(st.fmean(xs), 5), "median": round(st.median(xs), 5)}


def _hour(ts: Any) -> int | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(UTC).hour
    except ValueError:
        return None


def _session(hour: int | None) -> str | None:
    """The miner's own session label for an hour, so a proposal matches its cell by construction."""
    if hour is None:
        return None
    try:
        from research.execution_alpha_miner import _session_of
        return str(_session_of(int(hour)))
    except Exception:
        return None


def _fractions() -> dict[str, float]:
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    out: dict[str, float] = {}
    for r in rows or []:
        if isinstance(r, dict) and r.get("name") is not None:
            f = _num(r.get("risk_frac") or (r.get("admission") or {}).get("risk_frac"))
            if f is not None and f > 0:
                out[str(r["name"])] = f
    return out


def sleeve_costs(intents: list[dict[str, Any]], deals: list[dict[str, Any]]
                 ) -> dict[str, dict[str, Any]]:
    """Per-sleeve cost decomposition in R on the initial risk, plus fill rate and latency."""
    from mt5desk.markout import _entry_fill, _join_ticket, _direction, risk_price
    by_ticket = {i.get("ticket"): i for i in intents if i.get("ticket") is not None}
    acc: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    joined: set[Any] = set()
    for d in deals:
        t = _join_ticket(d, by_ticket)
        intent = by_ticket.get(t) if t is not None else None
        if intent is None:
            continue
        joined.add(t)
        name = str(intent.get("sleeve") or d.get("sleeve") or "?")
        a = acc[name]
        a["symbol"].append(intent.get("symbol") or d.get("symbol"))
        risk, _basis = risk_price(intent, d)
        want, got = _num(intent.get("intended")), _num(_entry_fill(d))
        dirn = _direction(intent.get("side"))
        size = (_num(d.get("contract_size")) or 0.0) * (_num(d.get("volume")) or 0.0)
        risk_ccy = risk * size if (risk and size) else None
        if risk and want is not None and got is not None and dirn:
            a["slip_r"].append((got - want) * dirn / risk)
            a["entry_price"].append(got)
        spread = _num(intent.get("spread_at_decision"))
        if risk and spread is not None:
            a["half_spread_r"].append(0.5 * spread / risk)
        if risk_ccy:
            for field, key in (("commission", "commission_r"), ("swap", "swap_r")):
                v = _num(d.get(field))
                if v is not None:
                    a[key].append(-v / risk_ccy)          # a cost is positive R
        rr = _num(d.get("r_multiple"))
        if rr is not None and rr != 0.0:
            a["realized_r"].append(rr)
        a["hour"].append(_hour(intent.get("time")))
        lat = _num(intent.get("latency_send_to_ack_ms") or intent.get("latency_ms"))
        if lat is not None:
            a["latency_ms"].append(lat)
    sent: dict[str, int] = defaultdict(int)
    unfilled: dict[str, int] = defaultdict(int)
    for t, i in by_ticket.items():
        name = str(i.get("sleeve") or "?")
        sent[name] += 1
        if t not in joined:
            unfilled[name] += 1
    out: dict[str, dict[str, Any]] = {}
    for name in sorted(set(acc) | set(sent)):
        a = acc.get(name, {})
        costs = {k: _stats(list(a.get(k, []))) for k in
                 ("slip_r", "half_spread_r", "commission_r", "swap_r")}
        total = sum(c["mean"] for c in costs.values() if c.get("mean") is not None)
        hours = [h for h in a.get("hour", []) if h is not None]
        out[name] = {
            "symbol": next((s for s in a.get("symbol", []) if s), None),
            "intents_sent": sent.get(name, 0), "unfilled_brackets": unfilled.get(name, 0),
            "fills": len(a.get("hour", [])),
            "costs_r": costs, "total_cost_r_mean": round(total, 5),
            "realized_r": _stats(list(a.get("realized_r", []))),
            "latency_ms": _stats(list(a.get("latency_ms", []))),
            "entry_hours": sorted(set(hours)),
            "sessions": sorted({s for s in (_session(h) for h in hours) if s}),
            "median_entry_price": (st.median(a["entry_price"]) if a.get("entry_price")
                                   else None),
            "median_risk_price": None,
        }
        risks = []
        for t, i in by_ticket.items():
            if str(i.get("sleeve") or "?") == name:
                r, _b = risk_price(i, {})
                if r:
                    risks.append(r)
        out[name]["median_risk_price"] = st.median(risks) if risks else None
    return out


def proposals(costs: dict[str, dict[str, Any]], alpha: Any,
              fractions: dict[str, float]) -> list[dict[str, Any]]:
    """Tape discoveries on a sleeve's own instrument and session, priced in R and E[log W]."""
    discoveries = (alpha or {}).get("discoveries") if isinstance(alpha, dict) else None
    out: list[dict[str, Any]] = []
    for d in discoveries or []:
        if not isinstance(d, dict):
            continue
        effect = d.get("effect") or {}
        cell = str(d.get("cell") or "")
        for name, c in costs.items():
            if c.get("symbol") != d.get("instrument") or not c.get("fills"):
                continue
            sess = [s for s in c.get("sessions") or [] if f"session={s}" in cell]
            if "session=all" not in cell and not sess:
                continue
            px, risk = c.get("median_entry_price"), c.get("median_risk_price")
            row: dict[str, Any] = {"sleeve": name, "symbol": c["symbol"], "cell": cell,
                                   "rule": d.get("suggested"), "effect": effect,
                                   "ci": d.get("ci"), "n_tape": d.get("n")}
            bps = _num(effect.get("diff_bps"))
            ci = [x for x in (d.get("ci") or []) if _num(x) is not None]
            if bps is None or not px or not risk:
                row.update(status="CANDIDATE", why=(
                    "no basis-point effect to price (adverse-move cell) or no initial risk "
                    "on the sleeve's intents; carried as a candidate, never armed"))
                out.append(row)
                continue
            delta_r = bps * float(px) / 1e4 / float(risk)
            trades_yr = 252.0 * c["fills"] / max(1, c["intents_sent"])
            f = fractions.get(name, DEFAULT_FRACTION)
            row["delta_r_per_trade"] = round(delta_r, 5)
            row["delta_elog_per_year"] = round(trades_yr * f * delta_r, 6)
            row["fraction_basis"] = "allocator" if name in fractions else "default_0.01"
            supported = (len(ci) == 2 and min(map(float, ci)) > 0 < delta_r
                         and delta_r >= MATERIAL_R)
            row["status"] = "SUPPORTED" if supported else "CANDIDATE"
            row["why"] = ("tape interval excludes zero on this instrument and the per-trade gain "
                          f"clears {MATERIAL_R}R; arming is a sealed gateway change"
                          if supported else
                          f"interval straddles zero or per-trade gain < {MATERIAL_R}R")
            out.append(row)
    out.sort(key=lambda r: -(r.get("delta_elog_per_year") or 0.0))
    return out


def build() -> dict[str, Any]:
    intents, deals = _jsonl(INTENTS), _jsonl(LEDGER)
    try:
        from libs.ops.live_ledger_view import ledger_path
        deals = _jsonl(ledger_path(LEDGER))
    except Exception:
        pass
    costs = sleeve_costs(intents, deals)
    alpha = _read(EXECUTION_ALPHA)
    props = proposals(costs, alpha, _fractions())
    e8 = _jsonl(E8_INTENTS)
    book = [c for c in costs.values() if c["fills"]]
    w = sum(c["fills"] for c in book) or 1
    return {
        "generated_at": _now(), "producer": "desks/mt5/research/execution_feedback.py",
        "accounts": {
            "fusion": {"status": "MEASURED" if book else UNMEASURED,
                       "sleeves": len(costs), "fills": sum(c["fills"] for c in book)},
            "e8": {"status": UNMEASURED, "intents_recorded": len(e8),
                   "why": ("the prop executor records orders as sent with no fill price and "
                           "no deal ledger, so no E8 execution cost is measurable yet")},
        },
        "book_cost_r_fill_weighted": round(sum(c["total_cost_r_mean"] * c["fills"]
                                               for c in book) / w, 5),
        "sleeves": costs,
        "tape_source": ("reports/EXECUTION_ALPHA.json" if isinstance(alpha, dict)
                        else f"{UNMEASURED}: reports/EXECUTION_ALPHA.json absent"),
        "proposals": props,
        "supported": sum(1 for p in props if p.get("status") == "SUPPORTED"),
        "rule": ("costs in R on the INITIAL risk (intent price to intent stop); a tape proposal "
                 "is SUPPORTED only when its interval excludes zero on the sleeve's own "
                 f"instrument and session and it is worth >= {MATERIAL_R}R a trade. Nothing here "
                 "places, sizes or vetoes an order (Rule 1); arming is a sealed gateway change"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(args.out)
    print(f"execution_feedback: sleeves={len(doc['sleeves'])} "
          f"fills={doc['accounts']['fusion']['fills']} "
          f"book_cost={doc['book_cost_r_fill_weighted']:+.4f}R "
          f"proposals={len(doc['proposals'])} supported={doc['supported']} -> {args.out}")
    worst = sorted(((n, c) for n, c in doc["sleeves"].items() if c["fills"]),
                   key=lambda kv: -kv[1]["total_cost_r_mean"])[:8]
    for n, c in worst:
        cr = c["costs_r"]
        print(f"  {n[:34]:34} fills={c['fills']:3} cost={c['total_cost_r_mean']:+.4f}R "
              f"slip={cr['slip_r'].get('median')} spread={cr['half_spread_r'].get('median')} "
              f"comm={cr['commission_r'].get('median')} realized={c['realized_r'].get('mean')}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
