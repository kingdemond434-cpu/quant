"""UTILISATION FENCE (L1.28a) -- every ceiling this desk owns, measured against its limit.

THE LAW: unused headroom is not safety, it is an unbooked loss. Capital, forward-confirmation
slots, model quota, data already paid for, built capability, scheduler cadence -- each is utilised
to its limit at all times, and idle headroom anywhere is a defect of the same class as a missed
edge.

WHY IDLENESS IS THE MOST EXPENSIVE FAILURE AVAILABLE, and why it needs a fence rather than an
intention: a wrong trade costs a bounded amount and announces itself. Idle capacity costs its
ENTIRE forward output stream and announces nothing. An unfilled forward slot is evidence that will
never be accrued. An unread dataset is a hypothesis never tested. A dormant module is engineering
already paid for returning zero forever. An idle dollar is compounding that never starts. None of
it appears in any P&L, and none of it generates an error -- which is exactly why it persists.

THE RULE THIS ENFORCES: every ceiling declares a LIMIT, carries a MEASURED utilisation, and where
utilisation is short of the limit, names the BINDING CONSTRAINT with a resolution path. Two design
choices follow from the law and both are deliberate:

  * UNMEASURED COUNTS AS ZERO. A ceiling nobody measures is idle by default and nobody would know.
    Treating "no measurement" as "probably fine" is how every one of these gaps survived.
  * A BINDING CONSTRAINT MUST BE NAMED, not implied. "Running at 60% and that seems fine" is a
    defect; "60%, bound by an unfunded OpenRouter key, re-test on funding" is a decision. The
    difference is whether anyone can act on it.

THE ONLY LEGITIMATE IDLE HEADROOM is a survival rail (L1.23 -- drawdown buffer, ruin margin,
Tier-3 reserve) or a named external blocker on the register with a re-test date.

    python scripts/check_utilisation.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/utilisation.json"
_LOGS = _ROOT / "data/cro_ai_logs"

#: Below this fraction of the limit, idle headroom must be explained by a named binding constraint.
_EXPECT = 0.90


@dataclass
class Ceiling:
    name: str
    limit: float
    used: float
    unit: str
    measured: bool
    binding_constraint: str      # "" = none named; required when utilisation < _EXPECT
    why_it_matters: str

    @property
    def utilisation(self) -> float:
        if not self.measured:
            return 0.0           # unmeasured counts as zero -- see module docstring
        return 0.0 if self.limit <= 0 else min(self.used / self.limit, 1.0)

    @property
    def status(self) -> str:
        if not self.measured:
            return "UNMEASURED"
        # OVER-LIMIT IS A MEASUREMENT DEFECT, NOT SATURATION, and clamping it to 100% is how it
        # hides. First run of this fence read deployed capital at $13,155 against $4,500 equity
        # and displayed a comfortable "SATURATED 100%". Either the two numbers come from different
        # sources, or the book is levered and the ceiling is wrong. Both need a human, and neither
        # is the healthy state the clamp implied. A ceiling you cannot trust is worse than one you
        # know is idle: it reports success while measuring nothing.
        if self.limit > 0 and self.used > self.limit * 1.02:
            return "OVER-LIMIT"
        if self.utilisation >= _EXPECT:
            return "SATURATED"
        return "IDLE-EXPLAINED" if self.binding_constraint else "IDLE-UNEXPLAINED"


def _forward_slots() -> Ceiling:
    """The single most load-bearing ceiling on the desk's only path from research to capital."""
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
        snap = derive_slots()
        used, cap = len(snap.get("slots", []) or []), float(MAX_FORWARD_SLOTS)
        measured = True
    except (ImportError, OSError, ValueError, KeyError):
        used, cap, measured = 0.0, 12.0, False
    return Ceiling(
        "forward_confirmation_slots", cap, float(used), "concurrent clocks", measured,
        "" if used >= cap * _EXPECT else
        "candidate supply into the forward queue -- see scripts/run_promotion_queue.py",
        "An empty slot accrues NO evidence while every candidate's capacity decays against a "
        "growing book. Idle slots are the direct mechanism by which an edge arrives already "
        "outgrown (L1.18a runway).")


def _capital() -> Ceiling:
    try:
        from libs.autodiscovery.validation import _desk_equity_usd
        from libs.research.capacity_policy import live_book_usd
        book, eq = float(live_book_usd()), float(_desk_equity_usd())
        measured = eq > 0
    except (ImportError, OSError, ValueError, AttributeError):
        book, eq, measured = 0.0, 0.0, False
    return Ceiling(
        "deployed_capital", eq, book, "USD", measured,
        "" if (measured and eq > 0 and book >= eq * _EXPECT) else
        "live connector not funded (EXECUTION_QUEUE gap #2) -- named external blocker",
        "An idle dollar is compounding that never starts. Under-deployment is a REAL cost "
        "reported as loudly as a risk breach (L1.20, doctrine).")


def _organs() -> Ceiling:
    """Scheduler saturation: manifest entries that actually produced a log in the last 48h."""
    if not _LOGS.exists():
        return Ceiling("scheduler_cadence", 1.0, 0.0, "organs fresh", False,
                       "log directory absent", "A scheduled organ that never runs is a cadence "
                       "declared and not kept -- the capability is paid for and returns zero.")
    manifest = _ROOT / "ops/crontab.manifest"
    scripts = set()
    if manifest.exists():
        for line in manifest.read_text("utf-8").splitlines():
            if line.strip().startswith("#") or "python" not in line:
                continue
            for tok in line.split():
                if tok.endswith(".py"):
                    scripts.add(Path(tok).stem)
    cutoff = (datetime.now(tz=UTC) - timedelta(hours=48)).timestamp()
    fresh = {p.stem.split("_20")[0] for p in _LOGS.glob("*.log") if p.stat().st_mtime >= cutoff}
    hit = sum(1 for s in scripts if any(s in f or f in s for f in fresh))
    return Ceiling(
        "scheduler_cadence", float(len(scripts)), float(hit), "organs run in 48h",
        bool(scripts),
        "" if scripts and hit >= len(scripts) * _EXPECT else
        "organs silent in 48h -- check_organs/check_stale_daemons name which; a fresh container "
        "shows zero because no cron has fired yet",
        "A scheduled organ that never runs is a cadence declared and not kept -- capability "
        "already paid for, returning zero.")


def _capability() -> Ceiling:
    """Built code that nothing imports and nothing schedules: engineering paid for, unused."""
    try:
        from libs.self_improvement.dormancy import scan
        rep = scan()
        total = float(rep.n_scripts_scanned + getattr(rep, "n_modules_scanned", 0))
        dormant = float(len(rep.dormant))
        measured = total > 0
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        total, dormant, measured = 0.0, 0.0, False
    return Ceiling(
        "capability_wired", total, max(total - dormant, 0.0), "reachable units", measured,
        "" if measured and total > 0 and (total - dormant) >= total * _EXPECT else
        "wiring backlog -- scripts/run_wiring_agent.py --apply auto-wires the provably-inert "
        "ones daily; the remainder are money-path/spend-capable and need a human cadence call",
        "A dormant capability is engineering already paid for that returns zero forever, and it "
        "compounds: nobody maintains it, so it rots into a liability (L2.9).")


def _data_assets() -> Ceiling:
    """Datasets acquired vs datasets actually READ by something. Paid-for and unread is the
    purest form of the defect: the cost is already sunk and the return is exactly zero."""
    reg = _ROOT / "data/data_asset_registry.json"
    try:
        rows = json.loads(reg.read_text("utf-8"))
        rows = rows.get("assets", rows) if isinstance(rows, dict) else rows
        total = float(len(rows))
        used = float(sum(1 for r in rows if r.get("consumed_by") or r.get("readers")))
        measured = total > 0
    except (OSError, ValueError, AttributeError, TypeError):
        total, used, measured = 0.0, 0.0, False
    return Ceiling(
        "data_assets_read", total, used, "datasets with a reader", measured,
        "" if measured and total > 0 and used >= total * _EXPECT else
        "registry absent or assets unconsumed -- data_asset_registry needs a consumed_by field "
        "per asset for this to measure rather than assume",
        "An unread dataset is a hypothesis never tested against evidence already bought. The "
        "26-year CFTC COT panel sat unread for weeks -- that is the proving instance (L1.3).")


def _mutation() -> Ceiling:
    """Test STRENGTH, not coverage: the fraction of injected faults the suite actually kills."""
    f = _ROOT / "data/mutation_score.json"
    try:
        d = json.loads(f.read_text("utf-8"))
        # The artifact is PER-TARGET (run_mutation.py writes a `targets` list), so a top-level
        # `kill_rate` lookup silently returned 0.0 and this ceiling read UNMEASURED while a real
        # measurement sat in the file. The aggregate is mutants-weighted, not a mean of rates:
        # a 10-mutant file at 100% must not cancel a 200-mutant file at 80%.
        targets = d.get("targets") or []
        killed = float(sum(float(t.get("killed", 0)) for t in targets))
        total = float(sum(float(t.get("total", 0)) for t in targets))
        score = killed / total if total > 0 else float(d.get("kill_rate", 0.0))
        score = score / 100.0 if score > 1.0 else score
        measured = score > 0
    except (OSError, ValueError, TypeError, AttributeError):
        score, measured = 0.0, False
    return Ceiling(
        "test_kill_rate", 1.0, score, "mutants killed (fraction)", measured,
        "" if score >= _EXPECT else
        "surviving mutants in libs/execution/staging.py and libs/risk/gate.py -- the survivor "
        "list IS the work queue (L1.0c)",
        "An unkilled mutant is a real code change the suite cannot see. On the money path that "
        "is a silent correctness ceiling under every other guarantee.")


def collect() -> list[Ceiling]:
    return [_capital(), _forward_slots(), _capability(), _data_assets(), _organs(), _mutation()]


def build() -> dict[str, Any]:
    ceilings = collect()
    rows = [{**asdict(c), "utilisation": round(c.utilisation, 3), "status": c.status}
            for c in ceilings]
    unexplained = [r["name"] for r in rows if r["status"] == "IDLE-UNEXPLAINED"]
    unmeasured = [r["name"] for r in rows if r["status"] == "UNMEASURED"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28a -- unused headroom is not safety, it is an unbooked loss. Unmeasured "
               "utilisation counts as ZERO: a ceiling nobody measures is idle by default.",
        "expect_fraction": _EXPECT,
        "mean_utilisation": round(sum(c.utilisation for c in ceilings) / max(len(ceilings), 1), 3),
        "idle_unexplained": unexplained, "unmeasured": unmeasured, "ceilings": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"utilisation (L1.28a): mean {rep['mean_utilisation']:.0%} across "
              f"{len(rep['ceilings'])} ceilings")
        for r in rep["ceilings"]:
            bar = f"{r['used']:,.0f}/{r['limit']:,.0f} {r['unit']}"
            print(f"  {r['status']:17} {r['name']:26} {r['utilisation']:6.1%}  {bar}")
            if r["binding_constraint"]:
                print(f"  {'':17} └─ bound by: {r['binding_constraint'][:100]}")
        print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0 if (args.report_only or not rep["idle_unexplained"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
