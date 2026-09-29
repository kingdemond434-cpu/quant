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
