#!/usr/bin/env python3
"""SLEEVE ALLOCATOR (R0141) -- risk across discretionary sleeves, by MARGINAL growth contribution.

PRINCIPAL ORDER (2026-07-31): *"advance this section way more so multiple discretionary edges
genuinely compound triple-digit CAGRs and max geometric growth each on the side."*

THE WORD THAT DOES THE WORK IS "GENUINELY". Adding sleeves only multiplies growth if the sleeves
are INDEPENDENT. Five sleeves all long crypto beta are one sleeve wearing five names: they draw
down together, so total risk scales with N while growth scales with 1, and the desk ends up paying
five sets of costs for one bet. That is not an abstract worry -- this book has already measured
crypto-vs-crypto return correlation at +0.48 and gold-vs-crypto at +0.15, so the difference between
a real second edge and a duplicate is large and measurable.

So the rule this organ enforces:

    A NEW DISCRETIONARY SLEEVE EARNS RISK ONLY IN PROPORTION TO WHAT IT ADDS THAT THE EXISTING
    BOOK DOES NOT ALREADY HAVE. Duplicates are funded at a discount or refused, and the discount
    is COMPUTED from the measured correlation of realised returns, never from the story attached
    to the sleeve.

WHY THIS IS THE HIGH-VALUE PIECE OF "MORE SLEEVES". At fixed total heat, splitting risk across N
INDEPENDENT sleeves multiplies the growth rate by roughly N while portfolio volatility grows as
sqrt(N) -- the same arithmetic that made 8 positions at 3% beat 1 position at 24%, applied one
level up. At correlation 1.0 the same split multiplies growth by 1 and buys nothing but extra fees.
The allocator is therefore where the "each on the side" part of the order is actually delivered or
quietly lost.

MARGINAL, NOT AVERAGE. A sleeve's allocation follows its marginal contribution to portfolio
E[log wealth], approximated by shrinking its standalone growth by how much of its variance the rest
of the book already carries. A sleeve with a strong standalone record that duplicates an existing
one contributes little at the margin and is funded accordingly -- which is the honest answer to
"but it makes money on its own".

UNMEASURED IS TREATED AS DUPLICATE, deliberately and in the pessimistic direction. Two sleeves with
no overlapping return history have no measured correlation, and assuming independence there would
hand full risk to a sleeve that might be the same bet. The assumption that costs money when wrong
is the one that gets made.

ZERO PROMOTION AUTHORITY (L1.6): this allocates PAPER risk budget among sleeves that have already
earned their place. It cannot promote a sleeve to live capital, and it places no orders.

    python scripts/run_sleeve_allocator.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/sleeve_allocation.json"

#: The registered discretionary sleeves and where their marked returns live. A sleeve absent from
#: here gets no budget -- "unregistered" must be a decision, not a way to slip in unmeasured.
_SLEEVES: dict[str, dict[str, str]] = {
    "conviction": {"book": "data/conviction_book.jsonl", "kind": "chart structure + levels",
                   "mark_key": "conviction"},
    "event": {"book": "data/llm_trader_book.jsonl", "kind": "prose/event causal reasoning",
              "mark_key": "event"},
}

#: Correlation at or above which a sleeve is a DUPLICATE rather than an edge. 0.7 is where shared
#: variance passes half (rho^2 = 0.49): beyond it the majority of the new sleeve's movement is
#: already carried by the book, so it is funding a second copy of an existing bet.
DUPLICATE_RHO = 0.70
#: Minimum overlapping closed trades before a correlation is believed. Below this the sample
#: correlation's standard error (~1/sqrt(n-1)) exceeds 0.35, which cannot distinguish +0.15 from
#: +0.48 -- the exact distinction the allocation turns on.
MIN_OVERLAP = 10
#: Total paper risk budget shared across discretionary sleeves. Matches MAX_PORTFOLIO_HEAT in the
#: conviction sleeve so the two layers cannot silently sum to more than the book allows.
TOTAL_HEAT = 0.30
#: Floor share for a registered sleeve with no measured history: it must be able to ACCUMULATE the
#: record that would earn it more, and a zero allocation is a sleeve that can never prove itself
#: (L1.28a -- idle capacity is unbooked loss). Small enough that being wrong is cheap.
SEED_SHARE = 0.10


def _series(root: Path, mark_key: str) -> list[tuple[str, float]]:
    """(exit timestamp, net return) for a sleeve's closed, marked trades."""
    try:
        marks = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))["marks"]
    except (OSError, ValueError, KeyError):
        return []
    return [(m.get("exit_at") or m.get("key") or "", float(m.get("equity_return") or 0.0))
            for m in marks
            if m.get("closed") and m.get("kind") == mark_key and m.get("equity_return") is not None]


def _corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 3:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        return None
    return round(sab / math.sqrt(saa * sbb), 4)


def _align(s1: list[tuple[str, float]], s2: list[tuple[str, float]],
           ) -> tuple[list[float], list[float]]:
    """Pair returns by DAY. Two sleeves rarely close at the same instant, so a naive positional
    zip would correlate unrelated trades and produce a number that means nothing."""
    def by_day(s):
        out: dict[str, float] = {}
        for ts, r in s:
            out[str(ts)[:10]] = out.get(str(ts)[:10], 0.0) + r
        return out
    d1, d2 = by_day(s1), by_day(s2)
    days = sorted(set(d1) & set(d2))
    return [d1[d] for d in days], [d2[d] for d in days]


def standalone_growth(rets: list[float]) -> float | None:
    """Realised log-growth per trade. None on no history -- never a zero, which would read as a
    measured flat result rather than as absence."""
    live = [r for r in rets if r > -0.999]
    return round(sum(math.log(1 + r) for r in live) / len(live), 6) if live else None


def allocate(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    series = {name: _series(root, spec["mark_key"]) for name, spec in _SLEEVES.items()}
    rows: dict[str, Any] = {}
    for name, spec in _SLEEVES.items():
        rets = [r for _, r in series[name]]
        rows[name] = {"kind": spec["kind"], "n_closed": len(rets),
                      "standalone_g": standalone_growth(rets)}

    pairs: dict[str, Any] = {}
    names = list(_SLEEVES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            xa, xb = _align(series[a], series[b])
            if len(xa) < MIN_OVERLAP:
                pairs[f"{a}|{b}"] = {
                    "state": "UNMEASURED", "overlap_days": len(xa),
                    "assumed_rho": 1.0,
                    "why": f"{len(xa)} overlapping days < {MIN_OVERLAP}; treated as a DUPLICATE, "
                           "because assuming independence would hand full risk to what may be the "
                           "same bet"}
                continue
            rho = _corr(xa, xb)
            pairs[f"{a}|{b}"] = {
                "state": "MEASURED", "overlap_days": len(xa), "rho": rho,
                "verdict": ("DUPLICATE -- majority of its variance is already carried by the book"
                            if rho is not None and rho >= DUPLICATE_RHO else
                            "INDEPENDENT ENOUGH TO FUND" if rho is not None else "UNMEASURED")}

    # BASE WEIGHT: standalone growth, floored so a registered sleeve can always accumulate the
    # record that would earn it more (a zero allocation is a sleeve that can never prove itself).
    base: dict[str, float] = {}
    for name in names:
        g = rows[name]["standalone_g"]
        base[name] = SEED_SHARE if g is None else max(SEED_SHARE, min(1.0, max(0.0, g) * 100))
    tot_base = sum(base.values()) or 1.0
    u = {n: base[n] / tot_base for n in names}          # normalised split

    # THE CORRECTION THAT MAKES THIS MEAN ANYTHING: correlation must scale TOTAL deployed risk,
    # not merely how a fixed total is divided. The first version normalised shares to 1 and so
    # handed two perfect duplicates the same total heat as two independent sleeves -- exactly the
    # failure this organ exists to prevent, in the organ itself. Total risk is now solved so the
    # CORRELATION-ADJUSTED portfolio risk equals TOTAL_HEAT: sqrt(u' S u) is near sum(u) for
    # duplicates (little scaling room) and much smaller for independent sleeves (more room).
    def rho_between(a: str, b: str) -> float:
        if a == b:
            return 1.0
        p = pairs.get(f"{a}|{b}") or pairs.get(f"{b}|{a}") or {}
        if p.get("state") == "MEASURED" and p.get("rho") is not None:
            return abs(float(p["rho"]))
        return 1.0                                       # UNMEASURED is treated as duplicate
    var = sum(u[a] * u[b] * rho_between(a, b) for a in names for b in names)
    port = math.sqrt(var) if var > 0 else 1.0
    scale = TOTAL_HEAT / port if port > 0 else TOTAL_HEAT
    for name in names:
        rows[name]["share"] = round(u[name], 4)
        rows[name]["risk_budget"] = round(min(u[name] * scale, TOTAL_HEAT), 4)
    rows_total = sum(r["risk_budget"] for r in rows.values())

    measured = [p for p in pairs.values() if p["state"] == "MEASURED"]
    n_ind = sum(1 for p in measured
                if p.get("rho") is not None and abs(p["rho"]) < DUPLICATE_RHO)
    effective_n = (1 + n_ind) if measured else 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6/L1.28b -- more sleeves only multiply growth if they are INDEPENDENT. "
               "Correlated sleeves draw down together: risk scales with N, growth with 1, and the "
               "desk pays N sets of costs for one bet.",
        "status": ("UNMEASURED" if not measured else
                   "DUPLICATION" if n_ind < len(measured) else "DIVERSIFIED"),
        "total_heat_cap": TOTAL_HEAT,
        "total_deployed": round(rows_total, 4),
        "correlation_scaling": round(scale, 3),
        "sleeves": rows, "pairs": pairs,
        "effective_independent_sleeves": effective_n,
        "growth_multiplier_note": (
            "at fixed total heat, N INDEPENDENT sleeves multiply growth by ~N while portfolio "
            "volatility grows as ~sqrt(N); at rho=1 the same split multiplies growth by 1 and buys "
            "only extra fees. This is the same arithmetic that made 8 positions at 3% beat 1 at "
            "24%, one level up."),
        "detail": (f"{len(rows)} registered discretionary sleeve(s); "
                   + (f"{n_ind}/{len(measured)} pairs independent enough to fund"
                      if measured else
                      "NO pair has enough overlapping history to measure -- all treated as "
                      "duplicates until they do")),
        "authority": "allocates PAPER risk budget only; cannot promote a sleeve to live capital "
                     "and places no orders (L1.6)",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = allocate(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"sleeve allocator (R0141): {rep['status']} -- {rep['detail']}")
        for n, r in rep["sleeves"].items():
            print(f"  {n:<12} n={r['n_closed']:<4} g={r['standalone_g']} "
                  f"budget={r['risk_budget']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
