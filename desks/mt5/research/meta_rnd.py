"""META-R&D -- the research PROCESS as an experimental subject, judged on recorded outcomes.

THE GAP THE LEDGER NAMED (Tier-1 B25): *"seats are A/B tested; gauntlet thresholds, mutation
operators and test ordering are not themselves experimental subjects."* `brain_ab` randomises
which SEAT proposes a hypothesis. Everything downstream of the proposal -- the order objections
are tried in, the mix of mutation operators that breeds the next candidate, the bars the judge
applies -- is a set of constants that no experiment has ever been run on. A desk that A/B tests
its scientists and never its method is optimising the smaller half of its own machine.

THREE SUBJECTS, AND THEY ARE DELIBERATELY NOT EQUAL IN WHAT THEY MAY CHANGE.

  1. TEST ORDERING          APPLIED. Four ordering policies are replayed against the recorded
                            falsifier battery: the catalogue's declared prior, the MEASURED kill
                            rate per class from the evolved destroyer pool, the pre-mortem's own
                            class first, and cheapest-first. Each is scored by the SECONDS IT
                            WOULD HAVE SPENT to reach the first kill on rows the desk already
                            ran, using each test's own recorded seconds. The winner's kill rates
                            are what `falsifier_run` asks for. Ordering is not a threshold: every
                            objection still runs and nothing passes or fails differently, so this
                            is free speed and L1.60 is untouched.

  2. MUTATION OPERATORS     MEASURED, NOT APPLIED. Three operator mixes -- the weights
                            `mutation_yield` publishes, a uniform mix, and greedy-on-top-k --
                            are scored on the recorded certify-per-operator posterior as
                            expected survivors per 100 trials. Not applied because
                            `mutation_yield` OWNS `data/mutation_operator_weights.json` and a
                            second writer would fight it every hour; the comparison is published
                            so that owner (or a person) can act on evidence rather than habit.

  3. GAUNTLET THRESHOLDS    MEASURED, AND REFUSED AS AN ACTION, in both directions and for two
                            different reasons. LOWERING a bar to let more cells through would
                            manufacture the evidence the bar exists to demand -- that is the one
                            thing a desk may never do to its own judge. RAISING one would size
                            the book smaller, which the principal's standing order forbids. And
                            the four files that hold those bars are sealed. So the counterfactual
                            counts are published and nothing is fed anywhere.

VERDICTS COME FROM THE ARENA'S OWN JUDGE (`libs.research.arena.judge`), so a process arm is
recorded in exactly the vocabulary AP5 counts, and an arm below the floor reads UNMEASURED rather
than losing.

    python desks/mt5/research/meta_rnd.py --once --budget-s 180
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import arena  # noqa: E402
from libs.validation import falsifiers  # noqa: E402

FALSIFIER_REPORT = DESK / "reports" / "FALSIFIER_VERDICTS.json"
FALSIFIERS_ALT = DESK / "reports" / "FALSIFIERS.json"
MUTATION_YIELD = DESK / "reports" / "MUTATION_YIELD.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "META_RND.json"

POLICIES = ("catalogue_prior", "measured_kill_rates", "premortem_first", "cheapest_first")
MIN_ROWS = 5              # replayed certificates below this: the tournament is UNMEASURED


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _battery_rows() -> tuple[list[dict[str, Any]], str]:
    for path in (FALSIFIER_REPORT, FALSIFIERS_ALT):
        doc = _read(path)
        per = doc.get("per_certificate")
        if isinstance(per, dict) and per:
            rows = [dict(v, cert_id=k) for k, v in per.items()
                    if isinstance(v, dict) and v.get("results")]
            if rows:
                return rows, str(path)
    return [], "no falsifier report with per-certificate results on this host"


def _order_for(policy: str, row: dict[str, Any], measured: dict[str, float]) -> list[str]:
    pre = {"failure_class": row.get("premortem_class")} if row.get("premortem_class") else None
    if policy == "catalogue_prior":
        return falsifiers.schedule(None)
    if policy == "measured_kill_rates":
        return falsifiers.schedule(None, kill_rates=measured or None)
    if policy == "premortem_first":
        return falsifiers.schedule(pre)
    return sorted(falsifiers.CATALOGUE, key=lambda n: falsifiers.CATALOGUE[n][0])


def replay_orderings(rows: list[dict[str, Any]],
                     measured: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Seconds each policy WOULD have spent to reach the first kill, on rows already run.

    Nothing is re-executed: every test's own recorded seconds and verdict are replayed in a
    different order, which is exactly what an ordering policy changes and all it changes."""
    out: dict[str, dict[str, Any]] = {}
    for policy in POLICIES:
        secs: list[float] = []
        kills = 0
        for row in rows:
            results = row.get("results") or {}
            order = [n for n in _order_for(policy, row, measured) if n in results]
            spent = 0.0
            killed = False
            for name in order:
                res = results.get(name) or {}
                spent += float(res.get("seconds") or 0.0)
                if str(res.get("verdict")) == "FAIL":
                    killed = True
                    break
            secs.append(spent)
            kills += 1 if killed else 0
        n = len(secs)
        out[policy] = {
            "n_rows": n, "n_killed": kills,
            "mean_seconds_to_verdict": round(sum(secs) / n, 4) if n else None,
            "total_seconds": round(sum(secs), 3),
            "verdict": "MEASURED" if n >= MIN_ROWS else "UNMEASURED",
            "why": (None if n >= MIN_ROWS else
                    f"{n} replayed certificate(s), under the floor of {MIN_ROWS}"),
        }
    return out


def ordering_kill_rates() -> dict[str, float]:
    """THE CONSUMER'S DOOR. `falsifier_run` asks for the winning policy's kill rates and passes
    them to `falsifiers.schedule`. An empty dict leaves the catalogue's declared prior in place,
    which is exactly the behaviour before this organ existed."""
    doc = _read(OUT)
    _block = doc.get("ordering")
    block: dict[str, Any] = dict(_block) if isinstance(_block, dict) else {}
    if str(block.get("applied_policy")) != "measured_kill_rates":
        return {}
    rates = block.get("measured_kill_rates")
    out: dict[str, float] = {}
    for k, v in (rates or {}).items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def operator_mixes() -> dict[str, Any]:
    """Three mixes scored on the certify-per-operator posterior mutation_yield already fits."""
    doc = _read(MUTATION_YIELD)
    _per = doc.get("per_operator")
    per: dict[str, Any] = dict(_per) if isinstance(_per, dict) else {}
    ops: dict[str, dict[str, float]] = {}
    for name, row in per.items():
        if not isinstance(row, dict):
            continue
        try:
            cert = float(row.get("certified") or 0.0)
            trials = float(row.get("n") or row.get("trials") or 0.0)
        except (TypeError, ValueError):
            continue
        if trials <= 0:
            continue
        ops[str(name)] = {"p": (1.0 + cert) / (2.0 + trials), "n": trials}
    if not ops:
        return {"status": "UNMEASURED",
                "why": ("no reports/MUTATION_YIELD.json per-operator rows on this host: the "
                        "operator posterior this compares mixes on does not exist yet"),
                "mixes": {}}
    names = sorted(ops)
    uniform = {n: 1.0 / len(names) for n in names}
    published = {n: float(ops[n]["p"]) for n in names}
    tot = sum(published.values()) or 1.0
    published = {n: v / tot for n, v in published.items()}
    top = sorted(names, key=lambda n: -ops[n]["p"])[:max(1, len(names) // 3)]
    greedy = {n: (1.0 / len(top) if n in top else 0.0) for n in names}
    mixes = {"uniform": uniform, "yield_weighted": published, "greedy_top_third": greedy}
    scored: dict[str, dict[str, Any]] = {
        name: {"expected_survivors_per_100_trials":
               round(100.0 * sum(w * ops[n]["p"] for n, w in mix.items()), 4),
               "weights": {n: round(w, 4) for n, w in mix.items() if w > 0}}
        for name, mix in mixes.items()}
    best = max(scored, key=lambda k: float(scored[k]["expected_survivors_per_100_trials"]))
    return {"status": "MEASURED", "n_operators": len(names), "mixes": scored, "best": best,
            "applied": False,
            "why_not_applied": (
                "`mutation_yield` owns data/mutation_operator_weights.json and writes it every "
                "hour; a second writer would fight it. The comparison is published for that "
                "owner and for a person, and nothing here writes the weights file.")}


def threshold_variants() -> dict[str, Any]:
    """How many judged cells each counterfactual bar WOULD have passed -- published, never fed."""
    doc = _read(SURVIVORS)
    _sv = doc.get("survivors")
    survivors: dict[str, Any] = dict(_sv) if isinstance(_sv, dict) else {}
    counts: dict[str, int] = {}
    n_gates_seen = 0
    for rec in survivors.values():
        gates = rec.get("gates") if isinstance(rec, dict) else None
        if not isinstance(gates, dict):
            continue
        n_gates_seen += 1
        passed = sum(1 for v in gates.values()
                     if isinstance(v, dict) and bool(v.get("passed")))
        for need in (8, 9, 10):
            key = f"pass_at_least_{need}_of_10"
            counts[key] = counts.get(key, 0) + (1 if passed >= need else 0)
    return {
        "status": "MEASURED" if n_gates_seen else "UNMEASURED",
        "n_certificates_with_gate_rows": n_gates_seen,
        "counterfactual_counts": counts,
        "applied": False,
        "why_not_applied": (
            "REFUSED IN BOTH DIRECTIONS, on two different grounds. Lowering a bar would "
            "manufacture the evidence the bar exists to demand; raising one would size the book "
            "smaller, which the principal's standing order forbids. The gauntlet, the promoter, "
            "the allocator proof and the state-admission judge are sealed and are not imported "
            "here -- this counts what the record says and stops."),
    }


def build(budget_s: float = 180.0) -> dict[str, Any]:
    t0 = time.monotonic()
    rows, source = _battery_rows()
    measured: dict[str, float] = {}
    try:
        from research.destroyer_pool import kill_rates
        measured = kill_rates()
    except Exception:
        measured = {}
    orderings = replay_orderings(rows, measured) if rows else {}
    eligible = {k: v for k, v in orderings.items() if v["verdict"] == "MEASURED"
                and v["mean_seconds_to_verdict"] is not None}
    winner = min(eligible, key=lambda k: float(eligible[k]["mean_seconds_to_verdict"])) \
        if eligible else None
    # The arena's own judge, in its own vocabulary: an arm is "born" per replayed certificate and
    # "certified" when its order reached a kill, so a faster policy that finds nothing does not
    # win by being fast at nothing.
    arms = {k: {"born": int(v["n_rows"]), "certified": int(v["n_killed"]),
                "alpha": 1.0 + int(v["n_killed"]),
                "beta": 1.0 + max(int(v["n_rows"]) - int(v["n_killed"]), 0),
                "group": "test_ordering",
                "cost_basis": f"mean {v['mean_seconds_to_verdict']}s to first verdict"}
            for k, v in orderings.items()}
    verdicts = arena.judge(arms) if arms else {"arms": {}, "leader": None, "recorded": 0,
                                               "trails": []}
    applied = winner if (winner and measured) else (winner or None)
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if rows else "UNMEASURED",
        "source": source, "n_replayed": len(rows),
        "ordering": {
            "policies": orderings, "winner": winner,
            "applied_policy": applied,
            "measured_kill_rates": measured,
            "applied": bool(applied == "measured_kill_rates" and measured),
            "rule": ("scored by the seconds each policy WOULD have spent to reach the first kill "
                     "on rows the desk already ran; nothing is re-executed and every objection "
                     "still runs, so no cell passes or fails differently for the order"),
        },
        "arena": verdicts,
        "operators": operator_mixes(),
        "thresholds": threshold_variants(),
        "consumers": [
            "desks/mt5/research/falsifier_run.py falsify() -> ordering_kill_rates(): the winning "
            "policy's kill rates are what `falsifiers.schedule` is given",
            "reports/META_RND.json -> the operator-mix and threshold-variant comparisons, "
            "published for their owners and explicitly not fed anywhere",
        ],
        "boundary": (
            "ONE SUBJECT IS APPLIED AND TWO ARE NOT, on purpose. Ordering costs nothing and "
            "changes no verdict. Operator weights belong to `mutation_yield`. Thresholds are "
            "sealed and refused in both directions -- lower manufactures evidence, higher sizes "
            "the book smaller."),
        "seconds": round(time.monotonic() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=180.0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"meta rnd: could not write {OUT}: {exc}")
        return 1
    o = doc["ordering"]
    print(f"meta rnd: {doc['n_replayed']} certificate batter(ies) replayed under "
          f"{len(POLICIES)} ordering policies; winner={o['winner']} "
          f"applied={o['applied_policy']}")
    for name, row in (o["policies"] or {}).items():
        print(f"   {name:<22} {row['verdict']:<10} n={row['n_rows']:<4} "
              f"kills={row['n_killed']:<4} mean_s={row['mean_seconds_to_verdict']}")
    ops = doc["operators"]
    print(f"   operators: {ops.get('status')} best={ops.get('best')} "
          f"(applied={ops.get('applied')})")
    th = doc["thresholds"]
    print(f"   thresholds: {th.get('status')} {th.get('counterfactual_counts')} "
          f"(applied={th.get('applied')})")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
