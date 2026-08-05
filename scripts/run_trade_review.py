#!/usr/bin/env python3
"""TRADE REVIEW (R0139) -- the discretionary desk's LEARNING LOOP. Binance perps, paper.

PRINCIPAL ORDER (2026-07-31): *"train the brain to maximum to get better and more profitable at
these and max this side as well... giving it just as much priority as the other section too."*

VENUE, stated once and unambiguously: this desk's discretionary sleeve trades BINANCE USD-M
PERPETUALS. The MT5 gold screenshots were the ORIGIN of the idea and a source of one measured data
point about trail width -- they are the principal's own separate account and are never this
sleeve's venue, its price source, or its benchmark.

WHAT "TRAINING" CAN AND CANNOT MEAN HERE, because the distinction decides whether this works. The
model's weights are fixed; nothing here fine-tunes anything. What CAN improve is the desk's
accumulated, evidence-weighted knowledge of WHICH SETUPS ACTUALLY PAY -- and that improves the
sleeve in exactly the way a trading journal improves a human: not by making them smarter, but by
stopping them repeating the mistake they cannot see from inside a single trade.

So this organ does what a professional does every evening:

  1. READS EACH CLOSED TRADE against what was actually claimed at entry -- the thesis, the named
     structure, the falsifier, the chart state -- and against what price then did, bar by bar.
  2. CLASSIFIES THE OUTCOME into causes that can be acted on, which a raw win/loss cannot:
     THESIS-WRONG (the driver did not happen), LEVEL-WRONG (thesis fine, invalidation misplaced),
     TIMING-WRONG (right idea, early/late), NOISE-STOP (stopped by wiggle inside the floor),
     RIGHT-AND-PAID, RIGHT-BUT-TRUNCATED (structure intact at the hold limit), UNLUCKY (correct
     process, adverse draw). A desk that cannot tell RIGHT-AND-UNLUCKY from WRONG will "fix" a
     process that was working, which is the most expensive mistake a journal can prevent.
  3. EXTRACTS ONE DURABLE LESSON with a FALSIFIER attached, and files it in the playbook.

THE PLAYBOOK IS EVIDENCE-WEIGHTED, NOT A PILE OF OPINIONS. This is the part that keeps it from
becoming the usual worthless list of trading platitudes:

  * a lesson enters PROVISIONAL on one observation and carries no authority,
  * it becomes SUPPORTED only after N_SUPPORT independent trades agree with it,
  * it is RETIRED the moment a trade CONTRADICTS it -- and the contradiction is recorded, so the
    same lesson cannot quietly return next week,
  * it goes STALE if the desk stops testing it, because an untested belief is not knowledge,
  * only SUPPORTED lessons reach the trading brief. PROVISIONAL ones are visible to review and to
    the principal, and invisible to the trader, so a single lucky trade cannot rewrite the method.

That ladder is the same evidence standard the rest of the desk applies to alpha (L1.6): nothing is
promoted on one observation, and nothing survives its own falsifier.

    python scripts/run_trade_review.py [--json] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
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

_BOOK = "data/conviction_book.jsonl"
_MARKS = "data/paper_book_pnl.json"
_PLAYBOOK = "data/trading_playbook.json"
_STATE = "data/trade_review.json"

#: 3 independent agreeing trades before a lesson reaches the trading brief. Derived from the same
#: N-gate the calibration fence uses (5 resolved forecasts before shrinkage applies) scaled to the
#: lower bar a piece of ADVICE needs versus a SIZING input: advice that is wrong costs a worse
#: prompt, sizing that is wrong costs money. Below 3 a "pattern" is one trade and two coincidences.
N_SUPPORT = 3
#: A lesson untested for 25 closed trades is STALE -- the desk stopped putting it at risk, so it
#: is no longer knowledge. 25 is one N_SUPPORT cycle at the ~8 trades the sleeve books per day.
STALE_AFTER = 25
#: At most 12 lessons reach the brief. Not a style preference: the brief already carries ~3.4k
#: tokens of chart context against a 21.9k doctrine, and an unbounded playbook would crowd out the
#: structure the trade is actually read from. Ranked by evidence, so growth costs the weakest slot.
MAX_BRIEF_LESSONS = 12

_CAUSES = ("THESIS-WRONG", "LEVEL-WRONG", "TIMING-WRONG", "NOISE-STOP",
           "RIGHT-AND-PAID", "RIGHT-BUT-TRUNCATED", "UNLUCKY")

_BRIEF = """You are reviewing a CLOSED paper trade from this desk's Binance perpetual futures
sleeve. Be the desk's harshest honest reviewer. The goal is not to feel bad about losses or good
about wins -- it is to extract knowledge that changes the NEXT trade.

THE TRADE AS IT WAS CLAIMED AT ENTRY:
{entry}

WHAT PRICE ACTUALLY DID, and how the managed position resolved:
{outcome}

CLASSIFY THE CAUSE as exactly one of: {causes}
  THESIS-WRONG        the driver you named did not happen
  LEVEL-WRONG         thesis was fine, the invalidation was in the wrong place
  TIMING-WRONG        right idea, entered too early or too late
  NOISE-STOP          stopped by ordinary wiggle, not by the thesis failing
  RIGHT-AND-PAID      the thesis happened and the trade was paid for it
  RIGHT-BUT-TRUNCATED the structure was still intact when the hold limit forced an exit
  UNLUCKY             process correct, adverse draw -- USE THIS HONESTLY. A desk that cannot tell
                      RIGHT-AND-UNLUCKY from WRONG will "fix" a process that was working, and that
                      is the most expensive error a review can make. But do not hide behind it.

THEN EXTRACT ONE LESSON, and it must survive these tests or it is worthless:
  * SPECIFIC to a recognisable situation ("on PAXG in a contracting-vol regime, a level with fewer
    than 3 touches does not hold a 30h horizon"), never a platitude ("cut losses, manage risk").
  * ACTIONABLE at the moment of the next trade -- it changes a level, a size, a horizon, or a pass.
  * FALSIFIABLE: state the observation that would prove it wrong.

OUTPUT EXACTLY ONE JSON OBJECT:
{{"cause": "one of the causes above",
  "what_happened": "2-3 sentences, concrete, referencing the actual prices",
  "lesson": "the specific actionable rule",
  "lesson_falsifier": "the observation that would prove this lesson wrong",
  "applies_when": "the recognisable situation this lesson is scoped to",
  "confidence": 0.6,
  "process_was_sound": true}}

If the trade contains no transferable lesson, say so: lesson "NONE -- single-instance noise, no
transferable rule" with process_was_sound set honestly. A review that manufactures a lesson from
every trade fills the playbook with superstition, and superstition in the brief is worse than an
empty playbook."""


def load_playbook(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / _PLAYBOOK).read_text("utf-8"))
    except (OSError, ValueError):
        return {"lessons": [], "reviewed_keys": []}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


def file_lesson(pb: dict[str, Any], lesson: dict[str, Any], trade_key: str,
                n_closed: int) -> dict[str, Any]:
    """Add or update a lesson on the evidence ladder. Contradiction RETIRES, and stays recorded."""
    text = str(lesson.get("lesson", "")).strip()
    if not text or text.upper().startswith("NONE"):
        return {"action": "no-lesson", "why": "review found no transferable rule"}
    key = _norm(text)[:120]
    for lv in pb["lessons"]:
        # TWO RECORD SHAPES LIVE HERE, and assuming one of them crashed the organ every day.
        # Lessons written by THIS function carry {key, text}; lessons IMPORTED from elsewhere
        # carry {lesson, origin, imported_from} and neither of the two fields this loop indexed.
        # All four records in data/trading_playbook.json are the imported shape, so `lv["key"]`
        # raised KeyError on the first iteration -- the review died before it could file anything,
        # which is why the playbook has sat at exactly those 4 imported lessons and never grew.
        # Read both shapes; keep WRITING one.
        lv_text = str(lv.get("text") or lv.get("lesson") or "")
        lv_key = str(lv.get("key") or _norm(lv_text)[:120])
        if lv_key == key or _norm(lv_text)[:60] == _norm(text)[:60]:
            if lesson.get("contradicts"):
                lv["status"] = "RETIRED"
                lv.setdefault("contradicted_by", []).append(trade_key)
                return {"action": "retired", "lesson": lv_text}
            lv["support"] = int(lv.get("support", 0)) + 1
            lv.setdefault("trades", []).append(trade_key)
            lv["last_seen_at_trade"] = n_closed
            if lv.get("status") == "PROVISIONAL" and lv["support"] >= N_SUPPORT:
                lv["status"] = "SUPPORTED"
                return {"action": "promoted", "lesson": lv_text, "support": lv["support"]}
            return {"action": "reinforced", "lesson": lv_text, "support": lv["support"]}
    pb["lessons"].append({
        "key": key, "text": text, "falsifier": lesson.get("lesson_falsifier", ""),
        "applies_when": lesson.get("applies_when", ""), "cause": lesson.get("cause"),
        "status": "PROVISIONAL", "support": 1, "trades": [trade_key],
        "first_seen_at_trade": n_closed, "last_seen_at_trade": n_closed,
    })
    return {"action": "new", "lesson": text, "support": 1}


def age_playbook(pb: dict[str, Any], n_closed: int) -> list[str]:
    """An untested belief is not knowledge. Mark long-unconfirmed lessons STALE."""
    staled = []
    for lv in pb["lessons"]:
        if lv["status"] == "SUPPORTED" and n_closed - lv["last_seen_at_trade"] > STALE_AFTER:
            lv["status"] = "STALE"
            staled.append(lv["text"])
    return staled


def brief_lessons(pb: dict[str, Any]) -> list[dict[str, Any]]:
    """ONLY SUPPORTED lessons reach the trader -- one lucky trade must not rewrite the method."""
    live = [lv for lv in pb["lessons"] if lv["status"] == "SUPPORTED"]
    live.sort(key=lambda lv: (-lv["support"], -lv["last_seen_at_trade"]))
    return [{"lesson": lv["text"], "applies_when": lv["applies_when"],
             "evidence_trades": lv["support"]} for lv in live[:MAX_BRIEF_LESSONS]]


def closed_trades(root: Path, *, limit: int = 5) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(book row, mark) pairs for trades the resolver has closed and review has not yet seen."""
    try:
        marks = {m["key"]: m for m in json.loads((root / _MARKS).read_text("utf-8"))["marks"]
                 if m.get("closed") and m.get("key")}
    except (OSError, ValueError, KeyError):
        return []
    seen = set(load_playbook(root).get("reviewed_keys") or [])
    out = []
    try:
        lines = (root / _BOOK).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for ln in reversed(lines):
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        k = row.get("at")
        if k in marks and k not in seen:
            out.append((row, marks[k]))
        if len(out) >= limit:
            break
    return out


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


def review_one(row: dict[str, Any], mark: dict[str, Any], *, ask=_ask) -> dict[str, Any] | None:
    entry = {k: row.get(k) for k in ("symbol", "direction", "probability", "entry_ref",
                                     "invalidation", "structure", "expected_move_pct",
                                     "horizon_hours", "driver", "falsifier", "stop_pct")}
    entry["sizing"] = {k: (row.get("sizing") or {}).get(k) for k in ("leverage", "risk_fraction")}
    entry["noise_floor_pct"] = (row.get("noise") or {}).get("floor_pct")
    out = {k: mark.get(k) for k in ("outcome", "exit_price", "realised_R", "gross_return",
                                    "equity_return", "stage_reached", "max_stage",
                                    "units_at_exit", "hold_hours", "buy_and_hold")}
    res = parse(ask(_BRIEF.format(entry=json.dumps(entry, indent=1),
                                  outcome=json.dumps(out, indent=1),
                                  causes=", ".join(_CAUSES))))
    if res is None or res.get("cause") not in _CAUSES:
        return None
    return res


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pb = load_playbook(_ROOT)
    pending = closed_trades(_ROOT, limit=args.limit)
    if not pending:
        state = {"status": "NOTHING-TO-REVIEW", "at": datetime.now(tz=UTC).isoformat(),
                 "why": "no closed trades the review has not already seen -- this is UNMEASURED "
                        "learning, not a healthy loop, until the book actually closes trades",
                 "playbook_supported": len(brief_lessons(pb))}
        (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
        print(json.dumps(state, indent=2) if args.json else
              f"trade review (R0139): {state['status']} -- {state['why'][:90]}")
        return 0

    n_closed = len(pb.get("reviewed_keys") or []) + len(pending)
    results = []
    for row, mark in pending:
        res = review_one(row, mark)
        key = row.get("at")
        if res is None:
            results.append({"trade": key, "status": "NO-REVIEW",
                            "why": "no parseable review (auth/quota/refusal)"})
            continue
        filed = file_lesson(pb, res, key, n_closed)
        pb.setdefault("reviewed_keys", []).append(key)
        results.append({"trade": key, "cause": res["cause"], "filed": filed,
                        "process_was_sound": res.get("process_was_sound")})
    staled = age_playbook(pb, n_closed)
    pb["updated"] = datetime.now(tz=UTC).isoformat()
    (_ROOT / _PLAYBOOK).write_text(json.dumps(pb, indent=2), "utf-8")

    causes = {c: sum(1 for r in results if r.get("cause") == c) for c in _CAUSES}
    state = {
        "status": "REVIEWED", "at": pb["updated"], "n_reviewed": len(results),
        "causes": {k: v for k, v in causes.items() if v},
        "staled": staled,
        "playbook": {"total": len(pb["lessons"]),
                     "supported": sum(1 for lv in pb["lessons"] if lv["status"] == "SUPPORTED"),
                     "provisional": sum(1 for lv in pb["lessons"]
                                        if lv["status"] == "PROVISIONAL"),
                     "retired": sum(1 for lv in pb["lessons"] if lv["status"] == "RETIRED")},
        "results": results,
    }
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"trade review (R0139): reviewed {len(results)}; playbook "
          f"{state['playbook']['supported']} supported / {state['playbook']['total']} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
