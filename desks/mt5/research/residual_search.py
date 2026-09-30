#!/usr/bin/env python3
"""RESIDUAL SEARCH AND COUNTERFACTUAL POLICY: what the book earns that its known factors do not
explain, emitted as conditioned cells; and what every gate would have earned relaxed or tightened.

    python desks/mt5/research/residual_search.py --once
    python desks/mt5/research/residual_search.py --once --dry-run   # measure, donate nothing

PART 1 -- THE RESIDUAL. Every trade the desk's live and certified book took (the shadow forward
ledgers and the live ledger, through `action_counterfactuals.load_trades`, plus the rows that
organ already persisted) is regressed on what the desk already knows explains it:

    r_hat = mean R of its axis_registry MECHANISM CLUSTER
          + n_s / (n_s + K) x (mean R of its SLEEVE - the cluster mean)

i.e. a cluster fixed effect with a shrunk certified-sleeve effect inside it. The residual
e = r - r_hat is what neither the cluster nor the sleeve predicts. It is then searched along four
axes that a sleeve-level mean cannot see -- the broker HOUR of entry, the DAY OF WEEK, the
VOLATILITY REGIME of the traded symbol (the desk's own `family_generic` definition), and the sign
of a CROSS-ASSET series' trailing return (USDX, US500, XAUUSD, UST10Y, USDJPY) -- one t-test per
populated bucket, every test counted, and Benjamini-Hochberg at q = FDR_Q over all of them. Only
a bucket that survives the correction is a finding.

A FINDING BECOMES A CELL, NOT A POLICY. For each finding, each certified parent whose own trades
in that bucket carry the same sign is written as a child cell -- the parent's exact (symbol,
family, params) wrapped by `entry_conditioned` with the filter (keep the bucket when the residual
is positive, drop it when negative). The child is buildability-checked, BUILT through the sealed
`build_cell`, and donated through `proposer_common.donate` only when it clears the gauntlet's
floor; the gauntlet then judges it like anything else. The parent stays exactly as it is.

PART 2 -- COUNTERFACTUAL POLICY. For each gate or filter the desk applies, read from the
decision and intent ledgers:
  * VETOES, RELAXED: the priced counterfactual of every bracket the gate refused
    (`data/counterfactuals.jsonl`, `counterfactual_markout`'s replays; and the VETO_ALPHA arms of
    `data/decision_dataset.jsonl`, `counterfactual_replay`'s pricing) -- what the book would have
    earned had the gate let them through.
  * VETOES, TIGHTENED: needs the MARGIN by which an admitted trade cleared the gate. Where a
    decision row carries one (a positive `signal_bps - modelled_cost_bps`, or a numeric feature),
    the admitted trades in its bottom quintile are joined to their realised R -- what one quintile
    tighter would have removed. Where no margin is recorded the answer is UNMEASURED with the
    field the gateway would have to write, never a zero.
  * CAPITAL MODIFIERS, BOTH WAYS: every trade joined to its sleeve's last `capital_modifier_ledger`
    row, its multiplier scaled as 1 + lambda (m - 1) for lambda in {0, 0.5, 1, 1.5} with the
    AVERAGE HEAT HELD FIXED (the construction `modifier_counterfactuals` explains is the only one
    that is not a tautology), and E[log(1 + h r)] read per lambda.
  * The rails `missed_growth`, `modifier_counterfactuals`, `counterfactual_markout` and
    `counterfactual_replay` already price are CITED from their own reports, never recomputed.

RESEARCH FINDINGS ONLY. Nothing here is read by the gateway, the promoter, admission, the
allocator or any sizing path; it writes `reports/RESIDUAL_SEARCH.json`, a donation of conditioned
CELLS for the gauntlet to judge, and its own state file. `research/residual_queue.py` queues its
findings. UNMEASURED WHEN ITS INPUTS ARE ABSENT (L1.28a): no trades is UNMEASURED, not "no
structure"; a gate with no priced refusal is UNMEASURED, not "harmless".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "residual_search"
OUT = BASE / "reports" / "RESIDUAL_SEARCH.json"
STATE = BASE / "data" / "residual_search_state.json"
PERSISTED_TRADES = BASE / "data" / "action_counterfactuals.jsonl"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVES = BASE / "data" / "sleeves.json"
COUNTERFACTUALS = BASE / "data" / "counterfactuals.jsonl"
DECISION_DATASET = BASE / "data" / "decision_dataset.jsonl"
DECISIONS = BASE / "data" / "decision_ledger.jsonl"
LIVE = BASE / "data" / "live_ledger.jsonl"
MODIFIERS = BASE / "data" / "capital_modifier_ledger.jsonl"
CITED = {
    "missed_growth": BASE / "reports" / "MISSED_GROWTH.json",
    "modifier_counterfactuals": BASE / "reports" / "MODIFIER_COUNTERFACTUALS.json",
    "filter_value": BASE / "reports" / "FILTER_VALUE.json",
    "counterfactual_world": BASE / "reports" / "COUNTERFACTUAL_WORLD.json",
    "action_counterfactuals": BASE / "reports" / "ACTION_COUNTERFACTUALS.json",
}
UNMEASURED = "UNMEASURED"

#: Shrinkage of a sleeve's own mean toward its cluster's: a sleeve with K trades is half-trusted.
SHRINK_K = 10.0
#: A bucket is tested only with this many trades in it, and a sleeve counts as a parent of a
#: finding only with this many of its own trades in the bucket.
MIN_BUCKET_N = 20
MIN_PARENT_N = 5
#: Benjamini-Hochberg false-discovery rate across every bucket tested in a pass.
FDR_Q = 0.10
#: Cross-asset conditioners, read from the bar store, and their trailing window in days.
COND_SYMBOLS = ("USDX", "US500", "XAUUSD", "UST10Y", "USDJPY")
COND_LOOKBACK_D = 5
#: The sealed gauntlet's floor and this organ's donation floor, as the class books use them.
FIRE_FLOOR = 60
SEED_FLOOR = 66
#: Risk per trade when the sleeve's allocator fraction is not on the row (said, never hidden).
FALLBACK_H = 0.01
LAMBDAS = (0.0, 0.5, 1.0, 1.5)
MIN_GATE_N = 20


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows(path: Path, limit: int = 200_000) -> list[dict]:
    out: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
                if len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def _ts(v: Any) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(str(v))
    except (TypeError, ValueError):
        return None
    if t is pd.NaT:
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _t(x: np.ndarray) -> float | None:
    if x.size < 2:
        return None
    sd = float(x.std(ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None
    return float(x.mean()) / (sd / math.sqrt(x.size))


def _p_two_sided(t: float) -> float:
    return float(math.erfc(abs(t) / math.sqrt(2.0)))


# =================================================================================== trades ===
def load_trades() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The book's trades on the BAR clock: (sleeve, symbol, basis, entry bar time, R).

    Shadow ledgers are stamped on the bar clock already. A live row's time is venue UTC and is
    moved to the bar clock through `libs.research.bar_clock`; when that clock is not measured on
    this host the row is COUNTED and left out of the hour/weekday/regime axes rather than joined
    two or three hours wrong."""
    notes: dict[str, Any] = {}
    raw: list[dict] = []
    try:
        from research import action_counterfactuals as ac
        got, gaps = ac.load_trades()
        raw.extend(got)
        notes["load_gaps"] = gaps
    except Exception as exc:
        notes["load_error"] = f"{type(exc).__name__}: {exc}"
    raw.extend(r for r in _rows(PERSISTED_TRADES) if r.get("entry_time"))
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    unclocked = 0
    for r in raw:
        sleeve = str(r.get("sleeve") or "")
        et = _ts(r.get("entry_time"))
        try:
            rm = float(r.get("r_multiple"))
        except (TypeError, ValueError):
            continue
        if not sleeve or et is None or not math.isfinite(rm):
            continue
        key = (sleeve, et.isoformat())
        if key in seen:
            continue
        seen.add(key)
        basis = str(r.get("basis") or "shadow")
        if basis == "live":
            try:
                from libs.research.bar_clock import to_bar_time
                moved, _status, _why = to_bar_time(et.to_pydatetime())
            except Exception:
                moved = None
            if moved is None:
                unclocked += 1
                continue
            et = pd.Timestamp(moved)
            et = et.tz_localize("UTC") if et.tzinfo is None else et
        out.append({"sleeve": sleeve, "symbol": str(r.get("symbol") or "").upper(),
                    "basis": basis, "t": et, "r": rm})
    notes["live_rows_without_bar_clock"] = unclocked
    notes["n_trades"] = len(out)
    notes["by_basis"] = dict(Counter(t["basis"] for t in out))
    return out, notes


# ================================================================================== parents ===
def _family_names() -> list[str]:
    try:
        from research.gauntlet_buildability import family_names
        return sorted(family_names(), key=len, reverse=True)
    except Exception:
        return []


def parent_specs() -> dict[str, dict[str, Any]]:
    """sleeve name -> {symbol, family, params, cert, source} for every CERTIFIED sleeve, from the
    canon's exact shadow_spec (`research_pnl.resolver`'s name join), then the roster's rows."""
    out: dict[str, dict[str, Any]] = {}
    canon = _read(CANON)
    if isinstance(canon, dict) and isinstance(canon.get("survivors"), dict):
        try:
            from research.research_pnl import resolver
            names = resolver(canon)
        except Exception:
            names = {}
        for name, hit in names.items():
            cert = canon["survivors"].get(hit.get("cert")) or {}
            spec = cert.get("shadow_spec") if isinstance(cert, dict) else None
            if isinstance(spec, dict) and spec.get("family"):
                out[name] = {"symbol": str(spec.get("symbol") or cert.get("sym") or "").upper(),
                             "family": str(spec["family"]),
                             "params": dict(spec.get("params") or {}),
                             "cert": hit.get("cert"), "source": "canon"}
    roster = _read(SLEEVES)
    for row in (roster.get("sleeves") if isinstance(roster, dict) else None) or []:
        if not isinstance(row, dict) or not row.get("name") or row["name"] in out:
            continue
        if row.get("family") and isinstance(row.get("params"), dict):
            out[str(row["name"])] = {"symbol": str(row.get("symbol") or "").upper(),
                                     "family": str(row["family"]),
                                     "params": dict(row["params"]), "cert": None,
                                     "source": "sleeves.json"}
    return out


def family_of(sleeve: str, specs: dict[str, dict[str, Any]], names: list[str]) -> str:
    spec = specs.get(sleeve)
    if spec:
        return spec["family"]
    low = sleeve.lower()
    return next((f for f in names if f and f in low), "")


def cluster_of(family: str) -> str:
    try:
        from research.axis_registry import classify_family
        return str(classify_family(family)[0])
    except Exception:
        return "UNKNOWN"


# ================================================================================ residuals ===
def residualise(trades: list[dict[str, Any]], specs: dict[str, dict[str, Any]]
                ) -> dict[str, Any]:
    """Cluster fixed effect + shrunk sleeve effect; writes `e`, `cluster`, `family` on each."""
    names = _family_names()
    for t in trades:
        t["family"] = family_of(t["sleeve"], specs, names)
        t["cluster"] = cluster_of(t["family"]) if t["family"] else "UNKNOWN"
    by_c: dict[str, list[float]] = defaultdict(list)
    by_s: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        by_c[t["cluster"]].append(t["r"])
        by_s[t["sleeve"]].append(t["r"])
    mu_c = {k: float(np.mean(v)) for k, v in by_c.items()}
    mu_s = {k: float(np.mean(v)) for k, v in by_s.items()}
    n_s = {k: len(v) for k, v in by_s.items()}
    for t in trades:
        w = n_s[t["sleeve"]] / (n_s[t["sleeve"]] + SHRINK_K)
        t["r_hat"] = mu_c[t["cluster"]] + w * (mu_s[t["sleeve"]] - mu_c[t["cluster"]])
        t["e"] = t["r"] - t["r_hat"]
    r = np.asarray([t["r"] for t in trades], dtype=float)
    e = np.asarray([t["e"] for t in trades], dtype=float)
    var_r = float(r.var()) if r.size else 0.0
    return {"n": len(trades), "clusters": {k: {"n": len(v), "mean_r": round(mu_c[k], 4)}
                                           for k, v in sorted(by_c.items())},
            "n_sleeves": len(by_s),
            "r2_explained_by_clusters_and_sleeves": (round(1.0 - float(e.var()) / var_r, 4)
                                                     if var_r > 0 else None),
            "model": (f"r_hat = cluster mean + n/(n+{SHRINK_K:g}) x (sleeve mean - cluster "
                      "mean); cluster = axis_registry mechanism of the sleeve's family")}


def _bars(symbol: str) -> pd.DataFrame | None:
    try:
        from research import proposer_common as pc
        return pc.bars(symbol)
    except Exception:
        return None


def label(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Hour, weekday, volatility regime and cross-asset state of each trade at entry -- with
    the same functions `entry_conditioned` filters on, so what is measured is what is traded."""
    from mt5desk.families_specialist import trailing_log_return, vol_regime_mask
    no_bars: set[str] = set()
    for t in trades:
        t["hour"] = int(t["t"].hour)
        t["dow"] = int(t["t"].dayofweek)
    for sym in sorted({t["symbol"] for t in trades}):
        d = _bars(sym) if sym else None
        mine = [t for t in trades if t["symbol"] == sym]
        if d is None or len(d) == 0:
            no_bars.add(sym or "?")
            continue
        hv = vol_regime_mask(d, "high_vol")
        lv = vol_regime_mask(d, "low_vol")
        at = d.index.get_indexer(pd.DatetimeIndex([t["t"] for t in mine]), method="ffill")
        for t, i in zip(mine, at, strict=True):
            if i < 0 or hv is None or lv is None:
                continue
            t["vol"] = "high_vol" if hv[i] else ("low_vol" if lv[i] else "neither")
    stamps = pd.DatetimeIndex([t["t"] for t in trades]).as_unit("ns").asi8 if trades else None
    cond_missing: list[str] = []
    for cs in COND_SYMBOLS:
        if stamps is None:
            break
        r = trailing_log_return(stamps, cs, COND_LOOKBACK_D)
        if not np.isfinite(r).any():
            cond_missing.append(cs)
            continue
        for t, v in zip(trades, r, strict=True):
            if np.isfinite(v) and v != 0 and cs != t["symbol"]:
                t[f"x:{cs}"] = "up" if v > 0 else "down"
    return {"symbols_without_bars": sorted(no_bars), "cond_symbols_without_bars": cond_missing}


def search(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """One t-test of the residual per populated bucket, BH-corrected over every test run."""
    axes = ["hour", "dow", "vol"] + [f"x:{c}" for c in COND_SYMBOLS]
    tests: list[dict[str, Any]] = []
    for ax in axes:
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for t in trades:
            if t.get(ax) is not None:
                groups[t[ax]].append(t)
        for bucket, members in groups.items():
            if len(members) < MIN_BUCKET_N:
                continue
            e = np.asarray([m["e"] for m in members], dtype=float)
            tt = _t(e)
            if tt is None:
                continue
            tests.append({"axis": ax, "bucket": bucket, "n": int(e.size),
                          "n_sleeves": len({m["sleeve"] for m in members}),
                          "mean_residual_r": round(float(e.mean()), 4), "t": round(tt, 3),
                          "p": _p_two_sided(tt)})
    m = len(tests)
    ranked = sorted(range(m), key=lambda i: tests[i]["p"])
    k_star = 0
    for rank, i in enumerate(ranked, start=1):
        if tests[i]["p"] <= FDR_Q * rank / m:
            k_star = rank
    for rank, i in enumerate(ranked, start=1):
        tests[i]["bh_rejected"] = rank <= k_star
        tests[i]["bonferroni_rejected"] = tests[i]["p"] <= 0.05 / max(m, 1)
        tests[i]["p"] = round(tests[i]["p"], 6)
    findings = [x for x in tests if x["bh_rejected"]]
    return {"tests_run": m, "fdr_q": FDR_Q, "findings": findings,
            "top_by_abs_t": sorted(tests, key=lambda x: -abs(x["t"]))[:15],
            "rule": (f"a bucket needs >= {MIN_BUCKET_N} trades to be tested; every test is "
                     f"counted; a finding is BH-rejected at q={FDR_Q} over all {m} tests")}


# ========================================================================= conditioned cells ===
def _filter_for(axis: str, bucket: Any, sign: int) -> dict[str, Any] | None:
    """The entry_conditioned filter that keeps a positive bucket or drops a negative one."""
    if axis == "hour":
        return {"hours": [int(bucket)] if sign > 0 else [h for h in range(24) if h != bucket]}
    if axis == "dow":
        return {"dows": [int(bucket)] if sign > 0 else [x for x in range(5) if x != bucket]}
    if axis == "vol":
        if bucket not in ("high_vol", "low_vol"):
            return None
        return {"vol_regime": bucket if sign > 0 else f"not_{bucket}"}
    if axis.startswith("x:"):
        s = 1 if bucket == "up" else -1
        return {"cond_symbol": axis[2:], "cond_lookback_d": COND_LOOKBACK_D,
                "cond_sign": s if sign > 0 else -s}
    return None


def identity(symbol: str, family: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


def children(trades: list[dict[str, Any]], findings: list[dict[str, Any]],
             specs: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    """Each finding x each certified parent whose own in-bucket residual has the finding's sign."""
    from mt5desk.families_specialist import wrappable
    from research import universe_policy as up
    try:
        from research.family_policy import family_banned
    except Exception:                                          # pragma: no cover - path
        def family_banned(_f: str) -> bool:
            return False
    skipped: Counter = Counter()
    out: list[dict[str, Any]] = []
    for f in findings:
        sign = 1 if f["mean_residual_r"] > 0 else -1
        filt = _filter_for(f["axis"], f["bucket"], sign)
        if filt is None:
            skipped["bucket has no expressible filter"] += 1
            continue
        per: dict[str, list[float]] = defaultdict(list)
        for t in trades:
            if t.get(f["axis"]) == f["bucket"]:
                per[t["sleeve"]].append(t["e"])
        for sleeve, es in sorted(per.items()):
            spec = specs.get(sleeve)
            if spec is None:
                skipped["parent sleeve has no certified spec"] += 1
                continue
            if len(es) < MIN_PARENT_N or np.sign(np.mean(es)) != sign:
                skipped["parent's own bucket residual too thin or of the other sign"] += 1
                continue
            fam, sym = spec["family"], spec["symbol"]
            if family_banned(fam) or not wrappable(fam):
                skipped[f"parent family {fam} cannot be wrapped"] += 1
                continue
            if not up.may_hypothesise(sym, "entry_conditioned"):
                skipped["parent symbol is not in the hypothesis lane"] += 1
                continue
            params = {"base_family": fam, "base_params": dict(spec["params"]), "symbol": sym,
                      **filt}
            out.append({"symbol": sym, "family": "entry_conditioned", "params": params,
                        "parent": {"sleeve": sleeve, "cert": spec.get("cert"), "family": fam},
                        "finding": {k: f[k] for k in ("axis", "bucket", "n", "mean_residual_r",
                                                      "t", "p")},
                        "parent_bucket_n": len(es),
                        "parent_bucket_mean_residual_r": round(float(np.mean(es)), 4)})
    uniq: dict[str, dict[str, Any]] = {}
    for c in out:
        uniq.setdefault(identity(c["symbol"], c["family"], c["params"]), c)
    return list(uniq.values()), skipped


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def emit(kids: list[dict[str, Any]], *, dry_run: bool, budget_s: float) -> dict[str, Any]:
    """Verdict, sealed build, floor, then the door -- the specialist organ's own path."""
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    from research.specialist_cell import _meta, charge, measure
    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    state = _load_state()
    cs = state["cells"]
    meta = _meta()
    counts: Counter = Counter()
    measured: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for c in kids:
        verdict, why = cell_verdict(c["family"], c["params"])
        if verdict != BUILDABLE:
            counts[f"set_aside: {verdict}"] += 1
            continue
        ident = identity(c["symbol"], c["family"], c["params"])
        prior = cs.get(ident) or {}
        if prior.get("day") != today:
            if time.monotonic() - started > budget_s:
                counts["not_reached_this_pass"] += 1
                continue
            prior = {**prior, **measure(c["symbol"], c["family"], c["params"], meta),
                     "day": today, "symbol": c["symbol"], "family": c["family"],
                     "params": c["params"], "parent": c["parent"]}
            cs[ident] = prior
            measured.append({**c, "mechanism": f"residual:{c['finding']['axis']}",
                             "klass": "residual"})
        if not prior.get("built"):
            counts["input_gap"] += 1
            continue
        if int(prior.get("trade_days_lb") or 0) < SEED_FLOOR:
            counts["held_back_under_floor"] += 1
            continue
        counts["clears_floor"] += 1
        if not prior.get("donated_at"):
            cands.append({**c, "ident": ident,
                          "firing": {k: prior.get(k) for k in ("signal_days", "trade_days_lb")}})
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = [pc.candidate(
            SOURCE, c["symbol"], c["family"], c["params"],
            (f"residual structure: the book's residual after its mechanism clusters and certified "
             f"sleeves is {c['finding']['mean_residual_r']:+.3f}R at {c['finding']['axis']}="
             f"{c['finding']['bucket']} (t={c['finding']['t']}, BH q={FDR_Q}); the certified "
             f"parent {c['parent']['sleeve']} conditioned on it"),
            f"{c['symbol']} {c['parent']['family']} | {c['finding']['axis']}="
            f"{c['finding']['bucket']}",
            {"firing": c["firing"], "finding": c["finding"], "parent": c["parent"],
             "parent_bucket_n": c["parent_bucket_n"],
             "parent_bucket_mean_residual_r": c["parent_bucket_mean_residual_r"],
             "control_arm": "the un-filtered parent cell, already certified"})
            for c in cands]
        path = pc.donate(SOURCE, rows, len(measured) or len(rows))
        got = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "donated": got.get("donated"),
                    "refused_wrong_lane": got.get("refused_wrong_lane"),
                    "refused_unstamped": got.get("refused_unstamped"),
                    "registry_error": got.get("registry_error")}
        if path:
            at = _now()
            for c in cands:
                cs[c["ident"]]["donated_at"] = at
    if not dry_run:
        _save_state(state)
    return {"children_named": len(kids), "measured_this_pass": len(measured),
            "counts": dict(counts), "candidates_this_pass": len(cands), "donation": donation,
            "trial_charge_this_pass": charge(measured),
            "donated_total": sum(1 for v in cs.values() if v.get("donated_at"))}


# ===================================================================== counterfactual policy ===
def _stats(x: np.ndarray) -> dict[str, Any]:
    t = _t(x)
    return {"n": int(x.size), "sum_r": round(float(x.sum()), 3),
            "mean_r": round(float(x.mean()), 4) if x.size else None,
            "t": round(t, 2) if t is not None else None}


def _relaxed_verdict(s: dict[str, Any]) -> str:
    if s["n"] < MIN_GATE_N or s["t"] is None:
        return "INCONCLUSIVE" if s["n"] else UNMEASURED
    if s["t"] >= 2.0:
        return "RELAXING_WOULD_HAVE_EARNED"
    if s["t"] <= -2.0:
        return "GATE_EARNED_ITS_PLACE"
    return "INCONCLUSIVE"


def gate_policy() -> dict[str, Any]:
    """Every veto reason: relaxed (its refused brackets, priced) and tightened (its admitted
    margin, where the ledger records one)."""
    relaxed: dict[str, list[float]] = defaultdict(list)
    d_elog: dict[str, list[float]] = defaultdict(list)
    sources: dict[str, set[str]] = defaultdict(set)
    seen: set[tuple[str, str, str]] = set()
    for r in _rows(COUNTERFACTUALS):
        if r.get("status") != "REPLAYED":
            continue
        try:
            rv = float(r["r"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (str(r.get("sleeve")), str(r.get("time")), str(r.get("side")))
        seen.add(key)
        g = str(r.get("reason") or "?")
        relaxed[g].append(rv)
        sources[g].add("counterfactual_markout")
    for row in _rows(DECISION_DATASET):
        ca = row.get("chosen_action") or {}
        g = str(ca.get("veto_reason") or "")
        if not g:
            continue
        key = (str(row.get("sleeve")), str(row.get("minute")), str(row.get("side")))
        for arm in (row.get("counterfactual_outcomes") or {}).get("alternatives") or []:
            if arm.get("class") != "VETO_ALPHA" or arm.get("status") != "PRICED":
                continue
            try:
                rv = float(arm["r"])
            except (KeyError, TypeError, ValueError):
                continue
            if key not in seen:
                relaxed[g].append(rv)
                seen.add(key)
            if arm.get("d_elog") is not None:
                d_elog[g].append(float(arm["d_elog"]))
            sources[g].add("counterfactual_replay")
    refused_seen = Counter(str((row.get("chosen_action") or {}).get("veto_reason") or "")
                           for row in _rows(DECISION_DATASET))
    refused_seen.update(str(r.get("veto_reason") or r.get("reason") or "")
                        for r in _rows(DECISIONS) if r.get("outcome") not in ("EXECUTED",))
    refused_seen.pop("", None)
    tightened = _tightened()
    gates: dict[str, Any] = {}
    for g in sorted(set(relaxed) | set(refused_seen)):
        s = _stats(np.asarray(relaxed.get(g, []), dtype=float))
        rel = {**s, "verdict": _relaxed_verdict(s), "sources": sorted(sources.get(g, ())),
               "refusals_seen": int(refused_seen.get(g, 0)),
               "sum_d_elog": (round(float(np.sum(d_elog[g])), 6) if d_elog.get(g) else None)}
        if not s["n"]:
            rel["why"] = ("no refusal of this gate has been priced yet (the bracket never "
                          "triggered, or no bars cover it on this host)")
        gates[g] = {"relaxed": rel, "tightened": tightened.get(g, tightened["*"])}
    status = "MEASURED" if any(v["relaxed"]["n"] for v in gates.values()) else UNMEASURED
    return {"status": status, "gates": gates,
            "rule": ("relaxed = the priced counterfactual R of every bracket the gate refused "
                     "(positive: the book would have earned it); tightened = the realised R of "
                     "the admitted trades in the bottom quintile of the gate's recorded margin "
                     "(what one quintile tighter would have removed)")}


def _tightened() -> dict[str, Any]:
    """Margin-quintile tightening where decision rows carry a margin; UNMEASURED otherwise."""
    live = {}
    for r in _rows(LIVE):
        for k in ("entry_order", "order", "position_id"):
            try:
                if r.get(k) and r.get("r_multiple") is not None and not r.get(
                        "r_unreconstructible"):
                    live[int(r[k])] = float(r["r_multiple"])
            except (TypeError, ValueError):
                continue
    margins: list[tuple[float, float]] = []
    for d in _rows(DECISIONS):
        if d.get("outcome") != "EXECUTED":
            continue
        try:
            ticket = int(d.get("ticket") or 0)
        except (TypeError, ValueError):
            ticket = 0
        if not ticket or ticket not in live:
            continue
        sig, cost = d.get("signal_bps"), d.get("modelled_cost_bps")
        if isinstance(sig, (int, float)) and isinstance(cost, (int, float)) and (sig or cost):
            margins.append((float(sig) - float(cost), live[ticket]))
    why = ("the decision ledger records each gate's VERDICT and not the MARGIN by which an "
           "admitted trade cleared it (signal_bps and modelled_cost_bps are 0 on every executed "
           "row read); tightening needs that margin, which only the gateway can write -- "
           "`gateway._record_decision` is money-path code, so it is named here, not edited")
    if len(margins) < MIN_GATE_N:
        return {"*": {"status": UNMEASURED, "n_admitted_with_margin": len(margins), "why": why}}
    margins.sort()
    cut = max(1, len(margins) // 5)
    x = np.asarray([r for _m, r in margins[:cut]], dtype=float)
    s = _stats(x)
    return {"*": {"status": "MEASURED", "gate": "cost (signal_bps - modelled_cost_bps)",
                  "bottom_quintile": s,
                  "reads": ("tightening would have removed trades that EARNED" if s["sum_r"] > 0
                            else "tightening would have removed trades that LOST"),
                  "n_admitted_with_margin": len(margins)}}


def modifier_policy(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Each modifier category scaled toward 1 (relaxed) and away from it (tightened), at the
    same average heat, priced in E[log(1 + h r)]."""
    mods: dict[str, list[tuple[pd.Timestamp, float, str]]] = defaultdict(list)
    for r in _rows(MODIFIERS):
        t = _ts(r.get("t"))
        try:
            m = float(r.get("multiplier"))
        except (TypeError, ValueError):
            continue
        if t is None or not math.isfinite(m) or not r.get("sleeve"):
            continue
        mods[str(r["sleeve"])].append((t, m, str(r.get("category") or "?")))
    if not mods:
        return {"status": UNMEASURED, "why": f"{MODIFIERS.name} absent or empty on this host"}
    for v in mods.values():
        v.sort(key=lambda x: x[0])
    joined: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for t in trades:
        rows = mods.get(t["sleeve"])
        if not rows:
            continue
        i = int(np.searchsorted([x[0].value for x in rows], t["t"].value, side="right")) - 1
        if i < 0:
            continue
        _when, m, cat = rows[i]
        joined[cat].append((m, t["r"]))
    if not joined:
        return {"status": UNMEASURED,
                "why": "no trade of the book falls after a modifier row of its own sleeve"}
    out: dict[str, Any] = {}
    for cat, pairs in sorted(joined.items()):
        m = np.asarray([p[0] for p in pairs], dtype=float)
        r = np.asarray([p[1] for p in pairs], dtype=float)
        curve = {}
        for lam in LAMBDAS:
            ml = np.clip(1.0 + lam * (m - 1.0), 0.0, None)
            mean = float(ml.mean())
            h = FALLBACK_H * (ml / mean if mean > 0 else np.ones_like(ml))
            g = np.log1p(np.clip(h * r, -0.99, None))
            curve[str(lam)] = round(float(g.mean()), 8)
        base = curve["1.0"]
        out[cat] = {"n": len(pairs), "elog_per_trade_by_lambda": curve,
                    "relaxed_minus_applied": round(curve["0.5"] - base, 8),
                    "removed_minus_applied": round(curve["0.0"] - base, 8),
                    "tightened_minus_applied": round(curve["1.5"] - base, 8),
                    "reads": ("the multiplier's DISPERSION, relaxed/tightened at the same mean "
                              "heat; its LEVEL is the allocator's and is not re-priced here")}
    return {"status": "MEASURED", "h_basis": f"FALLBACK_H={FALLBACK_H} per R, said",
            "categories": out}


def cited() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, path in CITED.items():
        doc = _read(path)
        if not isinstance(doc, dict):
            out[name] = {"status": UNMEASURED, "why": f"{path.name} absent on this host"}
            continue
        out[name] = {"status": "PRESENT", "path": str(path.relative_to(BASE)),
                     "at": doc.get("generated_at") or doc.get("generated_utc") or doc.get("at"),
                     "keys": sorted(doc)[:20]}
    return out


# ==================================================================================== run ===
def build(*, dry_run: bool = False, budget_s: float = 600.0) -> dict[str, Any]:
    started = time.monotonic()
    trades, notes = load_trades()
    specs = parent_specs()
    doc: dict[str, Any] = {
        "at": _now(), "organ": "desks/mt5/research/residual_search.py",
        "scope": ("RESEARCH FINDINGS ONLY: changes no sizing, admission or live policy; its "
                  "conditioned cells go to the gauntlet through the proposer door, and its "
                  "counterfactuals are read by research/residual_queue.py, never by the gateway, "
                  "promoter, admission or allocator"),
        "inputs": {**notes, "certified_parent_specs": len(specs)},
    }
    if len(trades) < MIN_BUCKET_N:
        doc["residual"] = {"status": UNMEASURED,
                           "why": (f"{len(trades)} book trades on the bar clock on this host; "
                                   f"the search needs >= {MIN_BUCKET_N} (shadow ledgers "
                                   "reports/shadow/ledger_*.json and data/live_ledger.jsonl)")}
    else:
        model = residualise(trades, specs)
        labels = label(trades)
        found = search(trades)
        kids, skipped = children(trades, found["findings"], specs)
        doc["residual"] = {"status": "MEASURED", "model": model, "labels": labels, **found,
                           "conditioned_cells": emit(kids, dry_run=dry_run,
                                                     budget_s=budget_s),
                           "children_not_expressible": dict(skipped)}
    doc["counterfactual_policy"] = {"gates": gate_policy(),
                                    "capital_modifiers": modifier_policy(trades),
                                    "cited_organs": cited()}
    doc["elapsed_s"] = round(time.monotonic() - started, 2)
    return doc


def run(*, dry_run: bool = False, budget_s: float = 600.0, out: Path | None = None
        ) -> dict[str, Any]:
    doc = build(dry_run=dry_run, budget_s=budget_s)
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(target)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(dry_run=args.dry_run, budget_s=args.budget_s, out=args.out)
    res = doc["residual"]
    gp = doc["counterfactual_policy"]["gates"]
    print(f"residual_search: residual={res.get('status')} trades={doc['inputs'].get('n_trades')} "
          f"tests={res.get('tests_run')} findings={len(res.get('findings') or [])} "
          f"children={(res.get('conditioned_cells') or {}).get('children_named')} "
          f"gates={gp.get('status')}:{len(gp.get('gates') or {})} -> {args.out or OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
