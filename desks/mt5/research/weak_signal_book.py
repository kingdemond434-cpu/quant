"""Hourly box job: pool EVERY judged cell and every live sleeve into one weak-signal book.

    eligible = every cell the gauntlet has ever judged (lifetime verdict index, seen-cells file,
               latest sweep) + every live sleeve with realised fills
    series   = each cell's daily net-R at 1x and 3x cost, taken from the gauntlet's own cache
               when it holds it, otherwise rebuilt with the gauntlet's own `_warm_one`, under a
               time budget, never-ingested cells first and then oldest first
    book     = libs.research.weak_signal_book.judge: purged walk-forward weights, DSR on the
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

# Research-pool citizen: never more than two BLAS threads, so the leg cannot spill onto the
# judge's reserved cores (judge-reserved-cores) through a numpy thread pool.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import UTC, date, datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import weak_signal_book as wsb  # noqa: E402

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
#: ONE FILE FOR THE HOURLY PASS, published to the branch by sync_shadow_to_git.ps1.
COVERAGE_OUT = REPORTS / "COMBINER_COVERAGE.json"
GAPS_OUT = STORE / "COMBINER_GAPS.jsonl"          # the full per-signal list (box only)
FIRST_SEEN = STORE / "first_seen.json"
PRODUCERS_SEEN = STORE / "producers_seen.json"
#: AUTO-ENROLMENT DOOR for anything that is not a gauntlet cell (class books, external sleeves):
#: drop one JSON per signal here and it is eligible on the next pass, no code change.
#:   {"id": str, "source": str, "validity": "passed"|"failed", "evidence": str,
#:    "daily_r": {"YYYY-MM-DD": R}, "daily_r_3x": {"YYYY-MM-DD": R}}
COMBINER_INPUTS = DATA / "combiner_inputs"
DECAY_LIVE = DATA / "decay_live.json"
DECAY_ZERO = DATA / "DECAY_ZERO.json"
FEATURE_DRIFT = REPORTS / "FEATURE_DRIFT.json"
#: The principal's DECAY RULING (11-03): gold_asia is exempt from decay retirement until a LIVE
#: replacement on XAUUSD exists. A data/DECAY_EXEMPT.json list, when present, replaces this.
DECAY_EXEMPT_DEFAULT = frozenset({"gold_asia"})
DECAY_EXEMPT = DATA / "DECAY_EXEMPT.json"
RETIRE_VERDICTS = frozenset({"RETIRE", "RETIRED", "DECAYED", "ZERO", "KILL", "KILLED"})
RED_AFTER_HOURS = 24.0
MAX_AGE_DAYS = 7           # a stored series older than this is rebuilt (rotation, not a gap)
CACHE_LOOKBACK_DAYS = 21   # how far back to look for a gauntlet-cached series of the same cell
#: A cell the judge itself could not give a series is refused BY RULE (counted, not missing).
REFUSED_GATES = {"symbol_eligibility": "symbol_untradeable", "observations": "judge_unmeasured"}
GATE_SPEC = _DESK / "policy" / "gate_spec.yaml"
FAILED_GATES = STORE / "failed_gates.json"
#: Judge stages gate_spec.yaml does not classify. swap_cost is a cost-model failure: VALIDITY.
EXTRA_VALIDITY = frozenset({"swap_cost"})


def gate_classes() -> tuple[frozenset[str], frozenset[str]]:
    """(VALIDITY, POWER) from the judge's own registry, never a hand-kept copy.

    VALIDITY failures (a corrupt series: leakage, overfit selection, cost or lockbox failure)
    are REFUSED by rule and never pooled, because their contamination persists into every test
    block and the training fit would favour them (audit HOLD 11-03). Only POWER failures -- real
    effects too weak to stand alone -- enter the pool. An unreadable registry refuses everything.
    """
    try:
        import yaml
        doc = yaml.safe_load(GATE_SPEC.read_text("utf-8")) or {}
        cls = doc.get("gate_classifications") or {}
        val = frozenset(str(g) for g in cls.get("validity") or ())
        pwr = frozenset(str(g) for g in cls.get("power") or ())
    except Exception:
        return frozenset(), frozenset()
    if not val or not pwr:
        return frozenset(), frozenset()
    return val | EXTRA_VALIDITY, pwr


def admission(cell: str, st: dict, failed: list[str] | None,
              validity: frozenset[str], power: frozenset[str]) -> tuple[str, str]:
    """('admit'|'refuse'|'gap', cause). Fail closed on anything unclassified or unrecorded."""
    gate = st.get("terminal_gate")
    if gate in REFUSED_GATES or st.get("unmeasured"):
        return "refuse", REFUSED_GATES.get(gate, "judge_unmeasured")
    if not validity:
        return "gap", "gate_registry_unreadable"
    if st.get("passed") or gate == "PASSED":
        return "admit", ""
    if gate in validity:
        return "refuse", "validity_failed"
    if failed is None:
        # Only the TERMINAL gate is on record, and the judge stops recording at the first
        # failure: whether a later validity gate also failed is unknown. Not pooled until a
        # sweep records the full list; a gap, because a re-judge closes it.
        return "gap", "validity_unrecorded"
    unknown = [g for g in failed if g not in validity and g not in power]
    if unknown:
        return "gap", f"unclassified_gate:{unknown[0]}"
    if any(g in validity for g in failed):
        return "refuse", "validity_failed"
    return "admit", ""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    """tmp + replace: a reader never sees a torn file (a torn record darkens the whole book)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


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
        if isinstance(v.get("failed_gates"), list):
            row["failed_gates"] = [str(g) for g in v["failed_gates"]]
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

def external_inputs(cov) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Every file in combiner_inputs/ is eligible. Admitted only with attested validity and a
    real 3x arm, so an external input can neither smuggle in a corrupt series nor make the cost
    gate vacuous."""
    out: dict[str, tuple[pd.Series, pd.Series]] = {}
    for f in sorted(COMBINER_INPUTS.glob("*.json")) if COMBINER_INPUTS.is_dir() else []:
        doc = _read_json(f, None)
        cid = f"EXT:{(doc or {}).get('id') or f.stem}" if isinstance(doc, dict) else f"EXT:{f.stem}"
        cov.eligible += 1
        if not isinstance(doc, dict):
            cov.gap("external_unreadable", cid)
            continue
        val = str(doc.get("validity") or "").lower()
        if val == "failed":
            cov.refuse("validity_failed")
            continue
        if val != "passed" or not doc.get("evidence"):
            cov.gap("external_validity_unattested", cid)
            continue
        try:
            s1 = pd.Series(doc["daily_r"], dtype=float)
            s1.index = pd.to_datetime(s1.index)
            s3 = pd.Series(doc.get("daily_r_3x") or {}, dtype=float)
            s3.index = pd.to_datetime(s3.index)
        except (KeyError, TypeError, ValueError):
            cov.gap("external_series_malformed", cid)
            continue
        if not len(s1):
            cov.refuse("series_has_no_trades")
            continue
        if not len(s3):
            cov.gap("external_no_3x_arm", cid)
            continue
        out[cid] = (s1.sort_index(), s3.sort_index())
        cov.ingested += 1
    return out


def decay_retired() -> tuple[set[str], str]:
    """Live sleeve names the decay organs have retired (decay_live verdicts + DECAY_ZERO)."""
    names: set[str] = set()
    doc = _read_json(DECAY_LIVE, None)
    basis = "decay_live.json unreadable" if doc is None else "decay_live.json"
    for k, v in ((doc or {}).get("verdicts") or {}).items():
        verdict = v.get("verdict") if isinstance(v, dict) else v
        if str(verdict or "").upper() in RETIRE_VERDICTS:
            names.add(str(k))
    z = _read_json(DECAY_ZERO, None)
    if isinstance(z, list):
        basis += " + DECAY_ZERO.json"
        names.update(str(k) for k in z)
    elif isinstance(z, dict):
        items = z.get("zeroed", z.get("sleeves"))
        if isinstance(items, list | dict):
            basis += " + DECAY_ZERO.json"
            names.update(str(k) for k in items)
        else:
            basis += " + DECAY_ZERO.json: no zeroed list"
    exempt = _read_json(DECAY_EXEMPT, None)
    exempt_set = (frozenset(str(x) for x in exempt) if isinstance(exempt, list)
                  else DECAY_EXEMPT_DEFAULT)
    held = sorted(names & exempt_set)
    if held:
        basis += f"; exempt by principal ruling, kept: {held}"
    return names - exempt_set, basis


def drift_flags() -> list[str]:
    """Early warning only (Tier-1 gap): reported, never used to zero a member."""
    doc = _read_json(FEATURE_DRIFT, None)
    out: list[str] = []

    def walk(o, key=""):
        if isinstance(o, dict):
            if str(o.get("verdict") or "") == "EDGE_DECAY_CANDIDATE":
                out.append(str(o.get("sleeve") or o.get("name") or o.get("cell") or key))
            for k, v in o.items():
                if isinstance(v, dict | list):
                    walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
    walk(doc)
    return sorted(set(out))


def _retired(live_name: str, retired: set[str]) -> bool:
    # EXACT match only (audit 11-03): a prefix match let "gold_asia" retire "gold_asia_v2".
    # A sleeve whose ledger comment was truncated therefore stays in; that is the safe side.
    n = live_name.removeprefix("LIVE:")
    return n in {r.removeprefix("LIVE:") for r in retired}


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

    # The full failed-gate list survives only one sweep in the judge's report; keep it here.
    failed_rec: dict[str, list[str]] = _read_json(FAILED_GATES, {}) or {}
    for c, st in cells.items():
        if "failed_gates" in st:
            failed_rec[c] = st["failed_gates"]
    STORE.mkdir(parents=True, exist_ok=True)
    _atomic_write(FAILED_GATES, json.dumps(failed_rec, sort_keys=True))
    validity, power = gate_classes()

    # Eligibility and refusals. Every cell lands in exactly one bucket.
    todo: list[str] = []
    unrec_family: Counter = Counter()
    for c, st in cells.items():
        cov.eligible += 1
        verdict, cause = admission(c, st, failed_rec.get(c), validity, power)
        if verdict == "refuse":
            cov.refuse(cause)
            continue
        if verdict == "gap":
            cov.gap(cause, c)
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
    _atomic_write(STORE_INDEX, json.dumps(_INDEX, sort_keys=True))

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
    # LIVE SLEEVES ARE A SEPARATE VARIANT (audit 11-03). Realised R has no 3x arm and is a
    # different measurement from backtest R; the armable book is the cells-only book, and the
    # with-live book is reported beside it, never armed.
    live_series: dict[str, tuple[pd.Series, None]] = {}
    retired, decay_basis = decay_retired()
    retired_members: list[str] = []
    for name, s in live.items():
        cov.eligible += 1
        if _retired(name, retired):
            cov.refuse("retired_for_decay")
            retired_members.append(name)
            continue
        cov.ingested += 1
        live_series[name] = (s, None)
    ext = external_inputs(cov)
    series.update(ext)

    lt, lt_basis = lifetime_trials()
    rows = trial_rows()
    recipe = cfg.digest()
    n_recipes = wsb.recipe_trials([*rows, {"recipe": recipe}])
    n_trials = (lt + n_recipes) if lt is not None else None
    latest_by_recipe: dict[str, float] = {}
    for r in rows:
        if r.get("recipe") and r.get("oos_sr_daily") is not None:
            latest_by_recipe[str(r["recipe"])] = float(r["oos_sr_daily"])
    recipe_srs = list(latest_by_recipe.values())
    pool = wsb.build_pool(series)
    book = wsb.judge(pool, cfg, n_trials=n_trials, recipe_sharpes=recipe_srs) if pool.ids else {
        "passed": False, "why": "empty pool", "recipe": recipe}
    with_live = None
    if live_series and pool.ids:
        lp = wsb.build_pool({**series, **live_series})
        wl = wsb.judge(lp, cfg, n_trials=n_trials, recipe_sharpes=recipe_srs)
        with_live = {"passed_informative": wl["passed"], "gates": wl["gates"], "oos": wl["oos"],
                     "live_weight": round(sum(m["weight"] for m in wl["members"]
                                              if m["cell"].startswith("LIVE:")), 6),
                     "note": "never armed: realised and backtest R on one calendar"}
    by_source = Counter(pm[c]["source"].split(":")[0] for c in series if c in pm)
    coverage_doc = publish_coverage(cov, cells, pm, ext, book, retired_members, decay_basis, now)
    doc = {
        "generated_utc": _now(), "elapsed_s": round(time.time() - t0, 1),
        "coverage": {**cov.as_dict(), "stale_over_max_age": stale,
                     "refreshed_this_pass": refreshed,
                     "build_status": dict(built_status.most_common(20)),
                     "eligibility_sources": sources,
                     "ingested_by_producer": dict(by_source.most_common(50)),
                     "params_unrecoverable_by_family": dict(unrec_family.most_common(30)),
                     "live_sleeves": sorted(live),
                     "gate_classes": {"validity": sorted(validity), "power": sorted(power)}},
        "trials": {"lifetime": lt, "lifetime_basis": lt_basis, "book_recipes": n_recipes,
                   "charged": n_trials},
        "pool": {"members": len(pool.ids), "days": len(pool.dates),
                 "first": str(pool.dates[0].date()) if len(pool.dates) else None,
                 "last": str(pool.dates[-1].date()) if len(pool.dates) else None},
        "book": book,
        "combiner_coverage": str(COVERAGE_OUT.name),
        "book_with_live_sleeves": with_live,
        "status": ("PROPOSE" if book.get("passed") else "NO_BOOK"),
        "authority": "proposes only; nothing here arms or sizes a live order",
    }
    _atomic_write(REPORT, json.dumps(doc, indent=1, default=str))
    with TRIALS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": doc["generated_utc"], "recipe": recipe,
                             "members": len(pool.ids), "passed": bool(book.get("passed")),
                             "oos_sr_daily": (book.get("oos") or {}).get("sr_daily")}) + "\n")
    doc["coverage"]["red_over_24h"] = coverage_doc["red_over_24h"]
    return doc


def publish_coverage(cov, cells: dict, pm: dict, ext: dict, book: dict,
                     retired_members: list[str], decay_basis: str, now: datetime) -> dict:
    """COMBINER_COVERAGE.json: the ONE file the hourly pass reads (item 37).

    Any eligible signal not ingested within RED_AFTER_HOURS of first being seen is RED. New
    producers are found from the eligible cells' own source stamps, so a new producer, cert
    family or idea enrols with no code change the hour its first cell is judged.
    """
    first = _read_json(FIRST_SEEN, {}) or {}
    stamp = now.isoformat(timespec="seconds")
    for c in list(cells) + list(ext):
        first.setdefault(c, stamp)
    for cid, _ in cov.missing:
        first.setdefault(cid, stamp)
    _atomic_write(FIRST_SEEN, json.dumps(first, sort_keys=True))
    red = []
    rows = []
    for cid, cause in cov.missing:
        try:
            age: float | str = round(
                (now - datetime.fromisoformat(first[cid])).total_seconds() / 3600, 1)
        except (KeyError, TypeError, ValueError):
            age = "UNMEASURED"           # an unreadable age is never read as young (L1.28a)
        row = {"signal": cid, "reason": cause, "first_seen_utc": first.get(cid),
               "age_hours": age}
        rows.append(row)
        if age == "UNMEASURED" or float(age) > RED_AFTER_HOURS:
            red.append(row)
    _atomic_write(GAPS_OUT, "".join(json.dumps(r) + "\n" for r in rows))
    seen_prod = set(_read_json(PRODUCERS_SEEN, []) or [])
    prod_now = Counter(str(v.get("source") or "?").split(":")[0] for v in pm.values())
    prod_now.update(str(c).split(":")[0] + ":external" for c in ext)
    new_prod = {p: n for p, n in prod_now.items() if p not in seen_prod}
    _atomic_write(PRODUCERS_SEEN, json.dumps(sorted(seen_prod | set(prod_now))))
    cd = cov.as_dict()
    b = book.get("breadth") or {}
    out = {
        "generated_utc": stamp,
        "status": cd["status"],
        "red_over_24h": len(red),
        "rule": f"every eligible signal is ingested, refused by a named rule, or listed here with "
                f"its reason; one not ingested {RED_AFTER_HOURS:.0f}h after first seen is RED",
        "eligible": cd["eligible"], "ingested": cd["ingested"], "missing": cd["missing"],
        "missing_by_cause": cd["missing_by_cause"], "refused_by_rule": cd["refused_by_rule"],
        "red_sample": red[:500],
        "not_ingested_sample": rows[:200],
        "not_ingested_full_list": (GAPS_OUT.relative_to(_DESK).as_posix()
                                   if GAPS_OUT.is_relative_to(_DESK) else str(GAPS_OUT)),
        "breadth_net_of_cost": {k: b.get(k) for k in ("n_active", "eff_n_weights",
                                                       "eff_n_independent")},
        "crisis_correlation": b.get("crisis"),
        "retired_for_decay": {"members": sorted(retired_members), "basis": decay_basis},
        "drift_early_warning": drift_flags(),
        "auto_enrolled_new_producers": new_prod,
        "external_inputs_ingested": sorted(ext),
        "book": {"passed": bool(book.get("passed")),
                 "gates": {k: v.get("passed") for k, v in (book.get("gates") or {}).items()},
                 "oos_sr_annual": (book.get("oos") or {}).get("sr_annual"),
                 "lambda_armed": (book.get("sizing") or {}).get("lambda_armed")},
    }
    _atomic_write(COVERAGE_OUT, json.dumps(out, indent=1, default=str))
    return out


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
