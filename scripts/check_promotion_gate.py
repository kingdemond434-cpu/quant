#!/usr/bin/env python3
"""PROMOTION GATE (R0150) -- what evidence buys what expansion, fixed BEFORE the evidence exists.

PRINCIPAL (2026-07-31): *"if it works we will expand and advance this after a week, maxxing it."*

Right. And the honest moment to define "works" and "expand" is NOW, while nobody knows the answer.

WHY THIS IS THE SYMMETRIC HALF OF THE KILL CONDITION. R0142 pre-registered the exit: 50 trades,
under a 25% hit rate, graveyard, no extensions. The desk therefore had a defined way to DIE and no
defined way to GROW -- which is not caution, it is an asymmetry that makes expansion an improvised
decision taken in the mood of a good week. A week of wins creates pressure to scale immediately,
and scaling on 50 trades is how a lucky streak becomes a large loss.

THE TRAP THIS CLOSES, and it is the specific one a good week produces: 50 trades in seven days is
ONE MARKET REGIME. A sleeve that made money in a single trending week has evidence about trending
weeks and nothing else. So every rung requires CALENDAR TIME as well as sample size -- they are
different evidence and only one of them can be manufactured by raising the cadence.

THE LADDER. Each rung states its cost of being wrong, and no rung may be skipped:

  RUNG 0  PAPER, 6% floor cap                     -- where it is now
  RUNG 1  50 closed + 14 days + hit > breakeven   -> per-trade cap rises to measured half-Kelly
          + attribution clean                        (still PAPER; this is the R0145 mechanism)
  RUNG 2  100 closed + 30 days + beats buy-and-   -> LIVE at 1% of book. The first real money, at
          hold AND carry after costs + Brier<0.25    a size where being wrong is tuition
  RUNG 3  200 closed + 60 days + rung 2 held      -> LIVE at 5% of book
          + max drawdown inside the sleeve rail
  RUNG 4  400 closed + 120 days + two regimes     -> LIVE at 15% of book, the ceiling for one
          + independent of the carry sleeve          discretionary sleeve

WHY THE STEPS ARE SMALL AT THE BOTTOM. The first live rung is 1%, not 10%, because the transition
from paper to live is where unmodelled costs appear -- real slippage, real fills, real funding at
the moment it matters. A sleeve that survives paper and dies on execution should cost tuition, not
capital.

REFUSES TO SKIP. Meeting rung 3's trade count while failing rung 2's benchmark grants rung 1, not
rung 3. Evidence is a ladder, not a maximum.

UNMEASURED IS NEVER A PASS: a criterion that cannot be evaluated blocks the rung, because the
alternative is a promotion granted by a broken reader.

    python scripts/check_promotion_gate.py [--json]
"""
from __future__ import annotations

import argparse
import json
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

_STATE = "data/promotion_gate.json"

#: Cost-adjusted breakeven hit rate, from the measured fee/slippage/funding stack in
#: resolve_paper_book (~17% of one R at this leverage). Clearing it is necessary, never sufficient.
BREAKEVEN_HIT = 0.311

#: THE LADDER. (rung, closed trades, calendar days, extra criteria, what it grants).
#: Calendar days are NOT redundant with trade count: 50 trades in a week is ONE regime, and
#: cadence can manufacture sample size but never time.
_RUNGS: tuple[dict[str, Any], ...] = (
    {"rung": 1, "trades": 50, "days": 14,
     "needs": ("hit_rate_above_breakeven", "attribution_clean"),
     "grants": "per-trade cap rises from the 6% floor to measured half-Kelly (still PAPER)"},
    {"rung": 2, "trades": 100, "days": 30,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative"),
     "grants": "LIVE at 1% of book -- the first real money, at a size where being wrong is tuition"},
    {"rung": 3, "trades": 200, "days": 60,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative", "drawdown_inside_rail"),
     "grants": "LIVE at 5% of book"},
    {"rung": 4, "trades": 400, "days": 120,
     "needs": ("hit_rate_above_breakeven", "attribution_clean", "beats_buy_and_hold",
               "calibration_informative", "drawdown_inside_rail", "two_regimes",
               "independent_of_carry"),
     "grants": "LIVE at 15% of book -- the ceiling for one discretionary sleeve"},
)


def _criteria(root: Path) -> dict[str, dict[str, Any]]:
    """Evaluate every criterion the ladder can ask about. UNMEASURED is never True."""
    out: dict[str, dict[str, Any]] = {}

    def put(k: str, ok: bool | None, why: str) -> None:
        out[k] = {"ok": bool(ok) if ok is not None else None,
                  "state": "UNMEASURED" if ok is None else ("PASS" if ok else "FAIL"), "why": why}

    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        pnl = {}
        put("hit_rate_above_breakeven", None, f"paper book unmarked ({type(exc).__name__})")
        put("beats_buy_and_hold", None, "paper book unmarked")
        put("drawdown_inside_rail", None, "paper book unmarked")
    if pnl:
        n = int(pnl.get("n_resolved") or 0)
        hit = pnl.get("win_rate")
        put("hit_rate_above_breakeven",
            None if hit is None or n < 20 else float(hit) > BREAKEVEN_HIT,
            f"{hit} vs {BREAKEVEN_HIT:.1%} breakeven over {n} closed"
            if hit is not None else "no closed trades")
        bh = pnl.get("beats_buy_and_hold")
        put("beats_buy_and_hold", None if bh is None else bool(bh),
            f"sleeve {pnl.get('sleeve_return')} vs buy-and-hold {pnl.get('buy_and_hold_return')}")
        eq = pnl.get("equity") or {}
        mdd = eq.get("max_drawdown")
        put("drawdown_inside_rail", None if mdd is None else float(mdd) < 0.35,
            f"max drawdown {mdd} vs the 35% sleeve rail")

    try:
        att = json.loads((root / "data/mechanism_attribution.json").read_text("utf-8"))
        put("attribution_clean", att.get("status") == "ATTRIBUTED",
            f"attribution status {att.get('status')}")
    except (OSError, ValueError) as exc:
        put("attribution_clean", None, f"attribution unreadable ({type(exc).__name__})")

    try:
        probe = json.loads((root / "data/calibration_probe.json").read_text("utf-8"))
        v = (probe.get("verdict") or {}).get("state")
        put("calibration_informative", None if v in (None, "ACCUMULATING", "UNMEASURED")
            else v == "INFORMATIVE", f"calibration verdict {v}")
    except (OSError, ValueError) as exc:
        put("calibration_informative", None, f"probe unreadable ({type(exc).__name__})")

    try:
        alloc = json.loads((root / "data/sleeve_allocation.json").read_text("utf-8"))
        st = alloc.get("status")
        put("independent_of_carry", None if st in (None, "UNMEASURED") else st == "DIVERSIFIED",
            f"sleeve allocation status {st}")
    except (OSError, ValueError) as exc:
        put("independent_of_carry", None, f"allocation unreadable ({type(exc).__name__})")

    # TWO REGIMES -- now MEASURED rather than permanently blocking. Every trade is already tagged
    # with the volatility regime at entry (run_conviction_trader.setup_features), so "did this
    # record span more than one tape" is answerable from the marks. A criterion that can never be
    # satisfied is not a standard, it is a wall, and a wall that nobody can climb gets removed
    # rather than met -- which is how a ladder quietly loses its top rung.
    regimes = {(m.get("setup") or {}).get("vol_regime") for m in (pnl.get("marks") or [])
               if m.get("closed") and (m.get("setup") or {}).get("vol_regime")}
    regimes.discard("UNKNOWN")
    regimes.discard(None)
    put("two_regimes", None if not regimes else len(regimes) >= 2,
        f"closed trades span {sorted(regimes)}" if regimes else
        "no regime tags on any closed trade yet -- UNMEASURED, not satisfied")
    return out


def evaluate(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    crit = _criteria(root)
    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
        n_closed = int(pnl.get("n_resolved") or 0)
        marks = [m.get("exit_at") for m in pnl.get("marks", []) if m.get("exit_at")]
        days = ((now - datetime.fromisoformat(min(marks))).days if marks else 0)
    except (OSError, ValueError, KeyError):
        n_closed, days = 0, 0

    granted, blocked_at = 0, None
    rows = []
    for r in _RUNGS:
        fails = [c for c in r["needs"] if not (crit.get(c, {}).get("ok"))]
        ok = n_closed >= r["trades"] and days >= r["days"] and not fails
        rows.append({"rung": r["rung"], "grants": r["grants"],
                     "trades": f"{n_closed}/{r['trades']}", "days": f"{days}/{r['days']}",
                     "unmet": ([f"trades {n_closed}/{r['trades']}"] if n_closed < r["trades"] else [])
                              + ([f"calendar days {days}/{r['days']}"] if days < r["days"] else [])
                              + fails,
                     "met": ok})
        # NO SKIPPING: the ladder stops at the first unmet rung, whatever later counts say.
        if ok and blocked_at is None:
            granted = r["rung"]
        elif blocked_at is None:
            blocked_at = r["rung"]

    return {
        "generated": now.isoformat(),
        "law": "L1.6 -- promotion is bought with evidence, on a ladder fixed BEFORE the evidence "
               "existed. A week of wins is one regime, and cadence can manufacture sample size "
               "but never calendar time.",
        "granted_rung": granted,
        "granted": ("PAPER at the 6% floor cap" if granted == 0
                    else _RUNGS[granted - 1]["grants"]),
        "blocked_at_rung": blocked_at,
        "n_closed": n_closed, "days_of_record": days,
        "criteria": crit,
        "ladder": rows,
        "no_skipping": "meeting a later rung's trade count while failing an earlier rung's "
                       "benchmark grants the EARLIER rung. Evidence is a ladder, not a maximum.",
        "detail": (f"rung {granted} granted ({rows[granted]['unmet'][:1] if granted < len(rows) else []}"
                   f" blocks rung {blocked_at})" if blocked_at else f"rung {granted} granted"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = evaluate(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"promotion gate (L1.6): rung {rep['granted_rung']} -- {rep['granted']}")
        for row in rep["ladder"]:
            if not row["met"]:
                print(f"  rung {row['rung']} blocked by: {', '.join(map(str, row['unmet'][:4]))}")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
