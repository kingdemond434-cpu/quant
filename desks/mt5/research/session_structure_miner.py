"""EVERY INSTRUMENT'S SESSION IS DERIVED FROM ITS OWN BARS, NEVER INHERITED FROM GOLD.

THE ORDER (principal, 2026-09-23): hunt the session-range-breakout mechanism across forex AND the
Fusion-executable crypto CFDs, so the desk earns on the instruments that trade when gold does not.
The crypto-EXCHANGE universe stays permanently banned -- nothing here touches Binance, Bybit, OKX
or Hyperliquid; these are CFDs on the desk's own venue, which `universe_policy` already places in
the hypothesis lane, and they are what gives genuine weekend coverage.

WHY THIS MODULE EXISTS AT ALL, and it is a measurement, not a hunch. `session_range_breakout` was
read as a dead family -- 0 passes across 1,216 judgements. It is nothing of the kind: 15 of the
desk's 28 ten-gate certificates are this family, more than any other. What the zero actually
measures, off `reports/universal_gates_external.json` 2026-09-23 (2,248 verdicts):

    1,174  never fired at all (days = 0)        -- UNMEASURED, never judged
      255  fired 1-59 days, too rare to judge   -- UNMEASURED
       93  refused at symbol_eligibility        -- CLOSE_ONLY on this account, untradeable
      562  judged, died at in_sample_screen     -- and EVERY ONE had a NEGATIVE Sharpe
      257  judged, died at deflated_sharpe      -- positive but small (median 0.097 vs sr0 0.3786)

So 64% of the family's cells were never evidence about the mechanism at all. They were aimed at
hours where the instrument does not trade, or at instruments that cannot be traded. That is a
MINTING defect, not a dead edge and not a costing error -- and it is the thing this module fixes.

THE MECHANISM, STATED SO IT CAN BE AIMED. A range builds while the instrument is QUIET; the
breakout is worth taking when activity RESUMES. Gold's quiet block happens to sit before 07:00
broker time, which is why the desk's certified gold cells read `range_start=7`. Measured here on
the box's own bars:

    XAUUSD   quiet 23, 7, 21, 6, 2      busiest 16, 17, 15   -- the certified window fits
    EURJPY   quiet 22, 23, 21, 20, 6    busiest 17, 10, 16   -- its quiet block is the EVENING
    USDJPY   quiet 23, 0, 22, 21, 20    busiest 17, 16, 3
    BTCUSD   quiet 13, 9, 7, 12, 14     busiest 17, 16, 18   -- INVERTED against FX

BTCUSD is the case that proves the point. Port gold's window to it and the range is built through
one of its ACTIVE stretches and the breakout is taken at hour 7, its QUIETEST hour. The cell then
fails for a reason that has nothing whatever to do with whether the edge exists.

WHAT IS SWEPT, AND WHY THE BOUNDARY IS A DIMENSION RATHER THAN A CONSTANT. The derived boundary is
an estimate from a noisy profile, so the neighbouring hour is swept beside it; a mechanism that
only works on exactly one derived hour is a fit, and the sweep is what exposes that. Costs, gates
and thresholds are untouched -- `policy/gate_spec.yaml` is not read, let alone written, and the
bar these cells must clear is the same bar every other cell clears.

NO PRIVILEGED PATH. Rows are donated to `data/intelligence/session_structure/` as EXACT_RECIPE
rows and reach the docket through `miner_candidate_compiler` exactly like every other seat's.
Nothing here writes the canonical certificate store, the docket, or any gate.

Artifact: `reports/SESSION_STRUCTURE.json` (the per-instrument profile and the derived boundary,
so the aim is auditable rather than asserted). Run: `python research/session_structure_miner.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE_DIR = BASE / "data" / "universe"
REGISTRY = UNIVERSE_DIR / "universe.json"
OUT = BASE / "reports" / "SESSION_STRUCTURE.json"
DONATION_DIR = BASE / "data" / "intelligence" / "session_structure"

UNMEASURED = "UNMEASURED"

#: Trailing bars the profile is measured over. ~400 trading days of H1: long enough that a single
#: quiet fortnight cannot move an hour's median, short enough that a venue that changed its hours
#: a year ago is not still being described by the old ones.
PROFILE_BARS = 24 * 400

#: The shortest run of quiet hours that can be called a session range. Two hours is noise on an
#: hourly profile; the desk's own certified gold window is seven.
MIN_QUIET_RUN = 3

#: A symbol whose account trade mode is this can be CLOSED but never OPENED, so a cell on it can
#: never be traded whatever it measures. 93 `session_range_breakout` verdicts died here, and
#: every one of them was compute spent on an instrument the account cannot buy.
TRADE_MODE_CLOSE_ONLY = 3

#: Registry `category` substrings that mean a single-name share, checked IN ADDITION to the lane
#: router. Measured 2026-09-23: `mt5desk.universe.asset_class` returns `crypto` for UnionPacific,
#: UnitedHealth and UnitedParcelService, which puts three US share CFDs in the hypothesis lane.
#: That is a defect in the pattern classifier (reported, not fixed here -- `mt5desk/families*.py`
#: and its neighbours are another builder's lane), and this is the belt-and-braces that keeps THIS
#: miner from minting on them. The two-lane order is that single names are traded on news.
SHARE_CATEGORY_MARKS = ("share", "stock", "equit")

#: The parameterisations swept beside each derived boundary. Every one of these is an ordinary
#: dimension of the family's own signature; none of them is a threshold, a cost or a gate.
RR_SWEEP = (1.5, 2.0, 2.5)
WAIT_BARS_SWEEP = (8, 12)
TTL_BARS = 12


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def eligible_symbols(registry: dict[str, Any] | None = None) -> tuple[list[str], dict[str, str]]:
    """The instruments this mechanism may be hunted on, and WHY each rejection happened.

    Three conditions, each of which the desk already decided elsewhere and none of which is
    invented here: the lane router admits it to statistical discovery, the account can OPEN a
    position in it, and the desk holds H1 bars for it.
    """
    reg = registry if registry is not None else (_read_json(REGISTRY, {}) or {})
    try:
        import universe_policy as up
    except ImportError:                                                 # pragma: no cover
        from research import universe_policy as up
    keep: list[str] = []
    why: dict[str, str] = {}
    for symbol, row in sorted(reg.items()):
        if not isinstance(row, dict):
            continue
        if up.lane(symbol) != up.HYPOTHESIS:
            why[symbol] = f"lane {up.lane(symbol)}: not a statistical-discovery instrument"
            continue
        category = str(row.get("category") or "").lower()
        if any(mark in category for mark in SHARE_CATEGORY_MARKS):
            why[symbol] = (f"registry category {row.get('category')!r} is a single-name share; "
                           "its edge is sought in the event lane, never here")
            continue
        try:
            mode = int(row.get("trade_mode"))          # type: ignore[arg-type]
        except (TypeError, ValueError):
            mode = -1
        if mode == TRADE_MODE_CLOSE_ONLY:
            why[symbol] = ("CLOSE_ONLY on this account (trade_mode 3): no new position can be "
                           "opened, so a cell here can never be traded whatever it measures")
            continue
        if not (UNIVERSE_DIR / f"{symbol}_H1.parquet").exists():
            why[symbol] = "no H1 bars on this host: UNMEASURED, never a zero"
            continue
        keep.append(symbol)
    return keep, why


def hourly_profile(symbol: str) -> dict[str, Any]:
    """Median normalised hourly true range, by hour of the broker clock, from this symbol's bars.

    NORMALISED BY PRICE so the hours of a 190-point gold contract and a 0.9 franc cross are
    comparable within their own instrument -- the comparison is always hour-against-hour on ONE
    instrument, never across instruments, so this only has to be monotone.
    """
    import pandas as pd

    path = UNIVERSE_DIR / f"{symbol}_H1.parquet"
    try:
        df = pd.read_parquet(path).tail(PROFILE_BARS)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    if df.empty or not {"high", "low", "close"} <= set(df.columns):
        return {"status": UNMEASURED, "why": "bars carry no high/low/close"}
    index = pd.to_datetime(df.index)
    rng = ((df["high"] - df["low"]) / df["close"].abs()).to_numpy()
    hours = index.hour
    med: dict[int, float] = {}
    count: dict[int, int] = {}
    for hour in range(24):
        mask = hours == hour
        n = int(mask.sum())
        count[hour] = n
        if n:
            med[hour] = float(pd.Series(rng[mask]).median())
    if len(med) < 12:
        return {"status": UNMEASURED, "why": f"only {len(med)} hours of the day carry bars",
                "bars_by_hour": count}
    return {"status": "MEASURED", "median_range_by_hour": med, "bars_by_hour": count,
            "n_bars": len(df),
            "first": str(index[0]), "last": str(index[-1])}


def derive_window(profile: dict[str, Any]) -> dict[str, Any]:
    """The instrument's own quiet run, and the family parameters that express it.

    THE FAMILY CANNOT EXPRESS A WINDOW THAT WRAPS MIDNIGHT, and saying so is the point.
    `family_session_range_breakout` builds its range from `(hour >= range_start) & (hour <
    range_end)`, which is empty whenever `range_end < range_start`. Its other form, `range_end
    is None`, means `hour < range_start` -- the midnight-to-`range_start` window, which is exactly
    the shape the desk's certified gold cells use.

    So a quiet run that wraps (EURJPY's 20-23-plus-early-hours, USDJPY's 20-00) is expressed by
    its POST-MIDNIGHT half and the truncation is RECORDED. That is an honest partial, not a
    silent one: the pre-midnight hours are named in `truncated_hours` so the cost of the family's
    limitation is visible and priceable by whoever owns that family, rather than showing up later
    as an unexplained weak result.
    """
    med = profile.get("median_range_by_hour") or {}
    if profile.get("status") != "MEASURED" or not med:
        return {"status": UNMEASURED, "why": profile.get("why", "no profile")}
    med = {int(h): float(v) for h, v in med.items()}
    ordered = sorted(med)
    typical = sorted(med.values())[len(med) // 2]
    quiet = {h for h in ordered if med[h] < typical}
    if not quiet:
        return {"status": UNMEASURED, "why": "no hour is below this instrument's own median"}
    # Longest contiguous run of quiet hours, read circularly so a run across midnight is found.
    best: list[int] = []
    for start in ordered:
        if (start - 1) % 24 in quiet:
            continue                        # not the beginning of a run
        run: list[int] = []
        hour = start
        while hour in quiet and len(run) < 24:
            run.append(hour)
            hour = (hour + 1) % 24
        if len(run) > len(best):
            best = run
    if len(best) < MIN_QUIET_RUN:
        return {"status": UNMEASURED,
                "why": f"longest quiet run is {len(best)}h, under the {MIN_QUIET_RUN}h minimum: "
                       "this instrument has no session structure to break out of"}
    wraps = best != sorted(best)
    if wraps:
        after_midnight = [h for h in best if h < best[0]]
        truncated = [h for h in best if h >= best[0]]
        if len(after_midnight) < MIN_QUIET_RUN:
            return {"status": UNMEASURED,
                    "why": (f"quiet run {best} wraps midnight and its post-midnight half is only "
                            f"{len(after_midnight)}h; `family_session_range_breakout` cannot "
                            "express a wrapping window, so there is nothing honest to mint here")}
        params = {"range_start": after_midnight[-1] + 1, "range_end": None}
        window = after_midnight
    else:
        truncated = []
        params = {"range_start": best[0], "range_end": best[-1] + 1}
        window = best
    signal_at = (window[-1] + 1) % 24
    return {
        "status": "MEASURED",
        "quiet_hours": sorted(quiet), "quiet_run": best, "wraps_midnight": wraps,
        "window_hours": window, "truncated_hours": sorted(truncated),
        "truncation_why": (
            "family_session_range_breakout builds its range from (hour >= range_start) & "
            "(hour < range_end), which is EMPTY when the window wraps midnight; these hours are "
            "genuinely part of this instrument's quiet run and are not being tested"
            if truncated else ""),
        "range_start": params["range_start"], "range_end": params["range_end"],
        "signal_at": signal_at,
        "busiest_hours": sorted(med, key=lambda h: -med[h])[:3],
    }


def cells_for(symbol: str, window: dict[str, Any]) -> list[dict[str, Any]]:
    """Every parameterisation to mint for one instrument, the boundary swept beside its estimate.

    THE BOUNDARY IS A DIMENSION. The derived hour is an estimate off a noisy median profile, so
    the next hour is swept with it: a mechanism that survives on exactly one derived hour and
    dies on its neighbour is a fit, and this is what makes that visible instead of flattering.
    """
    if window.get("status") != "MEASURED":
        return []
    out: list[dict[str, Any]] = []
    for signal_at in (int(window["signal_at"]), (int(window["signal_at"]) + 1) % 24):
        for rr in RR_SWEEP:
            for wait_bars in WAIT_BARS_SWEEP:
                params: dict[str, Any] = {
                    "range_start": int(window["range_start"]),
                    "signal_at": signal_at, "wait_bars": wait_bars,
                    "rr": rr, "ttl_bars": TTL_BARS,
                }
                if window.get("range_end") is not None:
                    params["range_end"] = int(window["range_end"])
                out.append({
                    "kind": "hypothesis",
                    "source": "session_structure",
                    "family": "session_range_breakout",
                    "symbols": [symbol],
                    "params": params,
                    "mechanism": (
                        f"{symbol} is quietest across hours {window['window_hours']} on its own "
                        f"bars and most active at {window['busiest_hours']}; a range built while "
                        f"the instrument is quiet and broken as activity resumes at "
                        f"{signal_at:02d}:00 broker time is the same mechanism the desk already "
                        f"holds certificates for on gold, aimed at THIS instrument's session "
                        f"rather than gold's"),
                    "derived_from": "median normalised hourly range over this symbol's own H1 bars",
                })
    return out


def run(write: bool = True, donate: bool = True) -> dict[str, Any]:
    """Profile every eligible instrument, derive its window, and donate the sweep."""
    started = datetime.now(UTC)
    symbols, rejected = eligible_symbols()
    instruments: dict[str, Any] = {}
    cells: list[dict[str, Any]] = []
    unmeasured: dict[str, str] = {}
    for symbol in symbols:
        profile = hourly_profile(symbol)
        window = derive_window(profile)
        instruments[symbol] = {
            "bars": profile.get("n_bars", UNMEASURED),
            "window": window,
            "median_range_by_hour": profile.get("median_range_by_hour", UNMEASURED),
        }
        if window.get("status") != "MEASURED":
            unmeasured[symbol] = str(window.get("why"))
            continue
        cells.extend(cells_for(symbol, window))
    payload: dict[str, Any] = {
        "at": started.isoformat(timespec="seconds"),
        "law": ("EVERY INSTRUMENT'S SESSION IS DERIVED FROM ITS OWN BARS. A session-range cell "
                "whose window is inherited from another instrument fails for a reason that has "
                "nothing to do with the edge; 1,174 of 2,248 session_range_breakout verdicts "
                "never fired at all. An instrument with no measurable quiet run is UNMEASURED "
                "and mints nothing -- never a zero, and never a guessed window."),
        "n_eligible": len(symbols), "n_rejected": len(rejected),
        "n_windows_measured": len(symbols) - len(unmeasured),
        "n_unmeasured": len(unmeasured), "unmeasured": unmeasured,
        "n_cells": len(cells),
        "sweep": {"rr": list(RR_SWEEP), "wait_bars": list(WAIT_BARS_SWEEP),
                  "signal_at": "derived hour and the hour after it",
                  "why": ("the derived boundary is an estimate off a noisy profile; a mechanism "
                          "that survives on exactly one hour and dies on its neighbour is a fit")},
        "rejected": rejected,
        "instruments": instruments,
        "donation_dir": str(DONATION_DIR),
        "intake": ("data/intelligence/session_structure/ -> miner_candidate_compiler EXACT_RECIPE "
                   "-> the docket -> the sealed gauntlet. No privileged path; the same ten gates "
                   "at the same thresholds as every other cell."),
    }
    if donate and cells:
        DONATION_DIR.mkdir(parents=True, exist_ok=True)
        stamp = started.strftime("%Y%m%dT%H%M%SZ")
        path = DONATION_DIR / f"discoveries_{stamp}.json"
        path.write_text(json.dumps(cells, indent=1, default=str), encoding="utf-8")
        payload["donated_to"] = str(path)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        tmp.replace(OUT)
    return payload


def render(payload: dict[str, Any]) -> str:
    lines = [f"SESSION STRUCTURE  eligible={payload.get('n_eligible')} "
             f"windows={payload.get('n_windows_measured')} "
             f"unmeasured={payload.get('n_unmeasured')} cells={payload.get('n_cells')}"]
    for symbol, row in list((payload.get("instruments") or {}).items())[:12]:
        w = row.get("window") or {}
        if w.get("status") == "MEASURED":
            lines.append(f"  {symbol:10s} quiet {w.get('window_hours')} -> signal "
                         f"{w.get('signal_at'):02d}:00  busiest {w.get('busiest_hours')}"
                         + ("  TRUNCATED " + str(w.get("truncated_hours"))
                            if w.get("truncated_hours") else ""))
        else:
            lines.append(f"  {symbol:10s} UNMEASURED -- {w.get('why')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="derive and report, donate nothing")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run, donate=not args.dry_run)
    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
