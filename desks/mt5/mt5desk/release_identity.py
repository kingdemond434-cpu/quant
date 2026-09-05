"""Which code is this box running, and is it the code the release named? Decided before any
new position may be opened.

THE INVARIANT (principal's audit, 2026-09-05): at all times

    running box SHA == RELEASE.code_sha == signed money-path SHA == tested SHA == merged SHA

and anything else means the gateway refuses NEW risk -- open positions are still managed, stops
still ratchet, brackets still expire; nothing new is entered. The audit found the desk running
`f9fd6a26` under a manifest that named `38688f5c`: the manifest was generated before the commit
that carried it, so the identity never covered the final merge. `libs/ops/release.seal` closes
that by making the seal a manifest-only commit; this module is the box-side half that reads the
seal and answers.

PURE ON PURPOSE. No MetaTrader5, no numpy, nothing from libs/: this has to import on the box when
everything else is broken, because it is what says whether "everything else" is licensed to
trade. Windows-safe paths throughout, and git is a convenience, not a requirement -- when the
binary is not on the scheduled task's PATH, HEAD is resolved from `.git` directly.

THREE OUTCOMES, ONE LICENCE.
    ok          the running SHA is the sealed commit, or differs from it only by the manifest and
                the box's own state-sync commits (the `non_code` set the seal recorded), AND the
                money-path files on disk hash to what the seal recorded, AND the signed judge
                manifest is the sealed one.
    refused     measured, and the answer is no: unreleased code, a file edited on the box, a
                re-signed judge the release does not know.
    unmeasured  the SHA or the release could not be read. Also no. An unmeasured identity is not
                a licence; it is the absence of one.

`stale` (the seal is older than `max_age_h`, default seven days) is REPORTED, not refused, unless
configured to refuse: a desk that has shipped nothing for a week is not thereby running the wrong
code, but an operator should see that the attestation is ageing.

The verdict is written to data/release_identity.json so the shadow sync and the dashboard carry
it to every other brain.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
RELEASE_REL = "desks/mt5/data/RELEASE.json"
VERDICT_REL = "desks/mt5/data/release_identity.json"
IMMUTABLE_REL = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
CANON_REL = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"

DEFAULT_MAX_AGE_H = 7 * 24.0
ENV_MAX_AGE_H = "MT5_RELEASE_MAX_AGE_H"
ENV_STALE_REFUSES = "MT5_RELEASE_STALE_REFUSES"

#: Fallback for a release record that predates the seal and carries no `non_code` list.
#: Mirrors libs/ops/release.NON_CODE; a test pins the two together.
NON_CODE: frozenset[str] = frozenset({
    RELEASE_REL,
    "desks/mt5/data/release_identity.json",
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json",
})

_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Identity:
    ok: bool
    running_sha: str | None
    release_sha: str | None
    reason: str
    age_h: float | None
    stale: bool
    measured: bool = True
    stale_refuses: bool = False
    source: str = "none"                       # git | refs | none -- how the SHA was learned
    release_id: str | None = None
    changed_paths: tuple[str, ...] = ()        # code paths in code_sha..running (refusal detail)
    drift: tuple[str, ...] = ()                # money-path files on disk that differ from the seal
    report: tuple[str, ...] = field(default_factory=tuple)   # non-refusing observations
    at: str = ""

    def allows_new_risk(self) -> bool:
        """The only question the gateway asks. ok AND measured, and not stale when staleness is
        configured to bind. Everything that is not a yes is a no."""
        return bool(self.ok and self.measured and not (self.stale and self.stale_refuses))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["allows_new_risk"] = self.allows_new_risk()
        d["verdict"] = ("OK" if self.ok else "REFUSED") if self.measured else "UNMEASURED"
        return d


# --------------------------------------------------------------------------------------- git
def _git(args: list[str], root: Path, timeout: float = 10.0) -> str | None:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(root),
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _is_sha(s: str) -> bool:
    return bool(_SHA.fullmatch(s.strip()))


def head_from_refs(root: Path) -> str | None:
    """HEAD without the git binary. `.git` may be a directory or -- in a worktree -- a file
    reading `gitdir: <path>`; a symbolic HEAD names a ref that lives loose in the worktree gitdir,
    loose in the common dir, or packed in the common dir's packed-refs. Anything this cannot
    resolve is None, never a guess."""
    dot = root / ".git"
    try:
        if dot.is_file():
            line = dot.read_text("utf-8").strip()
            if not line.startswith("gitdir:"):
                return None
            gitdir = Path(line[len("gitdir:"):].strip())
            if not gitdir.is_absolute():
                gitdir = (root / gitdir).resolve()
        elif dot.is_dir():
            gitdir = dot
        else:
            return None
        common = gitdir
        cd = gitdir / "commondir"
        if cd.is_file():
            c = cd.read_text("utf-8").strip()
            common = Path(c) if Path(c).is_absolute() else (gitdir / c).resolve()
        head = (gitdir / "HEAD").read_text("utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head if _is_sha(head) else None
    ref = head[4:].strip()
    for base in (gitdir, common):
        try:
            v = (base / Path(*ref.split("/"))).read_text("utf-8").strip()
        except OSError:
            continue
        if _is_sha(v):
            return v
    try:
        for ln in (common / "packed-refs").read_text("utf-8").splitlines():
            parts = ln.split()
            if len(parts) == 2 and parts[1] == ref and _is_sha(parts[0]):
                return parts[0]
    except OSError:
        pass
    return None


def running_sha(root: Path) -> tuple[str | None, str]:
    """(sha, source). git first; the ref files when git is not there; (None, 'none') otherwise."""
    out = _git(["rev-parse", "HEAD"], root)
    if out and _is_sha(out):
        return out.strip(), "git"
    sha = head_from_refs(root)
    return (sha, "refs") if sha else (None, "none")


# ------------------------------------------------------------------------------------- hashes
def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def _read(rel: str, root: Path) -> bytes | None:
    try:
        return (root / Path(*rel.split("/"))).read_bytes()
    except OSError:
        return None


def hash_paths(paths: list[str] | tuple[str, ...], root: Path) -> str:
    """Byte-for-byte the digest libs/ops/release.hash_paths takes at seal time: sorted paths,
    each path's name then its CRLF-normalised bytes (or `<absent>`), first 16 hex."""
    h = hashlib.sha256()
    for rel in sorted(paths):
        h.update(rel.encode())
        b = _read(rel, root)
        h.update(_norm(b) if b is not None else b"<absent>")
    return h.hexdigest()[:16]


def _sha256_16(rel: str, root: Path) -> str | None:
    b = _read(rel, root)
    return hashlib.sha256(_norm(b)).hexdigest()[:16] if b is not None else None


# ------------------------------------------------------------------------------------ verdict
def _age_h(rec: dict[str, Any], now: datetime) -> float | None:
    raw = rec.get("sealed_at") or rec.get("generated_utc")
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return round((now - t).total_seconds() / 3600.0, 3)


def _cfg_max_age(max_age_h: float | None) -> float:
    if max_age_h is not None:
        return float(max_age_h)
    try:
        return float(os.environ.get(ENV_MAX_AGE_H, DEFAULT_MAX_AGE_H))
    except ValueError:
        return DEFAULT_MAX_AGE_H


def _cfg_stale_refuses(stale_refuses: bool | None) -> bool:
    if stale_refuses is not None:
        return bool(stale_refuses)
    return os.environ.get(ENV_STALE_REFUSES, "").strip().lower() in ("1", "true", "yes")


def _write_verdict(ident: Identity, root: Path) -> None:
    """Best effort and never raising: the verdict is the product, the file is its shadow."""
    try:
        p = root / Path(*VERDICT_REL.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ident.to_dict(), indent=1, default=str), "utf-8")
    except OSError:
        pass


def verdict(root: Path | None = None, *, now: datetime | None = None,
            max_age_h: float | None = None, stale_refuses: bool | None = None,
            write: bool = True) -> Identity:
    """The identity of the code this box is running, measured against the sealed release.

    `max_age_h` / `stale_refuses` fall back to MT5_RELEASE_MAX_AGE_H / MT5_RELEASE_STALE_REFUSES,
    then to seven days / report-only. `write` mirrors the verdict to data/release_identity.json.
    """
    r = ROOT if root is None else Path(root)
    t_now = now if now is not None else datetime.now(tz=UTC)
    at = t_now.isoformat(timespec="seconds")
    refuses = _cfg_stale_refuses(stale_refuses)
    limit = _cfg_max_age(max_age_h)

    sha, source = running_sha(r)
    try:
        rec_raw = json.loads((r / Path(*RELEASE_REL.split("/"))).read_text("utf-8"))
        rec: dict[str, Any] | None = rec_raw if isinstance(rec_raw, dict) else None
    except (OSError, ValueError):
        rec = None

    if rec is None:
        ident = Identity(ok=False, running_sha=sha, release_sha=None, measured=False,
                         reason="UNMEASURED: no readable RELEASE.json -- nothing has been sealed "
                                "for this tree, and an unmeasured identity is not a licence",
                         age_h=None, stale=True, stale_refuses=refuses, source=source, at=at)
        if write:
            _write_verdict(ident, r)
        return ident

    release_sha = str(rec.get("code_sha") or rec.get("live_sha") or "") or None
    age = _age_h(rec, t_now)
    stale = age is None or age > limit
    report: list[str] = []
    if stale:
        report.append(f"seal is {'of unknown age' if age is None else f'{age / 24:.1f}d old'} "
                      f"(max {limit / 24:.1f}d)" + ("; configured to refuse" if refuses else ""))
    if not rec.get("sealed"):
        report.append("release was described from a working tree, not sealed from a commit")
    if rec.get("tested_sha") and rec.get("tested_sha") != release_sha:
        report.append("tested_sha differs from code_sha")
    common = {"release_sha": release_sha, "age_h": age, "stale": stale, "stale_refuses": refuses,
              "source": source, "release_id": rec.get("release_id"), "at": at}

    if sha is None:
        ident = Identity(ok=False, running_sha=None, measured=False,
                         reason="UNMEASURED: the running SHA cannot be determined (git absent "
                                "and .git unreadable) -- an unmeasured identity is not a licence",
                         report=tuple(report), **common)
        if write:
            _write_verdict(ident, r)
        return ident
    if not release_sha or release_sha == "unknown":
        ident = Identity(ok=False, running_sha=sha, measured=False,
                         reason="UNMEASURED: the release names no code_sha", report=tuple(report),
                         **common)
        if write:
            _write_verdict(ident, r)
        return ident

    # 1. The SHA. Equality needs nothing; anything else is a diff between two commits.
    ok, why, changed = True, f"running the sealed commit {release_sha[:12]}", []
    if sha != release_sha:
        out = _git(["diff", "--name-only", release_sha, sha], r)
        if out is None:
            ok, why = False, (f"running {sha[:12]} != sealed {release_sha[:12]} and the diff "
                              f"cannot be taken (git {'absent' if source != 'git' else 'failed'}"
                              f", or the sealed commit is not in this clone)")
        else:
            paths = sorted({ln.strip() for ln in out.splitlines() if ln.strip()})
            allow = set(rec.get("non_code") or NON_CODE)
            changed = [p for p in paths if p not in allow]
            if changed:
                ok, why = False, (f"running {sha[:12]} carries {len(changed)} path(s) the sealed "
                                  f"release {release_sha[:12]} never named: {changed[:6]}")
            else:
                why = (f"running {sha[:12]} is the sealed code {release_sha[:12]} plus "
                       f"seal/state commits only ({len(paths)} path(s))")

    # 2. The files. git can agree while a file edited on the box disagrees; the seal's per-file
    #    digests name which. A legacy record carries only the aggregate.
    drift: list[str] = []
    money = list(rec.get("money_path") or [])
    if money and rec.get("money_path_hash") and hash_paths(money, r) != rec["money_path_hash"]:
        per = rec.get("money_path_files") or {}
        drift = [rel for rel in money if per.get(rel) and hash_paths((rel,), r) != per[rel]] \
            or ["<money path aggregate differs; no per-file digests in this record>"]
        ok = False
        why += f"; money path drifted on disk: {drift[:6]}"
    imm_rec = (rec.get("immutable_manifest") or {}).get("sha256_16")
    if imm_rec and _sha256_16(IMMUTABLE_REL, r) != imm_rec:
        ok = False
        why += "; the signed judge manifest on disk is not the one the release sealed"
    canon_rec = rec.get("canon_sha256")
    if canon_rec:
        b = _read(CANON_REL, r)
        if (hashlib.sha256(_norm(b)).hexdigest() if b is not None else None) != canon_rec:
            # The canon moves on the research clock, on this box; that is attribution, not code.
            report.append("survivor canon on disk differs from the sealed one (reported only)")

    ident = Identity(ok=ok, running_sha=sha, reason=why, changed_paths=tuple(changed),
                     drift=tuple(drift), report=tuple(report), **common)
    if write:
        _write_verdict(ident, r)
    return ident


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="release identity of this checkout")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    ident = verdict(a.root, write=not a.no_write)
    print(json.dumps(ident.to_dict(), indent=1, default=str))
    return 0 if ident.allows_new_risk() else 1


if __name__ == "__main__":
    raise SystemExit(main())
