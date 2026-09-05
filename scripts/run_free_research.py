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
from contextlib import suppress
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

#: The PAID prompt's output contract, field for field:
#:     NAME | MECHANISM (<=25 words) | DATA SOURCE | TEST | KILL CONDITION
#:
#: MUST MATCH THE PROMPT EXACTLY. A first version named field 3 `payer` while the prompt asked
#: for DATA SOURCE, so every proposal was stored with a dataset in its payer field -- and the
#: compiler, the docket and every later reader would have believed the desk had recorded who is
#: compelled to trade when it had recorded a URL. A mislabelled field is worse than a missing one:
#: it is confidently wrong and nothing downstream can tell.
#:
#: The PAYER lives inside `mechanism` -- the prompt's rule 1 requires a mechanism that survives
#: "why has nobody arbitraged this?", which is the payer question asked the other way round.
#: THE AXES ARE PART OF THE CLAIM, NOT METADATA. Measured 2026-09-04: of 1,959 refused
#: proposals, 955 (49%) were refused for an unresolved event, direction or context -- the miner
#: named a mechanism but never said WHEN it fires or WHICH WAY. The compiler is right to refuse
#: (guessing 'asia' runs the experiment in a session the hypothesis never named), so the fix
#: belongs at generation: ask for the axes and they arrive. This is the single largest conversion
#: lever the desk has, and it needs no new data source.
_REQUIRED = ("name", "mechanism", "data_source", "test", "kill",
             "event", "context", "direction")


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


#: The compiler's OWN vocabularies, imported rather than restated. A second copy here would drift
#: from `compile_proposals` and start asking miners for axis values the compiler cannot resolve --
#: which is the same refusal it exists to prevent, arriving one layer earlier.
def _axis_words() -> tuple[list[str], list[str], list[str]]:
    import importlib.util as ilu
    spec = ilu.spec_from_file_location(
        "_cp_axes", Path(__file__).resolve().parent / "compile_proposals.py")
    if spec is None or spec.loader is None:      # pragma: no cover - file ships with this one
        return [], [], []
    mod = ilu.module_from_spec(spec)
    sys.modules.setdefault("_cp_axes", mod)
    with suppress(SystemExit):
        spec.loader.exec_module(mod)
    return (sorted(getattr(mod, "_EVENT_WORDS", {})),
            sorted(getattr(mod, "_CONTEXT_WORDS", {})),
            sorted(getattr(mod, "_DIRECTION_WORDS", {})))


_AXIS_EVENT, _AXIS_CONTEXT, _AXIS_DIRECTION = _axis_words()


#: The format spec, restated. A free model that cannot follow the contract often ECHOES it --
#: "NAME | MECHANISM (<=25 words) | TEST | KILL CONDITION" parses as a perfectly well-formed
#: row, and 435 of them (20.1% of the queue) had banked as hypotheses by 2026-09-04. The only
#: content check was `len(mechanism) > 12`, and "MECHANISM (<=25 words)" is 22 characters.
_ECHO_LITERALS = {
    "name", "mechanism", "test", "kill", "kill condition", "data source", "data_source",
    "mechanism (<=25 words)", "mechanism(<=25 words)", "lens", "context", "direction", "event",
}
_ECHO_INSTRUCTION = re.compile(
    r"we need to (output|produce|write|give|propose)|each line|<=\s*\d+\s*words|"
    r"exactly \d+ hypothes|^format:", re.I)


def _is_template_echo(rec: dict[str, str]) -> bool:
    """True when the row restates the PROMPT rather than answering it.

    Two independent tells, either sufficient: a field whose whole value is its own placeholder,
    or a name carrying the instruction text. Echoes are dropped at the parser, not refused later,
    because a queue that contains its own prompt makes every conversion rate downstream a lie.
    """
    if _ECHO_INSTRUCTION.search(str(rec.get("name") or "")):
        return True
    return sum(1 for f in ("name", "mechanism", "test", "kill", "data_source")
               if str(rec.get(f) or "").strip().lower() in _ECHO_LITERALS) >= 2

def _parse_proposals(text: str) -> list[dict[str, str]]:
    """Pipe-delimited lines into records. Anything malformed is DROPPED, never repaired.

    Repairing a malformed proposal means inventing the part the model did not supply, and the
    missing part is usually the mechanism -- the one field that matters.
    """
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. ")
        if line.count("|") < len(_REQUIRED) - 1:
            continue
        parts = [p.strip() for p in line.split("|")]
        rec = dict(zip(_REQUIRED, parts[:len(_REQUIRED)], strict=False))
        # THE OPTIONAL EIGHTH FIELD: a factor tree for the two shapes family_generic cannot
        # express. Parsed here and handed to the compiler, which validates it against the DSL
        # allowlist and only then waives the capability refusal. A malformed tree is DROPPED
        # rather than repaired -- repairing it would invent the half the model did not supply.
        if len(parts) > len(_REQUIRED):
            raw = "|".join(parts[len(_REQUIRED):]).strip()
            if raw.startswith("["):
                with suppress(json.JSONDecodeError):
                    rec["factor"] = json.loads(raw)
        if (all(rec.get(f) for f in _REQUIRED) and len(rec["mechanism"]) > 12
                and not _is_template_echo(rec)):
            rows.append(rec)
    return rows


def _rich_prompt() -> tuple[str, list[tuple[str, str]]]:
    """The PAID generator's own system prompt and causal lenses, reused for the free panel.

    "use all previously proposed prompts for the paid, but for free now" -- and the paid
    generator's prompt is genuinely better than anything written from scratch here. It leads with
    the desk's constitution (a generator that does not know the objective optimises for what a
    hypothesis LOOKS like), demands a mechanism that survives "why has nobody arbitraged this?",
    requires a named public data source and an explicit kill condition, and tells the model that a
    hypothesis whose likely outcome is a DISPROOF is a good hypothesis.

    Imported rather than copied: two divergent copies of a prompt is the same drift disease as two
    identity builders, and the paid path is where the prompt is maintained.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_hypgen", ROOT / "scripts" / "hypothesis_generator.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load hypothesis_generator for its prompt")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_hypgen"] = mod
    spec.loader.exec_module(mod)
    return mod.SYSTEM, list(mod.LENSES)


def role_generate(panel: Any) -> dict[str, Any]:
    """Generate through EVERY causal lens, on free models, with the graveyard in hand."""
    dead = _graveyard()
    try:
        system, lenses = _rich_prompt()
        source = "hypothesis_generator.SYSTEM (paid prompt, free panel)"
    except Exception as exc:
        # FAIL LOUD, DO NOT SILENTLY DOWNGRADE. A weaker fallback prompt would still produce
        # proposals, and nobody would ever notice the desk had stopped using its real one.
        return {"role": "generate", "error": f"rich prompt unavailable: {type(exc).__name__}: "
                                             f"{str(exc)[:120]} -- refusing to generate on an "
                                             f"unnamed fallback prompt"}

    props: list[dict[str, str]] = []
    used: list[str] = []
    per_lens: dict[str, int] = {}
    for name, lens in lenses:
        user = (
            f"CAUSAL LENS -- {name}: {lens}\n\n"
            "ALREADY DEAD OR ALREADY OWNED on this desk -- do not re-propose these:\n"
            + "\n".join(f"  - {d}" for d in dead)
            + "\n\nPropose 3 NEW hypotheses through THIS LENS ONLY. One per line, exactly:\n"
              "NAME | MECHANISM (<=25 words) | DATA SOURCE | TEST | KILL CONDITION | "
              "EVENT | CONTEXT | DIRECTION\n"
              "The last three are the CLAIM'S OWN AXES and must each be ONE word from these "
              "lists, chosen because the mechanism says so -- never to fill the field:\n"
              f"  EVENT:     {', '.join(_AXIS_EVENT)}\n"
              f"  CONTEXT:   {', '.join(_AXIS_CONTEXT)}\n"
              f"  DIRECTION: {', '.join(_AXIS_DIRECTION)}\n"
              "If the mechanism genuinely does not pick one, the hypothesis is not ready -- "
              "propose a different one rather than guessing, because a guessed axis tests a "
              "claim nobody made.\n"
              "\nIF AND ONLY IF the mechanism needs a cross-sectional rank or a multi-leg "
              "spread -- shapes the generic family cannot express -- append an EIGHTH field: a "
              "FACTOR TREE in JSON, e.g.\n"
              '  ["spread",["col","close"],["sym","GBPUSD","close"]]\n'
              '  ["rank",["col","close"]]\n'
              '  ["resid",["col","close"],["sym","XAUUSD","close"]]\n'
              "Operators: col, sym, lag, diff, pct, roll_mean, roll_std, roll_max, roll_min, "
              "zscore, rank, spread, ratio, resid, add, mul, gt, lt, cond, session, decay, const. "
              "Windows must be POSITIVE (a negative shift would read a future bar and is "
              "refused). Omit this field entirely when the mechanism does not need it -- a tree "
              "supplied for its own sake is complexity the gauntlet has to pay for.\n"
              "No preamble, no reasoning, no headings. Any line without seven '|' is discarded.")
        try:
            r = panel.ask("generation", system, user, max_tokens=1200, temperature=0.95)
        except Exception:
            # One lens failing is not the batch failing; the others still carry information.
            continue
        got = _parse_proposals(r.text)
        for g in got:
            g["lens"] = name
        props.extend(got)
        per_lens[name] = len(got)
        used.append(r.model)
    return {"role": "generate", "model": ",".join(sorted(set(used)))[:120],
            "prompt_source": source, "lenses": len(lenses), "per_lens": per_lens,
            "proposals": props, "raw_lines": sum(per_lens.values()), "parsed": len(props)}


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
                print(f"      {p['name'][:34]:36s} {p['mechanism'][:52]}")
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
