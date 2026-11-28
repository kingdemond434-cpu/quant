"""Book-gap steer: the compiler converts first what the LIVE book holds least of (2026-11-13).

The hourly pass measured the promoted book on 2026-11-13 at 170 strategies but only ~8
independent bets: 67 NOK-heavy, 55 CHF-heavy, all FX bar two BTC, no gold, no index, and nothing
entering 02:00-09:00 UTC. Another NOK cross adds a sleeve and almost no k_eff (k_eff is concave in
n at any correlation above zero, libs/research/alpha_clusters). So the research order should spend
the next judge slot where the book is empty.

This module reads the box's own LIVE rows (data/sleeves.json, status LIVE), measures the book's
share in three buckets per candidate -- asset class, currency legs, entry session -- and gives each
candidate a gap in [0, 1]: 1 where the book holds nothing of that bucket, 0 for the bucket the
book is most concentrated in. The compiler then orders by net-edge rank divided by
(1 + STRENGTH * gap): a full-gap candidate competes as if it ranked three times higher, a
candidate in the book's heaviest bucket keeps its rank. Nothing is dropped and nothing unpriced
jumps a priced one: the steer only reorders, so the judge's budget reaches the gaps first.

It re-derives itself every pass from the live book, so as gold or index sleeves go LIVE their gap
closes on its own. An unreadable or empty book is UNMEASURED and leaves the order exactly as the
net-edge ranking gave it. Revert path: QUANT_BOOK_GAP_STEER=0.

THE EXOTIC QUOTA (zuck, 2026-11-13 19:46Z) runs after the gap order, always: at most 10% of
every leading slice of the docket is an exotic (the broker's "forex exotics" class), so at least
90% of the judge's compute goes to non-exotic markets whatever its budget. Excess exotics wait
behind every non-exotic, marked `exotic_quota_deferred`; the report carries the realised split.
"""

from __future__ import annotations

import json
import os
from collections import Counter, deque
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
SLEEVES = BASE / "data" / "sleeves.json"

#: How far a full gap moves a candidate: rank / (1 + STRENGTH * gap). 2 => up to 3x earlier.
STRENGTH = 2.0
#: Session names whose entries fall in the book's empty 02:00-09:00 UTC window.
ASIA_SESSIONS = frozenset({"asia", "tokyo", "tokyo_fix", "sydney", "asia_open"})
#: The crosses the steer asks for: a USD, JPY or EUR leg and no NOK or CHF leg.
CROSS_LEGS = frozenset({"USD", "JPY", "EUR"})
CROWDED_LEGS = frozenset({"NOK", "CHF"})
METAL_PREFIXES = ("XAU", "XAG", "XPT", "XPD")
#: zuck's standing rule (2026-11-13 19:46Z): at least 90% of mining compute goes to non-exotic
#: markets, at most 10% to exotics. "Exotic" is the broker's own class label ("forex exotics").
EXOTIC_SHARE = 0.10


def _legs(symbol: str) -> tuple[str, ...]:
    s = str(symbol or "").strip().upper()
    for p in METAL_PREFIXES:
        if s.startswith(p):
            return (p, s[len(p):len(p) + 3]) if len(s) >= len(p) + 3 else (p,)
    if len(s) >= 6 and s[:6].isalpha():
        return s[:3], s[3:6]
    return ()


def _session(row: Mapping[str, Any]) -> str:
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    raw = row.get("session") or (params or {}).get("session") or "all"
    return str(raw).strip().lower() or "all"


def _class(symbol: str, class_of: Callable[[str], str]) -> str:
    s = str(symbol or "").strip().upper()
    if s.startswith("XAU"):
        return "gold"
    if s.startswith(METAL_PREFIXES):
        return "metals"
    try:
        c = str(class_of(s) or "").lower()
    except Exception:
        c = ""
    if "ind" in c:
        return "index"
    if "forex" in c or c == "fx":
        return "fx"
    if c in ("commodities", "commodity", "energy"):
        return "commodity"
    return c or "unclassified"


def _default_class_of() -> Callable[[str], str]:
    try:
        from research import universe_policy as up
    except ImportError:  # run as a script from research/
        import universe_policy as up  # type: ignore[no-redef]
    return up.asset_class_of


def live_book(path: Path = SLEEVES) -> list[dict[str, Any]] | None:
    """The LIVE rows of the box's sleeve registry, or None when it cannot be read."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("sleeves") if isinstance(doc, Mapping) else doc
    if isinstance(rows, Mapping):
        rows = list(rows.values())
    if not isinstance(rows, list):
        return None
    return [r for r in rows if isinstance(r, Mapping)
            and str(r.get("status") or "").upper() == "LIVE"]


def buckets(row: Mapping[str, Any], class_of: Callable[[str], str]) -> dict[str, list[str]]:
    sym = str(row.get("symbol") or "")
    return {"class": [_class(sym, class_of)], "leg": list(_legs(sym)), "session": [_session(row)]}


def tags(row: Mapping[str, Any], class_of: Callable[[str], str]) -> list[str]:
    """The steer's reporting buckets this candidate falls in (the hourly pass's four asks)."""
    sym = str(row.get("symbol") or "")
    cls, legs, out = _class(sym, class_of), set(_legs(sym)), []
    if cls == "gold":
        out.append("gold")
    if cls == "index":
        out.append("index")
    if cls == "fx" and legs & CROSS_LEGS and not legs & CROWDED_LEGS:
        out.append("usd_jpy_eur_cross")
    if _session(row) in ASIA_SESSIONS:
        out.append("asia_entry")
    return out


class Steer:
    def __init__(self, book: list[Mapping[str, Any]] | None,
                 class_of: Callable[[str], str] | None = None) -> None:
        self.class_of = class_of or _default_class_of()
        self.book = book
        self.shares: dict[str, dict[str, float]] = {}
        if book:
            for dim in ("class", "leg", "session"):
                c: Counter[str] = Counter()
                for r in book:
                    c.update(buckets(r, self.class_of)[dim])
                total = sum(c.values()) or 1
                self.shares[dim] = {k: v / total for k, v in c.items()}

    @property
    def measured(self) -> bool:
        return bool(self.book)

    def gap(self, row: Mapping[str, Any]) -> float:
        """Mean over the three dimensions of 1 - share/max_share (0 = the book's heaviest)."""
        if not self.measured:
            return 0.0
        b = buckets(row, self.class_of)
        parts: list[float] = []
        for dim, keys in b.items():
            shares = self.shares.get(dim) or {}
            top = max(shares.values(), default=0.0)
            if not keys or top <= 0:
                continue
            parts.append(sum(1.0 - shares.get(k, 0.0) / top for k in keys) / len(keys))
        return sum(parts) / len(parts) if parts else 0.0

    def order(self, ordered: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reorder priced candidates by rank / (1 + STRENGTH * gap); unpriced stay behind them."""
        if not self.measured:
            return ordered
        priced = [c for c in ordered if c.get("net_edge") is not None]
        unpriced = [c for c in ordered if c.get("net_edge") is None]

        def keyed(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
            scored = []
            for rank, c in enumerate(group, start=1):
                g = self.gap(c)
                c["book_gap"] = round(g, 4)
                scored.append((rank / (1.0 + STRENGTH * g), rank, c))
            return [c for _, _, c in sorted(scored, key=lambda t: (t[0], t[1]))]

        return keyed(priced) + keyed(unpriced)


def is_exotic(row: Mapping[str, Any], class_of: Callable[[str], str]) -> bool:
    """FAILS CLOSED: a symbol whose class cannot be read counts against the exotic share, so a
    broken registry can only shrink the exotic slice, never smuggle exotics into the 90%."""
    try:
        return "exotic" in str(class_of(str(row.get("symbol") or "").upper()) or "").lower()
    except Exception:
        return True


def exotic_quota(ordered: list[dict[str, Any]], class_of: Callable[[str], str],
                 share: float = EXOTIC_SHARE) -> tuple[list[dict[str, Any]], int]:
    """A HARD prefix quota: in every leading slice the judge can take, exotics hold at most
    `share` of the slots. An exotic is placed only while (exotics so far + 1) <= share * (slot);
    the rest wait, in their own order, behind every non-exotic and are marked
    `exotic_quota_deferred` -- kept and reported, never dropped, reached only once the
    non-exotic docket is spent. Returns the order and how many were deferred."""
    out: list[dict[str, Any]] = []
    waiting: deque[dict[str, Any]] = deque()
    n_exo = 0
    for c in ordered:
        if not is_exotic(c, class_of):
            out.append(c)
        else:
            waiting.append(c)
        while waiting and (n_exo + 1) <= share * (len(out) + 1):
            out.append(waiting.popleft())
            n_exo += 1
    for c in waiting:
        c["exotic_quota_deferred"] = True
    return out + list(waiting), len(waiting)


def split(rows: list[Mapping[str, Any]], class_of: Callable[[str], str]) -> dict[str, Any]:
    n = len(rows)
    exo = sum(1 for c in rows if is_exotic(c, class_of))
    return {"n": n, "exotic": exo, "non_exotic": n - exo,
            "exotic_share": round(exo / n, 4) if n else None}


def report(before: Iterable[Mapping[str, Any]], after: list[Mapping[str, Any]], steer: Steer,
           top_n: int = 1000) -> dict[str, Any]:
    """Counts per ask: candidates this pass, and how many sit in the first `top_n` before/after."""
    before = list(before)
    count = Counter(t for c in after for t in tags(c, steer.class_of))
    top_b = Counter(t for c in before[:top_n] for t in tags(c, steer.class_of))
    top_a = Counter(t for c in after[:top_n] for t in tags(c, steer.class_of))
    keys = ("gold", "index", "usd_jpy_eur_cross", "asia_entry")
    return {
        "status": "APPLIED" if steer.measured else "UNMEASURED: no LIVE rows in data/sleeves.json"
                                                   " (order left as net-edge ranked)",
        "live_sleeves": len(steer.book or []),
        "strength": STRENGTH,
        "book_shares": {d: dict(sorted(s.items(), key=lambda kv: -kv[1])[:8])
                        for d, s in steer.shares.items()},
        "candidates_by_ask": {k: int(count.get(k, 0)) for k in keys},
        f"in_first_{top_n}_before": {k: int(top_b.get(k, 0)) for k in keys},
        f"in_first_{top_n}_after": {k: int(top_a.get(k, 0)) for k in keys},
        "revert": "QUANT_BOOK_GAP_STEER=0",
    }


def apply(ordered: list[dict[str, Any]], *, sleeves: Path = SLEEVES,
          class_of: Callable[[str], str] | None = None, top_n: int = 1000
          ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The book-gap order, then the 90/10 exotic quota. The quota is a standing rule, so it
    applies whether the gap steer is measured, unmeasured or switched off."""
    steer = Steer(live_book(sleeves), class_of)
    off = os.environ.get("QUANT_BOOK_GAP_STEER", "1") == "0"
    out = list(ordered) if off else steer.order(list(ordered))
    out, deferred = exotic_quota(out, steer.class_of)
    rep = report(ordered, out, steer, top_n)
    if off:
        rep["status"] = "OFF: QUANT_BOOK_GAP_STEER=0 (revert path)"
    rep["exotic_quota"] = {
        "rule": f"at most {EXOTIC_SHARE:.0%} of every leading slice is exotic "
                "(broker class 'forex exotics'); the excess waits behind all non-exotics",
        "max_share": EXOTIC_SHARE, "deferred": deferred,
        f"first_{top_n}": split(out[:top_n], steer.class_of),
        "all": split(out, steer.class_of),
        "before_quota_first_{0}".format(top_n): split(list(ordered)[:top_n], steer.class_of),
    }
    return out, rep
