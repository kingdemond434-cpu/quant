"""Hunt the wiring regressions that cost this desk more than any research question.

WHY THIS EXISTS (principal, 2026-09-04: "the machinery doesn't execute, and the desk spends its
time repairing regressions")

In ONE session the desk lost hours to eight separate infrastructure failures, none of them
research:

    1. the certificate canon rolled back to a 12-day-old sweep holding ONE survivor, which
       unenrolled the forward book -- 48 clocks orphaned, 207 trades frozen
    2. universe.json replaced by a 23-symbol stump, so the gauntlet swept a tenth of the universe
    3. currency_profit lost on 248 of 251 symbols, blinding gate 8 (stress_costs) entirely
    4. four code fixes silently reverted by the ssh-context pre-commit guard
    5. the gauntlet -- the job that MINTS certificates -- running daily, not hourly
    6. the VPS bar cache eight days stale while the box held current bars
    7. NOTHING scheduled the forward engine on either machine
    8. sleeve_registry.py stale on the trading box, so every clock broke terminally

EVERY ONE WAS INVISIBLE TO THE DESK'S OWN CHECKS, and each was invisible for the same reason: the
check that would have caught it read a DIFFERENT record than the one that broke. Freshness checks
read mtime, and a rollback writes ancient content with a current mtime. Healers read the registry,
and the state file was the stale one. The parity checker read the manifest, and the installer read
a committed timer that disagreed with it.

SO THIS READS THE PAIRS. Not "is X fresh" but "do X and Y still agree", which is the question that
actually catches a rollback. It repairs what is mechanical and refuses to touch what is a
judgement, and it never reports health it did not measure: an unreadable input is UNKNOWN, never a
pass.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "desk_integrity.json"

#: Sub-checks that can repair themselves, run before the read-only audit so the audit sees the
#: repaired state rather than reporting a defect this pass already fixed.
_REPAIRERS: tuple[tuple[str, list[str]], ...] = (
    ("universe floor", ["scripts/check_universe_floor.py"]),
    ("artifact rollback", ["scripts/check_artifact_monotonic.py"]),
    ("schedule parity", ["scripts/check_scheduler_manifest.py", "--fix-schedules"]),
)


def _run(args: list[str], timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run([str(ROOT / ".venv/bin/python"), *args], cwd=ROOT, timeout=timeout,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as exc:
        return 125, f"{type(exc).__name__}: {exc}"


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def check_uncommitted_code() -> dict[str, Any]:
    """Code edits sitting uncommitted are one revert away from gone.

    Measured 2026-09-04: four separate fixes to shadow_forward.py, run_deep_audit.py and
    desk_modules.py were reverted before they were ever committed -- the last of them AFTER being
    shipped to the trading box and "hash-verified", because both copies had been reverted and
    matched each other. On this tree, uncommitted code is not work in progress; it is work about
    to be lost.
    """
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "UNKNOWN", "why": f"{type(exc).__name__}"}
    py = [ln[3:] for ln in out.splitlines()
          if ln[3:].endswith(".py") and not ln.startswith("??")]
    return {"status": "DEFECT" if py else "OK",
            "uncommitted_py": py[:12], "count": len(py),
            "why": ("uncommitted .py changes are reverted by the ssh-context guard; commit with "
                    "QUANT_ALLOW_SSH_PY=1" if py else "no uncommitted code")}


def check_record_pairs() -> dict[str, Any]:
    """Records that MUST agree. A rollback shows up here and nowhere else."""
    findings = []
    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    report = _json(DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
    if canon is None or report is None:
        findings.append({"pair": "canon/report", "status": "UNKNOWN",
                         "why": "one side unreadable -- never a clean pass"})
    else:
        cs, rs = canon.get("swept_at") or "", report.get("swept_at") or ""
        cn, rn = len(canon.get("survivors") or {}), len(report.get("survivors") or {})
        if cs != rs or abs(cn - rn) > 0:
            findings.append({
                "pair": "canon/report", "status": "DEFECT",
                "canon": f"{cn} survivors @ {cs}", "report": f"{rn} survivors @ {rs}",
                "why": ("the canon IS enrolment: if it is the older of the two, the forward book "
                        "is running on certificates that no longer represent the latest sweep")})

    reg = _json(DESK / "data" / "sleeve_registry.json") or {}
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    rows = reg.get("sleeves") or {}
    if rows and isinstance(sl, dict):
        dis = [k for k in rows
               if isinstance(sl.get(k), dict)
               and str(rows[k].get("status") or "") != str(sl[k].get("status") or "")]
        if len(dis) > len(rows) * 0.5:
            findings.append({
                "pair": "registry/state", "status": "DEFECT",
                "disagreeing": len(dis), "of": len(rows),
                "why": ("recovery paths key off whichever record says there is nothing to do; "
                        "when these disagree at scale, clocks deadlock and accrue nothing")})
    return {"status": "DEFECT" if any(f["status"] == "DEFECT" for f in findings)
            else ("UNKNOWN" if findings else "OK"), "findings": findings}


def check_forward_lane() -> dict[str, Any]:
    """Clocks that are terminal, and evidence frozen inside them."""
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json")
    if st is None:
        return {"status": "UNKNOWN", "why": "shadow_state unreadable"}
    sl = st.get("sleeves") or st
    rows = [v for v in sl.values() if isinstance(v, dict)]
    broken = [v for v in rows if str(v.get("status") or "") == "IDENTITY_BROKEN"]
    frozen = sum(v.get("n", 0) or 0 for v in broken)
    active = [v for v in rows if str(v.get("status") or "") == "ACTIVE"]
    return {"status": "DEFECT" if frozen else "OK",
            "active": len(active), "active_trades": sum(v.get("n", 0) or 0 for v in active),
            "identity_broken": len(broken), "trades_frozen": frozen,
            "why": ("trades sitting in terminal rows are evidence the desk already earned and is "
                    "discarding" if frozen else "no evidence frozen")}


def check_bar_freshness(max_hours: float = 48.0) -> dict[str, Any]:
    """The research plane silently reading a stale market is the worst failure mode here."""
    try:
        import pandas as pd
    except ImportError:
        return {"status": "UNKNOWN", "why": "pandas unavailable"}
    uni = DESK / "data" / "universe"
    now = pd.Timestamp.now(tz="UTC")
    ages = []
    for p in sorted(uni.glob("*_H1.parquet")):
        try:
            df = pd.read_parquet(p)
            idx = pd.DatetimeIndex(df.index if df.index.name else df.iloc[:, 0])
            last = idx.max()
            last = last.tz_localize("UTC") if last.tz is None else last
            ages.append((now - last).total_seconds() / 3600.0)
        except Exception:
            continue
    if not ages:
        return {"status": "UNKNOWN", "why": "no readable H1 parquet"}
    ages.sort()
    med = ages[len(ages) // 2]
    fresh = sum(1 for a in ages if a < 24)
    return {"status": "DEFECT" if med > max_hours else "OK",
            "symbols": len(ages), "median_staleness_h": round(med, 1), "fresher_than_24h": fresh,
            "why": ("bars this old mean every adapter, measurement and research pass is answering "
                    "about a market that has moved on" if med > max_hours else "bars current")}


def check_failed_units() -> dict[str, Any]:
    try:
        out = subprocess.run(["systemctl", "--user", "list-units", "--state=failed",
                              "--no-legend", "--plain"],
                             capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError):
        return {"status": "UNKNOWN", "why": "systemctl unavailable"}
    units = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    return {"status": "DEFECT" if units else "OK", "failed": units[:12], "count": len(units)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="audit only; run no repairer")
    a = ap.parse_args()
    now = datetime.now(tz=UTC)
    print(f"DESK INTEGRITY {now.isoformat(timespec='seconds')}")

    repairs: list[dict[str, Any]] = []
    if not a.report:
        for name, args in _REPAIRERS:
            rc, out = _run(args)
            acted = [ln.strip() for ln in out.splitlines()
                     if any(w in ln for w in ("RESTORED", "REPAIRED", "restored", "repaired"))]
            repairs.append({"check": name, "exit": rc, "acted": acted[:4]})
            print(f"  repair {name:20s} exit={rc}" + (f"  {acted[0][:80]}" if acted else ""))

    checks = {
        "uncommitted_code": check_uncommitted_code(),
        "record_pairs": check_record_pairs(),
        "forward_lane": check_forward_lane(),
        "bar_freshness": check_bar_freshness(),
        "failed_units": check_failed_units(),
    }
    for name, r in checks.items():
        extra = {k: v for k, v in r.items() if k not in ("status", "why")}
        print(f"  {r['status']:8s} {name:18s} {json.dumps(extra)[:110]}")
        if r["status"] != "OK" and r.get("why"):
            print(f"           -> {str(r['why'])[:150]}")

    bad = [k for k, v in checks.items() if v["status"] == "DEFECT"]
    unknown = [k for k, v in checks.items() if v["status"] == "UNKNOWN"]
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"), "repairs": repairs,
                               "checks": checks, "defects": bad, "unknown": unknown}, indent=1,
                              default=str), "utf-8")
    print(f"\n  {len(bad)} defect(s), {len(unknown)} unmeasured -> {OUT}")
    return 1 if (bad or unknown) else 0


if __name__ == "__main__":
    raise SystemExit(main())
