"""BREADTH FENCE ON THE JUDGE'S PREFIX: no symbol or asset class may crowd the queue.

`judge_coverage.order_docket` already makes every prefix FAMILY-balanced, and its keff /
occupancy stamps order cells by marginal effective breadth. It does not bound SYMBOL or ASSET
CLASS: measured 2026-11-19, 98% of 11,441 certificates were FX and 72% came from one producer,
because a family-balanced prefix can still be almost all EURUSD-style FX rows (principal
2026-11-20: "all spread out ... not concentrated into one type of thing", for ALL producers).

Every producer's rows reach the judge through this one funnel (merge_hypotheses -> order_docket
-> here -> write), so fencing here hooks every producer, miner and generator at once.

WHAT IT DOES. Within the first `window` rows (the part a pass's judging budget can reach) it
re-orders so that, on every prefix of length n, no symbol holds more than
max(symbol_share * n, 1) + slack rows and no asset class more than class_share * n + slack --
taking the EARLIEST eligible row each step, so the upstream family / keff / prejudge order is
kept wherever the caps allow. Tiers (Audit MF-1): both caps; else the symbol cap alone; else
the least-used symbol (round-robin) when the window holds too few symbols for the caps. The
fence can only ORDER, never starve the judge.

IT ORDERS, IT NEVER REMOVES. Same rows, same count, rows past the window untouched, no gate,
no bar and no trial count moves. Any fault returns the rows exactly as given (L1.28a).
"""
from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable
from typing import Any

WINDOW = int(os.environ.get("BREADTH_FENCE_WINDOW", "20000"))
SYMBOL_SHARE = float(os.environ.get("BREADTH_FENCE_SYMBOL_SHARE", "0.05"))
CLASS_SHARE = float(os.environ.get("BREADTH_FENCE_CLASS_SHARE", "0.40"))
SLACK = 2


def _symbol(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("sym") or "?").strip().upper() or "?"


def _default_class_of() -> Callable[[str], str]:
    try:
        from research.universe_policy import asset_class_of
    except Exception:
        return lambda _s: "?"

    cache: dict[str, str] = {}

    def f(sym: str) -> str:
        if sym not in cache:
            try:
                cache[sym] = asset_class_of(sym) or "?"
            except Exception:
                cache[sym] = "?"
        return cache[sym]

    return f


def _shares(rows: list[dict[str, Any]], class_of: Callable[[str], str]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    sym = Counter(_symbol(r) for r in rows)
    cls = Counter(class_of(_symbol(r)) for r in rows)
    n = len(rows)

    def eff(c: Counter) -> float:
        return round(1.0 / sum((v / n) ** 2 for v in c.values()), 2)

    top_s, top_c = sym.most_common(1)[0], cls.most_common(1)[0]
    return {"n": n,
            "distinct_symbols": len(sym), "effective_symbols": eff(sym),
            "top_symbol": top_s[0], "top_symbol_share": round(top_s[1] / n, 4),
            "distinct_classes": len(cls), "effective_classes": eff(cls),
            "top_class": top_c[0], "top_class_share": round(top_c[1] / n, 4),
            "class_shares": {k: round(v / n, 4) for k, v in cls.most_common()}}


def fence(rows: list[Any], *, window: int = WINDOW, symbol_share: float = SYMBOL_SHARE,
          class_share: float = CLASS_SHARE,
          class_of: Callable[[str], str] | None = None
          ) -> tuple[list[Any], dict[str, Any]]:
    """Return (rows re-ordered within the window, report). Never drops a row."""
    try:
        return _fence(rows, window, symbol_share, class_share,
                      class_of or _default_class_of())
    except Exception as exc:
        return rows, {"status": f"FAILED: {type(exc).__name__}: {exc}", "moved": 0}


def _fence(rows: list[Any], window: int, symbol_share: float, class_share: float,
           class_of: Callable[[str], str]) -> tuple[list[Any], dict[str, Any]]:
    w = max(0, min(window, len(rows)))
    head, tail = rows[:w], rows[w:]
    dict_rows = [r for r in head if isinstance(r, dict)]
    # An unavailable classifier labels everything "?": the class cap is then moot, the
    # symbol cap still applies, and the report says so (Audit nit, 0016).
    class_ok = any(class_of(_symbol(r)) != "?" for r in dict_rows[:200])
    before = _shares(dict_rows, class_of)

    # Per-symbol queues keep the upstream order inside each symbol; the next pick is the
    # earliest head (by upstream position) that the caps allow.
    queues: dict[str, list[int]] = {}
    keys: list[tuple[str, str]] = []
    for i, r in enumerate(head):
        s = _symbol(r) if isinstance(r, dict) else "\0"
        c = class_of(s) if isinstance(r, dict) else "\0"
        keys.append((s, c))
        queues.setdefault(s, []).append(i)
    ptr = dict.fromkeys(queues, 0)
    used_s: Counter = Counter()
    used_c: Counter = Counter()
    out_idx: list[int] = []
    capped = 0
    class_capped = 0
    for n in range(1, w + 1):
        s_cap = max(symbol_share * n, 1.0) + SLACK
        c_cap = class_share * n + SLACK
        # TIERED PICK (Audit MF-1, 0016): both caps, else the symbol cap alone (so an
        # FX-dominant window still rotates its FX symbols when the class cap binds), else
        # the least-used symbol -- the fence orders, it never starves the judge.
        best = sym_only = fallback = -1
        fb_key: tuple[int, int] | None = None
        for s, q in queues.items():
            p = ptr[s]
            if p >= len(q):
                continue
            i = q[p]
            # Last tier: the LEAST-USED symbol (earliest on a tie), i.e. round-robin, so a
            # window with too few symbols for the caps still spreads evenly over what it has.
            k = (used_s[s], i)
            if fb_key is None or k < fb_key:
                fb_key, fallback = k, i
            sym_ok = s == "\0" or used_s[s] + 1 <= s_cap
            if not sym_ok:
                continue
            if sym_only < 0 or i < sym_only:
                sym_only = i
            c = keys[i][1]
            if s == "\0" or used_c[c] + 1 <= c_cap:
                if best < 0 or i < best:
                    best = i
        if best >= 0:
            pick = best
        elif sym_only >= 0:
            pick = sym_only
            class_capped += 1
        else:
            pick = fallback
            capped += 1
        s, c = keys[pick]
        ptr[s] += 1
        used_s[s] += 1
        used_c[c] += 1
        out_idx.append(pick)
    new_head = [head[i] for i in out_idx]
    moved = sum(1 for k, i in enumerate(out_idx) if k != i)
    after = _shares([r for r in new_head if isinstance(r, dict)], class_of)
    return new_head + tail, {
        "status": "APPLIED", "window": w, "rows": len(rows), "moved": moved,
        "steps_without_eligible_row": capped,
        "steps_class_cap_waived": class_capped,
        "class_of_available": class_ok,
        "symbol_share_cap": symbol_share, "class_share_cap": class_share,
        "before": before, "after": after,
        "rule": ("every prefix of the judge's window: no symbol over "
                 f"{symbol_share:.0%} and no asset class over {class_share:.0%} (+{SLACK} "
                 "rows slack); earliest eligible row first; nothing removed")}
