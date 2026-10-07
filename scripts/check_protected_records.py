#!/usr/bin/env python3
"""A protected artifact may not lose RECORDS. Enforced where it is actually attacked: the commit.

THE DEFECT THIS EXISTS TO END (measured 2026-08-29). `ecc14ab0 "desk snapshot 2026-08-29T04:22Z"`
rewrote `docs/GAP_REGISTER.md` with 1 insertion and 813 deletions -- 1718 lines to 906, destroying
87 gap rows (ids 89 and 111-196). Among them were five rows the gap-fixer had closed three hours
earlier and row 194, a PRINCIPAL CONSOLE item carrying a 2026-09-10 deadline. HEAD's version was a
byte-identical PREFIX of the good one, so this was a truncation, not a merge.

THE DESK SAW IT COMING AND WROTE IT DOWN. `libs/ops/protected_artifacts.py` already lists
GAP_REGISTER.md, with the reason: "the ranked open-defect list every session reads to choose work.
Regenerated from a partial cycle it drops rows -- and a gap that vanishes reads exactly like a gap
closed." The prediction was exact. It did not help, because that list had exactly ONE enforcer --
the pytest conftest -- and a snapshot commit written by another box never runs pytest. A guard
wired only to the path the attack does not take is a guard in name.

WHY RECORDS AND NOT LINES. A line-count threshold is a heuristic, and heuristics on a shared tree
either eat real edits or are set so loose they miss the real case. These files are LEDGERS, and a
ledger has one invariant worth enforcing: a record that existed must still exist. Rewriting a
row's text is ordinary work and passes; making a row vanish is the failure and does not. Emptying
the file entirely is the degenerate case of the same rule and is called out separately because it
is what a partial regeneration actually produces.

THE OVERRIDE IS DELIBERATE AND VISIBLE. Set ALLOW_PROTECTED_RECORD_LOSS=1 in the environment of
the commit that genuinely retires records. It is one variable, it appears in shell history, and
it forces the decision to be made by someone rather than inherited from a default. It covers
EMPTIED and RECORDS_LOST only. A RECORDS_REWRITTEN finding passes only under its own variable,
ALLOW_PROTECTED_RECORD_REWRITE=1, so a loss override can never let a rewrite through -- and a
commit that both loses AND rewrites is reported for both and refused unless BOTH are set.

A MERGE IS JUDGED RECORD BY RECORD, THREE WAYS, AGAINST ITS MERGE-BASE. In a merge HEAD is only
the first parent, so a record HEAD holds and the staged blob does not is not automatically a loss:
the other side may have changed or retired it, on a commit this guard already checked. A record
the HEAD-to-staged comparison calls lost or rewritten is waived ONLY when, for the merging parent
P that supplies the staged body,

    HEAD's body == merge-base(HEAD, P)'s body   (HEAD never touched it since the base), and
    staged body == P's body                     (the merge takes P's version verbatim), and
    every OTHER merging parent Q left it as it was at merge-base(HEAD, Q).

So a record HEAD added or corrected since the base must survive in the staged file, and one
truncating parent of an octopus never wins. An EMPTIED file needs the same rule on the whole
blob. The merge itself must be real: MERGE_HEAD and MERGE_MSG present, every MERGE_HEAD sha a
commit and NONE of them an ancestor of HEAD. Anything else is treated as no merge at all, i.e.
the strict staged-vs-HEAD rule. `--range A B` applies the same rule when B is a merge commit
whose first parent is A (the clocked `--range HEAD~1 HEAD` pass); any other range compares its
two endpoints strictly, because a net loss across several commits is a loss whatever merged.

A CRISS-CROSS HISTORY HAS SEVERAL MERGE-BASES, AND THE RULE HOLDS AGAINST EVERY ONE. Plain
`git merge-base` prints one of them, chosen by git, not by this guard; a waiver read against that
one base alone could pass a record HEAD did change relative to the other. So `merge-base --all`
is read, and "HEAD's body == the base's body" (and "Q left it as its base had it") must hold for
EVERY base of that parent, or the record is not waived.

WHAT THIS GUARD DOES NOT COVER (residual cases, stated so nobody reads a pass as more than it is):

  1. IT TRUSTS ANYONE WITH WRITE ACCESS TO .git. It runs as a pre-commit hook, so whoever can
     write the repository's .git can bypass it outright: change `core.hooksPath` or the hook
     script, or write MERGE_HEAD and MERGE_MSG by hand to name a real non-ancestor commit and so
     have a staged blob judged as a merge taking that commit's records. The merge verification
     above refuses MERGE_HEAD without MERGE_MSG, non-commits and ancestors of HEAD; it cannot
     tell a hand-written pair naming a genuine side commit from one `git merge` wrote. The
     clocked `--range HEAD~1 HEAD` audit is the backstop for a skipped hook on an ordinary
     commit only: a forged pair commits a real merge with that parent, which the range pass
     judges by the same three-way rule and waives the same way.
  2. A WHOLE-FILE DELETION THAT ARRIVES THROUGH A MERGE. A protected path absent from the staged
     tree reads as an empty blob, which the EMPTIED rule judges with the three-way rule on the
     whole file: when the merging parent deleted the file and HEAD left it exactly as the base
     had it, the deletion is waived like any other change that parent made. The deletion was
     itself committed (and checked) on that parent's side, but a parent whose commits never ran
     this hook -- another box, a web edit -- delivers the deletion unexamined. The clocked
     `--range HEAD~1 HEAD` pass over the merge applies the same waiver; only a `--range` audit
     over that parent's own commits would name the deletion.

    git diff --cached  ->  this only ever inspects what is ABOUT to be committed.

Usage:
    python scripts/check_protected_records.py            # pre-commit: staged vs HEAD
    python scripts/check_protected_records.py --range A B # audit two arbitrary commits
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDE = "ALLOW_PROTECTED_RECORD_LOSS"
REWRITE_OVERRIDE = "ALLOW_PROTECTED_RECORD_REWRITE"

#: THE EVIDENCE THIS DETECTOR LEAVES BEHIND. Until 2026-09-23 this guard printed its verdict and
#: wrote nothing, so `self_repair_registry`'s `store_emptied_by_second_writer` class read its own
#: detector as having never produced and parked the class in MANUAL for ever -- a class found "by
#: hand" whose detector in fact fires on every commit. A detector with no artifact is
#: indistinguishable from a detector that stopped (L1.28a), which is the exact failure the
#: registry exists to make impossible, so the verdict is now recorded every run.
REPORT = ROOT / "desks" / "mt5" / "reports" / "PROTECTED_RECORDS.json"

#: `| 197 | **Gap title** | ...` -- the GAP_REGISTER row shape.
_MD_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
#: Keys a record-shaped payload uses for its identity, most specific first.
_ID_KEYS = ("id", "rowid", "row_id", "name", "slug", "key")


def _git(*args: str) -> str:
    return _git_rc(*args)[1]


def _git_rc(*args: str) -> tuple[int, str]:
    # UTF-8 EXPLICITLY, NEVER THE LOCALE. `text=True` alone decodes with the system locale --
    # cp1252 on the Windows trading box -- while git emits UTF-8. An unmappable byte (0x81,
    # 0x8d, 0x8f, 0x90, 0x9d) raises inside subprocess's reader THREAD, which the caller cannot
    # catch: the capture is lost and this hook exits non-zero having explained nothing. A
    # pre-commit hook that cannot decode blocks every commit on the box, including the
    # adoption's -- measured 2026-09-14, same defect in all three hook scripts.
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       check=False, timeout=120)
    return r.returncode, r.stdout


def _commit(rev: str) -> str:
    """The full sha `rev` names, or "" when it names no commit."""
    return _git("rev-parse", "-q", "--verify", f"{rev}^{{commit}}").strip()


class _Merge:
    """A VERIFIED merge: HEAD-side commit, the merging parents, and each parent's merge-base.

    `head` is the first parent (HEAD in pre-commit, A in `--range A B`). `bases[p]` is EVERY
    merge-base of (head, p) -- `merge-base --all`, because a criss-cross history has several and
    the waiver must hold against each -- or [""] when the two share no history: an empty base
    holds no records, so nothing HEAD holds can ever satisfy the three-way rule against it.
    """

    def __init__(self, head: str, parents: list[str]) -> None:
        self.head = head
        self.parents = parents
        self.bases = {p: _git("merge-base", "--all", head, p).split() or [""] for p in parents}
        self._cache: dict[tuple[str, str], str] = {}

    def text(self, sha: str, rel: str) -> str:
        if not sha:
            return ""
        key = (sha, rel)
        if key not in self._cache:
            self._cache[key] = _git("show", f"{sha}:{rel}")
        return self._cache[key]

    def doc(self) -> dict[str, object]:
        return {"head": self.head, "parents": self.parents, "bases": self.bases}


def _verified_parents(head: str, shas: list[str]) -> tuple[list[str], str]:
    """(parents, "") when every sha is a commit that is NOT an ancestor of `head`, else ([], why).

    ONE BAD PARENT VOIDS THE WHOLE MERGE. A MERGE_HEAD naming an ancestor of HEAD merges nothing
    (its every record is already in HEAD's history), so honouring it could only revert HEAD's own
    work; a MERGE_HEAD naming a blob, a tree or nothing is not a merge at all. Either way the
    commit is judged strictly, exactly as if no MERGE_HEAD existed.
    """
    if not head:
        return [], "HEAD names no commit"
    if not shas:
        return [], "MERGE_HEAD lists no sha"
    out: list[str] = []
    for s in shas:
        if _git("cat-file", "-t", s).strip() != "commit":
            return [], f"{s} is not a commit"
        full = _commit(s)
        if not full:
            return [], f"{s} does not resolve"
        if _git_rc("merge-base", "--is-ancestor", full, head)[0] == 0:
            return [], f"{s} is an ancestor of HEAD -- it merges nothing"
        out.append(full)
    return out, ""


def _git_file(name: str) -> Path | None:
    path = _git("rev-parse", "--git-path", name).strip()
    if not path:
        return None
    f = Path(path) if Path(path).is_absolute() else ROOT / path
    return f if f.is_file() else None


def _merge_in_progress() -> tuple[_Merge | None, str]:
    """The verified in-progress merge, or (None, why it was not honoured) -- why is "" if none.

    `git merge` writes MERGE_HEAD AND MERGE_MSG together and `git commit` consumes both. A
    MERGE_HEAD without its MERGE_MSG was not written by a merge. `--git-path` resolves both for
    a linked worktree too.
    """
    mh = _git_file("MERGE_HEAD")
    if mh is None:
        return None, ""
    try:
        shas = mh.read_text(encoding="utf-8").split()
    except OSError as e:
        return None, f"MERGE_HEAD unreadable: {e}"
    if _git_file("MERGE_MSG") is None:
        return None, "MERGE_HEAD present without MERGE_MSG -- no merge is in progress"
    parents, why = _verified_parents(_commit("HEAD"), shas)
    if not parents:
        return None, why
    return _Merge(_commit("HEAD"), parents), ""


def _merge_of_range(a: str, b: str) -> tuple[_Merge | None, str]:
    """`--range A B` is merge-aware only when B is a merge commit whose FIRST parent is A."""
    fa, fb = _commit(a), _commit(b)
    if not fa or not fb:
        return None, ""
    line = _git("rev-list", "--parents", "-n", "1", fb).split()
    ps = line[1:]
    if len(ps) < 2 or ps[0] != fa:
        return None, ""
    parents, why = _verified_parents(fa, ps[1:])
    if not parents:
        return None, why
    return _Merge(fa, parents), ""


def _protected() -> dict[str, str]:
    """The one list, imported rather than restated (promotion rule: import the number)."""
    sys.path.insert(0, str(ROOT))
    from libs.ops.protected_artifacts import PROTECTED
    return {k: (v[0] if isinstance(v, tuple) else str(v)) for k, v in PROTECTED.items()}


def _ident(obj: object, fallback: str) -> str:
    if isinstance(obj, dict):
        for k in _ID_KEYS:
            if k in obj:
                return f"{k}={obj[k]!r}"
    return fallback


def _add(out: dict[str, str], key: str, body: str) -> None:
    # A DUPLICATED ID IS ONE RECORD WITH SEVERAL BODIES; all of them are its body, in order.
    out[key] = f"{out[key]}\n{body}" if key in out else body


def record_bodies(rel: str, text: str) -> dict[str, str]:
    """Identity -> the record's full text, for every record in this payload.

    The keys are exactly `records()`. The bodies are what the three-way merge rule compares:
    a merge may waive a record only when its WHOLE body agrees with the merge-base on HEAD's side
    and with the merging parent on the staged side.
    """
    out: dict[str, str] = {}
    if not text.strip():
        return out
    if rel.endswith(".md"):
        for line in text.splitlines():
            if m := _MD_ROW.match(line):
                _add(out, m.group(1), line.rstrip())
        return out
    if rel.endswith(".jsonl"):
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            _add(out, _ident(obj, f"line{i}"), json.dumps(obj, sort_keys=True))
        return out
    if rel.endswith(".json"):
        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            return out
        if isinstance(d, dict):
            # A REGISTRY LOSES FIELDS, NOT KEYS. If every value is itself a record, the identity
            # that matters is key.FIELD -- otherwise a commit that strips one column from all 251
            # rows passes with every key intact. Measured 2026-08-29: the same snapshot commit
            # that deleted 87 gap rows also dropped `currency_profit` from all 251 symbols in
            # desks/mt5/data/universe/universe.json. It is MetaTrader5's own answer to "what
            # currency is this denominated in", the only correct route for a share or index CFD
            # whose name carries no denomination, and this desk has already paid once for a cost
            # field silently vanishing from this exact file (tick_value: 0/197 costable and a
            # 184x JPY commission undercharge).
            vals = list(d.values())
            if vals and all(isinstance(v, dict) for v in vals):
                for k, v in d.items():
                    for f in v:
                        _add(out, f"{k}.{f}", json.dumps(v[f], sort_keys=True))
                return out
            for k, v in d.items():
                _add(out, str(k), json.dumps(v, sort_keys=True))
            return out
        if isinstance(d, list):
            for i, x in enumerate(d):
                _add(out, _ident(x, f"idx{i}"), json.dumps(x, sort_keys=True))
    return out


def records(rel: str, text: str) -> set[str]:
    """Identity of every record in this payload, or an empty set when the shape is unknown.

    AN UNKNOWN SHAPE YIELDS NO RECORDS, so an unrecognised file is governed only by the
    empty-file rule. That is the honest direction: inventing record identities for a format this
    function cannot read would fabricate both the losses and the passes.
    """
    return set(record_bodies(rel, text))


def _bodies(rel: str, text: str) -> dict[str, str]:
    """id -> a fingerprint of the record's SUBSTANCE, for .jsonl ledgers that carry ids.

    Empty for every other shape, which keeps this check narrow on purpose.
    """
    if not rel.endswith(".jsonl") or not text.strip():
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict) or "id" not in d:
            continue
        # The substance, not the bookkeeping: a record may gain tags, an enforcer or a recurrence
        # count without being a different record. What must not change under a fixed id is what
        # the record ASSERTS.
        fields = (("title", "decision", "why", "by", "owner", "at", "evidence")
                  if rel == "context/decision_journal.jsonl"
                  else ("lesson", "evidence", "text", "claim"))
        body = "\u0000".join(str(d.get(k, "")) for k in fields)
        out[str(d["id"])] = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return out


def compare_all(rel: str, before: str, after: str) -> list[dict[str, object]]:
    """Every finding for this file, each with the affected ids NAMED; [] when nothing was lost.

    A LOSS NEVER HIDES A REWRITE. Until 2026-10-07 the loss finding returned first and the
    rewrite check never ran, so one commit that deleted a record and rewrote another, under
    ALLOW_PROTECTED_RECORD_LOSS=1, passed with the rewrite unreported. Both are reported now, and
    which override covers which is decided in `main`, never here.
    """
    if before.strip() and not after.strip():
        return [{"file": rel, "kind": "EMPTIED", "lost": [],
                 "detail": f"{len(before.splitlines())} lines -> 0"}]
    out: list[dict[str, object]] = []
    lost = sorted(records(rel, before) - records(rel, after),
                  key=lambda s: (len(s), s))
    if lost:
        out.append({"file": rel, "kind": "RECORDS_LOST", "lost": lost,
                    "detail": f"{len(lost)} record(s) present in the old version and absent "
                              f"from the new one"})
    # A RECORD CAN BE DESTROYED WITHOUT ITS ID EVER GOING MISSING (added 2026-09-14).
    #
    # Identity here is the id ALONE, so a commit that keeps every id and replaces what they say
    # passes this fence completely. That is not a hypothetical gap; it is how the desk's two
    # machines nearly lost eleven lessons in one night.
    #
    # `scripts/learn.py` mints the next id from the LOCAL ledger. The trading box and this
    # checkout were both sitting at L0293, so both minted L0294 onward, and eleven ids came to
    # name two entirely different lessons depending on which machine you asked. Adopting either
    # copy would have silently overwritten the other's eleven -- with every id present, every
    # count unchanged, and this guard reporting OK. The three ids that happened NOT to collide
    # (L0305-L0307) were caught, which is the only reason any of it was noticed.
    #
    # A ledger's promise is that a record, once written, keeps saying what it said. Deletion and
    # substitution break that promise equally, and substitution is the more dangerous of the two
    # precisely because it leaves the counts intact.
    #
    # Deliberate edits remain possible -- a typo, a sharpened evidence line -- through the same
    # named override the loss rule uses. What is refused is doing it SILENTLY.
    b_before, b_after = _bodies(rel, before), _bodies(rel, after)
    rewritten = sorted(
        (k for k in b_before if k in b_after and b_before[k] != b_after[k]),
        key=lambda s: (len(s), s))
    if rewritten:
        out.append({"file": rel, "kind": "RECORDS_REWRITTEN", "lost": rewritten,
                    "detail": f"{len(rewritten)} record(s) keep their id and now assert "
                              f"something different. Set {REWRITE_OVERRIDE}=1 to allow a "
                              f"deliberate edit, naming the records in the commit message"})
    return out


def compare(rel: str, before: str, after: str) -> dict[str, object] | None:
    """The first finding of `compare_all`, or None when nothing was lost."""
    found = compare_all(rel, before, after)
    return found[0] if found else None


def _waiver(m: _Merge, rel: str, key: str, head: str, staged: str,
            body: Callable[[str], dict[str, str]]) -> str | None:
    """The merging parent that waives record `key` under the three-way rule, else None.

    P waives it only if HEAD's body equals that of EVERY merge-base of (HEAD, P), the staged body
    equals P's, and every other merging parent Q left the record as each of its own merge-bases
    had it. A body that is absent is None on both sides, so a record P retired and HEAD never
    touched is waivable, while a record HEAD ADDED since the base (absent there, present in HEAD)
    never is. In a criss-cross history one base agreeing is not enough: HEAD may have changed the
    record relative to another, and which base plain `merge-base` prints is git's choice.
    """
    hb, sb = body(head).get(key), body(staged).get(key)

    def at(sha: str) -> str | None:
        return body(m.text(sha, rel)).get(key)

    for p in m.parents:
        if at(p) != sb or any(at(b) != hb for b in m.bases[p]):
            continue
        if all(at(q) == at(b) for q in m.parents if q != p for b in m.bases[q]):
            return p
    return None


def _apply_merge(m: _Merge, rel: str, head: str, staged: str,
                 found: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Split each finding into what the three-way rule waives and what still stands."""
    memo: dict[str, dict[str, str]] = {}

    def cached(fn: Callable[[str, str], dict[str, str]]) -> Callable[[str], dict[str, str]]:
        def get(text: str) -> dict[str, str]:
            k = f"{fn.__name__}\u0000{text}"
            if k not in memo:
                memo[k] = fn(rel, text)
            return memo[k]
        return get

    whole = cached(lambda _rel, text: {"": text})
    full, substance = cached(record_bodies), cached(_bodies)
    waived: dict[str, str] = {}
    kept: list[dict[str, object]] = []
    for f in found:
        if f["kind"] == "EMPTIED":
            if p := _waiver(m, rel, "", head, staged, whole):
                waived["<whole file>"] = p
            else:
                kept.append(f)
            continue
        body = full if f["kind"] == "RECORDS_LOST" else substance
        rest = []
        for key in (str(x) for x in f["lost"]):     # type: ignore[attr-defined]
            if p := _waiver(m, rel, key, head, staged, body):
                waived[key] = p
            else:
                rest.append(key)
        if rest:
            g = dict(f)
            g["lost"] = rest
            g["detail"] = (f"{f['detail']}; {len(rest)} not waived by the three-way merge rule"
                           if len(rest) != len(f["lost"]) else f["detail"])  # type: ignore[arg-type]
            kept.append(g)
    return kept, waived


def _write_report(prot: dict[str, str], compared: list[str],
                  findings: list[dict[str, object]], rng: list[str] | None,
                  merge: _Merge | None = None,
                  merge_waived: dict[str, dict[str, str]] | None = None,
                  merge_ignored: str = "") -> None:
    """Record what this run actually compared, so a vacuous pass cannot read as a clean one.

    `n` IS THE NUMBER OF FILES COMPARED, never the number guarded. A staged-vs-HEAD run with an
    empty index compares nothing and is a real measurement of nothing: it publishes n=0 and says
    so in `scope`, so a reader (and `self_repair_registry`) can tell "no protected artifact
    changed" from "this detector did not look".
    """
    doc = {
        "schema": "protected_records/1",
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "scope": f"range {rng[0]}..{rng[1]}" if rng else "staged vs HEAD",
        "protected": len(prot),
        "n": len(compared),
        "losses": len(findings),
        "compared": compared,
        "findings": findings,
        "merge": merge.doc() if merge else None,
        "merge_ignored": merge_ignored or None,
        "merge_waived": {rel: {k: f"waived against parent {p}" for k, p in w.items()}
                         for rel, w in (merge_waived or {}).items()},
        "rule": "a protected artifact may not lose records; a record that vanishes reads exactly "
                "like a record resolved",
    }
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(REPORT.suffix + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REPORT)
    except OSError:
        # THE GUARD OUTRANKS ITS OWN EVIDENCE. This runs as a pre-commit hook on a box where the
        # reports directory may be read-only or held by another writer; failing the commit
        # because the audit trail could not be written would block the money path over a log.
        pass


def _staged_paths() -> set[str]:
    # --no-renames: with rename detection a `git mv` of a protected file lists only the NEW path,
    # and the old protected path would never be compared at all. -z: no quoting of odd names.
    out = _git("diff", "--cached", "--name-only", "--no-renames", "-z")
    return {p for p in out.split("\0") if p}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--range", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="audit two commits instead of staged-vs-HEAD")
    args = ap.parse_args(argv)

    prot = _protected()
    findings: list[dict[str, object]] = []
    compared: list[str] = []
    merge_waived: dict[str, dict[str, str]] = {}
    if args.range:
        merge, merge_ignored = _merge_of_range(args.range[0], args.range[1])
        staged_paths: set[str] = set()
    else:
        merge, merge_ignored = _merge_in_progress()
        staged_paths = _staged_paths()
    for rel in sorted(prot):
        if args.range:
            before = _git("show", f"{args.range[0]}:{rel}")
            after = _git("show", f"{args.range[1]}:{rel}")
        else:
            if rel not in staged_paths:
                continue
            before = _git("show", f"HEAD:{rel}")
            after = _git("show", f":{rel}")          # the staged blob, not the working tree
        if not before.strip():
            continue                                  # nothing to lose
        compared.append(rel)
        found = compare_all(rel, before, after)
        if merge and found:
            found, waived = _apply_merge(merge, rel, before, after, found)
            if waived:
                merge_waived[rel] = waived
        findings.extend(found)

    _write_report(prot, compared, findings, args.range, merge, merge_waived, merge_ignored)

    if merge_ignored:
        print(f"  MERGE_IGNORED  {merge_ignored}; judged strictly against the first parent")
    for rel, w in merge_waived.items():
        by_parent: dict[str, list[str]] = {}
        for k, p in w.items():
            by_parent.setdefault(p, []).append(k)
        for p, ks in by_parent.items():
            print(f"  MERGE_WAIVED   {rel} -- {len(ks)} record(s) waived against parent {p} "
                  f"(HEAD unchanged since the merge-base; the merge takes that parent's body)")
    if not findings:
        print(f"protected records: OK over {len(prot)} guarded artifact(s)")
        return 0
    for f in findings:
        print(f"  {f['kind']:<14} {f['file']} -- {f['detail']}")
        lost = [str(x) for x in f["lost"]]            # type: ignore[attr-defined]
        if lost:
            # HEAD **AND** TAIL. Truncating to the first N hides exactly the records a session
            # just wrote -- the newest ids, the ones no other copy holds yet. Caught by this
            # guard's own test: the first cut named 20 of 87 lost rows and buried row 194, the
            # principal-console item with a deadline, in a "+67 more".
            if len(lost) <= 24:
                body = ", ".join(lost)
            else:
                body = (", ".join(lost[:12]) + f" ... +{len(lost) - 24} more ... "
                        + ", ".join(lost[-12:]))
            print(f"                 lost: {body}")
    losses = [f for f in findings if f["kind"] in ("EMPTIED", "RECORDS_LOST")]
    rewrites = [f for f in findings if f["kind"] == "RECORDS_REWRITTEN"]
    # EXACTLY "1". A variable that is merely non-empty ("0", "false", a stray export) is not a
    # decision someone made.
    loss_ok = os.environ.get(OVERRIDE) == "1"
    rewrite_ok = os.environ.get(REWRITE_OVERRIDE) == "1"
    refused = False
    if rewrites and not rewrite_ok:
        refused = True
        if loss_ok:
            print(f"  {OVERRIDE}=1 covers EMPTIED and RECORDS_LOST only, never RECORDS_REWRITTEN. "
                  f"A deliberate rewrite needs {REWRITE_OVERRIDE}=1, naming the records in the "
                  "commit message.")
    if losses and not loss_ok:
        refused = True
    if refused:
        print(f"\n  A protected artifact may not lose records. These files are ledgers, and a "
              f"record that vanishes reads exactly like a record resolved.\n"
              f"  If this retirement is deliberate, re-run with {OVERRIDE}=1 (losses) and/or "
              f"{REWRITE_OVERRIDE}=1 (rewrites) and name the records in the commit message.")
        return 2
    for name, used in ((OVERRIDE, losses), (REWRITE_OVERRIDE, rewrites)):
        if used:
            print(f"  {name}=1 -- allowed, and recorded in this output. Say in the commit "
                  "message WHICH records are being changed and why.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
