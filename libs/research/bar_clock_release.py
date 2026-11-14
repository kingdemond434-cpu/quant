"""The bar clock MEASURED FROM THE DESK'S OWN DATA, for when `BAR_CLOCK.json` is absent.

WHY (2026-10-20, judge never_fires follow-up). `bar_clock.offsets()` reads one file,
`desks/mt5/reports/BAR_CLOCK.json`, which `research/futures_lead_lag.py` writes from a Yahoo feed
stamped in epoch seconds. That file is gitignored and box-local, and where it is missing every
UTC join is dropped: `family_event_reaction` placed 0 of 198 calendar events, so 3,209
event_reaction cells per sweep came back never_fires on bars that were present. The cells were not
scarce; the clock was unread.

THE MEASUREMENT. A high-impact scheduled release is an instant stamped in genuine UTC by the
calendar (`event_date` carries its own offset, e.g. `-04:00`), and it makes the largest bar range
of its day on the instruments quoted in its currency. So for each candidate offset k the bar the
release WOULD sit in -- the bar labelled `release + k hours` -- is looked up, and its range is
compared with the instrument's median bar range. On the broker's clock the spike sits at exactly
one k. Measured on this tree (summer, 2026-08-23..09-12, 6-8 releases per instrument), every
instrument resolves +3 and no other hour comes close:

    XAUUSD M5   k=+3 10.35x   next best k=+4 2.64x
    EURUSD H1   k=+3  3.12x   next best k=+4 1.88x
    GBPUSD H1   k=+3  2.14x   next best k=+4 1.20x
    USDJPY H1   k=+3  3.14x   next best k=+4 1.82x
    AUDUSD H1   k=+3  2.72x   next best k=+4 1.03x

That agrees with the +3 summer offset `futures_lead_lag` documents, by a different instrument
(the release, not a futures feed) with the same property: the reference stamp is UTC by
construction and carries no convention to be wrong about.

WHAT IT KEEPS FROM `bar_clock`, unchanged:

  * NO GUESS. A season resolves only when at least MIN_INSTRUMENTS instruments each resolve one k
    clearly (best spike >= MIN_SPIKE x the median bar and >= MIN_MARGIN x the runner-up) on at
    least MIN_EVENTS releases, and all of them agree. Otherwise the season is absent and the
    caller drops the join exactly as before.
  * SEASONS ARE MEASURED SEPARATELY, from releases inside that season's window only. The shoulder
    months are still refused by `bar_clock.to_bar_time`; this never answers for them.
  * NAIVE STAMPS ARE NOT USED. A release time with no offset of its own is on an unknown clock and
    cannot be a reference for one.
  * NOTHING IS WRITTEN. The reading is computed in-process from files already on disk and cached
    for the process; the measured file, when present, always wins.

It reads only the price path's RANGE around a release, never its direction, so it cannot favour
either side of a drift/fade hypothesis that is later judged on the same bars.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

#: The desk's own UTC-stamped release calendar.
CALENDAR_REL = "desks/mt5/data/intelligence/ff_calendar_vintage"
UNIVERSE_REL = "desks/mt5/data/universe"

#: Liquid instruments quoted in the currencies the calendar's high-impact releases name. The
#: first chart that exists, finest first, is read; an absent instrument simply does not vote.
INSTRUMENTS: tuple[str, ...] = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
                                "NZDUSD", "USDCHF",
                                # NON-USD-QUOTED VOTERS (audit of b9d37faaa): every USD pair reads
                                # the same USD releases, so agreement among them is one reading
                                # counted several times. A cross reads its own currencies' releases.
                                "AUDCAD", "NZDCAD", "EURGBP", "EURAUD", "GBPAUD", "EURJPY",
                                "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "AUDNZD", "EURCHF")
CHARTS: tuple[str, ...] = ("M5", "M15", "H1")

#: Candidate offsets, wider than any broker uses so the answer is not boxed in by the search.
CANDIDATES: tuple[int, ...] = tuple(range(-2, 7))

MIN_EVENTS = 5
MIN_INSTRUMENTS = 3
#: Distinct release instants behind the agreed offset, counted once however many instruments
#: read them (audit of b9d37faaa: seven USD voters read the same 18 instants).
MIN_INDEPENDENT_RELEASES = 10
#: Per-release agreement: the winner's share of releases. An earlier peak is placed late, which
#: is safe; a LATER one is excluded (below).
MIN_RELEASE_SHARE = 0.6
#: PER-RELEASE EXCLUSION (auditor's ruling on 970d1622c). A release whose own peak is later than
#: the winning offset is EXCLUDED -- named, billed, and never converted -- and the instrument
#: still resolves on the rest, unless the late releases are not isolated:
#:
#:   * MAX_EXCLUDED_SHARE. At most one late release in five. The floor this module already
#:     admits a reading on is MIN_EVENTS = 5 releases, and 1 in 5 is the most that floor can lose
#:     to an isolated late peak while still being a sample at all: a second late release in five
#:     is 40%, the entire non-winning budget MIN_RELEASE_SHARE = 0.6 tolerates, spent on the one
#:     direction that is a look-ahead. Above 20% the late peaks are a population, not noise, and
#:     the offset itself is suspect. (Measured on this tree for what it decides, never fitted to
#:     it: GBPUSD 1 of 8 and AUDCAD 1 of 6 late, both under it.)
#:   * A CLUSTER. MIN_CLUSTER or more late releases within BOUNDARY_DAYS of the same daylight-
#:     saving changeover or season-window edge, or forming an unbroken run at the start or end of
#:     the instrument's own sample. That is the signature of an offset that changed part-way --
#:     wrong for a span, not an isolated release -- so the instrument refuses.
MAX_EXCLUDED_SHARE = 0.2
MIN_CLUSTER = 2
#: One calendar week: the weekly release cycle (claims, CPI, payrolls weeks), so consecutive
#: releases after a changeover land inside it together.
BOUNDARY_DAYS = 7
MIN_SPIKE = 2.0
MIN_MARGIN = 1.5

#: Re-check the inputs' signature at most this often inside one process.
RECHECK_S = 600.0

_CACHE: dict[str, tuple[float, tuple[tuple[str, int, int], ...], dict[str, Any]]] = {}


def _rows(path: Path) -> list[dict[str, Any]]:
    """Every row of one calendar vintage: a JSON list/{rows}, or JSON lines (optionally gzip)."""
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = path.read_text(encoding="utf-8")
    except (OSError, ValueError, EOFError):
        return []
    try:
        doc = json.loads(text)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows", [])
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except ValueError:
        pass
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def calendar_files(root: Path) -> list[Path]:
    base = root / Path(*CALENDAR_REL.split("/"))
    return sorted(base.glob("*.json*")) if base.exists() else []


def _releases(root: Path) -> list[tuple[Any, frozenset[str]]]:
    """(UTC instant, currencies) of every high-impact release with an explicit offset."""
    import pandas as pd
    seen: dict[Any, set[str]] = {}
    for path in calendar_files(root):
        for row in _rows(path):
            if str(row.get("impact", "")).lower() != "high":
                continue
            raw = row.get("event_date")
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                ts = pd.Timestamp(raw)
            except (TypeError, ValueError):
                continue
            if ts is pd.NaT or ts.tzinfo is None:
                continue
            ccys = {str(c).upper() for c in (row.get("symbols") or []) if isinstance(c, str)}
            seen.setdefault(ts.tz_convert("UTC"), set()).update(ccys)
    return sorted((t, frozenset(c)) for t, c in seen.items())


def _bars(root: Path, symbol: str) -> tuple[str, Any] | None:
    import pandas as pd
    base = root / Path(*UNIVERSE_REL.split("/"))
    for chart in CHARTS:
        path = base / f"{symbol}_{chart}.parquet"
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path, columns=["high", "low", "close"])
        except (OSError, ValueError, KeyError):
            continue
        if not isinstance(frame.index, pd.DatetimeIndex) or len(frame) < 100:
            continue
        idx = frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
        frame = frame.set_axis(idx).sort_index()
        return chart, frame[~frame.index.duplicated(keep="last")]
    return None


def _sunday(year: int, month: int, nth: int) -> Any:
    """The nth Sunday of a month (nth = -1 for the last)."""
    from datetime import date, timedelta
    if nth > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (nth - 1))
    nxt = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return nxt - timedelta(days=(nxt.weekday() + 1) % 7)


def boundaries(year: int) -> list[tuple[Any, str]]:
    """Every clock boundary of a year: the EU and US daylight-saving changeovers, and the edges
    of the measured season windows."""
    from datetime import date

    from libs.research.bar_clock import SEASON_WINDOWS
    out = [(_sunday(year, 3, -1), "EU spring changeover"), (_sunday(year, 10, -1),
                                                            "EU autumn changeover"),
           (_sunday(year, 3, 2), "US spring changeover"), (_sunday(year, 11, 1),
                                                           "US autumn changeover")]
    for name, (lo, hi) in SEASON_WINDOWS.items():
        out += [(date(year, lo // 100, lo % 100), f"{name} window start"),
                (date(year, hi // 100, hi % 100), f"{name} window end")]
    return out


def _cluster(late: list[Any], every: list[Any]) -> str:
    """Why the late releases are NOT isolated, or '' when they are."""
    if len(late) < MIN_CLUSTER:
        return ""
    for year in sorted({t.year for t in late} | {t.year + 1 for t in late}
                       | {t.year - 1 for t in late}):
        for day, name in boundaries(year):
            near = [t for t in late if abs((t.date() - day).days) <= BOUNDARY_DAYS]
            if len(near) >= MIN_CLUSTER:
                return (f"{len(near)} late releases within {BOUNDARY_DAYS} days of the {name} "
                        f"({day}): the offset is wrong for that span, not for one release")
    ordered = sorted(every)
    lateset, n = set(late), len(late)
    for edge, run in (("start", ordered[:n]), ("end", ordered[-n:])):
        if n < len(ordered) and all(t in lateset for t in run):
            return (f"the {n} late releases are an unbroken run at the {edge} of the sample "
                    f"({run[0].date()}..{run[-1].date()}): the offset changed part-way")
    return ""


def _instrument(chart_frame: tuple[str, Any], times: list[Any]) -> dict[str, Any]:
    """The offset at which this instrument's release spike sits, or None when unclear.

    THREE REFUSALS, each from an audit probe (JUDGE_DEAD_FAMILIES_28014bbde / b9d37faaa):

      * THE FLOOR IS COUNTED AT THE OFFSETS THAT DECIDE. `MIN_EVENTS` releases must have bars at
        the winning offset AND at the runner-up. The largest sample over all candidates let +3
        resolve from 2 releases when 6 of 8 had no bar there.
      * A MIXED HISTORY IS REFUSED, NEVER VOTED. Each release's own peak offset is read; the
        winner must hold at least MIN_RELEASE_SHARE of the releases. A release that peaks LATER
        than the winner, at any distance, would be entered before its news if converted at the
        winner, so it is EXCLUDED: named in `late_release_excluded`, billed on the missed-growth
        ledger, and never converted (`measure` carries it into the season window, where
        `bar_clock.to_bar_time` refuses it). The rest convert unchanged. The instrument refuses
        only when the late releases are not isolated (MAX_EXCLUDED_SHARE, `_cluster`). Ties read
        as the later hour. An earlier minority is placed late, which is safe, and is counted as
        `early_minority`.
      * `releases` names the instants that support the answer, so the season can count
        independent release instants rather than instruments that read the same ones.
    """
    import numpy as np
    import pandas as pd
    chart, frame = chart_frame
    rng = ((frame["high"] - frame["low"]) / frame["close"]).astype(float)
    rng = rng[np.isfinite(rng)]
    base = float(rng.median()) if len(rng) else 0.0
    if base <= 0:
        return {"chart": chart, "offset_h": None, "why": "no measurable bar range"}
    step = pd.Timedelta(frame.index.to_series().diff().median())
    width = max(step, pd.Timedelta(minutes=10))
    index = rng.index
    per_k: dict[int, dict[Any, float]] = {k: {} for k in CANDIDATES}
    for t in times:
        for k in CANDIDATES:
            start = (t.tz_convert("UTC").tz_localize(None) + pd.Timedelta(hours=k)).floor(step)
            lo = int(index.searchsorted(start, side="left"))
            hi = int(index.searchsorted(start + width, side="left"))
            if hi > lo:
                per_k[k][t] = float(rng.iloc[lo:hi].max()) / base
    spikes = {k: float(np.median(list(v.values()))) for k, v in per_k.items() if v}
    n_at = {k: len(v) for k, v in per_k.items() if v}
    out: dict[str, Any] = {"chart": chart, "n_releases_by_offset": {str(k): n for k, n in
                                                                    n_at.items()},
                           "spike_by_offset": {str(k): round(v, 3) for k, v in spikes.items()}}
    if len(spikes) < 2:
        return {**out, "offset_h": None, "why": "fewer than two candidate offsets on bars"}
    # TIES BREAK TOWARD THE LATER HOUR (audit of 3febc81f6): the later offset is the one that
    # can never place an event before its news, so an exact tie must not hand the win to the
    # earlier one.
    ranked = sorted(spikes.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    (best_k, best), (k2, second) = ranked[0], ranked[1]
    if n_at[best_k] < MIN_EVENTS or n_at[k2] < MIN_EVENTS:
        return {**out, "offset_h": None,
                "why": (f"{n_at[best_k]} releases on bars at the winning {best_k:+d}h and "
                        f"{n_at[k2]} at the runner-up {k2:+d}h, under {MIN_EVENTS}")}
    if best < MIN_SPIKE or best < MIN_MARGIN * second:
        return {**out, "offset_h": None,
                "why": f"no clear spike: best {best:.2f}x at {best_k:+d}h, next {second:.2f}x"}
    # Each release's own peak, over the offsets it has bars at.
    peaks: dict[Any, int] = {}
    for t in times:
        got = {k: per_k[k][t] for k in CANDIDATES if t in per_k[k]}
        if got:
            peaks[t] = max(got, key=lambda k: (got[k], k))     # a tie is read as the later hour
    out["peaks"] = {t.isoformat(): int(k) for t, k in sorted(peaks.items())}
    n_best = sum(1 for k in peaks.values() if k == best_k)
    share = n_best / len(peaks) if peaks else 0.0
    out["release_share_at_offset"] = round(share, 3)
    if share < MIN_RELEASE_SHARE:
        return {**out, "offset_h": None,
                "why": (f"mixed history: only {n_best} of {len(peaks)} releases peak at "
                        f"{best_k:+d}h (under {MIN_RELEASE_SHARE:.0%})")}
    # DIRECTION-AWARE, PER RELEASE (audits of 90a7ae175, 3febc81f6 and 970d1622c). Converting
    # with `best_k` places a release whose own peak is LATER -- one hour or several -- on a bar
    # before its spike: an entry before the news. So that RELEASE is excluded, at any share and
    # any distance, and never converted; the instrument's other releases are placed exactly as
    # before. A minority whose peak is EARLIER is placed late, never early: it costs signal, not
    # honesty, and is reported as `early_minority`.
    late = sorted((t, k) for t, k in peaks.items() if k > best_k)
    n_early = sum(1 for k in peaks.values() if k < best_k)
    out["early_minority"] = n_early
    out["late_minority"] = len(late)
    out["late_release_excluded"] = [{"release": t.isoformat(), "peak_h": int(k),
                                     "winning_h": int(best_k)} for t, k in late]
    excluded_share = len(late) / len(peaks) if peaks else 0.0
    out["excluded_share"] = round(excluded_share, 3)
    if late:
        shown = ", ".join(f"{t.date()} at {k:+d}h" for t, k in late)
        if excluded_share > MAX_EXCLUDED_SHARE:
            return {**out, "offset_h": None,
                    "why": (f"mixed history: {len(late)} of {len(peaks)} releases peak LATER "
                            f"than {best_k:+d}h ({shown}), {excluded_share:.0%} over the "
                            f"{MAX_EXCLUDED_SHARE:.0%} an isolated exclusion may take")}
        clustered = _cluster([t for t, _k in late], list(peaks))
        if clustered:
            return {**out, "offset_h": None,
                    "why": f"mixed history: late releases cluster ({shown}); {clustered}"}
    support = sorted(t for t, k in peaks.items() if k == best_k)
    return {**out, "offset_h": int(best_k), "releases": [t.isoformat() for t in support]}


def _usd_quoted(symbol: str) -> bool:
    return "USD" in (symbol[:3], symbol[3:6])


def measure(root: Path) -> dict[str, Any]:
    """{per_season: {name: {offset_h, agrees_across_pairs, window, readings}}}."""
    from libs.research.bar_clock import SEASON_WINDOWS, season_instance, season_of
    releases = _releases(root)
    frames = {s: fb for s in INSTRUMENTS if (fb := _bars(root, s)) is not None}
    per_season: dict[str, Any] = {}
    for season in SEASON_WINDOWS:
        readings: dict[str, Any] = {}
        for sym, fb in frames.items():
            ccys = {sym[:3], sym[3:6]}
            times = [t for t, c in releases
                     if c & ccys and season_of(t.to_pydatetime()) == season]
            readings[sym] = _instrument(fb, times)
        resolved = {s: r for s, r in readings.items() if r.get("offset_h") is not None}
        offs = {r["offset_h"] for r in resolved.values()}
        excluded = _excluded(readings, next(iter(offs)) if len(offs) == 1 else None)
        # An excluded instant supports nothing: it is never converted, so it cannot vouch.
        support = sorted({t for r in resolved.values() for t in r.get("releases", [])}
                         - {x["release"] for x in excluded})
        non_usd = sorted(s for s in resolved if not _usd_quoted(s))
        why = ""
        if len(offs) > 1:
            why = f"resolved instruments disagree: {sorted(offs)}"
        elif len(resolved) < MIN_INSTRUMENTS:
            why = f"{len(resolved)} instruments resolve, under {MIN_INSTRUMENTS}"
        elif len(support) < MIN_INDEPENDENT_RELEASES:
            why = (f"{len(support)} independent release instants support it, under "
                   f"{MIN_INDEPENDENT_RELEASES}")
        elif not non_usd:
            why = ("every agreeing instrument quotes USD: they read the same releases, so no "
                   "independent (non-USD-quoted) instrument confirms the clock")
        agrees = not why
        window = None
        if agrees:
            instances = sorted({season_instance(pd_ts(t)) for t in support})
            window = {"instances": instances, "first": support[0], "last": support[-1],
                      "n_releases": len(support), "instruments": sorted(resolved),
                      "non_usd_instruments": non_usd,
                      # NEVER CONVERTED: `bar_clock.to_bar_time` refuses these instants.
                      "excluded_releases": excluded}
        per_season[season] = {"offset_h": next(iter(offs)) if agrees else None,
                              "agrees_across_pairs": agrees, "instruments_resolved":
                              len(resolved), "independent_releases": len(support),
                              "window": window, "why": why or "resolved",
                              "readings": readings}
    return {"measured_by": ("release-spike alignment: the bar labelled release+k hours carries "
                            "the day's range spike only at the broker's true offset; releases are "
                            "UTC-stamped by the calendar with their own offset"),
            "n_releases": len(releases), "per_season": per_season}


def _excluded(readings: dict[str, Any], offset: int | None) -> list[dict[str, Any]]:
    """Every release instant any instrument read as peaking LATER than the season's offset --
    resolved instrument or not, because the instant is converted for every symbol alike."""
    if offset is None:
        return []
    by: dict[str, dict[str, Any]] = {}
    for sym, r in sorted(readings.items()):
        for t, k in (r.get("peaks") or {}).items():
            if int(k) > offset:
                row = by.setdefault(t, {"release": t, "peak_h": int(k), "instruments": []})
                row["peak_h"] = max(row["peak_h"], int(k))
                row["instruments"].append(sym)
    return [by[t] for t in sorted(by)]


def pd_ts(raw: str) -> Any:
    import pandas as pd
    return pd.Timestamp(raw).to_pydatetime()


def _signature(root: Path) -> tuple[tuple[str, int, int], ...]:
    sig: list[tuple[str, int, int]] = []
    paths = list(calendar_files(root))
    base = root / Path(*UNIVERSE_REL.split("/"))
    paths += [base / f"{s}_{c}.parquet" for s in INSTRUMENTS for c in CHARTS]
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        sig.append((p.name, int(st.st_mtime), int(st.st_size)))
    return tuple(sig)


def reading(root: Path) -> dict[str, Any]:
    """The cached measurement for `root`; recomputed only when its inputs change. Never raises."""
    key = str(Path(root).resolve())
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < RECHECK_S:
        return hit[2]
    sig = _signature(Path(root))
    if hit is not None and hit[1] == sig:
        _CACHE[key] = (now, sig, hit[2])
        return hit[2]
    try:
        doc = measure(Path(root)) if sig else {"per_season": {}}
    except Exception as exc:                                            # fail closed: no clock
        doc = {"per_season": {}, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    _CACHE[key] = (now, sig, doc)
    return doc


def offsets(root: Path) -> dict[str, int]:
    """Season -> offset, for seasons the release spikes resolve. {} otherwise."""
    out: dict[str, int] = {}
    for name, block in (reading(root).get("per_season") or {}).items():
        if isinstance(block, dict) and isinstance(block.get("offset_h"), int) \
                and block.get("agrees_across_pairs"):
            out[str(name)] = int(block["offset_h"])
    return out


def windows(root: Path) -> dict[str, dict[str, Any]]:
    """Season -> the window the offset was measured on: season instances, first/last release."""
    out: dict[str, dict[str, Any]] = {}
    for name, block in (reading(root).get("per_season") or {}).items():
        if isinstance(block, dict) and block.get("agrees_across_pairs") \
                and isinstance(block.get("window"), dict):
            out[str(name)] = block["window"]
    return out
