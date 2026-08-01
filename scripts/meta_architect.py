"""META-RESEARCH ARCHITECT + RESEARCH SIMPLIFIER -- improve the research SYSTEM, and prune it.

Two functions, deliberately paired, because a desk that only ADDS capability loses to entropy:

  SIMPLIFIER (mechanical, runs today)  -- what should be REMOVED or wired?
  ARCHITECT  (LLM, blocked on funding) -- what bottleneck should be attacked next?

THE PRINCIPAL'S FRAMING, adopted: this is NOT "GPT suggests things". It is a model-agnostic
ARCHITECTURE REVIEW BOARD. It does not care whether a proposal comes from GPT, Claude, Grok or
Nemotron; it cares whether the proposal names a measurable bottleneck and can be killed later.

THE BINDING RULE (principal): every new component must EITHER replace an existing component OR
improve a measurable bottleneck. A proposal that cannot name the bottleneck it removes, the metric
it should move, and how you would know it failed, stays in the backlog. That is the difference
between a research OS that evolves and one that accumulates layers because they were interesting.

WHY THE SIMPLIFIER EXISTS AND WHY IT RUNS FIRST: ~20 components were added to this desk in a single
day. Most are not wired to any cadence and have run exactly once. That is textbook architectural
bloat, created by the same process that created the useful parts, and nothing in the desk was
watching for it. The simplifier's first job is auditing that.

Read-only. The simplifier needs no keys; the architect needs OpenRouter (currently 402).
"""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
CYCLE = ROOT / "scripts/daily_research_cycle.py"
OUT = ROOT / "data/meta_architect.json"
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
CTX = ssl.create_default_context()
SEATS = ["openai/gpt-5.6-terra-pro", "x-ai/grok-4.3", "google/gemini-3.1-pro-preview"]

CHARTER = (
    "You are an ARCHITECTURE REVIEW BOARD for a quantitative research desk. You do NOT propose "
    "trading ideas. You propose improvements to the RESEARCH SYSTEM ITSELF.\n\n"
    "THE BINDING RULE: every proposal must EITHER replace an existing component OR improve a "
    "MEASURABLE bottleneck. Proposals that add capability without removing a constraint are "
    "rejected -- architectural bloat is the failure mode you exist to prevent.\n\n"
    "EVERY proposal MUST contain all seven fields. Missing any field = automatic rejection:\n"
    "PROBLEM | EVIDENCE | BENEFIT | COST | DEPENDENCIES | SUCCESS_METRIC | KILL_CONDITION\n\n"
    "  PROBLEM        a measurable bottleneck, not a missing feature\n"
    "  EVIDENCE       the observation that shows it -- cite a number from the state given to you\n"
    "  BENEFIT        which metric moves, and roughly how much\n"
    "  COST           engineering time + compute + ONGOING MAINTENANCE\n"
    "  DEPENDENCIES   what must already exist (say NONE if none)\n"
    "  SUCCESS_METRIC how you would know it worked, measurable\n"
    "  KILL_CONDITION when it should be REMOVED again\n\n"
    "Prefer proposals that DELETE or MERGE over proposals that ADD. Ask: where is research effort "
    "being wasted? which bottleneck now dominates? what assumption is no longer true? which "
    "experiments should be retired? Output one proposal per line, fields separated by |."
)


# ---------------------------------------------------------------- SIMPLIFIER (mechanical)

def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def simplifier() -> dict:
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    cycle_txt = CYCLE.read_text("utf-8") if CYCLE.exists() else ""
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              check=False, timeout=20).stdout
    except Exception:
        cron = ""
    try:
        recent = subprocess.run(["git", "log", "--since=30 days ago", "--name-only",
                                 "--pretty=format:"], cwd=str(ROOT), capture_output=True,
                                text=True, check=False, timeout=40).stdout
    except Exception:
        recent = ""

    unwired, orphan_out, wired = [], [], []
    for p in scripts:
        name = p.name
        stem = p.stem
        is_wired = (name in cycle_txt) or (name in cron)
        # does anything consume its output? crude but honest: does another script mention it?
        produces = re.findall(r'data/([A-Za-z0-9_]+)\.(?:json|jsonl)', p.read_text("utf-8",
                                                                                   errors="ignore"))
        consumed = False
        for art in set(produces):
            for q in scripts:
                if q != p and art in q.read_text("utf-8", errors="ignore"):
                    consumed = True
                    break
            if consumed:
                break
        (wired if is_wired else unwired).append(stem)
        if produces and not consumed and not is_wired:
            orphan_out.append(stem)
    return {"n_scripts": len(scripts), "wired": wired, "unwired": unwired,
            "orphan_outputs": orphan_out,
            "touched_30d": len({ln.strip() for ln in recent.splitlines() if ln.strip()})}


def _ask(base, key, model, system, user, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 12000, "temperature": 0.9,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("meta_architect") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def desk_state(simp: dict) -> str:
    """Facts the board must reason FROM -- a suggestor without state re-proposes what exists."""
    bits = [
        "MEASURED DESK STATE (reason from these numbers, do not restate them as proposals):",
        f"- {simp['n_scripts']} scripts; {len(simp['unwired'])} are NOT wired to any cadence",
        f"- {len(simp['orphan_outputs'])} scripts write artifacts NOTHING reads",
        "- carry: funding harvested $113 vs implied costs $876 (7.75x); fails risk-free hurdle",
        "- entry signal WORKS: funding persistence IC +0.432 (t +29.7), +25%/yr selection edge",
        "- ~28 hypotheses tested in one day, 1 survived; the survivor audited the LIVE system",
        "- failure autopsy: 38% WRONG_TIMING, 26% DATA_QUALITY -> 64% are measurement, not alpha",
        "- mechanism verdicts: 4 FAMILY KILLS (price-pattern, attention, skill-persistence, flow)",
        "- ALIVE mechanisms: forced-deleverage, structural-barrier. UNTESTED: liquidity-withdrawal",
        "- data/moat = 4.4GB recorded order books, DELTA-encoded, needs reconstruction, unmined",
        "- 3 LLM roles written but NEVER EXECUTED (OpenRouter 402)",
        "- 0 confirmed alphas; 3 forward clocks; first verdict Aug 7",
    ]
    return "\n".join(bits)


def main() -> None:
    print("=== RESEARCH SIMPLIFIER (mechanical -- runs today) ===")
    print("    a desk that only ADDS capability loses to entropy\n")
    s = simplifier()
    print(f"  {s['n_scripts']} scripts | {len(s['wired'])} wired to cadence | "
          f"{len(s['unwired'])} UNWIRED")
    print(f"  {len(s['orphan_outputs'])} write artifacts NOTHING reads:\n")
    for name in sorted(s["orphan_outputs"])[:24]:
        print(f"    {name}")
    if len(s["orphan_outputs"]) > 24:
        print(f"    ... +{len(s['orphan_outputs'])-24} more")
    print("\n  RULE: an unwired script that writes an unread artifact is either (a) a one-off")
    print("  analysis that should be ARCHIVED, or (b) a real capability that should be WIRED.")
    print("  Leaving it in scripts/ unwired is the third option, and it is the wrong one.")

    print("\n=== META-RESEARCH ARCHITECT (LLM -- charter-bound) ===")
    print("    NOT 'GPT suggests things': a model-agnostic architecture review board.")
    print("    7 mandatory fields; missing any = automatic rejection.")
    print("    BINDING RULE: replace a component OR improve a measurable bottleneck.\n")
    state = desk_state(s)
    print(state)

    if not KEYS.exists():
        print("\n  no panel keys -- architect cannot run")
        return
    # Seats resolve against the LIVE roster: an upgraded-away model is substituted (same lab
    # first), never silently dropped -- the old provs.get(seat)/continue amputated this board
    # to zero without a word the moment a seat was swapped.
    provs = {p["model"]: p for p in seats.resolve(SEATS, n=len(SEATS), role="meta_architect")}
    if not provs:
        print("\n  no panel seats resolvable -- architect cannot run")
        return
        print("\n  no panel keys -- architect cannot run")
        return
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
    user = (f"{state}\n\nPropose 6-10 improvements to this RESEARCH SYSTEM. Prefer DELETE/MERGE "
            f"over ADD. All seven fields required per proposal.")
    rows = []
    for seat in list(provs):
        prov = provs.get(seat)
        if not prov:
            continue
        try:
            txt = _ask(prov["base_url"], prov["key"], seat, CHARTER, user)
        except Exception as e:
            print(f"  {seat.split('/')[-1]:<22} FAILED ({type(e).__name__} "
                  f"{getattr(e, 'code', '')})")
            continue
        kept = rejected = 0
        for ln in txt.splitlines():
            parts = [x.strip() for x in ln.split("|")]
            if len(parts) < 7:
                if ln.count("|") >= 2:
                    rejected += 1                      # looked like a proposal, missing fields
                continue
            rows.append({"date": datetime.now(tz=UTC).date().isoformat(), "seat": seat,
                         "problem": parts[0][:200], "evidence": parts[1][:200],
                         "benefit": parts[2][:160], "cost": parts[3][:120],
                         "dependencies": parts[4][:120], "success_metric": parts[5][:160],
                         "kill_condition": parts[6][:160], "status": "proposed"})
            kept += 1
        print(f"  {seat.split('/')[-1]:<22} {kept} charter-complete, {rejected} rejected "
              f"(incomplete fields)")

    if rows:
        with LEDGER.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        print(f"\n  {len(rows)} proposals -> {LEDGER}")
        for r in rows[:8]:
            print(f"    [{r['seat'].split('/')[-1][:12]}] {r['problem'][:70]}")
            print(f"        metric: {r['success_metric'][:70]}  kill: {r['kill_condition'][:44]}")
    print("\n  SUGGESTION YIELD is tracked in the ledger: proposed -> accepted -> built ->")
    print("  changed-a-decision -> improved-live. A seat generating 200 clever proposals and one")
    print("  live improvement ranks BELOW one generating 20 of which five become infrastructure.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "simplifier": s, "proposals": len(rows)}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
