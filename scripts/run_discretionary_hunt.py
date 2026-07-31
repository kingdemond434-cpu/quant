#!/usr/bin/env python3
"""DISCRETIONARY EDGE HUNT (R0152) -- find the NEXT discretionary edge, not just tune the current one.

PRINCIPAL ORDER (2026-08-01): *"a whole system dedicated to this and improving the brain and
finding MULTIPLE discretionary edges this way, trading like a compounding human trader with the
philosophy of that screenshot."*

THE GAP THIS FILLS, and it is the one the rest of the section did not cover. The discretionary desk
has an optimiser (R0151 pushes the hit rate of the sleeve that exists) and a learner (R0139 extracts
lessons from closed trades). Both improve ONE edge. Neither ever asks whether there is a SECOND
one -- and the allocator's own arithmetic says a second INDEPENDENT edge is worth more than a large
improvement to the first, because growth multiplies across uncorrelated bets and merely adds within
one. A desk with a single discretionary hypothesis is one regime change away from having none.

WHAT A DISCRETIONARY EDGE IS HERE, stated so the hunt does not drift into indicator soup. It is a
situation a skilled human trader RECOGNISES and can act on, that has a MECHANISM (someone is forced
to trade, or is systematically late, or is priced off the wrong thing), and that fails a stated
observation. "RSI below 30" is not one -- it names no participant and no compulsion. "The stop
cluster above a triple-touched high gets swept before the real move, because resting stops are the
only guaranteed liquidity at that level" is one: it names who is forced and why.

THE FORCED-PARTICIPANT TEST is inherited from the event sleeve and is the single strongest filter
this desk owns. Every candidate must answer: WHO has to trade against you, and WHY can they not
wait? A hypothesis with no forced counterparty is a pattern, and the desk's record on patterns is
420 tested, 0 survived.

ANTI-REPETITION. Every candidate is registered permanently. A hunt that regenerates the same six
ideas every night looks productive and produces nothing, which is the failure mode of every
brainstorming loop ever built. Previously-seen candidates are shown to the model as ALREADY HUNTED
and it is told to go elsewhere -- and repeats are counted, because a rising repeat rate means the
search space is exhausted and the lenses need re-aiming rather than the cadence raising.

WHAT IT DOES NOT DO: promote anything. A survivor earns a pre-registered forward clock and a place
in the sleeve allocator's independence test, nothing more (L1.6). The allocator then decides
whether it is a genuine second edge or the first one wearing a new name -- which is the question
that decides whether "multiple edges" compounds or just costs more fees.

    python scripts/run_discretionary_hunt.py [--json] [--n 4]
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

_REGISTRY = "data/discretionary_edges.json"
_STATE = "data/discretionary_hunt.json"

#: 4 candidates per run. Enough that a weak lens still yields one usable idea, few enough that each
#: gets real reasoning rather than a list. Raising it trades depth for length, which is the wrong
#: direction when the binding constraint is candidate QUALITY and not candidate count.
N_CANDIDATES = 4

#: A repeat rate above this means the search space under the current lenses is exhausted: the
#: honest response is to re-aim the lenses, NOT to raise the cadence, which would just regenerate
#: the same ideas faster. 0.5 = half the batch already known.
EXHAUSTION_REPEAT_RATE = 0.5

#: LENSES -- each is a different WAY a human trader finds an edge, rotated so the hunt does not
#: circle one region forever. Deliberately about market participants and compulsion, not about
#: indicators.
_LENSES: tuple[tuple[str, str], ...] = (
    ("FORCED LIQUIDITY",
     "who is FORCED to transact at a price they would not choose -- liquidations, margin calls, "
     "index rebalances, expiries, redemption windows, stop clusters"),
    ("STRUCTURAL LATENESS",
     "who is systematically LATE -- mandates that can only act after a print, desks that hedge on "
     "a schedule, funds that cannot trade until a threshold is breached"),
    ("WRONG-PRICE ANCHOR",
     "what is priced off the WRONG reference -- a stale index, a lagging proxy, a correlation "
     "everyone assumes still holds, a funding rate anchored to a different venue"),
    ("SESSION AND CALENDAR",
     "what changes at a KNOWN TIME -- session opens and closes, funding stamps, settlement, "
     "weekend gaps, holiday liquidity, the hours no desk is staffed"),
    ("FAILED EXPECTATION",
     "where a widely-expected move FAILS -- failed breakouts, unbought dips, news that does not "
     "move price. The failure itself is information about positioning"),
    ("CROSS-ASSET DIVERGENCE",
     "when two things that normally move together STOP -- gold vs real yields, BTC vs risk, a "
     "perp vs its own spot, one venue vs another"),
)


def load_registry(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / _REGISTRY).read_text("utf-8"))
    except (OSError, ValueError):
        return {"edges": []}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()[:90]


def lens_for(stamp: str, slot: int = 0) -> tuple[str, str]:
    """Date-ordinal rotation so coverage is provable rather than random."""
    try:
        ordinal = datetime.strptime(stamp, "%Y%m%d").date().toordinal()
    except ValueError:
        ordinal = 0
    return _LENSES[(ordinal + slot) % len(_LENSES)]


_BRIEF = """You are hunting for a NEW DISCRETIONARY TRADING EDGE on Binance USD-M perpetuals -- the
kind a skilled human trader recognises on a chart and in the flow, not a statistical pattern.

TONIGHT'S LENS -- {lens_name}: {lens_body}

WHAT COUNTS AS AN EDGE HERE, and most proposals fail this:
  * it names a FORCED PARTICIPANT. Who has to trade against you, and why can they not wait?
    Liquidation engines, margin calls, index rebalances, mandates that must act after a print.
    "RSI below 30" names nobody and is not an edge. If you cannot name who is compelled, say so
    and discard the candidate rather than dressing it up.
  * a HUMAN could recognise it in real time from price, structure and the desk's feeds. If it
    needs a fitted model it belongs to the systematic side, not here.
  * it has a FALSIFIER -- the specific observation that would prove it is not real.

ALREADY HUNTED -- do NOT propose these again, go somewhere else entirely:
{seen}

THE DESK'S OWN LEARNED LESSONS, from its closed trades (weigh these, and say if one is wrong):
{playbook}

OUTPUT EXACTLY ONE JSON OBJECT:
{{"candidates": [
  {{"name": "short handle",
    "situation": "what a human sees, concretely, in one or two sentences",
    "forced_participant": "WHO must trade against you and why they cannot wait",
    "mechanism": "why this produces a price move that is not already arbitraged",
    "falsifier": "the observation that proves it is not real",
    "how_measured": "what data on this desk would test it -- charts, funding, liquidations, "
                    "announcements, copy-flow, cross-venue",
    "why_not_arbitraged": "why this survives being obvious",
    "confidence": 0.4}}
]}}

{n} candidates. Fewer good ones beats more weak ones -- a candidate with no forced participant
should not be in the list at all. If this lens is genuinely exhausted, return fewer and say so in
a candidate named "LENS-EXHAUSTED"."""


def _ask(prompt: str, timeout: int = 900) -> str:
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


def validate(c: dict[str, Any]) -> tuple[bool, str]:
    """The forced-participant test, and the falsifier. Both or it is a pattern."""
    for f in ("name", "situation", "forced_participant", "mechanism", "falsifier"):
        if not str(c.get(f, "")).strip():
            return False, f"REFUSED: missing {f}"
    fp = str(c["forced_participant"]).lower()
    if len(fp) < 25 or any(w in fp for w in ("traders", "the market", "everyone", "participants")):
        return False, ("REFUSED: forced participant is generic -- 'traders' and 'the market' name "
                       "nobody. A hypothesis with no identifiable compelled counterparty is a "
                       "pattern, and this desk is 420-tested/0-survived on patterns")
    if len(str(c["falsifier"])) < 20:
        return False, "REFUSED: falsifier too thin to act on"
    if len(str(c["mechanism"])) < 40:
        return False, "REFUSED: mechanism too thin -- state why the move is not already arbitraged"
    return True, "accepted"


def register(root: Path, cands: list[dict[str, Any]], lens: str,
             ) -> dict[str, Any]:
    reg = load_registry(root)
    seen = {e["key"] for e in reg["edges"]}
    now = datetime.now(tz=UTC).isoformat()
    new, repeat, refused = [], [], []
    for c in cands:
        ok, why = validate(c)
        if not ok:
            refused.append({"name": c.get("name"), "why": why})
            continue
        k = _key(c.get("name", "") + " " + c.get("situation", ""))
        if k in seen:
            repeat.append(c.get("name"))
            continue
        seen.add(k)
        reg["edges"].append({**c, "key": k, "lens": lens, "found": now,
                             "status": "CANDIDATE",
                             "authority": "forward clock only -- never capital (L1.6)"})
        new.append(c.get("name"))
    reg["updated"] = now
    (root / _REGISTRY).parent.mkdir(parents=True, exist_ok=True)
    (root / _REGISTRY).write_text(json.dumps(reg, indent=2), "utf-8")
    total = len(new) + len(repeat)
    return {"new": new, "repeats": repeat, "refused": refused,
            "repeat_rate": round(len(repeat) / total, 3) if total else None,
            "registry_size": len(reg["edges"])}


def build_report(root: Path | None = None, *, n: int = N_CANDIDATES, ask=_ask,
                 stamp: str | None = None) -> dict[str, Any]:
    root = root or _ROOT
    stamp = stamp or datetime.now(tz=UTC).strftime("%Y%m%d")
    lens_name, lens_body = lens_for(stamp)
    reg = load_registry(root)
    seen_txt = "\n".join(f"  - {e.get('name')}: {str(e.get('situation'))[:90]}"
                         for e in reg["edges"][-40:]) or "  (none yet)"
    try:
        from scripts.run_conviction_trader import _playbook_brief
        pb = _playbook_brief(root)
    except Exception as exc:
        pb = f"(playbook unavailable: {type(exc).__name__})"
    raw = ask(_BRIEF.format(lens_name=lens_name, lens_body=lens_body, seen=seen_txt,
                            playbook=pb[:1500], n=n))
    obj = parse(raw)
    if not obj or not isinstance(obj.get("candidates"), list):
        return {"generated": datetime.now(tz=UTC).isoformat(), "lens": lens_name,
                "status": "NO-CANDIDATES",
                "why": "no parseable JSON (auth/quota/refusal) -- this is UNMEASURED hunting, "
                       "not an empty search space"}
    res = register(root, obj["candidates"], lens_name)
    rr = res["repeat_rate"]
    exhausted = rr is not None and rr >= EXHAUSTION_REPEAT_RATE
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6/L1.31 -- a second INDEPENDENT edge is worth more than a large improvement to "
               "the first, because growth multiplies across uncorrelated bets and merely adds "
               "within one. A desk with a single discretionary hypothesis is one regime change "
               "away from having none.",
        "lens": lens_name, "status": "HUNTED",
        **res,
        "exhaustion": ("LENS-EXHAUSTED -- re-aim the lenses, do NOT raise the cadence: a higher "
                       "cadence on an exhausted space regenerates the same ideas faster"
                       if exhausted else "search space still yielding"),
        "authority": "candidates earn a pre-registered forward clock and a place in the sleeve "
                     "allocator's independence test. They earn no capital (L1.6), and the "
                     "allocator decides whether a survivor is a real second edge or the first one "
                     "wearing a new name.",
        "detail": (f"lens {lens_name}: {len(res['new'])} new, {len(res['repeats'])} repeats, "
                   f"{len(res['refused'])} refused; registry {res['registry_size']}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_CANDIDATES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT, n=args.n)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"discretionary hunt (R0152): {rep.get('detail') or rep.get('why')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
