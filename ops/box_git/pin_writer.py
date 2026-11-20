"""THE PIN WRITER: the only program that moves the trust pin. Frozen (in T), run as SYSTEM from the
pinned trust folder (C:\\ProgramData\\QuantBox\\trust), never from a checkout.

WHY (Governance review 2026-11-19, finding 1). The gate, the loop and box CI run code an ordinary
merge can change, so none of them may write the pin. This program, whose own code only an
owner-authorized change can alter, does it after re-deciding everything itself with the pinned
checker's `verdict`:

  1. TAMPER: every file of the trust folder is hashed against the pin. A mismatch is RESTORED
     from the copy archived for the current pin, and logged.
  2. LIVE MOVED: when LIVE's head differs from the one last recorded, `verdict(old, new)` is
     re-run. Allowed and T changed -> the pin follows (previous copies archived first, the
     checker files and contract suites refreshed from LIVE). Not allowed -> nothing moves, so
     every later merge waits (the forge hook should have refused it; this is the second lock).
  3. OPEN PRS: for a PR whose verdict is CONTRACT, the pinned contract suites run against its
     head as the non-admin CI worker; a pass is recorded under its T hash. For a TRUST change,
     the owner's own AUTHORIZE TRUST <head> (quant-admin, typed, unedited) is recorded under its
     T hash. The gate and the forge hook read those records; neither can write them.
  4. Every action appends one row to the rules-change log.

    python -I C:\\ProgramData\\QuantBox\\trust\\pin_writer.py --config <loop.json>
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
CHECKER_FILES = ("trust_check.py", "TRUST_SET.json", "pin_writer.py", "protect.py")
AUTHORIZE = re.compile(r"AUTHORIZE TRUST ([0-9a-f]{40})")
OWNER_LOGIN = "quant-admin"


def _load_checker(folder: Path) -> Any:
    spec = importlib.util.spec_from_file_location("_pinned_trust_check", folder / "trust_check.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("no trust_check.py in the trust folder")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folder_hashes(folder: Path) -> dict[str, str]:
    out = {n: sha(folder / n) for n in CHECKER_FILES if (folder / n).is_file()}
    suites = folder / "contracts"
    if suites.is_dir():
        for f in sorted(suites.rglob("*.py")):
            out[f.relative_to(folder).as_posix()] = sha(f)
    return out


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def log(path: Path | None, row: Mapping[str, Any]) -> None:
    if path is None:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": _now(), "by": "pin_writer", **row}) + "\n")
    except OSError:
        pass


def save_pin(path: Path, pin: Mapping[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(pin, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def archive(folder: Path, t_hash: str) -> Path:
    """Copy the current checker files and suites under history/<t_hash> (kept, never deleted)."""
    dest = folder / "history" / t_hash[:16]
    if not dest.exists():
        dest.mkdir(parents=True)
        for n in CHECKER_FILES:
            if (folder / n).is_file():
                shutil.copy2(folder / n, dest / n)
        if (folder / "contracts").is_dir():
            shutil.copytree(folder / "contracts", dest / "contracts")
    return dest


def restore(folder: Path, pin: Mapping[str, Any]) -> list[str]:
    """Put back every trust-folder file whose hash differs from the pin's record."""
    want: Mapping[str, str] = pin.get("files") or {}
    src = folder / "history" / str(pin.get("t_hash", ""))[:16]
    fixed = []
    for rel, h in want.items():
        f = folder / rel
        if f.is_file() and sha(f) == h:
            continue
        cand = src / rel
        if cand.is_file() and sha(cand) == h:
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cand, f)
            fixed.append(rel)
        else:
            fixed.append(f"{rel} (NO GOOD COPY)")
    return fixed


def refresh(folder: Path, git: Callable[..., str], ref: str, policy: Mapping[str, Any]) -> None:
    """Checker files and every contract suite from `ref` (an allowed LIVE head)."""
    for n in CHECKER_FILES:
        (folder / n).write_text(git("show", f"{ref}:ops/box_git/{n}"), encoding="utf-8")
    for area, spec in (policy.get("contracts") or {}).items():
        if area.startswith("_"):
            continue
        for t in spec.get("suite", []):
            dest = folder / "contracts" / area / t
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(git("show", f"{ref}:{t}"), encoding="utf-8")


# ------------------------------------------------------------------------- the forge (read only)
def forge_get(cfg: Mapping[str, Any], path: str) -> Any:
    import ssl
    token = (Path(cfg["tokens"]) / "adopt.token").read_text(encoding="utf-8").strip()
    ctx = ssl.create_default_context(cafile=str(cfg["ca"]))
    ctx.check_hostname = False
    req = urllib.request.Request(f"{str(cfg['forge_url']).rstrip('/')}/api/v1{path}",
                                 headers={"Authorization": f"token {token}"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read() or b"null")


def owner_typed(comments: list[Mapping[str, Any]], head: str) -> Mapping[str, Any] | None:
    for c in comments:
        m = AUTHORIZE.fullmatch(str(c.get("body") or "").strip())
        if (m and m.group(1) == head and str((c.get("user") or {}).get("login")) == OWNER_LOGIN
                and c.get("updated_at") in (None, c.get("created_at"))):
            return c
    return None


# ------------------------------------------------------------------------- contract suites
def run_suites(cfg: Mapping[str, Any], folder: Path, head: str, areas: list[str],
               policy: Mapping[str, Any], timeout: float = 5400) -> tuple[bool, str]:
    """The PINNED suites, copied over a worktree of `head`, run by the non-admin CI worker."""
    bare = str(cfg.get("forge_bare") or cfg["bare"])
    work = Path(cfg["work"])
    work.mkdir(parents=True, exist_ok=True)
    wt = Path(tempfile.mkdtemp(prefix="contract_", dir=work))
    subprocess.run(["git", "-c", "safe.directory=*", "-C", bare, "worktree", "add", "-q",
                    "--detach", str(wt), head], check=True, capture_output=True, timeout=600)
    try:
        tests = []
        for a in areas:
            for t in policy["contracts"][a]["suite"]:
                src = folder / "contracts" / a / t
                if not src.is_file():
                    return False, f"pinned suite {a}/{t} is missing"
                (wt / t).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, wt / t)
                tests.append(t)
        jobs = Path(cfg["ci_jobs"])
        jid = uuid.uuid4().hex
        (jobs / "pending").mkdir(parents=True, exist_ok=True)
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "PATHEXT", "COMSPEC")
               if k in os.environ}
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                    "GIT_CONFIG_VALUE_0": "*"})
        job = {"id": jid, "cwd": str(wt), "env": env, "timeout": timeout,
               "argv": [str(cfg.get("python") or sys.executable), "-m", "pytest", "-q", "-p",
                        "no:cacheprovider", "-p", "no:randomly", *sorted(set(tests))]}
        tmp = jobs / "pending" / f"{jid}.tmp"
        tmp.write_text(json.dumps(job), encoding="utf-8")
        os.replace(tmp, jobs / "pending" / f"{jid}.json")
        result = jobs / "done" / f"{jid}.json"
        deadline = time.monotonic() + timeout + 900
        while time.monotonic() < deadline:
            if result.exists():
                try:
                    doc = json.loads(result.read_text(encoding="utf-8"))
                    result.unlink(missing_ok=True)
                    return int(doc.get("rc", 1)) == 0, str(doc.get("out", ""))[-300:]
                except (OSError, ValueError):
                    pass
            time.sleep(5)
        return False, "the CI worker did not answer in time"
    finally:
        subprocess.run(["git", "-c", "safe.directory=*", "-C", bare, "worktree", "remove",
                        "--force", str(wt)], capture_output=True, timeout=300)
        shutil.rmtree(wt, ignore_errors=True)


# ------------------------------------------------------------------------- one pass
def one_pass(cfg: Mapping[str, Any], folder: Path = HERE,
             forge: Callable[[str], Any] | None = None,
             suites: Callable[..., tuple[bool, str]] | None = None) -> list[str]:
    pin_path = folder / "pin.json"
    rlog = Path(cfg["rules_log"]) if cfg.get("rules_log") else None
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    out: list[str] = []
    fixed = restore(folder, pin)
    if fixed:
        out.append(f"TAMPER restored {fixed}")
        log(rlog, {"class": "RESTORE", "what": "trust folder tamper", "files": fixed})
    tc = _load_checker(folder)
    policy = tc.load_policy((folder / "TRUST_SET.json").read_text(encoding="utf-8"))
    bare = str(cfg.get("forge_bare") or cfg["bare"])

    def git(*a: str) -> str:
        return subprocess.run(["git", "-c", "safe.directory=*", "-C", bare, *a],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              check=True, timeout=300).stdout
    live = git("rev-parse", f"refs/heads/{LIVE}").strip()
    if pin.get("live") and pin["live"] != live:
        ok, cls, why, ht = tc.verdict(git, pin["live"], live, pin, policy)
        if not ok:
            out.append(f"ALERT LIVE moved to {live[:12]} outside the boundary: {cls} {why}")
            log(rlog, {"class": "ALERT", "head": live, "why": f"{cls}: {why}"})
            save_pin(pin_path, pin)
            return out
        if ht and ht != pin.get("t_hash"):
            archive(folder, str(pin["t_hash"]))
            pin["history"] = [*(pin.get("history") or []),
                              {k: pin.get(k) for k in ("t_hash", "at", "by", "live")}][-200:]
            refresh(folder, git, live, policy)
            pin.update({"t_hash": ht, "at": _now(), "by": f"pin_writer: {cls} at {live[:12]}",
                        "files": folder_hashes(folder)})
            archive(folder, ht)
            out.append(f"PIN moved to {ht[:12]} ({cls})")
            log(rlog, {"class": cls, "head": live, "t_hash": ht, "why": why,
                       "undo": "revert the merge; the pin follows back (RESTORE)"})
    pin["live"] = live
    if forge is None:
        def forge(path: str) -> Any:
            return forge_get(cfg, path)
    prs = forge("/repos/quant/quant/pulls?state=open&limit=50") or []
    for p in prs:
        if (p.get("base") or {}).get("ref") != LIVE:
            continue
        head = str((p.get("head") or {}).get("sha") or "")
        ok, cls, why, ht = tc.verdict(git, live, head, pin, policy)
        if ok or not ht:
            continue
        n = p.get("number")
        if cls == "CONTRACT" and ht not in (pin.get("contract_tried") or {}):
            _c, _w, _m, areas = tc.classify_full(git, live, head, [], policy)
            passed, what = (suites or run_suites)(cfg, folder, head, areas, policy)
            pin.setdefault("contract_tried", {})[ht] = {"head": head, "ok": passed, "at": _now()}
            if passed:
                pin.setdefault("contract_ok", {})[ht] = areas
            out.append(f"PR #{n} CONTRACT {areas}: {'passed' if passed else 'FAILED'}")
            log(rlog, {"class": "CONTRACT", "pr": n, "head": head, "t_hash": ht,
                       "areas": areas, "ok": passed, "evidence": what[-200:]})
        if cls in ("TRUST", "CONTRACT") and ht not in (pin.get("authorized") or {}):
            c = owner_typed(forge(f"/repos/quant/quant/issues/{n}/comments?limit=50") or [], head)
            if c:
                pin.setdefault("authorized", {})[ht] = {"head": head, "pr": n,
                                                        "comment": c.get("id"), "at": _now()}
                out.append(f"PR #{n} AUTHORIZED by the owner at {head[:12]}")
                log(rlog, {"class": "AUTHORIZED", "pr": n, "head": head, "t_hash": ht})
    save_pin(pin_path, pin)
    return out


def init(folder: Path, src: str, ref: str, live: str) -> dict[str, Any]:
    """The one bootstrap (the install the owner requested): copy the checker and the contract
    suites from `ref` (the Audit-CLEARed installer commit), measure T there, and write the pin."""
    def git(*a: str) -> str:
        return subprocess.run(["git", "-c", "safe.directory=*", "-C", src, *a],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              check=True, timeout=300).stdout
    for n in CHECKER_FILES:
        (folder / n).write_text(git("show", f"{ref}:ops/box_git/{n}"), encoding="utf-8")
    tc = _load_checker(folder)
    policy = tc.load_policy((folder / "TRUST_SET.json").read_text(encoding="utf-8"))
    refresh(folder, git, ref, policy)
    t = tc.t_hash(git, ref, policy)
    pin = {"t_hash": t, "bootstrap_head": ref, "bootstrap_base": live, "live": live,
           "at": _now(), "by": "bootstrap: the install the owner requested (2026-11-19 20:22Z)",
           "history": [], "files": folder_hashes(folder)}
    archive(folder, t)
    save_pin(folder / "pin.json", pin)
    return pin


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config")
    ap.add_argument("--init", nargs=3, metavar=("SRC_REPO", "BOOT_SHA", "LIVE_SHA"))
    a = ap.parse_args(argv)
    if a.init:
        pin = init(HERE, *a.init)
        print(f"pinned {pin['t_hash']} at {a.init[1][:12]}")
        return 0
    if not a.config:
        ap.error("--config is required")
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    for line in one_pass(cfg):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
