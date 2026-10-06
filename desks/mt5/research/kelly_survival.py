#!/usr/bin/env python3
"""MAXIMUM AGGRESSION INSIDE SURVIVAL: the gold book's size per window, per venue.

The principal, 2026-09-30, after the survival-vs-Kelly arithmetic: "i dont want timidness but
i want maximum aggressiveness within survival". This organ is that sentence as a solve:

    maximise   ruin-counted posterior E[log W]          (Fusion)
               P(pass the challenge)                    (E8, a barrier game, where log wealth
                                                         is the wrong objective)
    subject to P(death within HORIZON) <= EPS_DEATH     (Fusion; E8's death is its own barrier)

over the three GOLD_WINDOWS, each window either OFF or at a size the venue can actually send.
Survival is the only thing that may take size away; everything else is growth's call.

WHY THIS CAN CUT A WINDOW, AND WHY THAT IS NOT TIMID. Full Kelly is the fastest-growing size
there is: betting above it lowers E[log W] AND raises ruin, so it is less aggressive in the only
sense that compounds. Measured 2026-09-30 on the allocator's worlds with live-updated posteriors:
the three windows at the 0.02-lot floor are ~24% heat on EUR 583, 2.7x full Kelly, at +0.65%/day
with 3.9% 60-day ruin; gold_asia alone at the floor (~9% heat, ~full Kelly) is +1.10%/day with
none. The 0.02 floor means a window is 0 or >= ~8% heat, so the only way to be AT Kelly is to
choose WHICH windows trade. Growth governance Rule 1 is met by construction: a window leaves
only when the solve measures that leaving raises E[log W], and the artifact carries that
missed-growth line (`vs_today`). Rule 2 is met the same way: sizes above the floor are in the
search, and a window whose live edge grows comes back on the next pass with no human act.

INPUTS, all the desk's own:

    worlds    data/pf_allocator_cache/worlds.npz   the allocator's world population (prior)
    live      data/live_ledger.jsonl               realised R per window, attributed by
                                                   `attribution_reconcile.attribute`
    equity    data/gateway_state.json (Fusion), reports/E8_GOLD.json (E8)
    floor     live_ledger risk per lot per window (measured), else decision_core constants

    -> reports/KELLY_SURVIVAL.json

The gateway and the E8 executor read it through `mt5desk.kelly_sizing.load_kelly_survival`, which
returns None -- today's behaviour, unchanged -- when the artifact is absent, stale or unreadable.

    python desks/mt5/research/kelly_survival.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

WORLDS = BASE / "data" / "pf_allocator_cache" / "worlds.npz"
LEDGER = BASE / "data" / "live_ledger.jsonl"
GATEWAY_STATE = BASE / "data" / "gateway_state.json"
ACCOUNT = BASE / "data" / "account_state.json"
E8_REPORT = BASE / "reports" / "E8_GOLD.json"
OUT = BASE / "reports" / "KELLY_SURVIVAL.json"

WINDOWS = ("asia", "london_am", "afternoon")
#: Fusion horizon in trading days and the path count. 60 days is long enough for a correlated
#: losing run to show and short enough that the worlds' 256 rows give independent blocks.
HORIZON = 60
N_PATHS = 4000
#: THE DEATH LINE. Below 20% of starting equity the 0.02-lot floor is >= ~40% risk per trade on
#: this book, so the account cannot place a survivable order again: that is ruin in practice,
#: long before equity touches zero or the broker's stop-out needs to act.
DEATH_LINE = 0.20
#: Allowed probability of crossing it within HORIZON. The desk's own tolerance for a stop-out
#: event (`posterior_growth.EPS_STOP`, 5%). EPS_RUIN (1e-3 per 5 days) was tried first and no
#: tradable gold size on a EUR ~560 account meets it -- a 0.01-lot gold_asia bracket alone
#: crosses the death line on 2.3% of 60-day paths -- so it would have answered "trade nothing",
#: which is the one answer that cannot compound.
from libs.portfolio.posterior_growth import EPS_STOP as EPS_DEATH  # noqa: E402
#: Fusion size grid, in lots per window (0 = OFF). 0.01 is the venue minimum and 0.02 the
#: principal's policy floor; the principal put survival above that floor on 2026-09-30, so the
#: venue minimum is in the grid and the solve says which one survival allows. Above the floor
#: the search is free, so a strong window can be sized UP (Rule 2).
FUSION_LOTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08)
GOLD_MIN_LOT = 0.02
#: E8 Pro rules (docs/PROP_FIRM_E8.md), in dollars of the $100,000 initial balance: +10% target,
#: $90,000 static floor, 2.5% daily breach, 2% daily profit cap stripped at rollover. The
#: barriers are placed relative to the account's CURRENT equity, which is not the initial one.
E8_INITIAL, E8_TARGET_USD, E8_FLOOR_USD = 100_000.0, 110_000.0, 90_000.0
E8_DAILY_BREACH, E8_DAILY_CAP = 0.025, 0.02
#: Survival on E8 is P(the account fails) = P(floor) + P(daily breach), held to EPS_DEATH; inside
#: it, the fastest median pass wins (aggression), P(pass) breaking ties.
E8_DAYS = 256
E8_PATHS = 2000
E8_RISKS = (0.0, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015)
#: Absurd R values are unit errors in the ledger (FX rows have read -15,889R), never evidence.
MAX_ABS_R = 20.0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def deal_r(d: dict[str, Any]) -> float | None:
    """A deal's realised R: the ledger's own, else P/L over the risk it recorded, else None."""
    r = _num(d.get("r_multiple"))
    if r is not None and r != 0.0 and abs(r) <= MAX_ABS_R:
        return r
    pl, risk = _num(d.get("pl_quote")), _num(d.get("risk_quote"))
    if pl is not None and risk:
        rr = pl / abs(risk)
        if abs(rr) <= MAX_ABS_R:
            return rr
    return None


def live_evidence(deals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per window: realised R list and the measured quote risk per lot, from attributed deals."""
    from attribution_reconcile import attribute
    names = [f"gold_{w}" for w in WINDOWS]
    gold = [d for d in deals if str(d.get("symbol") or "").upper().startswith("XAU")
            and str(d.get("account_kind") or "live") == "live"]
    out: dict[str, dict[str, Any]] = {w: {"r": [], "risk_per_lot": []} for w in WINDOWS}
    for row, d in zip(attribute(gold, names), gold, strict=True):
        name = str(row.get("sleeve") or "")
        if not name.startswith("gold_"):
            continue
        w = name[len("gold_"):]
        if w not in out:
            continue
        r = deal_r(d)
        if r is not None:
            out[w]["r"].append(r)
        risk, vol = _num(d.get("risk_quote")), _num(d.get("volume"))
        if risk and vol:
            out[w]["risk_per_lot"].append(abs(risk) / vol)
    return out


def posterior_shift(prior_mean: float, live_r: list[float]) -> tuple[float, float]:
    """(posterior mean, live weight) on the desk's own convention: the prior is worth K_SLEEVE
    observations and each live trade counts LIVE_WEIGHT times (posterior_growth)."""
    from libs.portfolio.posterior_growth import K_SLEEVE, LIVE_WEIGHT
    n = len(live_r)
    if n == 0:
        return prior_mean, 0.0
    w = LIVE_WEIGHT * n / (LIVE_WEIGHT * n + K_SLEEVE)
    return prior_mean + w * (float(np.mean(live_r)) - prior_mean), w


def fusion_equity() -> tuple[float | None, str]:
    for path, key in ((GATEWAY_STATE, "equity"), (ACCOUNT, "equity")):
        doc = _read_json(path)
        v = _num(doc.get(key)) if isinstance(doc, dict) else None
        if v and v > 0:
            return v, f"{path.name}:{key}"
    return None, "UNMEASURED: no equity in gateway_state.json or account_state.json"


def e8_equity() -> tuple[float | None, str]:
    doc = _read_json(E8_REPORT)
    v = _num(doc.get("equity")) if isinstance(doc, dict) else None
    return (v, "E8_GOLD.json:equity") if v and v > 0 else (None, "UNMEASURED: no E8 equity")


def ruin_counted_elog(r: np.ndarray, h: np.ndarray) -> tuple[float, float, float]:
    """(E[log W]/day with a dead path scored at the death line, P(death), P(-35% drawdown))."""
    x = 1.0 + r @ h                                          # (paths, days)
    logs = np.log(np.clip(x, 1e-12, None))
    cum = np.cumsum(logs, axis=1)
    low = cum.min(axis=1)
    dead = low <= math.log(DEATH_LINE)
    lw = np.where(dead, math.log(DEATH_LINE), cum[:, -1])
    return (float(lw.mean()) / r.shape[1], float(dead.mean()),
            float((low <= math.log(0.65)).mean()))


def e8_barrier(r: np.ndarray, h: np.ndarray, equity: float = E8_INITIAL
               ) -> dict[str, float | None]:
    """P(pass), P(static floor), P(daily breach), median days to pass, on E8 Pro's rules."""
    target, floor = E8_TARGET_USD / equity, E8_FLOOR_USD / equity
    day = np.minimum(r @ h, E8_DAILY_CAP)
    n, t_n = day.shape
    bal = np.ones(n)
    state = np.zeros(n, dtype=int)                           # 0 live, 1 pass, 2 daily, 3 floor
    days = np.full(n, t_n)
    for t in range(t_n):
        live = state == 0
        if not live.any():
            break
        breach = day[:, t] <= -E8_DAILY_BREACH
        bal = np.where(live, bal * (1.0 + day[:, t]), bal)
        f_d = live & breach
        f_s = live & ~breach & (bal <= floor)
        win = live & ~f_d & ~f_s & (bal >= target)
        state[f_d], state[f_s], state[win] = 2, 3, 1
        days[f_d | f_s | win] = t + 1
    passed = state == 1
    return {"p_pass": float(passed.mean()), "p_floor": float((state == 3).mean()),
            "p_daily": float((state == 2).mean()),
            "median_days": float(np.median(days[passed])) if passed.any() else None}


def solve(*, seed: int = 0) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "objective": "max ruin-counted E[log W] s.t. P(death) <= eps (Fusion);"
                                        " fastest median pass s.t. P(fail) <= eps (E8)",
                           "death_line": DEATH_LINE, "eps_death": EPS_DEATH,
                           "horizon_days": HORIZON, "status": "OK"}
    try:
        z = np.load(WORLDS, allow_pickle=True)
    except (OSError, ValueError) as exc:
        doc["status"] = f"UNMEASURED: worlds unreadable ({type(exc).__name__})"
        return doc
    names = [str(n) for n in z["names"]]
    cols = [f"gold_{w}" for w in WINDOWS]
    missing = [c for c in cols if c not in names]
    if missing:
        doc["status"] = f"UNMEASURED: worlds carry no column for {missing}"
        return doc
    idx = [names.index(c) for c in cols]
    r = np.asarray(z["r"], dtype=float)[:, :, idx]            # (worlds, rows, 3)
    deals = []
    try:
        with LEDGER.open(encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if text:
                    try:
                        deals.append(json.loads(text))
                    except ValueError:
                        continue
    except OSError:
        pass
    ev = live_evidence(deals)
    post: dict[str, Any] = {}
    for k, w in enumerate(WINDOWS):
        prior = float(r[:, :, k].mean())
        mean, weight = posterior_shift(prior, ev[w]["r"])
        r[:, :, k] += mean - prior
        post[w] = {"prior_r": round(prior, 4), "live_n": len(ev[w]["r"]),
                   "live_mean_r": (round(float(np.mean(ev[w]["r"])), 4) if ev[w]["r"] else None),
                   "live_weight": round(weight, 3), "posterior_r": round(mean, 4)}
    doc["posterior"] = post

    rng = np.random.default_rng(seed)
    n_w, n_rows, _ = r.shape
    wi = rng.integers(0, n_w, N_PATHS)
    start = rng.integers(0, n_rows - HORIZON + 1, N_PATHS)
    paths = r[wi[:, None], start[:, None] + np.arange(HORIZON)[None, :], :]

    # ---------------------------------------------------------------- Fusion
    from mt5desk.decision_core import CONTRACT_OZ, DIST_USD, FX_EUR
    equity, eq_src = fusion_equity()
    fus: dict[str, Any] = {"equity_eur": equity, "equity_source": eq_src}
    if equity:
        eur_per_lot = {}
        for w in WINDOWS:
            per_lot = ev[w]["risk_per_lot"]
            quote = float(np.median(per_lot)) if per_lot else DIST_USD * CONTRACT_OZ
            eur_per_lot[w] = quote * FX_EUR
        fus["risk_eur_per_lot"] = {w: round(v, 2) for w, v in eur_per_lot.items()}
        best: tuple[float, tuple[float, ...], tuple[float, float, float]] | None = None
        table = []
        for lots in itertools.product(FUSION_LOTS, repeat=len(WINDOWS)):
            h = np.array([lots[k] * eur_per_lot[w] / equity for k, w in enumerate(WINDOWS)])
            el, p_dead, p_dd = ruin_counted_elog(paths, h)
            row = {"lots": dict(zip(WINDOWS, lots, strict=True)), "heat": round(float(h.sum()), 4),
                   "elog_per_day": round(el, 6), "p_death": round(p_dead, 4),
                   "p_dd35": round(p_dd, 4), "survives": p_dead <= EPS_DEATH}
            table.append(row)
            # Ties go to the larger book: at equal growth, aggression wins.
            if row["survives"] and (best is None or el > best[0] + 1e-9 or (
                    abs(el - best[0]) <= 1e-9 and h.sum() > sum(best[1]))):
                best = (el, tuple(float(x) for x in h), (el, p_dead, p_dd))
        today = next(t for t in table if all(t["lots"][w] == GOLD_MIN_LOT for w in WINDOWS))
        if best is None:
            fus["status"] = "NO_SURVIVING_BOOK: every size crosses the death line; today stands"
        else:
            chosen = next(t for t in table if abs(t["heat"] - round(sum(best[1]), 4)) < 1e-9
                          and abs(t["elog_per_day"] - round(best[0], 6)) < 1e-12)
            fus.update({
                "status": "OK",
                "windows": {w: {"lots": chosen["lots"][w], "heat": round(best[1][k], 5)}
                            for k, w in enumerate(WINDOWS)},
                "chosen": chosen, "today": today,
                # THE MISSED-GROWTH LINE (growth governance Rule 1): what moving from today's
                # book to the chosen one does to robust forward E[log W], measured, per day.
                "vs_today": {"delta_elog_per_day": round(chosen["elog_per_day"]
                                                         - today["elog_per_day"], 6),
                             "delta_p_death": round(chosen["p_death"] - today["p_death"], 4)},
            })
        fus["top"] = sorted(table, key=lambda t: -t["elog_per_day"])[:8]
    else:
        fus["status"] = eq_src
    doc["fusion"] = fus

    # ---------------------------------------------------------------- E8
    e8: dict[str, Any] = {}
    eq8, src8 = e8_equity()
    e8["equity_usd"], e8["equity_source"] = eq8, src8
    wi8 = rng.integers(0, n_w, E8_PATHS)
    r8 = r[wi8]                                                # a full world-year per path
    days = min(E8_DAYS, r8.shape[1])
    r8 = r8[:, :days, :]
    eq_e8 = eq8 or E8_INITIAL
    best8: tuple[tuple[float, float], tuple[float, ...], dict[str, Any]] | None = None
    for risks in itertools.product(E8_RISKS, repeat=len(WINDOWS)):
        if not any(risks):
            continue
        res = e8_barrier(r8, np.array(risks), eq_e8)
        if (res["p_floor"] or 0.0) + (res["p_daily"] or 0.0) > EPS_DEATH:
            continue
        md = res["median_days"] if res["median_days"] is not None else float("inf")
        key = (-md, res["p_pass"] or 0.0)
        if best8 is None or key > best8[0]:
            best8 = (key, risks, res)
    today8 = e8_barrier(r8, np.array([0.005] * len(WINDOWS)), eq_e8)
    if best8 is None:
        e8["status"] = "NO_SURVIVING_BOOK: every size fails the account too often; today stands"
    else:
        e8.update({"status": "OK",
                   "windows": {w: {"risk_frac": best8[1][k]} for k, w in enumerate(WINDOWS)},
                   "chosen": best8[2], "today": today8,
                   "vs_today": {"delta_p_pass": round((best8[2]["p_pass"] or 0.0)
                                                      - (today8["p_pass"] or 0.0), 4)}})
    doc["e8"] = e8
    return doc


# ====================================================================== THE WHOLE CERTIFIED BOOK
#: The same rule over every certified sleeve the desk may trade, not only the gold windows
#: (principal 2026-10-06: "all promising max uncorrelated pf sleeves out of current certis ... put
#: them on mt5 n e8 early, the max growth n promising sleeve book"). Same objective, same death
#: line, same EPS_DEATH, on the allocator's own worlds. Two additions, both from measurement:
#:
#: SURVIVAL MUST SURVIVE BEING WRONG. The worlds' levels read high (shrunk but in-sample means), so
#: the death constraint is held on the as-estimated worlds AND on worlds whose positive edges are
#: halved; growth is maximised on the as-estimated ones. A book that only survives if its edges are
#: exactly right is not inside survival.
#:
#: AN EXACT SEARCH, NOT A GRADIENT. The smooth projected-gradient solve stalled 4x below the exact
#: optimum on this roster (measured 2026-10-06), and the allocator's own robust_elog can report
#: converged at a worse point while its redundancy penalty is non-PSD. The book is therefore found
#: by multi-start pattern search on the exact ruin-counted objective (coordinate steps plus pairwise
#: heat transfers, which escape the coordinate traps), and its P(death) is re-measured on an
#: independent path sample before it is published.
#: The canonical certificate store (certificate_truth.CANONICAL_CERTIFICATE_STORE) first; the
#: sealed canon copy only when the store is unreadable. On 2026-10-06 the box's store held 847
#: certificates while git's canon held 52, so reading the canon first would solve a stale world.
CERT_STORE = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CERT_CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
#: Certificates the allocator never priced are priced here by the gauntlet's own replay
#: (`pf_allocator.certified_evidence`), cached for a day, and the strongest decorrelated ones join
#: the search. The pairwise search is O(n^2), so the newcomers are pre-screened: positive mean,
#: correlation <= BOOK_MAX_CORR to every column already in, best daily Sharpe first.
CERT_REPLAY_CACHE = BASE / "data" / "pf_allocator_cache" / "cert_book_r.parquet"
CERT_REPLAY_MAX_AGE_S = 86_400
BOOK_MAX_NEW = 24
BOOK_MAX_CORR = 0.7
BOOK_HAIRCUT = 0.5
BOOK_MARGIN = 0.04            # solve against 4% so an independent sample still reads <= EPS_DEATH
BOOK_STEPS = (0.04, 0.02, 0.01, 0.005, 0.0025)
BOOK_STARTS = 6
BOOK_PATHS = 2000


def _world_column(cell: str, sym: str, family: str, selector: str, names: list[str]) -> str | None:
    """The worlds column a certificate trades: `<SYM>_<family>_<selector>`, the allocator's own
    naming. rr/wait variants of one cell share the column -- they are one bet bought twice."""
    col = f"{sym}_{family}_{selector}"
    return col if col in names else None


def certified_roster(names: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """(world columns, one screening row per certificate) for the non-banned certified sleeves."""
    doc = _read_json(CERT_STORE) or {}
    source = CERT_STORE.name
    if not doc.get("survivors"):
        doc, source = _read_json(CERT_CANON) or {}, CERT_CANON.name
    try:
        from family_policy import family_banned
    except ImportError:                                   # pragma: no cover - box path only
        def family_banned(_f: str) -> bool:
            return _f == "discovered"
    cols: list[str] = []
    rows: list[dict[str, Any]] = []
    policy = str((doc.get("gate_policy") or {}).get("version") or "")
    for key, c in (doc.get("survivors") or {}).items():
        spec = c.get("shadow_spec") or {}
        parts = str(key).split(".")
        # Store rows may carry no family field; the key is `external.SYM.family.p=...`.
        fam = str(spec.get("family") or (parts[2] if len(parts) > 2 else ""))
        sym = str(c.get("sym") or spec.get("symbol") or (parts[1] if len(parts) > 1 else ""))
        sel = str(spec.get("selector") or "")
        tf = str(spec.get("timeframe") or "H1").upper()
        g = c.get("gates") or {}
        row = {"certificate": key, "store": source, "symbol": sym, "family": fam,
               "selector": sel,
               "policy": policy, "v4": "v4" in policy,
               "edge_x3_costs": (g.get("stress_costs") or {}).get("exp_x3"),
               "wf_oos_sharpe": (g.get("walk_forward") or {}).get("oos_sharpe"),
               "dsr": (g.get("deflated_sharpe") or {}).get("dsr")}
        if family_banned(fam):
            row["excluded"] = "banned family"
        elif tf == "M15":
            row["excluded"] = "M15 banned"
        else:
            col = _world_column(str(c.get("cell") or ""), sym, fam, sel, names)
            row["column"] = col
            if col is None:
                row["excluded"] = "UNPRICED: the allocator's worlds carry no column for it"
            elif col not in cols:
                cols.append(col)
        rows.append(row)
    return cols, rows


def _replayed_certificates() -> tuple[dict[str, Any], str]:
    """Daily-R series for every certificate, replayed the gauntlet's way, cached for a day."""
    import pandas as pd
    try:
        if CERT_REPLAY_CACHE.exists() and \
                (datetime.now(tz=UTC).timestamp() - CERT_REPLAY_CACHE.stat().st_mtime
                 < CERT_REPLAY_MAX_AGE_S):
            df = pd.read_parquet(CERT_REPLAY_CACHE)
            return {c: df[c].dropna() for c in df.columns}, "replay cache"
    except (OSError, ValueError):
        pass
    try:
        from pf_allocator import certified_evidence
        series, acct = certified_evidence()
    except Exception as exc:                              # the box path; fail closed, named
        return {}, f"replay unavailable ({type(exc).__name__}: {exc})"
    if series:
        try:
            CERT_REPLAY_CACHE.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(series).to_parquet(CERT_REPLAY_CACHE)
        except (OSError, ValueError):
            pass
    return series, (f"replayed {acct.get('priced')}/{acct.get('certificates')} certificates, "
                    f"{len(acct.get('refused') or {})} refused")


def _extend_worlds(r: np.ndarray, cols: list[str], screen: list[dict[str, Any]],
                   seed: int) -> tuple[np.ndarray, list[str], str]:
    """Add the strongest decorrelated UNPRICED certificates to the world tensor.

    The newcomers are drawn as their own joint population from their replayed daily R
    (`robust_elog.sample_worlds`, the allocator's sampler) and paired world-for-world, row-for-row
    with the allocator's tensor. Pairing two populations drawn apart keeps each side's internal
    co-movement and treats new-vs-old as independent: it UNDERSTATES their correlation with the
    priced book, so the pre-screen below admits only newcomers decorrelated among themselves,
    and the allocator pricing them properly supersedes this on its next pass.
    """
    wanted = sorted({f"{row['symbol']}_{row['family']}_{row['selector']}"
                     for row in screen if str(row.get("excluded", "")).startswith("UNPRICED")})
    if not wanted:
        return r, cols, "every certificate already priced"
    series, why = _replayed_certificates()
    have = {k: v for k, v in series.items() if k in wanted and len(v) >= 60}
    if not have:
        return r, cols, f"{len(wanted)} unpriced; none replayable ({why})"
    import pandas as pd
    df = pd.DataFrame(have).sort_index().fillna(0.0)
    mu, sd = df.mean(), df.std()
    rank = [c for c in (mu / sd.replace(0, np.nan)).dropna().sort_values(ascending=False).index
            if mu[c] > 0]
    corr = df.corr()
    pick: list[str] = []
    for c in rank:
        if all(abs(corr.loc[c, p]) <= BOOK_MAX_CORR for p in pick):
            pick.append(c)
        if len(pick) >= BOOK_MAX_NEW:
            break
    if not pick:
        return r, cols, f"{len(have)} replayed; none with a positive mean"
    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds
    ev = [SleeveEvidence(name=c, daily_r=df[c].to_numpy(float),
                         family=c.split("_", 1)[-1].rsplit("_", 1)[0], symbol=c.split("_")[0])
          for c in pick]
    w = sample_worlds(ev, WorldConfig(seed=seed, n_worlds=r.shape[0], n_rows=r.shape[1]))
    new = np.asarray(w.r, dtype=float)
    n_w, n_t = min(new.shape[0], r.shape[0]), min(new.shape[1], r.shape[1])
    r2 = np.concatenate([r[:n_w, :n_t, :], new[:n_w, :n_t, :]], axis=2)
    for row in screen:
        name = f"{row['symbol']}_{row['family']}_{row['selector']}"
        if name in pick:
            row["column"] = name
            row["excluded"] = None
            row["priced_by"] = "replay (independent of the allocator's worlds)"
    return r2, cols + pick, (f"{len(wanted)} unpriced, {len(have)} replayed, {len(pick)} joined "
                             f"({why})")


def _book_eval(paths: np.ndarray, h: np.ndarray) -> dict[str, float]:
    el, p_dead, p_dd = ruin_counted_elog(paths, h)
    return {"elog_per_day": round(el, 6), "p_death": round(p_dead, 4), "p_dd35": round(p_dd, 4)}


def _pattern_search(paths: np.ndarray, paths_h: np.ndarray, mask: np.ndarray, cap: float,
                    rng: np.random.Generator, starts: int | None = None
                    ) -> tuple[np.ndarray, float]:
    starts = BOOK_STARTS if starts is None else starts
    n = mask.size
    idx = np.flatnonzero(mask)

    def val(h: np.ndarray) -> float:
        if np.any(h[~mask] > 0) or np.any(h > cap + 1e-12):
            return -math.inf
        el, p_dead, _ = ruin_counted_elog(paths, h)
        if p_dead > BOOK_MARGIN or ruin_counted_elog(paths_h, h)[1] > BOOK_MARGIN:
            return -math.inf
        return el

    best_h, best_v = np.zeros(n), val(np.zeros(n))
    for s in range(starts):
        h = np.zeros(n)
        h[idx] = 0.01 if s == 0 else rng.dirichlet(np.ones(idx.size)) * rng.uniform(0.1, 0.8)
        h = np.minimum(h, cap)
        while val(h) == -math.inf and h.sum() > 1e-4:
            h *= 0.9
        cur = val(h)
        for step in BOOK_STEPS:
            moved = True
            while moved:
                moved = False
                for i in idx:
                    for d in (step, -step):
                        t = h.copy()
                        t[i] = max(0.0, t[i] + d)
                        v = val(t)
                        if v > cur + 1e-9:
                            h, cur, moved = t, v, True
                for i in idx:
                    for j in idx:
                        if i != j and h[i] >= step:
                            t = h.copy()
                            t[i] -= step
                            t[j] += step
                            v = val(t)
                            if v > cur + 1e-9:
                                h, cur, moved = t, v, True
        if cur > best_v:
            best_h, best_v = h, cur
    return best_h, best_v


def solve_book(*, seed: int = 0) -> dict[str, Any]:
    """The max-growth book over the certified roster, per venue, inside survival (see above)."""
    out: dict[str, Any] = {"status": "OK", "haircut_for_survival": BOOK_HAIRCUT,
                           "margin": BOOK_MARGIN}
    try:
        z = np.load(WORLDS, allow_pickle=True)
    except (OSError, ValueError) as exc:
        return {"status": f"UNMEASURED: worlds unreadable ({type(exc).__name__})"}
    names = [str(x) for x in z["names"]]
    gold = [f"gold_{w}" for w in WINDOWS if f"gold_{w}" in names]
    cert_cols, screen = certified_roster(names)
    cols = gold + [c for c in cert_cols if c not in gold]
    r = np.asarray(z["r"], dtype=float)[:, :, [names.index(c) for c in cols]]
    r, cols, out["unpriced"] = _extend_worlds(r, cols, screen, seed)
    if not cols:
        return {"status": "UNMEASURED: no certified sleeve is priced", "screen": screen}
    deals: list[dict[str, Any]] = []
    try:
        with LEDGER.open(encoding="utf-8") as fh:
            deals = [json.loads(t) for t in (ln.strip() for ln in fh) if t.startswith("{")]
    except (OSError, ValueError):
        deals = []
    ev = live_evidence(deals)
    post: dict[str, Any] = {}
    for k, c in enumerate(cols):
        if c.startswith("gold_"):
            live_r = ev.get(c[len("gold_"):], {}).get("r", [])
        else:
            pre = "_".join(c.lower().split("_")[:-1])           # the column minus its selector
            live_r = [x for d in deals if str(d.get("sleeve") or "").lower().startswith(pre)
                      and str(d.get("account_kind") or "live") == "live"
                      for x in [deal_r(d)] if x is not None]
        prior = float(r[:, :, k].mean())
        mean, weight = posterior_shift(prior, live_r)
        r[:, :, k] += mean - prior
        post[c] = {"prior_r": round(prior, 4), "live_n": len(live_r),
                   "posterior_r": round(mean, 4), "live_weight": round(weight, 3)}
    mu = r.mean(axis=(0, 1))
    r_h = r - BOOK_HAIRCUT * np.maximum(mu, 0.0)
    rng = np.random.default_rng(seed)

    def draw(t: np.ndarray, m: int, g: np.random.Generator) -> np.ndarray:
        wi = g.integers(0, t.shape[0], m)
        st = g.integers(0, t.shape[1] - HORIZON + 1, m)
        return t[wi[:, None], st[:, None] + np.arange(HORIZON)[None, :], :]

    g1, g2 = np.random.default_rng(seed + 1), np.random.default_rng(seed + 2)
    p_s, ph_s = draw(r, BOOK_PATHS, g1), draw(r_h, BOOK_PATHS, np.random.default_rng(seed + 1))
    p_v = draw(r, 2 * BOOK_PATHS, g2)
    ph_v = draw(r_h, 2 * BOOK_PATHS, np.random.default_rng(seed + 2))
    flat = r.reshape(-1, len(cols))
    corr = np.corrcoef(flat.T)
    sd = flat.std(0)

    def k_eff(h: np.ndarray) -> float:
        x = h * sd
        v = float(x @ corr @ x)
        return round(float(x.sum()) ** 2 / v, 3) if v > 0 else 0.0

    from mt5desk.sizing import MAX_RISK_FRAC
    live_mix = flat[:, :len(gold)].sum(1) if gold else np.zeros(flat.shape[0])
    out.update({"columns": cols, "posterior": post, "screen": screen,
                "per_sleeve_cap": MAX_RISK_FRAC,
                "corr_to_live_gold": {c: round(float(np.corrcoef(live_mix, flat[:, i])[0, 1]), 3)
                                      for i, c in enumerate(cols)} if gold else {}})
    try:
        from prop.e8_book import _cached_catalogue
        e8_symbols = _cached_catalogue()
    except Exception:                                     # optional on any host
        e8_symbols = None
    venues = {"fusion": np.ones(len(cols), dtype=bool)}
    if e8_symbols:
        venues["e8"] = np.array([c.startswith("gold_") or c.split("_")[0] in e8_symbols
                                 for c in cols])
    for venue, mask in venues.items():
        h, v = _pattern_search(p_s, ph_s, mask, MAX_RISK_FRAC, rng)
        out[venue] = {"status": "OK" if v > -math.inf else "NO_SURVIVING_BOOK",
                      "heat": {c: round(float(h[i]), 4) for i, c in enumerate(cols) if h[i] > 0},
                      "total_heat": round(float(h.sum()), 4), "k_eff": k_eff(h),
                      "as_estimated": _book_eval(p_v, h), "edges_halved": _book_eval(ph_v, h)}
        if out[venue]["as_estimated"]["p_death"] > EPS_DEATH:
            out[venue]["status"] = "VALIDATION_FAILED: independent sample breaches EPS_DEATH"
    if "e8" not in venues:
        out["e8"] = {"status": "UNMEASURED: no cached E8 catalogue (prop/e8_book.py)"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--book", action="store_true",
                    help="also solve the whole certified book (the `book` block; readers that "
                         "size the gold windows ignore it)")
    a = ap.parse_args(argv)
    doc = solve()
    if a.book:
        doc["book"] = solve_book()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    tmp.replace(a.out)
    fus, e8 = doc.get("fusion") or {}, doc.get("e8") or {}
    print(f"kelly_survival: {doc['status']} -- fusion {fus.get('status')} "
          f"{ {w: v['lots'] for w, v in (fus.get('windows') or {}).items()} }; "
          f"e8 {e8.get('status')} { {w: v['risk_frac'] for w, v in (e8.get('windows') or {}).items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
