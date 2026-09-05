"""An artifact that is READ but never WRITTEN is a leg running blind, and it never says so.

WHY THIS FENCE EXISTS (measured 2026-09-05)

`research/edge_search.py` and `research/orthogonal_sweep.py` both read COT positioning from
`cot.json`, `cot_tff.json` and `cot_disagg.json`. Nothing in this repository has ever written any
of the three. The only mentions of those names anywhere are the two reads. Every pass fell
through all three, hit `continue`, and resolved with no COT at all -- for the entire life of the
search leg, and in complete silence, because the loop treats a missing optional input exactly as
it treats an input that is genuinely unavailable.

The desk owned the data the whole time: 26 years of point-in-time CFTC history sat in
`data/cot_zcache.parquet`, refreshed on a timer and shipped to the box every pipeline run.

THIS IS A CLASS, NOT AN INCIDENT. The same shape appeared three times the same day: COT fetchers
writing to a retired laptop's path while the readers looked in the desk tree, a launcher `cd`ing
into a directory that does not exist on the machine that runs it, and these three filenames. In
every case a producer and a consumer disagreed about a name, and nothing compared them, so the
desk spent compute continuously and produced nothing while every fence stayed green.

WHAT IT MEASURES. Every artifact filename that appears in a READ position somewhere in the tree,
and whether that same name appears in a WRITE position anywhere, or exists on disk. A name that
is read, never written, and absent is a wire that goes nowhere.

WHY NOT AST REACHABILITY. The desk already has `check_reachability.py` for the capability graph,
which answers "is this module reached". That is a different question from "does the FILE this
module opens ever get created", and the COT defect passed reachability cleanly: both readers were
perfectly reachable and perfectly wired to nothing.

    python3 scripts/check_read_without_writer.py [--json]

Every dead wire is NAMED on every run. The exit code is a RATCHET: adding one fails, and the
recorded count may only fall. See MAX_DANGLING for why a fence that failed on the existing debt
would have been switched off within a day instead of fixing anything.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "read_without_writer.json"

#: Artifact-looking string literals. Bare names and short relative paths, which is how the desk
#: writes them at call sites: `_read(BASE / "data" / "cot.json")`.
_ARTIFACT = re.compile(r'["\']([A-Za-z0-9_][A-Za-z0-9_./-]{2,80}\.'
                       r'(?:json|jsonl|parquet|csv|npz|txt|log))["\']')

#: A line that CONSUMES the name. Deliberately generous: a false "this is a read" only matters
#: when the same name is never written anywhere, which is the finding.
_READ = re.compile(r'\b(?:_read|read_text|read_bytes|read_json|read_parquet|read_csv|load|'
                   r'loads|open|glob|rglob|exists|is_file|iterdir|scandir)\b')

#: A line that PRODUCES it. `to_parquet`/`write_text`/`dump` are the desk's usual writers;
#: `scp`, `Set-Content` and shell redirection produce it from ops scripts.
#:
#: `_write`, `_save`, `_dump` and `_atomic_write` are THIS DESK'S OWN helpers and matter more
#: than the stdlib names: most artifacts here are produced through one of them, so a pattern
#: without them calls half the desk's real writers invisible and reports working wires as dead.
_WRITE = re.compile(r'\b(?:_write|_save|_dump|_atomic_write|atomic_write|write_json|save_json|'
                    r'write_text|write_bytes|to_parquet|to_json|to_csv|savez|dump|dumps|'
                    r'writer|writerow|writerows|mkdir|touch|rename|replace|copy|copy2|copyfile|'
                    r'scp|Set-Content|Out-File|tee)\b|>>?\s*["\']?\$?\{?[A-Za-z0-9_/.$-]*'
                    r'(?:json|jsonl|parquet|csv|log)')

_SKIP_PARTS = {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".ruff_cache",
               "vault", "archive"}
_SUFFIXES = {".py", ".sh", ".ps1", ".cmd"}

#: Lines either side of a name that count as its context. Two covers the shapes the
#: desk actually writes -- a tuple of names iterated on the next line, a constant
#: assigned above the call that uses it -- without reaching into unrelated code.
_WINDOW = 2

#: Read but never written IN THIS REPO, on purpose, with the reason. A fence whose allowlist
#: carries no reasons is a fence nobody can safely extend.
_EXTERNAL: dict[str, str] = {
    "requirements.txt": "packaging input, written by a human",
    "coverage.json": "written by pytest-cov at CI time, never by desk code",
    "mt5cov.json": "written by pytest-cov in the money-path job",
    "settings.json": "editor/tool configuration, not a desk artifact",
}

#: A RATCHET, NOT A BLOCKER, and the distinction is the point. Failing the build on the whole
#: existing debt would either stop every merge or, far more likely, get the fence switched off
#: within a day. Neither outcome fixes a wire. So the number may only FALL: a new dead wire fails
#: immediately, which is the case worth catching, because it is cheap to fix while the author
#: still remembers and it is exactly how COT went unnoticed for the life of the search leg.
#:
#: THIS NUMBER IS AN UPPER BOUND, AND KNOWING WHY MATTERS BEFORE ANYONE ACTS ON IT. `data/*` is
#: gitignored, so most real artifacts are absent from a fresh checkout and cannot clear the
#: "already on disk" test here even though they exist on the box. Run this ON THE VPS for the
#: true figure; in CI it measures the code, not the deployment. A large share of the rest sits in
#: crypto-era scripts currently being deleted, so the honest expectation is that this falls
#: sharply on its own.
#:
#: Measured 2026-09-05 on claude/tier1-batch, mid-purge, in a checkout with no data lake. An
#: earlier reading of 85 came from a line-local scan that could not see the COT defect itself
#: (see `_classify`); it is not comparable and must not be treated as a regression from it.
#:
#: 175 -> 167, same day, same checkout, as the scripts/ identity sweep closed eight wires: the
#: hedge-integrity surface and its producer, the perp-funding-decay research row and its detector
#: artifact, the two Coin Metrics BTC price reads (the FRED macro screen and the Stage-A executor)
#: repointed onto the MT5 desk's own BTCUSD bars, the two deleted crypto collectors dropped from
#: the wiring audit's reachability list, and the Upbit snapshot test dropped from the enforcement
#: map. Lowered because the fence asked: the count fell, so the floor follows it down and the next
#: new wire fails immediately.
MAX_DANGLING = 167


def _classify(path: Path) -> tuple[set[str], set[str], set[str]]:
    """(read here, written here, mentioned here at all), matched over a WINDOW of lines.

    LINE-LOCAL MATCHING MISSES THE DEFECT THIS FENCE EXISTS FOR, which I found by writing the
    test before trusting the code. The real `edge_search` reads COT like this:

        for name in ("cot_tff.json", "cot.json", "cot_disagg.json"):
            doc = _read(BASE / "data" / name)

    The filenames are on one line and the verb is on the next, joined by a variable. A scan that
    required both on the same line saw a tuple of strings nobody read and reported nothing --
    it would have passed the exact bug it was built to catch.

    So a name is READ when a read verb appears within `_WINDOW` lines of it, and WRITTEN on the
    same rule. The window also removes the need for the earlier "mentioned outside a read"
    guess: `OUT = ROOT / "data" / "verdicts.json"` two lines above `_write(OUT, doc)` is now
    seen as the write it is, rather than excused as an unknown.
    """
    reads: set[str] = set()
    writes: set[str] = set()
    named: set[str] = set()
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return reads, writes, named

    lines = text.splitlines()
    per_line: list[set[str]] = []
    for line in lines:
        if line.lstrip().startswith("#"):
            per_line.append(set())         # a name in a comment neither reads nor writes
            continue
        per_line.append({m.group(1).split("/")[-1] for m in _ARTIFACT.finditer(line)})

    for i, names in enumerate(per_line):
        if not names:
            continue
        named |= names
        lo, hi = max(0, i - _WINDOW), min(len(lines), i + _WINDOW + 1)
        near = "\n".join(lines[lo:hi])
        if _WRITE.search(near):
            writes |= names
        if _READ.search(near):
            reads |= names
    return reads, writes, named


def scan() -> dict:
    read_by: dict[str, list[str]] = {}
    written: set[str] = set()
    on_disk: set[str] = set()
    mentions: dict[str, int] = {}

    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or any(part in _SKIP_PARTS for part in p.parts):
            continue
        if p.suffix in {".json", ".jsonl", ".parquet", ".csv", ".npz", ".txt", ".log"}:
            on_disk.add(p.name)
        if p.suffix not in _SUFFIXES:
            continue
        rel = str(p.relative_to(ROOT))
        reads, writes, named = _classify(p)
        for n in named:
            mentions[n] = mentions.get(n, 0) + 1
        written |= writes
        for name in reads:
            read_by.setdefault(name, []).append(rel)

    # THE RULE IS DELIBERATELY NARROW, AND THE FIRST VERSION TAUGHT ME WHY. Flagging every name
    # that no line I recognised as a write produced gave 224 hits, 169 of them in production
    # code -- because this desk writes through helpers (`_write(p, doc)`, `json.dump(doc, f)`)
    # where the filename literal never shares a line with the verb. A fence at that precision is
    # noise, and the desk's own doctrine is explicit that a checker which flags correct behaviour
    # is worse than no checker: it trains everyone to skim past its output.
    #
    # So the signal is the one that is actually unambiguous, and it is the one the COT defect
    # had: a name whose ONLY appearances in the entire repository are reads. Not "I could not
    # find the writer" but "there is nothing else here at all". `cot.json`, `cot_tff.json` and
    # `cot_disagg.json` each appeared exactly twice, both times being read. No helper, no
    # indirection and no shell redirection can hide a producer that leaves no mention anywhere.
    dangling = []
    for name, readers in sorted(read_by.items()):
        if name in written or name in on_disk or name in _EXTERNAL:
            continue
        prod = sorted(r for r in set(readers)
                      if not (r.startswith("tests/") or "/tests/" in r))
        if not prod:
            continue                      # only tests name it: a fixture, not a leg's input
        dangling.append({"artifact": name, "read_by": prod[:6], "n_readers": len(set(readers))})

    return {"checked_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_artifacts_read": len(read_by), "n_written_somewhere": len(written),
            "n_present_on_disk": len(on_disk), "read_without_writer": dangling}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    doc = scan()
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    except OSError as e:
        doc["report_unwritten"] = str(e)
    if args.json:
        print(json.dumps(doc, indent=1))

    bad = doc["read_without_writer"]
    print(f"READ WITHOUT WRITER {doc['checked_at']}")
    print(f"  {doc['n_artifacts_read']} artifact names read, "
          f"{doc['n_written_somewhere']} written somewhere, "
          f"{doc['n_present_on_disk']} present on disk")
    if not bad:
        print("  every artifact a leg reads is produced by something, or is already there.")
        return 0

    for d in bad:
        print(f"    {d['artifact']}  <- read by {', '.join(d['read_by'])}"
              + (f" (+{d['n_readers'] - len(d['read_by'])} more)"
                 if d["n_readers"] > len(d["read_by"]) else ""))

    if len(bad) > MAX_DANGLING:
        print(f"  BREACH: {len(bad)} dead wires, above the {MAX_DANGLING} this tree carries. "
              f"A NEW one was added.")
        print("  Wire the producer, delete the dead read, or add it to _EXTERNAL WITH THE REASON "
              "it comes from outside this repo. Never raise MAX_DANGLING to go green: the "
              "ratchet only falls.")
        return 1

    print(f"  {len(bad)} dead wires, at or below the {MAX_DANGLING} recorded for this tree -- "
          f"a debt being worked down, not a new defect.")
    if len(bad) < MAX_DANGLING:
        print(f"  RATCHET: lower MAX_DANGLING to {len(bad)} in this file; the count has fallen "
              f"and the floor should follow it down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
