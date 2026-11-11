"""HEAT FLOOR LEDGER (hourly-pass idea 606) -- REPORT ONLY: per account and per UTC day, how
long the book sat below the 20% heat floor, how much capital that left idle, and WHY.

Each hourly pass samples every account's heat (open risk / equity) from the venue state the desk
already publishes, keeps one sample per account per UTC hour, and folds the samples into a
daily ledger:

  * fusion  data/xacct/fusion_book.json     (the gateway's published book)
  * e8      data/xacct/e8_book.json         (E8-Gold's published book)
  * ftmo    reports/FTMO_ACCOUNT_STATE.json (prop/ftmo_venue_reader.py)

A sample is MEASURED only when the file holds `equity` and either an `open_risk_usd` figure or
an empty book (no open positions -> zero risk, measured). Anything else -- the file absent,
unreadable, no equity, positions with no risk figure -- is UNMEASURED, never a zero heat.

The floor is the policy's own (`allocator_attribution._heat_bars`, which reads
`research.heat_policy` -- the same HEAT_TARGET check_heat_floor_wiring.py fences on); it is not
re-derived here. Every below-floor hour carries a cause from KNOWN_CAUSES, checked against the
live artifacts; an hour no known cause explains is UNEXPLAINED and counted as a BREACH of the
heat law (GROWTH_GOVERNANCE: the resolved heat is filled, never reported short).

It sizes nothing and touches no money path. Its idle-heat bill is published as
`missed_growth` lines that research/missed_growth.py carries (organ_published_lines).

    python research/heat_floor_ledger.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

OUT = BASE / "reports" / "HEAT_FLOOR_LEDGER.json"
SOURCES: dict[str, Path] = {
    "fusion": BASE / "data" / "xacct" / "fusion_book.json",
    "e8": BASE / "data" / "xacct" / "e8_book.json",
    "ftmo": BASE / "reports" / "FTMO_ACCOUNT_STATE.json",
}
FTMO_ALLOCATOR_ARMED = BASE / "data" / "FTMO_ALLOCATOR_ARMED"
FTMO_EXECUTOR_ARMED = BASE / "data" / "FTMO_EXECUTOR_ARMED"
FTMO_FOLLOWER_INTENTS = BASE / "data" / "ftmo_follower_intents.jsonl"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
KEEP_DAYS = 31
UNMEASURED = "UNMEASURED"
UNEXPLAINED = "UNEXPLAINED"

#: The known-cause table, in the order a below-floor hour is attributed.
KNOWN_CAUSES: dict[str, str] = {
    "ftmo_unarmed": "data/FTMO_ALLOCATOR_ARMED or data/FTMO_EXECUTOR_ARMED absent",
    "gold_only_pin (#954)": "decision_core.GOLD_ASIA_ONLY_ZERO inside PRINCIPAL_ZERO[account]",
    "follow_late_limit (#959)": "an FTMO follower RAIL_BLOCKED row with a late-limit reason "
                                "in the hour",
    "cert_book_zero": "data/CERT_BOOK_LIVE.json pins a sleeve at 0.0 on the account",
}


def heat_floor() -> tuple[float, str]:
    """The policy's floor, through the attribution ledger's reader (never re-derived)."""
    from research.allocator_attribution import _heat_bars
    floor, _ceiling, source = _heat_bars()
    return float(floor), source


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def sample(account: str, path: Path) -> dict[str, Any]:
    """One account's heat now, or UNMEASURED with the reason."""
    doc = _read_json(path)
    if not isinstance(doc, dict):
        why = "absent" if not path.exists() else "unreadable"
        return {"verdict": UNMEASURED, "why": f"{path.name} {why}"}
    equity = _num(doc.get("equity"))
    if equity is None or equity <= 0:
        return {"verdict": UNMEASURED, "why": f"{path.name} carries no positive equity"}
    risk = _num(doc.get("open_risk_usd"))
    if risk is None:
        positions = doc.get("positions")
        n_open = _num(doc.get("open_positions"))
        if (isinstance(positions, list) and not positions) or n_open == 0:
            risk = 0.0
        else:
            return {"verdict": UNMEASURED,
                    "why": f"{path.name} holds positions but no open_risk_usd figure"}
    return {"verdict": "MEASURED", "equity": equity, "open_risk_usd": risk,
            "heat": risk / equity}


def _late_blocks_since(since: datetime) -> bool:
    if not FTMO_FOLLOWER_INTENTS.exists():
        return False
    try:
        lines = FTMO_FOLLOWER_INTENTS.read_text("utf-8").splitlines()[-2000:]
    except OSError:
        return False
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if (isinstance(r, dict) and r.get("status") == "RAIL_BLOCKED"
                and "late" in str(r.get("reason") or "").lower()
                and str(r.get("at") or "") >= since.isoformat()[:19]):
            return True
    return False


def _cert_zero(account: str) -> bool:
    doc = _read_json(CERT_BOOK)
    block = doc.get(account) if isinstance(doc, dict) else None
    if isinstance(block, dict) and isinstance(block.get("book"), dict):
        block = block["book"]
    return isinstance(block, dict) and any(_num(v) == 0.0 for v in block.values())


def causes(account: str, now: datetime) -> list[str]:
    """Every known cause that holds for `account` now, in KNOWN_CAUSES order."""
    out: list[str] = []
    if account == "ftmo" and not (FTMO_ALLOCATOR_ARMED.exists() and FTMO_EXECUTOR_ARMED.exists()):
        out.append("ftmo_unarmed")
    try:
        from mt5desk import decision_core as dc
        GOLD_ASIA_ONLY_ZERO = dc.GOLD_ASIA_ONLY_ZERO
        # after #954 the pin lives behind principal_zeros(), re-armed by GOLD_ASIA_ONLY_ENABLED
        zeros = getattr(dc, "principal_zeros", None)
        pinned = zeros(account) if callable(zeros) else dc.PRINCIPAL_ZERO.get(account, frozenset())
        if GOLD_ASIA_ONLY_ZERO and GOLD_ASIA_ONLY_ZERO.issubset(pinned):
            out.append("gold_only_pin (#954)")
    except Exception:  # an unimportable core names no cause; it is not a cause
        pass
    if account == "ftmo" and _late_blocks_since(now - timedelta(hours=1)):
        out.append("follow_late_limit (#959)")
    if _cert_zero(account):
        out.append("cert_book_zero")
    return out


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def fold(samples: list[dict[str, Any]], floor: float) -> dict[str, dict[str, Any]]:
    """Per account, per UTC day: time-weighted heat over the measured hours, hours below the
    floor, idle capital, causes and breaches. Each hourly sample weighs one hour."""
    days: dict[str, dict[str, Any]] = {}
    for s in samples:
        acct = days.setdefault(s["account"], {})
        d = acct.setdefault(s["hour"][:10], {"hours_sampled": 0, "hours_measured": 0,
                                              "hours_below_floor": 0, "_heat": 0.0,
                                              "idle_capital_usd_hours": 0.0,
                                              "by_cause": {}, "breach_hours": []})
        d["hours_sampled"] += 1
        if s.get("verdict") != "MEASURED":
            continue
        d["hours_measured"] += 1
        d["_heat"] += s["heat"]
        if s["heat"] < floor - 1e-9:
            d["hours_below_floor"] += 1
            d["idle_capital_usd_hours"] += (floor - s["heat"]) * s["equity"]
            cause = (s.get("causes") or [UNEXPLAINED])[0]
            d["by_cause"][cause] = d["by_cause"].get(cause, 0) + 1
            if cause == UNEXPLAINED:
                d["breach_hours"].append(s["hour"])
    for acct in days.values():
        for d in acct.values():
            m = d.pop("_heat")
            n = d["hours_measured"]
            d["time_weighted_heat"] = round(m / n, 6) if n else UNMEASURED
            d["mean_idle_capital_usd"] = (round(d["idle_capital_usd_hours"] / n, 2)
                                          if n else UNMEASURED)
            d["idle_capital_usd_hours"] = round(d["idle_capital_usd_hours"], 2)
            d["hours_unmeasured"] = 24 - n
            d["breach"] = bool(d["breach_hours"])
            if not n:
                d["hours_below_floor"] = UNMEASURED
                d["idle_capital_usd_hours"] = UNMEASURED
    return days


def run(now: datetime | None = None, *, write: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    hour = now.strftime("%Y-%m-%dT%H:00Z")
    floor, floor_source = heat_floor()
    prev = _read_json(OUT) if OUT.exists() else None
    kept = [s for s in ((prev or {}).get("samples") or []) if isinstance(s, dict)
            and s.get("hour", "") >= (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
            and s.get("hour") != hour]
    for account, path in SOURCES.items():
        s = {"account": account, "hour": hour, "source": str(path.relative_to(BASE)),
             **sample(account, path)}
        if s["verdict"] == "MEASURED" and s["heat"] < floor - 1e-9:
            s["causes"] = causes(account, now) or [UNEXPLAINED]
        kept.append(s)
    kept.sort(key=lambda s: (s["hour"], s["account"]))
    ledger = fold(kept, floor)
    today = now.strftime("%Y-%m-%d")
    lines = [{"at": now.isoformat(), "rail": f"heat_floor:{a}", "verdict": UNMEASURED,
              "idle_capital_usd_hours": d["idle_capital_usd_hours"],
              "hours_below_floor": d["hours_below_floor"], "by_cause": d["by_cause"],
              "why": "capital the floor says should carry risk and did not; published, "
                     "the E[log W] price is UNMEASURED"}
             for a, days in ledger.items() for day, d in days.items()
             if day == today and isinstance(d["hours_below_floor"], int)
             and d["hours_below_floor"] > 0]
    breaches = sorted({f"{a}:{h}" for a, days in ledger.items() for d in days.values()
                       for h in d["breach_hours"]})
    doc = {"generated_utc": now.isoformat(), "report_only": True, "consumer": None,
           "intended_consumer": "missed-growth / heat-law review (research/missed_growth.py "
                                "published_gate_lines; GROWTH_GOVERNANCE heat law)",
           "heat_floor": floor, "heat_floor_source": floor_source,
           "known_causes": KNOWN_CAUSES, "accounts": ledger,
           "today": {a: days.get(today) for a, days in ledger.items()},
           "breaches": breaches, "n_breaches": len(breaches),
           "missed_growth": lines, "samples": kept}
    if write:
        _atomic(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = run()
    if a.json:
        print(json.dumps(doc["today"], indent=1, default=str))
    else:
        for acct, d in doc["today"].items():
            print(f"{acct}: {d}")
        print(f"breaches: {doc['n_breaches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
