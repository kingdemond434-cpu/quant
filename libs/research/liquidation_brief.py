"""RECENT FORCED FLOW, IN A FORM AN LLM BRIEF CAN USE -- read from the file that exists.

R0245. Two sleeves asked for liquidation context and neither has ever had any. Both spelled the
path ``data/liquidations.jsonl``, which has never existed on this box; the producer
(``scripts/liquidation_listener.py``) has written ``data/liquidations.parquet`` since 2026-07-09
and holds ~59k events. The read sat inside ``except OSError``, so each brief recorded
"ABSENT on this host" -- a string indistinguishable from a genuinely dead collector -- and
nothing ever compared the two spellings. A path read by code and written by nothing is L1.40's
READ-WITHOUT-WRITER class, the one the desk calls its most prolific.

WHY THIS IS NOT THE ONE-LINE PATH SWAP THE ROW ASKED FOR. ``tail -n 6`` of a line-oriented file
gives six INDIVIDUAL liquidation prints. On this tape the last six are consecutive BTCUSDT rows
worth $65 to $3,261, all inside two seconds. That is a technically-wired feed carrying no
information: nothing in six rows distinguishes a cascade from background noise, and a sleeve
handed them would be no better off than with the ABSENT string it has now. Forced flow is legible
only in AGGREGATE -- how much, which way, and against what is normal here.

THE BASELINE IS THE LOAD-BEARING HALF. "$4.2M of longs liquidated in the last hour" means nothing
without "against an hourly median of $0.3M over the trailing day". The RATIO is what says
cascade, it is what a trader would actually condition on, and it costs one extra pass over a
frame already in memory.

THE SIDE FIELD IS AMBIGUOUS AND IS REPORTED AS SUCH. The desk's own screen over this same file
(``scripts/screen_liquidation_reversion.py``) records that Bybit's ``allLiquidation`` carried the
ORDER side in one stream generation and the POSITION side in another, that the two are exact
opposites, and that it therefore counts BOTH mappings as separate trials. So this module names
the raw venue side and says the mapping is uncalibrated rather than silently picking one and
handing a sleeve a directional read that may be backwards. An undeclared field convention is an
assumption wearing a measurement's clothes (L1.46).

STALENESS IS DATA, NOT AN ERROR. The listener is a long-running websocket service and the desk
has already paid for a listener that held a fresh heartbeat while archiving zero events for 14
days. A window with no events is therefore reported WITH the age of the newest event on the tape,
so "the market is quiet" and "the collector died" cannot read the same way.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from libs.core.time import utcnow

#: The producer's own output path (scripts/liquidation_listener.py:33). Named once, here, so a
#: third reader cannot invent a fourth spelling.
REL = "data/liquidations.parquet"

#: Columns the summary needs. Reading a subset is not just speed -- a schema change that drops
#: one of these should raise here, in a module whose whole job is this file, rather than surface
#: as a silently missing line inside a trading brief.
_COLS = ["ts", "symbol", "side", "notional"]

#: Complete hours of tape OUTSIDE the reported window required before a ratio is published. Two
#: hours of history is not a normal, and a ratio a reader cannot distinguish from a real one is
#: worse than the absence of a ratio.
_MIN_BASELINE_HOURS = 6


@dataclass(frozen=True)
class LiquidationWindow:
    """What the tape says about forced flow right now, plus how much to trust it."""

    status: str                       # MEASURED | ABSENT | UNREADABLE | EMPTY
    lines: list[str]
    window_min: int
    n_events: int
    newest_age_h: float | None
    detail: str

    def for_brief(self) -> list[str] | str:
        """The shape both sleeves already put in their brief dict: lines, or one status string."""
        return self.lines if self.lines else self.detail


def summarize(
    root: Path | str,
    *,
    window_min: int = 60,
    baseline_h: int = 24,
    top: int = 6,
    now: pd.Timestamp | None = None,
) -> LiquidationWindow:
    """Summarise the last ``window_min`` minutes of the liquidation tape against its own baseline.

    ``now`` exists for tests only. It defaults to the real clock rather than to the tape's last
    row on purpose: taking "now" from the data would make a dead collector's final hour look like
    the present forever, which is the exact failure this file's staleness line exists to expose.
    """
    p = Path(root) / REL
    if not p.exists():
        return LiquidationWindow(
            "ABSENT", [], window_min, 0, None,
            f"ABSENT on this host -- nothing has written {REL}")
    try:
        df = pd.read_parquet(p, columns=_COLS)
    except (OSError, ValueError, KeyError) as exc:
        # UNREADABLE stays distinct from ABSENT (L1.55): "no producer has ever run" and "one ran
        # and wrote garbage" demand opposite responses, and a desk that cannot tell them apart
        # debugs the wrong organ.
        return LiquidationWindow(
            "UNREADABLE", [], window_min, 0, None,
            f"UNREADABLE ({type(exc).__name__}) -- {REL} exists but did not parse")
    if df.empty:
        return LiquidationWindow(
            "EMPTY", [], window_min, 0, None,
            f"{REL} exists and holds ZERO events -- the listener is connected but archiving "
            f"nothing (a heartbeat proves the loop is alive, never that the pipe is)")

    ts = pd.to_datetime(df["ts"], utc=True)
    at = pd.Timestamp(now) if now is not None else pd.Timestamp(utcnow())
    newest_age_h = float((at - ts.max()).total_seconds() / 3600.0)

    cut = at - pd.Timedelta(minutes=window_min)
    win = df[ts >= cut]
    # THE BASELINE EXCLUDES THE WINDOW IT IS JUDGING. Found by this module's own test: with a
    # short tape the trailing-24h slice contained nothing BUT the current window, so the median
    # was computed from the very events being compared to it and the ratio was 1.0x BY
    # CONSTRUCTION -- a number that reads "normal" on a tape with no history at all. Same shape as
    # the utilisation fence that divided a book by a total containing it (L1.51): a comparison and
    # its own reference may never share a source.
    base = df[(ts >= at - pd.Timedelta(hours=baseline_h)) & (ts < cut)]
    # Median HOURLY notional over the baseline, so the comparison is like-for-like with a window
    # scaled to one hour.
    hourly = (base.assign(_h=pd.to_datetime(base["ts"], utc=True).dt.floor("h"))
                  .groupby("_h")["notional"].sum())
    # And a median over one or two hours is not a baseline either. Below the floor the ratio is
    # REFUSED and the shortfall is named: "no baseline" is a fact a reader can act on, a ratio
    # built from two hours is one they cannot tell apart from a real one.
    med_hourly = float(hourly.median()) if len(hourly) >= _MIN_BASELINE_HOURS else None
    thin = f"only {len(hourly)}h of prior tape" if med_hourly is None else ""

    if win.empty:
        return LiquidationWindow(
            "MEASURED", [], window_min, 0, newest_age_h,
            f"no liquidations in the last {window_min}m; newest event on the tape is "
            f"{newest_age_h:.1f}h old"
            + ("" if newest_age_h < 1.0 else " -- CHECK THE LISTENER, this may be a dead feed "
                                             "rather than a quiet market"))

    total = float(win["notional"].sum())
    scale = 60.0 / max(window_min, 1)
    lines = [
        f"last {window_min}m: ${total:,.0f} forced flow across {len(win)} events"
        + (f" -- {total * scale / med_hourly:.1f}x the {baseline_h}h hourly median "
           f"(${med_hourly:,.0f})" if med_hourly else f" -- no baseline yet ({thin})")
    ]
    by_sym = (win.groupby(["symbol", "side"])["notional"].agg(["sum", "count"])
                 .sort_values("sum", ascending=False).head(top))
    for (sym, side), row in by_sym.iterrows():
        lines.append(f"  {sym} venue-side={side}: ${row['sum']:,.0f} in {int(row['count'])} events")
    lines.append(
        "side is the RAW Bybit allLiquidation field and its long/short mapping is UNCALIBRATED "
        "here -- the stream has carried order-side and position-side in different generations "
        "and they are exact opposites (screen_liquidation_reversion.py). Read it as pressure "
        "magnitude and location, never as a direction.")
    if newest_age_h >= 1.0:
        lines.append(f"WARNING: newest event on the tape is {newest_age_h:.1f}h old")
    return LiquidationWindow(
        "MEASURED", lines, window_min, len(win), newest_age_h,
        f"{len(win)} events in {window_min}m")


def for_brief(root: Path | str, *, window_min: int = 60, top: int = 6) -> list[str] | str:
    """One call for the sleeves: the brief-shaped value, never an exception."""
    return summarize(root, window_min=window_min, top=top).for_brief()
