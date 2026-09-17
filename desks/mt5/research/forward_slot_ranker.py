"""FORWARD SLOT RANKER -- a forward slot is the scarcest thing this desk owns, so price it.

A certificate is cheap: the gauntlet mints them in batches. A FORWARD SLOT is not. Every clock
owes `VERDICT_MIN_DAYS` of wall time and `VERDICT_MIN_TRADES` of forward bars before
`shadow_forward` will rule, and the lanes hold a finite number at once -- so a slot spent on a
cell that matures into nothing is weeks the book did not spend on one that would have moved it.
The lanes enrol by CERTIFICATE ARRIVAL ORDER, a queue and not a ranking, so the scarcest thing on
the desk went first-come-first-served while heat, trials and compute are allocated by dE[log W].
This ranks the queue:

    slot_value = P(certify forward) x dE[log W] x diversification / max(days_to_maturity, 1)

P(CERTIFY), RUNNING: `posterior_alpha.nig_update` on the clock's own forward R, pushed to the
promoter's decision point -- the mature mean is (n xbar + rem mu)/N with rem future trades drawn
at the posterior mu, so P is the normal-approximation probability it clears `PROMOTE_MIN_EXP`. It
rises with n (the no-edge shrink weakens, the remaining noise shrinks) and with the mean, which is
the point; a clock already past `PROMOTE_MIN_DD` is 0, because that bar is monotone and a drawdown
does not un-draw. WAITING: the same bar against the cell's in-sample EV at the dispersion its own
gates imply (sigma = ev / in-sample Sharpe), SHRUNK by the desk's MEASURED in-sample-to-forward
decay -- the fraction of certified cells whose clocks matured positive. Under `DECAY_MIN_N`
matured clocks that fraction is an anecdote, so the prior 0.5 is used AND SAID (L1.28a).

dE[log W]: Kelly-style from the cell's own mean and variance of R. Per-trade Sharpe S at lambda
trades/day is a daily Sharpe S sqrt(lambda), a Kelly bettor's growth at its own optimum is
0.5 S_daily^2 per day, and growth at fraction f of that optimum is f(2 - f) of it -- f_eff being
the MEASURED deployment fraction (`pf_allocation.kelly.kelly_fraction`). THE ALLOCATOR'S OWN
MARGINAL IS PUBLISHED BESIDE IT AND NOT RANKED ON: `marginal_delta_elog` and `admission.
candidates[*].delta_elogw_per_day` are the real thing, a re-solve of both books on sampled worlds,
but exist only for names the allocator has already scanned -- and a table ranked half on a
re-solve and half on an approximation ranks on the BASIS, not on the merit.

DIVERSIFICATION: 1 - max |corr| against every other running clock -- measured daily R from the
forward ledgers where two rows share `MIN_CORR_DAYS` days, else the declared proxy (same
instrument 0.8, same mechanism 0.5), with `exposure_decomposition`'s factor loadings breaking the
different-ticker-same-bet case in between. DAYS_TO_MATURITY: trades owed / the clock's OWN rate,
Jeffreys-smoothed so that no trades yet prices low rather than reading as UNMEASURED, floored by
the days it still owes; a forward t past `SEQ_MIN_T` matures on the sequential route at
`SEQ_MIN_TRADES` and owes the smaller count.

REPLACEABLE IS A REPORT, NEVER AN ACT: a clock earns it only when its slot value is under the best
WAITING candidate's AND its own P(certify) is under `REPLACE_P_MAX`, so evidence is never
displaced by an in-sample story. Each carries a missed-growth line in the ledger's own shape
(day / rail / value / at, log-wealth per day), published HERE and not appended to
`data/missed_growth.jsonl`, whose rows are keyed by rails registered in `libs.portfolio.rails`.
This organ registers no rail, writes nothing to `shadow_state.json`, and stops no clock.

TWO-SIDED, the only reason it may exist (GROWTH_GOVERNANCE 1 and 2): nothing here caps, shrinks,
vetoes or gates; a high slot value is a reason to ENROL MORE, and `capacity.free_slots` exists so
the desk fills its lanes rather than sits on them. A clock whose trade rate cannot be measured is
UNMEASURED, never REPLACEABLE -- a slot taken away on a missing number is taken away for free.

NOT WIRED TO A CLOCK YET (III.16, stated rather than hidden): ships with its test and no scheduler
leg. `python forward_slot_ranker.py` writes the artifact; `--dry-run` prints only. numpy only.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:                                                  # the desk's own posterior, reused whole
    _pa = importlib.import_module("research.posterior_alpha")
except ImportError:                                   # script entry point on the box
    _pa = importlib.import_module("posterior_alpha")

SHADOW_DIR = BASE / "reports" / "shadow"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
ALLOCATION = BASE / "reports" / "pf_allocation.json"
EXPOSURE = BASE / "reports" / "EXPOSURE_DECOMPOSITION.json"
CAPACITY_FILE = BASE / "data" / "forward_capacity.json"
SHADOW_FORWARD_SRC = BASE / "research" / "shadow_forward.py"
OUT = BASE / "reports" / "FORWARD_SLOT_RANKER.json"

UNMEASURED = "UNMEASURED"
#: Lane -> its clock state file, resolved against SHADOW_DIR at CALL time so a test can move it.
LANE_FILES = {"shadow": "shadow_state.json", "qquant": "qquant_shadow_state.json",
              "scalp": "scalp_shadow_state.json", "external": "external_shadow_state.json"}
#: A clock that still OCCUPIES a slot. A matured row has ruled, and is counted toward the decay.
RUNNING_STATUSES = ("ACTIVE",)
MATURED_POSITIVE = ("PROMOTION CANDIDATE", "PROMOTED", "LIVE", "ALLOCATED", "DEPLOYED")
MATURED_NEGATIVE = ("KILL", "KILLED", "REJECTED", "DEAD", "RETIRED_GATE_FAIL")
#: `shadow_forward`'s own bars, read from its SOURCE rather than imported: importing it opens a
#: log file, makes directories and pulls in pandas and the family registry, none of which a
#: ranking pass should cause. Parsed, so the two cannot drift; literals only if parsing fails.
FALLBACK_THRESHOLDS = {"VERDICT_MIN_TRADES": 50.0, "VERDICT_MIN_DAYS": 14.0,
                       "PROMOTE_MIN_EXP": 0.05, "PROMOTE_MIN_DD": -25.0,
                       "SEQ_MIN_TRADES": 20.0, "SEQ_MIN_T": 2.5}
#: Matured clocks needed before "fraction that matured positive" is a measurement and not an
#: anecdote; below it the decay is the prior and the basis says UNMEASURED.
DECAY_MIN_N, PRIOR_DECAY = 10, 0.5
#: REPLACEABLE needs BOTH: dominated on value AND a posterior this weak. Never either alone.
REPLACE_P_MAX = 0.30
#: The declared correlation proxy where no shared daily-R history exists.
SAME_SYMBOL_CORR, SAME_FAMILY_CORR, MIN_CORR_DAYS = 0.8, 0.5, 10
#: One unit of risk: an R-multiple's natural dispersion when nothing measures it. The two
#: fallbacks are uniform scales -- they move magnitudes, never the ranking. RATE_SMOOTHING is the
#: Jeffreys half-event that keeps a clock with no trades yet finite and rankable.
DEFAULT_SIGMA_R, FALLBACK_TRADE_RATE, FALLBACK_KELLY_FRACTION = 1.0, 1.0, 1.0
#: Jeffreys half-event, and the floor under the days it is divided by.
RATE_SMOOTHING, MIN_ELAPSED_DAYS = 0.5, 1.0

RULE = ("a forward slot goes to the clock most likely to move the book soonest; replacement is "
        "reported with its missed-growth line, never executed here")


# --------------------------------------------------------------------------- tolerant readers
def _read_text(path: Path) -> str:
    try:
        return Path(path).read_text("utf-8-sig")
    except OSError:
        return ""


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(_read_text(path))
    except ValueError:
        return default


def _f(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    out = float(value)
    return out if math.isfinite(out) else default


def _phi(z: float) -> float:
    """Standard normal CDF. stdlib only -- the desk ships no scipy."""
    if not math.isfinite(z):
        return 1.0 if z > 0 else 0.0
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def _elapsed_days(value: Any, now: datetime) -> float:
    """Fractional days since a stamp. `shadow_forward` writes `days_active` as a whole number, so
    a clock stamped 14 hours ago reads 0 there and would divide a trade rate by zero -- measured
    2026-09-17, 142 of 148 running clocks were re-stamped inside two days and read exactly 0."""
    try:
        started = datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return 0.0
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return max((now - started).total_seconds() / 86400.0, 0.0)


def maturity_thresholds() -> dict[str, Any]:
    """`shadow_forward`'s promotion bars, read out of its source by AST -- never imported."""
    out: dict[str, Any] = dict(FALLBACK_THRESHOLDS)
    try:
        tree = ast.parse(Path(SHADOW_FORWARD_SRC).read_text("utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {**out, "basis": "fallback_literals"}
    for node in tree.body:
        for target in getattr(node, "targets", []):
            if isinstance(target, ast.Name) and target.id in FALLBACK_THRESHOLDS:
                with contextlib.suppress(ValueError, TypeError):
                    out[target.id] = float(ast.literal_eval(node.value))
    return {**out, "basis": f"parsed:{Path(SHADOW_FORWARD_SRC).name}"}


# -------------------------------------------------------------------------------- the evidence
@dataclass
class Row:
    """One slot-holder or slot-seeker, with everything the value needs and where it came from."""

    kind: str                       # "running" | "waiting"
    key: str
    lane: str
    symbol: str
    family: str
    selector: str = ""
    status: str = ""
    n: float = 0.0
    days_active: float = 0.0
    mean_r: float | None = None
    sigma_r: float | None = None
    sharpe: float | None = None
    sharpe_basis: str = UNMEASURED
    forward_t: float = 0.0
    max_dd: float | None = None
    r_by_day: dict[str, float] = field(default_factory=dict)


def _identity(key: str, row: dict, specs: dict[str, dict]) -> tuple[str, str, str]:
    """(symbol, family, selector). The certificate's own spec wins, then the row, then the key."""
    spec = specs.get(key) or {}
    parts = str(key).split("#", 1)[0].split(".")
    symbol = str(spec.get("symbol") or row.get("symbol") or row.get("sym") or "") or parts[0]
    family = str(spec.get("family") or row.get("family") or "") or _pa._family_of_key(key)
    selector = str(spec.get("selector") or row.get("selector") or row.get("window") or "")
    if not selector:
        selector = parts[2] if len(parts) >= 3 else (parts[1] if len(parts) == 2 else "")
    return symbol, family, selector


def lane_states() -> dict[str, dict[str, dict]]:
    """Every lane's clock rows, lane -> key -> row. The files' meta keys are dropped."""
    out: dict[str, dict[str, dict]] = {}
    for lane, name in LANE_FILES.items():
        raw = _read_json(Path(SHADOW_DIR) / name)
        rows = ({str(k): v for k, v in raw.items() if isinstance(v, dict) and "status" in v}
                if isinstance(raw, dict) else {})
        if rows:
            out[lane] = rows
    return out


def forward_days(key: str) -> dict[str, float]:
    """A clock's FORWARD-phase daily R. Historical rows predate pre-registration and are excluded
    from every threshold on this desk, so they are excluded from the correlation too."""
    ledger = _read_json(Path(SHADOW_DIR) / f"ledger_{str(key).replace('.', '_')}.json", [])
    days: dict[str, float] = {}
    for trade in ledger if isinstance(ledger, list) else []:
        if not isinstance(trade, dict) or str(trade.get("phase") or "") != "forward":
            continue
        value = _f(trade.get("r_multiple"))
        stamp = _day(trade.get("exit_time") or trade.get("entry_time"))
        if value is not None and stamp is not None:
            days[stamp.isoformat()] = days.get(stamp.isoformat(), 0.0) + value
    return days


def running_rows(states: dict[str, dict[str, dict]], specs: dict[str, dict],
                 now: datetime) -> list[Row]:
    """Every clock still occupying a slot, with its forward moments and its daily R."""
    out: list[Row] = []
    for lane, rows in states.items():
        for key, raw in rows.items():
            if str(raw.get("status") or "").upper() not in RUNNING_STATUSES:
                continue
            symbol, family, selector = _identity(key, raw, specs)
            elapsed = max(_f(raw.get("days_active"), 0.0) or 0.0,
                          _elapsed_days(raw.get("forward_start") or raw.get("first_entry"), now))
            row = Row("running", key, lane, symbol, family, selector,
                      status=str(raw.get("status") or ""), n=_f(raw.get("n"), 0.0) or 0.0,
                      days_active=elapsed,
                      mean_r=_f(raw.get("exp_r")), forward_t=_f(raw.get("forward_t"), 0.0) or 0.0,
                      max_dd=_f(raw.get("max_dd_r")))
            row.r_by_day = forward_days(key)
            if row.mean_r is None and row.r_by_day:
                row.mean_r = float(np.mean(list(row.r_by_day.values())))
            out.append(row)
    return out


def waiting_rows(states: dict[str, dict[str, dict]], survivors: dict[str, dict],
                 notes: list[str]) -> list[Row]:
    """Certified cells with no clock anywhere. A cell already enrolled is not waiting for a slot:
    it HAS one, and is ranked in `running` on its forward evidence instead.

    Its sigma is IMPLIED by its own gates -- ev / in-sample Sharpe is the dispersion those two
    numbers were computed on -- so nothing is imputed while the cell itself can answer.
    """
    enrolled = {str(k).split("#", 1)[0] for rows in states.values() for k in rows}
    enrolled |= {str(k) for rows in states.values() for k in rows}
    out, unpriced = [], 0
    for key, cell in survivors.items():
        spec = cell.get("shadow_spec") or {}
        symbol = str(spec.get("symbol") or cell.get("sym") or "")
        family, selector = str(spec.get("family") or ""), str(spec.get("selector") or "")
        stem = f"{symbol}.{family}.{selector}"
        if {stem, f"{symbol}.{selector}", str(key)} & enrolled or any(
                name.startswith(stem) for name in enrolled):
            continue
        gates = cell.get("gates") or {}
        ev = _f((gates.get("expected_value") or {}).get("ev"))
        basis = next((f"{g}.{n}" for g, n in (("cpcv", "mean_oos_sharpe"),
                                              ("walk_forward", "oos_sharpe"),
                                              ("lockbox", "lockbox_sharpe"),
                                              ("in_sample_screen", "sharpe"))
                      if _f((gates.get(g) or {}).get(n)) is not None), UNMEASURED)
        in_sample = _f((gates.get("in_sample_screen") or {}).get("sharpe"))
        if ev is None or basis == UNMEASURED:
            unpriced += 1
            continue
        sigma = abs(ev) / abs(in_sample) if in_sample else DEFAULT_SIGMA_R
        sigma = sigma or DEFAULT_SIGMA_R
        out.append(Row("waiting", str(key), "unenrolled", symbol, family, selector,
                       status="CERTIFIED", mean_r=ev, sigma_r=sigma, sharpe=ev / sigma,
                       sharpe_basis=basis))
    if unpriced:
        notes.append(f"{unpriced} certified cell(s) carry no ev/Sharpe pair and cannot be priced: "
                     f"counted, never guessed")
    return out


# ----------------------------------------------------------------- the four terms of the value
def required_trades(row: Row, th: dict[str, Any]) -> float:
    """What the clock still owes. A forward t past SEQ_MIN_T matures on the sequential route at
    SEQ_MIN_TRADES; everything else pays the flat count."""
    if row.kind != "running" or row.forward_t < th["SEQ_MIN_T"]:
        return float(th["VERDICT_MIN_TRADES"])
    return max(row.n, float(th["SEQ_MIN_TRADES"]))


def p_certify_running(row: Row, th: dict[str, Any]) -> tuple[float, str]:
    """P(the mature clock clears the promoter's bar) -- NIG posterior, normal remaining trades."""
    if row.max_dd is not None and row.max_dd <= th["PROMOTE_MIN_DD"]:
        return 0.0, "max_dd already past the promoter's bar, and a drawdown does not un-draw"
    values = np.asarray(list(row.r_by_day.values()), dtype=float)
    mean = row.mean_r if row.mean_r is not None else (float(values.mean()) if values.size else 0.0)
    sumsq = (float(((values - values.mean()) ** 2).sum()) if values.size >= 2
             else max(row.n - 1.0, 0.0) * DEFAULT_SIGMA_R ** 2)   # dispersion IMPUTED, and said
    summary = _pa.summarise(_pa.nig_update(row.n, mean, sumsq, sigma0=DEFAULT_SIGMA_R))
    mu_n = _f(summary["mu_mean"], 0.0) or 0.0
    mu_sd = _f(summary["mu_sd"], DEFAULT_SIGMA_R) or DEFAULT_SIGMA_R
    sigma = _f(summary["sigma_mean"], DEFAULT_SIGMA_R) or DEFAULT_SIGMA_R
    row.sigma_r, row.sharpe = sigma, (mu_n / sigma if sigma > 0 else None)
    row.sharpe_basis = "posterior_alpha.nig_update on forward R"
    total = max(required_trades(row, th), row.n, 1.0)
    rem = max(total - row.n, 0.0)
    mature = (row.n * mean + rem * mu_n) / total
    var = (rem / total) ** 2 * mu_sd ** 2 + sigma ** 2 * rem / total ** 2
    if var <= 0:
        return (1.0 if mature > th["PROMOTE_MIN_EXP"] else 0.0), "no remaining uncertainty"
    return (round(_phi((mature - th["PROMOTE_MIN_EXP"]) / math.sqrt(var)), 6),
            f"NIG posterior pushed to n={total:.0f}, normal remainder")


def p_certify_waiting(row: Row, th: dict[str, Any], decay: float) -> tuple[float, str]:
    """In-sample EV against the same bar, shrunk by the desk's measured forward-decay base rate."""
    if row.mean_r is None:
        return 0.0, UNMEASURED
    sd = (row.sigma_r or DEFAULT_SIGMA_R) / math.sqrt(max(float(th["VERDICT_MIN_TRADES"]), 1.0))
    raw = (_phi((row.mean_r - th["PROMOTE_MIN_EXP"]) / sd) if sd > 0
           else float(row.mean_r > th["PROMOTE_MIN_EXP"]))
    return round(raw * decay, 6), f"in-sample ev vs the bar x measured decay {decay:.3f}"


def rate_and_days(row: Row, th: dict[str, Any],
                  median_rate: float | None) -> tuple[float | None, str, float | str, float]:
    """(trades/day, its basis, wall-clock days until the promoter can rule, trades still owed).

    A RUNNING clock is timed on its OWN rate and nothing else: it has had its days, and lending it
    the lane's median would credit it with trades it has not made. ZERO TRADES IN D DAYS IS A
    MEASUREMENT, NOT AN ABSENCE, so the rate is Jeffreys-smoothed to (n + 0.5)/days -- a barren
    clock then prices low and stays rankable instead of hiding behind UNMEASURED, which would
    shelter precisely the slots most worth reporting. Measured 2026-09-17: 142 of 149 running
    clocks carry n = 0, so the unsmoothed rule made the artifact almost entirely UNMEASURED. Only
    a clock with no elapsed days at all has nothing to measure. A WAITING candidate has no clock,
    so the lane's median is the only honest estimate. Both bars bind, so the wait is the LONGER of
    the trades owed and the days owed.
    """
    if row.kind == "running":
        # MIN_ELAPSED_DAYS floors the denominator: a clock stamped an hour ago would otherwise
        # post a rate of hundreds of trades a day off its half-event and rank above everything.
        # The floor can only LOWER a young clock's rate, never inflate one.
        rate = ((row.n + RATE_SMOOTHING) / max(row.days_active, MIN_ELAPSED_DAYS)
                if row.days_active > 0 else None)
        basis = (UNMEASURED if rate is None else
                 f"measured on this clock, Jeffreys-smoothed (n + {RATE_SMOOTHING})/days")
    elif median_rate and median_rate > 0:
        rate, basis = median_rate, "median measured rate across running clocks"
    else:
        rate, basis = None, UNMEASURED
    done = row.n if row.kind == "running" else 0.0
    owed = max(required_trades(row, th) - done, 0.0)
    elapsed = row.days_active if row.kind == "running" else 0.0
    by_days = max(float(th["VERDICT_MIN_DAYS"]) - elapsed, 0.0)
    if rate is None or rate <= 0:
        return rate, basis, (UNMEASURED if owed > 0 else round(by_days, 3)), owed
    return rate, basis, round(max(owed / rate, by_days), 3), owed


def delta_elogw(sharpe: float | None, rate: float | None, f_eff: float) -> float | str:
    """Kelly-style marginal growth from the cell's own mean/variance of R.

    Per-trade Sharpe S at lambda trades a day is a daily Sharpe S sqrt(lambda); a Kelly bettor's
    growth at its own optimum is 0.5 S_daily^2 per day, and growth at fraction f of that optimum
    is f(2 - f) of it. A negative Sharpe earns no heat from an optimiser that cannot short the
    sleeve, so it floors at zero rather than sign-flipping into a bet the desk cannot take.
    """
    if sharpe is None or rate is None or rate <= 0:
        return UNMEASURED
    s_daily = max(sharpe, 0.0) * math.sqrt(rate)
    return round(f_eff * (2.0 - f_eff) * 0.5 * s_daily ** 2, 12)


def _exposure_vectors() -> dict[str, np.ndarray]:
    """symbol -> its factor loading vector, reused from `exposure_decomposition`'s own report."""
    report = _read_json(EXPOSURE)
    factors = [str(f) for f in ((report or {}).get("factors") or [])] if isinstance(
        report, dict) else None
    out: dict[str, np.ndarray] = {}
    for sleeve in (report or {}).get("sleeves") or [] if isinstance(report, dict) else []:
        symbol = str(sleeve.get("symbol") or "") if isinstance(sleeve, dict) else ""
        exposures = sleeve.get("exposures") if isinstance(sleeve, dict) else None
        if not symbol or symbol in out or not isinstance(exposures, dict):
            continue
        vector = np.asarray([_f(exposures.get(n), 0.0) or 0.0
                             for n in (factors or sorted(exposures))], dtype=float)
        if float(np.linalg.norm(vector)) > 0:
            out[symbol] = vector
    return out


def pair_corr(a: Row, b: Row, vectors: dict[str, np.ndarray]) -> tuple[float, str]:
    """Correlation of two rows: measured daily R, else the declared instrument/mechanism proxy,
    with the factor cosine breaking the different-ticker-same-bet case in between."""
    common = sorted(set(a.r_by_day) & set(b.r_by_day))
    if len(common) >= MIN_CORR_DAYS:
        x = np.asarray([a.r_by_day[d] for d in common], dtype=float)
        y = np.asarray([b.r_by_day[d] for d in common], dtype=float)
        if x.std() > 0 and y.std() > 0:
            return round(float(np.corrcoef(x, y)[0, 1]), 6), "daily_r"
    if a.symbol and a.symbol == b.symbol:
        return SAME_SYMBOL_CORR, "same_symbol"
    va, vb = vectors.get(a.symbol), vectors.get(b.symbol)
    if va is not None and vb is not None and va.size == vb.size:
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom > 0:
            return round(float(va @ vb) / denom, 6), "factor_exposure"
    if a.family and a.family == b.family:
        return SAME_FAMILY_CORR, "same_family"
    return 0.0, "unrelated"


def diversification(row: Row, running: list[Row],
                    vectors: dict[str, np.ndarray]) -> tuple[float, float, str, str]:
    """1 - max |corr| against the clocks already running. Alone in the book is a full 1.0."""
    worst, against, basis = 0.0, "", "no other running clock"
    for other in running:
        if other is row or other.key == row.key:
            continue
        value, how = pair_corr(row, other, vectors)
        if abs(value) > abs(worst):
            worst, against, basis = value, other.key, how
    return round(max(0.0, 1.0 - abs(worst)), 6), round(worst, 6), against, basis


# ------------------------------------------------------------------------------ decay, capacity
def measure_decay(states: dict[str, dict[str, dict]]) -> dict[str, Any]:
    """The desk's in-sample-to-forward decay: of the certified cells whose clocks have RULED, what
    fraction ruled positive -- the gate ledger's `downstream_status` where it carries one, and the
    clocks' own terminal verdicts. Under DECAY_MIN_N that is an anecdote, so the prior is used and
    NAMED: a base rate invented from two clocks would price every waiting candidate on this desk.
    """
    ledger: list[dict] = []
    for line in _read_text(GATE_LEDGER).splitlines():
        with contextlib.suppress(ValueError):
            row = json.loads(line.strip() or "0")
            if isinstance(row, dict):
                ledger.append(row)
    counts = {"ledger": 0, "clocks": 0}
    matured = positive = 0
    for source, names in (
            ("ledger", [str(r.get("downstream_status") or "").upper() for r in ledger]),
            ("clocks", [str(r.get("status") or "").upper()
                        for rows in states.values() for r in rows.values()])):
        for status in names:
            if any(status.startswith(good) for good in MATURED_POSITIVE):
                matured, positive, counts[source] = matured + 1, positive + 1, counts[source] + 1
            elif any(status.startswith(bad) for bad in MATURED_NEGATIVE):
                matured, counts[source] = matured + 1, counts[source] + 1
    if matured < DECAY_MIN_N:
        return {"decay": PRIOR_DECAY, "basis": UNMEASURED, "n_matured": matured,
                "n_positive": positive, "min_n": DECAY_MIN_N,
                "why": f"{matured} matured clock(s) is under the {DECAY_MIN_N} this desk needs "
                       f"before a base rate is a measurement; the prior {PRIOR_DECAY} is used"}
    return {"decay": round(positive / matured, 6), "basis": "measured", "n_matured": matured,
            "n_positive": positive, "from_gate_ledger": counts["ledger"],
            "from_clocks": counts["clocks"],
            "why": "fraction of matured forward clocks that ruled positive"}


def measure_capacity(states: dict[str, dict[str, dict]], today: date) -> dict[str, Any]:
    """Slots per lane. A declared file wins; otherwise the MEASURED historical peak concurrency.

    A lane whose rows carry no `forward_start` has UNMEASURED capacity: it has not told the desk
    how many it can hold, and a 0 would read as a measurement that the lane holds nothing.
    """
    declared = _read_json(CAPACITY_FILE)
    declared = declared if isinstance(declared, dict) else {}
    declared = declared["capacity"] if isinstance(declared.get("capacity"), dict) else declared
    out: dict[str, Any] = {}
    for lane, rows in states.items():
        deltas: dict[date, int] = {}
        seen = live = 0
        for raw in rows.values():
            running = str(raw.get("status") or "").upper() in RUNNING_STATUSES
            live += running
            start = _day(raw.get("forward_start") or raw.get("first_entry"))
            if start is None:
                continue
            seen += 1
            end = today if running else (_day(raw.get("last_entry"))
                                         or _day(raw.get("last_attempt_at")) or start)
            end = max(end or start, start) + timedelta(days=1)
            deltas[start] = deltas.get(start, 0) + 1
            deltas[end] = deltas.get(end, 0) - 1
        block: dict[str, Any] = {"running_now": live, "n_clocks_with_a_start": seen,
                                 "n_rows": len(rows)}
        declared_n = _f(declared.get(lane))
        if declared_n is not None:
            block.update(capacity=int(declared_n), basis=f"declared:{CAPACITY_FILE.name}",
                         free_slots=int(declared_n) - live)
        elif not deltas:
            block.update(capacity=UNMEASURED, basis=UNMEASURED, free_slots=UNMEASURED,
                         why="no clock in this lane carries a forward_start")
        else:
            peak, at_peak, concurrent = 0, None, 0
            for stamp in sorted(deltas):
                concurrent += deltas[stamp]
                if concurrent > peak:
                    peak, at_peak = concurrent, stamp
            block.update(capacity=peak, basis="measured_max_concurrent",
                         peak_on=at_peak.isoformat() if at_peak else UNMEASURED,
                         free_slots=peak - live)
        out[lane] = block
    return out


# ------------------------------------------------------------------------------------- the pass
def _publish(row: Row, p: tuple[float, str], rate: tuple[float | None, str],
             days: float | str, owed: float, d_elog: float | str,
             div: tuple[float, float, str, str], allocator: float | None) -> dict[str, Any]:
    """One ranked row, with every term beside the source it came from."""
    denom = max(days, 1.0) if isinstance(days, float) else None
    out: dict[str, Any] = {
        "lane": row.lane, "symbol": row.symbol, "family": row.family, "selector": row.selector,
        "status": row.status, "n": int(row.n), "p_certify": p[0], "p_certify_basis": p[1],
        "trades_owed": round(owed, 2), "trade_rate_basis": rate[1],
        "trade_rate_per_day": round(rate[0], 4) if rate[0] else UNMEASURED,
        "days_to_maturity": days,
        "mean_r": round(row.mean_r, 6) if row.mean_r is not None else UNMEASURED,
        "sigma_r": round(row.sigma_r, 6) if row.sigma_r is not None else UNMEASURED,
        "sharpe_per_trade": round(row.sharpe, 6) if row.sharpe is not None else UNMEASURED,
        "sharpe_basis": row.sharpe_basis, "delta_elogw": d_elog,
        "delta_elogw_allocator": allocator if allocator is not None else UNMEASURED,
        "diversification": div[0], "max_corr": div[1], "max_corr_with": div[2] or UNMEASURED,
        "max_corr_basis": div[3],
        "slot_value": (round(p[0] * d_elog * div[0] / denom, 14)
                       if denom is not None and isinstance(d_elog, float) else UNMEASURED),
    }
    if row.kind == "running":
        out.update(days_active=round(row.days_active, 2), forward_t=round(row.forward_t, 3),
                   max_dd_r=round(row.max_dd, 4) if row.max_dd is not None else UNMEASURED)
    return out


def _value(entry: dict[str, Any]) -> float:
    raw = entry.get("slot_value")
    return float(raw) if isinstance(raw, float) else -1.0


def run(write: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """Rank every slot the desk holds and every one it could hold, and price the difference."""
    stamp = now or datetime.now(UTC)
    notes: list[str] = []
    th = maturity_thresholds()
    states = lane_states()
    if not states:
        notes.append(f"no lane state file readable under {SHADOW_DIR}: nothing holds a slot")
    raw_surv = _read_json(SURVIVORS)
    survivors = {str(k): v for k, v in
                 ((raw_surv.get("survivors") or {}) if isinstance(raw_surv, dict) else {}).items()
                 if isinstance(v, dict)}
    if not survivors:
        notes.append(f"no certified cells readable: {SURVIVORS}")

    alloc = _read_json(ALLOCATION) or {}
    f_eff = _f((alloc.get("kelly") or {}).get("kelly_fraction"))
    kelly_basis = "pf_allocation.kelly.kelly_fraction"
    if f_eff is None or not 0.0 < f_eff <= 1.0:
        f_eff, kelly_basis = FALLBACK_KELLY_FRACTION, f"fallback {FALLBACK_KELLY_FRACTION} (full)"
        notes.append("deployment fraction f_eff UNMEASURED: full Kelly used as the uniform scale, "
                     "which moves every magnitude alike and no ranking")
    marginals = {str(k): v for k, v in (alloc.get("marginal_delta_elog") or {}).items()}
    for name, cand in ((alloc.get("admission") or {}).get("candidates") or {}).items():
        value = _f(cand.get("delta_elogw_per_day")) if isinstance(cand, dict) else None
        if value is not None:
            marginals.setdefault(str(name), value)

    specs = {k: (v.get("shadow_spec") or {}) for k, v in survivors.items()}
    running = running_rows(states, specs, stamp)
    waiting = waiting_rows(states, survivors, notes)
    decay = measure_decay(states)
    vectors = _exposure_vectors()
    if not vectors:
        notes.append(f"factor exposures absent: {EXPOSURE} -- correlation falls to the "
                     f"instrument/mechanism proxy wherever no daily R overlaps")
    rates = [r.n / r.days_active for r in running if r.n > 0 and r.days_active > 0]
    median_rate = float(np.median(rates)) if rates else FALLBACK_TRADE_RATE
    if not rates:
        notes.append("no running clock measures a trade rate: waiting candidates are timed at "
                     f"the declared fallback of {FALLBACK_TRADE_RATE}/day")

    def _rank(rows: list[Row], label: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            p = (p_certify_running(row, th) if row.kind == "running"
                 else p_certify_waiting(row, th, float(decay["decay"])))
            rate, rate_basis, days, owed = rate_and_days(row, th, median_rate)
            name = "_".join(part for part in (row.symbol, row.family, row.selector) if part)
            out.append({label: row.key, **_publish(
                row, p, (rate, rate_basis), days, owed, delta_elogw(row.sharpe, rate, f_eff),
                diversification(row, running, vectors), _f(marginals.get(name)))})
        out.sort(key=lambda e: (-_value(e), -float(e["p_certify"]), str(e[label])))
        return out

    ranked_running, ranked_waiting = _rank(running, "clock"), _rank(waiting, "cell")
    best = ranked_waiting[0] if ranked_waiting else None
    replaceable: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    for entry in ranked_running:
        dominated = best is not None and _value(entry) < _value(best)
        weak = float(entry["p_certify"]) < REPLACE_P_MAX
        if not isinstance(entry.get("slot_value"), float):
            entry.update(verdict=UNMEASURED, why="no measured trade rate, so no maturity date and "
                         "no slot value: a slot is never taken away on an absent number")
        elif best is None:
            entry.update(verdict="KEEP",
                         why="no certified cell is waiting: nothing to be dominated by")
        elif dominated and weak:
            entry.update(verdict="REPLACEABLE",
                         why=(f"slot value {_value(entry):.3e} under the waiting {best['cell']} "
                              f"at {_value(best):.3e}, and P(certify) "
                              f"{float(entry['p_certify']):.3f} < {REPLACE_P_MAX}"))
            replaceable.append(entry)
            lines.append({
                "day": stamp.date().isoformat(), "at": stamp.isoformat(),
                "rail": f"forward_slot_occupancy:{entry['clock']}", "kind": "opportunity_cost",
                "value": round(-(_value(best) - _value(entry)), 14),
                "units": "E[log W] per day of book growth, per day of forward wait",
                "clock": entry["clock"], "lane": entry["lane"], "challenger": best["cell"],
                "p_certify": entry["p_certify"],
                "why": ("what holding this forward slot costs against the best waiting "
                        "certificate; PUBLISHED, never appended to data/missed_growth.jsonl and "
                        "never executed -- this organ registers no rail and stops no clock")})
        else:
            entry.update(verdict="KEEP",
                         why=("dominated on value but P(certify) still above the bar" if dominated
                              else "slot value at or above every waiting candidate"))

    payload = {
        "at": stamp.isoformat(), "rule": RULE,
        "capacity": measure_capacity(states, stamp.date()), "thresholds": th,
        "kelly_fraction": {"f_eff": round(f_eff, 6), "basis": kelly_basis,
                           "growth_factor": round(f_eff * (2.0 - f_eff), 6)},
        "decay_measured": decay, "n_running": len(ranked_running),
        "n_waiting": len(ranked_waiting), "n_replaceable": len(replaceable),
        "median_trade_rate_per_day": round(median_rate, 4),
        "running": ranked_running, "waiting": ranked_waiting, "replaceable": replaceable,
        "missed_growth_lines": lines, "unmeasured": notes,
        "formula": ("slot_value = P(certify forward) x dE[log W] x diversification / "
                    "max(days_to_maturity, 1); dE[log W] = f_eff (2 - f_eff) 0.5 "
                    "(sharpe_per_trade sqrt(trades_per_day))^2"),
        "inputs": {str(p): ("present" if Path(p).exists() else "absent")
                   for p in (SURVIVORS, GATE_LEDGER, ALLOCATION, EXPOSURE, CAPACITY_FILE,
                             Path(SHADOW_DIR) / LANE_FILES["shadow"])},
    }
    if write:
        _write_atomic(OUT, payload)
    return payload


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                  # a read-only destination is WinError 5 on this box
        path.chmod(0o644)
        os.replace(tmp, path)


def _cell(value: Any, width: int = 8) -> str:
    if isinstance(value, float):
        return f"{value:>{width}.4g}"
    return f"{('--' if value == UNMEASURED else str(value))[:width]:>{width}}"


def render(payload: dict[str, Any], limit: int = 20) -> str:
    """The table a human reads: the slots the desk holds, then the ones it could."""
    decay = payload["decay_measured"]
    lines = [f"FORWARD SLOT RANKER  running={payload['n_running']} "
             f"waiting={payload['n_waiting']} replaceable={payload['n_replaceable']}  "
             f"decay={decay['decay']} ({decay['basis']})"]
    lines += [f"  lane {lane:10s} capacity={b['capacity']} running={b['running_now']} "
              f"free={b['free_slots']} [{b['basis']}]" for lane, b in payload["capacity"].items()]
    lines.append(f"  {'row':34s} {'n':>4s} {'P(cert)':>8s} {'days':>8s} {'dElogW':>8s} "
                 f"{'div':>8s} {'value':>10s}  verdict")
    for key, label in (("running", "clock"), ("waiting", "cell")):
        for e in payload[key][:limit]:
            name = (str(e[label]) if key == "running" else "WAIT " + str(e[label]))[:34]
            lines.append(f"  {name:34s} {e['n']:>4d} {_cell(e['p_certify'])} "
                         f"{_cell(e['days_to_maturity'])} {_cell(e['delta_elogw'])} "
                         f"{_cell(e['diversification'])} {_cell(e['slot_value'], 10)}  "
                         f"{e.get('verdict', '')}")
        if len(payload[key]) > limit:
            lines.append(f"  ... {len(payload[key]) - limit} more {key} rows in the artifact")
    lines += [f"  MISSED GROWTH  {ln['rail']} {ln['value']:+.4g} vs {ln['challenger']}"
              for ln in payload["missed_growth_lines"]]
    return "\n".join(lines + [f"  UNMEASURED  {note}" for note in payload["unmeasured"]])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rank forward-test slots by expected slot value.")
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    ap.add_argument("--limit", type=int, default=20, help="rows in the printed table")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run)
    print(render(payload, limit=args.limit))
    print("(dry run, nothing written)" if args.dry_run else f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
