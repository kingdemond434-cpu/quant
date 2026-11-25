"""THE PRODUCER LOOP -- where each producer's funnel dies, the fixed remedy for that stage, and a
compute weight that follows measured, independent, forward-kept yield.

THE ASK (principal, 2026-11-25; LOOP_COVERAGE row L1). A standing, box-native loop that
diagnoses and improves any producer or generator making zero or few certificates, WITHOUT
OVERFITTING, in plain Python with no model call. It joins organs the desk already has:

    scripts/check_producer_yield.audit()      seat verdicts DEAD / STARVED / PRODUCING
    reports/PRODUCER_CONVERSION.json          per producer: discoveries, candidates, judged,
                                              certificates (certificate_provenance.conversion)
    data/certificate_provenance.json          certificate cell -> the producer that earned it
    reports/shadow/shadow_state.json          the forward clocks (ACTIVE / PROMOTION CANDIDATE
                                              are kept; KILL / IDENTITY_BROKEN are not)
    reports/PRODUCER_YIELD.json               compute hours per producer (7-day window)
    data/hypotheses/gate_verdict_ledger.jsonl which gate killed which cell (gate_verdict_digest
                                              .terminal_of, the judge's own rule)
    data/alpha_registry.sqlite                cell identity -> producer (frontier_identity)
    research/universe_policy                  the exotic and the tradable tests
    libs/research/trial_ledger.census         k_eff, the effective number of independent edges

THE FUNNEL, per producer, lifetime and per day (delta against the snapshot >= 24h old):

    emitted -> compiled -> judged -> certified -> forward-kept

and the STAGE WHERE IT DIES is the first one that is empty after a non-empty one, or CERTIFY
when the producer is a laggard on certificates per candidate, or FORWARD when its forward
keep-rate is below KEEP_FLOOR.

THE FIXED REMEDY MENU (REMEDIES_BY_STAGE below). Five remedies, never a parameter tweak:

    FETCH_PARSE_FIX    the feed/parser is broken           code-level -> CODE_FIX_NEEDED
    PROMPT_MODEL_SWAP  an LLM seat swaps to its DECLARED   config-level (seats only), applied
                       alternative (REPLACEMENTS)
    INSTRUMENT_REMAP   point it at the non-exotic universe config-level, applied
    GRID_WIDEN/NARROW  widen (too few trades) or narrow    code-level: no producer reads a grid
                       (no OOS edge / costs / duplicates)   directive today
    COMPUTE_REWEIGHT   the yield weight below              applied every pass, not an attempt

Config-level remedies are APPLIED by writing the declared prescription file
`data/PRODUCER_PRESCRIPTIONS.json`; no code is edited. A code-level remedy is CODE_FIX_NEEDED
with the producer's owner named, for humans or agents.

THE YIELD METRIC. Certified, tradable, NON-EXOTIC edges born in the last YIELD_WINDOW_D days,
counted as INDEPENDENT edges (k_eff = trial_ledger.census over (symbol, family, asset class)
descriptors -- never a raw count), times the producer's forward keep-rate (the desk's pooled
rate when its own is unmeasured, and said so), per CPU-hour. The weight is that yield over the
median measured yield, clipped to [WEIGHT_MIN, WEIGHT_MAX] -- TWO-SIDED, a weight rises as easily
as it falls; unmeasured is par (1.0). It is published in `data/PRODUCER_WEIGHTS.json` and read by
`merge_hypotheses` (`reweight_rows`), which reorders each family's rows inside that family's own
docket slots before the sealed judge's `allocate_by_yield` takes its family shares. So the
judge's exploration floor (YIELD_MIN_SHARE) is untouched and NO second floor is added; no row
leaves the docket.

CADENCE. Detection (audit, funnel, weights, remedy outcomes) every pass; the per-gate diagnosis
(registry + verdict-ledger scan) daily, unless --force; a remedy round per producer only when
MIN_JUDGED_SINCE_TWEAK of its candidates were judged since its last attempt AND
MIN_DAYS_BETWEEN_ATTEMPTS days passed -- `record_attempt` refuses otherwise.

THE RAILS.
  R1 held-out + forward: `record_attempt` refuses `judged_on` other than "held_out" or
     "forward_shadow"; a remedy is evaluated only on candidates judged AFTER it.
  R2 one trial budget: every attempt's trial ids are charged into the LIFETIME experiment ledger
     (`libs/research/experiment_ledger.lifetime`, the union that sets each cell's deflated-Sharpe
     charge) through ATTEMPTS, joined there as `loop_attempt_trials`. No second budget exists.
  R3 one change at a time, untouched controls: one open remedy per producer (the attempt gate),
     and each attempt freezes a control set of producers with no open remedy; the evaluation is
     a difference-in-differences against them.
  R4 two-sided: the weight goes up as well as down.
  R5 auto-revert: a remedy whose measured rate after (over the minimum sample) is worse than
     before, net of the controls, is REVERTED -- its prescription is withdrawn.
  R6 never touches prop rules, rails or live sizing: this module writes only its own files.
  R7 before/after: every evaluated remedy is published with both rates and the controls'.

NO PRODUCER IS EVER CUT (principal 2026-11-25: every producer kept, breadth kept and growing,
every producer pushed to full depth). After MAX_ATTEMPTS failed remedies the producer is PARKED:
it keeps producing at the WEIGHT_MIN floor share (never 0, so it is still judged and can earn its
way back), remedy rounds pause so the loop cannot overfit it, its funnel history and attempts are
archived to `data/producer_loop_archive/<producer>.json` (never deleted), and a re-test date is
set RETEST_AFTER_DAYS ahead; on that date its attempt count restarts.

A MISSING INPUT IS UNMEASURED, NEVER ZERO (L1.28a).

    python desks/mt5/research/producer_loop.py            # every-pass build
    python desks/mt5/research/producer_loop.py --force    # recompute the diagnosis now
    python desks/mt5/research/producer_loop.py --record-attempt NAME --remedy GRID_NARROW \
        --trial-id T1 --judged-on held_out [--family FAM]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "PRODUCER_LOOP.json"
LEDGER = DESK / "data" / "producer_loop_ledger.jsonl"
#: The attempt ledger: appended to ONLY by `record_attempt`; joined by experiment_ledger (R2).
ATTEMPTS = DESK / "data" / "producer_loop_attempts.jsonl"
STATE = DESK / "data" / "producer_loop_state.json"
ARCHIVE = DESK / "data" / "producer_loop_archive"
WEIGHTS = DESK / "data" / "PRODUCER_WEIGHTS.json"
PRESCRIPTIONS = DESK / "data" / "PRODUCER_PRESCRIPTIONS.json"

CONVERSION = DESK / "reports" / "PRODUCER_CONVERSION.json"
PROVENANCE = DESK / "data" / "certificate_provenance.json"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
YIELD_REPORT = DESK / "reports" / "PRODUCER_YIELD.json"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"
YIELD_SCRIPT = ROOT / "scripts" / "check_producer_yield.py"

UNMEASURED = "UNMEASURED"

#: Failed remedies before a producer is parked; also the cap on attempts per cycle.
MAX_ATTEMPTS = 3
#: THE MINIMUM SAMPLE. A remedy is read on the candidates judged AFTER it; below about two hundred
#: judged cells a certificate rate of the desk's order (~1e-3 to 1e-2) cannot tell "the fix did
#: nothing" from "not yet asked", so a next remedy would be chasing noise.
MIN_JUDGED_SINCE_TWEAK = 200
#: ... and a week of wall clock, so one burst of judging cannot license a round of remedies.
MIN_DAYS_BETWEEN_ATTEMPTS = 7.0
#: The diagnosis scan is recomputed at most daily.
DIAGNOSIS_MAX_AGE_H = 24.0
#: Parked producers get fresh remedy rounds a month later.
RETEST_AFTER_DAYS = 30
#: A laggard sits below this fraction of the desk's pooled certificates per candidate.
LAGGARD_FRACTION = 0.25
#: Below this many candidates a rate is not a measurement.
MIN_CANDIDATES = MIN_JUDGED_SINCE_TWEAK
#: A forward keep-rate below this is where the funnel dies (FORWARD).
KEEP_FLOOR = 0.5
#: Certificates born inside this window count toward yield; compute is the 7-day measured rate
#: scaled to the same window.
YIELD_WINDOW_D = 30.0
COMPUTE_WINDOW_D = 7.0
#: The two-sided weight's clip; unmeasured is par.
WEIGHT_MIN, WEIGHT_MAX = 0.25, 4.0
#: Bounds of the daily scan, for the 8 GB build box.
MAX_SCAN_ROWS = 1_000_000
SAMPLE_CELLS_PER_PRODUCER = 5_000
MAX_CONTROLS = 20
DEFAULT_BUDGET_S = 420.0

JUDGED_ON_ALLOWED = ("held_out", "forward_shadow")
KEPT_CLOCK = frozenset({"ACTIVE", "PROMOTION CANDIDATE"})
KILLED_CLOCK = frozenset({"KILL", "IDENTITY_BROKEN"})

# ----------------------------------------------------------------------------- the funnel stages

STAGES = ("EMIT", "COMPILE", "JUDGE", "CERTIFY", "FORWARD")

# ----------------------------------------------------------------------- the kill-class table

DEAD_DATA = "DEAD_DATA"
COSTS = "COSTS"
EXOTIC_UNIVERSE = "EXOTIC_UNIVERSE"
NO_OOS_EDGE = "NO_OOS_EDGE"
DUPLICATE = "DUPLICATE"
TOO_FEW_TRADES = "TOO_FEW_TRADES"
UNMAPPED = "UNMAPPED"
#: Not kills: a pass, and a cell the judge has not yet built (budget/queue).
PASSED = "PASSED"
PENDING = "PENDING"
KILL_CLASSES = (DEAD_DATA, COSTS, EXOTIC_UNIVERSE, NO_OOS_EDGE, DUPLICATE, TOO_FEW_TRADES,
                UNMAPPED)

#: THE EXPLICIT MAPPING: terminal gate id (gate_verdict_digest.terminal_of), UNMEASURED reason or
#: NOT_RUN status -> kill class. Anything absent is UNMAPPED -- counted and named, never dropped.
KILL_CLASS_BY_GATE: dict[str, str] = {
    # dead or broken data: no bars, a build that cannot run, a spec the builder refuses, a signal
    # that never fires (zero trades: the input is absent on the judge's side, judge_source_floor)
    "NOT_RUN_DATA_MISSING": DEAD_DATA, "NOT_RUN_BUILD_FAILED": DEAD_DATA,
    "NOT_RUN_MODIFIER": DEAD_DATA, "no_trades": DEAD_DATA, "short_history_after_cut": DEAD_DATA,
    "no_terminal_gate_recorded": DEAD_DATA,
    # costs (a cost kill on an exotic symbol is counted EXOTIC_UNIVERSE, see kill_class)
    "stress_costs": COSTS, "swap_cost": COSTS,
    # the universe
    "symbol_eligibility": EXOTIC_UNIVERSE, "NOT_RUN_UNTRADEABLE_SYMBOL": EXOTIC_UNIVERSE,
    # no (out-of-sample) edge: the screen, the multiplicity charge and every held-out gate
    "in_sample_screen": NO_OOS_EDGE, "expected_value": NO_OOS_EDGE,
    "deflated_sharpe": NO_OOS_EDGE, "walk_forward": NO_OOS_EDGE, "cpcv": NO_OOS_EDGE,
    "lockbox": NO_OOS_EDGE, "reality_check_spa": NO_OOS_EDGE, "economic_prior": NO_OOS_EDGE,
    # too few trades to rule
    "too_rare": TOO_FEW_TRADES, "lockbox_consumed_history": TOO_FEW_TRADES,
    "observations_under_60_days": TOO_FEW_TRADES, "observations": TOO_FEW_TRADES,
    # not kills
    "PASSED": PASSED, "NOT_RUN_BUILD_BUDGET_DEFERRED": PENDING, "NOT_RUN_BUILD_BUDGET": PENDING,
    "NOT_RUN_QUEUED": PENDING, "NOT_RUN_MEMORY_BUDGET": PENDING,
}
#: DUPLICATE has no judge gate: the registry scan counts a candidate whose exact cell identity an
#: earlier row already holds. Exotic candidates are set aside BEFORE the judge (merge_hypotheses
#: -> judge_exotic_exclusion), so they are counted from the producer's own symbols.

# --------------------------------------------------------------------------- the remedy menu

FETCH_PARSE_FIX = "FETCH_PARSE_FIX"
PROMPT_MODEL_SWAP = "PROMPT_MODEL_SWAP"
INSTRUMENT_REMAP = "INSTRUMENT_REMAP"
GRID_WIDEN = "GRID_WIDEN"
GRID_NARROW = "GRID_NARROW"
COMPUTE_REWEIGHT = "COMPUTE_REWEIGHT"
REMEDIES = (FETCH_PARSE_FIX, PROMPT_MODEL_SWAP, INSTRUMENT_REMAP, GRID_WIDEN, GRID_NARROW,
            COMPUTE_REWEIGHT)
#: remedy -> config-level (applied here by a declared prescription) or code-level.
CONFIG_LEVEL: dict[str, bool] = {
    FETCH_PARSE_FIX: False, PROMPT_MODEL_SWAP: True, INSTRUMENT_REMAP: True,
    GRID_WIDEN: False, GRID_NARROW: False, COMPUTE_REWEIGHT: True,
}
#: THE DOCUMENTED TABLE: stage of death -> the remedies that may treat it, in preference order.
REMEDIES_BY_STAGE: dict[str, tuple[str, ...]] = {
    "EMIT": (PROMPT_MODEL_SWAP, FETCH_PARSE_FIX),       # nothing emitted: swap a seat or fix it
    "COMPILE": (FETCH_PARSE_FIX,),                      # emitted rows that compile to nothing
    "JUDGE": (INSTRUMENT_REMAP, COMPUTE_REWEIGHT),      # compiled but never judged (set aside)
    "CERTIFY": (FETCH_PARSE_FIX, INSTRUMENT_REMAP, GRID_WIDEN, GRID_NARROW),
    "FORWARD": (COMPUTE_REWEIGHT, GRID_NARROW),         # certified, then killed forward
}
#: Inside CERTIFY, the dominant kill class picks the remedy.
REMEDY_BY_KILL_CLASS: dict[str, tuple[str, str]] = {
    DEAD_DATA: (FETCH_PARSE_FIX, "its cells never build or never fire: the feed or parser is "
                                 "broken"),
    EXOTIC_UNIVERSE: (INSTRUMENT_REMAP, "its cells die on exotic symbols: re-map to the "
                                        "non-exotic universe"),
    COSTS: (GRID_NARROW, "its edge does not survive costs: narrow to horizons/states where the "
                         "move pays the spread, on economic grounds"),
    NO_OOS_EDGE: (GRID_NARROW, "no out-of-sample edge: narrow the search to a stated economic "
                               "mechanism instead of a grid"),
    TOO_FEW_TRADES: (GRID_WIDEN, "too few trades to rule: widen the conditioning or horizon on "
                                 "economic grounds"),
    DUPLICATE: (GRID_NARROW, "it re-mints cells that already exist: narrow off covered ground"),
}


def kill_class(gate_id: str, symbol: str | None = None) -> str:
    """The kill class of one terminal gate id / reason / status. Unknown -> UNMAPPED."""
    k = KILL_CLASS_BY_GATE.get(str(gate_id or ""), UNMAPPED)
    if k == COSTS and symbol and _is_exotic(symbol):
        return EXOTIC_UNIVERSE
    return k


def classify(row: dict[str, Any]) -> str:
    """Kill class of one verdict-ledger row, through the judge's own terminal rule."""
    try:
        from research.gate_verdict_digest import terminal_of
        kind, gid, reason = terminal_of(row)
    except Exception:
        kind, gid, reason = "DEFECT", "no_terminal_gate_recorded", ""
    sym = symbol_of(str(row.get("cell") or ""))
    if kind == "UNMEASURED":
        return kill_class(str(reason).split(":", 1)[0].strip() or gid, sym)
    if kind == "DEFECT":
        # A legacy unstamped row still names its downstream status; read it before UNMAPPED.
        return kill_class(str(row.get("downstream_status") or "") or gid, sym)
    return kill_class(gid, sym)


def symbol_of(cell: str) -> str:
    """`<sym>[@TF].<family>.p=<digest>` -> sym."""
    head = cell.rsplit(".", 2)[0] if cell.count(".") >= 2 else cell
    return head.split("@", 1)[0]


def family_of(cell: str) -> str:
    parts = cell.rsplit(".", 2)
    return parts[1] if len(parts) == 3 else ""


def _is_exotic(symbol: str) -> bool:
    try:
        from research.universe_policy import is_exotic_symbol
        return bool(is_exotic_symbol(symbol))
    except Exception:
        return False


def _tradable(symbol: str, family: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol, family))
    except Exception:
        return False


# ------------------------------------------------------------------------------------ io helpers

def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")


def _norm(name: Any) -> str:
    try:
        from libs.research.attribution import normalise_producer
        return normalise_producer(name) or ""
    except Exception:
        return str(name or "").strip().lower()


def _int(v: Any) -> int | None:
    return int(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


# -------------------------------------------------------------------------------- attempt ledger

def attempts(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """producer -> its recorded attempts, oldest first."""
    out: dict[str, list[dict[str, Any]]] = {}
    try:
        lines = (path or ATTEMPTS).read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("producer"):
            out.setdefault(str(r["producer"]), []).append(r)
    return out


def _cycle(prior: list[dict[str, Any]], retest_at: Any) -> list[dict[str, Any]]:
    """The attempts of the current cycle: those after the last re-test date, once it passed."""
    t = _parse(retest_at)
    if t is None:
        return prior
    return [a for a in prior if (_parse(a.get("at")) or t) > t]


def attempt_gate(producer: str, *, judged_now: int | None, now: datetime | None = None,
                 history: dict[str, list[dict[str, Any]]] | None = None,
                 retest_at: Any = None) -> tuple[bool, str]:
    """(allowed, why) for a NEW remedy round on `producer` (see the module doc)."""
    now = now or _now()
    rt = _parse(retest_at)
    if rt is not None and now < rt:
        return False, f"parked: re-test date {retest_at} not reached"
    prior = _cycle((history if history is not None else attempts()).get(producer, []),
                   retest_at)
    if len(prior) >= MAX_ATTEMPTS:
        return False, (f"{len(prior)} of MAX_ATTEMPTS={MAX_ATTEMPTS} attempts used: tuning has "
                       f"paused; the producer is parked at the floor weight until its re-test date")
    if not prior:
        return True, "first attempt"
    last = prior[-1]
    at = _parse(last.get("at"))
    if at is None or (now - at) < timedelta(days=MIN_DAYS_BETWEEN_ATTEMPTS):
        return False, (f"last attempt at {last.get('at')}: fewer than "
                       f"{MIN_DAYS_BETWEEN_ATTEMPTS:g} days have passed")
    base = _int(last.get("judged_at_attempt"))
    if judged_now is None or base is None:
        return False, (f"{UNMEASURED}: judged count since the last attempt cannot be read, so the "
                       f"minimum sample of {MIN_JUDGED_SINCE_TWEAK} is unproven")
    if judged_now - base < MIN_JUDGED_SINCE_TWEAK:
        return False, (f"{judged_now - base} candidate(s) judged since the last attempt, below "
                       f"the minimum sample MIN_JUDGED_SINCE_TWEAK={MIN_JUDGED_SINCE_TWEAK}")
    return True, f"{judged_now - base} judged since the last attempt"


def _conversion_rows(doc: Any = None) -> dict[str, dict[str, Any]]:
    doc = doc if doc is not None else _read(CONVERSION, None)
    if not isinstance(doc, dict):
        return {}
    return {_norm(r.get("producer")): r for r in doc.get("producers") or []
            if isinstance(r, dict) and r.get("producer")}


def record_attempt(producer: str, remedy: str, trial_ids: list[str], judged_on: str, *,
                   family: str | None = None, judged_now: int | None = None,
                   certificates_now: int | None = None, controls: dict[str, Any] | None = None,
                   retest_at: Any = None, now: datetime | None = None,
                   path: Path | None = None) -> dict[str, Any]:
    """Record one remedy attempt, or REFUSE it. Returns {"recorded": bool, "why": str, "row"?}.

    Refused when `judged_on` is not held-out or forward shadow (R1), when `remedy` is not on the
    fixed menu, when there are no trial ids to charge (R2), when MAX_ATTEMPTS is used, or when
    the last attempt has not had its sample (MIN_JUDGED_SINCE_TWEAK judged AND
    MIN_DAYS_BETWEEN_ATTEMPTS days) -- one change at a time (R3)."""
    path = path or ATTEMPTS
    now = now or _now()
    producer = str(producer)
    if judged_on not in JUDGED_ON_ALLOWED:
        return {"recorded": False, "why": (f"judged_on={judged_on!r} refused: a remedy is judged "
                                           f"only on {' or '.join(JUDGED_ON_ALLOWED)}")}
    if remedy not in REMEDIES or remedy == COMPUTE_REWEIGHT:
        return {"recorded": False, "why": (f"remedy={remedy!r} is not an attempt on the fixed "
                                           f"menu {REMEDIES[:-1]}; parameter tweaks are refused "
                                           f"and the compute weight is derived every pass")}
    ids = [str(t) for t in trial_ids or [] if str(t)]
    if not ids:
        return {"recorded": False, "why": "no trial ids: an attempt that charges no trial is "
                                          "refused (one shared trial budget)"}
    if judged_now is None or certificates_now is None:
        row = _conversion_rows().get(_norm(producer))
        if row is not None:
            judged_now = judged_now if judged_now is not None else _int(row.get("judged"))
            certificates_now = (certificates_now if certificates_now is not None
                                else _int(row.get("certificates")))
    hist = attempts(path)
    ok, why = attempt_gate(producer, judged_now=judged_now, now=now, history=hist,
                           retest_at=retest_at)
    if not ok:
        return {"recorded": False, "why": why}
    rec = {"producer": producer, "remedy": remedy, "trial_ids": ids, "n_trials": len(ids),
           "family": family or f"producer_loop:{producer}", "judged_on": judged_on,
           "at": _iso(now), "attempt": len(_cycle(hist.get(producer, []), retest_at)) + 1,
           "max_attempts": MAX_ATTEMPTS, "judged_at_attempt": judged_now,
           "certificates_at_attempt": certificates_now, "controls": controls or {}}
    _append(path, [rec])
    return {"recorded": True, "why": why, "row": rec}


def loop_trial_counts(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """(trials, per family) charged by recorded attempts -- what experiment_ledger joins (R2)."""
    total, by_fam = 0, Counter()
    for rows in attempts(path).values():
        for r in rows:
            n = len(r.get("trial_ids") or [])
            total += n
            by_fam[str(r.get("family") or "producer_loop")] += n
    return total, dict(by_fam)


def evaluate(att: dict[str, Any], judged_now: int | None, certs_now: int | None,
             conv: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """R3/R5/R7: the attempt's before/after against its frozen controls, or None until sampled."""
    jb, cb = _int(att.get("judged_at_attempt")), _int(att.get("certificates_at_attempt"))
    at = _parse(att.get("at"))
    if None in (jb, cb, judged_now, certs_now) or at is None:
        return None
    assert jb is not None and cb is not None and judged_now is not None and certs_now is not None
    if judged_now - jb < MIN_JUDGED_SINCE_TWEAK or now - at < timedelta(
            days=MIN_DAYS_BETWEEN_ATTEMPTS):
        return None
    before = cb / jb if jb else 0.0
    after = (certs_now - cb) / (judged_now - jb)
    ctl = att.get("controls") or {}
    cj0, cc0 = _int(ctl.get("judged")), _int(ctl.get("certificates"))
    names = ctl.get("producers") or []
    cj1 = sum(_int((conv.get(n) or {}).get("judged")) or 0 for n in names)
    cc1 = sum(_int((conv.get(n) or {}).get("certificates")) or 0 for n in names)
    ctl_delta = None
    if cj0 and cj1 - cj0 > 0 and cc0 is not None:
        ctl_delta = (cc1 - cc0) / (cj1 - cj0) - cc0 / cj0
    net = (after - before) - (ctl_delta or 0.0)
    outcome = ("SUCCEEDED" if certs_now > cb and net > 0
               else "FAILED_REVERTED" if net < 0 else "FAILED")
    return {"attempt": att.get("attempt"), "remedy": att.get("remedy"), "at": att.get("at"),
            "evaluated_at": _iso(now), "before_certs_per_judged": round(before, 8),
            "after_certs_per_judged": round(after, 8),
            "controls_delta": round(ctl_delta, 8) if ctl_delta is not None else UNMEASURED,
            "net_effect": round(net, 8), "outcome": outcome}


# ------------------------------------------------------------------------- weights in the docket

def producer_weights(path: Path | None = None) -> dict[str, float]:
    doc = _read(path or WEIGHTS, {}) or {}
    out: dict[str, float] = {}
    for k, v in ((doc.get("producers") or {}) if isinstance(doc, dict) else {}).items():
        w = v.get("weight") if isinstance(v, dict) else v
        if isinstance(w, int | float):
            out[_norm(k)] = float(w)
    return out


def _flagged(r: Any) -> bool:
    """True when the row carries Tier-S pre-judge flags (libs/tiers/prejudge_screen tags it)."""
    v = r.get("prejudge") if isinstance(r, dict) else None
    return bool(isinstance(v, dict) and v.get("flags"))


def reweight_rows(rows: list[dict[str, Any]], weights: dict[str, float] | None = None
                  ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Family-slot preserving reorder by producer weight (the prejudge_screen rule): each family
    keeps the SAME docket positions; within them clean rows precede pre-judge-flagged rows, and
    inside each group rows go by weight, highest first, stably. The
    docket's length, membership and family interleave are unchanged; no row is removed, so the
    sealed judge's per-family shares and exploration floor are untouched."""
    w = weights if weights is not None else producer_weights()
    if not w or not rows:
        return rows, {"weighted_producers": len(w), "moved": 0}

    def weight(r: Any) -> float:
        if not isinstance(r, dict):
            return 1.0
        for k in ("producer", "source", "generator"):
            n = _norm(r.get(k)) if r.get(k) else ""
            if n in w:
                return w[n]
        return 1.0

    ws = [weight(r) for r in rows]
    slots: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        slots.setdefault(str(r.get("family") or "") if isinstance(r, dict) else "", []).append(i)
    out = list(rows)
    moved = 0
    for idxs in slots.values():
        # (flagged, -weight): a row the Tier-S pre-judge screen flagged stays behind every clean
        # row of its family whatever its producer's weight (layers 9/21 are never undone).
        order = sorted(idxs, key=lambda i: (_flagged(rows[i]), -ws[i]))
        for slot, src in zip(idxs, order, strict=True):
            out[slot] = rows[src]
            moved += int(slot != src)
    return out, {"weighted_producers": len(w), "rows_reweighted": sum(1 for x in ws if x != 1.0),
                 "moved": moved, "rule": "rows ordered by producer weight inside their own "
                                         "family's slots; no row is removed"}


# ---------------------------------------------------------------------- the daily diagnosis scan

def diagnose(*, db: Path | None = None, verdicts: Path | None = None,
             deadline: float | None = None) -> dict[str, Any]:
    """Per producer: the kill-class histogram over its sampled cells, exotic and duplicate counts.

    Two bounded passes: the newest MAX_SCAN_ROWS registry candidates (cell identity -> producer,
    duplicates, exotics), then one stream of the verdict ledger keeping each sampled cell's
    LATEST terminal (the ledger appends on every change of mind)."""
    db = db or REGISTRY
    verdicts = verdicts or VERDICTS
    out: dict[str, Any] = {"available": False, "at": _iso(_now())}
    if not db.exists():
        out["why"] = f"{UNMEASURED}: no registry at {db.as_posix()}"
        return out
    if not verdicts.exists():
        out["why"] = f"{UNMEASURED}: no verdict ledger at {verdicts.as_posix()}"
        return out
    try:
        from research.frontier_identity import cell_id
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: no cell identity ({type(exc).__name__})"
        return out
    per: dict[str, dict[str, Any]] = {}
    cell_owner: dict[str, set[str]] = {}
    seen: set[int] = set()
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            top = con.execute("SELECT max(rowid) FROM research_candidates").fetchone()[0] or 0
            cur = con.execute(
                "SELECT symbol, family, params_json, coalesce(producer,'') FROM "
                "research_candidates WHERE rowid > ? ORDER BY rowid", (top - MAX_SCAN_ROWS,))
            for n, (sym, fam, pj, who) in enumerate(cur, 1):
                if deadline is not None and n % 50_000 == 0 and time.monotonic() > deadline:
                    out["why"] = f"{UNMEASURED}: scan budget ran out after {n} candidates"
                    return out
                name = _norm(who)
                if not name or not sym or not fam:
                    continue
                try:
                    params = json.loads(pj) if pj else {}
                except ValueError:
                    params = {}
                try:
                    key = cell_id({"sym": sym, "family": fam,
                                   "params": params if isinstance(params, dict) else {}})
                except (KeyError, TypeError, ValueError):
                    continue
                p = per.setdefault(name, {"scanned": 0, "duplicates": 0, "exotic": 0,
                                          "families": Counter(), "cells": 0})
                p["scanned"] += 1
                p["families"][str(fam)] += 1
                h = hash(key)
                if h in seen:
                    p["duplicates"] += 1
                    continue
                seen.add(h)
                if _is_exotic(str(sym)):
                    p["exotic"] += 1
                    continue          # set aside before the judge: never gets a verdict
                if p["cells"] < SAMPLE_CELLS_PER_PRODUCER:
                    p["cells"] += 1
                    cell_owner.setdefault(key, set()).add(name)
        finally:
            con.close()
    except sqlite3.Error as exc:
        out["why"] = f"{UNMEASURED}: registry unreadable ({type(exc).__name__}: {exc})"
        return out
    seen.clear()
    last: dict[str, str] = {}
    try:
        with verdicts.open(encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if deadline is not None and n % 200_000 == 0 and time.monotonic() > deadline:
                    out["why"] = f"{UNMEASURED}: ledger budget ran out after {n} rows"
                    return out
                if '"cell"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                c = str(r.get("cell") or "") if isinstance(r, dict) else ""
                if c in cell_owner:
                    last[c] = classify(r)
    except OSError as exc:
        out["why"] = f"{UNMEASURED}: verdict ledger unreadable ({exc})"
        return out
    hists: dict[str, Counter[str]] = {n: Counter() for n in per}
    for c, owners in cell_owner.items():
        if c in last:
            for name in owners:
                hists[name][last[c]] += 1
    producers: dict[str, Any] = {}
    for name, p in per.items():
        hist = hists[name]
        with_verdict = sum(hist.values())
        hist[DUPLICATE] += p["duplicates"]
        hist[EXOTIC_UNIVERSE] += p["exotic"]
        producers[name] = {"scanned": p["scanned"], "cells_sampled": p["cells"],
                           "cells_with_verdict": with_verdict,
                           "exotic_share": round(p["exotic"] / p["scanned"], 4),
                           "histogram": {k: v for k, v in hist.items() if v},
                           "dominant_family": (p["families"].most_common(1)[0][0]
                                               if p["families"] else None)}
    out.update({"available": True, "producers": producers,
                "registry_rows_scanned_max": MAX_SCAN_ROWS,
                "sample_cells_per_producer": SAMPLE_CELLS_PER_PRODUCER})
    return out


# ------------------------------------------------------------------------- forward and yield

def forward_kept(shadow: Any = None) -> dict[tuple[str, str], str] | None:
    """(symbol, family) -> KEPT / KILLED from the forward clocks; None when unreadable."""
    doc = shadow if shadow is not None else _read(SHADOW, None)
    if not isinstance(doc, dict):
        return None
    out: dict[tuple[str, str], str] = {}
    for key, v in doc.items():
        if not isinstance(v, dict) or "status" not in v or key.count(".") < 2:
            continue
        sym, fam = key.split(".", 2)[:2]
        st = str(v.get("status") or "")
        k = (sym.split("@", 1)[0], fam)
        if st in KEPT_CLOCK:
            out[k] = "KEPT"
        elif st in KILLED_CLOCK:
            out.setdefault(k, "KILLED")
    return out


def k_eff(cells: list[str]) -> float:
    """Effective number of independent edges among certified cells: the desk's trial-ledger
    census (participation ratio of descriptor similarity; distinct families independent)."""
    if not cells:
        return 0.0
    try:
        from libs.research import trial_ledger as tl
        trials = []
        for c in cells:
            sym, fam = symbol_of(c), family_of(c)
            try:
                from research.universe_policy import peer_class
                klass = str(peer_class(sym) or "")
            except Exception:
                klass = ""
            trials.append(tl.Trial(c, fam or "?", {"symbol": sym, "class": klass}, {}))
        return float(tl.census(trials).n_effective)
    except Exception:
        # The census itself failed: distinct cells is the conservative ceiling (it can only
        # over-credit breadth, never invent an edge), and the trial-ledger import is pinned by
        # the tests so this branch is an outage, not a mode.
        return float(len(set(cells)))


def certificates_by_producer(prov: Any = None) -> dict[str, list[dict[str, Any]]] | None:
    doc = prov if prov is not None else _read(PROVENANCE, None)
    if not isinstance(doc, dict):
        return None
    recs = doc.get("records") or {}
    items = recs.values() if isinstance(recs, dict) else recs
    out: dict[str, list[dict[str, Any]]] = {}
    for r in items:
        if isinstance(r, dict) and r.get("producer") and r.get("cell"):
            out.setdefault(_norm(r["producer"]), []).append(r)
    return out


def compute_hours(doc: Any = None) -> dict[str, float]:
    doc = doc if doc is not None else _read(YIELD_REPORT, None)
    rows = ((doc or {}).get("cells_owed") or {}).get("producers") if isinstance(doc, dict) else []
    out: dict[str, float] = {}
    for r in rows or []:
        h = r.get("compute_hours_window7d") if isinstance(r, dict) else None
        if isinstance(h, int | float):
            out[_norm(r.get("producer"))] = float(h)
    return out


# --------------------------------------------------------------------------------- the funnel

def stage_of_death(f: dict[str, Any], *, laggard: bool, dead: bool) -> str | None:
    """The first empty stage after a non-empty one; CERTIFY for a laggard; FORWARD below
    KEEP_FLOOR. UNMEASURED stages are skipped, never read as zero."""
    if dead:
        return "EMIT"
    order = (("EMIT", "emitted"), ("COMPILE", "compiled"), ("JUDGE", "judged"),
             ("CERTIFY", "certified"))
    for stage, key in order:
        v = f.get(key)
        if isinstance(v, int) and v == 0:
            return stage
    if laggard:
        return "CERTIFY"
    kr = f.get("forward_keep_rate")
    if isinstance(kr, float) and kr < KEEP_FLOOR:
        return "FORWARD"
    return None


def choose_remedy(stage: str | None, hist: dict[str, int] | None, *, replacement: str | None,
                  is_seat: bool, exotic_share: float | None) -> dict[str, Any]:
    """The remedy from the fixed menu for the stage of death (REMEDIES_BY_STAGE)."""
    if stage is None:
        return {"remedy": None, "reason": "the funnel does not die"}
    if stage == "EMIT":
        if is_seat and replacement:
            return {"remedy": PROMPT_MODEL_SWAP, "replacement": replacement,
                    "reason": f"the seat emits nothing: swap to its declared alternative "
                              f"{replacement}"}
        return {"remedy": FETCH_PARSE_FIX, "reason": "emits nothing and has no declared "
                                                     "alternative: fetch/parse fix"}
    if stage == "COMPILE":
        return {"remedy": FETCH_PARSE_FIX, "reason": "emits rows that compile to no cell"}
    if stage == "JUDGE":
        if exotic_share is not None and exotic_share >= 0.5:
            return {"remedy": INSTRUMENT_REMAP, "reason": f"{exotic_share:.0%} of its cells are "
                                                          f"exotic and set aside before the "
                                                          f"judge"}
        return {"remedy": COMPUTE_REWEIGHT, "reason": "compiled cells not reaching the judge: "
                                                      "its weight is set from measured yield"}
    if stage == "FORWARD":
        return {"remedy": COMPUTE_REWEIGHT, "reason": "certified edges are killed forward: the "
                                                      "keep-rate already lowers its weight"}
    kills = {k: v for k, v in (hist or {}).items() if k in KILL_CLASSES and v}
    if not kills:
        return {"remedy": None, "reason": f"{UNMEASURED}: no per-gate diagnosis yet"}
    dom = sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    if dom == UNMAPPED:
        return {"remedy": None, "dominant_kill_class": dom,
                "reason": "the dominant terminal is not in KILL_CLASS_BY_GATE: extend the table"}
    rem, why = REMEDY_BY_KILL_CLASS[dom]
    return {"remedy": rem, "dominant_kill_class": dom, "reason": why}


def _dead_audit() -> dict[str, Any]:
    """check_producer_yield.audit(), live; the published report when the import fails."""
    try:
        spec = importlib.util.spec_from_file_location("_cpy_for_producer_loop", YIELD_SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError("no spec")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        doc = mod.audit()
        doc["replacements"] = dict(getattr(mod, "REPLACEMENTS", {}))
        doc["source"] = "check_producer_yield.audit() (live)"
        return doc
    except Exception as exc:
        doc = _read(YIELD_REPORT, None)
        if not isinstance(doc, dict):
            return {"why": f"{UNMEASURED}: audit failed ({type(exc).__name__}) and no "
                           f"PRODUCER_YIELD"}
        doc["source"] = f"PRODUCER_YIELD.json (audit import failed: {type(exc).__name__})"
        return doc


def _target(text: Any) -> str:
    head = str(text or "").split("--", 1)[0].strip()
    return "" if not head or head.upper().startswith("NONE") else head.split()[0].strip(";,")


def _owners() -> dict[str, str]:
    blob = _read(BLOCKERS, {}) or {}
    rows = blob.get("blockers", blob) if isinstance(blob, dict) else blob
    if isinstance(rows, dict):
        items = list(rows.items())
    elif isinstance(rows, list):
        items = [(r.get("producer"), r) for r in rows if isinstance(r, dict)]
    else:
        items = []
    return {_norm(k): str(v.get("owner") or v.get("by")) for k, v in items
            if k and isinstance(v, dict) and (v.get("owner") or v.get("by"))}


def _archive(name: str, row: dict[str, Any], prior: list[dict[str, Any]],
             outcomes: list[dict[str, Any]], retest_at: str) -> str:
    """Write the producer's funnel history and attempts to its archive JSON. Never deletes: a
    second retirement appends to the same file's `retirements` list."""
    path = ARCHIVE / f"{name.replace(':', '_').replace('/', '_')}.json"
    doc = _read(path, {}) or {}
    history: list[dict[str, Any]] = []
    try:
        for ln in LEDGER.read_text("utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("producer") == name:
                history.append(r)
    except OSError:
        pass
    doc.setdefault("producer", name)
    doc.setdefault("retirements", []).append({
        "retired_at": row.get("generated_at"), "retest_at": retest_at, "funnel": row.get("funnel"),
        "attempts": prior, "outcomes": outcomes, "funnel_history": history})
    _atomic(path, doc)
    return path.relative_to(DESK).as_posix()


def build(*, force: bool = False, now: datetime | None = None, budget_s: float | None = None,
          apply: bool = True) -> dict[str, Any]:
    """The loop document. Diagnosis from cache unless stale (>= DIAGNOSIS_MAX_AGE_H) or force."""
    now = now or _now()
    t0 = time.monotonic()
    budget = float(budget_s if budget_s is not None
                   else os.environ.get("QUANT_LEG_BUDGET_S") or DEFAULT_BUDGET_S)
    state = _read(STATE, {}) or {}
    cached = state.get("diagnosis") if isinstance(state.get("diagnosis"), dict) else None
    built_at = _parse((cached or {}).get("at"))
    fresh = bool(cached and built_at and (now - built_at) < timedelta(hours=DIAGNOSIS_MAX_AGE_H))
    if force or not fresh:
        diag = diagnose(deadline=t0 + budget * 0.85)
        diag["at"] = _iso(now)
        recomputed = True
    else:
        diag, recomputed = cached or {}, False

    audit = _dead_audit()
    verdict_of = {_norm(r.get("producer")): r for r in audit.get("producers") or []
                  if isinstance(r, dict)}
    repl = audit.get("replacements") or {}
    conv = _conversion_rows()
    certs_of = certificates_by_producer()
    clocks = forward_kept()
    cpu = compute_hours()
    hist_all = attempts()
    owners = _owners()
    diag_p = (diag.get("producers") or {}) if diag.get("available") else {}
    retired: dict[str, Any] = dict(state.get("retired") or {})
    outcomes: dict[str, list[dict[str, Any]]] = {k: list(v) for k, v in
                                                 (state.get("outcomes") or {}).items()}
    prescriptions = dict((_read(PRESCRIPTIONS, {}) or {}).get("producers") or {})
    snaps = state.get("snapshots") or {}

    tot_c = sum(_int(r.get("candidates")) or 0 for r in conv.values())
    tot_k = sum(_int(r.get("certificates")) or 0 for r in conv.values())
    desk_rate = (tot_k / tot_c) if tot_c else None
    # The desk's pooled keep-rate: the prior for a producer whose own certificates have no clock.
    pooled = Counter()
    if certs_of is not None and clocks is not None:
        for recs in certs_of.values():
            for rec in recs:
                c = str(rec["cell"])
                st = clocks.get((symbol_of(c), family_of(c)))
                if st:
                    pooled[st] += 1
    desk_keep = (pooled["KEPT"] / (pooled["KEPT"] + pooled["KILLED"])
                 if pooled["KEPT"] + pooled["KILLED"] else None)
    window_start = now - timedelta(days=YIELD_WINDOW_D)
    open_remedy = {n for n, a in hist_all.items()
                   if a and not any(o.get("attempt") == a[-1].get("attempt")
                                    for o in outcomes.get(n, []))}

    names = sorted(set(conv) | set(verdict_of) | set(hist_all) | set(diag_p)
                   | set(certs_of or {}))
    rows: list[dict[str, Any]] = []
    for name in names:
        c = conv.get(name)
        av = verdict_of.get(name) or {}
        dg = diag_p.get(name)
        hist = dict(dg["histogram"]) if dg else None
        cand = _int(c.get("candidates")) if c else None
        judged = _int(c.get("judged")) if c else None
        certs = _int(c.get("certificates")) if c else None
        emitted = (_int(c.get("discoveries")) or 0) + (cand or 0) if c else (
            _int(av.get("rows_in_window")) if av else None)
        # FORWARD-KEPT and YIELD from this producer's own certificates.
        mine = (certs_of or {}).get(name, []) if certs_of is not None else None
        kept = killed = 0
        window_cells: list[str] = []
        for rec in mine or []:
            cell = str(rec["cell"])
            sym, fam = symbol_of(cell), family_of(cell)
            st = clocks.get((sym, fam)) if clocks is not None else None
            kept += st == "KEPT"
            killed += st == "KILLED"
            born = _parse(rec.get("at"))
            if born and born >= window_start and _tradable(sym, fam) and not _is_exotic(sym):
                window_cells.append(cell)
        keep_rate: float | str = (round(kept / (kept + killed), 4) if kept + killed
                                  else UNMEASURED)
        keep_used = keep_rate if isinstance(keep_rate, float) else desk_keep
        hours = cpu.get(name)
        cpu_window = hours * YIELD_WINDOW_D / COMPUTE_WINDOW_D if hours else None
        keff = k_eff(window_cells) if mine is not None else None
        yld: float | str = UNMEASURED
        if keff is not None and keep_used is not None and cpu_window:
            yld = round(keff * keep_used / cpu_window, 8)
        funnel = {"emitted": emitted if emitted is not None else UNMEASURED,
                  "compiled": cand if c else UNMEASURED,
                  "judged": judged if c else UNMEASURED,
                  # The birth record is the certificate authority; the conversion table is
                  # derived from it, so either one answers the certified stage.
                  "certified": (certs if c else len(mine) if mine is not None
                                else UNMEASURED),
                  "forward_kept": (kept if mine is not None and clocks is not None
                                   else UNMEASURED),
                  "forward_keep_rate": keep_rate}
        prev = snaps.get(name) or {}
        prev_at = _parse(prev.get("at"))
        day = None
        if prev_at and now - prev_at >= timedelta(hours=24) and c:
            day = {k: (funnel[k] - prev[k]) if isinstance(funnel[k], int)
                   and isinstance(prev.get(k), int) else UNMEASURED
                   for k in ("emitted", "compiled", "judged", "certified", "forward_kept")}
        cpc = (certs / cand) if (cand and certs is not None) else None
        laggard = bool(cand and cand >= MIN_CANDIDATES and cpc is not None
                       and desk_rate is not None and cpc < LAGGARD_FRACTION * desk_rate)
        dead = av.get("verdict") == "DEAD"
        stage = stage_of_death(funnel, laggard=laggard, dead=dead)
        rx = choose_remedy(stage, hist, replacement=_target(repl.get(name)) or None,
                           is_seat=bool(av), exotic_share=(dg or {}).get("exotic_share"))
        rem = rx.get("remedy")
        ret = retired.get(name) or {}
        prior = _cycle(hist_all.get(name, []), ret.get("retest_at")
                       if ret and _parse(ret.get("retest_at")) and now >= _parse(
                           ret.get("retest_at")) else None)
        # R5: evaluate the open attempt, revert a worse one.
        for att in prior:
            if any(o.get("attempt") == att.get("attempt") and o.get("at") == att.get("at")
                   for o in outcomes.get(name, [])):
                continue
            ev = evaluate(att, judged, certs, conv, now)
            if ev is not None:
                outcomes.setdefault(name, []).append(ev)
                if ev["outcome"] == "FAILED_REVERTED":
                    prescriptions.pop(name, None)
        evals = [o for o in outcomes.get(name, [])
                 if any(o.get("at") == a.get("at") for a in prior)]
        failed = [o for o in evals if str(o.get("outcome")).startswith("FAILED")]
        r: dict[str, Any] = {
            "producer": name, "funnel": funnel, "funnel_day": day or UNMEASURED,
            "stage_of_death": stage, "seat_verdict": av.get("verdict") or UNMEASURED,
            "candidates": funnel["compiled"], "cells_judged": funnel["judged"],
            "certificates": funnel["certified"],
            "certificates_per_candidate": round(cpc, 8) if cpc is not None else UNMEASURED,
            "kill_class_histogram": hist if hist is not None else UNMEASURED,
            "dominant_kill_class": rx.get("dominant_kill_class"),
            "remedy": rem, "config_level": CONFIG_LEVEL.get(rem) if rem else None,
            "reason": rx.get("reason"),
            "yield": {"k_eff_edges": round(keff, 4) if keff is not None else UNMEASURED,
                      "forward_keep_rate_used": (round(keep_used, 4) if keep_used is not None
                                                 else UNMEASURED),
                      "keep_rate_source": ("OWN" if isinstance(keep_rate, float)
                                           else "DESK_POOLED" if desk_keep is not None
                                           else UNMEASURED),
                      "cpu_hours_window": (round(cpu_window, 3) if cpu_window
                                           else UNMEASURED),
                      "edges_per_cpu_hour": yld},
            "attempts_used": len(prior), "max_attempts": MAX_ATTEMPTS,
            "remedies_evaluated": evals, "owner": owners.get(name) or "UNASSIGNED",
        }
        if rx.get("replacement"):
            r["replacement"] = rx["replacement"]
        retest = ret.get("retest_at")
        if retest and _parse(retest) and now < _parse(retest):   # type: ignore[operator]
            status = "PARKED"
            r["retest_at"] = retest
            r["archive"] = ret.get("archive")
        elif len(failed) >= MAX_ATTEMPTS:
            status = "PARKED"
            retest = _iso(now + timedelta(days=RETEST_AFTER_DAYS))
            arch = _archive(name, {**r, "generated_at": _iso(now)}, prior, evals, retest)
            retired[name] = {"retired_at": _iso(now), "retest_at": retest, "archive": arch}
            prescriptions.pop(name, None)
            r.update({"retest_at": retest, "archive": arch,
                      "reason": f"{len(failed)} failed remedies: parked at the floor weight, evidence archived, "
                                f"re-test {retest[:10]}"})
        elif not c and not av:
            status = UNMEASURED
        elif stage is None:
            status = "HEALTHY" if c else UNMEASURED
        elif not dead and cand is not None and 0 < cand < MIN_CANDIDATES:
            status = "DIAGNOSING"
            r["reason"] = f"{cand} candidate(s), below the minimum sample {MIN_CANDIDATES}"
        elif rem is None:
            status = "DIAGNOSING"
        elif rem == COMPUTE_REWEIGHT:
            status = "FIX_QUEUED"
        elif not CONFIG_LEVEL[rem]:
            status = "CODE_FIX_NEEDED"
            r["owner_thread"] = owners.get(name) or "UNASSIGNED"
        else:
            status = "FIX_QUEUED"
            if apply and recomputed and name not in open_remedy:
                ctl_names = sorted(n for n in conv if n != name and n not in open_remedy
                                   and n not in retired)[:MAX_CONTROLS]
                controls = {"producers": ctl_names,
                            "judged": sum(_int(conv[n].get("judged")) or 0 for n in ctl_names),
                            "certificates": sum(_int(conv[n].get("certificates")) or 0
                                                for n in ctl_names)}
                res = record_attempt(name, rem, [f"loop:{name}:{rem}:{len(prior) + 1}"],
                                     "held_out", family=(dg or {}).get("dominant_family"),
                                     judged_now=judged, certificates_now=certs,
                                     controls=controls, now=now,
                                     retest_at=ret.get("retest_at"))
                r["attempt_recorded"] = res["recorded"]
                r["attempt_why"] = res["why"]
                if res["recorded"]:
                    r["attempts_used"] = len(prior) + 1
                    directive = ({"universe": "non_exotic",
                                  "test": "research.universe_policy.is_exotic_symbol"}
                                 if rem == INSTRUMENT_REMAP
                                 else {"replace_with": rx.get("replacement")})
                    prescriptions[name] = {"remedy": rem, "applied_at": _iso(now),
                                           "attempt": len(prior) + 1, "directive": directive,
                                           "reason": rx.get("reason")}
        r["status"] = status
        rows.append(r)

    # R4: TWO-SIDED weights from measured yield; unmeasured is par, parked is the floor (never 0).
    measured = [x["yield"]["edges_per_cpu_hour"] for x in rows
                if isinstance(x["yield"]["edges_per_cpu_hour"], float)]
    med = statistics.median([y for y in measured if y > 0]) if any(y > 0 for y in measured) \
        else None
    weights: dict[str, Any] = {}
    for x in rows:
        y = x["yield"]["edges_per_cpu_hour"]
        if x["status"] == "PARKED":
            w = WEIGHT_MIN
        elif isinstance(y, float) and med:
            w = min(WEIGHT_MAX, max(WEIGHT_MIN, y / med))
        elif isinstance(y, float) and measured:
            w = WEIGHT_MIN if y == 0 and any(v > 0 for v in measured) else 1.0
        else:
            w = 1.0
        x["weight"] = round(w, 4)
        if w != 1.0:
            weights[x["producer"]] = {"weight": round(w, 4), "yield": y, "status": x["status"]}

    ranked = sorted(rows, key=lambda x: (not isinstance(x["yield"]["edges_per_cpu_hour"], float),
                                         -(x["yield"]["edges_per_cpu_hour"]
                                           if isinstance(x["yield"]["edges_per_cpu_hour"], float)
                                           else 0.0),
                                         not isinstance(x["certificates_per_candidate"], float),
                                         -(x["certificates_per_candidate"]
                                           if isinstance(x["certificates_per_candidate"], float)
                                           else 0.0), x["producer"]))
    for i, x in enumerate(ranked, 1):
        x["rank"] = i
    census = Counter(x["status"] for x in ranked)
    doc = {
        "generated_at": _iso(now),
        "law": ("Every producer's funnel (emitted > compiled > judged > certified > forward-kept) "
                "is measured, the stage where it dies is named, and it gets a remedy from a "
                "fixed menu -- never a parameter tweak; remedies are charged to the lifetime "
                "trial ledger, judged held-out or forward only, one at a time against untouched "
                f"controls, reverted when worse, and parked at the floor weight after {MAX_ATTEMPTS} failures. "
                "Compute weight follows independent, non-exotic, forward-kept edges per "
                "CPU-hour, two-sided. A missing input is UNMEASURED, never zero."),
        "cadence": {"detection": "every pass",
                    "diagnosis": f"recomputed when >= {DIAGNOSIS_MAX_AGE_H:g}h old or --force",
                    "remedy_round": (f">= {MIN_JUDGED_SINCE_TWEAK} judged AND >= "
                                     f"{MIN_DAYS_BETWEEN_ATTEMPTS:g} days since the last")},
        "diagnosis": {"recomputed_this_pass": recomputed, "at": diag.get("at"),
                      "available": bool(diag.get("available")), "why": diag.get("why")},
        "inputs": {"conversion": "READ" if conv else f"{UNMEASURED}: {CONVERSION.name}",
                   "certificate_provenance": ("READ" if certs_of is not None
                                              else f"{UNMEASURED}: {PROVENANCE.name}"),
                   "forward_clocks": ("READ" if clocks is not None
                                      else f"{UNMEASURED}: {SHADOW.name}"),
                   "compute_hours": "READ" if cpu else f"{UNMEASURED}: {YIELD_REPORT.name}",
                   "dead_audit": audit.get("source") or audit.get("why")},
        "desk_certificates_per_candidate": (round(desk_rate, 8) if desk_rate is not None
                                            else UNMEASURED),
        "desk_forward_keep_rate": round(desk_keep, 4) if desk_keep is not None else UNMEASURED,
        "yield_metric": (f"k_eff(certified tradable non-exotic edges born in {YIELD_WINDOW_D:g}d; "
                         "libs.research.trial_ledger.census) x forward keep-rate / CPU-hours "
                         f"(7-day measured rate x {YIELD_WINDOW_D / COMPUTE_WINDOW_D:.2f})"),
        "kill_class_by_gate": KILL_CLASS_BY_GATE,
        "remedies_by_stage": {k: list(v) for k, v in REMEDIES_BY_STAGE.items()},
        "remedy_by_kill_class": {k: v[0] for k, v in REMEDY_BY_KILL_CLASS.items()},
        "config_level": CONFIG_LEVEL,
        "rails": {"R1": "held_out / forward_shadow only", "R2": "experiment_ledger "
                  "loop_attempt_trials", "R3": "one open remedy per producer; frozen controls",
                  "R4": "two-sided weights", "R5": "auto-revert when worse net of controls",
                  "R6": "writes only its own files; never prop rules, rails or live sizing",
                  "R7": "remedies_evaluated carries before/after"},
        "census": dict(census),
        # The contract's metric (docs/research/experiment_contracts.json): producers whose
        # funnel is measured and does not die, and the desk's independent forward-kept edges.
        "summary": {"n_producers": len(ranked), "n_healthy": census.get("HEALTHY", 0),
                    "n_with_remedy": sum(1 for x in ranked if x["remedy"]),
                    "n_parked": census.get("PARKED", 0),
                    "k_eff_edges_window": round(sum(
                        x["yield"]["k_eff_edges"] for x in ranked
                        if isinstance(x["yield"]["k_eff_edges"], float)), 4)},
        "laggards": [x["producer"] for x in ranked if x["status"] in (
            "DIAGNOSING", "FIX_QUEUED", "CODE_FIX_NEEDED", "PARKED")],
        "producers": ranked,
        "budget_s": budget, "elapsed_s": round(time.monotonic() - t0, 2),
    }
    new_snaps = dict(snaps)
    for x in rows:
        p = snaps.get(x["producer"]) or {}
        if not p or (_parse(p.get("at")) and now - _parse(p["at"]) >= timedelta(  # type: ignore
                hours=24)):
            new_snaps[x["producer"]] = {"at": _iso(now), **{
                k: x["funnel"][k] for k in ("emitted", "compiled", "judged", "certified",
                                            "forward_kept")}}
    doc["_state"] = {"diagnosis": diag, "retired": retired, "outcomes": outcomes,
                     "snapshots": new_snaps}
    doc["_weights"] = weights
    doc["_prescriptions"] = prescriptions
    return doc


def write(doc: dict[str, Any], *, out: Path | None = None) -> dict[str, Any]:
    """Publish the report, the weight and prescription files, the state and the ledger rows."""
    new_state = doc.pop("_state", {})
    weights = doc.pop("_weights", {})
    prescriptions = doc.pop("_prescriptions", {})
    _atomic(out or OUT, doc)
    _atomic(WEIGHTS, {"generated_at": doc["generated_at"],
                      "rule": ("two-sided producer weights from measured yield (par 1.0 when "
                               "unmeasured, the floor when parked); read by merge_hypotheses "
                               "reweight_rows inside each family's own docket slots -- no row "
                               "removed, the judge's exploration floor untouched"),
                      "producers": weights})
    _atomic(PRESCRIPTIONS, {"generated_at": doc["generated_at"],
                            "rule": "config-level remedies the loop applied; producers and the "
                                    "yield code read this file -- no code is edited",
                            "producers": prescriptions})
    state = _read(STATE, {}) or {}
    prev = state.get("status") or {}
    status = {x["producer"]: x["status"] for x in doc["producers"]}
    state.update({**new_state, "status": status, "at": doc["generated_at"]})
    _atomic(STATE, state)
    recomputed = bool((doc.get("diagnosis") or {}).get("recomputed_this_pass"))
    lines = [{"at": doc["generated_at"], "producer": x["producer"], "status": x["status"],
              "funnel": x["funnel"], "stage_of_death": x["stage_of_death"],
              "remedy": x["remedy"], "weight": x.get("weight"),
              "edges_per_cpu_hour": x["yield"]["edges_per_cpu_hour"],
              "attempts_used": x["attempts_used"]}
             for x in doc["producers"] if recomputed or prev.get(x["producer"]) != x["status"]]
    _append(LEDGER, lines)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--force", action="store_true", help="recompute the diagnosis now")
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--no-apply", action="store_true",
                    help="diagnose only; record no attempt and apply no config remedy")
    ap.add_argument("--record-attempt", metavar="PRODUCER")
    ap.add_argument("--remedy", choices=REMEDIES)
    ap.add_argument("--trial-id", action="append", default=[])
    ap.add_argument("--judged-on", default="")
    ap.add_argument("--family", default=None)
    args = ap.parse_args(argv)
    if args.record_attempt:
        res = record_attempt(args.record_attempt, str(args.remedy or ""), args.trial_id,
                             args.judged_on, family=args.family)
        print(json.dumps({k: v for k, v in res.items() if k != "row"}))
        return 0 if res["recorded"] else 1
    doc = write(build(force=args.force, budget_s=args.budget_s, apply=not args.no_apply))
    print(f"producer_loop: {len(doc['producers'])} producer(s) {doc['census']}; diagnosis "
          f"{'recomputed' if doc['diagnosis']['recomputed_this_pass'] else 'cached'} "
          f"({doc['diagnosis'].get('why') or 'ok'}) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
