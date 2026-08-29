"""The desk's research roles, running on free models, on a clock, with nobody watching.

WHY THIS EXISTS (principal, 2026-08-29)

    "nothing should rely on claude limit or wait for it"
    "even if today's session ends it still continues the whole pipeline as usual --
     discoveries fed to python by openrouter generations, validations, live"

That is the correct requirement and the desk did not meet it. The mechanism-generating role has
NEVER run: `data/hypothesis_queue.jsonl` has never existed, the generator sat on no timer, and
four scripts consumed a file that was never created. The cause was a $60 OpenRouter balance
running out and a 402 killing the role outright instead of degrading it.

So every role here draws from `free_panel` -- thirteen zero-cost models verified answering on an
overdrawn key -- and runs on a systemd timer. No step of it waits for a session, a subscription,
or a person.

FOUR ROLES, EACH WITH A DIFFERENT JOB AND A DIFFERENT FAILURE MODE:

    GENERATE  propose mechanisms WITH the graveyard in hand. A generator that cannot see what is
              already refuted keeps re-proposing the dead -- measured here: three of the first
              four hypotheses from an unprimed model were already refuted on this desk.
    AUDIT     cold-read the docket and name what is MISSING. Its value is that it has no stake in
              what is already there.
    REVIEW    adversarially attack a certificate, given frozen facts and no story. Never sees
              "this is our best candidate", because that sentence is worth nothing and biases
              everything.
    FEEDBACK  read the measured funnel and say where the search is stuck. This is the role that
              turns yesterday's outcome into tomorrow's direction.

NOTHING HERE HAS PROMOTION AUTHORITY. Output is a queue of candidate mechanisms and a set of
reports. Every proposal enters the funnel where all other candidates do and faces the identical
gauntlet. A free model proposing a mechanism is exactly as unprivileged as a parameter sweep
emitting one -- which is the property that makes running weaker models safe.

A FREE MODEL IS WORSE THAN A FLAGSHIP AND INFINITELY BETTER THAN A 402. The downside is trials
spent on weaker ideas; the upside is the role existing at all.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"
OUT = ROOT / "data" / "free_research.json"

#: How many refuted ideas to show the generator. Enough to steer it off dead ground, few enough
#: that a free model's context is spent on the task rather than on the list.
GRAVEYARD_N = 40

#: A proposal missing any of these is not a hypothesis. The desk holds 16,000 candidates that
#: were never asked for a mechanism, and that is precisely why yield is 0.33%.
_REQUIRED = ("name", "mechanism", "payer", "test", "kill")


#: PARSE FOR STRUCTURE, DO NOT STRIP PROSE. A first version tried to detect reasoning traces by
#: their opening words -- "here's my thinking", "let me analyse", "first, the user" -- and every
#: fix revealed another opener ("we need to parse the prompt"). That is unwinnable: there is no
#: finite list of ways a model can start talking to itself.
#:
#: The generator never had this problem, because it demands `A | B | C | D | E` and DROPS anything
#: malformed. Structure is verifiable; prose is not. So every role now returns delimited lines and
#: anything that does not match is discarded -- a role that produced no parseable line reports
#: NOTHING rather than storing deliberation, which is the honest outcome and a visible one.
_LINE = re.compile(r"^\s*[-*\d.\s]*([^|]{3,120})\|(.{10,400})$")


def _parse_lines(text: str, want: int) -> list[tuple[str, str]]:
    """Delimited `LABEL | BODY` lines only. Prose is dropped, never salvaged."""
    out: list[tuple[str, str]] = []
    for raw in (text or "").splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        label, body = m.group(1).strip(" *#`"), m.group(2).strip()
        # A reasoning trace occasionally contains a pipe; a real answer's label is short and has
        # no sentence punctuation in it.
        if len(label) > 90 or label.count(".") > 1:
            continue
        out.append((label, body))
        if len(out) >= want:
            break
    return out


def _graveyard() -> list[str]:
    """Families and cells the desk has already refuted, as short labels."""
    out: list[str] = []
    census = ROOT / "data" / "research_allocation.json"
    try:
        rep = json.loads(census.read_text("utf-8"))
        for fam in rep.get("unconfirmed_high_attempts", []):
            out.append(f"{fam} (100+ attempts, 0 certificates)")
    except (OSError, json.JSONDecodeError):
        pass
    try:
        surv = json.loads((DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
                          .read_text("utf-8")).get("survivors") or {}
        for k in list(surv)[:20]:
            out.append(f"ALREADY CERTIFIED: {k}")
    except (OSError, json.JSONDecodeError):
        pass
    return out[:GRAVEYARD_N]


def _parse_proposals(text: str) -> list[dict[str, str]]:
    """Pipe-delimited lines into records. Anything malformed is DROPPED, never repaired.

    Repairing a malformed proposal means inventing the part the model did not supply, and the
    missing part is usually the mechanism -- the one field that matters.
    """
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. ")
        if line.count("|") < 4:
            continue
        parts = [p.strip() for p in line.split("|")]
        rec = dict(zip(_REQUIRED, parts[:5], strict=False))
        if all(rec.get(f) for f in _REQUIRED) and len(rec["mechanism"]) > 12:
            rows.append(rec)
    return rows


def role_generate(panel: Any) -> dict[str, Any]:
    dead = _graveyard()
    system = (
        "You are a market microstructure researcher on an MT5/Fusion desk trading FX, metals, "
        "indices, energy and share CFDs. You propose MECHANISMS, never strategies.\n"
        "Every proposal must name a PAYER: a participant COMPELLED to trade for a reason that is "
        "not a forecast (a hedger, an index tracker, a margin call, a benchmark clock). If nobody "
        "is forced, arbitrage removes the edge and the proposal is worthless.\n"
        "You must also give a KILL CONDITION -- the observation that would prove you wrong.")
    user = (
        "ALREADY DEAD OR ALREADY OWNED on this desk -- do not re-propose these:\n"
        + "\n".join(f"  - {d}" for d in dead)
        + "\n\nPropose 6 NEW mechanisms. One per line, EXACTLY this format, no preamble:\n"
          "NAME | MECHANISM (<=25 words, name the payer) | PAYER | TEST | KILL CONDITION")
    r = panel.ask("generation", system, user, max_tokens=1400, temperature=0.95)
    props = _parse_proposals(r.text)
    return {"role": "generate", "model": r.model, "proposals": props,
            "raw_lines": len(r.text.splitlines()), "parsed": len(props)}


def role_feedback(panel: Any) -> dict[str, Any]:
    try:
        alloc = json.loads((ROOT / "data" / "research_allocation.json").read_text("utf-8"))
        intake = json.loads((ROOT / "data" / "research_intake.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"role": "feedback", "skipped": "census artifacts absent"}
    facts = (
        f"candidates: {alloc.get('total_candidates')}, certificates: "
        f"{alloc.get('total_certified')}, overall yield {alloc.get('overall_yield_pct')}%\n"
        f"semantic regions with conclusive evidence: "
        f"{intake.get('coverage', {}).get('regions_with_conclusive_evidence')} of "
        f"{intake.get('coverage', {}).get('regions')}\n"
        f"regions never touched: {intake.get('coverage', {}).get('regions_never_touched')}\n"
        f"candidates with NO declared mechanism: {intake.get('unmapped_families')}\n"
        f"novelty sample: {intake.get('novelty')}")
    r = panel.ask("feedback",
                  "You audit a quant research pipeline. You are given MEASURED facts only. Name "
                  "where the search is stuck and what ONE change would most raise independent "
                  "survivor yield. Be concrete and brief. Do not propose lowering any threshold.",
                  f"Measured state:\n{facts}\n\nWhat is the binding constraint, and why?",
                  max_tokens=700, temperature=0.6)
    rows = _parse_lines(r.text, 3)
    return {"role": "feedback", "model": r.model,
            "findings": [{"constraint": a, "why": b} for a, b in rows],
            "parsed": len(rows),
            "unparseable": None if rows else "model returned no delimited line; nothing stored"}


def role_audit(panel: Any) -> dict[str, Any]:
    try:
        intake = json.loads((ROOT / "data" / "research_intake.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"role": "audit", "skipped": "intake artifact absent"}
    never = intake.get("coverage", {}).get("never_touched", [])[:25]
    r = panel.ask("audit",
                  "You are a cold auditor with no stake in existing work. You name what is "
                  "MISSING, not what is wrong. OUTPUT RULES: no preamble, no reasoning "
                  "trace. Emit ONLY the requested lines.",
                  "These economic regions (event|direction) have NEVER been searched on this "
                  f"desk:\n{json.dumps(never, indent=0)}\n\n"
                  "Pick the THREE most likely to contain a real, compelled-flow edge on FX, "
                  "metals or index CFDs. For each give one line: REGION | why a payer exists "
                  "there.", max_tokens=600, temperature=0.7)
    rows = _parse_lines(r.text, 3)
    return {"role": "audit", "model": r.model, "unsearched_shown": len(never),
            "regions": [{"region": a, "why_a_payer_exists": b} for a, b in rows],
            "parsed": len(rows),
            "unparseable": None if rows else "model returned no delimited line; nothing stored"}


def main() -> int:
    from libs.research import free_panel as panel

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roles", default="generate,feedback,audit")
    args = ap.parse_args()

    now = datetime.now(tz=UTC)
    health = panel.panel_health()
    print(f"FREE RESEARCH {now.isoformat(timespec='seconds')}")
    print(f"  panel: {health['heavy_available']}/{health['heavy_total']} heavy, "
          f"{health['light_available']}/{health['light_total']} light"
          f"{'  cooling: ' + str(list(health['cooling_down'])) if health['cooling_down'] else ''}")

    results: list[dict[str, Any]] = []
    runners = {"generate": role_generate, "feedback": role_feedback, "audit": role_audit}
    for name in [r.strip() for r in args.roles.split(",") if r.strip()]:
        fn = runners.get(name)
        if fn is None:
            continue
        try:
            res = fn(panel)
        except panel.PanelExhausted as exc:
            # Capacity, not defect. Recorded so a run that did nothing cannot be mistaken for a
            # run that found nothing.
            res = {"role": name, "panel_exhausted": str(exc)[:200]}
        except Exception as exc:
            res = {"role": name, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        results.append(res)
        print(f"\n  [{name}] model={res.get('model', '-')}")
        if res.get("proposals") is not None:
            print(f"    parsed {res['parsed']} of {res['raw_lines']} lines")
            for p in res["proposals"][:6]:
                print(f"      {p['name'][:34]:36s} payer={p['payer'][:46]}")
        for k in ("findings", "regions"):
            for row in res.get(k, []) or []:
                vals = [*row.values(), "", ""]
                a, b = vals[0], vals[1]
                print(f"      {str(a)[:38]:40s} {str(b)[:78]}")
        if res.get("unparseable"):
            print(f"    UNPARSEABLE: {res['unparseable']}")
        for k in ("panel_exhausted", "error", "skipped"):
            if res.get(k):
                print(f"    {k.upper()}: {res[k][:170]}")

    # ---- append proposals to the queue every consumer has been waiting for -------------------
    new = 0
    for res in results:
        for p in res.get("proposals", []) or []:
            rec = {**p, "proposed_at": now.isoformat(timespec="seconds"),
                   "model": res.get("model"), "source": "free_panel",
                   "promotion_authority": False,
                   "note": ("no authority whatsoever; enters the funnel where every other "
                            "candidate does and faces the identical gauntlet")}
            with QUEUE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            new += 1
    total = sum(1 for _ in QUEUE.open(encoding="utf-8")) if QUEUE.exists() else 0
    print(f"\n  queue: +{new} this run, {total} total -> {QUEUE}")

    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"),
                               "panel": health, "results": results,
                               "queue_added": new, "queue_total": total}, indent=1,
                              default=str), "utf-8")
    print(f"  -> {OUT}")
    # A run that proposed nothing AND hit no exhaustion is a silent failure worth surfacing.
    produced = any(r.get("proposals") for r in results)
    exhausted = any(r.get("panel_exhausted") for r in results)
    return 0 if (produced or exhausted) else 1


if __name__ == "__main__":
    raise SystemExit(main())
