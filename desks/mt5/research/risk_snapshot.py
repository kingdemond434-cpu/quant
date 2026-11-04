#!/usr/bin/env python3
"""RISK SNAPSHOT -- one hourly page of how close each live account is to its own floors.

REPORT-ONLY. Nothing here halts, sizes or arms anything; every rail stays with its owner
(`proposals/fusion_deadman.py`, `prop/e8_guard.py`, `prop/ftmo_follower.py`). This leg reads the
stamps those owners already write and puts them side by side, per account:

    equity                      the account's own last stamp, with its age
    floors                      distance to the daily-loss, max-loss (deadman / static) and weekly
                                floors, each in account currency and as a fraction of equity
    open risk vs risk_frac      realised open risk / equity against the allocator's risk_frac
                                (`data/CERT_BOOK_LIVE.json`, the positive fractions per account)
    events (next 24 h)          high-impact scheduled events touching a live symbol, from the
                                verified calendar (`libs.execution.event_guard.CALENDAR`) and the
                                macro event ledger (`data/macro/event_ledger.jsonl`); ledger rows
                                whose category is UNCLASSIFIED are listed as UNCLASSIFIED

THE RULE IS L1.28a: an input that is absent, unreadable or stale is UNMEASURED, never 0. A field
that cannot be measured carries `"status": "UNMEASURED"` and a `why`; a number is written only
when the stamp that owns it was read. The rail constants are read from their owners' source by
AST (never re-typed here and never imported, so no MT5 terminal is needed).

Writes desks/mt5/reports/RISK_SNAPSHOT.json. Hourly leg `risk_snapshot` (hourly_cycle.py).
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "RISK_SNAPSHOT.json"

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
HORIZON_H = 24
#: A stamp older than this is a photograph, not a reading: its value is kept as `last_value`
#: under UNMEASURED. Two hourly cycles plus slack.
STALE_H = 3.0


def _paths(desk: Path, root: Path) -> dict[str, Path]:
    d = desk / "data"
    return {
        "gateway_state": d / "gateway_state.json",
        "deadman_state": d / "fusion_deadman_state.json",
        "deadman_src": desk / "proposals" / "fusion_deadman.py",
        "equity_reference_src": desk / "mt5desk" / "fusion_equity_reference.py",
        "equity_reference": d / "FUSION_EQUITY_REFERENCE.json",
        "e8_guard_report": desk / "reports" / "E8_GUARD.json",
        "e8_guard_src": desk / "prop" / "e8_guard.py",
        "ftmo_state": desk / "reports" / "FTMO_ACCOUNT_STATE.json",
        "ftmo_published": d / "account_state.json",
        "ftmo_src": desk / "prop" / "ftmo_follower.py",
        "cert_book": d / "CERT_BOOK_LIVE.json",
        "minlot": d / "MINLOT_OVERRIDE.json",
        "sleeves": d / "sleeves.json",
        "event_ledger": d / "macro" / "event_ledger.jsonl",
        "calendar": root / "data" / "event_calendar.json",
    }


# --------------------------------------------------------------------------- readers

def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _consts(src: Path, names: tuple[str, ...]) -> dict[str, float]:
    """Module-level numeric constants from an owner's source, by AST: the owner stays the truth."""
    try:
        tree = ast.parse(src.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    out: dict[str, float] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            try:
                v = ast.literal_eval(node.value)
            except ValueError:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[node.targets[0].id] = float(v)
    return out


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _parse_ts(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime
            t = parsedate_to_datetime(str(s))
        except (TypeError, ValueError, IndexError):
            return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _age_h(ts: Any, now: datetime) -> float | None:
    t = _parse_ts(ts)
    return None if t is None else round((now - t).total_seconds() / 3600.0, 2)


def _unm(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why}


def _equity(value: float | None, stamp: Any, now: datetime, why: str,
            **extra: Any) -> tuple[dict[str, Any], float | None]:
    """The equity field and the number the floors may use (None unless fresh)."""
    if value is None or value <= 0:
        return _unm(why), None
    age = _age_h(stamp, now)
    if age is None or age > STALE_H:
        return {**_unm(f"equity stamp {stamp!r} is older than {STALE_H} h or undated"),
                "last_value": value, "stamp": stamp, "age_h": age, **extra}, None
    return {"status": MEASURED, "value": value, "stamp": stamp, "age_h": age, **extra}, value


def _floor(equity: float | None, floor: float | None, why_missing: str,
           **extra: Any) -> dict[str, Any]:
    if equity is None or floor is None:
        return {**_unm(why_missing), **extra}
    dist = equity - floor
    return {"status": MEASURED, "floor": round(floor, 2), "distance": round(dist, 2),
            "distance_frac_of_equity": round(dist / equity, 4) if equity > 0 else None, **extra}


def _alloc_risk_frac(cert: Any, account: str) -> dict[str, Any]:
    if not isinstance(cert, dict) or not isinstance(cert.get(account), dict):
        return _unm(f"CERT_BOOK_LIVE.json has no '{account}' block")
    live = {k: float(v) for k, v in cert[account].items()
            if _num(v) is not None and float(v) > 0}
    if not live:
        return _unm(f"CERT_BOOK_LIVE.json '{account}' block holds no positive risk_frac")
    return {"status": MEASURED, "risk_frac": round(sum(live.values()), 6), "sleeves": live}


def _open_risk(n_open: Any, risk_quote: float | None, equity: float | None,
               alloc: dict[str, Any], why: str) -> dict[str, Any]:
    """Realised open risk / equity. Zero only when the stamp positively says zero positions."""
    if equity is None or equity <= 0:
        return _unm("no equity stamp")
    if n_open == 0:
        frac = 0.0
    elif risk_quote is not None:
        frac = risk_quote / equity
    else:
        return {**_unm(why), "open_positions": n_open}
    out: dict[str, Any] = {"status": MEASURED, "open_risk_frac": round(frac, 6),
                           "open_positions": n_open}
    if alloc.get("status") == MEASURED:
        out["allocator_risk_frac"] = alloc["risk_frac"]
        out["ratio_to_allocator"] = round(frac / alloc["risk_frac"], 4)
    else:
        out["allocator_risk_frac"] = UNMEASURED
    return out


# --------------------------------------------------------------------------- accounts

def fusion(p: dict[str, Path], cert: Any, now: datetime) -> dict[str, Any]:
    gw = _read_json(p["gateway_state"])
    dm = _read_json(p["deadman_state"])
    c = _consts(p["deadman_src"], ("EQUITY_FLOOR_EUR", "EQUITY_REARM_HYSTERESIS",
                                   "DAILY_LOSS_PCT", "WEEKLY_LOSS_PCT"))
    doc: dict[str, Any] = {"account": "fusion", "rails_source": str(p["deadman_src"].name)}
    doc["equity"], equity = _equity(
        _num(gw.get("equity")) if isinstance(gw, dict) else None,
        gw.get("last_reconcile") if isinstance(gw, dict) else None, now,
        "gateway_state.json carries no equity")
    halt_codes = (dm or {}).get("halt_codes") or [] if isinstance(dm, dict) else []
    doc["deadman"] = (_unm("fusion_deadman_state.json absent or unreadable")
                      if not isinstance(dm, dict) else
                      {"status": MEASURED, "halt_codes": halt_codes, "mode": dm.get("mode"),
                       "checked_at": dm.get("checked_at"),
                       "age_h": _age_h(dm.get("checked_at"), now)})
    # The withdrawn offset, by the owner's own function (a principal withdrawal is not a loss).
    offset = 0.0
    offset_status = "NO_REFERENCE"
    try:
        spec = importlib.util.spec_from_file_location("_fer", p["equity_reference_src"])
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if equity is not None:
            offset = float(mod.active_offset(equity, p["equity_reference"]))
            offset_status = "ACTIVE" if offset > 0 else "NO_REFERENCE"
    except Exception as exc:  # an unreadable owner is UNMEASURED, not a crash
        offset_status = f"{UNMEASURED}: {type(exc).__name__}"
    floors: dict[str, Any] = {}
    base = c.get("EQUITY_FLOOR_EUR")
    if base is not None and "EQUITY_FLOOR" in halt_codes:
        base *= c.get("EQUITY_REARM_HYSTERESIS", 1.0)
    floors["max_loss_deadman"] = _floor(
        None if equity is None else equity + offset, base,
        "no equity or EQUITY_FLOOR_EUR unreadable",
        judged_on="real equity + withdrawn offset", withdrawn_offset=offset,
        offset_status=offset_status,
        hysteresis_applied="EQUITY_FLOOR" in halt_codes)
    anchor = gw.get("day_start_equity") if isinstance(gw, dict) else None
    today = now.date().isoformat()
    if not isinstance(anchor, dict) or _num(anchor.get("equity")) is None:
        floors["daily_loss"] = _unm("no day_start_equity anchor in gateway_state.json")
    elif "DAILY_LOSS_PCT" not in c:
        floors["daily_loss"] = _unm("DAILY_LOSS_PCT unreadable from the deadman source")
    elif str(anchor.get("date")) != today:
        floors["daily_loss"] = _unm(f"day_start_equity is dated {anchor.get('date')}, not "
                                    f"{today}: a stale anchor is no opening balance")
    else:
        floors["daily_loss"] = _floor(equity, float(anchor["equity"]) * (1 - c["DAILY_LOSS_PCT"]),
                                      "no equity", anchor=anchor)
    floors["weekly"] = _unm("no week-start equity is stamped by the deadman or the gateway "
                            f"(WEEKLY_LOSS_PCT={c.get('WEEKLY_LOSS_PCT')})")
    doc["floors"] = floors
    alloc = _alloc_risk_frac(cert, "fusion")
    n_open = ((dm or {}).get("readings") or {}).get("open_positions") \
        if isinstance(dm, dict) else None
    dm_age = _age_h(dm.get("checked_at"), now) if isinstance(dm, dict) else None
    if dm_age is None or dm_age > STALE_H:
        n_open = None  # a stale deadman count is not evidence of a flat book
    position = gw.get("position") if isinstance(gw, dict) else None
    risk_q = None
    if isinstance(position, dict):
        risk_q = _num(position.get("risk_quote"))
    doc["open_risk"] = _open_risk(n_open, risk_q, equity, alloc,
                                  "open positions stamped without a per-position risk")
    minlot = _read_json(p["minlot"])
    if isinstance(minlot, dict) and minlot.get("enabled"):
        doc["minlot_override"] = {"lot": minlot.get("lot"), "target_risk":
                                  minlot.get("target_risk"), "sleeves": minlot.get("sleeves")}
    return doc


def e8(p: dict[str, Path], cert: Any, now: datetime) -> dict[str, Any]:
    rep = _read_json(p["e8_guard_report"])
    c = _consts(p["e8_guard_src"], ("START_BALANCE", "STATIC_DRAWDOWN", "DAILY_DRAWDOWN"))
    doc: dict[str, Any] = {"account": "e8", "rails_source": p["e8_guard_src"].name}
    equity = _num(rep.get("equity")) if isinstance(rep, dict) else None
    stamp = (rep or {}).get("generated_at") or (rep or {}).get("at") \
        if isinstance(rep, dict) else None
    doc["equity"], equity = _equity(equity, stamp, now,
                                    "reports/E8_GUARD.json absent or carries no equity",
                                    verdict=(rep or {}).get("verdict")
                                    if isinstance(rep, dict) else None)
    day_start = _num((rep or {}).get("day_start")) if isinstance(rep, dict) else None
    static = (c["START_BALANCE"] * (1 - c["STATIC_DRAWDOWN"])
              if {"START_BALANCE", "STATIC_DRAWDOWN"} <= c.keys() else None)
    daily = (day_start * (1 - c["DAILY_DRAWDOWN"])
             if day_start is not None and "DAILY_DRAWDOWN" in c else None)
    doc["floors"] = {
        "daily_loss": _floor(equity, daily, "no day_start in E8_GUARD.json or rail unreadable"),
        "max_loss_static": _floor(equity, static, "no equity or static rail unreadable"),
        "weekly": {"status": "NO_RULE", "why": "E8 One has no weekly loss rule"},
    }
    doc["open_risk"] = _open_risk(None, None, equity, _alloc_risk_frac(cert, "e8"),
                                  "E8_GUARD.json stamps no open positions or their stops")
    return doc


def ftmo(p: dict[str, Path], cert: Any, now: datetime) -> dict[str, Any]:
    st = _read_json(p["ftmo_state"])
    pub = _read_json(p["ftmo_published"])
    c = _consts(p["ftmo_src"], ("DAILY_LOSS_FRAC", "MAX_LOSS_FRAC"))
    doc: dict[str, Any] = {"account": "ftmo", "rails_source": p["ftmo_src"].name}
    equity = initial = day_start = None
    n_open: Any = None
    if isinstance(st, dict) and st.get("status") == "OK":
        equity = _num(st.get("equity"))
        initial = _num(st.get("initial_balance"))
        day_start = _num(st.get("day_start_balance"))
        pos = st.get("open_positions")
        n_open = len(pos) if isinstance(pos, list) else None
        src, stamp = "reports/FTMO_ACCOUNT_STATE.json", st.get("generated_at")
    elif isinstance(pub, dict) and str(pub.get("server", "")).upper().startswith("FTMO"):
        equity = _num(pub.get("equity"))
        n_open = pub.get("open_positions")
        src, stamp = "data/account_state.json", pub.get("updated_at")
    else:
        src, stamp = None, None
    doc["equity"], equity = _equity(equity, stamp, now,
                                    "neither FTMO_ACCOUNT_STATE.json (status OK) nor an FTMO "
                                    "account_state.json carries equity", source=src)
    daily = (day_start - c["DAILY_LOSS_FRAC"] * initial
             if day_start is not None and initial is not None and "DAILY_LOSS_FRAC" in c
             else None)
    mx = (initial * (1 - c["MAX_LOSS_FRAC"])
          if initial is not None and "MAX_LOSS_FRAC" in c else None)
    doc["floors"] = {
        "daily_loss": _floor(equity, daily, "no day_start_balance/initial_balance stamped"),
        "max_loss": _floor(equity, mx, "no initial_balance stamped"),
        "weekly": {"status": "NO_RULE", "why": "FTMO has no weekly loss rule"},
    }
    doc["open_risk"] = _open_risk(n_open, None, equity, _alloc_risk_frac(cert, "ftmo"),
                                  "FTMO stamps open positions without their stops")
    return doc


# --------------------------------------------------------------------------- events

def live_symbols(p: dict[str, Path], cert: Any) -> dict[str, list[str]]:
    """Live sleeve -> symbol, joined on sleeves.json; unjoinable names are kept as UNMEASURED."""
    by_name: dict[str, str] = {}
    sl = _read_json(p["sleeves"])
    rows = sl.get("sleeves") if isinstance(sl, dict) else sl
    for r in rows or []:
        if isinstance(r, dict) and r.get("name") and r.get("symbol"):
            by_name[str(r["name"])] = str(r["symbol"]).upper()
    live: list[tuple[str, str]] = []
    for acct in ("fusion", "e8", "ftmo"):
        block = cert.get(acct) if isinstance(cert, dict) else None
        live += [(acct, n) for n, v in (block or {}).items()
                 if isinstance(block, dict) and (_num(v) or 0) > 0]
    # The Fusion MINLOT override trades its named sleeves whatever the CERT_BOOK says.
    ml = _read_json(p["minlot"])
    if isinstance(ml, dict) and ml.get("enabled"):
        live += [("fusion", str(n)) for n in ml.get("sleeves") or []]
    out: dict[str, list[str]] = {}
    for acct, name in dict.fromkeys(live):
        sym = by_name.get(name) or ("XAUUSD" if name.startswith("gold_") else None)
        out.setdefault(sym or UNMEASURED, []).append(f"{acct}:{name}")
    return out


def _touches(symbol: str, ccys: set[str], instruments: set[str]) -> bool:
    s = symbol.upper()
    return s in instruments or any(c and c in s for c in ccys)


def events(p: dict[str, Path], symbols: list[str], now: datetime) -> dict[str, Any]:
    end = now + timedelta(hours=HORIZON_H)
    out: dict[str, Any] = {"horizon_h": HORIZON_H, "live_symbols": symbols, "events": []}
    cal = _read_json(p["calendar"])
    if not isinstance(cal, dict):
        out["calendar"] = _unm(f"{p['calendar']} absent or unreadable")
    else:
        through = _parse_ts(str(cal.get("valid_through", "")) + "T23:59:59+00:00"
                            if "T" not in str(cal.get("valid_through", ""))
                            else cal.get("valid_through"))
        if through is None or now > through:
            out["calendar"] = _unm(f"calendar valid_through={cal.get('valid_through')!r} is past")
        else:
            out["calendar"] = {"status": MEASURED, "source": cal.get("source"),
                               "not_covered": [s.get("series") for s in
                                               cal.get("pending_sources") or []]}
            for ev in cal.get("events") or []:
                t = _parse_ts(ev.get("utc"))
                if t is None or not (now <= t <= end):
                    continue
                if str(ev.get("impact", "high")).lower() != "high":
                    continue
                # The verified calendar is the Fed's: a USD event.
                hit = [s for s in symbols if _touches(s, {"USD"}, set())]
                if hit:
                    out["events"].append({"source": "calendar", "at": t.isoformat(),
                                          "name": ev.get("name"), "category": "scheduled",
                                          "symbols": hit})
    rows: list[dict[str, Any]] = []
    try:
        for line in p["event_ledger"].read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        out["event_ledger"] = {"status": MEASURED, "rows": len(rows)}
    except OSError:
        out["event_ledger"] = _unm(f"{p['event_ledger']} absent or unreadable")
    for r in rows:
        t = _parse_ts(r.get("happened_at")) or _parse_ts(r.get("published_at"))
        if t is None or not (now <= t <= end):
            continue
        cat = str(r.get("category") or "UNCLASSIFIED")
        imp = _num(r.get("importance"))
        unclassified = cat == "UNCLASSIFIED"
        if not unclassified and (imp is None or imp < 0.7):
            continue
        econ = {str(e).upper() for e in r.get("economies") or [] if e}
        inst = {str(i.get("symbol") if isinstance(i, dict) else i).upper()
                for i in r.get("instruments") or []}
        hit = [s for s in symbols if _touches(s, econ, inst)]
        if not hit and not unclassified:
            continue
        out["events"].append({"source": "event_ledger", "at": t.isoformat(),
                              "name": r.get("title"), "event_id": r.get("event_id"),
                              "category": cat,
                              "importance": imp if not unclassified else UNMEASURED,
                              "symbols": hit if hit else UNMEASURED,
                              **({"status": "UNCLASSIFIED"} if unclassified else {})})
    out["n_events"] = len(out["events"])
    return out


# --------------------------------------------------------------------------- build

def build(now: datetime | None = None, *, desk: Path = DESK, root: Path = ROOT) -> dict[str, Any]:
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    p = _paths(desk, root)
    cert = _read_json(p["cert_book"])
    accounts = {"fusion": fusion(p, cert, now), "e8": e8(p, cert, now),
                "ftmo": ftmo(p, cert, now)}
    sym_map = live_symbols(p, cert)
    syms = sorted(s for s in sym_map if s != UNMEASURED)
    unmeasured = sorted(f"{a}.{k}" for a, d in accounts.items() for k, v in
                        [("equity", d.get("equity")), ("open_risk", d.get("open_risk")),
                         *[(f"floors.{fk}", fv) for fk, fv in (d.get("floors") or {}).items()]]
                        if isinstance(v, dict) and v.get("status") == UNMEASURED)
    return {"generated_at": now.isoformat(timespec="seconds"), "report_only": True,
            "law": "L1.28a: an absent input is UNMEASURED, never 0",
            "accounts": accounts, "live_symbol_map": sym_map,
            "events_next_24h": events(p, syms, now), "unmeasured": unmeasured}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(a.out)
    eq = {k: (v["equity"].get("value") if v["equity"].get("status") == MEASURED else UNMEASURED)
          for k, v in doc["accounts"].items()}
    print(f"risk_snapshot: equity={eq} events={doc['events_next_24h']['n_events']} "
          f"unmeasured={len(doc['unmeasured'])} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
