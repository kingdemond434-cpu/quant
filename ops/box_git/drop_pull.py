"""THE DROP PULL: the box fetches new packets by itself, with no Claude session in the path.

WHY (principal 2026-11-20 16:58Z: "Nth should rely on Claude bro box should never go silent
ever"; 17:27Z he picked a private GitLab repository as the source). Until now a packet reached
the inbox only when the box's Remote Control session copied it there, and when that session went
quiet (11-20 13:15Z-17:15Z) nine Audit-CLEARed fixes sat undelivered. Now cloud threads push
packets to a private drop repository, and every pass of the release loop (a box-native SYSTEM
scheduled task) pulls it and copies anything new into the inbox. ops/box_git/inbox.py then
imports it exactly as before; nothing about the gate, the verdict seat or the hook changes.

  * read only: the box authenticates with an SSH deploy key it generated itself (`--init`). The
    private key never leaves the box; only the public key is registered, read-only, on the drop
    repository. The box never pushes to the drop.
  * the host key is pinned (gitlab.com's published ed25519 key), never trust-on-first-use.
  * only `<id>.bundle`, `<id>.json` and `verdicts/<id>.json` at those two levels are copied, each
    under a size cap, each name a plain token; anything else in the drop is ignored.
  * a file is copied when its sha256 differs from the last copy of the same path (so a new head
    for the same packet id is delivered again) and recorded in a ledger. A bundle is copied
    before its manifest and verdicts last, each through a temporary name, so the inbox never sees
    half a packet.
  * a failed fetch changes nothing and says why; the next pass tries again.

THE LOCAL DROP (zuck 2026-11-26 15:59Z: "why do we even need GitLab"). Cloud threads with folder
access to the box write packets into LOCAL_DROP, a plain folder with the drop's own layout. Every
pass stages its packet files into the drop checkout's working tree (untracked: the checkout's
`checkout -f` keeps them), so BOTH consumers read them exactly as if GitLab had carried them:
deliver() below copies root packets and verdicts into the inbox, and the boot mover reads
forge_reboot/ with every one of its sha256, verdict, HOLD, fast-forward and trust-set checks
unchanged. Staging runs even when the GitLab fetch fails, so GitLab is an optional second source.
Only the drop's packet names are staged (wanted() plus forge_reboot boot packets), each under its
size cap, never a symlink, each through a temporary name.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: gitlab.com ed25519 host key, from https://docs.gitlab.com/user/gitlab_com/ (SSH known_hosts
#: entries; fingerprint SHA256:eUXGGm1YGsMAS7vkcx6JOJdOGHPem5gQp4taiCfCLB8).
GITLAB_HOST_KEY = ("gitlab.com ssh-ed25519 "
                   "AAAAC3NzaC1lZDI1NTE5AAAAIAfuCHKVTjquxvt6CM6tdG4SLp1Btn/nOeHHE5UOzRdf")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
MAX_BUNDLE = 200 * 1024 * 1024
MAX_JSON = 256 * 1024
LEDGER = "drop_ledger.json"
LOCAL_DROP = Path(r"C:\opt\bridge\quant\drop_local")
#: (boot r22) THE PACKETS-ONLY INBOX (coordinator 2026-11-27 12:44Z; zuck 12:33Z "Yes" to letting
#: the box's own Claude drop new builds in). Writable by the box's interactive user, so builds
#: reach the forge with no owner paste. It can carry AUTHOR packets only: a root `<id>.bundle` /
#: `<id>.json`. Nothing under verdicts/, forge_reboot/ or announced/ is ever read from it, and a
#: manifest naming a verdict, hold, trust or owner line is refused, so it can never move a boot,
#: approve a head or start a silence window. A packet still merges only on the Auditor's CLEAR at
#: its exact head, which keeps arriving through drop_local (admin-only) as before.
PACKETS_LOCAL = Path(r"C:\opt\bridge\quant\packets_inbox")
_SEAT_LINE = re.compile(rb"AUDIT CLEAR|AUDIT HOLD|AUTHORIZE TRUST|OWNER APPROVE|silence_approved")
_BOOT = re.compile(r"boot-[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.(bundle|bundle\.sha256|verdict\.json)")

Run = Callable[[Sequence[str]], tuple[int, str]]


@dataclass(frozen=True)
class Drop:
    url: str          # git@gitlab.com:<owner>/quant-drop.git
    key: Path         # the box's private deploy key (Administrators/SYSTEM only)
    checkout: Path    # local clone of the drop (scratch, rebuilt if broken)
    branch: str = "main"
    host_key: str = GITLAB_HOST_KEY

    def known_hosts(self) -> Path:
        return self.key.with_name("drop_known_hosts")

    def ssh(self) -> str:
        kh = self.known_hosts().as_posix()
        return (f'ssh -i "{self.key.as_posix()}" -o IdentitiesOnly=yes -o BatchMode=yes '
                f'-o StrictHostKeyChecking=yes -o UserKnownHostsFile="{kh}"')


def _run(args: Sequence[str], timeout: int = 300) -> tuple[int, str]:
    try:
        p = subprocess.run(list(args), capture_output=True, timeout=timeout, check=False,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    out = (p.stdout + p.stderr).decode("utf-8", "replace")
    return p.returncode, out


def wanted(rel: str) -> int | None:
    """The size cap for a drop path we copy, or None when the path is not ours. Pure."""
    parts = rel.split("/")
    if len(parts) == 1:
        stem, dot, ext = parts[0].rpartition(".")
        if dot and NAME.fullmatch(stem) and ".." not in stem:
            return MAX_BUNDLE if ext == "bundle" else MAX_JSON if ext == "json" else None
    if len(parts) == 2 and parts[0] == "verdicts":
        stem, dot, ext = parts[1].rpartition(".")
        if dot and ext == "json" and NAME.fullmatch(stem) and ".." not in stem:
            return MAX_JSON
    return None


def wanted_local(rel: str) -> int | None:
    """wanted() plus the boot mover's packet names under forge_reboot/. Pure."""
    parts = rel.split("/")
    if len(parts) == 2 and parts[0] == "forge_reboot" and _BOOT.fullmatch(parts[1]) \
            and ".." not in parts[1]:
        return MAX_BUNDLE if parts[1].endswith(".bundle") else MAX_JSON
    return wanted(rel)


def stage_local(local: Path | None, checkout: Path) -> list[str]:
    """Copy new or changed packet files from the local drop folder into the checkout's tree."""
    if local is None or not local.is_dir():
        return []
    rows: list[str] = []
    found = [p for p in [*local.glob("*"), *local.glob("verdicts/*"),
                         *local.glob("forge_reboot/*")]
             if p.is_file() and not p.is_symlink()]
    for p in sorted(found, key=lambda q: order(q.relative_to(local).as_posix())):
        rel = p.relative_to(local).as_posix()
        cap = wanted_local(rel)
        if cap is None:
            continue
        size = p.stat().st_size
        if size > cap:
            rows.append(f"local refused {rel}: {size} bytes over the {cap} cap")
            continue
        dest = checkout / rel
        try:
            data = p.read_bytes()
            if dest.is_file() and dest.read_bytes() == data:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except OSError as exc:  # retried next pass
            rows.append(f"local stuck {rel}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        rows.append(f"local staged {rel} {hashlib.sha256(data).hexdigest()[:12]}")
    return rows


def stage_packets(folder: Path | None, checkout: Path, keep: Path | None = None) -> list[str]:
    """(r22) Author packets from the packets-only inbox into the checkout ROOT. Never a verdict,
    a boot packet or an announcement; never a symlink; never a manifest with a seat's line."""
    if folder is None or not folder.is_dir() or folder.is_symlink():
        return []
    rows: list[str] = []
    found = [p for p in folder.iterdir() if p.is_file() and not p.is_symlink()]
    for p in sorted(found, key=lambda q: order(q.name)):
        rel = p.name
        cap = wanted(rel)
        if cap is None:
            continue  # root files only: verdicts/ etc. are never even listed (iterdir, no glob)
        if keep is not None and (keep / rel).exists():
            rows.append(f"packets skipped {rel}: drop_local holds that name")
            continue
        size = p.stat().st_size
        if size > cap:
            rows.append(f"packets refused {rel}: {size} bytes over the {cap} cap")
            continue
        try:
            data = p.read_bytes()
        except OSError as exc:
            rows.append(f"packets stuck {rel}: {type(exc).__name__}")
            continue
        if rel.endswith(".json") and _SEAT_LINE.search(data):
            rows.append(f"packets refused {rel}: a manifest may not carry a verdict or owner line")
            continue
        dest = checkout / rel
        try:
            if dest.is_file() and dest.read_bytes() == data:
                continue
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except OSError as exc:  # retried next pass
            rows.append(f"packets stuck {rel}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        rows.append(f"packets staged {rel} {hashlib.sha256(data).hexdigest()[:12]}")
    return rows


def order(rel: str) -> tuple[int, str]:
    """Bundles first, then manifests, then verdicts, so the inbox never sees half a packet."""
    return (0 if rel.endswith(".bundle") else 2 if rel.startswith("verdicts/") else 1, rel)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(drop: Drop, run: Run = _run) -> tuple[bool, str]:
    """Bring the local clone to the drop's branch tip. Read only toward the drop."""
    kh = drop.known_hosts()
    if not kh.is_file() or kh.read_text(encoding="utf-8").strip() != drop.host_key:
        kh.write_text(drop.host_key + "\n", encoding="utf-8")
    cfg = ["-c", f"core.sshCommand={drop.ssh()}", "-c", "safe.directory=*"]
    if not (drop.checkout / ".git").is_dir():
        drop.checkout.mkdir(parents=True, exist_ok=True)
        rc, out = run(["git", "-C", str(drop.checkout), "init", "-q"])
        if rc != 0:
            return False, f"init failed: {out[-200:]}"
    rc, out = run(["git", *cfg, "-C", str(drop.checkout), "fetch", "-q", "--depth", "1",
                   drop.url, f"refs/heads/{drop.branch}"])
    if rc != 0:
        return False, f"fetch failed: {out[-300:]}"
    rc, out = run(["git", "-C", str(drop.checkout), "-c", "safe.directory=*", "checkout", "-q",
                   "-f", "--detach", "FETCH_HEAD"])
    if rc != 0:
        return False, f"checkout failed: {out[-300:]}"
    rc, out = run(["git", "-C", str(drop.checkout), "-c", "safe.directory=*", "rev-parse",
                   "HEAD"])
    return True, out.strip()[:12]


def _readable_or_gone(path: Path) -> bool:
    """True when the inbox copy is gone (filed away) or opens for reading. A copy this account
    cannot read (a foreign ACL, 11-26) is delivered again instead of being skipped forever."""
    try:
        with path.open("rb") as fh:
            fh.read(1)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def deliver(checkout: Path, inbox: Path, ledger_path: Path) -> list[str]:
    """Copy new or changed packet files from the drop clone into the inbox. Returns one row per
    file copied or refused."""
    try:
        seen = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(seen, dict):
            seen = {}
    except (OSError, ValueError):
        seen = {}
    rows: list[str] = []
    found = []
    for p in [*checkout.glob("*"), *checkout.glob("verdicts/*")]:
        if p.is_file() and not p.is_symlink():
            rel = p.relative_to(checkout).as_posix()
            if wanted(rel) is not None:
                found.append(rel)
    for rel in sorted(found, key=order):
        src = checkout / rel
        cap = wanted(rel) or 0
        size = src.stat().st_size
        if size > cap:
            rows.append(f"refused {rel}: {size} bytes over the {cap} cap")
            continue
        digest = sha256(src)
        if seen.get(rel) == digest and _readable_or_gone(inbox / rel):
            continue
        dest = inbox / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(src.read_bytes())
            os.replace(tmp, dest)
        except OSError as exc:  # one unwritable file never stops the rest; retried next pass
            rows.append(f"stuck {rel}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        seen[rel] = digest
        rows.append(f"delivered {rel} {digest[:12]}")
    tmp = ledger_path.with_name(ledger_path.name + ".part")
    tmp.write_text(json.dumps(seen, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, ledger_path)
    return rows


def pull(drop: Drop, inbox: Path, state_dir: Path, run: Run = _run,
         local: Path | None = LOCAL_DROP, packets: Path | None = PACKETS_LOCAL) -> str:
    ok, why = fetch(drop, run)
    staged = stage_local(local, drop.checkout) if drop.checkout.is_dir() else []
    # (r22) a name drop_local (admin) also holds is never taken from the packets inbox
    if drop.checkout.is_dir():
        staged += stage_packets(packets, drop.checkout, keep=local)
    if not ok and not (local is not None and local.is_dir() and drop.checkout.is_dir()):
        return f"drop not pulled ({why}); inbox unchanged"
    rows = staged + deliver(drop.checkout, inbox, state_dir / LEDGER)
    head = f"drop {why}" if ok else f"drop not pulled ({why}); local drop only"
    return f"{head}: " + ("; ".join(rows) if rows else "nothing new")


def init_key(key: Path, run: Run = _run) -> str:
    """Make the box's deploy key once and return the PUBLIC half (the only part that leaves)."""
    if not key.is_file():
        key.parent.mkdir(parents=True, exist_ok=True)
        rc, out = run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "quant-box-drop",
                       "-f", str(key)])
        if rc != 0:
            raise RuntimeError(f"ssh-keygen failed: {out[-300:]}")
    return key.with_name(key.name + ".pub").read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--init", metavar="KEY", help="create the deploy key; print the public key")
    a = ap.parse_args(argv)
    if a.init:
        print(init_key(Path(a.init)))
        return 0
    ap.error("--init KEY is the only standalone use; the release loop calls pull()")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
