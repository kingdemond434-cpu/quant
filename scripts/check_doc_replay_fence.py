#!/usr/bin/env python3
"""Heal a tracked document that has been REPLAYED back to an older snapshot of itself.

MEASURED 2026-08-27. While this cycle was writing gap rows, `docs/GAP_REGISTER.md` in the working
tree was repeatedly reverted -- byte-for-byte -- to the blob committed at 02:45, roughly every two
minutes. Rows 150-156 were written FOUR times and vanished three of them; only committing within
the replay window kept them. The desk has fought this before: the commit the replayer restores is
itself titled "restore rows 146-150", so an earlier session lost the same rows the same way.

The money-path fence heals code by checking for marker strings. Documents have no markers to
check, and `GAP_REGISTER.md` is the desk's memory of every open defect -- a register silently
rolled back six hours is worse than a missing one, because it still looks authoritative.

THE TEST IS EXACT, AND IT CANNOT EAT A REAL EDIT. A replay reproduces a historical blob
BYTE-FOR-BYTE; a genuine new edit essentially never does. So:

    working blob != HEAD blob  AND  working blob appears in this file's own history
        -> a stale snapshot was replayed. Restore from HEAD and say so loudly.
    working blob != HEAD blob  AND  it appears nowhere in history
        -> somebody is editing. Leave it completely alone.

The one false positive is a DELIBERATE revert (`git checkout HEAD~1 -- file`), which is rare and
loud here rather than silent. That trade is the right way round: a deliberate revert is easy to
redo, and a silently-rolled-back register is not something anyone notices to redo.

Read-only unless it heals; never commits, never pushes -- restoring the working tree from HEAD is
enough, and committing on a shared tree is how a fence starts causing the damage it prevents.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "doc_replay_fence.json"
LOG = ROOT / "data" / "doc_replay_fence.log"

#: Append-mostly documents whose silent rollback costs the desk memory it cannot reconstruct.
#: Not every doc: only ones where an OLD copy still reads as authoritative.
GUARDED = (
    "docs/GAP_REGISTER.md",
    "docs/LAWS.md",
    "docs/RESEARCH.md",
    "docs/research/institutional_knowledge.md",
    "docs/recommendations.md",
)
HISTORY_DEPTH = 200


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)
    return out.stdout.strip()


def check(rel: str) -> dict[str, str] | None:
    """A finding when `rel` holds a replayed stale snapshot, else None."""
    path = ROOT / rel
    if not path.exists():
        return None
    head = _git("rev-parse", f"HEAD:{rel}")
    work = _git("hash-object", rel)
    if not head or not work or head == work:
        return None
    commits = _git("log", f"-{HISTORY_DEPTH}", "--format=%H", "--", rel).split()
    for sha in commits:
        if _git("rev-parse", f"{sha}:{rel}") == work:
            when = _git("log", "-1", "--format=%ci", sha)
            subj = _git("log", "-1", "--format=%s", sha)
            return {"file": rel, "replayed_from": sha, "committed_at": when, "subject": subj,
                    "head_blob": head, "working_blob": work}
    return None


def _lost_records(rel: str) -> list[str]:
    """Record ids present in HEAD and absent from the working copy, or [] when none are.

    WHY THIS AND NOT A SIZE THRESHOLD (2026-08-29). The empty-file rule added earlier today
    caught a working copy at 0 bytes. Hours later the same file came back at 114,688 bytes -- a
    truncated PREFIX holding 44 of 214 rows -- and sailed through, because a prefix is not empty
    and its blob appears nowhere in history, so the "somebody is editing" branch left it alone
    and the fence went quiet over a register missing 170 rows.

    A percentage threshold would be a guess. These files are LEDGERS and they have an exact
    invariant, already implemented and tested for the commit boundary in
    scripts/check_protected_records.py: a record that existed must still exist. Rewriting a row's
    text is ordinary work and passes untouched; making a row VANISH is the failure. Reusing that
    module rather than restating the rule is deliberate -- one definition of "record", enforced
    at both boundaries.

    Returns [] for any file whose shape that module cannot read, so an unknown format is governed
    by the empty rule alone and never by an invented one.
    """
    try:
        # THE SIBLING MODULE LIVES BESIDE THIS FILE, NOT BESIDE THE TREE BEING INSPECTED. ROOT is
        # the repo under examination and tests point it at a fixture with no scripts/ directory;
        # resolving the import through ROOT made the import fail there, `records` come back
        # empty, and the fence report "being edited" over a truncated ledger -- the exact bug
        # this function exists to fix, reintroduced by its own import line. Caught by its test.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from check_protected_records import records
    except Exception:
        return []
    head_txt = _git("show", f"HEAD:{rel}")
    try:
        work_txt = (ROOT / rel).read_text("utf-8", errors="replace")
    except OSError:
        return []
    lost = records(rel, head_txt) - records(rel, work_txt)
    return sorted(lost, key=lambda x: (len(x), x))


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    healed: list[dict[str, str]] = []
    emptied: list[dict[str, str]] = []
    edited: list[str] = []
    clean: list[str] = []
    failed: list[dict[str, str]] = []
    for rel in GUARDED:
        if not (ROOT / rel).exists():
            continue
        finding = check(rel)
        if finding is None:
            head = _git("rev-parse", f"HEAD:{rel}")
            work = _git("hash-object", rel)
            if head == work:
                clean.append(rel)
                continue
            # AN EMPTY WORKING COPY IS NEVER AN EDIT (2026-08-29). The rule above -- "appears
            # nowhere in history, so somebody is editing, leave it alone" -- is right for a real
            # edit and catastrophically wrong for a zero-byte file. Measured live this cycle:
            # docs/GAP_REGISTER.md sat at 0 bytes against a 495KB HEAD while this fence printed
            # "2 clean, 1 being edited, 0 replayed" and exited 0. Destroyed and being-edited must
            # never render identically (L1.28a). Nobody edits a document by emptying it, and if
            # they do, HEAD still holds every byte.
            lost_ids = _lost_records(rel)
            if lost_ids or ((ROOT / rel).stat().st_size == 0
                            and _git("cat-file", "-s", f"HEAD:{rel}") != "0"):
                subprocess.run(["git", "checkout", "HEAD", "--", rel], cwd=ROOT,
                               capture_output=True, text=True, timeout=120)
                emptied_ok = _git("hash-object", rel) == head
                what = (f"lost {len(lost_ids)} record(s) present in HEAD ("
                        + ", ".join(lost_ids[:8])
                        + (" ..." if len(lost_ids) > 8 else "") + ")") if lost_ids else \
                    "was 0 bytes against a non-empty HEAD"
                line = (f"{now} DESTROYED {rel}: working copy {what} -- restored from HEAD "
                        f"({'ok' if emptied_ok else 'HEAL FAILED'}). This is destruction, not an "
                        "edit, and it is not a replay either: the blob appears nowhere in the "
                        "file's history.")
                print(line)
                with LOG.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
                rec = {"file": rel,
                       "reason": (f"working copy lost {len(lost_ids)} record(s) from HEAD"
                                  if lost_ids else
                                  "empty working copy against non-empty HEAD"),
                       "lost_records": lost_ids[:50],
                       "head_blob": head, "working_blob": work,
                       "outcome": "HEALED" if emptied_ok else "HEAL_FAILED"}
                (emptied if emptied_ok else failed).append(rec)
                continue
            edited.append(rel)
            continue
        # HEAL: restore the working copy from HEAD. Nothing is lost -- the replayed content is a
        # historical blob, still reachable at the commit named in the finding.
        subprocess.run(["git", "checkout", "HEAD", "--", rel], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
        if _git("hash-object", rel) != finding["head_blob"]:
            finding["outcome"] = "HEAL_FAILED"
            failed.append(finding)
        else:
            finding["outcome"] = "HEALED"
            healed.append(finding)
        line = (f"{now} REPLAY HEALED {rel}: working tree held the blob committed "
                f"{finding['committed_at']} ({finding['replayed_from'][:8]} "
                f"\"{finding['subject'][:60]}\"); restored from HEAD")
        print(line)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # A SUCCESSFUL HEAL IS SUCCESS. Exiting non-zero for it would park this unit permanently in
    # `failed`, and a unit that is always failed is a unit nobody reads -- the exact desensitising
    # defect that let `qquant-shadow` fail every 30 minutes unnoticed. The heal is recorded in the
    # log and the artifact, which is where a monitor should read it. Non-zero is reserved for a
    # replay this fence could NOT heal, which is a real problem needing a human.
    doc: dict[str, object] = {"checked_at": now, "healed": healed, "heal_failed": failed,
                              "emptied": emptied,
                              "edited_by_someone": edited, "clean": clean,
                              "status": "HEAL_FAILED" if failed else
                                        ("EMPTIED" if emptied else
                                         ("HEALED" if healed else "OK"))}
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    if not healed and not failed and not emptied:
        print(f"doc replay fence: {len(clean)} clean, {len(edited)} being edited, 0 replayed")
    # A REPLAY IS ROUTINE HERE AND AN EMPTYING IS NOT. The comment above is right that a healed
    # replay must exit 0 -- a permanently-failed unit is a unit nobody reads. An emptied guarded
    # document is a class this fence had never seen before 2026-08-29, it destroyed 87 register
    # rows the same day by a neighbouring route, and it should reach a human even when the heal
    # worked.
    return 1 if (failed or emptied) else 0


if __name__ == "__main__":
    sys.exit(main())
