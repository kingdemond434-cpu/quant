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
every verdict is taken on both: DEAD means the market's own session (Tokyo / London / New York
08:00-16:00 local, DST included) never holds a signal; SESSION_TZ_MISMATCH means it does and only
today's server-hour window misses them -- counted apart and never remapped, because the shared
filter's fix (desk pass 2) makes that variant live as it stands.

WHAT IT ANSWERS. For (family, chart, the params that move the hour) it returns the hours the
family's signals land on, MEASURED once on cached bars through the same call the gauntlet makes
(`fn(bars, side=1, **params)`, identity keys stripped, the cell's modifiers applied) and cached
with a VERSION. From that, per session: LIVE (the window holds signals), DEAD (it holds none, on a
pooled sample of at least `N_MIN` signals) or UNMEASURED. UNMEASURED IS NEVER DEAD: a family with
too few signals, inputs that cannot be rebuilt here, or no bars for the chart leaves its variant
exactly as it was. Nothing is ever dropped.

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
#: (read as UNMEASURED), never trusted.
VERSION = 3
UNMEASURED = "UNMEASURED"
LIVE = "LIVE"
DEAD = "DEAD"
#: Dead ONLY because of the clock: the market's own session holds signals, the server-hour
#: window the shared filter applies today (`family_call.SESSIONS`) holds none. Not remapped --
#: the fix to the shared filter (desk pass 2) makes it live -- and counted apart.
TZ_MISMATCH = "SESSION_TZ_MISMATCH"
#: The family's signals never land in the market's session at all: the cause a remap answers.
NEVER_FIRES = "NEVER_FIRES_IN_SESSION"

#: Pooled signals needed before an empty window is called DEAD. Below it the answer is
#: UNMEASURED: thirty signals all outside a window is a structure, five is an anecdote.
N_MIN = 30
#: Bars of each frame a measurement reads, from the tail. Enough for a once-a-day family to fire
#: well over N_MIN times on H1 (~3 years) and on M5 (~70 days), bounded so one key costs seconds.
BAR_TAIL = 20_000
#: Symbols pooled per key, the cell's own first. Stops early once the sample is thick.
MAX_SYMBOLS = 3
ENOUGH = 200
REFERENCE_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "EURGBP", "GBPJPY", "GBPAUD",
                     "AUDCAD", "NZDCAD", "AUDNZD", "USDCAD", "AUDUSD")

#: The session axis the producers mint. `all` is never dead and never remapped.
SESSION_NAMES = ("asia", "london", "ny")
_FALLBACK_SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None}

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
#: Server hours inside each market session in EVERY week of the year under New York + 7h:
#: Tokyo 08-16 is server 01-09 (US winter) or 02-10 (US summer); London 08-16 is server 10-18,
#: or 09-17 in the weeks US and UK DST disagree; New York 08-16 is always server 15-23. These
#: are where a stand-in is anchored and the only hours a prediction may count.
MARKET_SERVER_HOURS: dict[str, frozenset[int]] = {
    "asia": frozenset(range(2, 9)), "london": frozenset(range(10, 17)),
    "ny": frozenset(range(15, 23))}
#: The market's 08:00 open in server hours (every week): the anchor a stand-in is shifted to.
MARKET_OPEN_SERVER: dict[str, int] = {"asia": 2, "london": 10, "ny": 15}
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


def key(family: str, params: dict[str, Any] | None) -> str:
    """The cache key: family, chart, the EFFECTIVE hour params and any timing modifier.

    Only what can move the hour is in it: a lookback or a threshold changes how often a family
    fires, not when, so every such variant shares one measurement."""
    p = dict(params or {})
    hp = {n: _norm(p.get(n, d)) for n, d in sorted(hour_params(family).items())}
    mods = {k: _norm(p[k]) for k in sorted(p) if k in ("entry_timing", "execution_style")}
    return json.dumps([family, chart_of(family, p), hp, mods], sort_keys=True,
                      separators=(",", ":"), default=str)


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
    doc = {**doc, "version": VERSION,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "method": ("signals of fn(bars, side=1, **params) on the last "
                      f"{BAR_TAIL} bars of up to {MAX_SYMBOLS} cached symbols per key; DEAD "
                      f"needs >= {N_MIN} pooled signals and none in the MARKET session; "
                      f"{TZ_MISMATCH} when only the server-hour window is empty"),
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


def _symbols_for(chart: str, first: str | None) -> list[str]:
    out: list[str] = []
    for s in ([first] if first else []) + list(REFERENCE_SYMBOLS):
        if s and s not in out and _source_chart(s, chart):
            out.append(s)
    if len(out) < MAX_SYMBOLS:
        for c in (chart, *_FINER.get(chart, ())):
            for pq in sorted(UNIVERSE.glob(f"*_{c}.parquet")):
                s = pq.name[: -len(f"_{c}.parquet")]
                if s not in out:
                    out.append(s)
                if len(out) >= MAX_SYMBOLS * 3:
                    return out
    return out


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
    """Measure one key now. Always returns a record; failure is UNMEASURED with its reason."""
    p = dict(params or {})
    chart = chart_of(family, p)
    started = time.monotonic()
    if family_fn(family) is None:
        return {"status": UNMEASURED, "why": f"no constructor for {family!r}", "chart": chart,
                "host": _host(), "measured_at": time.time()}
    pooled: Counter[int] = Counter()
    market: Counter[str] = Counter()
    used: list[str] = []
    whys: list[str] = []
    for sym in _symbols_for(chart, symbol):
        if len(used) >= MAX_SYMBOLS or sum(pooled.values()) >= ENOUGH:
            break
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
    rec: dict[str, Any] = {"chart": chart, "n": n, "symbols": used, "host": _host(),
                           "measured_at": time.time(),
                           "hours": {str(h): int(c) for h, c in sorted(pooled.items())},
                           "market_sessions": {s: int(market.get(s, 0))
                                               for s in MARKET_SESSIONS},
                           "elapsed_s": round(time.monotonic() - started, 3)}
    if not used:
        rec.update(status=UNMEASURED, why=("; ".join(whys[:3]) or f"no {chart} bars cached"))
    elif n < N_MIN:
        rec.update(status=UNMEASURED,
                   why=f"{n} pooled signals < {N_MIN}: too few to call any window empty")
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
    """LIVE / DEAD / SESSION_TZ_MISMATCH / UNMEASURED for one session of a measured record.

    DEAD is judged on the MARKET clock (the session in its own local time); a variant whose
    market session holds signals but whose server-hour window -- the one the shared filter applies
    today -- holds none is SESSION_TZ_MISMATCH, never DEAD."""
    s = str(session or "all").lower()
    if s == "all" or s not in sessions():
        return LIVE if rec and rec.get("status") == "MEASURED" else UNMEASURED
    naive = window_count(rec, s)
    market = market_count(rec, s) if s in MARKET_SESSIONS else naive
    if naive is None or market is None:
        return UNMEASURED
    if market == 0:
        return DEAD
    return LIVE if naive > 0 else TZ_MISMATCH


def lookup(family: str, params: dict[str, Any] | None,
           cache: dict[str, Any] | None = None) -> dict[str, Any] | None:
    doc = cache if cache is not None else current_cache()
    return (doc.get("keys") or {}).get(key(family, params))


def firing(family: str, params: dict[str, Any] | None, *, cache: dict[str, Any] | None = None,
           measure_missing: bool = False, symbol: str | None = None) -> dict[str, Any]:
    """The record for this key: cached, measured now when asked, else UNMEASURED."""
    doc = cache if cache is not None else current_cache()
    k = key(family, params)
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
        v = "all" if s == "all" else verdict(firing(family, b, cache=doc), s)
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


def standin(family: str, params: dict[str, Any] | None, session: str | None = None, *,
            cache: dict[str, Any] | None = None,
            taken: set[str] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
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
        slots = session_cells(family, p, [s], cache=cache, taken=taken)
    except Exception:
        return p, None
    _label, out, note = slots[0]
    return out, note


def live_session(family: str, params: dict[str, Any] | None,
                 session: str | None) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    """`standin` for a proposer row that carries its session twice (in params and beside them):
    (params, session label, note). Never raises -- an oracle failure is UNMEASURED, which leaves
    the row exactly as proposed."""
    s = str(session or (params or {}).get("session") or "all").lower()
    try:
        p, note = standin(family, params, s)
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
