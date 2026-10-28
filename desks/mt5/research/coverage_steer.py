"""COVERAGE STEER: every producer aims at ground nobody has mined BEFORE it emits.

THE PRINCIPAL, 2026-10-28: "ur job is to stop miners from producing them and the 78% next time
should be all independent with same breadth hunts js differently directed ... without reducing
quantity".

WHAT THE 78% IS, MEASURED (git docket snapshot f7f0a1ff, 57,538 rows; the box docket is larger and
the shape is the same). `miner_candidates.json` -- the compiler, 96% of all rows -- repeats an
already-mined judge rule (`judge_coverage.structural_cell`) on 78.2% of its rows; the docket as a
whole 76.7%. Two different things hide inside that number:

    1. DISTINCT RULES THE KEY CANNOT SEE. `structural_cell` keys family|symbol|horizon|chart|
       session|regime|direction|representation and nothing else, so `exit_operated` wrapped around
       26 different base families on ADAUSD H1 is ONE cell. Counting categorical params (strings,
       booleans, symbol lists: `base_family`, `exit_on_anchor_flip`, `peer_symbol`) as structure,
       the duplicate share is 33.5%, not 76.7%. Those rows are new rules already; steering them
       away would throw a real rule out to make a number look better, so they are never touched.
    2. THRESHOLD REPEATS. The same rule on the same instrument, chart, session and regime with only
       a number changed. Those are the duplicates this module stops.

WHAT IT DOES. `CoverageMap` is the shared record of what has been mined: which STRUCTURAL rules
(the judge's L1 cell plus categorical params, `structural_key`) are already claimed and by which
cell, which correlation clusters each rule shape already sits in, which instruments each family
runs on, and how thinly each family covers each chart, session and regime. The merge writes it
beside the docket every pass (`data/hypotheses/coverage_map.json`); every producer reads it.

`Steerer.steer(rows, producer)` walks a producer's batch in its own order. A row whose structural
rule nobody holds goes out unchanged. A row that repeats a held rule is MOVED, before it is
emitted, onto the nearest empty ground of the SAME mechanism, in order of how independent the new
bet is:

    1. instrument   an instrument the same family already runs on, in a correlation cluster that
                    holds no member of this rule shape (`hypothesis_families`' re-aim order);
    2. chart        another chart with bars on the same instrument, thinnest for the family first;
    3. session      asia / london / ny, only where the firing-hours oracle says the rule can fire;
    4. regime       high_vol / low_vol / month_end / quarter_end, the desk-defined masks
                    `mt5desk.cell_modifiers` applies;
    5. instrument x chart, when every single move above is already held.

Every move is one the judge EXECUTES differently -- the gauntlet loads that chart, filters that
session, applies that mask -- and each is checked before it is taken: the lane law
(`universe_policy.may_hypothesise`), the judge's unrunnable bank, the judge's own deterministic
preflight (`external_gauntlet.modifier_preflight`), the chart pin (`timeframe_of`) and the bars on
disk. A move that would only change a label is never taken, because that would be breadth on
paper and the same bet in the book. Horizon is not an axis: not every family reads it.

QUANTITY IS CONSERVED EXACTLY. One row in, one row out, for every row: a repeat with no lawful empty
ground left goes out unchanged and is counted `unsteerable`. Nothing is dropped, capped or delayed,
so no miner's throughput moves (never-throttle-mining).

ONCE PER PARENT, EVER. Producers re-emit their recent window every pass. A parent that was steered
before is given the SAME child again (`steered` in the map, folded in from `steer_ledger.jsonl`),
which then collapses at the merge as an exact re-proposal. Re-emission never fans one idea out
across the universe hour after hour.

NOT A TRIAL, AND BLIND. Steering runs no backtest and reads no verdict: the map holds which cells
EXIST, never how any scored, so no outcome can leak into what gets proposed. A steered child is a
fresh candidate, judged and counted in the trial census exactly like any other row; it carries the
source and mechanism only (never the parent's `genome_id`, `axis`, `failure_prior`, `premortem`,
nor its `contributing_sources`: no source named the new ground). Fail closed: if the lane law, the
map, the re-aim ledger or the unrunnable bank cannot be read -- or the bank is EMPTY, which the
judge's reader cannot tell apart from missing -- NOTHING is moved and the report says why. A
parent `hypothesis_families.reaim` already gave a child is never steered as well.

THE ONE-TIME STEP IN THE DOCKET, STATED. Producers re-emit already-banked rows, and the bank keeps
every row it ever held. So the first passes after this lands steer the banked threshold repeats the
producers re-emit (~15k on the git docket, 53,172 of the compiler's 53,174 rows were banked): the
parents stay in the bank and each gains ONE child, a new structural cell the judge has never seen.
That is new breadth and new trials, counted as such (journalled in context/), once per parent;
after it, the step is zero and only fresh repeats are steered.

    python -c "from research import coverage_steer as c; print(c.CoverageMap.load().summary())"
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = BASE / "data" / "hypotheses"
MAP = HYP / "coverage_map.json"
LEDGER = HYP / "steer_ledger.jsonl"
REPORT = BASE / "reports" / "MINING_NOVELTY.json"
UNIVERSE = BASE / "data" / "universe"

VERSION = "coverage-steer-v1"
MAP_VERSION = 2

#: Params already inside the judge's L1 cell (or naming the chart): never part of the signature.
_L1_PARAMS = frozenset({"timeframe", "session", "selector", "regime", "condition", "direction",
                        "side", "representation", "feature", "horizon"})
#: The chart ladder a move may use, in the order a tie is broken (H1 by absence, never written).
CHARTS = ("M5", "M15", "M30", "H4", "D1", "M1", "H1")
SESSIONS = ("asia", "london", "ny")
REGIMES = ("high_vol", "low_vol", "month_end", "quarter_end")
#: Candidate moves examined per duplicate before it is declared unsteerable. A DETERMINISTIC work
#: bound (never wall-clock: under contention a time limit would make output depend on load).
MAX_TRIES = 64
#: Instruments crossed with charts in the two-axis pass.
COMBO_SYMBOLS = 8
#: Days of per-day novelty kept.
DAILY_WINDOW = 60

_UNMEASURED = "?"


# ------------------------------------------------------------------------------------ keys
def _h(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def _sym(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("sym") or "").strip()


def _fam(row: Mapping[str, Any]) -> str:
    return str(row.get("family") or "").strip()


def identity(row: Mapping[str, Any]) -> str:
    """merge_hypotheses._identity, spelled identically (that module is the docket's writer)."""
    params = row.get("params") or {}
    return json.dumps({
        "symbol": _sym(row), "family": _fam(row),
        "params": {k: params[k] for k in sorted(params)},
    }, sort_keys=True, default=str)


def _categorical(v: Any) -> Any:
    """The structural part of a param value -- the SAME rule as the Judge's
    `hypothesis_families._categorical` (judge_l1_categorical v1): bools and non-numeric words
    stay, numbers and numeric strings are thresholds and drop out, dicts and lists keep their
    categorical leaves only."""
    if isinstance(v, bool):
        return v
    if v is None or isinstance(v, (int, float)):
        return None
    if isinstance(v, str):
        txt = v.strip()
        try:
            float(txt)
            return None
        except ValueError:
            return txt.lower() or None
    if isinstance(v, Mapping):
        out = {str(k): c for k, c in ((k, _categorical(x)) for k, x in v.items()) if c is not None}
        return out or None
    if isinstance(v, (list, tuple, set, frozenset)):
        items = [c for c in (_categorical(x) for x in v) if c is not None]
        if isinstance(v, (set, frozenset)):
            items.sort(key=lambda c: json.dumps(c, sort_keys=True, default=str))
        return items or None
    return str(v).lower()


def signature(row: Mapping[str, Any]) -> str:
    """Categorical params outside the L1 cell, canonical JSON ('' when there are none)."""
    params = row.get("params") or {}
    if not isinstance(params, Mapping):
        return ""
    cat = {str(k): c for k, c in ((k, _categorical(params[k])) for k in sorted(params, key=str)
                                  if str(k) not in _L1_PARAMS) if c is not None}
    return json.dumps(cat, sort_keys=True, separators=(",", ":"), default=str) if cat else ""


def _judge_has_categorical() -> bool:
    try:
        from research import hypothesis_families as hf
        return hasattr(hf, "categorical_suffix")
    except Exception:
        return False


#: True once the Judge's own L1 key carries the categorical params (judge_l1_categorical): the
#: steer then uses that key verbatim, so the steer and the judge can never disagree on a rule.
_JUDGE_CATEGORICAL = _judge_has_categorical()
#: The key the map was built with; a map built under another key is never steered against.
KEY_VERSION = ("judge:hypothesis_families.rule_key" if _JUDGE_CATEGORICAL
               else "local:l1+categorical-v1")


def _l1(row: dict[str, Any]) -> str:
    from research.hypothesis_families import rule_key
    return rule_key(row)


def structural_key(row: dict[str, Any], rule: str | None = None) -> str:
    """The judge's L1 rule plus categorical params: two rows share it only when they differ in
    numeric thresholds alone. That, and only that, is a duplicate here. Spelled exactly as the
    Judge spells it (`base|{categorical json}`), whichever of the two modules supplies it."""
    r = rule if rule is not None else _l1(row)
    if _JUDGE_CATEGORICAL:
        return r
    sig = signature(row)
    return f"{r}|{sig}" if sig else r


def _swap_symbol(key: str, token: str) -> str:
    parts = key.split("|", 2)
    if len(parts) > 1:
        parts[1] = token
    return "|".join(parts)


def shape(key: str) -> str:
    """A structural key with no instrument: what 'the same rule elsewhere' means."""
    return _swap_symbol(key, "*")


def _chart(row: Mapping[str, Any]) -> str:
    params = row.get("params") or {}
    return str(params.get("timeframe") or row.get("timeframe") or "H1").upper()


def _session(row: Mapping[str, Any]) -> str:
    params = row.get("params") or {}
    return str(row.get("session") or params.get("session") or params.get("selector")
               or "all").lower()


def _regime(row: Mapping[str, Any]) -> str:
    params = row.get("params") or {}
    return str(row.get("regime") or params.get("regime") or params.get("condition")
               or "all").lower()


# ------------------------------------------------------------------------------- the map
class CoverageMap:
    """What has been mined, compact enough for every producer to load every pass.

    `claims`         structural key hash -> identity hash of the first cell that holds it
    `shape_clusters` shape hash -> correlation clusters already holding that rule shape
    `family_symbols` family -> {SYMBOL: cells}: where each family already runs
    `axes`           family -> {"chart"|"session"|"regime": {value: cells}}
    `clusters`       SYMBOL -> correlation cluster (hypothesis_families' cache)
    `steered`        parent identity hash -> the child it was steered to (delta + child hash)
    Never a verdict: the map says what exists, not how anything scored."""

    def __init__(self) -> None:
        self.claims: dict[str, str] = {}
        self.shape_clusters: dict[str, set[str]] = {}
        self.family_symbols: dict[str, Counter[str]] = {}
        self.axes: dict[str, dict[str, Counter[str]]] = {}
        self.clusters: dict[str, str] = {}
        self.steered: dict[str, dict[str, Any]] = {}
        #: per UTC day of `first_seen` (from_rows only): cells, NEW structural rules, steered
        self.daily: dict[str, Counter[str]] = {}
        self.rows = 0
        self.built_at: str | None = None
        self.status = "EMPTY"

    def cluster(self, sym: str) -> str:
        s = sym.upper()
        return self.clusters.get(s) or s

    def add(self, row: dict[str, Any], ident: str | None = None,
            key: str | None = None) -> str:
        k = key if key is not None else structural_key(row)
        kh = _h(k)
        self.claims.setdefault(kh, _h(ident if ident is not None else identity(row)))
        sym = _sym(row).upper()
        self.shape_clusters.setdefault(_h(shape(k)), set()).add(self.cluster(sym))
        fam = _fam(row)
        if sym:
            self.family_symbols.setdefault(fam, Counter())[sym] += 1
        ax = self.axes.setdefault(fam, {"chart": Counter(), "session": Counter(),
                                        "regime": Counter()})
        ax["chart"][_chart(row)] += 1
        ax["session"][_session(row)] += 1
        ax["regime"][_regime(row)] += 1
        self.rows += 1
        return kh

    def holder(self, key: str) -> str | None:
        return self.claims.get(_h(key))

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, Any]], clusters: Mapping[str, str] | None = None,
                  *, identity_fn: Callable[[dict[str, Any]], str] = identity,
                  steered: Mapping[str, Mapping[str, Any]] | None = None) -> CoverageMap:
        """Build from the docket in its own order (the docket's first claim is the claimant)."""
        m = cls()
        m.clusters = {str(k).upper(): str(v) for k, v in (clusters or {}).items()}
        ordered = sorted(rows, key=lambda r: str(r.get("first_seen") or "9999"))
        for row in ordered:
            if isinstance(row, dict) and _fam(row):
                key = structural_key(row)
                new = m.holder(key) is None
                m.add(row, identity_fn(row), key)
                day = m.daily.setdefault(str(row.get("first_seen") or "")[:10] or "unknown",
                                         Counter())
                day["cells"] += 1
                day["novel_structural"] += int(new)
                day["steered"] += int(isinstance(row.get("steered_from"), Mapping))
            sf = row.get("steered_from") if isinstance(row, dict) else None
            if isinstance(sf, Mapping) and sf.get("parent"):
                m.steered.setdefault(str(sf["parent"]), {
                    "child": _h(identity_fn(row)), "delta": dict(sf.get("delta") or {})})
        for p, v in (steered or {}).items():
            m.steered.setdefault(str(p), dict(v))
        m.built_at = datetime.now(UTC).isoformat(timespec="seconds")
        m.status = "BUILT"
        return m

    def to_doc(self) -> dict[str, Any]:
        return {"version": MAP_VERSION, "key_version": KEY_VERSION, "steer_version": VERSION,
                "built_at": self.built_at,
                "rows": self.rows, "structural_rules": len(self.claims),
                "rule": ("structural key = judge_coverage L1 cell + categorical params; a cell "
                         "repeating one only in numeric thresholds is a duplicate. Coverage only: "
                         "no verdict is ever stored here"),
                "claims": self.claims,
                "shape_clusters": {k: sorted(v) for k, v in self.shape_clusters.items()},
                "family_symbols": {f: dict(c) for f, c in self.family_symbols.items()},
                "axes": {f: {a: dict(c) for a, c in ax.items()} for f, ax in self.axes.items()},
                "clusters": self.clusters,
                "steered": self.steered,
                "thin": self.thin()}

    def save(self, path: Path | None = None) -> bool:
        return _atomic_write(path or MAP, json.dumps(self.to_doc(), separators=(",", ":"),
                                                     default=str))

    @classmethod
    def load(cls, path: Path | None = None) -> CoverageMap:
        m = cls()
        try:
            doc = json.loads((path or MAP).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            m.status = "ABSENT"
            return m
        if not isinstance(doc, dict) or int(doc.get("version") or 0) != MAP_VERSION:
            m.status = "WRONG_VERSION"
            return m
        if doc.get("key_version") != KEY_VERSION:
            # the judge's key changed under the map: the next merge rebuilds it; until then the
            # claims would be read under the wrong key, so nothing is steered
            m.status = "WRONG_KEY"
            return m
        m.claims = {str(k): str(v) for k, v in (doc.get("claims") or {}).items()}
        m.shape_clusters = {k: set(v) for k, v in (doc.get("shape_clusters") or {}).items()}
        m.family_symbols = {f: Counter(c) for f, c in (doc.get("family_symbols") or {}).items()}
        m.axes = {f: {a: Counter(c) for a, c in ax.items()}
                  for f, ax in (doc.get("axes") or {}).items()}
        m.clusters = dict(doc.get("clusters") or {})
        m.steered = dict(doc.get("steered") or {})
        m.rows = int(doc.get("rows") or 0)
        m.built_at = doc.get("built_at")
        m.status = "LOADED"
        return m

    def thin(self, per_axis: int = 10) -> dict[str, Any]:
        """The emptiest ground, for producers that choose WHAT to hunt (families, instruments,
        charts): per family, the declared charts/sessions/regimes it holds fewest cells on, and
        the families running on fewest instruments."""
        fams = sorted(self.family_symbols.items(), key=lambda kv: (len(kv[1]), kv[0]))
        per_family: dict[str, Any] = {}
        for fam, ax in self.axes.items():
            per_family[fam] = {
                "chart": _thinnest(ax.get("chart") or Counter(), CHARTS, per_axis),
                "session": _thinnest(ax.get("session") or Counter(), SESSIONS, per_axis),
                "regime": _thinnest(ax.get("regime") or Counter(), REGIMES, per_axis),
                "instruments": len(self.family_symbols.get(fam) or ())}
        return {"families_on_fewest_instruments": [
                    {"family": f, "instruments": len(c)} for f, c in fams[:25]],
                "per_family": per_family}

    def summary(self) -> dict[str, Any]:
        return {"status": self.status, "built_at": self.built_at, "rows": self.rows,
                "structural_rules": len(self.claims), "families": len(self.family_symbols),
                "steered_parents": len(self.steered)}


def _thinnest(counts: Counter[str], declared: Iterable[str], n: int) -> list[dict[str, Any]]:
    vals = {v: int(counts.get(v, 0)) for v in declared}
    return [{"value": v, "cells": c} for v, c in sorted(vals.items(), key=lambda kv: (kv[1], kv[0]))
            ][:n]


# ------------------------------------------------------------------------------ the checks
def _lawful() -> Callable[[str, str], bool] | None:
    try:
        from research.hypothesis_families import _lawful as hf_lawful
        return hf_lawful()
    except Exception:
        return None


def _unrunnable() -> Callable[[dict[str, Any]], bool] | None:
    """True for a spec the judge's unrunnable bank holds, or None -- and None closes the steer.

    An EMPTY bank is None too: `judge_coverage.unrunnable_bank()` returns {} for a missing or
    unreadable file, which is indistinguishable from "nothing is unrunnable" and would let a
    child be aimed at a cell the judge drops (audit of 17ccb785, MF3). UNMEASURED, not clean."""
    try:
        from research.frontier_identity import docket_cell_id
        from research.judge_coverage import unrunnable_bank
        bank = set(unrunnable_bank())
    except Exception:
        return None
    if not bank:
        return None

    def blocked(spec: dict[str, Any]) -> bool:
        try:
            return str(docket_cell_id(spec)) in bank
        except Exception:
            return True
    return blocked


def _reaimed(hyp_dir: Path | None) -> set[str] | None:
    """Parents `hypothesis_families.reaim` already gave a child (its ledger): never steered too,
    so one parent never holds two descendants. None when the ledger cannot be read at all."""
    try:
        from research.hypothesis_families import REAIM_LEDGER, reaimed_parents
        return reaimed_parents((hyp_dir / REAIM_LEDGER.name) if hyp_dir else None)
    except Exception:
        return None


def _gauntlet_checks() -> tuple[Callable[[dict[str, Any]], str | None] | None,
                                Callable[[dict[str, Any] | None, str], str] | None]:
    """(modifier_preflight, timeframe_of) from the sealed judge itself, or (None, None) -- in
    which case only instrument moves (params unchanged, so the parent's preflight stands) run."""
    try:
        scripts = str(BASE / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import external_gauntlet as eg  # type: ignore[import-not-found]
        return eg.modifier_preflight, eg.timeframe_of
    except Exception:
        return None, None


def _firing() -> Callable[..., list[Any]] | None:
    try:
        from libs.research.family_firing import session_cells
        return session_cells
    except Exception:
        return None


def has_bars(sym: str, chart: str, universe: Path | None = None) -> bool:
    return (Path(universe or UNIVERSE) / f"{sym}_{chart.upper()}.parquet").exists()


# ------------------------------------------------------------------------------- the steer
#: Provenance a child may carry -- the SOURCE and its MECHANISM only. Never a field that
#: describes the parent's own cell (`genome_id` names a different docket cell and would merge
#: child and parent in breadth_unit; `axis`, `failure_prior*`, `premortem` were derived for the
#: parent's chart/session) and never `contributing_sources` (no source named the new ground).
_SAFE = ("source", "producer", "origin", "title", "url", "source_url",
         "mechanism", "mechanism_status", "mechanism_note", "hypothesis", "why", "priority")
#: Charts on which a session window is a real filter: `session_filter` keys on the bar's hour,
#: so a D1/W1 bar (stamped 00:00) is "asia" whatever it holds and never "london"/"ny", and an H4
#: bar straddles windows. A session move is offered only on these.
SESSION_CHARTS = frozenset({"M1", "M5", "M15", "M30", "H1"})


class Steerer:
    """One producer pass worth of steering against one map. Reuse it across a producer's batches
    in the same pass so a rule claimed by batch 1 is held for batch 2."""

    def __init__(self, cmap: CoverageMap, *,
                 lawful: Callable[[str, str], bool] | None = None,
                 blocked: Callable[[dict[str, Any]], bool] | None = None,
                 preflight: Callable[[dict[str, Any]], str | None] | None = None,
                 chart_of: Callable[[dict[str, Any] | None, str], str] | None = None,
                 sessions: Callable[..., list[Any]] | None = None,
                 bars: Callable[[str, str], bool] | None = None,
                 tradeable: Callable[[str], bool] | None = None,
                 identity_fn: Callable[[dict[str, Any]], str] = identity,
                 resolve: bool = True,
                 reaimed: set[str] | None = None,
                 hyp_dir: Path | None = None,
                 now: datetime | None = None) -> None:
        self.map = cmap
        self.lawful = lawful if lawful is not None or not resolve else _lawful()
        self.blocked = blocked if blocked is not None or not resolve else _unrunnable()
        if resolve and preflight is None and chart_of is None:
            preflight, chart_of = _gauntlet_checks()
        self.preflight, self.chart_of = preflight, chart_of
        self.sessions = sessions if sessions is not None or not resolve else _firing()
        self.bars = bars or has_bars
        self.tradeable = tradeable
        self.identity_fn = identity_fn
        self.reaimed = reaimed if reaimed is not None or not resolve else _reaimed(hyp_dir)
        self.at = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        closed = []
        if cmap.status not in ("LOADED", "BUILT"):
            closed.append(f"coverage map {cmap.status}")
        if self.lawful is None:
            closed.append("lane law (universe_policy) unavailable")
        if self.blocked is None:
            closed.append("unrunnable bank absent, empty or unreadable (UNMEASURED)")
        if self.reaimed is None:
            closed.append("re-aim ledger unreadable")
        self.closed = closed
        self.by_producer: dict[str, Counter[str]] = {}
        self.by_axis: Counter[str] = Counter()
        self.children: list[dict[str, Any]] = []

    # -- candidate moves, most independent first --------------------------------------------
    def _moves(self, row: dict[str, Any], key: str) -> Iterator[dict[str, Any]]:
        fam, sym = _fam(row), _sym(row)
        held = self.map.shape_clusters.get(_h(shape(key)), set())
        ax: dict[str, Counter[str]] = self.map.axes.get(fam) or {}
        others = sorted(((self.map.cluster(s).startswith(_UNMEASURED), n, s)
                         for s, n in (self.map.family_symbols.get(fam) or {}).items()
                         if s.upper() != sym.upper() and self.map.cluster(s) not in held))
        syms = [s for _u, _n, s in others]
        for s in syms:
            yield {"axis": "instrument", "symbol": s}
        if self.preflight is None or self.chart_of is None:
            return
        cur = _chart(row)
        charts = sorted((c for c in CHARTS if c != cur),
                        key=lambda c: ((ax.get("chart") or Counter()).get(c, 0), CHARTS.index(c)))
        for c in charts:
            yield {"axis": "chart", "timeframe": c}
        if (self.sessions is not None and _session(row) == "all"
                and self._eff_chart(row) in SESSION_CHARTS):
            sess = ax.get("session") or Counter()
            for s in sorted(SESSIONS, key=lambda v: (sess.get(v, 0), v)):
                yield {"axis": "session", "session": s}
        if _regime(row) == "all":
            for g in sorted(REGIMES, key=lambda v: ((ax.get("regime") or Counter()).get(v, 0), v)):
                yield {"axis": "regime", "regime": g}
        for s in syms[:COMBO_SYMBOLS]:
            for c in charts:
                yield {"axis": "instrument+chart", "symbol": s, "timeframe": c}

    def _child(self, row: dict[str, Any], move: Mapping[str, Any]) -> dict[str, Any] | None:
        fam = _fam(row)
        params = dict(row.get("params") or {})
        sym = str(move.get("symbol") or _sym(row))
        if "timeframe" in move:
            if move["timeframe"] == "H1":
                params.pop("timeframe", None)
            else:
                params["timeframe"] = move["timeframe"]
        if "regime" in move:
            params["regime"] = move["regime"]
        if "session" in move:
            assert self.sessions is not None
            try:
                slots = self.sessions(fam, params, (move["session"],), symbol=sym)
            except Exception:
                return None
            if not slots:
                return None
            _label, p, remap = slots[0]
            if isinstance(remap, Mapping) and remap.get("remapped") is False:
                return None                     # a DEAD session with no stand-in: never minted
            params = dict(p)
        c = {k: row[k] for k in _SAFE if k in row}
        c.pop("timeframe", None)
        c.update({"symbol": sym, "family": fam, "params": params,
                  "contributing_sources": [], "n_independent_sources": 0})
        return c

    def _valid(self, child: dict[str, Any], move: Mapping[str, Any],
               parent: Mapping[str, Any] | None = None) -> bool:
        sym, fam = _sym(child), _fam(child)
        assert self.lawful is not None and self.blocked is not None
        if self.tradeable is not None and not self.tradeable(sym):
            return False
        if not self.lawful(sym, fam):
            return False
        params = child.get("params") or {}
        eff = self._eff_chart(child)
        if not self.bars(sym, eff):
            return False                        # every move: the child's own chart on disk
        if "session" in move and eff not in SESSION_CHARTS:
            return False                        # a session on D1/W1/H4 is a label or never fires
        if "timeframe" in move:
            assert self.chart_of is not None
            want = str(move["timeframe"]).upper()
            if str(self.chart_of(params, fam)).upper() != want:
                return False                    # a pinned family: the chart would be a label
            if parent is not None and str(self.chart_of(
                    dict(parent.get("params") or {}), fam)).upper() == want:
                return False                    # the parent already ran on that chart
        if self.preflight is not None:
            if self.preflight(child) is not None:
                return False
        elif move["axis"] != "instrument":
            return False
        return not self.blocked(child)

    def _eff_chart(self, row: Mapping[str, Any]) -> str:
        """The chart the judge will actually load: the family pin, else the params, else H1."""
        params = dict(row.get("params") or {})
        if self.chart_of is not None:
            try:
                return str(self.chart_of(params, _fam(row))).upper()
            except Exception:
                pass
        return _chart(row)

    def _replay(self, row: dict[str, Any], rec: Mapping[str, Any]) -> dict[str, Any] | None:
        delta = rec.get("delta") or {}
        if not isinstance(delta, Mapping) or not delta.get("axis"):
            return None
        params = delta.get("params")
        child = {k: row[k] for k in _SAFE if k in row}
        child.update({"symbol": str(delta.get("symbol") or _sym(row)), "family": _fam(row),
                      "params": dict(params) if isinstance(params, Mapping)
                      else dict(row.get("params") or {}),
                      "contributing_sources": [], "n_independent_sources": 0})
        return child

    def _stamp(self, child: dict[str, Any], parent_ident: str, status: str, axis: str,
               producer: str) -> dict[str, Any]:
        delta = {"axis": axis, "symbol": child["symbol"], "params": child["params"]}
        child["steered_from"] = {"version": VERSION, "parent": _h(parent_ident),
                                 "parent_status": status, "axis": axis, "at": self.at,
                                 "by": producer, "delta": delta,
                                 "why": ("the parent repeated a structural rule already mined "
                                         "(threshold-only difference); the same mechanism was "
                                         "moved to the nearest lawful empty ground before it "
                                         "was emitted")}
        child["available_time"] = self.at
        child["ingested_time"] = self.at
        child["source_version"] = VERSION
        child["payload_hash"] = hashlib.sha256(json.dumps(
            {"identity": self.identity_fn(child), "parent": _h(parent_ident),
             "version": VERSION}, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        child["first_seen"] = self.at
        child["dup_status"] = "STEERED"
        return child

    def steer(self, rows: list[dict[str, Any]], producer: str) -> list[dict[str, Any]]:
        """One row out per row in, in the same order. Never raises past a row: a fault on one row
        sends that row out unchanged."""
        tally = self.by_producer.setdefault(producer, Counter())
        out: list[dict[str, Any]] = []
        tally["rows_in"] += len(rows)
        for row in rows:
            if not isinstance(row, dict) or not _fam(row) or not _sym(row):
                out.append(row)
                tally["passed_unkeyed"] += 1
                continue
            try:
                out.append(self._one(row, producer, tally))
            except Exception:
                tally["fault_passed_unchanged"] += 1
                out.append(row)
        tally["rows_out"] += len(out)
        return out

    def _one(self, row: dict[str, Any], producer: str, tally: Counter[str]) -> dict[str, Any]:
        tally["emitted"] += 1
        if isinstance(row.get("steered_from"), Mapping):
            # Already steered upstream (the compiler, then the merge): never steered twice.
            tally["arrived_steered"] += 1
            self.map.add(row, self.identity_fn(row))
            tally["novel_out"] += 1
            return row
        ident = self.identity_fn(row)
        key = structural_key(row)
        holder = self.map.holder(key)
        ih = _h(ident)
        if holder is None or holder == ih:
            self.map.add(row, ident, key)
            tally["novel_in"] += 1
            tally["novel_out"] += 1
            return row
        status = "REPEAT"
        tally["duplicate_in"] += 1
        if self.closed:
            tally["unsteered_fail_closed"] += 1
            return row
        if self.reaimed is not None and ident in self.reaimed:
            tally["already_reaimed"] += 1       # hypothesis_families gave it a child already
            return row
        rec = self.map.steered.get(ih)
        if rec:
            child = self._replay(row, rec)
            if child is not None:
                axis = str((rec.get("delta") or {}).get("axis"))
                move: dict[str, Any] = {"axis": axis}
                if self._eff_chart(child) != self._eff_chart(row):
                    move["timeframe"] = self._eff_chart(child)
                if _session(child) != _session(row):
                    move["session"] = _session(child)
                # RE-VALIDATED, never trusted: the lane law, the bank or the bars may have moved
                # since the child was first minted; an invalid replay is searched afresh below
                if self._valid(child, move, row):
                    tally["replayed_prior_child"] += 1
                    return self._stamp(child, ident, status, axis, producer)
                tally["replay_invalid_researched"] += 1
        tries = 0
        for move in self._moves(row, key):
            tries += 1
            if tries > MAX_TRIES:
                break
            child = self._child(row, move)
            if child is None:
                continue
            ck = structural_key(child)
            if self.map.holder(ck) is not None:
                continue
            if not self._valid(child, move, row):
                continue
            child = self._stamp(child, ident, status, str(move["axis"]), producer)
            self.map.add(child, self.identity_fn(child), ck)
            self.map.steered[ih] = {"child": _h(self.identity_fn(child)),
                                    "delta": child["steered_from"]["delta"]}
            self.children.append(child)
            tally["steered"] += 1
            tally["novel_out"] += 1
            self.by_axis[str(move["axis"])] += 1
            return child
        tally["unsteerable"] += 1
        return row

    def report(self) -> dict[str, Any]:
        per: dict[str, Any] = {}
        tot: Counter[str] = Counter()
        for prod, c in sorted(self.by_producer.items()):
            tot.update(c)
            per[prod] = _shares(c)
        return {"at": self.at, "version": VERSION, "map": self.map.summary(),
                "fail_closed": self.closed or None,
                "checks": {"preflight": self.preflight is not None,
                           "chart_pin": self.chart_of is not None,
                           "session_oracle": self.sessions is not None},
                "total": _shares(tot), "by_producer": per,
                "steered_by_axis": dict(self.by_axis),
                "conservation": {"rows_in": tot.get("rows_in", 0),
                                 "rows_out": tot.get("rows_out", 0),
                                 "removed": tot.get("rows_in", 0) - tot.get("rows_out", 0)}}



def _shares(c: Counter[str]) -> dict[str, Any]:
    emitted = int(c.get("emitted", 0))
    dup_in = int(c.get("duplicate_in", 0))
    left = dup_in - int(c.get("steered", 0)) - int(c.get("replayed_prior_child", 0))
    return {**{k: int(v) for k, v in sorted(c.items())},
            "duplicate_share_in": round(dup_in / emitted, 4) if emitted else None,
            "duplicate_share_out": round(left / emitted, 4) if emitted else None}


# ------------------------------------------------------------------------- ledger + report
def load_ledger(path: Path | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        with (path or LEDGER).open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("parent"):
                    out.setdefault(str(rec["parent"]), {"child": rec.get("child"),
                                                        "delta": rec.get("delta") or {}})
    except OSError:
        pass
    return out


def ledger_lines_for(rows: Iterable[Mapping[str, Any]], known: Mapping[str, Any],
                     identity_fn: Callable[[dict[str, Any]], str] = identity
                     ) -> list[dict[str, Any]]:
    """Ledger lines for steered children in WRITTEN rows whose parent the ledger does not hold:
    called after the docket write, so the ledger never names a child that does not exist."""
    out: list[dict[str, Any]] = []
    seen = set(known)
    for r in rows:
        sf = r.get("steered_from") if isinstance(r, Mapping) else None
        if not isinstance(sf, Mapping) or not sf.get("parent") or sf["parent"] in seen:
            continue
        seen.add(str(sf["parent"]))
        out.append({"at": sf.get("at"), "parent": sf["parent"],
                    "child": _h(identity_fn(dict(r))), "by": sf.get("by"),
                    "delta": sf.get("delta") or {}})
    return out


def append_ledger(lines: list[dict[str, Any]], path: Path | None = None) -> int:
    if not lines:
        return 0
    p = path or LEDGER
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(x, default=str, separators=(",", ":")) + "\n"
                             for x in lines))
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        return 0
    return len(lines)


def novelty_by_day(cmap: CoverageMap, window: int = DAILY_WINDOW) -> list[dict[str, Any]]:
    """Per UTC day of `first_seen`: cells mined, NEW structural rules (first claim that day),
    steered children -- the headline 'novel independent cells per day', read off the map build
    so the keys are computed once."""
    out = []
    for d in sorted(cmap.daily)[-window:]:
        c = cmap.daily[d]
        out.append({"day": d, "cells": c["cells"], "novel_structural": c["novel_structural"],
                    "steered": c["steered"],
                    "novel_share": round(c["novel_structural"] / c["cells"], 4)
                    if c["cells"] else None})
    return out


def fence(report: Mapping[str, Any]) -> dict[str, Any]:
    """The invariant, not a tuned number: every duplicate a producer emitted was either moved to
    empty ground or recorded unsteerable because none was lawful, and nothing was removed.
    BREACH names the producer; UNMEASURED when steering could not run at all."""
    if report.get("fail_closed"):
        return {"status": "UNMEASURED", "why": report["fail_closed"]}
    breaches = []
    for prod, c in (report.get("by_producer") or {}).items():
        dup = int(c.get("duplicate_in", 0))
        handled = (int(c.get("steered", 0)) + int(c.get("replayed_prior_child", 0))
                   + int(c.get("unsteerable", 0)) + int(c.get("unsteered_fail_closed", 0))
                   + int(c.get("already_reaimed", 0)))
        if dup > handled and int(c.get("fault_passed_unchanged", 0)) >= dup - handled:
            handled = dup                       # faulted rows went out unchanged, counted
        if dup != handled:
            breaches.append({"producer": prod, "duplicates": dup, "handled": handled})
    cons = report.get("conservation") or {}
    if cons.get("rows_in") != cons.get("rows_out"):
        breaches.append({"conservation": cons})
    return {"status": "BREACH" if breaches else "PASS", "breaches": breaches or None,
            "rule": ("every duplicate is steered or recorded unsteerable; rows out == rows in. "
                     "duplicate_share_out per producer is the number to drive to zero")}


def _atomic_write(path: Path, text: str) -> bool:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, "utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return False


def write_report(doc: Mapping[str, Any], path: Path | None = None) -> bool:
    return _atomic_write(path or REPORT, json.dumps(doc, indent=1, default=str))


def for_producer(producer: str, path: Path | None = None, **kw: Any) -> Steerer:
    """The producers' door: load the shared map and return a Steerer for this pass (the re-aim
    ledger is read from the map's own directory)."""
    p = path or MAP
    kw.setdefault("hyp_dir", p.parent)
    return Steerer(CoverageMap.load(p), **kw)
