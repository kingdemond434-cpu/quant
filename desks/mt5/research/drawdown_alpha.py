"""THE DRAWDOWN-ALPHA FACTORY: the book's own worst periods, published as a research target.

    "If your main strategies make +200 in good states and -80 during their bad states, you can
     increase leverage only so far. Find another edge that earns +40 precisely during those -80
     periods. Even if its standalone Sharpe is mediocre, portfolio growth can explode because it
     reduces the denominator restricting leverage. Feed the factory: here are the worst 5%, 10%,
     20% of portfolio days. Find state variables and mechanisms that predict positive returns
     specifically during them."                                    -- the principal, 2026-09-05

WHY THIS AND NOT `research/tail_alpha_search.py`, WHICH ALREADY EXISTS AND IS RIGHT. That module
is a PROPOSER: it takes the book's worst decile and sweeps price families across the universe
looking for cells that pay there. It needs bars for every symbol, a compute budget, and it answers
"which recipe pays in the tail". It does not publish the tail itself. So the desk had a search
over drawdown alpha and no DESCRIPTION of its own drawdowns -- no list of the worst periods, no
state signature for them, and no measurement of which parts of the EXISTING book already earn
inside them. This is the feedstock half: it costs no bars and no sweep, it says which of the
book's own clusters are already tail-positive, and it hands the hunter the state coordinates.
`tail_alpha_search` stays the searcher; this is what feeds it.

THE ONE THING THAT MAKES THIS MEASUREMENT HONEST IS LEAVE-ONE-OUT. A candidate's conditional
expectancy on "the book's worst periods" is circular when the candidate is IN the book: the
sleeve that lost the most is what made the period bad, so it is guaranteed to score badly and the
sleeve that sat out is guaranteed to score well. Every band here is cut on the book EXCLUDING the
candidate, so the question asked is the one that matters -- when the REST of the book is hurting,
what does this earn? -- and a big loser is not condemned by its own presence in the sample.

THE MULTIPLICITY BURDEN IS CARRIED, NEVER SET ASIDE. Three quantile bands times two granularities
times every cluster and every sleeve is hundreds of hypotheses, and the best of hundreds looks
good under the null. Every row carries `n_tests` and `t_deflated = t - E[max_N Z]` from
`research/multiplicity.py`, unmodified, and a row is a CANDIDATE only at `t_deflated >= 2.0` with
`n >= MIN_N`. A row below the sample floor is UNMEASURED, which is not a weak candidate: it is the
absence of a measurement, and it is never queued as though it were evidence.

WHAT IS MEASURABLE TODAY AND WHAT IS NOT. On this desk's shadow history the daily book series is
FOURTEEN days long, so the worst 5% of days is ONE day and no daily band can reach any sample
floor. The hourly series has 162 periods, where the 10% and 20% bands do. Both are computed and
both report their own sample counts; the daily verdicts will read UNMEASURED until the history is
there, and saying that plainly is the point of computing them.
"""
from __future__ import annotations

import argparse
import json
import math
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

from libs.research.alpha_clusters import CLUSTERS, classify_sleeve  # noqa: E402

OUT = BASE / "reports" / "DRAWDOWN_ALPHA.json"
BREADTH = BASE / "reports" / "EFFECTIVE_BREADTH.json"

#: The bands the principal named. Each is cut on the book EXCLUDING the candidate being scored.
BANDS: tuple[float, ...] = (0.05, 0.10, 0.20)

#: Period granularities. A "portfolio day" is the natural unit and this desk does not yet have
#: enough of them; the hourly book is the finest unit its own opportunity curve already uses.
GRANULARITIES: tuple[tuple[str, str], ...] = (("day", "%Y-%m-%d"), ("hour", "%Y-%m-%dT%H"))

#: Observations inside a band before a conditional expectancy is a measurement. The same floor
#: `opportunity_curve` and `regime_coverage` use for a conditional verdict -- not lowered here,
#: because conditioning multiplies hypotheses and a 2-3x edge across twenty slices at n=8 each is
#: noise wearing a good number.
MIN_N = 8

#: |t| after multiplicity deflation before a row is called a CANDIDATE. The desk's standing bar
#: (`research/multiplicity.py`: "a survivor needs t_deflated > 2 to keep gate status").
T_LINE = 2.0

#: Observations before the candidate's correlation TO the drawdown is reported at all. A
#: correlation on five points is not a diversification claim.
MIN_RHO_N = 10

CANDIDATE, WATCH, NEGATIVE, UNMEASURED = "CANDIDATE", "WATCH", "NEGATIVE", "UNMEASURED"


def _load() -> list[tuple[str, str, float]]:
    """(sleeve, ISO entry time, R) for every realised shadow trade the desk holds."""
    from research.state_admission_run import load_trades
    return [(str(t.sleeve), str(t.when), float(t.r)) for t in load_trades("shadow")]


def _period(when: str, fmt: str) -> str:
    """The period label a trade's entry falls in. Unparseable stamps are the caller's problem."""
    return datetime.fromisoformat(when).astimezone(UTC).strftime(fmt)


def _matrix(trades: list[tuple[str, str, float]], fmt: str,
            key: Any) -> tuple[list[str], dict[str, dict[str, float]]]:
    """(ordered periods, {group: {period: summed R}}) with absent periods ABSENT, never zero.

    A period a group did not trade in is not a period it returned zero in. Zero-filling here would
    manufacture observations inside every drawdown band and inflate every sample count -- the same
    defect `mt5desk/independence.py` records inflating k_eff by 1.36x when `record_sleeve_returns`
    did it.
    """
    per: dict[str, dict[str, float]] = defaultdict(dict)
    periods: set[str] = set()
    for sleeve, when, r in trades:
        try:
            p = _period(when, fmt)
        except (TypeError, ValueError):
            continue
        g = key(sleeve)
        per[g][p] = per[g].get(p, 0.0) + r
        periods.add(p)
    return sorted(periods), dict(per)


def _t_stat(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    a = np.asarray(xs, dtype="float64")
    sd = float(a.std(ddof=1))
    if sd <= 0:
        return 0.0
    return float(a.mean() / (sd / math.sqrt(n)))


def _score(group: str, own: dict[str, float], others: dict[str, dict[str, float]],
           periods: list[str], band: float) -> dict[str, Any]:
    """One candidate against one band, with the band cut on the book WITHOUT that candidate."""
    loo: dict[str, float] = {}
    for g, series in others.items():
        if g == group:
            continue
        for p, v in series.items():
            loo[p] = loo.get(p, 0.0) + v
    have = [p for p in periods if p in loo]
    out: dict[str, Any] = {"candidate": group, "band": band,
                           "n_periods_in_book_excluding_candidate": len(have)}
    if not have:
        out.update({"verdict": UNMEASURED, "n": 0,
                    "why": "the book without this candidate has no periods to rank"})
        return out
    values = np.array([loo[p] for p in have], dtype="float64")
    threshold = float(np.quantile(values, band))
    bad = [p for p in have if loo[p] <= threshold]
    inside = [own[p] for p in bad if p in own]
    out.update({"n_bad_periods": len(bad), "band_threshold_r": round(threshold, 4), "n": len(inside)})
    if len(inside) < MIN_N:
        out.update({"verdict": UNMEASURED,
                    "why": (f"{len(inside)} observation(s) inside the worst {band:.0%} of "
                            f"{len(have)} periods, below the {MIN_N} floor -- UNMEASURED is not a "
                            "weak candidate, it is the absence of a measurement")})
        return out
    arr = np.asarray(inside, dtype="float64")
    paired = [(own[p], loo[p]) for p in bad if p in own]
    rho: float | None = None
    if len(paired) >= MIN_RHO_N:
        a = np.array([x for x, _ in paired], dtype="float64")
        b = np.array([y for _, y in paired], dtype="float64")
        if a.std() > 0 and b.std() > 0:
            rho = float(np.corrcoef(a, b)[0, 1])
    out.update({
        "mean_r_in_drawdown": round(float(arr.mean()), 4),
        "sum_r_in_drawdown": round(float(arr.sum()), 4),
        "t_raw": round(_t_stat(inside), 3),
        "rho_to_drawdown": None if rho is None else round(rho, 3),
        "rho_n": len(paired) if rho is not None else 0,
        "mean_r_all_periods": round(float(np.mean(list(own.values()))), 4) if own else None,
    })
    return out


def _state_signature(bad: list[str], every: list[str], fmt: str) -> list[dict[str, Any]]:
    """Which states the bad periods over-represent, against their own base rate.

    THE STATE VARIABLE IS THE DELIVERABLE. A hunter cannot act on "the book loses sometimes"; it
    can act on "62% of the worst decile is Monday and Monday is 21% of all periods". Every row
    carries both counts, because a lift computed on four periods is arithmetic, not evidence, and
    the reader must be able to see which it is.

    NO P-VALUE IS ATTACHED. These are descriptive slices of the same sample the bands were cut
    from, they are not independent, and a significance number here would be read as one. The
    counts are the evidence; the multiplicity burden that matters is carried by the candidate
    rows, which is where the promotion decision would be made.
    """
    from research.session_phase import phase_for_hour

    def labels(p: str) -> dict[str, str]:
        try:
            dt = datetime.strptime(p, fmt).replace(tzinfo=UTC)
        except ValueError:
            return {}
        out = {"weekday": dt.strftime("%a")}
        if "H" in fmt:
            out["hour_utc"] = f"{dt.hour:02d}"
            out["session_phase"] = str(phase_for_hour(dt.hour))
        return out

    base: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hit: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in every:
        for dim, val in labels(p).items():
            base[dim][val] += 1
    for p in bad:
        for dim, val in labels(p).items():
            hit[dim][val] += 1
    rows: list[dict[str, Any]] = []
    n_bad, n_all = len(bad), len(every)
    for dim, vals in sorted(hit.items()):
        for val, n in sorted(vals.items(), key=lambda kv: -kv[1]):
            b = base[dim].get(val, 0)
            if not b or not n_bad or not n_all:
                continue
            share_bad, share_all = n / n_bad, b / n_all
            rows.append({"dimension": dim, "state": val, "n_in_drawdown": n,
                         "n_all_periods": b, "share_of_drawdown": round(share_bad, 4),
                         "share_of_all": round(share_all, 4),
                         "lift": round(share_bad / share_all, 3) if share_all > 0 else None})
    rows.sort(key=lambda r: -(r["lift"] or 0.0))
    return rows


def _tasks(rows: list[dict[str, Any]], signatures: dict[str, dict[str, list[dict[str, Any]]]],
           empty_crisis: bool) -> list[dict]:
    """Research instructions: the state coordinates of the drawdown, and any measured candidate.

    ONE TASK PER GRANULARITY, FROM THE TIGHTEST BAND THAT REACHES THE SAMPLE FLOOR. The worst 5%
    is the most informative window and usually the thinnest; taking the tightest band that still
    has a state seen MIN_N times keeps the instruction as close to the real tail as the evidence
    allows, and refusing to emit anything when no band reaches the floor is the honest outcome --
    a state signature built on three periods would be a research instruction manufactured from
    noise, and the hunter cannot tell the difference once it is in the queue.
    """
    tasks: list[dict] = []
    for gran, by_band in sorted(signatures.items()):
        chosen: tuple[str, list[dict[str, Any]]] | None = None
        for band in BANDS:                      # tightest first
            sig = by_band.get(f"worst_{int(band * 100)}pct") or []
            top = [s for s in sig if s["n_in_drawdown"] >= MIN_N][:4]
            if top:
                chosen = (f"{band:.0%}", top)
                break
        if chosen is None:
            continue
        band_label, top = chosen
        where = "; ".join(f"{s['dimension']}={s['state']} is {s['share_of_drawdown']:.0%} of the "
                          f"drawdown against {s['share_of_all']:.0%} of all periods "
                          f"(n={s['n_in_drawdown']}, lift {s['lift']}x)" for s in top)
        tasks.append({
            "source": "drawdown_alpha", "kind": "drawdown_state_target",
            "title": f"State signature of the book's worst {band_label} of {gran} periods",
            "description": (
                f"The book's own drawdown, worst {band_label} by {gran}: {where}. Propose a "
                "mechanism with POSITIVE expectancy specifically in that state, on the MT5/Fusion "
                "universe. Standalone Sharpe is NOT the bar here -- a mediocre edge that pays "
                "while the book is losing raises the leverage the whole book can carry, which is "
                "worth more than another sleeve correlated with what already works. Carry the "
                f"sample size: a conditional edge needs n >= {MIN_N} in the band and t_deflated "
                f">= {T_LINE} after the multiplicity of every slice tried."),
            "granularity": gran, "band": band_label, "status": None,
            "consumer": "tail_alpha_search / deepening_worker / proposers",
        })
    live = [r for r in rows if r.get("verdict") in (CANDIDATE, WATCH)]
    for r in sorted(live, key=lambda x: -(x.get("t_deflated") or 0.0))[:5]:
        tasks.append({
            "source": "drawdown_alpha", "kind": "drawdown_alpha_candidate",
            "title": (f"{r['candidate']} earns {r['mean_r_in_drawdown']:+.2f}R inside the book's "
                      f"worst {r['band']:.0%} ({r['granularity']}, n={r['n']})"),
            "description": (
                f"Conditional expectancy {r['mean_r_in_drawdown']:+.4f}R on n={r['n']} "
                f"observations inside the worst {r['band']:.0%} of {r['granularity']} periods, cut "
                "on the book EXCLUDING this candidate. t_raw "
                f"{r['t_raw']}, t_deflated {r['t_deflated']} against {r['n_tests']} tests, "
                f"correlation to the drawdown {r['rho_to_drawdown']} (n={r['rho_n']}). Verdict "
                f"{r['verdict']}. Deepen this cell: does the edge survive out of sample, and is "
                "its cause specific to the drawdown state or incidental to it?"),
            "candidate": r["candidate"], "band": r["band"], "status": None,
            "consumer": "deepening_worker / tail_alpha_search",
        })
    if empty_crisis:
        tasks.append({
            "source": "drawdown_alpha", "kind": "empty_alpha_cluster",
            "title": "No sleeve in the book is a crisis / drawdown edge",
            "description": (
                "Every sleeve the book holds is scored above; none is a mechanism DESIGNED to pay "
                "inside the book's own worst periods. That is the cluster with the largest "
                "leverage consequence: the binding constraint on total heat is the depth of the "
                "book's bad states, not the height of its good ones. Hunt forced-deleveraging "
                "mechanisms on the MT5/Fusion universe -- stop cascades, margin liquidation, the "
                "bid that leaves when everyone needs it."),
            "cluster": "crisis_drawdown", "status": None,
            "consumer": "tail_alpha_search / proposers",
        })
    return tasks


def _crisis_cluster_empty(trades: list[tuple[str, str, float]]) -> tuple[bool, str]:
    """Whether the book holds a crisis/drawdown sleeve, from the PUBLISHED breadth artifact.

    ONE SOURCE OF TRUTH FOR CLUSTER OCCUPANCY. `alpha_breadth` classifies both the traded and the
    CERTIFIED book; this module sees only what has traded. Recomputing occupancy here from the
    trade list alone would report the crisis cluster empty while a certified crisis sleeve sat in
    the canon waiting for its first fill, and the two artifacts would then disagree about the same
    word. The artifact is preferred and the local recomputation is the fallback, with the fallback
    said out loud rather than silently substituted.
    """
    try:
        doc = json.loads(BREADTH.read_text("utf-8"))
        empty = list((doc.get("clusters") or {}).get("empty_in_both") or [])
        if empty:
            return "crisis_drawdown" in empty, ""
        occupied = list((doc.get("clusters") or {}).get("occupied_either") or [])
        if occupied:
            return "crisis_drawdown" not in occupied, ""
    except (OSError, ValueError, AttributeError):
        pass
    traded = {classify_sleeve(s) for s, _, _ in trades}
    return ("crisis_drawdown" not in traded,
            f"{BREADTH.name} absent or carries no cluster occupancy; the crisis-cluster verdict "
            "is recomputed from the TRADED book alone, so a certified crisis sleeve that has not "
            "filled yet would not be seen")


def run(write_queue: bool = True) -> dict[str, Any]:
    from research.multiplicity import deflate_t, expected_max_z

    trades = _load()
    doc: dict[str, Any] = {"generated_utc": datetime.now(tz=UTC).isoformat(),
                           "n_trades": len(trades), "bands": list(BANDS), "min_n": MIN_N,
                           "t_line": T_LINE, "gaps": {}}
    if not trades:
        doc["gaps"]["ledgers"] = "no shadow ledger on this tree; nothing to measure"
        doc["rows"] = []
        doc["windows"] = {}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        return doc

    rows: list[dict[str, Any]] = []
    windows: dict[str, Any] = {}
    signatures: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for gran, fmt in GRANULARITIES:
        periods, by_sleeve = _matrix(trades, fmt, lambda s: s)
        _, by_cluster = _matrix(trades, fmt, classify_sleeve)
        book = {p: sum(s.get(p, 0.0) for s in by_sleeve.values()) for p in periods}
        gran_windows: dict[str, Any] = {"n_periods": len(periods)}
        for band in BANDS:
            if periods:
                thr = float(np.quantile([book[p] for p in periods], band))
                bad = sorted(p for p in periods if book[p] <= thr)
            else:
                thr, bad = 0.0, []
            gran_windows[f"worst_{int(band * 100)}pct"] = {
                "threshold_r": round(thr, 4), "n_periods": len(bad),
                "periods": bad,
                "book_r_in_window": round(sum(book[p] for p in bad), 4),
                "measurable": len(bad) >= MIN_N,
            }
            if bad:
                signatures.setdefault(gran, {})[f"worst_{int(band * 100)}pct"] = _state_signature(
                    bad, periods, fmt)
        windows[gran] = gran_windows
        for level, series in (("cluster", by_cluster), ("sleeve", by_sleeve)):
            for group, own in sorted(series.items()):
                for band in BANDS:
                    r = _score(group, own, series, periods, band)
                    r.update({"granularity": gran, "level": level})
                    rows.append(r)

    # ONE multiplicity burden over EVERY test this module ran, not per granularity and not per
    # band. Splitting the burden by slice is the standard way to make a conditional finding look
    # significant, and it is exactly what the rules forbid.
    n_tests = len(rows)
    for r in rows:
        r["n_tests"] = n_tests
        if r.get("verdict") == UNMEASURED:
            continue
        r["t_deflated"] = round(deflate_t(float(r.get("t_raw") or 0.0), n_tests), 3)
        mean = float(r.get("mean_r_in_drawdown") or 0.0)
        if mean <= 0:
            r["verdict"] = NEGATIVE
        elif r["t_deflated"] >= T_LINE:
            r["verdict"] = CANDIDATE
        else:
            r["verdict"] = WATCH
        r["why"] = (
            f"{r['verdict']}: mean {mean:+.4f}R on n={r['n']} inside the worst "
            f"{r['band']:.0%}, t_raw {r['t_raw']}, t_deflated {r['t_deflated']} after "
            f"E[max Z] over {n_tests} tests"
            + ("" if r["verdict"] != WATCH else
               "; positive but not distinguishable from the best of this many tests"))

    empty_crisis, crisis_why = _crisis_cluster_empty(trades)
    doc["gaps"].update({} if not crisis_why else {"crisis_cluster_source": crisis_why})
    tasks = _tasks(rows, signatures, empty_crisis)
    measured = [r for r in rows if r.get("verdict") != UNMEASURED]
    doc.update({
        "windows": windows,
        "state_signature": signatures,
        "n_tests": n_tests,
        "n_rows_measured": len(measured),
        "n_rows_unmeasured": len(rows) - len(measured),
        "expected_max_z": round(float(expected_max_z(n_tests)), 3),
        "candidates": sorted([r for r in rows if r.get("verdict") == CANDIDATE],
                             key=lambda r: -(r.get("t_deflated") or 0.0)),
        "watch": sorted([r for r in rows if r.get("verdict") == WATCH],
                        key=lambda r: -(r.get("t_deflated") or 0.0)),
        "rows": rows,
        "crisis_cluster_empty": empty_crisis,
        "clusters_declared": [c.key for c in CLUSTERS],
        "instruction": [t["title"] for t in tasks],
        "rule": (
            f"a row is a CANDIDATE only at n >= {MIN_N} inside the band AND t_deflated >= "
            f"{T_LINE} against every test this module ran; every band is cut on the book "
            "EXCLUDING the candidate being scored, so a sleeve is never condemned or credited by "
            "its own contribution to the drawdown it is being measured against"),
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    if write_queue and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="drawdown_alpha")
        except Exception as exc:                                          # noqa: BLE001
            doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    doc["tasks"] = tasks
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    d = run(write_queue=not a.no_queue)
    print(f"DRAWDOWN ALPHA  {d['n_trades']} trades, {d.get('n_tests', 0)} tests, "
          f"E[max Z]={d.get('expected_max_z')}")
    for gran, w in sorted(d.get("windows", {}).items()):
        parts = ", ".join(f"{k.replace('worst_', '')}: n={v['n_periods']} "
                          f"{'MEASURABLE' if v['measurable'] else 'BELOW FLOOR'}"
                          for k, v in sorted(w.items()) if isinstance(v, dict))
        print(f"  {gran:5s} {w['n_periods']:4d} periods -- {parts}")
    print(f"  measured rows {d.get('n_rows_measured')}, unmeasured {d.get('n_rows_unmeasured')}")
    for r in (d.get("candidates") or [])[:6]:
        print(f"  CANDIDATE {r['candidate'][:34]:34s} band={r['band']:.0%} {r['granularity']:5s} "
              f"n={r['n']:3d} mean={r['mean_r_in_drawdown']:+.3f}R t_def={r['t_deflated']}")
    for r in (d.get("watch") or [])[:6]:
        print(f"  watch     {r['candidate'][:34]:34s} band={r['band']:.0%} {r['granularity']:5s} "
              f"n={r['n']:3d} mean={r['mean_r_in_drawdown']:+.3f}R t_def={r['t_deflated']}")
    for gran, by_band in sorted(d.get("state_signature", {}).items()):
        for band, sig in sorted(by_band.items()):
            for s in [x for x in sig if x["n_in_drawdown"] >= MIN_N][:3]:
                print(f"  state {gran:5s} {band:12s} {s['dimension']}={s['state']:14s} "
                      f"{s['share_of_drawdown']:.0%} of drawdown vs {s['share_of_all']:.0%} of "
                      f"all (n={s['n_in_drawdown']}, lift {s['lift']}x)")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
