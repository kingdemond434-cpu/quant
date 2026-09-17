"""The PROGRAM-ALPHA LANE: search candidates that branch, remember and watch a clock.

    for each program (template, prior program, or logic MUTATION of one):
        for each symbol:
            TPE over the program's numeric slots on the desk's own screen
    record every evaluation in the program database; write the winners out with their full IR

WHY A SEPARATE LANE (ledger item D4, principal 2026-09-16). Every other proposer on this desk
searches a FAMILY's parameters or an EXPRESSION's shape. Both are flat: one arithmetic rule
applied identically to every bar. The mechanisms this lane exists for are not flat -- "hold the
Asia range until it breaks, then ride it to the London close", "inside the last day before the
month-end fixing, take the prevailing drift", "fade a move only when it is extreme BY THIS
MONTH'S standard" -- and none of them can be written in the desk's existing vocabularies at all.
`libs/research/program_ir.py` is the vocabulary; this is the search over it.

THE TWO HALVES ARE DELIBERATELY SEPARATE, which is the half of D4 the ledger says is missing.
LOGIC REVISION changes what the program IS (`program_ir.mutate_logic`: swap a comparison, wrap a
subtree in a branch, turn a rule into a state machine). NUMERIC OPTIMISATION changes only what
its slots hold (TPE, on the same Parzen split `search_populations.bayesian` uses over expression
features -- imported from there, not re-spelled). Mixing them is how a search reports a "better
mechanism" that is one lucky lookback.

NOTHING HERE IS EXECUTED AS CODE. A program is a JSON tree validated against an eleven-node
allowlist before any data is touched, and `compile_program` turns it into the desk's own `Signal`
objects. There is no eval, no exec and no model-written source anywhere in this path.

THE WIRING GAP, STATED RATHER THAN PAPERED OVER. `mt5desk` has no `program_alpha` family
(measured: 28 registered families, and `get_family_func("program_alpha")` is None), and
`family_generic` CANNOT host a program -- its five axes are (event, context, direction, output,
quality), which cannot express a state machine, an event clock or a cross-asset reference, and
its own docstring refuses approximation for exactly this reason. So a winner is NOT donated into
the miner-discovery contract, because a row the compiler cannot execute is a docket cell that
spends the family-wise error budget and can never be judged. It is written to
`data/program_candidates.jsonl` with its full IR, and the report names what is missing: a
registered family whose params are a program tree, so the ten gates can reach these candidates.

Usage:
    python research/program_alpha_lane.py --dry-run
    python research/program_alpha_lane.py --symbols EURUSD,XAUUSD --budget-s 240
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families  # noqa: E402

from libs.research import program_ir as ir  # noqa: E402
from libs.research.search_populations import TPE_CANDIDATES, TPE_GAMMA  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "program_alpha"
UNI = _DESK / "data" / "universe"
REPORT = _DESK / "reports" / "PROGRAM_ALPHA_LANE.json"
PROGRAM_DB = _DESK / "data" / "program_db.jsonl"
CANDIDATES = _DESK / "data" / "program_candidates.jsonl"

#: Six non-equity majors and gold. The two-lane mandate (2026-09-06) keeps single names out of
#: hypothesis discovery, and `proposer_common.donate` enforces it again at the door.
DEFAULT_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "XAUUSD")
#: The peer a cross-asset program references. A symbol with no peer on disk simply does not get
#: the cross-asset template -- an absent reference is not a reason to substitute a different one.
PEERS = {"EURUSD": "GBPUSD", "GBPUSD": "EURUSD", "USDJPY": "USDCHF", "AUDUSD": "NZDUSD",
         "USDCHF": "EURUSD", "USDCAD": "AUDUSD", "XAUUSD": "XAGUSD"}
#: Bars the cheap screen runs on. This is a SCREEN, not the gauntlet: its job is to spend the
#: hour on programs worth a full judgment, and two years of H1 is enough to tell a mechanism that
#: fires from one that cannot.
SCREEN_BARS = 24 * 500
#: Slot draws per (program, symbol) before the lane moves on. Small on purpose: breadth over
#: programs beats depth on one, because the LOGIC is what this lane is searching.
TRIALS = 8
#: How many evaluations one program keeps in the database. A program tried for months would
#: otherwise grow a row nothing can read.
KEEP_EVALS = 40
#: Prior programs, by best measured t, that seed the next run's population.
SEED_FROM_DB = 8
#: The polarity axis, searched like a slot: +1 trades the program's own sign, -1 the opposite.
POLARITY = ir.Slot("polarity", -1.0, 1.0, 1.0)


# --------------------------------------------------------------------------- the seed templates
def _gate(lo: int, hi: int) -> ir.Node:
    """1.0 inside [lo, hi) broker hours. `mul` of two comparisons is this grammar's AND."""
    return ir.Binary("mul", ir.Compare("ge", ir.Series("hour"), ir.Const(float(lo))),
                     ir.Compare("lt", ir.Series("hour"), ir.Const(float(hi))))


def _session_range_breakout() -> ir.Node:
    """A STATE MACHINE: flat until the prior range breaks, then held until the trend gives way."""
    n = ir.Slot("range_n", 4, 96, 24)
    x = ir.Slot("exit_n", 4, 240, 48)
    up = ir.Compare("gt", ir.Series("close"), ir.Rolling("max", ir.Series("high"), n, 1))
    dn = ir.Compare("lt", ir.Series("close"), ir.Rolling("min", ir.Series("low"), n, 1))
    mean = ir.Rolling("mean", ir.Series("close"), x)
    machine = ir.State((
        ir.StateDef("flat", 0, (ir.Transition("long", up), ir.Transition("short", dn))),
        ir.StateDef("long", 1, (ir.Transition("flat", ir.Compare("lt", ir.Series("close"),
                                                                  mean)),)),
        ir.StateDef("short", -1, (ir.Transition("flat", ir.Compare("gt", ir.Series("close"),
                                                                   mean)),)),
    ))
    return ir.Cond(_gate(7, 17), machine, ir.Const(0.0))


def _event_clock_drift(kind: str = "month_end") -> ir.Node:
    """An EVENT CLOCK: inside the run-up to a forced-flow event, take the prevailing drift."""
    lead = ir.Slot("lead_bars", 2, 96, 24)
    trend = ir.Rolling("mean", ir.Series("ret"), ir.Slot("trend_n", 4, 240, 48))
    near = ir.Compare("le", ir.EventClock(kind, "to"), lead)
    return ir.Cond(near, ir.Cond(ir.Compare("gt", trend, ir.Const(0.0)), ir.Const(1.0),
                                 ir.Const(-1.0)), ir.Const(0.0))


def _adaptive_reversion() -> ir.Node:
    """An ADAPTIVE THRESHOLD: fade a stretch only when it is extreme by the recent regime."""
    z = ir.Rolling("zscore", ir.Series("close"), ir.Slot("z_n", 12, 240, 96))
    w = ir.Slot("q_n", 50, 500, 240)
    hi = ir.Adaptive(z, w, ir.Slot("q_hi", 0.6, 0.99, 0.9))
    lo = ir.Adaptive(z, w, ir.Slot("q_lo", 0.01, 0.4, 0.1))
    return ir.Cond(ir.Compare("gt", z, hi), ir.Const(-1.0),
                   ir.Cond(ir.Compare("lt", z, lo), ir.Const(1.0), ir.Const(0.0)))


def _cross_asset_residual(peer: str) -> ir.Node:
    """A CROSS REFERENCE: trade the gap between two normalised paths, back toward zero."""
    n = ir.Slot("z_n", 12, 240, 96)
    spread = ir.Binary("sub", ir.Rolling("zscore", ir.Series("close"), n),
                       ir.Rolling("zscore", ir.CrossRef(peer, "close"), n))
    w = ir.Slot("q_n", 50, 500, 240)
    hi = ir.Adaptive(spread, w, ir.Slot("q_hi", 0.6, 0.99, 0.9))
    lo = ir.Adaptive(spread, w, ir.Slot("q_lo", 0.01, 0.4, 0.1))
    return ir.Cond(ir.Compare("gt", spread, hi), ir.Const(-1.0),
                   ir.Cond(ir.Compare("lt", spread, lo), ir.Const(1.0), ir.Const(0.0)))


def templates(symbol: str) -> dict[str, ir.Node]:
    """The seed library. Registered families are not programs, so the lane brings its own."""
    out: dict[str, ir.Node] = {
        "session_range_breakout": _session_range_breakout(),
        "event_clock_drift": _event_clock_drift("month_end"),
        "fixing_clock_drift": _event_clock_drift("fixing"),
        "adaptive_reversion": _adaptive_reversion(),
    }
    peer = PEERS.get(symbol.upper())
    if peer and (UNI / f"{peer}_H1.parquet").exists():
        out["cross_asset_residual"] = _cross_asset_residual(peer)
    return out


# --------------------------------------------------------------------------- the program database
@dataclass
class Program:
    """One program and everything the desk has ever measured about it."""
    fingerprint: str
    name: str
    tree: ir.Node
    lineage: dict[str, Any] = field(default_factory=dict)
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def best(self) -> float:
        vals = [float(e.get("t_net", float("nan"))) for e in self.evaluations]
        vals = [v for v in vals if math.isfinite(v)]
        return max(vals) if vals else float("-inf")

    def row(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, "name": self.name,
                "describe": ir.describe(self.tree), "tree": ir.to_json(self.tree),
                "lineage": self.lineage, "created_at": self.created_at,
                "updated_at": datetime.now(tz=UTC).isoformat(),
                "n_evaluations": len(self.evaluations), "best_t_net": self.best(),
                "evaluations": self.evaluations[-KEEP_EVALS:]}


def load_db(path: Path | None = None) -> dict[str, Program]:
    """The database, keyed by FINGERPRINT -- which is what makes it dedupe rather than grow.

    A row whose tree no longer validates is dropped with nothing claimed: the IR's caps are the
    contract, and a program that would be refused today may not re-enter a population.
    """
    out: dict[str, Program] = {}
    src = path or PROGRAM_DB
    if not src.exists():
        return out
    for line in src.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            tree = ir.from_json(row["tree"])
        except (ValueError, KeyError, TypeError):
            continue
        if ir.validate(tree):
            continue
        fp = ir.fingerprint(tree)
        prior = out.get(fp)
        evals = list(row.get("evaluations") or [])
        if prior is not None:
            prior.evaluations = (prior.evaluations + evals)[-KEEP_EVALS:]
            continue
        out[fp] = Program(fp, str(row.get("name") or "unnamed"), tree,
                          dict(row.get("lineage") or {}), evals[-KEEP_EVALS:],
                          str(row.get("created_at") or ""))
    return out


def save_db(db: dict[str, Program], path: Path | None = None) -> Path:
    dst = path or PROGRAM_DB
    body = "\n".join(json.dumps(p.row(), default=str) for p in db.values())
    _atomic(dst, body + ("\n" if body else ""))
    return dst


def _atomic(path: Path, text: str) -> None:
    """Write whole or not at all. An hourly organ that half-writes its own memory has none."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


# --------------------------------------------------------------------------- bars and screening
_FRAMES: dict[str, pd.DataFrame] = {}


def bars_for(sym: str) -> pd.DataFrame | None:
    """`<SYM>_H1.parquet` on its own bar clock -- `external_gauntlet._bars_for`'s two calls."""
    key = sym.upper()
    if key in _FRAMES:
        return _FRAMES[key]
    pq = UNI / f"{key}_H1.parquet"
    if not pq.exists():
        return None
    try:
        frame = families._h1(pd.read_parquet(pq))
    except (OSError, ValueError, KeyError):
        return None
    if not isinstance(frame.index, pd.DatetimeIndex) or not len(frame):
        return None
    _FRAMES[key] = frame
    return frame


def _tpe_ask(box: list[ir.Slot], history: list[tuple[dict[str, float], float]],
             rng: np.random.Generator, n_cand: int = 0) -> dict[str, float]:
    """One slot vector to try next: TPE's Parzen split, on a numeric box instead of features.

    `search_populations.bayesian` splits its history at `TPE_GAMMA` into l(x) and g(x) and ranks
    cheap draws by sum log l/g; this is the same estimator with a Gaussian kernel per dimension,
    because a slot is continuous where an operator is present or absent. With too little history
    it draws uniformly AND SAYS SO by doing nothing else -- a surrogate fitted on nothing is a
    prior, not a model.
    """
    def draw() -> dict[str, float]:
        return {s.name: float(rng.uniform(s.lo, s.hi)) for s in box}

    rows = [(v, f) for v, f in history if math.isfinite(f)]
    cands = [draw() for _ in range(max(n_cand, TPE_CANDIDATES) // 8)]
    if len(rows) < 6 or not cands:
        return cands[0] if cands else {s.name: s.default for s in box}
    fits = np.asarray([f for _v, f in rows], dtype=float)
    cut = float(np.quantile(fits, 1.0 - TPE_GAMMA))
    good = [v for v, f in rows if f >= cut]
    bad = [v for v, f in rows if f < cut]
    if not good or not bad:
        return cands[0]

    def logp(pool: list[dict[str, float]], s: ir.Slot, x: float) -> float:
        vals = np.asarray([p.get(s.name, s.default) for p in pool], dtype=float)
        band = max(float(vals.std()), (s.hi - s.lo) / 10.0, 1e-9)
        return float(np.log(np.mean(np.exp(-0.5 * ((x - vals) / band) ** 2)) + 1e-12))

    best, best_score = cands[0], -np.inf
    for c in cands:
        score = sum(logp(good, s, c[s.name]) - logp(bad, s, c[s.name]) for s in box)
        if score > best_score:
            best, best_score = c, score
    return best


def _t_net(sc: dict[str, Any]) -> float:
    """The screen's t AFTER the round trip. `t_gross` is what the screen reports; the standard
    error it implies is gross / t_gross, so the net t follows without re-deriving the sample."""
    gross, t = float(sc["gross_per_trade"]), float(sc["t_gross"])
    if not math.isfinite(gross) or abs(gross) < 1e-12 or not math.isfinite(t):
        return float("-inf")
    return float((gross - float(sc["cost_frac"])) * t / gross)


# --------------------------------------------------------------------------- the lane
def run(symbols: list[str] | None = None, budget_s: float = 240.0, max_programs: int = 20,
        seed: int = 0, dry_run: bool = False, db_path: Path | None = None) -> dict[str, Any]:
    """One pass: seed, revise logic, tune slots, record everything, publish the winners."""
    started = time.monotonic()
    rng = np.random.default_rng(seed)
    now = datetime.now(tz=UTC).isoformat()
    syms = [s.upper() for s in (symbols or list(DEFAULT_SYMBOLS))]
    db = load_db(db_path)
    unmeasured: dict[str, str] = {}
    calendar = ir.load_calendar()
    if not calendar:
        unmeasured["forced_flow_calendar"] = ("absent or unreadable; every EventClock series is "
                                              "NaN and the clock templates cannot fire")
    meta = pc.universe_meta()

    # ---- seeds: the template library, then the programs the desk already knows about
    pop: dict[str, Program] = {}
    for sym in syms:
        for name, tree in templates(sym).items():
            errs = ir.validate(tree)
            if errs:
                unmeasured[f"template:{name}"] = "; ".join(errs)
                continue
            fp = ir.fingerprint(tree)
            pop.setdefault(fp, db.get(fp) or Program(fp, name, tree, {"op": "template"},
                                                     [], now))
    n_templates = len(pop)
    for prog in sorted(db.values(), key=lambda p: -p.best())[:SEED_FROM_DB]:
        pop.setdefault(prog.fingerprint, prog)
    n_seeds = len(pop)

    # ---- LOGIC REVISION, kept separate from the tuning below on purpose
    parents = sorted(pop.values(), key=lambda p: -p.best())[:max(2, max_programs // 3)]
    for parent in parents:
        if len(pop) >= max_programs:
            break
        child = ir.mutate_logic(parent.tree, rng)
        fp = ir.fingerprint(child)
        if fp in pop:
            continue
        pop[fp] = db.get(fp) or Program(fp, f"{parent.name}+mut", child,
                                        {"op": "mutate_logic", "parent": parent.fingerprint},
                                        [], now)
    programs = sorted(pop.values(), key=lambda p: -p.best())[:max_programs]

    # ---- TUNING: TPE over each program's numeric slots, on the desk's own screen
    rows: list[dict[str, Any]] = []
    n_evaluated = 0
    n_short = 0
    for sym in syms:
        if time.monotonic() - started > budget_s:
            unmeasured[sym] = "lane budget exhausted before this symbol was reached"
            continue
        frame = bars_for(sym)
        if frame is None or len(frame) < 24 * 250:
            unmeasured[sym] = "under 250 days of H1 bars"
            continue
        d = frame.iloc[-SCREEN_BARS:] if len(frame) > SCREEN_BARS else frame
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            unmeasured[sym] = "no contract terms to price the round trip"
            continue
        unfillable = pc.artifact_hours(d)
        peer = PEERS.get(sym)
        peer_bars = bars_for(peer) if peer else None
        extras = ir.Extras(cross={peer: peer_bars} if peer and peer_bars is not None else {},
                           calendar=calendar, symbol=sym)
        for prog in programs:
            if time.monotonic() - started > budget_s:
                unmeasured[f"{sym}:{prog.name}"] = "lane budget exhausted"
                break
            try:
                fn = ir.compile_program(prog.tree, extras, tag=SOURCE)
            except ir.ProgramError as exc:
                unmeasured[f"{prog.fingerprint}"] = f"uncompilable: {exc}"
                continue
            box = [*ir.slots(prog.tree), *ir.exec_slots(), POLARITY]
            history: list[tuple[dict[str, float], float]] = [
                ({str(k): float(v) for k, v in (e.get("slots") or {}).items()},
                 float(e.get("t_net", float("nan"))))
                for e in prog.evaluations if e.get("symbol") == sym]
            for trial in range(TRIALS):
                if time.monotonic() - started > budget_s:
                    break
                vals = ({s.name: s.default for s in box} if trial == 0 and not history
                        else _tpe_ask(box, history, rng))
                side = 1 if vals.get("polarity", 1.0) >= 0 else -1
                try:
                    sigs = fn(d, side, **vals)
                except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                    unmeasured[f"{prog.fingerprint}:{sym}"] = f"{type(exc).__name__}: {exc}"
                    break
                n_evaluated += 1
                sc = pc.screen(d, sigs, cost, unfillable)
                if sc is None:
                    # UNDER `proposer_common.MIN_TRADES` non-overlapping trades, or no dispersion.
                    # Counted, because a program that never fires and a program that fires and
                    # loses are different findings and a bare trial count hides the difference.
                    n_short += 1
                    history.append((vals, float("-inf")))
                    continue
                t_net = _t_net(sc)
                history.append((vals, t_net))
                ev = {"at": now, "symbol": sym, "side": side, "t_net": round(t_net, 4),
                      "slots": {k: round(float(v), 5) for k, v in vals.items()},
                      **{k: sc[k] for k in ("n_independent", "t_gross", "net_per_trade",
                                            "gross_per_trade", "cost_frac", "clears_cost")}}
                prog.evaluations.append(ev)
                rows.append({"cell": f"{sym}.{SOURCE}.{prog.fingerprint}", "symbol": sym,
                             "fingerprint": prog.fingerprint, "name": prog.name,
                             "describe": ir.describe(prog.tree), "side": side,
                             "tree": ir.to_json(prog.tree),
                             "slots": ev["slots"], "t_net": t_net, **sc})
            db[prog.fingerprint] = prog

    # ---- DEFLATE BY EVERYTHING THE LANE LOOKED AT, then keep one row per program-symbol cell
    rows = pc.deflate(rows)
    winners = pc.best_per_cell(rows)
    # ONE ROW PER CELL in `top`, for the same reason `best_per_cell` exists: ten tunings of one
    # program is one finding, and a leaderboard that lists them ten times reads as ten.
    seen_cells: dict[str, dict[str, Any]] = {}
    for r in sorted(rows, key=lambda x: -float(x.get("t_deflated_sweep", 0.0))):
        seen_cells.setdefault(str(r["cell"]), r)
    top = [{"fingerprint": r["fingerprint"], "describe": r["describe"], "symbol": r["symbol"],
            "t": round(float(r["t_deflated_sweep"]), 3), "n": int(r["n_independent"]),
            "slots": r["slots"]}
           for r in list(seen_cells.values())[:10]]

    report: dict[str, Any] = {
        "at": now, "n_seeds": n_seeds, "n_templates": n_templates,
        "n_programs": len(programs), "n_evaluated": n_evaluated,
        "n_donated": 0, "top": top, "db_size": len(db),
        "n_screens_too_short": n_short, "n_cells": len(seen_cells),
        "symbols": syms, "budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 1),
        "unmeasured": unmeasured, "dry_run": bool(dry_run),
        "donation_path": str(CANDIDATES), "program_db": str(db_path or PROGRAM_DB),
        "wiring_gap": ("mt5desk has no `program_alpha` family and `family_generic` cannot host a "
                       "program (its five axes cannot express a state machine, an event clock or "
                       "a cross-asset reference), so winners are written with their full IR "
                       "instead of donated: a docket cell no compiler can execute spends the "
                       "shared family-wise error budget and can never be judged. WHAT IS "
                       "MISSING: a registered family whose params are a program tree."),
        "rule": ("a program is a validated JSON tree, never source; the screen is forward return "
                 "at the program's own TTL, net of round trip, non-overlapping, deflated by "
                 "every trial this lane ran. It proposes; the ten gates certify."),
    }
    if dry_run:
        report["written"] = None
        return report

    cands = _write_candidates(winners, len(rows))
    report["n_donated"] = len(cands)
    save_db(db, db_path)
    _atomic(REPORT, json.dumps(report, indent=1, default=str))
    report["written"] = str(REPORT)
    return report


def _write_candidates(winners: list[dict[str, Any]], tests_run: int) -> list[dict[str, Any]]:
    """Append the winners, IR and all, to the candidates file. POINT-IN-TIME OR NOT AT ALL.

    The same rule `proposer_common.donate` enforces: a row that cannot carry an available_time
    cannot be refused for a decision earlier than the desk could have known it, so it is not
    written. These rows are not in the miner-discovery contract -- see `wiring_gap`.
    """
    if not winners:
        return []
    out: list[dict[str, Any]] = []
    for r in winners:
        row = {"source": SOURCE, "kind": SOURCE, "symbol": r["symbol"], "family": SOURCE,
               "fingerprint": r["fingerprint"], "program": r.get("tree"),
               "describe": r["describe"], "side": r["side"], "params": r["slots"],
               "mechanism": f"program {r['name']}: {r['describe']}",
               "title": f"{r['symbol']} {r['name']} {r['fingerprint']}",
               "tests_run": int(tests_run),
               "evidence": {k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                                  "net_per_trade", "cost_frac", "t_gross",
                                                  "t_deflated_sweep", "n_tests_sweep")},
               "executable": False,
               "why_not_donated": "no registered family can execute a program tree"}
        try:
            from libs.data.pit import is_stamped
            from libs.data.pit import stamp as pit_stamp
            row = pit_stamp(row, SOURCE)
            if not is_stamped(row):
                continue
        except Exception:
            continue
        out.append(row)
    if not out:
        return []
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES.open("a", encoding="utf-8") as handle:
        for row in out:
            handle.write(json.dumps(row, default=str) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the program-alpha lane (ledger item D4)")
    ap.add_argument("--symbols", default=None, help="comma-separated; default 6 majors + XAUUSD")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--max-programs", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    a = ap.parse_args(argv)
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] if a.symbols else None
    rep = run(symbols=syms, budget_s=a.budget_s, max_programs=a.max_programs, seed=a.seed,
              dry_run=a.dry_run)
    tag = "  [DRY RUN, nothing written]" if a.dry_run else ""
    print(f"PROGRAM-ALPHA LANE{tag}  seeds={rep['n_seeds']} programs={rep['n_programs']} "
          f"evaluated={rep['n_evaluated']} db={rep['db_size']} in {rep['elapsed_s']}s")
    for r in rep["top"][:10]:
        print(f"  {r['symbol']:8s} {r['fingerprint']}  t_defl={r['t']:+.2f} n={r['n']:4d}  "
              f"{r['describe'][:90]}")
    for k, v in list(rep["unmeasured"].items())[:6]:
        print(f"  UNMEASURED {k}: {v}")
    print(f"  candidates: {rep['n_donated']} -> {rep['donation_path']}")
    print(f"  WIRING GAP: {rep['wiring_gap'][:150]}")
    if rep.get("written"):
        print(f"written: {rep['written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
