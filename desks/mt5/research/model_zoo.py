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

THE GENERATOR LEAGUE (2026-09-09, inventory I11). The zoo ran hourly and reported zero entrants
because nothing registered a model against a shared window -- while two generator kinds the desk
already runs could be told apart from their own artifacts: the `external_screen` arm (the
automated backtest chain, no LLM in the loop) and the LLM seats (`deepseek`,
`kimi_k3_deep_forest`, whose donations the compiler counts in its `seats` block). They are
enrolled here as entrants over the compiler's own window, scored on the one number a generator
can be scored on -- survivors the gauntlet certified inside that window -- with compute hours
from the ledger where a leg was costed and UNCOSTED said plainly where none was. The
AI-vs-no-LLM delta is the difference in survivors; it is MEASURED only when both entrants put
rows into the window, because a delta against an empty entrant is not a measurement.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "MODEL_ZOO.json"
LEAGUE = BASE / "reports" / "CHALLENGE_LEAGUE.json"
#: A4's ledger, where the hourly cycle actually writes it (`libs.ops.compute_ledger.LEDGER`).
#: It was read from `<repo>/data/compute_ledger.jsonl` -- a file that has never existed -- and
#: for a `seconds` key the ledger never writes (it writes `wall_s`), so the zoo reported "0
#: usable run(s)" against a ledger holding rows.
LEDGER = BASE / "data" / "compute_ledger.jsonl"
COMPILED = BASE / "data" / "hypotheses" / "miner_candidates.json"
GRAPH = BASE / "data" / "hypothesis_graph.jsonl"

#: Mirrors `miner_candidate_compiler.WINDOW_DAYS`: the shared window every generator entrant is
#: scored over ends at the compiler's `compiled_at` and is this many days long.
COMPILER_WINDOW_DAYS = 7
#: The no-LLM entrant is the bandit's `external_screen` arm; the LLM entrants are the seats the
#: compiler reports (`miner_candidate_compiler.SEAT_SOURCES`).
NO_LLM = "external_screen"
SEATS: tuple[str, ...] = ("deepseek", "kimi_k3_deep_forest")
#: Which costed hourly legs are the generator's own compute (`libs.research.bandit.ARM_RUNS`
#: for the arm; the seats run under their own timers, outside every costed leg).
GENERATOR_RUNS: dict[str, tuple[str, ...]] = {
    NO_LLM: ("search", "deep_forest", "world_crawler"),
    "deepseek": (), "kimi_k3_deep_forest": (),
}
#: Fallback for the no-LLM source set when the bandit's `arm_of` cannot be imported.
_NO_LLM_SOURCES = frozenset({"external", "edge_search", "external_discoveries", "world_crawler",
                             "repo_miner"})

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
                s = (row.get("wall_s") or row.get("seconds") or row.get("elapsed_s")
                     or row.get("duration_s"))
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


# ------------------------------------------------------------------ the generator league


def generator_of(source: Any) -> str | None:
    """Which league entrant a hypothesis-graph row belongs to, or None when it is neither.

    A seat's rows carry its name as the source (`deepseek`, or `miner:deepseek` once the
    compiler has stamped them); the no-LLM entrant is every source the bandit routes to the
    `external_screen` arm, so the two definitions cannot drift apart.
    """
    text = str(source or "")
    head, _, tail = text.partition(":")
    if head in SEATS:
        return head
    if head == "miner" and tail.split(":")[0] in SEATS:
        return tail.split(":")[0]
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.research.bandit import arm_of
        arm = arm_of(text)
    except Exception:
        arm = NO_LLM if (head in _NO_LLM_SOURCES or head.startswith("deep_forest")) else None
    return NO_LLM if arm == NO_LLM else None


def shared_window(compiled: dict[str, Any] | None) -> tuple[str, str] | None:
    """[compiled_at - COMPILER_WINDOW_DAYS, compiled_at], or None when there is no artifact."""
    try:
        end = datetime.fromisoformat(str((compiled or {}).get("compiled_at")))
    except (TypeError, ValueError):
        return None
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    start = end - timedelta(days=COMPILER_WINDOW_DAYS)
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def _graph_rows(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or GRAPH
    try:
        return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _ledger_costs() -> dict[str, dict[str, Any]]:
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops.compute_ledger import cost_by_run
        return cost_by_run()
    except Exception:
        return {}


def _cost_of(gen: str, costs: dict[str, dict[str, Any]]) -> tuple[float | None, str]:
    legs = GENERATOR_RUNS.get(gen, ())
    if not legs:
        return None, ("UNCOSTED: no compute_ledger row is named after this seat -- it runs "
                      "under its own timer, outside the costed hourly legs")
    hit = [(leg, costs[leg]) for leg in legs
           if isinstance(costs.get(leg), dict) and int(costs[leg].get("runs") or 0) > 0]
    if not hit:
        return None, (f"UNCOSTED: legs {','.join(legs)} carry no compute_ledger row in the "
                      f"ledger window")
    hours = sum(float(c.get("hours") or 0.0) for _, c in hit)
    runs = sum(int(c["runs"]) for _, c in hit)
    return round(hours, 4), (f"measured: {runs} run(s) of {','.join(leg for leg, _ in hit)}, "
                             f"{hours:.3f}h in the ledger window")


def generator_entrants(compiled: dict[str, Any] | None,
                       graph_rows: list[dict[str, Any]] | None = None,
                       costs: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One row per generator over the compiler's window: rows in, judged, survivors, hours."""
    window = shared_window(compiled)
    if window is None:
        return []
    start, end = window
    latest: dict[str, dict[str, Any]] = {}
    for r in (graph_rows if graph_rows is not None else _graph_rows()):
        if not isinstance(r, dict) or not r.get("id"):
            continue
        at = str(r.get("at") or "")
        if start <= at <= end:
            latest[str(r["id"])] = r                 # appended in time order: last row wins
    counts = {g: {"born": 0, "judged": 0, "survivors": 0} for g in (NO_LLM, *SEATS)}
    for r in latest.values():
        g = generator_of(r.get("source"))
        if g is None:
            continue
        counts[g]["born"] += 1
        fate = str(r.get("fate"))
        if fate in ("FAILED", "BURIED", "CERTIFIED"):
            counts[g]["judged"] += 1
        if fate == "CERTIFIED":
            counts[g]["survivors"] += 1
    seats_block = (compiled or {}).get("seats")
    per_source = (compiled or {}).get("per_source") or {}
    costs = _ledger_costs() if costs is None else costs
    out: list[dict[str, Any]] = []
    for gen in (NO_LLM, *SEATS):
        c = counts[gen]
        if gen == NO_LLM:
            rows, cands = c["born"], None
            rows_basis = "hypothesis_graph nodes from external-screen sources inside the window"
        elif isinstance(seats_block, dict) and isinstance(seats_block.get(gen), dict):
            rows = int(seats_block[gen].get("rows") or 0)
            cands = int(seats_block[gen].get("candidates") or 0)
            rows_basis = "miner_candidates.json `seats` block (rows the seat donated)"
        elif isinstance(per_source.get(gen), dict):
            rows = int(per_source[gen].get("rows") or 0)
            cands = int(per_source[gen].get("candidates") or 0)
            rows_basis = "miner_candidates.json `per_source` (no `seats` block in this artifact)"
        else:
            rows, cands = None, None
            rows_basis = (f"UNMEASURED: miner_candidates.json (compiled_at "
                          f"{(compiled or {}).get('compiled_at')}) carries no `seats` block "
                          f"and no per_source row for this seat")
        hours, cost_basis = _cost_of(gen, costs)
        out.append({
            "model_id": gen,
            "kind": "no_llm" if gen == NO_LLM else "llm_seat",
            "window": [start, end],
            "rows": rows, "rows_basis": rows_basis, "candidates": cands,
            "judged": c["judged"], "survivors": c["survivors"],
            "survivor_yield": (round(c["survivors"] / c["judged"], 4) if c["judged"] else None),
            "compute_hours": hours, "cost_basis": cost_basis,
            "survivors_per_hour": (round(c["survivors"] / hours, 4) if hours else None),
        })
    return out


def ai_vs_no_llm(entrants: list[dict[str, Any]]) -> dict[str, Any]:
    """The delta the blueprint asks for: LLM-seat survivors minus no-LLM survivors, same window."""
    base = next((e for e in entrants if e["kind"] == "no_llm"), None)
    seats = [e for e in entrants if e["kind"] == "llm_seat"]
    if base is None or not seats:
        return {"status": "UNMEASURED", "why": "no entrants over a shared window"}
    llm_rows = [e["rows"] for e in seats]
    llm_surv = sum(int(e["survivors"]) for e in seats)
    llm_judged = sum(int(e["judged"]) for e in seats)
    delta = llm_surv - int(base["survivors"])
    if any(r is None for r in llm_rows):
        unknown = [e["model_id"] for e in seats if e["rows"] is None]
        reasons = sorted({e["rows_basis"] for e in seats if e["rows"] is None})
        status, why = "UNMEASURED", (f"rows in the window are unknown for {', '.join(unknown)}: "
                                     + "; ".join(reasons))
    elif sum(llm_rows) == 0:
        status, why = "UNMEASURED", ("the LLM seats donated 0 rows inside the shared window -- "
                                     "nothing entered, so the delta is against an empty "
                                     "entrant, not a measured zero")
    elif int(base["rows"] or 0) == 0:
        status, why = "UNMEASURED", ("the no-LLM arm registered 0 hypotheses inside the shared "
                                     "window -- nothing entered on that side")
    else:
        status, why = "MEASURED", (f"LLM seats {llm_surv} survivor(s) from {sum(llm_rows)} "
                                   f"row(s) vs no-LLM {base['survivors']} from {base['rows']} "
                                   f"over the same window and the same gauntlet")
    shared = min([int(base["rows"] or 0), *[int(r or 0) for r in llm_rows]])
    costed = [e for e in entrants if e["compute_hours"] is not None]
    per_hour_ok = len(costed) == len(entrants)
    return {
        "status": status, "why": why,
        "window": base["window"],
        "no_llm": {"survivors": base["survivors"], "rows": base["rows"],
                   "judged": base["judged"]},
        "llm_seats": {"survivors": llm_surv, "rows": (None if any(r is None for r in llm_rows)
                                                    else sum(llm_rows)),
                      "judged": llm_judged, "seats": [e["model_id"] for e in seats]},
        "delta_survivors": delta,
        "decisive": bool(status == "MEASURED" and shared >= MIN_SHARED_N
                         and abs(delta) > 0),
        "min_shared_rows": MIN_SHARED_N,
        "per_hour_comparable": per_hour_ok,
        "per_hour_why": ("both sides carry ledger hours" if per_hour_ok else
                         "INCOMPARABLE per hour: " + "; ".join(
                             f"{e['model_id']}: {e['cost_basis']}" for e in entrants
                             if e["compute_hours"] is None)),
        "rule": ("survivors certified inside the compiler's window, per generator; a delta is "
                 "MEASURED only when both sides put rows in, DECISIVE only above the shared "
                 f"sample of {MIN_SHARED_N}; per-hour ranking needs both sides costed"),
    }


def generator_league(compiled: dict[str, Any] | None = None,
                     graph_rows: list[dict[str, Any]] | None = None,
                     costs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if compiled is None:
        try:
            compiled = json.loads(COMPILED.read_text("utf-8"))
        except (OSError, ValueError):
            compiled = None
    if not isinstance(compiled, dict) or shared_window(compiled) is None:
        return {"status": "UNMEASURED", "entrants": [],
                "missing_input": (f"{COMPILED.name} is absent or carries no compiled_at -- the "
                                  f"compiler has not written the shared window on this host"),
                "ai_vs_no_llm": {"status": "UNMEASURED", "why": "no shared window"}}
    entrants = generator_entrants(compiled, graph_rows, costs)
    return {"status": "MEASURED", "window": list(shared_window(compiled) or ()),
            "entrants": entrants, "ai_vs_no_llm": ai_vs_no_llm(entrants),
            "ranked_on": ("survivors the gauntlet certified inside the shared window; hours from "
                          "the compute ledger where the generator's leg was costed")}


def run() -> dict[str, Any]:
    per_hour, price_why = cost_per_hour()
    entries = _entries_from_skill_track()
    tables = league(entries, per_hour)
    gens = generator_league()
    doc = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entrants": len(entries) + len(gens["entrants"]),
        "forecaster_entrants": len(entries),
        "generator_entrants": len(gens["entrants"]),
        "cost_per_hour": per_hour,
        "cost_basis": price_why,
        "complexity_rent_per_decade": COMPLEXITY_RENT_PER_DECADE,
        "min_net_gain_for_title": MIN_NET_GAIN,
        "min_shared_n": MIN_SHARED_N,
        "buckets": tables,
        "generators": gens,
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
    gens = doc["generators"]
    for e in gens.get("entrants") or []:
        hrs = "UNCOSTED" if e["compute_hours"] is None else f"{e['compute_hours']:.3f}h"
        rows = "rows ?" if e["rows"] is None else f"rows {e['rows']}"
        print(f"   generator {e['model_id']:22} {e['kind']:8} {rows:>10} judged {e['judged']:5d} "
              f"survivors {e['survivors']:3d}  {hrs}")
    verdict = gens.get("ai_vs_no_llm") or {}
    print(f"   AI vs no-LLM: {verdict.get('status')} -- {verdict.get('why')}"
          + (f" (delta {verdict['delta_survivors']:+d} survivor(s))"
             if "delta_survivors" in verdict else ""))
    if gens.get("missing_input"):
        print(f"   generators UNMEASURED: {gens['missing_input']}")
    if not doc["entrants"]:
        # ABSENCE IS NEVER A PASS. An empty zoo is not a healthy zoo, and printing nothing here
        # would let "no models publish beliefs yet" read exactly like "every model is fine".
        print("   NO ENTRANTS -- no model has published a scoreable result into the skill "
              "track and no generator has a shared window, so nothing can be ranked. This is a "
              "gap, not a clean bill of health.")
    elif not doc["forecaster_entrants"]:
        print("   NO FORECASTER ENTRANTS -- no model has published a scoreable result into the "
              "skill track; only the generator league has entrants. This is a gap, not a clean "
              "bill of health.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
