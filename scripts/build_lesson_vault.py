#!/usr/bin/env python3
"""AN OBSIDIAN VAULT OF THE DESK'S LESSONS -- a DERIVED VIEW, never the source of truth.

WHY A VIEW AND NOT A MIGRATION (principal 2026-09-06: "why don't you make an obsidian vault for
the self improvement lessons so its 100 percent absorption unless its a worse solution").

The honest answer is that a vault does not achieve 100% absorption, because absorption is not
limited by where the lessons are STORED. It is limited by the context an organ has to read them
in: `desk_memory.BUDGET_CHARS` is 12,000 and the corpus is 228 lessons. Moving those lessons from
one file into 228 files changes the storage and leaves the budget exactly where it was -- the
selection problem is untouched, because something still has to choose which lessons enter a
prompt.

AND 100% ABSORPTION WOULD BE A REGRESSION, not the goal. A lesson about never stashing in a
shared worktree does not belong in a gauntlet's context, and injecting it there does not make the
gauntlet wiser -- it dilutes the lessons that do apply. That is L1.37: a signal present in every
context is one every reader learns to skip. The current reach of ~70% is a ROUTING result, not a
storage limit: the missing 30% is lessons deliberately not shown to organs they do not govern.

So a vault is not a worse solution and it is not a better one. It is an ORTHOGONAL one, and it
is genuinely additive in the place the JSONL is weakest: a human cannot read `desk_lessons.jsonl`.
It has no backlinks, no graph, no way to see that eleven separate lessons are all instances of
"absence scored as a pass". This exporter gives that surface without giving up the structured
fields retrieval needs.

THE DIRECTION IS ONE-WAY ON PURPOSE. `docs/desk_lessons.jsonl` stays canonical; the vault is
regenerated from it and may be deleted at any time without losing anything. Two writable copies
of one corpus is how they drift, and a lesson corpus that disagrees with itself is worse than a
smaller one that does not.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "docs" / "desk_lessons.jsonl"
VAULT = ROOT / "docs" / "lesson_vault"

#: Lessons sharing this many significant terms are cross-linked as related. Low enough to find
#: real neighbours, high enough that a note does not link to eighty others and become a hub that
#: says nothing.
LINK_MIN_SHARED = 4

_STOP = {"the", "a", "an", "and", "or", "is", "was", "were", "be", "been", "to", "of", "in",
         "on", "for", "that", "this", "it", "its", "as", "at", "by", "with", "not", "no",
         "which", "what", "when", "so", "but", "from", "had", "has", "have", "would", "will"}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_]{4,}", str(text).lower()) if w not in _STOP}


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "")).strip("-").lower()[:60]
    return s or fallback


def load() -> list[dict[str, Any]]:
    rows = []
    try:
        with LESSONS.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def build(out: Path | None = None) -> dict[str, Any]:
    dest = out or VAULT
    rows = load()
    if not rows:
        # ABSENCE IS NEVER A PASS. An empty corpus must not produce a tidy empty vault that reads
        # like a healthy one.
        return {"lessons": 0, "written": 0,
                "why": f"{LESSONS} holds no readable lesson -- nothing was written"}

    notes = []
    for i, r in enumerate(rows):
        lid = str(r.get("id") or f"L{i:04d}")
        title = f"{lid} {str(r.get('lesson') or '')[:70]}".strip()
        notes.append({"row": r, "id": lid, "file": _slug(title, lid),
                      "terms": _terms(f"{r.get('lesson')} {r.get('evidence')}"),
                      "tags": [str(t) for t in (r.get("tags") or [])]})

    # Cross-links by shared vocabulary. Computed once, both directions, so the graph is symmetric
    # -- a one-way link in Obsidian shows as an unlinked mention and is easy to miss.
    for a in notes:
        a["links"] = sorted(
            b["file"] for b in notes
            if b is not a and len(a["terms"] & b["terms"]) >= LINK_MIN_SHARED)[:8]

    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.md"):
        old.unlink()

    written = 0
    for n in notes:
        r = n["row"]
        fm = {"id": n["id"], "cost": r.get("cost_class") or r.get("cost"),
              "tags": n["tags"], "enforced_by": r.get("enforced_by"),
              "enforcement_retired": r.get("enforcement_retired")}
        lines = ["---"]
        for k, v in fm.items():
            if v not in (None, "", [], {}):
                lines.append(f"{k}: {json.dumps(v) if isinstance(v, list) else v}")
        lines += ["---", "", f"# {n['id']}", "", str(r.get("lesson") or "").strip(), ""]
        if r.get("evidence"):
            lines += ["## Evidence", "", str(r["evidence"]).strip(), ""]
        if r.get("enforced_by"):
            lines += ["## Enforced by", "", f"`{r['enforced_by']}`", ""]
        if n["tags"]:
            lines += ["## Tags", "", " ".join(f"#{t}" for t in n["tags"]), ""]
        if n["links"]:
            lines += ["## Related", ""] + [f"- [[{lnk}]]" for lnk in n["links"]] + [""]
        (dest / f"{n['file']}.md").write_text("\n".join(lines), "utf-8")
        written += 1

    tag_counts = Counter(t for n in notes for t in n["tags"])
    index = ["# Desk lessons", "",
             f"{len(notes)} lessons, generated from `docs/desk_lessons.jsonl`.", "",
             "> [!warning] This vault is a DERIVED VIEW.",
             "> `docs/desk_lessons.jsonl` is the source of truth and the only thing organs read.",
             "> Edits made here are overwritten on the next build. Two writable copies of one",
             "> corpus is how they drift, and a lesson corpus that disagrees with itself is",
             "> worse than a smaller one that does not.", "",
             "## Why this is not how lessons reach an organ", "",
             "Absorption is limited by CONTEXT, not storage: `desk_memory.BUDGET_CHARS` is 12,000",
             "against a 228-lesson corpus, and moving the corpus into 228 files leaves that",
             "budget exactly where it was. Full absorption would also be a regression -- a lesson",
             "about shared worktrees does not belong in a gauntlet's context, and injecting it",
             "there dilutes the lessons that do apply.", "",
             "## Tags", ""]
    index += [f"- #{t} ({c})" for t, c in tag_counts.most_common(30)]
    index += ["", "## All lessons", ""]
    index += [f"- [[{n['file']}]]" for n in notes]
    (dest / "INDEX.md").write_text("\n".join(index), "utf-8")

    linked = sum(1 for n in notes if n["links"])
    return {"lessons": len(notes), "written": written,
            "with_links": linked, "orphans": len(notes) - linked,
            "tags": len(tag_counts), "path": str(dest.relative_to(ROOT))}


def main(argv: list[str] | None = None) -> int:
    doc = build()
    if not doc.get("written"):
        print(f"lesson vault: {doc.get('why')}")
        return 1
    print(f"lesson vault: {doc['written']} note(s) -> {doc['path']}  "
          f"({doc['with_links']} cross-linked, {doc['orphans']} orphan, {doc['tags']} tags)")
    print("   source of truth stays docs/desk_lessons.jsonl; this view is regenerated, "
          "never edited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
