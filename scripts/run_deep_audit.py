"""Give a free million-token model the WHOLE desk and ask what it is systematically failing to see.

WHY THIS EXISTS (principal, 2026-08-29: "can free tiers be exploited more -- if so exploit them
in every way for research, audits, recommendations, weakness targeting, hunts, survivors")

They could, and by a wide margin. Measured the same day: 22 free calls across an entire session,
zero models rate-limited, no account request cap. But the real waste was not the call count --

    the free panel includes models with 1,048,576-token context
    the desk was sending them a few hundred tokens

That is the difference between asking "propose a mechanism" and asking "here is every
certificate, the whole graveyard, the measured funnel, the coverage map and the measurement
audit -- now tell me what this desk is structurally blind to".

WHY WHOLE-STATE QUESTIONS ARE DIFFERENT IN KIND. A paginated prompt can only ever answer local
questions, because the model never sees two distant parts of the desk at once. Loading everything
allows the questions that actually matter here:

    which mechanism is absent across EVERY market, not just this one
    which failure repeats across families that share no code
    where the search has a BLIND SPOT rather than a gap -- a region nobody thought to name

Those are the questions worth spending a free call on, and none of them survives pagination.

FOUR ROLES, EACH A DIFFERENT LENS ON THE SAME STATE. Weakness targeting looks for what is broken;
survivor hunting looks for what is nearly working and being wasted; blind-spot search looks for
what was never considered; and the falsifier looks for the desk's most load-bearing assumption.
Running one model over four framings is cheaper and more diverse than four models over one.

NO AUTHORITY, AS EVER. Output is a report and a queue of coordinates. Every suggestion enters the
funnel where all candidates do and faces the identical gauntlet.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "deep_audit.json"

#: Artifacts that together describe the whole research state. Each is loaded whole -- the point
#: of a million-token context is that nothing has to be summarised away first.
_STATE_FILES: dict[str, Path] = {
    "measured_funnel": ROOT / "data" / "research_allocation.json",
    "semantic_coverage": ROOT / "data" / "research_intake.json",
    "forward_lane": ROOT / "data" / "forward_lane_health.json",
    "family_evidence": DESK / "reports" / "shadow" / "FAMILY_EVIDENCE.json",
    "bar_coverage": ROOT / "data" / "bar_coverage.json",
    "unmeasurable_claims": ROOT / "data" / "unmeasurable_claims.json",
    "proposal_compiler": ROOT / "data" / "proposal_compiler.json",
    "research_loop": ROOT / "data" / "research_loop.json",
    "promotion_readiness": ROOT / "data" / "promotion_readiness.json",
}

#: Roughly the usable share of a 1M window after the model's own overheads. Generous: the tier is
#: free, and truncating the state to be polite defeats the entire purpose.
_MAX_STATE_CHARS = 600_000


def _load_state() -> tuple[str, dict[str, int]]:
    """The desk's whole research state as one document, plus what went into it."""
    parts: list[str] = []
    sizes: dict[str, int] = {}
    for name, path in _STATE_FILES.items():
        try:
            raw = path.read_text("utf-8")
        except OSError:
            sizes[name] = 0
            continue
        sizes[name] = len(raw)
        parts.append(f"### {name} ({path.name})\n{raw}\n")

    # Certificates and the measurement audit are the two most decision-relevant blocks, so they
    # go LAST -- if anything is truncated it should be the routine telemetry, not the evidence.
    try:
        certs = (DESK / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8")
        parts.append(f"### certificates (UNIVERSAL_SURVIVORS.json)\n{certs}\n")
        sizes["certificates"] = len(certs)
    except OSError:
        sizes["certificates"] = 0
    try:
        from libs.research.measurement import audit

        m = json.dumps(audit(), indent=1)
        parts.append(f"### measurement_audit\n{m}\n")
        sizes["measurement_audit"] = len(m)
    except Exception:
        sizes["measurement_audit"] = 0

    doc = "\n".join(parts)
    if len(doc) > _MAX_STATE_CHARS:
        doc = doc[:_MAX_STATE_CHARS] + "\n[TRUNCATED -- state exceeded the window]"
    return doc, sizes


#: The four lenses. Each demands delimited output for the same reason every other role does:
#: prose cannot be parsed, and a role that returns prose has produced nothing a machine can act
#: on. See run_free_research for why detecting prose is unwinnable and structure is not.
_LENSES: dict[str, tuple[str, str]] = {
    "weakness": (
        "You audit a quantitative research desk. You are given its ENTIRE state.",
        "Name the THREE structural weaknesses most limiting independent forward survivors. A "
        "structural weakness is one that persists across families, not a single bad result.\n"
        "Emit ONLY lines: WEAKNESS | evidence in the state | the one change that fixes it\n"
        "At most 3 lines. No preamble, no reasoning. Lines without two '|' are discarded."),
    "blind_spot": (
        "You look for what is ABSENT. Things nobody thought to test do not appear in any "
        "failure list, so they are invisible to every check that reads results.",
        "Given the coverage map and mechanism census, name THREE economic mechanisms this desk "
        "has never considered at all -- not tested-and-failed, never named. Each must have a "
        "PAYER compelled to trade for a reason that is not a forecast, on FX, metals, indices or "
        "energy.\nEmit ONLY lines: MECHANISM | the compelled payer | why nobody looks there\n"
        "At most 3 lines. No preamble. Lines without two '|' are discarded."),
    "survivor_hunt": (
        "You hunt for value being WASTED -- candidates that are nearly working and are being "
        "discarded, mismeasured, or starved of trials.",
        "Given the funnel, the measurement audit and the forward lane, name THREE specific "
        "candidates or families that are closer to surviving than the desk's own numbers "
        "suggest, and say what is masking them.\n"
        "Emit ONLY lines: CANDIDATE | what is masking it | the cheapest test that would settle "
        "it\nAt most 3 lines. No preamble. Lines without two '|' are discarded."),
    "assumption": (
        "You find the single assumption a system most depends on and least examines.",
        "Given the whole state, name the THREE load-bearing assumptions this desk would be most "
        "damaged by being wrong about, and how each could be checked cheaply.\n"
        "Emit ONLY lines: ASSUMPTION | why it is load-bearing | the cheap check\n"
        "At most 3 lines. No preamble. Lines without two '|' are discarded."),
}


def _parse(text: str, want: int = 3) -> list[tuple[str, str, str]]:
    """`A | B | C` lines only. Prose is dropped, never salvaged."""
    out: list[tuple[str, str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*#0123456789. ")
        if line.count("|") < 2:
            continue
        a, b, c = (p.strip(" *`") for p in line.split("|", 2))
        if len(a) > 100 or not a or not b:
            continue
        out.append((a, b, c))
        if len(out) >= want:
            break
    return out


def main() -> int:
    from libs.research import free_panel as panel

    now = datetime.now(tz=UTC)
    state, sizes = _load_state()
    total = sum(sizes.values())
    print(f"DEEP AUDIT {now.isoformat(timespec='seconds')}")
    print(f"  desk state assembled: {total:,} chars from {len([s for s in sizes.values() if s])} "
          f"artifact(s) -- sent WHOLE to a million-token free model")

    results: dict[str, Any] = {}
    for lens, (system, ask) in _LENSES.items():
        try:
            r = panel.ask("deep_audit", system,
                          f"=== DESK STATE ===\n{state}\n\n=== TASK ===\n{ask}",
                          max_tokens=1200, temperature=0.7)
        except panel.PanelExhausted as exc:
            results[lens] = {"panel_exhausted": str(exc)[:160]}
            print(f"\n  [{lens}] panel exhausted")
            continue
        except Exception as exc:
            results[lens] = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            print(f"\n  [{lens}] {type(exc).__name__}")
            continue
        rows = _parse(r.text)
        results[lens] = {"model": r.model,
                         "findings": [{"a": a, "b": b, "c": c} for a, b, c in rows],
                         "parsed": len(rows),
                         "unparseable": None if rows else "no delimited line; nothing stored"}
        print(f"\n  [{lens}] {r.model}  ({len(rows)} finding(s))")
        for a, b, c in rows:
            print(f"    {a[:46]}")
            print(f"      why: {b[:96]}")
            print(f"      do:  {c[:96]}")
        if not rows:
            print("    UNPARSEABLE -- nothing stored")

    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"),
                               "state_chars": total, "state_sizes": sizes,
                               "results": results,
                               "authority": "REPORT ONLY -- every suggestion faces the gauntlet"},
                              indent=1, default=str), "utf-8")
    print(f"\n  -> {OUT}")
    got = sum(1 for v in results.values() if v.get("findings"))
    return 0 if got else 1


if __name__ == "__main__":
    raise SystemExit(main())
