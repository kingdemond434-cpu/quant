#!/usr/bin/env python3
"""THE ROOT RE-PIN SERVICE (SEALED; NO_OWNER_EVER, Governance condition 4, Auditor must-fix 4).

After a ROOT PR merged by the ROOT path (root_path.py), LIVE's root digest is no longer the one
pinned on the box, so the authority and the gate switch their path off. Today zuck re-pins by
hand (root_merge.ps1, an Administrator window). This service does it instead, and ONLY when
everything below holds; otherwise it re-pins nothing, keeps ROOT_INFLIGHT.json (so the ROOT path
stays off), logs a RED line and alerts:

  1. ROOT_INFLIGHT.json names the PR and head the gate merged by the ROOT path;
  2. the box ADOPTED a released tree C: the live tree's RELEASE.json (written by the release
     workflow's seal) names code_sha C, the live tree's HEAD contains C, and C contains the merge;
  3. the merge M is on C's first-parent line, titled by the gate's ROOT path for that PR, with
     that head as its second parent;
  4. the gate's own record shows a DELIVERED ROOT notice (a receipt) for that head at least
     ROOT_VETO_H before M was committed;
  5. M's change (M^1..M) touches no SEALED CORE file and no sealed value, judged by THIS
     installed copy of root_path.py, never by the tree being pinned;
  6. the root digest of C equals the root digest of M: no other root change rode in after M.

Then it writes the pin for C (digest, commit, the old digest, the PR, head and merge), appends a
line to repin.log.jsonl, alerts with both digests, and removes ROOT_INFLIGHT.json. It never pins a
digest it did not compute from the released tree, and it reads git only (no fetch, no checkout).

It runs as SYSTEM from C:\\opt\\authority\\sealed (install_repin.ps1, the last box step of the
final sitting); that folder is writable by Administrators and SYSTEM only, so no PR and no
session can change the copy that runs.

    python -I repin.py --registry C:\\opt\\audit_registry --live-tree C:\\opt\\quant
        [--pin C:\\opt\\audit_registry\\ROOT_PIN.json] [--notify "python ...send_alert.py"]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
INFLIGHT = "ROOT_INFLIGHT.json"
WINDOW = "root_window.json"
LOG = "repin.log.jsonl"
RELEASE_REL = "desks/mt5/data/RELEASE.json"
POLICY_REL = "ops/release/authority/policy.py"
ROOT_POLICY_REL = "ops/release/authority/ROOT_POLICY.json"
#: Commits searched for the merge when the current pin names no commit on the released line.
SCAN = 5000


def _root_path() -> Any:
    spec = importlib.util.spec_from_file_location("_repin_root_path", HERE / "root_path.py")
    if spec is None or spec.loader is None:
        raise ImportError("root_path")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_merge(
    log: list[tuple[str, list[str], int, str]], pr: int, head: str
) -> tuple[str, int] | None:
    """(sha, commit time) of the gate's ROOT-path merge of `pr` at `head` among `log` (first-parent
    commits of C, newest first: sha, parents, unix time, subject), or None."""
    want = f"Merge #{pr} ("
    for sha, parents, at, subject in log:
        if (subject.startswith(want) and "ROOT path" in subject and len(parents) == 2
                and parents[1] == head):  # fmt: skip
            return sha, at
    return None


def plan(f: Mapping[str, Any], rp: Any) -> tuple[str, str]:
    """("PIN" | "CLEAR" | "WAIT" | "REFUSE", why). Pure over the facts the service read:
    inflight, release_sha, adopted (bool, why), contains_merge, merge ((sha, time) or None),
    window_rec, sealed (list), digest_m, digest_c, old_digest."""
    inf = f.get("inflight")
    if not inf:
        return "CLEAR", "no ROOT merge in flight"
    if not isinstance(inf, Mapping) or not inf.get("head") or not isinstance(inf.get("pr"), int):
        return "REFUSE", f"{INFLIGHT} is unreadable: nothing is pinned"
    pr, head = int(inf["pr"]), str(inf["head"])
    if not f.get("release_sha"):
        return "WAIT", "no released tree yet (RELEASE.json names no code_sha)"
    ok, awhy = f.get("adopted") or (False, "adoption not read")
    if not ok:
        return "WAIT", f"the box has not adopted the release yet: {awhy}"
    if not f.get("contains_merge"):
        return "WAIT", f"the adopted release does not contain the merge of #{pr} yet"
    merge = f.get("merge")
    if merge is None:
        return "REFUSE", f"no ROOT-path merge of #{pr} at {head[:9]} on the released line"
    rec = f.get("window_rec") or {}
    if rec.get("head") != head or not rec.get("receipt"):
        return "REFUSE", f"no delivered ROOT notice on record for #{pr} at {head[:9]}"
    try:
        sent = datetime.fromisoformat(str(rec.get("at")))
    except ValueError:
        return "REFUSE", "the ROOT notice record has an unreadable time"
    merged = datetime.fromtimestamp(int(merge[1]), tz=UTC)
    if sent.tzinfo is None or merged - sent < timedelta(hours=float(rp.ROOT_VETO_H)):
        return "REFUSE", f"#{pr} merged before {rp.ROOT_VETO_H:.0f} h from its delivered notice"
    if f.get("sealed"):
        return "REFUSE", "the merge touches the SEALED CORE: " + "; ".join(f["sealed"])
    if not f.get("digest_c") or f.get("digest_c") != f.get("digest_m"):
        return "REFUSE", "another root change reached the release after the ROOT merge"
    if f.get("digest_c") == f.get("old_digest"):
        return "CLEAR", f"#{pr} changed no pinned root file: the pin stands"
    return "PIN", f"#{pr} {head[:9]} merged by the ROOT path and adopted as {f['release_sha'][:9]}"


# ----------------------------------------------------------------------------- the box side


class Repo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        """Read-only git as SYSTEM in a tree other accounts can write: no system or global
        config, and every repo-config key that can run a program is overridden on the command
        line (which wins over .git/config). Only plumbing reads are used: no index, no hooks."""
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}  # fmt: skip
        env.pop("GIT_DIR", None)
        env.pop("GIT_WORK_TREE", None)
        safe = ["-c", f"safe.directory={self.path.as_posix()}", "-c", "core.fsmonitor=false",
                "-c", "core.hooksPath=" + os.devnull, "-c", "diff.external=",
                "-c", "core.pager=cat", "-c", "core.sshCommand=",
                "-c", "protocol.allow=never"]  # fmt: skip
        return subprocess.run(
            ["git", *safe, "-C", str(self.path), *args],
            capture_output=True, check=False, timeout=120, env=env,
        )  # fmt: skip

    def out(self, *args: str) -> str:
        p = self.git(*args)
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr.decode('utf-8', 'replace')[:200]}")
        return p.stdout.decode("utf-8", "replace")

    def show(self, rev: str, name: str) -> bytes | None:
        p = self.git("show", "--no-textconv", f"{rev}:{name}")
        return p.stdout if p.returncode == 0 else None

    def ancestor(self, a: str, b: str) -> bool:
        return self.git("merge-base", "--is-ancestor", a, b).returncode == 0


def tree_digest(repo: Repo, rev: str, rp: Any) -> str:
    """The root digest of `rev` by the INSTALLED sealed root_path.root_digest (the same function
    the authority and the gate use), over that tree's ROOT_POLICY.json (a sealed file). No code
    from the tree is ever run."""
    raw = repo.show(rev, ROOT_POLICY_REL)
    if raw is None:
        raise RuntimeError(f"{rev[:9]} has no root policy")
    names = repo.out("ls-tree", "-r", "--name-only", rev).splitlines()
    return str(rp.root_digest(lambda n: repo.show(rev, n), names, json.loads(raw)))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None
    except (OSError, ValueError):
        return {"unreadable": True}


def gather(registry: Path, live: Path, pin: Path, rp: Any) -> dict[str, Any]:
    f: dict[str, Any] = {"inflight": _read_json(registry / INFLIGHT)}
    inf = f["inflight"]
    if not isinstance(inf, Mapping) or not inf.get("head") or not isinstance(inf.get("pr"), int):
        return f
    rel = _read_json(live / RELEASE_REL)
    c = str((rel or {}).get("code_sha") or "") if isinstance(rel, Mapping) else ""
    f["release_sha"] = c
    if not c:
        return f
    repo = Repo(live)
    tip = repo.out("rev-parse", "HEAD").strip()
    f["adopted"] = (repo.ancestor(c, tip), f"the live tree's HEAD {tip[:9]} vs release {c[:9]}")
    if not f["adopted"][0]:
        return f
    old = _read_json(pin)
    since = str(old.get("commit") or "") if isinstance(old, Mapping) else ""
    span = [c, f"^{since}"] if since and repo.ancestor(since, c) else [f"-{SCAN}", c]
    lines = repo.out("log", "--first-parent", "--format=%H%x00%P%x00%ct%x00%s", *span)
    log = []
    for ln in lines.splitlines():
        parts = ln.split("\x00")
        if len(parts) == 4:
            log.append((parts[0], parts[1].split(), int(parts[2] or 0), parts[3]))
    merge = find_merge(log, int(inf["pr"]), str(inf["head"]))
    f["merge"] = merge
    f["contains_merge"] = merge is not None or repo.ancestor(str(inf["head"]), c)
    window = _read_json(registry / WINDOW)
    f["window_rec"] = (window or {}).get(str(inf["pr"])) if isinstance(window, Mapping) else None
    if merge is None:
        return f
    m = merge[0]
    names = repo.out("diff", "--no-ext-diff", "--no-textconv", "--name-only", "--no-renames",
                     f"{m}^1", m).splitlines()  # fmt: skip

    def side(rev: str) -> Callable[[str], str | None]:
        def read(n: str) -> str | None:
            b = repo.show(rev, n)
            return b.decode("utf-8", "replace") if b is not None else None

        return read

    f["sealed"] = rp.sealed_touch(names, side(f"{m}^1"), side(m))
    f["digest_m"] = tree_digest(repo, m, rp)
    f["digest_c"] = tree_digest(repo, c, rp)
    f["old_digest"] = old.get("digest") if isinstance(old, Mapping) else None
    return f


def _alert(cmd: str | None, title: str, body: str) -> str:
    if not cmd:
        return "no notify command"
    try:
        p = subprocess.run([*shlex.split(cmd, posix=os.name != "nt"), title, body],
                           capture_output=True, text=True, timeout=120, check=False)  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        return f"alert failed ({type(exc).__name__})"
    return f"alert rc={p.returncode} {' '.join((p.stdout or '').split())[:120]}"


def write_pin(pin: Path, doc: Mapping[str, Any]) -> None:
    """Atomically: a temp file beside the pin, given the pin's ACL (Administrators and SYSTEM
    write, Users read) BEFORE it replaces the pin, so there is never a moment with a partial
    pin or a pin other accounts can write."""
    tmp = pin.with_name(pin.name + ".repin.tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    if os.name == "nt":
        got = subprocess.run(["icacls", str(tmp), "/inheritance:r", "/grant:r",
                              "Administrators:F", "SYSTEM:F", "Users:R"],
                             capture_output=True, check=False, timeout=60)  # fmt: skip
        if got.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise OSError("the new pin's ACL could not be set; nothing pinned")
    os.replace(tmp, pin)


def run(registry: Path, live: Path, pin: Path, notify: str | None, now: datetime) -> int:
    rp = _root_path()
    try:
        f = gather(registry, live, pin, rp)
        action, why = plan(f, rp)
    except Exception as exc:  # any read error pins nothing; the next pass looks again
        action, why, f = "WAIT", f"not judged ({type(exc).__name__}: {str(exc)[:160]})", {}
    line: dict[str, Any] = {"at": now.isoformat(), "action": action, "why": why}
    inf = f.get("inflight") if isinstance(f.get("inflight"), Mapping) else {}
    if action == "PIN":
        doc = {"digest": f["digest_c"], "commit": f["release_sha"], "pinned_at": now.isoformat(),
               "by": "repin", "previous_digest": f.get("old_digest"), "pr": inf.get("pr"),
               "head": inf.get("head"), "merge": f["merge"][0]}  # fmt: skip
        write_pin(pin, doc)
        line.update(old=f.get("old_digest"), new=f["digest_c"], commit=f["release_sha"])
        line["alert"] = _alert(notify, f"ROOT re-pinned after #{inf.get('pr')}",
                               f"{why}. Root digest {str(f.get('old_digest'))[:16]} -> "
                               f"{f['digest_c'][:16]}.")  # fmt: skip
    if action in ("PIN", "CLEAR") and inf:
        (registry / INFLIGHT).unlink(missing_ok=True)
    if action == "REFUSE":
        line["alert"] = _alert(notify, "RED ROOT re-pin refused",
                               f"{why}. Nothing was pinned; the ROOT path stays off.")  # fmt: skip
    if action != "CLEAR" or inf:
        with (registry / LOG).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
    print(f"{action}: {why}", flush=True)
    return 2 if action == "REFUSE" else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--live-tree", required=True)
    ap.add_argument("--pin")
    ap.add_argument("--notify")
    a = ap.parse_args(argv)
    registry = Path(a.registry)
    pin = Path(a.pin) if a.pin else registry / "ROOT_PIN.json"
    return run(registry, Path(a.live_tree), pin, a.notify, datetime.now(UTC))


if __name__ == "__main__":
    sys.exit(main())
