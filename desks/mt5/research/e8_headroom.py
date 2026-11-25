"""E8 ALL-FIRE HEADROOM (report-only): can the three gold windows breach E8's 2.5% daily floor?

    python research/e8_headroom.py                 write reports/E8_HEADROOM.json
    python research/e8_headroom.py --print         also print the summary

IDEA_QUEUE pass 10, rank 5 (F10-$1 MONEY). E8 trades three XAUUSD windows (asia, london_am,
afternoon). The coordinator states each runs at 0.75% risk; E8's daily drawdown is 2.5% of the
day's opening balance and its static floor is 90% of the start (`prop/e8_guard.py`).
Three stops on one day
are 2.25%. The queue row added markout.json's -0.202R per fill to reach 2.70%, but the desk found
that figure is a unit artifact (markout.py:344-349; true execution ~+0.006R per trade), so it is
carried only as an ARTIFACT_PROXY scenario, never counted. E8's own slip is UNMEASURED, so the
overall flag cannot be GREEN until it is measured.

WHAT IS READ, ALL READ-ONLY, NOTHING IMPORTED FROM THE MONEY PATH. The constants are read from
the source files by `ast` -- never executed -- so this report cannot change, or be changed by,
the code that trades:

    prop/e8_guard.py           START_BALANCE, STATIC_DRAWDOWN, DAILY_DRAWDOWN, STAND_DOWN
    prop/e8_gold.py            RISK_FRAC (reported; the live lane no longer reaches it, below)
    mt5desk/decision_core.py   GOLD_WINDOWS, CLOSE_HOUR, CANCEL_HOUR, BRACKET_TTL_HOURS,
                               E8_CERT_CEILING, PRINCIPAL_ZERO["e8"] (resolved by ast)
    mt5desk/sizing.py          MAX_RISK_FRAC (the cert book's per-value range, as kelly_sizing)
    data/CERT_BOOK_LIVE.json   the e8 block (gold_<window> risk fractions), as kelly_sizing reads it
    reports/KELLY_SURVIVAL.json  the e8 solve (reported; the live lane no longer reaches it)

HOW THE REPOSITORY RESOLVES EACH WINDOW, mirroring `prop/e8_gold.run` as of 2026-11-14: a window
in PRINCIPAL_ZERO["e8"] is 0; a VOID cert book (absent, disabled, torn, a value out of range)
sizes every window at 0; an enabled book is a WHITELIST (a window it does not name is 0); a named
window takes the book's value, capped at E8_CERT_CEILING. The KELLY_SURVIVAL solve and RISK_FRAC
are overridden on every path, so neither can size E8 today and neither is a reason for UNMEASURED.
What IS a reason: an unreadable ceiling, pin set or range, since the live value then cannot be
known from this checkout.
    ops/box_tasks.manifest     the E8-Executor cadence (the guard's polling interval)
    box-published E8 state     data/e8_guard_state.json, reports/E8_GUARD.json,
                               reports/E8_STATE.json
    reports/markout.json       Fusion mean_slip_r, an ARTIFACT_PROXY only; E8 slip UNMEASURED

WHAT IS COMPUTED, per scenario (fractions of the day's opening equity):

  1. concurrent: every window fills the SAME direction (the opposing leg is skipped while a
     position is open, so a second fill can only ADD to the first) and all stops are taken by one
     move before any loss realises -- the sum of stop risk, times (1 + adverse slip).
  2. overlap: the windows' fill intervals [signal hour, session end) and hold intervals (to
     CLOSE_HOUR -- e8_gold has no per-trade time exit) give the most windows that can be open at
     once, and when.
  3. stand-down: the guard flattens at -0.75% of equity (floating included) but only when its
     5-minute pass runs, and `close_all` closes positions; it does not cancel a resting bracket,
     which e8_gold leaves until its session ends. So the stand-down provably prevents the breach
     only for SEQUENTIAL losses (loss to the trip + one leak fill from the resting bracket). For
     concurrent stops the breach is prevented only if the move from -0.75% to -2.5% takes longer
     than a guard pass; that speed is UNMEASURED here, so the verdict is NOT_GUARANTEED.
  4. headroom to the daily and static floors, as fractions of the day's opening balance, when
     box state with equity exists. With no box state they are UNMEASURED, never 0. NO MONEY
     FIGURE IS PUBLISHED: equity and day_start are read and only their ratios leave.

FLAG: RED when any counted scenario's worst case exceeds DAILY_DRAWDOWN; else UNMEASURED while
any counted scenario is UNMEASURED (a scenario with an unknown slip or risk has no worst case);
GREEN only when every counted scenario is measured and inside. ARTIFACT_PROXY rows are reference
only. Nothing here sizes, vetoes or places anything; no execution code reads this file.
Wiring as a report-only hourly leg is described in the pass-10 APPLY.md.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `e8_headroom` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import e8_headroom as M; M.main()"
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "E8_HEADROOM.json"

UNMEASURED = "UNMEASURED"
#: markout.json's mean_slip_r is a MEASUREMENT ARTIFACT, not an execution cost (desk finding
#: 2026-10-20, /mnt/project-files/reports/markout_2026-10-20/README.md): mt5desk/markout.py:344-349
#: divides a PRICE slip by an ACCOUNT-MONEY risk, 96% of the -0.202R is ONE fill row (its
#: broker deal id is never written into this file or its report: Auditor MF1),
#: and its sign means "better than asked". Measured correctly, execution is about +0.006R per
#: trade. A scenario built on it is labelled ARTIFACT_PROXY and is never counted in the worst case
#: or the overall flag.
ARTIFACT_PROXY = "ARTIFACT_PROXY"
ARTIFACT_WHY = ("markout.json mean_slip_r is a unit artifact (markout.py:344-349 divides a price "
                "slip by account-money risk; 96% of it from a single fill; true ~+0.006R per trade, "
                "reports/markout_2026-10-20/README.md). Shown for reference only; never counted")
#: The coordinator's statement of the live E8 book (2026-10-20, E8 live 16:45Z). It is carried as
#: a STATED scenario beside what the repository's own files resolve to, never as a measurement.
STATED_WINDOW_RISK = 0.0075
STATED_SOURCE = "coordinator 2026-10-20: E8 live 16:45Z, three gold windows at 0.75% each"
#: KELLY_SURVIVAL older than `kelly_sizing.KELLY_SURVIVAL_MAX_AGE_S` is not used by the live
#: lane. That constant is ast-read from mt5desk/kelly_sizing.py at build time, never copied here.
KELLY_AGE_NAME = "KELLY_SURVIVAL_MAX_AGE_S"


# ------------------------------------------------------------------ read-only inputs
def literal_constants(path: Path, names: set[str]) -> dict[str, Any]:
    """{name: value} for module-level `NAME = <literal>` assignments, read with ast (never run)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    out: dict[str, Any] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or target.id not in names or value is None:
            continue
        try:
            out[target.id] = ast.literal_eval(value)
        except ValueError:
            continue
    return out


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def literal_sets(path: Path, name: str) -> dict[str, frozenset[str]] | None:
    """A module-level `name: dict[str, frozenset[str]]` whose values are frozenset literals, names
    of such, or `|` unions of them -- resolved with ast, never executed. None when any part of it
    is not resolvable that way (the caller then treats the value as unknown)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    defs: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
                node.targets[0], ast.Name):
            defs[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            defs[node.target.id] = node.value

    def _set(e: ast.expr, depth: int = 0) -> frozenset[str] | None:
        if depth > 20:
            return None
        if isinstance(e, ast.Name):
            ref = defs.get(e.id)
            return None if ref is None else _set(ref, depth + 1)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
            a, b = _set(e.left, depth + 1), _set(e.right, depth + 1)
            return None if a is None or b is None else a | b
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) \
                and e.func.id in ("frozenset", "set") and not e.keywords:
            if not e.args:
                return frozenset()
            try:
                items = ast.literal_eval(e.args[0])
            except ValueError:
                return None
            if isinstance(items, (set, frozenset, list, tuple)) and all(
                    isinstance(x, str) for x in items):
                return frozenset(items)
        return None

    top = defs.get(name)
    if not isinstance(top, ast.Dict):
        return None
    out: dict[str, frozenset[str]] = {}
    for k, v in zip(top.keys, top.values, strict=True):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            return None
        got = _set(v)
        if got is None:
            return None
        out[k.value] = got
    return out


def resolve_live_windows(names: list[str], cert_doc: Any, *, pinned: frozenset[str] | None,
                         ceiling: float | None, max_frac: float | None
                         ) -> tuple[dict[str, float] | None, dict[str, str], str]:
    """(risk per window, where each came from, why-if-unknown), mirroring `prop/e8_gold.run`.

    Precedence (e8_gold.window_sources): pinned_zero > cert_book_void > cert_book_absent >
    cert_book (capped at E8_CERT_CEILING). The solve and RISK_FRAC sit below cert_book_absent and
    cert_book_void, so they are unreachable for every window. Pure."""
    missing = [n for n, v in (("PRINCIPAL_ZERO['e8']", pinned), ("E8_CERT_CEILING", ceiling),
                              ("sizing.MAX_RISK_FRAC", max_frac)) if v is None]
    if missing:
        return None, {}, (f"UNMEASURED: {missing} not resolvable from source, so the live lane's "
                          "window risk is unknown")
    assert pinned is not None and ceiling is not None and max_frac is not None
    cert = cert_e8_windows(cert_doc, max_frac)
    risk: dict[str, float] = {}
    src: dict[str, str] = {}
    for n in names:
        if f"gold_{n}" in pinned:
            risk[n], src[n] = 0.0, "pinned_zero"
        elif cert is None:
            risk[n], src[n] = 0.0, "cert_book_void"
        elif n not in cert:
            risk[n], src[n] = 0.0, "cert_book_absent"
        elif cert[n] > ceiling:
            risk[n], src[n] = ceiling, "cert_book capped at E8_CERT_CEILING"
        else:
            risk[n], src[n] = cert[n], "cert_book"
    return risk, src, ""


def cert_e8_windows(doc: Any, max_frac: float = 0.10) -> dict[str, float] | None:
    """The e8 gold windows of CERT_BOOK_LIVE, voided whole on any bad value (kelly_sizing rule:
    every value a number in [0, sizing.MAX_RISK_FRAC])."""
    if not isinstance(doc, dict) or doc.get("enabled") is not True:
        return None
    block = doc.get("e8")
    if not isinstance(block, dict) or not block:
        return None
    out: dict[str, float] = {}
    for key, raw in block.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        v = float(raw)
        if v != v or not 0.0 <= v <= max_frac:
            return None
        if str(key).startswith("gold_"):
            out[str(key).removeprefix("gold_")] = v
    return out


def kelly_e8_windows(doc: Any, now: datetime, max_age_s: float | None
                     ) -> tuple[dict[str, float] | None, str]:
    """(windows, why). A why starting UNMEASURED means the live lane's choice cannot be known
    from this checkout -- it may or may not use the solve -- so a risk built on it is unknown."""
    if not isinstance(doc, dict):
        return None, "UNMEASURED: reports/KELLY_SURVIVAL.json absent or unreadable here"
    if max_age_s is None:
        return None, (f"UNMEASURED: {KELLY_AGE_NAME} unreadable from mt5desk/kelly_sizing.py, "
                      "so whether the live lane uses this solve is unknown")
    try:
        made = datetime.fromisoformat(str(doc.get("generated_at")))
    except ValueError:
        return None, "UNMEASURED: KELLY_SURVIVAL has no readable generated_at"
    if made.tzinfo is None:
        made = made.replace(tzinfo=UTC)
    age = (now - made).total_seconds()
    if not 0 <= age <= max_age_s:
        return None, f"KELLY_SURVIVAL is {age / 3600:.1f}h old; the live lane ignores it"
    block = doc.get("e8")
    if not isinstance(block, dict) or block.get("status") != "OK":
        return None, "KELLY_SURVIVAL e8 block is not OK; the live lane ignores it"
    out: dict[str, float] = {}
    for w, row in (block.get("windows") or {}).items():
        try:
            v = float(row["risk_frac"])
        except (KeyError, TypeError, ValueError):
            return None, ("KELLY_SURVIVAL e8 window without a readable risk_frac; "
                          "the lane ignores it")
        if v != v or v < 0:
            return None, "KELLY_SURVIVAL e8 holds an invalid risk_frac; the lane ignores it"
        out[str(w)] = v
    if not out:
        return None, "KELLY_SURVIVAL e8 names no window; the lane ignores it"
    return out, "kelly_survival e8"


def guard_cadence_s(manifest: Path) -> float | None:
    """Seconds between E8-Executor passes (it evaluates the guard), from the box task table."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'TASK name="E8-Executor" trigger="every (\d+) (minute|minutes|hour|hours)"',
                  text)
    if not m:
        return None
    return float(m.group(1)) * (60.0 if m.group(2).startswith("minute") else 3600.0)


def slip_r(markout: Any) -> dict[str, Any]:
    """Adverse entry slip in R. E8's own slip is UNMEASURED; markout.json's Fusion figure is
    carried only as an ARTIFACT_PROXY (see ARTIFACT_WHY), and nothing is ever replaced by 0."""
    e8 = {"value": None, "status": UNMEASURED,
          "why": "no E8 fill markout exists in the repository (markout.json matches Fusion deals)"}
    if not isinstance(markout, dict) or not markout.get("usable"):
        return {"e8": e8, "proxy": {"value": None, "status": UNMEASURED,
                                    "why": "reports/markout.json absent or not usable"}}
    raw = markout.get("mean_slip_r")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return {"e8": e8, "proxy": {"value": None, "status": UNMEASURED,
                                    "why": "markout.json has no mean_slip_r"}}
    return {"e8": e8, "proxy": {
        "value": max(0.0, -float(raw)), "status": ARTIFACT_PROXY,
        "mean_slip_r": float(raw), "n_matched": markout.get("n_matched"),
        "at": markout.get("at"),
        "why": ARTIFACT_WHY}}


def _positive(v: Any) -> float | None:
    """v as a float when it is a real number above 0, else None (0 and below are UNMEASURED)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and float(v) > 0:
        return float(v)
    return None


def box_state(desk: Path) -> dict[str, Any]:
    """The box-published E8 state if this checkout holds it: equity and the day's opening
    balance. Each source is named; an absent one is UNMEASURED."""
    srcs = {"e8_guard_state": desk / "data" / "e8_guard_state.json",
            "E8_GUARD": desk / "reports" / "E8_GUARD.json",
            "E8_STATE": desk / "reports" / "E8_STATE.json"}
    seen: dict[str, str] = {}
    equity: float | None = None
    day_start: float | None = None
    for name, p in srcs.items():
        doc = read_json(p)
        if not isinstance(doc, dict):
            seen[name] = f"{UNMEASURED}: {p.relative_to(desk)} absent or unreadable"
            continue
        seen[name] = "read"
        inner = doc.get("decision")
        dec: dict[str, Any] = inner if isinstance(inner, dict) else doc
        # 0 or below is not an equity this report can measure against (an unread account
        # reports 0); it reads UNMEASURED, never as a measured breach or a measured room.
        if equity is None:
            equity = _positive(dec.get("equity"))
        if day_start is None:
            day_start = _positive(dec.get("day_start"))
    return {"sources": seen, "equity": equity, "day_start": day_start}


# ------------------------------------------------------------------ pure arithmetic
def overlap(windows: list[tuple[str, float]], close_hour: float) -> dict[str, Any]:
    """Fill interval [sig, next sig or close) and hold to close_hour per window; the most
    windows open at once and the interval where that happens. Pure."""
    sigs = sorted(windows, key=lambda w: w[1])
    rows: list[dict[str, Any]] = []
    for i, (name, sig) in enumerate(sigs):
        end = sigs[i + 1][1] if i + 1 < len(sigs) else close_hour
        rows.append({"window": name, "fill_from": sig, "fill_until": end, "hold_until": close_hour})
    pts = sorted({r["fill_from"] for r in rows} | {close_hour})
    best, at = 0, None
    for t in pts:
        n = sum(1 for r in rows if r["fill_from"] <= t < r["hold_until"])
        if n > best:
            best, at = n, t
    return {"windows": rows, "max_concurrent": best,
            "max_concurrent_from_hour": at, "max_concurrent_until_hour": close_hour,
            "same_direction_only": True,
            "why": "e8_gold skips only the leg OPPOSING an open XAU position, so concurrent fills "
                   "all lean one way on one instrument: one adverse move takes every stop"}


def scenario(name: str, risks: dict[str, float], source: str, slip: float | None, *,
             daily: float, stand_down: float, max_concurrent: int, cadence_s: float | None
             ) -> dict[str, Any]:
    """Worst cases for one risk vector, in fractions of the day's opening equity. Pure.

    A slip of None is UNMEASURED: the scenario carries no worst case and flag UNMEASURED, never
    a figure computed as if the slip were 0 (L1.28a). A zero-slip scenario passes 0.0 on purpose
    and says so in its name."""
    ordered = sorted(risks.values(), reverse=True)
    concurrent = sum(ordered[:max_concurrent])
    if slip is None:
        return unmeasured_scenario(
            name, source, "the slip this scenario names is UNMEASURED (no usable markout)",
            window_risk=risks, stop_risk_all_fire=round(concurrent, 6), daily=daily)
    s = float(slip)
    conc_slip = concurrent * (1.0 + s)
    # Sequential: windows lose one at a time with a guard pass between; the guard trips once the
    # cumulative loss reaches STAND_DOWN; then one resting bracket (only one window's bracket
    # rests at a time -- each dies at the next window's signal) may still fill and stop.
    cum, tripped_after = 0.0, None
    for i, r in enumerate(ordered):
        cum += r * (1.0 + s)
        if round(cum * 1e6) >= round(stand_down * 1e6):
            tripped_after = i + 1
            break
    leak = 0.0
    if tripped_after is not None and tripped_after < len(ordered):
        leak = ordered[tripped_after] * (1.0 + s)
    sequential = cum + leak
    worst = max(conc_slip, sequential)
    cad = f"every {cadence_s:.0f}s" if cadence_s else "cadence UNMEASURED"
    if conc_slip <= daily:
        prevents = "NOT_NEEDED"
        why = "even all stops at once stay inside the daily floor"
    else:
        prevents = "NOT_GUARANTEED"
        why = (f"sequential losses stop at {sequential:.4%} (trip at {stand_down:.2%} after "
               f"{tripped_after} loss(es), plus one resting-bracket leak: close_all does not "
               f"cancel resting orders), but {max_concurrent} same-direction stops taken by one "
               f"move reach {conc_slip:.4%} before a guard pass "
               f"({cad}) can "
               f"flatten; the gold move speed from -{stand_down:.2%} to -{daily:.2%} equity "
               "against that cadence is UNMEASURED")
    return {
        "scenario": name, "risk_source": source,
        "window_risk": {k: round(v, 6) for k, v in risks.items()},
        "slip_r_used": slip if slip is not None else UNMEASURED,
        "stop_risk_all_fire": round(concurrent, 6),
        "concurrent_slip_adjusted": round(conc_slip, 6),
        "sequential_with_stand_down": round(sequential, 6),
        "stand_down_trips_after_losses": tripped_after,
        "worst_case": round(worst, 6),
        "daily_limit": daily,
        "headroom_to_daily_pct_of_day_start": round(daily - worst, 6),
        "stand_down_prevents_breach": prevents, "stand_down_why": why,
        "flag": "RED" if round(worst * 1e6) > round(daily * 1e6) else "GREEN",
    }


def unmeasured_scenario(name: str, source: str, why: str, *,
                        window_risk: dict[str, float] | None = None,
                        stop_risk_all_fire: float | None = None,
                        daily: float | None = None) -> dict[str, Any]:
    """A scenario whose inputs are not all known: no worst case, flag UNMEASURED. Pure."""
    return {"scenario": name, "risk_source": source,
            "window_risk": ({k: round(v, 6) for k, v in window_risk.items()}
                            if window_risk is not None else UNMEASURED),
            "slip_r_used": UNMEASURED if "slip" in why else None,
            "stop_risk_all_fire": (stop_risk_all_fire if stop_risk_all_fire is not None
                                   else UNMEASURED),
            "concurrent_slip_adjusted": None, "sequential_with_stand_down": None,
            "stand_down_trips_after_losses": None, "worst_case": None,
            "daily_limit": daily, "headroom_to_daily_pct_of_day_start": None,
            "stand_down_prevents_breach": UNMEASURED, "stand_down_why": why,
            "flag": UNMEASURED}


def overall_flag(scen: list[dict[str, Any]]) -> str:
    """RED if any scenario is RED; else UNMEASURED if any is UNMEASURED (or there are none);
    GREEN only when every scenario was measured and none breaches. Pure."""
    flags = [s.get("flag") for s in scen if s.get("counted", True)]
    if "RED" in flags:
        return "RED"
    if not flags or any(f != "GREEN" for f in flags):
        return UNMEASURED
    return "GREEN"


def money_headroom(state: dict[str, Any], worst: float | None, daily: float,
                   static_floor: float) -> dict[str, Any]:
    """Headroom to E8's floors AS FRACTIONS OF THE DAY'S OPENING BALANCE (the worst case's own
    base). Equity, day_start and the floors are used here and never published."""
    eq, ds = _positive(state.get("equity")), _positive(state.get("day_start"))
    if eq is None or ds is None:
        return {"status": UNMEASURED,
                "why": "no box-published E8 equity/day_start in this checkout "
                       "(desks/mt5/reports/* and data/e8_guard_state.json are box-local)",
                "room_to_daily_floor_frac": UNMEASURED, "room_to_static_floor_frac": UNMEASURED,
                "after_worst_case_daily_frac": UNMEASURED,
                "after_worst_case_static_frac": UNMEASURED}
    daily_floor = ds * (1.0 - daily)
    out: dict[str, Any] = {"status": "MEASURED", "basis": "fractions of the day's opening balance",
                           "equity_vs_day_start": round(eq / ds - 1.0, 6),
                           "room_to_daily_floor_frac": round((eq - daily_floor) / ds, 6),
                           "room_to_static_floor_frac": round((eq - static_floor) / ds, 6)}
    if worst is None:
        return {**out, "after_worst_case_daily_frac": UNMEASURED,
                "after_worst_case_static_frac": UNMEASURED,
                "why": "no scenario has a measured worst case"}
    loss = ds * worst
    return {**out, "worst_case_loss_frac": round(worst, 6),
            "after_worst_case_daily_frac": round((eq - loss - daily_floor) / ds, 6),
            "after_worst_case_static_frac": round((eq - loss - static_floor) / ds, 6)}


# ------------------------------------------------------------------ the report
def build(desk: Path = DESK, *, now: datetime | None = None,
          stated_risk: float | None = STATED_WINDOW_RISK) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    guard = literal_constants(desk / "prop" / "e8_guard.py",
                              {"START_BALANCE", "STATIC_DRAWDOWN", "DAILY_DRAWDOWN", "STAND_DOWN"})
    gold = literal_constants(desk / "prop" / "e8_gold.py", {"RISK_FRAC"})
    core = literal_constants(desk / "mt5desk" / "decision_core.py",
                             {"GOLD_WINDOWS", "CLOSE_HOUR", "CANCEL_HOUR", "BRACKET_TTL_HOURS",
                              "E8_CERT_CEILING"})
    missing = [k for k, d in (("STATIC_DRAWDOWN", guard), ("DAILY_DRAWDOWN", guard),
                              ("STAND_DOWN", guard), ("START_BALANCE", guard),
                              ("GOLD_WINDOWS", core), ("CLOSE_HOUR", core)) if k not in d]
    if missing:
        return {"generated_utc": now.isoformat(), "flag": UNMEASURED,
                "why": f"constants not readable from source: {missing}"}
    daily, stand = float(guard["DAILY_DRAWDOWN"]), float(guard["STAND_DOWN"])
    static_dd = float(guard["STATIC_DRAWDOWN"])
    static_floor = float(guard["START_BALANCE"]) * (1.0 - static_dd)
    windows = [(str(w[0]), float(w[1])) for w in core["GOLD_WINDOWS"]]
    names = [w[0] for w in windows]
    ov = overlap(windows, float(core["CLOSE_HOUR"]))
    cadence = guard_cadence_s(desk / "ops" / "box_tasks.manifest")
    slips = slip_r(read_json(desk / "reports" / "markout.json"))
    proxy = slips["proxy"]["value"]

    # What the repository's own files resolve each window to, exactly as e8_gold.run layers them.
    raw_frac = gold.get("RISK_FRAC")
    fallback: float | None = (float(raw_frac) if isinstance(raw_frac, (int, float))
                              and not isinstance(raw_frac, bool) else None)
    ages = literal_constants(desk / "mt5desk" / "kelly_sizing.py", {KELLY_AGE_NAME})
    raw_age = ages.get(KELLY_AGE_NAME)
    max_age = (float(raw_age) if isinstance(raw_age, (int, float))
               and not isinstance(raw_age, bool) else None)
    kelly_doc = read_json(desk / "reports" / "KELLY_SURVIVAL.json")
    kelly, kelly_why = kelly_e8_windows(kelly_doc, now, max_age)
    cert_doc = read_json(desk / "data" / "CERT_BOOK_LIVE.json")
    zeros = literal_sets(desk / "mt5desk" / "decision_core.py", "PRINCIPAL_ZERO")
    pinned = zeros.get("e8") if zeros is not None else None
    raw_ceiling = core.get("E8_CERT_CEILING")
    ceiling = (float(raw_ceiling) if isinstance(raw_ceiling, (int, float))
               and not isinstance(raw_ceiling, bool) else None)
    raw_max = literal_constants(desk / "mt5desk" / "sizing.py", {"MAX_RISK_FRAC"}).get(
        "MAX_RISK_FRAC")
    max_frac = (float(raw_max) if isinstance(raw_max, (int, float))
                and not isinstance(raw_max, bool) else None)
    repo_risk, repo_src, repo_why = resolve_live_windows(
        names, cert_doc, pinned=pinned, ceiling=ceiling, max_frac=max_frac)
    cert = cert_e8_windows(cert_doc, max_frac if max_frac is not None else 0.10)

    scen: list[dict[str, Any]] = []
    kw = {"daily": daily, "stand_down": stand, "max_concurrent": ov["max_concurrent"],
          "cadence_s": cadence}
    # Three slip readings per risk vector: an explicit zero-slip assumption, E8's own slip
    # (UNMEASURED: no E8 markout exists), and the Fusion artifact (reference only, never counted).
    e8_slip = slips["e8"]["value"]
    books: list[tuple[str, dict[str, float] | None, str]] = []
    if stated_risk is not None:
        books.append(("stated_live", {n: float(stated_risk) for n in names}, STATED_SOURCE))
    books.append(("repo_resolved", repo_risk, json.dumps(repo_src) if repo_src else repo_why))
    for book, risks, src in books:
        for suffix, sl in (("no_slip", 0.0), ("e8_slip", e8_slip),
                           ("fusion_artifact_proxy", proxy)):
            nm = f"{book}_{suffix}"
            if risks is None:
                row = unmeasured_scenario(nm, src, repo_why, daily=daily)
            else:
                row = scenario(nm, risks, src, sl, **kw)
            if suffix == "fusion_artifact_proxy":
                row = {**row, "flag": ARTIFACT_PROXY, "counted": False,
                       "artifact_why": ARTIFACT_WHY}
            else:
                row["counted"] = True
            scen.append(row)
    measured = [s for s in scen if s["counted"] and s["worst_case"] is not None]
    worst = max(measured, key=lambda s: s["worst_case"]) if measured else None
    state = box_state(desk)
    flag = overall_flag(scen)
    unmeasured = [s["scenario"] for s in scen if s["counted"] and s["flag"] == UNMEASURED]
    return {
        "generated_utc": now.isoformat(),
        "report_only": True,
        "rule": "RED when any scenario's worst case exceeds E8's daily drawdown; UNMEASURED "
                "(never GREEN) while any scenario is UNMEASURED; nothing here sizes, vetoes or "
                "places an order, and no execution code reads this file",
        "flag": flag,
        "unmeasured_scenarios": unmeasured,
        "worst_case": ({"scenario": worst["scenario"], "fraction": worst["worst_case"],
                        "pct": round(worst["worst_case"] * 100, 4),
                        "daily_limit_pct": daily * 100,
                        "headroom_to_daily_pct": round((daily - worst["worst_case"]) * 100, 4),
                        "over_measured_scenarios_only": bool(unmeasured)}
                       if worst is not None else
                       {"scenario": None, "fraction": None, "pct": None,
                        "daily_limit_pct": daily * 100, "headroom_to_daily_pct": None,
                        "why": "no scenario has a measured worst case"}),
        "arena": {"daily_drawdown": daily, "stand_down": stand,
                  "static_drawdown": static_dd,
                  "static_floor_basis": "fraction of the start balance, checked against equity, "
                                        "never trails",
                  "source": "prop/e8_guard.py (ast-read)"},
        "schedule": {**ov, "close_hour": core["CLOSE_HOUR"],
                     "cancel_hour": core.get("CANCEL_HOUR"),
                     "bracket_ttl_hours": core.get("BRACKET_TTL_HOURS"),
                     "source": "mt5desk/decision_core.py GOLD_WINDOWS (ast-read)"},
        "guard": {"cadence_s": cadence if cadence is not None else UNMEASURED,
                  "evaluates": "equity incl. floating P&L, on each E8-Executor pass",
                  "flatten": "close_all closes positions; resting brackets are NOT cancelled",
                  "placements": "e8_gold places nothing new while stood down"},
        "slippage": slips,
        "risk_inputs": {"cert_book_e8": cert if cert is not None else "VOID (every window 0)",
                        "pinned_zero_e8": sorted(pinned) if pinned is not None else UNMEASURED,
                        "e8_cert_ceiling": ceiling if ceiling is not None else UNMEASURED,
                        "resolved_by": repo_src or repo_why,
                        "kelly_survival_e8": kelly if kelly is not None else kelly_why,
                        "risk_frac_fallback": fallback if fallback is not None else UNMEASURED,
                        "kelly_max_age_s": max_age if max_age is not None else UNMEASURED,
                        "unreachable_in_live_lane": [
                            "kelly_survival_e8", "risk_frac_fallback",
                            "e8_gold.run overrides both: an enabled cert book is a whitelist "
                            "(unnamed windows 0) and a void book sizes every window 0"],
                        "stated": stated_risk if stated_risk is not None else None,
                        "disagreement": (
                            None if stated_risk is None or repo_risk is None or all(
                                abs(v - stated_risk) < 1e-12 for v in repo_risk.values())
                            else f"repository files resolve {repo_risk}; the stated live book is "
                                 f"{stated_risk} per window. The box's own KELLY_SURVIVAL / "
                                 "CERT_BOOK_LIVE decides which is live; both are reported")},
        "scenarios": scen,
        "money_headroom": money_headroom(state, worst["worst_case"] if worst else None, daily,
                                         static_floor),
        "box_state": {"sources": state.get("sources"),
                      "equity": "read" if state.get("equity") is not None else UNMEASURED,
                      "day_start": "read" if state.get("day_start") is not None else UNMEASURED},
        "cross_account": {"status": UNMEASURED,
                          "why": "Fusion+E8 aggregate XAUUSD exposure needs both accounts' open "
                                 "positions; E8's are box-local and not in this checkout"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--stated-window-risk", type=float, default=STATED_WINDOW_RISK)
    ap.add_argument("--no-stated", action="store_true")
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args(argv)
    doc = build(stated_risk=None if args.no_stated else args.stated_window_risk)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    if args.show:
        print(json.dumps({"flag": doc.get("flag"), "worst_case": doc.get("worst_case")}, indent=1))
        for s in doc.get("scenarios", []):
            wc = "UNMEASURED" if s["worst_case"] is None else f"{s['worst_case']:.4%}"
            print(f"{s['scenario']:36s} {wc:>10s} {s['flag']} "
                  f"stand-down={s['stand_down_prevents_breach']}")
    return 0

