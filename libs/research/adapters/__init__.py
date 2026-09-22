"""THE ADAPTERS -- one per federated system, each turning an upstream research engine's native
output into an ExternalResearchPacket over a READ-ONLY ResearchBundle (LAWS 5h, 5m).

WHAT AN ADAPTER IS. `run(bundle: ResearchBundle) -> ExternalResearchPacket`, executed INSIDE the
system's sandbox (`python -m libs.research.adapters.<system> --bundle <path> --out <path>`) by
`desks/mt5/research/sandbox_runner.py`, never inside the desk process. The bundle is a COPY of a
few bar frames, axis series with their available_time, the cost surface, a research question, a
compute budget, a seed and the allowed horizons -- written into the sandbox work directory,
never mounted. The packet is the ONLY exit: candidates, representations, mechanisms, research
methods and datasets with provenance and the real search burden (`trials_charged` counts every
parameter the engine evaluated). A verdict-shaped field raises at the contract, here and again
at the desk's boundary, so an upstream engine can donate a hypothesis and never a survivor.

WHAT AN ADAPTER IS NOT. It is not a validator (no Sharpe, no pass, no rank has authority), not a
sizer (riskfolio donates allocation EVIDENCE, never a size), and not a mount: it reads only what
the bundle carries. A library that is absent in the environment is reported UNMEASURED by name
in the packet's research_methods rather than raised, because "the engine did not run" is a
measurement the federation ledger needs and a stack trace is not.

THIS MODULE IS IMPORT-LIGHT ON PURPOSE. It is copied into every sandbox together with the packet
contract, so it may import the standard library and the contract and nothing else at module
scope; numpy is imported lazily because every federated engine already depends on it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import random
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research.external_federation import PACKET_FORBIDDEN, ExternalResearchPacket

#: A candidate row that names a registered price-only family compiles as STRUCTURED_HYPOTHESIS
#: in `miner_candidate_compiler` (family defaults, declared instruments). Adapters name ONLY
#: these; a family outside the vocabulary would be read as prose and lose its instrument.
FAMILIES: tuple[str, ...] = (
    "failed_breakout", "level_breakout", "overnight_drift", "mean_reversion_rsi",
    "mean_reversion_bollinger", "volatility_squeeze", "trend_ma_cross", "momentum_volgate",
    "range_reversion", "volume_spike", "pullback_entry", "vol_mean_reversion", "vol_transition",
    "drawdown_conditional", "spread_state",
)


@dataclass(frozen=True)
class Spec:
    """Where a system is distributed, at which measured pin, and what its adapter yields."""

    system_id: str
    distribution: str
    version: str
    module: str
    weight: str = "light"
    yields: tuple[str, ...] = ()
    note: str = ""

    @property
    def requirement(self) -> str:
        return f"{self.distribution}=={self.version}" if self.version else self.distribution


#: THE FIRST ADAPTERS. Pins are the versions `pip download --only-binary :all:` resolved on this
#: desk's interpreter (CPython 3.14, 2026-09-22) -- measured installable wheels, not remembered
#: release numbers. `weight="heavy"` marks a torch dependency (hundreds of MB; provisioned last).
SPECS: dict[str, Spec] = {s.system_id: s for s in (
    Spec("ruptures", "ruptures", "1.0.6", "ruptures", yields=("representations", "candidates"),
         note="1.1.x ships no wheel for this interpreter; 1.0.6 is the pure-python build"),
    Spec("stumpy", "stumpy", "1.14.1", "stumpy", yields=("representations", "candidates")),
    Spec("pysindy", "pysindy", "2.1.0", "pysindy", yields=("mechanisms",)),
    Spec("pydmd", "pydmd", "2025.8.1", "pydmd", yields=("representations",)),
    Spec("tsfresh", "tsfresh", "0.21.2", "tsfresh", yields=("representations",)),
    Spec("riskfolio", "Riskfolio-Lib", "7.3.0", "riskfolio", yields=("research_methods",),
         note="allocator CHALLENGER: allocation evidence, never a size"),
    Spec("pymoo", "pymoo", "0.6.2", "pymoo", yields=("candidates", "research_methods")),
    Spec("nevergrad", "nevergrad", "1.0.12", "nevergrad", yields=("candidates",)),
    Spec("botorch", "botorch", "0.18.1", "botorch", weight="heavy",
         yields=("research_methods", "candidates")),
    Spec("river", "river", "0.26.1", "river", yields=("representations",)),
    Spec("mapie", "mapie", "1.5.0", "mapie", yields=("representations",)),
    Spec("tensorly", "tensorly", "0.9.0", "tensorly", yields=("representations",)),
    Spec("pyrqa", "PyRQA", "", "pyrqa", yields=("representations",),
         note="sdist-only on PyPI and OpenCL-backed; provisioning measures whether it installs"),
    Spec("pgmpy", "pgmpy", "1.1.2", "pgmpy", weight="heavy", yields=("mechanisms",)),
    Spec("pyextremes", "pyextremes", "2.5.0", "pyextremes",
         yields=("representations", "candidates")),
    Spec("scikit_mine", "scikit-mine", "1.0.0", "skmine",
         yields=("representations", "candidates")),
    Spec("tslearn", "tslearn", "0.9.0", "tslearn", yields=("representations", "candidates")),
    Spec("pyvinecopulib", "pyvinecopulib", "1.0.0", "pyvinecopulib", yields=("representations",)),
    Spec("roughpy", "roughpy", "0.3.0", "roughpy", yields=("representations",)),
)}


# ------------------------------------------------------------------------------- the bundle

@dataclass(frozen=True)
class BarFrame:
    """One symbol's bars at one timeframe, as immutable columns (UTC ISO times)."""

    symbol: str
    timeframe: str
    time: tuple[str, ...]
    open: tuple[float, ...]
    high: tuple[float, ...]
    low: tuple[float, ...]
    close: tuple[float, ...]
    volume: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.time)

    @property
    def key(self) -> str:
        return f"{self.symbol}_{self.timeframe}"

    def log_returns(self) -> Any:
        import numpy as np
        c = np.asarray(self.close, dtype=float)
        return np.diff(np.log(np.maximum(c, 1e-12)))


@dataclass(frozen=True)
class AxisSeries:
    """A point-in-time axis: (available_time, value) points and the stamp's own basis."""

    axis: str
    series: str
    points: tuple[tuple[str, float], ...]
    available_time: str
    basis: str = ""


@dataclass(frozen=True)
class CostRow:
    """The cost surface for one symbol: spread by hour in points, tick and contract size."""

    symbol: str
    tick_size: float
    contract_size: float
    pooled_median_spread_pts: float
    spread_pts_p50_by_hour: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchBundle:
    """Everything an adapter may read, copied into the sandbox. Frozen: a bundle is never edited,
    and an engine that wants more data asks the runner for a different bundle."""

    bundle_id: str
    built_at: str
    question: str
    compute_budget_s: int
    seed: int
    horizons: tuple[str, ...]
    universe: tuple[str, ...]
    bars: Mapping[str, BarFrame] = field(default_factory=dict)
    axes: Mapping[str, AxisSeries] = field(default_factory=dict)
    costs: Mapping[str, CostRow] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True

    def frames(self, timeframe: str = "H1") -> list[BarFrame]:
        return [f for f in self.bars.values() if f.timeframe == timeframe]

    def frame(self, symbol: str, timeframe: str = "H1") -> BarFrame | None:
        return self.bars.get(f"{symbol}_{timeframe}")

    def watermark(self) -> str:
        """The newest bar time across frames -- the monotonic progress mark of a run."""
        return max((f.time[-1] for f in self.bars.values() if f.time), default="")

    def cost_pts(self, symbol: str) -> float:
        row = self.costs.get(symbol)
        return float(row.pooled_median_spread_pts) if row else float("nan")

    def digest(self) -> str:
        h = hashlib.sha256()
        for key in sorted(self.bars):
            f = self.bars[key]
            h.update(key.encode())
            h.update(str(len(f)).encode())
            h.update((f.time[-1] if f.time else "").encode())
            h.update(repr(f.close[-3:]).encode())
        h.update(json.dumps(sorted(self.axes)).encode())
        h.update(str(self.seed).encode())
        return h.hexdigest()[:16]


def write_bundle(bundle: ResearchBundle, directory: Path) -> Path:
    """Write the bundle as `bundle.json` + `bars/<key>.csv` under `directory`; return the manifest.
    CSV so a sandbox with numpy alone can read it; nothing here needs pandas or pyarrow."""
    directory.mkdir(parents=True, exist_ok=True)
    bars_dir = directory / "bars"
    bars_dir.mkdir(exist_ok=True)
    files: dict[str, str] = {}
    for key, f in bundle.bars.items():
        p = bars_dir / f"{key}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "open", "high", "low", "close", "volume"])
            for i in range(len(f)):
                w.writerow([f.time[i], f.open[i], f.high[i], f.low[i], f.close[i], f.volume[i]])
        files[key] = f"bars/{key}.csv"
    doc = {
        "bundle_id": bundle.bundle_id, "built_at": bundle.built_at, "question": bundle.question,
        "compute_budget_s": bundle.compute_budget_s, "seed": bundle.seed,
        "horizons": list(bundle.horizons), "universe": list(bundle.universe),
        "bars": {k: {"symbol": f.symbol, "timeframe": f.timeframe, "file": files[k],
                     "n": len(f)} for k, f in bundle.bars.items()},
        "axes": {k: asdict(a) for k, a in bundle.axes.items()},
        "costs": {k: {**asdict(c), "spread_pts_p50_by_hour": dict(c.spread_pts_p50_by_hour)}
                  for k, c in bundle.costs.items()},
        "provenance": dict(bundle.provenance), "read_only": True,
        "digest": bundle.digest(),
    }
    manifest = directory / "bundle.json"
    tmp = manifest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, manifest)
    return manifest


def load_bundle(path: Path) -> ResearchBundle:
    """Read a manifest written by `write_bundle` (paths resolve relative to the manifest)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    base = Path(path).parent
    bars: dict[str, BarFrame] = {}
    for key, meta in (doc.get("bars") or {}).items():
        cols: dict[str, list[Any]] = {c: [] for c in ("time", "open", "high", "low", "close",
                                                       "volume")}
        with (base / meta["file"]).open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cols["time"].append(str(row["time"]))
                for c in ("open", "high", "low", "close", "volume"):
                    cols[c].append(float(row[c]))
        bars[key] = BarFrame(str(meta["symbol"]), str(meta["timeframe"]), tuple(cols["time"]),
                             tuple(cols["open"]), tuple(cols["high"]), tuple(cols["low"]),
                             tuple(cols["close"]), tuple(cols["volume"]))
    axes = {k: AxisSeries(str(a["axis"]), str(a["series"]),
                          tuple((str(t), float(v)) for t, v in a.get("points") or ()),
                          str(a.get("available_time") or ""), str(a.get("basis") or ""))
            for k, a in (doc.get("axes") or {}).items()}
    costs = {k: CostRow(str(c["symbol"]), float(c.get("tick_size") or 0.0),
                        float(c.get("contract_size") or 0.0),
                        float(c.get("pooled_median_spread_pts") or float("nan")),
                        {str(h): float(v) for h, v in (c.get("spread_pts_p50_by_hour")
                                                        or {}).items()})
             for k, c in (doc.get("costs") or {}).items()}
    return ResearchBundle(
        bundle_id=str(doc.get("bundle_id") or "UNMEASURED"),
        built_at=str(doc.get("built_at") or ""), question=str(doc.get("question") or ""),
        compute_budget_s=int(doc.get("compute_budget_s") or 300),
        seed=int(doc.get("seed") or 0), horizons=tuple(doc.get("horizons") or ("24h",)),
        universe=tuple(doc.get("universe") or ()), bars=bars, axes=axes, costs=costs,
        provenance=dict(doc.get("provenance") or {}))


def synthetic_bundle(*, seed: int = 0, n: int = 600,
                     symbols: Sequence[str] = ("XAUUSD", "EURUSD", "USDJPY"),
                     timeframe: str = "H1", budget_s: int = 60) -> ResearchBundle:
    """Planted random-walk bars with a volatility break half way -- for tests and dry runs.
    Nothing in it is market data; a packet built on it is a shape test, never evidence."""
    rng = random.Random(seed)  # noqa: S311 -- planted bars, never a secret
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    step = {"H1": timedelta(hours=1), "M5": timedelta(minutes=5)}.get(timeframe,
                                                                     timedelta(hours=1))
    bars: dict[str, BarFrame] = {}
    for si, sym in enumerate(symbols):
        px = 100.0 * (si + 1)
        t, o, h, lo, c, v = [], [], [], [], [], []
        for i in range(n):
            vol = 0.002 if i < n // 2 else 0.006
            r = rng.gauss(0.0, vol) + (0.0004 * math.sin(i / 37.0))
            nxt = px * math.exp(r)
            hi = max(px, nxt) * (1 + abs(rng.gauss(0, vol / 2)))
            lw = min(px, nxt) * (1 - abs(rng.gauss(0, vol / 2)))
            t.append((t0 + i * step).isoformat())
            o.append(px)
            h.append(hi)
            lo.append(lw)
            c.append(nxt)
            v.append(float(rng.randint(100, 1000)))
            px = nxt
        bars[f"{sym}_{timeframe}"] = BarFrame(sym, timeframe, tuple(t), tuple(o), tuple(h),
                                              tuple(lo), tuple(c), tuple(v))
    axes = {"shadow_usd_liquidity.index": AxisSeries(
        "shadow_usd_liquidity", "index",
        tuple(((t0 + timedelta(days=d)).date().isoformat(), math.sin(d / 9.0))
              for d in range(0, n // 24 + 1)),
        (t0 + timedelta(days=n // 24)).date().isoformat(), "synthetic")}
    costs = {s: CostRow(s, 0.01, 100.0, 15.0, {str(hh): 15.0 + (hh % 5) for hh in range(24)})
             for s in symbols}
    return ResearchBundle(bundle_id=f"synthetic-{seed}", built_at=t0.isoformat(),
                          question="shape test on planted bars", compute_budget_s=budget_s,
                          seed=seed, horizons=("4h", "24h"), universe=tuple(symbols), bars=bars,
                          axes=axes, costs=costs, provenance={"synthetic": True})


# ------------------------------------------------------------------------------- the packet

class Deadline:
    """The compute budget, checked between parameter evaluations so an engine stops honestly and
    charges exactly what it evaluated."""

    def __init__(self, seconds: float) -> None:
        self.t0 = time.monotonic()
        self.seconds = float(seconds)

    def left(self) -> float:
        return self.seconds - (time.monotonic() - self.t0)

    def expired(self) -> bool:
        return self.left() <= 0


def library(name: str) -> Any | None:
    """The upstream module, or None when it is not importable here (reported, never raised)."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def commit_of(system_id: str) -> str:
    """The exact upstream revision this environment runs: `pypi:<dist>==<installed version>`."""
    spec = SPECS.get(system_id)
    if spec is None:
        return "UNMEASURED"
    try:
        return f"pypi:{spec.distribution}=={importlib.metadata.version(spec.distribution)}"
    except importlib.metadata.PackageNotFoundError:
        return f"pypi:{spec.distribution}==UNMEASURED"


def run_id_for(system_id: str, bundle: ResearchBundle) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{system_id}-{bundle.digest()}-{stamp}"


def py(value: Any) -> Any:
    """JSON-safe: numpy scalars/arrays to python, NaN/inf to None, tuples to lists."""
    if hasattr(value, "tolist"):
        return py(value.tolist())
    if isinstance(value, dict):
        return {str(k): py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [py(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def clean(row: Mapping[str, Any]) -> dict[str, Any]:
    """A packet row: JSON-safe and free of verdict-shaped keys (raises, at the source)."""
    hits = sorted(k for k in row if str(k).lower() in PACKET_FORBIDDEN)
    if hits:
        raise ValueError(f"adapter row carries verdict-shaped fields {hits}: an external engine "
                         f"is a researcher, never a validator (LAWS 5h)")
    return {str(k): py(v) for k, v in row.items()}


def candidate(family: str, symbols: Iterable[str], text: str, *, horizon: str,
              evidence: Mapping[str, Any], source: str) -> dict[str, Any]:
    """A STRUCTURED_HYPOTHESIS row: a registered family named outright, declared instruments,
    the engine's evidence riding along. The gauntlet judges; nothing here does."""
    if family not in FAMILIES:
        raise ValueError(f"{family!r} is not a registered price-only family: {FAMILIES}")
    return clean({"kind": "hypothesis", "family": family, "symbols": sorted(set(symbols)),
                  "text": text, "horizon": horizon, "evidence": dict(evidence),
                  "source": source, "authority": "none: a hypothesis for the ten gates"})


def packet(system_id: str, bundle: ResearchBundle, *, trials: int,
           candidates: Sequence[Mapping[str, Any]] = (),
           representations: Sequence[Mapping[str, Any]] = (),
           mechanisms: Sequence[Mapping[str, Any]] = (),
           research_methods: Sequence[Mapping[str, Any]] = (),
           datasets: Sequence[Mapping[str, Any]] = (),
           note: str = "") -> ExternalResearchPacket:
    """Build the packet through the contract: every row cleaned, every trial charged."""
    return ExternalResearchPacket(
        system_id=system_id, run_id=run_id_for(system_id, bundle), commit=commit_of(system_id),
        candidates=tuple(clean(r) for r in candidates),
        datasets=tuple(clean(r) for r in datasets),
        mechanisms=tuple(clean(r) for r in mechanisms),
        representations=tuple(clean(r) for r in representations),
        research_methods=tuple(clean(r) for r in research_methods),
        trials_charged=int(trials),
        provenance={"bundle_id": bundle.bundle_id, "bundle_digest": bundle.digest(),
                    "watermark": bundle.watermark(), "seed": bundle.seed,
                    "question": bundle.question, "note": note,
                    "produced_at": datetime.now(tz=UTC).isoformat(timespec="seconds")})


def unmeasured(system_id: str, bundle: ResearchBundle, why: str) -> ExternalResearchPacket:
    """The engine did not run: a packet that says so BY NAME, with zero trials charged."""
    return packet(system_id, bundle, trials=0,
                  research_methods=({"kind": "UNMEASURED", "system": system_id, "why": why},),
                  note="UNMEASURED")


def is_unmeasured(p: ExternalResearchPacket) -> bool:
    return (p.empty() or (all(str(r.get("kind")) == "UNMEASURED" for r in p.research_methods)
            and not (p.candidates or p.representations or p.mechanisms or p.datasets)))


def to_dict(p: ExternalResearchPacket) -> dict[str, Any]:
    return {"system_id": p.system_id, "run_id": p.run_id, "commit": p.commit,
            "candidates": list(p.candidates), "datasets": list(p.datasets),
            "mechanisms": list(p.mechanisms), "representations": list(p.representations),
            "research_methods": list(p.research_methods), "trials_charged": p.trials_charged,
            "provenance": dict(p.provenance), "counts": p.counts()}


def cli(run: Callable[[ResearchBundle], ExternalResearchPacket], system_id: str,
        argv: Sequence[str] | None = None) -> int:
    """`--bundle <manifest> --out <packet.json>`: the entry point the sandbox runner invokes.
    An adapter that raises still leaves a packet -- UNMEASURED with the failure named -- and
    exits 3, so the runner records RUN_FAILED with a reason instead of an empty out/ directory."""
    ap = argparse.ArgumentParser(description=f"{system_id} adapter (LAWS 5h sandbox worker)")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv) if argv is not None else None)
    bundle = load_bundle(Path(a.bundle))
    code = 0
    try:
        result = run(bundle)
    except Exception:
        tail = traceback.format_exc().strip().splitlines()[-3:]
        result = unmeasured(system_id, bundle, "adapter raised: " + " | ".join(tail)[:600])
        code = 3
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(to_dict(result), indent=1, default=str), encoding="utf-8")
    os.replace(tmp, out)
    sys.stdout.write(f"{system_id}: {result.counts()} -> {out}\n")
    return code


# ------------------------------------------------------------------------------- shared maths

def realised_vol(rets: Any, window: int) -> Any:
    """Rolling standard deviation of returns (trailing, NaN-padded), numpy only."""
    import numpy as np
    r = np.asarray(rets, dtype=float)
    out = np.full(r.shape[0], np.nan)
    if r.shape[0] >= window:
        c = np.cumsum(np.insert(r, 0, 0.0))
        c2 = np.cumsum(np.insert(r * r, 0, 0.0))
        mean = (c[window:] - c[:-window]) / window
        var = (c2[window:] - c2[:-window]) / window - mean * mean
        out[window - 1:] = np.sqrt(np.maximum(var, 0.0))
    return out


def ma_cross_objective(frame: BarFrame, fast: int, slow: int, cost_pts: float,
                       tick: float) -> dict[str, float]:
    """The objective the parameter-search engines share: a moving-average cross over the frame,
    charged the bundle's own spread. Returns EVIDENCE fields (objective_return,
    objective_drawdown, n_trades) -- names chosen so nothing here reads as a verdict."""
    import numpy as np
    c = np.asarray(frame.close, dtype=float)
    fast, slow = int(max(2, fast)), int(max(3, slow))
    if slow <= fast or c.shape[0] <= slow + 2:
        return {"objective_return": 0.0, "objective_drawdown": 0.0, "n_trades": 0.0}
    k_f = np.convolve(c, np.ones(fast) / fast, mode="valid")
    k_s = np.convolve(c, np.ones(slow) / slow, mode="valid")
    k_f = k_f[slow - fast:]
    pos = np.where(k_f > k_s, 1.0, -1.0)
    px = c[slow - 1:]
    rets = np.diff(np.log(np.maximum(px, 1e-12)))
    pnl = pos[:-1] * rets
    flips = np.abs(np.diff(pos)) > 0
    cost = (cost_pts * tick / np.maximum(px[1:], 1e-12)) if np.isfinite(cost_pts) else 0.0
    pnl = pnl - flips * cost
    eq = np.cumsum(pnl)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size else 0.0
    return {"objective_return": float(eq[-1]) if eq.size else 0.0, "objective_drawdown": dd,
            "n_trades": float(flips.sum())}
