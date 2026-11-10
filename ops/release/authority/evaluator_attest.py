#!/usr/bin/env python3
"""R3: RE-SIGN A JUDGE FILE WITHOUT THE OWNER, ON THE AUDITOR'S CLEAR AND THE AUTHORITY'S KEY.

WHY (zuck 2026-11-05 13:44Z, "no resigning remove that"). `scripts/check_immutable_evaluator.py`
seals the files that judge a hypothesis: any change to one must arrive with a re-signed
`IMMUTABLE_MANIFEST.json`, and until now the only way to re-sign was the owner running `--sign`.
So every reviewed fix to a judge file waited for a human at a keyboard, and the pre-push fence
refused even to put such a branch on GitHub. No agent may run `--sign`, and that stays true.

WHAT REPLACES THE OWNER'S STEP is two independent parties, neither of which can act alone:

  1. The AUDITOR reviews the change and appends one row to the box registry it already writes
     (QUANT_AUDIT_REGISTRY, a file no PR can write):
         {"kind": "EVALUATOR_CLEAR", "head": <40-hex>, "files": {<path>: <new hash>}, "at": ...}
     A later {"kind": "EVALUATOR_HOLD", "head": ...} for the same head is a veto.
  2. The RELEASE AUTHORITY (its own box account, the only reader of its Ed25519 key) runs `sign`.
     It decides nothing by judgement: it refuses unless its checkout's root digest equals the
     owner's pin, recomputes every sealed file's hash from the change itself, and signs only when
     those hashes equal, exactly, what the Auditor's latest row for that head named. One
     envelope per file, binding (file, old hash, new hash, head, base).

`apply` (any session) writes the manifest from such envelopes: it verifies each against the
public key pinned BELOW, requires the manifest to still hold the old hash and the checkout to
hold the new one, and changes nothing unless every envelope passes. `verify` (CI, law gate)
re-checks every attestation the manifest carries, so a forged or edited one is a breach.

WHAT IT CAN NEVER DO, whatever any row says:
  * re-sign `scripts/check_immutable_evaluator.py` (the fence itself) or anything this module's
    ROOT policy lists: a change to the root is never approved by the root's own authority;
  * act without a pinned key: PINNED_PUBKEY_B64 empty means `apply` refuses and nothing changes;
  * move the record seals (`append_only`, `vintage`): only judge-file hashes are written;
  * merge anything: the PR still needs its AUDIT CLEAR, its checks (replay-shadow included), an
    absent AUDIT HOLD and the gate's own merge path, exactly as before.

This file is ROOT (ops/release/authority/*): changing the pinned key, or this logic, takes the
owner's own merge and a re-pin of the root digest. The plain owner `--sign` is untouched.

    python ops/release/authority/evaluator_attest.py sign --key PEM --root-pin PIN \\
        --registry REG --bundle B.bundle --head SHA --out DIR        # the authority, on the box
    python ops/release/authority/evaluator_attest.py apply ENVELOPES.json   # any session
    python ops/release/authority/evaluator_attest.py verify                 # CI / law gate
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VERSION = "evaluator-attest/v1"
TYPE = "quant.evaluator.attestation/v1"
#: The release authority's public key, raw 32 bytes as base64. EMPTY = the attested path is OFF:
#: `apply` refuses and `verify` fails any manifest that claims an attestation. Pinned by the
#: owner's own merge of this ROOT file (read it from the box file QUANT_AUTHORITY_PUBKEY names).
PINNED_PUBKEY_B64 = ""
#: Sealed files the authority may never re-sign: the fence that judges every other seal.
NEVER_ATTESTED = ("scripts/check_immutable_evaluator.py",)
#: An envelope not applied within this long is dead; the authority re-issues on a fresh row.
MAX_AGE = timedelta(days=14)
REQUIRED = (
    "type", "repo", "file", "old_hash", "new_hash", "head_sha", "base_sha", "policy_digest",
    "auditor_at", "key_id", "issued_at",
)  # fmt: skip
_HASH = re.compile(r"^[0-9a-f]{16}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fence() -> Any:
    """The sealed fence itself: IMMUTABLE, MANIFEST and its exact hash rule."""
    return _load("immutable_evaluator_fence", ROOT / "scripts" / "check_immutable_evaluator.py")


def content_hash(raw: bytes) -> str:
    """The fence's own rule (check_immutable_evaluator._hashes): CRLF -> LF, sha256, first 16."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:16]


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pinned_key(b64: str | None = None) -> tuple[Any, str] | None:
    """(Ed25519PublicKey, key id) for the pinned key, or None when none is pinned/readable."""
    text = PINNED_PUBKEY_B64 if b64 is None else b64
    if not text:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519

        raw = base64.b64decode(text, validate=True)
        pub = ed25519.Ed25519PublicKey.from_public_bytes(raw)
    except Exception:
        return None
    return pub, hashlib.sha256(raw).hexdigest()[:16]


# ------------------------------------------------------------------------------ the verifier


def verify_envelope(env: Any, key: tuple[Any, str] | None) -> tuple[dict[str, Any] | None, str]:
    """(the verified statement, or None; why). Fails closed on every irregularity."""
    if key is None:
        return None, "no authority key is pinned: the attested path is off"
    pub, kid = key
    if not isinstance(env, Mapping) or not all(
        isinstance(env.get(k), str) for k in ("statement", "sig", "key_id")
    ):
        return None, "not an evaluator attestation envelope"
    if env["key_id"] != kid:
        return None, f"signed by key {str(env['key_id'])[:16]}, not the pinned authority key"
    try:
        pub.verify(base64.b64decode(env["sig"], validate=True), env["statement"].encode())
    except Exception:
        return None, "the signature does not verify"
    try:
        st = json.loads(env["statement"])
    except ValueError:
        return None, "the signed statement is not JSON"
    if not isinstance(st, dict) or st.get("type") != TYPE:
        return None, "not a v1 evaluator attestation"
    missing = [k for k in REQUIRED if k not in st]
    if missing:
        return None, f"the statement lacks {', '.join(missing)}"
    if st["key_id"] != kid:
        return None, "the statement names another key"
    if st["file"] in NEVER_ATTESTED:
        return None, f"{st['file']} is the fence itself: only the owner re-signs it"
    if not (_HASH.match(str(st["old_hash"])) and _HASH.match(str(st["new_hash"]))):
        return None, "a hash is not 16 hex"
    if not (_SHA.match(str(st["head_sha"])) and _SHA.match(str(st["base_sha"]))):
        return None, "a commit is not 40 hex"
    try:
        issued = datetime.fromisoformat(str(st["issued_at"]))
    except ValueError:
        return None, "unreadable issue time"
    if issued.tzinfo is None:
        return None, "an issue time without a zone"
    return st, "verified"


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def apply(
    envelopes: Sequence[Any],
    *,
    manifest: Path,
    current: Mapping[str, str],
    immutable: Sequence[str],
    key: tuple[Any, str] | None,
    is_ancestor: Callable[[str], bool],
    now: datetime | None = None,
) -> tuple[bool, list[str]]:
    """Write the manifest from verified envelopes, all or nothing. (written, one line per file).

    SINGLE USE (audit MF1, 2026-11-10). An envelope binds (file, old, new, head) and is spent
    once: one already in `attestation_log` is refused, so an owner who re-signs X->Y back to X
    cannot be undone by the old envelope if Y's bytes come back. Its head must be an ancestor
    of this checkout (`is_ancestor`), and it must be at most MAX_AGE old."""
    when = now or datetime.now(UTC)
    doc = _read_manifest(manifest)
    files = doc.get("files")
    if not isinstance(files, dict):
        return False, ["the manifest has no files section: only the owner's --sign creates one"]
    if not envelopes:
        return False, ["no envelopes given"]
    spent = {
        (r.get("file"), r.get("old_hash"), r.get("new_hash"), r.get("head_sha"))
        for r in (doc.get("attestation_log") or [])
        if isinstance(r, Mapping)
    }
    ok: list[tuple[dict[str, Any], Any]] = []
    out: list[str] = []
    seen: set[str] = set()
    for env in envelopes:
        st, why = verify_envelope(env, key)
        if st is None:
            out.append(f"REFUSED: {why}")
            continue
        f = str(st["file"])
        if f not in immutable:
            out.append(f"REFUSED {f}: not a sealed judge file")
        elif f in seen:
            out.append(f"REFUSED {f}: two envelopes for one file")
        elif (f, st["old_hash"], st["new_hash"], st["head_sha"]) in spent:
            out.append(f"REFUSED {f}: this envelope was already applied once (single use)")
        elif when - datetime.fromisoformat(str(st["issued_at"])) > MAX_AGE:
            out.append(f"REFUSED {f}: issued more than {MAX_AGE.days} days ago")
        elif not is_ancestor(str(st["head_sha"])):
            out.append(f"REFUSED {f}: head {st['head_sha'][:9]} is not in this checkout's history")
        elif files.get(f) != st["old_hash"]:
            out.append(f"REFUSED {f}: the manifest holds {files.get(f)}, the attestation was "
                       f"issued against {st['old_hash']} (stale or replayed)")  # fmt: skip
        elif current.get(f) != st["new_hash"]:
            out.append(f"REFUSED {f}: this checkout hashes to {current.get(f)}, the attestation "
                       f"names {st['new_hash']}")  # fmt: skip
        else:
            ok.append((st, env))
            out.append(f"ok {f}: {st['old_hash']} -> {st['new_hash']} (head {st['head_sha'][:9]})")
        seen.add(f)
    if len(ok) != len(envelopes):
        return False, [*out, "nothing written: every envelope must pass"]
    stamp = when.isoformat()
    rot = doc.get("rotation_signers")
    rot = dict(rot) if isinstance(rot, dict) else {}
    atts = doc.get("attestations")
    atts = dict(atts) if isinstance(atts, dict) else {}
    log = doc.get("attestation_log")
    log = list(log) if isinstance(log, list) else []
    for st, env in ok:
        f = str(st["file"])
        files[f] = st["new_hash"]
        rot[f] = f"release-authority:{st['key_id']}"
        atts[f] = dict(env)
        log.append({
            "file": f, "old_hash": st["old_hash"], "new_hash": st["new_hash"],
            "head_sha": st["head_sha"], "key_id": st["key_id"], "applied_utc": stamp,
        })  # fmt: skip
    doc.update(files=files, rotation_signers=rot, attestations=atts, attestation_log=log)
    manifest.write_text(json.dumps(doc, indent=1), "utf-8")
    return True, out


def _by_authority(signer: Any) -> bool:
    return str(signer or "").startswith("release-authority:")


def verify_manifest(manifest: Path, key: tuple[Any, str] | None) -> list[str]:
    """Breaches among the attestations the manifest carries ([] = clean, or none carried).

    VALID AND BOUND (audit MF2). A file whose `rotation_signers` entry names the release
    authority must carry an attestation that verifies AND names the hash the manifest holds;
    anything else is a hand edit wearing the authority's name. A file the owner re-signed later
    (its rotation entry no longer names the authority) keeps its envelope as history."""
    doc = _read_manifest(manifest)
    atts = doc.get("attestations")
    if not atts:
        return []
    if not isinstance(atts, dict):
        return ["the manifest's attestations section is not an object"]
    files_raw, rot_raw = doc.get("files"), doc.get("rotation_signers")
    files: dict[str, Any] = files_raw if isinstance(files_raw, dict) else {}
    rot: dict[str, Any] = rot_raw if isinstance(rot_raw, dict) else {}
    bad = []
    for f, env in sorted(atts.items()):
        st, why = verify_envelope(env, key)
        if st is None:
            bad.append(f"{f}: {why}")
        elif st["file"] != f:
            bad.append(f"{f}: the envelope attests {st['file']}")
        elif str(rot.get(f, "")).startswith("release-authority:") and st["new_hash"] != files.get(
            f
        ):
            bad.append(f"{f}: the manifest holds {files.get(f)} under the authority's name, the "
                       f"attestation names {st['new_hash']}")  # fmt: skip
    for f, signer in sorted(rot.items()):
        if _by_authority(signer) and f not in atts:
            bad.append(f"{f}: signed in the authority's name with no attestation")
    return bad


# ------------------------------------------------------------------------------ the authority


def registry_rows(path: str) -> list[dict[str, Any]]:
    """The registry's rows, oldest first; any unreadable line reads as no rows (fail closed)."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    except (OSError, ValueError):
        return []
    return rows if all(isinstance(r, dict) for r in rows) else []


def auditor_clear(
    rows: Sequence[Mapping[str, Any]], head: str
) -> tuple[dict[str, Any] | None, str]:
    """The Auditor's latest evaluator verdict for `head`: a CLEAR row, or None and why."""
    mine = [r for r in rows if r.get("head") == head
            and r.get("kind") in ("EVALUATOR_CLEAR", "EVALUATOR_HOLD")]  # fmt: skip
    if not mine:
        return None, f"no EVALUATOR_CLEAR row for {head[:9]}"
    last = mine[-1]
    if last.get("kind") != "EVALUATOR_CLEAR":
        return None, f"the latest evaluator row for {head[:9]} is a HOLD"
    if not isinstance(last.get("files"), dict) or not last["files"]:
        return None, "the CLEAR row names no files"
    return dict(last), "cleared"


def changed_sealed(
    read_base: Callable[[str], bytes | None],
    read_head: Callable[[str], bytes | None],
    immutable: Sequence[str],
) -> dict[str, tuple[str, str]]:
    """{file: (base hash, head hash)} for every sealed file the change touches."""
    out = {}
    for f in immutable:
        b, h = read_base(f), read_head(f)
        hb = content_hash(b) if b is not None else "<absent>"
        hh = content_hash(h) if h is not None else "<absent>"
        if hb != hh:
            out[f] = (hb, hh)
    return out


def decide(
    changed: Mapping[str, tuple[str, str]],
    manifest_files: Mapping[str, str],
    row: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """Mechanical, no judgement: the Auditor's row must name exactly the changed sealed files
    with exactly the hashes the authority computed, from a base whose manifest is honest."""
    why: list[str] = []
    if not changed:
        why.append("the change touches no sealed judge file")
    named = row.get("files") or {}
    for f, (old, new) in sorted(changed.items()):
        if f in NEVER_ATTESTED:
            why.append(f"{f} is the fence itself: only the owner re-signs it")
        if "<absent>" in (old, new):
            why.append(f"{f} is added or removed: that changes the sealed set, the owner's call")
        if manifest_files.get(f) != old:
            why.append(f"{f}: the base manifest holds {manifest_files.get(f)}, the base file "
                       f"hashes to {old} (the base is already red)")  # fmt: skip
        if named.get(f) != new:
            why.append(f"{f}: the Auditor CLEARed {named.get(f)}, the change hashes to {new}")
    for f in sorted(set(named) - set(changed)):
        why.append(f"{f}: CLEARed by the Auditor but not changed by this head")
    return not why, why


def statements(
    changed: Mapping[str, tuple[str, str]],
    *,
    repo: str,
    head: str,
    base: str,
    digest: str,
    auditor_at: str,
    kid: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    at = (now or datetime.now(UTC)).isoformat()
    return [
        {"type": TYPE, "repo": repo, "file": f, "old_hash": old, "new_hash": new,
         "head_sha": head, "base_sha": base, "policy_digest": digest, "auditor_at": auditor_at,
         "key_id": kid, "issued_at": at, "authority_version": VERSION}
        for f, (old, new) in sorted(changed.items())
    ]  # fmt: skip


def sign_statement(st: Mapping[str, Any], private: Any, kid: str) -> dict[str, str]:
    if st.get("key_id") != kid:
        raise ValueError("the statement's key_id is not the signing key's")
    body = canonical(dict(st)).decode()
    return {"statement": body, "sig": base64.b64encode(private.sign(body.encode())).decode(),
            "key_id": kid}  # fmt: skip


def _git(*args: str) -> bytes | None:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False)
    return p.stdout if p.returncode == 0 else None


def _sign_cmd(a: argparse.Namespace) -> int:
    auth = _load("authority_main", HERE / "authority.py")
    policy = auth.pol.load_policy()
    digest = auth.tree_digest("HEAD", policy)
    ok, why = auth.pinned(a.root_pin, digest)
    if not ok:
        print(f"evaluator-attest: {why}")
        return 2
    try:
        key, kid = auth.att.load_private(a.key)
    except Exception as exc:
        print(f"evaluator-attest: no usable key ({type(exc).__name__}); nothing signed")
        return 2
    if not _SHA.match(a.head):
        print("evaluator-attest: --head must be a full 40-hex commit")
        return 1
    ref = f"refs/evaluator/{a.head}"
    if _git("fetch", "-q", "--no-tags", str(a.bundle), f"+{a.head}:{ref}") is None:
        print("evaluator-attest: the bundle does not carry that head")
        return 1
    base = (_git("rev-parse", "HEAD") or b"").decode().strip()
    fen = fence()
    rel_manifest = fen.MANIFEST.relative_to(fen.ROOT).as_posix()
    mf = json.loads((_git("show", f"HEAD:{rel_manifest}") or b"{}").decode() or "{}")
    changed = changed_sealed(lambda f: _git("show", f"HEAD:{f}"),
                             lambda f: _git("show", f"{ref}:{f}"), fen.IMMUTABLE)  # fmt: skip
    row, rwhy = auditor_clear(registry_rows(a.registry), a.head)
    if row is None:
        print(f"evaluator-attest: {rwhy}; nothing signed")
        return 1
    good, reasons = decide(changed, mf.get("files") or {}, row)
    if not good:
        print("evaluator-attest: REFUSED\n  " + "\n  ".join(reasons))
        return 1
    envs = [sign_statement(st, key, kid) for st in statements(
        changed, repo=a.repo, head=a.head, base=base, digest=digest,
        auditor_at=str(row.get("at", "")), kid=kid)]  # fmt: skip
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"evaluator-{a.head[:12]}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    dest.write_text(json.dumps(envs, sort_keys=True, indent=1), encoding="utf-8")
    print(f"evaluator-attest: signed {len(envs)} file(s) for {a.head[:9]} -> {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign", help="the release authority, on the box")
    s.add_argument("--repo", default="kingdemond434-cpu/quant")
    s.add_argument("--key", required=True)
    s.add_argument("--root-pin", required=True)
    s.add_argument("--registry", required=True)
    s.add_argument("--bundle", required=True, type=Path)
    s.add_argument("--head", required=True)
    s.add_argument("--out", required=True)
    p = sub.add_parser("apply", help="write the manifest from verified envelopes")
    p.add_argument("envelopes", type=Path)
    sub.add_parser("verify", help="re-check every attestation the manifest carries")
    a = ap.parse_args(argv)
    if a.cmd == "sign":
        return _sign_cmd(a)
    fen = fence()
    key = pinned_key()
    if a.cmd == "verify":
        bad = verify_manifest(fen.MANIFEST, key)
        print("evaluator attestations: " + ("OK" if not bad else f"{len(bad)} breach(es)"))
        for b in bad:
            print(f"  BREACH {b}")
        return 1 if bad else 0
    try:
        envs = json.loads(a.envelopes.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"evaluator-attest: unreadable envelopes ({type(exc).__name__})")
        return 1
    envs = envs if isinstance(envs, list) else [envs]

    def is_ancestor(sha: str) -> bool:
        p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", sha, "HEAD"],
                           capture_output=True, check=False)  # fmt: skip
        return p.returncode == 0

    done, lines = apply(envs, manifest=fen.MANIFEST, current=fen._hashes(),
                        immutable=fen.IMMUTABLE, key=key, is_ancestor=is_ancestor)  # fmt: skip
    print("\n".join(lines))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
