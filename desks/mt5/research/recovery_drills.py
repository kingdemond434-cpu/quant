#!/usr/bin/env python3
"""ONE SCORECARD FOR EVERY FAILURE AND RECOVERY DRILL THE DESK RUNS -- what passed, what failed,
what has never been measured, and the open gap behind each failure.

    python desks/mt5/research/recovery_drills.py           # hourly leg `recovery_drills`
    python desks/mt5/research/recovery_drills.py --json

WHY (principal 2026-10-06, recovery drills). The drills existed and were scattered: the gateway
under a faulty MT5 double and a SIGKILLed journal writer inside tier_s's CHAOS organ, the order
door's chaos lab in CI, the off-box restore and journal replay inside OPS_REDUNDANCY, the reboot
drill, the off-site backup, the PIT canaries, the replay parity audit. No artifact said which of
the institution's failure modes had a drill, whether it passed on the box, or which had none.
A failure mode with no drill reads the same as one that passes until the day it happens.

WHAT IT IS NOT. It runs no drill and duplicates none: every row reads the artifact the owning
organ already writes, on that organ's own clock, and grades it. A row whose artifact is absent or
older than its organ's cadence allows is UNMEASURED -- never PASS (L1.28a). A row whose evidence
is a CI test only says so (CI_ONLY): a test that passes in CI is not a drill run on the box. A
known code gap is FAIL with the gap and where its fix lives.

Writes desks/mt5/reports/RECOVERY_DRILLS.json, read by the Institutional acceptance package.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "RECOVERY_DRILLS.json"

CHAOS = REPORTS / "tier_s" / "CHAOS.json"
OPS = REPORTS / "OPS_REDUNDANCY.json"
OFFSITE = REPORTS / "OFFSITE_BACKUP.json"
REBOOT = REPORTS / "REBOOT_DRILL.json"
DESK_STALE = REPORTS / "DESK_STALE.json"
PIT = REPORTS / "PIT_CENSUS.json"
FORECAST = REPORTS / "FORECAST_CONTRACT.json"
REPLAY = REPORTS / "STATE_REPLAY_PARITY.json"
RELEASE = DATA / "release_identity.json"
ACCOUNT = DATA / "account_state.json"
STALL = (DATA / "stall_watch.json", ROOT / "data" / "stall_watch.json")

#: The fix for the gateway rows, sent to the desktop pass (money path; the cloud edit is refused).
GATEWAY_SPEC = "docs/desktop_pass/recovery_drills/gateway_new_risk_gate.md"
FILL_ORDER_SPEC = "docs/desktop_pass/recovery_drills/gateway_partial_fill_and_ordering.md"
#: Fields an authoritative account ledger needs; the publisher writes a subset.
ACCOUNT_FIELDS = ("balance", "equity", "margin", "margin_free", "swap", "positions")
DISK_FLOOR_GB = 5.0

PASS, FAIL, UNMEASURED, CI_ONLY = "PASS", "FAIL", "UNMEASURED", "CI_ONLY"


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _age_h(p: Path, doc: Any, now: datetime) -> float | None:
    """Age of an artifact: its own stamp when it carries one, else the file's mtime."""
    stamp = None
    if isinstance(doc, dict):
        for k in ("generated_utc", "generated_at", "at", "checked_at", "measured_at", "ts"):
            stamp = _ts(doc.get(k)) if doc.get(k) else None
            if stamp:
                break
    if stamp is None:
        try:
            stamp = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        except OSError:
            return None
    return round((now - stamp).total_seconds() / 3600.0, 2)


def _artifact(p: Path, max_age_h: float, now: datetime) -> tuple[Any, dict[str, Any] | None]:
    """The artifact, or the UNMEASURED row explaining why it cannot be graded."""
    doc = _read(p)
    rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    if doc is None:
        return None, {"verdict": UNMEASURED, "evidence": rel,
                      "why": "artifact absent on this host: its organ has not run here"}
    age = _age_h(p, doc, now)
    if age is None or age > max_age_h:
        return None, {"verdict": UNMEASURED, "evidence": rel, "age_h": age,
                      "why": f"artifact older than {max_age_h}h: its organ has stopped"}
    return doc, None


def _row(verdict: str, evidence: str, why: str, **kw: Any) -> dict[str, Any]:
    return {"verdict": verdict, "evidence": evidence, "why": why, **kw}


# --------------------------------------------------------------------- gateway (tier_s CHAOS)
def _gateway(faults: tuple[str, ...], now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(CHAOS, 3.0, now)
    if miss:
        return miss
    gw = (doc or {}).get("gateway_drill") or {}
    rows = {r.get("fault"): r for r in gw.get("faults") or [] if isinstance(r, dict)}
    seen = [f for f in faults if (rows.get(f) or {}).get("status") == "MEASURED"]
    breaches = [f"{f}: {b}" for f in seen for b in rows[f].get("breaches") or []]
    ev = "reports/tier_s/CHAOS.json gateway_drill"
    if breaches:
        return _row(FAIL, ev, "; ".join(breaches)[:600], faults=list(faults),
                    fix=GATEWAY_SPEC if any("RECONCILE_BEFORE" in b for b in breaches) else None)
    if len(seen) < len(faults):
        missing = [f for f in faults if f not in seen]
        return _row(UNMEASURED, ev, f"fault(s) not measured on this run: {missing}",
                    faults=list(faults))
    return _row(PASS, ev, f"real gateway.py under {', '.join(faults)}: no breach",
                faults=list(faults))


def _process_kill(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(CHAOS, 3.0, now)
    if miss:
        return miss
    k = (doc or {}).get("process_kill") or {}
    st = str(k.get("status") or "").upper()
    v = PASS if st in ("PASS", "OK", "MEASURED") and not k.get("breaches") else (
        FAIL if st == "FAIL" or k.get("breaches") else UNMEASURED)
    return _row(v, "reports/tier_s/CHAOS.json process_kill",
                f"journal writer SIGKILLed and restarted: {st or 'no status'}"
                + (f", kills={k.get('kills')}" if k.get("kills") is not None else ""))


# ----------------------------------------------------------------------- box artifacts
def _ops_component(name: str, now: datetime, label: str) -> dict[str, Any]:
    doc, miss = _artifact(OPS, 3.0, now)
    if miss:
        return miss
    st = str(((doc or {}).get("components") or {}).get(name) or "")
    part = (doc or {}).get(name) or {}
    why = part.get("why") if isinstance(part, dict) else None
    v = PASS if st == "PASS" else FAIL if st == "FAIL" else UNMEASURED
    return _row(v, f"reports/OPS_REDUNDANCY.json {name}", f"{label}: {st or 'absent'}"
                + (f" ({why})" if why else ""))


def _backup(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(OFFSITE, 14.0, now)
    if miss:
        return miss
    sys.path.insert(0, str(DESK / "scripts"))
    try:
        import offsite_backup as ob  # type: ignore[import-not-found,unused-ignore]
        st, why = ob.verdict(doc or {}, now)
    except Exception as exc:
        return _row(UNMEASURED, "reports/OFFSITE_BACKUP.json",
                    f"offsite_backup unreadable: {type(exc).__name__}")
    v = PASS if st == "PASS" else UNMEASURED if st in ("NOT_ARMED", "NO_RESTIC") else FAIL
    return _row(v, "reports/OFFSITE_BACKUP.json restore_drill", f"{st}: {why}",
                needs_principal=st in ("NOT_ARMED", "NO_RESTIC", "KEY_NOT_ESCROWED"))


def _reboot(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(REBOOT, 50.0, now)
    if miss:
        return miss
    st = str((doc or {}).get("verdict") or (doc or {}).get("status") or "").upper()
    return _row(PASS if st == "PASS" else FAIL if st == "FAIL" else UNMEASURED,
                "reports/REBOOT_DRILL.json", f"daily reboot drill: {st or 'no verdict'}")


def _stale(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(DESK_STALE, 2.0, now)
    if miss:
        return miss
    measured = (doc or {}).get("status") == "MEASURED"
    return _row(PASS if measured else UNMEASURED, "reports/DESK_STALE.json",
                f"research-silence detector graded this pass: {(doc or {}).get('verdict')}",
                gap="feed freshness is gated on the XAUUSD tick alone (30 min); there is no "
                    "per-symbol stale-quote gate before a placement")


def _pit(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(PIT, 3.0, now)
    if miss:
        return miss
    c = (doc or {}).get("canaries") or {}
    green = c.get("green")
    return _row(PASS if green is True else FAIL if green is False else UNMEASURED,
                "reports/PIT_CENSUS.json canaries",
                f"a planted future row {'stayed invisible' if green else 'was not refused'} in "
                f"the stamping library and the lake's consumers" if green is not None else
                f"half the canary is unmeasured: {c.get('why')}")


def _forecast(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(FORECAST, 3.0, now)
    if miss:
        return miss
    n = int((doc or {}).get("beliefs") or 0)
    if not n:
        return _row(FAIL, "reports/FORECAST_CONTRACT.json",
                    "the contract refuses malformed beliefs, but no production model publishes "
                    "through it: malformed forecasts on the money path are not checked by it",
                    gap="UNWIRED forecast contract")
    return _row(PASS, "reports/FORECAST_CONTRACT.json",
                f"{n} belief(s) through the contract; defects refused")


def _deploy(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(RELEASE, 3.0, now)
    if miss:
        return miss
    v = str((doc or {}).get("verdict") or "")
    ok = bool((doc or {}).get("allows_new_risk"))
    return _row(PASS if ok else FAIL if v else UNMEASURED, "data/release_identity.json",
                "running code is the sealed release" if ok else
                f"release identity {v or 'unmeasured'}: new risk refused",
                gap="a failed smoke test gates nothing and rollback is manual "
                    "(libs/tiers/rollback.py); the safe state is the identity refusal")


def _account(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(ACCOUNT, 1.0, now)
    if miss:
        return miss
    have = set(doc or {}) | set((doc or {}).get("account") or {})
    lacking = [f for f in ACCOUNT_FIELDS if f not in have]
    if lacking:
        return _row(FAIL, "data/account_state.json",
                    f"account snapshot lacks {lacking}: positions, used margin and financing "
                    "are not in one authoritative ledger")
    return _row(PASS, "data/account_state.json", "balance, equity, margin, swap and positions")


def _resources(now: datetime) -> dict[str, Any]:
    p = next((x for x in STALL if x.exists()), STALL[0])
    doc, miss = _artifact(p, 1.0, now)
    if miss:
        return miss
    free = (doc or {}).get("free_gb")
    try:
        disk_ok = float(str(free)) >= DISK_FLOOR_GB
    except (TypeError, ValueError):
        return _row(UNMEASURED, "data/stall_watch.json", "no free_gb reading")
    return _row(PASS if disk_ok else FAIL, "data/stall_watch.json",
                f"disk {free} GB free (floor {DISK_FLOOR_GB}); stall watch heals stacked "
                "research and never touches the money path",
                gap="research yields cores, but nothing at the OS level reserves CPU or memory "
                    "for the gateway ahead of research")


def _replay(now: datetime) -> dict[str, Any]:
    doc, miss = _artifact(REPLAY, 3.0, now)
    if miss:
        return miss
    st = str((doc or {}).get("verdict") or (doc or {}).get("status") or "").upper()
    return _row(PASS if st in ("PASS", "PARITY", "OK") else FAIL if st == "FAIL" else UNMEASURED,
                "reports/STATE_REPLAY_PARITY.json", f"decision state replay: {st or 'none'}",
                gap="decision rows hash the strategy identity, not the input data: a decision "
                    "cannot yet be recomputed from frozen inputs")


def _ci(test: str, why: str) -> Callable[[datetime], dict[str, Any]]:
    def f(now: datetime) -> dict[str, Any]:
        exists = (ROOT / test).exists()
        return _row(CI_ONLY if exists else UNMEASURED, test,
                    why if exists else f"{test} is absent")
    return f


def _gap(why: str, fix: str) -> Callable[[datetime], dict[str, Any]]:
    return lambda now: _row(FAIL, "code", why, gap=why, fix=fix)


#: (drill id, the failure mode in the principal's words, grader)
DRILLS: tuple[tuple[str, str, Callable[[datetime], dict[str, Any]]], ...] = (
    ("broker_rejection", "broker rejection / requote",
     lambda n: _gateway(("reject_10015", "requote_10004"), n)),
    ("missing_ack", "missing acknowledgement (send returns nothing or raises)",
     lambda n: _gateway(("send_none", "send_raises"), n)),
    ("network_loss", "broker network loss / terminal disconnected",
     lambda n: _gateway(("terminal_down", "terminal_disconnected"), n)),
    ("restore_reconcile", "restart: reconcile broker state before any new exposure",
     lambda n: _gateway(("orders_get_raises", "reconcile_unreadable"), n)),
    ("no_quote", "model/feed failure: no quote for the symbol",
     lambda n: _gateway(("tick_none",), n)),
    ("worker_crash", "worker crash mid-write and restart", _process_kill),
    ("duplicate_delivery", "duplicate delivery / in-doubt resend",
     _ci("desks/mt5/tests/test_order_door_chaos.py",
         "the order door refuses an identical in-doubt send the venue shows landed; tested "
         "in CI, not drilled on the box")),
    ("queue_overload", "queue overload / worker flood",
     _ci("desks/mt5/tests/test_control_plane_chaos.py",
         "control-plane chaos (queue flood, frozen PID, killed worker) is tested in CI")),
    ("partial_fill", "partial fill",
     _gap("the order door labels a partial fill but nothing acts on the unfilled remainder "
          "(no resize of the stop leg, no record of the residual)",
          FILL_ORDER_SPEC)),
    ("out_of_order", "out-of-order updates",
     _gap("no sequencing of broker updates anywhere in mt5desk/: a stale positions read after "
          "a newer deal is taken at face value",
          FILL_ORDER_SPEC)),
    ("stale_data", "stale data / stale source", _stale),
    ("revision_leakage", "revision leakage (point in time)", _pit),
    ("malformed_forecast", "malformed forecast", _forecast),
    ("disk_pressure", "disk pressure / reserved resources", _resources),
    ("failed_deployment", "failed deployment and rollback", _deploy),
    ("backup_restore", "backup restoration (restore and test, not a script)", _backup),
    ("offbox_restore", "off-box restore of the journals",
     lambda n: _ops_component("offbox_restore_drill", n, "journals restored from origin")),
    ("journal_replay", "journal replay rebuilds the open book",
     lambda n: _ops_component("journal_replay", n, "journal replay")),
    ("duplicate_positions", "two order authorities / duplicate positions",
     lambda n: _ops_component("duplicate_guard", n, "duplicate-position guard")),
    ("clock_sync", "clock sync", lambda n: _ops_component("clock_sync", n, "box clock")),
    ("terminal_health", "terminal connected and trading allowed",
     lambda n: _ops_component("terminal_health", n, "terminal")),
    ("reboot", "box reboot and recovery", _reboot),
    ("account_ledger", "authoritative positions, cash, margin, financing", _account),
    ("reproducibility", "reproduce a decision from its inputs", _replay),
    ("secrets", "secrets never published",
     _ci("tests/ops/test_live_infrastructure_is_not_published.py",
         "the live-identifier scan runs in CI only; no scheduled leak scan")),
)


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = []
    for did, mode, grade in DRILLS:
        try:
            r = grade(now)
        except Exception as exc:          # a grader that breaks is an unmeasured drill
            r = _row(UNMEASURED, "grader", f"{type(exc).__name__}: {exc}"[:200])
        rows.append({"drill": did, "failure_mode": mode, **r})
    counts = {k: sum(1 for r in rows if r["verdict"] == k)
              for k in (PASS, FAIL, UNMEASURED, CI_ONLY)}
    return {"generated_utc": now.isoformat(timespec="seconds"), "drills": rows,
            "counts": counts, "n": len(rows),
            "verdict": FAIL if counts[FAIL] else PASS if counts[PASS] == len(rows) else
            UNMEASURED,
            "rule": "PASS only on a fresh box artifact that passed; absent or stale is "
                    "UNMEASURED; CI_ONLY is a test, not a drill run on the box; a known code "
                    "gap is FAIL with its fix named",
            "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"recovery_drills: {doc['verdict']} {doc['counts']}")
        for r in doc["drills"]:
            print(f"  {r['verdict']:<10} {r['drill']:<20} {r['why'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
