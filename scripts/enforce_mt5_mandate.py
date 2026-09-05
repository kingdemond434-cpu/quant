#!/usr/bin/env python3
"""The MT5 universe mandate, enforced on the box instead of written down.

WHY THIS EXISTS (2026-09-05). The principal retired the crypto-exchange universe on 2026-08-18:
"no miner, hunter, query, channel list, scoring vocabulary, or research mandate may target
crypto-exchange-native opportunities." The REPO was cleaned. The BOX was not: thirteen systemd
user timers were still firing `scripts/run_crypto_research.py` (a crypto hypothesis factory over
thirty symbols), plus a perp-DEX funding collector and an X-narrative collector for the same
retired universe. `scripts/check_unit_parity.py` sees them and says nothing, by design -- its
rule is "units present in ops/ but not installed are NOT a defect", and it has no rule at all
for a unit that IS installed and must not be.

The cost is not abstract. Measured 2026-09-05 on an 8 GB research box: 238 MB available, below
the 300 MB floor at which the kernel starts choosing victims. `edge_search` needs ~2000 MB and
could not start, `orthogonal_sweep` needs ~1250 MB and could not start, so the search leg went
27.7 h stale, the sweep 22.4 h, the canon 50.8 h, and two seats died of memory rather than of
anything they did. A mandate that only exists in a document does not free a page of RAM.

WHAT IT DOES, in this order, and it is all reversible by a human in one command:
  1. CENSUS. Names the top resident processes with their RSS, so the health fence can say WHO
     holds the memory instead of only how little is left. A number with no name has never
     started a repair.
  2. ENFORCE. For every process whose command line runs a script on `FORBIDDEN` -- the
     crypto-exchange HUNTERS, listed one by one with the reason -- stop and disable its systemd
     user timer and unit, then terminate it (SIGTERM, then SIGKILL after a grace period).
  3. REPORT. `data/mandate_enforcement.json`: what was found, what was stopped, what was freed,
     and what was NAMED BUT NOT TOUCHED because it is a principal decision rather than a rule.

WHAT IT WILL NEVER TOUCH. `PROTECTED` is checked first and wins over everything: the MT5
gateway, the forward engine, the promoter, the allocator, the dashboard, the deadman rail
(`scripts/run_deadman_switch.py`, Tier-3 never-touch) and its reconciliation companions, this
pipeline, and the data-moat recorders. The recorders store a venue the desk no longer trades and
are therefore a RETIREMENT DECISION, not a rule breach -- they are named in the report under
`principal_decision` and left running, because deleting a permanently unrecoverable asset is not
a call a scheduled script gets to make.

    python3 scripts/enforce_mt5_mandate.py [--dry-run] [--top 15]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _root() -> Path:
    """The repo this report belongs to, whichever copy of the script is running.

    `parents[1]` alone is wrong for the way this script is actually reached in an emergency:
    copied to /tmp and run from there (the fastest path to freeing memory when the checkout
    cannot merge), it resolved ROOT to "/" and died with PermissionError on /data before it had
    stopped a single organ. A memory fixer that only works from inside a healthy checkout is
    not a fixer. Order: an explicit QUANT_ROOT, then the script's own repo, then the working
    directory's repo, then the standard VPS path, then the working directory itself.
    """
    env = os.environ.get("QUANT_ROOT")
    if env and (Path(env) / "scripts").is_dir():
        return Path(env)
    here = Path(__file__).resolve().parents[1]
    if (here / "scripts").is_dir():
        return here
    cwd = Path.cwd()
    for cand in (cwd, *cwd.parents):
        if (cand / "scripts" / "enforce_mt5_mandate.py").exists():
            return cand
    vps = Path("/home/quant/quant-platform")
    return vps if (vps / "scripts").is_dir() else cwd


ROOT = _root()
OUT = ROOT / "data" / "mandate_enforcement.json"

#: Crypto-exchange HUNTERS: scripts whose purpose is to discover, screen or collect
#: opportunities native to a crypto exchange. Each is named with why it qualifies, because a
#: list without reasons is a list nobody can safely extend.
FORBIDDEN: dict[str, str] = {
    "run_crypto_research.py": "crypto hypothesis factory over the crypto-exchange universe",
    "run_crypto_shadow.py": "forward clock for crypto-exchange candidates",
    "run_crypto_portfolio.py": "portfolio construction over crypto-exchange sleeves",
    "run_crypto_target.py": "target selection over the crypto-exchange universe",
    "run_crypto_testnet.py": "crypto-exchange testnet execution loop",
    "ingest_crypto.py": "ingests the crypto-exchange lake for hunting",
    "ingest_crypto_enriched.py": "ingests the enriched crypto-exchange lake for hunting",
    "collect_perpdex_funding.py": "perp-DEX funding collection as a hunted universe",
    "collect_hyperliquid_funding.py": "perp-DEX funding collection as a hunted universe",
    "collect_x_signals.py": "X narrative collection for crypto symbols",
    "probe_bybit_archive.py": "crypto-exchange archive probe",
    "screen_bybit_print_flags.py": "screens crypto-exchange prints for opportunities",
}

#: Checked FIRST and wins over every other rule. A substring here in the command line means the
#: process is never signalled, whatever else matches.
PROTECTED: tuple[str, ...] = (
    "run_gateway_loop.py", "gateway.py", "shadow_forward.py", "shadow_cycle.py",
    "promoter.py", "pf_allocator.py", "research_supervisor.py", "serve_dashboard.py",
    "run_deadman_switch.py", "run_deadman_reconciliation.py", "run_deadman_stranded_sweep.py",
    "run_trade_forensics.py", "run_external_pipeline.sh", "enforce_mt5_mandate.py",
    "hourly_cycle.py", "daily_cycle.py", "hourly_discovery.py",
)

#: Named in the report, never touched: retired-venue assets whose removal is the principal's
#: call, not a rule's. The recorders hold the only permanently unrecoverable dataset the desk
#: owns; a scheduled script does not get to delete history.
PRINCIPAL_DECISION: dict[str, str] = {
    "run_recorder.py": "Binance USD-M microstructure moat recorder (retired venue, stored asset)",
    "run_recorder_spot.py": "Binance spot microstructure moat recorder (retired venue)",
    "run_recorder_bybit.py": "Bybit microstructure moat recorder (retired venue)",
}

#: Seconds between SIGTERM and SIGKILL. A hypothesis factory has nothing to flush that matters;
#: the grace period exists so a half-written artifact is closed rather than truncated.
TERM_GRACE_S = 5.0


def _procs() -> list[dict[str, Any]]:
    """Every process this user can see: pid, rss_mb, etime_s and command line.

    Reads /proc directly rather than shelling out to ps, so it works identically on a box with a
    trimmed userland and cannot be confused by a locale-dependent ps format.
    """
    rows: list[dict[str, Any]] = []
    ticks = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    try:
        with open("/proc/uptime", encoding="utf-8") as f:
            uptime = float(f.read().split()[0])
    except (OSError, ValueError):
        uptime = 0.0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", "replace").strip()
            if not cmd:
                continue
            rss_kb = 0
            for line in (entry / "status").read_text("utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    break
            start_ticks = float((entry / "stat").read_text("utf-8").rsplit(") ", 1)[1].split()[19])
            age = max(uptime - start_ticks / ticks, 0.0)
        except (OSError, ValueError, IndexError):
            continue
        rows.append({"pid": pid, "rss_mb": round(rss_kb / 1024, 1), "etime_s": round(age),
                     "cmd": cmd[:400]})
    rows.sort(key=lambda r: -r["rss_mb"])
    return rows


def mem_available_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def classify(cmd: str) -> tuple[str, str] | None:
    """(script, why) when this command line runs a forbidden hunter; None otherwise.

    PROTECTED wins first, always. A crypto script name appearing inside a protected process's
    command line -- an argument, a log path, a grep -- must never make that process eligible.
    """
    if any(p in cmd for p in PROTECTED):
        return None
    for script, why in FORBIDDEN.items():
        if script in cmd:
            return script, why
    return None


def _systemctl(*args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                           timeout=30, check=False)
        return r.returncode, (r.stdout + r.stderr).strip()[:300]
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"


#: Why the unit scan could not answer, when it could not. Written by `installed_units` and read
#: by `enforce`, so an unaskable systemd never reads as an all-clear.
_UNIT_SCAN: dict[str, str] = {"why": ""}


def installed_units() -> list[str]:
    """Installed user units whose ExecStart runs a forbidden hunter, so the timer that keeps
    respawning the process is stopped rather than only the process being killed."""
    units: list[str] = []
    rc, out = _systemctl("list-unit-files", "--no-legend", "--no-pager")
    if rc != 0:
        # A MISSING ANSWER IS NOT AN EMPTY ONE. `systemctl --user` needs a session bus, and over
        # a bare ssh it fails with "Failed to connect to bus" -- measured on the VPS, 2026-09-05,
        # where the report then read "0 unit(s) matched" and could not be told apart from "no
        # forbidden unit is installed". Those are opposite findings. The reason is carried out so
        # the caller reports UNKNOWN rather than a clean bill of health.
        _UNIT_SCAN["why"] = f"systemctl --user unavailable (rc={rc}): {out[:120]}"
        return units
    _UNIT_SCAN["why"] = ""
    names = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    for name in names:
        if not name.endswith((".service", ".timer")):
            continue
        rc2, show = _systemctl("show", name, "-p", "ExecStart", "--no-pager")
        target = show if rc2 == 0 else ""
        if any(s in target for s in FORBIDDEN):
            units.append(name)
        elif name.endswith(".timer"):
            # a timer's own ExecStart is empty; judge it by the service it activates
            rc3, unit = _systemctl("show", name, "-p", "Unit", "--no-pager")
            svc = unit.split("=", 1)[1].strip() if rc3 == 0 and "=" in unit else ""
            if svc:
                rc4, svc_exec = _systemctl("show", svc, "-p", "ExecStart", "--no-pager")
                if rc4 == 0 and any(s in svc_exec for s in FORBIDDEN):
                    units.append(name)
    return sorted(set(units))


def enforce(*, dry_run: bool = False, top: int = 15) -> dict[str, Any]:
    procs = _procs()
    before = mem_available_mb()
    census = [{k: p[k] for k in ("pid", "rss_mb", "etime_s", "cmd")} for p in procs[:top]]

    offenders: list[dict[str, Any]] = []
    for p in procs:
        hit = classify(p["cmd"])
        if hit:
            offenders.append({**p, "script": hit[0], "why": hit[1]})

    units = installed_units()
    unit_scan_why = _UNIT_SCAN.get("why") or ""
    stopped_units: list[dict[str, Any]] = []
    if not dry_run:
        for unit in units:
            rc_stop, out_stop = _systemctl("stop", unit)
            rc_dis, out_dis = _systemctl("disable", unit)
            stopped_units.append({"unit": unit, "stop_rc": rc_stop, "disable_rc": rc_dis,
                                  "note": (out_stop or out_dis)[:160]})

    killed: list[dict[str, Any]] = []
    for o in offenders:
        row = {"pid": o["pid"], "script": o["script"], "rss_mb": o["rss_mb"],
               "why": o["why"], "signal": None}
        if dry_run:
            row["signal"] = "DRY_RUN"
            killed.append(row)
            continue
        try:
            os.kill(o["pid"], signal.SIGTERM)
            row["signal"] = "SIGTERM"
        except ProcessLookupError:
            row["signal"] = "GONE"
        except PermissionError:
            row["signal"] = "DENIED"
        killed.append(row)
    if not dry_run and any(r["signal"] == "SIGTERM" for r in killed):
        time.sleep(TERM_GRACE_S)
        for row in killed:
            if row["signal"] != "SIGTERM":
                continue
            try:
                os.kill(row["pid"], 0)
                os.kill(row["pid"], signal.SIGKILL)
                row["signal"] = "SIGKILL"
            except ProcessLookupError:
                pass
            except PermissionError:
                row["signal"] = "DENIED"

    named = [{"pid": p["pid"], "rss_mb": p["rss_mb"], "cmd": p["cmd"][:160],
              "why": why}
             for p in procs for script, why in PRINCIPAL_DECISION.items() if script in p["cmd"]]

    after = mem_available_mb()
    doc: dict[str, Any] = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "dry_run": bool(dry_run),
        "mem_available_mb_before": before,
        "mem_available_mb_after": after,
        "freed_mb": (after - before) if (before is not None and after is not None) else None,
        "held_by_forbidden_mb": round(sum(o["rss_mb"] for o in offenders), 1),
        "census_top": census,
        "offenders": [{k: o[k] for k in ("pid", "rss_mb", "etime_s", "script", "why")}
                      for o in offenders],
        "units_stopped": stopped_units,
        "units_matched": units,
        # "" when the scan ran. Non-empty means the timers were NOT checked, so an empty
        # `units_matched` says nothing about what is installed.
        "unit_scan_unavailable": unit_scan_why,
        "killed": killed,
        # Retired-venue assets left running on purpose: the principal retires these, not a script.
        "principal_decision": named,
        "mandate": ("MT5/Fusion universe only (principal 2026-08-18). Fusion-executable crypto "
                    "CFDs are in scope; crypto-exchange-native hunting is not."),
    }
    # THE REPORT MUST NEVER COST THE ENFORCEMENT. Note-taking that fails is worth strictly less
    # than memory that was freed; the document is returned and printed either way.
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError as exc:
        doc["report_unwritten"] = f"{OUT}: {type(exc).__name__}: {exc}"
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be stopped; signal nothing")
    ap.add_argument("--top", type=int, default=15, help="how many memory holders to name")
    a = ap.parse_args()
    doc = enforce(dry_run=a.dry_run, top=a.top)
    avail = doc["mem_available_mb_after"]
    print(f"mandate: {len(doc['offenders'])} forbidden process(es) holding "
          f"{doc['held_by_forbidden_mb']}MB, {len(doc['units_matched'])} unit(s) matched, "
          f"{avail}MB available after")
    for row in doc["killed"]:
        print(f"  {row['signal']} pid={row['pid']} {row['script']} ({row['rss_mb']}MB) "
              f"-- {row['why']}")
    for u in doc["units_stopped"]:
        print(f"  UNIT stopped+disabled {u['unit']}")
    for n in doc["principal_decision"]:
        print(f"  NAMED (not touched) pid={n['pid']} {n['rss_mb']}MB -- {n['why']}")
    if doc["unit_scan_unavailable"]:
        print(f"  UNIT SCAN UNAVAILABLE -- {doc['unit_scan_unavailable']}. The timers were NOT "
              f"checked; run this on the box's own session (systemd --user) or with "
              f"XDG_RUNTIME_DIR set, or check by hand: "
              f"systemctl --user list-timers | grep -E 'autodiscovery|perpdex|x-collector'")
    if not doc["offenders"] and not doc["units_matched"]:
        top = doc["census_top"][:3]
        print("  no forbidden organ running; the memory is held by: " +
              ", ".join(f"{r['rss_mb']}MB {r['cmd'].split()[-1][:40]}" for r in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
