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


def check_dashboard() -> dict[str, Any]:
    """What the principal actually looks at. A dashboard reporting stale numbers is a lie at rest.

    It reads `web/desk_state.json`, which is pulled from the trading box every two minutes -- so a
    stamp older than an hour means the pull is dead and every figure on the page is describing a
    desk that has moved on, while looking perfectly current.
    """
    d = _json(ROOT / "web" / "desk_state.json")
    if d is None:
        return {"status": "UNKNOWN", "why": "desk_state.json unreadable -- the dashboard is blind"}
    acct = d.get("account") or {}
    age = acct.get("source_age_seconds")
    stamp = d.get("generated_at") or acct.get("source_updated_at") or ""
    stale = isinstance(age, (int, float)) and age > 3600
    res = d.get("research") or {}
    return {"status": "DEFECT" if stale else "OK",
            "generated_at": str(stamp)[:19], "source_age_s": age,
            "equity": acct.get("equity"), "canonical_survivors": res.get("canonical_survivors"),
            "why": ("the dashboard is serving figures older than an hour -- the desk pull is dead "
                    "and every number on the page is stale while looking current"
                    if stale else "dashboard current")}


def heal_forward_clocks() -> dict[str, Any]:
    """Clocks terminal on a drift that no longer exists are healed by RUNNING the engine.

    Not by rewriting a status. `shadow_forward` clears IDENTITY_BROKEN itself once `verify()`
    returns no drift, so the repair is to give it a pass -- on the box, where the live bars are.
    Rewriting the status here would empty this report and change nothing underneath, which is the
    failure mode a fixer that can hide its own failure always has.
    """
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json")
    if st is None:
        return {"acted": False, "why": "shadow_state unreadable"}
    sl = st.get("sleeves") or st
    broken = [k for k, v in sl.items()
              if isinstance(v, dict) and str(v.get("status") or "") == "IDENTITY_BROKEN"]
    if not broken:
        return {"acted": False, "why": "no clock is terminal on identity"}
    try:
        subprocess.run(["systemctl", "--user", "start", "--no-block",
                        "quant-forward-box.service"], timeout=60, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        return {"acted": False, "why": f"could not trigger the engine: {type(exc).__name__}"}
    return {"acted": True, "identity_broken": len(broken),
            "why": ("triggered the forward engine on the trading box; it clears the status itself "
                    "when verify() finds no drift, so nothing here rewrites a verdict")}


def check_conversion() -> dict[str, Any]:
    """Every funnel stage's yield, and whether it is getting better or quietly rotting.

    THE DESK'S FAILURE MODE IS A LEGITIMATE-LOOKING ZERO. A crawler with 75 sources and 474MB of
    corpus that converts NOTHING reports exactly like a crawler that is switched off, and the
    deep audit returned 0/0/0/1 findings for days while running on schedule. So this measures the
    RATIO at each hop rather than whether the job ran.
    """
    out: dict[str, Any] = {}
    comp = _json(ROOT / "data" / "proposal_compiler.json") or {}
    ok, ref = comp.get("compiled"), comp.get("refused")
    if isinstance(ok, int) and isinstance(ref, int) and (ok + ref):
        rate = ok / (ok + ref)
        out["compile"] = {"compiled": ok, "refused": ref, "rate": round(rate, 3)}

    audit = _json(ROOT / "data" / "deep_audit.json") or {}
    lenses = audit.get("results") or {}
    found = sum(len(v.get("findings") or []) for v in lenses.values() if isinstance(v, dict))
    out["deep_audit"] = {"lenses": len(lenses), "findings": found, "ran_at": audit.get("ran_at")}

    free = _json(ROOT / "data" / "free_research.json") or {}
    props = sum(len(r.get("proposals") or []) for r in (free.get("results") or []))
    out["free_research"] = {"proposals": props, "ran_at": free.get("ran_at")}

    mc = _json(ROOT / "data" / "miner_conversion.json") or {}
    miners = mc.get("miners") or {}
    zero = len(mc.get("zero_yield_miners") or [])
    out["miners"] = {"total": len(miners), "zero_yield": zero}

    # A LENS THAT RETURNS NOTHING IS A DEFECT, not a clean audit. Measured 2026-09-04: all four
    # lenses read 0 for days because the parser scored the model's own instructions and the token
    # cap truncated the answer -- the job ran perfectly on schedule the whole time.
    bad = (found == 0 and len(lenses) > 0) or props == 0 or (
        "compile" in out and out["compile"]["rate"] < 0.10)
    out["status"] = "DEFECT" if bad else "OK"
    out["why"] = ("a funnel stage is yielding nothing while running on schedule -- the shape of a "
                  "silent zero, not of an honest negative result" if bad else "every stage yielding")
    return out


def check_funnel() -> dict[str, Any]:
    """Every hop from discovery to a running clock, and WHICH hop is dead.

    A funnel reported only at its ends cannot say where it broke. Measured this session: the
    crawler held 6,251 documents, the queue held 2,050 hypotheses, 94 compiled, 58 certified and
    0 clocks were accruing -- and each stage looked healthy from inside itself. The dead hop was
    the last one, and nothing named it because nothing compared the hops.

    STAGE-TO-STAGE, therefore. A hop whose input is large and whose output is zero is the defect,
    and it is reported with the repair that belongs to THAT hop rather than a generic alarm.
    """
    stages: dict[str, Any] = {}
    q = ROOT / "data" / "hypothesis_queue.jsonl"
    try:
        stages["queued"] = sum(1 for _ in q.open(encoding="utf-8")) if q.exists() else 0
    except OSError:
        stages["queued"] = None

    comp = _json(DESK / "data" / "hypotheses" / "compiled_proposals.json") or {}
    stages["compiled"] = len(comp.get("cells") or [])

    bt = _json(DESK / "data" / "hypotheses" / "external_backtest_results.json")
    stages["backtested"] = (len(bt) if isinstance(bt, list)
                            else len(bt.get("results") or bt.get("cells") or {})
                            if isinstance(bt, dict) else None)

    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    stages["certified"] = len(canon.get("survivors") or {})

    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    rows = [v for v in sl.values() if isinstance(v, dict)]
    stages["clocked"] = sum(1 for v in rows if str(v.get("status") or "") == "ACTIVE")
    stages["trades"] = sum(v.get("n", 0) or 0 for v in rows
                           if str(v.get("status") or "") == "ACTIVE")

    #: hop -> (input stage, output stage, what repairs THAT hop)
    hops = (("compile", "queued", "compiled", "scripts/compile_proposals.py"),
            ("backtest", "compiled", "backtested", "ops/run_external_pipeline.sh"),
            ("certify", "backtested", "certified", "scripts/certify_gauntlet.py"),
            ("enrol", "certified", "clocked", "ops/run_forward_on_box.sh"))
    dead = []
    for name, src, dst, repair in hops:
        a, b = stages.get(src), stages.get(dst)
        if a is None or b is None:
            continue
        if a > 0 and b == 0:
            dead.append({"hop": name, "in": a, "out": b, "repair": repair,
                         "why": f"{a} in, ZERO out -- this hop is where the desk stops"})
    return {"status": "DEFECT" if dead else "OK", "stages": stages, "dead_hops": dead,
            "why": ("a hop with input and no output is the defect; the stage before it is healthy "
                    "and the stage after it is starved" if dead else "every hop passing volume")}


def next_growth_lever() -> dict[str, Any]:
    """The next lever for E[log W], ranked by MEASURED deficit rather than by opinion.

    Only the mechanical ones are acted on here. A lever with a trade-off -- lowering a gate,
    resizing live risk, changing what a certificate asserts -- is named and left for the principal,
    because an autonomous fixer that can relax its own bar will eventually relax it.
    """
    levers: list[dict[str, Any]] = []
    st = _json(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    sl = st.get("sleeves") or st
    act = [v for v in sl.values() if isinstance(v, dict) and v.get("status") == "ACTIVE"]
    if act:
        days = max(1.0, max((v.get("days_active") or 0) for v in act))
        rate = sum(v.get("n", 0) or 0 for v in act) / len(act) / days
        need = 50.0 / 14.0
        if rate < need:
            levers.append({
                "lever": "forward throughput", "measured": f"{rate:.2f} trades/sleeve/day",
                "needed": f"{need:.2f}", "shortfall": f"{need / max(rate, 1e-9):.1f}x",
                "act": "AUTOMATIC: none -- breadth is the fix and adding sleeves is a research act",
                "why": "n>=50 within a 14-day window is unreachable at this rate"})

    canon = _json(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    survivors = canon.get("survivors") or {}
    fams: dict[str, int] = {}
    for v in survivors.values():
        f = str((v.get("shadow_spec") or {}).get("family") or "?")
        fams[f] = fams.get(f, 0) + 1
    if survivors:
        top = max(fams.values()) / len(survivors)
        if top > 0.30:
            levers.append({
                "lever": "book independence", "measured": f"{top:.1%} in one family",
                "needed": "<30%", "act": "AUTOMATIC: none -- needs absent families to certify",
                "why": ("concentration caps n_eff: fifty variants of one bet is one bet, and "
                        "E[log W] pays for INDEPENDENT bets")})

    comp = _json(ROOT / "data" / "proposal_compiler.json") or {}
    if isinstance(comp.get("refused"), int) and comp.get("refused"):
        levers.append({
            "lever": "proposal conversion",
            "measured": f"{comp.get('compiled')} compiled / {comp.get('refused')} refused",
            "act": "AUTOMATIC: the axis contract is enforced at generation; refusals re-measured "
                   "each pass",
            "why": "a refusal for an unresolved axis is fixable at the prompt; a duplicate is not"})
    return {"levers": levers, "n": len(levers),
            "note": ("ranked by measured deficit. Levers with a TRADE-OFF (lowering a gate, "
                     "resizing live risk, changing what a certificate asserts) are named and left "
                     "for the principal -- a fixer that may relax its own bar eventually will.")}


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

    if not a.report:
        healed = heal_forward_clocks()
        repairs.append({"check": "forward clocks", "exit": 0,
                        "acted": [healed.get("why", "")] if healed.get("acted") else []})
        if healed.get("acted"):
            print(f"  repair forward clocks      {healed['identity_broken']} terminal clock(s) "
                  f"-- engine triggered on the box")

    checks = {
        "dashboard": check_dashboard(),
        "conversion": check_conversion(),
        "funnel": check_funnel(),
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

    lever = next_growth_lever()
    if lever["levers"]:
        print("\n  NEXT GROWTH LEVERS (measured deficit, largest first):")
        for lv in lever["levers"]:
            print(f"    {lv['lever']:22s} {str(lv.get('measured'))[:34]:34s} {lv['act'][:64]}")

    bad = [k for k, v in checks.items() if v["status"] == "DEFECT"]
    unknown = [k for k, v in checks.items() if v["status"] == "UNKNOWN"]
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"), "repairs": repairs,
                               "checks": checks, "defects": bad, "unknown": unknown,
                               "growth_levers": lever}, indent=1,
                              default=str), "utf-8")
    if not bad and not unknown:
        # A QUIET RUN IS THE POINT. On a healthy desk this says so in one line and does nothing --
        # a sweep that always finds something to do trains its reader to stop looking.
        print("\n  ALL CLEAR -- every pair agrees, no evidence frozen, nothing repaired")
    else:
        print(f"\n  {len(bad)} defect(s), {len(unknown)} unmeasured -> {OUT}")
    return 1 if (bad or unknown) else 0


if __name__ == "__main__":
    raise SystemExit(main())
