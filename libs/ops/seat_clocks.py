"""SEAT CLOCKS: which clock feeds each seat, and which seats have gone silent on every clock.

THE FAILURE THIS NAMES (2026-10-29, `reports/producer_revival/DEAD_PRODUCERS_2026-10-29.md`).
Thirty-three intelligence seats -- aaii, cot, darwinex, arxiv_qfin, the regional platforms, ...
-- were written ONLY by VPS systemd timers (`quant-seed-miners.timer` -> `seed_miners.py`,
`quant-external-pipeline.timer` / `full-pipeline.timer` -> `run_all_miners.py`), and reached the
trading box only through the `intel-ship/send` transport. That transport's last commit was
2026-10-14T01:50Z. MT5-IntelShip kept running with result 0 and adopting nothing, so nothing
anywhere said the seats had stopped: they simply read DEAD in the census two weeks later.

Two things here, both pure (no network, no miner import):

* the SEAT REGISTRY -- each VPS-only seat, the unit that writes it (`seed:<source>` or
  `external:<channel>`), and every clock that runs that unit with its cadence. The box's own
  clock is the `vps_seat_clock` hourly leg (`desks/mt5/side_channels/vps_seat_clock.py`).
* the RED CHECK -- a seat whose clocks have produced nothing for more than TWO cadences of its
  slowest declared clock is RED, and so is a daily proposer with no completed run in two days.
  `ops/never_stale.py` publishes the list, by name, in NEVER_STALE.json.

A seat's output is measured off the FILES its unit writes (`discoveries_*.json` mtimes), not
off a row's own timestamp: a seat that stopped writing is the thing being looked for.
"""
from __future__ import annotations

import glob
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

#: The box clock's per-unit cadence. The hourly leg attempts each unit at most once per this
#: many hours -- never more often than the VPS timer it stands in for -- and skips a unit whose
#: seats already hold output that fresh from ANY clock (the VPS's shipped files included).
BOX_CADENCE_H = 3.0
#: A seat is RED after this many cadences of its slowest clock with no output.
RED_CADENCES = 2
#: The daily proposers' cadence (MT5-Daily / the hourly `daily` leg).
PROPOSER_CADENCE_H = 24.0

VPS_SEED_CLOCK = ("vps:quant-seed-miners.timer", 1.0)
VPS_EXTERNAL_CLOCK = ("vps:quant-external-pipeline.timer", 1.0)
BOX_CLOCK = ("box:hourly_cycle:vps_seat_clock", BOX_CADENCE_H)

#: `seed_miners.MINERS`, in its order (pinned to that dict by a test). Each source writes
#: `data/intelligence/<source>/` -- `regional_survivors` also writes one seat per platform.
SEED_UNITS: tuple[str, ...] = (
    "global_frontier", "regional_survivors", "mql5_survivors", "mql5_signals",
    "myfxbook_outlook", "darwinex", "tradingview_scripts", "fxblue", "collective2",
    "quantconnect", "forexpeacearmy", "ff_calendar_vintage", "forextsd_cdx", "quant_se",
    "arxiv_qfin", "bis_speeches", "broker_swaps", "github_topics", "propfirm_boards",
)
#: `run_all_miners.ALL_MINERS`, in its order (pinned by a test).
EXTERNAL_UNITS: tuple[str, ...] = (
    "youtube", "github", "mql5_codebase", "mql5_articles", "mql5_signals", "mql5_forum",
    "tradingview", "quantconnect", "reddit", "central_bank", "forexfactory", "cot",
    "sec_edgar", "earnings", "aaii", "fear_greed", "investing", "google_trends", "academic",
    "correlations", "seasonality", "weather", "shipping", "china", "korea",
)
#: Where a channel's files land when the directory is not the channel's name.
EXTERNAL_SEAT: dict[str, str] = {
    "central_bank": "central_banks", "mql5_codebase": "mql5", "mql5_articles": "mql5",
    "mql5_signals": "mql5", "mql5_forum": "mql5",
}
#: `regional_survivor_hunters` platforms among the VPS-only seats (it writes a platform's seat
#: only when that platform returned real rows).
REGIONAL_SEATS: tuple[str, ...] = ("amarkets", "fbs_tape", "instaforex_copy", "litefinance",
                                   "trading_latam")

#: THE THIRTY-THREE SEATS WHOSE ONLY CLOCK WAS THE VPS (census 2026-10-29T11:43Z), by unit.
VPS_ONLY_SEATS: dict[str, str] = {
    **dict.fromkeys(REGIONAL_SEATS, "seed:regional_survivors"),
    **{s: f"seed:{s}" for s in (
        "arxiv_qfin", "bis_speeches", "darwinex", "ff_calendar_vintage", "forextsd_cdx",
        "fxblue", "github_topics", "mql5_signals", "mql5_survivors", "propfirm_boards",
        "quant_se", "quantconnect", "regional_survivors", "tradingview_scripts")},
    **{s: f"external:{s}" for s in (
        "aaii", "correlations", "cot", "earnings", "fear_greed", "github", "korea",
        "seasonality", "sec_edgar", "shipping", "tradingview", "weather", "youtube")},
    "central_banks": "external:central_bank",
}

BOX_STATE = DESK / "data" / "vps_seat_clock_state.json"
PROPOSER_STATE = DESK / "data" / "daily_proposers_state.json"


def units() -> list[str]:
    """Every unit the box clock runs, seed first then external, each in its runner's order."""
    return [f"seed:{n}" for n in SEED_UNITS] + [f"external:{n}" for n in EXTERNAL_UNITS]


def unit_seats(unit: str) -> tuple[str, ...]:
    kind, _, name = unit.partition(":")
    if kind == "external":
        return (EXTERNAL_SEAT.get(name, name),)
    if name == "regional_survivors":
        return ("regional_survivors", *REGIONAL_SEATS)
    return (name,)


def unit_clocks(unit: str) -> tuple[tuple[str, float], ...]:
    vps = VPS_SEED_CLOCK if unit.startswith("seed:") else VPS_EXTERNAL_CLOCK
    return (vps, BOX_CLOCK)


def _intel_roots(desk: Path) -> tuple[Path, ...]:
    return (desk / "data" / "intelligence", desk.parent.parent / "data" / "intelligence")


def last_output_ts(seat: str, desk: Path = DESK) -> float | None:
    """Newest `discoveries_*` file mtime for `seat` across both intelligence roots."""
    best: float | None = None
    for root in _intel_roots(desk):
        for f in glob.glob(str(root / seat / "discoveries_*")):
            try:
                m = os.path.getmtime(f)
            except OSError:
                continue
            best = m if best is None or m > best else best
    return best


def unit_last_output_ts(unit: str, desk: Path = DESK) -> float | None:
    ts = [t for t in (last_output_ts(s, desk) for s in unit_seats(unit)) if t is not None]
    return max(ts) if ts else None


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _iso_ts(text: object) -> float | None:
    try:
        dt = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).timestamp()


def _iso(ts: float | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC).isoformat(timespec="seconds")


def red_seats(now: float | None = None, desk: Path = DESK) -> list[dict[str, Any]]:
    """VPS-only seats with no output for more than RED_CADENCES of their slowest clock."""
    now = time.time() if now is None else now
    box = _read(desk / "data" / BOX_STATE.name)
    out: list[dict[str, Any]] = []
    for seat, unit in sorted(VPS_ONLY_SEATS.items()):
        clocks = unit_clocks(unit)
        threshold_h = RED_CADENCES * max(c for _, c in clocks)
        last = last_output_ts(seat, desk)
        age_h = None if last is None else (now - last) / 3600.0
        if age_h is not None and age_h <= threshold_h:
            continue
        b = box.get(unit) or {}
        out.append({
            "seat": seat, "unit": unit, "kind": "seat",
            "clocks": [f"{n} every {c:g}h" for n, c in clocks],
            "last_output_at": _iso(last),
            "age_h": None if age_h is None else round(age_h, 1),
            "threshold_h": threshold_h,
            "box_clock_last_started_at": b.get("last_started_at"),
            "box_clock_last_status": b.get("last_status"),
            "why": (f"no output on any clock for {'ever' if age_h is None else f'{age_h:.1f}h'}"
                    f", past {RED_CADENCES} cadences ({threshold_h:g}h) of its slowest clock"
                    + ("" if b else "; the box clock has never run this unit")),
        })
    return out


def red_proposers(now: float | None = None, desk: Path = DESK,
                  names: list[str] | None = None) -> list[dict[str, Any]]:
    """Daily proposers with no completed (OK) run in RED_CADENCES days."""
    now = time.time() if now is None else now
    if names is None:
        names = _daily_proposers(desk)
    state = _read(desk / "data" / PROPOSER_STATE.name)
    threshold_h = RED_CADENCES * PROPOSER_CADENCE_H
    out: list[dict[str, Any]] = []
    for n in names:
        st = state.get(n) or {}
        if st.get("last_status") == "ABSENT":
            continue
        last = _iso_ts(st.get("last_ok_at"))
        age_h = None if last is None else (now - last) / 3600.0
        if age_h is not None and age_h <= threshold_h:
            continue
        out.append({
            "seat": n, "unit": "daily_cycle:proposers", "kind": "proposer",
            "clocks": [f"MT5-Daily / hourly_cycle:daily every {PROPOSER_CADENCE_H:g}h"],
            "last_output_at": _iso(last), "age_h": None if age_h is None else round(age_h, 1),
            "threshold_h": threshold_h,
            "last_status": st.get("last_status"), "last_started_at": st.get("last_started_at"),
            "why": (f"no completed run for {'ever' if age_h is None else f'{age_h:.1f}h'}, past "
                    f"{RED_CADENCES} daily cadences" + (f"; last attempt {st['last_status']}"
                                                        if st.get("last_status") else "")),
        })
    return out


class Unmeasured(ValueError):
    """A roster this check reads could not be read. Never an empty roster: an empty roster has
    nothing RED in it and so reads clean (PR #524 audit, 2026-10-29)."""


def _daily_tree(desk: Path) -> Any:
    import ast
    src = desk / "research" / "daily_cycle.py"
    try:
        return ast.parse(src.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        raise Unmeasured(f"cannot parse {src}: {type(exc).__name__}: {exc}"[:300]) from exc


def _daily_proposers(desk: Path) -> list[str]:
    """`daily_cycle.PROPOSERS`, from the file's text. Raises Unmeasured -- never returns [] --
    when the file cannot be parsed or the roster is missing, not a literal, or empty."""
    import ast
    for node in _daily_tree(desk).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == "PROPOSERS" and node.value is not None:
            try:
                names = [str(x) for x in ast.literal_eval(node.value)]
            except (ValueError, TypeError, SyntaxError) as exc:
                raise Unmeasured(f"daily_cycle.PROPOSERS is not a literal: "
                                 f"{type(exc).__name__}: {exc}"[:300]) from exc
            if not names:
                raise Unmeasured("daily_cycle.PROPOSERS is empty")
            return names
    raise Unmeasured("daily_cycle.PROPOSERS: no annotated assignment found")


def _daily_steps(desk: Path) -> list[str]:
    """`daily_cycle.STEPS` names, from the file's text (the chain is never imported here).
    Raises Unmeasured -- never returns [] -- when the roster cannot be read or is empty."""
    import ast
    for node in _daily_tree(desk).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "STEPS"
                                                for t in node.targets) \
                and isinstance(node.value, ast.Tuple):
            names = [str(e.elts[0].value) for e in node.value.elts
                     if isinstance(e, ast.Tuple) and e.elts
                     and isinstance(e.elts[0], ast.Constant)]
            if not names:
                raise Unmeasured("daily_cycle.STEPS holds no (name, ...) tuple")
            if len(names) != len(node.value.elts):
                raise Unmeasured(f"daily_cycle.STEPS: {len(node.value.elts) - len(names)} "
                                 f"entr(ies) whose name is not a literal")
            return names
    raise Unmeasured("daily_cycle.STEPS: no tuple assignment found")


def red_daily_steps(now: float | None = None, desk: Path = DESK,
                    names: list[str] | None = None) -> list[dict[str, Any]]:
    """Daily-chain steps with no COMPLETED run in RED_CADENCES days (2026-10-29: MT5-Daily's log
    read "36 step(s) of 37 never did" day after day, and nothing named which)."""
    now = time.time() if now is None else now
    if names is None:
        names = _daily_steps(desk)
    hist = _read(desk / "data" / "daily_step_history.json")
    threshold_h = RED_CADENCES * PROPOSER_CADENCE_H
    out: list[dict[str, Any]] = []
    for n in names:
        h = hist.get(n) or {}
        last = _iso_ts(h.get("last_ok_at"))
        age_h = None if last is None else (now - last) / 3600.0
        if age_h is not None and age_h <= threshold_h:
            continue
        out.append({
            "seat": n, "unit": "daily_cycle:step", "kind": "daily_step",
            "clocks": [f"MT5-Daily / hourly_cycle:daily every {PROPOSER_CADENCE_H:g}h"],
            "last_output_at": _iso(last), "age_h": None if age_h is None else round(age_h, 1),
            "threshold_h": threshold_h, "last_at": h.get("last_at"),
            "last_error": h.get("last_error"),
            "why": (f"no completed run for {'ever' if age_h is None else f'{age_h:.1f}h'}, past "
                    f"{RED_CADENCES} daily cadences"
                    + (f"; last error: {str(h['last_error'])[:120]}" if h.get("last_error")
                       else "" if h else "; never recorded as run")),
        })
    return out


def report(now: float | None = None, desk: Path = DESK) -> dict[str, Any]:
    """RED when anything is RED; else UNMEASURED (with each cause) when any roster could not be
    read; OK only when every check measured and none is RED."""
    unmeasured: list[dict[str, str]] = []
    red: list[dict[str, Any]] = []
    for name, fn in (("seats", red_seats), ("proposers", red_proposers),
                     ("daily_steps", red_daily_steps)):
        try:
            red += fn(now, desk)
        except Exception as exc:
            unmeasured.append({"check": name, "error": f"{type(exc).__name__}: {exc}"[:300]})
    status = "RED" if red else ("UNMEASURED" if unmeasured else "OK")
    return {"status": status, "unmeasured": unmeasured,
            "rule": (f"RED = no output for more than {RED_CADENCES} cadences of the slowest "
                     f"clock that runs it (VPS-only seats: VPS timer 1h + box clock "
                     f"{BOX_CADENCE_H:g}h; daily proposers and daily-chain steps: "
                     f"{PROPOSER_CADENCE_H:g}h)"),
            "n_red": len(red), "red": red}
