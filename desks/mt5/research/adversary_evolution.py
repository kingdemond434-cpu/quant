"""F17 -- AN ADVERSARY THAT LEARNS, so the gates are tested against a moving target.

THE PRINCIPAL, 2026-09-12:

    An EVOLVING adversary population: every time the scientist improves, the destroyer invents new
    timestamp perturbations, synthetic leaks, state shifts, cost regimes, execution failures,
    covariance breaks and selection traps, so researchers evolve against a moving target.

THE GAP, AS THE LEDGER STATES IT: `adversary.py` is already excellent -- poison canaries through
the REAL gauntlet, silent-defect hunting, promoter gaming, anti-echo genealogy -- but the
adversary is STATIC. Five hand-written attacks, unchanged since the day they were written. A
suite that passes the same five attacks forever proves it can reject those five, which is a
smaller claim every time the desk changes.

WHAT AN EVOLVING ADVERSARY IS, precisely. The five canaries are named KINDS; this is a population
of CONTINUOUS genomes over the same failure space -- how much of tomorrow leaks into the signal,
how many draws the winner was selected from, how small the edge is against its spread, how many
free parameters it claims, how far the timestamp is shifted, how much the return series
autocorrelates, what share of the sample comes from another regime. The named canaries are corners
of that space. Between the corners is everything nobody wrote down.

EVERY ATTACK DECLARES ITS OWN GROUND TRUTH, AND THIS IS THE PART THAT TOOK TWO TRIES.

The first version scored any gauntlet PASS as a breach and reported three on its first run -- all
with leak near 1.0. They were not breaches. `adversary.docket_cell`'s own docstring says exactly
what they were: stamping a current-bar signal at offset 0 "would hand the engine a signal that is
literally the next bar's return -- undetectable by ANY engine, because the caller cheated before
the harness ever saw it -- and would raise the CAPITAL alarm every hour for a defect no gate can
have." An adversary that manufactures its own leak and then reports the gates for missing it is an
alarm generator.

Worse, in this harness a strong HONEST edge and a leak are the same array: the signal is built out
of the outcome either way, and only the STAMP separates them. So a genome with a large true edge,
correctly stamped, SHOULD pass -- and counting that as a breach would have the population evolve
toward discovering that the gates admit good strategies.

So each genome now carries a declared verdict it OUGHT to receive, derived from its own
pathologies -- current-bar information, an edge smaller than its spread, more parameters than
observations, survivorship without a real edge -- and its stamp is the honest timestamp of the
information it carries. Then:

    BREACH            ground truth REJECT and the gates ADMITTED it. A defect, with a recipe.
    FALSE_REJECTION   ground truth ADMIT and the gates REJECTED it. Also worth knowing: a gate
                      that refuses a clean strong edge is costing the desk certificates.
    correct           the gates agreed with the ground truth.

The gradient for a REJECT genome is how many gates it got past, so the population climbs toward
the boundary instead of wandering a flat landscape of uniform rejection. ADMIT genomes are
CONTROLS and do not breed toward breach -- they measure the other error.

THE POPULATION IS PERSISTENT, which is what makes it co-evolution rather than a fresh random
sample every hour. It is stored, it inherits, and when the desk tightens a gate the attacks that
used to score well lose their fitness and the population moves -- which is exactly the moving
target the principal asked for.

IT USES THE REAL JUDGE. Cells are built with `adversary.docket_cell` and judged by
`external_gauntlet.run_gauntlet` -- the same ten gates, the same costs, the same program-level
tests. An adversary graded by its own simulator would only prove that two of this desk's programs
agree.

A BREACH IS THE POINT AND IS NOT AN EMERGENCY. If a genome gets past the gates, that is the
finding: it is written down with its exact parameters so the gap can be closed deliberately. The
canary rejection rate is a CONSTANT to hold at 100%, and the way to hold a constant is to keep
attacking it with things nobody has tried.

    python desks/mt5/research/adversary_evolution.py [--apply] [--generations N]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

POP = DESK / "data" / "adversary_population.json"
OUT = DESK / "reports" / "ADVERSARY_EVOLUTION.json"

#: The attack genome. Each gene is a KNOB ON A KNOWN FAILURE MODE, with its range chosen so that
#: one end is harmless and the other is the named canary -- the hand-written attacks are corners
#: of this space, and the population searches between them.
GENES: dict[str, tuple[float, float]] = {
    #: share of tomorrow's return mixed into the signal. 1.0 IS the `lookahead` canary.
    "leak": (0.0, 1.0),
    #: draws the winner was selected from. 500 IS the `survivor_biased` canary.
    "selection_draws": (1.0, 1200.0),
    #: genuine correlation between signal and outcome, before costs.
    "true_edge": (0.0, 0.30),
    #: the edge's size as a multiple of the modelled spread. Below 1 IS `cost_blind`.
    "edge_over_cost": (0.2, 8.0),
    #: free parameters claimed against the sample. Above 1 IS `overfit_params`.
    "params_per_obs": (0.0, 1.5),
    #: bars the signal is shifted against the outcome. Negative is a subtle lookahead that no
    #: named canary covers -- half a bar of leak is not the `lookahead` corner and is the shape a
    #: real harness bug actually takes.
    "timestamp_shift": (-2.0, 2.0),
    #: autocorrelation of the return series. The gates' i.i.d. assumptions are the target.
    "autocorr": (0.0, 0.85),
    #: share of the sample drawn from a different distribution -- a covariance break mid-history.
    "regime_break": (0.0, 0.6),
}

#: Population and generations per run. Each generation is ONE run_gauntlet call over the whole
#: population, so the cost is generations x (a docket of POP_SIZE cells) -- bounded and small
#: against an hourly sweep of thousands.
POP_SIZE = 14
GENERATIONS = 2

#: Observations per attack. 400 matches the named canaries so a corner of this space reproduces
#: the canary it corresponds to, which is the only way to know the space is the right space.
N_OBS = 400

#: Mutation scale, as a fraction of each gene's range. Large enough to leave a local basin,
#: small enough that a child is recognisably its parent.
MUT = 0.25

#: Slots reserved for CLEAN genomes -- no pathology, a genuine correctly-stamped edge larger than
#: its costs. Reserved rather than hoped for: with eight genes and four pathology conditions a
#: random draw is clean perhaps one time in twenty, and the first run produced NONE, so the
#: gates' other error -- refusing a good strategy -- was silently unmeasured while the report
#: printed "0 FALSE REJECTIONS". An empty control arm is not a clean bill of health.
CONTROL_SLOTS = 3

SEED = 20260912


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _random_genome(rng: random.Random) -> dict[str, float]:
    return {g: rng.uniform(lo, hi) for g, (lo, hi) in GENES.items()}


def _control_genome(rng: random.Random) -> dict[str, float]:
    """A genome with NO pathology: the gates ought to pass it, and a refusal is their error.

    Constructed rather than sampled, because the pathology conditions between them cover most of
    the space and a random draw is clean about one time in twenty. Its edge is drawn across a
    range so the control arm spans weak-but-honest to strong-but-honest -- a gate that refuses
    the weak end and admits the strong one is behaving correctly, and only a refusal of the
    strong end is a finding.
    """
    return {
        "leak": rng.uniform(0.0, LEAK_IS_REAL * 0.5),
        "selection_draws": rng.uniform(1.0, 20.0),
        "true_edge": rng.uniform(0.06, 0.30),
        "edge_over_cost": rng.uniform(2.0, 8.0),
        "params_per_obs": rng.uniform(0.0, 0.4),
        "timestamp_shift": rng.uniform(0.0, 0.4),
        "autocorr": rng.uniform(0.0, 0.3),
        "regime_break": rng.uniform(0.0, 0.15),
    }


def _mutate(g: dict[str, float], rng: random.Random) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, (lo, hi) in GENES.items():
        v = float(g.get(name, (lo + hi) / 2))
        v += rng.gauss(0.0, (hi - lo) * MUT)
        out[name] = max(lo, min(hi, v))
    return out


def _cross(a: dict[str, float], b: dict[str, float], rng: random.Random) -> dict[str, float]:
    return {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENES}


#: A genome carries CURRENT-BAR information once its leak exceeds this. Below it the signal is
#: dominated by the honest components and the stamp that fits is the earlier one.
LEAK_IS_REAL = 0.05


def ground_truth(g: dict[str, float]) -> tuple[str, list[str]]:
    """What verdict this attack OUGHT to receive, and why. Declared before the gates see it.

    WITHOUT THIS THE ORGAN CANNOT TELL A BREACH FROM THE GATES WORKING. In this harness a strong
    honest edge and a lookahead are the same array of numbers -- the signal is built out of the
    outcome either way -- and only the timestamp separates them. A genome with a large true edge,
    correctly stamped, SHOULD pass; scoring that as a breach teaches the population to discover
    that the gates admit good strategies.
    """
    why: list[str] = []
    if float(g["leak"]) > LEAK_IS_REAL:
        why.append(f"carries current-bar information (leak {float(g['leak']):.2f}), so it is "
                   f"stamped on the bar it knows and the engine's one-bar delay must defeat it")
    if float(g["edge_over_cost"]) < 1.0:
        why.append(f"its edge is smaller than the spread it must cross "
                   f"(edge_over_cost {float(g['edge_over_cost']):.2f})")
    if float(g["params_per_obs"]) > 1.0:
        why.append(f"it claims more free parameters than observations "
                   f"({float(g['params_per_obs']):.2f} per obs)")
    if float(g["selection_draws"]) > 50 and float(g["true_edge"]) < 0.02:
        why.append(f"it is the best of {int(g['selection_draws'])} draws with no real edge, so "
                   f"any apparent skill is survivorship")
    return ("REJECT", why) if why else (
        "ADMIT", ["a genuine, correctly stamped edge larger than its costs with no pathology -- "
                  "the gates SHOULD pass this, and a rejection is their error, not a breach"])


def stamp_for(g: dict[str, float]) -> int:
    """The HONEST timestamp for the information this genome carries.

    A signal containing the current bar's return exists only once that bar has closed, so it is
    stamped on that bar (offset 1) exactly as the named `lookahead` canary is. Stamping it a bar
    earlier is the caller cheating, not the harness leaking.
    """
    return 1 if float(g["leak"]) > LEAK_IS_REAL else 0


def _materialise(g: dict[str, float], rng: random.Random) -> tuple[list[float], list[float]]:
    """Turn a genome into (signal, forward return). Deterministic given the rng handed in."""
    n = N_OBS
    # The outcome series, with autocorrelation and a regime break where the genome asks for them.
    rho = float(g["autocorr"])
    fwd: list[float] = []
    prev = 0.0
    for i in range(n):
        scale = 0.01 * (3.0 if i < n * float(g["regime_break"]) else 1.0)
        e = rng.gauss(0.0, scale)
        prev = rho * prev + math.sqrt(max(1e-9, 1 - rho * rho)) * e
        fwd.append(prev)

    # The signal: part genuine edge, part leak of the outcome itself, part noise.
    leak = float(g["leak"])
    edge = float(g["true_edge"])
    base = [edge * f / 0.01 + rng.gauss(0.0, 1.0) for f in fwd]
    sig = [(1 - leak) * b + leak * (f / 0.01) for b, f in zip(base, fwd, strict=True)]

    # SELECTION: keep the best of k draws, presented as one discovery. This is survivorship as a
    # continuous knob rather than as the 500-draw corner.
    k = int(max(1, round(float(g["selection_draws"]))))
    if k > 1:
        best, best_c = sig, _corr(sig, fwd)
        for _ in range(min(k, 1200) - 1):
            cand = [(1 - leak) * rng.gauss(0.0, 1.0) + leak * (f / 0.01) for f in fwd]
            c = _corr(cand, fwd)
            if c > best_c:
                best, best_c = cand, c
        sig = best

    # TIMESTAMP SHIFT: a whole-bar displacement of the signal against the outcome. A NEGATIVE
    # shift is a lookahead no named canary covers -- the partial kind a real harness bug takes.
    shift = round(float(g["timestamp_shift"]))
    if shift > 0:
        sig = [0.0] * shift + sig[:-shift or None]
    elif shift < 0:
        k2 = -shift
        sig = sig[k2:] + [0.0] * k2

    # COST SCALE: shrink the outcome so the same signal is worth less than its spread.
    scale = float(g["edge_over_cost"])
    fwd = [f * min(scale, 8.0) / 8.0 for f in fwd]
    return sig, fwd


def _corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((a[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((b[i] - mb) ** 2 for i in range(n)))
    return num / (da * db) if da > 0 and db > 0 else 0.0


def _judge(population: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]],
                                                                         str | None]:
    """Put the whole population through the REAL ten gates in one docket."""
    try:
        import external_gauntlet  # type: ignore[import-not-found]

        from research.adversary import CANARY_META, docket_cell
    except ImportError as exc:
        return population, (f"BLOCKED: the canonical judge is not importable ({exc}). This organ "
                            f"refuses to grade an adversary with its own simulator -- that would "
                            f"prove only that two of this desk's programs agree.")
    cells = []
    for ind in population:
        sig, fwd = _materialise(ind["genome"], random.Random(ind["seed"]))  # noqa: S311
        ind["_sig_len"] = len(sig)
        truth, reasons = ground_truth(ind["genome"])
        ind["ground_truth"] = truth
        ind["ground_truth_why"] = reasons
        ind["stamp_offset"] = stamp_for(ind["genome"])
        try:
            cells.append(docket_cell(ind["id"], sig, fwd,
                                     stamp_offset=stamp_for(ind["genome"])))
        except Exception as exc:
            ind["error"] = f"{type(exc).__name__}: {exc}"
    if not cells:
        return population, "BLOCKED: no attack could be built into a docket cell"
    try:
        out = external_gauntlet.run_gauntlet(cells, "adversary-evolution", CANARY_META)
    except Exception as exc:
        return population, f"BLOCKED: run_gauntlet raised {type(exc).__name__}: {exc}"
    verdicts = {str(v.get("family", "")).removeprefix("canary_"): v
                for v in (out.get("verdicts") or [])}
    for ind in population:
        v = verdicts.get(ind["id"])
        if v is None:
            ind["verdict"] = "NO_VERDICT"
            ind["fitness"] = 0.0
            continue
        stages = v.get("stages") or {}
        n_gates = max(len(stages), 1)
        passed_gates = sum(1 for s in stages.values() if s.get("passed"))
        if v.get("unmeasured"):
            # UNMEASURED IS NOT A BREACH AND IS NOT A REJECTION. An attack the certifier could
            # not judge has proved nothing about the gates, and scoring it as either would let
            # the population evolve toward being UNJUDGEABLE -- which is a way to look strong
            # while testing nothing.
            ind["verdict"] = "UNMEASURED"
            ind["fitness"] = 0.0
            ind["why"] = str((stages.get("observations") or {}).get("why", ""))[:200]
            continue
        admitted = bool(v.get("passed"))
        truth = str(ind.get("ground_truth") or "REJECT")
        ind["gates_passed"] = passed_gates
        ind["gates_total"] = len(stages)
        ind["failed_gates"] = [g for g, s in stages.items() if not s.get("passed")][:6]
        # THE NUMBERS BEHIND THE REFUSAL, not just its name. "failed deflated_sharpe" is a label;
        # the dsr it produced against the bar it needed at the trial count it was charged is the
        # finding, and without it a false rejection cannot be argued with.
        ds = stages.get("deflated_sharpe") if isinstance(stages, dict) else None
        if isinstance(ds, dict):
            ind["deflated_sharpe"] = {k: ds.get(k) for k in
                                      ("passed", "dsr", "sr0", "n_trials",
                                       "variance_of_sharpes", "variance_basis",
                                       "variance_measured_this_sweep") if k in ds}
        if truth == "REJECT":
            ind["verdict"] = "BREACH" if admitted else "REJECTED"
            # THE GRADIENT, for attacks that ought to fail. A rejected attack scores how far it
            # got, so the population climbs toward the boundary instead of wandering a flat
            # landscape of uniform rejection.
            ind["fitness"] = 1.0 + passed_gates if admitted else passed_gates / n_gates
        else:
            # A CONTROL. It ought to pass, so passing is correct and earns no fitness -- the
            # population must not learn that the way to score is to stop being an attack.
            ind["verdict"] = "CORRECT_ADMIT" if admitted else "FALSE_REJECTION"
            ind["fitness"] = 0.0
    return population, None


def build(generations: int = GENERATIONS) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rng = random.Random(SEED + int(now.timestamp()) // 3600)  # noqa: S311 -- attack data
    prior = _read(POP) or {}
    survivors: list[dict[str, Any]] = [i for i in (prior.get("population") or [])
                                       if isinstance(i, dict) and i.get("genome")]
    lineage = int(prior.get("generation") or 0)

    population: list[dict[str, Any]] = []
    for i in range(POP_SIZE):
        if i < CONTROL_SLOTS:
            # THE CONTROL ARM IS RESERVED, NEVER HOPED FOR. These measure the gates' other error
            # and they do not breed -- an attack population that learned to score by becoming
            # harmless would be measuring nothing at all.
            population.append({"id": f"ctl_g{lineage}_{i}", "genome": _control_genome(rng),
                               "parent": None, "seed": rng.randrange(1 << 30),
                               "is_control": True})
            continue
        if i < CONTROL_SLOTS + len(survivors) // 2 and survivors:
            # INHERITANCE IS WHAT MAKES THIS CO-EVOLUTION. A fresh random sample every hour is a
            # lottery that forgets; a population that carries its best forward moves when the
            # gates move, which is the moving target the principal asked for.
            a = survivors[(i - CONTROL_SLOTS) % len(survivors)]
            b = survivors[rng.randrange(len(survivors))]
            g = _mutate(_cross(a["genome"], b["genome"], rng), rng)
            parent = f"{a.get('id')}+{b.get('id')}"
        else:
            g = _random_genome(rng)
            parent = None
        population.append({"id": f"adv_g{lineage}_{i}", "genome": g, "parent": parent,
                           "seed": rng.randrange(1 << 30)})

    blocked = None
    history: list[dict[str, Any]] = []
    for gen in range(max(1, generations)):
        population, blocked = _judge(population, rng)
        if blocked:
            break
        scored = [i for i in population if isinstance(i.get("fitness"), (int, float))]
        scored.sort(key=lambda r: -float(r["fitness"]))
        history.append({
            "generation": lineage + gen,
            "n": len(scored),
            "best_fitness": round(float(scored[0]["fitness"]), 4) if scored else None,
            "mean_fitness": (round(sum(float(s["fitness"]) for s in scored) / len(scored), 4)
                             if scored else None),
            "n_breach": sum(1 for s in scored if s.get("verdict") == "BREACH"),
            "n_unmeasured": sum(1 for s in scored if s.get("verdict") == "UNMEASURED"),
        })
        if gen + 1 < max(1, generations) and scored:
            # ONLY ATTACKS BREED. Controls are re-drawn fresh each generation: they are a
            # measurement of the gates' other error, not a lineage, and letting them into the
            # elite would let the population drift toward harmlessness.
            attack_pool = [s for s in scored if not s.get("is_control")]
            elite = (attack_pool or scored)[: max(2, len(attack_pool or scored) // 3)]
            nxt: list[dict[str, Any]] = []
            for i in range(POP_SIZE):
                if i < CONTROL_SLOTS:
                    nxt.append({"id": f"ctl_g{lineage + gen + 1}_{i}",
                                "genome": _control_genome(rng), "parent": None,
                                "seed": rng.randrange(1 << 30), "is_control": True})
                    continue
                a = elite[i % len(elite)]
                b = elite[rng.randrange(len(elite))]
                nxt.append({"id": f"adv_g{lineage + gen + 1}_{i}",
                            "genome": _mutate(_cross(a["genome"], b["genome"], rng), rng),
                            "parent": f"{a['id']}+{b['id']}",
                            "seed": rng.randrange(1 << 30)})
            population = nxt

    scored = [i for i in population if isinstance(i.get("fitness"), (int, float))]
    scored.sort(key=lambda r: -float(r["fitness"]))
    breaches = [i for i in scored if i.get("verdict") == "BREACH"]
    unmeasured = [i for i in scored if i.get("verdict") == "UNMEASURED"]
    false_rej = [i for i in scored if i.get("verdict") == "FALSE_REJECTION"]
    controls = [i for i in scored if str(i.get("ground_truth")) == "ADMIT"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": ("BLOCKED" if blocked else "BREACH" if breaches else "OK"),
        "blocked_why": blocked,
        "lineage_generation": lineage + max(1, generations),
        "population_size": POP_SIZE,
        "generations_this_run": len(history),
        "history": history,
        "n_breach": len(breaches),
        "n_unmeasured": len(unmeasured),
        "controls": {
            "status": "OK" if controls else "UNMEASURED",
            "unmeasured_why": (None if controls else
                               "the control arm is empty this pass, so the gates' other error -- "
                               "refusing a clean strong edge -- was not measured. Reporting "
                               "'0 false rejections' off an empty arm would be a clean bill of "
                               "health issued without an examination."),
            "n": len(controls), "n_false_rejection": len(false_rej),
            "rows": [{"id": c["id"], "gates_passed": c.get("gates_passed"),
                      "failed_gates": c.get("failed_gates"),
                      "deflated_sharpe": c.get("deflated_sharpe"),
                      "genome": {k: round(v, 4) for k, v in c["genome"].items()}}
                     for c in false_rej[:6]],
            "why": ("genomes with NO pathology -- a genuine, correctly stamped edge larger than "
                    "its costs. They ought to pass, so passing earns no fitness and the "
                    "population cannot learn that the way to score is to stop being an attack. "
                    "A rejection here is the gates' OTHER error: refusing a clean strong edge "
                    "costs the desk certificates, and nothing else measures it."),
        },
        "breaches": [{"id": b["id"], "genome": {k: round(v, 5) for k, v in b["genome"].items()},
                      "ground_truth_why": b.get("ground_truth_why"),
                      "stamp_offset": b.get("stamp_offset"),
                      "gates_passed": b.get("gates_passed"),
                      "reproduce": ("materialise this genome with adversary_evolution._materialise "
                                    "at the recorded seed and judge it through "
                                    "external_gauntlet.run_gauntlet"),
                      "seed": b["seed"]} for b in breaches[:10]],
        "fittest_rejected": [{"id": s["id"], "fitness": round(float(s["fitness"]), 4),
                              "gates_passed": s.get("gates_passed"),
                              "failed_gates": s.get("failed_gates"),
                              "genome": {k: round(v, 4) for k, v in s["genome"].items()}}
                             for s in scored if s.get("verdict") == "REJECTED"][:6],
        "_population": scored[: max(4, POP_SIZE // 2)],
        "genes": {k: list(v) for k, v in GENES.items()},
        "judge": ("external_gauntlet.run_gauntlet over adversary.docket_cell -- the same ten "
                  "gates, costs and program-level tests the desk certifies with. An adversary "
                  "graded by its own simulator would prove only that two programs agree."),
        "unmeasured_is_neither": (
            "an attack the certifier could not judge has proved nothing about the gates. Scoring "
            "it as a rejection would let the population evolve toward being UNJUDGEABLE, which is "
            "a way to look strong while testing nothing."),
        "why": (
            "adversary.py runs five hand-written attacks, unchanged since the day they were "
            "written. A suite that passes the same five forever proves it can reject those five, "
            "and that is a smaller claim every time the desk changes. These five are CORNERS of a "
            "continuous space; between the corners is everything nobody wrote down."),
        "boundary": (
            "a breach is a FINDING, not an emergency, and nothing here changes a gate. It is "
            "written down with the exact genome and seed so the gap is closed deliberately."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--generations", type=int, default=GENERATIONS)
    a = ap.parse_args(argv)
    doc = build(a.generations)
    print(f"adversary evolution: {doc['status']}   generation {doc['lineage_generation']}, "
          f"population {doc['population_size']}")
    if doc.get("blocked_why"):
        print(f"  {doc['blocked_why'][:200]}")
    for h in doc["history"]:
        print(f"  gen {h['generation']:<4} best {h['best_fitness']}  mean {h['mean_fitness']}  "
              f"breach {h['n_breach']}  unmeasured {h['n_unmeasured']}")
    if doc["n_breach"]:
        print(f"  {doc['n_breach']} BREACH(ES) -- attacks the ten gates ADMITTED:")
        for b in doc["breaches"]:
            print(f"    {b['id']}  gates_passed={b.get('gates_passed')}  {b['genome']}")
    else:
        print("  no breach: every attack that OUGHT to be rejected was rejected")
    ctl = doc["controls"]
    if ctl.get("status") == "OK":
        print(f"  controls: {ctl['n']} clean genome(s), {ctl['n_false_rejection']} FALSE "
              f"REJECTION(S) -- the gates' other error, which nothing else measures")
    else:
        print(f"  controls: UNMEASURED -- {ctl['unmeasured_why'][:120]}")
    for c in ctl["rows"][:3]:
        ds = c.get("deflated_sharpe") or {}
        print(f"    {c['id']} refused at {', '.join(c['failed_gates'] or [])[:40]}"
              + (f"  dsr={ds.get('dsr')} sr0={ds.get('sr0')} trials={ds.get('n_trials')}"
                 if ds else ""))
    for s in doc["fittest_rejected"][:4]:
        print(f"    fittest rejected {s['id']} at {s['fitness']} "
              f"(failed {', '.join(s['failed_gates'] or [])[:60]})")
    if not a.apply:
        print("  --apply not given; population not persisted")
        return 0
    pop = doc.pop("_population")
    POP.parent.mkdir(parents=True, exist_ok=True)
    POP.write_text(json.dumps({"generation": doc["lineage_generation"],
                               "updated": doc["at"], "population": pop},
                              indent=1, default=str), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {POP}\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
