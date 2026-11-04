"""MERGE-TIME ADOPT_CLEARS ROWS: a merged PR's adoption CLEAR, derived from a verdict the gate
VERIFIES and did not create (R2f, docs/autonomy/HUMAN_DEPENDENCIES.md).

THE GAP. The box adopts code only when a CLEAR row in desks/mt5/data/ADOPT_CLEARS.jsonl vouches
for every governed (path, blob) it would run (libs/ops/adopt_guard.py). Those rows were landed on
LIVE by hand after every merge, and a Claude session landing one is rightly refused as a session
writing approvals. So every release waited on an owner-allowed push.

THE RULE (Governance 2026-11-04 12:50Z / 12:51Z). A row is written only from a verdict an
independent party gave and the box can check again on its own:
  * `authority` -- the release authority's Ed25519 attestation (ops/release/authority/
    attestation.py) for the PR's EXACT merged head, verified against the public key pinned on the
    box (QUANT_AUTHORITY_PUBKEY) under the pinned root digest (QUANT_AUTHORITY_ROOT_PIN). The
    signed envelope rides IN the row, so the guard re-verifies the signature itself.
  * `registry` -- the Auditor's latest row for the PR in the box registry (QUANT_AUDIT_REGISTRY)
    is CLEAR for the exact head; the guard reads that box file again at adoption.
A merge on its own, green checks, an AUDIT comment (a shared token, so unattributable) or an AUTO
"no comment" merge are NOT a source: no row is written and the guard keeps failing closed.

SELF-AUTHENTICATING. Where a row sits proves nothing (anyone holding the repo token can push to
LIVE). `verify_row` is what makes a `by: audit-gate` row count: the source re-verifies, the row's
commit is a merge whose second parent is the cleared head, and every (path, blob) it lists is the
head's own content that the merge kept byte for byte. A row that fails counts as absent.

The sweep (`--apply` from ops/box/workflow_gate.ps1) appends rows for recent merges as one
data-only commit on LIVE (a desks/mt5/data push starts no CI) and pushes it fast-forward only; a
lost race re-reads the tip and tries again, then gives up, says so in its --report record, and
leaves the guard closed.

READ BY THE GUARD (libs/ops/adopt_guard.effective_clears / authenticated): the target's own record
is the base; from origin LIVE's record only HOLDs (always) and, for a target in its history,
`by: audit-gate` CLEARs (re-verified) are added. A plain CLEAR that exists only on origin never
counts.

BOOTSTRAP (Auditor condition 7). The box guard that honours, re-verifies or refuses these rows is
the one in this tree. Until one adoption lands it, the box runs its 10-29 guard, which reads only
the target's own record and does none of the re-verification: a written `audit-gate` row is NOT
proof it was honoured until the box runs this code.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = "kingdemond434-cpu/quant"
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
CLEARS_REL = "desks/mt5/data/ADOPT_CLEARS.jsonl"
BY = "audit-gate"
KINDS = ("authority", "registry")
PUBKEY_ENV = "QUANT_AUTHORITY_PUBKEY"
ATTEST_DIR_ENV = "QUANT_AUTHORITY_ATTESTATIONS"
PIN_ENV = "QUANT_AUTHORITY_ROOT_PIN"
REGISTRY_ENV = "QUANT_AUDIT_REGISTRY"
KILL = "DEACTIVATE"
#: The merge titles LIVE carries: GitHub's own and the audit gate's (audit_gate.run).
MERGE_TITLE = re.compile(r"^Merge (?:pull request )?#(\d+)\b")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
#: How far back one sweep looks, in first-parent commits of LIVE.
LOOKBACK = 400
PUSH_TRIES = 3

Git = Callable[..., str]


def git_in(root: Path) -> Git:
    def run(*args: str, env: Mapping[str, str] | None = None, inp: bytes | None = None) -> str:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            input=inp,
            env=dict(env) if env is not None else None,
            check=False,
        )
        if done.returncode != 0:
            raise RuntimeError(f"git {' '.join(args[:2])}: {done.stderr.decode(errors='replace')}")
        return done.stdout.decode("utf-8", errors="replace").strip()

    return run


def _blob(git: Git, commit: str, rel: str) -> str | None:
    try:
        out = git("ls-tree", commit, "--", rel)
    except RuntimeError:
        return None
    parts = out.split()
    return parts[2] if len(parts) >= 3 and parts[1] == "blob" else None


def row_paths(git: Git, merge: str, head: str) -> dict[str, str | None]:
    """The (path, blob) pairs the PR changed (merge-base..head) whose content the merge kept
    byte for byte. A path the merge changed beyond the cleared head is left out: fail closed."""
    parents = git("rev-list", "--parents", "-n", "1", merge).split()[1:]
    if len(parents) < 2 or head not in parents[1:]:
        return {}
    base = git("merge-base", parents[0], head)
    out: dict[str, str | None] = {}
    for rel in git("diff", "--name-only", "--no-renames", base, head).splitlines():
        hb, mb = _blob(git, head, rel), _blob(git, merge, rel)
        if hb == mb:
            out[rel] = hb
    return out


def _attestation_mod(root: Path) -> Any:
    f = root / "ops" / "release" / "authority" / "attestation.py"
    spec = importlib.util.spec_from_file_location("_adopt_rows_attestation", f)
    if spec is None or spec.loader is None:
        raise ImportError(str(f))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Authority:
    """The box's pinned authority: public key, key id and root digest. `load` returns None when
    any part is missing or the kill file is present -- then no authority row is written or
    honoured."""

    def __init__(self, att: Any, public: Any, kid: str, digest: str, folder: str) -> None:
        self.att, self.public, self.kid, self.digest, self.folder = att, public, kid, digest, folder

    @classmethod
    def load(cls, root: Path, env: Mapping[str, str] | None = None) -> Authority | None:
        env = os.environ if env is None else env
        pub, pin, folder = env.get(PUBKEY_ENV), env.get(PIN_ENV), env.get(ATTEST_DIR_ENV, "")
        if not pub or not pin:
            return None
        if folder and (Path(folder) / KILL).exists():
            return None
        try:
            digest = json.loads(Path(pin).read_text(encoding="utf-8-sig")).get("digest")
            att = _attestation_mod(root)
            public, kid = att.load_public(pub)
        except Exception:  # no key, no cryptography, unreadable pin: nothing verifies
            return None
        if not isinstance(digest, str) or not digest:
            return None
        return cls(att, public, kid, digest, folder)

    def check(self, env: Any, pr: int, head: str, at: datetime) -> tuple[bool, str]:
        st, why = self.att.verify(
            env, self.public, self.kid, at, policy_digest=self.digest, repo=REPO
        )
        if st is None:
            return False, f"attestation: {why}"
        if st.get("verdict") != "CLEAR" or st.get("pr") != pr or st.get("head_sha") != head:
            return False, "attestation is not a CLEAR of this PR's exact head"
        return True, "attestation verified"

    def source(self, pr: int, head: str, at: datetime) -> dict[str, Any] | None:
        """The attestation that CLEARs `head`, as a row source; None if none, or if any verified
        attestation HOLDs it."""
        if not self.folder:
            return None
        found: list[tuple[str, dict[str, Any]]] = []
        for f in sorted(Path(self.folder).glob(f"pr{pr}-*.json")):
            try:
                env = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            st, _ = self.att.verify(
                env, self.public, self.kid, at, policy_digest=self.digest, repo=REPO
            )
            if st is not None and st.get("pr") == pr and st.get("head_sha") == head:
                found.append((str(st.get("verdict")), env))
        if not found or any(v == "HOLD" for v, _ in found):
            return None
        clears = [e for v, e in found if v == "CLEAR"]
        if not clears:
            return None
        return {"kind": "authority", "pr": pr, "head": head, "attestation": clears[-1]}


#: registry_latest's answer for a registry that cannot be read as a whole
GARBLED: dict[str, Any] = {"verdict": "GARBLED"}


def registry_latest(path: str | None, pr: int) -> dict[str, Any] | None:
    """The Auditor's latest registry row for `pr` -- the same "latest word wins" rule as the
    gate's registry_clear -- None when there is none, GARBLED when any line is not JSON."""
    if not path:
        return None
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    last: dict[str, Any] | None = None
    for line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            return GARBLED  # a garbled registry vouches for nothing
        if isinstance(r, dict) and r.get("pr") == pr:
            last = r
    return last


def registry_source(path: str | None, pr: int, head: str) -> dict[str, Any] | None:
    """The Auditor's latest registry row for `pr`, if it is a CLEAR of exactly `head`."""
    last = registry_latest(path, pr)
    if not last or last.get("verdict") != "CLEAR" or last.get("sha") != head:
        return None
    return {"kind": "registry", "pr": pr, "head": head, "at": str(last.get("at") or "")}


def _commit_time(git: Git, commit: str) -> datetime:
    return datetime.fromtimestamp(int(git("log", "-1", "--format=%ct", commit)), UTC)


def build_row(git: Git, merge: str, source: Mapping[str, Any]) -> dict[str, Any] | None:
    paths = row_paths(git, merge, str(source["head"]))
    if not paths:
        return None
    return {
        "commit": merge,
        "verdict": "CLEAR",
        "report": f"reports/audit/gate/pr{source['pr']}-{str(source['head'])[:12]}.md",
        "by": BY,
        "source": dict(source),
        "paths": paths,
    }


def verify_row(
    git: Git,
    row: Mapping[str, Any],
    *,
    authority: Authority | None,
    registry_path: str | None,
) -> tuple[bool, str]:
    """Does this `by: audit-gate` row stand on its own? Everything is re-derived on the box."""
    src = row.get("source")
    if not isinstance(src, Mapping) or src.get("kind") not in KINDS:
        return False, "no recognised source"
    pr, head, merge = src.get("pr"), src.get("head"), row.get("commit")
    if not isinstance(pr, int) or not isinstance(head, str) or not HEX40.match(head):
        return False, "source lacks pr or exact head"
    if row.get("verdict") != "CLEAR" or not isinstance(merge, str) or not HEX40.match(merge):
        return False, "not a CLEAR of a commit"
    try:
        kept = row_paths(git, merge, head)
        at = _commit_time(git, merge)
    except RuntimeError as exc:
        return False, f"cannot read the merge: {exc}"
    paths = row.get("paths")
    if not isinstance(paths, Mapping) or not paths:
        return False, "no paths"
    for p, b in paths.items():
        if p not in kept or kept[p] != b:
            return False, f"{p} is not the cleared head's content as merged"
    latest = registry_latest(registry_path, pr)
    if latest is not None and latest.get("verdict") != "CLEAR":
        return False, "the Auditor's latest registry word for the PR is not a CLEAR"
    if src["kind"] == "authority":
        if authority is None:
            return False, "no pinned authority on this box"
        return authority.check(src.get("attestation"), pr, head, at)
    if registry_source(registry_path, pr, head) is None:
        return False, "the registry's latest row for the PR is not a CLEAR of this head"
    return True, "registry CLEAR"


def _rows_at(git: Git, ref: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        text = git("show", f"{ref}:{CLEARS_REL}")
    except RuntimeError:
        text = ""
    rows = []
    for line in text.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return text, rows


def pending(
    git: Git, ref: str, *, authority: Authority | None, registry_path: str | None
) -> list[dict[str, Any]]:
    """Rows for LIVE's recent merges that no row covers yet and that have a verified source."""
    _, rows = _rows_at(git, ref)
    have = {r.get("commit") for r in rows}
    out: list[dict[str, Any]] = []
    log = git("log", "--first-parent", f"-{LOOKBACK}", "--format=%H %P%x09%s", ref)
    for line in log.splitlines():
        ids, _, subject = line.partition("\t")
        shas = ids.split()
        m = MERGE_TITLE.match(subject)
        if len(shas) < 3 or not m or shas[0] in have:
            continue
        merge, head, pr = shas[0], shas[2], int(m.group(1))
        at = _commit_time(git, merge)
        src = (authority.source(pr, head, at) if authority else None) or registry_source(
            registry_path, pr, head
        )
        if src is None:
            continue
        row = build_row(git, merge, src)
        if row is not None:
            ok, _ = verify_row(git, row, authority=authority, registry_path=registry_path)
            if ok:
                out.append(row)
    return list(reversed(out))  # oldest first


def append_commit(git: Git, root: Path, tip: str, rows: list[dict[str, Any]]) -> str:
    """A commit on `tip` that only appends `rows` to the CLEAR record (no working tree needed)."""
    text, _ = _rows_at(git, tip)
    body = text + ("\n" if text and not text.endswith("\n") else "")
    body += "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    idx = root / ".git" / "adopt-rows-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
    git("read-tree", tip, env=env)
    blob = git("hash-object", "-w", "--stdin", inp=body.encode("utf-8"))
    git("update-index", "--add", "--cacheinfo", f"100644,{blob},{CLEARS_REL}", env=env)
    tree = git("write-tree", env=env)
    prs = ", ".join(f"#{r['source']['pr']}" for r in rows)
    msg = (
        f"ADOPT_CLEARS: {len(rows)} merge-time row(s) for {prs} "
        "(verified authority/registry CLEARs; written by ops/release/adopt_rows.py)"
    )
    env_c = {
        **os.environ,
        "GIT_AUTHOR_NAME": "adopt-rows",
        "GIT_AUTHOR_EMAIL": "adopt-rows@box",
        "GIT_COMMITTER_NAME": "adopt-rows",
        "GIT_COMMITTER_EMAIL": "adopt-rows@box",
    }
    return git("commit-tree", tree, "-p", tip, "-m", msg, env=env_c)


def sweep(
    root: Path,
    *,
    apply: bool,
    remote: str = "origin",
    env: Mapping[str, str] | None = None,
    git: Git | None = None,
    report: Path | None = None,
) -> int:
    def note(state: str, tip: str, rows: list[dict[str, Any]], why: str = "") -> None:
        """The sweep's own record (Auditor condition 6): a miss is measurable, never silent."""
        if report is None:
            return
        doc = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "state": state,
            "tip": tip,
            "merges": [
                {"pr": r["source"]["pr"], "merge": r["commit"], "kind": r["source"]["kind"]}
                for r in rows
            ],
            "why": why,
        }
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"adopt-rows: report not written ({exc})")

    env = os.environ if env is None else env
    git = git or git_in(root)
    authority = Authority.load(root, env)
    registry_path = env.get(REGISTRY_ENV)
    ref = f"refs/remotes/{remote}/{LIVE}"
    for attempt in range(1, PUSH_TRIES + 1):
        git("fetch", "-q", remote, f"+refs/heads/{LIVE}:{ref}")
        tip = git("rev-parse", ref)
        rows = pending(git, ref, authority=authority, registry_path=registry_path)
        print(
            f"adopt-rows: {len(rows)} row(s) to write on {tip[:12]} (authority "
            f"{'on' if authority else 'off'}, registry {'on' if registry_path else 'off'})"
        )
        for r in rows:
            print(
                f"  #{r['source']['pr']} {r['commit'][:12]} [{r['source']['kind']}] "
                f"{len(r['paths'])} path(s)"
            )
        if not rows or not apply:
            note("listed" if rows else "nothing-to-write", tip, rows)
            return 0
        new = append_commit(git, root, tip, rows)
        touched = git("diff", "--name-only", tip, new).splitlines()
        if touched != [CLEARS_REL]:  # Auditor condition 5: the record and nothing else
            note("refused", tip, rows, f"the commit would touch {touched}")
            print(f"adopt-rows: refused, the commit would touch {touched}")
            return 1
        try:
            git("push", remote, f"{new}:refs/heads/{LIVE}")
        except RuntimeError as exc:
            print(f"adopt-rows: push {attempt}/{PUSH_TRIES} refused ({exc}); re-reading the tip")
            continue
        print(f"adopt-rows: pushed {new[:12]}")
        note("written", new, rows)
        return 0
    print("adopt-rows: gave up; the guard stays closed for these merges until the next sweep")
    note("gave-up", tip, rows, f"{PUSH_TRIES} fast-forward pushes refused: NO ROW WRITTEN")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--apply", action="store_true", help="push the rows (default: list only)")
    ap.add_argument("--report", default="", help="write this sweep's record here (JSON)")
    a = ap.parse_args(argv)
    try:
        return sweep(
            Path(a.root),
            apply=a.apply,
            remote=a.remote,
            report=Path(a.report) if a.report else None,
        )
    except RuntimeError as exc:
        print(f"adopt-rows: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
