#!/usr/bin/env python3
"""LOOK UP ANY LESSON, FROM ANY SESSION. Retention is 100%; injection never can be.

    "all lessons get stored there sessions can check it every session time etc n remember all
     memory again its so simple ... 100 percent lesson absorbtion 0 forgetting"
                                                        -- the principal, 2026-09-06

TWO DIFFERENT NUMBERS, AND ONLY ONE OF THEM CAN BE 100%.

    RETENTION   how much of what the desk has learned still exists and is reachable.
                This MUST be 100%. A lesson that cannot be found is forgotten however
                faithfully it is stored, and that is the failure the principal named.

    INJECTION   how much of it fits in one organ's context at the moment it works.
                `desk_memory.BUDGET_CHARS` is 12,000 against a 228-lesson corpus, so this is
                structurally ~10-15% and no storage format changes it. Nor should it: a lesson
                about shared worktrees does not belong in a gauntlet's context, and injecting it
                there dilutes the lessons that do apply (L1.37).

The gap between them was the real defect. Injection gave every organ its most relevant lessons
and there was NO WAY to reach the other 200 -- so from inside a session, a lesson that had not
been selected was indistinguishable from a lesson that did not exist. This closes that: selection
still decides what arrives unasked, and this decides what can be ASKED FOR, which is everything.

    python scripts/lessons.py stash worktree        # search
    python scripts/lessons.py --id L0423            # one lesson, in full
    python scripts/lessons.py --tag governance      # by tag
    python scripts/lessons.py --orphans             # lessons no organ is ever shown
    python scripts/lessons.py --all                 # the whole corpus, ids and one-liners

`--orphans` is the one that matters for "0 forgetting": it lists lessons that reach no organ
through routing, which are the ones actually at risk of being lost. They are not deleted and not
hidden; they are simply never volunteered, so they must be findable on purpose.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import desk_memory as dm  # noqa: E402

_STOP = {"the", "a", "an", "and", "or", "is", "was", "to", "of", "in", "on", "for", "that",
         "this", "it", "its", "as", "at", "by", "with", "not", "no", "from"}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_]{3,}", str(text).lower()) if w not in _STOP}


def search(query: str, limit: int = 12) -> list[tuple[float, object]]:
    """Rank the WHOLE corpus against a query. Never truncated by any context budget.

    Scored on the same axes routing uses -- body terms, tag terms weighted higher -- so a search
    surfaces what routing would have surfaced had there been room, rather than a second and
    differently-opinionated notion of relevance.
    """
    want = _terms(query)
    if not want:
        return []
    out = []
    for item in dm.load():
        body = _terms(f"{item.lesson} {item.evidence}")
        tags = _terms(" ".join(item.tags))
        score = len(body & want) + 3 * len(tags & want)
        if str(getattr(item, "id", "")).lower() in {w.lower() for w in query.split()}:
            score += 50
        if score:
            out.append((float(score), item))
    out.sort(key=lambda kv: (-kv[0], str(getattr(kv[1], "id", ""))))
    return out[:limit]


def orphans() -> tuple[list[object], list[object]]:
    """(unreached, lost) -- lessons routing never volunteers, and the strict subset it drops.

    These are not deleted and not hidden. They are simply never offered, which from inside a
    session is operationally identical to being forgotten: an organ cannot ask for a lesson it
    has no way to learn exists. Naming them is what makes the difference recoverable.

    `reach()` RETURNS {reached, unreached, lost}, NOT organ -> lessons. The first draft of this
    function iterated its values and unioned them, so every unreached lesson was counted as
    reached and the command cheerfully reported ZERO orphans against a corpus with 69 -- an
    answer that looked like perfect health and was produced by a bug. It also swallowed any
    exception into an empty list, which prints identically to a genuine zero. Both are fixed:
    the fields are read by name, and a failure raises rather than reading as a clean bill.
    """
    r = dm.reach()
    if not isinstance(r, dict) or "unreached" not in r:
        raise RuntimeError(
            f"desk_memory.reach() returned {sorted(r) if isinstance(r, dict) else type(r)}, "
            "which does not carry `unreached` -- this command cannot tell a fully-routed corpus "
            "from a broken query, and reporting zero orphans from that would be a clean verdict "
            "manufactured from a gap")
    return list(r.get("unreached") or []), list(r.get("lost") or [])


def _render(item, full: bool = False) -> str:
    lid = getattr(item, "id", "?")
    lesson = " ".join(str(getattr(item, "lesson", "")).split())
    head = f"{lid}  {lesson}"
    if not full:
        return head if len(head) <= 160 else head[:157] + "..."
    lines = [head, ""]
    ev = " ".join(str(getattr(item, "evidence", "") or "").split())
    if ev:
        lines += ["  EVIDENCE: " + ev, ""]
    if getattr(item, "enforced_by", None):
        lines.append(f"  ENFORCED BY: {item.enforced_by}")
    if getattr(item, "tags", None):
        lines.append(f"  TAGS: {' '.join(item.tags)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Look up desk lessons. Retention is 100%.")
    ap.add_argument("query", nargs="*", help="free-text search across the whole corpus")
    ap.add_argument("--id", help="show one lesson in full")
    ap.add_argument("--tag", help="every lesson carrying this tag")
    ap.add_argument("--orphans", action="store_true",
                    help="lessons routing never shows any organ")
    ap.add_argument("--all", action="store_true", help="the entire corpus")
    ap.add_argument("-n", type=int, default=12, help="max results (default 12)")
    a = ap.parse_args(argv)

    corpus = dm.load()
    if a.id:
        hit = [i for i in corpus if str(getattr(i, "id", "")).lower() == a.id.lower()]
        if not hit:
            print(f"no lesson with id {a.id!r} in {len(corpus)} lessons")
            return 1
        print(_render(hit[0], full=True))
        return 0
    if a.tag:
        hits = [i for i in corpus if a.tag.lower() in {t.lower() for t in (i.tags or ())}]
        print(f"{len(hits)} lesson(s) tagged #{a.tag}\n")
        for i in hits:
            print("  " + _render(i))
        return 0
    if a.orphans:
        # UNPACKED, not iterated. `orphans()` returns a (unreached, lost) TUPLE and the first
        # draft looped over it directly -- so `len()` was 2, the number of LISTS, and each
        # "lesson" rendered as a bare `?` because a list has no id. It reported "2 of 228
        # orphans" against a corpus with none, which is a wrong answer that looks like a real one.
        unreached, lost = orphans()
        print(f"{len(unreached)} of {len(corpus)} lessons reach no organ through routing; "
              f"{len(lost)} are dropped outright.")
        print("They are retained and searchable; they are simply never volunteered.\n")
        for label, group in (("UNREACHED", unreached), ("LOST", lost)):
            for i in group:
                print(f"  {label:9} " + _render(i))
        if not unreached and not lost:
            print("  none -- every lesson the desk has paid for reaches at least one organ")
        return 0
    if a.all:
        print(f"{len(corpus)} lessons\n")
        for i in corpus:
            print("  " + _render(i))
        return 0
    if not a.query:
        ap.print_help()
        print(f"\ncorpus: {len(corpus)} lessons, all searchable, none truncated by any budget")
        return 0

    hits = search(" ".join(a.query), limit=a.n)
    if not hits:
        # ABSENCE IS NEVER A PASS. "No match" must not read as "no such lesson exists" -- the
        # corpus size is printed so the reader can tell a miss from an empty corpus.
        print(f"no lesson matched {' '.join(a.query)!r} across all {len(corpus)} lessons")
        return 1
    print(f"{len(hits)} of {len(corpus)} lessons matched {' '.join(a.query)!r}\n")
    for score, item in hits:
        print(f"  [{score:5.1f}] " + _render(item))
    return 0


if __name__ == "__main__":
    sys.exit(main())
