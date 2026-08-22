"""Read the macro state vector that `research/macro_desk.py` writes 24/7.

WHY THIS FILE EXISTS (III.16, and it is the whole point)

`research/macro_desk.py` is a perpetual watcher. It pulls 22 FRED series,
maintains a point-in-time ALFRED vintage lake so a backtest cannot read a
revision nobody had on the day, computes a state vector, and writes
`data/macro_state.json` every cycle. Its own docstring says that file is
"consumed by desks and the reaction atlas."

Nothing read it. A repo-wide grep for `macro_state`, `GROWTH_STATE` and
`reaction_atlas` returned the writer and nothing else -- zero consumers. So
the desk computed a serious macro state around the clock and no family, gate
or filter ever saw one value of it. That is III.16 exactly: written, tested,
correct, and wired to nothing. This module is the wire.

WHAT IT DELIBERATELY DOES NOT DO

It does not decide anything. It reads the state, says how old it is, and
exposes derived quantities the desk's research actually names. Whether a
family conditions on any of it is that family's business and must be tested,
not asserted here -- a macro filter asserted rather than measured is just a
new untested hypothesis wearing a fact's clothing.

STALENESS FAILS CLOSED, LOUDLY

The macro state carries an `updated` timestamp. A macro vector read as
current when it is a week old is the absence-read-as-clean defect (L1.28a)
in its most expensive form: every conditioned decision inherits a stale
world and nothing anywhere reports a problem. `load()` therefore returns a
state whose `.stale` is True past `max_age_hours`, and `.usable` is False --
callers that ignore that get an explicit UNMEASURED, never a clean read.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

BASE = Path(__file__).resolve().parent.parent
STATE_F = BASE / "data" / "macro_state.json"

#: FRED publishes most macro series monthly; daily rates series refresh on
#: business days. 48h keeps a Friday read usable through the weekend while
#: still catching a watcher that has actually stopped.
DEFAULT_MAX_AGE_H = 48.0


@dataclass(frozen=True)
class MacroRegime:
    """One reading of the macro state vector, with its own age attached.

    Every field mirrors what `macro_desk.py` computed. Nothing is recomputed
    here -- a second implementation of the same state is a second source of
    truth, and the two drift silently.
    """
    updated: Optional[datetime]
    age_hours: float
    stale: bool
    detail: str
    states: dict[str, Any]

    @property
    def usable(self) -> bool:
        """False when the state is missing, unparseable or stale.

        A caller that treats `usable is False` as "no macro tilt" is correct.
        A caller that treats it as "neutral macro" is NOT -- neutral is a
        measurement, absence is not, and conflating them is the defect this
        whole module is built against.
        """
        return self.updated is not None and not self.stale

    def get(self, key: str) -> Optional[float]:
        """One state value, or None when absent/unusable. Never a default.

        Returning 0.0 for a missing state would read as "neutral" at every
        call site and is precisely the substitution L1.28a forbids.
        """
        if not self.usable:
            return None
        v = self.states.get(key)
        return float(v) if isinstance(v, (int, float)) else None

    @property
    def real_rate(self) -> Optional[float]:
        """POLICY_RATE - INFLATION_STATE: the classic gold driver.

        Gold pays no coupon, so its opportunity cost is the REAL rate, not
        the nominal one. This is the single most-cited macro relationship for
        XAUUSD and the reason a nominal-rate-only view misreads gold in an
        inflationary cut cycle. Exposed as a derived property because both
        inputs come from the same vintage-correct source -- computing it at
        call sites would let two callers derive it differently.

        NOTE ON UNITS: POLICY_RATE is in percent (3.75), INFLATION_STATE is a
        z-score, not a percent. The difference is therefore an INDEX, not a
        real yield in percent, and must be used as an ordinal signal only.
        Naming it `real_rate` and treating it as a yield would be a unit
        error that no test would catch.
        """
        pol, inf = self.get("POLICY_RATE"), self.get("INFLATION_STATE")
        if pol is None or inf is None:
            return None
        return pol - inf

    def render(self) -> str:
        """Human/model-readable block. Says UNMEASURED when it is."""
        if not self.usable:
            return f"MACRO STATE: UNMEASURED ({self.detail})"
        lines = [f"MACRO STATE (as of {self.updated:%Y-%m-%d %H:%MZ}, "
                 f"{self.age_hours:.0f}h old):"]
        for k, v in sorted(self.states.items()):
            if isinstance(v, bool):
                lines.append(f"  {k:<22} {v}")
            elif isinstance(v, (int, float)):
                lines.append(f"  {k:<22} {v:+.3f}")
            elif v is None:
                lines.append(f"  {k:<22} UNMEASURED")
        rr = self.real_rate
        if rr is not None:
            lines.append(f"  {'REAL_RATE_INDEX':<22} {rr:+.3f}  "
                         f"(POLICY_RATE - INFLATION_STATE; ordinal, not a yield)")
        return "\n".join(lines)


def load(path: Path = STATE_F, max_age_hours: float = DEFAULT_MAX_AGE_H,
         now: Optional[datetime] = None) -> MacroRegime:
    """Read the macro state. Never raises; absence is a state, not an error.

    A macro reader that throws on a missing file makes every caller wrap it
    in a try/except whose except branch invents a neutral default -- which is
    the substitution this module exists to prevent. So absence is returned as
    an unusable MacroRegime that says so.
    """
    now = now or datetime.now(tz=timezone.utc)
    if not path.exists():
        return MacroRegime(None, float("inf"), True,
                           f"{path} absent -- macro_desk.py has not run here", {})
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return MacroRegime(None, float("inf"), True, f"unreadable: {e}", {})

    raw = doc.get("updated")
    try:
        updated = datetime.fromisoformat(raw) if raw else None
    except (TypeError, ValueError):
        updated = None
    if updated is None:
        return MacroRegime(None, float("inf"), True,
                           "no parseable 'updated' timestamp -- age UNKNOWN, "
                           "which is not the same as fresh", doc.get("states", {}))
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    age_h = (now - updated).total_seconds() / 3600.0
    stale = age_h > max_age_hours
    detail = (f"{age_h:.1f}h old (> {max_age_hours:.0f}h limit) -- macro_desk.py "
              f"may have stopped" if stale else f"{age_h:.1f}h old")
    return MacroRegime(updated, age_h, stale, detail, doc.get("states", {}) or {})


def is_fresh(path: Path = STATE_F, max_age_hours: float = DEFAULT_MAX_AGE_H) -> bool:
    """Convenience for alerting: has the macro watcher actually been running."""
    return load(path, max_age_hours).usable


# --------------------------------------------------------------------------
# Historical macro — the part a backtest can actually condition on
# --------------------------------------------------------------------------
#
# `macro_state.json` is a SNAPSHOT: today's vector, nothing else. It can
# condition a live decision and cannot condition a backtest, because there is
# no history in it. `data/cross_asset_anchors.pkl` is the series version --
# daily, aligned, 2010 to now -- and it is what makes macro conditioning
# TESTABLE rather than merely assertable.

ANCHORS_F = BASE / "data" / "cross_asset_anchors.pkl"

#: Beyond this many days, a carried-forward macro value stops being "the last
#: print" and becomes an assumption. FRED market series publish on business
#: days, so 5 covers a holiday week and refuses to invent a month.
MAX_FFILL_DAYS = 5


def load_history(path: Path = ANCHORS_F) -> "Any":
    """Daily macro series with a real 10y yield attached, or None if absent.

    Returns a pandas DataFrame indexed by date. Adds one derived column:

      REAL_YIELD_10Y = DGS10 - T10YIE

    which is the ACTUAL 10-year real yield in percent -- nominal 10y minus
    the 10y breakeven -- not the ordinal index `MacroRegime.real_rate`
    computes from the snapshot's z-scores. This is the textbook gold driver:
    gold pays no coupon, so the real yield IS its opportunity cost, and the
    two quantities must not be confused, which is why they are named
    differently and documented in both places.

    NO PUBLICATION-VINTAGE PROBLEM HERE, and it is worth saying why rather
    than leaving it to be rediscovered: DGS10, T10YIE, VIX, DXY, SPX and CL
    are MARKET-OBSERVED series printed the same day they refer to. They are
    not revised the way PAYEMS and CPIAUCSL are, so joining them on their own
    date introduces no look-ahead. A CPI or payrolls series in this frame
    WOULD need the ALFRED vintage lake and must not be added here casually.

    Gaps are forward-filled at most `MAX_FFILL_DAYS` days. An unlimited ffill
    is how a series that stopped publishing in March silently conditions
    December's trades on March's world.
    """
    import pandas as pd                                       # noqa: PLC0415

    if not Path(path).exists():
        return None
    try:
        df = pd.read_pickle(path)
    except Exception:                                          # noqa: BLE001
        return None
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None

    df = df.sort_index()
    if "DGS10" in df.columns and "T10YIE" in df.columns:
        real = df["DGS10"] - df["T10YIE"]
        df = df.assign(REAL_YIELD_10Y=real)
    return df.ffill(limit=MAX_FFILL_DAYS)


__all__ = ["MacroRegime", "load", "load_history", "is_fresh",
           "STATE_F", "ANCHORS_F", "DEFAULT_MAX_AGE_H", "MAX_FFILL_DAYS"]
