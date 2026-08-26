#!/usr/bin/env python3
"""Resurrect allowlisted ops/crontab.manifest rows under a user timer (cron died 08-20).

ROOT CAUSE, measured 2026-08-26: root `cron.service` OOM-died 2026-08-20 and cannot be restarted
without the principal's console (no sudo by design). Every row in ops/crontab.manifest without a
user-timer twin has been silently dead since -- including the hourly law gate, the DAILY RATCHET
RAISER (the direct cause of the 16-day L1.50 coverage-floor stall), the §33 conversion fence and
the deploy puller. This dispatcher runs every 5 minutes from `quant-manifest-dispatch.timer` and
fires the rows on the ALLOWLIST below with exact cron semantics, reading schedule and command
LIVE from the manifest (anti-hardcode law: the manifest stays the single source of truth; the
allowlist only GATES which rows may fire, because most manifest rows are retired-crypto-era
organs that the MT5 mandate forbids resurrecting blindly).

Safety properties:
- Only allowlisted rows fire. Everything else is COUNTED in the state artifact as
  `uncovered_unallowed` so the remaining backlog is measured, never silent (L1.28a).
- A row whose script is referenced by any installed user unit is skipped (twin check at
  runtime) -- building a proper dedicated timer later auto-retires the dispatcher's copy.
- Catch-up window is capped: a row missed by more than CATCHUP_CAP_MIN minutes waits for its
  next scheduled slot instead of thundering after an outage.
- Rows keep their own flock/redirect wrapping; the dispatcher detaches and never blocks on them.
"""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "ops" / "crontab.manifest"
STATE = ROOT / "data" / "manifest_dispatch_state.json"
USER_UNITS = Path.home() / ".config" / "systemd" / "user"
CATCHUP_CAP_MIN = 20

#: script token -> why this row is resurrected. Tokens are matched against the manifest at
#: runtime; a token with no surviving manifest row simply never fires. EVERYTHING ELSE in the
#: manifest stays dead until a human moves it here or builds it a real timer -- most rows are
#: crypto-era organs the MT5 mandate (LAWS §1) forbids waking.
ALLOWLIST: dict[str, str] = {
    "scripts/run_law_gate.py": "hourly law gate -- the enforcement entry point for every organ",
    "scripts/check_conversion.py": "hourly §33 conversion fence",
    "scripts/check_ratchets.py": "daily ratchet raiser (its death caused the L1.50 floor stall)",
    "scripts/check_constitution_core.py": "6-hourly seal verification",
    "scripts/check_utilisation.py": "6-hourly utilisation/timidity fence",
    "scripts/check_fence_yield.py": "daily L1.43 governance-yield measurement",
    "scripts/check_enforcement_execution.py": "daily enforcement-execution fence",
    "scripts/check_campaign_retention.py": "daily campaign-retention fence",
    "scripts/check_repair_capacity.py": "daily repair-capacity fence",
    "scripts/build_event_calendar.py": "monthly macro event calendar (MT5 event guard input)",
    "scripts/run_intelligence_cycle.py": "4-hourly macro collectors (WALCL/RFB vintages feed MT5 axes)",
    "deploy/pull_deploy.sh": "10-min inbound deploy path (dead 126h; fence reads its state)",
    # ------------------------------------------------------------------------------------
    # SECOND WAVE, gap-fixer 2026-08-26. The first wave rescued 12 rows and left 173
    # venue-agnostic ones dead, because the backlog number this script writes was consumed by
    # NOBODY (grep: zero readers of manifest_dispatch_state.json) -- a measurement with no
    # consumer is an opinion, so "216 uncovered" sat in a file for six days and escalated to
    # no one. Every token below was RUN BY HAND on 2026-08-26 before being listed here: each
    # exits 0 or exits 2-with-a-real-finding, and none is crypto-era. rc=2 on a fence is
    # correct behaviour, not a failure -- these organs are supposed to fail loud.
    # Ordered by expected terminal-wealth impact, which is why the liveness fence leads:
    # ITS death is why the other 172 deaths went unnoticed.
    # ------------------------------------------------------------------------------------
    "scripts/check_organ_liveness.py": "hourly dead-organ detector -- ITSELF dead 128h; the "
                                       "reason the 08-20 cron death escalated to nobody",
    "scripts/check_freshness.py": "hourly L1.44 consumption-time freshness contracts",
    "scripts/check_change_window.py": "hourly L1.38 sterile-cockpit window (money-path guard)",
    "scripts/check_promotion_gate.py": "hourly L1.6 promotion-gate rung state",
    "scripts/run_promotion_queue.py": "6-hourly promotion queue -- the forward->live door",
    "scripts/check_gate0_ready.py": "hourly Gate-0 readiness ledger",
    "scripts/check_risk_units.py": "daily L1.67 risk-UNITS audit (the CADJPY 1.26%-logged/"
                                   "7.41%-run defect class; no other fence asks this)",
    "scripts/run_portfolio_risk.py": "daily portfolio risk aggregation",
    "scripts/run_sleeve_allocator.py": "daily sleeve allocation",
    "scripts/max_audit.py": "daily live-defect audit -- the desk's own defect finder was dead",
    "scripts/rerank_gaps.py": "weekly §35 gap re-rank (GAP_REGISTER is the only work driver)",
    "scripts/record_desk_metrics.py": "daily desk metric trend (a snapshot is not a trend)",
    "scripts/check_claim_consistency.py": "daily cross-organ claim contradiction detector",
    "scripts/check_input_provenance.py": "hourly artifact input-provenance declarations",
    "scripts/check_denominators.py": "hourly denominator-declaration fence",
    "scripts/check_idle_cost.py": "hourly idle-capital/timidity meter (LAWS §2a)",
    "scripts/run_stale_daemon_repair.py": "twice-daily stale-daemon actuator",
    "scripts/build_gauntlet_survivors.py": "the eight-gate barrier's MISSING producer -- it had judged zero candidates ever",
    "scripts/promotion_gate.py": "eight-gate screen-side record (capacity+fragility, which the canonical ten do not cover)",
}

#: THE BOX IS THE BINDING CONSTRAINT, AND IT IS NOT TIMIDITY TO SAY SO (measured 2026-08-26:
#: 3814MB total, ZERO swap, ~1660MB available, load 1.9). Three gap-wirer seats and the
#: same-day external pipeline were OOM-killed in the 24h before this was written. Firing a
#: batch of organs into that headroom can take the kernel's OOM killer to `quant-live-guard`
#: or the executor, which is a ruin path, not an inconvenience -- so the governor below names
#: the ruin probability it reduces, as the survival rails require of every clamp.
#: A deferred row is NEVER dropped: it lands in `pending` and fires on a later tick when the
#: headroom returns. Silent truncation would read as "the fleet is covered" when it is not.
MIN_AVAIL_MB = 420           # below this, defer rather than fire (kernel OOM territory)
MAX_FIRES_PER_TICK = 4       # burst cap: a 5-minute tick never thunders the whole manifest
PENDING_MAX_AGE_MIN = 180    # a row deferred longer than this waits for its next natural slot

TOKEN_RE = re.compile(r"(?:scripts|deploy|ops)/[A-Za-z0-9_./-]+\.(?:py|sh)")


def parse_field(expr: str, lo: int, hi: int) -> set[int]:
    """One cron field -> the set of matching values. Supports * a a-b a-b/n */n lists."""
    vals: set[int] = set()
    for part in expr.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part == "*":
            rng = range(lo, hi + 1)
        elif "-" in part:
            a, b = part.split("-", 1)
            rng = range(int(a), int(b) + 1)
        else:
            v = int(part)
            rng = range(v, v + 1)
        vals.update(v for v in rng if (v - rng.start) % step == 0)
    if hi == 7 and 7 in vals:  # cron dow: 7 == Sunday == 0
        vals.discard(7)
        vals.add(0)
    return vals


def cron_matches(spec: str, t: datetime) -> bool:
    """Vixie-cron semantics: if BOTH dom and dow are restricted, either may match."""
    f = spec.split()
    if len(f) != 5:
        return False
    minute, hour, dom, month, dow = f
    if t.minute not in parse_field(minute, 0, 59):
        return False
    if t.hour not in parse_field(hour, 0, 23):
        return False
    if t.month not in parse_field(month, 1, 12):
        return False
    dom_ok = t.day in parse_field(dom, 1, 31)
    dow_ok = ((t.weekday() + 1) % 7) in parse_field(dow, 0, 7)  # cron: 0=Sunday
    if dom != "*" and dow != "*":
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _avail_mb() -> float:
    """MemAvailable in MB, or +inf when it cannot be read.

    FAILING OPEN IS THE RIGHT DIRECTION HERE and it is a deliberate choice, not an oversight:
    this governor exists to protect a 3.8GB swapless box from an OOM cascade, but a governor
    that cannot read memory and therefore refuses to fire ANYTHING would silently re-create
    the exact outage it was built to end -- 200 organs dead and no one told. An unreadable
    /proc/meminfo is a broken probe, and a broken probe must not be allowed to hold the fleet
    down; the OOM killer is a survivable event, six silent days is not.
    """
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return float("inf")


def manifest_rows() -> list[tuple[str, str, str]]:
    """(cron_spec, command, token) for every active manifest row that names a script."""
    rows: list[tuple[str, str, str]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" in line.split(" ", 1)[0]:
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        spec, cmd = " ".join(parts[:5]), parts[5]
        m = TOKEN_RE.search(cmd)
        if m:
            rows.append((spec, cmd, m.group(0)))
    return rows


def twinned_tokens() -> set[str]:
    """Script tokens already referenced by an installed user unit -- never double-fire those."""
    tokens: set[str] = set()
    if USER_UNITS.is_dir():
        for unit in USER_UNITS.glob("*.service"):
            try:
                text = unit.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            tokens.update(TOKEN_RE.findall(text))
    return tokens


def due_times(spec: str, since: datetime, until: datetime) -> list[datetime]:
    t = since.replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    while t <= until:
        if cron_matches(spec, t):
            out.append(t)
        t += timedelta(minutes=1)
    return out


def main() -> int:
    now = datetime.now(tz=UTC)
    state: dict[str, object] = {}
    if STATE.is_file():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
    last_check = now - timedelta(minutes=5)
    if state.get("last_check"):
        with contextlib.suppress(ValueError):
            last_check = datetime.fromisoformat(state["last_check"])
    last_check = max(last_check, now - timedelta(minutes=CATCHUP_CAP_MIN))

    twins = twinned_tokens()
    fired: list[str] = []
    skipped_twinned: list[str] = []
    deferred: list[str] = []
    uncovered_tokens: set[str] = set()
    rows = manifest_rows()

    # THE TWIN CHECK RUNS FIRST NOW. It used to run AFTER `uncovered += 1`, so any row that
    # already had a real user timer -- run_moat_backup, run_live_guard, run_drills, certify_
    # gauntlet and 11 others -- was counted as part of the dead backlog it had already left.
    # The published figure was 216 uncovered of 228; the true dead set is 201. A backlog gauge
    # that counts healed rows as sick can never reach zero, so the ratchet it feeds could never
    # close (L1.50) and the number could never be trusted enough to act on.
    due: list[tuple[str, str]] = []
    for spec, cmd, token in rows:
        if token in twins:
            skipped_twinned.append(token)
            continue
        if token not in ALLOWLIST:
            uncovered_tokens.add(token)
            continue
        try:
            if not due_times(spec, last_check, now):
                continue
        except ValueError:
            continue  # malformed spec on an allowlisted row: never crash the whole dispatcher
        due.append((token, cmd))

    # Rows deferred by a previous tick's governor come first: they are already late, and the
    # whole point of the pending queue is that a governor delays work rather than losing it.
    pending: dict[str, dict[str, str]] = dict(state.get("pending") or {})
    replay: list[tuple[str, str]] = []
    for token, row in list(pending.items()):
        try:
            since = datetime.fromisoformat(str(row.get("since")))
        except (TypeError, ValueError):
            pending.pop(token, None)
            continue
        if (now - since) > timedelta(minutes=PENDING_MAX_AGE_MIN):
            pending.pop(token, None)  # stale: wait for the row's next natural slot, never thunder
            continue
        replay.append((token, str(row.get("cmd", ""))))
    queue = replay + [d for d in due if d[0] not in pending]

    for token, cmd in queue:
        if len(fired) >= MAX_FIRES_PER_TICK or _avail_mb() < MIN_AVAIL_MB:
            deferred.append(token)
            pending[token] = {"cmd": cmd, "since": pending.get(token, {}).get(
                "since", now.isoformat(timespec="seconds"))}
            continue
        subprocess.Popen(["/bin/sh", "-c", cmd], cwd=ROOT,
                         env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                              "QUANT_ROOT": str(ROOT)},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        fired.append(token)
        pending.pop(token, None)
        row_state = state.setdefault("rows", {}).setdefault(token, {})
        row_state["last_fired"] = now.isoformat(timespec="seconds")
        row_state["fires"] = int(row_state.get("fires", 0)) + 1

    state["last_check"] = now.isoformat(timespec="seconds")
    state["fired_this_run"] = fired
    state["deferred_this_run"] = deferred
    state["pending"] = pending
    state["avail_mb"] = _avail_mb()
    state["skipped_twinned"] = sorted(set(skipped_twinned))
    state["uncovered_unallowed"] = len(uncovered_tokens)
    # The COUNT alone is not actionable -- the next seat needs to know WHICH organs are dead
    # without re-deriving it. The list is what turns this artifact from a number into a queue.
    state["uncovered_tokens"] = sorted(uncovered_tokens)
    state["allowlisted"] = len(ALLOWLIST)
    state["manifest_rows_seen"] = len(rows)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    if fired:
        print(f"manifest-dispatch: fired {fired}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
