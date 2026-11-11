"""ROBOTS, FAIL CLOSED, UNTIL THE ONE GATE LANDS (audit hold on #251, 2026-11-11).

The desk's single robots.txt reader is `libs.data.robots_gate` (PR #831, governance robots ruling
2026-11-10). It is NOT on the live branch yet. The fetch paths the Asia planes added (the MOF and
HKMA rows of `alt_proxies`, whose robots.txt is recorded as not readable or not cited, and the
keyed / token paths of `asia_collector.collect_one`, `research/keyed_sources.py` and
`libs/ops/token_refresh.py`) therefore ask this shim first:

    robots_allows(url) -> bool

* `libs.data.robots_gate` importable: delegate to its `RobotsGate.check(url)`; only `ALLOWED`
  fetches (DISALLOWED and UNREAD both stop, as the ruling says).
* not importable (today): False. FAIL CLOSED -- no robots.txt is read, no request is sent.

A refusal is a named state, `REFUSED_ROBOTS_UNREAD`, never a silent skip, and it costs something:
`refuse()` writes one missed-growth line per organ, host and day to MISSED_GROWTH (this shim's own
append-only ledger -- `data/missed_growth.jsonl` is keyed by the registered capital rails and is
never appended to by a data organ). The growth given up is UNMEASURED: the series was never held.

This module makes no network call of its own when the gate is absent; with the gate present the
only call it makes is the gate's own robots.txt read.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
#: The refusal ledger (one missed-growth line per organ, host and day).
MISSED_GROWTH = ROOT / "desks" / "mt5" / "data" / "robots_refused_missed_growth.jsonl"

REFUSED_ROBOTS_UNREAD = "REFUSED_ROBOTS_UNREAD"
AGENT = "quant-research"
TIMEOUT_S = 15.0

_LOCK = threading.Lock()
_GATE: Any = None


def _gate_module() -> ModuleType | None:
    """`libs.data.robots_gate` (#831) when it is on this tree, else None."""
    try:
        from libs.data import robots_gate  # type: ignore[attr-defined,unused-ignore]
    except ImportError:
        return None
    return robots_gate  # type: ignore[no-any-return,unused-ignore]


def _get_robots(url: str) -> tuple[int | None, str]:
    """The gate's getter: (HTTP status | None, body) for one robots.txt."""
    req = urllib.request.Request(url, headers={"User-Agent": f"{AGENT} (robots.txt reader)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return int(getattr(r, "status", 200) or 200), r.read(500_000).decode(
                "utf-8", "replace")
    except urllib.error.HTTPError as e:
        return int(e.code or 0), ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ""


def robots_allows(url: str, get: Callable[[str], tuple[int | None, str]] | None = None) -> bool:
    """True only when the desk's robots gate says ALLOWED for `url`. Absent gate: False."""
    mod = _gate_module()
    if mod is None:
        return False
    global _GATE
    try:
        if get is not None:
            gate = mod.RobotsGate(get, agent=AGENT)
        else:
            with _LOCK:
                if _GATE is None:
                    _GATE = mod.RobotsGate(_get_robots, agent=AGENT)
                gate = _GATE
        return bool(gate.check(url) == getattr(mod, "ALLOWED", "ALLOWED"))
    except Exception:                           # an unreadable gate is an unread robots.txt
        return False


def why_refused(url: str) -> str:
    host = urllib.parse.urlsplit(url).netloc or url
    if _gate_module() is None:
        return (f"{REFUSED_ROBOTS_UNREAD}: robots.txt for {host} is not read -- the desk's robots "
                f"gate (libs.data.robots_gate, #831) is not on this tree, so the fetch fails "
                f"closed and no request is sent")
    return (f"{REFUSED_ROBOTS_UNREAD}: the robots gate did not answer ALLOWED for {host} "
            f"(disallowed, refused or unreachable robots.txt)")


def refuse(organ: str, url: str, source: str = "", now: datetime | None = None
           ) -> dict[str, Any]:
    """Record one refusal: a missed-growth line (once per organ, host and day) and the state a
    caller writes on its record. Never raises; never makes a network call."""
    t = now or datetime.now(tz=UTC)
    host = urllib.parse.urlsplit(url).netloc or url
    why = why_refused(url)
    line = {"day": t.date().isoformat(), "rail": "robots_unread", "organ": organ,
            "source": source, "host": host, "value": None, "measured": False,
            "at": t.isoformat(timespec="seconds"),
            "why": (f"{why}. The growth given up is UNMEASURED: the series was never held, so "
                    f"nothing prices what it would have added (Rule 1: a refusal is a risk "
                    f"reduction and owes its ledger line)")}
    try:
        with _LOCK:
            seen = set()
            if MISSED_GROWTH.exists():
                for ln in MISSED_GROWTH.read_text("utf-8").splitlines()[-2000:]:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    seen.add((r.get("day"), r.get("organ"), r.get("host"), r.get("source")))
            if (line["day"], organ, host, source) not in seen:
                MISSED_GROWTH.parent.mkdir(parents=True, exist_ok=True)
                with MISSED_GROWTH.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(line) + "\n")
    except OSError:
        pass
    return {"status": REFUSED_ROBOTS_UNREAD, "why": why, "requests": 0,
            "missed_growth": {"ledger": str(MISSED_GROWTH.relative_to(ROOT))
                              if MISSED_GROWTH.is_relative_to(ROOT) else str(MISSED_GROWTH),
                              "rail": "robots_unread", "value": None}}
