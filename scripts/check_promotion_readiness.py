"""What each certificate would be worth, and what it would be sized at, before anything is armed.

WHY THIS EXISTS (LAWS III.16, and the last mile of the 2026-08-29 build)

Three modules were built, tested and called by NOTHING:

    lockbox           the sealed holdout and the fresh-context reviewer
    portfolio_weight  what a sleeve adds to a book it is not yet part of
    account_profile   the risk envelope per venue, live vs prop

All three belong at the same moment in the pipeline -- the gap between "this certificate exists"
and "this certificate is armed" -- and none of them was in it. A promotion gate nobody calls is
not a gate; it is a description of one.

WHAT THIS ANSWERS, per certificate, before a single order:

    marginal value    correlation of this sleeve's forward returns to the live book. A clone at
                      rho 0.98 is the first sleeve bought twice at double the risk, and standalone
                      metrics cannot see that because the difference is not in either sleeve.
    venue sizing      what it would risk on the live account vs each prop envelope. The same
                      certificate is a 3% position on own capital and a 0.18% position on a 4%
                      static drawdown, and treating those as one number is how funded accounts
                      die in week one.
    lockbox state     whether the holdout has been spent on this fingerprint, and whether any
                      fingerprint has been asked TWICE. A repeat is how a holdout is consumed
                      without anyone deciding to consume it.

IT ARMS NOTHING. Every number here is a report. Promotion is the promoter's decision under the
principal's rules, and a script that both computed readiness and acted on it would be the
grading-own-homework failure this desk spent the day removing from three other places.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
SHADOW = DESK / "reports" / "shadow"
OUT = ROOT / "data" / "promotion_readiness.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DESK))

#: Forward phases that count. A selection-era fill in a correlation estimate makes two sleeves
#: look related because they were SELECTED together, not because they trade together.
_FORWARD_PHASES = ("forward", None)


def _forward_series() -> dict[str, list[float]]:
    """Per-sleeve forward R series, keyed by ledger stem."""
    out: dict[str, list[float]] = {}
    for path in sorted(SHADOW.glob("ledger_*.json")):
        try:
            rows = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rows, dict):
            rows = rows.get("trades") or []
        rs = [float(r["r_multiple"]) for r in rows
              if isinstance(r, dict) and r.get("phase") in _FORWARD_PHASES
              and r.get("r_multiple") is not None]
        if rs:
            out[path.stem.removeprefix("ledger_")] = rs
    return out


def _live_book(series: dict[str, list[float]]) -> list[float]:
    """Aggregate return stream of everything currently LIVE in the sleeve registry.

    An empty book is the honest answer while nothing is promoted, and `portfolio_weight` returns
    full weight for it -- the first sleeve cannot be redundant with nothing.
    """
    try:
        reg = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    live_keys = {k for k, v in (reg.get("sleeves") or {}).items()
                 if isinstance(v, dict) and v.get("status") == "PROMOTED"}
    book: list[float] = []
    for key in live_keys:
        sym = key.split(".", 1)[0]
        for stem, rs in series.items():
            if stem.startswith(sym):
                book.extend(rs)
    return book


def main() -> int:
    from mt5desk.account_profile import (
        E8_ONE_PHASE_100K,
        E8_PRO,
        LIVE,
        risk_for_expectancy,
    )
    from mt5desk.portfolio_weight import effective_bets, portfolio_weight

    from libs.research.lockbox import LockboxService

    now = datetime.now(tz=UTC)
    series = _forward_series()
    book = _live_book(series)

    print(f"PROMOTION READINESS {now.isoformat(timespec='seconds')}")
    print(f"  sleeves with forward evidence: {len(series)}")
    print(f"  live book return stream: {len(book)} observations"
          f"{'  (EMPTY -- nothing promoted, so nothing can be redundant yet)' if not book else ''}")

    rows: list[dict[str, Any]] = []
    weights: list[float] = []
    for stem, rs in sorted(series.items()):
        w, why = portfolio_weight(rs, book)
        exp_r = sum(rs) / len(rs)
        # SIZE IT PER VENUE. The same certificate is a different position on each account, and
        # the prop figure is read off MEASURED expectancy rather than assumed.
        prop_risk, prop_why = risk_for_expectancy(exp_r if len(rs) >= 20 else None,
                                                  E8_ONE_PHASE_100K)
        rows.append({
            "sleeve": stem, "n": len(rs), "exp_r": round(exp_r, 5),
            "portfolio_weight": round(w, 4), "weight_why": why,
            "live_risk_frac": round(LIVE.risk_frac * w, 5),
            "e8_pro_risk_frac": round(E8_PRO.risk_frac * w, 5),
            "e8_one_phase_risk_frac": round(prop_risk * w, 5),
            "e8_one_phase_why": prop_why,
        })
        weights.append(w)

    if rows:
        print(f"\n  {'sleeve':34s} {'n':>4s} {'exp_r':>8s} {'wt':>5s} "
              f"{'live%':>6s} {'e8_1ph%':>8s}")
        for r in sorted(rows, key=lambda x: -x["n"])[:12]:
            print(f"  {r['sleeve'][:34]:34s} {r['n']:4d} {r['exp_r']:+8.4f} "
                  f"{r['portfolio_weight']:5.2f} {r['live_risk_frac'] * 100:6.2f} "
                  f"{r['e8_one_phase_risk_frac'] * 100:8.3f}")
        # EFFECTIVE BETS IS MEANINGLESS AGAINST AN EMPTY BOOK. With nothing promoted every
        # weight is 1.0, and the participation ratio of N equal weights is exactly N -- so this
        # would print "34 independent bets" when the truth is that independence was never
        # measured. That is the precise class of false-confidence number this desk spent the day
        # removing; printing it here would be reintroducing it in a new place.
        if book:
            n_eff = effective_bets(weights)
            print(f"\n  effective bets across {len(weights)} sleeves: {n_eff:.2f}")
            print(f"    -- {len(weights)} names carrying {n_eff:.1f} independent bets is the "
                  f"number that decides whether the book grows or just gets bigger")
        else:
            print(f"\n  effective bets: UNMEASURABLE -- the live book is empty, so every weight "
                  f"is 1.0 by default and the participation ratio would report {len(weights)}.00 "
                  f"for {len(weights)} sleeves. That is arithmetic, not independence.")

    # ---- LOCKBOX INTEGRITY -------------------------------------------------------------------
    lb_ledger = DESK / "reports" / "lockbox_ledger.json"
    try:
        svc = LockboxService(data_path=DESK / "data" / "lockbox", ledger_path=lb_ledger)
        integ = svc.integrity()
    except Exception as exc:
        integ = {"verdict": "UNREADABLE", "why": f"{type(exc).__name__}: {str(exc)[:110]}"}
    print(f"\n  LOCKBOX: {integ.get('verdict')} "
          f"({integ.get('evaluations', 0)} evaluation(s), "
          f"{integ.get('repeat_attempts', 0)} repeat attempt(s))")
    if integ.get("repeat_attempts"):
        print(f"    {integ.get('why', '')[:150]}")

    payload = {"checked_at": now.isoformat(timespec="seconds"),
               "sleeves": rows, "live_book_observations": len(book),
               "effective_bets": (round(effective_bets(weights), 3)
                                  if (weights and book) else None),
               "effective_bets_note": (None if book else
                                       "unmeasurable against an empty live book"),
               "lockbox": integ,
               "authority": "REPORT ONLY -- arms nothing; promotion is the promoter's decision"}
    OUT.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    print(f"\n  -> {OUT}")
    return 1 if integ.get("verdict") in ("HOLDOUT REUSED", "UNREADABLE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
