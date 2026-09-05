"""One canonical live release: every decision on the desk names the SHA it was made under.

    LIVE_SHA                 git HEAD of the tree the gateway is running
    CONFIG_HASH              sizing constants + heat law
    SURVIVOR_REGISTRY_HASH   the canonical survivor file
    ALLOCATOR_HASH           the allocator, the proof, the heat policy
    MONEY_PATH_HASH          every module that places, sizes or vetoes an order
    DATA_SCHEMA_VERSION      the PIT stamp fields and the feature-store code version

`build()` computes them from the tree and writes `data/RELEASE.json`; `release_id()` is the
short hash the gateway stamps on every intent and every decision, so a fill weeks later is
attributable to exactly one code state. `verify()` says whether the tree the process is running
in still matches the last written release -- the state fence the audit asked for: no ambiguity
about which SHA is live.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
RELEASE = DESK / "data" / "RELEASE.json"

MONEY_PATH: tuple[str, ...] = (
    "desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/sizing.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py", "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/independence.py", "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/heat_policy.py", "desks/mt5/research/promoter.py",
    "libs/portfolio/robust_elog.py", "libs/portfolio/allocator_proof.py",
    "libs/portfolio/rails.py", "libs/portfolio/capital_modifiers.py",
)
CONFIG_FILES: tuple[str, ...] = ("desks/mt5/mt5desk/gateway_config_fallback.py",
                                 "desks/mt5/research/heat_policy.py")
ALLOCATOR_FILES: tuple[str, ...] = ("desks/mt5/research/pf_allocator.py",
                                    "libs/portfolio/robust_elog.py",
                                    "libs/portfolio/allocator_proof.py",
                                    "desks/mt5/research/heat_policy.py")
SURVIVORS = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"
DATA_SCHEMA_VERSION = "pit-1;features-2026-09-04.1"


def _sha(paths: tuple[str, ...] | list[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(paths):
        p = ROOT / rel
        h.update(rel.encode())
        h.update(p.read_bytes() if p.exists() else b"<absent>")
    return h.hexdigest()[:16]


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build(write: bool = True) -> dict[str, Any]:
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "live_sha": git_head(),
           "config_hash": _sha(CONFIG_FILES), "survivor_registry_hash": _sha((SURVIVORS,)),
           "allocator_hash": _sha(ALLOCATOR_FILES), "money_path_hash": _sha(MONEY_PATH),
           "data_schema_version": DATA_SCHEMA_VERSION, "money_path": list(MONEY_PATH)}
    doc["release_id"] = hashlib.sha256(json.dumps(
        {k: doc[k] for k in ("live_sha", "config_hash", "survivor_registry_hash",
                             "allocator_hash", "money_path_hash", "data_schema_version")},
        sort_keys=True).encode()).hexdigest()[:12]
    if write:
        RELEASE.parent.mkdir(parents=True, exist_ok=True)
        RELEASE.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


_CACHE: dict[str, Any] = {"mtime": None, "id": None}


def release_id() -> str:
    """The stamped id, cached on the release file's mtime; 'unreleased' when none exists."""
    try:
        m = RELEASE.stat().st_mtime
        if _CACHE["mtime"] != m:
            _CACHE["id"] = str(json.loads(RELEASE.read_text("utf-8")).get("release_id"))
            _CACHE["mtime"] = m
        return str(_CACHE["id"])
    except (OSError, ValueError):
        return "unreleased"


def verify() -> dict[str, Any]:
    """Does the running tree match the written release? The one-live-SHA fence."""
    try:
        rec = json.loads(RELEASE.read_text("utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "why": "no RELEASE.json"}
    now = build(write=False)
    diffs = {k: (rec.get(k), now[k]) for k in ("live_sha", "config_hash",
                                                "survivor_registry_hash", "allocator_hash",
                                                "money_path_hash", "data_schema_version")
             if rec.get(k) != now[k]}
    return {"ok": not diffs, "release_id": rec.get("release_id"), "diffs": diffs,
            "why": ("tree matches the written release" if not diffs else
                    f"{len(diffs)} component(s) differ from the written release")}
