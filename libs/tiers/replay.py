"""GLOBAL STATE REPLAY (Tier S layer 41): rebuild the desk's state at any past second from its
durable logs and immutable artifacts alone.

`desks/mt5/research/state_replay_audit.py` proves one thing: gateway decisions agree across a
restart boundary. It cannot answer "what did the desk know, hold and intend at 2026-09-14
07:00:00?" -- which certificates were valid, which sleeves were live, what the allocator had
published, which orders were in flight, which release was running, what the research budget was.

A STREAM is a time-stamped durable log plus a key and a reducer. `replay(streams, t)` folds every
record with time <= t into per-component state; nothing written after t can leak in, because the
fold never reads past t. `consistency()` replays at "now" and compares with the live artifacts:
agreement is the evidence that the logs are complete enough to rebuild the desk; disagreement
names the component whose history is not durable.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Reducer = Callable[[Any, Mapping[str, Any]], Any]


def parse_t(x: Any) -> datetime | None:
    if not x:
        return None
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


@dataclass
class Stream:
    component: str
    rows: list[Mapping[str, Any]]
    time_key: str | tuple[str, ...]
    key: Callable[[Mapping[str, Any]], str] = lambda r: "_"
    reducer: Reducer = lambda _old, new: dict(new)
    meta: dict[str, Any] = field(default_factory=dict)

    def time_of(self, r: Mapping[str, Any]) -> datetime | None:
        keys = (self.time_key,) if isinstance(self.time_key, str) else self.time_key
        for k in keys:
            t = parse_t(r.get(k))
            if t is not None:
                return t
        return None


def read_jsonl(path: Path, limit: int = 500_000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def replay(streams: Iterable[Stream], t: datetime) -> dict[str, Any]:
    state: dict[str, dict[str, Any]] = {}
    stats: dict[str, dict[str, int]] = {}
    for s in streams:
        comp: dict[str, Any] = {}
        used = undated = future = 0
        for r in s.rows:
            rt = s.time_of(r)
            if rt is None:
                undated += 1
                continue
            if rt > t:
                future += 1
                continue
            k = s.key(r)
            comp[k] = s.reducer(comp.get(k), r)
            used += 1
        state[s.component] = comp
        stats[s.component] = {"records_used": used, "undated": undated, "after_t": future,
                              "keys": len(comp)}
    return {"at": t.isoformat(), "state": state, "stats": stats}


def consistency(streams: list[Stream], live: Mapping[str, set[str]],
                now: datetime | None = None) -> dict[str, Any]:
    """Replay at now; compare each component's key set with the live artifact's key set."""
    now = now or datetime.now(UTC)
    rep = replay(streams, now)
    out: dict[str, Any] = {}
    agree = 0
    for comp, keys in live.items():
        got = set(rep["state"].get(comp, {}))
        missing = sorted(keys - got)
        extra = sorted(got - keys)
        ok = not missing
        agree += int(ok)
        out[comp] = {"live": len(keys), "replayed": len(got), "missing": missing[:10],
                     "n_missing": len(missing), "extra": len(extra), "reconstructible": ok}
    return {"components": out, "reconstructible_share": (agree / len(live)) if live else None,
            "stats": rep["stats"]}


def count_reducer(old: Any, _new: Mapping[str, Any]) -> Any:
    return int(old or 0) + 1


def position_reducer(old: Any, new: Mapping[str, Any]) -> Any:
    d = dict(old or {"fills": 0, "volume": 0.0, "pl": 0.0})
    d["fills"] += 1
    d["volume"] += float(new.get("volume") or 0.0)
    d["pl"] += float(new.get("pl_quote") or 0.0)
    d["last"] = new.get("time")
    return d
