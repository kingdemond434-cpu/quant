"""WHICH HOURS OF THE DAY THIS DESK HAS AN EDGE IN, and which hours its capital sits idle.

THE GAP THIS MEASURES. `pf_allocator` solves posterior E[log W] per SLEEVE and is good at it.
Nothing solves it per SESSION, and the book has drifted accordingly: measured 2026-09-14, nine of
the ten largest heat allocations are `_asia` sleeves and roughly 77% of the live book fires in one
window. That is two costs, not one. Capital is idle for most of the day, and -- the larger one --
sleeves that trade the same hours CO-MOVE even when their mechanisms differ, so a book
concentrated in one session carries correlation that no per-sleeve view can see. `n_eff` was 5.59
against a ceiling of 6.1 at the measured rho; session concentration is part of why that ceiling is
so low.

WHY IT COULD NOT BE MEASURED BEFORE. The forward clocks did not record their session. All 228
rows in `shadow_state.json` answered "?" to the only question that matters here, while the
information was sitting in plain sight in their own keys -- `GBPMXN_overnight_gap_decay_asia`,
`USDMXN.overnight_gap_decay.asia`. A dimension nobody records is a dimension nobody can allocate.

THIS FILE DECIDES NOTHING AND SIZES NOTHING. It publishes a measurement and a gap. That is
deliberate and it is not timidity: a second allocator stacked on top of `pf_allocator` would
shrink twice, and growth governance Rule 1 requires any risk reduction to prove it raises robust
forward E[log W]. The honest use of this artifact is ADDITIVE -- it tells the research side which
windows to hunt so the desk can fill idle hours with NEW independent bets, which is Rule 2, and
it never asks the capital side to take anything away from a window that is earning.

    python desks/mt5/research/session_allocator.py
"""
from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
SHADOW = BASE / "reports" / "shadow" / "shadow_state.json"
ALLOCATION = BASE / "reports" / "pf_allocation.json"
OUT = BASE / "reports" / "SESSION_ALLOCATION.json"

#: The desk's own windows, and the UTC hours each one owns. Hours are what make "idle" a
#: measurable claim rather than an impression: a window with no sleeve is a block of the clock
#: during which this desk cannot make money however good its mechanisms are.
#:
#: `continuous` is not a session and is counted apart -- a sleeve that may fire at any hour is not
#: evidence that any particular hour is covered.
SESSION_HOURS: dict[str, tuple[int, ...]] = {
    "asia": (0, 1, 2, 3, 4, 5, 6, 7),
    "london_am": (8, 9, 10, 11),
    "overlap": (12, 13, 14, 15),
    "new_york": (16, 17, 18, 19),
    "afternoon": (12, 13, 14, 15, 16),
    "ny_open": (13, 14),
}

#: Recognised session tokens, longest first so `london_am` is never matched as `london`.
_TOKENS = tuple(sorted(set(SESSION_HOURS) | {"continuous", "all"}, key=len, reverse=True))


def session_of(key: str, row: dict[str, Any] | None = None) -> str:
    """The window a clock trades, read from its row and falling back to its KEY.

    The key is a legitimate source here and not a guess: the desk MINTS these keys by joining
    symbol, family and selector, so the selector is present by construction. Reading it back is
    recovering a field that was flattened, not inferring one that was never set.

    UNCLASSIFIED is returned rather than a default. Calling an unknown window `continuous` would
    silently claim the whole clock is covered, which is the opposite of the truth and exactly the
    absence-as-permission failure the desk's laws forbid.
    """
    for field in ("selector", "window", "session"):
        v = str((row or {}).get(field) or "").strip().lower()
        if v in SESSION_HOURS or v in ("continuous", "all"):
            return v
    low = str(key).lower()
    for tok in _TOKENS:
        if re.search(rf"(^|[._]){re.escape(tok)}([._]|$)", low):
            return tok
    return "UNCLASSIFIED"


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def measure() -> dict[str, Any]:
    """Edge and deployed heat per window, plus the hours nothing covers."""
    state = _read(SHADOW)
    book = (_read(ALLOCATION) or {}).get("book") or {}

    per: dict[str, dict[str, Any]] = {}
    for key, row in (state.items() if isinstance(state, dict) else []):
        if not isinstance(row, dict) or "n" not in row:
            continue
        sess = session_of(key, row)
        d = per.setdefault(sess, {"clocks": 0, "trades": 0, "cum_r": 0.0, "heat": 0.0})
        d["clocks"] += 1
        d["trades"] += int(row.get("n", 0) or 0)
        d["cum_r"] += float(row.get("cum_r", 0.0) or 0.0)

    # Heat is joined on the SLEEVE NAME the allocator uses, which carries the same selector token.
    for name, frac in book.items():
        sess = session_of(str(name), None)
        per.setdefault(sess, {"clocks": 0, "trades": 0, "cum_r": 0.0, "heat": 0.0})
        per[sess]["heat"] += float(frac or 0.0)

    total_heat = sum(v["heat"] for v in per.values()) or 1.0
    for v in per.values():
        n = v["trades"]
        v["exp_r"] = round(v["cum_r"] / n, 4) if n else None
        # Standard error of the mean R, so a window with three trades cannot out-argue one with
        # three hundred. UNMEASURED when there is nothing to divide.
        v["se"] = round(1.0 / math.sqrt(n), 4) if n else None
        v["heat_share"] = round(v["heat"] / total_heat, 4)
        v["heat"] = round(v["heat"], 6)
        v["cum_r"] = round(v["cum_r"], 3)

    covered: set[int] = set()
    for sess, v in per.items():
        if v["clocks"] and sess in SESSION_HOURS:
            covered |= set(SESSION_HOURS[sess])
    idle = sorted(set(range(24)) - covered)

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "authority": ("MEASUREMENT ONLY -- this file sizes nothing and vetoes nothing. "
                      "pf_allocator remains the only thing that allocates capital."),
        "by_session": dict(sorted(per.items(), key=lambda kv: -kv[1]["trades"])),
        "idle_utc_hours": idle,
        "n_idle_hours": len(idle),
        "note": ("idle means no forward clock trades that hour. It is the research side's target "
                 "list: fill it with NEW independent mechanisms (Rule 2), never by moving heat "
                 "off a window that is earning -- Rule 1 would require proving that "
                 "raises E[log W])"),
    }


def main() -> int:
    doc = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"session allocation -> {OUT.name}")
    print(f"{'window':16} {'clocks':>7} {'trades':>7} {'exp_R':>8} {'+/-':>7} {'heat share':>11}")
    for sess, v in doc["by_session"].items():
        er = "UNMEASURED" if v["exp_r"] is None else f"{v['exp_r']:.4f}"
        se = "" if v["se"] is None else f"{v['se']:.4f}"
        print(f"{sess:16} {v['clocks']:7} {v['trades']:7} {er:>8} {se:>7} {v['heat_share']:10.1%}")
    print(f"\nidle UTC hours ({doc['n_idle_hours']}/24): {doc['idle_utc_hours']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
