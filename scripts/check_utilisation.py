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
        used, cap = float(len(snap.get("slots", []) or [])), float(MAX_FORWARD_SLOTS)
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
    """Capital ACTUALLY deployed against capital available -- and they must be two sources.

    THE WELD, found and fixed 2026-08-05. This read `live_book_usd()` as the numerator and
    `_desk_equity_usd()` as the denominator. `live_book_usd()` IS THE FIRST RUNG INSIDE
    `_desk_equity_usd()` (validation.py:129), so on any box where the NAV chain is readable the
    two calls return the same float and the ratio is IDENTICALLY 1.0 -- not usually, not by
    coincidence, but by construction. Measured on the day it was found: both returned 13151.52
    and this ceiling printed `utilisation 1.0, SATURATED` while `web/cashcarry_live.json` held
    `n_carries: 0, deployed_notional: 0.0`. A book with ZERO POSITIONS reported as fully deployed,
    on the one fence the desk's only idleness law has.

    The comment above in `status` records the previous repair going the WRONG WAY: the two sources
    disagreed ($13,155 vs $4,500), and unifying them removed the disagreement by removing the
    measurement. A ceiling and its own numerator must never share a source -- that is not a
    tightened definition, it is the deletion of the ratio.

    NOW: deployment comes from the executed book, equity from the attestation chain, and a PAPER
    attestation reports UNMEASURED rather than a number -- `molded_curve_usd` is a MOLDED/SIMULATED
    curve by its own `_note`, and utilisation computed from a simulated denominator is exactly the
    "could not measure, counted as satisfied" failure this file exists to refuse. One definition,
    owned by `libs/research/idle_yield.py`; no private copy here (the capacity_policy pattern).
    `check_idle_cost.py` prices the same gap in dollars per day (L1.51).
    """
    try:
        from libs.research.idle_yield import book_state
        bs = book_state()
        eq, book, measured, why = bs.equity_usd, bs.deployed_usd, bs.measurable, bs.why
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        eq, book, measured, why = 0.0, 0.0, False, "libs.research.idle_yield unavailable"
    return Ceiling(
        "deployed_capital", eq, book, "USD", measured,
        "" if (measured and eq > 0 and book >= eq * _EXPECT) else
        f"{why} -- priced per day by scripts/check_idle_cost.py (L1.51)",
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
    reg = _ROOT / "data/data_assets.json"
    try:
        rows = json.loads(reg.read_text("utf-8"))
        rows = rows.get("assets", rows) if isinstance(rows, dict) else rows
        # PRESENT assets only. An asset absent from this box is a COLLECTION question ("is the
        # collector scheduled, is this even the collecting box"), not an idle-capacity one --
        # scoring the two together would blame the desk for not reading a file it never had, and
        # the number would stop meaning anything actionable.
        present = [r for r in rows if (r.get("rows") or r.get("bytes") or r.get("span"))]
        total = float(len(present))
        # THE COLLECTOR IS NOT A CONSUMER. Counting it read 97.8% -- a comfortable number meaning
        # "almost every dataset is used" -- when many of those sole "consumers" were the very
        # script that WRITES the file. A dataset read only by its own collector is precisely the
        # idle asset L1.28a is about: paid for, collected on a cadence, and feeding no research.
        used = float(sum(1 for r in present
                         if [c for c in (r.get("consumers") or [])
                             if Path(str(c)).name != Path(str(r.get("collector") or "")).name]))
        measured = total > 0
    except (OSError, ValueError, AttributeError, TypeError):
        total, used, measured = 0.0, 0.0, False
    return Ceiling(
        "data_assets_read", total, used, "present datasets with a consumer", measured,
        "" if measured and total > 0 and used >= total * _EXPECT else
        "assets present on this box with no consumer -- run scripts/build_data_registry.py and "
        "read the `consumers` column; an absent asset is a collection gap, not an idle one",
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


def _test_suites_runnable() -> Ceiling:
    """Test modules that can actually EXECUTE here, vs modules that skip on a missing dependency.

    A `pytest.importorskip` skip prints one grey line and exits 0, so a suite covering the
    backtest cross-engine, GARCH stationarity, or any other optional-dep path reads as GREEN while
    testing nothing. Measured 2026-07-30: arch, backtrader and vectorbt are all DECLARED in
    pyproject and all absent, so five test modules have been silently inert.

    That is L1.28a exactly -- capability paid for (the tests are written, the deps are chosen) and
    returning zero, with no error to notice. Unmeasured counts as zero, so it belongs on this
    board rather than in a skip line nobody reads.
    """
    import importlib.util
    declared = ("arch", "backtrader", "vectorbt")
    have = [m for m in declared if importlib.util.find_spec(m) is not None]
    return Ceiling(
        "optional_test_deps", float(len(declared)), float(len(have)), "declared deps importable",
        True,
        "" if len(have) >= len(declared) * _EXPECT else
        f"missing {sorted(set(declared) - set(have))} -- their test modules skip silently and "
        "read as green; `pip install -e '.[research]'` on the box that runs CI",
        "A test that skips on a missing dependency prints one grey line and exits 0. The suite "
        "reports green while those paths are untested -- the same 'could not measure counted as "
        "satisfied' failure the Gate 0 board refuses.")


def _brain_seat() -> Ceiling:
    """THE SEAT: how much of the day the desk's ONE serial brain is actually working.

    THE UNMEASURED CEILING (found 2026-07-31 answering "is anything still below max
    frequency"): every claude-invoking organ takes /tmp/quant_brain.lock, and every LOSER
    appends a DEFERRED line to brain_mutex.log -- a complete, free record of contention that
    NOTHING had ever read. So the desk raised and lowered LLM cadences for weeks with no
    measurement of the resource they all compete for: the exact "we are running at 60% and
    that seems fine" defect L1.28a exists to kill, sitting on the desk's scarcest input.

    THE METRIC, and why it is deferrals rather than wall-clock: a deferral is a run the desk
    WANTED and did not get, which is precisely the thing extra cadence is supposed to buy. Two
    readings, both actionable:
      deferral rate LOW  -> the seat has idle windows: RAISE cadences (headroom exists).
      deferral rate HIGH -> the seat is the binding constraint: raising cron changes nothing;
                            only a second seat (the research twin) or shorter runs do.
    Utilisation is reported as attempts-that-ran / attempts-made over the trailing 24h, so
    100% means nothing was ever turned away and lower means real contention. UNMEASURED (no
    log yet, e.g. this container) counts as ZERO by law -- never as healthy."""
    log = _LOGS / "brain_mutex.log"
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    deferred = 0
    try:
        for line in log.read_text("utf-8", errors="ignore").splitlines():
            stamp = line.split(" ", 1)[0]
            try:
                if datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= since:
                    deferred += 1
            except ValueError:
                continue
        measured = True
    except OSError:
        measured = False
    # Attempts = organ fires that reached the mutex. Runs = attempts - deferrals. The daily
    # scheduled claude-organ fire count is the denominator's floor; deferrals add the rest.
    scheduled_fires = 34.0                                  # claude-invoking cron lines/day
    attempts = scheduled_fires + deferred
    ran = attempts - deferred
    return Ceiling(
        "brain_seat_throughput", attempts if measured else scheduled_fires,
        ran if measured else 0.0, "organ runs/24h (vs attempted)", measured,
        "" if (measured and deferred == 0) else
        ("ONE serial brain seat: every deferred organ is a run the desk wanted and did not "
         "get. The resolution path is a SECOND SEAT (research twin, ops/role=research) -- "
         "raising cron cadence cannot add throughput to a saturated mutex"
         if measured else
         "brain_mutex.log absent on this host -- measurable only where organs actually run"),
        "This is the resource EVERY llm cadence competes for. Unmeasured, the desk cannot tell "
        "'raise the cadence' (headroom) from 'buy a second seat' (contention) -- and it has "
        "been raising cadences blind. Deferrals are the only honest signal of which is true.")


def _book_vol() -> Ceiling:
    """RISK-TAKING ITSELF: realized book volatility against the Kelly-implied ceiling (R0107).

    THE CEILING THAT WAS MISSING, and it is the one closest to the objective. Every other
    ceiling here measures an INPUT -- slots, capital, organs, data. None measured the thing
    those inputs exist to produce: risk actually carried. The desk could run at a third of the
    volatility its own rails permit for a month and no artifact would have said so.

    The limit is not a hand-set number. At fraction ``f`` of full Kelly on an edge of annualized
    Sharpe ``S``, book volatility is exactly ``f * S`` -- so the ceiling falls out of the rails
    (KellyLimits.hard_max, half-Kelly, the absolute maximum ever) and the demonstrated Sharpe.
    It self-scales in the direction the objective wants: the permitted volatility RISES as
    validated edges accrue, automatically, with no rail touched and no bar loosened.

    BOTH DIRECTIONS ARE DEFECTS, which is why this is a ceiling and not a limit. Below it with
    no named constraint is L1.28a idleness -- risk the evidence supports and the desk declined.
    Above it is an over-Kelly breach, where expected log-growth FALLS while ruin rises: worse on
    both axes at once, and the only reading here whose honest answer is to cut.

    UNMEASURED TODAY, AND CORRECTLY SO. Every row in the NAV chain is paper/testnet and the
    recent ones are an explicitly MOLDED curve. Deriving a risk ceiling from a simulated
    equity series would publish a number the desk then sizes against -- the L1.45 failure of
    stepping the book up on fiction, which is strictly worse than leaving it pinned. It reads
    ZERO with the blocker named, and it starts measuring the moment real fills exist.
    """
    try:
        from libs.risk.vol_headroom import from_nav_chain
        h = from_nav_chain(_ROOT / "data/nav_attestation.jsonl")
        used, limit, measured, why = (h.realized_vol_ann, h.ceiling_vol_ann, h.measured, h.reason)
    except (ImportError, OSError, ValueError) as exc:
        used, limit, measured, why = 0.0, 0.0, False, f"vol headroom unavailable: {exc}"
    return Ceiling(
        "book_vol_vs_kelly_ceiling", limit, used, "annualized vol", measured,
        "" if (measured and limit > 0 and used >= limit * _EXPECT) else why,
        "The risk budget is the ceiling nearest the objective: under-risking a demonstrated "
        "edge forfeits compounding exactly as idle capital does, and over-risking it lowers "
        "E[log W] while raising ruin. Unmeasured, the desk cannot tell the two apart.")


def collect() -> list[Ceiling]:
    return [_capital(), _forward_slots(), _capability(), _data_assets(), _organs(), _mutation(),
            _test_suites_runnable(), _brain_seat(), _book_vol()]


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
