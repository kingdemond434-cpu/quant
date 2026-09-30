"""THE SHADOW DESK (Tier S layer 28): candidate code or config replayed beside live, in a sandbox.

The digital twin (`libs/tiers/twin.py`) pairs an incumbent's outcome with a challenger's. Until
this module the only pairs it could form were BOOKS (the allocator's weights times realised R):
a candidate CHANGE TO THE CODE, or to a sleeve's configuration, was never run at all before it
reached the box. This runs it.

WHAT A SHADOW RUN IS. Two trees are materialised side by side in a temporary directory:

    incumbent   the sealed live release's code (`git archive <sha>`)
    candidate   the code about to be adopted (`git archive <sha>`), or the incumbent's code with a
                candidate CONFIG (per-sleeve parameter overrides) laid over the sleeve rows

Both are handed the SAME INPUTS, snapshotted once: the live sleeves' rows and the tail of their
bars, copied byte-identically into each tree's own `desks/mt5/data/universe/` (the package-relative
path every family reads), with the snapshot's hashes published so "the same inputs" is checkable.
Each side's `mt5desk` then decides -- `family_call.signals`, the one call shape the gateway, the
forward clock and the gauntlet share -- in its own Python process. One neutral replay (next-open
entry, intrabar stop before target, TTL exit, the registry's spread charged once) scores both
sides' signals, so the only difference between the two columns is the candidate.

SANDBOXED BY CONSTRUCTION, and never the live terminal:
  * each side runs in a SEPARATE PROCESS whose `sys.path` starts at its own materialised tree, with
    `PYTHONPATH` dropped, so neither the live clone nor the other side is importable;
  * `MetaTrader5` is installed in `sys.modules` as a module whose every attribute access RAISES and
    is counted, BEFORE anything else is imported -- the real terminal package is never loaded, and
    a candidate that reaches for it is reported (`terminal_touches`) rather than served;
  * `MT5_DESK_ROOT` points every configured desk path at the sandbox tree, so state, intents and
    logs a candidate might write land in the temporary directory, which is deleted afterwards.

THE PAIRS. Per sleeve, per day of trade entry: (day, incumbent R, candidate R), summed across
sleeves into one daily pair list, which is what `twin.evaluate` judges -- and it counts only days
after the challenger was registered, so a candidate is never proven on history it was written
against. Signal agreement (Jaccard over (time, side)) is published beside the pairs: a code
change that moves no decision is visible as agreement 1.0, a determinism check for free.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "TWIN.json"

#: the code a sleeve decision imports: the desk package, the research modules that rebuild a
#: family's runtime inputs (`family_inputs` -> `orthogonal_sweep`) and the shared libraries
CODE_PATHS: tuple[str, ...] = ("desks/mt5/mt5desk", "desks/mt5/research", "libs")
WORKTREE = "WORKTREE"
BARS = 3000
MAX_SLEEVES = 12
TIMEOUT_S = 240.0
#: params keys that NAME another instrument whose bars the family loads
PEER_KEYS: tuple[str, ...] = ("peer_symbol", "input_symbol", "factor_symbols", "peers")


@dataclass(frozen=True)
class Candidate:
    """A challenger the shadow desk can replay: a code ref, a config overlay, or both."""
    name: str
    ref: str
    config: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


# ------------------------------------------------------------------------------ the child

#: The child's program, kept as source so it shares nothing with this process. argv: the tree,
#: the spec (sleeves, their bars' file names), the output path.
_CHILD = r'''
import json, os, sys, types
tree, spec_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
touches = []
class _Forbidden(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        touches.append(name)
        raise RuntimeError("shadow desk: the live terminal is never reached from a sandbox")
sys.modules["MetaTrader5"] = _Forbidden("MetaTrader5")
sys.path[:0] = [tree, os.path.join(tree, "desks", "mt5")]
res = {}
err = None
try:
    import pandas as pd
    from mt5desk.family_call import signals as call
    from mt5desk.family_inputs import resolve, strip_identity_keys
    def family_fn(name):
        fn = None
        try:
            from mt5desk import families
            fn = getattr(families, "family_" + name, None)
        except ImportError:
            fn = None
        if fn is None:
            try:
                from mt5desk import families_orthogonal as fo
                fn = fo.ORTHOGONAL_FAMILIES.get(name)
            except (ImportError, AttributeError):
                fn = None
        return fn
    spec = json.load(open(spec_path, encoding="utf-8"))
    for s in spec["sleeves"]:
        name = s["name"]
        try:
            path = os.path.join(tree, "desks", "mt5", "data", "universe", s["bars"])
            if not os.path.exists(path):
                res[name] = {"unmeasured": "no bars in the snapshot"}
                continue
            bars = pd.read_parquet(path)
            fn = family_fn(s["family"])
            if fn is None:
                res[name] = {"unmeasured": "family %r is in neither registry" % s["family"]}
                continue
            extra, why = resolve(s["symbol"], s["family"], dict(s["params"]), bars)
            if extra is None:
                res[name] = {"unmeasured": "inputs unresolvable: %s" % why}
                continue
            p = {**strip_identity_keys(s["family"], dict(s["params"])), **extra}
            if s.get("selector"):
                p["session"] = s["selector"]
            sigs = call(fn, bars, side=int(s["side"]), params=p)
            res[name] = {"signals": [
                {"time": str(getattr(g, "time", "")), "side": int(getattr(g, "side", 0)),
                 "stop": float(getattr(g, "stop", "nan")),
                 "target": float(getattr(g, "target", "nan")),
                 "ttl_bars": int(getattr(g, "ttl_bars", 1) or 1)} for g in sigs]}
        except Exception as exc:
            res[name] = {"unmeasured": ("%s: %s" % (type(exc).__name__, exc))[:200]}
except Exception as exc:
    err = ("%s: %s" % (type(exc).__name__, exc))[:300]
mod = sys.modules.get("MetaTrader5")
json.dump({"results": res, "error": err, "terminal_touches": touches,
           "terminal_module": type(mod).__name__ if mod is not None else None},
          open(out_path, "w", encoding="utf-8"))
'''


# ------------------------------------------------------------------------------ sandbox plumbing

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(ref: str, dest: Path, *, root: Path = ROOT,
                paths: Sequence[str] = CODE_PATHS) -> str:
    """The tree of `ref` (a commit) at `dest`, code paths only. `WORKTREE` copies the files on
    disk instead (the incumbent's code with a config overlay, or a test). Returns the full SHA,
    or `WORKTREE`."""
    dest.mkdir(parents=True, exist_ok=True)
    if ref == WORKTREE:
        for rel in paths:
            src = root / rel
            if src.is_dir():
                shutil.copytree(src, dest / rel, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif src.exists():
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / rel)
        return WORKTREE
    full = subprocess.run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()
    present = [p for p in paths if subprocess.run(
        ["git", "cat-file", "-e", f"{full}:{p}"], cwd=root, capture_output=True).returncode == 0]
    if not present:
        raise OSError(f"none of {list(paths)} exists at {full[:12]}")
    blob = subprocess.run(["git", "archive", "--format=tar", full, "--", *present], cwd=root,
                          check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(dest, filter="data")
    return full


def _needed(sleeve: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(symbol, timeframe) files a sleeve reads: its own, and any peer its params name."""
    tf = str(sleeve.get("timeframe") or "H1").upper()
    out = [(str(sleeve["symbol"]), tf)]
    params = sleeve.get("params") or {}
    for k in PEER_KEYS:
        v = params.get(k)
        for s in ([v] if isinstance(v, str) else list(v) if isinstance(v, list | tuple) else []):
            if s:
                out.append((str(s), "H1"))
    return out


def snapshot_inputs(sleeves: Sequence[Mapping[str, Any]], dest: Path, *,
                    universe: Path = UNIVERSE, bars: int = BARS) -> dict[str, Any]:
    """The ONE copy of the live inputs both sides read: each needed parquet's tail and the
    registry. Returns {file: sha256} -- the fingerprint both trees must match."""
    import pandas as pd
    dest.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    reg = universe / "universe.json"
    if reg.exists():
        shutil.copy2(reg, dest / "universe.json")
        files["universe.json"] = _sha(dest / "universe.json")
    for s in sleeves:
        for sym, tf in _needed(s):
            name = f"{sym}_{tf}.parquet"
            if name in files:
                continue
            src = universe / name
            if not src.exists():
                continue
            try:
                pd.read_parquet(src).tail(bars).to_parquet(dest / name)
            except (OSError, ValueError):
                continue
            files[name] = _sha(dest / name)
    return files


def _install_inputs(snapshot: Path, tree: Path) -> dict[str, str]:
    target = tree / "desks" / "mt5" / "data" / "universe"
    target.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for f in sorted(snapshot.iterdir()):
        shutil.copy2(f, target / f.name)
        out[f.name] = _sha(target / f.name)
    return out


def _child_env(tree: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "MT5_DESK_ROOT"}}
    env.update({"MT5_DESK_ROOT": str(tree / "desks" / "mt5"),
                "PYTHONDONTWRITEBYTECODE": "1", "QUANT_SHADOW_DESK": "1"})
    return env


def run_side(tree: Path, sleeves: Sequence[Mapping[str, Any]], work: Path, label: str, *,
             timeout: float = TIMEOUT_S) -> dict[str, Any]:
    """One side's decisions over the snapshot, in its own process. Never raises."""
    spec = work / f"{label}_spec.json"
    out = work / f"{label}_out.json"
    rows = [{**dict(s), "bars": f"{s['symbol']}_{str(s.get('timeframe') or 'H1').upper()}"
             f".parquet"} for s in sleeves]
    spec.write_text(json.dumps({"sleeves": rows}, default=str), "utf-8")
    try:
        proc = subprocess.run([sys.executable, "-c", _CHILD, str(tree), str(spec), str(out)],
                              cwd=work, env=_child_env(tree), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"results": {}, "error": f"timed out after {timeout:g}s", "terminal_touches": []}
    if not out.exists():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
        return {"results": {}, "error": f"child exited {proc.returncode}: {tail[0][:200]}",
                "terminal_touches": []}
    doc: dict[str, Any] = json.loads(out.read_text("utf-8"))
    return doc


# ------------------------------------------------------------------------------ neutral scoring

def _cost_px(meta: Mapping[str, Any]) -> float:
    ts = float(meta.get("tick_size", 0.0) or meta.get("point", 0.0) or 0.0)
    return max(0.0, float(meta.get("median_spread_pts", 0.0) or 0.0) * ts)


def replay(bars: Any, signals: Iterable[Mapping[str, Any]], cost_px: float = 0.0
           ) -> list[tuple[str, float]]:
    """(entry day, R) per trade: next-open entry, intrabar stop before target, TTL exit at the
    open, one position at a time, the spread charged once. The SAME judge for both sides."""
    import numpy as np
    import pandas as pd
    o = np.asarray(bars["open"], dtype="float64")
    h = np.asarray(bars["high"], dtype="float64")
    lo = np.asarray(bars["low"], dtype="float64")
    idx = pd.DatetimeIndex(bars.index)
    ns = np.asarray(idx.as_unit("ns").asi8, dtype="int64")
    out: list[tuple[str, float]] = []
    last_exit = -1
    for g in signals:
        try:
            t = pd.Timestamp(g["time"])
            if idx.tz is not None and t.tzinfo is None:
                t = t.tz_localize(idx.tz)
            elif idx.tz is None and t.tzinfo is not None:
                t = t.tz_convert("UTC").tz_localize(None)
            i = int(np.searchsorted(ns, t.value, side="right"))
        except (ValueError, TypeError, KeyError):
            continue
        side = 1 if int(g.get("side", 1)) >= 0 else -1
        stop, target = float(g.get("stop", math.nan)), float(g.get("target", math.nan))
        if i <= 0 or i >= len(idx) - 1 or i <= last_exit:
            continue
        entry = float(o[i])
        sd = abs(entry - stop)
        if not (entry > 0) or not (sd > 0) or not math.isfinite(sd):
            continue
        ttl = max(1, int(g.get("ttl_bars", 1) or 1))
        exit_px, held = None, 0
        for j in range(i, min(len(idx), i + ttl)):
            held = j - i + 1
            if (side > 0 and lo[j] <= stop) or (side < 0 and h[j] >= stop):
                exit_px = stop
            elif math.isfinite(target) and ((side > 0 and h[j] >= target)
                                            or (side < 0 and lo[j] <= target)):
                exit_px = target
            if exit_px is not None:
                break
        if exit_px is None:
            k = min(i + ttl, len(idx) - 1)
            exit_px, held = float(o[k]), k - i + 1
        last_exit = i + held - 1
        out.append((str(idx[i].date()), (exit_px - entry) / sd * side - cost_px / sd))
    return out


def agreement(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]]) -> float | None:
    """Jaccard of the two decision sets over (time, side); None when neither side decided."""
    sa = {(str(x.get("time")), int(x.get("side", 0))) for x in a}
    sb = {(str(x.get("time")), int(x.get("side", 0))) for x in b}
    if not sa and not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def pair(inc: Mapping[str, Any], cha: Mapping[str, Any], sleeves: Sequence[Mapping[str, Any]],
         bars_dir: Path, meta: Mapping[str, Any]) -> dict[str, Any]:
    """Per-sleeve rows and the daily (day, incumbent R, candidate R) pairs across sleeves."""
    import pandas as pd
    rows: list[dict[str, Any]] = []
    daily_inc: dict[str, float] = defaultdict(float)
    daily_cha: dict[str, float] = defaultdict(float)
    for s in sleeves:
        name = str(s["name"])
        a = (inc.get("results") or {}).get(name) or {}
        b = (cha.get("results") or {}).get(name) or {}
        if "signals" not in a or "signals" not in b:
            rows.append({"name": name, "status": "UNMEASURED",
                         "why": a.get("unmeasured") or b.get("unmeasured")
                         or inc.get("error") or cha.get("error") or "no decision returned"})
            continue
        tf = str(s.get("timeframe") or "H1").upper()
        try:
            bars = pd.read_parquet(bars_dir / f"{s['symbol']}_{tf}.parquet")
        except (OSError, ValueError) as exc:
            rows.append({"name": name, "status": "UNMEASURED",
                         "why": f"snapshot bars unreadable: {type(exc).__name__}"})
            continue
        cost = _cost_px(meta.get(str(s["symbol"])) or {})
        ra, rb = replay(bars, a["signals"], cost), replay(bars, b["signals"], cost)
        days: set[str] = set()
        for d, r in ra:
            daily_inc[d] += r
            days.add(d)
        for d, r in rb:
            daily_cha[d] += r
            days.add(d)
        rows.append({"name": name, "symbol": s["symbol"], "family": s["family"],
                     "status": "MEASURED",
                     "incumbent": {"signals": len(a["signals"]), "trades": len(ra),
                                   "sum_r": round(sum(r for _d, r in ra), 6)},
                     "candidate": {"signals": len(b["signals"]), "trades": len(rb),
                                   "sum_r": round(sum(r for _d, r in rb), 6)},
                     "signal_agreement": agreement(a["signals"], b["signals"]),
                     "days": len(days)})
    days_all = sorted(set(daily_inc) | set(daily_cha))
    pairs = [(f"{d}T23:59:59+00:00", round(daily_inc.get(d, 0.0), 8),
              round(daily_cha.get(d, 0.0), 8)) for d in days_all]
    meas = [r for r in rows if r["status"] == "MEASURED"]
    agr = [float(r["signal_agreement"]) for r in meas if r["signal_agreement"] is not None]
    return {"sleeves": rows, "pairs": pairs, "n_measured": len(meas),
            "decision_agreement": round(sum(agr) / len(agr), 6) if agr else None}


# ------------------------------------------------------------------------------ the run

def _overlay(sleeves: Sequence[Mapping[str, Any]],
             config: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for s in sleeves:
        row = dict(s)
        over = config.get(str(s["name"]))
        if over:
            row["params"] = {**dict(s.get("params") or {}), **dict(over)}
        out.append(row)
    return out


def run(candidate: Candidate, incumbent_ref: str, sleeves: Sequence[Mapping[str, Any]], *,
        root: Path = ROOT, universe: Path = UNIVERSE, bars: int = BARS,
        timeout: float = TIMEOUT_S, workdir: Path | None = None) -> dict[str, Any]:
    """Replay `candidate` beside `incumbent_ref` on one snapshot of the live inputs. The whole
    sandbox is deleted on return; nothing outside it is written."""
    sl = [dict(s) for s in sleeves][:MAX_SLEEVES]
    if not sl:
        return {"status": "UNMEASURED", "why": "no replayable live sleeve", "pairs": []}
    base = Path(tempfile.mkdtemp(prefix="shadow_desk_", dir=str(workdir) if workdir else None))
    try:
        snap = base / "inputs"
        files = snapshot_inputs(sl, snap, universe=universe, bars=bars)
        if not any(f.endswith(".parquet") for f in files):
            return {"status": "UNMEASURED", "why": "none of the sleeves' bars is on this host",
                    "pairs": []}
        try:
            inc_sha = materialize(incumbent_ref, base / "incumbent", root=root)
            cha_sha = materialize(candidate.ref, base / "candidate", root=root)
        except (subprocess.CalledProcessError, OSError, tarfile.TarError) as exc:
            return {"status": "UNMEASURED", "why": f"materialise failed: {type(exc).__name__}",
                    "pairs": []}
        inc_in = _install_inputs(snap, base / "incumbent")
        cha_in = _install_inputs(snap, base / "candidate")
        if inc_in != cha_in or inc_in != files:
            return {"status": "UNMEASURED", "why": "the two sides' inputs differ", "pairs": []}
        inc = run_side(base / "incumbent", sl, base, "incumbent", timeout=timeout)
        cha = run_side(base / "candidate", _overlay(sl, candidate.config), base, "candidate",
                       timeout=timeout)
        meta_doc: Any = {}
        if (snap / "universe.json").exists():
            try:
                meta_doc = json.loads((snap / "universe.json").read_text("utf-8-sig"))
            except ValueError:
                meta_doc = {}
        meta = meta_doc if isinstance(meta_doc, dict) else {}
        paired = pair(inc, cha, sl, snap, meta)
        touches = list(inc.get("terminal_touches") or []) + list(cha.get("terminal_touches")
                                                                  or [])
        return {"status": "MEASURED" if paired["n_measured"] else "UNMEASURED",
                "why": None if paired["n_measured"] else "no sleeve decided on both sides",
                "candidate": {"name": candidate.name, "ref": cha_sha,
                              "config_overrides": sorted(candidate.config)},
                "incumbent": {"ref": inc_sha},
                "same_code": inc_sha == cha_sha and not candidate.config,
                "inputs": {"files": files, "bars_per_file": bars},
                "sandbox": {"terminal_touches": touches,
                            "terminal_module": [inc.get("terminal_module"),
                                                cha.get("terminal_module")],
                            "desk_root": "temporary sandbox tree (deleted)",
                            "errors": [e for e in (inc.get("error"), cha.get("error")) if e]},
                **paired}
    finally:
        shutil.rmtree(base, ignore_errors=True)
