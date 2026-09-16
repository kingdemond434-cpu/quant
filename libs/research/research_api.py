"""THE RESEARCH API: one typed surface, so every researcher gets the same truth.

MEASURED 2026-09-16 (Tier-1 item Q8): the desk has eleven research capabilities and about as many
ways to reach each one. Bars are loaded by `external_gauntlet._bars_for` here, `shadow_forward.
fetch_h1` there, and a bare `pd.read_parquet` in whatever a seat wrote last night; the cost basis
is `Costs.from_symbol` in one organ and a literal spread in another. Nothing is wrong with any
single loader. What is wrong is that two organs asking the SAME question can get two different
answers and neither can tell -- and a desk whose evidence depends on which loader a seat happened
to import has no evidence, it has a coincidence.

THIS IS A FACADE AND NOTHING ELSE. Every verb delegates to the organ that already owns the work:
`mt5desk.families._h1` for the bar clock, `mt5desk.engine.run_backtest` for the simulation,
`external_gauntlet.run_gauntlet` for the ten gates, `robust_elog.score_book` for growth,
`semantic_memory.Memory` for what the desk already knows. It re-implements NOTHING and invents
nothing. A verb that cannot reach its organ returns UNMEASURED NAMING THE MISSING MODULE (L1.28a:
absence is a verdict, never a clean answer) -- never a crash, and never a plausible number
standing in for one nobody computed.

IT GRANTS NO AUTHORITY. `gauntlet.run` judges and does not certify; `forward.register` files a
REQUEST and enrols nothing; nothing here writes a certificate, a sleeve row or a heat fraction.
The promotion firewall is untouched: this is the surface researchers READ the desk through, not
a way around the organs that decide.

DETERMINISM IS THE PRODUCT. Every call appends one row to
`desks/mt5/data/research_api_calls.jsonl`: {at, verb, input_hash, output_hash, seconds, basis,
delegate}. `input_hash` is the sha256 of the request dataclass as sorted canonical JSON, so two
identical requests hash identically -- including their defaults, which is exactly why `as_of` and
`seed` are FIELDS and never wall-clock or entropy reads inside a verb. Where the delegate is
deterministic (and the seeded ones are: `WorldConfig.seed`, `significance(seed=)`) the output hash
is identical too, and a replay that disagrees is a finding about the ORGAN, not about the clock.

PIT IS ENFORCED, NOT ASSUMED. `macro.query` refuses every row whose `available_time` is after the
query's `as_of` and REPORTS how many it refused. The axes carry their own knowability: `cot` and
`bis` rows are stamped `knowable_at` (lag-adjusted at ingest) and that is the available time;
`fred` and `ecb` series carry only the observation date `d` and no publication lag, so the facade
uses `d` and SAYS SO in `basis` -- an observation date is a weaker stamp than a vintage, and a
caller who cannot tell the two apart will build a look-ahead without noticing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, TypeVar

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
UNIVERSE = DESK / "data" / "universe"
AXES = DESK / "data" / "axes"
CALL_LOG = DESK / "data" / "research_api_calls.jsonl"
#: forward.register's fallback queue. NO ORGAN READS THIS YET -- `shadow_admission` derives
#: enrolment from certificates in `reports/` and exposes no register/enrol entry point, so this
#: is a REQUEST the desk has not yet wired a consumer for. Said plainly because "wrote a row"
#: and "enrolled a sleeve" must never read identically (III.16).
FORWARD_REQUESTS = DESK / "data" / "forward_register_requests.jsonl"

OK = "OK"
UNMEASURED = "UNMEASURED"
REFUSED = "REFUSED"

OPAQUE: Mapping[str, Any] = {"opaque": True}
_R = TypeVar("_R")

#: verb -> the delegate modules it needs, in the order they are named to the caller. The FIRST
#: is the organ of record for that verb and is what the call log records as `delegate`.
DELEGATES: dict[str, tuple[str, ...]] = {
    "data.query": ("mt5desk.families",),
    "event.query": ("research.forced_flow_calendar",),
    "macro.query": ("libs.data.pit",),
    "causal.test": ("libs.research.information_flow",),
    "factor.build": ("libs.research_os.dsl",),
    "alpha.backtest": ("mt5desk.engine", "mt5desk.families", "mt5desk.family_call"),
    "execution.simulate": ("libs.execution.digital_twin",),
    "portfolio.evaluate": ("libs.portfolio.robust_elog",),
    "gauntlet.run": ("external_gauntlet",),
    "forward.register": ("research.shadow_admission",),
    "evidence.lookup": ("research.semantic_memory", "libs.research.hypothesis_graph"),
}
VERBS: tuple[str, ...] = tuple(DELEGATES)


# --------------------------------------------------------------------------- delegates

_MODULES: dict[str, ModuleType | None] = {}


def _syspath() -> None:
    """The desk tree is reachable at runtime and not to the type checker; the house pattern."""
    for p in (ROOT, DESK, DESK / "scripts"):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def _load(dotted: str) -> ModuleType | None:
    """Import a delegate, or None. NEVER raises: an absent organ is UNMEASURED, not a crash."""
    if dotted in _MODULES:
        return _MODULES[dotted]
    mod: ModuleType | None
    try:
        _syspath()
        mod = importlib.import_module(dotted)
    except Exception:
        mod = None
    _MODULES[dotted] = mod
    return mod


def _mod(dotted: str) -> ModuleType:
    """The delegate, AFTER `_missing` has cleared it. Unreachable on the UNMEASURED path -- it
    raises rather than asserting, so a future caller that skips the guard fails loudly."""
    mod = _load(dotted)
    if mod is None:
        raise ModuleNotFoundError(dotted)
    return mod


def _missing(verb: str) -> list[str]:
    return [m for m in DELEGATES[verb] if _load(m) is None]


def _why(missing: list[str]) -> str:
    return "delegate unavailable: " + ", ".join(missing)


# --------------------------------------------------------------------------- determinism

def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canon(obj: Any) -> Any:
    """Canonical JSON-shaped form. Opaque fields are skipped: a DataFrame is hashed through its
    own `digest` field, never through an id() that changes every process."""
    if obj is None or isinstance(obj, bool | int | str):
        return obj
    if isinstance(obj, float):
        return (round(obj, 12) + 0.0) if math.isfinite(obj) else f"<{obj}>"
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _canon(getattr(obj, f.name)) for f in fields(obj)
                if not f.metadata.get("opaque")}
    if isinstance(obj, Mapping):
        return {str(k): _canon(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, set | frozenset):
        return sorted(json.dumps(_canon(v), sort_keys=True) for v in obj)
    if isinstance(obj, list | tuple):
        return [_canon(v) for v in obj]
    return f"<{type(obj).__name__}>"


def hash_of(obj: Any) -> str:
    """The sha256 every input_hash and output_hash in the call log is taken with."""
    return _sha(json.dumps(_canon(obj), sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _digest(payload: Any) -> str:
    """A stable fingerprint for a frame/array payload, so an opaque field is still replayable."""
    try:
        import pandas as pd
        if isinstance(payload, pd.DataFrame | pd.Series):
            raw = pd.util.hash_pandas_object(payload, index=True).to_numpy().tobytes()
            return f"{type(payload).__name__}:{len(payload)}:{_sha(raw)[:16]}"
    except Exception:
        pass
    return f"<{type(payload).__name__}>"


def _log(verb: str, req: Any, out: Any, seconds: float) -> dict[str, Any]:
    """One row per call. The writer NEVER raises: a log that can take down the verb it records
    would be removed within a week."""
    row = {"at": datetime.now(UTC).isoformat(), "verb": verb, "input_hash": hash_of(req),
           "output_hash": hash_of(out), "seconds": round(float(seconds), 6),
           "basis": str(getattr(out, "basis", "")), "delegate": DELEGATES[verb][0]}
    try:
        CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CALL_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError:
        pass
    return row


# --------------------------------------------------------------------------- schemas

@dataclass
class _Result:
    """Every result carries the same three: what it is, what it rests on, and why not."""
    status: str = UNMEASURED
    basis: str = ""
    why: str = ""


@dataclass(frozen=True)
class BarsRequest:
    symbol: str
    timeframe: str = "H1"
    start: str = ""
    end: str = ""


@dataclass
class Bars(_Result):
    symbol: str = ""
    timeframe: str = ""
    n: int = 0
    first: str = ""
    last: str = ""
    columns: tuple[str, ...] = ()
    digest: str = ""
    frame: Any = field(default=None, repr=False, compare=False, metadata=OPAQUE)


@dataclass(frozen=True)
class EventQuery:
    start: str
    end: str
    kinds: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()


@dataclass
class Events(_Result):
    n: int = 0
    rows: tuple[dict[str, Any], ...] = ()
    kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class MacroQuery:
    axis: str
    series: str = ""
    as_of: str = ""
    limit: int = 5000


@dataclass
class MacroSeries(_Result):
    axis: str = ""
    series: str = ""
    n: int = 0
    points: tuple[tuple[str, float], ...] = ()
    available_time: str = ""
    refused_future: int = 0
    as_of: str = ""


@dataclass(frozen=True)
class CausalTest:
    source: tuple[float, ...]
    target: tuple[float, ...]
    condition: tuple[float, ...] = ()
    lag: int = 1
    bins: int = 4
    n_perm: int = 0
    seed: int = 0
    mode: str = "circular_shift"


@dataclass
class CausalResult(_Result):
    statistic: str = ""
    value: float | None = None
    n: int = 0
    bins: int = 0
    p_value: float | None = None


@dataclass(frozen=True)
class FactorSpec:
    name: str
    tree: Any = None
    symbol: str = ""
    timeframe: str = "H1"


@dataclass
class Factor(_Result):
    name: str = ""
    n: int = 0
    finite: int = 0
    mean: float | None = None
    std: float | None = None
    digest: str = ""
    values: Any = field(default=None, repr=False, compare=False, metadata=OPAQUE)


@dataclass(frozen=True)
class BacktestSpec:
    symbol: str
    family: str
    params: Mapping[str, Any] = field(default_factory=dict)
    timeframe: str = "H1"
    side: int = 1
    cost_mult: float = 1.0
    max_hold_bars: int | None = None


@dataclass
class BacktestResult(_Result):
    symbol: str = ""
    family: str = ""
    n: int = 0
    signals: int = 0
    expectancy: float | None = None
    t: float | None = None
    per_trade_r: tuple[float, ...] = ()


@dataclass(frozen=True)
class ExecutionSim:
    symbol: str
    side: int = 1
    lots: float = 0.01
    reference_price: float = 0.0
    spread_frac: float | None = None
    latency_ms: float = 0.0
    order_type: str = "market"
    hour: int = 0
    slip_frac: float | None = None
    p_fill: float | None = None


@dataclass
class ExecutionResult(_Result):
    symbol: str = ""
    filled: bool = False
    p_fill: float = 0.0
    fill_price: float | None = None
    slip_frac: float = 0.0
    spread_frac: float | None = None
    cost_frac: float = 0.0
    session: str = ""
    spread_bucket: str = ""
    latency_ms: float = 0.0


@dataclass(frozen=True)
class PortfolioEval:
    weights: Mapping[str, float]
    returns: Mapping[str, tuple[float, ...]]
    forward_days: Mapping[str, int] = field(default_factory=dict)
    seed: int = 0


@dataclass
class PortfolioResult(_Result):
    n_sleeves: int = 0
    total_heat: float = 0.0
    robust_score: float | None = None
    mean_log_growth: float | None = None
    cvar_log_growth: float | None = None
    annual_growth_pct: float | None = None
    prob_annual_loss: float | None = None


@dataclass(frozen=True)
class GauntletRun:
    cells: tuple[Mapping[str, Any], ...]
    name: str = "research_api"


@dataclass
class GauntletResult(_Result):
    name: str = ""
    n_cells: int = 0
    n_built: int = 0
    n_judged: int = 0
    n_unmeasured: int = 0
    survivors: int = 0
    n_trials: int = 0
    verdicts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ForwardRegistration:
    symbol: str
    family: str
    params: Mapping[str, Any] = field(default_factory=dict)
    side: str = "LONG"
    timeframe: str = "H1"
    certificate: str = ""
    note: str = ""


@dataclass
class ForwardReceipt(_Result):
    symbol: str = ""
    family: str = ""
    queued: bool = False
    already_authorized: bool = False
    path: str = ""
    request_hash: str = ""


@dataclass(frozen=True)
class EvidenceQuery:
    text: str = ""
    k: int = 10
    kinds: tuple[str, ...] = ()
    symbol: str = ""
    family: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)
    mode: str = "query"


@dataclass
class EvidenceHits(_Result):
    mode: str = ""
    n: int = 0
    hits: tuple[dict[str, Any], ...] = ()
    prior_failures: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- the eleven verbs

def _finish(verb: str, req: Any, out: _R, t0: float) -> _R:
    _log(verb, req, out, time.perf_counter() - t0)
    return out


def data_query(req: BarsRequest) -> Bars:
    """`<SYM>_<TF>.parquet` through the gauntlet's own normaliser -- one bar clock, one answer."""
    t0, verb = time.perf_counter(), "data.query"
    miss = _missing(verb)
    out = Bars(symbol=req.symbol, timeframe=req.timeframe.upper(), why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    fam = _mod("mt5desk.families")
    pq = UNIVERSE / f"{req.symbol}_{out.timeframe}.parquet"
    out.basis = f"{pq} -> mt5desk.families._h1 (external_gauntlet._bars_for's own loader)"
    if not pq.exists():
        out.why = f"no chart: {pq}"
        return _finish(verb, req, out, t0)
    try:
        import pandas as pd
        frame = fam._h1(pd.read_parquet(pq))
        if req.start:
            frame = frame[frame.index >= pd.Timestamp(req.start, tz="UTC")]
        if req.end:
            frame = frame[frame.index <= pd.Timestamp(req.end, tz="UTC")]
    except Exception as exc:
        out.why = f"load failed: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    out.frame, out.n = frame, len(frame)
    out.columns = tuple(str(c) for c in frame.columns)
    out.digest = _digest(frame)
    if out.n:
        out.first, out.last = str(frame.index[0]), str(frame.index[-1])
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


def event_query(req: EventQuery) -> Events:
    """The forced-flow calendar's own rules, filtered. `events()` is pure: no file is read."""
    t0, verb = time.perf_counter(), "event.query"
    miss = _missing(verb)
    out = Events(why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    cal = _mod("research.forced_flow_calendar")
    rules = getattr(cal, "RULES_VERSION", "?")
    out.basis = f"research.forced_flow_calendar.events (pure rules, RULES_VERSION {rules})"
    try:
        rows = [e.to_json() for e in cal.events(date.fromisoformat(req.start),
                                                date.fromisoformat(req.end))]
    except Exception as exc:
        out.why = f"calendar failed: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    if req.kinds:
        rows = [r for r in rows if str(r.get("kind")) in set(req.kinds)]
    if req.instruments:
        want = {s.upper() for s in req.instruments}
        rows = [r for r in rows if want & {str(i).upper() for i in (r.get("instruments") or ())}]
    out.rows = tuple(rows)
    out.n = len(rows)
    out.kinds = tuple(sorted({str(r.get("kind")) for r in rows}))
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


def _axis_points(doc: Mapping[str, Any], series: str) -> tuple[list[tuple[str, float]], str]:
    """Every axis shape reduced to (available_time, value). The stamp's strength is returned."""
    if isinstance(doc.get("series"), Mapping):
        block = doc["series"].get(series) or {}
        pts = [(str(p.get("d")), float(p.get("v"))) for p in (block.get("points") or ())
               if p.get("d") is not None and p.get("v") is not None]
        return pts, ("observation date `d` -- NO publication lag is recorded on this axis, so "
                     "this is weaker than a vintage stamp")
    sym, _, fieldname = series.partition(".")
    fieldname = fieldname or "net_pct_oi"
    pts = [(str(r.get("knowable_at")), float(r.get(fieldname)))
           for r in (doc.get("rows") or ())
           if str(r.get("symbol", "")).upper() == sym.upper() and r.get(fieldname) is not None]
    lag = doc.get("knowable_lag_days")
    return pts, f"`knowable_at` (lag-adjusted at ingest, knowable_lag_days={lag})"


def macro_query(req: MacroQuery) -> MacroSeries:
    """A macro axis, POINT-IN-TIME. Rows available after `as_of` are refused and counted."""
    t0, verb = time.perf_counter(), "macro.query"
    miss = _missing(verb)
    as_of = req.as_of or datetime.now(UTC).isoformat()
    out = MacroSeries(axis=req.axis, series=req.series, as_of=as_of, why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    path = AXES / f"{req.axis}.json"
    if not path.exists():
        out.why = f"no axis: {path}"
        return _finish(verb, req, out, t0)
    try:
        doc = json.loads(path.read_text("utf-8"))
        pts, stamp = _axis_points(doc, req.series)
    except Exception as exc:
        out.why = f"axis unreadable: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    out.basis = (f"{path} available_time = {stamp}; PIT enforced by "
                 f"libs.data.pit.usable_at's rule (available_time <= as_of)")
    cut = as_of[:10]
    kept = [(t, v) for t, v in pts if t and t[:10] <= cut]
    out.refused_future = len(pts) - len(kept)
    kept.sort(key=lambda tv: tv[0])
    out.points = tuple(kept[-max(int(req.limit), 0):]) if req.limit else ()
    out.n = len(out.points)
    out.available_time = out.points[-1][0] if out.points else ""
    if not pts:
        out.why = f"no points for series {req.series!r} on axis {req.axis!r}"
        return _finish(verb, req, out, t0)
    out.status = OK if out.n else REFUSED
    out.why = ("" if out.n else
               f"all {out.refused_future} rows are knowable only after as_of={as_of}")
    return _finish(verb, req, out, t0)


def causal_test(req: CausalTest) -> CausalResult:
    """Transfer entropy, or CMI when a conditioning series is given. The null is seeded."""
    t0, verb = time.perf_counter(), "causal.test"
    miss = _missing(verb)
    out = CausalResult(why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    flow = _mod("libs.research.information_flow")
    cond = bool(req.condition)
    out.statistic = "conditional_mutual_information" if cond else "transfer_entropy"
    out.basis = (f"libs.research.information_flow.{out.statistic} (nats, miller-madow), "
                 + (f"null: {req.mode} x{req.n_perm} seed={req.seed}" if req.n_perm else "no null"))
    rest: tuple[list[float], ...]
    try:
        if cond:
            est = flow.conditional_mutual_information(list(req.source), list(req.target),
                                                      list(req.condition), bins=req.bins)
            stat_fn, rest = flow.conditional_mutual_information, (list(req.target),
                                                                  list(req.condition))
        else:
            est = flow.transfer_entropy(list(req.source), list(req.target), lag=req.lag,
                                        bins=req.bins)
            stat_fn, rest = flow.transfer_entropy, (list(req.target),)
        if req.n_perm > 0:
            sig = flow.significance(stat_fn, list(req.source), *rest, n_perm=req.n_perm,
                                    seed=req.seed, mode=req.mode, bins=req.bins)
            p = sig.get("p_value")
            out.p_value = None if p is None else float(p)
    except Exception as exc:
        out.why = f"{out.statistic} failed: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    out.value = None if est.value is None else float(est.value)
    out.n, out.bins = int(est.n), int(est.bins)
    out.status = OK if est.value is not None else UNMEASURED
    out.why = "" if est.value is not None else str(est.why)
    return _finish(verb, req, out, t0)


def factor_build(spec: FactorSpec) -> Factor:
    """A factor from the allowlisted DSL. `compile_factor` validates before touching data."""
    t0, verb = time.perf_counter(), "factor.build"
    miss = _missing(verb)
    out = Factor(name=spec.name, why=_why(miss))
    if miss:
        return _finish(verb, spec, out, t0)
    dsl = _mod("libs.research_os.dsl")
    bars = data_query(BarsRequest(symbol=spec.symbol, timeframe=spec.timeframe))
    out.basis = f"libs.research_os.dsl.compile_factor over {bars.basis or 'no chart'}"
    if bars.status != OK:
        out.why = f"no primary frame: {bars.why}"
        return _finish(verb, spec, out, t0)
    try:
        values = dsl.compile_factor(spec.tree, bars.frame)
        finite = values.notna() & (values == values)
    except Exception as exc:
        out.why = f"compile_factor refused: {type(exc).__name__}: {exc}"
        return _finish(verb, spec, out, t0)
    out.values, out.n, out.finite = values, len(values), int(finite.sum())
    out.digest = _digest(values)
    if out.finite:
        clean = values[finite]
        out.mean, out.std = round(float(clean.mean()), 12), round(float(clean.std()), 12)
    out.status, out.why = OK, ""
    return _finish(verb, spec, out, t0)



def alpha_backtest(spec: BacktestSpec) -> BacktestResult:
    """`mt5desk.engine.run_backtest` on the family's own signals, at `Costs.from_symbol`."""
    t0, verb = time.perf_counter(), "alpha.backtest"
    miss = _missing(verb)
    out = BacktestResult(symbol=spec.symbol, family=spec.family, why=_why(miss))
    if miss:
        return _finish(verb, spec, out, t0)
    engine, fams = _mod("mt5desk.engine"), _mod("mt5desk.families")
    call = _mod("mt5desk.family_call")
    bars = data_query(BarsRequest(symbol=spec.symbol, timeframe=spec.timeframe))
    if bars.status != OK:
        out.why = f"no chart: {bars.why}"
        return _finish(verb, spec, out, t0)
    fn = fams.get_family_func(spec.family)
    if fn is None:
        out.why = f"unknown family {spec.family!r} in mt5desk.families.get_family_func"
        return _finish(verb, spec, out, t0)
    try:
        meta = json.loads((UNIVERSE / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        meta = {}
    costs = engine.Costs.from_symbol(meta.get(spec.symbol, {}), mult=spec.cost_mult)
    out.basis = (f"mt5desk.engine.run_backtest; costs=Costs.from_symbol(universe.json"
                 f"[{spec.symbol}], mult={spec.cost_mult})"
                 f"{'' if meta else ' -- UNIVERSE META ABSENT, engine defaults used'}")
    try:
        params = {k: v for k, v in dict(spec.params).items() if k != "timeframe"}
        sigs = call.signals(fn, bars.frame, side=spec.side, params=params)
        res = engine.run_backtest(bars.frame, sigs, costs, spec.max_hold_bars)
        stats = res.stats()
    except Exception as exc:
        out.why = f"backtest failed: {type(exc).__name__}: {exc}"
        return _finish(verb, spec, out, t0)
    out.signals = len(sigs)
    out.per_trade_r = tuple(round(float(t.r_multiple), 12) for t in res.trades)
    out.n = int(stats.get("n", 0))
    out.expectancy = round(float(stats.get("expectancy_r", 0.0)), 12)
    out.t = round(float(stats.get("t_stat", 0.0)), 12)
    out.status, out.why = OK, ""
    return _finish(verb, spec, out, t0)


def execution_simulate(req: ExecutionSim) -> ExecutionResult:
    """One order against the twin's calibrated spread/slip/fill model. NOTHING IS SAMPLED: a
    fill probability is reported as a probability, because a coin flip is not replayable."""
    t0, verb = time.perf_counter(), "execution.simulate"
    miss = _missing(verb)
    out = ExecutionResult(symbol=req.symbol, latency_ms=req.latency_ms, why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    twin = _mod("libs.execution.digital_twin")
    try:
        sim = twin.SimCost(slip_frac=float(req.slip_frac or 0.0),
                           p_fill=1.0 if req.p_fill is None else float(req.p_fill),
                           spread_frac=req.spread_frac)
        out.session = str(twin.session_of(int(req.hour)))
        out.spread_bucket = str(twin.spread_bucket(req.spread_frac))
    except Exception as exc:
        out.why = f"twin refused: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    spread = float(sim.spread_frac or 0.0)
    out.slip_frac, out.p_fill = float(sim.slip_frac), float(sim.p_fill)
    out.spread_frac = sim.spread_frac
    out.cost_frac = round(spread + 2.0 * out.slip_frac, 12)
    side = 1 if int(req.side) >= 0 else -1
    if req.reference_price:
        out.fill_price = round(float(req.reference_price)
                               * (1.0 + side * (spread / 2.0 + out.slip_frac)), 12)
    out.filled = out.p_fill >= 1.0
    out.basis = ("libs.execution.digital_twin.SimCost (slip one-way, spread round-trip, p_fill) "
                 "-- the twin CALIBRATES these from live intents joined to live fills. LATENCY IS "
                 "ECHOED, NOT CHARGED: SimCost carries no latency term (the twin only MEASURES it, "
                 "latency_summary), and the desk's one latency-bearing fill model, "
                 "libs.backtest.queue_fill.maker_fill, is not reached from here")
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


def portfolio_evaluate(req: PortfolioEval) -> PortfolioResult:
    """The GIVEN book's growth on the world population. No optimisation, no reweighting."""
    t0, verb = time.perf_counter(), "portfolio.evaluate"
    miss = _missing(verb)
    out = PortfolioResult(why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    rel = _mod("libs.portfolio.robust_elog")
    out.basis = (f"libs.portfolio.robust_elog.score_book on WorldConfig(seed={req.seed}) "
                 "-- seeded, so identical input replays identically")
    try:
        import numpy as np
        ev = [rel.SleeveEvidence(name=str(n), daily_r=np.asarray(r, dtype=float),
                                 forward_days=int(req.forward_days.get(n, 0)))
              for n, r in sorted(req.returns.items())]
        if not ev:
            out.why = "no sleeve returns supplied"
            return _finish(verb, req, out, t0)
        cfg = rel.WorldConfig(seed=int(req.seed))
        score = rel.score_book(ev, dict(req.weights), cfg=cfg)
    except Exception as exc:
        out.why = f"score_book failed: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    def _g(key: str) -> float | None:
        v = score.get(key)
        return None if v is None else round(float(v), 12)

    out.n_sleeves = len(ev)
    out.total_heat = float(_g("total_heat") or 0.0)
    out.robust_score, out.mean_log_growth = _g("robust_score"), _g("mean_log_growth")
    out.cvar_log_growth, out.annual_growth_pct = _g("cvar_log_growth"), _g("annual_growth_pct")
    out.prob_annual_loss = _g("prob_annual_loss")
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


def gauntlet_run(req: GauntletRun) -> GauntletResult:
    """The ten gates, in process, through the sweep's own `run_gauntlet`. JUDGES, NEVER CERTIFIES:
    no authority file is written here and no certificate is minted."""
    t0, verb = time.perf_counter(), "gauntlet.run"
    miss = _missing(verb)
    out = GauntletResult(name=req.name, n_cells=len(req.cells), why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    eg = _mod("external_gauntlet")
    out.basis = ("external_gauntlet.build_cell + run_gauntlet (ten gates, in process). NO "
                 "certificate and no authority file is written. The sweep exposes no in-process "
                 "time budget, so `budget_s` is deliberately not a field here")
    try:
        meta = json.loads((UNIVERSE / "universe.json").read_text("utf-8"))
        cells = [eg.build_cell(str(c.get("symbol")), str(c.get("family")),
                               dict(c.get("params") or {}), meta) for c in req.cells]
        built = [c for c in cells if c is not None]
        out.n_built = len(built)
        if not built:
            out.why = "build_cell refused every cell (absent chart, unknown family, or bad params)"
            return _finish(verb, req, out, t0)
        doc = eg.run_gauntlet(built, req.name, meta)
    except Exception as exc:
        out.why = f"gauntlet failed: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    if doc.get("error"):
        out.why = str(doc["error"])
        return _finish(verb, req, out, t0)
    out.n_judged, out.n_unmeasured = int(doc.get("n_judged", 0)), int(doc.get("n_unmeasured", 0))
    out.survivors = int(doc.get("survivors_passing_all", 0))
    out.n_trials = int(doc.get("n_trials", 0))
    out.verdicts = tuple({k: v.get(k) for k in ("cell", "sym", "family", "days", "passed",
                                                "unmeasured")}
                         for v in doc.get("verdicts", []))
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


def forward_register(req: ForwardRegistration) -> ForwardReceipt:
    """FILE A REQUEST -- this enrols nothing and grants nothing.

    `shadow_admission` DERIVES the forward population from certificates in `reports/` and exposes
    no register/enrol entry point (`authorized_specs` reads, it does not admit), so the honest
    surface is a queue: one row appended to `data/forward_register_requests.jsonl`. NO ORGAN
    READS THAT FILE TODAY. `queued: True` means a row was written and NOTHING MORE (III.16) --
    a reader is owed work, and this docstring is where the debt is recorded.
    """
    t0, verb = time.perf_counter(), "forward.register"
    miss = _missing(verb)
    out = ForwardReceipt(symbol=req.symbol, family=req.family, path=str(FORWARD_REQUESTS),
                         why=_why(miss), request_hash=hash_of(req))
    if miss:
        return _finish(verb, req, out, t0)
    adm = _mod("research.shadow_admission")
    out.basis = ("appended to data/forward_register_requests.jsonl; membership checked against "
                 "research.shadow_admission.authorized_runs. NO ORGAN CONSUMES THIS QUEUE YET")
    try:
        out.already_authorized = any(
            str(r.get("symbol", "")).upper() == req.symbol.upper()
            and str(r.get("family", "")) == req.family for r in adm.authorized_runs())
    except Exception as exc:
        out.why = f"authorized_runs unreadable: {type(exc).__name__}: {exc}"
    row = {"at": datetime.now(UTC).isoformat(), "request_hash": out.request_hash,
           "symbol": req.symbol, "family": req.family, "params": dict(req.params),
           "side": req.side, "timeframe": req.timeframe, "certificate": req.certificate,
           "note": req.note, "already_authorized": out.already_authorized,
           "enrolled": False, "source": "libs.research.research_api"}
    try:
        FORWARD_REQUESTS.parent.mkdir(parents=True, exist_ok=True)
        with FORWARD_REQUESTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        out.queued, out.status = True, OK
    except OSError as exc:
        out.why = f"queue unwritable: {exc}"
    return _finish(verb, req, out, t0)


def evidence_lookup(req: EvidenceQuery) -> EvidenceHits:
    """What the desk already knows. Four modes, all delegated, none of them a new opinion."""
    t0, verb = time.perf_counter(), "evidence.lookup"
    miss = _missing(verb)
    out = EvidenceHits(mode=req.mode, why=_why(miss))
    if miss:
        return _finish(verb, req, out, t0)
    sem = _mod("research.semantic_memory")
    graph = _mod("libs.research.hypothesis_graph")
    out.basis = (f"research.semantic_memory.Memory.{req.mode} + "
                 "libs.research.hypothesis_graph.Graph.prior_failures")
    if req.mode == "prior_failures":
        try:
            prior = graph.Graph().prior_failures(req.symbol, req.family, dict(req.params))
        except Exception as exc:
            out.why = f"hypothesis_graph unreadable: {type(exc).__name__}: {exc}"
            return _finish(verb, req, out, t0)
        out.prior_failures = dict(prior)
        out.n = int(prior.get("n_failed", 0))
        out.status, out.why = OK, ""
        return _finish(verb, req, out, t0)
    try:
        mem = sem.Memory.load()
        if req.mode == "similar_failures":
            hits = mem.similar_failures(req.text or dict(req.params), k=req.k)
        elif req.mode == "redundant_with":
            hits = mem.redundant_with(dict(req.params), k=req.k)
        else:
            hits = mem.query(req.text, k=req.k, kinds=req.kinds or None,
                             symbol=req.symbol or None, family=req.family or None)
    except Exception as exc:
        out.why = f"semantic index unavailable: {type(exc).__name__}: {exc}"
        return _finish(verb, req, out, t0)
    out.hits = tuple({"doc_id": str(h.doc_id), "kind": str(h.kind), "score": float(h.score),
                      "meta": dict(h.meta)} for h in hits)
    out.n = len(out.hits)
    out.status, out.why = OK, ""
    return _finish(verb, req, out, t0)


VERB_FNS: dict[str, Callable[[Any], Any]] = {
    "data.query": data_query, "event.query": event_query, "macro.query": macro_query,
    "causal.test": causal_test, "factor.build": factor_build, "alpha.backtest": alpha_backtest,
    "execution.simulate": execution_simulate, "portfolio.evaluate": portfolio_evaluate,
    "gauntlet.run": gauntlet_run, "forward.register": forward_register,
    "evidence.lookup": evidence_lookup,
}


def call(verb: str, request: Any) -> Any:
    """Dispatch by name, so an organ can be configured with a verb rather than an import."""
    fn = VERB_FNS.get(verb)
    if fn is None:
        raise KeyError(f"no such verb: {verb!r}; the eleven are {list(VERBS)}")
    return fn(request)


def verbs() -> dict[str, Any]:
    """The API's own coverage, MEASURED -- which verbs can actually reach their organ today.

    This is what the wiring audit reads. A verb whose delegate is unavailable is not a gap in
    the caller's code: it is a capability this box does not currently have, and it is named."""
    rows: dict[str, Any] = {}
    for verb, mods in DELEGATES.items():
        gone = _missing(verb)
        rows[verb] = {"delegates": list(mods), "missing": gone,
                      "status": "unavailable" if gone else "available"}
    avail = sum(1 for r in rows.values() if r["status"] == "available")
    return {"at": datetime.now(UTC).isoformat(), "n_verbs": len(rows), "available": avail,
            "unavailable": len(rows) - avail, "call_log": str(CALL_LOG), "verbs": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The desk's one typed, deterministic research API.")
    ap.add_argument("command", choices=["status"], help="status: the eleven verbs and their "
                                                        "delegate availability")
    ap.add_argument("--json", action="store_true", help="emit the status document")
    args = ap.parse_args(argv)
    doc = verbs()
    if args.json:
        print(json.dumps(doc, indent=1, sort_keys=True))
        return 0
    print(f"research API: {doc['available']}/{doc['n_verbs']} verbs reach their delegate")
    for verb, row in doc["verbs"].items():
        mark = "ok " if row["status"] == "available" else "-- "
        note = f"MISSING {', '.join(row['missing'])}" if row["missing"] else row["delegates"][0]
        print(f"  {mark}{verb:20s} {note}")
    print(f"call log: {doc['call_log']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
