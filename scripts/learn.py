#!/usr/bin/env python3
"""RECORD AND INJECT WHAT THE DESK HAS LEARNED -- the write side of libs/research/desk_memory.

The model's weights never change between sessions. Everything this desk works out today is gone
tomorrow unless it is written somewhere an organ READS AT RUNTIME. This is that write path, and
`render` is what ops/brain_env.sh injects into every organ.

    python scripts/learn.py render                 # the injected corpus (stdout) + overflow (stderr)
    python scripts/learn.py render --organ cro_ai  # the same budget, routed to one organ's subject
    python scripts/learn.py add --cost blind \
        --lesson "..." --evidence "..." [--tag x --source session]
    python scripts/learn.py recur L0005            # this lesson was re-learned -- promote it
    python scripts/learn.py graduate L0036 tests/t.py::test_x   # a test now enforces it
    python scripts/learn.py audit [--json]         # is memory reaching the organs?

THE ONE COMMAND THAT MATTERS MOST IS `recur`. Re-learning is the desk telling itself which
lessons do not stick, and the ranking turns that straight into injected context. A lesson learned
four times outranks a one-off by 3x -- automatically, with nobody deciding to prioritise it.

`add` REFUSES a lesson with no evidence. A corpus of unevidenced opinions injected into every
organ is strictly worse than no corpus: it launders guesses into doctrine, at which point the
desk cannot tell its measurements from its assumptions.

`graduate` IS WHAT KEEPS THIS FROM PLATEAUING, and it is the answer to "does this actually get
better forever". A fixed budget with a growing ledger saturates -- lesson 60 displaces lesson 40
and the desk stops accumulating even while it keeps learning. Graduation is the escape that is
not forgetting: convert a lesson from something an agent must READ AND REMEMBER into something a
TEST CHECKS MECHANICALLY. The property is then enforced forever at zero context cost, and the
budget it was using goes back to a lesson no test can catch. Every lesson that CAN become a test
SHOULD, and the ones left in the corpus are exactly the judgement calls a machine cannot make.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.desk_memory import (  # noqa: E402
    BUDGET_CHARS,
    COST_WEIGHT,
    LEDGER,
    append,
    broken_enforcement,
    bump,
    corpus,
    load,
    next_id,
    validate_row,
)

#: Every file that must carry the corpus for it to reach a running organ. brain_env.sh is the
#: single choke point -- every miner runner sources it -- so this is a short list on purpose.
_INJECTION_SITES = ("ops/brain_env.sh",)
_MARK = "scripts/learn.py render"


def cmd_render(organ: str = "") -> int:
    """The corpus this organ should read.

    `--organ` IS WHAT MAKES THE LEDGER SCALE. Without it every organ gets the same top-of-ranking
    lessons and the ledger saturates at whatever fits in 12,000 chars -- 25 lessons out of 228,
    measured 2026-09-05. With it the same 12,000 chars are spent on the lessons that apply to THIS
    organ, and 141 of the 228 reach somebody. No organ reads one character more than before.

    An unknown or empty organ renders the global ranking, which is exactly the old behaviour, so a
    caller that has not been taught to pass one is degraded rather than broken.
    """
    text, dropped = corpus(organ=organ)
    sys.stdout.write(text)
    if dropped:
        # NEVER silent. A memory layer that quietly truncated would recreate the exact defect it
        # exists to fix -- the desk believing it carries knowledge it does not carry.
        who = f" for organ {organ!r}" if organ else ""
        sys.stderr.write(
            f"desk_memory: {len(dropped)} lesson(s) did not fit the {BUDGET_CHARS}-char budget"
            f"{who} and are NOT injected: {', '.join(item.id for item in dropped)}\n")
    return 0


def would_reach_organs(row: dict[str, Any]) -> tuple[bool, list[str]]:
    """Would this lesson be INJECTED, and which currently-injected lessons would it displace?

    Answered by running the REAL packer over a scratch ledger containing the existing rows plus
    this candidate -- never by re-deriving the arithmetic here. The budget is a strict-rank pack
    with a latch (see corpus()), so "does it fit" is not a question about this lesson's length: a
    lesson can be short and still be dropped because a longer, higher-scoring one ahead of it
    closed the latch. Any local estimate of "free budget" would be wrong in exactly the cases
    that matter, and would be wrong SILENTLY.

    `root` is pinned to the repo so `enforced_by` references still resolve out of the scratch
    file; without it every graduated lesson would lose its discount and the probe would answer a
    different question from the one asked.
    """
    _text, over_before = corpus()
    injected_before = {i.id for i in load()} - {d.id for d in over_before}
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / "desk_lessons.jsonl"
        existing = LEDGER.read_text("utf-8") if LEDGER.exists() else ""
        probe.write_text(existing + json.dumps(row, ensure_ascii=False) + "\n", "utf-8")
        _text, dropped = corpus(path=probe, root=_ROOT)
    dropped_ids = {d.id for d in dropped}
    displaced = sorted(injected_before & dropped_ids)
    return row["id"] not in dropped_ids, displaced


def cmd_add(a: argparse.Namespace) -> int:
    row: dict[str, Any] = {
        "id": next_id(), "learned": time.strftime("%Y-%m-%d", time.gmtime()),
        "cost": a.cost, "recurrence": 1, "lesson": a.lesson, "evidence": a.evidence,
        "tags": a.tag or [], "source": a.source,
    }
    if a.enforced_by:
        row["enforced_by"] = a.enforced_by
    if a.accept_uninjected:
        row["accepted_uninjected"] = a.accept_uninjected
    problems = validate_row(row)
    if problems:
        for p in problems:
            print(f"REFUSED: {p}", file=sys.stderr)
        return 1

    # THE CHOICE IS FORCED HERE, AT WRITE TIME, BECAUSE NOWHERE ELSE EVER FORCED IT (R0346).
    # Demonstrated 2026-08-01 with an unusually clean causal chain: L0057 ("a red pytest leg can
    # mean zero tests ran") was recorded, its own commit message OBSERVED that it rendered 659
    # chars against 156 chars of free budget and so "reaches no organ" -- and the class it warned
    # about then recurred THREE times within 21 minutes, killing pytest collection repo-wide each
    # time. The overflow was visible at render and audit time and at neither of those moments was
    # anyone deciding anything. A lesson that does not fit is a WISH, and the ledger can tell at
    # the exact moment it is written.
    fits, displaced = would_reach_organs(row)
    if not fits and not a.enforced_by and not a.accept_uninjected:
        print(f"REFUSED: this lesson does NOT fit the {BUDGET_CHARS}-char injected budget -- it "
              f"would be recorded and reach NO organ, which is a diary entry, not memory.\n"
              f"  Choose one, and the choice is recorded on the row:\n"
              f"    --enforced-by tests/x.py::test_y   a test enforces it mechanically, forever, "
              f"at ~0 context cost (PREFERRED -- this is how the corpus keeps compounding)\n"
              f"    --accept-uninjected \"<why no test is possible>\"   an explicit, auditable "
              f"decision that this one rides in the ledger only\n"
              f"  RAISING THE BUDGET IS NOT ON THAT LIST: that is how the doctrine reached 95k.",
              file=sys.stderr)
        return 1

    rid = append(row)
    print(f"{rid} recorded ({a.cost}, weight {COST_WEIGHT[a.cost]})")
    if fits:
        print(f"  INJECTED: it reaches every organ through {_INJECTION_SITES[0]}.")
        for d in displaced:
            print(f"  DISPLACED {d} -- it outranked that lesson, which now reaches no organ. "
                  f"Graduating {d} to a test would buy its budget back.")
    elif a.enforced_by:
        verified = next((i for i in load() if i.id == rid), None)
        ok = verified is not None and verified.enforced_verified
        print(f"  NOT injected (over budget) but ENFORCED by {a.enforced_by} -- "
              f"{'verified on disk' if ok else 'WHICH DOES NOT RESOLVE'}.")
        if not ok:
            print(f"REFUSED-IN-PART: {a.enforced_by} does not name a real test, so this lesson is "
                  f"neither injected nor enforced. Fix the path with "
                  f"`scripts/learn.py graduate {rid} <test>`.", file=sys.stderr)
            return 1
    else:
        print(f"  NOT injected (over budget), accepted knowingly: {a.accept_uninjected}")
    return 0


def cmd_graduate(a: argparse.Namespace) -> int:
    """Attach a test to a lesson, verifying the test is REAL before granting the discount."""
    rows = LEDGER.read_text("utf-8").splitlines()
    out, found = [], False
    for line in rows:
        s = line.strip()
        if not s or s.startswith("#"):
            out.append(line)
            continue
        row = json.loads(s)
        if str(row.get("id")) == a.id:
            row["enforced_by"] = a.test
            found = True
            out.append(json.dumps(row, ensure_ascii=False))
        else:
            out.append(line)
    if not found:
        print(f"no lesson {a.id}", file=sys.stderr)
        return 1
    LEDGER.write_text("\n".join(out) + "\n", "utf-8")
    # Read back through load(), which VERIFIES the reference rather than trusting it.
    item = next((i for i in load() if i.id == a.id), None)
    if item is None or not item.enforced_verified:
        print(f"REFUSED: {a.test} does not resolve to a real test. The reference is recorded but "
              f"grants NO budget discount -- fix the path or the lesson silently leaves the "
              f"corpus while the ledger claims it is automated.", file=sys.stderr)
        return 1
    print(f"{a.id} graduated -> {a.test}\n  weight {item.score:.2f}; the property is now enforced "
          f"mechanically and its budget returns to a lesson no test can catch.")
    return 0


def cmd_recur(a: argparse.Namespace) -> int:
    n = bump(a.id)
    print(f"{a.id} re-learned -- recurrence now {n}. It will outrank one-off lessons of the same "
          f"cost class; a lesson that keeps recurring is the one worth the context.")
    return 0


def audit() -> dict[str, Any]:
    """Does the corpus actually REACH a running organ, and what is falling off the budget?

    Both halves matter. An uninjected corpus is a diary; a silently-overflowing one is a lie about
    what the desk carries.
    """
    text, dropped = corpus()
    items = load()
    sites = {}
    for rel in _INJECTION_SITES:
        p = _ROOT / rel
        sites[rel] = bool(p.exists() and _MARK in p.read_text("utf-8", errors="ignore"))
    by_cost: dict[str, int] = {}
    for item in items:
        by_cost[item.cost] = by_cost.get(item.cost, 0) + 1
    grad = [i for i in items if i.enforced_verified]
    broken = broken_enforcement()
    return {
        "n_graduated": len(grad),
        "graduated": [{"id": i.id, "test": i.enforced_by} for i in grad],
        "broken_enforcement": [{"id": i.id, "claims": i.enforced_by} for i in broken],
        "ledger": str(LEDGER.relative_to(_ROOT)), "n_active": len(items),
        "n_injected": len(items) - len(dropped), "n_dropped": len(dropped),
        "dropped_ids": [d.id for d in dropped],
        "chars": len(text), "budget": BUDGET_CHARS,
        "by_cost": by_cost,
        "most_relearned": [{"id": i.id, "recurrence": i.recurrence, "lesson": i.lesson[:90]}
                           for i in sorted(items, key=lambda x: -x.recurrence)[:5]],
        "injection_sites": sites,
        "reaching_organs": all(sites.values()) and bool(text) and not broken,
    }


def cmd_audit(a: argparse.Namespace) -> int:
    rep = audit()
    if a.json:
        print(json.dumps(rep, indent=2))
        return 0 if rep["reaching_organs"] else 1
    print(f"desk memory | {rep['n_active']} active lessons | {rep['chars']}/{rep['budget']} chars "
          f"injected | {rep['n_dropped']} over budget")
    print(f"  by cost: {rep['by_cost']}")
    print(f"  graduated to tests (enforced mechanically, ~0 context cost): {rep['n_graduated']}")
    for b in rep["broken_enforcement"]:
        print(f"  DEFECT: {b['id']} claims enforcement by {b['claims']} which does not resolve -- "
              "the ledger believes this is automated and it is not")
    print("  most re-learned (these are where the desk repeatedly fails):")
    for m in rep["most_relearned"]:
        print(f"    x{m['recurrence']}  {m['id']}  {m['lesson']}...")
    for site, ok in rep["injection_sites"].items():
        print(f"  {'REACHES' if ok else 'NOT WIRED'}  {site}")
    if rep["n_dropped"]:
        print(f"  OVER BUDGET, not injected: {', '.join(rep['dropped_ids'])}")
        print("    Raising the budget is the wrong reflex -- that is how the doctrine reached "
              "95k. Retire a lesson whose falsifier arrived, or accept the ranking.")
    if not rep["reaching_organs"]:
        print("  DEFECT: the corpus does not reach a running organ. Knowledge that is not "
              "injected at runtime changes no behaviour anywhere.")
    return 0 if rep["reaching_organs"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ren = sub.add_parser("render", help="print the injected corpus")
    ren.add_argument("--organ", default="", help="route the corpus to this organ's subject "
                                                 "(ops/run_<organ>.sh); empty = global ranking")
    add = sub.add_parser("add", help="record a durable lesson (evidence is mandatory)")
    add.add_argument("--cost", required=True, choices=sorted(COST_WEIGHT),
                     help="what it cost the desk NOT to know this")
    add.add_argument("--lesson", required=True, help="what to DO differently, imperative")
    add.add_argument("--evidence", required=True, help="file, number or date that proves it")
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--source", default="session")
    # THE TWO WAYS PAST A LESSON THAT DOES NOT FIT, and there is deliberately no third. Raising
    # BUDGET_CHARS is the reflex that took the doctrine file to 95k, so it is not offered here.
    add.add_argument("--enforced-by", default="",
                     help="tests/x.py::test_y -- a test enforces this mechanically (PREFERRED: "
                          "the property is kept forever at ~0 context cost)")
    add.add_argument("--accept-uninjected", default="",
                     help="record an explicit decision that this lesson rides in the ledger only "
                          "because no test can catch it -- auditable, never silent")
    rec = sub.add_parser("recur", help="this lesson was re-learned -- promote it")
    rec.add_argument("id")
    gr = sub.add_parser("graduate", help="a test now enforces this lesson mechanically")
    gr.add_argument("id")
    gr.add_argument("test", help="tests/path.py::test_name")
    aud = sub.add_parser("audit", help="is memory reaching the organs?")
    aud.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "render":
        return cmd_render(getattr(a, "organ", "") or "")
    if a.cmd == "add":
        return cmd_add(a)
    if a.cmd == "recur":
        return cmd_recur(a)
    if a.cmd == "graduate":
        return cmd_graduate(a)
    return cmd_audit(a)


if __name__ == "__main__":
    raise SystemExit(main())
