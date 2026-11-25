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

THE YIELD METRIC (libs/research/live_yield, principal 2026-11-25). EXPECTED LIVE EDGES per
CPU-hour: certified, tradable, NON-EXOTIC edges born in the last YIELD_WINDOW_D days, counted as
INDEPENDENT edges (k_eff = trial_ledger.census over (symbol, family, asset class) descriptors --
never a raw count), times p(cert -> forward-kept) times p(forward-kept -> LIVE and fill-proven),
each the producer's own rate at live_yield.MIN_STAGE_N, else shrunk toward the desk-pooled rate;
realised live edges dominate once they exist. The weight is that yield over the
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

SUCCESSORS (principal 2026-11-25: a producer that keeps failing has an opportunity cost). A producer
PARKED after its failed remedies, or whose yield sat below LAGGARD_FRACTION of the desk's pooled
yield over MIN_CANDIDATES judged cells, gets a SUCCESSOR DESIGN in `data/PRODUCER_SUCCESSORS.json`:
one LIVE successor per lineage at a time, named `<root>~s<gen>`, on the next untried axis of the
fixed menu DESIGN_AXES chosen by the head's dominant kill class (AXES_BY_KILL_CLASS) -- a
structural redesign, never a retune on judged results. FRESH_DESIGN_SHARE of slots (a hash of
root and generation), and the slot after two failed close variants, go to a FRESH design: a
different, least-judged family the paper miners and the brain already mined, placed on the
parent's symbols. `merge_hypotheses` mints the rows through `extend_docket` / `successor_rows`
before order_docket (so they pass judge_prescreen like every row): copies only, non-exotic,
executable families with params the judge builds, tagged producer / successor_of / design_axis /
origin / generation / lineage, bounded MAX_SUCCESSOR_ROWS per successor per pass. Universe and
fresh axes prefer the desk's `zero_cert_classes`. The successor has its own funnel, yield and
weight (par until measured); the parent keeps at least WEIGHT_MIN, so breadth only grows, and
compute follows whichever yields more. A successor that triggers in turn is closed (PARKED or
SEED: it keeps minting at its own weight) and the lineage's next generation is designed.

ONE LINEAGE, ONE TRIAL GROUP. Every row of a lineage (parent and every generation) is stamped
`claim_family = lineage:<root>` (`stamp_lineage`), the key trial_ledger groups on first, so
repeatedly spawning variants is charged as ONE family-wise lineage. BREADTH is counted per parent
CELL, not per lineage: a parent row keeps its own unit, a close-variant child takes the
`claim_selection.breadth_unit` of the cell it was mutated from (a variant is not a new
independent bet), and a fresh-design child keeps its own cell unit. trial_ledger.grid_key
keeps the strategy family on the grid axis for a lineage, so
grouping never lowers the charge. Every judged cell is still a trial; `lineage_trials` (parent
plus successors, cumulative, ratcheted) is published. No gate, DSR, FDR or the fixed 597 is
touched.

THE FEDERATION. Each third-party system (external_federation.SEEDS, sandbox_runner's state,
research/sandboxes/) is its OWN producer `sandbox:<system_id>` (`row_producer` reads the
`sandbox:` token on generator/source_id before the carrying organ's name), with the same funnel,
weight, parking and successors; its CPU comes from PRODUCER_YIELD, else from sandbox_runner_state's
compute_spent differenced over >= 7 days, else UNMEASURED. `federation` ranks them by yield.

PASS RATES. Each producer's pass rate (PASSED / judged in the daily sample) by asset class,
session and timeframe, with the live-promotion rate where measurable; `failed_volume_share` is
judged-and-killed over judged (reported; volume is penalised through the per-CPU-hour yield, never
by a cap).

A MISSING INPUT IS UNMEASURED, NEVER ZERO (L1.28a).

    python desks/mt5/research/producer_loop.py            # every-pass build
    python desks/mt5/research/producer_loop.py --force    # recompute the diagnosis now
    python desks/mt5/research/producer_loop.py --record-attempt NAME --remedy GRID_NARROW \
        --trial-id T1 --judged-on held_out [--family FAM]
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import sqlite3
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


#: Below this many judged cells a bucket's pass rate is UNMEASURED.
MIN_BUCKET_N = 30
MAX_PASSED_CELLS = 2_000
_SESSION_WORDS = (("asia", "asia"), ("tokyo", "asia"), ("sydney", "asia"), ("london", "london"),
                  ("europe", "london"), ("new_york", "ny"), ("newyork", "ny"), ("ny", "ny"),
                  ("us_open", "ny"), ("overlap", "london"))


def asset_class(symbol: str) -> str:
    """The peer class universe_policy ranks `symbol` within, else its registry class."""
    try:
        from research import universe_policy as up
        return str(up.peer_class(symbol) or up.asset_class_of(symbol) or "unclassified").lower()
    except Exception:
        return "unclassified"


def session_of(family: str, params: dict[str, Any]) -> str:
    """asia / london / ny when the params or the family name state it (a session word, or an
    entry hour in UTC: <7 asia, <13 london, <21 ny); "" when nothing states it (UNMEASURED)."""
    for k in ("session", "window", "selector", "session_window"):
        v = str(params.get(k) or "").lower()
        for w, sname in _SESSION_WORDS:
            if v and w in [*v.split("_"), v]:
                return sname
    for k in ("entry_hour", "hour", "open_hour", "entry_hour_utc"):
        h = params.get(k)
        if isinstance(h, int | float) and not isinstance(h, bool) and 0 <= h < 24:
            return "asia" if h < 7 else "london" if h < 13 else "ny" if h < 21 else "asia"
    parts = family.lower().split("_")
    for w, sname in _SESSION_WORDS:
        if w in parts:
            return sname
    return ""


def cell_attrs(sym: str, fam: str, params: dict[str, Any], cell: str = ""
               ) -> tuple[str, str, str]:
    """(asset class, timeframe, session) of one cell."""
    head = cell.rsplit(".", 2)[0] if cell.count(".") >= 2 else ""
    tf = (head.split("@", 1)[1] if "@" in head else str(params.get("timeframe") or "H1")).upper()
    return asset_class(sym), tf, session_of(fam, params)


def _is_exotic(symbol: str) -> bool:
    try:
        from research.universe_policy import is_exotic_symbol
        return bool(is_exotic_symbol(symbol))
    except Exception:
        return True       # fail CLOSED: an unreadable policy never lets an exotic through


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
        rp = row_producer(r)
        if rp in w:
            return w[rp]
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


# ----------------------------------------------------------------- producer identity of a row

#: A token with one of these prefixes names ONE system, and is never pooled into the organ that
#: carried the row: a registry re-emission is stamped producer="alpha_registry" by the merge, but
#: its generator/source_id `sandbox:<system_id>` is the system that made it (sandbox_runner.ingest).
SPECIFIC_PREFIXES = ("sandbox:",)


def row_producer(r: Any) -> str:
    """The producer a docket row belongs to: a successor's own name, else a specific system token
    (`sandbox:<system_id>`) on any of its keys, else producer / source / generator."""
    if not isinstance(r, dict):
        return ""
    if r.get("origin") == SUCCESSOR_ORIGIN and r.get("producer"):
        return _norm(r["producer"])
    for k in ("generator", "source_id", "source", "producer"):
        v = str(r.get(k) or "").strip().lower()
        if v.startswith(SPECIFIC_PREFIXES):
            return _norm(v)
    for k in ("producer", "source", "generator"):
        n = _norm(r.get(k)) if r.get(k) else ""
        if n:
            return n
    return ""


# ------------------------------------------------------------------------- SUCCESSOR PRODUCERS

SUCCESSOR_ORIGIN = "producer_successor"
#: The design file: one record per successor, written by `build`, read by merge_hypotheses.
SUCCESSORS: Path | None = None
#: sandbox_runner's own state (per-system lifetime compute_spent seconds).
SANDBOX_STATE: Path | None = None
#: The trial-ledger grouping key every row of a lineage carries (claim_family; see stamp_lineage).
LINEAGE_PREFIX = "lineage:"
#: Rows one successor mints per pass.
MAX_SUCCESSOR_ROWS = 40
#: Symbols one row is transferred to on a universe axis.
TRANSFER_SYMBOLS = 3
#: THE FRESH-DESIGN SHARE: this fraction of successor slots (by a hash of root and generation)
#: goes to a completely different design, and so does the slot after two close variants failed.
FRESH_DESIGN_SHARE = 0.25

#: THE FIXED AXIS MENU. A STRUCTURAL redesign each, never a retuning on judged results: the
#: values written (a coarser/finer chart, a doubled holding period, a declared volatility regime,
#: another non-exotic symbol) are fixed by the axis, not read off any verdict.
LOW_TURNOVER = "low_turnover_long_horizon"   # coarser chart, held longer, cheapest-cost symbols
WIDER_UNIVERSE = "wider_universe_timeframes"  # non-exotic class peers + a finer chart
REGIME_CONDITIONED = "regime_conditioned"     # cell_modifiers.VOL_REGIMES high_vol / low_vol
ORTHOGONAL = "orthogonal_placement"           # where the certified book holds no such cell
NON_EXOTIC_REMAP = "non_exotic_remap"         # exotic -> its non-exotic class peers
DATA_SOURCE_SWAP = "data_source_swap"         # a request only: mints no row
FRESH_DESIGN = "fresh_design"                 # another, under-covered family already mined
CLOSE_AXES = (LOW_TURNOVER, WIDER_UNIVERSE, REGIME_CONDITIONED, ORTHOGONAL, NON_EXOTIC_REMAP,
              DATA_SOURCE_SWAP)
DESIGN_AXES = (*CLOSE_AXES, FRESH_DESIGN)
#: The parent's dominant kill class -> the axes in preference order. ORTHOGONAL is placement, not
#: a residual: cell_modifiers REFUSES `residual` (no family residualises its input), so a residual
#: row would die as DEAD_DATA; a cell where the certified book has nothing is the orthogonal
#: design the judge can actually build.
AXES_BY_KILL_CLASS: dict[str, tuple[str, ...]] = {
    COSTS: (LOW_TURNOVER, REGIME_CONDITIONED, ORTHOGONAL, WIDER_UNIVERSE),
    TOO_FEW_TRADES: (WIDER_UNIVERSE, LOW_TURNOVER, ORTHOGONAL),
    NO_OOS_EDGE: (REGIME_CONDITIONED, ORTHOGONAL, LOW_TURNOVER, WIDER_UNIVERSE),
    DUPLICATE: (ORTHOGONAL, WIDER_UNIVERSE, REGIME_CONDITIONED),
    EXOTIC_UNIVERSE: (NON_EXOTIC_REMAP, WIDER_UNIVERSE, ORTHOGONAL),
    DEAD_DATA: (NON_EXOTIC_REMAP, DATA_SOURCE_SWAP, WIDER_UNIVERSE),
    UNMAPPED: (NON_EXOTIC_REMAP, DATA_SOURCE_SWAP, WIDER_UNIVERSE),
}
FINER = {"D1": "H4", "H4": "H1", "H1": "M30", "M30": "M15", "M15": "M5"}
VOL_REGIMES = ("high_vol", "low_vol")
#: Where a fresh design draws from: rows the paper miners and the daily brain already produced.
FRESH_SOURCE_PREFIXES = ("src:paper:", "brain", "seat:brain", "research_feeds", "arxiv")
#: Row keys a child never inherits: identities, verdicts and stamps belong to the parent's cell.
_CHILD_DROP = frozenset({"id", "hypothesis_id", "candidate_id", "genome_id", "cell", "cell_id",
                         "trial_id", "payload_hash", "prejudge", "verdict", "status", "passed",
                         "judged", "breadth_unit", "lineage", "lineage_root", "design_axis",
                         "successor_of", "generation"})


def _succ_path() -> Path:
    return SUCCESSORS or DESK / "data" / "PRODUCER_SUCCESSORS.json"


def _sandbox_state_path() -> Path:
    return SANDBOX_STATE or DESK / "data" / "sandbox_runner_state.json"


def load_designs(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read(path or _succ_path(), {}) or {}
    d = doc.get("designs") if isinstance(doc, dict) else None
    return {str(k): v for k, v in (d or {}).items() if isinstance(v, dict)}


def dominant_kill(hist: Any) -> str | None:
    kills = {k: v for k, v in (hist or {}).items()
             if k in KILL_CLASSES and isinstance(v, int) and v} if isinstance(hist, dict) else {}
    return sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if kills else None


def _fresh_slot(root: str, gen: int) -> bool:
    import hashlib
    h = int(hashlib.sha256(f"{root}|{gen}".encode()).hexdigest()[:8], 16)
    return (h % 10_000) < FRESH_DESIGN_SHARE * 10_000


def next_axis(kill: str | None, tried: list[str], root: str, gen: int,
              lineage: list[dict[str, Any]]) -> tuple[str, str]:
    """(axis, why) for generation `gen` of `root`'s lineage. FRESH on its hashed share, after two
    close variants in a row failed, or when every close axis was tried; else the next untried
    close axis in the dominant kill class's preference order, then the menu order."""
    closes = [d for d in sorted(lineage, key=lambda d: int(d.get("generation") or 0))
              if d.get("axis") != FRESH_DESIGN]
    last_two = sorted(lineage, key=lambda d: int(d.get("generation") or 0))[-2:]
    if _fresh_slot(root, gen):
        return FRESH_DESIGN, f"fresh-design share {FRESH_DESIGN_SHARE:.0%} (hash of root, gen)"
    if len(last_two) == 2 and all(d.get("axis") != FRESH_DESIGN and d.get("status") != "LIVE"
                                  for d in last_two):
        return FRESH_DESIGN, "two close-variant generations in a row failed"
    pref = AXES_BY_KILL_CLASS.get(kill or "", ())
    for ax in (*pref, *CLOSE_AXES):
        if ax not in tried:
            return ax, (f"next untried axis for dominant kill class {kill}" if kill
                        else f"next untried axis ({UNMEASURED} kill class: menu order)")
    del closes
    return FRESH_DESIGN, "every close axis was tried"


def _peers(symbol: str) -> list[str]:
    """Non-exotic class peers of `symbol` (universe_policy), sorted; [] when unreadable."""
    try:
        from research import universe_policy as up
        klass = up.peer_class(symbol) or ("fx_usd" if _is_exotic(symbol) else None)
        return [s for s in up.class_members(klass) if s.upper() != symbol.upper()] if klass \
            else []
    except Exception:
        return []


def _all_symbols() -> dict[str, list[str]]:
    try:
        from research import universe_policy as up
        return up.peer_classes()
    except Exception:
        return {}


def _spread(symbol: str) -> float | None:
    """The registry's median spread in points; None when unmeasured (absent or 0)."""
    try:
        from research import universe_policy as up
        v = (up._registry().get(symbol) or {}).get("median_spread_pts")
        return float(v) if isinstance(v, int | float) and v > 0 else None
    except Exception:
        return None


def _lengthen(params: dict[str, Any]) -> dict[str, Any] | None:
    """graveyard_resurrection's own lengthen (the holding parameter doubled), reused."""
    try:
        from research.graveyard_resurrection import _lengthen as f
        return f(params)
    except Exception:
        return None


def _coarser(tf: str) -> str | None:
    try:
        from research.graveyard_resurrection import COARSER
        return COARSER.get(tf)
    except Exception:
        return None


def _sym(r: dict[str, Any]) -> str:
    return str(r.get("symbol") or r.get("sym") or "")


def row_identity(r: dict[str, Any]) -> str:
    """merge_hypotheses._identity: symbol, family and params -- what would be executed."""
    params = r.get("params") or {}
    return json.dumps({"symbol": _sym(r), "family": str(r.get("family") or ""),
                       "params": {k: params[k] for k in sorted(params)}
                       if isinstance(params, dict) else {}}, sort_keys=True, default=str)


def _ok(sym: str, fam: str) -> bool:
    return bool(sym and fam) and not _is_exotic(sym) and _tradable(sym, fam)


def _variants(r: dict[str, Any], axis: str, book: set[tuple[str, str]],
              targets: frozenset[str] = frozenset()) -> list[tuple[str, dict[str, Any]]]:
    """(symbol, params) children of one parent row on one close axis."""
    sym, fam = _sym(r), str(r.get("family") or "")
    p = dict(r.get("params") or {}) if isinstance(r.get("params"), dict) else {}
    tf = str(p.get("timeframe") or r.get("timeframe") or "H1").upper()
    out: list[tuple[str, dict[str, Any]]] = []
    if axis == LOW_TURNOVER:
        c = _coarser(tf)
        if c is None:
            return out
        q = {**p, "timeframe": c}
        q = _lengthen(q) or q
        mine = _spread(sym)
        cheap = sorted((s for s in _peers(sym) if (_spread(s) or 0) > 0
                        and mine is not None and (_spread(s) or 0) < mine),
                       key=lambda s: (_spread(s) or 0, s))[:TRANSFER_SYMBOLS - 1]
        out += [(s, q) for s in [sym, *cheap]]
    elif axis == WIDER_UNIVERSE:
        out += [(s, p) for s in _peers(sym)[:TRANSFER_SYMBOLS]]
        if tf in FINER:
            out.append((sym, {**p, "timeframe": FINER[tf]}))
        # ... and every zero-certificate timeframe the desk has judged (evolution pushes there)
        out += [(sym, {**p, "timeframe": t[3:]}) for t in sorted(targets)
                if t.startswith("tf:") and t[3:] not in (tf, FINER.get(tf))]
    elif axis == REGIME_CONDITIONED:
        if str(p.get("regime") or "").lower() in ("", "unconditional", "all", "any"):
            out += [(sym, {**p, "regime": g}) for g in VOL_REGIMES]
    elif axis == ORTHOGONAL:
        own = None
        try:
            from research import universe_policy as up
            own = up.peer_class(sym)
        except Exception:
            own = None
        for klass, members in sorted(_all_symbols().items(),
                                     key=lambda kv: (f"class:{kv[0]}" not in targets, kv[0])):
            if klass == own or klass == "equity":
                continue
            free = [s for s in members if (s, fam) not in book]
            if free:
                out.append((free[0], p))
            if len(out) >= TRANSFER_SYMBOLS:
                break
    elif axis == NON_EXOTIC_REMAP:
        out += [(s, p) for s in _peers(sym)[:TRANSFER_SYMBOLS]]
    return out


def _fresh_source(r: dict[str, Any]) -> bool:
    for k in ("producer", "source", "source_id", "generator", "origin"):
        v = str(r.get(k) or "").strip().lower()
        if v and (v.startswith(FRESH_SOURCE_PREFIXES) or "research_feeds" in v):
            return True
    return False


def successor_rows(parent_rows: list[dict[str, Any]], design: dict[str, Any], *,
                   pool: list[dict[str, Any]] | None = None,
                   coverage: dict[str, int] | None = None,
                   existing: set[str] | None = None,
                   book: set[tuple[str, str]] | None = None) -> list[dict[str, Any]]:
    """THE DETERMINISTIC TRANSFORM: rows the successor `design` mints this pass, at most
    MAX_SUCCESSOR_ROWS. Copies only -- no parent row is removed or altered. Every child is a
    registered family with params the judge already builds (timeframe, the holding key
    graveyard_resurrection lengthens, cell_modifiers' volatility regime, another symbol), is
    non-exotic and tradable, is new to the docket by identity, and is tagged producer, successor_of,
    design_axis, origin, generation and its lineage (stamped as one trial-ledger group).

    A FRESH design does not mutate the parent: it takes the rows the paper miners and the brain
    already produced (FRESH_SOURCE_PREFIXES) of the least-judged family the lineage has not
    produced, and places that family on the parent's own non-exotic symbols."""
    axis = str(design.get("axis") or "")
    name, root = str(design.get("name") or ""), str(design.get("root") or "")
    seen = set(existing or ())
    book = book or set()
    targets = frozenset(str(t) for t in design.get("targets") or [])
    out: list[dict[str, Any]] = []
    latest = sorted((r for r in parent_rows if isinstance(r, dict)),
                    key=lambda r: str(r.get("ingested_time") or r.get("available_time") or ""),
                    reverse=True)

    def emit(src: dict[str, Any], sym: str, params: dict[str, Any], fam: str,
             unit: str | None = None) -> None:
        if len(out) >= MAX_SUCCESSOR_ROWS or not _ok(sym, fam):
            return
        child = {k: v for k, v in src.items() if k not in _CHILD_DROP}
        child[("sym" if "sym" in src and "symbol" not in src else "symbol")] = sym
        if "symbols" in child:
            child["symbols"] = [sym]
        child.update({"family": fam, "params": dict(params), "producer": name,
                      "successor_of": str(design.get("parent") or ""), "design_axis": axis,
                      "origin": SUCCESSOR_ORIGIN, "generation": int(design.get("generation") or 0),
                      "lineage": root})
        stamp_lineage(child, root)
        if unit is not None:
            child["breadth_unit"] = unit      # a variant of a cell is that cell's breadth
        ident = row_identity(child)
        if ident in seen:
            return
        seen.add(ident)
        out.append(child)

    if axis == FRESH_DESIGN:
        own = {str(r.get("family") or "") for r in latest}
        cov = coverage or {}
        cands = [r for r in pool or [] if isinstance(r, dict) and _fresh_source(r)
                 and str(r.get("family") or "") not in own]
        if not cands:
            return out
        fams = sorted({str(r.get("family")) for r in cands},
                      key=lambda f: (cov.get(f, 0), f))
        fam = fams[0]
        syms = sorted({_sym(r) for r in latest if _sym(r)}) or sorted(
            {_sym(r) for r in cands if str(r.get("family")) == fam})
        # zero-certificate classes first: one member of each, ahead of the parent's own symbols
        zc = [ms[0] for k, ms in sorted(_all_symbols().items())
              if f"class:{k}" in targets and ms]
        syms = [*zc, *[x for x in syms if x not in zc]]
        for src in (r for r in cands if str(r.get("family")) == fam):
            for s in syms:
                emit(src, s, dict(src.get("params") or {}), fam)
        return out
    for r in latest:
        if len(out) >= MAX_SUCCESSOR_ROWS:
            break
        unit = _breadth_unit(r)
        for s, q in _variants(r, axis, book, targets):
            emit(r, s, q, str(r.get("family") or ""), unit)
    return out


def _breadth_unit(row: dict[str, Any]) -> str | None:
    try:
        from libs.research import claim_selection as cs
        return cs.breadth_unit(row)
    except Exception:
        return None


def stamp_lineage(row: dict[str, Any], root: str) -> bool:
    """Charge `row` to its LINEAGE: the trial ledger groups on `claim_family` first
    (trial_from_record), so the parent's and every generation's rows are one family-wise group.
    BREADTH IS NOT TOUCHED here: the row keeps its own breadth unit (successor_rows gives a close
    variant its parent cell's unit). Additive only: `family`, `params`, the symbol
    and every verdict are untouched, and a row that already carries a claim family -- or whose
    text states a searched selection claim_selection will charge -- keeps that grouping, because
    re-keying it could drop the source's selection charge. trial_ledger.grid_key keeps the
    strategy family on the grid axis for a lineage group, so grouping never lowers the charge."""
    if not isinstance(row, dict) or row.get("claim_family"):
        return False
    try:
        from libs.research import claim_selection as cs
        if cs.selection_trials(cs.row_text(row)):
            return False
    except Exception:
        pass
    key = f"{LINEAGE_PREFIX}{root}"
    row["claim_family"] = key
    row["lineage_root"] = root
    return True


def extend_docket(rows: list[dict[str, Any]], *, coverage: dict[str, int] | None = None,
                  designs: dict[str, dict[str, Any]] | None = None
                  ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """merge_hypotheses' call: stamp every lineage member's rows, then append each successor's
    minted rows (generation order, so generation 2 mints from generation 1's rows). Appends only:
    no row is removed or reordered here; reweight_rows orders them inside their family's slots."""
    d = designs if designs is not None else load_designs()
    if not d or not rows:
        return rows, {"designs": len(d), "minted": 0}
    root_of = {n: str(v.get("root") or "") for n, v in d.items()}
    for v in d.values():
        root_of.setdefault(str(v.get("root") or ""), str(v.get("root") or ""))
    stamped = 0
    for r in rows:
        if isinstance(r, dict):
            rp = row_producer(r)
            if root_of.get(rp):
                stamped += stamp_lineage(r, root_of[rp])
    book: set[tuple[str, str]] = set()
    certs = certificates_by_producer() or {}
    for recs in certs.values():
        for rec in recs:
            c = str(rec.get("cell") or "")
            book.add((symbol_of(c), family_of(c)))
    cov = coverage
    if cov is None:
        cov = dict(Counter(str(r.get("family") or "") for r in rows if isinstance(r, dict)))
    existing = {row_identity(r) for r in rows if isinstance(r, dict)}
    out = list(rows)
    minted: dict[str, int] = {}
    for name, des in sorted(d.items(), key=lambda kv: int(kv[1].get("generation") or 0)):
        parent = str(des.get("parent") or "")
        kids = successor_rows([r for r in out if row_producer(r) == parent],
                              {**des, "name": name}, pool=out, coverage=cov, existing=existing,
                              book=book)
        existing.update(row_identity(k) for k in kids)
        out.extend(kids)
        minted[name] = len(kids)
    return out, {"designs": len(d), "minted": sum(minted.values()), "by_successor": minted,
                 "parent_rows_lineage_stamped": stamped,
                 "rule": "successor rows appended; no row removed or altered beyond the "
                         "additive lineage stamp"}


def _spawn_trigger(row: dict[str, Any], pooled_yield: float | None = None) -> str | None:
    """Why `row`'s producer earns a successor now, or None: PARKED after its failed remedies; a
    live edge the decay detector marks decaying (a failure signal like a failed remedy); or a
    staged live-yield score below LAGGARD_FRACTION of the desk's (score 1.0 = the median arm)
    over >= MIN_CANDIDATES judged cells."""
    if row.get("status") == "PARKED":
        return "PARKED after failed remedies"
    dec = (row.get("yield") or {}).get("decaying_live_edges")
    if dec:
        return f"decaying live edge(s) {', '.join(dec)} (decay detector)"
    y, j = row.get("score"), row.get("cells_judged")
    if (isinstance(y, float) and isinstance(j, int) and j >= MIN_CANDIDATES
            and y < LAGGARD_FRACTION):
        return (f"live-yield score {y:.3g} below {LAGGARD_FRACTION:g} x the desk's median "
                f"over {j} judged cells")
    return None


def plan_successors(by: dict[str, dict[str, Any]], designs: dict[str, dict[str, Any]], *,
                    now: datetime, pooled_yield: float | None, zero_cert: list[str],
                    prev_trials: dict[str, Any] | None = None
                    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(designs, the report's successor rows, lineage_trials). One LIVE successor per lineage at a
    time; when the lineage's head (the root, or its live successor) triggers, the head's design
    is closed (PARKED / SEED: it keeps minting at its own weight, so breadth only grows) and the
    next generation is designed on the next axis (`next_axis`)."""
    designs = {k: dict(v) for k, v in designs.items()}
    for root in sorted(n for n in by if n not in designs and "~s" not in n):
        lineage = {k: v for k, v in designs.items() if v.get("root") == root}
        live_d = sorted(k for k, v in lineage.items() if v.get("status") == "LIVE")
        head = live_d[0] if live_d else (root if not lineage else None)
        hr = by.get(head) if head else None
        trig = _spawn_trigger(hr, pooled_yield) if hr else None
        if not trig:
            continue
        if live_d:
            designs[head].update({"status": "PARKED" if hr["status"] == "PARKED" else "SEED",  # type: ignore
                                  "ended_at": _iso(now), "ended_why": trig})
        gen = max((int(v.get("generation") or 0) for v in lineage.values()), default=0) + 1
        tried = [str(v.get("axis")) for v in lineage.values()]
        kill = (dominant_kill(hr.get("kill_class_histogram"))  # type: ignore[union-attr]
                or dominant_kill((by.get(root) or {}).get("kill_class_histogram")))
        axis, why = next_axis(kill, tried, root, gen,
                              [v for v in designs.values() if v.get("root") == root])
        designs[f"{root}~s{gen}"] = {
            "root": root, "parent": head, "generation": gen, "axis": axis, "why": why,
            "trigger": trig, "dominant_kill_class": kill or UNMEASURED, "status": "LIVE",
            "created_at": _iso(now), "targets": list(zero_cert),
            **({"request": "swap the data source behind this producer's dead inputs"}
               if axis == DATA_SOURCE_SWAP else {})}
    report: list[dict[str, Any]] = []
    trials: dict[str, Any] = {}
    prev = prev_trials or {}
    roots = sorted({str(v.get("root")) for v in designs.values()})
    for root in roots:
        members = [root, *sorted(k for k, v in designs.items() if v.get("root") == root)]
        js = [(by.get(m) or {}).get("cells_judged") for m in members]
        now_n = sum(j for j in js if isinstance(j, int))
        before = prev.get(root, {}).get("lineage_trials") if isinstance(prev.get(root), dict) \
            else None
        trials[root] = {"lineage_trials": max(now_n, int(before or 0)),
                        "members": members, "group": f"{LINEAGE_PREFIX}{root}",
                        "basis": ("cumulative judged cells of the parent and every successor "
                                  "generation, ratcheted (never subtracted); one trial-ledger "
                                  "group and one breadth unit")}
    for name, d in sorted(designs.items(), key=lambda kv: (kv[1].get("root"),
                                                            int(kv[1].get("generation") or 0))):
        pr, sr = by.get(str(d.get("parent"))) or {}, by.get(name) or {}
        py, sy = pr.get("score"), sr.get("score")
        pw, sw = float(pr.get("weight") or 1.0), float(sr.get("weight") or 1.0)
        flow = (UNMEASURED if not (isinstance(py, float) and isinstance(sy, float))
                else "TO_SUCCESSOR" if sy > py else "TO_PARENT" if sy < py else "EVEN")
        report.append({"successor": name, "parent": d.get("parent"), "root": d.get("root"),
                       "generation": d.get("generation"), "axis": d.get("axis"),
                       "status": d.get("status"), "why": d.get("why"),
                       "trigger": d.get("trigger"),
                       "parent_yield": py if py is not None else UNMEASURED,
                       "successor_yield": sy if sy is not None else UNMEASURED,
                       "parent_weight": pw, "successor_weight": sw,
                       "parent_weight_share": round(pw / (pw + sw), 4),
                       "successor_weight_share": round(sw / (pw + sw), 4),
                       "compute_flow": flow})
    return designs, report, trials


def sandbox_roster() -> list[str]:
    """Every third-party system the federation declares, each its OWN producer: the
    external_federation SEEDS (RD-Agent among them), sandbox_runner's state, research/sandboxes/."""
    names: set[str] = set()
    try:
        from libs.research.external_federation import SEEDS
        names |= {f"sandbox:{s.system_id}".lower() for s in SEEDS}
    except Exception:
        pass
    st = _read(_sandbox_state_path(), {}) or {}
    names |= {f"sandbox:{k}".lower() for k in (st.get("systems") or {})} \
        if isinstance(st, dict) else set()
    with contextlib.suppress(OSError):
        names |= {f"sandbox:{p.stem}".lower() for p in
                  (ROOT / "desks" / "mt5" / "research" / "sandboxes").glob("*.py")
                  if p.stem != "__init__"}
    return sorted(names)


def sandbox_cpu_hours(snaps: list[dict[str, Any]], now: datetime
                      ) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """7-day CPU-hours per `sandbox:<id>` from sandbox_runner_state's lifetime compute_spent,
    differenced against the newest daily snapshot at least COMPUTE_WINDOW_D old (scaled to 7
    days). Returns (hours, the updated snapshot list); a system without such a snapshot is absent
    (UNMEASURED), never zero."""
    st = _read(_sandbox_state_path(), {}) or {}
    systems = (st.get("systems") or {}) if isinstance(st, dict) else {}
    cur = {f"sandbox:{k}".lower(): float(v.get("compute_spent") or 0.0)
           for k, v in systems.items() if isinstance(v, dict)
           and isinstance(v.get("compute_spent"), int | float)}
    snaps = [s for s in snaps if isinstance(s, dict) and _parse(s.get("at"))
             and now - _parse(s.get("at")) <= timedelta(days=YIELD_WINDOW_D)]  # type: ignore
    out: dict[str, float] = {}
    old = [s for s in snaps if now - _parse(s["at"]) >= timedelta(  # type: ignore[operator]
        days=COMPUTE_WINDOW_D)]
    if old:
        base = max(old, key=lambda s: s["at"])
        days = (now - _parse(base["at"])).total_seconds() / 86400  # type: ignore[operator]
        for k, v in cur.items():
            b = (base.get("spent") or {}).get(k)
            if isinstance(b, int | float) and v >= b and days > 0:
                out[k] = (v - b) / 3600 * COMPUTE_WINDOW_D / days
    if cur and (not snaps or now - _parse(max(s["at"] for s in snaps))  # type: ignore
                >= timedelta(hours=24)):
        snaps.append({"at": _iso(now), "spent": cur})
    return out, snaps


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
    attrs: dict[str, tuple[str, str, str]] = {}
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
                    attrs[key] = cell_attrs(str(sym), str(fam),
                                            params if isinstance(params, dict) else {}, key)
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
    #: per producer: bucket -> [judged, passed], and the passed cells (for the live-promotion rate)
    buckets: dict[str, dict[str, list[int]]] = {n: {} for n in per}
    combos: dict[str, dict[str, list[int]]] = {n: {} for n in per}
    passed_cells: dict[str, list[list[str]]] = {n: [] for n in per}
    for c, owners in cell_owner.items():
        if c in last:
            v = last[c]
            klass, tf, sess = attrs.get(c, ("unclassified", "H1", ""))
            for name in owners:
                hists[name][v] += 1
                if v == PENDING:
                    continue
                for b in (f"class:{klass}", f"tf:{tf}") + ((f"session:{sess}",) if sess else ()):
                    jp = buckets[name].setdefault(b, [0, 0])
                    jp[0] += 1
                    jp[1] += int(v == PASSED)
                cb = combos[name].setdefault(f"{klass}|{tf}|{sess}|{family_of(c)}", [0, 0])
                cb[0] += 1
                cb[1] += int(v == PASSED)
                if v == PASSED and len(passed_cells[name]) < MAX_PASSED_CELLS:
                    passed_cells[name].append([symbol_of(c), family_of(c), klass, tf, sess])
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
                           "buckets": buckets[name], "passed_cells": passed_cells[name],
                           "combos": combos[name],
                           "families": [f for f, _ in p["families"].most_common(50)],
                           "dominant_family": (p["families"].most_common(1)[0][0]
                                               if p["families"] else None)}
    out.update({"available": True, "producers": producers,
                "registry_rows_scanned_max": MAX_SCAN_ROWS,
                "sample_cells_per_producer": SAMPLE_CELLS_PER_PRODUCER})
    return out


# ------------------------------------------------------------------------- forward and yield

def forward_kept(shadow: Any = None) -> dict[tuple[str, str], str] | None:
    """(symbol, family) -> KEPT / KILLED from the forward clocks; None when unreadable."""
    from libs.research import live_yield as lv
    return lv.read_forward(shadow, path=SHADOW)


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
    from libs.research import live_yield as lv
    recs = lv.read_certificates(prov, path=PROVENANCE)
    if recs is None:
        return None
    out: dict[str, list[dict[str, Any]]] = {}
    for r in recs:
        if r.get("producer"):
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


#: THE LIVE-EDGE SCORE lives in libs/research/live_yield.py (shared desk-wide): expected promoted,
#: fill-proven live edges = certs x p(cert -> kept) x p(kept -> live), each stage shrunk toward
#: the desk-pooled rate below its minimum n; realised live edges dominate once they exist.


def live_sleeves() -> dict[str, dict[str, Any]] | None:
    """LIVE, non-exotic, fill-proven sleeves (libs/research/live_yield.read_live_sleeves)."""
    from libs.research import live_yield as lv
    return lv.read_live_sleeves(sleeves_path=DESK / "data" / "sleeves.json",
                                fills_path=DESK / "data" / "fill_corpus.jsonl",
                                is_exotic=_is_exotic)


def live_edges() -> set[tuple[str, str]] | None:
    sl = live_sleeves()
    return None if sl is None else {(v["symbol"], v["family"]) for v in sl.values()}


def pass_rates(buckets: Any, passed: Any, live: set[tuple[str, str]] | None
               ) -> dict[str, Any] | str:
    """Pass rate (judged cells whose terminal is PASSED / judged) by asset class, session and
    timeframe from the daily diagnosis sample, and the live-promotion rate (passed cells that are
    LIVE and fill-proven / passed) where live is readable. A bucket under MIN_BUCKET_N judged is
    UNMEASURED."""
    if not isinstance(buckets, dict):
        return UNMEASURED
    live_n: Counter[str] = Counter()
    for c in passed or []:
        if live is not None and (c[0], c[1]) in live:
            for b in (f"class:{c[2]}", f"tf:{c[3]}") + ((f"session:{c[4]}",) if c[4] else ()):
                live_n[b] += 1
    out: dict[str, Any] = {}
    for b, (j, k) in sorted(buckets.items()):
        out[b] = {"judged": j, "passed": k,
                  "pass_rate": round(k / j, 6) if j >= MIN_BUCKET_N else UNMEASURED,
                  "live_promotion_rate": (round(live_n[b] / k, 6) if live is not None and k
                                          else UNMEASURED)}
    return out


#: THE STANDING BREADTH PRESSURE: the share of EVERY producer's rows its gap target asks for.
GAP_SHARE = 0.20
SESSIONS = ("asia", "london", "ny")
BASE_TIMEFRAMES = ("M5", "M15", "H1", "H4", "D1")


def coverage_gaps(live_sl: dict[str, dict[str, Any]] | None,
                  clocks: dict[tuple[str, str], str] | None,
                  certs_of: dict[str, list[dict[str, Any]]] | None,
                  diag_p: dict[str, Any]) -> dict[str, Any]:
    """Desk-level gaps: non-exotic asset classes, sessions, timeframes and families with ZERO
    live edges; while live is empty, zero forward-kept; then zero certificates. A dimension the
    basis cannot see (the session of a certificate) is UNMEASURED, never a gap."""
    cells = [str(r["cell"]) for recs in (certs_of or {}).values() for r in recs]
    covered: list[tuple[str, str, str, str]] = []
    if live_sl:
        basis = "LIVE"
        covered = [(asset_class(v["symbol"]), str(v.get("timeframe") or "H1").upper(),
                    session_of(v["family"], {"session": v.get("session")}), v["family"])
                   for v in live_sl.values()]
    else:
        kept = [c for c in cells if clocks and clocks.get((symbol_of(c), family_of(c))) == "KEPT"]
        basis = "FORWARD_KEPT" if kept else "CERTIFIED" if cells else UNMEASURED
        for c in kept or cells:
            k, tf, _ = cell_attrs(symbol_of(c), family_of(c), {}, c)
            covered.append((k, tf, "", family_of(c)))
    classes = sorted(k for k in _all_symbols() if k != "equity")
    fams: set[str] = set()
    tfs: set[str] = set(BASE_TIMEFRAMES)
    for d in diag_p.values():
        fams |= set((d or {}).get("families") or [])
        tfs |= {b[3:] for b in ((d or {}).get("buckets") or {}) if b.startswith("tf:")}
    have = [{x[i] for x in covered} for i in range(4)]
    return {"basis": basis,
            "classes": sorted(set(classes) - have[0]),
            "timeframes": sorted(tfs - have[1]),
            "sessions": (sorted(set(SESSIONS) - have[2]) if basis == "LIVE" else UNMEASURED),
            "families": sorted(fams - have[3])}


def withdraw_prescription(prescriptions: dict[str, Any], name: str, now: datetime,
                          why: str) -> bool:
    """Withdraw a producer's prescription WITHOUT deleting it: the entry stays, marked
    `withdrawn` with when and why, and the withdrawn remedy kept under `previous`. A reader acts
    only on entries without `withdrawn` (`active_prescription`). Never on absence: called only on
    a measured FAILED_REVERTED outcome or a PARK whose evidence was just archived."""
    cur = prescriptions.get(name)
    if not isinstance(cur, dict) or cur.get("withdrawn"):
        return False
    prescriptions[name] = {"withdrawn": True, "withdrawn_at": _iso(now), "why": why,
                           "previous": cur}
    return True


def active_prescription(prescriptions: dict[str, Any], name: str) -> dict[str, Any] | None:
    """The prescription a seat runner should apply, or None when there is none or it was
    withdrawn."""
    cur = prescriptions.get(name)
    return cur if isinstance(cur, dict) and not cur.get("withdrawn") else None


def gap_target(dg: dict[str, Any] | None, gaps: dict[str, Any]) -> dict[str, Any]:
    """The gaps inside a producer's own reach (what it has emitted before), and GAP_SHARE."""
    if not dg:
        return {"status": UNMEASURED, "why": "no diagnosis sample: its reach is unknown",
                "gap_share": GAP_SHARE}
    b = dg.get("buckets") or {}
    reach = {"classes": {x[6:] for x in b if x.startswith("class:")},
             "timeframes": {x[3:] for x in b if x.startswith("tf:")},
             "sessions": {x[8:] for x in b if x.startswith("session:")},
             "families": set(dg.get("families") or [])}
    out: dict[str, Any] = {"gap_share": GAP_SHARE, "basis": gaps.get("basis")}
    for k, r in reach.items():
        g = gaps.get(k)
        out[k] = sorted(r & set(g)) if isinstance(g, list) else UNMEASURED
    return out


def gap_coverage(dg: dict[str, Any] | None, gaps: dict[str, Any],
                 live: set[tuple[str, str]] | None, indep: Any) -> dict[str, Any]:
    """Share of the producer's sampled judged rows that hit a gap, and the pass / live-promotion
    rates on gap rows versus the rest; plus its independence credit."""
    if not dg or not dg.get("combos"):
        return {"status": UNMEASURED, "independence_credit": indep}
    gs = {k: set(v) for k, v in gaps.items() if isinstance(v, list)}

    def hit(klass: str, tf: str, sess: str, fam: str) -> bool:
        return (klass in gs.get("classes", set()) or tf in gs.get("timeframes", set())
                or sess in gs.get("sessions", set()) or fam in gs.get("families", set()))

    tot = [0, 0, 0, 0]          # gap judged, gap passed, other judged, other passed
    for key, (j, k) in dg["combos"].items():
        klass, tf, sess, fam = [*key.split("|"), "", "", "", ""][:4]
        i = 0 if hit(klass, tf, sess, fam) else 2
        tot[i] += j
        tot[i + 1] += k
    lv_hits = [0, 0]
    for c in dg.get("passed_cells") or []:
        if live is not None and (c[0], c[1]) in live:
            lv_hits[0 if hit(c[2], c[3], c[4], c[1]) else 1] += 1
    n = tot[0] + tot[2]
    return {"gap_row_share": round(tot[0] / n, 6) if n else UNMEASURED,
            "gap_pass_rate": round(tot[1] / tot[0], 6) if tot[0] >= MIN_BUCKET_N else UNMEASURED,
            "non_gap_pass_rate": (round(tot[3] / tot[2], 6) if tot[2] >= MIN_BUCKET_N
                                  else UNMEASURED),
            "gap_live_promotion_rate": (round(lv_hits[0] / tot[1], 6)
                                        if live is not None and tot[1] else UNMEASURED),
            "non_gap_live_promotion_rate": (round(lv_hits[1] / tot[3], 6)
                                            if live is not None and tot[3] else UNMEASURED),
            "independence_credit": indep}


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
    lsl = live_sleeves()
    live = None if lsl is None else {(v["symbol"], v["family"]) for v in lsl.values()}
    from libs.research import live_yield as lv
    decay = lv.read_decay(path=DESK / "data" / "decay_live.json")
    cpu = compute_hours()
    yield_names = set(cpu)
    sandbox_cpu, sandbox_snaps = sandbox_cpu_hours(list(state.get("sandbox_cpu") or []), now)
    for k, v in sandbox_cpu.items():
        cpu.setdefault(k, v)        # PRODUCER_YIELD first; sandbox_runner's own clock otherwise
    designs = load_designs()
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
                if st == "KEPT" and live is not None and (symbol_of(c), family_of(c)) in live:
                    pooled["LIVE"] += 1
    desk_keep = (pooled["KEPT"] / (pooled["KEPT"] + pooled["KILLED"])
                 if pooled["KEPT"] + pooled["KILLED"] else None)
    # The smoothed pooled priors of the live-edge score (libs/research/live_yield.pooled).
    ok = certs_of is not None and clocks is not None
    stage_prior = lv.pooled({"desk": {"forward_kept": pooled["KEPT"] if ok else None,
                                "forward_killed": pooled["KILLED"] if ok else None,
                                "live_fill_proven": pooled["LIVE"] if ok and live is not None
                                else None}})
    # EACH PRODUCER'S LIVE EDGES: its KEPT certified cells that trade LIVE and fill-proven. A
    # decaying edge (the decay detector's verdict) earns no persistence credit and is a failure
    # signal for its producer; it is never removed here (retirement stays with the promoter).
    live_of: dict[str, dict[str, dict[str, Any]]] = {}
    if certs_of is not None and clocks is not None and lsl is not None:
        for pname, recs in certs_of.items():
            keys = {(symbol_of(str(r["cell"])), family_of(str(r["cell"]))) for r in recs}
            keys = {k for k in keys if clocks.get(k) == "KEPT"}
            live_of[pname] = {n: v for n, v in lsl.items() if (v["symbol"], v["family"]) in keys}
    persisting = {p_: {(v["symbol"], v["family"], asset_class(v["symbol"]))
                       for n, v in sl_.items() if not (decay or {}).get(n, {}).get("decaying")}
                  for p_, sl_ in live_of.items()}
    live_book = set().union(*persisting.values()) if persisting else set()
    window_start = now - timedelta(days=YIELD_WINDOW_D)
    open_remedy = {n for n, a in hist_all.items()
                   if a and not any(o.get("attempt") == a[-1].get("attempt")
                                    for o in outcomes.get(n, []))}

    names = sorted(set(conv) | set(verdict_of) | set(hist_all) | set(diag_p)
                   | set(certs_of or {}) | {_norm(n) for n in designs}
                   | set(sandbox_cpu))
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
        kept = killed = n_live = 0
        window_cells: list[str] = []
        for rec in mine or []:
            cell = str(rec["cell"])
            sym, fam = symbol_of(cell), family_of(cell)
            st = clocks.get((sym, fam)) if clocks is not None else None
            kept += st == "KEPT"
            killed += st == "KILLED"
            n_live += bool(st == "KEPT" and live is not None and (sym, fam) in live
                           and not _is_exotic(sym))
            born = _parse(rec.get("at"))
            if born and born >= window_start and _tradable(sym, fam) and not _is_exotic(sym):
                window_cells.append(cell)
        keep_rate: float | str = (round(kept / (kept + killed), 4) if kept + killed
                                  else UNMEASURED)
        keep_used = keep_rate if isinstance(keep_rate, float) else desk_keep
        hours = cpu.get(name)
        cpu_window = hours * YIELD_WINDOW_D / COMPUTE_WINDOW_D if hours else None
        keff = k_eff(window_cells) if mine is not None else None
        my_live = live_of.get(name, {})
        decaying = sorted(n for n in my_live if (decay or {}).get(n, {}).get("decaying"))
        indep = lv.independence_credit(persisting.get(name, set()), live_book)
        hl, hl_src = lv.half_life(my_live, decay)
        known = clocks is not None and mine is not None
        score = lv.expected_one(keff, kept if known else None, killed if known else None,
                                n_live if live is not None and known else None, stage_prior,
                                live_credit=indep["credit"] if live is not None else None)
        ev_ = score["expected_live"]
        exp_live: float | None = ev_ if isinstance(ev_, float) else None
        yld: float | str = UNMEASURED
        if exp_live is not None and cpu_window:
            yld = round(exp_live / cpu_window, 8)
        odds = stage_prior.get("p_cert_to_kept"), stage_prior.get("p_kept_to_live")
        s1 = (keff * odds[0] * odds[1] / cpu_window
              if keff is not None and None not in odds and cpu_window else None)  # type: ignore
        el = (lv.realised_elog(my_live, half_life_d=hl, now=now) if my_live
              else {"elog": UNMEASURED if lsl is None else 0.0, "n_trades": 0})
        s3 = (el["elog"] / cpu_window if isinstance(el["elog"], float) and cpu_window
              and el["n_trades"] else None)
        stages = {"certs_odds": s1, "expected_live": yld if isinstance(yld, float) else None,
                  "realised_elog": s3, "n_forward": kept + killed if known else 0,
                  "n_live_trades": int(el.get("n_trades") or 0)}
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
                    withdraw_prescription(prescriptions, name, now, "FAILED_REVERTED")
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
                      "cpu_source": ("PRODUCER_YIELD" if name in yield_names
                                     else "sandbox_runner_state" if name in sandbox_cpu
                                     else UNMEASURED),
                      **score["stage_rates"],
                      "live_edges_realised": score["realised_live"],
                      "expected_live_edges": score["expected_live"],
                      "unmeasured_inputs": score["unmeasured"],
                      "independence_credit": indep["credit"] if live is not None
                      else UNMEASURED,
                      "independence_basis": indep["basis"],
                      "decaying_live_edges": decaying,
                      "half_life_days": hl, "half_life_source": hl_src,
                      "realised_elog": el["elog"],
                      "live_trades": el.get("n_trades", 0),
                      "stage_values": {k: (round(v, 10) if isinstance(v, float) else UNMEASURED)
                                       for k, v in stages.items()
                                       if not k.startswith("n_")},
                      "edges_per_cpu_hour": yld},
            "failed_volume_share": (round((judged - (certs or 0)) / judged, 6)
                                    if judged else UNMEASURED),
            "pass_rate": pass_rates((dg or {}).get("buckets"), (dg or {}).get("passed_cells"),
                                    live),
            "_stages": stages,
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
            withdraw_prescription(prescriptions, name, now, "PARKED")
            r.update({"retest_at": retest, "archive": arch,
                      "reason": f"{len(failed)} failed remedies: parked at the floor "
                                f"weight, evidence archived, re-test {retest[:10]}"})
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

    # R4: TWO-SIDED weights from the STAGED live-yield score (live_yield.blend_stages: certs x
    # odds -> expected live edges -> realised live log-growth, each per CPU-hour, each taking over
    # at its own minimum sample); unmeasured is par, parked is the floor -- never 0, never cut.
    blend = lv.blend_stages({x["producer"]: x.pop("_stages") for x in rows})
    weights: dict[str, Any] = {}
    for x in rows:
        b = blend.get(x["producer"]) or {}
        rel = b.get("relative")
        x["score"] = round(rel, 8) if isinstance(rel, float) else UNMEASURED
        x["yield"]["stage_alphas"] = b.get("alphas")
        y = x["yield"]["edges_per_cpu_hour"]
        if x["status"] == "PARKED":
            w = WEIGHT_MIN
        elif isinstance(rel, float):
            w = min(WEIGHT_MAX, max(WEIGHT_MIN, rel))
        else:
            w = 1.0
        x["weight"] = round(w, 4)
        if w != 1.0:
            weights[x["producer"]] = {"weight": round(w, 4), "yield": y, "status": x["status"]}

    ranked = sorted(rows, key=lambda x: (not isinstance(x["score"], float),
                                         -(x["score"] if isinstance(x["score"], float) else 0.0),
                                         not isinstance(x["certificates_per_candidate"], float),
                                         -(x["certificates_per_candidate"]
                                           if isinstance(x["certificates_per_candidate"], float)
                                           else 0.0), x["producer"]))
    for i, x in enumerate(ranked, 1):
        x["rank"] = i
    census = Counter(x["status"] for x in ranked)
    # ZERO-CERTIFICATE CLASSES: asset classes and timeframes the desk judged and never passed.
    desk_b: dict[str, list[int]] = {}
    for p_ in diag_p.values():
        for b, jk in ((p_ or {}).get("buckets") or {}).items():
            acc = desk_b.setdefault(b, [0, 0])
            acc[0] += int(jk[0])
            acc[1] += int(jk[1])
    zero_cert = sorted(b for b, (j, k) in desk_b.items()
                       if b.startswith(("class:", "tf:")) and j > 0 and k == 0
                       and b != "class:unclassified")
    # STANDING BREADTH PRESSURE on every producer (the judge-side reorder is breadth_fence's, in
    # merge_hypotheses, over all rows): desk gaps, each producer's reachable gap target, and how
    # much of its recent output already lands there.
    gaps = coverage_gaps(lsl, clocks, certs_of, diag_p)
    gap_targets = {x["producer"]: gap_target(diag_p.get(x["producer"]), gaps) for x in rows}
    gap_cov = {x["producer"]: gap_coverage(diag_p.get(x["producer"]), gaps, live,
                                           x["yield"].get("independence_credit"))
               for x in rows}
    # SUCCESSORS (one live per lineage; generations chain; the next untried axis).
    meas = [(x["yield"]["expected_live_edges"], x["yield"]["cpu_hours_window"]) for x in rows
            if isinstance(x["yield"]["expected_live_edges"], float)
            and isinstance(x["yield"]["cpu_hours_window"], float)]
    pooled_yield = (sum(e for e, _ in meas) / sum(h for _, h in meas)
                    if meas and sum(h for _, h in meas) > 0 else None)
    prev_succ = _read(_succ_path(), {}) or {}
    by_name = {x["producer"]: x for x in rows}
    new_designs, succ_report, lineage_trials = plan_successors(
        by_name, designs, now=now, pooled_yield=pooled_yield,
        zero_cert=zero_cert, prev_trials=(prev_succ.get("lineages") or {})
        if isinstance(prev_succ, dict) else {})
    if not apply:
        new_designs = designs
    # THE FEDERATION: every third-party system its own producer, ranked by the same yield.
    roster = sandbox_roster()
    fed = [by_name.get(n) or {"producer": n, "status": UNMEASURED,
                              "yield": {"edges_per_cpu_hour": UNMEASURED}, "weight": 1.0}
           for n in sorted(set(roster) | {n for n in by_name if n.startswith("sandbox:")})]
    fed.sort(key=lambda x: (not isinstance(x.get("score"), float),
                            -(x["score"] if isinstance(x.get("score"), float) else 0.0),
                            x["producer"]))
    federation = [{"rank": i, "producer": x["producer"], "status": x["status"],
                   "weight": x.get("weight", 1.0), "score": x.get("score", UNMEASURED),
                   "edges_per_cpu_hour": x["yield"]["edges_per_cpu_hour"],
                   "expected_live_edges": x["yield"].get("expected_live_edges", UNMEASURED),
                   "live_edges_realised": x["yield"].get("live_edges_realised", UNMEASURED),
                   "cpu_source": x["yield"].get("cpu_source", UNMEASURED)}
                  for i, x in enumerate(fed, 1)]
    doc = {
        "generated_at": _iso(now),
        "law": ("Every producer's funnel (emitted > compiled > judged > certified > forward-kept) "
                "is measured, the stage where it dies is named, and it gets a remedy from a "
                "fixed menu -- never a parameter tweak; remedies are charged to the lifetime "
                "trial ledger, judged held-out or forward only, one at a time against untouched "
                f"controls, reverted when worse, and parked at the floor weight after "
                f"{MAX_ATTEMPTS} failures. "
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
        "yield_metric": ("EXPECTED LIVE EDGES per CPU-hour (libs/research/live_yield): k_eff("
                         f"certified tradable non-exotic edges born in {YIELD_WINDOW_D:g}d) x "
                         "p(cert->forward-kept) x p(kept->LIVE and fill-proven), each stage "
                         "shrunk toward the desk-pooled rate below its minimum n; realised live "
                         "edges dominate once they exist / CPU-hours (7-day measured rate x "
                         f"{YIELD_WINDOW_D / COMPUTE_WINDOW_D:.2f})"),
        "live_inputs": ("READ" if live is not None
                        else f"{UNMEASURED}: sleeves.json / fill_corpus.jsonl"),
        "zero_cert_classes": zero_cert,
        "coverage_gaps": gaps,
        "gap_coverage": gap_cov,
        "successors": succ_report,
        "lineage_trials": lineage_trials,
        "federation": federation,
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
                     "snapshots": new_snaps, "sandbox_cpu": sandbox_snaps}
    doc["_successors"] = {"designs": new_designs, "lineages": lineage_trials}
    doc["_weights"] = weights
    doc["_prescriptions"] = prescriptions
    doc["_gap_target"] = gap_targets
    return doc


def write(doc: dict[str, Any], *, out: Path | None = None) -> dict[str, Any]:
    """Publish the report, the weight and prescription files, the state and the ledger rows."""
    new_state = doc.pop("_state", {})
    weights = doc.pop("_weights", {})
    prescriptions = doc.pop("_prescriptions", {})
    gap_t = doc.pop("_gap_target", {})
    succ = doc.pop("_successors", None)
    _atomic(out or OUT, doc)
    if succ is not None:
        _atomic(_succ_path(), {
            "generated_at": doc["generated_at"],
            "rule": ("a producer PARKED after its failed remedies, or a yield laggard, gets ONE "
                     "live successor designed on the next untried axis; the parent stays at its "
                     "floor weight or above; merge_hypotheses mints the rows (extend_docket)"),
            "axes": list(DESIGN_AXES), "fresh_design_share": FRESH_DESIGN_SHARE,
            **succ})
    _atomic(WEIGHTS, {"generated_at": doc["generated_at"],
                      "rule": ("two-sided producer weights from measured yield (par 1.0 when "
                               "unmeasured, the floor when parked); read by merge_hypotheses "
                               "reweight_rows inside each family's own docket slots -- no row "
                               "removed, the judge's exploration floor untouched"),
                      "producers": weights})
    _atomic(PRESCRIPTIONS, {"generated_at": doc["generated_at"],
                            "rule": "config-level remedies the loop applied; producers and the "
                                    "yield code read this file -- no code is edited",
                            "producers": prescriptions,
                            "gap_target": gap_t})
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
