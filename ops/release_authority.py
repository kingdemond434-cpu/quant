"""ONE CANONICAL RELEASE, AND NOTHING ELSE TOUCHES THE MONEY PATH -- F1 of the 28.

THE PRINCIPAL, 2026-09-12, ranking this first of the remaining blueprint and calling it "the most
important remaining non-research item":

    There must be exactly one canonical branch/release lineage, protected and immutable; builds
    should be tied to an exact commit/data/config hash; live boxes should accept only signed
    release artifacts; no healer, sync process or agent should be able to overwrite money-path
    files directly.

THE MACHINERY ALREADY EXISTED AND NOTHING RAN IT. `libs/ops/release.verify()` answers "does the
running tree match the written release" against config_hash, survivor_registry_hash,
allocator_hash, money_path_hash, data_schema_version, dependency_hash and the immutable manifest.
`libs/ops/release_signing.sign/verify` authenticates that record over (code_sha, money_path_hash,
immutable_hash) with an HMAC. Measured 2026-09-12: `release.verify` has NO caller outside tests,
and `release_signing` has no caller outside its own test file. Two correct, complete guards, and
the box they protect never asked either of them a question.

That is the same DECORATIVE shape `check_enforcement_execution` found in dist_shift this morning,
except here the unrun guard is the one standing between an unreviewed process and the files that
size real positions.

THE FOURTH CLAUSE IS THE ONE WITH TEETH, and it is the failure the principal actually cites: a
correct allocator fix reverted by Adopt-Release because origin did not yet carry it. Adoption
lands the branch's tree IN PLACE, so any money-path file the box holds and origin lacks is
overwritten by an older version -- silently, hourly, by a process with no review.
`adopt_would_revert` below asks that question BEFORE it can happen, by name, per file.

WHAT THIS DOES NOT DO. It does not block, seal, adopt or push: it is a VERIFIER, and keeping it
separate from the thing it judges is the whole point (the same boundary organ_contract keeps). It
exits non-zero on a money-path drift so the watchdog and the pre-push hook can act on a verdict
they did not have to compute themselves.

    python ops/release_authority.py [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desks" / "mt5" / "reports" / "RELEASE_AUTHORITY.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _git(args: list[str], timeout: float = 30.0) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _same_bytes(rel: str, upstream: str) -> bool | None:
    """Do the working tree and upstream hold the SAME content for this path?

    Compared over NORMALISED line endings, because this repo has already paid for the other
    answer once: the immutable fence hashed raw bytes and a CRLF working tree against an LF
    worktree made identical code hash differently, leaving the fence permanently unsatisfiable.

    None when either side cannot be read -- which the caller treats as AT RISK, since an
    unreadable comparison is not evidence of safety.
    """
    try:
        here = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return None
    out = subprocess.run(["git", "show", f"{upstream}:{rel}"],
                         cwd=ROOT, capture_output=True, timeout=30)
    if out.returncode != 0:
        return None
    return here == out.stdout.replace(b"\r\n", b"\n")


def adopt_would_revert(upstream: str) -> dict[str, Any]:
    """Which MONEY-PATH files adoption would overwrite with an OLDER version.

    THE FAILURE THIS NAMES, in the principal's own words: "a correct allocator fix being reverted
    by Adopt-Release because the pushed origin did not yet contain it."

    Adopt-Release lands the branch's tree IN PLACE. That is correct when origin is ahead and
    catastrophic when the box is: a fix made on the box, not yet pushed, is replaced by the older
    upstream copy by an unattended hourly process. Nothing errors, nothing is logged as a loss,
    and the money path quietly goes backwards -- which is how 1,078 lines once vanished from
    gateway.py.

    The test is ancestry, not timestamps. A money-path file is at risk when the box's committed
    blob differs from upstream's AND the box's commit is not reachable from upstream: upstream
    simply does not have it, so landing upstream's tree discards it.
    """
    from libs.ops import release

    at_risk: list[dict[str, str]] = []
    up = _git(["rev-parse", upstream])
    if up is None:
        return {"state": "UNMEASURED",
                "why": f"cannot resolve {upstream!r} -- adoption risk is UNMEASURED, which is not "
                       f"the same as no risk (L1.28a)",
                "at_risk": []}
    behind = _git(["rev-list", "--count", f"{upstream}..HEAD"])
    for rel in release.MONEY_PATH:
        here = _git(["rev-parse", f"HEAD:{rel}"])
        there = _git(["rev-parse", f"{upstream}:{rel}"])
        if here is None:
            continue
        if there is None:
            at_risk.append({"file": rel, "why": "absent upstream -- adoption would DELETE it"})
            continue
        if here != there:
            # Differing blobs are only a LOSS when upstream cannot reach this box's version.
            reach = subprocess.run(
                ["git", "merge-base", "--is-ancestor", "HEAD", upstream],
                cwd=ROOT, capture_output=True, timeout=30)
            if reach.returncode != 0:
                # ANCESTRY IS NOT THE QUESTION -- CONTENT IS, and the first version asked only the
                # first. Measured 2026-09-12: families.py was flagged AT_RISK while the box, the
                # working tree and upstream all held byte-identical content (sha 137e0e49b6f77de2)
                # -- the file had reached upstream by a code-only ship commit the box's own branch
                # never merged, so it was unreachable AS A COMMIT and perfectly safe AS BYTES.
                #
                # Adoption writes BYTES. A guard that reports a loss where none can occur is a
                # guard that gets ignored, and this one stands between an unattended hourly
                # process and the files that size real positions -- it cannot afford to cry wolf.
                identical = _same_bytes(rel, upstream)
                if identical is True:
                    continue
                at_risk.append({
                    "file": rel,
                    "why": ("the box's version is not reachable from upstream AND its content "
                            "differs -- adoption would overwrite it with an older copy"
                            if identical is False else
                            "the box's version is not reachable from upstream and its content "
                            "could not be compared; treated as at risk, because an unreadable "
                            "comparison is not evidence of safety")})
    return {
        "state": "AT_RISK" if at_risk else "SAFE",
        "upstream": upstream,
        "commits_ahead_of_upstream": None if behind is None else int(behind or 0),
        "n_at_risk": len(at_risk),
        "at_risk": at_risk,
        "rule": ("adoption may only ever move the money path FORWARD. A file the box holds and "
                 "upstream does not is unpushed work, and landing upstream's tree destroys it."),
        "comparison": ("ancestry AND content. A file unreachable as a commit but byte-identical "
                       "upstream is SAFE -- adoption writes bytes, not history -- and reporting "
                       "it as a loss would make this guard noise. Line endings are normalised "
                       "before comparing, because a CRLF working tree against an LF blob is the "
                       "bug that once made the immutable fence permanently unsatisfiable."),
    }


def check() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds")}

    try:
        from libs.ops import release, release_signing
    except ImportError as exc:
        return {**doc, "status": "UNMEASURED",
                "why": f"release layer not importable ({exc}) -- UNMEASURED, never 'authoritative'"}

    # 1. TREE vs WRITTEN RELEASE.
    try:
        ver = release.verify()
    except Exception as exc:
        ver = {"ok": False, "why": f"{type(exc).__name__}: {exc}"}
    doc["tree_matches_release"] = ver

    # 2. IS THE RECORD AUTHENTIC. An unsigned release is not a release, it is a file -- anything
    #    on the box could have written it, which is precisely what "accept only signed artifacts"
    #    exists to prevent.
    rec = None
    try:
        rec = release.load()
    except Exception:
        rec = None
    if rec is None:
        doc["signature"] = {"state": "ABSENT",
                            "why": "no RELEASE.json -- nothing claims which build is live"}
    elif release_signing.SIG_FIELD not in rec:
        doc["signature"] = {
            "state": "UNSIGNED",
            "why": ("RELEASE.json carries no signature, so it is an unauthenticated assertion "
                    "about which code may move money. The signing key and verifier both exist "
                    "(libs/ops/release_signing.py); nothing had ever called them."),
            "fix": "seal with release_signing.sign() so the record can be authenticated",
        }
    else:
        try:
            ok, why = release_signing.verify(rec)
        except Exception as exc:
            ok, why = False, f"{type(exc).__name__}: {exc}"
        doc["signature"] = {"state": "VALID" if ok else "INVALID", "why": why,
                            "algo": rec.get(release_signing.SIG_ALGO_FIELD)}

    # 3. WOULD THE HOURLY ADOPTER DESTROY UNPUSHED MONEY-PATH WORK.
    upstream = (_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
                or "origin/HEAD")
    doc["adopt_guard"] = adopt_would_revert(upstream)

    # 4. UNCOMMITTED MONEY-PATH EDITS. A file edited on the box after the seal is drift even when
    #    git agrees about the commit -- it is running code nobody reviewed or signed.
    try:
        dirty = [p for p in release.dirty_paths(code_only=True)
                 if p in set(release.MONEY_PATH)]
    except Exception:
        dirty = []
    doc["uncommitted_money_path"] = dirty

    bad = (not ver.get("ok")) or dirty or doc["adopt_guard"]["state"] == "AT_RISK" \
        or doc["signature"]["state"] in ("UNSIGNED", "INVALID", "ABSENT")
    doc["status"] = "ATTENTION" if bad else "OK"
    doc["what_authority_means"] = (
        "one canonical lineage, a build pinned to an exact commit/data/config hash, a SIGNED "
        "record naming it, and no unattended process able to move the money path backwards. "
        "This verifies all four and blocks none of them -- a verifier that also enforces is both "
        "the decider and the check.")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
        return 0 if doc.get("status") == "OK" else 1

    print(f"release authority: {doc.get('status')}")
    tv = doc.get("tree_matches_release") or {}
    print(f"  tree vs release : {'OK' if tv.get('ok') else 'DRIFT'}  {str(tv.get('why'))[:90]}")
    sg = doc.get("signature") or {}
    print(f"  signature       : {sg.get('state')}  {str(sg.get('why'))[:90]}")
    ag = doc.get("adopt_guard") or {}
    print(f"  adopt guard     : {ag.get('state')}  {ag.get('n_at_risk', 0)} money-path file(s) "
          f"at risk vs {ag.get('upstream')}")
    for r in (ag.get("at_risk") or [])[:8]:
        print(f"      {r['file']}")
        print(f"        {r['why']}")
    if doc.get("uncommitted_money_path"):
        print(f"  uncommitted     : {len(doc['uncommitted_money_path'])} money-path file(s) edited "
              f"on the box after the seal")
        for p in doc["uncommitted_money_path"][:6]:
            print(f"      {p}")
    print(f"\n-> {OUT}")
    return 0 if doc.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
