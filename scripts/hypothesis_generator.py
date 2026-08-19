"""HYPOTHESIS GENERATOR -- external LLMs proposing MECHANISMS, with the graveyard in hand.

*** UNTESTED (OpenRouter 402). The brain must run it once and check output before relying on it. ***

WHY THIS ROLE DID NOT EXIST: the desk had an external LLM for SOURCE discovery (breadth_expander)
but nothing for HYPOTHESIS generation. The principal supplied a ~50-hypothesis slate from ChatGPT
that was genuinely well-framed -- and three of the first four were ALREADY REFUTED on this desk,
while the three novel escalations tested 0/3. That is not a failure of the model; it is a failure
of CONTEXT: a generator that cannot see the graveyard will keep re-proposing the dead.

SO THIS ROLE INVERTS THE BREADTH EXPANDER'S DESIGN, deliberately:
  breadth_expander     COLD, no desk context   -> avoids anchoring, finds sources we cannot imagine
  hypothesis_generator FED the graveyard       -> avoids re-proposing what is already refuted
Same principle (maximise NEW information), opposite implementation, because the failure modes are
opposite. Anchoring is the enemy of source search; ignorance is the enemy of hypothesis search.

SEATS: THE WHOLE ROSTER, priority-ordered. The principal observes GPT is strong at idea
generation; the desk's own measurement says gpt-5.6-terra-pro produced 0 parseable rows on 5 of 6
breadth lenses while nemotron/grok produced 18 each. Both can be true -- different task. So GPT
LEADS the priority order (its claimed strength, generative framing), and the YIELD TABLE decides
who keeps a seat. No seat by reputation.

But leading is not the same as being the only one asked. This ran THREE seats out of thirteen
until 2026-07-31: google, qwen, z-ai, moonshotai (Kimi), nvidia and the lab siblings never
generated a single hypothesis, on the desk's own #2 supreme objective. Cognitive diversity is the
entire reason the roster is 13 distinct labs rather than 3 copies of one, and generation is
exactly the task where uncorrelated training data pays. Every funded seat now generates.

OUTPUT CONTRACT forces falsifiability: every idea must name a MECHANISM, a FREE data source, a
concrete TEST, and a KILL CONDITION. "Interesting area" is rejected by construction.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.doctrine.constitution import (  # noqa: E402
    OBJECTIVE_PREAMBLE,
    RESIDUAL_MANDATE,
    RESIDUAL_PROTOCOL,
)
from libs.llm.effort import reasoning_payload  # noqa: E402
from libs.llm.push import GENERATION_LADDER, push_rounds  # noqa: E402
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
GRAVE = ROOT / "docs/graveyard.md"
MECH = ROOT / "docs/research/MECHANISM_GRAPH.md"
OUT = ROOT / "data/hypothesis_queue.jsonl"
CTX = ssl.create_default_context()

#: PRIORITY ORDER, not the seat list. These three are first because they are the lineages with
#: measured generation quality on this desk; everything else in the roster follows. The literal
#: model IDs are resolved against the LIVE roster by seats.resolve, so an upgraded-away model is
#: substituted same-lab-first rather than silently lost -- this list can go stale without
#: breaking anything, which is the point.
SEAT_PRIORITY = ["openai/gpt-5.6-terra-pro", "x-ai/grok-4.3", "deepseek/deepseek-v4-pro"]

#: HOW MANY SEATS GENERATE. `None` = every seat on the roster.
#:
#: WAS 3, HARDCODED, OUT OF 13. Ten funded seats -- google, qwen, z-ai, moonshotai (Kimi),
#: nvidia and the siblings -- never generated a single hypothesis, on the desk's own #2 supreme
#: objective. That is not a small throttle: cognitive diversity is the entire reason the roster
#: is 13 distinct labs rather than 3 instances of one, and generation is precisely the task where
#: uncorrelated training data pays. Using 3 of 13 for generation while paying for 13 is the
#: expensive way to be narrow.
#:
#: COST, STATED HONESTLY. 5 lenses x 13 seats = 65 calls at ~$0.22 = ~$14/run, against the
#: $100-150/mo envelope the panel budget already works to. At a weekly cadence that is ~$60/mo
#: for the desk's primary output. The old comment costed the 3-seat sweep at ~$3.30/run against
#: a "$10-30/mo" figure; the envelope has since been raised and this is the ROI the principal
#: explicitly funded the roster for. Set an integer here to cap it if that changes.
GEN_SEATS: int | None = None

LENSES = [
    ("MECHANISM TRANSITION", "What causes a market to move BETWEEN states (calm->stressed, "
     "trending->ranging, liquid->fragile)? Static-state signals have failed repeatedly here; "
     "transitions have not been tested."),
    ("PARTICIPANT CONSTRAINT", "Which market participant is FORCED to act against their own "
     "interest by a rule, mandate, margin call, redemption or licence? Forced flow is the most "
     "reliable edge source because the counterparty has no choice."),
    ("STRUCTURAL SEGMENTATION", "Where does a HARD barrier (licence, capital control, settlement "
     "delay, collateral incompatibility) prevent two prices for the same risk from converging? "
     "Soft frictions arbitrage away; hard ones persist."),
    ("MEASUREMENT ADVANTAGE", "What is publicly observable but expensive or awkward to MEASURE, "
     "such that most participants use a crude proxy instead of the real quantity?"),
    ("SECOND ORDER", "Take a signal that is known and crowded. What is its derivative, its "
     "dispersion, its persistence, or its failure mode -- and is THAT untested?"),
]

SYSTEM = (
    # THE CONSTITUTION LEADS. A generator that does not know the objective
    # optimises for what a hypothesis LOOKS like -- novelty, cleverness, a tidy mechanism --
    # rather than for expected shift in E[log W]. It also has to be told that a hypothesis
    # whose most likely outcome is a DISPROOF is a good hypothesis, or it will only ever
    # propose things it expects to confirm, which is the lowest-information batch available.
    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
    "You are a quantitative researcher generating TESTABLE hypotheses for a trading desk whose "
    "universe is the full MT5/Fusion market -- FX majors/crosses/exotics, gold and metals, equity "
    "indices, energy, soft commodities and share CFDs; crypto only as information for an MT5 move.\n"
    "HARD RULES:\n"
    "1. Every hypothesis must name a MECHANISM -- a reason the edge exists that survives the "
    "question 'why has nobody arbitraged this?'. No mechanism = rejected.\n"
    "2. The data must be FREE and PUBLIC, and you must name the actual endpoint or dataset.\n"
    "3. State a concrete FALSIFIABLE TEST and an explicit KILL CONDITION.\n"
    "4. Do NOT propose anything in the REFUTED list you are given. Those are already dead here.\n"
    "5. Prefer SPREADS and FORCED FLOWS over forecasts. On this desk every forecast-style "
    "hypothesis has died and every surviving candidate has been a spread with a hard constraint.\n"
    "6. Be specific enough that someone could code the test tomorrow. Vague themes are useless.\n"
    "Output ONE hypothesis per line:\n"
    "NAME | MECHANISM (<=25 words) | DATA SOURCE | TEST | KILL CONDITION"
)


def _ask(base, key, model, messages, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.95,
                       # DEPTH IS MEASURED, NOT ASSUMED. "high" is the middle rung of a ladder
                       # whose top differs per model and per month -- a literal here is
                       # capability left unused on a flagship the desk pays for.
                       "reasoning": reasoning_payload(model),
                       "messages": messages}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def _ask_pushed(base, key, model, system, user):
    """Generation is the desk's #2 supreme objective and it was taking ONE answer per seat per
    lens. The graveyard, mechanism map and lens prompt are already paid for; the ladder harvests
    the rest of what the seat has against that same context, and stops when novelty dies rather
    than at an arbitrary count."""
    r = push_rounds(lambda msgs: _ask(base, key, model, msgs), system, user,
                    ladder=GENERATION_LADDER)
    return r.text, f"{r.rounds} push round(s); {r.stop_reason}"


def refuted() -> tuple[str, set[str]]:
    """The graveyard, both as prose for the prompt and as tokens for dedup."""
    if not GRAVE.exists():
        return "", set()
    names, toks = [], set()
    for ln in GRAVE.read_text("utf-8").splitlines():
        if ln.startswith("|") and not set(ln) <= set("|- "):
            first = ln.strip("|").split("|")[0].strip()
            if first and first.lower() not in ("name", "signal", "strategy"):
                names.append(first[:80])
                toks.update(w for w in re.split(r"[^a-z0-9]+", first.lower()) if len(w) > 4)
    return "\n".join(f"- {n}" for n in names[:60]), toks


def main() -> None:
    if not KEYS.exists():
        print("no panel keys")
        return
    # Live-roster resolution: an upgraded-away seat is substituted (same lab first), not lost.
    #
    # THE PREFERRED LIST IS THE WHOLE ROSTER, priority-ordered. Passing only SEAT_PRIORITY here
    # capped generation at 3 seats no matter how many were funded, because resolve_ids walks the
    # preferred list and only tops up to an explicit `n`. So the roster could grow to 24 and
    # generation would still ask three models. Building the preferred list from the live roster
    # means every seat the desk pays for does the desk's #2 supreme objective.
    # DISTINCT LABS STAYS ON, and that is a choice worth defending rather than a default. It
    # collapses the lab siblings (a second openai, a second google), so a 13-seat roster yields
    # ~8 generating seats instead of 13. More volume was available and is deliberately declined:
    # the desk's measured problem is candidate QUALITY, not count -- 420 candidates produced zero
    # survivors -- and two models from one lab share training data, so the second mostly adds
    # correlated ideas. That is precisely the mode collapse batch_diversity() exists to detect:
    # throughput rising while information does not. Set distinct_labs=False only if the yield
    # table ever shows siblings producing genuinely different mechanisms.
    _roster = [str(p["model"]) for p in seats.load_roster()]
    _preferred = SEAT_PRIORITY + [m for m in _roster if m not in SEAT_PRIORITY]
    provs = {p["model"]: p for p in seats.resolve(_preferred, n=GEN_SEATS,
                                                  distinct_labs=True, role="hypothesis_gen")}
    seated = list(provs)
    dead_txt, dead_tok = refuted()
    mech = MECH.read_text("utf-8")[:3000] if MECH.exists() else ""

    # ALL LENSES EVERY RUN (was: LENSES[day % len(LENSES)] -- one lens per day).
    #
    # The one-lens rotation put a 5x throttle on the desk's PRIMARY output and took five days to
    # sweep the hypothesis space once. It also contradicted its own sibling: breadth_expander
    # runs every lens daily and states exactly why --
    #
    #     "ALL LENSES DAILY -- one prompt reshuffled would converge; six orthogonal framings
    #      cannot."                                        -- breadth_expander.py
    #
    # That argument is about ORTHOGONALITY OF FRAMING, not about which organ is asking, so it
    # applies here identically. Rotating lenses does not merely slow generation down: on any
    # given day the desk can only see the space through one framing, so a hypothesis that needs
    # PARTICIPANT CONSTRAINT thinking is invisible on a SECOND ORDER day and is never generated
    # at all unless the idea survives four days of nobody looking for it.
    #
    # Cost: len(LENSES) x len(seats) calls (5 x 3 = 15) at ~$0.22 = ~$3.30/run against a stated
    # $10-30/mo envelope. Generation is objective #2 of two co-equal supreme objectives; this is
    # the cheapest available purchase of discovery rate on the desk.
    print(f"=== HYPOTHESIS GENERATOR | FULL SWEEP: {len(LENSES)} lenses x {len(seated)} seats ===")
    print("    *** UNTESTED SCRIPT -- verify output before trusting it ***")
    print(f"    graveyard supplied: {len(dead_tok)} refuted tokens (prevents re-proposing dead)\n")

    def _user_for(lens_name: str, lens_txt: str) -> str:
        return (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                f"ALREADY REFUTED ON THIS DESK (do not propose these or close variants):\n"
                f"{dead_txt}\n\n"
                f"MECHANISM MAP (what is already observed):\n{mech}\n\n"
                "Give 10-15 hypotheses through THIS lens that are NOT in the refuted list.")

    jobs = [(ln, lt, seat) for ln, lt in LENSES for seat in seated]

    def run(job):
        lens_name, lens_txt, seat = job
        p = provs.get(seat)
        if not p:
            return lens_name, seat, "", "not in roster"
        try:
            txt, stop = _ask_pushed(p["base_url"], p["key"], seat, SYSTEM,
                                    _user_for(lens_name, lens_txt))
            print(f"  {lens_name[:22]:<22} {seat.split('/')[-1]:<22} {stop}")
            return (lens_name, seat, txt, None)
        except Exception as e:
            return lens_name, seat, "", f"{type(e).__name__} {getattr(e, 'code', '')}"

    # Fanned out because the sweep is now len(LENSES)x bigger and must still fit its cadence
    # window -- the same reason breadth_expander parallelises its full sweep.
    with ThreadPoolExecutor(max_workers=6) as ex:
        answers = list(ex.map(run, jobs))

    rows = []
    for lens_name, seat, txt, err in answers:
        if err:
            print(f"  {lens_name[:22]:<22} {seat.split('/')[-1]:<22} FAILED ({err})")
            continue
        kept = dup = 0
        for ln in txt.splitlines():
            if ln.count("|") < 4:
                continue
            parts = [x.strip() for x in ln.split("|")]
            name = parts[0].lstrip("-*0123456789. ")
            if not name or len(name) > 90:
                continue
            words = {w for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 4}
            if words & dead_tok:
                dup += 1
                continue
            rows.append({"date": datetime.now(tz=UTC).date().isoformat(), "lens": lens_name,
                         "seat": seat, "name": name, "mechanism": parts[1][:200],
                         "data": parts[2][:140], "test": parts[3][:200],
                         "kill": parts[4][:160] if len(parts) > 4 else ""})
            kept += 1
        print(f"  {lens_name[:22]:<22} {seat.split('/')[-1]:<22} "
              f"+{kept} new, {dup} rejected as already-refuted")

    if rows:
        with OUT.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    print(f"\n  {len(rows)} hypotheses queued")
    for r in rows[:10]:
        print(f"    {r['name'][:54]:<54} [{r['seat'].split('/')[-1][:14]}]")
        print(f"       mech: {r['mechanism'][:96]}")
    print("\n  These enter the EV gate and Stage-A screening like any other candidate.")
    print("  ZERO promotion authority. Per-seat yield is tracked -- a seat proposing only")
    print("  hypotheses that die loses its slot, GPT included. No seat by reputation.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
