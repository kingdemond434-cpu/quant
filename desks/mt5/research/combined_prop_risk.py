"""COMBINED PROP RISK -- one report across E8, FTMO and Fusion. REPORT-ONLY.

IDEA_QUEUE row 207. gold_asia places a buy-stop and a sell-stop together. On a whipsaw night
both legs can fill and both can stop, and E8 (automated) and FTMO (followed by hand) take that
night together. Nothing measured the joint hit before this file.

What it writes: desks/mt5/reports/COMBINED_PROP_RISK.json
  * one rule matrix (E8 Pro, FTMO 2-Step, Fusion deadman rail);
  * per account: room to the daily floor and the static floor, the daily reset clock;
  * the correlated worst case of the gold_asia two-leg bracket, against each daily limit.

What it does NOT do: it places, sizes, refuses or cancels nothing. It imports no venue and no
gateway, and logs in nowhere. The E8 and Fusion rules are read from their own files by parsing
the source (`ast`), never by importing them, so reading them can have no side effect.

FTMO has no code and no login here, on purpose. Its balance comes from a HAND-ENTERED JSON file
(default desks/mt5/data/ftmo_manual_state.json, see `FTMO_MANUAL_SCHEMA`). A file that carries a
credential-shaped key is refused outright and not read further.

Every input that is absent, unreadable or stale reads UNMEASURED or STALE. It never reads 0 or OK.

NO MONEY FIGURE IS PUBLISHED. Balances, equity, P&L and limits are read and used in memory; the
report carries only fractions (of the initial balance for E8 and FTMO, of current equity for
Fusion), R multiples and verdicts.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `combined_prop_risk` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import combined_prop_risk as M; M.main()"
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
OUT = DESK / "reports" / "COMBINED_PROP_RISK.json"
E8_GUARD_SRC = DESK / "prop" / "e8_guard.py"
E8_GUARD_REPORT = DESK / "reports" / "E8_GUARD.json"
E8_GUARD_STATE = DESK / "data" / "e8_guard_state.json"
FUSION_DEADMAN_SRC = DESK / "proposals" / "fusion_deadman.py"
FUSION_DEADMAN_STATE = DESK / "data" / "fusion_deadman_state.json"
FUSION_ACCOUNT_STATE = DESK / "data" / "account_state.json"
FTMO_MANUAL = DESK / "data" / "ftmo_manual_state.json"

UNMEASURED = "UNMEASURED"
STALE = "STALE"
MEASURED = "MEASURED"
REFUSED = "REFUSED"

#: An account reading older than this is STALE: its rooms are published but flagged, and the
#: worst case against current room is not claimed.
MAX_STATE_AGE_H = 6.0

#: gold_asia two-leg bracket, per the row-207 brief: E8 risks 0.006 of the initial balance per
#: leg, FTMO (following by hand) 0.009 per leg. Fusion's per-leg risk is not stated anywhere this
#: file can read, so it is UNMEASURED unless passed with --fusion-leg-risk.
E8_LEG_RISK = 0.006
FTMO_LEG_RISK = 0.009
LEGS = 2
GAP_R = 1.5

#: Spec values from the brief. Used for E8 only if e8_guard.py cannot be parsed, and then the
#: source says so.
E8_SPEC = {"START_BALANCE": 100_000.0, "PROFIT_TARGET": 0.10, "STATIC_DRAWDOWN": 0.10,
           "DAILY_DRAWDOWN": 0.025, "DAILY_PROFIT_CAP": 0.02,
           "SERVER_ANCHOR_TZ": "America/New_York", "SERVER_MIDNIGHT_ET_HOUR": 17}

#: The FTMO product's nominal balance. Used for arithmetic only; never published.
FTMO_INITIAL = 100_000.0
FTMO_RULES = {
    "firm": "FTMO", "product": "2-Step Challenge (100k nominal)",
    "profit_target_by_phase": {"1": 0.10, "2": 0.05},
    "daily_loss_limit": 0.05, "daily_loss_basis": "5% of initial balance below the day-start "
    "balance (including floating)",
    "max_loss_limit": 0.10, "max_loss_basis": "static: 10% of initial balance",
    "min_trading_days": 4,
    "source": "IDEA_QUEUE row 207 and reports/e8/PROP_FIRM_RACE_2026-10-20.md row 3 "
              "(FTMO public rules; not re-fetched: ftmo.com returned HTTP 403 via the proxy "
              "on 2026-10-21, a hard stop)",
}

FTMO_MANUAL_SCHEMA = {
    "entered_at": "ISO-8601 UTC time the numbers were read off the FTMO dashboard by a human",
    "phase": "1 or 2",
    "initial_balance": "the product's starting balance",
    "balance": "closed balance",
    "equity": "balance plus floating",
    "day_start_balance": "balance at the last FTMO daily reset",
    "trading_days": "count of trading days so far in this phase",
}

#: A hand-entered file must never carry a credential. A key matching any of these refuses it.
_SECRET_MARKERS = ("password", "passwd", "login", "token", "secret", "api_key", "apikey",
                   "investor", "credential")


# ----------------------------------------------------------------------------- readers

def read_constants(src: Path, names: tuple[str, ...]) -> dict[str, Any]:
    """Module-level literal assignments from a Python file, by parsing, never importing."""
    out: dict[str, Any] = {}
    try:
        tree = ast.parse(src.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return out
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            if isinstance(t, ast.Name) and t.id in names and value is not None:
                with contextlib.suppress(ValueError):
                    out[t.id] = ast.literal_eval(value)
    return out


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else None


def _age_h(ts: datetime | None, now: datetime) -> float | None:
    return None if ts is None else round((now - ts).total_seconds() / 3600.0, 2)


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _has_secret_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(m in str(k).lower() for m in _SECRET_MARKERS) or _has_secret_key(v):
                return True
    elif isinstance(obj, list):
        return any(_has_secret_key(v) for v in obj)
    return False


# ----------------------------------------------------------------------------- clocks

def next_reset(now: datetime, tz: str, hour: int) -> datetime:
    """The next wall-clock `hour`:00 in zone `tz` after `now`, in UTC. DST from the zone db."""
    local = now.astimezone(ZoneInfo(tz))
    cand = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if cand <= local:
        cand = (local + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return cand.astimezone(UTC)


def _clock(now: datetime, tz: str, hour: int, source: str, status: str = MEASURED,
           note: str | None = None) -> dict[str, Any]:
    nxt = next_reset(now, tz, hour)
    out: dict[str, Any] = {"status": status, "tz": tz, "local_hour": hour,
                           "next_reset_utc": nxt.isoformat(),
                           "hours_to_reset": round((nxt - now).total_seconds() / 3600.0, 2),
                           "source": source}
    if note:
        out["note"] = note
    return out


# ----------------------------------------------------------------------------- rooms

def rooms(*, equity: float | None, day_start: float | None, initial: float,
          daily_limit: float, static_limit: float) -> dict[str, Any]:
    """Room to the daily and static floors, AS FRACTIONS OF INITIAL. No money figure is returned.

    Daily floor = day-start balance - daily_limit x initial (E8 and FTMO both measure the daily
    limit on the initial balance and both count floating loss). Static floor = initial x (1 -
    static_limit). A missing input gives UNMEASURED for that room, never 0.
    """
    out: dict[str, Any] = {"static_floor_frac_of_initial": round(1.0 - static_limit, 5)}
    if equity is None or not initial > 0:
        out["room_to_static_floor_frac"] = UNMEASURED
    else:
        out["room_to_static_floor_frac"] = round((equity - initial * (1.0 - static_limit))
                                                 / initial, 5)
    if equity is None or day_start is None or not initial > 0:
        out["room_to_daily_floor_frac"] = UNMEASURED
    else:
        daily_floor = day_start - daily_limit * initial
        out["room_to_daily_floor_frac"] = round((equity - daily_floor) / initial, 5)
    return out


def worst_case(*, leg_risk: float | None, initial: float, daily_limit: float,
               room_to_daily: Any, state_status: str, legs: int = LEGS,
               gap_r: float = GAP_R) -> dict[str, Any]:
    """Both gold_asia legs stopped at `leg_risk` each, plus a `gap_r` R gap. Fractions only.

    `daily_limit` and `room_to_daily` are fractions of the same base the leg risk is a fraction
    of. Headline (conservative) reading: 2 legs x 1R + 1.5R gap = 3.5R. The alternative reading,
    each leg's stop slipping to 1.5R (3R total), and the clean 2R are published beside it.
    """
    if leg_risk is None:
        return {"status": UNMEASURED, "why": "per-leg risk for this account is not known"}
    scen = {"both_legs_stopped_2R": legs * 1.0,
            "each_leg_gapped_to_1.5R": legs * gap_r,
            "both_legs_plus_1.5R_gap": legs * 1.0 + gap_r}
    out: dict[str, Any] = {"status": MEASURED, "leg_risk_frac": leg_risk, "legs": legs,
                           "daily_limit_frac": round(daily_limit, 5),
                           "headline": "both_legs_plus_1.5R_gap", "scenarios": {}}
    for name, n_r in scen.items():
        loss = n_r * leg_risk
        row: dict[str, Any] = {
            "R": n_r, "loss_frac": round(loss, 5),
            "frac_of_daily_limit": round(loss / daily_limit, 4),
            "breaches_full_daily_limit": loss >= daily_limit - 1e-12,
        }
        if room_to_daily == UNMEASURED:
            row["breaches_current_daily_room"] = UNMEASURED
        elif state_status != MEASURED:
            row["breaches_current_daily_room"] = state_status
        else:
            row["breaches_current_daily_room"] = loss >= float(room_to_daily)
        out["scenarios"][name] = row
    return out


# ----------------------------------------------------------------------------- accounts

def _state_status(ts: datetime | None, now: datetime, max_age_h: float) -> str:
    if ts is None:
        return UNMEASURED
    return MEASURED if (now - ts) <= timedelta(hours=max_age_h) else STALE


def e8_block(now: datetime, *, guard_src: Path, guard_report: Path, guard_state: Path,
             leg_risk: float, max_age_h: float) -> dict[str, Any]:
    c = read_constants(guard_src, tuple(E8_SPEC))
    if all(k in c for k in E8_SPEC):
        src = f"desks/mt5/prop/{guard_src.name} (parsed, not imported)"
    else:
        c, src = dict(E8_SPEC), "IDEA_QUEUE row 207 brief (e8_guard.py not parseable)"
    initial = float(c["START_BALANCE"])
    rules = {"firm": "E8", "product": "E8 Pro",
             "profit_target": c["PROFIT_TARGET"], "static_drawdown": c["STATIC_DRAWDOWN"],
             "daily_drawdown": c["DAILY_DRAWDOWN"],
             "daily_basis": "of initial balance below day-start balance, floating counted",
             "daily_profit_cap": c["DAILY_PROFIT_CAP"], "source": src}
    clock = _clock(now, c["SERVER_ANCHOR_TZ"], int(c["SERVER_MIDNIGHT_ET_HOUR"]),
                   "desks/mt5/prop/e8_guard.py SERVER_ANCHOR_TZ: midnight server time = 17:00 "
                   "US Eastern, confirmed 2026-09-13 from E8's help centre",
                   note="E8 server midnight (UTC+2 winter / UTC+3 summer) is 17:00 New York")

    rep = read_json(guard_report)
    st = read_json(guard_state)
    equity = day_start = None
    ts = None
    inputs: dict[str, Any] = {"E8_GUARD.json": "present" if rep else "absent",
                              "e8_guard_state.json": "present" if st else "absent"}
    if rep:
        equity = _num(rep.get("equity"))
        day_start = _num(rep.get("day_start"))
        ts = _parse_ts(rep.get("checked_at") or rep.get("updated_at") or rep.get("as_of"))
    if day_start is None and st:
        day_start = _num(st.get("day_start") or st.get("day_start_balance"))
    status = _state_status(ts, now, max_age_h) if equity is not None else UNMEASURED
    acct = {"status": status, "equity": "read" if equity is not None else UNMEASURED,
            "day_start": "read" if day_start is not None else UNMEASURED,
            "state_at": ts.isoformat() if ts else UNMEASURED,
            "state_age_h": _age_h(ts, now) if ts else UNMEASURED, "inputs": inputs}
    if status == UNMEASURED:
        acct["why"] = ("no published E8 state: desks/mt5/reports/E8_GUARD.json and "
                       "desks/mt5/data/e8_guard_state.json are absent or carry no equity/time")
    rm = rooms(equity=equity, day_start=day_start, initial=initial,
               daily_limit=c["DAILY_DRAWDOWN"], static_limit=c["STATIC_DRAWDOWN"])
    wc = worst_case(leg_risk=leg_risk, initial=initial, daily_limit=c["DAILY_DRAWDOWN"],
                    room_to_daily=rm["room_to_daily_floor_frac"], state_status=status)
    return {"rules": rules, "reset_clock": clock, "state": acct, "room": rm,
            "gold_asia_worst_case": wc}


def ftmo_block(now: datetime, *, manual: Path, leg_risk: float,
               max_age_h: float) -> dict[str, Any]:
    rules: dict[str, Any] = dict(FTMO_RULES)
    initial = float(FTMO_INITIAL)
    clock = {"status": UNMEASURED, "claimed": "00:00 Europe/Prague (CE(S)T)",
             "claimed_by": "IDEA_QUEUE row 207 and the pass-17 brief",
             "why": "no FTMO source in the repo and ftmo.com returned HTTP 403 via the proxy "
                    "on 2026-10-21 (hard stop); verify on FTMO's own rule page",
             "if_true_next_reset_utc": next_reset(now, "Europe/Prague", 0).isoformat()}
    raw = read_json(manual)
    acct: dict[str, Any] = {"input_file": str(manual.name), "schema": FTMO_MANUAL_SCHEMA}
    equity = day_start = None
    phase = trading_days = None
    ts = None
    if raw is None:
        acct["status"] = UNMEASURED
        acct["why"] = f"hand-entered file {manual.name} absent or unreadable"
    elif _has_secret_key(raw):
        acct["status"] = REFUSED
        acct["why"] = "file carries a credential-shaped key; not read. Remove it and re-enter."
        raw = None
    if raw is not None:
        initial = _num(raw.get("initial_balance")) or initial
        equity = _num(raw.get("equity"))
        day_start = _num(raw.get("day_start_balance"))
        ts = _parse_ts(raw.get("entered_at"))
        p = raw.get("phase")
        phase = str(p) if str(p) in ("1", "2") else None
        td = raw.get("trading_days")
        trading_days = td if isinstance(td, int) and not isinstance(td, bool) else None
        acct["status"] = _state_status(ts, now, max_age_h) if equity is not None else UNMEASURED
        if equity is None or ts is None:
            acct["why"] = "hand-entered file lacks equity or entered_at"
    st = acct["status"]
    acct.update({"equity": "read" if equity is not None else UNMEASURED,
                 "day_start_balance": "read" if day_start is not None else UNMEASURED,
                 "entered_at": ts.isoformat() if ts else UNMEASURED,
                 "state_age_h": _age_h(ts, now) if ts else UNMEASURED,
                 "phase": phase or UNMEASURED})
    target = rules["profit_target_by_phase"].get(phase) if phase else None
    acct["profit_target"] = target if target is not None else UNMEASURED
    acct["progress_to_target_frac"] = (
        round((equity - initial) / initial / target, 4)
        if target and equity is not None and st in (MEASURED, STALE) else UNMEASURED)
    acct["trading_days"] = {
        "count": trading_days if trading_days is not None else UNMEASURED,
        "minimum": rules["min_trading_days"],
        "remaining": (max(0, rules["min_trading_days"] - trading_days)
                      if trading_days is not None else UNMEASURED)}
    use_eq = equity if st in (MEASURED, STALE) else None
    use_ds = day_start if st in (MEASURED, STALE) else None
    rm = rooms(equity=use_eq, day_start=use_ds, initial=initial,
               daily_limit=rules["daily_loss_limit"], static_limit=rules["max_loss_limit"])
    wc = worst_case(leg_risk=leg_risk, initial=initial, daily_limit=rules["daily_loss_limit"],
                    room_to_daily=rm["room_to_daily_floor_frac"], state_status=st)
    wc["follows_signal"] = "by hand (manual copy of gold_asia)"
    return {"rules": rules, "reset_clock": clock, "state": acct, "room": rm,
            "gold_asia_worst_case": wc}


def fusion_block(now: datetime, *, deadman_src: Path, deadman_state: Path, account: Path,
                 leg_risk: float | None, max_age_h: float) -> dict[str, Any]:
    c = read_constants(deadman_src, ("EQUITY_FLOOR_EUR", "DAILY_LOSS_PCT"))
    floor = c.get("EQUITY_FLOOR_EUR")
    daily_pct = c.get("DAILY_LOSS_PCT")
    rules = {"firm": "Fusion Markets (own account; desk rail, not a prop rule)",
             "currency": "EUR",
             "deadman_equity_floor": "parsed" if floor is not None else UNMEASURED,
             "deadman_daily_loss_pct": daily_pct if daily_pct is not None else UNMEASURED,
             "daily_basis": "realised P&L since 00:00 UTC vs pct x max(peak_equity, equity)",
             "source": "desks/mt5/proposals/fusion_deadman.py (parsed, not imported)"
             if c else UNMEASURED}
    clock = _clock(now, "UTC", 0, "desks/mt5/proposals/fusion_deadman.py: day_start = 00:00 UTC",
                   note="the desk's own rail clock, not a broker rule")
    acc = read_json(account)
    dm = read_json(deadman_state)
    equity = _num(acc.get("equity")) if acc else None
    if equity is not None and not equity > 0:
        equity = None                       # a zero or negative equity is no base for a fraction
    ts = _parse_ts(acc.get("updated_at")) if acc else None
    today_pnl = _num(acc.get("today_pnl")) if acc else None
    peak = _num(dm.get("peak_equity")) if dm else None
    peak_ts = _parse_ts(dm.get("checked_at")) if dm else None
    status = _state_status(ts, now, max_age_h) if equity is not None else UNMEASURED
    # NO MONEY FIGURE IS PUBLISHED: equity, P&L and peak are read, and only their ratios leave.
    state = {"status": status, "equity": "read" if equity is not None else UNMEASURED,
             "state_at": ts.isoformat() if ts else UNMEASURED,
             "state_age_h": _age_h(ts, now) if ts else UNMEASURED,
             "today_pnl": "read" if today_pnl is not None else UNMEASURED,
             "peak_equity": "read" if peak is not None else UNMEASURED,
             "peak_equity_at": peak_ts.isoformat() if peak_ts else UNMEASURED}
    room: dict[str, Any] = {"basis": "fractions of current equity"}
    room["room_to_deadman_floor_frac"] = (round((equity - floor) / equity, 5)
                                          if equity is not None and floor is not None
                                          else UNMEASURED)
    if equity is None or today_pnl is None or peak is None or daily_pct is None:
        room["room_to_daily_rail_frac"] = UNMEASURED
    else:
        ref = max(peak, equity)
        room["room_to_daily_rail_frac"] = round((daily_pct * ref + min(today_pnl, 0.0))
                                                / equity, 5)
        room["room_to_daily_rail_status"] = _state_status(peak_ts, now, max_age_h)
        room["daily_rail_note"] = ("today_pnl is the broker-day figure from account_state; the "
                                   "rail counts realised P&L since 00:00 UTC. Approximate.")
    wc: dict[str, Any]
    if leg_risk is None:
        wc = {"status": UNMEASURED,
              "why": "Fusion's gold_asia per-leg risk is not readable here; pass --fusion-leg-risk"}
    elif equity is None or daily_pct is None or peak is None:
        wc = {"status": UNMEASURED, "why": "Fusion equity, peak or rail missing"}
    else:
        ref = max(peak, equity)
        wc = worst_case(leg_risk=leg_risk, initial=equity, daily_limit=daily_pct * ref / equity,
                        room_to_daily=room["room_to_daily_rail_frac"],
                        state_status=(status if room.get("room_to_daily_rail_status") == MEASURED
                                      else STALE))
        wc["basis"] = "leg risk as a fraction of current equity"
    return {"rules": rules, "reset_clock": clock, "state": state, "room": room,
            "gold_asia_worst_case": wc}


# ----------------------------------------------------------------------------- report

def build(now: datetime | None = None, *, guard_src: Path = E8_GUARD_SRC,
          guard_report: Path = E8_GUARD_REPORT, guard_state: Path = E8_GUARD_STATE,
          ftmo_manual: Path = FTMO_MANUAL, deadman_src: Path = FUSION_DEADMAN_SRC,
          deadman_state: Path = FUSION_DEADMAN_STATE, account: Path = FUSION_ACCOUNT_STATE,
          e8_leg_risk: float = E8_LEG_RISK, ftmo_leg_risk: float = FTMO_LEG_RISK,
          fusion_leg_risk: float | None = None,
          max_age_h: float = MAX_STATE_AGE_H) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    e8 = e8_block(now, guard_src=guard_src, guard_report=guard_report, guard_state=guard_state,
                  leg_risk=e8_leg_risk, max_age_h=max_age_h)
    ftmo = ftmo_block(now, manual=ftmo_manual, leg_risk=ftmo_leg_risk, max_age_h=max_age_h)
    fusion = fusion_block(now, deadman_src=deadman_src, deadman_state=deadman_state,
                          account=account, leg_risk=fusion_leg_risk, max_age_h=max_age_h)
    accounts = {"E8": e8, "FTMO": ftmo, "FUSION": fusion}

    joint: dict[str, Any] = {"scenario": "gold_asia both legs stopped + 1.5R gap, same night",
                             "per_account": {}}
    any_breach_full = False
    unmeasured: list[str] = []
    for name, blk in accounts.items():
        wc = blk["gold_asia_worst_case"]
        if wc.get("status") != MEASURED:
            joint["per_account"][name] = UNMEASURED
            unmeasured.append(name)
            continue
        h = wc["scenarios"][wc["headline"]]
        joint["per_account"][name] = {k: h[k] for k in (
            "loss_frac", "frac_of_daily_limit", "breaches_full_daily_limit",
            "breaches_current_daily_room")}
        any_breach_full = any_breach_full or h["breaches_full_daily_limit"]
    joint["any_account_breaches_full_daily_limit"] = any_breach_full
    joint["unmeasured_accounts"] = unmeasured

    gaps = []
    for name, blk in accounts.items():
        if blk["state"].get("status") != MEASURED:
            gaps.append(f"{name} state {blk['state'].get('status')}")
        if blk["reset_clock"].get("status") != MEASURED:
            gaps.append(f"{name} reset clock UNMEASURED")
    return {
        "artifact": "COMBINED_PROP_RISK", "schema_version": 1, "report_only": True,
        "generated_at": now.isoformat(), "source": "desks/mt5/research/combined_prop_risk.py",
        "idea_queue_row": 207,
        "status": MEASURED if not gaps else "PARTIAL",
        "gaps": gaps,
        "assumptions": [
            "worst case headline = 2 legs x 1R + 1.5R gap (3.5R); 3R (each stop slips to 1.5R) "
            "and clean 2R are published beside it",
            f"E8 leg risk {e8_leg_risk}, FTMO leg risk {ftmo_leg_risk} of initial balance "
            "(row-207 brief)",
            "daily limits of E8 and FTMO measured on initial balance, floating loss counted",
        ],
        "accounts": accounts,
        "joint_worst_case": joint,
    }


def write(report: dict[str, Any], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--ftmo-file", type=Path, default=FTMO_MANUAL)
    ap.add_argument("--fusion-leg-risk", type=float, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    a = ap.parse_args(argv)
    rep = build(ftmo_manual=a.ftmo_file, fusion_leg_risk=a.fusion_leg_risk)
    if a.dry_run:
        print(json.dumps(rep, indent=1, default=str))
    else:
        write(rep, a.out)
        print(f"combined_prop_risk: status={rep['status']} gaps={len(rep['gaps'])}")
    return 0

