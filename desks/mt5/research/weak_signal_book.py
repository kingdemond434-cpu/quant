"""Hourly box job: pool EVERY judged cell and every live sleeve into one weak-signal book.

    eligible = every cell the gauntlet has ever judged (lifetime verdict index, seen-cells file,
               latest sweep) + every live sleeve with realised fills
    series   = each cell's daily net-R at 1x and 3x cost, taken from the gauntlet's own cache
               when it holds it, otherwise rebuilt with the gauntlet's own `_warm_one`, under a
               time budget, never-ingested cells first and then oldest first
    book     = libs.portfolio.weak_signal_book.judge: purged walk-forward weights, DSR on the
               lifetime trial union plus every recipe this book has run, 3x-cost gate, must beat
               its best single member, E[log W] sizing inside half the firm rails
    coverage = eligible versus ingested, by cause. Any gap is RED.

NEW SIGNALS JOIN AUTOMATICALLY. Eligibility is read from the judge's own lifetime index every
pass, so a cell judged for the first time this hour is eligible next pass and is built first.
Nothing is selected by verdict: a rejected cell and a certified cell enter the pool the same way,
and the training block alone decides its weight.

PROPOSES ONLY. Writes `reports/WEAK_SIGNAL_BOOK.json` and appends `reports/weak_signal_book/
trials.jsonl`. It never touches a live ledger, sleeve, certificate or gateway file.

Run: python desks/mt5/research/weak_signal_book.py [--budget-s 1200]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import weak_signal_book as wsb  # noqa: E402

REPORTS = _DESK / "reports"
DATA = _DESK / "data"
REPORT = REPORTS / "WEAK_SIGNAL_BOOK.json"
STORE = REPORTS / "weak_signal_book"
SERIES = STORE / "series"
STORE_INDEX = STORE / "index.json"
TRIALS = STORE / "trials.jsonl"
GATE_INDEX = DATA / "hypotheses" / "gate_verdict_index.json"
SEEN_CELLS = DATA / "hypotheses" / "gauntlet_seen_cells.json"
LATEST = REPORTS / "universal_gates_external.json"
DOCKET = DATA / "hypotheses" / "external_survivors.json"
GRAPH = DATA / "hypothesis_graph.jsonl"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
#: Further stores that carry (symbol, family, params) rows; walked generically, any depth.
EXTRA_PARAM_SOURCES = tuple(DATA / "hypotheses" / n for n in (
    "requeue_named.json", "external_backtest_results.json", "test_grid.json",
    "miner_candidates.json", "anomaly_candidates.json", "deepened_candidates.json",
    "queued_external.json", "latest_external.json", "orthogonal_candidates.json"))
#: sha256("{}")[:16]: a cell whose digest is this was minted with EMPTY params.
EMPTY_PARAMS_DIGEST = "44136fa355b3678a"
EXPERIMENT_LEDGER = REPORTS / "EXPERIMENT_LEDGER.json"
MAX_AGE_DAYS = 7           # a stored series older than this is rebuilt (rotation, not a gap)
CACHE_LOOKBACK_DAYS = 21   # how far back to look for a gauntlet-cached series of the same cell
#: A cell the judge itself could not give a series is refused BY RULE (counted, not missing).
REFUSED_GATES = {"symbol_eligibility": "symbol_untradeable", "observations": "judge_unmeasured"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------- eligibility

def eligible_cells() -> tuple[dict[str, dict], dict[str, str]]:
    """cell id -> {state}, and the source counts. Union of every record of a judged cell."""
    cells: dict[str, dict] = {}
    sources: dict[str, str] = {}
    idx = _read_json(GATE_INDEX, {})
    if isinstance(idx, dict):
        for cid, key in idx.items():
            gate, _, passed = str(key).partition("|")
            cells.setdefault(cid, {})["terminal_gate"] = gate
            cells[cid]["passed"] = passed == "1"
        sources["gate_verdict_index"] = f"{len(idx)} cells"
    else:
        sources["gate_verdict_index"] = "UNREADABLE"
    seen = _read_json(SEEN_CELLS, {})
    if isinstance(seen, dict):
        for cid in seen:
            cells.setdefault(cid, {})
        sources["gauntlet_seen_cells"] = f"{len(seen)} cells"
    latest = _read_json(LATEST, {})
    n_latest = 0
    for v in (latest.get("verdicts") or []) if isinstance(latest, dict) else []:
        if not isinstance(v, dict) or not v.get("cell"):
            continue
        n_latest += 1
        row = cells.setdefault(v["cell"], {})
        row["terminal_gate"] = v.get("terminal_gate") or row.get("terminal_gate")
        row["passed"] = bool(v.get("passed"))
        row["unmeasured"] = bool(v.get("unmeasured"))
        if isinstance(v.get("params"), dict):
            row["params"] = v["params"]
            row["sym"], row["family"] = v.get("sym"), v.get("family")
        stages = v.get("stages") or {}
        if "symbol_eligibility" in stages and not stages["symbol_eligibility"].get("passed"):
            row["terminal_gate"] = "symbol_eligibility"
    sources["latest_sweep"] = f"{n_latest} verdicts"
    return cells, sources


def params_map(wanted: set[str]) -> dict[str, dict]:
    """cell id -> {sym, family, params, source}, from every store that kept params.

    A verdict names a cell by a one-way digest of its params, so the params must come from the
    row that MINTED the cell: the docket and the append-only hypothesis graph. Both are scanned
    with the judge's own identity function, so the join is exact.
    """
    from research.frontier_identity import cell_id
    out: dict[str, dict] = {}

    def take(sym, family, params, source):
        if not sym or not family or not isinstance(params, dict):
            return
        try:
            key = cell_id({"sym": sym, "family": family, "params": params})
        except Exception:
            return
        if key in wanted and key not in out:
            out[key] = {"sym": sym, "family": family, "params": params, "source": source}

    docket = _read_json(DOCKET, [])
    for r in docket if isinstance(docket, list) else []:
        if isinstance(r, dict):
            take(r.get("symbol") or r.get("sym"), r.get("family"), r.get("params"),
                 str(r.get("source") or "docket"))
    try:
        with GRAPH.open(encoding="utf-8") as fh:
            for line in fh:
                if len(out) >= len(wanted):
                    break
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                take(r.get("symbol"), r.get("family"), r.get("params"),
                     str(r.get("source") or "hypothesis_graph"))
    except OSError:
        pass

    def walk(o, src: str) -> None:
        if isinstance(o, dict):
            take(o.get("symbol") or o.get("sym"), o.get("family"), o.get("params"),
                 str(o.get("source") or src))
            for v in o.values():
                if isinstance(v, dict | list):
                    walk(v, src)
        elif isinstance(o, list):
            for v in o:
                walk(v, src)

    for path in EXTRA_PARAM_SOURCES:
        if len(out) >= len(wanted):
            break
        doc = _read_json(path, None)
        if doc is not None:
            walk(doc, path.stem)
    # A digest of "{}" names its params exactly.
    for key in wanted - set(out):
        head, _, digest = key.rpartition(".p=")
        if digest == EMPTY_PARAMS_DIGEST and "." in head:
            sym_tf, family = head.split(".", 1)
            sym, _, tf = sym_tf.partition("@")
            params = {"timeframe": tf} if tf else {}
            try:
                if cell_id({"sym": sym, "family": family, "params": params}) == key:
                    out[key] = {"sym": sym, "family": family, "params": params,
                                "source": "empty_params"}
                elif cell_id({"sym": sym, "family": family, "params": {}}) == key:
                    out[key] = {"sym": sym, "family": family, "params": {},
                                "source": "empty_params"}
            except Exception:
                continue
    return out


# ---------------------------------------------------------------- series store

def _fname(cid: str) -> Path:
    return SERIES / f"{hashlib.sha1(cid.encode()).hexdigest()}.npz"


def store_save(cid: str, s1: pd.Series, s3: pd.Series | None, origin: str) -> None:
    SERIES.mkdir(parents=True, exist_ok=True)
    f = _fname(cid)
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    d1 = pd.to_datetime(s1.index)
    with open(tmp, "wb") as fh:
        np.savez_compressed(
            fh, dates=d1.astype("int64").to_numpy(), v1=s1.to_numpy(float),
            v3=(s3.reindex(s1.index).fillna(0.0).to_numpy(float) if s3 is not None
                else np.full(len(s1), np.nan)))
    os.replace(tmp, f)
    _INDEX[cid] = {"built_utc": _now(), "origin": origin, "days": len(s1)}


def store_load(cid: str) -> tuple[pd.Series, pd.Series | None] | None:
    try:
        z = np.load(_fname(cid), allow_pickle=False)
    except (OSError, ValueError):
        return None
    idx = pd.to_datetime(z["dates"])
    s1 = pd.Series(z["v1"], index=idx)
    v3 = z["v3"]
    s3 = None if np.isnan(v3).all() else pd.Series(np.nan_to_num(v3), index=idx)
    return s1, s3


_INDEX: dict[str, dict] = {}


def _stale(cid: str, now: datetime) -> bool:
    row = _INDEX.get(cid)
    if not row or not _fname(cid).exists():
        return True
    try:
        return now - datetime.fromisoformat(row["built_utc"]) > timedelta(days=MAX_AGE_DAYS)
    except (KeyError, ValueError):
        return True


# ---------------------------------------------------------------- building

def _gauntlet():
    import external_gauntlet as eg  # the judge's own builders; read-only use
    return eg


def from_gauntlet_cache(eg, spec: dict, today: date) -> tuple[pd.Series, pd.Series] | None:
    tf = eg.timeframe_of(spec["params"], spec["family"])
    for back in range(CACHE_LOOKBACK_DAYS):
        day = str(today - timedelta(days=back))
        pair = eg.cache_load(eg._cache_key(spec["sym"], spec["family"], spec["params"], day, tf))
        if pair is not None:
            return pair
    return None


def build_series(eg, spec: dict, meta: dict) -> tuple[tuple[pd.Series, pd.Series] | None, str]:
    """The gauntlet's own fresh path (`_warm_one`), which also warms the judge's cache."""
    out = eg._warm_one({"sym": spec["sym"], "family": spec["family"],
                        "params": spec["params"]}, meta)
    status = str(out.get("status") or "ERROR")
    if status in ("HIT", "WARMED") and out.get("ckey"):
        pair = eg.cache_load(out["ckey"])
        if pair is not None:
            return pair, status
    return None, status if status not in ("HIT", "WARMED") else "CACHE_UNREADABLE"


# ---------------------------------------------------------------- live sleeves

def live_sleeve_series() -> dict[str, pd.Series] | None:
    """Realised daily R per live sleeve, from fills. Real fills already carry real costs."""
    per: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    try:
        with LIVE_LEDGER.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                name = str(r.get("sleeve") or "")
                if not name or name[0] in "[#" or r.get("account_kind") not in (None, "live"):
                    continue
                risk = abs(float(r.get("risk_quote") or 0.0))
                pl = float(r.get("pl_quote") or 0.0) + float(r.get("commission") or 0.0) \
                    + float(r.get("swap") or 0.0)
                rm = float(r.get("r_multiple") or 0.0)
                val = pl / risk if risk > 0 else rm
                if not val:
                    continue
                day = str(r.get("time") or "")[:10]
                if day:
                    per[name][day] += val
    except OSError:
        return None
    return {f"LIVE:{k}": pd.Series(v, index=pd.to_datetime(list(v))).sort_index()
            for k, v in per.items() if v}


# ---------------------------------------------------------------- trials

def lifetime_trials() -> tuple[int | None, str]:
    doc = _read_json(EXPERIMENT_LEDGER, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("lifetime_trials"), int | float):
        return None, ("EXPERIMENT_LEDGER.json unreadable or carries no lifetime_trials: "
                      "DSR fails closed")
    return int(doc["lifetime_trials"]), f"lifetime union {int(doc['lifetime_trials'])}"


def trial_rows() -> list[dict]:
    rows = []
    try:
        with TRIALS.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


# ---------------------------------------------------------------- run

def run(budget_s: float = 1200.0, cfg: wsb.BookConfig | None = None) -> dict:
    t0 = time.time()
    cfg = cfg or wsb.BookConfig()
    now = datetime.now(UTC)
    _INDEX.clear()
    _INDEX.update(_read_json(STORE_INDEX, {}) or {})
    cells, sources = eligible_cells()
    cov = wsb.Coverage()
    need = {c for c, st in cells.items() if not st.get("params")}
    pm = params_map(need) if need else {}
    for c, st in cells.items():
        if st.get("params"):
            pm.setdefault(c, {"sym": st["sym"], "family": st["family"], "params": st["params"],
                              "source": "latest_sweep"})

    # Eligibility and refusals. Every cell lands in exactly one bucket.
    todo: list[str] = []
    unrec_family: Counter = Counter()
    for c, st in cells.items():
        cov.eligible += 1
        gate = st.get("terminal_gate")
        if gate in REFUSED_GATES or st.get("unmeasured"):
            cov.refuse(REFUSED_GATES.get(gate, "judge_unmeasured"))
            continue
        if c not in pm:
            cov.gap("params_unrecoverable", c)
            unrec_family[c.split(".")[1] if c.count(".") >= 2 else "?"] += 1
            continue
        todo.append(c)
    # Rotation: never-ingested first, then oldest stored.
    todo.sort(key=lambda c: (_INDEX.get(c, {}).get("built_utc") or ""))
    refreshed, built_status = 0, Counter()
    eg = meta = None
    try:
        eg = _gauntlet()
        meta = json.loads((eg.UNI / "universe.json").read_text("utf-8"))
    except Exception as exc:
        built_status[f"gauntlet_import: {type(exc).__name__}"] += 1
    deadline = t0 + budget_s
    for c in todo:
        if not _stale(c, now):
            continue
        if eg is None or time.time() > deadline:
            break
        spec = pm[c]
        try:
            pair = from_gauntlet_cache(eg, spec, now.date())
            origin = "gauntlet_cache"
            if pair is None:
                pair, status = build_series(eg, spec, meta)
                origin = f"built:{status}"
                built_status[status] += 1
            if pair is not None and pair[0] is not None and len(pair[0]):
                store_save(c, pair[0], pair[1], origin)
                refreshed += 1
            elif pair is not None:
                built_status["empty_series"] += 1
                _INDEX[c] = {"built_utc": _now(), "origin": "empty", "days": 0}
        except Exception as exc:
            built_status[f"{type(exc).__name__}: {str(exc)[:60]}"] += 1
    STORE.mkdir(parents=True, exist_ok=True)
    STORE_INDEX.write_text(json.dumps(_INDEX, sort_keys=True), encoding="utf-8")

    # Load the pool and close the coverage books.
    series: dict[str, tuple[pd.Series, pd.Series | None]] = {}
    stale = 0
    for c in todo:
        row = _INDEX.get(c)
        if row and row.get("origin") == "empty":
            cov.refuse("series_has_no_trades")
            continue
        got = store_load(c) if row else None
        if got is None:
            cov.gap("not_yet_built" if not row else "store_unreadable", c)
            continue
        series[c] = got
        cov.ingested += 1
        stale += int(_stale(c, now))
    live = live_sleeve_series()
    if live is None:
        cov.eligible += 1
        cov.gap("live_ledger_unreadable", str(LIVE_LEDGER.name))
        live = {}
    for name, s in live.items():
        cov.eligible += 1
        cov.ingested += 1
        series[name] = (s, None)

    lt, lt_basis = lifetime_trials()
    rows = trial_rows()
    recipe = cfg.digest()
    n_recipes = wsb.recipe_trials([*rows, {"recipe": recipe}])
    n_trials = (lt + n_recipes) if lt is not None else None
    pool = wsb.build_pool(series)
    book = wsb.judge(pool, cfg, n_trials=n_trials) if pool.ids else {
        "passed": False, "why": "empty pool", "recipe": recipe}
    by_source = Counter(pm[c]["source"].split(":")[0] for c in series if c in pm)
    doc = {
        "generated_utc": _now(), "elapsed_s": round(time.time() - t0, 1),
        "coverage": {**cov.as_dict(), "stale_over_max_age": stale,
                     "refreshed_this_pass": refreshed,
                     "build_status": dict(built_status.most_common(20)),
                     "eligibility_sources": sources,
                     "ingested_by_producer": dict(by_source.most_common(50)),
                     "params_unrecoverable_by_family": dict(unrec_family.most_common(30)),
                     "live_sleeves": sorted(live)},
        "trials": {"lifetime": lt, "lifetime_basis": lt_basis, "book_recipes": n_recipes,
                   "charged": n_trials},
        "pool": {"members": len(pool.ids), "days": len(pool.dates),
                 "first": str(pool.dates[0].date()) if len(pool.dates) else None,
                 "last": str(pool.dates[-1].date()) if len(pool.dates) else None},
        "book": book,
        "status": ("PROPOSE" if book.get("passed") else "NO_BOOK"),
        "authority": "proposes only; nothing here arms or sizes a live order",
    }
    REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    with TRIALS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": doc["generated_utc"], "recipe": recipe,
                             "members": len(pool.ids), "passed": bool(book.get("passed")),
                             "oos_sr_daily": (book.get("oos") or {}).get("sr_daily")}) + "\n")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-s", type=float, default=1200.0)
    a = ap.parse_args()
    d = run(budget_s=a.budget_s)
    c, b = d["coverage"], d["book"]
    print(f"WEAK-SIGNAL BOOK  coverage {c['status']} eligible={c['eligible']} "
          f"ingested={c['ingested']} missing={c['missing']} "
          f"refused={sum(c['refused_by_rule'].values())}"
          f"  pool={d['pool']['members']}  status={d['status']}")
    if b.get("gates"):
        print("  gates: " + ", ".join(f"{k}={'ok' if v['passed'] else 'FAIL'}"
                                      for k, v in b["gates"].items()))
        print(f"  OOS sr_annual={b['oos']['sr_annual']} lambda_armed={b['sizing']['lambda_armed']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
