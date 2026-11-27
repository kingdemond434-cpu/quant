#!/usr/bin/env python3
"""THE EXOTIC CERTIFICATES' FIRING STATE, AS POINT-IN-TIME CONDITIONERS FOR TRADABLE CELLS.

THE ASK (idea 47, 2026-11-25). Exotic FX is banned from the book (zuck 2026-11-24 18:06Z), so
~12,730 of the box's 13,452 ten-gate certificates name a rule that can never trade. The rule
still FIRES on observable prices, and "USDZAR's certified gap-decay rule fired yesterday" is a
statement about the world (ZAR stress, EM risk, the gold/commodity bloc) that a tradable
instrument may respond to. `exotic_transplant` re-mints the exotic SPEC on tradables; this organ
does the other half -- it never trades the exotic rule anywhere, it reads its FIRING STATE and
offers it as a pre-registered conditioner on certified NON-EXOTIC parents in the same macro bloc.

ONE CONDITIONER MECHANISM, NO PARALLEL REGISTRY. Features are published as lake series
(`data/lake/series/exo_state__<SYM>.csv`, one column `f_<id>` per certificate, in the PIT
envelope, through `alt_proxies.write_series_csv`, THE lake-series write) and cells name them as
`params.conditioner = "alt:exo_state__<SYM>:f_<id>:<gt|lt>:0"` -- the exact form
`mt5desk.cell_modifiers` applies in the gauntlet and the forward clock (`_alt_filter`, through
`family_exogenous_conditioner.conditioner`, with its publication-day lag). Being lake series they
are also read by every lake reader the desk already has (`causal_lab`, `exogenous_conditioner`),
which charge their own trials.

POINT IN TIME, AND WHAT IS REFUSED.
  * A feature for broker day D is the sign of the summed sides of the certified rule's signals on
    D's bars (+1 net long fired, -1 net short fired, 0 quiet). A signal at bar t is decided at
    t's close, so D's value is known at D's last close; it is stamped `available_time` = the
    start of broker day D+1 (never earlier than any close in D), and only COMPLETED days are
    written (bars exist for a later day). The bar labels are broker time, 2-3h AHEAD of UTC, so
    the stamp is late, never early, and the conditioner holds it back a further publication day.
  * The certificate's params are used EXACTLY as certified; nothing is fitted here.
  * POST-SAMPLE ONLY. A certificate's sample cannot run past `gated_at`, the instant it was
    judged. Only broker days whose start lies strictly after gated_at + BROKER_OFFSET_MAX_H are
    published; earlier firings are in-sample for the rule's selection and are never written. A
    certificate with no readable gated_at has no knowable sample end and is REFUSED
    (`NO_SAMPLE_END`), not guessed.
  * LOOK-AHEAD PROBE. The rule is replayed on bars truncated at sampled signal bars (plus one
    information-free bar so families that need a "next bar" to exist can still emit). If any
    signal at or before the cut differs from the full replay, the rule used data after its own
    bar and the feature is REFUSED (`LOOKAHEAD`).

THE PRE-REGISTERED HYPOTHESIS SET AND ITS DECLARED TRIAL COUNT. Fixed by declared rules before
any target return is read:
  * group = (exotic symbol, family, chart); its feature is the certificate with the earliest
    gated_at (most post-sample history; ties by key) whose feature is valid -- chosen on the
    exotic's data alone, never on a target's outcome;
  * targets = the first TARGETS_PER_FEATURE eligible instruments of the exotic leg's declared
    macro bloc (BLOC_OF_CCY -> BLOC_TARGETS), never an exotic, never the source;
  * base = the first PARENTS_PER_TARGET certified non-exotic parents on that target (earliest
    gated_at), whose family really applies the conditioner (`cell_modifiers.split` moves it);
  * two cells per (feature, target, parent): fired net long (gt 0) and fired net short (lt 0),
    the two halves of one split, neither chosen after seeing which paid.
`declared_trials` is the size of that whole plan, ready or not, and it is published, priced by
`libs.research.trial_ledger.census` (n_raw and n_effective, with the plan size as each trial's
declared width) and written once per plan version as a set card in the pre-registration ledger.
Every minted cell is a docket row the sealed judge charges like any other; nothing is filtered on
an outcome, so no trial is hidden. A cell is minted only once its feature has MIN_POST_DAYS
completed post-sample days and MIN_SIDE_DAYS days on its own side (data readiness, never return
readiness); until then it is OWED and counted.

EXOTICS NEVER TRADE. Every target is checked with `universe_policy.is_exotic_symbol` at plan time
and again at the door; a plan holding one mints nothing and reads FAIL.

    python desks/mt5/research/exotic_state_features.py --once --budget-s 300
    python desks/mt5/research/exotic_state_features.py --once --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE = UNIVERSE_DIR / "universe.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
STATE = DESK / "data" / "exotic_state_features" / "state.json"
PREREG_LEDGER: Path | None = None          # None = the desk's own ledger (tests redirect it)
OUT = DESK / "reports" / "EXOTIC_STATE_FEATURES.json"

ORIGIN = "exotic_state_features"
FILE_PREFIX = "exo_state__"
UNMEASURED = "UNMEASURED"

#: The broker clock runs at most this many hours AHEAD of UTC (+2 winter, +3 summer).
BROKER_OFFSET_MAX_H = 3
#: Data readiness before a cell is minted: completed post-sample days, and days on its side.
MIN_POST_DAYS = 40
MIN_SIDE_DAYS = 5
#: The declared shape of the hypothesis set (see the module docstring).
TARGETS_PER_FEATURE = 4
PARENTS_PER_TARGET = 1
SIDES: tuple[str, ...] = ("gt", "lt")
#: New cells minted per pass; the rest are owed to later passes, never dropped.
BUDGET_CELLS = int(os.environ.get("EXOTIC_STATE_BUDGET_CELLS", "400"))
#: Look-ahead probes per certificate, and how often a probed rule is re-probed.
PROBES = 3
REPROBE_DAYS = 7
#: A feature older than this is recomputed (new bars, new completed days).
REFRESH_HOURS = 20
#: Bars kept before the sample end for the tail replay, once the tail is proven exact.
TAIL_WARMUP_BARS = 3000

MAJORS8: frozenset[str] = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD"})

#: The exotic leg's macro bloc, declared. A currency not listed maps to the USD bloc.
BLOC_OF_CCY: dict[str, str] = {
    "ZAR": "southern_commodity",
    "MXN": "latam", "BRL": "latam", "CLP": "latam", "COP": "latam", "PEN": "latam",
    "ARS": "latam",
    "TRY": "turkey",
    "PLN": "ceemea_europe", "HUF": "ceemea_europe", "CZK": "ceemea_europe",
    "RON": "ceemea_europe", "BGN": "ceemea_europe", "HRK": "ceemea_europe",
    "NOK": "nordic_oil",
    "SEK": "nordic_euro", "DKK": "nordic_euro", "ISK": "nordic_euro",
    "CNH": "asia_em", "CNY": "asia_em", "HKD": "asia_em", "SGD": "asia_em", "KRW": "asia_em",
    "TWD": "asia_em", "THB": "asia_em", "MYR": "asia_em", "IDR": "asia_em", "PHP": "asia_em",
    "INR": "asia_em", "VND": "asia_em",
    "AED": "gulf_energy", "SAR": "gulf_energy", "QAR": "gulf_energy", "KWD": "gulf_energy",
    "BHD": "gulf_energy", "OMR": "gulf_energy", "RUB": "gulf_energy", "KZT": "gulf_energy",
    "ILS": "risk_dm",
    "EGP": "frontier", "NGN": "frontier", "KES": "frontier", "GHS": "frontier",
    "MAD": "frontier", "TND": "frontier", "UAH": "frontier", "PKR": "frontier",
    "LKR": "frontier", "BDT": "frontier", "JOD": "frontier",
}
#: What each bloc's stress is declared to move, in priority order. Filtered at run time to
#: eligible (tradable, non-exotic) symbols; the first TARGETS_PER_FEATURE are the targets.
BLOC_TARGETS: dict[str, tuple[str, ...]] = {
    # gold and PGM producer, EM carry: the gold/commodity bloc and AUD risk
    "southern_commodity": ("XAUUSD", "AUDUSD", "AUDJPY", "XPTUSD", "NZDUSD", "XAGUSD"),
    # US trade, oil and copper exporters: CAD, oil, copper, US equities
    "latam": ("USDCAD", "XTIUSD", "XCUUSD", "AUDUSD", "US500", "CADJPY"),
    # euro-area exposure and domestic gold demand
    "turkey": ("EURUSD", "XAUUSD", "EURJPY", "GER40", "EURCHF"),
    "ceemea_europe": ("EURUSD", "EURCHF", "GER40", "EURJPY", "EURGBP"),
    "nordic_oil": ("XBRUSD", "XTIUSD", "USDCAD", "CADJPY", "EURUSD"),
    "nordic_euro": ("EURUSD", "EURGBP", "EURCHF", "GER40", "EU50"),
    # China/Asia growth: AUD/NZD, Asian indices, copper
    "asia_em": ("AUDUSD", "AUDJPY", "HK50", "CHINAH", "JPN225", "NZDUSD", "XCUUSD"),
    "gulf_energy": ("XBRUSD", "XTIUSD", "USDCAD", "XAUUSD", "CADJPY"),
    "risk_dm": ("US500", "NAS100", "USDJPY", "EURUSD"),
    "frontier": ("XAUUSD", "XBRUSD", "EURUSD", "USDJPY"),
    # the pricing leg of every exotic
    "usd": ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "XAUUSD"),
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ identities and mapping
def _bare(sym: str) -> str:
    return str(sym or "").split("@", 1)[0].strip()


def is_exotic(sym: str, klass: str | None = None) -> bool:
    """The desk's ONE exotic definition (`universe_policy.is_exotic_symbol`)."""
    from research import universe_policy as up
    return bool(up.is_exotic_symbol(_bare(sym), klass))


def feature_id(cert_key: str) -> str:
    return "f_" + hashlib.sha256(str(cert_key).encode()).hexdigest()[:12]


def series_stem(sym: str) -> str:
    return FILE_PREFIX + "".join(ch if ch.isalnum() else "_" for ch in _bare(sym).upper())


def conditioner_spec(sym: str, fid: str, op: str) -> str:
    """The `cell_modifiers` form: alt:<file>:<column>:<op>:<threshold>."""
    return f"alt:{series_stem(sym)}:{fid}:{op}:0"


def exotic_leg(sym: str) -> str:
    core = "".join(ch for ch in _bare(sym).upper() if "A" <= ch <= "Z")
    if len(core) < 6:
        return ""
    a, b = core[:3], core[3:6]
    for c in (a, b):
        if c not in MAJORS8 and c in BLOC_OF_CCY:
            return c
    for c in (a, b):
        if c not in MAJORS8:
            return c
    return ""


def bloc_of(sym: str) -> str:
    return BLOC_OF_CCY.get(exotic_leg(sym), "usd")


def bloc_targets(sym: str, elig: Mapping[str, Any]) -> list[str]:
    """The source's declared bloc targets that are eligible: never exotic, never the source."""
    src = _bare(sym)
    out = [t for t in BLOC_TARGETS[bloc_of(sym)]
           if t in elig and t != src and not is_exotic(t)]
    return out[:TARGETS_PER_FEATURE]


def eligible_targets(meta: Mapping[str, Any], universe_dir: Path | None = None
                     ) -> dict[str, dict[str, Any]]:
    """The tradable, non-exotic set `exotic_transplant` mints on -- one definition, reused."""
    from research.exotic_transplant import eligible_targets as _elig
    return _elig(meta, universe_dir)


def sample_end(row: Mapping[str, Any]) -> datetime | None:
    """The latest instant the certificate's sample can have reached: the instant it was judged."""
    raw = row.get("gated_at") if isinstance(row, Mapping) else None
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _spec_of(key: str, row: Mapping[str, Any]) -> dict[str, Any] | None:
    from research.exotic_transplant import parse_spec
    spec = parse_spec(key, row)
    if spec is None:
        return None
    sh = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    side = -1 if str((sh or {}).get("side") or "").strip().upper() in {"SHORT", "-1"} else 1
    return {**spec, "selector": str((sh or {}).get("selector") or ""), "side": side}


def certified_rows() -> tuple[dict[str, Any], str]:
    from research.exotic_transplant import certified_rows as _rows
    return _rows()


# ------------------------------------------------------------------ the replay
Sig = tuple[pd.Timestamp, int]
ReplayFn = Callable[[Mapping[str, Any], pd.DataFrame], "list[Sig] | str"]
BarsFn = Callable[[str, str], "pd.DataFrame | None"]


def load_bars(sym: str, chart: str) -> pd.DataFrame | None:
    path = UNIVERSE_DIR / f"{_bare(sym)}_{(chart or 'H1').upper()}.parquet"
    if not path.exists():
        return None
    try:
        bars = pd.read_parquet(path)
    except Exception:
        return None
    bars.index = pd.DatetimeIndex(pd.to_datetime(bars.index, utc=True, errors="coerce"))
    bars = bars[bars.index.notna()].sort_index()
    return bars[~bars.index.duplicated(keep="last")]


def replay(spec: Mapping[str, Any], bars: pd.DataFrame) -> list[Sig] | str:
    """The certified rule's signals over `bars`, called exactly as the forward clock calls it
    (`family_inputs.resolve` + `strip_identity_keys`, then `family_call.signals`); a string
    naming why it could not be replayed."""
    try:
        from mt5desk.executables import resolve_family
        from mt5desk.family_call import signals as family_signals
        from mt5desk.family_inputs import resolve, strip_identity_keys
        fam, sym = str(spec["family"]), str(spec["symbol"])
        fn = resolve_family(fam)
        if fn is None:
            return f"no code on this tree answers to family {fam!r}"
        params = dict(spec.get("params") or {})
        extra, why = resolve(sym, fam, params, bars)
        if extra is None:
            return f"inputs unresolvable: {why}"
        call = {**strip_identity_keys(fam, params), **extra}
        if spec.get("selector") and "session" not in call:
            call["session"] = str(spec["selector"])
        sigs = family_signals(fn, bars, side=int(spec.get("side") or 1), params=call)
    except Exception as exc:
        return f"replay raised {type(exc).__name__}: {str(exc)[:120]}"
    out: list[Sig] = []
    for s in sigs or []:
        try:
            t = pd.Timestamp(s.time)
            t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
            out.append((t, 1 if int(s.side) > 0 else -1))
        except (AttributeError, TypeError, ValueError):
            continue
    return sorted(set(out))


def _neutral_next(bars: pd.DataFrame) -> pd.DataFrame:
    """`bars` plus one information-free bar (flat at the last close, no volume) one step later."""
    idx = bars.index
    step = (idx[-1] - idx[-2]) if len(idx) >= 2 else pd.Timedelta(hours=1)
    last = bars.iloc[-1]
    row: dict[str, Any] = {}
    for c in bars.columns:
        if c in ("open", "high", "low", "close"):
            row[c] = float(last["close"])
        elif pd.api.types.is_numeric_dtype(bars[c].dtype):
            row[c] = 0
        else:
            row[c] = last[c]
    nxt = pd.DataFrame([row], index=pd.DatetimeIndex([idx[-1] + step]))
    return pd.concat([bars, nxt[list(bars.columns)]])


def probe_times(sigs: list[Sig], start: datetime) -> list[pd.Timestamp]:
    """Up to PROBES signal bars, evenly spaced, post-sample ones first (deterministic)."""
    post = [t for t, _s in sigs if t > pd.Timestamp(start)]
    pool = post or [t for t, _s in sigs]
    if not pool:
        return []
    if len(pool) <= PROBES:
        return list(pool)
    step = (len(pool) - 1) / (PROBES - 1)
    return [pool[round(i * step)] for i in range(PROBES)]


def lookahead_probe(spec: Mapping[str, Any], bars: pd.DataFrame, full: list[Sig],
                    cuts: Iterable[pd.Timestamp], replay_fn: ReplayFn = replay
                    ) -> tuple[bool, str]:
    """(True, '') when every signal at or before each cut is the same on bars ending at the cut
    as on the full history -- i.e. the rule at t used data <= t only."""
    for cut in cuts:
        pre = bars[bars.index <= cut]
        if len(pre) < 2:
            continue
        got = replay_fn(spec, _neutral_next(pre))
        if isinstance(got, str):
            return False, f"probe replay at {cut} failed: {got}"
        a = {x for x in full if x[0] <= cut}
        b = {x for x in got if x[0] <= cut}
        if a != b:
            diff = sorted(a ^ b)[:3]
            return False, (f"LOOKAHEAD: signals at or before {cut} change when later bars are "
                           f"removed ({len(a ^ b)} differ, e.g. {diff})")
    return True, ""


def daily_feature(sigs: list[Sig], index: pd.DatetimeIndex, start: datetime
                  ) -> dict[str, int]:
    """{broker day: sign of summed sides} for every COMPLETED day whose start lies after
    `start` + BROKER_OFFSET_MAX_H. Days with bars and no signal are 0."""
    if len(index) == 0:
        return {}
    days = sorted({d.isoformat() for d in index.date})
    last = days[-1]                          # still forming: never published
    floor = pd.Timestamp(start) + pd.Timedelta(hours=BROKER_OFFSET_MAX_H)
    net: dict[str, int] = defaultdict(int)
    for t, s in sigs:
        net[t.date().isoformat()] += int(s)
    out: dict[str, int] = {}
    for d in days:
        if d == last:
            continue
        if pd.Timestamp(d, tz="UTC") <= floor:
            continue
        v = net.get(d, 0)
        out[d] = (v > 0) - (v < 0)
    return out


# ------------------------------------------------------------------ the feature pass
def exotic_certificates(survivors: Mapping[str, Any]) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Every certified spec whose symbol is exotic, with its sample end (None = refused)."""
    out: list[dict[str, Any]] = []
    n: Counter[str] = Counter()
    for key in sorted(survivors):
        row = survivors[key]
        if not isinstance(row, dict):
            continue
        spec = _spec_of(key, row)
        if spec is None:
            n["not_external_spec"] += 1
            continue
        if not is_exotic(spec["symbol"]):
            continue
        n["exotic_certificates"] += 1
        end = sample_end(row)
        out.append({**spec, "key": key, "fid": feature_id(key),
                    "sample_end": _iso(end) if end else None})
    return out, n


def compute_one(spec: Mapping[str, Any], bars: pd.DataFrame | None, prior: Mapping[str, Any],
                now: datetime, replay_fn: ReplayFn = replay
                ) -> tuple[dict[str, Any], dict[str, int] | None]:
    """(state row, daily values or None). Refusals are named in the row's status."""
    row: dict[str, Any] = {"symbol": spec["symbol"], "family": spec["family"],
                           "chart": spec["chart"], "fid": spec["fid"],
                           "sample_end": spec.get("sample_end"), "computed_at": _iso(now)}
    if not spec.get("sample_end"):
        return {**row, "status": "NO_SAMPLE_END",
                "why": "no readable gated_at: the sample end is unknowable, so every firing is "
                       "treated as in-sample and the feature is refused"}, None
    start = datetime.fromisoformat(str(spec["sample_end"]))
    if bars is None or len(bars) < 3:
        return {**row, "status": UNMEASURED,
                "why": f"no {spec['symbol']}_{spec['chart']} bars on this host"}, None
    # THE TAIL REPLAY is used only once it was proven to give the full replay's post-sample
    # signals on this certificate; otherwise the full history is replayed.
    use_tail = bool(prior.get("tail_exact"))
    pos = int(bars.index.searchsorted(pd.Timestamp(start)))
    tail = bars.iloc[max(0, pos - TAIL_WARMUP_BARS):]
    full = replay_fn(spec, tail if use_tail else bars)
    if isinstance(full, str):
        return {**row, "status": "REPLAY_FAILED", "why": full}, None
    post_floor = pd.Timestamp(start)
    if not use_tail and len(tail) < len(bars):
        got = replay_fn(spec, tail)
        row["tail_exact"] = (not isinstance(got, str)
                             and [x for x in got if x[0] > post_floor]
                             == [x for x in full if x[0] > post_floor])
    else:
        row["tail_exact"] = use_tail or len(tail) == len(bars)
    probed = str(prior.get("probed_at") or "")
    due = (not probed or prior.get("lookahead") != "CLEAN"
           or datetime.fromisoformat(probed) < now - timedelta(days=REPROBE_DAYS))
    if due:
        ok, why = lookahead_probe(spec, tail if use_tail else bars, full,
                                  probe_times(full, start), replay_fn)
        row["probed_at"] = _iso(now)
        row["lookahead"] = "CLEAN" if ok else "LOOKAHEAD"
        if not ok:
            return {**row, "status": "LOOKAHEAD", "why": why}, None
    else:
        row["probed_at"], row["lookahead"] = probed, "CLEAN"
    vals = daily_feature(full, pd.DatetimeIndex(bars.index), start)
    row["post_days"] = len(vals)
    row["side_days"] = {"gt": sum(1 for v in vals.values() if v > 0),
                        "lt": sum(1 for v in vals.values() if v < 0)}
    row["n_signals_post"] = sum(1 for t, _s in full if t > post_floor)
    row["last_day"] = max(vals) if vals else None
    if not vals:
        return {**row, "status": "NO_POST_SAMPLE_DAYS",
                "why": "no completed broker day after the sample end yet; nothing is published "
                       "from inside the sample"}, {}
    return {**row, "status": "VALID", "why": ""}, vals


def write_symbol_series(sym: str, values: Mapping[str, Mapping[str, int] | None],
                        series_dir: Path) -> str:
    """Merge this pass's columns into `exo_state__<SYM>.csv` (None drops a column)."""
    from research.alt_proxies import write_series_csv
    stem = series_stem(sym)
    path = series_dir / f"{stem}.csv"
    cols: dict[str, dict[str, int]] = {}
    if path.exists():
        try:
            old = pd.read_csv(path)
            for c in old.columns:
                if c.startswith("f_"):
                    s = old.set_index("event_time")[c].dropna()
                    cols[c] = {str(k): int(v) for k, v in s.items()}
        except Exception:
            cols = {}
    for fid, vals in values.items():
        if vals is None:
            cols.pop(fid, None)
        else:
            cols[fid] = dict(vals)
    days = sorted({d for v in cols.values() for d in v})
    frame = pd.DataFrame({"event_time": days})
    # Known at the end of broker day D: stamped the start of D+1 on the bar clock (see module).
    frame["available_time"] = [
        (pd.Timestamp(d, tz="UTC") + pd.Timedelta(days=1)).isoformat() for d in days]
    frame["source_id"] = ORIGIN
    for fid in sorted(cols):
        frame[fid] = [cols[fid].get(d) for d in days]
    if not days:
        frame = pd.DataFrame(columns=["event_time", "available_time", "source_id"])
    return write_series_csv(series_dir, stem, frame)


def feature_pass(specs: list[dict[str, Any]], state: dict[str, Any], now: datetime,
                 deadline: float, *, bars_fn: BarsFn = load_bars, replay_fn: ReplayFn = replay,
                 series_dir: Path = SERIES_DIR, write: bool = True) -> dict[str, Any]:
    """Compute or refresh features (never-computed first, then stale), one symbol resident."""
    feats: dict[str, Any] = state.setdefault("features", {})
    fresh_after = now - timedelta(hours=REFRESH_HOURS)

    def due(s: Mapping[str, Any]) -> int:
        r = feats.get(s["key"])
        if not r:
            return 0
        try:
            return 1 if datetime.fromisoformat(str(r.get("computed_at"))) < fresh_after else 2
        except ValueError:
            return 0

    pending = sorted((s for s in specs if due(s) < 2),
                     key=lambda s: (due(s), s["symbol"], s["chart"], s["key"]))
    touched: dict[str, dict[str, Mapping[str, int] | None]] = defaultdict(dict)
    loaded: tuple[tuple[str, str], pd.DataFrame | None] | None = None   # one symbol resident
    done = 0
    budget_stopped = False
    for s in pending:
        if time.monotonic() > deadline:
            budget_stopped = True
            break
        k = (s["symbol"], s["chart"])
        bars: pd.DataFrame | None = None
        if s.get("sample_end"):
            if loaded is None or loaded[0] != k:
                loaded = (k, bars_fn(*k))
            bars = loaded[1]
        row, vals = compute_one(s, bars, feats.get(s["key"]) or {}, now, replay_fn)
        feats[s["key"]] = row
        touched[s["symbol"]][s["fid"]] = vals if row["status"] == "VALID" else None
        done += 1
    written: list[str] = []
    errors: list[str] = []
    if write:
        for sym, vals_by in sorted(touched.items()):
            try:
                written.append(write_symbol_series(sym, vals_by, series_dir))
            except (OSError, ValueError) as exc:
                errors.append(f"{sym}: {type(exc).__name__}: {str(exc)[:80]}")
    return {"computed_this_pass": done, "pending_before": len(pending),
            "budget_stopped": budget_stopped, "series_written": written, "errors": errors}


# ------------------------------------------------------------------ the hypothesis set
def conditioner_applies(family: str) -> bool:
    """True when the family's own signature leaves `conditioner` to `cell_modifiers` (a family
    taking **kwargs or naming it would swallow the condition and trade unconditioned)."""
    try:
        from mt5desk import cell_modifiers as cm
        from mt5desk.executables import resolve_family
        fn = resolve_family(family)
        if fn is None:
            return False
        _kw, mods = cm.split(fn, {"conditioner": "alt:x:y:gt:0"})
        return "conditioner" in mods
    except Exception:
        return False


def parents_by_target(survivors: Mapping[str, Any], elig: Mapping[str, Any],
                      applies: Callable[[str], bool] = conditioner_applies
                      ) -> dict[str, list[dict[str, Any]]]:
    """Certified NON-EXOTIC parents per eligible target, earliest gated_at first."""
    try:
        from research.family_policy import family_banned
    except ImportError:                                    # pragma: no cover
        def family_banned(family: object, path: Path | None = None) -> bool:
            return False
    rows: dict[str, list[tuple[str, str, dict[str, Any]]]] = defaultdict(list)
    ok_family: dict[str, bool] = {}
    for key in sorted(survivors):
        row = survivors[key]
        if not isinstance(row, dict):
            continue
        spec = _spec_of(key, row)
        if spec is None or spec["symbol"] not in elig or is_exotic(spec["symbol"]):
            continue
        fam = spec["family"]
        if family_banned(fam):
            continue
        if fam not in ok_family:
            ok_family[fam] = applies(fam)
        if not ok_family[fam]:
            continue
        end = sample_end(row)
        rows[spec["symbol"]].append((_iso(end) if end else "9999", key, spec))
    return {sym: [{**sp, "key": k} for _e, k, sp in sorted(v)] for sym, v in rows.items()}


def _groups(specs: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    g: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in specs:
        g[(s["symbol"], s["family"], s["chart"])].append(s)
    for v in g.values():
        v.sort(key=lambda s: (s.get("sample_end") or "9999", s["key"]))
    return g


def build_plan(specs: list[dict[str, Any]], feats: Mapping[str, Any],
               parents: Mapping[str, list[dict[str, Any]]], elig: Mapping[str, Any]
               ) -> tuple[list[dict[str, Any]], Counter[str]]:
    """The whole pre-registered set: every (group x target x parent x side) cell. A group whose
    feature is not valid yet still counts its cells (declared trials) and mints none."""
    plan: list[dict[str, Any]] = []
    n: Counter[str] = Counter()
    for (sym, fam, chart), members in sorted(_groups(specs).items()):
        n["groups"] += 1
        rep = next((m for m in members
                    if (feats.get(m["key"]) or {}).get("status") == "VALID"), None)
        targets = bloc_targets(sym, elig)
        if not targets:
            n["groups_without_target"] += 1
            continue
        for t in targets:
            pars = (parents.get(t) or [])[:PARENTS_PER_TARGET]
            if not pars:
                n["targets_without_parent"] += 1
                continue
            for par in pars:
                for op in SIDES:
                    fr = (feats.get(rep["key"]) or {}) if rep else {}
                    side_days = int((fr.get("side_days") or {}).get(op) or 0)
                    ready = bool(rep) and int(fr.get("post_days") or 0) >= MIN_POST_DAYS \
                        and side_days >= MIN_SIDE_DAYS
                    params = dict(par.get("params") or {})
                    if par.get("selector") and "session" not in params:
                        params["session"] = str(par["selector"])
                    group = f"{sym}|{fam}|{chart}"
                    slot = f"{group}|{t}|{par['key']}|{op}"
                    cell: dict[str, Any] = {
                        "slot": slot, "group": group, "bloc": bloc_of(sym), "symbol": t,
                        "family": par["family"], "timeframe": par.get("chart") or "H1",
                        "parent": par["key"], "op": op, "source_symbol": sym,
                        "source_family": fam, "ready": ready}
                    if rep:
                        params["conditioner"] = conditioner_spec(sym, rep["fid"], op)
                        cell["feature_certificate"] = rep["key"]
                        cell["params"] = params
                        cell["cell_id"] = hashlib.sha256(json.dumps(
                            [t, par["family"], params, cell["timeframe"]], sort_keys=True,
                            default=str).encode()).hexdigest()[:20]
                    plan.append(cell)
                    n["cells_ready" if ready else "cells_owed"] += 1
    return plan, n


def plan_sha(plan: list[dict[str, Any]]) -> str:
    return hashlib.sha256("\n".join(sorted(c["slot"] for c in plan)).encode()).hexdigest()[:16]


def charge_trials(plan: list[dict[str, Any]]) -> dict[str, Any]:
    """The declared set priced by the desk's effective-trial ledger; every slot is a trial."""
    declared = len(plan)
    if not plan:
        return {"declared_trials": 0, "n_raw": 0, "n_effective": 0.0,
                "basis": "no plan on this host"}
    try:
        from libs.research import trial_ledger as tl
        rows = [tl.Trial(c["slot"], str(c["family"]),
                         {"symbol": c["symbol"], "chart": str(c["timeframe"]),
                          "conditioner_source": c["group"], "side": c["op"],
                          "bloc": c["bloc"], "dataset": ORIGIN},
                         {}, declared_width=declared) for c in plan]
        cen = tl.census(rows)
    except Exception as exc:
        return {"declared_trials": declared, "n_raw": declared, "n_effective": None,
                "basis": f"UNMEASURED: trial_ledger census failed ({type(exc).__name__})"}
    return {"declared_trials": declared, "n_raw": int(cen.n_raw),
            "n_effective": round(float(cen.n_effective), 2),
            "basis": ("every (feature group x target x parent x side) slot of the declared plan "
                      "is one trial, ready or not, each declaring the plan size as its width; "
                      "minted cells are also docket rows the sealed judge charges")}


def preregister_set(plan: list[dict[str, Any]], sha: str, state: dict[str, Any]
                    ) -> dict[str, Any]:
    """One set card per plan version in the pre-registration ledger, before any verdict."""
    done = state.setdefault("prereg_sets", {})
    if sha in done:
        return {"plan_sha": sha, "prereg_hash": done[sha], "new": False}
    try:
        from libs.research import preregistration as pr
        card = {
            "hypothesis": (f"the firing state of certified exotic rules conditions certified "
                           f"non-exotic parents in the same macro bloc ({len(plan)} declared "
                           "trials)"),
            "mechanism": ("an exotic pair's certified rule firing marks stress or flow in its "
                          "bloc (ZAR->gold/AUD, MXN->CAD/oil, TRY->EUR/gold, ...), which the "
                          "bloc's tradable instruments may price after the exotic does"),
            "direction": "two halves per slot: fired net long (gt 0) and fired net short (lt 0)",
            "variables": sorted({c["group"] for c in plan}),
            "universe": sorted({c["symbol"] for c in plan}),
            "horizon": "the parent's own certified exit",
            "parameters_allowed": {"declared_trials": len(plan), "plan_sha": sha,
                                   "targets_per_feature": TARGETS_PER_FEATURE,
                                   "parents_per_target": PARENTS_PER_TARGET,
                                   "sides": list(SIDES), "bloc_targets": BLOC_TARGETS},
            "acceptance_criterion": ("the canonical ten-gate gauntlet on each conditioned "
                                     "cell, charged by this set's declared trial count"),
            "falsifier": ("a conditioned cell does no better than its certified parent on the "
                          "same window"),
            "transformations": ORIGIN}
        kw: dict[str, Any] = {"source": ORIGIN}
        if PREREG_LEDGER is not None:
            kw["path"] = PREREG_LEDGER
        h = pr.register(card, **kw)
    except Exception as exc:
        return {"plan_sha": sha, "prereg_hash": None,
                "why": f"UNMEASURED: {type(exc).__name__}: {str(exc)[:120]}"}
    done[sha] = h
    return {"plan_sha": sha, "prereg_hash": h, "new": True}


class ExoticTargetError(AssertionError):
    """An exotic reached the door as a TRADED symbol: never allowed."""


def mint_one(cell: Mapping[str, Any], conn: Any, declared: int, sha: str) -> bool:
    from libs.moat.registry import enqueue_candidate
    t = str(cell["symbol"])
    if is_exotic(t):
        raise ExoticTargetError(f"{t} is exotic and may never be a traded symbol")
    src, op = cell["source_symbol"], cell["op"]
    why = (f"{cell['family']} on {t} only while {src}'s certified {cell['source_family']} rule "
           f"fired net {'long' if op == 'gt' else 'short'} (post-sample firing state, "
           f"{cell['bloc']} bloc)")
    _cid, created = enqueue_candidate(
        family=str(cell["family"]), symbol=t, params=dict(cell["params"]), origin=ORIGIN,
        mechanism=why, chart=str(cell["timeframe"] or "H1"), conn=conn, generator=ORIGIN,
        department="information", transformation=ORIGIN,
        source_id=str(cell["feature_certificate"]),
        parent_ids=[str(cell["parent"]), str(cell["feature_certificate"])],
        lineage={"producer": ORIGIN, "parent": cell["parent"],
                 "feature_certificate": cell["feature_certificate"], "bloc": cell["bloc"],
                 "conditioner": cell["params"]["conditioner"], "declared_trials": declared,
                 "plan_sha": sha,
                 "evidence": "none: the exotic certificate is a feature source, never evidence"},
        causal_rationale=why,
        falsifier=(f"{cell['family']} on {t} conditioned on {src}'s firing state does no better "
                   "than its certified parent"))
    return bool(created)


# ------------------------------------------------------------------ the pass
def build(budget_s: float = 300.0, *, budget_cells: int = BUDGET_CELLS, dry_run: bool = False,
          survivors: Mapping[str, Any] | None = None, survivors_path: str = "",
          meta: Mapping[str, Any] | None = None, universe_dir: Path | None = None,
          state_path: Path | None = None, series_dir: Path | None = None,
          bars_fn: BarsFn = load_bars, replay_fn: ReplayFn = replay,
          applies: Callable[[str], bool] = conditioner_applies,
          conn: Any = None, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(1.0, budget_s) * 0.7        # leave the plan and the door their share
    now = now or _now()
    spath = state_path or STATE
    sdir = series_dir or SERIES_DIR
    if survivors is None:
        survivors, survivors_path = certified_rows()
    if meta is None:
        meta = _read(UNIVERSE, {}) or {}
    state: dict[str, Any] = _read(spath, {}) or {}
    elig = eligible_targets(meta, universe_dir)
    specs, census = exotic_certificates(survivors)
    fp = feature_pass(specs, state, now, deadline, bars_fn=bars_fn, replay_fn=replay_fn,
                      series_dir=sdir, write=not dry_run)
    feats = state.get("features") or {}
    live_keys = {s["key"] for s in specs}
    status_n = Counter(str((feats.get(k) or {}).get("status") or "NOT_YET_COMPUTED")
                       for k in live_keys)
    parents = parents_by_target(survivors, elig, applies)
    plan, plan_n = build_plan(specs, feats, parents, elig)
    exotic_traded = sorted({c["symbol"] for c in plan if is_exotic(c["symbol"])})
    sha = plan_sha(plan)
    trials = charge_trials(plan)
    prereg = preregister_set(plan, sha, state) if (plan and not dry_run) else {"plan_sha": sha}

    minted_ids: set[str] = set(state.get("minted") or [])
    ready = [c for c in plan if c["ready"] and c.get("cell_id") not in minted_ids]
    minted, errors = 0, list(fp["errors"])
    own_conn = None
    reg_why = ""
    if exotic_traded:
        reg_why = f"FAIL: exotic traded symbol(s) in the plan {exotic_traded}; nothing minted"
    elif ready and not dry_run:
        try:
            if conn is None:
                from libs.moat import registry as R
                own_conn = conn = R.connect()
        except Exception as exc:
            reg_why = f"UNMEASURED: registry unavailable ({type(exc).__name__})"
        try:
            for c in ready:
                if minted >= budget_cells or reg_why:
                    break
                try:
                    mint_one(c, conn, len(plan), sha)
                    minted += 1
                    minted_ids.add(str(c["cell_id"]))
                except ExoticTargetError:
                    raise
                except Exception as exc:
                    errors.append(f"{c['slot'][:60]}: {type(exc).__name__}: {str(exc)[:60]}")
                    if len(errors) > 20:
                        break
        finally:
            if own_conn is not None:
                own_conn.close()
    state["minted"] = sorted(minted_ids)
    state["at"] = _iso(now)
    if not dry_run:
        _write(spath, state)
    n_valid = status_n.get("VALID", 0)
    status = ("FAIL" if exotic_traded else
              UNMEASURED if not survivors or reg_why.startswith(UNMEASURED) else "OK")
    return {
        "at": _iso(now), "status": status, "dry_run": bool(dry_run),
        "certified_source": survivors_path, "n_certificates": len(survivors),
        "exotic_certificates": census.get("exotic_certificates", 0),
        "features_valid": n_valid,
        "feature_status": dict(sorted(status_n.items())),
        "feature_pass": fp,
        "n_eligible_targets": len(elig),
        "plan": {"sha": sha, "declared_trials": len(plan), **dict(plan_n),
                 "targets_per_feature": TARGETS_PER_FEATURE,
                 "parents_per_target": PARENTS_PER_TARGET, "sides": list(SIDES),
                 "min_post_days": MIN_POST_DAYS, "min_side_days": MIN_SIDE_DAYS},
        "trial_charge": trials, "preregistration": prereg,
        "cells_minted_this_pass" if not dry_run else "cells_would_mint": (
            minted if not dry_run else min(len(ready), budget_cells)),
        "cells_minted_total": len(minted_ids),
        "cells_ready_unminted": len(ready) - (minted if not dry_run else 0),
        "exotic_traded_symbols": exotic_traded,
        "bloc_of_ccy": BLOC_OF_CCY, "bloc_targets": {k: list(v) for k, v in BLOC_TARGETS.items()},
        "unmeasured": [w for w in (reg_why,) if w]
        + ([] if survivors else ["UNMEASURED: no certified set on this host"]),
        "errors": errors[:10],
        "boundary": ("the exotic rule is never traded or re-minted here: its post-sample firing "
                     "state is a lake series and a conditioner on certified non-exotic parents. "
                     "No gate, DSR/FDR input or certificate is read for scoring or written."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--budget-cells", type=int, default=BUDGET_CELLS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, budget_cells=a.budget_cells, dry_run=a.dry_run)
    try:
        _write(a.out, doc)
    except OSError as exc:
        print(f"exotic state features: could not write {a.out}: {exc}")
        return 1
    p = doc["plan"]
    print(f"exotic state features: {doc['exotic_certificates']} exotic certificate(s) of "
          f"{doc['n_certificates']} from {doc['certified_source'] or 'NOWHERE'}; "
          f"{doc['features_valid']} valid feature(s) {doc['feature_status']}")
    print(f"  plan {p['sha']}: {p['declared_trials']} declared trial(s), ready "
          f"{p.get('cells_ready', 0)}, owed {p.get('cells_owed', 0)}; minted "
          f"{doc.get('cells_minted_this_pass', doc.get('cells_would_mint', 0))} "
          f"(total {doc['cells_minted_total']}); status {doc['status']}")
    for w in doc["unmeasured"]:
        print(f"  {w}")
    return 0 if doc["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
