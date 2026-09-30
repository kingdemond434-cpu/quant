#!/usr/bin/env python3
"""THE SIX COMMITTEES: deterministic specialist ensembles that challenge, never decide.

    python desks/mt5/research/committee_ensembles.py --once [--budget-s 300]
    python desks/mt5/research/committee_ensembles.py --health          # the CRO's duty read
    python desks/mt5/research/committee_ensembles.py --traps           # planted traps only

THE PRINCIPAL'S RULINGS (2026-09-30 16:59 and 17:04). Exactly six committees and no more:

    scientific       Scientific Adversarial      causal/placebo/leakage/stability/invariance
    forensic         Extreme-Return Forensic     decomposition, martingale/grid, hidden leverage,
                                                 selection bias, bootstrap luck, trade path
    portfolio_tail   Portfolio & Tail            factor rank, tail dependence, stress, ruin,
                                                 capacity, concentration, regime correlation
    execution        Execution & Microstructure  markout, spread/slippage/swap, latency,
                                                 adverse selection, fills
    data_integrity   Data & Measurement          PIT/vintage, timestamps, survivorship,
                     Integrity                   reconciliation, missingness/anomaly
    meta_research    Meta-Research &             producer redundancy, effective rank, compute
                     Architecture                ROI, evaluator discrimination, benchmark
                                                 leakage, module ablation

Each is a set of Python specialists over typed evidence (`libs/research/committee_engine.py`
owns the machinery: triggers and L0..L4 escalation, dynamic seat selection, evidence
partitions, Brier calibration, minority reports, the objection->experiment compiler and ranker,
falsification trees, cross-committee contradictions, planted traps, overlap/ablation and ROI
retirement). Macro, ML, countries and the rest stay researcher civilisations, never committees.
LLMs are optional external idea miners (`research/committees.py`, donations only) and sit on no
seat here.

"Researchers discover. Committees challenge explanations. Deterministic experiments adjudicate.
Gauntlet certifies. Portfolio optimizer allocates. Execution engine trades. Live evidence
ultimately judges everybody." So NOTHING here certifies, allocates, sizes, vetoes or trades.
The products are defect reports: challenges, the ranked experiments that would settle them, a
falsification tree per subject, the Scientific committee's lead class per cell as the falsifier
battery's ORDER hint (`premortems.json`, order only, L1.60), and the health file the daily CRO
cycle reads (`reports/COMMITTEE_HEALTH.json`).

THE NEXT EXPERIMENT IS CHOSEN BY PYTHON. A FAIL or UNMEASURED names the test that would settle
it; when that test is another seat of the same committee, the ranked queue carries the subject
into the next pass at that seat's level, highest information per second first.

A COMMITTEE THAT ADDS NO INFORMATION LOSES BUDGET. Each pass re-weights the six committees'
shares of the leg's fixed budget by their measured information per second (unique catches,
experiments saved, settled calibration), floored so no committee ever goes fully dark. A
committee whose floored share held for RETIRE_AFTER_PASSES consecutive passes with enough
measurements and nothing unique is RETIRED (traps and health keep running, so it can be
re-admitted on evidence). UNMEASURED never moves budget or retires anything (L1.28a).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import committee_engine as ce  # noqa: E402

FAIL, PASS, UNMEASURED = ce.FAIL, ce.PASS, ce.UNMEASURED

STATE_DIR = BASE / "data" / "committees"
STATE = STATE_DIR / "ensemble_state.json"
FINDINGS = STATE_DIR / "ensemble_findings.json"
PREMORTEMS = STATE_DIR / "premortems.json"
REPORT = BASE / "reports" / "COMMITTEES.json"
HEALTH = BASE / "reports" / "COMMITTEE_HEALTH.json"

BANK = BASE / "data" / "hypotheses" / "external_survivors.json"
NAMING_QUEUE = BASE / "data" / "hypotheses" / "mechanism_naming_queue.json"
MQL5 = BASE / "data" / "intelligence" / "mql5_survivors"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
MARKOUT = BASE / "reports" / "markout.json"
EXEC_QUALITY = BASE / "reports" / "execution_quality.json"
FILL_SURFACE = BASE / "reports" / "FILL_SURFACE.json"
CAPACITY = BASE / "reports" / "CAPACITY.json"
UNIVERSE_DIR = BASE / "data" / "universe"
UNIVERSE = UNIVERSE_DIR / "universe.json"
PIT_AUDIT = BASE / "reports" / "PIT_AUDIT.json"
PIT_CENSUS = BASE / "reports" / "PIT_CENSUS.json"
BREADTH = BASE / "reports" / "EFFECTIVE_BREADTH.json"
COMPUTE_LEDGER = BASE / "data" / "compute_ledger.jsonl"
RESEARCH_ROI = BASE / "reports" / "RESEARCH_ROI.json"
QUANTBENCH = BASE / "reports" / "QUANTBENCH.json"
RUNTIME_STATE = ROOT / "docs" / "research" / "runtime_state.json"

SCIENTIFIC, FORENSIC, PORTFOLIO = "scientific", "forensic", "portfolio_tail"
EXECUTION, DATA, META = "execution", "data_integrity", "meta_research"
#: Exactly six, by the principal's order. The test pins the count.
COMMITTEES: tuple[str, ...] = (SCIENTIFIC, FORENSIC, PORTFOLIO, EXECUTION, DATA, META)
TITLES = {SCIENTIFIC: "Scientific Adversarial", FORENSIC: "Extreme-Return Forensic",
          PORTFOLIO: "Portfolio & Tail", EXECUTION: "Execution & Microstructure",
          DATA: "Data & Measurement Integrity", META: "Meta-Research & Architecture"}

DEFAULT_BUDGET_S = 300.0
#: Starting shares of the leg budget; re-weighted every pass by measured information per second.
BASE_SHARE = {SCIENTIFIC: 0.40, FORENSIC: 0.10, PORTFOLIO: 0.08, EXECUTION: 0.08, DATA: 0.24,
              META: 0.10}
SHARE_FLOOR = 0.02
RETIRE_AFTER_PASSES = 168          # a week of hourly passes at the floor
PER_SUBJECT_S = 30.0
MAX_SUBJECTS = {SCIENTIFIC: 3000, FORENSIC: 400, PORTFOLIO: 4, EXECUTION: 200, DATA: 40,
                META: 2}
#: A subject is re-examined on unchanged evidence once this old, so calibration keeps settling.
REMEASURE_H = 24.0
#: Stale-feed thresholds for the data committee (hours with no bar on a weekday-open market).
STALE_H = 72.0


def _now() -> str:
    return ce.now()


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[-limit:] if limit else lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ================================================================== seat registry
SEATS: list[ce.Specialist] = []


def seat(committee: str, partition: str, level: int, failure_class: str, cost_s: float, *,
         trap: Callable[[], Any] | None = None, clean: Callable[[], Any] | None = None,
         settles_by: str = "remeasure") -> Callable[[Callable[..., ce.Result]],
                                                     Callable[..., ce.Result]]:
    """Register `fn(sp, evidence, key) -> Result` as one specialist."""
    def deco(fn: Callable[..., ce.Result]) -> Callable[..., ce.Result]:
        holder: dict[str, ce.Specialist] = {}

        def check(part: Any, key: str) -> ce.Result:
            return fn(holder["sp"], part, key)

        sp = ce.Specialist(fn.__name__, committee, partition, level, failure_class, cost_s,
                           check, trap, clean, settles_by)
        holder["sp"] = sp
        SEATS.append(sp)
        return fn
    return deco


def seats_of(committee: str) -> list[ce.Specialist]:
    return [s for s in SEATS if s.committee == committee]


def _r(sp: ce.Specialist, verdict: str, strength: float = 0.0, test: str = "",
       **evidence: Any) -> ce.Result:
    return ce.result(sp, verdict, strength, evidence=evidence, test=test)


# ================================================================== synthetic fixtures (traps)
@dataclass(frozen=True)
class Sig:
    """The signal shape the falsifier battery and the lookahead sentinel read."""

    time: Any
    side: int
    stop: float
    target: float
    ttl_bars: int = 1


def _bars(n: int = 800, seed: int = 7, drift: float = 0.0, vol: float = 0.002) -> Any:
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, n)
    close = np.exp(np.cumsum(r))
    open_ = np.r_[1.0, close[:-1]]
    idx = pd.date_range("2026-01-05", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * (1 + vol / 4),
                         "low": np.minimum(open_, close) * (1 - vol / 4), "close": close},
                        index=idx)


def _oracle(df: Any, every: int = 4, flip_after: int | None = None) -> list[Sig]:
    """Signals that know the next bar: the edge a clean fixture needs, with no subtlety."""
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    out = []
    for i in range(0, len(df) - 3, every):
        side = 1 if c[i + 2] > o[i + 1] else -1
        if flip_after is not None and i >= flip_after:
            side = -side
        out.append(Sig(df.index[i], side, float(c[i]) * (1 - 0.01 * side),
                       float(c[i]) * (1 + 0.01 * side), 1))
    return out


def _cell(df: Any, sigs: list[Sig], cost: float, family: Any = None) -> dict[str, Any]:
    return {"df": df, "signals": sigs, "cost": cost, "family": family, "usd": None}


def _lucky_tail_cell() -> dict[str, Any]:
    """A slow bleed with ten spikes: the whole edge sits in the top decile."""
    import numpy as np
    import pandas as pd
    n = 600
    step = np.full(n, -0.0005)
    spikes = list(range(30, n - 5, 60))
    for j in spikes:
        step[j] = 0.06
    close = np.exp(np.cumsum(step))
    open_ = np.r_[1.0, close[:-1]]
    idx = pd.date_range("2026-01-05", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close),
                       "low": np.minimum(open_, close), "close": close}, index=idx)
    at = sorted(set(range(0, n - 3, 6)) | {j - 1 for j in spikes})
    return _cell(df, [Sig(idx[i], 1, float(close[i]) * 0.99, float(close[i]) * 1.01, 1)
                      for i in at], 0.0)


def _peeking_family(frame: Any, **_kw: Any) -> list[Sig]:
    """Sides from the WHOLE frame's mean, future included: truncation must change them."""
    c = frame["close"].to_numpy()
    m = float(c.mean())
    return [Sig(frame.index[i], 1 if c[i] < m else -1, 0.0, 0.0, 1)
            for i in range(len(c)) if i % 3 == 0]


def _causal_family(frame: Any, **_kw: Any) -> list[Sig]:
    c = frame["close"].to_numpy()
    return [Sig(frame.index[i], 1 if c[i] > c[i - 1] else -1, 0.0, 0.0, 1)
            for i in range(1, len(c)) if i % 3 == 0]


# ================================================================== 1. SCIENTIFIC ADVERSARIAL
# The bank the gauntlet sweeps, cell by cell. L0 reads the mechanism partition (text and
# provenance, free); L1..L4 read the cell the gauntlet itself would build and run the falsifier
# catalogue in cost order. Settled by the hypothesis graph's later fate.
_PUBLIC_MAX = ("maximum of", "max of", "no multiplicity", "best of", "cherry", "optimi")


@seat(SCIENTIFIC, "mechanism", 0, "NO_MECHANISM", 0.001, settles_by="fate",
      trap=lambda: {"note": "", "status": "UNNAMED"},
      clean=lambda: {"note": "overnight stops sit beyond the Asia range and are run at the "
                             "London open", "status": "NAMED"})
def mechanism_named(sp: ce.Specialist, ev: Mapping[str, Any], key: str) -> ce.Result:
    note = str(ev.get("note") or "")
    if len(note) < 20 or str(ev.get("status") or "NAMED").upper() in ("UNNAMED", "NONE"):
        return _r(sp, FAIL, 0.5, "placebo_battery", note_chars=len(note),
                  status=ev.get("status"))
    return _r(sp, PASS, 0.3, note_chars=len(note))


@seat(SCIENTIFIC, "mechanism", 0, "SELECTION_BIAS", 0.001, settles_by="fate",
      trap=lambda: {"note": "reported Sharpe 1.9 was the MAXIMUM of ~200 searched variations"},
      clean=lambda: {"note": "a carry premium paid for bearing crash risk in the funding leg"})
def search_maximum(sp: ce.Specialist, ev: Mapping[str, Any], key: str) -> ce.Result:
    note = str(ev.get("note") or "").lower()
    hit = [w for w in _PUBLIC_MAX if w in note]
    if hit:
        return _r(sp, FAIL, 0.6, "half_stability", markers=hit)
    return _r(sp, PASS, 0.2)


@seat(SCIENTIFIC, "mechanism", 0, "OVERFIT", 0.001, settles_by="fate",
      trap=lambda: {"params": {f"p{i}": i for i in range(9)}},
      clean=lambda: {"params": {"lookback": 20}})
def parameter_budget(sp: ce.Specialist, ev: Mapping[str, Any], key: str) -> ce.Result:
    k = len(ev.get("params") or {})
    if k >= 7:
        return _r(sp, FAIL, min(0.9, 0.4 + 0.07 * k), "truncation", n_params=k)
    return _r(sp, PASS, 0.3, n_params=k)


def _falsifier_seat(name: str, level: int, failure_class: str, cost: float,
                    trap: Callable[[], Any], clean: Callable[[], Any], nxt: str) -> None:
    def check(sp: ce.Specialist, cell: Mapping[str, Any], key: str) -> ce.Result:
        from libs.validation import falsifiers as fz
        if cell.get("cost") is None and name != "truncation":
            return _r(sp, UNMEASURED, 0.0, "cost_surface", why=cell.get("cost_basis")
                      or "the cell's round-trip cost could not be priced")
        out = dict(fz.FALSIFIERS[name](cell["df"], cell["signals"], float(cell["cost"] or 0.0),
                                       family=cell.get("family"), params={},
                                       usd=cell.get("usd")))
        v = str(out.get("verdict"))
        kept = {k: v2 for k, v2 in out.items() if k in ("n", "why", "net_by_cost",
                                                          "t_first_half", "t_second_half",
                                                          "top_decile_share_of_pnl",
                                                          "only_with_future", "redteam")}
        if v == FAIL:
            return _r(sp, FAIL, 0.9, nxt, **kept)
        if v == PASS:
            # A survivor is not settled by one falsifier: it climbs to the next, dearer one.
            return _r(sp, PASS, 0.5, nxt, **kept)
        return _r(sp, UNMEASURED, 0.0, nxt, **kept)
    check.__name__ = name
    seat(SCIENTIFIC, "cell", level, failure_class, cost, trap=trap, clean=clean,
         settles_by="fate")(check)


def _longs(df: Any, every: int) -> list[Sig]:
    """Blind longs on a driftless walk: no edge, which a cost or a placebo must expose."""
    return [Sig(t, 1, 0.0, 0.0, 1) for t in df.index[:-3:every]]


_falsifier_seat("cost_surface", 1, "COST_DEATH", 0.5,
                lambda: _cell(_bars(seed=11), _longs(_bars(seed=11), 5), 0.02),
                lambda: _cell(_bars(seed=12), _oracle(_bars(seed=12)), 0.0), "half_stability")
_falsifier_seat("tail_worst_decile", 1, "TAIL_FAILURE", 0.5, _lucky_tail_cell,
                lambda: _cell(_bars(seed=13), _oracle(_bars(seed=13)), 0.0), "half_stability")
_falsifier_seat("half_stability", 2, "STATE_FRAGILE", 1.0,
                lambda: _cell(_bars(seed=14), _oracle(_bars(seed=14), flip_after=400), 0.0),
                lambda: _cell(_bars(seed=15), _oracle(_bars(seed=15)), 0.0), "truncation")
_falsifier_seat("truncation", 3, "LEAKAGE", 2.0,
                lambda: _cell(_bars(seed=16), [], 0.0, _peeking_family),
                lambda: _cell(_bars(seed=17), [], 0.0, _causal_family), "placebo_battery")
_falsifier_seat("placebo_battery", 4, "LEAKAGE", 20.0,
                lambda: _cell(_bars(seed=18), _longs(_bars(seed=18), 4), 0.0),
                lambda: _cell(_bars(seed=19), _oracle(_bars(seed=19)), 0.0), "")


@seat(SCIENTIFIC, "cell", 2, "DRIFT_EXPLAINED", 0.2, settles_by="fate",
      trap=lambda: _cell(_bars(seed=31, drift=0.002), _longs(_bars(seed=31, drift=0.002), 4),
                         0.0),
      clean=lambda: _cell(_bars(seed=32), _oracle(_bars(seed=32)), 0.0))
def drift_explanation(sp: ce.Specialist, cell: Mapping[str, Any], key: str) -> ce.Result:
    """THE ALTERNATIVE EXPLAINER: would holding the instrument's own drift, on the signals'
    side mix and holding time, have earned most of the edge?"""
    import numpy as np

    from libs.validation.falsifiers import _trade_returns
    df, sigs = cell["df"], list(cell["signals"])
    r, _ = _trade_returns(df, sigs)
    if r.size < 20:
        return _r(sp, UNMEASURED, 0.0, "", n=int(r.size))
    bar = np.diff(np.log(df["close"].to_numpy(dtype=float)))
    side = float(np.mean([int(x.side) for x in sigs]))
    # The battery's trade runs from the next bar's open to the close `ttl` bars later.
    ttl = float(np.mean([max(1, int(x.ttl_bars)) for x in sigs])) + 1.0
    implied = side * float(np.nanmean(bar)) * ttl
    edge = float(r.mean())
    if edge > 0 and implied >= 0.7 * edge:
        return _r(sp, FAIL, 0.85 if implied >= edge else 0.6, "placebo_battery",
                  edge=round(edge, 8), drift_implied=round(implied, 8), net_side=round(side, 3))
    return _r(sp, PASS, 0.5, "placebo_battery", edge=round(edge, 8),
              drift_implied=round(implied, 8))


def survivor_subjects() -> list[ce.Subject]:
    """THE GAUNTLET'S OWN SURVIVORS, red-teamed after certification ("where did this leak").

    Each certificate becomes a Scientific subject on the cell the gauntlet built, entering at
    L1 (no mechanism text to screen) and climbing the whole battery while it survives. A FAIL
    here is a dated defect report beside the certificate; it withdraws nothing (L1.60)."""
    try:
        import falsifier_run as fr  # type: ignore[import-not-found]
        certs, _src = fr.load_certificates()
    except Exception:
        return []
    out = []
    for cid, c in sorted((certs or {}).items()):
        spec = (c or {}).get("shadow_spec") or {}
        sym, fam = str(spec.get("symbol") or ""), str(spec.get("family") or "")
        params: dict[str, Any] = spec["params"] if isinstance(spec.get("params"), dict) else {}
        if not (sym and fam):
            continue
        out.append(ce.Subject(
            SCIENTIFIC, f"survivor:{cid}",
            {"cell": ce.Lazy(_gauntlet_cell(sym, fam, params)),
             "certificate": {"id": cid, "spec": {"symbol": sym, "family": fam,
                                                 "params": params}}},
            keys={"symbol": sym, "cell": _node_id(sym, fam, params)}, level=1,
            claim=f"certified survivor {fam} on {sym} {json.dumps(params, sort_keys=True)}"))
    return out


def _gauntlet_cell(symbol: str, family: str, params: Mapping[str, Any]) -> Callable[[], Any]:
    def load() -> Any:
        import falsifier_run as fr
        build, meta = _builder_cache()
        inputs, why = fr.build_inputs({"shadow_spec": {"symbol": symbol, "family": family,
                                                       "params": dict(params)}}, meta, build)
        if inputs is None:
            raise LookupError(why)
        return inputs
    return load


_BUILD: dict[str, Any] = {}


def _builder_cache() -> tuple[Any, dict[str, Any]]:
    if "build" not in _BUILD:
        import falsifier_run as fr
        _BUILD["build"], _BUILD["meta"] = fr._builder(), dict(fr._meta() or {})
    return _BUILD["build"], _BUILD["meta"]


def _node_id(symbol: str, family: str, params: Mapping[str, Any]) -> str:
    try:
        from libs.research.hypothesis_graph import node_id
        return str(node_id(symbol, family, dict(params)))
    except Exception:
        return ""


#: (path, rows): the bank read once per pass, shared by the Scientific subjects and the Meta
#: census. A read cache, dropped by rebinding at the end of the pass; nothing on disk changes.
_BANK_CACHE: tuple[str, list[Any]] | None = None


def _bank_rows(bank: Path | None = None) -> list[Any] | None:
    global _BANK_CACHE
    path = str(bank or BANK)
    if _BANK_CACHE is None or _BANK_CACHE[0] != path:
        rows = _json(Path(path), None)
        if isinstance(rows, dict):
            rows = next((v for v in rows.values() if isinstance(v, list)), None)
        if not isinstance(rows, list):
            return None
        _BANK_CACHE = (path, rows)
    return _BANK_CACHE[1]


def _drop_bank_cache() -> None:
    global _BANK_CACHE
    _BANK_CACHE = None


def scientific_subjects(bank: Path | None = None) -> list[ce.Subject]:
    rows = _bank_rows(bank) or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        sym, fam = str(r.get("symbol") or ""), str(r.get("family") or "")
        params = r["params"] if isinstance(r.get("params"), dict) else {}
        key = str(r.get("genome_id") or ce.sha([sym, fam, params]))
        out.append(ce.Subject(
            SCIENTIFIC, key,
            {"mechanism": {"note": str(r.get("mechanism_note") or ""),
                           "status": r.get("mechanism_status"), "params": params,
                           "sources": r.get("n_independent_sources"),
                           "contested": r.get("contested")},
             "cell": ce.Lazy(_gauntlet_cell(sym, fam, params)) if sym and fam else None},
            keys={"symbol": sym, "cell": _node_id(sym, fam, params) if sym and fam else ""},
            claim=f"{fam} on {sym} {json.dumps(params, sort_keys=True)}"))
    return out


# ================================================================== 2. EXTREME-RETURN FORENSIC
# Public track records that look too good (MQL5 survivors) and the largest measured-but-unnamed
# effects in the naming queue. Every seat reads the record's own numbers; nothing is fetched.
def _growth(x: Any) -> float | None:
    if isinstance(x, str):
        x = x.replace("%", "").replace(",", "").strip()
    return _f(x)


_GOOD = {"growth_pct": 180.0, "weeks": 150.0, "pf": 1.6, "max_dd_pct": 18.0, "trades": 900.0,
         "win_pct": 58.0, "author_other_signals": [], "phenotypes": ["algo_survivor"]}


@seat(FORENSIC, "record", 0, "DATA_DEFECT", 0.001,
      trap=lambda: _GOOD | {"win_pct": 2296.0}, clean=lambda: dict(_GOOD))
def record_integrity(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    bad = []
    w, pf, wk, tr = (_f(r.get(k)) for k in ("win_pct", "pf", "weeks", "trades"))
    if w is not None and not 0.0 <= w <= 100.0:
        bad.append(f"win_pct={w}")
    if pf is not None and pf < 0:
        bad.append(f"pf={pf}")
    if wk is not None and wk <= 0:
        bad.append(f"weeks={wk}")
    if tr is not None and tr < 0:
        bad.append(f"trades={tr}")
    dd = _f(r.get("max_dd_pct"))
    if dd is not None and not 0.0 <= abs(dd) <= 100.0:
        bad.append(f"max_dd_pct={dd}")
    if bad:
        return _r(sp, FAIL, 0.95, "re-scrape the record and reconcile the parser", defects=bad)
    return _r(sp, PASS, 0.6)


@seat(FORENSIC, "record", 0, "LOW_SAMPLE", 0.001,
      trap=lambda: _GOOD | {"weeks": 9.0, "trades": 40.0}, clean=lambda: dict(_GOOD))
def record_sample(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    wk, tr = _f(r.get("weeks")), _f(r.get("trades"))
    if wk is None or tr is None:
        return _r(sp, UNMEASURED, 0.0, "", why="weeks or trades absent")
    if wk < 26 or tr < 100:
        return _r(sp, FAIL, 0.6 if (wk >= 13 and tr >= 50) else 0.85, "bootstrap_luck",
                  weeks=wk, trades=tr)
    return _r(sp, PASS, 0.5, weeks=wk, trades=tr)


@seat(FORENSIC, "record", 1, "MARTINGALE_GRID", 0.001,
      trap=lambda: _GOOD | {"win_pct": 93.0, "pf": 1.08, "max_dd_pct": 61.0},
      clean=lambda: dict(_GOOD))
def martingale_grid(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    w, pf, dd = _f(r.get("win_pct")), _f(r.get("pf")), _f(r.get("max_dd_pct"))
    tags = " ".join(str(p) for p in r.get("phenotypes") or []).lower()
    named = any(t in tags for t in ("martingale", "grid", "averaging"))
    if w is None or pf is None or not 0 <= w <= 100:
        return _r(sp, FAIL, 0.7, "trade-path reconstruction", phenotype=named) if named else \
            _r(sp, UNMEASURED, 0.0, "", why="win_pct/pf absent or invalid")
    # A martingale's signature: most trades win, the average loss dwarfs the average win.
    ratio = pf * (1 - w / 100) / (w / 100) if w > 0 else float("inf")
    if named or (w >= 80 and ratio < 0.35 and (dd is None or abs(dd) >= 30)):
        return _r(sp, FAIL, 0.85 if named or (dd is not None and abs(dd) >= 40) else 0.6,
                  "trade-path reconstruction", win_pct=w, pf=pf, avg_win_over_loss=round(
                      ratio, 3), max_dd_pct=dd, phenotype=named)
    return _r(sp, PASS, 0.5, win_pct=w, avg_win_over_loss=round(ratio, 3))


@seat(FORENSIC, "record", 1, "HIDDEN_LEVERAGE", 0.001,
      trap=lambda: _GOOD | {"growth_pct": 22000.0, "weeks": 60.0, "max_dd_pct": 6.0},
      clean=lambda: dict(_GOOD))
def hidden_leverage(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    g, wk, dd = _growth(r.get("growth_pct")), _f(r.get("weeks")), _f(r.get("max_dd_pct"))
    if g is None or wk is None or wk <= 0 or g <= -100:
        return _r(sp, UNMEASURED, 0.0, "", why="growth or weeks absent")
    cagr = (1 + g / 100) ** (52.0 / wk) - 1
    if dd is None or dd == 0:
        return _r(sp, UNMEASURED, 0.0, "equity-curve drawdown from the signal page",
                  cagr=round(cagr, 3), why="max drawdown unreported")
    mar = cagr / (abs(dd) / 100)
    if mar > 10:
        return _r(sp, FAIL, min(0.95, 0.5 + mar / 100), "trade-path reconstruction",
                  cagr=round(cagr, 3), max_dd_pct=dd, mar=round(mar, 2))
    return _r(sp, PASS, 0.5, cagr=round(cagr, 3), mar=round(mar, 2))


@seat(FORENSIC, "record", 1, "LUCK", 0.001,
      trap=lambda: _GOOD | {"win_pct": 52.0, "pf": 1.05, "trades": 120.0},
      clean=lambda: dict(_GOOD))
def bootstrap_luck(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    w, pf, n = _f(r.get("win_pct")), _f(r.get("pf")), _f(r.get("trades"))
    if w is None or pf is None or n is None or not 0 < w < 100 or n < 10 or pf <= 0:
        return _r(sp, UNMEASURED, 0.0, "", why="win_pct/pf/trades absent or invalid")
    p = w / 100
    payoff = pf * (1 - p) / p                 # average win / average loss
    p0 = 1 / (1 + payoff)                     # the breakeven hit rate at that payoff
    z = (p - p0) / math.sqrt(p0 * (1 - p0) / n)
    if z < 2.0:
        return _r(sp, FAIL, 0.9 if z < 1.0 else 0.6, "record_sample",
                  z=round(z, 2), breakeven_hit=round(p0, 4), hit=p, n=n)
    return _r(sp, PASS, min(0.9, z / 10), z=round(z, 2))


@seat(FORENSIC, "record", 2, "SELECTION_BIAS", 0.001,
      trap=lambda: _GOOD | {"growth_pct": 900.0, "author_other_signals": [
          {"growth": "3%"}, {"growth": "-40%"}, {"growth": "12%"}, {"growth": "-80%"}]},
      clean=lambda: dict(_GOOD))
def selection_bias(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    g = _growth(r.get("growth_pct"))
    raw = [_growth(s.get("growth")) for s in r.get("author_other_signals") or []
           if isinstance(s, dict)]
    sib: list[float] = [x for x in raw if x is not None]
    if g is None:
        return _r(sp, UNMEASURED, 0.0, "", why="growth absent")
    if len(sib) < 2:
        return _r(sp, PASS, 0.3, siblings=len(sib))
    sib.sort()
    med = sib[len(sib) // 2]
    losers = sum(1 for x in sib if x <= 0)
    if med < 0.2 * g or losers * 2 >= len(sib):
        return _r(sp, FAIL, 0.6 + 0.3 * min(1.0, len(sib) / 8), "bootstrap_luck",
                  siblings=len(sib), sibling_median_growth=med, losers=losers, growth=g)
    return _r(sp, PASS, 0.5, siblings=len(sib), sibling_median_growth=med)


@seat(FORENSIC, "record", 2, "INCONSISTENT_RECORD", 0.001,
      trap=lambda: _GOOD | {"growth_pct": 5000.0, "trades": 150.0, "pf": 1.1},
      clean=lambda: dict(_GOOD))
def return_decomposition(sp: ce.Specialist, r: Mapping[str, Any], key: str) -> ce.Result:
    """Growth must be reachable from the trades: per-trade compounding against the profit factor."""
    g, n, pf = _growth(r.get("growth_pct")), _f(r.get("trades")), _f(r.get("pf"))
    if g is None or n is None or pf is None or n < 1 or g <= -100:
        return _r(sp, UNMEASURED, 0.0, "", why="growth/trades/pf absent")
    per_trade = (1 + g / 100) ** (1 / n) - 1
    # With profit factor pf the mean trade is at most (pf-1)/(pf+1) of the mean absolute trade;
    # a per-trade mean above 2% at a pf under 1.3 needs position sizes no record discloses.
    if per_trade > 0.02 and pf < 1.3:
        return _r(sp, FAIL, 0.8, "deposit/withdrawal and leverage audit",
                  per_trade=round(per_trade, 5), pf=pf)
    return _r(sp, PASS, 0.4, per_trade=round(per_trade, 5))


_FORENSIC_EFFECTS = 4000


@seat(FORENSIC, "effect", 0, "SELECTION_BIAS", 0.001,
      trap=lambda: {"t_stat": 2.3, "n_oos": 2100, "family_size": 4000},
      clean=lambda: {"t_stat": 6.0, "n_oos": 5000, "family_size": 4000})
def effect_multiplicity(sp: ce.Specialist, e: Mapping[str, Any], key: str) -> ce.Result:
    t, m = _f(e.get("t_stat")), max(1, int(_f(e.get("family_size")) or 1))
    if t is None:
        return _r(sp, UNMEASURED, 0.0, "", why="t_stat absent")
    from statistics import NormalDist
    bar = NormalDist().inv_cdf(1 - 0.025 / m)     # Bonferroni over the queue it was mined from
    if abs(t) < bar:
        return _r(sp, FAIL, 0.9 if abs(t) < bar - 1 else 0.6, "effect_sample",
                  t=round(t, 2), bonferroni_bar=round(bar, 2), family_size=m)
    return _r(sp, PASS, 0.7, t=round(t, 2), bonferroni_bar=round(bar, 2))


@seat(FORENSIC, "effect", 1, "LOW_SAMPLE", 0.001,
      trap=lambda: {"n_oos": 120}, clean=lambda: {"n_oos": 5000})
def effect_sample(sp: ce.Specialist, e: Mapping[str, Any], key: str) -> ce.Result:
    n = _f(e.get("n_oos"))
    if n is None:
        return _r(sp, UNMEASURED, 0.0, "", why="n_oos absent")
    if n < 500:
        return _r(sp, FAIL, 0.8 if n < 200 else 0.5, "a second out-of-sample window", n_oos=n)
    return _r(sp, PASS, 0.5, n_oos=n)


def forensic_subjects(mql5: Path | None = None, queue: Path | None = None) -> list[ce.Subject]:
    out: list[ce.Subject] = []
    d = mql5 or MQL5
    files = sorted(d.glob("discoveries_*.json"), reverse=True)[:6] if d.is_dir() else []
    seen: set[str] = set()
    for f in files:
        doc = _json(f, [])
        rows = doc.get("discoveries") if isinstance(doc, dict) else doc
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or not r.get("url") or r["url"] in seen:
                continue
            seen.add(str(r["url"]))
            syms = [str(s) for s in r.get("symbols") or [] if s]
            rec = {k: r.get(k) for k in ("growth_pct", "weeks", "pf", "max_dd_pct", "trades",
                                         "win_pct", "author_other_signals", "phenotypes",
                                         "hour_histogram")}
            out.append(ce.Subject(FORENSIC, str(r["url"]), {"record": rec},
                                  keys={"symbol": syms[0] if syms else ""},
                                  claim=f"public track record {r['url']}"))
    effects = _json(queue or NAMING_QUEUE, [])
    if isinstance(effects, list):
        m = len(effects) or 1
        for e in sorted((e for e in effects if isinstance(e, dict)),
                        key=lambda e: -abs(_f(e.get("t_stat")) or 0.0))[:_FORENSIC_EFFECTS]:
            key = "effect:" + ce.sha({k: e.get(k) for k in ("symbol", "feature", "band",
                                                              "horizon", "side")})
            out.append(ce.Subject(FORENSIC, key,
                                  {"effect": {"t_stat": e.get("t_stat"), "n_oos": e.get("n_oos"),
                                              "family_size": m}},
                                  keys={"symbol": str(e.get("symbol") or "")},
                                  claim=f"{e.get('feature')} {e.get('band')} on "
                                        f"{e.get('symbol')}"))
    return out


# ================================================================== 3. PORTFOLIO & TAIL
# The live book (live_ledger.jsonl, live account rows) and the forward shadow book, day by
# sleeve in R. One subject per book; its fingerprint moves with every new day.
def _matrix(days: Mapping[str, Mapping[str, float]], min_days: int = 20
            ) -> tuple[list[str], Any]:
    import numpy as np
    sleeves = sorted(s for s, d in days.items() if len(d) >= min_days)
    all_days = sorted({d for s in sleeves for d in days[s]})
    if len(sleeves) < 2 or len(all_days) < min_days:
        return sleeves, None
    m = np.array([[days[s].get(d, 0.0) for s in sleeves] for d in all_days], dtype=float)
    return sleeves, m


def _book(n_days: int = 160, n_sleeves: int = 6, common: float = 0.0, seed: int = 3,
          tail_common: bool = False) -> dict[str, dict[str, float]]:
    import numpy as np
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 1, n_days)
    out: dict[str, dict[str, float]] = {}
    for j in range(n_sleeves):
        x = common * f + math.sqrt(max(0.0, 1 - common ** 2)) * rng.normal(0.05, 1, n_days)
        if tail_common:
            x = np.where(f < np.quantile(f, 0.1), -3.0 + 0.1 * rng.normal(0, 1, n_days), x)
        out[f"s{j}"] = {f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}": float(v)
                        for i, v in enumerate(x)}
    return out


@seat(PORTFOLIO, "daily_r", 0, "CONCENTRATION", 0.05,
      trap=lambda: _book(common=0.95), clean=lambda: _book(common=0.0))
def effective_rank(sp: ce.Specialist, days: Mapping[str, Mapping[str, float]], key: str
                   ) -> ce.Result:
    import numpy as np
    sleeves, m = _matrix(days)
    if m is None:
        return _r(sp, UNMEASURED, 0.0, "more forward days per sleeve", sleeves=len(sleeves))
    c = np.corrcoef(m, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    ev = np.clip(np.linalg.eigvalsh(c), 0, None)
    n_eff = float(ev.sum() ** 2 / (ev ** 2).sum()) if ev.sum() > 0 else 0.0
    share = n_eff / len(sleeves)
    if share < 0.35:
        return _r(sp, FAIL, 0.85 if share < 0.2 else 0.6, "tail_dependence",
                  n_eff=round(n_eff, 2), sleeves=len(sleeves))
    return _r(sp, PASS, 0.6, n_eff=round(n_eff, 2), sleeves=len(sleeves))


@seat(PORTFOLIO, "daily_r", 1, "TAIL_DEPENDENCE", 0.05,
      trap=lambda: _book(tail_common=True), clean=lambda: _book())
def tail_dependence(sp: ce.Specialist, days: Mapping[str, Mapping[str, float]], key: str
                    ) -> ce.Result:
    import numpy as np
    sleeves, m = _matrix(days)
    if m is None:
        return _r(sp, UNMEASURED, 0.0, "more forward days per sleeve", sleeves=len(sleeves))
    book = m.sum(axis=1)
    worst = book <= np.quantile(book, 0.1)
    losing = (m < 0).mean(axis=1)
    tail, normal = float(losing[worst].mean()), float(losing[~worst].mean())
    lift = tail / normal if normal > 0 else float("inf")
    if lift > 1.8 and tail > 0.8:
        return _r(sp, FAIL, 0.85 if tail > 0.9 else 0.6, "regime_correlation",
                  co_loss_in_tail=round(tail, 3), co_loss_normal=round(normal, 3))
    return _r(sp, PASS, 0.6, co_loss_in_tail=round(tail, 3), co_loss_normal=round(normal, 3))


def _crash_book() -> dict[str, dict[str, float]]:
    """An ordinary book with one day on which every sleeve lost ten R."""
    b = _book()
    day = sorted(next(iter(b.values())))[80]
    return {k: v | {day: -10.0} for k, v in b.items()}


@seat(PORTFOLIO, "daily_r", 1, "TAIL_FAILURE", 0.05, trap=_crash_book, clean=lambda: _book())
def stress_worst_day(sp: ce.Specialist, days: Mapping[str, Mapping[str, float]], key: str
                     ) -> ce.Result:
    sleeves, m = _matrix(days)
    if m is None:
        return _r(sp, UNMEASURED, 0.0, "more forward days per sleeve", sleeves=len(sleeves))
    book = m.sum(axis=1)
    sd = float(book.std(ddof=1)) or 1e-9
    worst = float(book.min())
    z = -worst / sd
    if z > 4.0:
        return _r(sp, FAIL, 0.85 if z > 5.5 else 0.6, "ruin_simulation",
                  worst_day_r=round(worst, 3), worst_in_sd=round(z, 2))
    return _r(sp, PASS, 0.6, worst_day_r=round(worst, 3), worst_in_sd=round(z, 2))


#: Ruin in R units: the book loses RUIN_R of its per-trade risk units inside a year.
RUIN_R = 40.0


@seat(PORTFOLIO, "daily_r", 2, "RUIN", 0.5,
      trap=lambda: {k: {d: v - 0.3 for d, v in s.items()} for k, s in _book(common=0.8).items()},
      clean=lambda: {k: {d: v + 0.3 for d, v in s.items()} for k, s in _book().items()})
def ruin_simulation(sp: ce.Specialist, days: Mapping[str, Mapping[str, float]], key: str
                    ) -> ce.Result:
    import numpy as np
    sleeves, m = _matrix(days)
    if m is None:
        return _r(sp, UNMEASURED, 0.0, "more forward days per sleeve", sleeves=len(sleeves))
    book = m.sum(axis=1)
    rng = np.random.default_rng(0)
    n, block, horizon, paths = len(book), 5, 250, 400
    hits = 0
    for _ in range(paths):
        idx = np.concatenate([np.arange(s, s + block) % n
                              for s in rng.integers(0, n, horizon // block + 1)])[:horizon]
        eq = np.cumsum(book[idx])
        if float((np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq).max()) >= RUIN_R:
            hits += 1
    p = hits / paths
    if p > 0.05:
        return _r(sp, FAIL, 0.9 if p > 0.25 else 0.6, "regime_correlation",
                  p_drawdown_ge_ruin_r=round(p, 4), ruin_r=RUIN_R)
    return _r(sp, PASS, 0.7, p_drawdown_ge_ruin_r=round(p, 4), ruin_r=RUIN_R)


@seat(PORTFOLIO, "daily_r", 2, "CORRELATION_BREAKDOWN", 0.05,
      trap=lambda: _book(tail_common=True), clean=lambda: _book())
def regime_correlation(sp: ce.Specialist, days: Mapping[str, Mapping[str, float]], key: str
                       ) -> ce.Result:
    import numpy as np
    sleeves, m = _matrix(days)
    if m is None:
        return _r(sp, UNMEASURED, 0.0, "more forward days per sleeve", sleeves=len(sleeves))
    stress = np.abs(m.sum(axis=1))
    hi = stress >= np.quantile(stress, 0.8)

    def mean_corr(x: Any) -> float:
        if len(x) < 5:
            return float("nan")
        c = np.nan_to_num(np.corrcoef(x, rowvar=False), nan=0.0)
        k = c.shape[0]
        return float((c.sum() - k) / (k * (k - 1)))
    a, b = mean_corr(m[hi]), mean_corr(m[~hi])
    if not (math.isfinite(a) and math.isfinite(b)):
        return _r(sp, UNMEASURED, 0.0, "", why="too few stress days")
    if a - b > 0.3:
        return _r(sp, FAIL, 0.8 if a - b > 0.5 else 0.6, "",
                  corr_stress=round(a, 3), corr_calm=round(b, 3))
    return _r(sp, PASS, 0.6, corr_stress=round(a, 3), corr_calm=round(b, 3))


@seat(PORTFOLIO, "exposure", 0, "CONCENTRATION", 0.01,
      trap=lambda: {"EURUSD": 90.0, "GBPUSD": 5.0, "XAUUSD": 5.0},
      clean=lambda: {"EURUSD": 20.0, "GBPUSD": 20.0, "XAUUSD": 20.0, "USDJPY": 20.0,
                     "US500": 20.0})
def symbol_concentration(sp: ce.Specialist, gross: Mapping[str, float], key: str) -> ce.Result:
    tot = sum(abs(v) for v in gross.values())
    if tot <= 0 or len(gross) < 2:
        return _r(sp, UNMEASURED, 0.0, "", why="no gross exposure recorded")
    shares = sorted(((abs(v) / tot, k) for k, v in gross.items()), reverse=True)
    hhi = sum(s * s for s, _ in shares)
    if shares[0][0] > 0.5:
        return _r(sp, FAIL, 0.7, "effective_rank", top=shares[0][1],
                  top_share=round(shares[0][0], 3), hhi=round(hhi, 3))
    return _r(sp, PASS, 0.6, top=shares[0][1], top_share=round(shares[0][0], 3),
              hhi=round(hhi, 3))


@seat(PORTFOLIO, "capacity", 1, "CAPACITY", 0.01,
      trap=lambda: {"sleeves": {"a": {"utilisation": 1.4}}},
      clean=lambda: {"sleeves": {"a": {"utilisation": 0.2}}})
def capacity(sp: ce.Specialist, doc: Mapping[str, Any], key: str) -> ce.Result:
    rows = doc.get("sleeves")
    util: dict[str, float] = {}
    for k, v in (rows.items() if isinstance(rows, dict) else ()):
        u = _f(v.get("utilisation")) if isinstance(v, dict) else None
        if u is not None:
            util[str(k)] = u
    if not util:
        return _r(sp, UNMEASURED, 0.0, "publish per-sleeve utilisation in CAPACITY.json")
    over = sorted(k for k, v in util.items() if v > 1.0)
    if over:
        return _r(sp, FAIL, 0.8, "", over_capacity=over[:20])
    return _r(sp, PASS, 0.6, max_utilisation=round(max(util.values()), 3))


def _live_rows() -> list[dict[str, Any]]:
    return [r for r in _jsonl(LIVE_LEDGER) if str(r.get("account_kind") or "live") == "live"]


def portfolio_subjects() -> list[ce.Subject]:
    live = _live_rows()
    by: dict[str, dict[str, float]] = {}
    gross: dict[str, float] = {}
    for r in live:
        s, d, rm = str(r.get("sleeve") or ""), str(r.get("time") or "")[:10], _f(
            r.get("r_multiple"))
        if s and d and rm is not None:
            by.setdefault(s, {})[d] = by.setdefault(s, {}).get(d, 0.0) + rm
        pl = _f(r.get("pl_quote"))
        if pl is not None:
            gross[str(r.get("symbol") or "?")] = gross.get(str(r.get("symbol") or "?"), 0.0) + \
                abs(pl)
    try:
        import portfolio_evidence as pe  # type: ignore[import-not-found]
        forward = pe.daily_series()
    except Exception:
        forward = {}
    cap = _json(CAPACITY, None)
    out = [ce.Subject(PORTFOLIO, "book:live",
                      {"daily_r": by or None, "exposure": gross or None,
                       "capacity": cap if isinstance(cap, dict) else None},
                      keys={"book": "live"}, claim="the live book")]
    out.append(ce.Subject(PORTFOLIO, "book:forward", {"daily_r": forward or None},
                          keys={"book": "forward"}, claim="the forward shadow book"))
    return out


# ================================================================== 4. EXECUTION & MICROSTRUCTURE
_TRADES_OK = [{"pl_quote": 10.0, "commission": -0.5, "swap": 0.0, "entry_price": 1.0,
               "sl": 0.99, "tp": 1.02, "fill_price": 1.02, "r_unreconstructible": False}] * 30
_TRADES_COSTLY = [{"pl_quote": 1.0, "commission": -1.5, "swap": -0.4, "entry_price": 1.0,
                   "sl": 0.99, "tp": 1.02, "fill_price": 1.0001, "r_unreconstructible": False}] * 30
_TRADES_SLIPPED = [{"pl_quote": -12.0, "commission": -0.5, "swap": 0.0, "entry_price": 1.0,
                    "sl": 0.99, "tp": 1.02, "fill_price": 0.9875,
                    "r_unreconstructible": False}] * 30


@seat(EXECUTION, "trades", 0, "COST_DEATH", 0.005, trap=lambda: _TRADES_COSTLY,
      clean=lambda: _TRADES_OK)
def cost_drag(sp: ce.Specialist, rows: Sequence[Mapping[str, Any]], key: str) -> ce.Result:
    gross = sum(_f(r.get("pl_quote")) or 0.0 for r in rows)
    costs = sum((_f(r.get("commission")) or 0.0) + (_f(r.get("swap")) or 0.0) for r in rows)
    if len(rows) < 10:
        return _r(sp, UNMEASURED, 0.0, "more closed trades", n=len(rows))
    if gross > 0 and gross + costs <= 0:
        return _r(sp, FAIL, 0.9, "exit_slippage", gross=round(gross, 2), costs=round(costs, 2),
                  n=len(rows))
    if gross > 0 and -costs > 0.5 * gross:
        return _r(sp, FAIL, 0.6, "exit_slippage", gross=round(gross, 2), costs=round(costs, 2),
                  n=len(rows))
    return _r(sp, PASS, 0.6, gross=round(gross, 2), costs=round(costs, 2), n=len(rows))


@seat(EXECUTION, "trades", 0, "SWAP_DRAG", 0.005,
      trap=lambda: [r | {"swap": -3.0} for r in _TRADES_OK], clean=lambda: _TRADES_OK)
def swap_surface(sp: ce.Specialist, rows: Sequence[Mapping[str, Any]], key: str) -> ce.Result:
    gross = sum(_f(r.get("pl_quote")) or 0.0 for r in rows)
    swap = sum(_f(r.get("swap")) or 0.0 for r in rows)
    if len(rows) < 10:
        return _r(sp, UNMEASURED, 0.0, "more closed trades", n=len(rows))
    if gross > 0 and -swap > 0.2 * gross:
        return _r(sp, FAIL, 0.8 if -swap > 0.5 * gross else 0.6, "cost_drag",
                  swap=round(swap, 2), gross=round(gross, 2))
    return _r(sp, PASS, 0.6, swap=round(swap, 2))


def _stop_slip_r(r: Mapping[str, Any]) -> float | None:
    e, sl, fill = _f(r.get("entry_price")), _f(r.get("sl")), _f(r.get("fill_price"))
    tp = _f(r.get("tp"))
    if e is None or sl is None or fill is None or sl == e:
        return None
    risk = abs(e - sl)
    long = sl < e
    if tp is not None and abs(fill - tp) < abs(fill - sl):
        return None                             # a target exit, not a stop
    adverse = (sl - fill) if long else (fill - sl)
    return adverse / risk


@seat(EXECUTION, "trades", 1, "SLIPPAGE", 0.005, trap=lambda: _TRADES_SLIPPED,
      clean=lambda: [r | {"fill_price": 0.99, "pl_quote": -10.0} for r in _TRADES_OK])
def exit_slippage(sp: ce.Specialist, rows: Sequence[Mapping[str, Any]], key: str) -> ce.Result:
    slips = [s for s in (_stop_slip_r(r) for r in rows) if s is not None]
    if len(slips) < 5:
        return _r(sp, UNMEASURED, 0.0, "more stop exits", stop_exits=len(slips))
    mean = sum(slips) / len(slips)
    if mean > 0.1:
        return _r(sp, FAIL, 0.85 if mean > 0.2 else 0.6, "markout",
                  mean_stop_slip_r=round(mean, 4), stop_exits=len(slips))
    return _r(sp, PASS, 0.6, mean_stop_slip_r=round(mean, 4), stop_exits=len(slips))


@seat(EXECUTION, "trades", 1, "MEASUREMENT_GAP", 0.005,
      trap=lambda: [r | {"r_unreconstructible": True} for r in _TRADES_OK],
      clean=lambda: _TRADES_OK)
def r_reconstruction(sp: ce.Specialist, rows: Sequence[Mapping[str, Any]], key: str
                     ) -> ce.Result:
    if not rows:
        return _r(sp, UNMEASURED, 0.0, "", n=0)
    bad = sum(1 for r in rows if r.get("r_unreconstructible"))
    share = bad / len(rows)
    if share > 0.2:
        return _r(sp, FAIL, 0.8, "record the entry stop at send time", share=round(share, 3))
    return _r(sp, PASS, 0.6, share=round(share, 3))


@seat(EXECUTION, "markout", 0, "FILL_FAILURE", 0.001,
      trap=lambda: {"usable": True, "n_matched": 10, "n_unfilled_intents": 30, "mean_slip_r": 0.0},
      clean=lambda: {"usable": True, "n_matched": 90, "n_unfilled_intents": 2,
                     "mean_slip_r": 0.01, "edge_share": 0.05})
def fill_rate(sp: ce.Specialist, m: Mapping[str, Any], key: str) -> ce.Result:
    matched, unfilled = _f(m.get("n_matched")) or 0.0, _f(m.get("n_unfilled_intents")) or 0.0
    if matched + unfilled == 0:
        return _r(sp, UNMEASURED, 0.0, "record intents and join them to deals",
                  why=m.get("why"))
    miss = unfilled / (matched + unfilled)
    if miss > 0.3:
        return _r(sp, FAIL, 0.85 if matched == 0 else 0.6, "join intents to deals by ticket",
                  unfilled_share=round(miss, 3), matched=matched, unfilled=unfilled)
    return _r(sp, PASS, 0.6, unfilled_share=round(miss, 3))


@seat(EXECUTION, "markout", 1, "ADVERSE_SELECTION", 0.001,
      trap=lambda: {"usable": True, "n_matched": 50, "mean_slip_r": 0.25, "edge_share": 0.7},
      clean=lambda: {"usable": True, "n_matched": 50, "mean_slip_r": 0.01, "edge_share": 0.05})
def markout(sp: ce.Specialist, m: Mapping[str, Any], key: str) -> ce.Result:
    if not m.get("usable"):
        return _r(sp, UNMEASURED, 0.0, "record intents and join them to deals", why=m.get("why"))
    slip, share = _f(m.get("mean_slip_r")), _f(m.get("edge_share"))
    if (share is not None and share > 0.5) or (slip is not None and slip > 0.15):
        return _r(sp, FAIL, 0.8, "latency", mean_slip_r=slip, edge_share=share)
    return _r(sp, PASS, 0.6, mean_slip_r=slip, edge_share=share)


@seat(EXECUTION, "quality", 2, "LATENCY", 0.001,
      trap=lambda: {"latency_ms_p95": 2500}, clean=lambda: {"latency_ms_p95": 120})
def latency(sp: ce.Specialist, q: Mapping[str, Any], key: str) -> ce.Result:
    v = next((_f(q.get(k)) for k in ("latency_ms_p95", "send_to_fill_ms_p95", "latency_ms")
              if _f(q.get(k)) is not None), None)
    if v is None:
        return _r(sp, UNMEASURED, 0.0, "stamp order-send and fill times in the gateway",
                  why="no latency field in execution_quality.json")
    if v > 1000:
        return _r(sp, FAIL, 0.7, "", latency_ms_p95=v)
    return _r(sp, PASS, 0.6, latency_ms_p95=v)


def execution_subjects() -> list[ce.Subject]:
    live = _live_rows()
    by: dict[str, list[dict[str, Any]]] = {}
    for r in live:
        by.setdefault(str(r.get("sleeve") or "?"), []).append(r)
    q = _json(EXEC_QUALITY, None)
    m = _json(MARKOUT, None)
    out = [ce.Subject(EXECUTION, "desk", {"trades": live or None,
                                          "markout": m if isinstance(m, dict) else None,
                                          "quality": q if isinstance(q, dict) else None},
                      keys={"book": "live"}, claim="the live desk's execution")]
    for s, rows in sorted(by.items()):
        sym = str(rows[-1].get("symbol") or "")
        out.append(ce.Subject(EXECUTION, f"sleeve:{s}", {"trades": rows},
                              keys={"symbol": sym, "sleeve": s},
                              claim=f"execution of {s} on {sym}"))
    return out


# ================================================================== 5. DATA & MEASUREMENT INTEGRITY
def _clean_frame() -> Any:
    return _bars(n=24 * 60, seed=21)


def _dup_frame() -> Any:
    import pandas as pd
    df = _clean_frame()
    return pd.concat([df.iloc[:300], df.iloc[250:]])


def _bad_ohlc() -> Any:
    df = _clean_frame().copy()
    df.iloc[100:130, df.columns.get_loc("high")] = df["low"].iloc[100:130] * 0.99
    return df


def _gappy() -> Any:
    import numpy as np
    df = _clean_frame()
    return df[np.random.default_rng(5).random(len(df)) > 0.3]


def _spiky() -> Any:
    df = _clean_frame().copy()
    for i in range(50, 1400, 97):
        df.iloc[i, df.columns.get_loc("close")] *= 1.3
    return df


def _flat() -> Any:
    df = _clean_frame().copy()
    df.iloc[400:520, df.columns.get_loc("close")] = float(df["close"].iloc[400])
    return df


@seat(DATA, "bars", 0, "TIMESTAMP_DEFECT", 0.01, trap=_dup_frame, clean=_clean_frame)
def timestamps(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    idx = df.index
    dups = int(idx.duplicated().sum())
    back = int((idx[1:] < idx[:-1]).sum()) if len(idx) > 1 else 0
    if dups or back:
        return _r(sp, FAIL, 0.95, "re-pull the symbol's history", duplicates=dups,
                  backwards=back)
    return _r(sp, PASS, 0.8, bars=len(idx))


@seat(DATA, "bars", 0, "OHLC_DEFECT", 0.01, trap=_bad_ohlc, clean=_clean_frame)
def ohlc_consistency(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    need = {"open", "high", "low", "close"}
    if not need <= set(df.columns):
        return _r(sp, UNMEASURED, 0.0, "", why=f"columns {sorted(df.columns)[:8]}")
    o, h, lo, c = (df[k].astype(float) for k in ("open", "high", "low", "close"))
    bad = int(((h + 1e-12 < o.combine(c, max)) | (lo - 1e-12 > o.combine(c, min))).sum())
    nonpos = int(((o <= 0) | (c <= 0) | (lo <= 0)).sum())
    share = (bad + nonpos) / max(1, len(df))
    if share > 0.001:
        return _r(sp, FAIL, 0.9 if share > 0.01 else 0.6, "re-pull the symbol's history",
                  inconsistent=bad, non_positive=nonpos)
    return _r(sp, PASS, 0.8, inconsistent=bad, non_positive=nonpos)


def _hours(df: Any) -> Any:
    import pandas as pd
    idx = pd.DatetimeIndex(df.index)
    return (idx[1:] - idx[:-1]).total_seconds() / 3600.0


@seat(DATA, "bars", 1, "MISSINGNESS", 0.02, trap=_gappy, clean=_clean_frame)
def gaps(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    if len(df) < 50:
        return _r(sp, UNMEASURED, 0.0, "", bars=len(df))
    d = _hours(df)
    step = float(sorted(d)[len(d) // 2]) or 1.0
    # A weekend is 48-72h and a holiday one more day; anything longer inside a week is a hole.
    holes = int(((d > step * 1.5) & (d < 40)).sum())
    share = holes / len(d)
    if share > 0.05:
        return _r(sp, FAIL, 0.8 if share > 0.2 else 0.6, "cross_tf_reconciliation",
                  intraweek_holes=holes, share=round(share, 4), step_h=step)
    return _r(sp, PASS, 0.6, intraweek_holes=holes, step_h=step)


@seat(DATA, "bars", 1, "ANOMALY", 0.02, trap=_spiky, clean=_clean_frame)
def outliers(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    import numpy as np
    c = df["close"].astype(float).to_numpy()
    if len(c) < 50 or (c <= 0).any():
        return _r(sp, UNMEASURED, 0.0, "", bars=len(c))
    r = np.diff(np.log(c))
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med))) or 1e-12
    # A spike and its reversal: two consecutive extreme moves of opposite sign.
    z = (r - med) / (1.4826 * mad)
    rev = int(((np.abs(z[:-1]) > 15) & (np.abs(z[1:]) > 15) & (np.sign(z[:-1]) != np.sign(
        z[1:]))).sum())
    if rev >= 3:
        return _r(sp, FAIL, 0.85, "cross_tf_reconciliation", spike_reversals=rev)
    return _r(sp, PASS, 0.6, spike_reversals=rev)


@seat(DATA, "bars", 1, "STALE_FEED", 0.02, trap=_flat, clean=_clean_frame)
def flat_runs(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    c = df["close"].astype(float).to_numpy()
    if len(c) < 50:
        return _r(sp, UNMEASURED, 0.0, "", bars=len(c))
    run = longest = 0
    for i in range(1, len(c)):
        run = run + 1 if c[i] == c[i - 1] else 0
        longest = max(longest, run)
    if longest >= 48:
        return _r(sp, FAIL, 0.8, "re-pull the symbol's history", longest_flat_run=longest)
    return _r(sp, PASS, 0.6, longest_flat_run=longest)


def _daily_in_disguise() -> Any:
    import pandas as pd
    return _bars(n=400, seed=22).set_axis(pd.date_range("2024-01-01", periods=400, freq="D",
                                                        tz="UTC"))


@seat(DATA, "bars", 2, "FREQUENCY_DEFECT", 0.02, trap=_daily_in_disguise, clean=_clean_frame)
def bar_density(sp: ce.Specialist, df: Any, key: str) -> ce.Result:
    """An H1 file that is daily bars in disguise: the median step says what the file holds."""
    if len(df) < 50:
        return _r(sp, UNMEASURED, 0.0, "", bars=len(df))
    step = float(sorted(_hours(df))[len(df) // 2])
    declared = str(key).rsplit("_", 1)[-1].upper()
    want = {"M1": 1 / 60, "M5": 5 / 60, "M15": 0.25, "M30": 0.5, "H1": 1.0, "H4": 4.0,
            "D1": 24.0}.get(declared, 1.0)
    if step > want * 3:
        return _r(sp, FAIL, 0.9, "re-pull at the declared timeframe", median_step_h=step,
                  declared=declared)
    return _r(sp, PASS, 0.7, median_step_h=step, declared=declared)


@seat(DATA, "tail", 0, "STALE_DATA", 0.001,
      trap=lambda: {"last_bar_age_h": 500.0, "weekday_market": True},
      clean=lambda: {"last_bar_age_h": 2.0, "weekday_market": True})
def staleness(sp: ce.Specialist, t: Mapping[str, Any], key: str) -> ce.Result:
    age = _f(t.get("last_bar_age_h"))
    if age is None:
        return _r(sp, UNMEASURED, 0.0, "", why="no last bar time")
    if age > STALE_H:
        return _r(sp, FAIL, 0.8 if age > 3 * STALE_H else 0.6, "refresh_bars",
                  last_bar_age_h=round(age, 1))
    return _r(sp, PASS, 0.7, last_bar_age_h=round(age, 1))


@seat(DATA, "pair", 2, "RECONCILIATION", 0.05,
      trap=lambda: (_clean_frame(), _bars(n=24 * 60 * 4, seed=99, vol=0.001)),
      clean=lambda: (lambda h: (h, _to_m15(h)))(_clean_frame()))
def cross_tf_reconciliation(sp: ce.Specialist, pair: Any, key: str) -> ce.Result:
    """The M15 file resampled to H1 must close where the H1 file closes."""
    h1, m15 = pair
    rs = m15["close"].resample("1h", label="left", closed="left").last().dropna()
    j = h1["close"].astype(float).to_frame("h1").join(rs.to_frame("m15"), how="inner")
    if len(j) < 50:
        return _r(sp, UNMEASURED, 0.0, "", overlap=len(j))
    rel = ((j["h1"] - j["m15"]).abs() / j["h1"].abs()).to_numpy()
    share = float((rel > 1e-3).mean())
    if share > 0.05:
        return _r(sp, FAIL, 0.85 if share > 0.2 else 0.6, "re-pull both timeframes",
                  mismatch_share=round(share, 4), overlap=len(j))
    return _r(sp, PASS, 0.7, mismatch_share=round(share, 4), overlap=len(j))


def _to_m15(h1: Any) -> Any:
    """A consistent M15 file for an H1 file (the clean twin of the reconciliation trap)."""
    import pandas as pd
    idx = pd.date_range(h1.index[0], periods=len(h1) * 4, freq="15min", tz="UTC")
    return pd.DataFrame({"close": h1["close"].reindex(idx.floor("h")).to_numpy()}, index=idx)


@seat(DATA, "registry", 0, "SURVIVORSHIP", 0.01,
      trap=lambda: {"registered": ["A", "B", "C", "D"], "on_disk": ["A"]},
      clean=lambda: {"registered": ["A", "B"], "on_disk": ["A", "B"]})
def survivorship(sp: ce.Specialist, reg: Mapping[str, Any], key: str) -> ce.Result:
    r, d = set(reg.get("registered") or []), set(reg.get("on_disk") or [])
    if not r:
        return _r(sp, UNMEASURED, 0.0, "", why="empty registry")
    missing = sorted(r - d)
    share = len(missing) / len(r)
    if share > 0.25:
        return _r(sp, FAIL, 0.7, "deepen_bars", registered=len(r), without_bars=len(missing),
                  sample=missing[:15])
    return _r(sp, PASS, 0.6, registered=len(r), without_bars=len(missing))


@seat(DATA, "pit", 1, "POINT_IN_TIME", 0.001,
      trap=lambda: {"violations": 12, "checked": 100}, clean=lambda: {"violations": 0,
                                                                     "checked": 100})
def point_in_time(sp: ce.Specialist, p: Mapping[str, Any], key: str) -> ce.Result:
    v = next((_f(p.get(k)) for k in ("violations", "n_violations", "lookahead_rows")
              if _f(p.get(k)) is not None), None)
    n = next((_f(p.get(k)) for k in ("checked", "n_checked", "rows") if _f(p.get(k))), None)
    if v is None:
        return _r(sp, UNMEASURED, 0.0, "publish violations/checked in PIT_AUDIT.json")
    if v > 0:
        return _r(sp, FAIL, 0.85, "restate the series as filed", violations=v, checked=n)
    return _r(sp, PASS, 0.7, violations=0, checked=n)


def _both(a: ce.Lazy, b: ce.Lazy) -> Callable[[], tuple[Any, Any]]:
    return lambda: (a.get(), b.get())


def data_subjects(universe_dir: Path | None = None, now: datetime | None = None
                  ) -> list[ce.Subject]:
    d = universe_dir or UNIVERSE_DIR
    now = now or datetime.now(tz=UTC)
    out: list[ce.Subject] = []
    files = sorted(d.glob("*_*.parquet")) if d.is_dir() else []
    on_disk = sorted({f.stem.rsplit("_", 1)[0] for f in files})

    def loader(path: Path) -> Callable[[], Any]:
        def load() -> Any:
            import pandas as pd
            df = pd.read_parquet(path)
            if not isinstance(df.index, pd.DatetimeIndex):
                col = next((c for c in ("time", "datetime", "timestamp") if c in df.columns),
                           None)
                if col is None:
                    raise LookupError("no time index or column")
                df = df.set_index(pd.to_datetime(df[col], utc=True))
            elif df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            return df
        return load

    for f in files:
        sym, tf = f.stem.rsplit("_", 1)
        st = f.stat()
        lazy = ce.Lazy(loader(f))
        ev: dict[str, Any] = {"bars": lazy, "mtime": st.st_mtime_ns, "size": st.st_size}
        m15 = d / f"{sym}_M15.parquet"
        if tf.upper() == "H1" and m15.exists():
            m15_lazy = ce.Lazy(loader(m15))
            ev["pair"] = ce.Lazy(_both(lazy, m15_lazy))

        def tail(a: ce.Lazy = lazy) -> dict[str, Any]:
            df = a.get()
            last = df.index[-1].to_pydatetime()
            return {"last_bar_age_h": (now - last).total_seconds() / 3600.0}
        ev["tail"] = ce.Lazy(tail)
        out.append(ce.Subject(DATA, f.stem, ev, keys={"symbol": sym}, claim=f"{f.name}"))
    reg = _json(UNIVERSE, {})
    pit = _json(PIT_AUDIT, None) or _json(PIT_CENSUS, None)
    out.append(ce.Subject(DATA, "registry",
                          {"registry": {"registered": sorted(reg) if isinstance(reg, dict)
                                        else [], "on_disk": on_disk},
                           "pit": pit if isinstance(pit, dict) else None},
                          keys={"book": "universe"}, claim="the universe registry"))
    return out


# ================================================================== 6. META-RESEARCH & ARCHITECTURE
@seat(META, "bank", 0, "REDUNDANCY", 0.01,
      trap=lambda: {"producers": {"a": 950, "b": 30, "c": 20}, "duplicates": 0, "rows": 1000},
      clean=lambda: {"producers": {"a": 300, "b": 350, "c": 350}, "duplicates": 5, "rows": 1000})
def producer_concentration(sp: ce.Specialist, b: Mapping[str, Any], key: str) -> ce.Result:
    p = {k: float(v) for k, v in (b.get("producers") or {}).items()}
    tot = sum(p.values())
    if tot <= 0:
        return _r(sp, UNMEASURED, 0.0, "", why="no producer stamps in the bank")
    top = max(p.items(), key=lambda kv: kv[1])
    share = top[1] / tot
    if share > 0.6:
        return _r(sp, FAIL, 0.7, "blind_spots", top_producer=top[0], share=round(share, 3),
                  producers=len(p))
    return _r(sp, PASS, 0.6, top_producer=top[0], share=round(share, 3), producers=len(p))


@seat(META, "bank", 0, "DUPLICATE_WORK", 0.01,
      trap=lambda: {"duplicates": 400, "rows": 1000}, clean=lambda: {"duplicates": 5,
                                                                     "rows": 1000})
def duplicate_cells(sp: ce.Specialist, b: Mapping[str, Any], key: str) -> ce.Result:
    rows, dup = float(b.get("rows") or 0), float(b.get("duplicates") or 0)
    if rows <= 0:
        return _r(sp, UNMEASURED, 0.0, "", why="empty bank")
    share = dup / rows
    if share > 0.1:
        return _r(sp, FAIL, 0.7, "dedupe at the compiler", duplicate_share=round(share, 4))
    return _r(sp, PASS, 0.6, duplicate_share=round(share, 4))


@seat(META, "bank", 1, "COVERAGE_GAP", 0.01,
      trap=lambda: {"family_class": {"f1": ["fx"]}, "families": ["f1", "f2", "f3"],
                    "classes": ["fx", "metals", "indices"]},
      clean=lambda: {"family_class": {f: ["fx", "metals"] for f in ("f1", "f2")},
                     "families": ["f1", "f2"], "classes": ["fx", "metals"]})
def blind_spots(sp: ce.Specialist, b: Mapping[str, Any], key: str) -> ce.Result:
    fams, classes = list(b.get("families") or []), list(b.get("classes") or [])
    if not fams or not classes:
        return _r(sp, UNMEASURED, 0.0, "", why="no family or asset-class map")
    got = {(f, c) for f, cs in (b.get("family_class") or {}).items() for c in cs}
    empty = [(f, c) for f in fams for c in classes if (f, c) not in got]
    share = len(empty) / (len(fams) * len(classes))
    if share > 0.5:
        return _r(sp, FAIL, 0.6, "route the idle families to the empty classes",
                  empty_share=round(share, 3), sample=[f"{f}x{c}" for f, c in empty[:12]])
    return _r(sp, PASS, 0.5, empty_share=round(share, 3))


@seat(META, "program", 0, "DEAD_ARCHITECTURE", 0.005,
      trap=lambda: {"census": {"LIVE": 10, "NEVER": 80, "MISSING": 10}},
      clean=lambda: {"census": {"LIVE": 90, "NEVER": 5, "MISSING": 5}})
def dead_organs(sp: ce.Specialist, p: Mapping[str, Any], key: str) -> ce.Result:
    c = {k: float(v) for k, v in (p.get("census") or {}).items() if _f(v) is not None}
    tot = sum(c.values())
    if tot <= 0:
        return _r(sp, UNMEASURED, 0.0, "run runtime_attestation", why="no census")
    dead = (c.get("NEVER", 0) + c.get("MISSING", 0)) / tot
    if dead > 0.3:
        return _r(sp, FAIL, 0.8 if dead > 0.6 else 0.6, "clock or retire the dead organs",
                  dead_share=round(dead, 3), census=p.get("census"),
                  host=p.get("host_role"))
    return _r(sp, PASS, 0.6, dead_share=round(dead, 3))


@seat(META, "program", 0, "WASTED_COMPUTE", 0.005,
      trap=lambda: {"legs": {"a": {"wall_s": 900, "failed_s": 800}}},
      clean=lambda: {"legs": {"a": {"wall_s": 900, "failed_s": 10}}})
def compute_roi(sp: ce.Specialist, p: Mapping[str, Any], key: str) -> ce.Result:
    legs = p.get("legs") or {}
    wall = sum(float(v.get("wall_s") or 0) for v in legs.values())
    failed = sum(float(v.get("failed_s") or 0) for v in legs.values())
    if wall <= 0:
        return _r(sp, UNMEASURED, 0.0, "", why="no compute ledger wall time")
    share = failed / wall
    worst = sorted(legs.items(), key=lambda kv: -float(kv[1].get("failed_s") or 0))[:5]
    if share > 0.2:
        return _r(sp, FAIL, 0.7, "root-cause the failing legs", failed_share=round(share, 3),
                  worst=[k for k, _ in worst])
    return _r(sp, PASS, 0.6, failed_share=round(share, 3))


@seat(META, "program", 1, "LOW_BREADTH", 0.005,
      trap=lambda: {"k_eff": 1.5}, clean=lambda: {"k_eff": 12.0})
def effective_alpha_rank(sp: ce.Specialist, p: Mapping[str, Any], key: str) -> ce.Result:
    k = _f(p.get("k_eff"))
    if k is None:
        return _r(sp, UNMEASURED, 0.0, "publish k_eff in EFFECTIVE_BREADTH.json")
    if k < 4:
        return _r(sp, FAIL, 0.7, "more independent mechanisms", k_eff=k)
    return _r(sp, PASS, 0.6, k_eff=k)


@seat(META, "program", 1, "BENCHMARK_LEAKAGE", 0.005,
      trap=lambda: {"bench_cells": ["a", "b"], "bank_cells": ["a", "x"]},
      clean=lambda: {"bench_cells": ["a", "b"], "bank_cells": ["x", "y"]})
def benchmark_leakage(sp: ce.Specialist, p: Mapping[str, Any], key: str) -> ce.Result:
    bench, bank = set(p.get("bench_cells") or []), set(p.get("bank_cells") or [])
    if not bench:
        return _r(sp, UNMEASURED, 0.0, "publish benchmark cells in QUANTBENCH.json")
    leak = sorted(bench & bank)
    if leak:
        return _r(sp, FAIL, 0.8, "hold benchmark cells out of the bank", leaked=len(leak),
                  sample=leak[:10])
    return _r(sp, PASS, 0.6, bench=len(bench))


@seat(META, "committees", 0, "EVALUATOR_BLIND", 0.001,
      trap=lambda: {"seats": {"a": {"trap": UNMEASURED}, "b": {"trap": PASS, "caught": False}}},
      clean=lambda: {"seats": {"a": {"trap": FAIL, "caught": True, "clean": PASS}}})
def evaluator_discrimination(sp: ce.Specialist, t: Mapping[str, Any], key: str) -> ce.Result:
    """The committees' own planted traps: a seat that misses its defect cannot discriminate."""
    seats = t.get("seats") or {}
    if not seats:
        return _r(sp, UNMEASURED, 0.0, "", why="no trap results")
    missed = sorted(k for k, v in seats.items() if v.get("trap") != UNMEASURED
                    and not v.get("caught"))
    alarms = sorted(k for k, v in seats.items() if v.get("false_alarm"))
    untrapped = sorted(k for k, v in seats.items() if v.get("trap") == UNMEASURED)
    if missed or alarms or untrapped:
        return _r(sp, FAIL, 0.9 if missed else 0.6, "repair the seat against its trap",
                  missed=missed, false_alarms=alarms, untrapped=untrapped)
    return _r(sp, PASS, 0.8, seats=len(seats))


@seat(META, "committees", 1, "REDUNDANT_MODULE", 0.001,
      trap=lambda: {"measured": {"a": 500, "b": 500}, "unique": {"a": 0, "b": 12},
                    "fails": {"a": 40, "b": 52}},
      clean=lambda: {"measured": {"a": 500, "b": 500}, "unique": {"a": 7, "b": 12},
                     "fails": {"a": 40, "b": 52}})
def module_ablation(sp: ce.Specialist, o: Mapping[str, Any], key: str) -> ce.Result:
    """Seats with enough measurements whose catches every other seat also made."""
    meas, uniq, fails = o.get("measured") or {}, o.get("unique") or {}, o.get("fails") or {}
    judged = [k for k, n in meas.items() if n >= ce.MIN_OBS_FOR_RETIREMENT and fails.get(k)]
    if not judged:
        return _r(sp, UNMEASURED, 0.0, "", why="no seat has enough measurements yet")
    idle = sorted(k for k in judged if not uniq.get(k))
    if idle:
        return _r(sp, FAIL, 0.6, "ablate the seat and re-measure the committee's catches",
                  no_unique_catch=idle)
    return _r(sp, PASS, 0.6, judged=len(judged))


def _bank_census(bank: Path | None = None, universe: Mapping[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    rows = _bank_rows(bank)
    if rows is None:
        return None
    reg = universe if universe is not None else _json(UNIVERSE, {})
    cls_of = {k: str((v or {}).get("asset_class") or "?") for k, v in reg.items()
              if isinstance(v, dict)} if isinstance(reg, dict) else {}
    producers: dict[str, int] = {}
    cells: dict[str, int] = {}
    fam_cls: dict[str, set[str]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        producers[str(r.get("producer") or r.get("source") or "?")] = producers.get(
            str(r.get("producer") or r.get("source") or "?"), 0) + 1
        params = r["params"] if isinstance(r.get("params"), dict) else {}
        cell = _node_id(str(r.get("symbol") or ""), str(r.get("family") or ""), params) \
            or ce.sha([r.get("symbol"), r.get("family"), params])
        cells[cell] = cells.get(cell, 0) + 1
        fam_cls.setdefault(str(r.get("family") or "?"), set()).add(
            cls_of.get(str(r.get("symbol") or ""), "?"))
    classes = sorted({c for c in cls_of.values() if c not in ("?", "Equities")})
    return {"rows": len(rows), "producers": producers,
            "duplicates": sum(n - 1 for n in cells.values() if n > 1),
            "families": sorted(fam_cls), "classes": classes,
            "family_class": {f: sorted(c) for f, c in fam_cls.items()},
            "cells": sorted(cells)}


def _program() -> dict[str, Any]:
    rs = _json(RUNTIME_STATE, {})
    legs: dict[str, dict[str, float]] = {}
    for r in _jsonl(COMPUTE_LEDGER, limit=20000):
        leg = str(r.get("run") or "?")
        w = _f(r.get("wall_s")) or 0.0
        e = legs.setdefault(leg, {"wall_s": 0.0, "failed_s": 0.0})
        e["wall_s"] += w
        if str(r.get("outcome") or "ok") not in ("ok", "skipped"):
            e["failed_s"] += w
    br = _json(BREADTH, {})
    qb = _json(QUANTBENCH, {})
    bench = [str(c) for c in (qb.get("cells") or [])] if isinstance(qb, dict) else []
    return {"census": (rs.get("census") if isinstance(rs, dict) else None) or {},
            "host_role": ((rs.get("host") or {}).get("role") if isinstance(rs, dict) else None),
            "legs": legs,
            "k_eff": (br.get("k_eff") or br.get("effective_breadth")) if isinstance(br, dict)
            else None,
            "bench_cells": bench}


def meta_subjects(traps: Mapping[str, Any], ov: Mapping[str, Any],
                  bank: Mapping[str, Any] | None) -> list[ce.Subject]:
    prog = _program()
    if bank:
        prog["bank_cells"] = bank.get("cells") or []
    bank_ev = {k: v for k, v in (bank or {}).items() if k != "cells"} or None
    return [ce.Subject(META, "program", {"bank": bank_ev, "program": prog,
                                         "committees": {"seats": dict(traps)} | dict(ov)},
                       keys={"book": "program"}, claim="the research programme")]


# ================================================================== the pass
def _trigger(s: ce.Subject, state: Mapping[str, Any], queued: Mapping[str, int],
             now_ts: float) -> str | None:
    k = f"{s.committee}|{s.key}"
    if k in queued:
        s.level = queued[k]
        return "queued"
    fp = (state.get("seen") or {}).get(k)
    if fp is None:
        return "new"
    if fp != s.fingerprint():
        return "changed"
    at = (state.get("seen_at") or {}).get(k)
    if at is None or now_ts - float(at) > REMEASURE_H * 3600:
        return "due"
    return None


_TRIGGER_RANK = {"queued": 0, "new": 1, "changed": 2, "due": 3}


def _examine_committee(name: str, subjects: list[ce.Subject], state: dict[str, Any],
                       budget_s: float, now_ts: float) -> tuple[list[dict[str, Any]],
                                                                dict[str, int]]:
    seats = seats_of(name)
    queued = {f"{e['committee']}|{e['subject']}": int(e.get("level", 0))
              for e in state.get("queue") or [] if e.get("committee") == name}
    todo = []
    counts = {"population": len(subjects), "queued": 0, "new": 0, "changed": 0, "due": 0,
              "examined": 0, "deferred": 0}
    for s in subjects:
        t = _trigger(s, state, queued, now_ts)
        if t is None:
            continue
        s.trigger = t
        counts[t] += 1
        todo.append(s)
    todo.sort(key=lambda s: (_TRIGGER_RANK[s.trigger], -s.level))
    deadline = time.monotonic() + budget_s
    examined: list[dict[str, Any]] = []
    for s in todo[:MAX_SUBJECTS.get(name, 100)]:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        examined.append(ce.examine(s, seats, state, min(PER_SUBJECT_S, left)))
    counts["examined"] = len(examined)
    counts["deferred"] = len(todo) - len(examined)
    for ex in examined:
        state.setdefault("seen_at", {})[f"{name}|{ex['key']}"] = now_ts
    return examined, counts


def _queue(experiments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The experiments Python chose: a test that names a seat re-enters at that seat's level."""
    level = {s.name: (s.committee, s.level) for s in SEATS}
    out, seen = [], set()
    for e in experiments:
        hit = level.get(str(e.get("test")))
        if hit is None or hit[0] != e["committee"]:
            continue
        k = (e["committee"], e["subject"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"committee": e["committee"], "subject": e["subject"], "test": e["test"],
                    "level": hit[1], "gain_per_s": e["gain_per_s"]})
    return out[:5000]


def _outcome_fn(examined: Sequence[Mapping[str, Any]], fates: Mapping[str, Any]
                ) -> Callable[[Mapping[str, Any]], bool | None]:
    """Settle a claim: a graph fate for fate seats, a re-measurement on NEW evidence otherwise."""
    fate_seats = {s.name for s in SEATS if s.settles_by == "fate"}
    now_by: dict[tuple[str, str, str], tuple[str, str]] = {}
    cell_of: dict[tuple[str, str], str] = {}
    for ex in examined:
        cell_of[(ex["committee"], ex["key"])] = str((ex.get("keys") or {}).get("cell") or "")
        for r in ex.get("results") or []:
            if r["verdict"] != UNMEASURED:
                now_by[(ex["committee"], ex["key"], r["specialist"])] = (r["verdict"],
                                                                         ex["fingerprint"])

    def outcome(claim: Mapping[str, Any]) -> bool | None:
        if claim["specialist"] in fate_seats:
            gid = str(claim.get("cell") or "")
            f = str((fates.get(gid) or {}).get("fate") or "") if gid else ""
            if f == "CERTIFIED":
                return False
            if f in ("FAILED", "BURIED"):
                return True
            return None
        got = now_by.get((claim["committee"], claim["key"], claim["specialist"]))
        if got is None or got[1] == claim.get("fingerprint"):
            return None                         # no strictly newer evidence yet
        return got[0] == FAIL
    return outcome


def _fates() -> dict[str, Any]:
    try:
        from libs.research.hypothesis_graph import Graph
        return dict(Graph().current())
    except Exception:
        return {}


def _reweight(state: dict[str, Any], per: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """ROI ACCOUNTING: shares move toward measured information per second; floors hold."""
    shares = dict(state.get("shares") or BASE_SHARE)
    info: dict[str, float] = {}
    for c in COMMITTEES:
        p = per.get(c) or {}
        spent = float(p.get("seconds") or 0.0)
        measured = int(p.get("measured") or 0)
        if measured == 0 or spent <= 0:
            continue                             # UNMEASURED moves no budget (L1.28a)
        info[c] = (float(p.get("unique") or 0) + float(p.get("saved_s") or 0) / 10.0
                   + float(p.get("fails") or 0) * 0.1) / spent
    if len(info) >= 2:
        mean = sum(info.values()) / len(info)
        for c, v in info.items():
            ratio = v / mean if mean > 0 else 1.0
            shares[c] = max(SHARE_FLOOR, float(shares.get(c, BASE_SHARE[c]))
                            * (1 + 0.25 * (min(ratio, 3.0) - 1)))
    tot = sum(shares.get(c, BASE_SHARE[c]) for c in COMMITTEES)
    shares = {c: round(max(SHARE_FLOOR, shares.get(c, BASE_SHARE[c]) / tot), 4)
              for c in COMMITTEES}
    state["shares"] = shares
    # Retirement: a week at the floor with enough measured work and nothing unique.
    streak = state.setdefault("floor_streak", {})
    lifetime = state.setdefault("lifetime", {})
    for c in COMMITTEES:
        p = per.get(c) or {}
        lt = lifetime.setdefault(c, {"measured": 0, "unique": 0, "fails": 0, "seconds": 0.0,
                                     "saved_s": 0.0})
        for k in ("measured", "unique", "fails"):
            lt[k] = int(lt[k]) + int(p.get(k) or 0)
        for k in ("seconds", "saved_s"):
            lt[k] = round(float(lt[k]) + float(p.get(k) or 0.0), 3)
        at_floor = shares[c] <= SHARE_FLOOR + 1e-9 and c in info
        streak[c] = int(streak.get(c, 0)) + 1 if at_floor else 0
        retired = state.setdefault("retired_committees", {})
        if streak[c] >= RETIRE_AFTER_PASSES and lt["measured"] >= ce.MIN_OBS_FOR_RETIREMENT \
                and lt["unique"] == 0:
            retired.setdefault(c, {"at": _now(), "why": f"{streak[c]} passes at the budget "
                                   f"floor, {lt['measured']} measured, no unique catch"})
        elif c in retired and (per.get(c) or {}).get("unique"):
            retired.pop(c)                       # re-admitted on evidence
    return shares


def run(*, budget_s: float = DEFAULT_BUDGET_S, write: bool = True,
        subjects: Mapping[str, list[ce.Subject]] | None = None,
        fates: Mapping[str, Any] | None = None, now_ts: float | None = None
        ) -> dict[str, Any]:
    t0 = time.monotonic()
    now_ts = time.time() if now_ts is None else now_ts
    state: dict[str, Any] = _json(STATE, {}) if write else {}
    if not state:
        state = ce.blank_state()
    traps = ce.run_traps(SEATS)
    shares = dict(state.get("shares") or BASE_SHARE)
    retired_c = set(state.get("retired_committees") or {})
    examined_all: list[dict[str, Any]] = []
    per: dict[str, dict[str, Any]] = {}
    bank = None
    for name in COMMITTEES:
        c0 = time.monotonic()
        if name in retired_c:
            per[name] = {"status": "RETIRED", "why": state["retired_committees"][name]["why"]}
            continue
        share_s = max(1.0, float(budget_s) * float(shares.get(name, BASE_SHARE[name])))
        if subjects is not None:
            pool = list(subjects.get(name) or [])
        elif name == SCIENTIFIC:
            # Survivors first: a leak in a certified cell costs more than one in the bank.
            pool = survivor_subjects() + scientific_subjects()
        elif name == FORENSIC:
            pool = forensic_subjects()
        elif name == PORTFOLIO:
            pool = portfolio_subjects()
        elif name == EXECUTION:
            pool = execution_subjects()
        elif name == DATA:
            pool = data_subjects()
        else:
            ov_now = ce.overlap(examined_all, SEATS)
            if subjects is None:
                bank = _bank_census()
            pool = meta_subjects(traps, ov_now, bank)
        ex, counts = _examine_committee(name, pool, state, share_s, now_ts)
        examined_all += ex
        res = [r for e in ex for r in e["results"]]
        per[name] = counts | {
            "status": "RAN", "budget_s": round(share_s, 2),
            "seconds": round(time.monotonic() - c0, 3),
            "measured": sum(1 for r in res if r["verdict"] != UNMEASURED),
            "fails": sum(1 for r in res if r["verdict"] == FAIL),
            "unmeasured": sum(1 for r in res if r["verdict"] == UNMEASURED),
            "subjects_fail": sum(1 for e in ex if e["verdict"] == FAIL),
            "saved_s": round(sum(sum(e["saved_s"].values()) for e in ex), 3),
        }
    ov = ce.overlap(examined_all, SEATS)
    for name in COMMITTEES:
        if per[name].get("status") == "RAN":
            per[name]["unique"] = sum(v for k, v in ov["unique"].items()
                                      if any(s.name == k and s.committee == name
                                             for s in SEATS))
    experiments = ce.compile_experiments(examined_all, {s.name: s.cost_s for s in SEATS})
    trees = [ce.falsification_tree(e, experiments) for e in examined_all
             if e["verdict"] != PASS]
    contra = ce.contradictions(examined_all)
    ce.update_state(state, examined_all, traps)
    settled = ce.settle(state, _outcome_fn(examined_all, fates if fates is not None
                                           else _fates()))
    for e in examined_all:
        for name, s in (e.get("saved_s") or {}).items():
            st = state["seats"].setdefault(name, {})
            st["saved_s"] = round(float(st.get("saved_s", 0.0)) + float(s), 4)
            st["saves"] = int(st.get("saves", 0)) + 1
    newly_retired = ce.retire(state, SEATS, ov)
    new_shares = _reweight(state, per)
    state["queue"] = _queue(experiments)
    state["passes"] = int(state.get("passes", 0)) + 1
    state["last_pass"] = _now()
    roi = ce.roi(state, SEATS, ov)
    doc: dict[str, Any] = {
        "generated_utc": _now(),
        "law": ("Committees challenge; they never certify, allocate, size, veto or trade. "
                "Deterministic specialists only; no LLM sits on a seat."),
        "committees": {c: {"title": TITLES[c], "seats": [s.name for s in seats_of(c)],
                           "share": new_shares[c]} | per[c] for c in COMMITTEES},
        "experiments_ranked": experiments[:200], "experiments_total": len(experiments),
        "queued_next_pass": len(state["queue"]),
        "contradictions": contra[:200], "contradictions_total": len(contra),
        "minority_reports": [{"committee": e["committee"], "key": e["key"],
                              "minority": e["minority"]} for e in examined_all
                             if e["minority"]][:200],
        "trees_sample": trees[:50], "trees_total": len(trees),
        "traps": traps, "settled_this_pass": settled, "retired_this_pass": newly_retired,
        "seconds": round(time.monotonic() - t0, 3), "passes": state["passes"],
    }
    health = health_doc(state, roi, traps, ov, per)
    if write:
        _atomic(STATE, state)
        _atomic(FINDINGS, {"generated_utc": doc["generated_utc"], "examined": examined_all,
                           "experiments": experiments, "trees": trees,
                           "contradictions": contra})
        _atomic(PREMORTEMS, _premortems(examined_all))
        _atomic(REPORT, doc)
        _atomic(HEALTH, health)
    _drop_bank_cache()
    doc["health"] = health
    doc["examined"] = examined_all
    return doc


def _premortems(examined: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The Scientific committee's lead class per cell, for the falsifier battery's ORDER only."""
    hints = _json(PREMORTEMS, {})
    hints = hints if isinstance(hints, dict) else {}
    for e in examined:
        gid = str((e.get("keys") or {}).get("cell") or "")
        if e["committee"] != SCIENTIFIC or not gid:
            continue
        fails = sorted((r for r in e["results"] if r["verdict"] == FAIL),
                       key=lambda r: -float(r["strength"]))
        if fails:
            hints[gid] = {"failure_class": fails[0]["failure_class"], "source": "committees",
                          "specialist": fails[0]["specialist"], "at": _now()}
    return hints


# ================================================================== health (the CRO's duty read)
def health_doc(state: Mapping[str, Any], roi: Mapping[str, Mapping[str, Any]],
               traps: Mapping[str, Mapping[str, Any]], ov: Mapping[str, Any],
               per: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Per specialist: calibration, false_alarm_rate, experiments_saved, overlap,
    ablation_value, roi. Per committee: a verdict the CRO can act on."""
    seats_out: dict[str, Any] = {}
    stats = state.get("seats") or {}
    best_overlap: dict[str, float] = {}
    for p in ov.get("pairs") or []:
        for a in (p["a"], p["b"]):
            best_overlap[a] = max(best_overlap.get(a, 0.0), float(p["jaccard"]))
    for sp in SEATS:
        s = stats.get(sp.name) or {}
        r = roi.get(sp.name) or {}
        n = int(s.get("settled", 0))
        cleans = int(s.get("cleans", 0))
        cost = float(s.get("cost_s", 0.0))
        info = float(r.get("unique_catches") or 0) + float(s.get("saved_s", 0.0)) / 10.0
        seats_out[sp.name] = {
            "committee": sp.committee, "level": sp.level, "status": r.get("status"),
            "calibration": {"brier": round(float(s.get("brier_sum", 0.0)) / n, 4) if n
                            else UNMEASURED, "settled": n,
                            "pending": sum(1 for c in state.get("pending") or []
                                           if c.get("specialist") == sp.name)},
            "false_alarm_rate": round(int(s.get("false_alarms", 0)) / cleans, 4) if cleans
            else UNMEASURED,
            "trap_catch_rate": round(int(s.get("traps_caught", 0)) / int(s["traps"]), 4)
            if s.get("traps") else UNMEASURED,
            "experiments_saved": {"count": int(s.get("saves", 0)),
                                  "seconds": round(float(s.get("saved_s", 0.0)), 3)},
            "overlap": {"max_jaccard": round(best_overlap.get(sp.name, 0.0), 4),
                        "fails": (ov.get("fails") or {}).get(sp.name, 0)},
            "ablation_value": {"unique_catches": (ov.get("unique") or {}).get(sp.name, 0),
                               "sole_objector": (ov.get("ablation") or {}).get(sp.name, 0)},
            "roi": {"cost_s": round(cost, 3), "measured": int(s.get("measured", 0)),
                    "info_per_s": round(info / cost, 4) if cost > 0 else UNMEASURED},
            "last_trap": (traps.get(sp.name) or {}).get("trap"),
        }
    committees: dict[str, Any] = {}
    for c in COMMITTEES:
        mine = {k: v for k, v in seats_out.items() if v["committee"] == c}
        broken = sorted(k for k, v in mine.items() if v["status"] == "BROKEN")
        alarms = sorted(k for k, v in mine.items() if (traps.get(k) or {}).get("false_alarm"))
        p = per.get(c) or {}
        if p.get("status") == "RETIRED":
            verdict, why = "RETIRED", str(p.get("why"))
        elif broken or alarms:
            verdict, why = "DEGRADED", (f"broken seats {broken}" if broken else
                                        f"false alarms on clean twins {alarms}")
        elif p.get("examined", 0) and not p.get("measured"):
            verdict, why = "DARK", "examined subjects but measured nothing"
        elif not p.get("population"):
            verdict, why = UNMEASURED, "no subjects on this host"
        else:
            verdict, why = "HEALTHY", "every seat caught its trap; measured this pass"
        committees[c] = {"title": TITLES[c], "verdict": verdict, "why": why,
                         "seats": len(mine), "broken": broken, "false_alarms": alarms,
                         "retired_seats": sorted(k for k, v in mine.items()
                                                 if v["status"] == "RETIRED"),
                         "share": (state.get("shares") or BASE_SHARE).get(c),
                         "examined": p.get("examined", 0), "measured": p.get("measured", 0),
                         "deferred": p.get("deferred", 0)}
    return {"generated_utc": _now(), "last_pass": state.get("last_pass"),
            "committees": committees, "specialists": seats_out,
            "all_healthy": all(v["verdict"] == "HEALTHY" for v in committees.values())}


def read_health(path: Path | None = None, now: datetime | None = None,
                max_age_h: float = 3.0) -> dict[str, Any]:
    """The CRO's read: the published health plus its age; absent or stale is never HEALTHY."""
    doc = _json(path or HEALTH, None)
    if not isinstance(doc, dict):
        return {"verdict": UNMEASURED, "why": f"{(path or HEALTH).name} absent"}
    try:
        at = datetime.fromisoformat(str(doc.get("generated_utc")))
    except ValueError:
        return {"verdict": UNMEASURED, "why": "health file carries no timestamp"}
    age = ((now or datetime.now(tz=UTC)) - at) / timedelta(hours=1)
    bad = {c: v["verdict"] for c, v in (doc.get("committees") or {}).items()
           if v.get("verdict") != "HEALTHY"}
    if age > max_age_h:
        return {"verdict": "STALE", "age_h": round(age, 2), "why": "the committees leg has "
                "not published within its cadence", "committees": bad}
    return {"verdict": "HEALTHY" if not bad and len(doc.get("committees") or {}) == 6
            else "DEGRADED", "age_h": round(age, 2), "committees": bad}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--dry-run", action="store_true", help="examine, write nothing")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--health", action="store_true", help="read the published health")
    ap.add_argument("--traps", action="store_true", help="run the planted traps only")
    args = ap.parse_args(argv)
    if args.health:
        out = read_health()
        print(json.dumps(out, default=str))
        return 0
    if args.traps:
        print(json.dumps(ce.run_traps(SEATS), default=str))
        return 0
    doc = run(budget_s=args.budget_s, write=not args.dry_run)
    print(json.dumps({"seconds": doc["seconds"], "experiments": doc["experiments_total"],
                      "contradictions": doc["contradictions_total"],
                      "health": {c: v["verdict"] for c, v in doc["health"]["committees"].items()},
                      "committees": {c: {k: v.get(k) for k in ("status", "examined", "measured",
                                                                "fails", "deferred")}
                                     for c, v in doc["committees"].items()}}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
