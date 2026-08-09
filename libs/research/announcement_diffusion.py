"""STAGE-A SCREEN CORE: scheduled-event information diffusion, screened ONLY on a recovered
ANNOUNCEMENT INSTANT (census gap #6, `scheduled_event_diffusion`, gap_score 0.315, coverage
NO-CANDIDATE -- zero candidates ever tested).

=============================================================================================
PRE-REGISTRATION.  Written before any number was computed.
=============================================================================================

MECHANISM -- WHO PAYS WHOM, AND WHY IT PERSISTS
    An exchange listing or delisting announcement is PUBLIC information released at a single
    instant.  It does not diffuse instantaneously: a bot reading the announcements endpoint acts
    in milliseconds, a desk on an RSS poll acts in minutes, a human reading a newsletter acts in
    hours.  Between the first and last participant to act there is a price path.
    WHO PAYS: the slower participant.  Whoever is still buying the listing at minute thirty is
    buying from whoever bought it at second three.
    WHY IT PERSISTS -- AND THE HONEST PRIOR IS THAT IT MOSTLY DOES NOT.  It persists only to the
    extent attention is bounded.  This is the most latency-contested event class in crypto; the
    census holds plausibility DOWN at 0.45 on purpose, and this desk is not a millisecond
    participant.  The expected finding is decay so fast that the tradeable remainder is already
    arbitraged.  A NEGATIVE HERE IS THE PREDICTED OUTCOME, which is exactly why the screen must
    be built so that a POSITIVE cannot be manufactured by an alignment mistake.

THE SINGLE MOST LIKELY WAY THIS SCREEN PRODUCES A FAKE EDGE, AND THE RAIL AGAINST IT
    The census names the missing input precisely: "the announcement INSTANT, not the date".
    A date-stamped announcement tested against a daily bar is a SAME-BAR ARTIFACT.  If the
    announcement lands at 14:07 UTC and the "prediction" is the UTC-day return, the return being
    predicted ALREADY CONTAINS the announcement and the entire move it caused.  The screen would
    print a large IC, a large Sharpe, and a completely fictitious edge -- the same failure mode
    that made kimchi, the Coinbase premium and the Turkey premium look real until the
    de-contamination gate caught them as pure timing artifacts.
    So instant recovery is treated here as the LOAD-BEARING work, not a preprocessing step:
      * `recover_instant` classifies the precision of every row and REFUSES anything coarser
        than `MIN_PRECISION`.  A midnight-exact stamp is diagnosed as a DATE WEARING AN
        INSTANT'S CLOTHES and refused, because that is what a date-only feed looks like after a
        naive parse.
      * `screen_announcements` raises `InstantUnavailable` rather than screening a date.  There
        is no flag to override it, because the override would be used.
      * `SAME_BAR_CONTROL` runs the WRONG alignment deliberately, as a positive control for
        contamination.  If the contaminated cell does not come back TIMING-ARTIFACT or
        SUSPECT-LOOKAHEAD, the screen's own artifact detector is broken and no other cell in the
        run may be believed.

WHAT WAS FOUND ON DISK (recorded before the screen, because it decides whether it can run)
    `data/exchange_announcements.jsonl`, 100 rows, written by `scripts/collect_announcements.py`:
      * source `okx`            -- 20 rows, `published_at` carries MICROSECOND precision straight
                                   off the OKX announcements API.  INSTANT RECOVERABLE.
      * source `coindesk`       -- 25 rows, RSS pubDate, SECOND precision.  RECOVERABLE.
      * source `cointelegraph`  -- 30 rows, RSS pubDate, SECOND precision.  RECOVERABLE.
      * source `defillama_hacks`-- 25 rows, every stamp EXACTLY 00:00:00.000000 UTC.  That is a
                                   date, not an instant.  REFUSED.
    So the instant IS recoverable for the exchange-announcement class this gap is about.  The
    collector was already recording it; nobody had read it.

CONSTRUCTIONS (all DECLARED, all LOGGED, winners and losers alike)
      A1  event_pulse          1 on the bar in which the announcement instant fell, 0 elsewhere.
                               The harness then predicts the NEXT bar -- the first return that
                               is entirely after the instant.  This is the causal baseline.
      A2  tier_signed_pulse    A1 scaled by the collector's materiality tier (a delisting is not
                               a UI update).  Tests whether diffusion speed scales with stakes.
      A3  decay_pulse          A1 spread over DECAY_BARS with geometric weights.  Tests whether
                               the edge is a single-bar jump or a multi-bar drift -- the actual
                               "finite diffusion speed" claim.
      A4  SAME_BAR_CONTROL     THE ARTIFACT.  Fires one bar EARLY so the predicted return is the
                               bar CONTAINING the instant.  Never a candidate; reported so the
                               contamination detector is visible working.

BAR INTERVALS: 5m, 15m, 1h.  Declared, not swept.  Diffusion at a daily interval is not a
    diffusion test at all -- one daily bar swallows the entire event -- which is why the census
    lists "price at sub-daily resolution around the instant" as a required input.

EXACT TIMESTAMP ALIGNMENT (L1.46 clock provenance).  This is the whole screen:
    announcement clock: `published_at`, the PUBLISHER's stamp (OKX API publishTime / RSS
      pubDate).  Explicitly NOT `first_seen`, which is this desk's receive clock.
    price clock: Binance `open_time`, venue stamp, bar-open labelled, UTC.
    the rule: let bar k be the bar with open_k <= t_announce < open_{k+1} -- the bar CONTAINING
      the instant.  The signal is stamped at index k.  `stage_a_screen` predicts return[k+1],
      which spans (close_k, close_{k+1}] and is therefore ENTIRELY after the instant.  The
      harness's `same_period_corr` then compares the signal against return[k] -- the
      contaminated bar -- and the angle-20 gate kills the cell if that is where the correlation
      lives.  The contamination check is thus performed against the exact bar most likely to
      contain the leak.
    Nothing is ever stamped at index k-1 or earlier: that would place the signal before the
      announcement existed.  A4 does exactly that on purpose, and is labelled ARTIFACT-CONTROL.

THE DESK'S OWN LATENCY IS PART OF THE VERDICT, NOT A FOOTNOTE.  The collector records
    `first_seen` alongside `published_at`, so the desk's information latency is MEASURED rather
    than assumed.  Measured on this file: okx min 2031 min (~34 h), coindesk min 23.6 min,
    cointelegraph min 76.1 min.  If diffusion completes in minutes and the desk learns in hours,
    then even a real effect is unreachable -- the desk is the SLOWER PARTICIPANT, i.e. the payer.
    `tradeability` reports this beside every verdict, because a statistically real edge the desk
    provably cannot reach is not an edge for this desk.

MULTIPLICITY CHARGE.  This class has ZERO prior tested candidates (census: NO-CANDIDATE, 0
    constructions), so the charge is exactly the declared grid: 3 candidate constructions x 3
    intervals = 9 cells.  The artifact control is NOT charged -- it can never be promoted, and
    charging a cell that cannot win would inflate the bar protecting the ones that can.
    alpha stays 0.05.

STAGE-A ONLY (two-stage law): ZERO promotion authority.  Analytical last mile is
`libs.research.axis_screen.stage_a_screen`; power beside every verdict from
`libs.validation.type2_cost`.  Missing or insufficient input => NOT-READABLE-HERE or
SCREEN-UNDERPOWERED naming what is missing.  This module NEVER simulates and never fabricates.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.axis_screen import stage_a_screen
from libs.validation.type2_cost import Type2Cost, correlation_negative, indeterminate

# --------------------------------------------------------------------------- pre-registration

#: Declared candidate constructions.  A4 is declared separately -- see SAME_BAR_CONTROL.
CONSTRUCTIONS: tuple[str, ...] = ("A1_event_pulse", "A2_tier_signed_pulse", "A3_decay_pulse")

#: The deliberately-contaminated alignment.  Reported, never promotable, never charged.
SAME_BAR_CONTROL = "A4_same_bar_control"

#: Declared bar intervals in minutes.  Not swept.
INTERVALS_MIN: tuple[int, ...] = (5, 15, 60)

#: Bars over which A3 spreads the pulse, and the geometric decay applied.  Fixed constants.
#: DECAY_BARS is deliberately LONGER than the harness's z-window (20): see
#: `zscore_visibility` -- a pulse whose support is shorter than that window is annihilated at
#: exactly the bar it fires on, which is the one bar the screen is about.
DECAY_BARS = 24
DECAY_RATE = 0.85

#: Prior tested candidates on this class.  Census records NO-CANDIDATE: zero.
PRIOR_PARAMETERISATIONS = 0

NEW_CELLS = len(CONSTRUCTIONS) * len(INTERVALS_MIN)
TOTAL_TRIALS = PRIOR_PARAMETERISATIONS + NEW_CELLS

#: Minimum announcements that must land inside the price panel before a cell is screened.
#: Below this the cell is reported unread rather than screened: an event study on four events
#: cannot resolve anything, and printing an IC for it invites it to be read as a finding.
MIN_EVENTS_PER_CELL = 20

#: Minimum bars per cell, so the harness's own 30-row floor is never the binding constraint.
MIN_BARS_PER_CELL = 400

#: The harness's trailing z-window.  Mirrored here ONLY to measure visibility (below); the
#: harness remains the sole place the z-score is actually computed.
HARNESS_ZWIN = 20

#: Minimum fraction of event bars the harness's z-score must be able to SEE before a cell is
#: allowed to return a verdict.  See `zscore_visibility` for what goes wrong below this.
MIN_EVENT_VISIBILITY = 0.5

# ------------------------------------------------------------------ instant-precision taxonomy

SUBSECOND = "subsecond"
SECOND = "second"
MINUTE = "minute"
DATE_ONLY = "date-only"
ABSENT = "absent"

#: The coarsest precision this screen will accept.  MINUTE, because a minute-stamped event on a
#: 5-minute bar still lands in an identifiable bar, while a DATE lands in all 288 of them.
#: Loosening this is not a parameter change -- it reintroduces the same-bar artifact.
MIN_PRECISION = MINUTE

_PRECISION_ORDER: dict[str, int] = {ABSENT: 0, DATE_ONLY: 1, MINUTE: 2, SECOND: 3, SUBSECOND: 4}

NOT_READABLE = "NOT-READABLE-HERE"
UNDERPOWERED = "SCREEN-UNDERPOWERED"

DEFAULT_ANNOUNCEMENTS = Path("data/exchange_announcements.jsonl")
DEFAULT_BAR_ROOT = Path("data/binance_vision")


class InstantUnavailable(RuntimeError):
    """Raised when a screen is asked to run on announcements whose instant is not recoverable.

    DELIBERATELY AN EXCEPTION, NOT A DEGRADED MODE.  A function that returns a slightly-worse
    number when the instant is missing will be called, and its output will be read as a result.
    The only safe behaviour is to refuse.
    """


@dataclass(frozen=True)
class Announcement:
    """One announcement with its recovered instant and the provenance of that recovery."""

    source: str
    title: str
    instant: datetime | None
    precision: str
    #: Assets named by the announcement, uppercased.  Empty when none could be resolved.
    symbols: tuple[str, ...]
    tier: int
    #: `first_seen - published_at` in minutes: THIS DESK's information latency for this row.
    desk_latency_min: float | None
    why: str

    @property
    def screenable(self) -> bool:
        """True only if the instant is recovered at or finer than the declared minimum."""
        if self.instant is None:
            return False
        return _PRECISION_ORDER.get(self.precision, 0) >= _PRECISION_ORDER[MIN_PRECISION]


# --------------------------------------------------------------------------- instant recovery


def recover_instant(row: dict[str, Any]) -> Announcement:
    """Recover the announcement INSTANT from a collector row, and grade its precision honestly.

    THE DIAGNOSTIC THAT MATTERS.  A date-only feed parsed naively produces a perfectly
    well-formed aware datetime at exactly midnight UTC.  It looks like an instant to every type
    check and every ISO parser, and it is a DATE.  So precision is not read off the string's
    format -- it is read off the VALUE:

        h=m=s=us=0  ->  DATE_ONLY.  Refused.
        s=us=0      ->  MINUTE.     Accepted (the coarsest accepted).
        us=0        ->  SECOND.     Accepted.
        otherwise   ->  SUBSECOND.  Accepted.

    THE KNOWN FALSE POSITIVE, STATED RATHER THAN HIDDEN: a genuine announcement published at
    exactly 00:00:00.000 UTC is misgraded DATE_ONLY and dropped.  That costs at most a few rows
    and biases the sample only in the direction of FEWER events -- it can never manufacture an
    edge, only fail to find one.  The opposite error -- admitting a date as an instant -- is the
    one that manufactures an edge, so the test is deliberately asymmetric.
    """
    source = str(row.get("source") or "unknown")
    title = str(row.get("title") or "")
    tier_raw = row.get("tier")
    tier = int(tier_raw) if isinstance(tier_raw, int | float) else 3
    lat_raw = row.get("latency_minutes")
    latency = (
        float(lat_raw)
        if isinstance(lat_raw, int | float) and math.isfinite(float(lat_raw))
        else None
    )
    syms_raw = row.get("symbols")
    symbols = tuple(
        str(s).upper().strip() for s in syms_raw if str(s).strip()
    ) if isinstance(syms_raw, list) else ()

    raw = row.get("published_at")
    if not isinstance(raw, str) or not raw.strip():
        return Announcement(
            source, title, None, ABSENT, symbols, tier, latency,
            "no `published_at` field: the publisher clock was never recorded",
        )
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return Announcement(
            source, title, None, ABSENT, symbols, tier, latency,
            f"`published_at` {raw!r} is not ISO-8601",
        )
    if parsed.tzinfo is None:
        # A naive stamp is refused, not localised.  Assuming UTC on a publisher stamp is exactly
        # how a whole-day shift enters, and a whole-day shift on a daily bar is the artifact.
        return Announcement(
            source, title, None, ABSENT, symbols, tier, latency,
            f"`published_at` {raw!r} is timezone-naive: the publishing zone is unknown and "
            "guessing it introduces the misalignment this screen exists to exclude",
        )
    inst = parsed.astimezone(UTC)

    if (inst.hour, inst.minute, inst.second, inst.microsecond) == (0, 0, 0, 0):
        return Announcement(
            source, title, inst, DATE_ONLY, symbols, tier, latency,
            "stamp is exactly 00:00:00.000000 UTC -- a DATE parsed into a datetime, not an "
            "instant.  Screening it against a bar containing it is the same-bar artifact.",
        )
    if (inst.second, inst.microsecond) == (0, 0):
        precision, why = MINUTE, "minute-resolution publisher stamp"
    elif inst.microsecond == 0:
        precision, why = SECOND, "second-resolution publisher stamp"
    else:
        precision, why = SUBSECOND, "sub-second publisher stamp (exchange API publishTime)"
    return Announcement(source, title, inst, precision, symbols, tier, latency, why)


def load_announcements(
    path: Path | None = None,
) -> tuple[tuple[Announcement, ...], tuple[str, ...]]:
    """Read the collector log and grade every row's instant.  Returns (rows, missing-reasons)."""
    p = path if path is not None else DEFAULT_ANNOUNCEMENTS
    if not p.exists():
        return (), (f"{p}: absent from this checkout",)
    try:
        text = p.read_text("utf-8")
    except OSError as exc:
        return (), (f"{p}: unreadable ({exc.__class__.__name__})",)
    rows: list[Announcement] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            continue                      # a torn append must not take the whole screen down
        if isinstance(obj, dict):
            rows.append(recover_instant(obj))
    if not rows:
        return (), (f"{p}: parsed 0 announcement rows",)
    return tuple(rows), ()


def instant_audit(rows: tuple[Announcement, ...]) -> dict[str, Any]:
    """Per-source census of instant recoverability.  This IS the gap-#6 deliverable.

    Whether the screen can run at all is decided here, so the count travels with the verdict
    rather than being asserted in prose.
    """
    by_source: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_source.setdefault(
            row.source, {SUBSECOND: 0, SECOND: 0, MINUTE: 0, DATE_ONLY: 0, ABSENT: 0}
        )
        bucket[row.precision] = bucket.get(row.precision, 0) + 1
    screenable = [r for r in rows if r.screenable]
    refused = [r for r in rows if not r.screenable]
    return {
        "n_rows": len(rows),
        "n_instant_recovered": len(screenable),
        "n_refused": len(refused),
        "min_precision_accepted": MIN_PRECISION,
        "by_source": by_source,
        "refusal_reasons": sorted({r.why for r in refused}),
        "instant_recoverable": bool(screenable),
    }


def desk_latency_summary(rows: tuple[Announcement, ...]) -> dict[str, Any]:
    """This desk's own information latency, per source, in minutes.

    Not decoration.  The mechanism says the slower participant pays; this measures whether the
    desk IS the slower participant on this feed.
    """
    out: dict[str, Any] = {}
    for source in sorted({r.source for r in rows}):
        vals = [
            r.desk_latency_min
            for r in rows
            if r.source == source and r.desk_latency_min is not None
        ]
        if not vals:
            out[source] = {"n": 0, "note": "collector recorded no first_seen latency"}
            continue
        arr = np.asarray(vals, dtype="float64")
        out[source] = {
            "n": int(arr.size),
            "min_minutes": round(float(arr.min()), 1),
            "median_minutes": round(float(np.median(arr)), 1),
            "max_minutes": round(float(arr.max()), 1),
        }
    return out


# --------------------------------------------------------------------------- alignment


def containing_bar_index(instant: datetime, bar_open_ms: np.ndarray) -> int:
    """Index of the bar CONTAINING `instant`: open_k <= instant < open_{k+1}.

    Returns -1 when the instant precedes the panel or falls on/after its last bar open (the last
    bar has no successor, so nothing after it can be predicted causally).
    """
    ms = instant.timestamp() * 1000.0
    idx = int(np.searchsorted(np.asarray(bar_open_ms, dtype="float64"), ms, side="right")) - 1
    if idx < 0 or idx >= len(bar_open_ms) - 1:
        return -1
    return idx


def build_signal(
    events: tuple[Announcement, ...],
    bar_open_ms: np.ndarray,
    *,
    construction: str,
) -> np.ndarray:
    """Stamp announcements onto bars under the declared alignment.

    THE CAUSAL RULE (A1/A2/A3): the pulse is stamped at index k, the bar CONTAINING the instant.
    `stage_a_screen` predicts return[k+1], which begins at close_k -- strictly after the
    instant.  The event's OWN bar (k) is never the predicted bar; it is what the harness's
    de-contamination gate measures against.

    THE ARTIFACT (A4): the pulse is stamped at k-1, so the predicted return IS bar k -- the bar
    containing the announcement.  This is what a date-stamped announcement tested against a
    daily bar does, and it must come back TIMING-ARTIFACT.
    """
    if construction not in (*CONSTRUCTIONS, SAME_BAR_CONTROL):
        raise ValueError(f"undeclared construction {construction!r}")
    out = np.zeros(len(bar_open_ms), dtype="float64")
    for ev in events:
        if ev.instant is None:
            continue
        k = containing_bar_index(ev.instant, bar_open_ms)
        if k < 0:
            continue
        if construction == "A1_event_pulse":
            out[k] += 1.0
        elif construction == "A2_tier_signed_pulse":
            # tier 1 is the most material (delisting / spec change), tier 3 the least.
            out[k] += float(4 - min(max(ev.tier, 1), 3))
        elif construction == "A3_decay_pulse":
            for j in range(DECAY_BARS):
                if k + j < len(out):
                    out[k + j] += DECAY_RATE**j
        else:                              # SAME_BAR_CONTROL -- deliberately one bar early
            if k - 1 >= 0:
                out[k - 1] += 1.0
    return out


def zscore_visibility(signal: np.ndarray, zwin: int = HARNESS_ZWIN) -> dict[str, Any]:
    """Can the harness's trailing z-score actually SEE the events?  Measured, not assumed.

    A DEFECT FOUND WHILE BUILDING THIS SCREEN, RECORDED HERE RATHER THAN WORKED AROUND.
    `stage_a_screen` z-scores the signal over a trailing `zwin`-bar window and, when that window
    has zero variance, sets z to 0.  That rule is correct for a continuous axis signal.  For a
    SPARSE EVENT INDICATOR it is silently catastrophic: if announcements are further apart than
    `zwin` bars, the window preceding every event is all-zeros, so

        z is exactly 0 AT THE EVENT BAR -- the one bar the whole screen is about --

    while the ~20 bars AFTER the event (whose windows now contain the pulse) carry a small
    NEGATIVE z.  The screen then silently stops measuring "an announcement just fired" and
    starts measuring "an announcement fired recently", WITH THE SIGN INVERTED.  It still prints
    an IC, a Sharpe and a verdict, all of which are about a different question than the one
    asked.  Verified directly: three pulses 60 bars apart give z == 0.0 at all three.

    So visibility is gated rather than hoped for.  `event_visibility` is the fraction of firing
    bars at which the harness's window has non-zero variance; below `MIN_EVENT_VISIBILITY` the
    cell is reported unreadable INSTEAD of returning a verdict.  This can only ever suppress a
    reading, never create one.
    """
    sig = np.asarray(signal, dtype="float64")
    fires = [t for t in range(len(sig)) if sig[t] != 0.0]
    visible = 0
    for t in fires:
        if t < zwin:
            continue
        if float(sig[t - zwin:t].std()) > 0.0:
            visible += 1
    eligible = [t for t in fires if t >= zwin]
    frac = float(visible) / float(len(eligible)) if eligible else 0.0
    return {
        "n_firing_bars": len(fires),
        "n_eligible": len(eligible),
        "n_visible_to_zscore": visible,
        "event_visibility": round(frac, 4),
        "zwin": int(zwin),
        "min_required": MIN_EVENT_VISIBILITY,
        "readable": frac >= MIN_EVENT_VISIBILITY,
    }


# --------------------------------------------------------------------------- price panel


def load_bars(
    symbol: str, interval_min: int, root: Path | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Load (bar_open_ms, close) for one symbol/interval from the on-disk binance_vision lake.

    Returns two empty arrays when the pair is not on disk.  Absence is reported by the caller as
    a missing input; it is never filled in.
    """
    base = root if root is not None else DEFAULT_BAR_ROOT
    tag = {5: "5m", 15: "15m", 60: "1h"}.get(int(interval_min))
    if tag is None:
        return np.array([]), np.array([])
    matches = sorted(base.glob(f"{symbol}-{tag}-*.npz"))
    if not matches:
        return np.array([]), np.array([])
    with np.load(matches[-1], allow_pickle=True) as blob:
        if "open_time" not in blob or "close" not in blob:
            return np.array([]), np.array([])
        return (
            np.asarray(blob["open_time"], dtype="float64"),
            np.asarray(blob["close"], dtype="float64"),
        )


def available_symbols(root: Path | None = None) -> dict[int, set[str]]:
    """Which symbols have sub-daily bars on disk, per declared interval."""
    base = root if root is not None else DEFAULT_BAR_ROOT
    out: dict[int, set[str]] = {}
    for interval, tag in ((5, "5m"), (15, "15m"), (60, "1h")):
        found: set[str] = set()
        if base.is_dir():
            for f in base.glob(f"*-{tag}-*.npz"):
                found.add(f.name.split("-", 1)[0])
        out[interval] = found
    return out


def resolve_asset(ann: Announcement) -> str | None:
    """Best-effort mapping from an announcement to the BINANCE PAIR it would be traded on.

    Deliberately conservative.  The collector's `symbols` field is a regex extraction that
    frequently yields the QUOTE currency (`USDT`) rather than the listed asset, so a permissive
    mapper here would silently join an announcement about GRVT to the USDT-quoted BTC panel and
    call the resulting noise a screen.  Only an explicit base asset is accepted, and unresolved
    rows are COUNTED as unresolved rather than guessed.
    """
    quote_only = {"USDT", "USDC", "USD", "BUSD", "TUSD", "FDUSD", "EUR"}
    for sym in ann.symbols:
        if sym and sym not in quote_only:
            return f"{sym}USDT"
    return None


# --------------------------------------------------------------------------- screening


def screen_cell(
    signal: np.ndarray,
    close: np.ndarray,
    *,
    name: str,
    interval_min: int,
    n_events: int,
    charged: bool = True,
) -> dict[str, Any]:
    """One declared cell through the audited harness, with its detection floor attached."""
    px = np.asarray(close, dtype="float64")
    ret = np.zeros(len(px), dtype="float64")
    if len(px) > 1:
        ret[1:] = px[1:] / px[:-1] - 1.0
    horizon_days = float(interval_min) / (60.0 * 24.0)

    cost = correlation_negative(
        name,
        n_obs=float(len(px)),
        source="libs/research/announcement_diffusion.py",
        horizon_periods=1.0,     # one bar per observation; the bar IS the period
        n_tests=TOTAL_TRIALS if charged else 1,
        note=(
            f"{n_events} announcements landed inside the panel; multiplicity charge "
            f"{TOTAL_TRIALS if charged else 1}"
            + ("" if charged else " (artifact control -- not promotable, not charged)")
        ),
    )
    if n_events < MIN_EVENTS_PER_CELL or len(px) < MIN_BARS_PER_CELL:
        return {
            "name": name,
            "verdict": UNDERPOWERED,
            "status": NOT_READABLE if n_events == 0 else UNDERPOWERED,
            "n_events": int(n_events),
            "n_bars": len(px),
            "min_events_required": MIN_EVENTS_PER_CELL,
            "min_bars_required": MIN_BARS_PER_CELL,
            "why": (
                f"{n_events} announcements resolved onto a {len(px)}-bar panel; floors are "
                f"{MIN_EVENTS_PER_CELL} events and {MIN_BARS_PER_CELL} bars.  Not screened, "
                "not refuted."
            ),
            "power": cost.as_dict(),
        }

    # INSTRUMENT CHECK BEFORE THE READING.  If the harness's trailing z-window cannot see the
    # event bars, whatever it returns is an answer to a different question -- see
    # `zscore_visibility`.  Refuse the reading rather than publish a verdict about the wrong
    # quantity.  This gate can only suppress a reading, never manufacture one.
    vis = zscore_visibility(signal)
    if not vis["readable"]:
        return {
            "name": name,
            "verdict": UNDERPOWERED,
            "status": UNDERPOWERED,
            "n_events": int(n_events),
            "n_bars": len(px),
            "zscore_visibility": vis,
            "why": (
                f"the harness z-scores over a trailing {vis['zwin']}-bar window and only "
                f"{vis['event_visibility']:.0%} of firing bars sit in a window with non-zero "
                "variance (floor "
                f"{MIN_EVENT_VISIBILITY:.0%}).  Announcements are sparser than the z-window, so "
                "z is 0 AT the event bar and the screen would be reading 'an announcement fired "
                "recently', sign-inverted, not 'an announcement just fired'.  Not screened, not "
                "refuted."
            ),
            "power": cost.as_dict(),
        }

    out = stage_a_screen(signal, ret, name=name, horizon_days=horizon_days)
    out["power"] = cost.as_dict()
    out["zscore_visibility"] = vis
    out["n_events"] = int(n_events)
    out["multiplicity_charge"] = TOTAL_TRIALS if charged else 1
    if not charged:
        out["role"] = "ARTIFACT-CONTROL -- never promotable; a non-artifact verdict here means "
        out["role"] += "the contamination detector is broken and no cell in this run is safe"
    return out


def declared_cells() -> tuple[tuple[str, int], ...]:
    """Every (construction, interval) that will run, including the uncharged artifact control."""
    return tuple(
        (c, i) for c in (*CONSTRUCTIONS, SAME_BAR_CONTROL) for i in INTERVALS_MIN
    )


def screen_announcements(
    events: tuple[Announcement, ...],
    bar_open_ms: np.ndarray,
    close: np.ndarray,
    *,
    label: str,
) -> list[dict[str, Any]]:
    """Run the declared grid for ONE symbol panel.  REFUSES date-only input.

    Raises `InstantUnavailable` if ANY supplied event fails the precision bar.  Filtering them
    out silently would let a run be dominated by whatever fraction happened to be recoverable
    while reporting a clean n -- the caller must decide, in the open, what to do with the
    refused rows.
    """
    bad = [e for e in events if not e.screenable]
    if bad:
        raise InstantUnavailable(
            f"{len(bad)}/{len(events)} announcements have no usable instant "
            f"(precisions: {sorted({e.precision for e in bad})}); minimum accepted is "
            f"{MIN_PRECISION}.  Screening a date against a bar containing it is the same-bar "
            "artifact this screen exists to exclude.  Refusing to screen."
        )
    cells: list[dict[str, Any]] = []
    for construction, interval in declared_cells():
        sig = build_signal(events, bar_open_ms, construction=construction)
        n_hit = int(np.count_nonzero(sig))
        cells.append(
            screen_cell(
                sig,
                close,
                name=f"annc_{label}_{construction}_{interval}m",
                interval_min=interval,
                n_events=n_hit,
                charged=construction != SAME_BAR_CONTROL,
            )
        )
    return cells


def run_screen(
    *,
    announcements_path: Path | None = None,
    bar_root: Path | None = None,
) -> dict[str, Any]:
    """Full pre-registered run against on-disk data, or a NOT-READABLE-HERE artifact naming what
    is missing.  NEVER simulates and never substitutes synthetic data."""
    rows, missing_rows = load_announcements(announcements_path)
    header: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "screen": "announcement_diffusion",
        "census_gap": {"rank": 6, "class_id": "scheduled_event_diffusion", "score": 0.315},
        "law": (
            "Stage-A only (two-stage law): ZERO promotion authority.  A pass earns a "
            "pre-registered forward clock, never capital."
        ),
        "alpha": 0.05,
        "pre_registered": {
            "constructions": list(CONSTRUCTIONS),
            "artifact_control": SAME_BAR_CONTROL,
            "intervals_min": list(INTERVALS_MIN),
            "declared_cells": NEW_CELLS,
            "prior_parameterisations_charged": PRIOR_PARAMETERISATIONS,
            "multiplicity_charge": TOTAL_TRIALS,
            "min_precision_accepted": MIN_PRECISION,
        },
        "alignment": {
            "announcement_clock": "`published_at` (publisher stamp); `first_seen` NEVER used",
            "price_clock": "Binance `open_time`, venue stamp, bar-open labelled, UTC",
            "rule": (
                "signal stamped at bar k containing the instant; harness predicts return[k+1], "
                "which begins at close_k and is entirely after the instant"
            ),
            "same_bar_guard": (
                "return[k] (the bar containing the instant) is what the angle-20 gate measures "
                "contamination against; it is never the predicted bar"
            ),
        },
    }
    if missing_rows:
        header["status"] = NOT_READABLE
        header["verdict"] = NOT_READABLE
        header["missing_inputs"] = list(missing_rows)
        header["instant_recoverable"] = False
        header["power"] = indeterminate(
            "announcement_diffusion",
            "announcement log absent; no sample, therefore no detection floor",
            source="libs/research/announcement_diffusion.py",
            effect_unit="ic",
        ).as_dict()
        header["graveyard"] = []
        return header

    audit = instant_audit(rows)
    header["instant_audit"] = audit
    header["instant_recoverable"] = audit["instant_recoverable"]
    header["desk_latency"] = desk_latency_summary(rows)
    header["tradeability"] = (
        "The desk's own first_seen latency is reported per source above.  Where the minimum "
        "latency exceeds the diffusion window being tested, a statistically real effect is "
        "still unreachable BY THIS DESK: the mechanism's payer is the slower participant, and "
        "on this feed the desk is measurably slow."
    )

    screenable = tuple(r for r in rows if r.screenable)
    have = available_symbols(bar_root)
    resolved: dict[str, list[Announcement]] = {}
    n_unresolved = 0
    for ann in screenable:
        pair = resolve_asset(ann)
        if pair is None:
            n_unresolved += 1
            continue
        resolved.setdefault(pair, []).append(ann)

    coverage = {
        pair: {
            "n_announcements": len(v),
            "intervals_with_bars": sorted(i for i, s in have.items() if pair in s),
        }
        for pair, v in sorted(resolved.items())
    }
    header["symbol_coverage"] = coverage
    header["n_unresolved_symbol"] = n_unresolved
    header["subdaily_panel_on_disk"] = {str(k): sorted(v) for k, v in sorted(have.items())}

    usable = {
        pair: v
        for pair, v in resolved.items()
        if any(pair in s for s in have.values()) and len(v) >= MIN_EVENTS_PER_CELL
    }
    if not usable:
        header["status"] = NOT_READABLE
        header["verdict"] = NOT_READABLE
        header["missing_inputs"] = [
            (
                "sub-daily price bars for the ANNOUNCED assets.  The instant IS recoverable "
                f"({audit['n_instant_recovered']}/{audit['n_rows']} rows), but the on-disk "
                "sub-daily lake holds only "
                + ", ".join(sorted(have.get(5, set()) | have.get(60, set())))
                + " while the announcements name newly-listed assets that have no bars here."
            ),
            (
                f"announcement volume: {audit['n_rows']} rows total, "
                f"{n_unresolved} of the instant-bearing rows name no resolvable base asset "
                "(the collector's regex mostly extracts the QUOTE currency).  The floor is "
                f"{MIN_EVENTS_PER_CELL} events on one panel."
            ),
        ]
        header["power"] = indeterminate(
            "announcement_diffusion",
            "instant recovered but no announced asset has a sub-daily price panel on disk; no "
            "cell was screened, so nothing was refuted",
            source="libs/research/announcement_diffusion.py",
            effect_unit="ic",
        ).as_dict()
        header["cells_run"] = 0
        header["cells_declared"] = [
            {"construction": c, "interval_min": i} for c, i in declared_cells()
        ]
        header["graveyard"] = []
        header["reentry_condition"] = (
            "Either (a) extend the sub-daily price lake to the assets the announcement feed "
            "actually names -- newly listed tokens, which is where the mechanism lives -- or "
            "(b) run the collector forward until >= "
            f"{MIN_EVENTS_PER_CELL} instant-bearing announcements accumulate on a symbol whose "
            "bars are already on disk.  Re-run this module unchanged; the constructions are "
            "pre-registered and must not be re-chosen after seeing the data."
        )
        return header

    cells: list[dict[str, Any]] = []
    for pair, evs in sorted(usable.items()):
        for interval in INTERVALS_MIN:
            opens, close = load_bars(pair, interval, bar_root)
            if opens.size == 0:
                continue
            cells.extend(screen_announcements(tuple(evs), opens, close, label=pair))
    header["status"] = "SCREENED"
    header["cells_run"] = len(cells)
    header["cells"] = cells
    header["graveyard"] = [
        {
            "cell": c.get("name"),
            "verdict": c.get("verdict"),
            "reason": c.get("why") or f"harness verdict {c.get('verdict')}",
            "detection_floor_ic": c.get("power", {}).get("min_detectable_effect"),
            "powered": c.get("power", {}).get("label"),
        }
        for c in cells
        if c.get("verdict") != "SCREEN-INTERESTING"
    ]
    header["verdict"] = (
        "SCREEN-INTERESTING"
        if any(
            c.get("verdict") == "SCREEN-INTERESTING" and SAME_BAR_CONTROL not in str(c.get("name"))
            for c in cells
        )
        else UNDERPOWERED
    )
    return header


def power_for_absent_data() -> Type2Cost:
    """The detection floor for a screen that never ran: INDETERMINATE, by construction."""
    return indeterminate(
        "announcement_diffusion",
        "no screenable panel in this checkout; no sample, therefore no detection floor",
        source="libs/research/announcement_diffusion.py",
        effect_unit="ic",
    )
