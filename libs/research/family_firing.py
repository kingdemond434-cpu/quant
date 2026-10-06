"""THE FIRING-HOURS ORACLE: at which server hours can a family's signal actually exist?

WHY THIS EXISTS (2026-09-30, Tier S thread). 43% of judged cells returned UNKNOWN, and 21% of
those UNKNOWNs were `asia` / `london` / `ny` SESSION VARIANTS of families that only ever fire at
one hour. `family_call.session_filter` keeps a signal only when its bar hour falls in the session
window, so `london_close_momentum` (fires at 16) filtered to `asia` [0, 8) is an empty signal list
by construction: the judge spends a slot and the census a trial on a cell that can never trade.
The producers minting the cartesian chart x session axis (`miner_candidate_compiler.expand_axes`,
`breadth_sweep.cells`, the axis proposers) had no way to know, because nothing said when a family
fires.

TWO CLOCKS (2026-09-30, the MT5-losses thread). Bars are broker stamps on New York + 7h
(`libs/regime/session_clock.py`), and the shared
filter compares their SERVER hour with its windows; the markets keep their own local clocks. So
every verdict is taken on both, and DEAD needs BOTH to be empty:
  LIVE                 both clocks hold signals;
  LIVE_FILTER_ONLY     today's server-hour filter holds signals, the market session holds none --
                       the variant TRADES as the desk runs it today (two ten-gate certificates,
                       CHFDKK and EURZAR overnight_gap_decay asia, are exactly this). Kept, never
                       remapped, never sorted last;
  SESSION_TZ_MISMATCH  the market session holds signals and only today's server-hour window
                       misses them -- counted apart and never remapped (pass 2 fixes the filter);
  DEAD                 NEITHER clock holds a signal: the only class a stand-in answers.
THE AUDIT OF #145 (2026-09-30) is why: DEAD was first judged on the market clock alone and so
marked variants dead that fire under the live filter, certified sleeves among them. A guard now
reads the certificate canon and the verdict evidence (`protected`) and never lets a certified,
passed or net-positive cell be DEAD, whatever the hours say.

WHAT IT ANSWERS. For (family, chart, the params that move the hour) it returns the hours the
family's signals land on, MEASURED once on cached bars through the same call the gauntlet makes
(`fn(bars, side=1, **params)`, identity keys stripped, the cell's modifiers applied) and cached
with a VERSION, per SYMBOL (its own bars only). From that, per session: LIVE (the window holds
signals), DEAD (it holds none, on at least `N_MIN` signals) or UNMEASURED. UNMEASURED IS NEVER
DEAD: a family with too few signals, inputs that cannot be rebuilt here, or no bars for the
symbol and chart leaves its variant exactly as it was. Nothing is ever dropped.

WHAT A PRODUCER DOES WITH A DEAD VARIANT (`session_cells`, `replacements`). It mints the
equivalent cell that CAN fire in its place, one for one, so the minted count never falls:
  * the family's hour is a PARAMETER (range_start, signal_hour, fix_hour, decision_hour, hours,
    ...): every hour param is shifted by one delta so the firing hours land on the session's
    open (`family_call.SESSIONS`), making asia / london / ny three live cells. The shift is used
    only once a measurement of the shifted params confirmed it (`shift_verified`), so a family
    whose hour does not move with its parameter is never re-anchored on a guess;
  * the hour is FIXED in code: the cell is re-homed to the session its signals do fall in, and,
    because that plain re-homed cell is usually already minted, the dead slot is filled with the
    same cell conditioned on a desk-defined state the gauntlet applies honestly
    (`cell_modifiers.VOL_REGIMES` / `CALENDAR_REGIMES`) -- a new, judgeable cell at the hours the
    family actually trades.
Each replacement is a NEW cell and is charged to the trial census when the judge reads it, exactly
like every other cell; nothing here is judged for free and nothing here judges.

    python -m libs.research.family_firing --family london_close_momentum --chart H1
"""
from __future__ import annotations

import contextlib
import inspect
import json
import logging
import os
import re
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
UNIVERSE = DESK / "data" / "universe"
CACHE = DESK / "data" / "family_firing_hours.json"

#: Bump when the measurement changes meaning; a cache written under another version is ignored
#: (read as UNMEASURED), never trusted. The full version also carries a hash of the clock's
#: CONVERSION SETTINGS (`clock_hash`: the offset rule and the market-session table the classifier
#: reads), so a change to the conversion re-measures every key, while an edit to the clock
#: module's prose, tests or helpers does not void a cache that is still right.
#: 5: keys carry the symbol and its asset class, and a key is measured on its own symbol only.
SCHEMA_VERSION = 5
UNMEASURED = "UNMEASURED"
LIVE = "LIVE"
DEAD = "DEAD"
#: Fires under the filter the desk applies TODAY (`family_call.SESSIONS`, server hours) and never
#: in the market's own session. It trades as it stands, so it is kept, never remapped, never
#: written to the dead sidecar and never sorted last.
LIVE_FILTER_ONLY = "LIVE_FILTER_ONLY"
#: The oracle's hours alone would say DEAD, but the cell holds a ten-gate certificate, a passed
#: gate verdict or a net-positive verdict. Evidence of trading outranks a measured firing set:
#: kept exactly as it is and counted, so a nonzero count is a defect in the oracle to chase.
PROTECTED = "PROTECTED_BY_EVIDENCE"
#: Dead ONLY because of the clock: the market's own session holds signals, the server-hour
#: window the shared filter applies today (`family_call.SESSIONS`) holds none. Not remapped --
#: the fix to the shared filter (desk pass 2) makes it live -- and counted apart.
TZ_MISMATCH = "SESSION_TZ_MISMATCH"
#: The family's signals never land in the market's session at all: the cause a remap answers.
NEVER_FIRES = "NEVER_FIRES_IN_SESSION"

#: Signals needed before an empty window is called DEAD. Below it the answer is
#: UNMEASURED: thirty signals all outside a window is a structure, five is an anecdote.
N_MIN = 30
#: Bars of each frame a measurement reads, from the tail. Enough for a once-a-day family to fire
#: well over N_MIN times on H1 (~3 years) and on M5 (~70 days), bounded so one key costs seconds.
BAR_TAIL = 20_000
#: The session axis the producers mint. `all` is never dead and never remapped.
SESSION_NAMES = ("asia", "london", "ny", "tokyo_fix", "london_fix", "overlap")
_FALLBACK_SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None,
    "tokyo_fix": (2, 5), "london_fix": (17, 19), "overlap": (15, 18)}

#: Parameters that set an HOUR OF DAY. Matched by name against each family's signature, never
#: listed per family, so a family that gains one is re-anchorable the day it does.
_HOUR_PARAM = re.compile(r"(^hours$|_hour$|_hours$|^range_start$|^range_end$|^signal_at$)")
#: ...except durations that happen to be counted in hours.
_NOT_HOUR_OF_DAY = re.compile(r"^(lag|hold|ttl|max|min|lookback|wait|cooldown|horizon)_")

#: Desk-defined states the gauntlet applies (`cell_modifiers`): the conditioners a fixed-hour
#: family's re-homed cell is minted under when the plain re-homed cell already exists.
REHOME_REGIMES = ("high_vol", "low_vol", "month_end", "quarter_end")

_PINNED = {"lvc_asia_london": "M5"}
#: One slot of a producer's session axis: (session label, params to mint, remap note or None).
Slot = tuple[str, dict[str, Any], dict[str, Any] | None]

# ------------------------------------------------------------------------------ the two clocks
#
# THE BARS ARE BROKER STAMPS WEARING A UTC LABEL (Tier S 2026-09-30, PR #134). The venue clock is
# New York wall time + 7h (US DST rules), measured on eight years of EURUSD weekly opens; the ONE
# conversion is `libs/regime/session_clock.py` and it is imported here, never restated.
# `family_call.SESSIONS` compares those SERVER hours with windows written as if they were market
# hours. A variant is therefore judged on BOTH clocks:
#   market  the session in the market's own local clock, DST included (Tokyo / London / New York
#           08:00-16:00), `session_clock.in_session` -- the definition the shared filter moves to
#           in pass 2;
#   naive   the server-hour window the shared filter applies TODAY.
# A variant is LIVE when both hold signals, DEAD when the market session holds none, and
# SESSION_TZ_MISMATCH when only the clock kills it.
from libs.regime import session_clock  # noqa: E402

MARKET_SESSIONS: dict[str, tuple[str, int, int]] = dict(session_clock.MARKET_SESSIONS)


def clock_hash(settings: dict[str, Any] | None = None) -> str:
    """Hash of the conversion settings the market counts depend on: the venue offset rule
    (`SERVER_TZ` + `SERVER_SHIFT_H`) and the session table (`MARKET_SESSIONS`)."""
    import hashlib
    cfg = settings if settings is not None else clock_settings()
    raw = json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def clock_settings() -> dict[str, Any]:
    return {"server_tz": session_clock.SERVER_TZ, "server_shift_h": session_clock.SERVER_SHIFT_H,
            "market_sessions": {k: list(v) for k, v in session_clock.MARKET_SESSIONS.items()}}


#: The cache version: schema + the clock's conversion settings. A cache written under any other
#: conversion is read as empty (UNMEASURED) and re-measured, never trusted.
VERSION = f"{SCHEMA_VERSION}+clock:{clock_hash()}"
#: Years the every-day windows below are derived over: wide enough to hold every pairing of US
#: and UK daylight-time dates the rules produce (the mismatch weeks move with the calendar).
_DERIVE_YEARS = (2018, 2030)


def _always_server_hours() -> dict[str, frozenset[int]]:
    """Per session, the server hours that lie inside the market's own session on EVERY weekday
    of `_DERIVE_YEARS`, derived from `session_clock.in_session` -- never written by hand.

    London is the case that matters: server 10 is 08:00 London in most weeks but 07:00 in the
    weeks the US has changed clocks and the UK has not (2026-03-09..27, 2026-10-26..30), so the
    every-day London window is server 11-17, not 10-16."""
    import pandas as pd
    days = pd.bdate_range(f"{_DERIVE_YEARS[0]}-01-01", f"{_DERIVE_YEARS[1]}-12-31")
    out: dict[str, frozenset[int]] = {}
    for sess in MARKET_SESSIONS:
        keep = []
        for h in range(24):
            mask = session_clock.in_session(days + pd.Timedelta(hours=h), sess)
            if mask is not None and len(mask) and bool(mask.all()):
                keep.append(h)
        out[sess] = frozenset(keep)
    return out


#: Server hours inside each market session on every weekday under New York + 7h, DERIVED:
#: asia 2-8, london 11-17, ny 15-22 (inclusive). Where a stand-in is anchored, and the only hours a
#: prediction may count.
MARKET_SERVER_HOURS: dict[str, frozenset[int]] = _always_server_hours()
#: The earliest every-day server hour of each session: the anchor a stand-in is shifted to.
MARKET_OPEN_SERVER: dict[str, int] = {s: min(h) for s, h in MARKET_SERVER_HOURS.items() if h}
CLOCK_BASIS = (f"bars are broker stamps on {session_clock.SERVER_TZ} + "
               f"{session_clock.SERVER_SHIFT_H}h (libs/regime/session_clock.py); market sessions "
               "are Tokyo/London/New York 08:00-16:00 local, DST included")


def market_masks(times: Any) -> dict[str, Any]:
    """Per session, whether each broker-stamped time lies in that market's own session --
    `session_clock.in_session`, the desk's one conversion."""
    return {s: session_clock.in_session(times, s) for s in MARKET_SESSIONS}


# ------------------------------------------------------------------------------ plumbing


def _ensure_path() -> None:
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


def sessions() -> dict[str, tuple[int, int] | None]:
    """The desk's session windows in server hours -- `family_call.SESSIONS`, the one definition
    the gauntlet, the forward clock and the executor filter on."""
    try:
        _ensure_path()
        from mt5desk.family_call import SESSIONS
        return dict(SESSIONS)
    except Exception:
        return dict(_FALLBACK_SESSIONS)


def chart_of(family: str, params: dict[str, Any] | None) -> str:
    if family in _PINNED:
        return _PINNED[family]
    return str((params or {}).get("timeframe") or "H1").upper()


_FN_CACHE: dict[str, Any] = {}


def family_fn(family: str) -> Any:
    """The constructor the gauntlet builds `family` with (`families` then orthogonal)."""
    if family in _FN_CACHE:
        return _FN_CACHE[family]
    fn = None
    try:
        _ensure_path()
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
        if fn is None:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
    except Exception:
        fn = None
    _FN_CACHE[family] = fn
    return fn


def hour_params(family: str) -> dict[str, Any]:
    """{name: default} of every hour-of-day parameter `family` takes, by signature."""
    fn = family_fn(family)
    if fn is None:
        return {}
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}
    return {n: p.default for n, p in sig.parameters.items()
            if _HOUR_PARAM.search(n) and not _NOT_HOUR_OF_DAY.search(n)}


def _norm(v: Any) -> Any:
    if isinstance(v, tuple):
        return [_norm(x) for x in v]
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if v is inspect.Parameter.empty:
        return None
    return v


def _modifier_keys() -> frozenset[str]:
    try:
        _ensure_path()
        from mt5desk.cell_modifiers import MODIFIER_KEYS
        return frozenset(MODIFIER_KEYS)
    except Exception:
        return frozenset({"regime", "side_mode", "entry_timing", "execution_style"})


_CLASS_CACHE: dict[str, str] = {}
_LOG = logging.getLogger(__name__)
_WARNED: set[str] = set()


def universe_unreadable() -> str:
    """"" when the broker registry (`universe_policy.UNIVERSE`) reads with symbol rows; otherwise
    WHY it does not.

    THE AUDIT OF #145 (2026-09-30): the cache key carries the asset class, so an unreadable
    universe.json makes EVERY class read "", every key miss the cache, and every variant read
    UNMEASURED -- correct (UNMEASURED is never DEAD) but silent, indistinguishable from a cache
    that was simply never measured. This names the cause so the leg's artifact can carry it."""
    try:
        _ensure_path()
        import research.universe_policy as up  # type: ignore[import-not-found]
        path = Path(up.UNIVERSE)
        if up._registry():
            return ""
    except Exception as exc:
        return f"universe_policy unreachable ({type(exc).__name__}: {exc})"
    if not path.exists():
        return f"{path} is missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"{path} is unreadable ({type(exc).__name__})"
    return f"{path} holds no symbol rows"


def warn_universe_unreadable(reason: str) -> None:
    """Log the unreadable-registry cause once per reason per process."""
    if reason and reason not in _WARNED:
        _WARNED.add(reason)
        _LOG.warning("family_firing: broker registry unreadable -- %s; every asset-class key "
                     "misses the cache and every session variant reads %s until it is fixed",
                     reason, UNMEASURED)


def asset_class(symbol: str | None) -> str:
    """The symbol's asset class from the broker registry (`universe_policy.asset_class_of`);
    "" when unknown or unreachable. An unreadable registry is WARNED, and its "" is not cached,
    so the class returns the moment the file does."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return ""
    if sym not in _CLASS_CACHE:
        try:
            _ensure_path()
            from research.universe_policy import asset_class_of
            cls = str(asset_class_of(sym) or "")
        except Exception:
            cls = ""
        if not cls:
            reason = universe_unreadable()
            if reason:
                warn_universe_unreadable(reason)
                return ""
        _CLASS_CACHE[sym] = cls
    return _CLASS_CACHE[sym]


def key(family: str, params: dict[str, Any] | None, symbol: str | None = None) -> str:
    """The cache key: SYMBOL and its ASSET CLASS, family, chart, the EFFECTIVE hour params and any
    timing modifier.

    The symbol is in it because firing hours are a property of the instrument's own bars
    (EURUSD's are not CHFDKK's), so one symbol's measurement is never applied to another. A
    lookback or a threshold changes how often a family fires, not when, so every such variant of
    one symbol shares one measurement. No symbol, no measured key: the answer is UNMEASURED,
    which leaves the variant exactly as it was."""
    p = dict(params or {})
    sym = str(symbol or "").strip().upper()
    hp = {n: _norm(p.get(n, d)) for n, d in sorted(hour_params(family).items())}
    mods = {k: _norm(p[k]) for k in sorted(p) if k in ("entry_timing", "execution_style")}
    return json.dumps([family, chart_of(family, p), hp, mods, sym, asset_class(sym)],
                      sort_keys=True, separators=(",", ":"), default=str)


# ------------------------------------------------------------------------------ cache


def load_cache(path: Path | None = None) -> dict[str, Any]:
    target = path or CACHE
    try:
        doc = json.loads(Path(target).read_text(encoding="utf-8"))
    except Exception:
        doc = {}
    if not isinstance(doc, dict) or doc.get("version") != VERSION:
        doc = {}
    doc.setdefault("version", VERSION)
    doc.setdefault("keys", {})
    doc.setdefault("shift_verified", {})
    return doc


_MEMO: dict[str, tuple[float, dict[str, Any]]] = {}


def current_cache(path: Path | None = None) -> dict[str, Any]:
    """`load_cache`, re-read only when the file changed: producers ask per cell."""
    target = Path(path or CACHE)
    try:
        mtime = target.stat().st_mtime
    except OSError:
        mtime = -1.0
    hit = _MEMO.get(str(target))
    if hit is None or hit[0] != mtime:
        hit = (mtime, load_cache(target))
        _MEMO[str(target)] = hit
    return hit[1]


def save_cache(doc: dict[str, Any], path: Path | None = None) -> None:
    target = Path(path or CACHE)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = {**doc, "version": VERSION, "clock_hash": clock_hash(),
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "method": ("signals of fn(bars, side=1, **params) on the last "
                      f"{BAR_TAIL} bars of the key's own symbol; DEAD "
                      f"needs >= {N_MIN} signals and none in EITHER the market session "
                      f"or today's server-hour window; {LIVE_FILTER_ONLY} when only the market "
                      f"session is empty; {TZ_MISMATCH} when only the server-hour window is"),
           "clock": CLOCK_BASIS}
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, target)


# ------------------------------------------------------------------------------ measurement


#: A chart with no parquet of its own is BUILT from a finer one the symbol does hold (OHLC
#: resampled on the bar's own clock), never read off a coarser one. The build box holds M30 for
#: nothing; its M15 bars make honest M30 bars.
_FINER: dict[str, tuple[str, ...]] = {
    "M5": ("M1",), "M15": ("M5", "M1"), "M30": ("M15", "M5", "M1"),
    "H1": ("M30", "M15", "M5"), "H4": ("H1", "M30", "M15"), "D1": ("H1", "H4")}
_RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D"}
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum",
        "spread": "mean", "real_volume": "sum", "volume": "sum"}


def _source_chart(symbol: str, chart: str) -> str | None:
    if (UNIVERSE / f"{symbol}_{chart}.parquet").exists():
        return chart
    for fine in _FINER.get(chart, ()):
        if (UNIVERSE / f"{symbol}_{fine}.parquet").exists():
            return fine
    return None


def _bars(symbol: str, chart: str) -> Any:
    src = _source_chart(symbol, chart)
    if src is None:
        return None
    try:
        import pandas as pd
        from mt5desk import families
        raw = pd.read_parquet(UNIVERSE / f"{symbol}_{src}.parquet")
        if src != chart:
            raw = families._h1(raw)
            agg = {c: f for c, f in _AGG.items() if c in raw.columns}
            raw = raw.resample(_RULE[chart], label="left", closed="left").agg(agg)
            raw = raw.dropna(subset=["close"])
        frame = families._h1(raw)
    except Exception:
        return None
    if frame is None or len(frame) == 0:
        return None
    return frame.iloc[-BAR_TAIL:]


def _signal_hours(family: str, symbol: str, bars: Any,
                  params: dict[str, Any]) -> tuple[Counter[int], Counter[str], str]:
    """Hours of the family's signals on `bars`, called as `external_gauntlet.build_cell` calls
    it: inputs rebuilt by `family_inputs.resolve`, identity keys and the session stripped, the
    cell's modifiers split out and applied. The SESSION FILTER IS NOT APPLIED -- the point is to
    see every hour the family can reach."""
    _ensure_path()
    from mt5desk import cell_modifiers, family_inputs
    fn = family_fn(family)
    if fn is None:
        return Counter(), Counter(), "no constructor"
    extra, why = family_inputs.resolve(symbol, family, params, bars)
    if extra is None:
        return Counter(), Counter(), f"inputs: {why}"
    call = family_inputs.strip_identity_keys(family, params)
    call.pop("session", None)
    call.update(extra)
    call, mods = cell_modifiers.split(fn, call)
    refused = cell_modifiers.refusal(mods)
    if refused:
        # A refused modifier is a build failure for the cell; its hours are those of the
        # unmodified family, which is the superset -- measure that and say so.
        mods = {}
    try:
        sigs = fn(bars, side=1, **call)
    except TypeError:
        sigs = fn(bars, **call)
    sigs = list(sigs or [])
    if mods:
        sigs = cell_modifiers.apply(sigs, bars, mods)
    hrs: Counter[int] = Counter()
    times = []
    for g in sigs:
        t = getattr(g, "time", None)
        h = getattr(t, "hour", None)
        if h is not None:
            hrs[int(h)] += 1
            times.append(t)
    market: Counter[str] = Counter()
    if times:
        for s, mask in market_masks(times).items():
            market[s] += int(mask.sum()) if mask is not None else 0
    return hrs, market, "ok"


#: An UNMEASURED answer is retried after this long, or at once on another host: the build box
#: lacks bars and inputs the trading box holds, and its "cannot tell" must never pin the box's.
RETRY_UNMEASURED_S = 24 * 3600


def _host() -> str:
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return ""


def stale(rec: dict[str, Any] | None, now: float | None = None) -> bool:
    """Should this cached record be measured again? Never for a MEASURED one; for an UNMEASURED
    one when it is old or was taken on another machine."""
    if not rec:
        return True
    if rec.get("status") == "MEASURED":
        return False
    at = rec.get("measured_at")
    if not isinstance(at, (int, float)) or rec.get("host") != _host():
        return True
    return (now if now is not None else time.time()) - float(at) > RETRY_UNMEASURED_S


def measure(family: str, params: dict[str, Any] | None,
            symbol: str | None = None) -> dict[str, Any]:
    """Measure one key now, on `symbol`'s own bars only. Always returns a record; failure is
    UNMEASURED with its reason."""
    p = dict(params or {})
    chart = chart_of(family, p)
    started = time.monotonic()
    own = str(symbol or "").strip().upper()
    if not own:
        return {"status": UNMEASURED, "why": "no symbol: a firing set is measured per symbol",
                "chart": chart, "host": _host(), "measured_at": time.time()}
    if family_fn(family) is None:
        return {"status": UNMEASURED, "why": f"no constructor for {family!r}", "chart": chart,
                "host": _host(), "measured_at": time.time()}
    pooled: Counter[int] = Counter()
    market: Counter[str] = Counter()
    used: list[str] = []
    whys: list[str] = []
    for sym in ([own] if _source_chart(own, chart) else []):
        bars = _bars(sym, chart)
        if bars is None:
            continue
        try:
            hrs, mkt, why = _signal_hours(family, sym, bars, p)
        except Exception as exc:
            hrs, mkt, why = Counter(), Counter(), f"{type(exc).__name__}: {str(exc)[:120]}"
        if why != "ok":
            whys.append(f"{sym}: {why}")
            continue
        used.append(sym)
        pooled.update(hrs)
        market.update(mkt)
    n = int(sum(pooled.values()))
    rec: dict[str, Any] = {"chart": chart, "n": n, "symbols": used, "symbol": own,
                           "asset_class": asset_class(own), "per_symbol": True,
                           "host": _host(),
                           "measured_at": time.time(),
                           "hours": {str(h): int(c) for h, c in sorted(pooled.items())},
                           "market_sessions": {s: int(market.get(s, 0))
                                               for s in MARKET_SESSIONS},
                           "elapsed_s": round(time.monotonic() - started, 3)}
    if not used:
        rec.update(status=UNMEASURED, why=("; ".join(whys[:3]) or f"no {chart} bars cached"))
    elif n < N_MIN:
        rec.update(status=UNMEASURED,
                   why=f"{n} signals < {N_MIN}: too few to call any window empty")
    else:
        rec.update(status="MEASURED", why="ok")
    return rec


# ------------------------------------------------------------------------------ verdicts


def window_count(rec: dict[str, Any] | None, session: str) -> int | None:
    win = sessions().get(str(session or "all").lower())
    if not rec or rec.get("status") != "MEASURED":
        return None
    hours = {int(h): int(c) for h, c in (rec.get("hours") or {}).items()}
    if win is None:
        return sum(hours.values())
    lo, hi = win
    return sum(c for h, c in hours.items() if lo <= h < hi)


def market_count(rec: dict[str, Any] | None, session: str) -> int | None:
    if not rec or rec.get("status") != "MEASURED":
        return None
    got = (rec.get("market_sessions") or {}).get(session)
    return int(got) if got is not None else None


def verdict(rec: dict[str, Any] | None, session: str) -> str:
    """LIVE / LIVE_FILTER_ONLY / SESSION_TZ_MISMATCH / DEAD / UNMEASURED for one session.

    DEAD only when NEITHER clock holds a signal: never on today's server-hour filter and never in
    the market's own session. Filter-only is LIVE_FILTER_ONLY (it trades today); market-only is
    SESSION_TZ_MISMATCH. The evidence guard (`protected`) is applied by the callers that know the
    cell's symbol, on top of this."""
    s = str(session or "all").lower()
    if s == "all" or s not in sessions():
        return LIVE if rec and rec.get("status") == "MEASURED" else UNMEASURED
    naive = window_count(rec, s)
    market = market_count(rec, s) if s in MARKET_SESSIONS else naive
    if naive is None or market is None:
        return UNMEASURED
    if market > 0:
        return LIVE if naive > 0 else TZ_MISMATCH
    return LIVE_FILTER_ONLY if naive > 0 else DEAD


def lookup(family: str, params: dict[str, Any] | None,
           cache: dict[str, Any] | None = None, symbol: str | None = None) -> dict[str, Any] | None:
    doc = cache if cache is not None else current_cache()
    return (doc.get("keys") or {}).get(key(family, params, symbol))


def firing(family: str, params: dict[str, Any] | None, *, cache: dict[str, Any] | None = None,
           measure_missing: bool = False, symbol: str | None = None) -> dict[str, Any]:
    """The record for this key: cached, measured now when asked, else UNMEASURED."""
    doc = cache if cache is not None else current_cache()
    k = key(family, params, symbol)
    rec = (doc.get("keys") or {}).get(k)
    if measure_missing and stale(rec):
        rec = measure(family, params, symbol)
        doc.setdefault("keys", {})[k] = rec
    return rec or {"status": UNMEASURED, "why": "not measured yet", "chart": chart_of(family,
                                                                                      params)}


def classify(family: str, params: dict[str, Any] | None, session: str | None = None, *,
             cache: dict[str, Any] | None = None, measure_missing: bool = False,
             symbol: str | None = None) -> str:
    p = dict(params or {})
    s = str(session or p.get("session") or "all").lower()
    rec = firing(family, p, cache=cache, measure_missing=measure_missing, symbol=symbol)
    return verdict(rec, s)


# ------------------------------------------------------------------------------ evidence guard
#
# NEVER DEAD WHAT HAS TRADED OR PASSED (the audit of #145, 2026-09-30). The oracle judges hours;
# the desk also holds direct evidence that a cell does fire and earn: a ten-gate certificate in
# the canon, a PASSED row in the judge's verdict ledger, a NET_POSITIVE net verdict on a docket
# row. Any of those outranks a measured firing set, so such a cell is PROTECTED, never DEAD.
# A source that cannot be read is recorded as UNMEASURED in the guard, never as "no evidence
# exists" -- and the rule `DEAD needs both clocks empty` still stands on its own without it.

CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
NET_POSITIVE_PREFIX = "NET_POSITIVE"


def cell_key(symbol: Any, family: Any, params: dict[str, Any] | None,
             session: str | None = None) -> str:
    """(symbol, family, session, params without session): one name for a session variant, the
    canon's (`selector`) and the docket's (`params.session`) spellings alike."""
    raw = dict(params or {})
    s = str(session or raw.get("session") or "all").lower()
    p = {k: v for k, v in raw.items() if k != "session"}
    return json.dumps([str(symbol), str(family), s, p], sort_keys=True, default=str,
                      separators=(",", ":"))


def gauntlet_cell_id(symbol: Any, family: Any, params: dict[str, Any] | None) -> str | None:
    """The judge's own cell id (`frontier_identity.cell_id`), the key its verdict ledger uses."""
    try:
        _ensure_path()
        from research.frontier_identity import cell_id  # type: ignore[import-not-found]
        return str(cell_id({"sym": str(symbol), "family": str(family),
                            "params": dict(params or {})}))
    except Exception:
        return None


def load_guard(canon: Path | None = None, ledger: Path | None = None) -> dict[str, Any]:
    """The evidence a DEAD verdict may never contradict: {certified, passed, net_positive,
    sources}. `net_positive` is filled by whoever streams the docket (`note_net_verdict`)."""
    guard: dict[str, Any] = {"certified": set(), "certified_ids": set(), "passed": set(),
                             "net_positive": set(), "sources": {}}
    cpath = Path(canon or CANON)
    try:
        doc = json.loads(cpath.read_text(encoding="utf-8"))
        survivors = (doc.get("survivors") if isinstance(doc, dict) else None) or {}
        for name, row in survivors.items():
            if not isinstance(row, dict):
                continue
            raw_spec = row.get("shadow_spec")
            spec: dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
            sym = spec.get("symbol") or row.get("sym")
            fam = spec.get("family")
            sel = str(spec.get("selector") or "all").lower()
            if sym and fam:
                guard["certified"].add(cell_key(sym, fam, spec.get("params") or {},
                                                sel if sel in SESSION_NAMES else "all"))
            guard["certified_ids"].add(str(row.get("cell") or str(name).removeprefix("external.")))
        guard["sources"]["canon"] = {"path": cpath.name, "certificates": len(survivors)}
    except Exception as exc:
        guard["sources"]["canon"] = {"path": cpath.name,
                                     "status": f"{UNMEASURED}: {type(exc).__name__}"}
    lpath = Path(ledger or GATE_LEDGER)
    last: dict[str, bool] = {}
    try:
        with lpath.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("cell"):
                    last[str(r["cell"])] = bool(r.get("passed"))
        guard["passed"] = {c for c, ok in last.items() if ok}
        guard["sources"]["gate_verdict_ledger"] = {"path": lpath.name, "cells": len(last),
                                                   "passed": len(guard["passed"])}
    except OSError as exc:
        guard["sources"]["gate_verdict_ledger"] = {
            "path": lpath.name, "status": f"{UNMEASURED}: {type(exc).__name__} (box state)"}
    return guard


def note_net_verdict(guard: dict[str, Any], row: dict[str, Any]) -> None:
    """Record a docket row's own net verdict when it is net-positive."""
    if str(row.get("net_verdict") or "").upper().startswith(NET_POSITIVE_PREFIX):
        guard["net_positive"].add(cell_key(row.get("symbol"), row.get("family"),
                                           row.get("params") if isinstance(row.get("params"),
                                                                           dict) else {}))


def protected(guard: dict[str, Any] | None, symbol: Any, family: Any,
              params: dict[str, Any] | None, session: str | None = None) -> str | None:
    """Why this cell may never be DEAD, or None."""
    if not guard or not symbol:
        return None
    k = cell_key(symbol, family, params, session)
    if k in guard.get("certified", ()):
        return "ten-gate certificate (canon)"
    if k in guard.get("net_positive", ()):
        return "net-positive verdict"
    p = dict(params or {})
    s = str(session or p.get("session") or "all").lower()
    if s != "all":
        p["session"] = s
    cid = gauntlet_cell_id(symbol, family, p)
    if cid and cid in guard.get("passed", ()):
        return "passed gate verdict"
    return None


_GUARD_MEMO: dict[str, Any] = {}


def current_guard() -> dict[str, Any]:
    """`load_guard`, re-read only when the canon or the ledger changed: producers ask per cell."""
    stamp = []
    for pth in (CANON, GATE_LEDGER):
        try:
            stamp.append(pth.stat().st_mtime)
        except OSError:
            stamp.append(-1.0)
    if _GUARD_MEMO.get("stamp") != stamp:
        _GUARD_MEMO.update(stamp=stamp, guard=load_guard())
    got: dict[str, Any] = _GUARD_MEMO["guard"]
    return got


def guarded_verdict(rec: dict[str, Any] | None, session: str, *, symbol: Any = None,
                    family: Any = None, params: dict[str, Any] | None = None,
                    guard: dict[str, Any] | None = None) -> str:
    """`verdict`, with the evidence guard: a DEAD answer on a protected cell is PROTECTED."""
    v = verdict(rec, session)
    if v == DEAD and protected(guard, symbol, family, params, session):
        return PROTECTED
    return v


# ------------------------------------------------------------------------------ remapping


def _shift_value(v: Any, delta: int) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int):
        return v if v < 0 else (v + delta) % 24
    if isinstance(v, float) and v.is_integer():
        return v if v < 0 else float((int(v) + delta) % 24)
    if isinstance(v, (list, tuple)):
        return [_shift_value(x, delta) for x in v]
    return v


def shifted(family: str, params: dict[str, Any] | None, delta: int) -> dict[str, Any]:
    """`params` with EVERY hour-of-day parameter moved by `delta` hours (mod 24). A None (the
    family's own derivation) and a negative sentinel are left alone."""
    p = dict(params or {})
    for n, d in hour_params(family).items():
        v = p.get(n, _norm(d))
        nv = _shift_value(v, delta)
        if nv != v:
            p[n] = nv
    return p


def anchor_deltas(rec: dict[str, Any], session: str) -> list[int]:
    """Candidate shifts that move a measured firing set onto the market's own 08:00 open in
    server hours (`MARKET_OPEN_SERVER`, inside the server window too), best first: the earliest
    firing hour landed on the open, then each other firing hour."""
    if session not in MARKET_OPEN_SERVER or rec.get("status") != "MEASURED":
        return []
    lo = MARKET_OPEN_SERVER[session]
    hours = sorted(int(h) for h, c in (rec.get("hours") or {}).items() if int(c) > 0)
    out: list[int] = []
    for h in hours:
        d = (lo - h) % 24
        if d and d not in out:
            out.append(d)
    return out


def _predicted_live(rec: dict[str, Any], delta: int, session: str) -> bool:
    """Would the shifted firing set be LIVE on both clocks? Counted only on the server hours
    that lie in the market session in every week of the year, so a prediction never leans on
    a DST edge."""
    moved = {(int(h) + delta) % 24: int(c) for h, c in (rec.get("hours") or {}).items()}
    in_market = sum(c for h, c in moved.items() if h in MARKET_SERVER_HOURS.get(session, ()))
    naive = window_count({**rec, "hours": {str(h): c for h, c in moved.items()}}, session)
    return bool(in_market and naive)


def rehome_session(rec: dict[str, Any]) -> str | None:
    """The session LIVE on both clocks whose market window holds most of the family's signals;
    None when no named session is live on both (the caller re-homes to `all`)."""
    best, best_n = None, 0
    for s in SESSION_NAMES:
        if verdict(rec, s) != LIVE:
            continue
        c = market_count(rec, s) or 0
        if c > best_n:
            best, best_n = s, c
    return best


def _identity(params: dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))


def replacements(family: str, params: dict[str, Any] | None, session: str, *,
                 cache: dict[str, Any] | None = None, measure_missing: bool = False,
                 symbol: str | None = None) -> list[dict[str, Any]]:
    """Live cells that stand in for a DEAD `session` variant of (family, params), best first.

    Every candidate names its own session; each is judgeable by the oracle's own record. Empty
    when the variant is not DEAD or no stand-in can be shown to fire (the caller then leaves the
    variant exactly as it was)."""
    doc = cache if cache is not None else current_cache()
    base = {k: v for k, v in dict(params or {}).items() if k != "session"}
    rec = firing(family, base, cache=doc, measure_missing=measure_missing, symbol=symbol)
    if verdict(rec, session) != DEAD:
        return []
    out: list[dict[str, Any]] = []
    chart = chart_of(family, base)
    if hour_params(family):
        verified = bool((doc.get("shift_verified") or {}).get(f"{family}|{chart}"))
        for delta in anchor_deltas(rec, session):
            cand = shifted(family, base, delta)
            if cand == base:
                continue
            got = firing(family, cand, cache=doc, measure_missing=measure_missing, symbol=symbol)
            ok = verdict(got, session)
            if ok == UNMEASURED and verified and _predicted_live(rec, delta, session):
                ok = LIVE
            if ok == LIVE:
                if got.get("status") == "MEASURED":
                    doc.setdefault("shift_verified", {})[f"{family}|{chart}"] = True
                out.append({**cand, "session": session})
                break
    # RE-HOMED where the signals are. A family whose every signal falls outside all three named
    # windows (style_premia decides at 23) is re-homed to `all`, the only window that holds it.
    home = rehome_session(rec) or "all"
    at_home = dict(base) if home == "all" else {**base, "session": home}
    fn = family_fn(family)
    takes_regime = False
    with contextlib.suppress(TypeError, ValueError):
        takes_regime = "regime" in inspect.signature(fn).parameters
    out.append(at_home)
    if "regime" not in base and not takes_regime:
        out.extend({**at_home, "regime": r} for r in REHOME_REGIMES)
    return out


def session_cells(family: str, base: dict[str, Any] | None, session_axis: Iterable[str], *,
                  cache: dict[str, Any] | None = None, taken: set[str] | None = None,
                  symbol: str | None = None) -> list[Slot]:
    """The producers' door: (session label, params, remap note) for each slot of the axis.

    ONE CELL PER SLOT, ALWAYS -- the count a producer mints never falls. A LIVE or UNMEASURED
    slot is minted as it always was. A DEAD slot is minted as its first stand-in that is not
    already on the axis (or in `taken`); when every stand-in is taken the dead variant itself is
    minted, marked, exactly as before. Cache-only: a producer never measures at mint time."""
    doc = cache if cache is not None else current_cache()
    b = {k: v for k, v in dict(base or {}).items() if k != "session"}
    axis = list(session_axis)
    seen: set[str] = set(taken or ())
    planned: list[dict[str, Any]] = []
    for s in axis:
        p = dict(b)
        if s != "all":
            p["session"] = s
        planned.append(p)
    for p in planned:
        seen.add(_identity(p))
    out: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []
    for s, p in zip(axis, planned, strict=True):
        v = "all" if s == "all" else guarded_verdict(
            firing(family, b, cache=doc, symbol=symbol), s, symbol=symbol, family=family, params=b,
            guard=_safe_guard() if symbol else None)
        if v == TZ_MISMATCH:
            out.append((s, p, {"dead_session": s, "remapped": False, "cause": TZ_MISMATCH,
                               "why": "the market session holds signals; only the server-hour "
                                      "filter applied today misses them (pass 2 fixes it)"}))
            continue
        if v != DEAD:
            out.append((s, p, None))
            continue
        pick = None
        for cand in replacements(family, b, s, cache=doc, symbol=symbol):
            ident = _identity(cand)
            if ident not in seen:
                pick = cand
                seen.add(ident)
                break
        if pick is None:
            out.append((s, p, {"dead_session": s, "remapped": False, "cause": NEVER_FIRES,
                               "why": "every live stand-in is already minted"}))
            continue
        out.append((str(pick.get("session") or "all"), pick,
                    {"dead_session": s, "remapped": True, "cause": NEVER_FIRES,
                     "remap": ("reanchored" if any(pick.get(n) != b.get(n)
                                                   for n in hour_params(family))
                               else "rehomed"),
                     "census": "new cell, charged to the trial census when judged"}))
    return out


def _safe_guard() -> dict[str, Any] | None:
    try:
        return current_guard()
    except Exception:
        return None


def standin(family: str, params: dict[str, Any] | None, session: str | None = None, *,
            cache: dict[str, Any] | None = None,
            taken: set[str] | None = None,
            symbol: str | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The single-cell door, for a producer that mints ONE session variant (a proposer, a
    mutation): (params to mint, remap note). A LIVE or UNMEASURED variant comes back unchanged
    with no note; a DEAD one comes back as its first stand-in not in `taken`, or unchanged with a
    `remapped: False` note when every stand-in is taken. Always exactly one cell. Cache-only."""
    p = dict(params or {})
    s = str(session or p.get("session") or "all").lower()
    if s != "all":
        p["session"] = s
    if s == "all":
        return p, None
    try:
        slots = session_cells(family, p, [s], cache=cache, taken=taken, symbol=symbol)
    except Exception:
        return p, None
    _label, out, note = slots[0]
    return out, note


def live_session(family: str, params: dict[str, Any] | None, session: str | None,
                 symbol: str | None = None) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    """`standin` for a proposer row that carries its session twice (in params and beside them):
    (params, session label, note). Never raises -- an oracle failure is UNMEASURED, which leaves
    the row exactly as proposed."""
    s = str(session or (params or {}).get("session") or "all").lower()
    try:
        p, note = standin(family, params, s, symbol=symbol)
    except Exception:
        return dict(params or {}), s, None
    return p, str(p.get("session") or "all"), note


# ------------------------------------------------------------------------------ streaming


def iter_json_array(path: Path, chunk_chars: int = 1 << 20) -> Iterator[Any]:
    """Rows of a top-level JSON array, decoded incrementally (the docket is ~1.5m rows on the
    box). Same contract as `external_gauntlet.iter_json_array`, restated so this module never
    imports the sealed judge."""
    decoder = json.JSONDecoder()
    with Path(path).open("r", encoding="utf-8") as handle:
        buf, pos, eof = "", 0, False

        def refill() -> bool:
            nonlocal buf, pos, eof
            if pos:
                buf, pos = buf[pos:], 0
            more = handle.read(chunk_chars)
            if not more:
                eof = True
                return False
            buf += more
            return True

        refill()
        while pos < len(buf) and buf[pos].isspace():
            pos += 1
        if pos >= len(buf) or buf[pos] != "[":
            return
        pos += 1
        while True:
            while True:
                while pos < len(buf) and (buf[pos].isspace() or buf[pos] == ","):
                    pos += 1
                if pos < len(buf) or eof:
                    break
                refill()
            if pos >= len(buf) or buf[pos] == "]":
                return
            try:
                value, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if eof:
                    return
                refill()
                continue
            pos = end
            yield value


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--chart", default="H1")
    ap.add_argument("--symbol", default=None)
    a = ap.parse_args(argv)
    params = {} if a.chart == "H1" else {"timeframe": a.chart}
    rec = measure(a.family, params, a.symbol)
    rec["sessions"] = {s: verdict(rec, s) for s in SESSION_NAMES}
    print(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
