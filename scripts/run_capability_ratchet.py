#!/usr/bin/env python3
"""CAPABILITY RATCHET (R0104) -- score every aspect of the desk 0-10, and let the score only rise.

THE ORDER THIS ENFORCES. The principal's standing order is that every aspect of this desk is
pushed toward 10/10 every day, non-exhaustively. Before this organ that rating lived in
conversation only: it was asserted, never recorded, so it could not ratchet, could not regress
visibly, and could not name what was holding it down. This writes it to disk with a high-water
mark per aspect, exactly as libs/doctrine/ratchet.py does for constitutional aggression.

WHAT IT PRINTS AND WHY THAT IS THE PRODUCT. The number is the cheap part. Every aspect carries a
BINDING CONSTRAINT -- the specific, quantified next thing that buys one more point ("+5 organs
producing (19 -> 24 of 42)") -- because "what is stopping this aspect from being one point higher"
is the only output a reader can act on the same morning. Above them all sits ONE desk-wide binding
constraint: the single lowest-scoring component anywhere on the desk, named with its artifact. A
list of thirty constraints is a list nobody works; one is an instruction.

THE TAXONOMY IS DELIBERATELY WIDE, and it only ever widens. The headline aspects (validation, risk,
execution, alpha) are the ones anybody would think to grade. The rest -- the pager between
incidents, cost-model freshness, tape clock provenance, seat credentials, dependency drift, backup
restore drills, mutation BREADTH as distinct from kill rate, scheduler manifest drift, permission
hygiene -- are the ones that actually take desks down, precisely because nobody grades them. The
standing order says every aspect; a taxonomy that stops at the interesting ones is the order being
followed where it is comfortable.

STATUSES (fail LOUD, never advisory):
  REGRESSED  an aspect scored below its own high-water mark, or a component that used to measure
             went dark. Exit 2. A FALL IS A DEFECT AND CARRIES A NAMED CAUSE: which component,
             from what to what, out of which artifact. A fall the component marks cannot explain
             is reported as an UNEXPLAINED fall rather than accepted -- silence is never the
             verdict.
  STALLED    no aspect has set a new best in STALL_DAYS. Exit 2. The order is daily; a week of
             nothing is the order not being followed. Every flatlined aspect prints its binding
             constraint, so the fix is already on the screen.
  WIDENED    an aspect's mean fell purely because it now grades MORE components, with nothing that
             was already graded getting worse. Exit 0, and NOT a defect: a gate that fires when
             the desk measures more trains everyone to ignore it (the lesson check_ratchets.py
             already learned with per-target mutation floors). The old high-water mark is KEPT and
             printed beside today's reading -- it was earned over a narrower set.
  FLATLINE   no movement this run, which is normal for a single day. Exit 0, and every aspect
             still names its constraint -- that list IS the day's queue.
  RAISED     at least one aspect set a new best. Exit 0.

UNMEASURED IS NEVER OK AND NEVER A FAILURE. It is its own state, printed in its own block with the
reason and the artifact that would settle it (L1.28a, scripts/check_clock_provenance.py). Nothing
here scores an absent measurement as 0 or as 10.

WHERE THE RECORD LIVES, stated because it is a real limitation. data/CAPABILITY_RATCHET.json is
gitignored like the rest of data/, so `rm` resets the marks -- unlike the findings ratchet, which
lives in docs/ for exactly that reason. The mitigation here is VISIBILITY, not silence: the
artifact carries `first_recorded`, and a run that finds no prior record says so in capitals rather
than quietly starting the history again from today's reading.

    python scripts/run_capability_ratchet.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block -- a governance fault must never
# silence the organ that measures whether the desk is getting better.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.capability_ratchet import (  # noqa: E402
    ARTIFACT_PATH,
    build_artifact,
    load_marks,
    ratchet,
    read_capability,
)


def run(root: Path, now: datetime | None = None) -> dict[str, object]:
    """Read the desk, ratchet the marks, return the artifact. Pure of IO side effects except the
    read -- the caller decides whether to persist, so tests can run the whole organ on a tmp tree.
    """
    at = now if now is not None else datetime.now(tz=UTC)
    # ONE instant for the whole run: the aspects' staleness judgements and the ratchet's stall
    # clock must agree, or an artifact can be fresh to one half of the organ and stale to the
    # other within the same report.
    aspects = read_capability(root, at)
    marks = load_marks(root / ARTIFACT_PATH)
    new_marks, verdicts, status = ratchet(aspects, marks, at)
    # The artifact publishes the marks AFTER the raise, so today's reading and today's record are
    # the same document -- a reader never has to diff two files to know where the desk stands.
    return build_artifact(aspects, new_marks, verdicts, status, at)


def _table(rep: dict[str, object]) -> str:
    aspects = rep.get("aspects")
    rows = aspects if isinstance(aspects, list) else []
    out: list[str] = [
        f"CAPABILITY RATCHET (R0104): {rep.get('status')} -- "
        f"{rep.get('n_measured')}/{rep.get('n_aspects')} aspects measured, mean "
        f"{rep.get('measured_mean')} of {rep.get('scale_max')} over the measured ones; "
        f"{rep.get('n_raises')} raise(s) since {rep.get('first_recorded') or 'NO PRIOR RECORD'}",
        f"{'aspect':<24} {'now':>5} {'best':>5}  {'movement':<10} what is stopping the next point",
        "-" * 118,
    ]
    for r in rows:
        if not isinstance(r, dict):
            continue
        score = r.get("score")
        best = r.get("high_water")
        out.append(
            f"{r.get('key')!s:<24} "
            f"{('  --' if score is None else f'{float(score):5.1f}'):>5} "
            f"{('  --' if best is None else f'{float(best):5.1f}'):>5}  "
            f"{r.get('movement')!s:<10} {str(r.get('cause'))[:74]}")
    bind = rep.get("binding_constraint")
    if isinstance(bind, dict):
        out.append("")
        if bind.get("state") == "MEASURED":
            out.append(
                f"DESK BINDING CONSTRAINT -- work this first: {bind.get('aspect')}."
                f"{bind.get('component')} at {float(bind.get('score') or 0.0):.1f}/10 "
                f"[{bind.get('artifact')}]")
            out.append(f"  {bind.get('constraint')}")
            out.append(f"  ({bind.get('n_unmeasured_components')} component(s) UNMEASURED and "
                       "therefore not eligible to be this minimum -- see the block below)")
        else:
            out.append(f"DESK BINDING CONSTRAINT: {bind.get('constraint')}")
    unmeasured = rep.get("unmeasured_components")
    if isinstance(unmeasured, list) and unmeasured:
        out.append("")
        out.append(f"UNMEASURED ({len(unmeasured)}) -- neither a 0 nor a 10; the desk does not know:")
        for u in unmeasured:
            if isinstance(u, dict):
                out.append(f"  {u.get('aspect')}.{u.get('component')} [{u.get('artifact')}] "
                           f"{str(u.get('why'))[:88]}")
    widened = rep.get("widened")
    if isinstance(widened, list) and widened:
        out.append("")
        out.append(f"WIDENED ({len(widened)}) -- NOT a defect: the aspect now grades more, and "
                   "nothing already graded got worse. The mark is kept:")
        for w in widened:
            if isinstance(w, dict):
                out.append(f"  {w.get('aspect')} {w.get('score')} (mark {w.get('high_water')}) "
                           f"{str(w.get('detail'))[:150]}")
    defects = rep.get("defects")
    if isinstance(defects, list) and defects:
        out.append("")
        out.append(f"FELL ({len(defects)}) -- a defect, never silently accepted:")
        for d in defects:
            if isinstance(d, dict):
                out.append(f"  {d.get('aspect')} [{d.get('movement')}] {d.get('cause')}")
    return "\n".join(out)


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0 (for queue refresh)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    had_record = (_ROOT / ARTIFACT_PATH).exists()
    rep = run(_ROOT)
    out = _ROOT / ARTIFACT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(_table(rep))
        if not had_record:
            print("\nNO PRIOR RECORD FOUND -- today's reading became the first high-water mark. "
                  "If this file existed yesterday it was DELETED, and the ratchet cannot detect a "
                  "fall from a mark it no longer has.")
        print(f"-> {out}")

    if args.report_only:
        return 0
    status = rep.get("status")
    return 2 if status in ("REGRESSED", "STALLED") else 0


if __name__ == "__main__":
    sys.exit(main())
