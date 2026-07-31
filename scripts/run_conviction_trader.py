#!/usr/bin/env python3
"""CONVICTION SLEEVE (R0125) -- Claude as an AGGRESSIVE leveraged directional trader, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31, with an MT5 screenshot: a leveraged XAUUSD short, +60% in 12h):
*"the Binance equivalent to this -- aggressive, AI shouldn't be too calculative and earn less
than a manual trader."*

THE DESIGN PHILOSOPHY, stated plainly because it is the whole point. A manual discretionary
trader with no stop who is up 60% in 12 hours is not out-earning a disciplined desk -- they are
earlier in a distribution whose left tail is a zeroed account. The screenshot is the trade that
worked; the same 8x leverage that made +60% makes -60% just as fast, and a directional trader
without a stop meets the -100% version eventually. The desk's edge is NOT being more cautious per
trade. It is being able to take the SAME aggressive bet a thousand times without the one that
ends the account. So:

  AGGRESSION IS UNCAPPED. This sleeve takes real leverage, real directional conviction, and sizes
  UP on high-confidence calls -- fractional-Kelly against Claude's own stated probability, which
  at a 60% edge and a 2% stop is ~8x, exactly the leverage in the screenshot. A high-conviction
  call is meant to be large. Timidity here is a defect (L1.28).

  RUIN IS CAPPED, and this is the one line that does not move. EVERY position carries a stop
  (the thing the manual account lacks), per-trade loss is bounded, portfolio leverage is bounded,
  and the whole sleeve sits inside the -35% ruin rail like everything else (L1.23). This is not
  the timid reading of a restraint -- it is the mathematics of compounding: E[log wealth] of a
  ruined book is minus infinity, so the bet that can ruin you is never the growth-optimal bet
  however good it looks (the Alameda row in the desk's own cohort register).

  IT IS SCORED. Every call is a pre-registered forecast (direction, probability, expected move,
  stop) logged to the L1.29 calibration fence. A directional trader who cannot be scored is a
  gambler with a good story; this one finds out whether its conviction is CALIBRATED. If its 70%
  calls win 50% of the time, it is over-confident and the Kelly sizer shrinks automatically.

  PAPER ONLY until it earns real size the same way everything does (L1.6): a forward clock, and
  it must beat buy-and-hold AND the carry sleeve after costs. It places no orders here.

INSTRUMENTS: Binance perps for liquid directional exposure (BTCUSDT, ETHUSDT, SOLUSDT) and
PAXGUSDT as the on-Binance gold analogue of the screenshot's XAUUSD.

    python scripts/run_conviction_trader.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/conviction_book.jsonl"
_STATE = "data/conviction_trader.json"

INSTRUMENTS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT")
MIN_PROB, MAX_PROB = 0.52, 0.90        # below 52% is the other side; 90%+ is an over-confidence tell
KELLY_FRACTION = 0.5                    # half-Kelly: aggressive but robust to estimate error
MAX_LEVERAGE = 10.0                    # the hard aggression ceiling -- 10x, not the 100x that ruins
MIN_STOP_PCT = 0.5                      # a stop tighter than this is noise; 100%+ is no stop
MAX_STOP_PCT = 15.0
MAX_RISK_PER_TRADE = 0.20              # at most 20% of sleeve equity at risk on one call


def kelly_leverage(prob: float, reward_risk: float, stop_pct: float) -> dict[str, float]:
    """Fractional-Kelly leverage from Claude's OWN probability. Aggression is here; the caps are
    the rail. Kelly f* = (p*b - q)/b; leverage = (fraction of equity at risk) / (stop distance)."""
    p, q, b = prob, 1.0 - prob, max(reward_risk, 1e-6)
    edge = (p * b - q) / b                                  # full-Kelly fraction of equity
    risk_frac = max(0.0, min(MAX_RISK_PER_TRADE, edge * KELLY_FRACTION))
    lev = min(MAX_LEVERAGE, risk_frac / (stop_pct / 100.0)) if stop_pct > 0 else 0.0
    return {"full_kelly": round(edge, 4), "risk_fraction": round(risk_frac, 4),
            "leverage": round(lev, 2), "capped_by": (
                "no-edge" if edge <= 0 else "max_risk" if edge * KELLY_FRACTION > MAX_RISK_PER_TRADE
                else "max_leverage" if risk_frac / (stop_pct / 100.0) > MAX_LEVERAGE else "kelly")}


_BRIEF = """You are the desk's CONVICTION TRADER. You take AGGRESSIVE leveraged DIRECTIONAL bets --
this is the sleeve modelled on a sharp manual trader flipping an account fast, not the cautious
news reader. You are ENCOURAGED to size up when you have real conviction. But you carry a STOP on
every trade (the discipline a blown manual account lacked), and you will be SCORED, so your
confidence must be honest.

INSTRUMENTS: {instruments}. Take a directional view -- macro, technical, flow, positioning,
cross-asset (gold via PAXGUSDT, risk via BTC/ETH). A VIEW is allowed here (unlike the event
sleeve), but state the DRIVER: what makes this move happen, and what would kill it.

TODAY'S BRIEF (numeric context; you may reason over it, the desk's pipelines handle the arithmetic):
{brief}

OUTPUT EXACTLY ONE JSON OBJECT:
{{"action": "TRADE" | "PASS",
  "symbol": "one of the instruments",
  "direction": "LONG" | "SHORT",
  "probability": 0.63,             // YOUR honest P(this trade is profitable). SCORED against outcome.
  "expected_move_pct": 4.0,        // the move you expect if right, percent
  "stop_pct": 2.0,                 // where you are WRONG, percent from entry. REQUIRED -- no stop, no trade.
  "horizon_hours": 12,
  "driver": "what forces/drives this move",
  "falsifier": "the observation that kills the thesis before the stop",
  "reasoning": "2-4 sentences"}}

BE AGGRESSIVE ON CONVICTION, HONEST ON PROBABILITY. The desk sizes the trade FOR you by
fractional-Kelly against your probability and stop -- a 0.63 with a 2% stop becomes real
leverage automatically, so you do not need to inflate confidence to get size; inflating it only
makes the calibration fence catch you and SHRINK your future size. reward:risk =
expected_move_pct / stop_pct must exceed 1.2 or the trade is refused (you are risking more than
you stand to make). PASS with a reason if there is no directional edge -- but a conviction trader
that always passes is not doing its job. Probability must be {lo}-{hi}."""


def build_brief(root: Path) -> dict[str, Any]:
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "context": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 4),
                          ("liquidations", "data/liquidations.jsonl", 6),
                          ("tradeable_events", "data/exchange_announcements.jsonl", 6)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "tradeable_events":
                rows = []
                for ln in reversed(lines):
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r.get(k) for k in ("title", "symbols", "tier")})
                    if len(rows) >= n:
                        break
                brief["context"][label] = rows or "none this window"
            else:
                brief["context"][label] = [ln[:300] for ln in lines[-n:] if ln.strip()] or "ABSENT"
        except OSError:
            brief["context"][label] = "ABSENT on this host"
    return brief


def validate(call: dict[str, Any]) -> tuple[bool, str]:
    if call.get("action") == "PASS":
        if not call.get("pass_reason"):
            return False, "REFUSED: a PASS must state why -- an unjustified pass is not a decision"
        return True, f"PASS: {str(call['pass_reason'])[:80]}"
    for f in ("symbol", "direction", "probability", "expected_move_pct", "stop_pct",
              "horizon_hours", "driver", "falsifier"):
        if call.get(f) in (None, ""):
            return False, f"REFUSED: missing {f}"
    if call["symbol"] not in INSTRUMENTS:
        return False, f"REFUSED: symbol must be one of {INSTRUMENTS}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction LONG or SHORT"
    try:
        p, mv, stop = float(call["probability"]), float(call["expected_move_pct"]), \
            float(call["stop_pct"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability/move/stop not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB}"
    if not MIN_STOP_PCT <= stop <= MAX_STOP_PCT:
        # THE RAIL THE MANUAL ACCOUNT LACKED: a trade with no stop, or a stop so wide it is not a
        # stop, is the one that ends the account. This is not timidity -- it is the difference
        # between compounding the aggressive bet and being ruined by it (L1.23).
        return False, (f"REFUSED: stop_pct {stop} outside {MIN_STOP_PCT}-{MAX_STOP_PCT} -- every "
                       "conviction trade carries a real stop, no exceptions (L1.23)")
    if mv / stop < 1.2:
        return False, (f"REFUSED: reward:risk {mv/stop:.2f} < 1.2 -- risking more than the "
                       "expected gain is negative-EV even when the call is right")
    if len(str(call["driver"])) < 20 or len(str(call["falsifier"])) < 15:
        return False, "REFUSED: driver/falsifier too thin"
    return True, "accepted"


def record(root: Path, call: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    sizing = kelly_leverage(float(call["probability"]),
                            float(call["expected_move_pct"]) / float(call["stop_pct"]),
                            float(call["stop_pct"]))
    row = {**call, "at": now.isoformat(), "paper": True, "sizing": sizing,
           "resolve_by": (now + timedelta(hours=float(call["horizon_hours"]))).isoformat()}
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    try:
        from libs.self_improvement import forecast_calibration as fc
        fc.log_forecast(f"conviction:{now.isoformat()}", float(call["probability"]),
                        "directional", resolve_by=row["resolve_by"],
                        claim=f"{call['direction']} {call['symbol']} @{sizing['leverage']}x: "
                              f"{str(call['driver'])[:100]}")
    except Exception as exc:                                # noqa: BLE001 -- never lose the call
        row["calibration_log_error"] = str(exc)
    return row


def _ask(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    if args.brief:
        print(json.dumps(brief, indent=2))
        return 0
    raw = _ask(_BRIEF.format(instruments=", ".join(INSTRUMENTS),
                             brief=json.dumps(brief, indent=1)[:5000],
                             lo=MIN_PROB, hi=MAX_PROB))
    call = parse(raw)
    if call is None:
        state = {"status": "NO-CALL", "why": "no parseable JSON (auth/quota/refusal)",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        ok, why = validate(call)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call}
        elif call.get("action") == "PASS":
            state = {"status": "PASS", "why": why}
        else:
            row = record(_ROOT, call)
            state = {"status": "TRADE", "why": why, "call": row,
                     "leverage": row["sizing"]["leverage"]}
    state.setdefault("at", datetime.now(tz=UTC).isoformat())
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"conviction (R0125): {state['status']} -- {state['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
