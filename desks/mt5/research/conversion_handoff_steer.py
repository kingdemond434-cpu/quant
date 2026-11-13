"""conversion_handoff_steer: the breadth steer -- which parked cells are converted first.

WHY (hourly pass, 2026-11-13 19:21Z). The 170 promoted sleeves were about eight independent bets,
every one FX (NOK 67, CHF 55) plus two BTC: no gold, no index, and nothing entering 02:00-09:00,
12:00-13:00 or 21:00-23:00 UTC. The converter served its backlog round-robin by trial family, so
the classes the book lacks waited behind the class it already holds. `desks/mt5/data/
breadth_steer.json` names the groups to serve first; this module says which group a handoff row
belongs to. A steer REORDERS the work list and never drops a row: an unsteered row keeps its
place behind the steered ones, and an unreadable or absent steer file changes nothing.

The asia_window group matches a token in the row's family or cell name: a handoff row carries no
entry clock, so a session family is the only Asia-window evidence the row itself holds."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from research.conversion_handoff_common import DESK

STEER = DESK / "data" / "breadth_steer.json"
UNSTEERED = ""


def load_steer(path: Path = STEER) -> list[dict[str, Any]]:
    """The steer's groups in priority order; [] when the file is absent or unreadable."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    groups = doc.get("groups") if isinstance(doc, dict) else None
    return [g for g in groups or [] if isinstance(g, dict) and g.get("name")]


def _class_of(symbol: str) -> str:
    try:
        import research.universe_policy as up
    except ImportError:                                           # pragma: no cover - import ctx
        import universe_policy as up  # type: ignore[no-redef]
    try:
        return str(up.asset_class_of(symbol) or "")
    except Exception:                                             # pragma: no cover - defensive
        return ""


def asset_class(symbol: str) -> str:
    """The registry's class for the symbol, or UNCLASSIFIED."""
    return _class_of(symbol) or "UNCLASSIFIED"


def _pair(symbol: str) -> tuple[str, str] | None:
    s = "".join(ch for ch in symbol.upper() if ch.isalpha())
    return (s[:3], s[3:6]) if len(s) == 6 else None


def steer_group(row: Mapping[str, Any], groups: list[dict[str, Any]],
                class_of: Any = None) -> str:
    """The first steer group this row belongs to, or UNSTEERED."""
    symbol = str(row.get("symbol") or "").upper()
    text = f"{row.get('family') or ''} {row.get('trial_family') or ''} {row.get('cell') or ''}"
    text = text.lower()
    cls: str | None = None
    for g in groups:
        if symbol and any(symbol.startswith(str(p).upper()) for p in g.get("symbol_prefixes")
                          or ()):
            return str(g["name"])
        if g.get("asset_classes") and symbol:
            if cls is None:
                cls = (class_of or _class_of)(symbol) or ""
            if cls in {str(c).lower() for c in g["asset_classes"]}:
                return str(g["name"])
        if g.get("currency_set") and symbol:
            pair = _pair(symbol)
            want = {str(c).upper() for c in g["currency_set"]}
            if pair and pair[0] != pair[1] and set(pair) <= want:
                return str(g["name"])
        if any(str(t).lower() in text for t in g.get("text_tokens") or ()):
            return str(g["name"])
    return UNSTEERED
