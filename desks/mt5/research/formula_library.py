"""THE PUBLISHED FORMULA LIBRARIES AS A PRODUCER -- GTJA-191 and Qlib Alpha158, operator-exact.

WHAT WAS MISSING. The desk carried the published libraries only as STYLE TEMPLATES
(`libs/research/search_populations.py`, the `gtja191` / `alpha158` zoo seeds, each a shape
rewritten in the desk's grammar and proposed only after a mutation) and as a probe
(`libs/research/sandboxes/qlib.py`). No producer minted a single cell of either library as
published.

WHAT THIS DOES, hourly, in one bounded pass:

  1. THE CATALOGUE (`libs.research.formula_catalog`): every formula's published text, source and
     status. The formulas that read only open/high/low/close/tick volume are TESTABLE on an MT5
     bar; the rest need VWAP, turnover, a benchmark index or factor returns, or are not
     computable as printed, and are counted NONTESTABLE by reason. Alpha360 is implemented and
     verified, and NOT minted: its testable rows are raw lagged prices (Ref($close, i)/$close)
     that Qlib feeds to a learner, not standalone signals.
  2. THE SCOPE (`research/universe_policy.py`, the ONLY scope rule): every symbol with an H1 bar
     file that `universe_policy.may_hypothesise(symbol, "formula")` admits. Share CFDs are
     admitted by the policy only to its cross-sectional class-book families, and `formula` is
     not one, so none is minted. A formula that ranks ACROSS instruments (GTJA RANK) is minted
     for a symbol whose `peer_class` has at least one other member with bars; its recipe
     carries those peers by name (`panel_symbols`) and the executor ranks within them.
  3. THE CELLS. One cell per (formula, symbol, timeframe, horizon) -- H1 (pinned in params, so
     the compiler does not re-expand it over charts and sessions), holds of 8 and 24 bars (the
     formula family's horizons, `expression_factory.HORIZONS`), the family's frozen recipe
     (`expression_factory.RECIPE`), side `follow`: the publication's sign IS the hypothesis.
  4. THE DOOR AND THE CHARGE. New cells go to the judge's intake the way every converting
     producer's do: `family_donation.donate_per_family` writes
     `data/intelligence/formula_library/discoveries_*_formula.json` through
     `proposer_common.donate` (PIT stamp, lane filter, preregistration, registry record), and
     the contract's `tests_run` charges EVERY donated cell as a trial, after the compiler's own
     chart x session expansion. Its ledger (`data/donation_ledgers/formula_library.jsonl`)
     remembers what was charged, so a re-run never re-offers a cell and never charges it twice;
     losing the ledger re-charges, an over-count and never an under-count.
  5. NEAR-DUPLICATES ARE MINTED ONCE. Published formulas that are the same signal under another
     name (GTJA058 = CNTP20, SUMP = SUMD ...) are found by SIGNED rho > DEDUP_RHO between their
     evaluated series on reference symbols; one representative per cluster is minted. This reads
     the formulas' values, never a return, so it selects nothing on outcome: a formula left out
     is never tested and is no trial. An anti-correlated member is the representative's FADE (a
     distinct trade under `follow`) and is minted as its own cell.
  6. EVALUABLE OR NOT MINTED. Before a cell is minted its formula is evaluated on the symbol's
     recent bars (and peers): a formula that is NaN, constant, or whose 240-bar z never reaches
     the entry threshold would be a cell the judge can only file as "never fires". That is a
     construction check, not a screen -- the formula's returns are never read.
  7. BOUNDED, NOT THROTTLED. A pass donates at most max(the judge's own formula intake as
     JUDGE_COVERAGE.json measures it, EMIT_FLOOR) new cells, walking a persistent cursor over the
     id-ordered cell space so successive passes cover all of it.

ARTIFACT: reports/FORMULA_LIBRARY.json -- formulas implemented per library, cells donated and
trials charged this pass, cells already charged, the cell space per library, the symbols
covered, and every reason a formula or a cell was not minted.

    python research/formula_library.py --once --budget-s 480
    python research/formula_library.py --once --dry-run          # counts, writes nothing
    python research/formula_library.py --once --dry-run --out /tmp/FL.json   # ... but this file
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
#: The artifact, for the default desk (`Paths.report` is the same file under any root).
REPORT = _DESK / "reports" / "FORMULA_LIBRARY.json"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import formula_catalog as fc  # noqa: E402
from libs.research import formula_ops as fo  # noqa: E402

SOURCE = "formula_library"
FAMILY = "formula"
TIMEFRAME = "H1"
#: The formula family's frozen recipe and horizons -- `expression_factory.RECIPE` / `HORIZONS`,
#: restated rather than imported (that module loads the whole factory); a test pins them equal.
RECIPE: dict[str, Any] = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20,
                          "stop_atr": 2.0, "rr": 1.5}
HORIZONS: tuple[int, ...] = (8, 24)
SIDE_MODE = "follow"
#: The libraries minted, and the one implemented but not minted (see the module docstring).
EMITTED: tuple[str, ...] = ("gtja191", "alpha158")
NOT_EMITTED: dict[str, str] = {
    "alpha360": ("implemented and verified; not minted: its testable rows are raw lagged prices "
                 "Qlib feeds to a learner (Ref($close, i)/$close, i = 1..59), not standalone "
                 "signals; minting them would charge hundreds of trials on one lag structure"),
}
SCOPE_RULE = ("universe_policy.may_hypothesise(symbol, 'formula'): every hypothesis-discovery "
              "class; share CFDs only in the cross-sectional families, which formula is not")
#: Near-duplicate threshold on the evaluated signal, and the reference symbols it is read on.
DEDUP_RHO = 0.999
DEDUP_REFERENCE: tuple[str, ...] = ("EURUSD", "XAUUSD", "US500")
DEDUP_N_REFERENCE = 3
#: The dedupe rule's version: part of the cache fingerprint.
DEDUP_RULE = "signed_rho"
#: Cached clusters older than this are recomputed even with an unchanged fingerprint (bars move).
DEDUP_MAX_AGE_DAYS = 7.0
#: Bars of recent history the evaluability check reads (about a year of H1).
EVAL_TAIL_BARS = 6000
#: Evaluable = at least this share of the tail finite, and not constant. Discrete formulas are
#: published signals too: the judge z-scores them like any other, so a distinct-value floor
#: above 2 would be a screen nobody preregistered.
MIN_FINITE_SHARE = 0.5
MIN_DISTINCT = 2
#: The per-pass floor on new cells; the bound is max(judge intake, floor), never below intake.
EMIT_FLOOR = 500
UNMEASURED = "UNMEASURED"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def cell_id(key: str, symbol: str, timeframe: str, horizon: int) -> str:
    """THE ONE ID of a (formula, symbol, timeframe, horizon) cell. Deterministic: the same cell
    named on any pass, any machine, is the same id."""
    raw = f"{key}|{symbol}|{timeframe}|{int(horizon)}"
    return "fl_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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


@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def state(self) -> Path:
        return self.desk / "data" / "formula_library" / "state.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "FORMULA_LIBRARY.json"

    @property
    def judge_coverage(self) -> Path:
        return self.desk / "reports" / "JUDGE_COVERAGE.json"

    @property
    def ledger(self) -> Path:
        """`family_donation`'s charge ledger for this source (box state, gitignored)."""
        return self.desk / "data" / "donation_ledgers" / f"{SOURCE}.jsonl"


DEFAULT_PATHS = Paths(_DESK)


@dataclass(frozen=True)
class Cell:
    cid: str
    key: str
    symbol: str
    horizon: int
    peers: tuple[str, ...] = ()
    asset_class: str = ""

    @property
    def formula(self) -> fc.Formula:
        f = fc.get(self.key)
        assert f is not None
        return f

    def params(self) -> dict[str, Any]:
        """The executable recipe `family_formula` runs. `timeframe` pins the chart (the judge
        pops it before the call) so the compiler does not re-expand the cell."""
        f = self.formula
        p: dict[str, Any] = {**RECIPE, "hold_bars": int(self.horizon), "expr": ["lib", self.key],
                             "side_mode": SIDE_MODE, "timeframe": TIMEFRAME}
        if f.needs_panel:
            p["panel_symbols"] = list(self.peers)
        return p

    def row(self) -> dict[str, Any]:
        """The donation row: an EXACT_RECIPE hypothesis the compiler admits as it stands."""
        f = self.formula
        mech = (f"{f.library} {f.fid} as published: {f.text[:400]}"
                + (" [VOLUME = broker tick volume]" if f.volume_proxy else "")
                + (f" [RANK within {len(self.peers)} peers on the same bar]"
                   if f.needs_panel else ""))
        return {"source": SOURCE, "kind": "hypothesis", "url": "",
                "symbol": self.symbol, "family": FAMILY, "params": self.params(),
                "title": f"{f.library} {f.fid} on {self.symbol} {TIMEFRAME} h{self.horizon}",
                "mechanism": mech,
                "falsifier": (f"{f.library} {f.fid} on {self.symbol} {TIMEFRAME}, held "
                              f"{self.horizon} bars, z-scored on {RECIPE['norm']} bars and "
                              f"followed at |z| >= {RECIPE['entry_z']}: no net-of-cost edge "
                              "out of sample"),
                "asset_class": self.asset_class,
                "lineage": {"source": SOURCE, "library": f.library, "formula_id": f.fid,
                            "formula_text": f.text, "citation": f.source, "note": f.note,
                            "dialect": f.dialect, "volume_proxy": f.volume_proxy,
                            "cross_sectional": f.needs_panel,
                            "panel_symbols": list(self.peers), "formula_cell_id": self.cid,
                            "timeframe": TIMEFRAME, "horizon": self.horizon}}


# ============================================================================ the universe
@dataclass
class Universe:
    """Which symbols this producer may mint on, and each one's peers -- read, never listed."""

    paths: Paths
    meta: dict[str, Any] = field(default_factory=dict)
    have: set[str] = field(default_factory=set)
    in_scope: list[str] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    peers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    classes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, paths: Paths, policy: Any = None) -> Universe:
        u = cls(paths)
        doc = read_json(paths.universe / "universe.json", {})
        u.meta = {str(k): v for k, v in doc.items() if isinstance(v, dict)} \
            if isinstance(doc, dict) else {}
        u.have = {p.stem.removesuffix("_H1") for p in paths.universe.glob("*_H1.parquet")}
        if policy is None:
            from research import universe_policy as policy  # type: ignore[no-redef]
        for sym in sorted(u.have):
            row = u.meta.get(sym) or {}
            klass = str(row.get("asset_class") or "").lower()
            if not _may_hypothesise(policy, sym):
                u.excluded[f"lane:{policy.lane(sym)}"] = u.excluded.get(
                    f"lane:{policy.lane(sym)}", 0) + 1
                continue
            u.in_scope.append(sym)
            u.classes[sym] = klass
        try:
            members = policy.peer_classes()
        except Exception:
            members = {}
        for sym in u.in_scope:
            pc = policy.peer_class(sym)
            if pc is None:
                continue
            u.peers[sym] = tuple(sorted(p for p in members.get(pc, []) if p != sym
                                        and p in u.have and _may_hypothesise(policy, p)))
        return u


def _may_hypothesise(policy: Any, sym: str) -> bool:
    """`policy.may_hypothesise(sym, FAMILY)`: the family is passed so the policy, not this file,
    decides whether a share CFD may carry it (only the cross-sectional families may)."""
    try:
        return bool(policy.may_hypothesise(sym, FAMILY))
    except TypeError:
        return bool(policy.may_hypothesise(sym))


def cell_space(universe: Universe, libraries: Sequence[str] = EMITTED,
               duplicates: dict[str, str] | None = None) -> tuple[list[Cell], dict[str, int]]:
    """Every mintable cell, ordered by id (a hash, so libraries, formulas and symbols
    interleave and a bounded pass spreads over all of them), plus what was left out and why.

    A cross-sectional formula needs at least ONE peer: a rank of an instrument against itself
    is constant, which is no signal (a construction fact). There is no larger floor: the family
    enters on a 240-bar TIME-SERIES z of the rank (`family_formula`), which a two-member rank
    reaches, so the old MIN_PANEL_PEERS=6 (derived from a cross-sectional z) vetoed cells that
    could fire. `duplicates` maps a formula key to the representative it duplicates; those
    formulas are not minted (their representative is)."""
    dup = duplicates or {}
    out: list[Cell] = []
    held: dict[str, int] = {}
    for lib in libraries:
        for f in fc.by_library(lib):
            if f.status != "TESTABLE":
                continue
            if f.key in dup:
                # Only symbols that would otherwise be minted: a panel formula on a symbol with
                # no peers is held as no_peer_class_panel, never also counted as a duplicate.
                n_dup = sum(1 for s in universe.in_scope
                            if not f.needs_panel or universe.peers.get(s, ()))
                held["near_duplicate"] = held.get("near_duplicate", 0) + n_dup
                held["no_peer_class_panel"] = (held.get("no_peer_class_panel", 0)
                                               + len(universe.in_scope) - n_dup)
                continue
            for sym in universe.in_scope:
                peers: tuple[str, ...] = ()
                if f.needs_panel:
                    peers = universe.peers.get(sym, ())
                    if not peers:
                        held["no_peer_class_panel"] = held.get("no_peer_class_panel", 0) + 1
                        continue
                for h in HORIZONS:
                    out.append(Cell(cell_id(f.key, sym, TIMEFRAME, h), f.key, sym, h, peers,
                                    universe.classes.get(sym, "")))
    out.sort(key=lambda c: c.cid)
    return out, held


# ============================================================================ evaluability
class Bars:
    """H1 bars by symbol, tail-trimmed, cached for the pass."""

    def __init__(self, paths: Paths, tail: int = EVAL_TAIL_BARS) -> None:
        self.paths = paths
        self.tail = tail
        self.cache: dict[str, pd.DataFrame | None] = {}

    def get(self, sym: str) -> pd.DataFrame | None:
        if sym not in self.cache:
            p = self.paths.universe / f"{sym}_H1.parquet"
            try:
                df = pd.read_parquet(p)
                df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
                df = df[~df.index.isna()]
                df = df[~df.index.duplicated(keep="last")].sort_index().tail(self.tail)
                self.cache[sym] = df if {"open", "high", "low", "close"} <= set(df.columns) \
                    else None
            except Exception:
                self.cache[sym] = None
        return self.cache[sym]


def evaluability(f: fc.Formula, sym: str, peers: Iterable[str], bars: Bars) -> str:
    """'' when the formula evaluates to a usable series on `sym`'s recent bars, else why not.
    Computed on the symbol's OWN bar clock, peers reindexed onto it -- exactly as the executor
    (`family_formula`) computes it."""
    own = bars.get(sym)
    if own is None or len(own) < 3 * RECIPE["norm"]:
        return "too_few_bars"
    members: dict[str, pd.DataFrame] = {sym: own}
    if f.needs_panel:
        for p in peers:
            b = bars.get(p)
            if b is not None:
                members[p] = b
    fields = fo.panel_from_bars(members, index=own.index)
    try:
        col = fc.evaluate(f.key, fields)[sym]
    except fo.MissingField as exc:
        return f"missing_field: {exc}"[:80]
    except fo.FormulaError as exc:
        return f"formula_error: {exc}"[:80]
    vals = col.to_numpy(dtype=float)
    finite = np.isfinite(vals)
    if finite.mean() < MIN_FINITE_SHARE:
        return "mostly_nan"
    if len(np.unique(np.round(vals[finite], 12))) < MIN_DISTINCT:
        return "constant"
    # THE ENTRY THE EXECUTOR USES, CHECKED ON THE PANEL THE CELL WILL CARRY (replaces the old
    # MIN_PANEL_PEERS=6 floor, audit 2026-10-13 MF2). `family_formula` enters on the 240-bar
    # TIME-SERIES z of the series; a cell whose z never reaches entry_z on a year of the symbol's
    # own bars is one the judge can only file as "never fires". Measured, not derived: on the
    # fixture 17 of 30 cross-sectional GTJA formulas fire with ONE peer, while a pure RANK needs
    # about four -- a fixed peer floor was wrong both ways. Construction only; returns unread.
    norm = int(RECIPE["norm"])
    roll = col.astype(float).rolling(norm, min_periods=norm)
    z = ((col.astype(float) - roll.mean()) / roll.std()).to_numpy(dtype=float)
    if not np.any(np.abs(z[np.isfinite(z)]) >= float(RECIPE["entry_z"])):
        return "z_never_reaches_entry"
    return ""


# ============================================================================ near-duplicates
def evaluated_signal(f: fc.Formula, sym: str, peers: Iterable[str],
                     bars: Bars) -> pd.Series | None:
    """The formula's evaluated series on `sym`'s recent bars (peers reindexed onto them), or
    None when it cannot be evaluated there -- the same computation `evaluability` checks."""
    own = bars.get(sym)
    if own is None or len(own) < 3 * RECIPE["norm"]:
        return None
    members: dict[str, pd.DataFrame] = {sym: own}
    if f.needs_panel:
        for p in peers:
            b = bars.get(p)
            if b is not None:
                members[p] = b
        if len(members) < 2:
            return None
    try:
        col = fc.evaluate(f.key, fo.panel_from_bars(members, index=own.index))[sym]
    except (fo.FormulaError, KeyError):
        return None
    v = pd.Series(np.asarray(col, dtype=float), index=own.index)
    if np.isfinite(v.to_numpy()).mean() < MIN_FINITE_SHARE:
        return None
    return v


def reference_symbols(universe: Universe) -> list[str]:
    """The symbols duplicates are read on: the named references in scope, then the first
    in-scope symbols, up to DEDUP_N_REFERENCE."""
    refs = [s for s in DEDUP_REFERENCE if s in universe.in_scope]
    for s in universe.in_scope:
        if len(refs) >= DEDUP_N_REFERENCE:
            break
        if s not in refs:
            refs.append(s)
    return refs


def near_duplicates(universe: Universe, bars: Bars, libraries: Sequence[str] = EMITTED,
                    rho: float = DEDUP_RHO) -> dict[str, Any]:
    """Clusters of published formulas that are the same signal: SIGNED corr > `rho` between their
    evaluated series on EVERY reference symbol where both evaluate (and on at least one). One
    representative per cluster -- the first in library order (EMITTED), then by key -- is
    minted; the rest map to it in `duplicate_of`. An anti-correlated pair (corr < -rho) is NOT a
    duplicate: cells mint `follow` only, so the member is the representative's fade, a distinct
    trade. Reads the formulas' values only, never a return: a construction fact, not a screen
    and not a trial charge."""
    formulas = [f for lib in libraries for f in fc.by_library(lib) if f.status == "TESTABLE"]
    rank = {f.key: (list(libraries).index(f.library), f.key) for f in formulas}
    refs = reference_symbols(universe)
    dup: dict[tuple[str, str], bool] = {}
    for sym in refs:
        cols = {}
        for f in formulas:
            v = evaluated_signal(f, sym, universe.peers.get(sym, ()), bars)
            if v is not None:
                cols[f.key] = v
        if len(cols) < 2:
            continue
        frame = pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan)
        corr = frame.corr(min_periods=RECIPE["norm"]).to_numpy()
        keys = list(frame.columns)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = sorted((keys[i], keys[j]), key=lambda k: rank[k])
                c = corr[i, j]
                if not np.isfinite(c):
                    continue
                dup[(a, b)] = dup.get((a, b), True) and bool(c > rho)
    parent: dict[str, str] = {}

    def find(k: str) -> str:
        while parent.get(k, k) != k:
            k = parent[k]
        return k

    for (a, b), same in sorted(dup.items()):
        if not same:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            keep, drop = sorted((ra, rb), key=lambda k: rank[k])
            parent[drop] = keep
    clusters: dict[str, list[str]] = {}
    for k in parent:
        clusters.setdefault(find(k), []).append(k)
    out = [{"representative": rep, "members": sorted({rep, *ms}, key=lambda k: rank[k])}
           for rep, ms in sorted(clusters.items(), key=lambda kv: rank[kv[0]])]
    return {"rho": rho, "reference_symbols": refs, "clusters": out,
            "duplicate_of": {m: c["representative"] for c in out for m in c["members"]
                             if m != c["representative"]}}


def _dedupe_fingerprint(universe: Universe, libraries: Sequence[str] = EMITTED) -> str:
    keys = sorted(f.key for lib in libraries for f in fc.by_library(lib)
                  if f.status == "TESTABLE")
    raw = json.dumps([keys, reference_symbols(universe), DEDUP_RHO, DEDUP_RULE,
                      {s: list(universe.peers.get(s, ())) for s in reference_symbols(universe)}])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _dedupe_age_days(at: Any) -> float:
    """Age in days of a cached dedupe stamp; an unreadable stamp is infinitely old."""
    try:
        t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (datetime.now(UTC) - t).total_seconds() / 86400.0


# ============================================================================ the pass
def judge_intake(paths: Paths) -> tuple[int | None, str]:
    """The judge's own per-allocation intake for the formula family, from JUDGE_COVERAGE.json."""
    doc = read_json(paths.judge_coverage, {})
    fam = ((doc.get("families") or {}).get(FAMILY) or {}) if isinstance(doc, dict) else {}
    q = fam.get("quota") if isinstance(fam, dict) else None
    if isinstance(q, (int, float)) and q > 0:
        return int(q), f"JUDGE_COVERAGE.json families.formula.quota = {int(q)} at {doc.get('at')}"
    return None, f"{UNMEASURED}: no formula quota in {paths.judge_coverage.name}"


def charged_identities(ledger: Path) -> set[str]:
    """The `proposer_common.identity` of every cell `family_donation` has already charged for
    this source. An unreadable ledger is empty: every cell is offered and charged again."""
    out: set[str] = set()
    try:
        with ledger.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.add(str(json.loads(line).get("cell_id") or ""))
                except (ValueError, AttributeError):
                    continue
    except OSError:
        pass
    out.discard("")
    return out


def _donation_modules() -> tuple[Any, Any]:
    try:
        from research import family_donation as fd
        from research import proposer_common as pc
    except ImportError:                                           # pragma: no cover - import ctx
        import family_donation as fd  # type: ignore[no-redef]
        import proposer_common as pc  # type: ignore[no-redef]
    return fd, pc


class Producer:
    def __init__(self, paths: Paths = DEFAULT_PATHS, *, policy: Any = None,
                 donate: Any = None, dry_run: bool = False, out: Path | None = None) -> None:
        self.paths = paths
        self.out = out
        self.policy = policy
        self.dry_run = dry_run
        #: `family_donation.donate_per_family` unless a caller (a test) hands another door.
        self.donate = donate
        self.t0 = time.monotonic()

    def run(self, budget_s: float = 480.0, cap: int | None = None) -> dict[str, Any]:
        rep: dict[str, Any] = {"source": SOURCE, "generated_at": now_iso(), "dry_run": self.dry_run,
                               "budget_s": budget_s, "family": FAMILY, "timeframe": TIMEFRAME,
                               "horizons": list(HORIZONS), "side_mode": SIDE_MODE,
                               "recipe": RECIPE, "status": "STARTED"}
        census = fc.census()
        rep["libraries"] = {lib: {**census[lib], "minted": lib in EMITTED,
                                  "not_minted_because": NOT_EMITTED.get(lib, "")}
                            for lib in fc.libraries()}
        rep["formulas_implemented"] = {lib: census[lib]["testable"] for lib in fc.libraries()}
        rep["nontestable"] = {lib: [{"id": f.fid, "why": f.why_not()}
                                    for f in fc.by_library(lib) if f.status != "TESTABLE"]
                              for lib in EMITTED}
        uni = Universe.load(self.paths, self.policy)
        rep["scope"] = {"classes": sorted(set(uni.classes.values())), "symbols": uni.in_scope,
                        "n_symbols": len(uni.in_scope),
                        "by_class": {k: sorted(s for s in uni.in_scope if uni.classes[s] == k)
                                     for k in sorted(set(uni.classes.values()))},
                        "excluded": dict(sorted(uni.excluded.items())),
                        "rule": SCOPE_RULE}
        state = read_json(self.paths.state, {}) or {}
        bars = Bars(self.paths)
        fp = _dedupe_fingerprint(uni)
        cached = state.get("dedupe") if isinstance(state.get("dedupe"), dict) else {}
        if (cached.get("fingerprint") == fp and isinstance(cached.get("duplicate_of"), dict)
                and _dedupe_age_days(cached.get("at")) <= DEDUP_MAX_AGE_DAYS):
            dd = cached
        else:
            dd = {**near_duplicates(uni, bars), "fingerprint": fp, "at": now_iso()}
        cells, held = cell_space(uni, duplicates=dd["duplicate_of"])
        rep["dedupe"] = {"rho": dd["rho"], "reference_symbols": dd["reference_symbols"],
                         "n_clusters": len(dd["clusters"]),
                         "n_duplicate_formulas": len(dd["duplicate_of"]),
                         "cells_not_minted": held.get("near_duplicate", 0) * len(HORIZONS),
                         "clusters": dd["clusters"], "computed_at": dd.get("at"),
                         "max_age_days": DEDUP_MAX_AGE_DAYS,
                         "rule": ("SIGNED corr > rho between evaluated series on every reference "
                                  "symbol: one representative per cluster is minted, the same "
                                  "signal under another name. Reads formula values, never a "
                                  "return; a formula not minted is never tested and is no trial")}
        space_by_lib: dict[str, int] = {}
        for c in cells:
            lib = c.formula.library
            space_by_lib[lib] = space_by_lib.get(lib, 0) + 1
        intake, intake_basis = judge_intake(self.paths)
        bound = cap if cap is not None else max(intake or 0, EMIT_FLOOR)
        rep["bound"] = {"new_cells_per_pass": bound, "judge_intake": intake,
                        "judge_intake_basis": intake_basis, "floor": EMIT_FLOOR,
                        "rule": "max(judge's measured formula intake, floor): never below what "
                                "the judge accepts"}
        rep["cell_space"] = {"total": len(cells), "by_library": space_by_lib,
                             "held_out": held,
                             "id_rule": "fl_ + sha256(formula_key|symbol|timeframe|horizon)[:24]"}
        if not cells:
            rep["status"] = "NO_CELLS"
            rep["why"] = "no testable formula x in-scope symbol cell exists on this host"
            return self.finish(rep)
        fd, pc = _donation_modules()
        charged = charged_identities(self.paths.ledger)
        charged_by_lib: dict[str, int] = {}
        for c in cells:
            if pc.identity(c.symbol, FAMILY, c.params()) in charged:
                charged_by_lib[c.formula.library] = charged_by_lib.get(c.formula.library, 0) + 1
        cursor = str(state.get("cursor") or "")
        start = next((i for i, c in enumerate(cells) if c.cid > cursor), 0)
        order = cells[start:] + cells[:start]
        counts = {"scanned": 0, "new": 0, "already_charged": 0, "unevaluable": 0}
        unevaluable: dict[str, int] = {}
        new_by_lib: dict[str, int] = {}
        new_symbols: set[str] = set()
        verdict: dict[tuple[str, str], str] = {}
        rows: list[dict[str, Any]] = []
        last = cursor
        stop_reason = "space_walked"
        for c in order:
            if counts["new"] >= bound:
                stop_reason = "bound_reached"
                break
            if time.monotonic() - self.t0 > budget_s:
                stop_reason = "budget_spent"
                break
            counts["scanned"] += 1
            last = c.cid
            if pc.identity(c.symbol, FAMILY, c.params()) in charged:
                counts["already_charged"] += 1
                continue
            vk = (c.key, c.symbol)
            if vk not in verdict:
                verdict[vk] = evaluability(c.formula, c.symbol, c.peers, bars)
            why = verdict[vk]
            if why:
                counts["unevaluable"] += 1
                k = why.split(":")[0]
                unevaluable[k] = unevaluable.get(k, 0) + 1
                continue
            rows.append(c.row())
            counts["new"] += 1
            new_by_lib[c.formula.library] = new_by_lib.get(c.formula.library, 0) + 1
            new_symbols.add(c.symbol)
        donate = self.donate or fd.donate_per_family
        donation: dict[str, Any] = {}
        if rows:
            try:
                donation = donate(SOURCE, rows, ledger=self.paths.ledger, dry_run=self.dry_run)
            except Exception as exc:
                rep["status"] = "DONATION_FAILED"
                rep["why"] = f"{type(exc).__name__}: {exc}"[:300]
                rep["pass"] = {**counts, "stop": stop_reason}
                return self.finish(rep)
        trials = int(donation.get("tests_run_total") or 0)
        rep["pass"] = {**counts, "new_by_library": new_by_lib,
                       "unevaluable_by_reason": dict(sorted(unevaluable.items())),
                       "symbols_with_new_cells": sorted(new_symbols),
                       "stop": stop_reason, "cursor_from": cursor, "cursor_to": last,
                       "rule": "every donated cell is charged as a trial once, through "
                               "family_donation's per-family tests_run (post chart x session "
                               "expansion); a cell already in its ledger is skipped, never "
                               "re-offered and never charged twice"}
        rep["donation"] = {k: donation.get(k) for k in
                           ("offered", "already_charged", "incomplete", "tests_run_by_family",
                            "tests_run_total", "donated_by_family", "donated_total",
                            "refused_wrong_lane", "files")} if donation else {}
        rep["trials_charged"] = trials
        if rows and trials < len(rows) - int(donation.get("already_charged") or 0) \
                - int(donation.get("incomplete") or 0):
            # Never reached through family_donation (its charge is >= the rows it donates); a
            # door that charges fewer trials than it was handed cells is named, not absorbed.
            rep["status"] = "UNDER_CHARGED"
            rep["why"] = f"{trials} trials charged for {len(rows)} cells offered"
            return self.finish(rep)
        rep["charged_by_library"] = {k: charged_by_lib.get(k, 0) + new_by_lib.get(k, 0)
                                     for k in sorted(set(charged_by_lib) | set(new_by_lib))}
        if not self.dry_run:
            atomic_json(self.paths.state, {"cursor": last, "at": now_iso(),
                                           "space": len(cells), "dedupe": dd})
        rep["status"] = "RAN"
        return self.finish(rep)

    def finish(self, rep: dict[str, Any]) -> dict[str, Any]:
        rep["seconds"] = round(time.monotonic() - self.t0, 1)
        rep["volume_proxy"] = ("every formula reading VOLUME/$volume reads the broker's TICK "
                               "count (Fusion publishes no exchange volume); the cell's lineage "
                               "carries volume_proxy='tick'")
        rep["live_yield"] = (f"{UNMEASURED} until the gauntlet judges the donated cells on the "
                             "box's own bars")
        if not self.dry_run:
            atomic_json(self.paths.report, rep)
        elif self.out is not None:
            # A DRY RUN NEVER WRITES THE LIVE REPORT, STATE, LEDGER OR INTAKE; with --out it
            # writes its report to that path only, stamped dry_run true.
            atomic_json(self.out, rep)
        return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=480.0)
    ap.add_argument("--cap", type=int, default=None, help="override the per-pass bound")
    ap.add_argument("--dry-run", action="store_true",
                    help="count; never donate, never write the live report, state or ledger")
    ap.add_argument("--out", type=Path, default=None,
                    help="with --dry-run: write the dry report here (never the live path)")
    a = ap.parse_args(argv)
    env = os.environ.get("QUANT_LEG_BUDGET_S")
    budget = float(a.budget_s)
    if env:
        with contextlib.suppress(ValueError):
            budget = min(budget, max(30.0, float(env) - 60.0))
    if a.out is not None and not a.dry_run:
        ap.error("--out is for --dry-run only; a live pass writes reports/FORMULA_LIBRARY.json")
    rep = Producer(dry_run=a.dry_run, out=a.out).run(budget, a.cap)
    p = rep.get("pass") or {}
    print(f"formula_library: {rep.get('status')} in {rep.get('seconds')}s -- implemented "
          f"{rep.get('formulas_implemented')}; space "
          f"{(rep.get('cell_space') or {}).get('total')}; new {p.get('new')} / already charged "
          f"{p.get('already_charged')} / unevaluable {p.get('unevaluable')}; trials charged "
          f"{rep.get('trials_charged')}{'; DRY RUN' if a.dry_run else ''}", flush=True)
    return 0 if rep.get("status") in ("RAN", "NO_CELLS") else 1


if __name__ == "__main__":
    sys.exit(main())
