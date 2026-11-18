"""The spread-regime entry gate: DEFER a market entry while the spread is extreme for its own hour.

WHAT IT DOES. `research/spread_regime.py` publishes, every hour, each symbol's spread norm per
broker hour (median and a robust scale, from the tick tape where the box holds it and from the H1
bars' `spread` column where it does not). At the moment the family lane is about to send a market
entry, this reads the live quote's spread, normalises it against THAT hour's own norm,

    spread_z = (spread_pts - median[hour]) / scale[hour]

and, when `spread_z >= Z_DEFER`, the entry is one the gate would DEFER until the spread is back
under `Z_RELEASE`.

IT DEFERS. IT NEVER CANCELS AND NEVER SHRINKS. A deferral leaves the signal bar unmarked -- the
same retention `quote_spread` already uses in `resolve_family_order` -- so a later pass sends the
SAME order at the SAME lot. Three releases bound it so a deferral can never become a lost trade:

    the spread is back under Z_RELEASE                       send
    MAX_DEFER_MIN, or a third of the chart's bar, has passed send (a bar roll would lose it)
    the quote has moved against the entry by DRIFT_RELEASE_FRAC of the stop distance
        -- well inside the entry-drift tolerance (0.25), so the gate never pushes a signal
        into the stale-signal refusal                         send

SHADOW FIRST, BECAUSE OF RULE 1. A veto must prove it raises robust forward E[log W]. So the
switch `data/SPREAD_GATE_MODE.json` defaults to SHADOW: the gate returns None (send now) on every
call and only records, in `data/spread_gate_ledger.jsonl`, each entry it WOULD have deferred with
the quote and the norm it used. `research/spread_regime.py` scores each one hourly against the
tick tape -- the side quote at the release time against the side quote actually taken, both net
of spread because both are the side the order pays -- and writes the mode LIVE when the mean minus
one standard error of the improvement (in R) is above zero over at least N_MIN scored deferrals,
and back to SHADOW when it is not. No human step either way. `"pinned": true` in the switch file
freezes it (a human's revert path); `"mode": "OFF"` stops even the shadow record.

NEVER RAISES INTO THE GATEWAY and imports nothing outside the standard library: it sits in the
money path's import closure. Every failure answers None, which is "send exactly as before".
"""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODES = ("SHADOW", "LIVE", "OFF")
DEFAULT_MODE = "SHADOW"

#: Defer at or above this spread_z; release under Z_RELEASE (hysteresis, so one tick does not
#: flip it). Three robust standard deviations above the hour's own median.
Z_DEFER = 3.0
Z_RELEASE = 2.0
#: The longest a deferral may hold, and never more than a third of the chart's own bar.
MAX_DEFER_MIN = 20.0
#: A horizon shorter than one gateway pass (the loop runs each minute) cannot defer at all.
MIN_DEFER_S = 60.0
#: Release when the side quote has moved AGAINST the entry by this share of the stop distance.
DRIFT_RELEASE_FRAC = 0.10
#: Norms older than this are not today's: the gate is UNMEASURED and does nothing.
NORMS_MAX_AGE_H = 6.0
#: Promotion needs at least this many scored deferrals (research/spread_regime.py reads it).
N_MIN = 30

_NORMS_CACHE: dict[str, Any] = {"path": None, "mtime": None, "doc": None}


def paths(base: Path) -> dict[str, Path]:
    base = Path(base)
    return {"mode": base / "data" / "SPREAD_GATE_MODE.json",
            "ledger": base / "data" / "spread_gate_ledger.jsonl",
            "state": base / "data" / "spread_gate_state.json",
            "norms": base / "reports" / "SPREAD_REGIME.json"}


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def read_mode(base: Path) -> str:
    """The switch. Absent, unreadable or unknown is SHADOW -- never LIVE by accident."""
    doc = _read_json(paths(base)["mode"])
    mode = str((doc or {}).get("mode") or "").upper() if isinstance(doc, dict) else ""
    return mode if mode in MODES else DEFAULT_MODE


def _norms(base: Path) -> dict[str, Any] | None:
    p = paths(base)["norms"]
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    if _NORMS_CACHE["path"] != str(p) or _NORMS_CACHE["mtime"] != mtime:
        _NORMS_CACHE.update(path=str(p), mtime=mtime, doc=_read_json(p))
    doc = _NORMS_CACHE["doc"]
    return doc if isinstance(doc, dict) else None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _broker_hour(tick: Any, last_bar: Any, bar_minutes: int) -> tuple[int | None, int | None]:
    """(broker hour, broker epoch ms) of the quote. The tick's own clock first -- the bars and the
    tape are on the same venue clock -- and the forming bar's hour when the tick carries none."""
    ms = _num(getattr(tick, "time_msc", None))
    if ms is None:
        sec = _num(getattr(tick, "time", None))
        ms = sec * 1000.0 if sec is not None else None
    if ms is not None and ms > 0:
        return int(ms // 3_600_000) % 24, int(ms)
    try:
        from datetime import timedelta
        t = datetime.fromisoformat(str(last_bar).replace("Z", "+00:00"))
        return (t + timedelta(minutes=int(bar_minutes))).hour, None
    except (TypeError, ValueError):
        return None, None


def spread_z(norm_sym: dict[str, Any], hour: int, spread_pts: float) -> tuple[float | None, dict]:
    """spread_z against the symbol's norm for `hour`, or None when that hour is not measured."""
    cell = (norm_sym.get("hours") or {}).get(str(hour)) if isinstance(norm_sym, dict) else None
    if not isinstance(cell, dict) or cell.get("status") != "MEASURED":
        return None, {}
    med, sc = _num(cell.get("median")), _num(cell.get("scale"))
    if med is None or sc is None or sc <= 0:
        return None, {}
    return (spread_pts - med) / sc, {"median": med, "scale": sc}


def _append(p: Path, row: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def _write_state(p: Path, st: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(st, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, p)
    except OSError:                       # a read-only destination on Windows: write in place
        p.write_text(tmp.read_text("utf-8"), "utf-8")
        tmp.unlink(missing_ok=True)


def max_defer_s(bar_minutes: int) -> float:
    return min(MAX_DEFER_MIN * 60.0, float(bar_minutes) * 60.0 / 3.0)


def evaluate(s: dict[str, Any], plan: dict[str, Any], *, base: Path, bar_minutes: int = 60,
             now: datetime | None = None) -> dict[str, Any] | None:
    """The gate's reading of one entry, or None when it cannot read one (UNMEASURED). Pure: no
    file is written here."""
    lot = _num(plan.get("lot"))
    dist = _num(plan.get("dist"))
    quote = _num(plan.get("entry_ref"))
    tick = plan.get("tick")
    bid, ask = _num(getattr(tick, "bid", None)), _num(getattr(tick, "ask", None))
    if not (lot and lot > 0 and dist and dist > 0 and quote and bid and ask and ask >= bid):
        return None
    norms = _norms(base)
    if not norms:
        return None
    try:
        at = datetime.fromisoformat(str(norms.get("generated_at")))
        age_h = ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return None
    if not -0.25 <= age_h <= NORMS_MAX_AGE_H:
        return None
    symbol = str(s.get("symbol") or "")
    nsym = (norms.get("symbols") or {}).get(symbol)
    if not isinstance(nsym, dict):
        return None
    point = _num(getattr(plan.get("sym"), "point", None)) or _num(nsym.get("point"))
    if not point or point <= 0:
        return None
    hour, broker_ms = _broker_hour(tick, plan.get("last_bar"), bar_minutes)
    if hour is None:
        return None
    pts = (ask - bid) / point
    z, norm = spread_z(nsym, hour, pts)
    if z is None:
        return None
    side = int(plan.get("side") or 0)
    risk = _num(s.get("q_charge"))
    return {"sleeve": str(s.get("name")), "symbol": symbol, "side": side,
            "key": f"{s.get('name')}|{plan.get('last_bar')}", "quote": quote, "bid": bid,
            "ask": ask, "spread_pts": round(pts, 3), "z": round(z, 4), "broker_hour": hour,
            "broker_ms": broker_ms, "dist": dist, "lot": lot, "risk_frac": risk,
            "basis": nsym.get("basis"), "bar_minutes": int(bar_minutes),
            "max_defer_s": max_defer_s(bar_minutes), **norm}


def entry_gate(s: dict[str, Any], plan: dict[str, Any], *, base: Path, bar_minutes: int = 60,
               now: datetime | None = None) -> str | None:
    """The gateway's one call. Returns a reason when THIS PASS must not send (LIVE deferral
    only), otherwise None -- and in SHADOW it is always None. Never raises."""
    try:
        return _entry_gate(s, plan, base=Path(base), bar_minutes=int(bar_minutes), now=now)
    except Exception:
        return None


def _entry_gate(s: dict[str, Any], plan: dict[str, Any], *, base: Path, bar_minutes: int,
                now: datetime | None) -> str | None:
    mode = read_mode(base)
    if mode == "OFF" or not plan.get("ok"):
        return None
    now = now or datetime.now(tz=UTC)
    p = paths(base)
    st = _read_json(p["state"])
    st = st if isinstance(st, dict) else {}
    pending: dict[str, Any] = st.setdefault("pending", {})
    seen: list[str] = st.setdefault("seen", [])
    ev = evaluate(s, plan, base=base, bar_minutes=bar_minutes, now=now)
    key = f"{s.get('name')}|{plan.get('last_bar')}"
    stamp = now.isoformat()
    if mode != "LIVE":
        # SHADOW: record the entry once, send now. The order is not touched. A deferral left
        # pending by a LIVE spell that has since been demoted is let go.
        dropped = pending.pop(key, None) is not None
        if ev is None or ev["z"] < Z_DEFER or key in seen:
            if dropped:
                _write_state(p["state"], st)
            return None
        _append(p["ledger"], {"kind": "would_defer", "mode": mode, "at": stamp, **(ev or {})})
        seen.append(key)
        st["seen"] = seen[-500:]
        _write_state(p["state"], st)
        return None
    # LIVE.
    held = pending.get(key)
    if held is None:
        if ev is None or ev["z"] < Z_DEFER or ev["max_defer_s"] < MIN_DEFER_S:
            return None
        pending[key] = {"first_at": stamp, "quote0": ev["quote"], "z0": ev["z"],
                        "side": ev["side"], "dist": ev["dist"], "symbol": ev["symbol"],
                        "max_defer_s": ev["max_defer_s"], "risk_frac": ev["risk_frac"]}
        _append(p["ledger"], {"kind": "defer", "mode": mode, "at": stamp, **ev})
        _write_state(p["state"], st)
        return (f"spread_z {ev['z']:+.2f} >= {Z_DEFER:g} at broker hour {ev['broker_hour']} "
                f"({ev['spread_pts']:.1f} pts vs median {ev['median']:.1f}); deferred up to "
                f"{ev['max_defer_s'] / 60.0:.0f} min, same order, same lot")
    try:
        elapsed = (now - datetime.fromisoformat(str(held["first_at"]))).total_seconds()
    except (KeyError, TypeError, ValueError):
        elapsed = math.inf
    quote = _num(plan.get("entry_ref"))
    side, dist, q0 = int(held.get("side") or 0), _num(held.get("dist")), _num(held.get("quote0"))
    adverse = (side * (quote - q0) / dist) if (quote and q0 and dist) else None
    reason = ("unmeasured" if ev is None else "spread_normal" if ev["z"] < Z_RELEASE
              else "horizon" if elapsed >= float(held.get("max_defer_s") or 0.0)
              else "drift" if adverse is not None and adverse >= DRIFT_RELEASE_FRAC else None)
    if reason is None and ev is not None:
        return (f"spread_z {ev['z']:+.2f} still >= {Z_RELEASE:g}; deferred "
                f"{elapsed:.0f}s of {float(held.get('max_defer_s') or 0):.0f}s")
    pending.pop(key, None)
    _append(p["ledger"], {"kind": "release", "mode": mode, "at": stamp, "key": key,
                          "sleeve": str(s.get("name")), "symbol": held.get("symbol"),
                          "side": side, "reason": reason, "elapsed_s": round(elapsed, 1),
                          "quote0": q0, "quote": quote, "dist": dist,
                          "risk_frac": held.get("risk_frac"),
                          "z": None if ev is None else ev["z"],
                          "improvement_r": (None if adverse is None else round(-adverse, 6))})
    _write_state(p["state"], st)
    return None
