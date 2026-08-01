"""ZERO-CONTEXT BLIND RESEARCHER -- measures what the desk's own framing cannot see.

*** WRITTEN BUT NEVER EXECUTED (OpenRouter 402 on 2026-07-27). UNTESTED CODE. ***

THE FLAW IT FIXES, which is in my own design: every LLM role built on 2026-07-27 CONSUMES THE
DESK'S FRAMING. The breadth expander receives our class map and the six lens definitions I wrote.
The collector author receives our template. The panel receives a dossier we compile. So all three
can only expand WITHIN our conceptual boundaries -- they inherit our blind spots by construction,
which is precisely the failure L6 was created to prevent, reintroduced one level up.

This role is given NOTHING. No map, no lenses, no graveyard, no mechanism list. Just: "you are a
quant researcher entering crypto today with public data -- what would you study?" Then the answer
is DIFFED against what the desk actually covers.

    what it names AND we cover      -> confirms the map
    what it names AND we do not     -> a BLIND SPOT, measured rather than guessed
    what we cover AND it never says -> possible over-investment, or genuine private edge

The diff is the product. The suggestions themselves are secondary -- an anchored model produces
better sources, but only an UNANCHORED one can tell you what your framing excludes.

Run it cold, always. Never feed it the desk's context: doing so destroys the only property that
makes it useful.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
CLASSMAP = ROOT / "data/information_class_map.json"
MECH = ROOT / "docs/research/MECHANISM_GRAPH.md"
OUT = ROOT / "data/blind_diff.json"
CTX = ssl.create_default_context()

# deliberately DIVERSE labs -- shared training data would defeat the purpose
SEATS = ["openai/gpt-5.6-terra-pro", "google/gemini-3.1-pro-preview",
         "deepseek/deepseek-v4-pro", "qwen/qwen3.7-max"]

# NOTE: no desk context whatsoever. Adding any would destroy the measurement.
SYSTEM = (
    "You are a quantitative researcher who has just been given a budget and told to find "
    "systematic trading edges in crypto using ONLY free, public data. You have no existing "
    "infrastructure, no legacy positions and no prior assumptions. Answer from first principles."
)
USER = (
    "List the 20 things you would actually study, in priority order. For each give:\n"
    "TOPIC | DATA SOURCE | MECHANISM (why an edge could exist) | WHY MOST PEOPLE MISS IT\n"
    "Be concrete and specific. Prefer things that are structurally hard to arbitrage over things "
    "that merely sound clever. Do not hedge, do not caveat, just list them."
)


def _ask(base, key, model, messages, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 1.0,
                       "reasoning": {"effort": "high"},
                       "messages": messages}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def _ask_pushed(base, key, model):
    """Blind research is the purest push case on the desk.

    This organ is deliberately given NO desk context so it cannot anchor -- which means its first
    answer is the most generic thing it knows. The later rungs (inversion, constraint removal,
    cross-domain transfer, horizon shift) are exactly where a cold seat stops reciting and starts
    inventing. Stops when novelty dies, not at a fixed count.
    """
    r = push_rounds(lambda msgs: _ask(base, key, model, msgs), SYSTEM, USER, ladder=PUSH_LADDER)
    return r.text, f"{r.rounds} push round(s); {r.stop_reason}"


def desk_vocabulary() -> set[str]:
    """Everything the desk already talks about -- the thing we are diffing AGAINST."""
    vocab: set[str] = set()
    for p in (CLASSMAP, MECH, ROOT / "docs/graveyard.md"):
        if p.exists():
            vocab.update(w for w in re.split(r"[^a-z0-9]+", p.read_text("utf-8").lower())
                         if len(w) > 4)
    for p in (ROOT / "scripts").glob("*.py"):
        vocab.update(w for w in re.split(r"[^a-z0-9]+", p.stem.lower()) if len(w) > 4)
    return vocab


def main() -> None:
    if not KEYS.exists():
        print("no panel keys")
        return
    # Live-roster resolution: an upgraded-away seat is substituted (same lab first), not lost.
    # SEAT CAP REMOVED (2026-07-31). This read `n=len(SEATS)`, so the LITERAL'S LENGTH capped how
    # many funded seats were ever asked -- 3 of 13. Five organs shared the bug. SEATS is a
    # PRIORITY ORDER, not a membership list: the preferred list is now built from the LIVE roster
    # so every seat the desk pays for does the desk's work, and growing the roster grows the
    # organ. seats.resolve still substitutes an upgraded-away model same-lab-first.
    _roster = [str(p["model"]) for p in seats.load_roster()]
    _pref = SEATS + [m for m in _roster if m not in SEATS]
    provs = {p["model"]: p for p in seats.resolve(_pref, n=None, role="blind_researcher")}
    vocab = desk_vocabulary()
    print("=== ZERO-CONTEXT BLIND RESEARCHER ===")
    print("    *** UNTESTED SCRIPT -- verify output before trusting it ***")
    print(f"    desk vocabulary: {len(vocab)} terms. Models get NONE of it.\n")

    items, per_seat = [], {}
    for seat in list(provs):
        prov = provs.get(seat)
        if not prov:
            continue
        try:
            txt, _stop = _ask_pushed(prov["base_url"], prov["key"], seat)
            print(f"  {seat.split('/')[-1]:<24} {_stop}")
        except Exception as e:
            print(f"  {seat.split('/')[-1]:<24} FAILED ({type(e).__name__} "
                  f"{getattr(e, 'code', '')})")
            continue
        got = 0
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            parts = [x.strip() for x in ln.split("|")]
            topic = parts[0].lstrip("-*0123456789. ")
            if not topic or len(topic) > 90:
                continue
            words = {w for w in re.split(r"[^a-z0-9]+", topic.lower()) if len(w) > 4}
            known = bool(words & vocab)
            items.append({"seat": seat, "topic": topic, "source": parts[1][:90],
                          "mechanism": parts[2][:160],
                          "why_missed": parts[3][:160] if len(parts) > 3 else "",
                          "already_covered": known})
            got += 1
        per_seat[seat] = got
        print(f"  {seat.split('/')[-1]:<24} {got} topics")

    blind = [i for i in items if not i["already_covered"]]
    # cross-seat agreement on a blind spot is the strongest signal available here
    counts: dict[str, int] = {}
    for i in blind:
        k = i["topic"].lower()[:40]
        counts[k] = counts.get(k, 0) + 1

    print(f"\n  {len(items)} topics | {len(blind)} NOT in the desk's vocabulary")
    print("\n  === MEASURED BLIND SPOTS (named by an unanchored model, absent from our map) ===")
    for i in sorted(blind, key=lambda x: -counts.get(x["topic"].lower()[:40], 0))[:20]:
        seats_n = counts.get(i["topic"].lower()[:40], 1)
        mark = f"x{seats_n}" if seats_n > 1 else "  "
        print(f"    {mark} {i['topic'][:52]:<52} {i['source'][:34]}")
        print(f"          mech: {i['mechanism'][:96]}")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "per_seat": per_seat, "n_topics": len(items),
                               "n_blind": len(blind), "items": items}, indent=1), "utf-8")
    print("\n  A topic named by MULTIPLE independent labs but absent from our map is the")
    print("  strongest blind-spot signal this desk can generate. Single-seat items are noise")
    print("  until corroborated. Nothing here is an edge -- it is a research target.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
