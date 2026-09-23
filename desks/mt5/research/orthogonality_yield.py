"""THE TWO SIGNALS THAT DECIDE WHERE THE NEXT JUDGE-HOUR GOES -- measured, per producer.

The principal's order (2026-09-23): "compute should always go more to discovering things which
produce orthogonality along with ones who produce the most certis." Two signals, together, and
neither one alone.

WHAT WAS WRONG, MEASURED ON THE TRADING BOX. `judge_coverage.rank_by_value` already carried an
orthogonality term -- `(1 + breadth_gain)`, where `breadth_gain = 1/(1 + cluster_occupancy)` from
`EFFECTIVE_BREADTH.json`. That artifact clusters the LIVE SLEEVES OF THE BOOK, not the research
grid, so the term answers "does this family already hold deployed sleeves" and not "does this
producer's output open ground nobody else covers". The two are close to OPPOSITE, and the ranking
showed it: `clock_transition` -- 20,378 raw cells over 194 distinct ground cells, 105 near-copies
each, and a leave-one-out effective-rank contribution of 0.0000 -- drew the FULL orthogonality
bonus of 2.0, while `turn_of_month`, the single most orthogonal producer on the desk at 0.0611,
was marked down to 1.1111 for having live sleeves. A term with the wrong sign is worse than no
term, because it is spent with confidence.

THE RIGHT MEASURE IS MARGINAL AND IT IS A LEAVE-ONE-OUT. Not "how many cells did this producer
emit" -- volume is not information, and `cross_asset_residual` proves it: 59,912 raw cells over
548 ground cells (109 near-copies each) whose removal does not lower the grid's effective rank by
a measurable amount. The measure here is the desk's own: `libs.research.sandbox_rotation.breadth`
builds the producer x (symbol|horizon) indicator matrix, takes the participation ratio of its
singular spectrum, and reports for each producer the DROP when its row is removed. A producer
minting ten thousand near-identical cells scores near zero and the number says why.

WHY ORTHOGONALITY IS PRICED AT ALL, now that the bar does not move (principal, 2026-09-23).
`gate_spec.yaml` pins `fixed_trial_count` and `fixed_variance_of_sharpes` as constants -- "the
gates are the same for everyone no matter the quantity" -- so a redundant cell costs the desk NO
statistical bar and there is no multiplicity charge to model. Volume is free. What is NOT free is
COMPUTE: judge capacity, build time and the hour itself are finite, and an hour spent re-judging
the 109th copy of a cell is an hour the 8,418 reachable empty grid cells did not get. That
opportunity cost is the whole reason this signal exists, and it is why nothing here scores a
producer DOWN for volume -- both signals below are RATES, and both are one-sided.

HOW THE TWO SIGNALS ARE COMBINED, AND WHAT HAPPENS WHEN THEY DISAGREE. They do disagree, badly,
and that is the finding rather than a problem to be tuned away: on the measured pass the top
producers by marginal orthogonality (`turn_of_month`, `lead_lag`, `fx_fixing_reversal`) hold ZERO
certificates, and the top producers by certificate yield (`macro_conditional` at 309.8 certs per
judge-hour, `spread_state`, `overnight_gap_decay`) contribute ZERO marginal rank. Only `carry` and
`range_reversion` score on both axes.

The resolution is that NEITHER SIGNAL MAY VETO THE OTHER. Each becomes a multiplier on [PAR, CEIL]
set by where the producer sits in that signal's own measured distribution -- one-sided, upward
only, exactly the idiom `research_budget.ENGINE_FLOOR` and `GRAVEYARD_FLOOR` already carry and for
the reason recorded there. So a producer that opens new ground and has never certified is LIFTED
by the orthogonality factor and sits at par on the certificate one; one that certifies from
crowded ground is
LIFTED by the certificate factor and sits at par on orthogonality; a producer with both is lifted
by both; a producer with neither runs at par and keeps every cell of the floor it has today.
Because no factor can fall below par, no producer's priority is ever reduced by this module and
the disagreement never needs arbitration. That is the explicit weighting: EQUAL AUTHORITY, one
shared ceiling, and the evidence -- not a tuned constant -- decides which factor moves.

UNMEASURED IS NOT ZERO (L1.28a), and this is the part most likely to go wrong. A producer with no
judged cell has NO certificate rate -- not a rate of zero. `certs_per_judge_hour` is None for it,
its certificate factor is PAR, and its status is published as UNMEASURED. It is never ranked below
a producer measured to fail. The 18 families holding 1,325 cells that no judge has ever reached
are exactly the ones a yield-chasing allocator would bury, and they carry 0.0814 of marginal rank
between them.

THE 23 ZERO-PASS FAMILIES ARE NOT ONE THING, so `diagnose` separates them and the state is
published per producer:

    BANNED         the family may not reach capital at all (`family_policy`); it already draws
                   zero quota and appears here only so the zero is visibly EXPECTED, never read
                   as a dead mechanism. `discovered` is this and nothing else.
    UNMEASURED     no judged cell. Absence, not evidence. Par on the certificate axis, full
                   weight on the orthogonality axis it CAN be measured on.
    UNDER_JUDGED   judged, but the Beta(1,1) upper credible bound still admits the pooled rate,
                   so its zero is not yet distinguishable from ordinary bad luck at this n.
    MEASURED_ZERO  judged enough that the upper bound has fallen below the pooled rate. THIS is
                   the zero that carries information -- and it still only costs the producer its
                   LIFT, never its floor, because the factor stops at par.
    CERTIFYING     has produced at least one certificate.

WHAT THIS MODULE MAY NOT DO. The desk refused adaptive allocation over the search grid on
2026-08-29 (graveyard: "incompatible with pre-registered multiplicity"), with one named re-open
condition: "an allocator restricted to re-ORDERING cells within a fixed pre-registered membership
(ordering free, membership pre-registered)". This module answers that condition exactly. It emits
FACTORS ONLY. It never adds a cell to the docket, never removes one, never changes a gate, never
touches `gate_spec.yaml`, and never lowers a quota: `judge_coverage.allocate` still hands every
family holding backlog its equal share of `FLOOR_SHARE` before this is consulted, and the factors
re-order the remainder alone. Membership is pre-registered; only the order is free.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
OUT = DESK / "reports" / "ORTHOGONALITY_YIELD.json"

#: Par. No factor this module emits may fall below it, so no producer is ever ranked lower because
#: of anything measured here -- the standing order of 2026-09-08 (never reduce aggressiveness) in
#: the only form an allocator can honour it: re-weight upward, starve nothing.
PAR = 1.0
#: The one shared ceiling. BOTH signals get it, which is the weighting statement: neither axis is
#: privileged by construction, so the data decides which one moves a producer. 2.0 is the value
#: every other one-sided factor on the desk already uses (`research_budget.ENGINE_CEIL`,
#: `GRAVEYARD_CEIL`, `_meta_factor`, `_paradigm_factor`), not a number invented here.
CEIL = 2.0
#: Ledger rows whose downstream status begins with this were never judged -- the sweep's build
#: budget ran out first. Counting them as judged is the trap `external_gauntlet` documents, and
#: counting them would turn an unjudged producer into a measured failure.
NOT_JUDGED_PREFIX = "NOT_RUN"
#: Only for publishing a readable certs-per-HOUR number. The FACTOR is a ratio of two rates that
#: both carry this constant, so it cancels exactly and no assumed capacity can move the ranking.
JUDGE_SECONDS_PER_CELL = 0.081
MAX_ROWS = 400_000
UNMEASURED = "UNMEASURED"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def ground_inventory(db: Path | None = None) -> tuple[dict[str, set[str]], dict[str, int], str]:
    """({family: {"symbol|horizon"}}, {family: raw cell count}, why) from the candidate registry.

    The GROUND is deliberately keyed without the family: two producers working the same
    instruments at the same horizons are competing for the same ground, and that overlap is the
    thing an orthogonality measure has to see. Keying by the full grid cell would make every
    producer trivially disjoint and the effective rank would then measure nothing but volume.
    """
    path = db or REGISTRY
    if not path.exists():
        return {}, {}, f"{UNMEASURED}: no candidate registry at {path}"
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return {}, {}, f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
    try:
        cur = con.execute(
            "select lower(coalesce(nullif(family,''),'?')), "
            "lower(coalesce(nullif(symbol,''),'?')), "
            "lower(coalesce(nullif(horizon,''),'?')) from research_candidates limit ?",
            (MAX_ROWS,))
        ground: dict[str, set[str]] = defaultdict(set)
        raw: dict[str, int] = defaultdict(int)
        for fam, sym, hor in cur:
            ground[str(fam)].add(f"{sym}|{hor}")
            raw[str(fam)] += 1
        return dict(ground), dict(raw), ""
    except sqlite3.Error as exc:
        return {}, {}, f"{UNMEASURED}: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()


def marginal_orthogonality(ground: dict[str, set[str]]) -> dict[str, Any]:
    """Leave-one-out effective-rank contribution per producer, from the desk's own breadth measure.

    `libs.research.sandbox_rotation.breadth` is already the LOO participation ratio and is already
    tested; nothing is re-derived here. It clamps a marginal at zero, so the unclamped delta is
    recomputed alongside it: a producer whose REMOVAL RAISES the effective rank is concentrating
    the grid rather than spanning it, and a clamped 0.0 would hide that from the reader.
    """
    if not ground:
        return {"available": False, "why": f"{UNMEASURED}: no candidate row to span",
                "total": 0.0, "columns": 0, "marginal": {}, "marginal_raw": {}}
    from libs.research.sandbox_rotation import breadth
    from libs.risk.fx_exposure import effective_rank

    cells = {fam: sorted(cs) for fam, cs in ground.items()}
    doc = breadth(cells)
    total = float(doc.get("total") or 0.0)
    columns = sorted({c for cs in cells.values() for c in cs})
    index = {c: i for i, c in enumerate(columns)}
    ids = sorted(cells)
    matrix = [[0.0] * len(columns) for _ in ids]
    for r, fam in enumerate(ids):
        for c in cells[fam]:
            matrix[r][index[c]] = 1.0
    raw_marginal: dict[str, float] = {}
    for r, fam in enumerate(ids):
        without = [row for i, row in enumerate(matrix) if i != r]
        raw_marginal[fam] = round(total - (effective_rank(without) if without else 0.0), 6)
    marginal = doc.get("marginal")
    return {"available": True, "why": "", "total": total,
            "columns": int(doc.get("columns") or 0),
            "marginal": marginal if isinstance(marginal, dict) else {},
            "marginal_raw": raw_marginal, "basis": str(doc.get("basis") or "")}


def certificate_yield(ledger: Path | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    """({family: {judged, certs, not_run, certs_per_judge_hour}}, why) from the gate ledger.

    `NOT_RUN*` rows are excluded from `judged` on purpose: they were never computed, so counting
    them would manufacture a measured failure out of a build budget that ran out.
    """
    path = ledger or GATE_LEDGER
    if not path.exists():
        return {}, f"{UNMEASURED}: no gate verdict ledger at {path}"
    judged: dict[str, int] = defaultdict(int)
    certs: dict[str, int] = defaultdict(int)
    not_run: dict[str, int] = defaultdict(int)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                fam = str(row.get("family") or "?").lower()
                if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
                    not_run[fam] += 1
                    continue
                judged[fam] += 1
                if row.get("passed") is True:
                    certs[fam] += 1
    except OSError as exc:
        return {}, f"{UNMEASURED}: ledger unreadable ({type(exc).__name__}: {exc})"
    out: dict[str, dict[str, Any]] = {}
    for fam in set(judged) | set(not_run):
        n = judged.get(fam, 0)
        hours = n * JUDGE_SECONDS_PER_CELL / 3600.0
        out[fam] = {
            "judged": n, "certs": certs.get(fam, 0), "not_run": not_run.get(fam, 0),
            "judge_hours": round(hours, 6),
            # None, NEVER 0.0. A producer no judge has reached has no rate to report, and a zero
            # here would be read downstream as a measured failure (L1.28a).
            "certs_per_judge_hour": round(certs.get(fam, 0) / hours, 4) if hours > 0 else None,
        }
    return out, ""


def _posterior_hi(passed: int, judged: int) -> float:
    """Upper credible bound of Beta(1 + passed, 1 + judged - passed), the desk's own optimism.

    Two standard deviations above the posterior mean, clipped to [0, 1] -- the same shape
    `judge_coverage.family_priors` spends so an unjudged family ranks on 1.0 rather than on zero.
    """
    a = 1.0 + max(0, passed)
    b = 1.0 + max(0, judged - passed)
    mean = a / (a + b)
    var = (a * b) / (((a + b) ** 2) * (a + b + 1.0))
    return float(max(0.0, min(1.0, mean + 2.0 * (var ** 0.5))))


def diagnose(family: str, judged: int, certs: int, pooled: float) -> tuple[str, str]:
    """(state, why) for this producer's zero. A zero is never one thing -- see the module header."""
    banned = False
    for mod in ("research.family_policy", "family_policy"):
        try:
            policy = __import__(mod, fromlist=["family_banned"])
            banned = bool(policy.family_banned(family))
            break
        except Exception:
            continue
    if banned:
        return "BANNED", (f"{family} may not reach capital; its zero is EXPECTED and it already "
                          f"draws no quota. Judged rows here are historical.")
    if certs > 0:
        return "CERTIFYING", f"{certs} certificate(s) over {judged} judged cells"
    if judged <= 0:
        return "UNMEASURED", ("no judged cell: absence, not evidence. Par on the certificate axis "
                              "and full weight on the orthogonality axis (L1.28a)")
    hi = _posterior_hi(0, judged)
    if hi >= pooled:
        return "UNDER_JUDGED", (f"0 of {judged}: the Beta(1,1) upper bound {hi:.5f} still admits "
                                f"the pooled rate {pooled:.5f}, so this zero is not yet "
                                f"distinguishable from bad luck at this n")
    return "MEASURED_ZERO", (f"0 of {judged}: the upper bound {hi:.5f} has fallen below the pooled "
                             f"rate {pooled:.5f}. This zero carries information -- and it still "
                             f"costs this producer only its LIFT, never its floor")


def _factor(value: float | None, population: list[float]) -> tuple[float, float]:
    """(factor, percentile) -- where this producer sits in its signal's measured distribution.

    THE FACTOR IS THE PERCENTILE, NOT A RATIO TO THE MEAN, AND THE FIRST REAL PASS IS WHY. Against
    the mean the orthogonality signal SATURATED: mean marginal rank was 0.008825 and nine
    producers came back clipped at exactly x2.000, from `turn_of_month` at 0.0611 down to
    `joint_genome` at 0.0179. `judge_coverage.allocate` walks the ranking greedily, in ORDER, so
    nine identical factors hand the ordering of that whole group straight back to the term that
    was blind to orthogonality in the first place -- the signal is measured, published, and then
    discarded exactly where it was supposed to bite.

    The share of the population strictly BELOW this value is monotone in the signal, so no two
    distinct readings ever tie and the order survives the clip. It also fixes the bottom of the
    scale: the lowest reading maps to PAR exactly, rather than to whatever a ratio happens to
    give, so a producer measured at zero marginal rank keeps precisely what it has today.

    An absent value is PAR with percentile 0.0 -- UNMEASURED is not a low percentile, it is no
    percentile, and it must never be ranked as one (L1.28a).
    """
    if value is None or not population:
        return PAR, 0.0
    pct = sum(1 for p in population if p < value) / float(len(population))
    return PAR + (CEIL - PAR) * pct, pct


def signals(db: Path | None = None, ledger: Path | None = None) -> dict[str, Any]:
    """The whole measurement: both signals, both factors and the diagnosis, per producer."""
    ground, raw, why_g = ground_inventory(db)
    ortho = marginal_orthogonality(ground)
    yields, why_y = certificate_yield(ledger)

    tot_judged = sum(int(v["judged"]) for v in yields.values())
    tot_certs = sum(int(v["certs"]) for v in yields.values())
    pooled = (tot_certs / tot_judged) if tot_judged > 0 else 0.0

    marg: dict[str, float] = {k: float(v) for k, v in (ortho.get("marginal") or {}).items()}
    marg_raw: dict[str, float] = {k: float(v) for k, v in (ortho.get("marginal_raw") or {}).items()}

    # The two means the factors are measured against. Orthogonality averages over every producer
    # HOLDING INVENTORY (a measured 0.0 is a real reading and belongs in the mean); certificate
    # yield averages only over producers a judge has actually reached, because an unmeasured one
    # has no rate to average and including it as a zero would drag the par down for everyone.
    ortho_pop = [marg.get(f, 0.0) for f in ground]
    ortho_mean = (sum(ortho_pop) / len(ortho_pop)) if ortho_pop else 0.0
    cert_pop = [float(v["certs_per_judge_hour"]) for v in yields.values()
                if v.get("certs_per_judge_hour") is not None]
    cert_mean = (sum(cert_pop) / len(cert_pop)) if cert_pop else 0.0

    rows: list[dict[str, Any]] = []
    factors: dict[str, dict[str, Any]] = {}
    for fam in sorted(set(ground) | set(yields)):
        y = yields.get(fam) or {"judged": 0, "certs": 0, "not_run": 0, "judge_hours": 0.0,
                                "certs_per_judge_hour": None}
        judged, certs = int(y["judged"]), int(y["certs"])
        state, why_state = diagnose(fam, judged, certs, pooled)
        cph = y["certs_per_judge_hour"]
        m = marg.get(fam, 0.0)
        o_f, o_pct = _factor(m, ortho_pop)
        # UNMEASURED gets PAR on the certificate axis because it has no rate, not a low one.
        # A BANNED producer draws no quota at all, so a lift would be meaningless; par keeps it
        # out of the ranking's way without asserting anything about the mechanism.
        if state in ("UNMEASURED", "BANNED"):
            c_f, c_pct = PAR, 0.0
        else:
            c_f, c_pct = _factor(float(cph) if cph is not None else None, cert_pop)
        if state == "BANNED":
            o_f, o_pct = PAR, 0.0
        ground_cells = len(ground.get(fam, ()))
        rows.append({
            "family": fam, "state": state, "why_state": why_state,
            "raw_cells": raw.get(fam, 0), "ground_cells": ground_cells,
            "raw_per_ground_cell": (round(raw.get(fam, 0) / ground_cells, 2)
                                    if ground_cells else None),
            "marginal_rank": round(m, 6), "marginal_rank_unclamped": marg_raw.get(fam),
            "judged": judged, "certs": certs, "not_run": int(y["not_run"]),
            "judge_hours": y["judge_hours"], "certs_per_judge_hour": cph,
            "orthogonality_factor": round(o_f, 4), "certificate_factor": round(c_f, 4),
            # BOTH READINGS, SO THE WEIGHTING IS ARGUABLE RATHER THAN ASSERTED. The percentile is
            # what the factor spends; the ratio to the cross-producer mean is the same evidence in
            # the units every other desk factor is quoted in, published so a reader can disagree.
            "orthogonality_percentile": round(o_pct, 4),
            "certificate_percentile": round(c_pct, 4),
            "orthogonality_vs_mean": (round(m / ortho_mean, 3) if ortho_mean > 0 else None),
            "certs_vs_mean": (round(float(cph) / cert_mean, 3)
                              if cph is not None and cert_mean > 0 else None),
            "combined_factor": round(o_f * c_f, 4),
        })
        factors[fam] = {"orthogonality_factor": round(o_f, 4),
                        "certificate_factor": round(c_f, 4),
                        "marginal_rank": round(m, 6), "certs_per_judge_hour": cph,
                        "state": state}
    rows.sort(key=lambda r: (-float(r["combined_factor"]), str(r["family"])))

    states: dict[str, int] = defaultdict(int)
    for r in rows:
        states[str(r["state"])] += 1
    lifted = [r for r in rows if float(r["combined_factor"]) > PAR]
    verdict = "MEASURED" if (ortho.get("available") and yields) else UNMEASURED
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "verdict": verdict,
        "law": ("BOTH SIGNALS, ONE SHARED CEILING, NEITHER MAY VETO THE OTHER. Every factor here "
                "is one-sided upward from par, so this module can lift a producer's priority and "
                "can never lower it; the judge's floor (judge_coverage.FLOOR_SHARE) is untouched "
                "and every family holding backlog still draws it. Volume is never scored down -- "
                "the bar is fixed (gate_spec.yaml) so redundancy costs no statistical charge; "
                "what it costs is COMPUTE, and that is what the orthogonality signal prices."),
        "membership": ("FACTORS ONLY -- this re-orders the remainder within a pre-registered "
                       "membership and mints, drops and re-gates nothing (graveyard 2026-08-29 "
                       "re-open condition)."),
        "orthogonality": {
            "available": bool(ortho.get("available")), "why": why_g or ortho.get("why") or "",
            "total_effective_rank": ortho.get("total"), "columns": ortho.get("columns"),
            "mean_marginal": round(ortho_mean, 6), "basis": ortho.get("basis"),
        },
        "certificates": {
            "why": why_y, "judged_total": tot_judged, "certs_total": tot_certs,
            "pooled_pass_rate": round(pooled, 8), "mean_certs_per_judge_hour": round(cert_mean, 4),
            "n_measured": len(cert_pop),
        },
        "states": dict(states),
        "n_producers": len(rows), "n_lifted": len(lifted),
        "factors": factors,
        "producers": rows,
    }


def build(db: Path | None = None, ledger: Path | None = None,
          out: Path | None = None) -> dict[str, Any]:
    """Measure and publish. Returns the document it wrote."""
    doc = signals(db, ledger)
    dest = out or OUT
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError:
        pass
    return doc


def published_factors(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The factor table as a consumer sees it. An absent or stale artifact is {} -- every producer
    then runs at par, which is what an unmeasured signal is owed (never a silent demotion)."""
    doc = _read_json(path or OUT)
    table = doc.get("factors")
    if not isinstance(table, dict) or doc.get("verdict") != "MEASURED":
        return {}
    return {str(k): v for k, v in table.items() if isinstance(v, dict)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__ or "")
    # `--once` and `--budget-s` are the hourly cycle's own leg contract. This leg is a single
    # bounded measurement -- one registry scan, one ledger scan -- so it has nothing to loop over
    # and nothing to shed; the budget is accepted and reported so the compute ledger's row is
    # honest about what it was given rather than silently ignoring it.
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=0.0)
    args = ap.parse_args(argv)
    started = datetime.now(tz=UTC)
    doc = build()
    doc["budget_s"] = args.budget_s
    doc["elapsed_s"] = round((datetime.now(tz=UTC) - started).total_seconds(), 2)
    with contextlib.suppress(OSError):
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    o, c = doc["orthogonality"], doc["certificates"]
    print(f"orthogonality_yield: {doc['verdict']} -- {doc['n_producers']} producers, "
          f"{doc['n_lifted']} lifted above par")
    print(f"  grid effective rank {o.get('total_effective_rank')} over {o.get('columns')} "
          f"ground columns; mean marginal {o.get('mean_marginal')}")
    print(f"  certificates {c.get('certs_total')} over {c.get('judged_total')} judged; pooled "
          f"{c.get('pooled_pass_rate')}; mean {c.get('mean_certs_per_judge_hour')}/judge-hour")
    print(f"  states: {doc.get('states')}")
    for row in doc["producers"][:10]:
        print(f"    {row['family']:28s} x{row['combined_factor']:.3f} "
              f"(ortho x{row['orthogonality_factor']:.3f}, cert x{row['certificate_factor']:.3f}) "
              f"{row['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
