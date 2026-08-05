#!/usr/bin/env python3
"""SURVIVOR BOTTLENECK PANEL -- every seat argues about why nothing has ever survived.

WHAT THIS IS FOR. The desk has produced zero survivors in its life and has a MEASURED reason:
52 of 350 recorded negatives (14.9%) were powered enough to mean anything. That is a finding
Claude reached from the artifacts, and a finding from one reasoner is exactly the thing most worth
attacking. This organ puts the same numbers in front of every reachable seat -- the GPT/CRO brain
and every OpenRouter family -- and makes them argue about it.

GPT IS AN ADDITION, NEVER THE BRAIN. Nothing here defers to a seat, adopts its plan, or executes
its text. Every response is DATA: parsed into structured proposals, fenced, ranked by cross-seat
agreement, and handed to a person. A panel that could act on its own output would be a way for a
model's confident prose to move a desk, which is the failure this design exists to prevent.

TWO ROUNDS, BECAUSE ONE ROUND IS NOT A PANEL. Round 1 each seat answers alone. Round 2 each seat
reads the others' answers ANONYMISED and must refute at least one specific claim, name the single
binding constraint, and say what everyone missed. Agreement that survives forced contradiction is
worth something; agreement between parallel monologues is a shared prior.

FAMILY DIVERSITY IS THE POINT. Two seats from one vendor share training data and therefore share
blind spots -- the report says how many distinct FAMILIES answered, because "five seats agreed" is
a much weaker claim when four of them are the same model at different sizes.

EVERY PROPOSAL IS FENCED. A model asked "how do we get survivors" has one overwhelmingly easy
answer available -- lower the bar -- and it will find it. Anything that loosens a gate, raises
size, touches the deadman switch, selects on results post hoc, or removes a validation stage is
REFUSED and recorded with the reason, because a seat proposing it is information about the seat.

SPEND IS CHECKED BEFORE THE CALL, and a missing key produces a BLOCKED artifact naming what to
export -- never a silent empty run that reads as "the panel had no opinions".

    python scripts/run_survivor_panel.py [--seats N] [--no-round-two] [--json]
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

from libs.ops import llm_seat  # noqa: E402
from libs.research.survivor_panel import (  # noqa: E402
    Proposal,
    build_dossier,
    cross_examination_prompt,
    parse_proposals,
    rank_proposals,
    round_one_prompt,
)

OUT = "reports/survivor_panel.json"
LEDGER = "data/survivor_panel.jsonl"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _family(model: str) -> str:
    """Vendor family from a model id. Two seats from one family are ONE opinion for diversity."""
    m = str(model).lower()
    for fam in ("anthropic", "claude", "openai", "gpt", "o1", "o3", "deepseek", "qwen", "kimi",
                "moonshot", "llama", "meta", "mistral", "gemini", "google", "grok", "xai",
                "nemotron", "nvidia", "glm", "zhipu", "minimax", "cohere"):
        if fam in m:
            return {"claude": "anthropic", "gpt": "openai", "o1": "openai", "o3": "openai",
                    "moonshot": "kimi", "meta": "llama", "google": "gemini", "xai": "grok",
                    "nvidia": "nemotron", "zhipu": "glm"}.get(fam, fam)
    return m.split("/")[0] if "/" in m else "unknown"


def run(root: Path | None = None, *, max_seats: int = 6,
        round_two: bool = True) -> dict[str, Any]:
    base = root or _ROOT
    dossier = build_dossier(base)

    available = llm_seat.seats()
    if not available:
        return {"generated_utc": _now(), "status": "BLOCKED",
                "blocker": ("no LLM seat reachable -- export OPENROUTER_API_KEY (one key reaches "
                            "every family, which is what this panel needs) or OPENAI_API_KEY, or "
                            "write data/secrets/llm_panel.json"),
                "consequence": ("the desk's own root-cause finding stands UNCHALLENGED. It was "
                                "produced by one reasoner and nothing has attacked it, which is "
                                "the state this organ exists to end -- recorded rather than left "
                                "as an empty report that reads like agreement"),
                "dossier": dossier, "seats": [], "proposals": []}

    spent, cap = llm_seat.month_spend_usd(), llm_seat.monthly_cap_usd()
    if spent >= cap:
        return {"generated_utc": _now(), "status": "BLOCKED",
                "blocker": f"monthly LLM cap reached: ${spent:.2f} of ${cap:.2f}",
                "consequence": "no seat was called; nothing was spent and nothing was learned",
                "dossier": dossier, "seats": [], "proposals": []}

    sys_1, user_1 = round_one_prompt(dossier)
    round1: list[dict[str, Any]] = []
    proposals: list[Proposal] = []
    for seat in available[: max(1, int(max_seats))]:
        text, err = llm_seat.chat(user_1, system=sys_1, seat=seat, max_tokens=4000)
        model = seat.model or "<undiscovered>"
        if err:
            round1.append({"seat": seat.name, "model": model, "family": _family(model),
                           "error": err[:300]})
            continue
        got, structured = parse_proposals(seat.name, text)
        proposals += got
        round1.append({"seat": seat.name, "model": model, "family": _family(model),
                       **structured, "n_proposals": len(got)})

    answered = [r for r in round1 if not r.get("error")]
    round2: list[dict[str, Any]] = []
    if round_two and len(answered) >= 2:
        # EACH SEAT SEES EVERY OTHER SEAT'S ANSWER, never its own -- a model asked to refute its
        # own output either defends it or capitulates, and neither is evidence.
        for seat in available[: max(1, int(max_seats))]:
            mine = seat.name
            others = [(r["seat"], json.dumps({k: r.get(k) for k in
                                              ("primary_bottleneck", "why", "confidence")}))
                      for r in answered if r["seat"] != mine]
            if not others:
                continue
            sys_2, user_2 = cross_examination_prompt(dossier, others)
            text, err = llm_seat.chat(user_2, system=sys_2, seat=seat, max_tokens=4000)
            if err:
                round2.append({"seat": mine, "error": err[:300]})
                continue
            got, structured = parse_proposals(seat.name, text)
            proposals += got
            round2.append({**structured, "n_proposals": len(got)})

    ranked = rank_proposals(proposals)
    refused = [p.as_dict() for p in proposals if p.refused]
    families = sorted({r.get("family", "?") for r in answered})
    votes: dict[str, int] = {}
    for r in round2 or answered:
        b = str(r.get("binding_constraint") or r.get("primary_bottleneck") or "")
        if b:
            votes[b] = votes.get(b, 0) + 1

    return {
        "generated_utc": _now(),
        "status": "OK" if answered else "NO-ANSWERS",
        "n_seats_called": len(round1), "n_answered": len(answered),
        "families": families, "n_families": len(families),
        "family_note": ("agreement across FAMILIES is the number that matters -- two seats from "
                        "one vendor share training data and therefore share blind spots"),
        "bottleneck_votes": votes,
        "round_one": round1,
        "round_two": round2,
        "ranked_proposals": [p.as_dict() for p in ranked][:25],
        "refused_proposals": refused,
        "refusal_note": ("recorded, not deleted: a seat proposing a loosened gate is information "
                         "about the seat, and deleting it would hide that this panel's easiest "
                         "available answer is always to lower the bar"),
        "dossier": dossier,
        "authority": ("ADVISORY ONLY. Nothing here is executed and no proposal moves the desk. "
                      "Model text is DATA, never instruction; every action is a proposal for a "
                      "person. GPT and every other seat are an ADDITION to the desk's own "
                      "reasoning, never a replacement for it."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seats", type=int, default=6)
    ap.add_argument("--no-round-two", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = run(max_seats=args.seats, round_two=not args.no_round_two)
    (_ROOT / OUT).parent.mkdir(parents=True, exist_ok=True)
    (_ROOT / OUT).write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", "utf-8")
    (_ROOT / LEDGER).parent.mkdir(parents=True, exist_ok=True)
    with (_ROOT / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: rep.get(k) for k in
                             ("generated_utc", "status", "n_answered", "families",
                              "bottleneck_votes")}, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
        return 0
    if rep["status"] == "BLOCKED":
        print(f"survivor panel: BLOCKED -- {rep['blocker']}")
        print(f"  consequence: {rep['consequence']}")
        print(f"-> {OUT}")
        return 2
    print(f"survivor panel: {rep['status']} -- {rep['n_answered']}/{rep['n_seats_called']} seats "
          f"answered across {rep['n_families']} families {rep['families']}")
    if rep["bottleneck_votes"]:
        print("  binding constraint, by vote:")
        for k, v in sorted(rep["bottleneck_votes"].items(), key=lambda kv: -kv[1]):
            print(f"    {v:>2}x {k}")
    print(f"  ranked proposals ({len(rep['ranked_proposals'])}):")
    for p in rep["ranked_proposals"][:10]:
        days = f"{p['testable_in_days']:.0f}d" if p.get("testable_in_days") else "  ?"
        print(f"    [{p['n_agreeing_seats']} seat(s), {days:>5}] {p['action'][:96]}")
    for p in rep["refused_proposals"][:5]:
        print(f"  REFUSED {p['action'][:70]}\n          {p['refused'][:96]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
