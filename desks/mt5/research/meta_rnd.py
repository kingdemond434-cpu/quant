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
from itertools import pairwise
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
FRONTIER = DESK / "reports" / "RESEARCH_FRONTIER.json"

POLICIES = ("catalogue_prior", "measured_kill_rates", "premortem_first", "cheapest_first")
MIN_ROWS = 5              # replayed certificates below this: the tournament is UNMEASURED

# ----------------------------------------------------------------------------- THE WALL (F25)
# RESTORED 2026-09-29 from 16dc47e4 (F25, 2026-09-12). The rewrite of this module for B25
# (291270e2, 2026-09-23) dropped both tables, and `research_os_archive` -- which imports them to
# build its constitution -- fell back to an EMPTY forbidden list and an EMPTY movable set without
# a word: `forbidden_knobs()` returned {} and `meta_knob_specs()` returned {}, so the wall around
# the self-improving research system silently lost one of its two refusal lists. The tables are
# restored verbatim; the F25 single-champion tournament they came with is superseded by the
# archive (research_os_archive.py) and is not.

#: The knobs a meta-version MAY move. Every one is a property of how the desk SEARCHES -- never of
#: what it will risk, and never of the bar it is judged against.
META_KNOBS: dict[str, dict[str, Any]] = {
    "research_tree.BEAM": {
        "module": "research.research_tree", "attr": "BEAM", "lo": 4, "hi": 48,
        "changes": "how many tree nodes are expanded per pass -- the rate at which reach is "
                   "bought"},
    "research_tree.INHERIT": {
        "module": "research.research_tree", "attr": "INHERIT", "lo": 0.0, "hi": 0.9,
        "changes": "how strongly a child node inherits its parent's posterior; 0 flattens the "
                   "tree into a list, 1 makes a cross-market analogue as likely as its parent"},
    "joint_evolution.DRAWS": {
        "module": "research.joint_evolution", "attr": "DRAWS", "lo": 40, "hi": 400,
        "changes": "genomes sampled per surface -- the resolution of the interaction measurement"},
    "representation_discovery.BEAM": {
        "module": "research.representation_discovery", "attr": "BEAM", "lo": 2, "hi": 16,
        "changes": "composite search width, and therefore the trial count it charges the desk"},
    "adversary_evolution.MUT": {
        "module": "research.adversary_evolution", "attr": "MUT", "lo": 0.05, "hi": 0.6,
        "changes": "how far an attack's child moves from its parent -- the adversary's own "
                   "exploration rate"},
    "negative_knowledge.EXPLORE_FLOOR": {
        "module": "research.negative_knowledge", "attr": "EXPLORE_FLOOR", "lo": 0.10, "hi": 0.50,
        "changes": "the share of admissions reserved for the cells the model scores worst"},
}

#: Knobs a meta-version may NEVER move, and why. Enumerated rather than left to judgement: a
#: system graded on its own output will find these if they are merely discouraged.
FORBIDDEN_KNOBS: dict[str, str] = {
    "any gate threshold": (
        "the gates are what a meta-version is JUDGED by. A system permitted to move them would "
        "improve its score by lowering its bar, which is the shortest path to a better number "
        "and the least useful one."),
    "heat floor, heat ceiling, per-sleeve caps": (
        "the principal's standing order: risk is never reduced by fiat, and its mirror binds "
        "equally -- research must not raise its scores by moving what the desk will risk."),
    "minimum lot, daily loss, sizing parameters": (
        "money-path constants. A research tournament has no business near them, and F26's "
        "invariant says exactly one authority sizes."),
    "the trial charge": (
        "F19 measured what happens when it moves: the registry now holds two regimes and 15 of "
        "61 certificates cleared a standard the desk no longer applies. A meta-version moving it "
        "would make every comparison in this report span two worlds."),
}

QUANTBENCH = DESK / "reports" / "QUANTBENCH.json"
ADVERSARY = DESK / "reports" / "ADVERSARY_EVOLUTION.json"


def sealed_benchmark() -> dict[str, Any]:
    """THE SEALED BENCHMARK SUITE a challenger research policy must not regress, read -- never
    re-run -- from the two organs that own it (F25's arenas, restored as a verdict):

        sealed_traps   `quantbench` -- the defects this desk already paid for, replayed whole
        synthetic      `adversary_evolution` -- attacks with declared ground truth; a BREACH is
                       a gate that let a planted fake through

    `passed` is True only when BOTH were read and neither regressed. An absent or unreadable
    arena is UNMEASURED and FAILS the suite: absence never passes (L1.28a), and a self-improving
    system that could be promoted while its judge was dark would be promoted by the dark.
    False rejections are reported and never scored -- a policy can always cut them by making the
    gates permissive, which is the one lever this suite exists to deny it."""
    qb = _read(QUANTBENCH)
    adv = _read(ADVERSARY)
    traps: dict[str, Any]
    if qb.get("status") in ("OK", "REGRESSED"):
        traps = {"status": qb["status"], "n_cases": qb.get("n_cases"),
                 "regressed": qb.get("regressed") or [], "score": qb.get("score"),
                 "ok": qb["status"] == "OK"}
    else:
        traps = {"status": "UNMEASURED", "ok": False,
                 "why": f"no usable {QUANTBENCH.name} (status {qb.get('status')!r})"}
    synth: dict[str, Any]
    if isinstance(adv.get("n_breach"), int) and adv.get("status") != "BLOCKED":
        ctl = adv.get("controls") if isinstance(adv.get("controls"), dict) else {}
        synth = {"status": "OK", "n_breach": adv["n_breach"],
                 "n_false_rejection": ctl.get("n_false_rejection"),
                 "ok": int(adv["n_breach"]) == 0}
    else:
        synth = {"status": "UNMEASURED", "ok": False,
                 "why": f"no usable {ADVERSARY.name}: the arena that stops a policy improving "
                        "its score by weakening a gate is dark"}
    return {"passed": bool(traps["ok"] and synth["ok"]), "sealed_traps": traps,
            "synthetic": synth,
            "rule": ("both arenas read and neither regressed; UNMEASURED fails; breaches score, "
                     "false rejections are reported and never scored")}


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


def guarded_winner(rows: list[dict[str, Any]], measured: dict[str, float],
                   state_path: Path | None = None) -> dict[str, Any]:
    """The ordering winner chosen through `libs.research.reusable_holdout`. Rows split by their
    certificate id (a row never changes side); each policy's mean seconds on the training half
    is answered through Thresholdout against the holdout half.

    When the study's budget is gone the pick FREEZES at the last guarded winner and the study
    ROTATES: the certificates it was asked about are retired and the next epoch opens, with a
    fresh budget, on certificates no earlier epoch saw -- so the freeze lasts only until enough
    fresh rows arrive, and never reverts to selecting on the exhausted rows."""
    from libs.research import reusable_holdout as rh
    base = "meta_rnd.test_ordering"
    study, retired = rh.epoch(base, state_path)
    fresh = [r for r in rows if str(r.get("cert_id") or "") not in retired]
    last = str(_read(OUT).get("ordering", {}).get("winner") or "") or None
    halves: dict[str, list[dict[str, Any]]] = {"train": [], "holdout": []}
    for r in fresh:
        halves[rh.split(str(r.get("cert_id") or ""))].append(r)
    if min(len(halves["train"]), len(halves["holdout"])) < MIN_ROWS:
        return {"status": "UNMEASURED", "winner": last if retired else None, "study": study,
                "frozen": bool(retired), "rows_retired": len(retired),
                "why": f"each half needs {MIN_ROWS} rows no earlier epoch saw "
                       f"(train={len(halves['train'])}, holdout={len(halves['holdout'])})"}
    tr = replay_orderings(halves["train"], measured)
    ho = replay_orderings(halves["holdout"], measured)
    q = {k: (float(tr[k]["mean_seconds_to_verdict"]), float(ho[k]["mean_seconds_to_verdict"]))
         for k in POLICIES if tr[k]["mean_seconds_to_verdict"] is not None
         and ho[k]["mean_seconds_to_verdict"] is not None}
    if not q:
        return {"status": "UNMEASURED", "winner": None, "why": "no policy measured on both halves"}
    scale = sum(v[0] for v in q.values()) / len(q)
    out = rh.thresholdout(study, q, scale=scale, state_path=state_path)
    answered = {k: v for k, v in out["answers"].items() if v is not None}
    winner = min(answered, key=lambda k: float(answered[k])) if answered else last
    rotated = None
    if out["status"] == "EXHAUSTED" and out.get("state_error") is None:
        rotated = rh.rotate(base, {str(r.get("cert_id") or "") for r in fresh}, state_path)
    return {**out, "winner": winner, "n_train": len(halves["train"]),
            "n_holdout": len(halves["holdout"]), "rows_retired": len(retired),
            "frozen": not answered, "rotated_to": rotated,
            "why": (None if answered else "holdout budget exhausted: the pick is frozen at the "
                    "last guarded winner and the study rotated to certificates it never saw")}


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
    raw_winner = min(eligible, key=lambda k: float(eligible[k]["mean_seconds_to_verdict"])) \
        if eligible else None
    try:
        guard = guarded_winner(rows, measured)
    except (OSError, ValueError, TypeError) as exc:
        guard = {"status": "UNMEASURED", "winner": None, "why": f"{type(exc).__name__}: {exc}"}
    # The raw winner is reported, never applied: it was selected on rows the holdout no longer
    # protects. No guarded winner leaves the catalogue's declared prior in place.
    winner = guard.get("winner")
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
            "policies": orderings, "winner": winner, "raw_winner": raw_winner,
            # THE SAME ROWS ARE ASKED THE SAME QUESTION EVERY HOUR: the pick goes through a
            # reusable holdout so it stays an estimate, not a fit to these rows' noise.
            "reusable_holdout": guard,
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
        # THE WALL AND THE SEALED SUITE, published where the archive's promotion rule reads them.
        "wall": {"movable_meta_knobs": sorted(META_KNOBS),
                 "forbidden_knobs": FORBIDDEN_KNOBS},
        "sealed_benchmark": sealed_benchmark(),
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


# ===================================================================== CADENCE AND BOUND
#: The proxy's units. One R is RISK_PER_R of equity; each unit of weight turned over costs
#: TURNOVER_COST_R in R. Both are declared assumptions, published with every result.
RISK_PER_R = 0.005
TURNOVER_COST_R = 0.02
CADENCES = (1, 5, 20)
MIN_DAYS = 60


def _matrix(daily: dict[str, dict[str, float]]) -> tuple[list[str], list[str], Any]:
    import numpy as np
    sleeves = sorted(k for k, v in daily.items() if isinstance(v, dict) and len(v) >= 10)
    days = sorted({d for k in sleeves for d in daily[k]})
    m = np.array([[float(daily[k].get(d, 0.0)) for k in sleeves] for d in days]) \
        if sleeves and days else np.zeros((0, 0))
    return sleeves, days, m


def _proxy_weights(m: Any, t: int, lookback: int = 20) -> Any:
    """The PROXY allocator: equal weight over sleeves whose trailing mean R is positive."""
    import numpy as np
    past = m[max(0, t - lookback):t]
    if len(past) == 0:
        return np.zeros(m.shape[1])
    on = past.mean(axis=0) > 0
    return on / on.sum() if on.any() else np.zeros(m.shape[1])


#: Mean block length of the stationary bootstrap, in days.
BLOCK_MEAN = 10
#: The constant-fraction bound's box per sleeve (the old grid's range).
F_MAX = 2.0


def _stationary_index(rng: Any, n: int, mean_block: int) -> Any:
    """Politis-Romano stationary bootstrap: blocks start uniformly, lengths are geometric with
    mean `mean_block`, indices wrap circularly. Returns n day indices."""
    import numpy as np
    out: list[int] = []
    while len(out) < n:
        start = int(rng.integers(0, n))
        length = int(rng.geometric(1.0 / mean_block))
        out.extend(((start + np.arange(length)) % n).tolist())
    return np.array(out[:n])


def _best_constant_fraction(ret: Any) -> tuple[Any, float, str]:
    """argmax over f in [0, F_MAX]^k of mean log(1 + ret @ f): concave, so a local optimum from a
    feasible start is global. Starts from the best point of a coarse grid; the solver's answer is
    kept only if it is feasible and no worse than that start."""
    import numpy as np
    k = ret.shape[1]

    def growth(f: Any) -> float:
        port = ret @ f
        return float(np.log1p(port).mean()) if np.all(port > -1.0) else -np.inf
    start = np.zeros(k)
    for _ in range(2):
        for j in range(k):
            trial = start.copy()
            vals = []
            for g in np.linspace(0.0, F_MAX, 11):
                trial[j] = g
                vals.append(growth(trial))
            start[j] = np.linspace(0.0, F_MAX, 11)[int(np.argmax(vals))]
    best, val, solver = start, growth(start), "grid"
    try:
        from scipy.optimize import minimize

        def neg(f: Any) -> float:
            port = ret @ f
            if np.any(port <= -1.0):
                return 1e6
            return -float(np.log1p(port).mean())

        def grad(f: Any) -> Any:
            port = np.maximum(ret @ f, -1.0 + 1e-12)
            return -(ret / (1.0 + port)[:, None]).mean(axis=0)
        res = minimize(neg, start, jac=grad, method="L-BFGS-B", bounds=[(0.0, F_MAX)] * k)
        cand = np.clip(res.x, 0.0, F_MAX)
        if growth(cand) >= val:
            best, val, solver = cand, growth(cand), "L-BFGS-B (concave, global)"
    except Exception:
        pass
    return best, float(val), solver


def cadence_and_bound(daily: dict[str, dict[str, float]], seed: int = 0,
                      boots: int = 300) -> dict[str, Any]:
    """TWO RESEARCH-PROCESS QUESTIONS ON THE RECORDED BOOK.

    CADENCE: does re-weighting faster raise net log growth, or only turnover? The proxy is
    re-weighted every 1, 5 and 20 days on the same days, net of a turnover charge; a stationary
    bootstrap over days (Politis-Romano: geometric block lengths, mean BLOCK_MEAN days, circular)
    gives each cadence's interval and P(faster beats slower).

    BOUND: the hindsight-optimal CONSTANT fraction per sleeve, long-only in [0, F_MAX], solved to
    optimality (the mean log growth is concave in the fractions; L-BFGS-B from the best grid
    point) on the whole window. It is an upper bound for every constant-fraction book on that
    window -- not for the proxy, which re-weights through time and may beat it, so the gap is
    signed: positive is growth a constant book left on the table, negative is what the proxy's
    timing earned over the best constant book. A bound, never a target."""
    import numpy as np
    sleeves, days, m = _matrix(daily)
    if len(days) < MIN_DAYS or not sleeves:
        return {"status": "UNMEASURED",
                "why": f"{len(days)} recorded day(s) across {len(sleeves)} sleeve(s); need "
                       f"{MIN_DAYS}"}
    ret = m * RISK_PER_R

    def run(c: int, idx: Any) -> tuple[Any, float]:
        w = np.zeros(m.shape[1])
        g, turn = [], 0.0
        for j, t in enumerate(idx):
            if j % c == 0:
                nw = _proxy_weights(m, int(t))
                turn += float(np.abs(nw - w).sum())
                cost = float(np.abs(nw - w).sum()) * TURNOVER_COST_R * RISK_PER_R
                w = nw
            else:
                cost = 0.0
            g.append(np.log1p(float(ret[int(t)] @ w) - cost))
        return np.array(g), turn

    base = np.arange(len(days))
    out: dict[str, Any] = {}
    for c in CADENCES:
        g, turn = run(c, base)
        out[str(c)] = {"mean_log_growth": round(float(g.mean()), 7),
                       "turnover": round(turn, 3)}
    rng = np.random.default_rng(seed)
    block = BLOCK_MEAN
    wins = {f"{a}_vs_{b}": 0 for a, b in pairwise(CADENCES)}
    draws: dict[str, list[float]] = {str(c): [] for c in CADENCES}
    n = len(days)
    for _ in range(boots):
        idx = _stationary_index(rng, n, block)
        means = {c: float(run(c, idx)[0].mean()) for c in CADENCES}
        for c in CADENCES:
            draws[str(c)].append(means[c])
        for a, b in pairwise(CADENCES):
            wins[f"{a}_vs_{b}"] += int(means[a] > means[b])
    for c in CADENCES:
        lo, hi = np.quantile(draws[str(c)], [0.05, 0.95])
        out[str(c)]["ci90"] = [round(float(lo), 7), round(float(hi), 7)]
    best_f, bound, solver = _best_constant_fraction(ret)
    realised = out[str(CADENCES[0])]["mean_log_growth"]
    return {"status": "MEASURED", "days": n, "sleeves": len(sleeves),
            "subject": "equal weight over trailing-positive sleeves (a PROXY, not pf_allocator)",
            "assumptions": {"risk_per_r": RISK_PER_R, "turnover_cost_r": TURNOVER_COST_R,
                            "bootstrap": f"stationary (geometric blocks, mean {block} days, "
                                         f"circular) x {boots}"},
            "cadence": out,
            "p_faster_beats_slower": {k: round(v / boots, 3) for k, v in wins.items()},
            "bound": {"hindsight_constant_fraction_log_growth": round(bound, 7),
                      "fractions": [round(float(x), 4) for x in best_f],
                      "box": [0.0, F_MAX], "solver": solver,
                      "proxy_daily_log_growth": realised,
                      "gap": round(bound - float(realised), 7),
                      "why": "in-sample optimum over constant fractions in the box: an upper "
                             "bound for every constant-fraction book on this window, never a "
                             "target; the gap is signed because the proxy re-weights"}}


# ===================================================================== THE FRONTIER REPORT
def _rep(name: str) -> Path:
    return DESK / "reports" / name


#: One row per limitation of the RESEARCH PROCESS (principal, 2026-10-06: "research the
#: researcher"). Each names the organ that owns it, the artifact that measures it, and the
#: experiment that would move it. A row's numbers are READ from its artifact on every pass; an
#: absent artifact is UNMEASURED, and a challenger nobody has built is NOT_BUILT -- never a pass.
LIMITATIONS: tuple[dict[str, Any], ...] = (
    {"id": "dataset_discovery_method", "owner": "research/source_frontier.py, "
     "research/world_dataset_hunter.py (Breadth)",
     "limit": "whether catalogue enumeration finds more usable datasets per compute-hour than "
              "search and crawling has never been compared at matched compute",
     "artifacts": ("SOURCE_FRONTIER.json", "DATASET_HUNT.json"), "challenger": None,
     "resources": "both arms' acquisition outcomes per compute-hour (source_frontier's ROI "
                  "ledger); no new spend",
     "next": "paired weekly run: equal seconds to DBnomics/BIS catalogue enumeration and to the "
             "crawler on the same country set; score usable datasets admitted per hour"},
    {"id": "representation_novelty", "owner": "research/representation_forge.py, "
     "research/orthogonality_yield.py",
     "limit": "a new representation is credited by drop-one explained variance, with no "
              "interval and no comparison between representation methods",
     "artifacts": ("REPRESENTATION_FORGE.json", "ORTHOGONALITY_YIELD.json"),
     "challenger": "representation_methods",
     "resources": "the forge's own matrices; bootstrap over days",
     "next": "bootstrap CI on each family's incremental R^2 over the existing factor set, and "
             "a head-to-head of representation methods at equal feature count"},
    {"id": "joint_feature_model_search", "owner": "research/factor_model_coevolution.py",
     "limit": "joint (F, M) search was only ever compared with the base rate",
     "artifacts": ("COEVOLUTION.json",), "challenger": "method_challenger",
     "resources": "90 s per pass inside the coevolution leg",
     "next": "keep the paired runs accruing until the arena separates the arms; then extend "
             "the matched baseline to model-first"},
    {"id": "specialist_vs_general_agent", "owner": "libs/ops/llm_seat.py, "
     "libs/research_os/brain_ab.py",
     "limit": "cheaper specialist models are refused by policy (llm_seat), so whether one "
              "completes a task as reliably as a general model is unmeasurable",
     "artifacts": ("../data/brain_ab.json",), "challenger": None, "blocked_by": "policy",
     "resources": "a sanctioned A/B seat for one bounded task (extraction), cost logged",
     "next": "principal-gated: one extraction task routed 50/50 to a specialist and the "
             "incumbent, scored on the deepening worker's acceptance rate per dollar"},
    {"id": "allocator_speed_vs_turnover", "owner": "research/rebalance_trigger.py",
     "limit": "a faster rebalance cadence has never been replayed against net results; the "
              "trigger decides per event but no cadence is compared",
     "artifacts": ("REBALANCE_TRIGGER.json", "ALLOCATOR_PROOF.json"),
     "challenger": "cadence",
     "resources": "recorded forward daily R and the live ledger's costs",
     "next": "replay hourly vs daily vs weekly rebalancing of the recorded book: net E[log W] "
             "and turnover per cadence, with a block-bootstrap interval"},
    {"id": "adaptive_holdout_reuse", "owner": "research/meta_rnd.py, libs/research/lockbox.py",
     "limit": "hourly selections reuse the same recorded rows; the lockbox protects one final "
              "verdict, not a selection rule that runs forever",
     "artifacts": ("META_RND.json",), "challenger": "reusable_holdout",
     "resources": "fresh certificate rows; the study budget",
     "next": "extend the reusable holdout to research_os_archive's champion seating"},
    {"id": "research_trajectories", "owner": "research/research_os_archive.py, "
     "research/semantic_memory.py",
     "limit": "outcomes are kept; the steps, data and decisions that produced them are not "
              "replayable as procedures",
     "artifacts": ("RESEARCH_OS_ARCHIVE.json",), "challenger": None,
     "resources": "the event log and the hypothesis graph already hold the steps",
     "next": "record each certified and each buried candidate's lineage as a replayable "
             "procedure and measure reuse yield against cold starts"},
    {"id": "component_ablation", "owner": "libs/ops/module_rent.py, research/module_rent.py",
     "limit": "removal is estimated, never performed: no component is switched off on a shadow "
              "run to measure the loss",
     "artifacts": ("MODULE_RENT.json",), "challenger": None,
     "resources": "one shadow pass per component on the build box",
     "next": "shadow ablation of the lowest-rent research leg for a week; compare survivors "
             "per compute-hour with and without it"},
    {"id": "optimality_gap", "owner": "libs/portfolio/allocator_proof.py",
     "limit": "no allocator decision is compared with a bound (hindsight oracle or the solver's "
              "dual), so the gap to optimal is unknown",
     "artifacts": ("ALLOCATOR_PROOF.json",), "challenger": "bound",
     "resources": "recorded daily R; a hindsight-Kelly solve per window",
     "next": "publish realised log growth against the hindsight-optimal fixed-fraction bound "
             "per window: the gap and its interval"},
)


def _artifact(name: str, now_ts: float) -> dict[str, Any]:
    p = (DESK / "reports" / name).resolve()
    doc = _read(p)
    if not doc:
        return {"path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                "state": "ABSENT"}
    try:
        age_h = round((now_ts - p.stat().st_mtime) / 3600, 2)
    except OSError:
        age_h = None
    return {"path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            "state": "PRESENT", "age_h": age_h, "doc": doc}


def _challenger_result(cid: str, arts: dict[str, dict[str, Any]],
                       meta: dict[str, Any]) -> dict[str, Any]:
    if cid == "method_challenger":
        ch = (arts.get("COEVOLUTION.json", {}).get("doc") or {}).get("method_challenger") or {}
        if not ch:
            return {"status": "UNMEASURED", "why": "no method_challenger block on the report"}
        v = (ch.get("verdict") or {}).get("arms") or {}
        return {"status": "MEASURED" if ch.get("decided") else "UNMEASURED",
                "runs": ch.get("runs"), "wins": ch.get("wins"),
                "gap": ch.get("oos_net_gain_gap_joint_minus_sequential"),
                "verdicts": {k: (r or {}).get("verdict") for k, r in v.items()},
                "uncertainty": "posterior P(worse than leader) per arm; mean and SE of the "
                               "out-of-sample net-gain gap"}
    if cid == "representation_methods":
        rows = (((arts.get("REPRESENTATION_FORGE.json", {}).get("doc") or {}).get("roi") or {})
                .get("rows") or [])
        fam = {str(r.get("family")): r for r in rows if isinstance(r, dict) and r.get("family")}
        arms = {}
        for name, r in fam.items():
            born = int(float(r.get("used_by_candidates") or 0))
            won = min(int(float(r.get("survivors") or 0)), born)
            arms[name] = {"born": born, "certified": won, "alpha": 1.0 + won,
                          "beta": 1.0 + born - won, "group": "representation_method",
                          "cost_basis": "candidates built on the family's representations"}
        if not arms:
            return {"status": "UNMEASURED", "why": "no ROI rows on REPRESENTATION_FORGE.json"}
        v = arena.judge(arms)
        judged = {k: r["verdict"] for k, r in (v.get("arms") or {}).items()}
        return {"status": "MEASURED" if any(x != "UNMEASURED" for x in judged.values())
                else "UNMEASURED", "verdicts": judged, "leader": v.get("leader"),
                "uncertainty": "Beta posterior survivor rate per representation family; "
                               "P(worse than leader) decides TRAILS"}
    if cid in ("cadence", "bound"):
        st = meta.get("cadence_and_bound") or {}
        if st.get("status") != "MEASURED":
            return {"status": "UNMEASURED", "why": st.get("why") or "study not run"}
        if cid == "cadence":
            return {"status": "MEASURED", "subject": st["subject"], "cadence": st["cadence"],
                    "p_faster_beats_slower": st["p_faster_beats_slower"],
                    "uncertainty": "90% block-bootstrap interval per cadence",
                    "assumptions": st["assumptions"]}
        return {"status": "MEASURED", "subject": st["subject"], **st["bound"],
                "uncertainty": "in-sample bound; the gap is an upper limit on what a better "
                               "fixed-weight rule could have added on this window"}
    if cid == "reusable_holdout":
        g = (meta.get("ordering") or {}).get("reusable_holdout") or {}
        return {"status": "MEASURED" if g.get("status") in ("VALID", "EXHAUSTED")
                else "UNMEASURED",
                "holdout_status": g.get("status"), "budget_left": g.get("budget_left"),
                "overfit_this_pass": g.get("overfit"), "winner": g.get("winner"),
                "uncertainty": "Thresholdout's guarantee holds while budget_left > 0"}
    return {"status": "UNMEASURED"}


def frontier(meta: dict[str, Any], now_ts: float | None = None) -> dict[str, Any]:
    """THE FRONTIER REPORT: per limitation of the research process, what limits it, what was
    tested, the result and its uncertainty, what it would take to go further, and the next
    highest-value experiment. Read from artifacts every pass; nothing here is asserted."""
    now = time.time() if now_ts is None else now_ts
    rows = []
    for lim in LIMITATIONS:
        arts = {a: _artifact(a, now) for a in lim["artifacts"]}
        if lim.get("challenger"):
            res = _challenger_result(str(lim["challenger"]), arts, meta)
            status = res["status"]
        elif lim.get("blocked_by"):
            res, status = {"status": "BLOCKED_BY_POLICY"}, "BLOCKED_BY_POLICY"
        else:
            res, status = {"status": "NOT_BUILT"}, "NOT_BUILT"
        rows.append({"id": lim["id"], "owner": lim["owner"], "limit": lim["limit"],
                     "tested": lim.get("challenger") or "no matched challenger yet",
                     "result": res, "status": status,
                     "artifacts": {k: {kk: vv for kk, vv in v.items() if kk != "doc"}
                                   for k, v in arts.items()},
                     "resources_to_go_further": lim["resources"],
                     "next_experiment": lim["next"]})
    auction = _read(_rep("RESEARCH_AUCTION.json"))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "limitations": rows, "counts": counts,
            "measured_share": round(counts.get("MEASURED", 0) / len(rows), 4),
            "compute_auction": {"source": "research/research_auction.py",
                                "state": "PRESENT" if auction else "ABSENT",
                                "note": "producer competition for compute is the auction's; "
                                        "this report names experiments, it allocates nothing"},
            "rule": ("a NOT_BUILT or UNMEASURED row is the measurement, never a pass; the "
                     "report allocates no compute and moves no gate")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=180.0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        from research import portfolio_evidence as pe
        doc["cadence_and_bound"] = cadence_and_bound(pe.daily_series())
    except Exception as exc:
        doc["cadence_and_bound"] = {"status": "UNMEASURED",
                                    "why": f"{type(exc).__name__}: {exc}"}
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"meta rnd: could not write {OUT}: {exc}")
        return 1
    try:
        fr = frontier(doc)
        FRONTIER.write_text(json.dumps(fr, indent=1, default=str), encoding="utf-8")
        print(f"research frontier: {fr['counts']} -> {FRONTIER}")
    except Exception as exc:                       # the ordering result above still stands
        print(f"research frontier: FAILED {type(exc).__name__}: {exc}")
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
