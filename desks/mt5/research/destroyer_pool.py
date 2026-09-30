"""DESTROYERS THAT REPRODUCE -- two populations, one arms race.

THE GAP THE LEDGER NAMED (Tier-1 B17): *"falsifiers attack certificates, but there are no paired
populations and destroyers do not reproduce when they kill."* `falsifier_run` runs a FIXED
catalogue of six objections. A fixed catalogue is a predator that never adapts: every certificate
that survives it survives it for the same reason, and the objections that would have killed the
survivors are the ones nobody wrote.

TWO POPULATIONS, BOTH PERSISTED IN `data/destroyer_pool.json`:

    PREDATORS   destroyer genomes. A genome is a catalogue falsifier plus a VIEW of the evidence:
                which contiguous blocks of the certificate's own signals the test is allowed to
                see, and what multiple of the modelled cost it is charged. Nothing about the
                statistic is invented -- the objection is one the desk already wrote; what
                evolves is the slice of evidence it is asked about, which is exactly the axis a
                fixed battery cannot search.
    PREY        certificates, with the generations they have survived and who last killed them.
                A certificate that has survived twenty generations of an ADAPTING predator is a
                different fact from one that survived six fixed tests once.

FITNESS IS NOVEL KILLS PER SECOND, and novelty is what makes this co-evolution rather than a
second battery: a genome that kills a certificate the fixed catalogue ALREADY killed has told the
desk nothing (weight 1), and one that kills a certificate the catalogue passed has found a false
positive the desk was about to believe (weight NOVEL_WEIGHT). Cost is charged in seconds, so a
lethal-but-slow objection loses to an equally lethal cheap one -- the same economics the
catalogue's own schedule uses.

REPRODUCTION. Each pass, the top `ELITE` genomes by fitness survive, produce mutated offspring
(the view jittered by a deterministic RNG seeded from the parent and the generation), and the
worst are retired. Population size is fixed, so the pool cannot grow without bound on a box whose
hourly budget is already contested.

WHAT A KILL MAY AND MAY NOT DO. An evolved destroyer's kill is ADVISORY and is published under
`evolved` in FALSIFIERS.json beside the catalogue's own verdict. It does not retire a sleeve, does
not void a certificate and does not touch the ten gates: the sealed judge decides exactly what it
decided before (L1.60; the principal's never-reduce-aggressiveness order). What it DOES change is
what the desk knows about its survivors, and -- through `meta_rnd` -- the ORDER the catalogue is
run in, which costs nothing and kills sooner.

    python desks/mt5/research/destroyer_pool.py --once --budget-s 300
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "mt5desk"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

POOL = DESK / "data" / "destroyer_pool.json"
#: `falsifier_run` writes FALSIFIER_VERDICTS.json; FALSIFIERS.json is the older name and is
#: kept as a fallback so a box carrying either is scored rather than reported empty.
FALSIFIERS_REPORT = DESK / "reports" / "FALSIFIER_VERDICTS.json"
FALSIFIERS_ALT = DESK / "reports" / "FALSIFIERS.json"
OUT = DESK / "reports" / "DESTROYER_POOL.json"

POP_SIZE = 12
ELITE = 4
NOVEL_WEIGHT = 5.0
MIN_SIGNALS = 24          # below this a view is UNMEASURED, never a kill
MAX_PER_CERT = 4          # genomes attempted per certificate per pass, cheapest first
BASES = ("cost_surface", "half_stability", "truncation", "tail_worst_decile", "placebo_battery")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _genome(gid: str, base: str, block_frac: float, block_len: int, cost_mult: float,
            gen: int, parent: str | None) -> dict[str, Any]:
    return {"id": gid, "base": base, "gen": gen, "parent": parent,
            "view": {"block_frac": round(block_frac, 3), "block_len": int(block_len),
                     "cost_mult": round(cost_mult, 3)},
            "born_at": datetime.now(tz=UTC).isoformat(timespec="seconds")}


def seed_pool() -> dict[str, Any]:
    """The founding population: every base at three views, so generation 0 spans the axis."""
    rng = random.Random(20260923)  # noqa: S311 -- a breeding RNG, seeded for reproducibility
    genomes: list[dict[str, Any]] = []
    i = 0
    for base in BASES:
        for frac, blen, cm in ((0.5, 8, 1.0), (0.35, 16, 1.5), (0.7, 4, 2.0)):
            if len(genomes) >= POP_SIZE:
                break
            genomes.append(_genome(f"d{i:03d}", base, frac + rng.uniform(-0.05, 0.05), blen, cm,
                                   0, None))
            i += 1
    return {"generation": 0, "genomes": genomes, "prey": {}, "records": {}}


def load_pool() -> dict[str, Any]:
    doc = _read(POOL)
    if not isinstance(doc, dict) or not isinstance(doc.get("genomes"), list) \
            or not doc.get("genomes"):
        doc = seed_pool()
        _write(POOL, doc)
    doc.setdefault("prey", {})
    doc.setdefault("records", {})
    return dict(doc)


def _view(signals: list[Any], view: dict[str, Any], seed: int) -> list[Any]:
    """The contiguous blocks of signals this genome is allowed to see."""
    n = len(signals)
    blen = max(1, int(view.get("block_len") or 8))
    frac = min(max(float(view.get("block_frac") or 0.5), 0.05), 1.0)
    blocks = [(i, min(i + blen, n)) for i in range(0, n, blen)]
    if not blocks:
        return []
    keep = max(1, round(len(blocks) * frac))
    rng = random.Random(seed)  # noqa: S311 -- deterministic view sampling, not a secret
    chosen = sorted(rng.sample(range(len(blocks)), min(keep, len(blocks))))
    out: list[Any] = []
    for b in chosen:
        lo, hi = blocks[b]
        out.extend(signals[lo:hi])
    return out


def evaluate(genome: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """Run one genome's objection against one certificate's own evidence, on its own view."""
    from libs.validation import falsifiers
    base = str(genome.get("base"))
    fn = falsifiers.FALSIFIERS.get(base)
    if fn is None:
        return {"verdict": "UNMEASURED", "why": f"unknown base falsifier {base}"}
    signals = list(inputs.get("signals") or [])
    seed = abs(hash((str(genome.get("id")), int(genome.get("gen") or 0)))) % (2**31)
    view = _view(signals, genome.get("view") or {}, seed)
    if len(view) < MIN_SIGNALS:
        return {"verdict": "UNMEASURED",
                "why": f"view holds {len(view)} signals, under the floor of {MIN_SIGNALS}"}
    cost = inputs.get("cost")
    if cost is None:
        return {"verdict": "UNMEASURED", "why": str(inputs.get("cost_basis") or "no cost model")}
    mult = float((genome.get("view") or {}).get("cost_mult") or 1.0)
    t0 = time.monotonic()
    try:
        res = dict(fn(inputs["df"], view, float(cost) * mult,
                      family=inputs.get("family"), params=inputs.get("params") or {},
                      usd=inputs.get("usd")))
    except Exception as exc:                                    # a bad genome never stops a pass
        return {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    res["seconds"] = round(time.monotonic() - t0, 3)
    res["n_view"] = len(view)
    res["cost_mult"] = mult
    return res


def attack(inputs: dict[str, Any], deadline: float, *, catalogue_status: str = "",
           pool: dict[str, Any] | None = None,
           max_genomes: int = MAX_PER_CERT) -> dict[str, Any]:
    """THE CONSUMER'S DOOR. `falsifier_run` calls this once per certificate, inside the same
    deadline it gives the catalogue, and publishes what comes back under `evolved`.

    Genomes are attempted in fitness order, cheapest first, and whatever the deadline does not
    reach is recorded as NOT_REACHED -- a truncated attack is never a survival."""
    p = pool if pool is not None else load_pool()
    genomes = list(p.get("genomes") or [])
    fits = p.get("fitness") or {}
    genomes.sort(key=lambda g: -float(fits.get(str(g.get("id")), {}).get("fitness", 0.0)))
    results: dict[str, Any] = {}
    kills: list[str] = []
    not_reached: list[str] = []
    for g in genomes[:max_genomes]:
        gid = str(g.get("id"))
        if time.monotonic() > deadline:
            not_reached.append(gid)
            continue
        res = evaluate(g, inputs)
        results[gid] = {"base": g.get("base"), "view": g.get("view"), "gen": g.get("gen"),
                        **{k: v for k, v in res.items()
                           if k in ("verdict", "why", "seconds", "n_view", "cost_mult", "n")}}
        if str(res.get("verdict")) == "FAIL":
            kills.append(gid)
    return {"kills": kills, "n_attempted": len(results), "not_reached": not_reached,
            "novel": bool(kills) and str(catalogue_status).upper() == "SURVIVED",
            "catalogue_status": catalogue_status, "results": results,
            "rule": ("ADVISORY. An evolved kill is published beside the catalogue's verdict and "
                     "retires nothing: the ten gates are sealed and decide what they decided.")}


def score(report: dict[str, Any], pool: dict[str, Any]) -> dict[str, Any]:
    """Fitness per genome and survival per certificate, from the falsifier report's own rows."""
    per = report.get("per_certificate") or {}
    fitness: dict[str, dict[str, Any]] = {}
    prey: dict[str, dict[str, Any]] = dict(pool.get("prey") or {})
    class_kills: dict[str, dict[str, int]] = {}
    from libs.validation import falsifiers
    for cid, entry in per.items():
        if not isinstance(entry, dict):
            continue
        ev = entry.get("evolved")
        cat_status = str(entry.get("status") or "")
        row = prey.setdefault(str(cid), {"generations": 0, "killed_by": None, "streak": 0})
        killed_here = False
        for name in entry.get("kills") or []:
            cls = str((falsifiers.CATALOGUE.get(str(name)) or ("", ""))[1])
            c = class_kills.setdefault(cls or "unclassed", {"kills": 0, "runs": 0})
            c["kills"] += 1
        for name in entry.get("tests_run") or []:
            cls = str((falsifiers.CATALOGUE.get(str(name)) or ("", ""))[1])
            c = class_kills.setdefault(cls or "unclassed", {"kills": 0, "runs": 0})
            c["runs"] += 1
        if not isinstance(ev, dict):
            continue
        for gid, res in (ev.get("results") or {}).items():
            f = fitness.setdefault(str(gid), {"attempts": 0, "kills": 0, "novel_kills": 0,
                                              "seconds": 0.0, "unmeasured": 0})
            f["attempts"] += 1
            f["seconds"] += float(res.get("seconds") or 0.0)
            v = str(res.get("verdict"))
            if v == "FAIL":
                f["kills"] += 1
                killed_here = True
                if cat_status == "SURVIVED":
                    f["novel_kills"] += 1
            elif v != "PASS":
                f["unmeasured"] += 1
        row["generations"] = int(row.get("generations") or 0) + 1
        if killed_here:
            row["killed_by"] = sorted(ev.get("kills") or [])
            row["streak"] = 0
        else:
            row["streak"] = int(row.get("streak") or 0) + 1
    for f in fitness.values():
        secs = max(float(f["seconds"]), 0.01)
        f["fitness"] = round((f["kills"] + (NOVEL_WEIGHT - 1.0) * f["novel_kills"]) / secs, 6)
        f["kill_rate"] = round(f["kills"] / max(f["attempts"], 1), 4)
    rates = {cls: round(v["kills"] / max(v["runs"], 1), 4) for cls, v in class_kills.items()}
    return {"fitness": fitness, "prey": prey, "class_kill_rates": rates}


def reproduce(pool: dict[str, Any], fitness: dict[str, Any]) -> dict[str, Any]:
    """Elites survive, breed mutated offspring, the worst retire. Population size is fixed."""
    gen = int(pool.get("generation") or 0) + 1
    genomes = list(pool.get("genomes") or [])
    rng = random.Random(gen * 7919)  # noqa: S311 -- mutation jitter, seeded by generation
    ranked = sorted(genomes,
                    key=lambda g: -float((fitness.get(str(g.get("id"))) or {}).get("fitness", 0.0)))
    elites = ranked[:ELITE] if ranked else []
    scored = [g for g in ranked if str(g.get("id")) in fitness]
    survivors = list(elites)
    offspring: list[dict[str, Any]] = []
    for i, parent in enumerate(elites):
        pv = parent.get("view") or {}
        gid = f"d{gen:03d}{i:02d}"
        base = (str(parent.get("base")) if rng.random() > 0.2
                else rng.choice([b for b in BASES if b != parent.get("base")]))
        offspring.append(_genome(
            gid, base,
            min(max(float(pv.get("block_frac") or 0.5) + rng.uniform(-0.15, 0.15), 0.1), 1.0),
            max(2, int(pv.get("block_len") or 8) + rng.choice((-4, -2, 2, 4))),
            max(0.5, float(pv.get("cost_mult") or 1.0) * rng.choice((0.75, 1.0, 1.5))),
            gen, str(parent.get("id"))))
    keep = [g for g in ranked[ELITE:] if str(g.get("id")) not in
            {str(x.get("id")) for x in offspring}]
    retired = keep[max(0, POP_SIZE - len(survivors) - len(offspring)):]
    kept = keep[:max(0, POP_SIZE - len(survivors) - len(offspring))]
    pool["generation"] = gen
    pool["genomes"] = [*survivors, *offspring, *kept][:POP_SIZE]
    pool["retired"] = [{"id": g.get("id"), "gen": g.get("gen"),
                        "fitness": (fitness.get(str(g.get("id"))) or {}).get("fitness")}
                       for g in retired][-40:]
    return {"generation": gen, "n_elite": len(elites), "n_offspring": len(offspring),
            "n_retired": len(retired), "n_scored": len(scored)}


def kill_rates() -> dict[str, float]:
    """Measured P(kill | class) for the catalogue's own schedule, from the last evolution pass.

    `meta_rnd` reads this to decide whether a measured ordering beats the catalogue's declared
    prior. An empty dict leaves `falsifiers.schedule` exactly as it was."""
    doc = _read(OUT)
    rates = (doc or {}).get("class_kill_rates") if isinstance(doc, dict) else None
    out: dict[str, float] = {}
    for k, v in (rates or {}).items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def build(budget_s: float = 300.0) -> dict[str, Any]:
    t0 = time.monotonic()
    pool = load_pool()
    report = _read(FALSIFIERS_REPORT, {}) or _read(FALSIFIERS_ALT, {}) or {}
    if not report.get("per_certificate"):
        doc: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "status": "UNMEASURED",
               "why": ("no reports/FALSIFIER_VERDICTS.json with per-certificate rows: the "
                       "catalogue has not run here, so no destroyer has attempted anything "
                       "to be scored on"),
               "generation": pool.get("generation"), "population": pool.get("genomes"),
               "prey": pool.get("prey"), "class_kill_rates": {},
               "seconds": round(time.monotonic() - t0, 3)}
        return doc
    scored = score(report, pool)
    pool["fitness"] = scored["fitness"]
    pool["prey"] = scored["prey"]
    ev = reproduce(pool, scored["fitness"])
    _write(POOL, pool)
    fits = scored["fitness"]
    novel = sum(int(f.get("novel_kills") or 0) for f in fits.values())
    kills = sum(int(f.get("kills") or 0) for f in fits.values())
    attempts = sum(int(f.get("attempts") or 0) for f in fits.values())
    prey = scored["prey"]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if attempts else "AWAITING_ATTACKS",
        "generation": ev["generation"], "evolution": ev,
        "population": pool.get("genomes"),
        "fitness": fits,
        "n_attempts": attempts, "n_kills": kills, "n_novel_kills": novel,
        "novel_weight": NOVEL_WEIGHT,
        "prey": {"n": len(prey),
                 "longest_survivor": max(((k, v.get("streak", 0)) for k, v in prey.items()),
                                         key=lambda kv: kv[1], default=(None, 0))[0],
                 "mean_streak": round(sum(float(v.get("streak") or 0) for v in prey.values())
                                      / max(len(prey), 1), 3),
                 "rows": prey},
        "class_kill_rates": scored["class_kill_rates"],
        "seconds": round(time.monotonic() - t0, 3),
        "consumers": [
            "desks/mt5/research/falsifier_run.py -> attack(): every certificate is attacked by "
            "the evolved pool in the same pass, published under `evolved`",
            "desks/mt5/research/meta_rnd.py -> kill_rates(): the measured P(kill | class) is one "
            "of the ordering policies the meta-tournament judges",
        ],
        "boundary": (
            "ADVISORY BY CONSTRUCTION. An evolved kill retires no sleeve, voids no certificate "
            "and moves no gate: the four sealed files are not imported here. What evolves is the "
            "VIEW an existing objection is asked about, never a threshold (L1.60)."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"destroyer pool: could not write {OUT}: {exc}")
        return 1
    if doc.get("status") == "UNMEASURED":
        print(f"destroyer pool: UNMEASURED -- {doc.get('why')}")
    else:
        print(f"destroyer pool: generation {doc['generation']}, {doc['n_attempts']} attack(s), "
              f"{doc['n_kills']} kill(s) of which {doc['n_novel_kills']} novel; "
              f"{doc['evolution']['n_offspring']} offspring, "
              f"{doc['evolution']['n_retired']} retired")
        for gid, f in sorted(doc["fitness"].items(),
                             key=lambda kv: -float(kv[1].get("fitness") or 0))[:6]:
            print(f"   {gid:<10} fitness={f['fitness']:<10.4g} kills={f['kills']} "
                  f"novel={f['novel_kills']} attempts={f['attempts']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
