"""Q7 -- WHICH SINGLE MISSING OBSERVATION WOULD MOST REDUCE MY UNCERTAINTY, per unit of cost.

THE PRINCIPAL, 2026-09-16: autonomous information acquisition, as ONE RATIO per missing
observation.

    ValueOfData(d) = E[uncertainty reduction or decision improvement] / cost(d)

The desk already had both halves and had never divided them. `experiment_design` prices an
EXPERIMENT the desk could run; `data_prospector` prices a SOURCE it could fetch;
`information_value` prices a DATASET by how many blind spots it closes. None of them answers the
researcher's actual question, which is smaller and sharper than any of those: for THIS hypothesis,
which single observation am I missing, and what would having it be worth?

THE UNIT IS R OF POSTERIOR SD REMOVED, the same unit for every need on the list. That is the whole
reason this organ can rank a CFTC download against twenty more forward trades on a gold sleeve:
both are priced by what they do to a Normal-Inverse-Gamma posterior under `posterior_alpha`'s own
prior, with its own update, at its own credibility horizon (CREDIBLE_N observations). Nothing here
invents a second model of the desk's uncertainty; it advances the one the desk already publishes.

    MEASURED SLEEVE     a POSTERIOR_ALPHA row with n observations and a published mu_sd. The
                        missing observation is MORE FORWARD TRADES, worth sd(n) - sd(n+k).
                        Monotone by construction: the projection holds the posterior's own
                        E[sigma^2] fixed and holds mu at mu_n -- the posterior predictive mean IS
                        mu_n, so moving it would assume what the data is about to say.
    BLOCKED HYPOTHESIS  a mechanism that cannot be measured at all: research_os says
                        DATA_UNAVAILABLE, or an organ published UNMEASURED and named the dataset.
                        Its posterior IS the prior, so unblocking is worth sd(0) - sd(k) -- what
                        the FIRST k observations would remove. Derived, not asserted.

DECISION REGRET WHERE THERE IS CAPITAL AT RISK. Uncertainty about a sleeve the allocator funds is
not the same quantity as uncertainty about one it does not: the stake is risk_frac x sd and the
regret removed is risk_frac x delta_sd, both published per row. The ranking weight is
1 + risk_frac / median(risk_frac over funded sleeves) -- measured off the desk's own book and
floored at 1, so a funded sleeve is never priced BELOW an unfunded one. Reading uncertainty about
live capital as worth less than uncertainty about paper would be the timidity GROWTH_GOVERNANCE
forbids, and it would also be arithmetically backwards.

COST IS NEVER ZERO AND NEVER SILENTLY GUESSED. Where the catalogue behind `data_prospector`
already prices the source, its implementation_cost (1..10) is used and the basis says so;
otherwise the kind's DECLARED default is used and the row carries `cost_unmeasured`. An unpriced
need must never sort to the top of a ratio because nobody costed it (L1.28a).

IT FETCHES NOTHING. `acquire_datasets` is the only organ here that reaches the network, on its own
clock, from public and licensed sources. This writes it a ranked targets file and stops. A pricer
that also bought would be two organs, and the second one would be unaccountable. NOT WIRED TO A
CLOCK YET (III.16, stated rather than hidden): it ships with its test and no scheduler leg, so
until a session that owns `hourly_cycle` adds it as a leg it is a defect.

    python desks/mt5/research/value_of_data.py [--dry-run] [--top 25]

numpy only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import data_prospector as dp  # noqa: E402
from research import experiment_design as ed  # noqa: E402
from research import information_value as iv  # noqa: E402
from research import posterior_alpha as pa  # noqa: E402

POSTERIOR = BASE / "reports" / "POSTERIOR_ALPHA.json"
STANDING = BASE / "reports" / "STANDING_QUESTIONS.json"
RESIDUAL = BASE / "reports" / "RESIDUAL_QUEUE.json"
SLEEVES = BASE / "data" / "sleeves.json"
OUT = BASE / "reports" / "VALUE_OF_DATA.json"
TARGETS = BASE / "data" / "value_of_data_targets.json"
PROSPECTOR_TARGETS = BASE / "data" / "prospector_targets.json"

RULE = "one ratio per missing observation; the acquirer fetches, this only prices"

#: The six shapes a missing observation comes in. A need fitting none is NAMED in
#: `unmeasured.kindless`, never forced into the nearest -- a wrong kind carries a wrong cost.
KINDS = ("axis_series", "bars_timeframe", "event_actuals", "positioning",
         "cost_surface_dimension", "forward_trades")

#: DECLARED default cost per kind, on the catalogue's own 1..10 implementation-cost scale so the
#: two are comparable. Each is a statement about EFFORT, not about value. `cost_surface_dimension`
#: is cheapest because it is derivable from this desk's own tape; `forward_trades` sits at the top
#: of the scale because it is NOT PURCHASABLE AT ANY PRICE -- it accrues by trading, the only
#: currency that buys it is calendar time, and pricing it lower would rank it as a shopping item.
COST_BY_KIND: dict[str, float] = {
    "axis_series": 3.0, "bars_timeframe": 4.0, "event_actuals": 3.0, "positioning": 3.0,
    "cost_surface_dimension": 2.0, "forward_trades": 8.0,
}
#: The catalogue entries this desk is entitled to price a kind from -- only the honest matches: a
#: COT need IS `cot_positioning`, a calendar need IS `macro_release_calendar`. The other four
#: kinds have no catalogue twin, and inventing one would put a measured-looking number on a
#: declared default.
CATALOGUE_FOR_KIND: dict[str, str] = {
    "positioning": "cot_positioning", "event_actuals": "macro_release_calendar",
}
#: `information_value`'s dataset ids mapped to the kind of observation each one IS. Six of its
#: seven map; `compute_history` is absent because it is an observation about this desk's own
#: compute rather than about the market, and none of the six kinds names it.
IV_NEED_KIND: dict[str, str] = {
    "cot_positioning": "positioning", "macro_event_calendar": "event_actuals",
    "live_fill_history": "forward_trades", "depth_and_ticks": "cost_surface_dimension",
    "cost_surface_by_hour": "cost_surface_dimension", "financing_terms": "cost_surface_dimension",
}
#: research_os writes a free-text `missing_observable`; these marks are checked in order.
OBSERVABLE_MARKS: tuple[tuple[str, str], ...] = (
    ("cot", "positioning"), ("position", "positioning"),
    ("actual", "event_actuals"), ("calendar", "event_actuals"), ("surprise", "event_actuals"),
    ("spread", "cost_surface_dimension"), ("tick", "cost_surface_dimension"),
    ("swap", "cost_surface_dimension"), ("financing", "cost_surface_dimension"),
    ("depth", "cost_surface_dimension"), ("cost", "cost_surface_dimension"),
    ("fill", "forward_trades"), ("deal", "forward_trades"), ("trade", "forward_trades"),
    ("m15", "bars_timeframe"), ("m5", "bars_timeframe"), ("bar", "bars_timeframe"),
    ("axis", "axis_series"), ("yield", "axis_series"), ("rate", "axis_series"),
)

#: How far ahead every projection looks: `posterior_alpha`'s own credibility horizon, so "the next
#: k observations" is a horizon the desk already believes in rather than a new one.
K_OBS = int(pa.CREDIBLE_N)
#: A need worth a vanishing amount still costs a queue slot, and a queue full of near-zero rows is
#: a queue nobody reads (L1.37). This is `experiment_design.MIN_EVSI` -- a different unit, the
#: identical purpose, and 0.01 R of posterior sd is negligible in this unit too.
MIN_VALUE = float(ed.MIN_EVSI)
TOP_ROWS = 25                 #: priced needs that reach the artifact and the targets file
NAMED_HYPOTHESES = 12         #: served hypotheses a row names before it truncates


def projected_sd(n: float, sd_now: float, k: int = K_OBS) -> float:
    """Posterior sd of mu after `k` more observations, from a published (n, sd).

    The published sd is inverted back to (kappa_n, a_n, b_n) under `posterior_alpha`'s prior, so
    the projection starts at EXACTLY the number the artifact carries. Advancing (kappa, a, b) by k
    observations of the posterior's own E[sigma^2] leaves E[sigma^2] unchanged by construction and
    makes sd strictly decreasing in k -- a projection that can WIDEN the posterior is not a value
    but an artefact of the fixture, and the thinnest rows are where it would bite.
    """
    n, sd_now, k = max(float(n), 0.0), max(float(sd_now), 0.0), max(int(k), 0)
    kappa, a = pa.PRIOR_N0 + n, pa.PRIOR_A0 + n / 2.0
    nu = 2.0 * a
    if sd_now <= 0.0 or nu <= 2.0 or a <= 1.0:
        return sd_now
    b = (sd_now / float(np.sqrt(nu / (nu - 2.0)))) ** 2 * a * kappa
    b_k, a_k, kappa_k = b + k * (b / (a - 1.0)) / 2.0, a + k / 2.0, kappa + k
    nu_k = 2.0 * a_k
    if nu_k <= 2.0:
        return sd_now
    return float(np.sqrt(b_k / (a_k * kappa_k)) * np.sqrt(nu_k / (nu_k - 2.0)))


def sd_reduction(n: float, sd_now: float, k: int = K_OBS) -> float:
    """R of posterior sd that `k` more observations would remove. Never negative."""
    return max(0.0, float(sd_now) - projected_sd(n, sd_now, k))


#: The posterior sd of mu with NO observations at all: what a blocked hypothesis carries.
PRIOR_SD = float(pa.summarise(pa.nig_update(0.0, 0.0, 0.0))["mu_sd"])
#: What the FIRST K_OBS observations remove from a hypothesis that has none -- the value of
#: unblocking anything, in the same unit as every other row.
UNBLOCK_VALUE = sd_reduction(0.0, PRIOR_SD, K_OBS)
#: A sleeve whose mu_sd is still wider than the sd it would have at the desk's own credibility
#: horizon has less evidence than the bar `posterior_alpha` sets. Derived, not chosen.
SD_THRESHOLD = projected_sd(0.0, PRIOR_SD, K_OBS)


def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return f if np.isfinite(f) else None


def _kind_of(text: str) -> str | None:
    low = str(text).lower()
    return next((kind for mark, kind in OBSERVABLE_MARKS if mark in low), None)


def _need(need_id: str, kind: str | None, what: str, hyps: list[str], why: str, value: float,
          value_basis: str, source: str, **extra: Any) -> dict[str, Any]:
    """One missing observation, valued but not yet costed."""
    return {"need_id": need_id, "kind": kind, "what": what,
            "for_hypotheses": sorted(set(hyps))[:NAMED_HYPOTHESES], "serves": len(set(hyps)),
            "why": why, "value": round(float(value), 6), "value_basis": value_basis,
            "source": source, **extra}


# ------------------------------------------------------------------ (c) posterior_alpha sleeves
def _risk_fracs(doc: Any) -> tuple[dict[str, float], float]:
    """risk_frac by sleeve name and the MEDIAN over funded sleeves -- the stake reference.

    Measured off `data/sleeves.json`, the file every other organ here reads. With no funded sleeve
    the reference is 0.0 and every weight collapses to 1.0: an absent book must not invent a stake.
    """
    fracs: dict[str, float] = {}
    for r in ((doc or {}).get("sleeves") or []) if isinstance(doc, dict) else []:
        f = _num(r.get("risk_frac")) if isinstance(r, dict) else None
        if f is not None:
            fracs[str(r.get("name") or "")] = max(f, 0.0)
    funded = [v for v in fracs.values() if v > 0]
    return fracs, float(np.median(funded)) if funded else 0.0


def needs_from_posterior(doc: Any, fracs: dict[str, float], median_frac: float,
                         threshold: float = SD_THRESHOLD) -> list[dict[str, Any]]:
    """One `forward_trades` need per sleeve whose posterior is still wider than the desk's bar."""
    out: list[dict[str, Any]] = []
    for row in ((doc or {}).get("sleeves") or []) if isinstance(doc, dict) else []:
        if not isinstance(row, dict):
            continue
        name, n, sd = str(row.get("name") or ""), _num(row.get("n")), _num(row.get("mu_sd"))
        if not name or n is None or sd is None or sd <= threshold:
            continue
        delta, after = sd_reduction(n, sd, K_OBS), projected_sd(n, sd, K_OBS)
        frac = float(fracs.get(name, 0.0))
        weight = 1.0 + frac / median_frac if frac > 0 and median_frac > 0 else 1.0
        out.append(_need(
            f"forward_trades:{name}", "forward_trades",
            f"{K_OBS} more forward trades on {name}", [name],
            (f"mu_sd {sd:.4f} on n={n:.0f} is wider than the {threshold:.4f} the desk's own "
             f"credibility horizon implies; {K_OBS} more fills take it to {after:.4f}"
             + (f", and the allocator has {frac:.4%} of risk riding on the answer" if frac > 0
                else ", and no capital rides on the answer yet")),
            delta * weight,
            "NIG sd reduction sd(n) - sd(n+k) under posterior_alpha's prior"
            + (", weighted by the sleeve's stake" if weight > 1.0 else ""),
            "posterior_alpha",
            n=int(n), sd_now=round(sd, 6), sd_after=round(after, 6), risk_frac=round(frac, 8),
            stake_weight=round(weight, 4), regret_stake=round(frac * sd, 8),
            regret_reduction=round(frac * delta, 8)))
    return out


# ----------------------------------------------------------------- (a) research_os blocked work
def needs_from_blocking(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """One need per observable research_os records as DATA_UNAVAILABLE."""
    out: list[dict[str, Any]] = []
    for r in rows or []:
        obs = str(r.get("observable") or "").strip() if isinstance(r, dict) else ""
        if not obs:
            continue
        mechs = int(_num(r.get("mechanisms_blocked")) or 0)
        hyps = int(_num(r.get("hypotheses_blocked")) or 0)
        served = max(mechs, 1)
        out.append(_need(
            f"blocked:{obs}", _kind_of(obs), obs,
            [f"{obs}#mechanism_{i}" for i in range(served)],
            (f"research_os holds {hyps} failure(s) across {mechs} mechanism(s) in state "
             f"DATA_UNAVAILABLE on this observable: they are not refuted, they are unmeasured"),
            UNBLOCK_VALUE * served,
            f"unblocking: sd(0) - sd({K_OBS}) per blocked mechanism, under the same prior",
            "research_os.blocking_observables",
            mechanisms_blocked=mechs, hypotheses_blocked=hyps))
    return out


# ------------------------------------------------------- (b) information_value's UNMEASURED walk
def needs_from_blind_spots(ranked: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """One need per `information_value` dataset that closes at least one distinct blind spot."""
    out: list[dict[str, Any]] = []
    for r in ranked or []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("dataset") or "")
        closed = int(_num(r.get("blind_spots_closed")) or 0)
        if not name or closed <= 0:
            continue
        out.append(_need(
            f"blindspot:{name}", IV_NEED_KIND.get(name), str(r.get("what") or name),
            [f"{e.get('report')}{e.get('at')}" for e in (r.get("examples") or [])
             if isinstance(e, dict)] or [f"{name}#blind_spot_{i}" for i in range(closed)],
            (f"{closed} distinct UNMEASURED verdict(s) name this dataset; each is a question the "
             f"desk cannot answer at all, so its posterior is still the prior"),
            UNBLOCK_VALUE * closed,
            f"unblocking: sd(0) - sd({K_OBS}) per distinct blind spot, under the same prior",
            "information_value", tier=str(r.get("tier") or ""),
            obtainable=bool(r.get("obtainable", True)),
            publication_lag=str(r.get("publication_lag") or "")[:160]))
    return out


# ------------------------------------------- (d) standing questions / residual findings, by axis
def _walk_axis(node: Any, out: list[tuple[str, str]]) -> None:
    """Every dict anywhere in a report that names an `axis`, with the series it correlates with."""
    if isinstance(node, dict):
        axis = node.get("axis")
        if isinstance(axis, str) and axis.strip():
            out.append((axis.strip(),
                        str(node.get("symbol") or node.get("target") or node.get("name") or "?")))
        for v in node.values():
            _walk_axis(v, out)
    elif isinstance(node, list):
        for v in node[:2000]:
            _walk_axis(v, out)


def needs_from_axes(docs: list[Any]) -> list[dict[str, Any]]:
    """One `axis_series` need per axis a finding names -- extend the series, test the correlate."""
    pairs: list[tuple[str, str]] = []
    for doc in docs:
        if doc is not None:
            _walk_axis(doc, pairs)
    by_axis: dict[str, set[str]] = {}
    for axis, target in pairs:
        by_axis.setdefault(axis, set()).add(target)
    return [_need(
        f"axis_series:{axis}", "axis_series",
        f"extend the {axis} series -- more history and more of its fields", sorted(targets),
        (f"{len(targets)} finding(s) correlate a residual with {axis}; the next observation each "
         f"one needs is more of that axis, not another sweep of the same window"),
        UNBLOCK_VALUE * len(targets),
        f"unblocking: sd(0) - sd({K_OBS}) per residual correlate the axis serves",
        "standing_questions/residual_queue", axis=axis)
        for axis, targets in by_axis.items()]


# ------------------------------------------------------------- (e) data_prospector coverage gaps
def needs_from_coverage(uncovered: list[str], never: dict[str, int]) -> list[dict[str, Any]]:
    """One `bars_timeframe` need per timeframe the uncovered state buckets name."""
    by_tf: dict[str, int] = {}
    for key in uncovered or []:
        tf = str(key).split("timeframe=")[-1].split("|")[0] or "UNSTATED"
        by_tf[tf] = by_tf.get(tf, 0) + 1
    fams = sorted(never or {})
    return [_need(
        f"bars_timeframe:{tf}", "bars_timeframe",
        f"bars at timeframe {tf} covering the state buckets no sleeve pays in", fams,
        (f"{buckets} uncovered state bucket(s) carry timeframe={tf}, and {len(fams)} family/ies "
         f"have never been tried in any of them"),
        UNBLOCK_VALUE * len(fams),
        f"unblocking: sd(0) - sd({K_OBS}) per never-tried family the coverage would admit",
        "data_prospector.coverage_gaps", timeframe=tf, uncovered_buckets=buckets)
        for tf, buckets in by_tf.items() if fams]


# -------------------------------------------------------------------------------------- pricing
def catalogue_costs() -> dict[str, float]:
    """implementation_cost by catalogue name, through data_prospector's own mandate filter."""
    out: dict[str, float] = {}
    try:
        for row in dp._catalogue():
            c = _num(row.get("implementation_cost"))
            if c is not None and c > 0:
                out[str(row.get("name"))] = c
    except Exception:
        return {}
    return out


def price(need: dict[str, Any], costs: dict[str, float]) -> dict[str, Any]:
    """Attach cost, basis and ratio. An uncosted need is FLAGGED, never costed at zero."""
    kind = str(need.get("kind") or "")
    name = CATALOGUE_FOR_KIND.get(kind)
    if name and name in costs:
        cost, basis, unmeasured = costs[name], f"catalogue:{name}", False
    elif kind in COST_BY_KIND:
        cost, basis, unmeasured = COST_BY_KIND[kind], f"declared_default:{kind}", True
    else:
        cost, unmeasured = max(COST_BY_KIND.values()), True
        basis = ("declared_default:KINDLESS -- no kind, so the most expensive default on the "
                 "scale. An unpriced need never sorts to the top for being unpriced")
    value = float(need.get("value") or 0.0)
    return {**need, "cost": round(float(cost), 4), "cost_basis": basis,
            "cost_unmeasured": bool(unmeasured),
            "ratio": round(value / cost, 6) if cost > 0 else 0.0}


def gather() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every missing observation this desk can name today, from all five sources.

    TOLERANT BY DESIGN: an absent or unreadable input is a NAMED absence in `sources`, never a
    silent zero (L1.28a). RESIDUAL_QUEUE.json does not exist on this box, and the difference
    between "no residual findings" and "no residual report" is the whole of that law.
    """
    sources: dict[str, Any] = {}
    post = _read(POSTERIOR)
    fracs, median_frac = _risk_fracs(_read(SLEEVES))
    needs = needs_from_posterior(post, fracs, median_frac)
    sources["posterior_alpha"] = {
        "path": str(POSTERIOR), "present": post is not None, "needs": len(needs),
        "n_sleeves": len((post or {}).get("sleeves") or []) if isinstance(post, dict) else 0,
        "sd_threshold": round(SD_THRESHOLD, 6),
        "median_funded_risk_frac": round(median_frac, 8) if median_frac > 0 else "UNMEASURED"}

    blocking: list[dict[str, Any]] = []
    try:
        from libs.research_os import store
        blocking = list(store.blocking_observables())
    except Exception as exc:
        sources["research_os_error"] = f"{type(exc).__name__}: {exc}"
    rows = needs_from_blocking(blocking)
    needs += rows
    sources["research_os"] = {"rows": len(blocking), "needs": len(rows)}

    ranked: list[dict[str, Any]] = []
    try:
        ranked = list(iv.build().get("ranked_datasets") or [])
    except Exception as exc:
        sources["information_value_error"] = f"{type(exc).__name__}: {exc}"
    rows = needs_from_blind_spots(ranked)
    needs += rows
    sources["information_value"] = {"datasets": len(ranked), "needs": len(rows)}

    docs = [_read(STANDING), _read(RESIDUAL)]
    rows = needs_from_axes(docs)
    needs += rows
    sources["standing_questions"] = {"path": str(STANDING), "present": docs[0] is not None,
                                     "needs": len(rows)}
    sources["residual_queue"] = {
        "path": str(RESIDUAL), "present": docs[1] is not None,
        "why_absent": "" if docs[1] is not None else
        "no residual report on this box; the axis needs come from standing questions alone"}

    uncovered: list[str] = []
    never: dict[str, int] = {}
    try:
        uncovered, never = dp._coverage_gaps()
    except Exception as exc:
        sources["coverage_error"] = f"{type(exc).__name__}: {exc}"
    rows = needs_from_coverage(list(uncovered), dict(never))
    needs += rows
    sources["data_prospector"] = {"uncovered_states": len(uncovered),
                                  "families_never_tried": len(never), "needs": len(rows)}
    return needs, sources


def build(top: int = TOP_ROWS) -> dict[str, Any]:
    """Price every missing observation and rank by value / cost."""
    needs, sources = gather()
    costs = catalogue_costs()
    seen: set[str] = set()
    priced: list[dict[str, Any]] = []
    for n in needs:
        if str(n.get("need_id")) not in seen:
            seen.add(str(n.get("need_id")))
            priced.append(price(n, costs))
    priced.sort(key=lambda r: (-float(r["ratio"]), -float(r["value"]), str(r["need_id"])))

    by_kind: dict[str, Any] = {}
    for kind in (*KINDS, "KINDLESS"):
        rows = [r for r in priced if (r.get("kind") or "KINDLESS") == kind]
        if rows:
            by_kind[kind] = {"n": len(rows), "serves": sum(int(r["serves"]) for r in rows),
                             "value": round(sum(float(r["value"]) for r in rows), 6),
                             "cost_each": rows[0]["cost"], "cost_basis": rows[0]["cost_basis"],
                             "best_ratio": rows[0]["ratio"], "best": rows[0]["need_id"]}

    queued = [r for r in priced if float(r["value"]) >= MIN_VALUE]
    keys = ("need_id", "kind", "what", "value", "cost", "ratio", "serves", "why",
            "for_hypotheses", "value_basis", "cost_basis", "cost_unmeasured", "source")
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "rule": RULE,
        "n_needs": len(priced),
        "top": [{k: r[k] for k in keys} for r in queued[:max(int(top), 0)]],
        "by_kind": by_kind,
        "unmeasured": {
            "n_cost_unmeasured": sum(1 for r in priced if r["cost_unmeasured"]),
            "n_kindless": sum(1 for r in priced if not r.get("kind")),
            "kindless": [r["need_id"] for r in priced if not r.get("kind")][:20],
            "n_below_floor": len(priced) - len(queued), "min_value": MIN_VALUE,
            "cost_rule": ("an UNMEASURED cost reads as the kind's DECLARED default and carries "
                          "cost_unmeasured=true. It never reads as zero: a ratio whose "
                          "denominator is an absence would sort a need to the top for not having "
                          "been costed (L1.28a). A KINDLESS need -- information_value's "
                          "`compute_history` is the standing one, an observation about this "
                          "desk's own compute rather than about the market -- takes the most "
                          "expensive default on the scale rather than the nearest kind's"),
        },
        "model": {
            "unit": "R of posterior sd removed", "k_observations": K_OBS,
            "prior": {"n0": pa.PRIOR_N0, "a0": pa.PRIOR_A0, "sigma0": pa.DEFAULT_SIGMA},
            "prior_sd": round(PRIOR_SD, 6), "sd_threshold": round(SD_THRESHOLD, 6),
            "unblock_value": round(UNBLOCK_VALUE, 6),
            "why": ("both halves of the ratio advance through posterior_alpha's own NIG update at "
                    "its own credibility horizon, so a dataset and a fill are priced in one unit "
                    "and can be ranked against each other"),
        },
        "sources": sources, "targets": str(TARGETS),
        "boundary": ("this organ NEVER fetches. acquire_datasets is the only thing on this desk "
                     "that reaches the network, on its own clock, from public and licensed "
                     "sources; this writes it a ranked list and stops"),
    }


# -------------------------------------------------------------------------------- the artifacts
def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                  # a read-only destination is WinError 5 on this box
        path.chmod(0o644)
        os.replace(tmp, path)


def target_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The acquirer's row shape -- `query`, `why`, `unlocks`, `score`, which is exactly what
    `data_prospector.run` writes, so the file the crawler already reads can carry these rows
    unchanged. The pricing fields ride alongside for a reader who wants to know why a row is
    where it is."""
    return [{"query": r["what"], "why": r["why"], "unlocks": r["for_hypotheses"],
             "score": r["ratio"], "source": "value_of_data", "need_id": r["need_id"],
             "kind": r["kind"], "value": r["value"], "cost": r["cost"],
             "cost_unmeasured": r["cost_unmeasured"], "serves": r["serves"]}
            for r in doc.get("top") or []]


def write_targets(doc: dict[str, Any]) -> dict[str, Any]:
    payload = {"generated_utc": doc["at"], "source": "value_of_data", "rule": RULE,
               "targets": target_rows(doc), "boundary": doc["boundary"]}
    _write_atomic(TARGETS, payload)
    return payload


def append_prospector(doc: dict[str, Any]) -> str:
    """Append these rows into the prospector's targets file, idempotently.

    The formats ARE compatible, so the crawler needs no change to read them. Rows tagged
    `source: value_of_data` are REPLACED rather than accumulated and no prospector row is ever
    dropped. `data_prospector` rewrites this file wholesale on its own run, so the append is
    re-applied every time this organ runs -- the right direction, because the prospector's own
    ranking should survive a disagreement about a source.
    """
    doc_in = _read(PROSPECTOR_TARGETS)
    if not isinstance(doc_in, dict) or not isinstance(doc_in.get("targets"), list):
        return "SKIPPED -- the prospector targets file is absent or not in the expected shape"
    kept = [t for t in doc_in["targets"]
            if not (isinstance(t, dict) and t.get("source") == "value_of_data")]
    queries = {str(t.get("query")) for t in kept if isinstance(t, dict)}
    added = [r for r in target_rows(doc) if r["query"] not in queries]
    doc_in["targets"] = kept + added
    doc_in["value_of_data_appended_utc"] = doc["at"]
    _write_atomic(PROSPECTOR_TARGETS, doc_in)
    return f"APPENDED {len(added)} row(s) beside {len(kept)} prospector row(s)"


def render(doc: dict[str, Any]) -> list[str]:
    """Eight lines: the ratio, where the needs came from, what is unpriced, and the head."""
    u, m, src = doc["unmeasured"], doc["model"], doc["sources"]
    lines = [
        f"VALUE OF DATA  {doc['n_needs']} missing observation(s) priced; "
        f"{len(doc['top'])} published  [{doc['rule']}]",
        f"  unit: {m['unit']} over the next {m['k_observations']} observation(s); prior sd "
        f"{m['prior_sd']:.4f}, unblock {m['unblock_value']:.4f}, sleeve bar "
        f"{m['sd_threshold']:.4f}",
        "  by kind: " + (", ".join(f"{k}={v['n']}" for k, v in list(doc["by_kind"].items())[:5])
                         or "none"),
        f"  sources: posterior {src['posterior_alpha']['needs']}, "
        f"research_os {src['research_os']['needs']}, "
        f"blind spots {src['information_value']['needs']}, "
        f"axes {src['standing_questions']['needs']}, "
        f"coverage {src['data_prospector']['needs']}",
        f"  {u['n_cost_unmeasured']} need(s) carry a DECLARED cost, not a measured one; "
        f"{u['n_kindless']} have no kind; {u['n_below_floor']} below the {u['min_value']} floor",
    ]
    for r in (doc["top"] or [])[:2]:
        lines.append(f"  {float(r['ratio']):8.5f}  {r['kind'] or 'KINDLESS'!s:<22} "
                     f"{str(r['what'])[:52]:<52} serves {r['serves']}")
    while len(lines) < 7:
        lines.append("  (no need cleared the floor -- an empty queue is a measurement, L1.28a)")
    lines.append(f"  -> {doc['targets']}   next observation: "
                 f"{str((doc['top'] or [{}])[0].get('need_id', 'NONE'))[:60]}")
    return lines[:8]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="price every missing observation: value / cost")
    ap.add_argument("--dry-run", action="store_true", help="price and print; write nothing")
    ap.add_argument("--top", type=int, default=TOP_ROWS, help="rows published to the artifact")
    ap.add_argument("--no-prospector-append", action="store_true",
                    help="do not append these rows into data/prospector_targets.json")
    a = ap.parse_args(argv)
    doc = build(top=a.top)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    _write_atomic(OUT, doc)
    write_targets(doc)
    note = "skipped by flag" if a.no_prospector_append else append_prospector(doc)
    print(f"  wrote {OUT} and {TARGETS}; prospector: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
