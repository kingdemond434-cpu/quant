"""NOMINAL AGAINST EFFECTIVE BREADTH, published as one number the desk tracks over time.

    "Double the effective alpha breadth. This is the biggest lever. You don't need twice as many
     strategies. You need approximately twice as many genuinely independent sources of P&L. If
     portfolio Sharpe is ~1.7 now, approximately doubling effective breadth while preserving
     average edge quality can theoretically get you around 1.7 * sqrt(2) ~= 2.4."
                                                                 -- the principal, 2026-09-05

WHY THIS ARTIFACT EXISTS WHEN THREE BREADTH NUMBERS ALREADY DO. `mt5desk/independence.py` measures
k_eff from realised returns for the HEAT BUDGET, `libs/risk/fx_factors.py` counts currency legs,
and `research/alpha_genome.py` clusters certificates structurally. All three are read by something
that sizes or targets, none of them is published as the desk's breadth, and no two of them are
comparable. So the question "how many independent bets is this book" had three answers, no
headline, and no series -- which is the same as not having measured it. This writes ONE artifact
carrying every reading with its own status, the MINIMUM of the measured ones as the headline, and
appends a row per run so the number the principal wants doubled has a history to double against.

THE FOUR READINGS, and each is a different question:

    exposure_full_sample   what the book is directionally long and short of, against years of
                           bars -- available today, where realised-return breadth is not
    exposure_systematic    the same, against the leading factors only: how many bets the book is
                           making on the things that move everything at once
    exposure_stress        the same again inside a high prior-volatility regime, conditioned on a
                           LAGGED statistic so the estimate is not a collider (see
                           libs/research/effective_breadth.py -- conditioning on the book's own
                           bad days reports a book SEVEN TIMES more diversified when it is losing)
    realised_returns       the sleeves' own P&L correlation, on overlapping days only, at the
                           MIN_PAIR_OVERLAP floor the heat budget already uses

CLUSTER OCCUPANCY IS THE OTHER HALF, and the half that names research targets. `libs/research/
alpha_clusters.py` declares fifteen phenomena from OUTSIDE the book -- who pays, and why they
cannot stop -- and every sleeve is filed against them. The empty ones are written into the
deepening queue as research tasks, keyed on this source, because an empty cluster is where the
marginal sleeve buys the most breadth available anywhere: k_eff = n/(1+(n-1)rho) is concave in n,
so the twelfth correlated sleeve buys almost nothing and the first uncorrelated one buys the most.

NOT `breadth_ledger`, AND THE NAME WAS CHANGED FOR A REASON. `scripts/daily_research_cycle.py`
already runs a step called `breadth_ledger` -- the PLATFORM's rho-curve report from
`scripts/report_breadth.py` over `libs/research/breadth.py`. That one asks what a given rho does
to a projected Sharpe; this one measures what THIS book's rho actually is. Two organs sharing a
name would be merely confusing in prose and genuinely ambiguous in the two registries that are
keyed by string: `libs.ops.module_rent.MODULES` bills by module name and
`libs.research.bandit.SOURCE_ARM` routes hypotheses by source name. A collision there bills one
organ for another's growth.

NOTHING HERE SIZES, GATES OR PROMOTES. The heat budget keeps reading `mt5desk.independence`; this
publishes and it queues.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.alpha_clusters import (  # noqa: E402
    CLUSTERS,
    UNCLASSIFIED,
    classify_family,
    classify_sleeve,
    occupancy,
)
from libs.research.effective_breadth import (  # noqa: E402
    conditional_breadth,
    exposure_breadth,
    factor_breadth,
    headline,
    lagged_vol_regime,
    realised_breadth,
)

OUT = BASE / "reports" / "EFFECTIVE_BREADTH.json"
HISTORY = BASE / "data" / "effective_breadth.jsonl"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = BASE / "data" / "universe"
LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")

#: The stress regime the conditional reading is taken in: the top fifth of a 20-observation
#: trailing volatility average. Same quantile the desk's other tail work uses, and the window is
#: long enough that a single day cannot define a regime.
STRESS_QUANTILE = 0.20
STRESS_WINDOW = 20

#: Daily observations an instrument needs OF ITS OWN before it may join the aligned panel. Equal
#: to `libs.research.effective_breadth.MIN_PANEL_OBS`, because an instrument that cannot clear the
#: panel floor alone cannot help the panel clear it either -- and a stub series in a complete-case
#: intersection truncates everything else down to its own length.
MIN_OWN_OBS = 250


#: THE SHADOW LEDGERS DO NOT ALL SPEAK ONE SCHEMA, and a reader that knows only one silently
#: measures a subset. Measured on this tree 2026-09-05: 46 ledgers carry
#: `entry_time`/`side`/`r_multiple` and 4 -- every `xau_*` scalp sleeve, 140 of 487 trades and the
#: desk's flagship instrument -- carry `opened_at`/`direction`/`r`. Reading only the first schema
#: dropped all four into a `no_recorded_side` bucket, so the book's largest cluster left the
#: exposure measurement without anything failing. `state_admission_run.load_trades` already
#: tolerates both, which is why the trade COUNT looked right while the exposure did not; these
#: tuples mirror its key lists so the two loaders cannot drift apart again.
_TIME_KEYS: tuple[str, ...] = ("entry_time", "opened_at", "open_time", "time")
_R_KEYS: tuple[str, ...] = ("r_multiple", "r", "R")
_SIDE_KEYS: tuple[str, ...] = ("side", "direction")


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        v = row.get(k)
        if v is not None:
            return v
    return None


def _ledger_rows() -> dict[str, list[dict[str, Any]]]:
    """sleeve -> its realised rows, from every shadow ledger directory this desk keeps."""
    out: dict[str, list[dict[str, Any]]] = {}
    for d in LEDGER_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            keep = [r for r in rows if isinstance(r, dict)]
            if keep:
                out.setdefault(f.stem.removeprefix("ledger_"), []).extend(keep)
    return out


def _symbol_of(sleeve: str) -> str:
    """The instrument a sleeve label names. `xau_*` is the desk's own short form for XAUUSD."""
    tok = str(sleeve).split("_")[0].split(".")[-1].upper()
    if tok == "XAU":
        return "XAUUSD"
    if tok == "XAG":
        return "XAGUSD"
    return tok


def _daily_panel(symbols: list[str]) -> tuple[dict[str, list[float]], dict[str, str]]:
    """Vol-normalisable daily log returns per symbol, from the desk's own H1 bars.

    Aligned on the INTERSECTION of dates so the correlation matrix is complete-case: a
    pairwise-complete matrix on price series that all trade the same sessions buys nothing and can
    leave the matrix non-PSD, which `exposure_neff` would then refuse.

    A SHORT SERIES IS DROPPED BEFORE THE ALIGNMENT, NOT AFTER, and this is not an optimisation.
    One stub file did it here: `AUDNZD_H1.parquet` on this tree holds 20 days against 2,246 for
    every FX cross beside it, and a complete-case intersection that includes it collapses an
    eight-year panel to twenty observations -- so every breadth reading came back UNMEASURED on
    the strength of one instrument carrying one sleeve. Dropping the short series costs the
    breadth that sleeve would have contributed, which is the conservative direction and is
    reported by name; keeping it costs the entire measurement, silently.
    """
    try:
        import pandas as pd
    except ImportError:
        return {}, {"pandas": "not importable on this host"}
    frames: dict[str, Any] = {}
    dropped: dict[str, str] = {}
    for sym in symbols:
        f = UNIVERSE / f"{sym}_H1.parquet"
        if not f.exists():
            dropped[sym] = "no local H1 bars"
            continue
        try:
            d = pd.read_parquet(f, columns=["close"])
        except (OSError, ValueError, KeyError) as exc:
            dropped[sym] = f"unreadable: {type(exc).__name__}"
            continue
        r = np.log(d["close"]).resample("1D").sum()
        r = r[r != 0]
        if len(r) < MIN_OWN_OBS:
            dropped[sym] = (f"{len(r)} daily observations of its own, below the {MIN_OWN_OBS} "
                            "floor; kept in the panel it would truncate every other series")
            continue
        frames[sym] = r
    if len(frames) < 2:
        return {}, dropped
    df = pd.DataFrame(frames).dropna()
    return {str(c): [float(v) for v in df[c].to_numpy()] for c in df.columns}, dropped


def book_exposure() -> dict[str, Any]:
    """What the book is directionally long and short of, and everything that had to be dropped.

    Every sleeve carries one unit of standalone risk, which is what the desk's sizing makes true:
    each sleeve risks the same fraction of equity at its stop. Direction is the SIGN of the mean
    realised side, so a sleeve that traded both ways nets out -- and a sleeve that netted EXACTLY
    zero is dropped rather than credited with a small loading, because it still carries a full
    unit of variance and crediting the small number would overstate breadth.
    """
    rows = _ledger_rows()
    exposure: dict[str, float] = defaultdict(float)
    dropped: dict[str, list[str]] = defaultdict(list)
    kept: list[str] = []
    for sleeve, trades in sorted(rows.items()):
        sides = [float(v) for v in (_first(t, _SIDE_KEYS) for t in trades)
                 if isinstance(v, (int, float))]
        sym = _symbol_of(sleeve)
        if not sides:
            dropped["no_recorded_side"].append(sleeve)
            continue
        if not (UNIVERSE / f"{sym}_H1.parquet").exists():
            dropped["no_price_history"].append(sleeve)
            continue
        mean_side = float(np.mean(sides))
        if mean_side == 0.0:
            dropped["undirectional"].append(sleeve)
            continue
        exposure[sym] += float(np.sign(mean_side))
        kept.append(sleeve)
    n_all = len(rows)
    n_kept = len(kept)
    return {"exposure": dict(exposure), "kept": kept, "dropped": {k: v for k, v in dropped.items()},
            "n_sleeves_total": n_all, "n_sleeves_measured": n_kept,
            "measured_share_of_sleeves": (n_kept / n_all) if n_all else 0.0}


def daily_sleeve_returns() -> dict[str, dict[str, float]]:
    """sleeve -> {date: summed R}. Days a sleeve did not trade are ABSENT, never zero."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for sleeve, trades in _ledger_rows().items():
        for t in trades:
            when = _first(t, _TIME_KEYS)
            r = _first(t, _R_KEYS)
            if not isinstance(when, str) or not isinstance(r, (int, float)):
                continue
            day = when[:10]
            out[sleeve][day] = out[sleeve].get(day, 0.0) + float(r)
    return {k: v for k, v in out.items() if v}


def cluster_view() -> dict[str, Any]:
    """Cluster occupancy of the TRADED book and of the CERTIFIED book, reported separately.

    They answer different questions and conflating them would hide the more useful one. The traded
    book is what has actually produced evidence; the certified book is what the desk is entitled to
    trade, and a cluster occupied only there is a cluster whose edge has never been realised.
    """
    traded_labels: dict[str, str] = {}
    for sleeve in _ledger_rows():
        traded_labels[sleeve] = classify_sleeve(sleeve)
    certified_labels: dict[str, str] = {}
    try:
        canon = json.loads(CANON.read_text("utf-8"))
        for key, cert in (canon.get("survivors") or {}).items():
            if not isinstance(cert, dict):
                continue
            fam = (cert.get("shadow_spec") or {}).get("family") or cert.get("family")
            lab = classify_family(str(fam)) if fam else UNCLASSIFIED
            certified_labels[str(key)] = (lab if lab != UNCLASSIFIED
                                          else classify_sleeve(str(cert.get("cell") or key)))
    except (OSError, ValueError):
        certified_labels = {}
    traded = occupancy(traded_labels.values())
    certified = occupancy(certified_labels.values())
    union = sorted(set(traded["occupied"]) | set(certified["occupied"]))
    empty_both = [c.key for c in CLUSTERS if c.key not in union]
    return {"traded": traded, "certified": certified,
            "traded_labels": traded_labels, "certified_labels": certified_labels,
            "occupied_either": union, "empty_in_both": empty_both}


def _tasks(empty: list[str], head: dict[str, Any], clusters: dict[str, Any]) -> list[dict]:
    """One research instruction per empty cluster, naming the payer rather than an indicator."""
    by_key = {c.key: c for c in CLUSTERS}
    k_eff = head.get("effective_breadth")
    nominal = head.get("n_nominal")
    tasks: list[dict] = []
    for key in empty:
        c = by_key.get(key)
        if c is None:
            continue
        tasks.append({
            "source": "alpha_breadth", "kind": "empty_alpha_cluster",
            "title": f"No sleeve monetises {c.title.lower()}",
            "description": (
                f"The book holds {nominal} nominal sleeves at an effective breadth of "
                f"{k_eff if k_eff is not None else 'UNMEASURED'} "
                f"({clusters['traded']['n_occupied']} of 15 declared phenomena occupied). "
                f"{c.title} is EMPTY. Who pays: {c.payer} What to hunt: {c.hunt} "
                "Because k_eff = n/(1+(n-1)rho) is concave in n, the FIRST sleeve of an "
                "unoccupied phenomenon buys more breadth than the next five inside an occupied "
                "one -- propose a mechanism whose payer is the one named here, on the MT5/Fusion "
                "universe, not a re-parameterisation of what the book already trades."),
            "cluster": key, "payer": c.payer, "status": None,
            "consumer": "deepening_worker / proposers / research brains",
        })
    return tasks


def run(write_queue: bool = True) -> dict[str, Any]:
    exp = book_exposure()
    exposure = exp["exposure"]
    panel, panel_dropped = _daily_panel(sorted(exposure))
    covered = {k: v for k, v in exposure.items() if k in panel}
    nominal_measured = float(len(exp["kept"]))
    readings = []
    gaps: dict[str, str] = {}
    if panel_dropped:
        gaps["instruments_without_usable_bars"] = "; ".join(
            f"{k}: {v}" for k, v in sorted(panel_dropped.items()))
    if len(covered) < 2 or not panel:
        gaps["price_panel"] = (
            f"{len(covered)} of {len(exposure)} book instruments have usable local H1 bars; an "
            "exposure breadth cannot be measured on fewer than two")
    else:
        # Sleeves whose instrument dropped out of the aligned panel carry no measured breadth and
        # must not stay in the numerator -- that would divide a full book's nominal risk by a
        # subset's variance and report diversification that was never measured.
        lost = {s for s in exp["kept"] if _symbol_of(s) not in covered}
        nominal_measured = float(len(exp["kept"]) - len(lost))
        if lost:
            gaps["panel_alignment"] = (
                f"{len(lost)} sleeve(s) left the measurement when their instrument dropped out of "
                "the date-aligned panel; their nominal risk left with them")
        readings.append(exposure_breadth(nominal_measured, covered, panel))
        readings.append(factor_breadth(nominal_measured, covered, panel))
        cond = lagged_vol_regime(panel, window=STRESS_WINDOW)
        readings.append(conditional_breadth(nominal_measured, covered, panel, cond,
                                            quantile=STRESS_QUANTILE, high=True))
    readings.append(realised_breadth(daily_sleeve_returns()))
    head = headline(readings, int(nominal_measured) if nominal_measured else exp["n_sleeves_total"])
    # A STRESS READING ABOVE THE FULL-SAMPLE ONE IS NOT GOOD NEWS AND MUST NOT BE READ AS SOME.
    # It cannot widen anything -- the headline is the minimum -- but a reader who sees "3.7 bets in
    # stress against 1.3 overall" will draw a conclusion unless the ordering is named. The regime
    # here is panel-wide, so a high-volatility window can be one instrument's regime rather than
    # the book's, and the honest statement is that the stress reading did not BIND, not that the
    # book diversifies under stress.
    by_name = {r.name: r for r in readings}
    full, stress = by_name.get("exposure_full_sample"), by_name.get("exposure_stress")
    if (full is not None and stress is not None and full.measured and stress.measured
            and (stress.n_eff or 0.0) > (full.n_eff or 0.0)):
        gaps["stress_reading_above_full_sample"] = (
            f"exposure_stress reads {stress.n_eff:.2f} against a full-sample {full.n_eff:.2f}. "
            "The regime is defined on the WHOLE panel, so a high-volatility window can belong to "
            "one instrument rather than to the book; this reading did not bind and is not "
            "evidence that the book diversifies under stress")
    clusters = cluster_view()
    empty = clusters["empty_in_both"]
    tasks = _tasks(empty, head, clusters)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "gaps": gaps,
        "nominal": {
            "sleeves_with_ledgers": exp["n_sleeves_total"],
            "sleeves_in_the_measurement": int(nominal_measured),
            "instruments": len(exposure),
            "instruments_with_bars": len(covered),
            "dropped": exp["dropped"],
            "measured_share_of_sleeves": round(exp["measured_share_of_sleeves"], 4),
        },
        "effective": head,
        "exposure_by_instrument": {k: round(float(v), 3) for k, v in sorted(exposure.items())},
        "clusters": {
            "declared": len(CLUSTERS),
            "occupied_traded": clusters["traded"]["occupied"],
            "occupied_certified": clusters["certified"]["occupied"],
            "occupied_either": clusters["occupied_either"],
            "empty_in_both": empty,
            "n_unclassified_traded": clusters["traded"]["n_unclassified"],
            "n_unclassified_certified": clusters["certified"]["n_unclassified"],
            "counts_traded": clusters["traded"]["counts"],
            "counts_certified": clusters["certified"]["counts"],
            "largest_cluster_share_traded": round(
                float(clusters["traded"]["largest_cluster_share"]), 4),
            "target_band": [8, 15],
            "meets_target": bool(len(clusters["occupied_either"]) >= 8),
            "empty_detail": clusters["traded"]["empty_detail"],
        },
        "sleeve_clusters": clusters["traded_labels"],
        "instruction": [t["title"] for t in tasks],
        "rule": (
            "nominal counts labels; effective counts bets. The headline is the MINIMUM over the "
            "MEASURED readings and never an average of them, and an UNMEASURED reading is listed "
            "by name with its reason rather than folded into the verdict"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    _append_history(doc)
    if write_queue and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="alpha_breadth")
        except Exception as exc:                                          # noqa: BLE001
            doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    doc["tasks"] = tasks
    return doc


def _append_history(doc: dict[str, Any]) -> None:
    """One row per run, so the number the principal wants doubled has something to double against.

    Append-only and read back by this module alone. A breadth number with no series cannot say
    whether the desk is widening or just adding names, which is the whole failure mode.
    """
    row = {
        "at": doc["generated_utc"],
        "n_nominal": doc["effective"]["n_nominal"],
        "effective_breadth": doc["effective"]["effective_breadth"],
        "binding_reading": doc["effective"]["binding_reading"],
        "n_clusters_occupied": len(doc["clusters"]["occupied_either"]),
        "n_clusters_empty": len(doc["clusters"]["empty_in_both"]),
    }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def history() -> list[dict[str, Any]]:
    """Every recorded breadth row, oldest first. Empty when the ledger has not been written."""
    try:
        lines = HISTORY.read_text("utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    d = run(write_queue=not a.no_queue)
    e = d["effective"]
    print(f"EFFECTIVE BREADTH  nominal={e['n_nominal']}  effective="
          f"{e['effective_breadth']}  ({e['status']}, binding={e['binding_reading']})")
    for r in e["readings"]:
        print(f"  {r['status']:10s} {r['name']:22s} "
              f"n_eff={r['n_eff'] if r['n_eff'] is not None else '-':>8}  n_obs={r['n_obs']:5d}"
              f"  {r['why'][:70]}")
    c = d["clusters"]
    print(f"  clusters: {len(c['occupied_either'])}/{c['declared']} occupied, "
          f"{len(c['empty_in_both'])} empty, "
          f"{c['n_unclassified_traded']} traded sleeve(s) UNCLASSIFIED")
    print(f"  empty: {', '.join(c['empty_in_both'])}")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
