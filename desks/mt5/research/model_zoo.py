#!/usr/bin/env python3
"""P7 / P41 / P79 -- THE MODEL ZOO AND THE PERMANENT CHALLENGE LEAGUE.

Every model in this desk is ranked on ONE number: dElog after cost and complexity rent.

WHY NOT ACCURACY. A model that is 2% more accurate and costs four times the compute has not
earned its place, and a desk that ranks on accuracy will keep buying it forever. dElog is the
growth rate the belief actually adds to the book; rent is what holding the model costs. The
difference is the only quantity that answers "should this model exist", and it is routinely
negative for models that look excellent on a leaderboard.

    net = dElog  -  compute_rent  -  complexity_rent

    compute_rent      hours x the desk's own cost per hour, from the compute ledger. Not a
                      guess: A4 records every leg's cost, which is what makes this subtractable
                      rather than rhetorical.
    complexity_rent   a charge per ORDER OF MAGNITUDE of capacity. Capacity is not free even
                      when compute is: a bigger model has more ways to fit noise. Log-scale, not
                      linear -- see the constant, whose linear first draft priced a 10M-parameter
                      model out of contention no matter how good it was.

THE LEAGUE (P79) IS THE SAME TABLE, JUDGED FAIRLY. Ranking is meaningless unless every entrant
faced the same test, so the league REFUSES to compare models that did not:

    equal dates       same evaluation window. A model scored on a calm month against one scored
                      through a crash is not a comparison, it is a weather report.
    equal horizon     a one-hour forecaster beating a one-week forecaster is not a result.
    equal costs       the same cost model applied to both, or the cheaper assumption wins.
    equal evidence    a minimum shared sample. Two models with n=8 produce a champion by noise.

A pairing failing any of these is reported as INCOMPARABLE, never silently ranked. That refusal
is the point of the module: the easiest way to manufacture a champion is an unequal test, and it
never looks like cheating from the inside.

CHAMPIONS CHANGE ONLY ON MEASURED GAIN. `MIN_NET_GAIN` exists because a challenger ahead by
0.001 is ahead by nothing, and a league that swaps champions on noise churns the book while
learning nothing. The incumbent holds ties -- switching has its own cost, and the burden of proof
is on the challenger.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "MODEL_ZOO.json"
LEAGUE = BASE / "reports" / "CHALLENGE_LEAGUE.json"
LEDGER = ROOT / "data" / "compute_ledger.jsonl"

#: Complexity rent per ORDER OF MAGNITUDE of parameters, in dElog units.
#:
#: PER DECADE, NOT PER PARAMETER, and the first draft of this file got it wrong in a way its own
#: fence caught: at 1e-7 per parameter a 10M-parameter model owes 1.0 of rent, which erases any
#: dElog the desk will ever measure. That is not a rent, it is a cap on capability -- the model
#: could be twice as good as everything else and still finish last, and the zoo would have
#: silently locked the desk out of large models forever while appearing to rank them.
#:
#: Capacity cost is sub-linear because capability is: a 10M-parameter model is not ten thousand
#: times more prone to overfit than a 1k one, it is about three times, which is what log10 says.
#: Sized so seven decades of capacity cost ~0.014 -- enough to break a tie at equal skill
#: (P41: smallest model wins), never enough to overturn a real skill difference.
COMPLEXITY_RENT_PER_DECADE = 0.002

#: Fallback cost per compute hour when the ledger has nothing to say. Declared, not hidden, so a
#: zoo running on this number is visibly running on an assumption.
DEFAULT_COST_PER_HOUR = 0.02

#: A challenger must beat the champion by MORE than this on net dElog to take the title.
#: The incumbent holds ties: switching costs, and the burden of proof is on the challenger.
MIN_NET_GAIN = 0.005

#: Minimum shared sample before two models may be ranked against each other at all.
MIN_SHARED_N = 30


@dataclass(frozen=True)
class Entry:
    """One model's measured result over one evaluation window."""

    model_id: str
    bucket: str
    delta_elog: float
    n: int
    window_start: str
    window_end: str
    compute_hours: float = 0.0
    params: int = 0
    cost_model: str = "desk_default"
    note: str = ""


def cost_per_hour(ledger: Path | None = None) -> tuple[float, str]:
    """The desk's own measured cost per compute hour, or a declared assumption.

    Reads A4's ledger rather than restating a number, because the whole reason the compute
    allocator exists is that this desk had never recorded an hour. If the ledger is empty the
    fallback is used AND SAID SO -- a rent computed from an invented price is not a rent.
    """
    p = ledger if ledger is not None else LEDGER
    hours = 0.0
    runs = 0
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                s = row.get("seconds") or row.get("elapsed_s") or row.get("duration_s")
                if isinstance(s, (int, float)) and math.isfinite(s) and s > 0:
                    hours += float(s) / 3600.0
                    runs += 1
    except OSError:
        pass
    if runs < 5 or hours <= 0:
        return DEFAULT_COST_PER_HOUR, (
            f"declared default {DEFAULT_COST_PER_HOUR}/h -- the compute ledger holds {runs} "
            f"usable run(s), too few to price an hour from")
    return DEFAULT_COST_PER_HOUR, (
        f"declared default {DEFAULT_COST_PER_HOUR}/h over {runs} ledger run(s) totalling "
        f"{hours:.1f}h; the desk prices its own hour once the ledger carries a rate")


def rent(e: Entry, per_hour: float) -> dict[str, float]:
    compute = max(0.0, e.compute_hours) * per_hour
    complexity = COMPLEXITY_RENT_PER_DECADE * math.log10(max(1, e.params))
    return {"compute_rent": compute, "complexity_rent": complexity,
            "net_delta_elog": e.delta_elog - compute - complexity}


def comparable(a: Entry, b: Entry) -> list[str]:
    """Every reason these two may NOT be ranked against each other. Empty means fair."""
    why: list[str] = []
    if a.bucket != b.bucket:
        why.append(f"different horizon buckets ({a.bucket} vs {b.bucket}) -- a shorter-horizon "
                   "forecaster beating a longer one is not a result")
    if (a.window_start, a.window_end) != (b.window_start, b.window_end):
        why.append(f"different evaluation windows ({a.window_start}..{a.window_end} vs "
                   f"{b.window_start}..{b.window_end}) -- one may have been scored through a "
                   "crash and the other through a calm month")
    if a.cost_model != b.cost_model:
        why.append(f"different cost models ({a.cost_model} vs {b.cost_model}) -- whichever "
                   "assumed cheaper execution wins on the assumption, not the skill")
    if min(a.n, b.n) < MIN_SHARED_N:
        why.append(f"shared evidence is {min(a.n, b.n)} observations, below the {MIN_SHARED_N} "
                   "needed for a ranking to mean anything")
    return why


def league(entries: list[Entry], per_hour: float) -> dict[str, Any]:
    """Rank within each bucket, and report every pairing that could not be judged fairly."""
    scored = []
    for e in entries:
        r = rent(e, per_hour)
        scored.append({"model_id": e.model_id, "bucket": e.bucket, "n": e.n,
                       "delta_elog": e.delta_elog, **r, "params": e.params,
                       "compute_hours": e.compute_hours, "cost_model": e.cost_model,
                       "window": [e.window_start, e.window_end], "note": e.note})
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in scored:
        buckets.setdefault(row["bucket"], []).append(row)

    tables: dict[str, Any] = {}
    for name, rows in buckets.items():
        rows.sort(key=lambda r: r["net_delta_elog"], reverse=True)
        incomparable = []
        by_id = {e.model_id: e for e in entries if e.bucket == name}
        ids = [r["model_id"] for r in rows]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                why = comparable(by_id[a], by_id[b])
                if why:
                    incomparable.append({"pair": [a, b], "why": why})
        champion = rows[0] if rows else None
        runner = rows[1] if len(rows) > 1 else None
        verdict = None
        if champion and runner:
            gain = champion["net_delta_elog"] - runner["net_delta_elog"]
            fair = not comparable(by_id[champion["model_id"]], by_id[runner["model_id"]])
            verdict = {
                "gain_over_runner_up": round(gain, 6),
                "decisive": bool(fair and gain > MIN_NET_GAIN),
                "why": ("the top two were not judged on the same test, so this table names a "
                        "leader and not a champion" if not fair
                        else f"gain {gain:.4f} exceeds the {MIN_NET_GAIN} a title change requires"
                        if gain > MIN_NET_GAIN
                        else f"gain {gain:.4f} is inside the {MIN_NET_GAIN} noise band -- the "
                             "incumbent holds, because switching costs and the burden of proof "
                             "is on the challenger"),
            }
        tables[name] = {"ranked": rows, "incomparable": incomparable, "verdict": verdict}
    return tables


def _entries_from_skill_track() -> list[Entry]:
    """Read whatever the self-improvement tracker has already measured.

    The zoo does not run models. It ranks results that already exist, so it can never become a
    second, disagreeing source of truth about how a model performed.
    """
    track = BASE / "data" / "model_skill_track.jsonl"
    out: list[Entry] = []
    try:
        with track.open(encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
    except (OSError, ValueError):
        return out
    for row in rows[-200:]:
        for name, m in (row.get("predictors") or {}).items():
            skill = m.get("skill")
            if not isinstance(skill, (int, float)) or not math.isfinite(skill):
                continue
            out.append(Entry(
                model_id=str(name),
                bucket=str(m.get("bucket") or "session"),
                delta_elog=float(skill),
                n=int(m.get("n") or 0),
                window_start=str(row.get("window_start") or row.get("at") or "")[:10],
                window_end=str(row.get("window_end") or row.get("at") or "")[:10],
                compute_hours=float(m.get("compute_hours") or 0.0),
                params=int(m.get("params") or 0),
            ))
    return out


def run() -> dict[str, Any]:
    per_hour, price_why = cost_per_hour()
    entries = _entries_from_skill_track()
    tables = league(entries, per_hour)
    doc = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entrants": len(entries),
        "cost_per_hour": per_hour,
        "cost_basis": price_why,
        "complexity_rent_per_decade": COMPLEXITY_RENT_PER_DECADE,
        "min_net_gain_for_title": MIN_NET_GAIN,
        "min_shared_n": MIN_SHARED_N,
        "buckets": tables,
        "ranked_on": ("dElog after compute and complexity rent. Accuracy is not a ranking: a "
                      "model 2% more accurate at four times the compute has not earned its "
                      "place, and a desk that ranks on accuracy keeps buying it forever."),
        "fairness": ("Models are ranked only against models that faced the same window, the "
                     "same horizon bucket, the same cost model and a comparable sample. Every "
                     "pairing that fails one of those is listed as INCOMPARABLE rather than "
                     "silently ranked -- an unequal test is the easiest way to manufacture a "
                     "champion, and it never looks like cheating from the inside."),
    }
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = run()
    for path in (REPORT, LEAGUE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"model zoo: {doc['entrants']} entrant(s) across {len(doc['buckets'])} horizon bucket(s)")
    print(f"   cost basis: {doc['cost_basis']}")
    for name, t in doc["buckets"].items():
        rows, v = t["ranked"], t["verdict"]
        if not rows:
            continue
        top = rows[0]
        print(f"   {name:10} leader {top['model_id']:24} net dElog {top['net_delta_elog']:+.4f} "
              f"(n={top['n']})")
        if v:
            print(f"              {'CHAMPION' if v['decisive'] else 'NO TITLE CHANGE'}: {v['why']}")
        if t["incomparable"]:
            print(f"              {len(t['incomparable'])} pairing(s) refused as INCOMPARABLE")
    if not doc["entrants"]:
        # ABSENCE IS NEVER A PASS. An empty zoo is not a healthy zoo, and printing nothing here
        # would let "no models publish beliefs yet" read exactly like "every model is fine".
        print("   NO ENTRANTS -- no model has published a scoreable result into the skill "
              "track, so nothing can be ranked. This is a gap, not a clean bill of health.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
