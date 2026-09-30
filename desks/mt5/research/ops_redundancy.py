#!/usr/bin/env python3
"""OPERATIONAL REDUNDANCY ON ONE VENUE, MEASURED EVERY HOUR (Tier-1 audit item #19, 2026-09-29).

THE PRINCIPAL: "warm standby, independent market-data verification, replayable event journal,
encrypted off-box backups, tested restore, terminal-health monitoring, automatic failover that
cannot duplicate positions, DR drills." Multi-venue / a second broker is OUT OF SCOPE.

WHAT ALREADY EXISTED, and is read here rather than rebuilt:
  * the journal -- data/order_intents.jsonl, decision_ledger.jsonl, live_ledger.jsonl, written by
    the gateway, and carried OFF THE BOX to origin by `sync_shadow_to_git.ps1` every 15 minutes
    (git is the off-box replica: a second machine, a different failure domain);
  * `scripts/run_moat_backup.py` + `scripts/run_restore_drill.py` -- the VPS's moat backup and a
    weekly restore drill of the forward stores (VPS timers quant-moat-backup / -restore-drill);
  * `ops/reboot_drill.ps1` -- MT5-RebootDrill, daily, writes reports/REBOOT_DRILL.json;
  * `desks/mt5/scripts/stall_watch.ps1` -- data/stall_watch.json;
  * the failover pair MT5-Gateway (per minute) + MT5-GatewayResident (AtLogOn), which cannot
    double-trade because `research/run_gateway_loop.py` holds a PID-aware lock
    (data/gateway.lock), and the gateway refuses a second open on the same bar.

WHAT NOTHING DID, and this organ now does on the hourly clock:
  1. JOURNAL REPLAY -- every journal line parses, ids are unique, and replaying intents against
     closing deals reconstructs the open book, which is compared to the gateway's own state;
  2. OFF-BOX RESTORE DRILL -- each box store is restored FROM THE OFF-BOX COPY (the origin
     branch's git object, never the local file) into a temp dir, parsed as its consumer would,
     and checked: an append-only journal's restored lines must be a PREFIX of the live file, and
     the lag in rows and hours is published. A restore that was never exercised is a hope;
  3. TERMINAL HEALTH -- connected / trade-allowed / ping / last-tick age from the terminal on the
     box, the gateway lock's owner, the last placement pass, and the reboot drill's verdict;
  4. INDEPENDENT MARKET-DATA CROSS-CHECK -- the venue's own daily closes on FX majors against an
     independent source (Yahoo daily), at most once per 20 hours, median relative gap per pair;
  5. DUPLICATE-POSITION GUARD, MEASURED -- accepted intents from one sleeve, same side, within
     the same minute at the same intended price, are counted from the journal: the failover
     pair's promise is that this stays zero.

WHAT IS NOT DONE AND SAYS SO (each a `gap` row, never a pass):
  * warm standby: a second terminal on a second machine is a provisioning decision;
  * encryption: the off-box replica is a private git remote, not encrypted by the desk; a key
    the desk holds must also be escrowed off-box to be restorable -- a custody decision.

    -> reports/OPS_REDUNDANCY.json      (hourly, leg `ops_redundancy`)
    python desks/mt5/research/ops_redundancy.py [--no-network]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
REPORTS = DESK / "reports"
OUT = REPORTS / "OPS_REDUNDANCY.json"
XCHECK_CACHE = DATA / "ops_redundancy_xcheck.json"
GATEWAY_STATE = DATA / "gateway_state.json"
GATEWAY_LOCK = DATA / "gateway.lock"
REBOOT_DRILL = REPORTS / "REBOOT_DRILL.json"
STALL_WATCH = (DATA / "stall_watch.json", ROOT / "data" / "stall_watch.json")

#: The box's irreplaceable stores that ride the off-box replica, with how each is read back.
#: "jsonl" stores are append-only journals and must restore as a PREFIX of the live file.
BOX_STORES: dict[str, str] = {
    "desks/mt5/data/order_intents.jsonl": "jsonl",
    "desks/mt5/data/decision_ledger.jsonl": "jsonl",
    "desks/mt5/data/live_ledger.jsonl": "jsonl",
    "desks/mt5/data/fill_corpus.jsonl": "jsonl",
    "desks/mt5/data/sleeves.json": "json",
    "desks/mt5/data/sleeve_registry.json": "json",
    "desks/mt5/data/gateway_state.json": "json",
    "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json": "json",
    "desks/mt5/data/GOLD_RETIRED.json": "json",
    "desks/mt5/reports/shadow/shadow_state.json": "json",
}
#: An off-box copy older than this is STALE (the sync runs every 15 minutes).
OFFBOX_STALE_H = 6.0
#: Pairs checked against the independent feed, and the tolerated median relative gap. Daily
#: closes from two sources differ by their close times (the venue's 00:00 server vs Yahoo's
#: London-evening snapshot), so the bar is a gap that no timing difference explains on majors.
XCHECK_PAIRS: dict[str, str] = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
                                "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
                                "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X"}
XCHECK_TOL = 0.006
XCHECK_TTL_H = 20.0
TICK_STALE_S = 300.0
DONE_RETCODES = {10008, 10009, 10010}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _parse_ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _lines(text: str) -> tuple[list[dict[str, Any]], int]:
    rows, bad = [], 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            bad += 1
            continue
        if isinstance(d, dict):
            rows.append(d)
        else:
            bad += 1
    return rows, bad


# ------------------------------------------------------------------------ 1. journal replay
def journal_replay(data: Path = DATA) -> dict[str, Any]:
    """Parse, de-duplicate and replay the execution journal; compare to the gateway's state."""
    out: dict[str, Any] = {}
    stores = {}
    for name in ("order_intents", "decision_ledger", "live_ledger"):
        p = data / f"{name}.jsonl"
        try:
            rows, bad = _lines(p.read_text("utf-8", errors="replace"))
        except OSError:
            stores[name] = {"status": "ABSENT", "path": str(p.name)}
            continue
        times = [t for t in (_parse_ts(r.get("time") or r.get("at") or r.get("ts"))
                             for r in rows) if t]
        back = sum(1 for a, b in zip(times, times[1:], strict=False) if b < a)
        stores[name] = {"status": "PARSED", "rows": len(rows), "unparseable": bad,
                        "time_reversals": back, "_rows": rows}
    intents = stores.get("order_intents", {}).get("_rows") or []
    deals = stores.get("live_ledger", {}).get("_rows") or []
    ids = [str(r.get("intent_id")) for r in intents if r.get("intent_id")]
    deal_ids = [str(r.get("deal")) for r in deals if r.get("deal") is not None]
    dup_intents = len(ids) - len(set(ids))
    dup_deals = len(deal_ids) - len(set(deal_ids))
    accepted = [r for r in intents if int(r.get("retcode") or 0) in DONE_RETCODES]
    closed_positions = {str(r.get("position_id")) for r in deals if r.get("position_id")}
    closed_orders = {str(r.get("entry_order")) for r in deals if r.get("entry_order")}
    open_by_journal = sorted(str(r.get("ticket")) for r in accepted
                             if r.get("ticket") and str(r.get("ticket")) not in closed_positions
                             and str(r.get("ticket")) not in closed_orders)
    gs = _read(data / "gateway_state.json")
    gw_open = None
    if isinstance(gs, dict) and isinstance(gs.get("position"), list):
        gw_open = len(gs["position"])
    for s in stores.values():
        s.pop("_rows", None)
    parse_ok = all(s.get("unparseable", 0) == 0 for s in stores.values()
                   if s.get("status") == "PARSED")
    present = [k for k, s in stores.items() if s.get("status") == "PARSED"]
    out.update({
        "stores": stores,
        "intents": len(intents), "accepted": len(accepted), "closing_deals": len(deals),
        "duplicate_intent_ids": dup_intents, "duplicate_deals": dup_deals,
        "open_by_replay": len(open_by_journal), "open_tickets_by_replay": open_by_journal[:50],
        "open_by_gateway_state": gw_open,
        "status": ("UNMEASURED" if "order_intents" not in present or
                   "live_ledger" not in present else
                   "PASS" if parse_ok and dup_intents == 0 and dup_deals == 0 else "FAIL"),
        "note": ("open_by_replay counts accepted intents with no closing deal: a pending order "
                 "that never filled also counts, so it is an UPPER bound compared to the "
                 "gateway's own position list, not an equality"),
    })
    return out


# ---------------------------------------------------------------- 2. off-box restore drill
def _git(*args: str, cwd: Path = ROOT, text: bool = True) -> tuple[int, Any]:
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=text,
                           timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return p.returncode, p.stdout


def offbox_ref(cwd: Path = ROOT) -> tuple[str | None, str]:
    rc, out = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", cwd=cwd)
    if rc == 0 and str(out).strip():
        return str(out).strip(), "the branch's upstream"
    rc, br = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    br = str(br).strip()
    if rc == 0 and br and br != "HEAD":
        ref = f"origin/{br}"
        rc2, _ = _git("rev-parse", "--verify", "--quiet", ref, cwd=cwd)
        if rc2 == 0:
            return ref, "origin copy of the checked-out branch"
    return None, "no remote-tracking ref for the checked-out branch"


def restore_drill(stores: dict[str, str] | None = None, cwd: Path = ROOT) -> dict[str, Any]:
    """Restore each store FROM THE OFF-BOX COPY into a temp dir and verify it."""
    stores = stores if stores is not None else BOX_STORES
    ref, why = offbox_ref(cwd)
    if ref is None:
        return {"status": "UNMEASURED", "why": why}
    rc, ts = _git("log", "-1", "--format=%cI", ref, cwd=cwd)
    ref_time = _parse_ts(str(ts).strip()) if rc == 0 else None
    age_h = ((datetime.now(tz=UTC) - ref_time).total_seconds() / 3600.0) if ref_time else None
    rows: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="dr_drill_") as tmp:
        for rel, kind in stores.items():
            live_p = cwd / rel
            rc, blob = _git("show", f"{ref}:{rel}", cwd=cwd, text=False)
            if rc != 0:
                rows[rel] = {"status": "NOT_OFF_BOX",
                             "why": f"{rel} is not in {ref}: a loss of this box loses it"}
                continue
            dst = Path(tmp) / rel.replace("/", "_")
            dst.write_bytes(blob)
            restored = dst.read_text("utf-8", errors="replace")
            try:
                live = live_p.read_text("utf-8", errors="replace")
            except OSError:
                live = None
            if kind == "jsonl":
                r_rows, r_bad = _lines(restored)
                l_rows = _lines(live)[0] if live is not None else []
                r_lines = [ln for ln in restored.splitlines() if ln.strip()]
                l_lines = [ln for ln in (live or "").splitlines() if ln.strip()]
                prefix = l_lines[:len(r_lines)] == r_lines
                rows[rel] = {"status": ("PASS" if r_bad == 0 and prefix else "FAIL"),
                             "restored_rows": len(r_rows), "live_rows": len(l_rows),
                             "lag_rows": max(0, len(l_rows) - len(r_rows)),
                             "prefix_of_live": prefix, "unparseable": r_bad}
            else:
                try:
                    json.loads(restored)
                    ok = True
                except ValueError:
                    ok = False
                rows[rel] = {"status": "PASS" if ok else "FAIL", "parses": ok,
                             "identical_to_live": (live is not None
                                                   and live.strip() == restored.strip())}
    fails = sorted(k for k, v in rows.items() if v["status"] == "FAIL")
    missing = sorted(k for k, v in rows.items() if v["status"] == "NOT_OFF_BOX")
    stale = age_h is not None and age_h > OFFBOX_STALE_H
    return {"status": "FAIL" if fails else ("DEGRADED" if missing or stale else "PASS"),
            "ref": ref, "ref_why": why,
            "ref_commit_utc": ref_time.isoformat() if ref_time else None,
            "offbox_age_h": round(age_h, 2) if age_h is not None else None,
            "offbox_stale": stale, "failed": fails, "not_off_box": missing, "stores": rows,
            "rule": ("restored from the OFF-BOX copy (the origin ref's git object), never from "
                     "the local file; a journal must restore as a prefix of the live file")}


# -------------------------------------------------------------------- 3. terminal health
def terminal_health() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        import MetaTrader5 as mt5  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        out["terminal"] = {"status": "UNMEASURED",
                           "why": "MetaTrader5 is not importable on this host (not the box)"}
    else:
        opened = False
        try:
            if mt5.terminal_info() is None:
                try:
                    from mt5desk.config import terminal_path
                    path = terminal_path()
                except Exception:
                    path = ""
                opened = bool(mt5.initialize(path=path) if path else mt5.initialize())
            ti = mt5.terminal_info()
            if ti is None:
                out["terminal"] = {"status": "FAIL", "why": f"unreachable ({mt5.last_error()})"}
            else:
                tick = mt5.symbol_info_tick("XAUUSD")
                tick_age = (time.time() - float(tick.time)) if tick is not None else None
                ok = bool(ti.connected) and bool(ti.trade_allowed)
                out["terminal"] = {
                    "status": "PASS" if ok else "FAIL",
                    "connected": bool(ti.connected), "trade_allowed": bool(ti.trade_allowed),
                    "ping_ms": round(float(getattr(ti, "ping_last", 0)) / 1000.0, 2),
                    "xauusd_tick_age_s": round(tick_age, 1) if tick_age is not None else None,
                    "why": ("connected and algo trading allowed" if ok else
                            "terminal disconnected or AutoTrading off")}
        except Exception as exc:
            out["terminal"] = {"status": "FAIL", "why": f"{type(exc).__name__}: {exc}"}
        finally:
            if opened:
                try:
                    mt5.shutdown()
                except Exception:
                    pass
    gs = _read(GATEWAY_STATE)
    last_pass = _parse_ts(gs.get("placement_pass")) if isinstance(gs, dict) else None
    out["gateway_last_pass"] = {
        "at": last_pass.isoformat() if last_pass else None,
        "age_min": (round((datetime.now(tz=UTC) - last_pass).total_seconds() / 60.0, 1)
                    if last_pass else None)}
    lock: dict[str, Any] = {"present": GATEWAY_LOCK.exists()}
    if GATEWAY_LOCK.exists():
        try:
            pid = int(GATEWAY_LOCK.read_text("utf-8").strip() or 0)
        except (OSError, ValueError):
            pid = 0
        lock["pid"] = pid or None
        try:
            import psutil
            lock["owner_alive"] = bool(pid) and psutil.pid_exists(pid)
        except ImportError:
            lock["owner_alive"] = None
    out["gateway_lock"] = lock
    rd = _read(REBOOT_DRILL)
    out["reboot_drill"] = ({"verdict": rd.get("verdict") or rd.get("status"),
                            "at": rd.get("at") or rd.get("generated_utc")}
                           if isinstance(rd, dict) else
                           {"verdict": "UNMEASURED", "why": "no REBOOT_DRILL.json on this host"})
    sw = next((p for p in STALL_WATCH if p.exists()), None)
    out["stall_watch"] = ({"path": str(sw.relative_to(ROOT)),
                           "age_min": round((time.time() - sw.stat().st_mtime) / 60.0, 1)}
                          if sw else {"status": "UNMEASURED", "why": "no stall_watch.json"})
    term = out["terminal"].get("status")
    out["status"] = term if term in ("PASS", "FAIL") else "UNMEASURED"
    return out


# ------------------------------------------------------- 4. independent market-data check
def _venue_closes(symbol: str) -> dict[str, float]:
    try:
        from exposure_decomposition import load_bars
        ser = load_bars(symbol)
    except Exception:
        return {}
    if ser is None:
        return {}
    return {str(ix)[:10]: float(v) for ix, v in ser.tail(30).items()}


#: The second independent source, used when the first is unreachable: the Federal Reserve's
#: H.10 noon buying rates (FRED), same orientation as the venue symbol.
FRED_PAIRS: dict[str, str] = {"EURUSD": "DEXUSEU", "GBPUSD": "DEXUSUK", "USDJPY": "DEXJPUS",
                              "AUDUSD": "DEXUSAL", "USDCAD": "DEXCAUS", "USDCHF": "DEXSZUS"}


def _independent_closes(symbol: str) -> tuple[dict[str, float], str]:
    """(closes, source): Yahoo daily first, the Fed's H.10 rates when Yahoo is unreachable."""
    try:
        from free_data import fred_series, yahoo_daily
    except Exception:
        return {}, "none"
    tk = XCHECK_PAIRS.get(symbol)
    try:
        d = (yahoo_daily(tk) or {}) if tk else {}
    except Exception:
        d = {}
    if d:
        return {str(k)[:10]: float(v) for k, v in d.items()
                if isinstance(v, (int, float))}, "yahoo"
    sid = FRED_PAIRS.get(symbol)
    try:
        f = (fred_series(sid, start="2026-01-01") or {}) if sid else {}
    except Exception:
        f = {}
    return ({str(k)[:10]: float(v) for k, v in f.items() if isinstance(v, (int, float))},
            f"fred:{sid}" if f else "none")


def market_data_crosscheck(network: bool = True, venue: Any = None,
                           independent: Any = None) -> dict[str, Any]:
    cached = _read(XCHECK_CACHE)
    if isinstance(cached, dict):
        at = _parse_ts(cached.get("at"))
        if at and (datetime.now(tz=UTC) - at).total_seconds() < XCHECK_TTL_H * 3600:
            return {**cached, "cached": True}
    if not network:
        return {"status": "UNMEASURED", "why": "network disabled for this pass"}
    venue = venue or _venue_closes
    independent = independent or _independent_closes
    pairs: dict[str, Any] = {}
    for sym in XCHECK_PAIRS:
        a, (b, src) = venue(sym), independent(sym)
        common = sorted(set(a) & set(b))[-10:]
        if len(common) < 3:
            pairs[sym] = {"status": "UNMEASURED", "n_common_days": len(common),
                          "why": ("no venue bars on this host" if not a else
                                  "independent source unreachable" if not b else
                                  "fewer than 3 common days")}
            continue
        gaps = sorted(abs(a[d] - b[d]) / b[d] for d in common if b[d])
        med = gaps[len(gaps) // 2]
        pairs[sym] = {"status": "PASS" if med <= XCHECK_TOL else "FAIL", "source": src,
                      "n_common_days": len(common), "median_rel_gap": round(med, 6),
                      "max_rel_gap": round(max(gaps), 6)}
    measured = [v for v in pairs.values() if v["status"] != "UNMEASURED"]
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "status": ("UNMEASURED" if not measured else
                      "FAIL" if any(v["status"] == "FAIL" for v in measured) else "PASS"),
           "tolerance": XCHECK_TOL,
           "independent_source": "Yahoo Finance daily close, else FRED H.10 noon rates",
           "pairs": pairs}
    if measured:
        try:
            XCHECK_CACHE.parent.mkdir(parents=True, exist_ok=True)
            XCHECK_CACHE.write_text(json.dumps(doc, indent=1), "utf-8")
        except OSError:
            pass
    return doc


# ----------------------------------------------------------- 5. duplicate-position guard
def duplicate_guard(data: Path = DATA) -> dict[str, Any]:
    try:
        rows, _ = _lines((data / "order_intents.jsonl").read_text("utf-8", errors="replace"))
    except OSError:
        return {"status": "UNMEASURED", "why": "no order_intents.jsonl on this host"}
    groups: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for r in rows:
        if int(r.get("retcode") or 0) not in DONE_RETCODES or int(r.get("slice_depth") or 1) > 1:
            continue
        key = (str(r.get("sleeve")), str(r.get("side")), str(r.get("time") or "")[:16],
               str(r.get("intended")))
        groups[key].append(str(r.get("intent_id") or r.get("ticket")))
    dups = [{"sleeve": k[0], "side": k[1], "minute": k[2], "intended": k[3], "n": len(v)}
            for k, v in groups.items() if len(v) > 1]
    return {"status": "PASS" if not dups else "FAIL", "n_accepted_checked": sum(
                len(v) for v in groups.values()),
            "duplicates": dups[:20], "n_duplicates": len(dups),
            "guard": ("research/run_gateway_loop.py PID-aware lock (data/gateway.lock) shared by "
                      "MT5-Gateway and MT5-GatewayResident; the gateway refuses a second open on "
                      "the same bar"),
            "rule": "accepted intents, same sleeve + side + minute + intended price, counted"}


def build(network: bool = True) -> dict[str, Any]:
    t0 = time.time()
    journal = journal_replay()
    drill = restore_drill()
    term = terminal_health()
    xcheck = market_data_crosscheck(network=network)
    dup = duplicate_guard()
    parts = {"journal_replay": journal["status"], "offbox_restore_drill": drill["status"],
             "terminal_health": term["status"], "market_data_crosscheck": xcheck["status"],
             "duplicate_guard": dup["status"]}
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": ("FAIL" if "FAIL" in parts.values() else
                   "PASS" if all(v == "PASS" for v in parts.values()) else "PARTIAL"),
        "components": parts,
        "journal_replay": journal, "offbox_restore_drill": drill, "terminal_health": term,
        "market_data_crosscheck": xcheck, "duplicate_guard": dup,
        "gaps": [
            {"item": "warm_standby", "status": "NOT_PROVISIONED",
             "why": "a second terminal on a second machine is a provisioning decision "
                    "(NEEDS-PRINCIPAL); the failover pair above is same-box only"},
            {"item": "encrypted_offbox_backup", "status": "NOT_ENCRYPTED",
             "why": "the off-box replica is a private git remote; desk-side encryption needs a "
                    "key escrowed off the box to stay restorable (key custody: NEEDS-PRINCIPAL)"},
        ],
        "elapsed_s": round(time.time() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = build(network=not args.no_network)
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    print(f"ops_redundancy: {doc['status']} -- " +
          ", ".join(f"{k}={v}" for k, v in doc["components"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

