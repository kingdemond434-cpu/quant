#!/usr/bin/env python3
"""LLM DISCRETIONARY SLEEVE (R0122) -- Claude as a human-style trader, 24/7, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31): *"a strategy where Claude acts like a human trader with a brain
and trades 24/7 at charts."*

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT. It is NOT an LLM staring at chart images calling
breakouts, and refusing that is not timidity -- it is the two measured facts. (1) Language models
reason poorly over precise numeric OHLC: the desk's own numeric pipelines already dominate on
anything expressible as arithmetic, so a model eyeballing candles is a worse version of a tool
that exists. (2) "It looked like a breakout" is a PATTERN WITH NO MECHANISM, which is precisely
the class the 420-tested/0-survived record refuted -- carding it would be breadth-mining with a
narrator attached (L1.16, L1.25).

WHERE AN LLM GENUINELY HAS AN EDGE, and this sleeve lives exactly there: UNSTRUCTURED
INFORMATION THAT NUMERIC MODELS CANNOT PARSE AT ALL. Exchange announcements, listing/delisting
notices, contract-spec changes, chain incidents, regulatory statements, unusual forum activity --
text a human trader reads and reacts to, arriving 24/7 while a human sleeps. The mechanism is
stated and falsifiable: *an event whose implication requires reading prose is priced more slowly
than one expressible as a number, and the desk can read it continuously.* That is a FORCED-
PARTICIPANT-adjacent claim (someone must reposition when a contract spec changes) and it is
testable.

THE HONEST HARNESS, which is what makes this worth running at all:
  * EVERY call is a PRE-REGISTERED FORECAST -- direction, horizon, and an explicit PROBABILITY --
    logged to libs.self_improvement.forecast_calibration. It is therefore SCORED automatically
    (Brier, bias, hit-rate) by the L1.29 calibration fence, and its measured over-confidence is
    fed back as a shrinkage. An LLM trader that cannot be scored is a story generator; this one
    grades itself whether it likes the answer or not.
  * EVERY call states a MECHANISM and a FALSIFIER, or it is refused at write time. No mechanism,
    no trade -- the same bar every axis on this desk faces.
  * PAPER ONLY, permanently, until it earns promotion the same way as everything else: a
    pre-registered forward clock, a Holm slot, and Stage-B evidence (L1.6). This file places no
    orders and imports no connector -- a test asserts it.
  * Its benchmark is not zero. A discretionary sleeve must beat BUY-AND-HOLD and the desk's own
    carry sleeve after costs, or it is an expensive way to be average.

    python scripts/run_llm_trader.py --brief        # build the market brief only
    python scripts/run_llm_trader.py                # brief -> call -> log forecast -> paper mark
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

_BOOK = "data/llm_trader_book.jsonl"
_STATE = "data/llm_trader.json"
MIN_PROB, MAX_PROB = 0.50, 0.95      # a call below 50% is a call the other way; 95%+ is a tell
MAX_OPEN = 3                          # concurrent paper calls -- concentration discipline

#: CONTROLLED MECHANISM TAXONOMY (external critique, 2026-07-31). Free-text mechanisms cannot be
#: AGGREGATED, so "which mechanism families actually produce alpha" is unanswerable and every
#: thesis looks equally novel. Forcing each call into one of these makes mechanism survival
#: measurable exactly like an axis: after N calls the desk can retire the families that never
#: pay and concentrate on the ones that do. NEW families are added deliberately, never invented
#: per-call -- an unbounded vocabulary is the same as no vocabulary.
MECHANISMS = (
    "FORCED_LIQUIDATION",      # leveraged positions must close at any price
    "COLLATERAL_CHANGE",       # margin/leverage/haircut rules force repositioning
    "LIQUIDITY_MIGRATION",     # venue/pool listing or delisting moves where trading happens
    "INVENTORY_ADJUSTMENT",    # market makers rebalance inventory
    "ARBITRAGE_DISLOCATION",   # a link between venues/instruments breaks
    "SUPPLY_SHOCK",            # unlocks, emissions, burns, treasury movement
    "REGULATORY_CONSTRAINT",   # access/eligibility restricted or expanded
    "INFRASTRUCTURE_FAILURE",  # exploit, bridge/validator/RPC outage
    "GOVERNANCE_CHANGE",       # tokenomics, fees, emissions decided
)

#: WHO IS FORCED TO TRANSACT -- the external critique's sharpest structural suggestion. "LONG
#: because bullish" is untestable; "market makers must reduce inventory" names a participant
#: whose behaviour can be checked against OI, depth and flow. Forced flows persist; discretionary
#: ones do not, and this field is what lets the desk tell them apart afterwards.
PARTICIPANTS = ("LEVERAGED_LONGS", "LEVERAGED_SHORTS", "MARKET_MAKERS", "ARBITRAGEURS",
                "VALIDATORS_MINERS", "TREASURY_ISSUER", "ETF_AUTHORIZED_PARTICIPANTS",
                "LENDING_PROTOCOL_USERS", "NOBODY_FORCED")

_CALL_BRIEF = """You are the desk's DISCRETIONARY TRADER. You trade like a thoughtful human: you
read what happened, you form a view with a REASON, you state how confident you are, and you say
what would prove you wrong. You are PAPER-TRADING -- no capital moves on your word, and your only
route to real size is the same forward-evidence gate every other strategy faces.

YOUR EDGE IS NOT CHARTS. The desk's numeric pipelines beat you at anything arithmetic: momentum,
carry, z-scores, cross-sectional ranks. Do not compete there -- you will lose and you will waste
the slot. YOUR EDGE IS PROSE: exchange announcements, contract-spec changes, listing/delisting
notices, chain incidents, regulatory statements, unusual community activity -- information whose
IMPLICATION requires reading, arriving at 3am while humans sleep. Trade the implication of an
EVENT, not the shape of a line.

TODAY'S BRIEF:
{brief}

OUTPUT EXACTLY ONE JSON OBJECT, no prose around it:
{{"action": "CALL" | "PASS",
  "symbol": "BTCUSDT",
  "direction": "LONG" | "SHORT",
  "horizon_hours": 8,
  "probability": 0.62,            // YOUR honest P(this call is right). It WILL be scored.
  "mechanism": "who is forced to do what, and why that moves price",
  "falsifier": "the observation that would prove this wrong",
  "reasoning": "2-4 sentences"}}

PASS IS A FIRST-CLASS ANSWER and most windows deserve it: if nothing happened that requires
reading prose to understand, there is no edge here and a call would be noise. A desk that trades
every window is a desk with no filter. REFUSED AT WRITE TIME: any call without a real mechanism
(not a pattern), without a falsifier, or with a probability outside {lo}-{hi}.

BUT A PASS IS ALSO SCORED, and you must justify it. A model that passes on everything gets a
beautiful calibration score and contributes nothing -- so a PASS carries
`passed_on` (the most material event you declined) and `pass_reason` (already priced / no
mechanism / not tradeable / unclear direction). Those declines are marked against the same
horizon as a real call, so the desk can measure whether your filter ADDS value or merely avoids
deciding. Passing is allowed; passing without saying what you passed on is not.

FIELDS REQUIRED ON EVERY CALL, in addition to the above:
  "mechanism_class": one of {mechs}
  "forced_participant": one of {parts} -- who MUST transact, not who might want to
  "compressible": true if a simple IF-THEN rule on the event text would produce this same call.
    ANSWER HONESTLY: if most of your calls are compressible, the desk should replace you with
    ten lines of code, and finding that out is a win, not a loss."""


def build_brief(root: Path) -> dict[str, Any]:
    """Market state + the unstructured feeds this sleeve actually trades on."""
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "sources": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 5),
                          ("defi_lending", "data/defi_lending.jsonl", 2),
                          ("liquidations", "data/liquidations.jsonl", 8),
                          ("announcements", "data/exchange_announcements.jsonl", 10),
                          ("news", "data/news_feed.jsonl", 10)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "announcements":
                # ONLY TRADEABLE ITEMS reach the trader (R0122b): fresh enough to still be
                # unpriced AND material enough to force repositioning. Handing it the archive
                # is how a sleeve "trades" a three-year-old exploit.
                import json as _j
                rows = []
                for ln in reversed(lines):
                    try:
                        r = _j.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r[k] for k in
                                     ("source", "title", "symbols", "latency_minutes", "tier")
                                     if k in r})
                    if len(rows) >= n:
                        break
                brief["sources"][label] = rows or "no TRADEABLE events this window"
                continue
            brief["sources"][label] = [ln[:400] for ln in lines[-n:] if ln.strip()]
        except OSError:
            # ABSENT, never silently empty: a brief that hides its missing feeds invites a call
            # made on nothing (L1.28a).
            brief["sources"][label] = "ABSENT on this host"
    return brief


def validate_call(call: dict[str, Any]) -> tuple[bool, str]:
    """The write-time bar. A call that cannot state WHY is not a call (L1.16)."""
    if call.get("action") == "PASS":
        # A PASS IS A DECISION AND IS SCORED. Without this the model optimises toward passing:
        # perfect calibration, zero economic value (external critique, 2026-07-31).
        if not call.get("pass_reason"):
            return False, ("REFUSED: a PASS must say WHY -- an unjustified pass is how a model "
                           "farms a clean Brier score while contributing nothing")
        return True, f"PASS recorded and scored: {str(call.get('pass_reason'))[:80]}"
    for field in ("symbol", "direction", "horizon_hours", "probability", "mechanism",
                  "falsifier", "mechanism_class", "forced_participant"):
        if not call.get(field):
            return False, f"REFUSED: missing {field}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction must be LONG or SHORT"
    try:
        p = float(call["probability"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, (f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB} -- below 50% is "
                       "a call the other way, above 95% is a tell that the model is not scoring "
                       "itself honestly")
    mech = str(call["mechanism"])
    if len(mech) < 25:
        return False, "REFUSED: mechanism too thin to be a mechanism"
    # A PATTERN is not a MECHANISM -- this is the 420/0 lesson enforced at write time.
    pattern_words = ("breakout", "support", "resistance", "trend line", "trendline",
                     "head and shoulders", "golden cross", "oversold", "overbought")
    if any(w in mech.lower() for w in pattern_words) and "because" not in mech.lower():
        return False, ("REFUSED: mechanism reads as a chart PATTERN, not a mechanism -- name who "
                       "is forced to do what and why (L1.16). Patterns are the class the desk's "
                       "420-tested/0-survived record already refuted")
    if len(str(call["falsifier"])) < 15:
        return False, "REFUSED: no real falsifier"
    if call["mechanism_class"] not in MECHANISMS:
        return False, (f"REFUSED: mechanism_class must be one of {MECHANISMS} -- free-text "
                       "mechanisms cannot be aggregated, so mechanism survival becomes "
                       "unmeasurable and weak families never get retired")
    if call["forced_participant"] not in PARTICIPANTS:
        return False, f"REFUSED: forced_participant must be one of {PARTICIPANTS}"
    if call["forced_participant"] == "NOBODY_FORCED":
        return False, ("REFUSED: no forced participant means no forced flow -- that is a VIEW, "
                       "not a mechanism, and views are what the 420/0 record already refuted")
    return True, "accepted"


def record_call(root: Path, call: dict[str, Any]) -> dict[str, Any]:
    """Append to the paper book AND log the forecast so L1.29 scores it automatically."""
    now = datetime.now(tz=UTC)
    row = {**call, "at": now.isoformat(),
           "resolve_by": (now + timedelta(hours=float(call.get("horizon_hours", 8)))).isoformat(),
           "paper": True}
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    if call.get("action") == "CALL":
        try:
            from libs.self_improvement import forecast_calibration as fc
            fc.log_forecast(f"llm_trader:{now.isoformat()}", float(call["probability"]),
                            "discretionary", resolve_by=row["resolve_by"],
                            claim=f"{call['direction']} {call['symbol']}: {call['mechanism'][:120]}")
        except Exception as exc:                            # noqa: BLE001 -- never lose the call
            row["calibration_log_error"] = str(exc)
    return row


def _ask_claude(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse_call(raw: str) -> dict[str, Any] | None:
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
    ap.add_argument("--brief", action="store_true", help="build the brief and stop")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    if args.brief:
        print(json.dumps(brief, indent=2))
        return 0

    raw = _ask_claude(_CALL_BRIEF.format(brief=json.dumps(brief, indent=1)[:6000],
                                         lo=MIN_PROB, hi=MAX_PROB,
                                         mechs=" | ".join(MECHANISMS),
                                         parts=" | ".join(PARTICIPANTS)))
    call = parse_call(raw)
    if call is None:
        state = {"status": "NO-CALL", "why": "model returned no parseable JSON (auth, quota, or "
                                             "a refusal) -- recorded, never treated as a PASS",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        ok, why = validate_call(call)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call,
                     "at": datetime.now(tz=UTC).isoformat()}
        else:
            row = record_call(_ROOT, call)
            state = {"status": call.get("action", "CALL"), "why": why, "call": row,
                     "at": row["at"]}
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"llm trader (R0122): {state['status']} -- {state['why']}")
    return 0                          # a refused call is a working filter, never a build failure


if __name__ == "__main__":
    sys.exit(main())
