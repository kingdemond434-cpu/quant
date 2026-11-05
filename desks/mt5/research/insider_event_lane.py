"""THE INSIDER / POLITICIAN / BUYBACK EVENT LANE -- single-name filings in, candidate cells out.

ONE PASS, THREE READERS, ONE REPORT (sweep rows A18 + A23, item #26):

  form4_lane        Form 4 open-market insider purchase CLUSTERS on the broker-listed US share
                    CFDs, frozen at SEC acceptance -> `insider_cluster_drift` cells (source form4).
  congress          congressional periodic-transaction disclosures, CONSUMED, never collected
                    here: `libs/data/free_stack.fetch_congress` (House Clerk FD index + the
                    disclosure mirror) already collects them into `fs_congress_trades`. And they
                    stay OFF unless the principal sets `QUANT_CONGRESS_ATTEST=1` -- the switch
                    draft PR #641 (`libs/data/congress_gate.py`) puts in front of every reader,
                    because 5 U.S.C. 13107(c) bars commercial use of those reports. When that
                    module is present it decides; when it is not, the same variable is read the
                    same way (exactly "1"), so this lane can never be the reader that leaks.
  buyback_blackout  per-name repurchase blackout windows from 8-K item 2.02 acceptances and the
                    10-Q/10-K repurchase line, and the share of index repurchase dollars in
                    blackout for US500/NAS100/US30 -- a candidate FEATURE only.

THE LANE PROPOSES, THE GAUNTLET JUDGES. Cells go through `proposer_common.donate` (stamped,
lane-filtered to the event lane, pre-registered), each identity once, one trial each. Nothing
here sizes, trades or changes an index cell.

CLOCK. No executable of its own: `alpha_capture.main` (the hourly `alpha_capture` leg of
`hourly_cycle`, the desk's SEC/analyst-view organ under the same `QUANT_EDGAR_UA`) calls `run`
after its own pass, inside the leg's budget. The User-Agent is read from the environment and sent;
it is never printed, logged or written.

WHERE IT LANDS:
  desks/mt5/data/insider_events/   state.json (cursor, filing facts, hold),
                                   form4_transactions.jsonl,
                                   clusters.jsonl (append-only, read by insider_cluster_drift),
                                   congress_events.jsonl (only while attested),
                                   blackout_windows.json
  desks/mt5/data/lake/series/buyback_blackout_share.csv   the feature
  desks/mt5/reports/INSIDER_EVENT_LANE.json               the pass report
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from research import buyback_blackout as bb
    from research import form4_lane as fl
except ImportError:                                         # pragma: no cover - layout
    import buyback_blackout as bb  # type: ignore[no-redef,import-not-found]
    import form4_lane as fl  # type: ignore[no-redef,import-not-found]

SOURCE = "insider_event_lane"
STATE_DIR = fl.STATE_DIR
REPORT = fl.DESK / "reports" / "INSIDER_EVENT_LANE.json"
CONGRESS_SERIES = "fs_congress_trades"
CONGRESS_ENV = "QUANT_CONGRESS_ATTEST"
CONGRESS_SOURCE_ID = "congress_trades"
CONGRESS_EVENTS = "congress_events.jsonl"
#: Disclosed congressional net-buy days a share CFD needs before its cell is minted.
CONGRESS_MIN_EVENTS = 3
#: The lane's default share of the host leg's budget, and the most it ever takes.
DEFAULT_BUDGET_S = 90.0
#: The share of the pass the Form 4 fetch may use before the buyback reader gets the rest.
FORM4_SHARE = 0.7


# ------------------------------------------------------------------------------- congress

def congress_attested(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """{"on", "why"}: #641's switch when it is installed, else the same variable read the same
    way. OFF unless exactly "1"."""
    try:
        from libs.data import congress_gate as cg  # type: ignore[attr-defined]
        return dict(cg.attest_state(env))
    except ImportError:
        e = os.environ if env is None else env
        raw = str(e.get(CONGRESS_ENV, "")).strip()
        if raw == "1":
            return {"on": True, "why": f"{CONGRESS_ENV}=1 (attested by the principal)"}
        return {"on": False, "why": (f"{CONGRESS_ENV}={raw!r} is not 1: OFF" if raw else
                                     f"{CONGRESS_ENV} unset: OFF by default")}


def _congress_frame(series_root: Path) -> Any:
    import pandas as pd
    for suffix in (".parquet", ".csv"):
        p = series_root / f"{CONGRESS_SERIES}{suffix}"
        if p.exists():
            try:
                return pd.read_parquet(p) if suffix == ".parquet" else pd.read_csv(p)
            except Exception:
                return None
    return None


def congress_events(series_root: Path, names: Mapping[str, str]) -> list[dict[str, Any]]:
    """One event per (share CFD, disclosure day) with a POSITIVE disclosed net buy, dated at the
    series' `available_time` (when the desk first held that disclosure) and never earlier than
    the end of the disclosure day. Call only when attested."""
    df = _congress_frame(series_root)
    if df is None or getattr(df, "empty", True) or "available_time" not in df.columns:
        return []
    by_ticker = {t.upper(): s for s, t in names.items()}
    out: list[dict[str, Any]] = []
    for col in df.columns:
        if not str(col).startswith("net_") or col == "net_all":
            continue
        sym = by_ticker.get(str(col)[4:].upper())
        if sym is None:
            continue
        for _i, r in df[["period_end", "available_time", col]].iterrows():
            try:
                v = float(r[col])
            except (TypeError, ValueError):
                continue
            if not v or v != v or v <= 0:
                continue
            avail = fl.parse_time(str(r["available_time"]))
            day = fl.parse_time(str(r["period_end"])[:10])
            if avail is None or day is None:
                continue
            at = max(avail, day + timedelta(days=1))
            out.append({"kind": "CONGRESS_NET_BUY", "symbol": sym, "at": at.isoformat(),
                        "knowable_at": at.isoformat(), "score": v,
                        "disclosed": str(r["period_end"])[:10], "source": CONGRESS_SOURCE_ID})
    out.sort(key=lambda e: (e["at"], e["symbol"]))
    return out


def congress_cells(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sym = Counter(str(e["symbol"]) for e in events)
    return [{"symbol": sym, "symbols": [sym], "kind": "hypothesis",
             "family": fl.EVENT_FAMILY,
             "params": {"symbol": sym, "source": "congress", "hold_days": 5, "timeframe": "H1"},
             "title": f"Congressional disclosed net buy -> {sym} drift ({n} disclosures)"[:120],
             "mechanism": ("disclosed congressional purchases of a name, first public at the "
                           "periodic transaction report, are followed by drift as attention "
                           "catches up with the disclosure"),
             "falsifier": (f"{sym} returns over 5 trading days after each disclosure are no "
                           "better than the name's unconditional drift, net of costs"),
             "lane": "event"} for sym, n in sorted(by_sym.items()) if n >= CONGRESS_MIN_EVENTS]


# ------------------------------------------------------------------------------- donation

def _identity(c: Mapping[str, Any]) -> str:
    return json.dumps({"symbol": c["symbol"], "family": c["family"], "params": c["params"]},
                      sort_keys=True)


def donate_new(cells: list[dict[str, Any]], state: dict[str, Any], *, dry_run: bool
               ) -> dict[str, Any]:
    """Donate the cells never donated before; one trial each at the docket."""
    done = set(state.get("donated") or [])
    new = [c for c in cells if _identity(c) not in done]
    out: dict[str, Any] = {"new": len(new), "already": len(cells) - len(new)}
    if not new or dry_run:
        return out
    try:
        from research import proposer_common as pc
    except ImportError:                                     # pragma: no cover - layout
        import proposer_common as pc  # type: ignore[no-redef,import-not-found]
    path = pc.donate(SOURCE, new, tests_run=len(new))
    out["path"] = str(path) if path else None
    out["donation"] = {k: pc.LAST_DONATION.get(k) for k in
                       ("donated", "refused_unstamped", "refused_wrong_lane")}
    if path:
        state["donated"] = sorted(done | {_identity(c) for c in new})
    return out


# ------------------------------------------------------------------------------- the pass

def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        get: fl.Getter | None = None, state_dir: Path | None = None,
        series_root: Path | None = None, report_path: Path | None = None,
        names: dict[str, str] | None = None, dry_run: bool = False,
        env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """One bounded pass. Never raises for a source; writes its state and report and returns the
    report. `dry_run` donates nothing. `get` is injectable for tests; without it the UA must be
    configured."""
    started = time.monotonic()
    now = now or datetime.now(tz=UTC)
    e = os.environ if env is None else env
    sd = state_dir or STATE_DIR
    series = series_root or bb.SERIES_DIR
    state_path = sd / "state.json"
    state: dict[str, Any] = fl.read_json(state_path, {})
    names = names if names is not None else fl.issuers()
    ua = str(e.get(fl.UA_ENV, "")).strip()
    held = fl.active_hold(state)
    client: fl.EdgarClient | None = None
    if held is not None:
        fetch = {"status": "HELD", "requests": 0, "hold": held,
                 "why": (f"{held.get('verdict')} HTTP {held.get('status')} from "
                         f"{held.get('host')}: held until a person sets released_by")}
    elif budget_s <= 1:
        fetch = {"status": "NOT_REACHED", "why": "the host leg's budget ran out first"}
    elif get is None and not ua:
        fetch = {"status": "UNCONFIGURED",
                 "why": f"no {fl.UA_ENV}: the SEC's fair-access policy requires a declared "
                        "User-Agent, so nothing was fetched"}
    elif get is None and not fl.ua_has_contact(ua):
        fetch = {"status": "UNCONFIGURED",
                 "why": f"{fl.UA_ENV} names no contact (an email or a URL): nothing fetched"}
    else:
        fetch = {"status": "RUNNING"}
        client = fl.EdgarClient(get or fl.urllib_getter(ua), state, now=now,
                                deadline=started + budget_s * FORM4_SHARE, ua=ua)
    report: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                              "source": SOURCE, "issuers": len(names),
                              "user_agent_configured": bool(ua) or get is not None}
    sd.mkdir(parents=True, exist_ok=True)
    try:
        f4 = fl.run(client, state, names=names, state_dir=sd, now=now)
    except Exception as exc:                       # one reader never takes the others down
        f4 = {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"[:300], "_cells": []}
    if client is not None:
        client.deadline = started + budget_s      # the rest of the pass is the buyback reader's
    try:
        buyback = bb.run(client, state, names=names, state_dir=sd, now=now,
                         series_root=series)
    except Exception as exc:
        buyback = {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"[:300]}
    if client is not None:
        fetch = {**client.report(),
                 "status": ("HELD" if client.hold else "FETCHED" if client.ok else
                            "ROBOTS_UNAVAILABLE" if client.robots_unavailable else
                            "FAILED" if client.requests else "IDLE")}
        if client.hold is not None:
            state["hold"] = client.hold
    switch = congress_attested(e)
    congress: dict[str, Any] = {"switch": CONGRESS_ENV, "switch_read": switch,
                                "consumes": f"data/lake/series/{CONGRESS_SERIES}.*",
                                "collector": "libs/data/free_stack.fetch_congress"}
    c_cells: list[dict[str, Any]] = []
    if switch["on"]:
        evs = congress_events(series, names)
        tmp = sd / f"{CONGRESS_EVENTS}.tmp{os.getpid()}"
        tmp.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in evs), "utf-8")
        os.replace(tmp, sd / CONGRESS_EVENTS)
        c_cells = congress_cells(evs)
        congress.update({"status": "READ", "events": len(evs), "cells": len(c_cells)})
    else:
        # THE HELD READING: nothing is read, and earlier output is ignored (the family refuses
        # it too). The growth given up is UNMEASURED, never zero.
        congress.update({"status": "AWAITING_PRINCIPAL", "reading": fl.UNMEASURED,
                         "events": 0, "cells": 0,
                         "legal_basis": ("5 U.S.C. 13107(c): congressional periodic transaction "
                                         "reports may not be used for a commercial purpose")})
    cells = list(f4.pop("_cells", []) or []) + c_cells
    donated = donate_new(cells, state, dry_run=dry_run)
    fl.write_json(state_path, state)
    report.update({
        "fetch": fetch, "form4": f4, "congress": congress, "buyback_blackout": buyback,
        "cells": {"candidates": len(cells), "donated": donated,
                  "families": sorted({c["family"] for c in cells})},
        "elapsed_s": round(time.monotonic() - started, 2),
        "new_data": "MEASURED" if fetch.get("status") == "FETCHED" else fl.UNMEASURED,
        "status": "OK" if fetch.get("status") == "FETCHED" else fl.UNMEASURED})
    fl.write_json(report_path or REPORT, report)
    return report


def summary_line(rep: Mapping[str, Any]) -> str:
    f4 = rep.get("form4") or {}
    bbr = (rep.get("buyback_blackout") or {}).get("series") or {}
    return (f"  event_lane {rep.get('status')}: fetch {(rep.get('fetch') or {}).get('status')}, "
            f"clusters {f4.get('clusters', 0)}, congress "
            f"{(rep.get('congress') or {}).get('status')}, blackout points {bbr.get('points', 0)}"
            f", cells {(rep.get('cells') or {}).get('candidates', 0)}")
