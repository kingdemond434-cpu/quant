"""ALT-DATA INTELLIGENCE AS SCOREABLE BELIEFS -- the first proven reader of ALT_PROXIES_ALLOCATION_INTEL.

THE GAP (principal, 2026-10-06): `alt_proxies` writes `reports/ALT_PROXIES_ALLOCATION_INTEL.json`
every pass -- per instrument, per day, the point-in-time tilt of every mapped alternative series --
and says in its own header that nothing reads it. A published file is not a consumed one, and a
tilt nobody grades cannot earn or lose anything.

WHAT THIS DOES, AND WHAT IT DOES NOT. It turns each instrument's current tilt into a
`forecast_contract.Belief` -- the desk's validated forecast interface, the one door through which a
research model may say something about the future -- and later resolves each belief against the
instrument's own H1 bars. The belief carries no lot, no direction to act on and no authority; raw
alternative data still never reaches capital. What changes is that the alt-data layer now has a
MEASURED skill: Brier score against the 0.25 climatology of a coin, per instrument and overall,
which is exactly the "baseline versus baseline-plus-data" comparison the acquisition order asks for
-- the baseline is "no information" (p = 0.5), the challenger is the tilt.

THE MAPPING IS DECLARED, NOT FITTED. p(up over 5 days) = 0.5 + 0.1 * clip(tilt, -3, 3) / 3, so the
strongest tilt claims 60/40 and nothing more. That is a deliberately weak prior; Brier grades it,
and a tilt that is uninformative scores at the climatology and is published as such.

POINT IN TIME. A belief is stamped `at` = the pass instant, formed only on components whose
`available_time` is at or before it (their vintage ids are its `features`, so the contract's
leakage check can read them). It resolves from the first bar at or after `at` plus the broker-clock
pad to the first bar at or after `at + horizon` plus the same pad -- later entry, never earlier.

ONE BELIEF PER INSTRUMENT PER TILT DATE. The pass is hourly and the tilt is daily; re-publishing
the same day's tilt every hour would multiply one observation into twenty-four and inflate the
sample the skill is measured on.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

MODEL_ID = "alt_proxies_tilt"
HORIZON_S = 5 * 86400
#: Bars are stamped in broker time under a UTC tzinfo (+2 winter / +3 summer). Looking 3h later
#: can only enter late, never early.
CLOCK_PAD = timedelta(hours=3)
MAX_P_SHIFT = 0.10
CLIMATOLOGY_BRIER = 0.25


def _subject(sym: str) -> str:
    return f"{sym}|P(close[t+{HORIZON_S // 86400}d] > close[t])"


def p_up(tilt: float) -> float:
    return 0.5 + MAX_P_SHIFT * max(-3.0, min(3.0, float(tilt))) / 3.0


def beliefs_from_intel(intel: dict[str, Any], now: datetime,
                       published: dict[str, str]) -> list[Any]:
    """New beliefs for every instrument whose tilt date has not been published yet. Mutates
    `published` (instrument -> tilt date) for the caller to persist."""
    from research.forecast_contract import Belief
    out: list[Any] = []
    at = now.isoformat(timespec="seconds")
    for sym, row in sorted((intel.get("instruments") or {}).items()):
        if not isinstance(row, dict):
            continue
        tilt, as_of = row.get("tilt"), row.get("as_of")
        if tilt is None or not as_of or published.get(sym) == as_of:
            continue
        try:
            t = float(tilt)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(t):
            continue
        comps = [c for c in row.get("components") or [] if isinstance(c, dict)]
        features = tuple(sorted(f"alt:{c.get('source')}:{c.get('series')}@{c.get('available_time')}"
                                for c in comps))
        out.append(Belief(model_id=MODEL_ID, subject=_subject(sym), kind="PROBABILITY",
                          value=round(p_up(t), 6), horizon_s=float(HORIZON_S), at=at,
                          confidence=None, features=features,
                          note=f"tilt={t:+.4f} as_of={as_of} n_components={len(comps)}"))
        published[sym] = str(as_of)
    return out


def _first_at_or_after(close: Any, when: datetime) -> float | None:
    try:
        pos = int(close.index.searchsorted(when, side="left"))
    except Exception:                                                   # noqa: BLE001
        return None
    if pos >= len(close):
        return None
    v = float(close.iloc[pos])
    return v if math.isfinite(v) else None


def resolve(rows: list[dict[str, Any]], bars: Callable[[str], Any], now: datetime,
            done: set[str]) -> list[dict[str, Any]]:
    """Resolutions for every accepted belief of this model whose horizon has passed and whose
    bars exist. `done` holds the ids already resolved and is extended in place."""
    out: list[dict[str, Any]] = []
    cache: dict[str, Any] = {}
    for r in rows:
        if r.get("model_id") != MODEL_ID or r.get("status") != "ACCEPTED":
            continue
        bid = f"{r.get('subject')}@{r.get('at')}"
        if bid in done:
            continue
        try:
            at = datetime.fromisoformat(str(r["at"]))
            p = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
        at = at if at.tzinfo else at.replace(tzinfo=UTC)
        end = at + timedelta(seconds=float(r.get("horizon_s") or HORIZON_S))
        if now < end + CLOCK_PAD:
            continue
        sym = str(r.get("subject") or "").split("|", 1)[0]
        if sym not in cache:
            cache[sym] = bars(sym)
        close = cache[sym]
        if close is None:
            continue
        a = _first_at_or_after(close, at + CLOCK_PAD)
        b = _first_at_or_after(close, end + CLOCK_PAD)
        if a is None or b is None:
            continue
        y = 1.0 if b > a else 0.0
        out.append({"id": bid, "model_id": MODEL_ID, "symbol": sym, "at": r["at"], "p": p,
                    "outcome": y, "brier": round((p - y) ** 2, 6),
                    "entry": a, "exit": b, "resolved_at": now.isoformat(timespec="seconds")})
        done.add(bid)
    return out


def skill(resolutions: list[dict[str, Any]]) -> dict[str, Any]:
    """Brier against the coin's 0.25, overall and per instrument. A model with no resolved
    belief is UNMEASURED -- never a score of zero."""
    if not resolutions:
        return {"status": "UNMEASURED", "n": 0,
                "why": "no belief has reached its horizon with bars on both ends yet"}
    def _one(rs: list[dict[str, Any]]) -> dict[str, Any]:
        b = sum(float(r["brier"]) for r in rs) / len(rs)
        return {"n": len(rs), "brier": round(b, 6),
                "skill_vs_climatology": round(1.0 - b / CLIMATOLOGY_BRIER, 6),
                "hit_rate": round(sum(1 for r in rs if (r["p"] > 0.5) == (r["outcome"] > 0.5)
                                      and r["p"] != 0.5) / len(rs), 4)}
    by: dict[str, list[dict[str, Any]]] = {}
    for r in resolutions:
        by.setdefault(str(r["symbol"]), []).append(r)
    return {"status": "MEASURED", **_one(resolutions),
            "by_instrument": {s: _one(rs) for s, rs in sorted(by.items())}}


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def run(desk: Path, intel: dict[str, Any], bars: Callable[[str], Any],
        now: datetime | None = None, register: Path | None = None) -> dict[str, Any]:
    """Publish today's beliefs, resolve matured ones, write the skill report. Called by
    `alt_proxies.run` right after it writes the intel, so the reader runs on the writer's clock."""
    from research import forecast_contract as FC
    now = now or datetime.now(UTC)
    state_path = desk / "data" / "alt_proxies" / "forecast_state.json"
    res_path = desk / "data" / "alt_proxies" / "forecast_resolutions.jsonl"
    report_path = desk / "reports" / "ALT_INTEL_FORECASTS.json"
    state = _read(state_path, {})
    published: dict[str, str] = dict(state.get("published") or {})
    beliefs = beliefs_from_intel(intel, now, published)
    pub = FC.publish(beliefs, register) if beliefs else FC.Publication()
    resolved: list[dict[str, Any]] = []
    try:
        with res_path.open(encoding="utf-8") as fh:
            resolved = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        resolved = []
    done = {str(r.get("id")) for r in resolved}
    fresh = resolve(FC.read_register(register), bars, now, done)
    if fresh:
        res_path.parent.mkdir(parents=True, exist_ok=True)
        with res_path.open("a", encoding="utf-8") as fh:
            for r in fresh:
                fh.write(json.dumps(r) + "\n")
    state["published"] = published
    _atomic(state_path, state)
    try:
        from libs.data.dataset_use import record_reads
        comps = {f"alt_proxies:{c.get('source')}:{c.get('series')}": str(c.get("available_time"))
                 for row in (intel.get("instruments") or {}).values() if isinstance(row, dict)
                 for c in row.get("components") or [] if isinstance(c, dict)}
        if comps:
            record_reads("alt_intel_forecasts", comps, use="nowcast")
    except Exception:                                                   # noqa: BLE001
        pass
    doc = {"at": now.isoformat(timespec="seconds"), "model_id": MODEL_ID,
           "reads": "reports/ALT_PROXIES_ALLOCATION_INTEL.json",
           "publishes_to": "data/forecast_register.jsonl (forecast_contract)",
           "published_this_pass": pub.counts(), "resolved_this_pass": len(fresh),
           "skill": skill(resolved + fresh),
           "mapping": f"p_up = 0.5 + {MAX_P_SHIFT} * clip(tilt, -3, 3) / 3 (declared, uncalibrated)",
           "baseline": "climatology p = 0.5, Brier 0.25",
           "authority": "none: beliefs carry no size and no direction to act on"}
    _atomic(report_path, doc)
    return doc
