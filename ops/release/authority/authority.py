#!/usr/bin/env python3
"""THE RELEASE AUTHORITY -- an independent, deterministic signer of CLEAR / HOLD attestations.

WHAT IT IS. A separate service, NOT a code-writing agent and NOT a Claude session:
  * its own Windows account on the box (`quant-authority`), the only account that can read the
    signing key (C:\\opt\\authority\\key\\authority.pem, ACL: quant-authority + SYSTEM);
  * its own read-only GitHub App installation token in GH_TOKEN (contents, pull requests,
    checks, actions, issues: READ; it cannot push, comment, label or merge);
  * its own clean checkout of LIVE, whose ROOT digest must equal the box pin zuck wrote
    (C:\\opt\\authority\\ROOT_PIN.json) or it signs nothing at all.

WHAT IT DOES, per open PR into LIVE: reads the exact head, the complete changed-file list, the
base and head copies of what classify() needs, every required check run (provenance-checked by
the gate's own code), the trusted AUDIT verdicts and the release switches; runs policy.decide();
and for CLEAR or HOLD writes one signed envelope to the attestations folder the box gate reads.
It never merges. The gate verifies the signature, re-checks CI, sends the veto notice, waits
24 h by its own clock, and merges pinned to the head. Signer and merger are separate programs
under separate identities, so neither alone can land a change.

    python ops/release/authority/authority.py --repo OWNER/NAME --out DIR --key PEM \\
        --root-pin ROOT_PIN.json [--pr N] [--dry-run]

Exit 0: looked at every PR; 2: root pin mismatch or no key (nothing signed); 1: a PR failed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VERSION = "authority/v1"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


att = _load("authority_attestation", HERE / "attestation.py")
pol = _load("authority_policy", HERE / "policy.py")


def gate() -> Any:
    """The gate's own helpers, from THIS checkout (root, pinned): tier, checks, provenance..."""
    return _load("audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")


def _git_bytes(*args: str) -> bytes | None:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False)
    return p.stdout if p.returncode == 0 else None


def tree_digest(rev: str | None, policy: dict[str, Any]) -> str:
    """The root digest of `rev` (None: the working tree of this checkout)."""
    if rev is None:
        names = (_git_bytes("ls-files") or b"").decode().splitlines()

        def read(n: str) -> bytes | None:
            q = ROOT / n
            return q.read_bytes() if q.is_file() else None
    else:
        names = (_git_bytes("ls-tree", "-r", "--name-only", rev) or b"").decode().splitlines()

        def read(n: str) -> bytes | None:
            return _git_bytes("show", f"{rev}:{n}")

    return pol.root_digest(read, names, policy)


def pinned(pin_path: str, digest: str) -> tuple[bool, str]:
    try:
        pin = json.loads(Path(pin_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return False, f"the root pin is unreadable ({type(exc).__name__})"
    if not isinstance(pin, dict) or pin.get("digest") != digest:
        return False, "this checkout's root digest is not the one zuck pinned: nothing is signed"
    return True, "root pin matches"


def facts(ag: Any, repo: str, pr: int, base: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Everything decide() needs, read by the authority itself. Any read error raises."""
    p = ag._gh(f"repos/{repo}/pulls/{pr}")
    head = str(p["head"]["sha"])
    f: dict[str, Any] = {
        "pr": pr,
        "head": head,
        "open": p.get("state") == "open",
        "same_repo": (p["head"].get("repo") or {}).get("full_name") == repo,
        "base_ok": p["base"]["ref"] == base,
        "base_sha": str(p["base"]["sha"]),
    }
    if not (f["open"] and f["same_repo"] and f["base_ok"]):
        return f
    files = ag._flat(ag._gh(f"repos/{repo}/pulls/{pr}/files?per_page=100", "--paginate", "--slurp"))
    if str(ag._gh(f"repos/{repo}/pulls/{pr}")["head"]["sha"]) != head:
        raise RuntimeError("head moved while its files were read")
    level, twhy = ag.tier(files, int(p.get("changed_files") or 0),
                          lambda n: ag.referenced_by_code(base, n))  # fmt: skip
    names = sorted({str(n) for x in files for n in (x.get("filename"), x.get("previous_filename"))
                    if n})  # fmt: skip
    ag._git("fetch", "-q", "--no-tags", "origin", base)
    ag._git("fetch", "-q", "--no-tags", "origin", head)

    def reader(rev: str) -> Callable[[str], str | None]:
        def read(n: str) -> str | None:
            b = _git_bytes("show", f"{rev}:{n}")
            return b.decode("utf-8", "replace") if b is not None else None

        return read

    cls, why = pol.classify(names, level, policy, reader(f"origin/{base}"), reader(head))
    f.update(tier=level, tier_why=twhy, cls=cls, cls_reasons=why, files=names)
    found = ag.verdicts(ag._flat(ag._gh(f"repos/{repo}/issues/{pr}/comments?per_page=100",
                                        "--paginate", "--slurp")))  # fmt: skip
    if found and found[-1]["verdict"] != "CLEAR":
        f["hold"] = f"AUDIT HOLD {found[-1]['sha'][:9]} ({found[-1]['at']})"
    board = ag._flat(ag._gh(f"repos/{repo}/issues/{ag.APPROVALS_ISSUE}/comments?per_page=100",
                            "--paginate", "--slurp"))  # fmt: skip
    f["deactivated"] = not ag.activated(board)[0]
    f["patch_id"] = ag.patch_id(base, head)
    if cls in ("CONTROLLER", "AUTO", "LOW"):
        need = pol.required_jobs(cls, ag.GATING_JOBS, ag.AUTO_JOBS, policy)
        pages = ag._gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100", "--paginate",
                       "--slurp")  # fmt: skip
        runs = [r for page in ag._flat_pages(pages) for r in (page.get("check_runs") or [])]
        genuine = ag.provenance(repo, pr, head)
        f["checks"] = ag.checks(runs, need, genuine)
        f["review_queued"] = ag.queued_review(repo, runs, genuine) is not None
        f["evidence"] = {
            str(r.get("name")): {"id": r.get("id"), "conclusion": r.get("conclusion")}
            for r in runs
            if str(r.get("name")) in need and genuine(r)
        }
        if cls == "CONTROLLER" and f["checks"][0] == "pass":
            # a check-changing PR: its own pull_request runs are self-attested, so the BASE's
            # trusted-eval (pull_request_target) must also have passed on this exact head
            ok, ewhy = ag.trusted_eval_passed(repo, pr, head, base)
            if not ok:
                done = "running" not in ewhy and "no base-run" not in ewhy
                f["checks"] = ("fail" if done else "pending", ewhy)
            else:
                f["evidence"]["trusted-eval"] = ewhy
        f["fresh"], f["fresh_why"] = ag.up_to_date(base, head)
    return f


def issue(
    f: dict[str, Any],
    verdict: str,
    reasons: list[str],
    *,
    repo: str,
    digest: str,
    key: Any,
    kid: str,
    ttl_h: float,
    now: datetime | None = None,
) -> dict[str, str]:
    st = att.statement(
        repo=repo, pr=f["pr"], head_sha=f["head"], base_sha=f["base_sha"],
        patch_id=f.get("patch_id"), tier=str(f.get("cls")), verdict=verdict,
        policy_digest=digest,
        evidence={"checks": f.get("evidence") or {}, "files": f.get("files") or [],
                  "gate_tier": f.get("tier"), "checks_why": (f.get("checks") or ("", ""))[1]},
        reasons=reasons, kid=kid, now=now, ttl=timedelta(hours=ttl_h),
        authority_version=VERSION,
    )  # fmt: skip
    return att.sign(st, key, kid)


def write(out: Path, env: dict[str, str], pr: int, head: str, verdict: str, digest: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = out / f"pr{pr}-{head[:12]}-{verdict}-{digest[:8]}-{stamp}.json"
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(env, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return dest


def fresh_exists(
    out: Path, pr: int, head: str, verdict: str, digest: str, max_age_h: float = 12.0
) -> bool:
    """Was this (pr, head, verdict) signed in the last `max_age_h` hours? Then no re-sign."""
    import time

    for f in out.glob(f"pr{pr}-{head[:12]}-{verdict}-{digest[:8]}-*.json"):
        try:
            if time.time() - f.stat().st_mtime < max_age_h * 3600:
                return True
        except OSError:
            continue
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=None)
    ap.add_argument("--out", required=True, help="the attestations folder the gate reads")
    ap.add_argument("--key", required=True, help="the authority's Ed25519 PKCS8 PEM")
    ap.add_argument("--root-pin", required=True)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--dry-run", action="store_true", help="decide and print; sign nothing")
    a = ap.parse_args(argv)
    policy = pol.load_policy()
    digest = tree_digest("HEAD", policy)
    ok, why = pinned(a.root_pin, digest)
    if not ok:
        print(f"REFUSED: {why} (digest {digest[:16]})")
        return 2
    try:
        key, kid = att.load_private(a.key)
    except Exception as exc:  # no key, wrong type, no cryptography: sign nothing
        print(f"REFUSED: the signing key is unusable ({type(exc).__name__})")
        return 2
    if (Path(a.out) / "DEACTIVATE").exists():
        print("REFUSED: the DEACTIVATE file is present in the attestations folder")
        return 2
    ag = gate()
    base = a.base or ag.LIVE
    if a.pr is not None:
        prs = [a.pr]
    else:
        pages = ag._gh(f"repos/{a.repo}/pulls?state=open&base={base}&per_page=100", "--paginate",
                       "--slurp")  # fmt: skip
        prs = [int(p["number"]) for p in ag._flat(pages)]
    rc = 0
    for n in prs:
        try:
            f = facts(ag, a.repo, n, base, policy)
            verdict, reasons = pol.decide(f)
        except (RuntimeError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as exc:
            print(f"#{n}: not judged: {exc}")
            rc = 1
            continue
        line = f"#{n} @ {f['head'][:9]} [{f.get('cls')}]: {verdict} -- {'; '.join(reasons)}"
        if verdict in ("CLEAR", "HOLD") and fresh_exists(
            Path(a.out), n, f["head"], verdict, digest
        ):
            line += " (a fresh attestation already exists)"
        elif verdict in ("CLEAR", "HOLD") and not a.dry_run:
            env = issue(f, verdict, reasons, repo=a.repo, digest=digest, key=key, kid=kid,
                        ttl_h=float(policy.get("attestation_ttl_hours", 48)))  # fmt: skip
            line += f" -> {write(Path(a.out), env, n, f['head'], verdict, digest).name}"
        print(line, flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
