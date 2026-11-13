#!/usr/bin/env python3
"""THE CONVERSION HANDOFF CONSUMER -- every parked cell the judge hands over gets a next action.

    python desks/mt5/research/conversion_handoff_consumer.py --once --budget-s 420
    python desks/mt5/research/conversion_handoff_consumer.py --once --dry-run

THE DEFECT (audit 2026-11-13). `judge_coverage.write_conversion_handoff` rewrote
`data/hypotheses/conversion_handoff.json` every pass -- 734,406 rows on the box's 01:02 UTC pass
(untestable_as_specified 567,421, short_history 79,735, build_fail 79,373, input_missing 7,649,
needs_data 228) -- and NO PROGRAM ACTED ON IT. `judging_burndown` read only its `n`. Each of those
is a weak, possibly net-of-cost edge the desk minted, paid a trial for, and then never tested:
lost breadth. A queue with a writer and no reader is a parking lot.

WHAT ONE PASS DOES. The handoff is STREAMED (it is hundreds of MB on the box); every row is
counted IN by its reason and leaves the pass with exactly ONE outcome -- re-emitted, fixed,
deferred (with why) or abandoned (with why) -- so the artifact's books balance per reason and
nothing stays parked silently.

  BUILD LANE (build_failed, series_exception, ...). Every failure is reduced to a SIGNATURE (the
    family's exception with numbers/symbols stripped, else the census's build-failure kind) and
    the signatures are published ranked by count. A signature with a REPAIR in `REPAIRS` is
    FIXED: the parked cell's params are read from the docket, repaired, and the repaired rule is
    re-emitted as a NEW cell tagged with its parent. Repairs found on this tree (reproduced
    through `external_gauntlet.build_cell`):
      * coevolution grammar names (`w`, `h`, `fast`/`slow`, `w1`/`w2`) no family accepts
        -> translated by `grammar_param_names` (and the producer now donates family names);
      * `lower_turnover`, a label no family accepts -> dropped (the change IS the H4 chart; the
        producer `net_edge_spine` no longer writes it);
      * `side: "SHORT"/"LONG"` strings into a family that compares `side > 0` -> -1 / +1.
    Narrative-only params (`mechanism_genome`, `crossed_slot`) are ABANDONED by name: stripping
    them would build the family at its defaults, which is the parent cell under the child's name.
    Every other signature is DEFERRED with its owner; the judge's own seven-day retry re-asks it.

  FIRE LANE (never_fires, no_signals, signals_no_trades, no_trades, too_rare). A cursor walks the
    population in a fixed hash order, so every parked cell is reached once per cycle whatever the
    budget. For each parent, on the instrument's OWN full bar history, the family is called
    exactly as the judge calls it (inputs resolved, identity keys stripped, modifiers applied,
    session filtered) and its distinct firing days are counted against the need
    (`ceil(60 / (1 - lockbox fraction))`, the CPCV floor after the carve). Diagnosis, in order:
      fires_now          -> the parent itself is RE-QUEUED to the judge (`conversion_requeue.json`);
      session_mismatch   -> the session excludes the hours it fires: child on the session that
                            fires most (or `all`);
      timeframe_mismatch -> an intraday cell that fires on its H1 chart: child on H1;
      threshold_unreachable -> a BOUNDED, DETERMINISTIC ladder (x0.75, x1.5, x0.5, x2.0 on up to
                            four non-exit numeric parameters, the parent's own first, then the
                            family's signature defaults): children are the least-modified
                            variants that reach the need, at most three;
      no_bounded_variant_fires -> ABANDONED with that reason (the bounded search is exhausted).
    A family that cannot be probed here (an input absent on this host) is DEFERRED with the probe's
    own reason, never abandoned.

  DEPTH LANE (short_history_after_cut, lockbox_consumed_history, observations_under_60_days).
    Each chart's held history is measured in TRADING DAYS, and a per-chart snapshot series is
    kept, so a cell's baseline is the depth at the time it was parked. The cell is RE-QUEUED when
    the depth has grown by the factor its own fired days need (60 / days, bounded 1.25..3, the
    judge's rule restated in days, not bytes). Until then it sits in
    `data/hypotheses/data_depth_backlog.json` with its chart, which the hourly bar repair reads
    (`hourly_cycle.bars_wanted_symbols` asks `fetch_universe` for those symbols). An intraday cell
    whose H1 chart already holds the history is also offered a COARSER-CHART child through the
    fire lane's probe.

TRIALS ARE NEVER HIDDEN. Every child goes through `proposer_common.donate` (the registry and the
compiler's intake) with `tests_run` = the children emitted, carries `parent_cell` and
`trial_family`, and becomes a docket row the sealed judge charges like any other. The fireability
probes read signal TIMES only, never a return, so they select on nothing the deflated Sharpe
prices; they are counted and published (`fire_probes`) all the same.

NO GATE IS TOUCHED. Nothing here judges, vetoes, caps or sizes; the sealed judge rules on every
re-emitted cell exactly as on any other. Memory: every bound is DERIVED from `psutil` free memory
on the machine running it, and the handoff and the docket are streamed, never loaded whole.

Artifacts: `reports/CONVERSION_HANDOFF_CONSUMER.json` (per-reason in/out books, signatures,
diagnoses, throughput, cycle ETA), `data/hypotheses/conversion_requeue.json` (read by
`judge_coverage.update_unrunnable_bank`), `data/hypotheses/data_depth_backlog.json` (read by
`hourly_cycle.bars_wanted_symbols`) and `data/conversion_handoff_consumer_state.json` (cursor,
depth snapshots, repaired parents).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import heapq
import inspect
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = BASE / "data" / "hypotheses"
HANDOFF = HYP / "conversion_handoff.json"
DOCKET = HYP / "external_survivors.json"
REQUEUE = HYP / "conversion_requeue.json"
DEPTH_BACKLOG = HYP / "data_depth_backlog.json"
STATE = BASE / "data" / "conversion_handoff_consumer_state.json"
OUT = BASE / "reports" / "CONVERSION_HANDOFF_CONSUMER.json"
UNIVERSE = BASE / "data" / "universe"
SEAT = "conversion_handoff_consumer"
SCHEMA = "conversion-handoff-consumer/1"
UNMEASURED = "UNMEASURED"

BUILD_REASONS = frozenset({"build_failed", "series_exception", "no_series", "ERROR", "FAIL_3X",
                           "NOT_RUN_BUILD_FAILED"})
FIRE_REASONS = frozenset({"never_fires", "no_signals", "signals_no_trades", "no_trades",
                          "too_rare"})
DEPTH_REASONS = frozenset({"short_history_after_cut", "lockbox_consumed_history",
                           "observations_under_60_days"})
#: Classes another organ owns end-to-end; the consumer books them DEFERRED with that owner, so
#: the handoff's every row is accounted for here.
OWNED_ELSEWHERE: dict[str, str] = {
    "input_missing": "judge_coverage build_input_probe: re-admitted the pass the named input is "
                     "present; its bars join bars_wanted -> fetch_universe",
    "needs_data": "fire_inputs probe + needs_data_outstanding: re-admitted when the input "
                  "appears",
    "no_bars": "bars_wanted -> hourly_cycle.refresh_tail -> fetch_universe",
    "modifier_refused": "cell_modifiers.refusal names the missing desk definition",
    "untradeable_symbol": "universe_policy / the broker's trade mode",
}

#: CPCV's floor and the campaign lockbox fraction (`gate_policy.LOCKBOX_FRAC`): a cell needs this
#: many distinct firing days over its whole history to keep 60 after the carve.
CPCV_MIN_DAYS = 60
#: Exit-only parameters: they change how a trade ends, never whether a signal fires.
EXIT_KEYS = frozenset({"rr", "ttl_bars", "stop_atr", "tp_atr", "sl_atr", "hold_bars", "max_hold",
                       "exit_bars", "trail_atr", "side"})
LADDER = (0.75, 1.5, 0.5, 2.0)
LADDER_PARAMS = 4
MAX_CHILDREN = 3
INTRADAY = ("M1", "M5", "M15", "M30")
#: Bars `fetch_universe` requests per intraday chart (its INTRADAY_TIMEFRAMES; that module imports
#: MetaTrader5 and cannot be imported here). A file below it may be extendable by a deeper pull.
NOMINAL_BARS = {"M30": 40_000, "M15": 60_000, "M5": 120_000, "M1": 200_000}
READMIT_GROWTH, READMIT_GROWTH_CAP = 1.25, 3.0
#: Memory per probing worker (one chart's full bars, its H1 sibling and the family's frames).
PER_WORKER_BYTES = 700 * 2**20
WORKER_MEMORY_SHARE = 0.25
#: Bytes held per selected parent while its params ride to a worker.
PER_PARENT_BYTES = 8 * 1024
PARENT_MEMORY_SHARE = 0.02
PARENTS_FLOOR = 50
#: Seconds one probe is assumed to cost before a pass has measured it.
PROBE_S_PRIOR = 0.25
DEPTH_SNAPSHOTS = 48


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
        for attempt in range(20):           # Windows: a reader holding the file refuses replace
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ------------------------------------------------------------------------------ memory bounds
def free_bytes() -> int | None:
    """Available physical memory on THIS machine, measured; None when unreadable."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return int(psutil.virtual_memory().available)
    except Exception:
        return None


def workers_for(avail: int | None, cpus: int | None = None) -> int:
    """Probing processes: a quarter of free memory at PER_WORKER_BYTES each, at most cpus - 1."""
    cpus = cpus or os.cpu_count() or 1
    if avail is None:
        return 1
    return max(1, min(cpus - 1, int(avail * WORKER_MEMORY_SHARE // PER_WORKER_BYTES)))


def parents_cap(avail: int | None) -> int:
    """Parents a pass may hold in memory, derived from free memory (floored, never hard-coded)."""
    if avail is None:
        return PARENTS_FLOOR
    return max(PARENTS_FLOOR, int(avail * PARENT_MEMORY_SHARE // PER_PARENT_BYTES))


# ------------------------------------------------------------------------------ the stream
def iter_handoff(path: Path, chunk_chars: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Rows of the handoff's `rows` array, decoded incrementally (never loaded whole)."""
    decoder = json.JSONDecoder()
    with Path(path).open("r", encoding="utf-8") as fh:
        buf, eof = "", False
        while True:                                  # find `"rows"` then its `[`
            m = re.search(r'"rows"\s*:\s*\[', buf)
            if m:
                pos = m.end()
                break
            more = fh.read(chunk_chars)
            if not more:
                return
            buf = buf[-64:] + more
        while True:
            while pos < len(buf) and (buf[pos].isspace() or buf[pos] == ","):
                pos += 1
            if pos >= len(buf):
                if eof:
                    return
                more = fh.read(chunk_chars)
                eof = not more
                buf, pos = buf[pos:] + more, 0
                continue
            if buf[pos] == "]":
                return
            try:
                value, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if eof:
                    return
                more = fh.read(chunk_chars)
                eof = not more
                buf, pos = buf[pos:] + more, 0
                continue
            pos = end
            if isinstance(value, dict):
                yield value


def handoff_header(path: Path) -> dict[str, Any]:
    """`schema_version`, `generated_utc` and `n` from the head of the file."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(4096)
    except OSError:
        return {}
    out: dict[str, Any] = {}
    for key in ("schema_version", "n"):
        m = re.search(rf'"{key}"\s*:\s*(-?\d+)', head)
        if m:
            out[key] = int(m.group(1))
    m = re.search(r'"generated_utc"\s*:\s*"([^"]*)"', head)
    if m:
        out["generated_utc"] = m.group(1)
    return out


def lane_of(row: dict[str, Any]) -> str:
    reason = str(row.get("reason") or "")
    if reason in BUILD_REASONS or row.get("class") in ("build_fail", "fail_3x"):
        return "build"
    if reason in FIRE_REASONS:
        return "fire"
    if reason in DEPTH_REASONS or row.get("class") == "short_history":
        return "depth"
    return "other"


def _hash(cell: str) -> int:
    return int.from_bytes(hashlib.blake2b(cell.encode("utf-8"), digest_size=8).digest(), "big")


# ------------------------------------------------------------------------------ build lane
_NUM = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?")
_SYM_HINT = re.compile(r"\bfor [A-Z0-9.&_-]{3,}\b")


def _census_kind() -> Any:
    """`unknown_share_census.build_failure_kind` (the census's own vocabulary), else a prefix."""
    try:
        if str(BASE / "scripts") not in sys.path:
            sys.path.insert(0, str(BASE / "scripts"))
        import importlib
        return importlib.import_module("unknown_share_census").build_failure_kind
    except Exception:
        return lambda w: str(w)[:60]


def build_signature(why: Any, family: Any = "") -> str:
    """A build failure with the cell stripped out of it, so the table aggregates."""
    w = str(why or "").strip()
    for pre in ("NOT_RUN_BUILD_FAILED:", "NOT_RUN_MODIFIER:"):
        if w.startswith(pre):
            w = w[len(pre):].strip()
    m = re.search(r"raised (\w+): (.*)", w)
    if m:
        msg = re.sub(r"'[A-Z0-9.&_-]{3,}'", "'<SYM>'", m.group(2))
        msg = _NUM.sub("<N>", msg)
        return f"raised {m.group(1)}: {msg[:110]}"
    kind = _census_kind()(w)
    return _NUM.sub("<N>", _SYM_HINT.sub("for <SYM>", str(kind)))[:120] or "unnamed"


_UNEXPECTED = re.compile(r"unexpected keyword argument '([^']+)'")
#: Params that narrate a cell's breeding; no family reads them (`hypothesis_families`).
NARRATIVE_KEYS = frozenset({"mechanism_genome", "crossed_slot", "population", "title", "note",
                            "notes", "mechanism_note", "claim", "provenance", "origin"})
LABEL_KEYS = frozenset({"lower_turnover"})


def repair(family: str, params: dict[str, Any], why: str
           ) -> tuple[str, dict[str, Any] | None, str]:
    """(verdict, repaired params, reason). verdict: FIXED | ABANDONED | NO_REPAIR."""
    from research import grammar_param_names as gpn
    p = dict(params or {})
    bad = set(_UNEXPECTED.findall(str(why or "")))
    if bad & gpn.grammar_keys(family) or (gpn.grammar_keys(family) & set(p)
                                          and "unexpected keyword" in str(why)):
        fixed, how = gpn.translate(family, p)
        if fixed is None:
            return "ABANDONED", None, f"grammar names with no faithful translation: {how}"
        return "FIXED", fixed, f"coevolution grammar names translated ({how})"
    if bad & LABEL_KEYS:
        fixed = {k: v for k, v in p.items() if k not in LABEL_KEYS}
        return "FIXED", fixed, f"label {sorted(bad & LABEL_KEYS)} dropped; the change is the chart"
    if bad & NARRATIVE_KEYS:
        rest = {k: v for k, v in p.items() if k not in NARRATIVE_KEYS}
        if not [k for k in rest if k not in ("timeframe", "session")]:
            return "ABANDONED", None, ("narrative-only params: stripped, this is the family at "
                                       "its defaults, i.e. the parent cell under the child's "
                                       "name (owner: alpha_genome slot -> executable mapping)")
        return "FIXED", rest, f"narrative keys {sorted(bad & NARRATIVE_KEYS)} dropped"
    side = p.get("side")
    if isinstance(side, str) and "not supported between instances of 'str'" in str(why):
        val = {"short": -1, "sell": -1, "long": 1, "buy": 1}.get(side.strip().lower())
        if val is None:
            return "ABANDONED", None, f"side={side!r} names no direction"
        return "FIXED", {**p, "side": val}, f"side {side!r} -> {val}"
    return "NO_REPAIR", None, "no repair registered for this signature"


def modifier_refusal(family: str, params: dict[str, Any]) -> str | None:
    """The judge's own modifier preflight on a repaired rule; None when it would build."""
    try:
        from mt5desk import cell_modifiers, family_inputs

        from libs.research import family_firing as ff
        fn = ff.family_fn(family)
        if fn is None:
            return f"no constructor for {family}"
        _call, mods = cell_modifiers.split(fn, family_inputs.strip_identity_keys(family, params))
        return cell_modifiers.refusal(mods)
    except Exception as exc:
        return f"preflight raised {type(exc).__name__}"


def signature_owner(sig: str) -> str:
    if sig.startswith("raised "):
        return "family author (the family's own code raised)"
    if "bars" in sig or "basket" in sig or "surface" in sig or "calendar" in sig:
        return "data: bars_wanted -> fetch_universe / the input's collector"
    if "peer" in sig or "driver" in sig or "leg" in sig:
        return "discovery_compiler.complete_inputs (names the missing input)"
    return "judge retry clock (BUILD_FAILED_RETRY_DAYS) until a repair is registered"


# ------------------------------------------------------------------------------ fire probe
def _need_days() -> int:
    try:
        from research.gate_policy import LOCKBOX_FRAC
        frac = float(LOCKBOX_FRAC)
    except Exception:
        frac = 0.2
    return math.ceil(CPCV_MIN_DAYS / max(0.05, 1.0 - frac))


def chart_of(params: dict[str, Any]) -> str:
    return str((params or {}).get("timeframe") or "H1").upper()


def load_bars(symbol: str, chart: str) -> Any:
    """The chart's FULL history (the judge reads all of it), resampled from a finer file the way
    `family_firing._bars` does when the chart itself is not held."""
    from libs.research import family_firing as ff
    src = ff._source_chart(symbol, chart)
    if src is None:
        return None
    try:
        import pandas as pd
        from mt5desk import families
        raw = pd.read_parquet(UNIVERSE / f"{symbol}_{src}.parquet")
        if src != chart:
            raw = families._h1(raw)
            agg = {c: f for c, f in ff._AGG.items() if c in raw.columns}
            raw = raw.resample(ff._RULE[chart], label="left", closed="left").agg(agg)
            raw = raw.dropna(subset=["close"])
        frame = families._h1(raw)
    except Exception:
        return None
    return frame if frame is not None and len(frame) else None


def fire_days(family: str, symbol: str, bars: Any, params: dict[str, Any]
              ) -> tuple[int | None, str]:
    """Distinct days the family fires on `bars`, called as `external_gauntlet.build_cell` calls
    it; (None, why) when it cannot be built here."""
    from mt5desk import cell_modifiers, family_inputs
    from mt5desk.family_call import session_filter

    from libs.research import family_firing as ff
    fn = ff.family_fn(family)
    if fn is None:
        return None, "no constructor"
    try:
        extra, why = family_inputs.resolve(symbol, family, params, bars)
    except Exception as exc:
        return None, f"inputs raised {type(exc).__name__}"
    if extra is None:
        return None, f"inputs: {str(why)[:80]}"
    call = family_inputs.strip_identity_keys(family, params)
    call.update(extra)
    call, mods = cell_modifiers.split(fn, call)
    if cell_modifiers.refusal(mods):
        return None, "modifier refused"
    try:
        try:
            sigs = fn(bars, side=1, **call)
        except TypeError:
            sigs = fn(bars, **call)
    except Exception as exc:
        return None, f"raised {type(exc).__name__}"
    sigs = list(sigs or [])
    if params.get("session") is not None:
        sigs = session_filter(sigs, params.get("session"))
    sigs = cell_modifiers.apply(sigs, bars, mods)
    days = set()
    for g in sigs:
        t = getattr(g, "time", None)
        if t is not None:
            days.add(str(t)[:10])
    return len(days), "ok"


def ladder_keys(family: str, params: dict[str, Any]) -> list[str]:
    """Numeric, non-exit, non-hour parameters to scale: the parent's own first, then the family's
    signature defaults, at most LADDER_PARAMS."""
    from mt5desk import cell_modifiers, family_inputs

    from libs.research import family_firing as ff

    def ok(k: str, v: Any) -> bool:
        return (isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0
                and k not in EXIT_KEYS and k not in family_inputs.IDENTITY_KEYS
                and k not in cell_modifiers.MODIFIER_KEYS
                and not (ff._HOUR_PARAM.search(k) and not ff._NOT_HOUR_OF_DAY.search(k)))
    keys = [k for k in sorted(params) if ok(k, params[k])]
    fn = ff.family_fn(family)
    if fn is not None:
        with contextlib.suppress(TypeError, ValueError):
            for n, p in sorted(inspect.signature(fn).parameters.items()):
                if n not in params and n not in keys and ok(n, p.default):
                    keys.append(n)
    return keys[:LADDER_PARAMS]


def _scaled(v: Any, m: float) -> Any:
    if isinstance(v, int):
        out = round(v * m)
        if v > 0:
            out = max(1, out)
        return out if out != v else None
    return round(float(v) * m, 10)


def diagnose(parent: dict[str, Any], bars_for: Any, need: int, deadline: float
             ) -> dict[str, Any]:
    """One parent's diagnosis and children (see the module docstring for the order)."""
    from libs.research import family_firing as ff
    fam, sym = str(parent["family"]), str(parent["symbol"])
    params = dict(parent.get("params") or {})
    chart = chart_of(params)
    probes = 0
    res: dict[str, Any] = {"cell": parent["cell"], "children": []}

    def probe(p: dict[str, Any], c: str | None = None) -> int | None:
        nonlocal probes
        bars = bars_for(sym, c or chart_of(p))
        if bars is None:
            return None
        probes += 1
        n, why = fire_days(fam, sym, bars, p)
        res.setdefault("last_why", why)
        return n

    if parent.get("mode") == "depth_coarser":
        h1 = {**params}
        h1.pop("timeframe", None)
        n = probe(h1, "H1")
        res["probes"] = probes
        if n is not None and n >= need:
            res.update(diagnosis="coarser_chart_holds_history", fires=n,
                       children=[{"params": h1, "fire_days": n, "reparam": {"timeframe": "H1"}}])
        else:
            res.update(diagnosis="awaiting_depth", fires=n)
        return res
    base = probe(params)
    if base is None:
        res.update(diagnosis="unprobeable", why=str(res.get("last_why") or "no bars"),
                   probes=probes)
        return res
    res["fires"] = base
    if base >= need:
        res.update(diagnosis="fires_now", probes=probes)
        return res
    sess = str(params.get("session") or "all").lower()
    if sess != "all":
        best: tuple[int, str] | None = None
        for s in (*ff.SESSION_NAMES, "all"):
            if s == sess:
                continue
            n = probe({**params, "session": s})
            if n is not None and n >= need and (best is None or n > best[0]):
                best = (n, s)
            if best is not None and s == "all":
                break
        if best is not None:
            res.update(diagnosis="session_mismatch", probes=probes,
                       children=[{"params": {**params, "session": best[1]}, "fire_days": best[0],
                                  "reparam": {"session": [sess, best[1]]}}])
            return res
    if chart in INTRADAY:
        h1 = {**params}
        h1.pop("timeframe", None)
        n = probe(h1, "H1")
        if n is not None and n >= need:
            res.update(diagnosis="timeframe_mismatch", probes=probes,
                       children=[{"params": h1, "fire_days": n,
                                  "reparam": {"timeframe": [chart, "H1"]}}])
            return res
    fn_defaults: dict[str, Any] = {}
    fn = ff.family_fn(fam)
    if fn is not None:
        with contextlib.suppress(TypeError, ValueError):
            fn_defaults = {n: p.default for n, p in inspect.signature(fn).parameters.items()}
    kids: list[dict[str, Any]] = []
    for m in LADDER:
        for k in ladder_keys(fam, params):
            if time.monotonic() > deadline or len(kids) >= MAX_CHILDREN:
                break
            v = params.get(k, fn_defaults.get(k))
            nv = _scaled(v, m)
            if nv is None:
                continue
            n = probe({**params, k: nv})
            if n is not None and n >= need:
                kids.append({"params": {**params, k: nv}, "fire_days": n,
                             "reparam": {"param": k, "from": v, "to": nv, "mult": m}})
    res["probes"] = probes
    if kids:
        res.update(diagnosis="threshold_unreachable", children=kids)
    else:
        res.update(diagnosis="no_bounded_variant_fires")
    return res


def probe_chart(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Worker: every parent on one (symbol, chart), bars loaded once per chart."""
    for p in (str(BASE), str(BASE / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    cache: dict[tuple[str, str], Any] = {}

    def bars_for(sym: str, chart: str) -> Any:
        k = (sym, chart)
        if k not in cache:
            cache[k] = load_bars(sym, chart)
        return cache[k]
    out = []
    deadline = time.monotonic() + float(task["seconds"])
    for parent in task["parents"]:
        if time.monotonic() > deadline:
            out.append({"cell": parent["cell"], "diagnosis": "budget", "probes": 0})
            continue
        t0 = time.monotonic()
        try:
            r = diagnose(parent, bars_for, int(task["need"]), deadline)
        except Exception as exc:
            r = {"cell": parent["cell"], "diagnosis": "unprobeable",
                 "why": f"probe raised {type(exc).__name__}: {str(exc)[:80]}", "probes": 0}
        r["seconds"] = round(time.monotonic() - t0, 3)
        out.append(r)
    return out


# ------------------------------------------------------------------------------ depth lane
def chart_depth(symbol: str, chart: str) -> dict[str, Any] | None:
    """Trading days held on the chart (the file itself; a finer file when it is not held)."""
    from libs.research import family_firing as ff
    src = ff._source_chart(symbol, chart)
    if src is None:
        return None
    try:
        import pandas as pd
        idx = pd.read_parquet(UNIVERSE / f"{symbol}_{src}.parquet", columns=["close"]).index
        if not isinstance(idx, pd.DatetimeIndex):
            return None
        days = idx.normalize().unique()
        return {"days": len(days), "bars": len(idx), "source_chart": src,
                "first": str(idx.min())[:10], "last": str(idx.max())[:10]}
    except Exception:
        return None


def depth_factor(days_fired: int) -> float:
    if days_fired <= 0:
        return READMIT_GROWTH
    return min(READMIT_GROWTH_CAP, max(READMIT_GROWTH, CPCV_MIN_DAYS / float(days_fired)))


def baseline_for(snaps: list[list[Any]], parked: str | None) -> int | None:
    """The chart's depth at the latest snapshot taken at or before the cell was parked."""
    if not snaps:
        return None
    t = _ts(parked)
    best = snaps[0][1]
    for at, d in snaps:
        st = _ts(at)
        if t is not None and st is not None and st <= t:
            best = d
    return int(best)


def extendable(chart: str, depth: dict[str, Any]) -> bool:
    """Could a deeper pull hold more? Intraday files short of the collector's request, or an H1
    file that starts later than the collector's 2018 start."""
    if chart in NOMINAL_BARS:
        return int(depth.get("bars") or 0) < int(NOMINAL_BARS[chart] * 0.9)
    return str(depth.get("first") or "9999") > "2018-02-01"


# ------------------------------------------------------------------------------ docket lookup
def docket_params(wanted: dict[str, dict[str, Any]], *, docket: Path | None = None,
                  deadline: float | None = None) -> dict[str, dict[str, Any]]:
    """{cell: docket row fields} for every wanted cell found in one streaming docket pass."""
    from libs.research import family_firing as ff
    from research.frontier_identity import docket_cell_id
    docket = DOCKET if docket is None else docket
    pairs = {(str(w.get("symbol")), str(w.get("family"))) for w in wanted.values()}
    found: dict[str, dict[str, Any]] = {}
    if not docket.exists() or not wanted:
        return found
    for row in ff.iter_json_array(docket):
        if not isinstance(row, dict):
            continue
        if (str(row.get("symbol") or row.get("sym")), str(row.get("family"))) not in pairs:
            continue
        try:
            cid = docket_cell_id(row)
        except Exception:
            continue
        if cid in wanted and cid not in found:
            params = dict(row.get("params") or {})
            rtf = str(row.get("timeframe") or "").upper()
            if rtf and rtf != "H1" and "timeframe" not in params:
                params["timeframe"] = rtf
            found[cid] = {"params": params, "source": row.get("source"),
                          "mechanism_note": str(row.get("mechanism_note") or "")[:300]}
            if len(found) == len(wanted):
                break
        if deadline is not None and time.monotonic() > deadline:
            break
    return found


# ------------------------------------------------------------------------------ donation
def child_row(parent: dict[str, Any], child: dict[str, Any], diagnosis: str) -> dict[str, Any]:
    from research import proposer_common as pc
    fam, sym = str(parent["family"]), str(parent["symbol"])
    row = pc.candidate(
        SEAT, sym, fam, dict(child["params"]),
        mechanism=(f"{fam} on {sym}: the parked parent {parent['cell']} was {diagnosis}; this is "
                   "its bounded re-parameterisation "
                   f"{json.dumps(child.get('reparam'), default=str)} -- the same mechanism, now "
                   "able to reach the judge"),
        title=f"{sym} {fam} -- {diagnosis} child of {parent['cell']}",
        evidence={"parent_cell": parent["cell"], "diagnosis": diagnosis,
                  "reparam": child.get("reparam"), "fire_days": child.get("fire_days"),
                  "parent_reason": parent.get("reason"), "trial_family": fam,
                  "screen": "fireability only (signal days); no return was read"})
    row["parent_cell"] = parent["cell"]
    row["trial_family"] = fam
    row["lineage"] = {"root": parent["cell"], "operator": f"handoff:{diagnosis}"}
    return row


def donate(rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    if not rows:
        return {"donated": 0, "tests_run": 0}
    if dry_run:
        return {"donated": 0, "tests_run": 0, "would_donate": len(rows)}
    try:
        from research import proposer_common as pc
        path = pc.donate(SEAT, rows, tests_run=len(rows))
        counts = pc.donation_counts()
        return {"donated": int(counts.get("donated") or 0), "tests_run": len(rows),
                "path": str(path) if path else None,
                "refused_unstamped": int(counts.get("refused_unstamped") or 0),
                "refused_wrong_lane": int(counts.get("refused_wrong_lane") or 0)}
    except Exception as exc:
        return {"donated": 0, "tests_run": 0, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


# ------------------------------------------------------------------------------ the pass
class Books:
    """Per-reason IN and OUT, every row exactly one outcome."""

    def __init__(self) -> None:
        self.inn: Counter[str] = Counter()
        self.out: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: {"re_emitted": Counter(), "fixed": Counter(), "deferred": Counter(),
                     "abandoned": Counter()})

    def book(self, reason: str, outcome: str, why: str, n: int = 1) -> None:
        self.out[reason][outcome][why] += n
        if self.out[reason][outcome][why] <= 0:
            del self.out[reason][outcome][why]

    def doc(self) -> dict[str, Any]:
        rows = {}
        for reason, n in sorted(self.inn.items(), key=lambda kv: -kv[1]):
            o = self.out[reason]
            rows[reason] = {"in": n, **{k: sum(v.values()) for k, v in o.items()},
                            "by_why": {k: dict(v.most_common()) for k, v in o.items() if v}}
            rows[reason]["balanced"] = n == sum(sum(v.values()) for v in o.values())
        return rows


def run(*, budget_s: float = 420.0, dry_run: bool = False, handoff: Path = HANDOFF,
        docket: Path | None = None, out: Path = OUT, state_path: Path = STATE,
        requeue_path: Path = REQUEUE, depth_path: Path = DEPTH_BACKLOG,
        workers: int | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    stop = t0 + budget_s
    at = _now()
    avail = free_bytes()
    n_workers = workers or workers_for(avail)
    cap = parents_cap(avail)
    need = _need_days()
    doc: dict[str, Any] = {"schema": SCHEMA, "generated_utc": at, "handoff": str(handoff),
                           "memory": {"available_mb": None if avail is None else avail >> 20,
                                      "workers": n_workers, "parents_cap": cap,
                                      "basis": "psutil.virtual_memory().available"},
                           "need_fire_days": need}
    if not handoff.exists():
        doc.update(status=UNMEASURED, why=f"{handoff.name} is absent: the coverage pass has not "
                                          "handed anything over on this host")
        if not dry_run:
            _atomic_write(out, doc)
        return doc
    header = handoff_header(handoff)
    doc["handoff_header"] = header
    state = _read_json(state_path) if state_path.exists() else None
    state = state if isinstance(state, dict) else {}
    cursor = int(state.get("cursor", -1))
    cycle = int(state.get("cycle", 0))
    snaps: dict[str, list[list[Any]]] = state.get("depth_snapshots") or {}
    repaired: dict[str, str] = state.get("repaired_parents") or {}
    # Parents re-queued as `fires_now` on an earlier pass. One that comes back parked under the
    # same reason means the judge's full build (costs, fills, carve) disagrees with the probe:
    # it is never re-queued again on the probe's word (no loop), and is counted by name.
    asked_before: dict[str, str] = state.get("fires_now_requeued") or {}
    rate = float(state.get("seconds_per_parent") or PROBE_S_PRIOR * 6)
    old_req = (_read_json(requeue_path) or {}).get("requests") if requeue_path.exists() else None
    old_req = old_req if isinstance(old_req, dict) else {}

    books = Books()
    sigs: Counter[str] = Counter()
    sig_fams: dict[str, Counter[str]] = defaultdict(Counter)
    sig_example: dict[str, str] = {}
    repair_wanted: dict[str, dict[str, Any]] = {}
    depth_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    requests: dict[str, dict[str, Any]] = {}
    # How many parents this pass can probe: the budget's probe share at the measured rate, times
    # the workers, bounded by what free memory lets the pass hold.
    n_select = max(1, min(cap, int(budget_s * 0.6 / max(rate, 0.01) * n_workers)))
    # max-heaps of the n_select smallest hashes after the cursor, and overall (for the wrap)
    ahead: list[tuple[int, str, dict[str, Any]]] = []
    wrap: list[tuple[int, str, dict[str, Any]]] = []
    fire_total = 0

    def keep(heap: list[tuple[int, str, dict[str, Any]]], h: int, info: dict[str, Any]) -> None:
        if len(heap) < n_select:
            heapq.heappush(heap, (-h, info["cell"], info))
        elif -heap[0][0] > h:
            heapq.heapreplace(heap, (-h, info["cell"], info))

    n_rows = 0
    still_parked: set[str] = set()
    for row in iter_handoff(handoff):
        n_rows += 1
        cell = str(row.get("cell") or "")
        if cell in old_req:
            still_parked.add(cell)
        reason = str(row.get("reason") or row.get("class") or "unnamed")
        books.inn[reason] += 1
        lane = lane_of(row)
        if lane == "build":
            sig = build_signature(row.get("why"), row.get("family"))
            sigs[sig] += 1
            sig_fams[sig][str(row.get("family") or "")] += 1
            sig_example.setdefault(sig, str(row.get("why") or "")[:200])
            if cell in repaired:
                books.book(reason, "fixed", "repaired_child_already_emitted")
            elif ("unexpected keyword" in str(row.get("why")) or
                  "not supported between instances of 'str'" in str(row.get("why"))):
                if len(repair_wanted) < cap:
                    repair_wanted[cell] = {"cell": cell, "symbol": row.get("symbol"),
                                           "family": row.get("family"), "reason": reason,
                                           "why": str(row.get("why") or "")}
                else:
                    books.book(reason, "deferred", "repair_candidate_over_memory_cap")
            else:
                books.book(reason, "deferred", f"awaiting_fix:{signature_owner(sig)}")
        elif lane == "fire":
            fire_total += 1
            h = _hash(cell)
            info = {"cell": cell, "symbol": row.get("symbol"), "family": row.get("family"),
                    "reason": reason, "days": int(row.get("days") or 0), "mode": "fire", "h": h}
            if h > cursor:
                keep(ahead, h, info)
            keep(wrap, h, info)
            # Booked provisionally by cursor position; a row acted on this pass is moved below.
            books.book(reason, "deferred", "visited_this_cycle:judge_or_next_cycle"
                       if h <= cursor else "awaiting_turn:cursor")
        elif lane == "depth":
            ck = f"{row.get('symbol')}_{str(row.get('timeframe') or 'H1').upper()}"
            if sum(len(v) for v in depth_rows.values()) < cap * 4:
                depth_rows[ck].append({"cell": cell, "reason": reason,
                                       "days": int(row.get("days") or 0),
                                       "parked": row.get("first_parked_utc"),
                                       "symbol": row.get("symbol"), "family": row.get("family")})
            else:
                books.book(reason, "deferred", "depth_row_over_memory_cap")
        else:
            cls = str(row.get("class") or "")
            books.book(reason, "deferred",
                       f"owned_elsewhere:{OWNED_ELSEWHERE.get(cls, 'judge retry clock')}")
        if time.monotonic() > stop - budget_s * 0.4:
            doc["handoff_stream"] = "TRUNCATED_BY_BUDGET"
            break
    doc["handoff_rows_read"] = n_rows

    # ---- selection: the next n_select fire parents after the cursor, wrapping at cycle end
    picks = sorted((i for _h, _c, i in ahead), key=lambda i: i["h"])
    wrapped = len(picks) < n_select
    new_cursor = picks[-1]["h"] if picks else cursor
    if wrapped:
        have = {i["cell"] for i in picks}
        extra = [i for i in sorted((i for _h, _c, i in wrap), key=lambda i: i["h"])
                 if i["cell"] not in have][: n_select - len(picks)]
        picks += extra
        new_cursor = extra[-1]["h"] if extra else -1
    selected = {i["cell"]: i for i in picks}
    for i in picks:
        books.book(i["reason"], "deferred", "visited_this_cycle:judge_or_next_cycle"
                   if i["h"] <= cursor else "awaiting_turn:cursor", -1)

    # ---- depth lane: measure charts, requeue on growth, coarser-chart candidates
    depth_doc: dict[str, Any] = {}
    coarser: dict[str, dict[str, Any]] = {}
    for ck, cells in depth_rows.items():
        sym, _, tf = ck.rpartition("_")
        d = chart_depth(sym, tf)
        series = snaps.setdefault(ck, [])
        if d is not None and (not series or series[-1][1] != d["days"]):
            series.append([at, d["days"]])
            del series[:-DEPTH_SNAPSHOTS]
        waiting = 0
        for c in cells:
            if d is None:
                books.book(c["reason"], "deferred", "awaiting_depth:no_bars_on_this_host")
                continue
            base = baseline_for(series, c["parked"])
            target = None if base is None else math.ceil(base * depth_factor(c["days"]))
            if target is not None and d["days"] >= target and base is not None and \
                    d["days"] > base:
                requests[c["cell"]] = {"at": at, "cause": "history_sufficient", "chart": ck,
                                       "days_now": d["days"], "days_at_park": base}
                books.book(c["reason"], "re_emitted", "requeued:history_sufficient")
                continue
            waiting += 1
            if tf in INTRADAY and len(coarser) < max(1, n_select // 4) and \
                    _hash(c["cell"]) % 7 == cycle % 7:
                coarser[c["cell"]] = {**c, "mode": "depth_coarser"}
            else:
                books.book(c["reason"], "deferred", "awaiting_depth:bars_wanted")
        if d is not None:
            depth_doc[ck] = {"cells_waiting": waiting, **d,
                             "extendable": extendable(tf, d), "snapshots": len(series)}

    # ---- params for every parent this pass will act on, one docket stream
    wanted = {**repair_wanted, **selected, **coarser}
    t_dk = time.monotonic()
    params = docket_params(wanted, docket=docket, deadline=stop - budget_s * 0.35)
    doc["docket_lookup"] = {"wanted": len(wanted), "found": len(params),
                            "seconds": round(time.monotonic() - t_dk, 2)}

    children: list[dict[str, Any]] = []
    # ---- build repairs
    repairs_doc: Counter[str] = Counter()
    for cell, r in repair_wanted.items():
        found = params.get(cell)
        if found is None:
            books.book(r["reason"], "deferred", "repair:params_not_in_docket_this_pass")
            continue
        verdict, fixed, why = repair(str(r["family"]), found["params"], r["why"])
        if verdict == "FIXED" and fixed is not None:
            refused = modifier_refusal(str(r["family"]), fixed)
            if refused:
                verdict, why = "ABANDONED", f"repaired, but the judge would refuse it: {refused}"
        repairs_doc[f"{verdict}: {why}"] += 1
        if verdict == "FIXED" and fixed is not None:
            children.append(child_row({**r, "params": found["params"]},
                                      {"params": fixed, "reparam": {"repair": why}},
                                      "build_repaired"))
            repaired[cell] = at
            books.book(r["reason"], "fixed", "repaired_child_emitted")
        elif verdict == "ABANDONED":
            books.book(r["reason"], "abandoned", why[:120])
        else:
            books.book(r["reason"], "deferred", "awaiting_fix:no repair registered")

    # ---- fire + coarser-chart probes, in parallel by chart
    tasks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell, r in {**selected, **coarser}.items():
        found = params.get(cell)
        if found is None:
            books.book(r["reason"], "deferred", "params_not_in_docket_this_pass")
            continue
        p = {**r, "params": found["params"]}
        tasks[f"{r['symbol']}|{chart_of(found['params'])}"].append(p)
    left = max(5.0, stop - time.monotonic() - 20.0)
    results: list[dict[str, Any]] = []
    jobs = [{"parents": v, "need": need, "seconds": left * 0.9} for v in tasks.values()]
    t_pr = time.monotonic()
    if jobs and n_workers > 1:
        with ProcessPoolExecutor(max_workers=min(n_workers, len(jobs))) as ex:
            futs = [ex.submit(probe_chart, j) for j in jobs]
            for f in as_completed(futs):
                with contextlib.suppress(Exception):
                    results.extend(f.result())
    else:
        for j in jobs:
            results.extend(probe_chart(j))
    probe_s = time.monotonic() - t_pr
    by_cell = {**selected, **coarser}
    diag: Counter[str] = Counter()
    probes = 0
    visited = 0
    for res in results:
        parent = by_cell.get(res["cell"])
        if parent is None:
            continue
        parent = {**parent, "params": params[res["cell"]]["params"]}
        dg = str(res.get("diagnosis"))
        diag[dg] += 1
        probes += int(res.get("probes") or 0)
        rsn = parent["reason"]
        if dg == "budget":
            books.book(rsn, "deferred", "probe_budget:next_pass")
            continue
        visited += 1
        if dg == "fires_now" and parent["cell"] in asked_before:
            books.book(rsn, "deferred", "probe_disagrees_with_judge:requeued_before")
        elif dg == "fires_now":
            asked_before[parent["cell"]] = at
            requests[parent["cell"]] = {"at": at, "cause": "fires_now",
                                        "fire_days": res.get("fires")}
            books.book(rsn, "re_emitted", "requeued:fires_now")
        elif res.get("children"):
            for ch in res["children"]:
                children.append(child_row(parent, ch, dg))
            books.book(rsn, "re_emitted", f"children:{dg}")
        elif dg == "no_bounded_variant_fires":
            books.book(rsn, "abandoned", "no_bounded_variant_fires")
        elif dg == "awaiting_depth":
            books.book(rsn, "deferred", "awaiting_depth:bars_wanted")
        else:
            books.book(rsn, "deferred", f"unprobeable:{str(res.get('why') or '')[:60]}")
    # parents processed at the measured rate drive the next pass's selection size
    if visited:
        rate = max(0.01, probe_s * max(1, min(n_workers, len(jobs))) / visited)
    # a selected parent the workers never returned (a crashed worker) is still booked
    returned = {r.get("cell") for r in results}
    for cell, r in by_cell.items():
        if cell not in returned and cell in params:
            books.book(r["reason"], "deferred", "probe_lost:next_cycle")

    # ---- requests carry over until the judge has acted on them (the cell still parked)
    for c, r in old_req.items():
        if c not in requests and c in still_parked:
            requests[c] = r
    donation = donate(children, dry_run=dry_run)

    new_cycle = cycle + 1 if wrapped else cycle
    per_hour = visited
    eta_h = None if not per_hour else round(fire_total / per_hour, 1)
    doc.update({
        "status": "MEASURED",
        "books": books.doc(),
        "totals": {"in": sum(books.inn.values()),
                   **{k: sum(sum(o[k].values()) for o in books.out.values())
                      for k in ("re_emitted", "fixed", "deferred", "abandoned")}},
        "build_signatures": [{"signature": s, "cells": n,
                              "families": dict(sig_fams[s].most_common(5)),
                              "owner": signature_owner(s), "example": sig_example.get(s)}
                             for s, n in sigs.most_common(25)],
        "build_repairs": dict(repairs_doc.most_common()),
        "fire": {"population": fire_total, "selected": len(selected), "visited": visited,
                 "diagnoses": dict(diag.most_common()), "fire_probes": probes,
                 "cycle": new_cycle, "wrapped_this_pass": wrapped,
                 "hours_per_cycle_at_this_rate": eta_h,
                 "seconds_per_parent_per_worker": round(rate, 3),
                 "ladder": {"multipliers": LADDER, "params": LADDER_PARAMS,
                            "max_children": MAX_CHILDREN}},
        "depth": {"charts": len(depth_doc),
                  "extendable_charts": sum(1 for v in depth_doc.values() if v["extendable"]),
                  "coarser_candidates": len(coarser)},
        "children_emitted": len(children),
        "donation": donation,
        "requeue_requests": len(requests),
        "trials": {"charged": donation.get("tests_run", 0),
                   "rule": "every child is donated with tests_run = children emitted and becomes "
                           "a docket row the sealed judge charges; probes read signal times only"},
        "seconds": round(time.monotonic() - t0, 1),
    })
    if not dry_run:
        _atomic_write(requeue_path, {"schema": 1, "generated_utc": at, "requests": requests,
                                     "reader": "judge_coverage.update_unrunnable_bank"})
        _atomic_write(depth_path, {"schema": 1, "generated_utc": at, "need_rule":
                                   "re-queued when trading days >= depth at park x "
                                   "clamp(60/days, 1.25, 3)",
                                   "reader": "hourly_cycle.bars_wanted_symbols",
                                   "charts": depth_doc})
        _atomic_write(state_path, {"cursor": new_cursor, "cycle": new_cycle, "updated_utc": at,
                                   "seconds_per_parent": rate, "depth_snapshots": snaps,
                                   "fires_now_requeued": dict(sorted(
                                       asked_before.items(), key=lambda kv: kv[1])[-cap:]),
                                   "repaired_parents": dict(sorted(
                                       repaired.items(), key=lambda kv: kv[1])[-cap:])})
        _atomic_write(out, doc)
    return doc


def depth_symbols(path: Path = DEPTH_BACKLOG) -> list[str]:
    """Symbols whose extendable charts hold the most waiting cells (bars_wanted's second source)."""
    doc = _read_json(path)
    charts = doc.get("charts") if isinstance(doc, dict) else None
    if not isinstance(charts, dict):
        return []
    by: Counter[str] = Counter()
    for ck, v in charts.items():
        if isinstance(v, dict) and v.get("extendable") and int(v.get("cells_waiting") or 0) > 0:
            by[str(ck).rpartition("_")[0].upper()] += int(v["cells_waiting"])
    return [s for s, _ in by.most_common()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=420.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, workers=a.workers)
    print(json.dumps({k: doc.get(k) for k in ("status", "totals", "children_emitted",
                                               "requeue_requests", "fire", "seconds", "why")},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
