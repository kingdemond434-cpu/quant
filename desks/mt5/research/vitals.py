"""VITALS: the box's live state in one file, seconds old (zuck, 2026-11-13: "it must be literally
like a second old").

Every cloud thread and the hourly pass saw a week-old quant because the state they read was spread
over dozens of artifacts, some never published and some frozen (gateway_state.json stopped at
10-30 when the gateway paused). This reads the artifacts the box's own organs already write and
folds them into desks/mt5/reports/VITALS.json, every section stamped with its own "at" (the
source's own timestamp, else its mtime), so a reader sees at once which part is fresh and which
is not. It writes nothing else and touches no terminal.

ON THE WIRE (#1075, Auditor MF2): no account number and no absolute money. Accounts are named by
alias (e8, ftmo, fusion); P&L and drawdown are ratios. The file is published by MT5-ShadowSync
($reportPaths); `vitals.py --check` turns a stale heartbeat into a red exit.

    python desks/mt5/research/vitals.py            # one write
    python desks/mt5/research/vitals.py --serve    # rewrite every --every seconds (resident)
    python desks/mt5/research/vitals.py --check    # RED and exit 1 on a stale heartbeat
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: VITALS_DESK reads another tree's artifacts (a test, or the build box reading the live desk).
DESK = Path(os.environ.get("VITALS_DESK") or Path(__file__).resolve().parents[1])
REPO = DESK.parents[1]
OUT = DESK / "reports" / "VITALS.json"
SCHEMA = 1
UNMEASURED = "UNMEASURED"

_CACHE: dict[str, tuple[float, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _mtime_iso(p: Path) -> str | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(timespec="seconds")
    except OSError:
        return None


def _load(rel: str) -> tuple[Any, str | None]:
    """(parsed JSON, its mtime) -- reparsed only when the file changed, so a 58 MB source costs
    one parse per change, not one per pass. (None, None) when absent or unreadable."""
    p = DESK / rel
    try:
        m = p.stat().st_mtime
    except OSError:
        return None, None
    hit = _CACHE.get(rel)
    if hit is not None and hit[0] == m:
        return hit[1], _mtime_iso(p)
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, _mtime_iso(p)
    _CACHE[rel] = (m, doc)
    return doc, _mtime_iso(p)


def _ratio(num: Any, den: Any) -> float | None:
    try:
        n, d = float(num), float(den)
    except (TypeError, ValueError):
        return None
    return round(n / d, 6) if d else None


def adopted() -> dict[str, Any]:
    sha = None
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        sha = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(REPO), "rev-parse",
                              "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
    hb, hb_at = _load("reports/ADOPTION_HEARTBEAT.json")
    guard, g_at = _load("reports/ADOPT_GUARD.json")
    hb = hb if isinstance(hb, dict) else {}
    guard = guard if isinstance(guard, dict) else {}
    return {"at": hb.get("finished_at") or hb.get("started_at") or hb_at, "sha": sha or UNMEASURED,
            "last_attempt": {"ok": hb.get("ok"), "stage": hb.get("stage"),
                             "started_at": hb.get("started_at")},
            "guard": {"at": guard.get("at") or g_at, "decision": guard.get("decision"),
                      "target": guard.get("target"),
                      "n_uncovered": len(guard.get("uncovered") or [])}}


def certs_and_breadth() -> tuple[dict[str, Any], dict[str, Any]]:
    us, us_at = _load("reports/UNIVERSAL_SURVIVORS.json")
    book, book_at = _load("data/CERT_BOOK_LIVE.json")
    surv = (us or {}).get("survivors") if isinstance(us, dict) else None
    fams: Counter[str] = Counter()
    syms: set[str] = set()
    if isinstance(surv, dict):
        for row in surv.values():
            r = row if isinstance(row, dict) else {}
            # a survivor names itself "<SYM>.<family>.<params>" in `cell`, its symbol in `sym`
            parts = str(r.get("cell") or "").split(".")
            fams[parts[1] if len(parts) > 1 else "?"] += 1
            syms.add(str(r.get("sym") or (parts[0] if parts else "?")))
    per_lane: dict[str, Any] = {}
    if isinstance(book, dict):
        for lane, block in book.items():
            if isinstance(block, dict):
                funded = {k: v for k, v in block.items()
                          if isinstance(v, (int, float)) and v > 0}
                per_lane[lane] = {"funded": len(funded), "columns": sorted(funded)}
    certs = {"at": (us or {}).get("swept_at") if isinstance(us, dict) else None,
             "certificates": len(surv) if isinstance(surv, dict) else UNMEASURED,
             "per_lane": {"at": book_at, **per_lane} if per_lane else UNMEASURED}
    if certs["at"] is None:
        certs["at"] = us_at
    sl, sl_at = _load("data/sleeves.json")
    rows = (sl or {}).get("sleeves") if isinstance(sl, dict) else None
    breadth = {"at": us_at,
               "certs": len(surv) if isinstance(surv, dict) else UNMEASURED,
               "families": len(fams) if fams else UNMEASURED,
               "symbols": len(syms) if syms else UNMEASURED,
               "nominal": len(rows) if isinstance(rows, list) else UNMEASURED,
               "k_eff": UNMEASURED, "by_asset_class": UNMEASURED, "by_lane": UNMEASURED,
               "top_families": dict(fams.most_common(10))}
    return certs, breadth


def sleeves() -> dict[str, Any]:
    sl, at = _load("data/sleeves.json")
    rows = (sl or {}).get("sleeves") if isinstance(sl, dict) else None
    if not isinstance(rows, list):
        return {"at": at, "live": UNMEASURED, "standby": UNMEASURED}
    c = Counter(str(r.get("status")) for r in rows if isinstance(r, dict))
    live = sorted(str(r.get("name")) for r in rows
                  if isinstance(r, dict) and r.get("status") == "LIVE")
    return {"at": at, "live": c.get("LIVE", 0), "standby": c.get("STANDBY", 0),
            "retired": c.get("RETIRED", 0), "live_names": live}


def _door_today() -> tuple[Counter[str], dict[str, str]]:
    """Order-door rows sent today (UTC), by lane prefix of the caller, and each lane's last."""
    p = DESK / "data" / "order_door_ledger.jsonl"
    day = datetime.now(UTC).date().isoformat()
    n: Counter[str] = Counter()
    last: dict[str, str] = {}
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            f.seek(max(0, size - 4_000_000))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return n, last
    for ln in tail:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        at = str(r.get("at") or "")
        if not at.startswith(day) or r.get("door") != "sent":
            continue
        caller = str(r.get("caller") or "?")
        lane = ("ftmo" if caller.startswith("ftmo") else "e8" if caller.startswith("e8")
                else "fusion")
        n[lane] += 1
        last[lane] = max(last.get(lane, ""), at)
    return n, last


def accounts() -> dict[str, Any]:
    n, last = _door_today()
    out: dict[str, Any] = {}
    e8, e8_at = _load("reports/E8_EXEC.json")
    g = (e8 or {}).get("guard") or {} if isinstance(e8, dict) else {}
    risk = (e8 or {}).get("risk_usd_per_trade") if isinstance(e8, dict) else None
    out["e8"] = {"at": (e8 or {}).get("at", e8_at) if isinstance(e8, dict) else e8_at,
                 "trades_today": n.get("e8", 0),
                 "pnl_today_pct": _ratio(g.get("day_pnl"), g.get("day_start")),
                 "pnl_today_R": _ratio(g.get("day_pnl"), risk),
                 "dd_pct": _ratio(g.get("room_to_daily_floor"), g.get("equity")),
                 "dd_note": "dd_pct is room left to today's floor / equity",
                 "may_open": g.get("may_open"), "last_fill_at": last.get("e8")}
    ft, ft_at = _load("reports/FTMO_ACCOUNT_STATE.json")
    ft = ft if isinstance(ft, dict) else {}
    out["ftmo"] = {"at": ft.get("generated_at", ft_at), "status": ft.get("status"),
                   "phase": ft.get("phase"), "days_traded": ft.get("days_traded"),
                   "trades_today": n.get("ftmo", 0),
                   "pnl_today_pct": (_ratio(float(ft["equity"]) - float(ft["day_start_balance"]),
                                            ft["day_start_balance"])
                                     if ft.get("equity") is not None
                                     and ft.get("day_start_balance") else None),
                   "pnl_today_R": UNMEASURED,
                   "dd_pct": (_ratio(float(ft["initial_balance"]) - float(ft["equity"]),
                                     ft["initial_balance"])
                              if ft.get("equity") is not None and ft.get("initial_balance")
                              else None),
                   "open_positions": len(ft.get("open_positions") or [])
                   if isinstance(ft.get("open_positions"), list) else ft.get("open_positions"),
                   "last_fill_at": last.get("ftmo")}
    gs, gs_at = _load("data/gateway_state.json")
    gs = gs if isinstance(gs, dict) else {}
    ds = gs.get("day_start_equity") if isinstance(gs.get("day_start_equity"), dict) else {}
    paused = (DESK / "data" / "GATEWAY_PAUSED").exists()
    out["fusion"] = {"at": gs.get("paused_reading_at") or gs.get("last_reconcile") or gs_at,
                     "paused": paused, "trades_today": n.get("fusion", 0),
                     "pnl_today_pct": (_ratio(float(gs["equity"]) - float(ds["equity"]),
                                              ds["equity"])
                                       if gs.get("equity") is not None and ds.get("equity")
                                       and ds.get("date") == datetime.now(UTC).date().isoformat()
                                       else None),
                     "pnl_today_R": UNMEASURED, "dd_pct": UNMEASURED,
                     "last_fill_at": last.get("fusion")}
    return out


def allocator() -> dict[str, Any]:
    fa, at = _load("reports/FTMO_ALLOCATOR.json")
    fa = fa if isinstance(fa, dict) else {}
    cols = ((fa.get("universe") or {}).get("columns") or {}) if isinstance(fa.get("universe"),
                                                                         dict) else {}
    admitted = sorted(k for k, v in cols.items() if isinstance(v, dict) and v.get("admitted"))
    refused = Counter(str(v.get("why"))[:80] for v in cols.values()
                      if isinstance(v, dict) and not v.get("admitted"))
    return {"at": fa.get("generated_at", at),
            "ftmo": {"admitted_columns": admitted, "n_admitted": len(admitted),
                     "n_refused": sum(refused.values()), "refused_by": dict(refused.most_common(5)),
                     "book": fa.get("book"), "status": fa.get("status")}}


def organs() -> dict[str, Any]:
    ph, at = _load("reports/process_health.json")
    ph = ph if isinstance(ph, dict) else {}
    procs = ph.get("processes") if isinstance(ph.get("processes"), list) else []
    rows = {str(p.get("name")): {"last_run": p.get("last_run") or None,
                                 "rc": p.get("last_result_code"), "verdict": p.get("verdict"),
                                 "artifact_age_min": p.get("artifact_age_min")}
            for p in procs if isinstance(p, dict) and p.get("name")}
    return {"at": ph.get("at", at), "counts": ph.get("counts"), "status": ph.get("status"),
            "by_name": rows}


def build() -> dict[str, Any]:
    certs, breadth = certs_and_breadth()
    return {"schema": SCHEMA, "heartbeat_at": _now(), "host": os.environ.get("COMPUTERNAME"),
            "adopted": adopted(), "certs_clocks": certs, "breadth": breadth,
            "sleeves": sleeves(), "accounts": accounts(), "allocator": allocator(),
            "organs": organs(), "ci_queue": {"at": None, "status": UNMEASURED}}


def write(doc: dict[str, Any], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=out.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, sort_keys=True, default=str)
        for attempt in range(10):
            try:
                os.replace(tmp, out)
                break
            except PermissionError:        # a reader holds it open on Windows
                if attempt == 9:
                    raise
                time.sleep(0.1)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
    return out


def verdict(path: Path, max_age_s: float, now: datetime | None = None) -> tuple[bool, str]:
    """A STALE HEARTBEAT IS RED. (ok, line): not ok when VITALS is older than `max_age_s`, absent
    or unreadable -- absence is never a clean verdict."""
    now = now or datetime.now(UTC)
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        at = datetime.fromisoformat(str(doc["heartbeat_at"]).replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, f"RED: VITALS unreadable at {path} ({type(exc).__name__}) -- {UNMEASURED}"
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = (now - at).total_seconds()
    if age > max_age_s:
        return False, f"RED: VITALS heartbeat {age:.0f}s old (limit {max_age_s:.0f}s), at {at}"
    return True, f"OK: VITALS heartbeat {age:.0f}s old"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--every", type=float, default=5.0)
    # --check: read, never write. Exit 1 with a RED line when the heartbeat is stale. A reader of
    # the published mirror (every 15 min) passes --max-age-s 1200.
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--path", default=str(OUT))
    ap.add_argument("--max-age-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    if a.check:
        ok, msg = verdict(Path(a.path), a.max_age_s)
        print(msg)
        return 0 if ok else 1
    while True:
        try:
            write(build())
        except Exception as exc:  # the resident must outlive one bad source
            print(f"{_now()} vitals: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if not a.serve:
                return 1
        if not a.serve:
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())
