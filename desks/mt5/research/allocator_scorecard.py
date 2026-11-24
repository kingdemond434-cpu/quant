#!/usr/bin/env python3
"""ALLOCATOR SCORECARD -- one unified allocator, scored on every account, every pass.

WHY THIS EXISTS (zuck 2026-11-24 18:09Z, PERMANENT): "constantly evolve allocator logic across all
accounts, unified logic, to maximum growth, E[log W]". The objective is one allocator logic:
robust E[log W] on own capital (Fusion), speed x pass probability on the prop accounts (E8, FTMO),
never a firm rule breached and never aggressiveness reduced by fiat. Each later pass ships ONE
improvement aimed at the WEAKEST measure here, so the measurement comes first.

FOUR MEASURES PER ACCOUNT, each OK / WEAK / UNMET / UNMEASURED with its numbers and its reason:

  growth_vs_kelly   Fusion: reports/allocator_attribution.json -- realised dlogW/day and the
                    edge / correlation / execution / regime error terms. Prop: realised R over
                    the trailing window from data/live_ledger_prop.jsonl (no prop forecast ledger
                    exists yet, so the Kelly comparison itself is UNMEASURED and says so).
  risk_utilisation  Fusion: pf_allocation.json heat.total against heat.resolved and the 20% floor.
                    E8: the book's risk if every sleeve fires (E8_BOOK.json) against the room to
                    the daily floor (E8_GUARD.json). FTMO: the executable book (FTMO_ALLOCATOR.json)
                    against the room to the daily and static limits (FTMO_ACCOUNT_STATE.json).
  idle_proven       every sleeve FILL_PROVEN.json admits that holds ZERO weight on the account;
                    each emits an IDLE_PROVEN_SLEEVE event row (account, sleeve, n_out, adjR_out).
  corr_fit          Fusion: the attribution's correlation (dispersion) term. Prop: UNMEASURED --
                    the prop solve borrows Fusion's worlds, so its fit is Fusion's until a
                    prop-side realised-vs-modelled correlation exists.

`weakest` per account is the first UNMET, else the first WEAK, else the first UNMEASURED (an
unmeasured measure is a gap, never a pass), else None.

REPORTS ONLY. Nothing here sizes, gates or sends. Reads artifacts; no MetaTrader, no network, no
LLM. An absent artifact is UNMEASURED with its path named (L1.28a).

    python desks/mt5/research/allocator_scorecard.py --once
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent
REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "ALLOCATOR_SCORECARD.json"
EVENTS = DATA / "allocator_scorecard_events.jsonl"

SCHEMA = "allocator-scorecard/1"
FILL_PROVEN_SCHEMA = "fill-proven/1"
MAX_AGE_H = 3.0
TRAIL_DAYS = 30
HEAT_FLOOR = 0.20
#: FTMO 2-Step limits as fractions of the initial balance (memory: FTMO 2-Step 10% / 5%).
FTMO_DAILY = 0.05
FTMO_MAX = 0.10
#: Prop risk utilisation below this share of the daily room reads WEAK (the book leaves most of
#: the room the firm allows unused); above 1.0 is UNMET (one bad day could breach).
PROP_UTIL_WEAK = 0.25
MEASURES = ("growth_vs_kelly", "risk_utilisation", "idle_proven", "corr_fit")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _m(status: str, why: str, **kw: Any) -> dict[str, Any]:
    return {"status": status, "why": why, **kw}


def _unmeasured(path: Path) -> dict[str, Any]:
    return _m("UNMEASURED", f"{path.name} absent or unreadable")


# ----------------------------------------------------------------------------- inputs

def fill_proven(now: datetime, path: Path | None = None) -> tuple[list[dict[str, Any]], str]:
    doc = _read(path or REPORTS / "FILL_PROVEN.json")
    if not isinstance(doc, dict) or doc.get("schema") != FILL_PROVEN_SCHEMA:
        return [], "UNMEASURED: FILL_PROVEN.json absent or not fill-proven/1"
    gen = _ts(doc.get("generated_at"))
    if gen is None or not 0 <= (now - gen).total_seconds() / 3600 <= MAX_AGE_H:
        return [], "UNMEASURED: FILL_PROVEN.json undated or stale"
    rows = [r for r in doc.get("sleeves") or [] if isinstance(r, dict) and r.get("sleeve")]
    return rows, f"MEASURED: {len(rows)} admitted sleeve(s)"


def _match(label: str, weights: dict[str, float]) -> float:
    """The account's weight for a fill-proven label: exact, else the 27-char ledger truncation."""
    if label in weights:
        return weights[label]
    hits = [v for k, v in weights.items() if k[:27] == label[:27]] if len(label) >= 27 else []
    return hits[0] if len(hits) == 1 else 0.0


def weights(reports: Path = REPORTS) -> dict[str, dict[str, float] | None]:
    """{account: {sleeve: risk weight}} or None when that account's book is unreadable."""
    out: dict[str, dict[str, float] | None] = {}
    pf = _read(reports / "pf_allocation.json")
    book = pf.get("book") if isinstance(pf, dict) else None
    out["fusion"] = ({str(k): float(v) for k, v in book.items() if _num(v) is not None}
                     if isinstance(book, dict) else None)
    e8 = _read(reports / "E8_BOOK.json")
    if isinstance(e8, dict) and isinstance(e8.get("sleeves"), list):
        base = _num(e8.get("risk_frac")) or 0.0
        w: dict[str, float] = {}
        alias: dict[str, float] = {}
        for r in e8["sleeves"]:
            if not isinstance(r, dict):
                continue
            k = f"{r.get('symbol')}_{r.get('family')}_{r.get('selector') or 'asia'}"
            w[k] = _num(r.get("risk_frac")) or base
            if r.get("key"):
                alias[str(r["key"])] = w[k]
        out["e8"] = w
        out["e8_alias"] = alias
    else:
        out["e8"] = out["e8_alias"] = None
    ft = _read(reports / "FTMO_ALLOCATOR.json")
    ex = ft.get("executable") if isinstance(ft, dict) else None
    out["ftmo"] = ({str(k): float(v) for k, v in ex.items() if _num(v) is not None}
                   if isinstance(ex, dict) else None)
    return out


# ----------------------------------------------------------------------------- measures

def _symbol(label: str) -> str:
    return label.split("_", 1)[0].upper()


def tradeable(reports: Path = REPORTS, data: Path = DATA) -> dict[str, set[str] | None]:
    """{account: symbols its venue lists} -- None means the account allows every symbol it was
    given (Fusion's universe is the hunt universe) or the listing is unreadable (then nothing is
    filtered and the reason is the account's own measure)."""
    out: dict[str, set[str] | None] = {"fusion": None}
    e8 = _read(reports / "E8_BOOK.json")
    blocked = set(e8.get("blocked_by_venue") or []) if isinstance(e8, dict) else set()
    out["e8_blocked"] = {str(x).upper() for x in blocked}
    reg = _read(data / "ftmo_registry.json")
    syms = reg.get("symbols") if isinstance(reg, dict) else None
    out["ftmo"] = {str(k).upper() for k in syms} if isinstance(syms, dict) and syms else None
    return out


def idle_proven(account: str, w: dict[str, float] | None, proven: list[dict[str, Any]],
                proven_state: str, alias: dict[str, float] | None = None,
                listed: set[str] | None = None, blocked: set[str] | None = None,
                live: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not proven_state.startswith("MEASURED"):
        return _m("UNMEASURED", proven_state), []
    if w is None:
        return _m("UNMEASURED", f"{account} book unreadable"), []
    if not live:
        return _m("UNMEASURED", f"{account} holds no live book this pass (halted or zero heat)"
                  ), []
    names = {**(alias or {}), **w}
    allowed = [r for r in proven
               if (listed is None or _symbol(str(r["sleeve"])) in listed)
               and _symbol(str(r["sleeve"])) not in (blocked or set())]
    not_allowed = [r["sleeve"] for r in proven if r not in allowed]
    idle = [r for r in allowed if _match(str(r["sleeve"]), names) <= 0]
    events = [{"kind": "IDLE_PROVEN_SLEEVE", "account": account, "sleeve": r["sleeve"],
               "n_out": r.get("n_out"), "adjR_out": r.get("adjR_out")} for r in idle]
    status = "OK" if not idle else "UNMET"
    return _m(status, f"{len(idle)} of {len(allowed)} fill-proven sleeve(s) the venue lists "
                      "hold zero weight",
              n_proven=len(proven), n_allowed=len(allowed), n_idle=len(idle),
              not_allowed_by_venue=not_allowed[:50],
              idle=[r["sleeve"] for r in idle][:50]), events


def fusion_growth(attr: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(attr, dict):
        u = _m("UNMEASURED", "allocator_attribution.json absent or unreadable")
        return u, u
    terms = attr.get("terms") or {}
    vals = {k: (terms.get(k) or {}).get("value") for k in ("edge", "correlation", "execution",
                                                            "regime")}
    dl = (attr.get("dlogw_per_day") or {})
    mean = _num(dl.get("mean")) if isinstance(dl, dict) else None
    edge = _num(vals.get("edge"))
    if edge is None:
        g = _m("UNMEASURED", "the edge term is UNMEASURED", terms=vals, dlogw_per_day=dl)
    else:
        # The edge term is the realised-minus-forecast miss: negative means the book earned less
        # than the allocator expected (its Kelly), positive means more.
        g = _m("OK" if edge >= 0 else "WEAK",
               f"realised minus forecast edge {edge:+.6f}", terms=vals, dlogw_per_day=dl,
               dlogw_mean=mean)
    corr = _num(vals.get("correlation"))
    # HEURISTIC, DECLARED: the dispersion term (growth lost to correlation the allocator did not
    # model) is called WEAK when it is larger in size than the edge miss itself. A realised-vs-
    # modelled pairwise correlation comparison replaces this when one is published.
    c = (_m("UNMEASURED", "the correlation term is UNMEASURED") if corr is None else
         _m("OK" if abs(corr) <= max(abs(edge or 0.0), 1e-9) else "WEAK",
            f"correlation (dispersion) term {corr:+.6f}", value=corr,
            basis="heuristic: |dispersion term| vs |edge miss|; not realised-vs-modelled corr"))
    return g, c


def fusion_util(pf: Any) -> dict[str, Any]:
    heat = pf.get("heat") if isinstance(pf, dict) else None
    if not isinstance(heat, dict):
        return _m("UNMEASURED", "pf_allocation.json has no heat block")
    total, resolved = _num(heat.get("total")), _num(heat.get("resolved"))
    if total is None or resolved is None:
        return _m("UNMEASURED", "heat.total or heat.resolved missing")
    if total + 1e-9 < HEAT_FLOOR:
        st = "UNMET"
    elif resolved > 0 and total < 0.95 * resolved:
        st = "WEAK"
    else:
        st = "OK"
    return _m(st, f"heat {total:.4f} of resolved {resolved:.4f} (floor {HEAT_FLOOR})",
              total=total, resolved=resolved, held=heat.get("held"))


def prop_util(account: str, w: dict[str, float] | None, room_daily: float | None,
              equity: float | None, src: str) -> dict[str, Any]:
    if w is None:
        return _m("UNMEASURED", f"{account} book unreadable")
    if room_daily is None or not equity:
        return _m("UNMEASURED", f"{src} absent or without room/equity")
    used = sum(v for v in w.values() if v > 0)
    room_frac = room_daily / equity
    util = used / room_frac if room_frac > 0 else math.inf
    if util > 1.0:
        st = "UNMET"
    elif util < PROP_UTIL_WEAK:
        st = "WEAK"
    else:
        st = "OK"
    return _m(st, f"book risk if all fire {used:.4f} of equity vs daily room {room_frac:.4f}",
              risk_if_all_fire=round(used, 6), room_daily_frac=round(room_frac, 6),
              utilisation=None if math.isinf(util) else round(util, 4))


def prop_growth(account: str, ledger: Path, now: datetime) -> dict[str, Any]:
    try:
        lines = ledger.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return _m("UNMEASURED", f"{ledger.name} absent")
    cutoff = now - timedelta(days=TRAIL_DAYS)
    rs: list[float] = []
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(d, dict) or str(d.get("book")) != account:
            continue
        t = _ts(d.get("exit_time") or d.get("time"))
        r = _num(d.get("r_multiple"))
        if t is not None and t >= cutoff and r is not None:
            rs.append(r)
    if not rs:
        return _m("UNMEASURED", f"no {account} trades in {TRAIL_DAYS}d of {ledger.name}")
    return _m("UNMEASURED",
              "realised R measured; no prop forecast ledger yet, so the Kelly comparison is "
              "UNMEASURED", n=len(rs), sum_r=round(sum(rs), 4),
              mean_r=round(sum(rs) / len(rs), 4))


def weakest(measures: dict[str, dict[str, Any]]) -> str | None:
    for want in ("UNMET", "WEAK", "UNMEASURED"):
        for k in MEASURES:
            if measures[k]["status"] == want:
                return k
    return None


# ----------------------------------------------------------------------------- build

def build(now: datetime | None = None, reports: Path = REPORTS, data: Path = DATA
          ) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    proven, proven_state = fill_proven(now, reports / "FILL_PROVEN.json")
    w = weights(reports)
    venues = tradeable(reports, data)
    events: list[dict[str, Any]] = []
    accounts: dict[str, dict[str, Any]] = {}

    pf = _read(reports / "pf_allocation.json")
    g, c = fusion_growth(_read(reports / "allocator_attribution.json"))
    heat = (pf.get("heat") or {}) if isinstance(pf, dict) else {}
    fusion_live = bool(w["fusion"]) and (_num(heat.get("total")) or 0.0) > 0
    idle, ev = idle_proven("fusion", w["fusion"], proven, proven_state, live=fusion_live)
    events += ev
    accounts["fusion"] = {"growth_vs_kelly": g, "risk_utilisation": fusion_util(pf),
                          "idle_proven": idle, "corr_fit": c}

    ledger = data / "live_ledger_prop.jsonl"
    prop_corr = _m("UNMEASURED", "the prop solve borrows Fusion's worlds; no prop-side "
                                 "realised-vs-modelled correlation exists yet")
    guard = _read(reports / "E8_GUARD.json")
    gd = guard if isinstance(guard, dict) else {}
    idle, ev = idle_proven("e8", w["e8"], proven, proven_state, w["e8_alias"],
                           blocked=venues.get("e8_blocked"))
    events += ev
    accounts["e8"] = {"growth_vs_kelly": prop_growth("e8", ledger, now),
                      "risk_utilisation": prop_util("e8", w["e8"],
                                                    _num(gd.get("room_to_daily_floor")),
                                                    _num(gd.get("equity")), "E8_GUARD.json"),
                      "idle_proven": idle, "corr_fit": prop_corr}

    st = _read(reports / "FTMO_ACCOUNT_STATE.json")
    sd = st if isinstance(st, dict) else {}
    eq, init, start = (_num(sd.get("equity")), _num(sd.get("initial_balance")),
                       _num(sd.get("day_start_balance")))
    room = (min(eq - (start - FTMO_DAILY * init), eq - (1 - FTMO_MAX) * init)
            if eq is not None and init is not None and start is not None else None)
    idle, ev = idle_proven("ftmo", w["ftmo"], proven, proven_state, listed=venues.get("ftmo"))
    events += ev
    accounts["ftmo"] = {"growth_vs_kelly": prop_growth("ftmo", ledger, now),
                        "risk_utilisation": prop_util("ftmo", w["ftmo"], room, eq,
                                                      "FTMO_ACCOUNT_STATE.json"),
                        "idle_proven": idle, "corr_fit": prop_corr}

    for a in accounts.values():
        a["weakest"] = weakest(a)
    return {"schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
            "objective": {"fusion": "robust E[log W]",
                          "e8": "speed x pass probability within E8's rules",
                          "ftmo": "speed x pass probability within FTMO's rules"},
            "fill_proven": proven_state, "accounts": accounts,
            "n_idle_proven_events": len(events), "events": events,
            "rule": "weakest = first UNMET, else WEAK, else UNMEASURED; reports only"}


def changes(doc: dict[str, Any], prev: Any) -> list[dict[str, Any]]:
    """Events only on a CHANGE against the last report: a sleeve newly idle on an account
    (IDLE_PROVEN_SLEEVE) or newly funded (IDLE_PROVEN_CLEARED). A first report emits every idle."""
    now_idle = {(e["account"], e["sleeve"]): e for e in doc.get("events") or []}
    before: set[tuple[str, str]] = set()
    if isinstance(prev, dict):
        before = {(str(e.get("account")), str(e.get("sleeve")))
                  for e in prev.get("events") or [] if isinstance(e, dict)}
    out = [e for k, e in now_idle.items() if k not in before]
    out += [{"kind": "IDLE_PROVEN_CLEARED", "account": a, "sleeve": sl}
            for a, sl in sorted(before - set(now_idle))]
    return out


def write(doc: dict[str, Any], out: Path = OUT, events: Path = EVENTS) -> None:
    delta = changes(doc, _read(out))
    doc["n_event_changes"] = len(delta)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, out)
    if delta:
        events.parent.mkdir(parents=True, exist_ok=True)
        with events.open("a", encoding="utf-8") as f:
            for e in delta:
                f.write(json.dumps({"at": doc["generated_at"], **e}, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="build and write the scorecard once")
    args = ap.parse_args(argv)
    if not args.once:
        ap.print_help()
        return 0
    doc = build()
    write(doc)
    print("allocator_scorecard: " + "; ".join(
        f"{k} weakest={v['weakest']}" for k, v in doc["accounts"].items())
        + f"; {doc['n_idle_proven_events']} IDLE_PROVEN_SLEEVE")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
