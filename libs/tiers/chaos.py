"""CONTINUAL RECOVERY EXPERIMENTS (Tier S layer 42) -- against the twin, never the live terminal.

Two kinds of experiment, both sandboxed by construction:

  1. FAULT CAMPAIGNS ON THE PROTOCOL TWIN. The model checker (`libs/tiers/formal.py`) is
     exhaustive but bounded (at most two crashes, two republishes). A campaign walks thousands of
     LONG random traces through the same transition system with faults injected at a chosen rate
     -- kill the process, restart it, republish the allocation, deliver a late bar, revoke a
     certificate -- and counts invariant breaches, duplicate orders and lost fills beyond the
     checker's bound.

  2. CORRUPTION DRILLS ON THE DESK'S OWN LOADERS. Each drill copies a real state file into a
     temporary directory, damages the COPY (truncate, garbage bytes, empty, wrong type, missing),
     and calls the desk's real loader on it. A loader passes when it FAILS CLOSED -- returns its
     documented empty answer or raises a clean error -- and fails when it returns something that
     looks like valid state built from garbage. The live file is never opened for writing.

Killing processes or disconnecting MT5 on the trading box is NOT done here and never will be
without the principal's words; the twin is where the desk practises dying.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from libs.tiers import formal

CORRUPTIONS: tuple[str, ...] = ("truncate", "garbage", "empty", "wrong_type", "missing")


def campaign(p: formal.Protocol | None = None, *, runs: int = 2000, depth: int = 60,
             fault_rate: float = 0.3, seed: int = 0) -> dict[str, Any]:
    p = p or formal.Protocol()
    rng = np.random.default_rng(seed)
    breaches: dict[str, int] = {}
    example: dict[str, list[str]] = {}
    crashes = restarts = 0
    for _ in range(runs):
        s = formal.State()
        trace: list[str] = []
        for _step in range(depth):
            succ = list(formal.successors(s, p, max_publish=10**6, max_crash=10**6,
                                          max_late=10**6))
            if not succ:
                break
            faults = [x for x in succ if x[0] in ("crash", "publish(0)", "publish(1)",
                                                  "feed_late", "revoke_cert")]
            normal = [x for x in succ if x not in faults]
            pool = faults if (faults and (not normal or rng.random() < fault_rate)) else normal
            act, s = pool[int(rng.integers(len(pool)))]
            trace.append(act)
            crashes += act == "crash"
            restarts += act == "restart"
            for name, inv in formal.INVARIANTS.items():
                if not inv(s):
                    breaches[name] = breaches.get(name, 0) + 1
                    example.setdefault(name, list(trace))
            if any(not inv(s) for inv in formal.INVARIANTS.values()):
                break
    return {"runs": runs, "depth": depth, "fault_rate": fault_rate, "crashes": crashes,
            "restarts": restarts, "breaches": breaches, "examples": example,
            "clean": not breaches, "protocol": p.__dict__}


def _damage(path: Path, how: str) -> None:
    if how == "missing":
        path.unlink(missing_ok=True)
        return
    if how == "empty":
        path.write_bytes(b"")
        return
    if how == "truncate":
        data = path.read_bytes()
        path.write_bytes(data[: max(1, len(data) // 2)])
        return
    if how == "garbage":
        path.write_bytes(b"\x00\xff{{not json" * 7)
        return
    if how == "wrong_type":
        path.write_text(json.dumps(["a", "list", "where", "an", "object", "belongs"]),
                        encoding="utf-8")
        return
    raise ValueError(how)


def drill(name: str, source: Path, loader: Callable[[Path], Any],
          is_empty: Callable[[Any], bool], corruptions: Iterable[str] = CORRUPTIONS
          ) -> dict[str, Any]:
    """Damage a COPY of `source` every way in `corruptions`; the loader must fail closed."""
    rows: dict[str, str] = {}
    if not source.exists():
        return {"drill": name, "status": "UNMEASURED", "why": f"{source.name} absent here"}
    with tempfile.TemporaryDirectory(prefix="tier_s_chaos_") as tmp:
        for how in corruptions:
            copy = Path(tmp) / source.name
            shutil.copy2(source, copy)
            _damage(copy, how)
            try:
                out = loader(copy)
                rows[how] = "FAILED_CLOSED" if is_empty(out) else "ACCEPTED_GARBAGE"
            except Exception as exc:  # a clean raise is failing closed too
                rows[how] = f"RAISED:{type(exc).__name__}"
    bad = [k for k, v in rows.items() if v == "ACCEPTED_GARBAGE"]
    return {"drill": name, "results": rows, "status": "PASS" if not bad else "FAIL",
            "accepted_garbage": bad}


def ablation_campaigns(runs: int = 600, seed: int = 0) -> dict[str, Any]:
    base = formal.Protocol()
    out = {"desk": campaign(base, runs=runs, seed=seed)}
    for knob in ("reconcile_on_restart", "idempotent_client_id", "persist_before_send"):
        out[f"without_{knob}"] = campaign(replace(base, **{knob: False}), runs=runs, seed=seed)
    return out


# ---------------------------------------------------------------- real process kills, sandboxed
_WRITER = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from libs.tiers import truth_kernel as tk
j = tk.Journal(Path(sys.argv[2]))
try:
    j.load()
except Exception as exc:                       # a torn tail the loader cannot read
    print(json.dumps({"load_error": type(exc).__name__}), flush=True)
    sys.exit(3)
done = [int(n.payload.get("seq", -1)) for n in j.nodes() if n.kind == "order"]
start = max(done) + 1 if done else 0           # reconcile: resume after the last journalled
print(json.dumps({"resumed_at": start}), flush=True)
for seq in range(start, int(sys.argv[3])):
    j.put("order", {"seq": seq, "intent": "drill"})
    time.sleep(float(sys.argv[4]))
"""


def process_kill_drill(root: Path, *, orders: int = 400, kills: int = 5, seed: int = 0,
                       step_s: float = 0.01, timeout_s: float = 60.0) -> dict[str, Any]:
    """KILL A REAL PROCESS, IN A SANDBOX, AND CHECK WHAT SURVIVES.

    A child Python process writes `orders` intents through the desk's real journal
    (`truth_kernel.Journal`) into a TEMPORARY directory; the parent SIGKILLs it at a random
    moment `kills` times, restarting it each time (the child reconciles from the journal and
    resumes). The verdict counts what a crash costs: a torn tail the loader cannot read, a
    broken hash chain, a duplicated or a lost intent. Nothing outside the temp directory is
    touched; the live terminal and its journal are never in reach of this function."""
    import subprocess
    import sys
    import time

    rng = np.random.default_rng(seed)
    out: dict[str, Any] = {"orders": orders, "kills_planned": kills, "kills": 0, "restarts": 0,
                           "load_failures": 0, "sandbox": "tempdir"}
    with tempfile.TemporaryDirectory(prefix="tier_s_kill_") as td:
        jp = Path(td) / "journal.jsonl"

        def spawn() -> subprocess.Popen[str]:
            return subprocess.Popen([sys.executable, "-c", _WRITER, str(root), str(jp),
                                     str(orders), str(step_s)], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True)
        deadline = time.monotonic() + timeout_s
        proc = spawn()
        while time.monotonic() < deadline:
            if out["kills"] < kills:
                time.sleep(float(rng.uniform(0.35, 0.9)))
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                    out["kills"] += 1
            else:
                try:
                    proc.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            text, _ = proc.communicate()             # drains and closes the pipe
            rc = proc.returncode
            if rc == 3 or '"load_error"' in (text or ""):
                out["load_failures"] += 1
                break                               # the desk could not restart: a finding
            if rc == 0:
                break                               # every intent written: the run is over
            proc = spawn()
            out["restarts"] += 1
        if proc.poll() is None:
            proc.kill()
        proc.communicate()
        ver = truth_kernel_verify(jp)
        seqs: list[int] = []
        if ver.get("ok"):
            for line in jp.read_text("utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("kind") == "order":
                        seqs.append(int(row["payload"]["seq"]))
        dup = len(seqs) - len(set(seqs))
        lost = sorted(set(range(orders)) - set(seqs)) if ver.get("ok") else None
        out.update({"chain_ok": bool(ver.get("ok")), "chain": ver, "journalled": len(seqs),
                    "duplicates": dup, "lost": (len(lost) if lost is not None else None)})
    out["status"] = ("FAIL" if out["load_failures"] or not out["chain_ok"] or out["duplicates"]
                     or out["lost"] else "PASS")
    return out


def truth_kernel_verify(path: Path) -> dict[str, Any]:
    from libs.tiers import truth_kernel
    try:
        return truth_kernel.Journal(path).verify()
    except (ValueError, KeyError) as exc:          # a torn line is not a verified chain
        return {"ok": False, "why": f"{type(exc).__name__}: unreadable line"}
