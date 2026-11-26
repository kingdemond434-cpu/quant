"""The box's dashboard feed, built every hour as leg `dashboard_feed` (stdlib only, read only).

WHY IT IS A LEG AND NOT A SCRIPT ON ITS OWN TASK (2026-11-26). The page's pusher
(QuantForge-DashPush, installed by the owner) uploads `desks/mt5/reports/DASHBOARD_FEED.json`
and nothing on the box wrote that file, so the page could only ever say UNMEASURED. A builder
under desks/mt5/scripts/ is money path by rule (replay-shadow), and a new task needs an owner
paste; the hourly cycle already runs repo-level `scripts/*.py` legs, so the feed rides it.

WHAT IT MAY READ, AND WHAT MAY LEAVE. An ALLOW-LIST per source file (`pick`): only the named
keys are ever copied, so a login, server name or key a source file carries can never reach the
feed. A field the box files do not state is None, which the page prints as UNMEASURED. The base
feed (`DASHBOARD_FEED.base.json`, written by nothing on the box today) is optional.

It never opens a terminal, never writes outside `reports/`, and the write is atomic: a failed
build leaves the previous feed in place and exits non-zero, which the cycle ledger records.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1] / "desks" / "mt5"
UNMEASURED = "UNMEASURED: no cloud base feed on this box"
OK_VERDICTS = ("OK", "GREEN", "PASS", "HEALTHY")
#: Free text from a box file reaches the feed only as a short code (Audit should-fix 17:27Z): a
#: heartbeat line naming a host or address would make the pusher refuse the WHOLE feed.
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,47}")
_DOTTED_QUAD = re.compile(r"\d{1,3}(\.\d{1,3}){3}")


def code(x: Any) -> str:
    """`x` as a short identifier, or "withheld" when it is free text."""
    s = str(x).strip()
    return s if _CODE.fullmatch(s) and not _DOTTED_QUAD.search(s) else "withheld"


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def load(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def mtime(p: Path) -> str | None:
    try:
        return _iso(dt.datetime.fromtimestamp(p.stat().st_mtime, dt.UTC))
    except OSError:
        return None


def pick(d: Any, keys: list[str]) -> dict[str, Any]:
    """The allow-list: only these keys can ever leave the box."""
    return {k: d.get(k) for k in keys} if isinstance(d, dict) else dict.fromkeys(keys)


def fnum(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def stamp(d: Any, p: Path, *keys: str) -> str | None:
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, str) and len(v) >= 16:
            return v if v.endswith("Z") or "+" in v else v + "Z"
    return mtime(p)


def _account() -> dict[str, Any]:
    keys = ("phase", "equity", "balance", "day_pnl", "open_positions", "last_deal_utc",
            "room_daily", "room_static", "verdict", "as_of", "source")
    return dict.fromkeys(keys)


def skeleton() -> dict[str, Any]:
    """Every section UNMEASURED; the overlay fills only what the box measures."""
    def gauge() -> dict[str, Any]:
        return {"value": None, "floor": None, "status": None}
    return {
        "schema": 1, "built_at": None,
        "delivery": {"box_sha": None, "adoption_verdict": None, "days_since_adoption": None,
                     "seal_age_d": None, "latest_clear": None, "as_of": None,
                     "source": UNMEASURED},
        "scorecard": {"rules_violated": None, "rules_unmeasured": None, "rules_enforced": None,
                      "rules_total": None, "live_sleeves": None, "standby_sleeves": None,
                      "breadth": {"value": None, "floor": None, "basis": None,
                                  "research_n_eff": None, "research_n_eff_at": None,
                                  "empty_clusters_named": [], "vs_floor": None, "status": None},
                      "depth": gauge(), "conversion": gauge(), "components_alive": None,
                      "bdc_weakest": None, "open_asks": None,
                      "labs": {"fresh": None, "stale": None, "unproven": None, "total": None},
                      "as_of": None, "source": UNMEASURED},
        "pipeline": {"stages": [], "rates": [], "unjudged_backlog": None,
                     "created_per_day": None, "as_of": None, "source": UNMEASURED},
        "accounts": {"FTMO": _account(), "E8": _account(), "Fusion": _account()},
        "strategies": [], "notes": [], "trades": [],
        "memecoin": {"status": None, "note": None, "as_of": None, "equity": None,
                     "start_equity": None, "day_pnl": None, "equity_curve": [],
                     "paper_trades": []},
        "payout": {"ftmo_days": None, "e8_days": None, "target_month_usd": None,
                   "target_window": None, "as_of": None, "source": None},
        "rules": {"as_of": None, "counts": {"VIOLATED": None, "UNMEASURED": None,
                                            "ENFORCED": None}, "items": []},
        "refresh_s": None,
    }


def build(desk: Path, base_path: Path, now: dt.datetime, refresh_s: int) -> dict[str, Any]:
    def P(*a: str) -> Path:
        return desk.joinpath(*a)

    base = load(base_path)
    feed: dict[str, Any] = base if isinstance(base, dict) and base.get("schema") == 1 \
        else skeleton()
    feed.setdefault("accounts", {})
    src: dict[str, str | None] = {}

    pf, pfo = P("reports", "FTMO_ACCOUNT_STATE.json"), P("reports", "FTMO_FOLLOWER.json")
    f_raw = load(pf)
    F = pick(f_raw, ["phase", "balance", "equity", "day_start_balance", "days_traded",
                     "open_positions", "generated_at"])
    FO = pick(load(pfo), ["armed", "lane", "symbol", "placed", "status", "planned_usd"])
    if F["equity"] is not None:
        eq, bal, ds = fnum(F["equity"]), fnum(F["balance"]), fnum(F["day_start_balance"])
        a = feed["accounts"].setdefault("FTMO", _account())
        a.update({
            "phase": (f"phase {F['phase']}, {F['days_traded']} days traded"
                      if F["phase"] is not None else a.get("phase")),
            "equity": eq, "balance": bal,
            "day_pnl": round(eq - ds, 2) if eq is not None and ds is not None else None,
            "open_positions": F["open_positions"], "as_of": stamp(f_raw, pf, "generated_at"),
            "source": "box FTMO_ACCOUNT_STATE.json (day P&L = equity - day_start_balance)"})
        if FO["status"] is not None:
            a["verdict"] = f"follower {code(FO['status'])}, armed={FO['armed']}"
        src["FTMO_ACCOUNT_STATE"] = mtime(pf)

    pe, px = P("reports", "E8_GOLD.json"), P("reports", "E8_EXEC.json")
    E = pick(load(pe), ["equity", "armed", "status", "guard_decision"])
    X = pick(load(px), ["sleeves", "n_considered", "n_sent", "risk_usd_per_trade",
                        "outstanding_stop_risk_usd"])
    if E["equity"] is not None:
        a = feed["accounts"].setdefault("E8", _account())
        a.update({"equity": fnum(E["equity"]), "day_pnl": None, "room_daily": None,
                  "room_static": None,
                  "verdict": f"status {code(E['status'])}, guard {code(E['guard_decision'])}",
                  "as_of": mtime(pe),
                  "source": "box E8_GOLD.json (day P&L and rooms UNMEASURED: no E8 deal ledger)"})
        src["E8_GOLD"] = mtime(pe)

    pa = P("data", "account_state.json")
    a_raw = load(pa)
    A = pick(a_raw, ["balance", "equity", "today_pnl", "open_positions", "venue", "updated_at"])
    if A["equity"] is not None and "fusion" in str(A["venue"]).lower():
        a = feed["accounts"].setdefault("Fusion", _account())
        a.update({"equity": fnum(A["equity"]), "balance": fnum(A["balance"]),
                  "day_pnl": fnum(A["today_pnl"]), "open_positions": A["open_positions"],
                  "as_of": stamp(a_raw, pa, "updated_at"), "source": "box account_state.json"})
        src["account_state"] = mtime(pa)

    strategies: list[dict[str, Any]] = []
    if FO["status"] is not None:
        strategies.append({
            "account": "FTMO", "name": f"ftmo_follower {FO['lane']} ({FO['symbol']})",
            "status": str(FO["status"]).upper(),
            "size": f"planned ${FO['planned_usd']}" if FO["planned_usd"] is not None else None,
            "pnl": None, "note": f"armed={FO['armed']} placed={FO['placed']}",
            "as_of": mtime(pfo)})
    if X["n_considered"] is not None:
        n = len(X["sleeves"]) if isinstance(X["sleeves"], list) else X["sleeves"]
        strategies.append({
            "account": "E8", "name": f"e8 exec ({n} sleeves)",
            "status": "ARMED" if E["armed"] else "IDLE",
            "size": (f"risk ${X['risk_usd_per_trade']}/trade"
                     if X["risk_usd_per_trade"] is not None else None),
            "pnl": None,
            "note": (f"considered {X['n_considered']}, sent {X['n_sent']}, "
                     f"outstanding stop risk ${X['outstanding_stop_risk_usd']}"),
            "as_of": mtime(px)})
        src["E8_EXEC"] = mtime(px)
    if strategies:
        feed["strategies"] = strategies

    pg = P("data", "GATEWAY_LOADED.json")
    G = pick(load(pg), ["release_sha", "last_pass_at"])
    if G["release_sha"] is not None:
        d = feed.setdefault("delivery", {})
        d.update({"box_sha": G["release_sha"], "last_pass_at": G["last_pass_at"],
                  "as_of": G["last_pass_at"] or mtime(pg), "source": "box GATEWAY_LOADED.json"})
        src["GATEWAY_LOADED"] = mtime(pg)

    notes = [n for n in feed.get("notes") or [] if isinstance(n, dict) and n.get("bot") != "livebox"]
    ph = P("reports", "BOX_HEARTBEAT.json")
    H = pick(load(ph), ["verdict", "failing"])
    if H["verdict"] is not None:
        failing = H["failing"] if isinstance(H["failing"], list) else []
        tail = (": " + ", ".join(code(f) for f in failing[:5])) if failing else ""
        notes.append({"bot": "livebox", "text": f"Box heartbeat {code(H['verdict'])}{tail}",
                      "sev": "ok" if str(H["verdict"]).upper() in OK_VERDICTS else "bad",
                      "as_of": mtime(ph)})
        src["BOX_HEARTBEAT"] = mtime(ph)
    paused = P("data", "GATEWAY_PAUSED")
    if paused.exists():
        notes.append({"bot": "livebox", "text": "Gateway is PAUSED (marker present)",
                      "sev": "warn", "as_of": mtime(paused)})
    feed["notes"] = notes

    feed["built_at"] = _iso(now)
    feed["refresh_s"] = refresh_s
    feed["sources"] = {**(feed.get("sources") or {}), **{"live_" + k: v for k, v in src.items()}}
    return feed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desk", type=Path, default=Path(os.environ.get("BOX_ROOT", DESK)))
    ap.add_argument("--base", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--refresh-s", type=int, default=int(os.environ.get("FEED_REFRESH_S", "3600")))
    a = ap.parse_args(argv)
    base = a.base or a.desk / "reports" / "DASHBOARD_FEED.base.json"
    out = a.out or a.desk / "reports" / "DASHBOARD_FEED.json"
    feed = build(a.desk, base, dt.datetime.now(dt.UTC), a.refresh_s)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(feed, indent=1), encoding="utf-8")
    os.replace(tmp, out)
    print("ok", feed["built_at"], sorted(k for k in feed["sources"] if k.startswith("live_")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
