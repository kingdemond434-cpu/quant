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
from datetime import UTC, datetime
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


_FRESH_S = 6 * 3600


def _live_equity(st: dict[str, Any]) -> tuple[float | None, str]:
    """Combined equity from a VERIFIED source, or (None, why) -- never a guessed number.

    THE DEFECT THIS REPLACES (deep-sweep exec F1, R0071a): the old read fell through
    last_combined_equity (which no organ wrote) to the frozen inception to 0.0 -- so the one
    command that runs on launch day would have recorded equity $0.00 and re-based the rail far
    below venue truth. The ladder now is: (1) executor-persisted venue truth, only if FRESH;
    (2) a direct venue read; (3) refusal. An unverifiable equity is a refusal, never a zero --
    a VERIFIED zero (fresh empty account) passes; a fabricated one cannot."""
    ts = st.get("last_combined_equity_at")
    if "last_combined_equity" in st and isinstance(ts, str):
        try:
            age = (datetime.now(tz=UTC) - datetime.fromisoformat(ts)).total_seconds()
        except ValueError:
            age = float("inf")
        if age <= _FRESH_S:
            return (float(st["last_combined_equity"]),
                    f"executor venue-truth persist, {age / 60:.0f}m old")
    try:
        from libs.execution import binance_live as fut
        if fut.has_keys():
            eq = float(fut.account_summary()["equity"]) + float(st.get("realized_spot_pnl", 0.0))
            return (eq, "direct venue read (futures equity + banked spot P&L; any UNREALISED "
                        "spot P&L is not included -- flatten or pass --equity if positions "
                        "are open)")
    except Exception as exc:                                # refusal path
        return (None, f"venue read failed: {exc}")
    return (None, "no fresh executor persist and no venue keys on this box")


def _show() -> int:
    st = _state()
    raw_start = float(st.get("start_futures_equity", 0.0))
    eff = CE.effective_start_equity(raw_start)
    eq, src = _live_equity(st)
    print(f"inception (raw state)     ${raw_start:,.2f}")
    print(f"inception (effective)     ${eff:,.2f}"
          + ("   <- re-based by a recorded capital event" if eff != raw_start else ""))
    if eq is None:
        print(f"combined equity           UNVERIFIABLE ({src})")
        eq = 0.0
    else:
        print(f"combined equity           ${eq:,.2f}   [{src}]")
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
    if args.equity is not None:
        eq, src = float(args.equity), "explicit --equity from the principal"
    else:
        eq, src = _live_equity(st)
    if eq is None:
        # REFUSAL, not a default (R0071a): recording a capital event against a guessed equity
        # re-bases the survival rail against fiction. Check the venue, then pass --equity.
        print(f"REFUSED: combined equity is UNVERIFIABLE on this box ({src}).")
        print("Check the venue balance yourself, then re-run with --equity <number> "
              "(equity BEFORE the deposit lands). A verified 0.00 on a fresh account "
              "is legitimate; an assumed one is how a rail gets re-based ~89% below truth.")
        return 2
    print(f"equity source: {src}")
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
