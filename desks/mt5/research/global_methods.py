"""THE WORLD-PRACTICE METHODS AS PRODUCERS: cross-sectional LambdaRank, the 高频因子 intraday
realised-moment class book, the market-profile value-area rules and the Korean 변동성 돌파.

WHAT WAS MISSING. `generator_coverage` maps every hypothesis-generation method quants use, from
the Chinese broker factor reports to the Russian volume-profile school, against the code that
carries it on this desk. Four methods with a written economic prior on the desk's own tradables
had no code at all (the families and their priors: `mt5desk/family_global_methods.py`). This is
their producer, one bounded pass per method:

  1. THE SCOPE (`research/universe_policy.py`, the ONLY scope rule): every symbol with an H1 bar
     file that `universe_policy.may_hypothesise(symbol, family)` admits and that is NOT an exotic
     (`universe_policy.is_exotic_symbol`, the one exotic definition). A class method additionally
     needs a peer class with at least `families_cross_sectional.MIN_MEMBERS` non-exotic members
     holding bars. Share CFDs are not minted: these families are not the policy's class books.
  2. THE CELLS. One cell per (symbol, family-grid point) -- the grid is
     `family_global_methods.PARAM_GRID`, written there once -- H1 pinned in params (the judge
     pops `timeframe` before the call, the compiler does not re-expand it), `symbol` in params for
     the class books because they load their own panel from it.
  3. CONSTRUCTION, NOT A SCREEN. A cell is minted only when its symbol has the history its
     trailing windows need (`min_days` distinct bar days). No return is read here: a cell left out
     is never tested and is no trial.
  4. THE DOOR AND THE CHARGE. `family_donation.donate_per_family` writes
     `data/intelligence/global_methods/discoveries_*_<family>.json` through
     `proposer_common.donate` (PIT stamp, lane filter, preregistration, registry record); the
     contract's `tests_run` charges EVERY donated cell as an ordinary trial after the compiler's
     own expansion. The per-method ledger (`data/donation_ledgers/global_methods_<method>.jsonl`)
     remembers what was charged, so a re-run never re-offers or re-charges a cell.
  5. BOUNDED, NOT THROTTLED. A pass donates at most max(the judge's measured intake for the
     family in JUDGE_COVERAGE.json, EMIT_FLOOR) new cells, walking a persistent cursor over the
     id-ordered cell space so successive passes cover all of it.

ARTIFACT: reports/GLOBAL_METHOD_<METHOD>.json -- the method, its origin and prior, the cell space,
cells donated and trials charged this pass, cells charged in total, the scope and every reason a
symbol or a cell was not minted. `generator_coverage` reads it.

    python research/global_methods.py --method xs_ltr --once --budget-s 240
    python research/global_methods.py --method all --once --dry-run --out /tmp/GM.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import itertools
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_global_methods as gm  # noqa: E402

SOURCE = "global_methods"
TIMEFRAME = "H1"
EMIT_FLOOR = 300
UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class Method:
    name: str
    family: str
    origin: str
    method_row: str
    min_days: int

    @property
    def report_name(self) -> str:
        return f"GLOBAL_METHOD_{self.name.upper()}.json"


METHODS: dict[str, Method] = {
    "xs_ltr": Method("xs_ltr", "cross_sectional_class_ltr",
                     "institutional (Numerai, WorldQuant; 机器学习选股; Poh et al. 2021)",
                     "learning-to-rank, cross-sectional (LambdaRank) over the symbol panel",
                     min_days=900),
    "hf_moment": Method("hf_moment", "cross_sectional_class_hf_moment",
                        "China (Haitong / Founder 高频因子) + academic (Amaya et al. 2015)",
                        "intraday high-frequency factors aggregated to daily (realised skew, "
                        "signed jump variation, MAX), ranked in the class", min_days=320),
    "value_area": Method("value_area", "value_area_rule",
                         "US (CBOT Market Profile) + Russia (volume-profile school)",
                         "market profile / volume profile value-area rules (80% rule, "
                         "acceptance)", min_days=250),
    "vol_breakout": Method("vol_breakout", "volatility_breakout_kr",
                           "Korea (변동성 돌파, 노이즈 비율) + US (Larry Williams)",
                           "Larry Williams volatility breakout, Korean noise-ratio variant",
                           min_days=250),
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def cell_id(method: str, symbol: str, params: dict[str, Any]) -> str:
    raw = f"{method}|{symbol}|{json.dumps(params, sort_keys=True, default=str)}"
    return "gm_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe"

    def state(self, method: str) -> Path:
        return self.desk / "data" / "global_methods" / f"{method}.json"

    def report(self, m: Method) -> Path:
        return self.desk / "reports" / m.report_name

    @property
    def judge_coverage(self) -> Path:
        return self.desk / "reports" / "JUDGE_COVERAGE.json"

    def ledger(self, method: str) -> Path:
        return self.desk / "data" / "donation_ledgers" / f"{SOURCE}_{method}.jsonl"


DEFAULT_PATHS = Paths(_DESK)


def grid(family: str) -> list[dict[str, Any]]:
    spec = gm.PARAM_GRID.get(family) or {}
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def _policy() -> Any:
    from research import universe_policy as up
    return up


def bar_days(paths: Paths, symbol: str) -> int | None:
    """Distinct calendar days in `symbol`'s H1 store, or None when it cannot be read."""
    try:
        import pandas as pd

        frame = pd.read_parquet(paths.universe / f"{symbol}_H1.parquet", columns=["close"])
        idx = frame.index
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.DatetimeIndex(pd.to_datetime(idx, utc=True, errors="coerce"))
        return int(idx.dropna().normalize().nunique())
    except Exception:
        return None


@dataclass
class Universe:
    have: set[str] = field(default_factory=set)
    in_scope: list[str] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    classes: dict[str, str] = field(default_factory=dict)
    peers: dict[str, list[str]] = field(default_factory=dict)

    def skip(self, why: str) -> None:
        self.excluded[why] = self.excluded.get(why, 0) + 1


def load_universe(paths: Paths, m: Method, policy: Any = None) -> Universe:
    """Which symbols `m` may mint on: read from the bar store and the policy, never listed."""
    up = policy or _policy()
    u = Universe()
    u.have = {p.stem.removesuffix("_H1") for p in paths.universe.glob("*_H1.parquet")}
    needs_class = gm.NEEDS_CLASS.get(m.family, False)
    try:
        members = up.peer_classes()
    except Exception:
        members = {}
    for sym in sorted(u.have):
        try:
            allowed = bool(up.may_hypothesise(sym, m.family))
        except TypeError:
            allowed = bool(up.may_hypothesise(sym))
        if not allowed:
            u.skip(f"lane:{up.lane(sym)}")
            continue
        if up.is_exotic_symbol(sym):
            u.skip("exotic (universe_policy.is_exotic_symbol)")
            continue
        klass = up.peer_class(sym)
        if needs_class:
            if klass is None:
                u.skip("no_peer_class")
                continue
            peers = [p for p in members.get(klass, []) if p != sym and p in u.have
                     and not up.is_exotic_symbol(p)]
            if len(peers) + 1 < int(getattr(gm.xs, "MIN_MEMBERS", 5)):
                u.skip(f"class_too_small:{klass}")
                continue
            u.peers[sym] = peers
        u.in_scope.append(sym)
        u.classes[sym] = str(klass or "")
    return u


@dataclass(frozen=True)
class Cell:
    cid: str
    method: Method
    symbol: str
    params: dict[str, Any]
    klass: str

    def row(self) -> dict[str, Any]:
        m = self.method
        prior = gm.PRIORS[m.family]
        knobs = ", ".join(f"{k}={v}" for k, v in sorted(self.params.items())
                          if k not in ("symbol", "timeframe"))
        return {"source": SOURCE, "kind": "hypothesis", "url": "", "symbol": self.symbol,
                "family": m.family, "params": dict(self.params),
                "title": f"{m.family} on {self.symbol} {TIMEFRAME} ({knobs})",
                "mechanism": f"{m.method_row}: {prior}",
                "falsifier": (f"{m.family} on {self.symbol} {TIMEFRAME} with {knobs}: no "
                              "net-of-cost edge out of sample"),
                "asset_class": self.klass,
                "lineage": {"source": SOURCE, "method": m.name, "method_row": m.method_row,
                            "origin": m.origin, "prior": prior, "global_method_cell_id": self.cid,
                            "peer_class": self.klass, "timeframe": TIMEFRAME}}


def cell_space(u: Universe, m: Method) -> list[Cell]:
    out: list[Cell] = []
    needs_class = gm.NEEDS_CLASS.get(m.family, False)
    for sym in u.in_scope:
        for point in grid(m.family):
            params = {**point, "timeframe": TIMEFRAME}
            if needs_class:
                params["symbol"] = sym
            out.append(Cell(cell_id(m.name, sym, params), m, sym, params, u.classes.get(sym, "")))
    out.sort(key=lambda c: c.cid)
    return out


def judge_intake(paths: Paths, family: str) -> tuple[int | None, str]:
    doc = read_json(paths.judge_coverage, {})
    fam = ((doc.get("families") or {}).get(family) or {}) if isinstance(doc, dict) else {}
    q = fam.get("quota") if isinstance(fam, dict) else None
    if isinstance(q, (int, float)) and q > 0:
        return int(q), f"JUDGE_COVERAGE.json families.{family}.quota = {int(q)}"
    return None, f"{UNMEASURED}: no {family} quota in {paths.judge_coverage.name}"


def charged_identities(ledger: Path) -> set[str]:
    out: set[str] = set()
    try:
        with ledger.open(encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(ValueError, AttributeError):
                    out.add(str(json.loads(line).get("cell_id") or ""))
    except OSError:
        pass
    out.discard("")
    return out


def _donation_modules() -> tuple[Any, Any]:
    from research import family_donation as fd
    from research import proposer_common as pc
    return fd, pc


class Producer:
    def __init__(self, method: str, paths: Paths = DEFAULT_PATHS, *, policy: Any = None,
                 donate: Callable[..., dict[str, Any]] | None = None,
                 days: Callable[[str], int | None] | None = None, dry_run: bool = False,
                 out: Path | None = None) -> None:
        self.m = METHODS[method]
        self.paths = paths
        self.policy = policy
        self.donate = donate
        self.days = days or (lambda s: bar_days(paths, s))
        self.dry_run = dry_run
        self.out = out
        self.t0 = time.monotonic()

    def run(self, budget_s: float = 240.0, cap: int | None = None) -> dict[str, Any]:
        m = self.m
        rep: dict[str, Any] = {
            "source": SOURCE, "method": m.name, "family": m.family, "method_row": m.method_row,
            "origin": m.origin, "prior": gm.PRIORS[m.family], "generated_at": now_iso(),
            "dry_run": self.dry_run, "timeframe": TIMEFRAME, "grid": gm.PARAM_GRID[m.family],
            "status": "STARTED", "tests_run": 0, "cells_proposed": 0}
        u = load_universe(self.paths, m, self.policy)
        rep["scope"] = {"n_symbols": len(u.in_scope), "symbols": u.in_scope,
                        "by_class": {k: sorted(s for s in u.in_scope if u.classes[s] == k)
                                     for k in sorted(set(u.classes.values()))},
                        "excluded": dict(sorted(u.excluded.items())),
                        "rule": ("universe_policy.may_hypothesise(symbol, family) and not "
                                 "universe_policy.is_exotic_symbol(symbol); class methods need a "
                                 "peer class of >= MIN_MEMBERS non-exotic members with bars")}
        cells = cell_space(u, m)
        fd, pc = _donation_modules()
        ledger = self.paths.ledger(m.name)
        charged = charged_identities(ledger)
        already_total = sum(1 for c in cells if pc.identity(c.symbol, m.family, c.params)
                            in charged)
        intake, basis = judge_intake(self.paths, m.family)
        bound = cap if cap is not None else max(intake or 0, EMIT_FLOOR)
        rep["bound"] = {"new_cells_per_pass": bound, "judge_intake": intake,
                        "judge_intake_basis": basis, "floor": EMIT_FLOOR}
        rep["cell_space"] = {"total": len(cells), "per_symbol": len(grid(m.family)),
                             "id_rule": "gm_ + sha256(method|symbol|params)[:24]"}
        if not cells:
            rep.update(status="NO_CELLS", cells_charged_total=already_total,
                       why="no in-scope symbol on this host")
            return self.finish(rep)
        state = read_json(self.paths.state(m.name), {}) or {}
        cursor = str(state.get("cursor") or "")
        start = next((i for i, c in enumerate(cells) if c.cid > cursor), 0)
        order = cells[start:] + cells[:start]
        counts = {"scanned": 0, "new": 0, "already_charged": 0, "too_short": 0,
                  "unreadable_bars": 0}
        days_cache: dict[str, int | None] = {}
        rows: list[dict[str, Any]] = []
        last, stop = cursor, "space_walked"
        for c in order:
            if counts["new"] >= bound:
                stop = "bound_reached"
                break
            if time.monotonic() - self.t0 > budget_s:
                stop = "budget_spent"
                break
            counts["scanned"] += 1
            last = c.cid
            if pc.identity(c.symbol, m.family, c.params) in charged:
                counts["already_charged"] += 1
                continue
            if c.symbol not in days_cache:
                days_cache[c.symbol] = self.days(c.symbol)
            nd = days_cache[c.symbol]
            if nd is None:
                counts["unreadable_bars"] += 1
                continue
            if nd < m.min_days:
                counts["too_short"] += 1
                continue
            rows.append(c.row())
            counts["new"] += 1
        donation: dict[str, Any] = {}
        if rows:
            door = self.donate or fd.donate_per_family
            try:
                donation = door(SOURCE, rows, ledger=ledger, dry_run=self.dry_run)
            except Exception as exc:
                rep.update(status="DONATION_FAILED", why=f"{type(exc).__name__}: {exc}"[:300],
                           cells_charged_total=already_total)
                rep["pass"] = {**counts, "stop": stop}
                return self.finish(rep)
        trials = int(donation.get("tests_run_total") or 0)
        newly = len(rows) - int(donation.get("already_charged") or 0) \
            - int(donation.get("incomplete") or 0)
        rep["pass"] = {**counts, "stop": stop, "cursor_from": cursor, "cursor_to": last,
                       "min_days": m.min_days,
                       "rule": "every donated cell is charged as a trial once through "
                               "family_donation's per-family tests_run; a cell in the ledger is "
                               "never re-offered and never charged twice"}
        rep["donation"] = {k: donation.get(k) for k in
                           ("offered", "already_charged", "incomplete", "tests_run_by_family",
                            "tests_run_total", "donated_by_family", "donated_total",
                            "refused_wrong_lane", "files")} if donation else {}
        rep["tests_run"] = trials
        rep["cells_proposed"] = max(0, newly)
        rep["cells_charged_total"] = already_total + (0 if self.dry_run else max(0, newly))
        if rows and trials < newly:
            rep.update(status="UNDER_CHARGED", why=f"{trials} trials for {newly} cells")
            return self.finish(rep)
        if not self.dry_run:
            atomic_json(self.paths.state(m.name), {"cursor": last, "at": now_iso(),
                                                   "space": len(cells)})
        rep["status"] = "RAN"
        return self.finish(rep)

    def finish(self, rep: dict[str, Any]) -> dict[str, Any]:
        rep["seconds"] = round(time.monotonic() - self.t0, 1)
        rep["live_yield"] = (f"{UNMEASURED} until the gauntlet judges the donated cells on the "
                             "box's own bars")
        if not self.dry_run:
            atomic_json(self.paths.report(self.m), rep)
        elif self.out is not None:
            atomic_json(self.out, rep)
        return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--method", choices=[*METHODS, "all"], default="all")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="count; never donate, never write the live report, state or ledger")
    ap.add_argument("--out", type=Path, default=None, help="with --dry-run: the report path")
    a = ap.parse_args(argv)
    if a.out is not None and not a.dry_run:
        ap.error("--out is for --dry-run only")
    budget = float(a.budget_s)
    env = os.environ.get("QUANT_LEG_BUDGET_S")
    if env:
        with contextlib.suppress(ValueError):
            budget = min(budget, max(30.0, float(env) - 60.0))
    names = list(METHODS) if a.method == "all" else [a.method]
    worst = 0
    reports = {}
    for name in names:
        out = None
        if a.out is not None:
            out = a.out if len(names) == 1 else a.out.with_name(f"{a.out.stem}_{name}.json")
        rep = Producer(name, dry_run=a.dry_run, out=out).run(budget / len(names), a.cap)
        reports[name] = rep
        p = rep.get("pass") or {}
        print(f"global_methods[{name}]: {rep.get('status')} in {rep.get('seconds')}s -- space "
              f"{(rep.get('cell_space') or {}).get('total')}; new {p.get('new')} / already "
              f"{p.get('already_charged')} / too short {p.get('too_short')} / unreadable "
              f"{p.get('unreadable_bars')}; trials charged {rep.get('tests_run')}"
              f"{'; DRY RUN' if a.dry_run else ''}", flush=True)
        if rep.get("status") not in ("RAN", "NO_CELLS"):
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
