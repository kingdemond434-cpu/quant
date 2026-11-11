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
  4. THIS service's own record (NOTICES_FILE in its sealed folder) shows a ROOT notice it
     DELIVERED (a receipt) for that head at least ROOT_VETO_H before M was committed;
  5. M's change (M^1..M) touches no SEALED CORE file and no sealed value, judged by THIS
     installed copy of root_path.py, never by the tree being pinned;
  6. the root digest of C equals the root digest of M: no other root change rode in after M;
  7. C is on GitHub's LIVE: fetched from the sealed root_path.REPO_URL into a bare mirror in the
     sealed folder (MIRROR) that only SYSTEM writes. EVERY git call runs against that mirror with
     pinned config; git never runs in the live tree (another account can write its .git/config),
     whose HEAD is read from its .git files only.

Digests are computed by the INSTALLED root_path.root_digest over the INSTALLED copy of
ROOT_POLICY.json; no code from any tree is run. The sealed checks run before any digest.

It also SENDS THE ROOT VETO NOTICES: the authority writes a request into its own attestations
folder (root_path.REQUEST_FILE) when a ROOT PR passes everything but the window; this service
sends it through the sealed notifier (notify.py + the frozen alert_channels.py) and records it in
NOTICES_FILE only on a receipt. That record, which no session can write, starts the window for
the authority, the gate and step 4.

Then it writes the pin for C (digest, commit, the old digest, the PR, head and merge), appends a
line to repin.log.jsonl, alerts with both digests, and removes ROOT_INFLIGHT.json. It never pins a
digest it did not compute from the released tree, and it never checks anything out.

It runs as SYSTEM from C:\\opt\\authority\\sealed (install_repin.ps1, the last box step of the
final sitting); that folder is writable by Administrators and SYSTEM only, so no PR and no
session can change the copy that runs.

    python -I repin.py --registry C:\\opt\\audit_registry --live-tree C:\\opt\\quant
        [--pin C:\\opt\\audit_registry\\ROOT_PIN.json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
INFLIGHT = "ROOT_INFLIGHT.json"
ATTEMPTS = "root_notice_attempts.json"
#: The bare mirror of GitHub's LIVE the service owns (in its sealed folder).
MIRROR = "live.git"
#: A notice that was not delivered is tried again at most this often.
RETRY = timedelta(hours=1)
LOG = "repin.log.jsonl"
RELEASE_REL = "desks/mt5/data/RELEASE.json"
#: Commits searched for the merge when the current pin names no commit on the released line.
SCAN = 5000


def _sealed(name: str, home: Path = HERE) -> Any:
    spec = importlib.util.spec_from_file_location(f"_repin_{name}", home / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _root_path(home: Path = HERE) -> Any:
    return _sealed("root_path", home)


def sealed_policy(home: Path = HERE) -> dict[str, Any]:
    """The INSTALLED ROOT_POLICY.json (a sealed file: a ROOT-path merge never changes it)."""
    doc = json.loads((home / "ROOT_POLICY.json").read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("root_files"), list):
        raise ValueError("the installed ROOT_POLICY.json has no root_files")
    return doc


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
    on_live ((bool, why)), notices (root_path.own_notices for the PR), sealed (list), digest_m,
    digest_c, old_digest."""
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
    if f.get("sealed"):
        return "REFUSE", "the merge touches the SEALED CORE: " + "; ".join(f["sealed"])
    sent = [at for at, h in f.get("notices") or [] if h == head]
    if not sent:
        return "REFUSE", f"no delivered ROOT notice on record for #{pr} at {head[:9]}"
    merged = datetime.fromtimestamp(int(merge[1]), tz=UTC)
    if merged - max(sent) < timedelta(hours=float(rp.ROOT_VETO_H)):
        return "REFUSE", f"#{pr} merged before {rp.ROOT_VETO_H:.0f} h from its delivered notice"
    on_live, lwhy = f.get("on_live") or (False, "LIVE not read")
    if not on_live:
        return "WAIT", f"the released tree is not confirmed on GitHub's LIVE: {lwhy}"
    if not f.get("digest_c") or f.get("digest_c") != f.get("digest_m"):
        return "REFUSE", "another root change reached the release after the ROOT merge"
    if f.get("digest_c") == f.get("old_digest"):
        return "CLEAR", f"#{pr} changed no pinned root file: the pin stands"
    return "PIN", f"#{pr} {head[:9]} merged by the ROOT path and adopted as {f['release_sha'][:9]}"


# ----------------------------------------------------------------------------- the box side


#: Config pinned for every git call (GIT_CONFIG_COUNT, which outranks any repository config):
#: nothing git reads can name a program to run, a proxy, or switch TLS checks off.
_PINNED = (
    ("core.askPass", ""), ("credential.helper", ""), ("core.sshCommand", ""),
    ("core.hooksPath", os.devnull), ("core.fsmonitor", "false"), ("core.pager", "cat"),
    ("diff.external", ""), ("log.showSignature", "false"), ("gpg.program", "false"),
    ("protocol.allow", "never"), ("protocol.https.allow", "always"), ("http.proxy", ""),
    ("https.proxy", ""), ("http.sslVerify", "true"), ("http.extraHeader", ""),
    ("core.gitProxy", ""), ("uploadpack.packObjectsHook", ""),
)  # fmt: skip


class Repo:
    """git as SYSTEM, ONLY against a bare mirror in the sealed folder (MIRROR), which SYSTEM
    creates and owns and no other account can write: never against the live tree, whose
    .git/config another account can write. No system or global config; _PINNED on top."""

    def __init__(self, git_dir: Path) -> None:
        self.path = git_dir

    def git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("GIT_") and k not in ("SSH_ASKPASS", "HTTPS_PROXY",
                                                          "HTTP_PROXY", "ALL_PROXY")}  # fmt: skip
        env.update({"GIT_DIR": str(self.path), "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
                    "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_COUNT": str(len(_PINNED))})  # fmt: skip
        for i, (k, v) in enumerate(_PINNED):
            env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = k, v
        return subprocess.run(
            ["git", *args], capture_output=True, check=False, timeout=600, env=env,
            cwd=str(self.path),
        )  # fmt: skip

    def out(self, *args: str) -> str:
        p = self.git(*args)
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr.decode('utf-8', 'replace')[:200]}")
        return p.stdout.decode("utf-8", "replace")

    def show(self, rev: str, name: str) -> bytes | None:
        p = self.git("show", "--no-textconv", f"{rev}:{name}")
        return p.stdout if p.returncode == 0 else None

    def has(self, sha: str) -> bool:
        return self.git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    def ancestor(self, a: str, b: str) -> bool:
        return self.git("merge-base", "--is-ancestor", a, b).returncode == 0


def refresh_mirror(repo: Repo, rp: Any) -> str:
    """Fetch GitHub's LIVE (the sealed REPO_URL) into the sealed mirror; LIVE's tip sha."""
    if not (repo.path / "HEAD").exists():
        repo.path.mkdir(parents=True, exist_ok=True)
        repo.out("init", "--bare", "-q")
    repo.out("fetch", "-q", "--no-tags", rp.REPO_URL,
             f"+refs/heads/{rp.LIVE_BRANCH}:refs/heads/live")  # fmt: skip
    tip = repo.out("rev-parse", "refs/heads/live").strip()
    if len(tip) != 40:
        raise RuntimeError("the mirror has no LIVE tip")
    return tip


def live_head(live: Path) -> str | None:
    """The live tree's HEAD commit, read from its .git FILES (git is never run there)."""
    g = live / ".git"
    try:
        head = (g / "HEAD").read_text(encoding="ascii").strip()
        if not head.startswith("ref: "):
            return head if len(head) == 40 else None
        ref = head[5:].strip()
        if ".." in ref or not ref.startswith("refs/"):
            return None
        loose = g / ref
        if loose.is_file():
            sha = loose.read_text(encoding="ascii").strip()
            return sha if len(sha) == 40 else None
        for ln in (g / "packed-refs").read_text(encoding="ascii").splitlines():
            parts = ln.split()
            if len(parts) == 2 and parts[1] == ref and len(parts[0]) == 40:
                return parts[0]
    except (OSError, UnicodeDecodeError):
        return None
    return None


def tree_digest(repo: Repo, rev: str, rp: Any, policy: Mapping[str, Any]) -> str:
    """The root digest of `rev` by the INSTALLED sealed root_path.root_digest (the same function
    the authority and the gate use), over the INSTALLED ROOT_POLICY.json. No code and no policy
    from the tree is ever used; only its bytes are hashed."""
    names = repo.out("ls-tree", "-r", "--name-only", rev).splitlines()
    return str(rp.root_digest(lambda n: repo.show(rev, n), names, policy))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None
    except (OSError, ValueError):
        return {"unreadable": True}


def gather(registry: Path, live: Path, pin: Path, rp: Any, home: Path = HERE) -> dict[str, Any]:
    f: dict[str, Any] = {"inflight": _read_json(registry / INFLIGHT)}
    inf = f["inflight"]
    if not isinstance(inf, Mapping) or not inf.get("head") or not isinstance(inf.get("pr"), int):
        return f
    rel = _read_json(live / RELEASE_REL)
    c = str((rel or {}).get("code_sha") or "") if isinstance(rel, Mapping) else ""
    f["release_sha"] = c
    if not c:
        return f
    repo = Repo(home / MIRROR)
    tip = refresh_mirror(repo, rp)
    if not repo.has(c):
        f["on_live"] = (False, f"release {c[:9]} is not on GitHub's LIVE")
    else:
        f["on_live"] = (repo.ancestor(c, tip), f"release {c[:9]} vs GitHub's LIVE {tip[:9]}")
    if not f["on_live"][0]:
        f["adopted"] = (False, f["on_live"][1])
        return f
    here = live_head(live)
    ok = bool(here) and repo.has(str(here)) and repo.ancestor(c, str(here))
    f["adopted"] = (ok, f"the live tree's HEAD {str(here)[:9]} vs release {c[:9]}")
    if not ok:
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
    f["notices"] = rp.own_notices(_read_json(home / rp.NOTICES_FILE), int(inf["pr"]))
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
    if f["sealed"]:
        return f  # refused before anything else is read
    policy = sealed_policy(home)
    f["digest_m"] = tree_digest(repo, m, rp, policy)
    f["digest_c"] = tree_digest(repo, c, rp, policy)
    f["old_digest"] = old.get("digest") if isinstance(old, Mapping) else None
    return f


Sender = Callable[[str, str], tuple[int, str]]


def _alert(send: Sender, title: str, body: str) -> str:
    rc, out = send(title, body)
    return f"alert rc={rc} {' '.join(out.split())[:120]}"


def _write_json(path: Path, doc: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def serve_notices(registry: Path, home: Path, rp: Any, send: Sender, now: datetime) -> list[str]:
    """Send every ROOT notice the authority requested (registry/attestations/REQUEST_FILE) that
    has no delivered record dated after its `after`, at most once per RETRY each, and record ONLY
    a delivered one (a receipt) in home/NOTICES_FILE. What was done, one line each."""
    req = _read_json(registry / "attestations" / rp.REQUEST_FILE)
    if not isinstance(req, Mapping) or req.get("unreadable"):
        return []
    record = _read_json(home / rp.NOTICES_FILE)
    record = dict(record) if isinstance(record, Mapping) and not record.get("unreadable") else {}
    tries = _read_json(home / ATTEMPTS)
    tries = dict(tries) if isinstance(tries, Mapping) and not tries.get("unreadable") else {}
    done: list[str] = []
    for key, r in sorted(req.items()):
        if not key.isdigit() or not isinstance(r, Mapping):
            continue
        head, after = str(r.get("head") or ""), rp._when(r.get("after")) if r.get("after") else None
        if r.get("after") and after is None:
            continue
        have = [at for at, h in rp.own_notices(record, int(key)) if h == head]
        if have and (after is None or max(have) > after):
            continue
        prev = tries.get(key) if isinstance(tries.get(key), Mapping) else {}
        last = rp._when(prev.get("at")) if prev.get("at") else None
        if last is not None and prev.get("head") == head and now - last < RETRY:
            continue
        tries[key] = {"head": head, "at": now.isoformat()}
        _write_json(home / ATTEMPTS, tries)
        title, body = rp.notice(int(key), head, r.get("files") or [])
        rc, out = send(title, body)
        got = rp.receipt(rc, out)
        if got is None:
            done.append(f"#{key} {head[:9]}: ROOT notice NOT delivered ({out[:80]})")
            continue
        record.setdefault(key, []).append({"head": head, "at": now.isoformat(), "receipt": got})
        _write_json(home / rp.NOTICES_FILE, record)
        done.append(f"#{key} {head[:9]}: ROOT notice delivered ({got[:80]})")
    return done


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


def run(registry: Path, live: Path, pin: Path, now: datetime, home: Path = HERE,
        send: Sender | None = None) -> int:  # fmt: skip
    rp = _root_path(home)
    if send is None:
        nt = _sealed("notify", home)

        def send(title: str, body: str) -> tuple[int, str]:
            return nt.send(title, body, live, home)  # type: ignore[no-any-return]

    try:
        for msg in serve_notices(registry, home, rp, send, now):
            print(msg, flush=True)
    except Exception as exc:  # a broken request never blocks the re-pin side
        print(f"ROOT notices not served ({type(exc).__name__}: {str(exc)[:160]})", flush=True)
    try:
        f = gather(registry, live, pin, rp, home)
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
        line["alert"] = _alert(send, f"ROOT re-pinned after #{inf.get('pr')}",
                               f"{why}. Root digest {str(f.get('old_digest'))[:16]} -> "
                               f"{f['digest_c'][:16]}.")  # fmt: skip
    if action in ("PIN", "CLEAR") and inf:
        (registry / INFLIGHT).unlink(missing_ok=True)
    if action == "REFUSE":
        line["alert"] = _alert(send, "RED ROOT re-pin refused",
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
    a = ap.parse_args(argv)
    registry = Path(a.registry)
    pin = Path(a.pin) if a.pin else registry / "ROOT_PIN.json"
    return run(registry, Path(a.live_tree), pin, datetime.now(UTC))


if __name__ == "__main__":
    sys.exit(main())
