#!/usr/bin/env python3
"""THE STATE-ENGINE ENSEMBLE ORGAN: publish it, prove it against the plain input, re-test the
near-misses inside it.

    python desks/mt5/research/state_ensemble_run.py            # hourly leg: all three, self-paced
    python desks/mt5/research/state_ensemble_run.py --only state|contract|nearmiss

THREE PASSES, ONE LEG (`state_ensemble` in hourly_cycle), EACH ON ITS OWN CADENCE:

  state     every pass. `libs.regime.ensemble` on every hypothesis-lane symbol with H1 bars ->
            reports/STATE_ENSEMBLE.json: per symbol the world state now (vol tier x trend/range x
            agree/split), tomorrow's tier distribution, each engine's weight, and the WALK-FORWARD
            CALIBRATION of the fused forecast against the PLAIN input (the trailing base rate) --
            log score, Brier and high-tier ECE on identical days, 90% block-bootstrap interval.
            On XAUUSD it is also scored against the allocator's CURRENT input, the gold HMM, refit
            on the same schedule. A symbol whose newest completed day has not moved is carried
            from the last pass rather than refitted: bars change once a day, the leg runs hourly.
  contract  weekly (CONTRACT_EVERY_H). The allocation half of the proof, built on
            `regime_allocation_contract`'s own walk-forward, books and solver -- not a copy of
            them: geo (no regime), geo_hmm (the live recipe) and geo_ensemble (the ensemble's gold
            states conditioning the worlds), re-solved every 21 days on the trailing 750, held on
            the next 21 nobody has seen. reports/STATE_ENSEMBLE_CONTRACT.json.
  nearmiss  daily (NEARMISS_EVERY_H). Cells the canonical gauntlet judged and NARROWLY failed
            (`alpha_recombination.near_survivor`: died on the last gate, or deflated Sharpe within
            20% of the bar) are re-tested inside each ensemble regime as family `regime_split`
            with `labeler="ensemble"`, killed by the regime-split miner's purged walk-forward, and
            the survivors donated through `proposer_common.donate` -- the one door to the ten
            gates, which charge their own lifetime trials. reports/STATE_ENSEMBLE_NEARMISS.json.

TRIAL COUNTS, STATED BECAUSE THE PRINCIPAL ASKED FOR THEM TO BE HONEST AND NOT INFLATED. Each
(near-miss cell, regime bucket) is one trial, charged ONCE over a lifetime union
(data/state_ensemble_nearmiss_charged.json): a re-screen of a charged cell costs nothing new, a
first screen is charged whether or not anything survives -- on the donation file's `tests_run`
when the pass donates, on data/null_pass_trials.jsonl when it does not (one or the other, never
both, which is how `libs.research.experiment_ledger` counts every proposer). Deflation charges
every row the WHOLE union, never the pass. Nothing pads the count and nothing is excused from it.

WHAT IT DOES NOT DO. It sizes nothing and is read by no money-path file. `promotion.admits` turns
true only when BOTH halves win on the desk's own sleeves (calibration vs plain AND vs the HMM on
gold, and the allocation contract on the box's daily-R matrix). What the allocator owner wires
then is in `promotion.wiring` -- the reader is `pf_allocator.regime_state`, a money-path file this
organ never edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import control_room as cr  # noqa: E402
from libs.regime import ensemble as ens  # noqa: E402

SCHEMA = "state_ensemble/1"
REPORTS = DESK / "reports"
OUT = REPORTS / "STATE_ENSEMBLE.json"
CONTRACT = REPORTS / "STATE_ENSEMBLE_CONTRACT.json"
NEARMISS = REPORTS / "STATE_ENSEMBLE_NEARMISS.json"
GATES_EXTERNAL = REPORTS / "universal_gates_external.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
CHARGED = DESK / "data" / "state_ensemble_nearmiss_charged.json"
NULL_TRIALS = DESK / "data" / "null_pass_trials.jsonl"
#: Per-day log-score differences of the symbols carried between passes, so the pooled verdict
#: covers every symbol without refitting the ones whose newest day has not moved. Rewritten only
#: on a pass that refitted something.
CACHE = DESK / "data" / "state_ensemble_cache.json"
SOURCE = "state_ensemble_nearmiss"
FAMILY = "regime_split"
CONTRACT_EVERY_H = 7 * 24.0
NEARMISS_EVERY_H = 24.0
STATE_BUDGET_S = 420.0
CONTRACT_BUDGET_S = 900.0
NEARMISS_BUDGET_S = 600.0
INCUMBENT_SYMBOL = "XAUUSD"
#: The incumbent's world-probability rails (`regime_allocation_contract.hmm_conditioning`, itself
#: the live `pf_allocator.regime_state` recipe), applied to the ensemble identically so the two
#: arms differ ONLY in where the state comes from.
REGIME_MIN_SHARE, REGIME_MAX_SHARE = 0.08, 0.60
HEADLINE = ("geo_ensemble", "geo_hmm")
VOLS = ("low", "mid", "high")
TRENDS = ("trend", "range")
MAX_NEAR_CELLS = 400
#: Measured headroom each heavy pass needs before it starts (psutil, on the host it runs on). A
#: pass that cannot get it STANDS DOWN and says so -- UNMEASURED, never a silent skip.
NEED_MB = {"state": 600.0, "contract": 1500.0, "nearmiss": 1200.0}
UNMEASURED = "UNMEASURED"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def memory() -> dict[str, float]:
    """MEASURED, never assumed (CLAUDE.md): this host's total and available physical memory."""
    import psutil
    vm = psutil.virtual_memory()
    return {"total_mb": round(vm.total / 2 ** 20, 1),
            "available_mb": round(vm.available / 2 ** 20, 1)}


def _headroom(kind: str) -> dict[str, Any] | None:
    mem = memory()
    if mem["available_mb"] < NEED_MB[kind]:
        return {"status": UNMEASURED, "stood_down": True, "memory": mem,
                "why": f"{kind} needs ~{NEED_MB[kind]:.0f} MB and {mem['available_mb']:.0f} MB is "
                       "available on this host now; the pass re-tries next hour"}
    return None


def _age_h(path: Path, key: str = "generated_at") -> float | None:
    doc = _read(path, {})
    try:
        at = datetime.fromisoformat(str(doc.get(key)))
    except (TypeError, ValueError, AttributeError):
        return None
    return (_now() - at).total_seconds() / 3600.0


# ======================================================================== 1. the state pass
def lane_symbols() -> list[str]:
    """Every symbol with H1 bars that the two-lane mandate lets a `regime_split` cell mint on."""
    have: set[str] = set()
    for d in cr.BAR_DIRS:
        if d.exists():
            have |= {p.stem.removesuffix("_H1") for p in d.glob("*_H1.parquet")}
    try:
        from research.universe_policy import may_hypothesise
    except Exception:                                            # pragma: no cover - desk import
        return sorted(have)
    return sorted(s for s in have if may_hypothesise(s, FAMILY))


def _pub(c: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in c.items() if not k.startswith("_")}


def _pooled(diffs: list[np.ndarray]) -> dict[str, Any]:
    if not diffs:
        return {"status": UNMEASURED, "why": "no symbol was scored"}
    d = np.concatenate(diffs)
    lo, hi = ens._block_ci(d)
    return {"status": "MEASURED", "n_days": int(d.size), "n_symbols": len(diffs),
            "mean_log_score_gain": round(float(d.mean()), 6), "ci90": [round(lo, 6), round(hi, 6)],
            "verdict": "WIN" if lo > 0 else "LOSS" if hi < 0 else "INCONCLUSIVE"}


def symbol_state(sym: str, with_incumbent: bool) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    p = cr.bar_path(sym)
    if p is None:
        return {"status": UNMEASURED, "why": "no H1 bars"}, {}
    daily = cr.daily_frame(pd.read_parquet(p))
    if len(daily) < ens.MIN_FIT + ens.RANK_WIN:
        return {"status": UNMEASURED, "why": f"{len(daily)} complete days; the walk-forward "
                f"needs {ens.MIN_FIT + ens.RANK_WIN}", "last_day": str(daily.index[-1])
                if len(daily) else None}, {}
    res = ens.fit_ensemble(daily["close"])
    sides: dict[str, np.ndarray] = {"fused": res.fused, **res.engines}
    hmm = ens.hmm_tier_forecast(daily["close"]) if with_incumbent else None
    if hmm is not None:
        sides["incumbent_hmm"] = hmm
    keep = ens.common_mask(res.y, *sides.values())
    cal = {k: ens.calibration(v, res.y, keep) for k, v in sides.items()}
    vs_plain = ens.compare(cal["fused"], cal["climatology"])
    row: dict[str, Any] = {
        "status": "MEASURED", "last_day": str(daily.index[-1]), "now": res.current(),
        "recent": [{"day": d, "vol": r.vol, "trend": r.trend, "split": bool(r.split)}
                   for d, r in res.labels.tail(10).iterrows()],
        "calibration": {k: _pub(v) for k, v in cal.items()},
        "fused_vs_plain": vs_plain,
        "engines_unavailable": res.unavailable,
    }
    diffs: dict[str, np.ndarray] = {}
    if cal["fused"].get("status") == "MEASURED" and cal["climatology"].get("status") == "MEASURED":
        diffs["plain"] = cal["fused"]["_ls"] - cal["climatology"]["_ls"]
    if hmm is not None:
        row["fused_vs_incumbent_hmm"] = ens.compare(cal["fused"], cal["incumbent_hmm"])
        if cal["incumbent_hmm"].get("status") == "MEASURED":
            diffs["incumbent"] = cal["fused"]["_ls"] - cal["incumbent_hmm"]["_ls"]
    return row, diffs


def run_state(budget_s: float = STATE_BUDGET_S, symbols: list[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    prev = _read(OUT, {}) or {}
    prev_rows = prev.get("symbols") if isinstance(prev.get("symbols"), dict) else {}
    prev_diff = _read(CACHE, {}) or {}
    todo = symbols or lane_symbols()
    rows: dict[str, Any] = {}
    cache: dict[str, Any] = {}
    plain, incumbent = [], []
    carried = refit = 0
    skipped: dict[str, str] = {}
    stood = _headroom("state")
    for sym in todo:
        p = cr.bar_path(sym)
        last = None
        if p is not None:
            try:
                last = str(cr.daily_frame(pd.read_parquet(p, columns=["close"])).index[-1])
            except Exception:
                last = None
        old = prev_rows.get(sym) if isinstance(prev_rows, dict) else None
        if isinstance(old, dict) and last and old.get("last_day") == last \
                and old.get("status") == "MEASURED" and sym in prev_diff:
            rows[sym], cache[sym] = old, prev_diff[sym]
            carried += 1
        elif stood is not None:
            skipped[sym] = "stood down for memory"
            if isinstance(old, dict):
                rows[sym] = {**old, "stale": True}
            continue
        elif time.monotonic() - t0 > budget_s:
            skipped[sym] = "state budget exhausted; refitted next pass"
            if isinstance(old, dict):
                rows[sym] = {**old, "stale": True}
            continue
        else:
            try:
                row, diffs = symbol_state(sym, with_incumbent=sym == INCUMBENT_SYMBOL)
            except Exception as exc:
                row, diffs = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:240]}, {}
            rows[sym] = row
            cache[sym] = {k: [round(float(x), 6) for x in v] for k, v in diffs.items()}
            refit += 1
        got = cache.get(sym) or {}
        if got.get("plain"):
            plain.append(np.asarray(got["plain"], dtype=float))
        if got.get("incumbent"):
            incumbent.append(np.asarray(got["incumbent"], dtype=float))
    contract = _read(CONTRACT, {}) or {}
    doc = {
        "schema": SCHEMA, "generated_at": _iso(), "memory": memory(),
        "engines": list(ens.available_engines()),
        "engines_unavailable": [e for e in ens.ENGINES if e not in ens.available_engines()],
        "target": ("tomorrow's volatility tier: |r_{t+1}| against the terciles of the trailing "
                   f"{ens.RANK_WIN} days of |r| known at the close of t"),
        "design": {"refit_every_days": ens.REFIT_EVERY, "fit_window_days": ens.FIT_WIN,
                   "first_forecast_day": ens.MIN_FIT, "forget": ens.FORGET,
                   "split_quantile": ens.SPLIT_Q, "trend_z": ens.TREND_Z,
                   "plain_input": "climatology: the trailing year's tier frequencies",
                   "incumbent_input": f"3-state Gaussian HMM on {INCUMBENT_SYMBOL} daily closes, "
                                      "the allocator's regime_state engine, refit on the same "
                                      "schedule with training-window standardisation"},
        "n_symbols": len(todo), "n_measured": sum(1 for r in rows.values()
                                                  if isinstance(r, dict)
                                                  and r.get("status") == "MEASURED"),
        "refit_this_pass": refit, "carried_unchanged_day": carried, "skipped": skipped,
        "stood_down": stood,
        "calibration_vs_plain": _pooled(plain),
        "calibration_vs_incumbent": _pooled(incumbent) if incumbent else
        {"status": UNMEASURED, "why": f"{INCUMBENT_SYMBOL} not scored this pass"},
        "promotion": promotion(_pooled(plain), _pooled(incumbent) if incumbent else {},
                               contract),
        "symbols": rows,
        "runtime_s": round(time.monotonic() - t0, 1),
    }
    if refit:
        _write(CACHE, cache)
    _write(OUT, doc)
    return doc


WIRING = (
    "pf_allocator.regime_state(daily) (money path, allocator owner): when "
    "reports/STATE_ENSEMBLE_CONTRACT.json says admits=true and is under 14 days old, build "
    "WorldConfig.regime_labels / regime_probs from state_ensemble_run.ensemble_conditioning("
    "gold_close, train_days, step) instead of the RegimeEngine block -- same "
    "REGIME_MIN_SHARE/REGIME_MAX_SHARE rails, same regime_min_days -- and fall back to the HMM "
    "when that returns None or the file is stale/absent. One reader, fail-closed to today's "
    "behaviour, no other change: the contract measured exactly that substitution.")


def promotion(plain: dict[str, Any], incumbent: dict[str, Any],
              contract: dict[str, Any]) -> dict[str, Any]:
    """The admission rule, read from the three measurements. An absent one is UNMEASURED."""
    parts = {"calibration_vs_plain": plain.get("verdict", UNMEASURED),
             "calibration_vs_incumbent_hmm": incumbent.get("verdict", UNMEASURED),
             "allocation_contract": contract.get("verdict", UNMEASURED),
             "allocation_universe": (contract.get("design") or {}).get("universe", UNMEASURED)}
    admits = bool(parts["calibration_vs_plain"] == "WIN"
                  and parts["calibration_vs_incumbent_hmm"] == "WIN"
                  and contract.get("admits") is True)
    return {**parts, "admits": admits,
            "rule": ("admits iff the fused forecast beats the plain base rate AND the incumbent "
                     "HMM on pooled walk-forward log score (90% block interval above 0), AND the "
                     "allocation contract is a WIN on the desk's own daily-R matrix"),
            "authority": "NONE from this file: the allocator owner wires the reader",
            "wiring": WIRING}


# ===================================================================== 2. the allocation proof
def ensemble_conditioning(gold: pd.Series, train_days: list[str], step: int,
                          labels: pd.DataFrame | None = None
                          ) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...]] | None:
    """Ensemble world labels on the training days and the forward label probabilities, PIT.

    `labels` may be the ensemble fitted ONCE on the whole series: every label is a function of
    data up to its own day only (`test_state_ensemble.py` truncates and compares), so slicing a
    full fit at `asof` is the same reading as refitting at `asof`. Forward probability: the share
    of the next `step` training days' labels that followed days in today's label, blended 50/50
    with the training frequency on a `split` day (the engines disagree, so confidence halves),
    then the incumbent's floor and cap."""
    lab = labels if labels is not None else ens.label_days(pd.DataFrame({"close": gold}))
    by_day = lab["vol"].to_dict()
    lab_tr = [str(by_day.get(d, "")) for d in train_days]
    if sum(1 for x in lab_tr if x) < 0.5 * len(lab_tr):
        return None
    asof = train_days[-1]
    now = str(by_day.get(asof, ""))
    if not now:
        return None
    freq: dict[str, float] = {}
    for x in lab_tr:
        if x:
            freq[x] = freq.get(x, 0.0) + 1.0
    trans: dict[str, float] = {}
    for i, x in enumerate(lab_tr[:-1]):
        if x != now:
            continue
        for y in lab_tr[i + 1: i + 1 + step]:
            if y:
                trans[y] = trans.get(y, 0.0) + 1.0
    tf, tt = sum(freq.values()) or 1.0, sum(trans.values())
    split = bool(lab["split"].get(asof, False))
    conf = 0.5 if split else 1.0
    if tt <= 0:
        conf = 0.0
    keys = sorted(freq)
    probs = {k: max(conf * trans.get(k, 0.0) / (tt or 1.0) + (1 - conf) * freq[k] / tf,
                    REGIME_MIN_SHARE) for k in keys}
    z = sum(probs.values())
    probs = {k: v / z for k, v in probs.items()}
    top = max(probs, key=lambda k: probs[k])
    if probs[top] > REGIME_MAX_SHARE:
        spill, rest = probs[top] - REGIME_MAX_SHARE, sum(v for k, v in probs.items() if k != top)
        probs = {k: REGIME_MAX_SHARE if k == top else v + spill * v / (rest or 1.0)
                 for k, v in probs.items()}
    return tuple(lab_tr), tuple(sorted(probs.items(), key=lambda kv: -kv[1]))


def run_contract(step: int = 21, train_n: int = 750, n_worlds: int = 128, n_rows: int = 256,
                 budget_s: float = CONTRACT_BUDGET_S, max_steps: int | None = None,
                 universe: str = "auto") -> dict[str, Any]:
    """geo vs geo_hmm vs geo_ensemble, walk-forward, on `regime_allocation_contract`'s machinery."""
    import regime_allocation_contract as rac

    from libs.portfolio.robust_elog import WorldConfig

    t0 = time.monotonic()
    stood = _headroom("contract")
    if stood is not None:
        doc = {"schema": SCHEMA, "generated_at": _iso(), "verdict": UNMEASURED, "admits": False,
               **stood}
        _write(CONTRACT, doc)
        return doc
    desk = rac.load_desk() if universe in ("auto", "desk") else None
    if desk is not None:
        r, _labels, closes = desk
        used = "desk"
    else:
        closes, _labels = rac.load(rac.ASSETS)
        r = rac.sleeves(_labels, closes).dropna(how="all").iloc[rac.MOM_WIN + rac.SIG_WIN:]
        used = "bars"
    if INCUMBENT_SYMBOL not in closes:
        doc = {"schema": SCHEMA, "generated_at": _iso(), "verdict": UNMEASURED, "admits": False,
               "why": f"no {INCUMBENT_SYMBOL} closes: neither state can condition the worlds"}
        _write(CONTRACT, doc)
        return doc
    gold = closes[INCUMBENT_SYMBOL].dropna()
    lab = ens.label_days(pd.DataFrame({"close": gold}))
    days = list(r.index)
    arms = ["equal", "geo", "geo_hmm", "geo_ensemble"]
    cfg0 = WorldConfig(n_worlds=n_worlds, n_rows=n_rows)
    realised: dict[str, list[float]] = {a: [] for a in arms}
    starts = list(range(train_n, len(days) - 1, step))
    if max_steps:
        starts = starts[:max_steps]
    oos: list[str] = []
    conditioned = {"geo_hmm": 0, "geo_ensemble": 0}
    truncated = False
    for s in starts:
        if time.monotonic() - t0 > budget_s:
            truncated = True
            break
        train = r.iloc[s - train_n: s]
        train = train.loc[:, train.notna().sum() >= rac.MIN_TRAIN_OBS]
        if train.shape[1] < 2:
            continue
        test = r.iloc[s: s + step][train.columns].fillna(0.0)
        tdays = [str(d) for d in train.index]
        names = list(train.columns)
        ev = rac._evidence(train, None, None)
        heat: dict[str, dict[str, float]] = {"equal": {c: rac.TOTAL_HEAT / len(names)
                                                       for c in names}}
        heat["geo"] = rac._solve(ev, cfg0)
        for arm, cond in (("geo_hmm", rac.hmm_conditioning(gold, tdays)),
                          ("geo_ensemble", ensemble_conditioning(gold, tdays, step, lab))):
            if cond is None:
                heat[arm] = heat["geo"]
                continue
            conditioned[arm] += 1
            heat[arm] = rac._solve(ev, WorldConfig(n_worlds=n_worlds, n_rows=n_rows,
                                                   regime_labels=cond[0], regime_probs=cond[1]))
        for a in arms:
            h = np.array([heat[a].get(c, 0.0) for c in names])
            acct = test.to_numpy(float) @ h
            realised[a].extend(np.log1p(np.maximum(acct, -0.99)).tolist())
        oos.extend(str(d) for d in test.index)
    arr = {a: np.asarray(v) for a, v in realised.items()}
    if not oos or arr["geo"].size < 42:
        doc = {"schema": SCHEMA, "generated_at": _iso(), "verdict": UNMEASURED, "admits": False,
               "why": f"{arr['geo'].size} out-of-sample days; the contract needs 42",
               "design": {"universe": used}}
        _write(CONTRACT, doc)
        return doc
    diffs: dict[str, Any] = {}
    for a, b in (("geo_ensemble", "geo_hmm"), ("geo_ensemble", "geo"), ("geo_hmm", "geo"),
                 ("geo_ensemble", "equal")):
        d = arr[a] - arr[b]
        lo, hi = rac.block_bootstrap_ci(d)
        diffs[f"{a}_minus_{b}"] = {"mean_per_day": round(float(d.mean()), 9),
                                   "annual": round(float(d.mean()) * 252, 5),
                                   "ci90": [round(lo, 9), round(hi, 9)]}
    head = diffs["geo_ensemble_minus_geo_hmm"]
    win = head["ci90"][0] > 0 and diffs["geo_ensemble_minus_geo"]["mean_per_day"] > 0
    verdict = "WIN" if win else ("LOSS" if head["ci90"][1] < 0 else "INCONCLUSIVE")
    doc = {
        "schema": SCHEMA, "generated_at": _iso(), "contract": "state_ensemble_allocation",
        "verdict": verdict, "admits": bool(used == "desk" and verdict == "WIN" and not truncated),
        "headline": {"arm": HEADLINE[0], "against": HEADLINE[1], **head},
        "rule": ("WIN iff the 90% stationary-bootstrap interval of (geo_ensemble - geo_hmm) daily "
                 "log growth is above zero AND geo_ensemble beats geo (no regime); headline "
                 "declared before the run, never swapped; only the desk's own sleeves admit, and "
                 "only on a pass that completed every re-solve"),
        "trials": len(arms), "arms": {a: rac.summarise(x) for a, x in arr.items()},
        "differences": diffs, "conditioned_rebalances": conditioned,
        "truncated_by_budget": truncated, "memory": memory(),
        "design": {"universe": used, "step_days": step, "train_days": train_n,
                   "n_worlds": n_worlds, "n_rows": n_rows, "rebalances": len(starts),
                   "oos_first": oos[0], "oos_last": oos[-1],
                   "state_symbol": INCUMBENT_SYMBOL,
                   "rails": [REGIME_MIN_SHARE, REGIME_MAX_SHARE],
                   "lookahead": "labels fitted once on the gold series; each is a function of "
                                "data up to its own day (truncation test), and only training "
                                "days' labels and asof's state enter a solve"},
        "runtime_s": round(time.monotonic() - t0, 1),
    }
    _write(CONTRACT, doc)
    return doc


# ======================================================================= 3. the near-miss re-test
def _phash(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:10]


def near_misses(note: dict[str, str]) -> list[dict[str, Any]]:
    """Judged cells that narrowly failed, read from the gauntlet's own verdicts, best first."""
    from alpha_recombination import dsr_bar, last_gate, near_survivor
    bar, _ = dsr_bar()
    final, _ = last_gate()
    out: dict[str, dict[str, Any]] = {}

    def consider(v: dict[str, Any]) -> None:
        near = near_survivor(v, bar, final)
        if near is None:
            return
        params = v.get("params") if isinstance(v.get("params"), dict) else {}
        key = f"{v.get('sym')}|{v.get('family')}|{_phash(params)}"
        ratio = near.get("ratio")
        cand = {"sym": str(v.get("sym") or ""), "family": str(v.get("family") or ""),
                "params": params, "params_basis": "verdict" if params else
                "family defaults (the verdict carried no params)", "cell": v.get("cell"),
                "near": near, "rank": 1.0 if ratio is None else float(ratio)}
        if key not in out or cand["rank"] > out[key]["rank"]:
            out[key] = cand

    try:
        size_mb = GATES_EXTERNAL.stat().st_size / 2 ** 20
    except OSError:
        size_mb = -1.0
        note["gates_external"] = f"{GATES_EXTERNAL.name} absent"
    if size_mb >= 0:
        avail = memory()["available_mb"]
        # json.loads of a large report costs roughly ten times its size in Python objects.
        if avail < 10.0 * size_mb + 300.0:
            note["gates_external"] = (f"{size_mb:.0f} MB needs ~{10 * size_mb:.0f} MB to parse and "
                                      f"{avail:.0f} MB is available: UNMEASURED this pass")
        else:
            doc = _read(GATES_EXTERNAL, {})
            got = doc.get("verdicts") if isinstance(doc, dict) else None
            for v in got or []:
                if isinstance(v, dict):
                    consider(v)
            del doc, got
    # The thin ledger is streamed and only its near-survivors are kept: on the box it is
    # hundreds of thousands of rows, and none of the others is needed.
    try:
        with GATE_LEDGER.open(encoding="utf-8") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                try:
                    v = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(v, dict):
                    consider(v)
    except OSError:
        note["gate_ledger"] = f"{GATE_LEDGER.name} absent"
    return sorted(out.values(), key=lambda c: -c["rank"])


def _null_charge(n: int) -> None:
    if n <= 0:
        return
    NULL_TRIALS.parent.mkdir(parents=True, exist_ok=True)
    with NULL_TRIALS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _iso(), "source": SOURCE, "tests_run": n,
                             "by_family": {FAMILY: n},
                             "rule": "each (near-miss cell, regime) charged once, lifetime"})
                 + "\n")


def run_nearmiss(budget_s: float = NEARMISS_BUDGET_S, donate: bool = True) -> dict[str, Any]:
    import proposer_common as pc
    import regime_split_miner as rsm
    from mt5desk import families_orthogonal as fo

    t0 = time.monotonic()
    stood = _headroom("nearmiss")
    if stood is not None:
        doc = {"schema": SCHEMA, "generated_at": _iso(), **stood}
        _write(NEARMISS, doc)
        return doc
    note: dict[str, str] = {}
    cands = near_misses(note)
    try:
        from research.universe_policy import may_hypothesise
    except Exception:                                            # pragma: no cover
        def may_hypothesise(symbol: str, family: object = None) -> bool:
            return True
    union: dict[str, str] = _read(CHARGED, {}) or {}
    meta = pc.universe_meta()
    frames: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    refused: dict[str, int] = {}
    # Never-charged cells first, so a budget that runs out spends itself on new ground.
    cands.sort(key=lambda c: any(k.startswith(f"{c['sym']}.{FAMILY}.ens.{c['family']}."
                                              f"{_phash(c['params'])}.") for k in union))
    reached = 0
    for c in cands[:MAX_NEAR_CELLS]:
        if time.monotonic() - t0 > budget_s:
            break
        sym, base, bp = c["sym"], c["family"], dict(c["params"])

        def refuse(why: str) -> None:
            refused[why] = refused.get(why, 0) + 1
        if base == FAMILY or rsm._base_fn(base) is None:
            refuse("base family is not a price-only family the gauntlet can rebuild from bars")
            continue
        if set(bp) & {"base_family", "vol", "trend", "liq", "labeler"}:
            refuse("params collide with the regime_split axes")
            continue
        if not may_hypothesise(sym, FAMILY):
            refuse("two-lane mandate: not a hypothesis-lane symbol")
            continue
        if sym not in frames:
            d = pc.bars(sym)
            cost = pc.cost_frac(sym, meta, d["close"]) if d is not None else None
            frames[sym] = (None if d is None or len(d) < 24 * 400 or cost is None
                           else (d, cost, pc.artifact_hours(d)))
        if frames[sym] is None:
            refuse("under 400 days of H1 bars or no contract terms")
            continue
        d, cost, unfill = frames[sym]
        reached += 1
        blended = pc.screen(d, rsm._base_fn(base)(d, **bp), cost, unfill)
        for v in VOLS:
            for t in TRENDS:
                params = {"base_family": base, "vol": v, "trend": t, "labeler": "ensemble", **bp}
                sc = pc.screen(d, fo.family_regime_split(d, **params), cost, unfill, detail=True)
                if sc is None:
                    continue
                wf = rsm.purged_walk_forward(sc.pop("pnl"), sc.pop("entry_pos"), len(d), cost)
                rows.append({"cell": f"{sym}.{FAMILY}.ens.{base}.{_phash(bp)}.{v}_{t}",
                             "symbol": sym, "params": params, **sc, "walk_forward": wf,
                             "near_miss": {"cell": c["cell"], **c["near"],
                                           "params_basis": c["params_basis"]},
                             "blended": ({k: blended[k] for k in ("n_independent",
                                                                  "net_per_trade", "t_gross")}
                                         if blended else None)})
    rows = pc.deflate(rows)
    now = _iso()
    new = [str(r["cell"]) for r in rows if str(r["cell"]) not in union]
    for cell in new:
        union[cell] = now
    _write(CHARGED, union)
    from research.multiplicity import deflate_t
    for r in rows:
        n = max(int(r.get("n_tests_sweep") or 0), len(union))
        r["n_tests_sweep"] = n
        r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), n), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                             and int(r.get("n_independent", 0)) >= pc.MIN_TRADES
                             and r["walk_forward"]["passed"])
    proposals = pc.best_per_cell(rows)
    out_c = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"{r['params']['base_family']} narrowly failed the gauntlet blended "
                   f"({r['near_miss'].get('near_basis')}); re-tested only when {r['symbol']} is "
                   f"in the state ensemble's {r['params']['vol']}-vol {r['params']['trend']} "
                   "state of the last completed day"),
        title=str(r["cell"]),
        evidence={**{k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                       "cost_frac", "t_gross", "t_deflated_sweep",
                                       "n_tests_sweep")},
                  "walk_forward_measured": r["walk_forward"]["measured"],
                  "near_miss": r["near_miss"], "blended": r["blended"]},
    ) for r in proposals]
    donated: str | None = None
    if out_c and donate:
        path = pc.donate(SOURCE, out_c, len(new))
        donated = str(path) if path else None
    if donated is None:
        _null_charge(len(new))
    by_regime: dict[str, dict[str, int]] = {}
    for r in rows:
        k = f"{r['params']['vol']}_{r['params']['trend']}"
        b = by_regime.setdefault(k, {"tested": 0, "walk_forward_passed": 0, "proposed": 0})
        b["tested"] += 1
        b["walk_forward_passed"] += int(bool(r["walk_forward"]["passed"]))
        b["proposed"] += int(bool(r.get("proposed")))
    doc = {"schema": SCHEMA, "generated_at": now, "memory": memory(),
           "near_miss_cells": len(cands), "cells_reached": reached, "refused": refused,
           "notes": note, "tests_run": len(rows), "cells_newly_charged": len(new),
           "lifetime_union_cells": len(union), "cells_proposed": len(proposals),
           "killed_by_walk_forward": sum(1 for r in rows if r.get("clears_cost")
                                         and not r["walk_forward"]["passed"]),
           "per_regime": by_regime, "donated": donated,
           "trial_rule": ("each (near-miss cell, regime bucket) is one trial charged once over "
                          "the lifetime union; charged on the donation's tests_run, or on "
                          "null_pass_trials.jsonl when nothing is donated -- never both; every "
                          "row deflated against the whole union; the gauntlet then charges its "
                          "own lifetime count"),
           "proposals": proposals[:50], "all": rows[:400],
           "runtime_s": round(time.monotonic() - t0, 1)}
    _write(NEARMISS, doc)
    return doc


# ================================================================================== the leg
def run(only: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if only in (None, "contract"):
        age = _age_h(CONTRACT)
        if only == "contract" or age is None or age > CONTRACT_EVERY_H:
            try:
                c = run_contract()
                out["contract"] = {"verdict": c.get("verdict"), "admits": c.get("admits")}
            except Exception as exc:
                out["contract"] = {"error": f"{type(exc).__name__}: {exc}"[:240]}
        else:
            out["contract"] = {"skipped": f"{age:.1f} h old; re-run after {CONTRACT_EVERY_H} h"}
    if only in (None, "nearmiss"):
        age = _age_h(NEARMISS)
        if only == "nearmiss" or age is None or age > NEARMISS_EVERY_H:
            try:
                n = run_nearmiss()
                out["nearmiss"] = {k: n.get(k) for k in ("tests_run", "cells_proposed",
                                                         "cells_newly_charged")}
            except Exception as exc:
                out["nearmiss"] = {"error": f"{type(exc).__name__}: {exc}"[:240]}
        else:
            out["nearmiss"] = {"skipped": f"{age:.1f} h old; re-run after {NEARMISS_EVERY_H} h"}
    if only in (None, "state"):
        # LAST, so its `promotion` block reads the contract this pass may just have written.
        s = run_state()
        out["state"] = {k: s.get(k) for k in ("n_measured", "refit_this_pass",
                                              "calibration_vs_plain", "promotion")}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("state", "contract", "nearmiss"), default=None)
    a = ap.parse_args(argv)
    out = run(a.only)
    print(json.dumps(out, indent=1, default=str))
    failed = [k for k, v in out.items() if isinstance(v, dict) and "error" in v]
    return 1 if failed and len(failed) == len(out) else 0


if __name__ == "__main__":
    raise SystemExit(main())
