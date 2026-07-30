"""RECORD A CAPITAL EVENT -- the principal-only way a ruin stop is cleared (Gate 0 launch day).

A ruin floor is a STOP, not a pause, and until 2026-07-30 this desk's had no defined way back. The
carry book flattened on 113 consecutive rebalances because `dd_start` was measured against an
inception frozen at $5,000 since 2026-07-02, and the loop is closed by construction: flatten means
no opens, no opens means no funding, no funding means equity never moves, so the verdict never
changes. It also froze Gate 0's live-fills clock at 26.42 of 28 days -- the desk was closer to
launching than it could ever get again by trading well.

This is the way back, and it is deliberately a human act with a paper trail.

    # launch day: record the deposit BEFORE the executor's next tick
    python scripts/record_capital_event.py --deposit 1000 \
        --by "principal" --reason "Gate 0 launch funding: initial live deposit"

    python scripts/record_capital_event.py --show          # the ledger + current rail state

WHAT IT WILL REFUSE. A re-base with no new capital while a ruin stop is live -- that clears the
breach while nothing about the book has improved, which is the exact move L1.23 and the L2.8a
immutable core exist to prevent. Overriding it requires `--by "PRINCIPAL-OVERRIDE <name>"`, which
puts a name in an append-only ledger rather than letting a rail get cleared by nobody in
particular. The ruin threshold itself is never touched by anything here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.risk import capital_events as CE  # noqa: E402
from libs.risk import risk_controls  # noqa: E402

_STATE = _ROOT / "data/cashcarry_state.json"


def _state() -> dict[str, Any]:
    try:
        loaded: dict[str, Any] = json.loads(_STATE.read_text("utf-8"))
        return loaded
    except (OSError, ValueError):
        return {}


def _live_equity(st: dict[str, Any]) -> float:
    """Combined equity as the executor computes it: futures equity + banked realised spot P&L."""
    return float(st.get("last_combined_equity",
                        st.get("start_futures_equity", 0.0))) + 0.0


def _show() -> int:
    st = _state()
    raw_start = float(st.get("start_futures_equity", 0.0))
    eff = CE.effective_start_equity(raw_start)
    eq = _live_equity(st)
    print(f"inception (raw state)     ${raw_start:,.2f}")
    print(f"inception (effective)     ${eff:,.2f}"
          + ("   <- re-based by a recorded capital event" if eff != raw_start else ""))
    print(f"combined equity           ${eq:,.2f}")
    if eff > 0:
        d = risk_controls.evaluate(eq, eff, max(eff, eq), 0.0, ruin_cap_lev=8.0)
        print(f"drawdown from inception   {eq / eff - 1.0:+.1%}")
        print(f"rail verdict              {d.action.upper()}  ({'; '.join(d.reasons)})")
    h = CE.history()
    print(f"\ncapital events recorded: {len(h)}")
    for e in h:
        print(f"  {e['at'][:19]}  {e['kind']:<11} deposit ${e['deposit_usd']:>10,.2f}  "
              f"inception ${e['start_equity_before']:,.2f} -> ${e['start_equity_after']:,.2f}")
        print(f"      by {e['authorised_by']}: {e['reason']}")
        print(f"      cumulative loss since FIRST inception: "
              f"${e['cumulative_loss_since_first_inception_usd']:,.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="print the ledger and current rail state")
    ap.add_argument("--deposit", type=float, default=0.0, help="new capital arriving, USD")
    ap.add_argument("--equity", type=float, default=None,
                    help="combined equity BEFORE the deposit (default: read from state)")
    ap.add_argument("--start", type=float, default=None,
                    help="override the inception being replaced (default: effective inception "
                         "from state + ledger). Needed to verify the refusal path on a box whose "
                         "state file is absent, where inception would otherwise default to equity")
    ap.add_argument("--by", default="", help='who authorises this (or "PRINCIPAL-OVERRIDE <name>")')
    ap.add_argument("--reason", default="", help="what happened and why, in a sentence")
    ap.add_argument("--kind", default="DEPOSIT", choices=["DEPOSIT", "WITHDRAWAL", "RESTART"])
    args = ap.parse_args()

    if args.show or (not args.by and not args.reason and args.deposit == 0.0):
        return _show()

    st = _state()
    eq = args.equity if args.equity is not None else _live_equity(st)
    start = (args.start if args.start is not None
             else CE.effective_start_equity(float(st.get("start_futures_equity", eq))))
    try:
        ev = CE.rebase(equity_now=eq, start_equity=start, deposit_usd=args.deposit,
                       authorised_by=args.by, reason=args.reason, kind=args.kind)
    except CE.CapitalEventRefused as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(f"recorded {ev.kind}: inception ${ev.start_equity_before:,.2f} -> "
          f"${ev.start_equity_after:,.2f} (deposit ${ev.deposit_usd:,.2f})")
    print(f"  authorised by {ev.authorised_by}: {ev.reason}")
    print(f"  cumulative loss since FIRST inception: "
          f"${ev.cumulative_loss_since_first_inception_usd:,.2f}")
    print(f"-> {CE.LEDGER.relative_to(_ROOT)}")
    print("\nThe rail now measures drawdown from the new inception. The threshold is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
