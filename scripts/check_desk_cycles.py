"""Watch the GATES and the LOCAL CYCLES, and correct them in the same pass.

WHY THIS EXISTS

Every defect this desk lost days to in the last week was something a person had to notice:

  * the gate policy on the desk box was the pre-YAML loader while the spec beside it was current,
    so the box certified with non-canonical code and nothing said so;
  * the power-cure lane admitted exactly ONE family by a hardcoded whitelist, so 506 cells that
    cleared every validity gate could never gather the forward evidence their failing gate is
    declared curable by;
  * the unified dig was cut off after 10,667 bytes and the resume gate, scoring bytes, called it
    finished -- so it never resumed that day;
  * three cron jobs had never run once, and the absence of their log files was the only evidence.

None of those are subtle once measured. They were invisible because nothing measured them. This
checks each one every few minutes and ACTS: a stale cycle is restarted, a drifted module is
re-shipped, a missing cure lane is re-run. Reporting alone is what let them stand for days.

WHAT IT WILL NOT DO. It never edits a threshold, never rewrites a gate, and never promotes
anything. Gate DRIFT is healed by re-shipping what HEAD already says; gate CONTENT is the
principal's. A watchdog that could change the bar it enforces is not a watchdog.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "desk_cycles.json"

#: The canonical ten, in canonical order. Hardcoded ON PURPOSE: this is the invariant being
#: checked, so reading it from the same file it validates would make the check vacuous.
CANONICAL_GATES = (
    "economic_prior", "in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa",
    "cpcv", "walk_forward", "stress_costs", "lockbox", "expected_value",
)
CANONICAL_VALIDITY = {"economic_prior", "pbo", "reality_check_spa", "stress_costs", "lockbox"}
CANONICAL_POWER = {"in_sample_screen", "deflated_sharpe", "cpcv", "walk_forward",
                   "expected_value"}

#: Daily cycles and the systemd unit that runs each. A cycle absent from here is a cycle nobody
#: is watching, which is how the unified dig went a day without resuming.
DAILY_CYCLES = {
    "frontier_unified": "quant-seat-frontier.service",
    "brain_hunter": "quant-seat-frontier.service",
    "litminer": "quant-seat-litminer.service",
    "dataaxis": "quant-seat-dataaxis.service",
    "prospector": "quant-seat-prospector.service",
}

#: Files whose family-routing must never be narrowed to a whitelist again.
NO_WHITELIST_FILES = (
    "desks/mt5/research/shadow_admission.py",
    "desks/mt5/side_channels/run_external_backtest.py",
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _run(cmd: list[str], timeout: int = 240) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-300:]
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, f"{type(exc).__name__}"


def check_gates(now: datetime) -> tuple[list[str], list[str]]:
    """The ten gates, their classification, and that both boxes run the same policy."""
    breaches: list[str] = []
    fixes: list[str] = []

    spec = None
    try:
        import yaml
        spec = yaml.safe_load((DESK / "policy" / "gate_spec.yaml").read_text("utf-8"))
    except Exception as exc:
        breaches.append(f"GATE-SPEC unreadable ({type(exc).__name__}) -- the policy cannot be "
                        f"verified, so nothing downstream can claim it was applied")
        return breaches, fixes

    names = tuple(g.get("name") for g in (spec.get("gates") or []))
    if names != CANONICAL_GATES:
        breaches.append(f"GATE-SET CHANGED: spec lists {list(names)}, canon is "
                        f"{list(CANONICAL_GATES)} -- the ten-gate policy is not what it claims")
    cls = {g.get("name"): g.get("classification") for g in (spec.get("gates") or [])}
    got_validity = {n for n, c in cls.items() if c == "validity"}
    got_power = {n for n, c in cls.items() if c == "power"}
    if got_validity != CANONICAL_VALIDITY or got_power != CANONICAL_POWER:
        breaches.append(
            f"GATE-CLASSIFICATION CHANGED: validity={sorted(got_validity)} "
            f"power={sorted(got_power)}. Which gates are curable decides what may gather forward "
            f"evidence, so this silently moves the promotion firewall")

    # Both boxes must run the SAME policy. Drift here means the desk certifies with code that is
    # not the code that was reviewed -- healed by re-shipping HEAD, never by editing.
    rc, out = _run([sys.executable, str(ROOT / "scripts" / "check_desk_module_drift.py")], 600)
    if rc == 1 and "healed" in out:
        fixes.append(f"MODULE-DRIFT healed: {out.splitlines()[-1][:160]}")
    elif rc not in (0, 1):
        breaches.append(f"MODULE-DRIFT check failed (rc={rc}) -- cannot confirm the desk box "
                        f"runs the reviewed gate code")
    return breaches, fixes


def check_no_family_whitelist() -> list[str]:
    """No routing file may narrow the hunt to a named set of families.

    Twice now a hardcoded family list has hidden whole mechanism classes: the external backtest
    door reached 8 of 43 families, and the power-cure lane admitted 1. Both looked healthy from
    every count that mattered, because the excluded families simply never appeared.
    """
    breaches: list[str] = []
    needles = ("session_range_breakout\"}", "'session_range_breakout'}")
    for rel in NO_WHITELIST_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text("utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "not in {" in stripped and any(n in stripped for n in needles):
                breaches.append(
                    f"FAMILY WHITELIST reintroduced at {rel}:{line_no} -- "
                    f"{stripped[:90]}. A door only one family can walk through cannot "
                    f"diversify a book, and diversification is the binding constraint")
    return breaches


def check_cycles(now: datetime) -> tuple[list[str], list[str]]:
    """Did each daily cycle run today, and was it CUT OFF rather than finished?"""
    breaches: list[str] = []
    fixes: list[str] = []
    today = now.strftime("%Y%m%d")
    logs = ROOT / "data" / "cro_ai_logs"

    for cycle, unit in DAILY_CYCLES.items():
        sentinel = ROOT / "data" / ".digs" / f"{cycle.replace('frontier_', '')}_{today}.running"
        todays = sorted(logs.glob(f"{cycle}_{today}T*.log"))
        # A sentinel left behind means the dig died mid-run: it is written at start and removed
        # only on a clean return, so its presence needs no cooperation from the dead process.
        if sentinel.exists():
            rc, _ = _run(["systemctl", "--user", "start", unit], 60)
            fixes.append(f"CYCLE {cycle}: cut off mid-run (sentinel present) -- restarted {unit} "
                         f"(rc={rc}); it resumes from where it stopped")
            continue
        if not todays:
            # Before ~06:00 UTC the daily seats have not fired yet; that is not staleness.
            if now.hour >= 9:
                rc, _ = _run(["systemctl", "--user", "start", unit], 60)
                fixes.append(f"CYCLE {cycle}: no run at all today and it is "
                             f"{now.strftime('%H:%M')}Z -- started {unit} (rc={rc})")
            continue
        newest = todays[-1]
        if "exit" not in newest.read_text("utf-8", errors="ignore")[-4000:]:
            rc, _ = _run(["systemctl", "--user", "start", unit], 60)
            fixes.append(f"CYCLE {cycle}: today's log has no completion marker -- restarted "
                         f"{unit} (rc={rc}). Bytes are not completion")
    return breaches, fixes


def check_cure_lane(now: datetime) -> tuple[list[str], list[str]]:
    """If the sweep found validity-pass cells, the cure lane must be publishing them."""
    breaches: list[str] = []
    fixes: list[str] = []
    gates = _read(DESK / "reports" / "universal_gates_external.json")
    if not gates:
        return breaches, fixes
    judged = [v for v in (gates.get("verdicts") or []) if (v.get("stages") or {})]
    eligible = 0
    for v in judged:
        st = v["stages"]
        if v.get("passed"):
            continue
        if not all(isinstance(st.get(g), dict) and st[g].get("passed") is True
                   for g in CANONICAL_VALIDITY):
            continue
        if any(not (isinstance(st.get(g), dict) and st[g].get("passed") is True)
               for g in CANONICAL_POWER):
            eligible += 1
    if not eligible:
        return breaches, fixes
    cure = _read(DESK / "reports" / "POWER_CURE_CANDIDATES.json")
    if not cure:
        breaches.append(
            f"CURE LANE DARK: {eligible} cell(s) cleared every validity gate and failed only "
            f"curable ones, and POWER_CURE_CANDIDATES.json does not exist. The cure the policy "
            f"promises is unreachable, which makes it a wish rather than a rule")
    elif not (cure.get("candidates") or {}):
        breaches.append(
            f"CURE LANE EMPTY: {eligible} eligible cell(s) in the gate report but the cure "
            f"artifact lists none -- the two disagree and the artifact is what admission reads")
    if breaches:
        # THE FIXER: the artifact is written BY the sweep, so the repair is to run one. Only the
        # gauntlet may produce it -- this never writes the file itself, because a cure candidate
        # invented outside the gate run is a candidate nobody gated.
        rc, _ = _run(["ssh", "-o", "ConnectTimeout=25", "contabo-mt5",
                      "powershell -Command \"schtasks /Run /TN MT5-Gauntlet\""], 90)
        fixes.append(f"CURE LANE: triggered MT5-Gauntlet (rc={rc}) so the sweep publishes "
                     f"POWER_CURE_CANDIDATES.json for the {eligible} eligible cell(s)")
    return breaches, fixes


def main() -> int:
    now = datetime.now(tz=UTC)
    breaches: list[str] = []
    fixes: list[str] = []

    gb, gf = check_gates(now)
    breaches += gb
    fixes += gf
    breaches += check_no_family_whitelist()
    cb, cf = check_cycles(now)
    breaches += cb
    fixes += cf
    lb, lf = check_cure_lane(now)
    breaches += lb
    fixes += lf

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "breaches": breaches,
        "fixes_applied": fixes,
    }
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    if fixes:
        print(f"DESK CYCLES -- {len(fixes)} correction(s) applied {now.isoformat(timespec='seconds')}")
        for f in fixes:
            print(f"  FIXED  {f}")
    if breaches:
        print(f"DESK CYCLES BREACH {now.isoformat(timespec='seconds')}")
        for b in breaches:
            print(f"  - {b}")
        return 1
    if not fixes:
        print(f"desk cycles: gates canonical, no family whitelist, cycles current "
              f"({now.isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
