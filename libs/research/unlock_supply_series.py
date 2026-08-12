"""STAGE-A SCREEN CORE: mechanical supply release as a SCHEDULE-SERIES, not a snapshot (census gap
#3, `mechanical_supply_release`, gap_score 0.360, coverage TESTED-SHALLOW).

=============================================================================================
PRE-REGISTRATION.  Written before any number was computed; nothing below is chosen after
looking at a result.  Read this as the contract the code is held to.
=============================================================================================

MECHANISM -- WHO PAYS WHOM, AND WHY IT PERSISTS
    A vesting cliff hands tokens to an insider, a private-sale allocator or a miner whose cost
    basis is ~zero and whose fund lifecycle forces distribution.  They could not sell before
    receipt -- the contract forbade it -- and they are not price-sensitive in the way a
    discretionary holder is, because their alternative is not "hold" but "hold an illiquid
    position past a mandate deadline".
    WHO PAYS: whoever absorbs that supply.  A market maker who must widen, and the marginal
    buyer who lifts an offer that would not have existed absent the release.
    WHY IT PERSISTS: the schedule is CONTRACTUAL, not discretionary.  An issuer cannot cancel a
    cliff because the price is inconvenient, and arbitrage cannot compete the release away --
    the tokens arrive on the date the token-generation event fixed, years earlier.  That makes
    it structural in exactly the way funding and carry are, and unlike a discretionary treasury
    sale it cannot be timed away by the seller.

THE DEFECT THIS MODULE EXISTS TO FIX (recorded by the screen's own artifact, not discovered here)
    `data/unlock_event_screen.json` records TWO defects against itself, and they are the same
    defect wearing two hats -- the desk held a SNAPSHOT where the mechanism needs a SERIES:

      defect_2_snapshot_not_series: "One-shot scrape.  Forward calendar spans only
        2026-07-25 -> 2026-08-23 ... No collector refreshes it".
      defect_1_lookahead_denominator: "pct_circ_now is % of CURRENT (2026-07-24) circulating
        supply, applied to events back to 2016 ... the conditioning variable is not knowable at
        event time."

    Both make the SAME question unaskable.  The mechanism is not "did a token unlock happen" --
    that is a date, and 27 parameterisations already read NULL on it.  The mechanism is
    "HOW MUCH SUPPLY LANDS IN THE NEXT N DAYS RELATIVE TO THE FLOAT THAT MUST ABSORB IT".  That
    is a RATIO OF TWO TIME SERIES, and the desk held neither as a series.  A snapshot cannot
    express it at any parameterisation, which is why sweeping the 28th parameterisation on the
    old construction would have been re-litigating rather than a new test.

CONSTRUCTIONS (all four are DECLARED; all four are LOGGED whether or not they print).
    Reporting only the construction that printed is the garden of forking paths.  Each is a
    per-symbol daily series computed strictly from information timestamped at or before the
    bar close it is stamped on.

      C1  forward_fraction     sum(tokens released in (close_d, close_d + N days])
                               ------------------------------------------------
                                        circulating_supply(as of close_d)
          The mechanism in its plainest form: supply about to land, as a share of the float
          that has to absorb it.  This is the construction the snapshot could not express.

      C2  pressure_change      C1(d) - C1(d - N)
          A cliff APPROACHING.  If absorption is what costs, the derivative of the overhang may
          lead the level -- the market re-prices as the cliff enters the window, not when it
          lands.

      C3  standing_overhang    (total tokens still locked at close_d) / circulating(close_d)
          A LEVEL, not a flow.  Distinguishes "a big release is imminent" from "this token is
          permanently overhung".  Included because if only C3 works, the mechanism is dilution
          risk premium, not forced absorption -- a different mechanism with a different payer.

      C4  log_forward          log1p(C1)
          C1 is a heavy right tail (a single cliff can be 40% of float).  A z-score over a
          heavy tail is dominated by the tail, so the untransformed and transformed forms are
          genuinely different tests, not cosmetic variants of one.

    WINDOWS N (days): 7, 14, 30.  Declared, not swept: 7 is one weekly funding/settlement cycle,
    30 is the modal vesting granularity (monthly linear vests), 14 is the midpoint.  A fourth
    window is a NEW pre-registration, not a tuning step.

HORIZONS (days) of the target return: 1, 5, 10.  Matched to the prior screen's windows so the
    two readings are comparable; `horizon_days` is passed to the harness so Sharpe annualises on
    the right clock and the sharpe_ceiling rail keeps constant per-period strictness.

EXACT TIMESTAMP ALIGNMENT (L1.46 clock provenance).  Three separate rails, all strict:
    1. NUMERATOR CAUSALITY.  A release at instant `t_u` enters signal[d] only if
       `close_d < t_u <= close_d + N days` -- STRICTLY greater.  A release landing exactly at
       the close, or anywhere INSIDE bar d, is excluded from signal[d].  So an unlock at instant
       t never informs a bar containing t.
    2. KNOWN-FROM CAUSALITY.  A release also enters signal[d] only if it was PUBLICLY KNOWN by
       close_d (`known_from <= close_d`).  The schedule is contractual, but a schedule the
       market had not been told yet is not tradeable information.  Rows lacking `known_from` are
       COUNTED and the assumption is recorded as a defect, never silently applied.
    3. DENOMINATOR CAUSALITY.  circulating_supply(close_d) is the LAST observation at or before
       close_d.  There is no forward fill from a later observation, and there is NO fallback to
       a current-day snapshot -- that fallback IS defect_1, and reproducing it would rebuild the
       bug this module exists to remove.  A symbol-day with no prior supply observation yields
       NaN and is dropped, shrinking n honestly rather than borrowing tomorrow's float.

MULTIPLICITY CHARGE.  27 parameterisations were already spent on this class (recorded
    `trials: 27` in `data/unlock_event_screen.json`).  Those trials were paid for out of the
    same hypothesis budget and do not stop existing because a new construction is tried, so
    `PRIOR_PARAMETERISATIONS = 27` is added to every new cell count before any power or
    significance statement is made.  4 constructions x 3 windows x 3 horizons = 36 new cells,
    for 63 total.  alpha stays 0.05; the bar moves, never the alpha.

STAGE-A ONLY (two-stage law): ZERO promotion authority.  A pass earns a forward clock, never
capital.  The analytical last mile is `libs.research.axis_screen.stage_a_screen` so the
angle-20 de-contamination gate cannot be skipped, and every verdict is reported beside its
detection floor from `libs.validation.type2_cost` -- a negative without its power is not a
finding.

DATA REQUIRED, AND WHAT HAPPENS WHEN IT IS ABSENT.  This module NEVER simulates and never falls
back to synthetic data.  Missing input => a NOT-READABLE-HERE status artifact naming the exact
file and field that is missing.  `run_screen` returns that artifact; it does not raise, and it
does not return a number.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.axis_screen import stage_a_screen
from libs.validation.type2_cost import Type2Cost, correlation_negative, indeterminate

# --------------------------------------------------------------------------- pre-registration

#: Declared forward windows in days.  Not swept.  A fourth entry is a new pre-registration.
WINDOWS_DAYS: tuple[int, ...] = (7, 14, 30)

#: Declared target-return horizons in days.  Matched to the prior screen so readings compare.
HORIZONS_DAYS: tuple[int, ...] = (1, 5, 10)

#: Declared constructions.  ALL are run and ALL are logged, winners and losers alike.
CONSTRUCTIONS: tuple[str, ...] = (
    "C1_forward_fraction",
    "C2_pressure_change",
    "C3_standing_overhang",
    "C4_log_forward",
)

#: Trials already spent on this mechanism class before this module existed.  Read straight off
#: `data/unlock_event_screen.json` ("trials": 27).  They are charged to the multiplicity budget
#: because they were drawn from it; forgetting them is how a 28th look becomes a "discovery".
PRIOR_PARAMETERISATIONS = 27

#: Total declared cells this module contributes.
NEW_CELLS = len(CONSTRUCTIONS) * len(WINDOWS_DAYS) * len(HORIZONS_DAYS)

#: The multiplicity charge every power statement in this module is made against.
TOTAL_TRIALS = PRIOR_PARAMETERISATIONS + NEW_CELLS

#: Minimum symbol-days per cell before a reading is even attempted.  Below this the cell is
#: reported UNREADABLE rather than screened, so a three-point series cannot print an IC.
MIN_ROWS_PER_CELL = 60

NOT_READABLE = "NOT-READABLE-HERE"
UNDERPOWERED = "SCREEN-UNDERPOWERED"

#: Default on-disk locations.  Both are declared even though neither is guaranteed present --
#: naming the address is what makes "absent" a measurement rather than a shrug.
DEFAULT_SCHEDULE_PATH = Path("data/unlock_events.json")
DEFAULT_SUPPLY_PATH = Path("data/circulating_supply.jsonl")


# --------------------------------------------------------------------------- data model


@dataclass(frozen=True)
class UnlockRelease:
    """One contractual release of previously-locked tokens.

    `instant` is when the tokens become liquid.  `known_from` is when the schedule row became
    PUBLIC; a release the market has not been told about is not tradeable information, so a row
    whose `known_from` is after the bar close is excluded from that bar's signal.  `None` means
    the source did not record it -- the loader counts those rows and reports the count as a
    defect rather than quietly assuming the schedule was always public.
    """

    symbol: str
    instant: datetime
    tokens: float
    category: str = "unknown"
    known_from: datetime | None = None


@dataclass(frozen=True)
class ScheduleLoad:
    """What came off disk, and everything that was wrong with it."""

    releases: tuple[UnlockRelease, ...]
    #: Machine-readable reasons the load is unusable.  Empty tuple == usable.
    missing: tuple[str, ...]
    #: Recorded imperfections that do not block a read but must travel with the result.
    defects: tuple[str, ...]
    n_rows_seen: int = 0
    n_rows_kept: int = 0

    @property
    def readable(self) -> bool:
        return not self.missing and bool(self.releases)


@dataclass(frozen=True)
class SupplyLoad:
    """Circulating-supply history, per symbol, sorted ascending by observation instant."""

    series: dict[str, tuple[tuple[datetime, float], ...]]
    missing: tuple[str, ...]
    defects: tuple[str, ...]

    @property
    def readable(self) -> bool:
        return not self.missing and bool(self.series)


# --------------------------------------------------------------------------- loaders


def _as_utc(raw: object) -> datetime | None:
    """Parse an ISO-8601 stamp or epoch number into an aware UTC datetime, or None.

    A naive stamp is REJECTED rather than localised: guessing the zone of a vesting cliff is how
    a whole-day misalignment enters, and a whole-day misalignment on a daily bar is precisely
    the artifact class the harness's lookahead rail exists to catch.
    """
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else None
    if isinstance(raw, int | float):
        val = float(raw)
        if not math.isfinite(val) or val <= 0:
            return None
        # Heuristic on magnitude only: seconds vs milliseconds since epoch.
        if val > 1e11:
            val /= 1000.0
        try:
            return datetime.fromtimestamp(val, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


def load_unlock_schedule(path: Path | None = None) -> ScheduleLoad:
    """Read the vesting schedule AS A SERIES OF DATED RELEASES.

    Expected schema (a list, or a dict with a "events"/"unlocks" list), one object per release::

        {"symbol": "ARB", "instant": "2026-09-16T00:00:00+00:00",
         "tokens": 92650000.0, "category": "insiders",
         "known_from": "2023-03-16T00:00:00+00:00"}

    `tokens` is an ABSOLUTE token count, deliberately not a percentage: a percentage is already
    a ratio against some float, and which float it was taken against is exactly the thing
    defect_1 got wrong.  The denominator is supplied separately, dated, by
    `load_circulating_supply`.
    """
    p = path if path is not None else DEFAULT_SCHEDULE_PATH
    if not p.exists():
        return ScheduleLoad(
            releases=(),
            missing=(
                f"{p}: absent from this checkout.  The census records this class as "
                "ON-DISK, but the only unlock artifact present is the SCREEN OUTPUT "
                "`data/unlock_event_screen.json`, which is a summary of 27 cells and carries "
                "no per-release rows.  A summary cannot be re-cut into a series.",
            ),
            defects=(),
        )
    try:
        blob: Any = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return ScheduleLoad((), (f"{p}: unreadable ({exc.__class__.__name__})",), ())

    rows: Any = blob
    if isinstance(blob, dict):
        for key in ("events", "unlocks", "releases", "schedule"):
            if isinstance(blob.get(key), list):
                rows = blob[key]
                break
    if not isinstance(rows, list):
        return ScheduleLoad((), (f"{p}: no list of release rows found",), ())

    releases: list[UnlockRelease] = []
    n_no_known_from = 0
    n_bad_instant = 0
    n_bad_tokens = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
        instant = _as_utc(row.get("instant") or row.get("timestamp") or row.get("ts")
                          or row.get("date"))
        raw_tokens = row.get("tokens", row.get("amount"))
        tokens = float(raw_tokens) if isinstance(raw_tokens, int | float) else float("nan")
        if not symbol or instant is None:
            n_bad_instant += 1
            continue
        if not math.isfinite(tokens) or tokens < 0.0:
            n_bad_tokens += 1
            continue
        known = _as_utc(row.get("known_from"))
        if known is None:
            n_no_known_from += 1
        releases.append(
            UnlockRelease(
                symbol=symbol,
                instant=instant,
                tokens=tokens,
                category=str(row.get("category") or "unknown"),
                known_from=known,
            )
        )

    defects: list[str] = []
    if n_no_known_from:
        defects.append(
            f"{n_no_known_from}/{len(rows)} rows carry no `known_from`.  Treated as public from "
            "the start of the price series.  This is an ASSUMPTION, not a measurement: if any "
            "schedule row was added to the calendar retroactively, the signal reads a release "
            "the market had not been told about."
        )
    if n_bad_instant:
        defects.append(f"{n_bad_instant} rows dropped: no symbol or no timezone-aware instant")
    if n_bad_tokens:
        defects.append(f"{n_bad_tokens} rows dropped: token count absent or non-finite")

    missing: tuple[str, ...] = ()
    if not releases:
        missing = (f"{p}: parsed 0 usable releases",)
    return ScheduleLoad(
        releases=tuple(sorted(releases, key=lambda r: (r.symbol, r.instant))),
        missing=missing,
        defects=tuple(defects),
        n_rows_seen=len(rows),
        n_rows_kept=len(releases),
    )


def load_circulating_supply(path: Path | None = None) -> SupplyLoad:
    """Read circulating-supply HISTORY -- the denominator, dated.

    Expected schema, one JSON object per line::

        {"symbol": "ARB", "observed_at": "2026-07-01T00:00:00+00:00",
         "circulating": 4285000000.0}

    THE WHOLE POINT IS THAT THIS IS A SERIES.  `pct_circ_now` -- one number per symbol taken on
    the scrape date and applied backwards to 2016 -- is defect_1.  Circulating supply GROWS, so
    a current-float denominator records an old unlock that WAS a huge share of float at the time
    as a small share of today's, structurally emptying exactly the high-float-share bucket where
    the mechanism is supposed to live (the prior screen's `insiders >= 10%` bucket held 14
    events and `>= 30%` held zero).  There is deliberately NO snapshot fallback in this loader.
    """
    p = path if path is not None else DEFAULT_SUPPLY_PATH
    if not p.exists():
        return SupplyLoad(
            series={},
            missing=(
                f"{p}: absent from this checkout.  No circulating-supply history exists on "
                "disk in any form -- the only supply collector present is "
                "`scripts/collect_stablecoin_supply.py`, which writes stablecoin aggregate "
                "supply (`data/stablecoin_supply.jsonl`) and covers no unlocking token.  "
                "Without a dated float there is no honest denominator, and the only available "
                "substitute is the current-day snapshot that IS defect_1.",
            ),
            defects=(),
        )
    try:
        text = p.read_text("utf-8")
    except OSError as exc:
        return SupplyLoad({}, (f"{p}: unreadable ({exc.__class__.__name__})",), ())

    acc: dict[str, list[tuple[datetime, float]]] = {}
    n_bad = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except ValueError:
            n_bad += 1
            continue                      # a torn append must not take the whole screen down
        if not isinstance(row, dict):
            n_bad += 1
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        when = _as_utc(row.get("observed_at") or row.get("timestamp") or row.get("date"))
        raw = row.get("circulating", row.get("circulating_supply"))
        value = float(raw) if isinstance(raw, int | float) else float("nan")
        if not symbol or when is None or not math.isfinite(value) or value <= 0.0:
            n_bad += 1
            continue
        acc.setdefault(symbol, []).append((when, value))

    defects: list[str] = []
    if n_bad:
        defects.append(f"{n_bad} supply rows dropped: unparseable, naive-stamped, or non-positive")
    missing: tuple[str, ...] = ()
    if not acc:
        missing = (f"{p}: parsed 0 usable circulating-supply observations",)
    return SupplyLoad(
        series={s: tuple(sorted(v)) for s, v in acc.items()},
        missing=missing,
        defects=tuple(defects),
    )


# --------------------------------------------------------------------------- the construction


def circulating_at(
    series: tuple[tuple[datetime, float], ...], when: datetime
) -> float | None:
    """Circulating supply as it was KNOWN AT `when`: the last observation at or before it.

    Returns None -- never a later observation, and never a global snapshot -- when the series
    starts after `when`.  A None here shrinks the sample; a fallback here would rebuild defect_1.
    """
    if not series:
        return None
    idx = bisect_right([obs for obs, _ in series], when)
    if idx == 0:
        return None
    value = series[idx - 1][1]
    return value if value > 0.0 else None


def forward_unlock_tokens(
    releases: tuple[UnlockRelease, ...],
    bar_close: datetime,
    window_days: int,
) -> float:
    """Tokens contractually releasing in (bar_close, bar_close + window_days], known by bar_close.

    STRICTLY causal on both edges:
      * `instant > bar_close` -- STRICT.  A release landing exactly at the close, or anywhere
        inside the bar that ends at `bar_close`, is NOT in this sum.  An unlock at instant t
        therefore never informs a bar containing t.
      * `known_from <= bar_close` -- a schedule row the market had not been told about yet
        contributes nothing, even though it is contractually certain.
    """
    horizon = bar_close + timedelta(days=window_days)
    total = 0.0
    for rel in releases:
        if rel.instant <= bar_close or rel.instant > horizon:
            continue
        if rel.known_from is not None and rel.known_from > bar_close:
            continue
        total += rel.tokens
    return total


def locked_tokens_at(releases: tuple[UnlockRelease, ...], bar_close: datetime) -> float:
    """Tokens still locked at `bar_close`: everything scheduled strictly after it and known by it.

    The C3 numerator.  Same two causality rails as `forward_unlock_tokens`, without the horizon.
    """
    total = 0.0
    for rel in releases:
        if rel.instant <= bar_close:
            continue
        if rel.known_from is not None and rel.known_from > bar_close:
            continue
        total += rel.tokens
    return total


def build_series(
    releases: tuple[UnlockRelease, ...],
    supply: tuple[tuple[datetime, float], ...],
    bar_closes: tuple[datetime, ...],
    *,
    construction: str,
    window_days: int,
) -> np.ndarray:
    """The schedule-as-series construction: one signal value per bar close.

    Returns a float array the length of `bar_closes`, NaN wherever the value is not computable
    from information dated at or before that close.  NaN is the honest answer; it is dropped by
    `screen_cell`, which shrinks n rather than borrowing a denominator from the future.
    """
    if construction not in CONSTRUCTIONS:
        raise ValueError(f"undeclared construction {construction!r}; declared: {CONSTRUCTIONS}")
    out = np.full(len(bar_closes), np.nan, dtype="float64")
    fwd = np.full(len(bar_closes), np.nan, dtype="float64")

    for i, close in enumerate(bar_closes):
        float_at = circulating_at(supply, close)
        if float_at is None:
            continue                       # no dated float -> no honest ratio -> NaN
        if construction == "C3_standing_overhang":
            out[i] = locked_tokens_at(releases, close) / float_at
            continue
        fwd[i] = forward_unlock_tokens(releases, close, window_days) / float_at

    if construction == "C1_forward_fraction":
        out = fwd
    elif construction == "C4_log_forward":
        out = np.log1p(fwd)
    elif construction == "C2_pressure_change":
        lag = int(window_days)
        if lag < len(fwd):
            out[lag:] = fwd[lag:] - fwd[:-lag]
    return out


# --------------------------------------------------------------------------- screening


def screen_cell(
    signal: np.ndarray,
    target_ret: np.ndarray,
    *,
    name: str,
    horizon_days: int,
    panel_width: int = 1,
) -> dict[str, Any]:
    """Run ONE declared cell through the audited harness, with power attached either way.

    Rows where the signal is NaN (no dated float, or the C2 lag not yet filled) are dropped
    jointly from both legs BEFORE screening, so the harness never sees a fabricated value.
    """
    sig = np.asarray(signal, dtype="float64")
    ret = np.asarray(target_ret, dtype="float64")
    keep = np.isfinite(sig) & np.isfinite(ret)
    sig, ret = sig[keep], ret[keep]

    cost = correlation_negative(
        name,
        n_obs=float(len(sig)),
        source="libs/research/unlock_supply_series.py",
        horizon_periods=float(horizon_days),
        panel_width=max(1, int(panel_width)),
        n_tests=TOTAL_TRIALS,
        note=(
            f"multiplicity charge {TOTAL_TRIALS} = {PRIOR_PARAMETERISATIONS} prior "
            f"parameterisations on this class + {NEW_CELLS} new declared cells"
        ),
    )
    if len(sig) < MIN_ROWS_PER_CELL:
        return {
            "name": name,
            "verdict": UNDERPOWERED,
            "status": NOT_READABLE if len(sig) == 0 else UNDERPOWERED,
            "n_usable_rows": len(sig),
            "min_rows_required": MIN_ROWS_PER_CELL,
            "why": (
                f"{len(sig)} usable symbol-days after dropping rows with no dated circulating "
                f"supply; floor is {MIN_ROWS_PER_CELL}.  Not screened, not refuted."
            ),
            "power": cost.as_dict(),
        }
    out = stage_a_screen(
        sig, ret, name=name, horizon_days=float(horizon_days), panel_width=max(1, int(panel_width))
    )
    out["power"] = cost.as_dict()
    out["multiplicity_charge"] = TOTAL_TRIALS
    return out


def declared_cells() -> tuple[tuple[str, int, int], ...]:
    """Every (construction, window, horizon) this module will run.  Declared before any result."""
    return tuple(
        (c, w, h) for c in CONSTRUCTIONS for w in WINDOWS_DAYS for h in HORIZONS_DAYS
    )


def run_screen(
    *,
    schedule_path: Path | None = None,
    supply_path: Path | None = None,
    bars: dict[str, tuple[tuple[datetime, ...], np.ndarray]] | None = None,
) -> dict[str, Any]:
    """Run the full pre-registered grid, or return a NOT-READABLE-HERE artifact naming what is
    missing.  NEVER simulates, never substitutes synthetic data, never falls back to a snapshot
    denominator.

    `bars` maps symbol -> (bar close instants, close prices).  Passing None means the caller has
    no price panel, which is itself a missing input and is reported as one.
    """
    generated = datetime.now(tz=UTC).isoformat()
    schedule = load_unlock_schedule(schedule_path)
    supply = load_circulating_supply(supply_path)

    header: dict[str, Any] = {
        "generated": generated,
        "screen": "unlock_supply_series",
        "census_gap": {"rank": 3, "class_id": "mechanical_supply_release", "score": 0.360},
        "law": (
            "Stage-A only (two-stage law): ZERO promotion authority.  A pass earns a "
            "pre-registered forward clock, never capital."
        ),
        "alpha": 0.05,
        "pre_registered": {
            "constructions": list(CONSTRUCTIONS),
            "windows_days": list(WINDOWS_DAYS),
            "horizons_days": list(HORIZONS_DAYS),
            "declared_cells": NEW_CELLS,
            "prior_parameterisations_charged": PRIOR_PARAMETERISATIONS,
            "multiplicity_charge": TOTAL_TRIALS,
        },
        "alignment": {
            "numerator": "instant > bar_close (STRICT) and instant <= bar_close + N days",
            "known_from": "release enters signal[d] only if known_from <= close_d",
            "denominator": "last circulating observation at or before close_d; no forward fill",
            "snapshot_fallback": "NONE -- a current-float fallback is defect_1 and is refused",
            "target": "stage_a_screen predicts return of bar d+1 from signal at close of bar d",
        },
        "schedule_defects": list(schedule.defects),
        "supply_defects": list(supply.defects),
    }

    missing: list[str] = [*schedule.missing, *supply.missing]
    # Explicit `is not None` rather than a truthiness test: mypy 2.1 does not narrow Optional out
    # of a membership/truthiness check, and the two pinned mypy versions disagree about it.
    panel: dict[str, tuple[tuple[datetime, ...], np.ndarray]] = {} if bars is None else bars
    if not panel:
        missing.append(
            "price panel: no per-symbol daily bars supplied for the unlocking universe. "
            "scripts/screen_unlock_supply_series.py loads D1 closes from the bronze crypto lake "
            "for exactly the schedule's symbols (fixed 2026-08-12, R0385 -- the caller "
            "previously passed bars=None unconditionally); an empty panel here means none of "
            "those symbols have lake history yet, not a wiring gap."
        )

    if missing:
        header["status"] = NOT_READABLE
        header["verdict"] = NOT_READABLE
        header["missing_inputs"] = missing
        header["cells_run"] = 0
        header["cells_declared"] = [
            {"construction": c, "window_days": w, "horizon_days": h} for c, w, h in declared_cells()
        ]
        header["power"] = indeterminate(
            "unlock_supply_series",
            "no input series on disk, so no sample exists to state a detection floor against.  "
            "This is NOT a negative result: nothing was tested, so nothing was refuted.",
            source="libs/research/unlock_supply_series.py",
            effect_unit="ic",
        ).as_dict()
        header["graveyard"] = []
        header["reentry_condition"] = (
            "A recurring collector that appends the DefiLlama (or equivalent) unlock calendar "
            "as DATED RELEASE ROWS with `known_from`, PLUS a circulating-supply history "
            "collector writing `data/circulating_supply.jsonl`.  Both are required: the "
            "numerator without a dated denominator is defect_1 again, and the denominator "
            "without a refreshing schedule is defect_2 again.  Re-run this module unchanged "
            "once both exist -- the constructions above are pre-registered and must not be "
            "re-chosen after seeing the data."
        )
        return header

    cells: list[dict[str, Any]] = []
    graveyard: list[dict[str, Any]] = []
    for construction, window, horizon in declared_cells():
        sig_parts: list[np.ndarray] = []
        ret_parts: list[np.ndarray] = []
        for symbol, (closes, prices) in sorted(panel.items()):
            rel = tuple(r for r in schedule.releases if r.symbol == symbol)
            ser = supply.series.get(symbol, ())
            if not rel or not ser:
                continue
            values = build_series(
                rel, ser, closes, construction=construction, window_days=window
            )
            px = np.asarray(prices, dtype="float64")
            if len(px) < horizon + 2:
                continue
            fwd_ret = np.full(len(px), np.nan, dtype="float64")
            fwd_ret[horizon:] = px[horizon:] / px[:-horizon] - 1.0
            sig_parts.append(values)
            ret_parts.append(fwd_ret)
        if not sig_parts:
            continue
        name = f"unlock_{construction}_w{window}d_h{horizon}d"
        cell = screen_cell(
            np.concatenate(sig_parts),
            np.concatenate(ret_parts),
            name=name,
            horizon_days=horizon,
            panel_width=max(1, len(sig_parts)),
        )
        cell["construction"] = construction
        cell["window_days"] = window
        cells.append(cell)
        if cell.get("verdict") != "SCREEN-INTERESTING":
            graveyard.append(
                {
                    "cell": name,
                    "verdict": cell.get("verdict"),
                    "reason": cell.get("why")
                    or f"harness verdict {cell.get('verdict')} under the angle-20 gate",
                    "detection_floor_ic": cell.get("power", {}).get("min_detectable_effect"),
                    "powered": cell.get("power", {}).get("label"),
                }
            )

    header["status"] = "SCREENED"
    header["cells_run"] = len(cells)
    header["cells"] = cells
    header["graveyard"] = graveyard
    interesting = [c for c in cells if c.get("verdict") == "SCREEN-INTERESTING"]
    header["verdict"] = "SCREEN-INTERESTING" if interesting else (
        "SCREEN-WEAK"
        if any(c.get("verdict") == "SCREEN-WEAK" for c in cells)
        else UNDERPOWERED
    )
    return header


def power_for_absent_data() -> Type2Cost:
    """The detection floor for a screen that never ran: INDETERMINATE, by construction.

    Exposed so a caller cannot be tempted to invent one.  A missing dataset does not have a
    small detection floor or a large one -- it has none, and recording it as a powered negative
    would put a permanent kill in the graveyard on zero evidence.
    """
    return indeterminate(
        "unlock_supply_series",
        "inputs absent from this checkout; no sample, therefore no detection floor",
        source="libs/research/unlock_supply_series.py",
        effect_unit="ic",
    )
