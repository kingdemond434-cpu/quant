"""THE EXPRESSION FACTORY -- the desk's WorldQuant-style massive alpha factory (LAWS 5l, 5k;
RESEARCH 11). A 24/7 resident leg of the `factory` department.

WHAT IT DOES, in the order the law fixes: HARVEST (the graveyard's dead formula cells, the parked
formula candidates in the registry, the desk's own alpha_evolution proposals) -> TRANSFER (every
parent -- the 101 public alphas the DSL can transcribe, the grammar's canon, the harvest -- is
evaluated UNCHANGED across the loaded worlds: symbols x horizons, then sessions and regimes for a
parent that worked somewhere, with the recipe frozen) -> LIGHT MUTATION (one grammar move,
crossover, pruning a TOO_DEEP parent to the executor's depth, a window step, a horizon change,
a state condition, a basket-rank swap; parents chosen by V(a)) -> NEW INVENTION (typed random
trees, the smallest share). No parent is mutated before its transfer sweep is complete
(`TransferBeforeTuning`), which is the measured lesson of the public factories.

THE FUNNEL. Tier 0 is free: syntax / type / units through the grammar's own `is_valid`,
future-data impossibility through the fields' availability rules, duplicate AST through the DSL's
canonical form, a semantic twin through correlation with the symbol's archive, impossible
execution (an external terminal the desk cannot bind), insufficient sample. Tier 1 is one
vectorised pass: the signal's own path (z-scored on 240 bars, entered at |z| >= 1.5, held H bars,
non-overlapping), the DIRECTION chosen on the first 60% of trades and every number reported on
the last 40%, a permutation null from circularly shifted entries, coverage in trades per year,
and the desk's own round-trip cost with the cost surface's dear hours charged dearer. Tier 2 is
stability under neighbouring windows with the side FROZEN, session and regime splits, an
autocorrelation-adjusted effective sample, and a rough selection correction against the family's
trial count. Survivors are DONATED to the compiler in the seat shape it reads and recorded in
the registry as `expression_cell` discoveries with provenance to their parent; a survivor the
formula family cannot execute (a panel node, a state filter, an external terminal) is recorded
BLOCKED with the missing executor capability named, never quietly dropped.

EVERY EVALUATION IS A TRIAL, charged to its FAMILY (the canonical skeleton with the windows
blanked): EMA(19,57) and EMA(20,58) are one family. The raw count per family is kept here and
the pass's N_effective is priced by `libs/research/trial_ledger.py` (participation ratio over
descriptors and parameters, declared width per family); both ride the report.

THE CHEAP LAYER, THE NULL FACTORY, THE LOCKBOX, THE CAMPAIGN (2026-09-22). Before any tier a
cost-ordered cheap layer runs -- finite, non-constant, turnover bound, minimal IC, orthogonality
against the symbol's archive -- and a cell that fails it costs nothing more. Tier 1's null is a
FACTORY of three per candidate (circularly shifted entries, block-shuffled forward returns, a
synthetic random walk with the world's own volatility) and the worst of the three is the p the
gate reads. Every world's last LOCKBOX_FRAC of bars is sealed in `libs.validation.lockbox`'s
`LockedHoldout` and never read here. Every cell is a CAMPAIGN row: PROPOSED -> SCREENED ->
QUEUED (a registry candidate through `enqueue_candidate`, with its parent genome, mutation
chain and operator credits as provenance) -> TESTING -> FORWARD | FAILED, persisted under
data/expression_factory/ and advanced from the registry's own verdicts on the next pass. The
mutation engine draws its moves by MEASURED CREDIT (what screened, what survived), every move
dimension-preserving through `alpha_dsl.mutate`; the failure scientist records which operators
never survive on which asset classes. The QD archive is keyed (mechanism, horizon, asset class,
representation) with one ISLAND per asset class and elites migrating between them, transferred
unchanged before anything is tuned.

MEMORY-SAFE ON 8 GB: every cap (symbols loaded, subtree-cache cells, cells per pass, twins kept)
is derived from the free physical memory measured at the start of the pass, floored so an
unreadable counter changes nothing, and the pass STANDS DOWN with the reason in its report when
less than MIN_FREE_MB is free -- exactly as `miner_candidate_compiler` sizes its intake.

    python research/expression_factory.py --once --budget-s 3000
    python research/expression_factory.py --once --budget-s 120 --dry-run    # writes nothing
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_dsl as dsl  # noqa: E402
from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import trial_ledger as tl  # noqa: E402

try:
    from libs.validation.lockbox import LockedHoldout
except Exception:                                         # pragma: no cover - import guard
    LockedHoldout = None  # type: ignore[assignment, misc]

Expr = Any
SOURCE = "expression_factory"
#: The formula family's recipe, frozen: the factory measures what the executor would trade.
RECIPE: dict[str, Any] = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20,
                          "stop_atr": 2.0, "rr": 1.5}
HORIZONS: tuple[int, ...] = (8, 24)
SESSIONS: dict[str, tuple[int, int]] = {"asia": (0, 7), "london": (7, 13), "newyork": (13, 21),
                                        "late": (21, 24)}
REGIMES: tuple[str, ...] = ("low_vol", "mid_vol", "high_vol")
STAGES: tuple[str, ...] = ("harvest", "transfer", "mutation", "invention")
#: Budget shares of the four stages, in the law's order. Harvest feeds transfer, so its share is
#: the time spent READING; the harvested parents are then transferred like every other parent.
STAGE_SHARE: dict[str, float] = {"harvest": 0.10, "transfer": 0.45, "mutation": 0.35,
                                 "invention": 0.10}
MIN_FREE_MB = 400.0
BARS_PER_YEAR = 24 * 260
NORM, ENTRY_Z = 240, 1.5
IS_SHARE = 0.6
PERM_K = 24
T1 = {"finite_frac": 0.3, "n_oos": 30, "t_oos": 1.5, "p_perm": 0.10, "trades_per_year": 12.0}
T2 = {"stability": 0.5, "split_positive": 0.5, "n_eff": 40.0, "t_deflated": 1.0}
TWIN_RHO = 0.95
EXHAUST_N, EXHAUST_TAIL = 400, 200
MAX_HARVEST = 40
MAX_PARKED_PER_PASS = 24
#: THE LOCKBOX: the universal gate's sealed share of every world's bars (`universal_gate.
#: LOCKBOX_FRAC`). The factory reads the RESEARCH slice only; the tail is held by `LockedHoldout`
#: and no method here opens it.
LOCKBOX_FRAC = 0.20
LOCKBOX_MIN_BARS = 3 * NORM
#: THE CHEAP LAYER, cost-ordered: finite -> non-constant -> turnover -> minimal IC -> orthogonality.
CHEAP: dict[str, float] = {"finite_frac": 0.3, "min_unique": 20.0, "turnover_max": 0.5,
                           "ic_min": 0.002}
CHEAP_ORDER: tuple[str, ...] = ("finite", "non_constant", "turnover", "ic", "orthogonality")
#: THE NULL FACTORY: nulls per candidate -- circularly shifted entries (permutation), block-
#: shuffled forward returns (shuffle), a synthetic random walk with the world's own volatility.
NULLS: dict[str, int] = {"perm": PERM_K, "shuffle": 24, "synth": 8}
#: THE MOVES the mutation engine draws by measured credit: the DSL's six dimension-preserving
#: moves plus the factory's own three (a basket-rank swap, a horizon change, an external bind).
MOVES: tuple[str, ...] = (*dsl.MUTATIONS, "basket_swap", "horizon", "external_bind")
ISLAND_ELITES, MIGRANTS_PER_PASS = 24, 6
#: Negative knowledge: an operator tried this often on an asset class with no survivor is
#: recorded as never surviving there; its draw weight falls and nothing is vetoed.
NEG_KNOWLEDGE_N = 40
CAMPAIGN_STATES: tuple[str, ...] = ("PROPOSED", "SCREENED", "QUEUED", "TESTING", "FORWARD",
                                    "FAILED")
TRANSITIONS: dict[str, frozenset[str]] = {
    "PROPOSED": frozenset({"SCREENED", "FAILED"}), "SCREENED": frozenset({"QUEUED", "FAILED"}),
    "QUEUED": frozenset({"TESTING", "FORWARD", "FAILED"}),
    "TESTING": frozenset({"FORWARD", "FAILED"}), "FORWARD": frozenset(), "FAILED": frozenset(),
}


class TransferBeforeTuning(RuntimeError):
    """Raised when a parent is mutated before its unchanged transfer sweep has run."""


# ============================================================================ paths
@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def state_dir(self) -> Path:
        return self.desk / "data" / "expression_factory"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "EXPRESSION_FACTORY.json"

    @property
    def intel_dir(self) -> Path:
        return self.desk / "data" / "intelligence"

    @property
    def universe_dir(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def axes_dir(self) -> Path:
        return self.desk / "data" / "axes"

    @property
    def repr_dir(self) -> Path:
        return self.desk / "data" / "representations"

    @property
    def cost_surface(self) -> Path:
        return self.desk / "data" / "cost_surface.json"

    @property
    def hypothesis_graph(self) -> Path:
        return self.desk / "data" / "hypothesis_graph.jsonl"


DEFAULT_PATHS = Paths(_DESK)


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _count_by(items: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in items:
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


# ============================================================================ memory caps
def free_phys_mb() -> float | None:
    """Free physical memory: GlobalMemoryStatusEx on Windows, /proc/meminfo elsewhere, None
    when neither answers. None is UNMEASURED and every cap then takes its floor."""
    if sys.platform == "win32":
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
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            windll = getattr(ctypes, "windll", None)
            if windll is None or not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                return None
            return float(ms.ullAvailPhys) / (1024 * 1024)
        except Exception:
            return None
    try:
        txt = Path("/proc/meminfo").read_text(encoding="utf-8")
        kb = next(int(ln.split()[1]) for ln in txt.splitlines() if ln.startswith("MemAvailable:"))
        return kb / 1024.0
    except Exception:
        return None


@dataclass
class Caps:
    free_mb: float | None
    max_symbols: int
    cache_cells: int
    max_cells: int
    twin_k: int
    stood_down: bool
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"free_mb": None if self.free_mb is None else round(self.free_mb, 1),
                "max_symbols": self.max_symbols, "cache_cells": self.cache_cells,
                "max_cells": self.max_cells, "twin_k": self.twin_k,
                "stood_down": self.stood_down, "why": self.why,
                "rule": ("caps derived from measured free physical memory: symbols = free/40MB "
                         "(3..12), cache cells = 10% of free (0.5M..20M), cells = 20/MB "
                         "(200..20000), twins = free/40 (4..24); an unreadable counter takes "
                         f"the floors; below {MIN_FREE_MB:.0f} MB the pass stands down")}


def derive_caps(free_mb: float | None) -> Caps:
    if free_mb is None:
        return Caps(None, 3, 500_000, 200, 4, False, "free memory UNMEASURED: floors")
    if free_mb < MIN_FREE_MB:
        return Caps(free_mb, 0, 0, 0, 0, True,
                    f"free {free_mb:.0f} MB < {MIN_FREE_MB:.0f} MB: stood down")
    def clamp(v: float, lo: int, hi: int) -> int:
        return int(max(lo, min(hi, v)))
    return Caps(free_mb, clamp(free_mb * 0.25 / 40.0, 3, 12),
                clamp(free_mb * 0.10 * 1e6 / 8, 500_000, 20_000_000),
                clamp(free_mb * 20, 200, 20_000), clamp(free_mb / 40.0, 4, 24), False,
                f"free {free_mb:.0f} MB")


# ============================================================================ trial families
class FamilyTrials:
    """Every evaluated cell charged to its FAMILY, and the pass priced by the effective-trial
    ledger.

    The family is the canonical skeleton with its windows blanked (LAWS 5k). Two counts are
    kept and both are reported: the RAW count per family in `trial_families.json`, and
    N_effective from `libs.research.trial_ledger.census` over the pass's Trial rows
    (descriptors: symbol, horizon, state, asset class, mechanism; parameters: the windows),
    where parameter-neighbours collapse to their participation ratio and every family is
    charged its declared width. The census runs once at the end of the pass on at most
    `LEDGER_SAMPLE` members per family, each declaring the family's raw width, so the ratio
    transfers to the whole family exactly as the ledger's own docstring says it does. The old
    stated rule, N = sum_f (1 + ln n_f), is kept beside it for continuity of the reports.
    """

    LEDGER_SAMPLE = 300

    def __init__(self, path: Path) -> None:
        self.path = path
        doc = read_json(path, {})
        self.families: dict[str, dict[str, Any]] = (doc.get("families") or {}) \
            if isinstance(doc, dict) else {}
        self.pass_charges: dict[str, int] = {}
        self.trials: dict[str, list[tl.Trial]] = {}
        self._census: tl.LedgerCensus | None = None

    def charge(self, expr: Expr, n: int = 1, descriptors: dict[str, str] | None = None) -> int:
        fam = dsl.family_key(expr)
        row = self.families.setdefault(fam, {"n": 0, "first": now_iso(),
                                             "skeleton": ag.to_str(dsl.skeleton(expr)),
                                             "survivors": 0})
        row["n"] = int(row["n"]) + n
        row["last"] = now_iso()
        self.pass_charges[fam] = self.pass_charges.get(fam, 0) + n
        members = self.trials.setdefault(fam, [])
        if len(members) < self.LEDGER_SAMPLE:
            params = {f"w{i}": w for i, w in enumerate(dsl.windows_in(expr))}
            members.append(tl.Trial(f"{fam[:24]}#{self.pass_charges[fam]}", fam,
                                    dict(descriptors or {}), params))
        self._census = None
        return int(row["n"])

    def census(self) -> tl.LedgerCensus:
        """The ledger's N_effective for this pass. Every sampled member declares its family's
        raw width, so the unseen members are charged as redundant as the seen ones."""
        rows: list[tl.Trial] = []
        for fam, members in self.trials.items():
            width = max(1, self.pass_charges.get(fam, len(members)))
            rows.extend(tl.Trial(t.trial_id, t.family, t.descriptors, t.params, width)
                        for t in members)
        self._census = tl.census(rows)
        return self._census

    def survivor(self, expr: Expr) -> None:
        fam = dsl.family_key(expr)
        if fam in self.families:
            self.families[fam]["survivors"] = int(self.families[fam].get("survivors", 0)) + 1

    def pass_count(self, expr: Expr) -> int:
        return self.pass_charges.get(dsl.family_key(expr), 0)

    def n_effective(self, charges: dict[str, int] | None = None) -> float:
        rows = charges if charges is not None else {k: int(v["n"])
                                                    for k, v in self.families.items()}
        return float(sum(1.0 + math.log(max(1, n)) for n in rows.values()))

    def summary(self) -> dict[str, Any]:
        c = self._census or self.census()
        top = sorted(c.families.values(), key=lambda f: -f.n_raw)[:20]
        return {"families_lifetime": len(self.families),
                "trials_lifetime": int(sum(int(v["n"]) for v in self.families.values())),
                "n_effective_lifetime": round(self.n_effective(), 2),
                "families_this_pass": len(self.pass_charges),
                "trials_this_pass": int(sum(self.pass_charges.values())),
                "n_effective_this_pass": round(self.n_effective(self.pass_charges), 2),
                "ledger": {"n_raw": c.n_raw, "n_effective": round(c.n_effective, 2),
                           "inflation": round(c.inflation, 3), "n_families": len(c.families),
                           "basis": c.basis, "sample_per_family": self.LEDGER_SAMPLE,
                           "top_families": [f.to_dict() for f in top]},
                "mirrored_to_trial_ledger": True,
                "rule": ("windows blanked define the family; N_effective_this_pass is the stated "
                         "rule sum_f (1 + ln n_f), ledger.n_effective is trial_ledger.census "
                         "(participation ratio x declared width) and is the number the gauntlet "
                         "deflates by")}

    def save(self) -> None:
        atomic_json(self.path, {"at": now_iso(), "families": self.families,
                                "rule": self.summary()["rule"]})


# ============================================================================ the lake
@dataclass
class World:
    """One symbol's bars as terminal frames, plus what the evaluation needs beside them."""

    symbol: str
    frames: dict[str, pd.Series]
    logclose: np.ndarray
    hours: np.ndarray
    vol_regime: np.ndarray            #: 0/1/2 tercile of realised vol at each bar, -1 unknown
    cost: float                       #: round trip as a fraction of price
    hour_mult: np.ndarray             #: 24 multipliers from the cost surface
    bindings: dict[str, dsl.Field] = field(default_factory=dict)
    asset_class: str = ""
    cost_status: str = "MEASURED"
    lockbox: dict[str, Any] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.logclose.size)


def _seal(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The research slice of a world's bars and its lockbox record. The sealed tail is held by
    `libs.validation.lockbox.LockedHoldout`, whose `open_lockbox` nothing here calls: the
    factory has no method that reads it, and the record says `opened: False` because it is."""
    n = len(bars)
    if LockedHoldout is None:
        return bars, {"status": "UNMEASURED", "opened": False,
                      "why": "libs.validation.lockbox unimportable; no slice sealed"}
    if n * (1.0 - LOCKBOX_FRAC) < LOCKBOX_MIN_BARS:
        return bars, {"status": "UNSEALED", "opened": False,
                      "why": f"{n} bars leave fewer than {LOCKBOX_MIN_BARS} research bars"}
    box = LockedHoldout(bars, holdout_fraction=LOCKBOX_FRAC)
    research = box.research()
    return research, {"status": "SEALED", "frac": LOCKBOX_FRAC, "research_bars": len(research),
                      "sealed_bars": n - len(research),
                      "sealed_from": str(bars.index[box.split_index]), "opened": box.is_opened}


def _regimes(vol: pd.Series) -> np.ndarray:
    v = vol.to_numpy(dtype=float)
    out = np.full(v.size, -1, dtype=np.int8)
    ok = np.isfinite(v)
    if ok.sum() < 100:
        return out
    q1, q2 = np.nanquantile(v[ok], [1 / 3, 2 / 3])
    out[ok] = np.where(v[ok] <= q1, 0, np.where(v[ok] <= q2, 1, 2))
    return out


def _hour_multipliers(surface_row: dict[str, Any] | None) -> tuple[np.ndarray, str]:
    """Dear hours from the cost surface: the dearest hour and its neighbours pay
    `dear_over_cheap`; hours the surface calls UNMEASURED are reported as such."""
    mult = np.ones(24)
    if not isinstance(surface_row, dict):
        return mult, "UNMEASURED (no cost surface row)"
    try:
        dear = float(surface_row.get("dear_over_cheap") or 1.0)
        h_raw = surface_row.get("dearest_hour")
        if h_raw is None:
            return mult, "UNMEASURED (no dearest hour in the surface row)"
        h = int(h_raw)
    except (TypeError, ValueError):
        return mult, "UNMEASURED (surface row unreadable)"
    for k in (-1, 0, 1):
        mult[(h + k) % 24] = max(1.0, dear)
    hours = surface_row.get("hours") or {}
    unmeasured = sum(1 for v in hours.values() if isinstance(v, dict)
                     and v.get("status") == "UNMEASURED")
    return mult, ("MEASURED" if unmeasured == 0 else f"{unmeasured} hours UNMEASURED in surface")


def _every_symbol(_s: str) -> bool:
    return True


class Lake:
    """Bars, drivers, externals and costs for the symbols a pass loads."""

    def __init__(self, paths: Paths, catalogue: dsl.FieldCatalogue | None = None,
                 meta: dict[str, Any] | None = None) -> None:
        self.paths = paths
        self.catalogue = catalogue or dsl.FieldCatalogue(paths.axes_dir, paths.repr_dir)
        self.meta: dict[str, Any] = meta if meta is not None else self._meta()
        self.surface: dict[str, Any] = (read_json(paths.cost_surface, {}) or {}).get("symbols") \
            or {}
        self.worlds: dict[str, World] = {}
        self.injected: dict[str, pd.DataFrame] = {}
        self.macro_index = 0

    def _meta(self) -> dict[str, Any]:
        doc = read_json(self.paths.universe_dir / "universe.json", {})
        return {str(k).upper(): v for k, v in doc.items() if isinstance(v, dict)} \
            if isinstance(doc, dict) else {}

    # ---- which symbols
    def hypothesis_symbols(self) -> list[str]:
        allowed: Callable[[str], bool]
        try:
            from research import universe_policy as up
            allowed = up.may_hypothesise
        except Exception:
            allowed = _every_symbol
        have = sorted(p.stem.removesuffix("_H1")
                      for p in self.paths.universe_dir.glob("*_H1.parquet"))
        have += [s for s in self.injected if s not in have]
        return [s for s in have if allowed(s) or s in self.injected]

    def asset_class(self, sym: str) -> str:
        row = self.meta.get(sym.upper()) or {}
        return str(row.get("asset_class") or "unclassified").lower()

    def baskets(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for s in self.hypothesis_symbols():
            out.setdefault(self.asset_class(s), []).append(s)
        return out

    # ---- loading
    def bars(self, sym: str) -> pd.DataFrame | None:
        if sym in self.injected:
            return self.injected[sym]
        try:
            from research import proposer_common as pc
            return pc.bars(sym)
        except Exception:
            return None

    def _drivers(self, sym: str) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        if sym in self.injected:
            return out
        try:
            from mt5desk.economic_drivers import ROLES, driver_sets
            have = {p.stem.removesuffix("_H1")
                    for p in self.paths.universe_dir.glob("*_H1.parquet")}
            for ds in driver_sets(sym, self.meta, have):
                for d in ds.drivers:
                    for role, cands in ROLES.items():
                        if d in cands and role.lower() not in out:
                            b = self.bars(d)
                            if b is not None:
                                out[role.lower()] = b
        except Exception:
            pass
        return out

    def _bind_externals(self, sym: str, idx: pd.Index) -> tuple[dict[str, pd.Series],
                                                                  dict[str, dsl.Field]]:
        """One causal field per external terminal, the macro one rotating between passes."""
        extra: dict[str, pd.Series] = {}
        bound: dict[str, dsl.Field] = {}
        fields = [f for f in self.catalogue.external(sym) if f.causal()]
        for term in ("positioning", "fundamental", "macro", "event"):
            cands = [f for f in fields if f.terminal == term]
            if not cands:
                continue
            if term == "macro":
                k = self.macro_index % len(cands)
                cands = cands[k:] + cands[:k]
            for f in cands:
                s = self.catalogue.series(f, idx)
                if s is not None and bool(s.notna().sum() >= 100):
                    extra[term] = s
                    bound[term] = f
                    break
        return extra, bound

    def _cost(self, sym: str, close: pd.Series) -> float:
        if sym in self.injected:
            return 1e-4
        try:
            from research import proposer_common as pc
            c = pc.cost_frac(sym, self.meta, close)
            return float(c) if c is not None and math.isfinite(c) and c > 0 else 2e-4
        except Exception:
            return 2e-4

    def load(self, sym: str) -> World | None:
        if sym in self.worlds:
            return self.worlds[sym]
        bars = self.bars(sym)
        if bars is None or len(bars) < 3 * NORM:
            return None
        bars, lockbox = _seal(bars)
        raw = bars
        extra, bound = self._bind_externals(sym, bars.index)
        frames = ag.terminal_frames(bars, raw=raw, drivers=self._drivers(sym), extra=extra)
        close = frames["close"]
        idx = pd.DatetimeIndex(bars.index)
        mult, status = _hour_multipliers(self.surface.get(sym))
        world = World(sym, frames, np.log(close.to_numpy(dtype=float)),
                      idx.hour.to_numpy(dtype=np.int16), _regimes(frames["vol"]),
                      self._cost(sym, close), mult, bound, self.asset_class(sym), status,
                      lockbox)
        self.worlds[sym] = world
        return world

    def unload(self, sym: str) -> None:
        self.worlds.pop(sym, None)


# ============================================================================ cells
@dataclass
class Cell:
    expr: Expr
    symbol: str
    hold: int
    state: str = "none"             #: none | session:<name> | regime:<name>
    origin: str = "transfer"        #: harvest | transfer | mutation | invention
    parent: str = ""
    generator: str = ""
    asset_class: str = ""
    chain: list[str] = field(default_factory=list)   #: the mutation chain from the parent

    @property
    def key(self) -> str:
        return f"{self.symbol}|{self.hold}|{self.state}|{dsl.canonical_key(self.expr)}"

    def mechanism(self) -> str:
        """The tree's shape as the grammar describes it, with the state kind it is conditioned
        on: the MECHANISM axis of the archive."""
        shape = ag.describe(self.expr).split(": ", 1)[1].split(" of ", 1)[0]
        return f"{shape}/{self.state.split(':')[0]}"

    def representation(self) -> str:
        terms = ag.terminals_in(self.expr)
        return "+".join(("panel" if dsl.has_panel(self.expr) else "single",
                         "ext" if terms & set(ag.EXTERNAL_TERMINALS) else "bar",
                         "drv" if terms & set(ag.DRIVER_TERMINALS) else "own"))

    def descriptor(self) -> str:
        """The QD archive's key: mechanism x horizon x asset class x representation."""
        return "|".join((self.mechanism(), f"h{self.hold}", self.asset_class or "unclassified",
                         self.representation()))

    def as_dict(self) -> dict[str, Any]:
        return {"expr": self.expr, "rendered": ag.to_str(self.expr), "symbol": self.symbol,
                "hold": self.hold, "state": self.state, "origin": self.origin,
                "parent": self.parent, "generator": self.generator,
                "asset_class": self.asset_class, "chain": list(self.chain), "key": self.key,
                "family": dsl.family_key(self.expr), "mechanism": self.mechanism(),
                "representation": self.representation(), "descriptor": self.descriptor()}


def executable_by_formula_family(expr: Expr, state: str) -> str | None:
    """Why `family_formula` could NOT run this cell as written, or None when it can."""
    if state != "none":
        return f"state filter {state}: family_formula has no session/regime parameter"
    if dsl.has_panel(expr):
        return "panel node (xrank/xzscore): family_formula evaluates one instrument"
    ext = sorted(ag.terminals_in(expr) & set(ag.EXTERNAL_TERMINALS))
    if ext:
        return f"external terminal {', '.join(ext)}: the gauntlet's terminal_frames carry none"
    return None


# ============================================================================ evaluation
def _state_mask(world: World, state: str) -> np.ndarray | None:
    if state == "none":
        return None
    kind, _, name = state.partition(":")
    if kind == "session" and name in SESSIONS:
        lo, hi = SESSIONS[name]
        return np.asarray((world.hours >= lo) & (world.hours < hi))
    if kind == "regime" and name in REGIMES:
        return np.asarray(world.vol_regime == REGIMES.index(name))
    return None


def _entries(z: np.ndarray, hold: int, mask: np.ndarray | None) -> np.ndarray:
    """Non-overlapping entries where |z| >= ENTRY_Z (and the state admits), greedily."""
    ok = np.isfinite(z) & (np.abs(z) >= ENTRY_Z)
    if mask is not None:
        ok &= mask
    idx = np.flatnonzero(ok)
    idx = idx[idx < z.size - hold]
    out: list[int] = []
    last = -10 ** 9
    for i in idx.tolist():
        if i - last >= hold:
            out.append(i)
            last = i
    return np.asarray(out, dtype=np.int64)


def _gross(world: World, entries: np.ndarray, z: np.ndarray, hold: int) -> np.ndarray:
    """sign(z) x forward log return over `hold` bars, per entry (the FOLLOW side)."""
    lc = world.logclose
    return np.asarray(np.sign(z[entries]) * (lc[entries + hold] - lc[entries]))


def _costs(world: World, entries: np.ndarray) -> np.ndarray:
    return np.asarray(world.cost * world.hour_mult[world.hours[entries]])


def _tstat(x: np.ndarray) -> float:
    if x.size < 3:
        return 0.0
    sd = float(np.std(x, ddof=1))
    return float(np.mean(x) / sd * math.sqrt(x.size)) if sd > 0 else 0.0


def _zscore(v: pd.Series) -> np.ndarray:
    r = v.rolling(NORM, min_periods=NORM)
    return np.asarray(((v - r.mean()) / r.std()).to_numpy(dtype=float))


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size != a.size:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        if float(np.std(a)) <= 0 or float(np.std(b)) <= 0:
            return 0.0
        r = float(np.corrcoef(a, b)[0, 1])
    return r if math.isfinite(r) else 0.0


def cheap_screens(value: pd.Series, z: np.ndarray, world: World, hold: int,
                  twins: Sequence[tuple[str, np.ndarray]]) -> tuple[str | None, dict[str, Any]]:
    """THE CHEAP LAYER, in order of cost (`CHEAP_ORDER`): the first failing screen is returned
    with the metrics measured up to it, None when all five pass. A cell that dies here has cost
    one vectorised evaluation and nothing else -- no null, no neighbour, no gauntlet cell."""
    v = value.to_numpy(dtype=float)
    m: dict[str, Any] = {}
    finite = np.isfinite(v)
    m["finite_frac"] = round(float(finite.mean()) if v.size else 0.0, 3)
    if v.size < 3 * NORM or m["finite_frac"] < CHEAP["finite_frac"]:
        return "finite", m
    fv = v[finite]
    sample = fv[:: max(1, fv.size // 4000)]
    m["unique"] = int(np.unique(sample).size)
    if float(np.std(fv)) <= 0.0 or m["unique"] < CHEAP["min_unique"]:
        return "non_constant", m
    pos = np.where(np.isfinite(z) & (np.abs(z) >= ENTRY_Z), np.sign(z), 0.0)
    m["turnover"] = round(float(np.mean(np.abs(np.diff(pos))) / 2.0), 4) if pos.size > 1 else 0.0
    if m["turnover"] > CHEAP["turnover_max"]:
        return "turnover", m
    fwd = np.roll(world.logclose, -hold) - world.logclose
    ok = np.isfinite(z) & np.isfinite(fwd)
    ok[-hold:] = False
    m["ic"] = round(_corr(z[ok], fwd[ok]), 5) if ok.sum() > 100 else 0.0
    if abs(m["ic"]) < CHEAP["ic_min"]:
        return "ic", m
    rho_max = 0.0
    for _k, zt in twins:
        both = np.isfinite(z) & np.isfinite(zt)
        if both.sum() > 500:
            rho_max = max(rho_max, abs(_corr(z[both], zt[both])))
    m["rho_max"] = round(rho_max, 3)
    if rho_max >= TWIN_RHO:
        return "orthogonality", m
    return None, m


def null_factory(world: World, entries: np.ndarray, z: np.ndarray, side: int, hold: int,
                 observed: float, rng: np.random.Generator) -> dict[str, Any]:
    """THREE NULLS PER CANDIDATE, each keeping the trade structure (count, hold, side, cost)
    and destroying exactly one thing. PERMUTATION shifts the entries circularly (the
    alignment); SHUFFLE block-shuffles the forward returns in blocks of `hold` bars (the
    path's order); SYNTHETIC re-reads the same entries on a Gaussian random walk with the
    world's own bar volatility (the path itself). Each p is the share of nulls at or above the
    observed net; the gate reads the WORST of the three."""
    lc = world.logclose
    n = lc.size
    span = n - hold - 1
    k = dict(NULLS)
    if entries.size == 0 or span <= hold:
        return {"p_perm": 1.0, "p_shuffle": 1.0, "p_synth": 1.0, "p_null": 1.0,
                "worst": "empty", "k": k}
    sgn = side * np.sign(z[entries])
    cost = _costs(world, entries)
    perm = np.empty(k["perm"])
    for i in range(k["perm"]):
        shift = int(rng.integers(hold, span))
        e = (entries + shift) % span
        perm[i] = float(np.mean(sgn * (lc[e + hold] - lc[e]) - _costs(world, e)))
    fwd = lc[hold:] - lc[:-hold]
    nb = max(1, fwd.size // hold)
    blocks = fwd[:nb * hold].reshape(nb, hold)
    shuf = np.empty(k["shuffle"])
    for i in range(k["shuffle"]):
        f = blocks[rng.permutation(nb)].reshape(-1)
        e = entries < f.size
        shuf[i] = float(np.mean(sgn[e] * f[entries[e]] - cost[e])) if e.any() else -np.inf
    r = np.diff(lc)
    r = r[np.isfinite(r)]
    sd = float(np.std(r)) if r.size > 10 else 0.0
    syn = np.empty(k["synth"])
    for i in range(k["synth"]):
        path = np.concatenate([[0.0], np.cumsum(rng.normal(0.0, sd, n - 1))]) if sd > 0 \
            else np.zeros(n)
        syn[i] = float(np.mean(sgn * (path[entries + hold] - path[entries]) - cost))
    ps = {"permutation": float(np.mean(perm >= observed)),
          "shuffle": float(np.mean(shuf >= observed)),
          "synthetic": float(np.mean(syn >= observed))}
    worst = max(ps, key=lambda q: ps[q])
    return {"p_perm": ps["permutation"], "p_shuffle": ps["shuffle"], "p_synth": ps["synthetic"],
            "p_null": ps[worst], "worst": worst, "k": k}


@dataclass
class Tier1:
    passed: bool
    reason: str
    side: int = 1
    n_is: int = 0
    n_oos: int = 0
    gross_is: float = 0.0
    net_oos: float = 0.0
    t_oos: float = 0.0
    p_perm: float = 1.0
    trades_per_year: float = 0.0
    finite_frac: float = 0.0
    ic: float = 0.0
    n_all: int = 0
    net_all: float = 0.0
    t_all: float = 0.0
    entries: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    oos_returns: np.ndarray = field(default_factory=lambda: np.zeros(0))
    z: np.ndarray | None = None
    p_shuffle: float = 1.0
    p_synth: float = 1.0
    p_null: float = 1.0
    worst_null: str = ""

    def metrics(self) -> dict[str, Any]:
        return {"passed": self.passed, "reason": self.reason,
                "side_mode": "follow" if self.side > 0 else "fade", "n_is": self.n_is,
                "n_oos": self.n_oos, "gross_is": round(self.gross_is, 7),
                "net_oos": round(self.net_oos, 7), "t_oos": round(self.t_oos, 3),
                "p_perm": round(self.p_perm, 3), "p_shuffle": round(self.p_shuffle, 3),
                "p_synth": round(self.p_synth, 3), "p_null": round(self.p_null, 3),
                "worst_null": self.worst_null,
                "trades_per_year": round(self.trades_per_year, 1),
                "finite_frac": round(self.finite_frac, 3), "ic": round(self.ic, 4),
                "n_all": self.n_all, "net_all": round(self.net_all, 7),
                "t_all": round(self.t_all, 3)}


def tier1(cell: Cell, world: World, value: pd.Series, rng: np.random.Generator) -> Tier1:
    v = value.to_numpy(dtype=float)
    finite = float(np.isfinite(v).mean()) if v.size else 0.0
    if v.size < 3 * NORM or finite < T1["finite_frac"]:
        return Tier1(False, f"insufficient sample: finite {finite:.2f} of {v.size} bars",
                     finite_frac=finite)
    z = _zscore(value)
    entries = _entries(z, cell.hold, _state_mask(world, cell.state))
    n = int(entries.size)
    years = max(0.25, world.n / BARS_PER_YEAR)
    tpy = n / years
    if n < T1["n_oos"] + 10:
        return Tier1(False, f"too few trades: {n}", finite_frac=finite, trades_per_year=tpy,
                     n_all=n)
    gross = _gross(world, entries, z, cell.hold)
    cost = _costs(world, entries)
    cut = int(n * IS_SHARE)
    side = 1 if float(np.mean(gross[:cut])) >= 0 else -1
    net = side * gross - cost
    oos = net[cut:]
    n_oos = int(oos.size)
    net_oos, t_oos = float(np.mean(oos)), _tstat(oos)
    # THE NULL FACTORY: permutation, shuffle and synthetic nulls of the OOS trades, the same
    # trade structure each time; the worst of the three is the p the gate reads.
    nulls = null_factory(world, entries[cut:], z, side, cell.hold, net_oos, rng)
    p_perm = float(nulls["p_perm"])
    fwd = np.roll(world.logclose, -cell.hold) - world.logclose
    ok = np.isfinite(z) & np.isfinite(fwd)
    ok[-cell.hold:] = False
    ic = _corr(z[ok], fwd[ok]) if ok.sum() > 100 else 0.0
    t = Tier1(True, "ok", side, cut, n_oos, float(np.mean(gross[:cut])), net_oos, t_oos, p_perm,
              tpy, finite, ic, n, float(np.mean(net)), _tstat(net), entries, oos, z,
              float(nulls["p_shuffle"]), float(nulls["p_synth"]), float(nulls["p_null"]),
              str(nulls["worst"]))
    if n_oos < T1["n_oos"]:
        t.passed, t.reason = False, f"n_oos {n_oos} < {T1['n_oos']}"
    elif tpy < T1["trades_per_year"]:
        t.passed, t.reason = False, f"coverage {tpy:.1f} trades/year < {T1['trades_per_year']}"
    elif net_oos <= 0:
        t.passed, t.reason = False, f"net_oos {net_oos:.2e} <= 0 after cost"
    elif t_oos < T1["t_oos"]:
        t.passed, t.reason = False, f"t_oos {t_oos:.2f} < {T1['t_oos']}"
    elif t.p_null > T1["p_perm"]:
        t.passed, t.reason = False, (f"null factory p {t.p_null:.2f} > {T1['p_perm']} "
                                     f"({t.worst_null} null)")
    return t


def _neighbours(expr: Expr, rng: np.random.Generator, limit: int = 6) -> list[Expr]:
    """Each windowed node stepped one grammar window down and up, the rest frozen."""
    out: list[Expr] = []
    paths = [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), list)
             and str(ag._get(expr, p)[0]) in ag.WINDOWED + ag.BINARY_WINDOWED]
    rng.shuffle(paths)
    for p in paths:
        node = ag._get(expr, p)
        w = int(node[-1])
        i = ag.WINDOWS.index(w) if w in ag.WINDOWS else -1
        for j in (i - 1, i + 1):
            if 0 <= j < len(ag.WINDOWS) and i >= 0:
                new = list(node)
                new[-1] = int(ag.WINDOWS[j])
                cand = ag._set(ag._clone(expr), p, new)
                if ag.is_valid(cand):
                    out.append(cand)
        if len(out) >= limit:
            break
    return out[:limit]


@dataclass
class Tier2:
    passed: bool
    reason: str
    stability: float | None = None
    n_neighbours: int = 0
    splits: dict[str, float] = field(default_factory=dict)
    split_positive: float | None = None
    n_eff: float = 0.0
    t_deflated: float = 0.0
    family_trials: int = 0
    worst_split: str = ""

    def metrics(self) -> dict[str, Any]:
        return {"passed": self.passed, "reason": self.reason,
                "stability": "UNMEASURED" if self.stability is None else round(self.stability, 2),
                "n_neighbours": self.n_neighbours,
                "splits": {k: round(v, 7) for k, v in self.splits.items()},
                "split_positive": ("UNMEASURED" if self.split_positive is None
                                   else round(self.split_positive, 2)),
                "n_eff": round(self.n_eff, 1), "t_deflated": round(self.t_deflated, 3),
                "family_trials_this_pass": self.family_trials, "worst_split": self.worst_split}


def tier2(cell: Cell, world: World, t1: Tier1, evaluate: Any, rng: np.random.Generator,
          families: FamilyTrials) -> Tier2:
    """Stability, splits, effective sample, rough selection correction. Side FROZEN."""
    out = Tier2(True, "ok")
    # 1. neighbouring windows, the side frozen, every neighbour charged as a trial
    neigh = _neighbours(cell.expr, rng)
    held = 0
    for e in neigh:
        families.charge(e)
        v = evaluate(e)
        z = _zscore(v)
        ent = _entries(z, cell.hold, _state_mask(world, cell.state))
        if ent.size < 20:
            continue
        cut = int(ent.size * IS_SHARE)
        net = t1.side * _gross(world, ent, z, cell.hold) - _costs(world, ent)
        held += int(float(np.mean(net[cut:])) > 0)
    out.n_neighbours = len(neigh)
    out.stability = (held / len(neigh)) if neigh else None
    # 2. session and regime splits of the OOS trades
    oos_entries = t1.entries[t1.n_is:]
    hours = world.hours[oos_entries]
    regs = world.vol_regime[oos_entries]
    splits: dict[str, float] = {}
    for name, (lo, hi) in SESSIONS.items():
        m = (hours >= lo) & (hours < hi)
        if m.sum() >= 10:
            splits[f"session:{name}"] = float(np.mean(t1.oos_returns[m]))
    for i, name in enumerate(REGIMES):
        m = regs == i
        if m.sum() >= 10:
            splits[f"regime:{name}"] = float(np.mean(t1.oos_returns[m]))
    out.splits = splits
    out.split_positive = (sum(1 for v in splits.values() if v > 0) / len(splits)) if splits \
        else None
    out.worst_split = min(splits, key=lambda k: splits[k]) if splits else ""
    # 3. effective sample: lag-1 autocorrelation of the OOS trade returns
    r = t1.oos_returns
    rho = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if r.size > 3 and np.std(r) > 0 else 0.0
    rho = 0.0 if not math.isfinite(rho) else max(0.0, rho)
    out.n_eff = float(r.size / (1.0 + 2.0 * rho))
    # 4. rough selection correction against the family's trials THIS pass
    out.family_trials = max(1, families.pass_count(cell.expr))
    try:
        from research.multiplicity import deflate_t
        out.t_deflated = float(deflate_t(t1.t_all, out.family_trials))
    except Exception:
        out.t_deflated = float(t1.t_all - math.sqrt(2.0 * math.log(max(2, out.family_trials))))
    if out.stability is not None and out.stability < T2["stability"]:
        out.passed, out.reason = False, f"stability {out.stability:.2f} < {T2['stability']}"
    elif out.split_positive is not None and out.split_positive < T2["split_positive"]:
        out.passed, out.reason = False, (f"split_positive {out.split_positive:.2f} < "
                                         f"{T2['split_positive']} (worst {out.worst_split})")
    elif out.n_eff < T2["n_eff"]:
        out.passed, out.reason = False, f"n_eff {out.n_eff:.0f} < {T2['n_eff']}"
    elif out.t_deflated < T2["t_deflated"]:
        out.passed, out.reason = False, (f"t_deflated {out.t_deflated:.2f} < {T2['t_deflated']} "
                                         f"at {out.family_trials} family trials")
    return out


# ============================================================================ parents
@dataclass
class Parent:
    pid: str
    expr: Expr
    kind: str                        #: alpha101 | canon | harvest
    status: str = "TESTABLE"         #: TESTABLE | TOO_DEEP
    evaluated: int = 0
    tier1_pass: int = 0
    tier2_pass: int = 0
    transfers_held: list[str] = field(default_factory=list)
    gains: list[float] = field(default_factory=list)
    orth: list[float] = field(default_factory=list)
    recent: list[int] = field(default_factory=list)    #: 1/0 tier-1 results, last EXHAUST_TAIL
    axes: dict[str, list[str]] = field(default_factory=dict)
    transferred: bool = False
    chain: list[str] = field(default_factory=list)

    def value(self, families: FamilyTrials, archive_n: int) -> float:
        """V(a) = P(survive|D) x E[dG|survive] x Novelty x Orthogonality x InformationGain /
        (Compute + DataCost + TrialCost + Delay)."""
        p_surv = (self.tier1_pass + 0.5) / (self.evaluated + 10.0)
        e_gain = float(np.mean(self.gains)) if self.gains else 1e-4
        novelty = 1.0 / (1.0 + archive_n)
        orth = float(np.mean(self.orth)) if self.orth else 0.5
        info = 1.0 / math.sqrt(1.0 + self.evaluated)
        compute = 1.0 + ag.complexity(self.expr) / 10.0
        data = 1.0 + len(ag.terminals_in(self.expr) & set(ag.EXTERNAL_TERMINALS))
        trial = 1.0 + math.log1p(families.pass_count(self.expr))
        delay = 1.0
        return p_surv * max(e_gain, 1e-6) * novelty * max(orth, 0.05) * info / (
            compute + data + trial + delay)

    def exhausted(self) -> bool:
        return (self.evaluated >= EXHAUST_N and len(self.recent) >= EXHAUST_TAIL
                and sum(self.recent[-EXHAUST_TAIL:]) == 0)

    def as_dict(self) -> dict[str, Any]:
        return {"pid": self.pid, "kind": self.kind, "status": self.status,
                "rendered": ag.to_str(self.expr), "evaluated": self.evaluated,
                "tier1_pass": self.tier1_pass, "tier2_pass": self.tier2_pass,
                "transfers_held": sorted(set(self.transfers_held)),
                "mean_gain": round(float(np.mean(self.gains)), 7) if self.gains else None,
                "exhausted": self.exhausted(), "axes_tried": {k: sorted(set(v))[:40]
                                                              for k, v in self.axes.items()},
                "transferred": self.transferred}


def _prune(expr: Expr, rng: np.random.Generator) -> Expr:
    """A TOO_DEEP tree cut to the executor's depth: a random subtree at the right depth."""
    e = expr
    for _ in range(12):
        if ag.depth(e) <= ag.MAX_DEPTH:
            return e
        kids = [c for c in e[1:] if isinstance(c, (list, str))]
        e = kids[int(rng.integers(len(kids)))] if kids else e
    return e


# ============================================================================ credits
class Credits:
    """SEARCH-METHOD EVOLUTION: per-operator and per-move credit from what screens and what
    survives, and the failure scientist's negative knowledge -- which operators never survive
    on which asset classes. The mutation engine draws its moves by `move_weights`, so the
    budget flows toward what earns; a never-surviving (operator, asset class) pair is REPORTED
    with its trial count and its draw weight falls. Nothing is vetoed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        doc = read_json(path, {}) or {}
        self.ops: dict[str, dict[str, int]] = dict(doc.get("operators") or {})
        self.moves: dict[str, dict[str, int]] = dict(doc.get("moves") or {})
        self.negative: dict[str, dict[str, int]] = dict(doc.get("negative") or {})
        self.pass_moves: dict[str, dict[str, int]] = {}

    @staticmethod
    def _bump(table: dict[str, dict[str, int]], key: str, what: str) -> None:
        row = table.setdefault(key, {"trials": 0, "screened": 0, "survivors": 0})
        row[what] = int(row.get(what, 0)) + 1

    def _touch(self, expr: Expr, move: str, klass: str, what: str) -> None:
        for op in dsl.operators_in(expr):
            self._bump(self.ops, op, what)
            self._bump(self.negative, f"{op}|{klass or 'unclassified'}", what)
        if move:
            self._bump(self.moves, move, what)
            self._bump(self.pass_moves, move, what)

    def charge(self, expr: Expr, move: str, klass: str) -> None:
        self._touch(expr, move, klass, "trials")

    def screened(self, expr: Expr, move: str, klass: str) -> None:
        self._touch(expr, move, klass, "screened")

    def survivor(self, expr: Expr, move: str, klass: str) -> None:
        self._touch(expr, move, klass, "survivors")

    @staticmethod
    def credit(row: dict[str, int] | None) -> float:
        r = row or {}
        return (2.0 * int(r.get("survivors", 0)) + int(r.get("screened", 0)) + 0.5) / (
            int(r.get("trials", 0)) + 5.0)

    def move_weights(self, moves: Sequence[str]) -> np.ndarray:
        w = np.array([self.credit(self.moves.get(m)) for m in moves], dtype=float)
        w = np.maximum(w, 1e-6)
        return np.asarray(w / w.sum())

    def op_weight(self, op: str, klass: str) -> float:
        return self.credit(self.negative.get(f"{op}|{klass or 'unclassified'}"))

    def never_survives(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, row in self.negative.items():
            if int(row.get("trials", 0)) >= NEG_KNOWLEDGE_N and int(row.get("survivors", 0)) == 0:
                op, _, klass = key.partition("|")
                out.append({"operator": op, "asset_class": klass, "trials": int(row["trials"]),
                            "screened": int(row.get("screened", 0)),
                            "verdict": "never survived here (measured)"})
        return sorted(out, key=lambda r: -int(r["trials"]))

    def summary(self, moves: Sequence[str]) -> dict[str, Any]:
        weights = self.move_weights(moves)
        ranked = sorted(self.ops.items(), key=lambda kv: -self.credit(kv[1]))[:40]
        return {"moves": {m: {**self.moves.get(m, {}), "credit": round(self.credit(
            self.moves.get(m)), 4)} for m in moves},
            "move_weights": {m: round(float(w), 4) for m, w in zip(moves, weights, strict=True)},
            "moves_this_pass": self.pass_moves,
            "operators": {op: {**row, "credit": round(self.credit(row), 4)} for op, row in ranked},
            "negative_knowledge": self.never_survives()[:60],
            "n_negative_pairs": len(self.negative),
            "rule": ("credit = (2 survivors + screened + 0.5) / (trials + 5); the mutation "
                     "engine draws its moves by this weight so budget flows toward what earns; "
                     f"an (operator, asset class) pair with >= {NEG_KNOWLEDGE_N} trials and no "
                     "survivor is negative knowledge: reported, weight lowered, never vetoed")}

    def save(self) -> None:
        atomic_json(self.path, {"at": now_iso(), "operators": self.ops, "moves": self.moves,
                                "negative": self.negative})


# ============================================================================ campaign
class CampaignError(RuntimeError):
    """An illegal campaign transition, or a transition on a row that was never proposed."""


class Campaign:
    """THE CAMPAIGN STATE MACHINE: PROPOSED -> SCREENED -> QUEUED -> TESTING -> FORWARD |
    FAILED, persisted as an append-only `campaign.jsonl` of transitions plus a `campaign.json`
    snapshot of every row that reached the cheap layer (rows that died in it are counted, not
    kept). QUEUED and TESTING rows are advanced from the registry's own status on the next pass
    (`refresh`): the ONE gauntlet judges, this machine only records where each cell stands."""

    def __init__(self, state_dir: Path) -> None:
        self.snapshot = state_dir / "campaign.json"
        self.journal = state_dir / "campaign.jsonl"
        doc = read_json(self.snapshot, {}) or {}
        self.rows: dict[str, dict[str, Any]] = dict(doc.get("rows") or {})
        self.lifetime: dict[str, int] = dict(doc.get("lifetime") or {})
        self.pass_counts: dict[str, int] = dict.fromkeys(CAMPAIGN_STATES, 0)
        self.transitions: list[dict[str, Any]] = []

    def propose(self, cell: Cell) -> dict[str, Any]:
        row = self.rows.get(cell.key)
        if row is not None:
            return row
        row = {"state": "PROPOSED", "at": now_iso(), "symbol": cell.symbol, "hold": cell.hold,
               "state_filter": cell.state, "origin": cell.origin, "parent": cell.parent,
               "generator": cell.generator, "chain": list(cell.chain),
               "rendered": ag.to_str(cell.expr), "family": dsl.family_key(cell.expr),
               "asset_class": cell.asset_class, "candidate_id": "", "history": ["PROPOSED"]}
        self.rows[cell.key] = row
        self.pass_counts["PROPOSED"] += 1
        return row

    def state_of(self, key: str) -> str | None:
        row = self.rows.get(key)
        return None if row is None else str(row["state"])

    def advance(self, key: str, state: str, **why: Any) -> dict[str, Any]:
        row = self.rows.get(key)
        if row is None:
            raise CampaignError(f"{key[:60]}: never PROPOSED")
        if state not in CAMPAIGN_STATES:
            raise CampaignError(f"{state!r} is not one of {CAMPAIGN_STATES}")
        cur = str(row["state"])
        if state not in TRANSITIONS[cur]:
            raise CampaignError(f"{cur} -> {state} is not a legal transition")
        row["state"], row["at"] = state, now_iso()
        row["history"].append(state)
        row.update(why)
        self.pass_counts[state] += 1
        self.transitions.append({"at": row["at"], "key": key, "from": cur, "to": state,
                                 **{k: str(v)[:200] for k, v in why.items()}})
        return row

    def fail(self, key: str, why: str) -> None:
        row = self.rows.get(key)
        if row is not None and row["state"] not in ("FORWARD", "FAILED"):
            self.advance(key, "FAILED", why=why)

    def refresh(self, conn: Any) -> dict[str, int]:
        """QUEUED / TESTING rows re-read from the registry: claimed -> TESTING; survived ->
        FORWARD; judged and not survived -> FAILED with the failing gate named."""
        moved = {"TESTING": 0, "FORWARD": 0, "FAILED": 0, "unchanged": 0}
        for key, row in list(self.rows.items()):
            if row["state"] not in ("QUEUED", "TESTING") or not row.get("candidate_id"):
                continue
            cid = str(row["candidate_id"])
            r = conn.execute("SELECT status, survived, terminal_gate, failure_class FROM "
                             "research_candidates WHERE id=? OR donated_cell=?",
                             (cid, cid)).fetchone()
            if r is None:
                moved["unchanged"] += 1
                continue
            status = str(r["status"] or "").lower()
            survived = int(r["survived"] or 0)
            if survived or status in ("survived", "certified", "promoted", "live"):
                self.advance(key, "FORWARD", registry_status=status)
                moved["FORWARD"] += 1
            elif status in ("judged", "failed", "rejected", "retired", "killed"):
                self.advance(key, "FAILED", why=f"registry {status}: "
                             f"{r['failure_class'] or r['terminal_gate'] or 'gate'}")
                moved["FAILED"] += 1
            elif status in ("claimed", "testing", "running") and row["state"] == "QUEUED":
                self.advance(key, "TESTING", registry_status=status)
                moved["TESTING"] += 1
            else:
                moved["unchanged"] += 1
        return moved

    def counts(self) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        for r in self.rows.values():
            by_state[str(r["state"])] = by_state.get(str(r["state"]), 0) + 1
        return {"this_pass": dict(self.pass_counts), "rows_by_state": by_state,
                "lifetime": dict(self.lifetime), "rows_kept": len(self.rows),
                "states": list(CAMPAIGN_STATES),
                "transitions": {k: sorted(v) for k, v in TRANSITIONS.items()}}

    def save(self, keep_terminal: int = 2000) -> list[Path]:
        for state, n in self.pass_counts.items():
            self.lifetime[state] = self.lifetime.get(state, 0) + n
        keep = {k: r for k, r in self.rows.items()
                if r["state"] != "PROPOSED" and not (r["state"] == "FAILED"
                                                     and len(r["history"]) == 2)}
        terminal = [k for k, r in keep.items() if r["state"] in ("FORWARD", "FAILED")]
        for k in terminal[:max(0, len(terminal) - keep_terminal)]:
            keep.pop(k)
        self.rows = keep
        atomic_json(self.snapshot, {"at": now_iso(), "states": list(CAMPAIGN_STATES),
                                    "transitions": {k: sorted(v) for k, v in TRANSITIONS.items()},
                                    "rows": keep, "lifetime": self.lifetime})
        if self.transitions:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("a", encoding="utf-8") as fh:
                for t in self.transitions[-5000:]:
                    fh.write(json.dumps(t, default=str) + "\n")
        return [self.snapshot, self.journal]


# ============================================================================ the factory
class Factory:
    def __init__(self, paths: Paths = DEFAULT_PATHS, *, lake: Lake | None = None,
                 seed: int | None = None, dry_run: bool = False, registry: Any = None) -> None:
        self.paths = paths
        self.dry_run = dry_run
        self.rng = np.random.default_rng(seed)
        self.lake = lake or Lake(paths)
        self.families = FamilyTrials(paths.state_dir / "trial_families.json")
        self.state: dict[str, Any] = read_json(paths.state_dir / "state.json", {}) or {}
        self.archive: dict[str, dict[str, Any]] = (read_json(paths.state_dir / "archive.json", {})
                                                   or {}).get("cells", {})
        self.seen: set[str] = set((read_json(paths.state_dir / "seen.json", {}) or {})
                                  .get("keys", [])[-50_000:])
        self.parents: dict[str, Parent] = {}
        self.parent_book: dict[str, dict[str, Any]] = (read_json(paths.state_dir / "parents.json",
                                                                 {}) or {}).get("parents", {})
        self.registry = registry
        self.caps = derive_caps(free_phys_mb())
        self.twins: dict[str, list[tuple[str, np.ndarray]]] = {}
        self.credits = Credits(paths.state_dir / "credits.json")
        self.campaign = Campaign(paths.state_dir)
        self.islands: dict[str, dict[str, Any]] = (read_json(paths.state_dir / "islands.json",
                                                             {}) or {}).get("islands", {})
        self.counts: dict[str, Any] = {
            "generated": dict.fromkeys(STAGES, 0), "tier0": {"evaluated": 0, "rejected": {}},
            "cheap": {"passed": 0, "rejected": {}},
            "tier1": {"evaluated": 0, "passed": 0, "rejected": {}},
            "tier2": {"evaluated": 0, "passed": 0, "rejected": {}},
            "survivors": [], "blocked": [], "transfers_held": 0, "transfer_cells": 0,
            "mutations": {"by_move": {}, "by_trial_family": {}, "noop": {}}, "migrants": 0,
        }
        self.memos: dict[str, Any] = {}
        self.cache: Any = None
        self.log: list[str] = []
        self.started = time.monotonic()
        self.budget_s = 0.0
        self.cells_done = 0

    # ---- bookkeeping
    def say(self, msg: str) -> None:
        self.log.append(f"{now_iso()} {msg}")
        print(f"factory: {msg}", flush=True)

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def out_of_budget(self, stage: str | None = None) -> bool:
        if self.cells_done >= self.caps.max_cells:
            return True
        if stage is None:
            return self.elapsed() >= self.budget_s
        cutoff = sum(STAGE_SHARE[s] for s in STAGES[:STAGES.index(stage) + 1])
        return self.elapsed() >= self.budget_s * cutoff

    def _reject(self, tier: str, why: str) -> None:
        m = re.match(r"[A-Za-z_ :/]+", why)
        key = (m.group(0) if m else why).strip()[:60] or why[:60]
        d = self.counts[tier]["rejected"]
        d[key] = d.get(key, 0) + 1

    def memo_for(self, sym: str) -> Any:
        if sym not in self.memos:
            w = self.lake.worlds[sym]
            self.memos[sym] = (self.cache.scope(sym, w.frames) if self.cache is not None
                               else {})
        return self.memos[sym]

    def evaluate(self, expr: Expr, sym: str) -> pd.Series:
        frames = {s: w.frames for s, w in self.lake.worlds.items()
                  if w.asset_class == self.lake.worlds[sym].asset_class}
        if dsl.has_panel(expr):
            for s in frames:
                self.memo_for(s)
            return dsl.evaluate_cell(expr, frames, sym, self.memos)
        return ag.evaluate(expr, self.lake.worlds[sym].frames, self.memo_for(sym))

    # ---- parents
    def _parent(self, pid: str, expr: Expr, kind: str, status: str = "TESTABLE") -> Parent:
        if pid in self.parents:
            return self.parents[pid]
        p = Parent(pid, expr, kind, status)
        book = self.parent_book.get(pid) or {}
        p.evaluated = int(book.get("evaluated", 0))
        p.tier1_pass = int(book.get("tier1_pass", 0))
        p.tier2_pass = int(book.get("tier2_pass", 0))
        p.transfers_held = list(book.get("transfers_held", []))
        p.recent = list(book.get("recent", []))[-EXHAUST_TAIL:]
        p.axes = {k: list(v) for k, v in (book.get("axes_tried") or {}).items()}
        self.parents[pid] = p
        return p

    def load_parents(self) -> dict[str, Any]:
        census = dsl.genome_census()
        for aid, g in dsl.parent_genomes().items():
            if g.tree is not None and g.status in ("TESTABLE", "TOO_DEEP"):
                self._parent(aid, g.tree, "alpha101", g.status)
        for name, e in ag.CANON.items():
            self._parent(f"canon:{name}", e, "canon")
        return census

    def harvest(self) -> dict[str, Any]:
        """The graveyard and the parked candidates FIRST: dead and waiting formula cells."""
        found: dict[str, Expr] = {}
        n_dead = n_parked = n_own = 0
        # the graveyard: dead formula cells with their expression
        tail: list[dict[str, Any]] = []
        try:
            with self.paths.hypothesis_graph.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 6_000_000))
                for ln in fh.read().decode("utf-8", "replace").splitlines()[1:]:
                    try:
                        tail.append(json.loads(ln))
                    except ValueError:
                        continue
        except OSError:
            pass
        for row in tail:
            if str(row.get("family")) != "formula":
                continue
            if str(row.get("fate") or "").upper() not in ("FAILED", "RETIRED", "KILLED"):
                continue
            e = (row.get("params") or {}).get("expr")
            if e is not None and ag.is_valid(e):
                n_dead += 1
                found.setdefault(f"graveyard:{dsl.canonical_key(e)[:24]}", e)
        # parked: registry candidates of the formula family not yet judged
        if self.registry is not None:
            try:
                for c in self.registry.candidates(limit=2000):
                    if str(c.get("family")) != "formula":
                        continue
                    if str(c.get("status") or "") not in ("queued", "donated", "parked"):
                        continue
                    params = c.get("params_json") or c.get("params") or "{}"
                    params = json.loads(params) if isinstance(params, str) else params
                    e = (params or {}).get("expr")
                    if e is not None and ag.is_valid(e):
                        n_parked += 1
                        found.setdefault(f"parked:{dsl.canonical_key(e)[:24]}", e)
                        if n_parked >= MAX_PARKED_PER_PASS:
                            break
            except Exception as exc:
                self.say(f"harvest: registry unreadable ({type(exc).__name__}: {exc})")
        # the desk's own formula proposals
        src = self.paths.intel_dir / "alpha_evolution"
        for f in sorted(src.glob("discoveries_*.json"), reverse=True)[:3]:
            doc = read_json(f, {})
            for row in (doc.get("discoveries") or []) if isinstance(doc, dict) else []:
                e = ((row or {}).get("params") or {}).get("expr")
                if e is not None and ag.is_valid(e):
                    n_own += 1
                    found.setdefault(f"own:{dsl.canonical_key(e)[:24]}", e)
        keys = sorted(found)
        cursor = int(self.state.get("harvest_cursor", 0))
        take = keys[cursor:cursor + MAX_HARVEST] + keys[:max(0, cursor + MAX_HARVEST - len(keys))]
        self.state["harvest_cursor"] = (cursor + MAX_HARVEST) % max(1, len(keys))
        for k in take:
            self._parent(k, found[k], "harvest")
        return {"graveyard_dead": n_dead, "parked": n_parked, "own_proposals": n_own,
                "harvested_parents": len(take), "cursor": self.state["harvest_cursor"]}

    # ---- the funnel on one cell
    def run_cell(self, cell: Cell, parent: Parent | None) -> dict[str, Any]:
        """Tier 0 -> Tier 1 -> Tier 2 on one cell; every evaluation charged. Never raises."""
        self.counts["generated"][cell.origin] = self.counts["generated"].get(cell.origin, 0) + 1
        self.counts["tier0"]["evaluated"] += 1
        if cell.origin == "mutation":
            # EVERY MUTATION COUNTED BY FAMILY (LAWS 5k): by the move that made it and by the
            # trial family it lands in, whether or not it compiles or is new.
            bm = self.counts["mutations"]["by_move"]
            bm[cell.generator] = bm.get(cell.generator, 0) + 1
            fam = dsl.family_key(cell.expr)
            bf = self.counts["mutations"]["by_trial_family"]
            bf[fam] = bf.get(fam, 0) + 1
        world = self.lake.worlds.get(cell.symbol)
        if world is None:
            self._reject("tier0", "impossible execution: symbol not loaded")
            return {"tier": 0, "why": "symbol not loaded"}
        if not cell.asset_class:
            cell.asset_class = world.asset_class
        try:
            compiled = dsl.compile_expr(cell.expr, terminals=ag.available_terminals(world.frames))
        except dsl.CompileError as exc:
            self._reject("tier0", "syntax/type/units")
            return {"tier": 0, "why": f"compile: {exc}"}
        cell.expr = compiled.expr
        why = dsl.future_data_impossible(cell.expr, world.bindings)
        if why:
            self._reject("tier0", "future data: " + why)
            return {"tier": 0, "why": "future data: " + why}
        if cell.key in self.seen:
            self._reject("tier0", "duplicate AST")
            return {"tier": 0, "why": "duplicate AST"}
        self.seen.add(cell.key)
        self.cells_done += 1
        self.campaign.propose(cell)
        self.families.charge(cell.expr, descriptors={
            "symbol": cell.symbol, "horizon": str(cell.hold), "state": cell.state,
            "asset_class": cell.asset_class, "mechanism": cell.mechanism()})
        self.credits.charge(cell.expr, cell.generator, cell.asset_class)
        if parent is not None:
            parent.evaluated += 1
            parent.axes.setdefault("symbols", []).append(cell.symbol)
            parent.axes.setdefault("holds", []).append(str(cell.hold))
            parent.axes.setdefault("states", []).append(cell.state)
            parent.axes.setdefault("windows", []).extend(map(str, dsl.windows_in(cell.expr)))
        try:
            value = self.evaluate(cell.expr, cell.symbol)
        except Exception as exc:
            self._reject("tier0", f"evaluation raised {type(exc).__name__}")
            self.campaign.fail(cell.key, f"evaluation raised {type(exc).__name__}")
            return {"tier": 0, "why": f"evaluation raised {type(exc).__name__}: {exc}"}
        # THE CHEAP LAYER: finite, non-constant, turnover, minimal IC, orthogonality vs the
        # symbol's archive -- in that order of cost, and nothing dearer runs on a failure.
        z = _zscore(value)
        twins = self.twins.setdefault(cell.symbol, [])
        failed, cheap = cheap_screens(value, z, world, cell.hold, twins)
        rho_max = float(cheap.get("rho_max", 0.0))
        if failed is not None:
            rejected = self.counts["cheap"]["rejected"]
            rejected[failed] = rejected.get(failed, 0) + 1
            self._reject("tier0", f"cheap:{failed}")
            self.campaign.fail(cell.key, f"cheap:{failed}")
            if parent is not None:
                parent.recent.append(0)
            return {"tier": 0, "why": f"cheap layer {failed}: {cheap}"}
        self.counts["cheap"]["passed"] += 1
        self.campaign.advance(cell.key, "SCREENED", cheap=cheap)
        self.credits.screened(cell.expr, cell.generator, cell.asset_class)
        self.counts["tier1"]["evaluated"] += 1
        t1 = tier1(cell, world, value, self.rng)
        if parent is not None:
            parent.recent.append(int(t1.passed))
            parent.recent = parent.recent[-EXHAUST_TAIL:]
            parent.orth.append(1.0 - rho_max)
        if not t1.passed:
            self._reject("tier1", t1.reason)
            self.campaign.fail(cell.key, f"tier1: {t1.reason}")
            return {"tier": 1, "why": t1.reason, "t1": t1.metrics()}
        self.counts["tier1"]["passed"] += 1
        if parent is not None:
            parent.tier1_pass += 1
            parent.gains.append(t1.net_oos)
            if cell.origin in ("transfer", "harvest"):
                parent.transfers_held.append(cell.symbol)
                self.counts["transfers_held"] += 1
        if len(twins) < self.caps.twin_k:
            twins.append((cell.key, z.astype(np.float32)))
        self.counts["tier2"]["evaluated"] += 1
        t2 = tier2(cell, world, t1, lambda e: self.evaluate(e, cell.symbol), self.rng,
                   self.families)
        desc = cell.descriptor()
        score = t1.t_oos * (1.0 - rho_max)
        prev = self.archive.get(desc)
        if prev is None or float(prev.get("score", -1e9)) < score:
            self.archive[desc] = {"score": round(score, 4), "cell": cell.as_dict(),
                                  "net_oos": round(t1.net_oos, 7), "at": now_iso()}
        if not t2.passed:
            self._reject("tier2", t2.reason)
            self.campaign.fail(cell.key, f"tier2: {t2.reason}")
            return {"tier": 2, "why": t2.reason, "t1": t1.metrics(), "t2": t2.metrics()}
        self.counts["tier2"]["passed"] += 1
        self.families.survivor(cell.expr)
        self.credits.survivor(cell.expr, cell.generator, cell.asset_class)
        if parent is not None:
            parent.tier2_pass += 1
        blocked = executable_by_formula_family(cell.expr, cell.state)
        row = {"cell": cell.as_dict(), "t1": t1.metrics(), "t2": t2.metrics(),
               "orthogonality": round(1.0 - rho_max, 3), "executor_block": blocked,
               "falsifier": self._falsifier(cell, t1, t2, world)}
        (self.counts["blocked"] if blocked else self.counts["survivors"]).append(row)
        return {"tier": 3, "why": "survivor", **row}

    @staticmethod
    def _falsifier(cell: Cell, t1: Tier1, t2: Tier2, world: World) -> str:
        side = "follow" if t1.side > 0 else "fade"
        return (f"{ag.to_str(cell.expr)} on {cell.symbol}, {side}, hold {cell.hold} bars, "
                f"state {cell.state}: abandon if the gauntlet's net per trade at this hold is "
                f"<= 0 or its deflated t <= 2 over the pre-registered spec, or if 60 forward "
                f"trades net <= the round-trip cost ({world.cost:.2e}); expected failure "
                f"regime: {t2.worst_split or 'UNMEASURED'} (the weakest split in sample)")

    # ---- the four stages
    def worlds_for(self, expr: Expr, hold: int, states: Iterable[str] = ("none",)) -> list[Cell]:
        return [Cell(expr, s, hold, st, "transfer", asset_class=w.asset_class)
                for s, w in self.lake.worlds.items() for st in states]

    def transfer(self, parent: Parent) -> None:
        """The parent UNCHANGED across symbols x horizons; across sessions and regimes where it
        worked. Parameters frozen: nothing is tuned before the sweep says it transfers."""
        expr = parent.expr if parent.status == "TESTABLE" else _prune(parent.expr, self.rng)
        origin = "harvest" if parent.kind == "harvest" else "transfer"
        worked: list[tuple[str, int]] = []
        for hold in HORIZONS:
            for cell in self.worlds_for(expr, hold):
                cell.origin, cell.parent, cell.generator = origin, parent.pid, "transfer"
                cell.chain = [*parent.chain, "transfer"]
                res = self.run_cell(cell, parent)
                self.counts["transfer_cells"] += 1
                if res.get("tier", 0) >= 2:
                    worked.append((cell.symbol, hold))
                if self.out_of_budget("transfer"):
                    break
        states = [f"session:{s}" for s in SESSIONS] + [f"regime:{r}" for r in REGIMES]
        for sym, hold in worked[:4]:
            for st in states:
                cell = Cell(expr, sym, hold, st, origin, parent.pid, "transfer_state",
                            self.lake.worlds[sym].asset_class, [*parent.chain, "transfer_state"])
                self.run_cell(cell, parent)
                if self.out_of_budget("transfer"):
                    break
        parent.transferred = True

    def mutate_parent(self, parent: Parent, qd_target: str | None = None) -> Cell:
        """One LIGHT move on a transferred parent. Raises if the parent was never transferred."""
        if not parent.transferred:
            raise TransferBeforeTuning(f"{parent.pid} has not been transferred unchanged; "
                                       "tuning it first is the mistake the law names")
        rng = self.rng
        base = parent.expr if parent.status == "TESTABLE" else _prune(parent.expr, rng)
        syms = list(self.lake.worlds)
        sym = syms[int(rng.integers(len(syms)))]
        world = self.lake.worlds[sym]
        terms = ag.available_terminals(world.frames)
        hold = int(rng.choice(HORIZONS))
        state = "none"
        if qd_target and ("session" in qd_target or "regime" in qd_target):
            state = (f"session:{rng.choice(list(SESSIONS))}" if "session" in qd_target
                     else f"regime:{rng.choice(REGIMES)}")
            expr, gen = base, "qd_state"
        else:
            # THE MOVE IS DRAWN BY MEASURED CREDIT: what screened and survived earns the draws.
            gen = str(rng.choice(MOVES, p=self.credits.move_weights(MOVES)))
            child = self._apply_move(base, gen, terms, parent)
            for fallback in ("constant", "point", "subtree"):
                if child is not None:
                    break
                noop = self.counts["mutations"]["noop"]
                noop[gen] = noop.get(gen, 0) + 1
                gen = fallback
                child = self._apply_move(base, gen, terms, parent)
            expr = base if child is None else child
            if gen == "horizon":
                hold = HORIZONS[(HORIZONS.index(hold) + 1) % len(HORIZONS)]
        return Cell(expr, sym, hold, state, "mutation", parent.pid, gen, world.asset_class,
                    [*parent.chain, gen])

    def _apply_move(self, base: Expr, move: str, terms: Sequence[str],
                    parent: Parent) -> Expr | None:
        """One named move; None when it produced no dimension-preserving child."""
        if move in dsl.MUTATIONS:
            partner: Expr | None = None
            if move == "crossover":
                others = [p for p in self.parents.values()
                          if p.transferred and p.pid != parent.pid]
                partner = others[int(self.rng.integers(len(others)))].expr if others else None
            return dsl.mutate(base, move, self.rng, terminals=terms, partner=partner)
        if move == "basket_swap":
            out = self._swap_rank(base)
        elif move == "horizon":
            return ag._clone(base)
        else:
            out = self._bind_external(base, terms)
        return None if ag.key(out) == ag.key(base) else out

    def _swap_rank(self, expr: Expr) -> Expr:
        """ts_rank <-> xrank at one node: the same question asked of peers instead of time."""
        paths = [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), list)
                 and ag._get(expr, p)[0] in ("ts_rank", "xrank", "zscore", "xzscore")]
        if not paths:
            return expr
        p = paths[int(self.rng.integers(len(paths)))]
        node = ag._get(expr, p)
        if node[0] == "ts_rank":
            new: Expr = ["xrank", node[1]]
        elif node[0] == "zscore":
            new = ["xzscore", node[1]]
        elif node[0] == "xrank":
            new = ["ts_rank", node[1], int(self.rng.choice(ag.WINDOWS[3:]))]
        else:
            new = ["zscore", node[1], int(self.rng.choice(ag.WINDOWS[3:]))]
        cand = ag._set(ag._clone(expr), p, new)
        return cand if ag.is_valid(cand) else expr

    def _bind_external(self, expr: Expr, terms: Sequence[str]) -> Expr:
        """Replace one bar terminal with a bound external of a compatible kind, if any."""
        ext = [t for t in terms if t in ag.EXTERNAL_TERMINALS]
        if not ext:
            return ag.mutate(expr, self.rng, terminals=terms)
        leaves = [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), str)]
        self.rng.shuffle(leaves)
        for p in leaves:
            for t in ext:
                cand = ag._set(ag._clone(expr), p, t)
                if ag.is_valid(cand):
                    return cand
        return expr

    def invent(self) -> Cell:
        syms = list(self.lake.worlds)
        sym = syms[int(self.rng.integers(len(syms)))]
        terms = ag.available_terminals(self.lake.worlds[sym].frames)
        expr = ag.random_expr(self.rng, max_depth=3, terminals=terms)
        return Cell(expr, sym, int(self.rng.choice(HORIZONS)), "none", "invention", "",
                    "random", self.lake.worlds[sym].asset_class, ["invent"])

    def pick_parent(self, pool: list[Parent]) -> Parent:
        """V(a)-weighted draw among the pool, empty QD cells favoured through novelty."""
        weights = np.array([max(1e-12, p.value(self.families, self._archive_n(p)))
                            for p in pool])
        weights = weights / weights.sum()
        return pool[int(self.rng.choice(len(pool), p=weights))]

    def _archive_n(self, parent: Parent) -> int:
        d = Cell(parent.expr, "", HORIZONS[0]).mechanism().split("/")[0]
        return sum(1 for k in self.archive if k.startswith(d))

    def empty_qd_targets(self, klass: str | None = None) -> list[str]:
        """Archive cells (mechanism x horizon x asset class x representation) never filled
        for this pass's asset class, for the scheduler to aim a share of the draws at."""
        have = set(self.archive)
        shapes = {k.split("|")[0].split("/")[0] for k in have} or {"a momentum-type measure"}
        klass = klass or str(self.state.get("basket") or "unclassified")
        out: list[str] = []
        for shape in sorted(shapes):
            for hold in HORIZONS:
                for st in ("none", "session", "regime"):
                    key = f"{shape}/{st}|h{hold}|{klass}|single+bar+own"
                    if key not in have:
                        out.append(key)
        return out

    # ---- islands
    def migrate(self, klass: str) -> int:
        """Elites of the OTHER islands become `migrant` parents of this one, transferred
        unchanged before anything is tuned: TRANSFER BEFORE TUNING holds for a migrant exactly
        as it holds for a public alpha."""
        pool: list[tuple[float, str, dict[str, Any]]] = []
        for island, doc in self.islands.items():
            if island == klass:
                continue
            for row in (doc.get("elites") or {}).values():
                pool.append((float(row.get("score", 0.0)), island, row))
        pool.sort(key=lambda t: -t[0])
        n = 0
        for _score, island, row in pool[:MIGRANTS_PER_PASS]:
            cell = row.get("cell") or {}
            expr = cell.get("expr")
            if expr is None or not ag.is_valid(expr):
                continue
            p = self._parent(f"migrant:{island}:{ag.subtree_hash(dsl.canonical(expr))}", expr,
                             "migrant")
            p.chain = [*(cell.get("chain") or []), f"migrate:{island}->{klass}"]
            n += 1
        self.counts["migrants"] = n
        return n

    def update_islands(self, klass: str) -> None:
        elites: dict[str, Any] = self.islands.setdefault(klass, {"elites": {}})["elites"]
        for desc, row in self.archive.items():
            if str((row.get("cell") or {}).get("asset_class") or "unclassified") != klass:
                continue
            if desc not in elites or float(elites[desc].get("score", -1e9)) < float(row["score"]):
                elites[desc] = row
        top = sorted(elites.items(), key=lambda kv: -float(kv[1].get("score", 0.0)))
        self.islands[klass]["elites"] = dict(top[:ISLAND_ELITES])
        self.islands[klass]["at"] = now_iso()

    # ---- one pass
    def load_worlds(self, symbols: Sequence[str] | None, max_symbols: int | None) -> list[str]:
        """The basket of this pass: one asset class, rotated by the cursor between passes."""
        limit = max(1, min(self.caps.max_symbols, max_symbols or self.caps.max_symbols))
        if symbols:
            chosen = list(symbols)[:limit]
        else:
            baskets = {k: v for k, v in self.lake.baskets().items() if v}
            if not baskets:
                return []
            classes = sorted(baskets)
            ci = int(self.state.get("class_cursor", 0)) % len(classes)
            klass = classes[ci]
            syms = baskets[klass]
            si = int(self.state.get("symbol_cursor", 0)) % len(syms)
            chosen = (syms[si:] + syms[:si])[:limit]
            self.state["symbol_cursor"] = (si + limit) % len(syms)
            if si + limit >= len(syms):
                self.state["class_cursor"] = (ci + 1) % len(classes)
            self.state["basket"] = klass
        self.lake.macro_index = int(self.state.get("macro_cursor", 0))
        self.state["macro_cursor"] = self.lake.macro_index + 1
        loaded: list[str] = []
        for s in chosen:
            free = free_phys_mb()
            if free is not None and free < MIN_FREE_MB:
                self.say(f"stopping loads: free {free:.0f} MB < {MIN_FREE_MB:.0f}")
                break
            if self.lake.load(s) is not None:
                loaded.append(s)
        return loaded

    def run(self, budget_s: float, symbols: Sequence[str] | None = None,
            max_symbols: int | None = None) -> dict[str, Any]:
        self.budget_s = float(budget_s)
        report: dict[str, Any] = {"source": SOURCE, "generated_at": now_iso(),
                                  "budget_s": budget_s, "dry_run": self.dry_run,
                                  "memory": self.caps.as_dict()}
        if self.caps.stood_down:
            report["status"] = "STOOD_DOWN"
            report["why"] = self.caps.why
            self.say(self.caps.why)
            return self.finish(report)
        try:
            self.cache = ag.SubtreeCache(max_entries=2048, max_cells=self.caps.cache_cells)
        except TypeError:
            self.cache = None
        report["fields"] = self.lake.catalogue.census()
        report["parents_census"] = self.load_parents()
        report["harvest"] = self.harvest()
        loaded = self.load_worlds(symbols, max_symbols)
        report["worlds"] = {"symbols": loaded, "basket": self.state.get("basket", ""),
                            "bindings": {s: {t: f.name for t, f in w.bindings.items()}
                                         for s, w in self.lake.worlds.items()},
                            "cost_status": {s: w.cost_status for s, w in self.lake.worlds.items()},
                            "horizons": list(HORIZONS)}
        if not loaded:
            report["status"] = "NO_WORLDS"
            report["why"] = "no hypothesis-lane symbol with 720+ H1 bars could be loaded"
            return self.finish(report)
        klass = self.lake.worlds[loaded[0]].asset_class
        self.state["basket"] = klass
        report["worlds"]["lockbox"] = {s: w.lockbox for s, w in self.lake.worlds.items()}
        report["migration"] = {"island": klass, "migrants": self.migrate(klass),
                               "islands": {k: len(v.get("elites") or {})
                                           for k, v in self.islands.items()}}
        # HARVEST -> MIGRANTS -> TRANSFER: the dead and the parked first, then the other
        # islands' elites, then the public alphas and the canon by V(a)
        order = [p for p in self.parents.values() if p.kind == "harvest"]
        order += [p for p in self.parents.values() if p.kind == "migrant"]
        rest = [p for p in self.parents.values() if p.kind not in ("harvest", "migrant")]
        while rest and not self.out_of_budget("transfer"):
            p = self.pick_parent(rest)
            rest.remove(p)
            order.append(p)
        for p in order:
            if self.out_of_budget("transfer"):
                break
            self.transfer(p)
        # LIGHT MUTATION, parents by V(a), a share of draws aimed at empty QD cells
        pool = [p for p in self.parents.values() if p.transferred and not p.exhausted()]
        targets = self.empty_qd_targets(klass)
        n_mut = 0
        while pool and not self.out_of_budget("mutation"):
            parent = self.pick_parent(pool)
            target = targets[int(self.rng.integers(len(targets)))] \
                if targets and self.rng.random() < 0.3 else None
            try:
                cell = self.mutate_parent(parent, target)
            except TransferBeforeTuning as exc:
                self.say(str(exc))
                break
            self.run_cell(cell, parent)
            n_mut += 1
        # NEW INVENTION, the smallest share
        n_inv = 0
        while not self.out_of_budget("invention"):
            self.run_cell(self.invent(), None)
            n_inv += 1
        report["stages"] = {"transfer_parents": len([p for p in self.parents.values()
                                                     if p.transferred]),
                            "mutations": n_mut, "inventions": n_inv,
                            "order": "HARVEST -> TRANSFER -> LIGHT MUTATION -> NEW INVENTION"}
        report["status"] = "RAN"
        return self.finish(report)

    # ---- the end of a pass
    def finish(self, report: dict[str, Any]) -> dict[str, Any]:
        report["seconds"] = round(self.elapsed(), 1)
        report["cells"] = {"generated": self.counts["generated"],
                           "tier0": self.counts["tier0"], "tier1": self.counts["tier1"],
                           "tier2": self.counts["tier2"],
                           "transfer_cells": self.counts["transfer_cells"],
                           "transfers_held": self.counts["transfers_held"],
                           "survivors": len(self.counts["survivors"]),
                           "blocked_survivors": len(self.counts["blocked"]),
                           "cap_reached": self.cells_done >= self.caps.max_cells}
        report["families"] = self.families.summary()
        report["N_effective_charged"] = report["families"]["n_effective_this_pass"]
        parents = {pid: p.as_dict() for pid, p in self.parents.items()}
        report["parents"] = {"n": len(parents),
                             "exhausted": sorted(pid for pid, p in self.parents.items()
                                                 if p.exhausted()),
                             "with_survivors": sorted(pid for pid, p in self.parents.items()
                                                      if p.tier2_pass),
                             "transfers_held_by_parent": {pid: sorted(set(p.transfers_held))
                                                          for pid, p in self.parents.items()
                                                          if p.transfers_held},
                             "rows": parents}
        report["nontestable_parents_by_missing_field"] = \
            (report.get("parents_census") or {}).get("nontestable_by_missing", {})
        report["survivors"] = self.counts["survivors"][:200]
        report["blocked_survivors"] = self.counts["blocked"][:200]
        self.update_islands(str(self.state.get("basket") or "unclassified"))
        report["population"] = {
            "parents_by_kind": _count_by(p.kind for p in self.parents.values()),
            "parents_transferred": sum(1 for p in self.parents.values() if p.transferred),
            "parents_exhausted": sum(1 for p in self.parents.values() if p.exhausted()),
            "archive_cells": len(self.archive), "seen_keys": len(self.seen),
            "islands": {k: len(v.get("elites") or {}) for k, v in self.islands.items()},
            "migrants_this_pass": self.counts["migrants"],
            "twins_kept": {s: len(t) for s, t in self.twins.items()}}
        report["cheap_layer"] = {"order": list(CHEAP_ORDER), "thresholds": CHEAP,
                                 **self.counts["cheap"]}
        report["null_factory"] = {"k": NULLS, "threshold_p": T1["p_perm"],
                                  "rule": "permutation, block-shuffle and synthetic random-walk "
                                          "nulls per candidate; the gate reads the worst p"}
        mut = self.counts["mutations"]
        report["mutations"] = {
            "moves": list(MOVES), "by_move": mut["by_move"],
            "by_trial_family_top": dict(sorted(mut["by_trial_family"].items(),
                                               key=lambda kv: -kv[1])[:20]),
            "trial_families_mutated": len(mut["by_trial_family"]), "no_child_found": mut["noop"],
            "rule": "every move is dimension-preserving (alpha_dsl.mutate: production screen "
                    "AND the parent's root unit); every mutated cell is charged to its trial "
                    "family (LAWS 5k) and counted here by move and by family"}
        report["credits"] = self.credits.summary(MOVES)
        report["campaign"] = self.campaign.counts()
        report["catalogue"] = dsl.catalogue_census()
        report["qd_archive"] = {"cells_filled": len(self.archive),
                                "empty_targets": len(self.empty_qd_targets()),
                                "key": "mechanism|horizon|asset_class|representation",
                                "islands": {k: len(v.get("elites") or {})
                                            for k, v in self.islands.items()},
                                "order": "HARVEST -> TRANSFER (migrants included) -> LIGHT "
                                         "MUTATION -> NEW INVENTION; no parent tuned before "
                                         "its unchanged transfer sweep"}
        report["debts"] = [
            "trial ledger: libs/research/trial_ledger.py prices the pass (families.ledger); "
            "the mid-pass tier-2 deflation still uses the family's raw pass count because the "
            "census is priced once at the end -- the gauntlet's charge is the binding one",
            "executor: family_formula runs one instrument with bar and driver terminals only; "
            "survivors carrying a panel node, a state filter or an external terminal are "
            "recorded BLOCKED in the registry (blocked_survivors above), not donated",
            f"parents: {len(dsl.genome_census()['too_deep'])} public alphas transcribe deeper "
            f"than MAX_DEPTH {ag.MAX_DEPTH}; they reach the executor only through pruning",
            "event_intensity: no event-calendar field exists under data/axes, so the `event` "
            "terminal is unbound and UNMEASURED on every world",
        ]
        report["log"] = self.log[-40:]
        if self.dry_run:
            report["written"] = []
            self.say(f"dry run: {report['cells']} -- nothing written")
            return report
        written = self.persist(report)
        report["written"] = [str(p) for p in written]
        atomic_json(self.paths.report, report)
        return report

    def persist(self, report: dict[str, Any]) -> list[Path]:
        written: list[Path] = []
        sd = self.paths.state_dir
        self.families.save()
        written.append(self.families.path)
        atomic_json(sd / "archive.json", {"at": now_iso(), "cells": self.archive})
        atomic_json(sd / "seen.json", {"at": now_iso(), "keys": sorted(self.seen)[-50_000:]})
        for pid, p in self.parents.items():
            self.parent_book[pid] = {**p.as_dict(), "recent": p.recent[-EXHAUST_TAIL:]}
        atomic_json(sd / "parents.json", {"at": now_iso(), "parents": self.parent_book})
        atomic_json(sd / "state.json", {**self.state, "at": now_iso()})
        written += [sd / "archive.json", sd / "seen.json", sd / "parents.json", sd / "state.json"]
        atomic_json(sd / "islands.json", {"at": now_iso(), "islands": self.islands,
                                          "elites_per_island": ISLAND_ELITES,
                                          "migrants_per_pass": MIGRANTS_PER_PASS})
        self.credits.save()
        written += [sd / "islands.json", self.credits.path]
        donated = self.donate()
        if donated is not None:
            written.append(donated)
        report["donation"] = self._donation_counts()
        report["registry"] = self.record_registry()
        written += self.campaign.save()
        report["campaign"] = self.campaign.counts()
        return written

    # ---- outputs
    def _candidates(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self.counts["survivors"]:
            c = row["cell"]
            side = row["t1"]["side_mode"]
            params = {**RECIPE, "hold_bars": int(c["hold"]), "expr": c["expr"],
                      "side_mode": side}
            title = f"{c['symbol']}.formula.{side} {c['rendered']} <- {c['parent'] or 'invented'}"
            out.append({"source": SOURCE, "kind": SOURCE, "symbol": c["symbol"],
                        "family": "formula", "params": params,
                        "mechanism": ag.describe(c["expr"], side), "title": title, "url": "",
                        "falsifier": row["falsifier"],
                        "expected_costs": {"round_trip_frac": self.lake.worlds[c["symbol"]].cost
                                           if c["symbol"] in self.lake.worlds else None,
                                           "hour_multiplier": "cost surface dear hours"},
                        "exact_rule": {"family": "formula", "params": params,
                                       "entry": f"|z_{NORM}| >= {ENTRY_Z}", "hold_bars": c["hold"],
                                       "side": side},
                        "parent_alpha": c["parent"], "origin": c["origin"],
                        "generator": c["generator"], "trial_family": c["family"],
                        "evidence": {**row["t1"], **{f"t2_{k}": v for k, v in row["t2"].items()},
                                     "orthogonality": row["orthogonality"],
                                     "screen": "expression factory tiers 0-2: vectorised path, "
                                               "OOS direction, permutation null, neighbours, "
                                               "splits, n_eff, family deflation"}})
        return out

    def donate(self) -> Path | None:
        cands = self._candidates()
        if not cands:
            return None
        try:
            from research import proposer_common as pc
            donated: Path | None = pc.donate(SOURCE, cands,
                                             tests_run=self.counts["tier1"]["evaluated"])
            return donated
        except Exception as exc:
            self.say(f"donation failed ({type(exc).__name__}: {exc}); writing the seat file "
                     "directly")
            out = self.paths.intel_dir / SOURCE
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"discoveries_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M')}.json"
            atomic_json(path, {"source": SOURCE, "generated_at": now_iso(),
                               "tests_run": self.counts["tier1"]["evaluated"],
                               "discoveries": cands, "counts": {"donated": len(cands)},
                               "note": f"proposer_common.donate failed: {exc}"})
            return path

    def _donation_counts(self) -> dict[str, Any]:
        try:
            from research import proposer_common as pc
            return dict(pc.donation_counts())
        except Exception:
            return {"donated": len(self.counts["survivors"]), "via": "direct"}

    def record_registry(self) -> dict[str, Any]:
        """Every survivor as an `expression_cell` discovery with provenance to its parent;
        a blocked survivor parked BLOCKED with the executor gap named."""
        reg = self.registry
        if reg is None:
            try:
                from libs.moat import registry as reg
            except Exception as exc:
                return {"error": f"registry unavailable: {type(exc).__name__}"}
        out: dict[str, Any] = {"parents": 0, "cells": 0, "blocked": 0, "links": 0,
                               "queued": 0, "queued_existing": 0, "errors": []}
        try:
            origin = reg.origin_of(SOURCE)
        except Exception:
            origin = "EXPRESSION_FACTORY"
        parent_ids: dict[str, str] = {}
        rows = [(r, False) for r in self.counts["survivors"]] + \
            [(r, True) for r in self.counts["blocked"]]
        try:
            conn = reg.connect()
        except Exception as exc:
            return {"error": f"registry connect: {type(exc).__name__}: {exc}"}
        try:
            for row, blocked in rows:
                c = row["cell"]
                pid = str(c.get("parent") or "")
                try:
                    if pid and pid not in parent_ids:
                        p = self.parents.get(pid)
                        g = dsl.parent_genomes().get(pid)
                        did, _ = reg.record_discovery(
                            source_id="alpha101" if pid.startswith("alpha") else pid.split(":")[0],
                            source_type="parent_genome", mechanism=f"{pid}: " + (
                                g.formula if g is not None else
                                ag.to_str(p.expr) if p is not None else pid),
                            origin=origin, generator=SOURCE, assets=[],
                            exact_rule=json.dumps(g.as_dict() if g is not None else
                                                  {"expr": p.expr if p else None},
                                                  default=str)[:4000],
                            economic_rationale="public formula family, a seed (LAWS 5l)",
                            conn=conn)
                        parent_ids[pid] = did
                        out["parents"] += 1
                    params = {**RECIPE, "hold_bars": int(c["hold"]), "expr": c["expr"],
                              "side_mode": row["t1"]["side_mode"]}
                    did, _ = reg.record_discovery(
                        source_id=f"parent:{pid}" if pid else "invention",
                        source_type="expression_cell",
                        mechanism=ag.describe(c["expr"], row["t1"]["side_mode"]), origin=origin,
                        generator=SOURCE, assets=[c["symbol"]], horizons=[c["hold"]],
                        sessions=[c["state"]] if c["state"].startswith("session") else [],
                        regimes=[c["state"]] if c["state"].startswith("regime") else [],
                        exact_rule=json.dumps({"family": "formula", "params": params},
                                              sort_keys=True, default=str),
                        falsifier=row["falsifier"], novelty=row["orthogonality"],
                        confidence=min(1.0, max(0.0, row["t1"]["t_oos"] / 4.0)),
                        parent_ids=[parent_ids[pid]] if pid in parent_ids else [],
                        payload={"tier1": row["t1"], "tier2": row["t2"], "cell": c,
                                 "trial_family": c["family"]}, conn=conn)
                    if pid in parent_ids:
                        reg.link("discovery", parent_ids[pid], "discovery", did, "derived",
                                 conn=conn)
                        out["links"] += 1
                    if blocked:
                        reg.set_discovery_state(did, "BLOCKED",
                                                reason=f"NO_EXECUTOR: {row['executor_block']}",
                                                blocked_cells=1, conn=conn)
                        self.campaign.fail(str(c["key"]), f"NO_EXECUTOR: {row['executor_block']}")
                        out["blocked"] += 1
                    else:
                        reg.set_discovery_state(did, "QUEUED", possible_cells=1,
                                                generated_cells=1, compiled_cells=1,
                                                queued_cells=1, conn=conn)
                        # THE CAMPAIGN ADAPTER: the survivor becomes a registry candidate the
                        # ONE gauntlet judges, carrying its provenance -- parent genome,
                        # mutation chain, operator credits -- as lineage.
                        cid, created = reg.enqueue_candidate(
                            family="formula", symbol=c["symbol"], params=params, origin=origin,
                            mechanism=ag.describe(c["expr"], row["t1"]["side_mode"]),
                            generator=SOURCE, department="mathlab",
                            source_id=f"parent:{pid}" if pid else "invention",
                            discovery_id=did, trial_family=c["family"],
                            parent_ids_json=[parent_ids[pid]] if pid in parent_ids else [],
                            falsifier=row["falsifier"], horizon=str(c["hold"]),
                            session=c["state"] if c["state"].startswith("session") else "",
                            regime=c["state"] if c["state"].startswith("regime") else "",
                            asset_class=str(c.get("asset_class") or ""),
                            expected_costs=(self.lake.worlds[c["symbol"]].cost
                                            if c["symbol"] in self.lake.worlds else None),
                            novelty_vs_live=row["orthogonality"],
                            exact_rules=json.dumps({"family": "formula", "params": params,
                                                    "entry": f"|z_{NORM}| >= {ENTRY_Z}",
                                                    "hold_bars": c["hold"]}, default=str),
                            lineage_json=self._provenance(c, pid, g, p), conn=conn)
                        self.campaign.advance(str(c["key"]), "QUEUED", candidate_id=cid,
                                              created=created)
                        out["queued" if created else "queued_existing"] += 1
                    out["cells"] += 1
                except Exception as exc:
                    out["errors"].append(f"{type(exc).__name__}: {exc}"[:200])
            out["campaign_refresh"] = self.campaign.refresh(conn)
        finally:
            conn.close()
        out["errors"] = out["errors"][:10]
        return out

    def _provenance(self, c: dict[str, Any], pid: str, genome: Any, parent: Parent | None
                    ) -> dict[str, Any]:
        """What the candidate descends from: the parent genome and its public formula, the
        mutation chain that produced the cell, and the measured credit of every operator in it
        on this asset class."""
        klass = str(c.get("asset_class") or "")
        return {"source": SOURCE, "parent_genome": pid or "invention",
                "parent_kind": parent.kind if parent is not None else "",
                "parent_formula": (genome.formula if genome is not None else
                                   ag.to_str(parent.expr) if parent is not None else ""),
                "mutation_chain": list(c.get("chain") or []),
                "operator_credits": {op: round(self.credits.op_weight(op, klass), 4)
                                     for op in sorted(dsl.operators_in(c["expr"]))},
                "trial_family": c["family"], "descriptor": c["descriptor"],
                "generator": c.get("generator", "")}


# ============================================================================ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode; the "
                                                         "department resident re-runs it)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="evaluate, write NOTHING")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--max-symbols", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    fac = Factory(seed=a.seed, dry_run=a.dry_run)
    rep = fac.run(a.budget_s, a.symbols, a.max_symbols)
    cells = rep.get("cells") or {}
    print(f"expression_factory: {rep.get('status')} in {rep.get('seconds')}s -- "
          f"tier0 {cells.get('tier0', {}).get('evaluated', 0)} / tier1 "
          f"{cells.get('tier1', {}).get('passed', 0)} passed / tier2 "
          f"{cells.get('tier2', {}).get('passed', 0)} passed; survivors "
          f"{cells.get('survivors', 0)} + blocked {cells.get('blocked_survivors', 0)}; "
          f"campaign {(rep.get('campaign') or {}).get('this_pass')}; "
          f"N_eff {rep.get('N_effective_charged')}; "
          f"{'DRY RUN, nothing written' if a.dry_run else 'report ' + str(DEFAULT_PATHS.report)}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
