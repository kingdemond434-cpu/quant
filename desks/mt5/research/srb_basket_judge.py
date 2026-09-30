"""Judge session_range_breakout as a PORTFOLIO of legs, not one leg at a time.

THE TEST THE SWEEP DID NOT RUN, AND ITS OWN CLOSING OBSERVATION.
`reports/SRB_UNCORRELATED_SWEEP.json` minted 344 `session_range_breakout` cells over 144
hypothesis-lane instruments in 37 correlation blocks, judged 262 through the sealed gauntlet and
passed ZERO -- 165 dead at `in_sample_screen`, 97 at `deflated_sharpe`. Its control arm
re-derived gold's own certified window from gold's own clock, reproduced the standing
certificate's Sharpe to four decimals (0.1846 against 0.1845), and that failed too, at
`deflated_sharpe`, dsr=0.0 against the sealed hurdle sr0=0.3122. Every one of those verdicts was
of ONE LEG. The sweep's own `what_would_change_the_answer` names the missing test:

    "combining several uncorrelated cells into ONE portfolio series before judging -- the sum of
     8 near-zero-correlated 0.10-Sharpe legs has a materially higher Sharpe than any leg"

This organ builds that series and puts it through the SAME sealed judge, unmodified, as a single
cell. `external_gauntlet` is imported as a library and never edited; `gate_spec.yaml` is not
touched; the deflated-Sharpe hurdle is the sealed fixed one (n_trials and variance_of_sharpes are
both pinned by policy, so a basket's bar is identical to a leg's bar -- 0.3122 either way).

THE HONESTY PROBLEM IS THE WHOLE JOB, and it is why most of what is below is a refusal.
Picking the best 8 of 262 legs and calling the basket "one trial" is exactly the selection that
made 28 canon certificates collapse. So membership is decided by RULES FIXED IN THIS FILE, every
rule is reported including the ones that lose, and the two rules that select on in-sample
performance are CHARGED with a measured null rather than excused.

    THE CHARGE, AND IT IS THE FINDING. Sign-flip each leg's whole daily series (the family arms
    BOTH sides of the range, so a flip is a legitimate no-edge null that preserves every
    magnitude, every autocorrelation and the covariance structure up to sign), then run the WHOLE
    procedure again -- select by in-sample sign, sum, take the Sharpe. Measured 2026-09-24 over
    400 draws: the positive-sign basket of NO-EDGE legs scores +1.06 on average (p95 +1.30); the
    top-8 basket of no-edge legs scores +1.23 (p95 +1.46). The real baskets score +0.2665 and
    +0.3197. p = 1.0000 both. The in-sample basket's apparent 4x "diversification multiple" is
    selection, not diversification: a coin-flip of these same legs' own magnitudes beats it four
    times over, because the real family's positive legs are its SMALL ones (165 of 262 legs are
    negative, and the negative ones are bigger).

So the in-sample baskets are not evidence and are published as refusals. The rules that ARE
evidence are the split-sample ones: membership is fixed on the first 60% of the union calendar
and the judged series is the last 40% ONLY, so the number the judge sees was never selected on.

COSTS ARE PAID PER LEG, NOT PER BASKET, BY CONSTRUCTION. Every member's daily series is the
gauntlet's own `daily_series(df, sigs, costs)` with that instrument's own `Costs` -- the fill-hour
spread surface where it has one, the pooled median where it does not, both recorded per leg -- so
a basket of 8 pays 8 round trips. The 3x stress arm is the sum of the members' own 3x series, the
same `COST_SCENARIO = 3.0` the sealed gate applies, and it is charged BEFORE the sum, never after.

WHAT IT CANNOT CHARGE, said plainly: the engine models no swap, so `swap_cost` at basket level
reads UNMEASURED (the basket has no symbol to price). The members' own swap verdicts are
reported per basket instead. And `run_gauntlet` truncates its PBO/SPA matrix to the shortest
column, so the split-sample baskets and the full-sample ones are compared over the shorter
window; that is the sealed judge's own behaviour and is recorded, not worked around.

NOTHING IS ADDED TO ANY LIVE BOOK. This calls `run_gauntlet` directly, which writes no gate
ledger, no certificate and no authority file; `data/sleeves.json`, the rosters, the E8 config and
`UNIVERSAL_SURVIVORS*` are not opened.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[3]
MT5 = BASE / "desks" / "mt5"
REPORTS = MT5 / "reports"
SWEEP = REPORTS / "SRB_UNCORRELATED_SWEEP.json"
OUT = REPORTS / "SRB_BASKET_JUDGEMENT.json"
COSTMETA = MT5 / "data" / "srb_basket_leg_costs.json"
#: THE TRIAL CENSUS FOR THIS ORGAN. Every basket handed to the sealed judge is a trial of
#: `session_range_breakout`, and `libs.research.experiment_ledger` reads this file into the
#: lifetime count so the family's deflation sees it. One row per DISTINCT basket identity (rule,
#: weighting, window and the exact member set), written once: re-judging the same basket next
#: hour is the same trial, and charging it again would inflate the count, never correct it.
TRIALS = MT5 / "data" / "srb_basket_trials.jsonl"

for _p in (str(BASE), str(MT5), str(MT5 / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# THE SEALED JUDGE, imported as a library and never modified. The type-ignore is the desk's
# standing spelling for this import (`certificate_truth`, `capacity_frontier` and
# `execution_science` all carry the same one): the module lives under `desks/mt5/scripts/`, which
# is on sys.path at runtime and is not a package mypy can resolve.
import external_gauntlet as G  # type: ignore[import-not-found]  # noqa: E402

FAMILY = "session_range_breakout"

#: The fraction of the union calendar that decides membership for every split-sample rule. Fixed
#: here, not searched: 60/40 is the desk's usual train/test split and moving it would be one more
#: free parameter in a file whose entire subject is free parameters.
TRAIN_FRACTION = 0.6

#: Draws of the sign-flip null that charges the in-sample selection rules. Fixed seed so the
#: charge is reproducible and cannot be re-rolled until it is favourable.
NULL_DRAWS = 400
NULL_SEED = 20260924

#: The ladder of k for the ranked out-of-sample rule. THE WHOLE LADDER IS REPORTED. Reporting one
#: k chosen after seeing the ladder would be the argmax this file exists to refuse.
K_LADDER = (4, 8, 16, 32, 64, 128)


# --------------------------------------------------------------------------- leg series


def _norm_index(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.index = pd.to_datetime(out.index)
    return out


def _cost_meta_load() -> dict[str, Any]:
    try:
        raw = json.loads(COSTMETA.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _cost_meta_save(rows: dict[str, Any]) -> None:
    try:
        COSTMETA.parent.mkdir(parents=True, exist_ok=True)
        COSTMETA.write_text(json.dumps(rows, indent=1, sort_keys=True), "utf-8")
    except OSError:
        pass


def _leg_key(row: dict[str, Any]) -> str:
    return (f"{row['arm']}|{row['symbol']}|"
            f"{json.dumps(row['params'], sort_keys=True, separators=(',', ':'))}")


def build_legs(rows: list[dict[str, Any]], meta: dict[str, Any],
               deadline: float) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One daily R series per judged cell, at 1x and at the sealed 3x cost scenario.

    Built with the gauntlet's OWN `build_cell` / `daily_series` / `costs_for`, and served from the
    gauntlet's own content-addressed cache when that is warm -- so a leg here is byte-identical to
    the leg the sweep judged. Reproduction is checked, not assumed: `sharpe_reproduction_max_err`
    below is the largest disagreement between a rebuilt leg's Sharpe and the one the sweep
    published, and it is part of the artifact.
    """
    costmeta = _cost_meta_load()
    legs: dict[str, dict[str, Any]] = {}
    fresh = cached = skipped = 0
    for row in rows:
        if time.monotonic() > deadline:
            skipped += 1
            continue
        sym = str(row["symbol"])
        params = dict(row["params"])
        frame = G._bars_for(sym, "H1")
        if frame is None:
            skipped += 1
            continue
        last_day = frame.index[-1].normalize()
        key = _leg_key(row)
        ckey = G._cache_key(sym, FAMILY, params, str(last_day.date()), "H1")
        got = G.cache_load(ckey)
        if got is not None and key in costmeta:
            ds1, ds3 = _norm_index(got[0]), _norm_index(got[1])
            cached += 1
        else:
            cell = G.build_cell(sym, FAMILY, params, meta)
            if cell is None:
                skipped += 1
                continue
            costs3 = G.costs_for(sym, meta, mult=G.COST_SCENARIO)
            ds1 = _norm_index(G._series_trim_partial(
                G.daily_series(cell["df"], cell["sigs"], cell["costs"]), last_day))
            ds3 = _norm_index(G._series_trim_partial(
                G.daily_series(cell["df"], cell["sigs"], costs3), last_day))
            c = cell["costs"]
            costmeta[key] = {
                "symbol": sym,
                "cost_basis": cell["_cost_basis"],
                "modal_fill_hour": cell["_fill_hour"],
                "spread_per_lot_1x": round(float(getattr(c, "spread_per_lot", 0.0)), 6),
                "spread_per_lot_3x": round(float(getattr(costs3, "spread_per_lot", 0.0)), 6),
                "commission_per_lot_per_side": round(
                    float(getattr(c, "commission_per_lot", 0.0)), 6),
                "quote_per_account": round(float(getattr(c, "quote_per_account", 1.0)), 6),
            }
            fresh += 1
        if len(ds1) < 60:
            skipped += 1
            continue
        legs[key] = {"row": row, "ds1": ds1, "ds3": ds3,
                     "cost": costmeta.get(key, {"cost_basis": "UNMEASURED"})}
    _cost_meta_save(costmeta)
    err = 0.0
    for v in legs.values():
        err = max(err, abs(G.sharpe_ratio(v["ds1"].to_numpy(float))
                           - float(v["row"]["sharpe_is"])))
    return legs, {"n_legs": len(legs), "from_cache": cached, "built_fresh": fresh,
                  "skipped": skipped, "sharpe_reproduction_max_err": round(err, 8)}


# --------------------------------------------------------------------------- portfolio


class Panel:
    """The aligned leg panel: days x legs, with a liveness mask.

    THE CALENDAR IS THE UNION OF THE MEMBERS' OWN TRADE DAYS, which is the legs' own convention --
    the gauntlet judges a leg over the days it traded, never over a padded calendar, and padding
    the basket while the legs were not padded would flatter the basket by construction. A member
    that did not fire on a day the basket traded contributes 0.0 on that day, which is what it
    made. A member whose history has not started yet also contributes 0.0, so an early, thin book
    is thin in the series too rather than being rescaled into a fiction of full diversification.
    """

    def __init__(self, legs: dict[str, dict[str, Any]]) -> None:
        self.names = sorted(legs)
        self.legs = legs
        m1 = pd.DataFrame({k: legs[k]["ds1"] for k in self.names}).sort_index()
        m3 = pd.DataFrame({k: legs[k]["ds3"] for k in self.names}).sort_index()
        self.index = m1.index
        self.a1 = m1.to_numpy(float)
        self.a3 = m3.reindex(index=m1.index, columns=m1.columns).to_numpy(float)
        self.live = ~np.isnan(self.a1)
        self.a1 = np.nan_to_num(self.a1, nan=0.0)
        self.a3 = np.nan_to_num(self.a3, nan=0.0)

    def leg_sharpe(self, col: int, mask: np.ndarray) -> float | None:
        sel = mask & self.live[:, col]
        if int(sel.sum()) < 60:
            return None
        return float(G.sharpe_ratio(self.a1[sel, col]))

    def series(self, members: list[int], mask: np.ndarray,
               weights: np.ndarray | None = None) -> tuple[pd.Series, pd.Series]:
        """The basket's daily R at 1x and at 3x, over the days at least one member traded."""
        if not members:
            empty = pd.Series(dtype=float)
            return empty, empty
        w = np.ones(len(members)) if weights is None else np.asarray(weights, float)
        sel = mask & self.live[:, members].any(axis=1)
        idx = self.index[sel]
        b1 = (self.a1[np.ix_(sel, members)] * w).sum(axis=1)
        b3 = (self.a3[np.ix_(sel, members)] * w).sum(axis=1)
        return pd.Series(b1, index=idx), pd.Series(b3, index=idx)


def correlation_report(panel: Panel, members: list[int],
                       mask: np.ndarray) -> dict[str, Any]:
    """The basket's REALISED correlation structure and its effective independent bets.

    `effective_independent_bets` is the participation ratio of the correlation matrix's
    eigenvalues, (sum lambda)^2 / sum(lambda^2) -- k when the legs are orthogonal, 1 when they are
    one bet wearing k names. It is MEASURED on the same window the judge sees, so the
    diversification claim is a reading rather than an assumption.
    """
    if len(members) < 2:
        return {"n_members": len(members), "effective_independent_bets": float(len(members)),
                "why": "fewer than two members: no correlation to measure"}
    sel = mask & panel.live[:, members].any(axis=1)
    x = panel.a1[np.ix_(sel, members)]
    sd = x.std(axis=0, ddof=1)
    ok = sd > 0
    z = np.zeros_like(x)
    z[:, ok] = (x[:, ok] - x[:, ok].mean(axis=0)) / sd[ok]
    n = max(int(sel.sum()) - 1, 1)
    c = z.T @ z / n
    np.fill_diagonal(c, 1.0)
    off = c[~np.eye(len(members), dtype=bool)]
    lam = np.linalg.eigvalsh(c)
    lam = lam[lam > 1e-12]
    enb = float(lam.sum() ** 2 / float((lam ** 2).sum())) if lam.size else float(len(members))
    return {
        "n_members": len(members),
        "mean_abs_rho": round(float(np.abs(off).mean()), 4),
        "max_abs_rho": round(float(np.abs(off).max()), 4),
        "mean_rho": round(float(off.mean()), 4),
        "effective_independent_bets": round(enb, 2),
        "independence_fraction": round(enb / len(members), 4),
    }


# --------------------------------------------------------------------------- membership


def _rel_spread(sym: str, meta: dict[str, Any]) -> float:
    m = meta.get(sym) or {}
    px = float(m.get("last_close") or m.get("close") or 0.0)
    sp = float(m.get("median_spread_pts") or 0.0)
    ts = float(m.get("tick_size") or 0.0)
    if px > 0 and sp > 0 and ts > 0:
        return sp * ts / px
    return float("inf")


def _one_per_block(panel: Panel, pool: list[int],
                   rank: Any) -> list[int]:
    """One member per correlation block, by a caller-supplied ranking key.

    A LEG WITH NO BLOCK IS EXCLUDED, NEVER PROMOTED TO A BLOCK OF ITS OWN. The sweep dropped four
    short-history symbols from the clustering (`dropped_short_history`) and their cells carry
    `block: null`. Admitting each as its own singleton block would count an UNMEASURED
    independence as a measured one, in the direction that flatters the basket -- exactly the
    shape of error this file exists to refuse. Their absence is recorded in `unblocked_legs`.
    """
    best: dict[int, tuple[Any, int]] = {}
    for j in pool:
        raw = panel.legs[panel.names[j]]["row"].get("block")
        if raw is None:
            continue
        blk = int(raw)
        k = (rank(j), panel.names[j])
        if blk not in best or k < best[blk][0]:
            best[blk] = (k, j)
    return sorted(v[1] for v in best.values())


def membership_rules(panel: Panel, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Every membership rule this organ runs, with its selection class stated.

    ORDERED BY HOW MUCH THEY ARE ALLOWED TO CLAIM. `selection: none` and `non_performance` are
    genuinely one trial -- the rule could have been written before a single leg was measured.
    `sign_in_sample` and `ranked_in_sample` condition on the very data the judge then reads, so
    they are charged by the sign-flip null and are NOT promotable whatever they score.
    `*_out_of_sample` fix membership on the training window and hand the judge the test window
    alone, so their number was never selected on and it is the only number that can be believed.
    """
    n = len(panel.names)
    allj = list(range(n))
    full = np.ones(len(panel.index), bool)
    split = panel.index[int(len(panel.index) * TRAIN_FRACTION)]
    tr = np.asarray(panel.index < split, dtype=bool)
    te = np.asarray(panel.index >= split, dtype=bool)

    is_sr = np.array([panel.leg_sharpe(j, full) or 0.0 for j in allj])
    tr_sr = {j: panel.leg_sharpe(j, tr) for j in allj}
    tr_ok = [j for j in allj if tr_sr[j] is not None]
    tr_ranked = sorted(tr_ok, key=lambda j: (-float(tr_sr[j] or 0.0), panel.names[j]))
    tr_pos = [j for j in tr_ok if float(tr_sr[j] or 0.0) > 0]

    def days(j: int) -> int:
        return int(panel.legs[panel.names[j]]["row"]["days"])

    def spread(j: int) -> float:
        return _rel_spread(str(panel.legs[panel.names[j]]["row"]["symbol"]), meta)

    rules: list[dict[str, Any]] = [
        {"name": "all_judged", "selection": "none", "window": "full", "members": allj,
         "rule": "every judged cell in the sweep. No selection of any kind; one trial."},
        {"name": "block_longest_history", "selection": "non_performance", "window": "full",
         "members": _one_per_block(panel, allj, lambda j: -days(j)),
         "rule": "one leg per correlation block, the member with the longest daily history; "
                 "ties by leg key. Decidable before any performance was measured; one trial."},
        {"name": "block_most_liquid", "selection": "non_performance", "window": "full",
         "members": _one_per_block(panel, allj, spread),
         "rule": "one leg per correlation block, the member with the tightest RELATIVE median "
                 "spread (median_spread_pts x tick_size / last_close) from universe.json; ties "
                 "by leg key. Decidable before any performance was measured; one trial."},
        {"name": "all_positive_in_sample", "selection": "sign_in_sample", "window": "full",
         "members": [j for j in allj if is_sr[j] > 0],
         "rule": "membership by the SIGN of the full-sample Sharpe, no ranking and no top-N. "
                 "Still conditions on the data the judge reads: CHARGED by the sign-flip null."},
        {"name": "block_positive_longest", "selection": "sign_in_sample", "window": "full",
         "members": _one_per_block(panel, [j for j in allj if is_sr[j] > 0], lambda j: -days(j)),
         "rule": "one leg per block among the full-sample positives, longest history. "
                 "CHARGED by the sign-flip null."},
        {"name": "top8_by_in_sample_sharpe", "selection": "ranked_in_sample", "window": "full",
         "members": sorted(allj, key=lambda j: (-is_sr[j], panel.names[j]))[:8],
         "rule": "the eight highest full-sample Sharpes. This is the argmax the sweep warned "
                 "about and it is published as a REFUSAL, charged by the sign-flip null."},
        {"name": "oos_positive", "selection": "sign_out_of_sample", "window": "test",
         "members": tr_pos,
         "rule": f"membership by the sign of the Sharpe on the first {TRAIN_FRACTION:.0%} of the "
                 f"union calendar; the judged series is the remaining window ONLY."},
        {"name": "oos_block_positive_longest", "selection": "sign_out_of_sample",
         "window": "test", "members": _one_per_block(panel, tr_pos, lambda j: -days(j)),
         "rule": "one leg per block among the training-window positives, longest history; "
                 "judged on the test window only. The most independent honest basket."},
    ]
    for k in K_LADDER:
        rules.append({
            "name": f"oos_top{k}", "selection": "ranked_out_of_sample", "window": "test",
            "members": sorted(tr_ranked[:k]),
            "rule": f"the {k} highest TRAINING-window Sharpes, judged on the test window only. "
                    f"The whole ladder {list(K_LADDER)} is reported; picking the best k after "
                    f"seeing it would be the argmax this file refuses."})
    # Inverse-variance is a PRE-STATED weighting, never an optimisation: the weights use only the
    # training window's variance and never its mean, so no member is weighted for having won.
    for base in ("oos_positive", "oos_top32"):
        src = next(r for r in rules if r["name"] == base)
        rules.append({**src, "name": f"{base}_inverse_variance", "weighting": "inverse_variance"})
    for r in rules:
        r.setdefault("weighting", "equal_risk_R")
        r["mask"] = te if r["window"] == "test" else full
        r["train_mask"] = tr
    return rules


def weights_for(panel: Panel, rule: dict[str, Any]) -> np.ndarray | None:
    if rule["weighting"] != "inverse_variance":
        return None
    members = rule["members"]
    x = panel.a1[np.ix_(rule["train_mask"], members)]
    var = x.var(axis=0, ddof=1)
    w = np.where(var > 0, 1.0 / np.maximum(var, 1e-12), 0.0)
    total = float(w.sum())
    return w * (len(members) / total) if total > 0 else np.ones(len(members))


# --------------------------------------------------------------------------- the charge


def sign_flip_null(panel: Panel, draws: int, deadline: float) -> dict[str, Any]:
    """What the in-sample membership rules score on legs with NO EDGE AT ALL.

    A sign flip of a whole leg series is the right null here because the family arms both sides of
    the range: -r is an executable member of the same family, so flipping preserves every
    magnitude, every autocorrelation and the covariance structure while destroying the edge. Run
    the ENTIRE procedure on the flipped panel -- select by sign, select the top 8, sum, take the
    Sharpe -- and the distribution that comes back is the selection charge, measured rather than
    approximated by a formula.
    """
    rng = np.random.default_rng(NULL_SEED)
    n = len(panel.names)
    full = np.ones(len(panel.index), bool)
    pos_null: list[float] = []
    top_null: list[float] = []
    ks: list[int] = []
    done = 0
    for _ in range(draws):
        if time.monotonic() > deadline:
            break
        sgn = rng.choice(np.array([-1.0, 1.0]), size=n)
        flipped = panel.a1 * sgn
        srs = np.array([
            G.sharpe_ratio(flipped[panel.live[:, j], j])
            if int(panel.live[:, j].sum()) >= 60 else 0.0 for j in range(n)])
        pos = [j for j in range(n) if srs[j] > 0]
        if pos:
            sel = full & panel.live[:, pos].any(axis=1)
            pos_null.append(float(G.sharpe_ratio(flipped[np.ix_(sel, pos)].sum(axis=1))))
            ks.append(len(pos))
        top = sorted(range(n), key=lambda j: -srs[j])[:8]
        sel = full & panel.live[:, top].any(axis=1)
        top_null.append(float(G.sharpe_ratio(flipped[np.ix_(sel, top)].sum(axis=1))))
        done += 1
    if not top_null:
        return {"measured": False, "why": "UNMEASURED: the budget ran out before any draw"}
    p = np.asarray(pos_null)
    t = np.asarray(top_null)
    return {
        "measured": True, "draws": done, "seed": NULL_SEED,
        "what_it_is": "the SAME membership procedure run on sign-flipped (no-edge) legs",
        "all_positive_in_sample": {
            "mean": round(float(p.mean()), 4), "sd": round(float(p.std(ddof=1)), 4),
            "p95": round(float(np.quantile(p, 0.95)), 4), "max": round(float(p.max()), 4),
            "mean_k_selected": round(float(np.mean(ks)), 1)},
        "top8_by_in_sample_sharpe": {
            "mean": round(float(t.mean()), 4), "sd": round(float(t.std(ddof=1)), 4),
            "p95": round(float(np.quantile(t, 0.95)), 4), "max": round(float(t.max()), 4)},
    }


# --------------------------------------------------------------------------- the trial census


def basket_identity(rule: dict[str, Any], member_keys: list[str]) -> str:
    """A basket's trial identity: the rule, its weighting and window, and its EXACT members."""
    import hashlib
    blob = json.dumps({"rule": rule["name"], "weighting": rule.get("weighting"),
                       "window": rule.get("window"), "members": sorted(member_keys)},
                      sort_keys=True, separators=(",", ":"))
    return f"BASKET:{rule['name']}|{hashlib.sha256(blob.encode()).hexdigest()[:16]}"


def charge_trials(identities: list[str], path: Path | None = None) -> dict[str, Any]:
    """Append every basket identity not already charged. Nothing is judged for free.

    Returns what was charged; a write failure is REPORTED (the report says the charge is
    UNMEASURED) rather than swallowed, because an uncharged trial is a survivor manufactured.
    """
    path = path or TRIALS
    known: set[str] = set()
    try:
        for ln in path.read_text("utf-8").splitlines():
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("cell"):
                known.add(str(row["cell"]))
    except OSError:
        pass
    new = [i for i in dict.fromkeys(identities) if i not in known]
    if new:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for i in new:
                    fh.write(json.dumps({"at": now, "cell": i, "family": FAMILY,
                                         "source": "srb_basket_judge"},
                                        separators=(",", ":")) + "\n")
        except OSError as exc:
            return {"charged_now": 0, "lifetime": len(known), "family": FAMILY,
                    "status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    return {"charged_now": len(new), "lifetime": len(known) + len(new), "family": FAMILY,
            "status": "CHARGED", "ledger": path.name}


# --------------------------------------------------------------------------- the judge


def judge(panel: Panel, rules: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    """Feed every basket to the SEALED gauntlet as one batch of cells.

    `run_gauntlet` uses `_cached_ds` / `_cached_ds3` when a cell carries them and then never
    touches `df`, `sigs` or `costs` -- the documented door for a caller that has already built the
    series. Nothing here modifies the judge, its thresholds or its spec: the same ten stages, the
    same fixed trial count and the same fixed variance of Sharpes, so a basket's deflated-Sharpe
    hurdle is the identical 0.3122 a leg faces.
    """
    cells: list[dict[str, Any]] = []
    for r in rules:
        if r["_n_days"] < 60:
            continue
        cells.append({
            "sym": f"BASKET:{r['name']}", "family": FAMILY, "timeframe": "H1",
            "params": {"membership_rule": r["name"], "weighting": r["weighting"],
                       "window": r["window"], "k": len(r["members"])},
            "mechanism_status": "NAMED",
            "mechanism_note": ("session_range_breakout traded as a portfolio of legs on "
                               "near-zero-correlated instruments; the family is registered and "
                               "the basket changes only how many of it are held at once"),
            "df": None, "sigs": None, "costs": None,
            "_cached_ds": r["_b1"], "_cached_ds3": r["_b3"],
        })
    if not cells:
        return {"error": "no basket reached 60 daily observations", "verdicts": []}
    res: dict[str, Any] = G.run_gauntlet(cells, "srb_basket", meta)
    return res


def _verdict_row(v: dict[str, Any]) -> dict[str, Any]:
    """The judge's verdict, flattened. `.get` throughout: an UNMEASURED verdict carries only an
    `observations` stage, and a KeyError here would lose the whole report over a short basket."""
    st = v.get("stages") or {}

    def g(stage: str, field: str) -> Any:
        return (st.get(stage) or {}).get(field)

    return {
        "passed": bool(v.get("passed")), "terminal_gate": v.get("terminal_gate"),
        "failed_gates": v.get("failed_gates"), "unmeasured": bool(v.get("unmeasured")),
        "dsr": g("deflated_sharpe", "dsr"), "sr0": g("deflated_sharpe", "sr0"),
        "n_trials": g("deflated_sharpe", "n_trials"),
        "pbo": g("pbo", "pbo"), "spa_p": g("reality_check_spa", "p_value"),
        "cpcv_oos_sharpe": g("cpcv", "mean_oos_sharpe"),
        "wf_oos_sharpe": g("walk_forward", "oos_sharpe"),
        "wf_stability": g("walk_forward", "stability"),
        "stress_x3": g("stress_costs", "exp_x3"),
        "expected_value": g("expected_value", "ev"),
        "swap_cost": g("swap_cost", "why"),
    }


def build(budget_s: float = 900.0) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    try:
        sweep = json.loads(SWEEP.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"measured": False,
                "why": f"UNMEASURED: {SWEEP.name} unreadable on this host ({type(exc).__name__})",
                "generated_at": datetime.now(UTC).isoformat()}
    rows = [r for r in sweep.get("all_judged_cells") or [] if isinstance(r, dict)]
    meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    legs, leg_stats = build_legs(rows, meta, deadline)
    if len(legs) < 2:
        return {"measured": False,
                "why": f"UNMEASURED: only {len(legs)} leg series could be built",
                "legs": leg_stats, "generated_at": datetime.now(UTC).isoformat()}

    panel = Panel(legs)
    rules = membership_rules(panel, meta)
    for r in rules:
        b1, b3 = panel.series(r["members"], r["mask"], weights_for(panel, r))
        r["_b1"], r["_b3"] = b1, b3
        r["_n_days"] = len(b1)
    null = sign_flip_null(panel, NULL_DRAWS, deadline)
    res = judge(panel, rules, meta)
    # CHARGED BEFORE ANYTHING IS READ OFF THE VERDICTS: a basket the judge saw is a trial whether
    # it passed or not, and only the ones that reached the judge (>= 60 days) are counted.
    trial_charge = charge_trials([
        basket_identity(r, [panel.names[j] for j in r["members"]])
        for r in rules if r["_n_days"] >= 60])
    verdict_by = {v["sym"]: v for v in res.get("verdicts", [])}

    baskets: list[dict[str, Any]] = []
    for r in rules:
        b1 = r["_b1"]
        members = r["members"]
        arr = b1.to_numpy(float)
        member_sr = [panel.leg_sharpe(j, r["mask"]) or 0.0 for j in members]
        mean_leg = float(np.mean(member_sr)) if member_sr else 0.0
        sr = float(G.sharpe_ratio(arr)) if len(arr) else 0.0
        v = verdict_by.get(f"BASKET:{r['name']}")
        bases: dict[str, int] = {}
        for j in members:
            b = str(panel.legs[panel.names[j]]["cost"].get("cost_basis") or "UNMEASURED")
            bases[b] = bases.get(b, 0) + 1
        charge = None
        if r["selection"] == "sign_in_sample" and null.get("measured"):
            charge = null["all_positive_in_sample"]
        elif r["selection"] == "ranked_in_sample" and null.get("measured"):
            charge = null["top8_by_in_sample_sharpe"]
        baskets.append({
            "rule": r["name"], "selection": r["selection"], "weighting": r["weighting"],
            "judged_window": r["window"], "rule_text": r["rule"],
            "k_members": len(members), "n_days": len(arr),
            "first_day": str(b1.index[0].date()) if len(b1) else None,
            "last_day": str(b1.index[-1].date()) if len(b1) else None,
            "sharpe": round(sr, 4),
            "mean_member_sharpe": round(mean_leg, 4),
            "sharpe_multiple_over_mean_member": (
                round(sr / mean_leg, 2) if abs(mean_leg) > 1e-9 else None),
            "sr0_hurdle": 0.3122,
            "shortfall_vs_hurdle": round(0.3122 - sr, 4),
            "fraction_of_hurdle": round(sr / 0.3122, 3),
            "mean_daily_R_1x": round(float(arr.mean()), 4) if len(arr) else None,
            "mean_daily_R_3x": (round(float(r["_b3"].to_numpy(float).mean()), 4)
                                if len(r["_b3"]) else None),
            "correlation": correlation_report(panel, members, r["mask"]),
            "cost_basis_of_members": bases,
            "selection_charge_null": charge,
            "beats_its_own_null_p95": (None if charge is None
                                       else bool(sr > float(charge["p95"]))),
            "members": [str(panel.legs[panel.names[j]]["row"]["symbol"]) for j in members][:40],
            "verdict": None if v is None else _verdict_row(v),
        })

    honest = {"none", "non_performance", "sign_out_of_sample", "ranked_out_of_sample"}
    promotable = [b for b in baskets
                  if b["verdict"] and b["verdict"]["passed"] and b["selection"] in honest]
    # THE BEST HONEST BASKET IS THE BEST ONE THAT ONLY MISSES THE MULTIPLICITY CHARGE, not simply
    # the highest Sharpe. `oos_top64` scores higher than `oos_top32` and LOSES MONEY AT 3x COSTS
    # (exp_x3 -0.5894): it buys its Sharpe by admitting legs the cost stress kills. Naming it
    # "best" in the headline would be a flattering summary of exactly the kind this file refuses,
    # so the ranking is: among honest rules, prefer those whose only failed gate is
    # `deflated_sharpe` -- a candidate the spec itself marks curable by forward evidence -- and
    # fall back to raw Sharpe only when no basket clears everything else.
    def _only_multiplicity(b: dict[str, Any]) -> bool:
        return bool(b["verdict"]) and b["verdict"]["failed_gates"] == ["deflated_sharpe"]

    honest_rows = [b for b in baskets if b["selection"] in honest]
    clean = [b for b in honest_rows if _only_multiplicity(b)]
    best_honest = max(clean or honest_rows, key=lambda b: b["sharpe"], default=None)
    best_basis = ("highest Sharpe among honest rules whose ONLY failed gate is the multiplicity "
                  "charge" if clean else
                  "highest Sharpe among honest rules; NONE cleared every other gate")
    unselected = [b for b in baskets if b["selection"] in {"none", "non_performance"}]
    curable = [b["rule"] for b in baskets
               if b["selection"] in honest and b["verdict"]
               and b["verdict"]["failed_gates"] == ["deflated_sharpe"]]
    return {
        "measured": True,
        "headline": (
            f"{len(promotable)} of {len(baskets)} baskets passed the sealed ten gates. "
            f"Diversification is REAL and MEASURED -- the best honest basket lifts its members' "
            f"mean Sharpe {best_honest['sharpe_multiple_over_mean_member']}x on "
            f"{best_honest['correlation'].get('effective_independent_bets')} effective "
            f"independent bets -- and it is still not enough: "
            f"{best_honest['sharpe']} against the sealed hurdle 0.3122, "
            f"{best_honest['fraction_of_hurdle']}x the bar. "
            + ("Its only failed gate is the multiplicity charge." if clean
               else "NO honest basket cleared every gate but the multiplicity charge.")
            if best_honest else "UNMEASURED: no honest basket could be built"),
        "the_finding": {
            "diversification_works_and_is_insufficient": (
                "summing near-zero-correlated legs multiplies the mean member Sharpe by roughly "
                "the square root of the effective independent bets, exactly as the principal's "
                "argument says it should. It is measured here, not assumed. It moves the family "
                "from ~0.08 per leg to ~0.30 per basket against a 0.3122 hurdle, so the gap that "
                "one leg missed by half, a 32-leg portfolio misses by a few percent."),
            "no_selection_means_a_LOSS": (
                "the baskets that select nothing are decisively NEGATIVE: "
                + "; ".join(f"{b['rule']} {b['sharpe']:+.4f}" for b in unselected)
                + ". Traded the way the rule would actually be deployed -- every uncorrelated "
                  "instrument the sweep found an executable session for -- this mechanism loses "
                  "money. The positive baskets exist only after a membership filter."),
            "the_in_sample_baskets_are_not_evidence": (
                "the sign-flip null runs the identical procedure on legs with NO edge and scores "
                "HIGHER than the real data does, so every in-sample membership rule here has a "
                "one-sided p of 1.0. Their apparent multiple is selection."),
            "how_far_short": (
                f"best honest basket {best_honest['rule']} at Sharpe {best_honest['sharpe']} "
                f"= {best_honest['fraction_of_hurdle']}x the hurdle, dsr "
                f"{(best_honest['verdict'] or {}).get('dsr')} against the 0.95 threshold."
                if best_honest else "UNMEASURED"),
            "curable_by_forward": curable,
            "what_would_change_the_answer": [
                "BETTER legs, not more of them: the ladder peaks at k=32-64 and then falls, and "
                "k=64 buys its extra Sharpe by admitting legs that lose at 3x costs. Adding weak "
                "legs to this family no longer adds return per unit of variance.",
                "a second MECHANISM. The multiple here is bounded by the effective independent "
                "bets WITHIN one family; an uncorrelated family would raise the ceiling in a way "
                "another session_range_breakout instrument cannot.",
                "forward evidence on the k=16..32 out-of-sample baskets, whose only failed gate "
                "is the multiplicity charge the spec already marks cure_by_forward.",
            ],
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "what_this_is": (
            "session_range_breakout judged as a PORTFOLIO of legs summed into one daily R series "
            "and fed to the SEALED ten-gate gauntlet as a single cell -- the test the "
            "SRB_UNCORRELATED_SWEEP named as the one it had not run. Bar simulation on the "
            "desk's own H1 parquets, per-leg costs, no live lot, no forward evidence."),
        "nothing_was_added": (
            "run_gauntlet called directly: no gate ledger, no certificate, no authority file. "
            "data/sleeves.json, the rosters, the E8 config and UNIVERSAL_SURVIVORS were not "
            "opened. gate_spec.yaml was not touched and no threshold was moved."),
        "source_sweep": {"file": SWEEP.name, "judged_cells": len(rows),
                         "passed_in_sweep": 0, "sr0_hurdle": 0.3122},
        "legs": {**leg_stats, "unblocked_legs": sum(
            1 for k in panel.names if panel.legs[k]["row"].get("block") is None),
            "unblocked_note": ("legs the sweep could not cluster (short history) are excluded "
                               "from every one-per-block rule rather than admitted as singleton "
                               "blocks: their independence is UNMEASURED, not established")},
        "calendar": {"first_day": str(panel.index[0].date()),
                     "last_day": str(panel.index[-1].date()),
                     "union_days": len(panel.index),
                     "train_fraction": TRAIN_FRACTION,
                     "alignment": ("union of the members' own trade days; a member that did not "
                                   "fire contributes 0.0 that day, never a rescaled share")},
        "cost_treatment": {
            "per_leg_not_per_basket": ("each member's series is the gauntlet's own "
                                       "daily_series(df, sigs, costs) with that instrument's own "
                                       "Costs, so a basket of k pays k round trips"),
            "stress": f"{G.COST_SCENARIO}x the spread, charged per leg BEFORE the sum",
            "commission": ("Costs.from_symbol's published Fusion Zero schedule, per side; the "
                           "relayed 3.50 round-turn figure is not used here"),
            "swap": ("the engine models none; at basket level swap_cost reads UNMEASURED because "
                     "a basket has no symbol to price. Per-member cost bases are listed."),
            "known_defects_not_fixed_here": [
                "universe.json's median spread excludes zeros, which selects for the broker's "
                "placeholder quote",
                "slippage is barely characterised and is not charged by this engine at all",
            ]},
        "selection_charge": null,
        "baskets": sorted(baskets, key=lambda b: -b["sharpe"]),
        "judge": {"hunt": res.get("hunt"), "n_cells": res.get("n_cells"),
                  "n_trials": res.get("n_trials"),
                  "trial_count_basis": res.get("trial_count_basis"),
                  "program_level": res.get("program_level"),
                  "survivors_passing_all": res.get("survivors_passing_all"),
                  "gate_fails": res.get("gate_fails"),
                  "matrix_caveat": ("run_gauntlet truncates its PBO/SPA matrix to the shortest "
                                    "column, so full-sample and split-sample baskets are "
                                    "compared over the shorter window. Sealed behaviour, "
                                    "recorded rather than worked around.")},
        "promotable": [b["rule"] for b in promotable],
        "best_honest_basket": None if best_honest is None else {
            "rule": best_honest["rule"], "chosen_by": best_basis,
            "sharpe": best_honest["sharpe"],
            "fraction_of_hurdle": best_honest["fraction_of_hurdle"],
            "failed_gates": (best_honest["verdict"] or {}).get("failed_gates"),
            "mean_daily_R_3x": best_honest["mean_daily_R_3x"],
            "effective_independent_bets":
                best_honest["correlation"].get("effective_independent_bets")},
        "trial_charge": trial_charge,
        "seconds": round(time.monotonic() - t0, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError as exc:
        print(f"srb basket judge: could not write {a.out}: {exc}")
        return 1
    if not doc.get("measured"):
        print(f"srb basket judge: {doc.get('why')}")
        print(f"written: {a.out}")
        return 0
    print(f"srb basket judge: {len(doc['baskets'])} basket(s) from "
          f"{doc['legs']['n_legs']} legs, hurdle sr0=0.3122")
    for b in doc["baskets"]:
        v = b["verdict"] or {}
        flag = "PASS" if v.get("passed") else (v.get("terminal_gate") or "unjudged")
        print(f"  {b['rule']:<34} {b['selection']:<22} k={b['k_members']:>3} "
              f"SR={b['sharpe']:+.4f} ({b['fraction_of_hurdle']:.2f}x hurdle) "
              f"ENB={b['correlation'].get('effective_independent_bets')} -> {flag}")
    print(f"  promotable: {doc['promotable'] or 'NONE'}")
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
