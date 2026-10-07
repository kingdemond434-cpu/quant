"""Re-solve the certified book when its inputs move, not on the hour (principal 2026-10-07: "wby
isnt it every minute or compute").

`research/kelly_survival.py --book` sizes the whole certified book inside survival. It ran on the
hourly cycle, so a fill at :05 was sized against a book solved for the state before it until :00.
This organ rides the allocator trigger's pass (`allocator_trigger.poll`, every ~20s) and re-solves
the book on the SAME pass that sees any of:

  fill            a fill, bracket or netting change in gateway_state.json
  equity          Fusion or E8 equity 1% away from the level the book was last solved at
  certificate     a certificate arriving or dying (the canonical store, the sleeve registry)
  cost_regime     a book symbol's spread or swap moving a whole log2 bucket, or a swap flipping sign
  allocation      a new pf_allocation decision or a re-drawn world tensor

THE FINGERPRINT IS THE GATE. Every input is reduced to a bucketed signature and the whole set is
hashed (equity is compared to its solved level instead); an unchanged hash never re-solves, so a quiet market costs a few file reads per pass and
no compute. A changed hash that arrives inside the gap (`MIN_BOOK_GAP_S`) is not dropped: the
solved fingerprint is only advanced by a solve that finished, so the next pass after the gap
serves it. The hourly `kelly_survival` leg stays as the backstop.

The book is an artifact (reports/KELLY_SURVIVAL.json -> `book`). Whatever reads it must read it
per pass, never cache it across passes, so the newest solve is the one an order is sized from.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
REPORTS = DESK / "reports"
GATEWAY_STATE = DATA / "gateway_state.json"
ACCOUNT = DATA / "account_state.json"
E8_GOLD = REPORTS / "E8_GOLD.json"
CERT_STORE = REPORTS / "UNIVERSAL_SURVIVORS.json"
CERT_CANON = DATA / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVE_REGISTRY = DATA / "sleeve_registry.json"
QUOTES = DATA / "cost_truth_quotes.json"
ALLOCATION = REPORTS / "pf_allocation.json"
WORLDS = DATA / "pf_allocator_cache" / "worlds.npz"
KELLY = REPORTS / "KELLY_SURVIVAL.json"

FILL_KEYS = ("position", "netting_booked", "brackets", "lot")
#: A 1% equity move (in logs, against the equity the book was LAST SOLVED at) re-sizes every
#: fraction by 1%, the smallest change worth a solve. Measured from the solved level, not a fixed
#: grid, so equity hovering on a grid line cannot re-solve on every tick.
EQUITY_STEP = 0.01
#: The fewest seconds between two book solves. The solve is ~1 min on the build box; a burst of
#: fills inside the gap is served by one solve after it, never dropped.
MIN_BOOK_GAP_S = 60.0
BOOK_BUDGET_S = 900.0
ALWAYS_WATCHED = ("XAUUSD",)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _equity(v: Any) -> float | None:
    f = _num(v)
    return f if f is not None and f > 0 else None


def _equity_moved(now_eq: list[float | None], solved_eq: list[float | None]) -> bool:
    for a, b in zip(now_eq, solved_eq, strict=True):
        if (a is None) != (b is None):
            return True
        if a is not None and b is not None and abs(math.log(a / b)) >= math.log1p(EQUITY_STEP):
            return True
    return False


def _log2_bucket(v: Any) -> int | None:
    f = _num(v)
    if f is None:
        return None
    if f == 0:
        return 0
    # Signed so a swap flipping sign is a change; +100 keeps sub-unit magnitudes off zero.
    return int(math.copysign(math.floor(math.log2(abs(f))) + 100, f))


def book_symbols() -> list[str]:
    """The symbols the current book holds heat on, plus gold: the costs that can move it."""
    doc = _read(KELLY) or {}
    syms = set(ALWAYS_WATCHED)
    for venue in ("fusion", "e8"):
        for key in ((((doc.get("book") or {}).get(venue) or {}).get("heat")) or {}):
            head = str(key).split("_", 1)[0]
            if len(head) >= 6 and head.isupper():
                syms.add(head)
    return sorted(syms)


def components() -> dict[str, Any]:
    """Each input, bucketed. Equal components mean an unchanged book; that is the whole contract."""
    gs = _read(GATEWAY_STATE)
    gs = gs if isinstance(gs, dict) else {}
    acct = _read(ACCOUNT)
    e8 = _read(E8_GOLD)
    store = _read(CERT_STORE)
    if not (isinstance(store, dict) and store.get("survivors")):
        store = _read(CERT_CANON)
    certs = sorted(((store or {}).get("survivors") or {}).keys()) if isinstance(store, dict) else []
    reg = _read(SLEEVE_REGISTRY)
    qdoc = _read(QUOTES)
    quotes = (qdoc.get("symbols") or {}) if isinstance(qdoc, dict) else {}
    costs = {}
    for sym in book_symbols():
        q = quotes.get(sym) or {}
        costs[sym] = [_log2_bucket(q.get("live_spread_pts", q.get("spread"))),
                      _log2_bucket(q.get("swap_long")), _log2_bucket(q.get("swap_short"))]
    alloc = _read(ALLOCATION)
    try:
        worlds_at = round(WORLDS.stat().st_mtime)
    except OSError:
        worlds_at = None
    return {
        "fill": _hash({k: gs.get(k) for k in FILL_KEYS}),
        "equity": [_equity(gs.get("equity") if gs.get("equity") is not None
                           else (acct or {}).get("equity") if isinstance(acct, dict) else None),
                   _equity((e8 or {}).get("equity") if isinstance(e8, dict) else None)],
        "certificate": _hash([certs, (reg or {}).get("sleeves") if isinstance(reg, dict) else None]),
        "cost_regime": costs,
        "allocation": [(alloc or {}).get("decision_id") if isinstance(alloc, dict) else None,
                       worlds_at],
    }


def _solve(budget_s: float) -> dict[str, Any]:
    t = time.time()
    try:
        r = subprocess.run([sys.executable, "-u", str(DESK / "research" / "kelly_survival.py"),
                            "--book"], capture_output=True, text=True, timeout=budget_s,
                           cwd=str(DESK.parent.parent))
    except subprocess.TimeoutExpired:
        return {"rc": None, "wall_s": round(time.time() - t, 1), "tail": "timeout"}
    return {"rc": r.returncode, "wall_s": round(time.time() - t, 1),
            "tail": (r.stdout or r.stderr or "")[-300:]}


def poll(state: dict[str, Any], now: float, *, solve: bool = True,
         solver: Callable[[float], dict[str, Any]] | None = None,
         budget_s: float = BOOK_BUDGET_S) -> dict[str, Any]:
    """One pass. `state` is the allocator trigger's `book` block, updated in place."""
    comp = components()
    equity = comp.pop("equity")
    fp = _hash(comp)
    state["observed_at"], state["observed_fp"], state["components"] = _iso(now), fp, comp
    if not state.get("solved_fp"):
        # FIRST SIGHT IS THE BASELINE the hourly solve already sized against, not a change.
        state.update(solved_fp=fp, solved_components=comp, solved_equity=equity)
        return {"event": "baseline", "fp": fp}
    solved = state.get("solved_components") or {}
    moved = sorted(k for k in comp if solved.get(k) != comp[k])
    if _equity_moved(equity, state.get("solved_equity") or [None, None]):
        moved = sorted([*moved, "equity"])
    if not moved:
        return {"event": "unchanged", "fp": fp}
    last = float(state.get("last_solve_at") or 0.0)
    if not solve or now < last + MIN_BOOK_GAP_S:
        return {"event": "deferred", "fp": fp, "moved": moved,
                "why": "solve disabled" if not solve else
                f"next book solve allowed at {_iso(last + MIN_BOOK_GAP_S)}"}
    res = (solver or _solve)(budget_s)
    state["last_solve_at"] = now
    ok = res.get("rc") == 0
    if ok:
        # Only a FINISHED solve advances the solved state, so a failure is retried next pass.
        state.update(solved_fp=fp, solved_components=comp, solved_equity=equity,
                     solved_at=_iso(now))
    state["last_result"] = {"rc": res.get("rc"), "wall_s": res.get("wall_s"), "moved": moved}
    return {"event": "solved" if ok else "solve_failed", "fp": fp, "moved": moved,
            "rc": res.get("rc"), "wall_s": res.get("wall_s")}
