#!/usr/bin/env python3
"""THE CHIEF RESEARCH OFFICER, on a cadence.

PRINCIPAL ORDER (2026-08-01): GPT is the desk's permanent CRO -- it thinks, criticises, discovers,
prioritises and recommends, and it does NOT implement. Implementation agents execute the
highest-value validated recommendations. This organ is the CRO's runtime.

EACH CYCLE: assemble the desk's own measured artifacts, state the full standing mandate and the
geometric-growth objective with its fence, ask an INDEPENDENT model family to review the entire
desk, validate every answer against a contract it cannot talk its way around, and append the
survivors -- and the rejections -- to a ledger that owes dispositions.

WORKS DARK. With no seat configured it writes the complete briefing to docs/research/CRO_BRIEFING.md
and exits 0, so the principal can paste it into a chat UI and get the same review by hand. That is
how this desk's external panel ran its first two rounds. A cadenced organ that hard-fails on a
missing credential is an organ that gets disabled, and a disabled organ recommends nothing.

    python scripts/run_cro.py [--json] [--dry-run] [-n 12]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from libs.ops import llm_seat
from libs.research.cro_role import (
    MISSION,
    assemble_dossier,
    build_prompt,
    open_titles,
    parse,
    record,
    scorecard,
)

_ROOT = Path(__file__).resolve().parent.parent
_BRIEFING = _ROOT / "docs" / "research" / "CRO_BRIEFING.md"
_OUT = _ROOT / "data" / "cro_review.json"

_SYSTEM = (
    "You are the permanent Chief Research Officer of a quantitative trading desk. You think, "
    "criticise, discover, prioritise and recommend; you do not implement. You return JSON only, "
    "exactly as specified. You never exaggerate, never invent edge, and never assume "
    "profitability. You say plainly when the desk's own reasoning looks wrong -- agreeing for the "
    "sake of agreeing is the one thing that makes an independent seat worthless.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="assemble and write the briefing; never spend")
    ap.add_argument("-n", type=int, default=12, help="recommendations requested")
    args = ap.parse_args(argv)

    dossier = assemble_dossier()
    prompt = build_prompt(dossier, n=args.n)
    seat = llm_seat.primary_seat()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")

    doc: dict[str, object] = {
        "generated_utc": stamp,
        "mission": MISSION,
        "dossier_present": sorted((dossier.get("present") or {}).keys()),
        "dossier_missing": dossier.get("missing") or [],
        "seat": llm_seat.status(),
    }

    # DARK OR DRY: write the briefing and stop, exit 0. A missing credential is a known state of
    # the world, not a crash.
    if seat is None or args.dry_run:
        _write_briefing(prompt, dossier, stamp)
        doc["status"] = f"BRIEFING ONLY ({'dry-run' if args.dry_run else 'no seat configured'})"
        doc["briefing"] = str(_BRIEFING.relative_to(_ROOT))
        if not args.dry_run:
            doc["blocker"] = (
                "export OPENROUTER_API_KEY in the environment to seat the CRO -- one key "
                "reaches every model family and auto-upgrades across the market rather than "
                "within a single vendor. The same variable "
                "lights eleven other dark organs (run_external_panel, strategic_director, "
                "llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, "
                "collector_author, deep_review, run_micro_audit, refresh_panel_roster, "
                "llm_blind_researcher). Until then paste docs/research/CRO_BRIEFING.md into a "
                "chat UI by hand -- the briefing is the identical prompt the seat would receive.")
        _write(doc)
        _emit(doc, args.json)
        return 0

    # PUSHED, NEVER FIRST-ANSWER (principal 2026-08-04: "cheap llm tricks of asking ... is this
    # it or is this maxxed yet ... till they give up"). The dossier is the expensive half of the
    # call and it is already paid for; each rung re-uses the whole conversation and costs output
    # tokens only. push_rounds stops on MEASURED exhaustion (novelty floor), surrender, or the
    # cap -- so "the CRO gave up" is a number in the artifact, not a feeling.
    def _ask(msgs: list[dict[str, str]]) -> str:
        t, e = llm_seat.chat_messages(msgs, seat=seat, max_tokens=16000)
        if e:
            raise RuntimeError(e)
        return t

    from libs.llm.push import push_rounds
    try:
        pushed = push_rounds(_ask, _SYSTEM, prompt)
    except RuntimeError as exc:
        _write_briefing(prompt, dossier, stamp)
        doc.update({"status": "SEAT ERROR", "error": str(exc),
                    "briefing": str(_BRIEFING.relative_to(_ROOT))})
        _write(doc)
        _emit(doc, args.json)
        return 0                      # cadenced organ: report and survive

    doc["push"] = {"rounds": pushed.rounds, "stop_reason": pushed.stop_reason,
                   "novelties": pushed.novelties}
    # Each round is parsed SEPARATELY (each returns its own JSON array) and merged with the
    # duplicate fence doing the dedup -- titles already accepted in an earlier round are OPEN by
    # the time the later round is parsed, so a rung that re-states round 1 converts to nothing.
    text = pushed.texts[0]
    result = parse(text)
    for extra in pushed.texts[1:]:
        seen = {r.title for r in result.accepted}
        more = parse(extra, known_open=(open_titles() | {t.lower() for t in seen}))
        result.accepted.extend(more.accepted)
        result.rejected.extend(more.rejected)
        result.parse_errors.extend(more.parse_errors)
    model, _ = llm_seat.discover_model(seat)
    doc.update({
        "status": "MEASURED",
        "model": model,
        "summary": result.summary(),
        "n_recorded": record(result, seat=seat.name, model=model),
        "deliverable_coverage": result.deliverable_coverage(),
        "accepted": [asdict(r) for r in result.accepted],
        "rejected": [{"title": r.title, "lever": r.lever, "why": r.rejected_reason}
                     for r in result.rejected],
        "parse_errors": result.parse_errors,
        "scorecard": scorecard(),
    })
    _write(doc)
    _emit(doc, args.json)
    return 0


def _write_briefing(prompt: str, dossier: dict[str, object], stamp: str) -> None:
    """The manual path, carrying the IDENTICAL prompt the seat would receive -- so a hand-run
    review is comparable to an automated one rather than a different question asked differently."""
    missing = dossier.get("missing") or []
    _BRIEFING.parent.mkdir(parents=True, exist_ok=True)
    _BRIEFING.write_text(
        f"# CRO briefing — {stamp}\n\n"
        "Generated by `scripts/run_cro.py`. Paste everything below the rule into a chat UI (any "
        "frontier model from a family other than the desk's own) and feed the JSON array it "
        "returns back through `libs.research.cro_role.parse`.\n\n"
        f"Dossier artifacts missing this cycle: {', '.join(map(str, missing)) or 'none'}\n\n"
        "---\n\n" + prompt + "\n", "utf-8")


def _write(doc: dict[str, object]) -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")


def _emit(doc: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(doc, indent=2, default=str))
        return
    print(f"CRO: {doc.get('status')}")
    seat = doc.get("seat")
    if isinstance(seat, dict):
        print(f"  seats {seat.get('n_seats')}  spend ${seat.get('month_spend_usd')} "
              f"of ${seat.get('monthly_cap_usd')}")
    missing = doc.get("dossier_missing")
    if isinstance(missing, list) and missing:
        print(f"  dossier missing ({len(missing)}): {', '.join(map(str, missing[:6]))}")
    for key in ("blocker", "error"):
        if doc.get(key):
            print(f"  {key.upper()}: {doc[key]}")
    acc = doc.get("accepted")
    if isinstance(acc, list):
        for i, r in enumerate(acc, 1):
            if isinstance(r, dict):
                print(f"  {i}. [{r.get('deliverable')}|{r.get('lever')}|{r.get('kind')}|"
                      f"{r.get('evidence_class')}/{r.get('confidence')}] {r.get('title')}")
    rej = doc.get("rejected")
    if isinstance(rej, list) and rej:
        for r in rej:
            if isinstance(r, dict):
                print(f"  REJECTED [{r.get('lever')}] {r.get('title')}: {r.get('why')}")
    sc = doc.get("scorecard")
    if isinstance(sc, dict) and sc.get("verdict"):
        print(f"  scorecard: {sc['verdict']}")


if __name__ == "__main__":
    sys.exit(main())
