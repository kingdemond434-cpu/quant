"""THE AI MATHEMATICS RESEARCH CIVILIZATION, as an organ on a clock.

ONE PASS: build the panel from what the world model could NOT explain, hand it to fourteen
parallel mathematical traditions with a two-sided compute share each, charge every search its own
multiple-testing burden, register what survives in the canonical registry, donate the executable
ones to the SAME compiler every other miner uses, publish the invented state variables as
representations, and send per-tradition ROI back to the allocation file so next hour's compute
follows the evidence.

WHERE THE RESIDUAL COMES FROM, IN ORDER, AND NEVER IDLE:

  1. `data/world_model/residuals_<horizon>.parquet` -- the world model's out-of-sample epsilon,
     the thing this whole department exists to attack, joined to the residual-hunt targets
     (registry discoveries of kind `residual_target`) so an object can name the cluster it
     answers.
  2. `research/shadow_discovery.fit_epsilon` -- the live book's own factor residual, when the
     store is absent.
  3. A BAR BASELINE built here: the forward return less a ridge forecast from lagged returns and
     dispersion, fitted on the first 60% of the history. Named `bar_baseline` in every artifact so
     nobody reads it as the world model's residual.

  An organ that idles because its upstream has not run yet is a dark organ (L III.16), and an
  organ that pretends a fallback is the real input is worse. Both are refused here: the ladder
  always produces a panel, and the panel always says which rung produced it.

WHAT IS AND IS NOT DECIDED HERE. Nothing is certified and no capital is allocated. Objects that
clear the search-burden screen become candidates in `data/intelligence/mathlab/` and meet the ten
gates in `scripts/external_gauntlet.py` with every other hypothesis; the desk's sealed trial charge
is untouched. What is recorded here is the SEARCH SIZE, in the registry's hash-chained trials
ledger, because a search whose size nobody wrote down is a search whose results nobody can price.

CREDIT GOES BACK TO THE MATHEMATICAL METHOD. `generator_yield` carries one row per tradition
(`math:<tradition>`); `research_roi` already reads that table as SCIENTIST ROI, so a tradition
whose objects become forward survivors earns compute and one whose objects die loses it --
two-sided, with a 2% floor so no tradition ever goes silent and stops being able to detect that
conditions changed.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import burden as B  # noqa: E402
from research.mathlab import engines as E  # noqa: E402
from research.mathlab import grammar as G  # noqa: E402
from research.mathlab import institution as I  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402
from research.mathlab.objects import REGISTRY_KIND, MathObject, Panel, Variable  # noqa: E402
from research.mathlab.physics import PHYSICS_CORE_REGISTRY  # noqa: E402
from research.mathlab.physics_ext import PHYSICS_EXT_REGISTRY  # noqa: E402

DATA = DESK / "data"
UNIVERSE = DATA / "universe"
AXES = DATA / "axes"
REPRESENTATIONS = DATA / "representations"
MATHLAB_REPRESENTATIONS = REPRESENTATIONS / "mathlab"
ALLOCATION = DATA / "math_allocation.json"
DONATED = DATA / "mathlab_donated.json"
OUT = DESK / "reports" / "MATH_LAB.json"
SOURCE = "mathlab"

#: THE PHYSICS WING (2026-09-22): nineteen physical traditions run beside the twenty-eight
#: mathematical ones, inside this leg's budget, as their own DEPARTMENT. The department split
#: is two-sided by measured ROI with a floor (`engines.distributed_science`), and the share
#: allocation inside each department is the same two-sided rule as before.
PHYSICS_REGISTRY: dict[str, type[Any]] = {**PHYSICS_CORE_REGISTRY, **PHYSICS_EXT_REGISTRY}
PHYSICS_TRADITIONS: tuple[str, ...] = tuple(PHYSICS_REGISTRY)
#: The engines' slice of the pass budget (law discovery, model competition, MDL, primitive
#: invention, ... on the first panel with this pass's admitted objects).
ENGINE_SHARE = 0.08

SEED = 20260917
#: Compute share floor per tradition. Two-sided above it; never zero, so a tradition that stops
#: earning can still notice when the market changes back (LAWS 5f: always keep a scout).
FLOOR_SHARE = 0.02
#: Targets per pass. The panel build is the expensive part; the scientists are bounded by budget.
MAX_TARGETS = 4
MAX_PEERS = 10
MAX_DATASET_COLUMNS = 12
MAX_REPRESENTATION_COLUMNS = 8
MAX_DONATIONS = 40
#: Derived worker cap, exactly as `miner_candidate_compiler` derives its row cap: from memory
#: ACTUALLY FREE, floored, so an unreadable counter changes nothing.
WORKER_FLOOR = 2
BYTES_PER_WORKER = 300 * 2 ** 20
FREE_MEMORY_SHARE = 0.25
UNMEASURED = "UNMEASURED"

RULE = ("fourteen mathematical traditions attack the world model's residual in parallel; every "
        "object carries its own search burden (held-out evidence - MDL - sqrt(2 ln effective "
        "trials)); survivors go to the desk's own gauntlet, never a private one; credit returns "
        "to the tradition through generator_yield and the compute share moves with it")


# ------------------------------------------------------------------------------- plumbing
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _free_phys_bytes() -> int | None:
    """Free physical memory, measured. None when the counter cannot be read on this box."""
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
            return None
        return int(st.ullAvailPhys)
    except Exception:
        try:
            text = Path("/proc/meminfo").read_text(encoding="utf-8")
            kb = next(int(ln.split()[1]) for ln in text.splitlines()
                      if ln.startswith("MemAvailable:"))
            return kb * 1024
        except Exception:
            return None


def max_workers() -> tuple[int, dict[str, Any]]:
    """Parallel scientists, DERIVED from measured free memory rather than from a constant.

    The box that runs this holds the live terminal. A worker count sized for a 96 GB machine
    thrashes an 8 GB one, and the repo's own standing note about which box is which was wrong for
    three days -- so the number is measured here, floored at two, and reported with its evidence.
    """
    free = _free_phys_bytes()
    cpus = os.cpu_count() or 2
    if free is None:
        return WORKER_FLOOR, {"status": UNMEASURED, "why": "free physical memory unreadable",
                              "workers": WORKER_FLOOR, "cpus": cpus}
    allowed = int(free * FREE_MEMORY_SHARE / BYTES_PER_WORKER)
    workers = max(WORKER_FLOOR, min(cpus, allowed))
    return workers, {"status": "MEASURED", "free_phys_mb": round(free / 2 ** 20, 1),
                     "share": FREE_MEMORY_SHARE, "mb_per_worker": BYTES_PER_WORKER // 2 ** 20,
                     "allowed": allowed, "cpus": cpus, "workers": workers}


# ------------------------------------------------------------------------------- the panel
def hypothesis_universe() -> tuple[list[str], dict[str, Any]]:
    """Symbols the hypothesis lane may be hunted on, by ASSET CLASS, never by a symbol list."""
    status: dict[str, Any] = {"policy": "desks/mt5/research/universe_policy.py"}
    symbols = sorted(p.name[:-len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet"))
    try:
        from research.universe_policy import may_hypothesise
    except Exception as exc:
        status["status"] = UNMEASURED
        status["why"] = f"universe_policy unimportable: {type(exc).__name__}; no symbol is hunted"
        return [], status
    allowed = [s for s in symbols if may_hypothesise(s)]
    status.update({"status": "MEASURED", "with_bars": len(symbols), "hypothesis_lane": len(allowed),
                   "set_aside": len(symbols) - len(allowed),
                   "why": "single-name equities are traded in the event lane and never hunted "
                          "for statistical hypotheses (principal 2026-09-06)"})
    return allowed, status


def bar_frames(symbol: str) -> tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]] | None:
    """The desk's bar terminals for one symbol, in `alpha_grammar`'s own names and definitions.

    THE SAME FRAMES THE FAMILY WILL SEE. `mt5desk.family_formula` evaluates a donated expression
    through `alpha_grammar.terminal_frames`; building the panel from the same function is what
    makes the evidence measured here evidence about the thing that will actually be traded.
    """
    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd

        from libs.research.alpha_grammar import terminal_frames
        frame = pd.read_parquet(path)
        if frame.empty or "close" not in frame.columns:
            return None
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~frame.index.isna()].sort_index()
        bars = frame[[c for c in ("open", "high", "low", "close") if c in frame.columns]]
        frames = terminal_frames(bars, raw=frame)
    except Exception:
        return None
    columns = {name: series.to_numpy(dtype=float) for name, series in frames.items()}
    times = frame.index.view("int64") // 10 ** 9
    return columns, np.asarray(times, dtype=np.int64), {"bars": len(frame),
                                                        "first": str(frame.index[0]),
                                                        "last": str(frame.index[-1])}


def axis_columns(times: np.ndarray, limit: int = MAX_DATASET_COLUMNS
                 ) -> tuple[dict[str, np.ndarray], dict[str, Variable], list[str]]:
    """Every eligible dataset from `data/axes/*.json`, aligned POINT-IN-TIME to the bar clock.

    A value stamped `knowable_at` may be used at a bar only if it was knowable at or before that
    bar. The join is a forward-fill of the last knowable vintage -- never the newest revision,
    which is the join that turns a research result into a backtest artifact.
    """
    columns: dict[str, np.ndarray] = {}
    meta: dict[str, Variable] = {}
    unmeasured: list[str] = []
    files = sorted(AXES.glob("*.json"))
    if not files:
        unmeasured.append(f"datasets: no axis files under {AXES}; `axis_ingest` has not run here")
        return columns, meta, unmeasured
    for path in files:
        if len(columns) >= limit:
            break
        doc = _read_json(path)
        rows = doc.get("rows") if isinstance(doc, dict) else None
        if not isinstance(rows, list) or not rows:
            unmeasured.append(f"dataset {path.stem}: no rows")
            continue
        axis = str((doc or {}).get("axis") or path.stem)
        numeric = [k for k, v in rows[0].items()
                   if isinstance(v, (int, float)) and not isinstance(v, bool)]
        for key in numeric[:2]:
            if len(columns) >= limit:
                break
            stamps: list[tuple[int, float]] = []
            for row in rows:
                value = row.get(key)
                when = _epoch(row.get("knowable_at") or row.get("available_time")
                              or row.get("date") or row.get("time"))
                if when is not None and isinstance(value, (int, float)):
                    stamps.append((when, float(value)))
            if len(stamps) < 8:
                unmeasured.append(f"dataset {axis}.{key}: {len(stamps)} PIT-stamped points")
                continue
            stamps.sort()
            when = np.asarray([s[0] for s in stamps], dtype=np.int64)
            value = np.asarray([s[1] for s in stamps], dtype=float)
            position = np.searchsorted(when, times, side="right") - 1
            series = np.where(position >= 0, value[np.clip(position, 0, value.size - 1)], np.nan)
            name = f"{axis}_{key}"
            columns[name] = series
            meta[name] = Variable(name=name, dataset=f"axis:{axis}:{key}", source="axis",
                                  available_time=str(datetime.fromtimestamp(int(when[-1]), tz=UTC)))
    return columns, meta, unmeasured


def representation_columns(times: np.ndarray, limit: int = MAX_REPRESENTATION_COLUMNS
                           ) -> tuple[dict[str, np.ndarray], dict[str, Variable], list[str]]:
    """Representations from the forge (and from this lab's own past passes), PIT-aligned."""
    columns: dict[str, np.ndarray] = {}
    meta: dict[str, Variable] = {}
    unmeasured: list[str] = []
    if not REPRESENTATIONS.exists():
        unmeasured.append(f"representations: {REPRESENTATIONS} does not exist; the "
                          "representation forge has not minted anything on this box yet")
        return columns, meta, unmeasured
    for path in sorted(REPRESENTATIONS.glob("*.json")):
        if len(columns) >= limit or path.name == "manifest.json":
            continue
        doc = _read_json(path)
        points = doc.get("points") if isinstance(doc, dict) else None
        if not isinstance(points, list) or len(points) < 8:
            continue
        stamps = [(_epoch(p.get("available_time")), p.get("value")) for p in points
                  if isinstance(p, dict)]
        stamps = [(w, float(v)) for w, v in stamps
                  if w is not None and isinstance(v, (int, float))]
        if len(stamps) < 8:
            continue
        stamps.sort()
        when = np.asarray([s[0] for s in stamps], dtype=np.int64)
        value = np.asarray([s[1] for s in stamps], dtype=float)
        position = np.searchsorted(when, times, side="right") - 1
        name = f"repr_{path.stem[:40]}"
        columns[name] = np.where(position >= 0, value[np.clip(position, 0, value.size - 1)],
                                 np.nan)
        meta[name] = Variable(name=name, dataset=f"representation:{path.stem}",
                              source="representation",
                              available_time=str(datetime.fromtimestamp(int(when[-1]), tz=UTC)))
    if not columns:
        unmeasured.append("representations: no minted series file carried eight PIT-stamped "
                          "points; `representation_forge` writes them under "
                          "desks/mt5/data/representations/")
    return columns, meta, unmeasured


def _epoch(value: Any) -> int | None:
    """Epoch seconds from whatever stamp a source wrote, UTC-anchored. None when unparseable.

    A naive stamp is read as UTC and NOT as local time: every clock in this repo is UTC, and a
    source that omits the offset is stating the desk's clock rather than the reader's.
    """
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return int((parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).timestamp())
    except ValueError:
        pass
    parts = text.split("-")
    try:
        if len(parts) == 2:
            return int(datetime(int(parts[0]), int(parts[1]), 1, tzinfo=UTC).timestamp())
        if len(parts) >= 3:
            return int(datetime(int(parts[0]), int(parts[1]), int(parts[2][:2]),
                                tzinfo=UTC).timestamp())
    except (TypeError, ValueError):
        return None
    return None


def residual_rows() -> tuple[list[dict[str, Any]], str, str, list[str]]:
    """(rows, horizon, source, unmeasured) from the residual store, newest horizon with rows."""
    unmeasured: list[str] = []
    try:
        from research import world_model as WM
    except Exception as exc:
        return [], "", "", [f"world_model unimportable: {type(exc).__name__}"]
    best: tuple[int, str, list[dict[str, Any]]] = (0, "", [])
    for horizon in WM.HORIZONS:
        try:
            rows = WM.read_residuals(horizon)
        except Exception as exc:
            unmeasured.append(f"residual store {horizon}: {type(exc).__name__}")
            continue
        if len(rows) > best[0]:
            best = (len(rows), horizon, rows)
    if not best[2]:
        unmeasured.append("residual store: no horizon carries rows under "
                          f"{DESK / 'data' / 'world_model'}; world_model has not published here")
    return best[2], best[1], "world_model", unmeasured


def residual_targets() -> dict[str, str]:
    """target symbol -> the residual-hunt discovery id that opened the question."""
    out: dict[str, str] = {}
    try:
        from libs.moat import registry as reg
        for row in reg.discoveries(limit=400):
            # THE KIND IS NOT A COLUMN. `record_discovery` keeps only the columns the table has,
            # and `discoveries` has no `kind`; the residual hunt's rows are known by their
            # generator, which IS a column. Reading `row["kind"]` here matched nothing, silently.
            if str(row.get("generator")) != "residual_hunt":
                continue
            assets = row.get("assets_json") or row.get("assets") or "[]"
            names = json.loads(assets) if isinstance(assets, str) else list(assets)
            for name in names:
                out.setdefault(str(name), str(row.get("discovery_id")))
    except Exception:
        return out
    return out


def _bar_baseline(columns: dict[str, np.ndarray], horizon_bars: int = 4
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """The fallback residual: forward return less a ridge forecast, fitted on the first 60%.

    NAMED `bar_baseline` everywhere it appears. It is this organ's own baseline, not the world
    model's conditional distribution, and reading one as the other is exactly the confusion the
    residual store exists to prevent.
    """
    ret = columns.get("ret")
    if ret is None or ret.size < 600:
        return None
    n = ret.size
    forward = np.full(n, np.nan, dtype=float)
    cum = np.nancumsum(np.nan_to_num(ret))
    forward[:n - horizon_bars] = cum[horizon_bars:] - cum[:n - horizon_bars]
    features = [G.evaluate(tree, columns, n) for tree in (
        ["lag", "ret", 2], ["lag", "ret", 3], ["z", "ret", 24], ["z", "range", 24],
        ["z", "vol", 48] if "vol" in columns else ["z", "ret", 48])]
    design = np.column_stack([np.ones(n)] + [np.nan_to_num(f) for f in features])
    usable = np.isfinite(forward)
    cut = int(n * 0.6)
    train = usable & (np.arange(n) < cut)
    if int(train.sum()) < 200:
        return None
    gram = design[train].T @ design[train] + 1e-3 * np.eye(design.shape[1])
    beta = np.linalg.solve(gram, design[train].T @ forward[train])
    yhat = design @ beta
    epsilon = np.where(usable, forward - yhat, np.nan)
    with G.quiet():
        vol = G.evaluate(["rstd", "ret", 48], columns, n)
        edges = np.nanquantile(vol[train], [1 / 3, 2 / 3]) if int(train.sum()) else [0.0, 0.0]
        regime = np.where(vol <= edges[0], "low", np.where(vol <= edges[1], "mid", "high"))
    return epsilon, regime, yhat


def _sessions(times: np.ndarray) -> np.ndarray:
    hours = ((times // 3600) % 24).astype(int)
    out = np.full(times.size, "off", dtype=object)
    out[(hours >= 0) & (hours < 7)] = "asia"
    out[(hours >= 7) & (hours < 13)] = "london"
    out[(hours >= 13) & (hours < 21)] = "ny"
    return out.astype(str)


def build_panels(max_targets: int = MAX_TARGETS) -> tuple[list[Panel], dict[str, Any]]:
    """The pass's panels, and the full account of where every input came from or did not."""
    status: dict[str, Any] = {"unmeasured": []}
    allowed, universe_status = hypothesis_universe()
    status["universe"] = universe_status
    if not allowed:
        return [], status

    rows, horizon, store_source, store_unmeasured = residual_rows()
    status["unmeasured"].extend(store_unmeasured)
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or row.get("target") or "")
        if symbol in allowed:
            by_symbol.setdefault(symbol, []).append(row)
    ranked = sorted(by_symbol, key=lambda s: -len(by_symbol[s]))[:max_targets]
    if not ranked:
        ranked = allowed[:max_targets]
    status["targets"] = ranked
    status["residual_store"] = {"rows": len(rows), "horizon": horizon, "symbols": len(by_symbol)}

    targets = residual_targets()
    peer_pool: dict[str, tuple[dict[str, np.ndarray], np.ndarray]] = {}
    for symbol in allowed[:MAX_PEERS + len(ranked)]:
        loaded = bar_frames(symbol)
        if loaded is not None:
            peer_pool[symbol] = (loaded[0], loaded[1])

    panels: list[Panel] = []
    sources: dict[str, str] = {}
    for symbol in ranked:
        loaded = peer_pool.get(symbol)
        if loaded is None:
            status["unmeasured"].append(f"target {symbol}: no H1 bars under {UNIVERSE}")
            continue
        columns, times = {k: v.copy() for k, v in loaded[0].items()}, loaded[1]
        epsilon, regime, source = _epsilon_for(symbol, by_symbol.get(symbol, []), times, columns,
                                               store_source, status)
        if epsilon is None:
            continue
        sources[symbol] = source
        meta: dict[str, Variable] = {
            name: Variable(name=name, dataset=f"bars:{symbol}", source="bars",
                           available_time="the bar's own close")
            for name in columns}
        axis_cols, axis_meta, axis_unmeasured = axis_columns(times)
        repr_cols, repr_meta, repr_unmeasured = representation_columns(times)
        status["unmeasured"].extend(axis_unmeasured + repr_unmeasured)
        columns.update(axis_cols)
        columns.update(repr_cols)
        meta.update(axis_meta)
        meta.update(repr_meta)
        peers = {name: G.evaluate(["diff", "close", 2], {"close": frames[0]["close"]},
                                  frames[0]["close"].size)
                 for name, frames in list(peer_pool.items())[:MAX_PEERS + 1]
                 if frames[1].size == times.size}
        panel = Panel(target=symbol, times=times, epsilon=epsilon, columns=columns, meta=meta,
                      regime=regime, session=_sessions(times), peers=peers,
                      horizon=horizon or "4", source=source,
                      residual_discovery_id=targets.get(symbol, ""))
        panels.append(panel)
    status["panel_sources"] = sources
    status["datasets"] = sorted({v.dataset for p in panels for v in p.meta.values()
                                 if v.source == "axis"})
    status["representations"] = sorted({v.dataset for p in panels for v in p.meta.values()
                                        if v.source == "representation"})
    return panels, status


def _epsilon_for(symbol: str, rows: list[dict[str, Any]], times: np.ndarray,
                 columns: dict[str, np.ndarray], store_source: str, status: dict[str, Any]
                 ) -> tuple[np.ndarray | None, np.ndarray | None, str]:
    """The residual for one symbol, down the three-rung ladder, naming the rung it stopped on."""
    if rows:
        stamps = [(_epoch(r.get("time")), r.get("epsilon"), r.get("regime")) for r in rows]
        stamps = [(w, float(v), str(g)) for w, v, g in stamps
                  if w is not None and isinstance(v, (int, float))]
        if len(stamps) >= 60:
            stamps.sort()
            when = np.asarray([s[0] for s in stamps], dtype=np.int64)
            value = np.asarray([s[1] for s in stamps], dtype=float)
            label = np.asarray([s[2] for s in stamps], dtype=object)
            position = np.searchsorted(when, times, side="right") - 1
            exact = (position >= 0) & (np.abs(when[np.clip(position, 0, when.size - 1)]
                                              - times) <= 3600)
            epsilon = np.where(exact, value[np.clip(position, 0, value.size - 1)], np.nan)
            regime = np.where(exact, label[np.clip(position, 0, label.size - 1)], UNMEASURED)
            if int(np.isfinite(epsilon).sum()) >= 400:
                return epsilon, regime.astype(str), store_source
            status["unmeasured"].append(
                f"target {symbol}: the residual store holds {len(stamps)} rows but only "
                f"{int(np.isfinite(epsilon).sum())} align to this symbol's H1 clock")
    shadow = _shadow_epsilon(symbol, times, status)
    if shadow is not None:
        return shadow[0], shadow[1], "shadow_discovery"
    baseline = _bar_baseline(columns)
    if baseline is None:
        status["unmeasured"].append(f"target {symbol}: fewer than 600 usable bars for even the "
                                    "bar baseline")
        return None, None, ""
    return baseline[0], baseline[1], "bar_baseline"


def _shadow_epsilon(symbol: str, times: np.ndarray, status: dict[str, Any]
                    ) -> tuple[np.ndarray, np.ndarray] | None:
    """Rung two: the live book's factor residual from `shadow_discovery.fit_epsilon`.

    Per-TRADE, not per-bar, so it only produces a usable panel when the book has enough closed
    trades on this instrument. It usually does not (n=7 per sleeve as of 2026-09-07), and the
    shortfall is recorded by name rather than silently skipped.
    """
    try:
        from research import shadow_discovery as SD
    except Exception as exc:
        status["unmeasured"].append(f"shadow_discovery unimportable: {type(exc).__name__}")
        return None
    try:
        notes: list[dict[str, str]] = []
        sleeves = SD.collect(notes, {})
        panel, names, *_rest = SD.factor_panel(notes)
        trades = [t for sleeve in sleeves.values() for t in getattr(sleeve, "trades", [])
                  if str(getattr(t, "symbol", symbol)) == symbol]
        if len(trades) < 400:
            status["unmeasured"].append(
                f"target {symbol}: shadow_discovery has {len(trades)} closed trades, fewer than "
                f"the 400 a panel needs; more forward evidence would measure it")
            return None
        kept, eps, *_ = SD.fit_epsilon(trades, panel, len(names))
        when = np.asarray([int(t.at.timestamp()) for t in kept], dtype=np.int64)
        position = np.searchsorted(when, times, side="right") - 1
        aligned = np.where(position >= 0, eps[np.clip(position, 0, eps.size - 1)], np.nan)
        return aligned, np.full(times.size, UNMEASURED, dtype=object).astype(str)
    except Exception as exc:
        status["unmeasured"].append(f"shadow_discovery residual: {type(exc).__name__}")
        return None


# ------------------------------------------------------------------------------ allocation
def read_allocation() -> dict[str, Any]:
    doc = _read_json(ALLOCATION)
    return doc if isinstance(doc, dict) else {}


def all_traditions() -> tuple[str, ...]:
    """Every tradition this leg runs: the mathematical cohorts, then the physics wing."""
    return (*S.TRADITIONS, *[t for t in PHYSICS_TRADITIONS if t not in S.TRADITIONS])


def department_of(tradition: str) -> str:
    return "physics" if tradition in PHYSICS_REGISTRY else "mathematics"


def tradition_roi(traditions: tuple[str, ...] | list[str] | None = None
                  ) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Per-tradition ROI in `research_roi.scientist_roi`'s own shape, from `generator_yield`."""
    names = tuple(traditions) if traditions is not None else all_traditions()
    out: dict[str, float | None] = dict.fromkeys(names)
    detail: dict[str, Any] = {"source": "libs/moat/registry.py generator_yield",
                              "shape": "research_roi.scientist_roi"}
    try:
        from libs.moat import registry as reg
        rows = {str(r.get("generator")): r for r in reg.generator_yields()}
    except Exception as exc:
        detail["status"] = UNMEASURED
        detail["why"] = f"registry unreadable: {type(exc).__name__}"
        return out, detail
    detail["status"] = "MEASURED"
    detail["rows"] = {}
    for tradition in names:
        row = rows.get(f"math:{tradition}") or {}
        compute_h = float(row.get("compute_s") or 0.0) / 3600.0
        value = (float(row.get("independent_survivors") or 0.0)
                 + float(row.get("survivors") or 0.0) + float(row.get("delta_elogw") or 0.0))
        roi = round(value / compute_h, 6) if compute_h > 0 else None
        out[tradition] = roi
        detail["rows"][tradition] = {
            "generated": int(float(row.get("generated") or 0)),
            "donated": int(float(row.get("donated") or 0)),
            "judged": int(float(row.get("judged") or 0)),
            "independent_survivors": int(float(row.get("independent_survivors") or 0)),
            "delta_elogw": float(row.get("delta_elogw") or 0.0),
            "compute_hours": round(compute_h, 6), "value": round(value, 8), "roi": roi,
            "roi_status": "MEASURED" if compute_h > 0 else UNMEASURED}
    return out, detail


def allocation(roi: dict[str, float | None], previous: dict[str, Any] | None = None,
               traditions: tuple[str, ...] | list[str] | None = None) -> dict[str, Any]:
    """Compute shares per tradition: two-sided, floored at 2%, and never zero.

    AN UNPRICED TRADITION KEEPS THE DEFAULT. Pricing the unknown at zero defunds the frontier by
    accident -- the same reasoning `forest_allocation` uses for an unmeasured region. A tradition
    with measured ROI moves BOTH WAYS around the mean: better than average earns more than the
    default share, worse than average earns less, and the floor stops the worse case reaching
    silence so a tradition can still detect that conditions changed (LAWS 5f).
    """
    names = tuple(traditions) if traditions is not None else (tuple(roi) or S.TRADITIONS)
    prior = (previous or {}).get("traditions") or {}
    measured = {k: v for k, v in roi.items() if k in names and isinstance(v, (int, float))}
    scale = float(np.mean([abs(v) for v in measured.values()])) if measured else 0.0
    raw: dict[str, float] = {}
    why: dict[str, str] = {}
    for tradition in names:
        value = roi.get(tradition)
        if value is None or scale <= 0:
            raw[tradition] = 1.0
            why[tradition] = (f"ROI {UNMEASURED}: the declared default share -- an unpriced "
                              f"tradition is not an unproductive one")
        else:
            raw[tradition] = float(max(0.05, 1.0 + value / scale))
            why[tradition] = (f"ROI {value:+.6f} against a mean absolute ROI of {scale:.6f}: "
                              f"two-sided around the default, floored at {FLOOR_SHARE:.0%}")
    total = sum(raw.values()) or float(len(raw))
    free = max(0.0, 1.0 - FLOOR_SHARE * len(names))
    shares = {t: round(FLOOR_SHARE + free * raw[t] / total, 6) for t in names}
    return {
        "at": now_iso(), "rule": RULE, "floor": FLOOR_SHARE,
        "traditions": {t: {"share": shares[t], "roi": roi.get(t),
                           "roi_status": "MEASURED" if roi.get(t) is not None else UNMEASURED,
                           "lifetime_trials": int((prior.get(t) or {}).get("lifetime_trials", 0)),
                           "department": department_of(t), "why": why[t]}
                       for t in names},
        "sum": round(sum(shares.values()), 6),
        "two_sided": ("every share moves up AND down with measured ROI; the floor is a floor, "
                      "never a target, and no tradition is ever set to zero"),
    }


def department_plan(roi: dict[str, float | None], previous: dict[str, Any] | None,
                    budget_s: float) -> dict[str, Any]:
    """Two departments, each allocated by the two-sided rule above, under a department split
    that is itself two-sided by the departments' mean measured ROI with a floor
    (`engines.distributed_science`). Each tradition's `budget_share` is its share of the WHOLE
    pass: department share x share within the department."""
    maths = [t for t in all_traditions() if department_of(t) == "mathematics"]
    physics = [t for t in all_traditions() if department_of(t) == "physics"]
    plan = allocation(roi, previous, maths)
    plan_p = allocation(roi, previous, physics) if physics else {"traditions": {}}
    dept_roi: dict[str, float | None] = {}
    for dept, names in (("mathematics", maths), ("physics", physics)):
        measured = [v for t, v in roi.items() if t in names and isinstance(v, (int, float))]
        dept_roi[dept] = float(np.mean(measured)) if measured else None
    split = E.run_engine("distributed_science", E.distributed_science,
                         budget_s * (1.0 - ENGINE_SHARE), dept_roi)
    dept_share = split.summary.get("shares") or {"mathematics": 0.5, "physics": 0.5}
    if not physics:
        dept_share = {"mathematics": 1.0, "physics": 0.0}
    plan["traditions"].update(plan_p["traditions"])
    for t, row in plan["traditions"].items():
        row["budget_share"] = round((1.0 - ENGINE_SHARE) * float(dept_share.get(
            department_of(t), 0.0)) * float(row["share"]), 6)
    plan["departments"] = {"shares": dept_share, "roi": dept_roi, "engine_share": ENGINE_SHARE,
                           "budgets_s": {k: round(budget_s * (1.0 - ENGINE_SHARE) * v, 1)
                                         for k, v in dept_share.items()},
                           "engines_s": round(budget_s * ENGINE_SHARE, 1),
                           "rule": split.summary.get("two_sided")}
    plan["sum"] = round(sum(v["share"] for v in plan["traditions"].values()), 6)
    return plan


#: The engines that run inside THIS leg's budget; the full set runs in `physics_lab`.
MATHLAB_ENGINES: tuple[str, ...] = ("law_discovery", "model_competition", "mdl_score",
                                    "counterfactual_simulator", "experimental_discrimination",
                                    "formal_maths", "differentiable_science",
                                    "primitive_invention")


def run_engines(panel: Panel, objects: list[MathObject], budget_s: float
                ) -> dict[str, E.EngineResult]:
    """The engine slice of the pass: each engine bounded, none fatal, keyed for the proof."""
    slice_s = max(0.5, budget_s / len(MATHLAB_ENGINES))
    rng = np.random.default_rng(SEED + 3)
    out: dict[str, E.EngineResult] = {}
    out["law_discovery"] = E.run_engine("law_discovery", E.law_discovery, panel,
                                        budget_s=slice_s, rng=rng)
    out["model_competition"] = E.run_engine("model_competition", E.model_competition, panel,
                                            budget_s=slice_s, rng=rng)
    out["mdl_score"] = E.run_engine("mdl_score", E.mdl_competition, panel, objects,
                                    budget_s=slice_s, rng=rng)
    out["counterfactual_simulator"] = E.run_engine(
        "counterfactual_simulator", E.counterfactual_simulator, panel,
        (out["law_discovery"].summary or {}).get("best"), budget_s=slice_s, rng=rng)
    out["experimental_discrimination"] = E.run_engine(
        "experimental_discrimination", E.experimental_discrimination, panel,
        (out["model_competition"].summary or {}).get("predictions") or {}, budget_s=slice_s,
        rng=rng)
    out["formal_maths"] = E.run_engine("formal_maths", E.formal_maths,
                                       [o.expression for o in objects[:50]], budget_s=slice_s,
                                       rng=rng)
    out["differentiable_science"] = E.run_engine("differentiable_science",
                                                 E.differentiable_science, panel,
                                                 budget_s=slice_s, rng=rng)
    out["primitive_invention"] = E.run_engine("primitive_invention", E.primitive_invention,
                                              objects, budget_s=slice_s, rng=rng)
    out["model_competition"].summary.pop("predictions", None)
    return out


# --------------------------------------------------------------------------------- the pass
def _copy_panel(panel: Panel) -> Panel:
    """A per-tradition view. Column arrays are SHARED; the dict is not, so minting is private."""
    return Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                 columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                 session=panel.session, peers=panel.peers, horizon=panel.horizon,
                 source=panel.source, residual_discovery_id=panel.residual_discovery_id)


def _run_tradition(tradition: str, panels: list[Panel], budget_s: float, roi: dict[str, Any],
                   census: dict[str, int]) -> dict[str, Any]:
    """One tradition over every panel. NEVER RAISES: a failing scientist costs its own leg only."""
    started = time.monotonic()
    result: dict[str, Any] = {"tradition": tradition, "objects": [], "panels": [],
                              "evaluated": 0, "distinct": set(), "unmeasured": [], "minted": [],
                              "status": "OK"}
    try:
        kwargs = {"roi": roi, "operators_used": census} if tradition == "meta_mathematics" else {}
        scientist = S.build(tradition, **kwargs)
    except Exception as exc:
        result["status"] = "FAILED"
        result["why"] = f"{type(exc).__name__}: {exc}"
        result["compute_s"] = round(time.monotonic() - started, 3)
        return result
    per_panel = max(1.0, budget_s / max(1, len(panels)))
    for panel in panels:
        view = _copy_panel(panel)
        try:
            objects = scientist.propose(view, per_panel, np.random.default_rng(
                SEED + abs(hash((tradition, panel.target))) % 10_000))
        except Exception as exc:
            result["status"] = "FAILED"
            result["why"] = f"{type(exc).__name__}: {exc}"
            result["unmeasured"].append(f"panel {panel.target}: {type(exc).__name__}: {exc}")
            continue
        for obj in objects:
            obj.provenance.residual_target = panel.target
            obj.provenance.residual_discovery_id = panel.residual_discovery_id
            obj.provenance.panel_source = panel.source
            obj.provenance.datasets = sorted({v.dataset for v in obj.variables})
            obj.provenance.representations = sorted({v.dataset for v in obj.variables
                                                     if v.source == "representation"})
            obj.provenance.seed = SEED
        result["objects"].extend([(obj, view) for obj in objects])
        result["panels"].append(panel.target)
        result["evaluated"] += scientist.evaluated
        result["distinct"] |= scientist.distinct
        result["unmeasured"].extend(scientist.unmeasured)
        result["minted"].extend([(name, view) for name in scientist.minted])
    result["compute_s"] = round(time.monotonic() - started, 3)
    return result


def _operator_census(objects: list[MathObject]) -> dict[str, int]:
    census: dict[str, int] = {}
    for obj in objects:
        for token in G.OPERATORS:
            if f"{token}(" in obj.canonical:
                census[token] = census.get(token, 0) + 1
    return census


def _entry_exit(params: dict[str, Any]) -> dict[str, str]:
    return {
        "entry_rule": (f"evaluate the expression on H1 bars, z-score it over {params['norm']} "
                       f"bars, and enter at the NEXT bar's open in the direction of "
                       f"sign(z) * ({'+1' if params['side_mode'] == 'follow' else '-1'}) when "
                       f"|z| >= {params['entry_z']}"),
        "exit_rule": (f"stop at {params['stop_atr']} ATR({params['atr_n']}), target at "
                      f"{params['stop_atr'] * params['rr']} ATR, time exit after "
                      f"{params['hold_bars']} bars, whichever comes first"),
        "executor": "mt5desk.family_formula (family `formula`), exactly as written",
    }


def donation_rows(objects: list[MathObject], already: set[str]) -> tuple[list[dict[str, Any]],
                                                                        list[dict[str, str]]]:
    """Executable candidates for the compiler's EXACT_RECIPE door, plus what could not be one."""
    rows: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    try:
        from research import proposer_common as PC
    except Exception as exc:
        return [], [{"object_id": "*", "why": f"proposer_common unimportable: "
                                              f"{type(exc).__name__}"}]
    for obj in objects:
        if obj.object_id in already:
            continue
        expr, why = G.tradeable(obj.expression)
        if expr is None:
            refused.append({"object_id": obj.object_id, "canonical": obj.canonical, "why": why})
            continue
        params = {"expr": expr, "norm": B.NORM, "entry_z": 1.5, "side_mode": obj.side_mode,
                  "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}
        mechanism = (obj.interpretation.rationale if obj.interpretation.status == "interpreted"
                     else obj.statement)[:600]
        evidence = {**obj.evidence.to_row(), **_entry_exit(params),
                    "object_id": obj.object_id, "kind": obj.kind, "tradition": obj.tradition,
                    "canonical": obj.canonical, "complexity": obj.complexity,
                    "burden": obj.burden, "interpretation": obj.interpretation.to_row(),
                    "provenance": obj.provenance.to_row(),
                    "graph_node": B.graph_identity(obj, "formula", params)}
        row = PC.candidate(SOURCE, obj.target, "formula", params, mechanism,
                           f"mathlab/{obj.tradition}: {obj.canonical}", evidence)
        row["kind"] = "hypothesis"
        row["symbols"] = [obj.target]
        row["mathlab_object_id"] = obj.object_id
        rows.append(row)
    return rows, refused


def representation_manifest(minted: list[tuple[str, Panel, MathObject]], dry_run: bool
                            ) -> dict[str, Any]:
    """Publish this pass's invented state variables in the forge's manifest shape.

    Written under `data/representations/mathlab/`, NEVER into the forge's own manifest: the forge
    is another builder's organ and its file is its state. The next pass's panel builder reads both
    directories, so a variable invented by topology this hour is a column every tradition can
    build on next hour.
    """
    rows: dict[str, dict[str, Any]] = {}
    for name, panel, obj in minted:
        series = panel.columns.get(name)
        if series is None:
            continue
        finite = np.isfinite(series)
        points = [{"period_time": str(datetime.fromtimestamp(int(t), tz=UTC)),
                   "available_time": str(datetime.fromtimestamp(int(t), tz=UTC)),
                   "value": round(float(v), 8)}
                  for t, v in zip(panel.times[finite], series[finite], strict=False)][-3000:]
        rid = f"mathlab:{obj.tradition}:{name}:{panel.target}"
        rows[rid] = {
            "id": rid, "file": f"{rid.replace(':', '_')}.json", "dataset": f"mathlab:{name}",
            "transform": f"{obj.tradition}|{name}", "family": obj.tradition,
            "params": {"target": panel.target, "horizon": panel.horizon},
            "region": "GLOBAL", "information_type": "representation", "n": len(points),
            "first_available": points[0]["available_time"] if points else None,
            "last_available": points[-1]["available_time"] if points else None,
            "inputs": sorted(G.variables_in(obj.expression)),
            "novelty": None, "expected_value": obj.value, "score": obj.value,
            "explained_variance": obj.evidence.ic_held_out,
            "pit": {"carried_from": sorted(G.variables_in(obj.expression)),
                    "rule": "a value stamped available_time t uses only inputs available at t"},
            "minted_at": now_iso(), "minted_by": f"math:{obj.tradition}",
            "statement": obj.statement,
        }
        if not dry_run:
            MATHLAB_REPRESENTATIONS.mkdir(parents=True, exist_ok=True)
            _atomic(MATHLAB_REPRESENTATIONS / rows[rid]["file"],
                    {"id": rid, "dataset": f"mathlab:{name}", "points": points})
    if rows and not dry_run:
        _atomic(MATHLAB_REPRESENTATIONS / "manifest.json",
                {"at": now_iso(), "rule": RULE, "n": len(rows),
                 "representations": sorted(rows.values(), key=lambda r: str(r["id"]))})
    return {"minted": len(rows), "ids": sorted(rows), "path": str(MATHLAB_REPRESENTATIONS)}


def record_registry(objects: list[MathObject], per_tradition: dict[str, dict[str, Any]],
                    donated: dict[str, int]) -> dict[str, Any]:
    """Discoveries, provenance edges, representation rows and per-tradition credit.

    NEVER FATAL. A registry that can take down the search it records would be removed within a
    week, correctly -- every failure is reported in the artifact and nothing else.
    """
    out: dict[str, Any] = {"discoveries": 0, "new": 0, "links": 0, "representations": 0,
                           "generator_yield": 0, "trials": []}
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"registry unimportable: {type(exc).__name__}"}
    try:
        conn = reg.connect()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"registry unopenable: {type(exc).__name__}"}
    try:
        for obj in objects:
            try:
                did, created = reg.record_discovery(
                    source_id=f"mathlab:{obj.tradition}", source_type="mathematics",
                    mechanism=(obj.interpretation.rationale or obj.statement)[:800],
                    origin="DESK", generator=f"math:{obj.tradition}",
                    discovery_id=obj.object_id, kind=REGISTRY_KIND[obj.kind],
                    assets=[obj.target], horizons=[obj.horizon],
                    sessions=[], regimes=[],
                    information="mathematics",
                    economic_rationale=obj.statement[:800],
                    exact_rule=obj.canonical,
                    required_data=sorted({v.dataset for v in obj.variables}),
                    novelty=1.0, confidence=round(float(obj.interpretation.prior), 3),
                    falsifier=obj.interpretation.falsifier,
                    payload=obj.to_row(), conn=conn)
            except Exception:
                continue
            out["discoveries"] += 1
            out["new"] += int(created)
            with contextlib.suppress(Exception):
                reg.set_discovery_state(did, "QUEUED" if obj.passed else "UNPROCESSED",
                                        conn=conn)
            if obj.provenance.residual_discovery_id:
                try:
                    reg.link("discovery", obj.provenance.residual_discovery_id, "discovery", did,
                             "motivated", conn=conn)
                    out["links"] += 1
                except Exception:
                    pass
            if obj.kind == "representation":
                try:
                    reg.representation_upsert(
                        f"mathlab:{obj.tradition}:{obj.target}:{obj.canonical[:60]}",
                        dataset=f"mathlab:{obj.tradition}", transform=obj.canonical[:200],
                        family=obj.tradition, params={"target": obj.target},
                        pit={"rule": "carried from the inputs"}, conn=conn)
                    out["representations"] += 1
                except Exception:
                    pass
        for tradition, row in per_tradition.items():
            try:
                reg.generator_yield_update(
                    f"math:{tradition}", generated=int(row.get("proposed", 0)),
                    donated=int(donated.get(tradition, 0)),
                    compute_s=float(row.get("compute_s", 0.0)), conn=conn)
                out["generator_yield"] += 1
            except Exception:
                pass
            out["trials"].append({
                "tradition": tradition,
                **B.record_trials(tradition, distinct_forms=int(row.get("distinct", 0)),
                                  evaluated=int(row.get("evaluated", 0)),
                                  target=str(row.get("target") or ""),
                                  passed=int(row.get("passed", 0)), conn=conn)})
        return out
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def dedup(objects: list[MathObject]) -> tuple[list[MathObject], dict[str, Any]]:
    """One admitted object per mechanism, through the desk's own chain when it is importable."""
    try:
        from libs.research.dedup_chain import Item, census, fold
    except Exception:
        seen: set[str] = set()
        kept: list[MathObject] = []
        duplicates = 0
        for obj in objects:
            if obj.canonical in seen:
                duplicates += 1
                continue
            seen.add(obj.canonical)
            kept.append(obj)
        return kept, {"chain": "canonical-string identity (libs/research/dedup_chain unavailable)",
                      "admitted": len(kept), "duplicates": duplicates}
    items = [Item(item_id=o.object_id, title=o.statement[:300], text=o.canonical,
                  family="formula", instruments=(o.target,), condition=o.canonical,
                  horizon=o.horizon, source_id=f"math:{o.tradition}", kind=o.kind,
                  payload={"tradition": o.tradition}) for o in objects]
    verdicts, _ = fold(items)
    kept = [obj for obj, verdict in zip(objects, verdicts, strict=False)
            if verdict.is_new or verdict.is_descendant]
    return kept, {"chain": "libs/research/dedup_chain.fold", "admitted": len(kept),
                  "duplicates": len(objects) - len(kept), **census(verdicts)}


def run(*, budget_s: float = 3000.0, dry_run: bool = False,
        traditions: list[str] | None = None, max_targets: int = MAX_TARGETS,
        permutations: int = B.PERMUTATIONS) -> dict[str, Any]:
    """One pass of the mathematics civilization. Returns the report it also writes."""
    started = time.monotonic()
    chosen = [t for t in (traditions or list(all_traditions())) if t in S.REGISTRY]
    unknown = [t for t in (traditions or []) if t not in S.REGISTRY]
    panels, panel_status = build_panels(max_targets)
    workers, memory = max_workers()
    roi, roi_detail = tradition_roi()
    previous = read_allocation()
    plan = department_plan(roi, previous, budget_s)

    if not panels:
        report = _report(started, chosen, unknown, panel_status, memory, plan, roi_detail,
                         {}, [], {}, {}, {}, {}, dry_run,
                         ["panel: no target produced a usable residual panel this pass"])
        if not dry_run:
            _atomic(OUT, report)
        return report

    census = _operator_census([])
    budgets = {t: max(5.0, budget_s * float(plan["traditions"][t].get(
        "budget_share", plan["traditions"][t]["share"]))) for t in chosen}
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(chosen)))) as pool:
        futures = {pool.submit(_run_tradition, t, panels, budgets[t], roi, census): t
                   for t in chosen}
        for future, tradition in futures.items():
            try:
                results[tradition] = future.result()
            except Exception as exc:
                results[tradition] = {"tradition": tradition, "status": "FAILED",
                                      "why": f"{type(exc).__name__}: {exc}", "objects": [],
                                      "panels": [], "evaluated": 0, "distinct": set(),
                                      "unmeasured": [], "minted": [], "compute_s": 0.0}

    rng = np.random.default_rng(SEED)
    # THE WALL CLOCK GOVERNS THE JUDGE TOO (2026-09-23). `budgets` above bounds the SCIENTISTS;
    # judging is an unbounded loop over everything they proposed, and on a 50,000-row residual
    # panel it dominates. MEASURED: --budget-s 300 with the physics wing ran 1,228 s, and
    # `_producer_impl` kills this leg at LEG_BUDGET_SEC.get("math_lab", 720) -- so the pass was
    # cut before `_atomic(OUT, report)` and MATH_LAB.json was never written from the clock,
    # which is the definition of an idle organ. The judge now stops at its share of the same
    # budget and the objects it did not reach are named UNMEASURED by count.
    judge_deadline = started + 0.80 * budget_s
    unjudged = 0
    per_tradition: dict[str, dict[str, Any]] = {}
    judged: list[MathObject] = []
    minted: list[tuple[str, Panel, MathObject]] = []
    lifetime = {t: int((previous.get("traditions", {}).get(t) or {}).get("lifetime_trials", 0))
                for t in all_traditions()}

    for tradition in chosen:
        result = results.get(tradition, {})
        objects = result.get("objects") or []
        distinct = len(result.get("distinct") or set())
        charged = B.effective_trials(distinct, lifetime.get(tradition, 0))
        passed = 0
        for obj, view in objects:
            if time.monotonic() > judge_deadline:
                unjudged += 1
                continue
            try:
                B.judge(obj, view, distinct_forms=distinct,
                        lifetime_trials=lifetime.get(tradition, 0), rng=rng,
                        peers=[p for p in panels if p.target != obj.target][:2],
                        permutations=permutations)
            except Exception as exc:
                obj.notes.append(f"{UNMEASURED}: burden.judge raised {type(exc).__name__}")
                continue
            passed += int(obj.passed)
            judged.append(obj)
        for name, view in (result.get("minted") or []):
            owner = next((o for o, v in objects if v is view and name in G.variables_in(
                o.expression)), None)
            if owner is not None:
                minted.append((name, view, owner))
        per_tradition[tradition] = {
            "status": result.get("status", "OK"), "why": result.get("why"),
            "proposed": len(objects), "distinct": distinct,
            "evaluated": int(result.get("evaluated", 0)),
            "effective_trials": charged, "lifetime_trials_before": lifetime.get(tradition, 0),
            "passed_burden": passed, "minted_representations": len(result.get("minted") or []),
            "compute_s": float(result.get("compute_s", 0.0)),
            "panels": result.get("panels") or [],
            "target": (result.get("panels") or [""])[0],
            "unmeasured": result.get("unmeasured") or [],
        }

    admitted, dedup_status = dedup(judged)
    simplified_away = len(judged) - len(admitted)

    # ---- THE PROPOSER SEAT, OPTIONAL: candidate mechanism names for uninterpreted objects.
    # An object the traditions could not interpret carries a measured relation with no named
    # cause. The seat proposes a CAUSE TO TEST and nothing else: it lands in `notes`, it never
    # touches `interpretation.status`, and the object is judged and donated exactly as it would
    # be without the seat. {} on a box with no panel, so this is a no-op there.
    seat_named = 0
    try:
        from libs.research import proposer_seat as _ps
        _open = [o for o in admitted if o.interpretation.status != "interpreted"][:12]
        _names = _ps.names_for("math_lab",
                               [{"key": o.object_id, "claim": o.statement[:200],
                                 "tradition": o.tradition, "target": o.target} for o in _open])
        for _o in _open:
            _hit = _names.get(_o.object_id)
            if _hit:
                _o.notes.append(f"proposer_seat CANDIDATE mechanism (untested, not an "
                                f"interpretation): {_hit['mechanism']} | falsifier: "
                                f"{_hit['falsifier']} | by {_hit['by'].get('model')}")
                seat_named += 1
    except Exception as _exc:                             # pragma: no cover - optional seat
        seat_named = 0
        del _exc

    survivors = [o for o in admitted if o.passed]
    survivors.sort(key=lambda o: -(o.value or -9e9))

    already = set((_read_json(DONATED) or {}).get("object_ids") or [])
    rows, refused = donation_rows(survivors[:MAX_DONATIONS], already)
    donation: dict[str, Any] = {"donated": 0, "path": None, "refused_untradeable": len(refused),
                                "refusals": refused[:20],
                                "already_donated_in_a_previous_pass":
                                    len([o for o in survivors if o.object_id in already])}
    donated_by_tradition: dict[str, int] = {}
    if rows and not dry_run:
        try:
            from research import proposer_common as PC
            path = PC.donate(SOURCE, rows, tests_run=sum(
                int(v.get("evaluated", 0)) for v in per_tradition.values()))
            donation.update({"path": str(path) if path else None, **PC.donation_counts()})
            for row in rows:
                tradition = str(row.get("evidence", {}).get("tradition") or "")
                donated_by_tradition[tradition] = donated_by_tradition.get(tradition, 0) + 1
            donation["by_tradition"] = dict(donated_by_tradition)
            _atomic(DONATED, {"at": now_iso(),
                              "object_ids": sorted(already | {r["mathlab_object_id"]
                                                              for r in rows}),
                              "rule": "an object donated once is never donated again; the "
                                      "compiler's intake is idempotent by object id"})
        except Exception as exc:
            donation["status"] = f"{UNMEASURED}: donate raised {type(exc).__name__}: {exc}"
    elif rows:
        donation["donated"] = 0
        donation["status"] = "SKIPPED_DRY_RUN"

    representations = representation_manifest(minted, dry_run)
    registry = ({"status": "SKIPPED_DRY_RUN"} if dry_run
                else record_registry(admitted, per_tradition, donated_by_tradition))
    if not dry_run:
        for tradition, row in per_tradition.items():
            plan["traditions"][tradition]["lifetime_trials"] = (
                lifetime.get(tradition, 0) + int(row.get("distinct", 0)))
        _atomic(ALLOCATION, plan)
    engines = run_engines(panels[0], admitted, max(4.0, budget_s * ENGINE_SHARE))
    wiring = I.wiring_proof(
        {t: {**row, "passed": row.get("passed_burden", 0)} for t, row in per_tradition.items()},
        engines, chosen, list(MATHLAB_ENGINES))

    report = _report(started, chosen, unknown, panel_status, memory, plan, roi_detail,
                     per_tradition, admitted, dedup_status, donation, representations, registry,
                     dry_run,
                     ([f"budget: {unjudged} proposed objects were not judged this pass (judge "
                       f"deadline {0.80 * budget_s:.0f}s of a {budget_s:.0f}s budget)"]
                      if unjudged else []) +
                     ([] if seat_named else
                      ["proposer_seat: no candidate mechanism name proposed this pass (no panel "
                       "resolves, or nothing was uninterpreted) -- UNMEASURED, and every object "
                       "was judged exactly as it is without the seat"]),
                     simplified_away=simplified_away, engines=engines,
                     wiring=wiring)
    if not dry_run:
        _atomic(OUT, report)
    return report


def _report(started: float, chosen: list[str], unknown: list[str], panel_status: dict[str, Any],
            memory: dict[str, Any], plan: dict[str, Any], roi_detail: dict[str, Any],
            per_tradition: dict[str, dict[str, Any]], objects: list[MathObject],
            dedup_status: dict[str, Any], donation: dict[str, Any],
            representations: dict[str, Any], registry: dict[str, Any], dry_run: bool,
            extra_unmeasured: list[str], simplified_away: int = 0,
            engines: dict[str, E.EngineResult] | None = None,
            wiring: dict[str, Any] | None = None) -> dict[str, Any]:
    interpreted = sum(1 for o in objects if o.interpretation.status == "interpreted")
    by_kind: dict[str, int] = {}
    for obj in objects:
        by_kind[obj.kind] = by_kind.get(obj.kind, 0) + 1
    unmeasured = list(panel_status.get("unmeasured") or []) + list(extra_unmeasured)
    for tradition, row in per_tradition.items():
        unmeasured.extend(f"{tradition}/{u}" for u in row.get("unmeasured", []))
    return {
        "at": now_iso(), "rule": RULE, "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - started, 2),
        "traditions_run": chosen, "unknown_traditions": unknown,
        "departments": {"mathematics": [t for t in chosen if department_of(t) == "mathematics"],
                        "physics": [t for t in chosen if department_of(t) == "physics"],
                        **(plan.get("departments") or {})},
        "panel": panel_status, "memory": memory,
        "allocation": plan, "roi": roi_detail,
        "engines": {k: v.to_row() for k, v in (engines or {}).items()},
        "wiring_proof": wiring or I.wiring_proof(
            {}, {}, chosen, list(MATHLAB_ENGINES)),
        "per_tradition": {
            t: {**row,
                "share": plan["traditions"][t]["share"],
                "roi": plan["traditions"][t]["roi"],
                "donated": int(donation.get("by_tradition", {}).get(t, 0)),
                "objects_admitted": sum(1 for o in objects if o.tradition == t),
                "interpreted": sum(1 for o in objects
                                   if o.tradition == t
                                   and o.interpretation.status == "interpreted"),
                "uninterpreted": sum(1 for o in objects
                                     if o.tradition == t
                                     and o.interpretation.status == "uninterpreted")}
            for t, row in per_tradition.items()},
        "objects": {
            "admitted": len(objects), "simplified_away_duplicates": simplified_away,
            "by_kind": by_kind, "interpreted": interpreted,
            "uninterpreted": len(objects) - interpreted,
            "passed_burden": sum(1 for o in objects if o.passed),
            "top": [o.to_row() for o in sorted(objects, key=lambda x: -(x.value or -9e9))[:12]]},
        "dedup": dedup_status, "donation": donation, "representations": representations,
        "registry": registry,
        "effective_trials": {t: row.get("effective_trials") for t, row in per_tradition.items()},
        "unmeasured": unmeasured,
        "allocates_capital": False,
        "gauntlet": ("every donated object meets the ten gates in scripts/external_gauntlet.py "
                     "with every other hypothesis; this organ certifies nothing and the desk's "
                     "sealed trial charge is untouched"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit (the only mode)")
    ap.add_argument("--budget-s", type=float, default=3000.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and write nothing")
    ap.add_argument("--traditions", default="", help="comma-separated subset; default all 14")
    ap.add_argument("--max-targets", type=int, default=MAX_TARGETS)
    a = ap.parse_args(argv)
    chosen = [t.strip() for t in a.traditions.split(",") if t.strip()] or None
    report = run(budget_s=a.budget_s, dry_run=a.dry_run, traditions=chosen,
                 max_targets=a.max_targets)
    print(json.dumps({"at": report["at"], "elapsed_s": report["elapsed_s"],
                      "traditions": len(report["traditions_run"]),
                      "objects": report["objects"]["admitted"],
                      "passed": report["objects"]["passed_burden"],
                      "donated": report["donation"].get("donated"),
                      "unmeasured": len(report["unmeasured"])}, indent=1, default=str))
    return 0


if __name__ == "__main__":                                                # pragma: no cover
    raise SystemExit(main())
